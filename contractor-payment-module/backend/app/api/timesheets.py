from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends
from app.core.database import get_db
from app.core.auth import require_manager, require_admin
from app.schemas.schemas import (
    TimesheetSubmitDays, TimesheetUpdate, TimesheetReject,
    TimesheetOut, BulkApproveRequest, BulkApproveResult,
    DayCurrentStateOut, DayRateUpdate, SubmissionBatchOut
)
from app.services import swipey

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _can_process_timesheet(timesheet: dict) -> bool:
    return timesheet["status"] == "approved" and timesheet.get("sync_status") in ("pending", "failed")


def _day_to_week_key(day: int) -> str:
    if day <= 7:
        return "week1_hours"
    if day <= 14:
        return "week2_hours"
    if day <= 21:
        return "week3_hours"
    return "week4_hours"


@router.get("", response_model=list[TimesheetOut])
async def list_timesheets(
    outlet: str = None, status: str = None,
    month: int = None, year: int = None,
    sync_status: str = None,
    user=Depends(require_manager)
):
    db = get_db()
    q = db.table("timesheets").select("*").order("created_at", desc=True)
    if outlet:
        q = q.eq("outlet", outlet)
    if status:
        q = q.eq("status", status)
    if month:
        q = q.eq("month", month)
    if year:
        q = q.eq("year", year)
    if sync_status:
        q = q.eq("sync_status", sync_status)
    return q.execute().data


@router.get("/submitted-days/{token}")
async def get_submitted_days(token: str, year: int, month: int):
    """Return day-level entries for a contractor's month (for calendar locking)."""
    db = get_db()
    c_result = db.table("contractors").select("id").eq("registration_token", token).execute()
    if not c_result.data:
        raise HTTPException(status_code=404, detail="Invalid token")
    contractor_id = c_result.data[0]["id"]
    result = db.table("timesheet_days").select("*") \
        .eq("contractor_id", contractor_id).eq("year", year).eq("month", month) \
        .execute()
    return result.data


@router.post("/submit/{token}", response_model=TimesheetOut, status_code=201)
async def submit_timesheet(token: str, body: TimesheetSubmitDays):
    db = get_db()
    c_result = db.table("contractors").select("*").eq("registration_token", token).execute()
    if not c_result.data:
        raise HTTPException(status_code=404, detail="Invalid token")
    contractor = c_result.data[0]
    if contractor["status"] not in ("active", "paid"):
        raise HTTPException(status_code=403, detail="Contractor registration not complete")
    if not body.days:
        raise HTTPException(status_code=400, detail="No days provided")

    primary_outlet = body.outlet or contractor["outlet"]
    now = _utc_now_iso()
    submission_id = str(uuid4())  # groups all day logs from this single submit call

    # ── Step 1: Determine which timesheet record to use ────────────────────────
    # Rule: if latest timesheet for this month is already approved, create a new
    # record so the admin sees a fresh submission requiring review. Otherwise
    # add days to the existing submitted/rejected record.
    existing_ts_list = db.table("timesheets").select("*") \
        .eq("contractor_id", contractor["id"]) \
        .eq("year", body.year).eq("month", body.month) \
        .order("sequence", desc=True) \
        .execute().data

    latest_ts = existing_ts_list[0] if existing_ts_list else None

    if latest_ts is None or latest_ts["status"] in ("approved", "rejected"):
        # First submission, or previous was approved/rejected — start a fresh record
        next_seq = (latest_ts.get("sequence") or 0) + 1 if latest_ts else 1
        ts_result = db.table("timesheets").insert({
            "contractor_id": contractor["id"],
            "contractor_name": contractor["name"],
            "outlet": primary_outlet,
            "hourly_rate": contractor["hourly_rate"],
            "year": body.year,
            "month": body.month,
            "sequence": next_seq,
            "week1_hours": 0, "week2_hours": 0, "week3_hours": 0, "week4_hours": 0,
            "amount": 0,
            "status": "submitted",
            "sync_status": "pending",
            "submitted_at": now,
        }).execute()
        active_ts = ts_result.data[0]
    else:
        # Existing submitted record — add new days to it
        active_ts = latest_ts

    # ── Step 2: Process each submitted day ────────────────────────────────────
    for entry in body.days:
        day_outlet = entry.outlet or primary_outlet
        existing_day = db.table("timesheet_days").select("*") \
            .eq("contractor_id", contractor["id"]) \
            .eq("year", body.year).eq("month", body.month).eq("day", entry.day) \
            .execute()

        if existing_day.data:
            existing = existing_day.data[0]
            if existing["status"] in ("submitted", "approved"):
                continue  # locked — skip silently
            # Resubmit a rejected day — move it into the active timesheet
            db.table("timesheet_days").update({
                "hours": entry.hours,
                "outlet": day_outlet,
                "status": "submitted",
                "rejection_reason": None,
                "timesheet_id": active_ts["id"],
                "updated_at": now,
            }).eq("id", existing["id"]).execute()
            db.table("timesheet_day_logs").insert({
                "contractor_id": contractor["id"],
                "year": body.year, "month": body.month, "day": entry.day,
                "event": "resubmitted",
                "hours": entry.hours,
                "outlet": day_outlet,
                "submission_id": submission_id,
                "timesheet_id": active_ts["id"],
            }).execute()
        else:
            db.table("timesheet_days").insert({
                "contractor_id": contractor["id"],
                "year": body.year, "month": body.month, "day": entry.day,
                "hours": entry.hours,
                "outlet": day_outlet,
                "status": "submitted",
                "timesheet_id": active_ts["id"],
            }).execute()
            db.table("timesheet_day_logs").insert({
                "contractor_id": contractor["id"],
                "year": body.year, "month": body.month, "day": entry.day,
                "event": "submitted",
                "hours": entry.hours,
                "outlet": day_outlet,
                "submission_id": submission_id,
                "timesheet_id": active_ts["id"],
            }).execute()

    # ── Step 3: Recalculate totals for active_ts only ─────────────────────────
    all_days = db.table("timesheet_days").select("*") \
        .eq("timesheet_id", active_ts["id"]) \
        .neq("status", "rejected") \
        .execute().data

    week_hours = {"week1_hours": 0.0, "week2_hours": 0.0, "week3_hours": 0.0, "week4_hours": 0.0}
    for d in all_days:
        week_hours[_day_to_week_key(d["day"])] += float(d["hours"])

    total_hours = sum(week_hours.values())
    amount = round(total_hours * float(contractor["hourly_rate"]), 2)

    result = db.table("timesheets").update({
        **week_hours,
        "amount": amount,
        "outlet": primary_outlet,
        "status": "submitted",
        "submitted_at": now,
    }).eq("id", active_ts["id"]).execute()
    return result.data[0]


@router.get("/history/{token}", response_model=list[TimesheetOut])
async def payment_history(token: str):
    db = get_db()
    c_result = db.table("contractors").select("id").eq("registration_token", token).execute()
    if not c_result.data:
        raise HTTPException(status_code=404, detail="Invalid token")
    contractor_id = c_result.data[0]["id"]
    result = db.table("timesheets").select("*").eq("contractor_id", contractor_id) \
        .order("year", desc=True).order("month", desc=True).execute()
    return result.data


@router.get("/submission-history/{token}", response_model=list[SubmissionBatchOut])
async def submission_history(token: str):
    """Contractor payment history. One entry per timesheet (approval unit) — matches admin view."""
    db = get_db()
    c_result = db.table("contractors").select("id").eq("registration_token", token).execute()
    if not c_result.data:
        raise HTTPException(status_code=404, detail="Invalid token")
    contractor_id = c_result.data[0]["id"]

    timesheets = db.table("timesheets") \
        .select("id,year,month,sequence,status,sync_status,rejection_reason,amount,hourly_rate") \
        .eq("contractor_id", contractor_id) \
        .order("year", desc=True).order("month", desc=True).order("sequence", desc=True) \
        .execute().data

    if not timesheets:
        return []

    # Fetch all active days grouped by timesheet_id for counts + hours + outlets
    all_days = db.table("timesheet_days").select("timesheet_id,hours,outlet,status") \
        .eq("contractor_id", contractor_id) \
        .neq("status", "rejected") \
        .execute().data

    days_by_ts: dict[str, list] = {}
    for d in all_days:
        ts_id = d.get("timesheet_id")
        if ts_id:
            days_by_ts.setdefault(ts_id, []).append(d)

    # Earliest submitted log per timesheet = submitted_at
    logs = db.table("timesheet_day_logs").select("timesheet_id,created_at") \
        .eq("contractor_id", contractor_id) \
        .in_("event", ["submitted", "resubmitted"]) \
        .order("created_at") \
        .execute().data

    first_submitted_by_ts: dict[str, str] = {}
    for log in logs:
        ts_id = log.get("timesheet_id")
        if ts_id and ts_id not in first_submitted_by_ts:
            first_submitted_by_ts[ts_id] = log["created_at"]

    batches = []
    for ts in timesheets:
        ts_id = str(ts["id"])
        days = days_by_ts.get(ts_id, [])
        total_hours = sum(float(d["hours"] or 0) for d in days)
        outlets = list(dict.fromkeys(d["outlet"] for d in days if d.get("outlet")))
        submitted_at = first_submitted_by_ts.get(ts_id) or ts.get("created_at", "")

        batches.append(SubmissionBatchOut(
            submission_id=ts["id"],
            month=ts["month"],
            year=ts["year"],
            sequence=ts.get("sequence", 1),
            submitted_at=submitted_at,
            days_count=len(days),
            total_hours=total_hours,
            outlets=outlets,
            timesheet_status=ts["status"],
            sync_status=ts.get("sync_status"),
            rejection_reason=ts.get("rejection_reason") if ts["status"] == "rejected" else None,
            amount=float(ts["amount"]) if ts.get("amount") is not None else None,
        ))

    return batches


@router.get("/{timesheet_id}/days", response_model=list[DayCurrentStateOut])
async def get_timesheet_days(timesheet_id: str, user=Depends(require_manager)):
    """Current day-level state for a timesheet (used by the admin detail panel)."""
    db = get_db()
    ts_result = db.table("timesheets").select("*").eq("id", timesheet_id).execute()
    if not ts_result.data:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    ts = ts_result.data[0]
    # Filter by timesheet_id for new records; fall back to contractor+period for legacy rows
    days = db.table("timesheet_days").select("*") \
        .eq("timesheet_id", timesheet_id) \
        .order("day") \
        .execute()
    if not days.data:
        # Legacy rows created before timesheet_id column existed
        days = db.table("timesheet_days").select("*") \
            .eq("contractor_id", ts["contractor_id"]) \
            .eq("year", ts["year"]).eq("month", ts["month"]) \
            .order("day") \
            .execute()
    return days.data


@router.get("/{timesheet_id}/day-logs")
async def get_day_logs(timesheet_id: str, user=Depends(require_manager)):
    """Per-day audit log for a specific timesheet submission."""
    db = get_db()
    ts_result = db.table("timesheets").select("*").eq("id", timesheet_id).execute()
    if not ts_result.data:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    ts = ts_result.data[0]
    logs = db.table("timesheet_day_logs").select("*") \
        .eq("timesheet_id", timesheet_id) \
        .order("day").order("created_at") \
        .execute()
    if not logs.data:
        # Legacy fallback for rows without timesheet_id
        logs = db.table("timesheet_day_logs").select("*") \
            .eq("contractor_id", ts["contractor_id"]) \
            .eq("year", ts["year"]).eq("month", ts["month"]) \
            .order("day").order("created_at") \
            .execute()
    return logs.data


@router.patch("/days/{day_id}", response_model=DayCurrentStateOut)
async def update_day(day_id: str, body: DayRateUpdate, user=Depends(require_manager)):
    """Manager: update hourly rate and/or hours for a specific day. Recalculates timesheet amount."""
    if body.hourly_rate is None and body.hours is None:
        raise HTTPException(status_code=400, detail="Provide hourly_rate or hours to update")

    db = get_db()
    day_result = db.table("timesheet_days").select("*").eq("id", day_id).execute()
    if not day_result.data:
        raise HTTPException(status_code=404, detail="Day entry not found")
    day = day_result.data[0]

    day_updates: dict = {"updated_at": _utc_now_iso()}
    if body.hourly_rate is not None:
        day_updates["hourly_rate"] = body.hourly_rate
    if body.hours is not None:
        if body.hours <= 0:
            raise HTTPException(status_code=400, detail="hours must be greater than 0")
        day_updates["hours"] = body.hours

    updated = db.table("timesheet_days").update(day_updates).eq("id", day_id).execute()

    # Write audit log if hours were changed
    if body.hours is not None:
        db.table("timesheet_day_logs").insert({
            "contractor_id": day["contractor_id"],
            "year": day["year"],
            "month": day["month"],
            "day": day["day"],
            "event": "admin_hours_edit",
            "hours": body.hours,
            "outlet": day.get("outlet"),
            "actor_id": user["sub"],
            "timesheet_id": day.get("timesheet_id"),
        }).execute()

    # Recalculate amount for the specific timesheet this day belongs to
    ts_id = day.get("timesheet_id")
    if ts_id:
        ts_result = db.table("timesheets").select("*").eq("id", ts_id).execute()
    else:
        ts_result = db.table("timesheets").select("*") \
            .eq("contractor_id", day["contractor_id"]) \
            .eq("year", day["year"]).eq("month", day["month"]) \
            .execute()

    if ts_result.data:
        ts = ts_result.data[0]
        if ts_id:
            all_days = db.table("timesheet_days").select("*") \
                .eq("timesheet_id", ts_id) \
                .neq("status", "rejected") \
                .execute().data
        else:
            all_days = db.table("timesheet_days").select("*") \
                .eq("contractor_id", day["contractor_id"]) \
                .eq("year", day["year"]).eq("month", day["month"]) \
                .neq("status", "rejected") \
                .execute().data

        # Use the freshly updated hours value for the edited day
        updated_hours = body.hours
        all_days_merged = []
        for d in all_days:
            if d["id"] == day_id and updated_hours is not None:
                all_days_merged.append({**d, "hours": updated_hours})
            else:
                all_days_merged.append(d)

        new_amount = round(sum(
            float(d["hours"]) * float(d["hourly_rate"] if d.get("hourly_rate") is not None else ts["hourly_rate"])
            for d in all_days_merged
        ), 2)

        # Also recalculate week buckets when hours change
        if body.hours is not None:
            week_hours = {"week1_hours": 0.0, "week2_hours": 0.0, "week3_hours": 0.0, "week4_hours": 0.0}
            for d in all_days_merged:
                week_hours[_day_to_week_key(d["day"])] += float(d["hours"])
            db.table("timesheets").update({
                **week_hours,
                "amount": new_amount,
                "updated_at": _utc_now_iso(),
            }).eq("id", ts["id"]).execute()
        else:
            db.table("timesheets").update({
                "amount": new_amount,
                "updated_at": _utc_now_iso(),
            }).eq("id", ts["id"]).execute()

    return updated.data[0]


@router.patch("/{timesheet_id}", response_model=TimesheetOut)
async def update_timesheet(timesheet_id: str, body: TimesheetUpdate, user=Depends(require_manager)):
    db = get_db()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if any(k in updates for k in ("week1_hours", "week2_hours", "week3_hours", "week4_hours")):
        existing = db.table("timesheets").select("*").eq("id", timesheet_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Timesheet not found")
        ts = existing.data[0]
        hours = {
            "week1_hours": updates.get("week1_hours", ts["week1_hours"]),
            "week2_hours": updates.get("week2_hours", ts["week2_hours"]),
            "week3_hours": updates.get("week3_hours", ts["week3_hours"]),
            "week4_hours": updates.get("week4_hours", ts["week4_hours"]),
        }
        total = sum(hours.values())
        updates["amount"] = round(total * float(ts["hourly_rate"]), 2)
        updates.update(hours)

    result = db.table("timesheets").update(updates).eq("id", timesheet_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return result.data[0]


@router.post("/{timesheet_id}/approve", response_model=TimesheetOut)
async def approve_timesheet(timesheet_id: str, user=Depends(require_manager)):
    db = get_db()
    ts_result = db.table("timesheets").select("*").eq("id", timesheet_id).execute()
    if not ts_result.data:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    ts = ts_result.data[0]
    if ts["status"] != "submitted":
        raise HTTPException(status_code=400, detail="Timesheet is not in submitted state")

    result = db.table("timesheets").update({
        "status": "approved",
        "sync_status": "pending",
        "approved_at": _utc_now_iso(),
        "approved_by": user["sub"],
    }).eq("id", timesheet_id).execute()

    # Lock only days belonging to this specific timesheet submission
    locked = db.table("timesheet_days").update({"status": "approved"}) \
        .eq("timesheet_id", timesheet_id) \
        .eq("status", "submitted").execute()
    if not locked.data:
        # Legacy fallback for rows without timesheet_id
        db.table("timesheet_days").update({"status": "approved"}) \
            .eq("contractor_id", ts["contractor_id"]) \
            .eq("year", ts["year"]).eq("month", ts["month"]) \
            .eq("status", "submitted").execute()

    return result.data[0]


@router.post("/{timesheet_id}/reject", response_model=TimesheetOut)
async def reject_timesheet(timesheet_id: str, body: TimesheetReject, user=Depends(require_manager)):
    db = get_db()
    ts_result = db.table("timesheets").select("*").eq("id", timesheet_id).execute()
    if not ts_result.data:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    ts = ts_result.data[0]

    result = db.table("timesheets").update({
        "status": "rejected",
        "rejection_reason": body.rejection_reason,
    }).eq("id", timesheet_id).execute()

    # Unlock days belonging to this specific timesheet submission
    now = _utc_now_iso()
    days_result = db.table("timesheet_days").select("*") \
        .eq("timesheet_id", timesheet_id) \
        .eq("status", "submitted").execute()
    days = days_result.data
    if not days:
        # Legacy fallback
        days = db.table("timesheet_days").select("*") \
            .eq("contractor_id", ts["contractor_id"]) \
            .eq("year", ts["year"]).eq("month", ts["month"]) \
            .eq("status", "submitted").execute().data

    for d in days:
        db.table("timesheet_days").update({
            "status": "rejected",
            "rejection_reason": body.rejection_reason,
            "updated_at": now,
        }).eq("id", d["id"]).execute()
        db.table("timesheet_day_logs").insert({
            "contractor_id": ts["contractor_id"],
            "year": ts["year"], "month": ts["month"], "day": d["day"],
            "event": "rejected",
            "hours": d["hours"],
            "rejection_reason": body.rejection_reason,
            "actor_id": user["sub"],
        }).execute()

    return result.data[0]


def _next_invoice_seq(db, year: int, month: int) -> int:
    """Return the next available sequence number for a given month by checking existing payments."""
    prefix = f"BEN-{year}{month:02d}-"
    existing = db.table("payments").select("invoice_number") \
        .like("invoice_number", f"{prefix}%").execute().data
    if not existing:
        return 1
    seqs = []
    for row in existing:
        try:
            seqs.append(int(row["invoice_number"].split("-")[-1]))
        except (ValueError, IndexError):
            pass
    return max(seqs) + 1 if seqs else 1


@router.post("/bulk-approve", response_model=BulkApproveResult)
async def bulk_approve(body: BulkApproveRequest, user=Depends(require_admin)):
    db = get_db()
    approved = 0
    failed = 0
    results = []

    for ts_id in body.timesheet_ids:
        ts_result = db.table("timesheets").select("*").eq("id", ts_id).execute()
        if not ts_result.data:
            failed += 1
            results.append({"id": ts_id, "status": "error", "detail": "Not found"})
            continue

        ts = ts_result.data[0]
        if not _can_process_timesheet(ts):
            failed += 1
            results.append({
                "id": ts_id, "status": "skipped",
                "detail": f"Cannot process from status={ts['status']} sync_status={ts.get('sync_status')}",
            })
            continue

        contractor = db.table("contractors").select("*").eq("id", ts["contractor_id"]).execute().data
        if not contractor:
            failed += 1
            results.append({"id": ts_id, "status": "error", "detail": "Contractor not found"})
            continue
        contractor = contractor[0]

        now = _utc_now_iso()

        # Reuse existing payment row if a previous attempt already inserted one
        existing_payment = db.table("payments").select("*") \
            .eq("timesheet_id", ts_id).execute().data
        if existing_payment:
            payment_row = existing_payment[0]
            invoice_number = payment_row["invoice_number"]
            db.table("payments").update({
                "sync_status": "syncing",
                "attempted_at": now,
                "error_message": None,
            }).eq("id", payment_row["id"]).execute()
        else:
            seq = _next_invoice_seq(db, ts["year"], ts["month"])
            invoice_number = swipey.generate_invoice_number(contractor["id"], ts["year"], ts["month"], seq)
            payment_row = db.table("payments").insert({
                "timesheet_id": ts_id,
                "contractor_id": contractor["id"],
                "contractor_name": contractor["name"],
                "invoice_number": invoice_number,
                "amount": ts["amount"],
                "sync_status": "syncing",
                "attempted_at": now,
            }).execute().data[0]

        timesheet_updates = {"status": "approved", "sync_status": "syncing"}
        if ts["status"] == "submitted":
            timesheet_updates["approved_at"] = now
            timesheet_updates["approved_by"] = user["sub"]

        db.table("timesheets").update(timesheet_updates).eq("id", ts_id).execute()

        # Lock days
        db.table("timesheet_days").update({"status": "approved"}) \
            .eq("contractor_id", ts["contractor_id"]) \
            .eq("year", ts["year"]).eq("month", ts["month"]) \
            .eq("status", "submitted").execute()

        try:
            swipey_resp = await swipey.create_payment_record(
                contractor_name=contractor["name"],
                acquirer_id=contractor.get("acquirer_id", ""),
                account_number=contractor.get("account_number", ""),
                amount=float(ts["amount"]),
                invoice_number=invoice_number,
                year=ts["year"],
                month=ts["month"],
            )
            db.table("payments").update({
                "sync_status": "synced",
                "swipey_reference": swipey_resp.get("id"),
            }).eq("id", payment_row["id"]).execute()
            db.table("timesheets").update({
                "sync_status": "synced",
                "synced_at": _utc_now_iso(),
            }).eq("id", ts_id).execute()
            approved += 1
            results.append({"id": ts_id, "status": "synced", "invoice": invoice_number})

        except Exception as e:
            db.table("payments").update({
                "sync_status": "failed",
                "error_message": str(e),
            }).eq("id", payment_row["id"]).execute()
            db.table("timesheets").update({"sync_status": "failed"}).eq("id", ts_id).execute()
            failed += 1
            results.append({"id": ts_id, "status": "failed", "detail": str(e)})

    return BulkApproveResult(approved=approved, failed=failed, results=results)

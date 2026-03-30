import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from app.core.database import get_db
from app.core.auth import require_manager
from app.schemas.schemas import (
    ContractorCreate, ContractorUpdate, ContractorOut,
    ContractorPublicOut, ContractorRegisterConfirm, QRParseResult
)
from app.services.qr_parser import parse_qr_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contractors", tags=["contractors"])


def _registration_closed(status: str) -> bool:
    return status in ("inactive", "terminated")


@router.get("", response_model=list[ContractorOut])
async def list_contractors(outlet: str = None, status: str = None, user=Depends(require_manager)):
    db = get_db()
    q = db.table("contractors").select("*").order("created_at", desc=True)
    if outlet:
        q = q.eq("outlet", outlet)
    if status:
        q = q.eq("status", status)
    result = q.execute()
    return result.data


@router.post("", response_model=ContractorOut, status_code=201)
async def create_contractor(body: ContractorCreate, user=Depends(require_manager)):
    db = get_db()

    # Phone uniqueness check — prevent accidental re-invite of same contractor
    existing_phone = db.table("contractors").select("id", "name").eq("phone", body.phone).execute()
    if existing_phone.data:
        existing_name = existing_phone.data[0]["name"]
        raise HTTPException(
            status_code=409,
            detail=f"A contractor with this phone number already exists: {existing_name}. Check the Contractors list before adding again.",
        )

    result = db.table("contractors").insert({
        "name": body.name,
        "phone": body.phone,
        "outlet": body.outlet,
        "hourly_rate": body.hourly_rate,
        "created_by": user["sub"],
    }).execute()
    return result.data[0]


@router.get("/register/{token}", response_model=ContractorPublicOut)
async def get_contractor_by_token(token: str):
    db = get_db()
    result = db.table("contractors").select("*").eq("registration_token", token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Registration link not found or expired")
    c = result.data[0]
    if _registration_closed(c["status"]):
        raise HTTPException(status_code=410, detail="This registration link has been deactivated")
    return c


@router.post("/register/{token}/parse-qr", response_model=QRParseResult)
async def parse_qr(token: str, file: UploadFile = File(...)):
    db = get_db()
    result = db.table("contractors").select("id", "status").eq("registration_token", token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Invalid registration token")
    contractor = result.data[0]
    if _registration_closed(contractor["status"]):
        raise HTTPException(status_code=410, detail="Registration link deactivated")

    image_bytes = await file.read()
    try:
        parsed = parse_qr_image(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Upload QR image to Supabase Storage — failure must not break QR parsing
    try:
        path = f"{contractor['id']}/qr.jpg"
        db.storage.from_("contractor-qr-images").upload(
            path,
            image_bytes,
            {"content-type": file.content_type or "image/jpeg", "upsert": "true"},
        )
        db.table("contractors").update({"qr_image_path": path}).eq("id", contractor["id"]).execute()
    except Exception as exc:
        logger.warning("QR image storage upload failed (non-fatal): %s", exc)

    return QRParseResult(
        acquirer_id=parsed["acquirer_id"],
        account_number=parsed["account_number"],
        bank_name=parsed["bank_name"],
        payee_name=parsed["payee_name"],
        is_duitnow=parsed["is_duitnow"],
    )


@router.get("/{contractor_id}/qr-image")
async def get_qr_image(contractor_id: str, user=Depends(require_manager)):
    db = get_db()
    result = db.table("contractors").select("qr_image_path").eq("id", contractor_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contractor not found")
    qr_image_path = result.data[0].get("qr_image_path")
    if not qr_image_path:
        raise HTTPException(status_code=404, detail="No QR image on file for this contractor")
    try:
        signed = db.storage.from_("contractor-qr-images").create_signed_url(qr_image_path, 3600)
        # supabase-py v2 may return an object or a dict
        if isinstance(signed, dict):
            url = signed.get("signedURL") or signed.get("signed_url") or signed.get("signedUrl")
        else:
            url = getattr(signed, "signed_url", None) or getattr(signed, "signedURL", None)
        if not url:
            raise ValueError("No URL in signed response")
    except Exception as exc:
        logger.error("Failed to create signed URL for %s: %s", qr_image_path, exc)
        raise HTTPException(status_code=500, detail="Could not generate QR image URL")
    return {"signed_url": url}


@router.post("/register/{token}/confirm", response_model=ContractorPublicOut)
async def confirm_registration(token: str, body: ContractorRegisterConfirm):
    db = get_db()
    result = db.table("contractors").select("*").eq("registration_token", token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Invalid registration token")

    contractor = result.data[0]
    if contractor["status"] not in ("pending", "active"):
        raise HTTPException(status_code=400, detail="Registration already completed or deactivated")

    # Gate: payment data must be present before activating
    missing = []
    if not contractor.get("acquirer_id"):
        missing.append("acquirer_id")
    if not contractor.get("account_number"):
        missing.append("account_number")
    if not contractor.get("bank_name"):
        missing.append("bank_name")
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot activate: payment details missing ({', '.join(missing)}). Please upload your QR code first."
        )

    update: dict = {
        "ic_number": body.ic_number,
        "status": "active",
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    if body.name:
        update["name"] = body.name

    updated = db.table("contractors").update(update).eq("registration_token", token).execute()
    return updated.data[0]


@router.post("/register/{token}/save-qr")
async def save_qr_data(token: str, qr: QRParseResult):
    db = get_db()
    result = db.table("contractors").select("id", "status").eq("registration_token", token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Invalid registration token")
    contractor = result.data[0]
    if _registration_closed(contractor["status"]):
        raise HTTPException(status_code=410, detail="Registration link deactivated")

    # Bank account uniqueness check — prevent the same QR being registered twice
    duplicate = db.table("contractors") \
        .select("id", "name", "bank_name") \
        .eq("account_number", qr.account_number) \
        .neq("id", contractor["id"]) \
        .execute()
    if duplicate.data:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This {qr.bank_name} account (···{qr.account_number[-4:]}) is already registered "
                f"to another contractor. Please check you are uploading your own QR code."
            ),
        )

    db.table("contractors").update({
        "acquirer_id": qr.acquirer_id,
        "account_number": qr.account_number,
        "bank_name": qr.bank_name,
    }).eq("registration_token", token).execute()
    return {"ok": True}


@router.get("/{contractor_id}", response_model=ContractorOut)
async def get_contractor(contractor_id: str, user=Depends(require_manager)):
    db = get_db()
    result = db.table("contractors").select("*").eq("id", contractor_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return result.data[0]


@router.patch("/{contractor_id}", response_model=ContractorOut)
async def update_contractor(contractor_id: str, body: ContractorUpdate, user=Depends(require_manager)):
    db = get_db()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = db.table("contractors").update(updates).eq("id", contractor_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return result.data[0]


@router.delete("/{contractor_id}/deactivate")
async def deactivate_contractor(contractor_id: str, user=Depends(require_manager)):
    db = get_db()
    result = db.table("contractors").update({
        "status": "inactive",
        "deactivated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", contractor_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return {"ok": True}

"""
API tests for /timesheets endpoints.
Key scenarios:
  - Resubmission after rejection creates a NEW timesheet (bug fix)
  - Admin day update accepts hours field and writes audit log
  - Timesheet list accepts all-months filter (no month param)
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import make_mock_db, admin_token, manager_token

# ── Fixed UUIDs for fixtures ───────────────────────────────────────────────────
C_ID      = "10000000-0000-0000-0000-000000000001"
TOKEN     = "20000000-0000-0000-0000-000000000001"
TS_OLD    = "30000000-0000-0000-0000-000000000001"
TS_NEW    = "30000000-0000-0000-0000-000000000002"
TS_SUB    = "30000000-0000-0000-0000-000000000003"
TS_APPR   = "30000000-0000-0000-0000-000000000004"
TS_NEW3   = "30000000-0000-0000-0000-000000000005"
DAY_001   = "40000000-0000-0000-0000-000000000001"
DAY_002   = "40000000-0000-0000-0000-000000000002"
DAY_003   = "40000000-0000-0000-0000-000000000003"
USER_001  = "50000000-0000-0000-0000-000000000001"

CONTRACTOR = {
    "id": C_ID, "name": "Ahmad Salleh", "phone": "+60123456789",
    "outlet": "BENS-KLCC", "hourly_rate": 12.50, "status": "active",
    "registration_token": TOKEN, "acquirer_id": "890053",
    "account_number": "601234567890", "bank_name": "Touch and Go Digital",
    "ic_number": "901231141234", "qr_image_path": None,
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
    "registered_at": "2026-01-15T00:00:00+00:00",
}

def _ts(id_, seq, status, month=3, rejection_reason=None):
    return {
        "id": id_, "contractor_id": C_ID, "contractor_name": "Ahmad Salleh",
        "outlet": "BENS-KLCC", "hourly_rate": 12.50, "year": 2026, "month": month,
        "sequence": seq, "week1_hours": 0, "week2_hours": 8.0, "week3_hours": 0,
        "week4_hours": 0, "total_hours": 8.0, "amount": 100.0,
        "status": status, "sync_status": "pending",
        "rejection_reason": rejection_reason,
        "submitted_at": "2026-03-01T00:00:00+00:00",
        "approved_at": None, "approved_by": None, "synced_at": None,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-03-02T00:00:00+00:00",
    }

REJECTED_TS = _ts(TS_OLD, 1, "rejected", rejection_reason="Wrong hours")
NEW_TS      = _ts(TS_NEW, 2, "submitted")
SUBMITTED_TS = _ts(TS_SUB, 1, "submitted")

def _day(id_, day_num, ts_id, hours=8.0):
    return {
        "id": id_, "contractor_id": C_ID, "year": 2026, "month": 3,
        "day": day_num, "hours": hours, "outlet": "BENS-KLCC",
        "status": "submitted", "timesheet_id": ts_id,
        "rejection_reason": None, "hourly_rate": None,
        "created_at": "2026-03-15T00:00:00+00:00",
        "updated_at": "2026-03-15T00:00:00+00:00",
    }


class TestResubmissionAfterRejection:
    """Bug fix: resubmitting after rejection must create a NEW timesheet record."""

    def test_resubmit_creates_new_timesheet_sequence(self):
        day = _day(DAY_001, 15, TS_NEW)
        db = make_mock_db(
            [CONTRACTOR],        # contractor lookup by token
            [REJECTED_TS],       # existing timesheets (latest = rejected)
            [NEW_TS],            # new timesheet INSERT
            [],                  # existing day 15 lookup → none
            [day],               # timesheet_days INSERT
            [{"id": USER_001}],  # day log INSERT
            [day],               # recalc: all days for this timesheet
            [NEW_TS],            # timesheet UPDATE (totals)
        )

        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.post(
                f"/timesheets/submit/{TOKEN}",
                json={"year": 2026, "month": 3, "outlet": "BENS-KLCC",
                      "days": [{"day": 15, "hours": 8.0}]},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == TS_NEW
        assert data["sequence"] == 2
        assert data["status"] == "submitted"

    def test_resubmit_after_approval_also_creates_new_sequence(self):
        approved_ts = _ts(TS_APPR, 1, "approved", month=4)
        new_seq2 = _ts(TS_NEW3, 2, "submitted", month=4)
        day = _day(DAY_002, 1, TS_NEW3)

        db = make_mock_db(
            [CONTRACTOR],
            [approved_ts],
            [new_seq2],
            [],
            [day],
            [{"id": USER_001}],
            [day],
            [new_seq2],
        )

        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.post(
                f"/timesheets/submit/{TOKEN}",
                json={"year": 2026, "month": 4, "outlet": "BENS-KLCC",
                      "days": [{"day": 1, "hours": 8.0}]},
            )

        assert resp.status_code == 201
        assert resp.json()["sequence"] == 2

    def test_resubmit_to_existing_submitted_record_reuses_it(self):
        """Submitting additional days to a still-submitted record appends to it."""
        day = _day(DAY_003, 20, TS_SUB)
        updated_ts = {**SUBMITTED_TS, "week3_hours": 8.0, "total_hours": 16.0, "amount": 200.0}

        db = make_mock_db(
            [CONTRACTOR],
            [SUBMITTED_TS],      # latest is submitted — reuse it
            [],                  # day 20 not yet submitted
            [day],
            [{"id": USER_001}],
            [day],
            [updated_ts],
        )

        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.post(
                f"/timesheets/submit/{TOKEN}",
                json={"year": 2026, "month": 3, "outlet": "BENS-KLCC",
                      "days": [{"day": 20, "hours": 8.0}]},
            )

        assert resp.status_code == 201
        assert resp.json()["id"] == TS_SUB
        assert resp.json()["sequence"] == 1


class TestAdminDayUpdate:
    """PATCH /timesheets/days/{day_id} — admin can update hours and/or rate."""

    DAY = _day(DAY_001, 15, TS_SUB)
    TS  = {**SUBMITTED_TS, "id": TS_SUB, "hourly_rate": 12.50}

    def test_update_hours_returns_updated_day(self):
        updated_day = {**self.DAY, "hours": 6.0}
        db = make_mock_db(
            [self.DAY],           # day lookup
            [updated_day],        # day UPDATE
            [{"id": USER_001}],   # audit log INSERT (hours changed)
            [self.TS],            # timesheet lookup for recalc
            [updated_day],        # all days for recalc
            [self.TS],            # timesheet UPDATE
        )

        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.patch(
                f"/timesheets/days/{DAY_001}",
                json={"hours": 6.0},
                headers={"Authorization": f"Bearer {admin_token()}"},
            )

        assert resp.status_code == 200
        assert resp.json()["hours"] == 6.0

    def test_update_rate_only_no_audit_log(self):
        updated_day = {**self.DAY, "hourly_rate": 15.0}
        db = make_mock_db(
            [self.DAY],
            [updated_day],        # day UPDATE
            # No audit log INSERT when only rate changes
            [self.TS],            # timesheet lookup
            [self.DAY],           # all days for recalc
            [self.TS],            # timesheet UPDATE
        )

        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.patch(
                f"/timesheets/days/{DAY_001}",
                json={"hourly_rate": 15.0},
                headers={"Authorization": f"Bearer {admin_token()}"},
            )

        assert resp.status_code == 200

    def test_neither_field_returns_400(self):
        db = make_mock_db()
        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.patch(
                f"/timesheets/days/{DAY_001}",
                json={},
                headers={"Authorization": f"Bearer {admin_token()}"},
            )
        assert resp.status_code == 400

    def test_manager_can_update_days(self):
        """Manager role can now edit hours (changed from admin-only)."""
        updated_day = {**self.DAY, "hours": 6.0}
        db = make_mock_db(
            [self.DAY],
            [updated_day],
            [{"id": USER_001}],
            [self.TS],
            [updated_day],
            [self.TS],
        )
        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.patch(
                f"/timesheets/days/{DAY_001}",
                json={"hours": 6.0},
                headers={"Authorization": f"Bearer {manager_token()}"},
            )
        assert resp.status_code == 200

    def test_unauthenticated_update_returns_401(self):
        db = make_mock_db()
        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.patch(
                f"/timesheets/days/{DAY_001}",
                json={"hours": 6.0},
            )
        assert resp.status_code == 401

    def test_hours_zero_returns_400(self):
        db = make_mock_db([self.DAY])
        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.patch(
                f"/timesheets/days/{DAY_001}",
                json={"hours": 0.0},
                headers={"Authorization": f"Bearer {admin_token()}"},
            )
        assert resp.status_code == 400


class TestTimesheetListFilters:
    """GET /timesheets — filters including all-months."""

    def test_all_months_omits_month_param(self):
        ts_jan = _ts(TS_OLD, 1, "submitted", month=1)
        ts_mar = _ts(TS_NEW, 1, "submitted", month=3)
        db = make_mock_db([ts_jan, ts_mar])

        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.get(
                "/timesheets",
                params={"year": 2026},
                headers={"Authorization": f"Bearer {admin_token()}"},
            )

        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_outlet(self):
        ts_klcc = _ts(TS_OLD, 1, "submitted")
        db = make_mock_db([ts_klcc])

        with patch("app.api.timesheets.get_db", return_value=db):
            client = TestClient(app)
            resp = client.get(
                "/timesheets",
                params={"year": 2026, "month": 3, "outlet": "BENS-KLCC"},
                headers={"Authorization": f"Bearer {admin_token()}"},
            )

        assert resp.status_code == 200
        assert resp.json()[0]["outlet"] == "BENS-KLCC"

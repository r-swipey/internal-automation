"""
API tests for /contractors endpoints.
Key scenarios:
  - IC/passport field accepts any alphanumeric string
  - Re-activation retains existing QR/bank data
  - Registration requires QR to be uploaded first
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import make_mock_db, admin_token

C_ID  = "10000000-0000-0000-0000-000000000001"
TOKEN = "20000000-0000-0000-0000-000000000001"

PENDING_CONTRACTOR = {
    "id": C_ID, "name": "Siti Rahimah", "phone": "+60122223333",
    "outlet": "BENS-KLCC", "hourly_rate": 12.50, "status": "pending",
    "registration_token": TOKEN, "acquirer_id": "890053",
    "account_number": "601234567890", "bank_name": "Touch and Go Digital",
    "ic_number": None, "qr_image_path": None,
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
    "registered_at": None,
}

ACTIVE_CONTRACTOR = {
    **PENDING_CONTRACTOR,
    "status": "active", "ic_number": "901231141234",
    "registered_at": "2026-01-15T00:00:00+00:00",
}


class TestConfirmRegistration:
    def test_accepts_standard_ic_format(self):
        updated = {**ACTIVE_CONTRACTOR, "ic_number": "901231-14-1234"}
        db = make_mock_db([PENDING_CONTRACTOR], [updated])

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.post(
                f"/contractors/register/{TOKEN}/confirm",
                json={"ic_number": "901231-14-1234"},
            )

        assert resp.status_code == 200

    def test_accepts_passport_number(self):
        updated = {**ACTIVE_CONTRACTOR, "ic_number": "A12345678"}
        db = make_mock_db([PENDING_CONTRACTOR], [updated])

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.post(
                f"/contractors/register/{TOKEN}/confirm",
                json={"ic_number": "A12345678"},
            )

        assert resp.status_code == 200

    def test_accepts_any_freeform_id(self):
        updated = {**ACTIVE_CONTRACTOR, "ic_number": "MYKAD-OLD-FORMAT-999"}
        db = make_mock_db([PENDING_CONTRACTOR], [updated])

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.post(
                f"/contractors/register/{TOKEN}/confirm",
                json={"ic_number": "MYKAD-OLD-FORMAT-999"},
            )

        assert resp.status_code == 200

    def test_requires_qr_data_before_confirming(self):
        no_qr = {**PENDING_CONTRACTOR, "acquirer_id": None, "account_number": None, "bank_name": None}
        db = make_mock_db([no_qr])

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.post(
                f"/contractors/register/{TOKEN}/confirm",
                json={"ic_number": "901231141234"},
            )

        assert resp.status_code == 400
        assert "payment details missing" in resp.json()["detail"].lower()

    def test_inactive_contractor_link_returns_error(self):
        inactive = {**ACTIVE_CONTRACTOR, "status": "inactive"}
        db = make_mock_db([inactive])

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.get(f"/contractors/register/{TOKEN}")

        assert resp.status_code == 410

    def test_invalid_token_returns_404(self):
        db = make_mock_db([])  # no contractor found

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.get("/contractors/register/invalid-token")

        assert resp.status_code == 404


class TestReactivation:
    def test_reactivation_sets_status_to_active(self):
        """Re-activating an inactive contractor sets status=active (not pending)."""
        inactive = {**ACTIVE_CONTRACTOR, "status": "inactive"}
        updated = {**ACTIVE_CONTRACTOR, "status": "active"}
        db = make_mock_db([updated])

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.patch(
                f"/contractors/{C_ID}",
                json={"status": "active"},
                headers={"Authorization": f"Bearer {admin_token()}"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_reactivated_contractor_keeps_bank_data(self):
        """
        After reactivation the contractor record still has acquirer_id / account_number.
        The GET /register/{token} endpoint exposes bank_name + account_number
        so the frontend can skip the QR step.
        """
        reactivated = {**ACTIVE_CONTRACTOR, "status": "pending"}
        db = make_mock_db([reactivated])

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.get(f"/contractors/register/{TOKEN}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["bank_name"] == "Touch and Go Digital"
        assert data["account_number"] == "601234567890"


class TestSaveQR:
    def test_save_qr_accepts_is_proxy_id_field(self):
        """save-qr endpoint accepts the is_proxy_id field (ignored for storage but must not 422)."""
        contractor = {**PENDING_CONTRACTOR, "account_number": None}
        updated = {**PENDING_CONTRACTOR}
        db = make_mock_db(
            [contractor],   # token lookup
            [],             # duplicate account check
            [updated],      # update
        )

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.post(
                f"/contractors/register/{TOKEN}/save-qr",
                json={
                    "acquirer_id": "890053",
                    "account_number": "601234567890",
                    "bank_name": "Touch and Go Digital",
                    "payee_name": "Siti Rahimah",
                    "is_duitnow": True,
                    "is_proxy_id": False,
                },
            )

        assert resp.status_code == 200

    def test_duplicate_account_number_returns_409(self):
        """Same bank account registered to a different contractor must be rejected."""
        contractor = {**PENDING_CONTRACTOR}
        duplicate = [{"id": "99999999-0000-0000-0000-000000000001", "name": "Other Person", "bank_name": "Touch and Go Digital"}]
        db = make_mock_db(
            [contractor],
            duplicate,   # duplicate check finds a match
        )

        with patch("app.api.contractors.get_db", return_value=db):
            client = TestClient(app)
            resp = client.post(
                f"/contractors/register/{TOKEN}/save-qr",
                json={
                    "acquirer_id": "890053",
                    "account_number": "601234567890",
                    "bank_name": "Touch and Go Digital",
                    "payee_name": "Siti Rahimah",
                    "is_duitnow": True,
                    "is_proxy_id": False,
                },
            )

        assert resp.status_code == 409

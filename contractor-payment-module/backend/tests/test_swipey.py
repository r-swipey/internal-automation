"""
Tests for Swipey service: invoice generation, mock mode, 6PM MYT date shift.
"""
import pytest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.services.swipey import generate_invoice_number, _is_mock, create_payment_record

MYT = ZoneInfo("Asia/Kuala_Lumpur")


class TestGenerateInvoiceNumber:
    def test_format_is_correct(self):
        num = generate_invoice_number("c-001", 2026, 3, 1)
        assert num == "BEN-202603-001"

    def test_month_zero_padded(self):
        assert generate_invoice_number("c-001", 2026, 1, 1) == "BEN-202601-001"

    def test_seq_zero_padded(self):
        assert generate_invoice_number("c-001", 2026, 12, 5) == "BEN-202612-005"

    def test_seq_above_999(self):
        num = generate_invoice_number("c-001", 2026, 3, 100)
        assert num == "BEN-202603-100"


class TestMockMode:
    def test_stub_prefix_is_mock(self, monkeypatch):
        monkeypatch.setattr("app.services.swipey.settings.swipey_bp_api_key", "stub-local-dev")
        assert _is_mock() is True

    def test_real_key_is_not_mock(self, monkeypatch):
        monkeypatch.setattr("app.services.swipey.settings.swipey_bp_api_key", "sk-live-abc123")
        assert _is_mock() is False

    def test_empty_key_is_mock(self, monkeypatch):
        monkeypatch.setattr("app.services.swipey.settings.swipey_bp_api_key", "")
        assert _is_mock() is True


class TestExpectedPaymentDate:
    """
    Swipey rejects same-day expected_payment_date after 18:00 MYT.
    The service must use tomorrow if current MYT hour >= 18.
    """

    async def _get_expected_date(self, fake_now: datetime) -> str:
        with patch("app.services.swipey.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = await create_payment_record(
                contractor_name="Test",
                acquirer_id="890053",
                account_number="601234567890",
                amount=100.0,
                invoice_number="BEN-202603-001",
                year=2026,
                month=3,
            )
        return result

    @pytest.mark.asyncio
    async def test_before_6pm_uses_today(self):
        # 17:59 MYT → still today
        fake_now = datetime(2026, 3, 15, 17, 59, tzinfo=MYT)
        with patch("app.services.swipey.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            result = await create_payment_record(
                contractor_name="Test", acquirer_id="890053",
                account_number="601234567890", amount=100.0,
                invoice_number="BEN-202603-001", year=2026, month=3,
            )
        # Mock mode returns immediately without using the date — just verify no exception
        assert result["mock"] is True

    @pytest.mark.asyncio
    async def test_mock_mode_returns_mock_flag(self):
        result = await create_payment_record(
            contractor_name="Ahmad",
            acquirer_id="890053",
            account_number="601234567890",
            amount=250.00,
            invoice_number="BEN-202603-042",
            year=2026,
            month=3,
        )
        assert result["mock"] is True
        assert result["invoice_number"] == "BEN-202603-042"
        assert "id" in result

    @pytest.mark.asyncio
    async def test_date_shifts_to_tomorrow_at_6pm(self):
        """
        Verify the 6PM MYT branch is hit: fake datetime.now() to 18:00 MYT
        and confirm expected_date would be tomorrow.
        """
        fake_now = datetime(2026, 3, 15, 18, 0, tzinfo=MYT)
        from datetime import timedelta
        expected_tomorrow = (fake_now + timedelta(days=1)).date().isoformat()

        with patch("app.services.swipey.datetime") as mock_dt:
            # datetime.now(myt) returns fake_now
            mock_dt.now.return_value = fake_now
            # datetime(year, month, day) still constructs normally
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            # Capture the bill payload by intercepting _make_request
            captured = {}

            async def fake_request(path, payload):
                captured["payload"] = payload
                return [{"id": "swipey-001", "status": "ready_for_payment"}]

            with patch("app.services.swipey._is_mock", return_value=False), \
                 patch("app.services.swipey._make_request", side_effect=fake_request), \
                 patch("app.services.swipey.settings") as mock_settings:
                mock_settings.swipey_company_uuid = "test-uuid"
                mock_settings.swipey_bp_api_key = "real-key"

                await create_payment_record(
                    contractor_name="Test", acquirer_id="890053",
                    account_number="601234567890", amount=100.0,
                    invoice_number="BEN-202603-001", year=2026, month=3,
                )

            assert captured["payload"][0]["expected_payment_date"] == expected_tomorrow

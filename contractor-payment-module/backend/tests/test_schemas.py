"""
Tests for Pydantic schema validation — especially fields changed in this sprint.
"""
import pytest
from pydantic import ValidationError
from app.schemas.schemas import (
    ContractorRegisterConfirm,
    DayRateUpdate,
    TimesheetSubmitDays,
    DayEntry,
    QRParseResult,
    SubmissionBatchOut,
)


class TestContractorRegisterConfirm:
    def test_accepts_standard_ic(self):
        obj = ContractorRegisterConfirm(ic_number="901231-14-1234")
        assert obj.ic_number == "901231-14-1234"

    def test_accepts_ic_without_dashes(self):
        obj = ContractorRegisterConfirm(ic_number="901231141234")
        assert obj.ic_number == "901231141234"

    def test_accepts_passport_alphanumeric(self):
        obj = ContractorRegisterConfirm(ic_number="A12345678")
        assert obj.ic_number == "A12345678"

    def test_accepts_any_freeform_string(self):
        obj = ContractorRegisterConfirm(ic_number="X9999-PASSPORT-2024")
        assert obj.ic_number == "X9999-PASSPORT-2024"

    def test_name_optional(self):
        obj = ContractorRegisterConfirm(ic_number="901231141234")
        assert obj.name is None

    def test_name_can_override(self):
        obj = ContractorRegisterConfirm(ic_number="901231141234", name="Ahmad bin Ali")
        assert obj.name == "Ahmad bin Ali"

    def test_ic_number_required(self):
        with pytest.raises(ValidationError):
            ContractorRegisterConfirm()


class TestDayRateUpdate:
    def test_hourly_rate_only(self):
        obj = DayRateUpdate(hourly_rate=15.50)
        assert obj.hourly_rate == 15.50
        assert obj.hours is None

    def test_hours_only(self):
        obj = DayRateUpdate(hours=7.5)
        assert obj.hours == 7.5
        assert obj.hourly_rate is None

    def test_both_fields(self):
        obj = DayRateUpdate(hourly_rate=12.00, hours=8.0)
        assert obj.hourly_rate == 12.00
        assert obj.hours == 8.0

    def test_neither_field_is_valid_schema(self):
        # Schema allows neither — endpoint rejects it but schema itself is valid
        obj = DayRateUpdate()
        assert obj.hourly_rate is None
        assert obj.hours is None


class TestTimesheetSubmitDays:
    def test_valid_submission(self):
        body = TimesheetSubmitDays(
            year=2026, month=3, outlet="BENS-KLCC",
            days=[DayEntry(day=1, hours=8.0), DayEntry(day=2, hours=7.5)],
        )
        assert len(body.days) == 2
        assert body.days[0].hours == 8.0

    def test_day_entry_accepts_half_hours(self):
        entry = DayEntry(day=15, hours=4.5)
        assert entry.hours == 4.5

    def test_outlet_defaults_to_none(self):
        body = TimesheetSubmitDays(year=2026, month=3, days=[DayEntry(day=1, hours=8)])
        assert body.outlet is None


class TestQRParseResult:
    def test_is_proxy_id_defaults_false(self):
        obj = QRParseResult(
            acquirer_id="890053", account_number="601234567890",
            bank_name="Touch and Go Digital", payee_name="Ahmad",
            is_duitnow=True,
        )
        assert obj.is_proxy_id is False

    def test_is_proxy_id_can_be_set_true(self):
        obj = QRParseResult(
            acquirer_id="588734", account_number="",
            bank_name="MAYBANK", payee_name="Kalyana",
            is_duitnow=True, is_proxy_id=True,
        )
        assert obj.is_proxy_id is True
        assert obj.account_number == ""


class TestSubmissionBatchOut:
    def test_sequence_defaults_to_one(self):
        obj = SubmissionBatchOut(
            month=3, year=2026,
            submitted_at="2026-03-01T00:00:00+00:00",
            days_count=5, total_hours=40.0, outlets=["BENS-KLCC"],
            timesheet_status="approved", amount=500.0,
        )
        assert obj.sequence == 1

    def test_sequence_can_be_set(self):
        obj = SubmissionBatchOut(
            month=3, year=2026, sequence=2,
            submitted_at="2026-03-01T00:00:00+00:00",
            days_count=3, total_hours=24.0, outlets=["BENS-KLCC"],
            timesheet_status="submitted",
        )
        assert obj.sequence == 2

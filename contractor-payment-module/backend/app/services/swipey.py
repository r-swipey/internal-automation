"""
Swipey Bill Payment API integration.
Endpoint: POST /api/v4/external/bill-payment/{company_uuid}/bills/create/
Header:   X-API-Key
"""

import asyncio
import uuid
import calendar
from datetime import date
import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds

# Map DuitNow acquirer IDs (from QR) → Swipey's exact bank_name + swift_code
# Source of truth: Swipey List of bank accounts_PROD.csv
ACQUIRER_TO_SWIPEY_BANK = {
    "890053": {"bank_name": "Touch and Go Digital", "swift_code": "TNGDMYNB"},
    "588734": {"bank_name": "MAYBANK",              "swift_code": "MBBEMYKL"},
    "501664": {"bank_name": "AFFIN BANK",           "swift_code": "PHBMMYKL"},
    # Add more as new acquirer IDs are confirmed from real QR samples:
    # "XXXXXX": {"bank_name": "PUBLIC BANK",       "swift_code": "PBBEMYKL"},
}


def _is_mock() -> bool:
    key = settings.swipey_bp_api_key
    return not key or key.startswith("stub")


async def _make_request(path: str, payload: list) -> dict:
    headers = {
        "X-API-Key": settings.swipey_bp_api_key,
        "Content-Type": "application/json",
    }
    url = f"{settings.swipey_api_url}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def create_payment_record(
    contractor_name: str,
    acquirer_id: str,
    account_number: str,
    amount: float,
    invoice_number: str,
    year: int = 0,
    month: int = 0,
) -> dict:
    """
    Create a bill in Swipey via the Bill Payment API.
    Mock mode is active when SWIPEY_BP_API_KEY is unset or starts with 'stub'.
    """
    # ── Mock mode ─────────────────────────────────────────────────────────────
    if _is_mock():
        logger.info(f"[MOCK] Swipey bill: {invoice_number} | {contractor_name} | RM{amount:.2f}")
        await asyncio.sleep(0.3)
        return {
            "id": f"mock-{uuid.uuid4().hex[:8]}",
            "invoice_number": invoice_number,
            "status": "ready_for_payment",
            "mock": True,
        }

    if not settings.swipey_company_uuid:
        raise RuntimeError("SWIPEY_COMPANY_UUID is not configured")

    # ── Dates ─────────────────────────────────────────────────────────────────
    today = date.today()
    if year and month:
        last_day = calendar.monthrange(year, month)[1]
        due_date = date(year, month, last_day).isoformat()
    else:
        last_day = calendar.monthrange(today.year, today.month)[1]
        due_date = date(today.year, today.month, last_day).isoformat()
    expected_date = today.isoformat()

    # ── Bank mapping — acquirer ID → Swipey bank_name + swift_code ────────────
    bank_info = ACQUIRER_TO_SWIPEY_BANK.get(acquirer_id)
    if not bank_info:
        raise ValueError(
            f"Acquirer ID '{acquirer_id}' is not mapped to a Swipey bank. "
            f"Add it to ACQUIRER_TO_SWIPEY_BANK in swipey.py."
        )
    swipey_bank_name = bank_info["bank_name"]
    swift_code = bank_info["swift_code"]
    amount_str = f"{amount:.2f}"

    bill = {
        "name": f"Payment - {contractor_name} ({invoice_number})",
        "status": "pending_approval",
        "origin_amount": amount_str,
        "origin_amount_currency": "MYR",
        "amount": amount_str,
        "payment_due_date": due_date,
        "expected_payment_date": expected_date,
        "invoice_number": invoice_number,
        "vendor_name": contractor_name,
        "bank_account_number": account_number,
        "bank_account_name": contractor_name,
        "jompay_biller_code": None,
        "jompay_reference_code_1": None,
        "jompay_reference_code_2": None,
        "bank_name": swipey_bank_name,
        "bank_swift_code": swift_code,
    }

    path = f"/api/v4/external/bill-payment/{settings.swipey_company_uuid}/bills/create/"

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Swipey sync attempt {attempt} for invoice {invoice_number}")
            result = await _make_request(path, [bill])
            logger.info(f"Swipey sync success for invoice {invoice_number}")
            # API returns a list; grab first item
            if isinstance(result, list) and result:
                return result[0]
            return result
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code in (400, 422):
                logger.error(f"Swipey validation error for {invoice_number}: {e.response.text}")
                raise ValueError(f"Swipey rejected payment: {e.response.text}")
            logger.warning(f"Swipey attempt {attempt} failed ({e.response.status_code}), retrying...")
        except Exception as e:
            last_error = e
            logger.warning(f"Swipey attempt {attempt} error: {str(e)}, retrying...")

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_BASE_DELAY ** attempt)

    raise RuntimeError(f"Swipey sync failed after {MAX_RETRIES} attempts: {str(last_error)}")


def generate_invoice_number(contractor_id: str, year: int, month: int, seq: int) -> str:
    """Format: BEN-YYYYMM-SEQ (e.g. BEN-202603-001)"""
    return f"BEN-{year}{month:02d}-{seq:03d}"

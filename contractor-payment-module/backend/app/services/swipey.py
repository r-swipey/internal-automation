"""
Swipey Bill Payment API integration.
Endpoint: POST /api/v4/external/bill-payment/{company_uuid}/bills/create/
Header:   X-API-Key
"""

import asyncio
import uuid
import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds

# Map DuitNow acquirer IDs (from QR) → Swipey's exact bank_name + swift_code
# Source of truth: Swipey List of bank accounts_PROD.csv
ACQUIRER_TO_SWIPEY_BANK = {
    # Source: Swipey List of bank accounts_PROD.csv
    "589373": {"bank_name": "AGRO BANK",                                        "swift_code": "AGOBMYKL"},
    "501664": {"bank_name": "AFFIN BANK",                                       "swift_code": "PHBMMYKL"},
    "432134": {"bank_name": "AL RAJHI BANK",                                    "swift_code": "RJHIMYKL"},
    "504374": {"bank_name": "ALLIANCE BANK",                                    "swift_code": "MFBBMYKL"},
    "564169": {"bank_name": "AMBANK",                                           "swift_code": "ARBKMYKL"},
    "629188": {"bank_name": "BANK OF AMERICA MERRILL LYNCH",                    "swift_code": "BOFAMY2X"},
    "629152": {"bank_name": "BANK OF CHINA",                                    "swift_code": "BKCHMYKL"},
    "603346": {"bank_name": "BANK ISLAM",                                       "swift_code": "BIMBMYKL"},
    "564167": {"bank_name": "BANK MUAMALAT",                                    "swift_code": "BMMBMYKL"},
    "589267": {"bank_name": "BANK RAKYAT",                                      "swift_code": "BKRMMYKL"},
    "420709": {"bank_name": "BANK SIMPANAN NASIONAL(BSN)",                      "swift_code": "BSNAMYK1"},
    "629204": {"bank_name": "BNP PARIBAS",                                      "swift_code": "BNPAMYKL"},
    "629261": {"bank_name": "CHINA CONSTRUCTION BANK (CCB)",                    "swift_code": "PCBCMYKL"},
    "501854": {"bank_name": "CIMB",                                             "swift_code": "CIBBMYKL"},
    "589170": {"bank_name": "CITIBANK",                                         "swift_code": "CITIMYKL"},
    "629246": {"bank_name": "DEUTSCHE BANK",                                    "swift_code": "DEUTMYKL"},
    "629279": {"bank_name": "GX BANK BERHAD",                                   "swift_code": "GXSPMYKL"},
    "588830": {"bank_name": "HONG LEONG BANK",                                  "swift_code": "HLBBMYKL"},
    "589836": {"bank_name": "HSBC",                                             "swift_code": "HBMBMYKL"},
    "629253": {"bank_name": "INDUSTRIAL & COMMERCIAL BANK OF CHINA (ICBC)",     "swift_code": "ICBKMYKL"},
    "629212": {"bank_name": "J.P. MORGAN",                                      "swift_code": "CHASMYKX"},
    "639406": {"bank_name": "KUWAIT FINANCE HOUSE",                             "swift_code": "KFHOMYKL"},
    "588734": {"bank_name": "MAYBANK",                                          "swift_code": "MBBEMYKL"},
    "432310": {"bank_name": "MBSB BANK",                                        "swift_code": "AFBQMYKL"},
    "629220": {"bank_name": "MIZUHO CORP BANK (MALAYSIA) BERHAD",               "swift_code": "MHCBMYKA"},
    "629196": {"bank_name": "BANK OF TOKYO-MITSUBISHI UFJ(MALAYSIA) BERHAD",    "swift_code": "BOTKMY21"},
    "504324": {"bank_name": "OCBC BANK",                                        "swift_code": "OCBCMYKL"},
    "564162": {"bank_name": "PUBLIC BANK",                                      "swift_code": "PBBEMYKL"},
    "564160": {"bank_name": "RHB BANK",                                         "swift_code": "RHBBMYKL"},
    "539981": {"bank_name": "STANDARD CHARTERED",                               "swift_code": "SCBLMYKX"},
    "629238": {"bank_name": "SUMITOMO MITSUI BANKING CORPORATION MALAYSIA BERHAD", "swift_code": "SMBCMYKL"},
    "890053": {"bank_name": "Touch and Go Digital",                             "swift_code": "TNGDMYNB"},
    "519469": {"bank_name": "UNITED OVERSEAS BANK (DIQUOB)",                    "swift_code": "UOVBMYKL"},
    # E-wallets/digital banks below — must exist in Swipey DB before activating:
    # "890111": {"bank_name": "MERCHANTRADE ASIA", "swift_code": ""},   # pending ClickUp task
    # "629295": {"bank_name": "AEON BANK",         "swift_code": ""},   # pending ClickUp task
    # "890012": {"bank_name": "BIGPAY",            "swift_code": ""},   # pending ClickUp task
    # "629303": {"bank_name": "BOOST BANK",        "swift_code": ""},   # pending ClickUp task
    # "890046": {"bank_name": "GPAY NETWORK",      "swift_code": ""},   # pending ClickUp task
    # "890152": {"bank_name": "KIPLEPAY",          "swift_code": ""},   # pending ClickUp task
    # "890087": {"bank_name": "RAZER PAY",         "swift_code": ""},   # pending ClickUp task
    # "890004": {"bank_name": "SHOPEE PAY",        "swift_code": ""},   # pending ClickUp task
    # "629287": {"bank_name": "YTL DIGITAL BANK",  "swift_code": ""},   # pending ClickUp task
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
    myt = ZoneInfo("Asia/Kuala_Lumpur")
    now_myt = datetime.now(myt)
    # Swipey rejects same-day expected_payment_date after 18:00 MYT
    payment_date = now_myt.date() if now_myt.hour < 18 else (now_myt + timedelta(days=1)).date()
    if year and month:
        last_day = calendar.monthrange(year, month)[1]
        due_date = date(year, month, last_day).isoformat()
    else:
        last_day = calendar.monthrange(now_myt.year, now_myt.month)[1]
        due_date = date(now_myt.year, now_myt.month, last_day).isoformat()
    expected_date = payment_date.isoformat()

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
            logger.info(f"Swipey raw response for {invoice_number}: {result}")
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

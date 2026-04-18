"""
EMVCo DuitNow QR Parser
Extracts acquirer ID and account number from DuitNow QR images.

Known acquirer IDs:
  890053 = Touch 'n Go (TNG)
  588734 = Maybank / MAE
  501664 = Affin Bank
  Add more as validated with real QR samples.
"""

import io
import numpy as np
from PIL import Image
import cv2
from typing import Optional

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    _PYZBAR_AVAILABLE = True
except Exception:
    _PYZBAR_AVAILABLE = False

BANK_CODE_MAP = {
    # Source: PayNet DuitNow QR acquirer ID registry
    "629295": "AEON BANK",
    "501664": "AFFIN BANK",
    "432134": "AL RAJHI BANK",
    "504374": "ALLIANCE BANK",
    "564169": "AMBANK",
    "890293": "AMPERSAND PAY",
    "890061": "AXIATA DIGITAL ECODE",
    "603346": "BANK ISLAM",
    "589267": "BANK RAKYAT",
    "564167": "BANK MUAMALAT",
    "629188": "BANK OF AMERICA",
    "629152": "BANK OF CHINA",
    "589373": "AGROBANK",
    "420709": "BANK SIMPANAN NASIONAL",
    "890236": "BEEZ FINTECH",
    "890012": "BIGPAY",
    "629204": "BNP PARIBAS",
    "629303": "BOOST BANK",
    "890244": "BOOST CONNECT",
    "629261": "CHINA CONSTRUCTION BANK",
    "501854": "CIMB BANK",
    "589170": "CITIBANK",
    "890160": "CURLEC",
    "629246": "DEUTSCHE BANK",
    "890145": "FASS PAYMENT SOLUTIONS",
    "890020": "FAVE",
    "890038": "FINEXUS CARDS",
    "890103": "GHL CARDPAY",
    "890186": "GLOBAL PAYMENTS",
    "890046": "GPAY NETWORK",
    "629279": "GX BANK",
    "588830": "HONG LEONG BANK",
    "589836": "HSBC BANK",
    "629253": "ICBC",
    "890178": "INSTAPAY",
    "890079": "IPAY88",
    "629212": "JP MORGAN",
    "629311": "KAF INVESTMENT BANK",
    "890152": "KIPLEPAY",
    "890228": "KOPERASI CO-OPBANK",
    "639406": "KUWAIT FINANCE HOUSE",
    "588734": "MAYBANK",
    "890301": "MANAGEPAY",
    "432310": "MBSB BANK",
    "890111": "MERCHANTRADE ASIA",
    "629220": "MIZUHO BANK",
    "890210": "MOBILITYONE",
    "890277": "MOBIEDGE",
    "890327": "MRUNCIT",
    "629196": "MUFG BANK",
    "504324": "OCBC BANK",
    "890269": "PAYDIBS",
    "890194": "PAYEX",
    "564162": "PUBLIC BANK",
    "890087": "RAZER PAY",
    "890095": "REVENUE SOLUTION",
    "564160": "RHB BANK",
    "890129": "SETEL",
    "890004": "SHOPEE PAY",
    "890202": "SILICONNET",
    "539981": "STANDARD CHARTERED",
    "890137": "STRIPE",
    "629238": "SUMITOMO MITSUI BANK",
    "890053": "TOUCH AND GO DIGITAL",
    "890251": "UNIPIN",
    "519469": "UNITED OVERSEAS BANK",
    "890319": "WANNAPAY",
    "629287": "YTL DIGITAL BANK",
    "890285": "2C2P",
    "898989": "JOMPAY",
    "000000": "DuitNow",  # generic fallback
}


def _parse_emvco(raw: str) -> dict:
    """
    Parse EMVCo TLV string into tag/value dict.
    Returns flat dict of top-level tags and nested sub-tags for tag 26.
    """
    pos = 0
    tags = {}
    while pos < len(raw) - 3:
        tag = raw[pos:pos+2]
        try:
            length = int(raw[pos+2:pos+4])
        except ValueError:
            break
        value = raw[pos+4:pos+4+length]
        tags[tag] = value
        pos += 4 + length

    # Parse sub-tags inside tag 26 (merchant account info - DuitNow)
    sub_tags = {}
    if "26" in tags:
        sub_raw = tags["26"]
        sub_pos = 0
        while sub_pos < len(sub_raw) - 3:
            sub_tag = sub_raw[sub_pos:sub_pos+2]
            try:
                sub_len = int(sub_raw[sub_pos+2:sub_pos+4])
            except ValueError:
                break
            sub_val = sub_raw[sub_pos+4:sub_pos+4+sub_len]
            sub_tags[sub_tag] = sub_val
            sub_pos += 4 + sub_len

    return {"tags": tags, "sub_tags": sub_tags}


def _decode_image(image_bytes: bytes) -> Optional[str]:
    """Try pyzbar first, fallback to OpenCV QR detector."""
    # Attempt 1: pyzbar on PIL image
    if _PYZBAR_AVAILABLE:
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            results = pyzbar_decode(img)
            if results:
                return results[0].data.decode("utf-8")
        except Exception:
            pass

    # Attempt 2: OpenCV
    try:
        arr = np.frombuffer(image_bytes, np.uint8)
        cv_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(cv_img)
        if data:
            return data
    except Exception:
        pass

    # Attempt 3: OpenCV with preprocessing (grayscale + threshold)
    try:
        arr = np.frombuffer(image_bytes, np.uint8)
        cv_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(thresh)
        if data:
            return data
    except Exception:
        pass

    return None


def parse_qr_image(image_bytes: bytes) -> dict:
    """
    Main entry point. Accepts raw image bytes.
    Returns parsed payment info or raises ValueError.
    """
    raw = _decode_image(image_bytes)
    if not raw:
        raise ValueError("Could not decode QR code from image. Ensure the image is clear and contains a valid DuitNow QR.")

    parsed = _parse_emvco(raw)
    sub_tags = parsed["sub_tags"]
    tags = parsed["tags"]

    acquirer_id = sub_tags.get("01", "")
    account_number = sub_tags.get("02", "")

    if not account_number:
        raise ValueError("Could not extract account number from QR. This may not be a DuitNow QR code.")

    bank_name = BANK_CODE_MAP.get(acquirer_id, f"Unknown ({acquirer_id})" if acquirer_id else "Unknown")

    # Payee name is in tag 59
    payee_name = tags.get("59", "")

    # Detect proxy payment IDs — not usable as bank account numbers for bill payment.
    # Known proxy types: MAEPP* (Maybank MAE), PF* (HLB PayFlex), phone/IC numbers.
    # Real bank account numbers are always purely numeric.
    is_proxy_id = not account_number.isdigit()

    return {
        "raw_qr": raw,
        "acquirer_id": acquirer_id,
        "account_number": account_number if not is_proxy_id else "",
        "bank_name": bank_name,
        "payee_name": payee_name,
        "is_duitnow": "26" in tags,
        "is_proxy_id": is_proxy_id,
    }

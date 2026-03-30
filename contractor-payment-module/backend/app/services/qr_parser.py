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
    "890053": "Touch and Go Digital",
    "588734": "MAYBANK",
    "501664": "AFFIN BANK",
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

    return {
        "raw_qr": raw,
        "acquirer_id": acquirer_id,
        "account_number": account_number,
        "bank_name": bank_name,
        "payee_name": payee_name,
        "is_duitnow": "26" in tags,
    }

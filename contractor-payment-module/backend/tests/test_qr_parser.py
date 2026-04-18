"""
Tests for EMVCo DuitNow QR parser.
Tests _parse_emvco (pure logic) and parse_qr_image (with mocked image decode).
"""
import pytest
from unittest.mock import patch
from app.services.qr_parser import _parse_emvco, parse_qr_image, BANK_CODE_MAP


def build_emvco(acquirer_id: str, account_number: str, payee_name: str = "") -> str:
    """Build a minimal valid EMVCo TLV string for testing."""
    sub = f"01{len(acquirer_id):02d}{acquirer_id}02{len(account_number):02d}{account_number}"
    raw = f"26{len(sub):02d}{sub}"
    if payee_name:
        raw += f"59{len(payee_name):02d}{payee_name}"
    return raw


class TestParseEmvco:
    def test_extracts_tng_acquirer_and_account(self):
        raw = build_emvco("890053", "601234567890", "Ahmad Salleh")
        result = _parse_emvco(raw)
        assert result["sub_tags"]["01"] == "890053"
        assert result["sub_tags"]["02"] == "601234567890"

    def test_extracts_maybank_acquirer(self):
        raw = build_emvco("588734", "5128000112345")
        result = _parse_emvco(raw)
        assert result["sub_tags"]["01"] == "588734"
        assert result["sub_tags"]["02"] == "5128000112345"

    def test_extracts_payee_name_from_tag_59(self):
        raw = build_emvco("890053", "601111222333", "Test Payee")
        result = _parse_emvco(raw)
        assert result["tags"]["59"] == "Test Payee"

    def test_unknown_tag_does_not_crash(self):
        # Tag 26 plus a garbage tag at the end
        sub = "01068900530212601234567890"
        raw = f"26{len(sub):02d}{sub}99ZZ"
        result = _parse_emvco(raw)
        assert result["sub_tags"]["02"] == "601234567890"

    def test_empty_string_returns_empty_dicts(self):
        result = _parse_emvco("")
        assert result["tags"] == {}
        assert result["sub_tags"] == {}


class TestParseQrImage:
    def _mock_decode(self, raw_string):
        return patch("app.services.qr_parser._decode_image", return_value=raw_string)

    def test_tng_qr_returns_correct_bank(self):
        raw = build_emvco("890053", "601234567890", "Siti Rahimah")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake-image-bytes")
        assert result["bank_name"] == "TOUCH AND GO DIGITAL"
        assert result["acquirer_id"] == "890053"
        assert result["account_number"] == "601234567890"
        assert result["payee_name"] == "Siti Rahimah"
        assert result["is_duitnow"] is True

    def test_maybank_qr_returns_correct_bank(self):
        raw = build_emvco("588734", "5128001234567")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake")
        assert result["bank_name"] == "MAYBANK"

    def test_affin_qr_returns_correct_bank(self):
        raw = build_emvco("501664", "05123456789")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake")
        assert result["bank_name"] == "AFFIN BANK"

    def test_unknown_acquirer_returns_unknown_label(self):
        raw = build_emvco("999999", "601234567890")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake")
        assert "Unknown" in result["bank_name"]
        assert "999999" in result["bank_name"]

    def test_raises_if_no_account_number(self):
        # Tag 26 exists but sub-tag 02 is missing
        sub = "010689005"  # only sub-tag 01, malformed
        raw = f"26{len(sub):02d}{sub}"
        with self._mock_decode(raw):
            with pytest.raises(ValueError, match="account number"):
                parse_qr_image(b"fake")

    def test_raises_if_image_not_decodable(self):
        with self._mock_decode(None):
            with pytest.raises(ValueError, match="Could not decode"):
                parse_qr_image(b"not-a-qr")

    def test_bank_code_map_covers_known_acquirers(self):
        for code in ("890053", "588734", "501664"):
            assert code in BANK_CODE_MAP

    # ── Proxy ID detection ────────────────────────────────────────────────────

    def test_maybank_mae_proxy_sets_is_proxy_id_true(self):
        """MAEPP* accounts are proxy IDs — not usable for bill payment."""
        raw = build_emvco("588734", "MAEPP111205463572713", "Kalyana Mohana")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake")
        assert result["is_proxy_id"] is True

    def test_hlb_proxy_sets_is_proxy_id_true(self):
        """PF* accounts are HLB PayFlex proxy IDs."""
        raw = build_emvco("588830", "PF250615213834317429", "Ahmad Salleh")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake")
        assert result["is_proxy_id"] is True

    def test_proxy_clears_account_number_in_result(self):
        """account_number must be empty string for proxy QRs — not the proxy value."""
        raw = build_emvco("588734", "MAEPP111205463572713", "Test User")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake")
        assert result["account_number"] == ""

    def test_proxy_still_returns_bank_name_and_payee(self):
        """Even proxy QRs should return bank_name and payee_name for pre-filling the manual form."""
        raw = build_emvco("588830", "PF250615213834317429", "Ahmad Salleh")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake")
        assert result["bank_name"] == "HONG LEONG BANK"
        assert result["payee_name"] == "Ahmad Salleh"
        assert result["acquirer_id"] == "588830"

    def test_numeric_account_sets_is_proxy_id_false(self):
        """Standard numeric account numbers must not be flagged as proxy."""
        raw = build_emvco("890053", "601234567890", "Siti Rahimah")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake")
        assert result["is_proxy_id"] is False
        assert result["account_number"] == "601234567890"

    def test_alphanumeric_non_proxy_still_flagged(self):
        """Any non-numeric account number is treated as a proxy regardless of prefix."""
        raw = build_emvco("501854", "CIMB-VIRTUAL-001", "Test")
        with self._mock_decode(raw):
            result = parse_qr_image(b"fake")
        assert result["is_proxy_id"] is True

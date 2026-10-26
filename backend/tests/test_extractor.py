"""Tests for the tracking ID and phone-last-4 extractors.

All inputs use ``digit_text`` (number words already converted to digits
by the normalizer).

Covers:
- Happy: standard formats, phonetic prefixes, space-separated digits.
- Negative: 7-digit, 9-digit, no prefix, lowercase/uppercase.
- Multiple IDs: 2 valid IDs in one sentence → list of 2.
- Phone last 4: extracted correctly; exclude_digits prevents overlap;
  ambiguous (2 groups) → None.
- Parametrized: 15+ tracking ID phrasings.
"""

from __future__ import annotations

import pytest

from app.brain.extractor import extract_phone_last4, extract_tracking_ids

# ── Tracking ID — happy path ─────────────────────────────────────────


class TestTrackingIdHappy:
    def test_rd_contiguous(self):
        assert extract_tracking_ids("rd12345678") == ["RD12345678"]

    def test_rd_uppercase(self):
        assert extract_tracking_ids("RD12345678") == ["RD12345678"]

    def test_rd_space_separated_digits(self):
        result = extract_tracking_ids("rd 1 2 3 4 5 6 7 8")
        assert result == ["RD12345678"]

    def test_r_d_prefix(self):
        result = extract_tracking_ids("r d 1 2 3 4 5 6 7 8")
        assert result == ["RD12345678"]

    def test_are_dee_prefix(self):
        result = extract_tracking_ids("are dee 12345678")
        assert result == ["RD12345678"]

    def test_are_dee_space_separated(self):
        result = extract_tracking_ids("are dee 1 2 3 4 5 6 7 8")
        assert result == ["RD12345678"]

    def test_our_d_prefix(self):
        result = extract_tracking_ids("our d 12345678")
        assert result == ["RD12345678"]

    def test_our_d_space_separated(self):
        result = extract_tracking_ids("our d 1 2 3 4 5 6 7 8")
        assert result == ["RD12345678"]

    def test_ardie_prefix(self):
        result = extract_tracking_ids("ardie 12345678")
        assert result == ["RD12345678"]

    def test_ardie_space_separated(self):
        result = extract_tracking_ids("ardie 1 2 3 4 5 6 7 8")
        assert result == ["RD12345678"]

    def test_in_sentence(self):
        result = extract_tracking_ids("my tracking id is rd30000001 please")
        assert result == ["RD30000001"]

    def test_mixed_spacing(self):
        """Some digits grouped, some separated."""
        result = extract_tracking_ids("rd 12 34 56 78")
        assert result == ["RD12345678"]

    def test_partial_spacing(self):
        result = extract_tracking_ids("rd1234 5678")
        assert result == ["RD12345678"]


# ── Tracking ID — negative cases ─────────────────────────────────────


class TestTrackingIdNegative:
    def test_seven_digits(self):
        """Only 7 digits after prefix — should not match."""
        assert extract_tracking_ids("rd1234567") == []

    def test_nine_digits_extracts_first_eight(self):
        """9 digits: regex captures the first 8, last digit is leftover."""
        result = extract_tracking_ids("rd123456789")
        # The regex will capture the first 8 digits.
        assert result == ["RD12345678"]

    def test_no_prefix(self):
        """Plain 8 digits without RD prefix — no match."""
        assert extract_tracking_ids("12345678") == []

    def test_wrong_prefix(self):
        assert extract_tracking_ids("AB12345678") == []

    def test_empty_string(self):
        assert extract_tracking_ids("") == []

    def test_just_prefix(self):
        assert extract_tracking_ids("rd") == []

    def test_prefix_with_letters(self):
        assert extract_tracking_ids("rd abcd efgh") == []


# ── Tracking ID — multiple IDs ───────────────────────────────────────


class TestTrackingIdMultiple:
    def test_two_ids_in_one_sentence(self):
        text = "is it rd10000001 or rd30000002"
        result = extract_tracking_ids(text)
        assert result == ["RD10000001", "RD30000002"]

    def test_two_ids_different_prefixes(self):
        text = "rd10000001 and are dee 3 0 0 0 0 0 0 2"
        result = extract_tracking_ids(text)
        assert result == ["RD10000001", "RD30000002"]

    def test_three_ids(self):
        text = "rd11111111 rd22222222 rd33333333"
        result = extract_tracking_ids(text)
        assert len(result) == 3


# ── Tracking ID — parametrized ────────────────────────────────────────


@pytest.mark.parametrize(
    "digit_text, expected",
    [
        ("rd12345678", ["RD12345678"]),
        ("RD12345678", ["RD12345678"]),
        ("rd 1 2 3 4 5 6 7 8", ["RD12345678"]),
        ("r d 12345678", ["RD12345678"]),
        ("r d 1 2 3 4 5 6 7 8", ["RD12345678"]),
        ("are dee 12345678", ["RD12345678"]),
        ("are dee 1 2 3 4 5 6 7 8", ["RD12345678"]),
        ("our d 12345678", ["RD12345678"]),
        ("our d 1 2 3 4 5 6 7 8", ["RD12345678"]),
        ("ardie 12345678", ["RD12345678"]),
        ("ardie 1 2 3 4 5 6 7 8", ["RD12345678"]),
        ("my id is rd30000001", ["RD30000001"]),
        ("it's are dee 99887766", ["RD99887766"]),
        ("our d 1 1 2 2 3 3 4 4", ["RD11223344"]),
        ("rd10000001 or rd20000002", ["RD10000001", "RD20000002"]),
        ("no valid id here", []),
        ("rd1234567", []),  # 7 digits
        ("", []),
    ],
    ids=[
        "rd_contiguous",
        "rd_uppercase",
        "rd_spaced_digits",
        "r_d_contiguous",
        "r_d_spaced_digits",
        "are_dee_contiguous",
        "are_dee_spaced",
        "our_d_contiguous",
        "our_d_spaced",
        "ardie_contiguous",
        "ardie_spaced",
        "in_sentence",
        "phonetic_are_dee",
        "phonetic_our_d",
        "two_ids",
        "no_match",
        "seven_digits",
        "empty",
    ],
)
def test_extract_tracking_ids_parametrized(
    digit_text: str, expected: list[str]
):
    assert extract_tracking_ids(digit_text) == expected


# ── Phone last 4 — happy path ────────────────────────────────────────


class TestPhoneLast4Happy:
    def test_simple_4_digits(self):
        assert extract_phone_last4("my last 4 are 1234") == "1234"

    def test_4_digits_alone(self):
        assert extract_phone_last4("5678") == "5678"

    def test_with_surrounding_text(self):
        assert extract_phone_last4("the digits are 9012 thanks") == "9012"


# ── Phone last 4 — exclude_digits ────────────────────────────────────


class TestPhoneLast4Exclude:
    def test_exclude_overlapping_tracking_digits(self):
        """4-digit group that's a substring of the tracking ID's digits
        should be excluded."""
        # digit_text has tracking ID "rd12345678" and phone "9012".
        text = "rd12345678 and 9012"
        result = extract_phone_last4(text, exclude_digits="12345678")
        assert result == "9012"

    def test_all_4_digit_groups_excluded(self):
        """When the only 4-digit group is a substring of the tracking digits,
        return None."""
        text = "rd12345678 and 3456"
        result = extract_phone_last4(text, exclude_digits="12345678")
        assert result is None  # 3456 is a substring of 12345678

    def test_exclude_digits_with_spaces(self):
        """exclude_digits may contain spaces; they should be stripped."""
        text = "rd12345678 and 9012"
        result = extract_phone_last4(text, exclude_digits="1 2 3 4 5 6 7 8")
        assert result == "9012"

    def test_4_digits_inside_tracking_id_overlap(self):
        """A 4-digit group that falls within the tracking ID span in the
        text should be excluded via span overlap."""
        # The digits "3456" appear within "rd12345678"
        text = "rd12345678"
        result = extract_phone_last4(text)
        assert result is None  # all 4-digit groups overlap with tracking span


# ── Phone last 4 — ambiguous ─────────────────────────────────────────


class TestPhoneLast4Ambiguous:
    def test_two_groups_returns_none(self):
        """Two non-overlapping 4-digit groups → ambiguous → None."""
        assert extract_phone_last4("1234 and 5678") is None

    def test_three_groups_returns_none(self):
        assert extract_phone_last4("1234 5678 9012") is None


# ── Phone last 4 — negative ──────────────────────────────────────────


class TestPhoneLast4Negative:
    def test_no_digits(self):
        assert extract_phone_last4("no digits here") is None

    def test_three_digits(self):
        assert extract_phone_last4("only 123 here") is None

    def test_five_digits(self):
        """5 consecutive digits don't form a 4-digit word boundary match."""
        assert extract_phone_last4("12345") is None

    def test_empty_string(self):
        assert extract_phone_last4("") is None

    def test_none_exclude(self):
        """exclude_digits=None should work fine."""
        assert extract_phone_last4("1234", exclude_digits=None) == "1234"


# ── Combined extraction scenario ─────────────────────────────────────


class TestCombinedExtraction:
    """Simulate what the slot filler does: extract tracking ID first,
    then use its trailing 8 digits as exclude_digits for phone extraction."""

    def test_full_turn_with_id_and_phone(self):
        text = "rd30000001 and my phone ends in 1234"
        ids = extract_tracking_ids(text)
        assert ids == ["RD30000001"]

        # Trailing 8 digits of the tracking ID.
        exclude = ids[0][2:]  # "30000001"
        phone = extract_phone_last4(text, exclude_digits=exclude)
        assert phone == "1234"

    def test_full_turn_phone_overlaps_with_id(self):
        """Phone digits happen to be a substring of the tracking ID digits."""
        text = "rd12345678 and 2345"
        ids = extract_tracking_ids(text)
        assert ids == ["RD12345678"]

        exclude = ids[0][2:]  # "12345678"
        phone = extract_phone_last4(text, exclude_digits=exclude)
        # "2345" is a substring of "12345678" → excluded → None
        assert phone is None

    def test_no_tracking_id_phone_still_extracted(self):
        text = "my phone ends in 5678"
        ids = extract_tracking_ids(text)
        assert ids == []
        phone = extract_phone_last4(text)
        assert phone == "5678"

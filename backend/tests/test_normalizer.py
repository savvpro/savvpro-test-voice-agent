"""Tests for the two-pass text normalizer.

Covers:
- Happy: lowercases, strips fillers, "uh" removed, "um" removed.
- intent_text: "oh no" preserved, "one moment" preserved.
- digit_text: "oh" → "0" in digit context, "double five" → "55",
  "triple nine" → "999".
- Negative: already-digit strings unchanged; unknown words unchanged.
- Boundary: empty string, 2000-char, 2001-char truncated.
- Injection: <script>, SQL '; DROP TABLE, " — no crash, safe output.
- "like" is NOT stripped (preserved for "I'd like to…").
- Parametrized: 20+ phrase → expected intent_text and digit_text pairs.
"""

from __future__ import annotations

import pytest

from app.brain.normalizer import NormalizeResult, normalize

# ── Happy path ────────────────────────────────────────────────────────


class TestBasicNormalization:
    """Core preprocessing: lowercase, filler removal, whitespace collapse."""

    def test_lowercase(self):
        r = normalize("HELLO World")
        assert r.intent_text == "hello world"

    def test_strip_whitespace(self):
        r = normalize("  hello  world  ")
        assert r.intent_text == "hello world"

    def test_strip_filler_uh(self):
        r = normalize("uh I need to reschedule")
        assert "uh" not in r.intent_text

    def test_strip_filler_um(self):
        r = normalize("um can you help me um please")
        assert "um" not in r.intent_text
        assert "can you help me please" == r.intent_text

    def test_strip_filler_er(self):
        r = normalize("er I er want to er cancel")
        assert r.intent_text == "i want to cancel"

    def test_strip_multi_word_filler(self):
        r = normalize("you know I sort of need help")
        assert r.intent_text == "i need help"

    def test_like_preserved(self):
        """'like' is NOT a filler word — it must survive."""
        r = normalize("I'd like to reschedule please")
        assert "like" in r.intent_text

    def test_basically_stripped(self):
        r = normalize("basically I need to reschedule")
        assert "basically" not in r.intent_text


# ── Intent text preserves number words ────────────────────────────────


class TestIntentTextPreservation:
    """intent_text must NOT convert number words to digits."""

    def test_oh_no_preserved(self):
        r = normalize("oh no")
        assert r.intent_text == "oh no"

    def test_one_moment_preserved(self):
        r = normalize("one moment please")
        assert r.intent_text == "one moment please"

    def test_zero_preserved(self):
        r = normalize("zero chance of that")
        assert r.intent_text == "zero chance of that"

    def test_five_minutes_preserved(self):
        r = normalize("give me five minutes")
        assert r.intent_text == "give me five minutes"

    def test_two_ids_preserved(self):
        r = normalize("I have two tracking IDs")
        assert r.intent_text == "i have two tracking ids"


# ── Digit text conversions ────────────────────────────────────────────


class TestDigitTextConversions:
    """digit_text must convert number words to digit strings."""

    def test_double_five(self):
        r = normalize("double five")
        assert r.digit_text == "55"

    def test_triple_nine(self):
        r = normalize("triple nine")
        assert r.digit_text == "999"

    def test_double_zero(self):
        r = normalize("double zero")
        assert r.digit_text == "00"

    def test_triple_one(self):
        r = normalize("triple one")
        assert r.digit_text == "111"

    def test_double_raw_digit(self):
        r = normalize("double 7")
        assert r.digit_text == "77"

    def test_oh_between_digits(self):
        r = normalize("1 oh 2")
        assert "0" in r.digit_text
        assert "oh" not in r.digit_text

    def test_oh_after_digit(self):
        r = normalize("5 oh")
        assert r.digit_text == "50"

    def test_oh_before_digit(self):
        r = normalize("oh 3")
        assert r.digit_text == "03"

    def test_number_words_to_digits(self):
        r = normalize("one two three four five")
        assert r.digit_text == "1 2 3 4 5"

    def test_six_seven_eight_nine(self):
        r = normalize("six seven eight nine")
        assert r.digit_text == "6 7 8 9"

    def test_zero_word(self):
        r = normalize("zero one two")
        assert r.digit_text == "0 1 2"

    def test_ten(self):
        r = normalize("ten")
        assert r.digit_text == "10"

    def test_eleven_twelve(self):
        r = normalize("eleven twelve")
        assert r.digit_text == "11 12"

    def test_teens(self):
        r = normalize("thirteen fourteen fifteen")
        assert r.digit_text == "13 14 15"

    def test_twenty_one(self):
        r = normalize("twenty one")
        assert r.digit_text == "21"

    def test_thirty(self):
        r = normalize("thirty")
        assert r.digit_text == "30"

    def test_already_digit_unchanged(self):
        r = normalize("12345678")
        assert r.digit_text == "12345678"

    def test_mixed_words_and_digits(self):
        r = normalize("RD one two 3 4 five six 7 8")
        assert r.digit_text == "rd 1 2 3 4 5 6 7 8"

    def test_unknown_words_unchanged(self):
        r = normalize("reschedule delivery tomorrow")
        assert r.digit_text == "reschedule delivery tomorrow"


# ── Boundary conditions ──────────────────────────────────────────────


class TestBoundaryConditions:
    def test_empty_string(self):
        r = normalize("")
        assert r.intent_text == ""
        assert r.digit_text == ""

    def test_whitespace_only(self):
        r = normalize("   ")
        assert r.intent_text == ""
        assert r.digit_text == ""

    def test_max_length_preserved(self):
        text = "a" * 2000
        r = normalize(text)
        assert len(r.intent_text) == 2000

    def test_over_max_length_truncated(self):
        text = "b" * 2001
        r = normalize(text)
        assert len(r.intent_text) == 2000

    def test_2001_chars_truncated_correctly(self):
        """Verify that content beyond 2000 chars is dropped."""
        text = "x" * 2000 + "MARKER"
        r = normalize(text)
        assert "marker" not in r.intent_text


# ── Injection protection ─────────────────────────────────────────────


class TestInjectionProtection:
    def test_html_script_tag(self):
        """Angle brackets are printable ASCII; normalizer keeps them as
        harmless plain text.  The key safety property is that the output
        is pure ASCII and lowercased — no executable context exists."""
        r = normalize("<script>alert('xss')</script>")
        assert r.intent_text.isascii()
        assert r.intent_text == "<script>alert('xss')</script>"

    def test_sql_injection(self):
        r = normalize("'; DROP TABLE parcels; --")
        assert r.intent_text.isascii()
        # Should not crash; content is safe text.
        assert "drop" in r.intent_text  # lowercased, but harmless text

    def test_double_quotes(self):
        r = normalize('He said "hello"')
        assert r.intent_text.isascii()

    def test_unicode_stripped(self):
        r = normalize("café résumé naïve")
        # Non-ASCII stripped; 'caf', 'rsum', 'nave' remain.
        assert r.intent_text.isascii()

    def test_null_bytes(self):
        r = normalize("hello\x00world")
        assert "\x00" not in r.intent_text

    def test_newlines_and_tabs(self):
        r = normalize("hello\nworld\tthere")
        # Newlines and tabs are outside printable space (0x20-0x7E)
        # except tab 0x09 and newline 0x0A which are < 0x20
        assert "\n" not in r.intent_text
        assert "\t" not in r.intent_text


# ── Parametrized phrase tests ─────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected_intent, expected_digit",
    [
        # Basic phrases
        ("Hello there", "hello there", "hello there"),
        ("UH reschedule PLEASE", "reschedule please", "reschedule please"),
        # Number preservation in intent vs conversion in digit
        ("oh no I lost it", "oh no i lost it", "oh no i lost it"),
        ("one more thing", "one more thing", "1 more thing"),
        # Tracking ID style
        (
            "RD one two three four five six seven eight",
            "rd one two three four five six seven eight",
            "rd 1 2 3 4 5 6 7 8",
        ),
        (
            "are dee double five triple nine one two",
            "are dee double five triple nine one two",
            "are dee 55 999 1 2",
        ),
        # Phone digits
        ("one two three four", "one two three four", "1 2 3 4"),
        ("double oh seven nine", "double oh seven nine", "00 7 9"),
        # Fillers in context
        (
            "uh I um want to er reschedule",
            "i want to reschedule",
            "i want to reschedule",
        ),
        # Mixed fillers and numbers
        (
            "um five uh six er seven",
            "five six seven",
            "5 6 7",
        ),
        # "like" preserved
        (
            "I'd like to cancel please",
            "i'd like to cancel please",
            "i'd like to cancel please",
        ),
        # Date phrases (no number conversion in intent)
        (
            "tomorrow morning please",
            "tomorrow morning please",
            "tomorrow morning please",
        ),
        # Edge: all fillers
        ("uh um er", "", ""),
        # Edge: just a number
        ("five", "five", "5"),
        # Double/triple edge
        ("double double five", "double double five", "double 55"),
        # Twenty compounds
        ("twenty six", "twenty six", "26"),
        ("twenty nine", "twenty nine", "29"),
        # Already digits
        ("1234", "1234", "1234"),
        # Punctuation preserved
        ("hello, world!", "hello, world!", "hello, world!"),
    ],
    ids=[
        "basic_hello",
        "filler_reschedule",
        "oh_no_preserved",
        "one_more_thing",
        "tracking_id_words",
        "tracking_phonetic_doubles",
        "phone_digits",
        "double_oh_seven",
        "fillers_in_context",
        "mixed_fillers_numbers",
        "like_preserved",
        "date_phrase",
        "all_fillers",
        "just_five",
        "double_double",
        "twenty_six",
        "twenty_nine",
        "already_digits",
        "punctuation_preserved",
    ],
)
def test_normalize_parametrized(
    raw: str, expected_intent: str, expected_digit: str
):
    r = normalize(raw)
    assert r.intent_text == expected_intent, (
        f"intent_text mismatch for {raw!r}"
    )
    assert r.digit_text == expected_digit, (
        f"digit_text mismatch for {raw!r}"
    )


# ── Return type ───────────────────────────────────────────────────────


class TestReturnType:
    def test_returns_normalize_result(self):
        r = normalize("hello")
        assert isinstance(r, NormalizeResult)

    def test_result_is_frozen(self):
        r = normalize("hello")
        with pytest.raises(AttributeError):
            r.intent_text = "modified"  # type: ignore[misc]

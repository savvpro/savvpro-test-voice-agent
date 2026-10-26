"""Two-pass text normalizer for the REDELIVER voice assistant.

Produces two distinct outputs from one raw input:

* ``intent_text`` — safe for intent detection; number words **preserved**
  so phrases like "oh no" and "one moment" are not corrupted.
* ``digit_text`` — number words converted to digits; used by the extractor
  and date parser.

Neither output ever calls ``datetime.now()`` or reads the system clock.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass

from app.brain.constants import (
    _WORD_TO_SINGLE_DIGIT,
    DOUBLE_TRIPLE_PATTERN,
    FILLER_WORDS,
    MAX_INPUT_LENGTH,
    NUMBER_WORD_MAP,
    OH_DIGIT_CONTEXT,
)


@dataclass(frozen=True, slots=True)
class NormalizeResult:
    """Output of :func:`normalize`."""

    intent_text: str
    digit_text: str


# ── Printable-ASCII allowlist ─────────────────────────────────────────
#
# Keep letters, digits, basic punctuation, and whitespace.  This blocks
# injection characters without needing a deny-list.

_ALLOWED_CHARS = frozenset(
    string.ascii_letters
    + string.digits
    + " "
    + string.punctuation
)

_UNSAFE_RE = re.compile(r"[^\x20-\x7E]")  # anything outside printable ASCII


def _strip_unsafe(text: str) -> str:
    """Remove characters outside printable ASCII."""
    return _UNSAFE_RE.sub("", text)


# ── Filler removal ───────────────────────────────────────────────────

def _build_filler_pattern() -> re.Pattern[str]:
    """Compile a single regex that matches any filler phrase (whole-word)."""
    # Sort longest-first so multi-word fillers are matched before their
    # single-word substrings.
    sorted_fillers = sorted(FILLER_WORDS, key=len, reverse=True)
    escaped = [re.escape(f) for f in sorted_fillers]
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


_FILLER_RE = _build_filler_pattern()
_MULTI_SPACE = re.compile(r"\s+")


def _common_preprocess(raw: str) -> str:
    """Steps shared by both intent_text and digit_text.

    1. Lowercase + strip.
    2. Remove non-printable characters.
    3. Truncate to MAX_INPUT_LENGTH.
    4. Strip filler words (whole-word).
    5. Collapse whitespace.
    """
    text = raw.lower().strip()
    text = _strip_unsafe(text)
    text = text[:MAX_INPUT_LENGTH]
    text = _FILLER_RE.sub(" ", text)
    text = _MULTI_SPACE.sub(" ", text).strip()
    return text


# ── Digit pass ────────────────────────────────────────────────────────

def _replace_double_triple(match: re.Match[str]) -> str:
    """Replace 'double five' → '55', 'triple nine' → '999'."""
    multiplier = match.group(1).lower()
    digit_word = match.group(2).lower()
    # May be a raw digit character ("5") or a word ("five").
    digit = _WORD_TO_SINGLE_DIGIT.get(digit_word, digit_word)
    repeat = 2 if multiplier == "double" else 3
    return digit * repeat


def _convert_oh_to_zero(text: str) -> str:
    """Convert 'oh' to '0' when it appears next to digits.

    Only converts when 'oh' is adjacent to an actual digit character,
    so 'oh no' in digit_text is handled correctly — after number-word
    conversion there may or may not be adjacent digits.
    """
    return OH_DIGIT_CONTEXT.sub("0", text)


def _convert_number_words(text: str) -> str:
    """Convert number words to digit strings.

    Processes longest phrases first to avoid partial substitution.
    """
    for word, digit in NUMBER_WORD_MAP:
        text = re.sub(r"\b" + re.escape(word) + r"\b", digit, text)
    return text


def _digit_pass(text: str) -> str:
    """Additional processing for digit_text.

    6. Convert 'double X' / 'triple X'.
    7. Convert 'oh' → '0' when next to digits.
    8. Convert remaining number words.
    9. Collapse whitespace again.
    """
    text = DOUBLE_TRIPLE_PATTERN.sub(_replace_double_triple, text)
    text = _convert_number_words(text)
    text = _convert_oh_to_zero(text)
    text = _MULTI_SPACE.sub(" ", text).strip()
    return text


# ── Public API ────────────────────────────────────────────────────────

def normalize(raw_text: str) -> NormalizeResult:
    """Normalize raw caller input into two representations.

    Args:
        raw_text: The raw transcription from STT.

    Returns:
        A ``NormalizeResult`` with ``intent_text`` (number words preserved)
        and ``digit_text`` (number words → digits).
    """
    common = _common_preprocess(raw_text)
    return NormalizeResult(
        intent_text=common,
        digit_text=_digit_pass(common),
    )

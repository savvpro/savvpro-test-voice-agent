"""Phone-number extraction, including numbers spoken as words ("double five")."""

from __future__ import annotations

import re
from dataclasses import dataclass

DIGIT_WORDS = {
    "zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}  # fmt: skip
MULTIPLIERS = {"double": 2, "triple": 3}
_TOKEN_RE = re.compile(r"[a-z]+|\d+|[^\sa-z\d]")


@dataclass(frozen=True)
class PhoneResult:
    digits: str | None  # normalised digits if anything phone-like was heard
    valid: bool  # True only for an 11-digit Pakistani mobile number (03XXXXXXXXX)
    remaining: str  # the text with the phone number removed (for date/time parsing)


def _read_run(tokens: list[str], i: int) -> tuple[str, int, bool]:
    """Read consecutive digit tokens starting at i -> (digits, next_index, used_words)."""
    digits, j, used_words = "", i, False
    while j < len(tokens):
        tok = tokens[j]
        if tok.isdigit():
            digits += tok
            j += 1
        elif tok in DIGIT_WORDS:
            digits += DIGIT_WORDS[tok]
            used_words = True
            j += 1
        elif tok in MULTIPLIERS and j + 1 < len(tokens) and tokens[j + 1] in DIGIT_WORDS:
            digits += DIGIT_WORDS[tokens[j + 1]] * MULTIPLIERS[tok]
            used_words = True
            j += 2
        elif (
            tok == "-"
            and digits
            and j + 1 < len(tokens)
            and (tokens[j + 1].isdigit() or tokens[j + 1] in DIGIT_WORDS or tokens[j + 1] in MULTIPLIERS)
        ):
            j += 1
        else:
            break
    return digits, j, used_words


def normalize_pk(digits: str) -> str:
    if digits.startswith("92") and len(digits) == 12:
        return "0" + digits[2:]
    if digits.startswith("3") and len(digits) == 10:
        return "0" + digits
    return digits


def is_valid_pk_mobile(digits: str) -> bool:
    return len(digits) == 11 and digits.startswith("03")


def extract_phone(text: str, expecting: bool = False) -> PhoneResult:
    low = text.lower()
    matches = list(_TOKEN_RE.finditer(low))
    tokens = [m.group() for m in matches]
    best: tuple[str, int, int, bool] | None = None
    i = 0
    while i < len(tokens):
        digits, j, used_words = _read_run(tokens, i)
        if j > i and digits:
            if best is None or len(digits) > len(best[0]):
                best = (digits, i, j, used_words)
            i = j
        else:
            i += 1
    if best is None:
        return PhoneResult(None, False, text)
    digits, i, j, used_words = best
    n = len(digits)
    qualifies = n >= 10 or (n >= 7 and (expecting or used_words)) or (expecting and n >= 4)
    if not qualifies:
        return PhoneResult(None, False, text)
    remaining = low[: matches[i].start()] + " " + low[matches[j - 1].end() :]
    digits = normalize_pk(digits)
    return PhoneResult(digits, is_valid_pk_mobile(digits), remaining)

"""Clean up speech-to-text output before it is understood.

Browsers' speech recognition returns lowercase words, spelled-out numbers,
fillers ("um", "uh"), and sometimes "for" or "to" where the caller said a
number. This module turns that into predictable text.
"""

import re

_FILLERS = re.compile(r"\b(um+|uh+|erm+|hmm+|you know|okay so|so yeah)\b", re.I)

UNITS = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "thirtieth": 30,
}


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def words_to_digits(text: str) -> str:
    """'two thirty' -> '2 30', 'twenty first' -> '21st', 'five five five' -> '5 5 5'."""
    tokens = text.split()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        word = tokens[i]
        if word in TENS:
            value = TENS[word]
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt in UNITS and 0 < UNITS[nxt] < 10:
                out.append(str(value + UNITS[nxt]))
                i += 2
                continue
            if nxt in ORDINALS and ORDINALS[nxt] < 10:
                out.append(_ordinal(value + ORDINALS[nxt]))
                i += 2
                continue
            out.append(str(value))
        elif word in UNITS:
            out.append(str(UNITS[word]))
        elif word in ORDINALS:
            out.append(_ordinal(ORDINALS[word]))
        else:
            out.append(word)
        i += 1
    return " ".join(out)


def normalize(text: str) -> str:
    s = text.lower().strip()
    s = s.replace("’", "'")
    s = re.sub(r"(\d)(am|pm)\b", r"\1 \2", s)
    s = re.sub(r"\b([ap])\.?\s?m\.?(?=\s|$)", r"\1m", s)  # "p.m." / "p m" -> "pm"
    s = _FILLERS.sub(" ", s)
    s = re.sub(r"[^\w\s:'/-]", " ", s)
    s = words_to_digits(" ".join(s.split()))
    # "3 30" (from "three thirty") -> "3:30" when it reads like a clock time.
    s = re.sub(r"\b(1[0-2]|[1-9]) (15|30|45|00)\b", r"\1:\2", s)
    return " ".join(s.split())

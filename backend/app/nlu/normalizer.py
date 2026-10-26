"""Turn a raw (often speech-to-text) transcript into a canonical form.

    "Umm, I'd like Tuesday at half past three P.M."
 -> "i'd like tuesday at 3:30 pm"

The same function is applied to training data, so the classifier and the
rules always see text in the same shape.
"""

import re
import unicodedata

from app.nlu.lexicon import load_lexicon

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}  # fmt: skip
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "thirtieth": 30,
}  # fmt: skip
MONTHS = {
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
    "sept", "oct", "nov", "dec",
}  # fmt: skip

# An ordinal word is only a date ("the fifth", "fifth of May") when it is not
# picking an option ("the first one", "the second slot", "just a second").
_ORDINAL_DATE_BEFORE = {"the", "on", "of"} | MONTHS
_ORDINAL_NOT_DATE_AFTER = {
    "one", "available", "slot", "slots", "appointment", "time", "thing", "option", "opening",
    "free", "doctor", "week", "floor", "visit", "choice",
}  # fmt: skip

# "N to H" is only a clock time for these N; "2 to 3" is a range.
_MINUTES_TO = {"5": 5, "10": 10, "20": 20, "25": 25, "quarter": 15}


def _ordinal_suffix(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _clean_characters(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\ba\.\s?m\b\.?", "am", text)
    text = re.sub(r"\bp\.\s?m\b\.?", "pm", text)
    text = re.sub(r"\b(\d{1,2})\s*(am|pm)\b", r"\1 \2", text)
    text = re.sub(r"\b([ap])\s+m\b", r"\1m", text)  # "3 p m"
    text = re.sub(r"\bo'?\s?clock\b", " oclock", text)
    text = re.sub(r"\b(\d{1,2})\.(\d{2})\b", r"\1:\2", text)  # 3.30 -> 3:30
    # Keep ' (i'm, don't), : (times), / (dates), + (phones); everything else is a separator.
    text = re.sub(r"[^a-z0-9:'/+\s]", " ", text)
    text = re.sub(r"(?<![a-z])'|'(?![a-z])", " ", text)
    return text


def _words_to_numbers(tokens: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        prev = out[-1] if out else ""

        digit = str(UNITS[nxt]) if nxt in UNITS else nxt
        if tok in ("double", "triple") and len(digit) == 1 and digit.isdigit():
            out.extend([digit] * (2 if tok == "double" else 3))
            i += 2
            continue

        if tok in TENS:
            value = TENS[tok]
            if nxt in UNITS and 0 < UNITS[nxt] < 10:
                out.append(str(value + UNITS[nxt]))
                i += 2
                continue
            if nxt in ORDINALS and ORDINALS[nxt] < 10:
                out.append(
                    _maybe_ordinal(value + ORDINALS[nxt], f"{tok} {nxt}", prev, tokens, i + 2)
                )
                i += 2
                continue
            out.append(str(value))
        elif tok in UNITS:
            out.append(str(UNITS[tok]))
        elif tok in ORDINALS:
            out.append(_maybe_ordinal(ORDINALS[tok], tok, prev, tokens, i + 1))
        else:
            out.append(tok)
        i += 1
    return out


def _maybe_ordinal(value: int, words: str, prev: str, tokens: list[str], next_index: int) -> str:
    after = tokens[next_index] if next_index < len(tokens) else ""
    is_date = (prev in _ORDINAL_DATE_BEFORE or after == "of") and after not in (
        _ORDINAL_NOT_DATE_AFTER
    )
    if not is_date:
        return words  # "the first one" stays an option choice, not a date
    return f"{value}{_ordinal_suffix(value)}"


def _join_spoken_digits(tokens: list[str]) -> list[str]:
    """'0 3 0 0 1 2 3 4 5 6 7' (a phone number read digit by digit) -> '03001234567'."""
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if len(run) >= 7 or (run and run[0] == "+" and len(run) >= 8):
            out.append("".join(run))
        else:
            out.extend(run)
        run.clear()

    for tok in tokens:
        if tok == "plus":
            tok = "+"
        if (len(tok) == 1 and tok.isdigit()) or (tok == "+" and not run):
            run.append(tok)
        else:
            flush()
            out.append(tok)
    flush()
    return out


def _clock_phrases(text: str) -> str:
    def hm(hour: int, minute: int) -> str:
        return f"{hour}:{minute:02d}"

    text = re.sub(r"\bhalf past (\d{1,2})\b", lambda m: hm(int(m[1]), 30), text)
    text = re.sub(r"\bquarter past (\d{1,2})\b", lambda m: hm(int(m[1]), 15), text)
    text = re.sub(
        r"\b(\d{1,2}) (?:minutes )?past (\d{1,2})\b",
        lambda m: hm(int(m[2]), int(m[1])) if int(m[1]) < 60 else m[0],
        text,
    )

    def minutes_to(m: re.Match) -> str:
        hour = int(m[3])
        if m[1] or not 1 <= hour <= 12:  # "from 10 to 12" is a range
            return m[0]
        prev_hour = 12 if hour == 1 else hour - 1
        return hm(prev_hour, 60 - _MINUTES_TO[m[2]])

    text = re.sub(
        r"\b(?:(from|between) )?(5|10|20|25|quarter) (?:minutes )?to (\d{1,2})\b(?!:)",
        minutes_to,
        text,
    )
    text = re.sub(r"\b(\d{1,2}) oclock\b", lambda m: hm(int(m[1]), 0), text)
    # "3 30", "10 45 am" -> "3:30", "10:45 am"
    text = re.sub(
        r"\b(\d{1,2}) ([0-5][05])\b(?![:/])",
        lambda m: hm(int(m[1]), int(m[2])) if 1 <= int(m[1]) <= 12 else m[0],
        text,
    )
    return text.replace(" oclock", "")


def _dedupe_words(tokens: list[str]) -> list[str]:
    """Drop stuttered repeats ("i i want"), but never repeated digits."""
    out: list[str] = []
    for tok in tokens:
        if out and tok == out[-1] and tok.isalpha():
            continue
        out.append(tok)
    return out


def normalize(text: str) -> str:
    fillers = set(load_lexicon()["fillers"])
    tokens = [t for t in _clean_characters(text).split() if t not in fillers]
    tokens = _words_to_numbers(tokens)
    tokens = _join_spoken_digits(tokens)
    tokens = _dedupe_words(tokens)
    text = _clock_phrases(" ".join(tokens))
    return re.sub(r"\s+", " ", text).strip()

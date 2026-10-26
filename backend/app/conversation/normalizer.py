from __future__ import annotations

import re
import unicodedata

DIGITS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "won": "1",
    "two": "2",
    "too": "2",
    "three": "3",
    "four": "4",
    "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "ate": "8",
    "nine": "9",
}


def normalize(raw: str, context: str | None = None) -> str:
    text = unicodedata.normalize("NFKC", raw).lower().strip()
    text = re.sub(r"[^a-z0-9':\s-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b([ap])\s+m\b", r"\1m", text)
    text = _join_spelled_letters(text)
    if context == "phone" or "number is" in text or "phone" in text:
        text = _normalize_digit_words(text)
    text = _normalize_year_words(text)
    return text.strip()


def _join_spelled_letters(text: str) -> str:
    pattern = re.compile(r"(?:\b[a-z]\s+){2,}[a-z]\b")
    return pattern.sub(lambda match: match.group(0).replace(" ", ""), text)


def _normalize_digit_words(text: str) -> str:
    tokens = text.split()
    converted = [DIGITS.get(token, token) for token in tokens]
    text = " ".join(converted)
    return re.sub(r"(?<!\d)(\d(?:\s+\d){2,})(?!\d)", lambda m: m.group().replace(" ", ""), text)


def _normalize_year_words(text: str) -> str:
    replacements = {
        "twenty twenty one": "2021",
        "twenty twenty two": "2022",
        "twenty twenty three": "2023",
        "twenty twenty four": "2024",
        "twenty twenty five": "2025",
        "twenty twenty six": "2026",
    }
    for words, digits in replacements.items():
        text = text.replace(words, digits)
    return text

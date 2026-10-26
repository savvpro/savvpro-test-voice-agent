"""Deterministic Natural Language Parser for Tableline reservation agent.

Extracts dates, times, guest counts, customer names, confirmation/cancellation intents,
and corrections without using external LLM APIs.
"""

import re
import datetime
from typing import Dict, Any, Optional, Tuple, List
from dateutil import parser as date_parser

NUMBER_WORDS = {
    "one": 1, "a": 1, "an": 1, "single": 1, "two": 2, "couple": 2, "pair": 2,
    "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12
}

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6
}


class DeterministicParser:
    def __init__(self, reference_date: Optional[datetime.date] = None):
        """Allows injecting reference_date for deterministic unit testing."""
        self.ref_date = reference_date or datetime.date.today()

    def set_reference_date(self, ref_date: datetime.date):
        self.ref_date = ref_date

    def normalize(self, text: str) -> str:
        text = text.lower().strip()
        # Clean punctuation except colons and dashes
        text = re.sub(r"[^\w\s:\-]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def extract_intent(self, text: str) -> str:
        """Determines primary user intent from text."""
        norm = self.normalize(text)
        
        # Check cancellation
        if any(w in norm for w in ["cancel", "cancel it", "never mind", "nevermind", "abort", "forget it", "stop"]):
            return "CANCEL"

        # Check restart / reset
        if any(w in norm for w in ["start over", "restart", "reset", "begin again", "start again"]):
            return "RESTART"

        # Check explicit confirmation
        if any(w in norm for w in [
            "yes", "yeah", "yep", "sure", "sounds good", "confirm", "perfect", "that works",
            "looks good", "correct", "absolutely", "please do", "book it", "go ahead"
        ]):
            # Guard against "yes, but make it 4 people"
            if not any(neg in norm for neg in ["actually", "wait", "instead", "no", "change"]):
                return "CONFIRM"

        # Check explicit rejection
        if norm.startswith("no") or "don't book" in norm or "not that" in norm:
            return "REJECT"

        # Check greetings
        if any(norm == g or norm.startswith(g + " ") for g in ["hello", "hi", "hey", "good evening", "good afternoon"]):
            if not any(k in norm for k in ["table", "book", "reserve", "people", "person", "guests", "pm", "am"]):
                return "GREETING"

        # General booking / update intent
        return "BOOK_OR_UPDATE"

    def is_correction(self, text: str) -> bool:
        """Detects if user is revising/correcting previous statements."""
        norm = self.normalize(text)
        correction_signals = [
            "actually", "wait", "change that", "make that", "make it", "instead",
            "rather", "no wait", "sorry i meant", "i mean", "let me change"
        ]
        return any(sig in norm for sig in correction_signals)

    def extract_guest_count(self, text: str) -> Optional[int]:
        """Extracts party size from text (e.g. 'for 4 people', 'party of six', 'two guests', 'make it 6')."""
        norm = self.normalize(text)

        # Pattern 1: numbers before words like people, persons, guests, of us
        match = re.search(r"(\d+)\s*(people|persons|guests|party of|seats|of us)", norm)
        if match:
            return int(match.group(1))

        # Pattern 2: word number followed by people/guests
        for word, num in NUMBER_WORDS.items():
            if re.search(rf"\b{word}\s*(people|persons|guests|seats|of us)\b", norm):
                return num

        # Pattern 3: "party of X" or "table for X"
        match_table = re.search(r"(?:table for|party of|make that|make it|for)\s*(\d+)", norm)
        if match_table:
            return int(match_table.group(1))

        for word, num in NUMBER_WORDS.items():
            if re.search(rf"(?:table for|party of|make that|make it|just)\s+{word}\b", norm):
                return num

        # Pattern 4: direct digits when standalone or answering guest count prompt
        if re.match(r"^\s*(\d+)\s*$", norm):
            return int(norm.strip())

        for word, num in NUMBER_WORDS.items():
            if norm.strip() == word:
                return num

        return None

    def extract_time(self, text: str) -> Optional[str]:
        """Extracts standardized 24-hr time HH:MM from natural language."""
        norm = self.normalize(text)

        # Pattern 1: e.g. "7:30 pm", "19:30", "7 pm", "8pm", "8:00"
        match_12h = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", norm)
        if match_12h:
            hour = int(match_12h.group(1))
            minute = int(match_12h.group(2)) if match_12h.group(2) else 0
            meridiem = match_12h.group(3)
            if meridiem == "pm" and hour < 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            return f"{hour:02d}:{minute:02d}"

        # Pattern 2: 24-hour format e.g. "19:00", "20:30"
        match_24h = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", norm)
        if match_24h:
            hour = int(match_24h.group(1))
            minute = int(match_24h.group(2))
            return f"{hour:02d}:{minute:02d}"

        # Pattern 3: "at 7", "at eight", "at 8" in restaurant context (default to PM for evening dining)
        match_at = re.search(r"\bat\s*(\d{1,2})\b", norm)
        if match_at:
            hour = int(match_at.group(1))
            if 1 <= hour <= 11:  # Restaurant evening dining
                hour += 12
            return f"{hour:02d}:00"

        for word, num in NUMBER_WORDS.items():
            if re.search(rf"\bat\s*{word}\b", norm) or norm.strip() == f"at {word}":
                hour = num
                if 1 <= hour <= 11:
                    hour += 12
                return f"{hour:02d}:00"

        return None

    def extract_date(self, text: str) -> Tuple[Optional[str], bool]:
        """Extracts ISO date YYYY-MM-DD from natural language.
        Returns (date_str, is_ambiguous).
        """
        norm = self.normalize(text)
        today = self.ref_date

        # Relative keywords
        if "today" in norm or "tonight" in norm:
            return today.isoformat(), False
        if "tomorrow" in norm:
            return (today + datetime.timedelta(days=1)).isoformat(), False
        if "day after tomorrow" in norm:
            return (today + datetime.timedelta(days=2)).isoformat(), False

        # Weekdays: "this friday", "next saturday", "friday", "on friday"
        for day_name, day_idx in WEEKDAYS.items():
            if day_name in norm:
                current_weekday = today.weekday()
                # Check for "next <weekday>"
                is_next = f"next {day_name}" in norm
                
                days_ahead = (day_idx - current_weekday) % 7
                if is_next:
                    if days_ahead == 0:
                        days_ahead = 7
                    else:
                        days_ahead += 7

                target_date = today + datetime.timedelta(days=days_ahead)
                return target_date.isoformat(), False

        # Explicit dates like "October 28", "28th of October", "2026-10-30"
        iso_match = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", norm)
        if iso_match:
            d_str = iso_match.group(0)
            try:
                dt = datetime.date.fromisoformat(d_str)
                if dt < today:
                    return None, True  # Past date is rejected / ambiguous
                return d_str, False
            except Exception:
                return None, True

        month_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?\b",
            norm
        )
        if month_match:
            try:
                m_name = month_match.group(1)
                day_num = int(month_match.group(2))
                parsed_dt = date_parser.parse(f"{m_name} {day_num} {today.year}").date()
                if parsed_dt < today:
                    parsed_dt = date_parser.parse(f"{m_name} {day_num} {today.year + 1}").date()
                return parsed_dt.isoformat(), False
            except Exception:
                return None, True

        return None, False

    def extract_name(self, text: str) -> Optional[str]:
        """Extracts customer name when provided e.g. 'name is John', 'under John', 'call me Sarah'."""
        norm = self.normalize(text)
        patterns = [
            r"(?:my name is|name is|i am|i'm|under the name|under)\s+([a-z]+(?:\s+[a-z]+)?)",
            r"(?:call me|this is)\s+([a-z]+)"
        ]
        for p in patterns:
            match = re.search(p, norm)
            if match:
                candidate = match.group(1).title().strip()
                # Exclude false positives like "a table", "friday", etc.
                stopwords = ["a", "table", "booking", "four", "two", "six", "friday", "saturday", "tonight", "tomorrow"]
                if candidate.lower() not in stopwords:
                    return candidate
        return None

    def parse_utterance(self, text: str) -> Dict[str, Any]:
        """Full deterministic extraction bundle for single turn."""
        intent = self.extract_intent(text)
        is_corr = self.is_correction(text)
        guests = self.extract_guest_count(text)
        time_slot = self.extract_time(text)
        date_slot, is_date_ambiguous = self.extract_date(text)
        name = self.extract_name(text)

        return {
            "intent": intent,
            "is_correction": is_corr,
            "guests": guests,
            "time": time_slot,
            "date": date_slot,
            "is_date_ambiguous": is_date_ambiguous,
            "customer_name": name,
            "raw_text": text
        }

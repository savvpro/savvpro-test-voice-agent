"""Deterministic personal expense logging assistant API with SQLite persistence."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from difflib import get_close_matches
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from os import getenv
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4
import time
import httpx

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app.intent_model import classify


@dataclass
class Conversation:
    amount: float | None = None
    currency: str | None = None
    category: str | None = None
    date: str | None = None
    description: str | None = None
    expenses: list[dict[str, str | float]] | None = None
    pending_expenses: list[dict[str, str | float]] | None = None
    last_saved_expenses: list[dict[str, str | float]] | None = None
    last_intent: str | None = None
    last_slots: dict[str, str | None] | None = None
    last_logged_expense: dict[str, str | float] | None = None
    pending_mutation: dict[str, Any] | None = None
    last_mutation: dict[str, Any] | None = None
    awaiting_correction: bool = False
    fail_count: int = 0
    pending_choice: dict[str, Any] | None = None
    trace_notes: list[str] | None = None
    status: Literal["collecting", "confirming", "saved", "cancelled"] = "collecting"

    def __post_init__(self) -> None:
        if self.expenses is None:
            self.expenses = []
        if self.pending_expenses is None:
            self.pending_expenses = []
        if self.last_saved_expenses is None:
            self.last_saved_expenses = []
        if self.last_slots is None:
            self.last_slots = {}
        if self.trace_notes is None:
            self.trace_notes = []


class TurnRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    transcript: str = Field(min_length=1, max_length=1000)


class TurnResponse(BaseModel):
    reply: str
    status: str
    expense: dict[str, str | float] | None = None
    total: float = 0.0
    totals: dict[str, float] = Field(default_factory=dict)
    expenses: list[dict[str, str | float]] = Field(default_factory=list)
    saved_expenses: list[dict[str, str | float]] = Field(default_factory=list)
    turn_id: str | None = None
    confidence: float = 0.0
    decision_trace: list[dict[str, str | float]] = Field(default_factory=list)


class CorrectionRequest(BaseModel):
    turn_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=1000)
    intent: str = Field(min_length=1, max_length=100)


app = FastAPI(title="Penny Voice Assistant", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

conversations: dict[str, Conversation] = {}
DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "expenses.db"
TURN_LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "turns.jsonl"
CORRECTIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "corrections.jsonl"
DEFAULT_CURRENCY = getenv("PENNY_DEFAULT_CURRENCY", "USD").upper()
_RATE_CACHE: dict[tuple[str | None, str, str], tuple[float, float]] = {}
# cache key -> (rate, timestamp); key is (date_iso_or_None, from_currency, to_currency)
_RATE_CACHE_TTL = 60 * 60  # 1 hour


def _convert_amount(amount: float, from_currency: str, to_currency: str, date_iso: str | None = None) -> float | None:
    """Convert amount from one currency to another using exchangerate.host convert endpoint.
    Returns converted amount or None on failure. Caches rates per (date, from, to).
    """
    from_curr = (from_currency or DEFAULT_CURRENCY).upper()
    to_curr = (to_currency or DEFAULT_CURRENCY).upper()
    if from_curr == to_curr:
        return amount
    key = (date_iso, from_curr, to_curr)
    now = time.time()
    cached = _RATE_CACHE.get(key)
    if cached and now - cached[1] < _RATE_CACHE_TTL:
        rate = cached[0]
        return round(amount * rate, 2)
    try:
        params = {"from": from_curr, "to": to_curr, "amount": amount}
        if date_iso:
            params["date"] = date_iso
        resp = httpx.get("https://api.exchangerate.host/convert", params=params, timeout=5.0)
        data = resp.json()
        result = data.get("result")
        if result is None:
            # sometimes API returns success with 'info'->'rate'
            rate = data.get("info", {}).get("rate")
            if rate:
                _RATE_CACHE[key] = (rate, now)
                return round(amount * rate, 2)
            return None
        # store per-unit rate
        rate = data.get("info", {}).get("rate")
        if rate:
            _RATE_CACHE[key] = (rate, now)
        return round(float(result), 2)
    except Exception:
        return None


def _converted_total(expenses: list[dict[str, str | float]], target_currency: str) -> float | None:
    total = 0.0
    any_failed = False
    for exp in expenses:
        amt = float(exp.get("amount", 0.0))
        cur = str(exp.get("currency", DEFAULT_CURRENCY))
        date_iso = str(exp.get("date")) if exp.get("date") else None
        conv = _convert_amount(amt, cur, target_currency, date_iso)
        if conv is None:
            any_failed = True
            continue
        total += float(conv)
    if any_failed and total == 0.0:
        return None
    return round(total, 2)


def _connect_database() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(expenses)").fetchall()}
    if "currency" not in columns:
        connection.execute("ALTER TABLE expenses ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD'")
    connection.commit()
    return connection


@contextmanager
def _db():
    """Open a connection, commit on success, and always close it."""
    connection = _connect_database()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _read_expenses(session_id: str) -> list[dict[str, str | float]]:
    with _db() as connection:
        rows = connection.execute(
            "SELECT amount, currency, category, date, description FROM expenses WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def _save_expenses(session_id: str, expenses: list[dict[str, str | float]]) -> None:
    with _db() as connection:
        connection.executemany(
            "INSERT INTO expenses (session_id, amount, currency, category, date, description) VALUES (?, ?, ?, ?, ?, ?)",
            [(session_id, expense["amount"], expense["currency"], expense["category"], expense["date"], expense["description"]) for expense in expenses],
        )
        connection.commit()


def _delete_expenses(session_id: str) -> None:
    with _db() as connection:
        connection.execute("DELETE FROM expenses WHERE session_id = ?", (session_id,))
        connection.commit()


def _delete_saved_expense(session_id: str, expense: dict[str, str | float]) -> None:
    with _db() as connection:
        connection.execute(
            "DELETE FROM expenses WHERE id = (SELECT id FROM expenses WHERE session_id = ? AND amount = ? AND currency = ? AND category = ? AND date = ? AND description = ? ORDER BY id DESC LIMIT 1)",
            (session_id, expense["amount"], expense["currency"], expense["category"], expense["date"], expense["description"]),
        )
        connection.commit()


def _update_saved_expense(session_id: str, previous: dict[str, str | float], updated: dict[str, str | float]) -> None:
    with _db() as connection:
        connection.execute(
            "UPDATE expenses SET amount = ?, currency = ?, category = ?, date = ?, description = ? WHERE id = (SELECT id FROM expenses WHERE session_id = ? AND amount = ? AND currency = ? AND category = ? AND date = ? AND description = ? ORDER BY id DESC LIMIT 1)",
            (updated["amount"], updated["currency"], updated["category"], updated["date"], updated["description"], session_id, previous["amount"], previous["currency"], previous["category"], previous["date"], previous["description"]),
        )
        connection.commit()


def _conversation_for(session_id: str) -> Conversation:
    conversation = conversations.get(session_id)
    if conversation is None:
        conversation = Conversation(expenses=_read_expenses(session_id))
        if conversation.expenses:
            conversation.last_logged_expense = conversation.expenses[-1]
        context = _read_last_turn_context(session_id)
        if context:
            conversation.last_intent = context.get("last_intent")
            conversation.last_slots = context.get("last_slots") or {}
        conversations[session_id] = conversation
    return conversation


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_last_turn_context(session_id: str) -> dict[str, Any] | None:
    if not TURN_LOG_PATH.exists():
        return None
    for line in reversed(TURN_LOG_PATH.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("session_id") == session_id:
            return record
    return None


_CATEGORY_TERMS = {
    "groceries": ("grocery", "groceries", "supermarket"),
    "dining": ("dining", "restaurant", "lunch", "dinner", "takeout", "takeout", "food", "cafe", "coffee"),
    "transport": ("transport", "gas", "fuel", "uber", "taxi", "bus", "train", "parking"),
    "shopping": ("shopping", "clothes", "clothing", "shoes", "toy", "toys"),
    "bills": ("bill", "bills", "rent", "utilities", "electricity", "internet", "phone"),
    "entertainment": ("movie", "movies", "concert", "game", "entertainment", "streaming"),
    "health": ("health", "doctor", "pharmacy", "medicine", "medical"),
    "travel": ("travel", "hotel", "flight", "airfare"),
    "education": ("education", "school", "course", "books", "tuition"),
}


_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

_SCALE_WORDS = {"hundred": 100, "thousand": 1000, "million": 1000000}


_SYNONYMS = {
    "mt": "my", "tha": "the", "wat": "what", "whats": "what's", "plz": "please",
    "expenditure": "expense", "expenditures": "expenses", "spendings": "spending",
    "outgoings": "expenses", "expence": "expense", "expences": "expenses",
}
_VOCAB = sorted({
    "spending", "spent", "spend", "expense", "expenses", "total", "today", "yesterday",
    "groceries", "restaurant", "transport", "shopping", "entertainment", "education",
    "category", "delete", "remove", "update", "change", "yesterday", "summary",
    *(term for terms in _CATEGORY_TERMS.values() for term in terms if len(term) >= 5),
})


def _normalize(text: str) -> str:
    """Fix common STT/typing slips before any rule runs. Only touches words that change, so casing elsewhere is preserved."""
    def fix(match: re.Match) -> str:
        word = match.group(0)
        lowered = word.lower()
        if lowered in _SYNONYMS:
            return _SYNONYMS[lowered]
        if len(lowered) >= 5 and lowered not in _VOCAB and lowered.isalpha():
            close = get_close_matches(lowered, _VOCAB, n=1, cutoff=0.84)
            if close:
                return close[0]
        return word
    return re.sub(r"[A-Za-z']+", fix, text)


CLASSIFIER_CONFIDENT = 0.75   # act on the classifier alone at/above this (keep in sync with train.py CONFIDENT)
CLASSIFIER_HINT_FLOOR = 0.50  # below this the classifier's guess is not even mentioned to the user


def _hint_is(hint: tuple[str, float] | None, intent: str, minimum: float) -> bool:
    return bool(hint) and hint[0] == intent and hint[1] >= minimum


def _currency_for(text: str) -> str:
    lowered = text.lower()
    if "$" in text or re.search(r"\b(?:usd|dollars?|bucks?)\b", lowered):
        return "USD"
    if "€" in text or re.search(r"\b(?:eur|euros?)\b", lowered):
        return "EUR"
    if "£" in text or re.search(r"\b(?:gbp|pounds?)\b", lowered):
        return "GBP"
    if "¥" in text or re.search(r"\b(?:jpy|yen)\b", lowered):
        return "JPY"
    if re.search(r"\b(?:cad|canadian dollars|canadian)\b", lowered):
        return "CAD"
    if re.search(r"\b(?:aud|australian dollars|australian)\b", lowered):
        return "AUD"
    if re.search(r"\b(?:inr|rupees|rs\.?|rupee)\b", lowered):
        return "INR"
    # Pakistani rupee (explicit code or mentions)
    if re.search(r"\b(?:pkr|pakistani\s+rupees?|pakistan\s*rupee|pak rupee|pakistani)\b", lowered):
        return "PKR"
    # common 'rs' abbreviation (ambiguous) - prefer INR if 'inr' present, otherwise leave default
    if re.search(r"\brs\.?\b", lowered) and re.search(r"\b(inr|rupee|rupees)\b", lowered):
        return "INR"
    return DEFAULT_CURRENCY


def _valid_amount(value: float) -> float | None:
    return round(value, 2) if 0 < value <= 1_000_000 else None


def _spoken_amounts(text: str) -> list[tuple[float, int, int]]:
    results: list[tuple[float, int, int]] = []
    word = r"(?:" + "|".join(_NUMBER_WORDS) + r")"
    for match in re.finditer(rf"\b({word})\s+hundred\b", text.lower()):
        results.append((_NUMBER_WORDS[match.group(1)] * 100, match.start(), match.end()))
    for match in re.finditer(rf"\b({word})\s+(?:k|thousand)\b", text.lower()):
        results.append((_NUMBER_WORDS[match.group(1)] * 1000, match.start(), match.end()))
    # parse longer number-word sequences like "one hundred twenty five" or "two thousand three hundred"
    for match in re.finditer(r"\b(?:" + "|".join(_NUMBER_WORDS) + r"|hundred|thousand|million|and)(?:[ -](?:" + "|".join(_NUMBER_WORDS) + r"|hundred|thousand|million|and))*\b", text.lower()):
        seq = match.group(0)
        # skip trivial matches already captured above
        if re.search(r"\b(?:hundred|thousand|million)\b", seq):
            try:
                value = _parse_number_words(seq)
                if value is not None and _valid_amount(value) is not None:
                    results.append((value, match.start(), match.end()))
            except Exception:
                pass
    for match in re.finditer(rf"\b({word})\s+({word})(?=\s+(?:bucks?|dollars?|on|for)\b)", text.lower()):
        first = _NUMBER_WORDS[match.group(1)]
        second = _NUMBER_WORDS[match.group(2)]
        # Conversational money: “four fifty” means 4 dollars 50 cents.
        value = first + (second / 100 if second >= 10 else second)
        results.append((value, match.start(), match.end()))
    for match in re.finditer(rf"\b({word})\s+(?:bucks?|dollars?)\b", text.lower()):
        results.append((_NUMBER_WORDS[match.group(1)], match.start(), match.end()))
    return [(amount, start, end) for amount, start, end in results if _valid_amount(amount) is not None]


def _sanitize_category(cat: str | None) -> str:
    if not cat:
        return ""
    s = str(cat).strip()
    # if category is purely numeric (or contains digits), do not treat it as a category name
    if re.search(r"\d", s):
        return ""
    return s


def _parse_number_words(seq: str) -> float | None:
    """Convert sequences like 'one hundred twenty five' to numeric value.
    Returns None if cannot parse."""
    parts = re.split(r"[ -]|\band\b", seq)
    parts = [p for p in parts if p and p.isalpha()]
    total = 0
    current = 0
    for p in parts:
        if p in _NUMBER_WORDS:
            current += _NUMBER_WORDS[p]
        elif p in _SCALE_WORDS:
            scale = _SCALE_WORDS[p]
            if current == 0:
                current = 1
            current *= scale
            total += current
            current = 0
        else:
            # unknown token
            return None
    total += current
    return float(total) if total else None


def _amount_matches(text: str) -> list[tuple[float, int, int]]:
    matches: list[tuple[float, int, int]] = []
    numeric_patterns = (
        r"\$\s*(\d{1,8}(?:,\d{3})*(?:\.\d{1,2})?)(k)?",
        r"\b(\d{1,8}(?:,\d{3})*(?:\.\d{1,2})?)\s+k\b",
        r"\b(\d{1,8}(?:\.\d{1,2})?)(k)\b",
        r"\b(?:to|as|from|into)\s+\$?(\d{1,8}(?:,\d{3})*(?:\.\d{1,2})?)\b",
        r"\b(?:spent|paid|cost|costs|for)\s+(?:usd\s*)?(\d{1,8}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:dollars?|bucks?)?\b",
        r"\b(\d{1,8}(?:,\d{3})*(?:\.\d{1,2})?)\s+(?:dollars?|bucks?)\b",
        r"\b(\d{1,8}(?:,\d{3})*(?:\.\d{1,2})?)(?=\s+(?:on|for)\b)",
    )
    for pattern in numeric_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = float(match.group(1).replace(",", ""))
            if match.lastindex and match.lastindex >= 2 and match.group(2):
                value *= 1000
            if _valid_amount(value) is not None:
                matches.append((value, match.start(), match.end()))
    matches.extend(_spoken_amounts(text))
    unique: list[tuple[float, int, int]] = []
    for candidate in sorted(matches, key=lambda item: (item[1], -(item[2] - item[1]))):
        if not any(candidate[1] >= existing[1] and candidate[1] < existing[2] for existing in unique):
            unique.append(candidate)
    return unique


def _extract_amount(text: str) -> float | None:
    matches = _amount_matches(text)
    return matches[0][0] if matches else None


def _extract_category(text: str) -> str | None:
    lowered = text.lower()
    matches: list[tuple[int, str]] = []
    for category, terms in _CATEGORY_TERMS.items():
        for term in terms:
            match = re.search(rf"\b{re.escape(term)}\b", lowered)
            if match:
                matches.append((match.start(), category))
    if matches:
        return max(matches, key=lambda item: item[0])[1]
    match = re.search(r"\b(?:category|under)\s+(groceries|dining|transport|shopping|bills|entertainment|health|travel|education)\b", lowered)
    return match.group(1) if match else None


def _safe_iso(year: int, month: int, day: int) -> str | None:
    """ISO date string, or None for impossible dates such as 31 February."""
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _extract_date(text: str, today: date | None = None) -> str | None:
    today = today or date.today()
    normalized = text.lower()
    if re.search(r"\btwo days ago\b", normalized):
        return (today - timedelta(days=2)).isoformat()
    if re.search(r"\byesterday\b", normalized):
        return (today - timedelta(days=1)).isoformat()
    if re.search(r"\btomorrow\b", normalized):
        return (today + timedelta(days=1)).isoformat()
    # last <weekday>
    last_day = re.search(r"\blast\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", normalized)
    if last_day:
        weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday").index(last_day.group(1))
        days_ago = (today.weekday() - weekday) % 7 or 7
        return (today - timedelta(days=days_ago)).isoformat()
    # last weekend -> most recent Saturday
    if re.search(r"\blast\s+weekend\b", normalized):
        weekday = 5  # saturday
        days_ago = (today.weekday() - weekday) % 7 or 7
        return (today - timedelta(days=days_ago)).isoformat()
    # simple named days
    for day in ("today", "yesterday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        if re.search(rf"\b{day}\b", normalized):
            if day == "today":
                return today.isoformat()
            if day == "yesterday":
                return (today - timedelta(days=1)).isoformat()
            weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday").index(day)
            # Expenses are in the past: a bare weekday means its most recent occurrence (today included).
            days_ago = (today.weekday() - weekday) % 7
            return (today - timedelta(days=days_ago)).isoformat()
    # yyyy-mm-dd
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", normalized)
    if match:
        return _safe_iso(*(int(part) for part in match.group(1).split("-")))
    # mm/dd[/yy[yy]]
    match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", normalized)
    if match:
        month, day_number, year = match.groups()
        year_number = int(year) + (2000 if year and len(year) == 2 else 0) if year else today.year
        return _safe_iso(year_number, int(month), int(day_number))
    # month name (allow short forms)
    months = "january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
    month_match = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({months})\b", normalized)
    if not month_match:
        month_match = re.search(rf"\b({months})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", normalized)
        if month_match:
            month_name, day_number = month_match.groups()
        else:
            return None
    else:
        day_number, month_name = month_match.groups()
    month_name = month_name if month_name else month_name
    month_number = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december").index(month_name if len(month_name) > 3 else { 'jan':'january','feb':'february','mar':'march','apr':'april','may':'may','jun':'june','jul':'july','aug':'august','sep':'september','sept':'september','oct':'october','nov':'november','dec':'december' }[month_name]) + 1
    return _safe_iso(today.year, month_number, int(day_number))


def _extract_description(text: str, category: str | None) -> str | None:
    # prefer explicit 'for/on/at' descriptions
    match = re.search(r"\b(?:for|on|at)\s+(.+)$", text, re.IGNORECASE)
    if match:
        description = match.group(1).strip(" .,!? ")
        description = re.sub(r"\s+and$", "", description, flags=re.IGNORECASE).strip(" .,!? ")
        description = re.sub(r"\b(?:today|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", "", description, flags=re.IGNORECASE).strip(" .,!?")
        if category and description.lower() == category:
            return None
        return description[:80] or None

    # capture purchase-like phrases: "I bought an iPhone", "bought 2 toys", "purchased phone"
    buy_match = re.search(r"\b(?:bought|purchased|got|ordered|paid for|paid)\s+(?:an|a|the)?\s*([0-9]+\s+)?([A-Za-z0-9][A-Za-z0-9' &\-]{1,80})", text, re.IGNORECASE)
    if buy_match:
        qty = (buy_match.group(1) or "").strip()
        noun = buy_match.group(2).strip(" .,!? ")
        description = (qty + " " + noun).strip()
        if category and description.lower() == category:
            return None
        return description[:80]

    return None


def _is_yes(text: str) -> bool:
    return bool(re.search(r"\b(yes|yeah|yep|correct|confirm|that's right|sounds good|save it|log it)\b", text.lower()))


def _is_no(text: str) -> bool:
    return bool(re.search(r"\b(no|nope|wrong|change|actually)\b", text.lower()))


def _is_income(text: str) -> bool:
    return bool(re.search(r"\b(got paid|got my paycheck|paycheck|salary|income|earned|made money|received a payment|deposit)\b", text.lower()))


def _category_prompt(description: str | None = None) -> str:
    if description and re.search(r"\b(store|stuff|something|things|misc|various)\b", description.lower()):
        return "Was that groceries or general shopping? I don’t want to guess the category."
    return "What category should I use: groceries, dining, transport, shopping, bills, entertainment, health, travel, or education?"


def _is_spending_summary(text: str) -> bool:
    return bool(re.search(r"\b(total spending|total spent|total expense|total expenses|my total expense|my total expenses|how much have i spent|how much did i spend|spending total|expense summary|spending summary)\b", text.lower()))


def _query_slots(text: str) -> dict[str, str | None]:
    lowered = text.lower()
    if re.search(r"\bthis week\b", lowered):
        period = "this week"
    elif re.search(r"\blast week\b", lowered):
        period = "last week"
    elif re.search(r"\bthis month\b", lowered):
        period = "this month"
    elif re.search(r"\blast month\b", lowered):
        period = "last month"
    else:
        period = _extract_date(text)
    category = _extract_category(text)
    # detect an explicit target currency in the query: 'in USD', 'in PKR', 'to USD', etc.
    target_currency = None
    m = re.search(r"\b(?:in|to)\s+([A-Za-z]{2,4}|usd|eur|gbp|pkr|inr|idr|jpy|cad|aud|rupees?|dollars?|euros?|pounds?)\b", lowered)
    if m:
        token = m.group(1)
        # normalize words like 'dollars' -> USD via _currency_for
        # feed a small phrase to _currency_for to detect code
        target_currency = _currency_for(token)
    return {"period": period, "category": category, "target_currency": target_currency}


def _is_query_total_request(text: str) -> bool:
    lowered = text.lower()
    has_query_language = bool(re.search(r"\b(how much|how many|what is|what's|come to|comes to|add up|adds up|amount to|what did i spend|what do i spend|tell me|show me|give me|total|amount|spending summary)\b", lowered))
    has_spending_term = bool(re.search(r"\b(spending|spent|expense|expenses|cost|money)\b", lowered))
    return has_query_language and has_spending_term


def _is_follow_up(text: str) -> bool:
    return bool(re.match(r"\s*(and|what about|how about|same for|only|make that|change that|what if)\b", text.lower()))


def _date_from_value(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        if value.lower() == "today":
            return date.today()
    return None


def _matches_period(expense: dict[str, str | float], period: str | None) -> bool:
    if not period:
        return True
    expense_date = _date_from_value(str(expense.get("date", "")))
    if expense_date is None:
        return False
    today = date.today()
    if period == "this week":
        return today - timedelta(days=today.weekday()) <= expense_date <= today
    if period == "last week":
        start = today - timedelta(days=today.weekday() + 7)
        return start <= expense_date < start + timedelta(days=7)
    if period == "this month":
        return expense_date.year == today.year and expense_date.month == today.month
    if period == "last month":
        month = today.month - 1 or 12
        year = today.year if today.month > 1 else today.year - 1
        return expense_date.year == year and expense_date.month == month
    target = _date_from_value(period)
    return target == expense_date if target else False


def _query_total_reply(expenses: list[dict[str, str | float]], slots: dict[str, str | None]) -> str:
    filtered = [expense for expense in expenses if _matches_period(expense, slots.get("period")) and (not slots.get("category") or expense.get("category") == slots["category"])]
    if not filtered:
        qualifier = f" for {slots['period']}" if slots.get("period") else ""
        if slots.get("category"):
            qualifier += f" on {slots['category']}"
        return f"You have no saved expenses{qualifier}."
    total_text = _total_text(filtered)
    # if user requested a specific currency, return converted total in that currency first
    target = slots.get("target_currency") if isinstance(slots, dict) else None
    if target:
        conv_target = _converted_total(filtered, target)
        if conv_target is not None:
            if not slots.get("period") and not slots.get("category"):
                return f"Your total spending is {target} {conv_target:.2f} across {len(filtered)} logged expense(s). Original totals: {total_text}."
            if slots.get("period") == date.today().isoformat() and not slots.get("category"):
                entries = "; ".join(f"{item.get('currency', DEFAULT_CURRENCY)} {float(item['amount']):.2f} for {item.get('description') or item.get('category')}" for item in filtered)
                return f"Today you spent {target} {conv_target:.2f} across {len(filtered)} expense(s): {entries}."
            qualifier = f" for {slots['period']}" if slots.get("period") else ""
            if slots.get("category"):
                qualifier += f" on {slots['category']}"
            entries = "; ".join(f"{item.get('currency', DEFAULT_CURRENCY)} {float(item['amount']):.2f} for {item.get('description') or item.get('category')}" for item in filtered)
            return f"You spent {target} {conv_target:.2f}{qualifier} across {len(filtered)} expense(s): {entries}."

    # attempt to present a converted total in DEFAULT_CURRENCY when multiple currencies are present
    currencies = {str(item.get("currency", DEFAULT_CURRENCY)) for item in filtered}
    converted_note = ""
    if len(currencies) > 1 or (len(currencies) == 1 and next(iter(currencies)) != DEFAULT_CURRENCY):
        conv = _converted_total(filtered, DEFAULT_CURRENCY)
        if conv is not None:
            converted_note = f" (≈ {DEFAULT_CURRENCY} {conv:.2f} at current rates)"
    entries = "; ".join(f"{item.get('currency', DEFAULT_CURRENCY)} {float(item['amount']):.2f} for {item.get('description') or item.get('category')}" for item in filtered)
    # if user asked for a specific currency, try to provide the converted total in that currency
    target = slots.get("target_currency") if isinstance(slots, dict) else None
    if target:
        conv_target = _converted_total(filtered, target)
        if conv_target is not None:
            # show the converted total as the primary answer, include original breakdown
            if not slots.get("period") and not slots.get("category"):
                return f"Your total spending is {target} {conv_target:.2f} across {len(filtered)} logged expense(s). Original totals: {total_text}."
            if slots.get("period") == date.today().isoformat() and not slots.get("category"):
                return f"Today you spent {target} {conv_target:.2f} across {len(filtered)} expense(s): {entries}."
            qualifier = f" for {slots['period']}" if slots.get("period") else ""
            if slots.get("category"):
                qualifier += f" on {slots['category']}"
            return f"You spent {target} {conv_target:.2f}{qualifier} across {len(filtered)} expense(s): {entries}."
    if not slots.get("period") and not slots.get("category"):
        return f"Your total spending is {total_text} across {len(filtered)} logged expense(s){converted_note}."
    if slots.get("period") == date.today().isoformat() and not slots.get("category"):
        return f"Today you spent {total_text} across {len(filtered)} expense(s): {entries}{converted_note}."
    qualifier = f" for {slots['period']}" if slots.get("period") else ""
    if slots.get("category"):
        qualifier += f" on {slots['category']}"
    return f"You spent {total_text}{qualifier} across {len(filtered)} expense(s): {entries}{converted_note}."


def _is_today_spending_question(text: str) -> bool:
    lowered = text.lower()
    has_today = bool(re.search(r"\b(today|this day)\b", lowered))
    asks_amount = bool(re.search(r"\b(how much|how many|total|amount|money)\b", lowered))
    asks_breakdown = bool(re.search(r"\b(which things|what things|what did i spend|where did i spend|breakdown|items?)\b", lowered))
    return has_today and (asks_amount or asks_breakdown)


def _is_spending_breakdown_question(text: str) -> bool:
    return bool(re.search(r"\b(what are .*?spend money on|what do i spend money on|where do i spend money|what do i spend on|what things do i buy)\b", text.lower()))


def _is_log_update_request(text: str) -> bool:
    return bool(re.search(r"\b(update|edit|change|modify|correct|remove|delete|fix)\b", text.lower()) and re.search(r"\b(log|expense|expenses|entry|entries|record|records)\b", text.lower()))


def _is_delete_reference(text: str) -> bool:
    return bool(re.search(r"\b(delete|remove)\b", text.lower()) and re.search(r"\b(that|it|last expense|last entry)\b", text.lower()))


def _is_generic_delete_request(text: str) -> bool:
    lowered = text.lower()
    return bool(re.search(r"\b(delete|remove)\b", lowered) and re.search(r"\b(one|an|a)\s+(expense|entry|record)\b", lowered))


def _is_change_reference(text: str) -> bool:
    return bool(re.search(r"\b(change|make|update|correct)\b", text.lower()) and re.search(r"\b(that|it|last expense|last entry)\b", text.lower()) and _extract_amount(text) is not None)

def _is_compound_mutation(text: str) -> bool:
    lowered = text.lower()
    return bool(re.search(r"\b(delete|remove)\b", lowered) and re.search(r"\b(update|edit|change|modify|correct)\b", lowered) and re.search(r"\band\b", lowered))

def _targeted_delete_expense(text: str, expenses: list[dict[str, str | float]]) -> dict[str, str | float] | None:
    lowered = text.lower()
    if not re.search(r"\b(delete|remove)\b", lowered):
        return None
    target_date = _extract_date(text)
    target_category = _extract_category(text)
    if not target_date and not target_category:
        return None
    matches = []
    for expense in expenses:
        expense_date = str(expense.get("date", ""))
        description_date = _extract_date(str(expense.get("description", "")))
        date_matches = not target_date or target_date in (expense_date, description_date)
        category_matches = not target_category or expense.get("category") == target_category
        if date_matches and category_matches:
            matches.append(expense)
    return matches[-1] if len(matches) == 1 else None


def _targeted_update_expense(text: str, expenses: list[dict[str, str | float]]) -> tuple[dict[str, str | float], float] | None:
    lowered = text.lower()
    if not re.search(r"\b(update|edit|change|modify|correct)\b", lowered) or not re.search(r"\b(expense|entry|record|log)\b", lowered):
        return None
    amounts = _amount_matches(text)
    if len(amounts) < 2:
        return None
    old_amount, new_amount = amounts[0][0], amounts[1][0]
    category = _extract_category(text)
    matches = [expense for expense in expenses if abs(float(expense["amount"]) - old_amount) < 0.005 and (not category or expense.get("category") == category)]
    return (matches[-1], new_amount) if len(matches) == 1 else None


def _targeted_category_update(text: str, expenses: list[dict[str, str | float]]) -> tuple[dict[str, str | float], str] | None:
    match = re.search(r"\bfrom\s+(groceries|dining|transport|shopping|bills|entertainment|health|travel|education)\s+to\s+(?:a|an)\s+([a-z][a-z -]*)", text.lower())
    if not match:
        return None
    old_category, new_category = match.groups()
    new_category = new_category.strip(" .,!? ")
    matches = [expense for expense in expenses if expense.get("category") == old_category]
    described_matches = [expense for expense in matches if new_category in str(expense.get("description", "")).lower()]
    if len(described_matches) == 1:
        return described_matches[0], new_category
    return (matches[-1], new_category) if len(matches) == 1 else None


def _targeted_description_update(text: str, expenses: list[dict[str, str | float]]) -> tuple[dict[str, str | float], str] | None:
    """Detect requests like 'change the bills expense to iPhone' and return (target_expense, new_description)."""
    lowered = text.lower()
    if not re.search(r"\b(change|set|rename|update|make)\b", lowered):
        return None
    category, term = _category_and_term(text)
    if not category:
        return None
    m = re.search(r"\bto\s+([A-Za-z0-9][A-Za-z0-9' &\-]{1,80})", text, re.IGNORECASE)
    if not m:
        return None
    new_desc = m.group(1).strip(" .,!? ")
    matches = [expense for expense in expenses if expense.get("category") == category]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0], new_desc
    # try to narrow by term appearing in description
    if term and term != category:
        narrow = [e for e in matches if term in str(e.get("description", "")).lower()]
        if len(narrow) == 1:
            return narrow[0], new_desc
    return None


def _today_expenses(expenses: list[dict[str, str | float]]) -> list[dict[str, str | float]]:
    today = date.today().isoformat()
    return [item for item in expenses if str(item.get("date", "")).lower() in (today, "today")]


def _today_spending_reply(expenses: list[dict[str, str | float]]) -> str:
    today_expenses = _today_expenses(expenses)
    if not today_expenses:
        return "You have no saved expenses for today."
    total_text = _total_text(today_expenses)
    entries = "; ".join(
        f"{item.get('currency', DEFAULT_CURRENCY)} {float(item['amount']):.2f} for {item.get('description') or item['category']}"
        for item in today_expenses
    )
    return f"Today you spent {total_text} across {len(today_expenses)} expense(s): {entries}."


def _spending_breakdown_reply(expenses: list[dict[str, str | float]]) -> str:
    if not expenses:
        return "You have no saved expenses to summarize yet."
    category_totals: dict[tuple[str, str], float] = {}
    for expense in expenses:
        key = (str(expense.get("currency", DEFAULT_CURRENCY)), str(expense.get("category") or "uncategorized"))
        category_totals[key] = round(category_totals.get(key, 0.0) + float(expense["amount"]), 2)
    items = sorted(category_totals.items(), key=lambda item: (-item[1], item[0][1]))
    breakdown = "; ".join(f"{category}: {currency} {amount:.2f}" for (currency, category), amount in items)
    return f"You spend money on {breakdown}."


def _is_history_question(text: str) -> bool:
    return bool(re.search(r"\b(why (?:are|is) there .*logged expenses?|what are (?:these|the) .*?\b(?:log|logged)?\s*expenses?|what expenses|which expenses|show .*expenses|list .*expenses|expense history|logged expenses?)\b", text.lower()))


def _is_current_expense_question(text: str) -> bool:
    return bool(re.search(r"\b(current expense|latest expense|most recent expense|last expense)\b", text.lower()))


def _is_expense_recall_question(text: str) -> bool:
    lowered = text.lower()
    return bool(re.search(r"\b(wasn't|was not|was it|i thought|didn't i|before|earlier|previously)\b", lowered) and re.search(r"\$|\b(?:expense|spending|amount|total)\b", lowered))


def _history_reply(expenses: list[dict[str, str | float]]) -> str:
    if not expenses:
        return "There are no saved expenses in this session."
    entries = "; ".join(
        f"{item.get('currency', DEFAULT_CURRENCY)} {float(item['amount']):.2f} for {item.get('description') or item['category']}"
        for item in expenses
    )
    return f"This session has {len(expenses)} saved expense(s): {entries}. One session can contain multiple expense entries; the session is just the container."


def _current_expense_reply(expenses: list[dict[str, str | float]]) -> str:
    if not expenses:
        return "There are no saved expenses in this session."
    expense = expenses[-1]
    description = expense.get("description") or expense.get("category")
    return f"Your most recent saved expense is {expense.get('currency', DEFAULT_CURRENCY)} {float(expense['amount']):.2f} for {description} on {expense['date']}."


def _expense_recall_reply(text: str, expenses: list[dict[str, str | float]]) -> str:
    amount = _extract_amount(text)
    if amount is not None:
        matching = [item for item in expenses if abs(float(item["amount"]) - amount) < 0.005]
        if matching:
            item = matching[-1]
            description = item.get("description") or item.get("category")
            others = [item for item in expenses if item is not matching[-1]]
            response = f"Yes, you have a saved {item.get('currency', DEFAULT_CURRENCY)} {float(item['amount']):.2f} expense for {description}."
            if others:
                response += f" Your full saved total is {_total_text(expenses)} across {len(expenses)} expense(s)."
            return response
    return _history_reply(expenses)


def _small_talk_reply(text: str) -> str | None:
    lowered = text.lower()
    answers: list[str] = []
    if re.search(r"\b(how are (?:you|yu|ya|ypu)|how're you|how are things)\b", lowered):
        answers.append("I’m doing well, thanks for asking!")
    if re.search(r"\b(where do you live|where are you from|where is your home)\b", lowered):
        answers.append("I’m a virtual assistant, so I don’t have a physical home.")
    if re.search(r"\b(who are you|what are you|what can you do|help)\b", lowered):
        answers.append("I’m Penny, and I can help you log personal expenses and keep a running total.")
    if re.search(r"\b(why would i tell you|why should i tell you|why do you need to know)\b", lowered):
        answers.append("You only need to share an expense if you want it added to your log; it’s entirely up to you.")
    if answers:
        answers.append("For example, you can say ‘$12.50 on lunch.’")
        return " ".join(answers)
    return None


def _missing_prompt(conversation: Conversation) -> str:
    if conversation.amount is None:
        return "How much was the expense? You can say an amount like $12.50."
    if conversation.category is None:
        return _category_prompt(conversation.description)
    if conversation.date is None:
        conversation.date = date.today().isoformat()
    conversation.status = "confirming"
    description = f" for {conversation.description}" if conversation.description else ""
    currency = conversation.currency or DEFAULT_CURRENCY
    return f"I’ll log {currency} {conversation.amount:.2f} under {conversation.category}{description} for {conversation.date}. Should I save it?"


def _pending_prompt(expenses: list[dict[str, str | float]]) -> str:
    entries = "; ".join(
        f"{item['currency']} {float(item['amount']):.2f} under {item['category']} for {item['date']}"
        for item in expenses
    )
    return f"I found {len(expenses)} expenses: {entries}. Should I save them all?"


def _expense_dict(conversation: Conversation) -> dict[str, str | float]:
    return {
        "amount": conversation.amount or 0.0,
        "currency": conversation.currency or DEFAULT_CURRENCY,
        "category": _sanitize_category(conversation.category),
        "date": conversation.date or "",
        "description": conversation.description or "",
    }


def handle_turn(conversation: Conversation, transcript: str, hint: tuple[str, float] | None = None) -> tuple[str, dict[str, str | float] | None]:
    text = _normalize(transcript.strip())
    lowered = text.lower()
    conversation.trace_notes = []
    if text != transcript.strip():
        conversation.trace_notes.append(f"Normalized input: {text!r}")

    if re.search(r"\b(cancel|never mind|nevermind|discard)\b", lowered) or re.fullmatch(r"\s*stop(?: that| it)?[.!]*\s*", lowered):
        conversation.status = "cancelled"
        conversation.pending_choice = conversation.pending_mutation = None
        conversation.amount = conversation.currency = conversation.category = conversation.date = conversation.description = None
        conversation.pending_expenses = []
        return "Okay, I discarded that expense. Your previously logged expenses are unchanged.", None

    if conversation.pending_choice:
        choice, conversation.pending_choice = conversation.pending_choice, None
        picked = _pick_candidate(text, choice["candidates"])
        if picked is not None:
            return _mutation_prompt(conversation, choice["action"], picked, choice.get("amount")), None
        # not an answer to the question: fall through and treat it as a normal new request

    if conversation.pending_mutation and conversation.status == "confirming" and _is_no(text) and not _amount_matches(text):
        # allow 'No, update it to Samsung Galaxy' style corrections while confirming
        to_match = re.search(r"\b(?:to|as|under|call it)\s+(.+)$", lowered)
        if to_match:
            new_desc = to_match.group(1).strip(" .,!? ")[:80]
            # convert pending mutation into a description update
            previous = conversation.pending_mutation.get("target") or conversation.last_logged_expense
            conversation.pending_mutation = {"action": "description_update", "target": previous, "description": new_desc}
            conversation.status = "confirming"
            desc = previous.get("description") or previous.get("category") if previous else "that expense"
            return f"Should I update {desc} to {new_desc}?", None
        # otherwise user is rejecting the pending mutation
        conversation.pending_mutation = None
        conversation.status = "saved"
        return "Okay, I left your log unchanged.", None

    if _is_income(text):
        return "I can log spending, but not income. I didn’t add that payment to your expense log.", None

    if _is_compound_mutation(text):
        return (
            "I heard both a delete request and an update request. I won’t change anything yet because they may refer to the same dining expense. "
            "Please do them separately, for example: ‘remove the dining expense from October 26’ or ‘update food from $3 to $5’.",
            None,
        )

    targeted_category_update = _targeted_category_update(text, conversation.expenses or [])
    if targeted_category_update:
        target, new_category = targeted_category_update
        conversation.pending_mutation = {"action": "category_update", "target": target, "category": new_category}
        conversation.status = "confirming"
        description = target.get("description") or target.get("category")
        return f"Should I rename the category from {target['category']} to {new_category} for {target.get('currency', DEFAULT_CURRENCY)} {float(target['amount']):.2f} ({description})?", None

    targeted_description_update = _targeted_description_update(text, conversation.expenses or [])
    if targeted_description_update:
        target, new_description = targeted_description_update
        conversation.pending_mutation = {"action": "description_update", "target": target, "description": new_description}
        conversation.status = "confirming"
        description = target.get("description") or target.get("category")
        return f"Should I update the description for {target.get('currency', DEFAULT_CURRENCY)} {float(target['amount']):.2f} from {description} to {new_description}?", None

    targeted_delete = _targeted_delete_expense(text, conversation.expenses or [])
    if targeted_delete:
        conversation.pending_mutation = {"action": "delete", "target": targeted_delete}
        conversation.status = "confirming"
        description = targeted_delete.get("description") or targeted_delete.get("category")
        requested_date = _extract_date(text) or str(targeted_delete["date"])
        return f"Should I delete {targeted_delete.get('currency', DEFAULT_CURRENCY)} {float(targeted_delete['amount']):.2f} for {description} on {requested_date}?", None

    targeted_update = _targeted_update_expense(text, conversation.expenses or [])
    if targeted_update:
        target, new_amount = targeted_update
        conversation.pending_mutation = {"action": "update", "target": target, "amount": new_amount}
        conversation.status = "confirming"
        description = target.get("description") or target.get("category")
        return f"Should I update {description} from {target.get('currency', DEFAULT_CURRENCY)} {float(target['amount']):.2f} to {target.get('currency', DEFAULT_CURRENCY)} {new_amount:.2f}?", None

    mutation_reply = _start_mutation(conversation, text)
    if mutation_reply:
        return mutation_reply, None

    if _is_generic_delete_request(text):
        if not conversation.expenses:
            return "There are no saved expenses to remove.", None
        if len(conversation.expenses) == 1:
            target = conversation.expenses[0]
            conversation.pending_mutation = {"action": "delete", "target": target}
            conversation.status = "confirming"
            description = target.get("description") or target.get("category")
            return f"Should I delete {target.get('currency', DEFAULT_CURRENCY)} {float(target['amount']):.2f} for {description}?", None
        return "Which expense should I remove? Tell me its amount, category, description, or date.", None

    if _is_log_update_request(text):
        return (
            "Yes. I can update your log. Would you like to add a new expense, edit an existing entry, "
            "or remove one? You can say something like ‘change the clothes expense to $35’.",
            None,
        )

    if conversation.last_logged_expense and (_is_delete_reference(text) or _is_change_reference(text)):
        expense = conversation.last_logged_expense
        description = expense.get("description") or expense.get("category")
        if _is_delete_reference(text):
            conversation.pending_mutation = {"action": "delete"}
            conversation.status = "confirming"
            return f"Should I delete the last expense, {expense.get('currency', DEFAULT_CURRENCY)} {float(expense['amount']):.2f} for {description}?", None
        new_amount = _extract_amount(text)
        assert new_amount is not None
        conversation.pending_mutation = {"action": "update", "amount": new_amount}
        conversation.status = "confirming"
        return f"Should I change that expense from {expense.get('currency', DEFAULT_CURRENCY)} {float(expense['amount']):.2f} to {expense.get('currency', DEFAULT_CURRENCY)} {new_amount:.2f}?", None

    if _is_current_expense_question(text):
        return _current_expense_reply(conversation.expenses or []), None

    query_slots = _query_slots(text)
    follow_up_query = _is_follow_up(text) and conversation.last_intent == "query_total" and any(query_slots.values())
    classifier_query = (
        _hint_is(hint, "query_total", CLASSIFIER_CONFIDENT)
        and not _amount_matches(text)
        and not _is_yes(text)
        and not _is_no(text)
    )
    if classifier_query and not (_is_query_total_request(text) or follow_up_query):
        conversation.trace_notes.append(f"Rules did not match; classifier routed to query_total ({hint[1]:.2f} >= {CLASSIFIER_CONFIDENT})")
    if _is_query_total_request(text) or follow_up_query or classifier_query:
        conversation.fail_count = 0
        if follow_up_query:
            query_slots = {
                "period": query_slots["period"] or (conversation.last_slots or {}).get("period"),
                "category": query_slots["category"] or (conversation.last_slots or {}).get("category"),
            }
            conversation.trace_notes.append("Inherited intent query_total from previous turn")
        conversation.last_intent = "query_total"
        conversation.last_slots = query_slots
        return _query_total_reply(conversation.expenses or [], query_slots), None

    if _is_expense_recall_question(text):
        return _expense_recall_reply(text, conversation.expenses or []), None

    if _is_today_spending_question(text):
        return _today_spending_reply(conversation.expenses or []), None

    if _is_spending_breakdown_question(text):
        return _spending_breakdown_reply(conversation.expenses or []), None

    if _is_spending_summary(text):
        total_text = _total_text(conversation.expenses or [])
        if conversation.expenses:
            return f"Your total spending is {total_text} across {len(conversation.expenses)} logged expense(s).", None
        return "You have no saved expenses in this session yet.", None

    if _is_history_question(text):
        return _history_reply(conversation.expenses or []), None

    if conversation.status in ("saved", "cancelled"):
        conversation.amount = conversation.currency = conversation.category = conversation.date = conversation.description = None
        conversation.pending_expenses = []
        conversation.status = "collecting"

    amount_matches = _amount_matches(text)
    amount = amount_matches[0][0] if amount_matches else None
    currency = _currency_for(text)
    category = _extract_category(text)
    expense_date = _extract_date(text)
    description = _extract_description(text, category)

    if expense_date and expense_date > date.today().isoformat():
        return "I can only log expenses up to today. Which date did you mean?", None

    if conversation.awaiting_correction and not any((amount is not None, category, expense_date, description)):
        if re.search(r"\bcategory\b", lowered):
            conversation.category = None
            conversation.awaiting_correction = False
            return _category_prompt(conversation.description), None
        if re.search(r"\bamount\b", lowered):
            conversation.amount = None
            conversation.awaiting_correction = False
            return _missing_prompt(conversation), None
        if re.search(r"\b(date|day)\b", lowered):
            conversation.date = None
            conversation.awaiting_correction = False
            return "What date should I use for this expense?", None
        if re.search(r"\b(description|note)\b", lowered):
            conversation.description = None
            conversation.awaiting_correction = False
            return "What description should I use?", None

    if not any((amount is not None, category, expense_date, description)) and not _is_yes(text) and not _is_no(text):
        small_talk = _small_talk_reply(text)
        if small_talk:
            conversation.fail_count = 0
            return small_talk, None
        if re.fullmatch(r"\s*(?:hi|hello|hey|good morning|good afternoon|good evening)[!. ]*\s*", lowered):
            conversation.fail_count = 0
            return _missing_prompt(conversation), None
        conversation.fail_count += 1
        if conversation.fail_count >= 2:
            conversation.trace_notes.append(f"{conversation.fail_count} misses in a row; showing the full help menu")
            return (
                "Sorry, I still didn’t catch an expense. Here is what I can do: log one (‘$12.50 on lunch’), "
                "total them (‘what did I spend today?’), list them (‘show my expenses’), "
                "or fix the last one (‘change it to 35’, ‘delete that’)."
            ), None
        if _hint_is(hint, "out_of_scope", CLASSIFIER_HINT_FLOOR):
            conversation.trace_notes.append(f"Classifier says out_of_scope ({hint[1]:.2f})")
            return (
                "I can only help with expenses, and I didn’t catch an expense to log. "
                "You can tell me the amount and what it was for, like ‘$12.50 on lunch.’"
            ), None
        return (
            "I didn’t catch an expense to log. You can tell me the amount and what it was for, "
            "like ‘$12.50 on lunch.’"
        ), None
    conversation.fail_count = 0

    if amount is not None:
        conversation.amount = amount
        conversation.currency = currency
    if category:
        conversation.category = category
    if expense_date:
        conversation.date = expense_date
    if description:
        conversation.description = description
    if conversation.awaiting_correction and any((amount is not None, category, expense_date, description)):
        conversation.awaiting_correction = False

    if conversation.pending_expenses and category:
        unresolved = next((item for item in conversation.pending_expenses if not item["category"]), None)
        if unresolved:
            unresolved["category"] = category
            conversation.status = "confirming"
            return _pending_prompt(conversation.pending_expenses), None

    if len(amount_matches) > 1 and conversation.status == "collecting":
        pending: list[dict[str, str | float]] = []
        for index, (item_amount, start, end) in enumerate(amount_matches):
            next_start = amount_matches[index + 1][1] if index + 1 < len(amount_matches) else len(text)
            segment = text[start:next_start].strip(" ,.;")
            item_category = _extract_category(segment)
            item_description = _extract_description(segment, item_category)
            pending.append({
                "amount": item_amount,
                "currency": _currency_for(segment) if re.search(r"\$|€|£|\b(?:usd|eur|gbp|dollars?|euros?|pounds?|bucks?)\b", segment, re.IGNORECASE) else currency,
                "category": _sanitize_category(item_category),
                "date": _extract_date(segment) or expense_date or date.today().isoformat(),
                "description": item_description or "",
            })
        missing_category = next((item for item in pending if not item["category"]), None)
        if missing_category:
            conversation.pending_expenses = pending
            conversation.description = str(missing_category["description"])
            return _category_prompt(conversation.description), None
        conversation.pending_expenses = pending
        conversation.status = "confirming"
        return _pending_prompt(pending), None

    if conversation.status == "confirming" and _is_yes(text):
        if conversation.pending_mutation:
            mutation = conversation.pending_mutation
            assert conversation.expenses is not None
            previous = mutation.get("target") or conversation.last_logged_expense
            index = _index_of(conversation.expenses, previous)
            conversation.pending_mutation = None
            if previous is None or index is None:
                conversation.status = "collecting"
                return "I couldn’t find that expense in your log anymore, so I changed nothing.", None
            action = str(mutation["action"])
            if action == "delete":
                conversation.expenses.pop(index)
                conversation.last_mutation = {"action": "delete", "expense": previous}
                conversation.last_logged_expense = conversation.expenses[-1] if conversation.expenses else None
                conversation.status = "saved"
                return "Deleted that expense from your log.", None
            updated = dict(previous)
            if action == "update":
                updated["amount"] = mutation["amount"]
            elif action == "description_update":
                updated["description"] = mutation["description"]
            else:
                updated["category"] = mutation["category"]
            conversation.expenses[index] = updated
            conversation.last_mutation = {"action": "update", "previous": previous, "updated": updated}
            conversation.last_logged_expense = updated
            conversation.status = "saved"
            if action == "update":
                return f"Updated the expense to {updated['currency']} {float(updated['amount']):.2f}.", None
            if action == "description_update":
                return f"Updated the expense description to {updated['description']}.", None
            return f"Renamed the expense category to {updated['category']}.", None
        if conversation.pending_expenses:
            expenses_to_save = conversation.pending_expenses
            assert conversation.expenses is not None
            conversation.expenses.extend(expenses_to_save)
            conversation.last_saved_expenses = list(expenses_to_save)
            conversation.pending_expenses = []
            conversation.last_intent = "expense_log"
            conversation.last_logged_expense = expenses_to_save[-1]
            conversation.status = "saved"
            return f"Saved {len(expenses_to_save)} expenses. Your logged total is " + _total_text(conversation.expenses) + ".", expenses_to_save[0]
        # allow the user to confirm and include a brief override for description
        desc_override_match = re.search(r"\b(?:under|as|make it|set it to|call it)\s+(.+)$", lowered)
        if desc_override_match:
            conversation.description = desc_override_match.group(1).strip(" .,!? ")[:80]
        assert conversation.amount is not None and conversation.category and conversation.date
        expense = _expense_dict(conversation)
        assert conversation.expenses is not None
        conversation.expenses.append(expense)
        conversation.last_saved_expenses = [expense]
        conversation.last_intent = "expense_log"
        conversation.last_logged_expense = expense
        conversation.status = "saved"
        description_text = f" for {conversation.description}" if conversation.description else ""
        return f"Saved {conversation.currency or DEFAULT_CURRENCY} {conversation.amount:.2f} under {conversation.category}{description_text}. Your logged total is " + _total_text(conversation.expenses) + ".", expense

    if conversation.status == "confirming" and _is_no(text):
        if not any((amount, category, expense_date, description)):
            conversation.status = "collecting"
            conversation.awaiting_correction = True
            return "What would you like to change: the amount, category, date, or description?", None
        conversation.status = "confirming"

    return _missing_prompt(conversation), None


_ORDINALS = {"first": 0, "oldest": 0, "earliest": 0, "second": 1, "last": -1, "latest": -1, "newest": -1, "recent": -1}
_UPDATE_VERB = re.compile(r"\b(update|edit|change|modify|correct|set|make|fix)\b")
_DELETE_VERB = re.compile(r"\b(delete|remove)\b")
_EXPENSE_NOUN = re.compile(r"\b(expense|expenses|entry|entries|record|records)\b")


def _category_and_term(text: str) -> tuple[str | None, str | None]:
    """The category named in text and the exact word used ("clothes" -> shopping, "clothes")."""
    lowered = text.lower()
    best: tuple[int, str, str] | None = None
    for category, terms in _CATEGORY_TERMS.items():
        for term in terms:
            match = re.search(rf"\b{re.escape(term)}\b", lowered)
            if match and (best is None or match.start() > best[0]):
                best = (match.start(), category, term)
    return (best[1], best[2]) if best else (None, None)


def _find_candidates(text: str, expenses: list[dict[str, str | float]]) -> tuple[list[dict[str, str | float]], str]:
    """Expenses the sentence points at, plus a human label for the filter ("transport")."""
    category, term = _category_and_term(text)
    target_date = _extract_date(text)
    found = [
        item for item in expenses
        if (not category or item.get("category") == category) and (not target_date or str(item.get("date")) == target_date)
    ]
    if term and term != category:                      # "clothes" narrows shopping down to the clothes row
        found = [item for item in found if term in str(item.get("description", "")).lower()] or found
    label = " ".join(part for part in (category, "expense", f"on {target_date}" if target_date else "") if part)
    return found, label


def _describe(item: dict[str, str | float]) -> str:
    what = item.get("description") or item.get("category")
    return f"{item.get('currency', DEFAULT_CURRENCY)} {float(item['amount']):.2f} for {what} on {item.get('date')}"


def _pick_candidate(text: str, candidates: list[dict[str, str | float]]) -> dict[str, str | float] | None:
    lowered = text.lower()
    for word, position in _ORDINALS.items():
        if re.search(rf"\b{word}\b", lowered) and -len(candidates) <= position < len(candidates):
            return candidates[position]
    for match in re.finditer(r"\d+(?:\.\d+)?", lowered):
        hits = [item for item in candidates if abs(float(item["amount"]) - float(match.group())) < 0.005]
        if len(hits) == 1:
            return hits[0]
    wanted = _extract_date(text)
    if wanted:
        hits = [item for item in candidates if str(item.get("date")) == wanted]
        if len(hits) == 1:
            return hits[0]
    return None


def _mutation_prompt(conversation: Conversation, action: str, target: dict[str, str | float], new_amount: float | None) -> str:
    conversation.pending_mutation = {"action": action, "target": target}
    conversation.status = "confirming"
    if action == "delete":
        return f"Should I delete {_describe(target)}?"
    if action == "description_update":
        conversation.pending_mutation["description"] = new_amount
        description = target.get("description") or target.get("category")
        return f"Should I update {description} to {new_amount}?"
    conversation.pending_mutation["amount"] = new_amount
    currency = target.get("currency", DEFAULT_CURRENCY)
    description = target.get("description") or target.get("category")
    return f"Should I update {description} from {currency} {float(target['amount']):.2f} to {currency} {float(new_amount or 0):.2f}?"


def _start_mutation(conversation: Conversation, text: str) -> str | None:
    """Update/delete a saved expense that the sentence describes ("update the transport expense to $13.50")."""
    lowered = text.lower()
    expenses = conversation.expenses or []
    has_noun = bool(_EXPENSE_NOUN.search(lowered))
    category, _ = _category_and_term(text)
    if _DELETE_VERB.search(lowered):
        if not (category or _extract_date(text)):
            return None                                      # "remove an entry": generic path asks for a target
        action, new_amount = "delete", None
    elif _UPDATE_VERB.search(lowered) and (has_noun or (category and re.search(r"\b(update|edit|modify|correct)\b", lowered))):
        amounts = _amount_matches(text)
        if len(amounts) != 1:
            return None                                      # no amount, or old->new handled elsewhere
        if conversation.status == "confirming" and conversation.amount is not None and not has_noun:
            return None                                      # a draft is being corrected, not a saved expense
        action, new_amount = "update", amounts[0][0]
    else:
        return None
    if not expenses:
        return "There are no saved expenses to change yet."
    candidates, label = _find_candidates(text, expenses)
    if not candidates:
        return f"I couldn’t find a {label} in your log, so I changed nothing."
    pick = candidates[0] if len(candidates) == 1 else _pick_candidate(text, candidates)
    if pick is not None:
        conversation.trace_notes.append(f"Resolved ‘{label}’ to 1 of {len(candidates)} saved expense(s)")
        return _mutation_prompt(conversation, action, pick, new_amount)
    conversation.pending_choice = {"action": action, "amount": new_amount, "candidates": candidates}
    conversation.trace_notes.append(f"‘{label}’ matched {len(candidates)} expenses; asking which one")
    options = "; ".join(_describe(item) for item in candidates)
    return f"I found {len(candidates)} matching expenses: {options}. Which one? Say its amount, like ‘the {float(candidates[0]['amount']):g} one’, or ‘the latest’."


def _index_of(expenses: list[dict[str, str | float]], target: dict[str, str | float] | None) -> int | None:
    """Position of target in the log: identity first, then equality (e.g. after a reload)."""
    if target is None:
        return None
    for index, item in enumerate(expenses):
        if item is target:
            return index
    for index in range(len(expenses) - 1, -1, -1):
        if expenses[index] == target:
            return index
    return None


def _total_text(expenses: list[dict[str, str | float]]) -> str:
    totals: dict[str, float] = {}
    for expense in expenses:
        currency = str(expense.get("currency", DEFAULT_CURRENCY))
        totals[currency] = totals.get(currency, 0.0) + float(expense["amount"])
    return ", ".join(f"{currency} {amount:.2f}" for currency, amount in sorted(totals.items()))


def _totals(expenses: list[dict[str, str | float]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for expense in expenses:
        currency = str(expense.get("currency", DEFAULT_CURRENCY))
        totals[currency] = round(totals.get(currency, 0.0) + float(expense["amount"]), 2)
    return totals


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/turn", response_model=TurnResponse)
def turn(request: TurnRequest) -> TurnResponse:
    turn_id = str(uuid4())
    conversation = _conversation_for(request.session_id)
    before_status = conversation.status
    predicted_intent, confidence, ranked_intents = classify(request.transcript)
    reply, expense = handle_turn(conversation, request.transcript, hint=(predicted_intent, confidence))
    saved_expenses = conversation.last_saved_expenses or []
    if saved_expenses:
        _save_expenses(request.session_id, saved_expenses)
        conversation.last_saved_expenses = []
    if conversation.last_mutation:
        mutation = conversation.last_mutation
        if mutation["action"] == "delete":
            _delete_saved_expense(request.session_id, mutation["expense"])
        elif mutation["action"] == "update":
            _update_saved_expense(request.session_id, mutation["previous"], mutation["updated"])
        conversation.last_mutation = None
    all_expenses = conversation.expenses or []
    totals = _totals(all_expenses)
    flags: list[str] = []
    if confidence < 0.55:
        flags.append("low_confidence")
    if "didn’t catch an expense" in reply or "didn't catch an expense" in reply:
        flags.append("fallback")
    if re.search(r"\b(no|wrong|not what i meant|that's not right)\b", request.transcript.lower()):
        flags.append("negative_feedback")
    decision_trace: list[dict[str, str | float]] = [
        {"step": "classifier", "intent": predicted_intent, "confidence": confidence},
        {"step": "ranked_intents", "candidates": ", ".join(item["intent"] for item in ranked_intents)},
        {"step": "state", "before": before_status, "after": conversation.status},
        {"step": "persistence", "saved_count": len(saved_expenses)},
    ]
    decision_trace.extend({"step": "context", "note": note} for note in conversation.trace_notes or [])
    _append_jsonl(TURN_LOG_PATH, {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "turn_id": turn_id,
        "session_id": request.session_id,
        "text": request.transcript,
        "predicted_intent": predicted_intent,
        "confidence": confidence,
        "last_intent": conversation.last_intent,
        "last_slots": conversation.last_slots or {},
        "flags": flags,
        "reply": reply,
        "status": conversation.status,
        "decision_trace": decision_trace,
    })
    return TurnResponse(reply=reply, status=conversation.status, expense=expense, total=totals.get(DEFAULT_CURRENCY, 0.0), totals=totals, expenses=all_expenses, saved_expenses=saved_expenses, turn_id=turn_id, confidence=confidence, decision_trace=decision_trace)


@app.get("/api/expenses/{session_id}", response_model=TurnResponse)
def expenses(session_id: str) -> TurnResponse:
    conversation = _conversation_for(session_id)
    totals = _totals(conversation.expenses or [])
    return TurnResponse(reply="", status=conversation.status, total=totals.get(DEFAULT_CURRENCY, 0.0), totals=totals, expenses=conversation.expenses or [])


@app.post("/api/corrections")
def correction(request: CorrectionRequest) -> dict[str, str]:
    _append_jsonl(CORRECTIONS_PATH, {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "turn_id": request.turn_id,
        "text": request.text,
        "intent": request.intent,
    })
    return {"status": "recorded"}


@app.post("/api/reset/{session_id}")
def reset(session_id: str) -> dict[str, str]:
    conversations.pop(session_id, None)
    _delete_expenses(session_id)
    # Without this marker, _read_last_turn_context() would resurrect the old last_intent/last_slots.
    _append_jsonl(TURN_LOG_PATH, {"timestamp": datetime.now().isoformat(timespec="seconds"), "session_id": session_id, "event": "reset"})
    return {"status": "reset"}

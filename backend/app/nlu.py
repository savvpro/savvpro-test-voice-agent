"""Hand-written NLU: rule-based intents plus date/time/name extraction. No ML models."""
import re
from datetime import date, timedelta

INTENTS = [
    ("human", r"\b(human|real person|operator|receptionist|someone else)\b"),
    ("goodbye", r"\b(bye|goodbye|that'?s all|hang up|never ?mind)\b"),
    ("repeat", r"\b(repeat|say that again|pardon|come again|what was that)\b"),
    ("cancel", r"\bcancel"),
    ("reschedule", r"\b(re-?schedul\w*|move (my|the)|postpone|change (my|the) appointment)"),
    ("book", r"\b(book|appointment|schedule|check-?up|see (a|the) doctor)\b"),
    ("yes", r"\b(yes|yeah|yep|correct|that'?s right|sure|okay|ok|confirm)\b"),
    ("no", r"\b(no|nope|wrong|incorrect|not right)\b"),
    ("greeting", r"\b(hi|hello|hey)\b"),
]
_WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MO = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_NUM = dict(one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9,
            ten=10, eleven=11, twelve=12)
_MER = r"(a\.?m\.?|p\.?m\.?)"
_STOP = {"looking", "calling", "trying", "want", "wanting", "here", "hoping", "going", "a", "an",
         "the", "ok", "okay", "fine", "good", "not", "sorry", "just", "also", "and", "at", "on",
         "for", "to", "booking", "cancelling", "need", "would", "like", "yes", "no"}


def detect_intent(text):
    t = text.lower()
    for name, pat in INTENTS:
        if re.search(pat, t):
            return name
    return None


def parse_date(text, today):
    """Returns an ISO date string or None."""
    t = text.lower()
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        try:
            return date(*map(int, m.groups())).isoformat()
        except ValueError:
            return None
    if "day after tomorrow" in t:
        return (today + timedelta(2)).isoformat()
    if "tomorrow" in t:
        return (today + timedelta(1)).isoformat()
    if re.search(r"\btoday\b", t):
        return today.isoformat()
    for i, w in enumerate(_WD):
        if re.search(rf"\b{w}\b", t):
            return (today + timedelta((i - today.weekday()) % 7 or 7)).isoformat()
    m = re.search(rf"\b({'|'.join(_MO)})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", t)
    if m:
        mo, day = _MO.index(m[1]) + 1, int(m[2])
        try:
            d = date(today.year, mo, day)
            return (d if d >= today else date(today.year + 1, mo, day)).isoformat()
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", t)
    if m:
        day, y, mo = int(m[1]), today.year, today.month
        if day < today.day:
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
        try:
            return date(y, mo, day).isoformat()
        except ValueError:
            return None
    return None


def parse_time(text, pending=None):
    """Returns ("ok", "HH:MM"), ("ambiguous", (hour, minute)) or None.

    `pending` is an earlier ambiguous (hour, minute); "evening"/"pm" etc. resolves it.
    """
    t = re.sub(r"\b(" + "|".join(_NUM) + r")\b", lambda m: str(_NUM[m[1]]), text.lower())
    if "noon" in t or "midday" in t:
        return "ok", "12:00"
    pm_w = re.search(r"\b(afternoon|evening|tonight|night)\b|\bp\.m\.|\bpm\b", t)
    am_w = re.search(r"\bmorning\b|\ba\.m\.|^\s*am\W*$", t)
    word_mer = "pm" if pm_w else "am" if am_w else None
    mer = None
    if m := re.search(r"\b(half|quarter) past (\d{1,2})\b", t):
        h, mn = int(m[2]), 30 if m[1] == "half" else 15
    elif m := re.search(rf"\b(\d{{1,2}}):(\d{{2}})\s*{_MER}?", t):
        h, mn, mer = int(m[1]), int(m[2]), m[3]
    elif m := re.search(rf"\b(\d{{1,2}})\s*(?:{_MER}|o'?clock)", t):
        h, mn, mer = int(m[1]), 0, m[2]
    elif m := re.search(r"\b(?:at|around|to|for|make it|say)\s+(\d{1,2})\b(?!\s*(?:st|nd|rd|th|people|persons|minutes))", t):
        h, mn = int(m[1]), 0
    elif pending and word_mer:
        (h, mn), mer = pending, word_mer
    else:
        return None
    mer = mer[0] + "m" if mer else word_mer
    if mn > 59 or h > 23 or (h > 12 and mer):
        return None
    if mer == "pm" and h < 12:
        h += 12
    elif mer == "am" and h == 12:
        h = 0
    elif mer is None and h < 13 and h != 0:
        if h in (9, 10, 11, 12):
            pass
        elif 1 <= h <= 4:
            h += 12
        else:
            return "ambiguous", (h, mn)
    return "ok", f"{h:02d}:{mn:02d}"


def parse_name(text, expecting=False):
    t = text.lower()
    m = re.search(r"\b(?:my name is|my name's|name is|this is|i am|i'm|it's)\s+([a-z]+)(?:\s+([a-z]+))?", t)
    if m:
        parts = [p for p in m.groups() if p]
        if parts[0] in _STOP:
            return None
        if len(parts) > 1 and parts[1] in _STOP:
            parts = parts[:1]
        return " ".join(p.title() for p in parts)
    if expecting:
        w = re.findall(r"[a-z']+", t)
        if 1 <= len(w) <= 3 and not (set(w) & _STOP) and not detect_intent(t):
            return " ".join(x.title() for x in w)
    return None

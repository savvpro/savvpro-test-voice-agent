"""English calendar grammar with consumed spans kept out of time parsing.

No locale-dependent parser or guessed numeric date ordering. Relative dates use
the supplied business clock; named dates without a year use its current year.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MONTH_NAMES = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
MONTHS = {name: index for index, name in enumerate(MONTH_NAMES, 1)}
MONTHS.update({name[:3]: index for index, name in enumerate(MONTH_NAMES, 1)})
MONTHS["sept"] = 9
MONTH_PATTERN = "(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + ")"

CARDINALS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth")
DAY_WORDS = {word: index for words in (CARDINALS, ORDINALS) for index, word in enumerate(words, 1)}
TENS = ((20, "twenty", "twentieth"), (30, "thirty", "thirtieth"), (40, "forty", "fortieth"),
        (50, "fifty", "fiftieth"), (60, "sixty", "sixtieth"), (70, "seventy", "seventieth"),
        (80, "eighty", "eightieth"), (90, "ninety", "ninetieth"))
for tens, prefix, ordinal in TENS:
    DAY_WORDS.update({prefix: tens, ordinal: tens})
    for index in range(1, 10):
        DAY_WORDS[f"{prefix} {CARDINALS[index - 1]}"] = tens + index
        DAY_WORDS[f"{prefix} {ORDINALS[index - 1]}"] = tens + index
WORD_DAY_PATTERN = "|".join(re.escape(word).replace(r"\ ", "[ -]") for word in sorted(DAY_WORDS, key=len, reverse=True))
DAY_CONTINUATION = "|".join((*CARDINALS, *ORDINALS))
DAY_PATTERN = rf"(?:\d{{1,2}}(?:st|nd|rd|th)?|{WORD_DAY_PATTERN})(?![ -](?:{DAY_CONTINUATION})\b)"
YEAR_SUFFIX = r"(?:(?:\s*,\s*|\s+)(?:(?:in|of|year)\s+)?(?P<year>\d{1,4})(?![\w:]))?"
CALENDAR_HELP = "I couldn't interpret that date. Please say the day, month, and four-digit year, for example October 28 2026."


@dataclass
class CalendarExtraction:
    values: set[str] = field(default_factory=set)
    remainder: str = ""
    issue: str | None = None


def day_number(value: str) -> int:
    word = value.replace("-", " ")
    if word in DAY_WORDS:
        return DAY_WORDS[word]
    return int(re.sub(r"(?:st|nd|rd|th)$", "", value))


def extract_dates(text: str, now: datetime, *, expecting_date: bool = False) -> CalendarExtraction:
    result = CalendarExtraction(remainder=text)

    def mask(start: int, end: int) -> None:
        result.remainder = result.remainder[:start] + " " * (end - start) + result.remainder[end:]

    def add(year: int, month: int, day: int) -> None:
        try:
            result.values.add(date(year, month, day).isoformat())
        except ValueError:
            result.issue = "That calendar date does not exist. Please check the day, month, and year."

    # Most specific calendar forms first; every matched span is masked, including
    # invalid dates, so their numbers cannot be misinterpreted as hours/minutes.
    numeric_patterns = (
        r"\b(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\b",
        r"\b(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})\b",
        r"\b(?P<year>\d{4})\s+(?P<month>\d{2})(?P<day>\d{2})\b",
        r"\b(?P<year>\d{4})\s+(?P<month>\d{1,2})\s+(?P<day>\d{1,2})\b",
    )
    for pattern in numeric_patterns:
        for match in re.finditer(pattern, result.remainder):
            add(int(match["year"]), int(match["month"]), int(match["day"]))
            mask(*match.span())

    named_patterns = (
        rf"\b(?P<year>\d{{4}})\s+(?P<month>{MONTH_PATTERN})\.?\s+(?:the\s+)?(?P<day>{DAY_PATTERN})\b",
        rf"\b(?:the\s+)?(?P<day>{DAY_PATTERN})\s+(?:of\s+)?(?P<month>{MONTH_PATTERN})\.?{YEAR_SUFFIX}\b",
        rf"\b(?P<month>{MONTH_PATTERN})\.?\s+(?:the\s+)?(?P<day>{DAY_PATTERN}){YEAR_SUFFIX}\b",
    )
    for pattern in named_patterns:
        for match in re.finditer(pattern, result.remainder):
            year = match["year"]
            # Do not silently default the year when the caller explicitly
            # supplied a spoken year outside this four-digit year grammar.
            spoken_year = re.match(r"\s+(?:nineteen|twenty|two thousand)\b(?:[ -]+(?:and|thousand|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen))*", result.remainder[match.end():]) if year is None else None
            if spoken_year or (year is not None and len(year) != 4):
                result.issue = "Please give the full four-digit year, for example October 28 2026."
            else:
                add(int(year) if year else now.year, MONTHS[match["month"]], day_number(match["day"]))
            mask(match.start(), match.end() + (spoken_year.end() if spoken_year else 0))

    for match in re.finditer(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b", result.remainder):
        result.issue = "Numeric dates can mean different things. Please say the month name or use YYYY-MM-DD."
        mask(*match.span())
    for match in re.finditer(r"\b\d{1,2}\s+\d{1,2}\s+\d{4}\b", result.remainder):
        result.issue = "Please say the month name or put the year first so the date order is clear."
        mask(*match.span())
    # Incomplete/garbled year-led claims are date questions, never clock times.
    # Consume only date-like tokens; a separate "at 5 PM" stays available.
    garbled_year = r"\b(?:19|20|21)\d{2}\b(?:\s+(?:\d{1,4}|zero|oh|to|two)\b)*"
    for match in re.finditer(garbled_year, result.remainder):
        result.issue = CALENDAR_HELP
        mask(*match.span())
    for match in re.finditer(rf"\b{MONTH_PATTERN}\b\.?", result.remainder):
        prefix = result.remainder[:match.start()]
        suffix = result.remainder[match.end():]
        modal_may = match[0] == "may" and re.match(r"\s+(?:i|we|you)\b", suffix)
        if not modal_may and (expecting_date or re.search(r"\b(?:on|in|of|for|at)\s*$", prefix)):
            result.issue = CALENDAR_HELP
            mask(*match.span())

    offsets = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
    for match in re.finditer(r"\bin (one|two|three|four|five|six|seven|\d{1,3}) days?\b", result.remainder):
        offset = int(offsets.get(match[1], match[1]))
        result.values.add((now.date() + timedelta(days=offset)).isoformat())
        mask(*match.span())

    explicit = set(result.values)
    relatives = (("day after tomorrow", 2), ("tomorrow", 1), ("today", 0), ("yesterday", -1))
    for phrase, offset in relatives:
        for match in re.finditer(rf"\b{phrase}\b", result.remainder):
            result.values.add((now.date() + timedelta(days=offset)).isoformat())
            mask(*match.span())
    for index, weekday in enumerate(WEEKDAYS):
        for match in re.finditer(rf"\b(?:next\s+)?{weekday}\b", result.remainder):
            alternative = re.search(r"\bor\s*$", result.remainder[:match.start()]) or re.match(r"\s+or\b", result.remainder[match.end():])
            if len(explicit) == 1 and not match[0].startswith("next ") and not alternative:
                if date.fromisoformat(next(iter(explicit))).weekday() != index:
                    result.issue = "That weekday doesn't match the calendar date. Please check which date you mean."
            else:
                offset = (index - now.weekday()) % 7
                if match[0].startswith("next ") and offset == 0:
                    offset = 7
                result.values.add((now.date() + timedelta(days=offset)).isoformat())
            mask(*match.span())
    if len(result.values) > 1:
        result.issue = "I heard more than one date. Please give one date for this appointment."
    if re.search(r"\b(?:next week|next month|weekend|sometime|later)\b", result.remainder) and not result.values:
        result.issue = "Which exact day? You can say tomorrow, a weekday, or a calendar date such as October 28 2026."
    negated_day = rf"\b(?:not|except|anything but|no longer)\s+(?:on\s+)?(?:today|tomorrow|yesterday|next|{'|'.join(WEEKDAYS)}|{MONTH_PATTERN}|\d{{4}}|\d{{1,2}}(?:st|nd|rd|th)?\s+of\s+{MONTH_PATTERN})\b"
    if result.values and re.search(negated_day, text):
        result.issue = "Which date should I use instead? Please give one positive date."
    return result

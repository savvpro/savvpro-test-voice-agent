"""Clock grammar consumes complete expressions before numeric extraction."""
import re
from dataclasses import dataclass

NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
NUMBER_PATTERN = "(?:" + "|".join(NUMBERS) + r"|\d{1,2})"

@dataclass
class ClockExtraction:
    time: str | None = None
    period: str | None = None
    issue: str | None = None


def extract_clock(clean: str, date_clean: str, *, expecting_time: bool = False) -> ClockExtraction:
    result = ClockExtraction()
    periods = set(re.findall(r"\b(morning|afternoon|evening)\b", clean))
    if len(periods) > 1:
        result.issue = "I heard multiple parts of the day. Please give one time with AM or PM."
    elif periods:
        result.period = next(iter(periods))
    # Convert spoken times before running one numeric grammar.
    time_text = re.sub(r"\bhalf past (" + NUMBER_PATTERN + r")\b", lambda m: f"{NUMBERS.get(m[1], m[1])}:30", date_clean)
    time_text = re.sub(r"\bquarter past (" + NUMBER_PATTERN + r")\b", lambda m: f"{NUMBERS.get(m[1], m[1])}:15", time_text)
    time_text = re.sub(r"\b(" + NUMBER_PATTERN + r") (thirty|fifteen|forty five)\b",
                       lambda m: f"{NUMBERS.get(m[1], m[1])}:{ {'thirty': '30', 'fifteen': '15', 'forty five': '45'}[m[2]]}", time_text)
    def quarter_to(match):
        hour = int(NUMBERS.get(match[1], match[1]))
        if not 1 <= hour <= 12:
            return match[0]
        suffix = match[2] or ""
        if hour == 12 and suffix:
            suffix = "am" if suffix == "pm" else "pm"
        return f"{hour - 1 or 12}:45{suffix}"

    time_text = re.sub(r"\bquarter to (" + NUMBER_PATTERN + r")\s*(am|pm)?\b", quarter_to, time_text)
    # Do not pull a plausible final hour out of an unsupported expression.
    minute_words = r"(?:half|quarter|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|\d{1,2})"
    unsupported = (
        rf"\b{minute_words}(?:[ -]five)? (?:minutes? )?(?:to|past|before|after) {NUMBER_PATTERN}\s*(?:am|pm)?\b"
        rf"|\b(?:a little|a bit|just|shortly) (?:before|after) {NUMBER_PATTERN}\s*(?:am|pm)?\b"
        rf"|\bbetween {NUMBER_PATTERN}\s*(?:am|pm)? and {NUMBER_PATTERN}\s*(?:am|pm)?\b"
        rf"|\b(?:not|anything but|except) (?:at )?{NUMBER_PATTERN}(?::\d{{2}})?\s*(?:am|pm)?\b"
    )
    if re.search(unsupported, time_text):
        result.issue = "Please give one exact, positive time, for example 4:45 PM."
        time_text = re.sub(unsupported, " ", time_text)
    for word, number in NUMBERS.items():
        time_text = re.sub(rf"\b{word}\b", str(number), time_text)
    time_text = time_text.replace("o'clock", "")
    # Speech recognition commonly omits a colon: "five 30 PM" -> "5:30 PM".
    # Never join alternatives such as "4 or 5 PM" or guess a missing digit.
    time_text = re.sub(r"(?<![\w:/-])(\d{1,2})\s+(\d{2})(?![\w:/-])", r"\1:\2", time_text)
    candidates: set[tuple[int, int, str]] = set()
    for match in re.finditer(r"(?<![\w/-])(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?![\w/-])", time_text):
        prefix = time_text[:match.start()]
        has_context = bool(match[2] or match[3] or re.search(r"\b(?:at|to|make it|for|around|about|approximately|roughly)\s*$", prefix) or expecting_time or re.fullmatch(r"\s*\d{1,2}\s*(?:instead)?\s*", time_text))
        if has_context:
            candidates.add((int(match[1]), int(match[2] or 0), match[3] or ""))
    times = set()
    for hour, minute, suffix in candidates:
        if minute > 59 or hour > 23 or (suffix and not 1 <= hour <= 12):
            result.issue = "That time is invalid. Please use a time like 5:30 PM or 17:30."
            continue
        if suffix:
            hour = hour % 12 + (12 if suffix == "pm" else 0)
        elif result.period:
            if not 1 <= hour <= 12:
                result.issue = "Please give one time with AM or PM."
                continue
            hour = hour % 12 + (0 if result.period == "morning" else 12)
        elif hour < 13 and hour != 0:
            result.issue = "Is that AM or PM? Please say the full time, for example 5 PM."
            continue
        times.add(f"{hour:02d}:{minute:02d}")
    if re.search(r"\bnoon\b", clean):
        times.add("12:00")
    if re.search(r"\bmidnight\b", clean):
        times.add("00:00")
    if len(times) > 1:
        result.issue = "I heard more than one time. Please give one time with AM or PM."
    elif times:
        result.time = next(iter(times))
        result.period = None
    if not result.time and not result.issue and re.search(r"\b(?:at|around|about|approximately|roughly)\s+(?:\d|thirteen\b|fourteen\b|fifteen\b|sixteen\b|seventeen\b|eighteen\b|nineteen\b|twenty\b|thirty\b|forty\b|fifty\b)", time_text):
        result.issue = "I couldn't interpret that time. Please say the full time, such as 4:30 PM."
    if re.search(r"\b(?:at|to)\s+\d{1,2}:\d{1}(?!\d)", time_text):
        result.issue = "Please give the complete time, for example 5:30 PM."
    if result.issue:
        result.time = None
    return result

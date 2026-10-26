import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from lost_property.domain.models import Extraction
from lost_property.domain.normalization import (
    BRANDS,
    CATEGORY_WORDS,
    COLOURS,
    LOCATIONS,
    contains,
    normalize,
)

MONTHS = {
    name: index
    for index, name in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        1,
    )
}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _date(text: str, today: date) -> tuple[str | None, bool]:
    if re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", text):
        return None, True
    value: date | None = None
    try:
        if match := re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text):
            value = date.fromisoformat(match[1])
        elif match := re.search(
            r"\b(\d{1,2})(?:st|nd|rd|th)? (" + "|".join(MONTHS) + r")(?: (\d{4}))?\b", text
        ):
            value = date(int(match[3] or today.year), MONTHS[match[2]], int(match[1]))
        elif contains(text, "yesterday"):
            value = today - timedelta(days=1)
        elif contains(text, "today"):
            value = today
        elif contains(text, "tomorrow"):
            return None, True
        else:
            for index, weekday in enumerate(WEEKDAYS):
                if contains(text, weekday):
                    days = (today.weekday() - index) % 7
                    if contains(text, "last") and days == 0:
                        days = 7
                    value = today - timedelta(days=days)
                    break
    except ValueError:
        return None, True
    return (value.isoformat(), False) if value and value <= today else (None, value is not None)


def extract(text: str, now: datetime, expected: str | None = None) -> Extraction:
    value = normalize(text)
    result = Extraction()
    if expected and any(
        contains(value, phrase)
        for phrase in (
            "don't know",
            "do not know",
            "not sure",
            "can't remember",
            "cannot remember",
            "unknown",
            "skip",
        )
    ):
        result.unknown.append(expected)
        return result
    # Ignore explicitly negated alternatives rather than taking the first colour/category.
    positive = re.sub(r"\b(?:not|isn't|wasn't|no)\s+(?:a\s+)?(?:dark\s+|light\s+)?\w+", " ", value)
    categories = [
        category
        for category, words in CATEGORY_WORDS.items()
        if any(contains(positive, word) for word in words)
    ]
    if len(categories) > 1:
        result.problem = "category"
    elif categories:
        result.values["category"] = categories[0]
    for name, options in (("colour", COLOURS), ("location", LOCATIONS), ("brand", BRANDS)):
        for option in options:
            if contains(positive, option):
                result.values[name] = "apple" if name == "brand" and option == "iphone" else option
                if any(contains(value, word) for word in ("maybe", "perhaps", "possibly", "think")):
                    result.uncertain.append(name)
                break
    found_date, invalid = _date(text.casefold(), now.astimezone(ZoneInfo("Asia/Karachi")).date())
    if invalid:
        result.problem = "lost_date"
    elif found_date:
        result.values["lost_date"] = found_date
    return result

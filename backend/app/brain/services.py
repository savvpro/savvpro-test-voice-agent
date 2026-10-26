"""Catalog mentions with local inclusion/exclusion scope."""
import re


PATTERNS = {
    "haircut": r"haircut|hair cut|classic cut|trim my hair|hair(?=\s+(?:and|plus|&)\s+(?:a\s+)?beard)",
    "beard": r"beard(?: trim)?",
    "combo": r"combo|both",
    "unsupported": r"color|colour|massage|nails|facial|dye|perm",
}
EXCLUSION = r"\b(?:without|no|not|excluding|skip|don't want|do not want|instead of|rather than)\s+(?:(?:a|an|the|any)\s+)?$"
SERVICE_HELP = "Which one service should I use: haircut, beard trim, or the combination?"


def extract_service(text: str) -> tuple[str | None, str | None]:
    positive: set[str] = set()
    negative: set[str] = set()
    for service, pattern in PATTERNS.items():
        for match in re.finditer(rf"\b(?:{pattern})\b", text):
            target = negative if re.search(EXCLUSION, text[:match.start()]) else positive
            target.add(service)
    if "unsupported" in positive:
        return None, "We offer haircuts, beard trims, or the combination. Which would you like?"
    if positive & negative or "combo" in negative:
        return None, SERVICE_HELP
    requested = positive & {"haircut", "beard"}
    if "combo" in positive:
        requested.update(("haircut", "beard"))
    requested -= negative
    if not requested:
        return (None, SERVICE_HELP) if negative & {"haircut", "beard", "combo"} else (None, None)
    if len(requested) == 2:
        if re.search(r"\bor\b", text):
            return None, SERVICE_HELP
        return "combo", None
    return next(iter(requested)), None

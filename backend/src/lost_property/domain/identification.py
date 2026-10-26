from lost_property.domain.models import FoundItem
from lost_property.domain.normalization import contains, normalize


def identify(details: str, candidates: list[FoundItem]) -> str | None:
    value = normalize(details)
    if any(
        contains(value, word) for word in ("not", "no", "maybe", "perhaps", "possibly", "unsure")
    ):
        return None
    matches = [
        item.id
        for item in candidates
        if any(
            any(contains(value, normalize(phrase)) for phrase in variants)
            for variants in item.private_facts
        )
    ]
    return matches[0] if len(matches) == 1 else None

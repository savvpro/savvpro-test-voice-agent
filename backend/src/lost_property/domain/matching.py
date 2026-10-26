from datetime import date

from lost_property.domain.models import Candidate, Fields, FoundItem
from lost_property.domain.normalization import descriptive_tokens


def rank(fields: Fields, inventory: list[FoundItem]) -> list[Candidate]:
    candidates: list[Candidate] = []
    known = fields.model_dump()
    for name in (*fields.uncertain, *fields.unknown):
        known[name] = None
    query = descriptive_tokens(fields.description)
    for item in inventory:
        if item.status != "available":
            continue
        if known["category"] and known["category"] != item.category:
            continue
        lost = (
            date.fromisoformat(fields.lost_date)
            if known["lost_date"] and fields.lost_date
            else None
        )
        if lost and item.found_date < lost:
            continue
        signals: dict[str, float] = {"description": 0}
        if known["category"]:
            signals["category"] = 30
        document = descriptive_tokens(item.description)
        if query and document:
            signals["description"] = round(25 * len(query & document) / len(query | document), 2)
        for name, weight in (("colour", 15), ("brand", 10)):
            actual = getattr(item, name)
            if known[name] and actual:
                signals[name] = weight if known[name] == actual else -weight
        if known["location"] and fields.location == item.location:
            signals["location"] = 10
        if lost:
            elapsed = (item.found_date - lost).days
            signals["lost_date"] = 10 if elapsed == 0 else 5 if elapsed <= 2 else 0
        candidates.append(
            Candidate(
                item_id=item.id, score=max(0, min(100, sum(signals.values()))), signals=signals
            )
        )
    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.item_id))

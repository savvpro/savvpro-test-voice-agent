"""
Mock availability for the Clinic Appointment Voice Agent.
Generates 4 weeks of Mon–Fri slots from today's date.
No external dependencies.
"""

from datetime import date, timedelta

# { "YYYY-MM-DD": { "HH:MM": [doctor, ...] } }
# "any" in the doctor list means any/no-preference callers are accepted.
MOCK_AVAILABILITY: dict[str, dict[str, list[str]]] = {}


def _build() -> dict[str, dict[str, list[str]]]:
    """Generate availability grid for the next 28 weekdays from today."""
    today = date.today()
    slot_templates = [
        ("09:00", ["any", "Dr. Khan", "Dr. Smith"]),
        ("10:00", ["any", "Dr. Patel"]),
        ("11:00", ["Dr. Khan", "Dr. Ali"]),
        ("14:00", ["any", "Dr. Smith", "Dr. Ali"]),
        ("15:00", ["any", "Dr. Khan"]),
        ("16:00", ["Dr. Patel", "Dr. Smith"]),
    ]
    avail: dict[str, dict[str, list[str]]] = {}
    for offset in range(0, 57):          # include today and upcoming days
        d = today + timedelta(days=offset)
        avail[d.strftime("%Y-%m-%d")] = {
            t: list(docs) for t, docs in slot_templates
        }
        if len(avail) >= 28:
            break
    return avail


MOCK_AVAILABILITY = _build()


def is_available(date_str: str, time_str: str, doctor: str) -> bool:
    """Return True if *date_str* / *time_str* / *doctor* is in the mock grid."""
    slot_doctors = MOCK_AVAILABILITY.get(date_str, {}).get(time_str)
    if slot_doctors is None:
        return False
    if doctor == "any":
        return True
    return doctor in slot_doctors or "any" in slot_doctors


def find_alternatives(doctor: str, n: int = 3) -> list[dict]:
    """Return up to *n* available {date, time} dicts for *doctor*."""
    results: list[dict] = []
    for date_str, times in sorted(MOCK_AVAILABILITY.items()):
        for time_str, doctors in sorted(times.items()):
            if doctor == "any" or doctor in doctors or "any" in doctors:
                results.append({"date": date_str, "time": time_str})
                if len(results) >= n:
                    return results
    return results


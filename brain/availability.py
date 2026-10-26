from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

WORK_START = 9 * 60
WORK_END = 17 * 60
TAKEN_SLOTS = {
    ("2030-01-15", "14:00"),
    ("2030-01-15", "15:30"),
    ("2030-01-16", "13:00"),
}
BOOKINGS: List[Dict[str, str]] = []


def _minutes(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def _valid_slot(time: str) -> bool:
    minutes = _minutes(time)
    return WORK_START <= minutes < WORK_END and minutes % 30 == 0


def is_working_slot(time: str) -> bool:
    return _valid_slot(time)


def is_free(date: str, time: str) -> bool:
    return _valid_slot(time) and (date, time) not in TAKEN_SLOTS


def nearest_free(date: str, time: str) -> List[str]:
    requested = _minutes(time)
    candidates = [
        f"{minutes // 60:02d}:{minutes % 60:02d}"
        for minutes in range(WORK_START, WORK_END, 30)
        if minutes != requested and is_free(date, f"{minutes // 60:02d}:{minutes % 60:02d}")
    ]
    candidates.sort(key=lambda item: (abs(_minutes(item) - requested), _minutes(item)))
    if len(candidates) >= 2:
        return candidates[:2]

    current = datetime.strptime(date, "%Y-%m-%d").date() + timedelta(days=1)
    while True:
        if current.weekday() < 5:
            next_day = [
                f"{minutes // 60:02d}:{minutes % 60:02d}"
                for minutes in range(WORK_START, WORK_END, 30)
                if is_free(current.isoformat(), f"{minutes // 60:02d}:{minutes % 60:02d}")
            ]
            candidates.extend(next_day)
            if len(candidates) >= 2:
                return candidates[:2]
        current += timedelta(days=1)


def book(date: str, time: str, patient_name: str, phone: str, reason: str) -> Dict[str, str]:
    if not is_free(date, time):
        raise ValueError("The requested appointment slot is not available")
    TAKEN_SLOTS.add((date, time))
    booking = {"date": date, "time": time, "patient_name": patient_name,
               "phone": phone, "reason": reason}
    BOOKINGS.append(booking)
    return dict(booking)

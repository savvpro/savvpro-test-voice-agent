from datetime import datetime, time, timedelta

WEEKDAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

OPENING_HOURS = {
    0: (time(9, 0), time(17, 0)),
    1: (time(9, 0), time(17, 0)),
    2: (time(9, 0), time(17, 0)),
    3: (time(9, 0), time(17, 0)),
    4: (time(9, 0), time(17, 0)),
    5: (time(9, 0), time(17, 0)),
    6: None,  # Sunday: closed
}

APPOINTMENT_DURATION = timedelta(minutes=30)
SEARCH_LIMIT = timedelta(days=14)  # how far ahead we look for free slots

# Fake data. Prices in PKR.
SERVICES = {
    "checkup": 1500,
    "cleaning": 3000,
    "filling": 4000,
    "root canal": 12000,
    "wisdom tooth extraction": 10000,
}


class SlotTakenError(Exception):
    """Raised when the requested slot is already booked."""


def is_within_opening_hours(appointment_time: datetime) -> bool:
    opening_hours = OPENING_HOURS.get(appointment_time.weekday())
    if opening_hours is None:
        return False

    open_time, close_time = opening_hours
    appointment_starts = appointment_time.time()
    appointment_ends = (appointment_time + APPOINTMENT_DURATION).time()
    return (
        open_time <= appointment_starts < close_time
        and open_time <= appointment_ends <= close_time
    )


class ClinicCalendar:
    def __init__(self) -> None:
        self.booked_slots: dict[datetime, dict] = {}

    def is_on_grid(self, start_time: datetime) -> bool:
        return (
            start_time.minute % 30 == 0
            and start_time.second == 0
            and start_time.microsecond == 0
        )

    def is_taken(self, start_time: datetime) -> bool:
        return start_time in self.booked_slots

    def book(
        self,
        start_time: datetime,
        patient_name: str,
        patient_phone_number: str,
        service: str,
    ) -> None:
        # Check everything first, store last.
        if not self.is_on_grid(start_time):
            raise ValueError("Appointment time must be on the 30-minute grid.")
        if not is_within_opening_hours(start_time):
            raise ValueError("Appointment time is outside opening hours.")
        if service not in SERVICES:
            raise ValueError("Invalid service selected.")
        if self.is_taken(start_time):
            raise SlotTakenError("This time slot is already taken.")

        self.booked_slots[start_time] = {
            "patient_name": patient_name,
            "patient_phone_number": patient_phone_number,
            "service": service,
        }

    def _round_up_to_grid(self, moment: datetime) -> datetime:
        """Return the first grid time at or after `moment`."""
        rounded = moment.replace(second=0, microsecond=0)
        leftover = rounded.minute % 30
        if leftover or rounded != moment:
            rounded += timedelta(minutes=30 - leftover)
        return rounded

    def next_free_slots(self, start_time: datetime, count: int = 3) -> list[datetime]:
        slots: list[datetime] = []
        candidate = self._round_up_to_grid(start_time)
        limit = start_time + SEARCH_LIMIT

        while len(slots) < count and candidate < limit:
            if is_within_opening_hours(candidate) and not self.is_taken(candidate):
                slots.append(candidate)
            candidate += APPOINTMENT_DURATION  # always move forward

        return slots
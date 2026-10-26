"""Single-chair scheduling, validated against the injected business clock."""
import secrets
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brain.engine import BookingError
from app.catalog import CLOSE_HOUR, OPEN_HOUR, SERVICES
from app.config import Settings
from app.db import Appointment
from app.schemas import AppointmentView, Entities


class Bookings:
    def __init__(self, session: Session, settings: Settings, now: datetime):
        self.session = session
        self.settings = settings
        if now.tzinfo is None:
            raise ValueError("The booking clock must be timezone-aware.")
        self.now = now

    def view(self, appointment: Appointment) -> AppointmentView:
        zone = self.settings.zone
        return AppointmentView(
            reference=appointment.reference, service=appointment.service,
            service_name=SERVICES[appointment.service].name, customer_name=appointment.customer_name,
            starts_at=datetime.fromtimestamp(appointment.starts_at, timezone.utc).astimezone(zone).isoformat(),
            ends_at=datetime.fromtimestamp(appointment.ends_at, timezone.utc).astimezone(zone).isoformat(),
            timezone=self.settings.business_timezone, status=appointment.status, version=appointment.version,
        )

    def get(self, reference: str) -> Appointment:
        appointment = self.session.get(Appointment, reference.upper())
        if appointment is None:
            raise BookingError("I couldn't find that booking reference.", "reference")
        return appointment

    def lookup(self, reference: str) -> AppointmentView:
        return self.view(self.get(reference))

    def day(self, value: str | None) -> date:
        try:
            result = date.fromisoformat(value or "")
        except ValueError:
            raise BookingError("Please provide a valid date in YYYY-MM-DD format.", "date")
        today = self.now.astimezone(self.settings.zone).date()
        if result < today:
            raise BookingError(f"{result.isoformat()} is in the past. Please choose a future date.", "date")
        if result > today + timedelta(days=180):
            raise BookingError("Bookings are available up to 180 days ahead.", "date")
        if result.weekday() == 6:
            raise BookingError("Northline Studio is closed on Sunday. Please choose Monday through Saturday.", "date")
        return result

    def interval(self, entities: Entities) -> tuple[int, int]:
        if entities.service not in SERVICES:
            raise BookingError("Choose a haircut, beard trim, or the combination.", "service")
        day = self.day(entities.date)
        try:
            clock_time = time.fromisoformat(entities.time or "")
            if clock_time.tzinfo is not None or clock_time.second or clock_time.microsecond:
                raise ValueError
        except ValueError:
            raise BookingError("Please provide an exact time such as 5 PM.", "time")
        local = datetime.combine(day, clock_time, self.settings.zone)
        # Reject nonexistent and repeated wall times in DST zones instead of guessing.
        roundtrip = local.astimezone(timezone.utc).astimezone(self.settings.zone)
        if roundtrip.replace(tzinfo=None) != local.replace(tzinfo=None) or local.utcoffset() != local.replace(fold=1).utcoffset():
            raise BookingError("That local time is ambiguous or does not exist because of a clock change. Choose a different time.", "time")
        duration = SERVICES[entities.service].minutes
        end = local + timedelta(minutes=duration)
        if local < self.now.astimezone(self.settings.zone):
            raise BookingError("That time is in the past. Please choose a later time.", "time")
        if clock_time < time(OPEN_HOUR) or end.time() > time(CLOSE_HOUR) or end.date() != day:
            raise BookingError(f"The full {duration}-minute service must fit between 10 AM and 7 PM.", "time")
        return int(local.timestamp()), int(end.timestamp())

    def check(self, entities: Entities, excluding: str | None = None) -> None:
        starts, ends = self.interval(entities)
        query = select(Appointment.reference).where(
            Appointment.status == "confirmed", Appointment.starts_at < ends, Appointment.ends_at > starts,
        )
        if excluding:
            query = query.where(Appointment.reference != excluding)
        if self.session.scalar(query.limit(1)):
            raise BookingError("That slot is already taken. Please choose another time.", "time")

    def slots(self, entities: Entities, excluding: str | None = None) -> list[str]:
        day = self.day(entities.date)
        if entities.service not in SERVICES:
            raise BookingError("Choose a service first.", "service")
        if entities.time:
            try:
                self.check(entities, excluding)
                return [entities.time]
            except BookingError:
                return []
        slots = []
        for minutes in range(OPEN_HOUR * 60, CLOSE_HOUR * 60, 10):
            h, m = divmod(minutes, 60)
            if entities.period == "morning" and h >= 12:
                continue
            if entities.period == "afternoon" and not 12 <= h < 17:
                continue
            if entities.period == "evening" and h < 17:
                continue
            value = f"{h:02d}:{m:02d}"
            if entities.time and value != entities.time:
                continue
            candidate = entities.model_copy(update={"date": day.isoformat(), "time": value})
            try:
                self.check(candidate, excluding)
            except BookingError:
                continue
            slots.append(value)
        return slots

    def create(self, entities: Entities) -> AppointmentView:
        self.check(entities)
        if not entities.name or not 2 <= len(entities.name) <= 80:
            raise BookingError("A customer name is required.", "name")
        starts, ends = self.interval(entities)
        reference = "NL-" + secrets.token_hex(4).upper()
        while self.session.get(Appointment, reference):
            reference = "NL-" + secrets.token_hex(4).upper()
        appointment = Appointment(reference=reference, service=entities.service,
                                  customer_name=entities.name, starts_at=starts, ends_at=ends,
                                  status="confirmed", version=1)
        self.session.add(appointment)
        self.session.flush()
        return self.view(appointment)

    def current(self, reference: str, version: int) -> Appointment:
        appointment = self.get(reference)
        if appointment.status != "confirmed":
            raise BookingError("That appointment has already been cancelled.", "reference")
        if appointment.version != version:
            raise BookingError("That appointment changed in another session. Give its reference again to review the latest details.", "reference")
        if appointment.starts_at < int(self.now.timestamp()):
            raise BookingError("An appointment that has started cannot be changed.", "reference")
        return appointment

    def reschedule(self, entities: Entities, version: int) -> AppointmentView:
        appointment = self.current(entities.reference, version)
        self.check(entities, excluding=appointment.reference)
        starts, ends = self.interval(entities)
        if not entities.name or not 2 <= len(entities.name) <= 80:
            raise BookingError("A customer name is required.", "name")
        # Domain errors are caught by the engine, so finish validation before
        # making any ORM object dirty inside the surrounding turn transaction.
        appointment.starts_at, appointment.ends_at = starts, ends
        appointment.service = entities.service
        appointment.customer_name = entities.name
        appointment.version += 1
        self.session.flush()
        return self.view(appointment)

    def cancel(self, reference: str, version: int) -> AppointmentView:
        appointment = self.current(reference, version)
        appointment.status = "cancelled"
        appointment.version += 1
        self.session.flush()
        return self.view(appointment)

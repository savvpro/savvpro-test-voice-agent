
from datetime import date, datetime, timedelta
from pathlib import Path
import re
import subprocess
import sys


class ReservationAssistant:
    """Rule-based TableTalk assistant with eight physical tables."""

    TABLE_COUNT = 8
    BOOKING_MINUTES = 30

    def __init__(self):
        self.reservations = []
        self.next_reference = 1001

        # Bookings can start every 30 minutes from noon to 11:30 PM.
        self.available_times = {
            "%02d:%02d" % (hour, minute)
            for hour in range(12, 24)
            for minute in (0, 30)
        }

        self.active_reference = None
        self.pending_action = None
        self.pending_reference = None
        self.pending_change_field = None
        self.screen_notice = ""
        self.last_reply = ""

        self.reset()

    def reset(self):
        """Reset the conversation without deleting confirmed bookings."""
        self.slots = {
            "date": None,
            "party_size": None,
            "time": None,
            "name": None,
        }

        self.state = "collecting"
        self.active_reference = None
        self.pending_action = None
        self.pending_reference = None
        self.pending_change_field = None
        self.screen_notice = ""

        self.last_reply = (
            "Welcome to TableTalk Reservations. "
            "What day would you like to visit?"
        )

    # ---------------------------------------------------------
    # Parsing
    # ---------------------------------------------------------

    def _parse_date(self, text):
        value = text.lower().strip().replace(",", " ")
        value = re.sub(
            r"\b(\d{1,2})(st|nd|rd|th)\b",
            r"\1",
            value
        )
        value = re.sub(r"\s+", " ", value)

        today = date.today()

        if re.search(r"\btoday\b", value):
            return today

        if re.search(r"\btomorrow\b", value):
            return today + timedelta(days=1)

        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        for day_name, weekday in weekdays.items():
            if re.search(r"\b" + day_name + r"\b", value):
                delta = (weekday - today.weekday()) % 7

                if "next " in value:
                    delta += 7
                elif delta == 0:
                    delta = 7

                return today + timedelta(days=delta)

        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d %B %Y",
            "%d %b %Y",
            "%B %d %Y",
            "%b %d %Y",
            "%d %B",
            "%d %b",
            "%B %d",
            "%b %d",
            "%B %d %y",
            "%b %d %y",
            "%d %B %y",
            "%d %b %y",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt).date()

                if "%Y" not in fmt and "%y" not in fmt:
                    parsed = parsed.replace(year=today.year)

                    if parsed < today:
                        parsed = parsed.replace(
                            year=today.year + 1
                        )

                return parsed

            except ValueError:
                continue

        return None

    def _parse_time(self, text):
        value = text.lower().replace(".", "").strip()

        # For change requests, use the new value after the last "to".
        # Example: "change time from 2 PM to 4:00".
        if re.search(r"\bto\b", value):
            value = re.split(r"\bto\b", value)[-1].strip()

        # Explicit AM/PM: 5 PM, 5:30 PM, 12 AM.
        match = re.search(
            r"\b(1[0-2]|0?[1-9])"
            r"(?::([0-5]\d))?\s*(am|pm)\b",
            value
        )

        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            suffix = match.group(3)

            if suffix == "pm" and hour != 12:
                hour += 12
            elif suffix == "am" and hour == 12:
                hour = 0

            return "%02d:%02d" % (hour, minute)

        # Explicit 24-hour time: 17:00, 23:30.
        match = re.search(
            r"\b([01]\d|2[0-3]):([0-5]\d)\b",
            value
        )

        if match:
            return "%02d:%02d" % (
                int(match.group(1)),
                int(match.group(2))
            )

        # Bare clock time: 5:00 or 7:30 means PM by default.
        match = re.search(
            r"\b(1[0-2]|0?[1-9]):([0-5]\d)\b",
            value
        )

        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))

            if 1 <= hour <= 11:
                hour += 12

            return "%02d:%02d" % (hour, minute)

        # Bare hour: 5 means 5 PM.
        match = re.fullmatch(
            r"\s*(1[0-2]|0?[1-9])\s*",
            value
        )

        if match:
            hour = int(match.group(1))

            if 1 <= hour <= 11:
                hour += 12

            return "%02d:00" % hour

        return None

    def _parse_party_size(self, text, allow_bare=False):
        value = text.lower().strip()

        # Avoid interpreting a clock time as a party size.
        if self._parse_time(value) is not None:
            if re.search(
                r"\b(am|pm|a\.m\.|p\.m\.)\b",
                value
            ) or re.search(r"\b\d{1,2}:\d{2}\b", value):
                if not re.search(
                    r"\b(people|persons|guests|of us)\b",
                    value
                ):
                    return None

        words = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }

        # "There will be four people", "party of two".
        word_match = re.search(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b",
            value
        )

        if word_match:
            return words[word_match.group(1)]

        match = re.search(
            r"\b(?:for|party of|table for|there will be)"
            r"\s*(\d{1,2})\b",
            value
        )

        if not match:
            match = re.search(
                r"\b(\d{1,2})\s*"
                r"(?:people|persons|guests|of us)\b",
                value
            )

        if match:
            return int(match.group(1))

        # An isolated number is accepted only when party size is requested.
        if allow_bare:
            match = re.fullmatch(r"\s*(\d{1,2})\s*", value)

            if match:
                return int(match.group(1))

        return None

    def _extract_name(self, text):
        patterns = [
            r"\bmy name is\s+([A-Za-z][A-Za-z '\-]{0,39})",
            r"\bname is\s+([A-Za-z][A-Za-z '\-]{0,39})",
            r"\bunder the name\s+([A-Za-z][A-Za-z '\-]{0,39})",
            r"\bwrite name\s+([A-Za-z][A-Za-z '\-]{0,39})",
            r"\bi am\s+([A-Za-z][A-Za-z '\-]{0,39})",
            r"\bi'm\s+([A-Za-z][A-Za-z '\-]{0,39})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                name = match.group(1).strip(" .,!?:;")

                if name.lower() not in {
                    "your name",
                    "the name",
                    "not sure",
                }:
                    return name

        cleaned = text.strip(" .,!?:;")
        invalid_names = {
            "name",
            "write name",
            "your name",
            "the name",
            "change date",
            "change time",
            "change my timing",
            "cancel booking",
            "cancel the booking",
            "book another",
            "another booking",
            "yes",
            "no",
        }

        if (
            1 <= len(cleaned.split()) <= 3
            and cleaned.replace(" ", "").replace("-", "").isalpha()
            and cleaned.lower() not in invalid_names
        ):
            return cleaned

        return None

    def _format_time(self, value):
        parsed = datetime.strptime(value, "%H:%M")
        return parsed.strftime("%I:%M %p").lstrip("0")

    def _extract_reference(self, text):
        match = re.search(r"\bTT\s*[-#]?\s*(\d+)\b", text, re.I)

        if match:
            return "TT" + match.group(1)

        # Allow a table ID such as T1, but resolve it only if unambiguous.
        match = re.search(r"\bT\s*[-#]?\s*([1-8])\b", text, re.I)

        if match:
            return "T" + match.group(1)

        # A bare numeric reservation reference, e.g. 1001.
        match = re.fullmatch(r"\s*(\d{4,})\s*", text)

        if match:
            return "TT" + match.group(1)

        return None

    # ---------------------------------------------------------
    # Table and availability logic
    # ---------------------------------------------------------

    def _time_minutes(self, value):
        parsed = datetime.strptime(value, "%H:%M")
        return parsed.hour * 60 + parsed.minute

    def _table_is_free(
        self,
        table_id,
        day,
        time,
        exclude_reference=None
    ):
        requested_start = self._time_minutes(time)
        requested_end = requested_start + self.BOOKING_MINUTES

        for booking in self.reservations:
            if booking["reference"] == exclude_reference:
                continue

            if booking["table_id"] != table_id:
                continue

            if booking["date"] != day:
                continue

            booked_start = self._time_minutes(booking["time"])
            booked_end = booked_start + self.BOOKING_MINUTES

            # Overlap test: a table can be reused when the previous
            # 30-minute reservation has ended.
            if (
                requested_start < booked_end
                and booked_start < requested_end
            ):
                return False

        return True

    def _find_available_table(
        self,
        day,
        time,
        exclude_reference=None
    ):
        for number in range(1, self.TABLE_COUNT + 1):
            table_id = "T" + str(number)

            if self._table_is_free(
                table_id,
                day,
                time,
                exclude_reference
            ):
                return table_id

        return None

    def _available_slots(
        self,
        day,
        exclude_reference=None
    ):
        result = []

        for time in sorted(self.available_times):
            if self._find_available_table(
                day,
                time,
                exclude_reference
            ):
                result.append(time)

        return result

    def _show_available_slots(self, day, exclude_reference=None):
        slots = self._available_slots(day, exclude_reference)

        if slots:
            display = ", ".join(
                self._format_time(item) for item in slots
            )
        else:
            display = "No available slots on this date."

        self.screen_notice = (
            "Available time slots for %s: %s"
            % (day, display)
        )

    def _time_unavailable_reply(self, exclude_reference=None):
        day = self.slots["date"].isoformat()
        self._show_available_slots(day, exclude_reference)
        self.slots["time"] = None

        return (
            "Sorry, no table is available at that time. "
            "Please choose one of the available time slots "
            "shown on your screen."
        )

    def _next_reference(self):
        existing_numbers = []

        for booking in self.reservations:
            match = re.search(r"(\d+)$", booking["reference"])

            if match:
                existing_numbers.append(int(match.group(1)))

        if existing_numbers:
            self.next_reference = max(
                self.next_reference,
                max(existing_numbers) + 1
            )

        result = "TT" + str(self.next_reference)
        self.next_reference += 1
        return result

    # ---------------------------------------------------------
    # Create a booking
    # ---------------------------------------------------------

    def _make_booking(self):
        day = self.slots["date"].isoformat()
        time = self.slots["time"]

        table_id = self._find_available_table(day, time)

        if table_id is None:
            return self._time_unavailable_reply()

        booking = {
            "reference": self._next_reference(),
            "table_id": table_id,
            "date": day,
            "time": time,
            "end_time": self._format_time(
                (
                    datetime.strptime(time, "%H:%M")
                    + timedelta(minutes=self.BOOKING_MINUTES)
                ).strftime("%H:%M")
            ),
            "party_size": self.slots["party_size"],
            "name": self.slots["name"],
            "duration_minutes": self.BOOKING_MINUTES,
        }

        self.reservations.append(booking)
        self.active_reference = booking["reference"]
        self.state = "booked"
        self.screen_notice = ""

        return (
            "Your table is booked, %s! Reservation reference: %s. "
            "Table: %s. Party of %s on %s at %s for 30 minutes. "
            "Your table will be available again at %s. "
            "Thank you for choosing TableTalk."
            % (
                booking["name"],
                booking["reference"],
                booking["table_id"],
                booking["party_size"],
                booking["date"],
                self._format_time(booking["time"]),
                booking["end_time"],
            )
        )

    # ---------------------------------------------------------
    # Find, cancel, and update bookings
    # ---------------------------------------------------------

    def _find_booking(self, reference):
        exact = [
            booking for booking in self.reservations
            if booking["reference"].upper() == reference.upper()
        ]

        if exact:
            return exact[0], None

        # A physical table ID may have multiple reservations over time.
        if reference.upper().startswith("T"):
            matches = [
                booking for booking in self.reservations
                if booking["table_id"].upper() == reference.upper()
            ]

            if len(matches) == 1:
                return matches[0], None

            if len(matches) > 1:
                return None, (
                    "That table has multiple reservations. "
                    "Please provide the reservation reference, "
                    "for example TT1001."
                )

        return None, (
            "I couldn't find that reservation. "
            "Please check the reservation reference and try again."
        )

    def _start_cancel(self, text):
        self.pending_action = "cancel"
        self.pending_reference = None
        self.pending_change_field = None

        reference = self._extract_reference(text)

        if reference:
            return self._process_reference(reference)

        return (
            "Please provide your reservation reference or table ID "
            "(for example, TT1001). I will ask you to confirm before "
            "deleting the booking."
        )

    def _process_reference(self, reference):
        booking, error = self._find_booking(reference)

        if error:
            return error

        if booking is None:
            return (
                "I couldn't find that reservation. "
                "Please provide a valid reservation reference."
            )

        self.pending_reference = booking["reference"]

        if self.pending_action == "cancel":
            return (
                "I found reservation %s for %s at table %s, on %s at %s. "
                "Do you confirm that you want to permanently cancel it? "
                "This action is irreversible. If you want a booking later, "
                "you will need to create a new one. Say YES to confirm "
                "or NO to keep the reservation."
                % (
                    booking["reference"],
                    booking["name"],
                    booking["table_id"],
                    booking["date"],
                    self._format_time(booking["time"]),
                )
            )

        if self.pending_action == "change":
            if self.pending_change_field is None:
                return (
                    "Reservation %s found. What would you like to update: "
                    "the time, date/day, or number of people?"
                    % booking["reference"]
                )

            return self._change_prompt(self.pending_change_field)

        return "Please tell me what you would like to do."

    def _change_prompt(self, field):
        prompts = {
            "time": "What new time would you like?",
            "date": "What new date would you like?",
            "party_size": (
                "What is the new number of people? "
                "Please choose between 1 and 8."
            ),
        }

        return prompts[field]

    def _detect_change_field(self, text):
        value = text.lower()

        if re.search(
            r"\b(people|persons|party size|guests|"
            r"number of people|number of guests|group size)\b",
            value
        ):
            return "party_size"

        if re.search(r"\b(time|timing|hour)\b", value):
            return "time"

        if re.search(r"\b(date|day)\b", value):
            return "date"

        return None

    def _start_change(self, text):
        self.pending_action = "change"
        self.pending_reference = None
        self.pending_change_field = self._detect_change_field(text)

        reference = self._extract_reference(text)

        if reference:
            return self._process_reference(reference)

        return (
            "Please provide the reservation reference or table ID "
            "(for example, TT1001) that you want to change."
        )

    def _apply_change(self, text):
        booking, error = self._find_booking(self.pending_reference)

        if error or booking is None:
            self.pending_action = None
            self.pending_reference = None
            self.pending_change_field = None

            return error or "I couldn't find that reservation."

        field = self.pending_change_field

        if field is None:
            field = self._detect_change_field(text)

            if field is None:
                return (
                    "Please tell me what to update: time, date/day, "
                    "or number of people."
                )

            self.pending_change_field = field

        if field == "time":
            new_time = self._parse_time(text)

            if new_time is None:
                return "I couldn't understand that time. Please try again."

            if new_time not in self.available_times:
                self.screen_notice = (
                    "The restaurant accepts bookings from 12:00 PM "
                    "to 11:30 PM, with 30-minute booking slots."
                )
                return (
                    "That time is outside our booking hours. "
                    "Please choose a time between 12 PM and 11:30 PM."
                )

            new_date = booking["date"]

        elif field == "date":
            new_date_value = self._parse_date(text)

            if new_date_value is None:
                return (
                    "I couldn't understand that date. "
                    "Please provide a date such as 2026-10-30."
                )

            if new_date_value < date.today():
                return (
                    "That date is in the past. "
                    "Please choose today or a future date."
                )

            new_date = new_date_value.isoformat()
            new_time = booking["time"]

        else:
            new_size = self._parse_party_size(text, allow_bare=True)

            if new_size is None:
                return (
                    "I couldn't understand the number of people. "
                    "Please try again."
                )

            if not 1 <= new_size <= 8:
                return (
                    "For this demo, party size must be between 1 and 8. "
                    "Please try again."
                )

            new_date = booking["date"]
            new_time = booking["time"]

        if field == "party_size":
            new_size = self._parse_party_size(text, allow_bare=True)
        else:
            new_size = booking["party_size"]

        table_id = self._find_available_table(
            new_date,
            new_time,
            exclude_reference=booking["reference"]
        )

        if table_id is None:
            self._show_available_slots(
                new_date,
                exclude_reference=booking["reference"]
            )
            return (
                "No table is available at that time. "
                "Your existing reservation has not been changed. "
                "Please choose an available slot shown on your screen."
            )

        # Update the existing record rather than creating a new booking.
        old_table_id = booking["table_id"]
        booking["date"] = new_date
        booking["time"] = new_time
        booking["end_time"] = self._format_time(
            (
                datetime.strptime(new_time, "%H:%M")
                + timedelta(minutes=self.BOOKING_MINUTES)
            ).strftime("%H:%M")
        )
        booking["party_size"] = new_size
        booking["table_id"] = table_id

        self.active_reference = booking["reference"]
        self.pending_action = None
        self.pending_reference = None
        self.pending_change_field = None
        self.screen_notice = ""
        self.state = "booked"

        return (
            "Reservation %s has been updated successfully. "
            "Table: %s. Party of %s on %s at %s. "
            "Duration: 30 minutes."
            % (
                booking["reference"],
                booking["table_id"],
                booking["party_size"],
                booking["date"],
                self._format_time(booking["time"]),
            )
        )

    def _finish_cancel(self, confirmed):
        booking, error = self._find_booking(self.pending_reference)

        if error or booking is None:
            self.pending_action = None
            self.pending_reference = None
            return error or "I couldn't find that reservation."

        if not confirmed:
            self.pending_action = None
            self.pending_reference = None

            return (
                "Cancellation stopped. Your reservation %s remains active."
                % booking["reference"]
            )

        reference = booking["reference"]
        table_id = booking["table_id"]

        self.reservations.remove(booking)

        if self.active_reference == reference:
            self.active_reference = None

        self.pending_action = None
        self.pending_reference = None
        self.pending_change_field = None
        self.screen_notice = ""

        # The table is now available for overlapping future requests.
        self.state = "collecting"

        return (
            "Reservation %s has been permanently cancelled. "
            "Table %s is now available for that time slot. "
            "This action cannot be undone. If you want a booking later, "
            "you must create a new reservation."
            % (reference, table_id)
        )

    # ---------------------------------------------------------
    # Main conversation handler
    # ---------------------------------------------------------

    def handle(self, user_text):
        text = user_text.strip()
        lower = text.lower()

        if not text:
            self.last_reply = (
                "I didn't catch that. Please say that again "
                "or type your answer."
            )
            return self.last_reply

        self.screen_notice = ""

        # Handle a pending cancellation confirmation first.
        # Accept natural spoken confirmations and allow update requests to
        # switch flows instead of remaining stuck at the confirmation prompt.
        if (
            self.pending_action == "cancel"
            and self.pending_reference
        ):
            confirmation = re.sub(r"[^a-z\s']", " ", lower)
            confirmation = re.sub(r"\s+", " ", confirmation).strip()

            if re.search(r"\b(change|modify|update|reschedule)\b", lower):
                self.pending_action = None
                self.pending_reference = None
                self.pending_change_field = None
                self.last_reply = self._start_change(text)
                return self.last_reply

            yes_answers = {
                "yes", "yes please", "yeah", "yep", "yup", "sure",
                "okay", "ok", "confirm", "confirm cancellation",
                "cancel it", "do it", "affirmative", "correct",
                "that's right", "that is right",
            }
            no_answers = {
                "no", "no thanks", "no thank you", "nope", "nah",
                "don't", "do not", "keep it", "keep the booking",
                "cancel nothing", "negative", "not now",
            }

            yes_intent = (
                confirmation in yes_answers
                or re.match(r"^(yes|yeah|yep|yup)\b", confirmation) is not None
                or re.search(
                    r"\b(i want to|please|go ahead and)\s+"
                    r"(cancel|delete|remove)\b|"
                    r"\b(cancel|delete|remove)\s+"
                    r"(the reservation|the booking|it)\b",
                    confirmation,
                ) is not None
            )
            no_intent = (
                confirmation in no_answers
                or re.match(r"^(no|nope|nah)\b", confirmation) is not None
                or re.search(
                    r"\b(i do not want to|i don't want to|"
                    r"do not|don't)\s+(cancel|delete|remove)\b|"
                    r"\b(keep|keep the reservation|keep the booking)\b",
                    confirmation,
                ) is not None
            )

            if yes_intent:
                self.last_reply = self._finish_cancel(True)
                return self.last_reply

            if no_intent:
                self.last_reply = self._finish_cancel(False)
                return self.last_reply

            self.last_reply = (
                "Please say 'yes, I want to cancel' to confirm, "
                "or 'no, I don't want to cancel' to keep the reservation."
            )
            return self.last_reply

        # Handle a new intent before requiring a reference for a pending action.
        # This prevents the conversation from getting stuck when the user
        # changes their mind and wants to start a new booking or another action.
        new_booking_intent = any(
            phrase in lower
            for phrase in (
                "book another",
                "another booking",
                "new booking",
                "start a new booking",
                "start over",
                "restart",
                "make another reservation",
                "i want to book another",
                "i want to do a booking",
                "i want to make a booking",
                "i want to book",
                "make a booking",
                "book a table",
                "new reservation",
                "create a reservation",
            )
        )

        if self.pending_action and not self.pending_reference:
            if new_booking_intent:
                self.reset()
                return self.last_reply

            if re.search(r"\b(cancel|cancellation|delete)\b", lower):
                self.last_reply = self._start_cancel(text)
                return self.last_reply

            if re.search(r"\b(change|modify|update|reschedule)\b", lower):
                self.last_reply = self._start_change(text)
                return self.last_reply

            reference = self._extract_reference(text)

            if not reference:
                self.last_reply = (
                    "Please provide the reservation reference, "
                    "for example TT1001. You can find it in the bookings "
                    "table on the screen. To start a new booking instead, "
                    "say 'I want to do a booking'."
                )
                return self.last_reply

            self.last_reply = self._process_reference(reference)
            return self.last_reply

        # If a change is pending, accept a field selection or new value.
        if self.pending_action == "change" and self.pending_reference:
            if self.pending_change_field is None:
                field = self._detect_change_field(text)

                if field is None:
                    self.last_reply = (
                        "What would you like to update: time, date/day, "
                        "or number of people?"
                    )
                    return self.last_reply

                self.pending_change_field = field
                self.last_reply = self._change_prompt(field)
                return self.last_reply

            self.last_reply = self._apply_change(text)
            return self.last_reply

        # Start a new booking without removing existing records.
        if any(
            phrase in lower
            for phrase in (
                "book another",
                "another booking",
                "new booking",
                "start a new booking",
                "start over",
                "restart",
                "make another reservation",
                "i want to book another",
                "i want to do a booking",
                "i want to make a booking",
                "i want to book",
                "make a booking",
                "book a table",
                "new reservation",
                "create a reservation",
            )
        ):
            self.reset()
            return self.last_reply

        # Cancellation intent: ask for a reference, then confirmation.
        if re.search(r"\b(cancel|cancellation|delete)\b", lower):
            self.last_reply = self._start_cancel(text)
            return self.last_reply

        # Change intent: ask for the reservation reference first.
        if re.search(
            r"\b(change|modify|update|reschedule)\b",
            lower
        ):
            self.last_reply = self._start_change(text)
            return self.last_reply

        # A confirmed booking should not be duplicated by casual input.
        if self.state == "booked":
            self.last_reply = (
                "Your reservation is confirmed. You can say "
                "'cancel booking', 'change time', 'change date', "
                "'change number of people', or 'book another'."
            )
            return self.last_reply

        # Collect new booking details in the required order.
        missing_before = self._find_missing()

        parsed_date = self._parse_date(text)
        parsed_party = self._parse_party_size(
            text,
            allow_bare=(missing_before == "party_size")
        )
        parsed_time = self._parse_time(text)

        # A bare number while asking for party size is not a time.
        if missing_before == "party_size" and parsed_party is not None:
            parsed_time = None

        if parsed_date is not None:
            if parsed_date < date.today():
                self.last_reply = (
                    "That date is in the past. "
                    "Please choose today or a future date."
                )
                return self.last_reply

            if (
                self.slots["date"] is not None
                and self.slots["date"] != parsed_date
            ):
                self.slots["time"] = None

            self.slots["date"] = parsed_date

        if parsed_party is not None:
            if not 1 <= parsed_party <= 8:
                self.last_reply = (
                    "For this demo, party size must be between 1 and 8. "
                    "How many people should I book for?"
                )
                return self.last_reply

            self.slots["party_size"] = parsed_party

        if parsed_time is not None:
            self.slots["time"] = parsed_time

        # Validate time and table availability before asking for a name.
        if all(
            self.slots[key] is not None
            for key in ("date", "party_size", "time")
        ):
            if self.slots["time"] not in self.available_times:
                self.slots["time"] = None
                self.last_reply = (
                    "The restaurant accepts bookings from 12 PM "
                    "to 11:30 PM, with 30-minute booking slots. "
                    "What time would you like?"
                )
                return self.last_reply

            day = self.slots["date"].isoformat()
            table_id = self._find_available_table(
                day,
                self.slots["time"]
            )

            if table_id is None:
                self.last_reply = self._time_unavailable_reply()
                return self.last_reply

        # The name is requested only after a table is available.
        if self._find_missing() == "name":
            name = self._extract_name(text)

            if name:
                self.slots["name"] = name
            else:
                self.last_reply = self._ask_for_name()
                return self.last_reply

        missing = self._find_missing()

        if missing:
            prompts = {
                "date": (
                    "What date would you like? You can say today, "
                    "tomorrow, a weekday, or 2026-10-30."
                ),
                "party_size": (
                    "How many people will be in your party? "
                    "Please choose between 1 and 8 people."
                ),
                "time": (
                    "What time would you like? For example, 7 PM "
                    "or 19:00. We accept bookings from 12 PM to 11:30 PM."
                ),
                "name": self._ask_for_name(),
            }

            self.last_reply = prompts[missing]
            return self.last_reply

        self.last_reply = self._make_booking()
        return self.last_reply

    def _find_missing(self):
        """Return the next missing booking detail in conversation order."""
        for key in ("date", "party_size", "time", "name"):
            if self.slots.get(key) is None:
                return key

        return None

    def _ask_for_name(self):
        return "What name should I put the reservation under?"


def launch_ui():
    """Launch the Streamlit interface."""
    ui_path = Path(__file__).with_name("ui.py")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ui_path)
        ],
        check=False
    )


if __name__ == "__main__":
    launch_ui()

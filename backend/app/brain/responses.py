"""Everything the assistant can say: fixed sentences with {blanks}.

The policy decides WHICH sentence to use and WHICH values fill the blanks.
Nothing here generates new text.
"""
from datetime import date, datetime, time

from app.services.booking import OPENING_HOURS, SERVICES, WEEKDAY_NAMES

CLINIC_NAME = "Smile Dental Clinic"
FRONT_DESK = "0 5 1, 0 0 0 0 0 0 0"
ADDRESS = "Block A, Example Plaza, Islamabad"

TEMPLATES: dict[str, str] = {
    # --- asking for information ---
    "greet": "Hello, and welcome to {clinic}. How can I help you today?",
    "ask_service": (
        "What can I help you with? For example a checkup, a cleaning, "
        "a filling, a root canal, or a wisdom tooth extraction."
    ),
    "ask_when": "What day and time would you like to come in?",
    "ask_date": "Which day would you like to come in?",
    "ask_time": "What time would you like on {date}?",
    "ask_patient": "What is the patient's name?",
    "ask_phone": "What phone number can we reach you on?",
    "bad_phone": (
        "I couldn't catch a valid phone number. "
        "Please say it digit by digit, for example 0 3 0 0 and so on."
    ),
    "confirm": (
        "Let me confirm: a {service} for {name}, {date} at {time}, phone {phone}. "
        "Is that correct?"
    ),
    "ask_what_to_change": "No problem. What would you like to change?",
    # --- problems with the requested time ---
    "date_in_past": "That date has already passed.",
    "time_in_past": "That time has already passed.",
    "closed_day": "Sorry, we are closed on {weekday}s.",
    "outside_hours": "Sorry, that time is outside our opening hours. We are open {hours}.",
    "off_grid": "Our appointments start on the hour or the half hour.",
    "slot_taken": "Sorry, {date} at {time} is already taken.",
    "slot_available": "Yes, {date} at {time} is available.",
    "offer_alternatives": "I can offer {options}. Which one works for you?",
    "repeat_offer": "I can offer {options}. Which one would you like?",
    "earliest_available": "The earliest available times are {options}. Which one works for you?",
    "no_alternatives": (
        "Sorry, I couldn't find a free slot in the next two weeks. "
        "Please call our front desk on {front_desk}."
    ),
    # --- answers to side questions ---
    "answer_price": "A {service} costs {price} rupees.",
    "price_list": "Our fees are: {prices}.",
    "answer_hours": "We are open {hours}.",
    "answer_hours_day": "On {weekday}s we are open from {open} to {close}.",
    "answer_services": "We offer {services}.",
    "answer_location": "We are at {address}.",
    "discount_refusal_1": "I'm sorry, our fees are fixed, so I can't change the price.",
    "discount_refusal_2": (
        "I understand, but our fees are the same for every patient. "
        "I'm happy to book you at the standard fee."
    ),
    "small_talk": "Hello!",
    "thanks_reply": "You're welcome.",
    "urgent_ack": "I'm sorry you're in pain. Let's get you seen as soon as possible.",
    "cancel_unsupported": (
        "I can only book new appointments. To cancel or change an existing one, "
        "please call our front desk on {front_desk}."
    ),
    # --- trouble ---
    "not_understood_1": "Sorry, I didn't catch that.",
    "not_understood_2": (
        "Sorry, I still didn't catch that. You can say something like: "
        "a cleaning tomorrow at 5 PM."
    ),
    "handoff": (
        "I'm having trouble understanding. Please call our front desk on "
        "{front_desk}. Goodbye."
    ),
    "human_handoff": "Of course. Please call our front desk on {front_desk}. Goodbye.",
    "booking_failed": (
        "Sorry, I couldn't complete that booking. Please call our front desk on "
        "{front_desk}. Goodbye."
    ),
    # --- the end ---
    "booked": (
        "You're all set, {name}. Your {service} is booked for {date} at {time}. "
        "Your reference is {ref}. Thank you for calling {clinic}. Goodbye!"
    ),
    "goodbye": "Thank you for calling {clinic}. Goodbye!",
    "goodbye_no_booking": (
        "No problem, I haven't booked anything. Thank you for calling {clinic}. Goodbye!"
    ),
    "already_done": "This call has ended. Thank you for calling {clinic}.",
}


# --- formatting helpers ----------------------------------------------------

def format_time(value: time) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def format_date(value: date, today: date | None = None) -> str:
    if today is not None:
        if value == today:
            return "today"
        if (value - today).days == 1:
            return "tomorrow"
    return f"{WEEKDAY_NAMES[value.weekday()]}, {value.strftime('%B')} {value.day}"


def join_words(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " or " + items[-1]


def format_slots(slots: list[datetime], today: date | None = None) -> str:
    """'tomorrow at 11:30 AM, 12:00 PM or 12:30 PM' (date repeated only when it changes)."""
    pieces: list[str] = []
    last_date: date | None = None
    for slot in slots:
        if slot.date() != last_date:
            pieces.append(f"{format_date(slot.date(), today)} at {format_time(slot.time())}")
            last_date = slot.date()
        else:
            pieces.append(format_time(slot.time()))
    return join_words(pieces)


def format_phone(digits: str) -> str:
    return " ".join(digits)  # "0 3 1 2 ..." so the voice reads digit by digit


def describe_hours() -> str:
    """Built from OPENING_HOURS, so what we say can never disagree with what we enforce."""
    groups: list[list] = []  # [first_day, last_day, hours]
    for weekday in range(7):
        hours = OPENING_HOURS.get(weekday)
        if groups and groups[-1][2] == hours:
            groups[-1][1] = weekday
        else:
            groups.append([weekday, weekday, hours])

    parts = []
    for first, last, hours in groups:
        days = (
            WEEKDAY_NAMES[first]
            if first == last
            else f"{WEEKDAY_NAMES[first]} to {WEEKDAY_NAMES[last]}"
        )
        if hours is None:
            parts.append(f"closed on {days}")
        else:
            parts.append(f"{days}, {format_time(hours[0])} to {format_time(hours[1])}")
    return "; ".join(parts)


def describe_prices() -> str:
    return "; ".join(f"{name} {price} rupees" for name, price in SERVICES.items())


def describe_services() -> str:
    return join_words(list(SERVICES))


def render(action: str, **values) -> str:
    """Pick the sentence for `action` and fill its blanks."""
    defaults = {"clinic": CLINIC_NAME, "front_desk": FRONT_DESK, "address": ADDRESS}
    return TEMPLATES[action].format(**{**defaults, **values})
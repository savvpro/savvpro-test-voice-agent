"""Every sentence the agent says, with a few phrasings each.

Variants are picked with a seeded random generator so a conversation is
reproducible in tests. Output is plain text (no SSML) so any TTS can read it.
"""

import datetime as dt
import random

from app.clinic import CLINIC_ADDRESS, CLINIC_NAME, OPENING_HOURS

TEMPLATES: dict[str, list[str]] = {
    "greeting": [
        f"Hello, thank you for calling {CLINIC_NAME}. I can book, change or cancel "
        "an appointment, or answer questions about the clinic. How can I help you today?",
        f"Hello, you've reached {CLINIC_NAME}. I can book, reschedule or cancel appointments "
        "and tell you about the clinic. What can I do for you?",
    ],
    "anything_else": [
        "Is there anything else I can help you with?",
        "Can I help you with anything else?",
    ],
    "how_can_i_help": ["Sure, what can I help you with?", "Of course. How can I help?"],
    # collecting
    "ask_department": [
        "Which department would you like? We have {departments}.",
        "Which department do you need: {departments}?",
    ],
    "ask_date": ["What day would you like to come in?", "Which day suits you?"],
    "ask_name": [
        "Great, {slot}. Can I have the patient's full name, please?",
        "{slot} it is. What's the patient's name?",
    ],
    "ask_phone": [
        "Thanks, {name}. What's the best mobile number to reach you?",
        "Thank you, {name}. Could I have a mobile number, please?",
    ],
    "invalid_phone": [
        "Sorry, that doesn't look like a valid mobile number. Please say an 11-digit number "
        "starting with 03, for example 0300 1234567.",
    ],
    "offer_slots": [
        "I have {options}. Which one would you like?",
        "Available times are {options}. Which would you prefer?",
    ],
    "slot_taken": [
        "Sorry, {when} isn't available.",
        "I'm afraid {when} is already taken.",
    ],
    "nothing_free_then": [
        "There's nothing free {when}.",
        "Sorry, {when} is fully booked.",
    ],
    "nearest_instead": ["The nearest free times are {options}. Would one of those work?"],
    "no_slots_at_all": [
        "Sorry, {department} has no free appointments in the coming weeks. "
        "Would you like a different department?",
    ],
    "which_option": [
        "Which one would you like: {choices}?",
        "Sure, which one: {choices}?",
    ],
    "offer_declined": [
        "No problem. Which other day would suit you?",
        "Okay. What other day would you like?",
    ],
    "what_to_change": [
        "Sure, what would you like to change: the department, doctor, day, time, name or number?",
    ],
    "changed": ["Sure, I've changed the {what} to {value}.", "Okay, {what} changed to {value}."],
    # policy problems
    "date_past": ["{date} has already passed. Which day would you like instead?"],
    "date_closed": [
        "Sorry, we're closed on {date}. We're open Monday to Saturday. Which day would you like?",
    ],
    "date_too_far": [
        "Sorry, we only take bookings up to 30 days ahead, and {date} is further out. "
        "Could you pick an earlier day?",
    ],
    "time_past": ["{time} today has already passed. What later time would suit you?"],
    "time_before_open": [
        "We open at 9 AM, so {time} is too early. What time would you like?",
    ],
    "time_after_close": [
        "Sorry, {time} is after closing time. On {weekday} we close at {close}. "
        "What time would you like?",
    ],
    "time_lunch": [
        "Sorry, the clinic is closed for lunch from 1 to 2 PM. What other time would you like?",
    ],
    "unknown_department": [
        "Sorry, we don't have a {name} at this clinic.",
        "I'm afraid we don't offer {name} here.",
    ],
    # confirm & execute
    "confirm_booking": [
        "Let me confirm: {department} with {doctor} on {slot}, for {name}, phone {phone}. "
        "Shall I book it?",
        "So that's {department} with {doctor}, {slot}, for {name} on {phone}. Is that correct?",
    ],
    "booked": [
        "Done! You're booked with {doctor} on {slot}. Your booking reference is {ref}. "
        "Please arrive 10 minutes early.",
        "All set. {name} is booked with {doctor} on {slot}. Your reference is {ref}.",
    ],
    "slot_just_taken": ["Sorry, that slot was just taken by someone else."],
    "ask_booking_ref": [
        "Sure. What's your booking reference? It starts with S C. "
        "Or you can tell me the mobile number you booked with.",
    ],
    "ref_not_found": [
        "I couldn't find an active booking with reference {ref}. Could you check the "
        "reference, or tell me the mobile number you booked with?",
    ],
    "phone_not_found": [
        "I couldn't find an upcoming booking for {phone}. Do you have your booking reference?",
    ],
    "found_for_reschedule": [
        "I found your appointment: {department} with {doctor} on {slot}.",
    ],
    "confirm_reschedule": [
        "So I'll move your {department} appointment from {old} to {new} with {doctor}. "
        "Shall I go ahead?",
    ],
    "rescheduled": [
        "Done. Your appointment is now on {slot} with {doctor}. Your reference stays {ref}.",
    ],
    "confirm_cancel": [
        "I found your {department} appointment with {doctor} on {slot} for {name}. "
        "Shall I cancel it?",
    ],
    "cancelled": ["Your appointment on {slot} has been cancelled.", "Okay, that's cancelled."],
    "cancel_kept": ["Okay, I've left your appointment as it is."],
    "change_or_cancel": ["Would you like to reschedule or cancel that appointment?"],
    "yes_or_no": ["Sorry, I just need a yes or a no.", "Sorry, could you say yes or no?"],
    # conversation management
    "not_understood": [
        "Sorry, I didn't quite get that.",
        "Sorry, I didn't understand.",
    ],
    "silence": ["Sorry, I didn't hear anything.", "Are you still there?"],
    "silence_end": [
        "I can't hear you, so I'll end the call now. Please call back any time. Goodbye.",
    ],
    "out_of_scope": [
        "I'm the clinic receptionist, so I can only help with appointments and clinic information.",
    ],
    "emergency": [
        "This sounds like an emergency. Please hang up and call 1122 for Rescue, or go to the "
        "nearest emergency department right away.",
    ],
    "handoff": ["Of course. I'm transferring you to our reception team now. Please hold."],
    "handoff_failures": [
        "I'm having trouble understanding, so I'm transferring you to our reception team. "
        "Please hold.",
    ],
    "aborted": ["No problem, I've stopped that.", "Okay, I've cancelled that request."],
    "goodbye": [
        "Thank you for calling. Take care, bye!",
        "Thanks for calling Shifa Care. Bye!",
    ],
    "call_over": ["This call has ended."],
    "welcome": ["You're welcome."],
    "hello_again": ["Hello!"],
    # clinic info
    "hours": ["{hours}"],
    "location": [f"We're at {CLINIC_ADDRESS}."],
    "departments": ["Our departments are {departments}."],
    "doctors_in": ["In {department} we have {doctors}."],
    "doctors_all": ["Our doctors are: {listing}."],
}

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Responses:
    def __init__(self, seed: int | None = 0):
        self._rng = random.Random(seed)

    def __call__(self, key: str, **values) -> str:
        return self._rng.choice(TEMPLATES[key]).format(**values)


# --- formatting for speech ---------------------------------------------------


def format_date(day: dt.date) -> str:
    return f"{_WEEKDAY_NAMES[day.weekday()]} {day.day} {day.strftime('%B')}"


def format_time(at: dt.time) -> str:
    hour = at.hour % 12 or 12
    suffix = "AM" if at.hour < 12 else "PM"
    return f"{hour} {suffix}" if at.minute == 0 else f"{hour}:{at.minute:02d} {suffix}"


def format_slot(start: dt.datetime) -> str:
    return f"{format_date(start.date())} at {format_time(start.time())}"


def format_phone(phone: str) -> str:
    return f"{phone[:4]} {phone[4:]}"


def spell_ref(ref: str) -> str:
    """SC-4F7K -> 'SC-4F7K, that's S, C, 4, F, 7, K' so it survives TTS."""
    return f"{ref}, that's {', '.join(ref.replace('-', ''))}"


def join_words(items: list[str], last: str = "and") -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {last} {items[-1]}"


def opening_hours_text() -> str:
    weekday = OPENING_HOURS[0]
    saturday = OPENING_HOURS[5]
    return (
        f"We're open Monday to Friday from {format_time(weekday[0][0])} to "
        f"{format_time(weekday[-1][1])}, with a lunch break from {format_time(weekday[0][1])} "
        f"to {format_time(weekday[1][0])}, and Saturday from {format_time(saturday[0][0])} to "
        f"{format_time(saturday[-1][1])}. We're closed on Sunday."
    )


def weekday_name(day: dt.date) -> str:
    return _WEEKDAY_NAMES[day.weekday()]

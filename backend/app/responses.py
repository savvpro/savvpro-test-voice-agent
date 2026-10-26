"""Reply templates: action -> text. A tuple rotates deterministically by `failures`."""

from app.clinic import CLINIC_NAME, EMERGENCY_NUMBER

TEMPLATES: dict[str, str | tuple[str, ...]] = {
    "greet": f"Thanks for calling {CLINIC_NAME}. I can book, reschedule or cancel an appointment."
    " How can I help?",
    "ask_intent": "Would you like to book, reschedule or cancel an appointment?",
    "ask_name": "Sure. Can I have your full name, please?",
    "ask_dob": "Thanks. What's your date of birth?",
    "ask_doctor": "Which doctor would you like to see? We have {doctors}."
    " Or just tell me what it's about, like a checkup or a skin problem.",
    "ask_date": "What day would you like to come in?",
    "ask_time": "What time on {day} works for you? We're open 9 AM to 5 PM.",
    "offer_slots": "The closest openings are {options}. Which one would you like?",
    "no_openings": "I couldn't find any openings near then. What other day would suit you?",
    "taken": "Sorry, that time is already taken. ",
    "confirm_booking": "So that's {name}, born {dob}, with {doctor} on {day} at {time}."
    " Shall I book it?",
    "booked": "You're booked. Your reference is {ref}, that's {spelled}."
    " Is there anything else I can help with?",
    "ask_lookup": "I can help with that. What's your booking reference?"
    " If you don't have it, just tell me your full name.",
    "choose_appointment": "I found {count} appointments. {options}. Which one do you mean?",
    "confirm_cancel": "I have your appointment with {doctor} on {day} at {time},"
    " reference {ref}. Shall I cancel it?",
    "cancelled": "Done. Appointment {ref} is cancelled. Is there anything else I can help with?",
    "kept": "Okay, I'll leave that appointment as it is. Is there anything else I can help with?",
    "confirm_reschedule": "So I'll move appointment {ref} to {day} at {time} with {doctor}."
    " Shall I go ahead?",
    "rescheduled": "All done. Appointment {ref} is now on {day} at {time} with {doctor}."
    " Is there anything else I can help with?",
    "not_found": (
        (
            "I couldn't find an upcoming appointment with those details."
            " Could you give me your booking reference, or your full name?"
        ),
        "I still can't find that appointment. Would you like to book a new one instead?",
    ),
    "past": "That time has already passed. ",
    "weekend": "Sorry, we're closed on the weekend. ",
    "closed": "Sorry, we're only open from 9 AM to 5 PM, Monday to Friday. ",
    "off_grid": "Appointments start on the hour or half hour. ",
    "unknown_doctor": "Sorry, we don't have a doctor by that name. Our doctors are {doctors}."
    " Who would you like to see?",
    "ask_what_to_change": "No problem. What would you like to change: the doctor, the day,"
    " or the time?",
    "ask_new_time": "No problem. What day and time would suit you instead?",
    "ask_lookup_name": "Thanks. And what's the full name on the appointment?",
    "help": "I can book a new appointment, reschedule one, or cancel one. You can speak"
    " naturally, for example: book with Dr Patel tomorrow at 2 PM.",
    "reprompt": (
        "Sorry, I didn't catch that.",
        "Sorry, I still didn't get that.",
    ),
    "emergency": "This sounds like an emergency. Please hang up now and call"
    f" {EMERGENCY_NUMBER}, or go to the nearest emergency room.",
    "goodbye": f"Thanks for calling {CLINIC_NAME}. Take care, goodbye!",
    "give_up": "I'm sorry, I'm having trouble understanding. Please call back or visit the"
    " front desk. Goodbye.",
}


def render(action: str, **kw: object) -> str:
    t = TEMPLATES[action]
    if isinstance(t, tuple):
        failures = kw.get("failures", 0)
        t = t[failures % len(t) if isinstance(failures, int) else 0]
    return t.format(**kw)

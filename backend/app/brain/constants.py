"""Brain-layer constants — phrases, thresholds, and message templates.

Step 3 populates the normalizer-related constants (FILLER_WORDS,
NUMBER_WORD_MAP, DOUBLE_TRIPLE_PATTERN).  Intent keyword tables will be
fleshed out in Step 6.
"""

from __future__ import annotations

import re

# ── Filler words ──────────────────────────────────────────────────────
#
# Speech disfluencies stripped during normalisation.
# **"like" is NOT included** — it must survive to keep "I'd like to…".

FILLER_WORDS: frozenset[str] = frozenset(
    {
        "uh",
        "um",
        "uhm",
        "umm",
        "erm",
        "er",
        "ah",
        "hmm",
        "hm",
        "you know",
        "sort of",
        "kind of",
        "i mean",
        "basically",
        "literally",
        "right so",
    }
)

# ── Number-word → digit map ──────────────────────────────────────────
#
# Ordered **longest-first** so that multi-word entries are replaced before
# single-word ones (e.g. "twenty one" before "one").

NUMBER_WORD_MAP: list[tuple[str, str]] = [
    # Teens & compounds (longest first)
    ("twenty one", "21"),
    ("twenty two", "22"),
    ("twenty three", "23"),
    ("twenty four", "24"),
    ("twenty five", "25"),
    ("twenty six", "26"),
    ("twenty seven", "27"),
    ("twenty eight", "28"),
    ("twenty nine", "29"),
    ("thirty one", "31"),
    ("thirty", "30"),
    ("twenty", "20"),
    ("nineteen", "19"),
    ("eighteen", "18"),
    ("seventeen", "17"),
    ("sixteen", "16"),
    ("fifteen", "15"),
    ("fourteen", "14"),
    ("thirteen", "13"),
    ("twelve", "12"),
    ("eleven", "11"),
    ("ten", "10"),
    # Single digits
    ("nine", "9"),
    ("eight", "8"),
    ("seven", "7"),
    ("six", "6"),
    ("five", "5"),
    ("four", "4"),
    ("three", "3"),
    ("two", "2"),
    ("one", "1"),
    ("zero", "0"),
]

# ── Double / triple patterns ─────────────────────────────────────────

DOUBLE_TRIPLE_PATTERN: re.Pattern[str] = re.compile(
    r"\b(double|triple)\s+(zero|oh|one|two|three|four|five|six|seven|eight|nine|\d)\b",
    re.IGNORECASE,
)

# Map used inside the double/triple replacer.
_WORD_TO_SINGLE_DIGIT: dict[str, str] = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}

# ── "oh" → "0" context pattern ───────────────────────────────────────
#
# "oh" is converted to "0" only when it appears between digits, digit-words,
# or at the start/end of a digit sequence.  This avoids corrupting phrases
# like "oh no" in intent_text (which skips the digit pass entirely).

OH_DIGIT_CONTEXT: re.Pattern[str] = re.compile(
    r"(?<=[0-9])\s+oh\b|\boh\s+(?=[0-9])",
    re.IGNORECASE,
)

# ── Thresholds & limits ──────────────────────────────────────────────

MAX_INPUT_LENGTH: int = 2000

CONFIDENCE_THRESHOLD: float = 0.40
AMBIGUITY_MARGIN: float = 0.15
EXTRA_HIT_BONUS: float = 0.15
STT_CONFIDENCE_THRESHOLD: float = 0.50

# ── Parcel status rules ──────────────────────────────────────────────
#
# Maps a parcel status to the set of action intents the caller is allowed
# to perform.

PARCEL_STATUS_RULES: dict[str, set[str]] = {
    "failed_attempt": {"reschedule", "pickup_point", "cancel", "status"},
    "in_transit": {"status"},
    "out_for_delivery": {"status"},
    "delivered": {"status"},
    "cancelled": set(),
    "returned_to_sender": set(),
}

# ── RD phonetic prefixes ─────────────────────────────────────────────

RD_PHONETIC_PREFIXES: list[str] = [
    "rd",
    "r d",
    "are dee",
    "our d",
    "ardie",
]

# ── Messages (TTS-friendly) ──────────────────────────────────────────
#
# Placeholder keys use {slot} syntax; the state machine formats them.
# Sentences ≤ 20 words.

MESSAGES: dict[str, str] = {
    "greeting": (
        "Hello. Welcome to REDELIVER. I can help with a missed delivery. "
        "Please tell me your tracking ID. "
        "It starts with R. D. followed by 8 digits."
    ),
    "ask_tracking_id": (
        "Please say your tracking ID. "
        "It starts with R. D. followed by 8 digits."
    ),
    "tracking_not_found": (
        "I cannot find that parcel. Please try again."
    ),
    "tracking_confirm": (
        "I heard {tracking_id_spoken}. Is that correct?"
    ),
    "tracking_multiple": (
        "I heard two IDs. Which one did you mean? {id_a} or {id_b}?"
    ),
    "tracking_max_attempts": (
        "I was not able to find your tracking ID. "
        "Let me transfer you to a human agent. Goodbye."
    ),
    "ask_phone": (
        "Great. Please say the last 4 digits of your phone number."
    ),
    "phone_wrong": (
        "That did not match. Please try again."
    ),
    "phone_locked": (
        "For security I cannot continue. "
        "Please contact our support team. Goodbye."
    ),
    "verified_menu": (
        "Verified. What would you like to do? "
        "Reschedule, pick up from a point, cancel, or check status?"
    ),
    "status_blocked": (
        "Your parcel is currently {status}. "
        "That action is not available right now."
    ),
    "status_explanation": (
        "{explanation} {available_actions} What would you like to do?"
    ),
    "ask_date": (
        "What date works for you? I can book within the next 7 days."
    ),
    "ask_period": (
        "Which do you prefer? Morning, afternoon, or evening?"
    ),
    "confirm_slot": (
        "I have {period} on {date}. Shall I book that?"
    ),
    "slot_full": (
        "Sorry, {period} on {date} is fully booked. "
        "The nearest available is {alt_period} on {alt_date}. Want that?"
    ),
    "no_slots_on_day": (
        "No slots on {date}. The next available is {alt_period} on {alt_date}. "
        "Want that?"
    ),
    "date_past": (
        "That time has passed. Please choose a future date."
    ),
    "date_out_of_range": (
        "I can only book within the next 7 days."
    ),
    "date_cutoff": (
        "That time slot has already passed today. "
        "Please choose a later time or another day."
    ),
    "booked": (
        "Booked. Delivery on {date}, {period}. {anything_else}"
    ),
    "rebooked": (
        "Rebooked. Your new delivery is {date}, {period}. {anything_else}"
    ),
    "list_pickup_points": (
        "Here are the pickup points:\n\n{points_list}\n\n"
        "Choose by number, city, or pickup-point name. Which one would you like?"
    ),
    "pickup_point_ambiguous": (
        "I heard more than one location. Please say one city or pickup-point name."
    ),
    "confirm_pickup": (
        "You chose {name} at {address}. It is open {open_hours} PKT. Is that right?"
    ),
    "pickup_done": (
        "Noted. Please collect from {name}. {anything_else}"
    ),
    "confirm_cancel": (
        "Are you sure you want to cancel your delivery? Say yes to confirm."
    ),
    "cancelled": (
        "Your delivery has been cancelled. {anything_else}"
    ),
    "cancel_denied": (
        "OK, not cancelled. What else can I help with?"
    ),
    "anything_else": (
        "Is there anything else you would like help with? "
        "Say yes to continue, or no to end the call."
    ),
    "anything_else_continue": (
        "Sure. What would you like to do? "
        "Reschedule, pick up from a point, cancel, or check status?"
    ),
    "anything_else_clarify": (
        "Please say yes if you need help with something else, "
        "or no if you are done."
    ),
    "change_of_mind_menu": (
        "No problem. What would you like to do instead?"
    ),
    "silence_1": (
        "I did not hear anything. Are you still there?"
    ),
    "silence_2": (
        "I still cannot hear you. Please say something."
    ),
    "silence_3": (
        "I have not heard from you. I will end the call now. Goodbye."
    ),
    "unknown_1": (
        "I did not quite understand. Could you say that differently?"
    ),
    "unknown_2": (
        "I am still not sure what you need. "
        "You can say reschedule, pick up, cancel, or status."
    ),
    "unknown_3": (
        "I'm still not sure what you need. You can ask about your parcel, "
        "check its status, reschedule, choose pickup, or cancel."
    ),
    "unknown_4": (
        "I may have misunderstood. Please try saying that another way, "
        "or tell me which delivery option you need."
    ),
    "offer_human": (
        "I'm still having trouble understanding. Would you like me to "
        "transfer you to a human agent? Please say yes or no."
    ),
    "human_declined": (
        "Okay, I will not transfer you. Let's keep going. "
        "Please try saying that another way."
    ),
    "stt_low_confidence": (
        "I did not quite catch that. Could you say that again?"
    ),
    "repeat_no_previous": (
        "I have not said anything yet. How can I help?"
    ),
    "human_handoff": (
        "Let me transfer you to a human agent now. Goodbye."
    ),
    "goodbye": (
        "Thank you for calling REDELIVER. Goodbye."
    ),
    "session_ended": (
        "This call has ended. Goodbye."
    ),
    "affirm_wrong_state": (
        "I am not sure what you are confirming. {re_ask}"
    ),
}

# ── Intent keywords ──────────────────────────────────────────────────
#
# dict[str, list[tuple[str, float]]]
# intent → list of (whole_word_phrase, weight) tuples.
# Phrases are matched with \b boundaries.

INTENT_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "reschedule": [
        ("reschedule", 1.0),
        ("rescheduling", 1.0),
        ("rescheduled", 1.0),
        ("re schedule", 1.0),
        ("free schedule", 1.0),
        ("residual", 0.8),
        ("reach casual late", 1.0),
        ("reach schedule", 1.0),
        ("reset your late", 1.0),
        ("reset delivery", 1.0),
        ("rebook", 1.0),
        ("schedule again", 1.0),
        ("new date", 1.0),
        ("new time", 1.0),
        ("change delivery", 1.0),
        ("change my delivery", 1.0),
        ("change delivery date", 1.0),
        ("move my delivery", 1.0),
        ("different day", 1.0),
        ("another day", 1.0),
        ("book again", 1.0),
        ("delivery date", 0.5),
        ("different slot", 0.5),
    ],
    "pickup_point": [
        ("pickup point", 1.0),
        ("pick up point", 1.0),
        ("pick up", 1.0),
        ("want to pick up", 1.0),
        ("like to pick up", 1.0),
        ("pick up my parcel", 1.0),
        ("collection point", 1.0),
        ("pick it up", 1.0),
        ("collect it", 1.0),
        ("go to depot", 1.0),
        ("post office", 1.0),
        ("collect", 0.5),
        ("depot", 0.5),
        ("branch", 0.5),
    ],
    "cancel": [
        ("cancel the delivery", 1.0),
        ("cancel my delivery", 1.0),
        ("don't want it", 1.0),
        ("send it back", 1.0),
        ("return it", 1.0),
        ("refuse delivery", 1.0),
        ("cancel", 0.5),
        ("stop delivery", 0.5),
    ],
    "status": [
        ("where is my parcel", 1.0),
        ("where's my parcel", 1.0),
        ("tracking update", 1.0),
        ("any update on my delivery", 1.0),
        ("has it been delivered", 1.0),
        ("status", 0.5),
        ("tracking", 0.5),
        ("where is it", 0.5),
    ],
    "explain_status": [
        ("what does failed attempt mean", 1.0),
        ("what does fail attempt mean", 1.0),
        ("what is failed attempt", 1.0),
        ("what does this status mean", 1.0),
        ("explain failed attempt", 1.0),
    ],
    "affirm": [
        ("yes please", 1.0),
        ("yes confirm", 1.0),
        ("that's right", 1.0),
        ("go ahead", 1.0),
        ("that is correct", 1.0),
        ("confirm please", 1.0),
        ("yes", 0.5),
        ("yeah", 0.5),
        ("yep", 0.5),
        ("correct", 0.5),
        ("ok", 0.5),
        ("sure", 0.5),
        ("alright", 0.5),
        ("perfect", 0.5),
    ],
    "deny": [
        ("no that's wrong", 1.0),
        ("that is not right", 1.0),
        ("never mind that", 1.0),
        ("no", 0.5),
        ("nope", 0.5),
        ("wrong", 0.5),
        ("never mind", 0.5),
        ("incorrect", 0.5),
    ],
    "repeat": [
        ("say that again", 1.0),
        ("repeat that please", 1.0),
        ("what did you say", 1.0),
        ("come again please", 1.0),
        ("pardon", 0.5),
        ("repeat", 0.5),
        ("say again", 0.5),
        ("didn't catch", 0.5),
    ],
    "human_agent": [
        ("speak to a human", 1.0),
        ("talk to an agent", 1.0),
        ("real person please", 1.0),
        ("transfer me to someone", 1.0),
        ("human", 0.5),
        ("agent", 0.5),
        ("operator", 0.5),
        ("person", 0.5),
        ("representative", 0.5),
    ],
    "change_of_mind": [
        ("no wait actually", 1.0),
        ("actually wait", 1.0),
        ("on second thought", 1.0),
        ("let me change that", 1.0),
        ("something else instead", 1.0),
        ("actually", 0.5),
        ("wait", 0.5),
        ("instead", 0.5),
        ("switch", 0.5),
    ],
    "goodbye": [
        ("goodbye for now", 1.0),
        ("thanks that's all", 1.0),
        ("i'm all done", 1.0),
        ("all from my side", 0.9),
        ("thanks bye", 1.0),
        ("bye", 0.5),
        ("goodbye", 0.5),
        ("thanks", 0.5),
        ("thank you", 0.5),
        ("done", 0.5),
        ("cheers", 0.5),
    ],
}

# ── Intent regex patterns ─────────────────────────────────────────────
#
# dict[str, list[tuple[re.Pattern, float]]]
# Compiled regex patterns per intent with weights.

INTENT_REGEX_PATTERNS: dict[str, list[tuple[re.Pattern[str], float]]] = {
    "reschedule": [
        (re.compile(r"\bre[\s-]?schedule(?:d|s|ing)?\b", re.IGNORECASE), 1.0),
        (re.compile(r"\b(?:move|change)\b.*\b(delivery|date|time|day)\b", re.IGNORECASE), 0.9),
        (re.compile(r"deliver.*again", re.IGNORECASE), 0.8),
        (re.compile(r"(new|different)\s+(day|date|time|slot)", re.IGNORECASE), 0.8),
    ],
    "pickup_point": [
        (re.compile(r"\bpick\s+up\b", re.IGNORECASE), 1.0),
        (re.compile(r"pick\s*up\s*point", re.IGNORECASE), 0.8),
        (re.compile(r"collect\s*(it|from)", re.IGNORECASE), 0.8),
    ],
    "cancel": [
        (re.compile(r"cancel\s*(the\s*)?(delivery|order|parcel)", re.IGNORECASE), 0.8),
        (re.compile(r"don'?t\s+want", re.IGNORECASE), 0.8),
    ],
    "status": [
        (re.compile(r"where\s+(is|are)\s+(my|the)", re.IGNORECASE), 0.8),
        (re.compile(r"(what|how).*(status|update)", re.IGNORECASE), 0.8),
    ],
    "explain_status": [
        (re.compile(r"\bwhat\s+(?:does|is)\b.*\b(?:fail(?:ed)?\s+attempt|status)\b.*\bmean\b", re.IGNORECASE), 1.0),
    ],
    "affirm": [
        (re.compile(r"\byes\b", re.IGNORECASE), 0.5),
        (re.compile(r"\byeah\b", re.IGNORECASE), 0.5),
    ],
    "deny": [
        (re.compile(r"^no\b", re.IGNORECASE), 0.5),
        (re.compile(r"that'?s\s+(not\s+right|wrong)", re.IGNORECASE), 0.8),
    ],
    "repeat": [
        (re.compile(r"(say|repeat)\s+(that\s+)?(again|please)", re.IGNORECASE), 0.8),
    ],
    "human_agent": [
        (re.compile(r"(speak|talk)\s+to\s+(a\s+)?(human|person|agent)", re.IGNORECASE), 0.8),
    ],
    "change_of_mind": [
        (re.compile(r"(actually|wait)\s*,?\s*(no|let|can|i)", re.IGNORECASE), 0.8),
    ],
    "goodbye": [
        (re.compile(r"^(bye|goodbye)$", re.IGNORECASE), 0.8),
        (re.compile(r"that'?s\s+all", re.IGNORECASE), 0.8),
        (re.compile(r"\ball\s+from\s+my\s+side\b", re.IGNORECASE), 0.9),
    ],
}

# Plain-language explanations are returned by the backend when callers ask
# what their current delivery status means.
STATUS_EXPLANATIONS: dict[str, str] = {
    "in_transit": "In transit means your parcel is moving through the delivery network.",
    "out_for_delivery": "Out for delivery means the courier is expected to deliver your parcel today.",
    "failed_attempt": "A failed attempt means the courier tried to deliver your parcel but could not complete the delivery.",
    "delivered": "Delivered means the courier marked your parcel as delivered.",
    "cancelled": "Cancelled means the delivery has been cancelled.",
    "returned_to_sender": "Returned to sender means the parcel is on its way back to the sender.",
}

# ── State-aware intent priority ───────────────────────────────────────
#
# For CONFIRM states, evaluate these intents first.  If any scores above
# threshold, return it immediately without scoring other intents.

STATE_INTENT_PRIORITY: dict[str, list[str]] = {
    "CONFIRM_TRACKING_ID": ["affirm", "deny", "change_of_mind", "repeat", "human_agent", "goodbye"],
    "CONFIRM_SLOT": ["affirm", "deny", "change_of_mind", "repeat", "human_agent", "goodbye"],
    "CONFIRM_PICKUP": ["affirm", "deny", "change_of_mind", "repeat", "human_agent", "goodbye"],
    "CONFIRM_CANCEL": ["affirm", "deny", "change_of_mind", "repeat", "human_agent", "goodbye"],
    "VERIFY_PHONE": ["repeat", "human_agent", "goodbye"],
}

# ── Disambiguation patterns ──────────────────────────────────────────

DISAMBIG_NO_WAIT = re.compile(r"\b(no\s+wait|wait\s+no)\b", re.IGNORECASE)
DISAMBIG_CANCEL_THAT = re.compile(r"\bcancel\s+that\b", re.IGNORECASE)

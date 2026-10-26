from dataclasses import dataclass, field
from datetime import date, time
import re


@dataclass
class NLUResult:
    intents: set[str] = field(default_factory=set)
    service: str | None = None
    appt_date: date | None = None
    appt_time: time | None = None
    name: str | None = None
    phone: str | None = None
    choice: int | None = None      # "the second one" -> 2 (1-based)
    relation: str | None = None    # "my mother" -> "mother" (the patient is someone else)


MONEY_PATTERN = re.compile(r"\b\d{1,3}k\b|\b\d{3,6}\s?(?:rupees|rs|pkr)\b")  # for money like 8k , 10k etc


def normalize(raw: str) -> str:
    text = raw.lower()
    text = re.sub(r"['.]", "", text)          # delete apostrophes and dots
    text = re.sub(r"[^a-z0-9 :]", " ", text)  # other punctuation -> space, keep the colon
    return " ".join(text.split())


INTENT_PHRASES = {
    "greeting": [
        "hello", "hi", "hii", "hey", "hello there", "hi there", "good morning",
        "good afternoon", "good evening", "how are you", "how are you doing",
        "whats up", "salam", "assalamualaikum", "assalam o alaikum", "aoa",
    ],
    "book": [
        "book", "booking", "appointment", "appoint", "schedule", "reserve",
        "reservation", "slot", "consultation", "see the doctor", "see a doctor",
        "see the dentist", "see a dentist", "come in", "come to the clinic",
        "visit",
    ],
    "ask_hours": [
        "hours", "working hours", "opening hours", "timing", "timings",
        "clinic time", "clinic timing", "clinic timings", "your time", "your timing",
        "are you open", "is the clinic open", "open on", "open till", "open until",
        "closed on", "are you closed", "opening time", "closing time",
        "when do you open", "when do you close", "what time do you open",
        "what time do you close", "what time", "until what time", "till what time",
    ],
    "ask_availability": [
        "available", "availability", "any slot", "any slots", "do you have a slot",
        "any opening", "earliest", "soonest", "first available", "next available",
        "is the doctor free", "are you free",
    ],
    "ask_price": [
        "how much", "how much is", "how much does", "how much do you charge",
        "what do you charge", "charges", "charge", "charged", "price", "prices",
        "pricing", "cost", "costs", "fee", "fees", "rate", "rates",
        "kitna", "kitne paise", "paise",
    ],
    "ask_discount": [
        "discount", "discounts", "cheaper", "cheap", "reduce", "reduced",
        "lower", "lower the price", "reduce the price", "any less", "bit less",
        "a little less", "bargain", "negotiate", "negotiable", "concession",
        "too much", "too expensive", "too costly", "expensive", "costly",
        "best price", "last price", "final price",
    ],
    "ask_services": [
        "services", "what services", "which services", "what do you offer",
        "what treatments", "treatments", "do you offer", "do you provide",
        "do you do",
    ],
    "ask_location": [
        "address", "location", "located", "directions", "where are you",
        "where is the clinic", "how to reach", "how do i reach",
        "how to get there", "how do i get there",
    ],
    "affirm": [
        "yes", "yeah", "yep", "yup", "yes please", "yes sure", "okay", "ok",
        "sure", "of course", "absolutely", "definitely", "exactly", "sounds good",
        "correct", "thats correct", "right", "thats right", "confirmed", "confirm",
        "fine", "thats fine", "that works", "works for me", "alright", "all right",
        "perfect", "go ahead", "go for it", "book it", "please do",
        "haan", "han", "ji", "ji haan", "theek hai", "thik hai", "bilkul",
    ],
    "deny": [
        "no", "nope", "nah", "not really", "wrong", "incorrect", "not correct",
        "not right", "thats not right", "thats wrong", "thats not correct",
        "nahi", "nahin", "nai", "galat",
    ],
    "repeat": [
        "repeat", "repeat that", "repeat it", "please repeat", "can you repeat",
        "say that again", "say it again", "say again", "say that once more",
        "once more", "one more time", "come again", "pardon", "excuse me",
        "sorry what", "what did you say", "what did you just say",
        "what did you ask", "what was that", "didnt catch", "didnt hear",
        "i didnt get that", "didnt understand", "i dont understand",
        "could you say that again",
    ],
    "goodbye": [
        "bye", "goodbye", "good bye", "bye bye", "see you", "see you later",
        "take care", "talk later", "call later", "never mind", "nevermind",
        "forget it", "forget about it", "thats all", "nothing else", "no thanks",
        "no thank you", "hang up", "end the call", "end call", "ok bye",
        "thanks bye", "thank you bye", "allah hafiz", "khuda hafiz",
    ],
    "thanks": [
        "thanks", "thank you", "thankyou", "thx", "much appreciated",
        "appreciate it", "shukriya", "jazakallah",
    ],
    "human": [
        "speak to someone", "talk to someone", "speak to a person",
        "talk to a person", "talk to a human", "real person", "human being",
        "human", "receptionist", "speak to the receptionist",
        "talk to the receptionist", "speak to the doctor", "talk to the doctor",
        "front desk", "operator", "manager", "transfer me", "connect me",
    ],
    "urgent": [
        "urgent", "urgently", "emergency", "asap", "as soon as possible",
        "right now", "immediately", "pain", "painful", "severe pain",
        "unbearable", "toothache", "tooth ache", "swelling", "swollen",
        "bleeding", "infected", "infection",
    ],
    "cancel": [
        "cancel", "cancellation", "cancel my appointment",
        "cancel the appointment",
    ],
    "reschedule": [
        "reschedule", "rescheduling", "postpone", "prepone",
        "change my appointment", "change the appointment",
        "move my appointment", "move the appointment", "shift my appointment",
    ],
}

SERVICE_PHRASES = {
    "wisdom tooth extraction": [
        "wisdom tooth", "wisdom teeth", "wisdom", "molar extraction", "molar",
        "tooth extraction", "teeth extraction", "extraction", "extract",
        "pull out", "pulled out", "tooth removal", "remove a tooth",
    ],
    "root canal": ["root canal", "root canals", "rct", "nerve treatment"],
    "filling": ["filling", "fillings", "cavity", "cavities", "fill a tooth", "tooth filling"],
    "cleaning": [
        "cleaning", "teeth cleaning", "clean my teeth", "clean teeth",
        "scaling", "polishing", "scale and polish",
    ],
    "checkup": [
        "checkup", "checkups", "check up", "check ups", "general checkup",
        "general check up", "examination", "exam", "routine visit", "consultation",
    ],
}


def detect_intents(text: str) -> set[str]:
    cleaned = normalize(text)
    padded = f" {cleaned} "
    found: set[str] = set()
    for intent, phrases in INTENT_PHRASES.items():
        for phrase in phrases:
            if f" {phrase} " in padded:
                found.add(intent)
    if MONEY_PATTERN.search(cleaned):
        found.add("ask_discount")
    return found


def detect_service(text: str) -> str | None:
    padded = f" {normalize(text)} "
    for service, phrases in SERVICE_PHRASES.items():
        for phrase in phrases:
            if f" {phrase} " in padded:
                return service
    return None
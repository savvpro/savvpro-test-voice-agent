"""Deterministic dialogue engine. No model, network, or database dependencies."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Karachi")
WELCOME = "Assalam-o-alaikum! Welcome to Mezban, Lahore. Would you like à la carte, hi-tea, or dinner buffet? Please use fictional contact details in this demo."
RATES = {"hi-tea": 2000, "dinner buffet": 3000}
SLOTS = {"hi-tea": [16 * 60, 18 * 60], "dinner buffet": [20 * 60]}
QUESTIONS = {
    "dining": "Would you prefer à la carte, hi-tea, or dinner buffet?",
    "date": "Which date? You can say tomorrow or a date like 2026-11-06.",
    "time": "What arrival time? Please include AM or PM.",
    "adults": "How many adults? Please give children separately.",
    "children": "How many children? Say no children, or give their ages: children aged 3 and 7.",
    "seating": "Would you prefer indoor or rooftop seating?",
    "name": "What fictional name should I put the booking under? Say name is Demo Guest.",
    "phone": "Please give a fictional Pakistani mobile number, such as 03000000000.",
}


def initial():
    return {
        "stage": "collecting",
        "fields": {},
        "awaiting": "dining",
        "rule": "welcome",
        "intent": "WELCOME",
        "booking": None,
        "retries": 0,
    }


def normalize(text):
    text = text.lower().strip().replace("à", "a")
    for source, target in [
        ("کل", "tomorrow"),
        ("آج", "today"),
        ("بچے", "children"),
        ("افراد", "people"),
        ("ہائی ٹی", "hi-tea"),
        ("بوفے", "buffet"),
    ]:
        text = text.replace(source, target)
    for source, target in [
        ("zero", "0"),
        ("one", "1"),
        ("two", "2"),
        ("three", "3"),
        ("four", "4"),
        ("five", "5"),
        ("six", "6"),
        ("seven", "7"),
        ("eight", "8"),
        ("nine", "9"),
        ("ten", "10"),
        ("eleven", "11"),
        ("twelve", "12"),
        ("do", "2"),
        ("teen", "3"),
        ("chaar", "4"),
        ("paanch", "5"),
        ("cheh", "6"),
        ("saat", "7"),
        ("aath", "8"),
        ("nau", "9"),
        ("das", "10"),
        ("kal", "tomorrow"),
        ("aaj", "today"),
        ("raat", "pm"),
        ("baje", ""),
        ("bachay", "children"),
        ("bachche", "children"),
        ("log", "people"),
    ]:
        text = re.sub(r"\b" + source + r"\b", target, text)
    return text


def clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def quote(fields):
    rate = RATES.get(fields.get("dining"), 0)
    if not rate:
        return None
    total = fields.get("adults", 0) * rate + sum(
        0 if age < 4 else rate // 2 if age < 10 else rate
        for age in fields.get("children", [])
    )
    return {
        "total": total,
        "deposit": total // 4,
        "currency": "PKR",
        "tax_included": True,
    }


def extract(text, state, now):
    f = {}
    awaiting = state.get("awaiting")
    existing = state["fields"]
    if re.search(r"(?:^|\s)-\d", text):
        return (
            f,
            "Guest counts and ages cannot be negative. Please give the corrected details.",
        )
    if re.search(r"a la carte|ala carte|normal menu|regular table", text):
        f["dining"] = "a la carte"
    elif re.search(r"hi.?tea|high tea", text):
        f["dining"] = "hi-tea"
    elif "dinner buffet" in text:
        f["dining"] = "dinner buffet"
    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if date_match:
        try:
            f["date"] = datetime.strptime(date_match[1], "%Y-%m-%d").date().isoformat()
        except ValueError:
            return f, "That date is not valid. Please use YYYY-MM-DD."
    elif "tomorrow" in text:
        f["date"] = (now + timedelta(days=1)).date().isoformat()
    elif "today" in text:
        f["date"] = now.date().isoformat()
    else:
        for i, day in enumerate(
            [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
        ):
            if day in text:
                f["date"] = (
                    (now + timedelta(days=(i - now.weekday()) % 7 or 7))
                    .date()
                    .isoformat()
                )
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b", text)
    military = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if time_match:
        h, m = int(time_match[1]), int(time_match[2] or 0)
        if not 1 <= h <= 12 or m > 59:
            return f, "Please give a valid time, for example 6 PM."
        f["time"] = (h % 12 + (12 if time_match[3].startswith("p") else 0)) * 60 + m
    elif military:
        h, m = map(int, military.groups())
        if h > 23 or m > 59:
            return f, "Please give a valid time."
        f["time"] = h * 60 + m
    elif awaiting == "time" and re.fullmatch(r"\d{1,2}", text):
        return f, "Is that AM or PM? Please say the time with AM or PM."
    adults = re.search(r"\b(\d+)\s*(?:adults?|people|persons?|guests?)\b", text)
    if adults:
        f["adults"] = int(adults[1])
    elif awaiting == "adults" and text.isdigit():
        f["adults"] = int(text)
    if re.search(r"no (?:children|kids)|0 (?:children|kids)", text):
        f["children"] = []
    ages = re.search(
        r"(?:children|kids|child)\s*(?:are\s*)?(?:aged?|ages)\s*([\d ,and]+)", text
    )
    if ages:
        f["children"] = [int(n) for n in re.findall(r"\d+", ages[1])]
    elif re.search(r"\d+\s*(?:children|kids)", text) and "children" not in f:
        return (
            f,
            "Please give each child’s age, for example children aged 3 and 7. Are the adults counted separately?",
        )
    elif awaiting == "children" and re.fullmatch(r"none|no|0", text):
        f["children"] = []
    if "rooftop" in text:
        f["seating"] = "rooftop"
    elif "indoor" in text:
        f["seating"] = "indoor"
    name = re.search(r"(?:name is|under the name|naam)\s+([a-z ]{2,60})", text)
    if name:
        f["name"] = name[1].strip().title()
    elif awaiting == "name" and re.fullmatch(r"[a-z ]{2,60}", text):
        f["name"] = text.title()
    phone = re.sub(r"[\s()-]", "", text)
    number = re.search(r"(?:\+92|0)3\d{9}\b", phone)
    if number:
        f["phone"] = "0" + number[0][3:] if number[0].startswith("+92") else number[0]
    if (
        f.get("dining", existing.get("dining")) != existing.get("dining")
        and "time" not in f
    ):
        f["time"] = None
    return f, None


def advance(state, raw, now=None):
    now = now or datetime.now(TZ)
    text = normalize(raw)
    state["intent"] = "PROVIDE_DETAILS"

    def reply(message, rule, stage=None):
        state["rule"] = rule
        if stage:
            state["stage"] = stage
        return message

    if re.search(r"\b(cancel|cancel booking|mansookh)\b", text):
        state["intent"] = "CANCEL"
        if state.get("booking"):
            state["stage"] = "cancel_confirmation"
            return reply(
                "Cancel this reservation? Say yes to cancel or no to keep it.",
                "verify_cancellation",
            )
        return reply(
            "Your unfinished booking has been discarded. Allah hafiz!",
            "discard_draft",
            "ended",
        )
    if state["stage"] == "cancel_confirmation":
        if text in ["yes", "confirm", "haan", "ji"]:
            return reply("CANCEL_ACTION", "cancel_confirmed")
        if text in ["no", "no thanks", "nahi", "keep it"]:
            state["stage"] = state["booking"]["status"]
            return reply("Your booking has been kept.", "cancellation_declined")
        return reply(
            "Please say yes to cancel, or no to keep your booking.",
            "cancellation_clarification",
        )
    if re.search(
        r"\b(staff|human|manager|allergy|allergic|wheelchair|decoration|birthday|iftar|sehri)\b",
        text,
    ):
        state["intent"] = "REQUEST_STAFF"
        return reply(
            "This needs staff approval. I have recorded a demo assistance request; no staff member is contacted in this demo. Your booking details are preserved.",
            "staff_required",
        )
    if re.search(r"\b(price|cost|rate|included|drinks|kitna)\b", text):
        state["intent"] = "ASK_PRICE"
        return reply(
            "Hi-tea is PKR 2,000; dinner buffet PKR 3,000 per adult. Under 4 free; ages 4–9 half price; 10+ adult rate. Demo tax, water and tea included; soft drinks extra. Buffet requires a simulated 25% deposit. "
            + QUESTIONS.get(
                state.get("awaiting"), "Would you like to change anything?"
            ),
            "package_information",
        )
    if re.search(r"\b(menu|karahi|vegetarian|food)\b", text) and not re.search(
        r"normal menu", text
    ):
        state["intent"] = "ASK_MENU"
        return reply(
            "Our demo menu has chicken karahi PKR 1,800, daal PKR 650 and naan PKR 100. Vegetarian options are available; allergy questions need staff. Food is ordered on arrival. "
            + QUESTIONS.get(state.get("awaiting"), "Anything else?"),
            "menu_information",
        )
    if state["stage"] == "ended":
        return reply(
            "This conversation has ended. Start a new call to book again.",
            "session_ended",
        )
    if state["stage"] == "review" and text in [
        "yes",
        "confirm",
        "haan",
        "ji",
        "yes please",
    ]:
        f = state["fields"]
        arrival = datetime.fromisoformat(f["date"]).replace(
            hour=f["time"] // 60, minute=f["time"] % 60, tzinfo=TZ
        )
        if arrival <= now:
            f.pop("time")
            state["awaiting"] = "time"
            return reply(
                "That arrival time has now passed. Please choose a future time.",
                "past_time",
                "collecting",
            )
        state["intent"] = "CONFIRM"
        return reply("BOOK_ACTION", "explicit_confirmation")
    if state["stage"] in ["confirmed", "payment_pending"] and text in [
        "yes",
        "confirm",
        "haan",
        "ji",
    ]:
        if state.get("booking", {}).get("status") == "expired":
            return reply(
                "Your payment hold expired. Start a new call to check availability and book again.",
                "hold_expired",
            )
        return reply(
            "Your reservation is already recorded. See the booking reference and payment status.",
            "duplicate_confirmation",
        )
    if state["stage"] == "payment_pending" and re.search(r"\b(paid|payment)\b", text):
        return reply(
            "Payment is verified by the demo payment control, not a spoken claim. Use Simulate deposit to complete payment.",
            "payment_verification_required",
        )
    parsed, error = extract(text, state, now)
    if parsed and not error:
        state.pop("clarification", None)
    updates = {k: v for k, v in parsed.items() if state["fields"].get(k) != v}
    if updates:
        state["fields"].update(updates)
        state["stage"] = "collecting"
        state["retries"] = 0
        state.pop("clarification", None)
    f = state["fields"]
    if error:
        state["clarification"] = error
        return reply(error, "clarification_required", "collecting")
    if state.get("clarification"):
        return reply(state["clarification"], "clarification_required", "collecting")
    if not updates and state["stage"] in ["confirmed", "payment_pending"]:
        return reply(
            "Your reservation is recorded. Tell me the date, time, guests or seating you want to change, or say cancel.",
            "booking_unchanged",
        )
    if f.get("date") and f["date"] < now.date().isoformat():
        f.pop("date")
        return reply(
            "That date is in the past. Which future date would you like?", "past_date"
        )
    if f.get("adults") is not None and not 1 <= f["adults"] <= 12:
        f.pop("adults")
        return reply(
            "I can book 1–12 guests. Larger parties need staff assistance. How many adults for a standard booking?",
            "party_limit",
        )
    if any(a < 0 or a > 17 for a in f.get("children", [])):
        f.pop("children")
        return reply(
            "Please give child ages from 0 to 17. Adults should be counted separately.",
            "invalid_age",
        )
    if f.get("adults", 0) + len(f.get("children", [])) > 12:
        f.pop("children", None)
        return reply(
            "More than 12 guests needs staff approval. Please revise the party or ask for staff.",
            "party_limit",
        )
    dining = f.get("dining")
    minutes = f.get("time")
    if (
        dining == "dinner buffet"
        and f.get("date")
        and datetime.fromisoformat(f["date"]).weekday() < 4
    ):
        f.pop("date")
        return reply(
            "Dinner buffet runs Friday–Sunday. Which weekend date would you like?",
            "buffet_day",
        )
    if minutes is not None and dining:
        if dining in SLOTS and minutes not in SLOTS[dining]:
            f.pop("time")
            return reply(
                "Available sittings are "
                + ", ".join(clock(t) for t in SLOTS[dining])
                + ". Which would you prefer?",
                "fixed_sitting",
            )
        if dining == "a la carte" and not 720 <= minutes <= 1260:
            f.pop("time")
            return reply(
                "À la carte arrivals are between 12 PM and 9 PM, with a two-hour table duration. What time suits you?",
                "opening_hours",
            )
        if (
            f.get("date")
            and datetime.fromisoformat(f["date"]).replace(
                hour=minutes // 60, minute=minutes % 60, tzinfo=TZ
            )
            <= now
        ):
            f.pop("time")
            return reply(
                "That arrival time has passed. Please choose a future time.",
                "past_time",
            )
    for key, question in QUESTIONS.items():
        if f.get(key) is None:
            state["awaiting"] = key
            if not updates:
                state["retries"] += 1
                if state["retries"] >= 3:
                    return reply(
                        "I am having trouble understanding. Try the typed examples or ask for staff. "
                        + question,
                        "repeated_fallback",
                    )
            return reply(question, "collect_" + key)
    state["awaiting"] = None
    total = quote(f)
    price = (
        f" Total PKR {total['total']:,}, including demo tax; deposit PKR {total['deposit']:,}."
        if total
        else " Food is ordered and paid for on arrival."
    )
    summary = f"{f['dining']}, {f['date']} at {clock(f['time'])}, {f['adults']} adults and {len(f['children'])} children, {f['seating']}, under {f['name']}."
    return reply(
        summary
        + price
        + " Tables are held for 15 minutes after arrival time. Say yes to confirm or tell me what to change.",
        "review_required",
        "review",
    )

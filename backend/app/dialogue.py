"""Rule-based dialogue manager: (state, caller text) -> (state, reply, decision)."""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from sqlite3 import Connection as Conn
from typing import Literal

from app import scheduling as sch
from app.clinic import CLOSE, DOCTORS, OPEN, SLOT_MINUTES, doctor_by_id, doctors_for
from app.nlu import Entities, Intent, Parsed, Slot, parse
from app.parsing import _DAYS, _MONTHS, parse_dob
from app.responses import render

Flow = Literal["book", "reschedule", "cancel"]
Reply = tuple[str, str]  # (action, text)

SLOT_KEYS = ("name", "dob", "doctor_id", "specialty", "date", "time", "part_of_day", "ref")
_FLOWS: dict[Intent, Flow] = {
    Intent.BOOK: "book",
    Intent.RESCHEDULE: "reschedule",
    Intent.CANCEL: "cancel",
}
# A flow word ("yes, book it") only confirms with a plain yes and no negation anywhere.
_YES = re.compile(r"\b(yes|yeah|yep|yup)\b")
_NEG = re.compile(r"\b(no|not|don'?t|never)\b")
# "actually" hedges only straight after the yes ("yes, actually..."), not in "that's actually perfect"
_CORRECTION = re.compile(
    r"\b(but|instead|rather|change|make it|wait|hold on)\b"
    r"|\b(yes|yeah|yep|yup|sure|ok|okay)\W+actually\b"
)
# where to look for openings; we close at 17:00, so "evening" means 4 PM onwards
_POD_START = {"morning": time(9), "afternoon": time(13), "evening": time(16)}
# ponytail: stop-list heuristic for "doctor <word>" that isn't a name; grow it as calls show misses
_DR_WORD = re.compile(r"\b(?:dr\.?|doctor)\s+([a-z'-]+)")
# fmt: off
_NOT_A_NAME = {
    "appointment", "tomorrow", "today", "is", "on", "at", "for", "in", "please", "and", "next",
    "this", "the", "a", "about", "who", "that", "with", "visit", "office", "available", "as",
    "to", "or", "if", "i", *_DAYS, *_MONTHS,
}
# fmt: on


@dataclass
class CallState:
    flow: Flow | None = None
    step: str = "greeting"
    slots: dict[str, str] = field(default_factory=dict)
    expecting: str | None = None
    offers: list[list[str]] = field(default_factory=list)
    matches: list[str] = field(default_factory=list)
    last_reply: str = ""
    failures: int = 0
    misses: int = 0  # failed appointment lookups; separate from reprompt failures
    ended: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> "CallState":
        return cls(**json.loads(s))


@dataclass
class Decision:
    intent: str
    entities: dict[str, str]
    state: str
    action: str
    slots: dict[str, str]


# ---------- formatting ----------


def _day(d: date) -> str:
    return d.strftime("%A, %B %-d")


def _time(t: time) -> str:
    return t.strftime("%-I:%M %p")


def _doctor(doctor_id: str) -> str:
    d = doctor_by_id(doctor_id)
    return d.name if d else doctor_id


def _doctor_list() -> str:
    names = [d.name for d in DOCTORS]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _when(doctor_id: str, start: datetime) -> dict[str, str]:
    return {"doctor": _doctor(doctor_id), "day": _day(start.date()), "time": _time(start.time())}


def _start(s: CallState) -> datetime:
    return datetime.fromisoformat(f"{s.slots['date']}T{s.slots['time']}")


def _options(items: list[tuple[str, datetime]]) -> str:
    return ". ".join(
        f"{i}: {_day(t.date())} at {_time(t.time())} with {_doctor(doc)}"
        for i, (doc, t) in enumerate(items, 1)
    )


# ---------- entry points ----------


def start_call() -> tuple[CallState, str, Decision]:
    reply = render("greet")
    state = CallState(last_reply=reply)
    return state, reply, Decision("", {}, state.step, "greet", {})


def handle_turn(
    state: CallState, text: str, conn: Conn, now: datetime
) -> tuple[CallState, str, Decision]:
    s = CallState.from_json(state.to_json())  # never mutate the caller's state
    p = parse(text, now.date(), Slot(s.expecting) if s.expecting else None)
    action, reply = _turn(s, p, text.lower(), conn, now)
    if action != "repeat":
        s.last_reply = reply
    decision = Decision(p.intent.value, p.entities.as_dict(), s.step, action, dict(s.slots))
    return s, reply, decision


def _turn(s: CallState, p: Parsed, low: str, conn: Conn, now: datetime) -> Reply:
    i, ent = p.intent, p.entities
    if s.ended:
        return "goodbye", render("goodbye")
    if i == Intent.EMERGENCY:
        s.ended = True
        return "emergency", render("emergency")
    if i == Intent.GOODBYE:
        s.ended = True
        return "goodbye", render("goodbye")
    if i == Intent.REPEAT:
        return "repeat", s.last_reply or render("greet")
    if i == Intent.HELP and not ent.as_dict():  # "help me book with Dr Patel..." is a request
        return "help", render("help") + " " + _prompt(s, conn, now)[1]

    m = _DR_WORD.search(low)
    unknown_dr = bool(m and m[1] not in _NOT_A_NAME and not ent.doctor_id and not ent.any_doctor)
    flow = _FLOWS.get(i)
    if flow is None and s.flow is None:
        bookish = ent.doctor_id or ent.specialty or ent.date or ent.time or ent.part_of_day
        flow = "book" if bookish or ent.any_doctor or unknown_dr else None
    yes_at_readback = s.step == "confirming" and _is_yes(p, low)  # "yes, book it"
    started = bool(
        flow and not yes_at_readback and (flow != s.flow or s.step in ("greeting", "done"))
    )
    if started and flow:
        _begin(s, flow)

    if not started:
        handler = {
            "offering": _on_offering,
            "confirming": _on_confirming,
            "choosing": _on_choosing,
            "done": _on_done,
        }.get(s.step)
        if handler and (r := handler(s, p, low, conn, now)):
            return r
        if s.step == "offering":  # CHOICE parsing hides dates: read it again as a plain request
            ent = parse(low, now.date()).entities

    cleared = not started and _clear_requested(s, low)
    new = _merge(s, ent)
    if new or started or cleared:
        s.failures = 0
    if unknown_dr and s.flow == "book":
        s.failures += 1
        if s.failures >= 3:
            s.ended = True
            return "give_up", render("give_up")
        s.expecting = Slot.DOCTOR.value
        return "unknown_doctor", render("unknown_doctor", doctors=_doctor_list())
    if not (new or started or cleared):
        if s.expecting == Slot.DOB.value and parse_dob(low):  # a real date, just not yet past
            return _reprompt(s, conn, now, "future_dob")
        return _reprompt(s, conn, now)
    if s.flow is None:
        s.step = "greeting"
    return _prompt(s, conn, now)


def _begin(s: CallState, flow: Flow) -> None:
    keep = {"name", "dob"}
    if flow != "book" and s.flow in ("cancel", "reschedule"):
        keep.add("ref")  # "actually, reschedule it instead"
    s.flow = flow
    s.step = "collecting" if flow == "book" else "lookup"
    s.slots = {k: v for k, v in s.slots.items() if k in keep}
    s.offers, s.matches, s.failures, s.misses = [], [], 0, 0


def _merge(s: CallState, ent: Entities) -> set[str]:
    """Copy parsed entities into slots; return the slot keys whose value changed."""
    sl = s.slots
    new = {k: v for k, v in ent.as_dict().items() if k in SLOT_KEYS}
    if ent.any_doctor and "doctor_id" not in new:
        new.setdefault("specialty", sl.get("specialty", "general practice"))
    chosen = doctor_by_id(sl.get("doctor_id", ""))
    if chosen and "doctor_id" not in new and new.get("specialty") == chosen.specialty:
        del new["specialty"]  # "Dr Khan ... it's a checkup" agrees with the doctor
    if s.flow == "reschedule":  # a reschedule keeps the original doctor
        new.pop("doctor_id", None)
        new.pop("specialty", None)
    if s.step == "choosing":  # a day/time here only identifies which appointment
        for k in ("date", "time", "part_of_day"):
            new.pop(k, None)
    before = dict(sl)
    if s.step == "offering" and "date" in new and "time" not in new:
        sl.pop("time", None)  # "anything on Friday?" asks about the day, not the old time
    for key, other in [("doctor_id", "specialty"), ("time", "part_of_day")]:
        if key in new:
            sl.pop(other, None)
        if other in new:
            sl.pop(key, None)
    sl.update(new)
    changed = {k for k in SLOT_KEYS if sl.get(k) != before.get(k)}
    identity = {"ref", "name", "dob"} if s.flow == "cancel" else {"ref"}
    if s.flow in ("cancel", "reschedule") and changed & identity:
        if "ref" not in changed:
            sl.pop("ref", None)
        s.step, s.matches, s.offers = "lookup", [], []
    elif changed and s.step in ("offering", "confirming") and s.flow != "cancel":
        s.step, s.offers = "collecting", []
    return changed


def _complete(s: CallState) -> bool:
    """Everything needed for a read-back is present."""
    need = ["date", "time"] if s.flow == "reschedule" else ["name", "dob", "date", "time"]
    has_doctor = "doctor_id" in s.slots or "specialty" in s.slots
    return all(k in s.slots for k in need) and has_doctor


def _clear_requested(s: CallState, low: str) -> bool:
    """After ask_what_to_change (collecting with every slot filled), forget the slot the caller
    names ("the time", "the doctor") so it gets asked again."""
    if s.step != "collecting" or not _complete(s):
        return False
    keys = []
    if re.search(r"\btime\b", low):
        keys.append("time")
    if re.search(r"\b(day|date)\b", low):
        keys.append("date")
    if s.flow == "book" and re.search(r"\b(doctor|dr)\b", low):
        keys += ["doctor_id", "specialty"]
    for k in keys:
        s.slots.pop(k, None)
    return bool(keys)


def _reprompt(s: CallState, conn: Conn, now: datetime, action: str = "reprompt") -> Reply:
    s.failures += 1
    if s.failures >= 3:
        s.ended = True
        return "give_up", render("give_up")
    question = _prompt(s, conn, now)[1].removeprefix("Thanks. ").removeprefix("Sure. ")
    return action, render(action, failures=s.failures - 1) + " " + question


def _ask(s: CallState, action: str, slot: Slot | None, lead: str = "", **kw: object) -> Reply:
    s.expecting = slot.value if slot else None
    return action, lead + render(action, **kw)


# ---------- what to say next, given the state ----------


def _prompt(s: CallState, conn: Conn, now: datetime) -> Reply:
    if s.step == "collecting":
        return _collect(s, conn, now)
    if s.step == "lookup":
        return _lookup(s, conn, now)
    if s.step == "offering":
        offers = [(d, datetime.fromisoformat(t)) for d, t in s.offers]
        return _ask(s, "offer_slots", Slot.CHOICE, options=_options(offers))
    if s.step == "confirming":
        return _readback(s, conn, now)
    if s.step == "choosing":
        return _choices(s, conn, now)
    if s.step == "done" and s.flow:  # we offered to start this flow
        return _ask(s, "not_found", Slot.CONFIRM, failures=1)
    s.step = "greeting"
    return _ask(s, "ask_intent", None)


def _collect(s: CallState, conn: Conn, now: datetime) -> Reply:
    sl = s.slots
    if s.flow == "book":
        if "name" not in sl:
            return _ask(s, "ask_name", Slot.NAME)
        if "dob" not in sl:
            return _ask(s, "ask_dob", Slot.DOB)
        if "doctor_id" not in sl and "specialty" not in sl:
            return _ask(s, "ask_doctor", Slot.DOCTOR, doctors=_doctor_list())
    if "specialty" in sl:  # any doctor of that specialty, even if one was picked earlier
        doctors = [d.id for d in doctors_for(sl["specialty"])]
    else:
        doctors = [sl["doctor_id"]]
    day = date.fromisoformat(sl["date"]) if "date" in sl else None
    t = time.fromisoformat(sl["time"]) if "time" in sl else None

    if day and (day < now.date() or day.weekday() >= 5):
        del sl["date"]
        lead = render("past" if day < now.date() else "weekend")
        return _offer(
            s, conn, now, doctors, datetime.combine(day, t or OPEN), "explain_slot_problem", lead
        )
    if t and (not OPEN <= t < CLOSE or t.minute % SLOT_MINUTES):
        del sl["time"]
        lead = render("closed" if not OPEN <= t < CLOSE else "off_grid")
        if day is None:
            return "explain_slot_problem", _ask(s, "ask_date", Slot.DATE, lead)[1]
        return _offer(s, conn, now, doctors, datetime.combine(day, t), "explain_slot_problem", lead)
    if day is None:
        return _ask(s, "ask_date", Slot.DATE)
    if t is None:
        if pod := sl.get("part_of_day"):
            near = datetime.combine(day, _POD_START[pod])
            return _offer(s, conn, now, doctors, near, "offer_slots")
        return _ask(s, "ask_time", Slot.TIME, day=_day(day))

    start = datetime.combine(day, t)
    if sch.check_slot(start, now):  # only PAST can remain here (earlier today)
        return _offer(s, conn, now, doctors, start, "explain_slot_problem", render("past"))
    free = [d for d in doctors if sch.is_free(conn, d, start)]
    if not free:
        return _offer(s, conn, now, doctors, start, "offer_slots", render("taken"))
    sl["doctor_id"] = free[0]
    s.step = "confirming"
    return _readback(s, conn, now)


def _offer(
    s: CallState,
    conn: Conn,
    now: datetime,
    doctors: list[str],
    near: datetime,
    action: str,
    lead: str = "",
) -> Reply:
    found = sch.nearest_free(conn, doctors, near, now)
    if not found and s.flow == "book" and len(doctors) == 1 and (d := doctor_by_id(doctors[0])):
        found = sch.nearest_free(conn, [x.id for x in doctors_for(d.specialty)], near, now)
    if not found:
        s.step = "collecting"
        s.slots.pop("date", None)
        s.slots.pop("time", None)
        return action, _ask(s, "no_openings", Slot.DATE, lead)[1]
    s.offers = [[d, t.isoformat(timespec="minutes")] for d, t in found]
    s.step = "offering"
    return action, _ask(s, "offer_slots", Slot.CHOICE, lead, options=_options(found))[1]


def _readback(s: CallState, conn: Conn, now: datetime) -> Reply:
    sl = s.slots
    if s.flow == "cancel":
        found = sch.find_upcoming(conn, now, ref=sl["ref"])
        if not found:
            s.step = "lookup"
            sl.pop("ref")
            return _lookup(s, conn, now)
        a = found[0]
        return _ask(s, "confirm_cancel", Slot.CONFIRM, ref=a.ref, **_when(a.doctor_id, a.start))
    kw = _when(sl["doctor_id"], _start(s))
    if s.flow == "reschedule":
        return _ask(s, "confirm_reschedule", Slot.CONFIRM, ref=sl["ref"], **kw)
    dob = date.fromisoformat(sl["dob"]).strftime("%B %-d, %Y")
    return _ask(s, "confirm_booking", Slot.CONFIRM, name=sl["name"], dob=dob, **kw)


def _lookup(s: CallState, conn: Conn, now: datetime) -> Reply:
    sl = s.slots
    if "ref" in sl:
        found = sch.find_upcoming(conn, now, ref=sl["ref"])
    elif "name" in sl and "dob" in sl:
        found = sch.find_upcoming(conn, now, name=sl["name"], dob=date.fromisoformat(sl["dob"]))
    elif "name" in sl:
        return _ask(s, "ask_dob", Slot.DOB)
    elif "dob" in sl:
        return "ask_name", _ask(s, "ask_lookup_name", Slot.NAME)[1]
    else:
        return _ask(s, "ask_lookup", Slot.NAME)
    if not found:
        for k in ("ref", "name", "dob"):
            sl.pop(k, None)
        s.misses += 1
        if s.misses >= 2:  # second miss: offer a new booking instead
            s.flow, s.step, s.misses = "book", "done", 0
            return _ask(s, "not_found", Slot.CONFIRM, failures=1)
        return _ask(s, "not_found", Slot.NAME, failures=0)
    s.misses = 0
    if len(found) > 1:
        s.matches = [a.ref for a in found[:3]]
        s.step = "choosing"
        return _choices(s, conn, now)
    return _use_match(s, found[0], conn, now)


def _choices(s: CallState, conn: Conn, now: datetime) -> Reply:
    appts = [a for ref in s.matches for a in sch.find_upcoming(conn, now, ref=ref)]
    options = _options([(a.doctor_id, a.start) for a in appts])
    return _ask(s, "choose_appointment", Slot.CHOICE, count=len(appts), options=options)


def _use_match(s: CallState, a: sch.Appointment, conn: Conn, now: datetime) -> Reply:
    s.matches = [a.ref]
    s.slots["ref"] = a.ref
    if s.flow == "cancel":
        s.step = "confirming"
        return _readback(s, conn, now)
    s.slots["doctor_id"] = a.doctor_id
    s.step = "collecting"
    return _collect(s, conn, now)


# ---------- step handlers: return None to fall through to slot filling ----------


def _on_offering(s: CallState, p: Parsed, low: str, conn: Conn, now: datetime) -> Reply | None:
    ent, n = p.entities, len(s.offers)
    full = parse(low, now.date()).entities  # with dates, which CHOICE parsing skips
    idx: int | None = None
    if ent.choice is not None:
        idx = ent.choice - 1 if ent.choice > 0 else n - 1
    elif ent.time is not None:
        hhmm = ent.time.strftime("%H:%M")
        day = full.date and full.date.isoformat()
        idx = next(
            (k for k, (_, t) in enumerate(s.offers) if t[11:] == hhmm and day in (None, t[:10])),
            None,
        )
    if idx is None and (full.date or full.time or full.part_of_day):
        # a new day/time, or the taken one again: re-run the slot check (explains + re-offers)
        _merge(s, full)
        s.step, s.offers, s.failures = "collecting", [], 0
        return _collect(s, conn, now)
    if idx is None and p.intent == Intent.AFFIRM:
        idx = 0
    elif idx is None and p.intent == Intent.DENY:
        s.step, s.offers, s.failures = "collecting", [], 0
        for k in ("date", "time", "part_of_day"):
            s.slots.pop(k, None)
        return _ask(s, "ask_date", Slot.DATE, "No problem. ")
    if idx is None or not 0 <= idx < n:
        return None
    doctor_id, iso = s.offers[idx]
    s.slots.update(doctor_id=doctor_id, date=iso[:10], time=iso[11:])
    s.slots.pop("specialty", None)
    s.slots.pop("part_of_day", None)
    s.step, s.offers, s.failures = "confirming", [], 0
    return _readback(s, conn, now)


def _on_confirming(s: CallState, p: Parsed, low: str, conn: Conn, now: datetime) -> Reply | None:
    if _conflicts(s, p.entities):
        return None  # a correction ("no, make it 3:30"): merge it and read back again
    if p.intent == Intent.DENY or (p.intent in _FLOWS and _NEG.search(low)):
        s.failures = 0
        if s.flow == "cancel":
            _finish(s)
            return "ask_intent", render("kept")
        return _what_to_change(s)
    if _is_yes(p, low) and _CORRECTION.search(low):
        if s.flow == "cancel":
            return None  # "yes but keep it": never cancel on a hedged yes; reprompt re-asks
        s.failures = 0
        return _what_to_change(s)  # "sure, but make it 11" with nothing we could parse
    if _is_yes(p, low):
        s.failures = 0
        return _execute(s, conn, now)
    return None


def _conflicts(s: CallState, ent: Entities) -> bool:
    """Does the turn contradict the read-back? Details that agree ("yes, mornings are great",
    "yes, it's a checkup" for a GP) are not corrections."""
    sl = s.slots
    relevant = {"ref", "name", "dob"} if s.flow == "cancel" else set(SLOT_KEYS)
    for k, v in ent.as_dict().items():
        if k not in relevant or sl.get(k) == v:
            continue
        if k == "part_of_day" and "time" in sl and _in_part(sl["time"], v):
            continue  # "morning is great" for 11:00
        doctor = doctor_by_id(sl.get("doctor_id", ""))
        if k == "specialty" and doctor and doctor.specialty == v:
            continue  # "it's a checkup" for a GP
        return True
    return False


def _in_part(hhmm: str, pod: str) -> bool:
    return (
        hhmm < "12:00" if pod == "morning" else hhmm >= ("16:00" if pod == "evening" else "12:00")
    )


def _is_yes(p: Parsed, low: str) -> bool:
    if _NEG.search(low):
        return False
    return p.intent == Intent.AFFIRM or (p.intent in _FLOWS and bool(_YES.search(low)))


def _what_to_change(s: CallState) -> Reply:
    s.step = "collecting"
    key = "ask_what_to_change" if s.flow == "book" else "ask_new_time"
    return "ask_what_to_change", _ask(s, key, Slot.TIME)[1]


def _on_choosing(s: CallState, p: Parsed, low: str, conn: Conn, now: datetime) -> Reply | None:
    appts = [a for ref in s.matches for a in sch.find_upcoming(conn, now, ref=ref)]
    c, full = p.entities.choice, parse(low, now.date()).entities
    picked: list[sch.Appointment] = []
    if c is not None:
        picked = appts[c - 1 : c] if c > 0 else appts[-1:]
    elif full.date or full.time:  # "the Tuesday one", "the 2 pm one"
        picked = [
            a
            for a in appts
            if full.date in (None, a.start.date()) and full.time in (None, a.start.time())
        ]
    if len(picked) != 1:
        return None
    s.failures = 0
    return _use_match(s, picked[0], conn, now)


def _on_done(s: CallState, p: Parsed, low: str, conn: Conn, now: datetime) -> Reply | None:
    if p.intent == Intent.AFFIRM:
        if s.flow:
            _begin(s, s.flow)
            return _prompt(s, conn, now)
        s.step = "greeting"
        return _ask(s, "ask_intent", None)
    if p.intent == Intent.DENY:
        s.ended = True
        return "goodbye", render("goodbye")
    return None


def _finish(s: CallState) -> None:
    s.flow, s.step, s.expecting = None, "done", None
    s.slots = {k: v for k, v in s.slots.items() if k in ("name", "dob")}
    s.offers, s.matches = [], []


def _execute(s: CallState, conn: Conn, now: datetime) -> Reply:
    sl = s.slots
    if s.flow == "cancel":
        ref = sl["ref"]
        sch.cancel(conn, ref)
        _finish(s)
        return "cancelled", render("cancelled", ref=ref)
    start, doctor_id = _start(s), sl["doctor_id"]
    try:
        if s.flow == "reschedule":
            a = sch.reschedule(conn, sl["ref"], start, doctor_id)
        else:
            a = sch.book(conn, sl["name"], date.fromisoformat(sl["dob"]), doctor_id, start)
    except sch.SlotTaken:
        return _offer(s, conn, now, [doctor_id], start, "offer_slots", render("taken"))
    except KeyError:  # appointment vanished (cancelled elsewhere) before we rescheduled it
        s.step = "lookup"
        sl.pop("ref", None)
        return _lookup(s, conn, now)
    flow = s.flow
    _finish(s)
    if flow == "reschedule":
        return "rescheduled", render("rescheduled", ref=a.ref, **_when(a.doctor_id, a.start))
    spelled = " ".join(a.ref.replace("-", ""))
    return "booked", render("booked", ref=a.ref, spelled=spelled)

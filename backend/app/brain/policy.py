from datetime import datetime, time, timedelta

from app.brain.nlu import NLUResult
from app.brain.responses import (
    describe_hours,
    describe_prices,
    describe_services,
    format_date,
    format_phone,
    format_slots,
    format_time,
    render,
)
from app.brain.state import Session, State, TurnResult
from app.services.booking import (
    OPENING_HOURS,
    SERVICES,
    WEEKDAY_NAMES,
    ClinicCalendar,
    SlotTakenError,
    is_within_opening_hours,
)

Part = tuple[str, dict]  # (template name, values for its blanks)

QUESTION_INTENTS = {
    "ask_price", "ask_hours", "ask_discount", "ask_services",
    "ask_location", "cancel", "reschedule",
}
BOOKING_INTENTS = {"book", "ask_availability"}
LEAD_TIME = timedelta(minutes=30)  # earliest we offer is 30 minutes from now


def start_call(session: Session) -> TurnResult:
    reply = render("greet")
    session.last_reply = reply
    return TurnResult(reply=reply, actions=["greet"], state=session.state, trace=["call started"])


def handle_turn(session: Session, nlu: NLUResult, calendar: ClinicCalendar, now: datetime) -> TurnResult:
    today = now.date()
    intents = nlu.intents
    trace = [f"state: {session.state.value}", f"intents: {sorted(intents) or 'none'}"]

    if session.state is State.DONE:
        return _finish(session, [("already_done", {})], nlu, trace)

    found = [nlu.service, nlu.appt_date, nlu.appt_time, nlu.name, nlu.phone, nlu.choice, nlu.relation]
    if not intents and all(item is None for item in found):
        return _not_understood(session, nlu, calendar, now, trace)
    session.fail_count = 0

    if "goodbye" in intents:
        session.state = State.DONE
        started = any(session.slots().values())
        trace.append("global rule: goodbye -> end the call, nothing booked")
        return _finish(session, [("goodbye_no_booking" if started else "goodbye", {})], nlu, trace)

    if "human" in intents:
        session.state = State.DONE
        trace.append("global rule: caller wants a person -> hand off")
        return _finish(session, [("human_handoff", {})], nlu, trace)

    if "repeat" in intents:
        trace.append("global rule: repeat -> say the last reply again")
        reply = session.last_reply or render(_pending(session, today)[0], **_pending(session, today)[1])
        return TurnResult(reply=reply, actions=["repeat"], state=session.state, nlu=nlu, trace=trace)

    parts: list[Part] = []
    pure_question = bool(intents & QUESTION_INTENTS) and not (intents & BOOKING_INTENTS)

    if "urgent" in intents:
        parts.append(("urgent_ack", {}))
    if intents == {"greeting"} and all(item is None for item in found):
        parts.append(("small_talk", {}))
    if intents == {"thanks"}:
        parts.append(("thanks_reply", {}))
    parts += _answer_side_questions(session, nlu, today, trace)

    if session.state is State.OFFER_ALTERNATIVE and session.offered_slots:
        _handle_offer_reply(session, nlu, pure_question, trace)

    if session.state is State.CONFIRM and not pure_question:
        corrections = any(
            item is not None
            for item in (nlu.service, nlu.appt_date, nlu.appt_time, nlu.name, nlu.phone, nlu.relation)
        )
        if not corrections and "affirm" in intents:
            trace.append("confirmation: caller said yes -> book it")
            return _finish(session, parts + _book(session, calendar, now), nlu, trace)
        if not corrections and "deny" in intents:
            trace.append("confirmation: caller said no -> ask what to change")
            return _finish(session, parts + [("ask_what_to_change", {})], nlu, trace)

    before = dict(session.slots())
    _merge(session, nlu, pure_question, trace)
    after = session.slots()
    changed = {key: after[key] for key in after if after[key] != before[key]}
    if changed:
        trace.append(f"slots updated: {changed}")

    if session.state is State.OFFER_ALTERNATIVE and session.offered_slots:
        trace.append("still waiting for a pick from the offered slots")
        parts.append(("repeat_offer", {"options": format_slots(session.offered_slots, today)}))
        return _finish(session, parts, nlu, trace)

    wants_earliest = (
        ("ask_availability" in intents or "urgent" in intents)
        and session.appt_time is None
        and not pure_question
    )
    if wants_earliest:
        start = datetime.combine(session.appt_date, time(0, 0)) if session.appt_date else now
        start = max(start, now + LEAD_TIME)
        slots = calendar.next_free_slots(start, 3)
        trace.append("availability or urgent request without a time -> offer the earliest slots")
        parts += _offer(session, slots, [], today)
        if session.state is State.OFFER_ALTERNATIVE:
            parts[-1] = ("earliest_available", {"options": format_slots(slots, today)})
        return _finish(session, parts, nlu, trace)

    problem = _check_when(session, calendar, now, trace)
    if problem is not None:
        parts += problem
        if session.state is State.OFFER_ALTERNATIVE:
            return _finish(session, parts, nlu, trace)
    elif "ask_availability" in intents and session.appt_date and session.appt_time:
        parts.append((
            "slot_available",
            {"date": format_date(session.appt_date, today), "time": format_time(session.appt_time)},
        ))

    session.state = _next_step(session)
    trace.append(f"first empty slot -> {session.state.value}")
    action, values = _pending(session, today)
    return _finish(session, parts + [(action, values)], nlu, trace)



def _finish(session: Session, parts: list[Part], nlu: NLUResult, trace: list[str]) -> TurnResult:
    reply = " ".join(render(action, **values) for action, values in parts)
    session.last_reply = reply
    return TurnResult(
        reply=reply,
        actions=[action for action, _ in parts],
        state=session.state,
        nlu=nlu,
        trace=trace,
    )


def _next_step(session: Session) -> State:
    if session.service is None:
        return State.ASK_SERVICE
    if session.appt_date is None or session.appt_time is None:
        return State.ASK_WHEN
    if session.name is None:
        return State.ASK_PATIENT
    if session.phone is None:
        return State.ASK_PHONE
    return State.CONFIRM


def _pending(session: Session, today) -> Part:
    """The question the assistant is waiting on in the current state."""
    state = session.state
    if state is State.ASK_SERVICE:
        return "ask_service", {}
    if state is State.ASK_WHEN:
        if session.appt_date is None and session.appt_time is None:
            return "ask_when", {}
        if session.appt_date is not None:
            return "ask_time", {"date": format_date(session.appt_date, today)}
        return "ask_date", {}
    if state is State.OFFER_ALTERNATIVE:
        return "repeat_offer", {"options": format_slots(session.offered_slots, today)}
    if state is State.ASK_PATIENT:
        return "ask_patient", {}
    if state is State.ASK_PHONE:
        return "ask_phone", {}
    if state is State.CONFIRM:
        return "confirm", {
            "service": session.service,
            "date": format_date(session.appt_date, today),
            "time": format_time(session.appt_time),
            "name": session.name,
            "phone": format_phone(session.phone),
        }
    return "goodbye", {}


def _not_understood(session, nlu, calendar, now, trace) -> TurnResult:
    session.fail_count += 1
    trace.append(f"nothing understood (fail count {session.fail_count})")
    if session.fail_count >= 3:
        session.state = State.DONE
        trace.append("3 failures in a row -> hand off to the front desk")
        return _finish(session, [("handoff", {})], nlu, trace)
    if session.state is State.ASK_PHONE:
        return _finish(session, [("bad_phone", {})], nlu, trace)
    first = "not_understood_1" if session.fail_count == 1 else "not_understood_2"
    return _finish(session, [(first, {}), _pending(session, now.date())], nlu, trace)


def _answer_side_questions(session: Session, nlu: NLUResult, today, trace) -> list[Part]:
    intents = nlu.intents
    parts: list[Part] = []

    if "ask_discount" in intents:
        session.discount_asks += 1
        which = "discount_refusal_1" if session.discount_asks == 1 else "discount_refusal_2"
        trace.append(f"global rule: discount asked {session.discount_asks} time(s) -> {which}")
        parts.append((which, {}))

    if "ask_price" in intents:
        service = nlu.service or session.service
        if service:
            parts.append(("answer_price", {"service": service, "price": SERVICES[service]}))
        else:
            parts.append(("price_list", {"prices": describe_prices()}))
        trace.append("global rule: price question -> answer, then re-ask")

    if "ask_hours" in intents:
        if nlu.appt_date is not None:
            weekday = nlu.appt_date.weekday()
            hours = OPENING_HOURS.get(weekday)
            if hours is None:
                parts.append(("closed_day", {"weekday": WEEKDAY_NAMES[weekday]}))
            else:
                parts.append((
                    "answer_hours_day",
                    {
                        "weekday": WEEKDAY_NAMES[weekday],
                        "open": format_time(hours[0]),
                        "close": format_time(hours[1]),
                    },
                ))
        else:
            parts.append(("answer_hours", {"hours": describe_hours()}))
        trace.append("global rule: hours question -> answer, then re-ask")

    if "ask_services" in intents:
        parts.append(("answer_services", {"services": describe_services()}))
    if "ask_location" in intents:
        parts.append(("answer_location", {}))
    if "cancel" in intents or ("reschedule" in intents and session.state is not State.CONFIRM):
        parts.append(("cancel_unsupported", {}))
        trace.append("cancel/reschedule is not supported -> point to the front desk")
    return parts


def _handle_offer_reply(session: Session, nlu: NLUResult, pure_question: bool, trace) -> None:
    """The caller answers 'which slot?': a pick, a different time, or a no."""
    if pure_question:
        return
    intents = nlu.intents
    offered = session.offered_slots
    new_when = nlu.appt_date is not None or nlu.appt_time is not None

    picked = None
    if nlu.choice and 1 <= nlu.choice <= len(offered):
        picked = offered[nlu.choice - 1]
    elif "affirm" in intents and not new_when:
        picked = offered[0]

    if picked is not None:
        session.appt_date, session.appt_time = picked.date(), picked.time()
        session.offered_slots = []
        session.state = State.ASK_WHEN
        trace.append(f"caller picked {picked:%a %d %b %H:%M}")
    elif new_when:
        session.offered_slots = []
        session.state = State.ASK_WHEN
        trace.append("caller asked for a different time -> validate it again")
    elif "deny" in intents:
        session.offered_slots = []
        session.appt_time = None
        session.state = State.ASK_WHEN
        trace.append("caller refused the offered slots -> ask what time suits them")


def _merge(session: Session, nlu: NLUResult, pure_question: bool, trace) -> None:
    """Newer information overwrites older information."""
    if nlu.relation and nlu.relation != session.relation:
        session.relation = nlu.relation
        if session.name and not nlu.name:
            trace.append(f"patient is now the caller's {nlu.relation} -> forget the old name")
            session.name = None
    if nlu.name:
        session.name = nlu.name
    if nlu.phone:
        session.phone = nlu.phone
    if pure_question:
        return  # a service/date/time inside a question is not a booking choice
    if nlu.service:
        session.service = nlu.service
    if nlu.appt_date:
        session.appt_date = nlu.appt_date
    if nlu.appt_time:
        session.appt_time = nlu.appt_time


def _offer(session: Session, slots: list[datetime], reason: list[Part], today) -> list[Part]:
    """Move to OFFER_ALTERNATIVE with these slots (or say there are none)."""
    session.appt_time = None
    if not slots:
        session.state = State.ASK_WHEN
        return reason + [("no_alternatives", {})]
    session.offered_slots = slots
    session.state = State.OFFER_ALTERNATIVE
    return reason + [("offer_alternatives", {"options": format_slots(slots, today)})]


def _check_when(session: Session, calendar: ClinicCalendar, now: datetime, trace) -> list[Part] | None:
    """Return None when the requested date/time is fine, otherwise what to say."""
    today = now.date()
    date_, time_ = session.appt_date, session.appt_time
    if date_ is None:
        return None

    if date_ < today:
        session.appt_date = None
        session.appt_time = None
        trace.append("date is in the past")
        return [("date_in_past", {})]

    if OPENING_HOURS.get(date_.weekday()) is None:
        trace.append(f"{WEEKDAY_NAMES[date_.weekday()]} is a closed day -> offer the next open slots")
        slots = calendar.next_free_slots(datetime.combine(date_, time_ or time(9, 0)), 3)
        session.appt_date = None
        return _offer(session, slots, [("closed_day", {"weekday": WEEKDAY_NAMES[date_.weekday()]})], today)

    if time_ is None:
        return None

    requested = datetime.combine(date_, time_)
    if requested <= now:
        session.appt_time = None
        trace.append("time is in the past")
        return [("time_in_past", {})]

    if not calendar.is_on_grid(requested):
        reason: Part = ("off_grid", {})
    elif not is_within_opening_hours(requested):
        reason = ("outside_hours", {"hours": describe_hours()})
    elif calendar.is_taken(requested):
        reason = ("slot_taken", {"date": format_date(date_, today), "time": format_time(time_)})
    else:
        trace.append("requested time is free")
        return None

    trace.append(f"requested time rejected: {reason[0]} -> offer the nearest free slots")
    slots = calendar.next_free_slots(requested, 3)
    return _offer(session, slots, [reason], today)


def _book(session: Session, calendar: ClinicCalendar, now: datetime) -> list[Part]:
    today = now.date()
    start = datetime.combine(session.appt_date, session.appt_time)
    try:
        calendar.book(start, session.name, session.phone, session.service)
    except SlotTakenError:  # someone else took it while we were talking
        reason = [("slot_taken", {"date": format_date(start.date(), today), "time": format_time(start.time())})]
        return _offer(session, calendar.next_free_slots(start, 3), reason, today)
    except ValueError:
        session.state = State.DONE
        return [("booking_failed", {})]

    session.booking_ref = f"SDC{start:%m%d%H%M}"
    session.state = State.DONE
    return [("booked", {
        "name": session.name,
        "service": session.service,
        "date": format_date(start.date(), today),
        "time": format_time(start.time()),
        "ref": " ".join(session.booking_ref),
    })]
from datetime import datetime

from app.brain import TZ, advance, initial, quote

NOW = datetime(2026, 10, 26, 10, tzinfo=TZ)


def say(state, text):
    return advance(state, text, NOW)


def complete(dining="a la carte"):
    state = initial()
    for text in [
        dining,
        "2026-11-06",
        "6 PM" if dining != "dinner buffet" else "8 PM",
        "4 adults",
        "children aged 3 and 7",
        "indoor",
        "name is Demo Guest",
        "03000000000",
    ]:
        say(state, text)
    return state


def test_complete_and_explicit_confirmation():
    s = complete()
    assert s["stage"] == "review"
    assert say(s, "yes") == "BOOK_ACTION"


def test_correction_invalidates_review():
    s = complete()
    say(s, "6 adults")
    assert s["fields"]["adults"] == 6
    assert s["stage"] == "review"
    assert s["intent"] != "CONFIRM"


def test_price_interruption_preserves_state():
    s = initial()
    say(s, "hi-tea")
    before = dict(s["fields"])
    assert "2,000" in say(s, "price?")
    assert s["fields"] == before and s["awaiting"] == "date"


def test_child_price_boundaries():
    assert (
        quote({"dining": "hi-tea", "adults": 1, "children": [0, 3, 4, 9, 10, 17]})[
            "total"
        ]
        == 8000
    )


def test_invalid_date_and_time():
    s = initial()
    assert "not valid" in say(s, "2026-02-30")
    say(s, "a la carte tomorrow")
    assert "valid time" in say(s, "14 PM")
    say(s, "6 PM")
    assert s["fields"]["time"] == 1080


def test_past_date_and_weekday_buffet():
    s = initial()
    say(s, "2020-01-01")
    assert "date" not in s["fields"]
    say(s, "dinner buffet 2026-10-27")
    assert s["rule"] == "buffet_day"


def test_fixed_slot_and_dining_switch():
    s = complete("hi-tea")
    say(s, "7 PM")
    assert s["rule"] == "fixed_sitting"
    say(s, "6 PM")
    say(s, "normal menu")
    assert s["fields"].get("time") is None


def test_no_children_and_ambiguous_ages():
    s = initial()
    say(s, "2 children")
    assert s["rule"] == "clarification_required"
    say(s, "no children")
    assert s["fields"]["children"] == []


def test_handoff_and_unsupported_speech():
    s = initial()
    say(s, "nut allergy")
    assert s["intent"] == "REQUEST_STAFF"
    for _ in range(3):
        say(s, "unrecognized sentence")
    assert s["rule"] == "repeated_fallback"


def test_roman_urdu():
    s = initial()
    say(s, "a la carte kal aath pm chaar log")
    assert s["fields"]["adults"] == 4
    assert s["fields"]["time"] == 1200
    assert s["fields"]["date"] == "2026-10-27"


def test_cancel_draft():
    s = initial()
    say(s, "cancel")
    assert s["stage"] == "ended"


def test_negative_counts_are_not_silently_positive():
    s = initial()
    say(s, "-2 adults")
    assert s["rule"] == "clarification_required" and "adults" not in s["fields"]

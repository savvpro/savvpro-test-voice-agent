from datetime import date, datetime, time

from app.dialogue.responses import (
    TEMPLATES,
    Responses,
    format_date,
    format_phone,
    format_slot,
    format_time,
    join_words,
    opening_hours_text,
    spell_ref,
)


def test_formatting():
    assert format_date(date(2030, 1, 14)) == "Monday 14 January"
    assert format_time(time(9)) == "9 AM"
    assert format_time(time(14, 20)) == "2:20 PM"
    assert format_time(time(12)) == "12 PM"
    assert format_slot(datetime(2030, 1, 14, 10, 40)) == "Monday 14 January at 10:40 AM"
    assert format_phone("03001234567") == "0300 1234567"
    assert spell_ref("SC-4F7K") == "SC-4F7K, that's S, C, 4, F, 7, K"
    assert join_words(["a"]) == "a"
    assert join_words(["a", "b", "c"], "or") == "a, b or c"


def test_opening_hours_text():
    text = opening_hours_text()
    assert "9 AM to 5 PM" in text
    assert "Saturday from 9 AM to 1 PM" in text
    assert "closed on Sunday" in text


def test_seeded_responses_are_reproducible():
    a, b = Responses(seed=1), Responses(seed=1)
    assert [a("greeting") for _ in range(5)] == [b("greeting") for _ in range(5)]


def test_every_template_has_a_variant_and_is_plain_text():
    for key, variants in TEMPLATES.items():
        assert variants, key
        assert all("<" not in v for v in variants), key  # no SSML


def test_greeting_says_hello_and_goodbye_says_bye():
    assert all(t.startswith("Hello") for t in TEMPLATES["greeting"])
    assert all(t.endswith("bye!") or t.endswith("Bye!") for t in TEMPLATES["goodbye"])

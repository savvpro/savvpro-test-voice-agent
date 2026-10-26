from brain.nlu import parse_text


def test_parses_multiple_slots():
    result = parse_text("Tuesday at 2pm for a checkup", current_state="COLLECTING")
    assert result["slots"]["date"]
    assert result["slots"]["time"] == "14:00"
    assert result["slots"]["reason"] == "checkup"


def test_yes_and_no_are_confirmation_only_in_confirming():
    assert parse_text("yes", "CONFIRMING")["intent"] == "confirm_yes"
    assert parse_text("no", "CONFIRMING")["intent"] == "confirm_no"
    assert parse_text("no", "COLLECTING")["intent"] != "confirm_no"


def test_broad_confirmation_yes_and_no_phrases():
    for text in ("yeah", "ok", "yeah that's right", "sounds good", "go ahead", "book it", "confirm"):
        assert parse_text(text, "CONFIRMING")["intent"] == "confirm_yes"
    for text in ("nah", "not really", "not quite", "wrong", "incorrect", "change it"):
        assert parse_text(text, "CONFIRMING")["intent"] == "confirm_no"


def test_uncertain_confirmation_is_unclear():
    assert parse_text("maybe", "CONFIRMING")["intent"] == "unclear"


def test_ambiguous_hour_is_not_silently_assigned():
    result = parse_text("at 7", "COLLECTING")
    assert "time" not in result["slots"]
    assert result["ambiguous_time"] is True


def test_pending_time_accepts_flexible_meridiem_and_marks_bare_hour_ambiguous():
    ambiguous = parse_text("around 2 ish", "COLLECTING", pending_slot="time")
    assert ambiguous["ambiguous_time"] is True
    assert "time" not in ambiguous["slots"]

    parsed = parse_text("2 p.m", "COLLECTING", pending_slot="time")
    assert parsed["slots"]["time"] == "14:00"


def test_bare_time_formats_require_pending_time():
    assert parse_text("14", "COLLECTING", pending_slot="time")["slots"]["time"] == "14:00"
    assert parse_text("1400", "COLLECTING", pending_slot="time")["slots"]["time"] == "14:00"
    assert "time" not in parse_text("14", "COLLECTING", pending_slot="reason")["slots"]


def test_reason_answer_is_slot_directed_and_filler_only_is_unclear():
    parsed = parse_text("my back hurts", "COLLECTING", pending_slot="reason")
    assert parsed["slots"]["reason"] == "my back hurts"

    filler = parse_text("idk", "COLLECTING", pending_slot="reason")
    assert filler["intent"] == "unclear"
    assert filler["slots"] == {}


def test_bare_name_and_phone_only_fill_their_pending_slots():
    assert "patient_name" not in parse_text(
        "Alex Example", "COLLECTING", pending_slot="time"
    )["slots"]
    assert parse_text(
        "Alex Example", "COLLECTING", pending_slot="patient_name"
    )["slots"]["patient_name"] == "Alex Example"
    assert "phone" not in parse_text(
        "5551234567", "COLLECTING", pending_slot="time"
    )["slots"]


def test_dot_separated_times_parse_with_and_without_meridiem_dots():
    assert parse_text("3.30 pm", "COLLECTING", pending_slot="time")["slots"]["time"] == "15:30"
    assert parse_text("9.30 am", "COLLECTING", pending_slot="time")["slots"]["time"] == "09:30"
    assert parse_text("3.30 p.m", "COLLECTING", pending_slot="time")["slots"]["time"] == "15:30"

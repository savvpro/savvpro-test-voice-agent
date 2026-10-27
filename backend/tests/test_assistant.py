from app.main import _handle_turn, sessions


def setup_function() -> None:
    sessions.clear()


def send(text: str, session_id: str = "test-session"):
    return _handle_turn(session_id, text)


def test_books_available_slot_and_asks_for_missing_details() -> None:
    first = send("I want to book a bath for Luna Saturday at 10 AM")

    assert first.reply == "What is your name for the appointment?"
    assert first.current_step == "owner_name"
    assert first.status == "collecting"

    confirmation = send("My name is Maya")

    assert confirmation.status == "confirming"
    assert confirmation.current_step == "confirm_booking"
    assert "Should I book it?" in confirmation.reply

    completed = send("Yes")
    assert completed.status == "booked"
    assert completed.booking == {
        "service": "bath",
        "pet_name": "Luna",
        "day": "saturday",
        "time": "10:00 AM",
        "owner_name": "Maya",
    }
    assert "Saturday at 10:00 AM" in completed.reply


def test_understands_spoken_time_with_periods() -> None:
    first = send("Book a bath for Lunar Saturday at 10:00 a.m.")

    assert first.booking["time"] == "10:00 AM"
    assert first.booking["day"] == "saturday"
    assert first.reply == "What is your name for the appointment?"


def test_full_grooming_request_is_recognized_as_full_groom() -> None:
    first = send("Full grooming appointment")

    assert first.booking["service"] == "full groom"
    assert first.current_step == "pet_name"
    assert first.reply == "What is your pet's name?"


def test_spa_request_asks_for_supported_service_and_remembers_pet() -> None:
    first = send("Spa for my pet Tyler")

    assert first.status == "collecting"
    assert first.intent == "book"
    assert first.booking["pet_name"] == "Tyler"
    assert first.current_step == "service"
    assert "bath, haircut, nail trim, or full groom" in first.reply

    second = send("Full groom")
    assert second.booking["service"] == "full groom"
    assert second.booking["pet_name"] == "Tyler"
    assert second.current_step == "day"
    assert second.reply == "Which day would you prefer?"


def test_repeated_yes_confirms_booking() -> None:
    send("Book a bath for Luna Saturday at 10 AM")
    confirmation = send("Maya")

    assert confirmation.status == "confirming"
    completed = send("yes yes")

    assert completed.status == "booked"
    assert completed.booking["owner_name"] == "Maya"


def test_weekday_abbreviation_is_not_mistaken_for_pet_name() -> None:
    first = send("Book a full groom for Mon at 2 PM")

    assert first.booking["service"] == "full groom"
    assert first.booking["day"] == "monday"
    assert "pet_name" not in first.booking
    assert first.current_step == "pet_name"


def test_caller_can_provide_time_with_periods_in_follow_up() -> None:
    send("Book a bath for Luna Saturday")
    response = send("10:00 a.m.")

    assert response.booking["time"] == "10:00 AM"
    assert response.current_step == "owner_name"
    assert response.reply == "What is your name for the appointment?"


def test_short_pet_name_answer_is_understood_from_context() -> None:
    send("Book a bath")
    response = send("Coco")

    assert response.booking["pet_name"] == "Coco"
    assert response.current_step == "day"
    assert response.reply == "Which day would you prefer?"


def test_short_owner_name_answer_is_understood_from_context() -> None:
    send("Book a bath for Coco Saturday at 10 AM")
    confirmation = send("Maya")
    assert confirmation.status == "confirming"
    response = send("Yes")

    assert response.status == "booked"
    assert response.booking["owner_name"] == "Maya"
    assert "Maya's appointment for Coco" in response.reply


def test_contextual_name_phrases_are_understood() -> None:
    send("Book a bath")
    pet = send("It's Coco")

    assert pet.booking["pet_name"] == "Coco"

    send("Book a bath for Coco Saturday at 10 AM", session_id="another-session")
    confirmation = send("This is Maya", session_id="another-session")
    assert confirmation.status == "confirming"
    owner = send("Yes", session_id="another-session")

    assert owner.status == "booked"
    assert owner.booking["owner_name"] == "Maya"


def test_unavailable_slot_suggests_fake_availability() -> None:
    send("Book a bath for Luna Monday at 10 AM")
    response = send("My name is Maya")

    assert response.status == "collecting"
    assert response.current_step == "choose_slot"
    assert "isn't available" in response.reply
    assert "Saturday at 10:00 AM" in response.reply
    confirmation = send("Saturday at 10 AM")
    assert confirmation.status == "confirming"
    assert "Should I book it?" in confirmation.reply
    assert send("Yes").status == "booked"


def test_caller_can_correct_time_before_booking() -> None:
    send("Book a bath for Luna Saturday at 10 AM. My name is Maya")
    confirmation = send("Actually, Saturday at 2 PM")

    assert confirmation.status == "confirming"
    assert confirmation.booking["time"] == "2:00 PM"
    assert "Saturday at 2:00 PM" in confirmation.reply
    response = send("Yes")
    assert response.status == "booked"


def test_caller_can_correct_service_in_natural_language() -> None:
    send("Book a bath for Coco Saturday at 10 AM")
    response = send("Actually, make it a nail trim")

    assert response.booking["service"] == "nail trim"
    assert response.current_step == "owner_name"
    assert response.reply == "What is your name for the appointment?"


def test_reschedule_and_cancel_confirmation() -> None:
    send("Book a bath for Luna Saturday at 10 AM")
    send("My name is Maya")
    send("Yes")
    moving = send("Please reschedule to Tuesday at 2 PM")

    assert moving.status == "confirming"
    assert moving.current_step == "confirm_reschedule"
    assert "Should I make that change?" in moving.reply
    moved = send("Yes")
    assert moved.status == "booked"
    assert "moved to Tuesday at 2:00 PM" in moved.reply

    prompt = send("Cancel my appointment")
    assert prompt.current_step == "confirm_cancel"
    assert "say yes or no" in prompt.reply

    cancelled = send("Yes")
    assert cancelled.status == "cancelled"
    assert cancelled.booking == {}


def test_unavailable_reschedule_keeps_original_booking() -> None:
    send("Book a bath for Luna Saturday at 10 AM")
    send("My name is Maya")
    send("Yes")
    unavailable = send("Please reschedule to Monday at 10 AM")

    assert unavailable.status == "collecting"
    assert unavailable.current_step == "reschedule_slot"
    assert unavailable.booking["day"] == "saturday"
    assert unavailable.booking["time"] == "10:00 AM"
    assert "original appointment is unchanged" in unavailable.reply

    confirmation = send("Tuesday at 2 PM")
    assert confirmation.status == "confirming"
    moved = send("Yes")
    assert moved.status == "booked"
    assert moved.booking["day"] == "tuesday"
    assert moved.booking["time"] == "2:00 PM"


def test_declining_booking_does_not_create_appointment() -> None:
    send("Book a bath for Luna Saturday at 10 AM")
    confirmation = send("My name is Maya")

    assert confirmation.status == "confirming"
    declined = send("No")

    assert declined.status == "idle"
    assert declined.booking == {}
    assert "haven't booked anything" in declined.reply


def test_correction_during_confirmation_requires_new_confirmation() -> None:
    send("Book a bath for Luna Saturday at 10 AM")
    send("My name is Maya")
    first_confirmation = send("Yes")
    assert first_confirmation.status == "booked"

    # A new booking makes the service, pet, slot, and owner explicit for the confirmation turn.
    send("Book a haircut for Coco Friday at 1 PM")
    send("My name is Jamie")
    confirmation = send("Actually, make it a nail trim")

    assert confirmation.status == "confirming"
    assert confirmation.booking["service"] == "nail trim"
    assert "a nail trim for Coco" in confirmation.reply
    assert send("Yes").status == "booked"


def test_declining_reschedule_preserves_existing_appointment() -> None:
    send("Book a bath for Luna Saturday at 10 AM")
    send("My name is Maya")
    send("Yes")
    confirmation = send("Please reschedule to Tuesday at 2 PM")
    assert confirmation.status == "confirming"

    declined = send("No")

    assert declined.status == "booked"
    assert declined.booking["day"] == "saturday"
    assert declined.booking["time"] == "10:00 AM"
    assert "original appointment is still booked" in declined.reply


def test_existing_booking_can_be_updated_with_pet_name_confirmation() -> None:
    send("Book a full groom for Luna Tuesday at 2 PM")
    send("Ayesha")
    send("Yes")

    update_prompt = send("My pet's name is Paul")

    assert update_prompt.status == "confirming"
    assert update_prompt.intent == "update"
    assert update_prompt.current_step == "confirm_update"
    assert update_prompt.booking["pet_name"] == "Paul"
    assert "for Paul" in update_prompt.reply

    updated = send("Yes")
    assert updated.status == "booked"
    assert updated.booking["pet_name"] == "Paul"
    assert "updated" in updated.reply


def test_declining_existing_booking_update_restores_original_details() -> None:
    send("Book a bath for Luna Saturday at 10 AM")
    send("Maya")
    send("Yes")
    send("My pet's name is Paul")

    response = send("No")

    assert response.status == "booked"
    assert response.booking["pet_name"] == "Luna"
    assert "still booked" in response.reply


def test_farewell_after_booking_gets_a_friendly_close() -> None:
    send("Book a bath for Luna Saturday at 10 AM")
    send("Maya")
    send("Yes")

    response = send("No thanks, bye")

    assert response.status == "booked"
    assert response.booking["pet_name"] == "Luna"
    assert "Goodbye" in response.reply


def test_unknown_input_does_not_start_booking() -> None:
    response = send("What can you do?")

    assert response.intent == "none"
    assert response.status == "idle"
    assert "book, reschedule, or cancel" in response.reply

import pytest

from app.brain.phone import extract_phone


@pytest.mark.parametrize(
    "text",
    [
        "03211234567",
        "0321-1234567",
        "0321 1234567",
        "+92 321 1234567",
        "my number is 0321 123 4567 thanks",
        "zero three two one one two three four five six seven",
    ],
)
def test_valid_numbers_are_normalised(text):
    result = extract_phone(text)
    assert result.digits == "03211234567"
    assert result.valid


def test_double_and_oh_in_spoken_numbers():
    result = extract_phone("oh three double two one two three four five six seven")
    assert result.digits == "03221234567" and result.valid


def test_short_number_is_flagged_invalid_when_expected():
    result = extract_phone("zero three two one one two three", expecting=True)
    assert result.digits == "0321123"
    assert not result.valid


def test_dates_are_not_mistaken_for_phones():
    assert extract_phone("15 11 2026").digits is None
    assert extract_phone("tomorrow at 4 pm").digits is None


def test_phone_is_removed_from_remaining_text():
    result = extract_phone("book tomorrow my number is 03211234567 at 4 pm")
    assert "0321" not in result.remaining
    assert "tomorrow" in result.remaining and "4 pm" in result.remaining


def test_triple_multiplier():
    assert extract_phone("triple five one two three four five six", expecting=True).digits == "5551234 56".replace(
        " ", ""
    )

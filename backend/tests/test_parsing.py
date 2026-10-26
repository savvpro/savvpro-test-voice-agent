from app import main
from datetime import date, timedelta


def test_spoken_number_parsing():
    assert main._extract_amount("one hundred twenty five dollars") == 125.0
    assert main._extract_amount("two thousand three hundred") == 2300.0
    assert main._extract_amount("four fifty for lunch") == 4.50


def test_currency_detection():
    assert main._currency_for("I paid ¥500 for snacks") == "JPY"
    assert main._currency_for("It was 20 cad") == "CAD"
    assert main._currency_for("spent 30 aud yesterday") == "AUD"
    assert main._currency_for("paid 500 rupees") == "INR"


def test_last_weekend_parsing():
    today = date.today()
    # last weekend should return a Saturday
    saturday = main._extract_date("last weekend", today=today)
    assert saturday is not None
    parsed = date.fromisoformat(saturday)
    assert parsed.weekday() == 5


def test_month_abbrev_parsing():
    today = date.today()
    d = main._extract_date("Oct 5", today=today)
    assert d is not None
    parsed = date.fromisoformat(d)
    assert parsed.month == 10 and parsed.day == 5

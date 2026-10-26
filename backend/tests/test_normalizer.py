import pytest

from app.nlu.normalizer import normalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # casing, punctuation, fillers, stutters
        ("Hello, I'd like to BOOK!", "hello i'd like to book"),
        ("Umm, uh, I want to book", "i want to book"),
        ("I I want want to book", "i want to book"),
        ("   lots    of   space  ", "lots of space"),
        ("I’m Ali", "i'm ali"),
        # "like" and "actually" carry meaning and must survive
        ("I would like Friday", "i would like friday"),
        ("actually make it Friday", "actually make it friday"),
        # number words
        ("three", "3"),
        ("twenty five", "25"),
        ("twenty-one", "21"),
        ("i have two kids", "i have 2 kids"),
        # clock phrases
        ("half past three", "3:30"),
        ("quarter past ten", "10:15"),
        ("quarter to five", "4:45"),
        ("ten to four", "3:50"),
        ("twenty five past 4", "4:25"),
        ("three thirty pm", "3:30 pm"),
        ("ten forty five am", "10:45 am"),
        ("at 3 o'clock", "at 3:00"),
        ("at three oclock", "at 3:00"),
        ("3.30pm", "3:30 pm"),
        ("3PM", "3 pm"),
        ("10 a.m.", "10 am"),
        ("4 p m", "4 pm"),
        # ranges are not clock times
        ("from ten to twelve", "from 10 to 12"),
        ("between 2 to 3", "between 2 to 3"),
        # ordinals: dates vs. option choices
        ("the fifth of november", "the 5th of november"),
        ("on the twenty first", "on the 21st"),
        ("january third", "january 3rd"),
        ("the first one", "the first 1"),
        ("the second slot", "the second slot"),
        ("just a second", "just a second"),
        ("the twenty first slot", "the twenty first slot"),
        # phone numbers read digit by digit
        ("zero three zero zero one two three four five six seven", "03001234567"),
        ("zero three double zero one two three four five six seven", "03001234567"),
        ("zero three zero zero triple five one two three four", "03005551234"),
        ("plus nine two three zero zero one two three four five six seven", "+923001234567"),
        ("0300-1234567", "0300 1234567"),
        # short digit runs are not merged
        ("1 2 3", "1 2 3"),
        # misc
        ("Dr. Saima", "dr saima"),
        ("SC-4F7K", "sc 4f7k"),
        ("", ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("word", ["know", "now", "nothing", "anyone", "someone", "often"])
def test_number_words_only_replace_whole_words(word):
    assert normalize(word) == word


def test_normalize_is_idempotent():
    text = normalize("Umm book me at half past three P.M. on the fifth of May")
    assert normalize(text) == text

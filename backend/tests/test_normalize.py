import pytest

from app.nlu.normalize import normalize


@pytest.mark.parametrize(
    "heard, expected_part",
    [
        ("Three P.M.", "3 pm"),
        ("um I'd like uh a cleaning", "i'd like a cleaning"),
        ("three thirty", "3:30"),
        ("twenty first", "21st"),
        ("five five five one two three four five six seven", "5 5 5 1 2 3 4 5 6 7"),
    ],
)
def test_normalize(heard, expected_part):
    assert expected_part in normalize(heard)


def test_empty_and_fillers_only():
    assert normalize("") == ""
    assert normalize("  um  uh ") == ""

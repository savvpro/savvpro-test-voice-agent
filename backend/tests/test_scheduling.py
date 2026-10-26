import re
import sqlite3
from datetime import date, datetime, timedelta

import pytest

from app import db
from app import scheduling as s
from tests.conftest import NOW, TODAY

TUE = datetime(2026, 10, 27, 11, 0)


def test_check_slot() -> None:
    assert s.check_slot(datetime(2026, 10, 31, 10, 0), NOW) == s.SlotProblem.WEEKEND
    assert s.check_slot(datetime(2026, 11, 2, 8, 30), NOW) == s.SlotProblem.CLOSED
    assert s.check_slot(datetime(2026, 11, 2, 17, 0), NOW) == s.SlotProblem.CLOSED
    assert s.check_slot(datetime(2026, 11, 2, 16, 30), NOW) is None
    assert s.check_slot(datetime(2026, 11, 2, 10, 15), NOW) == s.SlotProblem.OFF_GRID
    assert s.check_slot(datetime(2026, 10, 23, 10, 0), NOW) == s.SlotProblem.PAST


def test_book_and_find(conn: sqlite3.Connection) -> None:
    a = s.book(conn, "Sara Lee", date(1990, 1, 2), "patel", TUE)
    assert re.fullmatch(r"CLN-[A-Z0-9]{4}", a.ref)
    found = s.find_upcoming(conn, NOW, name="  sara lee ", dob=date(1990, 1, 2))
    assert found == [a]
    assert s.find_upcoming(conn, NOW, ref=a.ref) == [a]


def test_double_booking_raises(conn: sqlite3.Connection) -> None:
    s.book(conn, "Sara Lee", date(1990, 1, 2), "patel", TUE)
    with pytest.raises(s.SlotTaken):
        s.book(conn, "Other", date(1991, 1, 2), "patel", TUE)


def test_cancel_frees_slot(conn: sqlite3.Connection) -> None:
    a = s.book(conn, "Sara Lee", date(1990, 1, 2), "patel", TUE)
    assert not s.is_free(conn, "patel", TUE)
    s.cancel(conn, a.ref)
    assert s.is_free(conn, "patel", TUE)
    s.book(conn, "Sara Lee", date(1990, 1, 2), "patel", TUE)


def test_nearest_free_skips_taken(conn: sqlite3.Connection) -> None:
    near = datetime(2026, 10, 27, 15, 0)
    res = s.nearest_free(conn, ["khan"], near, NOW)
    assert 0 < len(res) <= 3
    assert all(d == "khan" and s.check_slot(t, NOW) is None for d, t in res)
    assert res[0][1] not in (near, near + timedelta(minutes=30))
    assert [abs(t - near) for _, t in res] == sorted(abs(t - near) for _, t in res)


def test_reschedule_keeps_ref(conn: sqlite3.Connection) -> None:
    new = datetime(2026, 10, 28, 9, 0)
    a = s.reschedule(conn, "CLN-JC01", new, "khan")
    assert (a.ref, a.doctor_id, a.start) == ("CLN-JC01", "khan", new)
    assert s.find_upcoming(conn, NOW, ref="CLN-JC01") == [a]
    with pytest.raises(s.SlotTaken):
        s.reschedule(conn, "CLN-JC01", datetime(2026, 10, 27, 15, 0), "khan")
    assert s.find_upcoming(conn, NOW, ref="CLN-JC01")[0].start == new


def test_seed_idempotent(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    db.seed(conn, TODAY)
    assert conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == n
    es = s.find_upcoming(conn, NOW, name="Emily Stone", dob=date(1992, 2, 29))
    assert [a.ref for a in es] == ["CLN-ES01", "CLN-ES02"]


def test_refs_avoid_confusable_characters() -> None:
    assert not set(s._REF_CHARS) & set("0O1I")

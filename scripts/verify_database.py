"""Exercise a synthetic session through the running API and verify its actual database writes."""

import argparse
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app import Settings
from backend.database import Allocation, Appointment, Bay, CallerSession, make_engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    engine = make_engine(Settings().database_url)
    assert engine.dialect.name == "postgresql", (
        "This verification requires the wired Postgres database"
    )
    with httpx.Client(base_url=args.base_url, timeout=35) as client:
        assert client.get("/api/health").status_code == 200
        initial_response = client.post("/api/session")
        initial_response.raise_for_status()
        initial = initial_response.json()
        sid = client.cookies.get("bayline_session")
        with Session(engine) as db:
            assert db.get(CallerSession, sid) is not None, (
                "API and verifier are not using the same database"
            )
            assert (
                db.scalar(select(func.count()).select_from(Bay).where(Bay.session_id == sid)) == 2
            )
        print("PASS: running API uses the configured Neon Postgres; two isolated bays seeded.")
        revision = initial["revision"]
        day = initial["appointments"][0]["date"]

        def turn(utterance: str) -> dict:
            nonlocal revision
            response = client.post(
                "/api/turn", json={"turn_id": uuid4().hex, "revision": revision, "text": utterance}
            )
            response.raise_for_status()
            result = response.json()
            revision = result["revision"]
            return result

        turn(f"Reschedule my appointment to {day} at 10 AM")
        moved = turn("yes")
        assert moved["trace"]["action"] == "rescheduled"
        assert moved["appointments"][0]["time"] == "10:00"
        print("PASS: rescheduling persisted through the real API.")
        turn(f"Book a brake inspection for my SUV on {day} at 3 PM")
        booked = turn("yes")
        assert booked["trace"]["action"] == "booked"
        reference = booked["state"]["appointment"]["id"]
        with Session(engine) as db:
            segments = list(
                db.scalars(select(Allocation).where(Allocation.appointment_id == reference))
            )
            assert len(segments) == 2 and segments[0].bay_id == segments[1].bay_id
        print("PASS: 60-minute booking has two contiguous segments on one bay in Neon.")
        turn("Cancel my tyre rotation")
        cancelled = turn("yes")
        assert cancelled["trace"]["action"] == "cancelled"
        original_id = initial["appointments"][0]["id"]
        with Session(engine) as db:
            original = db.get(Appointment, original_id)
            assert original is not None and original.status == "cancelled"
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(Allocation)
                    .where(Allocation.appointment_id == original_id)
                )
                == 0
            )
        recovered = client.post("/api/session").json()
        assert recovered["revision"] == revision
        assert (
            len(recovered["appointments"]) == 1 and recovered["appointments"][0]["id"] == reference
        )
        print(
            "PASS: cancellation releases capacity; a fresh API read recovers the committed booking."
        )
        reset = client.post("/api/session/reset", json={"revision": revision})
        reset.raise_for_status()
        assert len(reset.json()["appointments"]) == 1 and reset.json()["history"] == []
        print("PASS: isolated demo reset restores initial fixtures on Neon.")
    engine.dispose()


if __name__ == "__main__":
    main()

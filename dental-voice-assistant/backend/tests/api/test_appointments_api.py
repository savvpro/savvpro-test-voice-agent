"""API tests — appointments endpoints."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest
from httpx import AsyncClient


def _next_open_day() -> date:
    d = date.today() + timedelta(days=1)
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


OPEN_DAY = _next_open_day()
DAY_STR = OPEN_DAY.isoformat()


@pytest.mark.asyncio
async def test_free_slots_returns_list(client: AsyncClient) -> None:
    r = await client.get("/appointments/slots", params={"date": DAY_STR})
    assert r.status_code == 200
    slots = r.json()
    assert isinstance(slots, list)
    assert len(slots) > 0
    # Each slot has date, start_time, end_time
    assert "start_time" in slots[0]


@pytest.mark.asyncio
async def test_book_appointment(client: AsyncClient) -> None:
    r = await client.post(
        "/appointments",
        json={
            "patient_name": "Sara Khan",
            "patient_phone": "03000000001",
            "service": "checkup",
            "date": DAY_STR,
            "start_time": "09:00:00",
            "end_time": "09:30:00",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["id"]
    assert data["status"] == "confirmed"


@pytest.mark.asyncio
async def test_book_duplicate_returns_409(client: AsyncClient) -> None:
    payload = {
        "patient_name": "Ali Ahmed",
        "patient_phone": "03000000002",
        "service": "cleaning",
        "date": DAY_STR,
        "start_time": "10:00:00",
        "end_time": "10:30:00",
    }
    r1 = await client.post("/appointments", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/appointments", json={**payload, "patient_name": "Other"})
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_list_by_day(client: AsyncClient) -> None:
    # Book one first
    await client.post(
        "/appointments",
        json={
            "patient_name": "Hira Malik",
            "patient_phone": "03000000003",
            "service": "filling",
            "date": DAY_STR,
            "start_time": "11:00:00",
            "end_time": "11:30:00",
        },
    )
    r = await client.get("/appointments", params={"date": DAY_STR})
    assert r.status_code == 200
    assert any(a["start_time"] == "11:00:00" for a in r.json())


@pytest.mark.asyncio
async def test_by_phone(client: AsyncClient) -> None:
    phone = "03000000077"
    await client.post(
        "/appointments",
        json={
            "patient_name": "Usman Raza",
            "patient_phone": phone,
            "service": "whitening",
            "date": DAY_STR,
            "start_time": "13:00:00",
            "end_time": "13:30:00",
        },
    )
    r = await client.get("/appointments/by-phone", params={"phone": phone})
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_cancel(client: AsyncClient) -> None:
    r = await client.post(
        "/appointments",
        json={
            "patient_name": "Fatima Noor",
            "patient_phone": "03000000005",
            "service": "checkup",
            "date": DAY_STR,
            "start_time": "14:00:00",
            "end_time": "14:30:00",
        },
    )
    appt_id = r.json()["id"]
    r2 = await client.delete(f"/appointments/{appt_id}")
    assert r2.status_code == 204


@pytest.mark.asyncio
async def test_cancel_nonexistent_404(client: AsyncClient) -> None:
    r = await client.delete("/appointments/nonexistent-uuid")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_reschedule(client: AsyncClient) -> None:
    # Book original
    r = await client.post(
        "/appointments",
        json={
            "patient_name": "Bilal Chaudhry",
            "patient_phone": "03000000006",
            "service": "cleaning",
            "date": DAY_STR,
            "start_time": "15:00:00",
            "end_time": "15:30:00",
        },
    )
    appt_id = r.json()["id"]

    r2 = await client.put(
        f"/appointments/{appt_id}/reschedule",
        json={
            "new_date": DAY_STR,
            "new_start_time": "15:30:00",
            "new_end_time": "16:00:00",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["start_time"] == "15:30:00"


@pytest.mark.asyncio
async def test_reschedule_nonexistent_404(client: AsyncClient) -> None:
    r = await client.put(
        "/appointments/nonexistent-id/reschedule",
        json={
            "new_date": DAY_STR,
            "new_start_time": "15:30:00",
            "new_end_time": "16:00:00",
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_reschedule_conflict_409(client: AsyncClient) -> None:
    # Book slot A
    r_a = await client.post(
        "/appointments",
        json={
            "patient_name": "Person A",
            "patient_phone": "03000000021",
            "service": "cleaning",
            "date": DAY_STR,
            "start_time": "09:30:00",
            "end_time": "10:00:00",
        },
    )
    assert r_a.status_code == 201
    # Book slot B
    r_b = await client.post(
        "/appointments",
        json={
            "patient_name": "Person B",
            "patient_phone": "03000000022",
            "service": "cleaning",
            "date": DAY_STR,
            "start_time": "10:00:00",
            "end_time": "10:30:00",
        },
    )
    b_id = r_b.json()["id"]
    # Try to reschedule B into slot A (which is taken)
    r_res = await client.put(
        f"/appointments/{b_id}/reschedule",
        json={
            "new_date": DAY_STR,
            "new_start_time": "09:30:00",
            "new_end_time": "10:00:00",
        },
    )
    assert r_res.status_code == 409


@pytest.mark.asyncio
async def test_concurrency_only_one_wins(client: AsyncClient) -> None:
    """10 parallel book() calls for the same slot → exactly one 201."""
    payload = {
        "patient_name": "Concurrent Test",
        "patient_phone": "03000000099",
        "service": "checkup",
        "date": DAY_STR,
        "start_time": "16:00:00",
        "end_time": "16:30:00",
    }

    async def book() -> int:
        r = await client.post("/appointments", json=payload)
        return r.status_code

    results = await asyncio.gather(*[book() for _ in range(10)])
    successes = [s for s in results if s == 201]
    conflicts = [s for s in results if s == 409]
    assert len(successes) == 1
    assert len(conflicts) == 9

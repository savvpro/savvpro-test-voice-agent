# Design: children's specialist clinic appointment assistant

## Scope

The system books, checks, cancels, and reschedules pediatric specialist appointments by a generated daily token schedule. It uses deterministic Python rules; it does not use an LLM.

## Schedule invariants

- Monday through Friday are working days. No past date or weekend is accepted.
- Capacity is 35 tokens per date.
- Opening time is 9:00 AM and consultation duration is 14 minutes.
- Each token's start and end are computed from its sequence number. Token 35 starts at 4:56 PM and ends at 5:10 PM.
- A partial unique index permits at most one active appointment for a date/token pair. `BEGIN IMMEDIATE` serializes token allocation, while cancelled and superseded records remain in history.

## Appointment workflow

Booking collects a guardian name, child name, age, and date; contact details may be supplied when needed. The backend validates the date, obtains the next token, asks for explicit confirmation, and commits only after a transactional allocation succeeds. If availability changes during confirmation, the caller receives a refreshed offer.

Checking, cancellation, and rescheduling require the appointment date, token, and matching guardian name or contact number. Cancellation requires explicit confirmation. Rescheduling confirms the new slot before atomically superseding the old record and creating its replacement.

## Modules

- `backend/app/config.py`: clinic hours, weekdays, capacity, generated slots.
- `backend/app/nlu.py`: regex-based intent and appointment-detail extraction.
- `backend/app/dialogue.py`: deterministic conversational states and validation.
- `backend/app/db.py`: SQLite transactions, uniqueness constraints, appointments, audit log, and call history.
- `backend/app/main.py`: FastAPI endpoints.
- `frontend/src/App.jsx`: voice/text conversation, appointment details, and occupied/available token grid.

## Verification

`backend/tests/test_clinic.py` exercises slot arithmetic, date validation, capacity, persistence, cancellation, rescheduling, concurrency, NLU extraction, and confirmation-before-commit behavior.

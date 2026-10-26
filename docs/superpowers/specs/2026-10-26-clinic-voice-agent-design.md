# Clinic Appointment Voice Agent — Design

## Intent

An assessment submission (see `TASK.md`): a voice assistant that does a real phone job end to end. The job is **booking, rescheduling and cancelling appointments at a small fictional clinic**. The hard rule: the "brain" (what the caller wants, what to ask next, what to do) is our own deterministic code. No LLM makes decisions. Graders reward handling messy callers and a production-quality codebase.

## Goals

- Caller talks in the browser → speech-to-text → Python brain → text-to-speech → caller hears the reply, looping until the call ends.
- Three complete flows: **book**, **reschedule**, **cancel**.
- Handle realistic messy-caller cases (list below), each covered by tests.
- The page shows *what the brain decided* every turn.
- Production hygiene: clean structure, typed code, tests, lint, CI, Docker, config via env vars, no secrets, fake data only.
- Required docs: `README.md` (setup/run), `DESIGN.md` (use case + how the brain decides), `AI_USAGE.md` (tools used, where they helped or erred, token usage).

## Non-goals

- Real telephony (Twilio, etc.). The "phone" is the browser.
- Auth or user accounts, multi-clinic, payments, reminders/SMS.
- Actual cloud deployment (the user picks a host; we ship deploy-ready images).

## Anti-goals (failure even if it "works")

- Any LLM in the decision path.
- Booking without reading back and getting a yes.
- Double-booking a slot.
- Giving medical advice; ignoring an emergency phrase.
- Over-engineered scaffolding the task doesn't need.

## Decided

**Use case & scope (user):** clinic appointments; book + reschedule + cancel.

**Speech (my call, user agreed):** browser Web Speech API for both STT (`SpeechRecognition`, Chrome/Edge) and TTS (`speechSynthesis`). No keys, free. A text box fallback for browsers without STT, and for testing.

**Production level (user: "add everything"):** Docker Compose for local run, GitHub Actions CI (lint + tests for both sides), deploy-ready images.

### Architecture (my call)

```
frontend/  React + TypeScript (Vite)   — mic, transcript, decision panel
backend/   Python 3.11 + FastAPI       — brain + REST API + SQLite
```

API:
- `POST /api/calls` → `{call_id, reply, decision}`: starts a call, returns the greeting.
- `POST /api/calls/{call_id}/turns` body `{text}` → `{reply, decision, ended}`.
- `GET /api/health`.

`decision` = `{intent, entities, state, action, filled_slots}` for the side panel.

Call state is persisted in SQLite (JSON column) so it survives restarts and works with multiple workers. Calls idle > 30 min expire.

### The brain (three stages, pure functions where possible)

1. **NLU (`nlu.py`):** text → `Parsed(intent, entities)`.
   - Intents by keyword/regex rules with priority: `emergency` > `goodbye` > `repeat` > `help` > `cancel` / `reschedule` / `book` > `affirm` / `deny` > `unknown`.
   - Entities: `name` ("my name is X", "this is X", or a bare answer when the brain is asking for a name), `doctor` (fuzzy match on doctor names via `difflib`), `specialty` (synonyms: "GP", "skin" → dermatology, …), `date` (today/tomorrow, weekday, "next Monday", "the 14th", "March 3", ISO), `time` (3pm, 15:00, "half past three", "quarter to 4", "noon", morning/afternoon as a range), `dob`, `booking_ref` (format `CLN-XXXX`).
   - Own small date/time parser on stdlib `datetime`. No heavy NLP dependency, deterministic, fully unit-tested.
2. **Dialogue manager (`dialogue.py`):** `(state, parsed) → (new_state, action)`. Explicit states: `greeting → collecting → offering_slots → confirming → done`, plus `lookup` for reschedule/cancel. Slot filling: any entity in any utterance fills its slot (so "Book Dr Khan Tuesday 3pm for Sara" fills four at once). The next missing required slot decides the question.
3. **NLG (`responses.py`):** action → templated sentence, with a few variants to avoid robotic repetition, plus the last prompt saved for "repeat".

**Scheduling (`scheduling.py`):** clinic hours Mon–Fri 09:00–17:00, 30-min slots, 3–4 fake doctors with specialties. Availability = generated slots minus booked appointments. Booking uses a DB unique constraint on `(doctor_id, start_time)` so races fail safely and the brain offers alternatives.

### Messy cases handled (each with tests)

1. Several details in one sentence.
2. Changing a detail mid-call ("actually make it Wednesday"): the new value overwrites, and the slot check re-runs.
3. "No" at the read-back → ask what to change.
4. Requested slot taken → offer the nearest 3 free slots (same doctor first, then the same specialty).
5. Outside hours, weekend, or past date → explain and re-ask.
6. Unknown doctor → list the available ones; fuzzy-correct close mishearings.
7. Not understood or silent → reprompt with a hint; after 3 failures in a row, apologise and end politely.
8. "Repeat that" / "what?" → repeat the last prompt.
9. Switching intent midway (book → cancel).
10. Lookup failure (no booking matching name+DOB or ref) → retry once, then offer to book new.
11. Emergency phrases (chest pain, can't breathe, bleeding heavily, …) → "call 911 now", end call.
12. Double-booking race → DB constraint, re-offer.
13. Goodbye at any point → end gracefully.

### Frontend (my call)

One page: a call start/end button and a push-to-talk/auto-listen mic, a chat-style transcript, and a "Brain" panel listing each turn's intent, entities, state and action. Text input fallback. Accessible: keyboard-operable, ARIA live region for replies.

### Quality

- Backend: `pip` + `.venv` (pyenv 3.11) for deps, `ruff` lint/format, `mypy`, `pytest` (NLU unit tests, dialogue scenario tests that script whole calls, API tests via FastAPI `TestClient`).
- Frontend: TypeScript strict, ESLint, `vitest` + Testing Library for the main component and API client.
- CI: GitHub Actions running both suites on push/PR.
- Docker: a backend image (uvicorn) and a frontend image (nginx serving the build, proxying `/api`). `docker compose up` runs everything.
- Config via env vars (`DATABASE_PATH`, `CORS_ORIGINS`, `CLINIC_TIMEZONE`). `.env.example` committed, no secrets.
- Structured logging of each turn (no PII beyond fake data).

### Settled after builder check (my calls)

- **Booking requires:** patient name, date of birth, (doctor *or* specialty), date, time. Phone number skipped (fake data, no reminders). The read-back covers all of them; the confirmation gives a `CLN-XXXX` reference.
- **Specialty only / "any doctor":** allowed. The brain picks the first free doctor in that specialty at the requested time, otherwise offers the nearest slots. "Any doctor" with no specialty → the GP.
- **Seed data:** a few fake patients with upcoming appointments, so reschedule/cancel/lookup/slot-taken can be demoed from a fresh DB. If name+DOB matches several upcoming appointments, the brain lists them (up to 3) and asks which one; a booking ref always matches exactly.
- **Build order:** brain + its tests → API → frontend → Docker/CI → docs.

- **Locale (user):** US. Emergency number 911, dates month/day (03/04/1990 = March 4), speech `en-US`, timezone `America/New_York`.

## Left to the builder

Exact phrasing of replies, doctor roster names (fake), slot-offer count, file split inside `backend/app/`, styling details.

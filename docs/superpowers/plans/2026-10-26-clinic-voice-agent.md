# Clinic Voice Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A browser voice assistant for a fictional US clinic that books, reschedules and cancels appointments, with a deterministic rule-based Python brain.

**Architecture:** React page uses Web Speech API for STT/TTS and sends each caller utterance as text to a FastAPI backend. The backend brain is NLU (regex/keyword rules) → dialogue state machine (slot filling) → templated replies, backed by SQLite. Call state is persisted per call in SQLite.

**Tech Stack:** Python 3.11 (pyenv, `.venv`, pip), FastAPI, stdlib `sqlite3`/`datetime`/`difflib`/`zoneinfo`, pytest, ruff, mypy. React 18 + TypeScript + Vite, vitest + Testing Library, ESLint. Node via `nvm use stable`. Docker Compose, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-26-clinic-voice-agent-design.md`

## Global Constraints

- No LLM / AI model anywhere in the decision path. NLU is regex/keyword/`difflib` only.
- Python 3.11. Backend deps: `fastapi`, `uvicorn[standard]` only. Dev deps: `pytest`, `httpx`, `ruff`, `mypy`. No other runtime deps without reason.
- Locale US: emergency number `911`; numeric dates are month/day (`03/04/1990` = March 4 1990); speech lang `en-US`; default timezone `America/New_York`.
- Clinic hours Mon–Fri 09:00–17:00, 30-minute slots (last slot starts 16:30). Datetimes are naive, clinic-local, stored as ISO `YYYY-MM-DDTHH:MM`.
- Booking reference format `CLN-` + 4 uppercase alphanumerics, e.g. `CLN-7K2Q`.
- Booking requires: name, dob, (doctor or specialty), date, time. Always read back and require a yes before booking/cancel/reschedule.
- Fake data only. No secrets committed; config via env: `DATABASE_PATH` (default `clinic.db`), `CORS_ORIGINS` (comma list, default `http://localhost:5173`), `CLINIC_TIMEZONE` (default `America/New_York`).
- Tests use a fixed "now": `2026-10-26 10:00` (a Monday). All time-dependent functions take `today`/`now` as a parameter — never call `datetime.now()` below the API layer.
- Python style: ruff (line length 100), mypy strict-ish (`disallow_untyped_defs`). TypeScript `strict: true`.

## Review Focus

1. **"Tuesday" said on a Tuesday** → means next week's Tuesday? No: means today if the clinic is still open later today, otherwise next week. Test in Task 2 (`test_weekday_today`).
2. **Bare numbers mis-slotted**: "3" while the brain asks for time means 3pm (clinic hours), "3" while it asks for a choice means option 3. Tests in Task 2 (`test_bare_hour_is_pm`) and Task 4 (`test_choice_by_number`).
3. **DOB vs appointment date confusion**: "March 4 1990" must never become an appointment date. Test in Task 2 (`test_past_year_is_dob`).
4. **Empty / whitespace / very long text turn** → reprompt, not a 500. API rejects >500 chars with 422. Tests in Task 5.
5. **Unknown or expired call id** → 404 with a clear message; the frontend offers "start a new call". Tests in Task 5 and Task 6.

## File Structure

```
backend/
  pyproject.toml            ruff/mypy/pytest config
  requirements.txt          runtime deps (pinned)
  requirements-dev.txt      -r requirements.txt + dev tools
  app/
    __init__.py
    config.py               env settings
    clinic.py               static clinic data: doctors, specialties, hours
    parsing.py              date/time/dob parsing (pure)
    nlu.py                  text -> Parsed(intent, entities) (pure)
    db.py                   sqlite connect, schema, seed
    scheduling.py           availability, book, find, cancel, reschedule
    responses.py            action -> reply text templates
    dialogue.py             state machine: handle_turn / start_call
    main.py                 FastAPI app, call persistence, endpoints
  tests/
    conftest.py             fixed NOW, in-memory db fixture
    test_parsing.py test_nlu.py test_scheduling.py test_dialogue.py test_api.py
  Dockerfile
frontend/
  package.json vite.config.ts tsconfig.json eslint.config.js index.html
  src/
    main.tsx App.tsx App.css
    api.ts                  typed REST client
    useSpeech.ts            Web Speech API hook (STT+TTS)
    components/Transcript.tsx BrainPanel.tsx
    App.test.tsx api.test.ts
  Dockerfile nginx.conf
docker-compose.yml
.github/workflows/ci.yml
.env.example .gitignore
README.md DESIGN.md AI_USAGE.md
```

## Execution Waves (parallelism)

- Wave 1: Task 1 (scaffold) — alone.
- Wave 2 (parallel): Task 2 (parsing + NLU), Task 3 (db + scheduling), Task 6 (frontend, against the API contract in Task 5).
- Wave 3: Task 4 (dialogue + responses), then Task 5 (API).
- Wave 4 (parallel): Task 7 (Docker + CI), Task 8 (docs).

---

### Task 1: Backend scaffold, config, clinic data

**Files:**
- Create: `backend/pyproject.toml`, `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/clinic.py`, `backend/tests/conftest.py`, `backend/tests/test_clinic.py`, `.gitignore`, `.env.example`

**Interfaces:**
- Produces:
  - `config.Settings` frozen dataclass `(database_path: str, cors_origins: list[str], timezone: ZoneInfo)`; `config.get_settings() -> Settings` reads env.
  - `clinic.Doctor` frozen dataclass `(id: str, name: str, specialty: str)`.
  - `clinic.DOCTORS: tuple[Doctor, ...]` = `("patel","Dr. Anita Patel","general practice")`, `("khan","Dr. Omar Khan","general practice")`, `("nguyen","Dr. Linh Nguyen","dermatology")`, `("garcia","Dr. Maria Garcia","pediatrics")`.
  - `clinic.SPECIALTY_SYNONYMS: dict[str, str]` word → specialty (`gp`, `general`, `family`, `checkup`, `check-up`, `physical` → general practice; `skin`, `rash`, `dermatologist`, `dermatology`, `acne` → dermatology; `child`, `kid`, `pediatrician`, `pediatrics`, `baby` → pediatrics).
  - `clinic.OPEN = time(9,0)`, `clinic.CLOSE = time(17,0)`, `clinic.SLOT_MINUTES = 30`, `clinic.EMERGENCY_NUMBER = "911"`, `clinic.CLINIC_NAME = "Maple Street Clinic"`.
  - `clinic.doctor_by_id(id: str) -> Doctor | None`, `clinic.doctors_for(specialty: str) -> list[Doctor]`.
  - `tests/conftest.py`: `NOW = datetime(2026,10,26,10,0)`, `TODAY = NOW.date()`, fixture `conn` → in-memory sqlite (uses `db.connect(":memory:")` + `db.init_db`; skip-import guarded until Task 3 lands: define fixture body importing inside function).

- [ ] **Step 1:** `cd backend && ~/.pyenv/versions/3.11.16/bin/python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt` (pin current versions in requirements files).
- [ ] **Step 2: Write test** `test_clinic.py`: `assert len(clinic.doctors_for("general practice")) == 2`; `assert clinic.doctor_by_id("nguyen").specialty == "dermatology"`; `assert clinic.doctor_by_id("nope") is None`; `get_settings()` with monkeypatched `CORS_ORIGINS="a,b"` → `["a","b"]`.
- [ ] **Step 3:** Implement; run `.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/mypy app` → all pass.
- [ ] **Step 4: Commit** `chore: backend scaffold, config and clinic data`.

---

### Task 2: Parsing + NLU (pure functions)

**Files:**
- Create: `backend/app/parsing.py`, `backend/app/nlu.py`, `backend/tests/test_parsing.py`, `backend/tests/test_nlu.py`

**Interfaces:**
- Consumes: `clinic.DOCTORS`, `clinic.SPECIALTY_SYNONYMS`.
- Produces:
  - `parsing.PartOfDay = Literal["morning", "afternoon"]`
  - `parsing.parse_date(text: str, today: date) -> date | None` — today/tomorrow/day after tomorrow; weekday names ("Tuesday" / "this Tuesday" → first occurrence ≥ today; **"next Tuesday" → that weekday in the following Mon–Sun calendar week**, so from Mon 10-26 "next Tuesday" = 11-03); "the 14th" (this month if ≥ today else next month); "November 3", "Nov 3rd", "3rd of November"; "11/3", "11/3/2026", ISO `2026-11-03`. Year omitted → next future occurrence.
  - `parsing.parse_time(text: str) -> time | PartOfDay | None` — "3pm", "3:30 pm", "15:00", "3 o'clock", "half past three", "quarter past/to four", "noon", "morning", "afternoon". Bare hour 1–6 without am/pm → pm; 7–11 → am; 12 → noon.
  - `parsing.parse_dob(text: str) -> date | None` — any explicit full date with a 4-digit year (words or `MM/DD/YYYY`), year ≤ current.
  - `parsing.number_words: dict[str,int]` one..twelve, used by time parsing.
  - `nlu.Intent(StrEnum)`: `EMERGENCY, GOODBYE, REPEAT, HELP, BOOK, RESCHEDULE, CANCEL, AFFIRM, DENY, UNKNOWN`.
  - `nlu.Slot(StrEnum)`: `NAME, DOB, DOCTOR, DATE, TIME, REF, CONFIRM, CHOICE` — what the brain is currently asking for.
  - `nlu.Entities` dataclass, all default None: `name: str|None, dob: date|None, doctor_id: str|None, specialty: str|None, any_doctor: bool=False, date: date|None, time: time|None, part_of_day: PartOfDay|None, ref: str|None, choice: int|None`; method `as_dict() -> dict[str, str]` (non-empty only, ISO strings).
  - `nlu.Parsed` dataclass `(intent: Intent, entities: Entities)`.
  - `nlu.parse(text: str, today: date, expecting: Slot | None = None) -> Parsed`.
- Rules (decisions the implementer can't infer):
  - Intent priority: EMERGENCY > GOODBYE > REPEAT > HELP > CANCEL > RESCHEDULE > BOOK > DENY > AFFIRM > UNKNOWN. Emergency phrases: chest pain, can't/cannot breathe, trouble breathing, heavy bleeding / bleeding a lot, unconscious, passed out, stroke, heart attack, overdose, suicidal / kill myself. "reschedule"/"move my appointment"/"change my appointment" → RESCHEDULE; "cancel" → CANCEL; "book"/"appointment"/"see a doctor"/"schedule" → BOOK. GOODBYE only for "bye/goodbye/that's all/hang up/nothing else", not bare "no".
  - A date with a 4-digit year in the past, or any date when `expecting == DOB`, goes to `dob`, never `date`.
  - Name: "my name is X", "this is X", "I'm X" (only if followed by capitalised/2-word name, not "I'm looking"), "name's X", "for X" after booking words is NOT a name. When `expecting == NAME` and no other entity/intent found, the whole cleaned text (title-cased, ≤4 words, letters/'/- only) is the name.
  - Doctor: "Dr./doctor <word>" fuzzy-matched by `difflib.get_close_matches(cutoff=0.7)` against last names; bare last name match too. "any doctor"/"anyone"/"first available" → `any_doctor=True`.
  - Ref: regex `CLN[\s-]?([A-Z0-9]{4})` case-insensitive, normalised `CLN-XXXX`; also spoken "C L N 7 K 2 Q" (strip spaces).
  - Choice (only when `expecting == CHOICE`): "first/1/one/the first one" → 1, second → 2, third → 3, "last" → -1. Otherwise a time like "the 3:30 one" is a time.
  - AFFIRM: yes, yeah, yep, correct, that's right, sure, sounds good, please do, ok. DENY: no, nope, not quite, that's wrong, incorrect.

- [ ] **Step 1: Write failing tests** (`today = date(2026,10,26)` Monday):
  - `test_relative_dates`: tomorrow → 10-27; "day after tomorrow" → 10-28; "Friday" → 10-30; "next Monday" → 11-02; "the 14th" → 11-14; "November 3rd" → 11-03; "11/3" → 11-03; "2026-11-03" → 11-03.
  - `test_weekday_today`: "Monday" with today Monday → 10-26.
  - `test_times`: "3pm"→15:00, "3:30 pm"→15:30, "15:00"→15:00, "half past three"→15:30, "quarter to four"→15:45, "noon"→12:00, "in the morning"→"morning", "9 am"→09:00.
  - `test_bare_hour_is_pm`: `parse_time("at 3")` → 15:00; "at 10" → 10:00.
  - `test_dob`: "March 4 1990"→1990-03-04; "03/04/1990"→1990-03-04; "4th of March 1990"→1990-03-04.
  - `test_past_year_is_dob`: `parse("I was born March 4 1990", today).entities` has `dob=1990-03-04`, `date is None`.
  - `test_intents`: table of (text, intent) incl. "I'd like to book an appointment"→BOOK, "I need to cancel"→CANCEL, "can I move my appointment"→RESCHEDULE, "yes that's right"→AFFIRM, "no"→DENY, "bye"→GOODBYE, "sorry what?"→REPEAT, "I have chest pain"→EMERGENCY, "I have chest pain, cancel my appointment"→EMERGENCY, "blah"→UNKNOWN.
  - `test_multi_entity`: "Book me with Dr Khan next Tuesday at 3pm, my name is Sara Lee" → BOOK, doctor_id "khan", date 11-03, time 15:00, name "Sara Lee".
  - `test_fuzzy_doctor`: "doctor nguen" → "nguyen"; "doctor smith" → None.
  - `test_specialty`: "something for a skin rash" → specialty "dermatology"; "any doctor is fine" → any_doctor True.
  - `test_bare_name_when_expecting`: `parse("sara lee", today, Slot.NAME)` → name "Sara Lee"; same text with no expecting → name None.
  - `test_ref`: "my reference is cln 7k2q" → "CLN-7K2Q"; "C L N 7 K 2 Q" → "CLN-7K2Q".
  - `test_choice`: `parse("the second one", today, Slot.CHOICE).entities.choice == 2`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_parsing.py tests/test_nlu.py -q` → FAIL (import errors).
- [ ] **Step 3:** Implement `parsing.py` then `nlu.py`.
- [ ] **Step 4:** Run tests + `ruff check . && mypy app` → PASS.
- [ ] **Step 5: Commit** `feat(brain): rule-based date/time parsing and NLU`.

---

### Task 3: Database + scheduling

**Files:**
- Create: `backend/app/db.py`, `backend/app/scheduling.py`, `backend/tests/test_scheduling.py`

**Interfaces:**
- Consumes: `clinic.*`.
- Produces:
  - `db.connect(path: str) -> sqlite3.Connection` (`row_factory=sqlite3.Row`, `check_same_thread=False`, `PRAGMA foreign_keys=ON`, WAL when not `:memory:`).
  - `db.init_db(conn) -> None` — idempotent schema:
    - `appointments(id INTEGER PRIMARY KEY, ref TEXT UNIQUE NOT NULL, patient_name TEXT NOT NULL, dob TEXT NOT NULL, doctor_id TEXT NOT NULL, start TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'booked' CHECK(status IN ('booked','cancelled')))`
    - `CREATE UNIQUE INDEX IF NOT EXISTS one_booking_per_slot ON appointments(doctor_id, start) WHERE status='booked'`
    - `calls(id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT NOT NULL)`
  - `db.seed(conn, today: date) -> None` — only if appointments empty. Fake patients: "John Carter" dob 1985-07-12 with Dr. Patel next weekday 10:00 (ref `CLN-JC01`); "Emily Stone" dob 1992-02-29 two appointments: Dr. Nguyen next weekday 14:00 (`CLN-ES01`) and Dr. Patel the weekday after 11:00 (`CLN-ES02`); "Sara Lee" none. Also fill Dr. Khan's next-weekday 15:00 and 15:30 with filler patient "Alex Morgan" dob 1970-01-01 (`CLN-AM01`, `CLN-AM02`) so "slot taken" is demoable.
  - `scheduling.Appointment` frozen dataclass `(ref: str, patient_name: str, dob: date, doctor_id: str, start: datetime)`.
  - `scheduling.SlotProblem(StrEnum)`: `PAST, WEEKEND, CLOSED, OFF_GRID`.
  - `scheduling.check_slot(start: datetime, now: datetime) -> SlotProblem | None` (OFF_GRID = minute not multiple of 30).
  - `scheduling.is_free(conn, doctor_id: str, start: datetime) -> bool`.
  - `scheduling.nearest_free(conn, doctor_ids: list[str], near: datetime, now: datetime, limit: int = 3) -> list[tuple[str, datetime]]` — valid free slots for any listed doctor, within 14 days of `near`, sorted by `abs(start - near)` then start then doctor order; at most one entry per start time.
  - `scheduling.SlotTaken(Exception)`.
  - `scheduling.book(conn, name: str, dob: date, doctor_id: str, start: datetime) -> Appointment` — generates unique ref with `secrets.choice`; raises `SlotTaken` on `sqlite3.IntegrityError` from the unique index.
  - `scheduling.find_upcoming(conn, now: datetime, *, ref: str | None = None, name: str | None = None, dob: date | None = None) -> list[Appointment]` — booked, start ≥ now, sorted by start; by ref, or by name (case-insensitive, trimmed) AND dob.
  - `scheduling.cancel(conn, ref: str) -> None`.
  - `scheduling.reschedule(conn, ref: str, new_start: datetime, doctor_id: str) -> Appointment` — single transaction; keeps ref; raises `SlotTaken`.

- [ ] **Step 1: Write failing tests** (`now = NOW` from conftest, fixture `conn` seeded with `db.seed(conn, TODAY)`):
  - `test_check_slot`: Sat → WEEKEND; Mon 08:30 → CLOSED; 17:00 → CLOSED; 16:30 → None; 10:15 → OFF_GRID; yesterday → PAST.
  - `test_book_and_find`: book Sara Lee → ref matches `^CLN-[A-Z0-9]{4}$`; `find_upcoming(name="  sara lee ", dob=...)` returns it.
  - `test_double_booking_raises`: booking the same doctor+start twice → `SlotTaken`.
  - `test_cancel_frees_slot`: cancel then `is_free` True and rebooking works.
  - `test_nearest_free_skips_taken`: near Dr Khan's seeded 15:00 → first result is not 15:00/15:30 for khan, results ≤ 3, all pass `check_slot`.
  - `test_reschedule_keeps_ref`.
  - `test_seed_idempotent`: seeding twice leaves count unchanged; Emily Stone has 2 upcoming.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run tests + ruff + mypy → PASS.
- [ ] **Step 5: Commit** `feat(scheduling): sqlite storage, availability and booking`.

---

### Task 4: Dialogue manager + responses

**Files:**
- Create: `backend/app/responses.py`, `backend/app/dialogue.py`, `backend/tests/test_dialogue.py`

**Interfaces:**
- Consumes: Task 2 `nlu.parse/Intent/Slot/Entities`, Task 3 `scheduling.*`, `clinic.*`.
- Produces:
  - `dialogue.CallState` dataclass: `flow: Literal["book","reschedule","cancel"] | None = None`, `step: str = "greeting"`, `slots: dict[str, str]` (ISO strings: `name, dob, doctor_id, specialty, date, time, part_of_day, ref`), `expecting: str | None`, `offers: list[list[str]]` (`[doctor_id, iso_start]`), `matches: list[str]` (refs), `last_reply: str = ""`, `failures: int = 0`, `ended: bool = False`. Methods `to_json() -> str`, `CallState.from_json(s: str) -> CallState`.
  - `dialogue.Decision` dataclass: `intent: str, entities: dict[str, str], state: str, action: str, slots: dict[str, str]`; `as_dict()`.
  - `dialogue.start_call() -> tuple[CallState, str, Decision]` — greeting: "Thanks for calling Maple Street Clinic. I can book, reschedule or cancel an appointment. How can I help?"
  - `dialogue.handle_turn(state: CallState, text: str, conn: sqlite3.Connection, now: datetime) -> tuple[CallState, str, Decision]` — never raises on any text.
  - `responses.render(action: str, **kw: object) -> str` — one template (or a short list rotated deterministically by `failures`) per action.
- Steps (values of `state.step`): `greeting, collecting, offering, confirming, lookup, choosing, done`.
- Actions (strings; shown in UI): `greet, ask_intent, ask_name, ask_dob, ask_doctor, ask_date, ask_time, offer_slots, confirm_booking, booked, ask_lookup, choose_appointment, confirm_cancel, cancelled, confirm_reschedule, rescheduled, not_found, explain_slot_problem, unknown_doctor, ask_what_to_change, repeat, help, reprompt, emergency, goodbye, give_up`.
- Behaviour rules:
  - Every turn: parse with `expecting=state.expecting`, merge all non-null entities into slots (new value overwrites → handles mid-call changes; changing date/time/doctor clears `offers` and returns to `collecting`).
  - EMERGENCY at any step → reply tells them to hang up and call 911, `ended=True`. GOODBYE → polite end. REPEAT → `last_reply` again (failures unchanged). HELP → explain the three things it can do and re-ask the current question.
  - Flow switch: BOOK/CANCEL/RESCHEDULE intent different from current flow (and not during `confirming` with an AFFIRM) switches flow, keeping name/dob.
  - Book: required order name → dob → doctor (doctor_id, specialty or any_doctor; any_doctor without specialty → general practice) → date → time. If `part_of_day` only, offer nearest slots at 09:00 (morning) / 13:00 (afternoon). Then `check_slot`; problem → `explain_slot_problem` + `offer_slots` near it. Taken → `offer_slots` (same doctor first; if none, same specialty). Free → `confirming` with read-back: "So that's {name}, born {dob:%B %-d, %Y}, with {doctor} on {date:%A, %B %-d} at {time:%-I:%M %p}. Shall I book it?" AFFIRM → `book()`; `SlotTaken` → `offer_slots`; success → `booked` with ref spelled out, ask "anything else?" (step `done`, flow None). DENY → `ask_what_to_change`.
  - Offering: caller picks by CHOICE number, by saying a time matching an offer, or AFFIRM (= first offer). Picked offer → `confirming`.
  - Cancel/reschedule: `lookup` asks for ref, or name + dob. One match → confirm (cancel) or collect new date/time then confirm (reschedule, same doctor). Several → `choosing` lists up to 3 ("1: Tuesday November 3 at 2 PM with Dr. Linh Nguyen ..."). None → `not_found`, one retry, then offer to book a new one.
  - Unknown doctor name mentioned (e.g. "Dr Smith" — NLU gives no doctor_id but text contains "dr|doctor <word>") → `unknown_doctor` listing doctors.
  - UNKNOWN with no new entities → `reprompt` (failures+1); after 3 consecutive → `give_up`, ended. Any turn that fills a slot resets failures to 0. Empty/whitespace text counts as a failure.
- [ ] **Step 1: Write failing scenario tests**, each scripting a whole call via a helper `talk(conn, *lines) -> list[tuple[str, Decision]]` using `NOW`:
  - `test_happy_booking_one_sentence`: "Hi, I want to book with Dr Patel tomorrow at 2pm, my name is Sara Lee", "March 4 1990", "yes" → final action `booked`, reply contains "CLN-", DB has 1 new appointment.
  - `test_step_by_step_booking`: "book an appointment", "Sara Lee", "03/04/1990", "a skin check", "Friday", "10am", "yes" → `booked` with Dr. Nguyen.
  - `test_change_time_midway`: … at read-back say "actually make it 3:30" → read-back shows 3:30 PM; "yes" → booked at 15:30.
  - `test_deny_at_readback`: "no" → action `ask_what_to_change`.
  - `test_slot_taken_offers_alternatives`: Dr Khan next weekday 15:00 (seeded) → action `offer_slots`, 3 offers none equal 15:00; "the second one", "yes" → booked at offer 2.
  - `test_weekend_and_closed`: "Saturday" → `explain_slot_problem`; "at 8pm" → `explain_slot_problem`.
  - `test_unknown_doctor`: "Dr Smith" → `unknown_doctor`, reply lists "Patel".
  - `test_reprompt_then_give_up`: three "blah" → actions reprompt, reprompt, give_up; `ended`.
  - `test_repeat`: "what?" returns previous reply verbatim.
  - `test_cancel_by_ref`: "cancel my appointment", "CLN-JC01", "yes" → `cancelled`; `find_upcoming(ref="CLN-JC01")` empty.
  - `test_cancel_multiple_matches`: "cancel", "Emily Stone", "February 29 1992" → `choose_appointment` listing 2; "the first one", "yes" → cancelled CLN-ES01.
  - `test_reschedule`: "reschedule", "CLN-JC01", "next Wednesday at 11", "yes" → `rescheduled`, same ref, new start.
  - `test_not_found_then_offer_book`: lookup fails twice → reply offers to book.
  - `test_switch_book_to_cancel`: "book" then "actually I want to cancel" → flow `cancel`, action `ask_lookup`.
  - `test_emergency`: mid-booking "I'm having chest pain" → action `emergency`, reply contains "911", ended.
  - `test_choice_by_number`: during offering, "3" → third offer chosen (not 3pm).
  - `test_empty_text`: "   " → `reprompt`, no exception.
  - `test_state_roundtrip`: `CallState.from_json(s.to_json()) == s` after a mid-booking turn.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `responses.py`, then `dialogue.py`.
- [ ] **Step 4:** Run full backend suite + ruff + mypy → PASS.
- [ ] **Step 5: Commit** `feat(brain): dialogue state machine and replies`.

---

### Task 5: FastAPI app

**Files:**
- Create: `backend/app/main.py`, `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `dialogue.start_call/handle_turn/CallState`, `db.connect/init_db/seed`, `config.get_settings`.
- Produces (HTTP contract — the frontend depends on this exactly):
  - `GET /api/health` → `{"status":"ok"}`.
  - `POST /api/calls` → 201 `{"call_id": str(uuid4), "reply": str, "decision": Decision, "ended": false}`.
  - `POST /api/calls/{call_id}/turns` body `{"text": str}` (max 500 chars, pydantic `Field(max_length=500)`) → 200 `{"call_id", "reply", "decision", "ended"}`; 404 `{"detail": "Call not found or expired"}` for unknown/expired/ended calls; 422 for >500 chars.
  - `Decision` JSON: `{"intent": str, "entities": {str: str}, "state": str, "action": str, "slots": {str: str}}`.
  - `app.main.create_app(db_path: str | None = None) -> FastAPI`; module-level `app = create_app()`.
- Rules: lifespan opens conn, `init_db`, `seed(today)`. `now` = `datetime.now(settings.timezone).replace(tzinfo=None, second=0, microsecond=0)` — the only place wall-clock is read; tests override via `app.state.clock: Callable[[], datetime]`. Calls idle > 30 min → expired (404). Per-call state saved after each turn in `calls` table (upsert). A `threading.Lock` around turn handling (`# ponytail: global lock, single sqlite writer; per-call locks if throughput matters`). CORS from settings. Log one structured line per turn: call_id, intent, action (no full text).
- [ ] **Step 1: Write failing tests** with `TestClient(create_app(":memory:"))` and clock fixed to `NOW`:
  - `test_health`.
  - `test_start_call_returns_greeting` (201, "Maple Street Clinic" in reply, decision.action == "greet").
  - `test_full_booking_over_http` (3 turns from the Task 4 happy path → `booked`).
  - `test_unknown_call_404`.
  - `test_expired_call_404` (advance clock 31 min).
  - `test_ended_call_404` (emergency turn then another turn → 404).
  - `test_text_too_long_422`.
  - `test_empty_text_reprompts` (200, action `reprompt`).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Full suite + ruff + mypy → PASS; `.venv/bin/uvicorn app.main:app` starts and `curl -X POST localhost:8000/api/calls` returns a greeting.
- [ ] **Step 5: Commit** `feat(api): FastAPI call endpoints with persisted call state`.

---

### Task 6: Frontend

**Files:**
- Create: everything under `frontend/` listed in File Structure (except Dockerfile/nginx.conf).

**Interfaces:**
- Consumes: Task 5 HTTP contract (verbatim above). Dev proxy: Vite `server.proxy['/api'] = 'http://localhost:8000'`; API base `import.meta.env.VITE_API_BASE ?? ''`.
- Produces:
  - `api.ts`: types `Decision`, `TurnResponse`; `startCall(): Promise<TurnResponse>`; `sendTurn(callId: string, text: string): Promise<TurnResponse>`; throws `ApiError(status, message)` on non-2xx.
  - `useSpeech.ts`: `useSpeech(): { supported: boolean; listening: boolean; listen(): Promise<string>; stop(): void; speak(text: string): Promise<void>; }` — `lang = 'en-US'`, `interimResults=false`, resolves `''` on no-speech; `speak` resolves on `onend`; cancels speech before listening (no self-hearing).
- UI rules: header with clinic name; "Start call"/"End call" button; when in a call, a large mic button (push to talk; hands-free toggle that auto-listens after each spoken reply until `ended`); text input + Send fallback (always available, required when `!supported`); `Transcript` (caller/assistant bubbles, `aria-live="polite"`); `BrainPanel` showing per-turn intent, action, state, entity chips and current filled slots, newest first. On `ApiError` 404 show "This call has ended or expired" + "Start new call". Network errors show an inline retry message, never crash. Mobile-friendly single column under 768px; two columns (transcript | brain) above. Use the frontend-design skill for a calm clinical look (no default Vite styling).
- [ ] **Step 1:** `nvm use stable`; scaffold Vite react-ts; add vitest, @testing-library/react, @testing-library/user-event, jsdom, eslint.
- [ ] **Step 2: Write failing tests:**
  - `api.test.ts`: `sendTurn` posts JSON to `/api/calls/abc/turns` (mock `fetch`), returns parsed body; 404 → rejects `ApiError` with status 404.
  - `App.test.tsx` (mock `api` and `useSpeech` with `supported:false`): click "Start call" → greeting visible; type "book" + Send → assistant reply and brain panel shows action text; mocked 404 → "Start new call" button visible.
- [ ] **Step 3:** Run `npm test -- --run` → FAIL. **Step 4:** Implement. **Step 5:** `npm test -- --run && npm run lint && npm run build` → PASS.
- [ ] **Step 6: Commit** `feat(frontend): voice call UI with brain decision panel`.

---

### Task 7: Docker + CI

**Files:**
- Create: `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `docker-compose.yml`, `.github/workflows/ci.yml`, `.dockerignore` files.

- Backend image: `python:3.11-slim`, non-root user, `pip install -r requirements.txt`, `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000`, `DATABASE_PATH=/data/clinic.db` on a named volume, healthcheck hitting `/api/health`.
- Frontend image: multi-stage `node:lts-alpine` build → `nginx:alpine` serving `dist`, `location /api/ { proxy_pass http://backend:8000; }`, SPA fallback.
- Compose: `backend` + `frontend` (port `8080:80`), frontend `depends_on` backend healthy.
- CI: on push + PR; job `backend` (setup-python 3.11, pip cache, ruff check, ruff format --check, mypy app, pytest); job `frontend` (setup-node lts, `npm ci`, lint, test, build); job `docker` builds both images (`docker compose build`) after the two pass.
- [ ] **Step 1:** Write files. **Step 2:** `docker compose up --build -d` → `curl -s localhost:8080/api/health` returns `{"status":"ok"}` and `curl -s -X POST localhost:8080/api/calls` returns a greeting; `docker compose down`. **Step 3:** Validate workflow YAML parses (`python -c "import yaml..."` or `docker run rhysd/actionlint` if available). **Step 4: Commit** `ci: docker compose and github actions`.

---

### Task 8: Docs

**Files:**
- Modify: `README.md` (replace the assessment instructions with project README; keep a short "Assessment" link to TASK.md)
- Create: `DESIGN.md`, `AI_USAGE.md`

- `README.md`: what it is, screenshot placeholder-free; quick start (Docker: `docker compose up --build` → http://localhost:8080; local: pyenv 3.11 venv + pip + `uvicorn`, `nvm use stable` + `npm run dev`); browser support (Chrome/Edge for voice; text fallback elsewhere); demo script using seeded fake data (refs `CLN-JC01`, Emily Stone two bookings, Dr Khan's taken 15:00); running tests/lint; env vars; project structure.
- `DESIGN.md`: use case, the pipeline, NLU rules (intent priority, entity extraction, DOB-vs-date rule), state machine diagram (mermaid) with steps and actions, slot-filling and correction handling, the 13 messy cases → how each is handled → which test covers it, data model & double-booking guarantee, why no LLM, known limitations.
- `AI_USAGE.md`: tools (Claude Code with Opus 5.5, superpowers brainstorming/plan/subagent-driven skills, ponytail), how they helped, where they went wrong (fill from execution notes collected during Tasks 1–7), token usage section with a placeholder table the user fills from `/cost` or the Claude usage page plus instructions to add screenshots under `docs/ai-usage/`.
- [ ] **Step 1:** Write docs. **Step 2:** Verify every command in README runs as written. **Step 3: Commit** `docs: README, DESIGN and AI_USAGE`.

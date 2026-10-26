# REDELIVER — Implementation Plan

> **Status:** Backend Steps 1–12 and Frontend Steps 13–15 implemented; see `docs/PROGRESS.md` for validation details.
> **Last updated:** 2026-10-26

---

## Table of Contents

1. [Folder Structure](#1-folder-structure)
2. [Module List and Responsibilities](#2-module-list-and-responsibilities)
3. [State Machine](#3-state-machine)
4. [Intent List and Detection](#4-intent-list-and-detection)
5. [Slot List](#5-slot-list)
6. [Data Model](#6-data-model)
7. [API Contract](#7-api-contract)
8. [Edge Case List](#8-edge-case-list)
9. [Test Plan](#9-test-plan)
10. [Implementation Steps](#10-implementation-steps)

---

## 1. Folder Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app factory, CORS, lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py        # GET /health
│   │   │   └── sessions.py      # POST /sessions, POST /sessions/{id}/turns,
│   │   │                        #   GET /sessions/{id}, DELETE /sessions/{id}
│   │   └── dependencies.py      # Shared FastAPI deps (session store injection)
│   ├── brain/
│   │   ├── __init__.py
│   │   ├── normalizer.py        # Text normalizer — two passes: intent text and digit text
│   │   ├── extractor.py         # Tracking ID (phonetic RD variants) and phone-last-4 extractors
│   │   ├── date_parser.py       # Date/time slot parser; returns ParseResult dataclass
│   │   ├── intent_detector.py   # Weighted keyword + regex scorer; state-aware priority
│   │   ├── slot_filler.py       # Slot management (gather, update, validate)
│   │   ├── state_machine.py     # Dialogue state machine and transition logic
│   │   └── constants.py         # Intent phrases, messages, thresholds — no logic here
│   ├── services/
│   │   ├── __init__.py
│   │   ├── verification.py      # Verify tracking ID exists + phone last 4 matching
│   │   ├── booking.py           # Slot availability check; atomic booking with slot release
│   │   ├── pickup.py            # Pickup point lookup and selection
│   │   └── cancellation.py      # Cancel parcel; releases booked slot atomically
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py            # Load JSON files from backend/data/
│   │   ├── interfaces.py        # Abstract base classes (IParcelRepo, ISessionStore)
│   │   └── repository.py        # In-memory implementations with threading.Lock
│   ├── models/
│   │   ├── __init__.py
│   │   ├── parcel.py            # Parcel, DeliverySlot, PickupPoint Pydantic models
│   │   ├── session.py           # Session, Turn, DecisionTrace Pydantic models
│   │   └── api.py               # Request/Response Pydantic models for the API layer
│   └── core/
│       ├── __init__.py
│       ├── config.py            # Settings (pydantic-settings, reads .env)
│       └── logging.py           # Structured JSON logger — stdlib logging, no structlog
│
├── data/
│   ├── parcels.json             # 20+ fake parcels
│   ├── slots.json               # Slot template (capacity, period definitions only)
│   └── pickup_points.json       # 5 fake pickup points
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures (test client, fake repo, injected clock)
│   ├── test_health.py
│   ├── test_normalizer.py
│   ├── test_extractor.py
│   ├── test_date_parser.py
│   ├── test_intent_detector.py
│   ├── test_slot_filler.py
│   ├── test_state_machine.py
│   ├── test_verification.py
│   ├── test_booking.py
│   ├── test_pickup.py
│   ├── test_cancellation.py
│   ├── test_sessions_api.py
│   ├── test_no_llm.py           # Fails if any LLM/AI SDK appears in requirements.txt
│   └── test_scenarios/
│       ├── __init__.py
│       ├── test_happy_path.py   # Full call, reschedule
│       ├── test_happy_pickup.py # Full call, pickup point
│       ├── test_happy_cancel.py # Full call, cancel
│       ├── test_happy_status.py # Full call, status query
│       └── test_edge_cases.py   # All 18 edge cases as end-to-end scenario tests
│
└── requirements.txt
```

> **Original backend phase scope:** the backend plan intentionally excluded
> `frontend/` and speech integration. Frontend work is now specified in Step 13.
> It must call the backend API for all application behavior. Browser-native
> speech recognition/synthesis can handle microphone and playback only; no LLM
> or external speech service is added to the decision path.

---

## 2. Module List and Responsibilities

### 2.1 `app/core/config.py`
- Reads all settings from environment variables via `pydantic-settings`.
- Settings: `CORS_ORIGINS` (comma-separated string, split on load), `LOG_LEVEL`,
  `SESSION_TTL_MINUTES`, `MAX_TRACKING_ATTEMPTS`, `MAX_PHONE_ATTEMPTS`,
  `MAX_SILENCE_TURNS`, `MAX_UNKNOWN_TURNS`, `DATA_DIR`, `APP_ENV`, `APP_VERSION`.
- `Settings` object is a singleton cached via `functools.lru_cache`.
- Never reads `.env` at import time — only when `get_settings()` is called.

### 2.2 `app/core/logging.py`
- Configures **stdlib `logging`** with a custom JSON formatter (no structlog dependency).
- All log records serialised to a single JSON line per message.
- Strips all PII: no tracking IDs, no phone digits; only session IDs and log-safe labels appear.

### 2.3 `app/data/loader.py`
- Reads `parcels.json` and `pickup_points.json` from `backend/data/` at startup.
- **Slot grid is generated at runtime** from the injected `datetime` clock so that the
  window is always today → today + 6 days. `slots.json` holds only the capacity/period
  template, not fixed dates.
- Validates all loaded objects against the Pydantic models in `app/models/parcel.py`.

### 2.4 `app/data/interfaces.py`
- `IParcelRepository`: abstract interface.
  - `get_parcel(tracking_id: str) -> Parcel | None`
  - `list_slots(start: date, end: date) -> list[DeliverySlot]`
  - `get_slot(slot_id: str) -> DeliverySlot | None`
  - `book_slot(slot_id: str, tracking_id: str) -> bool` (returns False if full)
  - `release_slot(slot_id: str, tracking_id: str) -> bool`
  - `list_pickup_points(open_on: date | None) -> list[PickupPoint]`
  - `get_pickup_point(point_id: str) -> PickupPoint | None`
  - `cancel_parcel(tracking_id: str) -> bool`
  - `increment_phone_failures(tracking_id: str) -> int` (returns new failure count)
  - `is_parcel_locked(tracking_id: str) -> bool`
- `ISessionStore`: abstract interface.
  - `create_session() -> Session`
  - `get_session(session_id: str) -> Session | None`
  - `save_session(session: Session) -> None`
  - `delete_session(session_id: str) -> None`

### 2.5 `app/data/repository.py`
- `InMemoryParcelRepository(IParcelRepository)`:
  - Protected by a single `threading.Lock` for parcel mutations.
  - Each parcel also has a per-parcel `threading.Lock` for fine-grained slot operations,
    so booking and releasing one parcel's slot does not block reads on another.
  - `book_slot` and `release_slot` are **atomic**: capacity check + mutation happen inside
    the same lock acquisition.
  - Re-scheduling (book new slot + release old slot) is performed inside one lock scope in
    the **service layer** (`booking.rebook_slot`) so the operation is atomic end-to-end.
  - Cancelling calls `cancel_parcel` which also calls `release_slot` inside the same lock.
  - `increment_phone_failures` increments a per-tracking-ID failure counter; once it reaches
    `MAX_PHONE_ATTEMPTS` the parcel is flagged `locked=True` and further verification is
    refused.
- `InMemorySessionStore(ISessionStore)`:
  - Dict of `Session` objects keyed by UUID string.
  - Protected by a `threading.Lock`.
  - Each session also carries its own `threading.Lock` so turns for the same session are
    serialised even under concurrent requests.

### 2.6 `app/models/parcel.py`
- `ParcelStatus` enum: `in_transit`, `out_for_delivery`, `failed_attempt`, `delivered`,
  `cancelled`, `returned_to_sender`.
- `DeliverySlot`: `slot_id`, `date` (date), `period` (`morning`/`afternoon`/`evening`),
  `capacity` (int), `booked` (int).
- `PickupPoint`: `point_id`, `name`, `address`, `selection_aliases`, `open_days` (list[str]), `open_hours` (str).
- `Parcel`: `tracking_id`, `phone_last4`, `status`, `recipient_name` (log only — never
  returned to caller before verification), `current_slot_id` (str | None),
  `phone_failures` (int, default 0), `locked` (bool, default False).

### 2.7 `app/models/session.py`
- `DialogueState` enum: all states listed in Section 3.
- `SlotMap`: typed dataclass (not a plain dict so fields are explicit and type-checked).
- `Turn`: `turn_id`, `caller_text`, `normalized_text`, `assistant_reply`,
  `trace` (DecisionTrace), `timestamp`.
- `DecisionTrace`: `normalized_text`, `intent`, `confidence`, `extracted_slots` (dict),
  `state_before`, `state_after`, `action`, `reason`, `rules_fired` (list[str]).
- `Session`: `session_id`, `state` (DialogueState), `slots` (SlotMap), `turns` (list[Turn]),
  `verified` (bool), `phone_attempts` (int), `tracking_attempts` (int),
  `silence_count` (int), `unknown_count` (int), `ended` (bool), `created_at` (datetime),
  `lock` (threading.Lock — excluded from serialisation).

### 2.8 `app/models/api.py`
- `TurnRequest`: `text` (str, default `""`, max length 2000), `silence` (bool, default False),
  `stt_confidence` (float | None, default None — if < 0.5 triggers re-ask).
  - Empty `text` with `silence=False` is treated as silence, **not** a 400 error.
- `TurnResponse`: `reply` (str), `ended` (bool), `trace` (DecisionTrace).
- `SessionResponse`: `session_id` (str), `state` (str), `greeting` (str).
- `HistoryResponse`: `session_id`, `state`, `verified` (bool), `ended` (bool),
  `slots` (dict), `turns` (list[Turn]).

### 2.9 `app/brain/constants.py`
- `INTENT_KEYWORDS`: `dict[str, list[tuple[str, float]]]` — intent → list of
  `(whole_word_phrase, weight)` tuples.
- `INTENT_REGEX_PATTERNS`: `dict[str, list[tuple[re.Pattern, float]]]` — intent →
  list of `(compiled_pattern, weight)` tuples.
- `STATE_INTENT_PRIORITY`: `dict[DialogueState, list[str]]` — for CONFIRM states,
  defines which intents to evaluate first (e.g., `[affirm, deny, change_of_mind, ...]`).
- `CONFIDENCE_THRESHOLD`: float (default 0.40).
- `AMBIGUITY_MARGIN`: float (default 0.15).
- `BEST_HIT_BASE_WEIGHT`: float (default 1.0) — base score for the top keyword hit.
- `EXTRA_HIT_BONUS`: float (default 0.15) — bonus per additional hit beyond the first.
- `MESSAGES`: `dict[str, str]` — all TTS-friendly message templates with `{slot}`
  placeholders. IDs read digit by digit (e.g., `"R. D. 1. 2. 3. 4. 5. 6. 7. 8."`).
  Sentences are short (≤ 20 words each).
- `FILLER_WORDS`: `frozenset[str]` — speech fillers to strip.
  **Does NOT include `"like"`** (to preserve "I'd like to…").
- `NUMBER_WORD_MAP`: `dict[str, str]` — ordered largest-first mapping of number words
  to digit strings. Used only in the **digit pass** of the normaliser.
- `PARCEL_STATUS_RULES`: `dict[str, set[str]]` — status → set of allowed action intents.
- `RD_PHONETIC_PREFIXES`: `list[str]` — variants for the "RD" prefix recognised by the
  extractor: `"rd"`, `"r d"`, `"are dee"`, `"our d"`, `"ardie"`.

### 2.10 `app/brain/normalizer.py`

The normaliser produces **two distinct outputs** from one raw input:

```
normalize(raw_text: str) -> NormalizeResult
```

`NormalizeResult` is a small dataclass:
- `intent_text: str` — safe for intent detection; number words **preserved** so
  "oh no" and "one moment" are not corrupted.
- `digit_text: str` — number words converted to digits; used by the extractor and
  date parser only.

**Common pre-processing (applied to both outputs):**
1. Lowercase and strip leading/trailing whitespace.
2. Remove or neutralise characters outside printable ASCII + common punctuation
   (injection protection).
3. Truncate to 2000 chars max.
4. Strip filler words (whole-word match against `FILLER_WORDS`).
5. Collapse whitespace.

**`digit_text` additional pass (applied after common pre-processing):**
6. Convert multi-word patterns: `"double five"` → `"55"`, `"triple two"` → `"222"`.
7. Convert `"oh"` → `"0"` when surrounded by other digit words or digits.
8. Convert remaining number words one-by-one (`"one"` → `"1"`, etc.) in descending
   length order to avoid partial substitution.
9. Collapse whitespace again.

**`intent_text`:** skips steps 6–9; number words are left as-is.

### 2.11 `app/brain/extractor.py`
- All extractors operate on `digit_text` from `NormalizeResult`.
- `extract_tracking_ids(digit_text: str) -> list[str]`
  - Recognises the `RD` prefix via `RD_PHONETIC_PREFIXES` (e.g. "are dee", "our d",
    space-separated "r d") followed by exactly 8 digits (possibly space-separated).
  - Returns **all** found candidates in order of appearance.
  - Caller (state machine / slot filler) decides what to do with multiple results:
    - 1 candidate → proceed normally.
    - 2+ candidates → ask caller which one to use (edge case 16).
  - Each result is the upper-cased canonical form `RD########`.
- `extract_phone_last4(digit_text: str, exclude_digits: str | None = None) -> str | None`
  - Looks for exactly 4 consecutive digits **not already matched as part of a tracking ID**.
  - `exclude_digits`: the 8 trailing digits of a tracking ID found in the same turn;
    any 4-digit substring overlapping them is ignored.
  - If multiple non-overlapping 4-digit groups remain, returns `None` (ambiguous).

### 2.12 `app/brain/date_parser.py`
- `parse_date_and_period(text: str, clock: datetime) -> ParseResult`
  - `clock`: injected — the full `datetime` object (not just a date), so the parser can
    determine that a slot earlier **today** is past the cutoff.
  - **Never** reads `datetime.now()` or `date.today()` internally.
- `ParseResult` dataclass:
  - `date: date | None`
  - `period: str | None` — `"morning"` / `"afternoon"` / `"evening"` / `None`
  - `reason: str | None` — `"past"` / `"out_of_range"` / `"cutoff"` / `None`
- Date recognition:
  - `"today"`, `"tomorrow"`, `"day after tomorrow"`, `"in N days"` (N = 1..6).
  - Weekday names: `"monday"` through `"sunday"`, `"next friday"`, `"this saturday"`.
  - `"this weekend"` → Saturday of the current week.
  - Ordinal patterns: `"26th"`, `"november 3rd"`.
- Period normalisation:
  - `"morning"`, `"am"`, `"before noon"` → `"morning"`.
  - `"afternoon"`, `"midday"`, `"lunchtime"`, `"after noon"` → `"afternoon"`.
  - `"evening"`, `"night"`, `"pm"`, `"after 5"`, `"after 6"` → `"evening"`.
- Rejection rules:
  - `reason="past"` — date is before today, or date is today and all remaining periods
    are before the current clock time (cutoff logic).
  - `reason="out_of_range"` — date is beyond today + 6 days.
  - The **"no service on this day"** check (no slots available for a date) is performed
    in `booking.get_available_slots`, **not** in the date parser.

### 2.13 `app/brain/intent_detector.py`
- `detect_intent(intent_text: str, state: DialogueState | None = None) -> IntentResult`
- `IntentResult` dataclass:
  - `intent: str`, `confidence: float`, `runner_up: str | None`,
    `runner_up_confidence: float | None`.
- **Algorithm (no AI, no external API):**
  1. For each intent, find all keyword and regex hits (whole-word matching via
     `r"\b{phrase}\b"` pattern for keywords; compiled patterns for regex).
  2. Score = best single-hit weight + `EXTRA_HIT_BONUS × (total_hits − 1)`, capped at 1.0.
  3. Apply state-aware priority: if `state` is in `STATE_INTENT_PRIORITY`, evaluate the
     listed intents first; if any scores above threshold, return it immediately without
     scoring other intents. This ensures `affirm`/`deny` win in CONFIRM states, and
     `change_of_mind` beats `cancel` for inputs like "no wait".
  4. Apply disambiguation rules before final scoring:
     - `"no wait"` / `"wait no"` → `change_of_mind` (not `deny`).
     - `"cancel that"` → `deny` (not `cancel`).
  5. `detected_intent = argmax(score)`; if score < `CONFIDENCE_THRESHOLD` → `unknown`.
  6. Track runner-up; if gap < `AMBIGUITY_MARGIN`, record in trace.

**Intent catalogue (unchanged from original plan except for algorithm details above):**

| Intent | Example phrases |
|---|---|
| `reschedule` | "reschedule", "rebook", "new date", "new time", "change delivery", "different day" |
| `pickup_point` | "pickup", "pick up", "collect", "collection point", "depot", "drop-off" |
| `cancel` | "cancel", "don't want it", "send it back", "return it", "refuse delivery" |
| `status` | "where is", "status", "tracking update", "where's my parcel", "any update" |
| `explain_status` | "what does failed attempt mean", "what is failed attempt", "what does this status mean" |
| `affirm` | "yes", "yeah", "correct", "that's right", "go ahead", "confirm", "sure" |
| `deny` | "no", "nope", "wrong", "not right", "that's wrong", "never mind" |
| `repeat` | "repeat", "say again", "what did you say", "pardon", "come again" |
| `human_agent` | "human", "agent", "operator", "speak to someone", "real person" |
| `change_of_mind` | "actually", "wait actually", "no wait", "let me change", "on second thought" |
| `goodbye` | "bye", "goodbye", "that's all", "thanks bye", "i'm done" |
| `unknown` | nothing matched above threshold |

**Keyword matching:** whole-word only (`\b` boundaries). "cancel" matches in "please cancel
it" but NOT in "cancellation" or "cancelled".

**Scoring formula (replaces divide-by-max approach):**
```
score(intent, text):
    hits = sorted_hits_by_weight(descending)
    if not hits: return 0.0
    score = hits[0].weight  # best hit is the base
    score += EXTRA_HIT_BONUS * (len(hits) - 1)
    return min(score, 1.0)
```

### 2.14 `app/brain/slot_filler.py`
- `SlotFiller`: stateless helper; all state lives in the `SlotMap` stored in the session.
- `fill_from_turn(slot_map, normalize_result, clock, state)`:
  - Extracts tracking IDs, phone last 4, date, period in one pass.
  - Handles multiple tracking IDs: if 2+ found, sets `slot_map.ambiguous_ids` and does
    NOT fill `tracking_id` yet (state machine will ask caller to choose).
  - Phone extractor is called with the trailing 8 digits of the tracking ID as
    `exclude_digits` to prevent digits from the tracking ID being mistaken for the phone.
- `missing_required_slots(slot_map, state)` → `list[str]` of slot names still needed.
- `reset_date_slots(slot_map)` — clears `intended_date`, `intended_period`,
  `confirmed_slot_id`.
- `reset_action_slots(slot_map)` — clears `action_intent` and all date/period/slot slots.

### 2.15 `app/brain/state_machine.py`
- `StateMachine.process(session, turn_text, silence, clock, stt_confidence) -> TurnResult`
  - `clock: datetime` — injected, never read from system.
  - `TurnResult`: `(reply: str, trace: DecisionTrace, ended: bool)`.
- All transitions are explicit `if/elif` chains; no dynamic dispatch.
- Normalises input → runs slot filler → runs intent detector (with state context) → applies
  transition rules → calls service functions → builds and returns trace.
- After a completed action or status read, enter `ANYTHING_ELSE` and ask whether
  the caller wants to continue. `yes` returns to the action menu; `no` ends the call.
- **TTS-friendly replies:** IDs are read digit by digit; sentences are ≤ 20 words.
  The `MESSAGES` dict in `constants.py` enforces this.

### 2.16 `app/services/verification.py`
- `verify_tracking_id(repo, tracking_id) -> Parcel | None`
- `verify_phone(repo, parcel, last4) -> bool`
  - On failure calls `repo.increment_phone_failures(tracking_id)`.
  - If `repo.is_parcel_locked(tracking_id)` is True, refuses immediately without a new
    attempt.

### 2.17 `app/services/booking.py`
- `get_available_slots(repo, target_date, clock, period=None) -> list[DeliverySlot]`
  - Filters out slots where `booked >= capacity`.
  - Also filters out slots that fall before the current clock time today (cutoff).
- `book_slot(repo, slot_id, tracking_id) -> bool`
- `release_slot(repo, slot_id, tracking_id) -> bool`
- `rebook_slot(repo, old_slot_id, new_slot_id, tracking_id) -> bool`
  - Atomically releases the old slot and books the new one in a single lock acquisition.
  - Returns False if the new slot is full (old slot remains unchanged in that case).

### 2.18 `app/services/pickup.py`
- `list_pickup_points(repo, open_on: date | None = None) -> list[PickupPoint]`
- `get_pickup_point(repo, point_id: str) -> PickupPoint | None`

### 2.19 `app/services/cancellation.py`
- `cancel_parcel(repo, tracking_id) -> bool`
  - Calls `repo.cancel_parcel(tracking_id)` which also releases the current slot
    atomically inside the repository lock.

### 2.20 `app/api/routes/health.py`
- `GET /health` → `{"status": "ok", "version": "<version>"}`.

### 2.21 `app/api/routes/sessions.py`
- `POST /sessions` → create session, emit greeting turn, return 201 with greeting.
- `POST /sessions/{session_id}/turns` → run state machine, return TurnResponse.
  - Empty `text` with `silence=False` is treated as silence (not 400).
- `GET /sessions/{session_id}` → return HistoryResponse.
- `DELETE /sessions/{session_id}` → mark session ended, return 204.

### 2.22 `app/api/dependencies.py`
- `get_settings()` → cached Settings singleton.
- `get_session_store()` → yields the singleton `InMemorySessionStore`.
- `get_parcel_repo()` → yields the singleton `InMemoryParcelRepository`.
- Both store/repo singletons overridable in tests via `app.dependency_overrides`.

---

## 3. State Machine

### 3.1 State Enum

```
GREETING
COLLECT_TRACKING_ID
CONFIRM_TRACKING_ID        (echo back digit-by-digit and ask "is that right?")
VERIFY_PHONE
CHOOSE_ACTION              (menu: reschedule, pickup, cancel, status)
COLLECT_DATE               (reschedule only)
COLLECT_PERIOD             (reschedule only — if date given but no period)
CONFIRM_SLOT               (echo slot back and ask to confirm)
COLLECT_PICKUP_POINT       (pickup_point flow)
CONFIRM_PICKUP             (echo pickup point and ask to confirm)
CONFIRM_CANCEL             (ask "are you sure you want to cancel?")
DELIVER_STATUS             (read parcel status → return to CHOOSE_ACTION)
ANYTHING_ELSE              (ask whether caller wants another action; yes → menu, no → END)
END
```

### 3.2 Transition Table

```
State                   | Input / Condition                                            | Next State              | Action / Response
------------------------|--------------------------------------------------------------|-------------------------|---------------------------------------------------
GREETING                | (auto-triggered by POST /sessions)                           | COLLECT_TRACKING_ID     | Emit greeting + ask for tracking ID
COLLECT_TRACKING_ID     | 1 tracking_id extracted AND found in data                    | CONFIRM_TRACKING_ID     | Echo ID digit by digit: "I heard R. D. 1. 2…  Is that correct?"
                        | 1 tracking_id extracted BUT not found in data                | COLLECT_TRACKING_ID     | "I cannot find that parcel. Please try again."
                        | 2+ tracking IDs extracted                                    | COLLECT_TRACKING_ID     | "I heard two IDs. Which one did you mean? [A] or [B]?"
                        | no tracking_id, attempts < MAX_TRACKING_ATTEMPTS             | COLLECT_TRACKING_ID     | Re-ask with hint
                        | no tracking_id, attempts == MAX_TRACKING_ATTEMPTS            | END                     | Offer human agent, end call
CONFIRM_TRACKING_ID     | affirm                                                       | VERIFY_PHONE            | "Great. Please say the last 4 digits of your phone number."
                        | deny                                                         | COLLECT_TRACKING_ID     | "Let me try again. Please say your tracking ID."
                        | new tracking_id extracted in same turn (correction)          | CONFIRM_TRACKING_ID     | Echo new ID digit by digit and re-ask
VERIFY_PHONE            | parcel is locked (too many prior failures)                   | END                     | Safe refusal, END
                        | phone_last4 matches                                          | CHOOSE_ACTION           | "Verified. What would you like? Reschedule, pick up, cancel, or status?"
                        | phone_last4 wrong, attempts < MAX_PHONE_ATTEMPTS             | VERIFY_PHONE            | "That did not match. Please try again."
                        | phone_last4 wrong, attempts == MAX_PHONE_ATTEMPTS            | END                     | Safe refusal + END; parcel locked in repo
CHOOSE_ACTION           | intent == reschedule AND parcel allows it                    | COLLECT_DATE            | "What date works for you? I can book within the next 7 days."
                        | intent == reschedule AND parcel does NOT allow it            | CHOOSE_ACTION           | Explain status, offer alternatives
                        | intent == pickup_point                                       | COLLECT_PICKUP_POINT    | List pickup points with names and addresses
                        | intent == cancel AND parcel allows it                        | CONFIRM_CANCEL          | "Are you sure you want to cancel? Say yes to confirm."
                        | intent == cancel AND parcel does NOT allow it                | CHOOSE_ACTION           | Explain why, offer alternatives
                        | intent == status                                             | DELIVER_STATUS          | Read status, then ask "Anything else?"
                        | intent == unknown / low confidence                           | CHOOSE_ACTION           | Clarifying question
COLLECT_DATE            | date parsed AND period in same turn AND slot available       | CONFIRM_SLOT            | "I have [period] on [date]. Shall I book that?"
                        | date parsed AND no period AND slots available                | COLLECT_PERIOD          | "Which do you prefer: morning, afternoon, or evening?"
                        | date parsed AND no slots on that day                        | COLLECT_DATE            | "No slots on [date]. The next available is [nearest]. Want that?"
                        | date is past / cutoff                                        | COLLECT_DATE            | "That time has passed. Please choose a future date."
                        | date outside 7-day window                                   | COLLECT_DATE            | "I can only book within the next 7 days."
                        | change_of_mind intent                                        | CHOOSE_ACTION           | Reset slots, return to menu
                        | no date found                                                | COLLECT_DATE            | Re-ask
COLLECT_PERIOD          | period recognised AND slot available                         | CONFIRM_SLOT            | "I have [period] on [date]. Shall I book that?"
                        | period recognised AND slot NOT available                     | COLLECT_PERIOD          | "No [period] slot that day. Available: [list]. Which do you prefer?"
                        | new date extracted (change of mind on date)                 | COLLECT_DATE            | Reset period, re-ask date
                        | change_of_mind intent                                        | CHOOSE_ACTION           | Reset all date slots, return to menu
CONFIRM_SLOT            | affirm                                                       | ANYTHING_ELSE           | book_slot or rebook_slot; report result and ask whether caller wants anything else
                        | deny                                                         | COLLECT_DATE            | "OK. What date would you like instead?"
                        | new date or period extracted                                 | COLLECT_DATE/PERIOD     | Reset and re-collect
COLLECT_PICKUP_POINT    | valid point selected (by number, name, city, or area alias)  | CONFIRM_PICKUP          | Confirm point, address, and PKT hours; allow action changes
                        | no valid selection, attempts within limit                    | COLLECT_PICKUP_POINT    | List points again with ordinal labels
                        | change_of_mind                                               | CHOOSE_ACTION           | Return to menu
CONFIRM_PICKUP          | affirm                                                       | ANYTHING_ELSE           | Confirm pickup point and ask whether caller wants anything else
                        | deny                                                         | COLLECT_PICKUP_POINT    | "Which point would you prefer?"
CONFIRM_CANCEL          | affirm                                                       | ANYTHING_ELSE           | cancel_parcel (releases slot); report cancellation and ask whether caller wants anything else
                        | deny                                                         | CHOOSE_ACTION           | "OK, not cancelled. What else can I help with?"
DELIVER_STATUS          | (auto on entry)                                              | ANYTHING_ELSE           | Read status and ask whether caller wants anything else
ANYTHING_ELSE           | affirm                                                       | CHOOSE_ACTION           | Offer the action menu
                        | deny                                                         | END                     | Say goodbye and end the call
                        | a recognized action                                          | CHOOSE_ACTION / action  | Continue with the requested help
END                     | any input                                                    | END                     | "This call has ended. Goodbye."
```

**Cross-cutting transitions (checked before state-specific logic):**

| Input | Condition | Action |
|---|---|---|
| `silence=True` OR empty text | silence_count < MAX_SILENCE_TURNS | Gentle prompt (turn 1), softer prompt (turn 2), end call (turn 3); silence_count++ |
| low `stt_confidence` (< 0.5) | — | "I didn't quite catch that. Could you say that again?" |
| `repeat` intent | — | Re-emit last assistant reply; state unchanged |
| `human_agent` intent | — | Handoff message; END |
| `goodbye` intent | — | Farewell; END |
| `unknown` for consecutive turns | unknown_count == MAX_UNKNOWN_TURNS | Ask whether the caller wants a human agent; transfer only after `affirm`, otherwise resume the current state |

**Separate counters:** `silence_count` and `unknown_count` are tracked independently.
A silence turn does not increment `unknown_count` and vice versa.

### 3.3 Text Diagram

```
                     ┌──────────────────────────────────────────┐
                     │                 GREETING                  │
                     │  (emitted automatically on POST /sessions)│
                     └─────────────────┬────────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │    COLLECT_TRACKING_ID       │◄──────────────────────┐
                        │  (up to MAX_TRACKING_ATTEMPTS│                       │
                        │   then → human / END)        │                       │
                        └──────────────┬──────────────┘                        │
                                       │  1 ID found                            │
                                       ▼                                        │ deny
                        ┌─────────────────────────────┐                        │
                        │    CONFIRM_TRACKING_ID       │────────────────────────┘
                        └──────────────┬──────────────┘
                                       │  affirm
                                       ▼
                        ┌─────────────────────────────┐
                        │       VERIFY_PHONE           │◄─── wrong (< max attempts)
                        │  (per-parcel failure counter │
                        │   locked after MAX fails)    │
                        └──────────────┬──────────────┘
                                       │  verified
                                       ▼
                        ┌─────────────────────────────┐
                  ┌────►│       CHOOSE_ACTION          │◄──────────────────────┐
                  │     │  reschedule / pickup /       │◄──────────────────────┤
                  │     │  cancel / status             │  (after DELIVER_STATUS)│
                  │     └────┬──────┬────────┬────────┘                        │
                  │          │      │        │                                   │
                  │    sched │ p/up │ cancel │ status                           │
                  │          │      │        │                                   │
                  │          ▼      ▼        ▼                                   │
                  │   ┌──────┐  ┌───────┐ ┌──────────────┐  ┌──────────────┐   │
                  │   │COLLEC│  │COLLEC │ │CONFIRM_CANCEL│  │DELIVER_STATUS│───┘
                  │   │_DATE │  │T_PICK │ └──────┬───────┘  └──────────────┘
                  │   └──┬───┘  │_POINT │        │ affirm
                  │      │      └───┬───┘         ▼
                  │      ▼          ▼         ┌───────┐
                  │  ┌────────┐ ┌──────────┐  │  END  │
                  │  │COLLECT │ │CONFIRM_  │  └───────┘
                  │  │_PERIOD │ │PICKUP    │
                  │  └──┬─────┘ └──┬───────┘
                  │     │          │ affirm → END
                  │     ▼          │
                  │  ┌──────────────┐  affirm
                  │  │CONFIRM_SLOT  │──────────────────► END
                  │  └──────────────┘
                  │         │ deny
                  └─────────┘
```

---

## 4. Intent List and Detection

### 4.1 Algorithm (no AI, no external API)

```
score(intent, text):
    hits = [w for (phrase, w) in INTENT_KEYWORDS[intent]
            if re.search(r'\b' + re.escape(phrase) + r'\b', text)]
    hits += [w for (pattern, w) in INTENT_REGEX_PATTERNS[intent]
             if pattern.search(text)]
    if not hits: return 0.0
    best = max(hits)
    return min(best + EXTRA_HIT_BONUS * (len(hits) - 1), 1.0)

State-aware priority:
    if state in STATE_INTENT_PRIORITY:
        for intent in STATE_INTENT_PRIORITY[state]:
            if score(intent, text) >= CONFIDENCE_THRESHOLD:
                return IntentResult(intent=intent, ...)
    # fall through to global argmax

Disambiguation rules applied to text BEFORE scoring:
    "no wait*"  → force-score change_of_mind higher
    "cancel that" → force-score deny higher
```

- No external calls, no stemming library.
- Common morphological variations listed explicitly in `constants.py`.
- State-aware priority for CONFIRM states: `[affirm, deny, change_of_mind, repeat, ...]`.

### 4.2 Intent Keyword and Pattern Table

| Intent | High-weight keywords/phrases (1.0) | Medium-weight (0.5) | Key regex patterns |
|---|---|---|---|
| `reschedule` | "reschedule", "rebook", "new date", "new time", "change delivery", "different day", "another day", "book again" | "delivery date", "different slot" | `r"deliver.*again"`, `r"(new|different)\s+(day|date|time|slot)"` |
| `pickup_point` | "pickup point", "pick up point", "collection point", "pick it up", "collect it", "go to depot", "post office" | "collect", "depot", "branch" | `r"pick\s*up\s*point"`, `r"collect\s*(it|from)"` |
| `cancel` | "cancel the delivery", "cancel my delivery", "don't want it", "send it back", "return it", "refuse delivery" | "cancel", "stop delivery" | `r"cancel\s*(the\s*)?(delivery|order|parcel)"`, `r"don'?t\s+want"` |
| `status` | "where is my parcel", "where's my parcel", "tracking update", "any update on my delivery", "has it been delivered" | "status", "tracking", "where is it" | `r"where\s+(is|are)\s+(my|the)"`, `r"(what|how).*(status|update)"` |
| `explain_status` | "what does failed attempt mean", "what does fail attempt mean", "what is failed attempt", "explain failed attempt" | — | Status meaning question patterns; response uses the parcel's current status and available actions |
| `affirm` | "yes please", "yes confirm", "that's right", "go ahead", "that is correct", "confirm please" | "yes", "yeah", "yep", "correct", "ok", "sure", "alright", "perfect" | `r"\byes\b"`, `r"\byeah\b"` |
| `deny` | "no that's wrong", "that is not right", "cancel that", "never mind that" | "no", "nope", "wrong", "never mind", "incorrect" | `r"^no\b"`, `r"that'?s\s+(not\s+right|wrong)"` |
| `repeat` | "say that again", "repeat that please", "what did you say", "come again please" | "pardon", "repeat", "say again", "didn't catch" | `r"(say|repeat)\s+(that\s+)?(again|please)"` |
| `human_agent` | "speak to a human", "talk to an agent", "real person please", "transfer me to someone" | "human", "agent", "operator", "person", "representative" | `r"(speak|talk)\s+to\s+(a\s+)?(human|person|agent)"` |
| `change_of_mind` | "no wait actually", "actually wait", "on second thought", "let me change that", "something else instead" | "actually", "wait", "instead", "switch" | `r"(actually|wait)\s*,?\s*(no|let|can|i)"` |
| `goodbye` | "goodbye for now", "thanks that's all", "i'm all done", "thanks bye" | "bye", "goodbye", "thanks", "thank you", "done", "cheers" | `r"^(bye|goodbye)$"`, `r"that'?s\s+all"` |

### 4.3 Thresholds

| Name | Default | Purpose |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | 0.40 | Below this → `unknown` |
| `AMBIGUITY_MARGIN` | 0.15 | If top − runner_up < this → flag in trace |
| `EXTRA_HIT_BONUS` | 0.15 | Bonus per additional hit beyond the first |
| `STT_CONFIDENCE_THRESHOLD` | 0.50 | Below this → re-ask regardless of intent |

---

## 5. Slot List

| Slot name | Type | Description | When collected |
|---|---|---|---|
| `tracking_id` | `str \| None` | Canonical `RD########` | COLLECT_TRACKING_ID |
| `ambiguous_ids` | `list[str]` | Multiple IDs heard; caller must choose | COLLECT_TRACKING_ID |
| `phone_last4` | `str \| None` | 4-digit string | VERIFY_PHONE |
| `intended_date` | `date \| None` | Desired delivery date | COLLECT_DATE |
| `intended_period` | `str \| None` | `morning / afternoon / evening` | COLLECT_PERIOD |
| `confirmed_slot_id` | `str \| None` | Slot the caller confirmed | CONFIRM_SLOT |
| `pickup_point_id` | `str \| None` | Selected pickup point | COLLECT_PICKUP_POINT |
| `action_intent` | `str \| None` | Top-level action (`reschedule / pickup_point / cancel / status`) | CHOOSE_ACTION |
| `cancel_confirmed` | `bool` | Whether cancellation was confirmed | CONFIRM_CANCEL |

Rules:
- Slots are **never revealed** to the caller before verification (`verified == True`).
- Any slot can be overwritten by a later turn (change of mind).
- Resetting `intended_date` also resets `intended_period` and `confirmed_slot_id`.
- Resetting `action_intent` also resets all date, period, slot, and pickup slots.

---

## 6. Data Model

### 6.1 `parcels.json` — 20+ fake parcels

Each parcel:
```json
{
  "tracking_id": "RD12345678",
  "phone_last4": "1234",
  "recipient_name": "Ayesha Khan",
  "status": "failed_attempt",
  "current_slot_id": null
}
```

Statuses covered:
- `in_transit` (3) — status only
- `out_for_delivery` (3) — status only
- `failed_attempt` (8) — reschedule / pickup / cancel / status
- `delivered` (3) — status only
- `cancelled` (2) — inform only
- `returned_to_sender` (2) — inform only

### 6.2 Slot generation (runtime, not fixed JSON)

Slots are generated by `loader.py` at startup relative to the injected `clock`:
- Window: today → today + 6 days (7 days total).
- Periods per day: morning, afternoon, evening.
- Capacity template comes from `slots.json` (defines default capacity per period and which
  day offsets are pre-booked to enable edge-case testing).

```json
{
  "default_capacity": 3,
  "pre_booked": [
    {"day_offset": 2, "period": "morning", "booked": 3},
    {"day_offset": 3, "period": "afternoon", "booked": 3},
    {"day_offset": 3, "period": "evening", "booked": 3}
  ]
}
```

At least one date (offset 3) has two of three periods full; tests inject the clock to make
edge cases deterministic.

### 6.3 `pickup_points.json` — 5 fake pickup points

```json
[
  {
    "point_id": "PP-001",
    "name": "Islamabad I-8 Markaz Depot",
    "address": "Shop 12, I-8 Markaz, Islamabad, Islamabad Capital Territory",
    "open_days": ["monday","tuesday","wednesday","thursday","friday"],
    "open_hours": "08:00-18:00"
  }
]
```

One point weekdays-only, one 7-days-a-week, to test `open_on` filtering.

---

## 7. API Contract

### 7.1 `GET /health`

**Response 200:**
```json
{"status": "ok", "version": "1.0.0"}
```

---

### 7.2 `POST /sessions`

**Request:** No body.

**Response 201:**
```json
{
  "session_id": "e3a2b1c0-1234-5678-abcd-ef0123456789",
  "state": "COLLECT_TRACKING_ID",
  "greeting": "Hello. Welcome to REDELIVER. I can help with a missed delivery. Please tell me your tracking ID. It starts with R. D. followed by 8 digits."
}
```

---

### 7.3 `POST /sessions/{session_id}/turns`

**Request body:**
```json
{
  "text": "reschedule RD12345678 to tomorrow morning",
  "silence": false,
  "stt_confidence": 0.92
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `text` | string | no (default `""`) | max 2000 chars; empty = treated as silence |
| `silence` | boolean | no (default false) | true = silence event from browser |
| `stt_confidence` | float | no (default null) | 0.0–1.0; < 0.5 triggers re-ask |

**Response 200:**
```json
{
  "reply": "I heard R. D. 1. 2. 3. 4. 5. 6. 7. 8.  Is that correct?",
  "ended": false,
  "trace": {
    "normalized_text": "reschedule rd12345678 to tomorrow morning",
    "intent": "reschedule",
    "confidence": 0.85,
    "extracted_slots": {
      "tracking_id": "RD12345678",
      "intended_date": "2026-10-27",
      "intended_period": "morning"
    },
    "state_before": "COLLECT_TRACKING_ID",
    "state_after": "CONFIRM_TRACKING_ID",
    "action": "echo_tracking_id",
    "reason": "Tracking ID extracted and found. Echoing digit by digit for confirmation.",
    "rules_fired": ["tracking_id_format_match", "multi_slot_fill", "tts_digit_expansion"]
  }
}
```

**Error responses:**
- `404` — session not found.
- `409` — session already ended.
- `422` — text > 2000 chars or malformed JSON.
- *(Empty text with silence=false is NOT a 400 — it is treated as silence.)*

---

### 7.4 `GET /sessions/{session_id}`

**Response 200:**
```json
{
  "session_id": "e3a2b1c0-...",
  "state": "CONFIRM_SLOT",
  "verified": true,
  "ended": false,
  "slots": {
    "tracking_id": "RD12345678",
    "phone_last4": null,
    "intended_date": "2026-10-27",
    "intended_period": "morning",
    "confirmed_slot_id": null,
    "pickup_point_id": null,
    "action_intent": "reschedule",
    "cancel_confirmed": false
  },
  "turns": [{"turn_id": 1, "...": "..."}]
}
```

---

### 7.5 `DELETE /sessions/{session_id}`

**Response 204:** No body. Idempotent on already-ended sessions.

---

## 8. Edge Case List

| # | Edge case | Detection | Response |
|---|---|---|---|
| 1 | Caller changes date or time mid-flow | New date/period extracted in COLLECT_DATE / COLLECT_PERIOD / CONFIRM_SLOT, or `change_of_mind` intent | Reset date/period slots, re-enter COLLECT_DATE, acknowledge change |
| 2 | Caller switches action (reschedule → pickup etc.) | `change_of_mind` + new action keyword at any post-verification state | Reset action and date slots, return to CHOOSE_ACTION |
| 3 | Tracking ID misheard / partial / wrong format | Extractor returns 0 candidates | Re-ask with hint; after MAX_TRACKING_ATTEMPTS → human + END |
| 4 | Tracking ID not found in data | Repository returns None | "I cannot find that parcel. Please try again." — increment attempt counter |
| 5 | Wrong phone last 4 (failure counter per tracking ID across sessions) | `verify_phone` returns False; `increment_phone_failures` called | Re-ask; on MAX_PHONE_ATTEMPTS → parcel locked + safe refusal + END |
| 6 | Parcel delivered / cancelled / returned | Status rules in CHOOSE_ACTION | Explain status politely; offer only applicable actions |
| 7 | Requested slot is full | `get_available_slots` returns empty list for chosen date+period | Offer nearest 2–3 alternatives |
| 8 | Date in past / beyond 7 days / past cutoff today | `parse_date_and_period` returns rejection reason | Tailored message per reason ("past", "out_of_range", "cutoff") |
| 9 | Multi-slot turn ("reschedule RD12345678 to tomorrow morning") | `fill_from_turn` extracts all in one pass | Fill all extracted slots; skip already-answered questions |
| 10 | Nothing useful / mumble / off-topic | Intent = `unknown`, confidence < threshold | Escalating clarification over 5 turns; then ask permission to transfer; only transfer after caller says yes |
| 11 | Silence or empty input | `silence=True` or `text==""` | Gentle prompt (1), soft (2), polite end (3); silence_count++ |
| 12 | Repeat / human / goodbye at any state | Cross-cutting intent rules | `repeat` → re-emit last reply; `human_agent` → handoff + END; `goodbye` → farewell + END |
| 13 | Cancellation without confirmation | Always routes through CONFIRM_CANCEL | Cancel only fires on `affirm`; `deny` → CHOOSE_ACTION |
| 14 | Affirm/deny at wrong moment | Intent affirm/deny in a non-CONFIRM state | "I am not sure what you are confirming. [re-ask current question]" |
| 15 | Long input / special chars / injection text | Length capped at 2000 chars; normaliser strips non-printable; no eval/exec | 422 if > 2000; otherwise normalised text is safe plain text |
| 16 | Two tracking IDs in one turn | Extractor returns 2+ candidates | "I heard two IDs. Which did you mean? [A] or [B]?" |
| 17 | Double / concurrent booking | threading.Lock in repo; book_slot is atomic | Second request returns False; system offers alternative slot |
| 18 | Session not found / ended / post-END turns | Route handler checks state before SM | 404 / 409 / "This call has ended. Goodbye." |

---

## 9. Test Plan

### 9.1 Coverage target
- **Brain modules**: ≥ 90% line coverage.
- **Service modules**: ≥ 85% line coverage.
- **API routes**: 100% of routes and error paths.

### 9.2 Unit tests — per module

#### `test_no_llm.py`
- Reads `requirements.txt` and asserts that none of the following substrings appear:
  `openai`, `anthropic`, `google-generativeai`, `langchain`, `llama`, `cohere`, `tiktoken`,
  `transformers`, `huggingface`. Fails with a clear message if any are found.

#### `test_normalizer.py`
- Happy: lowercases, strips fillers, "uh" → removed, "um" → removed.
- `intent_text`: "oh no" preserved as-is, "one moment" preserved as-is.
- `digit_text`: "oh" → "0", "double five" → "55", "triple nine" → "999".
- Negative: already-digit strings unchanged; unknown words unchanged.
- Boundary: empty string, 2000-char, 2001-char truncated.
- Injection: `<script>`, SQL `'; DROP TABLE`, `"` — no crash, safe output.
- Parametrized: 20+ phrase → expected intent_text and digit_text pairs.

#### `test_extractor.py`
- Happy: `"rd12345678"`, `"r d 1 2 3 4 5 6 7 8"`, `"are dee 12345678"`, `"our d 1 2 3 4 5 6 7 8"`.
- Negative: 7-digit, 9-digit, no prefix.
- Multiple IDs: 2 valid IDs in one sentence → list of 2.
- Phone last 4: extracted; with `exclude_digits` overlapping trailing 8 digits → not returned.
- Parametrized: 15+ tracking ID phrasings.

#### `test_date_parser.py`
- Inject `clock = datetime(2026, 10, 26, 14, 30)`.
- Happy: "tomorrow" → 2026-10-27, "next friday", "in 3 days".
- Cutoff: "today morning" when clock is 14:30 → reason="cutoff" (morning passed).
- Negative: "yesterday" → reason="past"; "in 10 days" → reason="out_of_range".
- Period parametrized: "am", "before noon" → "morning"; "after 5" → "evening".
- Boundary: "in 6 days" → valid; "in 7 days" → out_of_range.

#### `test_intent_detector.py`
- Happy path per intent; clear phrase → correct intent + confidence ≥ threshold.
- Whole-word matching: "cancellation" must NOT trigger `cancel`.
- State-aware: in CONFIRM_SLOT, "yes" wins over weaker reschedule keywords.
- Disambiguation: "no wait" → `change_of_mind`; "cancel that" → `deny`.
- False positive: "I need to cancel my gym membership" → `cancel` confidence must be low.
- False negative: "I'd like to pick up the parcel myself from your office" → `pickup_point`.
- Parametrized: 5+ phrasings per intent.

#### `test_slot_filler.py`
- `fill_from_turn` extracts all slots from a rich sentence.
- Phone digits that overlap tracking ID trailing digits are excluded.
- 2+ tracking IDs → `ambiguous_ids` set, `tracking_id` not set.
- Overwrite: new date → old date cleared, period cleared.

#### `test_state_machine.py`
- Each transition row tested with injected `clock = datetime(2026, 10, 26, 14, 30)`.
- Cross-cutting: `repeat`, `human_agent`, `goodbye`.
- Max tracking attempts → END.
- Max phone attempts → END; parcel locked.
- `rebook_slot` called on CONFIRM_SLOT when parcel already has a `current_slot_id`.
- `cancel_parcel` releases slot.
- DELIVER_STATUS → CHOOSE_ACTION.

#### `test_booking.py`
- Concurrency: two threads book the same 1-capacity slot; assert only one succeeds.
- `rebook_slot`: atomic; if new slot full → old slot unchanged.

### 9.3 API tests — `test_sessions_api.py`
- `GET /health` → 200 `{"status":"ok"}`.
- `POST /sessions` → 201, session_id returned.
- Empty text (no silence flag) → treated as silence, 200 returned.
- `POST /sessions/{id}/turns` after `ended=True` → 409.
- Text > 2000 chars → 422.
- `GET /sessions/{id}` → 200 with history.
- `DELETE /sessions/{id}` → 204.

### 9.4 Scenario tests
| File | Covers |
|---|---|
| `test_happy_path.py` | Full call: tracking → verify → reschedule → confirm |
| `test_happy_pickup.py` | Full call: tracking → verify → pickup point → confirm |
| `test_happy_cancel.py` | Full call: tracking → verify → cancel → confirm |
| `test_happy_status.py` | Full call: tracking → verify → status → another action → end |
| `test_edge_cases.py` | All 18 edge cases |

### 9.5 Determinism
- `conftest.py` defines `frozen_clock` fixture at 14:30 PKT (`timezone(timedelta(hours=5), name="PKT")`).
- Repository reset to clean snapshot before each test via `autouse` fixture.
- No test reads `datetime.now()` or `date.today()`.

---

## 10. Implementation Steps

### Step 1 — Config, logging, app factory, health endpoint ✅ in progress
- `app/core/config.py` — Settings with all env vars, `lru_cache`.
- `app/core/logging.py` — stdlib JSON logging, no structlog.
- `app/main.py` — FastAPI factory, CORS (from `CORS_ORIGINS`), lifespan.
- `app/api/routes/health.py` — `GET /health`.
- Wire routes in `main.py`.
- `tests/test_health.py` — health endpoint; test_no_llm.py — LLM guard.
- Update `requirements.txt` (add `pydantic-settings`), `README.md`.

### Step 2 — Fake data layer
- `backend/data/parcels.json`, `slots.json`, `pickup_points.json`.
- `app/models/parcel.py`.
- `app/data/loader.py` (slots generated at runtime from clock).
- `app/data/interfaces.py`.
- `app/data/repository.py` (threading.Lock everywhere, per-parcel lock).
- `tests/test_repository.py`.

### Step 3 — Text normalizer (two-pass: intent_text + digit_text)
- `app/brain/constants.py` (FILLER_WORDS without "like"; NUMBER_WORD_MAP; placeholders).
- `app/brain/normalizer.py`.
- `tests/test_normalizer.py`.

### Step 4 — Tracking ID and phone extractor
- `app/brain/extractor.py` (phonetic RD prefixes; exclude_digits for phone).
- `tests/test_extractor.py`.

### Step 5 — Date and time parser (returns ParseResult; clock injected)
- `app/brain/date_parser.py`.
- `tests/test_date_parser.py` (inject frozen_clock).

### Step 6 — Intent detector (state-aware; best-hit formula; whole-word matching)
- Flesh out `constants.py` with full intent keyword/regex tables.
- `app/brain/intent_detector.py`.
- `tests/test_intent_detector.py`.

### Step 7 — Slot filler and state machine
- `app/brain/slot_filler.py`.
- `app/models/session.py`.
- `app/brain/state_machine.py`.
- `tests/test_slot_filler.py`, `tests/test_state_machine.py`.

### Step 8 — Business logic services
- `app/services/verification.py`, `booking.py`, `pickup.py`, `cancellation.py`.
- Integrate into `state_machine.py`.
- Unit tests per service.

### Step 9 — Messy caller handling
- Silence counter + escalation; unknown counter + escalation; stt_confidence re-ask.
- Injection/length guards.
- Edge case tests.

### Step 10 — Session management and API endpoints
- `app/models/api.py`.
- `app/api/routes/sessions.py`.
- `app/api/dependencies.py`.
- `tests/test_sessions_api.py`, `tests/test_scenarios/`.

### Step 11 — Postman collection and documentation
- `docs/postman/redeliver.postman_collection.json`.

### Step 12 — Final pass
- `ruff check backend/` — fix all issues.
- `pytest --cov=app --cov-report=term-missing` — fix gaps below 90%.
- Final `README.md`, `DESIGN.md`, `AI_USAGE.md`, `docs/BACKEND_GUIDE.md`.

### Step 13 — React caller frontend
- Replace the starter page with the REDELIVER caller interface and responsive layouts.
- Keep every HTTP request in `frontend/src/services/redeliverApi.js` and call the backend session/health endpoints.
- Keep intent, parcel, verification, booking, cancellation, and state-transition logic in the backend.
- Add transcript entry, backend decision-trace display, session start/end, and clear loading/error states.
- Provide browser-native speech recognition and speech synthesis where supported; retain typed input as fallback.
- Configure the Vite `/api` proxy for local development and `VITE_API_BASE_URL` for deployments.
- Update the user, backend, and frontend documentation, then run frontend lint/build checks.

### Step 14 — Complete product site and operations dashboard
- Expand the caller console into a responsive product site with workflow, capabilities, use cases, and prototype limitations.
- Build a custom WebGL 3D hero visualizer; connect microphone amplitude through Web Audio when listening and use honest state animation for browser speech synthesis.
- Add dashboard overview, active-session transcript, fixed-agent information, local preferences, and light/dark themes.
- Map only existing health and session endpoints to UI; label historical analytics and agent management unavailable because no supporting backend APIs exist.
- Preserve the caller voice/session flow and backend-only business logic; update frontend docs and run lint/build checks.

### Step 15 — Landing-page balance, scroll reveals, and dedicated call page
- Balance the landing hero's left/right content margins across viewport sizes.
- Add viewport-triggered section reveals and staggered content motion, respecting reduced-motion preferences.
- Move live call transcript and microphone/speech controls to a dedicated voice page with its own URL hash route and browser back navigation.
- Keep the hero visualizer and voice-demo entry points on the marketing page; verify frontend lint/build and leave backend files unchanged.

---

## Appendix A — `.env.example` variables

```
# Comma-separated allowed CORS origins
CORS_ORIGINS=http://localhost:3000

# Log level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# Session TTL in minutes (for future cleanup)
SESSION_TTL_MINUTES=30

# Max attempts before giving up on tracking ID collection
MAX_TRACKING_ATTEMPTS=3

# Max phone-verification failures per parcel (across all sessions)
MAX_PHONE_ATTEMPTS=3

# Max consecutive silence turns before ending call
MAX_SILENCE_TURNS=3

# Max consecutive unknown-intent turns before offering human
MAX_UNKNOWN_TURNS=5

# Application environment: development, production
APP_ENV=development

# Application version string
APP_VERSION=1.0.0
```

---

*End of PLAN.md.*

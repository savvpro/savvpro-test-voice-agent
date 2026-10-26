# Design: Restaurant Voice Booking Assistant

## Use case

Callers book a table at **La Bella Tavola** by providing date, time, party size, and name. The assistant validates input, checks simulated availability, offers alternatives when a slot is full, confirms details, and completes or cancels the reservation. All guest data is fake and stored in memory only.

## Architecture

```
Browser (Next.js)
  ├─ Web Speech API  → user transcript
  ├─ speechSynthesis → spoken replies
  └─ REST            → FastAPI backend

FastAPI
  ├─ DialogEngine (brain)     ← rule-based FSM
  ├─ Intent classifier        ← keywords + regex
  ├─ Entity extractor         ← regex + date math
  └─ BookingService           ← in-memory slots
```

No GPT/Claude/Gemini (or similar) is used anywhere in the decision path.

## Dialog state machine

States (`ConversationState`) drive what the assistant asks next:

| State | Purpose |
|-------|---------|
| `ask_date` | Collect reservation date |
| `ask_time` | Collect time |
| `ask_party_size` | Collect guest count |
| `ask_name` | Collect name on reservation |
| `confirm` | User must confirm summary |
| `suggest_alternative` | User accepts/rejects a new slot |
| `booked` | Reservation confirmed |
| `goodbye` / `cancelled` | Terminal states |

### Turn processing (`DialogEngine.process`)

1. **Classify intents** on the utterance (`brain/intents.py`).
2. **Extract entities** (`brain/entities.py`).
3. **Global handlers** — `cancel`, `help`, restart after goodbye.
4. **Slot filling** — merge entities into `Booking` (supports multi-slot utterances).
5. **State transition** — change requests, confirmation, alternatives, or `_advance()`.

`_advance()` validates date (not in past), time (within opening hours), and party size (1–`MAX_PARTY_SIZE`), then either asks for the next missing slot or runs availability check.

### Availability

`BookingService` tracks how many tables are booked per `(date, time)` up to `TABLES_PER_SLOT`. Some slots are pre-seeded (e.g. Friday 19:00 fully booked) so the assistant must suggest alternatives via `find_alternative()` (nearby hours, then following days).

## Intent classification

Deterministic keyword and pattern matching. Multiple intents can fire on one utterance (e.g. book + date + time + party size).

Priority notes:

- **Cancel** short-circuits all other intents.
- **Change** re-opens the relevant slot (date/time/party/name) using keywords or new entities.
- **Confirm / deny** apply when no entity intents were detected on the same turn (avoids “yes” on a sentence that also contains a date).

## Entity extraction

| Entity | Method |
|--------|--------|
| Date | Relative (`today`, `tomorrow`), weekday names, month/day phrases, numeric dates |
| Time | 12h/24h patterns, `noon`/`midnight`; ambiguous 1–6h assumed PM in restaurant context |
| Party size | Digits, “party of N”, word numbers, short replies like “four” |
| Name | “My name is …”, or short alphabetic reply when asking for name |
| Contact | Phone patterns (optional slot; not required for happy path) |

Extracted values are applied in `_fill_slots()` even when the user jumps ahead (“Friday at 8 for 2, I'm Alex”).

## Edge cases handled

- **Mid-flow modification** — `change` intent + entity hints.
- **Past dates** — cleared with re-prompt.
- **Outside hours** — time cleared with re-prompt.
- **Oversized party** — re-prompt with max size.
- **Full slot** — alternative suggestion or pick new date.
- **Confirmation loop** — requires clear yes/no at `confirm`.
- **Post-booking** — informs user table is already booked; greeting can start fresh booking.

## API surface

| Method | Path | Role |
|--------|------|------|
| POST | `/api/conversation/start` | New session + greeting |
| POST | `/api/message` | User text → reply + `state` (includes `last_decision`) |
| GET | `/api/conversation/{id}` | Full turn history with per-turn `extracted` |
| WS | `/ws/conversation` | Same flow over WebSocket (optional) |

## Frontend transparency

The UI shows:

- Live booking fields from `state.booking`
- Current FSM state and step checklist
- **Decision log** — intents and entities the brain detected on each user turn (from conversation history)

This makes rule-based behavior inspectable without reading server logs.

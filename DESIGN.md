# Design — Voice Booking Assistant

This document explains the use case, the brain's decision-making logic, and
the edge cases it handles. It is the spec for `backend/brain/state_machine.py`.

## Use case

**Restaurant table booking over the phone.**

The caller wants to reserve a table at *The Copper Spoon*. The assistant
walks them through collecting the required slots, checks availability
against the restaurant's hours and existing bookings, and confirms the
reservation. The whole interaction takes 4–8 turns and ends with a
confirmation number.

This is a real phone job — every restaurant takes bookings by phone — and
it has enough structure to require a real state machine (not just a
chatbot) but enough messiness to make the brain interesting.

## Why a state machine (and not an LLM)

The task explicitly forbids using an LLM for decisions. That's the right
call for this domain:

- **Predictability**: every caller gets the same flow. No hallucinated
  bookings, no invented opening hours, no "I'll go ahead and book that for
  50 people".
- **Cost & latency**: zero per-call cost, sub-millisecond decisions.
- **Testability**: every state transition can be unit-tested.
- **Auditability**: the `decision` field on every `BrainResponse` tells you
  exactly which branch fired.

The trade-off is that the brain can't handle fully open-ended chit-chat.
That's fine — a phone booking assistant shouldn't be a chatbot.

## The state machine

```
                    ┌──────────┐
                    │ GREETING │
                    └────┬─────┘
                         │  (any utterance that's not pure greeting)
                         ▼
                  ┌─────────────┐
                  │  ASK_DATE   │ ◄──────┐
                  └──────┬──────┘        │
                         │               │
                         ▼               │
                  ┌─────────────┐        │
                  │  ASK_TIME   │ ───────┤  (any state can fall back
                  └──────┬──────┘        │   to a previous state on
                         │               │   a change_value intent)
                         ▼               │
                ┌─────────────────┐      │
                │ ASK_PARTY_SIZE  │ ─────┤
                └────────┬────────┘      │
                         │               │
                         ▼               │
              ┌─────────────────────┐    │
              │ CHECK_AVAILABILITY  │    │
              │  (transient)        │    │
              └────────┬────────────┘    │
                       │                 │
            ┌──────────┴──────────┐      │
            │                     │      │
       (available)          (unavailable)│
            │                     │      │
            ▼                     └──────┘
      ┌──────────┐
      │ ASK_NAME │
      └────┬─────┘
           │
           ▼
      ┌───────────┐
      │ ASK_PHONE │
      └────┬──────┘
           │
           ▼
      ┌──────────┐
      │ CONFIRM  │ ◄──┐
      └────┬─────┘    │  (deny → offer change
           │          │   → change_value → re-validate
       (confirm)      │   → back to CONFIRM)
           │          │
           ▼          │
      ┌──────────┐    │
      │  BOOKED  │    │
      └────┬─────┘    │
           │          │
           ▼          │
      ┌──────────┐    │
      │ GOODBYE  │    │
      └──────────┘    │
                      │
                      │
              (cancel from any state)
                      │
                      ▼
                ┌───────────┐
                │ CANCELLED │
                └───────────┘
```

### States

| State | What the brain is doing |
|-------|-------------------------|
| `GREETING` | Initial state. Waiting for caller to start. |
| `ASK_DATE` | Asking what day. |
| `ASK_TIME` | Asking what time. |
| `ASK_PARTY_SIZE` | Asking how many people. |
| `CHECK_AVAILABILITY` | (Transient) Validating the requested slot. |
| `ASK_NAME` | Asking for the booking name. |
| `ASK_PHONE` | Asking for a phone number. |
| `CONFIRM` | Reading back the booking and asking "yes/no". |
| `BOOKED` | Booking confirmed. Will say goodbye on next turn. |
| `CANCELLED` | Caller cancelled. |
| `GOODBYE` | Call ending. |

### Slots

| Slot | Type | Extractor |
|------|------|-----------|
| `date` | ISO `YYYY-MM-DD` | `extract_date` — handles today/tomorrow/weekdays/month-day/ISO/US-numeric |
| `time` | `HH:MM` 24-hour | `extract_time` — handles 7pm / 7:30pm / 19:30 / noon / "half past seven" / "quarter to eight" |
| `party_size` | int | `extract_party_size` — handles "for 4" / "party of 4" / "for four" / "just me" / "a couple" |
| `name` | str (title-cased) | `extract_name` — handles "my name is X" / "this is X" / "under X" / standalone capitalized |
| `phone` | str (10 digits) | `extract_phone` — handles `555-123-4567` / `(555) 123-4567` / `+1 555-123-4567` |

### Intents

Detected by `intents.classify()`. Pure keyword + regex, no ML.

| Intent | Trigger examples |
|--------|------------------|
| `greeting` | "hi", "hello", "hey", "good morning" |
| `goodbye` | "bye", "goodbye", "that's all", "I'm done" |
| `cancel` | "cancel", "never mind", "forget it" |
| `help` | "help", "what can you do" |
| `confirm` | "yes", "yeah", "correct", "sounds good", "book it" |
| `deny` | "no", "nope", "that's wrong", "incorrect" |
| `change_value` | "actually", "instead", "wait", "change", "switch" |
| `provide_date` | "today", "tomorrow", "friday", "January 5" |
| `provide_time` | "7pm", "7:30", "noon", "half past seven" |
| `provide_party_size` | "for 4", "party of 6", "just me" |
| `provide_name` | "my name is X", "this is X", "under X" |
| `provide_phone` | "555-123-4567", "my number is..." |
| `ask_hours` | "what are your hours", "how late are you open" |
| `ask_location` | "where are you", "what's your address" |
| `ask_menu` | "do you have vegetarian", "what's on the menu" |
| `ask_parking` | "do you have parking" |
| `repeat` | "can you repeat that", "pardon", "say that again" |
| `silence` | empty input |
| `fallback` | nothing matched |

The classifier returns a ranked list (highest confidence first). Ties are
broken by rule order — more specific rules (like `change_value`) are
defined before more general ones (like `provide_date`).

## How decisions get made — the dialogue manager

The `DialogueManager.process(user_text, session)` method runs this pipeline:

```
1. Classify intents  ->  ranked list, top intent
2. Hard interrupts    ->  goodbye / cancel / silence / help fire from any state
3. Meta side-questions ->  ask_hours / ask_location / ask_menu / ask_parking / repeat
                           (answered, then return to current state)
4. Terminal states    ->  GOODBYE / BOOKED
5. GREETING           ->  bare greeting? greet back. otherwise, start booking.
6. CONFIRM            ->  confirm -> finalize. deny -> offer change. change -> apply.
7. Slot-asking states ->  extract slots, merge, advance.
8. Fallback           ->  reprompt.
```

The `_advance` method is the workhorse — given the current set of slots, it
decides the next state:

```
need date     -> ASK_DATE
need time     -> ASK_TIME
need party    -> ASK_PARTY_SIZE
have all 3    -> check availability
                unavailable -> reset time, ASK_TIME, offer alternatives
                available   -> continue
need name     -> ASK_NAME
need phone    -> ASK_PHONE
have all 5    -> CONFIRM
```

### Multi-slot utterances

A caller can say "tomorrow at 7pm for 4 people" — all three slots in one
utterance. The brain extracts every slot in one pass via
`slots.extract_all()` and advances straight to `ASK_NAME`. This is the
single most important UX feature: it makes the assistant feel fast for
callers who know what they want, without penalizing callers who give one
slot at a time.

### Mid-flow changes

A caller can change a slot at (almost) any time:

- In `ASK_TIME`: "actually change the time to 6pm" → extract new time, re-validate, advance.
- In `CONFIRM`: "actually make it for 5 people" → extract new party size, re-validate availability, re-confirm.

The brain handles this via the `change_value` intent, which triggers
`_try_change` → `_apply_changes`. `_apply_changes` re-validates
availability if any of `date`/`time`/`party_size` changed, then calls
`_advance` again.

### Side questions

A caller can interrupt the booking to ask about hours, location, menu, or
parking. The brain answers, then returns to the exact state it was in.
This is implemented as a "meta intent" — handled before the state-machine
logic, never advances the state.

### Repeats

"Can you repeat that?" returns `session.last_prompt` verbatim. The brain
records the last prompt on every response.

### Availability logic

`restaurant.BookingStore.is_available(date, time, party_size)` checks:

1. Is the restaurant open that day? (Closed Mondays.)
2. Is the requested time inside an opening window, with at least
   `BOOKING_DURATION_MIN` (120) minutes before close?
3. Is there a table big enough for the party? (Largest table seats 10.)
4. Is that table free at the requested time? (2-hour booking window,
   no overlap with existing bookings.)

If unavailable, `suggest_alternatives()` returns the 4 closest available
slots on the same day, sorted by distance to the requested time.

### Session state

`backend/sessions.SessionStore` keeps one `Session` per caller in memory.
Each session tracks: current state, slot values, pending booking ID, last
prompt, turn count, and a full history list. In production this would be
Redis.

## Edge cases handled

| Edge case | How the brain handles it |
|-----------|--------------------------|
| Caller says all slots in one sentence | `extract_all` pulls every slot in one pass; brain jumps straight to `ASK_NAME`. |
| Caller changes time mid-flow | `change_value` intent triggers `_try_change`; new time extracted; availability re-validated. |
| Caller changes party size at confirm | Same — `change_value` triggers re-validation, then re-confirm. |
| Caller asks for unavailable slot | `is_available` returns False with a reason; brain resets `time` slot, offers alternatives. |
| Caller asks for a closed day | Reason mentions the weekday; brain asks for another day. |
| Caller asks for outside-hours time | Reason lists the opening windows; brain asks for another time. |
| Caller asks for too-large party | Reason mentions the largest table; brain asks to reduce party size. |
| Caller asks a side question | Meta intent handled before state logic; brain answers and returns to current state. |
| Caller asks to repeat | `repeat` intent replays `last_prompt`. |
| Caller says "yes" with nothing to confirm | `confirm` outside CONFIRM state returns "nothing to confirm yet". |
| Caller says "no" with nothing to deny | `deny` outside CONFIRM state returns "I haven't suggested anything yet". |
| Caller says gibberish | `fallback` intent → "I didn't quite catch that" reprompt. |
| Caller says nothing (empty input) | `silence` intent → "I didn't hear anything. Are you still there?" |
| Caller says "cancel" mid-flow | `cancel` intent wipes slots, transitions to CANCELLED. |
| Caller says "bye" at any point | `goodbye` intent fires from any state, sets `end_call=True`. |
| Caller says "help" | `help` intent lists what the assistant can do. |
| Caller says "ok" alone | Matches confirm regex; in CONFIRM state, finalizes booking. |
| Caller spells out name | Handled by `extract_name`'s standalone-capitalized fallback (only called in `ASK_NAME` state). |
| Caller says phone in different format | `extract_phone` handles `555-123-4567`, `(555) 123-4567`, `+1 555-123-4567`, etc. |
| Caller says relative date ("today", "tomorrow") | `extract_date` resolves relative to `datetime.now()`. |
| Caller says weekday ("friday") | `extract_date` finds the next occurrence, rolls to next week if same day. |
| Caller says month/day ("January 5") | `extract_date` resolves, rolls to next year if past. |
| Caller says word-form time ("half past seven") | `extract_time` parses via word-number map; defaults to PM for hours 1-10 (dinner context). |

## Test coverage

The brain has 81 tests covering:

- `test_slots.py` (30+ tests): every slot extractor, including word forms, multiple formats, and None cases.
- `test_intents.py` (25+ tests): every intent category, including fallback and silence.
- `test_state_machine.py` (20+ tests): end-to-end flows for happy path, mid-flow changes, side questions, repeats, cancellations, unavailable slots, closed days, too-large parties, and the full state machine.
- `test_api.py` (7 tests): the FastAPI endpoints, session persistence, and edge cases.

Run them with `python3 -m pytest backend/tests/ -v`.

## What's NOT in the brain (intentionally)

- **No LLM, no embeddings, no ML model files.** Pure Python.
- **No external NLU service** (Dialogflow, Rasa, Lex, etc.).
- **No persistent storage.** In-memory only — fine for a demo.
- **No multi-language support.** English only.
- **No authentication.** Single-tenant demo.
- **No audio streaming to the backend.** STT runs in the browser.

These are all things I'd add in production — see README.md → "Production notes".

# REDELIVER — Design Document

## Use Case

**REDELIVER** is a voice assistant for missed-delivery rescheduling. When a
parcel delivery fails (nobody home, wrong address, etc.), the recipient can
call REDELIVER and:

1. **Reschedule** the delivery to a new date and time window.
2. **Redirect** the parcel to a nearby pickup point.
3. **Cancel** the delivery entirely.

4. **Check status** of the parcel.

The prototype is localized for Pakistan. Its fake pickup points use cities
across Pakistan, runtime delivery dates and times use Pakistan Standard Time,
and the browser speech controls request Pakistani English when available.
Pickup addresses and recipients are fictional demo data.

The assistant handles the conversation — from caller identification through
confirmation — and asks before suggesting a human-agent transfer.

The repository includes the deterministic backend and a React product site,
caller voice demo, and operations dashboard. The frontend uses browser-provided
speech recognition and speech synthesis when available; there is no phone
connection or external speech provider.

## The Brain: How Decisions Are Made

> **No LLM is used anywhere in the decision logic.** All intent detection,
> slot filling, and state transitions are plain Python code.

### Architecture Overview

```
Caller speaks
    → Browser speech recognition (or typed transcript)
    → React frontend sends transcript to the backend API
    → Two-pass normalizer (intent_text + digit_text)
    → Slot filler (extracts tracking ID, phone, date, period)
    → Intent detector (weighted keyword scoring, state-aware priority)
    → State machine (explicit if/elif transitions)
    → Service layer (verification, booking, pickup, cancellation)
    → Backend returns TTS-friendly reply and decision trace
    → React displays reply and speaks it with browser speech synthesis
```

### Text Normalizer (Two-Pass)

The normalizer produces two outputs from each raw transcription:

- **`intent_text`**: Number words preserved ("oh no" stays as "oh no", "one
  moment" stays as "one moment"). Used for intent detection where number
  words carry meaning.
- **`digit_text`**: Number words converted to digits ("five" → "5",
  "double oh" → "00", "triple nine" → "999"). Used by the tracking ID
  extractor and date parser.

Both passes share common preprocessing:
1. Lowercase and strip whitespace.
2. Remove non-printable characters (injection protection).
3. Truncate to 2000 characters max.
4. Strip speech fillers ("uh", "um", "er", "you know", etc.) — but
   **"like" is NOT stripped** to preserve "I'd like to…".
5. Collapse whitespace.

### Intent Detection

Weighted keyword + regex scoring with no external AI:

```
score = best_hit_weight + 0.15 × (extra_hits)  [capped at 1.0]
```

State-aware priority ensures `affirm`/`deny` win in confirmation states,
and disambiguation rules handle ambiguous phrases ("no wait" →
`change_of_mind`, "cancel that" → `deny`).

### State Machine

14 dialogue states with explicit transitions, including a follow-up state
that asks before ending after a completed action. Cross-cutting handlers for
silence, repeat requests, human agent handoff, and goodbye are checked
before state-specific logic.

### Data Layer

- **Parcels**: 21 fake parcels across 6 statuses (in_transit,
  out_for_delivery, failed_attempt, delivered, cancelled,
  returned_to_sender).
- **Delivery slots**: Generated at runtime from an injected clock (7-day
  window, 3 periods per day). Pre-booked entries create deterministic
  edge cases (fully booked day, nearly-full slots).
- **Pickup points**: 5 locations with varied opening schedules (weekday-only,
  7-day, closed Mondays, etc.).

All data is fake. No real people's details.

### Thread Safety

- `InMemoryParcelRepository` uses `threading.Lock` for all mutations.
- Booking and releasing are atomic; rebooking (release old + book new)
  happens in a single lock acquisition.
- `InMemorySessionStore` has a store-level lock plus per-session locks
  for turn serialisation.

### HTTP API

FastAPI exposes `GET /health` and the session lifecycle:

- `POST /sessions` starts a session and returns its ID and greeting.
- `POST /sessions/{session_id}/turns` processes one transcript and returns
  the reply, ended flag, and decision trace.
- `GET /sessions/{session_id}` returns the current state and turn history.
- `DELETE /sessions/{session_id}` marks the session ended.

Sessions and parcel mutations are held in memory. Restarting the backend
clears them. See `docs/BACKEND_GUIDE.md` for setup, sample requests, and the
full HTTP contract.

### Frontend Boundary

The React frontend in `frontend/` owns the marketing site, a dedicated `#voice`
call page, and dashboard layout, transcript presentation, keyboard and
microphone interaction, local theme/voice preferences, and displaying the
backend decision trace. Its HTTP wrapper is
`frontend/src/services/redeliverApi.js`.
The frontend does not implement intent detection, verification, booking,
parcel lookup, or session transitions. All such work is sent to the Python
backend API. During local development Vite proxies `/api` to port 8000.

Voice capture and spoken replies use browser-native Web Speech capabilities;
the frontend sends recognized text to the backend and speaks only the reply
returned by the backend. The hero's custom WebGL ray-marched 3D form reads
microphone amplitude through Web Audio while listening. Browser speech
synthesis does not expose its playback stream, so speaking uses a visibly
state-driven animation instead of claiming audio analysis. Microphone tracks,
audio contexts, animation frames, and WebGL resources are cleaned up. A CSS
fallback appears without WebGL, and reduced-motion preference disables the
continuous animation. Typed input remains the fallback for browsers without
speech recognition.

The dashboard maps the existing health endpoint and session lifecycle/history
endpoints to live status, the active transcript, and current session state. The
backend does not expose historical call lists, aggregate analytics, editable
agent records, accounts, billing, or integration management; the frontend
omits or labels those capabilities unavailable rather than fabricating data.

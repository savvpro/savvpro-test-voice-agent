# Design

## Use case and boundary

The assistant performs one complete job: it books one vehicle into a fictional automotive shop. It gathers customer, vehicle, service, and requested-slot data; checks duration/resource capacity; requests explicit confirmation; and writes one ephemeral booking.

Price quotes, repair-status lookup, existing-booking cancellation, multiple vehicles in one call, and real shop integration are deliberately out of scope. They receive bounded template replies.

## Architecture

```text
Browser microphone -> browser STT adapter -> transcript text
                                           |
                                           v
React page -> POST turn -> normalizer -> candidate parsers -> precedence/FSM
                                                           -> booking service/store
React page <- structured decision + response template <----+
     |
     +-> browser TTS adapter -> speaker
```

Browser STT may itself use machine learning, but it is outside the brain. It produces text only and cannot select an intent, next question, response, or action. The `app/conversation` package is deterministic, has no LLM SDK, receives no HTTP client, and is tested with network sockets disabled.

Server-side `SpeechToTextAdapter` and `TextToSpeechAdapter` protocol boundaries are described in PLAN.md for a future provider. The current browser implementation avoids keys and keeps the assessment small.

## Conversation brain

`status` is session lifecycle (`active`, `confirmed`, `aborted`, `expired`, `ended`). `state` is only the active dialogue step (`collecting`, `choosing_slot`, `confirming`).

Each turn:

1. Replays an already processed `turn_id`.
2. Rejects expired, terminal, or stale-version requests.
3. Normalizes text and extracts candidates without mutation.
4. Applies command precedence: empty, goodbye, restart, correction, standalone abort, offered index, contextual yes/no, help/out-of-scope, then field values.
5. Validates and merges accepted values, invalidating a selected slot after date/time/service changes.
6. Chooses the next missing field or checks availability.
7. Rechecks availability under the process lock before confirmation.

Responses are fixed templates populated with structured values. The UI displays action and reason codes so decisions are inspectable.

## Dates and availability

The fake shop uses `America/Chicago`. A weekday means its next occurrence strictly after today; `next Monday` means Monday in the next calendar week. An hour without AM/PM is ambiguous. Day-parts use fixed preference windows. The clock is injectable in tests.

Services have fixed duration and require a general bay, lift bay, electrical technician, or diagnostic technician. Alternatives prefer the same date, same day-part, smallest time distance, then earlier time.

## Concurrency and privacy

The UI creates one UUID per submitted turn and reuses it for transport retries. The server caches the corresponding response. An integer session version prevents concurrent mutation from two requests. A single process-wide lock makes availability-check-plus-insert atomic only within that process.

Phone numbers and raw transcripts are excluded from normal logs. API inspection and booking lookup also omit phone numbers. All data is fictional and ephemeral.

## Tradeoffs and limitations

- Rule-based parsing is predictable and testable but has narrower language coverage than an LLM.
- Browser speech makes setup easy but varies across browsers and may require vendor connectivity.
- In-memory storage is suitable for a take-home demo, not durability or horizontal scaling.
- The voice lifecycle receives a manual browser smoke test; deterministic backend behavior is automated.


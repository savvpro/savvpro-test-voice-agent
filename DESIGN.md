# Mezban design

## Job and scope

A fictional Pakistani restaurant receptionist for à la carte seating, fixed-slot buffets, price/menu questions, amendments, cancellation, booking lookup and local staff-assistance records. Food ordering, delivery, telephone networks, SMS, real payments and event planning are outside this version. Policies are listed in README.md.

Real-world inspiration: separate dining flows at https://steakstudio.com.pk/reservations?purpose=dining, fixed sittings/advance payment at https://arcadiancafe.com/wp-content/uploads/buffet-form/arcadian-hitea-reservation.html, and booking requests at https://ziafat.pk/. Demo prices and rules are invented; they do not represent these restaurants.

## Deterministic brain

Browser transcription → normalize vocabulary → prioritize control/information intents → extract slots → apply corrections → validate policy → ask missing question → read back summary → explicit yes → transactional availability check/write → response template → browser speech.

No LLM SDK, prompt, embedding or model is used for runtime decisions. `advance(state, transcript, now)` is independent of FastAPI and SQLite. Every response is a Python template. The inspector displays intent, state, last rule and awaiting field.

### State and parsing

`collecting → review → confirmed` for à la carte, or `review → payment_pending → confirmed` for buffet. Cancellation requires a separate explicit confirmation. Corrections return through validation/review.

Slots: dining, date, minutes after midnight, adults, child ages, seating, name, fictional phone. Multiple slots may arrive together. Generic guest counts mean adults; children are asked separately. Counts without child ages trigger clarification. Bare hours ask for AM/PM. Supported dates: ISO, today, tomorrow and next named weekday (a same-day weekday means next week). Asia/Karachi is authoritative; unit tests inject time.

Price/menu interruptions preserve progress. Dining changes clear the old time unless a new time arrives in the same turn. Adult counts and child ages replace previous values. Three failed comprehension attempts suggest typed examples or staff. Limited Urdu/Roman Urdu normalization does not provide unrestricted natural-language understanding.

## Availability and integrity

Three joinable four-seat tables per seating area. Reservations consume whole tables rounded up from all guests, including free children. Both dining modes share inventory. Overlap means existing start < new end and existing end > new start; adjacent bookings are valid.

Availability is checked on final confirmation, not guaranteed during review. Full slots produce up to three alternatives checked against the same inventory, ordered by distance from the requested time and then seating preference. Clicking an alternative supplies its time and seating through the same brain. Alternatives are suggestions, not holds; final confirmation always checks again.

SQLite `BEGIN IMMEDIATE` serializes availability checks and writes. Pending buffet holds consume capacity; expiry is evaluated during booking, payment and lookup. A periodic worker is unnecessary for capacity correctness.

Each transcript request has an ID. Response, state and booking writes commit atomically. Retrying that ID returns the same response. A fresh second yes after success also cannot create a second booking.

Amendments secure the replacement before marking the original replaced, in one transaction. Failure preserves the original. Buffet amendments require a new simulated deposit; financial transfers/refunds are not implemented.

Only the demo-payment endpoint can verify payment; a spoken claim cannot. Expired or inactive reservations cannot be paid. Cancellation releases capacity. Grace periods are communicated but arrival tracking is outside scope.

## API and security

- POST `/api/sessions`: start a call.
- POST `/api/sessions/{id}/turns`: transcript and request_id; returns reply/state/quote.
- POST `/api/sessions/{id}/demo-payment`: simulated verification.
- POST `/api/bookings/lookup`: reference plus fictional phone; resume session.
- GET `/api/health`: runtime check.

Pydantic bounds payloads, SQL uses parameters, and CORS allows local frontend origins. Session IDs act as bearer capabilities. This demo is not suitable for public deployment without authentication, rate limits, retention controls and stronger lookup verification.

## Validation

Backend tests cover transitions, pricing boundaries, corrections, invalid dates/times, fixed sittings, fallbacks, concurrent capacity, idempotency, expired holds, cancellation, failed amendments and lookup. Browser tests exercise the real API for booking/deposit/amendment/cancellation and mobile overflow. Physical microphone and speaker quality need manual verification; typed input uses the same brain.

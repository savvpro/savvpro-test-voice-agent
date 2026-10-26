# Phase 4: conversation API

FastAPI routes call `ConversationService`, which coordinates the existing FSM
and SQLite repository. Neither the brain nor the database imports FastAPI or
the service, and the brain does not import storage. No AI service is used.

## Run

From `backend`, with dependencies in `requirements.txt` installed:

```powershell
python -m uvicorn app.main:app --reload
```

Startup initializes `backend/data/reservations.sqlite3` and seeds fictional
table inventory, preserving existing reservations. Set `DATABASE_PATH` to use
another file. Paths supplied through the environment are relative to the
working directory unless absolute. The default path is independent of the
working directory. Importing `app.main` alone does not initialize storage.

The existing `GET /api/health` endpoint remains available. Interactive API
documentation is at `/docs`. Initialization errors are logged on the server;
storage-dependent requests receive sanitized errors rather than filesystem or
SQL details. Restart the server after fixing a startup initialization failure.

## Endpoints

### POST /api/conversations/start

No request body is required. Returns HTTP 201 with a server-generated, opaque
session ID. Each call starts a separate conversation.

```json
{
  "message": "Welcome to The Golden Fork! I'd be happy to help you make a reservation. What date would you like to book?",
  "session_id": "<returned-session-id>",
  "status": "ask_date",
  "collected_data": {"date": null, "time": null, "party_size": null},
  "reservation": null
}
```

### POST /api/conversations/message

Supply the returned session ID and a unique ID for this logical message:

```json
{
  "session_id": "<returned-session-id>",
  "request_id": "turn-001",
  "message": "tomorrow at 7pm for 4"
}
```

All fields must be strings. Session/message IDs must contain 1–128 characters;
the message must contain 1–2000 characters. Surrounding whitespace is stripped;
blank input and extra fields are rejected. Do not send reservation status or
structured booking overrides: the deterministic brain collects the details.

If the date, time, and party size are valid and a table is available, the
response has `status: "confirm"`, normalized `collected_data`, a summary asking
whether to book, and `reservation: null`. Nothing has been saved yet.

Send a separate affirmative message after reviewing the details:

```json
{
  "session_id": "<returned-session-id>",
  "request_id": "turn-002",
  "message": "yes"
}
```

A successful response is HTTP 200 with the following structure. IDs, timestamp,
date, and formatted message below are illustrative; actual values come from the
session and committed reservation.

```json
{
  "message": "Your reservation has been confirmed! ...",
  "session_id": "<returned-session-id>",
  "status": "completed",
  "collected_data": {"date": "2026-10-27", "time": "19:00", "party_size": 4},
  "reservation": {
    "reservation_id": "<saved-reservation-id>",
    "reservation_date": "2026-10-27",
    "reservation_time": "19:00",
    "party_size": 4,
    "status": "confirmed",
    "created_at": "<UTC-creation-timestamp>"
  }
}
```

Conversation status is the existing FSM state: `ask_date`, `ask_time`,
`ask_party_size`, `confirm`, `completed`, or `cancelled`. The internal table
assignment and database submission key are not exposed. There is no public
reservation listing or lookup endpoint; the successful conversation response
already supplies its reservation, avoiding an unnecessary unauthenticated
reservation-browsing API.

## Availability and confirmation behavior

The [Phase 3 policy](DATABASE.md) is unchanged: one smallest-fitting table per
party, 90-minute occupancy, and overlapping bookings forbidden.

* The FSM continues to handle validation, corrections, rejection, help, cancel,
  and restart using its existing rules and templates.
* The service checks availability before offering a complete set of details
  for confirmation. This is not a hold on the table.
* Only an explicit confirmation accepted by the FSM can trigger creation.
  An affirmative message that also changes details, such as `yes, for 6 people`,
  presents a new summary and requires another confirmation.
* Creation rechecks availability inside the existing SQLite write transaction.
  The service returns `completed` and a reservation only after that call succeeds.
* A slot taken between the summary and confirmation is rejected without another
  booking. The response becomes `ask_time`, clears the unavailable time, retains
  the date and party size, and asks for another time. The customer can also change
  the date or cancel. Selecting another time requires a fresh confirmation.
* Invalid/rejected details, incomplete conversations, and cancellation do not
  create reservations. Changes or cancellation after completion do not modify
  the committed reservation; the brain explains that such changes are unsupported.
* `restart` or `start over` resets the draft and its booking key. It does not
  delete earlier reservations. Another booking must be collected and confirmed.

## Retries, transactions, and errors

Retain the same `request_id` when retrying a message. The same ID and normalized
text return the original response without processing the turn again. The same
ID with different text returns HTTP 409 without changing state. IDs are scoped
to one session and must remain unique across restarts within that session.
Late retries replay their original response, which may describe an earlier
conversation state; clients should match responses to the relevant message ID.

A server-owned booking key additionally protects the SQLite write, even when
confirmation is retried using another message ID. Per-session locks serialize
concurrent messages; SQLite transactions and constraints continue to serialize
competing bookings across separate connections.

| HTTP status | Meaning |
| --- | --- |
| 200 | Message processed, including validation follow-ups or an unavailable slot |
| 201 | New conversation started |
| 404 | Unknown session; start a new conversation |
| 409 | Reused message ID with different text, or a booking-key conflict |
| 422 | Invalid JSON or request fields |
| 503 | Storage failure; retry the same request after recovery |
| 500 | Unexpected processing failure; generic error without internal details |

Errors return a JSON `detail` field. On a processing exception the service
restores the previous FSM state/history and does not cache a successful response.
An error after an uncertain commit does not imply no reservation exists: retry
the original confirmation so the preserved booking key can recover the committed
record instead of inserting another one. Client error messages do not claim the
booking succeeded or expose exception details. Server logs retain diagnostic errors.

## Verification and limits

From `backend`:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_conversation_api.py
python -m pytest -q -p no:cacheprovider
python -m tests.check_phase2_conversations
```

Integration tests run FastAPI's real lifespan with the real brain/repository and
an isolated `tmp_path` database. They cover success, rejection, validation,
corrections, availability races, cancellation/restart, duplicate and concurrent
requests, storage failures, and uncertain commit recovery. No test initializes
the development database.

Sessions, message replay caches, and locks are in process memory. Use one worker;
server restarts/reloads lose conversations but retain SQLite reservations. Old
session IDs then return 404. Session expiration, bounded cache retention,
authentication, persistent sessions, and multiworker coordination are not part
of this phase. Treat random session IDs as private conversation credentials.
Starting a conversation is not idempotent: reuse the returned session ID for
subsequent messages. The React client and Phase 6 browser voice controls are
documented in [frontend/README.md](../frontend/README.md). Voice input becomes
editable text and is submitted using the unchanged message schema; no audio
endpoint or speech service was added to the backend.

# The Golden Fork frontend — Phases 5–6

A responsive React + Vite chat interface for the existing Python reservation
assistant. The backend owns parsing, validation, availability, confirmation,
cancellation, and reservation creation. JavaScript only manages the interface,
API transport, response shapes, request retries, and optional browser voice
controls. No LLM is used for reservation decisions. Browser Web Speech APIs
provide dictation and spoken replies without application API keys or paid APIs.

## Run locally

Tested with Node 24.11.1 and npm 11.6.2. Use a recent Node version compatible
with the locked Vite/Vitest packages. Install frontend dependencies with `npm ci`.

In one terminal, from the repository root:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Click **Start Conversation**, then describe your
booking, for example `tomorrow at 7pm for 4`. Review the assistant's details and
confirm in a separate message. The reservation card displays only the committed
reservation returned by the backend. The **New conversation** button requests a
new session and clears the previous chat after that request succeeds; it does
not cancel an earlier booking.

Use Enter to send, Shift+Enter for a new line. Composition input is supported.
The interface includes labels, a skip link, keyboard focus states, live message
and status announcements, reduced-motion support, and mobile layout breakpoints.

## Optional voice features

### Dictate, review, and send

1. Start a conversation before using the microphone.
2. Select **Dictate a message** beside Send. Permit microphone access if asked.
3. The interface shows **Opening microphone**, **Listening**, and **Processing
   speech**, with a live preview of recognized words.
4. Select **Stop listening**, or let the browser finish the utterance. During
   startup/processing, **Cancel dictation** returns you to text input without
   submitting the recognized words.
5. Final recognized words are appended to the editable draft. Review dates,
   times, and guest counts and correct anything misheard before pressing
   **Send** or Enter. Interim/empty results are never submitted.

Dictation does **not** send automatically, including a spoken `yes`. Sending
uses the unchanged `/api/conversations/message` endpoint and the same request
ID/retry protection as text input. Recognized text is shown in the message box
and becomes a customer chat message only after Send. Overlong dictation must
be edited rather than silently truncated.

Text entry remains fully available without speech APIs or microphone access.
It is temporarily disabled while recording/finalizing to avoid edits racing
with recognition; cancel dictation to type instead. Recognition errors explain
denied permissions, missing microphones, no speech, network failures, and
unavailable language/service support. None of these errors sends a booking request.

### Spoken replies

**Spoken replies** is off initially. Enable it to hear future assistant replies,
including the welcome if enabled before starting a conversation. Restored or
previously displayed chat history is not replayed when enabling it.

**Stop speaking** interrupts current/queued playback. Disabling **Spoken replies**
also cancels it. A reply is handled once by its message ID: rerenders, retries,
or toggling the setting do not automatically repeat that reply. New replies
replace older queued speech instead of accumulating a backlog.

Starting dictation stops playback to prevent the assistant's audio from being
recognized. Starting a new conversation, sending another message, and leaving
the page also stop current speech. Playback errors/interruption do not change
conversation state; assistant replies always remain readable as text.

### Browser support, permissions, and privacy

The app detects `SpeechRecognition` or `webkitSpeechRecognition` independently
from `speechSynthesis` and `SpeechSynthesisUtterance`. Availability varies by
browser, operating system, language, and policy; recognition is not universally
supported. A browser may expose the constructor while its recognition service
is unavailable. Unsupported controls are disabled with a text fallback.
See [MDN recognition compatibility](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition#browser_compatibility)
and [speech synthesis documentation](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis).

Use localhost/127.0.0.1 for local testing and HTTPS when deployed. Microphone
access requires user consent and can be blocked by browser site permissions or
the operating system's microphone privacy settings. After denying access,
change those settings before trying again. No recording starts on page load.

Dictation uses English (`en-US`) to match the existing English parser. Spoken
replies request `en-US` with the browser's default available voice. Recognition
accuracy, permission prompts, supported devices, and available voices are
browser-dependent. Some browsers use a remote recognition service and need an
internet connection; audio can be sent to the browser vendor's service. This is
not guaranteed to run offline or entirely on-device. Some synthesis voices may
also depend on browser/OS services. See the
[MDN service note](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).

The app has no audio-upload backend, audio recording storage, speech SDK,
external credentials, or paid speech integration. Only the final text explicitly
sent by the customer reaches the existing Python conversation API. Browser/OS
policies can block spoken playback even when the API exists; the UI reports
playback failures and keeps the text response available.

### Manual voice checklist

With the backend and frontend running as above:

1. In a browser exposing recognition, start a conversation, select the
   microphone, allow access, and say `tomorrow at 7 PM for four`. Check the
   listening/processing indicators and the final editable transcript.
2. Before sending, change the guest count to six. Confirm that no customer
   message or booking is created until Send. Check the returned summary, then
   dictate `yes`; review it and Send to confirm through Python/SQLite.
3. Enable **Spoken replies**, send another message, and listen to its reply.
   Type in the draft box, toggle playback off/on, and verify the same reply is
   not read again. Check **Stop speaking** and starting dictation during playback.
4. Deny microphone access, try without speaking, and test a browser without
   recognition support. Verify error/fallback text and normal text submission.
5. If a message request fails, use **Retry same message**. Dictation and other
   submissions stay disabled while the original result is uncertain; its ID is
   retained exactly as before. A speech-service network error is separate from
   a reservation API error and never submits text on its own.

Physical microphone transcription and audible device output require these
manual checks; mocked automated tests do not establish their accuracy or quality.

## API and proxy

`src/api.js` makes relative same-origin POST requests:

* `/api/conversations/start` — no body, uses the returned session ID.
* `/api/conversations/message` — `{ session_id, message, request_id }` exactly as
  documented in [the backend API guide](../backend/API.md).

Assistant replies and reservation details are displayed from the JSON response.
Backend statuses are mapped to human-readable labels, without parsing customer
text or deciding whether to book in JavaScript. Unavailable-time and validation
messages appear verbatim from the assistant.

Vite proxies `/api` to `http://127.0.0.1:8000` for both `npm run dev` (5173) and
`npm run preview` (4173). Requests therefore need no additional CORS settings.
To use another backend, copy `.env.example` to `.env.local`, set
`API_PROXY_TARGET`, and restart Vite. This variable configures the server proxy;
it is not embedded in browser code.

For a production build:

```powershell
npm run build
npm run preview
```

Build output is `dist/`. A production host must reverse-proxy `/api` to FastAPI
on the same origin; Vite's development/preview proxy is not part of the static
build. This phase does not deploy either application. If a future deployment
uses separate origins, it must configure the backend's `CORS_ORIGINS` accordingly.

## Request IDs, loading, and recovery

Each logical customer message gets a new `crypto.randomUUID()` before sending.
The exact payload is retained in memory and tab-scoped `sessionStorage`, along
with the current session and transcript. A retry reuses the same payload and key
and does not add another customer bubble. Later messages get different keys.
The client does not retry automatically or invent a new session or booking
after a failed message.

Loading disables submission and starting another conversation. A synchronous
guard also blocks two submissions before React renders the disabled controls.
For a timeout, network error, malformed response, or retryable server error,
**Retry same message** uses the original payload. Other messages and new
conversations remain blocked until that uncertain result is resolved. A reload
restores the pending request and offers that same retry. The UI says a response
was not received, because the backend may already have processed the message.

HTTP 404/409 require a new conversation. HTTP 422 displays an error and permits
a corrected submission. Failed start requests can be retried; start is not an
idempotent endpoint but it cannot book a table by itself.

Storage and current limitations:

* Transcript/session storage is limited to the current browser tab. Closing it
  clears this client state. If browser storage is blocked or full, in-memory
  retries still work, but reload recovery cannot be guaranteed.
* Backend conversations and replay caches remain in process memory. Use one
  backend worker. A backend restart invalidates previous sessions; completed
  SQLite reservations remain durable. If a confirmation result was lost and
  the session is no longer recoverable, check with the restaurant before making
  another booking; this API has no public reservation lookup endpoint.
* Authentication, chat synchronization between devices, and session expiration
  are not implemented. Session IDs should be treated as private credentials.
* Voice is optional and depends on the browser/OS services described above.
  Dictation and the spoken-replies preference are not resumed automatically on
  reload. Existing conversation/pending-message recovery remains unchanged.

## Tests

From `frontend`:

```powershell
npm test
npm run build
npm run test:e2e
```

Vitest, jsdom, and Testing Library cover request payloads, response-contract
handling, keyboard submission, loading and duplicate prevention, confirmation,
cancellation, unavailable-time messages, safe retries, reload recovery, new
sessions, and errors. Test fixtures contain fake data only.

Phase 6 tests mock browser recognition and synthesis. They additionally cover
standard/prefixed constructors, permission/network/empty-result errors, interim
vs final results, editable drafts, repeated/late events, processing cancellation,
cleanup, spoken-reply opt-in, interruption, deduplication under StrictMode,
voice-message retries, and text fallback.

The optional `test:e2e` script uses Node built-ins, an installed Chrome/Edge
browser, Python, and the existing backend requirements. It starts its own local
FastAPI/Vite servers on free ports and creates a temporary SQLite database.
Set `CHROME_PATH` or `PYTHON` if the installed executables are not discoverable.
It verifies the real proxy and booking flow, rejection/correction before saving,
unique message IDs, reload/new-conversation behavior, desktop rendering, and
390px mobile overflow. It also injects mocked browser speech APIs to test
dictation -> editing -> existing API -> explicit confirmation, playback controls,
and no automatic replay. The browser check does not record real audio or call
a recognition provider. It captures ignored screenshots under `artifacts/` and
stops its servers/browser and removes its temporary database afterward.

From `backend`, run the complete existing regression suite:

```powershell
python -m pytest -q -p no:cacheprovider
```

All backend/API tests use temporary databases; no frontend test writes the
development database.

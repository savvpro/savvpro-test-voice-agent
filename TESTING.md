# Run the application and test edge cases

Use fake booking details only. Automated tests create temporary databases; manual
bookings persist in whichever development database the server is configured to use.

## Start the application on Windows

Verified tooling in this workspace: Python 3.13.7, Node 24.11.1, npm 11.6.2.
The commands below do not require changing PowerShell execution policy.

For this already configured workspace, `backend/venv` exists and its declared
dependencies were verified. You can start immediately with the following in
Terminal 1, without creating another environment:

```powershell
Set-Location 'D:\savvpro-test-voice-agent\backend'
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then run `npm run dev` from `D:\savvpro-test-voice-agent\frontend` in Terminal 2.
The first-time setup below uses the conventional `.venv` name for a fresh clone.

Terminal 1 — install backend dependencies on first setup, then start FastAPI:

```powershell
Set-Location 'D:\savvpro-test-voice-agent\backend'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On later runs, skip venv creation/dependency installation and use the last
command from that directory. Use one backend worker. `--reload` is optional
during development but a reload loses in-memory conversations.

Terminal 2 — install frontend dependencies on first setup, then start Vite:

```powershell
Set-Location 'D:\savvpro-test-voice-agent\frontend'
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to FastAPI at
`http://127.0.0.1:8000`. API documentation is at **http://127.0.0.1:8000/docs**.
Check the running backend in another terminal with:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/health'
```

The normal database is `backend/data/reservations.sqlite3`, created at startup.
For repeatable manual capacity tests, use a new scratch file instead of deleting
existing reservations. Before starting the backend, in Terminal 1:

```powershell
Set-Location 'D:\savvpro-test-voice-agent\backend'
$manualDbPath = Join-Path (Get-Location) ('data\manual-' + [guid]::NewGuid().ToString('N') + '.sqlite3')
$env:DATABASE_PATH = $manualDbPath
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep this server running through each scenario; changing the process loses
sessions. Scratch databases are Git-ignored. No cleanup/deletion is required to
run the tests. To use the normal database in a later terminal session, leave
`DATABASE_PATH` unset. `.env.example` files contain optional configuration only;
no API keys are needed.

## Normal booking

1. Click **Start Conversation**.
2. Send `tomorrow at 7pm for 4`.
3. Check the assistant's summary and `Ready for your confirmation` status. This
   has not saved a reservation yet.
4. Send `yes`. Expect `Reservation confirmed`, a success card, and the saved
   reservation reference/date/time/guest count.
5. Click **New conversation** to create another session. This does not cancel
   the reservation just created.

The UI offers no public reservation list. For automated proof of persistence
and row counts, use the SQLite/API tests rather than inferring a write merely
from a chat phrase.

## Manual conversation edge cases

Start a fresh conversation for each row unless a sequence is provided. The
table describes supported examples; it does not claim arbitrary language works.

| Case | Input/steps | Expected result |
| --- | --- | --- |
| Missing fields | `tomorrow` | Ask for time, retain the date. |
| Missing guest count | `tomorrow at 7pm` | Ask how many guests. |
| Rejected confirmation | Full details, then `not correct` or `incorrect` | Ask what to change; no new reservation. |
| Changed details | Full details, then `change the time to 8pm` | Show updated summary and require another acceptance. |
| Acceptance plus correction | Full details, then `yes, for 6 people` | Reconfirm six guests; do not book from this message alone. |
| Invalid time | `tomorrow at 7:99pm for 4`; separately try `25:00` or `13:75` | Reject the time; ask for a valid one. |
| Impossible date | `February 30` or `April 31` | Ask for a real calendar date without converting it to another date. |
| Past date | `yesterday` or `January 1, 2020` | Reject as past. |
| Invalid guests | `tomorrow at 7pm for -2`; separately try `0 guests` and `21 guests` | Ask for a guest count from 1 to 20. |
| Ambiguous time | `tomorrow at 7pm or 8pm for 4` | Ask to choose one time. |
| Invalid correction | Full details for four guests; `actually 50 people`; then `yes` | Clear guest count and keep asking; do not silently book four. |
| Cancel draft | Full details, `cancel`, then `yes` | Stay cancelled, save nothing. |
| Restart draft | Some details, then `start over` | Clear collected fields and ask for date again. |
| Terminal protection | Complete booking, then `change the time to 8pm` | Explain completed-booking changes are unsupported; saved booking is unchanged. |
| Unexpected text | `what is the weather like` | A relevant follow-up; no booking. |

Yearless dates roll forward, so `January 1` is not a reliable past-date test.
Use an explicit year or `yesterday`.

## Manual unavailable-slot test

Use a fresh scratch database and the same running backend for these steps:

1. In conversation A, book `tomorrow at 7pm for 20`, then `yes`.
2. Start conversation B and request `tomorrow at 7pm for 20`.
3. Expect no suitable table, retained date/party size, and a request for another
   time. A premature `yes` must not book the unavailable time.
4. Send `8:30pm`. Expect a new confirmation summary; send `yes` to save it.

There is only one fake 20-seat table. Its 90-minute occupancy means 20:30 is
adjacent and available, while 20:29 still overlaps the 19:00 reservation.

To exercise the preflight race through the UI, open two independent sessions
before either confirms. Ask both for the same 20-person time, then confirm both.
Exactly one should complete; the other should ask for a new time. Automated
concurrency tests verify this with independent requests/connections.

## Retry and network checks

* Double-click Send during a request. Controls should prevent duplicate submits.
* To test response recovery, start a conversation while online, then take the
  browser offline before sending a message. Expect an error and **Retry same
  message**. Restore connectivity and retry. Do not start a new logical request
  when a previous confirmation's outcome is uncertain.
* In browser Developer Tools → Network, compare the failed message and retry
  JSON: `session_id`, `message`, and `request_id` must be identical. Later
  messages must have new IDs. The customer bubble should not be duplicated.
* Reload while a failed message is pending, then retry after recovery. Tab
  session storage retains the payload if storage is available.
* Restarting the backend is different from a transient network failure: its
  sessions are lost and old IDs return 404. If a confirmation result was lost,
  check with the restaurant before making another booking. Stored reservations
  survive the restart; the API intentionally has no public lookup endpoint.

Browser offline mode is useful for the API transport check, but a browser
vendor's speech service may not follow DevTools network emulation. Recognition
and API error paths also have separate automated coverage.

## Voice checks on a physical device

1. In a supported browser, start a conversation, click the microphone, allow
   access, and speak a short English booking request.
2. Verify opening/listening/processing states and the interim preview. Stop
   listening or cancel processing. Empty speech must not send a message.
3. Correct the final transcript in the textbox, then Send. Dictated `yes`
   likewise requires explicit Send and the normal Python confirmation logic.
4. Enable **Spoken replies** for future replies. Test **Stop speaking**, disable
   the checkbox, type in the draft to cause rerenders, and toggle on again.
   The same reply should not repeat automatically.
5. Start dictation during playback; it should stop the assistant's speech first.
6. Deny microphone permission and check the clear error/text fallback. Check a
   browser without recognition and, if possible, one without synthesis.

Browser/vendor/OS support and available English voices vary. Audio may be sent
to a browser-vendor service and may require internet. The automated voice tests
and browser integration use mocks; real microphone accuracy and audible output
have not been verified in this workspace. More details are in
[frontend/README.md](frontend/README.md).

## Automated tests

With the backend venv installed:

```powershell
Set-Location 'D:\savvpro-test-voice-agent\backend'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m tests.check_phase2_conversations
```

Frontend tests/build (existing server processes are not required):

```powershell
Set-Location 'D:\savvpro-test-voice-agent\frontend'
npm test
npm run build
```

Browser integration starts and stops its own servers with a temporary database:

```powershell
Set-Location 'D:\savvpro-test-voice-agent\frontend'
$env:PYTHON = 'D:\savvpro-test-voice-agent\backend\.venv\Scripts\python.exe'
npm run test:e2e
```

Chrome or Edge must be installed. If not discovered automatically, set
`CHROME_PATH` to the installed Chromium browser executable. Browser screenshots
are kept under ignored `frontend/artifacts/`. No physical microphone or paid
speech service is used by that check. Tests never use the development database.

The Phase 7 verification used both the system `python` interpreter and the
existing `backend/venv` with the exact declared dependency versions, including
the browser check with `PYTHON` pointing to that interpreter. It did not create
a fresh environment. Exact executed commands/results are recorded in
[SUBMISSION.md](SUBMISSION.md).

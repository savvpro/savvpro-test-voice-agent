# AI session log

Running notes from building this project with Claude Code (model: Claude Opus 5.5), kept
as raw material for `AI_USAGE.md`. Each phase lists what the AI got wrong or had to fix,
where the work deviated from `PLAN.md`, and anything else worth mentioning.

Token counts are not in this log: the assistant cannot see its own usage. Capture them
with `/cost` or `/usage` at the end of each session (and `npx ccusage` for totals).

## Phase 0 — Setup

- Only Python 3.14 is installed on the dev machine; the plan assumed 3.11. Everything
  installed and ran on 3.14 (including `piper-tts` and `faster-whisper`), so the project
  targets 3.14 (`pyproject.toml`).
- The plan expected `backend/requirements.txt`; the file was at the repo root, so it was
  moved into `backend/` unchanged.
- `requirements.txt` had a typo (`ruff>=0.5.` with a trailing dot). pip accepted it; it was
  fixed during the Phase 0 wrap-up.
- The first `pip install` created a virtualenv at the repo root before the backend
  layout existed; it was later deleted in favour of `backend/.venv`.
- Commit attribution was turned off in `.claude/settings.json`, and commit-message rules
  were added to the (local, untracked) `CLAUDE.md`.
- Personal working files (PLAN.md, CLAUDE.md, `.claude/`) were removed from branch
  history with `git filter-branch`. **Gotcha:** filter-branch's final checkout deleted those
  files from disk too. The assistant had backed them up first and restored them.

## Phase 1 — Database and fake data

- **Deviation:** `appointments.slot_id` uniqueness is a *partial* unique index (only rows
  with `status = 'booked'`), not a plain unique column. A plain unique column would make a
  cancelled slot impossible to book again. The DB still rejects two active bookings for one
  slot.
- Double-booking is prevented by a conditional `UPDATE ... WHERE is_booked = false` plus
  that index; tests cover same-session, two-connection and raw-insert cases.
- **AI mistake (test):** a test meant to check "soonest appointment by phone" picked two
  slots that were both at 09:00 (one per doctor), so neither was sooner. Fixed the test
  setup, not the code.
- Ruff asked for quoted forward references in the models to be unquoted (UP037); that
  works on Python 3.14's deferred annotations, and the tests confirm it.

## Phase 2 — NLU

- **dateparser surprises:** `"next monday"` and `"this friday"` return `None`, and
  `"the 5th"` returns a date that has already passed even with
  `PREFER_DATES_FROM="future"`. Both are worked around in `entities.py` and covered by tests.
- **Classifier accuracy started at 0.70** on the held-out split (25–35 utterances per
  intent). Hyper-parameter tuning (C, n-gram ranges, LinearSVC, SGD) moved it by less
  than 1 point; what helped was data and representation.
- **Deviation — entity placeholders ("delexicalization"):** before classification, entity
  values are replaced by placeholder words ("cardiology on monday" → "somedepartment on
  somedate"). The biggest single gain (inform 0.70 → 0.82 F1). Not in the plan.
- **AI-introduced bug — YAML type coercion:** `03001234567` in `intents.yaml` loaded as
  an *octal integer* (402995575), and `yes`/`no` loaded as booleans. The assistant's own
  script for merging new utterances then wrote them back as the words `true`/`false`, so
  the training data was silently corrupted. Spotted in a list of misclassified utterances;
  fixed by quoting, a loader that rejects non-strings, and a test.
- **AI bug — booking reference regex:** it matched any 6-letter word starting with "sc"
  ("screen", "school", "scared"). Spotted when "my phone screen is broken" became
  "my phone bookingref is broken" in the training features. Fixed with regression tests.
- **AI over-correction:** lowering the doctor-name fuzzy threshold from 85 to 80 (to accept
  "dr saema") also made "with usama" match Dr. Saima. Split into 80 after "dr/doctor" and
  85 after the weaker "with".
- Other regex false positives caught during manual checks: "go to 2 doctors" parsed as the
  time 14:00; "my name is Bilal Aslam" matching the doctor of the same name.
- Data was added in 8 rounds (561 → 1,726 utterances). Some early training labels were
  ambiguous ("is parking free", "do you have a pharmacy") and were removed.
- **Deviations from the plan:** char_wb n-grams 2–4 instead of 3–5 (same accuracy, smaller
  model); LogisticRegression C=10 (the default spread probabilities too thinly to pass the
  0.60 fusion threshold); weights stored as float32 (halves the file, max probability change
  4e-8). The model is 558 KB and is committed.
- **The report prints two views:** the plan's 80/20 split, and 5-fold cross-validation where
  every utterance is predicted once. With only 10–50 test examples per intent the split is
  noisy (one error moves an intent's F1 by 0.03–0.10).
- **Not fully met:** "every intent ≥ 0.85" — final held-out accuracy 0.902 (CV 0.903), but
  `list_departments` is 0.833 on the split and `out_of_scope` 0.845 in CV. Stopped after 8
  rounds as gains had flattened; reported rather than tuned to the number.
- Some fixes to Phase 2a files (YAML quoting, booking-ref regex) landed in the Phase 2b
  commit.

## Phase 3 — Dialogue manager

- **AI bug found in a manual run:** "my number is 0321" was treated as "change the phone
  number" (the word *number* matched a "which field do you want to change" rule), so the
  caller never got the format hint. Field-name clearing now only happens on a
  `change_request` or right after "what would you like to change?".
- **AI wrote a meaningless test** (`test_greeting_time_is_frozen`, asserting constants);
  removed before committing.
- **Weak test tightened:** one edge-case test checked the chosen slot against *all*
  bookings (including the ones the test made for "someone else"); it now checks the
  caller's booking by reference.
- **Mutation check:** temporarily disabling the emergency rule and the "pick an offered
  slot" logic made 7 edge-case tests fail, so the tests do exercise the behaviour.
- **Deviations from the plan:**
  - `app/clinic.py` holds clinic facts (name, invented address, opening hours, 30-day
    booking window) shared by seed data, policies and replies.
  - `ClinicRepository` (in `repository.py`) binds the repository functions to one
    session and clock; it is what the manager gets injected with.
  - `Frame` is a pydantic model rather than a dataclass so it serialises straight into
    API responses in Phase 4.
  - `check_availability` flows into the booking flow: the offered times can be picked
    and booked directly.
  - Entities are merged at any state, but only on slot-carrying intents: otherwise
    "what time do you close on Saturday?" would change the booking date.
  - Extra `Decision.action` values for the UI: `not_understood`, `silence`, `aborted`,
    `slot_unavailable`, `cancel_declined`, `ended_silence`.
  - Rescheduling keeps the same doctor by default.
- **Known limitations:** the "3 nearest" search ignores a requested doctor; "next Monday"
  means the coming Monday; offers list date and doctor, which is long when spoken.
- The emergency reply points callers to 1122 (Pakistan's public Rescue number) on purpose;
  it is the only real-world contact detail in the app.

## Phase 3 follow-up — nearest slots and the requested doctor

- Fixed the known limitation above: when the requested time is taken, the "3 nearest"
  offer now lists the requested doctor's nearest slots first and only fills the remaining
  places with other doctors in the department. Repository and conversation tests were
  checked to fail without the fix.

## Phases 4 and 5 — API, CLI, speech

- **Real incompatibility found by running real audio, not by the tests:** faster-whisper
  1.2.1 calls `av.open(..., metadata_errors=...)`, which PyAV 19 (installed) removed, so
  every transcription crashed. The fake-STT API tests could not catch this. Fix: decode the
  audio ourselves with PyAV (webm/ogg/wav to 16 kHz mono float32) and hand Whisper an array.
  Checked with Piper WAV and a webm/Opus re-encode, like the browser sends.
- **Download script failed on macOS:** python.org's Python 3.14 ships without CA
  certificates, so `urllib` couldn't verify Hugging Face over HTTPS. The script now uses the
  `certifi` bundle (already installed with httpx) instead of asking the user to change their
  system.
- **Startup was contacting Hugging Face** every time Whisper loaded (a revision check, and a
  140 MB download if the model was missing). Whisper now loads with `local_files_only=True`;
  a missing model means a warning and text-only mode, and `download_models.py` is the only
  thing that downloads.
- **AI test mistakes caught before committing:**
  - The "multipart without an audio field" test first sent a form-encoded body, so it
    passed for the wrong reason (it hit the JSON error). It now sends multipart with
    another field and checks the exact error message.
  - A filler test (asserting a module didn't import faster-whisper) was removed.
- **Deviations from the plan:**
  - The STT/TTS *interfaces* (and `NullTTS`) came in the Phase 4 commit so the audio
    endpoint could be built and tested with fakes; the real engines came in Phase 5.
  - Startup creates the tables and seeds the fake clinic if the database is empty, so
    `make run-backend` and `python -m app.cli` work without `make seed` first.
  - Extra response fields: `session_id` and `transcript_confidence` (Whisper's average
    token probability). `audio_mime` is null when there is no audio.
  - Error codes: unknown/expired session 404; audio when no STT is loaded 503 ("send text
    instead"); undecodable audio or a bad body 422.
  - The admin appointments view masks phone numbers (`0300****567`).
  - Each turn builds a fresh `DialogueManager` bound to that turn's DB session; the reply
    seed is `session seed + turn number`, so phrasing varies but tests stay deterministic.
  - The NLU is warmed up once at startup (the first parse took ~145 ms, later ones ~2 ms).
  - The CLI's loop (`chat()`) takes `read`/`write` functions, so it has its own tests.
  - Slow tests are skipped unless `RUN_SLOW=1` (`make test-slow`); also skipped if the
    models aren't downloaded.
- **Measured on the dev Mac (CPU):** model load ~1.3 s; per turn roughly STT 0.35–0.8 s,
  NLU 2 ms, dialogue <5 ms, Piper 0.05–0.2 s.
- **Noticed, not fixed (NLU, Phase 2 territory):** "I need a cardiologist next tuesday
  morning" was classified `nlu_fallback` (0.44) with the committed model. The booking
  still worked because the entities carried it, but it is worth more training data.
- **To do in Phase 7:** pin versions (`faster-whisper`, `av`, `piper-tts`) now that the
  combination is known to work with the decoder workaround.

## Final phase — booking coverage, web client, CI, docs

- **Booking intent gap fixed:** 25 booking utterances that combine department + date + time of
  day were added (1,726 → 1,751). "I need a cardiologist next tuesday morning" went from
  `nlu_fallback` (0.44) to `book_appointment` (0.99) and has a regression test. Held-out
  accuracy 0.900, 5-fold CV 0.912 ± 0.010; every intent ≥ 0.86 in CV, two (out_of_scope,
  reschedule) just under 0.85 on the noisy held-out split, reported as is.
- Speech packages pinned to the tested versions (faster-whisper 1.2.1, ctranslate2 4.8.4,
  av 19.0.2, piper-tts 1.8.0).
- **Node.js wasn't installed** (and no Homebrew). The official Node 22 LTS binary was
  downloaded into `~/.local/node` after checking its SHA-256 against nodejs.org's list; nothing
  system-wide was changed.
- **The web client was tested in a real browser**, not just with vitest: headless Chrome
  driven over the DevTools protocol, holding the push-to-talk button while a Piper-generated
  WAV played as the microphone. That run found three real problems the unit tests didn't:
  - **Whisper hallucination ended a call.** On a mostly silent recording Whisper produced
    "Thank you for watching. Bye now." (a known Whisper habit learned from video subtitles),
    and "bye" hung up. Fix: drop segments Whisper itself marks as non-speech
    (`no_speech_prob > 0.6` with `avg_logprob < -1`) and known subtitle phrases; tested with
    stand-in segments.
  - **The new booking wasn't visible** in the appointments panel: it listed the 50 soonest
    appointments, and the seed pre-books 30% of three weeks. Added `order=recent` to the API so
    the panel shows the newest bookings first, highlighted.
  - A React warning: a `useEffect` arrow returned a value.
- **Harness problems that were not app bugs (worth knowing for the write-up):** Chrome's
  sandbox silently blocked the fake-microphone WAV (recorded pure silence), and the fake mic
  loops the file on its own clock, so push-to-talk caught random fragments ("I'm your
  rheologist…"). The final harness stubs `getUserMedia` to play the WAV from the moment the
  button is pressed: 3/3 runs then transcribed the sentence exactly and completed the booking.
- **Docs written by the AI had invented details, caught by running them:**
  - The README's example conversation assumed changing the date re-offers times; it actually
    keeps the chosen time and doctor. The table was rewritten from a real CLI run.
  - DESIGN.md claimed "oh three hundred" normalizes to "0300"; it doesn't, so it was removed.
    Every other quoted example was checked against the code.
- **Changed at the user's request:** the agent now greets with "Hello" and ends with "Bye"
  instead of "Assalam o Alaikum" / "Allah Hafiz". Callers who say those are still understood.
- **Deviations:** CORS also allows `127.0.0.1:5173`; the greeting/hallucination fix went into
  its own `fix:` commit rather than the web-client commit; UI screenshots are in
  `docs/screenshots/`.

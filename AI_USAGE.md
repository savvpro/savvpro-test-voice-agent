# AI usage

How AI tools were used to build this project, how the work was kept under control, and where
the AI got things wrong. The detailed, phase-by-phase notes written during the build are in
[docs/ai-usage/session-log.md](docs/ai-usage/session-log.md). This page summarises them.

> **AI helped write the code and the training data. No LLM runs at runtime or makes any
> decision.** The receptionist's brain is regex rules, fuzzy matching, a scikit-learn
> classifier trained on our own examples, and a state machine. The backend has no
> OpenAI/Anthropic/Gemini package or API call, and CI fails if one appears.

## Tools

| Tool | Used for |
|---|---|
| **Claude chat** | Planning before any code: choosing the use case, the architecture (local Whisper + hybrid NLU + state machine + local Piper), the list of messy-caller cases, writing `PLAN.md` (a local working file, not committed; its messy-caller list is in DESIGN.md §5), and drafting the phase-by-phase prompts. |
| **Claude Code** (CLI, in VS Code) | All implementation: backend, NLU and training data, dialogue manager, API, speech, frontend, tests, CI and these docs. Run one phase at a time from those prompts. |

## How AI was used, phase by phase

| Phase | What the AI did (Claude Code) | What the phase prompt required |
|---|---|---|
| 0 · Setup | Backend skeleton, config, health route, Makefile; checked the speech packages install on Python 3.14 | Use the existing `requirements.txt`; stop once `/health` works; git rules, no AI attribution in commits |
| 1 · Database | Models, repository, double-booking protection, fake seed data, tests | `make seed` and `make test` green before committing |
| 2 · NLU | Normalizer, rules, fuzzy matching, entity extraction, 1,700+ training utterances over 8 rounds, classifier, train/evaluate script | ≥ 25 utterances per intent; future-preferring dates in the clinic timezone; no "no" match inside "know"/"now"; retrain if an intent is under 0.85; commit the model only if under 1 MB |
| 3 · Dialogue | Frame-based state machine, reply templates, 54 conversation tests | Changes merged at any state and acknowledged; 3 nearest slots, chosen by "the first one" or a time; a test for every messy-caller case in `PLAN.md` |
| 4 · API + CLI | Session store, conversation service, routes, terminal chat | API tests with fake speech engines |
| 5 · Speech | Whisper and Piper engines with fallbacks, model download script, real-audio test | Never crash if a model fails to load; one real Piper → Whisper test |
| 6 · Web client | React page, push-to-talk, Brain panel, appointments panel, vitest tests; tested it in a real (headless) browser | Clear mic-permission error; "Demo — fake data only"; later, "Hello"/"Bye" instead of Urdu greetings |
| 7–8 · CI + docs | GitHub Actions workflow, README, DESIGN, this file | Final audit of the assessment checklist |

## How the work was controlled

- **One phase per prompt.** Every prompt named the exact scope, the checks to run and the
  commit message. The AI was told not to build later phases early. Project rules lived in a
  local `CLAUDE.md`: no LLM in the brain, fake data only, no secrets, queries only in the
  repository, templates only in `responses.py`.
- **Tests before every commit.** `make test` and `make lint` had to pass, and failures had to
  be fixed "without weakening tests". The final suite has 531 backend tests and 7 frontend tests.
- **Checking that tests can fail.** Passing tests weren't trusted on their own:
  - the emergency rule and the slot-picking logic were disabled on purpose (7 edge-case tests
    failed);
  - the "prefer the requested doctor" tests were run against the old code (all 3 failed).
- **Manual runs with real input.** The CLI, real HTTP calls with Piper-generated audio, and a
  headless Chrome session with a fake microphone. Each of these found bugs that the unit tests
  could not (below).
- **Scope and hygiene rules.** Each commit had a prescribed message and scope; `git status` was
  checked before every commit, and personal working files (PLAN.md, CLAUDE.md, `.claude/`) are
  gitignored and were removed from history.

## Where AI got things wrong

| # | What went wrong | How it was caught | Fix |
|---|---|---|---|
| 1 | **YAML silently corrupted the training data.** `03001234567` loaded as an *octal integer* and `yes`/`no` as booleans. Then the AI's own merge script wrote them back as the words `true`/`false`. | A misclassification list contained "true" as an utterance | Quoted the values; the loader now rejects anything that isn't a string; added a test |
| 2 | **Booking-reference regex matched "sc" words**: "screen", "school", "scared" became booking refs. | "my phone screen is broken" became "my phone bookingref is broken" in the training features | Tightened the pattern; regression tests |
| 3 | **dateparser surprises:** "next monday" returned `None`, and "the 5th" returned a date already passed, even with "prefer future". | Entity tests | Own handling for "next/this <weekday>" and day-of-month; tests |
| 4 | **"number" read as a change request:** "my number is 0321" matched the field name "number", so the agent cleared the phone and never gave the format hint. | Manual CLI run | Field names only clear a slot on a real change request or after "what would you like to change?" |
| 5 | **`git filter-branch` deleted working files from disk.** Removing PLAN.md/CLAUDE.md from history also removed them from the working tree. | Immediately after the command | The AI had made a backup first and restored it |
| 6 | **Meaningless or weak tests.** One test only asserted constants; another checked a module's imports; an edge-case test checked the chosen slot against *all* bookings, including ones the test itself made. | Review before committing | The filler tests were deleted; the weak one now checks the caller's own booking by reference |
| 7 | **A test passed for the wrong reason.** The "multipart without an audio field" test actually sent a form-encoded body and hit the JSON error path. | Review of what the request really sent | Sends real multipart and checks the exact error message |
| 8 | **PyAV / faster-whisper incompatibility.** faster-whisper 1.2.1 passes an argument PyAV 19 removed, so **every** real transcription crashed. All API tests passed, because they used fake speech. | The first real audio run | Decode audio ourselves with PyAV; added a slow real-audio test; pinned versions |
| 9 | **Model download failed on macOS** with `CERTIFICATE_VERIFY_FAILED`: the python.org Python ships without CA certificates. | Running the script | The script uses the `certifi` bundle instead of asking the user to change their system |
| 10 | **"I need a cardiologist next tuesday morning" was misclassified** as `nlu_fallback` (0.44). The booking only worked by luck, through the entities. | Noticed in a manual CLI run | 25 new training examples of that shape; now `book_appointment` at 0.99, with a test |
| 11 | **Whisper's hallucination ended a call.** On near-silence it produced "Thank you for watching. Bye now.", and "bye" hung up. | Real-browser test with a fake microphone | Drop segments Whisper marks as non-speech, and known subtitle phrases |
| 12 | **Invented details in the docs.** The README's sample conversation assumed behaviour the agent doesn't have, and DESIGN.md quoted a normalization ("oh three hundred" → "0300") that doesn't exist. | Running every quoted example | Rewritten from real runs |
| 13 | Smaller ones: lowering a fuzzy threshold to accept "dr saema" also made "with usama" match Dr. Saima; "go to 2 doctors" parsed as 2 PM; a React effect returned a value; a test of "soonest appointment" used two slots at the same time. | Tests and manual checks | Split the thresholds by context; a bare number is only a time when the agent asked for one; fixed the effect and the test setup |

**The pattern:** the AI's code usually passed the tests it wrote itself. The real bugs showed up:
- when something *outside* the tests was exercised (real audio, a real browser, real
  library versions, a real OS); and
- when its claims were checked against the running system instead of trusted.

## Token usage

Exact token counts were not available. Claude Code and Claude chat were used for planning and
implementation.

No usage screenshots or token logs were captured into `docs/ai-usage/`. The session log there
records the work itself.

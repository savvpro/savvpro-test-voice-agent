# AI Usage Log

This document tracks all AI tool usage during the build. It is updated continuously, not written after the fact.

---

## Tools Used

| Tool | Purpose | Notes |
|---|---|---|
| **Antigravity** (Gemini 2.5 Pro) | Primary coding assistant — architecture, all code generation, debugging, test authoring, documentation | Entire build conducted in a single Antigravity agentic session |

---

## What the AI Generated

The following components were generated in full by AI with no manual code changes:

| Component | File(s) |
|---|---|
| FSM Design Document | `docs/DESIGN.md` |
| Intent Classifier | `backend/brain/intents.py` |
| Slot Extractor | `backend/brain/slots.py` |
| Availability Grid | `backend/brain/availability.py` |
| Response Templates | `backend/brain/responses.py` |
| FSM State Machine | `backend/brain/fsm.py` |
| FastAPI Backend | `backend/main.py` |
| STT Integration | `backend/brain/stt.py` |
| TTS Integration | `backend/brain/tts.py` |
| Piper Model Download Script | `backend/scripts/download_piper_model.py` |
| Terminal Test Client | `backend/scripts/test_client.py` |
| Unit Test Suite (126 tests) | `backend/tests/test_*.py` |
| Next.js Frontend UI | `frontend/src/app/page.tsx`, `layout.tsx`, `globals.css` |
| TypeScript Types | `frontend/src/types/agent.ts` |
| README | `README.md` |
| All `package.json`, `next.config.mjs`, `tailwind.config.ts`, `tsconfig.json` | `frontend/` config files |

---

## What the AI Got Right

- Designed the intent-first FSM architecture in [`docs/DESIGN.md`](../docs/DESIGN.md) isolating correction handlers from normal slot extraction — this paid off during E2E testing where correction flows worked naturally.
- Modularized brain logic cleanly into pure functions across `intents.py`, `slots.py`, `availability.py`, `responses.py`, and `fsm.py` — made unit testing easy.
- Built the FastAPI WebSocket server with proper binary/text/base64 frame multiplexing.
- Generated a comprehensive 126-test suite covering intents, slots, multi-slot utterances, mid-flow corrections, FSM lifecycle, STT, TTS, and 5 E2E scenarios.
- Proposed the PyAV monkeypatch fix for `faster-whisper` + `av >= 15` incompatibility — identified the root cause immediately from the traceback.
- Built an attractive dark-theme Next.js UI with audio visualizer, push-to-speak, slot inspector, FSM state badge, and booking confetti in a single pass.

---

## What the AI Got Wrong / Required Correction

1. **Over-eager Doctor Extraction**: Bare surname aliases (e.g. "Smith") in `extract_doctor` caused names like "John Smith" to prematurely bind `doctor = "Dr. Smith"`. Fixed by requiring explicit prefixes ("Dr.", "Doctor") or contextual verbs ("prefer", "with") for doctor surnames.

2. **Regex Correction Patterns**: Expressions like `actually I'd prefer 3pm` and `Wednesday instead` failed to trigger `CHANGE_TIME` and `CHANGE_DATE` because boundaries (`\b`) didn't match immediately before digit-meridiem combos like `3pm`, and `instead` was only checked before rather than after the date/time term. Refined patterns to handle suffix modifiers and compact time representations.

3. **Leading Filler Stripping**: Name extraction missed `um John Smith` due to strict full-match word tokenization; updated `extract_name` to trim conversational hesitation markers (`um`, `uh`, `er`, `well`).

4. **Unclear Count Tracking**: During slot extraction failures in normal FSM advance, `unclear_count` was getting reset unconditionally, preventing the 3-strikes handover logic from triggering. Updated the state machine transition to preserve and increment unclear counts correctly.

5. **PyAV 15+ Compatibility in faster-whisper**: `faster-whisper`'s `decode_audio` invokes `av.open(..., metadata_errors="ignore")`. In modern `av` versions (≥15), the `metadata_errors` keyword argument was removed, triggering a `TypeError`. Implemented an in-memory monkeypatch adapter in `WhisperSTT._load_model` to transparently remove unsupported arguments without breaking wheel dependencies.

6. **Cancel Confirmation Logic**: `_cancel_confirm` method only accepted `Intent.CONFIRM` to proceed with cancellation — but when the user says "Yes, please cancel it", the classifier correctly returns `Intent.CANCEL` (not CONFIRM). Fixed to treat `Intent.CANCEL` as a confirmation of the cancel intent within the `CANCEL_CONFIRM` state.

7. **Reschedule Flow State Ordering**: After collecting the reschedule date/time, `_next_question` would incorrectly loop back to collect `name` and `doctor` before confirming the reschedule. Added a reschedule-specific path in `_next_question` that skips already-collected identity slots and goes straight to confirmation.

8. **Multi-Slot Correction**: When the user says "Actually, make it Monday at 10am" during `CONFIRM_BOOKING`, the correction handler only updated the first matching slot (date) and missed the second (time). Fixed by running opportunistic extraction of all slots from the correction utterance and applying any found values.

---

## Session Summary

| Phase | Approx. Prompts / Iterations |
|---|---|
| Phase 1 – Design | ~3 (design + review + finalize) |
| Phase 2 – Backend Skeleton | ~4 (scaffold + WS server + test client + review) |
| Phase 3 – Unit Tests | ~3 (generate + fix slot edge cases + verify 115 pass) |
| Phase 4 – STT Integration | ~3 (integrate + PyAV fix + tests) |
| Phase 5 – TTS Integration | ~2 (integrate + download script + tests) |
| Phase 6 – Frontend UI | ~3 (scaffold + full UI pass + build verification) |
| Phase 7 – E2E Tests | ~5 (write scenarios + 8 FSM/intent bug fixes + 126 passing) |
| Phase 8 – Documentation | ~2 (README + AI_USAGE update) |
| **Total** | **~25 iterative prompts across one agentic session** |

### Human Intervention Points
- Confirming each phase before AI continued to the next
- Pointing out the backend error screenshot (`python-multipart` missing)
- Confirming frontend was visible before proceeding to E2E phase
- All bug fixes were AI-driven after test failures were observed

---

## AI-Generated vs Human-Written Code

| Category | Percentage |
|---|---|
| AI-generated code | ~97% |
| Human-written/corrected code | ~3% (env-specific config paths, pip install commands) |

# AI Usage Log

This document tracks all AI tool usage during the build. It is updated continuously, not written after the fact.

---

## Tools Used

| Tool | Purpose | Notes |
|---|---|---|
| Antigravity (Claude Sonnet 4.6 & Gemini Flash) | Code scaffolding, design review, debugging | Primary coding assistants |

---

## What the AI Got Right

- Designed the intent-first FSM architecture in [`docs/DESIGN.md`](file:///d:/SAVV%20Pro%20Solutions/Test%20Project/Voice%20Agent%20Task/savvpro-test-voice-agent/docs/DESIGN.md) isolating correction handlers from normal slot extraction.
- Modularized brain logic cleanly into pure functions across `intents.py`, `slots.py`, `availability.py`, `responses.py`, and `fsm.py`.
- Built the FastAPI WebSocket server, audio streaming endpoint, and interactive terminal testing client.
- Authored a comprehensive 118-test suite covering intents, slots, multi-slot utterances, mid-flow corrections, FSM lifecycle, and faster-whisper STT.

---

## What the AI Got Wrong / Required Correction

1. **Over-eager Doctor Extraction**: Bare surname aliases (e.g. "Smith") in `extract_doctor` caused names like "John Smith" to prematurely bind `doctor = "Dr. Smith"`. Fixed by requiring explicit prefixes ("Dr.", "Doctor") or contextual verbs ("prefer", "with") for doctor surnames.
2. **Regex Correction Patterns**: Expressions like `actually I'd prefer 3pm` and `Wednesday instead` failed to trigger `CHANGE_TIME` and `CHANGE_DATE` because boundaries (`\b`) didn't match immediately before digit-meridiem combos like `3pm`, and `instead` was only checked before rather than after the date/time term. Refined patterns to handle suffix modifiers and compact time representations.
3. **Leading Filler Stripping**: Name extraction missed `um John Smith` due to strict full-match word tokenization; updated `extract_name` to trim conversational hesitation markers (`um`, `uh`, `er`, `well`).
4. **Unclear Count Tracking**: During slot extraction failures in normal FSM advance, `unclear_count` was getting reset unconditionally, preventing the 3-strikes handover logic from triggering. Updated the state machine transition to preserve and increment unclear counts correctly.
5. **PyAV 15+ Compatibility in faster-whisper**: `faster-whisper`'s `decode_audio` invokes `av.open(..., metadata_errors="ignore")`. In modern `av` versions, the `metadata_errors` keyword argument was removed, triggering a `TypeError`. Implemented an in-memory monkeypatch adapter in `WhisperSTT._load_model` to transparently remove unsupported arguments without breaking wheel dependencies.

---

## Token / Session Usage

_(Add screenshots or summaries here as build progresses)_

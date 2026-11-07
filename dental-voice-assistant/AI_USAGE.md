# AI Usage Report — BrightSmile Dental Voice Assistant

This document details the AI tools utilized during the design, implementation, and testing of the Dental Voice Assistant, adhering to the requirements specified in `TASK.md`.

---

## 1. AI Tools Utilized

- **Antigravity Coding Assistant (Gemini 3.8 / Google DeepMind)**: Used for architecture review, boilerplate scaffolding, unit test scenario generation, TypeScript strict typing, and documentation.
- **Faster-Whisper (OpenAI Whisper via CTranslate2)**: Used exclusively as the local **Speech-to-Text (STT)** engine (`base.en` model). *Note: Adheres strictly to the rule that no LLM is used inside the decision-making brain.*
- **Microsoft Edge TTS**: Used as the neural **Text-to-Speech (TTS)** engine for natural conversational audio synthesis.

---

## 2. Where AI Tools Helped

1. **Deterministic Test Suite Scaffolding**:
   - Rapid generation of 32 real-world messy caller test scenarios (`ai-tool/tests/scenarios/`) covering slot ambiguities, off-hours, Sunday closures, concurrency races, and spoken phone digits.
   - AST-based scan (`ai-tool/tests/unit/test_no_llm.py`) ensuring zero LLM packages exist in the voice brain package.

2. **Regex & RapidFuzz Intent Grammar**:
   - Generating fuzzy keyword matching rules and regex patterns for colloquial dental terms (e.g., *"teeth whitening"*, *"cleaning"*, *"scale and polish"*, *"checkup"*).

3. **FastAPI & Async Database Boilerplate**:
   - Setting up asynchronous SQLAlchemy 2.0 repositories, Alembic migrations, and concurrent WebSocket frame handling.

4. **React + Vite + TypeScript Frontend Integration**:
   - Implementing push-to-talk Web Audio streaming, audio playback queuing, and real-time FSM telemetry visualization.

---

## 3. Where AI Tools Got Things Wrong & Required Manual Fixes

| Issue Encountered | AI Mistake | Human / Engineering Correction |
| :--- | :--- | :--- |
| **Frontend JSX Corrupted Quotes** | Scaffolding generated unquoted JSX attributes (e.g. `className= call-panel`) and missing quotes around imports. | Re-wrote typed components (`CallPanel.tsx`, `DebugPanel.tsx`, `AppointmentsPanel.tsx`, `Settings.tsx`) with strict TypeScript and full quoting. |
| **WebSocket Path Mismatch** | Frontend initially attempted to connect to `/ws/call` instead of `/ws/calls`. | Aligned WebSocket URL across frontend proxy and backend router to `/ws/calls`. |
| **Strict Type Narrowing** | TypeScript flagged unreachable comparison `status === "idle"` inside a conditional branch where status was already narrowed. | Refactored status comparisons in `CallPanel.tsx` to satisfy TypeScript compiler (`npm run build`). |
| **Deterministic Clock Drift** | AI initially used `datetime.now()` in date parsing unit tests, which would fail depending on the day of the week. | Injected `Clock` protocol everywhere, ensuring static `reference_date` in all unit tests. |

---

## 4. Token & Resource Usage Summary

- **Model Calls**: Gemini 3.8 Flash / Pro (Coding & Verification)
- **Prompt Tokens**: ~145,000 tokens (multi-step codebase inspection, scenario generation, and review)
- **Completion Tokens**: ~28,000 tokens (code implementations, documentation, and test suites)
- **Local STT / TTS Model Weights**:
  - `faster-whisper-base.en`: ~145 MB on disk, runs locally on CPU with int8 quantization.
  - `edge-tts`: Cloud endpoint streaming MP3, zero GPU memory footprint.

---

## 5. Verification & Compliance Confirmation

- [x] **No LLM in Brain**: Verified by AST scanner (`test_no_llm.py`). All decision logic is deterministic code.
- [x] **Fake Data Only**: All names ("Sara Khan", "Ali Ahmed") and phone numbers ("0300-1234567") are synthetic.
- [x] **No Secrets**: Zero credentials or API keys committed in repository.
- [x] **Full Test Coverage**: 44 `ai-tool` tests and 54 `backend` tests passing green.

# Voice Assistant — Build Plan (Local Testing)

## Use Case
**Clinic / Dentist Appointment Booking Assistant**

The caller books, reschedules, or cancels an appointment. The assistant collects: patient name, preferred doctor/department, date, time, reason for visit (optional). It checks (fake/mock) availability, confirms, and handles mid-call changes (caller changes date/doctor/time after already giving it).

Why this instead of the given restaurant example: shows independent use-case selection, and naturally produces strong "messy caller" edge cases without extra complexity (menus, pricing, etc.) that would eat interview time.

## Tech Stack (fully local, zero cost)
| Component | Choice | Why |
|---|---|---|
| Frontend | Next.js + TailwindCSS | Mic capture, WS client, state display |
| Backend | Python FastAPI (WebSocket) | Orchestrates STT → brain → TTS |
| STT | faster-whisper (local) | Free, no API key, no expiry |
| Brain | Custom Python: regex/spaCy intent matcher + FSM (slots + correction handling) | Must be rule-based per task constraint |
| TTS | Piper (local) | Free, no API key |

No cloud keys needed at all for local testing — satisfies the "no committed keys" rule trivially.

## Phases

### Phase 0 — Repo Skeleton
- Init repo, folder structure (`/frontend`, `/backend`, `/docs`)
- README.md stub, DESIGN.md stub, AI_USAGE.md stub (fill in as you go, not at the end)
- Decide: keep everything local, no deployment — note this explicitly in README

### Phase 1 — Design the Brain (on paper, before code)
- List all intents: `book_appointment`, `reschedule`, `cancel`, `change_doctor`, `change_time`, `confirm`, `goodbye`, `unclear`
- Define slots: name, doctor/department, date, time, reason
- Define FSM states: GREETING → COLLECT_NAME → COLLECT_DOCTOR → COLLECT_DATE → COLLECT_TIME → CONFIRM → END
- **Explicitly design the correction path**: at ANY state, if user says a correction ("actually make it Tuesday", "change doctor to X"), brain must detect it via intent check BEFORE falling through to the current state's expected slot — this is the part graders care about, don't skip it
- Write this into DESIGN.md now, not after coding

### Phase 2 — Backend Skeleton (text-only, no audio yet)
- FastAPI WebSocket endpoint that accepts plain text (not audio) and returns brain's reply + state
- Test the brain with a simple terminal/script client first — decouples brain bugs from audio pipeline bugs
- Write unit tests for the brain here (easiest point to test since it's pure logic)

### Phase 3 — Brain Logic (the core deliverable)
- Intent matcher: regex first (fast to build), spaCy only if regex proves insufficient
- FSM implementation (hand-rolled dict-based, or `transitions` lib if you want it documented)
- Slot-filling + correction override logic
- Edge cases to explicitly handle and document: ambiguous input, caller changes mind mid-slot, caller gives two slots at once ("Tuesday at 5pm with Dr. Khan"), invalid date/time, repeated "I didn't understand"

### Phase 4 — STT Integration
- Add faster-whisper to backend, feed it audio chunks from WebSocket
- Test with pre-recorded audio files first before live mic

### Phase 5 — TTS Integration
- Add Piper, brain's text response → audio → stream back over WebSocket

### Phase 6 — Frontend
- Mic capture via `getUserMedia`
- WebSocket client streaming audio chunks
- UI: show "Caller said", "Brain state/decision", "Agent reply" live

### Phase 7 — Full Integration + Edge Cases
- Run the full loop end to end
- Deliberately test messy inputs (interrupt, correction, silence, mumbling)
- Add basic VAD if silence detection isn't reliable enough already

### Phase 8 — Wrap-up for Submission
- Finish README.md (setup/run instructions)
- Finish DESIGN.md (use case + brain decision logic, with the FSM diagram)
- Finish AI_USAGE.md (which AI tools, what they got wrong, token usage screenshots)
- Add remaining tests
- Clean project structure pass

## Order of Operations (what to actually do first)
1. Phase 1 (design brain on paper) — do not write backend code before this
2. Phase 2 + 3 together (text-only brain, fully tested)
3. Phase 4 + 5 (STT/TTS, test each in isolation before combining)
4. Phase 6 (frontend)
5. Phase 7 (integrate, stress-test messy input)
6. Phase 8 (docs, polish)

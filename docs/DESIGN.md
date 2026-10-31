# Voice Agent — Design Document

> This document is filled in progressively as the build progresses. It is **not** written after the fact.

---

## Use Case

**Clinic / Dentist Appointment Booking Assistant**

A patient calls to book, reschedule, or cancel an appointment. The assistant collects all required information through natural conversation and handles mid-call corrections gracefully.

---

## Intents

_(Phase 1 — to be detailed)_

| Intent | Example utterances |
|---|---|
| `book_appointment` | "I'd like to book an appointment", "Can I schedule a visit?" |
| `reschedule` | "I need to reschedule", "Can I move my appointment?" |
| `cancel` | "Cancel my appointment", "I want to cancel" |
| `change_doctor` | "Actually, I'd prefer Dr. Khan", "Switch to a different doctor" |
| `change_time` | "Make it 3pm instead", "Change the time to morning" |
| `change_date` | "Actually Tuesday works better", "Let's do next Monday" |
| `confirm` | "Yes", "That's correct", "Sounds good" |
| `deny` | "No", "That's wrong", "Incorrect" |
| `goodbye` | "Thank you, bye", "That's all" |
| `unclear` | (catch-all for unrecognized input) |

---

## Slots

| Slot | Type | Example values |
|---|---|---|
| `name` | string | "John Smith" |
| `doctor` | string / enum | "Dr. Khan", "general", "dentist" |
| `date` | date | "Tuesday", "November 5th", "next week" |
| `time` | time | "3pm", "morning", "10:30" |
| `reason` | string (optional) | "toothache", "regular checkup" |

---

## FSM States

_(Phase 1 — to be detailed with transition diagram)_

```
GREETING → COLLECT_NAME → COLLECT_DOCTOR → COLLECT_DATE → COLLECT_TIME → CONFIRM → END
```

### Correction Path

**Critical design requirement**: At ANY state, before processing the expected slot for that state, the brain MUST first check for a correction intent. If a correction is detected, the relevant slot is updated and the FSM re-enters the confirm/re-ask loop for that slot.

---

## Brain Architecture

_(Phase 2/3 — to be filled in)_

---

## FSM Diagram

_(Phase 1 — to be added as Mermaid or ASCII diagram)_


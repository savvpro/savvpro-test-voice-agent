# Manual device demo

Use fictional names. Start both servers as documented. Automated tests **do not mark this checklist complete**.

## Voice in Chrome or Edge

- [ ] Open localhost, enable spoken replies and allow microphone permission.
- [ ] Tap the mic and say “Book a haircut tomorrow at 3 PM” (choose another day if Sunday). Verify the final transcript.
- [ ] Hear the reply; verify the microphone stays paused during speech and never transcribes the assistant.
- [ ] Tap the mic for each turn: “Actually make it 5 PM”, “Alex Example”, “Yes”. Hear the success reply and keep the reference.
- [ ] Mute/re-enable replies and stop audio mid-reply. Verify typing remains available.
- [ ] Deny microphone permission; verify a useful error and typed recovery.
- [ ] Remain silent or disconnect the mic; verify error/recovery behavior.

## Booking and recovery

- [ ] Inspect the actual rule, explanation, entities and state after each turn.
- [ ] Decline a proposal; verify no success/receipt appears.
- [ ] Book, then check availability at the same time and verify it is unavailable.
- [ ] Reschedule by reference, confirm, then cancel with another confirmation.
- [ ] Say “five thirty”; clarify with “five thirty PM”.
- [ ] Ask a business question mid-booking and continue without losing details.
- [ ] Try Sunday, past dates, overlaps and a service finishing after 7 PM.
- [ ] Try unknown input, repeat, restart and goodbye.
- [ ] Restart the backend and retrieve the saved booking by reference.
- [ ] Verify conversation, confirmation, errors and Inspector on a narrow viewport.

## Submission evidence

- [ ] Run Pytest, frontend typecheck/build and browser tests.
- [x] Add authentic Codex token counts and logs/screenshots to `AI_USAGE.md` (2026-10-26, 17:36:04 PKT; filtered session counters and original screenshot).
- [ ] Verify candidate branch, unchanged `TASK.md`, and no committed secrets/real data.
- [ ] Push/open the assessment PR only after explicit authorization.

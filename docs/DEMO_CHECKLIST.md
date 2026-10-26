# Manual device demo

Use fictional names. Start both servers as documented. Automated tests **do not mark this checklist complete**.

## Voice in Chrome or Edge

- [ ] Open localhost, enable spoken replies and allow microphone permission.
- [ ] Tap the mic and say “Book a haircut tomorrow at 3 PM” (choose another day if Sunday). Verify the final transcript.
- [ ] Hear the reply; verify the microphone stays paused during speech and never transcribes the assistant.
- [ ] Tap the mic for each turn: “Actually make it 5 PM”, “Alex Example”, “Yes”. Hear the success reply and keep the reference.
- [ ] Mute/re-enable replies and stop audio mid-reply. Verify typing remains available.
- [ ] Use **Listen again** and verify the current reply is audible. Try the English language choices and record which the device supports.
- [ ] Deny microphone permission; verify a useful error and typed recovery.
- [ ] Remain silent or disconnect the mic; verify error/recovery behavior.

## Booking and recovery

- [ ] Inspect the actual rule, explanation, entities and state after each turn.
- [ ] Decline a proposal; verify no success/receipt appears.
- [ ] After booking, propose a reschedule and say “cancel that change”. Verify the saved appointment is unchanged and the proposal disappears.
- [ ] During rescheduling, say “cancel it”; verify the assistant asks which target, and “yes” alone cannot cancel the saved appointment.
- [ ] Start another booking and discard it; verify the older saved booking remains unchanged.
- [ ] Book, then check availability at the same time and verify it is unavailable.
- [ ] Reschedule by reference, confirm, then cancel with another confirmation.
- [ ] Say “change the timing for this appointment”, supply a new time, then “never mind, don't do it, revert the change”. Verify the saved booking stays unchanged.
- [ ] Say “thank you” mid-task and continue; say “nothing, thank you so much” to end.
- [ ] Expand/collapse navigation and switch between chat and Appointment, preserving unsent input; use the labeled Decision inspector button to open/close the Inspector, and check both themes.
- [ ] In a new session, check both centered suggestions above the input. Send a message, reload and verify they remain hidden; New session restores them.
- [ ] Say “five thirty”; clarify with “five thirty PM”.
- [ ] Ask a business question mid-booking and continue without losing details.
- [ ] Try Sunday, past dates, overlaps and a service finishing after 7 PM.
- [ ] Try unknown input, repeat, restart and goodbye.
- [ ] Restart the backend and retrieve the saved booking by reference.
- [ ] Verify conversation, confirmation, errors and Inspector on a narrow viewport.
- [ ] Complete a keyboard-only turn and choose an available start with Enter; verify focus and a separate final confirmation.
- [ ] Run the held-out protocol in [CONVERSATION_TEST_MATRIX.md](CONVERSATION_TEST_MATRIX.md), recording unexpected behavior without silently repairing the transcript first.

## Device verification record

Not executed by the coding agent. Fill this in after using a physical microphone and speakers; keep the relevant boxes above unchecked until verified.

| Field | Actual observation |
| --- | --- |
| Date/time and tester | Pending |
| OS, browser/version, microphone/speakers | Pending |
| Selected speech language | Pending |
| Recognition transcript vs spoken words | Pending |
| Audible reply, replay and turn separation | Pending |
| Permission denial/silent microphone recovery | Pending |
| Held-out conversations and failures | Pending |

## Submission evidence

- [x] Run Pytest (**398 passed**), frontend typecheck/format/production build and browser tests (**24 passed**), locally on Python 3.13/Node 22. The latest UI-only follow-up reran frontend checks; the unchanged backend result is from the preceding full run.
- [x] Configure CI for Python 3.11/3.13, frontend checks and isolated browser tests; check YAML and pinned actions locally.
- [ ] Observe a successful remote CI run after publication is authorized.
- [x] Add authentic Codex token counts and logs/screenshots to `AI_USAGE.md` (2026-10-26, 17:36:04 PKT; filtered session counters and original screenshot).
- [x] Verify `candidate-TUAHASHAIKH` and unchanged `TASK.md`; limited credential-pattern scan found no matches in the checked text files. This is not a security audit. The demo is intended for fictional data only.
- [ ] Push/open the assessment PR only after explicit authorization.

**Submission is on hold at the candidate's explicit request.** Automated checks do not complete the physical device or independent conversation checks.

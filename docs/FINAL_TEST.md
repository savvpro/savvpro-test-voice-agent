# Final acceptance test

Run `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1` from the repository root. This scans deliverable text for common credential patterns, checks formatting/lint, runs backend tests, builds React, and runs isolated browser tests. The scanner is a heuristic, not a guarantee that any possible secret can be recognized.

Then start the app using README.md and open http://127.0.0.1:5173 in Chrome or Edge. All contact information below is fictional. Use a future date and Asia/Karachi times.

## Physical microphone and speaker (manual sign-off)

1. Ensure your OS has an input and output audio device, and site volume is enabled.
2. Click **Replay assistant reply**. Confirm you hear the displayed greeting. If muted, enable the assistant voice first.
3. Click the microphone, allow permission, and say **“hi-tea tomorrow at six PM”**. Confirm the transcript matches your speech and the summary shows hi-tea and 18:00. Confirm you hear the next question.
4. Say **“two adults”**, then **“children aged three and seven”**, tapping the mic for each turn. Confirm children are counted separately.
5. Ask **“What is the price?”**. Confirm the answer speaks and the booking details are preserved.
6. Say **“indoor”**, **“name is Demo Guest”**, and **“03000000000”**. For numbers, if recognition is inaccurate, use typed input and verify the readback. Do not enter a real phone number.
7. Confirm total PKR 5,000 and deposit PKR 1,250. Say **“yes”**. The reservation must be payment pending, not confirmed.
8. Say **“I paid”**. It must remain pending. Click **Simulate deposit**; it must become confirmed with a reference.
9. Record browser/version, microphone, output device and pass/fail below. Automated synthetic speech tests do not replace these steps.

## Booking cases

| Case | Action | Expected |
| --- | --- | --- |
| À la carte | New call; book tomorrow at 8 PM, 4 adults, no children, indoor, Demo Guest, 03000000000; yes | Confirmed immediately; no buffet total/deposit |
| Buffet slot | Request hi-tea at 7 PM | Offer valid 4 PM/6 PM sittings |
| Buffet weekday | Request dinner buffet on a Monday | Ask for Friday–Sunday |
| Correction | After a complete summary, say “six adults” | New summary/price; explicit yes required again |
| Unclear correction | After review, say “two children”, then “yes” | Ask ages; do not confirm the old party |
| Unavailable table | Make a 12-person indoor booking; try another overlapping indoor booking | Real alternatives shown; selected alternative goes through review |
| Amendment | Change a confirmed booking to an available time; confirm | Replacement active; old booking replaced |
| Failed amendment | Attempt a full seating area | Original booking remains active |
| Cancellation | Say cancel, then maybe, then no | Wait for explicit answer, then keep booking |
| Final cancellation | Say cancel, then yes | Cancelled; inventory released |
| Lookup | New call; Manage an existing booking; enter active reference and matching fake phone | Resume booking; wrong phone rejected |
| Hold expiry | Leave a pending buffet booking unpaid for 10 minutes, then try to pay | Rejected; no expired booking confirmed |
| Staff request | Say “nut allergy” or “birthday decoration” | Local staff request recorded; no safety guarantee or promised external contact |

## Audio/error recovery

- Deny microphone permission: clear explanation appears and typing still works.
- Allow permission but remain silent: browser no-speech error offers retry/typing.
- Stop listening with the microphone button: listening indicator stops.
- Mute: no spoken response; transcript still updates.
- Replay: most recent assistant reply is spoken without changing booking state.
- Select Urdu recognition and try a supported short phrase; note transcription accuracy separately. Replies remain English. Do not expect unrestricted Urdu conversation.
- Disconnect the backend and send text: recoverable error appears, text remains available for retry. Restart backend and retry; the same request ID prevents duplicate booking.
- At 390px mobile width, verify controls are reachable and there is no horizontal scrolling.

## Acceptance record

Automated preflight completed on 2026-10-27 (Asia/Karachi): 28 backend tests and 4 browser tests passed; Python lint/formatting, frontend formatting, production build and the source/evidence secret scan passed. Browser coverage includes the real API booking/payment/amendment/cancellation flow, mobile overflow, synthetic recognition-to-response speech wiring and denied microphone recovery. One third-party Starlette/httpx deprecation warning remains; it does not fail the tests.

Automated verification is run by the implementation agent; final physical audio sign-off is deliberately left for the tester with actual audio devices.

| Item | Result |
| --- | --- |
| Test date/time (Asia/Karachi) | Pending final tester |
| Browser/version | Pending final tester |
| Microphone/output device | Pending final tester |
| Actual recognition and playback | Pending final tester |
| English booking completed by voice | Pending final tester |
| Urdu recognition limitations observed | Pending final tester |

PR creation is left to the repository owner. Do not commit `.env`, `.venv`, databases or `node_modules`.

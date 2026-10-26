# Reviewer walkthrough

The [silent browser recording](images/demo-walkthrough.webm) runs against the actual Python backend and database. It demonstrates full-slot alternatives, confirmation, multiple-appointment selection, rescheduling, cancellation, isolated reset, and the dedicated desktop/mobile appointments navigation. The silent recording is accelerated 2x for review. It is a UI walkthrough, not evidence of live microphone accuracy.

For a spoken demonstration in desktop Chrome:

1. Start a call and allow microphone access.
2. Say "Reschedule my appointment"; the existing tyre rotation is read back.
3. Say "Thursday at 3 PM", check the proposal, then say "Yes".
4. Say "Book a brake inspection for my SUV tomorrow at 2 PM". The occupied fixture causes alternatives to be offered (choose another opening date if tomorrow is Sunday).
5. Say "First one", then "Actually make that Thursday at 11 AM". The new proposal requires fresh confirmation.
6. Say "Yes". Two appointments now exist.
7. Say "Cancel my appointment"; select the tyre rotation when asked, then confirm cancellation.
8. Ask "What time do you close?" and inspect the real decision trace.
9. End the call. Reset the demo to restore its initial state.

Check recognition text, audible replies, automatic listening after each reply, pause/resume, and interrupt controls. If browser recognition fails, configure a Groq key and select Server speech; never classify typed input alone as voice verification.

For mouse/touch review, open **Your appointments**, select **Reschedule** or **Cancel appointment** on a booking, and complete its confirmation at reception. Use **Type instead** next to Start a call for a microphone-free path.

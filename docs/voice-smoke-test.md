# Voice smoke test

Run in Chrome or Edge with the API and UI started.

- [ ] Click **Push to talk** and allow microphone access.
- [ ] Speak a name; confirm listening ends before the HTTP request and decision render.
- [ ] Confirm **Push to talk** is disabled while the assistant is speaking.
- [ ] Click Talk after a reply; confirm previous TTS stops before the microphone opens.
- [ ] Leave the microphone silent; confirm it stops by the hard timeout and state does not advance.
- [ ] Deny microphone permission; confirm the error is visible and text input still completes a booking.
- [ ] Capture a screenshot of the transcript and decision panel for submission evidence.


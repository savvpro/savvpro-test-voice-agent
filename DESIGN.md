# PawPal design

## Use case

PawPal is a text-first pet-grooming appointment assistant. A pet owner can book a grooming service, correct details while booking, request a new day/time for an existing appointment, or cancel after confirming. The demo uses fake availability and in-memory sessions only.

## Decision-making

The backend is the only decision-maker. `backend/app/main.py` uses explicit keyword/regular-expression parsing and a small state machine; no generative model is called. On a booking, it extracts recognized service, pet name, weekday, time, and owner name, then asks for the first missing detail in a fixed order. Broad requests such as “spa for my pet Tyler” start a booking, preserve the pet's name, and prompt for one of the supported services instead of silently mapping an ambiguous term. When asking for a name, it accepts a short answer such as “Coco” or “Maya” using the current missing-field context, as well as phrases such as “It's Coco” and “This is Maya.” It checks the requested weekday/time against a fixed fake availability list and suggests the available demo slots when a requested time is unavailable. Before finalizing a new booking or reschedule, the assistant reads back the details and requires an affirmative confirmation. Callers can correct a field during readback, which triggers a fresh confirmation; declining does not create a booking or change the existing appointment. A caller can also update an existing booking detail, such as the pet's name, with a separate confirmation; declining restores the saved detail. Cancellation requires confirmation, and farewells leave the booking intact while closing politely.

The API returns the recognized intent, next step, status, collected details, and sample openings so the frontend can show what the code decided. The frontend lists all sample openings by weekday and labels them as demo-only. These openings are static examples, not a real calendar; accepting a booking does not reserve or remove a slot. Session and booking state live in the backend process's in-memory `sessions` dictionary. There is no persistent database, and restarting the backend clears that state.

## Voice interaction

The browser frontend uses the Web Speech API: speech recognition converts a spoken utterance into text, which is sent through the same Python decision logic as typed messages; speech synthesis reads the backend's reply aloud. Spoken replies can be toggled, and typed chat remains available if browser speech features or microphone permission are unavailable. Browser recognition support varies and may require HTTPS or localhost and microphone permission. Speech services do not determine intent or booking actions.

## Known limits and next improvements

- Understanding is intentionally deterministic and limited to the stated service names, weekdays, and 12-hour AM/PM times.
- Availability is sample data, not a real calendar or reservation system.
- Sessions are in-memory and intended for a local single-process demo.
- Browser speech recognition availability and accuracy depend on the user's browser and configured speech service; text entry is the reliable fallback.
- A production version would use a persistent booking store, real availability integration, timezone-aware dates, stronger input parsing, and privacy/retention controls.

# Design

## Use case

A phone assistant for a dental clinic ("Bright Smile Dental") that can **book**, **reschedule** and
**cancel** appointments, and answer opening-hours questions. It finishes the whole job: it collects the
details, checks the calendar, confirms with the caller, writes the booking, and says goodbye.

Clinic rules (fake data): Monday to Friday 9-12 and 1-5, Saturday 9-12, closed Sunday. Appointments
are one hour and start on the hour. A fixed pattern marks some hours as already taken so the demo
has realistic gaps.

## Architecture

- **Browser:** speech to text and text to speech (Web Speech API), React page, reasoning panel.
- **FastAPI:** receives only text. One session object per call, kept in memory.
- **Brain** (`nlu.py` + `brain.py` + `scheduler.py`): everything that decides.

## How the brain decides

Each turn runs the same pipeline:

1. **Normalise** the text (lower case, punctuation, "a.m." -> "am").
2. **Extract entities** with rules: service, day, time, part of day, name, emergency words.
   "tomorrow", "next Tuesday", "October 30th", "3 pm", "half past three", "at ten" and so on.
3. **Detect intent** with ordered regexes: cancel, reschedule, book, hours, human, repeat, goodbye.
4. **Safety rules first:** emergency words end the call with a transfer to the on-call dentist;
   "talk to a person" hands off; "repeat" replays the last reply.
5. **Route by dialogue state:** `start/collecting -> offering -> confirming -> done -> ended`.
6. **Slot filling:** a new value always overwrites the old one, in any state. This is why the caller
   can change their mind at any point. The next question is the first missing slot.
7. **Validate with the calendar** before moving on (closed day, past date, outside hours, not on the
   hour, already taken). A failed check produces concrete alternatives instead of a dead end.
8. **Confirm** the full summary, then execute only on "yes".
9. Every turn returns a **reasoning trace** (what was heard, what was understood, which rule fired).

## Messy cases the assistant handles

| Situation | Behaviour |
|---|---|
| Caller changes time/day/service at the confirmation step | Re-validates and asks to confirm again |
| Says "no" at confirmation | Asks what to change; "change the time" asks only for the time |
| Sunday, a past date, a date over 60 days away | Explains why and asks for another day |
| 8 PM, lunch hour, or Saturday afternoon | States opening hours and offers nearest free slots |
| 3:30 PM | Explains booking is on the hour and offers hours |
| Requested slot already taken | Offers up to three alternatives; "the second one", "any" and "3 PM" all work |
| Nothing free that day | Offers the next day with openings |
| "Afternoon" with no exact time | Lists free afternoon slots |
| Slot taken between offer and confirm | Re-checks at booking time and offers alternatives |
| Hours question in the middle of a booking | Answers, then repeats the pending question |
| Name not found when cancelling or moving | Asks again, hands off after 3 misses |
| Several appointments under one name | Asks which day |
| Not understood | Repeats the pending question; hands off after 3 misses in a row |
| Empty input, greeting only | No failure counted for a greeting |
| Emergency words (swelling, bleeding) | Immediate transfer to the on-call dentist |
| Second request after a booking | Starts a fresh flow, remembers the caller's name |
| "This is urgent", "I'm looking for..." | Not mistaken for a person's name |

## Why rules instead of a model

Rules are predictable and testable: the same sentence always gives the same decision and every
decision has a visible reason. The cost is coverage: phrasing outside the patterns is not understood
and falls back to a re-prompt, then a human hand-off.

## Limits and next steps

- English only; spoken numbers beyond twelve and dates like "the twenty-eighth" are not parsed.
- In-memory state: swap `Schedule` and the session dict for a database and Redis for production.
- Natural next steps: rate limiting, structured logging, a persistent store, a phone (SIP) gateway.

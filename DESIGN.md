# Design

## The use case

**A phone receptionist for a dental clinic.** A front desk spends much of the day on three calls: *book me in*,
*move my appointment* and *cancel it*. Each has a clear end (a booking in the calendar, or a booking moved or
removed), each needs facts checked against real constraints (opening hours, lunch, free slots, dates in the past),
and callers are messy in predictable ways. That makes it a real job from start to end rather than a chat.

The clinic, "Brightside Dental", is fictional. Hours: Monday to Friday 9 to 5 with lunch 12 to 1, Saturday 9 to 1,
closed Sunday. Visits are 30 minutes. Some slots are already taken by a fixed pattern of fake patients, and one
named demo booking (Jordan Lee) exists so moving and cancelling can be tried.

## The pipeline

```
 browser                                   backend (Python)                                     browser
┌──────────────┐  text  ┌────────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────────┐  reply ┌──────────────┐
│ mic → Web    │───────▶│ normalize  │─▶│ understand │─▶│ merge into   │─▶│ decide ONE    │───────▶│ speechSynth  │
│ Speech API   │        │ (clean up) │  │ intent +   │  │ call state   │  │ next action   │        │ → speaker    │
└──────────────┘        └────────────┘  │ details    │  └──────────────┘  └───────────────┘        └──────────────┘
                                        └────────────┘         ▲                  │
                                                               └── calendar ◀─────┘
```

Speech to text and text to speech run in the browser (Web Speech API), so there are no keys and no audio leaves the
machine except to the browser's own recognizer. The backend only ever sees text, which keeps the brain testable
without audio. The browser falls back to typing when it has no speech recognition.

## How the brain decides

The brain is `backend/app/dialog/manager.py`. Every turn runs the same four stages and returns a `Decision` with
the heard text, cleaned text, intent and score, extracted details, the **reasons** (one line per choice made) and the
action. The call screen shows all of it.

### 1. Clean up what was heard — `nlu/normalize.py`

Speech recognizers return things like "three thirty p m" or "five five five one two…". Normalization lowercases,
removes fillers (um, uh), turns "p.m." into "pm", spelled-out numbers into digits ("twenty first" → "21st",
"three thirty" → "3:30"), and digit sequences into a form the parsers can read.

### 2. Understand — `nlu/intents.py`, `nlu/when.py`

- **Intent**: each intent has weighted regular-expression patterns (e.g. `reschedule … appointment` = 0.95,
  `appointment` alone = 0.6 for *book*). The highest-scoring match wins and its score is shown as the confidence.
  Intents: book, reschedule, cancel, emergency, hours, location, insurance, repeat, restart, human, goodbye,
  affirm, deny.
- **Details**: date ("tomorrow", "next Tuesday", "November 4", "the 3rd", "11/04"), time ("3:30 pm", "half past
  two", "noon", "at 3"), part of day ("afternoon"), visit type, name ("my name is…", or a bare name when we just
  asked for one), phone (any run of 7 to 15 digits in any grouping, such as "135 567454 2132" or "+44 20 7946 0000"), a choice ("the second one") and whether the
  caller is correcting themselves ("actually", "no wait", "instead", "make it").

### 3. Update what we know

The call state holds the job (book / reschedule / cancel), visit type, day, time, name, phone, the booking found,
any offered slots, and **what the last question asked for**. New details fill empty fields. A detail that would
overwrite an existing one is accepted only when the caller signals a correction or it answers the question just
asked; otherwise it is ignored *and the reason says so*. That one rule handles "actually, make it 2 PM" without
letting a stray "first" overwrite the day.

### 4. Pick one action — a fixed order of checks

1. **Anywhere in the call:** repeat → replay the last reply; start over → clear everything; a person → transfer;
   hours/address/insurance → answer, **then repeat the open question** (nothing collected is lost); goodbye → end.
2. **What is this call about:** set or switch the job. Emergency words jump straight to the earliest free slots,
   with a 911 note for severe symptoms. A date or time with no job is taken as a booking.
3. **Pending yes/no or choice:**
   - at the read-back, "yes" executes; "no" with a new detail applies it and reads back again; a bare "no" asks what
     to change;
   - with two slots on offer, "the first", "the later one", "yes" (if only one), or naming the time picks one; "no"
     asks for another time.
4. **Next missing or invalid detail** for the job, checked against the calendar:
   - move/cancel: find the booking by **name or phone** (a country code on one side still matches), read it back;
   - day: not in the past, not over 90 days out, not a closed day, not fully booked;
   - time: "at 3" with no AM/PM means **3 PM** (hours 1–7 are afternoon at a clinic), not already passed, inside
     opening hours, not taken. A problem time gets **the two nearest free slots** instead of a dead end;
   - name for new bookings, then a phone number, which is **optional**: "skip", "no" or "rather not" moves on;
   - then the **read-back**. Nothing is written until the caller hears it and says yes, and the slot is checked
     again at that moment in case another caller took it.

If a turn changes nothing (no new detail, no recognised answer), it counts as a miss and the question is asked
again. **Three misses in a row transfer the call to the front desk**, as a real receptionist line would.

### Why rules and not a model

The task's rule, but also the right call for this job: the set of things a caller can want here is small and known,
the cost of a wrong booking is high, and every decision has to be explainable and repeatable. Same words in, same
reply out, so each messy case is a unit test.

## Messy calls handled (each has a test in `backend/tests/test_dialog.py`)

| Situation | What happens |
|---|---|
| Changes the time halfway ("actually, make it 2 PM") | Time replaced; reason logs "changed time: 10 AM → 2 PM" |
| Corrects at the read-back ("no wait, make it Friday") | Day replaced, read back again |
| Bare "no" at the read-back | Asks what to change |
| Says everything in one sentence | All fields filled; goes straight to the read-back |
| Asks a question mid-booking | Answers it, then repeats the open question |
| Slot taken / outside hours / Sunday / lunch | Says why and offers the two nearest free slots |
| Picks an offer by "the second one" or by naming the time | That slot is used |
| "At 3" (no AM/PM) | Read as 3 PM, with the reason shown |
| "Tomorrow afternoon" (no time) | Offers free afternoon slots |
| Date already past this year, or too far ahead | Rejected with a reason |
| Time earlier today | Rejected |
| Slot taken by someone else before "yes" | Caught at confirmation; alternatives offered |
| Phone number in any format | Accepted; only the last four digits are read back |
| Doesn't want to give a phone number | Skipped; the booking is made without one |
| Name or number not on file (move/cancel) | Asks again; counts as a miss |
| Switches job ("actually I want to cancel") | Job switched |
| Pain or swelling | Earliest visit offered, with a safety note |
| Silence, or noise like "the first" when asked for a name | Not taken as an answer; asked again |
| Three unusable turns, or "a real person" | Transferred to the front desk |
| Talks after the call ended | Told the call has ended |

## Production notes

- **Structure:** parsing, calendar, dialog and HTTP are separate modules; the app is built by a factory
  (`create_app`) so tests inject a fixed clock and a fresh store.
- **Validation:** request text capped at 500 characters; unknown calls return 404; CORS limited to configured origins.
- **Privacy:** fake data only; a phone number is optional, never read back in full, and masked to its last four
  digits in the schedule API and on screen. Bookings can be found by name instead of number.
- **Concurrency:** one lock around the shared calendar so two calls cannot book the same slot.
- **Next steps for a live clinic:** a real database and practice-management integration in place of the in-memory
  calendar; a telephony provider (e.g. SIP/WebRTC) feeding a server-side recognizer; SMS confirmations; per-clinic
  configuration of hours and services; call recordings and metrics on transfers and misses.

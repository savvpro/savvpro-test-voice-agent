# Design

## Use case

A receptionist line for a small fictional clinic (Maple Street Clinic, US locale, 911 for emergencies): **book, reschedule and cancel** appointments. Four fake doctors (two GPs, dermatology, pediatrics), Mon-Fri 09:00-17:00, 30-minute slots. The brain is our own deterministic code; no LLM is in the decision path.

## Pipeline

```
text -> nlu.parse -> Parsed(intent, entities) -> dialogue.handle_turn(state, ...) -> (new state, action) -> responses.render -> reply
```

- **NLU** (`nlu.py`, `parsing.py`): keyword/regex rules, stdlib date/time parsing, `difflib` fuzzy doctor match.
  - Intent priority: emergency > goodbye > repeat > help > cancel / reschedule / book > affirm / deny > unknown.
  - Entities: name, DOB, doctor, specialty (synonyms like "skin" -> dermatology), date, time (also "half past three", "noon", morning/afternoon/evening), booking ref `CLN-XXXX`.
  - **DOB vs date:** a past year, or a date while the brain is asking for the DOB, is a DOB; otherwise a date is an appointment date. Ordinal words ("the second one") are choices, not dates.
  - A bare answer is a name only when the name is being asked for; "I'm X" is a name only in that case too.
- **Dialogue** (`dialogue.py`): explicit state in `CallState` (JSON, persisted in SQLite per call). Any entity in any utterance fills its slot, so one sentence can fill four slots; the first missing slot decides the next question. Booking needs name, DOB, doctor or specialty, date, time.
- **Responses** (`responses.py`): templates, with the last reply stored for "repeat".

## State machine

```mermaid
stateDiagram-v2
    [*] --> greeting
    greeting --> collecting: book intent or booking details
    greeting --> lookup: reschedule / cancel intent
    collecting --> offering: slot taken, part of day, or day/time not possible
    collecting --> confirming: all slots filled and slot free
    collecting --> lookup: reschedule given a new reference
    lookup --> choosing: several matches
    lookup --> collecting: one match (reschedule)
    lookup --> confirming: one match (cancel)
    lookup --> done: not found twice, offer to book
    choosing --> collecting: caller picks one (reschedule)
    choosing --> confirming: caller picks one (cancel)
    offering --> confirming: caller picks an offer
    offering --> collecting: new day or time, or "no"
    confirming --> collecting: no / correction (book, reschedule)
    confirming --> offering: slot taken at commit
    confirming --> done: clean yes (book / reschedule / cancel executes)
    confirming --> done: no at cancel read-back (kept)
    done --> collecting: yes to the booking offer, or a new booking
    done --> lookup: new reschedule / cancel
    done --> [*]: no / goodbye
    greeting --> [*]: goodbye / emergency / 3 failures
    collecting --> [*]: goodbye / emergency / 3 failures
```

Actions shown in the Brain panel include `ask_*`, `confirm_booking`, `confirm_reschedule`, `confirm_cancel`, `offer_slots`, `choose_appointment`, `booked`, `rescheduled`, `cancelled`, `explain_slot_problem`, `unknown_doctor`, `not_found`, `reprompt`, `repeat`, `help`, `emergency`, `goodbye`, `give_up`.

## Confirm safety

Nothing is written without a read-back and a **clean yes**. At a read-back the turn is checked in this order:

1. **A detail that contradicts the read-back** (time, day, part of day, doctor, specialty, name, DOB; for a cancel only reference, name and DOB) is merged and the slot is re-checked, so the caller hears a fresh read-back, or offers if the new slot is not free. Details that agree are not corrections: "yes, morning is great" for 11:00, "it's a checkup" for a GP. Parts of the day: morning is before 12:00, afternoon from 12:00, evening from 16:00 (the clinic closes at 17:00, so evening offers are the openings nearest 4 PM). "Yes, in the evening" on an 11 AM or 2 PM read-back is a correction and does not book.
2. **A no** ("no", "nope", "nah", "not quite", "that's wrong", or a flow word with a negation like "no please don't book it"): a booking asks "What would you like to change: the doctor, the day, or the time?", a reschedule asks "What day and time would suit you instead?", and a cancel keeps the appointment ("I'll leave that appointment as it is").
3. **A hedged yes**: a yes alongside a correction word ("but", "instead", "rather", "change", "make it", "wait", "hold on", or "actually" straight after the yes, as in "yes, actually") with no detail we could parse. A booking or reschedule asks the same what-to-change question as a no. A cancel never executes: the caller hears a reprompt ("Sorry, I didn't catch that.") and the cancel read-back again (this counts towards the three-strikes give-up). "Yes, that's actually perfect" is not hedged and books.
4. **A clean yes** executes. A yes is "yes", "yeah", "yep", "yup", "correct", "that's right", "sure", "sounds good", "please do", "ok" or "okay", with no "no", "not", "don't" or "never" anywhere. A flow word confirms only with a plain yes ("yes, book it").
5. Anything else reprompts with the read-back.

## Messy callers

| Case | Handling | Test |
|---|---|---|
| Several details in one sentence | All slots filled at once | `test_happy_booking_one_sentence`, `test_multi_entity` |
| Changes a detail midway | New value overwrites, slot re-checked, read-back repeats | `test_change_time_midway`, `test_no_with_correction_rereads` |
| "No" at read-back | Asks what to change | `test_deny_at_readback` |
| "Yes, but make it 3:30" | Never executes; re-reads | `test_yes_with_correction_rereads` |
| "Yes actually" / "yes, wait" / "hold on" | Never executes; asks what to change | `test_yes_actually_wait_hold_on_do_not_book` |
| "Yes but keep it" at a cancel read-back | Never cancels; re-asks | `test_hedged_yes_at_cancel_never_cancels` |
| "Yes, in the evening" on an earlier read-back | A correction: offers slots nearest 4 PM | `test_evening_conflicts_with_earlier_readback` |
| "No please don't book it" | Never executes | `test_negated_please_never_books_or_cancels` |
| Slot already taken | Offers 3 nearest free slots, same doctor first | `test_slot_taken_offers_alternatives` |
| Picks an offer | By number or ordinal | `test_choice_by_number` |
| New day while offered slots | Re-searches that day | `test_new_day_while_offering` |
| Weekend or outside hours | Explains and re-asks | `test_weekend_and_closed` |
| Unknown doctor | Lists the available doctors | `test_unknown_doctor` |
| Unintelligible or silent | Reprompt; give up politely after 3 | `test_reprompt_then_give_up`, `test_no_progress_turns_give_up` |
| "Repeat that" | Replays the last reply | `test_repeat` |
| Asks for help | Explains and re-asks the current question | `test_help_reasks` |
| Switches intent (book to cancel) | Flow changes, slots kept where relevant | `test_switch_book_to_cancel`, `test_switch_cancel_to_reschedule_keeps_ref` |
| Booking not found | One retry, then offers to book | `test_not_found_then_offer_book` |
| Several bookings match | Lists up to 3, asks which | `test_cancel_multiple_matches` |
| Emergency phrase | "Call 911", call ends | `test_emergency`, `test_bleeding_is_emergency` |
| "I am bleeding heavily" at the name prompt | Still an emergency, not a name | `test_i_am_not_a_name` |
| Filler ("um", "uh") | Not taken as a name | `test_filler_is_not_a_name`, `test_fillers` |
| Spoken numbers and times ("3 30 pm") | Parsed correctly | `test_spaced_and_spoken_times` |
| Spoken DOB | Parsed | `test_spoken_dob` |
| Double-booking race | DB unique index, offers alternatives | `test_double_booking_raises` |
| Expired or unknown call | 404 | `test_expired_call_404`, `test_unknown_call_404` |

## Data model and double-booking guarantee

SQLite, two tables: `appointments(ref, patient_name, dob, doctor_id, start, status)` and `calls(id, state, updated_at)`. A partial unique index `one_booking_per_slot` on `(doctor_id, start) WHERE status='booked'` makes a double-booking impossible even under races; the insert fails and the brain offers alternatives. Cancelling frees the slot; rescheduling keeps the reference. A process-wide lock serialises turns.

## Why no LLM

The brief forbids it, and for a booking line determinism is a feature: the same words always give the same decision, every rule has a test, there is no per-call cost or latency, and no hallucinated bookings. The cost is brittleness on unusual phrasing, handled by the reprompt/give-up path.

## Known limitations

- NLU is English-only and rule-based; unusual phrasing falls through to a reprompt.
- "I'm X" counts as a name only when the name is being asked for.
- Phone numbers, reminders and auth are out of scope; one clinic only.
- No caller verification beyond the booking reference: anyone who knows a reference (or a name and DOB) can reschedule or cancel that appointment.
- "Cancel" at a booking read-back switches to the cancel flow; "never mind" is not understood and just reprompts.
- A single-process lock around turns; SQLite is the shared store. Use per-call locks or Postgres for real throughput.
- Browser speech quality varies; voice needs Chrome or Edge.
- Known minor gaps: "not ok" can read as yes in isolation, "five past three" is unsupported, and a failure to save call state after a committed booking is only commented, not retried.

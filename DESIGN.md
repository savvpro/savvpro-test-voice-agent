# Design

**Use case:** a clinic front desk. Callers book, reschedule or cancel appointments.
Fake schedule: Mon-Fri, 9:00-17:00, 30-minute slots. Seed data is fake ("Sam Demo", "Jo Demo").

## Pipeline
Browser speech-to-text -> `POST /turn` -> **brain** -> reply text -> browser text-to-speech.
STT/TTS are the browser's Web Speech API. The brain lives in `backend/app`.

## How the brain decides
1. **NLU (`nlu.py`)**: ordered regex rules give an intent (book, cancel, reschedule, yes, no, repeat,
   human, goodbye, greeting). Separate parsers extract date, time and name.
2. **Slot filling (`brain.py`)**: one utterance may fill several slots. New values overwrite old
   ones, which is how corrections ("no, make it Thursday") work.
3. **State machine**: LISTEN -> ASK_NAME -> ASK_DATE -> ASK_TIME -> CONFIRM -> ENDED. The brain asks
   only for the first missing slot, then validates against the schedule before confirming.
4. **Trace**: every turn returns the reasons for its decision, shown in the UI.

## Messy cases handled
| Case | Behaviour |
|---|---|
| Caller changes date/time at any point | Overwrites the slot and re-validates |
| "No, ..." with a new value at confirmation | Treated as a correction, not a refusal |
| Plain "no" at confirmation | Asks for a new day and time |
| Ambiguous hour ("at 6") | Asks morning or evening; "evening" resolves it |
| Slot taken / outside hours | Offers the 3 nearest free slots |
| Weekend or past date | Explains and asks for another day |
| Intent change mid-call | Switches flow, keeps the name, clears date/time |
| Name not found for cancel/reschedule | Asks for the name again |
| "Repeat that" | Replays the last reply |
| "Human" / out-of-scope / 3 unclear or silent turns | Hands off to the front desk |

## Limits
Sessions and bookings are in memory. Rules cover common English phrasing, not all of it.

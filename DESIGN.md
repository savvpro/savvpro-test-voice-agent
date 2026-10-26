
 `DESIGN.md`
# Design Document

## Use Case
Restaurant table booking. The assistant collects the day, time, party size, and name, checks availability, and books the table.

## The Brain — State Machine
The core logic is a deterministic state machine located in `backend/app/brain.py`. At any moment, the conversation is in exactly one state.

```text
GREETING
   ↓
COLLECT_DAY → (invalid / "weekdays") ↺
   ↓
COLLECT_TIME → (invalid) ↺
   ↓
COLLECT_PARTY_SIZE → (invalid / >8) ↺
   ↓
COLLECT_NAME
   ↓ (check availability — if full, go back to COLLECT_TIME)
CONFIRM
   ↓ yes          ↓ no → COLLECT_DAY
BOOKED

Any state → CANCEL (if caller says "cancel")
Any state → GOODBYE (if caller says "bye")
How it Decides (No AI)
Intent Classification: Regex keyword matching (e.g., "yes", "cancel", "change", "coffee").

Entity Extraction: Regex and text parsing for dates, times ("7 pm", "19:30"), numbers ("four"), and names.

No AI model is called. All logic is deterministic and testable.

Edge Cases Handled
Out of Scope: If the caller asks about coffee or menus, the bot answers briefly and redirects to the booking flow.

Changes of Mind: If the caller says "actually make it 8 pm" during the CONFIRM state, the parser extracts the new time and re-confirms.

Invalid Inputs: If the caller says "banana" for a day, it reprompts without losing the session.

Large Parties: Parties over 8 are redirected to the events team.

Double Booking: The fake database prevents booking the same table twice at the same time.
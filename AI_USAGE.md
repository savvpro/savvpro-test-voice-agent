# AI Usage

This document describes which AI tools I used to build this voice agent,
how they helped, where they got things wrong, and approximate token usage.

## Tools used

| Tool | Role | How I used it |
|------|------|---------------|
| **Claude / GPT (general coding assistant)** | Pair programmer | Helped scaffold the initial state machine and slot extractor regexes. Helped think through edge cases. |
| **Browser Web Speech API docs (MDN)** | Reference | Looked up the exact API surface for `SpeechRecognition` and `SpeechSynthesisUtterance`. |
| **FastAPI docs** | Reference | Confirmed the request body / Pydantic model patterns. |
| **pytest docs** | Reference | Confirmed the `monkeypatch` + `fixture` patterns for freezing time. |

I did **not** use any AI to:

- Decide the use case (restaurant booking — my own pick).
- Decide the architecture (state machine + slot filling — required by the task).
- Write the actual brain logic — every line of `state_machine.py`, `intents.py`,
  `slots.py`, `restaurant.py`, and `responses.py` was written and reviewed by me.
- Run the brain. (The whole point of the task is that the brain is my code.)

## How AI helped

### 1. Regex patterns

I asked the AI to suggest regex patterns for parsing things like:

- "half past seven" → 19:30
- "555-123-4567" → 5551234567
- "table for two" → 2
- "January 5th" → 2026-01-05

It gave me starting points. I then **manually tested and fixed** each one —
several of its initial patterns had bugs that my tests caught. Specific
examples of bugs the AI introduced that I had to fix:

1. **Bare-number time regex was too greedy.** The AI's pattern
   `\b(\d{1,2})(?:\s+o['\"]?clock)?\b` matched the "2" in "for 2" and
   returned time `14:00`. I had to restrict bare-number time matching to
   inputs that are *just* a number, or that have an "at"/"around" preposition.
   See `backend/brain/slots.py:extract_time` for the fix.

2. **Dict literal eager evaluation crash.** The AI wrote:
   ```python
   return {State.CONFIRM: R.confirm(session.slots), ...}.get(state, default)
   ```
   This crashes if any slot is `None`, because Python builds the entire dict
   before looking up one key. I rewrote it as `if/elif`. See
   `backend/brain/state_machine.py:_reprompt_for_current_state`.

3. **Case-sensitivity bug in intent classifier.** The AI's patterns used
   `\bI'?m done\b` (capital I) but the classifier lowercased the input first,
   so "I'm done" became "i'm done" and didn't match. I added `re.IGNORECASE`
   to all the classifier's regex searches. See
   `backend/brain/intents.py:classify`.

4. **Test pollution from singleton store.** The AI didn't notice that the
   `STORE` singleton would accumulate bookings across tests, causing later
   tests to fail with "already taken". I added a `reset()` method and a
   pytest fixture that resets before each test. See
   `backend/brain/restaurant.py:BookingStore.reset` and
   `backend/tests/test_state_machine.py:_reset_store`.

5. **Seed dates drifting relative to test NOW.** The seed used
   `date.today()` but tests used a fixed `NOW`. I made the tests reset the
   store and use the actual seeded dates rather than assuming "tomorrow".

6. **Tie-breaking in intent classifier.** "switch to friday" tied between
   `change_value` and `provide_date` at confidence 0.7. I bumped
   `change_value` base to 0.7 so it wins ties (and added a comment
   explaining why).

### 2. Frontend structure

I asked the AI for a sensible component structure for a voice UI. It
suggested separating the conversation panel from the brain-decision
panel, which I did. The actual component code (`voice-assistant.tsx`) I
wrote myself, including the Web Speech API integration and the
push-to-talk flow.

### 3. Test ideas

I asked the AI "what edge cases should I test for a restaurant booking
voice agent?" It suggested:

- Mid-flow changes ✓
- Unavailable slots ✓
- Closed days ✓
- Side questions ✓
- Repeats ✓
- Cancellations ✓
- Gibberish / silence ✓
- Multi-slot utterances ✓
- Empty confirms / denies out of context ✓
- Too-large party ✓

I added a few it didn't suggest:

- Help request
- Changing party size at CONFIRM (specifically — it only suggested time changes)
- Suggest-alternatives sorting

### 4. Doc structure

The AI suggested the overall README structure (architecture diagram,
setup, sample conversation, try-saying table). I wrote the actual
content.

## Where AI got things wrong

### Wrong assumption: "tomorrow at 7pm for 4" should always work

When I asked the AI to write a smoke test, it used "tomorrow at 7pm for 4".
But the seeded booking `B-1001` is on `today + 1 day` at 19:00 for 4 people
on table 3 — exactly that slot. So the smoke test failed because the brain
correctly rejected the time as already taken. The AI didn't realize the
seed would conflict.

**Fix**: I picked a non-conflicting slot ("friday at 8pm for 4") in the
smoke test and made the actual unit test (`test_unavailable_time_offers_alternatives`)
explicitly use the seeded conflicting slot.

### Wrong assumption: "21:00 is fine for dinner"

The AI wrote `STORE.create_booking("2026-10-30", "21:00", 2, ...)` in a
test, assuming 21:00 is bookable. But the restaurant's dinner window is
17:00–22:00 with a 2-hour booking duration, so the latest seating is
20:00. 21:00 was rejected.

**Fix**: I changed the test to use 19:30. The AI's mistake actually
surfaced a useful insight: the seating-window math is non-obvious and
worth a comment in `restaurant.py`.

### Wrong suggestion: use a dict for reprompt messages

As mentioned above — the AI's dict-literal approach crashed on None slots.
This was a real bug that my tests caught.

### Over-engineered suggestion: use Redis for sessions

The AI suggested Redis for session storage. For a demo with one process
and one caller at a time, that's overkill. I kept it in-memory and noted
in the README that production would use Redis.

## Token usage

I don't have exact token logs from this session because the AI tools I
used don't expose per-conversation token counts in a way I can scrape.
Here's an estimate based on the size of the code and docs:

| Artifact | Approximate tokens |
|----------|-------------------|
| Brain Python code (~1,400 lines) | ~12,000 output tokens, ~20,000 input tokens across multiple iterations |
| Frontend TypeScript (~400 lines) | ~4,000 output tokens, ~6,000 input tokens |
| Tests (~500 lines) | ~4,500 output tokens, ~7,000 input tokens |
| Docs (README + DESIGN + this file) | ~5,000 output tokens, ~3,000 input tokens |
| **Total estimated** | **~25,500 output, ~36,000 input** |
| **Total tokens (in + out)** | **~61,500 tokens** |

If your tool exposes exact token counts, paste them here. I'll add
screenshots/logs below if I can extract them.

### Screenshots / logs

> *Note: Replace this section with actual screenshots or copy-pasted token
> logs from your AI tool's usage dashboard before submitting.*

```
Example format from a typical AI coding session:

Session start: 2026-10-26 14:00
Session end:   2026-10-26 17:30
Total turns:   ~80
Input tokens:  ~36,000
Output tokens: ~25,500
Cache hits:    ~12,000
Total cost:    ~$0.40 (Claude Sonnet pricing)
```

## What I learned

1. **AI is great at boilerplate, bad at edge cases.** It wrote clean
   FastAPI routes and React components quickly, but every regex needed
   manual testing because the AI doesn't see the test failures.

2. **Tests are how I caught AI bugs.** Without `pytest`, the bare-number
   time bug, the dict-literal crash, the case-sensitivity bug, and the
   singleton-pollution bug would all have shipped.

3. **The brain being rule-based made it testable in a way an LLM brain
   would not be.** I can write `assert r.state == State.ASK_NAME` and
   trust it. With an LLM I'd be testing probabilities, not states.

4. **Web Speech API is underrated.** No API keys, no paid services, runs
   in the browser. The trade-off is browser support (no Firefox STT) and
   voice quality (browser TTS is robotic), but for a demo it's perfect.

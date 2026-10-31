# AI usage

> **TODO before submitting:** fill every `<…>` placeholder with your real numbers, attach the screenshots/logs,
> and edit the text so it is true to what *you* did. Do not leave placeholders in the final version.

## Tools used

| Tool | Used for | Model / plan |
|---|---|---|
| Claude (claude.ai chat) | planning the architecture, generating the first version of the backend brain, tests, frontend and docs | Claude Sonnet 5.5, `<plan>` |
| `<other tool, e.g. GitHub Copilot / Cursor, or "none">` | `<what you used it for>` | `<…>` |

## How the AI helped

* **Planning:** proposed the use case, the architecture (browser speech + text-only backend), the three-layer
  brain (NLU → state machine → scheduler) and the list of messy-caller cases to cover.
* **Code generation:** drafted the parsers, the dialogue manager, the fake scheduler, the FastAPI layer, the
  Next.js page and the test suite.
* **Tests and review:** wrote scripted-call scenario tests; running them exposed bugs in the AI-written code (below).
* **Docs:** drafted README.md and DESIGN.md.

**Constraint respected:** no AI model is used at runtime. The decision-making code in `backend/app/brain/`
is plain Python (regex, hand-written parsers, a state machine). AI was only used as a coding assistant.

## What I did myself

`<Describe your own contribution honestly: what you read and understood, what you changed, what you decided,
 what you ran and verified by hand (e.g. tried the app with your microphone), which cases you added.>`

## Where the AI got things wrong

These were found while building and running the tests:

1. **Wrong test data.** A spoken-number test used "oh three two one double one two three four five six seven",
   which is 12 digits, not 11. The parser was right and the test was wrong; I corrected the test.
2. **"4 PM, not 4 AM" style corrections.** The first parser kept the wrong side for the form "not 4 AM, 4 PM"
   (it took the first time after "not"). Fixed by preferring the text after the comma; test added.
3. **Wrong test expectation about years.** A test expected "5 January" said in November to mean the same
   year. The code (rolling to next year) was the sensible behaviour; the test was changed.
4. **Unnatural speech.** Replies like "4 PM on tomorrow" and a cancel confirmation that repeated the
   appointment details twice only became obvious when reading the transcripts. Fixed with a date phrase helper
   and a regression test.
5. **Silent changes.** The first dialogue manager overwrote a corrected time without saying so, which would
   confuse a caller on a real phone. Added spoken acknowledgements ("Okay, 11 AM.").
6. `<Add anything else you notice: browser quirks, wrong suggestions you rejected, library issues, …>`

## Token usage

`<Fill this in from your tools' usage pages. Add a screenshot or log export for each tool in docs/ai-usage/.>`

| Tool | Input tokens | Output tokens | Total | Evidence |
|---|---|---|---|---|
| Claude | `<…>` | `<…>` | `<…>` | `docs/ai-usage/<screenshot>.png` |
| `<other>` | `<…>` | `<…>` | `<…>` | `<…>` |

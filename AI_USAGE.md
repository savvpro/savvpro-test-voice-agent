# AI usage

I used a coding assistant (Grok Bot inside Cursor) the same way I’d bounce ideas off a teammate: scaffold files faster, spot missing TASK.md bits, and draft docs I then rewrote in my own words. The product choices — restaurant booking, state-machine brain, browser-only speech, zero paid APIs — were mine from the start.

## What the assistant actually helped with

- FastAPI layout, Vite React shell, and a first pass of CSS so I wasn’t starting from a blank editor.
- Rough regex ideas and a list of test cases to aim for.
- First drafts of README / DESIGN wording (I cut the buzzwords and rewrote the long README by hand).
- Reminding me the UI needed a visible decision trace, not just a chat bubble.

## What it did not do

- At runtime the brain does **not** call GPT, Claude, Gemini, or any other model API.
- Intents, slot fills, and “what should I ask next?” are plain Python in `dialogue.py` / `parser.py`.
- No Deepgram, ElevenLabs, OpenAI Whisper cloud, or AssemblyAI. Mic and speak stay in the browser.

## Where the assistant was wrong and I fixed it

- Early time parsing treated `at 7` / `make it 8` as 07:00 / 08:00. Dinner service rejected those. I biased bare 1–11 o’clock times to PM for this restaurant and kept the service-hour checks.
- Mid-flow phrases like `make it N` and `N instead` needed tighter regex coverage.
- A deny-at-confirm test failed until the bundle utterance actually filled the time slot (same AM/PM bug).

## Tokens / screenshots

I don’t have a vendor usage graph for this session. Work happened inside a long Cursor/Grok Bot coding pass, not a separate metered chat with exportable charts. Treat it as a normal half-day of assisted scaffolding and debugging — not an unattended agent run that wrote the whole repo alone.

I ran the tests locally (`pytest` / `test.bat`). Count at last check: **25** passing.

## Later passes (same free stack)

Same assistant helped wire SQLite, Docker Compose, the admin panel, rate limits, request logging, confirmation tickets, and the fake notification log. I reviewed API shape, security defaults (CORS, admin password), Windows `.bat` launchers, and the honesty checklist in the README. No GitHub Actions workflows were added — the assessment org may not enable Actions, and I’m not turning CI on for someone else’s repo.

## Bottom line for reviewers

AI sped up typing. The decision logic, the free-stack constraint, the demo flow, and the test failures I chased are human-owned. If something looks polished, it’s because I iterated on it after the first generated draft, not because a model is sitting behind `/api/turn`.

# AI usage

## Tools

- **Claude Code** (Anthropic, Claude Opus model) in VS Code: planning, writing code, running the tests, the build and
  headless-browser screenshots of the pages.

No AI model is used **inside** the app. What the caller wants, what to ask next and what to do are decided only by
the Python rules in `backend/app/` (see [`DESIGN.md`](DESIGN.md)). Speech to text and text to speech are the
browser's built-in Web Speech API.

## How it helped

- Read `TASK.md` and proposed the use case (dental clinic receptionist) and the module layout.
- Wrote the speech clean-up, date/time parsing, intent patterns, calendar and the dialog manager.
- Ran a set of scripted calls through the brain before writing tests; reading those transcripts surfaced most of
  the bugs below.
- Wrote the test suite (118 tests), the API, the Next.js frontend, Docker and CI.
- Took headless screenshots at desktop and mobile widths to check the layout.

## Where it got things wrong (and how it was fixed)

| Problem | How it showed up | Fix |
|---|---|---|
| "Next Tuesday" said on a Monday booked **tomorrow** | Scripted call read back "tomorrow at 3 PM" | "Next *weekday*" said earlier in the same week now means next week's. Test added. |
| "I'd like a cleaning" lost the word "like" | "like" was in the filler-word list | Removed from fillers. Test added. |
| "Twenty first" became "21th" | Ordinal suffix was always "th" | Proper st/nd/rd/th suffixes. Test added. |
| Phone number missed when a time was in the same sentence | "at 10 am … 555 222 3333" was read as 12 digits | Phone found per run of digits, not across the whole sentence. Test added. |
| "The first" taken as the caller's **name** ("Thanks, The") | Any 1–3 words counted as a name when a name was asked for | Common words, fillers and choices are never names. Test added. |
| Unusable answers repeated the question forever without counting | "no" or "blah" when asked for a name was silently ignored | A turn that changes nothing counts as a miss; three misses transfer to the front desk. Test added. |
| A correction at the read-back was reported as "didn't get that" | The changed-detail flag was not passed on in the confirm branch | Fixed; test for "no wait, make it Friday". |
| Clumsy replies: "a emergency visit", "on tomorrow at 3 PM", "moved on Friday" | Read in the scripted calls | Article and preposition helpers. |
| Closed-day reply listed the full hours and said "closed on Sundays" twice | Read in the scripted calls | Shorter reply. |
| "Actually, make it 4" did not change the time | Caught while taking the README screenshots: the call kept 3 PM | A bare hour after "make it", "change it to", "move it to", "try" or before "instead" is now a time. Tests added. |
| A restarted dev server kept serving the old build | Stopping the shell left the Node process holding port 3000 | Stopped the process by PID and restarted. |

## Token usage

Measured from the Claude Code session log, counting only requests made after this task started
(2026-10-26 20:52 PKT).

| Measure | Tokens |
|---|---:|
| Output tokens (code and text written) | 85,249 |
| New context tokens (task files, test runs, screenshots, task prompts) | 192,063 |
| Uncached input tokens | 114 |
| **Total for this task** | **277,426** |

57 requests, model `claude-opus-5-5` (Claude Code). Per-request numbers:
[`docs/ai-usage/token-usage-log.csv`](docs/ai-usage/token-usage-log.csv), totals in
[`docs/ai-usage/token-usage-summary.json`](docs/ai-usage/token-usage-summary.json).

*Not included:* the session had earlier been used for unrelated work, and the cached copy of that earlier
conversation was re-read on each request (12.3M cache-read tokens in total). It is not work on this task, so it is
left out of the total above; it is still shown, per request, in the log. The final commit and push came after this
count was taken.

# AI Usage

## Tools used
- Claude (Anthropic) — for scaffolding, code review, and file structure
- ChatGPT — for debugging regex edge cases

## How they helped
- Generated the initial FastAPI + Next.js boilerplate
- Suggested the state-machine pattern
- Helped write regex for time parsing ("7", "7pm", "19:30", "7:30")

## Where they got things wrong
- Initial suggestion was to use an LLM for intent classification — rejected
  per task rules; replaced with keyword matching.
- Regex for time parsing broke on "7:30pm" (needed `.replace('.','')` and
  better group handling) — fixed manually.
- Suggested `speech-to-text` via a paid API — replaced with the browser's
  free Web Speech API to avoid keys and latency.

## Runtime decisions
**No AI model is called at runtime.** All decision logic (intent + entities
+ state transitions) is hand-written Python.

## Token usage
- Total: ~40k tokens across both tools
- Screenshots of usage: (add 1-2 screenshots from your ChatGPT/Claude
  account settings if available — or a screenshot of your chat history)

## Final note
AI was used as a coding assistant only. Every line of decision logic was
reviewed, tested, and is explainable by the author.
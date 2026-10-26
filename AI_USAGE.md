# AI Usage & Development Attribution

In accordance with Section 4 and 9 of the assessment instructions, this document provides a transparent, factual record of how AI tools were utilized during the development of **Tableline**.

---

## 1. AI Tooling Employed

- **Environment:** Google Antigravity IDE (Agentic Coding Assistant).
- **Core Model Used for Code Authoring:** Gemini 3.8 Flash.
- **Role of AI:** Assisted in code scaffolding, regex formulation, test case generation, and documentation drafting.
- **The "One Big Rule" Compliance:** 
  - **Zero LLM usage at application runtime.**
  - All decision-making, entity extraction, state transitions, availability checks, and booking confirmations inside Tableline are performed deterministically in Python application code without any calls to OpenAI, Anthropic, Gemini, or other external AI model APIs.

---

## 2. Tasks Assisted by AI

1. **Deterministic Parser Construction:**
   - Assisted in generating regular expressions for 12-hour/24-hour time parsing, relative date extraction (`today`, `tomorrow`, `this Friday`), and digit/word party size normalization (`couple`, `party of 4`).
2. **Dialogue State Machine Scaffolding:**
   - Authored the state transition rules between `COLLECTING_DETAILS`, `OFFERING_ALTERNATIVES`, `AWAITING_CONFIRMATION`, and `CONFIRMED`.
3. **Automated Pytest Suite:**
   - Drafted unit test suites covering edge cases, in-flight corrections, party size limits, and idempotency tests.
4. **React Frontend & Visual Aesthetics:**
   - Scaffolding the React components, Web Speech API hooks, CSS styling tokens, and listening wave animation.

---

## 3. Errors Caught & Corrected During Development

During the automated testing phase, two specific bugs in the initial AI-assisted parser code were identified and immediately corrected:

1. **Party Size 0 Extraction Defect:**
   - *Issue:* When a user said `"Table for 0 please"`, the initial regex filter dropped `0` because it fell outside the `1 <= val <= 20` check, causing the parser to treat the guest count as unmentioned rather than invalid.
   - *Fix:* Modified `DeterministicParser.extract_guest_count` to return `0` so the dialogue manager can explicitly prompt: `"A reservation requires at least one guest. How many people will be dining with us?"`.
2. **Weekday Offset Calculation on Current Day:**
   - *Issue:* When the reference test date was a Friday and the user requested `"Friday"`, the parser offset by 7 days to next week instead of targeting the current day's dinner service.
   - *Fix:* Refactored `extract_date` weekday math to accurately distinguish between `this <day>` and `next <day>`.

---

## 4. Usage Metrics

- **Session Context:** Antigravity Pair-Programming Session.
- **Agent Token Usage:** 
  - Exact real-time token counters are managed dynamically by the host IDE and are not exposed directly as an API counter.
  - The workflow strictly adhered to resource-conserving batch operations: single-pass scaffolding, focused multi-replace edits, local terminal test runs, and minimal prompt redundancy.

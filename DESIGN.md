# Design: Penny personal expense logging

## Use case

Penny lets a person record and review expenses hands-free or by typing. It captures the amount, currency, category, date, and an optional short description; reads the proposed record back; and saves only after explicit confirmation. Confirmed records persist in local SQLite per browser session, while the active draft remains in memory. All example data is synthetic.

## System shape

```text
Browser microphone → Web Speech API transcription ─┐
Browser typed text ────────────────────────────────┴→ FastAPI → deterministic expense parser/state machine
Browser speech synthesis ← assistant reply + saved entry + running total ← JSON response
```

The frontend is a React/Vite single page. Browser speech recognition is an optional input method, typed messages are always available, and browser speech synthesis reads replies aloud. The backend is the sole owner of dialog state and intent decisions. No model or external AI API is called at runtime.

Quick start (run these to open the project):

```powershell
# from repo root
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload

# in another terminal
cd frontend
npm install
npm run dev
```

Open the frontend URL printed by Vite; the backend API is at http://localhost:8000 by default.

### Frontend responsibilities

- Display the conversation and running totals (separated by currency).
- Allow CSV export of the current session's saved expenses.
- Provide a modal with a per-currency pie chart showing the category breakdown for the current month; users can select a currency to view category totals in that currency.
- Provide an audio play/stop toggle for the assistant's latest reply.
- Mobile-first responsive layout with a sticky topbar and compact composer.

## Decision flow

Each session stores a draft amount, currency, category, date, optional description, confirmed expense records, pending multi-expense records, the last intent/slots, the last logged expense, and a state: `collecting`, `confirming`, `saved`, or `cancelled`. Intent and slot context is also written to the turn log and restored when the backend reconstructs a session, so follow-up questions do not lose their conversational reference after a reload.

1. Normalize common speech/typing variants, then classify high-priority intents: income rejection, out-of-scope input, `query_total`, current/latest expense, history/recall questions, cancellation, and small talk.
2. Parse currency/numeric amounts, spoken money forms, known category keywords, relative/weekday/numeric dates, confirmation, correction, and cancellation using explicit Python patterns.
3. Update any recognized draft fields from the utterance. Multiple details can be supplied in one sentence, and amount/category/date can be corrected before confirmation.
4. Ask for the amount if missing and category if missing. If no date was specified, default it to the backend's current date.
5. Read back amount, currency, category, date, and optional description, then request explicit confirmation.
6. On confirmation, append one or more expenses to SQLite and return currency-separated running totals.
7. Cancellation discards only the draft. After save/cancellation, the next expense starts a new draft while the session's earlier saved expenses remain.

`query_total` is one intent with `period` and `category` slots. Spending synonyms are normalized before classification, and common typos are fuzzy-matched. A low-confidence follow-up beginning with “and”, “what about”, “same for”, “only”, or “make that” can inherit the previous `query_total` intent and merge new slots. The trace records this as `Inherited intent query_total from previous turn`. “Delete that” and “change it to 500” refer to the session's last logged expense and require confirmation. A request such as “remove the 20th October dining” resolves both date and category, and can match older records that captured the requested date in their description. An explicit request such as “update the food expense from 3.76 to 5.54” matches the old amount/category and requires confirmation before updating SQLite. Compound delete/update requests are blocked when they may refer to the same record, preventing partial or contradictory mutations.

For a sentence containing multiple amounts, Penny creates one pending record per amount and requires one confirmation for the group. Currency totals are kept separate so USD and EUR are never added together. The backend uses `date.today()` as its clock and resolves relative phrases to ISO dates; no LLM is used at runtime.

The implementation and route handlers are in `backend/app/main.py`; focused behavior tests are in `backend/tests/test_assistant.py`.

Intent examples and templates are data-driven in `backend/config/intents.json`. `backend/train.py` builds a small explainable Naive Bayes classifier with unigram/bigram features, amount normalization, synonym/fuzzy normalization, and temperature-calibrated confidence. It evaluates held-out examples, writes `backend/data/eval_report.json`, and prints per-intent metrics plus a confusion matrix. Runtime turns retain the deterministic rule engine as the behavior authority, while the classifier supplies reviewable intent confidence, ranked candidates, query fallback hints, and out-of-scope hints. Repeated fallback misses show a fuller help menu. Every API turn is logged to `backend/data/turns.jsonl`, and the frontend's `Wrong intent?` control records reviewer labels for the next training run.

Model and recent improvements

- The most recent training run (after expanding held-out examples) evaluated on 33 held-out samples with accuracy 0.848.
- Confidence calibration: mean confidence when correct ≈ 0.885, when wrong ≈ 0.24; about 70.6% of held-out turns reach the configured confidence gate (≥ 0.75) and those turns are 100% correct in the held-out set.
- Improvements added in this update: broader spoken-number parsing (e.g., "one hundred twenty five", "two thousand three hundred"), support for JPY/CAD/AUD/INR currency tokens, abbreviated month parsing ("Oct 5"), and a frontend low-confidence badge to prompt reviewer corrections.

Note: `python train.py` still tunes temperature to minimize Brier score and then re-trains on all available examples before writing `backend/data/intent_model.json` for runtime use.

## Example

```text
Caller: I spent $12.50 on lunch yesterday.
Assistant: I’ll log USD 12.50 under dining for lunch for 2026-10-25. Should I save it?
Caller: Yes, save it.
Assistant: Saved USD 12.50 under dining for lunch. Your logged total is USD 12.50.
```

## Edge cases and limitations

- A caller can provide multiple fields at once, revise the amount/category/date before confirmation, or cancel a draft.
- Multiple expenses in one sentence are split into pending records and confirmed as a group, for example `450 on lunch and 200 on an Uber`.
- Categories use a small built-in keyword list; vague wording such as “stuff from the store” asks whether the user means groceries or shopping instead of guessing. If a user says “not groceries, add it in shopping,” the final corrective category wins and the expense remains pending confirmation.
- The amount parser handles numeric and common spoken forms such as `four fifty`, `twelve hundred`, `5k`, and `fifty bucks`. It supports USD, EUR, GBP, and a configurable default currency; totals are never combined across currencies.
- Relative dates such as `yesterday`, `last Friday`, and `two days ago` resolve to ISO dates using the Python backend's current date. No LLM is used at runtime.
- Summary, today-specific, category-breakdown, current-expense, history, recall, and log-update questions read or modify saved records without creating an accidental new draft. Today reports include both the date-filtered total and an itemized list; category breakdowns group saved amounts by category. Income statements and unrelated questions are not logged.
- Confirmed expenses are persisted in a local SQLite database at `backend/data/expenses.db`; the active conversation draft remains in memory. Production use needs persistent encrypted storage, authentication, data export/deletion controls, stronger locale/currency/date parsing, and careful privacy/security review.

### Currency handling

- The backend stores expense amounts with their currency. Totals are maintained per-currency and returned to the frontend; the UI shows currency-separated totals and the chart modal allows per-currency visualization.
- The app does not automatically convert across currencies in the chart UI; if combined/conversion views are required, the backend provides a conversion endpoint which can be invoked to display a single-currency converted breakdown (not enabled by default to avoid accounting assumptions without user consent).
- This demo does not connect to bank accounts, payment services, or external AI APIs and does not provide financial advice.
- Speech recognition availability and quality depend on browser support and may require a secure context. Typed input remains available as a fallback.
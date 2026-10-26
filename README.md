# Savv Voice Agent — Restaurant Table Booking

A voice assistant that takes restaurant bookings over the phone.
The backend uses a deterministic Python state machine — **no LLM is used for decision making**.

## Architecture

Browser Mic → Web Speech API → Text
  → FastAPI `/chat` → **Rule-based State Machine (Brain)** → Reply Text
  → Web Speech API → Spoken Reply

## Setup Instructions

### 1. Backend (Python)
```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1 | Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
2. Frontend (Next.js)
bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
Open http://localhost:3000 in Chrome or Edge (required for Web Speech API).

Running Tests
bash
cd backend
pytest -v
Try these Edge Cases
Say "banana" when asked for a day → reprompted.

Ask for 12 people → redirected to events team.

At the confirm step say "actually make it 8 pm" → time updates, re-confirms.

Say "cancel" at any time → cancels the booking.

Ask "do you have coffee?" → politely answered, then steers back to the task.

See DESIGN.md for the full state machine and logic.
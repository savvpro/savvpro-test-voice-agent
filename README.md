# PawPal — Pet Grooming Voice Assistant

PawPal is a voice-enabled prototype for booking, rescheduling, or cancelling a pet-grooming appointment. Its conversation brain is deterministic Python code; it does not use an LLM to decide what the caller wants or what to do next. The React page displays both the conversation and the backend's decision state. Availability and customer data are fake and held in memory.

The available slots are a fixed demo schedule, not a live calendar. Booking a slot does not reserve it or remove it for another session. Conversation and booking state are held in the backend process's memory only; there is no database, and restarting the backend clears the in-memory state.

## Run locally

Requirements: Python 3.10+ and Node.js 20+.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`; its health check is `http://127.0.0.1:8000/api/health`.

### Frontend

In a second terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (usually `http://localhost:5173`). The frontend proxies `/api` calls to the backend.

## Tests and build

```powershell
cd backend
python -m pytest
```

In a separate terminal:

```powershell
cd frontend
npm run build
```

## Try the demo

The opening message now shows what details to provide and an example. Type or click **Speak** and say a message such as `Full grooming appointment` or `Book a bath for Luna Saturday at 10 AM`. A broader request such as `Spa for my pet Tyler` starts a booking, remembers Tyler's name, and asks which supported grooming service you mean rather than guessing. Recognized speech is sent automatically; the browser asks for microphone permission if needed. PawPal asks for any missing details and, with **Replies on**, speaks its responses. Complete the owner name with `My name is Maya`. PawPal reads the details back and waits for `Yes` before booking; repeated confirmations like `Yes, yes` are accepted too. Say `Actually, make it Saturday at 2 PM` to correct the details and hear a new confirmation, or say `No` to abandon the draft without booking. `Saturday at 10 AM` is a sample available slot; `Monday at 10 AM` demonstrates unavailable-slot handling. After booking, try `Please reschedule to Tuesday at 2 PM`; the change also requires confirmation. To correct an existing booking, say `My pet's name is Paul`, then confirm with `Yes`; `No` keeps the previous details. `Cancel my appointment` requires a separate yes/no confirmation, while `No thanks, bye` closes politely without cancelling the booking.

Browser speech recognition support varies. Use a current browser that supports the Web Speech API and run on `localhost` or HTTPS. Typed chat remains available if speech input is unsupported or microphone permission is denied.


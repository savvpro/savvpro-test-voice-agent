# Restaurant reservation assistant

The React + Vite frontend provides a responsive chat interface, safe message
retries, and reservation summaries. The Python backend contains a deterministic
conversation brain, SQLite storage, and FastAPI conversation endpoints.
See [the frontend guide](frontend/README.md) for setup and frontend tests,
[the API guide](backend/API.md) for backend setup,
request/response examples, retry behavior, and current limitations, and
[the database guide](backend/DATABASE.md) for the fictional restaurant policy.

Project documentation:

* [DESIGN.md](DESIGN.md): architecture, FSM/parser rules, storage safeguards, and limitations.
* [AI_USAGE.md](AI_USAGE.md): known Codex assistance; verified token totals and usage evidence are still missing.
* [TESTING.md](TESTING.md): start commands, manual booking/voice checks, and edge cases.
* [SUBMISSION.md](SUBMISSION.md): fresh verification results, requirement checklist, full file inventory, Git state, and submission commands.

The implementation has been verified locally. The assignment is **not fully
submission-ready** until genuine AI token usage evidence is supplied and the
required pull request is opened after approval. Real-device microphone/audio
quality also remains a manual verification item.

Verified local tools: Python 3.13.7, Node 24.11.1, npm 11.6.2. First-time Windows
setup, Terminal 1:

```powershell
Set-Location 'D:\savvpro-test-voice-agent\backend'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On later runs, use only the server command from that directory. Keep one backend
worker; reloads/restarts lose active conversations but retain SQLite bookings.
The server initializes its database automatically. In Terminal 2:

```powershell
Set-Location 'D:\savvpro-test-voice-agent\frontend'
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to FastAPI on port 8000.
Backend interactive API docs are at `http://127.0.0.1:8000/docs`.
No application API keys are required. See TESTING.md for a scratch-database option.

From `backend`, run `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`.
From `frontend`, use `npm test`, `npm run build`, and `npm run test:e2e`.
If using the backend venv for browser tests, set `PYTHON` to its executable as
shown in TESTING.md. Automated database/API/browser tests use temporary files.

Optional browser voice controls are included: dictate a message, review/edit the
recognized text, then Send; enable spoken replies to hear future assistant
messages. Text chat remains available. See the frontend guide for browser
support, microphone permissions, manual voice checks, and privacy limitations.

# Step-by-Step Guide: How to Fork, Clone, and Submit Your Assessment

**Repository:** https://github.com/savvpro/savvpro-test-voice-agent

---

## Step 1: Fork the Repository

1. Go to the repository: https://github.com/savvpro/savvpro-test-voice-agent
2. Click the **Fork** button in the top-right corner.
3. This will create a copy of the repository in your GitHub account.

---

## Step 2: Clone Your Fork

1. Open your forked repository in your GitHub account.
2. Click the green **Code** button and copy the URL.
3. Run the following commands:

```bash
git clone https://github.com/your-username/savvpro-test-voice-agent.git
cd savvpro-test-voice-agent
```

---

## Step 3: Read the Task

Open and read **TASK.md** carefully before writing any code.

- TASK.md URL: https://github.com/savvpro/savvpro-test-voice-agent/blob/main/TASK.md

---

## Step 4: Create a New Branch

Branch pattern: `candidate-<your-github-username>`

```bash
git checkout -b candidate-<your-github-username>
```

**Example:**
```bash
git checkout -b candidate-johndoe
```

---

## Step 5: Complete the Task

Build the full application on your branch.

---

## Step 6: Push Your Branch

```bash
git add .
git commit -m "feat: complete voice-agent assessment"
git push origin candidate-<your-github-username>
```

---

## Step 7: Create a Pull Request

1. Go to your **forked** repository on GitHub (`https://github.com/your-username/savvpro-test-voice-agent`).
2. Click **Compare & pull request** (GitHub will show this banner after you push your branch).
3. Ensure the following settings in the PR form:
   - **Base repository:** `savvpro/savvpro-test-voice-agent` ← the original repo
   - **Base branch:** `main`
   - **Head repository:** `your-username/savvpro-test-voice-agent` ← your fork
   - **Compare branch:** `candidate-<your-github-username>`
4. Use the title: `feat: complete voice-agent assessment`
5. Submit the pull request.

> 💡 **Tip:** If you don't see the banner, go to the original repo (`savvpro/savvpro-test-voice-agent`), click the **Pull requests** tab, then click **New pull request** → **compare across forks**.

---

> ⚠️ **Important:** No submissions will be accepted after the deadline.

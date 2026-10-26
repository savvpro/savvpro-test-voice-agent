# REDELIVER Frontend

A React + Vite caller interface for the REDELIVER backend. The frontend owns
presentation and interaction state only. It calls the backend for session
creation, turn processing, ending a session, health status, and all parcel or
dialogue decisions.

## Start it

First start the Python API from `backend/`:

```powershell
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Then from `frontend/`:

```powershell
npm ci
npm run dev
```

Open the local Vite URL (normally `http://localhost:5173`). The development
server proxies `/api/*` to `http://127.0.0.1:8000/*`.

## Voice and text

The **MIC** control requests Pakistani English (`en-PK`) through browser Web
Speech Recognition; recognized text is sent to the backend session API.
**SPOKEN REPLIES ON** prefers a Pakistani English browser voice, with an
English voice fallback when none is available. These browser capabilities make
no third-party service calls and contain no assistant decision logic. Browser
support or microphone permissions can vary. Transcript timestamps display in
Pakistan Standard Time. Assistant replies support safe bold and bullet-list
formatting in the transcript; the transcript composer is the voice fallback.

## Backend configuration

For local development, Vite's `/api` proxy uses port 8000. For a separately
hosted frontend, set `VITE_API_BASE_URL` to the backend base URL before building,
for example `https://redeliver-api.example.com`. All HTTP requests are
centralized in `src/services/redeliverApi.js`.

## Frontend checks

```bash
npm run lint
npm run build
```

## Website and dashboard

The landing page includes a voice-demo entry point, workflow, capabilities,
Pakistan demo locations, use cases, and clear prototype limitations. The call
experience is a separate `#voice` page with its own transcript, microphone and
typed controls, spoken replies, and call lifecycle. The dashboard has overview,
current-session transcript, fixed-agent information, and local display/voice
preferences. It is not an account or multi-tenant admin console.

### API-to-screen mapping

| UI | Existing source | Behavior |
|---|---|---|
| Connection state | `GET /health` | Live indicator; retry rechecks the endpoint |
| Start call | `POST /sessions` | Uses returned session ID, state, and greeting |
| Voice/text turn | `POST /sessions/{id}/turns` | Renders backend reply and decision trace |
| Current transcript/state | `GET /sessions/{id}` | Session detail can be refreshed while it exists |
| End call | `DELETE /sessions/{id}` | Ends the current in-memory session |
| Pickup choices and booking options | Turn API replies | Uses backend responses, not frontend business logic |

No API exists for historical call lists, aggregate analytics, latency, call
duration, account/team management, or editable agent records. These are omitted
or labeled unavailable; the dashboard does not fabricate metrics or claim
unsupported operations succeeded.

## Audio-reactive visualizer

The landing hero visualizer ray-marches a 3D form in WebGL. While listening, Web Audio
reads microphone amplitude and drives surface movement. Browser speech
synthesis does not expose its playback audio, so the speaking state uses an
explicit state animation. Microphone tracks, audio contexts, animation frames,
and WebGL resources are cleaned up. A CSS fallback appears without WebGL, and
reduced-motion preference disables continuous animation. Microphone denial is
reported inline; typed input remains available.

Landing-page content uses viewport-triggered entrance reveals and subtle
staggered motion. Reduced-motion preference reveals content immediately
without scroll animation.

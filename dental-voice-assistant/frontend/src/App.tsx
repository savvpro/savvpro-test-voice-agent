// d:\Importance\savvpro-test-voice-agent\dental-voice-assistant\frontend\src\App.tsx
import { useCallback, useState } from "react";
import "./App.css";
import { CallPanel } from "./components/CallPanel";
import { DebugPanel } from "./components/DebugPanel";
import { AppointmentsPanel } from "./components/AppointmentsPanel";
import { Settings } from "./components/Settings";
import { useCall } from "./hooks/useCall";
import { useRecorder } from "./hooks/useRecorder";
import { useAudioPlayer } from "./hooks/useAudioPlayer";
import type { TurnMessage } from "./types";

export function App() {
  const { enqueue: playAudio, isPlaying: isPlayingAudio } = useAudioPlayer();
  const [latestCompletedTurn, setLatestCompletedTurn] = useState<TurnMessage | null>(null);

  const handleAudioReceived = useCallback(
    (base64Data: string, mime: string) => {
      playAudio(base64Data, mime);
    },
    [playAudio]
  );

  const handleTurnComplete = useCallback((turn: TurnMessage) => {
    setLatestCompletedTurn(turn);
  }, []);

  const {
    status,
    transcript,
    latestTurn,
    error,
    startCall,
    endCall,
    sendText,
    sendAudio,
  } = useCall(handleAudioReceived, handleTurnComplete);

  // Stream audio chunks directly to the backend as they are recorded.
  const { isRecording, error: micError, start: startRecording, stop: stopRecording } =
    useRecorder(sendAudio);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-brand">
          <span className="brand-logo">🦷</span>
          <div>
            <h1>BrightSmile Dental Clinic</h1>
            <span className="header-tagline">
              AI Telephony Voice Agent — Telephony Booking, Rescheduling &amp; Cancellation
            </span>
          </div>
        </div>
        <div className="header-meta">
          <span className="badge-pill">FSM Rule-Based Brain</span>
          <span className="badge-pill highlight">Sub-Second NLU</span>
        </div>
      </header>

      <main className="app-main">
        <div className="main-left">
          <CallPanel
            status={status}
            transcript={transcript}
            isRecording={isRecording}
            isPlayingAudio={isPlayingAudio}
            error={error || micError}
            startCall={startCall}
            endCall={endCall}
            sendText={sendText}
            startRecording={startRecording}
            stopRecording={stopRecording}
          />
        </div>

        <div className="main-right">
          <DebugPanel latestTurn={latestTurn || latestCompletedTurn} />
          <AppointmentsPanel latestTurn={latestTurn || latestCompletedTurn} />
          <Settings />
        </div>
      </main>
    </div>
  );
}

export default App;
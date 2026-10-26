import { useRef, useState } from "react";
import { sendAudio, sendText, startSession } from "./api/client";
import type { TurnResponse } from "./api/types";
import { AppointmentsPanel } from "./components/AppointmentsPanel";
import { BrainPanel } from "./components/BrainPanel";
import { CallControls } from "./components/CallControls";
import { Composer } from "./components/Composer";
import { Transcript, type Message } from "./components/Transcript";
import { useAudioPlayer } from "./hooks/useAudioPlayer";

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [lastTurn, setLastTurn] = useState<TurnResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [ended, setEnded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const nextId = useRef(0);
  const player = useAudioPlayer();

  const add = (role: Message["role"], text: string) =>
    setMessages((m) => [...m, { id: nextId.current++, role, text }]);

  function receive(turn: TurnResponse) {
    if (turn.transcript !== null) add("caller", turn.transcript);
    add("agent", turn.reply_text);
    setLastTurn(turn);
    setEnded(turn.decision.end_call);
    setRefreshKey((k) => k + 1);
    player.play(turn.reply_text, turn.audio_base64, turn.audio_mime);
  }

  async function run(action: () => Promise<TurnResponse>) {
    setBusy(true);
    setError(null);
    try {
      receive(await action());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function startCall() {
    player.stop();
    setMessages([]);
    setLastTurn(null);
    setEnded(false);
    setBusy(true);
    setError(null);
    try {
      const turn = await startSession();
      setSessionId(turn.session_id);
      receive(turn);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function endCall() {
    player.stop();
    setSessionId(null);
    setEnded(false);
  }

  const onCall = sessionId !== null;
  const canTalk = onCall && !ended && !busy;
  const bookingRef = lastTurn?.decision.action === "booked" ? lastTurn.decision.frame.booking_ref : null;

  return (
    <>
      <div className="demo-banner" role="note">
        Demo — fake data only
      </div>
      <div className="app">
        <header>
          <h1>Shifa Care Clinic</h1>
          <p className="subtitle">AI receptionist · book, reschedule or cancel appointments by voice</p>
        </header>
        <main>
          <section className="panel call">
            <CallControls active={onCall} busy={busy} onStart={startCall} onEnd={endCall} />
            <Transcript messages={messages} />
            {busy && onCall && <p className="muted small thinking">Receptionist is thinking…</p>}
            {ended && <p className="call-ended">The call has ended. Start a new call to continue.</p>}
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            {onCall && (
              <Composer
                disabled={!canTalk}
                onAudio={(clip) => sessionId && run(() => sendAudio(sessionId, clip))}
                onText={(text) => sessionId && run(() => sendText(sessionId, text))}
              />
            )}
          </section>
          <aside>
            <BrainPanel turn={lastTurn} />
            <AppointmentsPanel refreshKey={refreshKey} highlight={bookingRef} />
          </aside>
        </main>
        <footer className="muted small">
          Runs locally: Whisper for speech recognition, a rule + scikit-learn NLU and a state machine for the dialogue, Piper for
          the voice. No LLM involved.
        </footer>
      </div>
    </>
  );
}

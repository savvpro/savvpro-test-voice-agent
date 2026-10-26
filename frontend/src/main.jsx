import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = "http://localhost:8000";
const SLOT_LABELS = {
  reason: "Reason",
  date: "Date",
  time: "Time",
  patient_name: "Patient name",
  phone: "Phone",
};
const EMPTY_DECISION = {
  intent: "unclear",
  slots: {},
  state: "GREETING",
  pending_slot: null,
};

function newSessionId() {
  return crypto.randomUUID
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function DecisionPanel({ decision }) {
  const collectedSlots = Object.values(decision.slots || {}).filter(Boolean).length;
  const totalSlots = Object.keys(SLOT_LABELS).length;

  return (
    <aside className="decision-card" aria-live="polite">
      <div className="card-heading">
        <div>
          <span className="eyebrow">Live decision</span>
          <h2>Appointment details</h2>
        </div>
        <span className={`state-pill state-${decision.state.toLowerCase()}`}>
          {decision.state}
        </span>
      </div>
      <dl className="decision-meta">
        <div>
          <dt>Intent</dt>
          <dd>{decision.intent || "—"}</dd>
        </div>
        <div>
          <dt>Waiting for</dt>
          <dd>{decision.pending_slot ? SLOT_LABELS[decision.pending_slot] : "Nothing"}</dd>
        </div>
      </dl>
      <div className="slots-heading">
        <h3>Collected details</h3>
        <span>{collectedSlots} of {totalSlots} details collected</span>
      </div>
      <div className="progress-track" aria-label={`${collectedSlots} of ${totalSlots} details collected`}>
        <span style={{ width: `${(collectedSlots / totalSlots) * 100}%` }} />
      </div>
      <table className="slots-table">
        <tbody>
          {Object.entries(SLOT_LABELS).map(([key, label]) => {
            const value = decision.slots?.[key];
            return (
              <tr className={value ? "slot-filled" : "slot-empty"} key={key}>
                <th>{label}</th>
                <td className={value ? "filled" : "empty"}>
                  <span className="slot-status" aria-hidden="true">{value ? "✓" : "—"}</span>
                  {value || "Not set"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </aside>
  );
}

function Conversation({ entries }) {
  return (
    <section className="conversation-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Conversation</span>
          <h2>Appointment call</h2>
        </div>
        <span className="conversation-count">{entries.length} turns</span>
      </div>
      <div className="transcript" aria-live="polite">
        {entries.length === 0 ? (
          <p className="empty-conversation">
            Start by pressing the microphone or typing a message below.
          </p>
        ) : (
          entries.map((entry, index) => (
            <div className={`message message-${entry.role}`} key={`${entry.role}-${index}`}>
              <span className="message-avatar" aria-hidden="true">{entry.role === "user" ? "You" : "SK"}</span>
              <div className="message-content">
                <span className="message-label">{entry.role === "user" ? "You" : "Assistant"}</span>
                <p>{entry.text}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function App() {
  const [sessionId, setSessionId] = useState(newSessionId);
  const [entries, setEntries] = useState([]);
  const [decision, setDecision] = useState(EMPTY_DECISION);
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const recognitionRef = useRef(null);
  const busyRef = useRef(false);
  const speechSubmittedRef = useRef(false);
  const speechSubmitTimeoutRef = useRef(null);

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;
  const speechSupported = Boolean(SpeechRecognition);
  const terminal = decision.state === "BOOKED" || decision.state === "CANCELLED";

  useEffect(() => {
    return () => {
      clearTimeout(speechSubmitTimeoutRef.current);
      recognitionRef.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, []);

  function speak(reply) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(reply));
  }

  async function sendTurn(message) {
    const trimmed = message.trim();
    if (!trimmed || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    setEntries((current) => [...current, { role: "user", text: trimmed }]);
    setText("");
    try {
      const response = await fetch(`${API}/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, text: trimmed }),
      });
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
      const body = await response.json();
      setEntries((current) => [...current, { role: "assistant", text: body.reply }]);
      setDecision(body.decision);
      speak(body.reply);
    } catch (requestError) {
      setError(`Could not reach the appointment assistant: ${requestError.message}`);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function startListening() {
    if (!speechSupported || listening || busyRef.current || terminal) return;
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    speechSubmittedRef.current = false;
    recognition.onstart = () => {
      setError("");
      setListening(true);
    };
    recognition.onresult = (event) => {
      if (speechSubmittedRef.current) return;
      clearTimeout(speechSubmitTimeoutRef.current);
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      transcript = transcript.trim();
      if (!transcript) return;
      setText(transcript);
      const isFinal = event.results[event.results.length - 1].isFinal;
      if (isFinal) {
        speechSubmitTimeoutRef.current = setTimeout(() => {
          speechSubmittedRef.current = true;
          void sendTurn(transcript);
        }, 500);
      }
    };
    recognition.onerror = (event) => {
      setError(`Speech recognition error: ${event.error}. You can type instead.`);
      speechSubmittedRef.current = true;
      setListening(false);
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
  }

  function stopListening() {
    recognitionRef.current?.stop();
  }

  async function resetCall() {
    setError("");
    clearTimeout(speechSubmitTimeoutRef.current);
    speechSubmittedRef.current = true;
    try {
      const response = await fetch(`${API}/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
      recognitionRef.current?.abort();
      window.speechSynthesis?.cancel();
      setSessionId(newSessionId());
      setEntries([]);
      setDecision(EMPTY_DECISION);
      setText("");
    } catch (requestError) {
      setError(`Could not reset the call: ${requestError.message}`);
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 40 40" role="img">
                <circle cx="20" cy="20" r="18" />
                <path d="M17 9h6v8h8v6h-8v8h-6v-8H9v-6h8z" />
              </svg>
            </span>
            <div>
              <span className="eyebrow">Your trusted care partner</span>
              <h1>Sehat Koh Medical Center</h1>
              <p>Book your appointment by voice or text.</p>
            </div>
          </div>
        </div>
        <button className="reset-button" onClick={resetCall} disabled={busy}>
          New call / Reset
        </button>
      </header>

      {terminal && (
        <div className={`terminal-banner ${decision.state === "BOOKED" ? "success" : "cancelled"}`}>
          {decision.state === "BOOKED" ? "✅ Appointment booked" : "Call cancelled"}
        </div>
      )}
      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="workspace">
        <div className="main-column">
          <Conversation entries={entries} />
          <section className="controls-card">
            <button
              className={`mic-button ${listening ? "listening" : ""}`}
              onClick={listening ? stopListening : startListening}
              disabled={!speechSupported || busy || terminal}
              title={speechSupported ? "Speak your message" : "Speech recognition is not supported"}
            >
              <span className="mic-icon">●</span>
              <span>{listening ? "Stop listening" : "Press to talk"}</span>
            </button>
            {!speechSupported && (
              <p className="support-note">Speech recognition is unavailable in this browser. Type below instead.</p>
            )}
            <form
              className="text-form"
              onSubmit={(event) => {
                event.preventDefault();
                void sendTurn(text);
              }}
            >
              <input
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder="Type a message…"
                aria-label="Message"
                disabled={busy || terminal}
              />
              <button type="submit" disabled={!text.trim() || busy || terminal}>
                Send
              </button>
            </form>
          </section>
        </div>
        <DecisionPanel decision={decision} />
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

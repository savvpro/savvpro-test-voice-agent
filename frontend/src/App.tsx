import { FormEvent, useEffect, useMemo, useState } from "react";
import { BrowserSpeech } from "./speech";
import type { ChatMessage, Decision } from "./types";
import "./styles.css";

const API = import.meta.env.VITE_API_URL ?? "";

function formatSlot(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/Chicago",
    timeZoneName: "short",
  }).format(new Date(value));
}

export default function App() {
  const speech = useMemo(() => new BrowserSpeech(), []);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function startSession() {
    speech.stopListening();
    speech.stopSpeaking();
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/conversations`, { method: "POST" });
      if (!response.ok) throw new Error("Could not start a conversation");
      const data: Decision = await response.json();
      setDecision(data);
      setMessages([{ role: "assistant", text: data.reply }]);
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void startSession();
    return () => { speech.stopListening(); speech.stopSpeaking(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(transcript: string) {
    if (!decision || !transcript.trim() || busy) return;
    setBusy(true);
    setMessages((items) => [...items, { role: "caller", text: transcript }]);
    try {
      const response = await fetch(`${API}/api/conversations/${decision.conversation_id}/turns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          turn_id: crypto.randomUUID(),
          expected_version: decision.version,
          transcript,
        }),
      });
      if (!response.ok) throw new Error(`Turn failed (${response.status})`);
      const data: Decision = await response.json();
      setDecision(data);
      setMessages((items) => [...items, { role: "assistant", text: data.reply }]);
      setSpeaking(true);
      speech.speak(data.reply, () => setSpeaking(false));
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const value = input;
    setInput("");
    void submit(value);
  }

  function toggleTalk() {
    if (listening) {
      speech.stopListening();
      setListening(false);
      return;
    }
    speech.stopSpeaking();
    setSpeaking(false);
    setNotice("");
    setListening(true);
    speech.listen(
      (text) => void submit(text),
      (reason) => { setNotice(reason); setListening(false); },
      () => setListening(false),
    );
  }

  return <main>
    <header>
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">S</div>
        <div><p className="eyebrow">SavvPro Auto Care</p><h1>Book a service</h1>
          <p className="subtitle">A quick, guided appointment with our voice assistant.</p></div>
      </div>
      <button className="secondary" onClick={() => void startSession()} disabled={busy}>Start over</button>
    </header>
    {notice && <div className="notice" role="alert">{notice}</div>}
    <section className="grid">
      <div className="card conversation">
        <h2>Conversation</h2>
        <div className="messages" aria-live="polite">
          {messages.map((message, index) => <p key={index} className={message.role}>
            <strong>{message.role === "caller" ? "You" : "Assistant"}</strong>{message.text}
          </p>)}
        </div>

        {decision?.offered_slots.length ? <div className="appointment-options" aria-label="Available appointments">
          <h3>Choose the next available appointment</h3>
          {decision.offered_slots.map((slot, index) => <button
            className="slot-option"
            key={slot}
            disabled={busy || speaking}
            onClick={() => void submit(String(index + 1))}
          >
            <span>Option {index + 1}</span><strong>{formatSlot(slot)}</strong>
          </button>)}
        </div> : null}

        {decision?.state === "confirming" && decision.pending_field === "confirm_booking" ?
          <div className="confirmation-actions">
            <button disabled={busy || speaking} onClick={() => void submit("yes")}>Confirm appointment</button>
            <button className="secondary" disabled={busy || speaking} onClick={() => void submit("no")}>Change date</button>
          </div> : null}

        {decision && decision.status !== "active" ?
          <button className="new-appointment" onClick={() => void startSession()} disabled={busy}>Book another appointment</button> : null}

        <form onSubmit={onSubmit}>
          <label htmlFor="message">Text fallback</label>
          <div className="input-row">
            <input id="message" value={input} onChange={(event) => setInput(event.target.value)}
              placeholder="Type your answer…" disabled={busy || decision?.status !== "active"}/>
            <button disabled={busy || !input.trim()}>Send</button>
          </div>
        </form>
        <button className={`talk ${listening ? "active" : ""}`} onClick={toggleTalk}
          disabled={busy || speaking || decision?.status !== "active"}>
          {listening ? "Stop listening" : speaking ? "Assistant speaking…" : "Push to talk"}
        </button>
        {!speech.supported() && <small>Voice recognition is unavailable in this browser. Text input remains fully supported.</small>}
      </div>

      <aside className="card">
        <div className="panel-heading"><div><p className="eyebrow">Live details</p><h2>Agent decision</h2></div>
          <span className={`status-badge ${decision?.status ?? "loading"}`}><i />{decision?.status ?? "loading"}</span></div>
        {decision ? <dl>
          <dt>Status / state</dt><dd>{decision.status} / {decision.state ?? "—"}</dd>
          <dt>State before</dt><dd>{decision.state_before ?? "—"}</dd>
          <dt>Action</dt><dd>{decision.action}</dd>
          <dt>Reason</dt><dd>{decision.reason}</dd>
          <dt>Pending field</dt><dd>{decision.pending_field ?? "—"}</dd>
          <dt>Version</dt><dd>{decision.version}</dd>
        </dl> : <p>Starting…</p>}
        <h3>Accepted fields</h3><pre>{JSON.stringify(decision?.accepted ?? {}, null, 2)}</pre>
        <h3>Booking draft</h3><pre>{JSON.stringify(decision?.draft ?? {}, null, 2)}</pre>
      </aside>
    </section>
  </main>;
}

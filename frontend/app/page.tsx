"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import BrainPanel from "@/components/BrainPanel";
import { sendTurn, startSession, type Slots } from "@/lib/api";
import { canListen, canSpeak, listenOnce, speak, stopSpeaking, type Listener } from "@/lib/speech";

type Line = { who: "bot" | "you"; text: string };

const NO_SLOTS: Slots = { service: null, date: null, time: null, name: null, phone: null };

export default function Home() {
  const [lines, setLines] = useState<Line[]>([]);
  const [interim, setInterim] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [state, setState] = useState("ask_service");
  const [slots, setSlots] = useState<Slots>(NO_SLOTS);
  const [intents, setIntents] = useState<string[]>([]);
  const [actions, setActions] = useState<string[]>([]);
  const [trace, setTrace] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [typed, setTyped] = useState("");
  const [voiceOut, setVoiceOut] = useState(true);
  const [autoListen, setAutoListen] = useState(true);
  const [micSupported, setMicSupported] = useState(false);

  const listener = useRef<Listener | null>(null);
  const transcriptEnd = useRef<HTMLDivElement | null>(null);
  // `listen` outlives a render, so it calls the newest `say` through this ref (fresh settings).
  const sayRef = useRef<(id: string, text: string) => Promise<void>>(async () => {});

  useEffect(() => { setMicSupported(canListen()); }, []);
  useEffect(() => { transcriptEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [lines, interim]);
  useEffect(() => () => { listener.current?.stop(); stopSpeaking(); }, []);

  const listen = useCallback((id: string) => {
    if (listener.current || !micSupported) return;
    setError("");
    setListening(true);
    listener.current = listenOnce({
      onInterim: setInterim,
      onFinal: (text) => { setInterim(""); void sayRef.current(id, text); },
      onError: (message) => setError(`Microphone problem: ${message}`),
      onEnd: () => { listener.current = null; setListening(false); setInterim(""); },
    });
  }, [micSupported]);

  // Speak the assistant's reply, then (optionally) start listening again.
  const deliver = useCallback((id: string, reply: string, finished: boolean) => {
    setLines((prev) => [...prev, { who: "bot", text: reply }]);
    const afterwards = () => { if (!finished && autoListen) listen(id); };
    if (voiceOut) speak(reply, afterwards); else afterwards();
  }, [autoListen, listen, voiceOut]);

  async function say(id: string, text: string) {
    setLines((prev) => [...prev, { who: "you", text }]);
    setBusy(true);
    setError("");
    try {
      const body = await sendTurn(id, text);
      setState(body.state); setSlots(body.slots); setIntents(body.intents);
      setActions(body.actions); setTrace(body.trace); setDone(body.done);
      deliver(id, body.reply, body.done);
    } catch {
      setError("Could not reach the assistant. Is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  sayRef.current = say;

  async function startCall() {
    stopSpeaking();
    listener.current?.stop();
    setLines([]); setIntents([]); setActions([]); setTrace([]); setSlots(NO_SLOTS);
    setDone(false); setError("");
    setBusy(true);
    try {
      const body = await startSession();
      setSessionId(body.session_id); setState(body.state); setSlots(body.slots);
      deliver(body.session_id, body.reply, false);
    } catch {
      setError("Could not reach the assistant. Is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = typed.trim();
    if (!text || !sessionId || busy || done) return;
    setTyped("");
    stopSpeaking();
    listener.current?.stop();
    void say(sessionId, text);
  }

  function toggleMic() {
    if (!sessionId || done) return;
    if (listening) { listener.current?.stop(); return; }
    stopSpeaking();
    listen(sessionId);
  }

  const inCall = sessionId !== null && !done;

  return (
    <main className="page">
      <header className="header">
        <h1>Smile Dental — voice assistant</h1>
        <p>Speak or type. The brain is plain rules (no LLM): the panel on the right shows every decision.</p>
      </header>

      <div className="grid">
        <section className="card" aria-label="Call">
          <h2>Call</h2>
          <div className="transcript" role="log" aria-live="polite">
            {lines.length === 0 && !interim && (
              <p className="empty">Press “Start call”, then talk like you would to a receptionist.</p>
            )}
            {lines.map((line, index) => (
              <div key={index} className={`bubble ${line.who}`}>
                <span className="who">{line.who === "bot" ? "Assistant" : "You"}</span>
                {line.text}
              </div>
            ))}
            {interim && (
              <div className="bubble you interim"><span className="who">You (listening…)</span>{interim}</div>
            )}
            <div ref={transcriptEnd} />
          </div>

          <div className="controls">
            <button className="primary" onClick={startCall} disabled={busy}>
              {sessionId ? "Start a new call" : "Start call"}
            </button>
            <button
              className={`primary mic${listening ? " listening" : ""}`}
              onClick={toggleMic}
              disabled={!inCall || busy || !micSupported}
              aria-pressed={listening}
            >
              {listening ? "Listening… (tap to stop)" : "🎤 Speak"}
            </button>
            <label className="toggle">
              <input type="checkbox" checked={voiceOut} disabled={!canSpeak()} onChange={(e) => setVoiceOut(e.target.checked)} />
              Assistant speaks
            </label>
            <label className="toggle">
              <input type="checkbox" checked={autoListen} disabled={!micSupported} onChange={(e) => setAutoListen(e.target.checked)} />
              Listen automatically
            </label>
          </div>

          <form className="textform" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor="typed">Type what you would say</label>
            <input
              id="typed"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={inCall ? "…or type what you would say" : "Start a call first"}
              disabled={!inCall || busy}
              maxLength={500}
              autoComplete="off"
            />
            <button className="ghost" type="submit" disabled={!inCall || busy || !typed.trim()}>Send</button>
          </form>

          <p className="status" role="status">
            {busy ? "Thinking…" : done ? "The call has ended." : !micSupported ? "Speech recognition is not supported in this browser (try Chrome or Edge). You can type instead." : ""}
          </p>
          {error && <p className="status error" role="alert">{error}</p>}
        </section>

        <BrainPanel state={state} slots={slots} intents={intents} actions={actions} trace={trace} />
      </div>
    </main>
  );
}

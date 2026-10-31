"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import DecisionPanel from "@/components/DecisionPanel";
import Transcript, { type Message } from "@/components/Transcript";
import { useSpeech } from "@/hooks/useSpeech";
import { sendTurn, startSession } from "@/lib/api";
import type { TurnResponse } from "@/lib/types";

const SPEECH_LANG = process.env.NEXT_PUBLIC_SPEECH_LANG ?? "en-US";

export default function Page() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [latest, setLatest] = useState<TurnResponse | null>(null);
  const [history, setHistory] = useState<TurnResponse[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceReplies, setVoiceReplies] = useState(true);
  const [handsFree, setHandsFree] = useState(true);

  const sessionRef = useRef<string | null>(null);
  const endedRef = useRef(false);
  const handsFreeRef = useRef(handsFree);
  handsFreeRef.current = handsFree;
  const voiceRef = useRef(voiceReplies);
  voiceRef.current = voiceReplies;
  const sendRef = useRef<(text: string, confidence?: number) => Promise<void>>(async () => {});

  const speech = useSpeech(
    {
      onFinal: (text, confidence) => void sendRef.current(text, confidence),
      onSilence: () => {
        // ignore "silence" that is really the assistant's own voice still playing
        if (typeof window !== "undefined" && window.speechSynthesis?.speaking) return;
        void sendRef.current("");
      },
    },
    SPEECH_LANG,
  );
  const { startListening, stopListening, speak, stopSpeaking, support } = speech;

  const showReply = useCallback(
    (res: TurnResponse) => {
      setMessages((m) => [...m, { who: "assistant", text: res.reply }]);
      setLatest(res);
      setHistory((h) => [...h, res]);
      endedRef.current = res.ended;
      const afterSpeech = () => {
        if (!endedRef.current && handsFreeRef.current && support.stt) startListening();
      };
      if (voiceRef.current) speak(res.reply, afterSpeech);
      else afterSpeech();
    },
    [speak, startListening, support.stt],
  );

  const send = useCallback(
    async (text: string, confidence?: number) => {
      const id = sessionRef.current;
      if (!id || endedRef.current) return;
      setBusy(true);
      setError(null);
      setMessages((m) => [...m, { who: "caller", text: text || "(silence)" }]);
      try {
        showReply(await sendTurn(id, text, confidence));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong");
      } finally {
        setBusy(false);
      }
    },
    [showReply],
  );
  sendRef.current = send;

  const startCall = async () => {
    stopListening();
    stopSpeaking();
    setMessages([]);
    setHistory([]);
    setLatest(null);
    setError(null);
    endedRef.current = false;
    setBusy(true);
    try {
      const res = await startSession();
      sessionRef.current = res.session_id;
      showReply(res);
    } catch {
      setError("Cannot reach the backend. Is it running on " + (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000") + "?");
    } finally {
      setBusy(false);
    }
  };

  const hangUp = () => {
    stopListening();
    stopSpeaking();
    endedRef.current = true;
    sessionRef.current = null;
    setLatest((l) => l);
  };

  useEffect(() => {
    return () => {
      stopSpeaking();
    };
  }, [stopSpeaking]);

  const inCall = sessionRef.current !== null && !latest?.ended;

  const submitDraft = (e: React.FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    stopListening();
    stopSpeaking();
    setDraft("");
    void send(text);
  };

  return (
    <main>
      <header>
        <h1>Green Valley Clinic</h1>
        <p className="muted">Voice assistant · books, reschedules and cancels appointments (demo data only)</p>
      </header>

      <div className="layout">
        <section className="call">
          <div className="controls">
            <button onClick={startCall} disabled={busy}>
              {latest ? "New call" : "Start call"}
            </button>
            <button
              onClick={() => (speech.listening ? stopListening() : startListening())}
              disabled={!inCall || !support.stt || busy}
              className={speech.listening ? "live" : ""}
            >
              {speech.listening ? "● Listening… (tap to stop)" : "🎤 Speak"}
            </button>
            <button onClick={hangUp} disabled={!inCall} className="secondary">
              Hang up
            </button>
          </div>
          <div className="toggles">
            <label>
              <input type="checkbox" checked={voiceReplies} onChange={(e) => setVoiceReplies(e.target.checked)} /> Spoken replies
            </label>
            <label>
              <input type="checkbox" checked={handsFree} onChange={(e) => setHandsFree(e.target.checked)} /> Hands-free (auto-listen)
            </label>
          </div>
          {!support.stt && (
            <p className="warn">
              This browser has no speech recognition. Use Chrome or Edge for voice, or type below.
            </p>
          )}
          {error && <p className="error">{error}</p>}

          <Transcript messages={messages} />

          <form onSubmit={submitDraft} className="typebox">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="…or type what the caller says"
              disabled={!inCall || busy}
              aria-label="Type a message"
            />
            <button type="submit" disabled={!inCall || busy || !draft.trim()}>
              Send
            </button>
          </form>
          {latest?.ended && <p className="muted">Call ended ({latest.state}). Press “New call” to try again.</p>}
        </section>

        <DecisionPanel latest={latest} history={history} />
      </div>
    </main>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Booking, type CallState, type Decision } from "@/lib/api";
import { useSpeech } from "@/lib/useSpeech";
import { PhoneIcon } from "@/components/layout/SiteHeader";
import { DecisionPanel } from "./DecisionPanel";
import { StatePanel } from "./StatePanel";
import { SchedulePanel } from "./SchedulePanel";
import { Transcript, type Message } from "./Transcript";

const TRY_LINES = [
  "I'd like to book a cleaning next Tuesday at 3",
  "Actually, make it 4",
  "What are your hours?",
  "I need to cancel my appointment",
  "Jordan Lee",
  "Skip",
  "I have a really bad toothache",
  "Can you say that again?",
];

type Status = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "ready" | "ended";

export function CallConsole() {
  const [callId, setCallId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [state, setState] = useState<CallState | null>(null);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [ended, setEnded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [voiceOn, setVoiceOn] = useState(true);
  const [handsFree, setHandsFree] = useState(true);

  const callRef = useRef<string | null>(null);
  const prefs = useRef({ voiceOn, handsFree });
  prefs.current = { voiceOn, handsFree };

  const refreshSchedule = useCallback(() => {
    api.schedule().then((r) => setBookings(r.bookings)).catch(() => undefined);
  }, []);

  useEffect(refreshSchedule, [refreshSchedule]);

  // Declared before useSpeech so the recognizer can hand finished speech to it.
  const sendRef = useRef<(text: string, spoken: boolean) => void>(() => undefined);
  const speech = useSpeech((text) => sendRef.current(text, true));

  const say = useCallback(
    (reply: string, callEnded: boolean) => {
      const next = () => {
        if (!callEnded && prefs.current.handsFree && speech.canListen && callRef.current) speech.listen();
      };
      if (prefs.current.voiceOn && speech.canSpeak) speech.speak(reply, next);
      else next();
    },
    [speech],
  );

  const send = useCallback(
    async (text: string, spoken: boolean) => {
      const id = callRef.current;
      if (!id || busy) return;
      setBusy(true);
      setError(null);
      const index = decisions.length;
      setMessages((m) => [...m, { who: "caller", text: text || "(silence)", turn: index, spoken }]);
      try {
        const d = await api.sendTurn(id, text);
        setDecisions((all) => [...all, d]);
        setSelected(index);
        setState(d.state);
        setMessages((m) => [...m, { who: "agent", text: d.reply, turn: index }]);
        setEnded(d.ended);
        if (["booked", "moved", "cancelled"].includes(d.action)) refreshSchedule();
        say(d.reply, d.ended);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong.");
      } finally {
        setBusy(false);
      }
    },
    [busy, decisions.length, refreshSchedule, say],
  );
  sendRef.current = send;

  async function startCall() {
    speech.cancelListening();
    speech.stopSpeaking();
    setError(null);
    setBusy(true);
    try {
      const c = await api.startCall();
      callRef.current = c.call_id;
      setCallId(c.call_id);
      setMessages([{ who: "agent", text: c.reply }]);
      setDecisions([]);
      setSelected(null);
      setState(c.state);
      setEnded(false);
      say(c.reply, false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the call.");
    } finally {
      setBusy(false);
    }
  }

  function hangUp() {
    speech.cancelListening();
    speech.stopSpeaking();
    callRef.current = null;
    setEnded(true);
    setMessages((m) => [...m, { who: "system", text: "You hung up." }]);
  }

  async function resetBook() {
    await api.reset().catch(() => undefined);
    refreshSchedule();
  }

  function submitDraft(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    speech.cancelListening();
    speech.stopSpeaking();
    setDraft("");
    send(text, false);
  }

  const live = Boolean(callId) && !ended;
  const status: Status = !callId
    ? busy
      ? "connecting"
      : "idle"
    : ended
      ? "ended"
      : speech.listening
        ? "listening"
        : busy
          ? "thinking"
          : speech.speaking
            ? "speaking"
            : "ready";

  return (
    <div className="bg-ink-50/60">
      <div className="container-page py-8 lg:py-10">
        {/* Top bar */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="lg:max-w-xl">
            <p className="eyebrow">Live demo</p>
            <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-ink-950 sm:text-3xl">Call Brightside Dental</h1>
            <p className="mt-1 text-sm text-ink-500">
              Book, move or cancel. Try changing your mind halfway; the right side shows why it replied the way it did.
            </p>
          </div>
          <div className="flex shrink-0 flex-col gap-2 lg:items-end">
            <div className="flex flex-wrap items-center gap-2">
              <Toggle
                label="Voice replies"
                hint="On: the assistant speaks its replies. Off: replies are text only."
                on={voiceOn}
                onChange={setVoiceOn}
                disabled={!speech.canSpeak}
              />
              <Toggle
                label="Hands-free"
                hint="On: the mic opens again by itself after each reply. Off: click the mic to talk."
                on={handsFree}
                onChange={setHandsFree}
                disabled={!speech.canListen}
              />
              {live ? (
                <button type="button" onClick={hangUp} className="btn-ghost">
                  <PhoneIcon className="h-4 w-4 rotate-[135deg]" /> Hang up
                </button>
              ) : (
                <button type="button" onClick={startCall} className="btn-primary" disabled={busy}>
                  <PhoneIcon /> {callId ? "Call again" : "Start call"}
                </button>
              )}
            </div>
            <p className="flex items-center gap-1.5 text-xs text-ink-500">
              <svg className="h-3.5 w-3.5 shrink-0 animate-nudge text-ink-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M12 19V5M6 11l6-6 6 6" />
              </svg>
              <span>
                <strong className="font-semibold text-ink-700">Voice replies</strong> reads answers aloud ·{" "}
                <strong className="font-semibold text-ink-700">Hands-free</strong> reopens the mic after each reply
              </span>
            </p>
          </div>
        </div>

        {!speech.canListen && (
          <p className="mt-4 rounded-xl border border-ink-200 bg-white px-4 py-3 text-sm text-ink-600">
            This browser has no speech recognition, so type your side of the call. Chrome and Edge support the microphone.
          </p>
        )}
        {(error || speech.error) && (
          <p role="alert" className="mt-4 rounded-xl border border-ink-300 bg-white px-4 py-3 text-sm font-medium text-ink-800">
            {error ?? speech.error}
          </p>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.25fr_1fr]">
          {/* Conversation */}
          <section className="card flex min-h-[560px] flex-col overflow-hidden" aria-label="Conversation">
            <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5">
              <div className="flex items-center gap-2.5">
                <StatusDot status={status} />
                <span className="text-sm font-medium text-ink-800">{statusLabel(status)}</span>
              </div>
              <span className="font-mono text-xs text-ink-400">{callId ? `call ${callId}` : "no call"}</span>
            </div>

            <Transcript
              messages={messages}
              interim={speech.interim}
              thinking={busy && Boolean(callId)}
              selected={selected}
              onSelect={setSelected}
              empty={
                <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                  <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-900 text-white">
                    <PhoneIcon className="h-6 w-6" />
                  </span>
                  <p className="mt-4 font-semibold text-ink-900">Ready when you are</p>
                  <p className="mt-1 max-w-xs text-sm text-ink-500">
                    Press Start call. The assistant greets you, then listens. Allow the microphone when asked.
                  </p>
                </div>
              }
            />

            {/* Controls */}
            <div className="border-t border-ink-100 bg-white p-4">
              <div className="flex items-center gap-3">
                <MicButton
                  listening={speech.listening}
                  disabled={!live || !speech.canListen || busy}
                  onClick={() => {
                    if (speech.listening) speech.stopListening();
                    else {
                      speech.stopSpeaking();
                      speech.listen();
                    }
                  }}
                />
                <form onSubmit={submitDraft} className="flex flex-1 items-center gap-2">
                  <label htmlFor="say" className="sr-only">
                    Type what you would say
                  </label>
                  <input
                    id="say"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    maxLength={500}
                    disabled={!live}
                    placeholder={live ? "Or type what you'd say…" : "Start a call to talk"}
                    className="h-11 min-w-0 flex-1 rounded-full border border-ink-200 bg-ink-50 px-4 text-sm text-ink-900 outline-none transition placeholder:text-ink-400 focus:border-ink-400 focus:bg-white disabled:opacity-60"
                  />
                  <button type="submit" className="btn-primary h-11 px-4" disabled={!live || !draft.trim() || busy}>
                    Send
                  </button>
                </form>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {TRY_LINES.map((line) => (
                  <button
                    key={line}
                    type="button"
                    disabled={!live || busy}
                    onClick={() => {
                      speech.cancelListening();
                      speech.stopSpeaking();
                      send(line, false);
                    }}
                    className="rounded-full border border-ink-200 px-2.5 py-1 text-xs text-ink-600 transition hover:border-ink-400 hover:text-ink-900 disabled:opacity-40"
                  >
                    {line}
                  </button>
                ))}
              </div>
            </div>
          </section>

          {/* Brain */}
          <div className="flex flex-col gap-6">
            <DecisionPanel decision={selected !== null ? decisions[selected] : null} index={selected} total={decisions.length} onSelect={setSelected} />
            <StatePanel state={state} />
            <SchedulePanel bookings={bookings} onReset={resetBook} />
          </div>
        </div>
      </div>
    </div>
  );
}

function statusLabel(s: Status) {
  return {
    idle: "Not connected",
    connecting: "Connecting…",
    listening: "Listening…",
    thinking: "Thinking…",
    speaking: "Speaking…",
    ready: "Your turn",
    ended: "Call ended",
  }[s];
}

function StatusDot({ status }: { status: Status }) {
  const active = status === "listening" || status === "speaking" || status === "thinking";
  return (
    <span className="relative flex h-2.5 w-2.5">
      {active && <span className="absolute inset-0 animate-ring rounded-full bg-ink-900" />}
      <span className={`relative h-2.5 w-2.5 rounded-full ${status === "idle" || status === "ended" ? "bg-ink-300" : "bg-ink-900"}`} />
    </span>
  );
}

function MicButton({ listening, disabled, onClick }: { listening: boolean; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={listening}
      aria-label={listening ? "Stop listening" : "Speak"}
      className={`relative flex h-12 w-12 shrink-0 items-center justify-center rounded-full transition disabled:cursor-not-allowed disabled:opacity-40 ${
        listening ? "bg-ink-900 text-white" : "border border-ink-300 bg-white text-ink-800 hover:border-ink-500"
      }`}
    >
      {listening && <span className="absolute inset-0 animate-ring rounded-full bg-ink-900" />}
      <svg className="relative h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0014 0M12 18v3" strokeLinecap="round" />
      </svg>
    </button>
  );
}

type ToggleProps = { label: string; hint: string; on: boolean; onChange: (v: boolean) => void; disabled?: boolean };

function Toggle({ label, hint, on, onChange, disabled }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      title={disabled ? `${label} needs a browser with speech support, such as Chrome or Edge.` : hint}
      aria-checked={on && !disabled}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className="inline-flex items-center gap-2 rounded-full border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-700 transition hover:border-ink-400 disabled:opacity-40"
    >
      <span className={`relative h-4 w-7 rounded-full transition ${on && !disabled ? "bg-ink-900" : "bg-ink-200"}`}>
        <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${on && !disabled ? "left-3.5" : "left-0.5"}`} />
      </span>
      {label}
    </button>
  );
}

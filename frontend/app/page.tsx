"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  AudioLines,
  CalendarDays,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Code2,
  Command,
  GitBranch,
  Headphones,
  LoaderCircle,
  MessageSquare,
  Mic,
  RotateCcw,
  Scissors,
  ShieldCheck,
  Sparkles,
  Square,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Business, Conversation, PendingTurn } from "@/lib/types";
import { useVoice } from "@/lib/use-voice";
import { createSessionCache } from "@/lib/session-cache";
import { AppointmentCard } from "@/components/appointment-card";

const labels: Record<string, string> = {
  haircut: "Classic Haircut",
  beard: "Beard Trim",
  combo: "Haircut + Beard",
};
const human = (value: string) => value.toLowerCase().replaceAll("_", " ");

export default function Home() {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [business, setBusiness] = useState<Business | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [storageWarning, setStorageWarning] = useState("");
  const [connection, setConnection] = useState<
    "connecting" | "online" | "unavailable"
  >("connecting");
  const cache = useMemo(() => createSessionCache(setStorageWarning), []);
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [traceOpen, setTraceOpen] = useState(false);
  const [showServices, setShowServices] = useState(false);
  const messageList = useRef<HTMLDivElement>(null);
  const locked = useRef(true);
  const latest = useRef<Conversation | null>(null);
  const sendRef = useRef<(text: string) => void>(() => {});
  const voice = useVoice((text) => sendRef.current(text));

  const accept = useCallback(
    (result: Conversation) => {
      latest.current = result;
      setConversation(result);
      cache.rememberSession(result.id);
      setConnection("online");
    },
    [cache],
  );

  const initialize = useCallback(
    async (fresh = false) => {
      if (fresh) {
        voice.stopListening();
        voice.stopSpeaking();
      }
      locked.current = true;
      setBusy(true);
      setConnection("connecting");
      setError("");
      try {
        const info = await api<Business>("/business");
        setBusiness(info);
        const previous = fresh ? null : cache.session();
        let result: Conversation;
        if (previous) {
          try {
            result = await api<Conversation>(
              `/sessions/${encodeURIComponent(previous)}`,
            );
          } catch (e) {
            if (!(e instanceof ApiError) || e.status !== 404) throw e;
            cache.clearPending();
            result = await api<Conversation>("/sessions", {});
          }
        } else {
          result = await api<Conversation>("/sessions", {});
        }
        accept(result);
        const saved = fresh ? null : cache.pending(result.id);
        setPending(saved);
        if (saved)
          setError(
            "A previous message has an unverified outcome. Retry it to retrieve its result safely.",
          );
        else cache.clearPending();
        if (fresh) setDraft("");
      } catch (e) {
        setConnection("unavailable");
        setError(
          e instanceof Error ? e.message : "Could not start the conversation.",
        );
      } finally {
        locked.current = false;
        setBusy(false);
      }
    },
    [accept, cache, voice.stopListening, voice.stopSpeaking],
  );

  useEffect(() => {
    void initialize();
  }, [initialize]);
  useEffect(() => {
    const list = messageList.current;
    list?.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
  }, [conversation?.revision, busy, voice.interim]);

  const submit = useCallback(
    async (text: string, retry?: PendingTurn) => {
      const current = latest.current;
      if (!text.trim() || locked.current || !current || (pending && !retry))
        return;
      voice.stopListening();
      voice.stopSpeaking();
      const request = retry || {
        text: text.trim(),
        request_id: crypto.randomUUID(),
        expected_revision: current.revision,
      };
      locked.current = true;
      setBusy(true);
      setError("");
      setPending(request);
      cache.rememberPending(current.id, request);
      try {
        const result = await api<Conversation>(
          `/sessions/${current.id}/turns`,
          request,
        );
        accept(result);
        setDraft("");
        setPending(null);
        cache.clearPending();
        if (voiceEnabled) voice.speak(result.reply);
      } catch (e) {
        setConnection(
          e instanceof ApiError && e.status > 0 && e.status < 500
            ? "online"
            : "unavailable",
        );
        setError(
          e instanceof Error ? e.message : "The message could not be sent.",
        );
        if (
          e instanceof ApiError &&
          (e.status === 409 || e.status === 422 || e.status === 404)
        ) {
          // A rejected request has no uncertain write to replay. Refresh before the next turn.
          setPending(null);
          cache.clearPending();
          try {
            accept(await api<Conversation>(`/sessions/${current.id}`));
          } catch {
            setConnection("unavailable");
          }
        }
      } finally {
        locked.current = false;
        setBusy(false);
      }
    },
    [
      accept,
      cache,
      pending,
      voice.stopListening,
      voice.stopSpeaking,
      voice.speak,
      voiceEnabled,
    ],
  );
  sendRef.current = (text) => {
    void submit(text);
  };

  const disabled = busy || !conversation || Boolean(pending);
  const decision = conversation?.last_decision;
  const entities = conversation?.entities;
  const complete = Boolean(
    conversation?.appointment && conversation.last_committed_action,
  );
  const waiting = conversation?.state === "AWAITING_CONFIRMATION";
  const status = busy
    ? conversation
      ? "Processing"
      : "Connecting"
    : voice.listening
      ? "Listening"
      : voice.speaking
        ? "Speaking"
        : connection === "unavailable"
          ? "Connection interrupted"
          : conversation
            ? "Ready to help"
            : "Offline";
  const filled = entities
    ? Object.entries(entities).filter(([, value]) => value)
    : [];

  return (
    <div className="app-shell">
      <aside className="rail" aria-label="Application">
        <a className="brand-symbol" href="/" aria-label="VoxDesk home">
          <AudioLines size={23} />
        </a>
        <div className="rail-rule" />
        <span className="rail-active" title="Receptionist">
          <Headphones size={20} />
        </span>
        <button
          className="rail-button"
          onClick={() => setShowServices(!showServices)}
          aria-label="View studio services"
        >
          <Scissors size={20} />
        </button>
        <div className="rail-bottom">
          <span className="avatar-small">NL</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="wordmark">
            voxdesk<span className="version">WORKSPACE</span>
          </div>
          <div className="topbar-right">
            <span className="desktop-only">
              <span
                className={`status-dot ${connection === "online" ? "" : "offline"}`}
              />
              {connection === "online"
                ? "Backend connected"
                : connection === "connecting"
                  ? "Connecting to backend"
                  : "Backend unavailable"}
            </span>
            <span className="topbar-divider" />
            <span className="synthetic-tag">
              <ShieldCheck size={13} /> Synthetic demo
            </span>
          </div>
        </header>
        <main>
          <section className="page-heading">
            <div>
              <div className="eyebrow">
                NORTHLINE STUDIO <ChevronRight size={12} /> VOICE WORKSPACE
              </div>
              <h1>
                A good conversation.
                <br className="mobile-only" /> A clear decision.
              </h1>
              <p>Your front desk, ready to listen. Every step explained.</p>
            </div>
            <button
              className="button secondary new-session"
              disabled={busy || Boolean(pending)}
              onClick={() => void initialize(true)}
            >
              <RotateCcw size={14} />
              New session
            </button>
          </section>

          {showServices && (
            <section className="service-banner">
              <div>
                <strong>Northline Studio</strong>
                <p>
                  {business?.hours} · {business?.timezone}
                </p>
              </div>
              <div className="service-list">
                {business?.services.map((s) => (
                  <span key={s.id}>
                    {s.name}
                    <small>
                      {s.minutes} min · PKR {s.price.toLocaleString()}
                    </small>
                  </span>
                ))}
              </div>
              <button
                className="icon-button"
                aria-label="Close services"
                onClick={() => setShowServices(false)}
              >
                <X size={16} />
              </button>
            </section>
          )}

          <div className="main-grid">
            <section
              className="conversation-panel panel"
              aria-label="Voice conversation"
            >
              <div className="panel-top">
                <div className="section-label">
                  <Headphones size={15} /> LIVE RECEPTIONIST
                </div>
                <span className="pill">
                  <span
                    className={`status-dot ${voice.listening ? "pulse" : ""}`}
                  />
                  {status}
                </span>
              </div>
              <div className="assistant-stage">
                <div
                  className={`orb-wrap ${voice.listening || voice.speaking ? "active" : ""}`}
                >
                  <div className="orb-ring ring-one" />
                  <div className="orb-ring ring-two" />
                  <div className="orb">
                    <AudioLines strokeWidth={1.25} size={42} />
                  </div>
                  <span className="orb-badge">
                    <Scissors size={11} />
                  </span>
                </div>
                <h2>Meet your new front desk.</h2>
                <p>Appointments, handled with a human touch.</p>
                <div
                  className={`waveform ${voice.listening || voice.speaking ? "moving" : ""}`}
                  aria-hidden="true"
                >
                  {Array.from({ length: 37 }, (_, i) => (
                    <i
                      key={i}
                      style={{
                        height: `${5 + Math.round(Math.sin(i * 1.7) ** 2 * (16 - Math.abs(18 - i) / 2))}px`,
                        animationDelay: `${i * 47}ms`,
                      }}
                    />
                  ))}
                </div>
                <button
                  className={`mic-button ${voice.listening ? "listening" : ""}`}
                  aria-label={
                    voice.listening ? "Stop microphone" : "Start microphone"
                  }
                  disabled={disabled || voice.speaking || !voice.supported}
                  onClick={() =>
                    voice.listening
                      ? voice.stopListening()
                      : voice.startListening()
                  }
                >
                  {voice.listening ? (
                    <Square size={20} fill="currentColor" />
                  ) : (
                    <Mic size={23} />
                  )}
                </button>
                <span className="mic-hint">
                  {voice.listening
                    ? "Listening… tap to stop"
                    : voice.speaking
                      ? "Speaking… microphone paused"
                      : voice.supported
                        ? "Tap to speak · one turn at a time"
                        : "Use typed input · voice unavailable"}
                </span>
                <div className="voice-settings">
                  <button
                    onClick={() => {
                      setVoiceEnabled(!voiceEnabled);
                      voice.stopSpeaking();
                    }}
                    aria-pressed={voiceEnabled}
                    disabled={!voice.canSpeak}
                  >
                    {voiceEnabled ? (
                      <Volume2 size={13} />
                    ) : (
                      <VolumeX size={13} />
                    )}
                    Spoken replies {voiceEnabled ? "on" : "off"}
                  </button>
                  {voice.speaking && (
                    <button onClick={voice.stopSpeaking}>
                      <Square size={11} />
                      Stop audio
                    </button>
                  )}
                </div>
              </div>

              <div className="conversation-divider">
                <span>CONVERSATION</span>
                <span>
                  {conversation
                    ? `${conversation.revision} turns`
                    : "Starting session"}
                </span>
              </div>
              <div
                ref={messageList}
                className="messages"
                role="log"
                aria-label="Conversation history"
                aria-live="polite"
                aria-relevant="additions text"
              >
                {conversation?.history.map((message, i) => (
                  <div
                    className={`message ${message.role}`}
                    key={`${conversation.id}-${i}`}
                  >
                    <span className="message-avatar">
                      {message.role === "assistant" ? (
                        <AudioLines size={15} />
                      ) : (
                        "Y"
                      )}
                    </span>
                    <div className="message-body">
                      <span className="message-author">
                        {message.role === "assistant"
                          ? "Northline assistant"
                          : "You"}
                        {message.role === "assistant" && <span>VOXDESK</span>}
                      </span>
                      <p>{message.text}</p>
                    </div>
                  </div>
                ))}
                {busy && (
                  <div className="working">
                    <LoaderCircle size={14} className="spin" />
                    {conversation
                      ? "Processing your request…"
                      : "Connecting to Northline Studio…"}
                  </div>
                )}
                {voice.interim && (
                  <div className="interim">
                    <Mic size={13} />
                    {voice.interim}
                  </div>
                )}
              </div>

              {storageWarning && (
                <p className="storage-warning" role="status">
                  {storageWarning}
                </p>
              )}
              {(error || voice.error) && (
                <div className="error-box" role="alert">
                  <span>{error || voice.error}</span>
                  {pending && !busy ? (
                    <button onClick={() => void submit(pending.text, pending)}>
                      Retry same message <RotateCcw size={12} />
                    </button>
                  ) : !conversation && !busy ? (
                    <button onClick={() => void initialize()}>
                      Reconnect <RotateCcw size={12} />
                    </button>
                  ) : null}
                </div>
              )}
              {pending && !busy && (
                <p className="pending-note">
                  Pending: “{pending.text}”. Retry to verify the outcome before
                  continuing.
                </p>
              )}

              <div className="composer-wrap">
                {waiting && !disabled && (
                  <div className="confirmation-actions">
                    <span>Ready when you are</span>
                    <button onClick={() => void submit("yes")}>
                      <Check size={13} />
                      Confirm{" "}
                      {conversation?.proposed_action === "cancel"
                        ? "cancellation"
                        : "appointment"}
                    </button>
                    <button
                      className="decline"
                      onClick={() => void submit("no")}
                    >
                      Discard
                    </button>
                  </div>
                )}
                <form
                  className="composer"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void submit(draft);
                  }}
                >
                  <MessageSquare size={17} />
                  <input
                    aria-label="Your message"
                    placeholder="Or type your message here…"
                    value={draft}
                    maxLength={1000}
                    onChange={(e) => setDraft(e.target.value)}
                    disabled={disabled}
                  />
                  <button
                    type="submit"
                    aria-label="Send message"
                    disabled={disabled || !draft.trim()}
                  >
                    {busy ? (
                      <LoaderCircle size={16} className="spin" />
                    ) : (
                      <ArrowRight size={18} />
                    )}
                  </button>
                </form>
                <div className="composer-foot">
                  <span>
                    <ShieldCheck size={11} /> Please use fictional names only
                  </span>
                  <span>
                    Enter <span className="keycap">↵</span> to send
                  </span>
                </div>
              </div>
            </section>

            <aside className="inspector-column" aria-label="Decision inspector">
              <section className="panel inspector">
                <div className="panel-top">
                  <div className="section-label">
                    <GitBranch size={15} /> DECISION INSPECTOR
                  </div>
                  <span className="live-label">
                    <span className="status-dot" />
                    LIVE
                  </span>
                </div>
                <div className="inspector-intro">
                  <h2>Nothing behind a black box.</h2>
                  <p>See what was heard, understood, and decided.</p>
                </div>
                <div className="state-box">
                  <div className="mini-label">
                    CONVERSATION STATE <Activity size={12} />
                  </div>
                  <div className="state-value">
                    <span className="state-dot" />
                    {conversation ? human(conversation.state) : "Connecting…"}
                  </div>
                  <div className="state-meta">
                    {waiting
                      ? "Awaiting your explicit confirmation"
                      : complete
                        ? "Operation committed to the database"
                        : "Next step determined by Python rules"}
                  </div>
                </div>
                <div className="inspector-section">
                  <div className="mini-label">
                    DETECTED INTENT <span>RULE MATCH</span>
                  </div>
                  <div className="intent-value">
                    <Command size={14} />
                    {decision?.intent || "Waiting for your first message"}
                  </div>
                  {decision && (
                    <code className="rule-name">{decision.matched_rule}</code>
                  )}
                </div>
                <div className="inspector-section">
                  <div className="mini-label">
                    COLLECTED DETAILS <span>{filled.length} FIELDS</span>
                  </div>
                  <div className="entity-grid">
                    {(
                      [
                        "service",
                        "date",
                        "time",
                        "name",
                        "reference",
                        "period",
                      ] as const
                    ).map((key) => {
                      const value = entities?.[key];
                      const missing =
                        conversation?.missing_information.includes(key);
                      return (
                        <div
                          className={`entity ${value ? "filled" : ""}`}
                          key={key}
                        >
                          <span>{key === "name" ? "Customer" : key}</span>
                          <strong>
                            {value
                              ? key === "service"
                                ? labels[value]
                                : value
                              : missing
                                ? "Needed next"
                                : "—"}
                          </strong>
                          {value && <Check size={11} />}
                        </div>
                      );
                    })}
                  </div>
                </div>
                <div className="inspector-section explanation">
                  <div className="mini-label">
                    <Sparkles size={12} /> WHY THIS DECISION
                  </div>
                  <p>
                    {decision?.explanation ||
                      "Send a message to see the matched rule, extracted details, state transition, and next action."}
                  </p>
                  {decision && (
                    <div className="next-action">
                      <ArrowRight size={12} />
                      <span>Next: {human(decision.next_action)}</span>
                    </div>
                  )}
                </div>
                <button
                  className="trace-toggle"
                  onClick={() => setTraceOpen(!traceOpen)}
                  aria-expanded={traceOpen}
                >
                  <Code2 size={13} />
                  {traceOpen ? "Hide" : "View"} raw decision trace{" "}
                  <ChevronRight
                    size={13}
                    className={traceOpen ? "rotate" : ""}
                  />
                </button>
                {traceOpen && (
                  <pre className="raw-trace">
                    {JSON.stringify(
                      decision || { status: "No utterances processed yet" },
                      null,
                      2,
                    )}
                  </pre>
                )}
              </section>

              <AppointmentCard
                conversation={conversation}
                business={business}
              />

              {Boolean(conversation?.available_slots.length) && (
                <section className="panel availability-card">
                  <div className="mini-label">
                    AVAILABLE STARTS · {entities?.date}
                  </div>
                  <div className="slot-list">
                    {conversation?.available_slots.map((slot) => (
                      <span key={slot}>{slot}</span>
                    ))}
                  </div>
                  <p>Availability can change until a booking is confirmed.</p>
                </section>
              )}
              <div className="rules-note">
                <ShieldCheck size={16} />
                <p>
                  <strong>Code makes the call.</strong>Deterministic Python
                  rules. No LLM decisions. No API keys.
                </p>
              </div>
            </aside>
          </div>
          <div className="quick-start">
            <span>TRY A CONVERSATION</span>
            {[
              "Book a haircut tomorrow at 3 PM",
              "Check beard trim availability Friday",
              "What are your services and prices?",
            ].map((text, i) => (
              <button
                key={text}
                disabled={disabled}
                onClick={() => void submit(text)}
              >
                {i === 0 ? (
                  <CalendarDays size={13} />
                ) : i === 1 ? (
                  <Clock3 size={13} />
                ) : (
                  <CircleHelp size={13} />
                )}
                {
                  [
                    "Book an appointment",
                    "Explore availability",
                    "Services & pricing",
                  ][i]
                }
                <ArrowRight size={12} />
              </button>
            ))}
          </div>
          <footer>
            <span>
              <AudioLines size={13} />
              Built for conversations. Designed for clarity.
            </span>
            <button onClick={() => setShowServices(!showServices)}>
              Northline Studio <ChevronRight size={12} />
            </button>
          </footer>
        </main>
      </div>
    </div>
  );
}

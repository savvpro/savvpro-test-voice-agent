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
  PanelLeftClose,
  PanelLeftOpen,
  RotateCcw,
  Scissors,
  ShieldCheck,
  Sparkles,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Business, Conversation, PendingTurn } from "@/lib/types";
import { useVoice } from "@/lib/use-voice";
import { createSessionCache } from "@/lib/session-cache";
import { AppointmentCard } from "@/components/appointment-card";
import { ThemeToggle } from "@/components/theme-toggle";
import { StudioServices } from "@/components/studio-services";

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
  const [speechLanguage, setSpeechLanguage] = useState("en-US");
  const [traceOpen, setTraceOpen] = useState(false);
  const [activeView, setActiveView] = useState<
    "voice" | "appointment" | "services"
  >("voice");
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const messageList = useRef<HTMLDivElement>(null);
  const messageInput = useRef<HTMLInputElement>(null);
  const restoreInputFocus = useRef(false);
  const locked = useRef(true);
  const latest = useRef<Conversation | null>(null);
  const sendRef = useRef<(text: string) => void>(() => {});
  const voice = useVoice((text) => sendRef.current(text), speechLanguage);

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
    list?.scrollTo({
      top: list.scrollHeight,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  }, [conversation?.revision, busy, voice.interim]);

  useEffect(() => {
    if (!busy && !pending && restoreInputFocus.current) {
      messageInput.current?.focus({ preventScroll: true });
      restoreInputFocus.current = false;
    }
  }, [busy, pending]);

  const submit = useCallback(
    async (text: string, retry?: PendingTurn) => {
      const current = latest.current;
      if (!text.trim() || locked.current || !current || (pending && !retry))
        return;
      restoreInputFocus.current = Boolean(
        document.activeElement?.closest(".composer"),
      );
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

  const showingInspector = activeView === "voice" && inspectorOpen;
  function toggleInspector() {
    setActiveView("voice");
    setInspectorOpen(!showingInspector);
  }

  return (
    <div
      className={`app-shell ${navigationOpen ? "navigation-expanded" : "navigation-collapsed"}`}
    >
      <aside
        id="workspace-navigation"
        className="rail"
        aria-label="Application"
      >
        <a className="brand-symbol" href="/" aria-label="VoxDesk home">
          <span className="brand-icon">
            <AudioLines size={23} />
          </span>
          <span className="brand-copy">
            voxdesk<small>WORKSPACE</small>
          </span>
        </a>
        <button
          className="rail-toggle"
          aria-label={
            navigationOpen ? "Collapse navigation" : "Expand navigation"
          }
          title={navigationOpen ? "Collapse navigation" : "Expand navigation"}
          aria-expanded={navigationOpen}
          aria-controls="workspace-navigation"
          onClick={() => setNavigationOpen(!navigationOpen)}
        >
          {navigationOpen ? (
            <PanelLeftClose size={18} />
          ) : (
            <PanelLeftOpen size={18} />
          )}
          <span>Collapse sidebar</span>
        </button>
        <div className="rail-rule" />
        <span className="rail-label">WORKSPACE</span>
        <button
          className={activeView === "voice" ? "rail-active" : "rail-button"}
          title="Voice receptionist"
          aria-label="Voice receptionist"
          aria-current={activeView === "voice" ? "page" : undefined}
          onClick={() => setActiveView("voice")}
        >
          <Headphones size={18} />
          <span>Voice receptionist</span>
        </button>
        <button
          className={
            activeView === "appointment" ? "rail-active" : "rail-button"
          }
          title="Your appointment"
          aria-label="View appointment"
          aria-current={activeView === "appointment" ? "page" : undefined}
          onClick={() => setActiveView("appointment")}
        >
          <CalendarDays size={18} />
          <span>Appointment</span>
        </button>
        <button
          className={activeView === "services" ? "rail-active" : "rail-button"}
          title="Studio services"
          onClick={() => {
            setActiveView("services");
            if (window.matchMedia("(max-width: 850px)").matches)
              setNavigationOpen(false);
          }}
          aria-label="View studio services"
          aria-current={activeView === "services" ? "page" : undefined}
        >
          <Scissors size={18} />
          <span>Studio services</span>
        </button>
        <div className="rail-bottom">
          <span className="avatar-small">NL</span>
          <span className="studio-copy">
            Northline Studio<small>YOUR FRONT DESK</small>
          </span>
        </div>
      </aside>
      {navigationOpen && (
        <button
          className="navigation-backdrop"
          aria-label="Close navigation"
          onClick={() => setNavigationOpen(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-navigation-toggle"
            aria-label={
              navigationOpen ? "Collapse navigation" : "Expand navigation"
            }
            aria-expanded={navigationOpen}
            aria-controls="workspace-navigation"
            onClick={() => setNavigationOpen(!navigationOpen)}
          >
            <PanelLeftOpen size={18} />
          </button>
          <div className="wordmark">
            Northline Studio<span className="version">Voice workspace</span>
          </div>
          <div className="topbar-right">
            <span className="connection-status">
              <span
                className={`status-dot ${connection === "online" ? "" : "offline"}`}
              />
              <span className="connection-copy">
                {connection === "online"
                  ? "Backend connected"
                  : connection === "connecting"
                    ? "Connecting to backend"
                    : "Backend unavailable"}
              </span>
            </span>
            <button
              className="icon-button mobile-view-toggle"
              aria-label={
                activeView === "voice"
                  ? "View appointment"
                  : "Voice receptionist"
              }
              title={
                activeView === "voice"
                  ? "View appointment"
                  : "Voice receptionist"
              }
              onClick={() =>
                setActiveView(activeView === "voice" ? "appointment" : "voice")
              }
            >
              {activeView === "voice" ? (
                <CalendarDays size={18} />
              ) : (
                <Headphones size={18} />
              )}
            </button>
            <ThemeToggle />
            <button
              className="button secondary new-session"
              aria-label="New session"
              title="Start a new session"
              disabled={busy || Boolean(pending)}
              onClick={() => void initialize(true)}
            >
              <RotateCcw size={14} />
              <span>New session</span>
            </button>
          </div>
        </header>
        <main className={showingInspector ? "with-inspector" : undefined}>
          <section className="page-heading">
            <div>
              <h1>
                {activeView === "voice"
                  ? "Voice receptionist"
                  : activeView === "services"
                    ? "Studio services"
                    : "Your appointment"}
              </h1>
              <p>
                {activeView === "voice" ? (
                  <>
                    <span
                      className={`status-dot ${voice.listening ? "pulse" : ""}`}
                    />
                    <span className="conversation-status">{status}</span>
                    <span aria-hidden="true">·</span>
                    {conversation
                      ? `${conversation.revision} turns`
                      : "Starting session"}
                  </>
                ) : activeView === "services" ? (
                  business ? (
                    `${business.name} · ${business.hours} · ${business.timezone}`
                  ) : (
                    "Loading studio details…"
                  )
                ) : (
                  "Your draft and saved appointment, in one place."
                )}
              </p>
            </div>
            <button
              className="icon-button inspector-toggle"
              aria-label={
                showingInspector
                  ? "Collapse decision inspector"
                  : "Expand decision inspector"
              }
              title={
                showingInspector
                  ? "Collapse decision inspector"
                  : "Expand decision inspector"
              }
              aria-expanded={showingInspector}
              aria-controls="decision-inspector-panel"
              onClick={toggleInspector}
              hidden={activeView === "services"}
            >
              <span>Decision inspector</span>
              <ChevronRight size={19} className="inspector-arrow" />
            </button>
          </section>

          <div
            className={`main-grid ${inspectorOpen ? "inspector-expanded" : "inspector-collapsed"}`}
            hidden={activeView !== "voice"}
          >
            <section
              className="conversation-panel panel"
              aria-label="Voice conversation"
            >
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
                      {message.role === "assistant" &&
                        i === conversation.history.length - 1 &&
                        decision?.matched_rule === "commit.confirmed" &&
                        conversation.appointment && (
                          <section
                            className="conversation-receipt"
                            aria-label="Latest appointment receipt"
                          >
                            <dl>
                              <div>
                                <dt>Reference</dt>
                                <dd>
                                  <code>
                                    {conversation.appointment.reference}
                                  </code>
                                </dd>
                              </div>
                              <div>
                                <dt>Service</dt>
                                <dd>{conversation.appointment.service_name}</dd>
                              </div>
                              <div>
                                <dt>Customer</dt>
                                <dd>
                                  {conversation.appointment.customer_name}
                                </dd>
                              </div>
                              <div>
                                <dt>Date</dt>
                                <dd>
                                  {conversation.appointment.starts_at.slice(
                                    0,
                                    10,
                                  )}{" "}
                                  ·{" "}
                                  {conversation.appointment.starts_at.slice(
                                    11,
                                    16,
                                  )}
                                </dd>
                              </div>
                              <div>
                                <dt>Status</dt>
                                <dd>
                                  <span className="receipt-status">
                                    {conversation.appointment.status}
                                  </span>
                                </dd>
                              </div>
                            </dl>
                            <small>
                              All times in {conversation.appointment.timezone}.
                              Please keep your reference.
                            </small>
                          </section>
                        )}
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
                {Boolean(conversation?.available_slots.length) && (
                  <section className="panel availability-card">
                    <div className="mini-label">
                      AVAILABLE STARTS · {entities?.date}
                    </div>
                    <div className="slot-list">
                      {conversation?.available_slots.map((slot) => (
                        <button
                          key={slot}
                          disabled={disabled}
                          aria-label={`Book at ${slot}`}
                          onClick={() => {
                            const [hour, minute] = slot.split(":").map(Number);
                            void submit(
                              `book it at ${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`,
                            );
                          }}
                        >
                          {slot}
                        </button>
                      ))}
                    </div>
                    <p>Availability can change until a booking is confirmed.</p>
                  </section>
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
                {conversation?.revision === 0 && !pending && (
                  <section
                    className="quick-start"
                    aria-label="Conversation suggestions"
                  >
                    {[
                      "Check beard trim availability Friday",
                      "What are your services and prices?",
                    ].map((text, i) => (
                      <button
                        key={text}
                        disabled={disabled}
                        onClick={() => void submit(text)}
                      >
                        {i === 0 ? (
                          <Clock3 size={13} />
                        ) : (
                          <CircleHelp size={13} />
                        )}
                        {["Explore availability", "Services & pricing"][i]}
                        <ArrowRight size={12} />
                      </button>
                    ))}
                  </section>
                )}
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
                    ref={messageInput}
                    aria-label="Your message"
                    placeholder="Type a message, or tap the mic to speak"
                    value={draft}
                    maxLength={1000}
                    onChange={(e) => setDraft(e.target.value)}
                    disabled={disabled}
                  />
                  <div className="composer-tools">
                    <button
                      type="button"
                      className="composer-tool"
                      onClick={() => {
                        setVoiceEnabled(!voiceEnabled);
                        voice.stopSpeaking();
                      }}
                      aria-pressed={voiceEnabled}
                      aria-label={`Spoken replies ${voiceEnabled ? "on" : "off"}`}
                      title={`Spoken replies ${voiceEnabled ? "on" : "off"}`}
                      disabled={!voice.canSpeak}
                    >
                      {voiceEnabled ? (
                        <Volume2 size={19} />
                      ) : (
                        <VolumeX size={19} />
                      )}
                    </button>
                    <button
                      type="button"
                      className="composer-tool"
                      aria-label="Listen again"
                      title="Listen again"
                      disabled={
                        !voice.canSpeak ||
                        busy ||
                        !conversation ||
                        voice.speaking
                      }
                      onClick={() =>
                        conversation && voice.speak(conversation.reply)
                      }
                    >
                      <AudioLines size={19} />
                    </button>
                    <button
                      type="button"
                      className={`mic-button ${voice.listening ? "listening" : ""}`}
                      aria-label={
                        voice.listening ? "Stop microphone" : "Start microphone"
                      }
                      title={
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
                        <Square size={18} fill="currentColor" />
                      ) : (
                        <Mic size={21} />
                      )}
                    </button>
                  </div>
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
                  <div className="composer-options">
                    <span className="mic-hint">
                      {voice.listening
                        ? "Listening… tap to stop"
                        : voice.speaking
                          ? "Speaking… microphone paused"
                          : voice.supported
                            ? "Tap to speak · one turn at a time"
                            : "Use typed input · voice unavailable"}
                    </span>
                    <label className="language-setting">
                      <span className="sr-only">Speech language</span>
                      <select
                        aria-label="Speech language"
                        value={speechLanguage}
                        disabled={busy || voice.listening || voice.speaking}
                        onChange={(event) =>
                          setSpeechLanguage(event.target.value)
                        }
                      >
                        <option value="en-US">English (US)</option>
                        <option value="en-GB">English (UK)</option>
                        <option value="en-PK">English (Pakistan)</option>
                      </select>
                    </label>
                    {voice.speaking && (
                      <button
                        type="button"
                        className="stop-audio"
                        onClick={voice.stopSpeaking}
                      >
                        <Square size={12} /> Stop audio
                      </button>
                    )}
                  </div>
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

            <aside
              id="decision-inspector-panel"
              className="inspector-column"
              aria-label="Decision inspector"
              aria-hidden={!inspectorOpen}
              inert={!inspectorOpen}
            >
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
            </aside>
          </div>
          <section
            className="appointment-view"
            aria-label="Appointment workspace"
            hidden={activeView !== "appointment"}
          >
            <div className="appointment-view-intro">
              <div>
                <span className="eyebrow">APPOINTMENT DETAILS</span>
                <h2>Everything for your next visit.</h2>
                <p>
                  Review your draft or saved receipt here. Confirmations and
                  changes happen in the conversation.
                </p>
              </div>
              <button
                className="button secondary"
                onClick={() => setActiveView("voice")}
              >
                <Headphones size={16} /> Back to conversation
              </button>
            </div>
            <AppointmentCard conversation={conversation} business={business} />

            <div className="rules-note">
              <ShieldCheck size={16} />
              <p>
                <strong>Code makes the call.</strong>Deterministic Python rules.
                No LLM decisions. No API keys.
              </p>
            </div>
          </section>
          <StudioServices
            business={business}
            hidden={activeView !== "services"}
            disabled={disabled}
            onStart={() => {
              setActiveView("voice");
              requestAnimationFrame(() =>
                messageInput.current?.focus({ preventScroll: true }),
              );
            }}
            onBook={(service) => {
              setActiveView("voice");
              void submit(`Book ${service.name}`);
            }}
          />
          <footer>
            <span>
              <span className="synthetic-tag">
                <ShieldCheck size={11} /> Synthetic demo
              </span>
              Built for conversations. Designed for clarity.
            </span>
            <button onClick={() => setActiveView("services")}>
              Northline Studio <ChevronRight size={12} />
            </button>
          </footer>
        </main>
      </div>
    </div>
  );
}

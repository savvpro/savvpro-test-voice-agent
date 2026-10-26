"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getConversation, sendMessage, startConversation } from "../lib/api";
import { useSpeech } from "../hooks/useSpeech";

const RESTAURANT_NAME = "La Bella Tavola";

const FLOW_STEPS = [
  { key: "ask_date", label: "Date" },
  { key: "ask_time", label: "Time" },
  { key: "ask_party_size", label: "Party size" },
  { key: "ask_name", label: "Name" },
  { key: "confirm", label: "Confirm" },
  { key: "booked", label: "Booked" },
];

function formatDate(iso) {
  if (!iso) return null;
  try {
    return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function formatTime(iso) {
  if (!iso) return null;
  const [h, m] = iso.split(":");
  const date = new Date();
  date.setHours(Number(h), Number(m || 0), 0, 0);
  return date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function stepStatus(stepKey, currentState) {
  const order = FLOW_STEPS.map((s) => s.key);
  const currentIdx = order.indexOf(currentState);
  const stepIdx = order.indexOf(stepKey);

  if (currentState === "cancelled") return "cancelled";
  if (currentState === "booked" || currentState === "goodbye") {
    return stepIdx <= order.indexOf("booked") ? "completed" : "";
  }
  if (stepIdx < currentIdx) return "completed";
  if (stepIdx === currentIdx) return "current";
  return "";
}

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [stateInfo, setStateInfo] = useState(null);
  const [decisionLog, setDecisionLog] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [connected, setConnected] = useState(null);

  const appendMessage = useCallback((role, text) => {
    setMessages((prev) => [...prev, { id: `${Date.now()}-${Math.random()}`, role, text }]);
  }, []);

  const refreshDecisions = useCallback(async (convId) => {
    if (!convId) return;
    const detail = await getConversation(convId);
    const entries = detail.turns
      .filter((t) => t.role === "user" && t.extracted)
      .map((t) => ({
        text: t.text,
        intents: t.extracted?.intents || [],
        entities: t.extracted?.entities || {},
        state: t.state,
      }));
    setDecisionLog(entries.slice(-8));
  }, []);

  const handleAssistantReply = useCallback(
    async (convId, responseText, state) => {
      appendMessage("assistant", responseText);
      setStateInfo(state);
      await refreshDecisions(convId);
      return responseText;
    },
    [appendMessage, refreshDecisions],
  );

  const speakRef = useRef(null);
  const conversationIdRef = useRef(conversationId);
  useEffect(() => { conversationIdRef.current = conversationId; }, [conversationId]);

  const processUserText = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      setError(null);
      appendMessage("user", trimmed);
      setInput("");
      setLoading(true);

      try {
        let convId = conversationIdRef.current;
        if (!convId) {
          const start = await startConversation();
          convId = start.conversation_id;
          setConversationId(convId);
          conversationIdRef.current = convId;
          setStateInfo(start.state);
        }

        const result = await sendMessage(convId, trimmed);
        speakRef.current?.(result.response);
        await handleAssistantReply(convId, result.response, result.state);
      } catch (err) {
        setError(err.message || "Something went wrong");
        setConnected(false);
      } finally {
        setLoading(false);
      }
    },
    [appendMessage, handleAssistantReply, loading],
  );

  const {
    listening,
    isSpeaking,
    interimTranscript,
    speechSupported,
    ttsEnabled,
    setTtsEnabled,
    speak,
    startListening,
    stopListening,
  } = useSpeech({ onTranscript: processUserText, enabled: !loading });

  const messagesContainerRef = useRef(null);

  useEffect(() => {
    speakRef.current = speak;
  }, [speak]);

  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, loading]);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      setLoading(true);
      setError(null);
      try {
        const start = await startConversation();
        if (cancelled) return;
        setConnected(true);
        setConversationId(start.conversation_id);
        setStateInfo(start.state);
        setMessages([{ id: "greeting", role: "assistant", text: start.response }]);
        if (typeof window !== "undefined" && window.speechSynthesis) {
          const utterance = new SpeechSynthesisUtterance(start.response);
          window.speechSynthesis.speak(utterance);
        }
      } catch (err) {
        if (!cancelled) {
          setConnected(false);
          setError(
            err.message ||
              "Cannot reach the backend. Start it with: cd backend && uvicorn main:app --reload",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  const resetConversation = async () => {
    setLoading(true);
    setError(null);
    setMessages([]);
    setDecisionLog([]);
    stopListening();
    try {
      const start = await startConversation();
      setConnected(true);
      setConversationId(start.conversation_id);
      setStateInfo(start.state);
      appendMessage("assistant", start.response);
      speak(start.response);
    } catch (err) {
      setConnected(false);
      setError(err.message || "Failed to start a new conversation");
    } finally {
      setLoading(false);
    }
  };

  const booking = stateInfo?.booking;
  const currentState = stateInfo?.state || "greeting";

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-brand">
          <div className="header-icon-badge">🍷</div>
          <div>
            <div className="header-title-row">
              <h1>{RESTAURANT_NAME}</h1>
              <span className="header-tag">Voice Concierge</span>
            </div>
            <p className="header-sub">Fine Dining Reservations • Conversational Assistant</p>
          </div>
        </div>

        <div className="header-actions">
          <div className={`connection-status ${connected ? "connected" : "disconnected"}`}>
            <span className="dot" aria-hidden />
            {connected === null ? "Connecting…" : connected ? "Backend online" : "Backend offline"}
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={resetConversation}
            disabled={loading}
            title="Start a new booking conversation"
          >
            ↺ New Reservation
          </button>
        </div>
      </header>

      <div className="main-content">
        <section className="glass-card conversation-panel" aria-label="Conversation">
          <div className="card-header">
            <span className="icon" aria-hidden>
              💬
            </span>
            <h2>Conversation</h2>
            <span className="chat-counter-badge">{messages.length} messages</span>
          </div>

          <div className="conversation-messages" ref={messagesContainerRef}>
            {messages.length === 0 && !loading && (
              <div className="empty-state">
                <span className="icon" aria-hidden>
                  🎙️
                </span>
                <p>Say hello or type a message to book a table.</p>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="message-header-line">
                  <span className="message-label">{msg.role === "user" ? "You" : "Assistant"}</span>
                  {msg.role === "assistant" && (
                    <button
                      type="button"
                      className="speaker-replay-btn"
                      onClick={() => speak(msg.text)}
                      title="Play voice"
                      aria-label="Play message audio"
                    >
                      🔊
                    </button>
                  )}
                </div>
                <div className="message-text">{msg.text}</div>
              </div>
            ))}

            {loading && (
              <div className="typing-indicator" aria-label="Assistant is thinking">
                <span />
                <span />
                <span />
              </div>
            )}
          </div>

          {error && (
            <p className="fade-in" style={{ padding: "0 1.5rem", color: "var(--error)", fontSize: "var(--font-sm)" }}>
              {error}
            </p>
          )}

          {listening && (
            <div className="voice-listening-bar fade-in">
              <span className={`voice-pulse-ring ${isSpeaking ? "speaking" : ""}`} />
              <div className="voice-status-content">
                <div className="voice-status-header">
                  <span className="voice-badge">
                    {isSpeaking ? "Listening…" : "Waiting for pause…"}
                  </span>
                  <span className="voice-subtext">
                    {isSpeaking
                      ? "Speak freely — I'll wait until you're done talking"
                      : "Silence detected — finishing up or press stop"}
                  </span>
                </div>
                {interimTranscript && (
                  <p className="voice-transcript-preview">
                    “{interimTranscript}”
                  </p>
                )}
              </div>
            </div>
          )}

          <div className="input-area">
            <button
              type="button"
              className={`mic-btn ${listening ? "listening" : ""}`}
              onClick={listening ? stopListening : startListening}
              disabled={!speechSupported || loading || connected === false}
              title={
                speechSupported
                  ? listening
                    ? "Stop listening"
                    : "Speak your message"
                  : "Speech recognition not supported in this browser"
              }
              aria-label={listening ? "Stop microphone" : "Start microphone"}
            >
              {listening ? "⏹" : "🎤"}
            </button>

            <input
              className="text-input"
              type="text"
              placeholder="Type or use the mic… e.g. tomorrow at 7pm for 4 people"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") processUserText(input);
              }}
              disabled={loading || connected === false}
              aria-label="Message input"
            />

            <button
              type="button"
              className="btn btn-primary btn-send"
              onClick={() => processUserText(input)}
              disabled={loading || !input.trim() || connected === false}
              aria-label="Send message"
            >
              ➤
            </button>
          </div>
        </section>

        <aside className="status-sidebar">
          <div className="glass-card">
            <div className="card-header">
              <span className="icon" aria-hidden>
                📋
              </span>
              <h2>Booking</h2>
            </div>
            <div className="booking-details">
              <div className="booking-field">
                <span className="field-label">Date</span>
                <span className={`field-value ${booking?.date ? "" : "empty"}`}>
                  {formatDate(booking?.date) || "Not set"}
                </span>
              </div>
              <div className="booking-field">
                <span className="field-label">Time</span>
                <span className={`field-value ${booking?.time ? "" : "empty"}`}>
                  {formatTime(booking?.time) || "Not set"}
                </span>
              </div>
              <div className="booking-field">
                <span className="field-label">Guests</span>
                <span className={`field-value ${booking?.party_size ? "" : "empty"}`}>
                  {booking?.party_size ?? "Not set"}
                </span>
              </div>
              <div className="booking-field">
                <span className="field-label">Name</span>
                <span className={`field-value ${booking?.guest_name ? "" : "empty"}`}>
                  {booking?.guest_name || "Not set"}
                </span>
              </div>
              <div className="booking-field">
                <span className="field-label">Status</span>
                <span className="field-value">{booking?.status?.replace("_", " ") || "pending"}</span>
              </div>
            </div>
          </div>

          <div className="glass-card">
            <div className="card-header">
              <span className="icon" aria-hidden>
                🧠
              </span>
              <h2>Brain state</h2>
            </div>
            <div className="state-indicator">
              <div className="state-badge-row">
                <span className="state-badge-title">Current Phase</span>
                <span
                  className={`state-badge ${
                    currentState === "booked" || currentState === "goodbye"
                      ? "confirmed"
                      : currentState === "cancelled"
                        ? "cancelled"
                        : "active"
                  }`}
                >
                  {currentState.replace(/_/g, " ")}
                </span>
              </div>
              <div className="state-steps">
                {FLOW_STEPS.map((step) => (
                  <div
                    key={step.key}
                    className={`state-step ${stepStatus(step.key, currentState)}`}
                  >
                    <span className="step-dot" />
                    <span className="step-name">{step.label}</span>
                    {stepStatus(step.key, currentState) === "completed" && (
                      <span className="step-status-tag done">✓</span>
                    )}
                    {stepStatus(step.key, currentState) === "current" && (
                      <span className="step-status-tag active">active</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="glass-card">
            <div className="card-header">
              <span className="icon" aria-hidden>
                🔍
              </span>
              <h2>Decisions</h2>
            </div>
            <div className="decision-log">
              {decisionLog.length === 0 && (
                <p style={{ color: "var(--text-muted)", fontSize: "var(--font-xs)" }}>
                  Intent and entity tags appear here after each of your turns.
                </p>
              )}
              {decisionLog.map((entry, idx) => (
                <div key={`${entry.text}-${idx}`} className="decision-entry">
                  <div style={{ marginBottom: "0.25rem" }}>&ldquo;{entry.text}&rdquo;</div>
                  {entry.intents.map((intent) => (
                    <span key={intent} className="intent-tag">
                      {intent}
                    </span>
                  ))}
                  {Object.entries(entry.entities).map(([key, value]) => (
                    <span key={key} className="entity-tag">
                      {key}: {value}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card voice-settings-card">
            <div className="card-header">
              <span className="icon" aria-hidden>
                ⚙️
              </span>
              <h2>Controls & Audio</h2>
            </div>
            <div className="voice-settings-body">
              <div className="settings-row">
                <label className="settings-toggle-label">
                  <input
                    type="checkbox"
                    checked={ttsEnabled}
                    onChange={(e) => setTtsEnabled(e.target.checked)}
                  />
                  <span>Speak assistant replies</span>
                </label>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => speak("Hello! Voice output is working perfectly.")}
                  title="Test audio through your speakers"
                >
                  🔊 Test
                </button>
              </div>

              <button
                type="button"
                className="btn btn-new-conv"
                onClick={resetConversation}
                disabled={loading}
                title="Start a new booking conversation"
              >
                ↺ New Conversation
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

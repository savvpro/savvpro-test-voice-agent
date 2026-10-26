import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api/client";
import type { ApiClient } from "../api/client";
import { useConversation } from "../features/conversation/useConversation";
import { CaseSummary } from "../features/conversation/CaseSummary";
import { DecisionInspector } from "../features/decision-inspector/DecisionInspector";
import { Icon } from "./Icon";
import { useSpeech } from "../speech/useSpeech";
import { VoiceControls } from "../features/conversation/VoiceControls";

export function App({ client = api }: { client?: ApiClient }) {
  const conversation = useConversation(client);
  const { session, busy, error, hasRetry } = conversation;
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const speech = useSpeech({
    onTranscript: (transcript) => {
      setText(transcript);
      void conversation.send(transcript).then((sent) => {
        if (sent) setText("");
      });
    },
    reply: session?.reply || "",
    version: session?.version ?? 0,
    busy,
  });
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [session?.version]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    speech.stop();
    if (await conversation.send(text)) {
      setText("");
      input.current?.focus();
    }
  };
  const step =
    session?.state === "completed"
      ? 3
      : session?.state === "confirming"
        ? 2
        : session?.candidates.length
          ? 1
          : 0;
  return (
    <div className="app-shell" data-ui>
      <a className="skip-link" href="#conversation">
        Skip to conversation
      </a>
      <header className="topbar">
        <a
          className="brand"
          href="#conversation"
          aria-label="Riverside Mall lost property"
        >
          <Icon name="river" size={32} />
          <span>
            riverside<span className="brand-sub">MALL · GUEST SERVICES</span>
          </span>
        </a>
        <div className="topbar-meta">
          <span>Lost-property desk</span>
          <span className="demo-label">Interactive demo</span>
        </div>
      </header>
      <aside className="sidebar" aria-label="How it works">
        <div className="sidebar-heading">Here to help.</div>
        <p>
          A familiar place.
          <br />A helping hand.
        </p>
        <ol className="journey">
          {[
            "Describe your item",
            "Narrow the search",
            "Review the next step",
            "Keep your reference",
          ].map((label, index) => (
            <li
              key={label}
              className={
                step === index ? "current" : step > index ? "done" : ""
              }
            >
              <span className="step-number">
                {step > index ? (
                  <Icon name="check" size={14} />
                ) : (
                  String(index + 1).padStart(2, "0")
                )}
              </span>
              <span>{label}</span>
            </li>
          ))}
        </ol>
        <div className="sidebar-bottom">
          <span>Privacy comes first</span>
          <p>
            Use fictional details only.
            <br />
            Please don't share personal information.
          </p>
          <a href="#desk-info">
            About the information desk <Icon name="arrow" size={16} />
          </a>
        </div>
      </aside>
      <main className="sheet" id="conversation">
        <div className="page-heading">
          <div>
            <div className="eyebrow">Riverside Mall / Guest services</div>
            <h1>Lost something?</h1>
            <p>Let's take it one detail at a time.</p>
          </div>
          <button
            className="quiet-button"
            disabled={busy || !session}
            onClick={() => {
              speech.stop();
              setText("");
              void conversation.erase();
            }}
          >
            New conversation <span aria-hidden="true">↗</span>
          </button>
        </div>
        <div className="workspace">
          <section
            className="conversation-panel"
            aria-label="Lost-property conversation"
          >
            <div className="conversation-header">
              <div>
                <span className="status-dot" />
                <h2>Riverside assistant</h2>
              </div>
              <span className="conversation-status">
                {busy
                  ? "Connecting…"
                  : session?.state === "completed"
                    ? "Request recorded"
                    : session?.state === "cancelled"
                      ? "Conversation ended"
                      : "Ready to listen"}
              </span>
            </div>
            <div
              className="messages"
              role="log"
              aria-label="Conversation transcript"
              aria-live="polite"
              aria-relevant="additions"
            >
              {!session && !error && (
                <p className="connecting">
                  Connecting to the lost-property desk…
                </p>
              )}
              {session?.transcript.map((message, index) => (
                <article
                  className={`message ${message.role}`}
                  key={`${index}-${message.role}`}
                >
                  <span className="message-speaker">
                    {message.role === "assistant" ? "Riverside" : "You"}
                  </span>
                  <p>{message.text}</p>
                </article>
              ))}
              {busy && session && (
                <p className="thinking" role="status">
                  Checking your details<span aria-hidden="true">…</span>
                </p>
              )}
              <div ref={end} />
            </div>
            {session?.candidates.length && session.state !== "completed" ? (
              <div className="candidate-list" aria-label="Possible matches">
                <span className="section-label">
                  Possible matches · staff verification required
                </span>
                {session.candidates.map((candidate) => (
                  <div className="candidate" key={candidate.label}>
                    <Icon name={candidate.category} />
                    <div>
                      <strong>{candidate.label}</strong>
                      <p>{candidate.description}</p>
                    </div>
                    <button
                      disabled={busy || hasRetry}
                      onClick={() => void conversation.send(candidate.label)}
                    >
                      Consider this <Icon name="arrow" size={16} />
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
            {session?.receipt && (
              <section className="receipt" aria-label="Your saved reference">
                <Icon name="check" />
                <div>
                  <span>
                    {session.receipt.kind === "claim"
                      ? "Pending staff review"
                      : "Lost-item report recorded"}
                  </span>
                  <strong>{session.receipt.reference}</strong>
                  <p>Keep this reference for the information desk.</p>
                </div>
              </section>
            )}
            {error && (
              <div className="error-banner" role="alert">
                <p>{error.message}</p>
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() =>
                    void (hasRetry ? conversation.retry() : conversation.open())
                  }
                >
                  {hasRetry ? "Retry message" : "Reconnect"}
                </button>
              </div>
            )}
            <VoiceControls
              speech={speech}
              disabled={
                busy || !session || hasRetry || session.state === "cancelled"
              }
            />
            <form className="composer" onSubmit={(event) => void submit(event)}>
              <label htmlFor="message">Your message</label>
              <div className="input-wrap">
                <textarea
                  ref={input}
                  id="message"
                  maxLength={1000}
                  rows={2}
                  placeholder="For example, I lost a black backpack near the food court yesterday…"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  disabled={busy || !session || hasRetry}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void submit(event);
                    }
                  }}
                />
                <button
                  className="send-button"
                  type="submit"
                  aria-label="Send message"
                  disabled={busy || !text.trim() || !session || hasRetry}
                >
                  <Icon name="arrow" />
                </button>
              </div>
              <div className="composer-bottom">
                <span>Enter to send · Shift + Enter for a new line</span>
                <button
                  className="text-button"
                  type="button"
                  disabled={busy || !session || session.state === "cancelled"}
                  onClick={() => {
                    speech.stop();
                    void conversation.send("cancel");
                  }}
                >
                  End conversation
                </button>
              </div>
            </form>
            <DecisionInspector session={session} />
          </section>
          <CaseSummary session={session} />
        </div>
        <footer className="sheet-footer">
          <span>Every item has a story. Let's find yours.</span>
          <span>Riverside · Lost property</span>
        </footer>
      </main>
    </div>
  );
}

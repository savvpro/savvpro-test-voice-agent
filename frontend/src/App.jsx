
import { useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

function Icon({ name, className = "h-5 w-5" }) {
  const paths = {
    phone: <><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.12 4.2 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.96.35 1.9.68 2.8a2 2 0 0 1-.45 2.11L8.07 9.93a16 16 0 0 0 6 6l1.3-1.27a2 2 0 0 1 2.11-.45c.9.33 1.84.56 2.8.68A2 2 0 0 1 22 16.92Z" /></>,
    mic: <><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10a7 7 0 0 0 14 0M12 19v3m-4 0h8" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 11h18" /></>,
    activity: <><path d="M3 12h4l3-9 4 18 3-9h4" /></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>,
    clock: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.6 9A7 7 0 0 1 17.5 6L20 12M4 12l2.5 6A7 7 0 0 0 18.4 15" /></>,
    sparkle: <><path d="m12 3 2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2L12 3Z" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    message: <><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z" /></>,
  };

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

function Panel({ children, className = "" }) {
  return (
    <section className={`rounded-2xl border border-slate-200/80 bg-white shadow-[0_4px_24px_rgba(15,23,42,0.035)] ${className}`}>
      {children}
    </section>
  );
}

function Heading({ icon, title, subtitle, right }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <div className="rounded-xl bg-teal-50 p-2.5 text-teal-700">
          <Icon name={icon} />
        </div>
        <div className="min-w-0">
          <h2 className="truncate text-sm font-bold text-slate-800 sm:text-base">{title}</h2>
          <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
        </div>
      </div>
      {right}
    </div>
  );
}

export default function App() {
  const [sid, setSid] = useState(null);
  const [log, setLog] = useState([]);
  const [info, setInfo] = useState(null);
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ended = Boolean(info?.done);

  const speak = (message) => {
    if (!("speechSynthesis" in window) || !message) return;

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(
      new SpeechSynthesisUtterance(message)
    );
  };

  const apply = (data, said) => {
    setInfo(data);
    setLog((previous) => [
      ...previous,
      ...(said !== undefined
        ? [{ who: "You", text: said || "(silence)" }]
        : []),
      {
        who: "Agent",
        text: data.reply || "I couldn't generate a response.",
      },
    ]);

    speak(data.reply);
  };

  const post = async (path, body = {}) => {
    const response = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `Request failed (${response.status})`);
    }

    return data;
  };

  const start = async () => {
    setLoading(true);
    setError("");

    try {
      window.speechSynthesis?.cancel();

      const data = await post("/sessions");

      setSid(data.session_id);
      setLog([]);
      setInfo(null);
      setText("");

      apply(data);
    } catch (err) {
      setError(err.message || "Could not start the session. Check the backend.");
    } finally {
      setLoading(false);
    }
  };

  const send = async (message) => {
    if (!sid || loading || ended) return;

    setLoading(true);
    setError("");

    try {
      const data = await post(`/sessions/${sid}/turn`, {
        text: message,
      });

      apply(data, message);
    } catch (err) {
      setError(err.message || "Message failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const listen = () => {
    const Recognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!Recognition) {
      setError("Speech recognition isn't supported here. Please type instead.");
      return;
    }

    const recognition = new Recognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setText(transcript);
      send(transcript);
    };

    recognition.onerror = (event) => {
      if (event.error !== "aborted") {
        setError(`Microphone error: ${event.error}. You can type instead.`);
      }
    };

    recognition.onend = () => setListening(false);

    setError("");
    setListening(true);

    try {
      recognition.start();
    } catch {
      setListening(false);
      setError("Couldn't start the microphone. Please try again.");
    }
  };

  const submit = (event) => {
    event.preventDefault();

    const message = text.trim();
    if (!message || !sid || ended || loading) return;

    setText("");
    send(message);
  };

  const reset = () => {
    window.speechSynthesis?.cancel();
    setSid(null);
    setLog([]);
    setInfo(null);
    setText("");
    setError("");
    setListening(false);
  };

  const slots = info?.slots || {};
  const captured = Object.values(slots).filter(
    (value) => value !== null && value !== undefined && value !== ""
  ).length;

  return (
    <div className="min-h-screen bg-[#f5f8fb] text-slate-800">
      {/* Navigation */}
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-700 text-white shadow-md shadow-teal-900/15">
              <Icon name="activity" className="h-5 w-5" />
            </div>
            <div>
              <p className="text-base font-extrabold tracking-tight text-slate-900">
                Care<span className="text-teal-700">Connect</span>
              </p>
              <p className="hidden text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400 sm:block">
                Voice assistant platform
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2">
            <span className={`h-2 w-2 rounded-full ${sid ? "bg-emerald-500" : "bg-slate-300"}`} />
            <span className="text-xs font-semibold text-slate-600">
              {sid ? "Session active" : "System ready"}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-9 lg:px-8">
        {/* Hero */}
        <section className="relative mb-7 overflow-hidden rounded-3xl bg-gradient-to-br from-[#0d3c43] via-[#11545a] to-[#13776f] px-5 py-7 text-white sm:px-8 sm:py-9 lg:px-10">
          <div className="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full border-[40px] border-white/[0.045]" />
          <div className="pointer-events-none absolute -bottom-32 right-1/4 h-64 w-64 rounded-full bg-teal-300/[0.08] blur-3xl" />

          <div className="relative grid gap-7 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.08] px-3 py-1.5 text-xs font-medium text-teal-100">
                <Icon name="sparkle" className="h-3.5 w-3.5" />
                SMART CLINIC AUTOMATION
              </div>

              <h1 className="max-w-2xl text-3xl font-bold leading-tight tracking-tight sm:text-4xl lg:text-[42px]">
                Better conversations.
                <br />
                <span className="text-teal-200">Simpler appointments.</span>
              </h1>

              <p className="mt-4 max-w-xl text-sm leading-6 text-teal-50/75 sm:text-base">
                Your virtual clinic receptionist can book, reschedule, and
                cancel appointments through natural conversation.
              </p>

              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  onClick={start}
                  disabled={loading}
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-bold text-teal-900 shadow-lg transition hover:bg-teal-50 disabled:opacity-60"
                >
                  <Icon name="phone" className="h-4 w-4" />
                  {loading ? "Connecting..." : sid ? "Start new call" : "Start a conversation"}
                </button>

                {sid && (
                  <button
                    onClick={reset}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/[0.07] px-4 py-3 text-sm font-medium text-white transition hover:bg-white/15"
                  >
                    <Icon name="refresh" className="h-4 w-4" />
                    Reset
                  </button>
                )}
              </div>
            </div>

            <div className="hidden min-w-52 rounded-2xl border border-white/15 bg-white/[0.07] p-5 backdrop-blur-sm sm:block">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-200/15 text-teal-100">
                <Icon name="calendar" className="h-6 w-6" />
              </div>
              <p className="text-xs font-medium text-teal-100/70">CONVERSATION STATUS</p>
              <p className="mt-1 text-xl font-bold">
                {ended ? "Completed" : sid ? "In progress" : "Ready to begin"}
              </p>
              <p className="mt-2 text-xs leading-5 text-teal-50/65">
                {sid
                  ? "Your session is ready for the next message."
                  : "Start a session to begin helping a patient."}
              </p>
            </div>
          </div>
        </section>

        {/* Feature cards */}
        <div className="mb-7 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            {
              icon: "calendar",
              title: "Appointment management",
              subtitle: "Book, reschedule and cancel",
              color: "bg-blue-50 text-blue-700",
            },
            {
              icon: "message",
              title: "Natural interaction",
              subtitle: "Voice and text conversations",
              color: "bg-teal-50 text-teal-700",
            },
            {
              icon: "shield",
              title: "Transparent decisions",
              subtitle: "Inspect state and decision trace",
              color: "bg-violet-50 text-violet-700",
            },
          ].map((item) => (
            <div
              key={item.title}
              className="flex items-center gap-3 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm shadow-slate-900/[0.02]"
            >
              <div className={`rounded-xl p-3 ${item.color}`}>
                <Icon name={item.icon} />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-800">{item.title}</p>
                <p className="mt-1 text-xs text-slate-500">{item.subtitle}</p>
              </div>
            </div>
          ))}
        </div>

        {error && (
          <div
            role="alert"
            className="mb-5 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
          >
            <span className="font-bold">!</span>
            <p className="flex-1">{error}</p>
            <button
              onClick={() => setError("")}
              aria-label="Dismiss error"
              className="font-bold text-rose-600"
            >
              ×
            </button>
          </div>
        )}

        {/* Workspace */}
        <div className="grid items-start gap-5 lg:grid-cols-[1.12fr_0.88fr]">
          {/* Conversation panel */}
          <Panel className="overflow-hidden">
            <Heading
              icon="message"
              title="Conversation workspace"
              subtitle="Interact with your virtual receptionist"
              right={
                sid ? (
                  <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold ${ended ? "bg-slate-100 text-slate-500" : "bg-emerald-50 text-emerald-700"}`}>
                    {ended ? "ENDED" : "LIVE"}
                  </span>
                ) : null
              }
            />

            <div
              className="min-h-[320px] space-y-5 bg-gradient-to-b from-white to-slate-50/70 p-4 sm:min-h-[400px] sm:p-6"
              aria-live="polite"
            >
              {log.length === 0 ? (
                <div className="flex min-h-[285px] flex-col items-center justify-center px-3 py-10 text-center">
                  <div className="mb-5 flex h-[76px] w-[76px] items-center justify-center rounded-3xl border border-teal-100 bg-teal-50 text-teal-700 shadow-sm">
                    <Icon name="mic" className="h-8 w-8" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-800">
                    Welcome to your clinic assistant
                  </h3>
                  <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
                    Start a call and tell the assistant what you need. You can
                    speak or type your message.
                  </p>
                  <div className="mt-5 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left">
                    <p className="text-xs font-semibold text-slate-500">DEMO PATIENT</p>
                    <p className="mt-1 text-sm font-bold text-teal-800">Sam Demo</p>
                  </div>
                </div>
              ) : (
                <>
                  {log.map((message, index) => {
                    const isUser = message.who === "You";

                    return (
                      <div
                        key={index}
                        className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}
                      >
                        <div
                          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-xs font-extrabold ${
                            isUser
                              ? "bg-blue-100 text-blue-700"
                              : "bg-teal-100 text-teal-800"
                          }`}
                        >
                          {isUser ? "YOU" : "AI"}
                        </div>

                        <div
                          className={`max-w-[88%] rounded-2xl px-4 py-3 sm:max-w-[82%] ${
                            isUser
                              ? "rounded-tr-sm border border-blue-100 bg-blue-50"
                              : "rounded-tl-sm border border-slate-200/80 bg-white shadow-sm shadow-slate-900/[0.02]"
                          }`}
                        >
                          <p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                            {isUser ? "You" : "Clinic assistant"}
                          </p>
                          <p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">
                            {message.text}
                          </p>
                        </div>
                      </div>
                    );
                  })}

                  {loading && (
                    <div className="flex items-center gap-3 text-sm text-slate-500">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
                        <Icon name="activity" className="h-4 w-4 animate-pulse" />
                      </div>
                      <span>Assistant is thinking...</span>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="border-t border-slate-100 bg-white p-4 sm:p-5">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <button
                  onClick={listen}
                  disabled={!sid || ended || listening || loading}
                  className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-40 ${
                    listening
                      ? "bg-rose-50 text-rose-700"
                      : "bg-teal-700 text-white shadow-sm hover:bg-teal-800"
                  }`}
                >
                  <Icon name="mic" className="h-4 w-4" />
                  {listening ? "Listening..." : "Speak"}
                </button>

                <button
                  onClick={() => send("")}
                  disabled={!sid || ended || loading}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Icon name="clock" className="h-4 w-4" />
                  Stay silent
                </button>
              </div>

              <form onSubmit={submit} className="flex gap-2">
                <input
                  aria-label="Type your message"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  disabled={!sid || ended || loading}
                  placeholder={sid ? "Type a message..." : "Start a call to begin"}
                  className="h-12 min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-teal-500 focus:bg-white focus:ring-4 focus:ring-teal-500/10 disabled:opacity-50"
                />

                <button
                  type="submit"
                  aria-label="Send message"
                  disabled={!sid || ended || !text.trim() || loading}
                  className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-35"
                >
                  <Icon name="send" className="h-4 w-4" />
                </button>
              </form>

              <p className="mt-3 text-[11px] leading-5 text-slate-400">
                Voice recognition requires browser support and microphone permission.
              </p>
            </div>
          </Panel>

          {/* Brain inspector */}
          <div className="space-y-5">
            <Panel className="overflow-hidden">
              <Heading
                icon="activity"
                title="Agent overview"
                subtitle="Live state and detected intent"
              />

              <div className="space-y-5 p-4 sm:p-6">
                <div className="rounded-2xl border border-teal-100 bg-gradient-to-br from-teal-50/80 to-white p-4 sm:p-5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-semibold uppercase tracking-wider text-teal-800/60">
                      Current state
                    </span>
                    <span className="flex items-center gap-1.5 text-xs font-semibold text-teal-800">
                      <span className={`h-2 w-2 rounded-full ${sid ? "bg-emerald-500" : "bg-slate-300"}`} />
                      {sid ? "Connected" : "Idle"}
                    </span>
                  </div>

                  <p className="mt-3 break-words text-xl font-extrabold tracking-tight text-slate-800">
                    {info?.state || "Awaiting session"}
                  </p>

                  <div className="mt-4 border-t border-teal-100 pt-3">
                    <p className="text-xs text-slate-500">Detected intent</p>
                    <span className="mt-2 inline-flex max-w-full break-words rounded-lg border border-teal-100 bg-white px-3 py-1.5 text-xs font-bold text-teal-800">
                      {info?.intent || "Not detected"}
                    </span>
                  </div>
                </div>

                <div>
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h3 className="text-sm font-bold text-slate-800">
                      Collected details
                    </h3>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                      {captured} captured
                    </span>
                  </div>

                  {Object.keys(slots).length > 0 ? (
                    <div className="space-y-2">
                      {Object.entries(slots).map(([key, value]) => {
                        const populated =
                          value !== null &&
                          value !== undefined &&
                          value !== "";

                        return (
                          <div
                            key={key}
                            className="flex items-start justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/70 px-3.5 py-3"
                          >
                            <span className="text-xs capitalize text-slate-500">
                              {key.replaceAll("_", " ")}
                            </span>

                            <span
                              className={`max-w-[65%] break-words text-right text-xs font-semibold ${
                                populated ? "text-slate-800" : "text-slate-400"
                              }`}
                            >
                              {populated ? String(value) : "Not provided"}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-200 px-4 py-8 text-center">
                      <Icon name="calendar" className="mx-auto mb-3 h-7 w-7 text-slate-300" />
                      <p className="text-sm font-semibold text-slate-600">
                        No details collected yet
                      </p>
                      <p className="mt-1 text-xs leading-5 text-slate-400">
                        Appointment information will appear here as the conversation progresses.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </Panel>

            <Panel className="overflow-hidden">
              <Heading
                icon="shield"
                title="Decision trace"
                subtitle="Processing steps recorded by the agent"
                right={
                  <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">
                    {info?.trace?.length || 0} steps
                  </span>
                }
              />

              <div className="p-4 sm:p-6">
                {info?.trace?.length ? (
                  <ol className="space-y-0">
                    {info.trace.map((step, index) => (
                      <li
                        key={`${index}-${step}`}
                        className="relative flex gap-3 pb-5 last:pb-0"
                      >
                        {index !== info.trace.length - 1 && (
                          <span className="absolute bottom-0 left-[13px] top-7 w-px bg-slate-200" />
                        )}

                        <span className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-teal-100 bg-teal-50 text-xs font-bold text-teal-800">
                          {index + 1}
                        </span>

                        <p className="break-words pt-1 text-sm leading-6 text-slate-600">
                          {step}
                        </p>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <div className="py-6 text-center">
                    <Icon name="activity" className="mx-auto mb-3 h-7 w-7 text-slate-300" />
                    <p className="text-sm font-semibold text-slate-600">
                      Waiting for activity
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">
                      Agent decisions will appear here during your session.
                    </p>
                  </div>
                )}
              </div>
            </Panel>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-8 flex flex-col gap-3 border-t border-slate-200 pt-5 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <p>CareConnect · Clinic Voice Agent Demo</p>
          <p className="flex items-center gap-2">
            <Icon name="shield" className="h-4 w-4 text-teal-700" />
            Session-based conversational engine
          </p>
        </footer>
      </main>
    </div>
  );
}
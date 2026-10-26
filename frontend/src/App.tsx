import { useEffect, useRef, useState } from "react";
import {
  CalendarDays,
  Mic,
  MicOff,
  Send,
  Utensils,
  RotateCcw,
  Volume2,
  VolumeX,
  ChevronDown,
  Play,
} from "lucide-react";

type Fields = {
  dining?: string;
  date?: string;
  time?: number;
  adults?: number;
  children?: number[];
  seating?: string;
  name?: string;
  phone?: string;
};
type Result = {
  session_id: string;
  message: string;
  quote: { total: number; deposit: number } | null;
  state: {
    fields: Fields;
    stage: string;
    rule: string;
    intent: string;
    awaiting: string | null;
    alternatives?: { time: number; seating: string }[];
    booking: { id: string; status: string; expires: string | null } | null;
  };
};
type Message = { role: "Mezban" | "You"; text: string };
type Recognition = {
  lang: string;
  interimResults: boolean;
  onresult: ((event: { results: { transcript: string }[][] }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};
const SpeechRecognition =
  (
    window as unknown as {
      SpeechRecognition?: new () => Recognition;
      webkitSpeechRecognition?: new () => Recognition;
    }
  ).SpeechRecognition ||
  (window as unknown as { webkitSpeechRecognition?: new () => Recognition })
    .webkitSpeechRecognition;

async function api(path: string, body?: unknown): Promise<Result> {
  const response = await fetch("/api/" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Unable to connect. Please check the backend and retry.",
    );
  }
  return response.json();
}

export default function App() {
  const [result, setResult] = useState<Result | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const [voice, setVoice] = useState(true);
  const [language, setLanguage] = useState("en-PK");
  const [manage, setManage] = useState(false);
  const [reference, setReference] = useState("");
  const [phone, setPhone] = useState("");
  const recognition = useRef<Recognition | null>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const request = useRef<{ text: string; request_id: string } | null>(null);
  const starting = useRef(false);
  function speak(message: string) {
    if (!voice || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(message);
    utterance.lang = "en-PK";
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  }
  async function start() {
    if (starting.current) return;
    starting.current = true;
    setBusy(true);
    setError("");
    recognition.current?.abort();
    window.speechSynthesis?.cancel();
    try {
      const next = await api("sessions");
      setResult(next);
      setMessages([{ role: "Mezban", text: next.message }]);
      request.current = null;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      starting.current = false;
      setBusy(false);
    }
  }
  useEffect(() => {
    void start();
    return () => {
      recognition.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, []);
  useEffect(() => {
    transcript.current?.scrollTo({
      top: transcript.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);
  async function send(value = text) {
    if (!value.trim() || busy || !result) return;
    recognition.current?.stop();
    setBusy(true);
    setError("");
    if (!request.current || request.current.text !== value)
      request.current = { text: value, request_id: crypto.randomUUID() };
    try {
      const next = await api(
        `sessions/${result.session_id}/turns`,
        request.current,
      );
      setResult(next);
      setMessages((old) => [
        ...old,
        { role: "You", text: value },
        { role: "Mezban", text: next.message },
      ]);
      setText("");
      request.current = null;
      speak(next.message);
    } catch (e) {
      setError((e as Error).message);
      setText(value);
    } finally {
      setBusy(false);
    }
  }
  function toggleMic() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    if (!SpeechRecognition) {
      setError(
        "Speech recognition is unavailable in this browser. Use Chrome or Edge, or type below.",
      );
      return;
    }
    window.speechSynthesis?.cancel();
    const instance = new SpeechRecognition();
    instance.lang = language;
    instance.interimResults = false;
    instance.onresult = (event) => {
      instance.onresult = null;
      const words = event.results[0][0].transcript;
      setText(words);
      void send(words);
    };
    instance.onerror = (event) => {
      const reasons: Record<string, string> = {
        "not-allowed":
          "Microphone permission was denied. Allow it in browser settings and try again.",
        "no-speech":
          "I did not hear any speech. Tap the microphone and try again.",
        "audio-capture": "No microphone was found. Check your audio device.",
        network: "The browser speech service could not connect.",
      };
      setError(
        `${reasons[event.error] || `Microphone: ${event.error}.`} You can also type below.`,
      );
      setListening(false);
    };
    instance.onend = () => setListening(false);
    recognition.current = instance;
    try {
      setListening(true);
      setError("");
      instance.start();
    } catch {
      setListening(false);
      setError("Could not start microphone. Please try again.");
    }
  }
  async function pay() {
    if (!result || busy) return;
    setBusy(true);
    setError("");
    try {
      const next = await api(`sessions/${result.session_id}/demo-payment`);
      setResult(next);
      setMessages((old) => [...old, { role: "Mezban", text: next.message }]);
      speak(next.message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function lookup() {
    setBusy(true);
    setError("");
    try {
      const next = await api("bookings/lookup", {
        reference: reference.trim(),
        phone: phone.trim(),
      });
      setResult(next);
      setMessages([{ role: "Mezban", text: next.message }]);
      setManage(false);
      request.current = null;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const f = result?.state.fields || {};
  const rows = [
    ["Dining", f.dining],
    ["Date", f.date],
    [
      "Time",
      f.time == null
        ? null
        : `${String(Math.floor(f.time / 60)).padStart(2, "0")}:${String(f.time % 60).padStart(2, "0")}`,
    ],
    [
      "Guests",
      f.adults == null
        ? null
        : `${f.adults} adults${f.children ? ` · ${f.children.length} children` : ""}`,
    ],
    ["Seating", f.seating],
    ["Name", f.name],
  ];
  return (
    <div className="shell">
      <header>
        <div className="brand">Mezban</div>
        <div className="location">
          A PAKISTANI RESTAURANT
          <br />
          LAHORE
        </div>
        <span className="demo">
          Demo restaurant <ChevronDown size={16} />
        </span>
      </header>
      <main>
        <div className="intro">
          <h1>Your table, a conversation away.</h1>
          <p>Natural conversation. Authentic hospitality.</p>
        </div>
        <div className="workspace">
          <section
            className="concierge panel"
            aria-label="Reservation conversation"
          >
            <div className="panel-heading">
              <div>
                <h2>Reservation concierge</h2>
                <p className="status">
                  <span />
                  {busy
                    ? "Working on your reservation…"
                    : listening
                      ? "Listening to you…"
                      : "Ready to assist"}
                </p>
              </div>
              <button
                className="icon-button"
                title="Start a new call"
                aria-label="Start a new call"
                disabled={busy}
                onClick={() => void start()}
              >
                <RotateCcw size={19} />
              </button>
            </div>
            <div className="voice-area">
              <div className={`mic-halo ${listening ? "listening" : ""}`}>
                <button
                  className="mic"
                  disabled={busy || !result}
                  onClick={toggleMic}
                  aria-label={listening ? "Stop listening" : "Start speaking"}
                >
                  {listening ? <MicOff size={34} /> : <Mic size={34} />}
                </button>
              </div>
              <h2>{listening ? "We’re listening." : "Talk to Mezban"}</h2>
              <p>
                Book a table, explore our buffet,
                <br />
                or make a change to your reservation.
              </p>
              <div className="suggestions">
                <button
                  disabled={busy || !result}
                  onClick={() => void send("I want a la carte")}
                >
                  <CalendarDays size={18} />
                  Book a table
                </button>
                <button
                  disabled={busy || !result}
                  onClick={() => void send("What is the buffet price?")}
                >
                  <Utensils size={18} />
                  Explore the buffet
                </button>
              </div>
            </div>
            <div className="conversation-label">
              <span>CONVERSATION</span>
              <div className="voice-settings">
                <select
                  aria-label="Recognition language"
                  value={language}
                  disabled={listening || busy}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  <option value="en-PK">English · PK</option>
                  <option value="ur-PK">Urdu · PK</option>
                </select>
                <button
                  className="icon-button"
                  aria-label="Replay assistant reply"
                  disabled={!voice || !result || busy || listening}
                  onClick={() => speak(result!.message)}
                >
                  <Play size={16} />
                </button>
                <button
                  className="icon-button"
                  aria-label={
                    voice ? "Mute assistant" : "Enable assistant voice"
                  }
                  onClick={() => {
                    setVoice(!voice);
                    window.speechSynthesis?.cancel();
                  }}
                >
                  {voice ? <Volume2 size={18} /> : <VolumeX size={18} />}
                </button>
              </div>
            </div>
            <div
              ref={transcript}
              className="transcript"
              role="log"
              aria-live="polite"
            >
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`message ${m.role === "You" ? "caller" : ""}`}
                >
                  <strong>{m.role}</strong>
                  <p>{m.text}</p>
                </div>
              ))}
            </div>
            {error ? (
              <div role="alert" className="error">
                {error}
                {!result ? (
                  <button onClick={() => void start()}>Reconnect</button>
                ) : null}
              </div>
            ) : null}
            {result?.state.alternatives?.length ? (
              <div className="suggestions alternatives">
                {result.state.alternatives.map((option) => {
                  const time = `${String(Math.floor(option.time / 60)).padStart(2, "0")}:${String(option.time % 60).padStart(2, "0")}`;
                  return (
                    <button
                      key={time + option.seating}
                      disabled={busy}
                      onClick={() => void send(`${time} ${option.seating}`)}
                    >
                      {time} · {option.seating}
                    </button>
                  );
                })}
              </div>
            ) : null}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <input
                aria-label="Your message"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Type your message…"
                maxLength={2000}
                disabled={busy || !result}
              />
              <button
                className="primary"
                disabled={busy || !result || !text.trim()}
              >
                <Send size={16} />
                Send
              </button>
            </form>
            <button
              className="manage-link"
              onClick={() => setManage(!manage)}
              disabled={busy}
            >
              Manage an existing booking
            </button>
            {manage ? (
              <form
                className="lookup"
                onSubmit={(e) => {
                  e.preventDefault();
                  void lookup();
                }}
              >
                <input
                  aria-label="Booking reference"
                  placeholder="MZ-…"
                  required
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                />
                <input
                  aria-label="Booking phone"
                  placeholder="03000000000"
                  pattern="03[0-9]{9}"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
                <button className="primary" disabled={busy}>
                  Find booking
                </button>
              </form>
            ) : null}
            <p className="speech-note">
              Tap the mic for each turn. Browser speech availability varies;
              typing always works.
            </p>
          </section>
          <aside>
            <section className="panel details">
              <h2>Booking details</h2>
              <dl>
                {rows.map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value || "—"}</dd>
                  </div>
                ))}
              </dl>
              {result?.quote ? (
                <div className="quote">
                  <span>
                    Total · tax included
                    <strong>PKR {result.quote.total.toLocaleString()}</strong>
                  </span>
                  <span>
                    25% demo deposit
                    <strong>PKR {result.quote.deposit.toLocaleString()}</strong>
                  </span>
                </div>
              ) : null}
              {result?.state.booking ? (
                <div className="booking">
                  <strong>{result.state.booking.id}</strong>
                  <span>
                    {result.state.booking.status.replaceAll("_", " ")}
                  </span>
                  {result.state.booking.status === "payment_pending" ? (
                    <>
                      <small>
                        Hold expires{" "}
                        {new Date(
                          result.state.booking.expires!,
                        ).toLocaleTimeString()}
                      </small>
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() => void pay()}
                      >
                        Simulate deposit
                      </button>
                    </>
                  ) : null}
                </div>
              ) : null}
              <h3>Packages</h3>
              <div className="package">
                <span>À la carte</span>
                <span>Menu prices</span>
              </div>
              <div className="package">
                <span>Hi-tea</span>
                <span>PKR 2,000</span>
              </div>
              <div className="package">
                <span>Dinner buffet</span>
                <span>PKR 3,000</span>
              </div>
              <p className="fine-print">
                Per adult · demo tax included
                <br />
                Under 4 free · ages 4–9 half price
              </p>
            </section>
            <section className="panel inspector">
              <details open>
                <summary>Decision inspector</summary>
                <dl>
                  <div>
                    <dt>State</dt>
                    <dd className="state">
                      {result?.state.stage || "connecting"}
                    </dd>
                  </div>
                  <div>
                    <dt>Intent</dt>
                    <dd>{result?.state.intent || "—"}</dd>
                  </div>
                  <div>
                    <dt>Rule</dt>
                    <dd>{result?.state.rule || "—"}</dd>
                  </div>
                  <div>
                    <dt>Next field</dt>
                    <dd>{result?.state.awaiting || "—"}</dd>
                  </div>
                </dl>
              </details>
              <p>
                Every decision comes from Python rules.
                <br />
                No language model makes booking decisions.
              </p>
            </section>
          </aside>
        </div>
      </main>
      <footer>
        <span>Mezban · Fictional restaurant · Fake details only</span>
        <span>Built with a rule-based brain</span>
      </footer>
    </div>
  );
}

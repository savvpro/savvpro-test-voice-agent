import { FormEvent, useEffect, useRef, useState } from "react";

type AssistantState = {
  session_id: string;
  reply: string;
  intent: "book" | "reschedule" | "update" | "cancel" | "none";
  current_step: string;
  status: "collecting" | "confirming" | "booked" | "cancelled" | "idle";
  booking: Record<string, string>;
  available_slots: string[];
};

type Message = { role: "assistant" | "caller"; text: string };
type AvailabilityGroup = { day: string; times: string[] };

type SpeechResult = ArrayLike<{ transcript: string }> & { isFinal: boolean };
type SpeechResultEvent = { results: ArrayLike<SpeechResult> };
type SpeechRecognitionError = { error: string };

type BrowserSpeechRecognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechRecognitionError) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;
type SpeechWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

const sessionId = crypto.randomUUID();
const welcomeMessage = "Hi, I'm PawPal. I can book, reschedule, or cancel a grooming appointment. To book, tell me the service, your pet's name, and a day and time—for example, \"Full groom for Sasha Friday at 1 PM.\" What would you like to do?";

function groupAvailability(slots: string[]): AvailabilityGroup[] {
  const groups = new Map<string, string[]>();
  for (const slot of slots) {
    const [day, time] = slot.split(" at ");
    if (!day || !time) continue;
    groups.set(day, [...(groups.get(day) ?? []), time]);
  }
  return Array.from(groups, ([day, times]) => ({ day, times }));
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: welcomeMessage },
  ]);
  const [assistantState, setAssistantState] = useState<AssistantState | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceReplies, setVoiceReplies] = useState(true);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const recognitionWindow = window as SpeechWindow;
  const Recognition = recognitionWindow.SpeechRecognition ?? recognitionWindow.webkitSpeechRecognition;
  const speechSupported = Boolean(Recognition);
  const speechSynthesisSupported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  const availabilityGroups = groupAvailability(
    assistantState?.available_slots ?? [
      "Friday at 1:00 PM",
      "Saturday at 10:00 AM",
      "Saturday at 2:00 PM",
      "Tuesday at 10:00 AM",
      "Tuesday at 2:00 PM",
      "Wednesday at 10:00 AM",
      "Wednesday at 4:00 PM",
    ],
  );

  useEffect(() => () => {
    recognitionRef.current?.stop();
    if (speechSynthesisSupported) window.speechSynthesis.cancel();
  }, [speechSynthesisSupported]);

  async function sendText(message: string) {
    const text = message.trim();
    if (!text || busy) return;

    setMessages((current) => [...current, { role: "caller", text }]);
    setInput("");
    setBusy(true);
    setError("");
    if (speechSynthesisSupported) window.speechSynthesis.cancel();
    try {
      const response = await fetch("/api/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      if (!response.ok) throw new Error(`Assistant API returned ${response.status}`);
      const result: AssistantState = await response.json();
      setAssistantState(result);
      setMessages((current) => [...current, { role: "assistant", text: result.reply }]);
      if (voiceReplies && speechSynthesisSupported) {
        const utterance = new SpeechSynthesisUtterance(result.reply);
        utterance.lang = "en-US";
        window.speechSynthesis.speak(utterance);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reach the assistant.");
    } finally {
      setBusy(false);
    }
  }

  function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendText(input);
  }

  function startListening() {
    if (!Recognition || busy || listening) return;
    setError("");
    const recognition = new Recognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognitionRef.current = recognition;

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .filter((result) => result.isFinal)
        .map((result) => result[0]?.transcript ?? "")
        .join(" ")
        .trim();
      if (transcript) {
        setInput(transcript);
        void sendText(transcript);
      }
    };
    recognition.onerror = (event) => {
      const messages: Record<string, string> = {
        "no-speech": "I didn't hear anything. Please try speaking again or type your message.",
        "not-allowed": "Microphone access is blocked. Allow microphone access in your browser settings, or type your message.",
        "service-not-allowed": "Speech recognition isn't permitted by this browser. You can still type your message.",
        network: "Speech recognition couldn't connect. Check your connection or type your message.",
      };
      setError(messages[event.error] ?? "Speech recognition failed. Please try again or type your message.");
    };
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };

    try {
      recognition.start();
      setListening(true);
    } catch (caught) {
      recognitionRef.current = null;
      setListening(false);
      setError(caught instanceof Error ? caught.message : "Could not start speech recognition.");
    }
  }

  function stopListening() {
    recognitionRef.current?.stop();
    setListening(false);
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="PawPal home">
          <span className="brand-mark">p</span>
          <span>PawPal</span>
        </a>
        <span className="channel-badge"><span>◉</span> VOICE + CHAT</span>
      </header>

      <section className="intro">
        <p className="eyebrow">THE FRIENDLY WAY TO BOOK</p>
        <h1>A little more <em>care</em><br />for your best friend.</h1>
        <p>Tell us what your pet needs. We’ll take care of the details.</p>
      </section>
      <nav className="journey" aria-label="How booking works">
        <span><i>01</i> Tell PawPal</span>
        <b aria-hidden="true" />
        <span><i>02</i> Review details</span>
        <b aria-hidden="true" />
        <span><i>03</i> Confirm to book</span>
      </nav>

      <section className="workspace" aria-label="PawPal appointment assistant">
        <div className="chat-card">
          <div className="card-heading">
            <div className="avatar">✿</div>
            <div><strong>Your PawPal assistant</strong><span>Here to help, one paw at a time</span></div>
            <span className="online-dot" aria-label="Online" />
          </div>
          <div className="transcript" aria-live="polite">
            {messages.map((message, index) => (
              <div key={index} className={`message-row ${message.role}`}>
                {message.role === "assistant" && <span className="mini-avatar">p</span>}
                <p>{message.text}</p>
              </div>
            ))}
            {busy && <div className="typing">PawPal is thinking<span> ···</span></div>}
          </div>
          {error && <p className="error-message" role="alert">{error}</p>}
          <form className="composer" onSubmit={sendMessage}>
            <label className="sr-only" htmlFor="message">Your message</label>
            <input
              id="message"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Type a message..."
              maxLength={1000}
              disabled={busy}
            />
            <button type="submit" disabled={busy || !input.trim()} aria-label="Send message">↑</button>
          </form>
          <div className="voice-controls">
            <button
              type="button"
              className={`voice-button ${listening ? "listening" : ""}`}
              onClick={listening ? stopListening : startListening}
              disabled={!speechSupported || busy}
              title={speechSupported ? "Speak your message" : "Speech recognition is not supported in this browser"}
            >
              {listening ? "■ Stop listening" : "🎙 Speak"}
            </button>
            <button
              type="button"
              className={`voice-button ${voiceReplies ? "enabled" : ""}`}
              onClick={() => {
                setVoiceReplies((enabled) => !enabled);
                if (voiceReplies && speechSynthesisSupported) window.speechSynthesis.cancel();
              }}
              disabled={!speechSynthesisSupported}
              aria-pressed={voiceReplies}
              title={speechSynthesisSupported ? "Toggle spoken assistant replies" : "Speech output is not supported in this browser"}
            >
              {voiceReplies ? "🔊 Replies on" : "🔈 Replies off"}
            </button>
          </div>
          <p className="chat-note">
            {listening
              ? "Listening… speak now"
              : !speechSupported
                ? "Speech input isn’t supported here; you can still type."
                : "Speak to send automatically, or type a message."}
          </p>
        </div>

        <aside className="details-card">
          <div className="details-title"><span>✧</span><h2>Appointment details</h2></div>
          <p className="details-caption">Review details and confirm before anything is booked.</p>
          <dl className="booking-details">
            <Detail label="SERVICE" value={assistantState?.booking.service} />
            <Detail label="PET'S NAME" value={assistantState?.booking.pet_name} />
            <Detail label="DAY" value={assistantState?.booking.day} />
            <Detail label="TIME" value={assistantState?.booking.time} />
            <Detail label="BOOKED BY" value={assistantState?.booking.owner_name} />
          </dl>
          <div className="decision-box">
            <span className="decision-label">ASSISTANT DECISION</span>
            <p><b>Intent</b><span>{assistantState?.intent ?? "waiting"}</span></p>
            <p><b>Next step</b><span>{assistantState?.current_step ?? "start"}</span></p>
            <p><b>Status</b><span>{assistantState?.status ?? "idle"}</span></p>
          </div>
          <div className="availability">
            <div className="availability-heading">
              <strong>Available sample slots</strong>
              <span>{assistantState?.available_slots.length ?? 7} openings</span>
            </div>
            <p className="availability-note">Demo schedule only · not a live calendar</p>
            <div className="availability-days">
              {availabilityGroups.map(({ day, times }) => (
                <div className="availability-day" key={day}>
                  <span>{day}</span>
                  <div>
                    {times.map((time) => <span className="slot-chip" key={time}>{time}</span>)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </section>
      <footer>Made with care for pets and their people <span>♥</span></footer>
    </main>
  );
}

function Detail({ label, value }: { label: string; value?: string }) {
  return <div className="detail-row"><dt>{label}</dt><dd className={value ? "filled" : ""}>{value ?? "—"}</dd></div>;
}

import { useEffect, useRef } from "react";

export interface Message {
  who: "caller" | "assistant";
  text: string;
}

export default function Transcript({ messages }: { messages: Message[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="transcript" aria-live="polite">
      {messages.length === 0 && <p className="muted">Press “Start call” to begin.</p>}
      {messages.map((m, i) => (
        <div key={i} className={`bubble ${m.who}`}>
          <span className="who">{m.who === "caller" ? "You" : "Assistant"}</span>
          {m.text}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

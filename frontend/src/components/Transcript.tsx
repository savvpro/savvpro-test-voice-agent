import { useEffect, useRef } from "react";
import type { Role } from "../api/types";

export interface Message {
  id: number;
  role: Role;
  text: string;
}

export function Transcript({ messages }: { messages: Message[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="transcript empty">
        <p>Press <strong>Start call</strong> to talk to the receptionist.</p>
        <p className="hint">Try: “I need a cardiologist next Tuesday morning.”</p>
      </div>
    );
  }
  return (
    <div className="transcript" aria-live="polite">
      {messages.map((m) => (
        <div key={m.id} className={`bubble ${m.role}`} data-role={m.role}>
          <span className="who">{m.role === "agent" ? "Receptionist" : "You"}</span>
          {m.text || <em>(silence)</em>}
        </div>
      ))}
      <div ref={end} />
    </div>
  );
}

"use client";

import { useEffect, useRef } from "react";

export type Message = { who: "agent" | "caller" | "system"; text: string; turn?: number; spoken?: boolean };

type Props = {
  messages: Message[];
  interim: string;
  thinking: boolean;
  selected: number | null;
  onSelect: (turn: number) => void;
  empty: React.ReactNode;
};

export function Transcript({ messages, interim, thinking, selected, onSelect, empty }: Props) {
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, interim, thinking]);

  if (!messages.length) return <div className="flex-1">{empty}</div>;

  return (
    <div className="flex-1 overflow-y-auto px-5 py-5" style={{ maxHeight: 520 }} aria-live="polite">
      <ul className="space-y-3">
        {messages.map((m, i) => {
          if (m.who === "system") {
            return (
              <li key={i} className="py-1 text-center text-xs text-ink-400">
                {m.text}
              </li>
            );
          }
          const caller = m.who === "caller";
          const isSelected = m.turn !== undefined && m.turn === selected;
          return (
            <li key={i} className={`flex animate-fade-up ${caller ? "justify-end" : ""}`}>
              <div className={`max-w-[85%] ${caller ? "text-right" : ""}`}>
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-ink-400">
                  {caller ? `You${m.spoken ? " · spoken" : " · typed"}` : "Assistant"}
                </p>
                <button
                  type="button"
                  disabled={m.turn === undefined}
                  onClick={() => m.turn !== undefined && onSelect(m.turn)}
                  title={m.turn !== undefined ? "Show what the brain decided on this turn" : undefined}
                  className={`rounded-2xl px-4 py-2.5 text-left text-sm leading-relaxed transition ${
                    caller ? "rounded-br-md bg-ink-900 text-white" : "rounded-bl-md bg-ink-100 text-ink-800"
                  } ${isSelected ? "ring-2 ring-ink-400 ring-offset-2" : ""} ${m.turn !== undefined ? "cursor-pointer hover:opacity-90" : "cursor-default"}`}
                >
                  {m.text}
                </button>
              </div>
            </li>
          );
        })}

        {interim && (
          <li className="flex justify-end">
            <p className="max-w-[85%] rounded-2xl rounded-br-md border border-dashed border-ink-400 px-4 py-2.5 text-sm italic text-ink-600">
              {interim}
            </p>
          </li>
        )}
        {thinking && (
          <li className="flex">
            <span className="flex gap-1 rounded-2xl rounded-bl-md bg-ink-100 px-4 py-3.5" aria-label="Thinking">
              {[0, 1, 2].map((d) => (
                <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-500" style={{ animationDelay: `${d * 0.15}s` }} />
              ))}
            </span>
          </li>
        )}
      </ul>
      <div ref={end} />
    </div>
  );
}

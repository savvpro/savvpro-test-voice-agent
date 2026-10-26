import type { SessionView } from "../src/api/client";

export function view(changes: Partial<SessionView> = {}): SessionView {
  return {
    version: 0,
    state: "collecting",
    reply: "Tell me what you lost.",
    fields: {
      category: null,
      colour: null,
      brand: null,
      location: null,
      lost_date: null,
      description: "",
      uncertain: [],
      unknown: [],
    },
    candidates: [],
    trace: { rule: "ready", explanation: "Ask for the missing information." },
    transcript: [{ role: "assistant", text: "Tell me what you lost." }],
    proposal: null,
    receipt: null,
    restart_pending: false,
    ...changes,
  };
}

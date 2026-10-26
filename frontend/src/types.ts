export type Decision = {
  conversation_id: string;
  version: number;
  status: string;
  state_before: string | null;
  state: string | null;
  action: string;
  reason: string;
  reply: string;
  candidates: Record<string, unknown>;
  accepted: Record<string, unknown>;
  pending_field: string | null;
  draft: Record<string, unknown>;
  offered_slots: string[];
};

export type ChatMessage = { role: "caller" | "assistant"; text: string };


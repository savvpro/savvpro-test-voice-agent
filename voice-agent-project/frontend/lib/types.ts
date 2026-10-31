export interface Trace {
  heard: string;
  state_before: string;
  state_after: string;
  intents: string[];
  entities: Record<string, string>;
  rule: string;
  notes: string[];
}

export interface TurnResponse {
  session_id: string;
  reply: string;
  ended: boolean;
  state: string;
  intent: string | null;
  slots: Record<string, string | null>;
  trace: Trace;
}

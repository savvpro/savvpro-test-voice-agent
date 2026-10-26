export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Slots = {
  service: string | null;
  date: string | null;
  time: string | null;
  name: string | null;
  phone: string | null;
};

export type SessionView = {
  session_id: string;
  state: string;
  slots: Slots;
  done: boolean;
};

export type StartResponse = SessionView & { reply: string };

export type TurnResponse = SessionView & {
  reply: string;
  intents: string[];
  actions: string[];
  trace: string[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Server answered ${response.status}`);
  }
  return (await response.json()) as T;
}

export function startSession(): Promise<StartResponse> {
  return request<StartResponse>("/api/sessions", { method: "POST" });
}

export function sendTurn(sessionId: string, text: string): Promise<TurnResponse> {
  return request<TurnResponse>(`/api/sessions/${sessionId}/turns`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

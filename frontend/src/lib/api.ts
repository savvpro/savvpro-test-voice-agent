export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type CallState = {
  task: string | null;
  service: string | null;
  day: string | null;
  at: string | null;
  part_of_day: string | null;
  name: string | null;
  phone: string | null;
  phone_skipped: boolean;
  booking_id: string | null;
  offers: string[];
  awaiting: string | null;
  misses: number;
  ended: boolean;
  result: string | null;
};

export type Decision = {
  heard: string;
  normalized: string;
  intent: string | null;
  confidence: number;
  extracted: Record<string, unknown>;
  action: string;
  reasons: string[];
  reply: string;
  state: CallState;
  ended: boolean;
};

export type StartedCall = { call_id: string; reply: string; state: CallState; ended: boolean };

export type Booking = { id: string; name: string; phone: string; service: string; start: string; when: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error(`Can't reach the assistant at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  startCall: () => request<StartedCall>("/api/calls", { method: "POST" }),
  sendTurn: (callId: string, text: string) =>
    request<Decision>(`/api/calls/${callId}/turns`, { method: "POST", body: JSON.stringify({ text }) }),
  schedule: () => request<{ bookings: Booking[] }>("/api/schedule"),
  reset: () => request<{ status: string }>("/api/reset", { method: "POST" }),
};

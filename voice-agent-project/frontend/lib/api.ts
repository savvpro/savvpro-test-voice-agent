import type { TurnResponse } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const startSession = () => request<TurnResponse>("/api/sessions", { method: "POST" });

export const sendTurn = (sessionId: string, text: string, confidence?: number) =>
  request<TurnResponse>(`/api/sessions/${sessionId}/turn`, {
    method: "POST",
    body: JSON.stringify({ text, confidence: confidence ?? null }),
  });

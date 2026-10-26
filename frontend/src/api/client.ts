import type { Appointment, TurnResponse } from "./types";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error(`Can't reach the backend at ${API_URL}. Is it running?`);
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      // not JSON: keep the status text
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.json() as Promise<T>;
}

export function startSession(): Promise<TurnResponse> {
  return request("/api/sessions", { method: "POST" });
}

export function sendText(sessionId: string, text: string): Promise<TurnResponse> {
  return request(`/api/sessions/${sessionId}/turn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export function sendAudio(sessionId: string, audio: Blob): Promise<TurnResponse> {
  const form = new FormData();
  const extension = audio.type.includes("ogg") ? "ogg" : audio.type.includes("wav") ? "wav" : "webm";
  form.append("audio", audio, `turn.${extension}`);
  return request(`/api/sessions/${sessionId}/turn`, { method: "POST", body: form });
}

export function listAppointments(): Promise<Appointment[]> {
  return request("/api/admin/appointments?order=recent");
}

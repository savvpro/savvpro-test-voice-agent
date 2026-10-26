/**
 * Backend API client.
 *
 * All requests go through the gateway using ?XTransformPort=8000 so the
 * Next.js frontend can reach the Python FastAPI backend without CORS issues.
 */

const BACKEND_PORT = 8000;

export type ChatResponse = {
  session_id: string;
  text: string;
  state: string;
  slots: {
    date: string | null;
    time: string | null;
    party_size: number | null;
    name: string | null;
    phone: string | null;
  };
  intent: string;
  decision: string;
  end_call: boolean;
  booking_id: string | null;
  history: Array<{
    role: "caller" | "assistant";
    text: string;
    intent?: string;
    confidence?: number;
    state?: string;
    decision?: string;
    state_before?: string;
  }>;
};

export type ResetResponse = {
  session_id: string;
  state: string;
  slots: Record<string, null>;
  last_prompt: string;
};

function url(path: string) {
  return `${path}?XTransformPort=${BACKEND_PORT}`;
}

export async function postChat(
  sessionId: string | null,
  text: string,
): Promise<ChatResponse> {
  const r = await fetch(url("/api/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, text }),
  });
  if (!r.ok) {
    throw new Error(`chat failed: ${r.status} ${await r.text()}`);
  }
  return (await r.json()) as ChatResponse;
}

export async function postReset(): Promise<ResetResponse> {
  const r = await fetch(url("/api/reset"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!r.ok) {
    throw new Error(`reset failed: ${r.status}`);
  }
  return (await r.json()) as ResetResponse;
}

export async function getHealth(): Promise<{
  ok: boolean;
  version: string;
  bookings_count: number;
  sessions_count: number;
}> {
  const r = await fetch(url("/api/health"));
  if (!r.ok) throw new Error(`health failed: ${r.status}`);
  return r.json();
}

function resolveApiBase() {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return "";
  }
  return "http://localhost:8001";
}

const API_BASE = resolveApiBase();

async function parseJsonResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || data.message || response.statusText;
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return data;
}

function apiUrl(path) {
  return `${resolveApiBase()}${path}`;
}

export async function startConversation() {
  const response = await fetch(apiUrl("/api/conversation/start"), {
    method: "POST",
  });
  return parseJsonResponse(response);
}

export async function sendMessage(conversationId, text) {
  const response = await fetch(apiUrl("/api/message"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, text }),
  });
  return parseJsonResponse(response);
}

export async function getConversation(conversationId) {
  const response = await fetch(apiUrl(`/api/conversation/${conversationId}`));
  return parseJsonResponse(response);
}

export { API_BASE };

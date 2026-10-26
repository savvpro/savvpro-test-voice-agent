const BASE = '/api';

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }
  return res.json();
}

/** Start a new call. Returns { session_id, reply, state }. */
export function startSession() {
  return request('/sessions', { method: 'POST' });
}

/** Send what the caller said. Returns { reply, state, intent, slots, trace, ended, alternatives }. */
export function sendTurn(sessionId, text) {
  return request(`/sessions/${encodeURIComponent(sessionId)}/turn`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

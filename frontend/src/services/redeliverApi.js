const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
    })
  } catch {
    throw new Error('Could not reach REDELIVER. Check that the backend is running.')
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : detail
    } catch {
      // Keep the status-based message if the backend did not return JSON.
    }
    throw new Error(detail)
  }
  if (response.status === 204) return null
  return response.json()
}

export function getHealth() {
  return request('/health')
}

export function createSession() {
  return request('/sessions', { method: 'POST', body: JSON.stringify({}) })
}

export function sendTurn(sessionId, turn) {
  return request(`/sessions/${encodeURIComponent(sessionId)}/turns`, {
    method: 'POST',
    body: JSON.stringify(turn),
  })
}

export function getSession(sessionId) {
  return request(`/sessions/${encodeURIComponent(sessionId)}`)
}

export function endSession(sessionId) {
  return request(`/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
}

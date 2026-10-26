export interface Decision {
  intent: string
  entities: Record<string, string>
  state: string
  action: string
  slots: Record<string, string>
}

export interface TurnResponse {
  call_id: string
  reply: string
  decision: Decision
  ended: boolean
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function post(path: string, body?: unknown): Promise<TurnResponse> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let msg = res.statusText || `Request failed (${res.status})`
    try {
      const d = (await res.json()).detail
      if (typeof d === 'string') msg = d
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, msg)
  }
  return res.json()
}

export const startCall = () => post('/api/calls')

export const sendTurn = (callId: string, text: string) =>
  post(`/api/calls/${encodeURIComponent(callId)}/turns`, { text })

export type Appointment = {
  id: string
  reference: string
  service: string
  service_name: string
  vehicle: string
  date: string
  time: string
  description: string
  minutes: number
  status: string
}
export type DecisionTrace = {
  from_state: string
  to_state: string
  intent: string | null
  rules: string[]
  extracted: Record<string, string>
  validation: string[]
  action: string
}
export type ConversationState = {
  phase?: string
  intent?: string
  slots?: Record<string, string>
  alternatives?: { date: string; time: string; label: string }[]
  appointment?: Appointment
  last_reply?: string
}
export type TurnResult = {
  revision: number
  state: ConversationState
  reply: string
  trace: DecisionTrace
  appointments: Appointment[]
}
export type HistoryItem = { text: string; reply: string; trace: DecisionTrace }
export type SessionData = {
  revision: number
  state: ConversationState
  appointments: Appointment[]
  history: HistoryItem[]
  welcome: string
  caller: string
  timezone: string
  demo_date: string
}
export type Capabilities = {
  server_stt: boolean
  timezone: string
  services: Record<string, { name: string; minutes: number }>
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 35000)
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  if (signal?.aborted) controller.abort()
  try {
    const response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      credentials: 'same-origin',
      headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
      signal: controller.signal,
    })
    const result = await response.json()
    if (!response.ok)
      throw new ApiError(
        typeof result.detail === 'string'
          ? result.detail
          : 'Please check your message and try again.',
        response.status,
      )
    return result as T
  } finally {
    clearTimeout(timeout)
    signal?.removeEventListener('abort', abort)
  }
}

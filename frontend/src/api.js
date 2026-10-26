// Transport and response-contract checks only. Reservation decisions stay in Python.
export class ApiError extends Error {
  constructor(message, { status = 0, retryable = true } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.retryable = retryable;
  }
}

const statuses = new Set(['ask_date', 'ask_time', 'ask_party_size', 'confirm', 'completed', 'cancelled']);
const nonempty = (value) => typeof value === 'string' && value.trim().length > 0;

export function isConversation(value) {
  if (!value || !nonempty(value.session_id) || !nonempty(value.message) || !statuses.has(value.status)) return false;
  const details = value.collected_data;
  if (!details || !['date', 'time'].every((key) => details[key] === null || nonempty(details[key]))) return false;
  if (details.party_size !== null && !Number.isInteger(details.party_size)) return false;
  const reservation = value.reservation;
  if (reservation === null) return value.status !== 'completed';
  return Boolean(reservation &&
    ['reservation_id', 'reservation_date', 'reservation_time', 'status', 'created_at'].every((key) => nonempty(reservation[key])) &&
    Number.isInteger(reservation.party_size));
}

async function post(path, body, signal) {
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  signal?.addEventListener('abort', onAbort, { once: true });
  if (signal?.aborted) controller.abort();
  const timeout = setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}),
      signal: controller.signal,
    });
    let result;
    try { result = await response.json(); } catch { /* Handle invalid JSON below. */ }
    if (!response.ok) {
      const retryable = response.status >= 500 || [408, 425, 429].includes(response.status);
      let message = typeof result?.detail === 'string' ? result.detail : 'That request could not be accepted. Please try again.';
      if (response.status === 404) message = 'This conversation is no longer available. Please start a new conversation.';
      if (response.status === 409) message = 'We could not match that message safely. Please start a new conversation.';
      throw new ApiError(message, { status: response.status, retryable });
    }
    if (!isConversation(result) || (body && result.session_id !== body.session_id)) {
      throw new ApiError('We could not read the assistant’s response. Retry the same request to check its result.');
    }
    return result;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('We did not receive a response. Please retry the same request; it may already have been processed.');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', onAbort);
  }
}

export const startConversation = (signal) => post('/api/conversations/start', undefined, signal);
export const sendConversationMessage = (payload, signal) => post('/api/conversations/message', payload, signal);

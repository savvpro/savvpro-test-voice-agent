export const details = { date: '2026-10-27', time: '19:00', party_size: 4 };
export const reservation = {
  reservation_id: 'test-booking-001', reservation_date: details.date,
  reservation_time: details.time, party_size: 4,
  status: 'confirmed', created_at: '2026-10-26T10:00:00Z',
};

export function conversation(overrides = {}) {
  return {
    session_id: 'test-session-from-server',
    status: 'ask_date', message: 'Welcome! What date would you like to book?',
    collected_data: { date: null, time: null, party_size: null }, reservation: null,
    ...overrides,
  };
}

export function http(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

export function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

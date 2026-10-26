const API = import.meta.env.VITE_API_URL || ''

async function parseError(res, fallback) {
  let detail = fallback
  try {
    const body = await res.json()
    if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : fallback
  } catch {
    /* ignore */
  }
  return detail
}

export async function checkHealth() {
  const res = await fetch(`${API}/api/health`)
  if (!res.ok) throw new Error(`Health failed (${res.status})`)
  return res.json()
}

export async function sendTurn(sessionId, text) {
  const res = await fetch(`${API}/api/turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, text }),
  })
  if (res.status === 429) throw new Error(await parseError(res, 'Too many requests — wait a moment'))
  if (!res.ok) throw new Error(await parseError(res, `Turn failed (${res.status})`))
  return res.json()
}

export async function resetSession(sessionId) {
  const res = await fetch(`${API}/api/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!res.ok) throw new Error(await parseError(res, `Reset failed (${res.status})`))
  return res.json()
}

export function newSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `s-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function adminHeaders(password) {
  return {
    'Content-Type': 'application/json',
    'X-Admin-Password': password,
  }
}

export async function adminListBookings(password, { date, q, includeCancelled = true } = {}) {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  if (q) params.set('q', q)
  params.set('include_cancelled', includeCancelled ? 'true' : 'false')
  const qs = params.toString()
  const res = await fetch(`${API}/api/admin/bookings?${qs}`, {
    headers: adminHeaders(password),
  })
  if (res.status === 401) throw new Error('Wrong admin password')
  if (!res.ok) throw new Error(`List failed (${res.status})`)
  return res.json()
}

export async function adminCancelBooking(password, id) {
  const res = await fetch(`${API}/api/admin/bookings/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: adminHeaders(password),
  })
  if (res.status === 401) throw new Error('Wrong admin password')
  if (res.status === 404) throw new Error('Booking not found')
  if (!res.ok) throw new Error(`Cancel failed (${res.status})`)
  return res.json()
}

export async function adminRestoreBooking(password, id) {
  const res = await fetch(
    `${API}/api/admin/bookings/${encodeURIComponent(id)}/restore`,
    { method: 'POST', headers: adminHeaders(password) },
  )
  if (res.status === 401) throw new Error('Wrong admin password')
  if (res.status === 409) throw new Error('Cannot restore — table may be taken')
  if (!res.ok) throw new Error(`Restore failed (${res.status})`)
  return res.json()
}

export async function adminOpenSlots(password, date, partySize = 2) {
  const params = new URLSearchParams({
    date,
    party_size: String(partySize),
  })
  const res = await fetch(`${API}/api/admin/open-slots?${params}`, {
    headers: adminHeaders(password),
  })
  if (res.status === 401) throw new Error('Wrong admin password')
  if (!res.ok) throw new Error(`Open slots failed (${res.status})`)
  return res.json()
}

export async function adminStats(password) {
  const res = await fetch(`${API}/api/admin/stats`, {
    headers: adminHeaders(password),
  })
  if (res.status === 401) throw new Error('Wrong admin password')
  if (!res.ok) throw new Error(`Stats failed (${res.status})`)
  return res.json()
}

export async function adminSeed(password) {
  const res = await fetch(`${API}/api/admin/seed`, {
    method: 'POST',
    headers: adminHeaders(password),
  })
  if (res.status === 401) throw new Error('Wrong admin password')
  if (!res.ok) throw new Error(`Seed failed (${res.status})`)
  return res.json()
}

export function adminCsvUrl(password, date) {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  // Browser download can't set custom headers easily — use fetch blob helper instead
  return `${API}/api/admin/bookings.csv?${params}`
}

export async function adminDownloadCsv(password, date) {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  const res = await fetch(`${API}/api/admin/bookings.csv?${params}`, {
    headers: adminHeaders(password),
  })
  if (res.status === 401) throw new Error('Wrong admin password')
  if (!res.ok) throw new Error(`CSV export failed (${res.status})`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'bookings.csv'
  a.click()
  URL.revokeObjectURL(url)
}

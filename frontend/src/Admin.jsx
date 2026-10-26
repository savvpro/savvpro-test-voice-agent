import { useCallback, useState } from 'react'
import {
  adminCancelBooking,
  adminDownloadCsv,
  adminListBookings,
  adminOpenSlots,
  adminRestoreBooking,
  adminSeed,
  adminStats,
} from './api'
import './App.css'

const DEFAULT_PASS = 'admin'

export default function Admin() {
  const [password, setPassword] = useState(
    () => sessionStorage.getItem('hlb_admin_pw') || DEFAULT_PASS,
  )
  const [unlocked, setUnlocked] = useState(false)
  const [bookings, setBookings] = useState([])
  const [dateFilter, setDateFilter] = useState('')
  const [idSearch, setIdSearch] = useState('')
  const [slotDate, setSlotDate] = useState('')
  const [partySize, setPartySize] = useState(2)
  const [openTimes, setOpenTimes] = useState([])
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    setBusy(true)
    setError('')
    setMsg('')
    try {
      sessionStorage.setItem('hlb_admin_pw', password)
      const [data, st] = await Promise.all([
        adminListBookings(password, {
          date: dateFilter || undefined,
          q: idSearch || undefined,
          includeCancelled: true,
        }),
        adminStats(password),
      ])
      setBookings(data.bookings || [])
      setStats(st)
      setUnlocked(true)
    } catch (err) {
      setUnlocked(false)
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }, [password, dateFilter, idSearch])

  const cancel = async (id) => {
    if (!window.confirm(`Cancel booking ${id}?`)) return
    setBusy(true)
    setError('')
    try {
      await adminCancelBooking(password, id)
      setMsg(`Cancelled ${id}`)
      await load()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }

  const restore = async (id) => {
    setBusy(true)
    setError('')
    try {
      await adminRestoreBooking(password, id)
      setMsg(`Restored ${id}`)
      await load()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }

  const loadSlots = async () => {
    if (!slotDate) {
      setError('Pick a date for open slots')
      return
    }
    setBusy(true)
    setError('')
    try {
      const data = await adminOpenSlots(password, slotDate, partySize)
      setOpenTimes(data.open_times || [])
      setUnlocked(true)
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }

  const seed = async () => {
    setBusy(true)
    setError('')
    try {
      const data = await adminSeed(password)
      setMsg(`Seeded ${data.created} demo booking(s)`)
      await load()
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }

  const exportCsv = async () => {
    setBusy(true)
    setError('')
    try {
      await adminDownloadCsv(password, dateFilter || undefined)
      setMsg('CSV download started')
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page admin-page">
      <header className="hero">
        <div>
          <p className="eyebrow">Harbor Lights Bistro</p>
          <h1>Admin — bookings</h1>
          <p className="lede">
            Local assessment panel. Shared password from{' '}
            <code>ADMIN_PASSWORD</code> (default <code>admin</code>). Not real auth.
          </p>
        </div>
        <div className="hero-actions">
          <a className="btn ghost" href="#/">
            ← Talk UI
          </a>
        </div>
      </header>

      {error ? (
        <div className="banner error" role="alert">
          {error}
        </div>
      ) : null}
      {msg ? (
        <div className="banner ok" role="status">
          {msg}
        </div>
      ) : null}

      <section className="panel admin-auth">
        <div className="panel-head">
          <h2>Unlock</h2>
        </div>
        <div className="banner ok demo-pass-banner" role="note">
          <strong>Demo password:</strong> <code>{DEFAULT_PASS}</code>
          <span className="muted"> (local only — change via ADMIN_PASSWORD)</span>
        </div>
        <div className="admin-row">
          <label>
            Password
            <input
              type="text"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="off"
              placeholder={`Demo: ${DEFAULT_PASS}`}
              aria-describedby="admin-pass-hint"
            />
            <span id="admin-pass-hint" className="field-hint">
              For reviewers: type <code>{DEFAULT_PASS}</code> then click Load bookings
            </span>
          </label>
          <label>
            Filter date
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
            />
          </label>
          <label>
            Search ID
            <input
              type="search"
              placeholder="HLB-…"
              value={idSearch}
              onChange={(e) => setIdSearch(e.target.value)}
            />
          </label>
          <button type="button" className="btn primary" onClick={load} disabled={busy}>
            Load bookings
          </button>
          <button type="button" className="btn ghost" onClick={seed} disabled={busy}>
            Seed demo
          </button>
          <button type="button" className="btn ghost" onClick={exportCsv} disabled={busy || !unlocked}>
            Export CSV
          </button>
        </div>
      </section>

      {unlocked && stats ? (
        <section className="panel stats-panel">
          <div className="panel-head">
            <h2>Stats</h2>
          </div>
          <div className="stats-grid">
            <div>
              <span className="stat-label">Active</span>
              <strong>{stats.total_active}</strong>
            </div>
            <div>
              <span className="stat-label">Cancelled</span>
              <strong>{stats.total_cancelled}</strong>
            </div>
            <div>
              <span className="stat-label">Today ({stats.today})</span>
              <strong>{stats.today_count}</strong>
            </div>
            <div>
              <span className="stat-label">Seats today</span>
              <strong>{stats.today_seats}</strong>
            </div>
          </div>
        </section>
      ) : null}

      {unlocked ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Bookings ({bookings.length})</h2>
          </div>
          {bookings.length === 0 ? (
            <p className="empty tight">No bookings yet. Use Seed demo or book from the talk UI.</p>
          ) : (
            <div className="table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Party</th>
                    <th>Table</th>
                    <th>Guest</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {bookings.map((b) => (
                    <tr key={b.id} className={b.status === 'cancelled' ? 'row-cancelled' : ''}>
                      <td>
                        <code>{b.id}</code>
                      </td>
                      <td>{b.date}</td>
                      <td>{b.time}</td>
                      <td>{b.party_size}</td>
                      <td>{b.table_label}</td>
                      <td>{b.guest_name || '—'}</td>
                      <td>
                        <span className={`status-pill ${b.status}`}>{b.status}</span>
                      </td>
                      <td className="actions-cell">
                        {b.status === 'active' ? (
                          <button
                            type="button"
                            className="btn danger"
                            disabled={busy}
                            onClick={() => cancel(b.id)}
                          >
                            Cancel
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="btn ghost"
                            disabled={busy}
                            onClick={() => restore(b.id)}
                          >
                            Restore
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <h2>Open slots</h2>
        </div>
        <div className="admin-row">
          <label>
            Date
            <input
              type="date"
              value={slotDate}
              onChange={(e) => setSlotDate(e.target.value)}
            />
          </label>
          <label>
            Party size
            <input
              type="number"
              min={1}
              max={20}
              value={partySize}
              onChange={(e) => setPartySize(Number(e.target.value) || 2)}
            />
          </label>
          <button type="button" className="btn ghost" onClick={loadSlots} disabled={busy}>
            Check
          </button>
        </div>
        {openTimes.length > 0 ? (
          <p className="slots-line">
            Open:{' '}
            {openTimes.map((t) => (
              <span key={t} className="pill">
                {t}
              </span>
            ))}
          </p>
        ) : unlocked && slotDate ? (
          <p className="empty tight">No open times for that party size (or not checked yet).</p>
        ) : null}
      </section>
    </div>
  )
}

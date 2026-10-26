import { useCallback, useEffect, useRef, useState } from 'react'
import { checkHealth, newSessionId, resetSession, sendTurn } from './api'
import { speak, speechSupported, startListening, stopSpeaking, ttsSupported } from './speech'
import './App.css'

const STATE_LABELS = {
  greeting: 'Greeting',
  ask_date: 'Asking for date',
  ask_time: 'Asking for time',
  ask_party: 'Asking for party size',
  confirm: 'Confirming booking',
  booked: 'Booked',
  goodbye: 'Goodbye',
  cancelled: 'Cancelled',
}

function formatSlot(slots) {
  if (!slots) return []
  const rows = []
  if (slots.date) rows.push(['Date', slots.date])
  if (slots.time) rows.push(['Time', slots.time])
  if (slots.party_size) rows.push(['Party', String(slots.party_size)])
  if (slots.guest_name) rows.push(['Name', slots.guest_name])
  return rows
}

export default function App() {
  const [sessionId, setSessionId] = useState(() => newSessionId())
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [busy, setBusy] = useState(false)
  const [ttsOn, setTtsOn] = useState(true)
  const [state, setState] = useState('greeting')
  const [slots, setSlots] = useState({})
  const [decisions, setDecisions] = useState([])
  const [booking, setBooking] = useState(null)
  const [confirmation, setConfirmation] = useState(null)
  const [error, setError] = useState('')
  const [apiOnline, setApiOnline] = useState(null)
  const [micOk] = useState(() => speechSupported())
  const listenRef = useRef(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  const applyResponse = useCallback(
    (data, callerText) => {
      setState(data.state)
      setSlots(data.slots || {})
      setBooking(data.booking || null)
      if (data.confirmation) setConfirmation(data.confirmation)
      setDecisions((prev) => [
        {
          id: `${Date.now()}-${prev.length}`,
          caller: callerText,
          ...data.decision,
        },
        ...prev,
      ])
      setMessages((prev) => [
        ...prev,
        ...(callerText
          ? [{ id: `c-${Date.now()}`, role: 'caller', text: callerText }]
          : []),
        { id: `a-${Date.now()}`, role: 'assistant', text: data.reply },
      ])
      if (ttsOn && ttsSupported()) speak(data.reply)
    },
    [ttsOn],
  )

  const pingApi = useCallback(async () => {
    try {
      await checkHealth()
      setApiOnline(true)
      return true
    } catch {
      setApiOnline(false)
      return false
    }
  }, [])

  const boot = useCallback(async () => {
    setBusy(true)
    setError('')
    const ok = await pingApi()
    if (!ok) {
      setError(
        'Cannot reach the backend. Start it with RUN_APP.bat or: cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000',
      )
      setBusy(false)
      return
    }
    try {
      const data = await resetSession(sessionId)
      setMessages([])
      setDecisions([])
      setBooking(null)
      setConfirmation(null)
      setSlots({})
      applyResponse(data, null)
    } catch (err) {
      setApiOnline(false)
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }, [sessionId, applyResponse, pingApi])

  useEffect(() => {
    boot()
    const t = setInterval(pingApi, 15000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, interim])

  const submitText = async (raw) => {
    const text = (raw || '').trim()
    if (!text || busy) return
    setBusy(true)
    setError('')
    setDraft('')
    setInterim('')
    try {
      const data = await sendTurn(sessionId, text)
      setApiOnline(true)
      applyResponse(data, text)
    } catch (err) {
      if (String(err.message || '').includes('fetch') || String(err).includes('Network')) {
        setApiOnline(false)
      }
      setError(String(err.message || err))
    } finally {
      setBusy(false)
      inputRef.current?.focus()
    }
  }

  const onSubmit = (e) => {
    e.preventDefault()
    submitText(draft)
  }

  const onComposerKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submitText(draft)
    }
  }

  const toggleMic = () => {
    if (listening) {
      listenRef.current?.stop()
      listenRef.current = null
      setListening(false)
      return
    }
    if (!micOk) {
      setError('This browser has no SpeechRecognition. Use the text box.')
      return
    }
    stopSpeaking()
    setError('')
    setListening(true)
    setInterim('')
    listenRef.current = startListening({
      onResult: (text, isFinal) => {
        setInterim(text)
        if (isFinal && text.trim()) {
          listenRef.current?.stop()
          listenRef.current = null
          setListening(false)
          submitText(text.trim())
        }
      },
      onError: (msg) => {
        setError(`Mic: ${msg}`)
        setListening(false)
      },
      onEnd: () => {
        setListening(false)
        listenRef.current = null
      },
    })
  }

  const onMicKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      toggleMic()
    }
  }

  const hardReset = async () => {
    stopSpeaking()
    listenRef.current?.stop()
    setListening(false)
    const id = newSessionId()
    setSessionId(id)
    setBusy(true)
    setError('')
    try {
      const data = await resetSession(id)
      setApiOnline(true)
      setMessages([])
      setDecisions([])
      setBooking(null)
      setConfirmation(null)
      setSlots({})
      applyResponse(data, null)
    } catch (err) {
      setApiOnline(false)
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }

  const slotRows = formatSlot(slots)
  const ticket = confirmation || (booking
    ? {
        code: booking.id,
        restaurant: booking.restaurant || 'Harbor Lights Bistro',
        datetime_display: `${booking.date} at ${booking.time}`,
        date: booking.date,
        time: booking.time,
        party_size: booking.party_size,
        table_label: booking.table_label,
        guest_name: booking.guest_name,
        notification_logged: false,
      }
    : null)

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Harbor Lights Bistro</p>
          <h1>Table booking assistant</h1>
          <p className="lede">
            Talk or type. The brain is a hand-written state machine — no LLM,
            no paid speech APIs. Mic uses the browser Web Speech API when
            available.
          </p>
        </div>
        <div className="hero-actions">
          <span
            className={`conn-pill ${apiOnline === false ? 'down' : apiOnline ? 'up' : ''}`}
            title="API health"
            role="status"
          >
            {apiOnline === false ? 'API offline' : apiOnline ? 'API online' : 'Checking…'}
          </span>
          <label className="toggle">
            <input
              type="checkbox"
              checked={ttsOn}
              onChange={(e) => setTtsOn(e.target.checked)}
            />
            Speak replies
          </label>
          <button type="button" className="btn ghost" onClick={hardReset} disabled={busy}>
            Reset call
          </button>
          <a className="btn ghost" href="#/admin" title="Demo password: admin">
            Admin (pass: admin)
          </a>
        </div>
      </header>

      {apiOnline === false ? (
        <div className="banner warn" role="alert">
          Backend unreachable on port 8000. Start <code>RUN_APP.bat</code> or uvicorn, then Retry.
          <button type="button" className="btn ghost inline" onClick={boot} disabled={busy}>
            Retry
          </button>
        </div>
      ) : null}
      {error ? (
        <div className="banner error" role="alert">
          {error}
        </div>
      ) : null}

      <div className="layout">
        <section className="panel talk">
          <div className="panel-head">
            <h2>Conversation</h2>
            <span className={`pill state-${state}`}>{STATE_LABELS[state] || state}</span>
          </div>

          <div className="transcript" aria-live="polite">
            {busy && messages.length === 0 && !interim ? (
              <p className="empty">Connecting…</p>
            ) : null}
            {messages.length === 0 && !interim && !busy ? (
              <p className="empty">Starting the call…</p>
            ) : null}
            {messages.map((m) => (
              <div key={m.id} className={`bubble ${m.role}`}>
                <span className="who">{m.role === 'caller' ? 'You' : 'Host'}</span>
                <p>{m.text}</p>
              </div>
            ))}
            {interim ? (
              <div className="bubble caller interim">
                <span className="who">You (listening)</span>
                <p>{interim}</p>
              </div>
            ) : null}
            {busy && messages.length > 0 ? (
              <p className="empty tight thinking" aria-busy="true">
                Thinking…
              </p>
            ) : null}
            <div ref={bottomRef} />
          </div>

          <form className="composer" onSubmit={onSubmit}>
            <button
              type="button"
              className={`mic ${listening ? 'hot' : ''}`}
              onClick={toggleMic}
              onKeyDown={onMicKeyDown}
              disabled={busy || apiOnline === false}
              title={micOk ? 'Toggle microphone (Enter / Space)' : 'Mic not supported — type instead'}
              aria-pressed={listening}
              aria-label={listening ? 'Stop listening' : 'Start microphone'}
            >
              {listening ? 'Listening…' : 'Mic'}
            </button>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onComposerKeyDown}
              placeholder="Type a reply — e.g. tomorrow at 7 for 4"
              disabled={busy || apiOnline === false}
              autoComplete="off"
              aria-label="Message"
            />
            <button
              type="submit"
              className="btn primary"
              disabled={busy || !draft.trim() || apiOnline === false}
              aria-label="Send message"
            >
              {busy ? '…' : 'Send'}
            </button>
          </form>
          {!micOk ? (
            <p className="hint">
              SpeechRecognition isn’t in this browser (common on Firefox). Typed
              input always works; Chrome/Edge usually support the mic.
            </p>
          ) : (
            <p className="hint">
              Tip: try “Friday at 8 for 2”, then change your mind mid-flow. Mic:
              click or press Enter/Space.
            </p>
          )}
        </section>

        <aside className="side">
          <section className="panel">
            <div className="panel-head">
              <h2>Slots</h2>
            </div>
            {slotRows.length === 0 ? (
              <p className="empty tight">Nothing filled yet.</p>
            ) : (
              <dl className="slots">
                {slotRows.map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          {ticket ? (
            <section className="panel booking ticket" aria-label="Confirmation ticket">
              <div className="panel-head">
                <h2>Confirmation</h2>
              </div>
              <p className="conf">{ticket.code}</p>
              <p className="ticket-rest">{ticket.restaurant}</p>
              <ul>
                <li>{ticket.datetime_display || `${ticket.date} · ${ticket.time}`}</li>
                <li>
                  Party of {ticket.party_size} · table {ticket.table_label}
                </li>
                {ticket.guest_name ? <li>{ticket.guest_name}</li> : null}
              </ul>
              {ticket.notification_logged ? (
                <p className="ticket-note">Fake email/SMS logged locally (not sent).</p>
              ) : null}
            </section>
          ) : null}

          <section className="panel decisions">
            <div className="panel-head">
              <h2>Decision trace</h2>
              <span className="pill muted-pill">{decisions.length} turns</span>
            </div>
            {decisions.length === 0 ? (
              <p className="empty tight">Turns will show up here.</p>
            ) : (
              <ul className="log">
                {decisions.map((d, i) => (
                  <li key={d.id} className={i === 0 ? 'latest' : ''}>
                    <div className="log-top">
                      <strong className="action-tag">{d.action}</strong>
                      <span className="state-flow">
                        {d.state_before} → {d.state_after}
                      </span>
                    </div>
                    <div className="log-meta">
                      <span className="intent-chip">{d.intent}</span>
                      {d.caller ? <span className="caller-quote">“{d.caller}”</span> : null}
                    </div>
                    {d.slots_updated && Object.keys(d.slots_updated).length > 0 ? (
                      <div className="log-meta slots-chip">
                        {Object.entries(d.slots_updated).map(([k, v]) => (
                          <span key={k}>
                            {k}={String(v)}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {d.notes?.length ? (
                      <div className="log-meta notes">{d.notes.join(' · ')}</div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>

      <footer className="foot">
        Free stack · FastAPI brain · browser Web Speech · SQLite · rate-limited · no paid APIs
      </footer>
    </div>
  )
}

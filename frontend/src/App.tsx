import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'
import {
  ArrowRight,
  AudioLines,
  CalendarDays,
  Car,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Code2,
  CornerDownLeft,
  Headphones,
  Disc3,
  Droplets,
  Wrench,
  Info,
  Loader2,
  Mic,
  Pause,
  PhoneOff,
  Play,
  RotateCcw,
  Send,
  ShieldCheck,
  Square,
  Volume2,
  X,
} from 'lucide-react'
import { api, ApiError } from './types'
import type { Appointment, Capabilities, DecisionTrace, SessionData, TurnResult } from './types'
import { browserSpeechAvailable, englishVoices, VoiceController } from './voice'
import type { SpeechMode, VoiceStatus } from './voice'
import './styles.css'
import { TranscriptText } from './TranscriptText'

type Message = { role: 'caller' | 'assistant'; text: string; animate?: boolean }
const quickTests = [
  { label: 'Try a fully booked time', text: 'Book a brake inspection for my SUV tomorrow at 2 PM' },
  { label: 'Change details mid-call', text: 'Actually make that Tuesday at 11 AM' },
  { label: 'Try a negated intent', text: "Don't cancel it, reschedule it to Thursday" },
  { label: 'Ask about opening hours', text: 'What time do you close?' },
]
const statusText: Record<VoiceStatus, string> = {
  idle: 'Ready when you are',
  listening: 'Listening to you',
  processing: 'Checking the details',
  speaking: 'Your receptionist is speaking',
  paused: 'Call paused',
}
const serviceNames: Record<string, string> = {
  oil_change: 'Oil Change',
  tyre_rotation: 'Tyre Rotation',
  brake_inspection: 'Brake Inspection',
}

export function prettyTime(value?: string): string {
  if (!value) return '—'
  const [hour, minute] = value.split(':').map(Number)
  return `${hour % 12 || 12}:${String(minute).padStart(2, '0')} ${hour >= 12 ? 'PM' : 'AM'}`
}
function prettyDate(value?: string): string {
  return value
    ? new Date(value + 'T12:00:00+05:00').toLocaleDateString('en-GB', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        timeZone: 'Asia/Karachi',
      })
    : 'To be selected'
}
function historyMessages(data: SessionData): Message[] {
  return [
    { role: 'assistant', text: data.welcome },
    ...data.history.flatMap((item) => [
      { role: 'caller' as const, text: item.text },
      { role: 'assistant' as const, text: item.reply },
    ]),
  ]
}

export default function App() {
  const [view, setView] = useState<'reception' | 'appointments'>(() =>
    window.location.hash === '#appointments' ? 'appointments' : 'reception',
  )
  const viewHeading = useRef<HTMLHeadingElement>(null)
  const initialView = useRef(true)
  const [session, setSession] = useState<SessionData | null>(null)
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [trace, setTrace] = useState<DecisionTrace | null>(null)
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(false)
  const [status, setStatus] = useState<VoiceStatus>('idle')
  const [interim, setInterim] = useState('')
  const [callStarted, setCallStarted] = useState(false)
  const [mode, setMode] = useState<SpeechMode>('browser')
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [replyVoice, setReplyVoice] = useState('')
  const [resetPrompt, setResetPrompt] = useState(false)
  const sessionRef = useRef<SessionData | null>(null)
  const pending = useRef(false)
  const epoch = useRef(0)
  const pendingTurn = useRef<{ text: string; turn_id: string; revision: number } | null>(null)
  const voice = useRef<VoiceController | null>(null)
  const sendRef = useRef<(text: string) => void>(() => undefined)
  const transcriptBottom = useRef<HTMLDivElement>(null)
  const conversationHeading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    const changeView = () => {
      if (!['#appointments', '#reception'].includes(window.location.hash)) return
      const next = window.location.hash === '#appointments' ? 'appointments' : 'reception'
      if (next === 'appointments') voice.current?.pause()
      setView(next)
    }
    window.addEventListener('hashchange', changeView)
    return () => window.removeEventListener('hashchange', changeView)
  }, [])

  useEffect(() => {
    document.title =
      view === 'appointments' ? 'Your appointments — Bayline' : 'Bayline — Service reception'
    if (view === 'appointments') {
      setMessages((items) => items.map((message) => ({ ...message, animate: false })))
    }
    if (initialView.current) {
      initialView.current = false
      return
    }
    viewHeading.current?.focus({ preventScroll: true })
    window.scrollTo?.({ top: 0, behavior: 'instant' })
  }, [view])

  const navigate = (next: 'reception' | 'appointments', event?: MouseEvent<HTMLAnchorElement>) => {
    if (
      event &&
      (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0)
    )
      return
    event?.preventDefault()
    if (next === 'appointments') voice.current?.pause()
    window.location.hash = next
    setView(next)
  }

  const manageAppointment = (appointment: Appointment, intent: 'Reschedule' | 'Cancel') => {
    navigate('reception')
    void send(`${intent} my appointment reference ${appointment.reference}`)
  }

  const applySession = useCallback((data: SessionData) => {
    sessionRef.current = data
    setSession(data)
    setMessages(historyMessages(data))
    setTrace(data.history.at(-1)?.trace ?? null)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [data, caps] = await Promise.all([
        api<SessionData>('/api/session', {}),
        api<Capabilities>('/api/capabilities'),
      ])
      applySession(data)
      setCapabilities(caps)
    } catch {
      setError(
        'The reception could not connect. Check your connection and retry. A sleeping demo server may take about a minute to wake up.',
      )
    } finally {
      setLoading(false)
    }
  }, [applySession])

  useEffect(() => {
    const controller = new VoiceController({
      status: setStatus,
      interim: setInterim,
      text: (text) => sendRef.current(text),
      error: setError,
    })
    voice.current = controller
    void load()
    return () => {
      controller.end()
      voice.current = null
      epoch.current++
    }
  }, [load])

  useEffect(() => {
    const refresh = () => setVoices(englishVoices())
    refresh()
    window.speechSynthesis?.addEventListener?.('voiceschanged', refresh)
    return () => window.speechSynthesis?.removeEventListener?.('voiceschanged', refresh)
  }, [])

  useEffect(() => {
    const transcript = transcriptBottom.current?.parentElement
    if (transcript) transcript.scrollTop = transcript.scrollHeight
  }, [messages, interim])

  const send = useCallback(
    async (text: string, isRetry = false) => {
      const current = sessionRef.current
      if (pending.current || !current || !text.trim()) return
      pending.current = true
      setBusy(true)
      setError(null)
      const playbackGeneration = voice.current?.processing()
      const generation = epoch.current
      const payload =
        isRetry && pendingTurn.current
          ? pendingTurn.current
          : { text: text.trim(), revision: current.revision, turn_id: crypto.randomUUID() }
      pendingTurn.current = payload
      if (!isRetry)
        setMessages((items) => [...items, { role: 'caller', text: payload.text, animate: true }])
      setInput('')
      try {
        const result = await api<TurnResult>('/api/turn', payload)
        if (generation !== epoch.current) return
        const updated = {
          ...current,
          revision: result.revision,
          state: result.state,
          appointments: result.appointments,
        }
        sessionRef.current = updated
        setSession(updated)
        setMessages((items) => [...items, { role: 'assistant', text: result.reply, animate: true }])
        setTrace(result.trace)
        setRetry(false)
        pendingTurn.current = null
        if (result.trace.action === 'end_call') {
          setCallStarted(false)
          voice.current?.speak(result.reply, false, playbackGeneration)
          if (voice.current) voice.current.active = false
        } else voice.current?.speak(result.reply, voice.current.active, playbackGeneration)
      } catch (problem) {
        if (generation !== epoch.current) return
        voice.current?.pause()
        if (problem instanceof ApiError && (problem.status === 409 || problem.status === 401)) {
          pendingTurn.current = null
          setRetry(false)
          try {
            applySession(await api<SessionData>('/api/session', {}))
          } catch {
            /* Preserve recovery message. */
          }
          setError(
            'The conversation changed in another request or tab. Its latest state has been loaded. Please check the transcript before continuing.',
          )
        } else {
          setRetry(true)
          setError(
            problem instanceof Error && problem.name !== 'AbortError'
              ? problem.message
              : 'The request timed out. Retry this same turn safely; it will not create a duplicate booking.',
          )
        }
      } finally {
        if (generation === epoch.current) {
          pending.current = false
          setBusy(false)
        }
      }
    },
    [applySession],
  )
  useEffect(() => {
    sendRef.current = (text) => {
      void send(text)
    }
  }, [send])

  const reset = async () => {
    if (!sessionRef.current || pending.current) return
    voice.current?.end()
    setCallStarted(false)
    setResetPrompt(false)
    pending.current = true
    setBusy(true)
    epoch.current++
    try {
      applySession(
        await api<SessionData>('/api/session/reset', { revision: sessionRef.current.revision }),
      )
      pendingTurn.current = null
      setRetry(false)
      setError(null)
    } catch (problem) {
      setError(
        problem instanceof Error ? problem.message : 'Reset failed. Please reload and try again.',
      )
      try {
        applySession(await api<SessionData>('/api/session', {}))
      } catch {
        /* Keep reset error visible. */
      }
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void send(input)
  }
  const startCall = () => {
    if (!session) return
    setError(null)
    setCallStarted(true)
    const resumeDraft = ['COLLECTING', 'CONFIRMING', 'SELECTING_APPOINTMENT'].includes(
      session.state.phase ?? '',
    )
    voice.current?.start(
      resumeDraft ? (session.state.last_reply ?? session.welcome) : session.welcome,
    )
  }
  const endCall = () => {
    voice.current?.end()
    setCallStarted(false)
    void send('end call')
  }
  const switchMode = (value: SpeechMode) => {
    setMode(value)
    voice.current?.setMode(value)
    setError(null)
  }
  const disabled = busy || loading || !session || retry
  const slots = session?.state.slots
  const drafting = Boolean(
    slots &&
    Object.keys(slots).length &&
    !['COMPLETED', 'ENDED'].includes(session?.state.phase ?? ''),
  )
  const firstAppointment = session?.appointments[0]
  const draftService = slots?.service ? serviceNames[slots.service] : 'Choose a service'
  const lastReply = [...messages].reverse().find((item) => item.role === 'assistant')?.text
  const waveform = Array.from({ length: 49 }, (_, index) =>
    Math.round(10 + Math.sin(index * 1.9) ** 2 * (48 - Math.abs(index - 24) * 1.6)),
  )

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <a
          className="brand"
          href="#reception"
          onClick={(event) => navigate('reception', event)}
          aria-label="Bayline home"
        >
          <img src="/favicon.svg" alt="" width="38" height="38" />
          Bayline
          <span className="brand-divider" />
          <span className="brand-caption">Service reception</span>
        </a>
        <nav aria-label="Reception navigation">
          <a
            className={view === 'reception' ? 'nav-active' : ''}
            aria-current={view === 'reception' ? 'page' : undefined}
            href="#reception"
            onClick={(event) => navigate('reception', event)}
          >
            <Headphones size={17} /> Reception
          </a>
          <a
            className={view === 'appointments' ? 'nav-active' : ''}
            aria-current={view === 'appointments' ? 'page' : undefined}
            href="#appointments"
            onClick={(event) => navigate('appointments', event)}
          >
            <CalendarDays size={17} />
            Your appointments<span className="nav-count">{session?.appointments.length ?? 0}</span>
          </a>
        </nav>
        <div className="header-actions">
          <span className="demo-badge">
            <span />
            Isolated demo
          </span>
          <button
            className="text-button reset-button"
            disabled={busy || !session}
            onClick={() => setResetPrompt((value) => !value)}
          >
            <RotateCcw size={15} />
            Reset demo
          </button>
        </div>
      </header>

      <main id="main-content" className="main-content" tabIndex={-1}>
        {resetPrompt && (
          <div className="reset-notice" role="alert">
            <div>
              <strong>Reset this demo session?</strong>
              <p>
                Your demo appointments and conversation will be replaced with the initial fixtures.
                Other reviewers are unaffected.
              </p>
            </div>
            <button className="button secondary" onClick={() => setResetPrompt(false)}>
              Keep session
            </button>
            <button className="button" onClick={() => void reset()}>
              Reset Demo Session
            </button>
          </div>
        )}
        {error && (
          <div className="error-notice" role="alert">
            <Info size={19} />
            <span>{error}</span>
            {retry && (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => void send(pendingTurn.current?.text ?? '', true)}
              >
                Retry same turn
              </button>
            )}
            {!retry && (
              <button
                className="icon-button"
                aria-label="Dismiss message"
                onClick={() => setError(null)}
              >
                <X size={17} />
              </button>
            )}
          </div>
        )}

        {view === 'appointments' ? (
          <section className="appointments-view" aria-labelledby="appointments-title">
            <div className="appointments-intro">
              <div>
                <h1 id="appointments-title" ref={viewHeading} tabIndex={-1}>
                  Your appointments.
                </h1>
                <p>All your service visits, in one place. Times are shown in PKT.</p>
              </div>
              <button
                className="button"
                disabled={Boolean(disabled)}
                onClick={() => {
                  navigate('reception')
                  void send('I would like to book a service')
                }}
              >
                <Wrench size={17} /> Book a service <ArrowRight size={16} />
              </button>
            </div>
            <div className="appointments-owner">
              <span className="profile-avatar">AR</span>
              <div>
                <strong>Alex Rivera</strong>
                <span>Fictional demo profile · Only bookings from this session</span>
              </div>
            </div>
            {session?.state.phase === 'COMPLETED' && (
              <AppointmentChange appointment={session.state.appointment} action={trace?.action} />
            )}
            {loading ? (
              <div className="loading-state">
                <Loader2 className="spinner" size={20} />
                Loading your appointments…
              </div>
            ) : !session ? (
              <div className="empty-schedule">
                <p>Your appointments could not be loaded.</p>
                <button className="button" onClick={() => void load()}>
                  Retry connection
                </button>
              </div>
            ) : session.appointments.length ? (
              <div className="appointment-list">
                {session.appointments.map((appointment) => (
                  <article
                    className="booking-row"
                    key={appointment.id}
                    aria-label={`${appointment.service_name} booking ${appointment.reference}`}
                  >
                    <div className="booking-icon">
                      <ServiceIcon service={appointment.service} size={28} />
                    </div>
                    <div className="booking-description">
                      <span className="status-badge">
                        <CheckCircle2 size={12} /> Confirmed
                      </span>
                      <h2>{appointment.service_name}</h2>
                      <p>
                        <Car size={15} />
                        {appointment.vehicle === 'suv' ? 'SUV' : 'Car'}
                        <span>·</span>
                        {appointment.minutes} minutes
                      </p>
                      <span className="booking-reference">
                        Reference <code>{appointment.reference}</code>
                      </span>
                    </div>
                    <div className="booking-when">
                      <strong>{prettyTime(appointment.time)}</strong>
                      <span>{prettyDate(appointment.date)}</span>
                      <small>Pakistan Standard Time</small>
                    </div>
                    <div className="booking-actions">
                      <button
                        className="button secondary"
                        disabled={Boolean(disabled)}
                        onClick={() => manageAppointment(appointment, 'Reschedule')}
                      >
                        <CalendarDays size={16} />
                        Reschedule
                      </button>
                      <button
                        className="text-button cancel-appointment"
                        disabled={Boolean(disabled)}
                        onClick={() => manageAppointment(appointment, 'Cancel')}
                      >
                        <X size={15} />
                        Cancel appointment
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-schedule">
                <CalendarDays size={44} strokeWidth={1.2} />
                <h2>No upcoming appointments.</h2>
                <p>Choose a service at reception. We’ll help you find a time.</p>
                <button
                  className="button"
                  disabled={Boolean(disabled)}
                  onClick={() => {
                    navigate('reception')
                    void send('I would like to book a service')
                  }}
                >
                  Book your first service
                  <ArrowRight size={16} />
                </button>
              </div>
            )}
            <p className="management-note">
              <ShieldCheck size={17} />
              Changes are reviewed at reception. Nothing is rescheduled or cancelled until you
              confirm.
            </p>
            <a
              className="back-link"
              href="#reception"
              onClick={(event) => navigate('reception', event)}
            >
              <Headphones size={17} />
              {callStarted ? 'Return to your paused call' : 'Back to reception'}
              <ArrowRight size={16} />
            </a>
          </section>
        ) : (
          <>
            <div className="reception-grid">
              <section className="call-workspace" aria-label="Voice reception">
                <div className="intro-row">
                  <div>
                    <h1 ref={viewHeading} tabIndex={-1}>
                      Good service.
                      <br />
                      <span>Starts with a conversation.</span>
                    </h1>
                    <p>
                      Tell us what your vehicle needs.
                      <br className="mobile-break" /> We'll find a time that works.
                    </p>
                  </div>
                  <div className="reception-symbol" aria-hidden="true">
                    <Headphones size={24} strokeWidth={1.4} />
                  </div>
                </div>
                <div className="service-choices" aria-label="Choose a service">
                  {Object.entries(capabilities?.services ?? {}).map(([key, service]) => (
                    <button
                      key={key}
                      disabled={Boolean(disabled)}
                      onClick={() => void send(`I would like to book a ${service.name}`)}
                    >
                      <ServiceIcon service={key} size={20} />
                      <span>
                        {service.name}
                        <small>{service.minutes} min</small>
                      </span>
                      <ArrowRight size={14} />
                    </button>
                  ))}
                </div>
                <div className="call-stage" data-status={status}>
                  <div className="stage-topline">
                    <span className="assistant-label">
                      <span
                        className={'availability-dot ' + (status === 'listening' ? 'live' : '')}
                      />
                      Bayline receptionist
                    </span>
                    <label className="source-select">
                      <Mic size={14} />
                      <span className="sr-only">Speech input source</span>
                      <select
                        value={mode}
                        disabled={busy}
                        onChange={(event) => switchMode(event.target.value as SpeechMode)}
                      >
                        <option value="browser">Browser speech</option>
                        <option value="server" disabled={!capabilities?.server_stt}>
                          Server speech{!capabilities?.server_stt ? ' · not configured' : ''}
                        </option>
                      </select>
                      <ChevronDown size={12} />
                    </label>
                  </div>
                  <div className="waveform" aria-hidden="true">
                    {waveform.map((height, index) => (
                      <span
                        key={index}
                        style={{ height: `${height}px`, animationDelay: `${index * -0.043}s` }}
                      />
                    ))}
                  </div>
                  <p className="call-status" role="status">
                    {busy ? statusText.processing : statusText[status]}
                  </p>
                  <p className="call-hint">
                    {status === 'listening'
                      ? 'Speak naturally. We’ll listen, then reply.'
                      : status === 'speaking'
                        ? 'You can interrupt playback at any time.'
                        : status === 'processing'
                          ? 'Your Python receptionist is working.'
                          : 'Book, reschedule, or cancel. Just ask.'}
                  </p>
                  {!callStarted ? (
                    <div className="call-entry-actions">
                      <button
                        className="start-call button"
                        disabled={Boolean(disabled)}
                        onClick={startCall}
                      >
                        <Mic size={19} />
                        Start a call
                        <ArrowRight size={17} />
                      </button>
                      <button
                        className="text-button type-instead"
                        disabled={Boolean(disabled)}
                        onClick={() => document.getElementById('message-input')?.focus()}
                      >
                        Type instead
                        <CornerDownLeft size={14} />
                      </button>
                    </div>
                  ) : (
                    <div className="active-controls">
                      <button
                        className="button"
                        disabled={busy || retry}
                        onClick={() => {
                          if (status === 'paused' || status === 'idle') {
                            setError(null)
                            voice.current?.resume()
                          } else voice.current?.pause()
                        }}
                      >
                        {status === 'paused' || status === 'idle' ? (
                          <Play size={16} />
                        ) : (
                          <Pause size={16} />
                        )}
                        {status === 'paused' || status === 'idle' ? 'Resume call' : 'Pause'}
                      </button>
                      {status === 'speaking' && (
                        <button
                          className="button secondary"
                          onClick={() => voice.current?.interrupt()}
                        >
                          <Mic size={16} />
                          Interrupt
                        </button>
                      )}
                      {mode === 'server' && status === 'listening' && (
                        <button
                          className="button secondary"
                          onClick={() => voice.current?.stopRecording()}
                        >
                          <Square size={13} />
                          Finish speaking
                        </button>
                      )}
                      <button
                        className="button end-call"
                        disabled={busy || retry}
                        onClick={endCall}
                      >
                        <PhoneOff size={16} />
                        End call
                      </button>
                    </div>
                  )}
                  <p className="speech-note">
                    {browserSpeechAvailable() || mode === 'server'
                      ? 'English · Microphone access required'
                      : 'Voice recognition is unavailable here. Try Chrome or use the text box.'}
                  </p>
                  <label className="reply-voice-select">
                    <Volume2 size={14} />
                    <span>Reply voice</span>
                    <select
                      aria-label="Reply voice"
                      value={replyVoice}
                      disabled={busy || status === 'speaking'}
                      onChange={(event) => {
                        setReplyVoice(event.target.value)
                        if (voice.current) voice.current.voiceURI = event.target.value
                      }}
                    >
                      <option value="">Best available English voice</option>
                      {voices.map((item) => (
                        <option key={item.voiceURI} value={item.voiceURI}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={12} />
                  </label>
                </div>

                <div className="conversation-heading">
                  <h2 ref={conversationHeading} tabIndex={-1}>
                    Conversation
                  </h2>
                  <span className="live-caption">
                    <span />
                    {callStarted
                      ? 'Live transcript'
                      : messages.length > 1
                        ? 'Conversation transcript'
                        : 'Ready for your first request'}
                  </span>
                  <button
                    className="icon-button"
                    aria-label="Replay last reply"
                    title="Replay last reply"
                    disabled={!lastReply || busy}
                    onClick={() => lastReply && voice.current?.speak(lastReply, false)}
                  >
                    <Volume2 size={16} />
                  </button>
                  {status === 'speaking' && !callStarted && (
                    <button
                      className="icon-button stop-reply"
                      aria-label="Stop reply"
                      title="Stop reply"
                      onClick={() => voice.current?.interrupt()}
                    >
                      <Square size={15} />
                    </button>
                  )}
                </div>
                {session?.state.phase === 'COMPLETED' && (
                  <AppointmentChange
                    appointment={session.state.appointment}
                    action={trace?.action}
                    onView={() => navigate('appointments')}
                  />
                )}
                <div
                  className="transcript"
                  role="log"
                  aria-live="polite"
                  aria-label="Conversation transcript"
                  aria-relevant="additions"
                >
                  {loading ? (
                    <div className="loading-state">
                      <Loader2 className="spinner" size={20} />
                      Preparing your demo reception…
                    </div>
                  ) : (
                    messages.map((message, index) => (
                      <div key={index} className={'message ' + message.role}>
                        <div className="message-avatar" aria-hidden="true">
                          {message.role === 'caller' ? 'AR' : <AudioLines size={14} />}
                        </div>
                        <div className="message-content">
                          <span className="message-name">
                            {message.role === 'caller' ? 'You' : 'Bayline'}
                          </span>
                          <p>
                            <TranscriptText text={message.text} animate={message.animate} />
                          </p>
                        </div>
                        {index === messages.length - 1 && message.role === 'assistant' && (
                          <Check
                            size={14}
                            className="message-delivered"
                            aria-label="Reply received"
                          />
                        )}
                      </div>
                    ))
                  )}
                  {interim && (
                    <div className="interim" aria-live="off">
                      <Mic size={13} />
                      <TranscriptText text={interim} animate live />
                    </div>
                  )}
                  {busy && (
                    <div className="thinking">
                      <span />
                      <span />
                      <span />
                      <span className="sr-only">Processing your request</span>
                    </div>
                  )}
                  <div ref={transcriptBottom} />
                </div>
                {!session && !loading && (
                  <button className="button reconnect" onClick={() => void load()}>
                    Reconnect to reception
                  </button>
                )}
                <form className="composer" onSubmit={submit}>
                  <label className="sr-only" htmlFor="message-input">
                    Type your message
                  </label>
                  <input
                    id="message-input"
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    maxLength={1000}
                    disabled={Boolean(disabled)}
                    placeholder="Prefer to type? Send a message…"
                    autoComplete="off"
                  />
                  <span className="composer-shortcut" aria-hidden="true">
                    <CornerDownLeft size={13} />
                  </span>
                  <button
                    className="send-button"
                    disabled={Boolean(disabled) || !input.trim()}
                    aria-label="Send message"
                  >
                    <Send size={18} />
                  </button>
                </form>
                <div className="composer-footer">
                  <ShieldCheck size={12} />
                  <span>Fictional caller. No personal details needed.</span>
                  <span className="timezone-label">Pakistan time · PKT</span>
                </div>
              </section>

              <aside className="appointment-panel" aria-label="Next appointment summary">
                <div className="panel-heading">
                  <h2>
                    {drafting
                      ? session?.state.intent === 'CANCEL'
                        ? 'Cancellation to confirm'
                        : 'Your proposed service'
                      : 'Your next appointment'}
                  </h2>
                  <span className={'status-badge ' + (drafting ? 'pending' : '')}>
                    {loading
                      ? 'Loading'
                      : !session
                        ? 'Offline'
                        : drafting
                          ? 'Not confirmed'
                          : firstAppointment
                            ? 'Confirmed'
                            : 'No bookings'}
                  </span>
                </div>
                {loading ? (
                  <div className="loading-state">
                    <Loader2 className="spinner" size={20} />
                    Loading your schedule…
                  </div>
                ) : !session ? (
                  <div className="no-appointments">
                    <p>Reconnect to view your appointments.</p>
                  </div>
                ) : drafting ? (
                  <>
                    <div className="appointment-time draft-time">{prettyTime(slots?.time)}</div>
                    <p className="appointment-day">{prettyDate(slots?.date)}</p>
                    <AppointmentDetails
                      service={draftService}
                      vehicle={slots?.vehicle}
                      minutes={
                        slots?.service === 'brake_inspection' ? 60 : slots?.service ? 30 : undefined
                      }
                    />
                    <div className="confirmation-note">
                      <Info size={16} />
                      <span>
                        {session?.state.phase === 'CONFIRMING'
                          ? 'Review the details, then say yes to confirm.'
                          : 'We’re collecting the details. Nothing has changed yet.'}
                      </span>
                    </div>
                    {session?.state.phase === 'CONFIRMING' && (
                      <div className="confirm-actions">
                        <button
                          className="button"
                          disabled={Boolean(disabled)}
                          onClick={() => void send('yes')}
                        >
                          <Check size={16} />
                          Confirm{' '}
                          {session.state.intent === 'CANCEL' ? 'cancellation' : 'appointment'}
                        </button>
                        <button
                          className="text-button"
                          disabled={Boolean(disabled)}
                          onClick={() => void send('no')}
                        >
                          No, keep things as they are
                        </button>
                      </div>
                    )}
                  </>
                ) : firstAppointment ? (
                  <>
                    <div className="appointment-time">{prettyTime(firstAppointment.time)}</div>
                    <p className="appointment-day">{prettyDate(firstAppointment.date)}</p>
                    <AppointmentDetails
                      service={firstAppointment.service_name}
                      vehicle={firstAppointment.vehicle}
                      minutes={firstAppointment.minutes}
                    />
                    <div className="reference-row">
                      <span>Booking reference</span>
                      <code>{firstAppointment.reference}</code>
                    </div>
                    <div className="appointment-actions">
                      <button
                        className="button secondary"
                        disabled={Boolean(disabled)}
                        onClick={() =>
                          void send(
                            `Reschedule my appointment reference ${firstAppointment.reference}`,
                          )
                        }
                      >
                        <CalendarDays size={15} />
                        Reschedule
                      </button>
                      <button
                        className="text-button cancel-appointment"
                        disabled={Boolean(disabled)}
                        onClick={() =>
                          void send(`Cancel my appointment reference ${firstAppointment.reference}`)
                        }
                      >
                        Cancel appointment
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="no-appointments">
                    <CalendarDays size={32} strokeWidth={1.2} />
                    <h3>A clear schedule.</h3>
                    <p>Ask the receptionist to book your next service.</p>
                    <button
                      className="button secondary"
                      disabled={Boolean(disabled)}
                      onClick={() => void send('I would like to book a service')}
                    >
                      Book a service
                      <ArrowRight size={14} />
                    </button>
                  </div>
                )}
                {Boolean(session?.appointments.length) && drafting && (
                  <div className="existing-booking-note">
                    <CheckCircle2 size={15} />
                    <span>
                      {session?.appointments.length} existing appointment
                      {session?.appointments.length === 1 ? '' : 's'} remain unchanged until
                      confirmation.
                    </span>
                  </div>
                )}
                {(session?.appointments.length ?? 0) > (drafting ? 0 : 1) && (
                  <div className="more-appointments">
                    <h3>{drafting ? 'Your current bookings' : 'Also on your calendar'}</h3>
                    {session?.appointments.slice(drafting ? 0 : 1).map((appointment) => (
                      <SmallAppointment
                        key={appointment.id}
                        appointment={appointment}
                        disabled={Boolean(disabled)}
                        onSelect={() =>
                          void send(`Reschedule my appointment reference ${appointment.reference}`)
                        }
                      />
                    ))}
                  </div>
                )}
                <div className="workshop-info">
                  <h3>
                    <Clock3 size={15} />
                    Workshop hours
                  </h3>
                  <div>
                    <span>Monday – Saturday</span>
                    <strong>9 AM – 6 PM</strong>
                  </div>
                  <div>
                    <span>Sunday</span>
                    <span>Closed</span>
                  </div>
                  <p>Two service bays · Book up to 14 days ahead</p>
                </div>
                <div className="profile-note">
                  <span className="profile-avatar">AR</span>
                  <div>
                    <strong>Alex Rivera</strong>
                    <span>Your fictional demo profile</span>
                  </div>
                  <ShieldCheck size={17} />
                </div>
                <a
                  className="view-all-link"
                  href="#appointments"
                  onClick={(event) => navigate('appointments', event)}
                >
                  View all appointments <ArrowRight size={16} />
                </a>
              </aside>
            </div>

            <section className="quick-section" aria-labelledby="quick-title">
              <div className="section-heading">
                <h2 id="quick-title">Take it for a test drive.</h2>
                <span>One click sends the exact utterance.</span>
              </div>
              <div className="quick-grid">
                {quickTests.map((item) => (
                  <button
                    key={item.text}
                    className="quick-chip"
                    disabled={Boolean(disabled)}
                    title={item.label}
                    onClick={() => {
                      void send(item.text)
                      conversationHeading.current?.focus({ preventScroll: true })
                      conversationHeading.current?.scrollIntoView?.({
                        behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
                          ? 'instant'
                          : 'smooth',
                        block: 'center',
                      })
                    }}
                  >
                    <span>{item.text}</span>
                    <ArrowRight size={15} />
                  </button>
                ))}
              </div>
            </section>

            <details className="inspector">
              <summary>
                <span className="inspector-icon">
                  <Code2 size={18} />
                </span>
                <div>
                  <h2>How the assistant decided</h2>
                  <p>Real rules. Visible state. Every turn explained.</p>
                </div>
                <span className="brain-badge">Python · No LLM decisions</span>
                <ChevronDown className="inspector-chevron" size={18} />
              </summary>
              <div className="inspector-content">
                {trace ? (
                  <>
                    <div className="trace-overview">
                      <div>
                        <span>Conversation state</span>
                        <strong>
                          {trace.from_state}
                          <ArrowRight size={13} />
                          {trace.to_state}
                        </strong>
                      </div>
                      <div>
                        <span>Detected intent</span>
                        <strong>{trace.intent ?? 'Clarification'}</strong>
                      </div>
                      <div>
                        <span>Action taken</span>
                        <strong>
                          {trace.action === 'none' ? 'Awaiting caller' : trace.action}
                        </strong>
                      </div>
                      <div>
                        <span>Session revision</span>
                        <strong>{session?.revision}</strong>
                      </div>
                    </div>
                    <div className="trace-details">
                      <div>
                        <h3>Matched rules</h3>
                        {trace.rules.length ? (
                          trace.rules.map((rule, index) => <code key={index}>{rule}</code>)
                        ) : (
                          <p>No rule matched; a clarification was requested.</p>
                        )}
                      </div>
                      <div>
                        <h3>Extracted this turn</h3>
                        {Object.keys(trace.extracted).length ? (
                          Object.entries(trace.extracted).map(([key, value]) => (
                            <p key={key}>
                              <span>{key}</span>
                              <strong>{value}</strong>
                            </p>
                          ))
                        ) : (
                          <p>No new appointment details.</p>
                        )}
                      </div>
                      <div>
                        <h3>Validation</h3>
                        {trace.validation.length ? (
                          trace.validation.map((value, index) => <p key={index}>{value}</p>)
                        ) : (
                          <p>No availability check needed this turn.</p>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="inspector-empty">
                    <Code2 size={23} />
                    <p>
                      Send a request to inspect the matched Python rules, extracted details, and
                      resulting action.
                    </p>
                  </div>
                )}
              </div>
            </details>
          </>
        )}

        <footer className="page-footer">
          <span>
            <img src="/favicon.svg" alt="" width="17" height="17" />
            Bayline<span className="footer-dot">·</span>Built to listen. Designed to explain.
          </span>
          <span>
            <Info size={13} />
            An isolated simulation. All appointments are fictional.
          </span>
        </footer>
      </main>
    </div>
  )
}

function AppointmentChange({
  appointment,
  action,
  onView,
}: {
  appointment?: Appointment
  action?: string
  onView?: () => void
}) {
  const labels: Record<string, string> = {
    booked: 'Appointment booked',
    rescheduled: 'Appointment rescheduled',
    cancelled: 'Appointment cancelled',
  }
  const label = action && labels[action]
  if (!appointment || !label) return null
  return (
    <div className="schedule-update" role="status" aria-label="Schedule update">
      <CheckCircle2 size={18} />
      <div>
        <strong>{label}</strong>
        <span>
          {appointment.service_name} · {prettyDate(appointment.date)} at{' '}
          {prettyTime(appointment.time)}
        </span>
        <small>
          Reference {appointment.reference}
          {action === 'cancelled'
            ? ' · Removed from your upcoming appointments.'
            : ' · Your schedule is up to date.'}
        </small>
      </div>
      {onView && (
        <button className="text-button" onClick={onView}>
          View updated schedule
          <ArrowRight size={14} />
        </button>
      )}
    </div>
  )
}

function ServiceIcon({ service, size = 20 }: { service: string; size?: number }) {
  const Icon = service === 'oil_change' ? Droplets : service === 'tyre_rotation' ? Disc3 : Wrench
  return <Icon size={size} strokeWidth={1.6} aria-hidden="true" />
}

function AppointmentDetails({
  service,
  vehicle,
  minutes,
}: {
  service: string
  vehicle?: string
  minutes?: number
}) {
  return (
    <dl className="appointment-details">
      <div>
        <dt>
          <Car size={15} />
          Service
        </dt>
        <dd>{service}</dd>
      </div>
      <div>
        <dt>Vehicle</dt>
        <dd>{vehicle ? (vehicle === 'suv' ? 'SUV' : 'Car') : 'To be selected'}</dd>
      </div>
      <div>
        <dt>
          <Clock3 size={14} />
          Duration
        </dt>
        <dd>{minutes ? `${minutes} minutes` : 'Depends on service'}</dd>
      </div>
      <div>
        <dt>Time zone</dt>
        <dd>
          Pakistan Standard Time<span>UTC +05:00</span>
        </dd>
      </div>
    </dl>
  )
}

function SmallAppointment({
  appointment,
  disabled,
  onSelect,
}: {
  appointment: Appointment
  disabled: boolean
  onSelect(): void
}) {
  return (
    <button className="small-appointment" disabled={disabled} onClick={onSelect}>
      <CalendarDays size={17} />
      <span>
        <strong>{appointment.service_name}</strong>
        <span>
          {prettyDate(appointment.date)} · {prettyTime(appointment.time)}
        </span>
      </span>
      <ArrowRight size={14} />
    </button>
  )
}

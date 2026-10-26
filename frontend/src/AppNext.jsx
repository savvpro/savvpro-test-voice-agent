import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createSession, endSession, getHealth, getSession, sendTurn } from './services/redeliverApi'
import VoiceVisualizer from './components/VoiceVisualizer'
import SiteHome from './components/SiteHome'
import useFx from './hooks/useFx'
import './AppNext.css'

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
const views = [
  { id: 'overview', label: 'Overview', icon: '◫' },
  { id: 'conversations', label: 'Conversations', icon: '≋' },
  { id: 'agents', label: 'Agent setup', icon: '◉' },
  { id: 'settings', label: 'Preferences', icon: '⌘' },
]

function ThemeButton({ theme, onToggle }) {
  return <button className="theme-button" onClick={onToggle} type="button" aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}><span aria-hidden="true">{theme === 'dark' ? '☼' : '◐'}</span><span>{theme === 'dark' ? 'Light' : 'Dark'} mode</span></button>
}

function FormattedReply({ text }) {
  return <div className="formatted-reply">{text.split(/\n\s*\n/).map((block, i) => {
    const lines = block.split(/\r?\n/)
    const list = lines.every((line) => /^\s*[-*]\s+/.test(line))
    const inline = (line, key) => line.split(/(\*\*[^*]+\*\*)/g).map((part, n) => part.startsWith('**') ? <strong key={`${key}-${n}`}>{part.slice(2, -2)}</strong> : part)
    return list ? <ul key={i}>{lines.map((line, j) => <li key={j}>{inline(line.replace(/^\s*[-*]\s+/, ''), `${i}-${j}`)}</li>)}</ul> : <p key={i}>{lines.map((line, j) => <span key={j}>{j > 0 && <br />}{inline(line, `${i}-${j}`)}</span>)}</p>
  })}</div>
}

function StatusDot({ online }) { return <span className={`status-dot ${online ? 'online' : 'offline'}`} aria-hidden="true" /> }

function CallExperience({ onBack, backend, sessionId, stateName, voiceState, messages, trace, notice, input, setInput, busy, listening, micEnabled, speaking, voiceReplies, setVoiceReplies, onStart, onEnd, onListen, onSubmit, onInterrupt, onReplay, onRefresh, onToggleTheme, analyser, theme }) {
  const lastAssistantReply = [...messages].reverse().find((message) => message.role === 'assistant')?.text
  return <div className="call-page">
    <header className="call-page-nav"><button className="back-link" type="button" onClick={onBack}>← <span>Back to REDELIVER</span></button><a className="brand" href="#call"><span className="brand-symbol">R<span>/</span>D</span><span>REDELIVER / VOICE</span></a><div className="call-page-nav-actions"><ThemeButton theme={theme} onToggle={onToggleTheme} /><span className="call-connection"><StatusDot online={backend === 'online'} />{backend === 'online' ? 'API CONNECTED' : backend === 'checking' ? 'CONNECTING' : 'API OFFLINE'}{backend === 'offline' && <button type="button" onClick={onRefresh}>Retry</button>}</span></div></header>
    <main className="call-page-main" id="call">
      <div className="call-page-heading"><p className="eyebrow">PAKISTAN / PKT · LIVE VOICE DEMO</p><h1>A clear next step,<br />spoken out loud.</h1><p>Talk to REDELIVER about your missed parcel. Your replies go to the backend, which handles verification and delivery actions.</p></div>
      <div className="call-page-grid">
        <section className="call-page-visual" aria-label="Voice status"><div className="call-page-visual-head"><span>REDELIVER VOICE</span><span><StatusDot online={Boolean(sessionId)} />{sessionId ? stateName.replaceAll('_', ' ') : 'READY'}</span></div><VoiceVisualizer state={voiceState} analyser={analyser} theme={theme} /><div className="call-page-visual-foot"><span>{listening ? 'MICROPHONE ACTIVE' : speaking ? 'SPEAKING THE BACKEND REPLY' : busy ? 'PROCESSING YOUR TURN' : 'VOICE EXPERIENCE / EN-PK'}</span><span>01 of 04</span></div><div className="call-capability-legend"><span><i className="legend-idle" />Ready</span><span><i className="legend-listening" />Listening</span><span><i className="legend-processing" />Processing</span><span><i className="legend-speaking" />Speaking</span></div></section>
        <section className="call-page-console" aria-label="Voice conversation"><div className="call-console-title"><div><p className="eyebrow">YOUR PARCEL SUPPORT LINE</p><h2>{sessionId ? 'You’re on the line.' : 'The line is ready.'}</h2></div><span className="state-badge"><StatusDot online={Boolean(sessionId)} />{sessionId ? stateName.replaceAll('_', ' ').toLowerCase() : 'no active session'}</span></div><div className="call-page-transcript" aria-live="polite" aria-label="Voice call transcript">{messages.length ? <div className="message-list">{messages.map((message, index) => <article className={`message ${message.role}`} key={`${index}-${message.time?.getTime?.() || index}`}>{message.role !== 'system' && <div className="message-meta"><span>{message.role === 'caller' ? 'YOU' : 'REDELIVER'}</span>{message.time && <time>{message.time.toLocaleTimeString('en-PK', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Karachi' })}</time>}</div>}{message.role === 'assistant' ? <FormattedReply text={message.text} /> : <p>{message.text}</p>}</article>)}{busy && <div className="typing-indicator"><i /><i /><i /><span>Working it out</span></div>}</div> : <div className="call-page-empty"><span className="empty-serial">VOICE SESSION / 01</span><h3>Start with your<br />tracking ID.</h3><p>REDELIVER will welcome you and ask for your tracking ID.</p><button className="primary-button" onClick={onStart} type="button" disabled={busy || backend !== 'online'}>{busy ? 'Connecting…' : 'Start voice call'}<span aria-hidden="true">↗</span></button></div>}{!sessionId && messages.length > 0 && <div className="call-restart"><button className="primary-button" onClick={onStart} type="button" disabled={busy || backend !== 'online'}>Start another call <span aria-hidden="true">↗</span></button></div>}</div>{notice && <p className="inline-notice" role="status">{notice}</p>}{sessionId && <div className="call-page-controls"><div className="call-page-control-head"><span>{listening ? 'LISTENING NOW' : busy ? 'PLEASE WAIT' : speaking ? 'REDELIVER IS SPEAKING' : 'YOUR TURN'}</span><div className="control-actions">{lastAssistantReply && <button className="voice-toggle" type="button" onClick={() => onReplay(lastAssistantReply)}>REPLAY</button>}{speaking && <button className="voice-toggle" type="button" onClick={onInterrupt}>STOP SPEAKING</button>}<button className="voice-toggle" type="button" onClick={() => setVoiceReplies((enabled) => !enabled)} aria-pressed={voiceReplies}>{voiceReplies ? 'VOICE ON' : 'VOICE OFF'}</button></div></div><form className="composer" onSubmit={onSubmit}><label className="sr-only" htmlFor="call-input">Say or type your response</label><textarea id="call-input" value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) onSubmit(event) }} placeholder="Say what you need…" maxLength={2000} disabled={busy} rows={1} /><button className={`mic-button ${micEnabled ? 'listening' : ''}`} type="button" onClick={onListen} disabled={busy && !micEnabled} aria-label={micEnabled ? 'Turn microphone off' : 'Turn microphone on'}>{micEnabled ? 'MIC ON' : 'MIC'}</button><button className="send-button" type="submit" disabled={busy || !input.trim()} aria-label="Send message">↑</button></form><div className="composer-foot"><span>{micEnabled ? (listening ? 'MIC ON · SPEAK ANYTIME' : 'MIC ON · RECONNECTING') : 'ENTER TO SEND · MIC USES EN-PK'}</span><span>{input.length} / 2000</span></div><button className="end-call-link" type="button" onClick={onEnd} disabled={busy}>End this call</button></div>}</section>
      </div>
      {trace && <section className="call-trace"><span className="eyebrow">BACKEND DECISION</span><div><span>Intent <b>{trace.intent || 'none'}</b></span><span>Confidence <b>{typeof trace.intent_confidence === 'number' ? `${Math.round(trace.intent_confidence * 100)}%` : 'none'}</b></span><span>State <b>{trace.state_before || 'none'} → {trace.state_after || 'none'}</b></span></div></section>}
      <p className="call-page-note">Speech recognition and spoken replies depend on your browser. You can always type your response. This is a local prototype; its session data is held in backend memory.</p>
    </main>
  </div>
}

function Dashboard({ view, setView, onBack, backend, sessionId, stateName, voiceState, messages, trace, sessionSnapshot, onRefresh, busy, theme, onToggleTheme, voiceReplies, onToggleVoice }) {
  const turns = messages.filter((message) => message.role !== 'system')
  const title = views.find((item) => item.id === view)?.label || 'Overview'
  const sessionLink = sessionId ? sessionId.slice(0, 8) : 'No active session'

  return <div className="dashboard-shell">
    <aside className="dashboard-sidebar">
      <a href="#home" className="brand dashboard-brand" onClick={(event) => { event.preventDefault(); onBack() }}><span className="brand-symbol">R<span>/</span>D</span><span>REDELIVER</span></a>
      <div className="workspace-label">WORKSPACE <span>DEMO</span></div>
      <nav className="dashboard-nav" aria-label="Dashboard navigation">
        {views.map((item) => <button key={item.id} type="button" className={view === item.id ? 'active' : ''} onClick={() => setView(item.id)}><span className="nav-glyph">{item.icon}</span>{item.label}</button>)}
      </nav>
      <div className="sidebar-spacer" />
      <div className="sidebar-health"><StatusDot online={backend === 'online'} /><div><b>{backend === 'online' ? 'API connected' : backend === 'checking' ? 'Checking API' : 'API unavailable'}</b><span>Local service · PKT</span></div></div>
      <button className="back-link" type="button" onClick={onBack}>← Back to REDELIVER</button>
    </aside>
    <main className="dashboard-main">
      <header className="dashboard-topbar"><div className="breadcrumb"><span>Workspace</span><b>/</b><strong>{title}</strong></div><div className="dashboard-actions"><span className="live-label"><StatusDot online={backend === 'online'} />{backend === 'online' ? 'Service live' : 'Service offline'}</span><ThemeButton theme={theme} onToggle={onToggleTheme} /><span className="operator-chip">RD</span></div></header>
      <div className="dashboard-content">
        <div className="page-heading"><div><p className="eyebrow">REDELIVER / OPERATIONS</p><h1>{title}</h1><p className="page-subtitle">A clear view of the live parcel support demo.</p></div><button className="outline-button" type="button" onClick={onRefresh} disabled={busy}>↻ <span>{busy ? 'Refreshing' : 'Refresh session'}</span></button></div>
        {view === 'overview' && <>
          <section className="metric-grid" aria-label="Live session metrics">
            <article className="metric-panel"><div className="metric-top"><span>API status</span><span className="metric-icon">↗</span></div><strong className="metric-value metric-status"><StatusDot online={backend === 'online'} />{backend === 'online' ? 'Connected' : backend === 'checking' ? 'Checking' : 'Unavailable'}</strong><p>Live response from <code>/health</code></p></article>
            <article className="metric-panel"><div className="metric-top"><span>Current conversation</span><span className="metric-icon">◉</span></div><strong className="metric-value">{sessionId ? 'In progress' : 'None'}</strong><p>{sessionId ? `Session ${sessionLink}…` : 'Start a call from the product page'}</p></article>
            <article className="metric-panel"><div className="metric-top"><span>Turns in this session</span><span className="metric-icon">≋</span></div><strong className="metric-value">{turns.length}</strong><p>Caller and assistant turns held in this page</p></article>
          </section>
          <section className="dashboard-split">
            <article className="surface-panel activity-panel"><div className="section-title"><div><span className="eyebrow">SESSION ACTIVITY</span><h2>Latest turns</h2></div><button className="text-button" type="button" onClick={() => setView('conversations')}>View conversation →</button></div>
              {turns.length ? <ol className="activity-list">{turns.slice(-5).reverse().map((message, index) => <li key={`${message.time?.getTime?.() || index}-${index}`}><span className={`activity-marker ${message.role}`} /> <div><b>{message.role === 'caller' ? 'Caller' : 'REDELIVER'}</b><p>{message.text}</p></div><time>{message.time?.toLocaleTimeString('en-PK', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Karachi' })}</time></li>)}</ol> : <div className="empty-state"><span className="empty-icon">≋</span><h3>No session turns yet</h3><p>Start a demo call to see the verified transcript here.</p><button type="button" className="text-button" onClick={onBack}>Open voice demo →</button></div>}
            </article>
            <article className="surface-panel state-panel"><div className="section-title"><div><span className="eyebrow">LIVE STATE</span><h2>Assistant status</h2></div><span className="state-badge"><StatusDot online={Boolean(sessionId)} />{sessionId ? stateName.replaceAll('_', ' ').toLowerCase() : 'idle'}</span></div><div className="state-orbit"><VoiceVisualizer state={voiceState} theme={theme} /></div>{trace ? <div className="dashboard-trace"><div><span>LAST INTENT</span><b>{trace.intent || 'none'}{typeof trace.intent_confidence === 'number' ? ` · ${Math.round(trace.intent_confidence * 100)}%` : ''}</b></div><div><span>STATE CHANGE</span><b>{trace.state_before || 'none'} → {trace.state_after || 'none'}</b></div><div><span>EXTRACTED FIELDS</span><b>{Object.keys(trace.slots_extracted || {}).length ? Object.entries(trace.slots_extracted).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`).join(' · ') : 'none'}</b></div></div> : <p className="state-copy">The backend owns conversation state, verification, and parcel actions.</p>}<div className="state-foot"><span>SESSION ID</span><code>{sessionId || 'none'}</code></div></article>
          </section>
          <section className="availability-note"><span className="note-mark">i</span><div><b>Metrics reflect the available API</b><p>The backend exposes health and the current in-memory session. It does not provide historical call totals, duration, latency, trends, or success rates, so those are not shown as numbers.</p></div></section>
        </>}
        {view === 'conversations' && <section className="surface-panel conversation-page"><div className="section-title"><div><span className="eyebrow">CURRENT SESSION</span><h2>Conversation transcript</h2></div><span className="state-badge"><StatusDot online={Boolean(sessionId)} />{sessionId ? 'active' : 'not active'}</span></div><p className="muted-copy">The API has no historical conversation list. This view shows the current demo session and its transcript in this browser.</p><div className="conversation-meta"><span>Session <code>{sessionId || sessionSnapshot?.session_id || 'not started'}</code></span><span>State <b>{sessionSnapshot?.state || stateName}</b></span><span>Turns <b>{turns.length}</b></span></div>{turns.length ? <div className="transcript-table">{turns.map((message, index) => <article className={`transcript-row ${message.role}`} key={`${index}-${message.time?.getTime?.() || index}`}><span>{message.role === 'caller' ? 'CALLER' : 'REDELIVER'}</span>{message.role === 'assistant' ? <FormattedReply text={message.text} /> : <p>{message.text}</p>}{message.time && <time>{message.time.toLocaleTimeString('en-PK', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Karachi' })}</time>}</article>)}</div> : <div className="empty-state"><span className="empty-icon">≋</span><h3>Nothing to review yet</h3><p>Start a call and the conversation will appear here.</p></div>}</section>}
        {view === 'agents' && <section className="surface-panel unavailable-page"><div className="unavailable-art">RD</div><span className="eyebrow">AGENT CONFIGURATION</span><h2>One focused agent, configured in code</h2><p>The current backend provides a fixed REDELIVER dialogue flow. It has no endpoints for listing, creating, editing, testing, activating, or deleting agents, so those controls are unavailable here.</p><div className="capability-tags"><span>Tracking verification</span><span>Delivery status</span><span>Rescheduling</span><span>Pickup selection</span><span>Cancellation</span></div></section>}
        {view === 'settings' && <div className="settings-layout"><section className="surface-panel settings-card"><div className="section-title"><div><span className="eyebrow">DISPLAY</span><h2>Appearance</h2></div></div><p className="muted-copy">Choose a theme for the website and dashboard. Your choice stays in this browser.</p><div className="setting-row"><div><b>Color theme</b><span>Applies across marketing and dashboard pages</span></div><ThemeButton theme={theme} onToggle={onToggleTheme} /></div></section><section className="surface-panel settings-card"><div className="section-title"><div><span className="eyebrow">VOICE</span><h2>Browser audio</h2></div></div><p className="muted-copy">Speech input and output use browser-provided Web Speech features where supported.</p><div className="setting-row"><div><b>Spoken assistant replies</b><span>{voiceReplies ? 'Replies are read aloud using an available English voice' : 'Replies remain on screen'}</span></div><button className={`switch ${voiceReplies ? 'on' : ''}`} type="button" aria-pressed={voiceReplies} onClick={onToggleVoice}><span /></button></div><div className="setting-row"><div><b>Speech recognition</b><span>{Recognition ? 'Available in this browser' : 'Not available; typed replies still work'}</span></div><span className="availability-chip">{Recognition ? 'SUPPORTED' : 'UNAVAILABLE'}</span></div></section><section className="availability-note"><span className="note-mark">i</span><div><b>Account and integrations</b><p>This prototype has no sign-in, team accounts, usage billing, external voice provider, or integration-management API. No credentials are stored in the browser.</p></div></section></div>}
        <footer className="dashboard-footer"><span>REDELIVER · PAKISTAN STANDARD TIME</span><span>Session data is held in backend memory</span></footer>
      </div>
    </main>
  </div>
}

function App() {
  useFx()
  const [backend, setBackend] = useState('checking')
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('redeliver-session-id'))
  const [sessionSnapshot, setSessionSnapshot] = useState(null)
  const [stateName, setStateName] = useState('OFFLINE')
  const [messages, setMessages] = useState([])
  const [trace, setTrace] = useState(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const [micEnabled, setMicEnabled] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [audioAnalyser, setAudioAnalyser] = useState(null)
  const [voiceReplies, setVoiceReplies] = useState(() => localStorage.getItem('redeliver-voice') !== 'off')
  const [notice, setNotice] = useState('')
  const [view, setView] = useState(() => window.location.hash === '#voice' ? 'call' : window.location.hash === '#dashboard' ? 'dashboard' : 'site')
  const [dashboardView, setDashboardView] = useState('overview')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('redeliver-theme') || document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'))
  const recognitionRef = useRef(null)
  const transcriptEndRef = useRef(null)
  const meterRef = useRef(null)
  const outputUtteranceRef = useRef(null)
  const micEnabledRef = useRef(false)
  const busyRef = useRef(false)
  const speakingRef = useRef(false)
  const recognitionRestartRef = useRef(null)
  const restartTimerRef = useRef(null)

  const scheduleRecognitionRestart = useCallback(() => {
    window.clearTimeout(restartTimerRef.current)
    restartTimerRef.current = window.setTimeout(() => recognitionRestartRef.current?.(), 350)
  }, [])

  const stopMeter = useCallback(() => {
    const meter = meterRef.current
    if (!meter) return
    meter.stream?.getTracks().forEach((track) => track.stop())
    meter.context?.close().catch(() => {})
    meterRef.current = null
    setAudioAnalyser(null)
  }, [])

  useEffect(() => {
    let live = true
    getHealth().then(() => live && setBackend('online')).catch(() => live && setBackend('offline'))
    const savedSessionId = localStorage.getItem('redeliver-session-id')
    if (savedSessionId) {
      getSession(savedSessionId).then((snapshot) => {
        if (!live) return
        setSessionSnapshot(snapshot)
        setStateName(snapshot.state)
        setMessages(snapshot.turns.map((turn) => ({
          role: turn.role === 'user' ? 'caller' : 'assistant',
          text: turn.text,
          trace: turn.trace,
          time: null,
        })))
        const latestTrace = [...snapshot.turns].reverse().find((turn) => turn.trace)?.trace
        setTrace(latestTrace || null)
        if (snapshot.ended || snapshot.state === 'END') {
          localStorage.removeItem('redeliver-session-id')
          setSessionId(null)
        }
      }).catch(() => {
        if (!live) return
        localStorage.removeItem('redeliver-session-id')
        setSessionId(null)
        setNotice('The previous session is no longer available. Start a new call to continue.')
      })
    }
    return () => {
      live = false
      micEnabledRef.current = false
      window.clearTimeout(restartTimerRef.current)
      recognitionRef.current?.abort()
      window.speechSynthesis?.cancel()
      stopMeter()
    }
  }, [stopMeter])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('redeliver-theme', theme)
  }, [theme])

  useEffect(() => {
    const syncRoute = () => setView(window.location.hash === '#voice' ? 'call' : window.location.hash === '#dashboard' ? 'dashboard' : 'site')
    window.addEventListener('popstate', syncRoute)
    return () => window.removeEventListener('popstate', syncRoute)
  }, [])

  useEffect(() => {
    localStorage.setItem('redeliver-voice', voiceReplies ? 'on' : 'off')
  }, [voiceReplies])

  useEffect(() => {
    if (view !== 'site') return undefined
    const sections = document.querySelectorAll('.scroll-reveal')
    const revealImmediately = window.matchMedia('(prefers-reduced-motion: reduce)').matches || typeof IntersectionObserver === 'undefined'
    if (revealImmediately) {
      sections.forEach((section) => section.classList.add('is-visible'))
      return undefined
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          observer.unobserve(entry.target)
        }
      })
    }, { threshold: 0.12, rootMargin: '0px 0px -45px 0px' })
    sections.forEach((section) => observer.observe(section))
    return () => observer.disconnect()
  }, [trace, view])

  useEffect(() => { transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, busy])

  const visualState = useMemo(() => {
    if (backend === 'offline') return 'error'
    if (listening) return 'listening'
    if (busy) return 'processing'
    if (speaking) return 'speaking'
    return 'idle'
  }, [backend, busy, listening, speaking])

  const speak = useCallback((text) => {
    if (!voiceReplies || !window.speechSynthesis || !text) return
    speakingRef.current = true
    window.speechSynthesis.cancel()
    const spokenText = text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/^\s*[-*]\s+/gm, '').replace(/—/g, ', ')
    const utterance = new SpeechSynthesisUtterance(spokenText)
    const voices = window.speechSynthesis.getVoices()
    const voice = voices.find((item) => item.lang?.toLowerCase() === 'en-pk') || voices.find((item) => item.lang?.toLowerCase() === 'en-gb') || voices.find((item) => item.lang?.toLowerCase().startsWith('en'))
    utterance.lang = 'en-PK'
    if (voice) utterance.voice = voice
    utterance.rate = 0.96
    utterance.pitch = 0.94
    utterance.onstart = () => setSpeaking(true)
    utterance.onend = () => {
      speakingRef.current = false
      setSpeaking(false)
      if (micEnabledRef.current) scheduleRecognitionRestart()
    }
    utterance.onerror = () => {
      speakingRef.current = false
      setSpeaking(false)
      if (micEnabledRef.current) scheduleRecognitionRestart()
    }
    outputUtteranceRef.current = utterance
    window.speechSynthesis.speak(utterance)
  }, [scheduleRecognitionRestart, voiceReplies])

  const startCall = async () => {
    setBusy(true); setNotice('')
    try {
      const session = await createSession()
      localStorage.setItem('redeliver-session-id', session.session_id)
      setSessionId(session.session_id); setStateName(session.state); setSessionSnapshot({ session_id: session.session_id, state: session.state })
      setMessages([{ role: 'assistant', text: session.greeting, time: new Date() }]); setTrace(null); speak(session.greeting)
    } catch (error) { setNotice(error.message); setBackend('offline') }
    finally { busyRef.current = false; setBusy(false) }
  }

  const submitTurn = async (rawText, sttConfidence) => {
    const text = rawText.trim()
    if (!sessionId || busyRef.current || (!text && !sttConfidence?.silence)) return
    busyRef.current = true
    if (micEnabledRef.current) {
      recognitionRef.current?.abort()
      recognitionRef.current = null
      setListening(false)
    }
    setBusy(true); setNotice('')
    if (text) setMessages((items) => [...items, { role: 'caller', text, time: new Date() }])
    setInput('')
    try {
      const result = await sendTurn(sessionId, { text, silence: Boolean(sttConfidence?.silence), ...(typeof sttConfidence?.confidence === 'number' ? { stt_confidence: sttConfidence.confidence } : {}) })
      setMessages((items) => [...items, { role: 'assistant', text: result.reply, trace: result.trace, time: new Date() }])
      setTrace(result.trace); setStateName(result.trace.state_after || stateName); speak(result.reply)
      if (result.ended) { micEnabledRef.current = false; setMicEnabled(false); localStorage.removeItem('redeliver-session-id'); setSessionId(null); setListening(false); recognitionRef.current?.abort(); stopMeter() }
    } catch (error) { setNotice(error.message); setBackend('offline') }
    finally {
      busyRef.current = false
      setBusy(false)
      if (micEnabledRef.current && !speakingRef.current) scheduleRecognitionRestart()
    }
  }

  const startRecognition = () => {
    if (!micEnabledRef.current || busyRef.current || speakingRef.current || !sessionId || !Recognition) return
    const recognition = new Recognition()
    recognition.lang = 'en-PK'; recognition.interimResults = false; recognition.maxAlternatives = 1
    recognition.onstart = () => { setListening(true); setNotice('Microphone is on. Speak when ready; it will stay on between turns.') }
    recognition.onresult = (event) => {
      const result = event.results[event.resultIndex]?.[0]
      if (!result) return
      setInput(result.transcript); setNotice('')
      const confidence = Number.isFinite(result.confidence) && result.confidence > 0 ? result.confidence : undefined
      void submitTurn(result.transcript, { confidence })
    }
    recognition.onerror = (event) => {
      setListening(false)
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        micEnabledRef.current = false
        setMicEnabled(false)
        stopMeter()
        setNotice('Microphone permission was blocked. Allow microphone access or type your turn.')
      } else if (event.error !== 'no-speech' && event.error !== 'aborted') {
        setNotice(`Voice input stopped: ${event.error}. You can type your turn instead.`)
      }
    }
    recognition.onend = () => {
      if (recognitionRef.current === recognition) recognitionRef.current = null
      setListening(false)
      if (micEnabledRef.current && !busyRef.current && !speakingRef.current) scheduleRecognitionRestart()
    }
    recognitionRef.current = recognition
    try { recognition.start() } catch {
      setListening(false)
      if (micEnabledRef.current) scheduleRecognitionRestart()
    }
  }
  recognitionRestartRef.current = startRecognition

  const listen = async () => {
    if (!Recognition) { setNotice('Voice input is not supported here. You can type your turn below.'); return }
    if (micEnabledRef.current) {
      micEnabledRef.current = false
      setMicEnabled(false)
      window.clearTimeout(restartTimerRef.current)
      recognitionRef.current?.abort()
      recognitionRef.current = null
      setListening(false)
      stopMeter()
      setNotice('Microphone is off.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      const AudioContext = window.AudioContext || window.webkitAudioContext
      if (AudioContext) {
        const context = new AudioContext()
        const analyser = context.createAnalyser()
        analyser.fftSize = 256
        context.createMediaStreamSource(stream).connect(analyser)
        meterRef.current = { stream, context, analyser }
        setAudioAnalyser(analyser)
      } else {
        meterRef.current = { stream }
      }
    } catch (error) {
      setNotice(error.name === 'NotAllowedError' ? 'Microphone permission was denied. Allow access in your browser settings or type your reply.' : 'Could not access the microphone. You can type your reply instead.')
      return
    }
    micEnabledRef.current = true
    setMicEnabled(true)
    startRecognition()
  }

  const finishCall = async () => {
    if (!sessionId) return
    busyRef.current = true; micEnabledRef.current = false; setMicEnabled(false); window.clearTimeout(restartTimerRef.current); setBusy(true); recognitionRef.current?.abort(); recognitionRef.current = null; setListening(false); stopMeter(); window.speechSynthesis?.cancel(); speakingRef.current = false; setSpeaking(false)
    try {
      await endSession(sessionId)
      localStorage.removeItem('redeliver-session-id')
      setMessages((items) => [...items, { role: 'system', text: 'Call ended. Start a new call whenever you need help.', time: new Date() }]); setStateName('END'); setSessionId(null)
    } catch (error) { setNotice(error.message) }
    finally { busyRef.current = false; setBusy(false) }
  }

  const refreshSession = async () => {
    setBusy(true)
    try {
      await getHealth()
      setBackend('online')
      if (sessionId) setSessionSnapshot(await getSession(sessionId).catch(() => null))
      setNotice('')
    } catch (error) { setBackend('offline'); setNotice(error.message) }
    finally { busyRef.current = false; setBusy(false) }
  }

  const onSubmit = (event) => { event.preventDefault(); void submitTurn(input) }
  const toggleTheme = () => setTheme((value) => value === 'dark' ? 'light' : 'dark')
  const scrollToTop = () => window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  const navigateToView = (nextView) => {
    const route = nextView === 'call' ? '#voice' : nextView === 'dashboard' ? '#dashboard' : ''
    window.history.pushState({ redeliverView: nextView }, '', `${window.location.pathname}${window.location.search}${route}`)
    setView(nextView)
    scrollToTop()
  }
  const returnHome = () => {
    window.history.replaceState({ redeliverView: 'site' }, '', `${window.location.pathname}${window.location.search}`)
    setView('site')
    scrollToTop()
  }
  const openCallPage = () => { setMobileMenuOpen(false); navigateToView('call') }
  const openDashboard = () => { setMobileMenuOpen(false); navigateToView('dashboard') }
  const interruptSpeech = () => {
    window.speechSynthesis?.cancel()
    speakingRef.current = false
    setSpeaking(false)
    if (micEnabledRef.current) scheduleRecognitionRestart()
  }

  if (view === 'dashboard') return <Dashboard view={dashboardView} setView={setDashboardView} onBack={returnHome} backend={backend} sessionId={sessionId} stateName={stateName} voiceState={visualState} messages={messages} trace={trace} sessionSnapshot={sessionSnapshot} onRefresh={refreshSession} busy={busy} theme={theme} onToggleTheme={toggleTheme} voiceReplies={voiceReplies} onToggleVoice={() => setVoiceReplies((enabled) => !enabled)} />
  if (view === 'call') return <CallExperience onBack={returnHome} backend={backend} sessionId={sessionId} stateName={stateName} voiceState={visualState} messages={messages} trace={trace} notice={notice} input={input} setInput={setInput} busy={busy} listening={listening} micEnabled={micEnabled} speaking={speaking} voiceReplies={voiceReplies} setVoiceReplies={setVoiceReplies} onStart={startCall} onEnd={finishCall} onListen={listen} onSubmit={onSubmit} onInterrupt={interruptSpeech} onReplay={speak} onRefresh={refreshSession} onToggleTheme={toggleTheme} analyser={audioAnalyser} theme={theme} />
  return <SiteHome backend={backend} sessionId={sessionId} visualState={visualState} analyser={audioAnalyser} theme={theme} trace={trace} onCall={openCallPage} onDashboard={openDashboard} onToggleTheme={toggleTheme} onRetry={refreshSession} menuOpen={mobileMenuOpen} setMenuOpen={setMobileMenuOpen} />
}

export default App



import { useCallback, useEffect, useRef, useState } from 'react'
import { createSession, endSession, getHealth, sendTurn } from './services/redeliverApi'
import './App.css'

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition

function formatInline(text, keyPrefix) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => (
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={`${keyPrefix}-${index}`}>{part.slice(2, -2)}</strong>
      : part
  ))
}

function FormattedReply({ text }) {
  const blocks = []
  let bullets = []
  const flushBullets = () => {
    if (bullets.length) {
      blocks.push(
        <ul className="reply-list" key={`list-${blocks.length}`}>
          {bullets.map((line, index) => (
            <li key={`item-${index}`}>{formatInline(line, `list-${blocks.length}-${index}`)}</li>
          ))}
        </ul>
      )
      bullets = []
    }
  }

  text.split(/\r?\n/).forEach((line) => {
    const item = line.match(/^\s*[-*]\s+(.+)$/)
    if (item) {
      bullets.push(item[1])
      return
    }
    flushBullets()
    if (line.trim()) {
      blocks.push(<p key={`paragraph-${blocks.length}`}>{formatInline(line, `paragraph-${blocks.length}`)}</p>)
    }
  })
  flushBullets()
  return <div className="message-formatted">{blocks}</div>
}

function App() {
  const [backend, setBackend] = useState('checking')
  const [sessionId, setSessionId] = useState(null)
  const [stateName, setStateName] = useState('OFFLINE')
  const [messages, setMessages] = useState([])
  const [trace, setTrace] = useState(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const [voiceReplies, setVoiceReplies] = useState(true)
  const [notice, setNotice] = useState('')
  const recognitionRef = useRef(null)
  const transcriptEndRef = useRef(null)

  useEffect(() => {
    let live = true
    getHealth()
      .then(() => live && setBackend('online'))
      .catch(() => live && setBackend('offline'))
    return () => {
      live = false
      recognitionRef.current?.abort()
      window.speechSynthesis?.cancel()
    }
  }, [])

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, busy])

  const speak = useCallback((text) => {
    if (!voiceReplies || !window.speechSynthesis || !text) return
    window.speechSynthesis.cancel()
    const spokenText = text
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/^\s*[-*]\s+/gm, '')
      .replace(/—/g, ', ')
    const utterance = new SpeechSynthesisUtterance(spokenText)
    const voices = window.speechSynthesis.getVoices()
    const voice = voices.find((item) => item.lang?.toLowerCase() === 'en-pk')
      || voices.find((item) => item.lang?.toLowerCase() === 'en-gb')
      || voices.find((item) => item.lang?.toLowerCase().startsWith('en'))
    utterance.lang = 'en-PK'
    if (voice) utterance.voice = voice
    utterance.rate = 0.96
    utterance.pitch = 0.94
    window.speechSynthesis.speak(utterance)
  }, [voiceReplies])

  const startCall = async () => {
    setBusy(true)
    setNotice('')
    try {
      const session = await createSession()
      setSessionId(session.session_id)
      setStateName(session.state)
      setMessages([{ role: 'assistant', text: session.greeting, time: new Date() }])
      setTrace(null)
      speak(session.greeting)
    } catch (error) {
      setNotice(error.message)
      setBackend('offline')
    } finally {
      setBusy(false)
    }
  }

  const submitTurn = async (rawText, sttConfidence) => {
    const text = rawText.trim()
    if (!sessionId || busy || (!text && !sttConfidence?.silence)) return
    setBusy(true)
    setNotice('')
    if (text) setMessages((items) => [...items, { role: 'caller', text, time: new Date() }])
    setInput('')
    try {
      const result = await sendTurn(sessionId, {
        text,
        silence: Boolean(sttConfidence?.silence),
        ...(typeof sttConfidence?.confidence === 'number'
          ? { stt_confidence: sttConfidence.confidence }
          : {}),
      })
      setMessages((items) => [...items, {
        role: 'assistant', text: result.reply, trace: result.trace, time: new Date(),
      }])
      setTrace(result.trace)
      setStateName(result.trace.state_after || stateName)
      speak(result.reply)
      if (result.ended) {
        setSessionId(null)
        setListening(false)
        recognitionRef.current?.abort()
      }
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusy(false)
    }
  }

  const listen = () => {
    if (!SpeechRecognition) {
      setNotice('Voice input is not supported in this browser. You can type your turn below.')
      return
    }
    if (listening) {
      recognitionRef.current?.stop()
      setListening(false)
      return
    }
    const recognition = new SpeechRecognition()
    recognition.lang = 'en-PK'
    recognition.interimResults = false
    recognition.maxAlternatives = 1
    recognition.onstart = () => {
      setListening(true)
      setNotice('Listening. Say your answer after the tone.')
    }
    recognition.onresult = (event) => {
      const result = event.results[0][0]
      const transcript = result.transcript
      setInput(transcript)
      setNotice('')
      const confidence = Number.isFinite(result.confidence) && result.confidence > 0
        ? result.confidence
        : undefined
      void submitTurn(transcript, { confidence })
    }
    recognition.onerror = (event) => {
      setListening(false)
      setNotice(event.error === 'not-allowed'
        ? 'Microphone permission was blocked. Allow microphone access in your browser settings.'
        : `Voice input stopped: ${event.error}. You can type your turn instead.`)
    }
    recognition.onend = () => setListening(false)
    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch {
      setListening(false)
      setNotice('Could not start the microphone. Check that another tab is not using it.')
    }
  }

  const finishCall = async () => {
    if (!sessionId) return
    setBusy(true)
    recognitionRef.current?.abort()
    setListening(false)
    window.speechSynthesis?.cancel()
    try {
      await endSession(sessionId)
      setMessages((items) => [...items, {
        role: 'system', text: 'Call ended. Start a new call whenever you need help.', time: new Date(),
      }])
      setStateName('END')
      setSessionId(null)
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusy(false)
    }
  }

  const onSubmit = (event) => {
    event.preventDefault()
    void submitTurn(input)
  }

  const confidence = trace?.intent_confidence
  const extracted = trace?.slots_extracted || {}

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Redeliver home">
          <span className="brand-mark">R<span>/</span>D</span>
          <span className="brand-name">REDELIVER</span>
        </a>
        <div className="topbar-meta">
          <span className={`connection ${backend}`}>
            <span className="connection-dot" />
            {backend === 'checking' ? 'CONNECTING' : backend.toUpperCase()}
          </span>
          <span className="topbar-divider" />
          <span className="meta-label">PAKISTAN / PKT</span>
        </div>
        <a className="docs-link" href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
          API docs <span aria-hidden="true">↗</span>
        </a>
      </header>

      <div className="workspace" id="top">
        <section className="intro-panel" aria-label="REDELIVER call controls">
          <div className="intro-copy">
            <p className="eyebrow"><span className="eyebrow-rule" /> MISSED DELIVERY? MOVE ON.</p>
            <h1>Let’s get<br /><em>it moving.</em></h1>
            <p className="intro-description">
              Reschedule, reroute, or check in. Tell us what happened and we’ll take it from here.
            </p>
            {!sessionId ? (
              <button className="start-button" type="button" onClick={startCall} disabled={busy || backend !== 'online'}>
                <span>{busy ? 'Opening line…' : stateName === 'END' ? 'Start another call' : 'Start a call'}</span>
                <span className="button-arrow" aria-hidden="true">↗</span>
              </button>
            ) : (
              <button className="end-button" type="button" onClick={finishCall} disabled={busy}>
                End this call <span aria-hidden="true">×</span>
              </button>
            )}
            <p className="privacy-note">Secure parcel verification · Your details stay in this session</p>
          </div>

          <div className={`voice-visual ${listening ? 'is-listening' : ''}`} aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="orbit-core"><span>RD</span></div>
            <div className="waveform">
              {Array.from({ length: 29 }, (_, index) => (
                <i key={index} style={{ '--bar-index': index, '--bar-height': `${4 + ((index * 17 + 13) % 23)}px` }} />
              ))}
            </div>
            <span className="visual-caption">{listening ? 'VOICE IN / LIVE' : 'READY WHEN YOU ARE'}</span>
          </div>

          <div className="intro-foot">
            <span>BUILT FOR THE MOMENT AFTER “WE MISSED YOU.”</span>
            <span className="intro-foot-mark">01 — 04</span>
          </div>
        </section>

        <section className="call-panel" aria-label="Conversation">
          <div className="call-header">
            <div>
              <p className="panel-kicker">LIVE ASSISTANT</p>
              <h2>{sessionId ? 'You’re on the line.' : 'Your line is ready.'}</h2>
            </div>
            <div className="call-state">
              <span className={`state-light ${sessionId ? 'active' : ''}`} />
              {sessionId ? stateName.replaceAll('_', ' ') : 'NO ACTIVE SESSION'}
            </div>
          </div>

          <div className="transcript" aria-live="polite" aria-label="Call transcript">
            {messages.length === 0 ? (
              <div className="empty-transcript">
                <div className="empty-stamp">01<span>/</span>04</div>
                <p className="empty-title">Start with your<br />tracking ID.</p>
                <p className="empty-copy">We’ll verify the parcel before changing or sharing delivery details.</p>
                <div className="transcript-divider"><span>HOW IT WORKS</span><span>01—02—03</span></div>
                <div className="steps-row">
                  <span><b>01</b> Identify</span>
                  <span><b>02</b> Verify</span>
                  <span><b>03</b> Resolve</span>
                </div>
              </div>
            ) : (
              <div className="message-list">
                {messages.map((message, index) => (
                  <article className={`message ${message.role}`} key={`${index}-${message.time?.getTime?.() || index}`}>
                    {message.role !== 'system' && (
                      <div className="message-meta">
                        <span>{message.role === 'caller' ? 'YOU' : 'REDELIVER'}</span>
                        <time>{message.time?.toLocaleTimeString('en-PK', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Karachi' })}</time>
                      </div>
                    )}
                    {message.role === 'assistant'
                      ? <FormattedReply text={message.text} />
                      : <p>{message.text}</p>}
                  </article>
                ))}
                {busy && <div className="typing-indicator"><i /><i /><i /><span>Working it out</span></div>}
                <div ref={transcriptEndRef} />
              </div>
            )}
          </div>

          {notice && <p className="notice" role="status">{notice}</p>}

          <div className="composer-wrap">
            <div className="composer-toolbar">
              <span>{sessionId ? 'YOUR TURN' : 'START A CALL TO CONTINUE'}</span>
              <button
                className={`voice-toggle ${voiceReplies ? 'enabled' : ''}`}
                type="button"
                onClick={() => setVoiceReplies((enabled) => !enabled)}
                aria-pressed={voiceReplies}
                title="Toggle spoken replies"
              >
                {voiceReplies ? 'SPOKEN REPLIES ON' : 'SPOKEN REPLIES OFF'}
              </button>
            </div>
            <form className="composer" onSubmit={onSubmit}>
              <label className="sr-only" htmlFor="turn-input">Speak or type your response</label>
              <textarea
                id="turn-input"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) onSubmit(event)
                }}
                placeholder={sessionId ? 'Say what you need…' : 'Start a call to begin…'}
                maxLength={2000}
                disabled={!sessionId || busy}
                rows={1}
              />
              <button
                className={`mic-button ${listening ? 'listening' : ''}`}
                type="button"
                onClick={listen}
                disabled={!sessionId || busy}
                aria-label={listening ? 'Stop listening' : 'Speak your response'}
                title={SpeechRecognition ? 'Speak your response' : 'Voice input is unsupported in this browser'}
              >
                {listening ? 'STOP' : 'MIC'}
              </button>
              <button className="send-button" type="submit" disabled={!sessionId || busy || !input.trim()} aria-label="Send message">
                <span aria-hidden="true">↑</span>
              </button>
            </form>
            <div className="composer-hint"><span>ENTER TO SEND</span><span>{input.length} / 2000</span></div>
          </div>
        </section>

        <aside className="insight-panel" aria-label="Assistant decision trace">
          <div className="insight-heading">
            <p className="panel-kicker">UNDER THE HOOD</p>
            <h2>Decision trace</h2>
          </div>
          <div className="decision-body">
            {trace ? (
              <>
                <div className="decision-intent">
                  <span className="decision-label">DETECTED INTENT</span>
                  <strong>{trace.intent || '—'}</strong>
                  <div className="confidence-line">
                    <span>CONFIDENCE</span>
                    <b>{typeof confidence === 'number' ? `${Math.round(confidence * 100)}%` : '—'}</b>
                  </div>
                  <div className="confidence-track"><i style={{ width: `${Math.max(0, Math.min(100, (confidence || 0) * 100))}%` }} /></div>
                </div>
                <div className="state-transition">
                  <span className="decision-label">STATE TRANSITION</span>
                  <div className="state-pair"><span>{trace.state_before || '—'}</span><b>→</b><span>{trace.state_after || '—'}</span></div>
                </div>
                <div className="extracted-block">
                  <span className="decision-label">EXTRACTED SLOTS</span>
                  {Object.keys(extracted).length ? (
                    <dl>
                      {Object.entries(extracted).map(([key, value]) => (
                        <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{String(value ?? '—')}</dd></div>
                      ))}
                    </dl>
                  ) : <p className="quiet-value">Nothing extracted this turn.</p>}
                </div>
              </>
            ) : (
              <div className="trace-empty">
                <span className="trace-symbol">{`{ }`}</span>
                <p>The assistant’s rule-based decisions will show here as you talk.</p>
                <span className="trace-note">PLAIN PYTHON · NO LLM DECISIONS</span>
              </div>
            )}
          </div>
          <div className="insight-footer">
            <span>SESSION</span>
            <code>{sessionId ? `${sessionId.slice(0, 8)}…` : 'NOT STARTED'}</code>
          </div>
        </aside>
      </div>

      <footer className="site-footer">
        <span>REDELIVER <b>© 2026</b></span>
        <span>YOUR PARCEL. YOUR NEXT MOVE.</span>
        <span>TEXT TRANSCRIPTS STAY IN MEMORY FOR THIS SESSION</span>
      </footer>
    </main>
  )
}

export default App

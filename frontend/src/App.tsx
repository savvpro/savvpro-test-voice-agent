import { useRef, useState } from 'react'
import { ApiError, sendTurn, startCall, type Decision, type TurnResponse } from './api'
import BrainPanel from './components/BrainPanel'
import Transcript, { type Message } from './components/Transcript'
import { useSpeech } from './useSpeech'

type Problem = { kind: 'expired' } | { kind: 'error'; message: string; retry?: () => void } | null

// Only a failed fetch is a connection problem; 5xx may be transient, so offer Retry; 4xx won't change.
function failure(e: unknown, retry: () => void): Problem {
  if (!(e instanceof ApiError))
    return { kind: 'error', message: 'Can’t reach the clinic line. Check your connection.', retry }
  if (e.status === 404) return { kind: 'expired' }
  return {
    kind: 'error',
    message: 'Something went wrong on our side. Please try again.',
    retry: e.status >= 500 ? retry : undefined,
  }
}

const MAX_SILENT = 3 // hands-free gives up after this many empty listens in a row

export default function App() {
  const speech = useSpeech()
  const [callId, setCallId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [ended, setEnded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<Problem>(null)
  const [handsFree, setHandsFree] = useState(false)
  const [draft, setDraft] = useState('')
  const handsFreeRef = useRef(false)
  const listenSeq = useRef(0) // only the latest listen loop may act
  const busyRef = useRef(false)
  const [hint, setHint] = useState('')
  const session = useRef(0) // bumped on every start/end so stale async work is dropped

  const inCall = callId !== null
  const live = inCall && !ended && problem?.kind !== 'expired'

  function reset() {
    session.current++
    listenSeq.current++
    speech.stop()
    setCallId(null)
    setMessages([])
    setDecisions([])
    setEnded(false)
    busyRef.current = false
    setBusy(false)
    setProblem(null)
    setDraft('')
  }

  async function onReply(res: TurnResponse, sid: number) {
    setMessages((m) => [...m, { role: 'assistant', text: res.reply }])
    setDecisions((d) => [res.decision, ...d])
    if (res.ended) setEnded(true)
    const seq = listenSeq.current
    await speech.speak(res.reply)
    if (!res.ended && handsFreeRef.current && sid === session.current && seq === listenSeq.current)
      void listenLoop(res.call_id, sid, ++listenSeq.current, 0)
  }

  async function listenLoop(id: string, sid: number, seq: number, silent: number) {
    if (sid !== session.current || seq !== listenSeq.current || busyRef.current) return
    const text = await speech.listen()
    if (sid !== session.current || seq !== listenSeq.current || !handsFreeRef.current) return
    if (text) void submit(id, text, sid)
    else if (silent + 1 < MAX_SILENT) void listenLoop(id, sid, seq, silent + 1)
    else {
      handsFreeRef.current = false
      setHandsFree(false)
      setHint('Hands-free turned off after no speech. Tap the mic to talk.')
    }
  }

  async function submit(id: string, text: string, sid: number, echo = true) {
    if (echo) setMessages((m) => [...m, { role: 'caller', text }])
    busyRef.current = true
    setBusy(true)
    setHint('')
    setProblem(null)
    try {
      const res = await sendTurn(id, text)
      if (sid !== session.current) return
      busyRef.current = false
      setBusy(false)
      await onReply(res, sid)
    } catch (e) {
      if (sid !== session.current) return
      busyRef.current = false
      setBusy(false)
      setProblem(failure(e, () => void submit(id, text, sid, false)))
    }
  }

  async function start() {
    reset()
    const sid = session.current
    busyRef.current = true
    setBusy(true)
    try {
      const res = await startCall()
      if (sid !== session.current) return
      setCallId(res.call_id)
      busyRef.current = false
      setBusy(false)
      await onReply(res, sid)
    } catch (e) {
      if (sid !== session.current) return
      busyRef.current = false
      setBusy(false)
      setProblem(failure(e, () => void start()))
    }
  }

  async function mic() {
    if (!callId || busy) return
    listenSeq.current++ // supersede any hands-free loop
    if (speech.listening) return speech.stop()
    const text = await speech.listen()
    if (text) void submit(callId, text, session.current)
  }

  function toggleHandsFree() {
    const on = !handsFree
    handsFreeRef.current = on
    listenSeq.current++
    setHint('')
    setHandsFree(on)
    if (!on) speech.stop()
    else if (callId && live && !busy) void listenLoop(callId, session.current, ++listenSeq.current, 0)
  }

  function send(e: React.FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text || !callId || busy || !live) return
    setDraft('')
    listenSeq.current++
    speech.stop()
    void submit(callId, text, session.current)
  }

  return (
    <div className="app">
      <header>
        <h1>Maple Street Clinic</h1>
        <p>Appointment line</p>
        {inCall ? (
          <button className="btn danger" onClick={reset}>End call</button>
        ) : (
          <button className="btn primary" onClick={start} disabled={busy}>Start call</button>
        )}
      </header>

      {problem?.kind === 'expired' && (
        <div className="notice" role="alert">
          This call has ended or expired.{' '}
          <button className="btn primary" onClick={start}>Start new call</button>
        </div>
      )}
      {problem?.kind === 'error' && (
        <div className="notice" role="alert">
          {problem.message}{' '}
          {problem.retry && <button className="btn" onClick={problem.retry}>Retry</button>}
        </div>
      )}
      {hint && <p className="muted" role="status">{hint}</p>}
      {ended && (
        <div className="notice info" role="status">
          The call has finished.{' '}
          <button className="btn primary" onClick={start}>Start new call</button>
        </div>
      )}

      <main>
        <div className="col">
          <Transcript messages={messages} />
          {inCall && (
            <div className="controls">
              {speech.supported && (
                <div className="voice">
                  <button
                    className={`mic${speech.listening ? ' on' : ''}`}
                    onClick={mic}
                    disabled={!live || busy}
                    aria-pressed={speech.listening}
                    aria-label={speech.listening ? 'Stop listening' : 'Push to talk'}
                  >
                    {speech.listening ? 'Listening…' : 'Talk'}
                  </button>
                  <label className="toggle">
                    <input type="checkbox" checked={handsFree} onChange={toggleHandsFree} />
                    Hands-free
                  </label>
                </div>
              )}
              {speech.voices.length > 1 && (
                <label className="voice-pick">
                  Voice
                  <select value={speech.voice?.name ?? ''} onChange={(e) => speech.setVoiceName(e.target.value)}>
                    {speech.voices.map((v) => (
                      <option key={v.name} value={v.name}>
                        {v.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <form onSubmit={send} className="text">
                <label htmlFor="msg">Type a message</label>
                <input
                  id="msg"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  maxLength={500}
                  autoComplete="off"
                  disabled={!live}
                  placeholder={speech.supported ? 'Or type here' : 'Voice isn’t supported here; type instead'}
                />
                <button className="btn primary" type="submit" disabled={!live || busy || !draft.trim()}>
                  Send
                </button>
              </form>
            </div>
          )}
        </div>
        <BrainPanel decisions={decisions} />
      </main>
    </div>
  )
}

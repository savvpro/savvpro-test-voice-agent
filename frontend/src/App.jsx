import { useEffect, useRef, useState } from 'react';
import { sendTurn, startSession } from './api.js';
import { useSpeech } from './useSpeech.js';

const EXAMPLES = [
  'I\u2019d like to book a cleaning next Tuesday afternoon',
  'Cancel my appointment, my name is Sara Khan',
  'What are your opening hours?',
];

const ERROR_TEXT = {
  'not-allowed': 'Microphone access was blocked. Allow it in the browser, or type instead.',
  'no-speech': 'I did not hear anything. Try again.',
  network: 'Speech recognition needs an internet connection in this browser.',
};

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [turn, setTurn] = useState(null);
  const [ended, setEnded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState('');
  const [autoListen, setAutoListen] = useState(true);
  const logRef = useRef(null);

  const speech = useSpeech({
    onResult: (text) => submit(text),
    onError: (code) => setError(ERROR_TEXT[code] ?? `Speech error: ${code}`),
  });

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const addMessage = (from, text) => setMessages((m) => [...m, { from, text }]);

  async function beginCall() {
    setError('');
    setBusy(true);
    try {
      const data = await startSession();
      setSessionId(data.session_id);
      setMessages([{ from: 'assistant', text: data.reply }]);
      setTurn(null);
      setEnded(false);
      speech.speak(data.reply, () => autoListen && speech.supported && speech.start());
    } catch {
      setError('Could not reach the assistant. Is the backend running on port 8000?');
    } finally {
      setBusy(false);
    }
  }

  async function submit(text) {
    const clean = text.trim();
    if (!clean || !sessionId || busy || ended) return;
    setError('');
    setDraft('');
    addMessage('caller', clean);
    setBusy(true);
    try {
      const data = await sendTurn(sessionId, clean);
      addMessage('assistant', data.reply);
      setTurn(data);
      setEnded(data.ended);
      speech.speak(data.reply, () => !data.ended && autoListen && speech.supported && speech.start());
    } catch {
      setError('Something went wrong talking to the assistant. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  const inCall = Boolean(sessionId) && !ended;

  return (
    <div className="app">
      <header>
        <h1>Bright Smile Dental</h1>
        <p>Voice assistant demo. Everything the assistant decides is made by plain rules, not an AI model.</p>
      </header>

      <main>
        <section className="call" aria-label="Call">
          {!inCall ? (
            <button className="primary" onClick={beginCall} disabled={busy}>
              {ended ? 'Start a new call' : 'Start call'}
            </button>
          ) : (
            <div className="controls">
              {speech.supported ? (
                <button
                  className={`mic ${speech.listening ? 'on' : ''}`}
                  onClick={speech.listening ? speech.stop : speech.start}
                  disabled={busy}
                  aria-pressed={speech.listening}
                >
                  {speech.listening ? 'Listening… (tap to stop)' : 'Tap to speak'}
                </button>
              ) : (
                <p className="note">Voice input needs Chrome or Edge. You can still type below.</p>
              )}
              <label className="toggle">
                <input type="checkbox" checked={autoListen} onChange={(e) => setAutoListen(e.target.checked)} />
                Listen automatically after each reply
              </label>
            </div>
          )}

          {error && <p role="alert" className="error">{error}</p>}

          <div className="log" ref={logRef} role="log" aria-live="polite">
            {messages.length === 0 && <p className="note">Press “Start call”. Try saying:</p>}
            {messages.length === 0 && (
              <ul className="examples">{EXAMPLES.map((e) => <li key={e}>{e}</li>)}</ul>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`bubble ${m.from}`}>
                <span className="who">{m.from === 'assistant' ? 'Assistant' : 'You'}</span>
                {m.text}
              </div>
            ))}
            {ended && <p className="note">The call has ended.</p>}
          </div>

          {inCall && (
            <form onSubmit={(e) => { e.preventDefault(); submit(draft); }}>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="…or type what you would say"
                aria-label="Type your message"
                maxLength={500}
              />
              <button type="submit" disabled={busy || !draft.trim()}>Send</button>
            </form>
          )}
        </section>

        <aside className="brain" aria-label="What the assistant decided">
          <h2>What the assistant decided</h2>
          {!turn ? (
            <p className="note">Decisions appear here after your first sentence.</p>
          ) : (
            <>
              <dl>
                <dt>Call state</dt><dd>{turn.state}</dd>
                <dt>Goal</dt><dd>{turn.intent ?? 'not known yet'}</dd>
              </dl>
              <h3>Details collected</h3>
              {Object.keys(turn.slots).length === 0 ? (
                <p className="note">Nothing yet.</p>
              ) : (
                <dl>
                  {Object.entries(turn.slots).map(([k, v]) => (
                    <div key={k} className="slot"><dt>{k}</dt><dd>{String(v)}</dd></div>
                  ))}
                </dl>
              )}
              {turn.alternatives.length > 0 && (
                <>
                  <h3>Options offered</h3>
                  <ol>{turn.alternatives.map((a) => <li key={a}>{a}</li>)}</ol>
                </>
              )}
              <h3>Reasoning trace (last turn)</h3>
              <ol className="trace">{turn.trace.map((t, i) => <li key={i}>{t}</li>)}</ol>
            </>
          )}
        </aside>
      </main>
    </div>
  );
}

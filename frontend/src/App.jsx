import { useEffect, useRef, useState } from 'react';
import { useConversation } from './useConversation.js';
import { useSpeechInput } from './useSpeechInput.js';
import { useSpokenReplies } from './useSpokenReplies.js';

const labels = {
  ask_date: 'Choosing a date', ask_time: 'Choosing a time', ask_party_size: 'Adding your guests',
  confirm: 'Ready for your confirmation', completed: 'Reservation confirmed', cancelled: 'Conversation cancelled',
};

function Icon({ name, size = 20 }) {
  const paths = {
    fork: <><path d="M6 3v7m-3-7v4a3 3 0 0 0 6 0V3M6 10v11M18 3c-5 4-5 10 0 11V3Zm0 11v7" /></>,
    arrow: <><path d="m5 12 14 0m-5-5 5 5-5 5" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    guests: <><circle cx="9" cy="8" r="3" /><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v2" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    plus: <path d="M12 5v14M5 12h14" />,
    microphone: <><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10v1a7 7 0 0 0 14 0v-1M12 18v4m-4 0h8" /></>,
    stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function dateLabel(value) {
  if (!value) return 'Not chosen yet';
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }).format(date);
}

function Detail({ icon, label, children, missing }) {
  return <div className={`detail ${missing ? 'detail-empty' : ''}`}>
    <span className="detail-icon"><Icon name={icon} /></span>
    <div><dt>{label}</dt><dd>{children}</dd></div>
  </div>;
}

export default function App() {
  const chat = useConversation();
  const [draft, setDraft] = useState('');
  const input = useRef(null);
  const end = useRef(null);
  const details = chat.conversation?.collected_data;
  const status = chat.conversation?.status;
  const reservation = chat.conversation?.reservation;
  const blocked = !chat.conversation || chat.busy || Boolean(chat.pending) || chat.needsNewSession;
  const newBlocked = chat.busy || chat.pending?.kind === 'message';
  const dictationBase = useRef('');
  const speech = useSpeechInput({
    disabled: blocked,
    onTranscript: (text) => {
      setDraft([dictationBase.current, text].filter(Boolean).join(' '));
      input.current?.focus();
    },
  });
  const playback = useSpokenReplies(chat.messages, { paused: speech.busy });
  const draftTooLong = draft.length > 2000;
  const voiceStatus = !speech.supported ? 'Voice input is unavailable in this browser. You can still type.'
    : speech.status === 'starting' ? 'Opening microphone… Allow access if your browser asks.'
    : speech.status === 'listening' ? 'Listening… Speak your message, then stop.'
    : speech.status === 'processing' ? 'Processing speech… You can cancel dictation to type instead.'
    : speech.status === 'ready' ? 'Speech added. Review or edit your message, then press Send.'
    : 'Microphone is optional. Review your words before sending.';
  const microphoneLabel = speech.status === 'listening' ? 'Stop listening'
    : speech.busy ? 'Cancel dictation' : 'Dictate a message';

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'nearest' });
  }, [chat.messages.length, chat.busy, chat.error]);

  useEffect(() => {
    if (chat.conversation && !blocked && !speech.busy) input.current?.focus();
  }, [chat.conversation, blocked, speech.busy]);

  function submit(event) {
    event.preventDefault();
    if (speech.isActive()) return;
    if (chat.send(draft)) { playback.stop(); setDraft(''); }
  }

  function start() {
    speech.cancel();
    playback.stop();
    setDraft('');
    chat.start();
  }

  function dictate() {
    if (speech.status === 'listening') { speech.stop(); return; }
    if (speech.isActive()) { speech.cancel(); return; }
    if (blocked) return;
    playback.stop();
    dictationBase.current = draft.trim();
    speech.start();
  }

  return <div className="app-shell">
    <a className="skip-link" href="#conversation">Skip to conversation</a>
    <header className="site-header">
      <a className="brand" href="#" aria-label="The Golden Fork home">
        <span className="brand-mark"><Icon name="fork" size={25} /></span>
        <span>The Golden Fork<span className="brand-caption">A LITTLE TIME, WELL SPENT</span></span>
      </a>
      <span className="header-note"><span className="small-dot" /> YOUR TABLE AWAITS</span>
    </header>

    <main className="reservation-layout">
      <aside className="reservation-sidebar" aria-label="Reservation overview">
        <p className="eyebrow">GOOD FOOD. GREAT COMPANY.</p>
        <h1>Make room for{' '}<br /><em>something good.</em></h1>
        <p className="intro">A catch-up, a celebration, or just because. Let’s find you a table.</p>
        <section className="details-card" aria-labelledby="details-heading">
          <div className="card-heading"><h2 id="details-heading">Your reservation</h2><span className="outline-fork"><Icon name="fork" size={18} /></span></div>
          <p className="card-description">The details come together here.</p>
          <dl className="details-list">
            <Detail icon="calendar" label="Date" missing={!details?.date}>{dateLabel(details?.date)}</Detail>
            <Detail icon="clock" label="Time" missing={!details?.time}>{details?.time || 'Not chosen yet'}</Detail>
            <Detail icon="guests" label="Guests" missing={details?.party_size == null}>{details?.party_size == null ? 'Not chosen yet' : `${details.party_size} ${details.party_size === 1 ? 'guest' : 'guests'}`}</Detail>
          </dl>
          <p className="details-note"><Icon name="check" size={15} /> Booked only after you confirm.</p>
        </section>
        <div className="host-note"><span className="note-line" /><p>Less planning.<br /><span>More looking forward.</span></p></div>
      </aside>

      <section className="chat-panel" id="conversation" aria-labelledby="chat-heading" tabIndex={-1}>
        <div className="chat-header">
          <div className="host-avatar"><Icon name="fork" size={25} /><span /></div>
          <div className="chat-heading"><h2 id="chat-heading">Your reservation assistant</h2><p>Let’s make an occasion of it.</p></div>
          {chat.conversation && <button className="new-button" type="button" onClick={start} disabled={newBlocked}><Icon name="plus" size={16} /><span>New conversation</span></button>}
        </div>

        <div className={`conversation-status status-${status || 'idle'}`} role="status">
          <span className="status-dot" />{chat.busy ? (chat.pending?.kind === 'start' ? 'Starting your conversation…' : 'Waiting for the assistant…') : chat.needsNewSession ? 'Start a new conversation to continue' : labels[status] || 'Ready when you are'}
        </div>

        <div className="message-area">
          {!chat.conversation && !chat.messages.length && <div className="welcome">
            <div className="welcome-illustration" aria-hidden="true"><span className="plate plate-outer"><span className="plate-inner"><Icon name="fork" size={43} /></span></span><span className="spark spark-one">✧</span><span className="spark spark-two">✧</span></div>
            <p className="eyebrow">PULL UP A CHAIR</p>
            <h3>A good evening<br />starts with a table.</h3>
            <p>Tell us when you’d like to visit and how many<br className="desktop-break" /> people are coming. We’ll take it from there.</p>
            <button className="primary-button start-button" type="button" onClick={start} disabled={chat.busy}>{chat.busy ? 'Starting…' : 'Start Conversation'}<Icon name="arrow" size={18} /></button>
            <span className="welcome-footnote">A few messages. Something to look forward to.</span>
          </div>}

          <ol className="messages" aria-label="Conversation messages" aria-live="polite" aria-relevant="additions" aria-busy={chat.busy}>
            {chat.messages.map((message) => <li key={message.id} className={`message message-${message.role}`}>
              {message.role === 'assistant' && <span className="message-avatar" aria-hidden="true"><Icon name="fork" size={16} /></span>}
              <div className="message-content"><span className="message-author">{message.role === 'assistant' ? 'The Golden Fork' : 'You'}</span><div className="message-bubble">{message.text}</div>{chat.pending?.kind === 'message' && chat.pending.payload.request_id === message.id && <span className="message-delivery">{chat.busy ? 'Sending…' : 'Response not received'}</span>}</div>
            </li>)}
          </ol>
          {chat.busy && chat.pending?.kind === 'message' && <div className="typing" role="status" aria-label="Assistant is replying"><span /><span /><span /></div>}

          {status === 'completed' && reservation && <section className="success-card" aria-labelledby="success-heading">
            <span className="success-check"><Icon name="check" size={22} /></span>
            <div><p className="eyebrow">SOMETHING TO LOOK FORWARD TO</p><h3 id="success-heading">Your table is booked.</h3><p>{dateLabel(reservation.reservation_date)} · {reservation.reservation_time} · {reservation.party_size} {reservation.party_size === 1 ? 'guest' : 'guests'}</p><p className="booking-reference">Reservation reference <span>{reservation.reservation_id}</span></p></div>
          </section>}

          {chat.error && <div className="error-card" role="alert"><strong>Let’s get you back on track.</strong><p>{chat.error.message}</p>{chat.pending && <button type="button" className="retry-button" onClick={() => { playback.stop(); chat.retry(); }} disabled={chat.busy}>{chat.busy ? 'Retrying…' : chat.pending.kind === 'message' ? 'Retry same message' : 'Try starting again'}</button>}</div>}
          <div ref={end} />
        </div>

        <form className="composer" onSubmit={submit} aria-label="Send a message">
          <div className="voice-controls">
            <label className="spoken-toggle"><input type="checkbox" checked={playback.enabled} onChange={playback.toggle} disabled={!playback.supported} />Spoken replies</label>
            <button className="stop-speaking" type="button" onClick={playback.stop} disabled={!playback.speaking}>Stop speaking</button>
            {!playback.supported && <span className="voice-unavailable">Playback unavailable</span>}
            {playback.speaking && <span className="speaking-state" role="status">Reading reply aloud…</span>}
          </div>
          {playback.error && <p className="voice-error" role="alert">{playback.error}</p>}
          <label className="sr-only" htmlFor="message-input">Your message</label>
          <div className="input-row"><textarea id="message-input" ref={input} value={draft} onChange={(event) => setDraft(event.target.value)} disabled={blocked || speech.busy} rows={2} maxLength={2000} placeholder={chat.conversation ? 'For example, tomorrow at 7pm for 4…' : 'Start a conversation to reserve your table…'} aria-describedby="input-help voice-status" onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form.requestSubmit(); }
          }} /><button className={`microphone-button ${speech.busy ? 'microphone-active' : ''}`} type="button" onClick={dictate} disabled={!speech.supported || blocked} aria-label={microphoneLabel} aria-pressed={speech.busy} title={microphoneLabel}><Icon name={speech.busy ? 'stop' : 'microphone'} /></button><button className="send-button" type="submit" disabled={blocked || speech.busy || draftTooLong || !draft.trim()} aria-label="Send message"><span>Send</span><Icon name="arrow" size={19} /></button></div>
          <p id="voice-status" className="voice-status" role="status">{voiceStatus}</p>
          {speech.busy && speech.transcript && <p className="recognition-preview" aria-live="polite">Heard: {speech.transcript}</p>}
          {speech.error && <p className="voice-error" role="alert">{speech.error}</p>}
          {draftTooLong && <p className="voice-error" role="alert">Your message is over 2,000 characters. Please shorten it before sending.</p>}
          <div className="composer-footer"><span id="input-help">Enter to send <span aria-hidden="true">·</span> Shift + Enter for a new line</span><span className="text-only">A conversation, at your pace.</span></div>
        </form>
      </section>
    </main>
    <footer className="site-footer"><span>THE GOLDEN FORK</span><p>Good company deserves a good table.</p><span className="footer-ornament" aria-hidden="true">✧</span></footer>
  </div>;
}

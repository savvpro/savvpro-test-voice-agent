import { useCallback, useEffect, useRef, useState } from "react";

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const TRY = [
  "I want to book an appointment",
  "I want to check my appointment",
  "I need to cancel an appointment",
  "Please reschedule my appointment",
];

const mins = (value) => {
  if (value == null) return "not yet";
  const hour = Math.floor(value / 60), minute = value % 60;
  return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`;
};

function nextWeekday() {
  const day = new Date();
  day.setDate(day.getDate() + 1);
  while (day.getDay() === 0 || day.getDay() === 6) day.setDate(day.getDate() + 1);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

function readableDate(value) {
  if (!value) return "not yet";
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
}

async function api(path, body, headers = {}) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json", ...headers },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Request failed (${res.status})`);
  return res.json();
}

export default function App() {
  const [msgs, setMsgs] = useState([]);
  const [brain, setBrain] = useState(null);
  const [live, setLive] = useState(false);
  const [mode, setMode] = useState("idle");
  const [interim, setInterim] = useState("");
  const [handsFree, setHandsFree] = useState(!!SR);
  const [error, setError] = useState("");
  const [typed, setTyped] = useState("");
  const [scheduleDate, setScheduleDate] = useState(nextWeekday);
  const [schedule, setSchedule] = useState(null);
  const [appointment, setAppointment] = useState(null);
  const [staffKey, setStaffKey] = useState("");
  const [staffAppointments, setStaffAppointments] = useState(null);
  const sid = useRef(null);
  const liveRef = useRef(false);
  const hfRef = useRef(handsFree);
  const recRef = useRef(null);
  const logRef = useRef(null);

  hfRef.current = handsFree;
  useEffect(() => { logRef.current?.scrollTo({ top: 1e9 }); }, [msgs, interim]);
  useEffect(() => {
    let active = true;
    api(`/api/schedule?date=${encodeURIComponent(scheduleDate)}`)
      .then((result) => { if (active) { setSchedule(result); setError(""); } })
      .catch((e) => { if (active) { setSchedule(null); setError(e.message); } });
    return () => { active = false; };
  }, [scheduleDate]);

  const stopListening = () => { try { recRef.current?.abort(); } catch {} recRef.current = null; };

  const listen = useCallback(() => {
    if (!SR || !liveRef.current || !hfRef.current) { setMode("idle"); return; }
    stopListening();
    const rec = new SR();
    rec.lang = "en-US"; rec.interimResults = true; rec.maxAlternatives = 1;
    let done = false;
    rec.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      setInterim(result[0].transcript);
      if (result.isFinal && !done) { done = true; setInterim(""); send(result[0].transcript); }
    };
    rec.onerror = (event) => {
      if (done) return;
      done = true;
      if (event.error === "no-speech") send("");
      else if (event.error === "not-allowed") { setError("Microphone blocked. Allow it in the browser, or type below."); setHandsFree(false); setMode("idle"); }
      else setMode("idle");
    };
    rec.onend = () => { if (!done) { done = true; if (liveRef.current && hfRef.current) listen(); } };
    recRef.current = rec;
    setMode("listening");
    try { rec.start(); } catch { setMode("idle"); }
  }, []);

  const speak = useCallback((text) => {
    stopListening();
    if (!("speechSynthesis" in window)) { listen(); return; }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.02;
    utterance.onend = () => (liveRef.current ? listen() : setMode("idle"));
    utterance.onerror = utterance.onend;
    setMode("speaking");
    window.speechSynthesis.speak(utterance);
  }, [listen]);

  const apply = useCallback((result) => {
    setMsgs((items) => [...items, { who: "bot", text: result.reply }]);
    setBrain(result);
    if (result.appointment) {
      setAppointment(result.appointment);
      setScheduleDate(result.appointment.appointment_date);
    }
    if (result.action?.startsWith("BOOKED:") || result.action?.startsWith("CANCELLED:") || result.action?.startsWith("RESCHEDULED:")) {
      api(`/api/schedule?date=${encodeURIComponent(scheduleDate)}`).then(setSchedule).catch((e) => setError(e.message));
    }
    if (result.end) { liveRef.current = false; setLive(false); }
    speak(result.reply);
  }, [scheduleDate, speak]);

  async function send(text) {
    if (!liveRef.current) return;
    setError(""); setMode("thinking");
    window.speechSynthesis?.cancel(); stopListening();
    setMsgs((items) => [...items, { who: "you", text: text.trim() ? "(private caller response)" : "(silence)", quiet: !text.trim() }]);
    try { apply(await api("/api/turn", { session_id: sid.current, text })); }
    catch (e) { setError(e.message); setMode("idle"); }
  }

  async function start() {
    setMsgs([]); setBrain(null); setAppointment(null); setError("");
    try {
      const result = await api("/api/call", {});
      sid.current = result.session_id; liveRef.current = true; setLive(true);
      apply(result);
    } catch (e) { setError("Cannot reach the clinic backend on :8000. Is uvicorn running? " + e.message); }
  }

  function hangUp() {
    liveRef.current = false; setLive(false); setMode("idle");
    window.speechSynthesis?.cancel(); stopListening();
  }

  const slots = brain?.slots || {};
  const statusText = { idle: live ? "Waiting" : "Not on a call", speaking: "Assistant speaking", listening: "Listening to you", thinking: "Clinic rules deciding" }[mode];

  return (
    <div className="shell">
      <header>
        <div>
          <h1>Children&apos;s Specialist Clinic</h1>
          <p className="sub">Appointment booking, token management, and follow-up by deterministic Python rules.</p>
        </div>
        <div className={`status ${mode}`} role="status" aria-live="polite"><i /> {statusText}</div>
      </header>

      <main>
        <section className="call" aria-label="Appointment call">
          <div className="controls">
            {!live ? <button className="primary" onClick={start}>Start call</button>
                   : <button className="danger" onClick={hangUp}>End call</button>}
            <label className={!SR ? "off" : ""}>
              <input type="checkbox" checked={handsFree} disabled={!SR} onChange={(event) => {
                setHandsFree(event.target.checked);
                if (!event.target.checked) stopListening(); else if (live) listen();
              }} />
              Hands-free microphone
            </label>
            {!SR && <span className="note">Speech recognition needs Chrome or Edge. You can still type.</span>}
          </div>
          <div className="log" ref={logRef} aria-label="Conversation transcript">
            {!msgs.length && <p className="empty">Start a call to book, check, cancel, or reschedule an appointment.</p>}
            {msgs.map((message, index) => <p key={index} className={`bubble ${message.who} ${message.quiet ? "quiet" : ""}`}>{message.text}</p>)}
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          <form onSubmit={(event) => { event.preventDefault(); if (live) { send(typed); setTyped(""); } }}>
            <input value={typed} onChange={(event) => setTyped(event.target.value)} disabled={!live}
              placeholder={live ? "Type what the caller says" : "Start a call first"} aria-label="Type a reply" />
            <button disabled={!live}>Send</button>
            <button type="button" className="ghost" disabled={!live} onClick={() => send("")}>Stay silent</button>
          </form>
          <div className="try">
            <span>Try an appointment request:</span>
            {TRY.map((text) => <button key={text} className="chip" disabled={!live} onClick={() => send(text)}>{text}</button>)}
          </div>
        </section>

        <aside aria-label="Appointment and clinic schedule">
          <div className="slip">
            <h2>Appointment details</h2>
            <dl>
              <dt>Token</dt><dd className={appointment ? "" : "blank"}>{appointment ? `#${appointment.token}` : slots.token ? `#${slots.token} (proposed)` : "not assigned"}</dd>
              <dt>Child</dt><dd className={appointment?.child_name || slots.child_name ? "" : "blank"}>{appointment?.child_name || slots.child_name || "not yet"}</dd>
              <dt>Age</dt><dd className={appointment || slots.child_age != null ? "" : "blank"}>{appointment?.child_age ?? slots.child_age ?? "not yet"}</dd>
              <dt>Guardian</dt><dd className={appointment?.guardian_name || slots.guardian_name ? "" : "blank"}>{appointment?.guardian_name || slots.guardian_name || "not yet"}</dd>
              <dt>Contact</dt><dd>{appointment?.contact || slots.contact || "not provided"}</dd>
              <dt>Date</dt><dd className={appointment || slots.date ? "" : "blank"}>{readableDate(appointment?.appointment_date || slots.date)}</dd>
              <dt>Time</dt><dd className={appointment || slots.time != null ? "" : "blank"}>{mins(appointment?.start_min ?? slots.time)}</dd>
              <dt>Status</dt><dd>{appointment?.status || (brain?.state === "CONFIRM_BOOK" ? "Awaiting confirmation" : "not booked")}</dd>
            </dl>
            {brain?.expecting && <p className="asking">Waiting for: <b>{brain.expecting}</b></p>}
          </div>

          <div className="panel">
            <h2>Daily token schedule</h2>
            <p className="note">Monday to Friday · 35 tokens · 14 minutes each · 9:00 AM–5:10 PM</p>
            <label className="schedule-date">Appointment date
              <input type="date" value={scheduleDate} onChange={(event) => setScheduleDate(event.target.value)} />
            </label>
            {schedule && <>
              <p className="schedule-summary">{schedule.available_count} available · {schedule.active_count} occupied</p>
              <div className="token-grid" aria-label="Token availability">
                {schedule.slots.map((slot) => <div key={slot.token} className={`token ${slot.status}`} title={`${mins(slot.start_min)} — ${slot.status}`}>
                  <b>{slot.token}</b><span>{mins(slot.start_min)}</span><small>{slot.status}</small>
                </div>)}
              </div>
            </>}
          </div>

          <div className="panel">
            <h2>Last decision</h2>
            {brain ? <table><tbody>
              <tr><th>Intent</th><td>{brain.intent || "none yet"}</td></tr>
              <tr><th>State</th><td>{brain.state}</td></tr>
              <tr><th>Action</th><td>{brain.action}</td></tr>
              <tr><th>Heard</th><td><code>{JSON.stringify(brain.extracted || {})}</code></td></tr>
            </tbody></table> : <p className="empty">Nothing yet.</p>}
          </div>
          <div className="panel">
            <h2>Deterministic decision trace</h2>
            {brain?.trace?.length ? <ol className="trace">{brain.trace.map((entry, index) => <li key={index}>{entry}</li>)}</ol>
              : <p className="empty">Rule firings appear here.</p>}
          </div>
          <div className="panel">
            <h2>Authorized staff records</h2>
            <p className="note">Staff API credentials are held only in this page's memory and are never saved in browser storage.</p>
            <form onSubmit={async (event) => {
              event.preventDefault();
              try {
                const records = await api("/api/appointments", null, { Authorization: `Bearer ${staffKey}` });
                setStaffAppointments(records); setError("");
              } catch (e) { setStaffAppointments(null); setError("Staff authorization failed or records are unavailable."); }
            }}>
              <input type="password" value={staffKey} onChange={(event) => setStaffKey(event.target.value)}
                autoComplete="off" placeholder="Staff access key" aria-label="Staff access key" />
              <button type="submit">View records</button>
            </form>
            {staffAppointments && <div className="staff-records">
              <p>{staffAppointments.length} appointment records</p>
              {staffAppointments.map((item) => <article className="staff-record" key={item.id}>
                <b>Token {item.token} · {readableDate(item.appointment_date)} · {mins(item.start_min)} · {item.status}</b>
                <span>Child: {item.child_name} ({item.child_age}) · Guardian: {item.guardian_name}</span>
                {item.contact && <span>Contact: {item.contact}</span>}
                <span>Verified notification email: {item.email || "not provided"}</span>
              </article>)}
            </div>}
          </div>
        </aside>
      </main>
    </div>
  );
}

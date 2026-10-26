import { useEffect, useState } from 'react'
import VoiceVisualizer from './VoiceVisualizer'

const steps = [
  { title: 'Identify the parcel', text: 'Share the tracking ID. REDELIVER reads it back so you can confirm before moving on.' },
  { title: 'Verify the recipient', text: 'Confirm the last four digits of the phone number linked to the parcel.' },
  { title: 'Choose what happens next', text: 'Check status, pick a new delivery window, collect from a point, or cancel when allowed.' },
]
const tiles = [
  { title: 'One missed attempt. Four ways forward.', text: 'Availability follows the parcel’s status: check what happened, book another slot, choose a pickup point, or cancel with confirmation.' },
  { title: 'Check parcel status', text: 'Get the current status and a plain-language explanation when available.' },
  { title: 'Choose a pickup point', text: 'Browse fictional demo locations across Islamabad, Lahore, Karachi, Peshawar, and Rawalpindi.' },
  { title: 'Speak or type', text: 'Use browser speech recognition where supported, or type the same response.' },
  { title: 'Keep a human in the loop', text: 'The assistant asks before offering a transfer after repeated unclear turns.' },
]
const cases = [
  { tag: 'Status', q: '“Did they try to deliver?”', text: 'Check the parcel’s current status and understand what a failed attempt means.' },
  { tag: 'Reschedule', q: '“Can they come tomorrow?”', text: 'Choose from available delivery windows and confirm the booking through the backend.' },
  { tag: 'Pickup', q: '“Can I collect it nearby?”', text: 'Select a listed pickup location and confirm it before the call moves on.' },
]

function Dot({ on }) { return <span className={`status-dot ${on ? 'online' : 'offline'}`} aria-hidden="true" /> }

export default function SiteHome({ backend, sessionId, visualState, analyser, theme, trace, onCall, onDashboard, onToggleTheme, onRetry, menuOpen, setMenuOpen }) {
  const [step, setStep] = useState(0)
  const online = backend === 'online'

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return undefined
    const io = new IntersectionObserver((entries) => entries.forEach((entry) => { if (entry.isIntersecting) setStep(Number(entry.target.dataset.i)) }), { rootMargin: '-45% 0px -45% 0px' })
    document.querySelectorAll('.story-step').forEach((node) => io.observe(node))
    return () => io.disconnect()
  }, [])

  return <div className="site-shell" id="home">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="site-nav">
      <a href="#home" className="brand"><span className="brand-symbol">R<span>/</span>D</span><span>REDELIVER</span></a>
      <nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#capabilities">What it handles</a><a href="#platform">Use cases</a></nav>
      <div className="nav-actions">
        <button className="theme-button" type="button" onClick={onToggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}><span aria-hidden="true">{theme === 'dark' ? '☼' : '◐'}</span><span>{theme === 'dark' ? 'Light' : 'Dark'} mode</span></button>
        <button className="nav-demo" type="button" onClick={onCall}>Voice demo <span aria-hidden="true">↗</span></button>
        <button className="nav-dashboard" type="button" onClick={onDashboard}>Open dashboard <span aria-hidden="true">↗</span></button>
        <button className="mobile-menu" type="button" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen} aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}>{menuOpen ? '×' : '☰'}</button>
      </div>
      {menuOpen && <nav className="mobile-nav" aria-label="Mobile navigation">
        <a href="#how-it-works" onClick={() => setMenuOpen(false)}>How it works</a>
        <a href="#capabilities" onClick={() => setMenuOpen(false)}>What it handles</a>
        <a href="#platform" onClick={() => setMenuOpen(false)}>Use cases</a>
        <button type="button" onClick={onCall}>Open voice demo ↗</button>
        <button type="button" onClick={onDashboard}>Open dashboard ↗</button>
      </nav>}
    </header>

    <main id="main-content">
      <section className="hero" aria-labelledby="hero-title">
        <h1 id="hero-title">Missed delivery.<br />Next move.</h1>
        <p className="hero-lede">A voice assistant that helps people in Pakistan check a parcel, choose a new delivery time, or find a pickup point in a few clear steps.</p>
        <div className="hero-actions">
          <button className="primary-button" type="button" onClick={onCall}>{sessionId ? 'Continue your call' : 'Try the voice demo'}<span aria-hidden="true">↗</span></button>
          <a className="secondary-link" href="#how-it-works">See how it works <span aria-hidden="true">↓</span></a>
        </div>
        <div className="hero-stage">
          <VoiceVisualizer state={visualState} analyser={analyser} theme={theme} />
          <span className="chip chip-a"><Dot on />Tracking ID verified</span>
          <span className="chip chip-b"><Dot on />Delivery moved to tomorrow</span>
          <span className="chip chip-c"><Dot on />Pickup point chosen</span>
        </div>
        <ul className="hero-stats" aria-label="Product facts">
          <li><b>01</b><span>One clear conversation</span><small>Each step comes from a real backend state.</small></li>
          <li><b>05</b><span>Pickup points in Pakistan</span><small>Demo locations in five cities.</small></li>
          <li><b>PKT</b><span>Local time and language</span><small>Designed around Pakistan Standard Time.</small></li>
        </ul>
      </section>

      {trace && <section className="inline-trace scroll-reveal" aria-label="Latest backend decision trace"><span className="eyebrow">BACKEND TRACE</span><div><span>Intent <b>{trace.intent || 'none'}</b></span><span>Confidence <b>{typeof trace.intent_confidence === 'number' ? `${Math.round(trace.intent_confidence * 100)}%` : 'none'}</b></span><span>State <b>{trace.state_before || 'none'} → {trace.state_after || 'none'}</b></span><span>Slots <b>{Object.keys(trace.slots_extracted || {}).length ? Object.entries(trace.slots_extracted).map(([key, value]) => `${key}: ${value}`).join(' · ') : 'none'}</b></span></div></section>}

      <section className="story scroll-reveal" id="how-it-works">
        <div className="story-sticky">
          <span className="story-meter" aria-hidden="true"><i style={{ transform: `scaleY(${(step + 1) / steps.length})` }} /></span>
          <p className="kicker">From missed to sorted</p>
          <h2>A short route back on track.</h2>
          <p className="story-copy">Every call follows a simple, visible flow. The service verifies first, then gives options based on that parcel’s status.</p>
        </div>
        <div className="story-steps">
          {steps.map((item, i) => <article key={item.title} data-i={i} className={`story-step ${i === step ? 'on' : ''}`}><span className="story-num">0{i + 1}</span><h3>{item.title}</h3><p>{item.text}</p></article>)}
        </div>
      </section>

      <section className="bento-section scroll-reveal" id="capabilities">
        <div className="section-head"><div><p className="kicker">Built around the delivery</p><h2>Useful answers. Real actions.</h2></div><p>The assistant uses explicit backend rules and parcel records. It doesn’t promise actions outside the current service.</p></div>
        <div className="bento">
          {tiles.map((tile, i) => <article key={tile.title} className={`bento-card bento-${i}`}>
            {i === 0 && <div className="route" aria-hidden="true"><i /><i /><i /><i /></div>}
            <h3>{tile.title}</h3><p>{tile.text}</p>
          </article>)}
        </div>
      </section>

      <section className="cases scroll-reveal" id="platform">
        <div className="section-head"><div><p className="kicker">Made for the moment after the bell</p><h2>Three things people need to know.</h2></div></div>
        <div className="case-grid">
          {cases.map((item) => <article key={item.tag} className="quote-card"><span className="quote-tag">{item.tag}</span><h3>{item.q}</h3><p>{item.text}</p></article>)}
        </div>
      </section>

      <section className="finale scroll-reveal">
        <div className="finale-card">
          <div>
            <h2>Get your next move.</h2>
            <p>This is a local prototype: sessions and parcel data are held in backend memory. Browser speech features depend on your device and browser. The assistant’s choices come from deterministic Python rules, not a general-purpose AI model.</p>
            <ul className="facts"><li><Dot on={online} />{online ? 'API reachable now' : backend === 'checking' ? 'Checking API' : 'API not reachable'}</li><li>Browser-native speech</li><li>Fictional parcel records</li></ul>
          </div>
          <button className="primary-button" type="button" onClick={onCall}>Open the voice demo<span aria-hidden="true">↗</span></button>
        </div>
      </section>
    </main>

    <footer className="site-footer"><a href="#home" className="brand"><span className="brand-symbol">R<span>/</span>D</span><span>REDELIVER</span></a><span>PARCEL SUPPORT / PAKISTAN</span><button type="button" onClick={onCall}>Voice demo ↗</button><button type="button" onClick={onDashboard}>Dashboard ↗</button><span>DEMO DATA · © 2026</span></footer>
  </div>
}
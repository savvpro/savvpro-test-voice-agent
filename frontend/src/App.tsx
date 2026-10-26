import { useEffect, useRef, useState } from 'react'
import { AudioLines, Check, CircleHelp, Clock3, Mic, RotateCcw, Send, Sparkles, Wallet, Volume2, Download, PieChart } from 'lucide-react'
import './review.css'

type Message = { role: 'assistant' | 'caller'; text: string; turnId?: string; sourceText?: string; confidence?: number; decisionTrace?: Array<Record<string, string | number>>; corrected?: boolean }
type Expense = { amount: number; currency: string; category: string; date: string; description: string }
type ApiTurn = { reply: string; status: string; expense: Expense | null; total: number; totals: Record<string, number>; expenses: Expense[]; saved_expenses: Expense[]; turn_id?: string; confidence: number; decision_trace: Array<Record<string, string | number>> }

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const welcome = "Hi there! I’m Penny, your expense logging assistant. Tell me what you spent, for example: ‘$12.50 on lunch yesterday.’"
// review intents and front-end correction UI removed

function newSessionId() {
  return crypto.randomUUID()
}

function getSpeechRecognition(): any {
  const speechWindow = window as typeof window & { SpeechRecognition?: new () => any; webkitSpeechRecognition?: new () => any }
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null
}

export default function App() {
  const [sessionId, setSessionId] = useState(() => {
    const storedSessionId = window.localStorage.getItem('penny-session-id')
    if (storedSessionId) return storedSessionId
    const nextSessionId = newSessionId()
    window.localStorage.setItem('penny-session-id', nextSessionId)
    return nextSessionId
  })
  const [messages, setMessages] = useState<Message[]>([{ role: 'assistant', text: welcome }])
  const [input, setInput] = useState('')
  const [listening, setListening] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('collecting')
  const [expense, setExpense] = useState<ApiTurn['expense']>(null)
  const [totals, setTotals] = useState<Record<string, number>>({})
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [savedExpenses, setSavedExpenses] = useState<Expense[]>([])
  
  const [showHelp, setShowHelp] = useState(false)
  const [speechAvailable] = useState(() => Boolean(getSpeechRecognition()))
  const [audioPlaying, setAudioPlaying] = useState(false)
  const [showChart, setShowChart] = useState(false)
  const [chartCurrency, setChartCurrency] = useState<string | null>(null)
  // theme is fixed to black-orange for this deployment
  const recognition = useRef<any>(null)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
  const chartRef = useRef<HTMLCanvasElement | null>(null)
  const conversationRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (showChart) document.body.classList.add('no-scroll')
    else document.body.classList.remove('no-scroll')
    return () => { document.body.classList.remove('no-scroll') }
  }, [showChart])

  useEffect(() => {
    const conversation = conversationRef.current
    conversation?.scrollTo({ top: conversation.scrollHeight, behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    // force the black-orange theme at startup
    document.documentElement.classList.add('theme-blackorange')
  }, [])

  useEffect(() => {
    void fetch(`${API_URL}/api/expenses/${sessionId}`)
      .then((response) => response.ok ? response.json() as Promise<ApiTurn> : null)
      .then((result) => {
        if (!result) return
        setTotals(result.totals)
        setExpenses(result.expenses)
      })
      .catch(() => undefined)
  }, [sessionId])

  async function sendMessage(rawText: string) {
    const transcript = rawText.trim()
    if (!transcript || busy) return
    setMessages((current) => [...current, { role: 'caller', text: transcript }])
    setInput('')
    setBusy(true)
    try {
      const response = await fetch(`${API_URL}/api/turn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, transcript }),
      })
      if (!response.ok) throw new Error('The assistant could not respond. Please try again.')
      const result: ApiTurn = await response.json()
      setMessages((current) => [...current, { role: 'assistant', text: result.reply, turnId: result.turn_id, sourceText: transcript, confidence: result.confidence, decisionTrace: result.decision_trace }])
      setStatus(result.status)
      setExpense(result.expense)
      setTotals(result.totals)
      setExpenses(result.expenses)
      setSavedExpenses(result.saved_expenses)
      if ('speechSynthesis' in window) {
        // speak via centralized handler so the audio button can control it
        speakText(result.reply)
      }
    } catch {
      setMessages((current) => [...current, { role: 'assistant', text: 'I’m having trouble reaching the expense logger. Please check that the backend is running and try again.' }])
    } finally {
      setBusy(false)
    }
  }

  function speakText(text: string) {
    if (!('speechSynthesis' in window)) return
    try {
      window.speechSynthesis.cancel()
    } catch {}
    const u = new SpeechSynthesisUtterance(text)
    utteranceRef.current = u
    u.onend = () => { setAudioPlaying(false); utteranceRef.current = null }
    u.onerror = () => { setAudioPlaying(false); utteranceRef.current = null }
    window.speechSynthesis.speak(u)
    setAudioPlaying(true)
  }

  function toggleAudio() {
    if (!('speechSynthesis' in window)) return
    if (audioPlaying) {
      window.speechSynthesis.cancel()
      setAudioPlaying(false)
      utteranceRef.current = null
      return
    }
    // play last assistant message
    const last = [...messages].slice().reverse().find(m => m.role === 'assistant')
    if (last) speakText(last.text)
  }

  function downloadCSV() {
    const rows = (savedExpenses && savedExpenses.length > 0 ? savedExpenses : expenses) || []
    if (!rows.length) {
      // create an empty CSV with header
      const csv = 'date,currency,amount,category,description\n'
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `penny-expenses-${sessionId}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      return
    }
    const quote = (s: any) => '"' + (s === undefined || s === null ? '' : String(s).replace(/"/g, '""')) + '"'
    const header = ['date','currency','amount','category','description']
    const csv = [header.join(',')].concat(rows.map(r => [r.date, r.currency, r.amount.toFixed(2), r.category, r.description || ''].map(quote).join(','))).join('\n') + '\n'
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `penny-expenses-${sessionId}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  function computeCategoryTotalsForCurrentMonth() {
    const all = [...(savedExpenses || []), ...(expenses || [])]
    const now = new Date()
    const year = now.getFullYear()
    const month = now.getMonth()
    const byCategory: Record<string, Record<string, number>> = {}
    const totalsByCurrency: Record<string, number> = {}
    for (const e of all) {
      if (!e || !e.date) continue
      const d = new Date(e.date)
      if (isNaN(d.getTime())) continue
      if (d.getFullYear() === year && d.getMonth() === month) {
        const cat = e.category || 'Uncategorized'
        const cur = e.currency || 'USD'
        byCategory[cat] = byCategory[cat] || {}
        byCategory[cat][cur] = (byCategory[cat][cur] || 0) + (e.amount || 0)
        totalsByCurrency[cur] = (totalsByCurrency[cur] || 0) + (e.amount || 0)
      }
    }
    const categories = Object.keys(byCategory).map((category) => ({ category, totals: byCategory[category] }))
    const currencies = Object.keys(totalsByCurrency)
    return { categories, currencies, totalsByCurrency }
  }

  // draw a simple pie chart into the canvas when requested
  function drawChart() {
    const canvas = chartRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const result = computeCategoryTotalsForCurrentMonth()
    const data = result.categories
    const currencies = result.currencies
    const totalsByCurrency = result.totalsByCurrency
    // chosen currency for drawing slices
    const drawCurrency = chartCurrency || (currencies.length > 0 ? currencies[0] : null)
    // size canvas for high-DPI and make drawing responsive to container size
    const dpr = window.devicePixelRatio || 1
    const cw = canvas.clientWidth || 420
    // set canvas height proportional to width so it fits modal box
    const ch = Math.max(200, Math.round(cw * 0.72))
    canvas.style.height = `${ch}px`
    canvas.width = Math.floor(cw * dpr)
    canvas.height = Math.floor(ch * dpr)
    ctx.setTransform(dpr,0,0,dpr,0,0)
    ctx.clearRect(0,0,cw,ch)
    if (!data.length || !drawCurrency) {
      ctx.fillStyle = '#999'
      ctx.font = '14px sans-serif'
      ctx.fillText('No expenses for this month', 10, 30)
      return
    }
    // compute amounts in selected currency; categories without that currency are zero
    const amounts = data.map((r) => ({ category: r.category, amount: +(r.totals[drawCurrency] || 0) }))
    const total = amounts.reduce((s, r) => s + r.amount, 0)
    const cx = cw/2
    const cy = ch/2
    const radius = Math.min(cx, cy) - 10
    let start = -Math.PI/2
    const palette = ['#e6fff3','#c7f8e7','#a8f0db','#84e9cf','#5fe0c3','#3bd9b8','#23dc70','#0fa55a']
    amounts.forEach((slice, i) => {
      const frac = total === 0 ? 0 : slice.amount / total
      const end = start + frac * Math.PI * 2
      ctx.beginPath()
      ctx.moveTo(cx,cy)
      ctx.arc(cx,cy,radius,start,end)
      ctx.closePath()
      ctx.fillStyle = palette[i % palette.length]
      ctx.fill()
      start = end
    })
    // center label
    ctx.fillStyle = 'rgba(0,0,0,0.6)'
    ctx.font = '14px sans-serif'
    ctx.textAlign = 'center'
    // center: show total for selected currency if available, else show all totals
    const centerText = drawCurrency ? `${drawCurrency} ${(totalsByCurrency[drawCurrency]||0).toFixed(2)}` : Object.entries(totalsByCurrency).map(([c, v]) => `${c} ${v.toFixed(2)}`).join(' · ')
    ctx.fillText(centerText, cx, cy)
  }

  useEffect(() => {
    if (!showChart) return
    drawChart()
    const onResize = () => drawChart()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [showChart, expenses, savedExpenses, chartCurrency])

  // front-end correction recording removed; backend still accepts corrections if used server-side

  function startListening() {
    const Recognition = getSpeechRecognition()
    if (!Recognition) return
    const instance = new Recognition()
    recognition.current = instance
    instance.lang = 'en-US'
    instance.interimResults = false
    instance.maxAlternatives = 1
    instance.onstart = () => setListening(true)
    instance.onend = () => setListening(false)
    instance.onerror = () => setListening(false)
    instance.onresult = (event: any) => void sendMessage(event.results[0][0].transcript)
    instance.start()
  }

  async function resetConversation() {
    recognition.current?.stop()
    window.speechSynthesis?.cancel()
    await fetch(`${API_URL}/api/reset/${sessionId}`, { method: 'POST' }).catch(() => undefined)
    const nextSessionId = newSessionId()
    window.localStorage.setItem('penny-session-id', nextSessionId)
    setSessionId(nextSessionId)
    setMessages([{ role: 'assistant', text: welcome }])
    setStatus('collecting')
    setExpense(null)
    setTotals({})
    setExpenses([])
    setSavedExpenses([])
    setInput('')
  }

  /* restaurant-note and exports removed per user request */

  // theme toggle removed; app uses black + orange theme only

  const saved = status === 'saved' && expense
  const totalLabel = Object.entries(totals).map(([currency, amount]) => `${currency} ${amount.toFixed(2)}`).join(' · ') || 'USD 0.00'

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#home" aria-label="Penny home">
          <span className="brand-mark"><Wallet size={17} /></span>
          <span className="brand-text">
            <strong>Penny</strong>
            <small className="brand-subtitle">your expense assistant</small>
          </span>
        </a>
        <div className="topbar-right"><span className="availability"><span /> Your personal expense log</span>
          <div style={{display:'flex',alignItems:'center',gap:8}}>
            <button className="help-button" onClick={() => setShowHelp(true)} title="How Penny works" aria-label="How Penny works"><CircleHelp size={19} /></button>
          </div>
        </div>
      </header>

      <section className="workspace" id="home">
        <aside className="intro-panel">
          <div className="eyebrow"><span className="eyebrow-line" /> MONEY, MINDFULLY TRACKED</div>
          <h1>Know where<br /><span>it goes.</span></h1>
          <p className="intro-copy">Log everyday spending in a few words. A quick voice note is all it takes to stay on top of things.</p>
          <div className="steps">
            <div className="step"><span className="step-number">01</span><span>Say what you spent</span></div>
            <div className="step"><span className="step-number">02</span><span>Choose or confirm a category</span></div>
            <div className="step"><span className="step-number">03</span><span>Review and save it</span></div>
          </div>
          {/* restaurant-note removed per user request */}
          <div className="decor decor-one" /><div className="decor decor-two" />
        </aside>

        <section className="assistant-card" aria-label="Expense logging assistant">
          <div className="card-heading"><div className="assistant-identity"><div className="avatar"><AudioLines size={19} /></div><div><h2>Your expense assistant</h2><div className="assistant-presence"><span className="presence-dot" /> Ready when you are</div></div></div><button className="reset-button" onClick={resetConversation} aria-label="Start a new conversation" title="Start over"><RotateCcw size={17} /></button></div>
          <div className="conversation" ref={conversationRef} aria-live="polite">
            <div className="date-divider"><span /> TODAY <span /></div>
            {messages.map((message, index) => {
              return (
                <div className={`message-row ${message.role}`} key={`${index}-${message.text}`}>
                  {message.role === 'assistant' && <div className="mini-avatar"><AudioLines size={14} /></div>}
                  <div className="message-content">
                    <span className="message-author">{message.role === 'assistant' ? 'PENNY' : 'YOU'}</span>
                    <div className={`message-bubble ${message.role}`}>{message.text}</div>
                    {message.corrected && <span className="correction-recorded">Correction recorded</span>}
                  </div>
                </div>
              )
            })}
            {busy && <div className="message-row assistant"><div className="mini-avatar"><AudioLines size={14} /></div><div className="typing-dots"><i /><i /><i /></div></div>}
            {saved && <div className="booking-summary"><div className="booking-check"><Check size={16} /></div><div><strong>{savedExpenses.length > 1 ? `${savedExpenses.length} expenses saved` : `Expense saved · ${expense.currency} ${expense.amount.toFixed(2)}`}</strong><span>{savedExpenses.length > 1 ? savedExpenses.map((entry) => `${entry.currency} ${entry.amount.toFixed(2)}`).join(' · ') : `${expense.category}${expense.description ? ` · ${expense.description}` : ''} · ${expense.date}`} <b>·</b> Total {totalLabel}</span></div></div>}
            {expenses.length > 0 && <section className="expense-ledger" aria-label="Expenses logged in this session"><div className="ledger-heading"><span>THIS SESSION</span><strong>{totalLabel}</strong></div>{expenses.map((entry, index) => <div className="ledger-row" key={`${index}-${entry.amount}-${entry.date}`}><span><strong>{entry.description || entry.category}</strong><small>{entry.category} · {entry.date}</small></span><b>{entry.currency} {entry.amount.toFixed(2)}</b></div>)}</section>}
          </div>
          <div className="composer-wrap">
            {listening && <div className="listening-label"><span className="sound-bars"><i /><i /><i /><i /></span> Listening… speak naturally</div>}
            <form className="composer" onSubmit={(event) => { event.preventDefault(); void sendMessage(input) }}>
              <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="e.g. I spent $12 on lunch…" aria-label="Your message" disabled={busy} />
              <button type="button" className={`mic-button ${listening ? 'active' : ''}`} disabled={!speechAvailable || busy} onClick={() => listening ? recognition.current?.stop() : startListening()} aria-label={listening ? 'Stop listening' : 'Speak'} title={speechAvailable ? 'Speak' : 'Speech recognition is unavailable in this browser'}><Mic size={18} /></button>
              <button type="submit" className="send-button" disabled={!input.trim() || busy} aria-label="Send message"><Send size={17} /></button>
            </form>
            <div className="composer-hint"><span>{speechAvailable ? <><Mic size={12} /> Say an expense or type it</> : <>Type an expense to get started</>}</span><span className="secure-note"><span /> Stored for this session</span></div>
          </div>
          <div className="card-footer"><span><Sparkles size={13} /> Your money, a little clearer</span>
            <div style={{display:'flex',gap:8,alignItems:'center'}}>
              <button className="help-button" onClick={downloadCSV} title="Download CSV of session expenses"><Download size={14} />&nbsp;Download CSV</button>
              <button className="help-button" onClick={() => setShowChart(true)} title="View chart for current month"><PieChart size={14} />&nbsp;View chart</button>
              <button onClick={() => toggleAudio()} title={audioPlaying ? 'Stop audio' : 'Play latest reply'} aria-pressed={audioPlaying}><Volume2 size={14} /> {audioPlaying ? 'Stop audio' : 'Play audio'}</button>
            </div>
          </div>
        </section>
      </section>
      <footer className="page-footer"><span><Clock3 size={13} /> Running total this session: {totalLabel}</span><span>Simple, private expense tracking.</span></footer>
      {showHelp && <div className="modal-backdrop" role="presentation" onClick={() => setShowHelp(false)}><section className="help-modal" role="dialog" aria-modal="true" aria-labelledby="help-title" onClick={(event) => event.stopPropagation()}><button className="modal-close" onClick={() => setShowHelp(false)} aria-label="Close help">×</button><div className="modal-icon"><CircleHelp size={20} /></div><h2 id="help-title">How Penny works</h2><p>Tell Penny what you spent, such as “$12 on lunch yesterday.” It identifies the amount, category, and date, then asks you to confirm before saving.</p><p>Saved expenses are stored in the local SQLite database and shown in this session’s ledger. The reset button clears this session’s saved entries.</p><button className="modal-action" onClick={() => setShowHelp(false)}>Got it</button></section></div>}
      {showChart && (
        <div className="modal-backdrop" role="presentation" onClick={() => setShowChart(false)}>
          <section className="help-modal" role="dialog" aria-modal="true" aria-labelledby="chart-title" onClick={(event) => event.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowChart(false)} aria-label="Close chart">×</button>
            <div className="modal-icon"><span className="brand-mark"><Wallet size={17} /></span></div>
            <h2 id="chart-title">Expenses — this month</h2>
            <p>Category breakdown for the current month.</p>
            <div style={{maxWidth:420,width:'100%',margin:'0 auto', display:'flex',justifyContent:'center',alignItems:'center'}}>
              <canvas ref={el => { if (el) { chartRef.current = el; drawChart() } }} style={{width:360,height:300,display:'block',margin:'0 auto'}} />
            </div>
            <div style={{marginTop:12}}>
              {(() => {
                const res = computeCategoryTotalsForCurrentMonth()
                if (!res.categories.length) return <div>No expenses for this month</div>
                const currencies = res.currencies
                // ensure a selected currency
                if (!chartCurrency && currencies.length) setChartCurrency(currencies[0])
                return (
                  <div style={{display:'grid',gap:8}}>
                    <div style={{display:'flex',alignItems:'center',gap:8}}>
                      <label style={{fontSize:12,color:'var(--muted)'}}>View by currency:</label>
                      <select value={chartCurrency||''} onChange={(e) => setChartCurrency(e.target.value)}>
                        {currencies.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </div>
                    <div style={{display:'grid',gap:6}}>
                      {res.categories.map((row, idx) => (
                        <div key={row.category} style={{display:'flex',justifyContent:'space-between'}}>
                          <span style={{display:'flex',gap:8,alignItems:'center'}}>
                            <span style={{width:12,height:12,background:['#e6fff3','#c7f8e7','#a8f0db','#84e9cf','#5fe0c3','#3bd9b8','#23dc70','#0fa55a'][idx%8]}} />
                            {row.category}
                          </span>
                          <strong>{(row.totals[chartCurrency||currencies[0]]||0).toFixed(2)} {chartCurrency||currencies[0]}</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}
            </div>
          </section>
        </div>
      )}
    </main>
  )
}
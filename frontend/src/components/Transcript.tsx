export interface Message {
  role: 'caller' | 'assistant'
  text: string
}

export default function Transcript({ messages }: { messages: Message[] }) {
  return (
    <section aria-label="Transcript" className="panel">
      <h2>Transcript</h2>
      <div className="transcript" role="log" aria-live="polite">
        {messages.length === 0 && <p className="muted">Start a call to begin.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <span className="who">{m.role === 'caller' ? 'You' : 'Assistant'}</span>
            {m.text}
          </div>
        ))}
      </div>
    </section>
  )
}

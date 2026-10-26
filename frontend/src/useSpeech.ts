import { useCallback, useEffect, useRef, useState } from 'react'

const Ctor = typeof window === 'undefined' ? undefined : window.SpeechRecognition ?? window.webkitSpeechRecognition
const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window

export function useSpeech() {
  const [listening, setListening] = useState(false)
  const rec = useRef<SpeechRecognitionLike | null>(null)
  const supported = !!Ctor

  const stop = useCallback(() => {
    rec.current?.abort()
    if (canSpeak) window.speechSynthesis.cancel()
  }, [])

  useEffect(() => stop, [stop])

  const listen = useCallback(
    () =>
      new Promise<string>((resolve) => {
        if (!Ctor) return resolve('')
        if (canSpeak) window.speechSynthesis.cancel() // never hear ourselves
        rec.current?.abort()
        const r = new Ctor()
        rec.current = r
        let text = ''
        r.lang = 'en-US'
        r.interimResults = false
        r.maxAlternatives = 1
        r.onresult = (e) => {
          text = Array.from(e.results, (x) => x[0].transcript).join(' ').trim()
        }
        r.onerror = () => {} // no-speech / aborted / not-allowed: resolve '' via onend
        r.onend = () => {
          setListening(false)
          resolve(text)
        }
        setListening(true)
        try {
          r.start()
        } catch {
          setListening(false)
          resolve('')
        }
      }),
    [],
  )

  const speak = useCallback(
    (text: string) =>
      new Promise<void>((resolve) => {
        if (!canSpeak) return resolve()
        rec.current?.abort()
        const u = new SpeechSynthesisUtterance(text)
        u.lang = 'en-US'
        u.onend = () => resolve()
        u.onerror = () => resolve()
        window.speechSynthesis.cancel()
        window.speechSynthesis.speak(u)
      }),
    [],
  )

  return { supported, listening, listen, stop, speak }
}

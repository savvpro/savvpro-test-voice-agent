import { useCallback, useEffect, useRef, useState } from 'react'

const Ctor = typeof window === 'undefined' ? undefined : window.SpeechRecognition ?? window.webkitSpeechRecognition
const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window

const VOICE_KEY = 'voice'
// Most natural first: Edge/Windows neural, macOS/iOS downloaded voices, Chrome's cloud voice.
const RANK = [/natural|neural|online/i, /premium|enhanced/i, /^google/i, /samantha|ava|allison|zira|aria|jenny/i]

/** The most natural-sounding en-US voice the browser offers, if any. */
export function pickVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  const us = voices.filter((v) => v.lang.replace('_', '-').startsWith('en-US'))
  const score = (v: SpeechSynthesisVoice) => {
    const i = RANK.findIndex((re) => re.test(v.name))
    return i === -1 ? RANK.length : i
  }
  return us.reduce<SpeechSynthesisVoice | undefined>((best, v) => (!best || score(v) < score(best) ? v : best), undefined)
}

function saved(): string {
  try {
    return localStorage.getItem(VOICE_KEY) ?? ''
  } catch {
    return ''
  }
}

export function useSpeech() {
  const [listening, setListening] = useState(false)
  const rec = useRef<SpeechRecognitionLike | null>(null)
  const supported = !!Ctor
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [voiceName, setVoiceNameState] = useState(saved)

  useEffect(() => {
    if (!canSpeak) return
    const load = () => setVoices(window.speechSynthesis.getVoices()) // Chrome fills these in async
    load()
    window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', load)
  }, [])

  const voice = voices.find((v) => v.name === voiceName) ?? pickVoice(voices)
  const voiceRef = useRef(voice) // speak() stays stable for the hands-free loop; reads the latest voice
  useEffect(() => {
    voiceRef.current = voice
  }, [voice])

  const setVoiceName = useCallback((name: string) => {
    setVoiceNameState(name)
    try {
      localStorage.setItem(VOICE_KEY, name)
    } catch {
      /* private mode: choice lasts for this page only */
    }
  }, [])

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
          if (rec.current === r) setListening(false)
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
        if (voiceRef.current) u.voice = voiceRef.current
        u.onend = () => resolve()
        u.onerror = () => resolve()
        window.speechSynthesis.cancel()
        window.speechSynthesis.speak(u)
      }),
    [],
  )

  const englishVoices = voices.filter((v) => v.lang.startsWith('en'))
  return { supported, listening, listen, stop, speak, voices: englishVoices, voice, setVoiceName }
}

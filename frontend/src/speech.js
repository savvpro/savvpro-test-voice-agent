/**
 * Browser Web Speech helpers — free, no API keys.
 * SpeechRecognition for STT, speechSynthesis for TTS.
 */

function getRecognitionCtor() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

export function speechSupported() {
  return Boolean(getRecognitionCtor())
}

export function ttsSupported() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

export function speak(text, { rate = 1, pitch = 1 } = {}) {
  if (!ttsSupported() || !text) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.rate = rate
  u.pitch = pitch
  // Prefer a natural English voice when available
  const voices = window.speechSynthesis.getVoices()
  const preferred = voices.find(
    (v) => v.lang.startsWith('en') && /Google|Natural|Samantha|Daniel/i.test(v.name),
  ) || voices.find((v) => v.lang.startsWith('en'))
  if (preferred) u.voice = preferred
  window.speechSynthesis.speak(u)
}

export function stopSpeaking() {
  if (ttsSupported()) window.speechSynthesis.cancel()
}

/**
 * Start one-shot recognition. Returns a controller with stop().
 * onResult(transcript), onError(message), onEnd()
 */
export function startListening({ onResult, onError, onEnd, lang = 'en-US' }) {
  const Ctor = getRecognitionCtor()
  if (!Ctor) {
    onError?.('Speech recognition is not available in this browser. Type instead.')
    return { stop() {} }
  }

  const rec = new Ctor()
  rec.lang = lang
  rec.interimResults = true
  rec.continuous = false
  rec.maxAlternatives = 1

  let finalText = ''

  rec.onresult = (event) => {
    let interim = ''
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const piece = event.results[i][0].transcript
      if (event.results[i].isFinal) finalText += piece
      else interim += piece
    }
    onResult?.(finalText || interim, Boolean(finalText))
  }

  rec.onerror = (event) => {
    if (event.error === 'aborted' || event.error === 'no-speech') {
      onEnd?.()
      return
    }
    onError?.(event.error || 'recognition error')
  }

  rec.onend = () => {
    if (finalText.trim()) onResult?.(finalText.trim(), true)
    onEnd?.()
  }

  try {
    rec.start()
  } catch (err) {
    onError?.(String(err))
  }

  return {
    stop() {
      try {
        rec.stop()
      } catch {
        /* already stopped */
      }
    },
  }
}

import { api } from './types'

export type VoiceStatus = 'idle' | 'listening' | 'processing' | 'speaking' | 'paused'
export type SpeechMode = 'browser' | 'server'
type RecognitionEvent = {
  resultIndex: number
  results: {
    length: number
    [index: number]: { isFinal: boolean; [index: number]: { transcript: string } }
  }
}
type Recognition = {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: RecognitionEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void
  abort(): void
}
declare global {
  interface Window {
    SpeechRecognition?: new () => Recognition
    webkitSpeechRecognition?: new () => Recognition
  }
}
type Callbacks = {
  status(value: VoiceStatus): void
  interim(value: string): void
  text(value: string): void
  error(value: string): void
}

export function chunkReply(text: string): string[] {
  const chunks: string[] = []
  let pending: string[] = []
  for (const sentence of text
    .trim()
    .split(/(?<=[.!?])\s+/)
    .filter(Boolean)) {
    const words = sentence.split(/\s+/)
    if (pending.length && pending.length + words.length > 18) {
      chunks.push(pending.join(' '))
      pending = []
    }
    while (words.length > 18) {
      let boundary = 18
      for (let index = 17; index >= 7; index--) {
        if (/[,;:]$/.test(words[index])) {
          boundary = index + 1
          break
        }
      }
      chunks.push(words.splice(0, boundary).join(' '))
    }
    pending.push(...words)
  }
  if (pending.length) chunks.push(pending.join(' '))
  return chunks
}

export function englishVoices(): SpeechSynthesisVoice[] {
  const score = (voice: SpeechSynthesisVoice) => {
    const name = voice.name.toLowerCase()
    return (
      (/natural|neural|premium|enhanced/.test(name)
        ? 100
        : /google/.test(name)
          ? 80
          : /online/.test(name)
            ? 70
            : 0) + (voice.lang === 'en-US' || voice.lang === 'en-GB' ? 5 : 0)
    )
  }
  return (window.speechSynthesis?.getVoices() ?? [])
    .filter((voice) => voice.lang.toLowerCase().startsWith('en'))
    .sort((a, b) => score(b) - score(a) || a.name.localeCompare(b.name))
}

export function watchdogMs(text: string): number {
  return Math.min(12000, Math.max(3500, (text.trim().split(/\s+/).length / 2.2 + 2.5) * 1000))
}

export function browserSpeechAvailable(): boolean {
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
}

export class VoiceController {
  active = false
  mode: SpeechMode = 'browser'
  voiceURI = ''
  private generation = 0
  private recognition: Recognition | null = null
  private recorder: MediaRecorder | null = null
  private stream: MediaStream | null = null
  private audioContext: AudioContext | null = null
  private timer: number | undefined
  private meter: number | undefined
  private upload: AbortController | null = null
  private utterance: SpeechSynthesisUtterance | null = null
  private callbacks: Callbacks

  constructor(callbacks: Callbacks) {
    this.callbacks = callbacks
  }

  private clear(): number {
    const generation = ++this.generation
    clearTimeout(this.timer)
    clearInterval(this.meter)
    if (this.utterance) {
      this.utterance.onstart = null
      this.utterance.onend = null
      this.utterance.onerror = null
      this.utterance = null
    }
    this.upload?.abort()
    this.upload = null
    if (this.recognition) {
      this.recognition.onend = null
      this.recognition.onerror = null
      this.recognition.onresult = null
      this.recognition.abort()
      this.recognition = null
    }
    if (this.recorder) {
      this.recorder.onstop = null
      this.recorder.onerror = null
      this.recorder.ondataavailable = null
      if (this.recorder.state !== 'inactive') this.recorder.stop()
      this.recorder = null
    }
    this.stream?.getTracks().forEach((track) => track.stop())
    this.stream = null
    if (this.audioContext?.state !== 'closed') void this.audioContext?.close()
    this.audioContext = null
    window.speechSynthesis?.cancel()
    this.callbacks.interim('')
    return generation
  }

  start(reply: string): void {
    this.active = true
    this.speak(reply)
  }

  pause(): void {
    this.active = false
    this.clear()
    this.callbacks.status('paused')
  }

  resume(): void {
    this.active = true
    this.listen()
  }

  end(): void {
    this.active = false
    this.clear()
    this.callbacks.status('idle')
  }

  setMode(mode: SpeechMode): void {
    const wasActive = this.active
    this.clear()
    this.mode = mode
    if (wasActive) this.listen()
  }

  interrupt(): void {
    if (this.active) this.listen()
    else {
      this.clear()
      this.callbacks.status('idle')
    }
  }

  processing(): number {
    const generation = this.clear()
    this.callbacks.status('processing')
    return generation
  }

  stopRecording(): void {
    if (this.recorder?.state === 'recording') this.recorder.stop()
  }

  speak(reply: string, listenAfter = true, expectedGeneration?: number): void {
    if (expectedGeneration !== undefined && expectedGeneration !== this.generation) return
    if (!listenAfter) this.active = false
    const generation = this.clear()
    const chunks = chunkReply(reply)
    if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === 'undefined') {
      this.fail('Speech playback is unavailable. You can read the reply and use typed input.')
      return
    }
    this.callbacks.status('speaking')
    const next = () => {
      if (generation !== this.generation) return
      const chunk = chunks.shift()
      if (!chunk) {
        if (this.active && listenAfter) this.listen()
        else this.callbacks.status(this.active ? 'paused' : 'idle')
        return
      }
      const utterance = new SpeechSynthesisUtterance(chunk)
      // Keep the current utterance alive until completion or explicit cancellation.
      this.utterance = utterance
      utterance.lang = 'en-US'
      utterance.rate = 1
      const voices = englishVoices()
      utterance.voice =
        voices.find((voice) => voice.voiceURI === this.voiceURI) ?? voices[0] ?? null
      if (utterance.voice) utterance.lang = utterance.voice.lang
      let finished = false
      let started = false
      utterance.onstart = () => {
        started = true
      }
      const finish = (timedOut = false) => {
        if (finished || generation !== this.generation) return
        finished = true
        clearTimeout(this.timer)
        utterance.onend = null
        utterance.onerror = null
        utterance.onstart = null
        this.utterance = null
        if (timedOut && !started) {
          this.fail(
            'Speech playback did not start. Click Replay last reply to try again, or continue with text.',
          )
          return
        }
        if (timedOut) window.speechSynthesis.cancel()
        this.timer = window.setTimeout(next, 0)
      }
      utterance.onend = () => finish()
      utterance.onerror = (event) => {
        if (finished || generation !== this.generation) return
        finished = true
        this.fail(
          event.error === 'not-allowed'
            ? 'Your browser blocked speech playback. Click Replay last reply to try again, or continue with text.'
            : 'Speech playback failed. Click Replay last reply to try again, or continue with text.',
        )
      }
      this.timer = window.setTimeout(() => finish(true), watchdogMs(chunk))
      // Flush before every chunk; stale callbacks are detached and generation-guarded.
      window.speechSynthesis.cancel()
      try {
        if (window.speechSynthesis.paused) window.speechSynthesis.resume()
        window.speechSynthesis.speak(utterance)
      } catch {
        this.fail(
          'Speech playback failed. Click Replay last reply to try again, or continue with text.',
        )
      }
    }
    next()
  }

  private fail(message: string): void {
    this.pause()
    this.callbacks.error(message)
  }

  private listen(): void {
    if (!this.active) return
    const generation = this.clear()
    this.callbacks.status('listening')
    if (this.mode === 'server') {
      void this.record(generation)
      return
    }
    const Constructor = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!Constructor) {
      this.fail(
        'Browser recognition is unavailable. Choose server speech if configured, or use typed input. Desktop Chrome is recommended.',
      )
      return
    }
    const recognition = new Constructor()
    this.recognition = recognition
    recognition.lang = 'en-US'
    recognition.continuous = false
    recognition.interimResults = true
    let delivered = false
    recognition.onresult = (event) => {
      if (generation !== this.generation || delivered) return
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) final += event.results[i][0].transcript + ' '
        else interim += event.results[i][0].transcript
      }
      this.callbacks.interim(interim)
      if (final.trim()) {
        delivered = true
        this.processing()
        this.callbacks.text(final.trim())
      }
    }
    recognition.onerror = (event) => {
      if (generation !== this.generation || delivered || event.error === 'aborted') return
      const messages: Record<string, string> = {
        'not-allowed':
          'Microphone permission was denied. Allow microphone access in your browser, then resume the call.',
        'audio-capture': 'No microphone was found. Connect a microphone or use typed input.',
        'no-speech': 'I did not hear speech. Resume when ready, or type your message.',
        network:
          'Browser speech could not reach its recognition service. Try server speech or typed input.',
        'service-not-allowed':
          'This browser does not allow speech recognition. Try desktop Chrome or server speech.',
      }
      this.fail(
        messages[event.error] ?? 'Speech recognition stopped. Resume the call or use typed input.',
      )
    }
    recognition.onend = () => {
      if (generation === this.generation && !delivered)
        this.fail('Listening ended without a complete utterance. Resume the call to try again.')
    }
    this.timer = window.setTimeout(() => {
      if (generation === this.generation)
        this.fail('Listening paused after 30 seconds. Resume when you are ready.')
    }, 30000)
    try {
      recognition.start()
    } catch {
      this.fail(
        'Microphone could not start. Close other microphone apps and resume, or type your message.',
      )
    }
  }

  private async record(generation: number): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      this.fail(
        'Audio recording requires a supported browser and HTTPS or localhost. Typed input is available.',
      )
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      })
      if (generation !== this.generation) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      this.stream = stream
      const mime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'].find((type) =>
        MediaRecorder.isTypeSupported(type),
      )
      if (!mime) {
        this.fail(
          'This browser has no supported recording format. Use browser speech or typed input.',
        )
        return
      }
      const recorder = new MediaRecorder(stream, { mimeType: mime })
      this.recorder = recorder
      const chunks: Blob[] = []
      const context = new AudioContext()
      this.audioContext = context
      await context.resume()
      if (generation !== this.generation) {
        if (context.state !== 'closed') await context.close()
        return
      }
      const analyser = context.createAnalyser()
      analyser.fftSize = 1024
      context.createMediaStreamSource(stream).connect(analyser)
      const samples = new Uint8Array(analyser.fftSize)
      let heard = false
      let lastSound = performance.now()
      const started = lastSound
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data)
      }
      recorder.onerror = () => {
        if (generation === this.generation)
          this.fail('The recording failed. Try again or type your message.')
      }
      recorder.onstop = async () => {
        clearInterval(this.meter)
        clearTimeout(this.timer)
        stream.getTracks().forEach((track) => track.stop())
        if (context.state !== 'closed') await context.close()
        if (generation !== this.generation) return
        if (!heard || !chunks.length) {
          this.fail('No speech was detected. Resume and speak closer to the microphone.')
          return
        }
        this.callbacks.status('processing')
        const data = new FormData()
        data.append(
          'audio',
          new Blob(chunks, { type: mime.split(';')[0] }),
          'turn.' + (mime.includes('mp4') ? 'mp4' : mime.includes('ogg') ? 'ogg' : 'webm'),
        )
        this.upload = new AbortController()
        try {
          const result = await api<{ text: string }>('/api/stt', data, this.upload.signal)
          if (generation !== this.generation) return
          this.callbacks.text(result.text)
        } catch (error) {
          if (generation === this.generation)
            this.fail(
              error instanceof Error ? error.message : 'Transcription failed. Please try typing.',
            )
        }
      }
      recorder.start(250)
      this.meter = window.setInterval(() => {
        if (generation !== this.generation || recorder.state !== 'recording') return
        analyser.getByteTimeDomainData(samples)
        const rms = Math.sqrt(
          samples.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / samples.length,
        )
        const stamp = performance.now()
        if (rms > 0.018) {
          heard = true
          lastSound = stamp
        }
        if (
          (heard && stamp - lastSound > 1400 && stamp - started > 900) ||
          (!heard && stamp - started > 8000)
        )
          recorder.stop()
      }, 100)
      this.timer = window.setTimeout(() => {
        if (generation === this.generation && recorder.state === 'recording') recorder.stop()
      }, 20000)
    } catch {
      if (generation === this.generation)
        this.fail(
          'Microphone access failed. Allow microphone permission, then resume, or use typed input.',
        )
    }
  }
}

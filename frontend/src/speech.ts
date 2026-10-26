type RecognitionEvent = Event & { results: ArrayLike<{ 0: { transcript: string } }> };
type RecognitionErrorEvent = Event & { error: string };
type Recognition = {
  continuous: boolean; interimResults: boolean; lang: string;
  start(): void; stop(): void;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
};
type RecognitionConstructor = new () => Recognition;

declare global {
  interface Window { webkitSpeechRecognition?: RecognitionConstructor; SpeechRecognition?: RecognitionConstructor; }
}

export class BrowserSpeech {
  private recognition: Recognition | null = null;
  private timer: number | null = null;

  supported(): boolean { return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition); }

  listen(onText: (text: string) => void, onError: (reason: string) => void, onEnd: () => void): void {
    this.stopSpeaking();
    const Constructor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Constructor) { onError("Speech recognition is unavailable. Use text input."); return; }
    this.recognition = new Constructor();
    this.recognition.continuous = false;
    this.recognition.interimResults = false;
    this.recognition.lang = "en-US";
    this.recognition.onresult = (event) => onText(event.results[0][0].transcript);
    this.recognition.onerror = (event) => onError(`Microphone error: ${event.error}. Use text input.`);
    this.recognition.onend = () => { this.clearTimer(); this.recognition = null; onEnd(); };
    this.recognition.start();
    this.timer = window.setTimeout(() => this.stopListening(), 10_000);
  }

  stopListening(): void { this.recognition?.stop(); this.clearTimer(); }
  speak(text: string, onEnd: () => void): void {
    this.stopListening(); this.stopSpeaking();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onend = onEnd; utterance.onerror = onEnd;
    window.speechSynthesis.speak(utterance);
  }
  stopSpeaking(): void { window.speechSynthesis?.cancel(); }
  private clearTimer(): void { if (this.timer !== null) window.clearTimeout(this.timer); this.timer = null; }
}


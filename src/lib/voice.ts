/**
 * Web Speech API wrappers — speech recognition (STT) and speech synthesis (TTS).
 *
 * Browser-native APIs only. No external STT/TTS service, no API keys.
 *
 * TypeScript doesn't ship types for the prefixed `webkitSpeechRecognition`
 * API, so we declare just enough surface area here to keep the compiler happy.
 */

// ---- Minimal type declarations for the Web Speech API ----
type SpeechRecognitionResultLike = {
  0: { transcript: string; confidence: number };
  isFinal: boolean;
  length: number;
};
type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: { length: number; [i: number]: SpeechRecognitionResultLike };
};
type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
};
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

export function isSttSupported(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function isTtsSupported(): boolean {
  if (typeof window === "undefined") return false;
  return typeof window.speechSynthesis !== "undefined";
}

export function getSttErrorMessage(error: string): string {
  switch (error) {
    case "no-speech":
      return "I didn't hear anything. Try again?";
    case "audio-capture":
      return "I can't access your microphone. Check browser permissions.";
    case "not-allowed":
      return "Microphone permission was denied. Please allow it and try again.";
    case "network":
      return "Network error during speech recognition.";
    case "aborted":
      return "Listening was cancelled.";
    default:
      return `Speech recognition error: ${error}`;
  }
}

/**
 * Recognize a single utterance. Resolves with the transcribed text.
 *
 * We use continuous=false, interimResults=true so the UI can show partial
 * transcriptions as the user speaks. The promise resolves on the first
 * final result OR on `onend` (if no final result was received).
 */
export function recognizeOnce(
  onInterim?: (text: string) => void,
): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!isSttSupported()) {
      reject(new Error("Speech recognition is not supported in this browser."));
      return;
    }
    const Ctor = (window.SpeechRecognition ||
      window.webkitSpeechRecognition) as SpeechRecognitionCtor;
    const rec = new Ctor();
    rec.lang = "en-US";
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    let finalText = "";
    let ended = false;

    rec.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) {
          finalText += r[0].transcript;
        } else {
          interim += r[0].transcript;
        }
      }
      if (interim && onInterim) onInterim(interim);
      if (finalText) {
        ended = true;
        rec.stop();
        resolve(finalText.trim());
      }
    };
    rec.onerror = (e) => {
      reject(new Error(getSttErrorMessage(e.error)));
    };
    rec.onend = () => {
      if (!ended) {
        // No final result; resolve with whatever interim text we have, or empty.
        resolve(finalText.trim());
      }
    };
    rec.start();
  });
}

/**
 * Speak the given text using browser speech synthesis. Resolves when done.
 */
export function speak(
  text: string,
  opts?: { onBoundary?: (charIndex: number) => void; rate?: number },
): Promise<void> {
  return new Promise((resolve) => {
    if (!isTtsSupported() || !text.trim()) {
      resolve();
      return;
    }
    window.speechSynthesis.cancel();  // stop anything currently speaking
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    u.rate = opts?.rate ?? 1.0;
    u.pitch = 1.0;
    if (opts?.onBoundary) {
      u.onboundary = (e) => opts.onBoundary!(e.charIndex);
    }
    u.onend = () => resolve();
    u.onerror = () => resolve();
    window.speechSynthesis.speak(u);
  });
}

export function stopSpeaking() {
  if (isTtsSupported()) {
    window.speechSynthesis.cancel();
  }
}

import { useCallback, useEffect, useRef, useState } from 'react';

const Recognition =
  typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null;

/**
 * Browser speech: speech-to-text via the Web Speech API (Chrome / Edge) and
 * text-to-speech via speechSynthesis. No API keys are needed.
 */
export function useSpeech({ onResult, onError }) {
  const [listening, setListening] = useState(false);
  const recRef = useRef(null);
  const handlers = useRef({ onResult, onError });
  handlers.current = { onResult, onError };

  const start = useCallback(() => {
    if (!Recognition) return;
    window.speechSynthesis?.cancel();           // never listen to ourselves
    const rec = new Recognition();
    rec.lang = 'en-US';
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e) => handlers.current.onResult(e.results[0][0].transcript);
    rec.onerror = (e) => handlers.current.onError?.(e.error);
    rec.onend = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    try {
      rec.start();
    } catch {
      setListening(false);
    }
  }, []);

  const stop = useCallback(() => recRef.current?.stop(), []);

  const speak = useCallback((text, onEnd) => {
    const synth = window.speechSynthesis;
    if (!synth) {
      onEnd?.();
      return;
    }
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.onend = () => onEnd?.();
    utterance.onerror = () => onEnd?.();
    synth.speak(utterance);
  }, []);

  useEffect(() => () => {
    recRef.current?.abort?.();
    window.speechSynthesis?.cancel();
  }, []);

  return { supported: Boolean(Recognition), listening, start, stop, speak };
}

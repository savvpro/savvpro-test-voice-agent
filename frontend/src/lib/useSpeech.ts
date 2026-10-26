"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// The Web Speech API is not in TypeScript's DOM types yet; this is the part we use.
type RecognitionResult = { isFinal: boolean; 0: { transcript: string } };
type RecognitionEvent = { resultIndex: number; results: ArrayLike<RecognitionResult> };
type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};
type RecognitionCtor = new () => Recognition;

function getRecognition(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** Browser speech to text and text to speech, with no keys or servers. */
export function useSpeech(onFinal: (text: string) => void) {
  const [canListen, setCanListen] = useState(false);
  const [canSpeak, setCanSpeak] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<Recognition | null>(null);
  const finalRef = useRef(onFinal);
  finalRef.current = onFinal;

  useEffect(() => {
    setCanListen(Boolean(getRecognition()));
    setCanSpeak(typeof window !== "undefined" && "speechSynthesis" in window);
    return () => {
      recRef.current?.abort();
      if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, []);

  const listen = useCallback(() => {
    const Ctor = getRecognition();
    if (!Ctor) return;
    recRef.current?.abort();
    const rec = new Ctor();
    rec.lang = "en-US";
    rec.continuous = false;
    rec.interimResults = true;
    let finalText = "";
    rec.onresult = (e) => {
      let live = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else live += r[0].transcript;
      }
      setInterim(finalText + live);
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        setError("Microphone access was blocked. Allow it in the browser, or type instead.");
      } else if (e.error !== "no-speech" && e.error !== "aborted") {
        setError(`Speech recognition error: ${e.error}. You can type instead.`);
      }
    };
    rec.onend = () => {
      setListening(false);
      setInterim("");
      recRef.current = null;
      // An empty turn still counts: the brain answers silence too.
      finalRef.current(finalText.trim());
    };
    recRef.current = rec;
    setError(null);
    setListening(true);
    try {
      rec.start();
    } catch {
      setListening(false);
    }
  }, []);

  const stopListening = useCallback(() => recRef.current?.stop(), []);

  const cancelListening = useCallback(() => {
    const rec = recRef.current;
    if (!rec) return;
    rec.onend = null;
    rec.abort();
    recRef.current = null;
    setListening(false);
    setInterim("");
  }, []);

  const speak = useCallback((text: string, done?: () => void) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      done?.();
      return;
    }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    u.rate = 1.03;
    const voice = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("en") && /female|samantha|aria|jenny|google us/i.test(v.name));
    if (voice) u.voice = voice;
    u.onstart = () => setSpeaking(true);
    u.onend = () => {
      setSpeaking(false);
      done?.();
    };
    u.onerror = () => {
      setSpeaking(false);
      done?.();
    };
    window.speechSynthesis.speak(u);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  return { canListen, canSpeak, listening, speaking, interim, error, listen, stopListening, cancelListening, speak, stopSpeaking };
}

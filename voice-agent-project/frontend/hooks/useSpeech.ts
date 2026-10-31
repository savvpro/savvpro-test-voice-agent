"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface Handlers {
  onFinal: (text: string, confidence: number) => void;
  onSilence: () => void;
}

// The Web Speech API is not in TypeScript's DOM lib everywhere, so keep the typing loose.
/* eslint-disable @typescript-eslint/no-explicit-any */
type Recognition = any;

export function useSpeech(handlers: Handlers, lang: string, silenceMs = 12000) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;
  const recRef = useRef<Recognition | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speakIdRef = useRef(0);
  const [listening, setListening] = useState(false);
  const [support, setSupport] = useState({ stt: false, tts: false });

  useEffect(() => {
    const w = window as any;
    setSupport({
      stt: Boolean(w.SpeechRecognition || w.webkitSpeechRecognition),
      tts: "speechSynthesis" in window,
    });
  }, []);

  const clearTimer = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
  };

  const stopListening = useCallback(() => {
    clearTimer();
    const rec = recRef.current;
    recRef.current = null; // detach first so the abort below is ignored by the handlers
    rec?.abort?.();
    setListening(false);
  }, []);

  const startListening = useCallback(() => {
    const w = window as any;
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) return false;
    stopListening();
    const rec: Recognition = new Ctor();
    rec.lang = lang;
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.continuous = false;
    let settled = false;
    const settle = (fn: () => void) => {
      if (settled || recRef.current !== rec) return;
      settled = true;
      clearTimer();
      recRef.current = null;
      setListening(false);
      fn();
    };
    rec.onresult = (e: any) => {
      const alt = e.results[0][0];
      // Chrome reports 0 when it gives no confidence score, so treat 0 as "unknown"
      const confidence = typeof alt.confidence === "number" && alt.confidence > 0 ? alt.confidence : 1;
      settle(() => handlersRef.current.onFinal(alt.transcript, confidence));
    };
    rec.onerror = (e: any) => {
      if (e.error === "no-speech") settle(() => handlersRef.current.onSilence());
      else if (e.error !== "aborted") settle(() => handlersRef.current.onSilence());
    };
    rec.onend = () => settle(() => handlersRef.current.onSilence());
    recRef.current = rec;
    rec.start();
    setListening(true);
    timerRef.current = setTimeout(() => {
      settle(() => handlersRef.current.onSilence());
      rec.abort?.();
    }, silenceMs);
    return true;
  }, [lang, silenceMs, stopListening]);

  const speak = useCallback((text: string, onEnd?: () => void) => {
    if (!("speechSynthesis" in window)) {
      onEnd?.();
      return;
    }
    const myId = ++speakIdRef.current; // callbacks from an older, cancelled utterance must do nothing
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    // Chrome sometimes fires "end" early on long sentences, so wait until it has really stopped,
    // then pause briefly so the microphone does not hear the tail of the assistant's voice.
    const finish = () => {
      if (myId !== speakIdRef.current) return;
      const synth = window.speechSynthesis;
      if (synth.speaking || synth.pending) {
        setTimeout(finish, 200);
      } else {
        setTimeout(() => onEnd?.(), 400);
      }
    };
    utterance.onend = finish;
    utterance.onerror = finish;
    window.speechSynthesis.speak(utterance);
  }, []);

  const stopSpeaking = useCallback(() => {
    speakIdRef.current += 1;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  useEffect(() => {
    return () => {
      stopListening();
      stopSpeaking();
    };
  }, [stopListening, stopSpeaking]);

  return { listening, support, startListening, stopListening, speak, stopSpeaking };
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type RecognitionResultEvent = {
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
};
type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  abort(): void;
  stop(): void;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};

export function useVoice(onFinal: (text: string) => void, language = "en-US") {
  const [supported, setSupported] = useState(false);
  const [canSpeak, setCanSpeak] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState("");
  const recognition = useRef<Recognition | null>(null);
  const finalCallback = useRef(onFinal);
  const active = useRef(false);
  const spoken = useRef<SpeechSynthesisUtterance | null>(null);
  finalCallback.current = onFinal;

  useEffect(() => {
    const browser = window as SpeechWindow;
    setSupported(
      Boolean(browser.SpeechRecognition || browser.webkitSpeechRecognition),
    );
    setCanSpeak("speechSynthesis" in window);
    return () => {
      active.current = false;
      recognition.current?.abort();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, []);

  const stopSpeaking = useCallback(() => {
    if (spoken.current) {
      spoken.current.onend = null;
      spoken.current.onerror = null;
    }
    spoken.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  const stopListening = useCallback(() => {
    active.current = false;
    recognition.current?.abort();
    recognition.current = null;
    setListening(false);
    setInterim("");
  }, []);

  const speak = useCallback(
    (text: string) => {
      // Abort recognition first so synthesized replies never become user turns.
      stopListening();
      stopSpeaking();
      if (!("speechSynthesis" in window)) {
        setError(
          "Spoken replies are unavailable in this browser. All replies are shown in the conversation.",
        );
        return;
      }
      setError("");
      try {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = language;
        utterance.rate = 0.98;
        spoken.current = utterance;
        setSpeaking(true);
        utterance.onend = () => {
          if (spoken.current === utterance) {
            setSpeaking(false);
            spoken.current = null;
          }
        };
        utterance.onerror = (event) => {
          if (spoken.current !== utterance) return;
          setSpeaking(false);
          spoken.current = null;
          if (event.error !== "canceled" && event.error !== "interrupted")
            setError(
              "Your browser could not speak this reply. You can read it in the conversation or try Listen again.",
            );
        };
        window.speechSynthesis.speak(utterance);
      } catch {
        spoken.current = null;
        setSpeaking(false);
        setError(
          "Your browser could not speak this reply. Read it in the conversation or choose Listen again.",
        );
      }
    },
    [language, stopListening, stopSpeaking],
  );

  const startListening = useCallback(() => {
    if (active.current || window.speechSynthesis?.speaking) return;
    const browser = window as SpeechWindow;
    const Constructor =
      browser.SpeechRecognition || browser.webkitSpeechRecognition;
    if (!Constructor) {
      setError(
        "Speech recognition is unavailable. Use the message field below; typed input supports every workflow.",
      );
      return;
    }
    setError("");
    setInterim("");
    const instance = new Constructor();
    instance.lang = language;
    instance.continuous = false;
    instance.interimResults = true;
    recognition.current = instance;
    instance.onresult = (event) => {
      if (!active.current || recognition.current !== instance) return;
      let preview = "";
      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          const transcript = result[0].transcript.trim();
          stopListening();
          if (transcript) finalCallback.current(transcript);
          return;
        }
        preview += result[0].transcript;
      }
      setInterim(preview);
    };
    instance.onerror = (event) => {
      if (recognition.current !== instance) return;
      const messages: Record<string, string> = {
        "not-allowed":
          "Microphone permission was denied. Allow it in your browser settings, or type your message.",
        "service-not-allowed":
          "Your browser blocked speech recognition. Try Chrome or Edge, or type your message.",
        "audio-capture":
          "No microphone was found. Connect a microphone, or type your message.",
        "no-speech":
          "No speech was detected. Tap the microphone to try again, or type below.",
        network:
          "The browser's speech service could not connect. Check your connection, or use typed input.",
      };
      if (event.error !== "aborted")
        setError(
          messages[event.error] ||
            "Speech recognition stopped. Please try again or type your message.",
        );
      stopListening();
    };
    instance.onend = () => {
      if (recognition.current === instance) {
        active.current = false;
        setListening(false);
        setInterim("");
      }
    };
    try {
      active.current = true;
      setListening(true);
      instance.start();
    } catch {
      stopListening();
      setError(
        "Could not start the microphone. Check its permissions or type your message.",
      );
    }
  }, [language, stopListening]);

  return {
    supported,
    canSpeak,
    listening,
    speaking,
    interim,
    error,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
  };
}

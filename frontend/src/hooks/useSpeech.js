"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

function getSpeechRecognition() {
  if (typeof window === "undefined") return null;
  return (
    window.SpeechRecognition ||
    window.webkitSpeechRecognition ||
    null
  );
}

const emptySubscribe = () => () => {};

export function useSpeech({
  onTranscript,
  enabled = true,
  silenceDelay = 2000,
}) {
  const recognitionRef = useRef(null);
  const onTranscriptRef = useRef(onTranscript);
  const silenceTimerRef = useRef(null);
  const transcriptRef = useRef("");
  const isListeningRef = useRef(false);

  const [listening, setListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [ttsEnabled, setTtsEnabled] = useState(true);

  const speechSupported = useSyncExternalStore(
    emptySubscribe,
    () => Boolean(getSpeechRecognition()),
    () => false,
  );

  // Always keep onTranscript ref up to date
  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  const commitAndStop = useCallback(() => {
    clearSilenceTimer();
    const finalUtterance = transcriptRef.current.trim();
    transcriptRef.current = "";
    setInterimTranscript("");
    setIsSpeaking(false);
    isListeningRef.current = false;

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore already stopped error
      }
    }
    setListening(false);

    if (finalUtterance) {
      onTranscriptRef.current?.(finalUtterance);
    }
  }, []);

  // Pre-load and track available TTS voices
  const voicesRef = useRef([]);
  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const loadVoices = () => {
      voicesRef.current = window.speechSynthesis.getVoices() || [];
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }, []);

  const currentAudioRef = useRef(null);

  const fallbackWebSpeech = useCallback((cleanedText) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const synth = window.speechSynthesis;
    try {
      synth.cancel();
      if (synth.paused) synth.resume();

      const utterance = new SpeechSynthesisUtterance(cleanedText);
      utterance.lang = "en-US";
      utterance.volume = 1.0;
      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      const voices = synth.getVoices() || [];
      const localVoice = voices.find(
        (v) => (v.lang === "en-US" || v.lang.startsWith("en")) && v.localService,
      );
      if (localVoice) utterance.voice = localVoice;

      window.__activeUtterance = utterance;
      utterance.onend = () => { window.__activeUtterance = null; };
      utterance.onerror = () => { window.__activeUtterance = null; };

      setTimeout(() => {
        try {
          if (synth.paused) synth.resume();
          synth.speak(utterance);
        } catch {
          // ignore
        }
      }, 50);
    } catch {
      // ignore
    }
  }, []);

  const speak = useCallback(
    (text) => {
      if (!ttsEnabled || typeof window === "undefined" || !text) {
        return;
      }

      // Stop any existing playback
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      }
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }

      const cleanedText = text
        .replace(/[*_#]/g, "")
        .replace(/\n+/g, ". ")
        .trim();

      if (!cleanedText) return;

      // 1. Play high-quality native audio from backend /api/tts
      const encoded = encodeURIComponent(cleanedText);
      const audio = new Audio(`/api/tts?text=${encoded}`);
      currentAudioRef.current = audio;

      audio.onplay = () => {
        console.log("[Audio] Playing backend speech:", cleanedText);
      };

      audio.onended = () => {
        if (currentAudioRef.current === audio) {
          currentAudioRef.current = null;
        }
      };

      audio.onerror = () => {
        console.warn("[Audio] Backend TTS failed, using browser Web Speech API fallback");
        currentAudioRef.current = null;
        fallbackWebSpeech(cleanedText);
      };

      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn("[Audio] Autoplay blocked, falling back to Web Speech:", err);
          fallbackWebSpeech(cleanedText);
        });
      }
    },
    [ttsEnabled, fallbackWebSpeech],
  );

  const stopListening = useCallback(() => {
    commitAndStop();
  }, [commitAndStop]);

  const startListening = useCallback(() => {
    const SpeechRecognition = getSpeechRecognition();
    if (!SpeechRecognition || !enabled) return;

    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    window.speechSynthesis?.cancel();
    clearSilenceTimer();
    transcriptRef.current = "";
    setInterimTranscript("");
    setIsSpeaking(false);

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      isListeningRef.current = true;
      setListening(true);
    };

    recognition.onaudiostart = () => {
      setIsSpeaking(true);
    };

    recognition.onspeechstart = () => {
      setIsSpeaking(true);
    };

    recognition.onspeechend = () => {
      setIsSpeaking(false);
    };

    recognition.onresult = (event) => {
      let accumulated = "";
      for (let i = 0; i < event.results.length; i++) {
        accumulated += event.results[i][0].transcript + " ";
      }
      const trimmed = accumulated.trim();
      transcriptRef.current = trimmed;
      setInterimTranscript(trimmed);
      setIsSpeaking(true);

      // Reset silence timer on every new speech event: wait for user to finish talking
      clearSilenceTimer();
      silenceTimerRef.current = setTimeout(() => {
        // User has stopped talking for `silenceDelay` ms
        commitAndStop();
      }, silenceDelay);
    };

    recognition.onerror = (event) => {
      // Don't treat "no-speech" as fatal if still waiting for input
      if (event.error === "no-speech") {
        return;
      }
      clearSilenceTimer();
      setListening(false);
      setIsSpeaking(false);
      isListeningRef.current = false;
    };

    recognition.onend = () => {
      // If recognition ended prematurely by browser while we're still waiting for speech
      if (isListeningRef.current) {
        if (transcriptRef.current.trim()) {
          commitAndStop();
        } else {
          // Restart recognition if user hasn't said anything yet
          try {
            recognition.start();
          } catch {
            setListening(false);
            isListeningRef.current = false;
          }
        }
      } else {
        setListening(false);
        setIsSpeaking(false);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      // Handle already active recognition
    }
  }, [enabled, silenceDelay, commitAndStop]);

  useEffect(() => {
    return () => {
      clearSilenceTimer();
      recognitionRef.current?.stop();
      window.speechSynthesis?.cancel();
    };
  }, []);

  return {
    listening,
    isSpeaking,
    interimTranscript,
    speechSupported,
    ttsEnabled,
    setTtsEnabled,
    speak,
    startListening,
    stopListening,
  };
}

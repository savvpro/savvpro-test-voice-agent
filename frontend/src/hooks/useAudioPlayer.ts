import { useCallback, useEffect, useRef } from "react";

/** Plays the agent's reply: server audio when there is some, browser speech otherwise. */
export function useAudioPlayer() {
  const current = useRef<HTMLAudioElement | null>(null);

  const stop = useCallback(() => {
    current.current?.pause();
    current.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }, []);

  const speak = useCallback((text: string) => {
    if (!("speechSynthesis" in window) || !text) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  }, []);

  const play = useCallback(
    (text: string, audioBase64: string | null, mime: string | null) => {
      stop();
      if (!audioBase64) {
        speak(text);
        return;
      }
      const audio = new Audio(`data:${mime ?? "audio/wav"};base64,${audioBase64}`);
      current.current = audio;
      // Autoplay can be blocked; the browser voice is better than silence.
      audio.play().catch(() => speak(text));
    },
    [speak, stop],
  );

  useEffect(() => stop, [stop]);

  return { play, stop };
}

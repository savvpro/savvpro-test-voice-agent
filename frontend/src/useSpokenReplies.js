import { useCallback, useEffect, useRef, useState } from 'react';

export function useSpokenReplies(messages, { paused = false } = {}) {
  const synthesis = globalThis.speechSynthesis;
  const Utterance = globalThis.SpeechSynthesisUtterance;
  const supported = Boolean(synthesis && typeof synthesis.speak === 'function' &&
    typeof synthesis.cancel === 'function' && typeof Utterance === 'function');
  const [enabled, setEnabled] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState(null);
  // Seed with restored history: enabling voice never replays old replies.
  const seen = useRef(new Set(messages.filter((message) => message.role === 'assistant').map((message) => message.id)));
  const active = useRef(null);

  const cancelCurrent = useCallback(() => {
    const utterance = active.current;
    active.current = null;
    if (!utterance) return;
    utterance.onstart = utterance.onend = utterance.onerror = null;
    try { synthesis.cancel(); } catch { /* Text remains available if the browser engine fails. */ }
  }, [synthesis]);

  const stop = useCallback(() => {
    cancelCurrent();
    setSpeaking(false);
  }, [cancelCurrent]);

  useEffect(() => () => cancelCurrent(), [cancelCurrent]);

  useEffect(() => {
    const fresh = messages.filter((message) => message.role === 'assistant' && !seen.current.has(message.id));
    for (const message of fresh) seen.current.add(message.id);
    if (!supported || !enabled || paused || !fresh.length) return;
    stop();
    setError(null);
    // Only the newest reply is useful if several arrive in one render.
    const message = fresh[fresh.length - 1];
    try {
      const text = message.text.replace(/[\p{Extended_Pictographic}\uFE0F]/gu, '').replace(/\s+/g, ' ').trim();
      if (!text) return;
      const utterance = new Utterance(text);
      utterance.lang = 'en-US';
      active.current = utterance;
      setSpeaking(true); // Also covers a queued utterance that has not started.
      utterance.onstart = () => { if (active.current === utterance) setSpeaking(true); };
      utterance.onend = () => {
        if (active.current !== utterance) return;
        active.current = null;
        setSpeaking(false);
      };
      utterance.onerror = (event) => {
        if (active.current !== utterance) return;
        active.current = null;
        setSpeaking(false);
        if (!['canceled', 'interrupted'].includes(event.error)) {
          setError('Spoken playback is unavailable. You can still read the reply or turn spoken replies off.');
        }
      };
      synthesis.speak(utterance);
    } catch {
      cancelCurrent();
      setSpeaking(false);
      setError('Spoken playback could not start. The assistant’s reply is available as text.');
    }
  }, [messages, enabled, paused, supported, synthesis, Utterance, stop, cancelCurrent]);

  function toggle() {
    stop();
    setError(null);
    if (supported) setEnabled((previous) => !previous);
  }

  return { supported, enabled, speaking, error, toggle, stop };
}

import { useCallback, useEffect, useRef, useState } from 'react';

const empty = () => ({ status: 'idle', transcript: '', error: null });
const errors = {
  'not-allowed': 'Microphone access was denied. Allow microphone access in your browser settings, or type your message.',
  'service-not-allowed': 'Your browser blocked speech recognition. You can still type your message.',
  'audio-capture': 'No working microphone was found. Check your microphone, or type your message.',
  'no-speech': 'No clear speech was recognized. Try the microphone again, or type your message.',
  network: 'The browser’s speech service could not connect. Try again when connected, or type your message.',
  'language-not-supported': 'English speech recognition is unavailable in this browser. Please type your message.',
};

export function useSpeechInput({ disabled, onTranscript }) {
  const Recognition = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition;
  const supported = typeof Recognition === 'function';
  const [state, setState] = useState(empty);
  const current = useRef(null);
  const options = useRef({ disabled, onTranscript });
  options.current = { disabled, onTranscript };

  const release = useCallback(() => {
    const active = current.current;
    current.current = null;
    if (!active) return;
    const recognition = active.recognition;
    for (const name of ['onstart', 'onresult', 'onspeechend', 'onaudioend', 'onend', 'onerror', 'onnomatch']) recognition[name] = null;
    try { recognition.abort(); } catch { /* It may already have disconnected. */ }
  }, []);

  const cancel = useCallback(() => {
    release();
    setState(empty());
  }, [release]);

  useEffect(() => {
    if (disabled) cancel();
  }, [disabled, cancel]);
  useEffect(() => () => release(), [release]);

  function start() {
    if (!supported || options.current.disabled || current.current) return false;
    let recognition;
    try { recognition = new Recognition(); } catch {
      setState({ ...empty(), status: 'error', error: 'Speech recognition could not start. Please type your message.' });
      return false;
    }
    const active = { recognition, finalText: '', stopping: false };
    current.current = active;
    const isCurrent = () => current.current === active;
    const fail = (code) => {
      if (!isCurrent()) return;
      release();
      setState(code === 'aborted' ? empty() : {
        ...empty(), status: 'error',
        error: errors[code] || 'Speech recognition was interrupted. Try again, or type your message.',
      });
    };
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      if (isCurrent() && !active.stopping) setState((previous) => ({ ...previous, status: 'listening' }));
    };
    recognition.onresult = (event) => {
      if (!isCurrent()) return;
      // Rebuild the complete result list; repeated final events cannot append
      // the same phrase twice. Only final results enter the editable draft.
      const results = Array.from(event.results || []);
      const text = (result) => result[0]?.transcript?.trim() || '';
      active.finalText = results.filter((result) => result.isFinal).map(text).filter(Boolean).join(' ');
      setState((previous) => ({ ...previous, transcript: results.map(text).filter(Boolean).join(' ') }));
    };
    recognition.onspeechend = () => { if (isCurrent()) stop(); };
    recognition.onaudioend = () => {
      if (isCurrent()) setState((previous) => ({ ...previous, status: 'processing' }));
    };
    recognition.onerror = (event) => fail(event.error);
    recognition.onnomatch = () => fail('no-speech');
    recognition.onend = () => {
      if (!isCurrent()) return;
      const finalText = active.finalText.trim();
      release();
      if (!finalText) {
        setState({ ...empty(), status: 'error', error: errors['no-speech'] });
        return;
      }
      setState({ status: 'ready', transcript: finalText, error: null });
      options.current.onTranscript(finalText);
    };
    setState({ ...empty(), status: 'starting' });
    try { recognition.start(); } catch { fail('start-failed'); return false; }
    return true;
  }

  function stop() {
    const active = current.current;
    if (!active || active.stopping) return;
    active.stopping = true;
    setState((previous) => ({ ...previous, status: 'processing' }));
    try { active.recognition.stop(); } catch {
      release();
      setState({ ...empty(), status: 'error', error: 'Dictation could not finish. Try again, or type your message.' });
    }
  }

  return {
    ...state, supported,
    busy: ['starting', 'listening', 'processing'].includes(state.status),
    isActive: () => current.current !== null,
    start, stop, cancel,
  };
}

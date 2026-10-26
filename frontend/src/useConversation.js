import { useEffect, useRef, useState } from 'react';
import { isConversation, sendConversationMessage, startConversation } from './api.js';

export const STORAGE_KEY = 'golden-fork-conversation-v1';
const emptyState = () => ({ conversation: null, messages: [], pending: null, error: null, busy: false, needsNewSession: false });

function savedState() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY));
    if (!saved || (saved.conversation !== null && !isConversation(saved.conversation))) return emptyState();
    if (!Array.isArray(saved.messages) || !saved.messages.every((item) =>
      typeof item.id === 'string' && ['customer', 'assistant'].includes(item.role) && typeof item.text === 'string')) return emptyState();
    const pending = saved.pending;
    if (pending && (pending.kind !== 'message' ||
      pending.payload?.session_id !== saved.conversation?.session_id ||
      typeof pending.payload?.request_id !== 'string' || typeof pending.payload?.message !== 'string')) return emptyState();
    return {
      ...emptyState(), ...saved, busy: false,
      error: pending ? { message: 'A previous response was not received. Retry the saved request before continuing.', retryable: true } : saved.error,
    };
  } catch { return emptyState(); }
}

export function useConversation() {
  const [state, setState] = useState(savedState);
  const stateRef = useRef(state);
  const mounted = useRef(true);
  const controller = useRef(null);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; controller.current?.abort(); };
  }, []);

  function update(change) {
    if (!mounted.current) return;
    const next = { ...stateRef.current, ...change };
    stateRef.current = next;
    setState(next);
    try {
      // Persist before the network call so a reload can replay the SAME key.
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        ...next, busy: false, pending: next.pending?.kind === 'message' ? next.pending : null,
      }));
    } catch { /* In-memory retries remain safe if browser storage is unavailable. */ }
  }

  async function execute(pending) {
    update({ busy: true, error: null, pending });
    controller.current = new AbortController();
    try {
      const response = pending.kind === 'start'
        ? await startConversation(controller.current.signal)
        : await sendConversationMessage(pending.payload, controller.current.signal);
      if (!mounted.current) return;
      const messages = pending.kind === 'start' ? [] : stateRef.current.messages;
      update({
        conversation: response, pending: null, error: null, busy: false, needsNewSession: false,
        messages: [
          ...messages.map((item) => ({ ...item, waiting: false })),
          { id: pending.kind === 'start' ? `${response.session_id}:welcome` : `${pending.payload.request_id}:reply`, role: 'assistant', text: response.message },
        ],
      });
    } catch (error) {
      if (!mounted.current) return;
      update({
        busy: false,
        pending: error.retryable ? pending : null,
        error: { message: error.message, retryable: error.retryable },
        needsNewSession: [404, 409].includes(error.status),
        messages: stateRef.current.messages.map((item) => ({ ...item, waiting: false })),
      });
    }
  }

  function start() {
    if (stateRef.current.busy || stateRef.current.pending?.kind === 'message') return;
    void execute({ kind: 'start' });
  }

  function send(message) {
    const current = stateRef.current;
    const text = message.trim();
    if (!text || text.length > 2000 || !current.conversation || current.busy || current.pending || current.needsNewSession) return false;
    const payload = {
      session_id: current.conversation.session_id,
      request_id: crypto.randomUUID(),
      message: text,
    };
    const pending = { kind: 'message', payload };
    update({ messages: [...current.messages, { id: payload.request_id, role: 'customer', text, waiting: true }] });
    void execute(pending);
    return true;
  }

  function retry() {
    const current = stateRef.current;
    if (!current.busy && current.pending) void execute(current.pending);
  }

  return { ...state, start, send, retry };
}

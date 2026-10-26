import { StrictMode } from 'react';
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useSpokenReplies } from './useSpokenReplies.js';
import { installSynthesis } from './test/speechMocks.js';

const reply = { id: 'message-1:reply', role: 'assistant', text: 'What time would you prefer?' };

function setup(initialMessages = []) {
  const mocks = installSynthesis();
  const hook = renderHook(({ messages, paused = false }) => useSpokenReplies(messages, { paused }), {
    initialProps: { messages: initialMessages }, wrapper: StrictMode,
  });
  return { ...hook, ...mocks };
}

describe('spoken reply playback', () => {
  it('is opt-in and never speaks old history when enabled', () => {
    const { result, rerender, synthesis } = setup([reply]);
    expect(result.current.enabled).toBe(false);
    act(() => result.current.toggle());
    expect(synthesis.speak).not.toHaveBeenCalled();
    rerender({ messages: [reply, { ...reply, id: 'message-2:reply' }] });
    expect(synthesis.speak).toHaveBeenCalledTimes(1);
  });

  it('speaks a fresh reply once despite rerenders, duplicate replies, and StrictMode', () => {
    const { result, rerender, synthesis } = setup();
    act(() => result.current.toggle());
    rerender({ messages: [reply] });
    rerender({ messages: [{ ...reply }] });
    rerender({ messages: [reply, { ...reply }] });
    expect(synthesis.speak).toHaveBeenCalledTimes(1);
    expect(synthesis.speak.mock.calls[0][0].text).toBe(reply.text);
    expect(result.current.speaking).toBe(true);
  });

  it('does not read customer messages', () => {
    const { result, rerender, synthesis } = setup();
    act(() => result.current.toggle());
    rerender({ messages: [{ ...reply, role: 'customer' }] });
    expect(synthesis.speak).not.toHaveBeenCalled();
  });

  it('stops queued/current speech without replaying it', () => {
    const { result, rerender, synthesis } = setup();
    act(() => result.current.toggle());
    rerender({ messages: [reply] });
    act(() => result.current.stop());
    expect(synthesis.cancel).toHaveBeenCalledTimes(1);
    expect(result.current.speaking).toBe(false);
    rerender({ messages: [{ ...reply }] });
    expect(synthesis.speak).toHaveBeenCalledTimes(1);
  });

  it('disabling spoken replies cancels playback and re-enabling does not replay', () => {
    const { result, rerender, synthesis } = setup();
    act(() => result.current.toggle());
    rerender({ messages: [reply] });
    act(() => result.current.toggle());
    expect(result.current.enabled).toBe(false);
    expect(synthesis.cancel).toHaveBeenCalledTimes(1);
    act(() => result.current.toggle());
    expect(synthesis.speak).toHaveBeenCalledTimes(1);
  });

  it('handles completion and ignores the previous utterance after a new reply', () => {
    const { result, rerender, utterances } = setup();
    act(() => result.current.toggle());
    rerender({ messages: [reply] });
    const staleEnd = utterances[0].onend;
    rerender({ messages: [reply, { ...reply, id: 'next:reply' }] });
    act(() => staleEnd());
    expect(result.current.speaking).toBe(true);
    act(() => utterances[1].onend());
    expect(result.current.speaking).toBe(false);
  });

  it.each(['interrupted', 'canceled'])('handles %s without an error or replay', (error) => {
    const { result, rerender, utterances, synthesis } = setup();
    act(() => result.current.toggle());
    rerender({ messages: [reply] });
    act(() => utterances[0].onerror({ error }));
    expect(result.current.error).toBeNull();
    expect(result.current.speaking).toBe(false);
    rerender({ messages: [reply] });
    expect(synthesis.speak).toHaveBeenCalledTimes(1);
  });

  it('reports playback errors without retry loops', () => {
    const { result, rerender, utterances, synthesis } = setup();
    act(() => result.current.toggle());
    rerender({ messages: [reply] });
    act(() => utterances[0].onerror({ error: 'network' }));
    expect(result.current.error).toContain('available');
    rerender({ messages: [reply] });
    expect(synthesis.speak).toHaveBeenCalledTimes(1);
  });

  it('handles an unavailable synthesis engine throwing synchronously', () => {
    const { result, rerender, synthesis } = setup();
    synthesis.speak.mockImplementation(() => { throw new Error('audio unavailable'); });
    act(() => result.current.toggle());
    rerender({ messages: [reply] });
    expect(result.current.speaking).toBe(false);
    expect(result.current.error).toContain('available as text');
  });

  it('does not speak while dictation is using the microphone', () => {
    const { result, rerender, synthesis } = setup();
    act(() => result.current.toggle());
    rerender({ messages: [reply], paused: true });
    rerender({ messages: [reply], paused: false });
    expect(synthesis.speak).not.toHaveBeenCalled();
  });

  it('cancels playback on unmount', () => {
    const { result, rerender, synthesis, unmount } = setup();
    act(() => result.current.toggle());
    rerender({ messages: [reply] });
    unmount();
    expect(synthesis.cancel).toHaveBeenCalledTimes(1);
  });
});

import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useSpeechInput } from './useSpeechInput.js';
import { installRecognition, recognitionResult } from './test/speechMocks.js';

function setup(options = {}) {
  const instances = installRecognition(options);
  const onTranscript = vi.fn();
  const hook = renderHook(({ disabled }) => useSpeechInput({ disabled, onTranscript }), { initialProps: { disabled: false } });
  return { ...hook, instances, onTranscript };
}

describe('speech input lifecycle', () => {
  it.each([false, true])('supports the browser constructor (prefixed: %s)', (prefixed) => {
    const { result, instances } = setup({ prefixed });
    expect(result.current.supported).toBe(true);
    act(() => { result.current.start(); result.current.start(); });
    expect(instances).toHaveLength(1);
    expect(instances[0].lang).toBe('en-US');
    expect(instances[0].continuous).toBe(false);
    expect(instances[0].interimResults).toBe(true);
    expect(result.current.status).toBe('starting');
    act(() => instances[0].onstart());
    expect(result.current.status).toBe('listening');
  });

  it('previews interim speech, processes once, and delivers only finalized text', () => {
    const { result, instances, onTranscript } = setup();
    act(() => result.current.start());
    const recognition = instances[0];
    act(() => recognition.onresult({ results: [recognitionResult('tomorrow', false)] }));
    expect(result.current.transcript).toBe('tomorrow');
    expect(onTranscript).not.toHaveBeenCalled();
    act(() => { recognition.onspeechend(); result.current.stop(); });
    expect(recognition.stop).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe('processing');
    const repeated = { results: [recognitionResult('tomorrow'), recognitionResult('at seven')] };
    act(() => { recognition.onresult(repeated); recognition.onresult(repeated); });
    const end = recognition.onend;
    act(() => { end(); end(); });
    expect(onTranscript).toHaveBeenCalledExactlyOnceWith('tomorrow at seven');
    expect(result.current.status).toBe('ready');
  });

  it.each(['not-allowed', 'service-not-allowed', 'audio-capture', 'network', 'language-not-supported', 'no-speech', 'unknown-error'])('handles %s without producing a message', (code) => {
    const { result, instances, onTranscript } = setup();
    act(() => result.current.start());
    act(() => instances[0].onerror({ error: code }));
    expect(result.current.status).toBe('error');
    expect(result.current.error).toMatch(/type your message|type|microphone/i);
    expect(result.current.busy).toBe(false);
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it.each([[], [recognitionResult('   ')], [recognitionResult('uncertain words', false)]])('does not accept empty or interim-only results (%j)', (results) => {
    const { result, instances, onTranscript } = setup();
    act(() => result.current.start());
    act(() => { instances[0].onresult({ results }); instances[0].onend(); });
    expect(result.current.error).toContain('No clear speech');
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it('treats an aborted recognition as a quiet interruption', () => {
    const { result, instances } = setup();
    act(() => result.current.start());
    act(() => instances[0].onerror({ error: 'aborted' }));
    expect(result.current.status).toBe('idle');
    expect(result.current.error).toBeNull();
  });

  it('ignores late events after cancel and allows another attempt', () => {
    const { result, instances, onTranscript } = setup();
    act(() => result.current.start());
    const oldResult = instances[0].onresult;
    const oldEnd = instances[0].onend;
    const oldSpeechEnd = instances[0].onspeechend;
    act(() => { result.current.cancel(); result.current.start(); });
    act(() => {
      oldResult({ results: [recognitionResult('stale booking')] });
      oldEnd();
      oldSpeechEnd();
    });
    expect(instances).toHaveLength(2);
    expect(instances[1].stop).not.toHaveBeenCalled();
    expect(onTranscript).not.toHaveBeenCalled();
    expect(result.current.status).toBe('starting');
  });

  it('cancels on disabled state and unmount and blocks new recognition', () => {
    const { result, instances, rerender, unmount } = setup();
    act(() => result.current.start());
    rerender({ disabled: true });
    expect(instances[0].abort).toHaveBeenCalledTimes(1);
    act(() => expect(result.current.start()).toBe(false));
    rerender({ disabled: false });
    act(() => result.current.start());
    unmount();
    expect(instances[1].abort).toHaveBeenCalledTimes(1);
  });

  it('handles a synchronous start failure without trapping the text input', () => {
    const { result, onTranscript } = setup({ startError: new Error('browser rejected start') });
    act(() => result.current.start());
    expect(result.current.status).toBe('error');
    expect(result.current.busy).toBe(false);
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it('reports unsupported browsers without attempting recognition', () => {
    vi.stubGlobal('SpeechRecognition', undefined);
    vi.stubGlobal('webkitSpeechRecognition', undefined);
    const { result } = renderHook(() => useSpeechInput({ disabled: false, onTranscript: vi.fn() }));
    expect(result.current.supported).toBe(false);
    act(() => expect(result.current.start()).toBe(false));
  });
});

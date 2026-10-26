import { afterEach, describe, expect, it, vi } from 'vitest';
import { sendTurn, startSession } from './api.js';

afterEach(() => vi.restoreAllMocks());

function mockFetch(ok, body, status = 200) {
  const fn = vi.fn().mockResolvedValue({ ok, status, json: async () => body });
  vi.stubGlobal('fetch', fn);
  return fn;
}

describe('api client', () => {
  it('starts a session with POST /api/sessions', async () => {
    const fetchMock = mockFetch(true, { session_id: 'abc', reply: 'Hello', state: 'start' });
    const data = await startSession();
    expect(data.session_id).toBe('abc');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/sessions');
    expect(fetchMock.mock.calls[0][1].method).toBe('POST');
  });

  it('sends the caller text as JSON', async () => {
    const fetchMock = mockFetch(true, { reply: 'ok' });
    await sendTurn('abc', 'book a cleaning');
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/sessions/abc/turn');
    expect(JSON.parse(options.body)).toEqual({ text: 'book a cleaning' });
  });

  it('throws on a failed request', async () => {
    mockFetch(false, {}, 404);
    await expect(sendTurn('nope', 'hi')).rejects.toThrow('404');
  });
});

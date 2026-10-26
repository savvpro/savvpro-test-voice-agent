import { describe, expect, it, vi } from 'vitest';
import { ApiError, isConversation, sendConversationMessage, startConversation } from './api.js';
import { conversation, http, reservation } from './test/fixtures.js';

describe('API transport', () => {
  it('uses the local start endpoint without a made-up session or booking', async () => {
    const fetch = vi.fn().mockResolvedValue(http(conversation(), 201));
    vi.stubGlobal('fetch', fetch);
    expect(await startConversation()).toEqual(conversation());
    expect(fetch).toHaveBeenCalledWith('/api/conversations/start', expect.objectContaining({ method: 'POST' }));
    expect(fetch.mock.calls[0][1].body).toBeUndefined();
  });

  it('sends exactly the supplied session, text, and retained message ID', async () => {
    const fetch = vi.fn().mockResolvedValue(http(conversation()));
    vi.stubGlobal('fetch', fetch);
    const payload = { session_id: conversation().session_id, message: 'hello', request_id: 'one-turn' };
    await sendConversationMessage(payload);
    expect(fetch.mock.calls[0][0]).toBe('/api/conversations/message');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(payload);
  });

  it.each([408, 429, 500, 503])('marks HTTP %i as safe to retry with the original key', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(http({ detail: 'Please retry the same request.' }, status)));
    await expect(startConversation()).rejects.toMatchObject({ status, retryable: true });
  });

  it.each([404, 409, 422])('does not automatically retry HTTP %i', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(http({ detail: [{ msg: 'Invalid fields' }] }, status)));
    await expect(startConversation()).rejects.toMatchObject({ status, retryable: false });
  });

  it('handles a network failure without claiming a message was not processed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('private network detail')));
    await expect(startConversation()).rejects.toMatchObject({ retryable: true, message: expect.stringContaining('may already have been processed') });
  });

  it('rejects malformed successful JSON and leaves the result uncertain', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(http({ status: 'completed' })));
    await expect(startConversation()).rejects.toBeInstanceOf(ApiError);
  });

  it('rejects a response belonging to another session', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(http(conversation({ session_id: 'wrong-session' }))));
    await expect(sendConversationMessage({ session_id: 'right-session', message: 'yes', request_id: 'r' })).rejects.toMatchObject({ retryable: true });
  });

  it('requires reservation data for a completed response', () => {
    expect(isConversation(conversation({ status: 'completed' }))).toBe(false);
    expect(isConversation(conversation({ status: 'completed', reservation }))).toBe(true);
  });

  it('handles non-JSON errors without displaying raw proxy/server HTML', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => { throw new Error('<SECRET>'); } }));
    await expect(startConversation()).rejects.toMatchObject({ retryable: true, message: 'That request could not be accepted. Please try again.' });
  });
});

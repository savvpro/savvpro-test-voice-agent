import { afterEach, expect, it, vi } from 'vitest'
import { ApiError, sendTurn } from './api'

afterEach(() => vi.unstubAllGlobals())

const body = { call_id: 'abc', reply: 'hi', ended: false, decision: {} }

it('posts JSON and returns parsed body', async () => {
  const f = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }))
  vi.stubGlobal('fetch', f)
  expect(await sendTurn('abc', 'book')).toEqual(body)
  const [url, init] = f.mock.calls[0]
  expect(url).toBe('/api/calls/abc/turns')
  expect(init.method).toBe('POST')
  expect(JSON.parse(init.body)).toEqual({ text: 'book' })
})

it('rejects ApiError on 404', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ detail: 'Call not found or expired' }), { status: 404 })),
  )
  const err = await sendTurn('abc', 'x').catch((e) => e)
  expect(err).toBeInstanceOf(ApiError)
  expect(err.status).toBe(404)
  expect(err.message).toBe('Call not found or expired')
})

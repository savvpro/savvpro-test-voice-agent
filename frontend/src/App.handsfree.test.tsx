import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import App from './App'
import * as api from './api'

const sp = vi.hoisted(() => {
  const pending: Array<(t: string) => void> = []
  return {
    pending,
    listen: vi.fn(() => new Promise<string>((r) => pending.push(r))),
    // like the real hook: stopping aborts the recognizer, resolving the pending listen with ''
    stop: vi.fn(() => pending.splice(0).forEach((r) => r(''))),
    speak: vi.fn().mockResolvedValue(undefined),
  }
})
vi.mock('./useSpeech', () => ({ useSpeech: () => ({ supported: true, listening: false, voices: [], setVoiceName: vi.fn(), ...sp }) }))
vi.mock('./api', async (orig) => ({ ...(await orig<typeof api>()), startCall: vi.fn(), sendTurn: vi.fn() }))

const dec = { intent: 'x', entities: {}, state: 's', action: 'greet', slots: {} }

it('typing while hands-free leaves exactly one listen loop', async () => {
  vi.mocked(api.startCall).mockResolvedValue({ call_id: 'c', reply: 'hello', decision: dec, ended: false })
  vi.mocked(api.sendTurn).mockResolvedValue({ call_id: 'c', reply: 'ok', decision: dec, ended: false })
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole('button', { name: 'Start call' }))
  await screen.findByText('hello')
  await user.click(screen.getByLabelText('Hands-free'))
  expect(sp.listen).toHaveBeenCalledTimes(1)

  await user.type(screen.getByLabelText('Type a message'), 'hi')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  await screen.findByText('ok')
  await act(async () => {})

  // one loop from the toggle, one after the reply; the superseded loop must not re-arm
  expect(sp.listen).toHaveBeenCalledTimes(2)
  expect(sp.pending).toHaveLength(1)
})

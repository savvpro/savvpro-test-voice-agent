import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './api'

vi.mock('./useSpeech', () => ({
  useSpeech: () => ({
    supported: false,
    listening: false,
    listen: vi.fn(),
    stop: vi.fn(),
    speak: vi.fn().mockResolvedValue(undefined),
    voices: [],
    setVoiceName: vi.fn(),
  }),
}))
vi.mock('./api', async (orig) => ({ ...(await orig<typeof api>()), startCall: vi.fn(), sendTurn: vi.fn() }))

const dec = (o = {}) => ({ intent: 'greet', entities: {}, state: 'idle', action: 'greet', slots: {}, ...o })

beforeEach(() => {
  vi.mocked(api.startCall).mockResolvedValue({
    call_id: 'c1',
    reply: 'Welcome to Maple Street Clinic',
    decision: dec(),
    ended: false,
  })
})

async function startAndSend(text: string) {
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole('button', { name: 'Start call' }))
  await screen.findByText('Welcome to Maple Street Clinic')
  await user.type(screen.getByLabelText('Type a message'), text)
  await user.click(screen.getByRole('button', { name: 'Send' }))
}

it('shows greeting, then reply and decision after sending text', async () => {
  vi.mocked(api.sendTurn).mockResolvedValue({
    call_id: 'c1',
    reply: 'What time works?',
    ended: false,
    decision: dec({ intent: 'book', action: 'ask_time', entities: { doctor: 'Dr. Lee' }, slots: { doctor: 'Dr. Lee' } }),
  })
  await startAndSend('book')
  expect(await screen.findByText('What time works?')).toBeInTheDocument()
  expect(screen.getAllByText('Ask time').length).toBeGreaterThan(0)
})

it('offers a new call on 404', async () => {
  vi.mocked(api.sendTurn).mockRejectedValue(new api.ApiError(404, 'Call not found or expired'))
  await startAndSend('hi')
  expect(await screen.findByText(/This call has ended or expired/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Start new call' })).toBeInTheDocument()
})

it.each([
  [new TypeError('Failed to fetch'), /Can’t reach the clinic line/, true],
  [new api.ApiError(500, 'Internal error'), /Something went wrong on our side/, true],
  [new api.ApiError(422, 'Unprocessable'), /Something went wrong on our side/, false],
])('error notice for %s', async (err, text, retry) => {
  vi.mocked(api.sendTurn).mockRejectedValue(err)
  await startAndSend('hi')
  expect(await screen.findByText(text)).toBeInTheDocument()
  if (err instanceof api.ApiError) expect(screen.queryByText(/Can’t reach/)).not.toBeInTheDocument()
  expect(!!screen.queryByRole('button', { name: 'Retry' })).toBe(retry)
})

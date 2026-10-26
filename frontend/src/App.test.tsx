import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App, { prettyTime } from './App'

const appointment = {
  id: 'fake-id',
  reference: 'DEADBEEF',
  service: 'tyre_rotation',
  service_name: 'Tyre Rotation',
  vehicle: 'suv',
  date: '2026-10-27',
  time: '11:00',
  description: 'Tyre Rotation for your SUV',
  minutes: 30,
  status: 'active',
}
const session = {
  revision: 0,
  state: {},
  appointments: [appointment],
  history: [],
  welcome: 'Welcome to Bayline.',
  caller: 'Alex Rivera',
  timezone: 'Asia/Karachi',
  demo_date: '2026-10-27',
}
const trace = {
  from_state: 'IDLE',
  to_state: 'COLLECTING',
  intent: 'BOOK',
  rules: ['intent_book'],
  extracted: {},
  validation: [],
  action: 'none',
}

function mockTurnResults(results: unknown[]) {
  const fallback = vi.mocked(fetch)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) =>
      url === '/api/turn'
        ? { ok: true, json: async () => results.shift() }
        : fallback(url, options),
    ),
  )
}

function holdSpeechPlayback() {
  const speak = vi.fn()
  vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), getVoices: () => [], speak })
  vi.stubGlobal(
    'SpeechSynthesisUtterance',
    class {
      text: string
      constructor(text: string) {
        this.text = text
      }
    },
  )
  return speak
}

beforeEach(() => {
  window.history.replaceState(null, '', '/')
  vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url === '/api/capabilities'
          ? { server_stt: false, services: {}, timezone: 'Asia/Karachi' }
          : url === '/api/turn'
            ? {
                revision: 1,
                state: { phase: 'COLLECTING' },
                appointments: [appointment],
                reply: 'Which service?',
                trace,
              }
            : session,
    })),
  )
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it('opens a distinct appointments view and targets the selected booking when managing it', async () => {
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.click(screen.getByRole('link', { name: /Your appointments/ }))
  expect(screen.getByRole('heading', { name: 'Your appointments.' })).toBeInTheDocument()
  expect(screen.queryByRole('textbox', { name: 'Type your message' })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Your appointments/ })).toHaveAttribute(
    'aria-current',
    'page',
  )
  expect(screen.getByText('DEADBEEF')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Reschedule' }))
  expect(screen.getByRole('textbox', { name: 'Type your message' })).toBeInTheDocument()
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      '/api/turn',
      expect.objectContaining({
        body: expect.stringContaining('Reschedule my appointment reference DEADBEEF'),
      }),
    ),
  )
})

it('supports appointment deep links and cancellation without bypassing confirmation', async () => {
  window.history.replaceState(null, '', '/#appointments')
  render(<App />)
  await screen.findByText('DEADBEEF')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel appointment' }))
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      '/api/turn',
      expect.objectContaining({
        body: expect.stringContaining('Cancel my appointment reference DEADBEEF'),
      }),
    ),
  )
  const turns = vi.mocked(fetch).mock.calls.filter(([url]) => url === '/api/turn')
  expect(turns).toHaveLength(1)
  expect(String(turns[0][1]?.body)).not.toContain('"text":"yes"')
})

it('responds to back navigation and shows an actionable empty appointment view', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url === '/api/capabilities'
          ? { server_stt: false, services: {}, timezone: 'Asia/Karachi' }
          : { ...session, appointments: [] },
    })),
  )
  render(<App />)
  await screen.findByText('A clear schedule.')
  window.history.replaceState(null, '', '/#appointments')
  fireEvent(window, new HashChangeEvent('hashchange'))
  expect(screen.getByRole('heading', { name: 'No upcoming appointments.' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Book your first service/ })).toBeEnabled()
  window.history.replaceState(null, '', '/#reception')
  fireEvent(window, new HashChangeEvent('hashchange'))
  expect(screen.getByRole('button', { name: /Start a call/ })).toBeInTheDocument()
})

it('renders the seeded appointment and disables unavailable server speech', async () => {
  render(<App />)
  expect(await screen.findByText('11:00 AM')).toBeInTheDocument()
  expect(screen.getByText('Tyre Rotation')).toBeInTheDocument()
  expect(screen.getByRole('option', { name: /Server speech/ })).toBeDisabled()
  expect(screen.getByRole('button', { name: /Start a call/ })).toBeEnabled()
})

it('dispatches quick utterances through the same turn endpoint as typing', async () => {
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.click(
    screen.getByRole('button', { name: /Book a brake inspection for my SUV tomorrow at 2 PM/ }),
  )
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      '/api/turn',
      expect.objectContaining({ body: expect.stringContaining('Book a brake inspection') }),
    ),
  )
  expect(await screen.findByText('Which service?')).toBeInTheDocument()
  const input = screen.getByRole('textbox', { name: 'Type your message' })
  fireEvent.change(input, { target: { value: 'oil change' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      '/api/turn',
      expect.objectContaining({ body: expect.stringContaining('oil change') }),
    ),
  )
})

it('requires deliberate reset and calls the session-scoped endpoint', async () => {
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.click(screen.getByRole('button', { name: /Reset demo/ }))
  expect(screen.getByText('Reset this demo session?')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Reset Demo Session' }))
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      '/api/session/reset',
      expect.objectContaining({ body: '{"revision":0}' }),
    ),
  )
})

it('formats midnight, noon, and afternoon without timezone conversion', () => {
  expect(prettyTime('00:00')).toBe('12:00 AM')
  expect(prettyTime('12:30')).toBe('12:30 PM')
  expect(prettyTime('17:30')).toBe('5:30 PM')
})

it('offers typed entry without starting a voice call or sending a turn', async () => {
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.click(screen.getByRole('button', { name: 'Type instead' }))
  expect(screen.getByRole('textbox', { name: 'Type your message' })).toHaveFocus()
  expect(vi.mocked(fetch).mock.calls.filter(([url]) => url === '/api/turn')).toHaveLength(0)
})

it('lists multiple appointments and manages the chosen reference rather than the first booking', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url === '/api/capabilities'
          ? {
              server_stt: false,
              services: { oil_change: { name: 'Oil Change', minutes: 30 } },
              timezone: 'Asia/Karachi',
            }
          : url === '/api/turn'
            ? { revision: 1, state: {}, appointments: [appointment], reply: 'Which date?', trace }
            : {
                ...session,
                appointments: [
                  appointment,
                  {
                    ...appointment,
                    id: 'second',
                    reference: 'CAFEBABE',
                    service_name: 'Brake Inspection',
                    service: 'brake_inspection',
                    minutes: 60,
                  },
                ],
              },
    })),
  )
  render(<App />)
  await screen.findByText('11:00 AM')
  expect(screen.getByRole('button', { name: /Oil Change.*30 min/ })).toBeEnabled()
  fireEvent.click(screen.getByRole('link', { name: /Your appointments/ }))
  expect(screen.getAllByRole('article')).toHaveLength(2)
  const second = screen.getByRole('article', { name: 'Brake Inspection booking CAFEBABE' })
  fireEvent.click(within(second).getByRole('button', { name: 'Reschedule' }))
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      '/api/turn',
      expect.objectContaining({
        body: expect.stringContaining('Reschedule my appointment reference CAFEBABE'),
      }),
    ),
  )
})

it('starts a fresh call with a greeting after a previous call ended', async () => {
  const speak = vi.fn()
  vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), getVoices: () => [], speak })
  vi.stubGlobal(
    'SpeechSynthesisUtterance',
    class {
      text: string
      constructor(text: string) {
        this.text = text
      }
    },
  )
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url === '/api/capabilities'
          ? { server_stt: false, services: {}, timezone: 'Asia/Karachi' }
          : { ...session, state: { phase: 'ENDED', last_reply: 'Goodbye.' } },
    })),
  )
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.click(screen.getByRole('button', { name: /Start a call/ }))
  expect(speak.mock.calls[0][0].text).toBe('Welcome to Bayline.')
})

it('speaks a quick-test reply without requiring a call and offers stop playback', async () => {
  const speak = vi.fn()
  const cancel = vi.fn()
  vi.stubGlobal('speechSynthesis', { cancel, getVoices: () => [], speak })
  vi.stubGlobal(
    'SpeechSynthesisUtterance',
    class {
      text: string
      constructor(text: string) {
        this.text = text
      }
    },
  )
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.click(screen.getByRole('button', { name: /What time do you close/ }))
  await waitFor(() => expect(speak).toHaveBeenCalledOnce())
  expect(speak.mock.calls[0][0].text).toBe('Which service?')
  expect(screen.queryByRole('button', { name: 'End call' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Stop reply' }))
  expect(screen.queryByRole('button', { name: 'Stop reply' })).not.toBeInTheDocument()
  expect(cancel).toHaveBeenCalled()
})

it('keeps a delayed API reply silent after navigating away from reception', async () => {
  const speak = vi.fn()
  vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), getVoices: () => [], speak })
  vi.stubGlobal(
    'SpeechSynthesisUtterance',
    class {
      text: string
      constructor(text: string) {
        this.text = text
      }
    },
  )
  let resolveTurn!: (value: unknown) => void
  const pending = new Promise((resolve) => {
    resolveTurn = resolve
  })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url === '/api/capabilities'
          ? { server_stt: false, services: {}, timezone: 'Asia/Karachi' }
          : url === '/api/turn'
            ? await pending
            : session,
    })),
  )
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.click(screen.getByRole('button', { name: /What time do you close/ }))
  fireEvent.click(screen.getByRole('link', { name: /Your appointments/ }))
  resolveTurn({
    revision: 1,
    state: {},
    appointments: [appointment],
    reply: 'We close at six.',
    trace,
  })
  await waitFor(() => expect(screen.getByRole('button', { name: 'Reschedule' })).toBeEnabled())
  expect(speak).not.toHaveBeenCalled()
})

it('updates a rescheduled booking everywhere immediately, before speech ends', async () => {
  const speak = holdSpeechPlayback()
  const moved = { ...appointment, date: '2026-10-29', time: '15:00' }
  mockTurnResults([
    {
      revision: 1,
      state: {
        phase: 'CONFIRMING',
        intent: 'RESCHEDULE',
        slots: { service: 'tyre_rotation', vehicle: 'suv', date: moved.date, time: moved.time },
      },
      appointments: [appointment],
      reply: 'Move your tyre rotation to Thursday at three PM?',
      trace: { ...trace, intent: 'RESCHEDULE', action: 'none' },
    },
    {
      revision: 2,
      state: { phase: 'COMPLETED', appointment: moved },
      appointments: [moved],
      reply: 'Your appointment has been rescheduled.',
      trace: { ...trace, intent: 'RESCHEDULE', action: 'rescheduled' },
    },
  ])
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.change(screen.getByRole('textbox', { name: 'Type your message' }), {
    target: { value: 'Reschedule to Thursday at 3 PM' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  await screen.findByRole('button', { name: 'Confirm appointment' })
  fireEvent.click(screen.getByRole('link', { name: /Your appointments/ }))
  expect(within(screen.getByRole('article')).getByText('11:00 AM')).toBeInTheDocument()
  expect(within(screen.getByRole('article')).queryByText('3:00 PM')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('link', { name: 'Reception' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm appointment' }))
  await screen.findByText('Appointment rescheduled')
  const summary = screen.getByRole('complementary', { name: 'Next appointment summary' })
  expect(within(summary).getByText('3:00 PM')).toBeInTheDocument()
  expect(within(summary).queryByText('11:00 AM')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Stop reply' })).toBeInTheDocument()
  expect(speak).toHaveBeenCalledTimes(2)
  fireEvent.click(screen.getByRole('button', { name: /View updated schedule/ }))
  expect(within(screen.getByRole('article')).getByText('3:00 PM')).toBeInTheDocument()
  expect(vi.mocked(fetch).mock.calls.filter(([url]) => url === '/api/session')).toHaveLength(1)
})

it('removes a confirmed cancellation from the card, list and count before speech ends', async () => {
  holdSpeechPlayback()
  mockTurnResults([
    {
      revision: 1,
      state: {
        phase: 'CONFIRMING',
        intent: 'CANCEL',
        slots: {
          service: 'tyre_rotation',
          vehicle: 'suv',
          date: appointment.date,
          time: appointment.time,
        },
      },
      appointments: [appointment],
      reply: 'Cancel your tyre rotation?',
      trace: { ...trace, intent: 'CANCEL', action: 'none' },
    },
    {
      revision: 2,
      state: { phase: 'COMPLETED', appointment: { ...appointment, status: 'cancelled' } },
      appointments: [],
      reply: 'Your appointment has been cancelled.',
      trace: { ...trace, intent: 'CANCEL', action: 'cancelled' },
    },
  ])
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel appointment' }))
  await screen.findByRole('button', { name: 'Confirm cancellation' })
  expect(
    within(screen.getByRole('link', { name: /Your appointments/ })).getByText('1'),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Confirm cancellation' }))
  await screen.findByText('Appointment cancelled')
  const summary = screen.getByRole('complementary', { name: 'Next appointment summary' })
  expect(within(summary).getByText('A clear schedule.')).toBeInTheDocument()
  expect(within(summary).queryByText('11:00 AM')).not.toBeInTheDocument()
  expect(
    within(screen.getByRole('link', { name: /Your appointments/ })).getByText('0'),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Stop reply' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /View updated schedule/ }))
  expect(screen.queryByRole('article')).not.toBeInTheDocument()
  expect(screen.getByText('No upcoming appointments.')).toBeInTheDocument()
})

it('keeps the original schedule when a reschedule cannot be committed', async () => {
  mockTurnResults([
    {
      revision: 1,
      state: {
        phase: 'CONFIRMING',
        intent: 'RESCHEDULE',
        slots: { service: 'tyre_rotation', vehicle: 'suv', date: '2026-10-29', time: '15:00' },
      },
      appointments: [appointment],
      reply: 'Move to Thursday at three?',
      trace,
    },
    {
      revision: 2,
      state: { phase: 'COLLECTING', intent: 'RESCHEDULE' },
      appointments: [appointment],
      reply: 'That slot became unavailable. Your original booking is unchanged.',
      trace: { ...trace, action: 'none', validation: ['both_bays_occupied'] },
    },
  ])
  render(<App />)
  await screen.findByText('11:00 AM')
  fireEvent.change(screen.getByRole('textbox', { name: 'Type your message' }), {
    target: { value: 'Move to Thursday at 3 PM' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  await screen.findByRole('button', { name: 'Confirm appointment' })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm appointment' }))
  await screen.findByText('That slot became unavailable. Your original booking is unchanged.')
  expect(screen.queryByRole('status', { name: 'Schedule update' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('link', { name: /Your appointments/ }))
  expect(within(screen.getByRole('article')).getByText('11:00 AM')).toBeInTheDocument()
})

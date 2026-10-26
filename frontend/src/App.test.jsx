import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App.jsx';
import { conversation, deferred, details, http, reservation } from './test/fixtures.js';
import { STORAGE_KEY } from './useConversation.js';

let fetchMock;
beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

async function started(response = conversation()) {
  const user = userEvent.setup();
  fetchMock.mockResolvedValueOnce(http(response, 201));
  const view = render(<App />);
  await user.click(screen.getByRole('button', { name: 'Start Conversation' }));
  await screen.findByText(response.message);
  return { user, ...view };
}

async function typeAndSend(user, text) {
  await user.type(screen.getByRole('textbox', { name: 'Your message' }), text);
  await user.click(screen.getByRole('button', { name: 'Send message' }));
}

describe('reservation chat', () => {
  it('starts only on request and keeps the composer disabled until a session exists', () => {
    render(<App />);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole('textbox', { name: 'Your message' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
    expect(screen.getByRole('link', { name: 'Skip to conversation' })).toHaveAttribute('href', '#conversation');
  });

  it('uses the real session returned by the start API and focuses the input', async () => {
    await started();
    expect(fetchMock.mock.calls[0][0]).toBe('/api/conversations/start');
    expect(screen.getByRole('textbox')).toHaveFocus();
    expect(screen.getByText('Choosing a date')).toBeInTheDocument();
  });

  it('renders customer and assistant messages and sends normalized text with a unique key', async () => {
    const { user } = await started();
    fetchMock.mockResolvedValueOnce(http(conversation({ status: 'ask_time', message: 'What time would you prefer?', collected_data: { date: details.date, time: null, party_size: null } })));
    await typeAndSend(user, '  tomorrow  ');
    await screen.findByText('What time would you prefer?');
    const payload = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(payload).toEqual({ session_id: conversation().session_id, message: 'tomorrow', request_id: expect.any(String) });
    expect(payload.request_id.length).toBeGreaterThan(10);
    const messages = within(screen.getByRole('list', { name: 'Conversation messages' }));
    expect(messages.getByText('tomorrow')).toBeInTheDocument();
    expect(messages.getByText('What time would you prefer?')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toHaveValue('');
  });

  it('sends Enter once and uses a different key for a later message', async () => {
    const { user } = await started();
    fetchMock.mockResolvedValueOnce(http(conversation({ message: 'Choose a time.', status: 'ask_time' })));
    await user.type(screen.getByRole('textbox'), 'tomorrow{Enter}');
    await screen.findByText('Choose a time.');
    const first = JSON.parse(fetchMock.mock.calls[1][1].body);
    fetchMock.mockResolvedValueOnce(http(conversation({ message: 'How many guests?', status: 'ask_party_size' })));
    await typeAndSend(user, '7pm');
    await screen.findByText('How many guests?');
    const second = JSON.parse(fetchMock.mock.calls[2][1].body);
    expect(first.request_id).not.toBe(second.request_id);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('supports Shift+Enter and does not submit during IME composition', async () => {
    const { user } = await started();
    await user.type(screen.getByRole('textbox'), 'hello{Shift>}{Enter}{/Shift}there');
    expect(screen.getByRole('textbox')).toHaveValue('hello\nthere');
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter', isComposing: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('prevents whitespace submissions and bounds text to the API limit', async () => {
    const { user } = await started();
    await user.type(screen.getByRole('textbox'), '   ');
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
    expect(screen.getByRole('textbox')).toHaveAttribute('maxlength', '2000');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('shows start loading and prevents duplicate start clicks', async () => {
    const pending = deferred();
    fetchMock.mockReturnValue(pending.promise);
    render(<App />);
    const button = screen.getByRole('button', { name: 'Start Conversation' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(screen.getByRole('button', { name: /Starting/ })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    pending.resolve(http(conversation(), 201));
    await screen.findByText(conversation().message);
  });

  it('disables sends and new conversations while a response is pending', async () => {
    const { user } = await started();
    const pending = deferred();
    fetchMock.mockReturnValueOnce(pending.promise);
    await typeAndSend(user, 'tomorrow');
    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'New conversation' })).toBeDisabled();
    expect(screen.getByRole('status', { name: 'Assistant is replying' })).toBeInTheDocument();
    fireEvent.submit(screen.getByRole('form', { name: 'Send a message' }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    pending.resolve(http(conversation({ message: 'A server reply.' })));
    await screen.findByText('A server reply.');
  });

  it('retries a failed message with exactly the same payload and no duplicate customer bubble', async () => {
    const { user } = await started();
    fetchMock.mockResolvedValueOnce(http({ detail: 'Storage unavailable. Please retry the same request.' }, 503));
    await typeAndSend(user, 'tomorrow at 7pm for 4');
    await screen.findByRole('alert');
    const original = fetchMock.mock.calls[1][1].body;
    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'New conversation' })).toBeDisabled();
    fetchMock.mockResolvedValueOnce(http(conversation({ status: 'confirm', message: 'Shall I book these details?', collected_data: details })));
    await user.click(screen.getByRole('button', { name: 'Retry same message' }));
    await screen.findByText('Shall I book these details?');
    expect(fetchMock.mock.calls[2][1].body).toBe(original);
    expect(screen.getAllByText('tomorrow at 7pm for 4')).toHaveLength(1);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText('Ready for your confirmation')).toBeInTheDocument();
  });

  it('retains a pending confirmation key across a reload and displays the recovered booking', async () => {
    const { user, unmount } = await started(conversation({ status: 'confirm', message: 'Please confirm these details.', collected_data: details }));
    fetchMock.mockRejectedValueOnce(new TypeError('Network lost'));
    await typeAndSend(user, 'yes');
    await screen.findByRole('alert');
    const payload = fetchMock.mock.calls[1][1].body;
    expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)).pending.payload.request_id).toBe(JSON.parse(payload).request_id);
    unmount();
    fetchMock.mockResolvedValueOnce(http(conversation({ status: 'completed', message: 'Your reservation has been confirmed!', collected_data: details, reservation })));
    render(<App />);
    expect(screen.getByText(/A previous response was not received/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry same message' }));
    await screen.findByRole('heading', { name: 'Your table is booked.' });
    expect(fetchMock.mock.calls[2][1].body).toBe(payload);
    expect(screen.getByText(reservation.reservation_id)).toBeInTheDocument();
    expect(screen.getByText('Reservation confirmed')).toBeInTheDocument();
  });

  it('displays server unavailable-time text and corrected summary without fabricating a reservation', async () => {
    const { user } = await started();
    const message = 'No suitable table is available for that time. What other time would you prefer?';
    fetchMock.mockResolvedValueOnce(http(conversation({ status: 'ask_time', message, collected_data: { ...details, time: null } })));
    await typeAndSend(user, 'tomorrow at 7pm for 4');
    await screen.findByText(message);
    expect(screen.getByText('Choosing a time')).toBeInTheDocument();
    expect(screen.getByText('4 guests')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Your table is booked.' })).not.toBeInTheDocument();
  });

  it('displays cancellation as returned by the backend', async () => {
    const { user } = await started();
    fetchMock.mockResolvedValueOnce(http(conversation({ status: 'cancelled', message: 'Your reservation process has been cancelled.' })));
    await typeAndSend(user, 'cancel');
    await screen.findByText('Your reservation process has been cancelled.');
    expect(screen.getByText('Conversation cancelled')).toBeInTheDocument();
  });

  it('starts a new session through the API and clears the old chat only after success', async () => {
    const { user } = await started(conversation({ status: 'completed', message: 'An earlier booking is confirmed.', collected_data: details, reservation }));
    expect(screen.getByRole('heading', { name: 'Your table is booked.' })).toBeInTheDocument();
    fetchMock.mockResolvedValueOnce(http(conversation({ session_id: 'another-server-session', message: 'Welcome to your new conversation.' }), 201));
    await user.click(screen.getByRole('button', { name: 'New conversation' }));
    await screen.findByText('Welcome to your new conversation.');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/conversations/start');
    expect(screen.queryByText('An earlier booking is confirmed.')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Your table is booked.' })).not.toBeInTheDocument();
    fetchMock.mockResolvedValueOnce(http(conversation({ session_id: 'another-server-session', message: 'Choose a date.' })));
    await typeAndSend(user, 'hello');
    await screen.findByText('Choose a date.');
    expect(JSON.parse(fetchMock.mock.calls[2][1].body).session_id).toBe('another-server-session');
  });

  it('recovers from an unknown session by requiring a fresh conversation', async () => {
    const { user } = await started();
    fetchMock.mockResolvedValueOnce(http({ detail: 'Unknown conversation' }, 404));
    await typeAndSend(user, 'hello');
    await screen.findByRole('alert');
    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Retry same message' })).not.toBeInTheDocument();
    fetchMock.mockResolvedValueOnce(http(conversation({ session_id: 'recovered-session', message: 'A fresh welcome.' }), 201));
    await user.click(screen.getByRole('button', { name: 'New conversation' }));
    await screen.findByText('A fresh welcome.');
    expect(screen.getByRole('textbox')).toBeEnabled();
  });

  it('allows retrying a failed start without claiming any reservation exists', async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValueOnce(new Error('Offline'));
    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Start Conversation' }));
    await screen.findByRole('alert');
    fetchMock.mockResolvedValueOnce(http(conversation(), 201));
    await user.click(screen.getByRole('button', { name: 'Try starting again' }));
    await screen.findByText(conversation().message);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('ignores corrupt tab storage and starts cleanly', () => {
    sessionStorage.setItem(STORAGE_KEY, '{not valid json');
    render(<App />);
    expect(screen.getByRole('button', { name: 'Start Conversation' })).toBeEnabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('continues safely in memory if storage cannot be written', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage disabled'); });
    const { user } = await started();
    fetchMock.mockRejectedValueOnce(new Error('Offline'));
    await typeAndSend(user, 'tomorrow');
    await screen.findByRole('alert');
    const original = fetchMock.mock.calls[1][1].body;
    fetchMock.mockResolvedValueOnce(http(conversation({ message: 'A recovered reply.' })));
    await user.click(screen.getByRole('button', { name: 'Retry same message' }));
    await screen.findByText('A recovered reply.');
    expect(fetchMock.mock.calls[2][1].body).toBe(original);
  });
});

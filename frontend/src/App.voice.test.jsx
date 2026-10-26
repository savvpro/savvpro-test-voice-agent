import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App.jsx';
import { conversation, details, http, reservation } from './test/fixtures.js';
import { installRecognition, installSynthesis, recognitionResult } from './test/speechMocks.js';

let fetchMock;
beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

async function startChat(response = conversation()) {
  const user = userEvent.setup();
  fetchMock.mockResolvedValueOnce(http(response, 201));
  render(<App />);
  await user.click(screen.getByRole('button', { name: 'Start Conversation' }));
  await screen.findByText(response.message);
  return user;
}

function recognize(recognition, text) {
  act(() => {
    recognition.onstart();
    recognition.onresult({ results: [recognitionResult(text)] });
    recognition.onend();
  });
}

describe('voice controls in the chat', () => {
  it('keeps text chat usable when both speech APIs are unsupported', async () => {
    vi.stubGlobal('SpeechRecognition', undefined);
    vi.stubGlobal('webkitSpeechRecognition', undefined);
    vi.stubGlobal('speechSynthesis', undefined);
    vi.stubGlobal('SpeechSynthesisUtterance', undefined);
    const user = await startChat();
    expect(screen.getByRole('button', { name: 'Dictate a message' })).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: 'Spoken replies' })).toBeDisabled();
    expect(screen.getByText(/Voice input is unavailable/)).toBeInTheDocument();
    fetchMock.mockResolvedValueOnce(http(conversation({ message: 'Your text was received.' })));
    await user.type(screen.getByRole('textbox'), 'hello{Enter}');
    await screen.findByText('Your text was received.');
  });

  it('previews recognized words, permits correction, and sends only on explicit Send', async () => {
    const instances = installRecognition();
    const user = await startChat();
    await user.click(screen.getByRole('button', { name: 'Dictate a message' }));
    act(() => instances[0].onstart());
    expect(screen.getByText(/Listening…/)).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
    act(() => instances[0].onresult({ results: [recognitionResult('tomorrow at seven for two', false)] }));
    expect(screen.getByText('Heard: tomorrow at seven for two')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Stop listening' }));
    expect(screen.getByText(/Processing speech/)).toBeInTheDocument();
    act(() => {
      instances[0].onresult({ results: [recognitionResult('tomorrow at 7pm for 2')] });
      instances[0].onend();
    });
    expect(screen.getByRole('textbox')).toHaveValue('tomorrow at 7pm for 2');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Review or edit your message/)).toBeInTheDocument();
    await user.clear(screen.getByRole('textbox'));
    await user.type(screen.getByRole('textbox'), 'tomorrow at 7pm for 4');
    fetchMock.mockResolvedValueOnce(http(conversation({ status: 'confirm', message: 'Shall I book for 4?', collected_data: details })));
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByText('Shall I book for 4?');
    const payload = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(payload).toEqual({ session_id: conversation().session_id, message: 'tomorrow at 7pm for 4', request_id: expect.any(String) });
    expect(screen.getByText('tomorrow at 7pm for 4')).toBeInTheDocument();
  });

  it('appends dictation to an existing draft without submitting or repeating final words', async () => {
    const instances = installRecognition({ prefixed: true });
    const user = await startChat();
    await user.type(screen.getByRole('textbox'), 'A table for');
    await user.click(screen.getByRole('button', { name: 'Dictate a message' }));
    const event = { results: [recognitionResult('four tomorrow')] };
    act(() => {
      instances[0].onresult(event);
      instances[0].onresult(event);
      instances[0].onend();
    });
    expect(screen.getByRole('textbox')).toHaveValue('A table for four tomorrow');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each(['not-allowed', 'network', 'audio-capture'])('handles %s and returns to text input', async (error) => {
    const instances = installRecognition();
    const user = await startChat();
    await user.click(screen.getByRole('button', { name: 'Dictate a message' }));
    act(() => instances[0].onerror({ error }));
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Dictate a message' })).toBeEnabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does not send empty recognition and preserves the typed draft', async () => {
    const instances = installRecognition();
    const user = await startChat();
    await user.type(screen.getByRole('textbox'), 'keep this');
    await user.click(screen.getByRole('button', { name: 'Dictate a message' }));
    act(() => instances[0].onend());
    expect(screen.getByText(/No clear speech/)).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toHaveValue('keep this');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('offers cancellation during processing and ignores an old recognition result', async () => {
    const instances = installRecognition();
    const user = await startChat();
    await user.click(screen.getByRole('button', { name: 'Dictate a message' }));
    const oldResult = instances[0].onresult;
    const oldEnd = instances[0].onend;
    act(() => { instances[0].onstart(); instances[0].onspeechend(); });
    await user.click(screen.getByRole('button', { name: 'Cancel dictation' }));
    act(() => { oldResult({ results: [recognitionResult('stale yes')] }); oldEnd(); });
    expect(screen.getByRole('textbox')).toHaveValue('');
    expect(screen.getByRole('textbox')).toBeEnabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('blocks form submission and rapid microphone clicks before UI updates', async () => {
    const instances = installRecognition();
    const user = await startChat();
    await user.type(screen.getByRole('textbox'), 'yes');
    const button = screen.getByRole('button', { name: 'Dictate a message' });
    fireEvent.click(button);
    fireEvent.click(button); // Cancels the first start rather than starting twice.
    expect(instances).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Dictate a message' }));
    fireEvent.submit(screen.getByRole('form', { name: 'Send a message' }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('requires editing overlong dictation rather than silently truncating or sending it', async () => {
    const instances = installRecognition();
    const user = await startChat();
    await user.click(screen.getByRole('button', { name: 'Dictate a message' }));
    recognize(instances[0], 'x'.repeat(2001));
    expect(screen.getByRole('textbox')).toHaveValue('x'.repeat(2001));
    expect(screen.getByText(/over 2,000 characters/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('retains retry IDs for voice confirmations, disables dictation during retry, and speaks the result once', async () => {
    const instances = installRecognition();
    const { synthesis } = installSynthesis();
    const user = await startChat(conversation({ status: 'confirm', message: 'Confirm the collected details?', collected_data: details }));
    await user.click(screen.getByRole('checkbox', { name: 'Spoken replies' }));
    await user.click(screen.getByRole('button', { name: 'Dictate a message' }));
    recognize(instances[0], 'yes');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fetchMock.mockResolvedValueOnce(http({ detail: 'Please retry the same request.' }, 503));
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByText('Please retry the same request.');
    const original = fetchMock.mock.calls[1][1].body;
    expect(screen.getByRole('button', { name: 'Dictate a message' })).toBeDisabled();
    fetchMock.mockResolvedValueOnce(http(conversation({ status: 'completed', message: 'Your table is confirmed.', collected_data: details, reservation })));
    await user.click(screen.getByRole('button', { name: 'Retry same message' }));
    await screen.findByRole('heading', { name: 'Your table is booked.' });
    expect(fetchMock.mock.calls[2][1].body).toBe(original);
    expect(screen.getAllByText('yes')).toHaveLength(1);
    await waitFor(() => expect(synthesis.speak).toHaveBeenCalledTimes(1));
    await user.type(screen.getByRole('textbox'), 'another draft');
    expect(synthesis.speak).toHaveBeenCalledTimes(1);
  });

  it('supports spoken reply opt-in, Stop speaking, microphone interruption, and disabling playback', async () => {
    const instances = installRecognition();
    const { synthesis } = installSynthesis();
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(http(conversation(), 201));
    render(<App />);
    await user.click(screen.getByRole('checkbox', { name: 'Spoken replies' }));
    await user.click(screen.getByRole('button', { name: 'Start Conversation' }));
    await screen.findByText(conversation().message);
    expect(synthesis.speak).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Stop speaking' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Dictate a message' }));
    expect(synthesis.cancel).toHaveBeenCalledTimes(1);
    act(() => instances[0].onerror({ error: 'aborted' }));
    fetchMock.mockResolvedValueOnce(http(conversation({ message: 'A new assistant reply.' })));
    await user.type(screen.getByRole('textbox'), 'hello{Enter}');
    await screen.findByText('A new assistant reply.');
    expect(synthesis.speak).toHaveBeenCalledTimes(2);
    await user.click(screen.getByRole('button', { name: 'Stop speaking' }));
    expect(screen.getByRole('button', { name: 'Stop speaking' })).toBeDisabled();
    await user.click(screen.getByRole('checkbox', { name: 'Spoken replies' }));
    expect(screen.getByRole('checkbox', { name: 'Spoken replies' })).not.toBeChecked();
  });

  it('new conversation aborts recognition and ignores late transcripts', async () => {
    const instances = installRecognition();
    const user = await startChat();
    await user.click(screen.getByRole('button', { name: 'Dictate a message' }));
    const oldResult = instances[0].onresult;
    const oldEnd = instances[0].onend;
    fetchMock.mockResolvedValueOnce(http(conversation({ session_id: 'fresh-session', message: 'New welcome.' }), 201));
    await user.click(screen.getByRole('button', { name: 'New conversation' }));
    await screen.findByText('New welcome.');
    act(() => { oldResult({ results: [recognitionResult('old booking')] }); oldEnd(); });
    expect(instances[0].abort).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('textbox')).toHaveValue('');
  });
});

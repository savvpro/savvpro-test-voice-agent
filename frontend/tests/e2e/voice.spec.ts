import { expect, test } from '@playwright/test'

test.use({ permissions: ['microphone'], launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } })

test('recorded audio passes through transcription, Python decisions, and spoken replies to a completed claim', async ({ page }) => {
  // Real browser recording and our real API/brain; external STT/TTS are controlled
  // here. A separate live Groq check verifies actual provider transcription.
  await page.addInitScript(() => {
    const replies: string[] = []
    Object.defineProperty(window, '__spokenReplies', { value: replies })
    Object.defineProperty(window, 'speechSynthesis', { value: {
      cancel() {},
      speak(utterance: SpeechSynthesisUtterance) {
        replies.push(utterance.text)
        queueMicrotask(() => utterance.dispatchEvent(new Event('end')))
      },
    } })
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Talk to the assistant' }).click()
  await page.getByRole('button', { name: 'Agree and start microphone' }).click()
  for (let turn = 0; turn < 3; turn++) {
    if (turn > 0) await page.getByRole('button', { name: 'Talk to the assistant' }).click()
    await expect(page.getByRole('button', { name: 'Finish recording' })).toBeVisible()
    // Allow the browser's real audio encoder to collect a short synthetic tone.
    await page.waitForTimeout(400)
    await page.getByRole('button', { name: 'Finish recording' }).click()
    await expect(page.locator('.message.caller')).toHaveCount(turn + 1)
    await expect(page.getByRole('button', { name: 'Talk to the assistant' })).toBeVisible()
  }
  await expect(page.getByText('Pending staff review', { exact: true })).toBeVisible()
  await expect(page.locator('.receipt strong')).toHaveText(/^LF-/)
  const spoken = await page.evaluate(() => (window as unknown as { __spokenReplies: string[] }).__spokenReplies)
  expect(spoken).toHaveLength(3)
  expect(spoken[2]).toContain('Your reference is LF-')
})

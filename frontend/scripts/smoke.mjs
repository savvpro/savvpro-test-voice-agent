import { chromium, expect as baseExpect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

// UI smoke and walkthrough only. Actual microphone speech requires manual Chrome verification.
const baseURL = process.env.SMOKE_URL || 'http://127.0.0.1:8000'
const expect = baseExpect.configure({ timeout: 45000 })
const root = new URL('../../artifacts/', import.meta.url)
await mkdir(root, { recursive: true })
const browser = await chromium.launch({ headless: true })
const errors = []
const context = await browser.newContext({
  viewport: { width: 1440, height: 1100 },
  reducedMotion: 'reduce',
  recordVideo: {
    dir: fileURLToPath(new URL('walkthrough/', root)),
    size: { width: 1440, height: 1100 },
  },
})
const page = await context.newPage()
page.on('pageerror', (error) => errors.push(error.message))

async function send(text, target = page) {
  await target.getByRole('textbox', { name: 'Type your message' }).fill(text)
  const response = target.waitForResponse(
    (response) => response.url().endsWith('/api/turn') && response.request().method() === 'POST',
  )
  await target.getByRole('button', { name: 'Send message', exact: true }).click()
  const result = await response
  expect(result.status()).toBe(200)
  await expect(target.getByRole('button', { name: 'Send message', exact: true })).toBeDisabled()
  return result.json()
}

try {
  await page.goto(baseURL)
  await expect(page.getByText('11:00 AM', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => window.scrollY)).toBe(0)
  await page.screenshot({
    path: fileURLToPath(new URL('reception-desktop.png', root)),
    fullPage: true,
  })
  await page.getByRole('link', { name: /Your appointments/ }).click()
  await expect(page.getByRole('heading', { name: 'Your appointments.' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Reschedule', exact: true })).toBeVisible()
  await page.screenshot({
    path: fileURLToPath(new URL('appointments-desktop.png', root)),
    fullPage: true,
  })
  await page.getByRole('link', { name: 'Reception', exact: true }).click()
  const first = await send('Book a brake inspection for my SUV tomorrow at 2 PM')
  expect(first.trace.validation).toContain('both_bays_occupied')
  await page.locator('.inspector summary').click()
  await expect(page.getByText('both_bays_occupied', { exact: true })).toBeVisible()
  const selected = await send('first one')
  expect(selected.state.phase).toBe('CONFIRMING')
  const confirmed = await send('yes')
  expect(confirmed.trace.action).toBe('booked')
  expect(confirmed.appointments).toHaveLength(2)
  const multiple = await send('reschedule my appointment')
  expect(multiple.state.phase).toBe('SELECTING_APPOINTMENT')
  await send('first one')
  await send('Thursday at 3 PM')
  const moved = await send('yes')
  expect(moved.trace.action).toBe('rescheduled')
  await expect(page.getByRole('status', { name: 'Schedule update' })).toContainText(
    'Appointment rescheduled',
  )
  await page.getByRole('link', { name: /Your appointments/ }).click()
  await expect(page.getByRole('article')).toHaveCount(2)
  await expect(
    page.getByRole('article').filter({ hasText: moved.state.appointment.reference }),
  ).toContainText('3:00 PM')
  await page.screenshot({
    path: fileURLToPath(new URL('appointments-updated-desktop.png', root)),
    fullPage: true,
  })
  const cancelRequest = page.waitForResponse((response) => response.url().endsWith('/api/turn'))
  await page
    .getByRole('article')
    .filter({ hasText: 'Tyre Rotation' })
    .getByRole('button', { name: 'Cancel appointment' })
    .click()
  expect((await cancelRequest).status()).toBe(200)
  await expect(page.getByRole('textbox', { name: 'Type your message' })).toBeVisible()
  const cancelled = await send('yes')
  expect(cancelled.trace.action).toBe('cancelled')
  await expect(page.getByRole('status', { name: 'Schedule update' })).toContainText(
    'Appointment cancelled',
  )
  await page.getByRole('button', { name: /View updated schedule/ }).click()
  await expect(page.getByRole('article')).toHaveCount(1)
  await expect(
    page.getByRole('article').filter({ hasText: cancelled.state.appointment.reference }),
  ).toHaveCount(0)
  await expect(page.locator('.nav-count')).toHaveText('1')
  await page.getByRole('link', { name: 'Reception', exact: true }).click()
  await page.getByRole('button', { name: /Reset demo/ }).click()
  const reset = page.waitForResponse((response) => response.url().endsWith('/api/session/reset'))
  await page.getByRole('button', { name: 'Reset Demo Session', exact: true }).click()
  expect((await reset).status()).toBe(200)
  await expect(page.getByText('11:00 AM', { exact: true })).toBeVisible()

  await page.emulateMedia({ reducedMotion: 'no-preference' })
  const quickReply = page.waitForResponse((response) => response.url().endsWith('/api/turn'))
  await page.getByRole('button', { name: 'What time do you close?' }).click()
  const quickResult = await (await quickReply).json()
  await expect(page.getByRole('heading', { name: 'Conversation', exact: true })).toBeInViewport()
  const reply = page.locator('.message.assistant').last()
  await expect(reply.locator('.sr-only')).toHaveText(quickResult.reply)
  await expect(reply.locator('.revealed-word').last()).toHaveCSS('animation-name', 'reveal-word')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(reply.locator('.revealed-word').last()).toHaveCSS('animation-name', 'none')

  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    deviceScaleFactor: 1,
    reducedMotion: 'reduce',
  })
  const phone = await mobile.newPage()
  phone.on('pageerror', (error) => errors.push(error.message))
  await phone.goto(baseURL)
  await expect(phone.getByText('11:00 AM', { exact: true })).toBeVisible()
  expect(await phone.evaluate(() => window.scrollY)).toBe(0)
  expect(
    await phone.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true)
  await phone.screenshot({
    path: fileURLToPath(new URL('reception-mobile.png', root)),
    fullPage: true,
  })
  await phone.getByRole('link', { name: /Your appointments/ }).click()
  await expect(phone.getByRole('heading', { name: 'Your appointments.' })).toBeVisible()
  expect(
    await phone.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true)
  await phone.screenshot({
    path: fileURLToPath(new URL('appointments-mobile.png', root)),
    fullPage: true,
  })
  const mobileRequest = phone.waitForResponse((response) => response.url().endsWith('/api/turn'))
  await phone.getByRole('button', { name: 'Reschedule', exact: true }).click()
  expect((await mobileRequest).status()).toBe(200)
  await expect(phone.getByRole('textbox', { name: 'Type your message' })).toBeVisible()
  await send('Thursday at 3 PM', phone)
  const mobileConfirmation = phone.waitForResponse((response) =>
    response.url().endsWith('/api/turn'),
  )
  await phone.getByRole('button', { name: 'Confirm appointment', exact: true }).click()
  expect((await mobileConfirmation).status()).toBe(200)
  await expect(phone.getByRole('status', { name: 'Schedule update' })).toContainText(
    'Appointment rescheduled',
  )
  await phone.getByRole('button', { name: /View updated schedule/ }).click()
  await expect(phone.getByRole('article')).toContainText('3:00 PM')
  await phone.screenshot({
    path: fileURLToPath(new URL('appointments-updated-mobile.png', root)),
    fullPage: true,
  })
  expect(
    await phone.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true)
  await mobile.close()
  expect(errors).toEqual([])
  console.log(
    'PASS: booking, alternatives, selection, instant confirmed reschedule/cancellation updates, reset, quick replies, text reveal/reduced motion, desktop/mobile navigation and rendering; no page errors.',
  )
} finally {
  await context.close()
  await browser.close()
}

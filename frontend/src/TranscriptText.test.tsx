import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { TranscriptText } from './TranscriptText'

afterEach(cleanup)

it('preserves exact response text for assistive technology and the visual reveal', () => {
  const text = "Don't cancel it. Move it to 11:30 AM, please."
  const { container } = render(<TranscriptText text={text} animate />)
  expect(screen.getByText(text)).toHaveClass('sr-only')
  expect(container.querySelector('[aria-hidden="true"]')?.textContent).toBe(text)
})

it('shows recognition corrections without retaining an earlier interpretation', () => {
  const { container, rerender } = render(<TranscriptText text="Book an oil change" animate live />)
  rerender(<TranscriptText text="Book a brake inspection" animate live />)
  expect(container.querySelector('[aria-hidden="true"]')?.textContent).toBe(
    'Book a brake inspection',
  )
  expect(container.textContent).not.toContain('oil change')
})

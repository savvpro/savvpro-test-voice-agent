import { expect, it } from 'vitest'
import { pickVoice } from './useSpeech'

const v = (name: string, lang = 'en-US') => ({ name, lang }) as SpeechSynthesisVoice

it('prefers natural/neural voices, then premium, then Google, and stays en-US', () => {
  const fred = v('Fred')
  const google = v('Google US English')
  const premium = v('Ava (Premium)')
  const natural = v('Microsoft Aria Online (Natural) - English (United States)')
  const french = v('Thomas (Natural)', 'fr-FR')
  expect(pickVoice([fred, google, premium, natural, french])).toBe(natural)
  expect(pickVoice([fred, google, premium])).toBe(premium)
  expect(pickVoice([fred, google])).toBe(google)
  expect(pickVoice([fred, french])).toBe(fred)
  expect(pickVoice([french])).toBeUndefined()
  expect(pickVoice([])).toBeUndefined()
})

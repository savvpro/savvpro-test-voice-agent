# Reception surface

- Mode: operate. Caller books, reschedules, and cancels; reviewer sees actual deterministic decisions.
- Approved composition: `.impeccable/mocks/layout-b.png`, selected by the user on 26 October 2026. Top navigation, approximately 65/35 call/appointment split, transcript composer beneath the call stage, quick utterances and decision inspector below.
- User explicitly replaced the visual world on 26 October: black/charcoal surfaces, warm brass gold, coherent SVG identity and favicon, self-hosted Manrope, restrained voice-state motion. Preserve the approved B reception split and actual booking behavior; a dedicated Your appointments view fixes the reported navigation issue, with visible mobile tabs and scoped reschedule/cancel actions. This precise theme/layout brief overrides the concept draw; no new composition choice is pending.
- Do not literalize generated content: all dates, durations, identities, appointment statuses, and state traces come from the real API. No invented customers, locations, vehicles, confidence scores, or confirmations.

| Ingredient | Implementation medium |
| --- | --- |
| Top bar and wordmark | Semantic HTML, CSS, small flat SVG mark |
| Call waveform and microphone | CSS bars driven by voice status; lucide SVG icons |
| Appointment ticket and draft | HTML definition lists backed by API data |
| Transcript and composer | HTML log/form with labels and keyboard support |
| Quick utterances and inspector | Buttons and native details element |
| Desktop/mobile hierarchy | CSS grid becoming a single-column flow |

The comp requires no photographic or illustrated assets. Images remain local reference artifacts; production UI is accessible code.

- Current task: book through voice, typing or service shortcuts; manage all session-owned appointments in a dedicated hash-navigable view. Every change returns to reception for explicit confirmation. No physical metal effects, gradients, glows, fake metrics, or photographic assets.

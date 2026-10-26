---
name: Bayline Service Reception
description: Matte charcoal reception with warm brass actions and explicit appointment review.
colors:
  canvas: "#0b0d10"
  surface: "#121519"
  raised: "#1a1e23"
  ink: "#f1ede4"
  muted: "#a7abae"
  line: "#303338"
  gold: "#dfbd7d"
  gold-hover: "#eccd96"
  gold-tint: "#27241e"
  success: "#a9c5af"
  danger: "#e6a6a2"
typography:
  display:
    fontFamily: "Manrope Variable, Segoe UI, sans-serif"
    fontSize: "clamp(30px, 3vw, 43px)"
    fontWeight: 650
    lineHeight: 1.18
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Manrope Variable, Segoe UI, sans-serif"
    fontSize: "16px"
    fontWeight: 650
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Manrope Variable, Segoe UI, sans-serif"
    fontSize: "15px"
    lineHeight: 1.6
  control:
    fontFamily: "Manrope Variable, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 650
  conversation:
    fontFamily: "Manrope Variable, Segoe UI, sans-serif"
    fontSize: "12px"
    lineHeight: 1.75
rounded:
  control: "8px"
  field: "10px"
  panel: "12px"
  stage: "14px"
spacing:
  compact: "8px"
  control: "12px"
  row: "20px"
  section: "28px"
components:
  button-primary:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.canvas}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "12px 19px"
  button-primary-hover:
    backgroundColor: "{colors.gold-hover}"
  button-secondary:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "12px 19px"
  button-text:
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "10px 3px"
  field-composer:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "5px"
  panel-appointment:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.stage}"
    padding: "25px"
  panel-inspector:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
---

# Design System: Bayline Service Reception

## Overview

**Creative North Star: "The Brass Service Reception"**

Bayline is an operational reception desk expressed in matte charcoal, warm brass, and precise ruled details. The user-requested black-and-gold world supersedes the earlier white/slate/blue theme while retaining the approved reception composition. Its premium character comes from restrained contrast, self-hosted Manrope, generous task spacing, and coherent SVG identity rather than imagery or metallic effects.

Call controls, conversation, and appointment review remain the main experience. A dedicated Your appointments view makes session-owned booking management discoverable; technical evidence stays in an expandable inspector. This record derives from the shipped React components and CSS, not a promise of manual voice or accessibility verification.

**Key Characteristics:**

- Matte charcoal surfaces with warm brass actions and off-white facts.
- Self-hosted variable typography and consistent stroked SVG icons.
- Flat, finely divided working regions and explicit appointment states.
- Visible mobile navigation, typed fallback, and confirmation before changes.

## Colors

The frontmatter records the implemented CSS palette; one warm brand accent sits above a compact dark neutral stack.

### Primary

- **Warm Brass** (`gold`): primary actions, active navigation, service icons, proposed appointment details, and voice-state bars.
- **Light Brass** (`gold-hover`): enabled primary-action hover feedback.
- **Brass Tint** (`gold-tint`): quiet avatar and reset-notice surfaces.

### Neutral

- **Charcoal Canvas** (`canvas`): page and header ground; dark text on brass controls.
- **Reception Surface** (`surface`): call stage, composer, appointment panel, and inspector.
- **Raised Charcoal** (`raised`): secondary controls, count badges, and quiet hover treatment.
- **Warm Ink** (`ink`): headings, appointment facts, and conversation text.
- **Quiet Gray** (`muted`): supporting instructions, metadata, and secondary actions.
- **Ruled Divider** (`line`): panel boundaries and structural separators.

Success and danger are semantic colors, reinforced by labels and icons. Pending proposals use brass; confirmed bookings use muted green. Error/end-call components also use local subdued red surfaces.

**The Brass Action Rule.** Reserve brass for interaction, current proposals, and small status or identity accents; keep large working surfaces charcoal.

## Typography

**Display and body font:** self-hosted Manrope Variable, imported through `@fontsource-variable/manrope`, with local sans fallbacks. References and rule identifiers use the browser's monospace stack.

**Character:** rounded sans letterforms, controlled weight changes, tight display tracking, and tabular appointment numerals. The frontmatter records shared roles; local section headings vary by density.

### Hierarchy

- **Display:** responsive task heading; the narrow layout uses `clamp(30px, 5.7vw, 40px)`.
- **Appointment time:** the reception ticket uses 48px, weight 550, line-height 1.2, and tracking -0.035em; list times use 30px and become 27px below 800px.
- **Title:** compact section headings, with a larger 20px service title in appointment rows.
- **Body and conversation:** use the recorded reading roles; transcript text preserves line breaks and wraps long content.
- **Controls:** consistent medium-weight action labels. The composer input becomes 16px below 440px.

Small annotation text exists in the shipped interface. Do not reuse its smallest sizes as general reading-text defaults.

## Layout

The centered content container has a maximum width of 1352px and 28px desktop gutters. The reception pairs a wider call/conversation column with an appointment column using `minmax(0, 1.9fr) minmax(320px, 1fr)` and a 48px gap. Service shortcuts form three ruled columns before the call stage. The transcript stays within its own scrollable 145px region; new messages scroll that region rather than moving the page.

Quick requests form four ruled columns below the workspace, followed by the native-disclosure decision inspector. The Your appointments view uses divided booking rows containing service, date/time, reference, and management actions. It shares the same header and page shell.

At 1120px, the reception gap narrows to 28px, columns rebalance, and supporting header captions disappear. At 800px, navigation moves onto a visible full-width second row; the reception becomes one column, quick requests become two columns, and booking rows reflow. At 440px, gutters become 18px, quick requests and booking actions become one column, and the composer input grows for mobile use. Above 1600px, the content top padding increases.

**The Task First Rule.** Keep call controls and conversation before appointment details in reading order, and place technical evidence after the caller's task.

## Elevation & Depth

There are no box shadows. Depth comes from the canvas/surface/raised tonal stack, fine borders, and deliberate whitespace. The call stage and appointment panel are bounded working regions; service choices, requests, and appointment lists rely on ruled divisions. No gradients, glows, physical-metal effects, or photographic assets are required by this world.

**The Matte Surface Rule.** Separate regions through tone, spacing, and fine borders rather than ornamental elevation.

## Shapes

Controls and avatars use gently rounded corners; fields, inspector panels, and larger working stages use the frontmatter radius steps. Small circular status dots and the narrow waveform bars are functional exceptions. Lucide provides consistent stroked SVG icons; the local SVG favicon and header mark share the brass monogram identity. Icons supplement visible labels and accessible names.

## Components

### Buttons

Primary actions use brass with canvas-colored text and the shared control radius. Secondary actions use raised charcoal, warm text, and a fine divider border; text actions remain muted until hover. Button/text/icon controls have a minimum height of 44px; icon controls are at least 44px wide. Disabled controls use 45% opacity and a non-interactive cursor. Background and color transitions last 180ms. Shared keyboard focus is a 2px brass outline with 5px offset; the skip link exposes direct access to main content.

### Chips

Quick-request buttons are divided sentence rows with a brass icon, not rounded filter pills. Their group changes from four to two to one column. Service shortcuts are three adjacent ruled buttons with service/duration labels. Both send real utterances through the same pipeline as speech and typing.

### Cards / Containers

Call stage and appointment panel use the surface color, divider border, and stage radius. The appointment panel uses 25px desktop padding, narrowing at smaller breakpoints. Inspector and grouped appointment rows use the panel radius. Appointment facts remain definition-list rows; a proposal, existing booking, and completed change have distinct text and status treatment.

### Inputs / Fields

The composer is a dark bordered enclosure with a flexible input and square brass send control. Focus within shifts the enclosure border to brass. Speech-source and reply-voice selects have explicit labels, a minimum 44px height, dark option surfaces, and SVG chevrons. Type instead focuses the composer as an available alternative to starting a call. Errors and reset confirmation remain inline and recoverable.

### Navigation

Reception and Your appointments are actual hash-navigable views. The active link uses brass text and a thin matching underline; the appointment count is a small raised badge. Mobile retains both destinations in the header's second row. Navigating to appointments pauses voice interaction; management actions return to reception with a specific owned reference for explicit review.

### Voice stage and decision inspector

Confirmed booking changes appear in a flat, divided status row beside the conversation and in the appointments view. It names the actual service, date/time, reference, and committed action, with a View updated schedule action at reception. Keep it tied to the returned server state; never present a proposal as committed or wait for speech to update the schedule.

Fresh conversation text reveals with 180ms word fades and delays capped at 600ms; live recognition changes use 100ms fades. These are visual presentations of actual text, not generated-token streaming. Assistive technology receives the complete text once, and reduced motion disables the reveal. Test-drive chips bring the conversation into view; history remains immediate on session initialization.

The waveform illustrates controller status rather than measured audio amplitude. Bars animate only while listening or speaking; text carries the actual status. Reduced-motion preferences suppress animation and smooth scrolling. The native disclosure shows the actual state, matched rules, entities, validation, action, and revision, with an honest empty state before a request.

## Do's and Don'ts

### Do:

- **Do** use matte charcoal, warm brass, self-hosted Manrope, and coherent SVG icons.
- **Do** retain visible mobile destinations, visible keyboard focus, readable inputs, and 44px primary control targets.
- **Do** distinguish proposals from confirmed appointments and require explicit confirmation.
- **Do** render appointment facts and decision traces from actual session-scoped API data.
- **Do** keep transcript scrolling local and respect reduced-motion preferences.

### Don't:

- **Don't** reintroduce the superseded white/blue theme or generic marketing-page styling.
- **Don't** add gradients, glows, metallic effects, or ornamental panel shadows.
- **Don't** treat illustrative waveform bars as measured audio or invent confidence scores.
- **Don't** infer provider, microphone, hosting, or accessibility-conformance verification from visual source inspection.
- **Don't** collect real contact, registration, or payment information in this fictional simulation.

## Technical appendix: deterministic reception brain

The Python backend makes zero runtime LLM calls for intent detection, extraction, dialogue policy, or response generation. A finite English grammar uses explicit rules and regular expressions to recognize booking, rescheduling, cancellation, service/vehicle synonyms, dates, times, references, and supported ordinal choices. Templates generate replies. Unsupported or ambiguous language produces clarification. Browser recognition is primary; optional Groq Whisper supplies transcription only. Typed text, final speech transcripts, and quick utterances use one turn pipeline.

The explicit state machine moves between `IDLE`, `COLLECTING`, `SELECTING_APPOINTMENT`, `CONFIRMING`, `COMPLETED`, and `ENDED`. Complete, valid, available details lead to a readback; explicit yes commits the proposed change. Editing any appointment detail invalidates confirmation and rechecks the proposal. A yes accompanied by changed details causes a new readback rather than a premature commit. Hours/catalog/help replies preserve the pending task.

Rescheduling and cancellation operate only on appointments owned by the browser's session. When multiple appointments match, the brain asks for a unique selection using supported reference, details, or ordinal choices. Background occupancy is never caller-owned. Dates resolve in Asia/Karachi through an injectable clock; stored instants normalize to UTC. The workshop opens Monday–Saturday 09:00–18:00, with half-hour boundaries, 30- or 60-minute services, and a 14-day horizon.

SQLAlchemy transactions protect two-bay allocation. Every service segment uses the same bay; `UniqueConstraint("bay_id", "segment_start")` enforces occupancy uniqueness. Savepoints and transaction rollback preserve an existing appointment when a reschedule cannot reserve its destination. Cancellation releases the owned allocations atomically. Persisted turn IDs deduplicate requests together with their mutations; expected revisions reject stale turns, including those arriving after a session-scoped reset. Confirmation, state, mutations, and the returned trace are persisted coherently.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the decision policy, database isolation, reset semantics, speech completion/watchdog lifecycle, and deliberate limits. This design record documents source and captured rendering; it does not assert live microphone, Groq, Neon/Postgres, deployment, Docker, or accessibility-conformance verification.

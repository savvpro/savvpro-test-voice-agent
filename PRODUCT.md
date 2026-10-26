# Bayline Service Reception
<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
User-approved: React with TypeScript, FastAPI/Python, SQLAlchemy 2.0, SQLite locally, Neon Postgres in deployment. Render serves frontend and backend together.

## Users
Callers booking fictional vehicle servicing, and technical reviewers evaluating deterministic dialogue decisions.

## Product Purpose
Complete booking, rescheduling, and cancellation through English speech. Reveal the actual rules, extracted details, and actions behind each reply.

## Operating Context
Each browser owns a separate synthetic two-bay workshop and fictional caller Alex Rivera. Cars and SUVs; oil change and tyre rotation take 30 minutes, brake inspection 60 minutes. Open Monday–Saturday 09:00–18:00 Asia/Karachi; 14-day horizon.

## Capabilities and Constraints
No runtime LLM decisions. Browser speech primary, optional Groq Whisper transcription, browser synthesis. Hands-free turn-taking with explicit controls and typed fallback. Seeded appointments, quick utterances, isolated reset. Free hosting and speech services. Midnight PKT assessment deadline on 27 October 2026.

## Brand Commitments
User-requested black-and-gold redesign: charcoal/black surfaces, warm brass-gold actions, a coherent SVG identity/favicon and icons, clear typography, restrained motion, and usable mobile navigation. Reception and Your appointments are distinct navigable views. Keep service selection and booking management easy to discover. Bayline is a fictional demo identity, not a real workshop.

## Evidence on Hand
TASK.md defines the assessment. All workshop identities and bookings are synthetic. Verification results and usage logs must be recorded from actual runs.

## Product Principles
- Confirm before changing a booking.
- Clarify ambiguity rather than invent details.
- Keep the caller's task primary and technical evidence available.
- Make failure recoverable and visible.

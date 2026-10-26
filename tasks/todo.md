# Riverside Lost Property: Task Status

This is the delivery checklist for [plan.md](plan.md). Detailed implementation tasks will be added after design review. Checkboxes describe observed completion, not intended work.

## Planning

- [x] Read TASK.md and README.md and inspect the repository/environment.
- [x] Agree on the lost-property use case and code-owned synonym-aware matching.
- [x] Create candidate-Harris-05 in the existing fork.
- [x] Write proposed DESIGN.md, CONSTRAINTS.md, and delivery roadmap.
- [x] Resolve independent builder review; no blocking gaps reported.
- [x] User reviews the concrete design and proposed defaults.
- [x] Freeze exact implementation interfaces and test-first tasks.

## Delivery

- [ ] Slice 1: Runnable text foundation with initial checks.
- [ ] Slice 2: Explainable matching, extraction, clarification, and correction.
- [ ] Checkpoint A: Review brain behaviour against labeled examples.
- [ ] Slice 3: Durable isolated sessions, transactional turns, and retry safety.
- [ ] Slice 4: Confirmed lost report with durable receipt.
- [ ] Slice 5: Safe pending claim with private identifying details.
- [ ] Checkpoint B: Verify complete typed journeys in a real browser.
- [ ] Slice 6: Real voice lifecycle and typed recovery.
- [ ] Slice 7: Responsive caller experience and safe decision inspector.
- [ ] Slice 8: CI, reproducible operation, documentation, and evidence.
- [ ] Checkpoint C: Full review and assessment requirement audit.

## Required evidence before calling the assessment complete

- [ ] Actual automated test/lint/type/build results.
- [ ] Actual session-isolation, privacy, concurrency, and rollback verification.
- [ ] Actual browser/accessibility/responsive verification.
- [ ] Actual supported-browser microphone and spoken-reply verification.
- [ ] Actual migration, seeding, persistence, and expiry verification.
- [ ] Actual dependency/secret scan results and measured performance/bundle sizes.
- [ ] Complete README.md, DESIGN.md, and AI_USAGE.md.
- [ ] Genuine redacted AI token logs or usage screenshots.
- [ ] Confirm external deadline and open the required pull request.

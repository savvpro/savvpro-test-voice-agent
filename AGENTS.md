# Repository working rules

Read TASK.md, DESIGN.md, and CONSTRAINTS.md before writing code. Do not weaken CONSTRAINTS.md to make a change pass.

The user approved the design and delivery roadmap on 2026-10-26. Their existence alone is not evidence that implementation or checks pass.

Do not create commits, push, or open a pull request. The user explicitly manages commits and submission themselves. Preserve all implementation changes in this checkout.

The caller-facing decision logic must be implemented in Python without an LLM or embedding service. Keep private inventory facts server-side, use fictional data only, and add behavioural tests with each implementation slice.

Work on candidate-Harris-05. Keep the implementation task status in tasks/todo.md and keep setup, design, and AI-usage documentation accurate as work proceeds.

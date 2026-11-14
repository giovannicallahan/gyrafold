# Gyrafold: rules for Claude Code

Gyrafold is a free, static 3D brain-learning web app. The site is `viewer/public/`, served as-is
at https://gyrafold.com from the `gh-pages` branch. No build step, no server, no paid services,
no external requests, no analytics.

## Before changing anything

- Keep it free and self-hosted. Use `textContent`, never `innerHTML` with data.
- Lesson content states only what its cited sources support. Never invent facts.
- The guide, Oron, is a lookup guide and not an AI. Never describe the app as AI-powered.
- UX rule: simple and never overwhelming. Every page has a Home link.
- Saved-progress keys start with `neuroapp.`; do not rename them.
- Do not read or touch `github-recovery-codes.txt` if it is nearby.

## Team

- The main Claude Code session leads and makes the final decision.
- Opus builds; Sonnet and Haiku take the smaller pieces. A separate agent reviews before shipping.
- IBM Bob joins on large projects: a new Bob chat at 13 coins, his edits approved one at a time.
- A single agent is enough when the task is menial. The goal is efficiency, not waste.

## AI collaboration rules (Codex / Astra)

When a task is complicated, use Codex for a second opinion.

For important technical decisions:

1. Ask Codex for an independent opinion (`/codex:rescue`, or `/codex:adversarial-review` on a plan).
2. Review the advice.
3. Make the final decision.
4. Implement the change.
5. Use Codex to review the final changes (`/codex:review`).
6. Fix valid problems found by the review.
7. Run the tests before finishing.

Do not use Codex for every small task. Hand it bounded work with exact files and a stopping
point. The main Claude Code session remains responsible for the final decision, and checks
anything Codex reports before acting on it.

## Tests and deploy

- Tests: `python3 scripts/tests/test_nav.py`, `test_neuron.py`, `test_imaging.py`, `test_pwa.py`,
  and `validate_content.py <file>`. The atlas tests are slow; run them one at a time.
- Before deploying, change `VERSION` at the top of `viewer/public/sw.js`.
- Deploy: see "Deploying the demo" in `README.md`.

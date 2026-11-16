# Tier 10: rules every builder follows

- Static site in `viewer/public/`. No build step, no server, no external requests, no analytics, CSP unchanged.
- `textContent` only; never `innerHTML` with data. Saved-progress keys start with `neuroapp.`; never rename existing ones.
- Never invent neuroscience facts. Lesson text may only come from `viewer/public/content/*.json`. Oron is a lookup guide; never say AI.
- UX rule: simple, never overwhelming. New things are optional, off or collapsed by default, one idea per view. Phones first (390x844): touch targets >= 44px, nothing hidden behind the sheet (body[data-sheet] read/split/model, see docs/tasks/tier9-phone-reading-room.md). Desktop layout must not regress.
- Respect `prefers-reduced-motion`. Keyboard reachable, visible focus, aria labels.
- Work ONLY in your own worktree and ONLY in the files your brief names. Do not touch sw.js, CLAUDE.md, or other pages. Do not push. Commit to your branch when done (one commit).
- Browser checks: the machine renders in software and is shared. Wrap EVERY browser run in `flock /tmp/browser.lock <cmd>`, serve your own worktree on your own port (given in the brief), keep each run under 6 minutes, and do not run the big suites in scripts/tests (the lead runs those). The atlas page takes 1-2 minutes to load; see `ready()` and ARGS in scripts/tests/test_nav.py for how to launch Chrome and wait.
- Do not spawn further agents. Finish with a report under 250 words: what you built, where (file:line), what you verified and how, what is unverified, any decision the lead should know.

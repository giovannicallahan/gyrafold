# Tier 8: imaging page becomes tabbed, one topic per view

Owner's feedback (verbatim): "The scrolling to the next topic is tedious it should be one page,
they can choose to maneuver to the next via a tab at the top and or a next button at the bottom.
The option to go to another page should always be visible."

File: `viewer/public/imaging.html` (static, single file, inline CSS/JS, content from
`content/imaging.json`). Read `CLAUDE.md` first. Do NOT commit, push or deploy.

## What to build

1. **One topic per view.** Today the page is one long scroll: opening, families, trade-off chart,
   methods one by one, EEG explorer, quiz, glossary, sources. Turn the top-level topics into
   views; only one shows at a time. Suggested tabs (rename for plain language, keep it to 7 or
   fewer): Overview (opening + two families), Compare (trade-off chart), Methods, EEG explorer,
   Quiz, Glossary, Sources.
2. **Methods: one method at a time.** Inside Methods, show a single method (MRI, DTI, CT, fMRI,
   PET, EEG, MEG) with a small always-visible picker (the existing chips can become this) and
   Previous/Next method buttons. No long stack of seven cards.
3. **Tab bar always visible.** A sticky tab bar directly under the existing sticky top bar
   (which keeps Home / Whole brain / Neuron / Imaging). On phones the tab bar scrolls
   horizontally, shows the active tab, and scrolls the active tab into view. It must never be
   covered or scrolled away.
4. **Previous / Next at the bottom of every view**, labelled with the destination
   ("Next: Compare"). On the last method, Next goes to the next tab. On the last tab there is no
   Next; offer the existing "Keep exploring" links instead.
5. Changing view scrolls to the top of the content and moves focus sensibly.

## Must keep working

- Deep links: `imaging.html#m-<id>` (the welcome page's guide Oron links to these) must open the
  Methods view on that method. Give each tab its own hash too (`#compare`, `#quiz`, ...), update
  the hash on change with `history.pushState` so browser Back steps through views, and handle
  `hashchange`/`popstate`.
- Any existing in-page links (chart points → method, quiz feedback → method, glossary, source
  citations → Sources) must switch to the right view and land on the target.
- No-JS and failed-JSON fallback: everything visible as one page, as today (hide views only
  under a JS-set class).
- Accessibility: real `role="tablist"`/`tab`/`tabpanel` with arrow-key movement, `aria-selected`,
  visible focus, 44px tap targets on phones, `prefers-reduced-motion` respected.
- CSP unchanged, no external requests, `textContent` only, saved-progress keys unchanged.
- Visual style stays as is. UX rule: simple, never overwhelming.

## Tests

- Update `scripts/tests/test_imaging.py` (currently 145 checks, Playwright, see how it launches
  Chrome) for the new structure and add checks for: one view visible at a time; tab bar visible
  after scrolling at 1366x800 and 390x844; Next/Previous on every view; method picker and
  method Next; `#m-fmri` deep link; every tab hash; browser Back; keyboard arrows on tabs; no
  horizontal page scroll at 390px; no console errors; no external requests.
- Run `test_pwa.py` afterwards (slow, about 8 minutes; foreground, long timeout) since it loads
  imaging.html offline. Take screenshots at both sizes and look at them before reporting.
- Bump `VERSION` in `viewer/public/sw.js` to "2026-11-15.1".

## Report

Under 300 words: what changed, tab names chosen, test counts, anything unverified, judgment calls.

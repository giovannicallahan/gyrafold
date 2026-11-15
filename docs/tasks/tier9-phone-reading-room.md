# Tier 9: more room to read on phones (neuron page and brain atlas)

Owner's feedback, on his phone (verbatim): "The scroll is restricted to only the bottom, people
need more space to read and peruse the options." / "When I am on the neuron page" / "And the
brain side as well" / "All of the options are at bottom of screen".

Files: `viewer/public/neuron.html` and `viewer/public/atlas-viewer.html`. Read `CLAUDE.md` first.
Do NOT commit, push or deploy. Desktop layouts (wider than 760px) must not change.

## The problem (measured at 390x844 on neuron.html)

The 3D stage is fixed at the top and takes 50-464px. The panel is fixed below it (464-844) and,
after the level/search row, the tab row and the footer line, the only scrolling reading area is
about 230px tall (570-801). The atlas has the same shape: a 3D view with a bottom sheet. People
can only read and choose in a small strip at the bottom of the screen.

## What to build (phones only, max-width 760px)

1. **Reading gets most of the screen by default.** Default split: the 3D view about 34% of the
   height, the panel the rest, so the scrolling reading area is at least 55% of the viewport
   height. The model must re-frame itself to stay fully visible and centred in the smaller
   stage (renderer and camera resize; labels still readable).
2. **One obvious size control at the top edge of the panel**: a 44px-tall handle/button row that
   cycles or drags between three sizes, with plain labels:
   - "Read" (panel about 88% of the height; the 3D view is a short strip or hidden),
   - "Split" (the default above),
   - "Model" (panel collapsed to a peek showing its title and the tabs; the 3D view large).
   Tapping works; dragging the handle is a bonus if it is reliable. Announce state to screen
   readers (`aria-expanded` or a labelled button group). Remember the choice for the session
   (sessionStorage; never rename the `neuroapp.*` localStorage keys).
3. **Options first.** In the panel, the tabs/options row sits at the top, directly under the
   handle, and stays pinned while the content scrolls. Fold the level switch and search into the
   scrolling content or a compact single row so they do not eat reading height. Move the
   "Educational use only; not medical advice. Sources" footer line into the end of the
   scrolling content on phones (it must remain reachable on every tab).
4. **The whole panel body scrolls**, with momentum scrolling and `overscroll-behavior: contain`,
   and the last item is not hidden behind the phone's home bar (`env(safe-area-inset-bottom)`).
5. **Tapping a part of the model** (neuron) or a structure (atlas) while in "Model" size brings
   the panel back to "Split" so the explanation is visible. Starting a quiz or tour must still
   work in every size; if a quiz needs the model, use "Split".
6. Atlas specifics: it already has a bottom sheet with three heights. Rework it to the same
   three named sizes and the same handle, so both pages behave identically. The floating
   Home / Back / Reset view buttons (`#nav-float`) must stay visible and uncovered in "Split"
   and "Model"; in "Read" they may sit in the strip or the sheet header, but Home must always
   be reachable. Neuron specifics: keep the Biological/Artificial switch and Reset view / Labels
   / Look inside reachable in "Split" and "Model" without covering the model.

UX rule from the owner: simple, never overwhelming; the way to another page is always visible.

## Tests

- Update `scripts/tests/test_neuron.py` (78 checks) and `scripts/tests/test_nav.py` (20 checks)
  where the phone layout changed, and add phone checks for both pages at 390x844 and 360x740:
  default reading area >= 55% of viewport height; "Read" >= 80%; "Model" leaves the 3D view
  >= 60%; the handle and tabs are >= 44px tall and visible in every size; the content scrolls to
  its last element; tapping the model in "Model" size returns to "Split"; the model's bounding
  box stays inside the visible stage in "Split"; Home always reachable; no horizontal scroll; no
  console errors; desktop 1366x800 layout unchanged (compare key element boxes before/after).
- The atlas loads slowly under swiftshader (1 to 2 minutes; see `test_nav.py` for how to wait).
  Run slow tests in the foreground, one at a time, with long timeouts. Leave no servers running.
- Take phone screenshots of both pages in all three sizes and look at them before reporting.
- Bump `VERSION` in `viewer/public/sw.js` to "2026-11-15.4".

## Report

Under 300 words: what changed on each page, test counts, anything unverified, judgment calls.

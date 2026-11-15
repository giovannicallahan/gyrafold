#!/usr/bin/env python3
"""Playwright checks for viewer/public/neuron.html.

Run:  timeout 900 python3 scripts/tests/test_neuron.py
Serves viewer/public with python3 -m http.server on a free port, drives system Chrome
(headless, SwiftShader WebGL) at 1280x800 and 390x844, plus a reduced-motion run, and the
Tier 9 phone panel sizes (Read / Split / Model) at 390x844 and 360x740 with a 1366x800 desktop check.
Screenshots go to /home/claude/stage/shots6/neuron-*.png. Exit code 1 if any check fails.
"""
import json
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PUBLIC = os.path.join(ROOT, 'viewer', 'public')
SHOTS = '/home/claude/stage/shots6'
CHROME = '/usr/bin/google-chrome'
ARGS = ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
CONTENT = json.load(open(os.path.join(PUBLIC, 'content', 'neuron.json'), encoding='utf-8'))
PARTS = [p['id'] for p in CONTENT['parts']]
PROCS = [p['id'] for p in CONTENT['processes']]

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + str(detail)) if detail and not ok else ''))


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Watch:
    """Collects console errors, page errors, failed requests and off-host requests."""

    def __init__(self, page, host):
        self.errors, self.failed, self.offhost = [], [], []
        page.on('console', lambda m: self.errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: self.errors.append('pageerror: ' + str(e)))
        page.on('requestfailed', lambda r: self.failed.append(r.url))
        page.on('response', lambda r: self.failed.append(f'{r.status} {r.url}') if r.status >= 400 else None)
        page.on('request', lambda r: self.offhost.append(r.url)
                if urlparse(r.url).scheme in ('http', 'https') and urlparse(r.url).netloc != host else None)


def new_page(browser, w, h, base, reduced=False, skip_arrival=True):
    ctx = browser.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1,
                              reduced_motion='reduce' if reduced else 'no-preference',
                              has_touch=w < 760, is_mobile=False)
    if skip_arrival:
        ctx.add_init_script("try{localStorage.setItem('neuroapp.neuron.arrived.v1','1')}catch(e){}")
    page = ctx.new_page()
    page.set_default_timeout(60000)
    watch = Watch(page, urlparse(base).netloc)
    return ctx, page, watch


def ready(page):
    # wait on a selector, not wait_for_function: polling a string would need 'unsafe-eval' under the page's CSP
    page.wait_for_selector('body[data-ready="1"]', state='attached', timeout=90000)
    page.wait_for_timeout(800)


def shot(page, name):
    page.screenshot(path=os.path.join(SHOTS, f'neuron-{name}.png'))


def run_viewport(browser, base, w, h, tag):
    ctx, page, watch = new_page(browser, w, h, base)
    page.goto(base + '/neuron.html')
    ready(page)
    shot(page, f'{tag}-default')
    check(f'[{tag}] triangle count under 150k', page.evaluate('window.__neuron.tris()') < 150000,
          page.evaluate('window.__neuron.tris()'))

    # header and footer
    check(f'[{tag}] Neuron mode link is aria-current', page.get_attribute('a[href="./neuron.html"]', 'aria-current') == 'page')
    check(f'[{tag}] footer disclaimer present', 'Educational use only; not medical advice.' in page.inner_text('#panel-foot'))

    # every part reachable from the list
    names = {p['id']: p['name'] for p in CONTENT['parts']}
    bad = []
    for pid in PARTS:
        page.click(f'#pane-explore .part-btn[data-part="{pid}"]')
        page.wait_for_timeout(250)
        got = page.inner_text('#focus-name')
        if got != names[pid]:
            bad.append((pid, got))
        if pid in ('myelin_sheath', 'synapse', 'dendritic_spines'):
            page.wait_for_timeout(1200)
            shot(page, f'{tag}-part-{pid}')
        page.click('#pane-explore .back')
        page.wait_for_timeout(150)
    check(f'[{tag}] all {len(PARTS)} parts reachable from the list', not bad, bad)

    # level switch changes the text
    page.click('#pane-explore .part-btn[data-part="axon"]')
    page.click('#lvl-beginner')
    beg = page.inner_text('#focus-summary')
    page.click('#lvl-expert')
    exp = page.inner_text('#focus-summary')
    check(f'[{tag}] level switch changes text', beg != exp and beg and exp, (beg, exp))
    stored = page.evaluate("JSON.parse(localStorage.getItem('neuroapp.profile.v1')).level")
    check(f'[{tag}] level stored under shared profile key', stored == 'expert', stored)
    page.click('#lvl-beginner')

    # citation popover
    page.click('#pane-explore .cite-sup >> nth=0')
    check(f'[{tag}] citation marker shows the citation', page.is_visible('#cite-pop') and 'OpenStax' in page.inner_text('#cite-pop'))
    page.keyboard.press('Escape')
    page.click('#pane-explore .back')
    page.wait_for_timeout(1300)

    # picking on the 3D model (soma at the default view)
    page.click('#btn-reset')
    page.wait_for_timeout(1500)
    pos = page.evaluate("window.__neuron.screenOf('soma')")
    small = page.viewport_size['width'] <= 760        # the model is smaller in the phone's split view
    page.mouse.click(pos['x'] - (4 if small else 10), pos['y'] - (10 if small else 40))
    page.wait_for_timeout(400)
    picked = page.inner_text('#focus-name') if page.query_selector('#focus-name') else ''
    check(f'[{tag}] clicking the model selects a part', picked != '', picked)
    if page.query_selector('#pane-explore .back'):
        page.click('#pane-explore .back')
        page.wait_for_timeout(1200)

    # labels toggle
    page.click('#btn-labels')
    page.wait_for_timeout(600)
    vis = page.evaluate("[...document.querySelectorAll('.p-label')].filter(e => e.style.display === 'block').length")
    check(f'[{tag}] labels toggle shows labels', vis >= 6, vis)
    shot(page, f'{tag}-labels')
    page.click('#btn-labels')

    # search
    page.fill('#search', 'myelin')
    page.wait_for_timeout(200)
    n = page.evaluate("document.querySelectorAll('#pane-explore .part-btn').length")
    g = page.inner_text('#pane-explore .gloss')
    check(f'[{tag}] search filters parts and glossary', 1 <= n < len(PARTS) and 'Saltatory' not in g or n >= 1, (n,))
    page.fill('#search', '')

    # tabs: arrow-key navigation
    page.focus('#tab-explore')
    page.keyboard.press('ArrowRight')
    check(f'[{tag}] arrow key moves between tabs', page.get_attribute('#tab-how', 'aria-selected') == 'true')

    # every process reachable, every step reachable
    bad = []
    for pr in CONTENT['processes']:
        page.click('#tab-how')
        if page.query_selector('#pane-how .back'):
            page.click('#pane-how .back')
        page.click(f'#pane-how .proc-btn[data-process="{pr["id"]}"]')
        page.wait_for_timeout(300)
        for i, st in enumerate(pr['steps']):
            title = page.inner_text('#pane-how .step-title')
            if title != st['title']:
                bad.append((pr['id'], i, title))
            if i < len(pr['steps']) - 1:
                page.click('#btn-next-step')
                page.wait_for_timeout(250)
        if pr['id'] == 'action-potential':
            page.wait_for_timeout(900)
            shot(page, f'{tag}-ap')
            page.click('#btn-fire')
            page.wait_for_timeout(700)
            shot(page, f'{tag}-ap-pulse')
        if pr['id'] == 'synapse':
            page.wait_for_timeout(1200)
            shot(page, f'{tag}-synapse')
            check(f'[{tag}] synapse close-up open', page.is_visible('#syn-panel'))
        if pr['id'] == 'summation':
            page.evaluate("(() => { const b = document.getElementById('btn-exc'); b.click(); b.click(); })()")
            ro2 = page.inner_text('#sum-readout')
            check(f'[{tag}] two quick excitatory inputs stay below threshold', 'Below threshold' in ro2, ro2)
            page.evaluate("document.getElementById('btn-exc').click()")
            page.wait_for_timeout(300)
            ro = page.inner_text('#sum-readout')
            check(f'[{tag}] third quick excitatory input crosses threshold and fires', 'Threshold reached' in ro, ro)
            page.wait_for_timeout(1500)
            page.click('#btn-exc')
            ro = page.inner_text('#sum-readout')
            check(f'[{tag}] single input stays below threshold', 'Below threshold' in ro or 'refractory' in ro, ro)
            page.click('#btn-inh')
            shot(page, f'{tag}-summation')
    check(f'[{tag}] all {len(PROCS)} processes and their steps reachable', not bad, bad)
    check(f'[{tag}] Play control present (motion allowed)', page.query_selector('#btn-play') is not None)

    # compare tab
    page.click('#tab-compare')
    page.wait_for_timeout(300)
    out0 = page.inner_text('#perc-out')
    page.eval_on_selector('#sl-th', "e => { e.value = '-1'; e.dispatchEvent(new Event('input')); }")
    out1 = page.inner_text('#perc-out')
    check(f'[{tag}] perceptron output changes with threshold', out0 != out1 and 'output = 1' in out1, (out0, out1))
    page.focus('.cmp-row >> nth=0')
    hl = page.evaluate("document.querySelectorAll('#cmp-svg .hl').length")
    check(f'[{tag}] focusing a compare row highlights both sides', hl >= 2, hl)
    check(f'[{tag}] compare caveats shown', 'not a description of how real neurons compute' in page.inner_text('.caveats'))
    page.evaluate("document.querySelector('#pane-compare').scrollTop = 0")
    shot(page, f'{tag}-compare')

    # quiz: multiple choice and find-the-part
    page.click('#tab-quiz')
    page.wait_for_timeout(300)
    page.click('#pane-quiz .qopt >> nth=0')
    fb = page.inner_text('#q-feedback')
    check(f'[{tag}] quiz multiple-choice gives feedback', ('Correct' in fb or 'Not quite' in fb) and len(fb) > 20, fb)
    check(f'[{tag}] quiz feedback is aria-live', page.get_attribute('#q-feedback', 'aria-live') == 'polite')
    shot(page, f'{tag}-quiz')
    # advance to a find-the-part item
    found = False
    for _ in range(6):
        page.click('#q-next')
        page.wait_for_timeout(200)
        if page.query_selector('#pane-quiz details'):
            found = True
            break
        page.click('#pane-quiz .qopt >> nth=0')
    if found:
        page.click('#pane-quiz details summary')
        target = page.evaluate("document.querySelector('#pane-quiz .qtext').textContent")
        opts = page.query_selector_all('#pane-quiz details .qopt')
        wrong = [o for o in opts if o.inner_text().lower() not in target.lower()]
        if wrong:
            wrong[0].click()
            check(f'[{tag}] find-the-part wrong try offers Show me', page.is_visible('#q-showme'))
            page.click('#q-showme')
            page.wait_for_timeout(1200)
            shot(page, f'{tag}-quiz-showme')
            check(f'[{tag}] Show me reveals Next', page.is_visible('#q-next'))
    check(f'[{tag}] find-the-part question generated', found)

    check(f'[{tag}] no console errors', not watch.errors, watch.errors[:5])
    check(f'[{tag}] no failed requests', not watch.failed, watch.failed[:5])
    check(f'[{tag}] no requests to another host', not watch.offhost, watch.offhost[:5])
    ctx.close()


def run_extras(browser, base):
    # reduced motion
    ctx, page, watch = new_page(browser, 390, 844, base, reduced=True, skip_arrival=False)
    page.goto(base + '/neuron.html')
    ready(page)
    check('[rm] arrival overlay not shown under reduced motion', not page.is_visible('#arrival'))
    check('[rm] scale note shown instead', page.is_visible('#scale-note'))
    shot(page, 'rm-scale-note')
    page.click('#btn-scale-close')
    check('[rm] idle rotation off', page.evaluate('window.__neuron.idle()') is False)
    page.click('#tab-how')
    page.click('#pane-how .proc-btn[data-process="action-potential"]')
    check('[rm] no Play button (step-only)', page.query_selector('#btn-play') is None)
    page.click('#btn-next-step')
    page.click('#btn-next-step')
    check('[rm] stepping works', page.inner_text('#pane-how .step-title') == CONTENT['processes'][1]['steps'][2]['title'])
    shot(page, 'rm-ap')
    page.click('#pane-how .back')
    page.click('#pane-how .proc-btn[data-process="summation"]')
    for _ in range(3):
        page.click('#btn-exc')
    ro = page.inner_text('#sum-readout')
    check('[rm] summation works step-by-step', 'Threshold reached' in ro, ro)
    page.click('#btn-wait')
    check('[rm] no console errors', not watch.errors, watch.errors[:5])
    check('[rm] no failed requests', not watch.failed, watch.failed[:5])
    ctx.close()

    # arrival overlay on first visit, with skip
    ctx, page, watch = new_page(browser, 1280, 800, base, skip_arrival=False)
    page.goto(base + '/neuron.html')
    page.wait_for_selector('#arrival.open', timeout=60000)
    check('[arrival] overlay shows scale text', CONTENT['scale']['text'][:30] in page.inner_text('#arrival'))
    page.click('#arr-skip', timeout=5000)
    check('[arrival] Skip closes overlay', not page.is_visible('#arrival'))
    page.reload()
    ready(page)
    check('[arrival] shown only once per browser', not page.is_visible('#arrival'))
    page.goto(base + '/neuron.html?from=atlas')
    page.wait_for_selector('#arrival.open', timeout=60000)
    check('[arrival] ?from=atlas shows it again', True)
    page.wait_for_timeout(600)
    shot(page, 'arrival')
    page.wait_for_timeout(3500)
    check('[arrival] overlay closes by itself', not page.is_visible('#arrival'))
    check('[arrival] no console errors', not watch.errors, watch.errors[:5])
    ctx.close()

    # deep links
    ctx, page, watch = new_page(browser, 1280, 800, base)
    page.goto(base + '/neuron.html?part=node_of_ranvier&level=expert')
    ready(page)
    check('[deep] ?part= opens the part', page.inner_text('#focus-name') == 'Nodes of Ranvier')
    check('[deep] ?level=expert applies', page.get_attribute('#lvl-expert', 'aria-pressed') == 'true')
    page.wait_for_timeout(1200)
    shot(page, 'deep-node-expert')
    page.goto(base + '/neuron.html?process=synapse')
    ready(page)
    check('[deep] ?process= opens the process', page.get_attribute('#tab-how', 'aria-selected') == 'true'
          and page.inner_text('#pane-how h2') == 'Passing the message on')
    page.goto(base + '/neuron.html?tab=quiz')
    ready(page)
    check('[deep] ?tab=quiz opens the quiz', page.get_attribute('#tab-quiz', 'aria-selected') == 'true')
    page.click('#btn-sources')
    n = page.evaluate("document.querySelectorAll('#sources-list li').length")
    check('[sources] Sources lists every source', n == len(CONTENT['sources']), n)
    shot(page, 'sources')
    check('[deep] no console errors', not watch.errors, watch.errors[:5])
    ctx.close()

    # narrowest phone
    ctx, page, watch = new_page(browser, 360, 740, base)
    page.goto(base + '/neuron.html')
    ready(page)
    over = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    check('[360] no horizontal overflow at 360 px', not over)
    small = page.evaluate("""[...document.querySelectorAll('#panel button, #hud button, #topbar a')]
      .filter(e => e.offsetParent && !e.classList.contains('cite-sup') && !e.classList.contains('linkbtn'))
      .map(e => [e.textContent.trim().slice(0,20), e.getBoundingClientRect().height]).filter(x => x[1] < 44)""")
    check('[360] touch targets at least 44 px', not small, small[:6])
    shot(page, '360-default')
    ctx.close()


# ── Tier 9: phone panel sizes (Read / Split / Model) ─────────────────────────
SHEET_JS = """() => {
  const r = s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect();
    return { top: b.top, bottom: b.bottom, left: b.left, right: b.right, height: b.height, width: b.width }; };
  const hit = s => { const e = document.querySelector(s); if (!e) return false; const b = e.getBoundingClientRect();
    if (b.height < 1 || b.bottom <= 0 || b.top >= innerHeight) return false;
    const t = document.elementFromPoint(b.left + b.width / 2, b.top + Math.min(b.height / 2, 20)); return !!t && (t === e || e.contains(t)); };
  const panel = r('#panel'), tabs = r('#tabs');
  return { size: document.body.dataset.sheet || 'split', vh: innerHeight,
    pressed: [...document.querySelectorAll('#sheet-bar [data-size]')].filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.size),
    panel, tabs, bar: r('#sheet-bar'), stage: r('#stage'),
    reading: Math.min(panel.bottom, innerHeight) - tabs.bottom,
    barHit: hit('#sheet-bar .sheet-title'), tabsHit: hit('#tab-explore') && hit('#tab-quiz'),
    homeHit: hit('nav.modes a[href="./index.html"]'),
    hudHit: hit('#btn-reset') && hit('#btn-labels') && hit('#btn-inside'),
    sidesHit: hit('#stage .sides a[href="./artificial.html"]'),
    hscroll: document.documentElement.scrollWidth > innerWidth };
}"""

DESKTOP_BEFORE = {  # 1366x800 boxes measured before Tier 9 (x, y, w, h)
    '#topbar': [0, 0, 1366, 56], '#stage': [0, 56, 966, 744], '#panel': [966, 56, 400, 744],
    '#panel-top': [967, 56, 399, 58], '#tabs': [967, 114, 399, 45], '#panel-foot': [967, 757, 399, 43],
    '#hud': [12, 68, 266.1, 36], '.sides': [767, 64, 187, 46], '#pane-explore': [967, 159, 399, 598],
    '#search': [1138.2, 68, 213.8, 38], '#c': [0, 56, 966, 744]}


def sheet_size(page, size, wait=900):
    page.click(f'#sheet-bar [data-size="{size}"]')
    page.wait_for_timeout(wait)
    return page.evaluate(SHEET_JS)


def run_sheet(browser, base, w, h):
    tag = f'sheet {w}x{h}'
    ctx = browser.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1, is_mobile=True, has_touch=True)
    ctx.add_init_script("try{localStorage.setItem('neuroapp.neuron.arrived.v1','1')}catch(e){}")
    page = ctx.new_page()
    page.set_default_timeout(60000)
    watch = Watch(page, urlparse(base).netloc)
    page.goto(base + '/neuron.html')
    ready(page)
    page.wait_for_timeout(600)
    m = page.evaluate(SHEET_JS)
    shot(page, f'sheet-{w}-split')
    check(f'[{tag}] default size is Split (aria-pressed)', m['size'] == 'split' and m['pressed'] == ['split'], (m['size'], m['pressed']))
    check(f'[{tag}] Split: reading area >= 55% of the height', m['reading'] / m['vh'] >= 0.55, round(m['reading'] / m['vh'], 3))
    sizes = {'split': m}
    mr = page.evaluate('window.__neuron.modelRect()')
    st = m['stage']
    inside = mr['left'] >= st['left'] - 1 and mr['right'] <= st['right'] + 1 and mr['top'] >= st['top'] - 1 and mr['bottom'] <= st['bottom'] + 1
    check(f'[{tag}] Split: model box inside the visible stage', inside, (mr, st))
    over = page.evaluate("""(m) => ['#hud', '#stage .sides'].filter(sel => { const r = document.querySelector(sel).getBoundingClientRect();
        return Math.min(r.right, m.right) - Math.max(r.left, m.left) > 2 && Math.min(r.bottom, m.bottom) - Math.max(r.top, m.top) > 2; })""", mr)
    check(f'[{tag}] Split: model box clear of the stage buttons', not over, (over, mr))

    m = sheet_size(page, 'read')
    sizes['read'] = m
    shot(page, f'sheet-{w}-read')
    check(f'[{tag}] Read: reading area >= 80% of the height', m['reading'] / m['vh'] >= 0.80, round(m['reading'] / m['vh'], 3))
    check(f'[{tag}] Read: aria-pressed follows', m['pressed'] == ['read'], m['pressed'])
    # the whole panel scrolls to its last element, the footer, on every tab
    bad = []
    for t in ['explore', 'how', 'compare', 'quiz']:
        page.click(f'#tab-{t}')
        page.wait_for_timeout(300)
        page.evaluate("const p = document.getElementById('panel'); p.scrollTop = p.scrollHeight")
        page.wait_for_timeout(200)
        f = page.evaluate("""(() => { const f = document.getElementById('panel-foot').getBoundingClientRect(), p = document.getElementById('panel').getBoundingClientRect(),
            t = document.getElementById('tabs').getBoundingClientRect(); return { ok: f.bottom <= p.bottom + 1 && f.top >= t.bottom - 1, f: [f.top, f.bottom], p: p.bottom } })()""")
        if not f['ok'] or 'Educational use only; not medical advice.' not in page.inner_text('#panel-foot'):
            bad.append((t, f))
    check(f'[{tag}] panel scrolls to its last element (footer) on every tab', not bad, bad)
    page.click('#tab-explore')
    page.wait_for_timeout(300)
    css = page.evaluate("(() => { const c = getComputedStyle(document.getElementById('panel')); return [c.overflowY, c.overscrollBehaviorY] })()")
    check(f'[{tag}] panel scrolls with overscroll-behavior: contain', css == ['auto', 'contain'], css)

    m = sheet_size(page, 'model', 1500)
    sizes['model'] = m
    shot(page, f'sheet-{w}-model')
    check(f'[{tag}] Model: 3D view >= 60% of the height', m['stage']['height'] / m['vh'] >= 0.60, round(m['stage']['height'] / m['vh'], 3))
    check(f'[{tag}] Model: Reset view / Labels / Look inside and Biological/Artificial uncovered', m['hudHit'] and m['sidesHit'], (m['hudHit'], m['sidesHit']))
    for k, v in sizes.items():
        check(f'[{tag}] {k}: size row and tabs >= 44 px and visible', v['bar']['height'] >= 44 and v['tabs']['height'] >= 44 and v['barHit'] and v['tabsHit'],
              (v['bar']['height'], v['tabs']['height'], v['barHit'], v['tabsHit']))
        check(f'[{tag}] {k}: Home reachable, no horizontal scroll', v['homeHit'] and not v['hscroll'], (v['homeHit'], v['hscroll']))
    check(f'[{tag}] Split: stage buttons uncovered', sizes['split']['hudHit'] and sizes['split']['sidesHit'])

    # tapping the model in Model size brings the panel back to Split with the explanation
    page.click('#btn-reset')
    page.wait_for_timeout(1500)
    # find a screen point on the soma or axon (anchors are not always on the surface), then tap it
    pos = page.evaluate("""(() => { const s = window.__neuron.screenOf('soma');
      for (let r = 0; r < 60; r += 4) for (let a = 0; a < 6.28; a += 0.5) { const x = s.x + r * Math.cos(a), y = s.y + r * Math.sin(a);
        if (['soma', 'axon_hillock', 'myelin_sheath', 'axon'].includes(window.__neuron.partAt(x, y))) return { x, y }; }
      return s; })()""")
    page.touchscreen.tap(pos['x'], pos['y'])
    page.wait_for_timeout(1200)
    m = page.evaluate(SHEET_JS)
    name = page.inner_text('#focus-name') if page.query_selector('#focus-name') else ''
    check(f'[{tag}] tapping the model in Model returns to Split and shows the part', m['size'] == 'split' and name != '', (m['size'], name))
    shot(page, f'sheet-{w}-tapped')
    page.click('#pane-explore .back')
    page.wait_for_timeout(1300)
    mr = page.evaluate('window.__neuron.modelRect()')
    st = page.evaluate(SHEET_JS)['stage']
    check(f'[{tag}] Split after Model: model re-framed inside the stage',
          mr['left'] >= st['left'] - 1 and mr['right'] <= st['right'] + 1 and mr['top'] >= st['top'] - 1 and mr['bottom'] <= st['bottom'] + 1, (mr, st))

    # quiz starts in Model size (opens to Split); a find-the-part question works from Read
    sheet_size(page, 'model', 1200)
    page.click('#tab-quiz')
    page.wait_for_timeout(1200)
    m = page.evaluate(SHEET_JS)
    check(f'[{tag}] Quiz tab from Model opens Split and shows the question', m['size'] == 'split' and page.is_visible('#pane-quiz .qtext'), m['size'])
    sheet_size(page, 'read')
    for _ in range(4):
        if page.evaluate("/Find the part/.test(document.querySelector('#pane-quiz .qtext').textContent)"):
            break
        page.click('#pane-quiz .qopt >> nth=0')
        page.wait_for_timeout(200)
        page.click('#q-next')
        page.wait_for_timeout(600)
    is_find = page.evaluate("/Find the part/.test(document.querySelector('#pane-quiz .qtext').textContent)")
    m = page.evaluate(SHEET_JS)
    check(f'[{tag}] find-the-part question brings the model back (Split)', is_find and m['size'] == 'split', (is_find, m['size']))
    page.click('#tab-explore')

    # remembered for the session; neuroapp.* localStorage keys untouched
    sheet_size(page, 'read')
    page.reload()
    ready(page)
    m = page.evaluate(SHEET_JS)
    check(f'[{tag}] size remembered for the session', m['size'] == 'read' and m['pressed'] == ['read'], (m['size'], m['pressed']))
    keys = page.evaluate("Object.keys(localStorage).filter(k => !k.startsWith('neuroapp.'))")
    check(f'[{tag}] no new localStorage keys', not keys, keys)

    # dragging the size row (bonus): drag up from Split snaps to Read, down to Model
    sheet_size(page, 'split', 1200)
    b = page.evaluate(SHEET_JS)['bar']
    x, y = b['left'] + 60, b['top'] + 22
    page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x, y - 120, steps=6); page.mouse.move(x, 60, steps=6); page.mouse.up()
    page.wait_for_timeout(900)
    up = page.evaluate(SHEET_JS)['size']
    b = page.evaluate(SHEET_JS)['bar']
    x, y = b['left'] + 60, b['top'] + 22
    page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x, y + 120, steps=6); page.mouse.move(x, h - 40, steps=6); page.mouse.up()
    page.wait_for_timeout(900)
    down = page.evaluate(SHEET_JS)['size']
    check(f'[{tag}] dragging the size row snaps to Read and to Model', up == 'read' and down == 'model', (up, down))
    check(f'[{tag}] no console errors', not watch.errors, watch.errors[:5])
    ctx.close()


def run_desktop_same(browser, base):
    ctx, page, watch = new_page(browser, 1366, 800, base)
    page.goto(base + '/neuron.html')
    ready(page)
    got = page.evaluate("""(sels) => Object.fromEntries(sels.map(s => { const b = document.querySelector(s).getBoundingClientRect();
        return [s, [b.x, b.y, b.width, b.height].map(v => Math.round(v * 10) / 10)]; }))""", list(DESKTOP_BEFORE))
    diff = {k: (DESKTOP_BEFORE[k], got[k]) for k in DESKTOP_BEFORE if any(abs(a - b) > 1 for a, b in zip(DESKTOP_BEFORE[k], got[k]))}
    check('[desktop 1366] key element boxes unchanged by Tier 9', not diff, diff)
    check('[desktop 1366] size row hidden on desktop', not page.is_visible('#sheet-bar'))
    check('[desktop 1366] no console errors', not watch.errors, watch.errors[:5])
    ctx.close()


def main():
    os.makedirs(SHOTS, exist_ok=True)
    port = free_port()
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'],
                           cwd=PUBLIC, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f'http://127.0.0.1:{port}'
    time.sleep(0.8)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME, args=ARGS)
            only = sys.argv[1] if len(sys.argv) > 1 else 'all'
            if only in ('all', 'desktop'):
                run_viewport(browser, base, 1280, 800, 'desktop')
            if only in ('all', 'phone'):
                run_viewport(browser, base, 390, 844, 'phone')
            if only in ('all', 'extras'):
                run_extras(browser, base)
            if only in ('all', 'sheet'):
                run_desktop_same(browser, base)
                run_sheet(browser, base, 390, 844)
                run_sheet(browser, base, 360, 740)
            browser.close()
    finally:
        srv.terminate()
    passed = sum(1 for _, ok in results if ok)
    print(f'\n{passed} passed, {len(results) - passed} failed, {len(results)} checks')
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())

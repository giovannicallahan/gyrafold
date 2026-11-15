#!/usr/bin/env python3
"""Playwright checks for viewer/public/imaging.html.

Usage: python3 scripts/tests/test_imaging.py [--port 8765]

Serves viewer/public with python3 -m http.server, then runs the page in system Chrome
at 1366x800 and 390x844, with and without reduced motion. Screenshots go to
/home/claude/stage/shots6/. Prints PASS/FAIL per check and a summary; exit 1 on failure.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tab_checks import goto_view, run_fallback_checks, run_tab_checks, visible_views  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "viewer" / "public"
SHOTS = Path("/home/claude/stage/shots6")
METHODS = ["mri", "dti", "ct", "fmri", "pet", "eeg", "meg"]

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))


def serve(port):
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                            cwd=PUBLIC, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/imaging.html", timeout=1)
            return proc
        except Exception:
            time.sleep(0.1)
    proc.kill()
    raise SystemExit("server did not start")


VIEWS = [("overview", "Overview"), ("compare", "Compare"), ("methods", "Methods"), ("eeg", "EEG explorer"),
         ("quiz", "Quiz"), ("glossary", "Glossary"), ("sources", "Sources")]
SECTIONS = ["opening", "families", "tradeoff", "methods", "eeg", "quiz", "glossary", "sources"]


def visible_cards(page):
    return page.evaluate("[...document.querySelectorAll('#cards .mcard')].filter(c=>getComputedStyle(c).display!=='none').map(c=>c.dataset.method)")


def run_case(browser, base, w, h, reduced, tag):
    ctx = browser.new_context(viewport={"width": w, "height": h},
                              reduced_motion="reduce" if reduced else "no-preference",
                              device_scale_factor=1, has_touch=w < 760)
    page = ctx.new_page()
    errors, failed, foreign = [], [], []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: failed.append(r.url))
    page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)

    def on_request(r):
        if not r.url.startswith(base) and not r.url.startswith("data:") and not r.url.startswith("blob:"):
            foreign.append(r.url)
    page.on("request", on_request)

    url = base + "/imaging.html"
    page.goto(url)
    page.wait_for_selector("body[data-ready='1']", timeout=10000)
    page.wait_for_timeout(300)
    p = f"[{tag}] "

    check(p + "content loaded", page.locator("#load-err").is_hidden())
    check(p + "header has Home plus three mode links, Imaging current",
          page.locator(".modes a").count() == 4 and page.locator(".modes a[aria-current='page']").inner_text() == "Imaging")
    check(p + "seven method chips", page.locator("#chips .chip").count() == 7)
    check(p + "two families", page.locator("#fam .card").count() == 2)
    ov = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check(p + "no horizontal overflow", ov <= 1, f"overflow {ov}px")
    page.screenshot(path=str(SHOTS / f"imaging_{tag}_top.png"))

    # ── tabs: structure, one view at a time, pager, sticky bar, Back, keys, hashes ──
    run_tab_checks(page, check, p, url, VIEWS, w, SHOTS, f"imaging_{tag}")

    # ── Compare: chart, picker, table ──
    goto_view(page, "compare")
    bars = page.locator("#chart .bar")
    check(p + "chart has 5 drawn bars (activity methods + DTI)", bars.count() == 5, str(bars.count()))
    vb = page.evaluate("+document.getElementById('chart').getAttribute('viewBox').split(' ')[2]")
    check(p + "chart drawn at the width of its view", vb > (700 if w > 1000 else 300), str(vb))
    ok_all = True
    for m in METHODS:
        page.locator(f"#picker button[data-method='{m}']").click()
        txt = page.locator("#res-detail").inner_text()
        name = page.evaluate(f"document.querySelector('#chips .chip[data-method={m}]').textContent")
        if name.strip() not in txt:
            ok_all = False
    check(p + "every method selectable from picker", ok_all)
    page.locator("#chart .bar[data-method='fmri']").click()
    check(p + "chart bar click selects", "fMRI" in page.locator("#res-detail").inner_text())
    page.locator("#chart .bar[data-method='eeg']").focus()
    page.keyboard.press("Enter")
    check(p + "chart bar keyboard select", "EEG" in page.locator("#res-detail").inner_text())
    check(p + "table has 7 rows", page.locator("#res-table tbody tr").count() == 7)
    page.locator("#tradeoff").screenshot(path=str(SHOTS / f"imaging_{tag}_chart.png"))
    page.locator("#res-detail a", has_text="Read about EEG").click()
    page.wait_for_timeout(60)
    check(p + "chart 'Read about' link opens Methods on that method",
          visible_views(page) == ["methods"] and visible_cards(page) == ["eeg"] and page.evaluate("location.hash") == "#m-eeg")
    check(p + "link lands focus on the method heading", page.evaluate("document.activeElement.id") == "mh-eeg")

    # ── level switch ──
    goto_view(page, "overview")
    page.locator(".seg button[data-level='beginner']").click()
    intro_b = page.locator("#intro").inner_text()
    sum_b = page.evaluate("document.querySelector('#m-fmri .summary').textContent")
    page.locator(".seg button[data-level='expert']").click()
    intro_e = page.locator("#intro").inner_text()
    sum_e = page.evaluate("document.querySelector('#m-fmri .summary').textContent")
    check(p + "level switch changes text", intro_b != intro_e and sum_b != sum_e)
    stored = page.evaluate("JSON.parse(localStorage.getItem('neuroapp.profile.v1')||'{}').level")
    check(p + "level stored under viewer key", stored == "expert", str(stored))
    check(p + "expert shows caveat", page.locator("#m-fmri .caveat").count() == 1)
    page.reload()
    page.wait_for_selector("body[data-ready='1']")
    check(p + "level persists after reload",
          page.locator(".seg button[data-level='expert']").get_attribute("aria-pressed") == "true")
    page.locator(".seg button[data-level='beginner']").click()

    # ── Methods: one at a time ──
    all_cards = True
    for m in METHODS:
        goto_view(page, "overview")
        page.locator(f"#chips .chip[data-method='{m}']").click()
        page.wait_for_timeout(50)
        if visible_views(page) != ["methods"] or visible_cards(page) != [m] or not page.locator(f"#mb-{m}").is_visible():
            all_cards = False
    check(p + "every overview chip opens Methods on that method, one card shown", all_cards)
    goto_view(page, "overview")
    page.locator("#fam .mini a", has_text="PET").click()
    check(p + "family links open their method", visible_cards(page) == ["pet"])
    check(p + "method picker has 7 chips", page.locator("#mpick .chip").count() == 7)
    pick_ok = True
    for m in METHODS:
        page.locator(f"#mpick .chip[data-method='{m}']").click()
        page.wait_for_timeout(40)
        if visible_cards(page) != [m] or page.locator(f"#mpick .chip[data-method='{m}']").get_attribute("aria-current") != "true" \
           or page.evaluate("location.hash") != "#m-" + m or page.evaluate("document.activeElement.dataset.method") != m:
            pick_ok = False
    check(p + "picker shows one method, marks it current, sets #m- hash, keeps focus", pick_ok)
    page.locator("#mpick .chip[data-method='mri']").click()
    pg = page.locator("#view-methods > .pager")
    check(p + "first method: Previous goes to Compare, Next to the next method",
          pg.locator("a.prev").text_content() == "←Previous: Compare" and pg.locator("a.next").text_content() == "Next method: DTI→",
          f"{pg.locator('a.prev').text_content()} / {pg.locator('a.next').text_content()}")
    page.mouse.wheel(0, 3000)
    page.wait_for_timeout(150)
    pk = page.evaluate("""(()=>{const k=document.getElementById('mpick').getBoundingClientRect(),
        t=document.getElementById('tabbar').getBoundingClientRect(),
        c=document.querySelector('#mpick .chip[aria-current=true]').getBoundingClientRect();
        const e=document.elementFromPoint(c.left+c.width/2,c.top+c.height/2);
        return [Math.round(k.top-t.bottom), !!(e&&e.closest('#mpick'))];})()""")
    check(p + "method picker stays visible under the tab bar after scrolling", abs(pk[0]) <= 1 and pk[1], str(pk))
    walk = []
    for _ in range(6):
        page.locator("#view-methods > .pager a.next").click()
        page.wait_for_timeout(40)
        walk.append(visible_cards(page)[0])
    check(p + "Next method walks MRI to MEG in order", walk == METHODS[1:], str(walk))
    check(p + "Next method moves focus to the method heading", page.evaluate("document.activeElement.id") == "mh-meg")
    check(p + "last method: Next goes to EEG explorer",
          pg.locator("a.next").text_content() == "Next: EEG explorer→")
    if w < 760:
        check(p + "phones: method body shown without a Show/Hide toggle",
              page.locator("#mb-meg").is_visible() and page.locator("#m-meg .mtoggle").is_hidden())
    page.locator("#m-meg").screenshot(path=str(SHOTS / f"imaging_{tag}_card_meg.png"))
    page.locator("#view-methods > .pager a.next").click()
    page.wait_for_timeout(60)
    check(p + "Next from the last method opens EEG explorer", visible_views(page) == ["eeg"])
    goto_view(page, "methods")
    check(p + "Methods tab reopens the last method shown", visible_cards(page) == ["meg"] and page.evaluate("location.hash") == "#methods")
    page.locator("#mpick .chip[data-method='fmri']").click()
    page.locator("#m-fmri").screenshot(path=str(SHOTS / f"imaging_{tag}_card_fmri.png"))

    # deep link from the welcome page's guide (fresh page load)
    page.goto("about:blank")
    page.goto(url + "#m-fmri")
    page.wait_for_selector("body[data-ready='1']")
    page.wait_for_timeout(150)
    check(p + "#m-fmri deep link opens Methods on fMRI",
          visible_views(page) == ["methods"] and visible_cards(page) == ["fmri"]
          and page.locator("#mpick .chip[data-method='fmri']").get_attribute("aria-current") == "true"
          and page.locator("#tab-methods").get_attribute("aria-selected") == "true")
    check(p + "#m-fmri deep link opens at the top of the view", page.evaluate("scrollY") <= 1, str(page.evaluate("scrollY")))
    page.evaluate("location.hash='#m-pet'")
    page.wait_for_timeout(150)
    check(p + "typed hash change switches method", visible_cards(page) == ["pet"] and page.evaluate("scrollY") <= 1)
    page.go_back(); page.wait_for_timeout(150)
    check(p + "Back returns to the previous method", visible_cards(page) == ["fmri"])

    # citations
    cite = page.locator("#m-fmri .cite").first
    cite.click()
    pop = page.locator("#cite-pop")
    link = pop.locator("a")
    check(p + "cite popover opens with safe link",
          pop.is_visible() and link.count() == 1 and link.get_attribute("rel") == "noopener noreferrer")
    page.keyboard.press("Escape")
    check(p + "cite popover closes with Escape", pop.is_hidden())
    page.locator("#m-fmri .cite").first.click()
    goto_view(page, "glossary")
    check(p + "changing view closes an open cite popover", pop.is_hidden())

    # ── EEG explorer ──
    goto_view(page, "eeg")
    els = page.locator("#head-box .el")
    check(p + "21 electrodes", els.count() == 21, str(els.count()))
    page.locator("#head-box .el[data-el='F3']").click()
    d = page.locator("#el-detail").inner_text()
    check(p + "electrode decoded (F3)", "frontal" in d and "left" in d, d)
    page.locator("#head-box .el[data-el='Pz']").click()
    check(p + "electrode decoded (Pz)", "midline" in page.locator("#el-detail").inner_text())
    sizes = page.evaluate("[...document.querySelectorAll('#head-box .el')].map(b=>{const r=b.getBoundingClientRect();return Math.min(r.width,r.height)})")
    check(p + "electrode targets >= 44px", min(sizes) >= 44, str(min(sizes)))
    texts = set()
    for b in ["delta", "theta", "alpha", "beta", "gamma"]:
        page.locator(f"#bands button[data-band='{b}']").click()
        texts.add(page.locator("#band-text").inner_text())
    check(p + "five bands give five texts", len(texts) == 5)
    play = page.locator("#wave-play").inner_text()
    if reduced:
        check(p + "reduced motion: wave not autoplaying", play == "Play", play)
        a = page.evaluate("document.getElementById('wave').toDataURL()")
        page.wait_for_timeout(400)
        b2 = page.evaluate("document.getElementById('wave').toDataURL()")
        check(p + "reduced motion: static trace", a == b2)
    else:
        check(p + "wave animates by default", play == "Pause", play)
    page.locator("#eeg").screenshot(path=str(SHOTS / f"imaging_{tag}_eeg.png"))

    # ── quiz ──
    goto_view(page, "quiz")
    n = page.evaluate("fetch('./content/imaging.json').then(r=>r.json()).then(d=>d.chooser.length)")
    answer_id = page.evaluate("fetch('./content/imaging.json').then(r=>r.json()).then(d=>d.chooser[0].answer)")
    page.locator("#quiz-opts button").first.click()
    page.locator("#quiz").screenshot(path=str(SHOTS / f"imaging_{tag}_quiz.png"))
    page.locator("#quiz-fb a").click()
    page.wait_for_timeout(60)
    check(p + "quiz feedback link opens the best method",
          visible_views(page) == ["methods"] and visible_cards(page) == [answer_id], f"{visible_cards(page)} want {answer_id}")
    page.go_back(); page.wait_for_timeout(150)
    check(p + "Back from the method returns to the quiz with the answer kept",
          visible_views(page) == ["quiz"] and page.locator("#quiz-next").is_visible())
    fb_ok = True
    page.locator("#quiz-next").click()
    for i in range(1, n):
        page.locator("#quiz-opts button").first.click()
        if not page.locator("#quiz-fb .verdict").inner_text().strip():
            fb_ok = False
        page.locator("#quiz-next").click()
    check(p + "quiz answers give feedback", fb_ok)
    check(p + "quiz feedback is aria-live", page.locator("#quiz-fb").get_attribute("aria-live") == "polite")
    check(p + "quiz shows score", "of " + str(n) in page.locator("#quiz-q").inner_text())
    page.locator("#quiz-opts button", has_text="Try again").click()
    check(p + "quiz try again", "Question 1 of" in page.locator("#quiz-progress").inner_text())

    # ── glossary and sources ──
    goto_view(page, "glossary")
    check(p + "glossary rendered", page.locator("#gloss > div").count() >= 8)
    goto_view(page, "sources")
    nsrc = page.evaluate("fetch('./content/imaging.json').then(r=>r.json()).then(d=>Object.keys(d.sources).length)")
    check(p + "every source listed", page.locator("#src-list li").count() == nsrc)
    page.locator("#foot-src-btn").click()
    check(p + "footer sources control", page.locator("#foot-src-list li").count() == nsrc
          and page.locator("#foot-sources").is_visible())
    ext = page.evaluate("[...document.querySelectorAll('a[target=_blank]')].every(a=>a.rel==='noopener noreferrer')")
    check(p + "external links rel=noopener noreferrer", ext)
    keys = page.evaluate("Object.keys(localStorage)")
    check(p + "saved-progress keys unchanged (neuroapp. prefix only)", all(k.startswith("neuroapp.") for k in keys), str(keys))

    # keyboard focus visible on a header link
    goto_view(page, "overview")
    page.evaluate("document.activeElement && document.activeElement.blur(); window.scrollTo(0,0)")
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
    check(p + "visible focus ring", outline not in ("none", ""), outline)

    page.screenshot(path=str(SHOTS / f"imaging_{tag}_full.png"), full_page=True)
    check(p + "no console errors", not errors, "; ".join(errors[:3]))
    check(p + "no failed requests", not failed, "; ".join(failed[:3]))
    check(p + "no requests to other hosts", not foreign, "; ".join(foreign[:3]))
    ctx.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    rc = subprocess.call([sys.executable, str(Path(__file__).with_name("validate_content.py")),
                          str(PUBLIC / "content" / "imaging.json")])
    check("content JSON validates", rc == 0)
    proc = serve(args.port)
    base = f"http://127.0.0.1:{args.port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                                         args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
            for w, h in ((1366, 800), (390, 844)):
                for reduced in (False, True):
                    run_case(browser, base, w, h, reduced, f"{w}x{h}{'_rm' if reduced else ''}")
            run_fallback_checks(browser, check, base + "/imaging.html", "**/content/imaging.json*", SECTIONS, "[fallback] ")
            browser.close()
    finally:
        proc.terminate()
    passed = sum(1 for r in results if r[1])
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

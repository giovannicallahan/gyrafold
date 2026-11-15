#!/usr/bin/env python3
"""Playwright checks for viewer/public/artificial.html (the tabbed "Artificial side" page).

Usage: python3 scripts/tests/test_artificial.py [--port 8766]

Serves viewer/public with python3 -m http.server, then runs the page in system Chrome
at 1366x800 and 390x844, with and without reduced motion. Screenshots go to
/home/claude/stage/shots6/ (artificial_*). Prints PASS/FAIL per check and a summary; exit 1 on failure.
The content file itself is checked by test_artificial_content.py.
"""
import argparse
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
VIEWS = [("overview", "Overview"), ("one", "One neuron"), ("compare", "Real and artificial"),
         ("network", "Deep network"), ("training", "Training"), ("quiz", "Quiz"), ("glossary", "Words and sources")]
SECTIONS = ["opening", "one", "compare", "network", "training", "quiz", "glossary", "sources"]

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))


def serve(port):
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                            cwd=PUBLIC, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/artificial.html", timeout=1)
            return proc
        except Exception:
            time.sleep(0.1)
    proc.kill()
    raise SystemExit("server did not start")


def fresh(page, url):
    page.goto("about:blank")
    page.goto(url)
    page.wait_for_selector("body[data-ready='1']", timeout=10000)
    page.wait_for_timeout(120)


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

    url = base + "/artificial.html"
    page.goto(url)
    page.wait_for_selector("body[data-ready='1']", timeout=10000)
    page.wait_for_timeout(300)
    p = f"[{tag}] "

    check(p + "content loaded", page.locator("#load-err").is_hidden() and len(page.locator("#intro").inner_text()) > 20)
    check(p + "header has Home and mode links", page.locator(".modes a", has_text="Home").count() == 1)
    check(p + "Biological / Artificial switch present", page.locator(".sides a[aria-current='page']").inner_text() == "Artificial")
    ov = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check(p + "no horizontal overflow", ov <= 1, f"overflow {ov}px")
    page.screenshot(path=str(SHOTS / f"artificial_{tag}_top.png"))

    run_tab_checks(page, check, p, url, VIEWS, w, SHOTS, f"artificial_{tag}")

    # overview chips switch views
    chips_ok = True
    for href, vid in (("#one", "one"), ("#compare", "compare"), ("#network", "network"),
                      ("#training", "training"), ("#quiz", "quiz"), ("#glossary", "glossary")):
        goto_view(page, "overview")
        page.locator(f"#opening .chips a[href='{href}']").click()
        page.wait_for_timeout(50)
        if visible_views(page) != [vid] or page.evaluate("location.hash") != href:
            chips_ok = False
    check(p + "overview chips open their views", chips_ok)

    # deep links used by index.html and the guide
    deep_ok = True
    for href, vid in (("#one", "one"), ("#network", "network"), ("#training", "training"), ("#glossary", "glossary")):
        fresh(page, url + href)
        if visible_views(page) != [vid] or page.evaluate("scrollY") > 1:
            deep_ok = False
    check(p + "index.html deep links (#one #network #training #glossary) open their views", deep_ok)
    fresh(page, url + "#sources")
    top = page.evaluate("document.getElementById('sources').getBoundingClientRect().top")
    bar = page.evaluate("document.getElementById('tabbar').getBoundingClientRect().bottom")
    check(p + "#sources opens Words and sources and lands on the source list",
          visible_views(page) == ["glossary"] and page.locator("#tab-glossary").get_attribute("aria-selected") == "true"
          and bar - 1 <= top <= bar + 60, f"top {top}, bar {bar}")

    # one neuron
    fresh(page, url + "#one")
    r0 = page.locator("#n-readout").inner_text()
    page.locator("#sw0").fill("-2")
    page.locator("#sw0").dispatch_event("input")
    check(p + "weight slider changes the readout", page.locator("#n-readout").inner_text() != r0)
    page.locator("#act-seg button[data-act='relu']").click()
    check(p + "activation switch", "ReLU" in page.locator("#fn-info").inner_text() or "relu" in page.locator("#fn-info").inner_text().lower())
    page.locator("#n-reset").click()
    check(p + "reset restores the readout", page.locator("#n-readout").inner_text() == r0)
    page.locator("#view-one").screenshot(path=str(SHOTS / f"artificial_{tag}_one.png"))

    # network: drawn at the width of its view once shown
    goto_view(page, "network")
    vb = page.evaluate("+document.getElementById('netsvg').getAttribute('viewBox').split(' ')[2]")
    want = page.evaluate("Math.max(300, Math.round(document.getElementById('net-wrap').clientWidth - 16))")
    check(p + "network diagram fits its box when the view opens", vb == want, f"{vb} vs {want}")
    page.locator("#net-send").click()
    if reduced:
        check(p + "reduced motion: signal computed at once", "All layers" in page.locator("#net-caption").inner_text())
    else:
        page.wait_for_timeout(200)
        goto_view(page, "training")
        cap = page.locator("#net-caption").inner_text()
        check(p + "leaving the network view finishes a travelling signal", "Done" in cap, cap)
        goto_view(page, "network")
    page.locator("#hl-seg button[data-n='3']").click()
    check(p + "hidden-layer switch", "3 hidden" in page.locator("#net-count").inner_text())

    # training pauses when its view is left
    goto_view(page, "training")
    page.locator("#t-train").click()
    page.wait_for_timeout(250)
    goto_view(page, "quiz")
    s1 = page.locator("#t-steps").text_content()
    page.wait_for_timeout(300)
    s2 = page.locator("#t-steps").text_content()
    stopped = page.locator("#t-train").text_content() == "Train" or "Learned" in page.locator("#train-status").text_content()
    check(p + "training pauses when you leave its view", s1 == s2 and stopped, f"{s1} -> {s2}")
    goto_view(page, "training")
    page.locator("#t-step").click()
    check(p + "one training step", page.locator("#t-steps").text_content() != "0")
    page.locator("#view-training").screenshot(path=str(SHOTS / f"artificial_{tag}_training.png"))

    # quiz
    goto_view(page, "quiz")
    n = page.evaluate("fetch('./content/ann.json').then(r=>r.json()).then(d=>d.quiz.length)")
    fb_ok = True
    for i in range(n):
        page.locator("#quiz-opts button").first.click()
        if not page.locator("#quiz-fb .verdict").inner_text().strip():
            fb_ok = False
        if i == 0:
            page.locator("#quiz").screenshot(path=str(SHOTS / f"artificial_{tag}_quiz.png"))
        page.locator("#quiz-next").click()
    check(p + "quiz answers give feedback", fb_ok)
    check(p + "quiz shows score", "of " + str(n) in page.locator("#quiz-q").inner_text())

    # level
    goto_view(page, "overview")
    i_b = page.locator("#intro").inner_text()
    page.locator("#level-seg button[data-level='expert']").click()
    check(p + "level switch changes text", page.locator("#intro").inner_text() != i_b)
    check(p + "level stored under viewer key",
          page.evaluate("JSON.parse(localStorage.getItem('neuroapp.profile.v1')||'{}').level") == "expert")
    page.locator("#level-seg button[data-level='beginner']").click()

    # cite popover closes on view change
    goto_view(page, "one")
    page.locator("#view-one .cite").first.click()
    check(p + "cite popover opens", page.locator("#cite-pop").is_visible())
    goto_view(page, "compare")
    check(p + "changing view closes an open cite popover", page.locator("#cite-pop").is_hidden())

    # glossary and sources
    goto_view(page, "glossary")
    check(p + "glossary rendered", page.locator("#gloss > div").count() >= 5)
    nsrc = page.evaluate("fetch('./content/ann.json').then(r=>r.json()).then(d=>Object.keys(d.sources).length)")
    check(p + "every source listed", page.locator("#src-list li").count() == nsrc)
    ext = page.evaluate("[...document.querySelectorAll('a[target=_blank]')].every(a=>a.rel==='noopener noreferrer')")
    check(p + "external links rel=noopener noreferrer", ext)
    keys = page.evaluate("Object.keys(localStorage)")
    check(p + "saved-progress keys unchanged (neuroapp. prefix only)", all(k.startswith("neuroapp.") for k in keys), str(keys))

    page.screenshot(path=str(SHOTS / f"artificial_{tag}_full.png"), full_page=True)
    check(p + "no console errors", not errors, "; ".join(errors[:3]))
    check(p + "no failed requests", not failed, "; ".join(failed[:3]))
    check(p + "no requests to other hosts", not foreign, "; ".join(foreign[:3]))
    ctx.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    args = ap.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    proc = serve(args.port)
    base = f"http://127.0.0.1:{args.port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                                         args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
            for w, h in ((1366, 800), (390, 844)):
                for reduced in (False, True):
                    run_case(browser, base, w, h, reduced, f"{w}x{h}{'_rm' if reduced else ''}")
            run_fallback_checks(browser, check, base + "/artificial.html", "**/content/ann.json*", SECTIONS, "[fallback] ")
            browser.close()
    finally:
        proc.terminate()
    passed = sum(1 for r in results if r[1])
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

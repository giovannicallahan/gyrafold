"""Shared Playwright checks for the tabbed lesson pages (imaging.html, artificial.html).

Both pages use the same setupTabs() code, so they are held to the same checks here.
`check(name, cond, detail)` is the caller's reporter; `p` is the case prefix.
"""


def visible_views(page):
    return page.evaluate("[...document.querySelectorAll('.view')].filter(v=>getComputedStyle(v).display!=='none').map(v=>v.id.slice(5))")


def active_tab(page):
    return page.evaluate("(document.querySelector('[role=tab][aria-selected=true]')||{}).dataset?.view || null")


def goto_view(page, vid):
    page.locator(f"#tab-{vid}").click()
    page.wait_for_timeout(60)


def tabbar_unobstructed(page):
    """Tab bar on screen and not covered: the element at each visible tab's centre is that tab."""
    return page.evaluate("""(()=>{
      const bar=document.getElementById('tabbar').getBoundingClientRect();
      if (bar.top < -0.5 || bar.bottom > innerHeight) return 'bar off screen: top '+bar.top;
      const list=document.getElementById('tablist').getBoundingClientRect();
      for (const t of document.querySelectorAll('[role=tab]')) {
        const r=t.getBoundingClientRect();
        if (r.right<=list.left+2 || r.left>=list.right-2) continue; // scrolled out sideways (phones)
        const x=Math.min(Math.max(r.left+r.width/2,list.left+4),list.right-4), y=r.top+r.height/2;
        const e=document.elementFromPoint(x,y);
        if (!e || !t.contains(e)) return 'tab '+t.id+' covered by '+(e&&(e.id||e.className||e.tagName));
      }
      return 'ok';
    })()""")


def run_tab_checks(page, check, p, base_url, views, w, shots=None, tag=""):
    """views: list of (id, label). base_url: the page URL without hash."""
    ids = [v for v, _ in views]
    labels = dict(views)
    phone = w < 760

    # structure
    check(p + "tablist with role=tab buttons, 7 or fewer",
          page.locator("#tablist[role=tablist]").count() == 1
          and page.locator("#tablist [role=tab]").count() == len(views) <= 7)
    check(p + "tab labels in order", page.evaluate("[...document.querySelectorAll('[role=tab]')].map(t=>t.textContent)") == [l for _, l in views])
    ok = page.evaluate("""[...document.querySelectorAll('[role=tab]')].every(t=>{
        const pnl=document.getElementById(t.getAttribute('aria-controls'));
        return pnl && pnl.getAttribute('role')==='tabpanel' && pnl.getAttribute('aria-labelledby')===t.id;})""")
    check(p + "every tab controls a labelled tabpanel", ok)
    check(p + "first view only on load", visible_views(page) == [ids[0]], str(visible_views(page)))

    # one view at a time, hashes, pager on every view, no sideways scroll
    one_at_a_time, hashes_ok, sel_ok, pager_ok, overflow_ok, top_ok, tabvis_ok = True, True, True, True, True, True, True
    pager_detail, ov_detail = "", ""
    for i, vid in enumerate(ids):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        goto_view(page, vid)
        if visible_views(page) != [vid]:
            one_at_a_time = False
        if page.evaluate("location.hash") != "#" + vid:
            hashes_ok = False
        if page.evaluate("[...document.querySelectorAll('[role=tab]')].filter(t=>t.getAttribute('aria-selected')==='true').map(t=>t.dataset.view+':'+t.tabIndex).join()") != vid + ":0":
            sel_ok = False
        if page.evaluate("scrollY") > 1:
            top_ok = False
        prev_t = page.evaluate(f"[...document.querySelectorAll('#view-{vid} > .pager a.prev')].map(a=>a.textContent)")
        next_t = page.evaluate(f"[...document.querySelectorAll('#view-{vid} > .pager a.next')].map(a=>a.textContent)")
        if vid != "methods":  # imaging's Methods pager steps through methods; checked separately
            want_prev = ["←Previous: " + labels[ids[i - 1]]] if i > 0 else []
            want_next = ["Next: " + labels[ids[i + 1]] + "→"] if i < len(ids) - 1 else []
            if prev_t != want_prev or next_t != want_next:
                pager_ok = False
                pager_detail = f"{vid}: {prev_t} {next_t}"
        elif not (prev_t and next_t):
            pager_ok = False
            pager_detail = f"{vid}: {prev_t} {next_t}"
        ov = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if ov > 1:
            overflow_ok = False
            ov_detail = f"{vid}: {ov}px"
        # the active tab is scrolled into view inside the bar
        inside = page.evaluate(f"""(()=>{{const l=document.getElementById('tablist').getBoundingClientRect(),
            r=document.getElementById('tab-{vid}').getBoundingClientRect(); return r.left>=l.left-1 && r.right<=l.right+1;}})()""")
        if not inside:
            tabvis_ok = False
        if shots:
            page.screenshot(path=str(shots / f"{tag}_view_{vid}.png"))
    check(p + "exactly one view visible for every tab", one_at_a_time)
    check(p + "every tab sets its own hash", hashes_ok)
    check(p + "aria-selected and roving tabindex follow the active tab", sel_ok)
    check(p + "changing view scrolls to the top", top_ok)
    check(p + "Previous/Next on every view, labelled with the destination", pager_ok, pager_detail)
    check(p + "no horizontal page scroll on any view", overflow_ok, ov_detail)
    check(p + "active tab scrolled into view in the tab bar", tabvis_ok)
    last = ids[-1]
    check(p + "last view has no Next and offers Keep exploring links",
          page.locator(f"#view-{last} > .pager a.next").count() == 0
          and page.locator(f"#view-{last} .closing a").count() >= 2
          and page.locator(f"#view-{last} .closing a").first.is_visible())

    # tab bar stays visible and uncovered after scrolling, on every view
    stick_ok, stick_detail = True, ""
    for vid in ids:
        goto_view(page, vid)
        page.mouse.wheel(0, 2500)
        page.wait_for_timeout(150)
        r = tabbar_unobstructed(page)
        if r != "ok":
            stick_ok, stick_detail = False, f"{vid}: {r}"
    check(p + "tab bar visible and uncovered after scrolling, every view", stick_ok, stick_detail)
    if not phone:
        tb = page.evaluate("document.getElementById('topbar').getBoundingClientRect().bottom")
        bt = page.evaluate("document.getElementById('tabbar').getBoundingClientRect().top")
        check(p + "tab bar sits directly under the sticky top bar", abs(tb - bt) <= 1.5, f"{tb} vs {bt}")
        check(p + "top bar (Home link) still visible after scrolling",
              page.locator(".modes a", has_text="Home").is_visible()
              and page.evaluate("document.getElementById('topbar').getBoundingClientRect().top") >= -0.5)

    # Next button walks the views; it moves focus to the new view's heading
    goto_view(page, ids[0])
    page.locator(f"#view-{ids[0]} > .pager a.next").click()
    page.wait_for_timeout(60)
    check(p + "Next button opens the next view", visible_views(page) == [ids[1]], str(visible_views(page)))
    foc = page.evaluate("document.activeElement && document.activeElement.closest('.view') && document.activeElement.closest('.view').id")
    check(p + "Next moves focus into the new view (its heading)",
          foc == "view-" + ids[1] and page.evaluate("/^H[1-3]$/.test(document.activeElement.tagName)"))
    page.locator(f"#view-{ids[1]} > .pager a.prev").click()
    page.wait_for_timeout(60)
    check(p + "Previous button opens the previous view", visible_views(page) == [ids[0]])

    # browser Back steps through views
    goto_view(page, ids[1]); goto_view(page, ids[2]); goto_view(page, ids[3])
    page.go_back(); page.wait_for_timeout(150)
    b1 = visible_views(page)
    page.go_back(); page.wait_for_timeout(150)
    b2 = visible_views(page)
    page.go_forward(); page.wait_for_timeout(150)
    f1 = visible_views(page)
    check(p + "browser Back and Forward step through views", b1 == [ids[2]] and b2 == [ids[1]] and f1 == [ids[2]], f"{b1} {b2} {f1}")
    check(p + "Back updates the selected tab", active_tab(page) == ids[2])

    # keyboard: arrows, Home, End on the tablist
    goto_view(page, ids[0])
    page.locator(f"#tab-{ids[0]}").focus()
    page.keyboard.press("ArrowRight")
    k1 = (active_tab(page), page.evaluate("document.activeElement.id"))
    page.keyboard.press("ArrowLeft")
    k2 = active_tab(page)
    page.keyboard.press("ArrowLeft")
    k3 = active_tab(page)
    page.keyboard.press("Home")
    k4 = active_tab(page)
    page.keyboard.press("End")
    k5 = (active_tab(page), visible_views(page))
    check(p + "ArrowRight selects and focuses the next tab", k1 == (ids[1], "tab-" + ids[1]), str(k1))
    check(p + "ArrowLeft goes back and wraps from the first tab", k2 == ids[0] and k3 == ids[-1], f"{k2} {k3}")
    check(p + "Home and End jump to the first and last tab", k4 == ids[0] and k5 == (ids[-1], [ids[-1]]), f"{k4} {k5}")
    outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
    check(p + "visible focus ring on a keyboard-focused tab", outline not in ("none", ""), outline)

    # tap targets
    small = page.evaluate("""[...document.querySelectorAll('[role=tab], .view.active > .pager a')]
        .map(e=>e.getBoundingClientRect()).filter(r=>r.height<44 || r.width<44).length""")
    check(p + "tabs and pager buttons are at least 44px", small == 0, f"{small} too small")

    # every tab hash opens its view on a fresh load
    deep_ok, deep_detail = True, ""
    for vid in ids:
        page.goto(base_url + "#" + vid)
        page.wait_for_selector("body[data-ready='1']", timeout=10000)
        page.wait_for_timeout(100)
        if visible_views(page) != [vid] or active_tab(page) != vid:
            deep_ok, deep_detail = False, f"{vid}: {visible_views(page)}"
    check(p + "every tab hash opens its view on page load", deep_ok, deep_detail)
    page.goto(base_url)
    page.wait_for_selector("body[data-ready='1']", timeout=10000)


def run_fallback_checks(browser, check, base_url, content_glob, section_ids, prefix):
    """No-JS and failed-JSON: every section visible as one long page, no tab bar."""
    ctx = browser.new_context(viewport={"width": 1366, "height": 800}, java_script_enabled=False)
    page = ctx.new_page()
    page.goto(base_url)
    vis = [s for s in section_ids if page.locator(f"#{s}").is_visible()]
    check(prefix + "no JS: every section shown as one page", vis == section_ids, str(vis))
    check(prefix + "no JS: tab bar hidden", page.locator("#tabbar").is_hidden())
    ctx.close()

    ctx = browser.new_context(viewport={"width": 1366, "height": 800})
    page = ctx.new_page()
    page.route(content_glob, lambda r: r.abort())
    page.goto(base_url + "#quiz")
    page.wait_for_selector("#load-err", state="visible", timeout=10000)
    page.wait_for_timeout(200)
    vis = [s for s in section_ids if page.locator(f"#{s}").is_visible()]
    check(prefix + "failed content load: every section shown as one page", vis == section_ids, str(vis))
    check(prefix + "failed content load: tab bar and pagers removed",
          page.locator("#tabbar").is_hidden() and page.locator(".pager").count() == 0)
    check(prefix + "failed content load: error message shown", page.locator("#load-err").is_visible())
    ctx.close()

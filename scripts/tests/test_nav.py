import subprocess,time,math
from playwright.sync_api import sync_playwright
srv=subprocess.Popen(['python3','-m','http.server','8942'],cwd='/home/claude/neuroapp/viewer/public',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
ARGS=['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']
ok=[];bad=[]
def chk(n,c):
    (ok if c else bad).append(n); print(('PASS ' if c else 'FAIL ')+n)
def clk(sel):
    r=pg.evaluate('''s=>{const e=document.querySelector(s);const b=e.getBoundingClientRect();const t=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return t&&(t===e||e.contains(t))}''',sel)
    if not r: print('  covered:',sel)
    pg.evaluate('s=>document.querySelector(s).click()',sel)
def ready(pg):
    for _ in range(240):
        # loader gone AND every model loaded (the loader's 60 s fallback can hide it before loading ends)
        if pg.evaluate("(()=>{const l=document.getElementById('loader');const s=(document.getElementById('status')||{}).textContent||'';return (!l||getComputedStyle(l).display=='none'||getComputedStyle(l).opacity=='0')&&/All \\d+ meshes|Saved for offline|Done:/.test(s)})()"): break
        pg.wait_for_timeout(1000)
    pg.wait_for_timeout(1500)
    for sel in ['#onboard-close','.onboard-skip']:
        try:
            if pg.locator(sel).first.is_visible(): pg.locator(sel).first.click()
        except Exception: pass
# ── Tier 9: phone sheet sizes (Read / Split / Model) ──
SHEET_JS="""() => {
  const r = s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return { top: b.top, bottom: b.bottom, left: b.left, right: b.right, height: b.height, width: b.width }; };
  const hit = s => { const e = document.querySelector(s); if (!e) return false; const b = e.getBoundingClientRect();
    if (b.height < 1 || b.bottom <= 0 || b.top >= innerHeight) return false;
    const t = document.elementFromPoint(b.left + b.width / 2, b.top + Math.min(b.height / 2, 20)); return !!t && (t === e || e.contains(t)); };
  const panel = r('#panel'), tabs = r('#panel-tabs');
  return { size: document.body.dataset.sheet || 'split', vh: innerHeight, vw: innerWidth,
    pressed: [...document.querySelectorAll('#sheet-bar [data-size]')].filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.size),
    panel, tabs, bar: r('#sheet-bar'), nav: r('#nav-float'), reading: Math.min(panel.bottom, innerHeight) - tabs.bottom,
    barHit: hit('#sheet-title'), tabsHit: hit('.ptab[data-pane="pane-explore"]') && hit('.ptab[data-pane="pane-tools"]'),
    homeHit: hit('#nav-home'), backHit: document.getElementById('nav-back').hidden || hit('#nav-back'), resetHit: document.getElementById('nav-reset').hidden || hit('#nav-reset'),
    brain: window.__atlas ? window.__atlas.brainRect() : null, hscroll: document.documentElement.scrollWidth > innerWidth };
}"""
def sheet_checks(b, w, h):
    t=f'[sheet {w}x{h}] '
    c=b.new_context(viewport={'width':w,'height':h},is_mobile=True,has_touch=True); pg=c.new_page(); errs=[]
    pg.on('pageerror',lambda e: errs.append(str(e))); pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.add_init_script("try{localStorage.setItem('neuroapp.level','new');localStorage.setItem('neuroapp.onboarded','1')}catch(e){}")
    pg.goto('http://127.0.0.1:8942/atlas-viewer.html'); ready(pg)
    def M():
        # software rendering can go seconds without a frame, which stalls the sheet's height transition;
        # a screenshot forces a frame, so take two around the transition before measuring
        pg.screenshot(); pg.wait_for_timeout(450); pg.screenshot(); pg.wait_for_timeout(150)
        return pg.evaluate(SHEET_JS)
    def size(n, wait=2500):
        pg.evaluate('n=>document.querySelector(`#sheet-bar [data-size="${n}"]`).click()', n); pg.wait_for_timeout(wait); return M()
    m=M(); sizes={'split':m}
    pg.screenshot(path=f'/home/claude/stage/nav/sheet-{w}-split.png')
    chk(t+'default size is Split (aria-pressed)', m['size']=='split' and m['pressed']==['split'])
    chk(t+'Split: reading area >= 55% of the height', m['reading']/m['vh']>=0.55); print('   reading', round(m['reading']/m['vh'],3))
    br=m['brain']; top=m['panel']['top']
    chk(t+'Split: brain box inside the visible view, below the buttons', br and br['left']>=-1 and br['right']<=w+1 and br['top']>=m['nav']['bottom']-1 and br['bottom']<=top+1); print('   brain', br, 'panel top', top)
    # select a structure (tap the middle of the brain) so Back / Reset view show too
    pg.touchscreen.tap((br['left']+br['right'])/2, (br['top']+br['bottom'])/2); pg.wait_for_timeout(2000)
    m=M(); sizes['split+selected']=m
    chk(t+'Split: tapping the brain selects; title follows', pg.evaluate("getComputedStyle(document.getElementById('focus-page')).display")=='flex' and pg.inner_text('#sheet-title')==pg.inner_text('#focus-header-name'))
    chk(t+'Split: Home / Back / Reset view uncovered', m['homeHit'] and m['backHit'] and m['resetHit'] and not pg.locator('#nav-back').is_hidden())
    pg.screenshot(path=f'/home/claude/stage/nav/sheet-{w}-split-selected.png')
    m=size('read'); sizes['read']=m
    pg.screenshot(path=f'/home/claude/stage/nav/sheet-{w}-read.png')
    chk(t+'Read: reading area >= 80% of the height', m['reading']/m['vh']>=0.80); print('   reading', round(m['reading']/m['vh'],3))
    chk(t+'Read: aria-pressed follows', m['pressed']==['read'])
    # the whole sheet scrolls to the last element of every tab
    badl=[]
    for pane in ['pane-explore','pane-learn','pane-quiz','pane-progress','pane-tools']:
        pg.evaluate('p=>document.querySelector(`.ptab[data-pane="${p}"]`).click()', pane); pg.wait_for_timeout(400)
        pg.evaluate("(()=>{const p=document.getElementById('panel');p.scrollTop=p.scrollHeight})()"); pg.wait_for_timeout(300)
        f=pg.evaluate("""p=>{const kids=[...document.getElementById(p).querySelectorAll('*')].filter(e=>e.getBoundingClientRect().height>0&&(e.checkVisibility?e.checkVisibility({visibilityProperty:true}):getComputedStyle(e).visibility!=='hidden'));
          const last=kids.reduce((a,e)=>e.getBoundingClientRect().bottom>a.getBoundingClientRect().bottom?e:a, kids[0]);
          const lb=last.getBoundingClientRect(), pb=document.getElementById('panel').getBoundingClientRect(), tb=document.getElementById('panel-tabs').getBoundingClientRect();
          return {ok: lb.bottom<=pb.bottom+1 && lb.bottom>tb.bottom, last: last.id||last.className||last.tagName, b: lb.bottom, p: pb.bottom}}""", pane)
        if not f['ok']: badl.append((pane,f))
    chk(t+'sheet scrolls to the last element of every tab', not badl); print('  ', badl[:3])
    css=pg.evaluate("(()=>{const c=getComputedStyle(document.getElementById('panel'));return [c.overflowY,c.overscrollBehaviorY]})()")
    chk(t+'sheet scrolls with overscroll-behavior: contain', css==['auto','contain'])
    pg.evaluate("document.querySelector('.ptab[data-pane=\"pane-explore\"]').click()"); pg.wait_for_timeout(300)
    m=size('model'); sizes['model']=m
    pg.screenshot(path=f'/home/claude/stage/nav/sheet-{w}-model.png')
    chk(t+'Model: 3D view >= 60% of the height', m['panel']['top']/m['vh']>=0.60); print('   view', round(m['panel']['top']/m['vh'],3))
    for k,v in sizes.items():
        chk(t+k+': size row and tabs >= 44 px and visible', v['bar']['height']>=44 and v['tabs']['height']>=44 and v['barHit'] and v['tabsHit'])
        chk(t+k+': Home reachable, no horizontal scroll', v['homeHit'] and not v['hscroll'])
        if k!='read': chk(t+k+': Home / Back / Reset view not covered by the sheet', v['nav']['bottom']<=v['panel']['top'] and v['homeHit'] and v['backHit'] and v['resetHit'])
    # tapping a structure in Model brings the sheet back to Split
    # the view is zoomed on the selected structure here, so tap the middle of the visible 3D view
    pg.touchscreen.tap(w/2, (m['nav']['bottom']+m['panel']['top'])/2); pg.wait_for_timeout(2500)
    m=M()
    chk(t+'tapping the brain in Model returns to Split', m['size']=='split'); print('   ', m['size'], pg.inner_text('#sheet-title'))
    pg.screenshot(path=f'/home/claude/stage/nav/sheet-{w}-tapped.png')
    # a quiz starts from Read and uses Model while it runs; the size comes back afterwards
    size('read', 1500)
    pg.evaluate("document.querySelector('.ptab[data-pane=\"pane-quiz\"]').click()"); pg.wait_for_timeout(400)
    clk2=lambda sel: pg.evaluate('s=>document.querySelector(s).click()', sel)
    clk2('#qcard-quick'); pg.wait_for_timeout(3000)
    m=M(); qh=pg.evaluate("(()=>{const e=document.getElementById('quiz-hud');const r=e.getBoundingClientRect();return {vis:e.classList.contains('visible'),top:r.top,bottom:r.bottom}})()")
    pg.screenshot(path=f'/home/claude/stage/nav/sheet-{w}-quiz.png')
    chk(t+'quiz from Read: quiz box shown above the sheet (Model size), Home visible', qh['vis'] and m['size']=='model' and qh['bottom']<=m['panel']['top']+1 and qh['top']>=0 and m['homeHit']); print('   ', m['size'], qh, m['panel']['top'])
    clk2('#btn-quit-quiz'); pg.wait_for_timeout(2500)
    chk(t+'after the quiz the earlier size (Read) comes back', M()['size']=='read')
    # remembered for the session, shared with the neuron page; no new localStorage keys
    keys=pg.evaluate("Object.keys(localStorage).filter(k=>!k.startsWith('neuroapp.'))")
    chk(t+'no new localStorage keys', not keys); print('   ', keys)
    chk(t+'no page or console errors', not errs); print('   ', errs[:3])
    pg.goto('http://127.0.0.1:8942/neuron.html'); pg.wait_for_timeout(2500)
    chk(t+'size remembered for the session (neuron page opens in Read)', pg.evaluate("document.body.dataset.sheet")=='read')
    c.close()
DESK_BEFORE={"#panel":[0,0,270,800],"#panel-top":[0,0,269,40],"#panel-tabs":[0,40,269,28],"#nav-float":[282,12,86.7,36],"#canvas-wrap":[270,0,1096,800],"#pane-explore":[0,68,269,732],"#search":[12,76,245,28],"#c":[270,0,1096,800],"#footer":[0,755,269,45],"#gizmo":[1266,700,80,80]}
S="window.__s=()=>({sel:document.getElementById('focus-header-name').textContent, page:getComputedStyle(document.getElementById('focus-page')).display, back:!document.getElementById('nav-back').hidden, hash:location.hash})"
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=ARGS)
    c=b.new_context(viewport={'width':1366,'height':800}); pg=c.new_page(); errs=[]
    pg.on('pageerror',lambda e: errs.append(str(e)))
    pg.add_init_script("try{localStorage.setItem('neuroapp.level','new');localStorage.setItem('neuroapp.onboarded','1')}catch(e){}")
    pg.goto('http://127.0.0.1:8942/index.html'); pg.goto('http://127.0.0.1:8942/atlas-viewer.html'); ready(pg)
    pg.evaluate(S)
    got=pg.evaluate("""sels=>Object.fromEntries(sels.map(s=>{const b=document.querySelector(s).getBoundingClientRect();return [s,[b.x,b.y,b.width,b.height].map(v=>Math.round(v*10)/10)]}))""", list(DESK_BEFORE))
    diff={k:(DESK_BEFORE[k],got[k]) for k in DESK_BEFORE if any(abs(a-b)>1 for a,b in zip(DESK_BEFORE[k],got[k]))}
    chk('desktop 1366: key element boxes unchanged by Tier 9', not diff); print('  ', diff)
    chk('desktop 1366: size row hidden', not pg.locator('#sheet-bar').is_visible())
    chk('main menu visible', pg.locator('#nav-home').is_visible())
    chk('back hidden at start', pg.locator('#nav-back').is_hidden())
    cam0=pg.evaluate("1")
    cv=pg.locator('#c').bounding_box()
    pg.mouse.click(cv['x']+cv['width']*.5, cv['y']+cv['height']*.45); pg.wait_for_timeout(1200)
    s1=pg.evaluate('__s()'); print(s1)
    chk('click selects + back appears', s1['page']=='flex' and s1['back'])
    def search(term):
        pg.fill('#search',term); pg.wait_for_timeout(300)
        pg.locator('#search-results .sr-item').first.dispatch_event('mousedown'); pg.wait_for_timeout(900)
    search('hippocampus'); sA=pg.evaluate('__s()')
    search('cerebellum'); sB=pg.evaluate('__s()'); print(sA['sel'],'->',sB['sel'])
    clk('#nav-back'); pg.wait_for_timeout(900)
    chk('back returns to previous structure', pg.evaluate('__s()')['sel']==sA['sel'])
    clk('#foc-isolate')
    pg.wait_for_timeout(400)
    vis=lambda: pg.evaluate("(()=>{let n=0;document.querySelectorAll('x');return 0})()")
    clk('#nav-back'); pg.wait_for_timeout(900)
    chk('back after isolate keeps structure', pg.evaluate('__s()')['sel']==sA['sel'])
    chk('reset visible when selected', pg.locator('#nav-reset').is_visible())
    clk('#nav-reset'); pg.wait_for_timeout(900)
    r=pg.evaluate('__s()'); chk('reset clears to whole brain + hides itself', r['page']=='none' and pg.locator('#nav-reset').is_hidden() and r['back'])
    clk('#nav-back'); pg.wait_for_timeout(900)
    chk('back undoes reset', pg.evaluate('__s()')['sel']==sA['sel'])
    # browser back
    pg.go_back(); pg.wait_for_timeout(900)
    chk('browser back steps view, stays in atlas', 'atlas-viewer' in pg.url and pg.evaluate('__s()')['sel']==s1['sel'])
    clk('#nav-back'); pg.wait_for_timeout(900)
    s0=pg.evaluate('__s()'); print(s0)
    chk('back to whole brain', s0['page']=='none' and not s0['back'])
    pg.mouse.click(cv['x']+cv['width']*.5, cv['y']+cv['height']*.45); pg.wait_for_timeout(1000)
    pg.screenshot(path='/home/claude/stage/nav/after_d.png')
    clk('#focus-back-btn'); pg.wait_for_timeout(800)
    chk('panel back works', pg.evaluate('__s()')['page']=='none')
    # quiz hides nav
    clk('.ptab[data-pane="pane-quiz"]'); pg.wait_for_timeout(300)
    clk('#btn-start-quiz'); pg.wait_for_timeout(1500)
    chk('quiz: home stays, back/reset hidden', pg.locator('#nav-home').is_visible() and not pg.locator('#nav-back').is_visible() and not pg.locator('#nav-reset').is_visible()); pg.screenshot(path='/home/claude/stage/nav/after_quiz.png')
    clk('#btn-quit-quiz'); pg.wait_for_timeout(800)
    chk('nav back after quiz', pg.locator('#nav-home').is_visible())
    clk('#nav-home'); pg.wait_for_timeout(4000); print('URL',pg.url)
    chk('home goes to welcome', pg.url.endswith('/index.html'))
    chk('no page errors', not errs); print(errs[:3])
    c.close()
    c=b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True); pg=c.new_page()
    pg.add_init_script("try{localStorage.setItem('neuroapp.level','new');localStorage.setItem('neuroapp.onboarded','1')}catch(e){}")
    pg.goto('http://127.0.0.1:8942/atlas-viewer.html'); ready(pg)
    br=pg.evaluate('window.__atlas.brainRect()'); pg.touchscreen.tap((br['left']+br['right'])/2, (br['top']+br['bottom'])/2); pg.wait_for_timeout(1200)
    bb=pg.locator('#nav-back').bounding_box(); hb=pg.locator('#nav-home').bounding_box(); rb=pg.locator('#nav-reset').bounding_box(); chk('phone nav fits', rb and rb['x']+rb['width']<=390)
    chk('phone buttons visible >=44px', bb and hb and bb['height']>=44 and hb['height']>=44)
    pg.screenshot(path='/home/claude/stage/nav/after_m.png')
    clk('#nav-back'); pg.wait_for_timeout(900)
    chk('phone back clears', pg.locator('#nav-back').is_hidden())
    for f in ['neuron.html','imaging.html']:
        pg.goto('http://127.0.0.1:8942/'+f); pg.wait_for_timeout(2500)
        h=pg.locator('nav.modes a[href="./index.html"]'); bx=h.bounding_box()
        chk(f+' home link visible on phone', h.is_visible() and bx['x']>=0 and bx['x']+bx['width']<=390 and pg.evaluate('document.documentElement.scrollWidth')<=390)
        pg.screenshot(path='/home/claude/stage/nav/'+f+'_m.png')
    c.close()
    sheet_checks(b, 390, 844)
    sheet_checks(b, 360, 740)
    b.close()
srv.kill(); print(len(ok),'pass',len(bad),'fail')

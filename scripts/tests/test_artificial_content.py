#!/usr/bin/env python3
"""Checks viewer/public/content/ann.json (artificial neuron content) and its sw.js wiring.
Standard library only. Prints PASS/FAIL per check, exits 1 on any failure."""
import json
import re
import sys
from pathlib import Path

PUB = Path(__file__).resolve().parents[2] / 'viewer' / 'public'
fails = 0


def chk(name, ok, detail=''):
    global fails
    if not ok:
        fails += 1
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok or not detail else ' :: ' + str(detail)))


D = json.loads((PUB / 'content' / 'ann.json').read_text(encoding='utf-8'))
SRC = D.get('sources', {})

KEYS = ['version', 'note', 'sources', 'intro', 'neuron', 'activations', 'compare',
        'network', 'training', 'quiz', 'glossary']
chk('top-level keys', all(k in D for k in KEYS), [k for k in KEYS if k not in D])

bad = [i for i, s in SRC.items() if not all(isinstance(s.get(f), str) and s[f].strip()
       for f in ('citation', 'url', 'license', 'checked')) or not s['url'].startswith('https://')]
chk('sources complete, https urls', bool(SRC) and not bad, bad)

cited, bad_cite = set(), []
need_cite = []


def walk(o, path, skip):
    if isinstance(o, dict):
        if 'cite' in o:
            c = o['cite']
            if not (isinstance(c, list) and c and all(isinstance(x, str) and x in SRC for x in c)):
                bad_cite.append(path)
            else:
                cited.update(c)
        if not skip and any(k in o for k in ('text', 'definition', 'explain')) and 'cite' not in o:
            need_cite.append(path)
        for k, v in o.items():
            walk(v, path + '/' + k, skip or path + '/' + k == '/training/demo')
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, '%s[%d]' % (path, i), skip)


walk({k: v for k, v in D.items() if k != 'note'}, '', False)
chk('every cite is a non-empty list of known source ids', not bad_cite, bad_cite)
chk('every source is cited', set(SRC) <= cited, sorted(set(SRC) - cited))
chk('text/definition/explain objects carry a cite', not need_cite, need_cite)

chk('intro beginner and expert', isinstance(D.get('intro'), dict) and 'beginner' in D['intro'] and 'expert' in D['intro'])


def ids(x):
    return [p.get('id') for p in x] if isinstance(x, list) else None


parts = D.get('neuron', {}).get('parts')
chk('neuron.parts ids', sorted(ids(parts) or []) == sorted(['inputs', 'weights', 'bias', 'sum', 'activation', 'output']), ids(parts))
acts = D.get('activations')
if isinstance(acts, dict):
    acts = acts.get('items') or acts.get('list') or acts.get('functions') or acts
chk('activations ids', sorted(ids(acts) or []) == sorted(['step', 'sigmoid', 'tanh', 'relu']), ids(acts))
steps = D.get('training', {}).get('steps')
chk('training.steps has 5 items', isinstance(steps, list) and len(steps) == 5)

qbad = []
for i, q in enumerate(D.get('quiz', [])):
    o, a = q.get('options'), q.get('answer')
    if not (isinstance(o, list) and len(o) == 4 and len(set(o)) == 4 and isinstance(a, int)
            and not isinstance(a, bool) and 0 <= a < 4):
        qbad.append(i)
chk('quiz items: 4 distinct options, valid answer', bool(D.get('quiz')) and not qbad, qbad)

rows = D.get('compare', {}).get('rows', [])
hbad = [r.get('href') for r in rows if 'href' in r and not str(r['href']).startswith('./neuron.html')]
chk('compare.rows hrefs start with ./neuron.html', bool(rows) and not hbad, hbad)

strs = []


def collect(o):
    if isinstance(o, str):
        strs.append(o)
    elif isinstance(o, dict):
        for k, v in o.items():
            strs.append(k)
            collect(v)
    elif isinstance(o, list):
        for v in o:
            collect(v)


collect(D)
chk('no "AI-powered" or em dash', not [s for s in strs if re.search('ai-powered', s, re.I) or '—' in s],
    [s[:60] for s in strs if re.search('ai-powered', s, re.I) or '—' in s])

sw = (PUB / 'sw.js').read_text(encoding='utf-8')
m = re.search(r'SHELL\s*=\s*\[(.*?)\]', sw, re.S)
shell = m.group(1) if m else ''
chk('sw.js SHELL lists artificial.html and ann.json', '"./artificial.html"' in shell and '"./content/ann.json"' in shell)

print('\n%s' % ('ALL PASSED' if not fails else '%d FAILED' % fails))
sys.exit(1 if fails else 0)

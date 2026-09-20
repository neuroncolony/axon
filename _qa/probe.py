import json, urllib.request as u
from playwright.sync_api import sync_playwright

B = 'https://axon-production-7097.up.railway.app'
d = json.load(u.urlopen(B + '/api/tokens', timeout=25))
toks = d.get('tokens', d) if isinstance(d, dict) else d
t = toks[0]
print('token keys:', list(t.keys()))
addr = t.get('address') or t.get('token') or t.get('addr') or t.get('id')
URL = f'{B}/token?a={addr}'
print('URL', URL)

CHAIN = """e => { const out = []; let n = e.parentElement;
  while (n) { const c = getComputedStyle(n);
    out.push([n.tagName + '.' + (n.className || ''), 'tf=' + c.transform, 'fl=' + c.filter, 'op=' + c.opacity,
              'mb=' + c.mixBlendMode, 'ct=' + c.contain, 'ov=' + c.overflow, 'wc=' + c.willChange,
              'h=' + Math.round(n.getBoundingClientRect().height)].join(' | '));
    n = n.parentElement; }
  return out; }"""

with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    for name, url, w in [('home', B + '/', 780), ('token', URL, 780)]:
        pg = b.new_page(viewport={'width': w, 'height': 900}, device_scale_factor=2)
        pg.goto(url, wait_until='networkidle', timeout=60000)
        pg.mouse.wheel(0, 500)
        pg.wait_for_timeout(1500)
        pg.screenshot(path=f'/data/workspace/output/axon/_qa/{name}_780.png', clip={'x': 0, 'y': 0, 'width': w, 'height': 120})
        print('---', name, pg.url)
        print(' stuck:', repr(pg.eval_on_selector('#nav', 'e => e.getAttribute("data-stuck")')))
        print(' pill :', pg.eval_on_selector('#nav .pill-left', 'e => { const c = getComputedStyle(e); return [c.backdropFilter, c.backgroundColor]; }'))
        for line in pg.eval_on_selector('#nav .pill-left', CHAIN):
            print('  ^', line)
        pg.close()
    b.close()
print('done')

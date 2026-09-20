from playwright.sync_api import sync_playwright

B = 'https://axon-production-7097.up.railway.app'
URL = B + '/token?a=0x39966D78fb8687686ffAD078731903DAF1e9F816'

JS = """() => {
  const out = [];
  for (const e of document.querySelectorAll('body *')) {
    const c = getComputedStyle(e);
    const z = c.zIndex;
    const r = e.getBoundingClientRect();
    if (r.top < 110 && r.bottom > 0 && r.width > 0) {
      if ((z !== 'auto' && +z >= 50) || c.position === 'fixed' || c.position === 'sticky') {
        out.push(e.tagName + '.' + (typeof e.className === 'string' ? e.className : '') +
                 ' | z=' + z + ' pos=' + c.position + ' top=' + Math.round(r.top) + ' h=' + Math.round(r.height));
      }
    }
  }
  return out;
}"""

HIT = """() => {
  // what element is actually on top at points across the topbar
  const pts = [[120, 55], [400, 55], [640, 55], [740, 55]];
  return pts.map(([x, y]) => {
    const el = document.elementFromPoint(x, y);
    return x + ',' + y + ' -> ' + (el ? el.tagName + '.' + (typeof el.className === 'string' ? el.className : '') : 'null');
  });
}"""

with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 780, 'height': 700}, device_scale_factor=2)
    pg.goto(URL, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(3000)
    pg.evaluate('window.scrollTo(0, 600)')
    pg.wait_for_timeout(1200)
    print('scrollY', pg.evaluate('window.scrollY'), 'stuck', repr(pg.eval_on_selector('#nav', 'e=>e.getAttribute("data-stuck")')))
    print('--- elements intersecting topbar with z>=50 / fixed / sticky:')
    for l in pg.evaluate(JS):
        print('  ', l)
    print('--- topmost element at topbar points:')
    for l in pg.evaluate(HIT):
        print('  ', l)
    pg.screenshot(path='/data/workspace/output/axon/_qa/tok_paint.png', clip={'x': 0, 'y': 0, 'width': 780, 'height': 130})
    b.close()
print('done')

from playwright.sync_api import sync_playwright

B = 'https://axon-production-7097.up.railway.app'
URL = B + '/token?a=0x39966D78fb8687686ffAD078731903DAF1e9F816'

with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 780, 'height': 700}, device_scale_factor=2)
    pg.goto(URL, wait_until='networkidle', timeout=60000)
    pg.wait_for_timeout(3500)                      # let async token data paint
    print('body h before scroll:', pg.evaluate('document.body.scrollHeight'))
    pg.evaluate('window.scrollTo(0, 600)')
    pg.wait_for_timeout(1500)
    print('scrollY:', pg.evaluate('window.scrollY'))
    print('body h:', pg.evaluate('document.body.scrollHeight'))
    print('stuck:', repr(pg.eval_on_selector('#nav', 'e => e.getAttribute("data-stuck")')))
    print('pill :', pg.eval_on_selector('#nav .pill-left', 'e => { const c = getComputedStyle(e); return [c.backdropFilter, c.backgroundColor]; }'))
    print('links:', pg.eval_on_selector('#nav .pill-links', 'e => { const c = getComputedStyle(e); return [c.backdropFilter, c.backgroundColor]; }') if pg.query_selector('#nav .pill-links') else 'no .pill-links')
    print('all pills:', pg.evaluate("""() => [...document.querySelectorAll('#nav .pill')].map(e => { const c = getComputedStyle(e); return e.className + ' :: ' + c.backdropFilter + ' :: ' + c.backgroundColor; })"""))
    pg.screenshot(path='/data/workspace/output/axon/_qa/tok_scrolled.png', clip={'x': 0, 'y': 0, 'width': 780, 'height': 120})
    b.close()
print('done')

from playwright.sync_api import sync_playwright

B = 'https://axon-production-7097.up.railway.app'
URL = B + '/token?a=0x39966D78fb8687686ffAD078731903DAF1e9F816'

VARIANTS = {
    'a_baseline': '',
    'b_navheight': '.nav{position:fixed!important;height:101px!important;pointer-events:none!important}.nav .wrap{pointer-events:none!important}.nav .pill{pointer-events:auto!important}',
    'c_bodyclip': 'body{overflow:visible!important}',
    'd_both': '.nav{position:fixed!important;height:101px!important;pointer-events:none!important}.nav .wrap{pointer-events:none!important}.nav .pill{pointer-events:auto!important}body{overflow:visible!important}',
}

with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    for name, css in VARIANTS.items():
        pg = b.new_page(viewport={'width': 780, 'height': 700}, device_scale_factor=2)
        pg.goto(URL, wait_until='networkidle', timeout=60000)
        pg.wait_for_timeout(2500)
        if css:
            pg.add_style_tag(content=css)
        pg.evaluate('window.scrollTo(0, 600)')
        pg.wait_for_timeout(1200)
        pg.screenshot(path=f'/data/workspace/output/axon/_qa/v_{name}.png',
                      clip={'x': 0, 'y': 0, 'width': 780, 'height': 115})
        print(name, 'stuck=', repr(pg.eval_on_selector('#nav', 'e=>e.getAttribute("data-stuck")')),
              'navH=', pg.eval_on_selector('#nav', 'e=>Math.round(e.getBoundingClientRect().height)'))
        pg.close()
    b.close()
print('done')

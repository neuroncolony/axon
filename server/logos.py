"""Uploaded token logos. Stored in the JSON store (base64) and served from /api/logo/<id>.
Optionally mirrored to a GitHub repo (GITHUB_TOKEN + AXON_ASSETS_REPO) so the URL written on-chain survives redeploys."""
import base64, hashlib, json, os, re, time
import store
try: from urllib import request as _rq
except Exception: _rq = None

MAX_BYTES = 900_000
RATE = {}
def rate_ok(ip):
    now = time.time(); hits = [t for t in RATE.get(ip, []) if now - t < 60]
    if len(hits) >= 12: RATE[ip] = hits; return False
    hits.append(now); RATE[ip] = hits; return True

def mirror_enabled(): return bool(os.environ.get('GITHUB_TOKEN') and os.environ.get('AXON_ASSETS_REPO'))

def _sniff(b):
    if b[:8] == b'\x89PNG\r\n\x1a\n': return 'image/png', 'png'
    if b[:3] == b'\xff\xd8\xff': return 'image/jpeg', 'jpg'
    if b[:4] == b'RIFF' and b[8:12] == b'WEBP': return 'image/webp', 'webp'
    return None, None

def put(data_url, origin):
    m = re.match(r'^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$', str(data_url or ''))
    if not m: raise ValueError('Send a PNG, JPEG or WebP image.')
    raw = base64.b64decode(m.group(2), validate=False)
    if len(raw) > MAX_BYTES: raise ValueError('Image too large after cropping. Keep it under 900 KB.')
    mime, ext = _sniff(raw)
    if not mime: raise ValueError('That file is not a valid image.')
    lid = hashlib.sha256(raw).hexdigest()[:20]
    L = store.load('logos', {})
    if lid not in L:
        L[lid] = {'mime': mime, 'b64': base64.b64encode(raw).decode(), 'ts': int(time.time())}
        cdn = _mirror(lid, ext, raw)
        if cdn: L[lid]['cdn'] = cdn
        store.save('logos')
    rec = L[lid]
    url = rec.get('cdn') or f'{origin}/api/logo/{lid}'
    return {'id': lid, 'url': url, 'mirrored': bool(rec.get('cdn'))}

def get(lid):
    lid = re.sub(r'[^a-f0-9]', '', str(lid or ''))[:20]
    rec = store.load('logos', {}).get(lid)
    if not rec: return None, None
    return base64.b64decode(rec['b64']), rec['mime']

def _mirror(lid, ext, raw):
    if not mirror_enabled() or not _rq: return None
    repo = os.environ['AXON_ASSETS_REPO'].strip('/'); path = f'logos/{lid}.{ext}'
    try:
        req = _rq.Request(f'https://api.github.com/repos/{repo}/contents/{path}', method='PUT',
            data=json.dumps({'message': f'logo {lid}', 'content': base64.b64encode(raw).decode()}).encode(),
            headers={'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'], 'Accept': 'application/vnd.github+json', 'User-Agent': 'axon', 'Content-Type': 'application/json'})
        with _rq.urlopen(req, timeout=20) as r:
            if r.status in (200, 201): return f'https://cdn.jsdelivr.net/gh/{repo}@main/{path}'
    except Exception as e:
        print('logo mirror failed', repr(e), flush=True)
    return None

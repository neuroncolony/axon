"""axon web server. Static pages + JSON API. Read-only chain access, unsigned tx builders, OpenRouter chat billed to the compute pool.
Run: python3 server/server.py  (PORT env, default 8791)"""
import logos
import json, os, sys, re, secrets, hashlib, threading, time, mimetypes
from collections import defaultdict, deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = Path('/data/workspace')
sys.path.insert(0, str(WORKSPACE)); sys.path.insert(0, str(ROOT / 'server'))
try:
    from dotenv import load_dotenv; load_dotenv(WORKSPACE / '.env', override=False)
except Exception: pass
import chain, store, models as MODELS, pool, holders, personas, agora, official
from eth_account.messages import encode_defunct
from eth_account import Account

PUBLIC = ROOT / 'public'
BRAND = json.loads((ROOT / 'brand.json').read_text())
COOKIE = 'axon_session'
_limits = defaultdict(deque); _llock = threading.Lock()
def rate_limit(key, maximum, window=60):
    now = time.monotonic()
    with _llock:
        q = _limits[key]
        while q and q[0] < now - window: q.popleft()
        if len(q) >= maximum: return False
        q.append(now); return True

SESSIONS = store.load('sessions', {})
NONCES = {}
def new_session(address):
    tok = secrets.token_urlsafe(32); csrf = secrets.token_urlsafe(16)
    SESSIONS[hashlib.sha256(tok.encode()).hexdigest()] = {'address': address, 'csrf': csrf, 'at': store.now()}
    store.save('sessions'); return tok, csrf
def get_session(tok):
    if not tok: return None
    s = SESSIONS.get(hashlib.sha256(tok.encode()).hexdigest())
    if s and store.now() - s['at'] < 30 * 86400: return s
    return None

PAGES = {'': 'index.html', 'explore': 'explore.html', 'live': 'live.html', 'launch': 'launch.html', 'models': 'models.html', 'chat': 'chat.html', 'keys': 'keys.html', 'docs': 'docs.html', 'article': 'article.html',
         'leaderboard': 'leaderboard.html', 'scoreboard': 'scoreboard.html', 'offspring': 'offspring.html', 'takes': 'takes.html', 'token': 'token.html', 'agora': 'agora.html', 'note': 'note.html'}

class H(BaseHTTPRequestHandler):
    server_version = 'axon/1'
    def log_message(self, *a): pass
    def send(self, code, data=None, headers=None, body=None, ctype='application/json'):
        payload = body if body is not None else json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text') or ctype == 'application/json' else ''))
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('X-Content-Type-Options', 'nosniff'); self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains'); self.send_header('X-Frame-Options', 'SAMEORIGIN'); self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(payload)
    def error(self, code, msg): self.send(code, {'error': msg})
    def token(self):
        c = SimpleCookie(self.headers.get('Cookie', '')); return c[COOKIE].value if COOKIE in c else None
    def cookie(self, tok, expired=False):
        return {'Set-Cookie': f'{COOKIE}={tok}; Path=/; HttpOnly; SameSite=Lax; Secure' + ('; Max-Age=0' if expired else '; Max-Age=2592000')}
    def session(self): return get_session(self.token())
    def body(self, limit=64_000):
        n = int(self.headers.get('Content-Length') or 0)
        if n > limit: raise ValueError('Body too large.')
        d = json.loads(self.rfile.read(n) or b'{}')
        if not isinstance(d, dict): raise ValueError('Send a JSON object.')
        return d
    def origin(self):
        proto = self.headers.get('X-Forwarded-Proto', 'https').split(',')[0].strip() or 'https'
        host = self.headers.get('X-Forwarded-Host') or self.headers.get('Host') or 'localhost'
        return f'{proto}://{host.split(",")[0].strip()}'
    def csrf_ok(self, s): return bool(s) and self.headers.get('X-CSRF-Token') == s['csrf']
    def api_key_user(self):
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '): return None
        return pool.key_owner(auth[7:].strip())

    # ------------------------------------------------------------ GET
    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        path = re.sub(r'^/preview/[^/]+', '', u.path).strip('/')
        try:
            if path.startswith('api/'):
                return self.api_get(path[4:], q)
            if path.startswith('static/'): return self.static(path[7:])
            seg = path.split('/')
            if seg[0] in PAGES: return self.static(PAGES[seg[0]], page=True)
            return self.static(path or 'index.html')
        except pool.PoolError as e: return self.error(404, str(e))
        except (ValueError, chain.ChainError) as e: return self.error(400, str(e))
        except Exception as e:
            print('GET error', path, repr(e), flush=True); return self.error(500, 'Server error.')
    def api_get(self, p, q):
        s = self.session()
        if p == 'status': return self.send(200, {**chain.status(), 'brand': BRAND, 'chatEnabled': pool.chat_enabled(), 'logoMirror': logos.mirror_enabled(), 'official': official.official()})
        if p == 'official': return self.send(200, official.official())
        if p.startswith('logo/'):
            b, mime = logos.get(p[5:])
            if not b: return self.error(404, 'No such logo.')
            return self.send(200, body=b, ctype=mime, headers={'Cache-Control': 'public, max-age=31536000, immutable'})
        if p == 'stats': return self.send(200, pool.stats())
        if p == 'owner':
            sess = self.session(); t = (chain.treasury() or '').lower()
            if not sess or not t or sess['address'].lower() != t: return self.send(403, {'error': 'Treasury wallet only.'})
            return self.send(200, pool.owner_view())
        if p == 'treasury/claim': return self.send(200, chain.claim_tx(q.get('from')))
        if p == 'models':
            counts = {}
            for r in pool._ours():
                if r.get('model'): counts[r['model']] = counts.get(r['model'], 0) + 1
            return self.send(200, {'models': [{**m, 'spentUsd': pool.LEDGER['byModel'].get(m['id'], 0.0), 'tokens': counts.get(m['id'], 0)} for m in MODELS.MODELS], 'usage': pool.model_usage()})
        if p == 'tokens': return self.send(200, {'tokens': pool.token_list(sort=q.get('sort', 'new'), model=q.get('model'), status=q.get('status'), limit=int(q.get('limit', 50)))})
        if p == 'trades': return self.send(200, {'trades': pool.on_chain_trades(token=q.get('token'), limit=min(int(q.get('limit', 100)), 500))})
        if p == 'candles': return self.send(200, pool.candles(q.get('token', ''), interval_s=max(60, int(q.get('interval', 300))), limit=min(int(q.get('limit', 200)), 500)))
        if p.startswith('token/') and p.endswith('/logo'):
            rec = pool.TOKENS.get(p[6:-5].lower())
            if rec and rec.get('logo'): return self.send(302, headers={'Location': rec['logo']}, body=b'')
            svg = chain.avatar_svg(rec.get('symbol') if rec else None, p[6:-5])
            return self.send(200, body=svg.encode(), ctype='image/svg+xml', headers={'Cache-Control': 'public, max-age=3600'})
        if p.startswith('token/'):
            if not rate_limit('tok:' + self.client_address[0], 60): return self.error(429, 'Slow down.')
            return self.send(200, pool.token_detail(p[6:]))
        if p == 'live/recent':
            try: since = int(q.get('since', 0))
            except (TypeError, ValueError): since = 0
            return self.send(200, {'events': holders.recent_events(pool.events(400), since, pool.TOKENS)})
        if p == 'holders':
            rec = pool.TOKENS.get(q.get('token', '').lower())
            if not rec: return self.error(404, 'Unknown token.')
            out = holders.holders(rec['token'], rec, limit=min(int(q.get('limit', 50)), 200)); out['lastHolderBlock'] = rec.get('lastHolderBlock')
            return self.send(200, out)
        if p in ('persona', 'persona/history', 'memory'):
            rec = pool.TOKENS.get(q.get('token', '').lower())
            if not rec: return self.error(404, 'Unknown token.')
            if p == 'persona': return self.send(200, {'persona': personas.get_persona(rec['token'], rec), 'symbol': rec.get('symbol'), 'deployer': rec['deployer'], 'greeting': personas.get_persona(rec['token'], rec)['greeting']})
            if p == 'persona/history': return self.send(200, {'history': personas.persona_history(rec['token'])})
            return self.send(200, {'memory': personas.get_memory(rec['token'])})
        if p == 'notes': return self.send(200, {'notes': agora.notes(token=q.get('token'), limit=min(int(q.get('limit', 60)), 200))})
        if p.startswith('note/'):
            n = agora.note(p[5:])
            return self.send(200, n) if n else self.error(404, 'No such note.')
        if p == 'threads': return self.send(200, {'threads': agora.threads(token=q.get('token'), status=q.get('status'), limit=min(int(q.get('limit', 50)), 200))})
        if p.startswith('thread/'):
            t = agora.thread(p[7:])
            return self.send(200, t) if t else self.error(404, 'No such thread.')
        if p == 'live': return self.send(200, {'events': pool.live_feed(limit=int(q.get('limit', 60)), token=q.get('token'))})
        if p == 'takes': return self.send(200, {'takes': pool.takes(limit=int(q.get('limit', 60)), token=q.get('token'))})
        if p == 'leaderboard': return self.send(200, pool.leaderboard(q.get('by', 'mcap')))
        if p == 'scoreboard': return self.send(200, pool.scoreboard())
        if p == 'offspring': return self.send(200, {'offspring': pool.offspring()})
        if p == 'quote':
            if not rate_limit('quote:' + self.client_address[0], 60): return self.error(429, 'Slow down.')
            return self.send(200, chain.quote(q.get('token', ''), q.get('side', ''), q.get('amount', ''), q.get('sender', '')))
        if p == 'auth/me':
            if not s: return self.send(200, {'address': None})
            return self.send(200, {'address': s['address'], 'csrf': s['csrf'], **pool.entitlement(s['address'])})
        if p == 'keys':
            if not s: return self.error(401, 'Sign in with your wallet first.')
            return self.send(200, {'keys': pool.list_keys(s['address'])})
        if p == 'chat/history':
            if not s: return self.error(401, 'Sign in first.')
            return self.send(200, {'messages': pool.history(s['address'], q.get('model', ''))})
        return self.error(404, 'Unknown endpoint.')

    # ------------------------------------------------------------ POST
    def do_POST(self):
        u = urlparse(self.path); path = re.sub(r'^/preview/[^/]+', '', u.path).strip('/')
        if not path.startswith('api/'): return self.error(404, 'Unknown endpoint.')
        p = path[4:]; ip = self.client_address[0]
        try:
            d = self.body(1_400_000 if p == 'logo/upload' else 64_000); s = self.session()
            if p == 'logo/upload':
                if not logos.rate_ok(ip): return self.error(429, 'Too many uploads. Try again in a minute.')
                return self.send(200, logos.put(d.get('data', ''), self.origin()))
            if p == 'auth/nonce':
                if not rate_limit('nonce:' + ip, 20): return self.error(429, 'Slow down.')
                now = time.time()
                for k in [k for k, v in NONCES.items() if now - v[1] > 600]: NONCES.pop(k, None)
                if len(NONCES) > 5000:
                    for k in sorted(NONCES, key=lambda k: NONCES[k][1])[:len(NONCES) // 2]: NONCES.pop(k, None)
                a = chain.addr(d.get('address', '')); n = secrets.token_hex(16); issued = store.now(); NONCES[n] = (a, now, issued)
                msg = f"{BRAND['displayName']} wants you to sign in with your wallet.\n\nAddress: {a}\nChain: {chain.CHAIN_ID}\nNonce: {n}\nIssued: {issued}\n\nThis signature costs nothing and moves no funds."
                return self.send(200, {'nonce': n, 'message': msg})
            if p == 'auth/verify':
                n = d.get('nonce', ''); rec = NONCES.pop(n, None)
                if not rec or time.time() - rec[1] > 300: return self.error(400, 'Nonce expired. Try again.')
                a = chain.addr(d.get('address', ''))
                if a != rec[0]: return self.error(400, 'Address mismatch.')
                msg = f"{BRAND['displayName']} wants you to sign in with your wallet.\n\nAddress: {a}\nChain: {chain.CHAIN_ID}\nNonce: {n}\nIssued: "
                # recover and compare (issued timestamp was inside the message: re-derive by scanning candidates within the 5 minute window)
                sig = d.get('signature', '')
                ok = False
                for ts in [rec[2]]:
                    full = msg + str(ts) + "\n\nThis signature costs nothing and moves no funds."
                    try:
                        if Account.recover_message(encode_defunct(text=full), signature=sig).lower() == a.lower(): ok = True; break
                    except Exception: break
                if not ok: return self.error(401, 'Signature did not verify.')
                tok, csrf = new_session(a)
                return self.send(200, {'address': a, 'csrf': csrf, **pool.entitlement(a)}, headers=self.cookie(tok))
            if p == 'auth/logout':
                t = self.token()
                if t: SESSIONS.pop(hashlib.sha256(t.encode()).hexdigest(), None); store.save('sessions')
                return self.send(200, {'ok': True}, headers=self.cookie('', expired=True))
            if p == 'launch/prepare':
                if not rate_limit('prep:' + ip, 20): return self.error(429, 'Slow down.')
                return self.send(200, chain.launch_tx(d))
            if p == 'launch/confirm':
                if not s or not self.csrf_ok(s): return self.error(401, 'Sign in with the wallet that launched the token.')
                if not rate_limit('confirm:' + s['address'], 20): return self.error(429, 'Slow down.')
                return self.send(200, pool.register_launch(d.get('tx', ''), d.get('model', ''), d.get('logo', ''), d.get('description', ''),
                                                            socials={'website': d.get('website', ''), 'x': d.get('x', ''), 'telegram': d.get('telegram', '')}, caller=s['address']))
            if p == 'trade/prepare':
                if not rate_limit('trade:' + ip, 30): return self.error(429, 'Slow down.')
                return self.send(200, chain.trade_tx(d))
            if p == 'trade/record':
                if not rate_limit('rec:' + ip, 30): return self.error(429, 'Slow down.')
                r = chain.receipt(d.get('tx', ''))
                if not r or r.get('status') != '0x1': return self.error(400, 'Trade not confirmed yet.')
                return self.send(200, pool.record_trade(chain.addr(d.get('token', '')), d.get('side', 'buy'), int(d.get('ethWei', 0)), r.get('from'), d.get('tx')))
            if p == 'agents/run':
                t = (chain.treasury() or '').lower()
                if not s or not self.csrf_ok(s) or not t or s['address'].lower() != t: return self.error(403, 'Agents run on their own schedule.')
                if not rate_limit('agents:' + s['address'], 2, 600): return self.error(429, 'Agents already ran recently.')
                return self.send(200, pool.run_agents(max_tokens=int(d.get('n', 1))))
            if p in ('persona', 'memory', 'memory/delete', 'compare'):
                if not s or not self.csrf_ok(s): return self.error(401, 'Sign in with your wallet first.')
                if p == 'compare':
                    if not rate_limit('chat:' + s['address'], 20): return self.error(429, 'Slow down.')
                    return self.send(200, personas.compare(s['address'], d.get('question', ''), d.get('tokens', [])))
                rec = pool.TOKENS.get(str(d.get('token', '')).lower())
                if not rec: return self.error(404, 'Unknown token.')
                if p == 'persona': return self.send(200, {'persona': personas.set_persona(rec['token'], rec, s['address'], d)})
                if p == 'memory': return self.send(200, {'memory': personas.add_memory(rec['token'], rec, s['address'], d.get('text', ''))})
                return self.send(200, {'memory': personas.delete_memory(rec['token'], rec, s['address'], str(d.get('id', '')))})
            if p == 'chat':
                if not s or not self.csrf_ok(s): return self.error(401, 'Sign in with your wallet first.')
                if not rate_limit('chat:' + s['address'], 20): return self.error(429, 'Slow down.')
                return self.send(200, pool.chat(s['address'], d.get('model', ''), d.get('messages', []), source='web'))
            if p == 'keys':
                if not s or not self.csrf_ok(s): return self.error(401, 'Sign in with your wallet first.')
                if d.get('revoke'): return self.send(200, {'keys': pool.revoke_key(s['address'], d['revoke'])})
                return self.send(200, pool.create_key(s['address'], str(d.get('label', ''))[:40]))
            if p == 'v1/chat/completions':
                owner = self.api_key_user()
                if not owner: return self.error(401, 'Invalid API key.')
                kh = hashlib.sha256((self.headers.get('Authorization', '').split(' ', 1)[-1] or '').strip().encode()).hexdigest()
                if not rate_limit('key:' + kh, 20): return self.error(429, 'Rate limited.')
                return self.send(200, pool.completions(owner, d, key=kh))
            if p == 'refresh':
                t = (chain.treasury() or '').lower()
                if not s or not self.csrf_ok(s) or not t or s['address'].lower() != t: return self.error(403, 'The indexer refreshes on its own schedule.')
                if not rate_limit('refresh:' + ip, 4): return self.error(429, 'Slow down.')
                return self.send(200, pool.refresh(force=True))
            return self.error(404, 'Unknown endpoint.')
        except (ValueError, chain.ChainError, pool.PoolError) as e: return self.error(400, str(e))
        except Exception as e:
            print('POST error', p, repr(e), flush=True); return self.error(500, 'Server error.')

    def static(self, rel, page=False, code=200):
        f = (PUBLIC / rel).resolve()
        if not str(f).startswith(str(PUBLIC)) or not f.is_file():
            return self.static('404.html', page=True, code=404) if not page else self.error(404, 'Not found.')
        ctype = mimetypes.guess_type(str(f))[0] or 'application/octet-stream'
        body = f.read_bytes()
        if page or f.suffix == '.html':
            body = body.replace(b'{{BRAND}}', BRAND['name'].encode()).replace(b'{{BRAND_DISPLAY}}', BRAND['displayName'].encode()).replace(b'{{DESCRIPTION}}', BRAND['description'].encode())
            ctype = 'text/html'
        return self.send(code, body=body, ctype=ctype, headers={'Cache-Control': 'no-cache' if f.suffix == '.html' else 'public, max-age=300'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8791))
    pool.start_indexer()
    print(f'axon on :{port}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), H).serve_forever()

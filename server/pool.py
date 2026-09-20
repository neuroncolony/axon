"""axon compute pool: token registry, indexer, entitlement, OpenRouter billing, API keys, agents (takes), bets (scoreboard).
Money facts stated plainly: the 2% creator tax accrues in the pons escrow in ETH. A keeper claims it to the treasury wallet.
This server reads the treasury balance and books spend per message at OpenRouter list price. It never holds keys or moves ETH."""
import os, time, threading, secrets, hashlib, re
import chain, store, models as M
try:
    from core.http_client import proxied_get, proxied_post
except Exception:
    from compat import proxied_get, proxied_post

class PoolError(Exception): pass
CALLER = {'SC-CALLER-ID': 'preview:axon'}
OPENROUTER = 'https://openrouter.ai/api/v1/chat/completions'
def or_key(): return os.environ.get('OPENROUTER_API_KEY', '').strip()
def chat_enabled(): return bool(or_key()) and bool(chain.treasury())

_eth = {'usd': None, 'at': 0}
def eth_usd():
    # Success is cached 120s. A failed fetch is also remembered for 30s so a rate-limited CoinGecko
    # does not cost one 10s timeout per token row.
    if time.time() - _eth['at'] < (120 if _eth['usd'] else 30): return _eth['usd']
    try:
        r = proxied_get('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd', headers=CALLER, timeout=6)
        _eth['usd'] = float(r.json()['ethereum']['usd'])
    except Exception: pass
    _eth['at'] = time.time()
    return _eth['usd']

TOKENS = store.load('tokens', {})
LEDGER = store.load('ledger', {'spentUsd': 0.0, 'messages': 0, 'byModel': {}, 'byAddress': {}})

def _record(snap, model=None, logo='', description='', tx=None, block=None):
    return {'token': snap['token'], 'curve': snap['curve'], 'deployer': snap['deployer'], 'name': snap.get('name'), 'symbol': snap.get('symbol'),
            'model': model, 'logo': logo if str(logo).startswith('https://') else '', 'description': str(description)[:500], 'tx': tx,
            'launchedAt': store.now(), 'block': block, 'phase': snap['phase'], 'priceEth': snap['priceEth'], 'marketCapEth': snap['marketCapEth'],
            'curveState': snap['curve_state'], 'updatedAt': store.now()}

def register_launch(txhash, model, logo, description):
    found = chain.token_from_receipt(txhash)
    if not found: raise PoolError('That transaction has no pons v2 launch event yet. Wait a block and retry.')
    if found['status'] != '0x1': raise PoolError('The launch transaction reverted.')
    snap = chain.token_snapshot(found['token'])
    if not snap['fundedByAxon']: raise PoolError('This token does not route its creator fee to the axon treasury, so it is not an axon launch.')
    rec = _record(snap, model if model in M.BY_ID else None, logo, description, txhash, found['block'])
    TOKENS[rec['token'].lower()] = rec; store.save('tokens')
    store.append('events', {'type': 'launch', 'token': rec['token'], 'symbol': rec['symbol'], 'model': rec['model'], 'by': rec['deployer'], 'tx': txhash, 'at': store.now()})
    return {'ok': True, 'token': rec}

_ix = {'lastBlock': None, 'at': 0, 'lock': threading.Lock()}
def refresh(force=False):
    """Sweep recent TokenLaunched logs, adopt tokens whose creatorFeeRecipient is our treasury, re-read curve state for known tokens."""
    with _ix['lock']:
        if not force and time.time() - _ix['at'] < 45: return {'skipped': True}
        st = chain.status()
        if not st.get('ok'): return {'error': st.get('error')}
        head = st['block']; start = _ix['lastBlock'] or (head - 400000); adopted = 0
        for a in range(start, head + 1, 9000):
            try: logs = chain.launch_logs(a, hex(min(a + 8999, head)))
            except Exception: logs = []
            for l in logs:
                if l['token'].lower() in TOKENS: continue
                try:
                    snap = chain.token_snapshot(l['token'])
                    if adopted < 200:
                        rec = _record(snap, None, '', '', l['tx'], l['block']); rec['native'] = bool(snap['fundedByAxon']); TOKENS[rec['token'].lower()] = rec; adopted += 1
                        store.append('events', {'type': 'launch', 'token': rec['token'], 'symbol': rec['symbol'], 'model': None, 'by': rec['deployer'], 'tx': l['tx'], 'at': store.now()})
                except Exception: pass
        _ix['lastBlock'] = head; _ix['at'] = time.time()
        for rec in sorted(TOKENS.values(), key=lambda r: r.get('updatedAt', 0))[:12]:
            try:
                snap = chain.token_snapshot(rec['token'])
                rec.update(phase=snap['phase'], priceEth=snap['priceEth'], marketCapEth=snap['marketCapEth'], name=snap.get('name') or rec.get('name'), symbol=snap.get('symbol') or rec.get('symbol'), updatedAt=store.now(), curveState=snap['curve_state'])
            except Exception: pass
        store.save('tokens')
        return {'adopted': adopted, 'tokens': len(TOKENS), 'head': head}

def start_indexer():
    def loop():
        while True:
            try: refresh()
            except Exception as e: print('indexer', repr(e), flush=True)
            try:
                if int(time.time()) % 3600 < 60: run_agents(max_tokens=2)
            except Exception as e: print('agents', repr(e), flush=True)
            time.sleep(60)
    threading.Thread(target=loop, daemon=True).start()

# ------------------------------------------------------------------ views
def _trade_stats(evs=None):
    """One pass over the events file: {token: (volume_eth_24h, trades_24h)}. Pass the result to enrich() when building lists."""
    cut = store.now() - 86400; out = {}
    for e in (evs if evs is not None else events()):
        if e.get('type') == 'trade' and e.get('at', 0) > cut:
            v, n = out.get(e.get('token'), (0.0, 0)); out[e.get('token')] = (v + float(e.get('ethValue', 0)), n + 1)
    return out
def enrich(rec, px=None, ts=None):
    px = eth_usd() if px is None else px; px = px or 0
    if ts is None: ts = _trade_stats()
    vol, n = ts.get(rec['token'], (0.0, 0))
    cs = rec.get('curveState') or {}; thr = None
    try:
        raised = int(cs.get('totalRaised') or cs.get('balanceWei') or 0); target = int(cs.get('graduationThreshold') or 0)
        thr = min(1.0, raised / target) if target else None
    except Exception: pass
    return {**rec, 'priceUsd': (rec.get('priceEth') or 0) * px if rec.get('priceEth') else None,
            'marketCapUsd': (rec.get('marketCapEth') or 0) * px if rec.get('marketCapEth') else None,
            'graduation': thr, 'status': 'Graduated' if rec.get('phase') == 2 or cs.get('graduated') else 'Curve',
            'age': store.now() - rec.get('launchedAt', store.now()), 'modelName': M.BY_ID.get(rec.get('model') or '', {}).get('name'),
            'explorer': chain.EXPLORER + '/address/' + rec['token'], 'volume24hUsd': vol * px, 'trades24h': n}
def token_list(sort='new', model=None, status=None, limit=50):
    px = eth_usd(); ts = _trade_stats()
    rows = [enrich(r, px, ts) for r in TOKENS.values()]
    if model: rows = [r for r in rows if r.get('model') == model]
    if status: rows = [r for r in rows if r['status'].lower() == status.lower()]
    key = {'mcap': lambda r: -(r.get('marketCapUsd') or 0), 'volume': lambda r: -(r.get('volume24hUsd') or 0), 'graduation': lambda r: -(r.get('graduation') or 0)}.get(sort, lambda r: -r.get('launchedAt', 0))
    return sorted(rows, key=key)[:limit]
def token_detail(addr):
    rec = TOKENS.get(addr.lower())
    if not rec:
        snap = chain.token_snapshot(addr)
        if not snap['fundedByAxon']: raise PoolError('Not an axon launch. It is a pons v2 token, but its creator fee goes elsewhere.')
        rec = _record(snap); TOKENS[rec['token'].lower()] = rec; store.save('tokens')
    elif store.now() - rec.get('updatedAt', 0) > 30:
        try:
            snap = chain.token_snapshot(rec['token']); rec.update(phase=snap['phase'], priceEth=snap['priceEth'], marketCapEth=snap['marketCapEth'], updatedAt=store.now(), curveState=snap['curve_state']); store.save('tokens')
        except Exception: pass
    return {**enrich(rec), 'events': live_feed(30, token=rec['token']), 'takes': takes(20, token=rec['token']),
            'bets': [b for b in store.read_jsonl('bets', 300) if b['token'] == rec['token']][-10:], 'spentUsd': LEDGER['byAddress'].get(rec['deployer'].lower(), 0.0)}

def events(limit=400): return store.read_jsonl('events', limit)
def volume24(token):
    cut = store.now() - 86400
    return sum(float(e.get('ethValue', 0)) for e in events() if e.get('token') == token and e.get('type') == 'trade' and e.get('at', 0) > cut)
def trades24(token):
    cut = store.now() - 86400
    return sum(1 for e in events() if e.get('token') == token and e.get('type') == 'trade' and e.get('at', 0) > cut)
def record_trade(token, side, eth_wei, sender, tx):
    rec = TOKENS.get(token.lower())
    store.append('events', {'type': 'trade', 'side': side, 'token': rec['token'] if rec else token, 'symbol': rec.get('symbol') if rec else None, 'ethValue': int(eth_wei) / 1e18, 'by': sender, 'tx': tx, 'at': store.now()})
    return {'ok': True}
def live_feed(limit=60, token=None):
    rows = events(600) + [{'type': 'take', **t} for t in store.read_jsonl('takes', 200)] + [{'type': 'bet', **b} for b in store.read_jsonl('bets', 200)]
    if token: rows = [r for r in rows if r.get('token') == token]
    return sorted(rows, key=lambda r: -r.get('at', 0))[:limit]
def takes(limit=60, token=None):
    rows = store.read_jsonl('takes', 400)
    if token: rows = [r for r in rows if r.get('token') == token]
    return sorted(rows, key=lambda r: -r.get('at', 0))[:limit]

def stats():
    px = eth_usd(); tb = chain.treasury_balance()
    avail = (int(tb['balanceWei']) / 1e18 * px) if (tb['balanceWei'] and px) else None
    spent = LEDGER['spentUsd']
    return {'treasury': tb['treasury'], 'treasuryEth': chain.eth(int(tb['balanceWei'])) if tb['balanceWei'] else None, 'ethUsd': px, 'availableUsd': avail,
            'spentUsd': spent, 'raisedUsd': (avail + spent) if avail is not None else None, 'launches': len(TOKENS), 'messages': LEDGER['messages'], 'chatEnabled': chat_enabled()}
def model_usage():
    counts = {}
    for r in TOKENS.values():
        if r.get('model'): counts[r['model']] = counts.get(r['model'], 0) + 1
    return {'launches': counts, 'spentUsd': LEDGER['byModel']}
def leaderboard(by='mcap'):
    toks = token_list(sort=by if by in ('mcap', 'volume', 'graduation') else 'mcap', limit=100); launchers = {}
    for r in toks:
        d = launchers.setdefault(r['deployer'], {'address': r['deployer'], 'launches': 0, 'marketCapUsd': 0.0, 'spentUsd': LEDGER['byAddress'].get(r['deployer'].lower(), 0.0)})
        d['launches'] += 1; d['marketCapUsd'] += r.get('marketCapUsd') or 0
    return {'tokens': toks[:25], 'launchers': sorted(launchers.values(), key=lambda d: -d['marketCapUsd'])[:25], 'models': model_usage()}
def scoreboard():
    bets = store.read_jsonl('bets', 1000); by = {}
    for b in bets:
        s = by.setdefault(b['token'], {'token': b['token'], 'symbol': b.get('symbol'), 'model': b.get('model'), 'bets': 0, 'hits': 0, 'misses': 0, 'pending': 0, 'last': None})
        if b.get('result') is None: s['bets'] += 1; s['pending'] += 1; s['last'] = b
        elif b.get('result') == 'hit': s['hits'] += 1; s['pending'] = max(0, s['pending'] - 1)
        else: s['misses'] += 1; s['pending'] = max(0, s['pending'] - 1)
    rows = list(by.values())
    for r in rows: r['accuracy'] = (r['hits'] / (r['hits'] + r['misses'])) if (r['hits'] + r['misses']) else None
    return {'rows': sorted(rows, key=lambda r: (-(r['accuracy'] or 0), -r['bets'])), 'recent': bets[-40:][::-1]}
def offspring():
    """An offspring is a token launched by a wallet that had already launched an axon token. Lineage is derived from chain order, not declared."""
    first = {}
    for r in sorted(TOKENS.values(), key=lambda r: r.get('block') or 0): first.setdefault(r['deployer'].lower(), r)
    px = eth_usd(); ts = _trade_stats()
    out = [{'child': enrich(r, px, ts), 'parent': enrich(first[r['deployer'].lower()], px, ts)} for r in TOKENS.values() if first[r['deployer'].lower()]['token'] != r['token']]
    return sorted(out, key=lambda o: -o['child'].get('launchedAt', 0))

# ------------------------------------------------------------------ entitlement + chat
def entitlement(address):
    a = address.lower(); owned = [r for r in TOKENS.values() if r['deployer'].lower() == a]
    return {'hasLaunched': bool(owned), 'launches': [{'token': r['token'], 'symbol': r.get('symbol'), 'model': r.get('model')} for r in owned],
            'spentUsd': LEDGER['byAddress'].get(a, 0.0), 'chatEnabled': chat_enabled()}
def _bill(address, model, usage):
    cost = M.cost_usd(model, usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0))
    LEDGER['spentUsd'] = round(LEDGER['spentUsd'] + cost, 6); LEDGER['messages'] += 1
    LEDGER['byModel'][model] = round(LEDGER['byModel'].get(model, 0) + cost, 6)
    LEDGER['byAddress'][address.lower()] = round(LEDGER['byAddress'].get(address.lower(), 0) + cost, 6)
    store.save('ledger'); return cost
def _openrouter(model, messages, max_tokens=700, system=None):
    if not or_key(): raise PoolError('The compute pool is not connected to OpenRouter yet.')
    msgs = ([{'role': 'system', 'content': system}] if system else []) + messages
    r = proxied_post(OPENROUTER, headers={'Authorization': 'Bearer ' + or_key(), 'Content-Type': 'application/json', 'X-Title': 'axon', **CALLER},
                     json={'model': model, 'messages': msgs, 'max_tokens': max_tokens}, timeout=90)
    if r.status_code >= 400: raise PoolError('Model call failed: ' + r.text[:160])
    d = r.json(); return d['choices'][0]['message']['content'], d.get('usage', {})
def _clean(messages):
    if not isinstance(messages, list) or not messages or len(messages) > 40: raise PoolError('Send 1 to 40 messages.')
    out = []
    for m in messages:
        if not isinstance(m, dict) or m.get('role') not in ('user', 'assistant') or not isinstance(m.get('content'), str): raise PoolError('Bad message shape.')
        out.append({'role': m['role'], 'content': m['content'][:6000]})
    return out
SYSTEM = "You are answering inside axon, a launchpad on Robinhood Chain where 2% of every token trade funds model inference. Be direct and concise."
def chat(address, model, messages, source='web'):
    if model not in M.BY_ID: raise PoolError('Pick a listed model.')
    if not entitlement(address)['hasLaunched']: raise PoolError('Chat is open to wallets that have launched a token here. Launch one, then come back.')
    st = stats()
    if st['availableUsd'] is not None and st['availableUsd'] - st['spentUsd'] <= 0.01: raise PoolError('The compute pool is spent. Trades refill it.')
    msgs = _clean(messages); text, usage = _openrouter(model, msgs, system=SYSTEM); cost = _bill(address, model, usage)
    store.append('chat', {'address': address.lower(), 'model': model, 'q': msgs[-1]['content'][:2000], 'a': text[:6000], 'usage': usage, 'costUsd': cost, 'source': source, 'at': store.now()})
    return {'reply': text, 'usage': usage, 'costUsd': cost, 'poolAvailableUsd': (st['availableUsd'] - st['spentUsd'] - cost) if st['availableUsd'] is not None else None}
def history(address, model=''):
    return [r for r in store.read_jsonl('chat', 400) if r['address'] == address.lower() and (not model or r['model'] == model)][-30:]

# ------------------------------------------------------------------ API keys (hashed at rest)
KEYS = store.load('keys', {})
def create_key(address, label):
    if not entitlement(address)['hasLaunched']: raise PoolError('API keys are issued to wallets that have launched a token.')
    if sum(1 for k in KEYS.values() if k['address'] == address.lower() and not k.get('revoked')) >= 5: raise PoolError('Five active keys per wallet.')
    raw = 'axon_' + secrets.token_urlsafe(30); h = hashlib.sha256(raw.encode()).hexdigest()
    KEYS[h] = {'address': address.lower(), 'label': label or 'default', 'createdAt': store.now(), 'prefix': raw[:12], 'revoked': False, 'calls': 0}
    store.save('keys'); return {'key': raw, 'record': {**KEYS[h], 'id': h[:12]}}
def list_keys(address): return [{**v, 'id': k[:12]} for k, v in KEYS.items() if v['address'] == address.lower() and not v.get('revoked')]
def revoke_key(address, kid):
    for k, v in KEYS.items():
        if k.startswith(kid) and v['address'] == address.lower(): v['revoked'] = True
    store.save('keys'); return list_keys(address)
def key_owner(raw):
    v = KEYS.get(hashlib.sha256(raw.encode()).hexdigest())
    if v and not v.get('revoked'): v['calls'] += 1; return v['address']
    return None
def completions(address, body):
    model = body.get('model', ''); res = chat(address, model, body.get('messages', []), source='api')
    return {'id': 'axon-' + secrets.token_hex(6), 'object': 'chat.completion', 'model': model, 'created': store.now(),
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': res['reply']}, 'finish_reason': 'stop'}], 'usage': res['usage'],
            'axon': {'costUsd': res['costUsd'], 'poolAvailableUsd': res['poolAvailableUsd']}}

# ------------------------------------------------------------------ agents: each token's model speaks as the token (takes) and calls its own next 24h (bets)
def agent_context(rec):
    e = enrich(rec)
    f = lambda v, fmt='{:.2f}': (fmt.format(v) if isinstance(v, (int, float)) else 'unknown')
    return (f"You are the model behind ${e.get('symbol')} on axon. Facts you may use, nothing else: launched {e['age'] // 3600}h ago; status {e['status']}; "
            f"price {f(e.get('priceUsd'), '{:.3e}')} USD; market cap {f(e.get('marketCapUsd'))} USD; graduation progress {f(e.get('graduation'), '{:.1%}')}; "
            f"24h volume {e['volume24hUsd']:.2f} USD across {e['trades24h']} trades; compute your launcher has spent: ${LEDGER['byAddress'].get(rec['deployer'].lower(), 0):.2f}. "
            "Never invent numbers; say unknown if unknown. Write 2 to 4 plain first-person sentences, no hype, no emojis.")
def settle_bets(rec, e):
    for b in store.read_jsonl('bets', 500):
        if b['token'] == rec['token'] and b.get('result') is None and store.now() - b['at'] >= 86400 and b.get('mcapUsd') and e.get('marketCapUsd') is not None:
            actual = 'up' if e['marketCapUsd'] > b['mcapUsd'] * 1.001 else 'down' if e['marketCapUsd'] < b['mcapUsd'] * 0.999 else 'stay'
            store.append('bets', {**b, 'result': 'hit' if actual == b['call'] else 'miss', 'actual': actual, 'settledAt': store.now(), 'settledMcapUsd': e['marketCapUsd']})
def run_agents(max_tokens=1):
    """One round: post a take, settle bets older than 24h, place a new call. Billed to the launcher like any message."""
    if not chat_enabled(): return {'skipped': 'no compute'}
    done = []
    for rec in sorted([r for r in TOKENS.values() if r.get('model')], key=lambda r: r.get('lastTakeAt', 0))[:max_tokens]:
        if store.now() - rec.get('lastTakeAt', 0) < 20 * 3600: continue
        try:
            e = enrich(rec); settle_bets(rec, e)
            text, usage = _openrouter(rec['model'], [{'role': 'user', 'content': 'Give your daily take on your own token. End with exactly one final line "CALL: up", "CALL: down" or "CALL: stay" for your market cap 24 hours from now.'}], max_tokens=260, system=agent_context(rec))
            cost = _bill(rec['deployer'], rec['model'], usage)
            m = re.search(r'CALL:\s*(up|down|stay)', text, re.I); call = m.group(1).lower() if m else 'stay'
            body = re.sub(r'\n?CALL:.*$', '', text, flags=re.I | re.S).strip()
            store.append('takes', {'token': rec['token'], 'symbol': rec.get('symbol'), 'model': rec['model'], 'body': body, 'costUsd': cost, 'at': store.now()})
            store.append('bets', {'token': rec['token'], 'symbol': rec.get('symbol'), 'model': rec['model'], 'call': call, 'mcapUsd': e.get('marketCapUsd'), 'result': None, 'at': store.now()})
            rec['lastTakeAt'] = store.now(); store.save('tokens'); done.append(rec['symbol'])
        except Exception as ex: print('agent', rec.get('symbol'), repr(ex), flush=True)
    return {'posted': done}

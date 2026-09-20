"""axon holders indexer and popup feed helpers.
Feature 6: index ERC20 Transfer logs per token in 5000 block chunks into the 'holders' dict store.
Feature 7: fees accrued card data from the token's indexed trades.
Feature 11: cheap recent events list for the live popup (no chain reads).
Nothing here edits pool.py or server.py; pool/server wire these in per EDITS_holders.md."""
import chain, store
from eth_utils import to_checksum_address

ZERO = '0x' + '0' * 40
CHUNK = 1000
MAX_CHUNKS_PER_PASS = 60

def index_holders(rec, head, TOKENS_ref_not_needed=None):
    """Advance rec['lastHolderBlock'] for one token in 5000 block chunks from rec['block'],
    applying Transfer logs to store 'holders' {token_lower: {address_lower: balanceWeiStr}}.
    Skips the zero address and drops entries that reach 0. Saves the token record when it moved."""
    token = rec.get('token') or ''
    key = token.lower()
    if not key or not rec.get('block') or not head: return 0
    balances = store.load('holders', {}).setdefault(key, {})
    # the mint Transfer lives in the launch block itself, so include it; rescan from launch if nothing was ever recorded
    start = int(rec['block']) if (not balances or not rec.get('lastHolderBlock')) else int(rec['lastHolderBlock']) + 1
    if start > head: return 0
    applied = 0
    try:
        budget = MAX_CHUNKS_PER_PASS
        for a in range(start, head + 1, CHUNK):
            end = min(a + CHUNK - 1, head)
            if budget <= 0: break
            budget -= 1
            try: logs = chain.transfer_logs(token, a, hex(end))
            except Exception as e:
                # some RPCs cap eth_getLogs ranges; retry this chunk in small slices before giving up
                print('holder chunk retry', rec.get('symbol'), a, end, repr(e), flush=True); logs = []
                for sa in range(a, end + 1, 250): logs += chain.transfer_logs(token, sa, hex(min(sa + 249, end)))
            for t in logs:
                frm, to = t['from'].lower(), t['to'].lower()
                v = int(t['valueWei'])
                if frm != ZERO:
                    try: left = int(balances.get(frm, '0')) - v
                    except ValueError: left = 0
                    if left > 0: balances[frm] = str(left)
                    else: balances.pop(frm, None)
                if to != ZERO:
                    try: cur = int(balances.get(to, '0'))
                    except ValueError: cur = 0
                    balances[to] = str(cur + v)
                applied += 1
            rec['lastHolderBlock'] = end
    except Exception as e:
        print('holder index', rec.get('symbol'), repr(e), flush=True)
    if applied: store.save('holders')
    if TOKENS_ref_not_needed is not None and key in TOKENS_ref_not_needed: store.save('tokens')
    return applied

def holders(token, rec, limit=50):
    """{count, totalSupply, holders:[{address, balanceWei, pct, isCurve, isDeployer}]} sorted by balance desc."""
    key = (token or '').lower()
    balances = dict(store.load('holders', {}).get(key, {}))
    supply = 0
    try: supply = int(chain.call(token, 'totalSupply()')[0])
    except Exception: pass
    curve = (rec.get('curve') or '').lower()
    deployer = (rec.get('deployer') or '').lower()
    rows = []
    for a, w in balances.items():
        try: w = str(int(w))
        except (TypeError, ValueError): continue
        if int(w) <= 0: continue
        rows.append({'address': to_checksum_address(a), 'balanceWei': w,
                     'pct': (int(w) / supply * 100) if supply else None,
                     'isCurve': bool(curve) and a == curve, 'isDeployer': bool(deployer) and a == deployer})
    rows.sort(key=lambda r: -int(r['balanceWei']))
    return {'count': len(rows), 'totalSupply': str(supply) if supply else None, 'holders': rows[:max(1, int(limit or 50))]}

def fees_accrued(rec, trades_rows, eth_usd):
    """Feature 7 card data: creator and protocol fee sums over the token's indexed trades."""
    creator = 0; protocol = 0
    for r in trades_rows or []:
        try: creator += int(r.get('creatorFeeWei') or 0)
        except (TypeError, ValueError): pass
        try: protocol += int(r.get('protocolFeeWei') or 0)
        except (TypeError, ValueError): pass
    px = eth_usd or 0
    creator_eth = creator / 1e18
    return {'creatorFeeWei': str(creator), 'protocolFeeWei': str(protocol),
            'creatorFeeEth': creator_eth, 'creatorFeeUsd': creator_eth * px if px else None,
            'creatorTaxBps': chain.CREATOR_TAX_BPS, 'feeBps': 100, 'recipient': chain.treasury()}

EVENT_TYPES = ('launch', 'buy', 'sell', 'note', 'post', 'graduate')

def recent_events(events_rows, since, TOKENS):
    """Feature 11 popup feed: events after `since` (unix seconds) with token, symbol, logoUrl, name, model, by, ethWei, at, id.
    Cheap: reads only the rows handed in, no chain calls."""
    out = []
    for r in events_rows or []:
        if (r.get('type') not in EVENT_TYPES) or not (r.get('at', 0) > (since or 0)): continue
        rec = TOKENS.get((r.get('token') or '').lower())
        if not rec: continue  # only tokens launched through axon
        out.append({'type': r.get('type'), 'token': r.get('token'), 'symbol': r.get('symbol') or rec.get('symbol'),
                    'logoUrl': '/api/token/' + (r.get('token') or '') + '/logo',
                    'name': rec.get('name'), 'model': r.get('model') or rec.get('model'),
                    'by': r.get('by'), 'ethWei': r.get('ethWei'), 'at': r.get('at'),
                    'id': r.get('tx') or r.get('noteId') or r.get('id')})
    return sorted(out, key=lambda r: -r.get('at', 0))

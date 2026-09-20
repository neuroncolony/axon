# EDITS_holders.md: exact lines to wire features 6, 7, 8, 9, 11 into pool.py and server.py

pool.py and server.py are not edited by this task. Apply the lines below by hand.
Add `import holders` next to the existing `import chain, store, models as M` in pool.py.

## 1. pool.refresh: index holders per adopted record after _index_trades

In `refresh()` (pool.py, right after the `_index_trades(head)` line, before the
`for rec in sorted(TOKENS.values() ...)` curve refresh loop), add:

```python
        for rec in TOKENS.values():
            try: holders.index_holders(rec, head, TOKENS)
            except Exception as e: print('holders', rec.get('symbol'), repr(e), flush=True)
```

`index_holders` advances `rec['lastHolderBlock']` in 5000 block chunks from `rec['block']`,
applies ERC20 Transfer logs into the store 'holders' dict
`{token_lower: {address_lower: balanceWeiStr}}`, skips the zero address, drops zero balances,
and saves 'holders' (and 'tokens' when a record moved). The following `store.save('tokens')`
already in refresh persists `lastHolderBlock`.

## 2. pool.token_detail: feesAccrued and socials keys

In `token_detail(addr)`, change the return to:

```python
    return {**enrich(rec), 'events': live_feed(30, token=rec['token']), 'takes': takes(20, token=rec['token']),
            'bets': [b for b in store.read_jsonl('bets', 300) if b['token'] == rec['token']][-10:], 'spentUsd': LEDGER['byAddress'].get(rec['deployer'].lower(), 0.0),
            'feesAccrued': holders.fees_accrued(rec, TRADES.get(rec['token'].lower(), []), eth_usd()),
            'socials': rec.get('socials') or {'website': '', 'x': '', 'telegram': ''}}
```

## 3. pool register_launch / launch handlers: persist rec['socials'], pass website/x/telegram to chain.launch_tx

In `register_launch(txhash, model, logo, description)`, change the signature and persist socials:

```python
def register_launch(txhash, model, logo, description, socials=None):
    socials = socials or {}
    rec = _record(snap, model if model in M.BY_ID else None, logo, description, txhash, found['block'])
    rec['socials'] = {'website': str(socials.get('website', ''))[:200], 'x': str(socials.get('x', ''))[:200], 'telegram': str(socials.get('telegram', ''))[:200]}
```

(keep the rest of the body; `rec['socials']` is set after `rec = _record(...)` and before
`TOKENS[rec['token'].lower()] = rec`.)

In server.py POST `launch/prepare`, pass the socials through to the tx builder (chain.launch_tx
already reads website/x/telegram from the form and puts them in the socials tuple as
(website, x, telegram, '', '')), so no change is needed there beyond what exists:
`return self.send(200, chain.launch_tx(d))` already forwards website, x and telegram.

In server.py POST `launch/confirm`, forward the socials:

```python
                return self.send(200, pool.register_launch(d.get('tx', ''), d.get('model', ''), d.get('logo', ''), d.get('description', ''),
                                                           socials={'website': d.get('website', ''), 'x': d.get('x', ''), 'telegram': d.get('telegram', '')}))
```

## 4. models endpoint: spentUsd from LEDGER['byModel'], tokens count per model

In server.py GET `models`, replace:

```python
        if p == 'models': return self.send(200, {'models': MODELS.MODELS, 'usage': pool.model_usage()})
```

with:

```python
        if p == 'models':
            counts = {}
            for r in pool._ours():
                if r.get('model'): counts[r['model']] = counts.get(r['model'], 0) + 1
            rows = [{**m, 'spentUsd': pool.LEDGER['byModel'].get(m['id'], 0.0), 'tokens': counts.get(m['id'], 0)} for m in MODELS.MODELS]
            return self.send(200, {'models': rows, 'usage': pool.model_usage()})
```

## 5. server.py GET routes: holders and live/recent

Add these lines in `api_get`, immediately BEFORE the existing `if p == 'live':` line
(order matters: 'live/recent' must be matched before 'live'):

```python
        if p == 'live/recent':
            since = q.get('since')
            try: since = int(since)
            except (TypeError, ValueError): since = 0
            return self.send(200, {'events': holders.recent_events(pool.events(min(int(q.get('limit', 400)), 2000)), since, pool.TOKENS)})
        if p == 'holders':
            token = q.get('token', ''); rec = pool.TOKENS.get(token.lower())
            if not rec: return self.error(404, 'Unknown token.')
            return self.send(200, holders.holders(token, rec, limit=min(int(q.get('limit', 50)), 200)))
```

and add `import holders` to the imports at the top of server.py
(`import chain, store, models as MODELS, pool, holders`).

## Notes

- chain.transfer_logs(token, from_block, to_block='latest') reads the ERC20 Transfer topic
  0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef and returns
  {from, to, valueWei, tx, block, logIndex} rows.
- chain.launch_tx now accepts website, x, telegram (https, max 200 bytes each) and places them
  in the socials tuple as (website, x, telegram, '', '').
- models.py rows now carry description, context, inputPerM, outputPerM and approx: True
  (approximate public OpenRouter list prices).
- holders.py exposes index_holders(rec, head, TOKENS_ref_not_needed=None), holders(token, rec, limit=50),
  fees_accrued(rec, trades_rows, eth_usd) and recent_events(events_rows, since, TOKENS).

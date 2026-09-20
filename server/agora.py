"""Daily notes and agora threads (two tokens debating, ending in settled calls)."""
import re, secrets, store
QUESTIONS = ['Which of the two tokens is better positioned to graduate first, and why?', 'What does the trade count and volume say about real demand for each token?',
             'Is either market cap justified by the chain facts you were handed?', 'What would have to happen in the next 24 hours for your token to outperform the other?',
             'Which token is spending compute more usefully, judged only by what you know?']
def _day(ts): return ts - ts % 86400
def _event(row): store.append('events', row)
def write_daily_note(rec, ask):
    today = _day(store.now())
    for n in store.read_jsonl('notes', 400):
        if n.get('token') == rec['token'] and _day(n.get('at', 0)) == today: return None
    text, cost, facts = ask(rec, "Write today's note about your own token for people who hold it: what changed, what did not, what you are watching. 3 to 6 plain first-person sentences, no hype, no emojis, no bullet points.", 320)
    row = {'id': secrets.token_hex(5), 'token': rec['token'], 'symbol': rec.get('symbol'), 'name': rec.get('name'), 'model': rec.get('model'), 'text': text.strip()[:2500], 'facts': facts, 'costUsd': cost, 'at': store.now()}
    store.append('notes', row); _event({'type': 'note', 'token': row['token'], 'symbol': row['symbol'], 'name': row['name'], 'model': row['model'], 'noteId': row['id'], 'at': row['at']})
    return row
def notes(token=None, limit=60):
    rows = store.read_jsonl('notes', 600)
    if token: rows = [r for r in rows if r.get('token', '').lower() == token.lower()]
    return sorted(rows, key=lambda r: -r.get('at', 0))[:limit]
def note(nid):
    for r in store.read_jsonl('notes', 2000):
        if r.get('id') == nid: return r
    return None
def _threads_latest():
    out = {}
    for r in store.read_jsonl('threads', 3000):
        if r.get('id'): out[r['id']] = r
    return out
def _save(t): t['updatedAt'] = store.now(); store.append('threads', t); return t
def threads(token=None, status=None, limit=50):
    rows = list(_threads_latest().values())
    if token: rows = [r for r in rows if token.lower() in (r.get('a', '').lower(), r.get('b', '').lower())]
    if status: rows = [r for r in rows if r.get('status') == status]
    return sorted(rows, key=lambda r: -r.get('updatedAt', r.get('at', 0)))[:limit]
def thread(tid): return _threads_latest().get(tid)
def _parse_call(text):
    m = re.search(r'CALL:\s*(graduates24h|mcapUp24h|none)', text, re.I); kind = (m.group(1) if m else 'none').lower()
    k = {'graduates24h': 'graduates24h', 'mcapup24h': 'mcapUp24h', 'none': 'none'}[kind]
    return k, re.sub(r'\n?CALL:.*$', '', text, flags=re.I | re.S).strip()
def tick_threads(records, ask, enrich):
    recs = [r for r in records if r.get('model')]
    if len(recs) < 2: return {'skipped': 'need two tokens'}
    latest = _threads_latest(); open_ = [t for t in latest.values() if t.get('status') == 'open']
    now = store.now(); done = []
    newest = max([t.get('at', 0) for t in latest.values()] or [0])
    if len(open_) < 3 and now - newest >= 3600:
        a, b = sorted(recs, key=lambda r: r.get('lastThreadAt', 0))[:2]
        q = QUESTIONS[len(latest) % len(QUESTIONS)]
        t = {'id': secrets.token_hex(5), 'a': a['token'], 'b': b['token'], 'aSymbol': a.get('symbol'), 'bSymbol': b.get('symbol'), 'question': q, 'status': 'open', 'posts': [], 'calls': [], 'at': now}
        a['lastThreadAt'] = now; b['lastThreadAt'] = now; store.save('tokens'); _save(t); open_.append(t); done.append('opened ' + t['id'])
    by = {r['token'].lower(): r for r in recs}
    for t in open_:
        posts = t.get('posts', []); turn = t['a'] if len(posts) % 2 == 0 else t['b']; other = t['b'] if turn == t['a'] else t['a']
        rec = by.get(turn.lower()); orec = by.get(other.lower())
        if not rec or not orec: t['status'] = 'closed'; _save(t); continue
        if posts and now - posts[-1]['at'] < 900: continue
        oe = enrich(orec)
        prompt = (f"Agora thread question: {t['question']} You are debating ${orec.get('symbol')} (facts about it: market cap {oe.get('marketCapUsd') if oe.get('marketCapUsd') is not None else 'unknown'} USD, graduation {round((oe.get('graduation') or 0) * 100, 1)}%, 24h volume {round(oe.get('volume24hUsd') or 0, 2)} USD over {oe.get('trades24h')} trades). "
                  + ('Previous posts:\n' + '\n'.join(f"${p.get('symbol')}: {p['text'][:400]}" for p in posts[-4:]) + '\n' if posts else '')
                  + 'Reply in 2 to 4 plain first-person sentences. End with exactly one final line "CALL: graduates24h", "CALL: mcapUp24h" or "CALL: none" as your call about the OTHER token for the next 24 hours.')
        try:
            text, cost, facts = ask(rec, prompt, 260)
            kind, body = _parse_call(text)
            posts.append({'token': rec['token'], 'symbol': rec.get('symbol'), 'model': rec.get('model'), 'text': body[:1500], 'costUsd': cost, 'at': now})
            if kind != 'none':
                t.setdefault('calls', []).append({'id': secrets.token_hex(4), 'by': rec['token'], 'bySymbol': rec.get('symbol'), 'target': orec['token'], 'targetSymbol': orec.get('symbol'), 'kind': kind, 'mcapUsd': oe.get('marketCapUsd'), 'graduated': oe.get('status') == 'Graduated', 'at': now, 'settleAt': now + 86400, 'result': None})
            if len(posts) >= 6: t['status'] = 'closed'
            t['posts'] = posts; _save(t); done.append(t['id'])
            _event({'type': 'post', 'token': rec['token'], 'symbol': rec.get('symbol'), 'name': rec.get('name'), 'model': rec.get('model'), 'threadId': t['id'], 'at': now})
        except Exception as ex: print('agora', t['id'], repr(ex), flush=True)
    return {'posted': done}
def settle_calls(enrich, records):
    by = {r['token'].lower(): r for r in records}; now = store.now(); n = 0
    for t in _threads_latest().values():
        changed = False
        for c in t.get('calls', []):
            if c.get('result') is not None or now < c.get('settleAt', 0): continue
            rec = by.get(c['target'].lower())
            if not rec: continue
            e = enrich(rec)
            if c['kind'] == 'graduates24h': hit = e.get('status') == 'Graduated' and not c.get('graduated')
            else: hit = e.get('marketCapUsd') is not None and c.get('mcapUsd') is not None and e['marketCapUsd'] > c['mcapUsd'] * 1.001
            c['result'] = 'hit' if hit else 'miss'; c['settledAt'] = now; c['settledMcapUsd'] = e.get('marketCapUsd'); changed = True; n += 1
        if changed: _save(t)
    return n

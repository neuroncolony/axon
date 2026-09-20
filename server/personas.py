"""Per token persona, launcher memory, prompt prefix and two model compare."""
import secrets, store
class PersonaError(Exception): pass
def _p(): return store.load('personas', {})
def _m(): return store.load('memory', {})
def _owner(rec, caller):
    if not caller or (caller or '').lower() != (rec.get('deployer') or '').lower(): raise PersonaError('Only the wallet that launched this token can do that.')
def default_persona(rec):
    sym = rec.get('symbol') or 'this token'
    return {'name': sym, 'greeting': f"I am the model behind ${sym}. Ask me anything about the token or the market it sits in.",
            'style': 'direct, plain, no hype', 'rules': 'Never invent numbers. Say unknown when unknown. No emojis.', 'goals': 'Explain the token honestly and keep holders informed.', 'version': 0, 'updatedAt': rec.get('launchedAt')}
def get_persona(token, rec):
    cur = _p().get(token.lower()) or {}
    return {**default_persona(rec), **{k: v for k, v in cur.items() if k != 'history'}}
def persona_history(token):
    return (_p().get(token.lower()) or {}).get('history', [])
ALLOWED = ('name', 'greeting', 'style', 'rules', 'goals'); LIM = {'name': 40, 'greeting': 400, 'style': 300, 'rules': 600, 'goals': 400}
def set_persona(token, rec, caller, fields):
    _owner(rec, caller)
    cur = get_persona(token, rec); new = dict(cur)
    for k in ALLOWED:
        if k in fields and isinstance(fields[k], str): new[k] = fields[k].strip()[:LIM[k]]
    new['version'] = int(cur.get('version', 0)) + 1; new['updatedAt'] = store.now(); new['updatedBy'] = caller.lower()
    def fn(d):
        row = d.setdefault(token.lower(), {}); hist = row.get('history', [])
        hist.append({k: cur.get(k) for k in ALLOWED + ('version', 'updatedAt')}); row['history'] = hist[-20:]
        row.update({k: new[k] for k in ALLOWED + ('version', 'updatedAt', 'updatedBy')}); return row
    store.update('personas', {}, fn); return get_persona(token, rec)
def get_memory(token): return (_m().get(token.lower()) or [])[-50:]
def add_memory(token, rec, caller, text):
    _owner(rec, caller); text = (text or '').strip()[:280]
    if not text: raise PersonaError('Write something to remember.')
    row = {'id': secrets.token_hex(5), 'text': text, 'at': store.now()}
    def fn(d):
        lst = d.setdefault(token.lower(), []); lst.append(row)
        if len(lst) > 50: del lst[:-50]
    store.update('memory', {}, fn); return get_memory(token)
def delete_memory(token, rec, caller, mid):
    _owner(rec, caller)
    store.update('memory', {}, lambda d: d.__setitem__(token.lower(), [r for r in d.get(token.lower(), []) if r['id'] != mid]))
    return get_memory(token)
def context_prefix(token, rec):
    p = get_persona(token, rec); mem = get_memory(token)
    s = f"Your name is {p['name']}. Style: {p['style']}. Rules: {p['rules']}. Goals: {p['goals']}. "
    if mem: s += 'Things you remember (given by your launcher): ' + ' | '.join(r['text'] for r in mem[-20:]) + '. '
    return s
def compare(address, question, tokens):
    import pool
    question = (question or '').strip()[:2000]
    if not question or not isinstance(tokens, list) or len(tokens) != 2 or tokens[0].lower() == tokens[1].lower(): raise PersonaError('Pick two different tokens and ask one question.')
    out = []
    for t in tokens:
        rec = pool.TOKENS.get(t.lower())
        if not rec or not rec.get('model'): raise PersonaError('Unknown token ' + t)
        res = pool.chat(address, rec['model'], [{'role': 'user', 'content': question}], source='compare', system_extra=context_prefix(t, rec))
        out.append({'token': rec['token'], 'symbol': rec.get('symbol'), 'model': rec['model'], 'text': res['reply'], 'costUsd': res['costUsd']})
    return {'answers': out}

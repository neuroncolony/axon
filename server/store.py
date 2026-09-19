"""Tiny JSON store. One file per collection, write-through with a lock. Good enough for a single-process preview."""
import json, os, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent / 'data'
ROOT.mkdir(exist_ok=True)
_lock = threading.RLock()
_mem = {}
def load(name, default):
    with _lock:
        if name in _mem: return _mem[name]
        p = ROOT / (name + '.json')
        try: _mem[name] = json.loads(p.read_text())
        except Exception: _mem[name] = default
        return _mem[name]
def save(name):
    with _lock:
        p = ROOT / (name + '.json'); tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(_mem[name], indent=0, default=str)); os.replace(tmp, p)
def update(name, default, fn):
    with _lock:
        d = load(name, default); r = fn(d); save(name); return r
def append(name, row):
    with _lock:
        with open(ROOT / (name + '.jsonl'), 'a') as f: f.write(json.dumps(row, default=str) + '\n')
def read_jsonl(name, limit=200):
    p = ROOT / (name + '.jsonl')
    if not p.exists(): return []
    rows = p.read_text().splitlines()[-limit:]
    out = []
    for r in rows:
        try: out.append(json.loads(r))
        except Exception: pass
    return out
def now(): return int(time.time())

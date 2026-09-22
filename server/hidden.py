"""Tokens removed from the site by the operator. Chain state is untouched; the site simply never lists, adopts or narrates them.
Seeded here so a data-volume reset cannot bring them back; AXON_HIDDEN (comma separated addresses) extends the list at runtime."""
import os
SEED = {
    '0x99720c12df25c6216812c5184ca08c62ebd075f4',  # ATEST
    '0xb4d69b3a7a59069e1a80057704d1eaa6ded52559',  # ATEST
    '0xddd6f156f9d200a423b3e249a3c973b8768e6577',  # AXTEST
    '0x7baa67d96e9ed7ed0e9578a2ccd5565ed115883b',  # TEST
    '0x591318a987a7b694e1521b721ee9f2c4fed0e87c',  # TEST
    '0x39966d78fb8687686ffad078731903daf1e9f816',  # AXON (pre-launch test deployment)
}
HIDDEN = SEED | {a.strip().lower() for a in os.environ.get('AXON_HIDDEN', '').split(',') if a.strip()}
def is_hidden(addr): return (addr or '').lower() in HIDDEN
def visible(rows, key='token'): return [r for r in rows if not is_hidden(r.get(key))]

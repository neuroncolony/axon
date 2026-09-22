"""The operator's own token holds the first slot everywhere. Until AXON_OFFICIAL_TOKEN is set the slot renders as a placeholder."""
import os
def official():
    tok = os.environ.get('AXON_OFFICIAL_TOKEN', '').strip().lower() or None
    return {'name': os.environ.get('AXON_OFFICIAL_NAME', 'Axon'), 'symbol': os.environ.get('AXON_OFFICIAL_SYMBOL', 'AXON'),
            'pairedWith': 'Axon', 'token': tok, 'link': os.environ.get('AXON_OFFICIAL_LINK', '').strip() or None,
            'live': bool(tok)}

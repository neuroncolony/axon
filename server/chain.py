"""axon chain layer: pons v2 on Robinhood Chain (4663).
Read-only RPC plus unsigned transaction builders. No private keys here.
Every launch made through axon sets creatorFeeRecipient = AXON_TREASURY so the
creator tax slice (2%) funds the shared compute pool. Nothing here is simulated."""
import os, re, json, time, threading
from eth_abi import encode, decode
from eth_utils import keccak, to_checksum_address
try:
    from core.http_client import proxied_get, proxied_post
except Exception:
    from compat import proxied_get, proxied_post

RPC = os.environ.get('AXON_RPC', '').strip() or 'https://rpc.mainnet.chain.robinhood.com'
PONS = (os.environ.get('AXON_PONS_FACTORY', '').strip() or '0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e').lower()
ESCROW = (os.environ.get('AXON_PONS_ESCROW', '').strip() or '0xd3afeb2a57f70ef218aa82451c51b2fb0416ac9e').lower()
ZERO = '0x' + '0' * 40
CHAIN_ID = 4663
CALLER = 'preview:axon'
CREATOR_TAX_BPS = 200
SOCIALS = '(string,string,string,string,string)'
PARAM_TUPLE = '(string,string,string,string,' + SOCIALS + ',address,uint16,bool,bytes32,bytes32)'
LAUNCH_TOPIC = '0x' + keccak(text='TokenLaunched(address,address,address,address,uint256,uint256)').hex()
EXPLORER = 'https://robinhoodchain.blockscout.com'
# Trade events are emitted by the curve itself. BUY data = [ethIn, tokensOut, protocolFee, creatorFee].
# SELL data = [tokensIn, ethOut, protocolFee, creatorFee] (confirmed against the ERC20 Transfer into the curve).
BUY_TOPIC = '0xec36bf571f136799e8dc0b0b8bea4b04d8bd3d43de838aab0d5fc21d4cbfc455'
SELL_TOPIC = '0x8113d738abdcb6b38357e9d53a54a7157861a09031b453651f0fe7fe151f59df'
TRADE_TOPICS = [BUY_TOPIC, SELL_TOPIC]
FEE_BPS_TOTAL = 300  # feeBps 100 + creatorTaxBps 200, taken from the ETH side of every trade

_cache, _lock = {}, threading.Lock()

class ChainError(Exception): pass

def treasury():
    t = os.environ.get('AXON_TREASURY', '').strip()
    return to_checksum_address(t) if re.fullmatch(r'0x[0-9a-fA-F]{40}', t) else None

def addr(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]{40}', value) or int(value, 16) == 0:
        raise ValueError('Enter a valid, nonzero address.')
    return to_checksum_address(value)

def eth(value):
    whole, fraction = divmod(int(value), 10**18)
    return str(whole) + (('.' + str(fraction).zfill(18).rstrip('0')) if fraction else '')

READ_METHODS = {'eth_chainId','eth_call','eth_getCode','eth_getBalance','eth_blockNumber','eth_getLogs','eth_getTransactionReceipt','eth_getBlockByNumber','eth_getTransactionByHash'}
def rpc(method, params):
    if method not in READ_METHODS: raise ChainError('Read method not permitted.')
    data = None
    for attempt in range(4):
        r = proxied_post(RPC, json={'jsonrpc':'2.0','id':1,'method':method,'params':params},
                         headers={'SC-CALLER-ID':CALLER,'User-Agent':'Mozilla/5.0 axon'}, timeout=25)
        if r.status_code == 429 and attempt < 3:
            time.sleep(0.6 * (2 ** attempt)); continue
        r.raise_for_status()
        data = r.json(); break
    if 'error' in data or 'result' not in data:
        raise ChainError('RPC: ' + str(data.get('error', {}).get('message', 'no result')))
    return data['result']

def calldata(signature, types=(), values=()):
    return '0x' + (keccak(text=signature)[:4] + encode(list(types), list(values))).hex()

def call(target, signature, types=(), values=(), returns=('uint256',)):
    raw = rpc('eth_call', [{'to':addr(target),'data':calldata(signature,types,values)}, 'latest'])
    if raw == '0x': raise ChainError('Empty return from ' + signature)
    return decode(list(returns), bytes.fromhex(raw[2:]))

def cached(key, fetch, ttl=20):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now: return hit[1]
    value = fetch()
    with _lock: _cache[key] = (now + ttl, value)
    return value

# ---------------------------------------------------------------- factory reads
def economics(): return call(PONS, 'previewLaunchEconomics(uint256,address)', ['uint256','address'], [0, ZERO], ['bytes32'])[0]
def launch_fee(): return call(PONS, 'launchFee()')[0]

def status():
    def fetch():
        out = {'chainId':CHAIN_ID,'factory':PONS,'escrow':ESCROW,'treasury':treasury(),'ok':False,'launchFeeEth':None,'baseFeeBps':None,'creatorTaxBps':CREATOR_TAX_BPS,'block':None,'version':os.environ.get('RAILWAY_GIT_COMMIT_SHA','')[:7]}
        try:
            if int(rpc('eth_chainId',[]),16) != CHAIN_ID: raise ChainError('wrong chain')
            out['block'] = int(rpc('eth_blockNumber',[]),16)
            out['launchFeeEth'] = eth(launch_fee())
            cfg = call(PONS,'getLaunchConfig(uint256)',['uint256'],[0],['uint256','uint256','uint256','uint256','uint24','int24','bool'])
            out['baseFeeBps'] = cfg[1]
            out['claimableEth'] = eth(escrow_claimable(out['treasury'])) if out['treasury'] else None
            out['ok'] = True
        except Exception as e:
            out['error'] = str(e)[:160]
        out['checkedAt'] = int(time.time())
        return out
    return cached('status', fetch, 30)

LAUNCHED_TYPES = ['address','address','address','address','address','uint256','uint24','int24','uint16','bool','uint8']
def launched(token):
    """getLaunchedToken(token) -> dict. phase: 0 none, 1 curve, 2 graduated (as returned by factory)."""
    raw = rpc('eth_call', [{'to':PONS,'data':calldata('getLaunchedToken(address)',['address'],[addr(token)])},'latest'])
    b = bytes.fromhex(raw[2:])
    # tuple may have more fields than we decode; decode a prefix by slicing 32-byte words
    words = [b[i:i+32] for i in range(0, len(b), 32)]
    if len(words) < 11: raise ChainError('Unexpected launched-token layout.')
    a = lambda w: to_checksum_address('0x' + w[-20:].hex())
    u = lambda w: int.from_bytes(w, 'big')
    return {'token':a(words[0]),'curve':a(words[1]),'deployer':a(words[2]),'creatorFeeRecipient':a(words[3]),'pairToken':a(words[4]),
            'graduationThreshold':str(u(words[5])),'poolFee':u(words[6]),'creatorTaxBps':u(words[8]),'buybackEnabled':bool(u(words[9])),'phase':u(words[10])}

MODEL_TAG = re.compile(rb'axon:model=([\x21-\x7e]{1,64})')
def model_from_tx(txhash):
    """Recover the model id from the launch calldata: launch_tx() appends 'axon:model=<id>' to the on-chain description, so the registry can always be rebuilt from chain."""
    try:
        t = rpc('eth_getTransactionByHash', [txhash])
        m = MODEL_TAG.search(bytes.fromhex((t or {}).get('input', '0x')[2:]))
        return m.group(1).decode() if m else None
    except Exception as e:
        print('model_from_tx', txhash[:12], repr(e), flush=True); return None

def curve_state(curve):
    """Reads from the bonding curve. Each call is isolated so one missing getter does not kill the row.
    The curve has no ethReserve()/totalRaised() getters; reserves come from getReserves() (virtual, wei scale)."""
    curve = addr(curve)
    out = {'graduated': None, 'ethReserve': None, 'tokenReserve': None, 'graduationThreshold': None, 'balanceWei': None, 'priceEth': None}
    try: out['graduated'] = bool(call(curve, 'graduated()', returns=['bool'])[0])
    except Exception: pass
    try: out['ethReserve'], out['tokenReserve'] = call(curve, 'getReserves()', returns=['uint256', 'uint256'])
    except Exception: pass
    try: out['graduationThreshold'] = call(curve, 'graduationThreshold()', returns=['uint256'])[0]
    except Exception: pass
    try: out['balanceWei'] = int(rpc('eth_getBalance',[curve,'latest']),16)
    except Exception: pass
    # spot price in ETH per whole token: ratio of the two virtual reserves
    if out['ethReserve'] and out['tokenReserve']: out['priceEth'] = out['ethReserve'] / out['tokenReserve']
    return out

def erc20(token):
    t = addr(token); out = {}
    for key, sig, ret in (('name','name()',['string']),('symbol','symbol()',['string']),('totalSupply','totalSupply()',['uint256']),('decimals','decimals()',['uint8'])):
        try: out[key] = call(t, sig, returns=ret)[0]
        except Exception: out[key] = None
    if isinstance(out.get('totalSupply'), int): out['totalSupply'] = str(out['totalSupply'])
    return out

def token_snapshot(token):
    info = launched(token)
    if info['token'].lower() != token.lower(): raise ChainError('Not a pons v2 token.')
    meta = erc20(token); curve = curve_state(info['curve'])
    supply = int(meta['totalSupply']) if meta.get('totalSupply') else 0
    price = curve.get('priceEth')
    mcap = (price * supply / 10**18) if (price and supply) else None
    ours = bool(treasury()) and info['creatorFeeRecipient'].lower() == treasury().lower()
    return {**info, **meta, 'curve_state':{k:(str(v) if isinstance(v,int) else v) for k,v in curve.items()},
            'priceEth':price,'marketCapEth':mcap,'fundedByAxon':ours,'explorer':EXPLORER + '/address/' + info['token'],'readAt':int(time.time())}

def launch_logs(from_block, to_block='latest'):
    logs = rpc('eth_getLogs',[{'fromBlock':hex(from_block),'toBlock':to_block,'address':PONS,'topics':[LAUNCH_TOPIC]}])
    out = []
    for l in logs:
        t = l['topics']
        out.append({'token':to_checksum_address('0x'+t[1][-40:]),'curve':to_checksum_address('0x'+t[2][-40:]),'deployer':to_checksum_address('0x'+t[3][-40:]),
                    'block':int(l['blockNumber'],16),'tx':l['transactionHash']})
    return out

def receipt(txhash):
    if not re.fullmatch(r'0x[0-9a-fA-F]{64}', txhash or ''): raise ValueError('Bad tx hash.')
    return rpc('eth_getTransactionReceipt',[txhash])

def token_from_receipt(txhash):
    r = receipt(txhash)
    if not r: return None
    for l in r.get('logs', []):
        if l['address'].lower() == PONS and l['topics'] and l['topics'][0] == LAUNCH_TOPIC:
            return {'token':to_checksum_address('0x'+l['topics'][1][-40:]),'curve':to_checksum_address('0x'+l['topics'][2][-40:]),
                    'deployer':to_checksum_address('0x'+l['topics'][3][-40:]),'block':int(r['blockNumber'],16),'status':r['status']}
    return None

# ---------------------------------------------------------------- tx builders (unsigned, wallet signs)
def launch_tx(form):
    t = treasury()
    if not t: raise ChainError('AXON_TREASURY is not configured, launches are disabled.')
    name = str(form.get('name','')).strip(); symbol = str(form.get('symbol','')).strip().upper()
    description = str(form.get('description','')).strip(); logo = str(form.get('logo','')).strip()
    model = str(form.get('model','')).strip()
    website = str(form.get('website','')).strip(); x = str(form.get('x','')).strip(); telegram = str(form.get('telegram','')).strip()
    if not (1 <= len(name.encode()) <= 64): raise ValueError('Name must be 1 to 64 bytes.')
    if not re.fullmatch(r'[A-Z0-9]{1,12}', symbol): raise ValueError('Symbol must be 1 to 12 letters or numbers.')
    if len(description.encode()) > 500 or len(logo.encode()) > 500: raise ValueError('Description and logo are capped at 500 bytes.')
    if logo and not logo.startswith('https://'): raise ValueError('Logo URL must be HTTPS.')
    if not re.fullmatch(r'[a-z0-9\-]+/[a-z0-9.\-:]+', model): raise ValueError('Pick a model.')
    for u in (website, x, telegram):
        if u and not u.startswith('https://'): raise ValueError('Links must be HTTPS.')
    for u in (website, x, telegram):
        if len(u.encode()) > 200: raise ValueError('Links are capped at 200 bytes.')
    salt = os.urandom(32)
    # model id rides in the description tail so it is recoverable on-chain without a server
    desc = (description + ('\n' if description else '') + 'axon:model=' + model)[:500]
    socials = (website, x, telegram, '', '')
    params = (name, symbol, logo, desc, socials, t, CREATOR_TAX_BPS, False, economics(), salt)
    data = calldata('launchToken(' + PARAM_TUPLE + ',uint256,address)', [PARAM_TUPLE, 'uint256', 'address'], [params, 0, ZERO])
    return {'tx':{'to':to_checksum_address(PONS),'data':data,'value':hex(launch_fee()),'chainId':CHAIN_ID},'creatorFeeRecipient':t,'creatorTaxBps':CREATOR_TAX_BPS,'model':model,'salt':'0x'+salt.hex()}

def _reserves(curve):
    e, t = call(curve, 'getReserves()', returns=['uint256','uint256'])
    return int(e), int(t)
def quote(token, side, amount, sender):
    """Constant product on the curve's virtual reserves, 300 bps taken from the ETH side. Buy is confirmed against an eth_call simulation when possible."""
    info = launched(token); sender = addr(sender)
    if side not in ('buy','sell') or not re.fullmatch(r'[1-9][0-9]{0,77}', str(amount)): raise ValueError('Use a valid side and a positive wei amount.')
    if call(info['curve'],'graduated()',returns=['bool'])[0]: raise ChainError('This token has graduated to the pool. Trade it on the DEX.')
    n = int(amount); e, t = _reserves(info['curve']); k = e * t
    requires = False
    if side == 'buy':
        net = n * (10000 - FEE_BPS_TOTAL) // 10000
        out = t - k // (e + net)
        try:
            sim = rpc('eth_call',[{'from':sender,'to':info['curve'],'data':calldata('buy(uint256,uint256,address)',['uint256','uint256','address'],[n,0,sender]),'value':hex(n)},'latest'])
            if sim and sim != '0x': out = decode(['uint256'], bytes.fromhex(sim[2:]))[0]
        except Exception: pass
    else:
        gross = e - k // (t + n)
        out = gross * (10000 - FEE_BPS_TOTAL) // 10000
        try: requires = call(info['token'],'allowance(address,address)',['address','address'],[sender,info['curve']])[0] < n
        except Exception: requires = True
    return {'side':side,'amountInWei':str(n),'amountOutWei':str(out),'priceEth':(e / t) if t else None,'feeBpsTotal':FEE_BPS_TOTAL,'requiresApproval':requires,
            'curve':info['curve'],'token':info['token'],'chainId':CHAIN_ID,'quotedAt':int(time.time())}

def trade_tx(form):
    side = form.get('side'); amount = str(form.get('amountWei','')); sender = addr(form.get('sender','')); bps = form.get('slippageBps')
    if not isinstance(bps,int) or isinstance(bps,bool) or not 10 <= bps <= 1000: raise ValueError('Slippage must be between 0.1% and 10%.')
    q = quote(str(form.get('token','')), side, amount, sender)
    minimum = int(q['amountOutWei']) * (10000 - bps) // 10000
    if minimum == 0: raise ValueError('Output too small.')
    n = int(amount)
    if side == 'buy': data, value = calldata('buy(uint256,uint256,address)',['uint256','uint256','address'],[n,minimum,sender]), hex(n)
    else: data, value = calldata('sell(uint256,uint256,address)',['uint256','uint256','address'],[n,minimum,sender]), '0x0'
    out = {'tx':{'to':q['curve'],'data':data,'value':value,'chainId':CHAIN_ID},'quote':q,'minOutWei':str(minimum)}
    if q['requiresApproval']: out['approval'] = {'to':q['token'],'data':calldata('approve(address,uint256)',['address','uint256'],[q['curve'],n]),'value':'0x0','chainId':CHAIN_ID}
    return out

_ts_cache = {}
def block_timestamp(block):
    b = int(block)
    if b not in _ts_cache:
        blk = rpc('eth_getBlockByNumber',[hex(b), False])
        _ts_cache[b] = int(blk['timestamp'],16) if blk else int(time.time())
        if len(_ts_cache) > 5000: _ts_cache.clear()
    return _ts_cache[b]

def trade_logs(curve, from_block, to_block='latest'):
    """Buy and Sell events emitted by the curve. BUY data = [ethIn, tokensOut, protocolFee, creatorFee]; SELL data = [tokensIn, ethOut, protocolFee, creatorFee]."""
    logs = rpc('eth_getLogs',[{'fromBlock':hex(int(from_block)),'toBlock':to_block if isinstance(to_block,str) else hex(int(to_block)),'address':addr(curve),'topics':[TRADE_TOPICS]}])
    out = []
    for l in logs:
        d = l['data'][2:]; w = [int(d[i:i+64],16) for i in range(0, len(d), 64)]
        if len(w) < 4 or len(l['topics']) < 3: continue
        buy = l['topics'][0].lower() == BUY_TOPIC
        out.append({'side':'buy' if buy else 'sell','caller':to_checksum_address('0x'+l['topics'][1][-40:]),'trader':to_checksum_address('0x'+l['topics'][2][-40:]),
                    'ethWei':str(w[0] if buy else w[1]),'tokenWei':str(w[1] if buy else w[0]),'protocolFeeWei':str(w[2]),'creatorFeeWei':str(w[3]),
                    'tx':l['transactionHash'],'block':int(l['blockNumber'],16),'logIndex':int(l['logIndex'],16)})
    return out

TRANSFER_TOPIC = '0x' + keccak(text='Transfer(address,address,uint256)').hex()

def transfer_logs(token, from_block, to_block='latest'):
    """ERC20 Transfer events for `token`. topics[1] = from, topics[2] = to, data = value (uint256)."""
    logs = rpc('eth_getLogs',[{'fromBlock':hex(int(from_block)),'toBlock':to_block if isinstance(to_block,str) else hex(int(to_block)),
                               'address':addr(token),'topics':[TRANSFER_TOPIC]}])
    out = []
    for l in logs:
        if len(l.get('topics', [])) < 3: continue
        d = l['data'][2:]
        try: value = str(int(d, 16)) if d else '0'
        except ValueError: continue
        out.append({'from':to_checksum_address('0x'+l['topics'][1][-40:]),'to':to_checksum_address('0x'+l['topics'][2][-40:]),
                    'valueWei':value,'tx':l['transactionHash'],'block':int(l['blockNumber'],16),'logIndex':int(l['logIndex'],16)})
    return out

def launch_logo(txhash):
    """Logo URI from the launch tx params tuple; ipfs:// is mapped to a public gateway. Empty string when it cannot be decoded."""
    try:
        tx = rpc('eth_getTransactionByHash',[txhash]); inp = bytes.fromhex(tx['input'][2:])
        for off in (4, 36, 68):
            try:
                params = decode([PARAM_TUPLE], inp[off:])[0]; logo = str(params[2]).strip()
                if logo.startswith('ipfs://'): logo = 'https://ipfs.io/ipfs/' + logo[7:].lstrip('/')
                return logo if logo.startswith('https://') else ''
            except Exception: continue
    except Exception: pass
    return ''

def avatar_svg(symbol, address):
    h = (address or '0x').lower().replace('0x','').ljust(12,'0')
    h1 = int(h[0:3],16) % 360; h2 = (h1 + 40 + int(h[3:6],16) % 120) % 360
    text = ''.join(ch for ch in str(symbol or '?').upper() if ch.isalnum())[:3] or '?'
    size = 72 if len(text) <= 2 else 54
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="hsl({h1},70%,55%)"/><stop offset="1" stop-color="hsl({h2},70%,40%)"/></linearGradient></defs>'
            f'<rect width="160" height="160" rx="36" fill="url(#g)"/><text x="80" y="80" dy=".36em" text-anchor="middle" font-family="system-ui,Segoe UI,Roboto,sans-serif" font-weight="700" font-size="{size}" fill="#fff">{text}</text></svg>')

def treasury_balance():
    t = treasury()
    if not t: return {'treasury':None,'balanceWei':None}
    return cached('treasury:'+t, lambda: {'treasury':t,'balanceWei':str(int(rpc('eth_getBalance',[t,'latest']),16))}, ttl=30)

def escrow_claimable(recipient):
    """ETH the pons fee escrow owes `recipient`. Trades pay the 2% creator tax into the curve; sweepFees moves it here; claim() pays it out."""
    return call(ESCROW, 'balanceOf(address)', ['address'], [addr(recipient)])[0]
CLAIMER = '0xdA681CbB6AFfd78259df53B5Db1FA33A50487B30'  # the only wallet allowed to claim, hardcoded on purpose
def claim_tx(sender=None):
    """Escrow claim(). Pays msg.sender its balance, so it must be signed by the treasury wallet itself.
    The server additionally refuses to build the tx for anyone but CLAIMER."""
    t = treasury()
    if not t: raise ChainError('AXON_TREASURY is not configured.')
    if (sender or '').lower() != CLAIMER.lower(): raise ChainError('Only the treasury owner wallet can claim.')
    return {'tx': {'to': to_checksum_address(ESCROW), 'data': calldata('claim()'), 'value': '0x0', 'chainId': CHAIN_ID}, 'claimTo': t, 'claimableWei': str(escrow_claimable(t))}

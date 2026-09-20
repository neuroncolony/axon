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

RPC = 'https://rpc.mainnet.chain.robinhood.com'
PONS = '0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e'
ESCROW = '0xd3afeb2a57f70ef218aa82451c51b2fb0416ac9e'
ZERO = '0x' + '0' * 40
CHAIN_ID = 4663
CALLER = 'preview:axon'
CREATOR_TAX_BPS = 200
SOCIALS = '(string,string,string,string,string)'
PARAM_TUPLE = '(string,string,string,string,' + SOCIALS + ',address,uint16,bool,bytes32,bytes32)'
LAUNCH_TOPIC = '0x' + keccak(text='TokenLaunched(address,address,address,address,uint256,uint256)').hex()
EXPLORER = 'https://robinhoodchain.blockscout.com'

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

READ_METHODS = {'eth_chainId','eth_call','eth_getCode','eth_getBalance','eth_blockNumber','eth_getLogs','eth_getTransactionReceipt','eth_getBlockByNumber'}
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
        out = {'chainId':CHAIN_ID,'factory':PONS,'escrow':ESCROW,'treasury':treasury(),'ok':False,'launchFeeEth':None,'baseFeeBps':None,'creatorTaxBps':CREATOR_TAX_BPS,'block':None}
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

def curve_state(curve):
    """Best-effort reads from the bonding curve. Each call is isolated so one missing getter does not kill the row."""
    out = {}
    for key, sig, ret in (('graduated','graduated()',['bool']),('ethReserve','ethReserve()',['uint256']),('tokenReserve','tokenReserve()',['uint256']),
                          ('totalRaised','totalRaised()',['uint256']),('graduationThreshold','graduationThreshold()',['uint256'])):
        try: out[key] = call(curve, sig, returns=ret)[0]
        except Exception: out[key] = None
    try: out['balanceWei'] = int(rpc('eth_getBalance',[addr(curve),'latest']),16)
    except Exception: out['balanceWei'] = None
    # spot quote for 0.001 ETH gives an implied price
    try:
        raw = rpc('eth_call',[{'to':addr(curve),'data':calldata('buy(uint256)',['uint256'],[0]),'value':hex(10**15)},'latest'])
        got = decode(['uint256'],bytes.fromhex(raw[2:]))[0]
        out['priceEth'] = (10**15 / got) if got else None
    except Exception: out['priceEth'] = None
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
    website = str(form.get('website','')).strip(); twitter = str(form.get('twitter','')).strip(); telegram = str(form.get('telegram','')).strip()
    if not (1 <= len(name.encode()) <= 64): raise ValueError('Name must be 1 to 64 bytes.')
    if not re.fullmatch(r'[A-Z0-9]{1,12}', symbol): raise ValueError('Symbol must be 1 to 12 letters or numbers.')
    if len(description.encode()) > 500 or len(logo.encode()) > 500: raise ValueError('Description and logo are capped at 500 bytes.')
    if logo and not logo.startswith('https://'): raise ValueError('Logo URL must be HTTPS.')
    if not re.fullmatch(r'[a-z0-9\-]+/[a-z0-9.\-:]+', model): raise ValueError('Pick a model.')
    for u in (website, twitter, telegram):
        if u and not u.startswith('https://'): raise ValueError('Links must be HTTPS.')
    salt = os.urandom(32)
    # model id rides in the description tail so it is recoverable on-chain without a server
    desc = (description + ('\n' if description else '') + 'axon:model=' + model)[:500]
    socials = (twitter, telegram, '', website, '')
    params = (name, symbol, logo, desc, socials, t, CREATOR_TAX_BPS, False, economics(), salt)
    data = calldata('launchToken(' + PARAM_TUPLE + ',uint256,address)', [PARAM_TUPLE, 'uint256', 'address'], [params, 0, ZERO])
    return {'tx':{'to':to_checksum_address(PONS),'data':data,'value':hex(launch_fee()),'chainId':CHAIN_ID},'creatorFeeRecipient':t,'creatorTaxBps':CREATOR_TAX_BPS,'model':model,'salt':'0x'+salt.hex()}

def quote(token, side, amount, sender):
    info = launched(token); sender = addr(sender)
    if side not in ('buy','sell') or not re.fullmatch(r'[1-9][0-9]{0,77}', str(amount)): raise ValueError('Use a valid side and a positive wei amount.')
    if call(info['curve'],'graduated()',returns=['bool'])[0]: raise ChainError('This token has graduated to the pool. Trade it on the DEX.')
    n = int(amount); tx = {'from':sender,'to':info['curve']}
    if side == 'buy': tx.update(data=calldata('buy(uint256)',['uint256'],[0]), value=hex(n))
    else:
        allowance = call(info['token'],'allowance(address,address)',['address','address'],[sender,info['curve']])[0]
        if allowance < n: return {'side':side,'amountInWei':str(n),'amountOutWei':None,'requiresApproval':True,'curve':info['curve'],'token':info['token'],'chainId':CHAIN_ID}
        tx.update(data=calldata('sell(uint256,uint256)',['uint256','uint256'],[n,0]))
    out = decode(['uint256'], bytes.fromhex(rpc('eth_call',[tx,'latest'])[2:]))[0]
    return {'side':side,'amountInWei':str(n),'amountOutWei':str(out),'requiresApproval':False,'curve':info['curve'],'token':info['token'],'chainId':CHAIN_ID,'quotedAt':int(time.time())}

def trade_tx(form):
    side = form.get('side'); amount = str(form.get('amountWei','')); sender = addr(form.get('sender','')); bps = form.get('slippageBps')
    if not isinstance(bps,int) or isinstance(bps,bool) or not 10 <= bps <= 1000: raise ValueError('Slippage must be between 0.1% and 10%.')
    q = quote(str(form.get('token','')), side, amount, sender)
    if q['requiresApproval']:
        return {'approval':{'to':q['token'],'data':calldata('approve(address,uint256)',['address','uint256'],[q['curve'],int(amount)]),'value':'0x0','chainId':CHAIN_ID}}
    minimum = int(q['amountOutWei']) * (10000 - bps) // 10000
    if minimum == 0: raise ValueError('Output too small.')
    data = calldata('buy(uint256)',['uint256'],[minimum]) if side == 'buy' else calldata('sell(uint256,uint256)',['uint256','uint256'],[int(amount),minimum])
    return {'tx':{'to':q['curve'],'data':data,'value':hex(int(amount)) if side=='buy' else '0x0','chainId':CHAIN_ID},'quote':q,'minOutWei':str(minimum)}

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

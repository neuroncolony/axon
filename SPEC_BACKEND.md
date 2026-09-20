# Backend spec: real curve data, on-chain trades, candles, logos

Project: /data/workspace/output/axon. Python 3.11, stdlib + eth_abi + eth_utils. Files: server/chain.py, server/pool.py, server/server.py, server/store.py. Read all four fully first.

## Verified chain facts (chain 4663, use chain.rpc / chain.call / chain.calldata helpers)
- The curve does NOT have ethReserve(), totalRaised(), buy(uint256) or sell(uint256,uint256). Current curve_state, quote and trade_tx are broken (price null).
- Curve has: getReserves() -> (uint256 ethReserve, uint256 tokenReserve) [virtual reserves, wei scale; fresh curve = 1680000000000000000, 1e27], tokenReserve(), graduated() -> bool, graduationThreshold() -> uint256 (4.2e18), feeBps() (100), creatorTaxBps() (200), token(), pairToken(), feeEscrow(), sweepFees(uint256).
- Trading: buy(uint256 ethAmount, uint256 minTokensOut, address to) payable; ethAmount MUST equal msg.value; returns uint256 tokensOut. eth_call with from + value works as a quote (1e15 wei on the fresh AXON curve 0x76C7d47bb96Cf78eCf99c5711A0524EC7Ff1D215 returned 577047775986483994360399). sell(uint256 tokenAmount, uint256 minEthOut, address to); seller must approve the curve for tokenAmount first.
- Constant product on virtual reserves, total fee = feeBps + creatorTaxBps = 300 bps taken from the ETH side.
  buy: ethNet = ethIn*(10000-300)//10000; out = tokenReserve - ethReserve*tokenReserve//(ethReserve+ethNet).
  sell: ethGross = ethReserve - ethReserve*tokenReserve//(tokenReserve+tokensIn); ethOut = ethGross*(10000-300)//10000.
  Spot price in ETH per whole token = ethReserve/tokenReserve (float ratio of the two wei numbers). Market cap ETH = price * totalSupply/1e18.
- Graduation progress = eth_getBalance(curve) / graduationThreshold, clamp 0..1. Graduated only when graduated() is True or factory phase == 2. Bug now: curveState stores the bool as string 'False' (truthy) so status says Graduated. Store real bools, ints as str.
- Trade events are emitted by the CURVE. BUY topic0 = 0xec36bf571f136799e8dc0b0b8bea4b04d8bd3d43de838aab0d5fc21d4cbfc455; topics[1]=caller, topics[2]=trader; data = [ethIn, tokensOut, protocolFee, creatorFee]. SELL topic0 starts with 0x8113d738ab, also 3 topics + 4 data words. Find the full SELL hash and confirm its data order: eth_getLogs address=0xf04c320bdc940c36c390763fab464a6029892a82 over the last 40000 blocks, take one 0x8113d738ab log and its tx receipt (the ERC20 Transfer into the curve = tokensIn; the ETH number is the small one). Put both full hashes as constants in chain.py.
- Launch tx input: the factory launch call params tuple type is chain.PARAM_TUPLE (name, symbol, logo, description, socials, recipient, tax, bool, bytes32, bytes32). Decoding the record's launch tx input after the 4 byte selector yields the logo URI (often ipfs://CID). If decode fails (router call), leave logo ''. Map ipfs://X to https://ipfs.io/ipfs/X.

## Do
1. chain.py curve_state(curve): getReserves, graduated, graduationThreshold, balance; priceEth from reserves; isolated reads. Keys: graduated (bool), ethReserve, tokenReserve, graduationThreshold, balanceWei (str or None), priceEth (float or None). Fix token_snapshot mcap.
2. chain.py quote(token, side, amount, sender): reserves math (for buy also try the eth_call simulation and prefer it on success). Return amountInWei, amountOutWei, priceEth, requiresApproval (sell: allowance(sender,curve) < amount), curve, feeBpsTotal. trade_tx(form): buy -> buy(uint256,uint256,address) (amount, minimum, sender), value=amount; sell -> sell(uint256,uint256,address) (amount, minimum, sender); include 'approval' tx (token approve(curve, amount)) when requiresApproval. Keep the existing slippage handling.
3. chain.py trade_logs(curve, from_block, to_block='latest') -> [{side, trader, caller, ethWei, tokenWei, protocolFeeWei, creatorFeeWei (str), tx, block, logIndex}]. block_timestamp(block) with in-memory cache.
4. chain.py launch_logo(txhash) -> https URL or ''. avatar_svg(symbol, address) -> SVG string 160x160, rounded square, deterministic two-color gradient from the address hex, symbol initials (max 3, white, bold, centered, system-ui). No network.
5. pool.py: new jsonl store 'trades' (mirror how 'events' is written) and rec['lastTradeBlock']. In refresh(): for each token in _ours(), fetch trade_logs from lastTradeBlock+1 (first time: launch block) to head in chunks <= 5000 blocks; append trades with 'at' = block timestamp and 'priceEth' = ethWei/tokenWei; also append a live event {type:'buy'|'sell', token, symbol, model, by: trader, ethWei, tokenWei, tx, at}. Dedupe by tx+logIndex. For records with empty logo, try chain.launch_logo(rec['tx']) once (rec['logoChecked']=True).
6. pool.py: volume24, trades24, _trade_stats from the on-chain trades store (sum ethWei last 24h). record_trade becomes a no-op ack.
7. pool.py enrich(): add logoUrl = '/api/token/<token>/logo', keep logo raw, status from real bool, graduation = balanceWei/threshold, add volume24hEth, lastTradeAt.
8. pool.py: trades(token=None, limit=100) newest first (without token include token+symbol per item); candles(token, interval_s=300, limit=200): buckets floor(at/interval), each {t,o,h,l,c,vEth}; no trades -> one candle at current priceEth, t=now. Top level also priceEth, ethUsd.
9. server.py api_get: 'trades' (q token, limit), 'candles' (q token, interval, limit), 'token/<addr>/logo' -> 302 to rec logo if set else 200 image/svg+xml avatar with Cache-Control public, max-age=3600. Match the logo route before 'token/<addr>'. Write a small raw-response helper if send() only does JSON.
10. Sanity run: `cd /data/workspace/output/axon && set -a && source /data/workspace/.env && set +a && PORT=8123 python3 server/server.py &` (check how the port is read; adapt). Wait for the indexer, then curl:
   - /api/token/0x39966D78fb8687686ffAD078731903DAF1e9F816 -> priceEth about 1.68e-9, marketCapEth about 1.68, status 'Curve', graduation 0.0, logoUrl present
   - /api/token/0x39966D78fb8687686ffAD078731903DAF1e9F816/logo -> SVG
   - /api/candles?token=0x39966D78fb8687686ffAD078731903DAF1e9F816 -> one candle
   - '/api/quote?token=0x39966D78fb8687686ffAD078731903DAF1e9F816&side=buy&amount=1000000000000000&sender=0xFB10DEe2b407347F732399af51540722B24C212f' -> amountOutWei within 1% of 577047775986483994360399
   Kill the server after. Also test trade_logs on 0xf04c320bdc940c36c390763fab464a6029892a82 (last 5000 blocks), print 2 buys and 2 sells.

## Output
Edited files in place plus a short report: SELL topic hash, confirmed data order, curl outputs.

## Don't
No edits to public/*. No git commit/push. No em dashes or en dashes anywhere. Do not remove endpoints. Do not change treasury/claim logic (CLAIMER, claim_tx, _purge_foreign, _ours). Do not write to /data/workspace/.env.

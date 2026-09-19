# axon page build spec (shared by all page delegations)

Project root: /data/workspace/output/axon. Static pages live in `public/`. Server: `server/server.py` (Python, no framework). Read `public/index.html` FIRST and copy its exact skeleton, script loading, and coding style. Read `public/styles.css` for every available class (use those classes; add page-specific CSS only inside a `<style>` block in the page, keep it small). Read `public/shell.js` for the `AXON` helper object.

## Skeleton every page must use (copy from index.html)
- `<!DOCTYPE html><html lang="en">`, `<head>` with `<title>{{BRAND}} · Page name</title>`, meta viewport, `<link rel="stylesheet" href="static/styles.css">`, `<script src="static/shell.js" defer></script>`.
- `<body><header class="nav" id="nav"></header><main class="page"><div class="wrap"> ... </div></main><footer class="footer" id="footer"></footer><script>...</script></body>`.
- All internal links are RELATIVE (no leading slash): `href="explore"`, `href="launch"`, `href="token/0x..."`. In JS use `AXON.href('/explore')`. Static assets: `static/...`. API calls: `AXON.api('tokens?sort=new')` (GET) or `AXON.api('chat', {model, messages})` (POST). The server strips a `/preview/<id>` prefix, so never hardcode absolute paths.
- Wrap page JS in `document.addEventListener('DOMContentLoaded', async () => { const { api, esc, fmtUsd, fmtEth, toWei, fromWei, ago, short, pct, toast, href, state, login, me, ensureChain, sendTx, openWalletModal } = AXON; ... })`.
- Always escape user/API strings with `esc()`. Numbers: `fmtUsd(n)` for USD (handles tiny prices as $0.0₅443), `pct(x)` for 0..1 fractions, `ago(unixSeconds)` for ages, `short(address)`.
- Placeholders `{{BRAND}}`, `{{BRAND_DISPLAY}}`, `{{DESCRIPTION}}` are replaced server-side; use them instead of a hardcoded brand name.
- Empty states use `<div class="empty">...</div>`. Loading rows show a faint "Reading the chain…" text. Errors show `<div class="notice error">`.
- Copy style: plain, direct, no hype, no emojis, NEVER use em dashes or en dashes (use commas, periods, colons or parentheses). State limits honestly (for example: "Trade volume is counted from trades made through this site; trades made elsewhere are not indexed yet.").

## Design language (from styles.css)
Light theme. White background, navy `--navy #0f2340` headings, `--ink` text, `--muted/--faint` secondary, `--accent #7cc4ff` highlights, `--line #d3e0ee` borders, `--mint #eef5fc` soft fills, `--up #2f8f5b`, `--down #b4452f`. Instrument Sans body, DM Mono for numbers/labels (`.mono`, `.eyebrow`, `.chip`). Radius .5rem. Max width 72rem. Tables: `.table-wrap > table.table` with `th.num/td.num` right aligned, `.tok` cell with `.logo .n .s`. Cards: `.card`, `.card.stat` (`.k` label, `.v` value). Sections: `.section` with `.section-head` (eyebrow + h2 left, link right). Grids: `.grid.c2/.c3/.c4`. Buttons: `.btn`, `.btn.ghost`, `.btn.accent`, `.btn.sm`, `.btn.wide`. Chips: `.chip`, `.chip.up/.down/.navy/.mint`. Forms: `.field > span + input/select/textarea + .hint`. Feed: `.feed > .feed-item > .t + div(.who, .body)`. Tabs: `.tabs`. Prose: `.prose`. Chat: `.chat`, `.msgs`, `.msg.user/.ai`, `.compose`. Progress bar: `<span class="bar"><i style="width:40%"></i></span>`.

## API (GET unless noted). All JSON. Errors: `{error}` with 4xx.
- `status` → `{chainId, factory, treasury, ok, launchFeeEth, baseFeeBps, creatorTaxBps, block, brand:{name,displayName,tagline,description}, chatEnabled}`
- `stats` → `{treasury, treasuryEth, ethUsd, availableUsd, spentUsd, raisedUsd, launches, messages, chatEnabled}` (any may be null)
- `models` → `{models:[{id,name,provider,ctx,in,out,tag}], usage:{launches:{modelId:count}, spentUsd:{modelId:usd}}}` (in/out are USD per 1M tokens)
- `tokens?sort=new|mcap|volume|graduation&model=<id>&status=curve|graduated&limit=50` → `{tokens:[T]}`
  T = `{token, curve, deployer, name, symbol, model, modelName, logo, description, tx, launchedAt, block, phase, priceEth, priceUsd, marketCapEth, marketCapUsd, graduation (0..1 or null), status:"Curve"|"Graduated", age (seconds), explorer, volume24hUsd, trades24h, curveState:{...}}`
- `token/<address>` → T plus `{events:[E], takes:[K], bets:[B], spentUsd}`
- `live?limit=60&token=<addr>` → `{events:[E]}` where E has `type: "launch"|"trade"|"take"|"bet"`, `token, symbol, at`, and per type: launch `{model, by, tx}`, trade `{side, ethValue, by, tx}`, take `{model, body, costUsd}`, bet `{model, call:"up"|"down"|"stay", mcapUsd, result:null|"hit"|"miss", actual}`
- `takes?limit=60&token=` → `{takes:[K]}` K = `{token, symbol, model, body, costUsd, at}`
- `leaderboard?by=mcap|volume|graduation` → `{tokens:[T], launchers:[{address, launches, marketCapUsd, spentUsd}], models:{launches:{}, spentUsd:{}}}`
- `scoreboard` → `{rows:[{token, symbol, model, bets, hits, misses, pending, accuracy (0..1|null), last:B}], recent:[B]}`
- `offspring` → `{offspring:[{child:T, parent:T}]}` (an offspring is a token launched by a wallet that already launched one here; lineage derived from chain order)
- `quote?token=&side=buy|sell&amount=<wei>&sender=<addr>` → `{side, amountInWei, amountOutWei, requiresApproval, curve, token, chainId}`
- POST `trade/prepare {token, side, amountWei, sender, slippageBps}` → `{tx:{to,data,value,chainId}, quote, minOutWei}` or `{approval:{to,data,value,chainId}}`
- POST `trade/record {token, side, ethWei, tx}` after a confirmed trade (records the trade for volume/feed)
- POST `launch/prepare {name, symbol, description, logo, model, website, twitter, telegram}` → `{tx:{to,data,value,chainId}, creatorFeeRecipient, creatorTaxBps, model}`
- POST `launch/confirm {tx, model, logo, description}` → `{ok, token:T}` (call after the wallet confirms; retry on "no launch event yet")
- Auth: `AXON.login()` (wallet signs a message, sets cookie, returns `{address, csrf, hasLaunched, launches:[{token,symbol,model}], spentUsd, chatEnabled}`); `AXON.me()` returns the same or null. `AXON.state.address` is the connected wallet (may be set without a session). Listen for `document.addEventListener('axon:wallet', ...)` when the wallet connects.
- POST `chat {model, messages:[{role:"user"|"assistant", content}]}` (needs login) → `{reply, usage:{prompt_tokens, completion_tokens}, costUsd, poolAvailableUsd}`. `chat/history?model=` → `{messages:[{model,q,a,costUsd,at}]}`.
- `keys` (needs login) → `{keys:[{id,label,prefix,createdAt,calls}]}`. POST `keys {label}` → `{key (shown once), record}`. POST `keys {revoke:id}` → `{keys}`. Public endpoint for key holders: POST `api/v1/chat/completions` with `Authorization: Bearer axon_...`, OpenAI-compatible body `{model, messages}`.
- Wallet tx flow: `const prep = await api('launch/prepare', form); const {hash} = await sendTx(prep.tx, prep.tx.to); then api('launch/confirm', {tx: hash, ...})`. For trades: expected `to` is the curve (or token for approval).

## Chain facts for copy
Robinhood Chain, chain id 4663. pons v2 factory `0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e` (unaudited). Explorer https://robinhoodchain.blockscout.com. Creator tax 2% of every curve trade, paid in ETH into the pons escrow, claimed by a keeper into the treasury (its address comes from `status.treasury`, show it and link it). Chat and API keys are open to wallets that have launched a token here. Each reply is billed to the pool at the model's list price per token.

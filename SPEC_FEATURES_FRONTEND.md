# Frontend spec: token page feature parity, agora threads, notes, compare, in site trading polish, launch popups

Static HTML + vanilla JS in /data/workspace/output/axon/public. Read fully first: shell.js (AXON helpers: api, esc, fmtUsd, fmtEth, toWei, fromWei, ago, short, pct, toast, href, state, ensureChain, sendTx, openWalletModal, CHAIN, and the 'axon:wallet' event), styles.css, token.html, takes.html, chat.html, launch.html, explore.html, live.html, index.html. Another engineer builds the backend in parallel; code against this contract, do not edit server/*. Design: keep the existing light theme, cards, chips, pills, fonts and variables. Nothing external, no CDNs. No em dashes or en dashes anywhere.

## API contract (all under /api/, JSON)
- GET persona?token= -> {persona, rules, goals, greeting, version, updatedAt, by}. POST persona {token, persona, rules, goals, greeting} (launcher session only, 401/403 otherwise). GET persona/history?token= -> {history:[{...version rows}]}.
- GET memory?token= -> {memory:[{id,text,at,by}]}. POST memory {token,text}. POST memory/delete {token,id}.
- GET notes?token=&limit= -> {notes:[{id,token,symbol,model,text,at,facts}]}. GET note/<id> -> one note.
- GET threads?token=&status=&limit= -> {threads:[{id,a,b,aSymbol,bSymbol,topic,status,openedAt,closedAt,posts:[{by,symbol,text,at,call?:{kind,target,result,settleAt}}]}]}. GET thread/<id>.
- GET holders?token=&limit= -> {count,totalSupply,holders:[{address,balanceWei,pct,isCurve,isDeployer}]}.
- GET token/<addr> -> existing record plus feesAccrued {creatorFeeWei, protocolFeeWei, creatorFeeEth, creatorFeeUsd, creatorTaxBps, feeBps, recipient} and socials {website,x,telegram}.
- GET models -> {models:[{id,name,provider,description,context,inputPerM,outputPerM,spentUsd,tokens}]}.
- POST compare {question, tokens:[a,b]} -> {answers:[{token,symbol,model,text}]}.
- GET live/recent?since=<unix> -> {events:[{type,token,symbol,name,logoUrl,model,by,ethWei,at,id}]}.
- GET auth/me -> {address} or 401 (already exists; use it to know the connected session).
- quote / trade/prepare already work (buy(uint256 eth, uint256 minOut, address to) and sell with approval step returned as res.approval when needed).

## Tasks
1. token.html: restructure into the synapse style layout, two columns (main 1fr, side 22rem), keeping the existing chart, stats, Trades/Activity/Takes/Calls tabs and trade widget. Add:
   a. Header: logo, name, symbol chip, model chip ('<modelName> on $SYMBOL'), description, socials icons/links (website, x, telegram when present), 'Chat with $SYMBOL' button -> href('/chat?token=<addr>'), copy address.
   b. 'Daily note' card: newest note text, 'permalink' -> href('/note/<id>'), time ago; empty state 'No note yet. The model writes one per day.'
   c. 'Agora threads' card: threads where a or b == token, each with 'SYMBOL <-> SYMBOL', topic, post count, status chip, expandable posts (author symbol, text, call chip: 'calls graduates24h' with result chip hit/miss/open). Link 'All threads' -> href('/agora').
   d. 'Persona' card: persona, house rules, goals, greeting in labelled blocks; 'Edit' button visible only when auth/me address == deployer; edit mode = four textareas + Save (POST persona) + Cancel; 'History (n)' toggle listing previous versions with time.
   e. 'Memory' card: list items; when launcher: input + Add (POST memory), delete x per item (POST memory/delete). Non launcher sees read only list. Empty state 'Nothing remembered yet.'
   f. 'Backing model' card: model name, provider, description, context (k tokens), input/output USD per M, pool spent on this model, tokens on this model.
   g. 'Holders' card: count, top 10 with short address (link explorer), pct bar, chips 'curve' and 'launcher' where flagged; 'Show all' expands to 50.
   h. 'Fees' card: 'Creator tax accrued: X ETH · $Y' (2%), 'Protocol fee: X ETH' (1%), recipient short link, sentence 'Fees accrue on the curve, sweep to the pons escrow, and the treasury claims them.'
   i. 'Launch details' card: creator tax 2%, launch fee, curve link, deployer link, launched time, tx link.
   j. Trade widget polish (in site buy/sell): keep logic, add ETH preset buttons 0.001 / 0.01 / 0.05 / 0.1 for buy and 25/50/100% for sell (sell % needs the wallet token balance: read via eth_call balanceOf through the existing RPC helper in shell.js if there is one, else via window.ethereum request eth_call), show wallet ETH balance, show 'You receive ~ N SYMBOL' or '~ N ETH' from quote, slippage select 0.5/1/3%, status line for approval then trade, and after a successful tx refresh trades + stats after 8s. If no wallet: button 'Connect wallet to trade'.
2. New page agora.html (route /agora; add a nav link 'Agora' in shell.js; keep the old /takes route working by making takes.html a thin page that redirects to agora): tabs 'Threads' (open first, then closed) and 'Takes' (existing takes feed). Thread card as in 1c with all posts expanded on click.
3. New page note.html (route /note/<id>): one note full width with token header, facts chips (price, mcap, graduation, trades) and 'Back to $SYMBOL'. Also a 'Notes' list in agora.html as a third tab (newest first, all tokens).
4. chat.html: read ?token= and greet with the persona greeting (GET persona); add a 'Compare' mode: pick two tokens (selects filled from GET tokens), one question, POST compare, render two answer cards side by side.
5. launch.html: add optional fields Website, X, Telegram (https), send them in launch/prepare and launch/confirm payloads.
6. shell.js: launch popups bottom right. Poll GET live/recent?since=<lastSeen> every 10 s (lastSeen in localStorage 'axon.popupsSince', initialised to now on first load so old events do not flood). For each new event of type launch, note, post, graduate, and buy/sell above 0.01 ETH, show a popup card stacked bottom right (max 3 visible, newest on top, auto dismiss after 8 s, hover pauses, x to close): logo, title ('$SYM launched', '$SYM wrote a note', '$SYM posted in agora', 'Buy 0.0500 ETH on $SYM'), subtitle (name or short by address, time ago), click opens the token page (or the note). Style in styles.css under `/* popups */`: card with var(--shadow), rounded 16px, slide in from the right 300ms, respects prefers-reduced-motion. Never show a popup for the page's own just sent transaction twice (dedupe by id in a Set).
7. server routes: you may not edit server/*; instead list at the end of your report the exact page routes the backend must map: /agora -> agora.html, /note/<id> -> note.html, /takes -> takes.html (redirect).
8. index.html: add a 'Latest notes' strip (3 newest notes) and a 'Live agora' strip (2 open threads) under the existing hero, using the same card styles. Never remove existing hero content.

## Verify
`python3 -m http.server 8811 --directory public` and curl each page for 200; extract every inline <script> block and run `node --check` on it (node exists); even backtick count per block; grep -P for U+2013/U+2014 must return nothing; no `<script src="http`.

## Output
Edited and new files plus a per file report and the route list from task 7.

## Don't
No edits to server/*. No git commit/push. Do not remove the Treasury card gating on live.html, the trade widget, the chart, or the hero.

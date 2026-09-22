/* axon shell: brand, nav, wallet (EIP-6963 + window.ethereum), api helpers, formatters. Loaded by every page. */
window.AXON = (() => {
  const MARK = '<svg viewBox="0 0 100 100" fill="currentColor" aria-hidden="true"><ellipse cx="50" cy="7.9" rx="17.8" ry="7.9"/><ellipse cx="85.8" cy="29.3" rx="17.9" ry="8" transform="rotate(60 85.8 29.3)"/><ellipse cx="85.7" cy="71.7" rx="17.8" ry="7.9" transform="rotate(120 85.7 71.7)"/><ellipse cx="50" cy="92.4" rx="17.8" ry="7.8"/><ellipse cx="14.4" cy="71.6" rx="17.8" ry="7.9" transform="rotate(60 14.4 71.6)"/><ellipse cx="14.5" cy="29.3" rx="17.9" ry="8" transform="rotate(120 14.5 29.3)"/></svg>';
  window.AXON_MARK = MARK;
  if (!document.querySelector('link[rel="icon"]')) { const l = document.createElement('link'); l.rel = 'icon'; l.type = 'image/svg+xml'; l.href = '/logo.svg'; document.head.appendChild(l); }

  const BRAND = { name: 'axon', display: 'Axon', symbol: 'AXON' };
  const CHAIN = { id: 4663, hex: '0x1237', name: 'Robinhood Chain', rpc: 'https://rpc.mainnet.chain.robinhood.com', explorer: 'https://robinhoodchain.blockscout.com' };
  const NAV = [['/explore','Markets'],['/live','Live'],['/agora','Agora'],['/models','Models'],['/chat','Chat'],['/keys','API'],['/docs','Docs']];
  const base = new URL(document.querySelector('base')?.href || (location.pathname.match(/^\/preview\/[^/]+\//)?.[0] || '/'), location.origin);
  const href = p => new URL(p.replace(/^\//,''), base).pathname;
  const $ = (s, r=document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const state = { provider:null, address:null, chainId:null, wallets:[] };
  let session = null;

  // ---------- dev mode theme
  const isDev = () => document.documentElement.getAttribute('data-theme') === 'dev';
  function setTheme(dev){ try{ dev ? localStorage.setItem('axon.theme','dev') : localStorage.removeItem('axon.theme'); }catch(e){} location.reload(); }

  // ---------- api
  async function api(path, body, opts={}) {
    const r = await fetch(new URL('api/' + path.replace(/^\//,''), base), {
      credentials:'same-origin',
      ...(body !== undefined ? { method:'POST', headers:{'Content-Type':'application/json', ...(session?.csrf ? {'X-CSRF-Token':session.csrf} : {})}, body:JSON.stringify(body) } : {}),
      ...opts });
    let d; try { d = await r.json(); } catch { throw Error('The server did not return a usable response.'); }
    if (!r.ok) throw Error(d.error || 'This request could not be completed.');
    return d;
  }

  // ---------- formatters
  const fmtUsd = n => n == null || !isFinite(n) ? '...' : n >= 1e9 ? '$'+(n/1e9).toFixed(2)+'B' : n >= 1e6 ? '$'+(n/1e6).toFixed(2)+'M' : n >= 1e3 ? '$'+(n/1e3).toFixed(1)+'K' : n >= 1 ? '$'+n.toFixed(2) : n === 0 ? '$0.00' : subscript(n);
  function subscript(n) { // 0.0₅443 style for tiny prices
    const s = n.toExponential(2); const [m, e] = s.split('e'); const exp = -parseInt(e,10);
    if (exp <= 3) return '$' + n.toFixed(Math.min(8, exp+2));
    const zeros = exp - 1; const digits = m.replace('.','').slice(0,3);
    return '$0.0' + String(zeros).replace(/\d/g, d => '₀₁₂₃₄₅₆₇₈₉'[d]) + digits;
  }
  const fmtEth = (wei, dp=4) => wei == null ? '...' : (Number(BigInt(wei)) / 1e18).toFixed(dp).replace(/\.?0+$/,'') || '0';
  const fromWei = wei => (Number(BigInt(wei))/1e18).toString();
  const toWei = v => { const [w, f=''] = String(v).trim().split('.'); if (!/^\d*$/.test(w) || !/^\d*$/.test(f) || (w===''&&f==='')) throw Error('Enter a valid amount.'); return (BigInt(w||'0')*10n**18n + BigInt((f+'0'.repeat(18)).slice(0,18))).toString(); };
  const ago = ts => { const s = Math.max(0, Date.now()/1000 - ts); if (s<60) return Math.floor(s)+'s'; if (s<3600) return Math.floor(s/60)+'m'; if (s<86400) return Math.floor(s/3600)+'h'; return (s/86400).toFixed(s<86400*10?1:0).replace(/\.0$/,'')+'d'; };
  const short = a => a ? a.slice(0,6)+'…'+a.slice(-4) : '';
  const pct = x => x == null ? '...' : (x*100).toFixed(x*100 < 10 ? 1 : 0) + '%';
  function toast(m, ms=3200) { const t = document.createElement('div'); t.className='toast'; t.textContent=m; document.body.appendChild(t); setTimeout(()=>t.remove(), ms); }

  // ---------- cookie notice (bottom right, non-blocking, separate from the terms gate)
  function cookieBar() {
    const CK = 'axon_cookies';
    if (localStorage.getItem(CK) || document.cookie.split(';').some(c => /^axon_cookies=/.test(c.trim()))) return;
    const set = v => { document.cookie = CK + '=' + v + '; max-age=31536000; path=/; SameSite=Lax' + (location.protocol === 'https:' ? '; Secure' : ''); localStorage.setItem(CK, v); };
    const el = document.createElement('div'); el.className = 'cookie-pop';
    el.innerHTML = `<div class="cookie-t">Cookies</div><p>We use one first-party cookie to remember your choices. No trackers, no third-party analytics.</p><div class="cookie-actions"><button class="btn ghost" data-no>Decline</button><button class="btn accent" data-ok>Accept</button></div>`;
    el.addEventListener('click', e => { if (e.target.closest('[data-ok]')) set('1'); else if (e.target.closest('[data-no]')) set('0'); else return; el.classList.add('bye'); setTimeout(() => el.remove(), 300); });
    const mount = () => document.body.appendChild(el);
    document.body ? mount() : document.addEventListener('DOMContentLoaded', mount);
  }

  // ---------- entry gate (terms). Must be accepted before using the site.
  (function gate() {
    const KEY = 'axon_consent', EXIT = 'https://www.ponsfamily.com';
    const has = () => document.cookie.split(';').some(c => c.trim().startsWith(KEY + '=1')) || localStorage.getItem(KEY) === '1';
    if (has()) { const mount = () => cookieBar(); document.body ? mount() : document.addEventListener('DOMContentLoaded', mount); return; }
    const accept = () => { document.cookie = KEY + '=1; max-age=31536000; path=/; SameSite=Lax' + (location.protocol === 'https:' ? '; Secure' : ''); localStorage.setItem(KEY, '1'); m.classList.add('out'); document.documentElement.classList.remove('gated'); setTimeout(() => m.remove(), 320); cookieBar(); };
    const leave = () => { location.replace(EXIT); };
    const m = document.createElement('div'); m.className = 'modal gate'; m.setAttribute('role', 'dialog'); m.setAttribute('aria-modal', 'true');
    m.innerHTML = `<div class="card modal-card gate-card">
      <div class="gate-mark">${MARK}</div>
      <h2 class="modal-title">Before you enter</h2>
      <p>axon is a token launcher on Robinhood Chain. Tokens launched here are experimental and can go to zero. Nothing on this site is financial advice. Trades are on-chain and cannot be reversed.</p>
      <p>By entering you confirm you are of legal age where you live, you are not in a restricted jurisdiction, and you accept the <a href="/docs#limits">honest limits</a> of this product.</p>
      <div class="gate-actions"><button class="btn ghost" data-leave>I do not accept</button><button class="btn accent" data-accept>Accept and enter</button></div>
    </div>`;
    m.addEventListener('click', e => { if (e.target.closest('[data-accept]')) accept(); else if (e.target.closest('[data-leave]')) leave(); });
    m.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); } });
    document.documentElement.classList.add('gated');
    const mount = () => { document.body.appendChild(m); m.querySelector('[data-accept]').focus(); };
    document.body ? mount() : document.addEventListener('DOMContentLoaded', mount);
  })();

  // ---------- wallet
  window.addEventListener('eip6963:announceProvider', e => { if (!state.wallets.find(w => w.info.uuid === e.detail.info.uuid)) state.wallets.push(e.detail); });
  window.dispatchEvent(new Event('eip6963:requestProvider'));
  function providers() { const list = [...state.wallets]; if (!list.length && window.ethereum) list.push({ info:{ name: window.ethereum.isRabby ? 'Rabby' : window.ethereum.isMetaMask ? 'MetaMask' : 'Browser wallet', icon:'' }, provider: window.ethereum }); return list; }
  async function connectWith(p) {
    const [addr] = await p.provider.request({ method:'eth_requestAccounts' });
    state.provider = p.provider; state.address = addr; state.chainId = await p.provider.request({ method:'eth_chainId' });
    p.provider.on?.('accountsChanged', a => { state.address = a[0] || null; session = null; renderNav(); });
    p.provider.on?.('chainChanged', c => { state.chainId = c; });
    localStorage.setItem('axon.wallet', p.info.name); renderNav();
    document.dispatchEvent(new CustomEvent('axon:wallet', { detail:{ address: addr } }));
  }
  function openWalletModal() {
    return new Promise((resolve, reject) => {
      const list = providers(); const m = document.createElement('div'); m.className='modal';
      m.innerHTML = `<div class="card modal-card"><button class="modal-x" data-x aria-label="Close"><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M1 1l12 12M13 1L1 13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" fill="none"/></svg></button><h2 class="modal-title">Connect a wallet</h2><div class="wallet-list">${list.length ? list.map((w,i)=>`<button data-i="${i}">${w.info.icon?`<img src="${esc(w.info.icon)}" alt="">`:''}<span>${esc(w.info.name)}</span></button>`).join('') : '<div class="empty">No browser wallet detected. Install MetaMask, Rabby or another EIP-1193 wallet.</div>'}</div></div>`;
      m.onclick = async e => { if (e.target === m || e.target.closest('[data-x]')) { m.remove(); reject(Error('Cancelled.')); return; } const b = e.target.closest('[data-i]'); if (!b) return; try { await connectWith(list[+b.dataset.i]); m.remove(); resolve(); } catch (err) { toast(err.message); } };
      document.body.appendChild(m);
    });
  }
  async function ensureChain() {
    if (!state.provider) await openWalletModal();
    const p = state.provider; let c = await p.request({ method:'eth_chainId' });
    if (parseInt(c,16) !== CHAIN.id) {
      try { await p.request({ method:'wallet_switchEthereumChain', params:[{ chainId: CHAIN.hex }] }); }
      catch (e) { if (e.code === 4902) await p.request({ method:'wallet_addEthereumChain', params:[{ chainId: CHAIN.hex, chainName: CHAIN.name, nativeCurrency:{ name:'Ether', symbol:'ETH', decimals:18 }, rpcUrls:[CHAIN.rpc], blockExplorerUrls:[CHAIN.explorer] }] }); else throw e; }
      c = await p.request({ method:'eth_chainId' });
      if (parseInt(c,16) !== CHAIN.id) throw Error('Switch your wallet to Robinhood Chain before continuing.');
    }
    state.chainId = c;
  }
  // ---------- dev mode: one signature at entry, then a local key signs everything
  const DEV_ACK = 'axon.dev.ack', DEV_SK = 'axon.dev.sk';
  const devSk = () => { try { return localStorage.getItem(DEV_SK); } catch (e) { return null; } };
  const devOn = () => isDev() && !!devSk();
  let _v = null;
  async function viem() {
    if (_v) return _v;
    const [core, acct] = await Promise.all([import('https://esm.sh/viem@2.21.4'), import('https://esm.sh/viem@2.21.4/accounts')]);
    _v = { ...core, ...acct }; return _v;
  }
  const DEV_CHAIN = { id: CHAIN.id, name: CHAIN.name, nativeCurrency: { name:'Ether', symbol:'ETH', decimals:18 }, rpcUrls:{ default:{ http:[CHAIN.rpc] } } };
  async function devClients(create) {
    const v = await viem();
    let sk = devSk();
    if (!sk) {
      if (!create) return null;
      sk = '0x' + [...crypto.getRandomValues(new Uint8Array(32))].map(b => b.toString(16).padStart(2,'0')).join('');
      localStorage.setItem(DEV_SK, sk);
    }
    const account = v.privateKeyToAccount(sk);
    return { v, account,
      pub: v.createPublicClient({ chain: DEV_CHAIN, transport: v.http(CHAIN.rpc) }),
      wal: v.createWalletClient({ account, chain: DEV_CHAIN, transport: v.http(CHAIN.rpc) }) };
  }
  async function devBalance() { try { const c = await devClients(false); if (!c) return null; return await c.pub.getBalance({ address: c.account.address }); } catch (e) { return null; } }
  async function devSend(tx) {
    const c = await devClients(false); if (!c) throw Error('No dev key on this browser.');
    const bal = await c.pub.getBalance({ address: c.account.address });
    if (bal <= BigInt(tx.value)) throw Error('The dev key is out of ETH. Top it up from the dev panel.');
    const hash = await c.wal.sendTransaction({ to: tx.to, data: tx.data, value: BigInt(tx.value) });
    toast('Sent from the dev key. No signature asked.');
    const r = await c.pub.waitForTransactionReceipt({ hash });
    if (r.status !== 'success') throw Error('The transaction reverted on-chain.');
    return { hash, receipt: r };
  }
  async function devPanel() {
    const c = await devClients(true);
    const m = document.createElement('div'); m.className = 'modal dev-panel';
    const row = (k, v) => `<div class="dev-row"><span>${k}</span><b>${v}</b></div>`;
    m.innerHTML = `<div class="card modal-card dev-card"><button class="modal-x" data-x aria-label="Close"><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M1 1l12 12M13 1L1 13" stroke="currentColor" stroke-width="2"/></svg></button>
      <h2 class="modal-title">Dev key</h2>
      <p class="dev-note">Every on-chain action in dev mode is signed by this key, with no wallet prompt. It spends real ETH on chain ${CHAIN.id}.</p>
      ${row('Address', `<span class="mono">${short(c.account.address)}</span>`)}
      ${row('Balance', `<span class="mono" data-bal>checking…</span>`)}
      <div class="dev-fund"><input class="inp" data-amt type="text" inputmode="decimal" value="0.01" aria-label="Amount in ETH"><button class="btn accent" data-fund>Fund from my wallet</button></div>
      <div class="gate-actions"><button class="btn ghost" data-drain>Send it all back</button><button class="btn ghost" data-copy>Copy private key</button></div>
      <p class="dev-warn">Anyone with access to this browser can spend this key. Keep only what you are willing to lose.</p></div>`;
    document.body.appendChild(m);
    const setBal = async () => { const b = await devBalance(); const el = m.querySelector('[data-bal]'); if (el) el.textContent = b === null ? 'unreachable' : (Number(b) / 1e18).toFixed(5) + ' ETH'; };
    setBal();
    m.onclick = async e => {
      if (e.target === m || e.target.closest('[data-x]')) return m.remove();
      try {
        if (e.target.closest('[data-copy]')) { await navigator.clipboard.writeText(devSk()); return toast('Private key copied.'); }
        if (e.target.closest('[data-fund]')) {
          if (!state.address) await openWalletModal();
          await ensureChain();
          const eth = Number(m.querySelector('[data-amt]').value); if (!(eth > 0)) throw Error('Enter an amount.');
          const val = '0x' + BigInt(Math.round(eth * 1e18)).toString(16);
          await state.provider.request({ method:'eth_sendTransaction', params:[{ from: state.address, to: c.account.address, value: val }] });
          toast('Funding sent. Balance updates in a few seconds.'); setTimeout(setBal, 6000); return;
        }
        if (e.target.closest('[data-drain]')) {
          if (!state.address) await openWalletModal();
          const bal = await c.pub.getBalance({ address: c.account.address });
          const gp = await c.pub.getGasPrice(); const fee = gp * 21000n * 2n;
          if (bal <= fee) throw Error('Not enough left to cover gas.');
          const hash = await c.wal.sendTransaction({ to: state.address, value: bal - fee });
          toast('Sent back to your wallet.'); await c.pub.waitForTransactionReceipt({ hash }); setBal(); return;
        }
      } catch (err) { toast(err.message || 'That did not go through.'); }
    };
  }
  function devGate() {
    if (!isDev()) return;
    try { if (localStorage.getItem(DEV_ACK) === '1') return; } catch (e) { return; }
    const m = document.createElement('div'); m.className = 'modal gate dev-gate'; m.setAttribute('role','dialog'); m.setAttribute('aria-modal','true');
    m.innerHTML = `<div class="card modal-card gate-card">
      <h2 class="modal-title">Dev mode</h2>
      <p>Dev mode is the fast lane. No animation, no video, no chrome, and no wallet prompt between you and the chain.</p>
      <p>You sign <b>once</b> when you turn it on. That single signature opens your session across the whole site, so nothing asks you to sign in again.</p>
      <p>After that, axon creates a <b>dev key inside this browser</b>. You fund it from your wallet, and every launch, buy and sell is signed by that key on its own.</p>
      <div class="dev-warnbox"><b>Read this before you accept.</b><ul>
        <li>Transactions go through with <b>no confirmation step</b>. A click is the whole flow.</li>
        <li>It spends <b>real ETH</b> on chain ${CHAIN.id}. Nothing here is a testnet.</li>
        <li>The dev key sits in this browser's storage. Anyone on this machine can drain it. It is not backed up.</li>
        <li>Mistakes are final. There is no confirm dialog to catch a wrong click and no way to reverse a transaction.</li>
        <li>Fund it with small amounts only. Send the rest back when you are done.</li>
      </ul></div>
      <div class="gate-actions"><button class="btn ghost" data-no>Leave dev mode</button><button class="btn accent" data-yes>I understand, enable it</button></div>
    </div>`;
    m.addEventListener('click', async e => {
      if (e.target.closest('[data-no]')) { m.remove(); return setTheme(false); }
      if (!e.target.closest('[data-yes]')) return;
      localStorage.setItem(DEV_ACK, '1'); m.remove();
      try {
        if (!state.address) await openWalletModal();
        await login();
        await devPanel();
      } catch (err) { toast(err.message || 'Connect a wallet to finish setting up dev mode.'); }
    });
    const mount = () => document.body.appendChild(m);
    document.body ? mount() : document.addEventListener('DOMContentLoaded', mount);
  }
  function devChip() {
    if (!isDev()) return;
    const right = document.querySelector('.pill-right'); if (!right || right.querySelector('.dev-chip')) return;
    const b = document.createElement('button'); b.className = 'dev-chip'; b.type = 'button'; b.title = 'Dev key';
    b.innerHTML = '<span class="mono" data-chipbal>dev</span>';
    b.onclick = () => devPanel();
    right.insertBefore(b, right.firstChild);
    devBalance().then(v => { const el = b.querySelector('[data-chipbal]'); if (el) el.textContent = v === null ? 'dev' : 'dev ' + (Number(v)/1e18).toFixed(3); });
  }

  async function sendTx(tx, expectedTo) {
    if (!tx || tx.chainId !== CHAIN.id || !/^0x[0-9a-fA-F]{40}$/.test(tx.to) || (expectedTo && tx.to.toLowerCase() !== expectedTo.toLowerCase()) || !/^0x[0-9a-fA-F]*$/.test(tx.data) || !/^0x[0-9a-fA-F]+$/.test(tx.value)) throw Error('The transaction did not match the expected contract.');
    if (devOn()) return devSend(tx);
    await ensureChain();
    const bal = BigInt(await state.provider.request({ method:'eth_getBalance', params:[state.address,'latest'] }));
    if (bal <= BigInt(tx.value)) throw Error('Your wallet needs enough ETH for the transaction plus gas.');
    const hash = await state.provider.request({ method:'eth_sendTransaction', params:[{ from: state.address, to: tx.to, data: tx.data, value: tx.value }] });
    toast('Submitted. Waiting for confirmation.');
    for (let i = 0; i < 90; i++) { const r = await state.provider.request({ method:'eth_getTransactionReceipt', params:[hash] }); if (r) { if (parseInt(r.status,16) !== 1) throw Error('The transaction reverted on-chain.'); return { hash, receipt: r }; } await new Promise(r => setTimeout(r, 2000)); }
    throw Error('Still pending. Check your wallet, then refresh.');
  }
  // SIWE-style session: server issues a nonce, wallet signs, server sets cookie.
  async function login() {
    if (session?.address?.toLowerCase() === state.address?.toLowerCase()) return session;
    await ensureChain();
    const { nonce, message } = await api('auth/nonce', { address: state.address });
    const sig = await state.provider.request({ method:'personal_sign', params:[message, state.address] });
    session = await api('auth/verify', { address: state.address, signature: sig, nonce });
    renderNav(); return session;
  }
  async function me() { if (session) return session; try { const r = await api('auth/me'); session = r?.address ? r : null; if (session && !state.address) state.address = session.address; } catch { session = null; } return session; }

  // ---------- nav / footer
  function renderNav() {
    const path = location.pathname.replace(base.pathname.replace(/\/$/,''), '') || '/';
    const nav = $('#nav'); if (!nav) return;
    nav.innerHTML = `<div class="wrap nav-row"><div class="pill pill-left"><a class="brand" href="${href('/')}"><span class="mark">${MARK}</span><span class="wm-text">${BRAND.name}</span></a><nav class="nav-links">${NAV.map(([p,l])=>`<a href="${href(p)}" class="${path.startsWith(p)?'active':''}">${l}</a>`).join('')}</nav><button class="btn sm ghost nav-burger" id="burger" aria-label="menu">&#9776;</button></div><div class="pill pill-right"><button class="theme-tg" id="theme-tg" type="button" title="${isDev() ? 'Standard theme' : 'Dev theme'}" aria-label="Toggle theme" aria-pressed="${isDev()}"><svg viewBox="0 0 24 24" width="17" height="17" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 2.2v15.6a7.8 7.8 0 0 1 0-15.6z"/></svg></button><a class="nav-x" href="https://x.com/axonpad" target="_blank" rel="noopener" aria-label="axon on X"><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.9 1.2h3.7l-8.1 9.3L24 22.8h-7.5l-5.9-7.7-6.7 7.7H.2l8.7-9.9L0 1.2h7.7l5.3 7 6-7zm-1.3 19.4h2L6.6 3.3H4.4l13.2 17.3z"/></svg></a><a class="nav-x nav-pons" href="https://www.ponsfamily.com/launchpad" target="_blank" rel="noopener" aria-label="axon on pons"><svg width="17" height="17" viewBox="0 0 512 512" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M209 79L307 79L307 80L317 80L317 81L326 82L328 84L338 87L339 89L343 90L348 95L350 95L358 103L358 105L360 106L360 108L362 109L362 111L364 112L364 114L366 115L369 121L369 124L372 129L373 139L374 139L374 263L373 263L373 268L372 268L372 271L368 279L361 286L351 291L342 292L342 293L264 293L264 294L259 295L255 299L254 305L253 305L253 393L252 393L251 403L248 409L241 417L239 417L236 420L229 421L229 422L189 423L189 422L179 422L179 421L172 420L162 415L160 412L158 412L149 403L149 401L145 397L144 392L142 391L142 388L140 385L139 377L138 377L138 149L139 149L139 138L140 138L140 132L142 129L142 125L147 115L153 108L153 106L163 96L165 96L172 90L184 84L194 82L194 81L209 80ZM210 82L207 84L197 85L195 87L212 86L212 85L244 85L244 84L239 84L239 83L230 84L230 83ZM310 83L309 84L297 84L297 85L321 87L319 85L315 85L314 83ZM210 89L200 90L200 91L190 93L188 95L185 95L184 97L177 99L175 102L170 104L163 111L163 113L159 116L159 118L156 120L155 124L152 127L150 137L149 137L150 363L151 363L152 298L153 298L152 290L153 290L153 237L154 237L154 233L153 233L154 231L154 148L155 148L155 142L156 142L156 138L157 138L157 134L160 129L160 126L162 122L164 121L166 115L168 114L170 108L173 106L173 104L182 102L183 100L187 100L192 97L210 95L210 94L307 94L307 95L297 95L297 96L283 97L283 98L263 98L263 99L217 99L217 100L201 99L201 100L195 100L195 101L189 102L175 111L175 113L171 116L167 124L168 126L165 129L165 132L162 133L160 140L159 140L159 145L158 145L159 267L160 267L162 218L163 218L162 214L163 214L163 191L164 191L164 170L165 170L165 140L166 140L166 134L168 134L169 131L173 127L175 127L176 124L178 124L181 120L184 120L185 118L191 115L202 113L202 111L206 112L208 110L210 111L210 110L216 110L216 109L308 108L308 109L315 109L317 111L321 111L321 112L324 112L325 114L333 116L344 127L345 132L349 136L351 134L350 122L342 108L345 109L345 111L352 117L353 121L355 121L355 119L350 114L350 112L347 110L347 108L345 108L345 106L342 105L339 101L337 101L336 99L334 99L333 97L329 95L326 95L324 93L321 93L315 90L307 90L307 89ZM359 121L358 121L358 125L359 125L361 135L362 135L362 147L363 147L363 152L364 152L364 200L365 200L365 218L366 218L366 142L365 142L364 131ZM146 129L144 132L143 144L142 144L142 270L143 270L143 148L144 148L144 138L145 138ZM366 243L364 246L363 253L360 257L358 267L361 266L363 260L365 259L364 256L365 256L365 251L366 251ZM262 277L246 281L243 287L244 288L247 287L251 282L255 280L266 279ZM271 277L270 279L277 279L277 278L321 279L321 278L326 278L326 277ZM298 282L297 283L265 283L265 284L334 284L331 282ZM252 286L248 288L246 296L247 294L248 295L250 294L249 292L250 290L251 290L250 292L254 292L255 288ZM244 348L243 348L242 382L238 390L238 397L243 391ZM167 405L166 406L169 407L170 409L178 411L178 412L182 412L182 413L201 413L201 412L196 412L190 409L181 410L171 405Z"/></svg></a>${state.address ? `<button class="btn sm ghost mono" data-acct>${short(state.address)}</button>` : `<button class="btn sm ghost" data-connect>Connect wallet</button>`}<a class="btn sm accent" href="${href('/launch')}">Launch a coin</a></div></div><div class="nav-mobile" id="navm"><button class="theme-tg" id="theme-tg-m" type="button" title="${isDev() ? 'Standard theme' : 'Dev theme'}" aria-label="Toggle theme" aria-pressed="${isDev()}"><svg viewBox="0 0 24 24" width="17" height="17" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 2.2v15.6a7.8 7.8 0 0 1 0-15.6z"/></svg></button>${NAV.map(([p,l])=>`<a href="${href(p)}" class="${path.startsWith(p)?'active':''}">${l}</a>`).join('')}<div class="nm-actions">${state.address ? `<button class="btn sm ghost mono" data-acct>${short(state.address)}</button>` : `<button class="btn sm ghost" data-connect>Connect wallet</button>`}<a class="btn sm accent" href="${href('/launch')}">Launch a coin</a></div></div>`;
    const stuck = () => { if (window.scrollY > 8) nav.setAttribute('data-stuck',''); else nav.removeAttribute('data-stuck'); };
    if (!nav.dataset.scrollBound) { nav.dataset.scrollBound = '1'; addEventListener('scroll', stuck, { passive: true }); }
    stuck();
    const tg = $('#theme-tg'); if (tg) tg.addEventListener('click', () => setTheme(!isDev()));
    devChip();
    const tgm = $('#theme-tg-m'); if (tgm) tgm.addEventListener('click', () => setTheme(!isDev()));
    // sliding indicator under the active tab; follows hover and returns to the active page
    const links = $('.nav-links', nav); if (links && !isDev()) {
      const ind = document.createElement('span'); ind.className = 'nav-ind'; links.appendChild(ind);
      const moveTo = a => { if (!a) { ind.classList.remove('on'); return; } ind.style.left = (a.offsetLeft + 12) + 'px'; ind.style.width = Math.max(0, a.offsetWidth - 24) + 'px'; ind.classList.add('on'); };
      const active = () => links.querySelector('a.active');
      requestAnimationFrame(() => { ind.style.transition = 'none'; moveTo(active()); requestAnimationFrame(() => { ind.style.transition = ''; }); });
      for (const a of links.querySelectorAll('a')) a.addEventListener('mouseenter', () => moveTo(a));
      links.addEventListener('mouseleave', () => moveTo(active()));
      addEventListener('resize', () => moveTo(active()), { passive: true });
    }
    // fade the page out before a same-site navigation when the browser lacks cross-document view transitions
    if (!nav.dataset.navBound) { nav.dataset.navBound = '1'; document.addEventListener('click', e => {
      if (isDev()) return; // no page-leave fade in dev mode
      const a = e.target.closest('a[href]'); if (!a || a.target === '_blank' || a.hasAttribute('download') || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      const u = new URL(a.href, location.href); if (u.origin !== location.origin || (u.pathname === location.pathname && u.hash)) return;
      if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      if (CSS.supports && CSS.supports('view-transition-name', 'x') && 'navigation' in window) return; // native cross document transition handles it
      const pg = document.querySelector('main.page'); if (!pg) return;
      e.preventDefault(); pg.classList.add('leaving'); setTimeout(() => { location.href = u.href; }, 190);
    }); }
    for (const b of document.querySelectorAll('[data-connect]')) b.addEventListener('click', () => openWalletModal().catch(e => e.message !== 'Cancelled.' && toast(e.message)));
    for (const b of document.querySelectorAll('[data-acct]')) b.addEventListener('click', () => { if (confirm('Disconnect this wallet from the page?')) { state.provider = null; state.address = null; session = null; localStorage.removeItem('axon.wallet'); api('auth/logout', {}).catch(()=>{}); renderNav(); } });
    const burger = $('#burger'), navm = $('#navm');
    if (burger && navm) {
      const place = () => { const r = burger.getBoundingClientRect(); navm.style.top = (r.bottom + 8) + 'px'; navm.style.right = Math.max(12, innerWidth - r.right) + 'px'; };
      burger.addEventListener('click', e => { e.stopPropagation(); place(); navm.classList.toggle('open'); });
      document.addEventListener('click', e => { if (navm.classList.contains('open') && !navm.contains(e.target)) navm.classList.remove('open'); });
      document.addEventListener('keydown', e => { if (e.key === 'Escape') navm.classList.remove('open'); });
      addEventListener('resize', () => { if (navm.classList.contains('open')) place(); }, { passive: true });
    }
    if (!document.getElementById('mit-modal')) {
      const m = document.createElement('div');
      m.id = 'mit-modal';
      m.style.cssText = 'display:none';
      m.className = 'modal';
      m.innerHTML = '<div class="sheet" style="max-width:540px;width:100%;padding:2rem 2.5rem;border-radius:24px;background:var(--panel-a);box-shadow:0 24px 60px -10px rgba(11,26,51,.18);position:relative"><button onclick="document.getElementById(\'mit-modal\').style.display=\'none\'" style="position:absolute;top:1rem;right:1rem;background:none;border:none;cursor:pointer;font-size:20px;color:#666;line-height:1" aria-label="Close">&times;</button><h2 style="margin:0 0 1.2rem;font-family:var(--head);font-size:1.3rem;font-weight:700">MIT License</h2><pre style="white-space:pre-wrap;word-break:break-word;font-family:var(--mono);font-size:13px;line-height:1.7;color:var(--ink);margin:0">Copyright (c) 2026 Axon\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the &quot;Software&quot;), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED &quot;AS IS&quot;, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.</pre></div>';
      m.addEventListener('click', e => { if (e.target === m) m.style.display = 'none'; });
      document.body.appendChild(m);
    }
    if (!isDev() && !document.querySelector('.sky-bg')) {
      const sky = document.createElement('div');
      sky.className = 'sky-bg';
      sky.innerHTML = '<video muted loop playsinline autoplay preload="auto" src="/static/assets/sky-bg.mp4"></video>';
      document.body.prepend(sky);
      const v = sky.firstElementChild;
      v.addEventListener('canplay', () => v.classList.add('on'), { once: true });
      v.play().catch(() => {});
    }
    document.querySelectorAll('.btn.cta .mark:empty').forEach(m => m.innerHTML = MARK);
    const f = $('#footer'); if (f) f.innerHTML = `<div class="wrap"><div class="fgrid"><div><a class="brand" href="${href('/')}"><span class="mark">${MARK}</span>${BRAND.name}</a><p class="ftxt">Every trade fires a thought. Tokens on pons v2, Robinhood Chain. Inference through OpenRouter.</p></div><div><p class="eyebrow">Product</p><div class="flinks"><a href="${href('/launch')}">Launch a coin</a><a href="${href('/explore')}">Markets</a><a href="${href('/live')}">Live</a><a href="${href('/explore')}?view=compare">Compare</a><a href="${href('/leaderboard')}">Leaderboards</a></div></div><div><p class="eyebrow">Under the hood</p><div class="flinks"><a href="${href('/article')}">What is axon?</a><a href="${href('/docs')}">Notes</a><a href="${href('/takes')}">Agora</a><a href="${href('/offspring')}">Offspring</a><a href="${CHAIN.explorer}" target="_blank" rel="noopener">Explorer</a></div></div><div><p class="eyebrow">Socials</p><div class="flinks"><a href="https://x.com/axonpad" target="_blank" rel="noopener" class="f-x"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-label="X" style="vertical-align:middle;margin-right:4px"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>@axonpad</a></div></div></div><div class="fbottom"><span>&copy; ${new Date().getFullYear()} ${BRAND.display}.</span><span class="mono"><a href="#" id="f-mit" onclick="document.getElementById('mit-modal').style.display='grid';return false">License</a> · pons v2 · Robinhood Chain</span></div></div>`;
  }
  async function autoReconnect() {
    const want = localStorage.getItem('axon.wallet'); if (!want) return;
    await new Promise(r => setTimeout(r, 150));
    const p = providers().find(w => w.info.name === want); if (!p) return;
    try { const accts = await p.provider.request({ method:'eth_accounts' }); if (accts[0]) { state.provider = p.provider; state.address = accts[0]; state.chainId = await p.provider.request({ method:'eth_chainId' }); renderNav(); document.dispatchEvent(new CustomEvent('axon:wallet', { detail:{ address: accts[0] } })); } } catch {}
  }

  /* popups: bottom right launch / trade / graduation / note feed */
  (function popups(){
    const KEY='axon.popupsSince'; const seen=new Set(); let since=Number(localStorage.getItem(KEY)||0); if(!since){ since=Math.floor(Date.now()/1000); localStorage.setItem(KEY,String(since)); }
    let stack=null;
    function box(){ if(!stack){ stack=document.createElement('div'); stack.className='pops'; document.body.appendChild(stack); } return stack; }
    function title(e){
      if(e.type==='launch') return `${e.symbol} just launched`;
      if(e.type==='graduated') return `${e.symbol} graduated to the DEX`;
      if(e.type==='trade') return `${e.side==='sell'?'Sell':'Buy'} on ${e.symbol}${e.ethAmount?` · ${Number(e.ethAmount).toFixed(4)} ETH`:''}`;
      if(e.type==='note') return `${e.symbol} wrote today's note`;
      if(e.type==='post') return `${e.symbol} posted in the agora`;
      return e.symbol||'axon';
    }
    function show(e){
      const st=box(); if(st.children.length>=3) st.firstElementChild?.remove();
      const el=document.createElement('a'); el.className='pop pop-'+esc(e.type||'x');
      el.href = e.type==='note' && e.noteId ? href('/note/'+e.noteId) : href('/token/'+e.token);
      el.innerHTML = `<img class="pop-logo" src="${href(e.logoUrl||('/api/token/'+e.token+'/logo'))}" alt="" onerror="this.style.visibility='hidden'"><div class="pop-body"><div class="pop-title">${esc(title(e))}</div><div class="pop-sub">${esc(e.name||'')}${e.model?` · ${esc(String(e.model).split('/').pop())}`:''}<span class="pop-time"> · ${esc(ago(e.at))}</span></div></div><button class="pop-x" aria-label="dismiss">&times;</button>`;
      let t=setTimeout(()=>el.remove(),8000);
      el.onmouseenter=()=>clearTimeout(t); el.onmouseleave=()=>{ t=setTimeout(()=>el.remove(),4000); };
      el.querySelector('.pop-x').onclick=(ev)=>{ ev.preventDefault(); ev.stopPropagation(); el.remove(); };
      st.appendChild(el); if (isDev()) el.classList.add('in'); else requestAnimationFrame(()=>el.classList.add('in'));
    }
    async function tick(){
      try{ const r=await api('live/recent?since='+since); const list=(r.events||[]).slice().sort((a,b)=>a.at-b.at);
        for(const e of list){ if(!e.id||seen.has(e.id)) continue; seen.add(e.id); if(e.at>since) since=e.at; show(e); }
        localStorage.setItem(KEY,String(since));
      }catch(_){}
    }
    document.addEventListener('DOMContentLoaded',()=>{ setTimeout(tick,1500); setInterval(tick,10000); });
  })();

  /* themed dropdowns: keeps the native <select> as the source of truth, paints an in page listbox so the scrollbar is ours */
  function fancySelect(sel){
    if(sel.dataset.xsel||sel.multiple||sel.size>1) return;
    sel.dataset.xsel='1';
    const wrap=document.createElement('div');
    wrap.className='xsel'+(sel.classList.contains('sel')?' sm inline':'');
    sel.parentNode.insertBefore(wrap,sel); wrap.appendChild(sel);
    const btn=document.createElement('button'); btn.type='button'; btn.className='xsel-btn';
    btn.setAttribute('aria-haspopup','listbox'); btn.setAttribute('aria-expanded','false');
    btn.innerHTML='<span class="xsel-val"></span>';
    const menu=document.createElement('div'); menu.className='xsel-menu'; menu.setAttribute('role','listbox');
    wrap.appendChild(btn); wrap.appendChild(menu);
    let cursor=-1;
    const opts=()=>Array.from(sel.options);
    function paint(){
      const cur=sel.selectedIndex;
      btn.querySelector('.xsel-val').textContent = cur>=0 ? sel.options[cur].text : '';
      menu.innerHTML='';
      opts().forEach((o,i)=>{
        const row=document.createElement('div');
        row.className='xsel-opt'; row.setAttribute('role','option');
        row.setAttribute('aria-selected', i===cur?'true':'false');
        row.dataset.i=i;
        const t=o.text; const mt=t.match(/^(.*)\s\(([^()]+)\)$/);
        row.innerHTML = mt ? `<span>${esc(mt[1])}</span><small>${esc(mt[2])}</small>` : `<span>${esc(t)}</span>`;
        if(o.disabled) row.style.opacity='.45';
        menu.appendChild(row);
      });
    }
    function moveCursor(i){
      const rows=Array.from(menu.children); if(!rows.length) return;
      cursor=Math.max(0,Math.min(rows.length-1,i));
      rows.forEach((r,n)=>r.classList.toggle('cursor',n===cursor));
      rows[cursor].scrollIntoView({block:'nearest'});
    }
    function open(){
      if(wrap.classList.contains('open')) return;
      paint();
      const below=window.innerHeight-wrap.getBoundingClientRect().bottom;
      wrap.classList.toggle('up', below<260);
      wrap.classList.add('open'); btn.setAttribute('aria-expanded','true');
      moveCursor(Math.max(0,sel.selectedIndex));
      const cur=menu.querySelector('[aria-selected="true"]'); if(cur) cur.scrollIntoView({block:'center'});
    }
    function close(){ wrap.classList.remove('open'); btn.setAttribute('aria-expanded','false'); }
    function choose(i){
      if(i<0||i>=sel.options.length||sel.options[i].disabled) return;
      if(sel.selectedIndex!==i){ sel.selectedIndex=i; sel.dispatchEvent(new Event('input',{bubbles:true})); sel.dispatchEvent(new Event('change',{bubbles:true})); }
      paint(); close(); btn.focus();
    }
    btn.addEventListener('click',e=>{ e.preventDefault(); wrap.classList.contains('open')?close():open(); });
    menu.addEventListener('mousedown',e=>e.preventDefault());
    menu.addEventListener('click',e=>{ const r=e.target.closest('.xsel-opt'); if(r) choose(+r.dataset.i); });
    btn.addEventListener('keydown',e=>{
      const isOpen=wrap.classList.contains('open');
      if(e.key==='ArrowDown'||e.key==='ArrowUp'){ e.preventDefault(); if(!isOpen){ open(); return; } moveCursor(cursor+(e.key==='ArrowDown'?1:-1)); }
      else if(e.key==='Enter'||e.key===' '){ e.preventDefault(); isOpen?choose(cursor):open(); }
      else if(e.key==='Escape'&&isOpen){ e.preventDefault(); close(); }
      else if(e.key==='Home'&&isOpen){ e.preventDefault(); moveCursor(0); }
      else if(e.key==='End'&&isOpen){ e.preventDefault(); moveCursor(sel.options.length-1); }
      else if(isOpen&&e.key.length===1){ const q=e.key.toLowerCase(); const i=opts().findIndex(o=>o.text.toLowerCase().startsWith(q)); if(i>=0) moveCursor(i); }
    });
    document.addEventListener('click',e=>{ if(!wrap.contains(e.target)) close(); });
    document.addEventListener('keydown',e=>{ if(e.key==='Escape') close(); });
    window.addEventListener('resize',close);
    new MutationObserver(()=>paint()).observe(sel,{childList:true,subtree:true,attributes:true,attributeFilter:['value']});
    sel.addEventListener('change',paint);
    const desc=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value');
    try{ Object.defineProperty(sel,'value',{get(){return desc.get.call(sel);},set(v){ desc.set.call(sel,v); paint(); },configurable:true}); }catch(_){}
    paint();
  }
  function fancySelects(root){ (root||document).querySelectorAll('select:not([data-xsel]):not([data-plain])').forEach(fancySelect); }

  // ---------- official token: reserved first slot in every market grid and table
  let _official = null;
  let _officialSync = null;
  function official() { return _official || (_official = api('official').then(d => { _officialSync = d; return d; }).catch(() => { const d = { name: 'Axon', symbol: 'AXON', pairedWith: 'Axon', token: null, live: false }; _officialSync = d; return d; })); }
  function officialLogo() { return `<span class="official-logo">${MARK}</span>`; }
  function officialCard(o) {
    const inner = `<div class="mkt-head">${officialLogo()}<div class="mkt-name"><span class="n">${esc(o.name)}</span><span class="chip">${esc(o.symbol)}</span></div></div>
      <div class="mkt-sub"><span class="mono">${o.live ? '' : 'Launching soon'}</span><span class="chip official">Paired to ${esc(o.pairedWith)}</span></div>
      <div class="mkt-stats"><span>Price <b>n/a</b></span><span>24h vol <b>n/a</b></span></div>
      <div class="mkt-grad"><span class="bar"><i style="width:0%"></i></span><span class="mono faint">0%</span></div>
      <div class="mkt-foot"><span class="chip">Official</span><span class="faint">${o.link ? `<a href="${esc(o.link)}" target="_blank" rel="noopener">link ↗</a>` : 'reserved'}</span></div>`;
    return `<div class="mkt-card official-slot placeholder">${inner}</div>`;
  }
  function officialRow(cols) {
    // cols = total column count of the table; first cell is the token cell, second is model/backs, remaining are filled with n/a except the last which gets the chip
    const o = _officialSync || { name: 'Axon', symbol: 'AXON', pairedWith: 'Axon' };
    const cells = [`<td><div class="tok">${officialLogo()}<span><span class="n">${esc(o.name)}</span><br><span class="s">${esc(o.symbol)} · paired to ${esc(o.pairedWith)}</span></span></div></td>`, `<td><span class="chip official">Official</span></td>`];
    for (let i = 2; i < cols - 1; i++) cells.push('<td class="num faint">n/a</td>');
    cells.push('<td><span class="chip">Soon</span></td>');
    return `<tr class="official-row">${cells.join('')}</tr>`;
  }

  document.addEventListener('DOMContentLoaded', () => { devGate(); renderNav(); autoReconnect(); fancySelects(); new MutationObserver(()=>fancySelects()).observe(document.body,{childList:true,subtree:true}); });
  return { devPanel, devBalance, devOn, BRAND, CHAIN, base, href, $, esc, api, fmtUsd, fmtEth, fromWei, toWei, ago, short, pct, toast, state, fancySelects, openWalletModal, ensureChain, sendTx, login, me, renderNav, official, officialCard, officialRow, setTheme, isDev };
})();

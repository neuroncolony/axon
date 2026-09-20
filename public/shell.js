/* axon shell: brand, nav, wallet (EIP-6963 + window.ethereum), api helpers, formatters. Loaded by every page. */
window.AXON = (() => {
  const BRAND = { name: 'axon', display: 'Axon', symbol: 'AXON' };
  const CHAIN = { id: 4663, hex: '0x1237', name: 'Robinhood Chain', rpc: 'https://rpc.mainnet.chain.robinhood.com', explorer: 'https://robinhoodchain.blockscout.com' };
  const NAV = [['/explore','Markets'],['/live','Live'],['/takes','Agora'],['/models','Models'],['/chat','Chat'],['/keys','API'],['/docs','Docs']];
  const base = new URL(document.querySelector('base')?.href || (location.pathname.match(/^\/preview\/[^/]+\//)?.[0] || '/'), location.origin);
  const href = p => new URL(p.replace(/^\//,''), base).pathname;
  const $ = (s, r=document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const state = { provider:null, address:null, chainId:null, wallets:[] };
  let session = null;

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
      m.innerHTML = `<div class="card"><div class="section-head" style="margin-bottom:.25rem"><h2>Connect a wallet</h2><button class="copy" data-x>close</button></div><p class="muted" style="margin:.25rem 0 0;font-size:.85rem">Robinhood Chain (${CHAIN.id}). Nothing is signed until you approve it in your wallet.</p><div class="wallet-list">${list.length ? list.map((w,i)=>`<button data-i="${i}">${w.info.icon?`<img src="${esc(w.info.icon)}" alt="">`:''}<span>${esc(w.info.name)}</span></button>`).join('') : '<div class="empty">No browser wallet detected. Install MetaMask, Rabby or another EIP-1193 wallet.</div>'}</div></div>`;
      m.onclick = async e => { if (e.target === m || e.target.dataset.x !== undefined) { m.remove(); reject(Error('Cancelled.')); return; } const b = e.target.closest('[data-i]'); if (!b) return; try { await connectWith(list[+b.dataset.i]); m.remove(); resolve(); } catch (err) { toast(err.message); } };
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
  async function sendTx(tx, expectedTo) {
    if (!tx || tx.chainId !== CHAIN.id || !/^0x[0-9a-fA-F]{40}$/.test(tx.to) || (expectedTo && tx.to.toLowerCase() !== expectedTo.toLowerCase()) || !/^0x[0-9a-fA-F]*$/.test(tx.data) || !/^0x[0-9a-fA-F]+$/.test(tx.value)) throw Error('The transaction did not match the expected contract.');
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
  async function me() { if (session) return session; try { session = await api('auth/me'); if (session?.address && !state.address) state.address = session.address; } catch { session = null; } return session; }

  // ---------- nav / footer
  function renderNav() {
    const path = location.pathname.replace(base.pathname.replace(/\/$/,''), '') || '/';
    const nav = $('#nav'); if (!nav) return;
    nav.innerHTML = `<div class="wrap nav-row"><div class="pill pill-left"><a class="brand" href="${href('/')}"><span class="mark"></span><span class="wm-text">${BRAND.name}</span></a><nav class="nav-links">${NAV.map(([p,l])=>`<a href="${href(p)}" class="${path.startsWith(p)?'active':''}">${l}</a>`).join('')}</nav><button class="btn sm ghost nav-burger" id="burger" aria-label="menu">&#9776;</button></div><div class="pill pill-right"><a class="nav-x" href="https://x.com" target="_blank" rel="noopener" aria-label="axon on X"><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.9 1.2h3.7l-8.1 9.3L24 22.8h-7.5l-5.9-7.7-6.7 7.7H.2l8.7-9.9L0 1.2h7.7l5.3 7 6-7zm-1.3 19.4h2L6.6 3.3H4.4l13.2 17.3z"/></svg></a>${state.address ? `<button class="btn sm ghost mono" data-acct>${short(state.address)}</button>` : `<button class="btn sm ghost" data-connect>Connect wallet</button>`}<a class="btn sm accent" href="${href('/launch')}">Launch a coin</a></div></div><div class="nav-mobile" id="navm">${NAV.map(([p,l])=>`<a href="${href(p)}" class="${path.startsWith(p)?'active':''}">${l}</a>`).join('')}<div class="nm-actions">${state.address ? `<button class="btn sm ghost mono" data-acct>${short(state.address)}</button>` : `<button class="btn sm ghost" data-connect>Connect wallet</button>`}<a class="btn sm accent" href="${href('/launch')}">Launch a coin</a></div></div>`;
    const stuck = () => { if (window.scrollY > 8) nav.setAttribute('data-stuck',''); else nav.removeAttribute('data-stuck'); };
    if (!nav.dataset.scrollBound) { nav.dataset.scrollBound = '1'; addEventListener('scroll', stuck, { passive: true }); }
    stuck();
    for (const b of document.querySelectorAll('[data-connect]')) b.addEventListener('click', () => openWalletModal().catch(e => e.message !== 'Cancelled.' && toast(e.message)));
    for (const b of document.querySelectorAll('[data-acct]')) b.addEventListener('click', () => { if (confirm('Disconnect this wallet from the page?')) { state.provider = null; state.address = null; session = null; localStorage.removeItem('axon.wallet'); api('auth/logout', {}).catch(()=>{}); renderNav(); } });
    $('#burger')?.addEventListener('click', () => $('#navm').classList.toggle('open'));
    const f = $('#footer'); if (f) f.innerHTML = `<div class="wrap"><div class="fgrid"><div><a class="brand" href="${href('/')}"><span class="mark"></span>${BRAND.name}</a><p class="ftxt">Every trade fires a thought. Tokens on pons v2, Robinhood Chain. Inference through OpenRouter.</p><p class="ftxt"><a class="mono" href="${CHAIN.explorer}/address/0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e" target="_blank" rel="noopener">factory 0x7eD598Bc…EC7e</a></p></div><div><p class="eyebrow">Product</p><div class="flinks"><a href="${href('/launch')}">Launch a coin</a><a href="${href('/explore')}">Markets</a><a href="${href('/live')}">Live</a><a href="${href('/explore')}?view=compare">Compare</a><a href="${href('/leaderboard')}">Leaderboards</a></div></div><div><p class="eyebrow">Under the hood</p><div class="flinks"><a href="${href('/docs')}">Notes</a><a href="${href('/takes')}">Agora</a><a href="${href('/offspring')}">Offspring</a><a href="${CHAIN.explorer}" target="_blank" rel="noopener">Explorer</a></div></div></div><div class="fbottom"><span>${BRAND.name} runs on chain ${CHAIN.id}. Tokens are experiments, not investments.</span><span class="mono">pons v2 · Robinhood Chain</span></div></div>`;
  }
  async function autoReconnect() {
    const want = localStorage.getItem('axon.wallet'); if (!want) return;
    await new Promise(r => setTimeout(r, 150));
    const p = providers().find(w => w.info.name === want); if (!p) return;
    try { const accts = await p.provider.request({ method:'eth_accounts' }); if (accts[0]) { state.provider = p.provider; state.address = accts[0]; state.chainId = await p.provider.request({ method:'eth_chainId' }); renderNav(); document.dispatchEvent(new CustomEvent('axon:wallet', { detail:{ address: accts[0] } })); } } catch {}
  }
  document.addEventListener('DOMContentLoaded', () => { renderNav(); autoReconnect(); });
  return { BRAND, CHAIN, base, href, $, esc, api, fmtUsd, fmtEth, fromWei, toWei, ago, short, pct, toast, state, openWalletModal, ensureChain, sendTx, login, me, renderNav };
})();

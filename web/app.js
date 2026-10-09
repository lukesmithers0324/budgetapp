const _fetch = window.fetch;
window.fetch = async (u, o = {}) => {
  if (o.method && o.method !== 'GET') o = {...o, headers: {...(o.headers || {}), 'X-Budget': '1'}};
  const r = await _fetch(u, o);
  if (r.status === 401) location.href = '/login.html';
  return r;
};
const $ = s => document.querySelector(s);
const usd = (c, d = 0) => (c / 100).toLocaleString(undefined, {style: 'currency', currency: 'USD', maximumFractionDigits: d, minimumFractionDigits: d});
const pct = p => Math.round(p * 100) + '%';
const sum = a => a.reduce((x, y) => x + y, 0);
const el = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
const month = $('#month'); month.value = new Date().toISOString().slice(0, 7);
let S = {sum: {categories: []}, tx: [], trends: []};

function ring(title, p, big, small, cls = 'ok', size = 120) {
  const r = size / 2 - 9, c = 2 * Math.PI * r, k = Math.max(0, Math.min(1, p || 0)), h = size / 2;
  const disc = el('div', undefined, 'disc');
  disc.innerHTML = `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="${Math.round(k * 100)} percent"><circle cx="${h}" cy="${h}" r="${r + 6}" fill="none" stroke-dasharray="1.5 4.5" style="stroke:var(--line)"/><circle cx="${h}" cy="${h}" r="${r}" fill="none" style="stroke:var(--line)" stroke-width="9"/><circle class="arc" cx="${h}" cy="${h}" r="${r}" fill="none" style="stroke:url(#g-${cls});color:var(--${cls})" stroke-width="9" stroke-linecap="round" stroke-dasharray="${c * k} ${c}" transform="rotate(-90 ${h} ${h})"/></svg>`;
  disc.append(el('b', big)); disc.style.width = size + 'px';
  const d = el('div', undefined, 'ring'); d.append(disc, el('strong', title), el('span', small));
  return d;
}

function pace() {
  const [y, m] = month.value.split('-').map(Number), days = new Date(y, m, 0).getDate();
  const daily = Array(days).fill(0);
  for (const x of S.tx) if (x.amount_cents < 0) daily[+x.date.slice(8, 10) - 1] += -x.amount_cents;
  let run = 0; const cum = daily.map(v => run += v);
  const budget = sum(S.sum.categories.map(c => c.budget_cents || 0)), now = new Date();
  const last = now.getFullYear() === y && now.getMonth() + 1 === m ? now.getDate() : days;
  const max = Math.max(cum[last - 1] || 0, budget, 1), W = 360, H = 200, L = 46, B = 24, T = 10, R = 8;
  const X = d => L + (W - L - R) * d / ((days - 1) || 1), Y = v => H - B - (H - B - T) * v / max;
  const path = cum.slice(0, last).map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join('');
  const tx = (x, yy, t, a) => `<text x="${x}" y="${yy}" text-anchor="${a}" font-size="10" style="fill:var(--mute)">${t}</text>`;
  $('#pace').setAttribute('viewBox', `0 0 ${W} ${H}`);
  $('#pace').innerHTML = `<line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" style="stroke:var(--line)"/>` +
    tx(L - 4, H - B, '$0', 'end') + tx(L - 4, T + 8, usd(max), 'end') + tx(L, H - 8, '1', 'middle') + tx(W - R, H - 8, days, 'middle') +
    (budget ? `<line x1="${L}" x2="${W - R}" y1="${Y(budget)}" y2="${Y(budget)}" stroke-dasharray="5 4" stroke-width="1.5" style="stroke:var(--over)"/>` : '') +
    (path ? `<defs><linearGradient id="pg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#8b7bff" stop-opacity=".4"/><stop offset="1" stop-color="#8b7bff" stop-opacity="0"/></linearGradient></defs><path d="${path}L${X(last - 1).toFixed(1)} ${H - B}L${X(0)} ${H - B}Z" style="fill:url(#pg)"/><path class="glow" d="${path}" fill="none" stroke-width="2.5" stroke-linejoin="round" style="stroke:var(--spent)"/>` : '');
}

function trend() {
  const t = S.trends, W = 360, H = 200, L = 8, B = 24, T = 10;
  if (!t.length) { $('#trend').setAttribute('viewBox', `0 0 ${W} 80`); $('#trend').innerHTML = `<text x="${W / 2}" y="40" text-anchor="middle" font-size="12" style="fill:var(--mute)">No history yet</text>`; return; }
  const max = Math.max(1, ...t.flatMap(r => [r.income_cents, r.spent_cents])), bw = (W - 2 * L) / t.length, h = v => (H - B - T) * v / max;
  $('#trend').setAttribute('viewBox', `0 0 ${W} ${H}`);
  $('#trend').innerHTML = t.map((r, i) => { const x = L + i * bw;
    return `<rect x="${x + bw * .12}" y="${H - B - h(r.income_cents)}" width="${bw * .36}" height="${h(r.income_cents)}" rx="2" style="fill:var(--ok)"/>` +
      `<rect x="${x + bw * .52}" y="${H - B - h(r.spent_cents)}" width="${bw * .36}" height="${h(r.spent_cents)}" rx="2" style="fill:var(--spent)"/>` +
      `<text x="${x + bw / 2}" y="${H - 8}" text-anchor="middle" font-size="10" style="fill:var(--mute)">${r.month.slice(5)}</text>`; }).join('');
}


function txns() {
  const q = $('#q').value.toLowerCase(), cf = $('#cf').value;
  const rows = S.tx.filter(x => (!q || (x.merchant || '').toLowerCase().includes(q)) && (!cf || (x.category || 'Uncategorized') === cf));
  $('#count').textContent = rows.length > 100 ? `Showing 100 of ${rows.length}` : `${rows.length} transactions`;
  $('#txns').replaceChildren(...rows.slice(0, 100).map(x => {  // bank text is untrusted: textContent only
    const tr = el('tr'); tr.append(el('td', x.date, 'date'), el('td', x.merchant), catCell(x), el('td', usd(x.amount_cents, 2), x.amount_cents > 0 ? 'num in' : 'num'));
    return tr; }));
}

async function setBudget(c) {
  const v = prompt(`Monthly budget for ${c.category}, from ${month.value} onward (dollars)`, c.budget_cents ? c.budget_cents / 100 : '');
  if (v === null || isNaN(parseFloat(v))) return;
  await fetch('/api/budget', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({category: c.category, month: month.value, amount: parseFloat(v)})});
  load();
}

async function load() {
  const m = month.value;
  try {
    const [s, tx, tr, cats] = await Promise.all([`/api/summary?month=${m}`, `/api/transactions?month=${m}&limit=2000`, '/api/trends?months=6', '/api/categories'].map(u => fetch(u).then(r => r.json())));
    CATS = cats; S = {sum: s, tx, trends: tr}; render();
  } catch (e) { $('#status').textContent = 'Could not load data. Is the server running?'; }
}

const shift = n => { const [y, m] = month.value.split('-').map(Number), d = new Date(y, m - 1 + n, 1); month.value = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'); load(); };
$('#prev').onclick = () => shift(-1); $('#next').onclick = () => shift(1);
month.addEventListener('change', load); $('#q').addEventListener('input', txns); $('#cf').addEventListener('change', txns);
(async () => {
  try { await fetch('/api/sync', {method: 'POST'}).then(r => r.json()); }
  catch (e) { $('#status').textContent = 'Sync failed. Check config.toml and the server log.'; }
  load();
})();

const PAL = ['#9b5de5', '#00bbf9', '#ffa62b', '#f72585', '#2cf58c', '#8b7bff', '#ff6b6b', '#c0c8d8'];
const colorOf = n => PAL[Math.abs([...n].reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) | 0, 7)) % PAL.length];
const pillCell = n => { const td = el('td'), p = el('span', n, 'pill'); p.style.setProperty('--c', colorOf(n)); td.append(p); return td; };

function spark(v, col) {
  if (v.length < 2) return '';
  const W = 90, H = 34, mx = Math.max(...v), mn = Math.min(...v), Y = x => H - 3 - (H - 6) * (x - mn) / ((mx - mn) || 1);
  const d = v.map((x, i) => `${i ? 'L' : 'M'}${(i * W / (v.length - 1)).toFixed(1)} ${Y(x).toFixed(1)}`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="90" height="34" aria-hidden="true"><path d="${d}L${W} ${H}L0 ${H}Z" fill="${col}" opacity=".18"/><path d="${d}" fill="none" stroke="${col}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function stats() {
  const inc = S.sum.income_cents, sp = S.sum.spent_cents, t = S.trends, i = t.findIndex(r => r.month === month.value), prev = i > 0 ? t[i - 1] : null;
  const delta = (cur, old, goodUp) => { if (!old) return ['', '']; const p = (cur - old) / Math.abs(old); return [(p >= 0 ? '↑ +' : '↓ ') + (p * 100).toFixed(1) + '%', (p >= 0) === goodUp ? 'up' : 'down']; };
  const rate = r => r.income_cents ? (r.income_cents - r.spent_cents) / r.income_cents : 0;
  const cards = [
    ['Income', usd(inc), '↓', '#9b5de5', t.map(r => r.income_cents), delta(inc, prev && prev.income_cents, true)],
    ['Spent', usd(sp), '↑', '#00bbf9', t.map(r => r.spent_cents), delta(sp, prev && prev.spent_cents, false)],
    ['Left over', usd(inc - sp), '=', '#ffa62b', t.map(r => r.income_cents - r.spent_cents), delta(inc - sp, prev && prev.income_cents - prev.spent_cents, true)],
    ['Savings rate', inc ? pct((inc - sp) / inc) : '–', '%', '#f72585', t.map(rate), ['', '']]];
  $('#stats').replaceChildren(...cards.map(([label, val, ico, c, series, [dt, cls]]) => {
    const d = el('div', undefined, 'card stat'), sk = el('div', undefined, 'spark');
    d.innerHTML = `<i class="ico" style="background:${c}">${ico}</i>`; sk.innerHTML = spark(series, c);
    d.append(el('b', val), el('span', label), el('em', dt, cls), sk);
    return d;
  }));
}

function donut() {
  const cats = S.sum.categories.filter(c => c.spent_cents > 0).sort((a, b) => b.spent_cents - a.spent_cents), tot = sum(cats.map(c => c.spent_cents));
  const r = 62, C = 2 * Math.PI * r; let off = 0, segs = '';
  for (const c of cats) {
    const f = c.spent_cents / tot;
    segs += `<circle cx="80" cy="80" r="${r}" fill="none" stroke-width="22" stroke-dasharray="${Math.max(f * C - 2, 0)} ${C}" stroke-dashoffset="${-off * C}" style="stroke:${colorOf(c.category)}" transform="rotate(-90 80 80)"/>`;
    off += f;
  }
  $('#donut').setAttribute('viewBox', '0 0 160 160');
  $('#donut').innerHTML = `<circle cx="80" cy="80" r="${r}" fill="none" stroke-width="22" style="stroke:var(--line)"/>${segs}<text x="80" y="78" text-anchor="middle" font-size="17" font-weight="700" style="fill:var(--ink)">${tot ? usd(tot) : '–'}</text><text x="80" y="96" text-anchor="middle" font-size="10" style="fill:var(--mute)">Spent</text>`;
  $('#legend').replaceChildren(...cats.slice(0, 6).map(c => { const li = el('li'); li.style.setProperty('--c', colorOf(c.category)); li.append(el('span', c.category), el('b', pct(c.spent_cents / tot))); return li; }));
}

function budgets() {
  const g = $('#cats'); g.replaceChildren();
  for (const c of [...S.sum.categories].sort((a, b) => b.spent_cents - a.spent_cents)) {
    const p = c.budget_cents ? c.spent_cents / c.budget_cents : 0, row = el('div', undefined, 'brow'), head = el('div', undefined, 'bhead');
    head.append(el('span', c.category), el('em', c.budget_cents ? `${usd(c.spent_cents)} of ${usd(c.budget_cents)}` : `${usd(c.spent_cents)}, no budget`));
    if (c.category !== 'Uncategorized') { const b = el('button', c.budget_cents ? 'Edit' : 'Set budget', 'link'); b.onclick = () => setBudget(c); head.append(b); }
    const bar = el('div', undefined, 'bar'), f = el('i'); f.style.width = Math.min(100, p * 100) + '%'; if (p > 1) f.className = 'over';
    bar.append(f); row.append(head, bar); g.append(row);
  }
}

function render() {
  const s = S.sum, inc = s.income_cents, sp = s.spent_cents, cats = s.categories;
  const bud = cats.filter(c => c.budget_cents), bT = sum(bud.map(c => c.budget_cents)), bS = sum(bud.map(c => c.spent_cents));
  const unc = (cats.find(c => c.category === 'Uncategorized') || {}).spent_cents || 0;
  $('#rings').replaceChildren(
    bT ? ring('Budget used', bS / bT, pct(bS / bT), `${usd(bS)} of ${usd(bT)}`, bS > bT ? 'over' : 'ok') : ring('Budget used', 0, '–', 'Set a budget below', 'ok'),
    inc ? ring('Savings rate', (inc - sp) / inc, pct((inc - sp) / inc), `${usd(inc - sp)} kept`, inc < sp ? 'over' : 'ok') : ring('Savings rate', 0, '–', 'No income this month', 'ok'),
    sp ? ring('Needs a category', unc / sp, pct(unc / sp), `${usd(unc)} of spending`, unc / sp > .25 ? 'over' : 'spent') : ring('Needs a category', 0, '–', 'No spending yet', 'ok'));
  const cf = $('#cf'), cur = cf.value, names = [...new Set([...cats.map(c => c.category), 'Uncategorized'])].sort();
  cf.replaceChildren(new Option('All categories', ''), ...names.map(n => new Option(n, n))); cf.value = names.includes(cur) ? cur : '';
  stats(); donut(); budgets(); pace(); trend(); txns();
}

$('#logout').onclick = async () => { await fetch('/api/logout', {method: 'POST'}); location.href = '/login.html'; };
$('#sync').onclick = async () => {
  $('#status').textContent = 'Syncing...';
  try { await fetch('/api/sync?force=true', {method: 'POST'}).then(r => r.json()); $('#status').textContent = ''; }
  catch (e) { $('#status').textContent = 'Sync failed. Check config.toml and the server log.'; }
  load();
};

async function connectBank(resume) {
  try {
    let token = resume ? localStorage.getItem('plaid_link_token') : null;
    if (!token) { token = (await fetch('/api/plaid/link-token').then(r => r.json())).link_token; localStorage.setItem('plaid_link_token', token); }
    const cfg = {token, onSuccess: async (pt, meta) => {
      localStorage.removeItem('plaid_link_token');
      await fetch('/api/plaid/exchange', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({public_token: pt, institution: meta.institution && meta.institution.name})});
      await fetch('/api/sync?force=true', {method: 'POST'});
      location.replace(location.origin + '/');
    }, onExit: (err, meta) => {
      if (err) { const bank = meta && meta.institution ? ' at ' + meta.institution.name : ''; $('#status').textContent = `Plaid Link stopped${bank}: ${err.error_code || err.error_type || 'unknown error'}. Look up that code in Plaid's docs or the dashboard logs.`; }
      else if (resume) location.replace(location.origin + '/');
    }};
    if (resume) cfg.receivedRedirectUri = location.href;
    Plaid.create(cfg).open();
  } catch (e) { $('#status').textContent = 'Could not start the bank connection. Check the [plaid] section of config.toml.'; }
}
$('#connect').onclick = () => connectBank(false);
if (location.search.includes('oauth_state_id')) connectBank(true);

let CATS = [];
function catCell(x) {
  const td = el('td'), sel = el('select', undefined, 'catsel'), cur = x.category || 'Uncategorized';
  sel.style.setProperty('--c', colorOf(cur));
  sel.setAttribute('aria-label', 'Category for ' + (x.merchant || 'transaction'));
  for (const n of ['Uncategorized', ...CATS]) sel.append(new Option(n, n, false, n === cur));
  sel.onchange = async () => {
    if (sel.value === 'Uncategorized') { sel.value = cur; return; }
    const rule = confirm(`Also categorize other "${x.merchant}" transactions, and future ones, as ${sel.value}?`);
    const r = await fetch(`/api/transactions/${x.id}/category`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({category: sel.value, make_rule: rule})});
    if (r.ok) load();
  };
  td.append(sel);
  return td;
}
$('#recat').onclick = async () => {
  const r = await fetch('/api/recategorize', {method: 'POST'}).then(r => r.json());
  $('#status').textContent = `Categorized ${r.updated} transactions.`;
  load();
};

// Gemeinsame Helfer für Verwaltung und Monitor
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k === 'value') el.value = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

async function api(path, method = 'GET', body) {
  const res = await fetch('/api' + path, {
    method, headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Fehler ' + res.status);
  return data;
}

const OUT = { single: 'Single Out', double: 'Double Out', master: 'Master Out' };
const fmtDate = d => d ? new Date(d + 'T12:00:00').toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '';

function dartLogo(size = 34) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 40 40'); s.setAttribute('width', size); s.setAttribute('height', size);
  s.innerHTML = '<circle cx="20" cy="20" r="19" fill="#111"/><circle cx="20" cy="20" r="16" fill="#2f9e63"/><circle cx="20" cy="20" r="12" fill="#f1ece0"/><circle cx="20" cy="20" r="8" fill="#d6453a"/><circle cx="20" cy="20" r="4" fill="#f1ece0"/><circle cx="20" cy="20" r="1.8" fill="#d6453a"/>';
  return s;
}

// Gruppentabelle. qualify = Anzahl Plätze, die markiert werden
function standingsTable(rows, qualify = 0) {
  return h('table', {},
    h('thead', {}, h('tr', {}, h('th', {}, '#'), h('th', {}, 'Spieler'), h('th', {}, 'Sp'), h('th', {}, 'S–N'),
      h('th', {}, 'Legs'), h('th', {}, 'Diff'))),
    h('tbody', {}, rows.map((r, i) => h('tr', { class: i < qualify ? 'q' : '' },
      h('td', {}, r.rank), h('td', {}, r.name, r.tie && r.played ? h('span', { class: 'badge r', title: 'Gleichstand – nicht aufgelöst' }, '=') : null),
      h('td', {}, r.played), h('td', {}, `${r.wins}–${r.losses}`),
      h('td', {}, `${r.legs_for}:${r.legs_against}`), h('td', { class: r.diff > 0 ? 'win' : '' }, (r.diff > 0 ? '+' : '') + r.diff)))));
}

function bracketView(ko, currentId, onClick) {
  return h('div', { class: 'bracket' }, ko.rounds.map(r => h('div', { class: 'bcol' },
    h('h3', {}, r.name, ' ', h('span', { class: 'muted', style: 'text-transform:none' }, `BO${r.best_of}`)),
    r.matches.map(m => {
      const row = (id, name, legs) => h('div', { class: m.winner ? (m.winner === id ? 'w' : 'l') : (name ? '' : 'tbd') },
        h('span', {}, name || 'offen'), h('span', {}, legs ?? ''));
      return h('div', { class: 'bm' + (m.id === currentId ? ' cur' : ''), onclick: onClick ? () => onClick(m) : null,
        style: onClick ? 'cursor:pointer' : null }, row(m.p1, m.p1_name, m.legs1), row(m.p2, m.p2_name, m.legs2));
    }))));
}

const metaSpans = (...items) => items.flat().filter(x => x != null && x !== false).map(x => x.nodeType ? x : h('span', {}, x));

// Verwaltungs-Oberfläche (Laptop)
const main = document.getElementById('main');
const ui = { sel: new Set(), form: { name: '', group_best_of: 3, group_out: 'single', ko_out: 'double', start_score: 501, groups: null },
  swap: null, ko: { size: null, best_of: null, ko_out: 'double' }, rank: { key: 'titles', dir: -1 }, h2h: { a: '', b: '' }, showDone: false };
let players = [];

function toast(msg, ok) {
  const t = h('div', { class: 'toast' + (ok ? ' ok' : '') }, msg);
  document.body.append(t);
  setTimeout(() => t.remove(), ok ? 1800 : 4500);
}
async function act(fn) {
  try { await fn(); } catch (e) { toast(e.message); }
  render();
}

const NAV = [['#/', 'Turnier'], ['#/spieler', 'Spieler'], ['#/ranking', 'Gesamt-Ranking'], ['#/duelle', 'Duelle'], ['#/archiv', 'Archiv']];
function renderNav() {
  const cur = location.hash || '#/';
  document.getElementById('nav').replaceChildren(...NAV.map(([href, label]) =>
    h('a', { href, class: (cur === href || (href !== '#/' && cur.startsWith(href))) ? 'on' : '' }, label)),
    h('a', { href: '/display', target: '_blank', style: 'border:1px solid var(--line)' }, '🖥 Monitor'));
}

async function render() {
  renderNav();
  const hash = location.hash || '#/';
  let node;
  try {
    players = await api('/players');
    if (hash === '#/') node = await activeView();
    else if (hash === '#/spieler') node = await playersView();
    else if (hash === '#/ranking') node = await rankingView();
    else if (hash === '#/duelle') node = await h2hView();
    else if (hash === '#/archiv') node = await archiveView();
    else if (hash.startsWith('#/turnier/')) node = tournamentView(await api('/tournaments/' + hash.split('/')[2]));
    else if (hash.startsWith('#/spieler/')) node = await playerDetailView(hash.split('/')[2]);
    else node = h('div', {}, 'Seite nicht gefunden');
  } catch (e) { node = h('div', { class: 'card' }, 'Fehler: ' + e.message); }
  main.replaceChildren(node);
}
window.addEventListener('hashchange', render);

// ------------------------------------------------------------------ Turnier
async function activeView() {
  const list = await api('/tournaments');
  const act = list.find(t => ['draft', 'group', 'ko'].includes(t.status));
  if (act) return tournamentView(await api('/tournaments/' + act.id));
  return await newTournamentView();
}

async function newTournamentView() {
  const f = ui.form;
  const active = players.filter(p => p.active);
  const n = ui.sel.size;
  const opts = n >= 3 ? await api('/group-options?n=' + n) : [];
  if (opts.length && (!f.groups || f.groups > opts.length)) f.groups = opts.find(o => o.recommended).groups;
  const quickAdd = h('input', { placeholder: 'Neuer Spieler …', onkeydown: e => e.key === 'Enter' && add() });
  const add = () => act(async () => { if (!quickAdd.value.trim()) return; const p = await api('/players', 'POST', { name: quickAdd.value }); ui.sel.add(p.id); });
  const set = (k, v) => { f[k] = v; };
  const minSize = opts.length && f.groups ? Math.min(...opts[f.groups - 1].sizes) : 5;
  const dateInput = h('input', { type: 'date', value: f.date || new Date().toLocaleDateString('sv') , onchange: e => f.date = e.target.value });
  return h('div', {},
    h('h2', {}, 'Neues Turnier'),
    h('div', { class: 'card' },
      h('div', { class: 'row' }, h('h3', { style: 'margin:0' }, `Wer ist heute da? (${n})`), h('div', { class: 'sp' }),
        h('button', { onclick: () => { active.forEach(p => ui.sel.add(p.id)); render(); } }, 'Alle'),
        h('button', { onclick: () => { ui.sel.clear(); render(); } }, 'Keine')),
      h('div', { class: 'chips', style: 'margin:14px 0' }, active.map(p => h('div', { class: 'chip' + (ui.sel.has(p.id) ? ' on' : ''),
        onclick: () => { ui.sel.has(p.id) ? ui.sel.delete(p.id) : ui.sel.add(p.id); render(); } }, (ui.sel.has(p.id) ? '✓ ' : '') + p.name))),
      h('div', { class: 'row' }, quickAdd, h('button', { onclick: add }, '+ Spieler anlegen'))),
    n < 3 ? h('div', { class: 'card muted' }, 'Mindestens 3 Spieler auswählen.') : h('div', { class: 'card' },
      h('h3', {}, 'Gruppen'),
      h('div', { class: 'chips', style: 'margin-bottom:6px' }, opts.map(o => h('div', { class: 'opt' + (f.groups === o.groups ? ' on' : ''), onclick: () => {
        f.groups = o.groups; const ms = Math.min(...o.sizes); if (ms <= 3) f.group_best_of = 5; else if (f.group_best_of === 5) f.group_best_of = 3; render(); } },
        h('b', {}, `${o.groups} ${o.groups === 1 ? 'Gruppe' : 'Gruppen'}`), o.recommended ? h('span', { class: 'badge' }, 'Empfohlen') : null,
        h('div', {}, o.sizes.join(' / '), ' Spieler'), h('div', { class: 'muted small' }, `${o.matches} Spiele insgesamt`)))),
      minSize <= 3 ? h('div', { class: 'muted small' }, 'Tipp: Bei nur 3 Spielern pro Gruppe bietet sich Best-of-5 oder Double Out an.') : null,
      h('h3', { style: 'margin-top:18px' }, 'Gruppenphase'),
      h('div', { class: 'row' },
        sel('Best of', [1, 3, 5, 7], f.group_best_of, v => f.group_best_of = +v, v => 'Best of ' + v),
        sel('Finish', Object.keys(OUT), f.group_out, v => f.group_out = v, v => OUT[v]),
        h('label', { class: 'f' }, 'Startpunkte', h('input', { type: 'number', value: f.start_score, style: 'width:100px', onchange: e => f.start_score = +e.target.value })),
        h('label', { class: 'f' }, 'Datum', dateInput),
        h('label', { class: 'f sp' }, 'Name (optional)', h('input', { value: f.name, placeholder: 'Ranking-Turnier …', onchange: e => f.name = e.target.value }))),
      h('div', { class: 'muted small', style: 'margin-top:8px' }, 'KO-Phase (Runden, Best-of, Finish) wird nach der Gruppenphase festgelegt.'),
      h('div', { style: 'margin-top:18px' }, h('button', { class: 'primary big', onclick: () => act(async () => {
        const r = await api('/tournaments', 'POST', { player_ids: [...ui.sel], groups: f.groups, date: dateInput.value, name: f.name,
          settings: { group_best_of: f.group_best_of, group_out: f.group_out, start_score: f.start_score } });
        ui.swap = null; location.hash = '#/'; }) }, '🎲 Spieler auslosen'))));
}

function sel(label, values, cur, onchange, fmt = v => v) {
  return h('label', { class: 'f' }, label, h('select', { onchange: e => onchange(e.target.value) },
    values.map(v => h('option', { value: v, selected: String(v) === String(cur) }, fmt(v)))));
}

function tournamentView(t) {
  const head = h('div', { class: 'row', style: 'margin-bottom:14px' }, h('h2', { style: 'margin:0' }, t.name),
    h('span', { class: 'muted' }, fmtDate(t.date)),
    h('span', { class: 'badge ' + (t.status === 'finished' ? 'g' : '') }, { draft: 'Auslosung', group: 'Gruppenphase', ko: 'KO-Phase', finished: 'Beendet' }[t.status]),
    h('div', { class: 'sp' }),
    t.status !== 'finished' || true ? h('button', { class: 'danger', onclick: () => { if (confirm(`Turnier „${t.name}“ wirklich ${t.status === 'finished' ? 'löschen' : 'abbrechen und löschen'}? (Es wird vorher ein Backup angelegt.)`))
      act(async () => { await api('/tournaments/' + t.id, 'DELETE'); location.hash = '#/'; }); } }, t.status === 'finished' ? 'Löschen' : 'Abbrechen') : null);
  const body = { draft: draftView, group: playView, ko: playView, finished: playView }[t.status](t);
  return h('div', {}, head, body);
}

function draftView(t) {
  const s = t.settings;
  const clickPlayer = id => {
    if (ui.swap == null) ui.swap = id;
    else if (ui.swap === id) ui.swap = null;
    else { const a = ui.swap; ui.swap = null; return act(() => api(`/tournaments/${t.id}/swap`, 'POST', { a, b: id })); }
    render();
  };
  const save = patch => act(() => api(`/tournaments/${t.id}/settings`, 'PUT', patch));
  return h('div', {},
    h('div', { class: 'grid cols3' }, t.groups.map(g => h('div', { class: 'card' }, h('h3', {}, g.name, ` (${g.players.length})`),
      h('div', { class: 'chips' }, g.players.map(p => h('div', { class: 'chip' + (ui.swap === p.id ? ' sel' : ''), onclick: () => clickPlayer(p.id) }, p.name)))))),
    h('div', { class: 'muted small' }, 'Tipp: Zwei Spieler nacheinander anklicken, um sie zu tauschen.'),
    h('div', { class: 'card', style: 'margin-top:14px' }, h('div', { class: 'row' },
      sel('Best of', [1, 3, 5, 7], s.group_best_of, v => save({ group_best_of: +v }), v => 'Best of ' + v),
      sel('Finish', Object.keys(OUT), s.group_out, v => save({ group_out: v }), v => OUT[v]),
      h('label', { class: 'f' }, 'Startpunkte', h('input', { type: 'number', value: s.start_score, style: 'width:100px', onchange: e => save({ start_score: +e.target.value }) })),
      h('div', { class: 'sp' }),
      h('button', { onclick: () => act(() => api(`/tournaments/${t.id}/redraw`, 'POST')) }, '🎲 Neu auslosen'),
      h('button', { class: 'primary big', onclick: () => act(() => api(`/tournaments/${t.id}/start`, 'POST')) }, '▶ Turnier starten'))));
}

function resultEntry(m, t) {
  const need = Math.floor(m.best_of / 2) + 1;
  const ks = [...Array(need).keys()];
  const send = (l1, l2) => act(() => api(`/matches/${m.id}/result`, 'POST', { legs1: l1, legs2: l2 }));
  return h('div', { class: 'entry' },
    h('div', { class: 'col' }, h('span', {}, m.p1_name + ' gewinnt'), h('div', { class: 'btns' }, ks.map(k => h('button', { class: 'primary', onclick: () => send(need, k) }, `${need}:${k}`)))),
    h('div', { class: 'col' }, h('span', {}, m.p2_name + ' gewinnt'), h('div', { class: 'btns' }, ks.slice().reverse().map(k => h('button', { class: 'primary', onclick: () => send(k, need) }, `${k}:${need}`)))));
}

function matchCard(m, t, isCurrent) {
  const where = m.phase === 'ko' ? m.round_name : (t.groups.length > 1 ? t.groups[m.group].name : 'Gruppenphase');
  const out = OUT[m.phase === 'ko' ? t.settings.ko_out : t.settings.group_out];
  const done = m.status === 'done';
  const locked = done && m.phase === 'group' && t.status !== 'group';
  return h('div', { class: 'match' + (isCurrent ? ' cur' : '') + (done ? ' done' : '') },
    h('div', { class: 'meta' }, isCurrent ? h('span', { class: 'badge' }, 'Jetzt') : null, h('span', {}, where),
      done ? `BO${m.best_of}` : h('select', { style: 'padding:1px 4px;font-size:.78rem', title: 'Best-of für dieses Spiel ändern',
        onchange: e => act(() => api('/matches/' + m.id, 'PUT', { best_of: +e.target.value })) },
        [1, 3, 5, 7].map(v => h('option', { value: v, selected: v === m.best_of }, 'BO' + v))), h('span', {}, out)),
    h('div', { class: 'vs' }, h('span', { class: 'n' + (m.winner === m.p1 ? ' win' : '') }, m.p1_name),
      h('span', { class: 's' }, done ? `${m.legs1} : ${m.legs2}` : 'vs'),
      h('span', { class: 'n' + (m.winner === m.p2 ? ' win' : '') }, m.p2_name)),
    done ? (locked ? null : h('div', { class: 'right' }, h('button', { class: 'small', onclick: () => act(() => api(`/matches/${m.id}/reset`, 'POST')) }, '✎ Ergebnis ändern')))
      : resultEntry(m, t));
}

function playView(t) {
  const nodes = [];
  if (t.status === 'finished') nodes.push(h('div', { class: 'champ', style: 'margin-bottom:18px' }, h('div', { class: 'cup' }, '🏆'),
    h('div', { class: 'muted' }, 'Turniersieger'), h('div', { class: 'name' }, t.champion_name)));
  const pct = t.progress.total ? Math.round(100 * t.progress.done / t.progress.total) : 0;
  nodes.push(h('div', { class: 'row', style: 'margin-bottom:14px' }, h('div', { class: 'bar sp' }, h('i', { style: `width:${pct}%` })),
    h('span', { class: 'muted small' }, `${t.progress.done}/${t.progress.total} Spiele`)));

  if (t.status === 'group' && t.group_done) nodes.push(koStartCard(t));
  if (t.ko) nodes.push(h('div', { class: 'card' }, h('h3', {}, 'KO-Phase'), bracketView(t.ko, t.current && t.current.id)));

  const pending = t.matches.filter(m => m.status === 'pending' && m.p1 && m.p2).sort((a, b) => a.seq - b.seq);
  const done = t.matches.filter(m => m.status === 'done').sort((a, b) => (b.finished_at || '').localeCompare(a.finished_at || ''));
  const left = h('div', {}, h('h3', {}, 'Spielplan'),
    pending.length ? pending.slice(0, 8).map((m, i) => matchCard(m, t, i === 0)) : h('div', { class: 'muted' }, t.status === 'finished' ? '' : 'Keine offenen Spiele.'),
    pending.length > 8 ? h('div', { class: 'muted small' }, `… und ${pending.length - 8} weitere Spiele`) : null,
    done.length ? h('div', {}, h('h3', { style: 'margin-top:20px;cursor:pointer', onclick: () => { ui.showDone = !ui.showDone; render(); } }, `${ui.showDone ? '▾' : '▸'} Gespielt (${done.length})`),
      ui.showDone ? done.map(m => matchCard(m, t, false)) : null) : null);
  const q = t.ko ? Math.floor(t.ko.size / t.groups.length) : 0;
  const right = h('div', {}, h('h3', {}, 'Tabellen'), t.groups.map(g => h('div', { class: 'card' },
    h('div', { class: 'row' }, h('b', {}, g.name), h('div', { class: 'sp' }), h('span', { class: 'muted small' }, `${g.matches_done}/${g.matches_total}`)),
    standingsTable(g.standings, q))),
    t.groups.some(g => g.standings.some(r => r.tie)) ? h('div', { class: 'muted small' }, '= Gleichstand auch nach direktem Vergleich – bei Bedarf Stechen spielen.') : null);
  nodes.push(h('div', { class: 'grid', style: 'grid-template-columns:minmax(380px,1fr) minmax(380px,1fr);align-items:start' }, left, right));
  return h('div', {}, nodes);
}

function koStartCard(t) {
  const k = ui.ko;
  if (!k.size || !t.ko_sizes.includes(k.size)) { k.size = t.ko_default; k.best_of = null; }
  const rounds = Math.log2(k.size);
  if (!k.best_of || k.best_of.length !== rounds) k.best_of = [...Array(rounds)].map((_, r) => r === rounds - 1 ? 5 : 3);
  const card = h('div', { class: 'card', style: 'border-color:var(--gold)' }, h('h2', {}, '🏁 Gruppenphase beendet – KO-Phase festlegen'));
  const names = ['Finale', 'Halbfinale', 'Viertelfinale', 'Achtelfinale'];
  card.append(h('div', { class: 'row', style: 'margin-bottom:6px' },
    sel('Teilnehmer KO', t.ko_sizes, k.size, v => { k.size = +v; k.best_of = null; render(); }, v => `${v} Spieler`),
    k.best_of.map((b, r) => sel(`${names[rounds - 1 - r] || 'Runde ' + (r + 1)}`, [1, 3, 5, 7], b, v => k.best_of[r] = +v, v => 'BO' + v)),
    sel('Finish', Object.keys(OUT), k.ko_out, v => k.ko_out = v, v => OUT[v]),
    h('div', { class: 'sp' }),
    h('button', { class: 'gold big', onclick: () => act(() => api(`/tournaments/${t.id}/ko-start`, 'POST', { size: k.size, best_of: k.best_of, ko_out: k.ko_out })) }, '▶ KO-Phase starten')));
  api(`/tournaments/${t.id}/ko-preview?size=${k.size}`).then(p => {
    card.append(h('div', { class: 'muted small', style: 'margin:10px 0 4px' }, 'Paarungen Runde 1 (Setzung nach Platzierung, Gruppengleiche möglichst getrennt):'),
      h('div', { class: 'chips' }, p.pairs.map(([a, b]) => {
        const q = id => p.qualifiers.find(x => x.id === id);
        const lab = x => `${x.name} (${t.groups[x.group].name.slice(-1)}${x.place}${x.wildcard ? ' WC' : ''})`;
        return h('div', { class: 'chip' }, lab(q(a)), h('span', { class: 'muted' }, 'vs'), lab(q(b)));
      })));
  }).catch(e => card.append(h('div', {}, e.message)));
  return card;
}

// ------------------------------------------------------------------ Spieler
async function playersView() {
  const input = h('input', { placeholder: 'Name …', onkeydown: e => e.key === 'Enter' && add() });
  const add = () => act(async () => { if (input.value.trim()) await api('/players', 'POST', { name: input.value }); });
  return h('div', {}, h('h2', {}, 'Spieler'),
    h('div', { class: 'card' }, h('div', { class: 'row' }, input, h('button', { class: 'primary', onclick: add }, '+ Anlegen'))),
    h('div', { class: 'card' }, h('table', {}, h('tbody', {}, players.map(p => h('tr', { style: p.active ? '' : 'opacity:.5' },
      h('td', { class: 'l', style: 'text-align:left!important;width:auto' }, h('a', { href: '#/spieler/' + p.id }, p.name), p.active ? '' : h('span', { class: 'muted' }, ' (inaktiv)')),
      h('td', { class: 'right' },
        h('button', { onclick: () => { const n = prompt('Neuer Name:', p.name); if (n) act(() => api('/players/' + p.id, 'PUT', { name: n })); } }, 'Umbenennen'), ' ',
        h('button', { onclick: () => act(() => api('/players/' + p.id, 'PUT', { active: p.active ? 0 : 1 })) }, p.active ? 'Deaktivieren' : 'Aktivieren'), ' ',
        h('button', { class: 'danger', onclick: () => confirm(`„${p.name}“ löschen?`) && act(() => api('/players/' + p.id, 'DELETE')) }, '✕'))))))),
    h('div', { class: 'muted small' }, 'Deaktivierte Spieler erscheinen nicht mehr in der Turnier-Auswahl, bleiben aber in der Statistik.'),
    h('div', { style: 'margin-top:18px' }, h('a', { class: 'btn', href: '/api/backup', style: 'display:inline-block' }, '💾 Datenbank-Backup herunterladen')));
}

async function playerDetailView(id) {
  const d = await api(`/players/${id}/stats`);
  const t = d.total;
  const kpi = (l, v) => h('div', { class: 'card', style: 'margin:0;text-align:center' }, h('div', { class: 'muted small' }, l), h('div', { style: 'font-size:1.8rem;font-weight:800' }, v));
  return h('div', {}, h('div', { class: 'row' }, h('a', { href: '#/spieler' }, '← Spieler'), h('h2', { style: 'margin:0' }, d.name)),
    t ? h('div', { class: 'grid', style: 'grid-template-columns:repeat(auto-fit,minmax(130px,1fr));margin:14px 0' },
      kpi('Turniere', t.tournaments), kpi('Titel 🏆', t.titles), kpi('Finals', t.finals), kpi('Siege / Spiele', `${t.wins}/${t.matches}`),
      kpi('Legs', `${t.legs_for}:${t.legs_against}`), kpi('Leg-Quote', t.leg_rate + '%')) : h('div', { class: 'card muted' }, 'Noch keine Turniere gespielt.'),
    h('div', { class: 'grid cols2' },
      h('div', { class: 'card' }, h('h3', {}, 'Turnier-Historie'), h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, ''), h('th', {}, 'Turnier'), h('th', {}, 'Gruppe'), h('th', {}, 'KO'))),
        h('tbody', {}, d.history.map(x => h('tr', {}, h('td', {}), h('td', {}, h('a', { href: '#/turnier/' + x.id }, fmtDate(x.date))),
          h('td', {}, `${x.group_rank}./${x.group_size} (${x.legs_for}:${x.legs_against})`), h('td', {}, x.ko || '–')))))),
      h('div', { class: 'card' }, h('h3', {}, 'Bilanz gegen Gegner'), h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, ''), h('th', {}, 'Gegner'), h('th', {}, 'Spiele'), h('th', {}, 'S–N'), h('th', {}, 'Legs'))),
        h('tbody', {}, d.opponents.map(o => h('tr', {}, h('td', {}), h('td', {}, h('a', { href: '#/duelle' , onclick: () => { ui.h2h = { a: String(id), b: String(o.id) }; } }, o.name)),
          h('td', {}, o.matches), h('td', {}, `${o.wins}–${o.matches - o.wins}`), h('td', {}, `${o.legs_for}:${o.legs_against}`))))))));
}

// ------------------------------------------------------------------ Ranking / Duelle / Archiv
async function rankingView() {
  const rows = await api('/ranking');
  const r = ui.rank;
  rows.sort((a, b) => ((a[r.key] > b[r.key]) - (a[r.key] < b[r.key])) * r.dir || a.name.localeCompare(b.name));
  const cols = [['name', 'Spieler'], ['tournaments', 'Turniere'], ['titles', 'Titel'], ['finals', 'Finals'], ['matches', 'Spiele'], ['wins', 'Siege'], ['win_rate', 'Sieg %'],
    ['legs_for', 'Legs +'], ['legs_against', 'Legs −'], ['diff', 'Diff'], ['leg_rate', 'Leg %']];
  return h('div', {}, h('h2', {}, 'Gesamt-Ranking'),
    h('div', { class: 'muted small', style: 'margin-bottom:8px' }, 'Auf eine Spalte klicken zum Sortieren. Standard: Titel, dann Leg-Differenz.'),
    h('div', { class: 'card' }, rows.length ? h('table', { class: 'sortable' }, h('thead', {}, h('tr', {}, h('th', {}, '#'),
      cols.map(([k, l]) => h('th', { class: k === 'name' ? 'l' : '', onclick: () => { r.dir = r.key === k ? -r.dir : (k === 'name' ? 1 : -1); r.key = k; render(); } }, l + (r.key === k ? (r.dir < 0 ? ' ▼' : ' ▲') : '')))))
      , h('tbody', {}, rows.map((p, i) => h('tr', {}, h('td', {}, i + 1),
        h('td', {}, h('a', { href: '#/spieler/' + p.id }, p.name)), cols.slice(1).map(([k]) => h('td', {}, k === 'diff' ? (p.diff > 0 ? '+' : '') + p.diff : (k === 'win_rate' || k === 'leg_rate' ? p[k] + '%' : p[k]))))))) :
      h('div', { class: 'muted' }, 'Noch keine Daten – spielt euer erstes Turnier!')));
}

async function h2hView() {
  const f = ui.h2h;
  const opts = [h('option', { value: '' }, '– wählen –'), ...players.map(p => h('option', { value: p.id }, p.name))];
  const mk = k => h('select', { onchange: e => { f[k] = e.target.value; render(); } }, opts.map(o => { const c = o.cloneNode(true); if (c.value === f[k]) c.selected = true; return c; }));
  let res = null, err = null;
  if (f.a && f.b && f.a !== f.b) { try { res = await api(`/h2h?a=${f.a}&b=${f.b}`); } catch (e) { err = e.message; } }
  const total = res ? res.a.legs + res.b.legs : 0;
  const view = res ? (res.matches.length ? h('div', {},
    h('div', { class: 'grid', style: 'grid-template-columns:1fr 1fr;text-align:center;margin:10px 0' },
      h('div', {}, h('div', { class: 'muted' }, res.a.name), h('div', { style: 'font-size:2.6rem;font-weight:900;color:var(--green)' }, res.a.wins), h('div', { class: 'muted small' }, 'Siege')),
      h('div', {}, h('div', { class: 'muted' }, res.b.name), h('div', { style: 'font-size:2.6rem;font-weight:900;color:var(--red)' }, res.b.wins), h('div', { class: 'muted small' }, 'Siege'))),
    h('div', { class: 'bars' }, h('div', { style: `background:var(--green);width:${100 * res.a.legs / total}%` }, res.a.legs), h('div', { style: `background:var(--red);width:${100 * res.b.legs / total}%` }, res.b.legs)),
    h('div', { class: 'center muted small', style: 'margin:4px 0 14px' }, 'gewonnene Legs'),
    h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, ''), h('th', {}, 'Datum'), h('th', {}, 'Phase'), h('th', {}, 'Ergebnis'))),
      h('tbody', {}, res.matches.slice().reverse().map(m => h('tr', {}, h('td', {}), h('td', {}, h('a', { href: '#/turnier/' + m.tournament_id }, fmtDate(m.date))), h('td', {}, m.phase),
        h('td', { class: m.legs_a > m.legs_b ? 'win' : '' }, `${m.legs_a} : ${m.legs_b}`)))))) : h('div', { class: 'muted' }, 'Diese beiden haben noch nicht gegeneinander gespielt.')) : null;
  return h('div', {}, h('h2', {}, 'Duelle'), h('div', { class: 'card' }, h('div', { class: 'row' }, mk('a'), h('b', {}, 'vs'), mk('b')),
    err ? h('div', {}, err) : null, view));
}

async function archiveView() {
  const list = await api('/tournaments');
  return h('div', {}, h('h2', {}, 'Archiv'), h('div', { class: 'card' }, list.length ? h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, ''), h('th', {}, 'Turnier'), h('th', {}, 'Datum'), h('th', {}, 'Spieler'), h('th', {}, 'Sieger'), h('th', {}, 'Status'))),
    h('tbody', {}, list.map(t => h('tr', {}, h('td', {}), h('td', {}, h('a', { href: '#/turnier/' + t.id }, t.name)), h('td', {}, fmtDate(t.date)), h('td', {}, `${t.players} (${t.groups} Gr.)`),
      h('td', {}, t.champion_name ? '🏆 ' + t.champion_name : '–'), h('td', {}, { draft: 'Auslosung', group: 'läuft', ko: 'KO läuft', finished: 'beendet' }[t.status]))))) : h('div', { class: 'muted' }, 'Noch keine Turniere.')));
}

render();

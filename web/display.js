// Monitor-Ansicht: aktualisiert sich alle 3 Sekunden selbst
const main = document.getElementById('main');
let last = '';

function qualifyCount(t) {
  const s = t.settings;
  if (t.ko) return Math.floor(t.ko.size / t.groups.length);
  return 0;
}

function matchLine(m) {
  return h('div', { class: 'match' },
    h('div', { class: 'meta' }, metaSpans(m.phase === 'ko' ? m.round_name : (t0.groups.length > 1 ? t0.groups[m.group].name : 'Gruppenphase'),
      `BO${m.best_of}`, OUT[m.phase === 'ko' ? t0.settings.ko_out : t0.settings.group_out])),
    h('div', { class: 'vs' }, h('span', { class: 'n' }, m.p1_name), h('span', { class: 'muted' }, 'vs'), h('span', { class: 'n' }, m.p2_name)));
}
let t0 = null;

function rankingCard(rank) {
  return h('div', { class: 'card' }, h('h2', {}, 'Gesamt-Ranking'),
    h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, '#'), h('th', {}, 'Spieler'), h('th', {}, 'Turn.'), h('th', {}, 'Siege'), h('th', {}, 'Legs'), h('th', {}, 'Diff'))),
      h('tbody', {}, rank.map((r, i) => h('tr', {}, h('td', {}, i + 1), h('td', {}, r.name, r.titles ? ` 🏆×${r.titles}` : ''),
        h('td', {}, r.tournaments), h('td', {}, r.titles), h('td', {}, `${r.legs_for}:${r.legs_against}`), h('td', {}, (r.diff > 0 ? '+' : '') + r.diff))))));
}

function render(data) {
  const t = data.tournament; t0 = t;
  const clock = h('div', { class: 'clock', id: 'clock' });
  const head = h('div', { class: 'dhead' }, dartLogo(54),
    h('div', {}, h('h1', {}, 'Dart Club Pischelsdorf e.V.'), t ? h('div', { class: 'muted' }, `${t.name} · ${fmtDate(t.date)}`) : null),
    h('div', { class: 'sp' }), clock);
  let body;
  if (!t || t.status === 'draft') {
    body = h('div', { class: 'dbody', style: 'grid-template-columns:1fr' }, rankingCard(data.ranking));
    if (t) body = h('div', {}, h('div', { class: 'card center' }, h('h2', {}, 'Turnier wird vorbereitet …'),
      h('div', { class: 'chips', style: 'justify-content:center' }, t.groups.map(g => h('div', { class: 'card' }, h('h3', {}, g.name), g.players.map(p => h('div', {}, p.name)))))));
  } else {
    const showKO = !!t.ko;
    const left = showKO
      ? h('div', {}, h('div', { class: 'card' }, bracketView(t.ko, t.current && t.current.id)),
        h('div', { style: 'height:1vw' }),
        h('div', { class: 'dleft compact g' + Math.min(t.groups.length, 3) }, t.groups.map(g => h('div', { class: 'card' }, h('h3', {}, g.name), standingsTable(g.standings, qualifyCount(t))))))
      : h('div', { class: 'dleft g' + Math.min(t.groups.length, 3) }, t.groups.map(g => h('div', { class: 'card' },
        h('h3', {}, g.name, h('span', { class: 'muted', style: 'float:right;text-transform:none' }, `${g.matches_done}/${g.matches_total}`)),
        standingsTable(g.standings, 0))));
    const right = h('div', { class: 'dleft' });
    if (t.status === 'finished') {
      right.append(h('div', { class: 'champ' }, h('div', { class: 'cup' }, '🏆'), h('div', { class: 'muted' }, 'Turniersieger'), h('div', { class: 'name' }, t.champion_name)));
    } else if (t.current) {
      right.append(h('div', { class: 'now' }, h('div', { class: 'lbl' }, 'Jetzt am Board'),
        h('div', { class: 'meta' }, metaSpans(t.current.phase === 'ko' ? t.current.round_name : (t.groups.length > 1 ? t.groups[t.current.group].name : 'Gruppenphase'),
          `BO${t.current.best_of}`, OUT[t.current.phase === 'ko' ? t.settings.ko_out : t.settings.group_out], `${t.settings.start_score} Punkte`)),
        h('div', { class: 'vs' }, h('span', { class: 'n' }, t.current.p1_name), h('span', { class: 'muted' }, 'vs'), h('span', { class: 'n' }, t.current.p2_name))));
    } else if (t.group_done && !t.ko) {
      right.append(h('div', { class: 'now' }, h('div', { class: 'lbl' }, 'Gruppenphase beendet'), h('div', {}, 'KO-Phase wird gestartet …')));
    }
    if (t.next.length) right.append(h('div', { class: 'card' }, h('h3', {}, 'Als Nächstes'), t.next.map(matchLine)));
    if (t.recent.length) right.append(h('div', { class: 'card' }, h('h3', {}, 'Letzte Ergebnisse'),
      t.recent.slice(0, 4).map(m => h('div', { class: 'vs', style: 'font-size:.95em;padding:.2em 0' },
        h('span', { class: 'n' + (m.winner === m.p1 ? ' win' : '') }, m.p1_name), h('span', { class: 's' }, `${m.legs1}:${m.legs2}`),
        h('span', { class: 'n' + (m.winner === m.p2 ? ' win' : '') }, m.p2_name)))));
    body = h('div', { class: 'dbody' + (showKO ? ' ko' : '') }, left, right);
  }
  main.replaceChildren(head, body);
  tick();
}

function tick() {
  const c = document.getElementById('clock');
  if (c) c.textContent = new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' }) + ' Uhr';
}
setInterval(tick, 10000);

async function poll() {
  try {
    const data = await api('/display');
    const sig = JSON.stringify(data);
    if (sig !== last) { last = sig; render(data); }
  } catch (e) {
    main.replaceChildren(h('div', { class: 'card center' }, 'Keine Verbindung zum Server …'));
    last = '';
  }
}
poll();
setInterval(poll, 3000);

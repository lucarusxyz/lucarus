"""Datenbank und Turnier-Operationen."""
import json
import os
import sqlite3
from datetime import datetime

import logic

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DART_DB", os.path.join(BASE, "data", "dart.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS players(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tournaments(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, date TEXT NOT NULL,
  status TEXT NOT NULL, settings TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS participants(
  tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES players(id),
  group_idx INTEGER NOT NULL, PRIMARY KEY(tournament_id, player_id));
CREATE TABLE IF NOT EXISTS matches(
  id INTEGER PRIMARY KEY,
  tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
  phase TEXT NOT NULL, group_idx INTEGER, round INTEGER NOT NULL DEFAULT 0, pos INTEGER NOT NULL DEFAULT 0,
  p1 INTEGER REFERENCES players(id), p2 INTEGER REFERENCES players(id),
  best_of INTEGER NOT NULL, legs1 INTEGER, legs2 INTEGER,
  status TEXT NOT NULL DEFAULT 'pending', seq INTEGER NOT NULL, finished_at TEXT);
"""

ACTIVE = ("draft", "group", "ko")
DEFAULTS = {"group_best_of": 3, "group_out": "single", "ko_out": "double",
            "start_score": 501, "ko_best_of": None, "ko_size": None}


class ApiError(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con


def now():
    return datetime.now().isoformat(timespec="seconds")


def backup(con, tag="auto"):
    d = os.path.join(os.path.dirname(DB_PATH), "backups")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"dart-{datetime.now():%Y%m%d-%H%M%S}-{tag}.db")
    dst = sqlite3.connect(path)
    con.backup(dst)
    dst.close()
    return path


# ---------------------------------------------------------------- Spieler
def list_players(con):
    return [dict(r) for r in con.execute("SELECT id,name,active FROM players ORDER BY name COLLATE NOCASE")]


def add_player(con, name):
    name = (name or "").strip()
    if not name:
        raise ApiError("Name fehlt")
    try:
        with con:
            cur = con.execute("INSERT INTO players(name,created_at) VALUES(?,?)", (name, now()))
    except sqlite3.IntegrityError:
        raise ApiError(f"Spieler „{name}“ existiert bereits")
    return {"id": cur.lastrowid, "name": name, "active": 1}


def update_player(con, pid, data):
    p = con.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not p:
        raise ApiError("Spieler nicht gefunden", 404)
    name = (data.get("name", p["name"]) or "").strip()
    if not name:
        raise ApiError("Name fehlt")
    try:
        with con:
            con.execute("UPDATE players SET name=?, active=? WHERE id=?",
                        (name, int(data.get("active", p["active"])), pid))
    except sqlite3.IntegrityError:
        raise ApiError(f"Spieler „{name}“ existiert bereits")
    return {"ok": True}


def delete_player(con, pid):
    used = con.execute("SELECT 1 FROM participants WHERE player_id=?", (pid,)).fetchone()
    if used:
        raise ApiError("Spieler hat Turnier-Teilnahmen und kann nicht gelöscht werden – bitte deaktivieren.")
    with con:
        con.execute("DELETE FROM players WHERE id=?", (pid,))
    return {"ok": True}


# ---------------------------------------------------------------- Turnier anlegen
def _tournament(con, tid):
    t = con.execute("SELECT * FROM tournaments WHERE id=?", (tid,)).fetchone()
    if not t:
        raise ApiError("Turnier nicht gefunden", 404)
    return t


def _settings(t):
    return {**DEFAULTS, **json.loads(t["settings"])}


def _clean_settings(data, base):
    s = dict(base)
    for k in ("group_best_of", "start_score"):
        if k in data and data[k] is not None:
            s[k] = int(data[k])
    for k in ("group_out", "ko_out"):
        if data.get(k) in ("single", "double", "master"):
            s[k] = data[k]
    if s["group_best_of"] < 1 or s["group_best_of"] % 2 == 0:
        raise ApiError("Best-of muss ungerade sein (1, 3, 5, …)")
    return s


def create_tournament(con, data):
    if con.execute("SELECT 1 FROM tournaments WHERE status IN ('draft','group','ko')").fetchone():
        raise ApiError("Es läuft bereits ein Turnier. Bitte zuerst beenden oder abbrechen.")
    ids = list(dict.fromkeys(int(i) for i in data.get("player_ids", [])))
    if len(ids) < 3:
        raise ApiError("Mindestens 3 Spieler nötig")
    known = {r["id"] for r in con.execute("SELECT id FROM players")}
    if not set(ids) <= known:
        raise ApiError("Unbekannter Spieler")
    opts = logic.group_options(len(ids))
    g = int(data.get("groups") or 1)
    if not 1 <= g <= len(opts):
        raise ApiError("Ungültige Gruppenanzahl")
    settings = _clean_settings(data.get("settings", {}), DEFAULTS)
    settings["num_groups"] = g
    date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    name = (data.get("name") or "").strip() or "Ranking-Turnier"
    with con:
        cur = con.execute("INSERT INTO tournaments(name,date,status,settings,created_at) VALUES(?,?,?,?,?)",
                          (name, date, "draft", json.dumps(settings), now()))
        tid = cur.lastrowid
        _draw(con, tid, ids, opts[g - 1]["sizes"])
    return {"id": tid}


def _draw(con, tid, ids, sizes):
    con.execute("DELETE FROM participants WHERE tournament_id=?", (tid,))
    for gi, grp in enumerate(logic.draw_groups(ids, sizes)):
        for pid in grp:
            con.execute("INSERT INTO participants VALUES(?,?,?)", (tid, pid, gi))


def _require_status(t, *allowed):
    if t["status"] not in allowed:
        raise ApiError("Aktion in diesem Turnierstatus nicht möglich")


def redraw(con, tid):
    t = _tournament(con, tid)
    _require_status(t, "draft")
    rows = con.execute("SELECT player_id, group_idx FROM participants WHERE tournament_id=?", (tid,)).fetchall()
    sizes = [0] * (max(r["group_idx"] for r in rows) + 1)
    for r in rows:
        sizes[r["group_idx"]] += 1
    with con:
        _draw(con, tid, [r["player_id"] for r in rows], sizes)
    return {"ok": True}


def swap(con, tid, a, b):
    t = _tournament(con, tid)
    _require_status(t, "draft")
    ra = con.execute("SELECT group_idx FROM participants WHERE tournament_id=? AND player_id=?", (tid, a)).fetchone()
    rb = con.execute("SELECT group_idx FROM participants WHERE tournament_id=? AND player_id=?", (tid, b)).fetchone()
    if not ra or not rb:
        raise ApiError("Spieler nicht im Turnier")
    with con:
        con.execute("UPDATE participants SET group_idx=? WHERE tournament_id=? AND player_id=?", (rb[0], tid, a))
        con.execute("UPDATE participants SET group_idx=? WHERE tournament_id=? AND player_id=?", (ra[0], tid, b))
    return {"ok": True}


def update_settings(con, tid, data):
    t = _tournament(con, tid)
    _require_status(t, "draft")
    s = _clean_settings(data, _settings(t))
    name = (data.get("name") or t["name"]).strip()
    with con:
        con.execute("UPDATE tournaments SET settings=?, name=? WHERE id=?", (json.dumps(s), name, tid))
    return {"ok": True}


def start(con, tid):
    t = _tournament(con, tid)
    _require_status(t, "draft")
    s = _settings(t)
    groups = {}
    for r in con.execute("SELECT player_id, group_idx FROM participants WHERE tournament_id=? ORDER BY player_id", (tid,)):
        groups.setdefault(r["group_idx"], []).append(r["player_id"])
    glist = [groups[i] for i in sorted(groups)]
    with con:
        for seq, (gi, a, b) in enumerate(logic.schedule(glist), 1):
            con.execute("INSERT INTO matches(tournament_id,phase,group_idx,p1,p2,best_of,seq) VALUES(?,?,?,?,?,?,?)",
                        (tid, "group", gi, a, b, s["group_best_of"], seq))
        con.execute("UPDATE tournaments SET status='group' WHERE id=?", (tid,))
    return {"ok": True}


def delete_tournament(con, tid):
    _tournament(con, tid)
    backup(con, "vor-loeschen")
    with con:
        con.execute("DELETE FROM matches WHERE tournament_id=?", (tid,))
        con.execute("DELETE FROM participants WHERE tournament_id=?", (tid,))
        con.execute("DELETE FROM tournaments WHERE id=?", (tid,))
    return {"ok": True}


# ---------------------------------------------------------------- Zustand
def _match_dict(r, names, total_rounds=None):
    d = dict(r)
    d["group"] = d.pop("group_idx")
    d["p1_name"] = names.get(d["p1"])
    d["p2_name"] = names.get(d["p2"])
    d["winner"] = None
    if d["status"] == "done":
        d["winner"] = d["p1"] if d["legs1"] > d["legs2"] else d["p2"]
    d["round_name"] = logic.round_name(d["round"], total_rounds) if d["phase"] == "ko" and total_rounds else None
    return d


def tournament_state(con, tid):
    t = _tournament(con, tid)
    s = _settings(t)
    names = {r["id"]: r["name"] for r in con.execute("SELECT id,name FROM players")}
    parts = con.execute("SELECT player_id, group_idx FROM participants WHERE tournament_id=?", (tid,)).fetchall()
    ngroups = (max(p["group_idx"] for p in parts) + 1) if parts else 0
    rows = con.execute("SELECT * FROM matches WHERE tournament_id=? ORDER BY seq", (tid,)).fetchall()
    ko_rows = [r for r in rows if r["phase"] == "ko"]
    total_rounds = (max(r["round"] for r in ko_rows) + 1) if ko_rows else 0
    matches = [_match_dict(r, names, total_rounds) for r in rows]

    groups = []
    for gi in range(ngroups):
        plist = sorted(({"id": p["player_id"], "name": names[p["player_id"]]} for p in parts if p["group_idx"] == gi),
                       key=lambda p: p["name"].lower())
        gm = [m for m in matches if m["phase"] == "group" and m["group"] == gi]
        groups.append({"idx": gi, "name": f"Gruppe {chr(65 + gi)}", "players": plist,
                       "standings": logic.standings(plist, gm) if gm else
                       [dict(p, rank=i + 1, played=0, wins=0, losses=0, legs_for=0, legs_against=0, diff=0, tie=False)
                        for i, p in enumerate(plist)],
                       "matches_total": len(gm), "matches_done": sum(1 for m in gm if m["status"] == "done")})

    ko = None
    champion = None
    if ko_rows:
        rounds = []
        for r in range(total_rounds):
            rm = [m for m in matches if m["phase"] == "ko" and m["round"] == r]
            rounds.append({"round": r, "name": logic.round_name(r, total_rounds),
                           "best_of": rm[0]["best_of"] if rm else None, "matches": rm})
        ko = {"size": 2 ** total_rounds, "rounds": rounds}
        final = rounds[-1]["matches"][0]
        champion = final["winner"]

    group_ms = [m for m in matches if m["phase"] == "group"]
    group_done = bool(group_ms) and all(m["status"] == "done" for m in group_ms)
    sizes = [len(g["players"]) for g in groups]

    queue = [m for m in matches if m["status"] == "pending" and m["p1"] and m["p2"]]
    queue.sort(key=lambda m: m["seq"])
    recent = sorted((m for m in matches if m["status"] == "done"), key=lambda m: m["finished_at"] or "", reverse=True)[:6]

    state = {
        "id": t["id"], "name": t["name"], "date": t["date"], "status": t["status"], "settings": s,
        "groups": groups, "ko": ko, "matches": matches,
        "current": queue[0] if queue else None, "next": queue[1:5], "recent": recent,
        "champion": champion, "champion_name": names.get(champion),
        "group_done": group_done, "progress": {
            "done": sum(1 for m in matches if m["status"] == "done"), "total": len(matches)},
        "ko_result": _ko_results(matches, total_rounds, names) if ko else {},
    }
    if t["status"] == "group" and group_done:
        state["ko_sizes"] = logic.ko_options(sizes)
        state["ko_default"] = logic.default_ko_size(sizes)
    return state


def _ko_results(matches, total_rounds, names):
    """Wie weit ist jeder Spieler im KO-Baum gekommen? (Schlüssel: Spieler-ID als Text)"""
    res = {}
    for m in matches:
        if m["phase"] != "ko":
            continue
        for p in (m["p1"], m["p2"]):
            if p:
                res.setdefault(str(p), "Im Rennen")
        if m["status"] == "done":
            loser = m["p2"] if m["winner"] == m["p1"] else m["p1"]
            final = m["round"] == total_rounds - 1
            res[str(loser)] = "Finalist" if final else m["round_name"]
            if final:
                res[str(m["winner"])] = "Sieger"
    return res


def list_tournaments(con):
    out = []
    for t in con.execute("SELECT * FROM tournaments ORDER BY date DESC, id DESC"):
        st = tournament_state(con, t["id"])
        out.append({"id": t["id"], "name": t["name"], "date": t["date"], "status": t["status"],
                    "players": sum(len(g["players"]) for g in st["groups"]),
                    "groups": len(st["groups"]), "champion_name": st["champion_name"],
                    "progress": st["progress"]})
    return out


def active_tournament_id(con):
    r = con.execute("SELECT id FROM tournaments WHERE status IN ('draft','group','ko') ORDER BY id DESC").fetchone()
    return r["id"] if r else None


# ---------------------------------------------------------------- KO-Phase
def _group_tables(con, tid):
    st = tournament_state(con, tid)
    return st, [g["standings"] for g in st["groups"]]


def ko_preview(con, tid, size):
    st, tables = _group_tables(con, tid)
    if st["status"] != "group" or not st["group_done"]:
        raise ApiError("Gruppenphase ist noch nicht abgeschlossen")
    if size not in st["ko_sizes"]:
        raise ApiError("Ungültige KO-Größe")
    quali = logic.seed_qualifiers(logic.select_qualifiers(tables, size), len(tables))
    slots = logic.bracket_slots(quali)
    return {"qualifiers": [{k: q[k] for k in ("id", "name", "group", "place", "wildcard", "seed", "tie")} for q in quali],
            "pairs": [[slots[i]["id"], slots[i + 1]["id"]] for i in range(0, len(slots), 2)]}


def ko_start(con, tid, data):
    t = _tournament(con, tid)
    st, tables = _group_tables(con, tid)
    if st["status"] != "group" or not st["group_done"]:
        raise ApiError("Gruppenphase ist noch nicht abgeschlossen")
    size = int(data.get("size") or 0)
    if size not in st["ko_sizes"]:
        raise ApiError("Ungültige KO-Größe")
    rounds = size.bit_length() - 1
    best_of = data.get("best_of") or [5 if r == rounds - 1 else 3 for r in range(rounds)]
    best_of = [int(b) for b in best_of]
    if len(best_of) != rounds or any(b < 1 or b % 2 == 0 for b in best_of):
        raise ApiError("Best-of je Runde ungültig (ungerade Zahlen)")
    quali = logic.seed_qualifiers(logic.select_qualifiers(tables, size), len(tables))
    slots = logic.bracket_slots(quali)
    s = _settings(t)
    s["ko_size"], s["ko_best_of"] = size, best_of
    if data.get("ko_out") in ("single", "double", "master"):
        s["ko_out"] = data["ko_out"]
    seq = 1000
    with con:
        for r in range(rounds):
            for pos in range(size >> (r + 1)):
                p1 = p2 = None
                if r == 0:
                    p1, p2 = slots[2 * pos]["id"], slots[2 * pos + 1]["id"]
                con.execute("INSERT INTO matches(tournament_id,phase,round,pos,p1,p2,best_of,seq) VALUES(?,?,?,?,?,?,?,?)",
                            (tid, "ko", r, pos, p1, p2, best_of[r], seq))
                seq += 1
        con.execute("UPDATE tournaments SET status='ko', settings=? WHERE id=?", (json.dumps(s), tid))
    return {"ok": True}


# ---------------------------------------------------------------- Ergebnisse
def _next_match(con, m, last_round):
    if m["phase"] != "ko" or m["round"] >= last_round:
        return None
    return con.execute("SELECT * FROM matches WHERE tournament_id=? AND phase='ko' AND round=? AND pos=?",
                       (m["tournament_id"], m["round"] + 1, m["pos"] // 2)).fetchone()


def _last_ko_round(con, tid):
    r = con.execute("SELECT MAX(round) FROM matches WHERE tournament_id=? AND phase='ko'", (tid,)).fetchone()[0]
    return r


def _clear(con, m):
    """Ergebnis zurücknehmen (inkl. Folgespiel im KO-Baum)."""
    t = _tournament(con, m["tournament_id"])
    if m["phase"] == "ko":
        last = _last_ko_round(con, m["tournament_id"])
        nxt = _next_match(con, m, last)
        if m["status"] == "done" and nxt is not None:
            if nxt["status"] == "done":
                raise ApiError("Das Folgespiel wurde schon gespielt – zuerst dieses zurücksetzen.")
            col = "p1" if m["pos"] % 2 == 0 else "p2"
            con.execute(f"UPDATE matches SET {col}=NULL WHERE id=?", (nxt["id"],))
        if t["status"] == "finished":
            con.execute("UPDATE tournaments SET status='ko' WHERE id=?", (t["id"],))
    elif t["status"] != "group":
        raise ApiError("Gruppenergebnisse sind nach Start der KO-Phase gesperrt.")
    con.execute("UPDATE matches SET legs1=NULL, legs2=NULL, status='pending', finished_at=NULL WHERE id=?", (m["id"],))


def _match(con, mid):
    m = con.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone()
    if not m:
        raise ApiError("Spiel nicht gefunden", 404)
    return m


def set_result(con, mid, l1, l2):
    m = _match(con, mid)
    if not m["p1"] or not m["p2"]:
        raise ApiError("Spieler stehen noch nicht fest")
    need = m["best_of"] // 2 + 1
    l1, l2 = int(l1), int(l2)
    if not ((l1 == need and 0 <= l2 < need) or (l2 == need and 0 <= l1 < need)):
        raise ApiError(f"Ungültiges Ergebnis für Best-of-{m['best_of']} (Sieger braucht {need} Legs)")
    with con:
        if m["status"] == "done":
            _clear(con, m)
        m = _match(con, mid)
        t = _tournament(con, m["tournament_id"])
        if m["phase"] == "group" and t["status"] != "group":
            raise ApiError("Gruppenergebnisse sind nach Start der KO-Phase gesperrt.")
        con.execute("UPDATE matches SET legs1=?, legs2=?, status='done', finished_at=? WHERE id=?",
                    (l1, l2, now(), mid))
        if m["phase"] == "ko":
            winner = m["p1"] if l1 > l2 else m["p2"]
            last = _last_ko_round(con, m["tournament_id"])
            nxt = _next_match(con, m, last)
            if nxt:
                col = "p1" if m["pos"] % 2 == 0 else "p2"
                con.execute(f"UPDATE matches SET {col}=? WHERE id=?", (winner, nxt["id"]))
            else:
                con.execute("UPDATE tournaments SET status='finished' WHERE id=?", (m["tournament_id"],))
    if m["phase"] == "ko" and _tournament(con, m["tournament_id"])["status"] == "finished":
        backup(con, "turnier-ende")
    return {"ok": True, "tournament_id": m["tournament_id"]}


def reset_result(con, mid):
    m = _match(con, mid)
    if m["status"] != "done":
        return {"ok": True}
    with con:
        _clear(con, m)
    return {"ok": True}


def set_best_of(con, mid, best_of):
    m = _match(con, mid)
    best_of = int(best_of)
    if m["status"] == "done":
        raise ApiError("Spiel ist bereits gespielt")
    if best_of < 1 or best_of % 2 == 0:
        raise ApiError("Best-of muss ungerade sein")
    with con:
        con.execute("UPDATE matches SET best_of=? WHERE id=?", (best_of, mid))
    return {"ok": True}


# ---------------------------------------------------------------- Statistik
def _all_done(con):
    """Alle gespielten Spiele (ohne Entwürfe) mit Turnierinfos."""
    return con.execute(
        "SELECT m.*, t.date, t.name AS tname, t.status AS tstatus FROM matches m JOIN tournaments t ON t.id=m.tournament_id "
        "WHERE m.status='done' ORDER BY t.date, m.tournament_id, m.seq").fetchall()


def ranking(con):
    players = {r["id"]: r["name"] for r in con.execute("SELECT id,name FROM players")}
    stats = {pid: {"id": pid, "name": n, "tournaments": 0, "titles": 0, "finals": 0, "matches": 0, "wins": 0,
                   "losses": 0, "legs_for": 0, "legs_against": 0} for pid, n in players.items()}
    for r in con.execute("SELECT p.player_id FROM participants p JOIN tournaments t ON t.id=p.tournament_id WHERE t.status!='draft'"):
        stats[r[0]]["tournaments"] += 1
    for m in _all_done(con):
        a, b = stats[m["p1"]], stats[m["p2"]]
        a["matches"] += 1
        b["matches"] += 1
        a["legs_for"] += m["legs1"]
        a["legs_against"] += m["legs2"]
        b["legs_for"] += m["legs2"]
        b["legs_against"] += m["legs1"]
        w, l = (a, b) if m["legs1"] > m["legs2"] else (b, a)
        w["wins"] += 1
        l["losses"] += 1
        if m["phase"] == "ko":
            last = _last_ko_round(con, m["tournament_id"])
            if m["round"] == last:
                w["titles"] += 1
                w["finals"] += 1
                l["finals"] += 1
    out = []
    for s in stats.values():
        if not s["tournaments"]:
            continue
        s["diff"] = s["legs_for"] - s["legs_against"]
        s["win_rate"] = round(100 * s["wins"] / s["matches"]) if s["matches"] else 0
        s["leg_rate"] = round(100 * s["legs_for"] / (s["legs_for"] + s["legs_against"])) \
            if s["legs_for"] + s["legs_against"] else 0
        out.append(s)
    out.sort(key=lambda s: (-s["titles"], -s["diff"], -s["legs_for"], s["name"].lower()))
    return out


def head_to_head(con, a, b):
    players = {r["id"]: r["name"] for r in con.execute("SELECT id,name FROM players WHERE id IN (?,?)", (a, b))}
    if a not in players or b not in players or a == b:
        raise ApiError("Bitte zwei verschiedene Spieler wählen")
    res = {"a": {"id": a, "name": players[a], "wins": 0, "legs": 0},
           "b": {"id": b, "name": players[b], "wins": 0, "legs": 0}, "matches": []}
    for m in _all_done(con):
        if {m["p1"], m["p2"]} != {a, b}:
            continue
        la, lb = (m["legs1"], m["legs2"]) if m["p1"] == a else (m["legs2"], m["legs1"])
        res["a"]["legs"] += la
        res["b"]["legs"] += lb
        res["a" if la > lb else "b"]["wins"] += 1
        last = _last_ko_round(con, m["tournament_id"]) if m["phase"] == "ko" else None
        res["matches"].append({"date": m["date"], "tournament": m["tname"], "tournament_id": m["tournament_id"],
                               "phase": "KO: " + logic.round_name(m["round"], last + 1) if last is not None else "Gruppenphase",
                               "legs_a": la, "legs_b": lb})
    return res


def player_stats(con, pid):
    row = con.execute("SELECT id,name FROM players WHERE id=?", (pid,)).fetchone()
    if not row:
        raise ApiError("Spieler nicht gefunden", 404)
    total = next((s for s in ranking(con) if s["id"] == pid), None)
    opp, history = {}, []
    names = {r["id"]: r["name"] for r in con.execute("SELECT id,name FROM players")}
    for m in _all_done(con):
        if pid not in (m["p1"], m["p2"]):
            continue
        other = m["p2"] if m["p1"] == pid else m["p1"]
        mine, theirs = (m["legs1"], m["legs2"]) if m["p1"] == pid else (m["legs2"], m["legs1"])
        o = opp.setdefault(other, {"id": other, "name": names[other], "matches": 0, "wins": 0, "legs_for": 0, "legs_against": 0})
        o["matches"] += 1
        o["wins"] += mine > theirs
        o["legs_for"] += mine
        o["legs_against"] += theirs
    for t in con.execute("SELECT t.id FROM tournaments t JOIN participants p ON p.tournament_id=t.id "
                         "WHERE p.player_id=? AND t.status!='draft' ORDER BY t.date DESC, t.id DESC", (pid,)):
        st = tournament_state(con, t["id"])
        grp = next(g for g in st["groups"] if any(p["id"] == pid for p in g["players"]))
        srow = next(r for r in grp["standings"] if r["id"] == pid)
        res = st["ko_result"].get(str(pid)) if st["ko"] else None
        history.append({"id": st["id"], "name": st["name"], "date": st["date"], "group": grp["name"],
                        "group_rank": srow["rank"], "group_size": len(grp["players"]),
                        "legs_for": srow["legs_for"], "legs_against": srow["legs_against"],
                        "ko": res, "status": st["status"]})
    return {"id": pid, "name": row["name"], "total": total, "opponents": sorted(opp.values(), key=lambda o: -o["matches"]),
            "history": history}

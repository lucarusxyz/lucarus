"""Reine Turnierlogik (ohne Datenbank / HTTP): Gruppen, Spielplan, Tabelle, KO-Baum."""
import random


# ---------------------------------------------------------------- Gruppen
def group_options(n):
    """Mögliche Gruppenaufteilungen für n Spieler (Gruppen mit mind. 3 Spielern)."""
    opts = []
    for g in range(1, n // 3 + 1):
        base, extra = divmod(n, g)
        sizes = [base + 1] * extra + [base] * (g - extra)
        opts.append({
            "groups": g,
            "sizes": sizes,
            "matches": sum(s * (s - 1) // 2 for s in sizes),
            "recommended": False,
        })
    if opts:
        rec = min(max(1, round(n / 5)), len(opts))
        opts[rec - 1]["recommended"] = True
    return opts


def draw_groups(ids, sizes, rng=None):
    ids = list(ids)
    (rng or random).shuffle(ids)
    out, i = [], 0
    for s in sizes:
        out.append(ids[i:i + s])
        i += s
    return out


def round_robin(ids):
    """Jeder gegen jeden (Kreismethode). Liefert Liste von Spieltagen mit (a, b)."""
    ids = list(ids)
    if len(ids) % 2:
        ids.append(None)
    n = len(ids)
    rounds = []
    for _ in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = ids[i], ids[n - 1 - i]
            if a is not None and b is not None:
                pairs.append((a, b))
        rounds.append(pairs)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    return rounds


def schedule(groups):
    """Spielreihenfolge über alle Gruppen; vermeidet, dass jemand direkt nacheinander spielt."""
    per = [round_robin(g) for g in groups]
    flat = []
    for r in range(max((len(p) for p in per), default=0)):
        for gi, p in enumerate(per):
            if r < len(p):
                for a, b in p[r]:
                    flat.append((gi, a, b))
    ordered, remaining = [], flat[:]
    while remaining:
        pick = None
        for lookback in (2, 1, 0):
            blocked = set()
            for m in ordered[len(ordered) - lookback:] if lookback else []:
                blocked.update(m[1:])
            pick = next((m for m in remaining if m[1] not in blocked and m[2] not in blocked), None)
            if pick:
                break
        ordered.append(pick)
        remaining.remove(pick)
    return ordered


# ---------------------------------------------------------------- Tabelle
def standings(players, matches):
    """Tabelle: 1. gewonnene Legs, 2. Leg-Differenz, 3. direkter Vergleich.

    players: [{id, name}], matches: dicts mit p1, p2, legs1, legs2, status.
    """
    rows = {p["id"]: {"id": p["id"], "name": p["name"], "played": 0, "wins": 0, "losses": 0,
                      "legs_for": 0, "legs_against": 0, "tie": False} for p in players}
    done = [m for m in matches if m["status"] == "done" and m["p1"] in rows and m["p2"] in rows]
    for m in done:
        a, b = rows[m["p1"]], rows[m["p2"]]
        a["played"] += 1
        b["played"] += 1
        a["legs_for"] += m["legs1"]
        a["legs_against"] += m["legs2"]
        b["legs_for"] += m["legs2"]
        b["legs_against"] += m["legs1"]
        if m["legs1"] > m["legs2"]:
            a["wins"] += 1
            b["losses"] += 1
        else:
            b["wins"] += 1
            a["losses"] += 1
    for r in rows.values():
        r["diff"] = r["legs_for"] - r["legs_against"]

    def key(r):
        return (-r["legs_for"], -r["diff"])

    ordered = sorted(rows.values(), key=lambda r: (key(r), r["name"].lower()))
    result, i = [], 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and key(ordered[j + 1]) == key(ordered[i]):
            j += 1
        cluster = ordered[i:j + 1]
        if len(cluster) > 1:
            cluster = _head_to_head(cluster, done)
        result.extend(cluster)
        i = j + 1
    for k, r in enumerate(result):
        r["rank"] = k + 1
    return result


def _head_to_head(cluster, done):
    ids = {r["id"] for r in cluster}
    mw = {i: 0 for i in ids}
    md = {i: 0 for i in ids}
    for m in done:
        if m["p1"] in ids and m["p2"] in ids:
            md[m["p1"]] += m["legs1"] - m["legs2"]
            md[m["p2"]] += m["legs2"] - m["legs1"]
            mw[m["p1"] if m["legs1"] > m["legs2"] else m["p2"]] += 1

    def k(r):
        return (-mw[r["id"]], -md[r["id"]])

    cluster = sorted(cluster, key=lambda r: (k(r), r["name"].lower()))
    for r in cluster:
        r["tie"] = sum(1 for o in cluster if k(o) == k(r)) > 1
    return cluster


# ---------------------------------------------------------------- KO-Phase
def ko_options(sizes):
    """Gültige KO-Feldgrößen (2, 4, 8, ...) für die Gruppengrößen."""
    g, total = len(sizes), sum(sizes)
    out = []
    for n in (2, 4, 8, 16, 32):
        if n > total or n < g:
            continue
        per = n // g
        if per > min(sizes):
            continue
        if n - per * g > sum(1 for s in sizes if s > per):
            continue
        out.append(n)
    return out


def default_ko_size(sizes):
    opts = ko_options(sizes)
    if not opts:
        return None
    limit = len(sizes) * (min(sizes) - 1)
    if len(sizes) == 1:
        limit = min(limit, 4)
    fit = [n for n in opts if n <= limit]
    return fit[-1] if fit else opts[0]


def select_qualifiers(group_tables, n):
    """group_tables: Liste von Tabellen (Zeilen mit rank). Rest wird mit Wildcards aufgefüllt."""
    g = len(group_tables)
    per = n // g
    quali, pool = [], []
    for gi, rows in enumerate(group_tables):
        for pl, row in enumerate(rows):
            entry = dict(row, group=gi, place=pl + 1, wildcard=False)
            if pl < per:
                quali.append(entry)
            elif pl == per:
                pool.append(dict(entry, wildcard=True))
    pool.sort(key=lambda r: (-r["diff"], -r["legs_for"], r["group"]))
    quali += pool[:n - per * g]
    return quali


def seed_qualifiers(quali, num_groups):
    if num_groups <= 2:
        key = lambda r: (r["place"], r["group"])
    else:
        key = lambda r: (r["place"], -r["diff"], -r["legs_for"], r["group"])
    seeded = sorted(quali, key=key)
    for i, r in enumerate(seeded):
        r["seed"] = i + 1
    return seeded


def seed_order(n):
    order = [1]
    while len(order) < n:
        m = len(order) * 2 + 1
        order = [x for s in order for x in (s, m - s)]
    return order


def bracket_slots(seeded):
    """Setzliste (1 vs N, ...) und Vermeidung gleicher Gruppen in Runde 1."""
    slots = [seeded[s - 1] for s in seed_order(len(seeded))]
    n = len(slots)

    def clash(a, b):
        return a["group"] == b["group"]

    for i in range(0, n, 2):
        if not clash(slots[i], slots[i + 1]):
            continue
        best = None
        for j in range(0, n, 2):
            if j == i:
                continue
            for jj in (j, j + 1):
                other = slots[j + 1] if jj == j else slots[j]
                if clash(slots[i], slots[jj]) or clash(slots[i + 1], other):
                    continue
                dist = abs(slots[i + 1]["seed"] - slots[jj]["seed"])
                if best is None or dist < best[0]:
                    best = (dist, jj)
        if best:
            jj = best[1]
            slots[i + 1], slots[jj] = slots[jj], slots[i + 1]
    return slots


def round_name(r, total_rounds):
    left = total_rounds - r
    return {1: "Finale", 2: "Halbfinale", 3: "Viertelfinale", 4: "Achtelfinale"}.get(left, f"Runde {r + 1}")

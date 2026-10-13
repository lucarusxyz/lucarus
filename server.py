#!/usr/bin/env python3
"""Dart Club Pischelsdorf e.V. – Ranking-Turnier-Verwaltung (nur Python-Standardbibliothek)."""
import argparse
import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import logic
import service as svc
from service import ApiError

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def routes():
    S = svc
    return [
        ("GET", r"/api/players", lambda c, b, q: S.list_players(c)),
        ("POST", r"/api/players", lambda c, b, q: S.add_player(c, b.get("name"))),
        ("PUT", r"/api/players/(\d+)", lambda c, b, q, i: S.update_player(c, int(i), b)),
        ("DELETE", r"/api/players/(\d+)", lambda c, b, q, i: S.delete_player(c, int(i))),
        ("GET", r"/api/players/(\d+)/stats", lambda c, b, q, i: S.player_stats(c, int(i))),
        ("GET", r"/api/group-options", lambda c, b, q: logic.group_options(int(q.get("n", 0)))),
        ("GET", r"/api/tournaments", lambda c, b, q: S.list_tournaments(c)),
        ("POST", r"/api/tournaments", lambda c, b, q: S.create_tournament(c, b)),
        ("GET", r"/api/tournaments/(\d+)", lambda c, b, q, i: S.tournament_state(c, int(i))),
        ("DELETE", r"/api/tournaments/(\d+)", lambda c, b, q, i: S.delete_tournament(c, int(i))),
        ("POST", r"/api/tournaments/(\d+)/redraw", lambda c, b, q, i: S.redraw(c, int(i))),
        ("POST", r"/api/tournaments/(\d+)/swap", lambda c, b, q, i: S.swap(c, int(i), int(b["a"]), int(b["b"]))),
        ("PUT", r"/api/tournaments/(\d+)/settings", lambda c, b, q, i: S.update_settings(c, int(i), b)),
        ("POST", r"/api/tournaments/(\d+)/start", lambda c, b, q, i: S.start(c, int(i))),
        ("GET", r"/api/tournaments/(\d+)/ko-preview", lambda c, b, q, i: S.ko_preview(c, int(i), int(q.get("size", 0)))),
        ("POST", r"/api/tournaments/(\d+)/ko-start", lambda c, b, q, i: S.ko_start(c, int(i), b)),
        ("POST", r"/api/matches/(\d+)/result", lambda c, b, q, i: S.set_result(c, int(i), b["legs1"], b["legs2"])),
        ("POST", r"/api/matches/(\d+)/reset", lambda c, b, q, i: S.reset_result(c, int(i))),
        ("PUT", r"/api/matches/(\d+)", lambda c, b, q, i: S.set_best_of(c, int(i), b["best_of"])),
        ("GET", r"/api/ranking", lambda c, b, q: S.ranking(c)),
        ("GET", r"/api/h2h", lambda c, b, q: S.head_to_head(c, int(q.get("a", 0)), int(q.get("b", 0)))),
        ("GET", r"/api/display", display),
    ]


def display(con, body, q):
    tid = svc.active_tournament_id(con)
    if tid is None:
        row = con.execute("SELECT id FROM tournaments WHERE status='finished' ORDER BY date DESC, id DESC").fetchone()
        tid = row["id"] if row else None
    return {"tournament": svc.tournament_state(con, tid) if tid else None, "ranking": svc.ranking(con)[:10]}


ROUTES = [(m, re.compile(p + r"$"), f) for m, p, f in routes()]


class Handler(BaseHTTPRequestHandler):
    server_version = "DartClub/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("DART_VERBOSE"):
            super().log_message(fmt, *args)

    def _send(self, status, payload, ctype="application/json; charset=utf-8", extra=None):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _api(self, method):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        except ValueError:
            return self._send(400, {"error": "Ungültiges JSON"})
        if url.path == "/api/backup" and method == "GET":
            con = svc.connect()
            path = svc.backup(con, "download")
            with open(path, "rb") as f:
                return self._send(200, f.read(), "application/octet-stream",
                                  {"Content-Disposition": f'attachment; filename="{os.path.basename(path)}"'})
        for m, rx, fn in ROUTES:
            mt = rx.match(url.path)
            if m == method and mt:
                con = svc.connect()
                try:
                    return self._send(200, fn(con, body, q, *mt.groups()))
                except ApiError as e:
                    return self._send(e.status, {"error": str(e)})
                except (KeyError, ValueError, TypeError) as e:
                    return self._send(400, {"error": f"Ungültige Eingabe: {e}"})
                finally:
                    con.close()
        self._send(404, {"error": "Nicht gefunden"})

    def _static(self):
        path = urlparse(self.path).path
        path = {"/": "/index.html", "/display": "/display.html"}.get(path, path)
        full = os.path.normpath(os.path.join(WEB, path.lstrip("/")))
        if not full.startswith(WEB) or not os.path.isfile(full):
            return self._send(404, b"Nicht gefunden", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype + ("; charset=utf-8" if ctype.startswith("text") or "javascript" in ctype else ""))

    def do_GET(self):
        self._api("GET") if self.path.startswith("/api/") else self._static()

    def do_POST(self):
        self._api("POST")

    def do_PUT(self):
        self._api("PUT")

    def do_DELETE(self):
        self._api("DELETE")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1", help="Standard: nur dieser Rechner (127.0.0.1)")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    svc.connect().close()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dart Club Pischelsdorf läuft:\n  Verwaltung: http://{args.host}:{args.port}/\n  Monitor:    http://{args.host}:{args.port}/display\n"
          f"  Datenbank:  {svc.DB_PATH}\nBeenden mit Strg+C", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
        sys.exit(0)


if __name__ == "__main__":
    main()

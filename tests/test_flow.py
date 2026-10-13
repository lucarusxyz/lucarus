import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DART_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
import service as svc  # noqa: E402


class FlowTest(unittest.TestCase):
    def play(self, con, st_matches):
        for m in st_matches:
            need = m["best_of"] // 2 + 1
            lo = random.randint(0, need - 1)
            a, b = (need, lo) if random.random() < .5 else (lo, need)
            svc.set_result(con, m["id"], a, b)

    def test_full(self):
        con = svc.connect()
        ids = [svc.add_player(con, f"P{i}")["id"] for i in range(10)]
        t = svc.create_tournament(con, {"player_ids": ids, "groups": 2})["id"]
        with self.assertRaises(svc.ApiError):
            svc.create_tournament(con, {"player_ids": ids, "groups": 2})
        svc.redraw(con, t)
        svc.start(con, t)
        st = svc.tournament_state(con, t)
        self.assertEqual(len(st["matches"]), 20)
        self.assertIsNotNone(st["current"])
        with self.assertRaises(svc.ApiError):
            svc.set_result(con, st["matches"][0]["id"], 1, 1)
        self.play(con, st["matches"])
        st = svc.tournament_state(con, t)
        self.assertTrue(st["group_done"])
        self.assertEqual(st["ko_default"], 8)
        prev = svc.ko_preview(con, t, 8)
        self.assertEqual(len(prev["pairs"]), 4)
        svc.ko_start(con, t, {"size": 8})
        for _ in range(3):
            st = svc.tournament_state(con, t)
            ready = [m for m in st["matches"] if m["phase"] == "ko" and m["status"] == "pending" and m["p1"] and m["p2"]]
            self.play(con, ready)
        st = svc.tournament_state(con, t)
        self.assertEqual(st["status"], "finished")
        self.assertEqual(st["ko"]["rounds"][-1]["best_of"], 5)
        self.assertTrue(st["champion_name"])
        # Korrektur: Halbfinale zurücksetzen geht nicht, solange das Finale gespielt ist
        semi = st["ko"]["rounds"][1]["matches"][0]
        with self.assertRaises(svc.ApiError):
            svc.reset_result(con, semi["id"])
        svc.reset_result(con, st["ko"]["rounds"][2]["matches"][0]["id"])
        self.assertEqual(svc.tournament_state(con, t)["status"], "ko")
        r = svc.ranking(con)
        self.assertEqual(len(r), 10)
        self.assertEqual(sum(x["titles"] for x in r), 0)
        h = svc.head_to_head(con, ids[0], ids[1])
        self.assertIn("matches", h)
        self.assertTrue(svc.player_stats(con, ids[0])["history"])
        svc.delete_tournament(con, t)


if __name__ == "__main__":
    unittest.main()

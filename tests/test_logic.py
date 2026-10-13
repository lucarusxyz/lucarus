import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import logic  # noqa: E402


def m(p1, p2, l1, l2):
    return {"p1": p1, "p2": p2, "legs1": l1, "legs2": l2, "status": "done"}


class LogicTests(unittest.TestCase):
    def test_group_options(self):
        o = logic.group_options(9)
        self.assertEqual([x["sizes"] for x in o], [[9], [5, 4], [3, 3, 3]])
        self.assertEqual([x["groups"] for x in o if x["recommended"]], [2])
        self.assertEqual([x["groups"] for x in logic.group_options(10) if x["recommended"]], [2])
        self.assertEqual([x["groups"] for x in logic.group_options(14) if x["recommended"]], [3])

    def test_round_robin_complete(self):
        for n in (3, 4, 5, 6, 9):
            pairs = [frozenset(p) for r in logic.round_robin(range(n)) for p in r]
            self.assertEqual(len(pairs), n * (n - 1) // 2)
            self.assertEqual(len(set(pairs)), len(pairs))

    def test_schedule_no_back_to_back(self):
        s = logic.schedule([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])
        self.assertEqual(len(s), 20)
        for a, b in zip(s, s[1:]):
            self.assertFalse(set(a[1:]) & set(b[1:]))

    def test_standings_tiebreak(self):
        players = [{"id": i, "name": n} for i, n in ((1, "A"), (2, "B"), (3, "C"))]
        # alle haben 2 Legs gewonnen/verloren -> Gleichstand, direkter Vergleich entscheidet
        ms = [m(1, 2, 2, 1), m(2, 3, 2, 1), m(3, 1, 2, 1)]
        t = logic.standings(players, ms)
        self.assertEqual([r["legs_for"] for r in t], [3, 3, 3])
        self.assertTrue(all(r["tie"] for r in t))  # Dreierkreis nicht aufzulösen
        ms = [m(1, 2, 2, 0), m(2, 3, 2, 1), m(3, 1, 0, 2)]
        t = logic.standings(players, ms)
        self.assertEqual(t[0]["id"], 1)

    def test_h2h_two_players(self):
        players = [{"id": i, "name": n} for i, n in ((1, "A"), (2, "B"), (3, "C"), (4, "D"))]
        ms = [m(1, 2, 2, 1), m(1, 3, 1, 2), m(1, 4, 2, 1),
              m(2, 3, 2, 1), m(2, 4, 2, 0), m(3, 4, 0, 2)]
        # A: 5:4  B: 5:2...  Test nur Konsistenz der Rangfolge
        t = logic.standings(players, ms)
        self.assertEqual(sorted(r["rank"] for r in t), [1, 2, 3, 4])

    def test_bracket_two_groups(self):
        tables = [
            [{"id": f"{g}{i}", "name": f"{g}{i}", "diff": 0, "legs_for": 0} for i in range(1, 5)]
            for g in "AB"
        ]
        q = logic.seed_qualifiers(logic.select_qualifiers(tables, 8), 2)
        slots = logic.bracket_slots(q)
        pairs = [(slots[i]["id"], slots[i + 1]["id"]) for i in range(0, 8, 2)]
        self.assertEqual(pairs, [("A1", "B4"), ("B2", "A3"), ("B1", "A4"), ("A2", "B3")])

    def test_ko_options(self):
        self.assertEqual(logic.ko_options([5, 5]), [2, 4, 8])
        self.assertEqual(logic.default_ko_size([5, 5]), 8)
        self.assertEqual(logic.default_ko_size([3, 3, 3]), 4)
        self.assertEqual(logic.default_ko_size([9]), 4)
        self.assertEqual(logic.default_ko_size([5, 5, 4]), 8)

    def test_wildcards(self):
        tables = [[{"id": f"{g}{i}", "name": "x", "diff": 10 - i - gi, "legs_for": 5}
                   for i in range(1, 4)] for gi, g in enumerate("ABC")]
        q = logic.select_qualifiers(tables, 4)
        self.assertEqual(len(q), 4)
        self.assertEqual(sum(1 for x in q if x["wildcard"]), 1)


if __name__ == "__main__":
    unittest.main()

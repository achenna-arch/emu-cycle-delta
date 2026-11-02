"""Checks the analysis on synthetic data with known truth. Not a result."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "campaign"))

import build_matrix as bm
import delta_metrics as dm
import gate_g2 as g2
import gate_pretest as gp
import mutants as mt
import parse_log as pl
import qemu_bridge as qb
from synth import make_cells


class Metrics(unittest.TestCase):
    @staticmethod
    def floor(cells, level):
        return pd.Series(level, index=cells["op"].unique())

    def test_faithful_emulator_scores_high(self):
        cells = make_cells(layout_sigma=0.0)
        c = dm.criteria(dm.pair_table(cells, self.floor(cells, 0.01)))
        self.assertGreater(c["moved_built"], 50)
        self.assertEqual(c["c1_sign_agreement"], 1.0)
        self.assertEqual(c["renode_zero_share"], 0.0)
        self.assertGreater(c["c2_spearman"], 0.95)
        self.assertLess(c["c3_false_alarm_built"], 0.05)
        self.assertLess(c["c4_miss_built"], 0.05)
        self.assertLess(c["c4_miss_code"], 0.05)

    def test_blind_moves_become_misses(self):
        c = dm.criteria(dm.pair_table(make_cells(blind_share=0.6, layout_sigma=0.0)))
        self.assertGreater(c["c4_miss_built"], 0.4)
        self.assertLess(c["c1_sign_agreement"], 0.6)

    def test_renode_zero_is_declared_not_excluded(self):
        c = dm.criteria(dm.pair_table(make_cells(p_move=0.1, layout_sigma=0.002)))
        self.assertGreater(c["renode_zero_share"], 0.5)
        self.assertLess(c["c1_sign_agreement"], 0.5)

    def test_floor_keeps_layout_noise_out_of_r2(self):
        cells = make_cells(p_move=0.0, layout_sigma=0.02)
        c = dm.criteria(dm.pair_table(cells, self.floor(cells, 0.05)))
        self.assertGreater(c["moved_built"], 50)
        self.assertLessEqual(c["moved_code"] / c["n"], 0.01)

    def test_layout_noise_is_detected(self):
        cells = make_cells(p_move=0.0, layout_sigma=0.02)
        self.assertGreater(dm.c5_share(cells), 0.9)
        self.assertEqual(dm.c5_share(make_cells(p_move=0.0, layout_sigma=0.0002)), 0.0)

    def test_small_real_move_under_threshold_is_a_miss(self):
        cells = make_cells(effect=0.008, layout_sigma=0.0005)
        c = dm.criteria(dm.pair_table(cells, self.floor(cells, 0.002)))
        self.assertGreater(c["moved_code"], 50)
        self.assertGreater(c["c1_sign_code"], 0.95)
        self.assertGreater(c["c4_miss_code"], 0.5)

    def test_missing_floor_is_refused(self):
        cells = make_cells(n_pairs=2)
        with self.assertRaises(ValueError):
            dm.pair_table(cells, pd.Series({"op0": 0.01}))

    def test_interval_brackets_point(self):
        table = dm.pair_table(make_cells(n_pairs=12))
        point = dm.criteria(table)["c2_spearman"]
        low, high = dm.cluster_ci(table, lambda t: dm.criteria(t)["c2_spearman"], n_boot=200)
        self.assertLessEqual(low, point)
        self.assertGreaterEqual(high, point)

    def test_a_pair_drawn_twice_counts_twice(self):
        cells = make_cells(n_pairs=4, layout_sigma=0.02)
        low, high = dm.cluster_ci(cells, dm.c5_share, n_boot=20)
        self.assertLessEqual(low, high)
        seen = []
        dm.cluster_ci(cells, lambda c: seen.append(c["pair"].nunique()) or 0.0, n_boot=20)
        self.assertEqual(set(seen), {4})

    def test_negative_control_reads_the_outside_stratum(self):
        table = pd.DataFrame({"pair": ["A", "B", "B"], "truth_code": [1, 0, 1]})
        strata = pd.Series({"A": "A", "B": "B"})
        self.assertEqual(dm.negative_control(table, strata), 0.5)


class Placebos(unittest.TestCase):
    @staticmethod
    def rows(tag, pad, value, op="sem.give"):
        return {"platform": "silicon", "tag": tag, "pad": pad, "op": op, "p50": value}

    def test_floor_is_the_largest_move(self):
        rows = pd.DataFrame([self.rows("smoke", 0, 100), self.rows("smoke", 4, 101),
                             self.rows("smoke/g1", 0, 103), self.rows("smoke/g2", 0, 95)])
        plain, marked = dm.split_placebos(rows)
        self.assertEqual(len(marked), 2)
        self.assertAlmostEqual(dm.placebo_floor(plain, marked)["sem.give"], 0.05)

    def test_a_larger_rigid_spread_raises_the_floor(self):
        rows = pd.DataFrame([self.rows("smoke", 0, 100), self.rows("smoke", 4, 300),
                             self.rows("smoke/g1", 0, 103)])
        plain, marked = dm.split_placebos(rows)
        self.assertAlmostEqual(dm.placebo_floor(plain, marked)["sem.give"], 1.0)

    def test_placebo_without_base_is_refused(self):
        rows = pd.DataFrame([self.rows("smoke", 4, 100), self.rows("smoke/g1", 0, 103)])
        plain, marked = dm.split_placebos(rows)
        with self.assertRaises(ValueError):
            dm.placebo_floor(plain, marked)


class Sample(unittest.TestCase):
    ROWS = [{"pair": f"{s}{i:03d}", "stratum": s, "selected": str(int(i < q))}
            for s, q in (("A", 6), ("B", 2)) for i in range(q + 2)]

    def test_a_failed_pair_gives_way_to_the_next_of_its_stratum(self):
        got = [r["pair"] for r in bm.sample(self.ROWS, {"A001"})]
        self.assertEqual(got, ["A000", "A002", "A003", "A004", "A005", "A006", "B000", "B001"])

    def test_placebos_follow_the_kept_pairs(self):
        tags = bm.placebo_tags(bm.sample(self.ROWS, {"A001", "B000"}))
        self.assertEqual(tags, ["A000:parent", "A002:parent", "A003:parent", "A004:parent",
                                "A005:parent", "B001:parent"])


class Bridge(unittest.TestCase):
    @staticmethod
    def rows(parent, child, step=1.0):
        return pd.DataFrame([{"tag": f"A000:{side}", "pad": 0, "platform": "x", "op": op,
                              "p50": value * step}
                             for side, values in (("parent", parent), ("child", child))
                             for op, value in values.items()])

    def test_timer_phase_is_not_a_delta(self):
        got = qb.deltas(qb.instructions(self.rows({"op": 102}, {"op": 103})))
        self.assertEqual(got.iloc[0], 0)

    def test_same_moves_pass(self):
        parent, child = {"a": 100, "b": 200, "c": 50}, {"a": 110, "b": 200, "c": 45}
        table = qb.bridge(self.rows(parent, child, 3.2), self.rows(parent, child))
        got = qb.criteria(table)
        self.assertEqual(got["q1"], 1.0)
        self.assertTrue(got["pass"])

    def test_opposite_moves_fail(self):
        parent = {"a": 100, "b": 200, "c": 50}
        table = qb.bridge(self.rows(parent, {"a": 110, "b": 180, "c": 55}, 3.2),
                          self.rows(parent, {"a": 90, "b": 220, "c": 45}))
        self.assertFalse(qb.criteria(table)["pass"])


class Mutants(unittest.TestCase):
    @staticmethod
    def rows(cost):
        out = []
        for pad in (0, 4, 8, 12):
            out.append({"tag": "smoke", "pad": pad, "op": "sem.give", "p50": 48 + pad})
            for n in (4, 8):
                out.append({"tag": f"mut_alu{n}", "pad": pad, "op": "sem.give",
                            "p50": 48 + pad + n * cost})
        return pd.DataFrame(out)

    def test_slope_is_the_cost_of_an_instruction(self):
        got = mt.slopes(mt.added(self.rows(2)))
        self.assertAlmostEqual(got.loc[0, "slope"], 2.0)


class Parser(unittest.TestCase):
    LOG = [
        "BENCH,START,nrf52840dk,A000:parent,4,1000\n",
        "BENCH,ROUND,0\n",
        "1578319671.676831;nrf52840dk-1;R,sem.give,1000,50,51,52,60,90,53\r\n",
        "BENCH,DONE\n",
    ]

    def test_prefix_and_fields(self):
        rows, done, boots = pl.parse_lines(self.LOG, "silicon")
        self.assertEqual((done, boots, len(rows)), (1, 1, 1))
        self.assertEqual(rows[0][:6], ["silicon", "A000:parent", 4, 0, 0, "sem.give"])
        self.assertEqual(rows[0][9], 52)

    def test_firmware_error_raises(self):
        with self.assertRaises(ValueError):
            pl.parse_lines(["BENCH,ERROR,NO_COUNTER\n"], "silicon")

    def test_truncated_boot_is_reported(self):
        _, done, boots = pl.parse_lines(self.LOG[:3], "silicon")
        self.assertEqual((done, boots), (0, 1))

    def test_reset_drops_the_cut_boot(self):
        glued = "R,sem.give,1000,50BENCH,START,nrf52840dk,A000:parent,4,1000\n"
        rows, done, boots = pl.parse_lines(self.LOG[:3] + [glued] + self.LOG[1:], "silicon")
        self.assertEqual((done, boots, len(rows)), (1, 2, 1))
        self.assertEqual(rows[0][3], 1)

    def test_placebo_log_is_marked_by_its_name(self):
        rows, _, _ = pl.parse_lines(self.LOG, "silicon")
        self.assertEqual(pl.mark_placebo(rows, "A000_parent_g3")[0][1], "A000:parent/g3")
        rows, _, _ = pl.parse_lines(self.LOG, "silicon")
        self.assertEqual(pl.mark_placebo(rows, "A000_parent_p4")[0][1], "A000:parent")


class LogsToCriteria(unittest.TestCase):
    PADS = range(0, 16, 4)

    @staticmethod
    def log(tag, pad, value):
        return [f"BENCH,START,nrf52840dk,{tag},{pad},1000\n", "BENCH,ROUND,0\n",
                f"R,sem.give,1000,1,1,{value},1,1,1\n", "BENCH,DONE\n"]

    def rows(self):
        out = []
        for platform, parent, child in (("silicon", 100, 110), ("renode", 50, 51)):
            step = 1 if platform == "silicon" else 0
            for pad in self.PADS:
                for tag, base in (("A000:parent", parent), ("A000:child", child)):
                    value = base + step * pad // 4
                    out += pl.parse_lines(self.log(tag, pad, value), platform)[0]
        return pd.DataFrame(out, columns=pl.FIELDS)

    def test_logs_reach_the_pair_table(self):
        table = dm.pair_table(dm.cells_from_rows(dm.label_rows(self.rows())))
        self.assertEqual(len(table), 1)
        self.assertEqual(table.loc[0, "truth_built"], 1)
        self.assertAlmostEqual(table.loc[0, "delta_renode"], 0.02)
        self.assertAlmostEqual(table.loc[0, "delta_silicon"], 0.10)
        self.assertAlmostEqual(table.loc[0, "delta_code"], 111.5 / 101.5 - 1)

    def test_control_lines_stay_out_of_the_cells(self):
        rows = pd.DataFrame({"pair": ["A"] * 3, "side": ["parent"] * 3, "pad": [0] * 3,
                             "platform": ["silicon"] * 3, "p50": [1, 2, 3],
                             "op": ["sem.give", "calib.alu", "clock.overhead"]})
        self.assertEqual(list(dm.cells_from_rows(rows)["op"]), ["sem.give"])

    def test_tag_without_side_is_refused(self):
        with self.assertRaises(ValueError):
            dm.label_rows(pd.DataFrame({"tag": ["smoke"]}))


class GateG2(unittest.TestCase):
    @staticmethod
    def rows(give, wake, placebo=(48, 1330)):
        out = []
        for op, base, mutants, moved in (("sem.give", 48, give, placebo[0]),
                                         ("sem.wake", 1322, wake, placebo[1])):
            for pad in g2.SHIFTS:
                out.append({"tag": "smoke", "pad": pad, "op": op, "p50": base})
                for tag in g2.MUTANTS:
                    out.append({"tag": tag, "pad": pad, "op": op, "p50": mutants})
            out.append({"tag": "smoke/g1", "pad": 0, "op": op, "p50": moved})
        return pd.DataFrame(out)

    def test_a_visible_mutant_clears_the_floor(self):
        table, _ = g2.gate(self.rows(80, 1354))
        self.assertTrue(table["clears"].all())

    def test_a_mutant_lost_in_the_noise_fails(self):
        table, _ = g2.gate(self.rows(80, 1326))
        self.assertFalse(table["clears"].all())

    def test_a_missing_shift_is_refused(self):
        rows = self.rows(80, 1354)
        rows = rows[~((rows["tag"] == "mut_alu32") & (rows["pad"] == 8))]
        with self.assertRaises(ValueError):
            g2.gate(rows)


def frame(values, jitter=0.0):
    rows = []
    for op, v in values.items():
        for r in range(5):
            rows.append({"op": op, "p50": v * (1 + jitter * (r - 2) / 2)})
    return pd.DataFrame(rows)


class Gates(unittest.TestCase):
    INSTR = {"clock.overhead": 2, "calib.alu": 1004, "calib.load": 1004,
             "sem.give": 100, "yield.switch": 300, "irq.enter": 60}

    def test_all_pass(self):
        cycles = {"clock.overhead": 2, "calib.alu": 1010, "calib.load": 2010,
                  "sem.give": 130, "yield.switch": 520, "irq.enter": 150}
        got, _ = gp.gates(frame(cycles, 0.002), frame(self.INSTR))
        self.assertTrue(all(got.values()), got)

    def test_constant_ratio_is_trivial(self):
        cycles = {k: v * 1.4 for k, v in self.INSTR.items()}
        got, _ = gp.gates(frame(cycles), frame(self.INSTR))
        self.assertFalse(got["P4_not_trivial"])

    def test_unstable_cycles_fail(self):
        cycles = {k: v * 1.4 for k, v in self.INSTR.items()}
        got, _ = gp.gates(frame(cycles, 0.05), frame(self.INSTR))
        self.assertFalse(got["P3_silicon_repeatable"])

    def test_mixed_images_are_refused(self):
        one = pd.DataFrame({"tag": ["smoke"], "pad": [0]})
        two = pd.DataFrame({"tag": ["smoke", "mut_alu8"], "pad": [0, 0]})
        gp.same_image(one, one)
        with self.assertRaises(ValueError):
            gp.same_image(one, two)

    def test_dead_counter_fails(self):
        dead = {k: 0 for k in self.INSTR}
        got, _ = gp.gates(frame(dead), frame(dead))
        self.assertFalse(got["P1_counter_alive"])
        self.assertFalse(got["P2_renode_counts_instructions"])


if __name__ == "__main__":
    unittest.main()

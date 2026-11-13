import datetime as dt
import math
import unittest

from tests.helpers import ROOT, built
from cwc import data, metrics, pool, speccurve, verdict

D = dt.date
CFG = {"strict_band": 0.15, "kill_share": 0.5}
GOOD = {"determined": True, "lo_pct": -10.0, "hi_pct": 12.0}


def decide(**changes):
    args = dict(take_ratio_min=1.3, interval=GOOD, break_even_pct=-30.0, estimate_pct=-2.0,
                clean_share_below_band=0.01, share_held=True, cfg=CFG)
    args.update(changes)
    return verdict.decide(**args)


class Verdict(unittest.TestCase):
    def test_supported_when_every_rule_holds(self):
        out = decide()
        self.assertEqual(out["label"], verdict.SUPPORTED)
        self.assertEqual(out["loss_bound_pct"], 10.0)

    def test_supported_in_part_when_a_smaller_loss_is_not_ruled_out(self):
        out = decide(interval={"determined": True, "lo_pct": -19.0, "hi_pct": 21.0})
        self.assertEqual((out["label"], out["reason"]), (verdict.SUPPORTED_IN_PART, "smaller_loss_not_ruled_out"))
        self.assertFalse(out["claims"]["strict"])

    def test_supported_in_part_when_a_loss_is_detected_below_break_even(self):
        out = decide(interval={"determined": True, "lo_pct": -12.0, "hi_pct": -3.0})
        self.assertEqual((out["label"], out["reason"]), (verdict.SUPPORTED_IN_PART, "loss_detected_below_break_even"))

    def test_not_supported_in_rule_order(self):
        cases = [
            (dict(take_ratio_min=0.98), "cut_did_not_rise"),
            (dict(interval={"determined": False, "lo_pct": -80.0, "hi_pct": 200.0}), "interval_not_determined"),
            (dict(interval={"determined": True, "lo_pct": -35.0, "hi_pct": 5.0}), "break_even_loss_not_ruled_out"),
            (dict(estimate_pct=-20.0, clean_share_below_band=0.6, interval={"determined": True, "lo_pct": -28.0, "hi_pct": -5.0}), "most_specifications_show_a_loss"),
            (dict(share_held=False), "share_check_failed"),
        ]
        for changes, reason in cases:
            out = decide(**changes)
            self.assertEqual((out["label"], out["reason"]), (verdict.NOT_SUPPORTED, reason))
        first = decide(take_ratio_min=0.9, share_held=False)
        self.assertEqual(first["reason"], "cut_did_not_rise")      # the first failing rule decides

    def test_kill_rule_needs_both_conditions(self):
        self.assertFalse(decide(estimate_pct=-20.0, clean_share_below_band=0.4)["claims"]["kill"])
        self.assertFalse(decide(estimate_pct=-10.0, clean_share_below_band=0.9)["claims"]["kill"])

    def test_share_rule_and_forward_check(self):
        rule = {"capture_floor": 0.2, "max_share_drop_pp": 10.0}
        self.assertTrue(verdict.share_check(0.27, -4.1, rule)["passed"])
        self.assertFalse(verdict.share_check(0.15, -4.1, rule)["passed"])      # the cut was given back
        self.assertFalse(verdict.share_check(0.27, -10.5, rule)["passed"])     # the share fell too far
        passed = verdict.share_check(0.27, -4.1, rule)
        self.assertEqual(verdict.forward_check("2027-02-15", "2026-11-08", passed)["status"], "not yet due")
        self.assertEqual(verdict.forward_check("2027-02-15", "2027-02-14", passed)["status"], "thesis not contradicted")
        failed = verdict.share_check(0.27, -12.0, rule)
        self.assertEqual(verdict.forward_check("2027-02-15", "2027-02-21", failed)["status"], "thesis contradicted")


class Metrics(unittest.TestCase):
    def test_break_even(self):
        self.assertAlmostEqual(metrics.break_even_change(1.0, 1.5), -1.0 / 3.0)
        self.assertAlmostEqual((1.0 + metrics.break_even_change(1.4, 2.1)) * 2.1, 1.4)   # revenue is unchanged at break-even

    def test_window_and_exact_split_on_made_up_series(self):
        start, mid, end = D(2026, 1, 5), D(2026, 1, 19), D(2026, 2, 2)
        days = data.days_between(start, end)
        near = {
            "volume": {d: (100.0 if d < mid else 150.0) for d in days},
            "fees": {d: (1.0 if d < mid else 1.2) for d in days},
            "revenue": {d: (0.1 if d < mid else 0.3) for d in days},
            "front_end": {d: 0.05 for d in days},
            "other": {d: (0.05 if d < mid else 0.25) for d in days},
            "front_end_earned": {d: 0.05 for d in days},
        }
        peers = {"a": {d: 100.0 for d in days}, "b": {d: 50.0 for d in days}}
        before, after = metrics.window(near, peers, start, mid), metrics.window(near, peers, mid, end)
        self.assertAlmostEqual(before["capture_earned"], 0.1)
        self.assertAlmostEqual(before["fee_rate_bps"], 100.0)
        self.assertAlmostEqual(before["take_earned_bps"], 10.0)
        self.assertAlmostEqual(before["share"], 0.4)
        self.assertAlmostEqual(before["share_without"]["b"], 0.5)
        out = metrics.compare(before, after)
        self.assertAlmostEqual(out["split_sum_log"], out["split_total_log"], places=12)
        self.assertAlmostEqual(sum(out["volume_split_log"].values()), out["split_log"]["volume"], places=12)
        self.assertAlmostEqual(out["take_ratio_earned"], 2.0)
        self.assertAlmostEqual(out["break_even_change_earned"], -0.5)
        self.assertAlmostEqual(out["share_change_points"]["all"], 10.0)

    def test_split_adds_up_on_the_real_data(self):
        findings, _ = built()
        for change in findings["changes"].values():
            self.assertAlmostEqual(change["split_sum_log"], change["split_total_log"], places=5)
            self.assertAlmostEqual(math.exp(change["split_total_log"]), change["revenue_ratio_earned"], places=4)


class Peers(unittest.TestCase):
    def test_rule_selects_exactly_the_registered_aggregators(self):
        cfg = data.load_config(ROOT)
        table = pool.select(ROOT, cfg)
        chosen = {r["key"] for r in table["aggregators"] if r["status"] == "peer"}
        registered = {s["key"] for s in cfg["series"] if s["role"] == "peer" and s.get("group") == "aggregator"}
        self.assertEqual(chosen, registered)
        self.assertTrue(all(r["reason"] for r in table["aggregators"] if r["status"] == "excluded"))
        self.assertEqual(pool.slug_of("https://api.llama.fi/summary/dexs/near-intents?x=1"), "near-intents")

    def test_history_rule(self):
        event = D(2026, 2, 23)
        full = {event - dt.timedelta(days=i): 1.0 for i in range(1, 200)}
        self.assertEqual(pool.history_ok(full, event, 26, 5), (True, None))
        short = {day: value for day, value in full.items() if day >= D(2025, 11, 1)}
        ok, week = pool.history_ok(short, event, 26, 5)
        self.assertFalse(ok)
        self.assertEqual(week, D(2025, 8, 25))

    def test_declared_definition_change_is_in_the_raw_file(self):
        changes = pool.definition_changes(ROOT, data.load_config(ROOT))
        self.assertTrue(all(c["date"] for c in changes))


class Curve(unittest.TestCase):
    def test_donor_sets_and_panel_validity(self):
        peers = [{"key": "a", "name": "A", "group": "protocol"}, {"key": "b", "name": "B", "group": "aggregator"}, {"key": "c", "name": "C", "group": "aggregator"}]
        sets = dict(speccurve.donor_sets(peers, [{"key": "z", "name": "Z"}]))
        self.assertEqual(sets["all peers"], ["a", "b", "c"])
        self.assertEqual(sets["without B"], ["a", "c"])
        self.assertEqual(sets["peers plus excluded candidates"], ["a", "b", "c", "z"])
        start = D(2026, 1, 5)
        days = data.days_between(start, start + dt.timedelta(weeks=4))
        ok = {d: 10.0 for d in days}
        gap = {d: (0.0 if D(2026, 1, 12) <= d < D(2026, 1, 16) else 10.0) for d in days}      # four dead days in week two
        series = {"a": ok, "b": gap, "c": ok}
        y, x, used = speccurve.build_panel(ok, series, ["a", "b", "c"], start, 4, 5, {"c": D(2026, 1, 20)})
        self.assertEqual(used, ["a"])            # b has an undefined week, c changes definition inside the window
        self.assertEqual(len(x), 4)
        runs = {"b": data.outages(gap, start, start + dt.timedelta(weeks=4), 3)}
        self.assertFalse(speccurve.window_is_clean(runs, start, start + dt.timedelta(weeks=4)))
        self.assertTrue(speccurve.window_is_clean(runs, D(2026, 1, 19), D(2026, 2, 2)))

    def test_curve_on_the_real_data(self):
        findings, _ = built()
        curve = findings["spec_curve"]
        counts = curve["counts"]
        self.assertEqual(counts["planned"], counts["run"] + counts["beyond_data"] + counts["too_few_donors"]
                         + counts["duplicate_donor_set"] + counts["too_many_donors_for_sc"])
        self.assertEqual(sum(1 for r in curve["rows"] if r["primary"]), 1)
        primary = [r for r in curve["rows"] if r["primary"]][0]
        self.assertTrue(primary["clean"])
        self.assertAlmostEqual(primary["estimate_pct"], findings["event_test"]["estimators"]["sc"]["estimate_pct"], places=6)
        signatures = [(r["event_date"], r["pre_weeks"], r["post_weeks"], r["donor_set"], r["estimator"]) for r in curve["rows"]]
        self.assertEqual(len(signatures), len(set(signatures)))
        self.assertEqual(findings["peers"]["longest_clean_post_weeks"], findings["config"]["post_weeks"])


if __name__ == "__main__":
    unittest.main()

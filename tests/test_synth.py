import itertools
import math
import unittest

from tests.helpers import panel
from cwc import synth


class Simplex(unittest.TestCase):
    def test_inverse(self):
        a = [[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]]
        inv = synth.invert(a)
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(sum(a[i][k] * inv[k][j] for k in range(3)), 1.0 if i == j else 0.0)
        self.assertIsNone(synth.invert([[1.0, 2.0], [2.0, 4.0]]))

    def test_recovers_known_weights_exactly(self):
        x = [[math.sin(t), math.cos(1.7 * t), math.sin(0.4 * t + 1)] for t in range(12)]
        y = [0.2 * r[0] + 0.5 * r[1] + 0.3 * r[2] for r in x]
        w = synth.SimplexFitter(x).solve(y)
        for got, want in zip(w, (0.2, 0.5, 0.3)):
            self.assertAlmostEqual(got, want, places=6)

    def test_corner_solution_and_constraints(self):
        x = [[math.sin(t), math.cos(1.7 * t), math.sin(0.4 * t + 1)] for t in range(12)]
        y = [1.4 * r[0] - 0.4 * r[1] for r in x]            # the unconstrained answer has a negative weight
        w = synth.SimplexFitter(x).solve(y)
        self.assertTrue(all(v >= 0 for v in w))
        self.assertAlmostEqual(sum(w), 1.0, places=9)
        self.assertEqual(w[1], 0.0)

    def test_matches_a_brute_force_search(self):
        x = [[math.sin(t), math.cos(1.7 * t), math.sin(0.4 * t + 1)] for t in range(10)]
        y = [0.9 * r[0] + 0.3 * r[1] - 0.2 * r[2] + 0.05 * math.cos(3 * t) for t, r in enumerate(x)]
        w = synth.SimplexFitter(x).solve(y)
        sse = lambda v: sum((y[t] - sum(v[j] * x[t][j] for j in range(3))) ** 2 for t in range(10))
        best = min(sse((a / 100, b / 100, (100 - a - b) / 100)) for a, b in itertools.product(range(101), repeat=2) if a + b <= 100)
        self.assertLessEqual(sse(w), best + 1e-12)


class EventEstimate(unittest.TestCase):
    def test_known_shift_is_recovered_by_synthetic_control(self):
        for shift in (math.log(0.9), 0.0):
            y, x = panel(13, 11, shift, noise=0.01)
            est = synth.Model(y, x, "sc").event(13)["estimate_log"]
            self.assertAlmostEqual(synth.to_pct(est), synth.to_pct(shift), delta=1.0)

    def test_known_shift_is_recovered_exactly_by_the_two_simple_estimators(self):
        shift = math.log(0.9)
        _, x = panel(13, 11, 0.0)
        for mode in ("equal", "pooled"):
            control = synth.fixed_control(x, mode)
            y = [c + 0.3 + (shift if t >= 13 else 0.0) for t, c in enumerate(control)]
            est = synth.Model(y, x, mode).event(13)
            self.assertAlmostEqual(est["estimate_log"], shift, places=9, msg=mode)
            self.assertAlmostEqual(est["pre_rmse"], 0.0, places=9, msg=mode)

    def test_synthetic_control_weights_and_fit(self):
        y, x = panel(13, 11, 0.0)
        ev = synth.Model(y, x, "sc").event(13)
        self.assertAlmostEqual(sum(ev["weights"]), 1.0, places=9)
        self.assertAlmostEqual(ev["weights"][0], 0.6, delta=0.08)
        self.assertLess(ev["pre_rmse"], 0.05)
        self.assertAlmostEqual(sum(ev["gap"][:13]), 0.0, places=9)   # the intercept centres the gap before the event

    def test_fixed_controls(self):
        x = [[math.log(2.0), math.log(8.0)]]
        self.assertAlmostEqual(synth.fixed_control(x, "equal")[0], math.log(4.0))
        self.assertAlmostEqual(synth.fixed_control(x, "pooled")[0], math.log(10.0))
        self.assertAlmostEqual(synth.slope([1.0, 3.0, 5.0]), 2.0)


class Interval(unittest.TestCase):
    def setUp(self):
        self.grid = synth.theta_grid(-0.6, 0.6, 0.01)

    def test_grid_contains_zero(self):
        self.assertIn(0.0, self.grid)
        self.assertAlmostEqual(self.grid[1] - self.grid[0], 0.01)

    def test_interval_contains_the_true_shift_and_excludes_a_far_one(self):
        true = math.log(0.9)
        y, x = panel(13, 11, true)
        model = synth.Model(y, x, "sc")
        iv = model.interval(13, self.grid, 0.9)
        self.assertTrue(iv["determined"] and iv["contiguous"])
        self.assertLess(iv["lo_log"], true)
        self.assertGreater(iv["hi_log"], true)
        self.assertLess(iv["hi_log"], 0.0)                 # a 10 percent fall is told apart from no change
        self.assertLessEqual(model.p_value(13, 0.2), 0.1)
        self.assertGreater(model.p_value(13, true), 0.1)

    def test_interval_that_runs_off_the_grid_is_not_determined(self):
        y, x = panel(13, 11, math.log(0.9))
        iv = synth.Model(y, x, "sc").interval(13, synth.theta_grid(-0.12, -0.09, 0.01), 0.9)
        self.assertFalse(iv["determined"])

    def test_equal_halves_cannot_reject_at_ten_percent_with_few_weeks(self):
        y, x = panel(9, 9, math.log(0.5))
        iv = synth.Model(y, x, "equal").interval(9, self.grid, 0.9)
        self.assertFalse(iv["determined"])                 # the smallest possible p-value is 2/18, above 0.10


if __name__ == "__main__":
    unittest.main()

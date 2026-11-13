"""Estimators of how one series moved against a group of others after an event,
and a permutation interval for that movement. Pure Python, exact, deterministic.

Three estimators share one interface. Each builds a comparison series (the
"control") from the donor series, removes the average difference before the
event, and reports the average difference after it.

  sc      synthetic control: non-negative donor weights that sum to one, chosen
          to track the treated series before the event, plus an intercept
  equal   every donor gets the same weight (the plain mean of the donors' logs)
  pooled  the log of the donors' summed volume, so large donors count for more

References
  Abadie, Diamond, Hainmueller (2010), synthetic control.
  Doudchenko, Imbens (2016), synthetic control with an intercept.
  Chernozhukov, Wuthrich, Zhu (2021), permutation inference for such designs.
"""
from __future__ import annotations

import itertools
import math

MODES = ("sc", "equal", "pooled")
RIDGE = 1e-10       # added to the diagonal so a set of collinear donors stays solvable
NEG_TOL = 1e-9      # a weight below -NEG_TOL makes a donor subset infeasible
SSE_TOL = 1e-12     # a later subset must beat the best squared error by more than this
P_TOL = 1e-12       # tolerance when a shifted statistic is compared with the observed one


def invert(a: list):
    """Inverse of a square matrix by Gauss-Jordan elimination with partial pivoting. None if singular."""
    n = len(a)
    m = [list(map(float, row)) + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-14:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        scale = m[col][col]
        m[col] = [v / scale for v in m[col]]
        for r in range(n):
            if r != col and m[r][col] != 0.0:
                factor = m[r][col]
                row_c = m[col]
                m[r] = [v - factor * c for v, c in zip(m[r], row_c)]
    return [row[n:] for row in m]


class SimplexFitter:
    """Least squares with weights w >= 0, sum(w) = 1, for one fixed donor matrix.

    The answer is exact. For every non-empty subset of donors the problem with
    the weights only forced to sum to one is a linear system. A subset is
    feasible when none of its weights is negative. The feasible subset with the
    smallest squared error is the solution; ties go to the smaller subset, then
    to the earlier donors. With k donors there are 2^k - 1 subsets, so k is
    capped by the caller. The systems depend only on the donors, so they are
    inverted once and reused for every outcome vector.
    """

    def __init__(self, x: list):
        self.n = len(x)
        self.k = len(x[0]) if x else 0
        self.x = x
        cols = [[row[j] for row in x] for j in range(self.k)]
        self.cols = cols
        self.gram = [[math.fsum(a * b for a, b in zip(cols[i], cols[j])) for j in range(self.k)] for i in range(self.k)]
        self.systems = []
        for size in range(1, self.k + 1):
            for subset in itertools.combinations(range(self.k), size):
                kkt = [[self.gram[i][j] + (RIDGE if i == j else 0.0) for j in subset] + [1.0] for i in subset]
                kkt.append([1.0] * size + [0.0])
                inverse = invert(kkt)
                if inverse is not None:
                    self.systems.append((subset, [row for row in inverse[:size]]))

    def solve(self, y: list) -> list:
        xty = [math.fsum(a * b for a, b in zip(col, y)) for col in self.cols]
        yty = math.fsum(v * v for v in y)
        best_sse, best = None, None
        for subset, inverse in self.systems:
            rhs = [xty[i] for i in subset] + [1.0]
            w = [math.fsum(a * b for a, b in zip(row, rhs)) for row in inverse]
            if min(w) < -NEG_TOL:
                continue
            w = [max(v, 0.0) for v in w]
            sse = yty - 2.0 * math.fsum(w[a] * xty[i] for a, i in enumerate(subset))
            sse += math.fsum(w[a] * w[b] * self.gram[i][j] for a, i in enumerate(subset) for b, j in enumerate(subset))
            if best_sse is None or sse < best_sse - SSE_TOL:
                best_sse, best = sse, (subset, w)
        weights = [0.0] * self.k
        for a, i in enumerate(best[0]):
            weights[i] = best[1][a]
        return weights


def _mean(values: list) -> float:
    return math.fsum(values) / len(values)


def _rms(values: list) -> float:
    return math.sqrt(math.fsum(v * v for v in values) / len(values))


def fixed_control(x: list, mode: str) -> list:
    """Comparison series for the two estimators without fitted weights."""
    if mode == "equal":
        return [_mean(row) for row in x]
    if mode == "pooled":
        return [math.log(math.fsum(math.exp(v) for v in row)) for row in x]
    raise ValueError(f"no fixed control for mode {mode!r}")


class Model:
    """One estimator bound to one panel (y: treated log series, x: donor log series by row).

    `fit(values, rows)` returns the gap series: values minus the fitted control
    and intercept, where weights (sc only) and intercept are fitted on `rows`.
    """

    def __init__(self, y: list, x: list, mode: str):
        if mode not in MODES:
            raise ValueError(f"unknown estimator {mode!r}")
        self.y, self.x, self.mode = y, x, mode
        self.t = len(y)
        self.k = len(x[0])
        self._fitters: dict = {}
        self._fixed = fixed_control(x, mode) if mode != "sc" else None

    def _fitter(self, rows: tuple):
        if rows not in self._fitters:
            means = [_mean([self.x[t][j] for t in rows]) for j in range(self.k)]
            centred = [[self.x[t][j] - means[j] for j in range(self.k)] for t in rows]
            self._fitters[rows] = (SimplexFitter(centred), means)
        return self._fitters[rows]

    def fit(self, values: list, rows: tuple) -> dict:
        if self.mode == "sc":
            fitter, means = self._fitter(rows)
            v_mean = _mean([values[t] for t in rows])
            weights = fitter.solve([values[t] - v_mean for t in rows])
            control = [math.fsum(w * self.x[t][j] for j, w in enumerate(weights)) for t in range(self.t)]
        else:
            weights = None
            control = self._fixed
        diff = [values[t] - control[t] for t in range(self.t)]
        intercept = _mean([diff[t] for t in rows])
        return {"weights": weights, "intercept": intercept, "control": control, "gap": [d - intercept for d in diff]}

    def event(self, n_pre: int) -> dict:
        """Fit on the first n_pre rows; the estimate is the mean gap over the remaining rows, in log points."""
        fitted = self.fit(self.y, tuple(range(n_pre)))
        gap = fitted["gap"]
        pre_rmse, post_rmse = _rms(gap[:n_pre]), _rms(gap[n_pre:])
        return {
            "weights": fitted["weights"],
            "intercept": fitted["intercept"],
            "control_plus_intercept": [c + fitted["intercept"] for c in fitted["control"]],
            "gap": gap,
            "estimate_log": _mean(gap[n_pre:]),
            "pre_rmse": pre_rmse,
            "post_rmse": post_rmse,
            "rmse_ratio": post_rmse / pre_rmse if pre_rmse > 0 else None,
        }

    def p_value(self, n_pre: int, theta: float) -> float:
        """Permutation p-value for the hypothesis that the post-event shift is `theta` log points.

        If the hypothesis is true, the series with `theta` taken out of the
        post rows has no break. The model is therefore refitted on all rows of
        that series, and the mean of the last n_post residuals is compared with
        the same mean after each cyclic shift of the residuals. The p-value is
        the share of shifts, the unshifted one included, whose absolute mean is
        at least as large.
        """
        n_post = self.t - n_pre
        adjusted = [self.y[t] - (theta if t >= n_pre else 0.0) for t in range(self.t)]
        resid = self.fit(adjusted, tuple(range(self.t)))["gap"]
        observed = abs(math.fsum(resid[-n_post:])) / n_post
        hits = 0
        doubled = resid + resid
        for shift in range(self.t):
            stat = abs(math.fsum(doubled[shift + self.t - n_post: shift + self.t])) / n_post
            if stat >= observed - P_TOL:
                hits += 1
        return hits / self.t

    def interval(self, n_pre: int, grid: list, level: float) -> dict:
        """The values of theta on the grid that are not rejected at 1 - level.

        Reported ends are one grid step outside the smallest and largest
        accepted value, because the true ends lie between an accepted and a
        rejected grid point. The result says whether the accepted values touch
        an edge of the grid (the interval is then not determined) and whether
        they form one unbroken run.
        """
        alpha = 1.0 - level
        p_values = [self.p_value(n_pre, theta) for theta in grid]
        accepted = [i for i, p in enumerate(p_values) if p > alpha + P_TOL]
        p_zero = self.p_value(n_pre, 0.0)
        if not accepted:
            return {"determined": False, "empty": True, "lo_log": None, "hi_log": None, "p_zero": p_zero,
                    "touches_lower_edge": False, "touches_upper_edge": False, "contiguous": True,
                    "accepted": 0, "theta_p_max": None, "p_max": max(p_values)}
        lo_i, hi_i = accepted[0], accepted[-1]
        touches_lo, touches_hi = lo_i == 0, hi_i == len(grid) - 1
        best = max(p_values)
        plateau = [i for i, p in enumerate(p_values) if p >= best - P_TOL]
        return {
            "determined": not (touches_lo or touches_hi),
            "empty": False,
            "lo_log": grid[max(lo_i - 1, 0)],
            "hi_log": grid[min(hi_i + 1, len(grid) - 1)],
            "p_zero": p_zero,
            "touches_lower_edge": touches_lo,
            "touches_upper_edge": touches_hi,
            "contiguous": len(accepted) == hi_i - lo_i + 1,
            "accepted": len(accepted),
            "theta_p_max": grid[plateau[len(plateau) // 2]],
            "p_max": best,
        }


def theta_grid(lo: float, hi: float, step: float) -> list:
    """Evenly spaced grid that contains 0.0 exactly."""
    k_lo = int(math.ceil(lo / step - 1e-9))
    k_hi = int(math.floor(hi / step + 1e-9))
    return [k * step for k in range(k_lo, k_hi + 1)]


def to_pct(log_points):
    """A difference in log points as a percent change."""
    return None if log_points is None else (math.exp(log_points) - 1.0) * 100.0


def slope(values: list) -> float:
    """Least-squares slope of the values against 0, 1, 2, ..."""
    n = len(values)
    mx, my = (n - 1) / 2.0, _mean(values)
    return math.fsum((i - mx) * (v - my) for i, v in enumerate(values)) / math.fsum((i - mx) ** 2 for i in range(n))

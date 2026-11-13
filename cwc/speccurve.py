"""Specification curve: the same estimate under every declared combination of
event date, window, donor set and estimator, so a reader can see how much the
answer depends on analysis choices.

Two rules keep the curve honest. A specification is "clean" only if no peer has
an outage inside its window; the others are shown but do not count toward the
decision rule. And two donor sets that end up with the same valid donors in the
same window are one specification, not two.
"""
from __future__ import annotations

import datetime as dt
import math

from . import data, synth

ESTIMATOR_NAMES = {"sc": "synthetic control", "equal": "equal-weight difference", "pooled": "pooled-volume difference"}


def donor_sets(peers: list, candidates: list) -> list:
    """Named donor sets in a fixed order: (label, list of series keys)."""
    keys = [p["key"] for p in peers]
    sets = [("all peers", keys)]
    sets.append(("swap protocols only", [p["key"] for p in peers if p.get("group") == "protocol"]))
    sets.append(("bridge aggregators only", [p["key"] for p in peers if p.get("group") == "aggregator"]))
    for p in peers:
        sets.append((f"without {p['name']}", [k for k in keys if k != p["key"]]))
    sets.append(("peers plus excluded candidates", keys + [c["key"] for c in candidates]))
    return sets


def build_panel(treated: dict, donors: dict, keys: list, start: dt.date, n_weeks: int, min_days: int, changes: dict):
    """Log weekly series for the treated unit and for the valid donors among `keys`.

    A donor is valid when its weekly volume is defined in every week of the
    window and no declared definition change falls inside the window. Returns
    (y, x, used keys), or None if the treated unit has an undefined week or no
    donor is valid.
    """
    end = start + n_weeks * data.ONE_WEEK
    y_raw = data.weekly_series(treated, start, n_weeks, min_days)
    if any(v is None for v in y_raw):
        return None
    columns, used = [], []
    for key in keys:
        change = changes.get(key)
        if change is not None and start < change < end:
            continue
        col = data.weekly_series(donors[key], start, n_weeks, min_days)
        if all(v is not None for v in col):
            columns.append([math.log(v) for v in col])
            used.append(key)
    if not used:
        return None
    x = [[col[t] for col in columns] for t in range(n_weeks)]
    return [math.log(v) for v in y_raw], x, used


def window_is_clean(peer_outages: dict, start: dt.date, end: dt.date) -> bool:
    return not any(data.overlaps(run, start, end) for runs in peer_outages.values() for run in runs)


def summary(rows: list, band: float) -> dict:
    if not rows:
        return {"count": 0}
    values = sorted(r["estimate_pct"] for r in rows)
    n = len(values)
    median = values[n // 2] if n % 2 else 0.5 * (values[n // 2 - 1] + values[n // 2])
    return {
        "count": n,
        "median_pct": median,
        "min_pct": values[0],
        "max_pct": values[-1],
        "share_within_band": sum(1 for v in values if -band <= v <= band) / n,
        "share_below_band": sum(1 for v in values if v < -band) / n,
        "share_above_band": sum(1 for v in values if v > band) / n,
    }


def run(near_volume: dict, series: dict, peers: list, candidates: list, changes: dict,
        peer_outages: dict, last_week_end: dt.date, cfg: dict) -> dict:
    spec = cfg["spec_curve"]
    band = 100.0 * cfg["strict_band"]
    events = [dt.date.fromisoformat(cfg["event_date"])] + [dt.date.fromisoformat(d) for d in cfg["alt_event_dates"]]
    sets = donor_sets(peers, candidates)
    rows = []
    counts = {"planned": 0, "beyond_data": 0, "too_few_donors": 0, "duplicate_donor_set": 0, "too_many_donors_for_sc": 0}
    for event in events:
        for pre in spec["pre_weeks"]:
            for post in spec["post_weeks"]:
                start = event - pre * data.ONE_WEEK
                end = event + post * data.ONE_WEEK
                counts["planned"] += len(sets) * len(synth.MODES)
                if end - data.ONE_DAY > last_week_end:
                    counts["beyond_data"] += len(sets) * len(synth.MODES)
                    continue
                clean = window_is_clean(peer_outages, start, end)
                seen: dict = {}
                for label, keys in sets:
                    panel = build_panel(near_volume, series, keys, start, pre + post, cfg["min_days_per_week"], changes)
                    if panel is None or len(panel[2]) < spec["min_donors"]:
                        counts["too_few_donors"] += len(synth.MODES)
                        continue
                    y, x, used = panel
                    signature = tuple(sorted(used))
                    if signature in seen:
                        counts["duplicate_donor_set"] += len(synth.MODES)
                        for row in seen[signature]:
                            row["same_as"].append(label)
                        continue
                    seen[signature] = []
                    for mode in synth.MODES:
                        if mode == "sc" and len(used) > spec["max_donors_exact"]:
                            counts["too_many_donors_for_sc"] += 1
                            continue
                        estimate = synth.to_pct(synth.Model(y, x, mode).event(pre)["estimate_log"])
                        row = {
                            "event_date": event.isoformat(),
                            "pre_weeks": pre,
                            "post_weeks": post,
                            "clean": clean,
                            "donor_set": label,
                            "same_as": [],
                            "donors": len(used),
                            "estimator": ESTIMATOR_NAMES[mode],
                            "estimate_pct": estimate,
                            "primary": (event.isoformat() == cfg["event_date"] and pre == cfg["pre_weeks"]
                                        and post == cfg["post_weeks"] and label == "all peers" and mode == "sc"),
                        }
                        rows.append(row)
                        seen[signature].append(row)
    rows.sort(key=lambda r: (r["estimate_pct"], r["event_date"], r["pre_weeks"], r["post_weeks"], r["donor_set"], r["estimator"]))
    clean_rows = [r for r in rows if r["clean"]]
    counts["run"] = len(rows)
    return {
        "rows": rows,
        "counts": counts,
        "all": summary(rows, band),
        "clean": summary(clean_rows, band),
        "not_clean": summary([r for r in rows if not r["clean"]], band),
        "clean_by_estimator": {name: summary([r for r in clean_rows if r["estimator"] == name], band) for name in ESTIMATOR_NAMES.values()},
        "clean_by_event_date": {e.isoformat(): summary([r for r in clean_rows if r["event_date"] == e.isoformat()], band) for e in events},
    }

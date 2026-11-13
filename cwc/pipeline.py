"""Build every number the project reports, in one pass, from the committed snapshot.

`build_findings(root)` returns one dictionary. Nothing else in the project
computes a result: the thesis text, the README block and the charts only format
what is in this dictionary. No clock, random number or network call is used.
"""
from __future__ import annotations

import datetime as dt
import math

from . import __version__, data, metrics, partners, pool, speccurve, synth, verdict

Date = dt.date
WEEK = data.ONE_WEEK
DAY = data.ONE_DAY


def daily_from(series: dict, through: Date):
    """Earliest day from which the series is positive on every day up to `through`."""
    day = through
    if series.get(day, 0.0) <= 0:
        return None
    while series.get(day - DAY, 0.0) > 0:
        day -= DAY
    return day


def interval_pct(interval: dict) -> dict:
    out = dict(interval)
    out["lo_pct"] = synth.to_pct(interval["lo_log"])
    out["hi_pct"] = synth.to_pct(interval["hi_log"])
    out["theta_p_max_pct"] = synth.to_pct(interval["theta_p_max"])
    return out


def load(root, cfg: dict) -> dict:
    key = lambda measure: data.series_key(cfg, measure)
    near = {
        "volume": data.load_daily(root, key("volume")),
        "fees": data.load_daily(root, key("fees")),
        "revenue": data.load_daily(root, key("revenue")),
        "holders": data.load_daily(root, key("holders_revenue")),
    }
    labelled = data.load_labelled(root, key("revenue_by_label"))
    names = cfg["labels"]
    unknown = sorted(set(labelled) - set(names.values()))
    if unknown:
        raise data.SnapshotError(f"revenue has labels this analysis does not know: {unknown}")
    near["front_end"] = labelled.get(names["front_end"], {})
    near["other"] = labelled.get(names["other"], {})
    worst = max(abs(value - near["front_end"].get(day, 0.0) - near["other"].get(day, 0.0)) for day, value in near["revenue"].items())
    if worst > 2.0:
        raise data.SnapshotError(f"revenue by label does not add up to total revenue (largest daily difference ${worst:.2f})")
    near["front_end_earned"] = data.accrue(near["front_end"], near["fees"])
    peers = data.series_with_role(cfg, "peer")
    candidates = data.series_with_role(cfg, "candidate")
    series = {s["key"]: data.load_daily(root, s["key"]) for s in peers + candidates}
    return {
        "near": near,
        "peers": peers,
        "candidates": candidates,
        "series": series,
        "peer_series": {s["key"]: series[s["key"]] for s in peers},
        "names": {s["key"]: s["name"] for s in cfg["series"]},
        "changes": {s["key"]: Date.fromisoformat(s["definition_change"]) for s in cfg["series"] if s.get("definition_change")},
    }


def event_test(ctx: dict, cfg: dict, event: Date, pre: int, post: int, grid: list, full: bool) -> dict:
    """The comparison of NEAR Intents with its peers around one event date and window choice."""
    start = event - pre * WEEK
    panel = speccurve.build_panel(ctx["near"]["volume"], ctx["series"], [p["key"] for p in ctx["peers"]],
                                  start, pre + post, cfg["min_days_per_week"], ctx["changes"])
    if panel is None:
        return {"defined": False}
    y, x, used = panel
    out = {
        "defined": True,
        "event_date": event.isoformat(),
        "pre_weeks": pre,
        "post_weeks": post,
        "start": start.isoformat(),
        "end": (event + post * WEEK - DAY).isoformat(),
        "donors": [ctx["names"][k] for k in used],
        "estimators": {},
    }
    modes = synth.MODES if full else ("sc",)
    for mode in modes:
        model = synth.Model(y, x, mode)
        ev = model.event(pre)
        result = {
            "estimate_pct": synth.to_pct(ev["estimate_log"]),
            "estimate_log": ev["estimate_log"],
            "pre_rmse_log": ev["pre_rmse"],
            "post_rmse_log": ev["post_rmse"],
            "rmse_ratio": ev["rmse_ratio"],
            "interval": interval_pct(model.interval(pre, grid, cfg["interval_level"])),
        }
        if full:
            hold = cfg["backtest_holdout_weeks"]
            back = synth.Model(y[:pre], x[:pre], mode).event(pre - hold)
            result["backtest"] = {
                "fit_weeks": pre - hold,
                "holdout_weeks": hold,
                "pseudo_event_date": (event - hold * WEEK).isoformat(),
                "pseudo_effect_pct": synth.to_pct(back["estimate_log"]),
                "holdout_rmse_log": back["post_rmse"],
                "within_band": abs(synth.to_pct(back["estimate_log"])) <= 100.0 * cfg["strict_band"],
            }
        if mode == "sc":
            result["weights"] = {ctx["names"][k]: w for k, w in zip(used, ev["weights"])}
            if full:
                gap = ev["gap"]
                half = post // 2
                result["weeks"] = [{
                    "week": (start + t * WEEK).isoformat(),
                    "period": "before" if t < pre else "after",
                    "near_usd_per_day": math.exp(y[t]) / 7.0,
                    "basket_usd_per_day": math.exp(ev["control_plus_intercept"][t]) / 7.0,
                    "gap_pct": synth.to_pct(gap[t]),
                } for t in range(pre + post)]
                result["gap_first_part_pct"] = synth.to_pct(math.fsum(gap[pre:pre + half]) / half)
                result["gap_second_part_pct"] = synth.to_pct(math.fsum(gap[pre + half:]) / (post - half))
                result["gap_first_part_weeks"] = half
                result["gap_second_part_weeks"] = post - half
                result["gap_last_three_weeks_pct"] = synth.to_pct(math.fsum(gap[-3:]) / 3.0)
                result["gap_slope_log_per_week"] = synth.slope(gap[pre:])
        out["estimators"][mode] = result
    return out


def placebo(ctx: dict, cfg: dict, event: Date, pre: int, post: int, grid: list, near_result: dict) -> dict:
    """Run the same test on each peer, none of which had the fee switch, with the other peers as donors."""
    start = event - pre * WEEK
    rows = []
    for peer in ctx["peers"]:
        others = [p["key"] for p in ctx["peers"] if p["key"] != peer["key"]]
        panel = speccurve.build_panel(ctx["series"][peer["key"]], ctx["series"], others, start, pre + post,
                                      cfg["min_days_per_week"], ctx["changes"])
        if panel is None or len(panel[2]) < cfg["spec_curve"]["min_donors"]:
            continue
        y, x, _used = panel
        model = synth.Model(y, x, "sc")
        ev = model.event(pre)
        interval = interval_pct(model.interval(pre, grid, cfg["interval_level"]))
        excludes_zero = bool(interval["determined"] and (interval["lo_pct"] > 0 or interval["hi_pct"] < 0))
        rows.append({
            "name": peer["name"],
            "estimate_pct": synth.to_pct(ev["estimate_log"]),
            "lo_pct": interval["lo_pct"],
            "hi_pct": interval["hi_pct"],
            "determined": interval["determined"],
            "excludes_zero": excludes_zero,
            "pre_rmse_log": ev["pre_rmse"],
            "rmse_ratio": ev["rmse_ratio"],
        })
    ratios = sorted([r["rmse_ratio"] for r in rows] + [near_result["rmse_ratio"]], reverse=True)
    fits = sorted([r["pre_rmse_log"] for r in rows] + [near_result["pre_rmse_log"]])
    return {
        "units": rows,
        "units_tested": len(rows),
        "intervals_excluding_zero": sum(1 for r in rows if r["excludes_zero"]),
        "near_rmse_ratio_rank": ratios.index(near_result["rmse_ratio"]) + 1,
        "near_pre_fit_rank": fits.index(near_result["pre_rmse_log"]) + 1,
        "units_ranked": len(rows) + 1,
    }


def build_findings(root) -> dict:
    cfg = data.load_config(root)
    manifest = data.verify_manifest(root, cfg)
    selection = pool.select(root, cfg)
    ctx = load(root, cfg)
    near, peer_series, names = ctx["near"], ctx["peer_series"], ctx["names"]

    event = Date.fromisoformat(cfg["event_date"])
    alt_events = [Date.fromisoformat(d) for d in cfg["alt_event_dates"]]
    pre, post = cfg["pre_weeks"], cfg["post_weeks"]
    pre_start, post_end = event - pre * WEEK, event + post * WEEK
    last_week = data.last_complete_week([near["volume"], near["fees"], near["revenue"]] + list(peer_series.values()))
    latest_end = last_week + WEEK
    latest_start = latest_end - cfg["latest_weeks"] * WEEK
    data_through = min(max(near[k]) for k in ("volume", "fees", "revenue"))
    band_pct = 100.0 * cfg["strict_band"]

    for name in ("volume", "fees"):
        gaps = data.missing_days(near[name], pre_start, latest_end)
        if gaps:
            raise data.SnapshotError(f"NEAR Intents {name} has {gaps} days without a value between {pre_start} and {latest_end}")

    # Peer outages and what they imply for the windows.
    scan_start = min([event] + alt_events) - max(cfg["spec_curve"]["pre_weeks"]) * WEEK
    peer_outages = {key: data.outages(series, scan_start, latest_end, cfg["outage_min_days"]) for key, series in peer_series.items()}
    longest_clean_post = 0
    while (event + (longest_clean_post + 1) * WEEK <= latest_end
           and speccurve.window_is_clean(peer_outages, pre_start, event + (longest_clean_post + 1) * WEEK)):
        longest_clean_post += 1
    outage_list = sorted(
        ({"name": names[key], **run} for key, runs in peer_outages.items() for run in runs),
        key=lambda r: (r["start"], r["name"]))

    # The three windows.
    windows = {
        "before": metrics.window(near, peer_series, pre_start, event),
        "after": metrics.window(near, peer_series, event, post_end),
        "latest": metrics.window(near, peer_series, latest_start, latest_end),
    }
    for label, (a, b) in {"before": (pre_start, event), "after": (event, post_end), "latest": (latest_start, latest_end)}.items():
        windows[label]["weeks"] = (b - a).days // 7
        windows[label]["peer_days_without_volume"] = sum(
            1 for series in peer_series.values() for day in data.days_between(a, b) if series.get(day, 0.0) <= 0)
        windows[label]["share_without"] = {names[k]: v for k, v in windows[label]["share_without"].items()}
        windows[label]["peer_volume_per_day"] = {names[k]: v for k, v in windows[label]["peer_volume_per_day"].items()}
    changes = {
        "after_vs_before": metrics.compare(windows["before"], windows["after"]),
        "latest_vs_before": metrics.compare(windows["before"], windows["latest"]),
    }

    # Dates the data themselves show.
    front_end_transfers = sorted(day for day, value in near["front_end"].items() if value > 0)
    front_end_daily = daily_from(near["front_end"], data_through)
    lumpy = [day for day in front_end_transfers if front_end_daily is None or day < front_end_daily]
    lumpy_gaps = [(b - a).days for a, b in zip(lumpy, lumpy[1:])]
    facts = {
        "holders_revenue_first_day": data.first_positive_day(near["holders"]).isoformat(),
        "revenue_daily_from": daily_from(near["revenue"], data_through).isoformat(),
        "other_revenue_daily_from": daily_from(near["other"], data_through).isoformat(),
        "front_end_revenue_daily_from": front_end_daily.isoformat() if front_end_daily else None,
        "front_end_transfers_before_daily": len(lumpy),
        "front_end_longest_gap_days": max(lumpy_gaps) if lumpy_gaps else 0,
        "front_end_transfers_in_before_window": sum(1 for day in front_end_transfers if pre_start <= day < event),
        "days_holders_revenue_differs_from_revenue_since_event": sum(
            1 for day, value in near["revenue"].items() if day >= event and abs(value - near["holders"].get(day, 0.0)) > 1.0),
    }

    # How the capture and take ratios depend on the choice of window.
    grid_rows = []
    for ev_date in [event] + alt_events:
        for p in cfg["spec_curve"]["pre_weeks"]:
            for q in cfg["spec_curve"]["post_weeks"]:
                a, b = ev_date - p * WEEK, ev_date + q * WEEK
                if b > latest_end or not speccurve.window_is_clean(peer_outages, a, b):
                    continue
                cmp_ = metrics.compare(metrics.window(near, peer_series, a, ev_date), metrics.window(near, peer_series, ev_date, b))
                grid_rows.append({
                    "event_date": ev_date.isoformat(), "pre_weeks": p, "post_weeks": q,
                    "capture_ratio_booked": cmp_["capture_ratio_booked"],
                    "capture_ratio_earned": cmp_["capture_ratio_earned"],
                    "take_ratio_booked": cmp_["take_ratio_booked"],
                    "take_ratio_earned": cmp_["take_ratio_earned"],
                    "fee_rate_ratio": cmp_["fee_rate_ratio"],
                    "break_even_pct": 100.0 * cmp_["break_even_change_earned"],
                })
    window_grid = {
        "rows": grid_rows,
        "count": len(grid_rows),
        "take_ratio_earned_min": min(r["take_ratio_earned"] for r in grid_rows),
        "take_ratio_earned_max": max(r["take_ratio_earned"] for r in grid_rows),
        "capture_ratio_booked_min": min(r["capture_ratio_booked"] for r in grid_rows),
        "capture_ratio_booked_max": max(r["capture_ratio_booked"] for r in grid_rows),
        "break_even_pct_smallest_loss": max(r["break_even_pct"] for r in grid_rows),
        "break_even_pct_largest_loss": min(r["break_even_pct"] for r in grid_rows),
    }

    # The event test, its checks, and the same test under other window choices.
    theta = cfg["theta_grid"]
    grid = synth.theta_grid(theta["min"], theta["max"], theta["step"])
    primary = event_test(ctx, cfg, event, pre, post, grid, full=True)
    sc = primary["estimators"]["sc"]
    break_even_pct = 100.0 * changes["after_vs_before"]["break_even_change_earned"]
    primary["break_even_pct"] = break_even_pct
    primary["estimate_inside_interval"] = bool(
        sc["interval"]["determined"] and sc["interval"]["lo_pct"] <= sc["estimate_pct"] <= sc["interval"]["hi_pct"])
    primary["lower_ends_pct"] = {mode: res["interval"]["lo_pct"] for mode, res in primary["estimators"].items()}
    primary["placebo"] = placebo(ctx, cfg, event, pre, post, grid, sc)

    robustness_rows = []
    for row in grid_rows:
        ev_date = Date.fromisoformat(row["event_date"])
        test = event_test(ctx, cfg, ev_date, row["pre_weeks"], row["post_weeks"], grid, full=False)
        res = test["estimators"]["sc"]
        determined = res["interval"]["determined"]
        holds = bool(determined and res["interval"]["lo_pct"] > row["break_even_pct"])
        robustness_rows.append({
            "event_date": row["event_date"], "pre_weeks": row["pre_weeks"], "post_weeks": row["post_weeks"],
            "estimate_pct": res["estimate_pct"], "lo_pct": res["interval"]["lo_pct"], "hi_pct": res["interval"]["hi_pct"],
            "determined": determined, "break_even_pct": row["break_even_pct"],
            "status": "holds" if holds else ("not determined" if not determined else "fails"),
            "loss_detected": bool(determined and res["interval"]["hi_pct"] < 0),
        })
    window_robustness = {
        "rows": robustness_rows,
        "count": len(robustness_rows),
        "holds": sum(1 for r in robustness_rows if r["status"] == "holds"),
        "not_determined": sum(1 for r in robustness_rows if r["status"] == "not determined"),
        "fails": sum(1 for r in robustness_rows if r["status"] == "fails"),
        "loss_detected": sum(1 for r in robustness_rows if r["loss_detected"]),
    }

    curve = speccurve.run(near["volume"], ctx["series"], ctx["peers"], ctx["candidates"], ctx["changes"],
                          peer_outages, latest_end - DAY, cfg)
    extended = [r for r in curve["rows"] if r["event_date"] == cfg["event_date"] and r["pre_weeks"] == pre
                and r["post_weeks"] == post and r["donor_set"] == "peers plus excluded candidates"
                and r["estimator"] == speccurve.ESTIMATOR_NAMES["sc"]]
    primary["with_excluded_candidates_pct"] = extended[0]["estimate_pct"] if extended else None
    primary["with_excluded_candidates_donors"] = extended[0]["donors"] if extended else None

    # The share rule, now and at the dated forward check.
    share_now = verdict.share_check(windows["latest"]["capture_earned"],
                                    changes["latest_vs_before"]["share_change_points_min"], cfg["share_check"])
    forward = verdict.forward_check(cfg["forward_check_date"], (latest_end - DAY).isoformat(), share_now)

    decision = verdict.decide(
        take_ratio_min=window_grid["take_ratio_earned_min"],
        interval=sc["interval"],
        break_even_pct=break_even_pct,
        estimate_pct=sc["estimate_pct"],
        clean_share_below_band=curve["clean"].get("share_below_band", 0.0),
        share_held=share_now["passed"],
        cfg=cfg,
    )
    written_for = cfg["written_for"]
    decision["prose_written_for"] = written_for
    decision["prose_matches"] = all(decision["claims"][k] == v for k, v in written_for.items())

    # Series for the charts.
    weekly = []
    week = pre_start
    while week < latest_end:
        w = metrics.window(near, peer_series, week, week + WEEK)
        weekly.append({
            "week": week.isoformat(),
            "volume_per_day": w["volume_per_day"],
            "peers_volume_per_day": w["peers_volume_per_day"],
            "share": w["share"],
            "capture_other": w["capture_other"],
            "capture_earned_front_end": w["capture_earned_front_end"],
            "capture_earned": w["capture_earned"],
            "fee_rate_bps": w["fee_rate_bps"],
        })
        week += WEEK
    trailing = []
    span = cfg["latest_weeks"] * WEEK
    end = event
    while end <= latest_end:
        w = metrics.window(near, peer_series, end - span, end)
        trailing.append({
            "window_end": (end - DAY).isoformat(),
            "capture_earned": w["capture_earned"],
            "capture_booked": w["capture_booked"],
            "capture_other": w["capture_other"],
            "capture_earned_front_end": w["capture_earned_front_end"],
            "fee_rate_bps": w["fee_rate_bps"],
            "take_earned_bps": w["take_earned_bps"],
            "volume_per_day": w["volume_per_day"],
            "revenue_earned_per_day": w["revenue_earned_per_day"],
            "share": w["share"],
        })
        end += WEEK

    # Partner by partner, from the stored sample of NEAR's own swap records (optional data).
    sample = partners.load(root, cfg)
    if sample is None:
        partner_view = {"available": False}
    else:
        partner_view = partners.analyse(
            sample, cfg,
            {"before": (pre_start, event), "after": (event, post_end), "latest": (latest_start, latest_end)},
            {name: windows[name]["volume_per_day"] for name in ("before", "after", "latest")})

    by_key = {entry["key"]: entry for entry in manifest["series"]}
    snapshot = [{
        "key": s["key"], "name": s["name"], "role": s["role"], "measure": s["measure"], "url": s["url"],
        "fetched_at_utc": by_key[s["key"]]["fetched_at_utc"], "sha256": by_key[s["key"]]["sha256"],
        "first_day": by_key[s["key"]].get("first_day"), "last_day": by_key[s["key"]].get("last_day"),
    } for s in cfg["series"]]

    return {
        "meta": {
            "version": __version__,
            "event_date": cfg["event_date"],
            "alt_event_dates": cfg["alt_event_dates"],
            "data_through": data_through.isoformat(),
            "last_complete_week_end": (latest_end - DAY).isoformat(),
            "snapshot_fetched_utc": max(e["fetched_at_utc"] for e in manifest["series"]),
            "manifest_sha256": data.sha256_file(root / "data" / "raw" / "MANIFEST.json"),
            "analysis_config_sha256": data.sha256_file(root / "config" / "analysis.json"),
            "series_config_sha256": data.sha256_file(root / "config" / "series.json"),
        },
        "config": {k: v for k, v in cfg.items() if k != "series"},
        "snapshot": snapshot,
        "peers": {
            "selection": selection,
            "definition_changes": pool.definition_changes(root, cfg),
            "outages": outage_list,
            "longest_clean_post_weeks": longest_clean_post,
            "post_window_is_longest_clean": longest_clean_post == post,
        },
        "facts": facts,
        "windows": windows,
        "changes": changes,
        "window_grid": window_grid,
        "event_test": primary,
        "window_robustness": window_robustness,
        "spec_curve": curve,
        "share_check": share_now,
        "forward_check": forward,
        "verdict": decision,
        "partners": partner_view,
        "series": {"weekly": weekly, "trailing": trailing},
    }


def rounded(obj, digits: int = 6):
    """Copy of a nested structure with every float rounded, so the JSON is stable across machines."""
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise ValueError("a result is not a finite number")
        value = round(obj, digits)
        return 0.0 if value == 0 else value
    if isinstance(obj, dict):
        return {str(k): rounded(v, digits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [rounded(v, digits) for v in obj]
    return obj

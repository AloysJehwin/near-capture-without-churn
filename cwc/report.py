"""Turn the findings into words: every figure quoted in THESIS.md, in the README
results block and on the dashboard is formatted here, from the findings only.

A template can use a figure only through a `{{name}}` placeholder that this
module defines. A placeholder it does not define stops the rebuild.
"""
from __future__ import annotations

import datetime as dt
import re

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
ESTIMATORS = {"sc": "synthetic control", "equal": "equal-weight difference", "pooled": "pooled-volume difference"}
START, END = "<!-- results:start -->", "<!-- results:end -->"


def n(value: float, digits: int = 1) -> str:
    text = f"{value:.{digits}f}"
    return text[1:] if text.startswith("-") and float(text) == 0 else text


def pct(value: float, digits: int = 1) -> str:
    return n(value, digits) + "%"


def signed(value: float, digits: int = 1) -> str:
    text = n(value, digits)
    return ("+" if not text.startswith("-") and float(text) != 0 else "") + text + "%"


def points(value: float, digits: int = 1) -> str:
    text = n(value, digits)
    return ("+" if not text.startswith("-") and float(text) != 0 else "") + text


def share(fraction: float, digits: int = 1) -> str:
    return pct(100.0 * fraction, digits)


def usd(value: float) -> str:
    if abs(value) >= 1e6:
        return "$" + n(value / 1e6, 1) + "M"
    return "$" + n(value / 1e3, 1) + "K"


def long_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def moved(ratio: float) -> str:
    change = 100.0 * (ratio - 1.0)
    return ("rose " if change >= 0 else "fell ") + pct(abs(change))


def pass_through(fee_ratio: float) -> str:
    change = 100.0 * (fee_ratio - 1.0)
    if abs(change) < 5.0:
        return f"The fee rate {moved(fee_ratio)}, so on average partners did not pass the cost on."
    if change > 0:
        return f"The fee rate {moved(fee_ratio)}: some of the cost reached users."
    return f"The fee rate {moved(fee_ratio)}: users paid less, not more."


def loss(value_pct: float) -> str:
    """A negative percent change written as a positive loss."""
    return pct(abs(value_pct))


def verdict_sentence(f: dict) -> str:
    v, et = f["verdict"], f["event_test"]
    sc = et["estimators"]["sc"]
    ch = f["changes"]["after_vs_before"]
    lead = (f"NEAR's take per $100 swapped rose from {n(f['windows']['before']['take_earned_bps'], 2)} to "
            f"{n(f['windows']['after']['take_earned_bps'], 2)} cents. Volume would have had to fall {loss(et['break_even_pct'])} to cancel that. ")
    reason = v["reason"]
    if reason == "cut_did_not_rise":
        return (f"NEAR's take per dollar swapped did not rise under every window choice "
                f"(lowest ratio {n(f['window_grid']['take_ratio_earned_min'], 2)}), so there is no increase to test.")
    if reason == "interval_not_determined":
        return lead + "The test could not put a bound on the volume change, so the claim is not supported."
    seen = (f"Against {len(et['donors'])} peers it changed by {signed(sc['estimate_pct'])} "
            f"({share(f['config']['interval_level'], 0)} interval {signed(sc['interval']['lo_pct'])} to {signed(sc['interval']['hi_pct'])}). ")
    if reason == "break_even_loss_not_ruled_out":
        return lead + seen + "A loss large enough to cancel the gain cannot be ruled out."
    if reason == "most_specifications_show_a_loss":
        return lead + seen + (f"Most alternative specifications show a loss of more than {pct(v['strict_band_pct'], 0)} "
                              f"({share(f['spec_curve']['clean']['share_below_band'], 0)} of them).")
    if reason == "share_check_failed":
        return lead + seen + "Since then NEAR has either given back its cut or lost more than the allowed share of the peer basket."
    if reason == "loss_detected_below_break_even":
        return lead + seen + "Volume fell against peers, but by less than the loss that would cancel the gain."
    if reason == "strict_form_holds":
        return lead + seen + f"A loss of more than {pct(v['strict_band_pct'], 0)} is ruled out."
    return lead + seen + f"The higher cut paid for itself. A loss of up to {pct(v['loss_bound_pct'])} cannot be ruled out."


def one_line(f: dict) -> str:
    v = f["verdict"]
    ch = f["changes"]["after_vs_before"]
    base = (f"in the {f['windows']['after']['weeks']} weeks after the fee switch NEAR's take per dollar swapped was "
            f"{n(ch['take_ratio_earned'], 2)}x its level before, the fee rate users pay {moved(ch['fee_rate_ratio'])}, "
            f"and NEAR Intents' share of the peer basket went from "
            f"{share(f['windows']['before']['share'])} to {share(f['windows']['after']['share'])}")
    if v["label"] == "NOT SUPPORTED":
        return base + ". The claim is not supported: " + v["reason"].replace("_", " ") + "."
    if v["claims"]["strict"]:
        return base + f". A volume loss of more than {pct(v['strict_band_pct'], 0)} is ruled out."
    return base + f". A volume loss of up to {pct(v['loss_bound_pct'])} cannot be ruled out; the loss that would cancel the gain is {loss(f['event_test']['break_even_pct'])}."


def weights_text(weights: dict) -> str:
    used = sorted(((w, name) for name, w in weights.items() if w >= 0.005), reverse=True)
    return ", ".join(f"{name} {pct(100 * w, 0)}" for w, name in used)


def facts(f: dict) -> dict:
    w, ch, et, v = f["windows"], f["changes"], f["event_test"], f["verdict"]
    b, a, l = w["before"], w["after"], w["latest"]
    ca, cl = ch["after_vs_before"], ch["latest_vs_before"]
    sc, eq, po = et["estimators"]["sc"], et["estimators"]["equal"], et["estimators"]["pooled"]
    curve, grid, rob, pl = f["spec_curve"], f["window_grid"], f["window_robustness"], et["placebo"]
    sel = f["peers"]["selection"]
    detected = [r for r in rob["rows"] if r["loss_detected"]]
    failed = [r for r in rob["rows"] if r["status"] == "fails"]
    runs = f["peers"]["outages"]
    first_start = min((r["start"] for r in runs), default=None)
    first_names = sorted(r["name"] for r in runs if r["start"] == first_start)
    if not first_names:
        outage_phrase = "no peer has an outage in the data"
    elif len(first_names) == 1:
        outage_phrase = f"{first_names[0]} reports no volume from {first_start}"
    else:
        outage_phrase = f"{', '.join(first_names[:-1])} and {first_names[-1]} report no volume from {first_start}"
    out = {
        "verdict_label": v["label"],
        "verdict_sentence": verdict_sentence(f),
        "one_line": one_line(f),
        "event_date": f["meta"]["event_date"],
        "event_date_long": long_date(f["meta"]["event_date"]),
        "alt_event_date": f["meta"]["alt_event_dates"][0],
        "data_through": f["meta"]["data_through"],
        "last_week_end": f["meta"]["last_complete_week_end"],
        "snapshot_fetched": f["meta"]["snapshot_fetched_utc"],
        "before_start": b["start"], "before_end": b["end"], "before_weeks": str(b["weeks"]),
        "after_start": a["start"], "after_end": a["end"], "after_weeks": str(a["weeks"]),
        "latest_start": l["start"], "latest_end": l["end"], "latest_weeks": str(l["weeks"]),
        # capture, fee rate, take
        "capture_before": share(b["capture_earned"], 2), "capture_after": share(a["capture_earned"], 2), "capture_latest": share(l["capture_earned"], 2),
        "capture_booked_before": share(b["capture_booked"], 2), "capture_booked_after": share(a["capture_booked"], 2),
        "other_before": share(b["capture_other"], 2), "other_after": share(a["capture_other"], 2), "other_latest": share(l["capture_other"], 2),
        "front_before": share(b["capture_earned_front_end"], 2), "front_after": share(a["capture_earned_front_end"], 2), "front_latest": share(l["capture_earned_front_end"], 2),
        "front_share_of_revenue_before": share(b["capture_earned_front_end"] / b["capture_earned"], 0),
        "fee_before": n(b["fee_rate_bps"], 1), "fee_after": n(a["fee_rate_bps"], 1), "fee_latest": n(l["fee_rate_bps"], 1),
        "take_before": n(b["take_earned_bps"], 2), "take_after": n(a["take_earned_bps"], 2), "take_latest": n(l["take_earned_bps"], 2),
        "take_booked_before": n(b["take_booked_bps"], 2), "take_booked_after": n(a["take_booked_bps"], 2),
        "volume_before": usd(b["volume_per_day"]), "volume_after": usd(a["volume_per_day"]), "volume_latest": usd(l["volume_per_day"]),
        "revenue_before": usd(b["revenue_earned_per_day"]), "revenue_after": usd(a["revenue_earned_per_day"]), "revenue_latest": usd(l["revenue_earned_per_day"]),
        "share_before": share(b["share"]), "share_after": share(a["share"]), "share_latest": share(l["share"]),
        # changes, after against before
        "take_ratio": n(ca["take_ratio_earned"], 2), "take_ratio_booked": n(ca["take_ratio_booked"], 2),
        "capture_ratio": n(ca["capture_ratio_earned"], 2), "capture_ratio_booked": n(ca["capture_ratio_booked"], 2),
        "break_even": loss(et["break_even_pct"]), "break_even_booked": loss(100 * ca["break_even_change_booked"]),
        "volume_moved_after": moved(ca["volume_ratio"]), "peers_moved_after": moved(ca["peers_volume_ratio"]),
        "fee_moved_after": moved(ca["fee_rate_ratio"]), "revenue_ratio_after": n(ca["revenue_ratio_earned"], 2),
        "share_change_after": points(ca["share_change_points"]["all"], 1),
        "share_change_after_min": points(ca["share_change_points_min"], 1), "share_change_after_max": points(ca["share_change_points_max"], 1),
        # changes, latest against before
        "capture_ratio_latest": n(cl["capture_ratio_earned"], 2), "take_ratio_latest": n(cl["take_ratio_earned"], 2),
        "volume_ratio_latest": n(cl["volume_ratio"], 2), "peers_ratio_latest": n(cl["peers_volume_ratio"], 2),
        "fee_ratio_latest": n(cl["fee_rate_ratio"], 2), "revenue_ratio_latest": n(cl["revenue_ratio_earned"], 2),
        "growth_from_capture": share(cl["split_share_of_growth"]["capture"], 0),
        "growth_from_volume": share(cl["split_share_of_growth"]["volume"], 0),
        "growth_from_fee_rate": share(cl["split_share_of_growth"]["fee_rate"], 0),
        "share_change_latest": points(cl["share_change_points"]["all"], 1),
        "share_change_latest_min": points(cl["share_change_points_min"], 1), "share_change_latest_max": points(cl["share_change_points_max"], 1),
        # window choices
        "grid_count": str(grid["count"]),
        "take_ratio_min": n(grid["take_ratio_earned_min"], 2), "take_ratio_max": n(grid["take_ratio_earned_max"], 2),
        "capture_ratio_booked_min": n(grid["capture_ratio_booked_min"], 2), "capture_ratio_booked_max": n(grid["capture_ratio_booked_max"], 2),
        "break_even_smallest": loss(grid["break_even_pct_smallest_loss"]), "break_even_largest": loss(grid["break_even_pct_largest_loss"]),
        # event test
        "estimate": signed(sc["estimate_pct"]), "interval_lo": signed(sc["interval"]["lo_pct"]), "interval_hi": signed(sc["interval"]["hi_pct"]),
        "p_zero": n(sc["interval"]["p_zero"], 2), "loss_bound": pct(v["loss_bound_pct"]) if v["loss_bound_pct"] is not None else "not determined",
        "fit_error": n(sc["pre_rmse_log"], 2), "fit_error_equal": n(eq["pre_rmse_log"], 2), "fit_error_pooled": n(po["pre_rmse_log"], 2),
        "weights": weights_text(sc["weights"]), "donor_count": str(len(et["donors"])),
        "estimate_equal": signed(eq["estimate_pct"]), "equal_lo": signed(eq["interval"]["lo_pct"]), "equal_hi": signed(eq["interval"]["hi_pct"]),
        "estimate_pooled": signed(po["estimate_pct"]), "pooled_lo": signed(po["interval"]["lo_pct"]), "pooled_hi": signed(po["interval"]["hi_pct"]),
        "backtest": signed(sc["backtest"]["pseudo_effect_pct"]), "backtest_equal": signed(eq["backtest"]["pseudo_effect_pct"]),
        "backtest_pooled": signed(po["backtest"]["pseudo_effect_pct"]), "backtest_date": sc["backtest"]["pseudo_event_date"],
        "backtest_fit_weeks": str(sc["backtest"]["fit_weeks"]), "backtest_holdout_weeks": str(sc["backtest"]["holdout_weeks"]),
        "gap_first": signed(sc["gap_first_part_pct"]), "gap_second": signed(sc["gap_second_part_pct"]), "gap_last_three": signed(sc["gap_last_three_weeks_pct"]),
        "gap_first_weeks": str(sc["gap_first_part_weeks"]), "gap_second_weeks": str(sc["gap_second_part_weeks"]),
        "with_candidates": signed(et["with_excluded_candidates_pct"]) if et["with_excluded_candidates_pct"] is not None else "not run",
        "with_candidates_donors": str(et["with_excluded_candidates_donors"] or ""),
        # checks on the method
        "placebo_excluding_zero": str(pl["intervals_excluding_zero"]), "placebo_units": str(pl["units_tested"]),
        "near_ratio_rank": str(pl["near_rmse_ratio_rank"]), "near_fit_rank": str(pl["near_pre_fit_rank"]), "units_ranked": str(pl["units_ranked"]),
        "rob_count": str(rob["count"]), "rob_holds": str(rob["holds"]), "rob_not_determined": str(rob["not_determined"]),
        "rob_fails": str(rob["fails"]), "rob_loss_detected": str(rob["loss_detected"]),
        "rob_failed_case": "; ".join(f"event {r['event_date']}, {r['pre_weeks']} weeks before, {r['post_weeks']} after: lower end {signed(r['lo_pct'])} against a break-even of -{loss(r['break_even_pct'])}" for r in failed) or "none",
        "rob_detected_case": "; ".join(f"event {r['event_date']}, {r['pre_weeks']} weeks before, {r['post_weeks']} after: {signed(r['lo_pct'])} to {signed(r['hi_pct'])}" for r in detected) or "none",
        # specification curve
        "curve_planned": str(curve["counts"]["planned"]), "curve_run": str(curve["counts"]["run"]),
        "curve_duplicates": str(curve["counts"]["duplicate_donor_set"]), "curve_too_few": str(curve["counts"]["too_few_donors"]),
        "curve_clean": str(curve["clean"]["count"]), "curve_median": signed(curve["clean"]["median_pct"]),
        "curve_min": signed(curve["clean"]["min_pct"]), "curve_max": signed(curve["clean"]["max_pct"]),
        "curve_within": share(curve["clean"]["share_within_band"], 0), "curve_below": share(curve["clean"]["share_below_band"], 1),
        "curve_above": share(curve["clean"]["share_above_band"], 0),
        "curve_not_clean": str(curve["not_clean"]["count"]),
        "curve_not_clean_median": signed(curve["not_clean"]["median_pct"]) if curve["not_clean"]["count"] else "n/a",
        "curve_sc_median": signed(curve["clean_by_estimator"]["synthetic control"]["median_pct"]),
        "curve_equal_median": signed(curve["clean_by_estimator"]["equal-weight difference"]["median_pct"]),
        "curve_pooled_median": signed(curve["clean_by_estimator"]["pooled-volume difference"]["median_pct"]),
        # share rule and forward check
        "share_floor": share(f["share_check"]["capture_floor"], 0), "share_drop_limit": n(f["share_check"]["max_share_drop_points"], 0),
        "share_check_result": "passes" if f["share_check"]["passed"] else "fails",
        "forward_date": f["forward_check"]["date"], "forward_status": f["forward_check"]["status"],
        # what the data show about dates and peers
        "holders_first_day": f["facts"]["holders_revenue_first_day"], "other_daily_from": f["facts"]["other_revenue_daily_from"],
        "front_daily_from": f["facts"]["front_end_revenue_daily_from"] or "not yet",
        "front_transfers_lumpy": str(f["facts"]["front_end_transfers_before_daily"]), "front_longest_gap": str(f["facts"]["front_end_longest_gap_days"]),
        "first_outage_phrase": outage_phrase,
        "longest_clean_post": str(f["peers"]["longest_clean_post_weeks"]),
        "universe_entries": str(sel["universe_entries"]), "size_rule": "$" + n(sel["min_trailing_year_volume_usd"] / 1e9, 0) + " billion",
        "history_rule_weeks": str(sel["min_history_weeks_before_event"]),
        "peer_count": str(len(et["donors"])),
        "basket_count": str(len(b["peer_volume_per_day"])),
        "interval_margin": n(sc["interval"]["lo_pct"] - et["break_even_pct"], 1) if sc["interval"]["determined"] else "n/a",
        "curve_margin": n(curve["clean"]["min_pct"] - et["break_even_pct"], 1),
        "pass_through_sentence": pass_through(ca["fee_rate_ratio"]),
        "pooled_break_even_phrase": ("Its interval reaches past the break-even loss" if po["interval"]["determined"] and po["interval"]["lo_pct"] <= et["break_even_pct"]
                                     else "Its interval stops short of the break-even loss" if po["interval"]["determined"] else "Its interval could not be determined"),
        "fit_rank_phrase": f"ranks {pl['near_pre_fit_rank']} of {pl['units_ranked']} (1 is the closest fit)",
        "strict_band": pct(v["strict_band_pct"], 0), "kill_share": share(f["config"]["kill_share"], 0),
        "interval_level": share(f["config"]["interval_level"], 0),
        "manifest_sha": f["meta"]["manifest_sha256"][:16], "config_sha": f["meta"]["analysis_config_sha256"][:16],
    }
    out.update(tables(f))
    return out


def table(header: list, rows: list) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def tables(f: dict) -> dict:
    w = f["windows"]
    cols = [w["before"], w["after"], w["latest"]]
    windows = table(
        ["", f"{w['before']['weeks']} weeks before", f"{w['after']['weeks']} weeks after", f"latest {w['latest']['weeks']} weeks"],
        [
            ["Dates"] + [f"{x['start']} to {x['end']}" for x in cols],
            ["Swap volume per day"] + [usd(x["volume_per_day"]) for x in cols],
            ["Fees users paid per $100 swapped (cents)"] + [n(x["fee_rate_bps"], 1) for x in cols],
            ["Share of fees NEAR kept"] + [share(x["capture_earned"], 2) for x in cols],
            ["- from partner fees and other"] + [share(x["capture_other"], 2) for x in cols],
            ["- from its own front end"] + [share(x["capture_earned_front_end"], 2) for x in cols],
            ["NEAR's take per $100 swapped (cents)"] + [n(x["take_earned_bps"], 2) for x in cols],
            ["NEAR's revenue per day"] + [usd(x["revenue_earned_per_day"]) for x in cols],
            ["NEAR Intents' share of the peer basket"] + [share(x["share"]) for x in cols],
        ])
    et = f["event_test"]
    estimators = table(
        ["Estimator", "Volume change", "90% interval", "Fit error before (log points)", "Backtest (should be 0)"],
        [[ESTIMATORS[m], signed(r["estimate_pct"]),
          f"{signed(r['interval']['lo_pct'])} to {signed(r['interval']['hi_pct'])}" if r["interval"]["determined"] else "not determined",
          n(r["pre_rmse_log"], 2), signed(r["backtest"]["pseudo_effect_pct"])] for m, r in et["estimators"].items()])
    sel = f["peers"]["selection"]
    peers = table(
        ["Service", "Kind", "Used as a peer", "Reason if not"],
        [[p["name"], "swap protocol", "yes", ""] for p in sel["protocols"]]
        + [[r["name"], "bridge aggregator", "yes" if r["status"] == "peer" else "no", r["reason"]] for r in sel["aggregators"]])
    placebo = table(
        ["Unit treated as if it had the switch", "Estimate", "90% interval", "Interval excludes zero"],
        [[u["name"], signed(u["estimate_pct"]), f"{signed(u['lo_pct'])} to {signed(u['hi_pct'])}", "yes" if u["excludes_zero"] else "no"]
         for u in et["placebo"]["units"]])
    return {"table_windows": windows, "table_estimators": estimators, "table_peers": peers, "table_placebo": placebo}


def fill(template: str, values: dict) -> str:
    def replace(match):
        name = match.group(1)
        if name not in values:
            raise KeyError(f"template uses {{{{{name}}}}}, which cwc/report.py does not define")
        return values[name]
    return re.sub(r"\{\{([a-z0-9_]+)\}\}", replace, template)


def banner(f: dict) -> str:
    if f["verdict"]["prose_matches"]:
        return ""
    return ("> **Read this first.** The numbers in this file were rebuilt and the outcome of the tests changed. "
            "The verdict line and every figure are current. The explanatory sentences were written for a different outcome "
            "and may no longer fit. See `verdict.claims` in `out/findings.json`.\n\n")


def render_thesis(f: dict, template: str) -> str:
    values = facts(f)
    values["banner"] = banner(f)
    return fill(template, values)


def readme_block(f: dict) -> str:
    v = facts(f)
    lines = [
        START,
        f"**Verdict: {v['verdict_label']}.** {v['verdict_sentence']}",
        "",
        banner(f).strip(),
        "",
        "| What | Value |",
        "| --- | --- |",
        f"| NEAR's take per $100 swapped, {v['before_weeks']} weeks before the switch | {v['take_before']} cents |",
        f"| NEAR's take per $100 swapped, {v['after_weeks']} weeks after | {v['take_after']} cents ({v['take_ratio']}x) |",
        f"| Volume loss that would cancel the gain (break-even) | {v['break_even']} |",
        f"| Volume change against {v['peer_count']} peers | {v['estimate']} ({v['interval_level']} interval {v['interval_lo']} to {v['interval_hi']}) |",
        f"| Largest loss the data cannot rule out | {v['loss_bound']} |",
        f"| Fee users paid per $100 swapped, before and after | {v['fee_before']} and {v['fee_after']} cents |",
        f"| NEAR Intents' share of the peer basket: before, after, latest | {v['share_before']}, {v['share_after']}, {v['share_latest']} |",
        f"| Share of fees NEAR kept in the latest {v['latest_weeks']} weeks | {v['capture_latest']} ({v['capture_ratio_latest']}x the level before) |",
        f"| Clean specifications run | {v['curve_clean']} (median {v['curve_median']}, range {v['curve_min']} to {v['curve_max']}) |",
        "",
        "![Volume change against peers with the break-even loss](docs/charts/ruler.svg)",
        "",
        "![Share of fees that reached NEAR, by week and source](docs/charts/capture.svg)",
        "",
        "![NEAR Intents' share of the peer basket by week](docs/charts/share.svg)",
        "",
        f"Data through {v['data_through']}. Snapshot fetched {v['snapshot_fetched']}. All figures are written by `python3 -m cwc rebuild`.",
        END,
    ]
    return "\n".join(line for i, line in enumerate(lines) if not (line == "" and i > 0 and lines[i - 1] == ""))


def render_readme(f: dict, readme: str) -> str:
    if START not in readme or END not in readme:
        raise KeyError("README.md has lost its results markers")
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    return head + readme_block(f) + tail

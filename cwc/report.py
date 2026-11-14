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
    out.update({k: v for k, v in partner_facts(f).items() if isinstance(v, str)})
    return out


def listed(names: list) -> str:
    if not names:
        return "none"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def ratio(value, digits: int = 2) -> str:
    return "n/a" if value is None else n(value, digits) + "x"


def partner_facts(f: dict) -> dict:
    """Everything the texts say about single partner apps. All of it is generated, because all of it depends on the sample."""
    p = f["partners"]
    if not p["available"]:
        return {
            "partners_available": "",
            "partner_section": ("This copy of the repository has no sample of NEAR's swap records, so there is nothing to report here. "
                                "`scripts/explorer_sample.py` takes one. It needs a partner key for NEAR's Explorer API."),
            "partner_gap_bullet": ("**Which partners stayed.** Total volume can hold up while individual partners leave and others arrive. "
                                   "That needs swap-level data from NEAR's Explorer API, which requires a partner key."),
            "partner_verdict_note": ("Partner-level evidence would also change it. If the largest partners from before the switch stopped sending swaps "
                                     "while new ones filled the gap, \"without churn\" would be the wrong name for what happened."),
            "partner_method_bullet": "**Partner sample.** None in this copy of the repository.",
            "partner_against_items": [],
            "partner_readme_rows": [],
        }
    w = p["windows"]
    b, a, l = w["before"], w["after"], w["latest"]
    ca, cl = f["changes"]["after_vs_before"], f["changes"]["latest_vs_before"]
    top = p["top_count"]
    cents = lambda bps: n(bps, 1)
    hours = listed([f"{h:02d}:00" for h in p["hours_utc"]])
    se_after = p["top_after_over_before_se_log"]
    se_text = f"about {pct(100 * (2.718281828459045 ** se_after - 1), 0)} either way" if se_after is not None else "not available"
    gone, halved = p["top_gone_after"], p["top_halved_after"]
    gone_latest = p["top_gone_latest"]
    gone_limit = share(p["gone_below"], 0)
    table_rows = []
    for r in p["top_partners"]:
        fee_cell = lambda cell: "n/a" if cell["app_fee_bps"] is None else cents(cell["app_fee_bps"])
        table_rows.append([r["name"], share(r["share_of_partner_volume_before"], 1), usd(r["before"]["usd_per_day"]), usd(r["after"]["usd_per_day"]),
                           usd(r["latest"]["usd_per_day"]), ratio(r["after_over_before"]), ratio(r["latest_over_before"]),
                           f"{fee_cell(r['before'])}, {fee_cell(r['after'])}, {fee_cell(r['latest'])}"])
    partner_table = table(["Partner app", "Share of partner volume before", "Per day before", "Per day after", "Per day latest",
                           "After against before", "Latest against before", "App fee per $100 (cents): before, after, latest"], table_rows)
    if p["top_still_sending_latest"] == top:
        still = f"All {top} still appear in the sample in the latest window."
    else:
        still = f"{p['top_still_sending_latest']} of the {top} still appear in the sample in the latest window."
    if a["partner_app_fee_bps"] <= 1.05 * b["partner_app_fee_bps"]:
        fee_read = "Partners did not raise the fee they charge to make up for NEAR's share."
    else:
        fee_read = "Partners charged more after the switch."
    for_items = [
        f"The {top} largest partners together sent {ratio(p['top_after_over_before'])} their earlier volume per day after the switch and {ratio(p['top_latest_over_before'])} in the latest window. "
        f"NEAR Intents as a whole, in DefiLlama's data, was {ratio(ca['volume_ratio'])} and {ratio(cl['volume_ratio'])}; the peers together were {ratio(ca['peers_volume_ratio'])} and {ratio(cl['peers_volume_ratio'])}.",
        still,
        f"Partner apps sent {share(b['volume_share']['partner'], 0)} of the sampled volume before the switch, {share(a['volume_share']['partner'], 0)} after and {share(l['volume_share']['partner'], 0)} in the latest window.",
        f"Partner apps that do not appear in the sample before the switch sent {share(p['new_partner_share_of_partner_volume_latest'], 0)} of partner volume in the latest window.",
        f"The app fee partners charged was {cents(b['partner_app_fee_bps'])} cents per $100 before, {cents(a['partner_app_fee_bps'])} after and {cents(l['partner_app_fee_bps'])} latest. {fee_read}",
    ]
    against_items = []
    if gone or halved:
        against_items.append(
            f"**Some partners did leave.** Of the {top} largest before the switch, {len(halved)} sent less than half their earlier volume after it ({listed(halved)}), "
            f"and {len(gone)} of those less than {gone_limit} ({listed(gone)}). In the latest window {len(gone_latest)} {'is' if len(gone_latest) == 1 else 'are'} below {gone_limit} ({listed(gone_latest)}). "
            "The sample cannot say why a partner sent less.")
    if p["top_after_over_before"] is not None and p["top_after_over_before"] < 1:
        against_items.append(
            f"**The largest partners sent less after the switch.** {ratio(p['top_after_over_before'])} their earlier volume per day, with a sampling error of {se_text}. "
            f"NEAR Intents as a whole was {ratio(ca['volume_ratio'])} over the same weeks, so the partners did no worse than the total, but the total fell.")
    against_items.append(
        f"**The sample is not the whole of NEAR Intents.** It holds swaps made through the 1Click service, about {share(b['share_of_defillama_volume'], 0)} of DefiLlama's volume before the switch, "
        f"{share(a['share_of_defillama_volume'], 0)} after and {share(l['share_of_defillama_volume'], 0)} latest. It is taken at fixed hours ({hours} UTC), not all day. The partner name is the one the app declares.")
    against_items.append(
        f"**Most app fees in the sample are still addressed to the partner.** Of the app fees declared in the sampled swaps, {share(b['fee_share_to_near_partner_share_wallets'], 1)} named NEAR's fee-share wallets as the receiver before the switch, "
        f"{share(a['fee_share_to_near_partner_share_wallets'], 1)} after and {share(l['fee_share_to_near_partner_share_wallets'], 1)} latest. NEAR's documentation gives 50/50 as the default split. "
        "The field shows where a swap's app fee is addressed. It does not show what NEAR collects in other ways, so it is not a measure of the split.")
    g = p["fee_groups"]
    gw = g["without_largest"]
    big = (spec_names := f["config"]["partners"].get("display_names", {})).get(g["largest_charging_partner"], g["largest_charging_partner"])
    cut = n(g["min_fee_bps"], 0)
    err = lambda se: "n/a" if se is None else f"about {pct(100 * (2.718281828459045 ** se - 1), 0)} either way"
    group_row = lambda label, d: [label, str(d["partners"]), share(d["share_of_partner_volume_before"], 0), ratio(d["after_over_before"]), ratio(d["latest_over_before"])]
    fee_rows = [group_row(f"Charged an app fee of {cut} cents per $100 or more", g["charging"])]
    if gw:
        fee_rows.append(group_row(f"The same without the largest one ({big})", gw["charging"]))
    fee_rows.append(group_row("Charged less, or nothing", g["not_charging"]))
    fee_table = table(["Partner apps, by what they charged before the switch", "Apps", "Share of partner volume before", "After against before", "Latest against before"], fee_rows)
    cut_offs = "; ".join(f"at {n(c['min_fee_bps'], 0)} cent{'' if c['min_fee_bps'] == 1 else 's'}, {ratio(c['after_gap'])} with {big} and {ratio(c['after_gap_without_largest'])} without" for c in g["other_cut_offs"])
    fee_text = (
        "Only a partner that charges an app fee has a fee for NEAR to share. Partners that charge none are a comparison group inside NEAR Intents: same market, same weeks, no fee to lose. "
        f"After the switch the fee-charging group sent {ratio(g['charging']['after_over_before'])} its earlier volume per day and the others {ratio(g['not_charging']['after_over_before'])}, "
        f"a gap of {ratio(g['after_gap'])} (sampling error {err(g['after_gap_se_log'])}). "
        + (f"One app, {big}, is {share(g['largest_share_of_partner_volume_before'], 0)} of all partner volume. Without it the fee-charging group sent {ratio(gw['charging']['after_over_before'])}, "
           f"a gap of {ratio(gw['after_gap'])} to the others (sampling error {err(gw['after_gap_se_log'])}); in the latest window {ratio(gw['charging']['latest_over_before'])} against {ratio(g['not_charging']['latest_over_before'])}. " if gw else "")
        + f"With other cut-offs for \"charges a fee\" the gap after the switch is: {cut_offs}.")
    if g["after_gap"] is not None and g["after_gap"] >= 0.9:
        for_items.insert(1, f"Taken together, partners that charged an app fee did no worse after the switch than partners that charged none: {ratio(g['charging']['after_over_before'])} against {ratio(g['not_charging']['after_over_before'])}.")
    if gw and gw["after_gap"] is not None and gw["after_gap"] < 0.8:
        against_items.insert(0,
            f"**Apart from {big}, the partners with a fee to share fell behind.** Fee-charging partners other than {big} sent {ratio(gw['charging']['after_over_before'])} their earlier volume after the switch, "
            f"while partners with no fee to share sent {ratio(g['not_charging']['after_over_before'])}: a gap of {ratio(gw['after_gap'])}, with a sampling error of {err(gw['after_gap_se_log'])}. "
            f"In the latest window it is {ratio(gw['charging']['latest_over_before'])} against {ratio(g['not_charging']['latest_over_before'])}. "
            f"This is what leaving because of the fee switch would look like. The result for the whole group rests on {big} staying.")
    body = "\n\n".join([
        f"DefiLlama gives totals. NEAR's Explorer API lists single swaps and names the partner app that sent each one. It needs a partner key, so this repository stores a sample taken with one: "
        f"{p['swaps']:,} successful swaps in {p['blocks']} blocks, each block up to 1,000 swaps in a row ending at a fixed hour ({hours} UTC) on each day from {p['first_day']} to {p['last_day']}. "
        "Only totals per partner app are stored. No user address and no single swap is stored. This evidence stands beside the rules in section 7; it does not enter the verdict.",
        partner_table,
        "Volume per day is the dollars in a window's blocks divided by the time those blocks span.",
        "![The largest partner apps before the fee switch, in three windows](docs/charts/partners.svg)",
        "**Did the partners with a fee to share do worse?**",
        fee_text,
        fee_table,
        "**What it shows for the thesis**",
        "\n".join("* " + item for item in for_items),
        "**What it shows against**",
        "\n".join("* " + item for item in against_items),
    ])
    return {
        "partners_available": "yes",
        "partner_section": body,
        "partner_gap_bullet": "**Why a partner sent less.** Section 5 shows which partner apps sent less after the switch. It cannot show whether the fee switch was the reason.",
        "partner_verdict_note": (
            "Partner-level evidence is in section 5. It is not part of the rules, because it is a sample that others cannot retake without a key. "
            f"If the largest partners from before the switch had stopped sending swaps while new ones filled the gap, \"without churn\" would be the wrong name for what happened. "
            f"In the sample the {top} largest together sent {ratio(p['top_after_over_before'])} their earlier volume after the switch and {ratio(p['top_latest_over_before'])} latest, and {len(gone)} of them fell below {gone_limit}. "
            + (f"Fee-charging partners other than {big} sent {ratio(gw['charging']['after_over_before'])} against {ratio(g['not_charging']['after_over_before'])} for partners with no fee to share, "
               "which is churn among the smaller partners that the totals hide." if gw and gw["after_gap"] is not None and gw["after_gap"] < 0.8 else "")),
        "partner_method_bullet": (
            f"**Partner sample.** `scripts/explorer_sample.py` asks NEAR's Explorer API for up to 1,000 successful swaps that end at each of the hours {hours} UTC on every day, and keeps totals per partner app and per fee account. "
            "The files are in `data/explorer/` with their SHA-256 in `data/explorer/MANIFEST.json`, and the rebuild stops if one does not match. Taking a new sample needs a partner key; rebuilding from the stored one does not. "
            f"NEAR's own apps are told apart from partners by {p['own_front_end_rule']}: {listed(['`' + name + '`' for name in p['own_front_end_referrals']])}. "
            f"The sampling error quoted for the largest partners comes from leaving out one day at a time."),
        "partner_against_items": against_items,
        "partner_for_items": for_items,
        "partner_table": partner_table,
        "partner_readme_rows": [
            f"| The {top} largest partner apps before the switch: volume per day after, and latest (sample of NEAR's swap records) | {ratio(p['top_after_over_before'])}, {ratio(p['top_latest_over_before'])} |",
            f"| Of those {top}, below {gone_limit} of their earlier volume after the switch | {len(gone)} ({listed(gone)}) |",
            f"| Fee-charging partners against partners with no fee, volume after the switch | {ratio(g['charging']['after_over_before'])} against {ratio(g['not_charging']['after_over_before'])} |",
            *([f"| The same without the largest partner ({big}) | {ratio(gw['charging']['after_over_before'])} against {ratio(g['not_charging']['after_over_before'])} |"] if gw else []),
        ],
        "partner_top_after": ratio(p["top_after_over_before"]), "partner_top_latest": ratio(p["top_latest_over_before"]),
        "partner_top_count": str(top), "partner_gone_count": str(len(gone)), "partner_gone_names": listed(gone),
        "partner_swaps": f"{p['swaps']:,}", "partner_blocks": str(p["blocks"]), "partner_hours": hours,
        "partner_first_day": p["first_day"], "partner_last_day": p["last_day"],
        "partner_coverage_before": share(b["share_of_defillama_volume"], 0),
    }


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
        *partner_facts(f)["partner_readme_rows"],
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

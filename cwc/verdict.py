"""The decision rules. Pure functions: numbers and thresholds in, one label out.

The rules are applied in a fixed order and the first one that fails decides, so
there is exactly one outcome for any set of numbers.

  1. The cut rose          NEAR's take per dollar swapped is higher after the
                           switch than before under every clean window choice.
  2. The test can decide   the interval for the volume change does not run off
                           the edge of the search grid.
  3. It paid for itself    the lower end of the interval is above the
                           break-even change.
  4. No wider sign of loss not (the estimate is below minus the strict band and
                           more than the kill share of the clean, distinct
                           specifications are below it too).
  5. Share held since      in the latest window capture is at least the floor
                           and NEAR's share of the peer basket is not more than
                           the allowed drop below its share before the switch,
                           whichever peer is left out.

If any of 1 to 5 fails the claim is NOT SUPPORTED. Otherwise:

  6. Loss detected         the whole interval is below zero: SUPPORTED IN PART.
  7. Strict form           the lower end is at or above minus the strict band:
                           SUPPORTED. Else SUPPORTED IN PART.
"""
from __future__ import annotations

SUPPORTED = "SUPPORTED"
SUPPORTED_IN_PART = "SUPPORTED IN PART"
NOT_SUPPORTED = "NOT SUPPORTED"


def share_check(capture_latest: float, share_change_min_points: float, rule: dict) -> dict:
    """Rule 5, also used for the dated forward check."""
    capture_ok = capture_latest >= rule["capture_floor"]
    share_ok = share_change_min_points >= -rule["max_share_drop_pp"]
    return {
        "capture_latest": capture_latest,
        "capture_floor": rule["capture_floor"],
        "capture_ok": capture_ok,
        "share_change_min_points": share_change_min_points,
        "max_share_drop_points": rule["max_share_drop_pp"],
        "share_ok": share_ok,
        "passed": capture_ok and share_ok,
    }


def decide(take_ratio_min: float, interval: dict, break_even_pct: float, estimate_pct: float,
           clean_share_below_band: float, share_held: bool, cfg: dict) -> dict:
    band = 100.0 * cfg["strict_band"]
    lo, hi = interval.get("lo_pct"), interval.get("hi_pct")
    determined = bool(interval.get("determined")) and lo is not None and hi is not None
    cut_rose = take_ratio_min > 1.0
    paid = determined and lo > break_even_pct
    kill = estimate_pct < -band and clean_share_below_band > cfg["kill_share"]
    loss_detected = determined and hi < 0.0
    strict = determined and lo >= -band
    loss_bound = max(0.0, -lo) if determined else None

    if not cut_rose:
        label, reason = NOT_SUPPORTED, "cut_did_not_rise"
    elif not determined:
        label, reason = NOT_SUPPORTED, "interval_not_determined"
    elif not paid:
        label, reason = NOT_SUPPORTED, "break_even_loss_not_ruled_out"
    elif kill:
        label, reason = NOT_SUPPORTED, "most_specifications_show_a_loss"
    elif not share_held:
        label, reason = NOT_SUPPORTED, "share_check_failed"
    elif loss_detected:
        label, reason = SUPPORTED_IN_PART, "loss_detected_below_break_even"
    elif strict:
        label, reason = SUPPORTED, "strict_form_holds"
    else:
        label, reason = SUPPORTED_IN_PART, "smaller_loss_not_ruled_out"

    return {
        "label": label,
        "reason": reason,
        "claims": {
            "cut_rose": cut_rose,
            "paid_for_itself": paid,
            "kill": kill,
            "share_held": share_held,
            "loss_detected": loss_detected,
            "strict": strict,
        },
        "interval_determined": determined,
        "loss_bound_pct": loss_bound,
        "strict_band_pct": band,
    }


def forward_check(check_date: str, last_week_end: str, evaluated: dict) -> dict:
    """The same share rule, to be read on the first snapshot whose last complete week ends on or after the day before `check_date`."""
    import datetime as dt

    due_from = (dt.date.fromisoformat(check_date) - dt.timedelta(days=1)).isoformat()
    due = last_week_end >= due_from
    out = {"date": check_date, "due_when_data_run_through": due_from, "due": due}
    if not due:
        out["status"] = "not yet due"
    else:
        out["status"] = "thesis not contradicted" if evaluated["passed"] else "thesis contradicted"
    return out

"""Ratios built from plain window sums: capture, fee rate, take, basket share, and
the exact split of revenue growth.

Vocabulary (all for NEAR Intents, over one window of days)
  volume    USD value of swaps
  fees      gross fees users paid on those swaps
  revenue   the part of fees that reached NEAR, split by DefiLlama into
            "front end" (NEAR's own app) and "other" (its share of fees on
            swaps that partner apps send, and smaller items)
  capture   revenue / fees
  fee rate  fees / volume, in basis points (1 basis point = 0.01 percent)
  take      revenue / volume, in basis points; equals fee rate x capture

Revenue is measured two ways. "Booked" is DefiLlama's series as published: each
transfer counts on the day NEAR made it. "Earned" moves each front-end transfer
back onto the days it was earned (see data.accrue). The tests use earned
revenue; booked revenue is reported beside it.
"""
from __future__ import annotations

import math

from .data import ONE_DAY, window_sum


def window(near: dict, peers: dict, start, end) -> dict:
    """Measures for start <= day < end.

    `near` maps 'volume', 'fees', 'revenue', 'front_end', 'other' and
    'front_end_earned' to daily series. `peers` maps a peer key to its daily
    volume series.
    """
    days = (end - start).days
    volume = window_sum(near["volume"], start, end)
    fees = window_sum(near["fees"], start, end)
    booked = window_sum(near["revenue"], start, end)
    front_end = window_sum(near["front_end"], start, end)
    other = window_sum(near["other"], start, end)
    front_end_earned = window_sum(near["front_end_earned"], start, end)
    earned = front_end_earned + other
    peer_volume = {key: window_sum(series, start, end) for key, series in peers.items()}
    basket = math.fsum(peer_volume.values())
    return {
        "start": start.isoformat(),
        "end": (end - ONE_DAY).isoformat(),
        "days": days,
        "volume_per_day": volume / days,
        "fees_per_day": fees / days,
        "revenue_booked_per_day": booked / days,
        "revenue_earned_per_day": earned / days,
        "fee_rate_bps": 1e4 * fees / volume,
        "capture_booked": booked / fees,
        "capture_booked_front_end": front_end / fees,
        "capture_earned": earned / fees,
        "capture_earned_front_end": front_end_earned / fees,
        "capture_other": other / fees,
        "take_booked_bps": 1e4 * booked / volume,
        "take_earned_bps": 1e4 * earned / volume,
        "peers_volume_per_day": basket / days,
        "peer_volume_per_day": {key: value / days for key, value in peer_volume.items()},
        "share": volume / (volume + basket),
        "share_without": {key: volume / (volume + basket - value) for key, value in peer_volume.items()},
    }


def break_even_change(take_before: float, take_after: float) -> float:
    """The volume change, as a fraction, at which revenue would be the same as before.

    Revenue is volume times take. If take goes from t0 to t1, revenue is
    unchanged when volume changes by t0 / t1 - 1.
    """
    return take_before / take_after - 1.0


def compare(before: dict, after: dict) -> dict:
    """Ratios between two windows and the exact split of revenue growth.

    ln(R1/R0) = ln(V1/V0) + ln(f1/f0) + ln(c1/c0), with R earned revenue per
    day, V volume per day, f the fee rate and c earned capture. The volume term
    splits further into basket size and NEAR's share of it:
    ln(V1/V0) = ln(B1/B0) + ln(s1/s0), where B is NEAR plus the peers.
    """
    terms = {
        "volume": math.log(after["volume_per_day"] / before["volume_per_day"]),
        "fee_rate": math.log(after["fee_rate_bps"] / before["fee_rate_bps"]),
        "capture": math.log(after["capture_earned"] / before["capture_earned"]),
    }
    total = math.log(after["revenue_earned_per_day"] / before["revenue_earned_per_day"])
    basket_before = before["volume_per_day"] + before["peers_volume_per_day"]
    basket_after = after["volume_per_day"] + after["peers_volume_per_day"]
    share_points = {"all": 100.0 * (after["share"] - before["share"])}
    for key in before["share_without"]:
        share_points[key] = 100.0 * (after["share_without"][key] - before["share_without"][key])
    return {
        "capture_ratio_booked": after["capture_booked"] / before["capture_booked"],
        "capture_ratio_earned": after["capture_earned"] / before["capture_earned"],
        "take_ratio_booked": after["take_booked_bps"] / before["take_booked_bps"],
        "take_ratio_earned": after["take_earned_bps"] / before["take_earned_bps"],
        "fee_rate_ratio": after["fee_rate_bps"] / before["fee_rate_bps"],
        "volume_ratio": after["volume_per_day"] / before["volume_per_day"],
        "peers_volume_ratio": after["peers_volume_per_day"] / before["peers_volume_per_day"],
        "revenue_ratio_booked": after["revenue_booked_per_day"] / before["revenue_booked_per_day"],
        "revenue_ratio_earned": after["revenue_earned_per_day"] / before["revenue_earned_per_day"],
        "break_even_change_booked": break_even_change(before["take_booked_bps"], after["take_booked_bps"]),
        "break_even_change_earned": break_even_change(before["take_earned_bps"], after["take_earned_bps"]),
        "share_change_points": share_points,
        "share_change_points_min": min(share_points.values()),
        "share_change_points_max": max(share_points.values()),
        "split_log": terms,
        "split_total_log": total,
        "split_sum_log": math.fsum(terms.values()),
        "split_share_of_growth": {name: value / total for name, value in terms.items()} if total else {},
        "volume_split_log": {
            "basket": math.log(basket_after / basket_before),
            "share": math.log(after["share"] / before["share"]),
        },
    }

"""The rule that decides which bridge aggregators are comparison peers.

The comparison group is the easiest part of this kind of test to bend, so the
bridge-aggregator peers are not hand-picked. They are every entry in DefiLlama's
bridge-aggregator list (stored in the snapshot) that passes three rules:

  size      at least the configured trailing-year volume
  distinct  not flagged `doublecounted` by DefiLlama (its volume is already
            inside another entry)
  history   weekly volume defined in every one of the configured number of
            weeks before the event

This module applies the rules to the snapshot and stops the rebuild if the
result differs from the peers named in config/series.json.
"""
from __future__ import annotations

import datetime as dt

from . import data


def slug_of(url: str) -> str:
    return url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]


def history_ok(series: dict, event: dt.date, weeks: int, min_days: int):
    """(True, None) if weekly volume is defined in each of the `weeks` weeks before the event,
    else (False, first undefined week)."""
    first = event - weeks * data.ONE_WEEK
    values = data.weekly_series(series, first, weeks, min_days)
    for i, value in enumerate(values):
        if value is None:
            return False, first + i * data.ONE_WEEK
    return True, None


def select(root, cfg: dict) -> dict:
    """Apply the rules. Returns the table of candidates and raises SnapshotError on a mismatch with the registry."""
    rule = cfg["peer_rule"]
    event = dt.date.fromisoformat(cfg["event_date"])
    universe_key = data.series_with_role(cfg, "universe")[0]["key"]
    overview = data.read_json(root / "data" / "raw" / f"{universe_key}.json")
    by_slug = {slug_of(s["url"]): s for s in cfg["series"] if s["role"] in ("peer", "candidate") and s.get("group") == "aggregator"}

    rows = []
    listed = sorted(overview.get("protocols", []), key=lambda p: (-(p.get("total1y") or 0), p.get("name") or ""))
    for entry in listed:
        total = float(entry.get("total1y") or 0.0)
        if total < rule["min_trailing_year_volume_usd"]:
            continue
        slug = entry.get("slug") or ""
        registered = by_slug.get(slug)
        if registered is None:
            raise data.SnapshotError(
                f"{entry.get('name')} ({slug}) passes the size rule but has no series in config/series.json; add it and refresh")
        series = data.load_daily(root, registered["key"])
        meta = data.load_meta(root, registered["key"])
        first_day = data.first_positive_day(series)
        double = bool(meta.get("doublecounted") or entry.get("doublecounted"))
        ok, gap_week = history_ok(series, event, rule["min_history_weeks_before_event"], cfg["min_days_per_week"])
        if double:
            status, reason = "excluded", "flagged as double-counted by DefiLlama"
        elif not ok:
            status, reason = "excluded", f"no weekly volume in the week of {gap_week.isoformat()}"
        else:
            status, reason = "peer", ""
        rows.append({
            "name": registered["name"],
            "protocol": entry.get("name"),
            "key": registered["key"],
            "trailing_year_volume_usd": total,
            "double_counted": double,
            "first_day_with_volume": first_day.isoformat() if first_day else None,
            "status": status,
            "reason": reason,
        })

    selected = {r["key"] for r in rows if r["status"] == "peer"}
    registry_peers = {s["key"] for s in by_slug.values() if s["role"] == "peer"}
    if selected != registry_peers:
        raise data.SnapshotError(
            "the peer rule and config/series.json disagree on the bridge-aggregator peers: "
            f"rule selects {sorted(selected)}, registry lists {sorted(registry_peers)}")
    extra = {s["key"] for s in by_slug.values()} - {r["key"] for r in rows}
    if extra:
        raise data.SnapshotError(f"registry lists aggregators that fail the size rule: {sorted(extra)}")

    protocols = []
    for s in data.series_with_role(cfg, "peer"):
        if s.get("group") != "protocol":
            continue
        series = data.load_daily(root, s["key"])
        meta = data.load_meta(root, s["key"])
        ok, gap_week = history_ok(series, event, rule["min_history_weeks_before_event"], cfg["min_days_per_week"])
        if meta.get("doublecounted") or not ok:
            raise data.SnapshotError(f"protocol peer {s['name']} fails the distinct or history rule")
        protocols.append({"name": s["name"], "protocol": s["protocol"], "key": s["key"],
                          "first_day_with_volume": data.first_positive_day(series).isoformat()})

    return {
        "universe_entries": len(listed),
        "min_trailing_year_volume_usd": rule["min_trailing_year_volume_usd"],
        "min_history_weeks_before_event": rule["min_history_weeks_before_event"],
        "aggregators": rows,
        "protocols": protocols,
    }


def definition_changes(root, cfg: dict) -> list:
    """Declared definition changes, each checked against the methodology text in the raw file."""
    out = []
    for s in cfg["series"]:
        day = s.get("definition_change")
        if not day:
            continue
        text = str(data.load_meta(root, s["key"]).get("methodology") or "")
        if day not in text:
            raise data.SnapshotError(f"{s['key']}: config says its definition changes on {day}, but the raw file's methodology text does not mention that date")
        out.append({"name": s["name"], "key": s["key"], "date": day})
    return out

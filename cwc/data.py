"""Load the committed DefiLlama snapshot and turn it into daily and weekly series.

Nothing in this module touches the network. Every function is deterministic:
sums use math.fsum, which gives the same result on every platform and Python
version.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import pathlib

Date = dt.date
ONE_DAY = dt.timedelta(days=1)
ONE_WEEK = dt.timedelta(weeks=1)


class SnapshotError(RuntimeError):
    """The raw snapshot is missing, does not match its manifest, or breaks a stated rule."""


def project_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(root: pathlib.Path) -> dict:
    """Analysis settings, with the series registry attached under 'series'."""
    cfg = read_json(root / "config" / "analysis.json")
    cfg["series"] = read_json(root / "config" / "series.json")["series"]
    return cfg


def series_with_role(cfg: dict, role: str) -> list:
    return [s for s in cfg["series"] if s["role"] == role]


def series_key(cfg: dict, measure: str) -> str:
    """Key of the NEAR Intents series that carries the given measure."""
    for s in cfg["series"]:
        if s["role"] == "treated" and s["measure"] == measure:
            return s["key"]
    raise SnapshotError(f"no treated series with measure {measure!r} in config/series.json")


def verify_manifest(root: pathlib.Path, cfg: dict) -> dict:
    """Recompute the SHA-256 of every raw file and compare it with MANIFEST.json.

    Returns the manifest. Raises SnapshotError on a missing file, a hash mismatch,
    or a registry entry without a manifest entry, so a rebuild can never run on
    data other than the recorded snapshot.
    """
    raw = root / "data" / "raw"
    manifest_path = raw / "MANIFEST.json"
    if not manifest_path.exists():
        raise SnapshotError(f"missing {manifest_path}; run `python3 scripts/refresh.py` once with network access")
    manifest = read_json(manifest_path)
    listed = {entry["key"] for entry in manifest["series"]}
    wanted = {s["key"] for s in cfg["series"]}
    if listed != wanted:
        raise SnapshotError(f"config/series.json and MANIFEST.json list different series: {sorted(listed ^ wanted)}")
    for entry in manifest["series"]:
        path = raw / f"{entry['key']}.json"
        if not path.exists():
            raise SnapshotError(f"missing raw file {path}")
        digest = sha256_file(path)
        if digest != entry["sha256"]:
            raise SnapshotError(f"hash mismatch for {path.name}: manifest {entry['sha256'][:12]}, file {digest[:12]}")
    return manifest


def _day(ts) -> Date:
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date()


def load_daily(root: pathlib.Path, key: str) -> dict:
    """{UTC date: USD value} from the `totalDataChart` of a /summary/ response."""
    body = read_json(root / "data" / "raw" / f"{key}.json")
    return {_day(ts): float(value or 0.0) for ts, value in body.get("totalDataChart") or []}


def load_labelled(root: pathlib.Path, key: str) -> dict:
    """{label: {UTC date: USD value}} from a /v2/chart/.../label-breakdown response."""
    rows = read_json(root / "data" / "raw" / f"{key}.json")
    out: dict = {}
    for ts, parts in rows:
        for label, value in parts.items():
            out.setdefault(label, {})[_day(ts)] = float(value or 0.0)
    return out


def load_meta(root: pathlib.Path, key: str) -> dict:
    """The descriptive fields of a /summary/ response, without the charts."""
    body = read_json(root / "data" / "raw" / f"{key}.json")
    return {k: v for k, v in body.items() if not k.startswith("totalDataChart")}


def monday_of(day: Date) -> Date:
    return day - dt.timedelta(days=day.weekday())


def days_between(start: Date, end: Date) -> list:
    """Every date d with start <= d < end."""
    return [start + dt.timedelta(days=i) for i in range((end - start).days)]


def window_sum(series: dict, start: Date, end: Date) -> float:
    """Plain sum of the reported daily values for start <= day < end. A missing day adds nothing."""
    return math.fsum(series.get(day, 0.0) for day in days_between(start, end))


def missing_days(series: dict, start: Date, end: Date) -> int:
    """Number of days in [start, end) with no reported value at all."""
    return sum(1 for day in days_between(start, end) if day not in series)


def weekly_value(series: dict, monday: Date, min_days: int):
    """Weekly volume under the 'at least min_days positive days' rule.

    A day with a zero or missing value is treated as a reporting gap, not as a
    real zero. The week is defined only when at least `min_days` of its seven
    days are positive; its value is then the sum of those days scaled to seven
    days. Otherwise the week is undefined and None is returned.
    """
    positive = [v for v in (series.get(monday + dt.timedelta(days=i)) for i in range(7)) if v is not None and v > 0]
    if len(positive) < min_days:
        return None
    return math.fsum(positive) * 7.0 / len(positive)


def weekly_series(series: dict, first_monday: Date, n_weeks: int, min_days: int) -> list:
    return [weekly_value(series, first_monday + w * ONE_WEEK, min_days) for w in range(n_weeks)]


def first_positive_day(series: dict):
    days = [day for day, value in series.items() if value > 0]
    return min(days) if days else None


def last_complete_week(series_list: list) -> Date:
    """Monday of the last Monday-to-Sunday week fully covered by every series given."""
    cutoff = min(max(s) for s in series_list)
    sunday = cutoff - dt.timedelta(days=(cutoff.weekday() + 1) % 7)
    return sunday - dt.timedelta(days=6)


def outages(series: dict, start: Date, end: Date, min_run: int) -> list:
    """Runs of at least `min_run` consecutive days in [start, end) with zero or missing volume."""
    runs = []
    run_start = None
    for day in days_between(start, end) + [end]:
        down = day < end and series.get(day, 0.0) <= 0
        if down and run_start is None:
            run_start = day
        if not down and run_start is not None:
            if (day - run_start).days >= min_run:
                runs.append({"start": run_start.isoformat(), "end": (day - ONE_DAY).isoformat(), "days": (day - run_start).days})
            run_start = None
    return runs


def overlaps(run: dict, start: Date, end: Date) -> bool:
    """True if an outage run shares at least one day with [start, end)."""
    return Date.fromisoformat(run["start"]) < end and Date.fromisoformat(run["end"]) >= start


def accrue(transfers: dict, fees: dict) -> dict:
    """Spread each transfer back over the days on which it was earned.

    NEAR's front-end revenue reaches its revenue wallet in transfers that are
    sometimes weeks apart, and DefiLlama books each transfer on the day it is
    made. This function moves every transfer onto the days since the previous
    transfer (the day after it, up to and including the transfer day), in
    proportion to the gross fees charged on each of those days. The total is
    unchanged. A stream that is transferred every day comes back unchanged.
    """
    transfer_days = sorted(day for day, value in transfers.items() if value > 0)
    fee_days = sorted(day for day, value in fees.items() if value > 0)
    if not transfer_days or not fee_days:
        return {}
    earned: dict = {}
    previous = fee_days[0] - ONE_DAY
    for day in transfer_days:
        span = days_between(previous + ONE_DAY, day + ONE_DAY) if day > previous else [day]
        total_fees = math.fsum(fees.get(d, 0.0) for d in span)
        for d in span:
            part = fees.get(d, 0.0) / total_fees if total_fees > 0 else 1.0 / len(span)
            earned[d] = earned.get(d, 0.0) + transfers[day] * part
        previous = max(previous, day)
    return earned

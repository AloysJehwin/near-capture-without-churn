#!/usr/bin/env python3
"""Download the raw DefiLlama responses listed in config/series.json.

This is the only step that touches the network. It writes every response
byte for byte to data/raw/<key>.json and records the address, fetch time,
size, SHA-256 and date coverage in data/raw/MANIFEST.json. Everything else
in the project rebuilds offline from those committed files.

Standard library only. No key is needed.

Usage:  python3 scripts/refresh.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "series.json"
RAW = ROOT / "data" / "raw"
USER_AGENT = "capture-without-churn/1.0 (research snapshot; stdlib urllib)"


def fetch(url: str, tries: int = 4, timeout: int = 60) -> bytes:
    last: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last}")


def coverage(body: bytes) -> dict:
    """Point count and first and last UTC day of the daily chart, if the response has one.

    Two response shapes carry a daily chart: an object with `totalDataChart`
    (the /summary/ endpoints) and a bare list of [unix_seconds, value] rows
    (the /v2/chart/ endpoints).
    """
    empty = {"points": 0, "first_day": None, "last_day": None}
    try:
        parsed = json.loads(body)
    except ValueError:
        return empty
    chart = parsed if isinstance(parsed, list) else (parsed.get("totalDataChart") or [])
    if not chart:
        return empty

    def day(ts) -> str:
        return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%d")

    return {"points": len(chart), "first_day": day(chart[0][0]), "last_day": day(chart[-1][0])}


def problem(entry: dict, body: bytes) -> str | None:
    """Why a response must not be stored, or None if it looks sound."""
    try:
        parsed = json.loads(body)
    except ValueError:
        return "the response is not JSON"
    if entry["role"] == "universe":
        return None if isinstance(parsed, dict) and parsed.get("protocols") else "the list of protocols is missing or empty"
    if coverage(body)["points"] == 0:
        return "the response has no daily chart"
    return None


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    # Download everything first. Nothing on disk changes unless every response is sound,
    # so a failed run cannot leave files that disagree with the manifest.
    fetched = []
    for s in cfg["series"]:
        body = fetch(s["url"])
        reason = problem(s, body)
        if reason:
            print(f"Stopped: {s['key']}: {reason}. Nothing was written.", file=sys.stderr)
            return 1
        info = {
            "key": s["key"],
            "protocol": s["protocol"],
            "role": s["role"],
            "measure": s["measure"],
            "url": s["url"],
            "fetched_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
        info.update(coverage(body))
        fetched.append((info, body))
        print(f"{s['key']:<32} {info['points']:>5} pts  {info['first_day']} .. {info['last_day']}  {info['bytes']:>9} B")
        time.sleep(0.4)
    RAW.mkdir(parents=True, exist_ok=True)
    wanted = {f"{info['key']}.json" for info, _ in fetched} | {"MANIFEST.json"}
    for info, body in fetched:
        (RAW / f"{info['key']}.json").write_bytes(body)
    for stale in sorted(p for p in RAW.glob("*.json") if p.name not in wanted):
        stale.unlink()
        print(f"removed {stale.name} (no longer listed in config/series.json)")
    manifest = {"source": cfg["source"], "series": [info for info, _ in fetched]}
    (RAW / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(fetched)} files and MANIFEST.json to {RAW}")
    print("Now run: python3 -m cwc rebuild")
    return 0


if __name__ == "__main__":
    sys.exit(main())

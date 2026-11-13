"""Partner by partner: what NEAR's own swap records show.

DefiLlama gives totals. The NEAR Intents Explorer lists single swaps made
through the 1Click API, with the partner app that sent each one (its
"referral") and the accounts its app fees are paid to. A fixed sample of those
swaps, reduced to totals per partner, is stored in data/explorer/. Taking the
sample needs a partner key (scripts/explorer_sample.py); reading it does not.

The sample is made of blocks. A block is up to 1,000 consecutive successful
swaps that end at a fixed clock time, and it records how many seconds of
activity it spans. Dollars per day for a group of blocks is the sum of their
dollars divided by the sum of their seconds, times 86,400. Shares are ratios of
sums. Nothing here uses the network.
"""
from __future__ import annotations

import datetime as dt
import math

from . import data

Date = dt.date
SECONDS_PER_DAY = 86400.0


def load(root, cfg: dict):
    """The stored sample, or None if this copy of the project has none. Stops on a hash mismatch.

    The sample can be stored in more than one file (one per run of the sampling
    script). Every file listed in the configuration that exists must be in
    data/explorer/MANIFEST.json with a matching SHA-256. Their blocks are used
    together.
    """
    spec = cfg.get("partners") or {}
    paths = [root / name for name in spec.get("sample_files", [])]
    present = [path for path in paths if path.exists()]
    if not present:
        return None
    manifest_path = present[0].parent / "MANIFEST.json"
    if not manifest_path.exists():
        raise data.SnapshotError(f"{present[0].name} has no MANIFEST.json beside it")
    recorded = {entry["file"]: entry for entry in data.read_json(manifest_path)["files"]}
    files, blocks, seen = [], [], set()
    for path in present:
        digest = data.sha256_file(path)
        entry = recorded.get(path.name)
        if entry is None:
            raise data.SnapshotError(f"{path.name} is not listed in {manifest_path.name}")
        if digest != entry["sha256"]:
            raise data.SnapshotError(f"hash mismatch for {path.name}: manifest {entry['sha256'][:12]}, file {digest[:12]}")
        part = data.read_json(path)
        for block in part["blocks"]:
            if block["end_unix"] in seen:
                raise data.SnapshotError(f"{path.name} repeats the block ending at {block['end_unix']}")
            seen.add(block["end_unix"])
            blocks.append(merge_names(block, spec.get("same_partner", {})))
        files.append({"file": path.name, "sha256": digest, "blocks": len(part["blocks"]), "design": part.get("design"),
                      "sampled_from_utc": part.get("sampled_from_utc"), "sampled_to_utc": part.get("sampled_to_utc"),
                      "blocks_failed": len(part.get("blocks_failed", []))})
    blocks.sort(key=lambda block: block["end_unix"])
    return {"source": spec.get("source"), "files": files, "blocks": blocks}


def merge_names(block: dict, same: dict) -> dict:
    """Count referral names that belong to one partner as that partner (for example after a rename)."""
    if not same:
        return block
    out = dict(block)
    referrals: dict = {}
    for name, values in block["referrals"].items():
        target = same.get(name, name)
        if target in referrals:
            referrals[target] = [a + b for a, b in zip(referrals[target], values)]
        else:
            referrals[target] = list(values)
    out["referrals"] = referrals
    if block.get("referral_fee_recipients") is not None:
        split: dict = {}
        for name, accounts in block["referral_fee_recipients"].items():
            entry = split.setdefault(same.get(name, name), {})
            for account, (count, amount) in accounts.items():
                old = entry.get(account, [0, 0.0])
                entry[account] = [old[0] + count, old[1] + amount]
        out["referral_fee_recipients"] = split
    return out


def block_day(block: dict) -> Date:
    """The UTC day a block's swaps belong to: the day of its last second."""
    return dt.datetime.fromtimestamp(block["end_unix"] - 1, dt.timezone.utc).date()


def kind_of(referral: str, own: set, none_label: str) -> str:
    if referral == none_label:
        return "no referral"
    return "own front end" if referral in own else "partner"


def own_front_ends(blocks: list, spec: dict) -> tuple:
    """Referrals that are NEAR's own apps: those whose app fees go mostly to NEAR's front-end wallet.

    Decided from the blocks that record where each referral's fees go. If no
    block does, the list in the configuration is used instead and the result
    says so.
    """
    front = set(spec["near_wallets"]["front_end"])
    totals: dict = {}
    for block in blocks:
        for referral, accounts in (block.get("referral_fee_recipients") or {}).items():
            entry = totals.setdefault(referral, [0.0, 0.0])
            for account, (_count, amount) in accounts.items():
                entry[0] += amount
                if account in front:
                    entry[1] += amount
    if not totals:
        return set(spec.get("own_front_end_referrals", [])), "configuration list"
    own = {referral for referral, (total, to_front) in totals.items() if total > 0 and to_front / total >= 0.5}
    return own, "fee accounts in the sample"


def totals(blocks: list, start: Date, end: Date) -> dict:
    """Sums over the blocks whose day is in [start, end)."""
    out = {"blocks": 0, "swaps": 0, "seconds": 0.0, "usd": 0.0, "referrals": {}, "accounts": {}, "split": {}, "split_blocks": 0, "days": {}}
    for block in blocks:
        day = block_day(block)
        if not (start <= day < end):
            continue
        out["blocks"] += 1
        out["swaps"] += block["swaps"]
        out["seconds"] += block["span_seconds"]
        out["usd"] += block["usd"]
        per_day = out["days"].setdefault(day.isoformat(), {"seconds": 0.0, "referrals": {}})
        per_day["seconds"] += block["span_seconds"]
        for referral, (count, usd, capped, fee, with_fee) in block["referrals"].items():
            entry = out["referrals"].setdefault(referral, [0, 0.0, 0.0, 0.0, 0])
            entry[0] += count
            entry[1] += usd
            entry[2] += capped
            entry[3] += fee
            entry[4] += with_fee
            per_day["referrals"][referral] = per_day["referrals"].get(referral, 0.0) + usd
        for account, (_count, amount) in block["fee_recipients"].items():
            out["accounts"][account] = out["accounts"].get(account, 0.0) + amount
        if block.get("referral_fee_recipients") is not None:
            out["split_blocks"] += 1
            for referral, accounts in block["referral_fee_recipients"].items():
                entry = out["split"].setdefault(referral, {})
                for account, (_count, amount) in accounts.items():
                    entry[account] = entry.get(account, 0.0) + amount
    return out


def per_day(usd: float, seconds: float) -> float:
    return usd / seconds * SECONDS_PER_DAY if seconds > 0 else 0.0


def jackknife_log_ratio(before: dict, after: dict, names: set) -> float:
    """Standard error of ln(after rate / before rate) for a group of referrals, leaving out one day at a time."""
    def rate(days: dict, skip=None) -> float:
        usd = math.fsum(v for key, d in days.items() if key != skip for r, v in d["referrals"].items() if r in names)
        seconds = math.fsum(d["seconds"] for key, d in days.items() if key != skip)
        return usd / seconds if seconds > 0 and usd > 0 else float("nan")

    full = math.log(rate(after["days"]) / rate(before["days"]))
    values = []
    for key in before["days"]:
        values.append(math.log(rate(after["days"]) / rate(before["days"], key)))
    for key in after["days"]:
        values.append(math.log(rate(after["days"], key) / rate(before["days"])))
    values = [v for v in values if v == v]
    if len(values) < 3:
        return float("nan")
    # the two windows are independent samples, so their jackknife variances add
    nb, na = len(before["days"]), len(after["days"])
    vb = values[:nb]
    va = values[nb:]
    var = 0.0
    for part in (vb, va):
        if len(part) > 1:
            mean = math.fsum(part) / len(part)
            var += (len(part) - 1) / len(part) * math.fsum((v - mean) ** 2 for v in part)
    return math.sqrt(var) if full == full else float("nan")


def analyse(sample: dict, cfg: dict, windows: dict, defillama_volume_per_day: dict) -> dict:
    """`windows` maps 'before', 'after', 'latest' to (start, end) dates; `defillama_volume_per_day` to DefiLlama's figure."""
    spec = cfg["partners"]
    blocks = sample["blocks"]
    none_label = spec["no_referral"]
    own, own_source = own_front_ends(blocks, spec)
    front_wallets = set(spec["near_wallets"]["front_end"])
    share_wallets = set(spec["near_wallets"]["partner_share"])
    sums = {name: totals(blocks, a, b) for name, (a, b) in windows.items()}

    out_windows = {}
    for name, t in sums.items():
        by_kind = {"partner": 0.0, "own front end": 0.0, "no referral": 0.0}
        fee_by_kind = {"partner": 0.0, "own front end": 0.0, "no referral": 0.0}
        for referral, (_n, usd, _capped, fee, _with_fee) in t["referrals"].items():
            by_kind[kind_of(referral, own, none_label)] += usd
            fee_by_kind[kind_of(referral, own, none_label)] += fee
        fee_all = math.fsum(t["accounts"].values())
        to_front = math.fsum(v for k, v in t["accounts"].items() if k in front_wallets)
        to_share = math.fsum(v for k, v in t["accounts"].items() if k in share_wallets)
        out_windows[name] = {
            "start": windows[name][0].isoformat(),
            "end": (windows[name][1] - data.ONE_DAY).isoformat(),
            "blocks": t["blocks"],
            "swaps": t["swaps"],
            "days_sampled": len(t["days"]),
            "hours_covered": t["seconds"] / 3600.0,
            "usd_per_day": per_day(t["usd"], t["seconds"]),
            "share_of_defillama_volume": per_day(t["usd"], t["seconds"]) / defillama_volume_per_day[name],
            "volume_share": {k: (v / t["usd"] if t["usd"] else 0.0) for k, v in by_kind.items()},
            "usd_per_day_by_kind": {k: per_day(v, t["seconds"]) for k, v in by_kind.items()},
            "app_fee_bps": fee_all / t["usd"] if t["usd"] else 0.0,
            "partner_app_fee_bps": fee_by_kind["partner"] / by_kind["partner"] if by_kind["partner"] else 0.0,
            "fee_share_to_near_front_end_wallet": to_front / fee_all if fee_all else 0.0,
            "fee_share_to_near_partner_share_wallets": to_share / fee_all if fee_all else 0.0,
            "fee_share_to_near": (to_front + to_share) / fee_all if fee_all else 0.0,
            "referrals_seen": len(t["referrals"]),
            "partners_seen": sum(1 for r in t["referrals"] if kind_of(r, own, none_label) == "partner"),
        }

    before, after, latest = sums["before"], sums["after"], sums["latest"]
    partner_usd_before = math.fsum(v[1] for r, v in before["referrals"].items() if kind_of(r, own, none_label) == "partner")
    ranked = sorted((r for r in before["referrals"] if kind_of(r, own, none_label) == "partner"),
                    key=lambda r: (-before["referrals"][r][1], r))
    top = ranked[: spec["top"]]

    def near_share(t: dict, referral: str):
        accounts = t["split"].get(referral)
        if not accounts:
            return None
        total = math.fsum(accounts.values())
        return math.fsum(v for k, v in accounts.items() if k in share_wallets or k in front_wallets) / total if total > 0 else None

    rows = []
    for referral in top:
        cells = {}
        for name, t in sums.items():
            n, usd, capped, fee, _with_fee = t["referrals"].get(referral, [0, 0.0, 0.0, 0.0, 0])
            cells[name] = {
                "swaps": n,
                "usd_per_day": per_day(usd, t["seconds"]),
                "usd_per_day_capped": per_day(capped, t["seconds"]),
                "app_fee_bps": fee / usd if usd else None,
                "near_share_of_its_fees": near_share(t, referral),
            }
        b = cells["before"]["usd_per_day"]
        rows.append({
            "partner": referral,
            "share_of_partner_volume_before": before["referrals"][referral][1] / partner_usd_before,
            "before": cells["before"], "after": cells["after"], "latest": cells["latest"],
            "after_over_before": cells["after"]["usd_per_day"] / b if b else None,
            "latest_over_before": cells["latest"]["usd_per_day"] / b if b else None,
            "after_over_before_capped": (cells["after"]["usd_per_day_capped"] / cells["before"]["usd_per_day_capped"]
                                         if cells["before"]["usd_per_day_capped"] else None),
        })

    def group_ratio(a: dict, b: dict, names: set) -> float:
        num = per_day(math.fsum(v[1] for r, v in b["referrals"].items() if r in names), b["seconds"])
        den = per_day(math.fsum(v[1] for r, v in a["referrals"].items() if r in names), a["seconds"])
        return num / den if den else float("nan")

    def group_ratio_capped(a: dict, b: dict, names: set) -> float:
        num = per_day(math.fsum(v[2] for r, v in b["referrals"].items() if r in names), b["seconds"])
        den = per_day(math.fsum(v[2] for r, v in a["referrals"].items() if r in names), a["seconds"])
        return num / den if den else float("nan")

    top_set = set(top)
    partners_before = {r for r in before["referrals"] if kind_of(r, own, none_label) == "partner"}
    partners_after = {r for r in after["referrals"] if kind_of(r, own, none_label) == "partner"}
    partners_latest = {r for r in latest["referrals"] if kind_of(r, own, none_label) == "partner"}
    all_partners = partners_before | partners_after | partners_latest
    gone_below = spec["gone_below"]
    shown = lambda r: spec.get("display_names", {}).get(r["partner"], r["partner"])
    gone_after = [shown(r) for r in rows if (r["after_over_before"] or 0.0) < gone_below]
    gone_latest = [shown(r) for r in rows if (r["latest_over_before"] or 0.0) < gone_below]
    halved_after = [shown(r) for r in rows if (r["after_over_before"] or 0.0) < 0.5]
    new_latest_usd = math.fsum(v[1] for r, v in latest["referrals"].items() if r in partners_latest and r not in partners_before)
    latest_partner_usd = math.fsum(v[1] for r, v in latest["referrals"].items() if r in partners_latest)
    se_after = jackknife_log_ratio(before, after, top_set)
    se_latest = jackknife_log_ratio(before, latest, top_set)
    names = spec.get("display_names", {})
    for row in rows:
        row["name"] = names.get(row["partner"], row["partner"])
    return finite({
        "available": True,
        "source": sample.get("source"),
        "files": sample["files"],
        "hours_utc": sorted({dt.datetime.fromtimestamp(b["end_unix"], dt.timezone.utc).hour for b in blocks}),
        "first_day": min(block_day(b) for b in blocks).isoformat(),
        "last_day": max(block_day(b) for b in blocks).isoformat(),
        "blocks": len(blocks),
        "swaps": sum(b["swaps"] for b in blocks),
        "blocks_with_fee_accounts_per_partner": sum(1 for b in blocks if b.get("referral_fee_recipients") is not None),
        "own_front_end_referrals": sorted(own),
        "own_front_end_rule": own_source,
        "near_wallets": spec["near_wallets"],
        "windows": out_windows,
        "top_partners": rows,
        "top_count": len(rows),
        "top_share_of_partner_volume_before": math.fsum(r["share_of_partner_volume_before"] for r in rows),
        "top_after_over_before": group_ratio(before, after, top_set),
        "top_latest_over_before": group_ratio(before, latest, top_set),
        "top_after_over_before_capped": group_ratio_capped(before, after, top_set),
        "top_after_over_before_se_log": se_after,
        "top_latest_over_before_se_log": se_latest,
        "all_partners_after_over_before": group_ratio(before, after, all_partners),
        "all_partners_latest_over_before": group_ratio(before, latest, all_partners),
        "own_front_end_after_over_before": group_ratio(before, after, own),
        "own_front_end_latest_over_before": group_ratio(before, latest, own),
        "top_still_sending_after": sum(1 for r in rows if r["after"]["swaps"] > 0),
        "top_still_sending_latest": sum(1 for r in rows if r["latest"]["swaps"] > 0),
        "top_gone_after": gone_after,
        "top_gone_latest": gone_latest,
        "top_halved_after": halved_after,
        "gone_below": gone_below,
        "new_partner_share_of_partner_volume_latest": new_latest_usd / latest_partner_usd if latest_partner_usd else 0.0,
    })


def finite(obj):
    """Replace a number that is not finite by None, at any depth."""
    if isinstance(obj, float):
        return obj if obj == obj and obj not in (float("inf"), float("-inf")) else None
    if isinstance(obj, dict):
        return {k: finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [finite(v) for v in obj]
    return obj

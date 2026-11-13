#!/usr/bin/env python3
"""Sample NEAR Intents swaps from the Explorer API and save totals per partner app.

Why this exists
    DefiLlama shows how much was swapped in total. It does not show which
    partner app (the "referral") sent each swap. The NEAR Intents Explorer API
    does, but it needs a partner token. This script takes a fixed sample of
    successful swaps and keeps only totals per partner app. Nothing that
    identifies a user is written to disk: no sender, recipient, deposit address,
    transaction hash or single swap. The account names that receive app fees
    are kept, because they identify an app, not a user.

What it needs
    A token in the environment variable INTENTS_JWT, or in a file named .env in
    the folder you run it from, as one line:
        INTENTS_JWT=your-token
    The token is sent only to explorer.near-intents.org. It is never printed
    and never written to any file.

How to run
    python3 explorer_sample.py --check     one small request; shows that the token works
    python3 explorer_sample.py             the full sample (about 90 minutes)

    The API allows one request every 5 seconds, which is why it takes this
    long. Progress is saved as it goes. If it stops, run the same command again
    and it continues where it left off.

The sample
    For every UTC day from --first-day to --last-day, and for each of the hours
    in --hours (default 0, 8 and 16), one request asks for up to 1,000
    successful swaps created in the 8 hours before that time. The API returns
    the most recent ones first, so each request is a block of consecutive swaps
    that ends at a fixed clock time. The same clock times are used on every
    day, so periods can be compared with each other.

Output
    explorer_sample.json: one record per request with the time it covers, the
    number of swaps, and per partner app the number of swaps, the USD value and
    the fees the app charged.

Standard library only. Works with Python 3.8 or later.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://explorer.near-intents.org/api/v0/transactions"
USER_AGENT = "capture-without-churn/1.0 (explorer sample; stdlib urllib)"
MIN_GAP_SECONDS = 5.3          # the API allows one request every 5 seconds
BLOCK_SECONDS = 8 * 3600       # each request looks back at most 8 hours
PAGE_SIZE = 1000
CAP_USD = 100000.0             # second total in which no single swap counts for more than this
NO_REFERRAL = "(none)"

UTC = dt.timezone.utc


class Stop(Exception):
    """A problem the user has to fix; the message says what to do."""


def read_token() -> str:
    token = os.environ.get("INTENTS_JWT", "").strip()
    if not token:
        for folder in (pathlib.Path.cwd(), pathlib.Path(__file__).resolve().parent, pathlib.Path(__file__).resolve().parent.parent):
            env = folder / ".env"
            if env.is_file():
                for line in env.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("export "):
                        line = line[len("export "):].strip()
                    if line.startswith("INTENTS_JWT="):
                        token = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
            if token:
                break
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token or token in ("your-token", "PASTE_TOKEN_HERE"):
        raise Stop(
            "No token found. Put it in a file named .env in this folder as one line:\n"
            "    INTENTS_JWT=your-token\n"
            "or set the environment variable INTENTS_JWT."
        )
    return token


def ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def ssl_context_certifi():
    try:
        import certifi  # type: ignore
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


class Client:
    def __init__(self, token: str):
        self._token = token
        self._last = 0.0
        self._context = ssl_context()
        self.requests = 0

    def get(self, params: dict):
        url = API + "?" + urllib.parse.urlencode(params)
        waits = 0
        errors = 0
        while True:
            gap = time.monotonic() - self._last
            if gap < MIN_GAP_SECONDS:
                time.sleep(MIN_GAP_SECONDS - gap)
            self._last = time.monotonic()
            self.requests += 1
            request = urllib.request.Request(url, headers={
                "Authorization": "Bearer " + self._token,
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            })
            try:
                with urllib.request.urlopen(request, timeout=90, context=self._context) as response:
                    body = json.loads(response.read().decode("utf-8"))
                if isinstance(body, dict) and "error" in body:
                    raise Stop("The API answered with an error: " + describe_error(body))
                if not isinstance(body, list):
                    raise Stop("The API answered with something other than a list of swaps.")
                return body
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = describe_error(json.loads(exc.read().decode("utf-8")))
                except Exception:
                    pass
                if exc.code in (401, 403):
                    raise Stop(f"The API rejected the token (HTTP {exc.code}). {detail}\nCheck that INTENTS_JWT holds the Explorer API token and that it has not expired.")
                if exc.code == 400:
                    raise Stop(f"The API rejected the request (HTTP 400). {detail}")
                if exc.code == 429:
                    waits += 1
                    if waits > 30:
                        raise Stop("The API kept answering 'too many requests'. Wait a few minutes and run the same command again.")
                    time.sleep(10)
                    continue
                errors += 1
                if errors > 5:
                    return None
                time.sleep(5 * errors)
            except ssl.SSLCertVerificationError:
                fallback = ssl_context_certifi()
                if fallback is None or self._context is fallback:
                    raise Stop(
                        "Python on this computer could not check the site's security certificate.\n"
                        "Fix (macOS, python.org install): run 'Install Certificates.command' from the Python folder in Applications,\n"
                        "or run:  python3 -m pip install certifi   and start this script again."
                    )
                self._context = fallback
            except urllib.error.URLError as exc:
                if isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError):
                    fallback = ssl_context_certifi()
                    if fallback is None or self._context is fallback:
                        raise Stop(
                            "Python on this computer could not check the site's security certificate.\n"
                            "Fix (macOS, python.org install): run 'Install Certificates.command' from the Python folder in Applications,\n"
                            "or run:  python3 -m pip install certifi   and start this script again."
                        )
                    self._context = fallback
                    continue
                errors += 1
                if errors > 5:
                    return None
                time.sleep(5 * errors)
            except (TimeoutError, ConnectionError, json.JSONDecodeError):
                errors += 1
                if errors > 5:
                    return None
                time.sleep(5 * errors)


def describe_error(body) -> str:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or "")[:300]
        if error:
            return str(error)[:300]
    return ""


def to_float(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number and number not in (float("inf"), float("-inf")) else 0.0


def summarise(swaps: list, end_unix: int) -> dict:
    """Totals for one block of swaps. Nothing that identifies a user is kept."""
    stamps = [int(to_float(s.get("createdAtTimestamp"))) for s in swaps if s.get("createdAtTimestamp") is not None]
    referrals: dict = {}
    recipients: dict = {}
    deposit_types: dict = {}
    recipient_types: dict = {}
    total_usd = 0.0
    zero_usd = 0
    for s in swaps:
        usd = to_float(s.get("amountInUsd")) or to_float(s.get("amountOutUsd"))
        if usd <= 0:
            zero_usd += 1
        total_usd += usd
        name = str(s.get("referral") or NO_REFERRAL).strip().lower() or NO_REFERRAL
        fees = s.get("appFees") if isinstance(s.get("appFees"), list) else []
        fee_bps = 0.0
        for fee in fees:
            if not isinstance(fee, dict):
                continue
            bps = to_float(fee.get("fee"))
            fee_bps += bps
            who = str(fee.get("recipient") or "(unknown)").strip().lower()
            entry = recipients.setdefault(who, [0, 0.0])
            entry[0] += 1
            entry[1] += bps * usd
        entry = referrals.setdefault(name, [0, 0.0, 0.0, 0.0, 0])
        entry[0] += 1                       # swaps
        entry[1] += usd                     # USD value
        entry[2] += min(usd, CAP_USD)       # USD value with each swap capped
        entry[3] += fee_bps * usd           # app fee in basis points times USD (divide by USD for the average fee)
        entry[4] += 1 if fee_bps > 0 else 0  # swaps on which the app charged a fee
        key = str(s.get("depositType") or "(unknown)")
        deposit_types[key] = deposit_types.get(key, 0) + 1
        key = str(s.get("recipientType") or "(unknown)")
        recipient_types[key] = recipient_types.get(key, 0) + 1
    newest = max(stamps) if stamps else None
    oldest = min(stamps) if stamps else None
    full = len(swaps) >= PAGE_SIZE
    return {
        "end_unix": end_unix,
        "swaps": len(swaps),
        "full_page": full,
        "oldest_unix": oldest,
        "newest_unix": newest,
        # seconds of activity the block covers: back to the oldest swap if the page is full, else the whole 8 hours
        "span_seconds": (end_unix - oldest) if (full and oldest is not None) else BLOCK_SECONDS,
        "newest_first": stamps == sorted(stamps, reverse=True),
        "usd": round(total_usd, 2),
        "zero_usd_swaps": zero_usd,
        "deposit_types": deposit_types,
        "recipient_types": recipient_types,
        "referrals": {k: [v[0], round(v[1], 2), round(v[2], 2), round(v[3], 2), v[4]] for k, v in sorted(referrals.items())},
        "fee_recipients": {k: [v[0], round(v[1], 2)] for k, v in sorted(recipients.items())},
    }


def plan(first_day: dt.date, last_day: dt.date, hours: list) -> list:
    """Block end times: all days at the first hour, then all days at the second hour, and so on."""
    ends = []
    for hour in hours:
        day = first_day
        while day <= last_day:
            ends.append(int(dt.datetime(day.year, day.month, day.day, hour, tzinfo=UTC).timestamp()))
            day += dt.timedelta(days=1)
    return ends


def load_progress(path: pathlib.Path) -> dict:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"blocks": {}, "failed": []}


def save(path: pathlib.Path, payload: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temp, path)


def write_output(path: pathlib.Path, progress: dict, args, hours: list, started: str) -> None:
    blocks = [progress["blocks"][key] for key in sorted(progress["blocks"], key=int)]
    payload = {
        "source": "NEAR Intents Explorer API, GET /api/v0/transactions (partner token required; the token is not stored)",
        "what": "Totals per partner app (referral) from a fixed sample of successful swaps. No sender, recipient, deposit address, hash or single swap is stored.",
        "design": {
            "first_day": args.first_day,
            "last_day": args.last_day,
            "hours_utc": hours,
            "block_seconds": BLOCK_SECONDS,
            "page_size": PAGE_SIZE,
            "statuses": "SUCCESS",
            "cap_usd": CAP_USD,
            "referral_fields": ["swaps", "usd", "usd_capped", "fee_bps_times_usd", "swaps_with_app_fee"],
            "fee_recipient_fields": ["fee_entries", "fee_bps_times_usd"],
        },
        "sampled_from_utc": started,
        "sampled_to_utc": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "blocks_planned": len(plan(dt.date.fromisoformat(args.first_day), dt.date.fromisoformat(args.last_day), hours)),
        "blocks_done": len(blocks),
        "blocks_failed": sorted(progress.get("failed", [])),
        "blocks": blocks,
    }
    save(path, payload)


def check(client: Client) -> int:
    now = int(time.time())
    swaps = client.get({"numberOfTransactions": 50, "statuses": "SUCCESS", "endTimestampUnix": now})
    if swaps is None:
        raise Stop("Could not reach the API. Check the internet connection and try again.")
    summary = summarise(swaps, now)
    print(f"The token works. The API returned {summary['swaps']} successful swaps.")
    if swaps:
        print("Fields in a swap record: " + ", ".join(sorted(swaps[0].keys())))
        if summary["oldest_unix"] and summary["newest_unix"]:
            print(f"They cover {summary['newest_unix'] - summary['oldest_unix']} seconds, newest first: {summary['newest_first']}.")
        top = sorted(summary["referrals"].items(), key=lambda kv: -kv[1][0])[:8]
        print("Partner apps in this small sample (name: swaps): " + ", ".join(f"{name}: {values[0]}" for name, values in top))
        print(f"Swaps with a USD value of zero: {summary['zero_usd_swaps']}.")
    print("Now run the same command without --check to take the full sample.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sample NEAR Intents swaps and save totals per partner app.")
    parser.add_argument("--check", action="store_true", help="make one small request to test the token, then stop")
    parser.add_argument("--first-day", default="2025-11-24", help="first UTC day to sample (default 2025-11-24)")
    parser.add_argument("--last-day", default="2026-11-08", help="last UTC day to sample (default 2026-11-08)")
    parser.add_argument("--hours", default="0,8,16", help="UTC hours at which a block ends (default 0,8,16)")
    parser.add_argument("--out", default="explorer_sample.json", help="output file (default explorer_sample.json)")
    args = parser.parse_args()
    try:
        client = Client(read_token())
        if args.check:
            return check(client)
        hours = [int(h) for h in args.hours.split(",") if h.strip() != ""]
        if not hours or any(h < 0 or h > 23 for h in hours):
            raise Stop("--hours must be a list of numbers from 0 to 23, for example 0,8,16")
        ends = plan(dt.date.fromisoformat(args.first_day), dt.date.fromisoformat(args.last_day), hours)
        out_path = pathlib.Path(args.out)
        progress_path = out_path.with_suffix(".progress.json")
        progress = load_progress(progress_path)
        progress.setdefault("started_utc", dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
        todo = [end for end in ends if str(end) not in progress["blocks"]]
        minutes = len(todo) * MIN_GAP_SECONDS / 60.0
        print(f"{len(ends)} requests planned, {len(ends) - len(todo)} already done, {len(todo)} to go (about {minutes:.0f} minutes).")
        print("You can stop with Ctrl-C at any time and run the same command again to continue.")
        done_now = 0
        t0 = time.monotonic()
        try:
            for end in todo:
                swaps = client.get({
                    "numberOfTransactions": PAGE_SIZE,
                    "statuses": "SUCCESS",
                    "startTimestampUnix": end - BLOCK_SECONDS,
                    "endTimestampUnix": end,
                })
                if swaps is None:
                    if end not in progress["failed"]:
                        progress["failed"].append(end)
                else:
                    progress["blocks"][str(end)] = summarise(swaps, end)
                    if end in progress["failed"]:
                        progress["failed"].remove(end)
                done_now += 1
                if done_now % 10 == 0 or done_now == len(todo):
                    save(progress_path, progress)
                    left = (len(todo) - done_now) * (time.monotonic() - t0) / done_now / 60.0
                    stamp = dt.datetime.fromtimestamp(end, UTC).strftime("%Y-%m-%d %H:%M")
                    print(f"  {done_now}/{len(todo)} done, block ending {stamp} UTC, about {left:.0f} minutes left", flush=True)
        except KeyboardInterrupt:
            print("\nStopped. Progress is saved; run the same command again to continue.")
        save(progress_path, progress)
        write_output(out_path, progress, args, hours, progress["started_utc"])
        print(f"Wrote {out_path} with {len(progress['blocks'])} of {len(ends)} blocks ({len(progress.get('failed', []))} failed).")
        if len(progress["blocks"]) == len(ends):
            print("Complete. Send this file back, or put it in data/explorer/ in the project.")
        return 0
    except Stop as stop:
        print(str(stop), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

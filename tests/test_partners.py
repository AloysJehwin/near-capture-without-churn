import datetime as dt
import json
import pathlib
import tempfile
import unittest

from tests.helpers import ROOT, built
from cwc import data, partners

SPEC = {
    "source": "made up",
    "sample_files": ["data/explorer/a.json", "data/explorer/b.json"],
    "near_wallets": {"front_end": ["front.near"], "partner_share": ["share.near"]},
    "own_front_end_referrals": ["listed-own"],
    "no_referral": "(none)",
    "top": 2,
    "gone_below": 0.1,
    "same_partner": {"old-name": "alpha"},
    "display_names": {"alpha": "Alpha"},
}
DAY = dt.date(2026, 1, 1)


def unix(day: dt.date, hour: int = 0) -> int:
    return int(dt.datetime(day.year, day.month, day.day, hour, tzinfo=dt.timezone.utc).timestamp())


def block(day: dt.date, referrals: dict, seconds: int = 3600, split=None, hour: int = 0) -> dict:
    """One block that ends at `hour` on the day after `day`, so that it belongs to `day`."""
    out = {
        "end_unix": unix(day + dt.timedelta(days=1), hour) if hour == 0 else unix(day, hour),
        "swaps": sum(v[0] for v in referrals.values()),
        "span_seconds": seconds,
        "usd": sum(v[1] for v in referrals.values()),
        "referrals": {k: [v[0], v[1], v[1], v[2], v[0]] for k, v in referrals.items()},
        "fee_recipients": {},
    }
    if split is not None:
        out["referral_fee_recipients"] = split
        for accounts in split.values():
            for account, (count, amount) in accounts.items():
                old = out["fee_recipients"].get(account, [0, 0.0])
                out["fee_recipients"][account] = [old[0] + count, old[1] + amount]
    return out


def sample(blocks: list) -> dict:
    return {"source": "made up", "files": [{"file": "a.json", "sha256": "0" * 64}], "blocks": blocks}


WINDOWS = {"before": (DAY, DAY + dt.timedelta(days=2)), "after": (DAY + dt.timedelta(days=2), DAY + dt.timedelta(days=4)),
           "latest": (DAY + dt.timedelta(days=4), DAY + dt.timedelta(days=6))}
LLAMA = {"before": 1e6, "after": 1e6, "latest": 1e6}


def days(*offsets):
    return [DAY + dt.timedelta(days=o) for o in offsets]


class Analyse(unittest.TestCase):
    def setUp(self):
        blocks = []
        for d in days(0, 1):          # before: alpha 100 an hour, beta 50, gamma 10
            blocks.append(block(d, {"alpha": (10, 100.0, 5000.0), "beta": (5, 50.0, 0.0), "gamma": (1, 10.0, 0.0), "(none)": (2, 40.0, 0.0)}))
        for d in days(2, 3):          # after: alpha halves, beta is gone, blocks span two hours
            blocks.append(block(d, {"alpha": (10, 100.0, 5000.0), "gamma": (1, 20.0, 0.0), "listed-own": (1, 80.0, 0.0)}, seconds=7200))
        for d in days(4, 5):          # latest: alpha back, counted under an old name on one day
            name = "old-name" if d == days(4)[0] else "alpha"
            blocks.append(block(d, {name: (10, 100.0, 5000.0), "delta": (1, 100.0, 0.0)}))
        cfg = {"partners": SPEC}
        blocks = [partners.merge_names(b, SPEC["same_partner"]) for b in blocks]
        self.out = partners.analyse(sample(blocks), cfg, WINDOWS, LLAMA)

    def test_volume_per_day_uses_the_time_the_blocks_span(self):
        w = self.out["windows"]
        self.assertAlmostEqual(w["before"]["usd_per_day"], 200.0 * 24)
        self.assertAlmostEqual(w["after"]["usd_per_day"], 200.0 / 2 * 24)
        self.assertAlmostEqual(w["before"]["share_of_defillama_volume"], 200.0 * 24 / 1e6)

    def test_top_partners_are_ranked_on_the_window_before(self):
        rows = self.out["top_partners"]
        self.assertEqual([r["partner"] for r in rows], ["alpha", "beta"])
        self.assertEqual(rows[0]["name"], "Alpha")
        self.assertAlmostEqual(rows[0]["after_over_before"], 0.5)
        self.assertAlmostEqual(rows[1]["after_over_before"], 0.0)
        self.assertAlmostEqual(rows[0]["latest_over_before"], 1.0)
        self.assertAlmostEqual(self.out["top_after_over_before"], 50.0 / 150.0)
        self.assertEqual(self.out["top_gone_after"], ["beta"])
        self.assertEqual(self.out["top_halved_after"], ["beta"])

    def test_names_of_one_partner_are_counted_together(self):
        self.assertEqual(self.out["top_partners"][0]["latest"]["swaps"], 20)

    def test_kinds_and_fees(self):
        w = self.out["windows"]
        self.assertAlmostEqual(w["before"]["volume_share"]["partner"], 160.0 / 200.0)
        self.assertAlmostEqual(w["before"]["volume_share"]["no referral"], 40.0 / 200.0)
        self.assertAlmostEqual(w["after"]["volume_share"]["own front end"], 80.0 / 200.0)
        self.assertAlmostEqual(w["before"]["partner_app_fee_bps"], 10000.0 / 320.0)
        self.assertEqual(self.out["own_front_end_rule"], "configuration list")
        self.assertAlmostEqual(self.out["new_partner_share_of_partner_volume_latest"], 0.5)

    def test_own_apps_are_found_from_fee_accounts_when_the_sample_has_them(self):
        split = {"alpha": {"alpha-fees.near": [10, 90.0], "share.near": [10, 10.0]}, "house": {"front.near": [3, 30.0]}}
        blocks = [block(d, {"alpha": (10, 100.0, 100.0), "house": (3, 30.0, 30.0)}, split=split) for d in days(0, 1, 2, 3, 4, 5)]
        out = partners.analyse(sample(blocks), {"partners": SPEC}, WINDOWS, LLAMA)
        self.assertEqual(out["own_front_end_referrals"], ["house"])
        self.assertEqual(out["own_front_end_rule"], "fee accounts in the sample")
        self.assertAlmostEqual(out["top_partners"][0]["before"]["near_share_of_its_fees"], 0.1)
        self.assertAlmostEqual(out["windows"]["before"]["fee_share_to_near_partner_share_wallets"], 10.0 / 130.0)
        self.assertAlmostEqual(out["windows"]["before"]["fee_share_to_near_front_end_wallet"], 30.0 / 130.0)

    def test_every_number_is_finite_or_none(self):
        text = json.dumps(self.out, allow_nan=False)
        self.assertNotIn("NaN", text)


class Load(unittest.TestCase):
    def write(self, root: pathlib.Path, name: str, blocks: list) -> str:
        path = root / "data" / "explorer" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"blocks": blocks}), encoding="utf-8")
        return data.sha256_file(path)

    def test_no_sample_file_means_no_partner_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(partners.load(pathlib.Path(tmp), {"partners": SPEC}))

    def test_files_are_joined_and_checked_against_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            a = self.write(root, "a.json", [block(DAY, {"alpha": (1, 1.0, 0.0)})])
            b = self.write(root, "b.json", [block(DAY, {"old-name": (1, 1.0, 0.0)}, hour=12)])
            manifest = root / "data" / "explorer" / "MANIFEST.json"
            manifest.write_text(json.dumps({"files": [{"file": "a.json", "sha256": a}, {"file": "b.json", "sha256": b}]}), encoding="utf-8")
            loaded = partners.load(root, {"partners": SPEC})
            self.assertEqual(len(loaded["blocks"]), 2)
            self.assertEqual([list(x["referrals"]) for x in loaded["blocks"]], [["alpha"], ["alpha"]])
            (root / "data" / "explorer" / "b.json").write_text(json.dumps({"blocks": []}), encoding="utf-8")
            with self.assertRaises(data.SnapshotError):
                partners.load(root, {"partners": SPEC})
            manifest.write_text(json.dumps({"files": [{"file": "a.json", "sha256": a}]}), encoding="utf-8")
            with self.assertRaises(data.SnapshotError):
                partners.load(root, {"partners": SPEC})

    def test_the_same_block_twice_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            one = [block(DAY, {"alpha": (1, 1.0, 0.0)})]
            a = self.write(root, "a.json", one)
            b = self.write(root, "b.json", one)
            (root / "data" / "explorer" / "MANIFEST.json").write_text(
                json.dumps({"files": [{"file": "a.json", "sha256": a}, {"file": "b.json", "sha256": b}]}), encoding="utf-8")
            with self.assertRaises(data.SnapshotError):
                partners.load(root, {"partners": SPEC})


class Committed(unittest.TestCase):
    def test_partner_view_matches_the_committed_sample(self):
        findings, files = built()
        view = findings["partners"]
        has_sample = any((ROOT / name).exists() for name in findings["config"]["partners"]["sample_files"])
        self.assertEqual(view["available"], has_sample)
        self.assertEqual("docs/charts/partners.svg" in files, has_sample)
        if has_sample:
            self.assertEqual(view["blocks"], sum(entry["blocks"] for entry in view["files"]))
            self.assertLessEqual(view["top_count"], findings["config"]["partners"]["top"])
            for window in view["windows"].values():
                self.assertAlmostEqual(sum(window["volume_share"].values()), 1.0, places=4)


if __name__ == "__main__":
    unittest.main()

import datetime as dt
import pathlib
import shutil
import tempfile
import unittest

from tests.helpers import ROOT
from cwc import data

D = dt.date


class WeeklyRule(unittest.TestCase):
    def test_week_needs_five_positive_days_and_is_scaled_to_seven(self):
        monday = D(2026, 3, 2)
        series = {monday + dt.timedelta(days=i): 10.0 for i in range(7)}
        self.assertAlmostEqual(data.weekly_value(series, monday, 5), 70.0)
        series[monday + dt.timedelta(days=1)] = 0.0
        del series[monday + dt.timedelta(days=2)]
        self.assertAlmostEqual(data.weekly_value(series, monday, 5), 70.0)   # five days of 10, scaled to seven
        series[monday + dt.timedelta(days=3)] = 0.0
        self.assertIsNone(data.weekly_value(series, monday, 5))              # only four positive days

    def test_weekly_series_and_last_complete_week(self):
        monday = D(2026, 3, 2)
        series = {monday + dt.timedelta(days=i): 1.0 for i in range(17)}     # ends on a Wednesday
        self.assertEqual(data.weekly_series(series, monday, 2, 5), [7.0, 7.0])
        self.assertEqual(data.last_complete_week([series]), monday + dt.timedelta(days=7))
        self.assertEqual(data.monday_of(D(2026, 3, 8)), monday)

    def test_window_sum_and_missing_days(self):
        start = D(2026, 1, 1)
        series = {start: 1.0, start + dt.timedelta(days=2): 3.0}
        self.assertEqual(data.window_sum(series, start, start + dt.timedelta(days=3)), 4.0)
        self.assertEqual(data.missing_days(series, start, start + dt.timedelta(days=3)), 1)
        self.assertEqual(data.first_positive_day({start: 0.0, start + dt.timedelta(days=5): 2.0}), start + dt.timedelta(days=5))

    def test_outages_are_runs_of_zero_or_missing_days(self):
        start = D(2026, 5, 1)
        series = {start + dt.timedelta(days=i): (0.0 if 3 <= i <= 6 else 5.0) for i in range(12)}
        del series[start + dt.timedelta(days=9)]                             # one missing day is not an outage
        runs = data.outages(series, start, start + dt.timedelta(days=12), 3)
        self.assertEqual(runs, [{"start": "2026-05-04", "end": "2026-05-07", "days": 4}])
        self.assertTrue(data.overlaps(runs[0], D(2026, 5, 7), D(2026, 5, 20)))
        self.assertFalse(data.overlaps(runs[0], D(2026, 5, 8), D(2026, 5, 20)))


class Accrual(unittest.TestCase):
    def test_transfer_is_spread_by_fees_and_total_is_kept(self):
        start = D(2026, 1, 1)
        fees = {start + dt.timedelta(days=i): float(i + 1) for i in range(6)}        # 1, 2, 3, 4, 5, 6
        transfers = {start + dt.timedelta(days=2): 60.0, start + dt.timedelta(days=5): 150.0}
        earned = data.accrue(transfers, fees)
        self.assertAlmostEqual(sum(earned.values()), 210.0)
        self.assertAlmostEqual(earned[start], 10.0)                                   # 60 * 1 / (1 + 2 + 3)
        self.assertAlmostEqual(earned[start + dt.timedelta(days=2)], 30.0)
        self.assertAlmostEqual(earned[start + dt.timedelta(days=3)], 40.0)            # 150 * 4 / (4 + 5 + 6)

    def test_daily_stream_is_unchanged(self):
        start = D(2026, 1, 1)
        fees = {start + dt.timedelta(days=i): 100.0 for i in range(5)}
        transfers = {start + dt.timedelta(days=i): 7.0 + i for i in range(5)}
        earned = data.accrue(transfers, fees)
        for day, value in transfers.items():
            self.assertAlmostEqual(earned[day], value)


class Snapshot(unittest.TestCase):
    def test_every_raw_file_matches_its_manifest_hash(self):
        cfg = data.load_config(ROOT)
        manifest = data.verify_manifest(ROOT, cfg)
        self.assertEqual({e["key"] for e in manifest["series"]}, {s["key"] for s in cfg["series"]})

    def test_one_changed_byte_stops_the_rebuild(self):
        cfg = data.load_config(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            copy = pathlib.Path(shutil.copytree(ROOT / "data" / "raw", pathlib.Path(tmp) / "data" / "raw"))
            victim = sorted(p for p in copy.iterdir() if p.name != "MANIFEST.json")[0]
            body = bytearray(victim.read_bytes())
            body[len(body) // 2] ^= 1
            victim.write_bytes(bytes(body))
            with self.assertRaises(data.SnapshotError):
                data.verify_manifest(copy.parent.parent, cfg)


if __name__ == "__main__":
    unittest.main()

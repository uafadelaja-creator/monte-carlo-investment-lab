"""Offline guardrail tests for daily discovery (no internet required)."""
import unittest
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import daily_pair_scanner as d


class DailyDiscoveryTests(unittest.TestCase):
    def test_candidate_generation_deduplicated(self):
        pairs = d.all_candidates()
        self.assertGreater(len(pairs), 150)
        self.assertEqual(len(pairs), len({tuple(sorted((a, b))) for a, b, _ in pairs}))
        self.assertIn(("NVDA", "AMD", "Semiconductors"), pairs)

    def test_fdr_across_complete_universe(self):
        result = d.fdr_bh([.001, .02, 1., 1.])
        self.assertAlmostEqual(result[0], .004)
        self.assertAlmostEqual(result[1], .04)
        self.assertEqual(result[-1], 1.)
        self.assertEqual(d.fdr_bh([]), [])

    def test_stale_feed_rejected(self):
        dates = pd.bdate_range(end=datetime.now(timezone.utc).date() - timedelta(days=15), periods=400)
        frame = pd.DataFrame({c: np.linspace(10, 20, 400) for c in ("A", "B", "C")}, index=dates)
        with self.assertRaisesRegex(RuntimeError, "stale"):
            d.select_as_of(frame, datetime.now(timezone.utc))

    def test_partial_current_feed_rejected(self):
        dates = pd.bdate_range(end=datetime.now(timezone.utc).date(), periods=400)
        frame = pd.DataFrame({c: np.linspace(10, 20, 400) for c in ("A", "B", "C", "D")}, index=dates)
        frame.loc[dates[-1], ["B", "C", "D"]] = np.nan
        with self.assertRaisesRegex(RuntimeError, "inconsistent"):
            d.select_as_of(frame, datetime.now(timezone.utc))

    def test_never_scans_unfinished_today_candle(self):
        from zoneinfo import ZoneInfo
        days = pd.bdate_range(end="2026-11-17", periods=400)
        prices = pd.DataFrame({"A": np.linspace(10, 20, 400)}, index=days)
        timezone_ny = ZoneInfo("America/New_York")
        midday = datetime(2026, 11, 17, 13, 0, tzinfo=timezone_ny)
        after_close = datetime(2026, 11, 17, 18, 0, tzinfo=timezone_ny)
        filtered = d.completed_daily_bars(prices, midday)
        self.assertEqual(str(filtered.index[-1].date()), "2026-11-16")
        self.assertEqual(str(d.completed_daily_bars(prices, after_close).index[-1].date()), "2026-11-17")

    def test_measure_uses_prior_training_data_only(self):
        rng = np.random.default_rng(42)
        dates = pd.bdate_range(end="2026-11-17", periods=430)
        trend = np.cumsum(rng.normal(0, .008, len(dates)))
        a = np.exp(4 + trend + rng.normal(0, .006, len(dates)))
        b = np.exp(3 + trend + rng.normal(0, .006, len(dates)))
        frame = pd.DataFrame({"A": a, "B": b}, index=dates)
        result = d.measure("A", "B", "Synthetic peers", frame, str(dates[-1].date()))
        self.assertEqual(result["pair"], "A/B")
        self.assertTrue(np.isfinite(result["z"]))
        self.assertTrue(-1 <= result["correlation"] <= 1)
        self.assertTrue(0 <= result["p"] <= 1)
        self.assertGreater(result["beta"], 0)


if __name__ == "__main__":
    unittest.main()

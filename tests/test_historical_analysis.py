import unittest
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import historical_analysis as ha


class HistoricalAnalysisTests(unittest.TestCase):
    def test_contribution_variants_preserve_unitized_risk(self):
        sample = np.full((10, 36, 3), -0.01)
        no_deposits = ha.simulate_wealth(sample, weekly=0)
        deposits = ha.simulate_wealth(sample, weekly=200)
        np.testing.assert_array_equal(no_deposits['unit'], deposits['unit'])
        np.testing.assert_array_equal(no_deposits['drawdown'], deposits['drawdown'])
        expected = ha.START_CASH
        for _ in range(36):
            expected = expected * .99 + 200 * 52 / 12
        np.testing.assert_allclose(deposits['wealth'][-1], expected)
        rows = ha.summarize(deposits, 'test', dict.fromkeys(ha.TICKERS, .1), weekly=200)
        self.assertEqual(rows[-1]['contributed_usd'], ha.START_CASH + 200 * 52 * 3)

    def test_daily_input_uses_last_price_and_excludes_partial_month(self):
        dates = pd.bdate_range("2022-01-01", "2026-11-06")
        prices = pd.DataFrame(np.arange(len(dates))[:, None] + np.ones((len(dates), 3)),
                              index=dates, columns=ha.TICKERS)
        complete = ha.complete_month_prices(prices, "2026-11-07")
        self.assertEqual(complete.index[-1], pd.Timestamp("2026-10-01"))
        np.testing.assert_array_equal(complete.iloc[-1], prices.loc["2026-10-30"])
        expected = complete.iloc[-1] / complete.iloc[-2] - 1
        np.testing.assert_allclose(ha.monthly_returns(complete).iloc[-1], expected)

    def test_missing_month_is_rejected(self):
        dates = pd.date_range("2020-01-01", periods=60, freq="MS").delete(20)
        prices = pd.DataFrame(100., index=dates, columns=ha.TICKERS)
        with self.assertRaisesRegex(ValueError, "Missing calendar months"):
            ha.complete_month_prices(prices, "2026-11-07")

    def test_invalid_csv_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            for body in ["2020-01-01,1,2,3\n2020-01-01,2,3,4",
                         "2020-01-01,0,2,3", "2020-01-01,1,inf,3",
                         "2020-01-01,1,2,3\n2020-01-02,2,,4"]:
                path.write_text("Date,ARKK,QUAL,SPY\n" + body + "\n")
                with self.assertRaises((ValueError, RuntimeError)):
                    ha.load_prices("2015-01-01", str(path))

    def test_joint_block_sampling_is_reproducible(self):
        returns = np.arange(90, dtype=float).reshape(30, 3) / 10_000
        first = ha.sample_joint_returns(returns, 100, 36, 3, 123)
        second = ha.sample_joint_returns(returns, 100, 36, 3, 123)
        self.assertEqual(first.shape, (100, 36, 3))
        np.testing.assert_array_equal(first, second)

    def test_zero_returns_separate_contributions_from_gains(self):
        sampled = np.zeros((20, 36, 3))
        simulation = ha.simulate_wealth(sampled)
        expected = ha.START_CASH + 36 * ha.MONTHLY_DEPOSIT
        np.testing.assert_allclose(simulation["wealth"][-1], expected)
        np.testing.assert_allclose(simulation["unit"][-1], 1.0)
        np.testing.assert_allclose(simulation["drawdown"][-1], 0.0)

    def test_summary_probability_and_quantile_invariants(self):
        rng = np.random.default_rng(7)
        sampled = np.clip(rng.normal(0.01, 0.04, (2000, 36, 3)), -0.95, None)
        simulation = ha.simulate_wealth(sampled)
        rows = ha.summarize(
            simulation,
            "test",
            {"ARKK": 0.4, "QUAL": 0.2, "SPY": 0.2},
        )
        self.assertEqual(len(rows), 18)
        for row in rows:
            self.assertAlmostEqual(
                row["prob_profitable"] + row["prob_loss"],
                1.0,
                places=12,
            )
            self.assertLessEqual(row["p05"], row["p25"])
            self.assertLessEqual(row["p25"], row["median_ending_value"])
            self.assertLessEqual(row["median_ending_value"], row["p75"])
            self.assertLessEqual(row["p75"], row["p95"])
            self.assertLessEqual(
                row["median_max_drawdown"],
                row["p95_max_drawdown"],
            )


if __name__ == "__main__":
    unittest.main()


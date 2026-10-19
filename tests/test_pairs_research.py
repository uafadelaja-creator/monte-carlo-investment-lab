import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import pairs_research as pr


class PairsResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2019-01-02", periods=950)
        log_b = np.cumsum(rng.normal(0.0003, 0.009, len(dates))) + 4.0
        residual = np.zeros(len(dates))
        for index in range(1, len(dates)):
            residual[index] = 0.88 * residual[index - 1] + rng.normal(0, 0.018)
        log_a = 0.3 + 1.15 * log_b + residual
        spy = 100 * np.exp(np.cumsum(rng.normal(0.00035, 0.010, len(dates))))
        sector = 80 * np.exp(np.cumsum(rng.normal(0.00030, 0.011, len(dates))))
        cls.prices = pd.DataFrame(
            {
                "A": np.exp(log_a),
                "B": np.exp(log_b),
                "SPY": spy,
                "SECTOR": sector,
            },
            index=dates,
        )

    def _backtest(self, fee=10.0):
        return pr.backtest(
            self.prices,
            "A",
            "B",
            ("SPY", "SECTOR"),
            "2022-01-03",
            formation=252,
            z_window=60,
            refit=21,
            entry_z=0.75,
            exit_z=0.25,
            stop_z=4.0,
            p_limit=1.0,
            fee_bps=fee,
            borrow_apr=0.03,
        )

    def test_execution_is_delayed_one_session(self):
        result = self._backtest()
        nonzero = result.index[result["signal_side"] != 0]
        self.assertGreater(len(nonzero), 0)
        for date in nonzero[:10]:
            location = result.index.get_loc(date)
            if location + 1 >= len(result):
                continue
            beta = result.loc[date, "hedge_beta"]
            side = result.loc[date, "signal_side"]
            expected_a = side / (1 + beta)
            self.assertAlmostEqual(
                result.iloc[location + 1]["executed_weight_a"], expected_a, places=12
            )

    def test_costs_reduce_net_return_path(self):
        zero_cost = self._backtest(fee=0.0)
        cost = self._backtest(fee=20.0)
        difference = (
            zero_cost["strategy_return_net"] - cost["strategy_return_net"]
        ).sum()
        self.assertGreater(difference, 0)
        self.assertTrue((cost["turnover_cost"] >= 0).all())

    def test_future_changes_do_not_alter_prior_signals(self):
        baseline = self._backtest()
        altered = self.prices.copy()
        split = altered.index[-40]
        altered.loc[altered.index > split, "A"] *= 1.8
        changed = pr.backtest(
            altered,
            "A",
            "B",
            ("SPY", "SECTOR"),
            "2022-01-03",
            252,
            60,
            21,
            0.75,
            0.25,
            4.0,
            1.0,
            10.0,
            0.03,
        )
        columns = ["signal_side", "zscore", "hedge_beta"]
        pd.testing.assert_frame_equal(
            baseline.loc[:split, columns], changed.loc[:split, columns]
        )

    def test_block_bootstrap_is_reproducible_and_ordered(self):
        result = self._backtest()
        first = pr.block_bootstrap(
            result["strategy_return_net"], paths=1000, block=20, seed=123
        )
        second = pr.block_bootstrap(
            result["strategy_return_net"], paths=1000, block=20, seed=123
        )
        self.assertEqual(first, second)
        self.assertEqual([row["horizon_months"] for row in first], [1, 3, 6, 12, 24, 36])
        for row in first:
            self.assertLessEqual(row["p05_return"], row["p25_return"])
            self.assertLessEqual(row["p25_return"], row["median_return"])
            self.assertLessEqual(row["median_return"], row["p75_return"])
            self.assertLessEqual(row["p75_return"], row["p95_return"])
            self.assertGreaterEqual(row["probability_loss"], 0)
            self.assertLessEqual(row["probability_loss"], 1)
            self.assertLessEqual(row["median_max_drawdown"], row["p95_max_drawdown"])


if __name__ == "__main__":
    unittest.main()


import unittest

import numpy as np

import historical_analysis as ha


class HistoricalAnalysisTests(unittest.TestCase):
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


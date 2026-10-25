import tempfile
import unittest
from pathlib import Path

import pandas as pd

import monitor_stat_arb as monitor


class MonitoringTests(unittest.TestCase):
    def _row(self, observed_on="2026-10-18", protocol="fixed"):
        return pd.DataFrame(
            [
                {
                    "observed_on": observed_on,
                    "data_through": "2026-10-16",
                    "pair": "V/MA",
                    "protocol_sha256": protocol,
                    "adjusted_close_sha256": "prices",
                    "test_sessions": 951,
                    "entries": 2,
                    "exposure_fraction": 0.01,
                    "net_cumulative_return": -0.001,
                    "max_drawdown": -0.01,
                    "twelve_month_median_return": 0.0,
                    "twelve_month_probability_profitable": 0.25,
                    "twelve_month_probability_loss": 0.26,
                    "thirty_six_month_median_return": 0.0,
                    "thirty_six_month_probability_profitable": 0.42,
                    "thirty_six_month_probability_loss": 0.46,
                }
            ]
        )

    def test_ledger_update_is_idempotent(self):
        first = self._row()
        updated = monitor.update_ledger(first, first)
        self.assertEqual(len(updated), 1)

    def test_protocol_change_requires_new_series(self):
        with self.assertRaisesRegex(ValueError, "Protocol fingerprint changed"):
            monitor.update_ledger(self._row(), self._row(protocol="changed"))

    def test_previous_date_ignores_idempotent_current_snapshot(self):
        previous = self._row()
        current = self._row(observed_on="2026-10-25")
        current["data_through"] = "2026-10-23"
        ledger = pd.concat([previous, current], ignore_index=True)
        self.assertEqual(
            monitor.previous_data_date(ledger, "2026-10-23"), "2026-10-16"
        )

    def test_prefix_hash_is_stable_for_same_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            frame = pd.DataFrame(
                {"A": [1.0, 1.1, 1.2]},
                index=pd.to_datetime(["2026-10-15", "2026-10-16", "2026-10-23"]),
            )
            frame.index.name = "Date"
            frame.to_csv(path, float_format="%.10f")
            first = monitor.prefix_sha256(path, "2026-10-16")
            second = monitor.prefix_sha256(path, "2026-10-16")
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

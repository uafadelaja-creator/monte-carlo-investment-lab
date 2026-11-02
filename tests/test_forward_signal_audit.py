import tempfile
import unittest
from pathlib import Path

import pandas as pd

import forward_signal_audit as audit


class ForwardAuditTests(unittest.TestCase):
    def _row(self, key="observation|V/MA|2026-10-30|2026-11-01"):
        return {
            "record_key": key,
            "record_type": "observation",
            "observed_on": "2026-11-01",
            "data_through": "2026-10-30",
            "pair": "V/MA",
            "protocol_sha256": "fixed",
            "source_sha256": "prices",
            "signal_date": "2026-10-30",
            "signal_event": "INITIAL_FLAT",
            "signal_side": 0,
            "signal_state": "flat",
            "execution_status": "not_applicable",
        }

    def test_append_is_idempotent_and_chain_valid(self):
        ledger = audit.append_rows(pd.DataFrame(), [self._row()])
        again = audit.append_rows(ledger, [self._row()])
        self.assertEqual(len(again), 1)
        self.assertTrue(audit.verify_chain(again))

    def test_chain_detects_mutation(self):
        ledger = audit.append_rows(pd.DataFrame(), [self._row()])
        ledger.loc[0, "signal_state"] = "changed"
        self.assertFalse(audit.verify_chain(ledger))

    def test_chain_survives_csv_roundtrip(self):
        ledger = audit.append_rows(pd.DataFrame(), [self._row()])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            ledger.to_csv(path, index=False, float_format="%.12g")
            loaded = pd.read_csv(path, keep_default_na=False)
        self.assertTrue(audit.verify_chain(loaded))

    def test_state_event_labels(self):
        self.assertEqual(audit._event(None, 0), "INITIAL_FLAT")
        self.assertEqual(audit._event(None, 1), "INITIAL_ENTRY")
        self.assertEqual(audit._event(0, -1), "ENTRY")
        self.assertEqual(audit._event(1, -1), "REVERSAL")
        self.assertEqual(audit._event(-1, 0), "EXIT")

    def test_target_weights_are_dollar_neutral_by_gross_normalization(self):
        first, second = audit._target(1, 1.5)
        self.assertAlmostEqual(first, 0.4)
        self.assertAlmostEqual(second, -0.6)
        self.assertAlmostEqual(abs(first) + abs(second), 1.0)


if __name__ == "__main__":
    unittest.main()

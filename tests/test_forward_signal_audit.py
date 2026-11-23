import hashlib
import json
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

    def _write_lifecycle_fixture(self, root: Path, signal_sides=(1, 1)):
        results = root / "results"
        data = root / "data"
        results.mkdir()
        data.mkdir()
        settings = {
            "formation_days": 252,
            "z_lookback": 60,
            "refit_every_days": 21,
            "entry_z": 2.0,
            "exit_z": 0.5,
            "stop_z": 3.5,
            "cointegration_max_p": 0.05,
            "turnover_cost_bps_per_notional_dollar": 10.0,
            "hypothetical_short_borrow_apr": 0.03,
            "execution": "signal after close T; modeled fill at close T+1",
            "price_basis": "vendor-adjusted close",
        }
        report = {
            "pair": ["V", "MA"],
            "test_start": "2023-01-03",
            "settings": settings,
        }
        (results / "V_MA_report.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        dates = pd.to_datetime(["2026-11-13", "2026-11-16"])
        daily = pd.DataFrame(
            {
                "signal_side": signal_sides,
                "hedge_beta": [1.5, 1.5],
                "zscore": [-2.1, -2.2],
                "cointegration_p": [0.04, 0.04],
            },
            index=dates,
        )
        daily.to_csv(results / "V_MA_daily.csv")
        adjusted = pd.DataFrame(
            {"V": [100.0, 101.0], "MA": [200.0, 202.0]}, index=dates
        )
        market_frames = {
            "adjusted_close": adjusted,
            "raw_open": adjusted - 0.5,
            "raw_high": adjusted + 1.0,
            "raw_low": adjusted - 1.0,
            "raw_close": adjusted,
            "volume": pd.DataFrame(
                {"V": [1_000_000, 1_100_000], "MA": [900_000, 950_000]},
                index=dates,
            ),
        }
        for name, frame in market_frames.items():
            frame.to_csv(data / f"{name}.csv")
        price_hash = hashlib.sha256(
            (data / "adjusted_close.csv").read_bytes()
        ).hexdigest()
        (data / "download_manifest.json").write_text(
            json.dumps(
                {
                    "latest_date": "2026-11-16",
                    "file_sha256": {"adjusted_close.csv": price_hash},
                }
            ),
            encoding="utf-8",
        )
        protocol, protocol_sha = audit._protocol({"V/MA": report})
        return results, data, protocol, protocol_sha, price_hash

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

    def test_entry_resolves_once_on_next_completed_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results, data, protocol, protocol_sha, price_hash = (
                self._write_lifecycle_fixture(root)
            )
            entry = self._row()
            entry.update(
                {
                    "record_key": "observation|V/MA|2026-11-13|2026-11-15",
                    "observed_on": "2026-11-15",
                    "data_through": "2026-11-13",
                    "protocol_sha256": protocol_sha,
                    "source_sha256": price_hash,
                    "signal_date": "2026-11-13",
                    "signal_event": "ENTRY",
                    "signal_side": 1,
                    "signal_state": "long_first_short_second",
                    "execution_status": "pending_next_session_close_audit",
                }
            )
            ledger = audit.append_rows(pd.DataFrame(), [entry])

            records, observed_protocol, observed_sha = audit.build_records(
                results, data, ledger, "2026-11-17"
            )
            self.assertEqual(observed_protocol, protocol)
            self.assertEqual(observed_sha, protocol_sha)
            updated = audit.append_rows(ledger, records)
            resolutions = updated.loc[updated["record_type"] == "resolution"]
            self.assertEqual(len(resolutions), 1)
            resolution = resolutions.iloc[0]
            self.assertEqual(resolution["execution_date"], "2026-11-16")
            self.assertEqual(float(resolution["adjusted_price_a"]), 101.0)
            self.assertEqual(float(resolution["raw_close_b"]), 202.0)
            self.assertTrue(audit.verify_chain(updated))

            rerun_records, _, _ = audit.build_records(
                results, data, updated, "2026-11-18"
            )
            rerun = audit.append_rows(updated, rerun_records)
            self.assertEqual(
                len(rerun.loc[rerun["record_type"] == "resolution"]), 1
            )
            self.assertTrue(audit.verify_chain(rerun))

    def test_exit_is_not_resolved_and_reversal_resolves_once(self):
        for event, side, state, expected_resolutions in (
            ("EXIT", 0, "flat", 0),
            ("REVERSAL", -1, "short_first_long_second", 1),
        ):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                results, data, _, protocol_sha, price_hash = (
                    self._write_lifecycle_fixture(root, signal_sides=(side, side))
                )
                observation = self._row()
                observation.update(
                    {
                        "record_key": f"observation|V/MA|2026-11-13|{event}",
                        "observed_on": "2026-11-15",
                        "data_through": "2026-11-13",
                        "protocol_sha256": protocol_sha,
                        "source_sha256": price_hash,
                        "signal_date": "2026-11-13",
                        "signal_event": event,
                        "signal_side": side,
                        "signal_state": state,
                        "execution_status": (
                            "pending_next_session_close_audit"
                            if event == "REVERSAL"
                            else "not_applicable"
                        ),
                    }
                )
                ledger = audit.append_rows(pd.DataFrame(), [observation])
                records, _, _ = audit.build_records(
                    results, data, ledger, "2026-11-17"
                )
                updated = audit.append_rows(ledger, records)
                resolutions = updated.loc[updated["record_type"] == "resolution"]
                self.assertEqual(len(resolutions), expected_resolutions)
                self.assertTrue(audit.verify_chain(updated))

                rerun_records, _, _ = audit.build_records(
                    results, data, updated, "2026-11-18"
                )
                rerun = audit.append_rows(updated, rerun_records)
                self.assertEqual(
                    len(rerun.loc[rerun["record_type"] == "resolution"]),
                    expected_resolutions,
                )
                self.assertTrue(audit.verify_chain(rerun))


if __name__ == "__main__":
    unittest.main()

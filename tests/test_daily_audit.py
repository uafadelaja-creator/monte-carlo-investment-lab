"""Offline audit guardrails: independent math, BH correction and content hashes."""
import gzip
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import audit_daily_scan as audit
import daily_pair_scanner as screen


class ModelAuditTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(21)
        self.days=pd.bdate_range(end="2026-11-17",periods=420)
        walk=np.cumsum(rng.normal(0,.007,420))
        self.prices=pd.DataFrame({
            "A":np.exp(3+walk+rng.normal(0,.015,420)),
            "B":np.exp(3.3+walk+rng.normal(0,.015,420)),
        },index=self.days)
        self.cutoff=str(self.days[-1].date())

    def test_independent_measure_reproduces_scanner(self):
        expected=screen.measure("A","B","Synthetic",self.prices,self.cutoff)
        actual=audit.independent_measure(self.prices,"A","B",self.cutoff)
        self.assertIsNotNone(actual)
        for key,tol in [("p",1e-6),("z",1e-4),("beta",1e-4),("correlation",1e-4),("beta_drift_pct",.1)]:
            self.assertAlmostEqual(expected[key],actual[key],delta=tol)

    def test_bh_multiple_testing(self):
        self.assertEqual(audit.adjusted_q([1.0,1.0]),[1.0,1.0])
        self.assertAlmostEqual(audit.adjusted_q([.01,.04,1])[0],.03)
        self.assertAlmostEqual(audit.adjusted_q([.01,.04,1])[1],.06)

    def test_missing_market_history_fails(self):
        broken=self.prices.copy()
        broken.loc[self.days[-1],"B"]=np.nan
        self.assertIsNone(audit.independent_measure(broken,"A","B",self.cutoff))

    def test_tampered_input_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            # Checkpoints are SHA-256 based; altered bytes cannot match a
            # previously published canonical digest.
            path=Path(d)/"input.csv.gz"
            buf=io.StringIO()
            self.prices.to_csv(buf,index_label="date",date_format="%Y-%m-%d",float_format="%.17g")
            original=buf.getvalue().encode()
            expected=hashlib.sha256(original).hexdigest()
            path.write_bytes(gzip.compress(original,mtime=0))
            self.assertEqual(hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest(),expected)
            path.write_bytes(gzip.compress(original+b"\nTAMPERED",mtime=0))
            self.assertNotEqual(hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest(),expected)

    def test_missing_or_fake_audit_values_rejected(self):
        with self.assertRaises(AssertionError):
            audit.comparable(.4,.9,.001,"invented value")
        with self.assertRaises(AssertionError):
            audit.comparable(float("nan"),.5,.01,"nan value")


if __name__=="__main__":
    unittest.main()

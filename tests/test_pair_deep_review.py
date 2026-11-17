"""Offline regression checks: selected pairs, dated ledger, historical replay."""
import unittest
from datetime import datetime, timezone
import numpy as np
import pandas as pd

import daily_pair_scanner as scan
import pair_deep_review as deep


class DeepReviewTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(140)
        idx = pd.bdate_range(end="2026-11-17", periods=440)
        core = np.cumsum(rng.normal(0, .011, len(idx)))
        self.prices = pd.DataFrame({
            "A": np.exp(3.5 + core + rng.normal(0, .025, len(idx))),
            "B": np.exp(3.2 + core + rng.normal(0, .025, len(idx))),
            "C": np.exp(3.9 + core + rng.normal(0, .023, len(idx))),
            "D": np.exp(3.1 + core + rng.normal(0, .022, len(idx))),
        }, index=idx)
        self.today = datetime(2026, 11, 17, 23, 30, tzinfo=timezone.utc)
        self.pairs = []
        for a,b,industry,status,p,q in [
            ("A", "B", "Alpha", "preliminary_watch", .02, .4),
            ("A", "C", "Alpha", "not_qualified", .5, 1),
            ("B", "C", "Beta", "not_qualified", .6, 1),
            ("C", "D", "Gamma", "not_qualified", .7, 1),
        ]:
            row = scan.measure(a,b,industry,self.prices,str(self.prices.index[-1].date()))
            row.update(status=status,p=p,q=q,
                       gates={"cointegration":p<.05,"correlation":True,
                              "deviation":False,"fdr":q<.05,"beta_stable":True})
            self.pairs.append(row)
        self.snapshot = {"as_of":"2026-11-17","pairs":self.pairs}

    def test_two_distinct_reviews_with_retrospective_diagnostics(self):
        result = deep.update_history(self.snapshot,self.prices,self.today)
        self.assertEqual(result["total_reviews"],2)
        self.assertEqual(len({r["pair"] for r in result["records"]}),2)
        self.assertEqual(result["records"][0]["review_date"],"2026-11-17")
        for row in result["records"]:
            self.assertTrue(row["z_history"])
            self.assertIn("retrospective_replay",row)
            self.assertIn("half_window_eg_p",row["metrics"])
            self.assertIn("verdict",row)

    def test_same_day_rerun_is_idempotent(self):
        first = deep.update_history(self.snapshot,self.prices,self.today)
        second = deep.update_history(self.snapshot,self.prices,self.today,first)
        self.assertEqual(first["records"],second["records"])

    def test_next_day_rotates_to_unreviewed_pairs(self):
        first=deep.update_history(self.snapshot,self.prices,self.today)
        tomorrow=datetime(2026,11,18,23,30,tzinfo=timezone.utc)
        second=deep.update_history(self.snapshot,self.prices,tomorrow,first)
        self.assertEqual(second["total_reviews"],4)
        self.assertEqual(second["unique_pairs_reviewed"],4)

    def test_no_duplicate_day_and_pair_allowed(self):
        first=deep.update_history(self.snapshot,self.prices,self.today)
        history={"schema_version":1,"records":[first["records"][0],first["records"][0]]}
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            deep.update_history(self.snapshot,self.prices,self.today,history)

    def test_replay_uses_forward_fill_without_same_day_entry(self):
        output=deep.replay(self.prices[["A","B"]])
        for example in output["examples"]:
            self.assertLess(example["signal_date"],example["entry_date"])
            self.assertLess(example["entry_date"],example["exit_date"])
        self.assertEqual(output["hold_sessions"],5)
        self.assertIn("RETROSPECTIVE",output["label"])


if __name__=="__main__":
    unittest.main()

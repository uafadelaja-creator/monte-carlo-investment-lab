"""Synthetic evidence and returns exclusively for validation, not a real backtest."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.shariah_lab.point_in_time import PITError, backtest_pit, load_pit_history
from src.shariah_lab.portfolio import sector_return_attribution, portfolio_returns
from src.shariah_lab.screening import load_registry


def all_test_returns(months=60):
    dates = pd.date_range("2021-01-31", periods=months, freq="ME")
    # Synthetic returns are deliberately constants and obvious tests.
    return pd.DataFrame({"AAPL": [.01]*months, "NVDA": [.03]*months, "MSFT": [-.01]*months, "GOOGL": [.02]*months, "AVGO": [.00]*months}, index=dates)


def monthly_evidence():
    rows = []
    # Pre-month-end snapshot every month. Jan 2020 through end 2026.
    for d in pd.date_range("2020-12-31", "2025-12-31", freq="ME"):
        for ticker in ("AAPL", "NVDA", "MSFT", "GOOGL", "AVGO"):
            rows.append({"as_of": d.strftime("%Y-%m-%d"), "ticker": ticker, "eligible": "yes", "source_name": "SYNTHETIC TEST SOURCE", "source_url": "https://example.com/fixture", "weight_hint": 1.0})
    return load_pit_history(pd.DataFrame(rows).to_csv(index=False))


def test_pit_equal_weight_exact_returns():
    r = all_test_returns()
    strategy, audit = backtest_pit(r, monthly_evidence())
    assert len(strategy) == len(r)
    assert np.allclose(strategy, np.mean([.01,.03,-.01,.02,0]))
    assert audit["holdings"].eq(5).all()
    assert (audit["screen_as_of"].dt.to_period("M") < audit.index.to_period("M")).all()


def test_pit_future_eligibility_cannot_change_previous_month():
    r = all_test_returns()
    evidence = monthly_evidence()
    original, audit = backtest_pit(r, evidence)
    last_date = evidence.as_of.max()
    evidence.loc[(evidence.as_of == last_date) & (evidence.ticker == "NVDA"), "eligible"] = False
    amended, _ = backtest_pit(r, evidence)
    assert np.allclose(original.values, amended.values)


def test_pit_missing_historical_records_cannot_be_filled_in():
    evidence = monthly_evidence()
    # Remove a long interval of snapshots, generating > 65-day evidence age.
    evidence = evidence[~evidence.as_of.between("2022-01-01", "2022-07-31")]
    with pytest.raises(PITError, match="Missing sufficiently recent"):
        backtest_pit(all_test_returns(), evidence)


def test_pit_rejects_missing_source():
    evidence = monthly_evidence()
    evidence.loc[0, "source_url"] = "my spreadsheet"
    with pytest.raises(PITError, match="HTTPS"):
        load_pit_history(evidence.to_csv(index=False))


def test_pit_rejects_future_dated_records():
    evidence = monthly_evidence()
    evidence.loc[0, "as_of"] = "2099-01-01"
    with pytest.raises(PITError, match="future"):
        load_pit_history(evidence.to_csv(index=False))


def test_sector_contributions_sum_to_portfolio_return():
    h = load_registry().set_index("ticker").loc[["AAPL", "NVDA", "MSFT", "GOOGL", "AVGO"]].reset_index()
    weights = pd.Series(.2, index=h.ticker)
    ret = all_test_returns()
    attrib = sector_return_attribution(ret, weights, h)
    port = portfolio_returns(ret, weights)
    assert np.allclose(attrib.sum(axis=1), port)
    assert len(attrib.columns) > 1

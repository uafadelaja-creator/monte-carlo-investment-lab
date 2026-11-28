from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.shariah_lab.data import DataError, load_prices_csv, monthly_returns, to_csv_bytes, trim_incomplete_last_month, validate_prices


def sample_prices():
    dates = pd.date_range("2022-01-03", "2025-01-03", freq="B")
    n = len(dates)
    return pd.DataFrame({"SPY": np.linspace(100, 150, n), "SPUS": np.linspace(90, 140, n), "HLAL": np.linspace(80, 130, n)}, index=dates)


def test_csv_round_trip():
    original = sample_prices()
    restored = load_prices_csv(to_csv_bytes(original))
    assert tuple(restored.columns) == ("SPY", "SPUS", "HLAL")
    assert restored.index[0].date() == original.index[0].date()
    assert np.allclose(restored.to_numpy(), original.to_numpy())
    m = monthly_returns(restored)
    assert len(m) >= 24
    assert (m > 0).all().all()


def test_no_missing_tickers():
    with pytest.raises(DataError, match="Missing ticker"):
        validate_prices(sample_prices().drop(columns="SPUS"))


def test_csv_requires_date():
    with pytest.raises(DataError, match="Date"):
        load_prices_csv(b"SPY,SPUS,HLAL\n1,2,3\n")


def test_missing_and_invalid_prices():
    df = sample_prices()
    df.iloc[0, 0] = -1
    with pytest.raises(DataError, match="positive"):
        validate_prices(df)


def test_reject_duplicate_dates():
    df = sample_prices()
    duplicated = pd.concat([df, df.iloc[[0]]])
    with pytest.raises(DataError, match="Duplicate dates"):
        validate_prices(duplicated)


def test_short_history_rejected():
    df = sample_prices().iloc[:60]
    with pytest.raises(DataError, match="At least"):
        validate_prices(df)


def test_partial_last_month_is_excluded():
    prices = sample_prices()
    # Selected date range ends on a business day in early January (not month-end).
    result = trim_incomplete_last_month(prices)
    assert result.index[-1].month == 12
    assert len(monthly_returns(prices)) == len(monthly_returns(result))

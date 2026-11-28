from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.shariah_lab.data import DataError, load_universe_csv, validate_universe_prices
from src.shariah_lab.model import moving_block_bootstrap, simulation_summary
from src.shariah_lab.portfolio import (
    PortfolioError, benchmark_diagnostics, concentration, metric_table,
    optimization_weights, portfolio_returns, purification_worksheet,
    rolling_annualized, sector_allocation, walk_forward, worst_benchmark_months,
)
from src.shariah_lab.report import build_report
from src.shariah_lab.screening import load_registry


def stock_returns(n=70):
    dates = pd.date_range("2020-01-31", periods=n, freq="ME")
    i = np.arange(n)
    return pd.DataFrame({
        "AAPL": .006 + .018 * np.sin(i),
        "NVDA": .015 + .035 * np.cos(i * .82),
        "MSFT": .007 + .015 * np.sin(i * .53),
        "XOM": .004 + .027 * np.cos(i * .48),
        "PG": .005 + .009 * np.sin(i * .38),
    }, index=dates)


def test_portfolio_exact_weighted_return():
    x = pd.DataFrame({"AAPL": [0.10]*24, "MSFT": [-.05]*24})
    r = portfolio_returns(x, {"AAPL": .6, "MSFT": .4})
    assert np.allclose(r, .04)


def test_bad_weights_prohibited():
    x = stock_returns()
    with pytest.raises(PortfolioError, match="100%"):
        portfolio_returns(x, {name: .1 for name in x.columns})
    with pytest.raises(PortfolioError, match="match"):
        portfolio_returns(x, {"OTHER": 1})


def test_min_variance_optimizer_constraints():
    x = stock_returns()
    w = optimization_weights(x, objective="Minimum variance", max_weight=.35)
    assert np.isclose(w.sum(), 1)
    assert (w >= -1e-8).all() and (w <= .3500001).all()
    assert len(w) == 5


def test_max_sharpe_optimizer_constraints():
    x = stock_returns()
    w = optimization_weights(x, objective="Maximum Sharpe", max_weight=.4)
    assert np.isclose(w.sum(), 1)
    assert (w >= -1e-8).all() and (w <= .4000001).all()


def test_unfeasible_optimizer_cap_rejected():
    with pytest.raises(PortfolioError, match="Maximum weight"):
        optimization_weights(stock_returns(), max_weight=.1)


def test_optimizer_is_reproducible():
    x = stock_returns()
    a = optimization_weights(x, max_weight=.3)
    b = optimization_weights(x, max_weight=.3)
    assert np.array_equal(a.values, b.values)


def test_metrics_and_benchmark_diagnostics():
    x = stock_returns()
    frame = pd.DataFrame({"SPY": x.AAPL, "HLAL": x.MSFT, "Custom basket": x.PG})
    metrics = metric_table(frame)
    assert set(metrics.index) == set(frame.columns)
    assert np.isfinite(metrics.loc["SPY", "CAGR"])
    assert metrics.loc["SPY", "Max monthly drawdown"] <= 0
    d = benchmark_diagnostics(frame)
    assert abs(d.loc["SPY", "Beta vs SPY"] - 1) < 1e-10
    assert abs(d.loc["SPY", "Tracking error (annual)"]) < 1e-10


def test_concentration_and_sector_weights():
    h = load_registry()
    weights = pd.Series(.5, index=["AAPL", "JNJ"])
    assert concentration(weights)["Effective holdings"] == 2
    s = sector_allocation(weights, h)
    assert np.isclose(s.sum(), 1)
    assert set(s.index) == {"Information Technology", "Health Care"}


def test_walk_forward_never_uses_future_month_returns_for_prior_weights():
    x = stock_returns()
    before, before_w = walk_forward(x, train_months=36, rebalance_months=6, max_weight=.4)
    altered = x.copy()
    altered.iloc[-1, :] = altered.iloc[-1, :] * -2
    after, after_w = walk_forward(altered, train_months=36, rebalance_months=6, max_weight=.4)
    assert np.allclose(before_w.values, after_w.values)
    assert np.allclose(before.iloc[:-1], after.iloc[:-1])
    assert len(before) == len(x) - 36


def test_rolling_and_stress():
    x = stock_returns()
    x = x.rename(columns={"AAPL": "SPY"})
    roll = rolling_annualized(x, 12)
    assert roll.iloc[:11].isna().all().all()
    assert np.isfinite(roll.iloc[12].values).all()
    worst = worst_benchmark_months(x, n=3)
    assert len(worst) == 3
    assert set(worst.index) == set(x.SPY.nsmallest(3).index)


def test_purification_requires_actual_input_rates():
    data = pd.DataFrame({"ticker": ["AAPL", "MSFT"], "shares": [10, 3], "dividend_per_share": [.50, 1.00], "purification_fraction": [.03, .05]})
    worksheet = purification_worksheet(data)
    assert np.allclose(worksheet.purification_amount, [.15, .15])
    data.loc[0, "purification_fraction"] = 1.5
    with pytest.raises(PortfolioError, match="between 0 and 1"):
        purification_worksheet(data)


def test_bootstrap_generic_four_portfolios_and_pairing():
    x = stock_returns(60)
    base = x.AAPL*.6 + x.MSFT*.4
    frame = pd.DataFrame({"SPY": base, "SPUS": base*.9, "HLAL": base*1.1, "Custom basket": base*1.2})
    output = moving_block_bootstrap(frame, years=2, n_sims=120, initial=5000, monthly_contribution=100)
    assert output.terminal.shape == (120, 4)
    assert "Custom basket" in simulation_summary(output).index


def test_universe_csv_accepts_extended_stocks():
    dates = pd.date_range("2020-01-02", "2024-01-02", freq="B")
    n = len(dates)
    p = pd.DataFrame({name: np.linspace(100, 200, n) for name in ["SPY", "SPUS", "HLAL", "AAPL", "MSFT"]}, index=dates)
    p.index.name = "Date"
    back = load_universe_csv(p.to_csv().encode())
    assert list(back.columns) == list(p.columns)
    assert len(back) == n


def test_extended_csv_missing_required_etf_rejected():
    data = "Date,SPY,HLAL,AAPL\n2021-01-01,1,2,3"
    with pytest.raises(DataError, match="missing"):
        load_universe_csv(data)


def test_no_forward_fill_of_missing_prices():
    dates = pd.date_range("2020-01-02", "2024-01-02", freq="B")
    p = pd.DataFrame({name: 100.0 for name in ["SPY", "SPUS", "HLAL", "AAPL"]}, index=dates)
    p.loc[dates[50], "AAPL"] = np.nan
    out = validate_universe_prices(p)
    assert len(out) == len(dates) - 1
    assert dates[50] not in out.index


def test_report_contains_data_dates_and_cautions():
    x = stock_returns(60)
    r = pd.DataFrame({"SPY": x.AAPL, "SPUS": x.MSFT, "HLAL": x.XOM, "Custom basket": x.PG}, index=x.index)
    holdings = load_registry()
    weights = pd.Series([.5, .5], index=["AAPL", "JNJ"])
    report = build_report(r, "TEST FIXTURE, NOT MARKET DATA", holdings=holdings, weights=weights, as_of="2026-11-25")
    assert "2026-11-25" in report
    assert "TEST FIXTURE, NOT MARKET DATA" in report
    assert "2026-11-24" in report
    assert "look-ahead bias" in report.lower()
    assert "not" in report.lower()

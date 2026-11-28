from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.shariah_lab.model import (
    fan_percentiles,
    moving_block_bootstrap,
    performance_metrics,
    simulation_summary,
)


def example_returns(n=36):
    dates = pd.date_range("2020-01-31", periods=n, freq="ME")
    base = np.array([0.01, -0.02, 0.015, 0.025, -0.005, 0.03] * (n // 6 + 1))[:n]
    return pd.DataFrame({"SPY": base, "SPUS": base * 1.15, "HLAL": base * 0.8}, index=dates)


def test_bootstrap_reproducible_and_shape():
    kwargs = dict(years=2, n_sims=250, initial=10000, monthly_contribution=250, block_months=3, seed=7)
    a = moving_block_bootstrap(example_returns(), **kwargs)
    b = moving_block_bootstrap(example_returns(), **kwargs)
    assert a.paths.shape == (250, 25, 3)
    assert np.array_equal(a.paths, b.paths)
    assert a.contributions == 16000
    assert np.all(a.nav_drawdowns <= 0)
    assert np.all(a.nav_drawdowns >= -1)


def test_constant_market_monthly_deposits_and_zero_drawdown():
    returns = pd.DataFrame({"SPY": [0.0] * 30, "SPUS": [0.0] * 30, "HLAL": [0.0] * 30})
    result = moving_block_bootstrap(returns, 1, 100, 1000, 100, 6, 42)
    assert np.all(result.terminal == 2200)
    assert np.all(result.nav_drawdowns == 0)
    summary = simulation_summary(result)
    assert (summary["Below contributions (%)"] == 0).all()
    assert (summary.loc[["SPUS", "HLAL"], "Beats SPY (%)"] == 0).all()
    assert np.isnan(summary.loc["SPY", "Beats SPY (%)"])


def test_joint_returns_preserve_same_resampled_months():
    # One-month blocks and exact 2x/3x relations to SPY ensure each historical
    # index is sampled identically for all assets and not independently.
    r = pd.DataFrame({"SPY": np.arange(1, 37) / 10000})
    r["SPUS"] = 2 * r["SPY"]
    r["HLAL"] = 3 * r["SPY"]
    sim = moving_block_bootstrap(r, 1, 100, 1000, 0, 1, 1)
    observed = sim.paths[:, 1:, :] / sim.paths[:, :-1, :] - 1
    assert np.allclose(observed[:, :, 1], 2 * observed[:, :, 0])
    assert np.allclose(observed[:, :, 2], 3 * observed[:, :, 0])


def test_single_full_block_repeatable_returns_and_fan():
    r = example_returns(24)
    sim = moving_block_bootstrap(r, 2, 100, 1000, 0, 24, 999)
    assert np.all(sim.terminal == sim.terminal[0])
    fan = fan_percentiles(sim, "SPUS")
    assert fan.shape == (25, 4)
    assert np.allclose(fan["P10"], fan["P90"])
    with pytest.raises(ValueError, match="Ticker"):
        fan_percentiles(sim, "INVALID")


def test_bad_settings_are_rejected():
    r = example_returns()
    with pytest.raises(ValueError, match="Block length"):
        moving_block_bootstrap(r, 10, 100, 100, 100, 50)
    with pytest.raises(ValueError, match="nonzero"):
        moving_block_bootstrap(r, 10, 100, 0, 0)
    with pytest.raises(ValueError, match="100–100,000"):
        moving_block_bootstrap(r, 1, 99, 100, 0)


def test_performance_metrics_flat_market_and_risk_free_zero():
    # Use daily timestamps with a multi-year span so elapsed-time CAGR is defined.
    dates = pd.date_range("2022-01-03", "2025-01-03", freq="B")
    df = pd.DataFrame(100.0, index=dates, columns=["SPY", "SPUS", "HLAL"])
    metrics = performance_metrics(df)
    assert (metrics["Total return"] == 0).all()
    assert (metrics["Max drawdown"] == 0).all()
    assert (metrics["CAGR"] == 0).all()
    assert metrics["Sharpe"].isna().all()

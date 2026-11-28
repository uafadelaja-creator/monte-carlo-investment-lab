"""Paired moving-block bootstrap and portfolio performance metrics.

Every asset uses the same resampled month index, preserving observed
contemporaneous return relationships.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import TICKERS, trim_incomplete_last_month


@dataclass(frozen=True)
class Simulation:
    tickers: tuple[str, ...]
    paths: np.ndarray  # (simulation, months+1, asset), with deposits
    nav_drawdowns: np.ndarray  # (simulation, asset), deposits excluded
    contributions: float
    months: int

    @property
    def terminal(self) -> np.ndarray:
        return self.paths[:, -1, :]


def performance_metrics(prices: pd.DataFrame, annual_rf: float = 0.0) -> pd.DataFrame:
    """Basic ETF total-return metrics, aligned to a shared observation period."""
    if not -0.99 < annual_rf < 2.0:
        raise ValueError("Annual risk-free rate is outside supported range.")
    prices = trim_incomplete_last_month(prices)
    monthly = prices.resample("ME").last().pct_change(fill_method=None).dropna()
    if len(monthly) < 2:
        raise ValueError("At least two monthly return observations are needed.")
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    monthly_rf = (1 + annual_rf) ** (1 / 12) - 1
    output = {}
    for ticker in TICKERS:
        series = prices[ticker]
        rm = monthly[ticker].to_numpy(dtype=float)
        excess = rm - monthly_rf
        sigma = float(np.std(rm, ddof=1))
        downside = float(np.sqrt(np.mean(np.minimum(excess, 0.0) ** 2)))
        cagr = float((series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1)
        nav = series / series.iloc[0]
        dd = float((nav / nav.cummax() - 1).min())
        output[ticker] = {
            "CAGR": cagr,
            "Annual volatility": sigma * np.sqrt(12),
            "Sharpe": float(np.mean(excess) / sigma * np.sqrt(12)) if sigma > 0 else np.nan,
            "Sortino": float(np.mean(excess) / downside * np.sqrt(12)) if downside > 0 else np.nan,
            "Max drawdown": dd,
            "Total return": float(series.iloc[-1] / series.iloc[0] - 1),
        }
    return pd.DataFrame.from_dict(output, orient="index")


def moving_block_bootstrap(
    returns: pd.DataFrame,
    years: int,
    n_sims: int,
    initial: float,
    monthly_contribution: float,
    block_months: int = 6,
    seed: int = 42,
) -> Simulation:
    """Simulate joint ETF returns with monthly end-of-month contributions.

    Each simulated path is a sequence of whole historical blocks drawn with
    replacement. This is a *scenario model*, not a calibrated price forecast.
    """
    tickers = tuple(returns.columns)
    if "SPY" not in tickers or len(tickers) < 2 or len(tickers) != len(set(tickers)):
        raise ValueError("Simulations need SPY and at least one distinct comparison asset.")
    data = returns.to_numpy(dtype=float)
    n_obs, n_assets = data.shape
    if n_obs < 24 or np.any(~np.isfinite(data)) or np.any(data <= -1):
        raise ValueError("Require at least 24 clean monthly return observations above -100%.")
    if not (1 <= years <= 40 and 100 <= n_sims <= 100_000):
        raise ValueError("Use 1–40 years and 100–100,000 simulations.")
    if not (1 <= block_months <= n_obs):
        raise ValueError("Block length must be between 1 and the number of monthly observations.")
    if initial < 0 or monthly_contribution < 0 or initial + monthly_contribution <= 0:
        raise ValueError("Provide a nonzero, nonnegative investment or contribution.")

    months = 12 * years
    num_blocks = int(np.ceil(months / block_months))
    rng = np.random.default_rng(seed)
    start_indices = rng.integers(0, n_obs - block_months + 1, size=(n_sims, num_blocks))
    block_indices = start_indices[:, :, None] + np.arange(block_months)[None, None, :]
    indices = block_indices.reshape(n_sims, -1)[:, :months]
    future_returns = data[indices]  # identical index draws across the three ETFs

    paths = np.empty((n_sims, months + 1, n_assets), dtype=float)
    paths[:, 0, :] = initial
    nav = np.ones((n_sims, n_assets), dtype=float)
    nav_peaks = nav.copy()
    worst_drawdown = np.zeros((n_sims, n_assets), dtype=float)
    for month in range(months):
        month_return = future_returns[:, month, :]
        paths[:, month + 1, :] = paths[:, month, :] * (1.0 + month_return) + monthly_contribution
        nav *= 1.0 + month_return
        nav_peaks = np.maximum(nav_peaks, nav)
        worst_drawdown = np.minimum(worst_drawdown, nav / nav_peaks - 1.0)

    return Simulation(
        tickers=tickers,
        paths=paths,
        nav_drawdowns=worst_drawdown,
        contributions=initial + monthly_contribution * months,
        months=months,
    )


def simulation_summary(result: Simulation) -> pd.DataFrame:
    summary = {}
    terminal = result.terminal
    spy_index = result.tickers.index("SPY")
    for i, ticker in enumerate(result.tickers):
        values = terminal[:, i]
        summary[ticker] = {
            "10th percentile ($)": np.percentile(values, 10),
            "Median ($)": np.percentile(values, 50),
            "90th percentile ($)": np.percentile(values, 90),
            "Below contributions (%)": 100.0 * np.mean(values < result.contributions),
            "30%+ NAV drawdown (%)": 100.0 * np.mean(result.nav_drawdowns[:, i] <= -0.30),
            "Beats SPY (%)": (
                100.0 * np.mean(values > terminal[:, spy_index]) if ticker != "SPY" else np.nan
            ),
        }
    return pd.DataFrame.from_dict(summary, orient="index")


def fan_percentiles(result: Simulation, ticker: str) -> pd.DataFrame:
    if ticker not in result.tickers:
        raise ValueError(f"Ticker must be one of {result.tickers}.")
    asset = result.paths[:, :, result.tickers.index(ticker)]
    p = np.percentile(asset, [10, 50, 90], axis=0)
    return pd.DataFrame({"Month": np.arange(result.months + 1), "P10": p[0], "P50": p[1], "P90": p[2]})

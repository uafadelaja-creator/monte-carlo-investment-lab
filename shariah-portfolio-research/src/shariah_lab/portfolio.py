"""Backtest diagnostics and constrained portfolio optimization.

CRITICAL: A basket selected from a 2026 holdings snapshot is a retrospective
exposure study before the snapshot date, not an investable historical backtest.
No stock-level Shariah certification is performed here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


class PortfolioError(ValueError):
    pass


def clean_return_matrix(returns: pd.DataFrame, minimum: int = 24) -> pd.DataFrame:
    if not isinstance(returns, pd.DataFrame) or returns.empty or len(returns) < minimum:
        raise PortfolioError(f"At least {minimum} monthly return rows are required.")
    if returns.columns.duplicated().any():
        raise PortfolioError("Duplicate tickers detected.")
    try:
        array = returns.to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise PortfolioError("Return observations must be numeric.") from exc
    if np.any(~np.isfinite(array)) or np.any(array <= -1):
        raise PortfolioError("Returns must be finite and greater than -100%.")
    return returns.astype(float)


def portfolio_returns(asset_returns: pd.DataFrame, weights: pd.Series | dict) -> pd.Series:
    """End-of-month rebalanced, fully invested portfolio; before trading costs."""
    asset_returns = clean_return_matrix(asset_returns, minimum=1)
    weights = pd.Series(weights, dtype=float)
    if not set(asset_returns.columns) == set(weights.index):
        raise PortfolioError("Portfolio holdings and return columns must match exactly.")
    weights = weights.reindex(asset_returns.columns)
    if (weights < -1e-9).any() or not np.isfinite(weights).all() or not np.isclose(weights.sum(), 1.0, atol=1e-6):
        raise PortfolioError("Weights must be nonnegative and sum to 100%.")
    result = asset_returns.dot(weights)
    result.name = "Custom basket"
    return result


def metric_table(returns: pd.DataFrame, annual_rf: float = 0.0) -> pd.DataFrame:
    """Apples-to-apples metrics using *monthly* portfolio/ETF return series."""
    clean_return_matrix(returns)
    if not -0.99 < annual_rf < 2.0:
        raise PortfolioError("Risk-free assumption is outside supported range.")
    monthly_rf = (1 + annual_rf) ** (1 / 12) - 1
    output = {}
    for name in returns.columns:
        r = returns[name].astype(float)
        excess = r - monthly_rf
        sigma = r.std(ddof=1)
        downside = np.sqrt(np.mean(np.minimum(excess, 0) ** 2))
        wealth = (1.0 + r).cumprod()
        wealth_with_zero = pd.concat([pd.Series([1.0]), wealth.reset_index(drop=True)], ignore_index=True)
        drawdown = (wealth_with_zero / wealth_with_zero.cummax() - 1).min()
        output[name] = {
            "CAGR": float(wealth.iloc[-1] ** (12.0 / len(r)) - 1.0),
            "Annual volatility": float(sigma * np.sqrt(12)),
            "Sharpe": float(excess.mean() / sigma * np.sqrt(12)) if sigma > 1e-12 else np.nan,
            "Sortino": float(excess.mean() / downside * np.sqrt(12)) if downside > 1e-12 else np.nan,
            "Max monthly drawdown": float(drawdown),
            "Total return": float(wealth.iloc[-1] - 1.0),
        }
    return pd.DataFrame.from_dict(output, orient="index")


def benchmark_diagnostics(returns: pd.DataFrame, benchmark: str = "SPY") -> pd.DataFrame:
    clean_return_matrix(returns)
    if benchmark not in returns:
        raise PortfolioError("Benchmark ticker not found.")
    b = returns[benchmark]
    vb = b.var(ddof=1)
    result = {}
    for name in returns.columns:
        a = returns[name]
        beta = a.cov(b) / vb if vb > 0 else np.nan
        tracking_error = (a - b).std(ddof=1) * np.sqrt(12)
        result[name] = {
            "Beta vs SPY": beta,
            "Correlation vs SPY": a.corr(b),
            "Tracking error (annual)": tracking_error,
            "Annualized arithmetic active return": (a-b).mean() * 12,
        }
    return pd.DataFrame.from_dict(result, orient="index")


def optimization_weights(returns: pd.DataFrame, objective: str = "Minimum variance", max_weight: float = 0.15, annual_rf: float = 0.0, shrink: float = 0.25) -> pd.Series:
    """Long-only SLSQP weights; covariance regularization limits overfit.

    Max-Sharpe expected returns are shrunk 50% toward the cross-sectional mean
    to make estimates less extreme. This is still an IN-SAMPLE optimizer.
    """
    mat = clean_return_matrix(returns, minimum=24)
    n = mat.shape[1]
    if not (0.0 <= shrink <= 1.0):
        raise PortfolioError("Covariance shrinkage must be within [0,1].")
    if n < 2 or max_weight < 1/n - 1e-10 or max_weight > 1:
        raise PortfolioError("Maximum weight must allow a fully invested, diversified portfolio.")
    if objective not in {"Minimum variance", "Maximum Sharpe"}:
        raise PortfolioError("Unknown optimization objective.")
    raw_cov = np.atleast_2d(np.cov(mat.to_numpy(dtype=float), rowvar=False, ddof=1))
    diag = np.diag(np.diag(raw_cov))
    cov = (1-shrink) * raw_cov + shrink * diag + np.eye(n) * 1e-8
    mean = mat.mean().to_numpy(dtype=float)
    mean = 0.5*mean + 0.5*mean.mean()
    rf_monthly = (1 + annual_rf)**(1/12) - 1

    def loss(w: np.ndarray) -> float:
        v = max(float(w @ cov @ w), 1e-12)
        if objective == "Minimum variance":
            return v
        return -float((w @ mean - rf_monthly) / np.sqrt(v))

    result = minimize(
        loss, np.full(n, 1 / n), method="SLSQP",
        bounds=[(0, max_weight)]*n,
        constraints=[{"type": "eq", "fun": lambda x: float(np.sum(x)-1)}],
        options={"maxiter": 1500, "ftol": 1e-11},
    )
    if not result.success or np.any(result.x < -1e-6) or np.any(result.x > max_weight + 1e-6):
        raise PortfolioError(f"Optimization failed: {result.message}")
    weights = np.clip(result.x, 0, max_weight)
    weights /= weights.sum()
    return pd.Series(weights, index=mat.columns, name=objective)


def walk_forward(
    returns: pd.DataFrame,
    objective: str = "Minimum variance",
    train_months: int = 36,
    rebalance_months: int = 6,
    max_weight: float = 0.15,
    annual_rf: float = 0,
) -> tuple[pd.Series, pd.DataFrame]:
    """Fit using PREVIOUS months only; apply weights to next test months.

    Universe may still exhibit constituent-selection look-ahead bias if chosen
    from a later ETF holdings snapshot. This validates weighting method only.
    """
    r = clean_return_matrix(returns, minimum=train_months + 1)
    if train_months < 24 or rebalance_months < 1 or rebalance_months > 24:
        raise PortfolioError("Invalid train/test window.")
    predictions = []
    saved = []
    for start in range(train_months, len(r), rebalance_months):
        train = r.iloc[start-train_months:start]
        weights = optimization_weights(train, objective=objective, max_weight=max_weight, annual_rf=annual_rf)
        test = r.iloc[start:start+rebalance_months]
        predictions.append(portfolio_returns(test, weights))
        row = {"rebalance_date": str(test.index[0].date()), **weights.to_dict()}
        saved.append(row)
    if not predictions:
        raise PortfolioError("Insufficient periods for walk-forward validation.")
    series = pd.concat(predictions)
    series.name = f"Walk-forward {objective}"
    return series, pd.DataFrame(saved).set_index("rebalance_date")


def sector_allocation(weights: pd.Series, registry: pd.DataFrame) -> pd.Series:
    sectors = registry.drop_duplicates("ticker").set_index("ticker")["sector"]
    if not set(weights.index).issubset(sectors.index):
        raise PortfolioError("Every portfolio stock needs a sector label.")
    w = weights.groupby(weights.index.map(sectors)).sum().sort_values(ascending=False)
    w.name = "Portfolio weight"
    return w


def concentration(weights: pd.Series) -> dict[str, float]:
    if weights.empty:
        raise PortfolioError("Empty portfolio.")
    w = np.asarray(weights, dtype=float)
    hhi = float(np.sum(w ** 2))
    return {"HHI": hhi, "Effective holdings": 1.0/hhi, "Largest position": float(w.max()), "Top 5 weight": float(np.sort(w)[-5:].sum())}


def rolling_annualized(returns: pd.DataFrame, window: int = 12) -> pd.DataFrame:
    clean_return_matrix(returns, minimum=window)
    if window < 2:
        raise PortfolioError("Rolling horizon must be at least two months.")
    return (1 + returns).rolling(window).apply(lambda r: np.prod(r), raw=True) ** (12/window) - 1


def worst_benchmark_months(returns: pd.DataFrame, benchmark: str = "SPY", n: int = 5) -> pd.DataFrame:
    clean_return_matrix(returns)
    if benchmark not in returns:
        raise PortfolioError("Benchmark missing.")
    return returns.loc[returns[benchmark].nsmallest(n).index].sort_index()


def purification_worksheet(dividends: pd.DataFrame) -> pd.DataFrame:
    """Calculate purification only from user-supplied per-distribution ratios.

    Input: ticker, shares, dividend_per_share, purification_fraction; e.g. .02
    means 2% of the dividend, not 2% of the stock's market value.
    """
    needed = {"ticker", "shares", "dividend_per_share", "purification_fraction"}
    if not needed.issubset(dividends.columns):
        raise PortfolioError("Purification CSV needs ticker, shares, dividend_per_share, purification_fraction.")
    out = dividends.copy()
    for k in ("shares", "dividend_per_share", "purification_fraction"):
        out[k] = pd.to_numeric(out[k], errors="coerce")
    if out[list(needed - {"ticker"})].isna().any().any() or (out[list(needed - {"ticker"})] < 0).any().any():
        raise PortfolioError("Purification amounts and rates must be nonnegative numeric values.")
    if (out["purification_fraction"] > 1).any():
        raise PortfolioError("Purification fraction must be between 0 and 1.")
    out["gross_dividend"] = out["shares"] * out["dividend_per_share"]
    out["purification_amount"] = out["gross_dividend"] * out["purification_fraction"]
    return out


def sector_return_attribution(monthly_stock_returns: pd.DataFrame, weights: pd.Series, registry: pd.DataFrame) -> pd.DataFrame:
    """Exact MONTHLY arithmetic sector contributions to the custom basket.

    Each month portfolio return is the sum of its sector contributions. These
    are not a causal attribution of the difference between halal and SPY.
    """
    monthly_stock_returns = clean_return_matrix(monthly_stock_returns)
    sectors = registry.drop_duplicates("ticker").set_index("ticker")["sector"]
    if set(monthly_stock_returns.columns) != set(weights.index) or not set(weights.index).issubset(sectors.index):
        raise PortfolioError("Stock returns, weights and sector labels must correspond.")
    grouped = {}
    for sector in sorted(set(sectors.loc[weights.index])):
        names = [t for t in weights.index if sectors.loc[t] == sector]
        grouped[sector] = monthly_stock_returns[names].dot(weights.loc[names])
    return pd.DataFrame(grouped, index=monthly_stock_returns.index)

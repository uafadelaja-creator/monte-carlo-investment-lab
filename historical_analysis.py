"""Historical ETF proxy analysis and moving-block-bootstrap Monte Carlo.

The cached adjusted-price CSV makes published results reproducible without a
future network call. ETF proxies are not survivorship-free stock cohorts, and
bootstrap frequencies are conditional on the observed sample—not forecasts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TICKERS = ["ARKK", "QUAL", "SPY"]
LABELS = {
    "ARKK": "Speculative technology proxy",
    "QUAL": "Quality-equity proxy",
    "SPY": "S&P 500 benchmark",
}
HORIZONS = (1, 3, 6, 12, 24, 36)
START_CASH = 500.0
WEEKLY_DEPOSIT = 100.0
MONTHLY_DEPOSIT = WEEKLY_DEPOSIT * 52.0 / 12.0
SHOCKS = np.array([-0.25, -0.15, -0.18])
VERSION = "0.4"


def fetch_yahoo_monthly(ticker: str, start: str) -> pd.Series:
    """Download Yahoo adjusted monthly closes via yfinance for exploration."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Install yfinance from requirements.txt") from exc
    data = yf.download(
        ticker,
        start=start,
        interval="1mo",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )
    if data is None or data.empty:
        raise RuntimeError(f"No Yahoo/yfinance history returned for {ticker}")
    if isinstance(data.columns, pd.MultiIndex):
        key = ("Adj Close", ticker) if ("Adj Close", ticker) in data.columns else (ticker, "Adj Close")
        series = data[key]
    else:
        series = data["Adj Close"]
    series = pd.to_numeric(series, errors="coerce").dropna()
    series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
    series.name = ticker
    return series[~series.index.duplicated(keep="last")]


def load_prices(start: str, input_csv: str | None) -> tuple[pd.DataFrame, str]:
    if input_csv:
        prices = (
            pd.read_csv(input_csv, parse_dates=["Date"])
            .set_index("Date")[TICKERS]
            .apply(pd.to_numeric, errors="coerce")
        )
        source = f"cached_csv:{input_csv}"
    else:
        prices = pd.concat(
            [fetch_yahoo_monthly(ticker, start) for ticker in TICKERS], axis=1
        )
        source = "Yahoo Finance through yfinance adjusted monthly closes (exploratory)"
    prices = prices.sort_index().dropna(how="all")
    if prices.empty or prices[TICKERS].isna().all().any():
        raise RuntimeError("Missing adjusted-price history for one or more ETFs")
    return prices[TICKERS], source


def complete_month_prices(prices: pd.DataFrame, as_of: str | None) -> pd.DataFrame:
    cutoff = pd.Timestamp(as_of) if as_of else pd.Timestamp.now(tz="UTC").tz_localize(None)
    complete = prices.loc[prices.index.to_period("M") < cutoff.to_period("M")]
    complete = complete.resample("MS").last().dropna(how="any")
    if len(complete) < 37:
        raise RuntimeError("At least 37 common complete-month prices are required")
    return complete


def monthly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    returns = prices.pct_change(fill_method=None).dropna(how="any")
    if (returns <= -1).any().any():
        raise RuntimeError("Adjusted-price history contains a return at or below -100%")
    return returns


def risk_stats(returns: pd.DataFrame, rf_annual: float) -> list[dict[str, object]]:
    rf_monthly = (1 + rf_annual) ** (1 / 12) - 1
    rows: list[dict[str, object]] = []
    for ticker in TICKERS:
        series = returns[ticker]
        months = len(series)
        cumulative = (1 + series).cumprod()
        running_peak = np.maximum.accumulate(np.r_[1.0, cumulative.to_numpy()])[1:]
        drawdown = cumulative.to_numpy() / running_peak - 1
        annualized_vol = series.std(ddof=1) * np.sqrt(12)
        sharpe = (
            (series.mean() - rf_monthly) * 12 / annualized_vol
            if annualized_vol > 0
            else np.nan
        )
        tail = series[series <= series.quantile(0.05)]
        rows.append(
            {
                "ticker": ticker,
                "label": LABELS[ticker],
                "first_month": str(series.index.min().date()),
                "last_month": str(series.index.max().date()),
                "months": months,
                "cagr": float(cumulative.iloc[-1] ** (12 / months) - 1),
                "annualized_volatility": float(annualized_vol),
                "sharpe_ratio_assumed_constant_rf": float(sharpe),
                "historical_max_drawdown_month_end": float(drawdown.min()),
                "best_month": float(series.max()),
                "worst_month": float(series.min()),
                "monthly_skewness": float(series.skew()),
                "monthly_excess_kurtosis": float(series.kurt()),
                "monthly_var_95": float(series.quantile(0.05)),
                "monthly_cvar_95": float(tail.mean()),
            }
        )
    return rows


def sample_joint_returns(
    returns: np.ndarray,
    paths: int,
    months: int,
    block: int,
    seed: int,
) -> np.ndarray:
    """Resample contiguous blocks of joint monthly observations."""
    rng = np.random.default_rng(seed)
    observations = len(returns)
    if observations < block:
        raise ValueError("Block length exceeds available history")
    number_blocks = math.ceil(months / block)
    starts = rng.integers(0, observations - block + 1, size=(paths, number_blocks))
    indices = (starts[:, :, None] + np.arange(block)).reshape(paths, -1)[:, :months]
    return returns[indices]


def simulate_wealth(
    sampled_returns: np.ndarray,
    shock: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    paths, months, arms = sampled_returns.shape
    wealth = np.full((paths, arms), START_CASH)
    unit_nav = np.ones((paths, arms))
    unit_peak = unit_nav.copy()
    maximum_drawdown = np.zeros((paths, arms))
    wealth_history = np.empty((months, paths, arms))
    unit_history = np.empty_like(wealth_history)
    drawdown_history = np.empty_like(wealth_history)
    shocks = np.zeros(arms) if shock is None else np.asarray(shock, dtype=float)

    for month in range(months):
        gross_return = 1 + sampled_returns[:, month, :]
        if month == 0:
            gross_return = gross_return * (1 + shocks)
        if (gross_return <= 0).any():
            raise RuntimeError("A simulated gross return is not positive")
        wealth = wealth * gross_return + MONTHLY_DEPOSIT
        unit_nav *= gross_return
        unit_peak = np.maximum(unit_peak, unit_nav)
        maximum_drawdown = np.maximum(maximum_drawdown, 1 - unit_nav / unit_peak)
        wealth_history[month] = wealth
        unit_history[month] = unit_nav
        drawdown_history[month] = maximum_drawdown
    return {
        "wealth": wealth_history,
        "unit": unit_history,
        "drawdown": drawdown_history,
    }


def summarize(
    simulation: dict[str, np.ndarray],
    scenario: str,
    annual_volatility: dict[str, float],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for months in HORIZONS:
        index = months - 1
        contributed = START_CASH + MONTHLY_DEPOSIT * months
        wealth = simulation["wealth"][index]
        units = simulation["unit"][index]
        drawdowns = simulation["drawdown"][index]
        for arm, ticker in enumerate(TICKERS):
            values = wealth[:, arm]
            p05, p25, median, p75, p95 = np.percentile(values, [5, 25, 50, 75, 95])
            rows.append(
                {
                    "scenario": scenario,
                    "ticker": ticker,
                    "months": months,
                    "contributed_usd": contributed,
                    "mean_ending_value": float(values.mean()),
                    "median_ending_value": float(median),
                    "p05": float(p05),
                    "p25": float(p25),
                    "p75": float(p75),
                    "p95": float(p95),
                    "prob_profitable": float(np.mean(values > contributed)),
                    "prob_loss": float(np.mean(values < contributed)),
                    "mean_contribution_adjusted_return": float(
                        values.mean() / contributed - 1
                    ),
                    "median_time_weighted_cagr": (
                        float(np.median(units[:, arm] ** (12 / months) - 1))
                        if months >= 12
                        else None
                    ),
                    "median_max_drawdown": float(np.median(drawdowns[:, arm])),
                    "p95_max_drawdown": float(np.percentile(drawdowns[:, arm], 95)),
                    "historical_annualized_volatility": annual_volatility[ticker],
                    "prob_beat_spy": (
                        float(np.mean(values > wealth[:, 2])) if arm != 2 else None
                    ),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_wealth_fan(
    output: Path,
    baseline: dict[str, np.ndarray],
    stressed: dict[str, np.ndarray],
) -> None:
    months = np.arange(1, 37)
    contributed = START_CASH + MONTHLY_DEPOSIT * months
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)
    for arm, ax in enumerate(axes):
        values = baseline["wealth"][:, :, arm]
        p05, median, p95 = np.percentile(values, [5, 50, 95], axis=1)
        stress_median = np.median(stressed["wealth"][:, :, arm], axis=1)
        ax.fill_between(months, p05, p95, alpha=0.2, label="5th–95th")
        ax.plot(months, median, linewidth=2, label="Historical bootstrap median")
        ax.plot(months, stress_median, ":", linewidth=1.8, label="Shock median")
        ax.plot(months, contributed, "--", linewidth=1.3, label="Contributed")
        ax.set_title(f"{TICKERS[arm]} · {LABELS[TICKERS[arm]]}")
        ax.set_xlabel("Months")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Portfolio value ($)")
    axes[-1].legend(fontsize=8, loc="upper left")
    fig.suptitle("Historical joint block bootstrap · conditional, not predictive")
    fig.tight_layout()
    fig.savefig(output / "historical_wealth_fan.png", dpi=180)
    plt.close(fig)


def plot_historical_risk(
    output: Path,
    prices: pd.DataFrame,
    returns: pd.DataFrame,
) -> None:
    normalized = prices / prices.iloc[0]
    cumulative = (1 + returns).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1
    correlation = returns.corr()
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    normalized.plot(ax=axes[0, 0], linewidth=1.8)
    axes[0, 0].set_title("Growth of $1 · adjusted prices")
    axes[0, 0].set_ylabel("Multiple")
    drawdown.plot(ax=axes[0, 1], linewidth=1.4)
    axes[0, 1].set_title("Month-end historical drawdowns")
    axes[0, 1].set_ylabel("Drawdown")
    axes[0, 1].yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    axes[1, 0].boxplot(
        [returns[ticker] * 100 for ticker in TICKERS],
        tick_labels=TICKERS,
        showfliers=True,
    )
    axes[1, 0].set_title("Monthly return distributions")
    axes[1, 0].set_ylabel("Return (%)")
    image = axes[1, 1].imshow(correlation.to_numpy(), vmin=-1, vmax=1, cmap="coolwarm")
    axes[1, 1].set_xticks(range(3), TICKERS)
    axes[1, 1].set_yticks(range(3), TICKERS)
    axes[1, 1].set_title("Monthly return correlations")
    for row in range(3):
        for column in range(3):
            axes[1, 1].text(
                column,
                row,
                f"{correlation.iloc[row, column]:.2f}",
                ha="center",
                va="center",
            )
    fig.colorbar(image, ax=axes[1, 1], fraction=0.046)
    for ax in axes.flat:
        ax.grid(alpha=0.18)
    fig.suptitle("Observed ETF proxy history · common complete months")
    fig.tight_layout()
    fig.savefig(output / "historical_risk_dashboard.png", dpi=180)
    plt.close(fig)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--csv", default=None)
    parser.add_argument("--cache-csv", default=None)
    parser.add_argument("--paths", type=int, default=50_000)
    parser.add_argument("--block", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20_261_011)
    parser.add_argument("--rf", type=float, default=0.0)
    parser.add_argument("--outdir", type=Path, default=Path("results"))
    args = parser.parse_args()
    if args.paths < 50_000:
        raise SystemExit("Published project runs require at least 50,000 paths")
    if args.block < 1 or args.rf <= -1:
        raise SystemExit("block must be positive and rf must exceed -1")

    raw_prices, source = load_prices(args.start, args.csv)
    latest_common = raw_prices.dropna(how="any").iloc[-1]
    latest_date = str(raw_prices.dropna(how="any").index[-1].date())
    # Quantize before calculation and caching so an offline rerun from the
    # repository reproduces the published CSV outputs byte-for-byte.
    complete_prices = complete_month_prices(raw_prices, args.as_of).round(8)
    returns = monthly_returns(complete_prices)
    args.outdir.mkdir(parents=True, exist_ok=True)

    cached_path = Path(args.cache_csv) if args.cache_csv else None
    if cached_path:
        cached_path.parent.mkdir(parents=True, exist_ok=True)
        complete_prices.rename_axis("Date").to_csv(cached_path, float_format="%.8f")

    risk_rows = risk_stats(returns, args.rf)
    volatility = {row["ticker"]: row["annualized_volatility"] for row in risk_rows}
    sampled = sample_joint_returns(
        returns.to_numpy(), args.paths, max(HORIZONS), args.block, args.seed
    )
    baseline = simulate_wealth(sampled)
    stressed = simulate_wealth(sampled, SHOCKS)
    baseline_rows = summarize(baseline, "historical_joint_block_bootstrap", volatility)
    stress_rows = summarize(stressed, "hypothetical_first_month_shock", volatility)

    write_csv(args.outdir / "historical_risk_metrics.csv", risk_rows)
    write_csv(
        args.outdir / "historical_simulation_summary.csv",
        baseline_rows + stress_rows,
    )
    returns.corr().to_csv(args.outdir / "historical_correlations.csv", float_format="%.6f")

    block_rows: list[dict[str, object]] = []
    for block in (1, 3, 6):
        block_sample = sample_joint_returns(
            returns.to_numpy(), args.paths, max(HORIZONS), block, args.seed
        )
        block_simulation = simulate_wealth(block_sample)
        for row in summarize(
            block_simulation,
            f"historical_bootstrap_block_{block}m",
            volatility,
        ):
            if row["months"] == 36:
                block_rows.append(row)
    write_csv(args.outdir / "historical_block_sensitivity.csv", block_rows)

    plot_wealth_fan(args.outdir, baseline, stressed)
    plot_historical_risk(args.outdir, complete_prices, returns)

    cache_hash = file_sha256(cached_path) if cached_path else None
    metadata = {
        "version": VERSION,
        "data_source": source,
        "price_type": "adjusted close",
        "proxy_assets": TICKERS,
        "historical_first_price_month": str(complete_prices.index.min().date()),
        "historical_last_complete_price_month": str(complete_prices.index.max().date()),
        "first_return_month": str(returns.index.min().date()),
        "last_return_month": str(returns.index.max().date()),
        "common_return_months": int(len(returns)),
        "current_market_snapshot": {
            "date": latest_date,
            **{ticker: float(latest_common[ticker]) for ticker in TICKERS},
        },
        "paths": args.paths,
        "master_seed": args.seed,
        "seed_policy": "Fixed seed; joint returns and sensitivity variants are reproducible.",
        "horizons_months": list(HORIZONS),
        "block_months_primary": args.block,
        "block_sensitivity_months": [1, 3, 6],
        "starting_cash_usd": START_CASH,
        "weekly_contribution_usd": WEEKLY_DEPOSIT,
        "monthly_equivalent_contribution_usd": MONTHLY_DEPOSIT,
        "contribution_timing": "month-end",
        "annual_risk_free_rate_assumption": args.rf,
        "hypothetical_first_month_shock": dict(zip(TICKERS, SHOCKS.tolist())),
        "cached_price_file": str(cached_path) if cached_path else None,
        "cached_price_sha256": cache_hash,
        "limitations": [
            "ETF proxies are not survivorship-free point-in-time stock cohorts.",
            "The sample begins in 2015 and is highly regime-dependent.",
            "Moving-block bootstrap resamples observed history and does not forecast.",
            "Correlation and volatility can change abruptly outside the sample.",
            "Month-end data miss intramonth drawdowns and liquidity gaps.",
            "Adjusted-price histories may be revised by the data vendor.",
            "Taxes, spreads, fund fees, inflation, and exact weekly timing are omitted.",
            "A fixed zero-percent risk-free rate is used only for transparent Sharpe comparison.",
        ],
    }
    (args.outdir / "historical_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )
    dashboard = {
        "metadata": metadata,
        "risk_metrics": risk_rows,
        "correlations": returns.corr().round(6).to_dict(),
        "baseline": baseline_rows,
        "shock": stress_rows,
        "block_sensitivity_36m": block_rows,
    }
    (args.outdir / "historical_dashboard_data.json").write_text(
        json.dumps(dashboard, indent=2, allow_nan=False) + "\n"
    )
    print(
        f"Historical sample: {metadata['first_return_month']} through "
        f"{metadata['last_return_month']} ({metadata['common_return_months']} months)"
    )
    print(f"Current snapshot: {metadata['current_market_snapshot']}")
    print(f"Wrote results to {args.outdir.resolve()}")


if __name__ == "__main__":
    main()


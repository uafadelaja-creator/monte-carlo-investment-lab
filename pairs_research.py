"""Walk-forward pairs research with delayed fills, costs, and uncertainty.

This module tests predeclared hypotheses. It does not search for or issue trade
alerts. Signals use only observations available before the modeled execution,
and results remain exploratory because adjusted closes are not executable quotes.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint


HORIZON_SESSIONS = {1: 21, 3: 63, 6: 126, 12: 252, 24: 504, 36: 756}


def load_prices(
    path: Path, a: str, b: str, benchmarks: tuple[str, ...]
) -> pd.DataFrame:
    prices = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    requested = [a, b, *benchmarks]
    missing = [ticker for ticker in requested if ticker not in prices.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} in {path}")
    if not prices.index.is_unique:
        raise ValueError("Duplicate price dates. Clean the source first.")
    frame = prices[requested].replace([np.inf, -np.inf], np.nan)
    pair_mask = frame[[a, b]].notna().all(axis=1) & (frame[[a, b]] > 0).all(axis=1)
    frame = frame.loc[pair_mask]
    if len(frame) < 600:
        raise ValueError("Need at least 600 aligned daily pair observations.")
    return frame


def trailing_estimate(
    log_a: np.ndarray,
    log_b: np.ndarray,
    index: int,
    formation: int,
    z_window: int,
) -> dict[str, float | bool | None]:
    sample_a = log_a[index - formation:index]
    sample_b = log_b[index - formation:index]
    beta, intercept = np.polyfit(sample_b, sample_a, 1)
    if not (np.isfinite(beta) and 0.1 < beta < 10):
        return {"valid": False, "p": None, "beta": None, "mean": None, "std": None}
    with np.errstate(all="ignore"):
        p_value = float(coint(sample_a, sample_b, trend="c", autolag="aic")[1])
    residual = sample_a - intercept - beta * sample_b
    center = float(residual[-z_window:].mean())
    stdev = float(residual[-z_window:].std(ddof=1))
    valid = np.isfinite(p_value) and np.isfinite(stdev) and stdev > 1e-7
    return {
        "valid": bool(valid),
        "p": p_value if valid else None,
        "beta": float(beta),
        "intercept": float(intercept),
        "mean": center,
        "std": stdev,
    }


def backtest(
    prices: pd.DataFrame,
    a: str,
    b: str,
    benchmarks: tuple[str, ...],
    test_start: str,
    formation: int,
    z_window: int,
    refit: int,
    entry_z: float,
    exit_z: float,
    stop_z: float,
    p_limit: float,
    fee_bps: float,
    borrow_apr: float,
) -> pd.DataFrame:
    dates = prices.index
    cutoff = int(dates.searchsorted(pd.Timestamp(test_start)))
    if cutoff < formation or cutoff >= len(dates) - 5:
        raise ValueError("Test start must leave a full training window and a non-empty test.")
    if not (0 <= exit_z < entry_z < stop_z):
        raise ValueError("Require 0 <= exit_z < entry_z < stop_z.")
    if formation < max(z_window, 100):
        raise ValueError("Formation must be >= max(z_window, 100).")

    log_a = np.log(prices[a].to_numpy())
    log_b = np.log(prices[b].to_numpy())
    n_obs = len(prices)
    signals = np.zeros(n_obs, dtype=np.int8)
    targets = np.zeros((n_obs, 2))
    zvalues = np.full(n_obs, np.nan)
    pvalues = np.full(n_obs, np.nan)
    betas = np.full(n_obs, np.nan)
    parameter: dict[str, float | bool | None] | None = None
    side = 0
    last_fit = -refit

    for index in range(cutoff, n_obs):
        # Every formation/refit observation is strictly earlier than date[index].
        if parameter is None or index - last_fit >= refit:
            parameter = trailing_estimate(
                log_a, log_b, index, formation=formation, z_window=z_window
            )
            last_fit = index
        if not parameter["valid"]:
            side = 0
            continue
        p_value = float(parameter["p"])
        beta = float(parameter["beta"])
        spread = log_a[index] - float(parameter["intercept"]) - beta * log_b[index]
        zscore = (spread - float(parameter["mean"])) / float(parameter["std"])
        zvalues[index], pvalues[index], betas[index] = zscore, p_value, beta

        if p_value > p_limit or not np.isfinite(zscore):
            side = 0
        elif side == 0:
            if entry_z <= zscore <= stop_z:
                side = -1
            elif -stop_z <= zscore <= -entry_z:
                side = 1
        elif abs(zscore) <= exit_z or abs(zscore) >= stop_z:
            side = 0

        signals[index] = side
        if side:
            targets[index] = (side / (1 + beta), -side * beta / (1 + beta))

    # Signal at close T is assumed filled at close T+1. That position begins
    # earning only over T+1 -> T+2. Turnover cost is charged at each modeled fill.
    executed = np.zeros_like(targets)
    executed[1:] = targets[:-1]
    pair_returns = prices[[a, b]].pct_change(fill_method=None).to_numpy()
    gross = np.zeros(n_obs)
    turnover = np.zeros(n_obs)
    turnover_cost = np.zeros(n_obs)
    borrow_cost = np.zeros(n_obs)
    short_notional = np.zeros(n_obs)
    net = np.zeros(n_obs)

    for index in range(1, n_obs):
        prior_position = executed[index - 1]
        gross[index] = (
            prior_position[0] * pair_returns[index, 0]
            + prior_position[1] * pair_returns[index, 1]
        )
        turnover[index] = np.abs(executed[index] - prior_position).sum()
        turnover_cost[index] = turnover[index] * fee_bps / 10_000
        short_notional[index] = max(-prior_position[0], 0) + max(-prior_position[1], 0)
        borrow_cost[index] = short_notional[index] * borrow_apr / 252
        net[index] = gross[index] - turnover_cost[index] - borrow_cost[index]

    if np.abs(executed[-1]).sum() > 0:
        liquidation = np.abs(executed[-1]).sum()
        turnover[-1] += liquidation
        extra_cost = liquidation * fee_bps / 10_000
        turnover_cost[-1] += extra_cost
        net[-1] -= extra_cost

    result = pd.DataFrame(index=dates)
    result["zscore"] = zvalues
    result["cointegration_p"] = pvalues
    result["hedge_beta"] = betas
    result["signal_side"] = signals
    result["executed_weight_a"], result["executed_weight_b"] = executed.T
    result["gross_return"] = gross
    result["turnover"] = turnover
    result["turnover_cost"] = turnover_cost
    result["short_notional"] = short_notional
    result["borrow_cost"] = borrow_cost
    result["strategy_return_net"] = net
    for ticker in benchmarks:
        result[f"{ticker}_return"] = prices[ticker].pct_change(fill_method=None)
    result = result.iloc[cutoff:].copy()
    result["strategy_nav_net"] = (1 + result["strategy_return_net"]).cumprod()
    for ticker in benchmarks:
        result[f"{ticker}_nav"] = (1 + result[f"{ticker}_return"].fillna(0)).cumprod()
    return result


def metrics(returns: pd.Series) -> dict[str, float | int | None]:
    clean = returns.dropna().astype(float)
    if len(clean) < 10:
        return {"n_sessions": int(len(clean)), "cumulative_return": None}
    if (clean <= -1).any():
        raise ValueError("Return at or below -100%; investigate the model.")
    nav = (1 + clean).cumprod()
    peak = np.maximum.accumulate(np.r_[1.0, nav.to_numpy()])[1:]
    drawdown = nav.to_numpy() / peak - 1
    volatility = float(clean.std(ddof=1) * np.sqrt(252))
    downside = clean[clean < 0].std(ddof=1) * np.sqrt(252)
    sharpe = (
        float(clean.mean() / clean.std(ddof=1) * np.sqrt(252))
        if clean.std(ddof=1) > 0
        else None
    )
    sortino = float(clean.mean() * 252 / downside) if downside and downside > 0 else None
    years = len(clean) / 252
    cumulative = float(nav.iloc[-1] - 1)
    cagr = float(nav.iloc[-1] ** (1 / years) - 1) if years > 0 else None
    return {
        "n_sessions": int(len(clean)),
        "cumulative_return": cumulative,
        "cagr": cagr,
        "annualized_volatility": volatility,
        "max_drawdown": float(drawdown.min()),
        "sharpe_rf_0": sharpe,
        "sortino_rf_0": sortino,
        "profitable_day_fraction": float((clean > 0).mean()),
    }


def comparison(strategy: pd.Series, benchmark: pd.Series) -> dict[str, float | None]:
    joined = pd.concat([strategy, benchmark], axis=1).dropna()
    joined.columns = ["strategy", "benchmark"]
    if len(joined) < 10:
        return {"information_ratio_rf_0": None, "volatility_ratio": None}
    active = joined["strategy"] - joined["benchmark"]
    tracking_error = active.std(ddof=1) * np.sqrt(252)
    information = (
        float(active.mean() * 252 / tracking_error) if tracking_error > 0 else None
    )
    benchmark_vol = joined["benchmark"].std(ddof=1) * np.sqrt(252)
    strategy_vol = joined["strategy"].std(ddof=1) * np.sqrt(252)
    return {
        "information_ratio_rf_0": information,
        "volatility_ratio_strategy_to_benchmark": (
            float(strategy_vol / benchmark_vol) if benchmark_vol > 0 else None
        ),
        "note": "Descriptive risk adjustment only; neither series is leverage-matched.",
    }


def factor_attribution(
    strategy: pd.Series, factor_path: Path | None
) -> dict[str, float | int | str | None]:
    if factor_path is None or not factor_path.exists():
        return {
            "status": "not_run",
            "reason": "official Kenneth French factor file not supplied",
        }
    factors = pd.read_csv(factor_path, index_col=0, parse_dates=True).sort_index()
    required = ["Mkt-RF", "SMB", "HML", "RF"]
    missing = [column for column in required if column not in factors.columns]
    if missing:
        raise ValueError(f"Missing factor columns {missing} in {factor_path}")
    joined = pd.concat([strategy.rename("strategy"), factors[required]], axis=1).dropna()
    if len(joined) < 100:
        return {"status": "not_run", "reason": "fewer than 100 aligned sessions"}
    if joined["strategy"].std(ddof=1) == 0:
        return {
            "status": "not_estimable",
            "reason": "strategy was flat throughout the aligned factor sample",
        }
    # Pair returns are modeled as returns on a self-financing long/short sleeve;
    # collateral interest is omitted, so treat the series as zero-cash excess return.
    dependent = joined["strategy"]
    independent = sm.add_constant(joined[["Mkt-RF", "SMB", "HML"]])
    model = sm.OLS(dependent, independent).fit(
        cov_type="HAC", cov_kwds={"maxlags": 5}
    )
    return {
        "status": "descriptive_only",
        "n_sessions": int(model.nobs),
        "annualized_alpha_zero_cash": float(model.params["const"] * 252),
        "alpha_hac_tstat": float(model.tvalues["const"]),
        "alpha_hac_pvalue": float(model.pvalues["const"]),
        "market_beta": float(model.params["Mkt-RF"]),
        "smb_beta": float(model.params["SMB"]),
        "hml_beta": float(model.params["HML"]),
        "source": "Kenneth French daily F-F Research Factors",
        "warning": "HAC inference is exploratory and does not establish implementable alpha.",
    }


def block_bootstrap(
    returns: pd.Series,
    paths: int,
    block: int,
    seed: int,
    batch_size: int = 2000,
) -> list[dict[str, float | int]]:
    """Moving-block resampling of observed out-of-sample NET strategy returns."""
    sample = returns.dropna().to_numpy(dtype=float)
    if len(sample) < block * 3:
        raise ValueError("Not enough out-of-sample returns for the requested block.")
    if paths < 1:
        return []
    rows: list[dict[str, float | int]] = []
    for horizon_months, horizon in HORIZON_SESSIONS.items():
        rng = np.random.default_rng(seed + horizon)
        terminal = np.empty(paths)
        maximum_drawdown = np.empty(paths)
        completed = 0
        blocks_needed = math.ceil(horizon / block)
        while completed < paths:
            batch = min(batch_size, paths - completed)
            starts = rng.integers(
                0, len(sample) - block + 1, size=(batch, blocks_needed)
            )
            indices = (
                starts[:, :, None] + np.arange(block)
            ).reshape(batch, -1)[:, :horizon]
            sampled = sample[indices]
            nav = np.cumprod(1 + sampled, axis=1)
            peaks = np.maximum.accumulate(np.c_[np.ones(batch), nav], axis=1)[:, 1:]
            terminal[completed:completed + batch] = nav[:, -1] - 1
            maximum_drawdown[completed:completed + batch] = 1 - np.min(
                nav / peaks, axis=1
            )
            completed += batch
        p05, p25, median, p75, p95 = np.percentile(
            terminal, [5, 25, 50, 75, 95]
        )
        rows.append(
            {
                "horizon_months": horizon_months,
                "horizon_sessions": horizon,
                "paths": paths,
                "block_sessions": block,
                "seed": seed + horizon,
                "mean_return": float(terminal.mean()),
                "p05_return": float(p05),
                "p25_return": float(p25),
                "median_return": float(median),
                "p75_return": float(p75),
                "p95_return": float(p95),
                "probability_profitable": float(np.mean(terminal > 0)),
                "probability_loss": float(np.mean(terminal < 0)),
                "median_max_drawdown": float(np.median(maximum_drawdown)),
                "p95_max_drawdown": float(np.percentile(maximum_drawdown, 95)),
            }
        )
    return rows


def _manifest(prices_path: Path) -> dict | None:
    manifest = prices_path.with_name("download_manifest.json")
    if not manifest.exists():
        return None
    return json.loads(manifest.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> dict:
    benchmarks = tuple(dict.fromkeys([args.benchmark, args.sector_benchmark]))
    prices = load_prices(args.prices, args.a, args.b, benchmarks)
    result = backtest(
        prices,
        args.a,
        args.b,
        benchmarks,
        args.test_start,
        args.formation,
        args.z_window,
        args.refit,
        args.entry_z,
        args.exit_z,
        args.stop_z,
        args.p_limit,
        args.fee_bps,
        args.borrow_apr,
    )
    if (result["strategy_return_net"] <= -1).any():
        raise ValueError("Model produced a catastrophic daily loss.")
    bootstrap = block_bootstrap(
        result["strategy_return_net"], args.paths, args.block, args.seed
    )
    strategy_metrics = metrics(result["strategy_return_net"])
    benchmark_metrics = {
        ticker: metrics(result[f"{ticker}_return"]) for ticker in benchmarks
    }
    comparisons = {
        ticker: comparison(
            result["strategy_return_net"], result[f"{ticker}_return"]
        )
        for ticker in benchmarks
    }
    exposure = (
        result["executed_weight_a"].abs() + result["executed_weight_b"].abs()
    )
    entries = int(((exposure.shift(1).fillna(0) == 0) & (exposure > 0)).sum())
    report = {
        "research_only": True,
        "hypothesis_predeclared": True,
        "pair": [args.a, args.b],
        "market_data": str(args.prices),
        "download_manifest": _manifest(args.prices),
        "test_start": args.test_start,
        "last_test_session": str(result.index.max().date()),
        "settings": {
            "formation_days": args.formation,
            "z_lookback": args.z_window,
            "refit_every_days": args.refit,
            "entry_z": args.entry_z,
            "exit_z": args.exit_z,
            "stop_z": args.stop_z,
            "cointegration_max_p": args.p_limit,
            "turnover_cost_bps_per_notional_dollar": args.fee_bps,
            "hypothetical_short_borrow_apr": args.borrow_apr,
            "execution": "signal after close T; modeled fill at close T+1; P&L begins T+1 to T+2",
            "price_basis": "vendor-adjusted close; total-return approximation, not executable quote",
        },
        "strategy_net": strategy_metrics,
        "flat_cash": {
            "cumulative_return": 0.0,
            "volatility": 0.0,
            "note": "Nominal zero-yield cash; interest and inflation omitted.",
        },
        "benchmarks": benchmark_metrics,
        "risk_adjusted_comparisons": comparisons,
        "fama_french_attribution": factor_attribution(
            result["strategy_return_net"], args.factors
        ),
        "executed_entry_count": entries,
        "exposure_fraction": float((exposure > 0).mean()),
        "total_turnover": float(result["turnover"].sum()),
        "total_modeled_turnover_cost": float(result["turnover_cost"].sum()),
        "total_modeled_borrow_drag": float(result["borrow_cost"].sum()),
        "bootstrap": bootstrap,
        "warnings": [
            "Not a live recommendation or trade alert.",
            "Present-day survivor-selected pairs are fixed hypotheses, not a historical universe.",
            "Adjusted closes are total-return approximations and not executable fills.",
            "Flat turnover cost and borrow APR are scenarios, not observed bid/ask or locate data.",
            "Borrow availability, margin calls, taxes, market impact, and intraday gaps are omitted.",
            "Rolling cointegration tests do not prove persistent mean reversion.",
            "No model was selected by ranking these test-period results.",
            "Block bootstrap is conditional on this observed test sample and cannot create unseen regimes.",
        ],
    }

    args.outdir.mkdir(parents=True, exist_ok=True)
    prefix = f"{args.a}_{args.b}"
    result.to_csv(args.outdir / f"{prefix}_daily.csv", float_format="%.10f")
    (args.outdir / f"{prefix}_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    pd.DataFrame(bootstrap).to_csv(
        args.outdir / f"{prefix}_bootstrap.csv", index=False, float_format="%.10f"
    )

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    axes[0].plot(result.index, result["strategy_nav_net"], label=f"{prefix} strategy net")
    for ticker in benchmarks:
        axes[0].plot(result.index, result[f"{ticker}_nav"], label=f"{ticker} buy/hold")
    axes[0].legend()
    axes[0].grid(alpha=0.25)
    axes[0].set_ylabel("Growth of $1")
    axes[1].plot(result.index, result["zscore"], lw=0.9)
    axes[1].axhline(args.entry_z, color="gray", ls="--")
    axes[1].axhline(-args.entry_z, color="gray", ls="--")
    axes[1].axhline(0, color="gray", lw=0.5)
    axes[1].set_ylabel("Training-only Z-score")
    axes[1].grid(alpha=0.25)
    fig.suptitle("Predeclared walk-forward pair study — research only")
    fig.tight_layout()
    fig.savefig(args.outdir / f"{prefix}_research.png", dpi=160)
    plt.close(fig)
    print(json.dumps({"pair": report["pair"], "strategy_net": strategy_metrics}, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", type=Path, default=Path("data/adjusted_close.csv"))
    parser.add_argument(
        "--factors", type=Path, default=Path("data/french_factors_daily.csv")
    )
    parser.add_argument("--a", default="V")
    parser.add_argument("--b", default="MA")
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--sector-benchmark", default="XLF")
    parser.add_argument("--test-start", default="2023-01-03")
    parser.add_argument("--formation", type=int, default=252)
    parser.add_argument("--z-window", type=int, default=60)
    parser.add_argument("--refit", type=int, default=21)
    parser.add_argument("--entry-z", type=float, default=2.0)
    parser.add_argument("--exit-z", type=float, default=0.5)
    parser.add_argument("--stop-z", type=float, default=3.5)
    parser.add_argument("--p-limit", type=float, default=0.05)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--borrow-apr", type=float, default=0.03)
    parser.add_argument("--paths", type=int, default=50_000)
    parser.add_argument("--block", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261018)
    parser.add_argument("--outdir", type=Path, default=Path("results/stat_arb"))
    args = parser.parse_args()
    for attribute in ("a", "b", "benchmark", "sector_benchmark"):
        setattr(args, attribute, getattr(args, attribute).upper())
    if args.a == args.b:
        raise ValueError("Pair securities must be distinct.")
    if len({args.benchmark, args.sector_benchmark}) < 2:
        raise ValueError("Use distinct broad and sector benchmarks.")
    run(args)


if __name__ == "__main__":
    main()


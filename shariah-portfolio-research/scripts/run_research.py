"""Reproducible CLI analysis with optional network retrieval.

Examples:
  python -m scripts.run_research --download --out-dir outputs
  python -m scripts.run_research --prices data/actual_adjusted_prices.csv --out-dir outputs
  python -m scripts.run_research --prices data/actual_adjusted_prices.csv --no-basket
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from src.shariah_lab.data import (
    TICKERS, download_universe_prices, load_universe_csv, monthly_returns,
    to_csv_bytes, trim_incomplete_last_month, validate_universe_prices,
)
from src.shariah_lab.model import moving_block_bootstrap, simulation_summary
from src.shariah_lab.point_in_time import backtest_pit, load_pit_history
from src.shariah_lab.portfolio import (
    benchmark_diagnostics, metric_table, portfolio_returns,
    optimization_weights, walk_forward,
)
from src.shariah_lab.report import build_report
from src.shariah_lab.screening import load_registry, suggested_weights


def create_outputs(
    prices: pd.DataFrame,
    output_dir: Path,
    registry: pd.DataFrame | None = None,
    basket_size: int = 20,
    weighting: str = "Equal weight",
    paths: int = 10_000,
    years: int = 10,
    initial: float = 10_000,
    monthly_deposit: float = 250,
    seed: int = 42,
    block: int = 6,
    source: str = "Provided adjusted-price CSV",
    pit_history: pd.DataFrame | None = None,
    pit_weighting: str = "Equal weight",
) -> dict:
    holdings = registry.sort_values("issuer_weight_pct", ascending=False).head(basket_size).copy() if registry is not None else None
    names = holdings["ticker"].tolist() if holdings is not None else []
    pit_names = list(pit_history.loc[pit_history["eligible"], "ticker"].unique()) if pit_history is not None else []
    needed = list(dict.fromkeys(list(TICKERS) + names + pit_names))
    validated = validate_universe_prices(prices[needed])
    trimmed = trim_incomplete_last_month(validated)
    monthly = monthly_returns(trimmed)
    combined = monthly[list(TICKERS)].copy()
    weights = None
    if names:
        if weighting in ("Equal weight", "Issuer proportional (top basket only)"):
            weights = suggested_weights(holdings, weighting)
        else:
            weights = optimization_weights(monthly[names], objective=weighting, max_weight=max(.15, 1 / len(names)+.001))
        combined["Custom basket"] = portfolio_returns(monthly[names], weights)
    pit_audit = None
    if pit_history is not None:
        pit_series, pit_audit = backtest_pit(monthly[pit_names], pit_history, weight_method=pit_weighting)
        combined = combined.loc[pit_series.index].copy()
        combined[pit_series.name] = pit_series

    sim = moving_block_bootstrap(combined, years=years, n_sims=paths, initial=initial, monthly_contribution=monthly_deposit, block_months=block, seed=seed)
    scenario = simulation_summary(sim)
    metrics = metric_table(combined)
    benchmark = benchmark_diagnostics(combined)
    data_bytes = to_csv_bytes(trimmed)
    checksum = sha256(data_bytes).hexdigest()
    assumptions = {
        "Source": source, "Observed price SHA256": checksum,
        "Initial capital": f"${initial:,.2f}", "Monthly contribution": f"${monthly_deposit:,.2f}",
        "Investment horizon": f"{years} years", "Simulation paths": paths,
        "Bootstrap block length": f"{block} months", "Seed": seed,
        "Portfolio weighting": weighting if names else "ETF-only",
        "Basket constituent snapshot": ", ".join(sorted(set(map(str, holdings.as_of)))) if names else "Not used",
        "User PIT screen records": f"{pit_history['as_of'].nunique()} snapshots, {pit_weighting} weights" if pit_history is not None else "Not supplied",
    }
    report = build_report(combined, source, holdings=holdings, weights=weights, scenario=scenario, assumptions=assumptions)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "research_report.md").write_text(report, encoding="utf-8")
    (output_dir / "market_prices_adjusted.csv").write_bytes(data_bytes)
    metrics.to_csv(output_dir / "historical_metrics.csv")
    scenario.to_csv(output_dir / "simulation_summary.csv")
    benchmark.to_csv(output_dir / "benchmark_diagnostics.csv")
    combined.to_csv(output_dir / "monthly_return_series.csv")
    if weights is not None:
        weights.to_csv(output_dir / "basket_weights.csv", header=True)
        holdings.to_csv(output_dir / "basket_evidence.csv", index=False)
        if len(monthly) > 36 and len(names) >= 7:
            wf, allocations = walk_forward(monthly[names], train_months=36, rebalance_months=6, max_weight=max(.15, 1/len(names)+.001))
            wf.to_csv(output_dir / "walk_forward_monthly_returns.csv", header=True)
            allocations.to_csv(output_dir / "walk_forward_allocations.csv")
    if pit_history is not None and pit_audit is not None:
        pit_history.to_csv(output_dir / "historical_screening_evidence.csv", index=False)
        pit_audit.to_csv(output_dir / "historical_screening_audit.csv")
    metadata = {
        "generated_at_utc_date": date.today().isoformat(),
        "input_data_provenance": source,
        "input_price_sha256": checksum,
        "observed_first_date": trimmed.index[0].date().isoformat(),
        "observed_last_date": trimmed.index[-1].date().isoformat(),
        "monthly_observations": len(monthly),
        "tickers": list(combined.columns),
        "current_holdings_lookahead_warning": bool(names),
        "historical_screens_user_provided_not_independently_certified": bool(pit_history is not None),
        "assumptions": assumptions,
    }
    (output_dir / "study_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an as-of dated, evidence-backed research package (no made-up prices).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prices", type=Path, help="CSV with Date, SPY, SPUS, HLAL + 20 stock adjusted-price columns")
    group.add_argument("--download", action="store_true", help="Download adjusted Yahoo Finance histories on this machine")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2019, 12, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--out-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--registry", type=Path, help="Alternative dated stock-evidence registry CSV")
    parser.add_argument("--no-basket", action="store_true", help="ETFs only; no 2026-constituent backcast")
    parser.add_argument("--pit-history", type=Path, help="Optional dated complete screening-snapshot CSV")
    parser.add_argument("--pit-weighting", choices=["Equal weight", "Evidence proportional"], default="Equal weight")
    parser.add_argument("--basket-size", type=int, choices=range(5, 21), metavar="5..20", default=20)
    parser.add_argument("--weighting", choices=["Equal weight", "Issuer proportional (top basket only)", "Minimum variance", "Maximum Sharpe"], default="Equal weight")
    parser.add_argument("--paths", type=int, default=10_000)
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--initial", type=float, default=10_000)
    parser.add_argument("--monthly-deposit", type=float, default=250)
    parser.add_argument("--block", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    registry = None if args.no_basket else load_registry(args.registry.as_posix() if args.registry else None)
    pit_history = load_pit_history(args.pit_history.read_bytes()) if args.pit_history else None
    pit_names = pit_history.loc[pit_history["eligible"], "ticker"].unique().tolist() if pit_history is not None else []
    symbols = list(dict.fromkeys(list(TICKERS) + (registry.sort_values("issuer_weight_pct", ascending=False).head(args.basket_size)["ticker"].tolist() if registry is not None else []) + pit_names))
    if args.prices is not None:
        prices = load_universe_csv(args.prices.read_bytes())
        source = f"Provided adjusted-price CSV {args.prices.name}"
    else:
        prices = download_universe_prices(args.start, args.end, tuple(symbols))
        source = f"Yahoo Finance adjusted prices downloaded on {date.today().isoformat()}"
    metadata = create_outputs(prices, args.out_dir, registry, args.basket_size, args.weighting, args.paths, args.years, args.initial, args.monthly_deposit, args.seed, args.block, source, pit_history, args.pit_weighting)
    print(f"Research files written to {args.out_dir.resolve()} (prices SHA256 {metadata['input_price_sha256'][:12]}…).")
    print("Do not present 2026 holdings backcasts as Shariah-compliant historical strategies.")


if __name__ == "__main__":
    main()

"""Run the fixed three-pair protocol without selecting a winner ex post."""
from __future__ import annotations

import argparse
import json
from argparse import Namespace
from pathlib import Path

import pandas as pd

import pairs_research as pr


PAIR_HYPOTHESES = (
    ("V", "MA", "XLF"),
    ("KO", "PEP", "XLP"),
    ("XOM", "CVX", "XLE"),
)


def namespace(args: argparse.Namespace, a: str, b: str, sector: str) -> Namespace:
    values = vars(args).copy()
    values.update({"a": a, "b": b, "benchmark": "SPY", "sector_benchmark": sector})
    return Namespace(**values)


def sensitivity_row(
    args: argparse.Namespace,
    a: str,
    b: str,
    sector: str,
    formation: int,
    fee_bps: float,
) -> dict:
    benchmarks = ("SPY", sector)
    prices = pr.load_prices(args.prices, a, b, benchmarks)
    result = pr.backtest(
        prices,
        a,
        b,
        benchmarks,
        args.test_start,
        formation,
        args.z_window,
        args.refit,
        args.entry_z,
        args.exit_z,
        args.stop_z,
        args.p_limit,
        fee_bps,
        args.borrow_apr,
    )
    metrics = pr.metrics(result["strategy_return_net"])
    return {
        "pair": f"{a}/{b}",
        "sector_benchmark": sector,
        "formation_days": formation,
        "turnover_cost_bps": fee_bps,
        **metrics,
    }


def run(args: argparse.Namespace) -> None:
    args.outdir.mkdir(parents=True, exist_ok=True)
    reports: list[dict] = []
    for a, b, sector in PAIR_HYPOTHESES:
        reports.append(pr.run(namespace(args, a, b, sector)))

    summary_rows: list[dict] = []
    for report in reports:
        strategy = report["strategy_net"]
        one_year = next(
            row for row in report["bootstrap"] if row["horizon_months"] == 12
        )
        summary_rows.append(
            {
                "pair": "/".join(report["pair"]),
                "test_start": report["test_start"],
                "last_test_session": report["last_test_session"],
                "entries": report["executed_entry_count"],
                "exposure_fraction": report["exposure_fraction"],
                "net_cumulative_return": strategy["cumulative_return"],
                "net_cagr": strategy["cagr"],
                "annualized_volatility": strategy["annualized_volatility"],
                "max_drawdown": strategy["max_drawdown"],
                "sharpe_rf_0": strategy["sharpe_rf_0"],
                "one_year_bootstrap_median_return": one_year["median_return"],
                "one_year_bootstrap_probability_loss": one_year["probability_loss"],
                "one_year_bootstrap_median_drawdown": one_year["median_max_drawdown"],
                "ff3_annualized_alpha_zero_cash": report["fama_french_attribution"].get(
                    "annualized_alpha_zero_cash"
                ),
                "ff3_alpha_hac_pvalue": report["fama_french_attribution"].get(
                    "alpha_hac_pvalue"
                ),
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(args.outdir / "predeclared_pair_summary.csv", index=False)

    sensitivity: list[dict] = []
    for a, b, sector in PAIR_HYPOTHESES:
        for fee in (5.0, 10.0, 20.0):
            sensitivity.append(
                sensitivity_row(args, a, b, sector, args.formation, fee)
            )
        for formation in (126, 252, 504):
            sensitivity.append(
                sensitivity_row(args, a, b, sector, formation, args.fee_bps)
            )
    pd.DataFrame(sensitivity).drop_duplicates().to_csv(
        args.outdir / "cost_window_sensitivity.csv", index=False
    )

    manifest_path = args.prices.with_name("download_manifest.json")
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )
    lines = [
        "# Predeclared statistical-arbitrage research",
        "",
        f"Data through: **{manifest.get('latest_date', 'not documented')}**  ",
        f"Source: **{manifest.get('provider', 'manifest unavailable')}**  ",
        f"Test period starts: **{args.test_start}**  ",
        f"Paths per pair and horizon: **{args.paths:,}**  ",
        f"Seed: **{args.seed}** (horizon-specific deterministic offsets)",
        "",
        "These are fixed hypothesis tests, not ranked trade recommendations.",
        "Adjusted closes are total-return approximations rather than executable prices.",
        "",
        "| Pair | Net cumulative | CAGR | Volatility | Max drawdown | Entries | 12m bootstrap P(loss) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            "| {pair} | {net_cumulative_return:.2%} | {net_cagr:.2%} | "
            "{annualized_volatility:.2%} | {max_drawdown:.2%} | {entries} | "
            "{one_year_bootstrap_probability_loss:.1%} |".format(**row)
        )
    lines += [
        "",
        "No pair is selected as a winner after observing the holdout. Statistical",
        "significance, if any, would not by itself establish implementable alpha.",
    ]
    (args.outdir / "STAT_ARB_RESULTS.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(summary.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", type=Path, default=Path("data/adjusted_close.csv"))
    parser.add_argument(
        "--factors", type=Path, default=Path("data/french_factors_daily.csv")
    )
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
    run(parser.parse_args())


if __name__ == "__main__":
    main()


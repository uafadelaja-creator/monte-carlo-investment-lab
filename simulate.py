"""Reproducible multi-asset Monte Carlo investment lab.

Models three ETF sleeves with correlated, heavy-tailed monthly log returns and
explicit month-end contributions. This is scenario analysis, not a forecast.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


NAMES = ["ARKK proxy", "QUAL proxy", "SPY proxy"]
TICKERS = ["ARKK", "QUAL", "SPY"]
ANNUAL_RETURN_ANCHOR = np.array([0.1363, 0.1447, 0.1522])
MU = np.log1p(ANNUAL_RETURN_ANCHOR)
VOL = np.array([0.50, 0.1228, 0.1274])
CORR = np.array([[1.00, 0.62, 0.58], [0.62, 1.00, 0.92], [0.58, 0.92, 1.00]])
STRESS_CORR = np.array([[1.00, 0.85, 0.80], [0.85, 1.00, 0.97], [0.80, 0.97, 1.00]])
HORIZONS = (1, 3, 6, 12, 24, 36)
START = 500.0
WEEKLY = 100.0
MONTHLY_EQ = WEEKLY * 52.0 / 12.0
AS_OF = "2026-10-02"
VERSION = "0.3"
MARKET_SNAPSHOT = {"ARKK": 89.83, "QUAL": 224.48, "SPY": 769.64}


def run(
    paths: int,
    seed: int,
    *,
    annual_mean: np.ndarray = MU,
    annual_vol: np.ndarray = VOL,
    corr: np.ndarray = CORR,
    weekly: float = WEEKLY,
    months: int = 36,
) -> dict[str, np.ndarray]:
    """Simulate correlated Student-t monthly log returns and cash flows."""
    rng = np.random.default_rng(seed)
    df = 5
    monthly_mean = annual_mean / 12.0
    monthly_vol = annual_vol / np.sqrt(12.0)
    cov = np.outer(monthly_vol, monthly_vol) * corr
    chol = np.linalg.cholesky(cov)
    nav = np.full((paths, len(NAMES)), START)
    wealth = np.empty((months, paths, len(NAMES)), dtype=np.float64)
    unit_nav = np.ones_like(nav)
    unit_wealth = np.empty_like(wealth)
    unit_peak = unit_nav.copy()
    max_drawdown = np.zeros_like(nav)
    drawdown_history = np.empty_like(wealth)
    contribution = weekly * 52.0 / 12.0

    for month in range(months):
        z = rng.standard_normal((paths, len(NAMES))) @ chol.T
        scale = np.sqrt(df / rng.chisquare(df, paths))[:, None]
        log_return = monthly_mean + z * scale / np.sqrt(df / (df - 2))
        gross_return = np.exp(log_return)
        nav *= gross_return
        nav += contribution
        unit_nav *= gross_return
        unit_peak = np.maximum(unit_peak, unit_nav)
        max_drawdown = np.minimum(max_drawdown, unit_nav / unit_peak - 1.0)
        wealth[month] = nav
        unit_wealth[month] = unit_nav
        drawdown_history[month] = max_drawdown

    return {
        "wealth": wealth,
        "unit_wealth": unit_wealth,
        "max_drawdown": drawdown_history,
    }


def summarize(
    out: dict[str, np.ndarray], weekly: float, volatility: np.ndarray = VOL
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for months in HORIZONS:
        contributed = START + weekly * 52.0 / 12.0 * months
        nav = out["wealth"][months - 1]
        for idx, name in enumerate(NAMES):
            values = nav[:, idx]
            unit_values = out["unit_wealth"][months - 1, :, idx]
            percentile = np.percentile(values, [5, 25, 50, 75, 95])
            drawdown = -out["max_drawdown"][months - 1, :, idx]
            gain = values / contributed - 1.0
            rows.append(
                {
                    "portfolio": name,
                    "months": months,
                    "contributed": contributed,
                    "mean_ending_value": values.mean(),
                    "median_ending_value": percentile[2],
                    "p5": percentile[0],
                    "p25": percentile[1],
                    "p75": percentile[3],
                    "p95": percentile[4],
                    "prob_profitable": np.mean(values > contributed),
                    "prob_loss": np.mean(values < contributed),
                    "mean_contribution_adjusted_return": gain.mean(),
                    "median_time_weighted_cagr": np.nan
                    if months < 12
                    else np.median(unit_values ** (12.0 / months) - 1.0),
                    "median_max_drawdown": np.median(drawdown),
                    "p95_max_drawdown": np.percentile(drawdown, 95),
                    "annual_volatility_input": volatility[idx],
                    "prob_beat_spy": np.nan if idx == 2 else np.mean(values > nav[:, 2]),
                }
            )
    return rows


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def horizon36(
    rows: list[dict[str, object]], label: str, weekly: float
) -> list[dict[str, object]]:
    compact = []
    for row in rows:
        if row["months"] != 36:
            continue
        compact.append(
            {
                "scenario": label,
                "portfolio": row["portfolio"],
                "weekly_contribution": weekly,
                "contributed": row["contributed"],
                "median_ending_value": row["median_ending_value"],
                "mean_ending_value": row["mean_ending_value"],
                "p5": row["p5"],
                "p95": row["p95"],
                "prob_profitable": row["prob_profitable"],
                "prob_loss": row["prob_loss"],
                "mean_contribution_adjusted_return": row[
                    "mean_contribution_adjusted_return"
                ],
                "median_time_weighted_cagr": row["median_time_weighted_cagr"],
                "median_max_drawdown": row["median_max_drawdown"],
                "p95_max_drawdown": row["p95_max_drawdown"],
                "prob_beat_spy": row["prob_beat_spy"],
            }
        )
    return compact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=20_261_004)
    parser.add_argument("--outdir", type=Path, default=Path("results"))
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    baseline = run(args.paths, args.seed)
    baseline_rows = summarize(baseline, WEEKLY)
    write_rows(args.outdir / "baseline_summary.csv", baseline_rows)

    lower_return_anchor = np.maximum(ANNUAL_RETURN_ANCHOR - 0.05, -0.99)
    lower_mean = np.log1p(lower_return_anchor)
    risk_scenarios = [
        ("Historical-anchor baseline", MU, VOL, CORR),
        ("Return reversion (-5pp annual)", lower_mean, VOL, CORR),
        (
            "Stress (-5pp return, 1.5x vol, tighter corr)",
            lower_mean,
            VOL * 1.5,
            STRESS_CORR,
        ),
    ]
    scenario_rows: list[dict[str, object]] = []
    for label, mean, vol, corr in risk_scenarios:
        out = run(
            args.paths,
            args.seed,
            annual_mean=mean,
            annual_vol=vol,
            corr=corr,
        )
        scenario_rows.extend(
            horizon36(summarize(out, WEEKLY, vol), label, WEEKLY)
        )
    write_rows(args.outdir / "scenario_summary.csv", scenario_rows)

    contribution_rows: list[dict[str, object]] = []
    for weekly in (0.0, 50.0, 100.0, 200.0):
        out = run(args.paths, args.seed, weekly=weekly)
        contribution_rows.extend(
            horizon36(
                summarize(out, weekly),
                "Historical-anchor baseline",
                weekly,
            )
        )
    write_rows(args.outdir / "contribution_sensitivity.csv", contribution_rows)

    assumptions = {
        "version": VERSION,
        "as_of": AS_OF,
        "paths": args.paths,
        "master_seed": args.seed,
        "seed_policy": (
            "Fixed master seed; identical random draws across scenarios "
            "for paired comparisons."
        ),
        "assets": TICKERS,
        "current_close_snapshot": MARKET_SNAPSHOT,
        "historical_annualized_total_return_anchors": dict(
            zip(TICKERS, ANNUAL_RETURN_ANCHOR.tolist())
        ),
        "annual_log_return_drifts": dict(zip(TICKERS, MU.tolist())),
        "annual_volatility": dict(zip(TICKERS, VOL.tolist())),
        "correlation_matrix": CORR.tolist(),
        "return_distribution": "Multivariate Student-t log returns, df=5",
        "initial_investment": START,
        "weekly_contribution": WEEKLY,
        "monthly_equivalent_contribution": MONTHLY_EQ,
        "contribution_timing": "month-end",
        "drawdown_method": "Unitized time-weighted wealth path; contributions do not reduce drawdown.",
        "cagr_method": "Median CAGR of unitized time-weighted wealth; shown for horizons of at least 12 months.",
        "horizons_months": list(HORIZONS),
        "risk_scenarios": [label for label, _, _, _ in risk_scenarios],
        "contribution_scenarios_weekly": [0.0, 50.0, 100.0, 200.0],
        "limitations": [
            "Historical ETF returns may not persist and regime changes are not predictable.",
            "Student-t tails improve on a Gaussian model but cannot reproduce every crash or liquidity event.",
            "Correlations are unstable and may converge toward one in crises.",
            "ARKK's shorter inception history and active management create selection and regime sensitivity.",
            "ETF history contains survivorship and product-design bias; taxes, fees, spreads, and inflation are omitted.",
            "Contribution-adjusted return is ending value divided by cash contributed minus one; it is not money-weighted IRR.",
        ],
    }
    (args.outdir / "assumptions.json").write_text(
        json.dumps(assumptions, indent=2) + "\n"
    )

    months = np.arange(1, 37)
    median = np.median(baseline["wealth"], axis=1)
    p5 = np.percentile(baseline["wealth"], 5, axis=1)
    p95 = np.percentile(baseline["wealth"], 95, axis=1)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    for idx, ax in enumerate(axes):
        ax.fill_between(
            months,
            p5[:, idx],
            p95[:, idx],
            alpha=0.22,
            label="5th-95th",
        )
        ax.plot(months, median[:, idx], linewidth=2, label="Median")
        ax.plot(
            months,
            START + MONTHLY_EQ * months,
            linestyle="--",
            label="Contributed",
        )
        ax.set_title(NAMES[idx])
        ax.set_xlabel("Months")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Ending value ($)")
    axes[-1].legend(loc="upper left", fontsize=8)
    fig.suptitle("Monte Carlo wealth paths: median and 90% interval")
    fig.tight_layout()
    fig.savefig(args.outdir / "wealth_fan.png", dpi=180)


if __name__ == "__main__":
    main()

"""Reproducible, assumption-based Monte Carlo investment comparison.

This is a scenario engine, NOT a historical estimate or a stock recommendation.
Run: python simulate.py --paths 50000 --seed 20260926
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NAMES = ("Speculative technology", "Established companies", "Diversified index")
ANNUAL_MEAN = np.array([0.14, 0.10, 0.08])  # illustrative arithmetic expected returns
ANNUAL_VOL = np.array([0.50, 0.25, 0.18])
CORRELATION = np.array([[1.0, 0.70, 0.55], [0.70, 1.0, 0.80], [0.55, 0.80, 1.0]])
HORIZONS = (1, 3, 5, 10)
MONTHS_PER_YEAR = 12
START = 500.0
WEEKLY_CONTRIBUTION = 100.0
MONTHLY_CONTRIBUTION = WEEKLY_CONTRIBUTION * 52 / 12


def simulate(paths: int, seed: int, years: int = 10,
             annual_mean: np.ndarray = ANNUAL_MEAN,
             annual_vol: np.ndarray = ANNUAL_VOL):
    if paths < 1 or years < 1:
        raise ValueError("paths and years must be positive")
    rng = np.random.default_rng(seed)
    chol = np.linalg.cholesky(CORRELATION)
    wealth = np.full((paths, 3), START)
    # Unitized NAV tracks investment drawdown without deposits masking losses.
    nav = np.ones((paths, 3))
    peak = nav.copy()
    max_dd = np.zeros((paths, 3))
    outcome = {}
    monthly = []
    drift = np.log1p(annual_mean) / 12 - 0.5 * annual_vol**2 / 12
    scale = annual_vol / np.sqrt(12)
    for month in range(1, years * 12 + 1):
        z = rng.standard_normal((paths, 3)) @ chol.T
        gross = np.exp(drift + z * scale)
        wealth *= gross
        wealth += MONTHLY_CONTRIBUTION  # deposit at end of each month
        nav *= gross
        peak = np.maximum(peak, nav)
        max_dd = np.maximum(max_dd, 1 - nav / peak)
        q = np.percentile(wealth, [5, 50, 95], axis=0)
        monthly.append((month, q))
        if month % 12 == 0 and month // 12 in HORIZONS:
            outcome[month // 12] = (wealth.copy(), max_dd.copy())
    return outcome, monthly


def summarize(outcome):
    rows = []
    for year in HORIZONS:
        wealth, drawdown = outcome[year]
        total_deposits = START + 52 * WEEKLY_CONTRIBUTION * year
        for i, name in enumerate(NAMES):
            w = wealth[:, i]
            rows.append({
                "years": year, "portfolio": name,
                "total_contributions": total_deposits,
                "mean_ending_wealth": np.mean(w),
                "p05_ending_wealth": np.percentile(w, 5),
                "p25_ending_wealth": np.percentile(w, 25),
                "median_ending_wealth": np.median(w),
                "p75_ending_wealth": np.percentile(w, 75),
                "p95_ending_wealth": np.percentile(w, 95),
                "p_below_contributions": np.mean(w < total_deposits),
                "p_beat_index": np.mean(w > wealth[:, 2]) if i != 2 else np.nan,
                "median_max_drawdown": np.median(drawdown[:, i]),
                "p_drawdown_over_50pct": np.mean(drawdown[:, i] > .50),
            })
    return rows


def write_outputs(outdir: Path, rows, monthly, paths: int, seed: int):
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir / "baseline_summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    assumptions = {
        "status": "ILLUSTRATIVE ASSUMPTIONS, NOT HISTORICALLY CALIBRATED",
        "paths": paths, "seed": seed, "monthly_steps": 120,
        "start_usd": START, "weekly_contribution_usd": WEEKLY_CONTRIBUTION,
        "deposit_model": "52/12 times the weekly amount, deposited at each month end",
        "portfolios": list(NAMES), "annual_arithmetic_mean_assumptions": ANNUAL_MEAN.tolist(),
        "annual_volatility_assumptions": ANNUAL_VOL.tolist(),
        "correlations": CORRELATION.tolist(),
        "return_model": "joint correlated lognormal, constant parameters, no bankruptcy jumps",
        "excluded": ["inflation", "taxes", "fees", "trading costs", "survivorship", "regime shifts"],
    }
    (outdir / "assumptions.json").write_text(json.dumps(assumptions, indent=2) + "\n")
    months = np.array([m for m, _ in monthly])
    q = np.stack([x for _, x in monthly])
    fig, axs = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    colors = ("#7041a6", "#167b8e", "#555e6b")
    for i, (ax, name) in enumerate(zip(axs, NAMES)):
        ax.fill_between(months / 12, q[:, 0, i], q[:, 2, i], color=colors[i], alpha=.16, label="5th–95th")
        ax.plot(months / 12, q[:, 1, i], color=colors[i], lw=2, label="Median")
        ax.plot(months / 12, START + MONTHLY_CONTRIBUTION * months,
                color="black", linestyle="--", lw=1, label="Contributed")
        ax.set_title(name)
        ax.set_xlabel("Years")
        ax.grid(alpha=.2)
    axs[0].set_ylabel("Portfolio value (USD)")
    axs[-1].legend(fontsize=8)
    fig.suptitle("Illustrative scenarios only · assumed returns, not forecasts", fontsize=12)
    fig.tight_layout()
    fig.savefig(outdir / "wealth_fan.png", dpi=170)
    plt.close(fig)


def write_sensitivity(outdir: Path, paths: int, seed: int):
    """Show how assumed speculative mean and volatility change the conclusion."""
    rows = []
    for mean in (0.08, 0.14, 0.20):
        for vol in (0.40, 0.50, 0.60):
            means = ANNUAL_MEAN.copy()
            vols = ANNUAL_VOL.copy()
            means[0], vols[0] = mean, vol
            outcomes, _ = simulate(paths, seed, annual_mean=means, annual_vol=vols)
            wealth, _ = outcomes[10]
            rows.append({
                "assumed_spec_annual_mean": mean,
                "assumed_spec_annual_volatility": vol,
                "spec_10y_median_usd": np.median(wealth[:, 0]),
                "index_10y_median_usd": np.median(wealth[:, 2]),
                "spec_10y_p_below_deposits": np.mean(wealth[:, 0] < START + 520 * WEEKLY_CONTRIBUTION),
                "spec_10y_p_beat_paired_index": np.mean(wealth[:, 0] > wealth[:, 2]),
            })
    with (outdir / "sensitivity.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=20260926)
    parser.add_argument("--outdir", type=Path, default=Path("results"))
    parser.add_argument("--sensitivity", action="store_true", help="run nine speculative assumption variants")
    args = parser.parse_args()
    outcome, monthly = simulate(args.paths, args.seed)
    rows = summarize(outcome)
    write_outputs(args.outdir, rows, monthly, args.paths, args.seed)
    if args.sensitivity:
        write_sensitivity(args.outdir, args.paths, args.seed)
    for row in rows:
        print(f"{row['years']:2d}y {row['portfolio']:<23} "
              f"median=${row['median_ending_wealth']:,.0f} "
              f"p05=${row['p05_ending_wealth']:,.0f} "
              f"p95=${row['p95_ending_wealth']:,.0f} "
              f"Pr(loss)={row['p_below_contributions']:.1%}")


if __name__ == "__main__":
    main()

"""Reproducible Markdown research note based ONLY on supplied observed data."""
from __future__ import annotations

from datetime import date
from typing import Mapping

import numpy as np
import pandas as pd

from .portfolio import benchmark_diagnostics, concentration, metric_table, sector_allocation


def pct(value: float) -> str:
    return f"{value * 100:.2f}%" if np.isfinite(value) else "N/A"


def money(value: float) -> str:
    return f"${value:,.0f}" if np.isfinite(value) else "N/A"


def markdown_table(frame: pd.DataFrame, formats: Mapping[str, str] | None = None) -> str:
    formats = formats or {}
    df = frame.copy()
    df.index = df.index.astype(str)
    for name in df.columns:
        if name in formats:
            mode = formats[name]
            if mode == "percent":
                df[name] = df[name].apply(lambda x: pct(float(x)))
            elif mode == "money":
                df[name] = df[name].apply(lambda x: money(float(x)))
            elif mode == "percent_points":
                df[name] = df[name].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
            else:
                df[name] = df[name].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    cols = ["Series"] + list(df.columns)
    rows = [[idx] + [str(x) for x in values] for idx, values in df.iterrows()]
    escape = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    return "| " + " | ".join(cols) + " |\n| " + " | ".join(["---"]*len(cols)) + " |\n" + "\n".join("| " + " | ".join(escape(x) for x in row) + " |" for row in rows)


def build_report(
    monthly: pd.DataFrame,
    data_source: str,
    holdings: pd.DataFrame | None = None,
    weights: pd.Series | None = None,
    scenario: pd.DataFrame | None = None,
    assumptions: Mapping[str, object] | None = None,
    annual_rf: float = 0.0,
    as_of: str | None = None,
) -> str:
    """Build an as-of dated Markdown report; no fictional metrics or forecasts."""
    metrics = metric_table(monthly, annual_rf)
    diagnostics = benchmark_diagnostics(monthly)
    first = monthly.index[0].date().isoformat() if isinstance(monthly.index, pd.DatetimeIndex) else str(monthly.index[0])
    last = monthly.index[-1].date().isoformat() if isinstance(monthly.index, pd.DatetimeIndex) else str(monthly.index[-1])
    today = as_of or date.today().isoformat()
    shariah = [x for x in ("SPUS", "HLAL") if x in monthly]
    observations = []
    spy_cagr = metrics.loc["SPY", "CAGR"]
    for ticker in shariah:
        diff = metrics.loc[ticker, "CAGR"] - spy_cagr
        word = "higher" if diff > 0 else "lower" if diff < 0 else "equal to"
        observations.append(f"- **{ticker}** CAGR was **{abs(diff)*100:.2f} percentage points {word}** than SPY over this particular observed window (not causal impact of Shariah screening).")
    extra = "\n".join(observations)
    mformats = {"CAGR": "percent", "Annual volatility": "percent", "Max monthly drawdown": "percent", "Total return": "percent", "Sharpe": "float", "Sortino": "float"}
    dformats = {"Tracking error (annual)": "percent", "Annualized arithmetic active return": "percent", "Beta vs SPY": "float", "Correlation vs SPY": "float"}
    text = [
        "# Shariah-Compliant Equity Portfolio: Comparative Research Note",
        f"**Report generated:** {today}  ",
        f"**Observed common monthly-return window:** {first} to {last} ({len(monthly)} monthly observations)  ",
        f"**Data provenance:** {data_source}  ",
        "**Scope:** Historical adjusted-price comparisons and hypothetical resampled scenarios; not religious certification or investment advice.\n",
        "## Executive summary",
        "This is an **observational performance comparison** of Shariah-screened US equity ETFs versus the SPY conventional benchmark. SPY is **not** represented as Shariah-compliant. Differences may reflect sector weights, market cycles, expenses and stock concentration; they do not identify the causal effect of Islamic screening.",
        extra or "- Shariah ETF comparisons were not available in these inputs.",
        "\n## Historical risk and return",
        "All measures below use the **same completed calendar-month returns** for fair ETF/basket comparison. The drawdown is based on month-end observations and may understate daily intramonth declines.",
        markdown_table(metrics, mformats),
        "\n## Risk diagnostics versus SPY",
        markdown_table(diagnostics, dformats),
    ]
    if "PIT screened strategy" in monthly.columns:
        text.extend([
            "\n## User-supplied point-in-time eligibility strategy",
            "The historical strategy uses only complete eligibility snapshots dated before each relevant return month, with a maximum age for evidence. This prevents *software-level* future-information leakage, but the lab does not independently authenticate screening provider decisions, delisted-stock completeness or whether Shariah requirements were correctly applied. Therefore the uploaded history is **not certified** solely because the software accepted the CSV.",
        ])
    if holdings is not None and weights is not None:
        snapshot_dates = ", ".join(sorted(set(map(str, holdings["as_of"]))))
        snapshot = f"**Constituent evidence dates:** {snapshot_dates}."
        concentrate = concentration(weights)
        sectors = sector_allocation(weights, holdings).to_frame("Weight")
        text.extend([
            "\n## Custom basket — historical exposure illustration",
            snapshot,
            "The basket uses **dated fund holdings or user-supplied screening evidence**. A fund holdings snapshot is **not** a stock-level Shariah certification and cannot establish that a ticker qualified in earlier years. Any returns before the evidence date are retrospective backcasts with **constituent-selection/survivorship and look-ahead bias**; they must not be presented as a historically implementable Shariah strategy.",
            f"- Number of stocks: **{len(weights)}**; largest position: **{pct(concentrate['Largest position'])}**; effective number of holdings: **{concentrate['Effective holdings']:.2f}**; top-five exposure: **{pct(concentrate['Top 5 weight'])}**.",
            "\n### Portfolio weights",
            markdown_table(weights.to_frame("Weight"), {"Weight": "percent"}),
            "\n### User-editable broad sector grouping",
            markdown_table(sectors, {"Weight": "percent"}),
        ])
    if scenario is not None:
        formats = {col: ("money" if "($)" in col else "percent_points" if "(%)" in col else "float") for col in scenario.columns}
        text.extend([
            "\n## Hypothetical paired-block Monte Carlo results",
            "Model frequencies are conditional on repeatedly resampling historical monthly return blocks. These are *not calibrated probabilities of future events*, nor price targets. Each asset faces the **same sampled historical months** within each scenario.",
            markdown_table(scenario, formats),
        ])
    if assumptions:
        text.extend(["\n### Scenario assumptions"] + [f"- **{k}:** {v}" for k,v in assumptions.items()])
    text.extend([
        "\n## Shariah methodology and data integrity",
        "A compliant ETF's inclusion process uses both **business activity exclusions** and **financial ratio screening**. Fund methodologies are not interchangeable. Screening results can change through time. Stock holdings do not document a full historical compliance series. An independently validated point-in-time simulation would require dated constituent universes, financial screens, dividend purification ratios and reconstitution rules for **each past rebalance date**.",
        "\n## Limitations and next research tests",
        "- Common post-inception ETF history is short and does not cover every macroeconomic regime.",
        "- Past winners selected using today's constituents introduce look-ahead/survivorship bias even when optimization uses only prior returns.",
        "- Dividend/split-adjusted traded prices approximate reinvestment; they are not fund NAV or guaranteed executable values.",
        "- Monthly rebalancing is modeled without trading costs, tax drag, tracking spreads, market impact, inflation or purification.",
        "- Mean-variance optimized weights depend on estimated parameters; shrinkage and walk-forward evaluation reduce some overfitting but do not fix universe-selection bias.",
        "- Verify ETF returns and compliance information against issuer and index-provider primary documents before use outside research.",
        "\n## References",
        "- SP Funds, SPUS issuer page and dated portfolio holdings: https://www.sp-funds.com/SPUS/",
        "- Wahed, HLAL issuer page and purification statements: https://www.wahed.com/hlal",
        "- S&P DJI, Shariah indices background: https://www.spglobal.com/spdji/en/indices/equity/sp-500-shariah-industry-exclusions-index/",
        "- HLAL regulatory methodology: https://www.sec.gov/Archives/edgar/data/1683471/000089418926026510/R4.htm",
        "- Yahoo Finance access library: https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html",
        "\n*Research exercise only. No stock recommendation, Shariah opinion, or assurance of a positive investment outcome.*",
    ])
    return "\n\n".join(filter(None, text)) + "\n"

#!/usr/bin/env python3
"""Independently recompute the provisional PAIR//LAB snapshot with statsmodels.

Usage:
    pip install numpy pandas scipy statsmodels
    python stat-arb-dashboard/recompute_audit.py --allow-unadjusted

This checks estimates, not trading efficacy. It does not update screen.json.
The third-party close price columns have unverified adjustment status.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

ROOT = Path(__file__).resolve().parent
URL = "https://raw.githubusercontent.com/yennanliu/finance_data/main/data/prices/{}.csv"


def fdr_bh(pvalues):
    p = np.asarray(pvalues, dtype=float)
    if not np.isfinite(p).all() or np.any(p < 0) or np.any(p > 1):
        raise ValueError("Invalid p-values")
    result = np.zeros(len(p))
    prior = 1.0
    for rank, idx in reversed(list(enumerate(np.argsort(p), start=1))):
        prior = min(prior, p[idx] * len(p) / rank)
        result[idx] = prior
    return result.tolist()


def fetch(ticker, date):
    url = URL.format(ticker.lower())
    with urlopen(Request(url, headers={"User-Agent": "PAIR-LAB/1.0"}), timeout=25) as res:
        body = res.read()
    df = pd.read_csv(io.BytesIO(body), parse_dates=["date"])
    if not {"date", "close", "div", "split"} <= set(df):
        raise ValueError("Missing source columns for " + ticker)
    if not df.date.is_monotonic_increasing or df.date.duplicated().any():
        raise ValueError("Dates not sorted or duplicate for " + ticker)
    df = df[df.date <= pd.Timestamp(date)].set_index("date")
    if len(df) < 320 or not np.isfinite(df.close).all() or (df.close <= 0).any():
        raise ValueError("Invalid/short price series " + ticker)
    return df.close.astype(float), {
        "url": url, "sha256": hashlib.sha256(body).hexdigest(),
        "last_date": str(df.index[-1].date()),
        "div_events": int(df["div"].notna().sum()),
        "split_events": int(df["split"].notna().sum())}


def measure(a, b, values, date):
    xy = pd.concat([values[a].rename("a"), values[b].rename("b")], axis=1,
                   join="inner").dropna().loc[:date]
    if len(xy) < 320:
        raise ValueError("Not enough shared dates for " + a + "/" + b)
    training = np.log(xy.iloc[-253:-1])
    observed = np.log(xy.iloc[-1])
    if len(training) != 252:
        raise AssertionError("Expected 252 formation dates")
    y, x = training.a.to_numpy(), training.b.to_numpy()
    beta, intercept = np.polyfit(x, y, 1)
    residual = y - intercept - beta * x
    z = (observed.a - intercept - beta * observed.b -
         np.mean(residual[-60:])) / np.std(residual[-60:], ddof=1)
    returns = training.diff().dropna().iloc[-90:]
    corr = float(returns.a.corr(returns.b))
    t, p, critical = coint(y, x, trend="c", autolag="aic")
    arr = np.array([t, p, corr, z, beta])
    if not np.isfinite(arr).all():
        raise ValueError("Non-finite model output for " + a + "/" + b)
    return {"pair": a + "/" + b, "as_of": str(xy.index[-1].date()),
            "eg_t": float(t), "eg_p": float(p),
            "eg_5pct_critical": float(critical[1]),
            "corr90": corr, "z60": float(z), "beta": float(beta)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default="2026-11-11")
    parser.add_argument("--allow-unadjusted", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "independent_audit.json")
    args = parser.parse_args()
    if not args.allow_unadjusted:
        parser.error("Explicit --allow-unadjusted required: price adjustments not verified")
    snapshot = json.loads((ROOT / "data" / "screen.json").read_text())
    if args.as_of != snapshot["as_of"]:
        parser.error("As-of date must match published screen for comparisons")
    tickers = sorted({t for p in snapshot["pairs"] for t in [p["a"], p["b"]]})
    values, hashes = {}, {}
    for t in tickers:
        values[t], hashes[t] = fetch(t, args.as_of)
    measurements = [measure(p["a"], p["b"], values, args.as_of) for p in snapshot["pairs"]]
    qvalues = fdr_bh([r["eg_p"] for r in measurements])
    different = []
    for old, new, q in zip(snapshot["pairs"], measurements, qvalues):
        new["fdr_q"] = q
        new["nominal_gates"] = new["eg_p"] < .05 and new["corr90"] > .75 and abs(new["z60"]) >= 2
        delta = {}
        for key, old_key, tol in [
            ("eg_p", "p", .005), ("fdr_q", "q", .005),
            ("corr90", "correlation", .005),
            ("z60", "z", .03), ("beta", "beta", .03)]:
            if abs(new[key] - old[old_key]) > tol:
                delta[key] = {"published": old[old_key], "independent": new[key]}
        if delta:
            different.append({"pair": new["pair"], "differences": delta})
    summary = {"pairs_tested": len(measurements),
               "nominal_cointegration": sum(r["eg_p"] < .05 for r in measurements),
               "fdr_survivors": sum(r["fdr_q"] < .05 for r in measurements),
               "nominal_alert_gates": sum(r["nominal_gates"] for r in measurements),
               "published_discrepancies": len(different)}
    report = {
        "status": "RESEARCH RECOMPUTATION; NOT TRADE VALIDATION",
        "date": args.as_of, "source_hashes": hashes,
        "methods": "statsmodels coint, trend=c, autolag=aic; 252 formation days; 90 return-correlation days; 60 residual Z days; BH FDR",
        "source_adjustment_verified": False,
        "out_of_sample_net_pnl_verified": False,
        "summary": summary, "pairs": measurements, "differences": different}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print("Audit written:", args.output)
    if different:
        print("WARNING: The prior screen differs from statsmodels; inspect the audit JSON.")


if __name__ == "__main__":
    main()

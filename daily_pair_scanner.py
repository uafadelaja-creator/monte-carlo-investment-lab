#!/usr/bin/env python3
"""Daily, exploratory PAIR//LAB discovery across sector-related stock combinations.

Independent from the frozen three-pair backtest and archived 18-pair dashboard.
Uses free Yahoo Finance adjusted close estimates; no trade execution or claims
of profitable signals. Fails closed instead of publishing stale/partial results.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "stat-arb-dashboard" / "data" / "daily_discovery.json"
# Each candidate is generated afresh from the full cross-product within its peer
# group; unlike the 18-pair archived screen, these are not fixed hypotheses.
PEER_GROUPS = {
    "Semiconductors": ("NVDA", "AMD", "AVGO", "QCOM", "TXN", "ADI", "MU", "MRVL", "ON", "INTC"),
    "Banks": ("JPM", "BAC", "C", "WFC", "GS", "MS", "USB", "PNC"),
    "Energy": ("XOM", "CVX", "COP", "EOG", "OXY", "SLB", "HAL"),
    "Payments": ("V", "MA", "AXP", "PYPL", "FIS", "GPN", "FI"),
    "Consumer staples": ("KO", "PEP", "PG", "CL", "KMB", "MDLZ", "KHC"),
    "Defense": ("LMT", "RTX", "NOC", "GD", "LHX", "AVAV", "KTOS"),
    "Software": ("MSFT", "ORCL", "CRM", "ADBE", "NOW", "INTU"),
    "Fintech": ("SOFI", "NU", "HOOD", "AFRM", "COIN", "XYZ"),
    "Retail": ("WMT", "TGT", "COST", "KR", "DG", "DLTR"),
    "Utilities": ("NEE", "DUK", "SO", "AEP", "EXC", "XEL"),
    "Airlines": ("DAL", "UAL", "AAL", "LUV", "JBLU"),
}
MIN_SESSIONS = 320
FORMATION = 252
Z_WINDOW = 60
CORR_WINDOW = 90
MIN_FOR_TEST = 0.50
MAX_STALE_DAYS = 5


def all_candidates() -> list[tuple[str, str, str]]:
    seen = set()
    result = []
    for industry, names in PEER_GROUPS.items():
        for a, b in itertools.combinations(names, 2):
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            result.append((a, b, industry))
    return result


def fdr_bh(pvalues: list[float]) -> list[float]:
    """BH adjustment over *all* enumerated hypotheses; untested rows get p=1."""
    if not pvalues:
        return []
    p = np.asarray(pvalues, dtype=float)
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("Invalid p-values for BH correction")
    answer = np.ones(len(p))
    running = 1.0
    for rank, idx in reversed(list(enumerate(np.argsort(p), start=1))):
        running = min(running, float(p[idx]) * len(p) / rank)
        answer[idx] = running
    return answer.tolist()


def download_adjusted_close(tickers: list[str]) -> pd.DataFrame:
    """Download each small batch, enforcing an explicit auto-adjusted series."""
    import yfinance as yf

    pieces = []
    for offset in range(0, len(tickers), 12):
        group = tickers[offset:offset + 12]
        last_error = None
        for attempt in range(3):
            try:
                raw = yf.download(
                    tickers=group, period="2y", interval="1d",
                    auto_adjust=True, actions=False, progress=False,
                    threads=False, timeout=25, group_by="column",
                )
                if raw.empty:
                    raise ValueError("Empty vendor response")
                if isinstance(raw.columns, pd.MultiIndex):
                    if "Close" in raw.columns.get_level_values(0):
                        close = raw["Close"]
                    else:
                        close = raw.xs("Close", axis=1, level=1)
                else:
                    close = raw[["Close"]].rename(columns={"Close": group[0]})
                if isinstance(close, pd.Series):
                    close = close.to_frame(name=group[0])
                close.columns = [str(x).upper() for x in close.columns]
                close = close.loc[:, ~close.columns.duplicated()]
                close = close.reindex(columns=group)
                close.index = pd.DatetimeIndex(pd.to_datetime(close.index)).tz_localize(None).normalize()
                close = close.loc[~close.index.duplicated(keep="last")].sort_index()
                pieces.append(close)
                break
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
        else:
            raise RuntimeError(f"Price download failed for {group}: {last_error}")
    prices = pd.concat(pieces, axis=1).loc[:, ~pd.concat(pieces, axis=1).columns.duplicated()]
    prices = prices.apply(pd.to_numeric, errors="coerce")
    return prices.where(np.isfinite(prices) & (prices > 0))


def select_as_of(prices: pd.DataFrame, now: datetime) -> tuple[str, list[str]]:
    valid = {}
    for ticker in prices.columns:
        series = prices[ticker].dropna()
        if len(series) >= MIN_SESSIONS:
            valid[ticker] = str(series.index[-1].date())
    if len(valid) < int(0.7 * prices.shape[1]):
        raise RuntimeError(f"Insufficient history: {len(valid)}/{prices.shape[1]} usable tickers")
    latest = max(valid.values())
    current = [ticker for ticker, last in valid.items() if last == latest]
    if len(current) < int(0.7 * prices.shape[1]):
        raise RuntimeError(f"Price feed inconsistent: only {len(current)}/{prices.shape[1]} stocks current through {latest}")
    age = (now.date() - datetime.strptime(latest, "%Y-%m-%d").date()).days
    if age < 0 or age > MAX_STALE_DAYS:
        raise RuntimeError(f"Rejecting stale/future data: last market date {latest}, age {age} days")
    return latest, sorted(current)


def measure(a: str, b: str, industry: str, prices: pd.DataFrame, as_of: str) -> dict:
    frame = prices[[a, b]].loc[:as_of].dropna()
    if len(frame) < MIN_SESSIONS or str(frame.index[-1].date()) != as_of:
        raise ValueError("Insufficient aligned recent prices")
    logged = np.log(frame.iloc[-253:])
    training = logged.iloc[:-1]
    observation = logged.iloc[-1]
    y, x = training[a].to_numpy(), training[b].to_numpy()
    if np.std(x) < 1e-7 or np.std(y) < 1e-7:
        raise ValueError("Near-constant log prices")
    beta, intercept = np.polyfit(x, y, 1)
    residual = y - intercept - beta * x
    tail = residual[-Z_WINDOW:]
    sigma = float(np.std(tail, ddof=1))
    if sigma < 1e-9:
        raise ValueError("Spread variance too small")
    z = (float(observation[a]) - intercept - beta * float(observation[b]) - float(np.mean(tail))) / sigma
    returns = training.diff().dropna().iloc[-CORR_WINDOW:]
    corr = float(returns[a].corr(returns[b]))
    first_beta = float(np.polyfit(x[:126], y[:126], 1)[0])
    last_beta = float(np.polyfit(x[-126:], y[-126:], 1)[0])
    drift = abs(last_beta - first_beta) / max(abs(first_beta), .10)
    if not all(map(math.isfinite, (beta, z, corr, drift))):
        raise ValueError("Non-finite model output")
    # A predeclared correlation gate saves API runner time. A skipped test has
    # p=1 and stays in the full BH family, rather than reducing test counts.
    tested = corr > MIN_FOR_TEST
    p = float(coint(y, x, trend="c", autolag="aic")[1]) if tested else 1.0
    if not math.isfinite(p):
        raise ValueError("Invalid cointegration p-value")
    return {
        "a": a, "b": b, "pair": f"{a}/{b}", "industry": industry,
        "correlation": round(corr, 5), "z": round(float(z), 4),
        "p": p, "q": 1.0, "beta": round(float(beta), 5),
        "beta_drift_pct": round(float(drift * 100), 1),
        "cointegration_tested": tested,
    }


def scan(prices: pd.DataFrame, now: datetime, previous: dict | None = None) -> dict:
    as_of, current = select_as_of(prices, now)
    current_set = set(current)
    rows, skipped = [], []
    for a, b, industry in all_candidates():
        if a not in current_set or b not in current_set:
            skipped.append({"pair": f"{a}/{b}", "reason": "missing/current price data"})
            rows.append({"a": a, "b": b, "pair": f"{a}/{b}", "industry": industry,
                         "p": 1.0, "q": 1.0, "status": "data_unavailable"})
            continue
        try:
            rows.append(measure(a, b, industry, prices, as_of))
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
            skipped.append({"pair": f"{a}/{b}", "reason": str(exc)})
            rows.append({"a": a, "b": b, "pair": f"{a}/{b}", "industry": industry,
                         "p": 1.0, "q": 1.0, "status": "data_unavailable"})

    qvalues = fdr_bh([r["p"] for r in rows])
    prior_seen = set((previous or {}).get("ever_qualified_pairs", []))
    qualified_now = set()
    for row, q in zip(rows, qvalues):
        row["q"] = round(q, 8)
        if row.get("status") == "data_unavailable":
            continue
        nominal = row["p"] < .05 and row["correlation"] > .75 and abs(row["z"]) >= 2
        stable = row["beta"] > 0 and row["beta_drift_pct"] <= 30
        qualified = nominal and row["q"] < .05 and stable
        row["gates"] = {
            "cointegration": row["p"] < .05,
            "correlation": row["correlation"] > .75,
            "deviation": abs(row["z"]) >= 2,
            "fdr": row["q"] < .05,
            "beta_stable": stable,
        }
        row["status"] = ("research_candidate" if qualified else
                         "preliminary_watch" if nominal else "not_qualified")
        row["p"] = round(row["p"], 8)
        if qualified:
            qualified_now.add(row["pair"])
        row["first_qualified_today"] = qualified and row["pair"] not in prior_seen

    # Most promising first; data-unavailable at the bottom. No profitability rank.
    rank = {"research_candidate": 0, "preliminary_watch": 1,
            "not_qualified": 2, "data_unavailable": 3}
    rows.sort(key=lambda r: (rank[r["status"]], r["q"],
                             -abs(r.get("z", 0)), -r.get("correlation", -1)))
    new = sorted(qualified_now - prior_seen)
    return {
        "schema_version": 1,
        "kind": "DAILY_EXPLORATORY_DISCOVERY_NOT_TRADE_SIGNALS",
        "as_of": as_of,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance (auto_adjust=True, free, best-effort)",
        "method": ("Generate peer-sector combinations; 252 completed formation sessions "
                   "excluding observation; 90-return correlation; Engle-Granger "
                   "trend=c autolag=AIC when r>0.50; 60-residual Z; "
                   "BH FDR across every enumerated hypothesis (untested p=1); "
                   "positive beta and <=30% half-window beta drift."),
        "warnings": [
            "Exploratory multiple-comparison scan, not an independently validated trading edge.",
            "Yahoo historical adjusted closes are vendor estimates, not certified executable quotes.",
            "No walk-forward net-of-cost/borrow/earnings validation or automatic orders.",
            "Weekends and market holidays repeat the most recent completed session.",
            "New means first qualified since this daily history began, not a recommendation.",
        ],
        "summary": {
            "stocks_in_universe": len(set(itertools.chain.from_iterable(PEER_GROUPS.values()))),
            "stocks_current": len(current),
            "pairs_enumerated": len(rows),
            "pairs_tested_cointegration": sum(r.get("cointegration_tested", False) for r in rows),
            "pairs_unavailable": len(skipped),
            "nominal_combined_gates": sum(r["status"] in ("preliminary_watch", "research_candidate") for r in rows),
            "fdr_survivors": sum(r.get("q", 1) < .05 for r in rows),
            "research_candidates": len(qualified_now),
            "newly_qualified": len(new),
        },
        "new_qualified_pairs": new,
        "ever_qualified_pairs": sorted(prior_seen | qualified_now),
        "pairs": rows,
        "skipped": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    prior = json.loads(args.output.read_text()) if args.output.exists() else {}
    tickers = sorted(set(itertools.chain.from_iterable(PEER_GROUPS.values())))
    prices = download_adjusted_close(tickers)
    result = scan(prices, now, prior)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"as_of": result["as_of"], **result["summary"],
                      "new": result["new_qualified_pairs"]}, indent=2))
    print(f"Saved {args.output}; educational research only.")


if __name__ == "__main__":
    main()

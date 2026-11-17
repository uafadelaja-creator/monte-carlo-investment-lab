#!/usr/bin/env python3
"""Two in-depth, dated PAIR//LAB peer reviews per UTC day.

Runs with the same validated prices as daily_pair_scanner.py. Stores an
idempotent historical ledger and deliberately distinguishes a retrospective
paper replay from independently out-of-sample profitability evidence.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

LEDGER = Path(__file__).resolve().parent / "stat-arb-dashboard" / "data" / "review_history.json"
REVIEW_COUNT = 2
HOLD_SESSIONS = 5
COST_PER_LEG_PER_SIDE = .001  # 10 bps on each leg, at entry and exit
BORROW_APR = .03
REPLAY_WINDOW = 150


def finite(value):
    return round(float(value), 6) if value is not None and math.isfinite(float(value)) else None


def choose_pairs(rows: list[dict], records: list[dict], day: str, count: int = REVIEW_COUNT) -> list[dict]:
    """Prefer new/stronger names, diversify sectors, never repeat a dated review."""
    done_today = {r["pair"] for r in records if r["review_date"] == day}
    eligible = [r for r in rows if r["status"] != "data_unavailable" and r["pair"] not in done_today]
    dates = {}
    for r in records:
        pair = r["pair"]
        dates[pair] = max(dates.get(pair, ""), r["review_date"])
    # Unreviewed pairs take priority until all have been seen. Stronger current
    # hypotheses lead the queue; if no novel combinations remain, revisit oldest.
    status_rank = {"research_candidate": 0, "preliminary_watch": 1, "not_qualified": 2}
    eligible.sort(key=lambda r: (
        r["pair"] in dates,
        dates.get(r["pair"], ""),
        status_rank.get(r["status"], 3),
        r.get("q", 1),
        r.get("p", 1),
        -r.get("correlation", -1),
        -abs(r.get("z", 0)),
        r["pair"],
    ))
    selected, industries = [], set()
    for _ in range(min(count, len(eligible))):
        candidate = next((p for p in eligible if p["industry"] not in industries), eligible[0])
        selected.append(candidate)
        industries.add(candidate["industry"])
        eligible.remove(candidate)
    return selected


def z_at(log_prices: pd.DataFrame, offset: int) -> tuple[float, float, float]:
    """Observation at offset uses strictly earlier formation observations."""
    formation = log_prices.iloc[offset - 252:offset]
    if len(formation) != 252:
        raise ValueError("Not enough formation days")
    a, b = formation.columns
    x, y = formation[b].to_numpy(), formation[a].to_numpy()
    beta, intercept = np.polyfit(x, y, 1)
    residual = y - intercept - beta * x
    scale = np.std(residual[-60:], ddof=1)
    if scale < 1e-9 or not math.isfinite(float(scale)):
        raise ValueError("Invalid residual dispersion")
    obs = log_prices.iloc[offset]
    z = (float(obs[a]) - intercept - beta * float(obs[b]) - np.mean(residual[-60:])) / scale
    corr = float(formation.diff().dropna().iloc[-90:][a].corr(formation.diff().dropna().iloc[-90:][b]))
    return float(z), float(beta), corr


def replay(price_frame: pd.DataFrame) -> dict:
    """Non-overlapping five-session, equal-dollar two-leg retrospective examples.

    A T close signal is entered at T+1 close, exited at T+6 close. This is NOT
    an executable quote or independent OOS validation: the pair was selected
    based on the full current cross-sectional scan before this historical replay.
    """
    log_prices = np.log(price_frame)
    n = len(price_frame)
    entries = []
    start = max(252, n - REPLAY_WINDOW)
    last_t = n - (HOLD_SESSIONS + 2)
    next_eligible_t = start
    for t in range(start, last_t + 1):
        if t < next_eligible_t:
            continue
        try:
            z, beta, corr = z_at(log_prices, t)
        except (ValueError, np.linalg.LinAlgError):
            continue
        if abs(z) < 2 or corr <= .75 or beta <= 0:
            continue
        entry_idx, exit_idx = t + 1, t + 1 + HOLD_SESSIONS
        entry_prices = price_frame.iloc[entry_idx].to_numpy(dtype=float)
        exit_prices = price_frame.iloc[exit_idx].to_numpy(dtype=float)
        if (entry_prices <= 0).any() or (exit_prices <= 0).any():
            continue
        returns = exit_prices / entry_prices - 1
        direction = -1 if z > 0 else 1  # short A, long B when spread is high
        gross = .5 * direction * returns[0] - .5 * direction * returns[1]
        fees = 2 * COST_PER_LEG_PER_SIDE  # each fill is 1x gross notional across two legs
        borrow = .5 * BORROW_APR * HOLD_SESSIONS / 252
        net = float(gross - fees - borrow)
        entries.append({
            "signal_date": str(price_frame.index[t].date()),
            "entry_date": str(price_frame.index[entry_idx].date()),
            "exit_date": str(price_frame.index[exit_idx].date()),
            "z_at_signal": finite(z),
            "direction": "SHORT_A_LONG_B" if z > 0 else "LONG_A_SHORT_B",
            "gross_return_pct": finite(100 * gross),
            "net_return_pct": finite(100 * net),
        })
        next_eligible_t = exit_idx + 1

    returns = [x["net_return_pct"] / 100 for x in entries]
    if returns:
        equity = np.cumprod(1 + np.asarray(returns))
        peak = np.maximum.accumulate(np.r_[1, equity])
        max_drawdown = float(np.min(np.r_[1, equity] / peak - 1)) * 100
        cum = float((equity[-1] - 1) * 100)
        win_pct = 100 * sum(x > 0 for x in returns) / len(returns)
    else:
        max_drawdown = cum = win_pct = None
    return {
        "label": "RETROSPECTIVE EXAMPLES ONLY - current pair selection uses later data",
        "sessions_examined": min(REPLAY_WINDOW, n - 252),
        "events": len(entries),
        "hold_sessions": HOLD_SESSIONS,
        "entry": "next session closing price after close-based signal",
        "exit": "closing price five sessions after entry",
        "entry_z": 2,
        "cost_assumption_bps_per_leg_per_side": 10,
        "borrow_apr_assumption_pct": BORROW_APR * 100,
        "equal_dollar_legs": True,
        "cumulative_net_return_pct": finite(cum),
        "max_drawdown_pct": finite(max_drawdown),
        "win_rate_pct": finite(win_pct),
        "examples": entries[-8:],
        "limitations": "Selected on current data, non-overlapping examples only, simplified closes and costs; excludes real slippage, spreads, dividends, borrow recall, margin and market impact. Not an independent forward backtest.",
    }


def review(pair: dict, prices: pd.DataFrame, as_of: str, day: str) -> dict:
    a, b = pair["a"], pair["b"]
    frame = prices[[a, b]].loc[:as_of].dropna()
    if len(frame) < 340 or str(frame.index[-1].date()) != as_of:
        raise ValueError("Insufficient current aligned history for deep review")
    log = np.log(frame)
    train = log.iloc[-253:-1]
    x, y = train[b].to_numpy(), train[a].to_numpy()
    beta, intercept = np.polyfit(x, y, 1)
    residual = y - intercept - beta * x
    # The same full-window test is already in the broad scan. These two
    # half-window tests are only sensitivity diagnostics, not confirmation.
    first_p = float(coint(y[:126], x[:126], trend="c", autolag="aic")[1])
    second_p = float(coint(y[-126:], x[-126:], trend="c", autolag="aic")[1])
    phi = float(np.dot(residual[:-1], residual[1:]) / max(np.dot(residual[:-1], residual[:-1]), 1e-12))
    half_life = float(math.log(.5) / math.log(phi)) if 0 < phi < 1 else None
    if half_life is not None and half_life > 504:
        half_life = None
    # Prior-formation Z trace, so chart values are date-correct.
    points = []
    for i in range(max(252, len(frame) - 32), len(frame)):
        try:
            z, _, _ = z_at(log, i)
            points.append({"date": str(frame.index[i].date()), "z": finite(z)})
        except (ValueError, np.linalg.LinAlgError):
            pass
    stats = replay(frame)
    status = pair["status"]
    if status == "research_candidate":
        verdict = "Passes today's strict research gates, but profitability remains unverified."
    elif status == "preliminary_watch":
        verdict = "Interesting unadjusted relationship; fails at least one stronger safety gate. Not a qualified trade."
    else:
        verdict = "Does not pass the research screening gates. No trade is justified from this model."
    if pair["z"] >= 2:
        direction = f"{a} has risen relative to {b} in the fitted spread; a mean-reversion hypothesis would short {a} and buy {b}."
    elif pair["z"] <= -2:
        direction = f"{a} has fallen relative to {b} in the fitted spread; a mean-reversion hypothesis would buy {a} and short {b}."
    else:
        direction = "The modeled spread is inside the usual ±2 standard-deviation observation band; no fresh divergence threshold is met."
    return {
        "id": day + ":" + pair["pair"],
        "review_date": day,
        "data_through": as_of,
        "input_provenance": None,  # Filled by update_history with source snapshot.
        "pair": pair["pair"],
        "a": a, "b": b, "industry": pair["industry"],
        "classification": status,
        "verdict": verdict,
        "relative_value_explanation": direction,
        "metrics": {
            "correlation_90d": pair["correlation"],
            "z_score_60d": pair["z"],
            "engle_granger_p": pair["p"],
            "universe_fdr_q": pair["q"],
            "hedge_beta_log_price": pair["beta"],
            "beta_drift_pct": pair["beta_drift_pct"],
            "half_life_sessions_estimate": finite(half_life),
            "half_window_eg_p": [finite(first_p), finite(second_p)],
        },
        "gates": pair.get("gates", {}),
        "z_history": points,
        "retrospective_replay": stats,
        "source": "Yahoo Finance via yfinance auto-adjusted closes; exploratory, unverified execution",
        "risk_note": "This dated review is exploratory, not a recommendation. No independent forward P/L or executable arbitrage has been established.",
    }


def update_history(
    result: dict,
    prices: pd.DataFrame,
    now: datetime,
    history: dict | None = None,
    count: int = REVIEW_COUNT,
) -> dict:
    """Return a new complete ledger, preserving all previous dated records."""
    day = now.astimezone(timezone.utc).date().isoformat()
    previous = history or {"schema_version": 1, "records": []}
    if previous.get("schema_version") != 1 or not isinstance(previous.get("records"), list):
        raise ValueError("Unsupported review history schema")
    old = previous["records"]
    keys = [(r["review_date"], r["pair"]) for r in old]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate history records; refusing to overwrite")
    if any(r["review_date"] > day for r in old):
        raise ValueError("Future review records found; refusing to append")
    reviews = list(old)
    to_add = max(0, count - sum(r["review_date"] == day for r in reviews))
    candidate_list = choose_pairs(result["pairs"], reviews, day, to_add)
    for pair in candidate_list:
        try:
            record = review(pair, prices, result["as_of"], day)
            record["input_provenance"] = dict(result.get("input_provenance") or {}) or None
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            # A broken review should not silently become a successful two-pair
            # day. Fail the whole workflow, preserving previously published data.
            raise
        reviews.append(record)
    if sum(r["review_date"] == day for r in reviews) != count:
        raise RuntimeError("Unable to complete two distinct deep reviews today; declining partial publication")
    # Earlier reviews predate the source-snapshot requirement; mark them as
    # legacy rather than retroactively claiming they were independently audited.
    for item in reviews:
        if not item.get("input_provenance"):
            item["provenance_status"] = "legacy_no_preserved_price_input"
        else:
            item["provenance_status"] = "checkpoint_available_subject_to_audit"
    reviews.sort(key=lambda r: (r["review_date"], r["pair"]))
    return {
        "schema_version": 1,
        "kind": "PAIR_LAB_EXPLORATORY_DATED_REVIEWS",
        "updated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "data_through": result["as_of"],
        "reviews_per_day": count,
        "total_reviews": len(reviews),
        "unique_pairs_reviewed": len({r["pair"] for r in reviews}),
        "review_dates": len({r["review_date"] for r in reviews}),
        "records": reviews,
    }


if __name__ == "__main__":
    raise SystemExit("Run daily_pair_scanner.py to update scan and deep reviews together.")

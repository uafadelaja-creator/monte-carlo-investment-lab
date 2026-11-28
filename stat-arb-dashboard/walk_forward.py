"""Frozen-formation pairs experiment using a dated adjusted-close CSV.

Run: python walk_forward.py prices.csv A B C
The supplied symbols must represent a universe known before the test.
"""
import argparse
from itertools import combinations

import numpy as np
import pandas as pd


def evaluate(prices, formation=252, test=63):
    rows = []
    for start in range(formation, len(prices) - test + 1, test):
        train = np.log(prices.iloc[start - formation:start])
        correlations = train.diff().corr()
        a, b = max(combinations(train.columns, 2), key=lambda pair: correlations.loc[pair[0], pair[1]])
        beta, intercept = np.polyfit(train[b], train[a], 1)
        residual = train[a] - intercept - beta * train[b]
        mean, std = residual.mean(), residual.std()
        if beta <= 0 or std <= 1e-10:
            continue
        window = prices[[a, b]].iloc[start:start + test]
        z = (np.log(window[a]) - intercept - beta * np.log(window[b]) - mean) / std
        targets = []
        position = 0
        for score in z:
            if position and (abs(score) >= 3 or position * score >= -0.5):
                position = 0
            elif not position and 2 <= abs(score) < 3:
                position = -int(np.sign(score))
            targets.append(position)
        # A close-based signal fills at the following close. No overnight
        # return before that fill accrues to the new position.
        filled = pd.Series(targets, index=window.index).shift(1, fill_value=0)
        filled.iloc[-1] = 0
        weights = pd.DataFrame({a: filled / (1 + beta), b: -beta * filled / (1 + beta)})
        price_returns = window.pct_change().fillna(0)
        daily = (weights.shift(1, fill_value=0) * price_returns).sum(axis=1)
        turnover = weights.diff().fillna(weights).abs().sum(axis=1)
        short_exposure = -weights.shift(1, fill_value=0).clip(upper=0).sum(axis=1)
        elapsed_days = window.index.to_series().diff().dt.days.fillna(0)
        for execution_bps, borrow_pct in [(0, 0), (5, 3), (15, 8), (30, 15)]:
            net = daily - turnover * execution_bps / 10_000 - short_exposure * elapsed_days * borrow_pct / 36_500
            rows.append({
                "formation_end": train.index[-1].date(),
                "test_start": window.index[0].date(),
                "test_end": window.index[-1].date(),
                "pair": f"{a}/{b}",
                "entries": int(((filled != 0) & (filled.shift(fill_value=0) == 0)).sum()),
                "execution_bps": execution_bps,
                "annual_borrow_pct": borrow_pct,
                "net_return_pct": 100 * ((1 + net).prod() - 1),
            })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="Date column and adjusted closes for each symbol")
    parser.add_argument("symbols", nargs="+")
    args = parser.parse_args()
    if len(set(args.symbols)) < 2 or len(set(args.symbols)) != len(args.symbols):
        parser.error("Provide at least two distinct symbols.")
    frame = pd.read_csv(args.csv, index_col="Date", parse_dates=["Date"]).sort_index()
    if not set(args.symbols).issubset(frame.columns):
        parser.error("Every requested symbol needs a price column.")
    prices = frame[args.symbols].apply(pd.to_numeric, errors="coerce")
    if prices.index.has_duplicates or prices.index.hasnans or not np.isfinite(prices).all().all() or (prices <= 0).any().any():
        parser.error("Use unique dates and complete positive prices.")
    if len(prices) < 315:
        parser.error("Use at least 315 aligned trading sessions.")
    results = evaluate(prices)
    if results.empty:
        parser.error("No usable formation fits.")
    print(results.to_csv(index=False), end="")


if __name__ == "__main__":
    main()

# Data provenance and reproducibility checklist

This project cannot legitimately publish calculated 2026 performance statistics until live historic price downloads or a genuine adjusted-price CSV have been checked.

1. Confirm prices use **adjusted closing prices**, not unadjusted trade closes.
2. Record vendor and timestamp; save original dataset in a private/source archive and store its SHA-256 checksum.
3. Validate that all ETFs and basket stocks share the same market-trading observations before calculating percentages.
4. Confirm common period begins after all three ETFs existed. A current-date universe backcast may begin earlier than the evidence date, but **must not** be called a point-in-time compliance backtest.
5. Keep the last fully observed calendar month only; do not use partial months in the fitted return distribution.
6. Verify one historical price / adjusted corporate action independently against a fund sponsor source.
7. Record ETF sponsor-document dates and the as-of date of any stock-list evidence. Re-check whether status changed before publishing a specific security claim.
8. Label each optimization result as **in-sample** or **walk-forward**.
9. Use the same historical month draws across compared series for Monte Carlo outperformance frequencies.
10. State exclusions: transaction costs, spreads, market impact, personal taxes, purification, inflation and ex-ante constituent availability.

**Reproducible export:** `python -m scripts.run_research --download` automatically saves the aligned observed prices, checksum, assumptions, analysis dates and output tables in `outputs/`.

### Distinguishing claim types

| Statement | Defensible? | Why |
|---|---|---|
| "AAPL appeared in SPUS's November 24, 2026 holdings" | Yes, if issuer source is preserved | Dated disclosed fact |
| "AAPL was Shariah-approved in 2019 because it appears in 2026 SPUS" | No | Time-travel/eligibility bias |
| "The equal-weighted current-holdings basket retrospectively had a particular return" | Only with verified prices and explicit backcast warning | Descriptive historical exposure illustration |
| "The strategy would have achieved this return for a Shariah investor in 2019" | No | Historical members, purification and costs not established |
| "Bootstrap reports a 70% true probability of outperforming SPY" | No | Conditional resampling frequency ≠ calibrated probability |

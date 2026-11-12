# PAIR//LAB — Statistical Arbitrage Observatory

A futuristic, responsive research dashboard integrated into the [Monte Carlo Investment Lab](../README.md).

## Open the dashboard

- [Static dashboard](index.html)
- [Provisional research snapshot](data/screen.json)
- From the repository's main home page, select **Stat-Arb Observatory**.

To run locally:

```bash
python -m http.server 8000
# open http://localhost:8000/stat-arb-dashboard/
```

Directly opening the HTML using \`file://\` is not supported because the site fetches its JSON file. It requires HTTP hosting. The repository has GitHub Pages enabled and a previously confirmed deployment. Use [the published dashboard](https://uafadelaja-creator.github.io/monte-carlo-investment-lab/stat-arb-dashboard/).


## Interactive trade-plan research workspace

The website includes an **educational conditional plan builder**, not a brokerage execution engine. You can explore any of the 18 pairs and five preselected research examples (AVAV/KTOS, KTOS/ONDS, SOFI/NU, AMD/MRVL, NVDA/TSM). None currently meets the full snapshot screening gates.

The plan editor lets you adjust:

- Absolute Z entry watch threshold (1.5–2.5), mean-reversion exit band (0–1), invalidation band (2.5–4), and maximum hold (5, 10, 20 sessions).
- Illustrative **gross** notional ($100–$1,000), per-leg transaction cost (0–50 basis points per fill), and hypothetical annual short borrow charge (0–15%).
- An independently chosen **past** threshold crossing from the 520-session historical-price chart universe. Its subsequent gross and cost-adjusted P/L are shown on a two-line replay chart. If the dataset ends first, the position is labeled **unresolved**.

**Replay assumptions and limits:** Every spread Z uses a 252-session trailing log-price OLS fit excluding that day's observation and 60 recent formation residuals. A cross of ±Z is an *educational price-only event*—historical cointegration and structural-break gates are **not** rechecked at each event. A signal observed at close T receives an **assumed next-session closing price T+1** (not an actionable market-on-close execution or a plausible quote guarantee). Later daily closes trigger exit/invalidation/holding limits, and the exit fills at the following session's close. An unclosed trade is marked through the final historical close.

The example position splits gross dollar notional equally across long and short legs. That simplifies the P/L illustration, but is **not** the stock hedge implied by log-price regression β. Gross return equals long-leg dollar return plus the short-leg dollar return. Estimated costs subtract one transaction fee on both legs at entry, an estimated fee for both legs at exit, and daily short borrow carry at the selected annualized rate. The model **excludes spreads/slippage, dividends, exchange fees, borrow recall, taxes, changing borrow rates, margin requirements and financing costs**. Raw vendor close prices lack independently certified split/dividend adjustments. A Z-score stop does **not** bound dollar losses, and theoretical short losses may exceed capital.

The researcher can export a plain-text record of chosen assumptions and the historical example. No account connections, trade placement, guaranteed entries, profitability forecasts, or automatic alerts are created by the website.

**Validation:** GitHub Actions executes site structure/integrity assertions, independent \`statsmodels\` recomputation, Node syntax checks for chart and plan scripts, and a no-dependency Node UI smoke test. The user-supplied $300 options budget is **not** interpreted as permission to short or as a maximum loss for two-leg stock trading.

## What the dashboard actually proves

The snapshot documents an exploratory **18-pair** subset sourced from the daily \`close\` columns in [yennanliu/finance_data](https://github.com/yennanliu/finance_data), ending **November 11, 2026**. It is not a 50–100-stock universe. Each pair was estimated from a 252-session formation window ending on the **previous completed session**; Z is computed for the next session. It shows independently recomputed statsmodels Engle–Granger p-values (trend=c, autolag=AIC), 90-session daily-return correlation, and a 60-session residual Z-score, plus Benjamini–Hochberg false-discovery-rate q-values across the 18 tests.

### Results

- **18** candidate hypotheses screened; **2** preliminary unadjusted p-values < 0.05.
- **0** candidates survived q < 0.05 under a 5% FDR screen.
- **0** candidates met the scanner's nominal p < 0.05 AND correlation > 0.75 AND |Z| ≥ 2 threshold.
- **No validated trading edge** and **no actionable signal**.

The two raw p < 0.05 observations are **KTOS/ONDS** (p ≈ .0289, r ≈ .699, Z ≈ +0.39, q ≈ .397) and **SOFI/NU** (p ≈ .0441, r ≈ .353, Z ≈ +0.98, q ≈ .397). Both fail correlation, Z-entry and FDR gates. **AVAV/KTOS** is not cointegrated at the 5% threshold under the independently recomputed test (p ≈ .1272). Large deviations in NVDA/AMD, NVDA/AVGO and NVDA/TSM are **not** validated mean reversion signals.

## Audit findings and limitations

1. **Source data:** The CSV source supplies daily close, volume, and optional dividend and split fields. The entire corporate-action-adjustment history and total-return consistency have *not* been independently verified. Split events and changing companies may distort the regressions. The snapshot must not be treated as executable adjusted-price data.
2. **Statistical test:** On November 12, 2026, a clean GitHub Actions runner recomputed 18 hypotheses using \\`statsmodels.tsa.stattools.coint(..., trend="c", autolag="aic")\\`. The audit found **11 numerical discrepancies** with earlier hand-calculated values; the published p-values and BH q-values were updated accordingly. [Audit run](https://github.com/uafadelaja-creator/monte-carlo-investment-lab/actions/runs/43284043346).
3. **Reproducibility:** The independently recomputed audit produced source SHA-256 hashes for its 18-pair constituent tickers and a versioned GitHub Actions artifact. The dashboard exposes corrected statistical output; price-adjustment provenance remains unverified.
4. **Hypothesis testing:** Because multiple pairs were screened, raw p < 0.05 is insufficient. BH q controls expected false discovery rate under its assumptions; this sample's minimum q is > 0.05. The candidate universe is discretionary and was not pre-registered for independent significance claims.
5. **No profitability validation:** No new candidate has undergone fully out-of-sample, next-day-executable, net-of-cost walk-forward validation, realistic borrow or a structural-break/earnings audit. Hedge ratios are log-price regression slopes, not executable share counts.
6. **No live monitoring inside the site:** The dashboard is a dated static research snapshot, separate from the existing automated alert system. It does not connect to Robinhood or place trades.

## Deployment

The folder \`stat-arb-dashboard/\` is a standalone static site with no build tools or CDN dependency. If the existing GitHub Pages workflow publishes the repository root, the path will be:

`https://uafadelaja-creator.github.io/monte-carlo-investment-lab/stat-arb-dashboard/`

GitHub Actions has successfully deployed the repository root to its GitHub Pages URL. The dashboard is served from the subdirectory above; publishing is independent of the statistical-alert automation.

## Next validations before live research signals

Obtain and hash a consistent **split-and-dividend-adjusted** daily dataset; independently rerun every pair using standard Engle–Granger; check sensitivity to formation and normalization choices; use genuinely predeclared hypotheses for confirmatory significance; test one-session-delayed fills with costs and borrow; review company actions, earnings and beta stability; then extend coverage to 50–100 stocks without silently expanding the alert universe.
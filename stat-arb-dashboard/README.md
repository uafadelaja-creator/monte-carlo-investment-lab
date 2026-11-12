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

Directly opening the HTML using \`file://\` is not supported because the site fetches its JSON file. It requires HTTP hosting. GitHub Pages must be enabled independently for a public hosted URL; committing files does not establish a deployment.

## What the dashboard actually proves

The snapshot documents an exploratory **18-pair** subset sourced from the daily \`close\` columns in [yennanliu/finance_data](https://github.com/yennanliu/finance_data), ending **November 11, 2026**. It is not a 50–100-stock universe. Each pair was estimated from a 252-session formation window ending on the **previous completed session**; Z is computed for the next session. It shows approximate Engle–Granger p-values, 90-session daily-return correlation, and a 60-session residual Z-score, plus Benjamini–Hochberg false-discovery-rate q-values across the 18 tests.

### Results

- **18** candidate hypotheses screened; **2** preliminary unadjusted p-values < 0.05.
- **0** candidates survived q < 0.05 under a 5% FDR screen.
- **0** candidates met the scanner's nominal p < 0.05 AND correlation > 0.75 AND |Z| ≥ 2 threshold.
- **No validated trading edge** and **no actionable signal**.

The closest research candidate was **AVAV/KTOS** (p ≈ .0289, 90-day r ≈ .814, Z ≈ +1.15, q ≈ .2604), which fails the Z-entry gate and FDR gate. **AVAV/ONDS** (p ≈ .0069, r ≈ .690, Z ≈ +1.22, q ≈ .1234) fails the correlation, Z and FDR gates. Large deviations in NVDA/AMD, NVDA/AVGO and NVDA/TSM are **not** validated mean reversion signals.

## Audit findings and limitations

1. **Source data:** The CSV source supplies daily close, volume, and optional dividend and split fields. The entire corporate-action-adjustment history and total-return consistency have *not* been independently verified. Split events and changing companies may distort the regressions. The snapshot must not be treated as executable adjusted-price data.
2. **Statistical test:** Preliminary estimates used a hand-implemented residual ADF with lag choices 0–4 by AIC and MacKinnon approximate cointegration p-values. Full statistical equivalence to \`statsmodels.tsa.stattools.coint(..., trend="c", autolag="aic")\` has not been established; this could change rankings and q-values.
3. **Reproducibility:** The 18 numerical rows are frozen with a source link, date, protocol explanation and explicit provisional flag. The upcoming standard-library audit should reconcile source hashes, date alignment and unit tests.
4. **Hypothesis testing:** Because multiple pairs were screened, raw p < 0.05 is insufficient. BH q controls expected false discovery rate under its assumptions; this sample's minimum q is > 0.05. The candidate universe is discretionary and was not pre-registered for independent significance claims.
5. **No profitability validation:** No new candidate has undergone fully out-of-sample, next-day-executable, net-of-cost walk-forward validation, realistic borrow or a structural-break/earnings audit. Hedge ratios are log-price regression slopes, not executable share counts.
6. **No live monitoring inside the site:** The dashboard is a dated static research snapshot, separate from the existing automated alert system. It does not connect to Robinhood or place trades.

## Deployment

The folder \`stat-arb-dashboard/\` is a standalone static site with no build tools or CDN dependency. If the existing GitHub Pages workflow publishes the repository root, the path will be:

`https://uafadelaja-creator.github.io/monte-carlo-investment-lab/stat-arb-dashboard/`

This is a **potential URL**, not a claim of confirmed deployment. If GitHub Pages is not configured or the workflow publishes another directory, the public link will not work until that is changed.

## Next validations before live research signals

Obtain and hash a consistent **split-and-dividend-adjusted** daily dataset; independently rerun every pair using standard Engle–Granger; check sensitivity to formation and normalization choices; use genuinely predeclared hypotheses for confirmatory significance; test one-session-delayed fills with costs and borrow; review company actions, earnings and beta stability; then extend coverage to 50–100 stocks without silently expanding the alert universe.
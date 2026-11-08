## 2026-11-07 · Unified historical dashboard

- Replaced the main dashboard's embedded illustrative data with the uploaded
  historical dataset. Default view shows observed normalized performance.
- Added historical bootstrap percentile curves and all contribution controls
  using joint sampled returns, with a clearly labeled hypothetical shock option.
- Unified both pages with shared CSS, navigation, typography, and ETF definitions.
- Added historical chart inspection, accessible tabs, comparison CSV downloads,
  and a research page covering provenance, correlation, and block sensitivity.
- Added regression coverage for contribution variants and unitized risk accounting.

## 2026-11-07 · Historical ETF refresh (engine v0.4.1)

- Ingested the user-provided daily adjusted-price CSV locally, with input hash,
  date range, row count, and dependency versions recorded in aggregate metadata.
- Recomputed 50,000-path monthly bootstrap results through October 2026; excluded
  partial November. Preserved the separate illustrative and pairs-research models.
- Added strict CSV validation and missing-month checks, and corrected the historical
  drawdown chart to include initial capital in its running peak.
- Generated the historical page from aggregate JSON, added ETF explanations, and
  linked it prominently from the main dashboard. Vendor prices remain gitignored.

# Changelog

## v0.7 · 1 November 2026

- Extended the frozen pair holdout through 30 October; five new sessions produced
  no entries and did not change the no-edge conclusion.
- Added `forward_signal_audit.py`, a prospective append-only ledger with chained
  SHA-256 integrity, idempotent observations, and next-session resolution logic.
- Added raw open/high/low/volume audit downloads while keeping all vendor tables
  excluded from Git.
- Explicitly labels daily range as a non-spread proxy and borrow availability as
  unobserved rather than inventing execution realism.
- Extended official Kenneth French factors through September 2026 and expanded
  the validation suite from eleven to sixteen tests.

## v0.6 · 25 October 2026

- Extended the frozen pair holdout through 23 October without changing hypotheses
  or trading parameters; five new sessions produced no entries.
- Added an idempotent sequential evidence ledger and protocol SHA-256 fingerprint.
- Added a prior-prefix adjusted-price hash check to disclose upstream data revisions.
- Expanded aggregate reports with 12- and 36-month profit/loss probabilities.
- Added bounded Kenneth French download retries and dynamic exclusion of the
  current in-progress market session.
- Pinned CI's direct dependencies and expanded the test suite from seven to eleven tests.

## v0.5 · 18 October 2026

- Integrated the statistical-arbitrage prototype as a separate empirical layer.
- Predeclared V/MA, KO/PEP, and XOM/CVX with SPY and sector benchmarks.
- Added one-session delayed fills, explicit turnover and borrow assumptions,
  six-horizon 50,000-path moving-block resampling, and cost/window sensitivity.
- Added synthetic leakage, execution-delay, cost, and reproducibility tests.
- Added a GitHub Actions validation workflow that does not commit raw vendor data.
- Preserved the original illustrative engine and v0.4 ETF bootstrap unchanged.

## v0.4 · 11 October 2026

- Completed the empirical ARKK/QUAL/SPY historical extension.
- Added 140 common monthly returns and a cached, hashed adjusted-price input.
- Added 50,000-path joint moving-block bootstrap across six horizons.
- Added empirical Sharpe, volatility, drawdown, skewness, kurtosis, VaR, CVaR, and correlations.
- Added block-length sensitivity, shock analysis, two GitHub-rendered charts, dashboard JSON, tests, and a standalone historical-results page.
- Preserved the v0.3 parametric model as a separate model-risk comparison.

## v0.3 · 4 October 2026

- Added paired return-reversion, volatility/correlation stress, and contribution scenarios.
- Corrected CAGR and drawdown to use unitized return paths.
- Added deterministic rerun validation.

## v0.2 · 27 September 2026

- Added correlated fat-tailed Student-t returns, six horizons, benchmark comparison, and complete risk metrics.

## v0.1 · 26 September 2026

- Created the initial assumption-based Monte Carlo demonstration.


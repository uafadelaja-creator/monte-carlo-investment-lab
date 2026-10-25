# Changelog

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


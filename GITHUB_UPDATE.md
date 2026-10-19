# GitHub update for v0.5

Repository: https://github.com/uafadelaja-creator/monte-carlo-investment-lab  
Public dashboard: https://uafadelaja-creator.github.io/monte-carlo-investment-lab/

## Publication boundary

Keep the existing `index.html` and original `simulate.py`. They remain the
assumption-driven demonstration. The empirical ETF page and stat-arb research are
separate modules and must not be described as calibrated forecasts or proven alpha.

Do **not** commit Yahoo/yfinance price tables, raw closes, pair daily return tables,
or local manifests containing third-party source data. Publish code, hashes,
aggregate statistics, and charts only.

## Feature branch contents

- `historical_analysis.py`, `historical_results.html`, and aggregate
  `results/historical_*` files from v0.4.
- `download_prices.py`, `download_french_factors.py`, `pairs_research.py`,
  `run_stat_arb_research.py`, and `STAT_ARB_GUIDE.md`.
- `tests/test_historical_analysis.py` and `tests/test_pairs_research.py`.
- `.github/workflows/empirical-research.yml`.
- Aggregate `results/stat_arb_current` reports, bootstrap tables, sensitivity
  table, and charts from the 18 October 2026 fixed holdout.
- Updated README, FINDINGS, CHANGELOG, requirements, and dated run reports.

## Validation checklist

1. Seven unit tests pass.
2. The cached v0.4 historical summary and risk files reproduce byte-for-byte.
3. The workflow downloads its own exploratory data and never commits raw prices.
4. Every pair report states the one-session delay, cost/borrow assumptions, and
   adjusted-close limitation.
5. The fixed pair list is not ranked or converted into a live signal.
6. GitHub Pages keeps the original dashboard and serves `historical_results.html`.
7. The pull request states that the first stat-arb holdout did not demonstrate edge.

Suggested pull-request title:

`Add empirical ETF and predeclared stat-arb research modules`


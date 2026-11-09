# Predeclared statistical-arbitrage research

Data through: **2026-11-06**
Source: **Yahoo Finance through yfinance (unofficial; exploratory research only)**
Test period starts: **2023-01-03**
Paths per pair and horizon: **50,000**
Seed: **20261018** (horizon-specific deterministic offsets)

These are fixed hypothesis tests, not ranked trade recommendations.
Adjusted closes are total-return approximations rather than executable prices.

| Pair | Net cumulative | CAGR | Volatility | Max drawdown | Entries | 12m P(loss), MC 95% CI | 36m P(loss), MC 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| V/MA | -0.00% | -0.00% | 0.46% | -0.56% | 2 | 25.35% [24.97%, 25.73%] | 45.27% [44.83%, 45.71%] |
| KO/PEP | 0.00% | 0.00% | 0.00% | 0.00% | 0 | 0.00% [0.00%, 0.01%] | 0.00% [0.00%, 0.01%] |
| XOM/CVX | -2.29% | -0.60% | 1.15% | -2.30% | 1 | 41.36% [40.93%, 41.80%] | 79.81% [79.45%, 80.16%] |

No pair is selected as a winner after observing the holdout. Statistical
significance, if any, would not by itself establish implementable alpha.
The reported Monte Carlo intervals isolate finite-path sampling error;
they do not include model, parameter, historical-sample, or regime uncertainty.

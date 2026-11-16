# Predeclared statistical-arbitrage research

Data through: **2026-11-13**
Source: **Yahoo Finance through yfinance (unofficial; exploratory research only)**
Test period starts: **2023-01-03**
Paths per pair and horizon: **50,000**
Seed: **20261018** (horizon-specific deterministic offsets)

These are fixed hypothesis tests, not ranked trade recommendations.
Adjusted closes are total-return approximations rather than executable prices.

| Pair | Net cumulative | CAGR | Volatility | Max drawdown | Entries | 12m P(loss), MC 95% CI | 36m P(loss), MC 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| V/MA | -0.00% | -0.00% | 0.46% | -0.56% | 2 | 25.03% [24.65%, 25.41%] | 45.19% [44.76%, 45.63%] |
| KO/PEP | 0.00% | 0.00% | 0.00% | 0.00% | 0 | 0.00% [0.00%, 0.01%] | 0.00% [0.00%, 0.01%] |
| XOM/CVX | -2.29% | -0.60% | 1.15% | -2.30% | 1 | 40.99% [40.56%, 41.42%] | 79.52% [79.17%, 79.88%] |

No pair is selected as a winner after observing the holdout. Statistical
significance, if any, would not by itself establish implementable alpha.
The reported Monte Carlo intervals isolate finite-path sampling error;
they do not include model, parameter, historical-sample, or regime uncertainty.

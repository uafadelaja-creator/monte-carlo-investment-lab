# Sequential evidence monitor

Current data through: **2026-10-30**
Price source: **Yahoo Finance through yfinance (unofficial; exploratory research only)**
Protocol SHA-256: `694c2d7be62c6f2d0093e91025f2408386ab910924d3434bbdc2087977529a60`

The pair list and protocol remain frozen. This page reports evidence drift; it does not
select a winning pair, revise parameters, or issue a trade alert.

| Pair | New sessions | New entries | Net return | Change | 12m P(loss) | 36m P(loss) |
|---|---:|---:|---:|---:|---:|---:|
| KO/PEP | 5 | 0 | 0.000% | +0.000% | 0.0% | 0.0% |
| V/MA | 5 | 0 | -0.005% | +0.000% | 25.5% | 45.2% |
| XOM/CVX | 5 | 0 | -2.287% | +0.000% | 41.5% | 79.9% |

## Integrity checks

- Prior-prefix vendor revision check: **hash changed**. Aggregate result drift must be interpreted as a combination of new sessions and upstream adjusted-price revisions.
- Frozen pairs: KO/PEP, V/MA, XOM/CVX.
- Model input SHA-256: `4b1e3b76bdb945c7f71a583910940f94b8e3e35f086da1d85a2581f6201d775d`.
- Zero trades or a zero simulated loss rate denotes inactivity, not evidence of success.
- Repeated weekly checks are descriptive monitoring, not independent hypothesis tests.

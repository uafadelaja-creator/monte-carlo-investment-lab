# Sequential evidence monitor

Current data through: **2026-11-06**
Price source: **Yahoo Finance through yfinance (unofficial; exploratory research only)**
Protocol SHA-256: `694c2d7be62c6f2d0093e91025f2408386ab910924d3434bbdc2087977529a60`

The pair list and protocol remain frozen. This page reports evidence drift; it does not
select a winning pair, revise parameters, or issue a trade alert.

| Pair | New sessions | New entries | Net return | Change | 12m P(loss) | 36m P(loss) |
|---|---:|---:|---:|---:|---:|---:|
| KO/PEP | 5 | 0 | 0.000% | +0.000% | 0.0% | 0.0% |
| V/MA | 5 | 0 | -0.005% | -0.000% | 25.4% | 45.3% |
| XOM/CVX | 5 | 0 | -2.287% | -0.000% | 41.4% | 79.8% |

## Integrity checks

- Prior-prefix vendor revision check: **hash changed**. Aggregate result drift must be interpreted as a combination of new sessions and upstream adjusted-price revisions.
- Frozen pairs: KO/PEP, V/MA, XOM/CVX.
- Model input SHA-256: `4ccd6923df8d4cad0dea82d87e7180e0ce98f432a0bc000aee66921414055ec9`.
- Zero trades or a zero simulated loss rate denotes inactivity, not evidence of success.
- Repeated weekly checks are descriptive monitoring, not independent hypothesis tests.

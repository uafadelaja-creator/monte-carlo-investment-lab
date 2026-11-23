# Sequential evidence monitor

Current data through: **2026-11-20**
Price source: **Yahoo Finance through yfinance (unofficial; exploratory research only)**
Protocol SHA-256: `694c2d7be62c6f2d0093e91025f2408386ab910924d3434bbdc2087977529a60`

The pair list and protocol remain frozen. This page reports evidence drift; it does not
select a winning pair, revise parameters, or issue a trade alert.

| Pair | New sessions | New entries | Net return | Change | 12m P(loss) | 36m P(loss) |
|---|---:|---:|---:|---:|---:|---:|
| KO/PEP | 5 | 0 | 0.000% | +0.000% | 0.0% | 0.0% |
| V/MA | 5 | 0 | -0.005% | -0.000% | 25.1% | 45.0% |
| XOM/CVX | 5 | 0 | -2.287% | -0.000% | 41.0% | 79.4% |

## Integrity checks

- Prior-prefix vendor revision check: **hash changed**. Aggregate result drift must be interpreted as a combination of new sessions and upstream adjusted-price revisions.
- Frozen pairs: KO/PEP, V/MA, XOM/CVX.
- Model input SHA-256: `afdac5901ce349c56f4ba65bcb8b827bddcea294c10adbea871f9282366727a3`.
- Zero trades or a zero simulated loss rate denotes inactivity, not evidence of success.
- Repeated weekly checks are descriptive monitoring, not independent hypothesis tests.

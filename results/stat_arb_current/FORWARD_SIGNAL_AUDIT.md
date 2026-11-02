# Forward paper-signal audit

Protocol SHA-256: `694c2d7be62c6f2d0093e91025f2408386ab910924d3434bbdc2087977529a60`
Frozen pairs: KO/PEP, V/MA, XOM/CVX

This append-only audit begins at its initialization date; it does not backfill
historical signals as if they had been observed in real time.

| Pair | Signal date | Event | State | Z-score | Coint. p | Execution audit |
|---|---|---|---|---:|---:|---|
| KO/PEP | 2026-10-30 | INITIAL_FLAT | flat | n/a | n/a | not_applicable |
| V/MA | 2026-10-30 | INITIAL_FLAT | flat | 1.08 | 0.814 | not_applicable |
| XOM/CVX | 2026-10-30 | INITIAL_FLAT | flat | -0.60 | 0.071 | not_applicable |

Resolved prospective entries: **0**.

## Interpretation limits

- Adjusted closes remain model inputs, not trade-executable quotes.
- Raw next-session closes are audit references; they do not prove fill quality.
- The daily range proxy is not a bid/ask spread estimate.
- Borrow inventory and actual borrow rates remain unobserved; the model uses a 3% APR scenario.
- Weekly observations can miss intraweek signal changes and are not trade alerts.
- Hash chain status: **valid**.

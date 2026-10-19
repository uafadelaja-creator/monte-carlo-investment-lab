# Latest run: stat-arb integration, 18 October 2026

The new statistical-arbitrage module is a research harness, and its first fixed
holdout run did not show an edge.
It predeclares V/MA, KO/PEP, and XOM/CVX, uses a 2023-01-03 holdout, delays modeled
fills by one session, charges turnover and borrow scenarios, and compares with SPY
plus sector benchmarks. Local synthetic tests validate timing, cost deductions,
leakage isolation, and deterministic block resampling.

On adjusted daily data through 2026-10-16, V/MA had two entries and a −0.005%
net holdout return, KO/PEP never opened a position, and XOM/CVX had one entry and
a −2.29% net return. Strict filters produced only 0%–2.1% exposure, so the study
is underpowered as well as unprofitable. The 36-month block-bootstrap loss
probabilities were 45.7% V/MA and 80.1% XOM/CVX; KO/PEP remained flat. Cost and
formation-window sensitivity changed outcomes materially. These results reject
any current claim of robust statistical-arbitrage alpha.

The completed empirical result remains the ETF block bootstrap below.

## Empirical ETF block bootstrap, 11 October 2026

The current v0.4 results are in `RUN_2026-10-11.md` and the `results/historical_*` files. The project now resamples 140 common monthly ARKK, QUAL, and SPY returns with 50,000 joint moving-block-bootstrap paths across all six required horizons. The exact adjusted-price input is cached and hashed for reproducibility.

At 36 months and $16,100 contributed, median ending values are $20,264 ARKK, $19,715 QUAL, and $19,926 SPY. Loss probabilities are 26.8%, 7.6%, and 6.5%. ARKK beat its paired SPY path 53.2% of the time, which is too close to chance to establish an edge, while its median simulated maximum drawdown was 37.7% versus 14.4% QUAL and 13.4% SPY.

Observed history reinforces the risk difference: ARKK's annualized volatility was 36.4% and month-end maximum drawdown was 77.1%, versus approximately 15% volatility and 24%–28% maximum drawdowns for QUAL and SPY. QUAL and SPY were 0.98 correlated in the sample, limiting diversification.

## Archived 4 October 2026 run

The v0.3 results are preserved in `RUN_2026-10-04.md` and `results/baseline_summary.csv`. That run added paired return-reversion, volatility/correlation stress, and contribution-schedule scenarios. It also corrected CAGR and drawdown to use deposit-free unitized return paths, preventing deposits from artificially softening reported market risk.

At 36 months and $16,100 contributed, median ending values are $20,394 ARKK, $19,953 QUAL, and $20,155 SPY. ARKK's median maximum drawdown is 48.6% versus 9.6% QUAL and 9.9% SPY; its 95th-percentile drawdown is 77.9%. The results remain conditional on historical anchors and do not establish predictive certainty or an investment edge.

## Archived 27 September 2026 run

The v0.2 narrative is preserved in `RUN_2026-09-27.md`. The section below is retained as the original v0.1 baseline for auditability.

This is a demonstration using hypothetical annual return, volatility, and correlation assumptions. **None of these probabilities are estimates of actual future performance.** See README and `results/assumptions.json`.

50,000 paired paths, fixed seed 20260926; $500 initially and $100 weekly cash-flow equivalent invested at each month end. Ten-year cumulative contributions: **$52,500**.

| Arm | Assumed mean / volatility | 10y mean | 10y median | 5th–95th percentile | Chance below deposits | Chance above index on matched path |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Speculative technology | 14% / 50% | $108,149 | $60,851 | $16,543–$338,085 | 43.6% | 40.7% |
| Established companies | 10% / 25% | $87,442 | $75,649 | $35,512–$178,270 | 22.2% | 54.0% |
| Diversified index | 8% / 18% | $78,913 | $73,102 | $42,217–$134,839 | 16.6% | — |

The speculative arm's higher **mean** and lower **median** reflect the asymmetry the project will study. Its simulated median maximum drawdown on a deposit-free return index is 80.5% versus 46.5% for established companies and 34.0% for the index. This calculation uses a lognormal model; actual speculative stocks can also delist or fail outright.

Assumption sensitivity is decisive: at 14% expected return and 40% volatility, speculative median wealth is $73,773, slightly above the index's $73,102. At 14% and 60% volatility it is $48,980. At 20% and 50% volatility it is $79,542. These results are conditional arithmetic, **not evidence** that any arm's assumed expected return is attainable.

Next research milestone: freeze eligible company rules and assemble a dated, survivorship-aware total-return dataset before drawing any empirical conclusion. The historical study will use SEC filing dates for point-in-time classifications and will test how conclusions change with costs, sample period, and bootstrap design.

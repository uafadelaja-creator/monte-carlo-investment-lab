# First run: illustrative results, 26 September 2026

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

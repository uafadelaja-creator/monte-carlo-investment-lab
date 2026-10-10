# Speculative technology versus proven investing: Monte Carlo lab

**Research question:** Across 1, 3, 5, and 10 years, does the upside from speculative emerging technologies sufficiently compensate for greater downside and volatility relative to established companies and a diversified index strategy?

**Current status (v0.1):** A fully reproducible **assumption-based demonstration**, not an empirical study and not a forecast. It does not recommend any security or report that one class historically outperformed another. The annual means, volatility, and correlations were chosen to illustrate how the comparison works; they were **not estimated from historical data**. The three arms are stylized portfolio-level return streams, not actual five-stock baskets. Read `results/assumptions.json` before interpreting numbers.

## Run

```bash
python -m pip install -r requirements.txt
python simulate.py --paths 50000 --seed 20260926 --sensitivity
```

Outputs: `results/baseline_summary.csv`, `results/assumptions.json`, `results/wealth_fan.png`, and `results/sensitivity.csv`. The fixed seed reproduces the stochastic results on compatible NumPy versions. Sensitivity varies the speculative assumed annual mean (8%, 14%, 20%) and volatility (40%, 50%, 60%) while holding the other arms fixed.

## Predeclared comparison

| Arm | Intended empirical portfolio | Illustrative annual mean / volatility |
| --- | --- | --- |
| Speculative technology | Systematically selected emerging technology companies | 14% / 50% |
| Established companies | Systematically selected mature, profitable businesses | 10% / 25% |
| Diversified index | Broad US market total-return benchmark | 8% / 18% |

Each arm starts with $500; contributes the cash-flow equivalent of $100 weekly at each month end ($433.33/month); contributions are identical across arms. We simulate 50,000 paired paths with correlated monthly returns. The same market scenario affects all three arms through the stated correlation matrix. Wealth, probability of ending below cumulative deposits, probability of exceeding the matched index path, and maximum drawdown of a deposit-free unitized NAV are reported. The probability of ending below deposits is a **nominal cash loss measure**, not an inflation-adjusted return or an internal rate of return. Fan bands are pointwise wealth percentiles and need not describe one attainable path.

## What the first run can establish

The code demonstrates a fair contribution schedule, paired path comparison, and sensitivity of results to assumed return and risk. A larger expected return can coexist with a poor median or deep drawdowns. **The first run cannot establish whether speculative investing actually has a 14% expected return or beats the index in real life.** The lognormal model cannot capture delisting, bankruptcy, discontinuous crashes, changing correlations, or heavy tails. Its percentile and drawdown probabilities are conditional on its assumptions and likely understate some real-world tail risks. There is no fee, tax, or inflation adjustment.

## Empirical phase: protocol before seeing results

1. **Freeze universe and definitions.** US exchange-listed operating companies, selected using information publicly available at each historical formation date. Specify technology themes and classification thresholds in a dated protocol. Proposed starting classification: speculative if the business operates in a predefined emerging-technology theme and has no positive GAAP operating income in the past three reported fiscal years; established if it has at least five years of public trading history, three consecutive years of positive operating income and operating cash flow, and at least $1 billion of annual revenue. Resolve overlap and missing filings before calculating returns. These are draft criteria and will be frozen before empirical results are viewed.
2. **Use point-in-time fundamentals.** SEC EDGAR company facts and filing timestamps can anchor profitability and revenue classification. Account for disclosure delay. Avoid selecting today's surviving winners and projecting them backward.
3. **Build total-return histories with delisting events.** Obtain a source that includes dividends, splits, delistings, and security identifier history. An ordinary downloaded list of surviving tickers is insufficient. French's public research portfolios can serve as a broad market and industry cross-check, but cannot by themselves identify an emerging technology firm cohort.
4. **Hold out later periods.** Set formation frequency, equal/value weighting, reconstitution, transaction costs, and date boundaries in advance. Use rolling out-of-sample evaluation. Block-bootstrap historical **joint** monthly returns for the empirical simulation, preserving cross-arm co-movement and some clustered volatility. Report sensitivity to block length, start date, classifications, and costs. Avoid presenting in-sample fits as predictive probabilities.
5. **Compare matched paths and report uncertainty.** Use matched contributions and dates. Include median and tails, conditional loss and drawdowns, paired index-beating probability, and robustness checks. Interpret differences with confidence intervals or bootstrap uncertainty, not a single ranking.

## Sources and cautions

- [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html): US market, factor, and research portfolio return series; revisions and construction details matter.
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces): company facts and filings for later point-in-time classifications.
- [SEC diversification guide](https://www.investor.gov/additional-resources/general-resources/publications-research/info-sheets/beginners-guide-asset): a handful of individual stocks does not offer the same diversification as a broad fund.

The assumptions are scenario inputs, not historical facts. Do not use the demonstration probabilities to place trades.

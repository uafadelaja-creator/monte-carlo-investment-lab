# Technical research methodology

## 1. Research question

Do rules-based Shariah-screened US equity ETF portfolios exhibit materially different realized returns and risk measures from a conventional US equity benchmark, and how sensitive are historical findings to portfolio composition and the method used to simulate possible future outcomes?

**Hypothesis, not an a priori finding:** Shariah screening may change industry/sector weights and capital-structure exposures; return differences may be explained by those exposures and the observed market environment rather than the screening label itself.

## 2. Fund universe

- **SPY:** conventional S&P 500 tracking ETF, *not* Shariah-compliant, used only as a conventional benchmark.
- **SPUS:** SP Funds S&P 500 Sharia Industry Exclusions ETF, which follows the S&P 500 Shariah Industry Exclusions index approach.
- **HLAL:** Wahed FTSE USA Shariah ETF, which tracks a FTSE USA Shariah index approach.
- **Custom basket:** a subset of explicitly dated SPUS fund holdings, *not* a stock-level Shariah certification. The bundled file identifies 20 names and their November 24, 2026 issuer-reported weights. Broad sector labels are editorial grouping metadata.

The two Shariah indices use related but not identical business and financial screens; changing constituent sets, financial ratios and rebalancing rules mean Shariah standards cannot be freely substituted. For example, FTSE's SEC-disclosed ratio criteria include debt, cash/interest-bearing assets, cash/receivables and non-compliant income thresholds relative to specified denominators. The S&P Shariah Index family has its own methodology. Use primary documents, not simplified generalized rules, to interpret a security's status.

## 3. Returns, common calendar and metrics

The data pipeline requests adjusted close prices. Such vendor series are proxies for traded ETF/stock total returns with distributions reinvested; they are not fund NAV. Assets are aligned to the **intersection of observed trading dates**. The unfinished final calendar month is removed to avoid labelling month-to-date observations as complete monthly returns. The same completed month-end observations underpin ETF and basket comparisons.

For month-end prices \(P_t\), simple return is \(r_t=P_t/P_{t-1}-1\). A monthly rebalanced basket of weights \(w_i\) has return \(r_{p,t}=\sum_i w_i r_{i,t}\), assuming no trading costs. Compound growth is \(\prod_t(1+r_t)\). Annualized geometric return uses \((\prod_t(1+r_t))^{12/T}-1\) with T observed months. Annualized volatility is monthly standard deviation times \(\sqrt{12}\). Sharpe and Sortino use the explicitly entered annual risk-free assumption converted to a monthly equivalent. Drawdown uses the maximum-to-date *month-end* portfolio index. This understates intramonth peak-to-trough losses.

Tracking error is the annualized standard deviation of month-by-month return differences versus SPY. Beta uses monthly covariance with SPY divided by SPY monthly variance; it is not a causal effect estimate. Correlation and rolling-return windows offer descriptive robustness tests only.

## 4. Portfolio optimization and evaluation

Two starting allocations are supported: equal-weight and the issuer's reported *top-basket proportional* weight, which normalizes the selected 20 positions' original ETF weights to a fully invested 20-name portfolio. This is **not identical to owning the whole ETF**.

For optimization, the program uses long-only constrained SLSQP with all weights summing to 1, each weight capped by the user, and estimated monthly covariance shrunk toward its diagonal to reduce ill-conditioning. The maximum-Sharpe objective shrinks each asset's sample return expectation halfway toward the cross-sectional average. Despite these controls, the optimization is **in-sample** and should not be cited as a live track record.

The walk-forward routine trains on the immediately prior 24/36/48/60 monthly returns, fixes weights for the next six months, and repeats. This prevents **future return information** entering previous allocation fits. However, the full stock universe was itself selected by a **2026 holdings snapshot**, so the entire backtest retains stock-selection look-ahead and survivorship bias. It does **not** establish a truly historical halal portfolio.

To run a defensible historically implementable test, reconstruct constituents using **point-in-time screening** (including delisted securities) at *each rebalance date*, and apply period-specific index eligibility, trading constraints, purification, fees, and turnover.

## 5. Point-in-time historical eligibility (optional)

For an independently sourced historical eligibility file, every `as_of` is assumed to be a full cross-section of eligible and excluded stocks with source URLs. The engine does **not** apply the same 2026 stock list to every historical month. For each monthly return period, it chooses the most recent complete screening snapshot whose as-of date precedes the *start* of that return month and whose age at month start is no more than 65 days. It invests in the eligible stocks using equal or evidence-proportional weights. Missing sufficient coverage, stale snapshots, missing stock price histories, or fewer than 24 eligible months cause a failure, not an invented or silently forward-filled strategy.

This improves temporal integrity, but it remains dependent on whether submitted historical screening decisions and delisted-company histories are complete and authentic. The program cannot independently grant a Shariah ruling.

## 6. Sector return attribution

For fixed monthly portfolio weights, each stock's month-t weighted return is grouped by an editable research sector label. Sector contributions sum **exactly** to the monthly custom portfolio return. Their annualized arithmetic means may help diagnose technology concentration. They are **not** a causal sector-neutral counterfactual against SPY and do not add directly to the portfolio's geometric CAGR.

## 7. Monte Carlo model

Let the observed historical matrix R contain monthly returns for all compared portfolios. For each simulated path, sample starting indices for contiguous blocks of length B, then concatenate sampled blocks to the required horizon. Apply **the identical sampled month indices** to SPY, SPUS, HLAL and the custom basket. This preserves contemporaneous dependence (including the relative performance recorded in historical stress periods) and short within-block return patterns.

Path month t applies \(V_{t+1}=V_t(1+r_t)+C\), with C deposited at **month end**. An independent return-only NAV index tracks cumulative losses without deposits; the max drawdown probability is the fraction of simulated return-only NAV paths whose worst drawdown is ≤ −30%. Below-contribution frequency tests final portfolio value against initial capital plus accumulated deposits. Beats-SPY frequency compares paired terminal values in the *same simulated months*.

**Scenario percentiles are not calibrated future return probabilities.** Resampling cannot anticipate unseen crises, structural regime shifts, change in index constituents, changes in compliance, changed interest rates or fund closure. Results also depend on the common available start date, block length, and selected historical period. Do not extrapolate results as return forecasts.

## 8. Risks, limitations and disclosure

- Price vendor may revise distributions or corporate actions; verify using issuer figures.
- Short post-launch ETF history creates a fragile distribution estimate.
- SPUS and HLAL are already screened funds, but individual constituent status may change; bundled 2026 names cannot be projected backward as historically compliant.
- A concentration in large technology companies can dominate differences against SPY, producing misleading causal narratives.
- Cost model excludes spreads, broker commissions, personal tax effects, turnover, market impact, inflation, purification and custody details.
- Historical-adjusted-price returns are not a guarantee of realizable executions.
- Study is descriptive and educational, not a stock recommendation, an investment performance claim, or a Shariah ruling.

## 9. Primary references

1. SP Funds, SPUS official details and dated holdings: https://www.sp-funds.com/SPUS/
2. Wahed, HLAL fund materials and purification: https://www.wahed.com/hlal
3. S&P Dow Jones Indices, S&P 500 Shariah Industry Exclusions Index: https://www.spglobal.com/spdji/en/indices/equity/sp-500-shariah-industry-exclusions-index/
4. SEC, 2026 HLAL fund description and FTSE Shariah USA Index methodology: https://www.sec.gov/Archives/edgar/data/1683471/000089418926026510/R4.htm
5. yfinance, price history parameter definitions: https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html

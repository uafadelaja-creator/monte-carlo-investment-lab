# Explaining your project to investment research recruiters

### 30-second answer

"I built a standalone Python investment research lab that compares two Shariah-screened US equity ETFs, SPUS and HLAL, against SPY. It uses real adjusted market prices, calculates risk-adjusted metrics and tracking error, constructs a basket from dated ETF holdings, and runs paired Monte Carlo return-block simulations. I also implemented long-only constrained optimization and walk-forward validation. The key research discipline was identifying bias: a present-day halal ETF holdings list cannot be treated as a historically compliant portfolio."

### Technical questions and strong answers

**1. Why is SPY in the analysis if it isn't halal?** Conventional benchmark; comparison only, not a compliant allocation suggestion. It helps identify the performance cost or benefit relative to broad-market exposure, without assigning causality.

**2. What exactly is a Monte Carlo simulation here?** Randomly draw sequences of observed historical monthly-return blocks and compound alternative portfolios. Each simulated market-month shock applies to all portfolios simultaneously, so their differences are meaningfully paired.

**3. Why block bootstrap instead of independent normal draws?** Block sampling preserves empirical fat tails, cross-ETF correlations and some sequence structure; normal, independent draws can understate those features. It still cannot estimate unseen regimes.

**4. What does a 70% 'beats SPY' result mean?** In 70% of generated return-resampling paths under chosen historical input and parameters, the portfolio ended above SPY. It is not a calibrated forecast of the actual probability.

**5. What counts as Shariah-approved?** Screening is methodology-specific and time-dependent, incorporating business exclusions, financial-ratio screens, and sometimes purification rules. Dated SPUS ownership is fund holdings evidence, not a perpetual stock-level religious certification.

**6. What is the biggest limitation?** Today's 2026 stock list introduces universe-selection look-ahead and survivorship bias when backcast over past prices. Walk-forward optimization only avoids future *returns* leakage; it cannot fix historical constituent selection.

**7. How does optimizing the portfolio work?** Mean-variance optimization with a covariance matrix, long-only weights summing to 100%, a maximum position size, and diagonal shrinkage. Maximum-Sharpe also shrinks expected return estimates toward the cross-sectional mean to reduce extreme weights.

**8. What is walk-forward testing?** Estimate parameters on prior 36 months, fix the weights for subsequent six months, then repeat. It separates estimation from the following return period. It does not establish a fully point-in-time universe.

**9. How are dividends treated?** Adjusted price histories approximate reinvestment and capture corporate actions. The lab separately calculates purification only when exact user-supplied amounts and purification fractions are available; it does not guess Shariah-required purification.

**10. What would you build next with institutional data?** Historical monthly Shariah index constituents, delisting and corporate actions, portfolio turnover/fee estimates, sector/factor regression (especially tech concentration), and a live-tracked out-of-sample paper portfolio starting after the 2026 evidence date.

**11. How are you sure it is reproducible?** Fixed random seed, stored aligned price CSV and SHA-256, date-stamped metadata, well-scoped Python functions, unit tests, and a CLI that generates tables and a full report from the same source file.

**12. What did you learn?** A return difference is not the causal effect of a screening rule. Portfolio construction, sector exposure, date alignment, data integrity and selection bias matter at least as much as a headline CAGR.

### Honest resume bullet ideas

- *Built a Python/Streamlit Shariah ETF research platform comparing SPUS and HLAL with SPY using synchronized adjusted-price histories, risk diagnostics and 10,000-path paired-block Monte Carlo simulations.*
- *Implemented constrained mean-variance optimization, walk-forward weighting evaluation and reproducible research exports, explicitly identifying look-ahead risk in retrospective constituent-based backcasts.*

Only state **deployed** or **published performance results** after the app has actually been hosted and the market-data analysis has been verified.

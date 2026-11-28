# Shariah Portfolio Research Lab

**A standalone quantitative equity research platform.** Compare conventional S&P 500 exposure (SPY) to two Shariah-screened funds (SPUS and HLAL), construct a research basket from a dated SPUS holdings snapshot, test portfolio construction choices, and examine hypothetical wealth paths with a paired Monte Carlo bootstrap.

**Project status — version 1.0 research release candidate (25 Nov 2026):** Full Python research framework, Streamlit interface, exportable research report, reproducibility CLI, dated issuer-holdings evidence, and offline automated tests are implemented. The **live data download, hosted Streamlit app, and end-to-end user-browser launch have not been verified in this environment**. No real historical performance statistics have been fabricated or prefilled. This project is **not** deployed to the user's GitHub account; create a new GitHub repository before publishing.

> **Important:** SPY is not Shariah-compliant. SPUS and HLAL use distinct fund/index screening approaches. The custom basket consists of **stocks observed in a Shariah-screened fund on a documented date**; this is **not** an independent stock-by-stock Shariah certification, nor evidence of prior-years compliance. A study using today's top 20 holdings to calculate 2019+ returns suffers from **look-ahead and survivorship bias**. Its historical performance is explicitly labelled a *retrospective exposure illustration*, not an implementable, point-in-time Shariah investing strategy.

## What the project tests

1. Did SPUS or HLAL have different compounded returns, Sharpe/Sortino ratios, volatility, drawdowns, tracking error, and beta than SPY **over their exact common observed history**?
2. How much of a contemporary SPUS-derived 20-stock basket is concentrated in certain names or sectors?
3. How do monthly equal weighting, issuer-weight-normalized weighting, and constrained minimum-variance / maximum-Sharpe weighting differ?
4. Do weights refitted using only **past returns** hold up in subsequent six-month intervals? (This validates the weighting method, **not** historical eligibility of a present-day stock list.)
5. If a dated **complete historical screening record** is supplied, can a point-in-time strategy be calculated without using future compliance data? (The lab verifies dates and input completeness, not the provider's religious decisions.)
6. Under *paired historical block-resampled scenarios*, what are the 10th, 50th, and 90th percentile terminal values, loss-below-contributions frequencies, drawdown frequencies, and frequencies of beating SPY?
7. What amounts might require dividend purification if **actual dividend and purification rates** are provided from an independent source?

## Run locally (Python 3.11+)

```bash
python -m venv .venv
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

Choose **Yahoo Finance (live)** and leave the default 20-stock bundled SPUS issuer snapshot selected. The app will retrieve adjusted-price histories when internet access is available. Alternatively, upload a **real adjusted-price CSV** with one `Date` column and `SPY,SPUS,HLAL` plus your selected stock-ticker columns. Data source and dates appear on the dashboard, and the comparison uses a common observed calendar.

The app includes six tabs: **Performance**, **Portfolio builder**, **Risk & validation**, **Monte Carlo**, **Shariah evidence**, and **Research report**. Results have CSV export controls and the complete generated memorandum can be downloaded as Markdown.

### Command-line reproducibility

```bash
# Fetch real adjusted market prices, run every research calculation, save dated output:
python -m scripts.run_research --download --out-dir outputs

# Recreate the exact report from a known historical-price file:
python -m scripts.run_research --prices data/my_actual_adjusted_prices.csv --out-dir outputs

# SPY / SPUS / HLAL only — excludes the hindsight-selected custom basket:
python -m scripts.run_research --prices data/my_three_etfs.csv --no-basket --out-dir outputs

# When you have VERIFIED historical screening snapshots and matching stock prices:
python -m scripts.run_research --prices data/my_all_stocks.csv --no-basket --pit-history data/my_historical_screens.csv --out-dir outputs
```

The `outputs/` folder receives an automatically generated research note, market-price CSV, price-data SHA-256 digest, performance and benchmark metrics, monthly returns, Monte Carlo summaries, and (when applicable) basket weights, walk-forward allocations and point-in-time screening audit files. It is ignored by Git so your market-data source files are not accidentally claimed to be bundled observations. No silent fallback to synthetic market data occurs.

## Deploy your independent project

1. Create a **new** public repository at [github.com/new](https://github.com/new) called `shariah-portfolio-research`. **Do not** use `monte-carlo-investment-lab`.
2. Upload the **contents of this folder** to the root of that new repo (including `src/`, `data/`, `.streamlit/`, `.github/`, `tests/`, and `requirements.txt`). If you upload a single ZIP file without extracting it, Streamlit cannot execute the app.
3. Visit [Streamlit Community Cloud](https://share.streamlit.io), choose **Create app**, select the new repository, branch `main`, and entrypoint `app.py`. Deploy. See [Streamlit's official instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
4. If Yahoo Finance rate-limits shared cloud IPs, use the provided **CSV upload** option with a separately verified actual adjusted-price dataset. Do not generate sample prices to conceal an outage.
5. Confirm live prices against issuer fund data, review the displayed data window, and download a date-stamped research memorandum before citing performance results in resumes or interviews.

## Model and controls

- **Observed data:** Yahoo Finance `auto_adjust=True` daily market prices, intended as dividend-/split-adjusted price-history return proxies. Not fund NAV, official benchmark index returns, or a guarantee of executable prices. The data service is third-party and can be revised.
- **Alignment:** Shared observed trading dates across all series, **no fake interpolation**, drop incomplete final calendar month, and require at least 24 valid months (fewer months when launching a full custom basket are rejected).
- **Metrics:** CAGR, annualized monthly volatility, Sharpe and Sortino with explicit illustrative annual risk-free assumption (default 0%), *month-end* maximum drawdown, beta, correlation, active return and tracking error against SPY.
- **Monthly portfolio weighting:** Rebalanced every month, long-only, 100% invested, gross of incremental brokerage fees, spreads, taxes and dividend purification.
- **Optimization:** Scipy SLSQP, long-only stock-weight cap, covariance diagonal-shrinkage and expected-return shrinkage. In-sample optimizers are marked as such. Walk-forward uses a trailing 24–60 month estimation window and holds weights for the next six months.
- **Monte Carlo:** Resample contiguous *joint* monthly return blocks. Identical historical month draws across SPY, SPUS, HLAL and the custom basket preserve cross-series dependence; each series compounds with month-end contributions. Results are not true future probabilities, projected returns, or trading signals.
- **Sector attribution:** The monthly-rebalanced basket's additive return contributions by broad, user-editable sector are reported without claiming a causal Shariah-vs-SPY effect.
- **Historical eligibility:** An optional second CSV with *complete, dated screening snapshots* enables a point-in-time study. Each month's holdings come from the latest snapshot dated before that month began, and histories become invalid when the last record is over 65 days old. The software does not certify external screening decisions or solve missing delisted-security histories.
- **Screening registry:** 20 documented holdings from the SPUS issuer's **November 24, 2026** webpage snapshot. Evidence must have a date, source name, URL, and evidence type. The `ETF_HOLDING` evidence type does **not** imply independent certification. The app can fetch a fresh issuer CSV or import a user-screened registry.
- **Purification:** Only calculates amounts for explicitly entered share counts, gross distributions, and purification fractions. Does not estimate or certify required fractions.

## Folder structure

```text
shariah-portfolio-research/
├── app.py                               Streamlit dashboard
├── src/shariah_lab/
│   ├── data.py                          Historical data collection / validation
│   ├── screening.py                     Dated issuer holdings / evidence model
│   ├── point_in_time.py                 Strict historical-screening audit and strategy
│   ├── portfolio.py                     Portfolio / optimization / robustness
│   ├── model.py                         Historical ETF metrics / paired bootstrap
│   └── report.py                        Auto-generated research memorandum
├── scripts/run_research.py              Reproducible CLI and output manifest
├── data/spus_holdings_2026-11-24.csv    Actual 20-stock issuer snapshot
├── research/
│   ├── METHODOLOGY.md                   Full methods and identification limits
│   ├── DATA_PROVENANCE.md               Data and screening integrity checklist
│   ├── INTERVIEW_GUIDE.md               Project defense for recruiters
│   └── RESEARCH_TEMPLATE.md             Report structure
├── tests/                               Offline synthetic-fixture unit tests
├── .github/workflows/tests.yml          GitHub Actions tests on push/PR
├── .streamlit/config.toml               App theme
├── requirements.txt
└── README.md
```

## Research limits, especially for recruiting

**Do not** call these stocks "Shariah-approved throughout 2019–2026" or claim a profitable, implementable strategy on the strength of a 2026 list. That would involve hindsight selection. Correct research language is: *"I used dated holdings from a Shariah-screened ETF as a present-day research universe, compared its retrospective risk exposures with broad-market benchmarks, and implemented walk-forward optimization while transparently identifying the remaining universe-selection bias."* 

Further research would require **historical point-in-time screening/holdings files for each rebalance date**, corresponding membership-change rules, a comprehensive delisted-stock data source, independently verified financial screening and dividend purification, realistic turnover costs, and deeper factor/sector controls.

**This is an educational research tool, not financial advice or an independent Shariah ruling.**

### Core external methodology sources

- [SPUS fund page and official dated holdings](https://www.sp-funds.com/SPUS/)
- [Wahed HLAL fund information and purification documents](https://www.wahed.com/hlal)
- [S&P 500 Shariah Industry Exclusions Index](https://www.spglobal.com/spdji/en/indices/equity/sp-500-shariah-industry-exclusions-index/)
- [HLAL's SEC-filed FTSE USA Shariah methodology](https://www.sec.gov/Archives/edgar/data/1683471/000089418926026510/R4.htm)
- [yfinance price-history reference](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html)
- [Streamlit deployment documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

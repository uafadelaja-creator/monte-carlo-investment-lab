# Historical data + statistical-arbitrage research (v0.5)

This empirical module is separate from the original assumption-driven `simulate.py`.
It tests predeclared pairs and does not generate live trade alerts or assert alpha.

## Fixed research protocol

| Item | Frozen setting |
|---|---|
| Candidate hypotheses | V/MA, KO/PEP, XOM/CVX |
| Broad benchmark | SPY |
| Sector benchmarks | XLF, XLP, XLE |
| Exploration window | 2015-01-01 through 2022-12-30 |
| Holdout start | 2023-01-03 |
| Formation / normalization | 252 / 60 sessions |
| Refit frequency | 21 sessions |
| Entry / exit / stop | ±2.0 / ±0.5 / ±3.5 Z |
| Cointegration gate | trailing Engle-Granger p ≤ 0.05 |
| Modeled execution | signal after close T; fill at close T+1; P&L begins T+1→T+2 |
| Turnover cost | 10 bps per notional dollar traded |
| Borrow drag | hypothetical 3% annual rate on short notional |
| Monte Carlo | 50,000 moving-block paths, 20-session blocks, seed 20261018 |

The three pairs are hypotheses, not presumed cointegrated opportunities. The protocol
does not choose a winner after seeing the holdout.

## Reproduce locally

1. Use Python 3.11+.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Download exploratory data through the final trading session. The example end
   date is exclusive:

   ```bash
   python download_prices.py --start 2015-01-01 --end 2026-10-17
   ```

5. Inspect `data/download_manifest.json`, missing observations, and hashes.
   `adjusted_close.csv` is the model input. It approximates total return after
   vendor corporate-action adjustment and is **not an executable historical price**.
   `raw_close.csv` is audit context only. Both are excluded from Git.

   Download the official daily Fama-French research factors for descriptive
   HAC-robust attribution:

   ```bash
   python download_french_factors.py
   ```

6. Run the complete fixed protocol:

   ```bash
   python run_stat_arb_research.py \
     --test-start 2023-01-03 \
     --paths 50000 --block 20 --seed 20261018
   ```

7. Run tests:

   ```bash
   python -m unittest discover -s tests -v
   ```

## Outputs

The baseline report for each pair contains net return, CAGR, volatility, Sharpe and
Sortino ratios at a disclosed 0% risk-free assumption, maximum drawdown, exposure,
turnover, modeled costs, SPY and sector-benchmark metrics, and moving-block
distributions for 1/3/6/12/24/36 months. The aggregate runner also records 5/10/20
bps cost sensitivity and 126/252/504-session formation sensitivity.
Each pair report also includes a descriptive Fama-French three-factor regression
when the official factor file is present; its alpha p-value is not treated as proof.

No capital contributions are modeled in this self-financing long/short module.
That differs from the contribution-aware ETF portfolio Monte Carlo.

## Data and research sources

- Yahoo Finance through [yfinance](https://ranaroussi.github.io/yfinance/) is an
  unofficial exploratory source; availability, corrections, and permitted uses
  can change.
- [Kenneth French's official data library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
  is the intended source for a later factor-model extension.
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
  will support future point-in-time classifications using filing availability dates.
- Delisting-inclusive CRSP data would materially improve the universe study if
  authorized institutional access becomes available. This project does not imply
  direct undergraduate WRDS access.
- Cointegration uses the documented
  [statsmodels Engle-Granger implementation](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.coint.html).

## What the prototype does not establish

- Present-day liquid pairs introduce survivorship and point-in-time membership bias.
- A trailing cointegration p-value is a filter, not proof of durable mean reversion.
- Repeated rolling tests are dependent; ordinary p-values do not fix data snooping.
- Adjusted closes do not model next-session executable quotes, spreads, market
  impact, locates, recalls, margin requirements, intraday gaps, taxes, or outages.
- The 10 bps cost and 3% borrow assumptions are scenarios, not observed costs.
- Moving-block resampling is conditional on the observed holdout and cannot create
  a truly unseen crisis or structural break.
- Risk-adjusted returns and statistical significance do not by themselves prove
  implementable alpha.

## First fixed holdout, 18 October 2026

The protocol used adjusted daily observations through 2026-10-16. V/MA made two
entries and returned −0.005% net; KO/PEP made no entries; XOM/CVX made one entry
and returned −2.29% net. The rules were exposed only 0%–2.1% of sessions. At 36
months, moving-block loss probabilities were 45.7% for V/MA and 80.1% for XOM/CVX;
KO/PEP stayed at zero because it never traded. Formation-window and transaction-
cost sensitivity was material. This is evidence of inactivity/instability, not a
validated alpha source.

## Roadmap

1. Run and archive the fixed protocol on real exploratory data.
2. Add official Kenneth French factors and HAC-robust attribution without using
   significance alone as an edge claim.
3. Replace adjusted-close fills with timestamped executable-price approximations
   and observed liquidity/borrow assumptions.
4. Add a delisting-inclusive, point-in-time universe if authorized data become
   available.
5. Forward-paper-trade timestamped signals before considering any real-money use.


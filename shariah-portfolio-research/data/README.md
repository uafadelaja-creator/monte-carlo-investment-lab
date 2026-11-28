# Dataset contracts and provenance

The only bundled non-synthetic market **universe** file is `spus_holdings_2026-11-24.csv`. Its ticker names, company descriptions and issuer-weight percentages are transcribed from the SP Funds official SPUS fund holdings table, last observed November 24, 2026: https://www.sp-funds.com/SPUS/. Broad sector labels were added as an editable analyst grouping (not an official GICS license or a Shariah assessment).

**No historical prices are bundled:** run with Yahoo Finance internet access or upload a genuine adjusted-price CSV. As of this release, we have not independently verified the live download from the current runtime.

### Adjusted-price input example (header only)

`Date,SPY,SPUS,HLAL,AAPL,NVDA,MSFT,GOOGL,AVGO,LLY,TSLA,MU,AMD,JNJ,XOM,ABBV,PG,CSCO,HD,MRK,PANW,AMAT,TXN,LRCX`

- Every date must represent observed prices for the assets under study. Never enter fabricated price histories.
- Numbers should be **dividend- and split-adjusted market closes**, with consistent price-adjustment definitions for every stock and ETF.
- Preserve the vendor/export timestamp and the SHA256 checksum of the market-price CSV for reproducibility.
- Avoid combining manually split-adjusted prices with already-adjusted downloaded prices.
- Data gaps or tickers with insufficient common history can prevent custom-basket analysis; choose ETFs only if you cannot verify stock history.

### Dated holdings CSV schema

` ticker,company,sector,issuer_weight_pct,as_of,evidence_type,source_name,source_url `

`evidence_type` is either `ETF_HOLDING` (reported ETF constituent; not independent certification) or `CUSTOM_SCREENED` (an external screening assessment you supplied and must independently verify). `as_of` records a snapshot, **not** a historical eligibility interval. No historical membership is inferred from the present-day table.

### Dividend purification inputs

` ticker,shares,dividend_per_share,purification_fraction `

Enter fractions between 0 and 1 from your screening advisor or issuer's reported purification information. The worksheet computes shares × dividend per share × rate; it does not choose a rate.

### Historical point-in-time screening inputs (advanced)

` as_of,ticker,eligible,source_name,source_url,weight_hint `

For every as_of date, each row belongs to a **complete** provider screening snapshot. `eligible` is yes/no (or true/false); omitted tickers are treated as **not** eligible, not silently carried forward. Latest valid snapshot must predate the *start* of a return month; records older than 65 days are considered stale. The provided adjusted-price dataset must include historical price histories for every documented eligible ticker. At least 24 eligible months are required.

The software checks dates, evidence presence, nonnegative weights and monthly coverage. It **cannot authenticate the provider's Shariah conclusions** or detect missing historical delisted companies, so source audit is still required.

"""Build both site pages from a shared layout and historical model outputs."""
import argparse
import html
import json
from pathlib import Path

ETF_INFO = {
    'ARKK': ('ARK Innovation ETF', 'Actively managed companies pursuing disruptive innovation, from robotics to genomics. An innovation-focused equity strategy.', 'https://www.ark-funds.com/funds/arkk'),
    'QUAL': ('iShares USA Quality Factor ETF', 'U.S. companies selected for strong profitability, stable earnings, and low debt. Quality is a selection rule, not a guarantee.', 'https://www.ishares.com/us/products/256101/QUAL'),
    'SPY': ('SPDR S&P 500 ETF Trust', 'Broad exposure to roughly 500 large U.S. companies. The benchmark for comparing investment outcomes in this project.', 'https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy'),
}
COLORS = {'ARKK': '#8961c3', 'QUAL': '#4b80c0', 'SPY': '#167d70'}


def shell(content, page, data):
    m = data['metadata']
    nav = ''.join(f'<a href="{url}"'+(' aria-current="page"' if page == key else '')+f'>{label}</a>' for key,url,label in [('overview','index.html','Overview'),('research','historical_results.html','Research & data')])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Historical ETF performance and reproducible Monte Carlo analysis of ARKK, QUAL, and SPY.">
<title>{'Overview' if page == 'overview' else 'Research & data'} · Monte Carlo Investment Lab</title>
<link rel="stylesheet" href="assets/site.css"><script defer src="assets/dashboard.js"></script></head>
<body data-page="{page}"><header class="site-header"><div class="header-inner"><a class="brand" href="index.html"><span class="brand-mark">M</span><span>Monte Carlo<small>Investment Lab</small></span></a><nav class="nav" aria-label="Main navigation">{nav}</nav><span class="author">Independent research · Umar Adelaja</span></div></header>
<main><div id="load-error" class="error" role="alert" hidden></div>{content}
<noscript><p class="no-script">Enable JavaScript for interactive charts and controls. <a href="results/historical_risk_metrics.csv">Download historical metrics</a> or <a href="results/historical_simulation_summary.csv">simulation results</a>.</p></noscript></main>
<footer class="footer"><span>Umar Adelaja · Built with AI assistance · Research, not investment advice</span><span>Data through {m['input_last_date']} · <a href="https://github.com/uafadelaja-creator/monte-carlo-investment-lab">View source ↗</a></span></footer></body></html>'''


def etfs():
    return '<div class="etfs">'+''.join(f'<article class="etf-card"><span class="ticker"><span class="dot" style="background:{COLORS[t]}"></span>{t}</span><h3>{name}</h3><p>{description}</p><a href="{url}">Explore the fund ↗</a></article>' for t,(name,description,url) in ETF_INFO.items())+'</div>'


def overview(data):
    m=data['metadata']
    content=f'''<section class="hero"><div><p class="eyebrow">Evidence before expectations</p><h1>Portfolio risk, grounded in history.</h1><p class="intro">Explore how innovation, quality, and the broader market performed. Then use that history to examine a range of possible investment outcomes.</p></div><div class="data-status"><strong><span class="status-dot"></span>Historical data connected</strong>{m['input_price_rows']:,} daily observations · 3 ETFs</div></section>
<div class="tabs" role="tablist" aria-label="Analysis view"><button id="tab-history" role="tab" aria-selected="true" aria-controls="history-view">Historical performance</button><button id="tab-monte" role="tab" aria-selected="false" aria-controls="monte-view" tabindex="-1">Monte Carlo simulation</button></div>
<section id="history-view" role="tabpanel" aria-labelledby="tab-history">
<div id="history-metrics" class="metrics"></div>
<section class="panel"><div class="panel-head"><div><h2>Growth of $1,000</h2><p class="panel-sub">Observed adjusted-price performance · no additional contributions</p></div><span class="pill">Jan 2015 – Oct 2026 · month-end</span></div>
<div class="chart-grid"><div class="chart-panel"><div class="legend"><span><i class="dot" style="background:#8961c3"></i>ARKK · Innovation</span><span><i class="dot" style="background:#4b80c0"></i>QUAL · Quality</span><span><i class="dot"></i>SPY · Benchmark</span></div><svg id="history-chart" class="chart" role="img" aria-label="Historical growth of one thousand dollars for ARKK, QUAL, and SPY"></svg><div id="history-readout" class="chart-readout">Hover or tap the chart to inspect a month.</div><p class="chart-caption">Rebased to $1,000 at the end of January 2015. Prices include dividend and split adjustments.</p></div><aside class="aside"><p class="eyebrow">The research sample</p><dl><dt>Completed monthly returns</dt><dd>{m['common_return_months']}</dd><dt>Common observation window</dt><dd>11 years, 9 months</dd><dt>Comparison benchmark</dt><dd>S&P 500 · SPY</dd></dl><p>November prices are present in the input, but the incomplete month is excluded from analysis.</p></aside></div></section>
<section class="panel"><div class="panel-head"><div><h2>Return is only half the story.</h2><p class="panel-sub">Compare growth with volatility and the losses experienced along the way.</p></div><a class="button" href="results/historical_risk_metrics.csv">Download metrics ↓</a></div><div class="table-wrap"><table><thead><tr><th>ETF</th><th>Historical CAGR</th><th>Annual volatility</th><th>Maximum drawdown</th><th>Best month</th><th>Worst month</th></tr></thead><tbody id="risk-table"></tbody></table></div><p class="chart-caption">CAGR is annualized compounded growth. Drawdown is the largest month-end decline from a previous peak.</p></section>
</section>
<section id="monte-view" role="tabpanel" aria-labelledby="tab-monte" hidden>
<div class="model-note"><strong>HISTORY-BASED</strong><span>50,000 paths resampled from observed joint returns. These are hypothetical outcomes, not actual future prices.</span></div>
<div class="controls"><label>Investment<select id="portfolio"><option value="ARKK">ARKK · Innovation</option><option value="QUAL">QUAL · Quality</option><option value="SPY" selected>SPY · S&P 500</option></select></label><label>Time horizon<select id="horizon"><option value="1">1 month</option><option value="3">3 months</option><option value="6">6 months</option><option value="12">1 year</option><option value="24">2 years</option><option value="36" selected>3 years</option></select></label><label>Weekly contribution<select id="weekly"><option value="0">$0 / week</option><option value="50">$50 / week</option><option value="100" selected>$100 / week</option><option value="200">$200 / week</option></select></label><label>Scenario<select id="scenario"><option value="baseline">Historical bootstrap</option><option value="shock">Hypothetical initial shock</option></select></label></div>
<div id="simulation-metrics" class="metrics" aria-live="polite"></div>
<section class="panel"><div class="panel-head"><div><h2 id="fan-title">A range of possible outcomes</h2><p class="panel-sub" id="fan-subtitle"></p></div><span class="pill">50,000 paths · paired comparisons</span></div><div class="chart-grid"><div class="chart-panel"><div class="legend"><span><i class="dot" id="fan-dot"></i>Median outcome</span><span>Shaded area: 5th–95th percentile</span><span>Dashed line: deposits</span></div><svg id="fan-chart" class="chart" role="img" aria-label="Historical bootstrap median wealth and fifth to ninety-fifth percentile band"></svg><div id="fan-readout" class="chart-readout"></div><p class="chart-caption">The band shows pointwise simulated percentiles, not guaranteed bounds. Month-end deposits approximate weekly investing.</p></div><aside class="aside"><p class="eyebrow">Model settings</p><dl><dt>Initial investment</dt><dd>$500</dd><dt>Historical sampling</dt><dd>3-month blocks</dd><dt>Path generation</dt><dd>Joint across all ETFs</dd></dl><p>Whole market periods are resampled together, preserving observed relationships between the ETFs.</p></aside></div></section>
<section class="panel"><div class="panel-head"><div><h2>Compare all three investments</h2><p class="panel-sub">Identical deposits and the same sampled market periods.</p></div><button class="button" id="download-comparison">Download comparison ↓</button></div><div class="table-wrap"><table><thead><tr><th>ETF</th><th>Median value</th><th>5th–95th range</th><th>Loss frequency</th><th>Beat SPY frequency</th><th>Median max drawdown</th></tr></thead><tbody id="comparison"></tbody></table></div><p class="chart-caption" id="scenario-note"></p></section>
</section>
<div class="section-heading"><h2>Three funds. Three different approaches.</h2><span class="small">Understand what you are comparing</span></div>{etfs()}
<p class="notice">These ETFs are not selected using Shariah screening rules. This is a conventional ETF comparison; a Shariah-compliant portfolio would require separately screened investments.</p>'''
    return shell(content,'overview',data)


def research(data):
    m=data['metadata']
    limitations=''.join(f'<li>{html.escape(x)}</li>' for x in m['limitations'])
    meta=''.join(f'<div><dt>{label}</dt><dd>{html.escape(str(value))}</dd></div>' for label,value in [('Source','Yahoo Finance via yfinance'),('Input coverage',m['input_first_date']+' → '+m['input_last_date']),('Input price rows',f"{m['input_price_rows']:,}"),('Model window',m['first_return_month'][:7]+' → '+m['last_return_month'][:7]),('Monte Carlo paths',f"{m['paths']:,}"),('Random seed',m['master_seed']),('Primary block length','3 months'),('Sensitivity checks','1 / 3 / 6 months')])
    content=f'''<section class="hero"><div><p class="eyebrow">Transparent by design</p><h1>Behind the results.</h1><p class="intro">The source, method, and limitations behind every chart. Historical observations and simulated projections are kept distinct throughout the lab.</p></div><a class="button" href="index.html">Back to overview ↗</a></section>
<div class="research-grid"><section class="panel"><div class="panel-head"><h2>From prices to possible outcomes</h2><span class="pill">Methodology</span></div>
<div class="step"><span class="step-number">01</span><div><h3>Start with observed prices</h3><p>The uploaded CSV contains adjusted daily closes for ARKK, QUAL, and SPY. Dates must be unique and prices finite, positive, and complete.</p></div></div>
<div class="step"><span class="step-number">02</span><div><h3>Use a common monthly history</h3><p>Take each completed month's final price and calculate percentage changes. Exclude partial November and reject missing months.</p></div></div>
<div class="step"><span class="step-number">03</span><div><h3>Resample market periods together</h3><p>Draw consecutive three-month blocks of all three ETFs' returns. Repeat to generate 50,000 paths of up to 36 months.</p></div></div>
<div class="step"><span class="step-number">04</span><div><h3>Apply deposits and compare risk</h3><p>Each arm starts with $500. Weekly contributions are converted to month-end deposits. Drawdowns exclude deposits so new cash does not hide losses.</p></div></div></section>
<section class="panel"><h2>Data provenance</h2><dl class="meta-list">{meta}</dl><p class="small">Original input SHA-256</p><div class="hash">{m['input_price_sha256']}</div><p class="small">Input prices passed structural validation, but were not independently reconciled with another provider. Raw vendor price tables remain local; aggregate results and normalized chart series are published.</p><a class="button" href="results/historical_metadata.json">Full metadata ↓</a></section></div>
<section class="panel" style="margin-top:20px"><div class="panel-head"><div><h2>How closely did the funds move together?</h2><p class="panel-sub">Observed monthly return correlations · a value near 1 means similar direction and timing.</p></div><span class="pill">Common historical window</span></div><div class="table-wrap"><table><thead><tr><th>ETF</th><th>ARKK</th><th>QUAL</th><th>SPY</th></tr></thead><tbody id="correlation-table"></tbody></table></div></section>
<section class="panel"><div class="panel-head"><div><h2>Does the sampling choice change the answer?</h2><p class="panel-sub">36-month outcomes at $100/week. Compare one-, three-, and six-month block lengths.</p></div><a class="button" href="results/historical_block_sensitivity.csv">Download sensitivity ↓</a></div><div class="table-wrap"><table><thead><tr><th>Block</th><th>ETF</th><th>Median value</th><th>5th–95th range</th><th>Loss frequency</th><th>Beat SPY frequency</th></tr></thead><tbody id="sensitivity-table"></tbody></table></div></section>
<div class="research-grid"><section class="panel"><h2>What the model does not establish</h2><ul class="limitations">{limitations}</ul><p class="small">This is descriptive risk research, not evidence of a profitable trading strategy or a validated forecast. No out-of-sample validation is claimed.</p></section><section class="panel"><h2>Stress assumptions</h2><p class="panel-sub">The optional shock is hypothetical, not an observed event or estimated probability.</p><div class="table-wrap"><table><thead><tr><th>ETF</th><th>Additional first-month shock</th></tr></thead><tbody><tr><td>ARKK</td><td>−25%</td></tr><tr><td>QUAL</td><td>−15%</td></tr><tr><td>SPY</td><td>−18%</td></tr></tbody></table></div><p class="small">The shock multiplies the first sampled month's gross return before its month-end contribution. Subsequent months follow the same sampled history.</p><h3 style="margin-top:24px">Reproducible outputs</h3><div class="downloads"><a class="button" href="results/historical_simulation_summary.csv">Simulation CSV ↓</a><a class="button" href="results/historical_risk_metrics.csv">Risk CSV ↓</a><a class="button" href="results/historical_dashboard_data.json">Dashboard JSON ↓</a></div><p class="small">See the repository README for commands. Matching input data, seed, parameters, and dependencies reproduce the results. New vendor downloads can revise historical prices.</p></section></div>
<div class="section-heading"><h2>Fund definitions & sources</h2></div>{etfs()}<p class="notice">The site uses historical bootstrap data exclusively. The older assumption-based engine is retained only as archived research code, not as a source for these pages.</p>'''
    return shell(content,'research',data)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=Path('results/historical_dashboard_data.json'))
    parser.add_argument('--output',type=Path,default=Path('historical_results.html'))
    parser.add_argument('--index-output',type=Path,default=Path('index.html'))
    args=parser.parse_args();data=json.loads(args.data.read_text())
    args.output.write_text(research(data),encoding='utf-8')
    args.index_output.write_text(overview(data),encoding='utf-8')

if __name__=='__main__':
    main()

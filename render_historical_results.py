"""Render the public historical report from generated aggregate JSON."""
import argparse
import html
import json
from pathlib import Path


ETF_INFO = {
    "ARKK": ("ARK Innovation ETF", "Actively managed companies focused on disruptive innovation. Represents the innovation-focused strategy.", "https://www.ark-funds.com/funds/arkk"),
    "QUAL": ("iShares MSCI USA Quality Factor ETF", "U.S. stocks selected for high return on equity, stable earnings, and low debt. Quality does not mean risk-free.", "https://www.ishares.com/us/products/256101/QUAL"),
    "SPY": ("SPDR S&P 500 ETF Trust", "Tracks the S&P 500: roughly 500 large U.S. companies. Serves as the comparison benchmark.", "https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy"),
}


def render(data, results_url="results"):
    m = data["metadata"]
    esc = html.escape
    pct = lambda x: "—" if x is None else f"{x:.1%}"
    usd = lambda x: f"${x:,.0f}"
    cards = "".join(f'<section class="card"><h2>{ticker}</h2><strong>{esc(name)}</strong><p>{esc(description)}</p><a href="{url}">Fund provider</a></section>'
                    for ticker, (name, description, url) in ETF_INFO.items())
    risk = "".join(f'<tr><td>{r["ticker"]}</td><td>{pct(r["cagr"])}</td><td>{pct(r["annualized_volatility"])}</td><td>{pct(r["historical_max_drawdown_month_end"])}</td></tr>' for r in data["risk_metrics"])
    outcomes = "".join(f'<tr><td>{r["months"]}</td><td>{r["ticker"]}</td><td>{usd(r["contributed_usd"])}</td><td>{usd(r["median_ending_value"])}</td><td>{usd(r["p05"])}–{usd(r["p95"])}</td><td>{pct(r["prob_loss"])}</td><td>{pct(r["prob_beat_spy"])}</td></tr>' for r in data["baseline"])
    limitations = "".join(f"<li>{esc(line)}</li>" for line in m["limitations"])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Historical ETF Results · Monte Carlo Investment Lab</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#08111f;color:#eef4ff;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1160px;margin:auto;padding:36px 24px}}h1{{font-size:clamp(30px,5vw,52px);line-height:1.1}}h2{{margin-top:32px}}p,li{{color:#b5c5dc}}a{{color:#8ec1ff}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.card{{background:#101c2f;border:1px solid #263650;border-radius:14px;padding:20px}}.card h2{{margin-top:0}}.table{{overflow:auto}}table{{width:100%;border-collapse:collapse;white-space:nowrap}}th,td{{padding:12px;text-align:right;border-bottom:1px solid #263650}}th:first-child,td:first-child{{text-align:left}}th{{color:#bcd0ef}}img{{width:100%;background:white;border-radius:12px}}code{{overflow-wrap:anywhere}}.note{{border-left:3px solid #ffbf69;padding:12px 16px;background:#192133}}footer{{margin-top:32px;font-size:13px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}main{{padding:24px 16px}}}}
</style></head><body><main>
<a href="index.html">Illustrative scenario dashboard</a>
<h1>Historical ETF results</h1>
<p>{m['paths']:,} joint bootstrap paths, calibrated to your uploaded adjusted-price history. These are conditional simulations, not forecasts.</p>
<p><strong>Input:</strong> {m['input_price_rows']:,} price rows, {esc(m['input_first_date'])}–{esc(m['input_last_date'])}. <strong>Model sample:</strong> {m['common_return_months']} complete monthly returns, {m['first_return_month'][:7]}–{m['last_return_month'][:7]}. Partial months are excluded.</p>
<h2>What the ETFs represent</h2><div class="grid">{cards}</div>
<p class="note">These funds are not selected using Shariah screens. This comparison is not a Shariah-compliant portfolio; SPY is a benchmark.</p>
<h2>Observed historical risk</h2><p>Calculated from month-end adjusted prices. Daily or intramonth losses can be larger.</p>
<div class="table"><table><thead><tr><th>ETF</th><th>Historical CAGR</th><th>Annualized volatility</th><th>Maximum drawdown</th></tr></thead><tbody>{risk}</tbody></table></div>
<h2>Observed versus simulated drawdowns</h2><img src="{esc(results_url)}/historical_drawdown.svg" alt="Historical maximum drawdown and median simulated 36-month drawdown for each ETF">
<h2>Simulated outcomes</h2><p>Each ETF is a separate investment arm starting with {usd(m['starting_cash_usd'])}, receiving {usd(m['weekly_contribution_usd'])}/week represented as ${m['monthly_equivalent_contribution_usd']:,.2f} at month-end. Loss means ending below total deposits. P(beat SPY) compares the same resampled market periods.</p>
<div class="table"><table><thead><tr><th>Months</th><th>ETF</th><th>Deposited</th><th>Median value</th><th>5th–95th percentile</th><th>P(loss)</th><th>P(beat SPY)</th></tr></thead><tbody>{outcomes}</tbody></table></div>
<h2>How to interpret this</h2><p>The model samples consecutive {m['block_months_primary']}-month blocks across all three ETFs together, preserving observed co-movement. The 1- and 6-month block comparisons and hypothetical shock results are available in the aggregate downloads. No trading strategy or out-of-sample performance claim is established by this simulation.</p>
<ul>{limitations}</ul>
<h2>Download calculated results</h2><p><a href="{esc(results_url)}/historical_simulation_summary.csv">Simulation CSV</a> · <a href="{esc(results_url)}/historical_risk_metrics.csv">Risk metrics</a> · <a href="{esc(results_url)}/historical_correlations.csv">Correlations</a> · <a href="{esc(results_url)}/historical_block_sensitivity.csv">Block sensitivity</a> · <a href="{esc(results_url)}/historical_metadata.json">Input provenance and parameters</a></p>
<footer><p>Source: {esc(m['data_source'])}. Input prices are reported as adjusted closes, not executable quotes. Vendor price tables remain local.</p><p>Input SHA-256: <code>{esc(m['input_price_sha256'] or 'Not supplied')}</code><br>Seed: {m['master_seed']} · Engine: {m['version']}</p></footer>
</main></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("results/historical_dashboard_data.json"))
    parser.add_argument("--output", type=Path, default=Path("historical_results.html"))
    args = parser.parse_args()
    args.output.write_text(render(json.loads(args.data.read_text())), encoding="utf-8")


if __name__ == "__main__":
    main()

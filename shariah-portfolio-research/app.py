"""Shariah Portfolio Research Lab — standalone Streamlit research application.

Data provenance first. No synthetic financial history, no stock certification,
and no benchmark return assumptions are silently fabricated.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from src.shariah_lab.data import (
    DataError, TICKERS, download_universe_prices, load_universe_csv,
    monthly_returns, to_csv_bytes, trim_incomplete_last_month, validate_universe_prices,
)
from src.shariah_lab.model import fan_percentiles, moving_block_bootstrap, simulation_summary
from src.shariah_lab.point_in_time import load_pit_history, backtest_pit, PITError
from src.shariah_lab.portfolio import (
    PortfolioError, benchmark_diagnostics, concentration, metric_table, optimization_weights,
    portfolio_returns, purification_worksheet, rolling_annualized, sector_allocation, sector_return_attribution,
    walk_forward, worst_benchmark_months,
)
from src.shariah_lab.report import build_report
from src.shariah_lab.screening import (
    ScreeningError, SPUS_ISSUER_PAGE, fetch_live_spus_holdings,
    load_registry, suggested_weights,
)

st.set_page_config(page_title="Shariah Portfolio Research Lab", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
COLORS = {
    "SPY": "#8898A8", "SPUS": "#53D5B0", "HLAL": "#6EACED",
    "Custom basket": "#E7B86C", "Walk-forward Minimum variance": "#E7B86C", "PIT screened strategy": "#BF93FF",
}
DISPLAY = {
    "SPY": "SPY · conventional S&P 500 benchmark",
    "SPUS": "SPUS · SP Funds Shariah ETF",
    "HLAL": "HLAL · Wahed FTSE Shariah ETF",
    "Custom basket": "Custom · dated SPUS holdings basket",
    "PIT screened strategy": "PIT · uploaded historical screening records",
}
st.markdown("""<style>
.block-container { max-width: 1400px; padding-top: 1.45rem; padding-bottom: 3rem; }
h1, h2, h3 { letter-spacing: -.025em; }
[data-testid="stMetric"] { border: 1px solid rgba(120,145,170,.25); border-radius: 13px; padding: 13px 15px; }
[data-testid="stSidebar"] { border-right: 1px solid rgba(100,125,150,.25); }
div[data-testid="stTabs"] button { font-weight: 600; }
</style>""", unsafe_allow_html=True)

st.title("Shariah Portfolio Research Lab")
st.caption("Historical evidence  /  Dated holdings  /  Risk attribution  /  Monte Carlo  /  Reproducible research")
st.info("**Interpretation rule:** SPY is not Shariah-screened. A 2026 SPUS holdings snapshot is a **current research universe**, not evidence that each stock was Shariah-compliant in every prior year. Pre-snapshot basket performance is a **retrospective illustration**, not an investable historical Shariah backtest.")

with st.sidebar:
    st.header("Data & universe")
    source = st.radio("Market price source", ["Yahoo Finance (live)", "Upload adjusted-price CSV"], help="Never switch silently to fake prices.")
    start = st.date_input("Beginning", value=date(2019, 12, 1), max_value=date.today())
    end = st.date_input("Through", value=date.today(), max_value=date.today())
    uploaded_prices = st.file_uploader("Adjusted-price CSV", type=["csv"], key="prices") if source.startswith("Upload") else None
    st.divider()
    build_custom = st.toggle("Include custom holdings basket", value=False)
    registry_source = "Bundled dated SPUS snapshot"
    uploaded_registry = None
    if build_custom:
        registry_source = st.radio(
            "Holdings evidence", ["Bundled dated SPUS snapshot", "Latest official SPUS CSV", "Upload screening/holdings registry"],
            help="Live holdings are today's cross-section. They do not create a point-in-time universe for previous years.",
        )
        if registry_source.startswith("Upload"):
            uploaded_registry = st.file_uploader("Holdings evidence CSV", type=["csv"], key="holdings")
        basket_size = st.slider("Number of names", 5, 20, 20)
        weight_method = st.selectbox("Portfolio construction", ["Equal weight", "Issuer proportional (top basket only)", "Minimum variance", "Maximum Sharpe"])
        max_weight = st.slider("Maximum optimizer stock weight (%)", 8, 30, 15, 1) / 100
    else:
        basket_size = 0
        weight_method = "Equal weight"
        max_weight = .15
    st.divider()
    st.subheader("Advanced: historical eligibility")
    pit_upload = st.file_uploader("Full dated screening-history CSV (optional)", type=["csv"], key="pit", help="Unlike the one-day holdings snapshot, complete historical evidence is needed to avoid selecting today's stocks in earlier years.")
    pit_weighting = st.selectbox("Historical-screen weights", ["Equal weight", "Evidence proportional"]) if pit_upload is not None else "Equal weight"
    st.divider()
    st.subheader("Scenario assumptions")
    initial = st.number_input("Initial capital ($)", min_value=0, max_value=10_000_000, value=10_000, step=1_000)
    monthly_deposit = st.number_input("Monthly deposit ($)", min_value=0, max_value=200_000, value=250, step=50)
    years = st.slider("Years to simulate", 1, 30, 10)
    n_sims = st.select_slider("Monte Carlo paths", [1_000, 5_000, 10_000, 20_000], value=10_000)
    block = st.slider("Resampled block length (months)", 1, 12, 6)
    seed = st.number_input("Reproducibility seed", min_value=0, max_value=2_147_483_647, value=42, step=1)
    annual_rf = st.number_input("Assumed annual risk-free rate (%)", -5., 30., 0., .25) / 100


@st.cache_data(ttl=3600, show_spinner=False)
def cached_prices(start_date: date, end_date: date, symbols: tuple[str, ...]) -> pd.DataFrame:
    return download_universe_prices(start_date, end_date, symbols)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_issuer_holdings() -> pd.DataFrame:
    return fetch_live_spus_holdings(limit=100)


try:
    holdings = None
    custom_names = []
    if build_custom:
        if registry_source == "Bundled dated SPUS snapshot":
            holdings = load_registry()
        elif registry_source == "Latest official SPUS CSV":
            with st.spinner("Retrieving published holdings from SP Funds..."):
                holdings = cached_issuer_holdings()
        else:
            if uploaded_registry is None:
                st.warning("Upload the holdings-evidence CSV, or use the bundled dated SPUS snapshot.")
                st.stop()
            holdings = load_registry(uploaded_registry.getvalue())
        holdings = holdings.sort_values("issuer_weight_pct", ascending=False).head(basket_size).reset_index(drop=True)
        custom_names = holdings["ticker"].tolist()

    pit_history = load_pit_history(pit_upload.getvalue()) if pit_upload is not None else None
    if pit_history is not None and pit_history.attrs.get("assumed_publication_date"):
        st.warning("This file lacks published_at. Historical results assume each snapshot was published on its as-of date.")
    pit_names = list(pit_history.loc[pit_history["eligible"], "ticker"].unique()) if pit_history is not None else []
    requested = tuple(dict.fromkeys([*TICKERS, *custom_names, *pit_names]))
    if source == "Yahoo Finance (live)":
        with st.spinner(f"Retrieving adjusted returns for {len(requested)} securities..."):
            raw_prices = cached_prices(start, end, requested)
        source_description = f"Yahoo Finance adjusted daily closes, retrieved on {date.today().isoformat()}"
    else:
        if uploaded_prices is None:
            st.warning("Upload adjusted historical prices with Date, SPY, SPUS, and HLAL columns. Add stock columns for any selected basket. Or choose Yahoo Finance.")
            st.stop()
        raw_prices = load_universe_csv(uploaded_prices.getvalue(), required=TICKERS, align=False)
        raw_prices = raw_prices.loc[(raw_prices.index.date >= start) & (raw_prices.index.date <= end)]
        source_description = f"User-supplied adjusted-price CSV: {uploaded_prices.name}"

    absent = sorted(set(requested) - set(raw_prices.columns))
    if absent:
        if set(absent).intersection(pit_names):
            raise DataError(f"Point-in-time screening records reference stocks without prices: {', '.join(sorted(set(absent).intersection(pit_names)))}")
        if set(absent).intersection(TICKERS):
            raise DataError(f"Required ETFs missing from price data: {', '.join(absent)}")
        st.warning(f"Missing {len(absent)} custom tickers: {', '.join(absent)}. Custom basket needs complete adjusted price histories for all selected names.")
        build_custom = False
        holdings = None
        custom_names = []
    benchmark_prices = trim_incomplete_last_month(validate_universe_prices(raw_prices[list(TICKERS)]))
    benchmark_returns = monthly_returns(benchmark_prices)
    if len(benchmark_returns) < 24:
        raise DataError("At least 24 complete benchmark return months are needed.")
    benchmark_metrics = metric_table(benchmark_returns, annual_rf=annual_rf)
    try:
        all_stocks = list(dict.fromkeys(custom_names + pit_names))
        raw_prices = validate_universe_prices(raw_prices[list(TICKERS) + all_stocks])
    except DataError:
        if pit_names:
            raise
        if custom_names:
            st.warning("Custom stock prices do not share sufficient complete months. Displaying ETF benchmark research instead. For the custom study, upload a single CSV with complete adjusted prices for the full basket.")
            raw_prices = validate_universe_prices(raw_prices[list(TICKERS)])
            build_custom = False
            holdings = None
            custom_names = []
        else:
            raise
    raw_last = raw_prices.index[-1].date()
    prices = trim_incomplete_last_month(raw_prices)
    monthly_all = monthly_returns(prices)
    if len(monthly_all) < 24:
        raise DataError("At least 24 shared completed calendar-month returns are needed.")
    combined = monthly_all[list(TICKERS)].copy()
    weights = None
    optimization_note = ""
    if build_custom:
        stock_monthly = monthly_all[custom_names]
        if weight_method in ("Equal weight", "Issuer proportional (top basket only)"):
            weights = suggested_weights(holdings, weight_method)
        else:
            if max_weight < 1/len(custom_names)-1e-10:
                raise PortfolioError("Maximum position weight is too low for the selected number of stocks. Increase it or add holdings.")
            weights = optimization_weights(stock_monthly, objective=weight_method, max_weight=max_weight, annual_rf=annual_rf)
            optimization_note = f"**In-sample optimization alert:** {weight_method} uses the full visible history to choose weights. It must not be interpreted as out-of-sample strategy performance. Review the walk-forward analysis below."
        combined["Custom basket"] = portfolio_returns(stock_monthly, weights)
    pit_audit = None
    if pit_history is not None:
        pit_strategy, pit_audit = backtest_pit(monthly_all[pit_names], pit_history, min_holdings=5, max_age_days=65, weight_method=pit_weighting)
        combined = combined.loc[pit_strategy.index].copy()
        combined[pit_strategy.name] = pit_strategy
    common_start, common_end = combined.index[0].date(), combined.index[-1].date()
    metrics = metric_table(combined, annual_rf=annual_rf)
    diagnostics = benchmark_diagnostics(combined)
except (DataError, ScreeningError, PortfolioError, ValueError) as exc:
    st.error(f"Research input error: {exc}")
    st.caption("No fake prices or Shariah statuses are generated when a data source is unavailable. Verify your CSV or retry the issuer/vendor source.")
    st.stop()

st.caption(f"**Monthly observations:** {len(combined)} · **Common return window:** {common_start} through {common_end} · **Market data:** {source_description}")
if raw_last != prices.index[-1].date():
    st.caption(f"Excluded the unfinished final month (last downloaded date: {raw_last}).")
if build_custom:
    snapshot_dates = ", ".join(sorted(set(map(str, holdings["as_of"]))))
    st.caption(f"**Basket snapshot:** {snapshot_dates} · **Evidence:** {registry_source} · **Holdings:** {len(weights)} · **Rebalanced monthly without taxes/trading costs**")
if pit_history is not None:
    st.caption(f"**Historical-screen strategy:** {pit_history['as_of'].nunique()} dated full snapshots · {len(pit_names)} unique eligible tickers · strict no-future-screening check · 65-day evidence age cap")
if optimization_note:
    st.warning(optimization_note)

summary_top = st.columns(4)
summary_top[0].metric("Study period", f"{len(benchmark_returns)} months")
summary_top[1].metric("SPUS annualized", f"{benchmark_metrics.loc['SPUS', 'CAGR']:.2%}")
summary_top[2].metric("HLAL annualized", f"{benchmark_metrics.loc['HLAL', 'CAGR']:.2%}")
summary_top[3].metric("SPY annualized", f"{benchmark_metrics.loc['SPY', 'CAGR']:.2%}")

etf_tab, custom_tab, diagnostics_tab, scenario_tab, evidence_tab, report_tab = st.tabs([
    "Performance", "Portfolio builder", "Risk & validation",
    "Monte Carlo", "Shariah evidence", "Research report",
])

with etf_tab:
    st.subheader("Historical growth of $10,000")
    matched = False
    if len(combined.columns) > len(TICKERS):
        matched = st.toggle("Compare strategies over their shared window", value=False)
    display_returns = combined if matched else benchmark_returns
    display_metrics = metrics if matched else benchmark_metrics
    st.caption(f"{display_returns.index[0]:%b %Y} – {display_returns.index[-1]:%b %Y} · {len(display_returns)} monthly returns")
    growth = (1 + display_returns).cumprod() * 10_000
    starting_value = pd.DataFrame(10_000, columns=growth.columns, index=[growth.index[0] - pd.offsets.MonthEnd(1)])
    growth = pd.concat([starting_value, growth])
    fig = go.Figure()
    for name in growth.columns:
        fig.add_trace(go.Scatter(x=growth.index, y=growth[name], name=name, mode="lines", line=dict(color=COLORS.get(name), width=3 if name == "Custom basket" else 2), hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra>" + name + "</extra>"))
    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10, r=12, t=12, b=10), yaxis_title="Value ($)", hovermode="x unified", legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)
    if matched and build_custom:
        st.caption("The monthly-rebalanced basket illustrates what today’s holdings would have done historically. Earlier eligibility is unverified.")
    visible = display_metrics.style.format({"CAGR": "{:.2%}", "Annual volatility": "{:.2%}", "Sharpe": "{:.2f}", "Sortino": "{:.2f}", "Max monthly drawdown": "{:.2%}", "Total return": "{:.2%}"}, na_rep="—")
    st.dataframe(visible, use_container_width=True)
    st.caption("Max drawdown is measured using **month-end** values for every comparison series. Intramonth losses can be larger.")
    left, right = st.columns(2)
    left.download_button("Download observed adjusted prices", to_csv_bytes(prices if matched else benchmark_prices), file_name="observed_adjusted_prices.csv", mime="text/csv")
    right.download_button("Download performance metrics", display_metrics.to_csv().encode(), file_name="historical_metrics.csv", mime="text/csv")

with custom_tab:
    if not build_custom:
        st.warning("Enable 'Include custom holdings basket' in the sidebar, and provide adjusted-price history, to build the stock portfolio.")
    else:
        st.subheader(f"{len(custom_names)}-stock research basket · {weight_method}")
        c1, c2, c3 = st.columns(3)
        cons = concentration(weights)
        c1.metric("Effective holdings", f"{cons['Effective holdings']:.1f}")
        c2.metric("Largest position", f"{cons['Largest position']:.1%}")
        c3.metric("Top-five concentration", f"{cons['Top 5 weight']:.1%}")
        c_left, c_right = st.columns([1.2, 1])
        with c_left:
            wplot = weights.sort_values(ascending=False)
            bar = px.bar(x=wplot.index, y=wplot.values * 100, labels={"x": "Ticker", "y": "Portfolio weight (%)"}, template="plotly_dark")
            bar.update_traces(marker_color="#E7B86C")
            bar.update_layout(height=400, margin=dict(l=4, r=4, t=10, b=4))
            st.plotly_chart(bar, use_container_width=True)
        with c_right:
            sectors = sector_allocation(weights, holdings)
            pie = px.pie(names=sectors.index, values=sectors.values, hole=.55, template="plotly_dark")
            pie.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0), legend=dict(font=dict(size=10)))
            st.plotly_chart(pie, use_container_width=True)
        table = holdings.set_index("ticker")[["company", "sector", "issuer_weight_pct", "as_of", "evidence_type", "source_url"]].copy()
        table.insert(0, "model_weight_pct", weights.reindex(table.index).values * 100)
        st.dataframe(table, use_container_width=True)
        st.caption("Sector categories are user-editable broad research groupings, not licensed GICS classifications. Issuer weights refer to the whole ETF on the snapshot date; proportional basket weights are rescaled to the selected subset.")
        sector_monthlies = sector_return_attribution(stock_monthly, weights, holdings)
        sector_arithmetic = (sector_monthlies.mean() * 12 * 100).sort_values(ascending=False)
        st.markdown("#### Annualized arithmetic return contribution by sector")
        st.bar_chart(sector_arithmetic, x_label="Broad sector grouping", y_label="Annualized contribution (percentage points)")
        st.caption("These additive sector contributions describe this *chosen basket's* monthly returns, not the causal effect of Islamic screening. Compounding means they do not sum exactly to geometric CAGR.")
        d1, d2 = st.columns(2)
        d1.download_button("Export portfolio weights", weights.to_csv(header=True).encode(), file_name="basket_weights.csv", mime="text/csv")
        d2.download_button("Export dated evidence", holdings.to_csv(index=False).encode(), file_name="basket_screening_evidence.csv", mime="text/csv")
        st.info("**Avoid look-ahead claims:** Even walk-forward weights do not solve the bias from selecting a 2026 constituent universe. A true historical Shariah implementation requires screening records from each historical rebalance date.")

with diagnostics_tab:
    st.subheader("Risk, benchmark sensitivity and robustness")
    styled = diagnostics.style.format({"Beta vs SPY": "{:.2f}", "Correlation vs SPY": "{:.2f}", "Tracking error (annual)": "{:.2%}", "Annualized arithmetic active return": "{:+.2%}"}, na_rep="—")
    st.dataframe(styled, use_container_width=True)
    l, r = st.columns([1.2, 1])
    with l:
        horizon = st.select_slider("Rolling annualized return horizon", [12, 24, 36, 60], value=12)
        if len(combined) >= horizon:
            rolling = rolling_annualized(combined, horizon) * 100
            roll = go.Figure()
            for name in rolling.columns:
                roll.add_trace(go.Scatter(x=rolling.index, y=rolling[name], name=name, line=dict(color=COLORS.get(name))))
            roll.update_layout(template="plotly_dark", height=360, yaxis_title="Rolling annualized (%)", margin=dict(l=4, r=4, t=8, b=4), legend=dict(orientation="h"))
            st.plotly_chart(roll, use_container_width=True)
        else:
            st.caption(f"Need {horizon} months for the selected rolling window.")
    with r:
        corr = combined.corr()
        heat = px.imshow(corr, zmin=-1, zmax=1, color_continuous_scale="RdBu", text_auto=".2f", aspect="auto")
        heat.update_layout(template="plotly_dark", height=360, margin=dict(l=4, r=4, t=8, b=4), coloraxis_showscale=False)
        st.plotly_chart(heat, use_container_width=True)
    st.markdown("#### Worst SPY calendar months in the available sample")
    worst = worst_benchmark_months(combined)
    st.dataframe(worst.style.format("{:+.2%}"), use_container_width=True)
    if build_custom and len(stock_monthly) >= 37:
        st.markdown("#### Walk-forward weighting validation (no future *returns* in fitting)")
        obj = st.selectbox("Test objective", ["Minimum variance", "Maximum Sharpe"], key="wf_obj")
        train_len = st.select_slider("Training window", [24, 36, 48, 60], value=36)
        if len(stock_monthly) <= train_len:
            st.caption("Not enough observations for this train/test split.")
        else:
            try:
                effective_cap = max(max_weight, 1 / len(custom_names) + .005)
                wf, allocations = walk_forward(stock_monthly, objective=obj, train_months=train_len, rebalance_months=6, max_weight=effective_cap, annual_rf=annual_rf)
                common_wf = wf.index.intersection(combined.index)
                if len(common_wf) == 0:
                    raise PortfolioError("Walk-forward and shared benchmark windows do not overlap.")
                equal_w = pd.Series(1/len(stock_monthly.columns), index=stock_monthly.columns)
                equal_oos = portfolio_returns(stock_monthly.loc[common_wf], equal_w)
                compare = combined.loc[common_wf, list(TICKERS)].copy()
                compare["Equal-weight custom (OOS period)"] = equal_oos
                compare[wf.name] = wf.loc[common_wf]
                if len(compare) >= 24:
                    st.dataframe(metric_table(compare).style.format({"CAGR": "{:.2%}", "Annual volatility": "{:.2%}", "Sharpe": "{:.2f}", "Sortino": "{:.2f}", "Max monthly drawdown": "{:.2%}", "Total return": "{:.2%}"}, na_rep="—"), use_container_width=True)
                else:
                    st.caption(f"Only {len(compare)} out-of-sample months; require 24 or more before annualized diagnostic metrics are displayed.")
                st.download_button("Download walk-forward allocation history", allocations.to_csv().encode(), file_name="walk_forward_weights.csv", mime="text/csv")
                st.caption(f"Weights estimated on previous {train_len} months, re-estimated every 6 months. **The current-dated stock universe remains hindsight-selected**, so this is a test of weighting discipline, not of a historical Shariah eligibility strategy.")
            except PortfolioError as exc:
                st.warning(f"Walk-forward analysis unavailable: {exc}")
    st.download_button("Download diagnostic table", diagnostics.to_csv().encode(), file_name="benchmark_diagnostics.csv", mime="text/csv")

with scenario_tab:
    st.subheader("Paired historical-block Monte Carlo scenarios")
    st.caption("These frequencies are conditional on the available historical monthly returns, not calibrated predictions. The same historical market months drive every compared portfolio.")
    if initial == 0 and monthly_deposit == 0:
        st.warning("Set nonzero initial capital or monthly deposits to simulate.")
        scenario = None
    else:
        try:
            with st.spinner(f"Simulating {n_sims:,} paired investment paths..."):
                sim = moving_block_bootstrap(combined, years, n_sims, float(initial), float(monthly_deposit), min(block, len(combined)), int(seed))
                scenario = simulation_summary(sim)
            m1, m2, m3 = st.columns(3)
            m1.metric("Starting capital", f"${initial:,.0f}")
            m2.metric("Total deposits + initial", f"${sim.contributions:,.0f}")
            m3.metric("Simulated horizon", f"{years} years")
            pretty = scenario.copy()
            for key in ["10th percentile ($)", "Median ($)", "90th percentile ($)"]:
                pretty[key] = pretty[key].map(lambda x: f"${x:,.0f}")
            for key in ["Below contributions (%)", "30%+ NAV drawdown (%)", "Beats SPY (%)"]:
                pretty[key] = pretty[key].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
            st.dataframe(pretty, use_container_width=True)
            select = st.selectbox("Visualize scenario fan", sim.tickers, index=1 if len(sim.tickers)>1 else 0, format_func=lambda s: DISPLAY.get(s,s))
            fan = fan_percentiles(sim, select)
            f = go.Figure()
            f.add_trace(go.Scatter(x=fan.Month/12, y=fan.P90, line=dict(width=0), name="P90"))
            f.add_trace(go.Scatter(x=fan.Month/12, y=fan.P10, fill="tonexty", line=dict(width=0), fillcolor="rgba(83, 213, 176, .18)", name="P10–P90", hovertemplate="$%{y:,.0f}<extra></extra>"))
            f.add_trace(go.Scatter(x=fan.Month/12, y=fan.P50, line=dict(color=COLORS.get(select, "#E7B86C"), width=3), name="Median", hovertemplate="$%{y:,.0f}<extra></extra>"))
            f.update_layout(template="plotly_dark", height=410, xaxis_title="Future simulation years", yaxis_title="Portfolio value ($)", margin=dict(l=8,r=8,t=12,b=8))
            st.plotly_chart(f, use_container_width=True)
            st.download_button("Download Monte Carlo output", scenario.to_csv().encode(), file_name="monte_carlo_summary.csv", mime="text/csv")
            st.caption("Month-end contributions are applied after monthly returns. The 30% drawdown statistic uses **return-only NAV**, so deposits do not conceal losses. Custom baskets use retrospective inputs and are subject to historical-universe bias.")
        except ValueError as exc:
            scenario = None
            st.error(str(exc))

with evidence_tab:
    st.subheader("Shariah methodology, evidence and purification")
    st.markdown("""
    **What is actually screened?** Fund providers typically assess prohibited activities and accounting ratios. The precise denominators and rebalancing rules differ. Stock eligibility can change. We therefore distinguish an **ETF-holding observation** from an **independent stock-level screening conclusion**.

    - **SPUS** follows the S&P 500 Shariah Industry Exclusions approach. [Issuer](https://www.sp-funds.com/SPUS/) · [Index provider](https://www.spglobal.com/spdji/en/indices/equity/sp-500-shariah-industry-exclusions-index/)
    - **HLAL** uses a FTSE USA Shariah index methodology. [Issuer and purification documents](https://www.wahed.com/hlal) · [SEC description of screening criteria](https://www.sec.gov/Archives/edgar/data/1683471/000089418926026510/R4.htm)
    - **SPY** is **not** a halal benchmark; it is a conventional comparator for performance and risk.
    """)
    if holdings is not None:
        st.dataframe(holdings, use_container_width=True)
        st.caption("'ETF_HOLDING' means the stock was reported among a screened fund's holdings on the displayed date. It does **not** mean that this lab independently certified the individual security.")
    if pit_history is not None and pit_audit is not None:
        st.markdown("#### Point-in-time screening audit")
        st.dataframe(pit_audit, use_container_width=True)
        st.download_button("Download historical screening audit", pit_audit.to_csv().encode(), file_name="point_in_time_audit.csv", mime="text/csv")
        st.caption("The software enforces prior-month snapshot availability and a 65-day maximum age; it does not independently verify that uploaded provider decisions were correct.")
    st.markdown("#### Historical screening-history input")
    st.download_button("Blank historical-screening CSV", b"as_of,published_at,ticker,eligible,source_name,source_url,weight_hint\n", file_name="historical_screening_template.csv", mime="text/csv")
    st.caption("Each as_of date must include the **complete** eligible/excluded universe for that screening event. Include the actual publication date in published_at. Legacy files without that column assume same-day publication. Monthly results use only records published **before** that return month. Include historical delisted securities to reduce survivorship bias.")
    with st.expander("Evidence CSV format and how to use your own screening provider"):
        st.code("ticker,company,sector,issuer_weight_pct,as_of,evidence_type,source_name,source_url\nAAPL,Apple Inc,Information Technology,4.0,2026-11-24,ETF_HOLDING,SP Funds,https://www.sp-funds.com/SPUS/", language="csv")
        st.caption("Example row illustrates file structure; it is not an additional independent screening claim. For CUSTOM_SCREENED rows provide the provider's dated assessment and verifiable link; the app validates format only, not religious correctness.")
    st.markdown("#### Dividend purification worksheet")
    st.caption("Enter actual shares, distribution-per-share and an externally established purification fraction for **each dividend**. The app never guesses purification rates.")
    template = b"ticker,shares,dividend_per_share,purification_fraction\n"
    st.download_button("Download blank purification CSV", template, file_name="purification_input_template.csv", mime="text/csv")
    purge_upload = st.file_uploader("Upload dividend/purification CSV", type="csv", key="purification")
    if purge_upload is not None:
        try:
            dividends = pd.read_csv(BytesIO(purge_upload.getvalue()))
            worksheet = purification_worksheet(dividends)
            st.dataframe(worksheet, use_container_width=True)
            st.metric("Calculated purification amount", f"${worksheet['purification_amount'].sum():,.2f}")
            st.download_button("Export calculated worksheet", worksheet.to_csv(index=False).encode(), file_name="purification_worksheet.csv", mime="text/csv")
        except (PortfolioError, ValueError) as exc:
            st.error(f"Purification input error: {exc}")

with report_tab:
    st.subheader("Reproducible equity research memorandum")
    try:
        assumptions = {
            "Investment horizon": f"{years} years",
            "Initial contribution": f"${initial:,}",
            "Monthly contribution": f"${monthly_deposit:,}",
            "Monte Carlo scenarios": f"{n_sims:,}",
            "Historical block length": f"{block} months",
            "Random seed": str(seed),
            "Annual risk-free assumption": f"{annual_rf:.2%}",
            "Portfolio construction": weight_method if build_custom else "ETF-only",
            "Screening evidence type": registry_source if build_custom else "No custom stocks",
            "Point-in-time screening history": f"User-provided {pit_history['as_of'].nunique()} snapshots; 65-day maximum evidence age; portfolio weights {pit_weighting}" if pit_history is not None else "Not supplied (no PIT certification claim)",
        }
        report = build_report(
            combined, source_description, holdings=holdings if build_custom else None,
            weights=weights, scenario=scenario if "scenario" in locals() else None,
            assumptions=assumptions, annual_rf=annual_rf,
        )
        st.download_button("Download complete research note (.md)", report.encode(), file_name=f"shariah_research_note_{date.today():%Y%m%d}.md", mime="text/markdown")
        st.markdown(report)
    except (PortfolioError, ValueError) as exc:
        st.error(f"Report generation error: {exc}")

st.divider()
st.caption("Educational research only. Neither the performance comparison nor the ETF holdings registry is an independent Shariah certification or an investment recommendation. Historical and hypothetical results can differ dramatically from future outcomes.")

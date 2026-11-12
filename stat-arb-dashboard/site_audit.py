#!/usr/bin/env python3
"""Offline structural and statistical-consistency checks for PAIR//LAB."""
from __future__ import annotations
import json, math, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
data = json.loads((HERE / "data" / "screen.json").read_text(encoding="utf-8"))
site = (HERE / "index.html").read_text(encoding="utf-8")
home = (ROOT / "index.html").read_text(encoding="utf-8")
pairs = data["pairs"]
assert data["schema_version"] == 1, "Unexpected data format"
assert data["as_of"] == "2026-11-11", "Snapshot date changed unexpectedly"
assert len(pairs) == 18, "Expected precisely 18 tested pair hypotheses"
assert len({p["pair"] for p in pairs}) == len(pairs), "Duplicate pair"
assert all(p["pair"] == p["a"] + "/" + p["b"] for p in pairs)
assert all(p["a"] != p["b"] for p in pairs)

for p in pairs:
    for k in ("p", "q", "correlation", "z", "beta", "beta_drift_pct"):
        assert isinstance(p[k], (int, float)) and math.isfinite(p[k]), (p["pair"], k)
    assert 0 <= p["p"] <= 1 and 0 <= p["q"] <= 1
    assert -1 <= p["correlation"] <= 1
    assert p["gates"]["coint"] == (p["p"] < .05)
    assert p["gates"]["corr"] == (p["correlation"] > .75)
    assert p["gates"]["z"] == (abs(p["z"]) >= 2)
    assert p["gates"]["multiple_testing"] == (p["q"] < .05)

pvalues = [p["p"] for p in pairs]
order = sorted(range(len(pairs)), key=lambda i: pvalues[i])
fdr = [0.] * len(pairs)
q = 1.
for rank in range(len(pairs)-1, -1, -1):
    idx = order[rank]
    q = min(q, len(pairs) * pvalues[idx] / (rank + 1))
    fdr[idx] = q
for p, expected in zip(pairs, fdr):
    assert abs(p["q"] - expected) <= .015, (p["pair"], p["q"], expected)

assert sum(p["p"] < .05 for p in pairs) == 2
assert sum(p["q"] < .05 for p in pairs) == 0
assert sum(p["p"] < .05 and p["correlation"] > .75 and abs(p["z"]) >= 2 for p in pairs) == 0
assert 'fetch("./data/screen.json"' in site
assert 'id="table-body"' in site and 'id="scatter"' in site
assert 'id="export"' in site and 'id="pair-detail"' in site
assert 'href="stat-arb-dashboard/index.html"' in home
assert "PROVISIONAL DATA" in site and "NO VERIFIED TRADE SIGNALS" in site
assert "<script>" in site and "</script>" in site
assert "github-pages" not in data.get("source", ""), "No misleading data origin"

for tag in ("section", "div", "header", "footer", "main", "svg", "table", "tbody", "thead"):
    assert len(re.findall(r"<" + tag + r"(?:\s|>)", site)) == len(re.findall(r"</" + tag + r">", site)), tag


# Historical-price visualizer integrity: the displayed data must reproduce the
# actual trailing 252-session regression and latest 60-residual Z-scores.
import statistics

chart_js = (HERE / "charts.js").read_text(encoding="utf-8")
chart_css = (HERE / "charts.css").read_text(encoding="utf-8")
part_a = json.loads((HERE / "data" / "prices-1.json").read_text(encoding="utf-8"))
part_b = json.loads((HERE / "data" / "prices-2.json").read_text(encoding="utf-8"))
assert part_a["schema_version"] == part_b["schema_version"] == 1
assert part_a["as_of"] == part_b["as_of"] == data["as_of"]
assert part_a["dates"] == part_b["dates"], "Price shard calendars don't match"
chart_dates = part_a["dates"]
assert len(chart_dates) >= 500
assert chart_dates == sorted(set(chart_dates))
assert chart_dates[-1] == data["as_of"]
series = {**part_a["series"], **part_b["series"]}
assert len(series) >= 20
assert all(len(v) == len(chart_dates) for v in series.values())
assert all(all(x is None or (isinstance(x,(int,float)) and math.isfinite(x) and x > 0)
               for x in v) for v in series.values())
assert all(k in site for k in ('id="trade-visualizer"', 'id="price-evolution"',
            'id="spread-evolution"', 'id="chart-pair"', 'id="learn"'))
assert 'src="charts.js"' in site and 'href="charts.css"' in site
assert "rolling" in chart_js.lower() and "Math.log" in chart_js
assert "NOT executed trades" in site or "not executed trades" in site
assert len(chart_css) > 1000
max_z_error = 0.
max_beta_error = 0.
max_corr_error = 0.
for item in pairs:
    a = series[item["a"]]
    b = series[item["b"]]
    aligned = [(u, v) for u, v in zip(a, b) if u is not None and v is not None]
    assert len(aligned) >= 320, item["pair"]
    formation = aligned[-253:-1]
    x = [math.log(t[1]) for t in formation]
    y = [math.log(t[0]) for t in formation]
    mx, my = statistics.mean(x), statistics.mean(y)
    beta = sum((u-mx)*(v-my) for u,v in zip(x,y)) / sum((u-mx)**2 for u in x)
    alpha = my - beta * mx
    e = [v-alpha-beta*u for u,v in zip(x,y)]
    z = (math.log(aligned[-1][0])-alpha-beta*math.log(aligned[-1][1])
         - statistics.mean(e[-60:])) / statistics.stdev(e[-60:])
    return_a = [y[j] - y[j-1] for j in range(1,len(y))][-90:]
    return_b = [x[j] - x[j-1] for j in range(1,len(x))][-90:]
    ar, br = statistics.mean(return_a), statistics.mean(return_b)
    corr = (sum((u-ar)*(v-br) for u,v in zip(return_a,return_b)) /
            (sum((u-ar)**2 for u in return_a)*sum((v-br)**2 for v in return_b))**0.5)
    max_z_error = max(max_z_error, abs(z-item["z"]))
    max_beta_error = max(max_beta_error, abs(beta-item["beta"]))
    max_corr_error = max(max_corr_error, abs(corr-item["correlation"]))
    assert abs(z-item["z"]) < 0.025, (item["pair"],z,item["z"])
    assert abs(beta-item["beta"]) < 0.01, (item["pair"],beta,item["beta"])
    assert abs(corr-item["correlation"]) < 0.005, (item["pair"],corr,item["correlation"])

print("PASS: all 20 historical price series aligned, charts are wired,")
print("      and 18 chart-derived closing Z-scores, hedge ratios, correlations match audited snapshot.")
print("      max |Z delta|=", round(max_z_error,6),
      "; max |beta delta|=", round(max_beta_error,6),
      "; max |correlation delta|=", round(max_corr_error,6))


# Strategy workspace structural audit.
from html.parser import HTMLParser

class _IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id":
                self.ids.append(value)

parser = _IdParser()
parser.feed(site)
assert len(parser.ids) == len(set(parser.ids)), "Duplicate HTML element IDs"
expected_plan_ids = [
    "plan-builder","plan-pair","plan-entry","plan-exit","plan-stop","plan-hold",
    "plan-gross","plan-fees","plan-borrow","plan-equity-chart","plan-event",
    "plan-pnl-gross","plan-net","plan-days","plan-result","plan-verdict",
    "plan-download","plan-condition","plan-direction","plan-exit-text","plan-reject"
]
assert all(key in parser.ids for key in expected_plan_ids)
assert "id=\"plan-builder\"" in site and "NO CURRENT TRADE" in site
assert 'href="plans.css"' in site and 'src="plans.js"' in site
script = (HERE / "plans.js").read_text(encoding="utf-8")
style = (HERE / "plans.css").read_text(encoding="utf-8")
assert len(script) > 8000 and len(style) > 1000
assert all(token in script for token in [
    "function findCrossings(","function paperReplay(","function exportPlan(",
    "const entry=trigger+1","const sample=arr.slice(t-252,t)",
    "Math.abs(z)>=threshold","borrow", "fees",
    "window.addEventListener(\"pairlab:selected\""
])
assert '$("plan-gross").textContent' not in script, "Notional input must remain separate from P/L output"
assert '$("plan-pnl-gross").textContent' in script
assert len(re.findall(r'data-proposal-pair="[A-Z]+/[A-Z]+"', site)) >= 3
print("PASS: trade-plan controls, unique DOM IDs, no-lookahead formation,")
print("      next-close paper fills, notional/P&L separation and no-trade disclosures.")

print("PASS: site structure, internal links, screen schema, 18 unique hypotheses,")
print("      gate integrity, BH FDR recalculation, zero alerts, and provisional disclosures.")

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

print("PASS: site structure, internal links, screen schema, 18 unique hypotheses,")
print("      gate integrity, BH FDR recalculation, zero alerts, and provisional disclosures.")

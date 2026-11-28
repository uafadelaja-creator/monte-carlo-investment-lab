"""Offline end-to-end export using EXPLICITLY SYNTHETIC TEST PRICES.

No synthetic fixtures are distributed as actual market history.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from scripts.run_research import create_outputs
from src.shariah_lab.screening import load_registry


def test_research_export_end_to_end(tmp_path):
    holdings = load_registry()
    tickers = ["SPY", "SPUS", "HLAL"] + holdings["ticker"].tolist()
    idx = pd.date_range("2020-01-02", "2025-12-31", freq="B")
    # These are purely mathematical test fixtures, never represented as market prices.
    x = np.arange(len(idx))
    frame = pd.DataFrame({t: 50 + i + (x + 1) * (0.005 + i * 0.00003) + 0.25 * np.sin(x / 25 + i) for i, t in enumerate(tickers)}, index=idx)
    output = tmp_path / "research"
    metadata = create_outputs(
        frame, output, registry=holdings, basket_size=20,
        paths=120, years=2, source="SYNTHETIC TEST FIXTURE - NOT ACTUAL PRICE DATA",
    )
    for file in (
        "research_report.md", "market_prices_adjusted.csv", "historical_metrics.csv",
        "simulation_summary.csv", "benchmark_diagnostics.csv", "monthly_return_series.csv",
        "basket_weights.csv", "basket_evidence.csv", "walk_forward_monthly_returns.csv",
        "walk_forward_allocations.csv", "study_metadata.json",
    ):
        assert (output / file).exists(), file
    assert metadata["tickers"][-1] == "Custom basket"
    assert metadata["current_holdings_lookahead_warning"] is True
    assert len(metadata["input_price_sha256"]) == 64
    report = (output / "research_report.md").read_text()
    assert "SYNTHETIC TEST FIXTURE - NOT ACTUAL PRICE DATA" in report
    assert "look-ahead bias" in report.lower()
    assert "November" not in report or "2026" in report


def test_research_export_etf_only(tmp_path):
    idx = pd.date_range("2021-01-04", "2024-12-31", freq="B")
    frame = pd.DataFrame({"SPY": np.linspace(100, 130, len(idx)), "SPUS": np.linspace(100, 145, len(idx)), "HLAL": np.linspace(100, 140, len(idx))}, index=idx)
    info = create_outputs(frame, tmp_path, registry=None, paths=100, years=1, source="SYNTHETIC FIXTURE - TEST ONLY")
    assert info["current_holdings_lookahead_warning"] is False
    assert "Custom basket" not in info["tickers"]
    assert not (tmp_path / "basket_weights.csv").exists()

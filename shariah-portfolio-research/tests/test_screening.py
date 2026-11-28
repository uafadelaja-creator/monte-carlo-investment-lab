from __future__ import annotations

import io
import pandas as pd
import pytest

from src.shariah_lab.screening import (
    ScreeningError, load_registry, parse_spus_holdings, suggested_weights,
    validate_registry,
)


def test_snapshot_provenance_and_weight_fields():
    holdings = load_registry()
    assert len(holdings) == 20
    assert holdings["ticker"].iloc[0] == "AAPL"
    assert holdings["ticker"].iloc[-1] == "LRCX"
    assert set(holdings["evidence_type"]) == {"ETF_HOLDING"}
    assert {str(d) for d in holdings["as_of"]} == {"2026-11-24"}
    assert (holdings["issuer_weight_pct"] > 0).all()


def test_equal_weights():
    holdings = load_registry()
    w = suggested_weights(holdings, "Equal weight")
    assert len(w) == 20
    assert (w == 0.05).all()


def test_issuer_proportional_weights():
    holdings = load_registry()
    w = suggested_weights(holdings, "Issuer proportional (top basket only)")
    assert abs(w.sum() - 1.0) < 1e-10
    assert w.loc["AAPL"] > w.loc["NVDA"]
    assert w.loc["NVDA"] > w.loc["MSFT"]


def test_invalid_weights_raise():
    holdings = load_registry()
    holdings.loc[0, "issuer_weight_pct"] = -2
    with pytest.raises(ScreeningError, match="nonnegative"):
        validate_registry(holdings)


def test_duplicate_tickers_rejected():
    holdings = load_registry()
    holdings.loc[1, "ticker"] = holdings.loc[0, "ticker"]
    with pytest.raises(ScreeningError, match="only once"):
        validate_registry(holdings)


def test_missing_provenance_rejected():
    holdings = load_registry().drop(columns="source_url")
    with pytest.raises(ScreeningError, match="Missing"):
        validate_registry(holdings)


def test_unsupported_certification_labels_rejected():
    holdings = load_registry()
    holdings.loc[0, "evidence_type"] = "CERTIFIED_PERMANENTLY"
    with pytest.raises(ScreeningError, match="ETF_HOLDING"):
        validate_registry(holdings)


def test_parse_issuer_rows():
    raw = b"Date,Account,StockTicker,SecurityName,Weightings\n11/24/2026,SPUS,AAPL,Apple Inc,14.18\n11/24/2026,SPUS,MSFT,Microsoft Corp,10.18\n11/24/2026,SPUS,CASH,USD Cash,0\n"
    result = parse_spus_holdings(raw, limit=3)
    assert result["ticker"].tolist() == ["AAPL", "MSFT"]
    assert str(result.iloc[0]["as_of"]) == "2026-11-24"
    assert "CERTIFIED" not in result["evidence_type"].tolist()


def test_parse_issuer_html_is_error():
    with pytest.raises(ScreeningError):
        parse_spus_holdings("<html>not a csv</html>")


def test_future_screening_date_rejected():
    holdings = load_registry()
    holdings.loc[0, "as_of"] = "2099-01-01"
    with pytest.raises(ScreeningError, match="future"):
        validate_registry(holdings)

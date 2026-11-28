"""Dated constituents/evidence registry. Fund inclusion != independent certification."""
from __future__ import annotations

from datetime import date
from io import BytesIO, StringIO
from pathlib import Path
import re

import numpy as np
import pandas as pd

SPUS_HOLDINGS_URL = "https://www.sp-funds.com/wp-content/uploads/data/TidalFG_Holdings_SPUS.csv"
SPUS_ISSUER_PAGE = "https://www.sp-funds.com/SPUS/"
DEFAULT_HOLDINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "spus_holdings_2026-11-24.csv"
REQUIRED_FIELDS = (
    "ticker", "company", "sector", "issuer_weight_pct", "as_of",
    "evidence_type", "source_name", "source_url",
)
EVIDENCE_TYPES = {"ETF_HOLDING", "CUSTOM_SCREENED"}


class ScreeningError(ValueError):
    pass


def validate_registry(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED_FIELDS) - set(frame.columns)
    if missing:
        raise ScreeningError(f"Missing screening/holding fields: {', '.join(sorted(missing))}")
    out = frame.loc[:, list(REQUIRED_FIELDS)].copy()
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    if out["ticker"].duplicated().any():
        raise ScreeningError("A ticker may occur only once in the current snapshot.")
    if not out["ticker"].map(lambda s: bool(re.fullmatch(r"[A-Z]{1,6}(?:[-.][A-Z])?", s))).all():
        raise ScreeningError("Invalid stock ticker format.")
    for col in ("company", "sector", "source_name", "source_url"):
        out[col] = out[col].astype(str).str.strip()
        if out[col].isin(["", "nan", "None"]).any():
            raise ScreeningError(f"Every row requires {col}.")
    if not out["source_url"].str.match(r"^https://", case=False).all():
        raise ScreeningError("Evidence links must be HTTPS URLs.")
    out["evidence_type"] = out["evidence_type"].astype(str).str.upper().str.strip()
    if not set(out["evidence_type"]).issubset(EVIDENCE_TYPES):
        raise ScreeningError("evidence_type must be ETF_HOLDING or CUSTOM_SCREENED.")
    out["issuer_weight_pct"] = pd.to_numeric(out["issuer_weight_pct"], errors="coerce")
    if out["issuer_weight_pct"].isna().any() or (out["issuer_weight_pct"] < 0).any():
        raise ScreeningError("Weights must be nonnegative numeric percentages.")
    try:
        out["as_of"] = pd.to_datetime(out["as_of"], errors="raise").dt.date
    except Exception as exc:
        raise ScreeningError("as_of dates must use YYYY-MM-DD.") from exc
    if out["as_of"].isna().any() or any(d > date.today() for d in out["as_of"]):
        raise ScreeningError("Snapshot dates cannot be absent or in the future.")
    if len(out) < 2:
        raise ScreeningError("At least two holdings are needed.")
    return out.reset_index(drop=True)


def load_registry(contents: bytes | str | None = None) -> pd.DataFrame:
    if contents is None:
        return validate_registry(pd.read_csv(DEFAULT_HOLDINGS_FILE))
    if isinstance(contents, bytes):
        frame = pd.read_csv(BytesIO(contents))
    elif "\n" not in contents and Path(contents).is_file():
        frame = pd.read_csv(contents)
    else:
        frame = pd.read_csv(StringIO(contents))
    return validate_registry(frame)


def parse_spus_holdings(raw: bytes | str, limit: int = 25) -> pd.DataFrame:
    """Parse the issuer's live holdings CSV, without making stock-level approval claims.

    A live feed supplies tickers and weights; sector labels are deliberately
    labelled 'Not classified' until a documented sector mapping is attached.
    """
    try:
        src = BytesIO(raw) if isinstance(raw, bytes) else StringIO(raw)
        data = pd.read_csv(src, on_bad_lines="skip")
        needed = {"Date", "StockTicker", "SecurityName", "Weightings"}
        if not needed.issubset(data.columns):
            raise ScreeningError("Issuer CSV has a different schema than expected.")
        data = data.loc[:, list(needed)].rename(
            columns={"Date": "as_of", "StockTicker": "ticker", "SecurityName": "company", "Weightings": "issuer_weight_pct"}
        )
        data["issuer_weight_pct"] = pd.to_numeric(data["issuer_weight_pct"].astype(str).str.rstrip("%"), errors="coerce")
        data["ticker"] = data["ticker"].astype(str).str.upper().str.strip()
        data = data.dropna(subset=["issuer_weight_pct", "as_of"])
        data = data[data["issuer_weight_pct"] > 0]
        data = data[data["ticker"].str.fullmatch(r"[A-Z]{1,6}(?:[-.][A-Z])?", na=False)]
        # SP Funds' published Weightings column uses percentage units, e.g. 14.18.
        # Some data vendors encode percentage as fractions; detect rather than guess.
        if data["issuer_weight_pct"].max() < 1.0 and data["issuer_weight_pct"].sum() <= 1.25:
            data["issuer_weight_pct"] *= 100.0
        data = data.sort_values("issuer_weight_pct", ascending=False).drop_duplicates("ticker").head(limit)
        data["sector"] = "Not classified"
        data["evidence_type"] = "ETF_HOLDING"
        data["source_name"] = "SP Funds official SPUS daily holdings"
        data["source_url"] = SPUS_ISSUER_PAGE
        return validate_registry(data)
    except ScreeningError:
        raise
    except Exception as exc:
        raise ScreeningError("Unable to parse SP Funds holdings CSV.") from exc


def fetch_live_spus_holdings(limit: int = 25) -> pd.DataFrame:
    """Fetch official holdings when internet is available; never use invented fallback."""
    import requests
    try:
        response = requests.get(SPUS_HOLDINGS_URL, timeout=20, headers={"User-Agent": "ShariahPortfolioResearchLab/1.0 research"})
        response.raise_for_status()
        return parse_spus_holdings(response.content, limit)
    except ScreeningError:
        raise
    except Exception as exc:
        raise ScreeningError("Official holdings download unavailable; use dated bundled snapshot or upload an issuer CSV.") from exc


def suggested_weights(registry: pd.DataFrame, style: str) -> pd.Series:
    """Return long-only weights summing to one, indexed by ticker."""
    frame = validate_registry(registry)
    if style == "Equal weight":
        w = np.ones(len(frame), dtype=float)
    elif style == "Issuer proportional (top basket only)":
        w = frame["issuer_weight_pct"].to_numpy(dtype=float)
    else:
        raise ScreeningError("Unknown weighting method.")
    if w.sum() <= 0:
        raise ScreeningError("Weights cannot all be zero.")
    return pd.Series(w / w.sum(), index=frame["ticker"].tolist(), name="Weight")

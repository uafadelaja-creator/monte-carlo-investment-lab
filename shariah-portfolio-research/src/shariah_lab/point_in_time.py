"""Point-in-time (PIT) backtest from user-provided dated FULL screening snapshots.

NO snapshot history is invented. A month's holdings must have been visible
prior to that month; stale or insufficient snapshots stop the backtest.
Religious status in uploaded data is not independently verified by this lab.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO, StringIO

import numpy as np
import pandas as pd

from .portfolio import PortfolioError, clean_return_matrix

REQUIRED = ("as_of", "ticker", "eligible", "source_name", "source_url", "weight_hint")


class PITError(PortfolioError):
    pass


def load_pit_history(content: bytes | str) -> pd.DataFrame:
    """Read an evidence history: each as_of is a *complete* screening snapshot.

    eligible accepts yes/no, true/false, 1/0. Each distinct snapshot must be a
    self-contained eligible stock universe; omissions mean *not held*.
    """
    try:
        raw = pd.read_csv(BytesIO(content) if isinstance(content, bytes) else StringIO(content))
    except Exception as exc:
        raise PITError("Unable to read point-in-time screening CSV.") from exc
    missing = set(REQUIRED) - set(raw.columns)
    if missing:
        raise PITError("Missing PIT columns: " + ", ".join(sorted(missing)))
    frame = raw[list(REQUIRED)].copy()
    try:
        frame["as_of"] = pd.to_datetime(frame["as_of"], errors="raise").dt.normalize()
    except Exception as exc:
        raise PITError("Invalid as_of dates in PIT history.") from exc
    if frame.as_of.isna().any() or frame.as_of.max().date() > date.today():
        raise PITError("PIT history cannot contain future or missing as-of dates.")
    assumed_publication = "published_at" not in raw
    try:
        frame["published_at"] = (
            frame.as_of if assumed_publication
            else pd.to_datetime(raw["published_at"], errors="raise").dt.normalize()
        )
        published = frame.published_at
        if published.isna().any() or (published < frame.as_of).any() or (published > pd.Timestamp(date.today())).any():
            raise ValueError
        if frame.groupby("as_of").published_at.nunique().gt(1).any():
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise PITError("Use one valid publication date per snapshot, on or after its as-of date.") from exc
    frame.attrs["assumed_publication_date"] = assumed_publication
    frame["ticker"] = frame["ticker"].astype(str).str.strip().str.upper()
    if frame.duplicated(["as_of", "ticker"]).any():
        raise PITError("Each ticker may appear only once per complete snapshot.")
    choices = {"true": True, "yes": True, "1": True, "false": False, "no": False, "0": False}
    status = frame["eligible"].astype(str).str.lower().str.strip().map(choices)
    if status.isna().any():
        raise PITError("eligible must be true/false, yes/no or 1/0.")
    frame["eligible"] = status.astype(bool)
    frame["weight_hint"] = pd.to_numeric(frame["weight_hint"], errors="coerce")
    if frame.weight_hint.isna().any() or (frame.weight_hint < 0).any():
        raise PITError("PIT weight_hint must be a nonnegative number.")
    frame["source_url"] = frame["source_url"].astype(str).str.strip()
    frame["source_name"] = frame["source_name"].astype(str).str.strip()
    if (~frame.source_url.str.match(r"https://")).any() or frame.source_name.isin(["", "nan"]).any():
        raise PITError("Every historical screen must identify an HTTPS source and source_name.")
    return frame.sort_values(["as_of", "ticker"]).reset_index(drop=True)


def backtest_pit(
    monthly_stock_returns: pd.DataFrame,
    snapshots: pd.DataFrame,
    min_holdings: int = 5,
    max_age_days: int = 65,
    weight_method: str = "Equal weight",
) -> tuple[pd.Series, pd.DataFrame]:
    """Return only contiguous, retrospectively supported monthly strategy values.

    A month dated month-end t uses the LAST COMPLETE snapshot available before
    that calendar month began. No current month's decisions influence its return.
    Fail if evidence disappears after the first covered month.
    """
    monthly_stock_returns = clean_return_matrix(monthly_stock_returns, minimum=24)
    if not isinstance(monthly_stock_returns.index, pd.DatetimeIndex):
        raise PITError("PIT monthly returns must have a calendar DatetimeIndex.")
    if not 1 <= min_holdings <= 100 or max_age_days < 1:
        raise PITError("Invalid minimum holding count or evidence staleness limit.")
    if weight_method not in ("Equal weight", "Evidence proportional"):
        raise PITError("PIT weighting must be equal weight or evidence proportional.")
    if snapshots.empty or not set(REQUIRED).issubset(snapshots.columns):
        raise PITError("Invalid or empty PIT snapshot history.")
    publication = snapshots.get("published_at", snapshots.as_of)
    dates = sorted(set(zip(snapshots.as_of, publication)))
    monthly_values = []
    metadata = []
    started = False
    for month_end, r in monthly_stock_returns.iterrows():
        cutoff = pd.Timestamp(month_end).to_period("M").start_time - pd.Timedelta(days=1)
        valid = [(d, published) for d, published in dates if published <= cutoff and (cutoff - d).days <= max_age_days]
        if not valid:
            if started:
                raise PITError(f"Missing sufficiently recent historical screening evidence for return month {month_end:%Y-%m}.")
            continue
        last, published = valid[-1]
        eligible = snapshots[(snapshots.as_of == last) & (snapshots.eligible)]
        tickers = eligible.ticker.tolist()
        if len(tickers) < min_holdings:
            raise PITError(f"Only {len(tickers)} eligible names documented for {month_end:%Y-%m}, need {min_holdings}.")
        missing_prices = sorted(set(tickers) - set(r.index))
        if missing_prices:
            raise PITError(f"Historical prices missing for PIT holdings: {', '.join(missing_prices)}")
        w = np.ones(len(tickers)) if weight_method == "Equal weight" else eligible.weight_hint.to_numpy(dtype=float)
        if w.sum() <= 0:
            raise PITError("PIT evidence weights cannot all be zero.")
        w = w / w.sum()
        monthly_values.append((month_end, float(np.dot(r[tickers].to_numpy(dtype=float), w))))
        metadata.append({"return_month": month_end, "screen_as_of": last, "published_at": published, "holdings": len(tickers), "age_days": (cutoff - last).days})
        started = True
    if len(monthly_values) < 24:
        raise PITError("PIT evidence covers fewer than 24 complete monthly returns; no unsupported history will be fabricated.")
    strategy = pd.Series(dict(monthly_values), name="PIT screened strategy", dtype=float)
    strategy.index = pd.DatetimeIndex(strategy.index)
    return strategy, pd.DataFrame(metadata).set_index("return_month")

"""Historical ETF price ingestion and validation.

Prices are split- and dividend-adjusted ETF market prices, not raw closes.
"""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO, StringIO

import numpy as np
import pandas as pd

TICKERS = ("SPY", "SPUS", "HLAL")
MIN_MONTHS = 24


class DataError(ValueError):
    """A helpful, user-facing market-data validation error."""


def validate_prices(prices: pd.DataFrame, min_months: int = MIN_MONTHS) -> pd.DataFrame:
    """Return aligned, positive, adjusted close prices on a common trading calendar."""
    if not isinstance(prices, pd.DataFrame):
        raise DataError("Prices must be a table with SPY, SPUS, and HLAL columns.")
    missing = set(TICKERS) - set(prices.columns)
    if missing:
        raise DataError(f"Missing ticker columns: {', '.join(sorted(missing))}.")
    frame = prices.loc[:, list(TICKERS)].copy()
    try:
        frame.index = pd.to_datetime(frame.index, errors="raise", utc=True).tz_convert(None)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataError("Dates could not be parsed. Use YYYY-MM-DD dates.") from exc
    if frame.index.has_duplicates:
        raise DataError("Duplicate dates detected. Remove duplicates before analysis.")
    frame = frame.sort_index()
    for ticker in TICKERS:
        frame[ticker] = pd.to_numeric(frame[ticker], errors="coerce")
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if frame.empty or (frame <= 0).any().any():
        raise DataError("ETF prices must be positive numbers, with common dates for all tickers.")
    if len(frame) < 30:
        raise DataError("Too few aligned trading days to analyze.")
    if len(frame.resample("ME").last()) - 1 < min_months:
        raise DataError(
            f"At least {min_months} complete monthly return observations are required. "
            "Try a longer date range."
        )
    if (frame.index[-1] - frame.index[0]).days < min_months * 27:
        raise DataError("The market history is too short for meaningful monthly analysis.")
    return frame


def load_prices_csv(data: bytes | str, min_months: int = MIN_MONTHS) -> pd.DataFrame:
    """Accept a Date,SPY,SPUS,HLAL adjusted-close CSV; no raw closes."""
    try:
        inp = BytesIO(data) if isinstance(data, bytes) else StringIO(data)
        table = pd.read_csv(inp)
        if "Date" not in table.columns:
            raise DataError("CSV must contain a 'Date' column alongside SPY, SPUS, and HLAL.")
        table["Date"] = pd.to_datetime(table["Date"], errors="raise")
        return validate_prices(table.set_index("Date"), min_months=min_months)
    except DataError:
        raise
    except Exception as exc:
        raise DataError("Unable to load CSV. Expected Date,SPY,SPUS,HLAL adjusted prices.") from exc


def download_prices(start_date: date, end_date: date) -> pd.DataFrame:
    """Download adjusted prices; align all ETFs to their shared observed history."""
    if start_date >= end_date:
        raise DataError("Start date must come before end date.")
    if end_date > date.today():
        raise DataError("End date cannot be in the future.")
    try:
        import yfinance as yf
    except ImportError as exc:
        raise DataError("Install requirements.txt to use Yahoo Finance downloads.") from exc

    columns: dict[str, pd.Series] = {}
    for ticker in TICKERS:
        try:
            history = yf.Ticker(ticker).history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=True,
                actions=False,
                raise_errors=True,
            )
            if history.empty or "Close" not in history.columns:
                raise DataError(f"No adjusted close prices returned for {ticker}.")
            index = pd.to_datetime(history.index, utc=True).tz_convert(None).normalize()
            columns[ticker] = pd.Series(history["Close"].to_numpy(dtype=float), index=index)
        except DataError:
            raise
        except Exception as exc:
            raise DataError(
                f"Could not download {ticker}. Yahoo Finance may be temporarily unavailable. "
                "Try again or upload an adjusted-price CSV."
            ) from exc
    return validate_prices(pd.DataFrame(columns))


def trim_incomplete_last_month(prices: pd.DataFrame) -> pd.DataFrame:
    """Exclude a last month with no end-of-month trading observation.

    Last business day is an approximation to the US exchange calendar; it
    errs on the side of dropping a month around exceptional market holidays.
    """
    if prices.empty:
        return prices
    last = pd.Timestamp(prices.index[-1])
    last_business_day = (last + pd.offsets.BMonthEnd(0)).normalize()
    if last.normalize() < last_business_day:
        current_month = last.to_period("M")
        return prices.loc[prices.index.to_period("M") < current_month].copy()
    return prices


def monthly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Month-end total-return proxies, excluding the last incomplete month."""
    prices = trim_incomplete_last_month(prices)
    month_end = prices.resample("ME").last().dropna(how="any")
    result = month_end.pct_change(fill_method=None).dropna(how="any")
    if (result < -1).any().any():
        raise DataError("Invalid adjusted price data generated a return below -100%.")
    return result


def to_csv_bytes(prices: pd.DataFrame) -> bytes:
    frame = prices.copy()
    frame.index.name = "Date"
    return frame.to_csv(float_format="%.9f", date_format="%Y-%m-%d").encode("utf-8")


def validate_universe_prices(prices: pd.DataFrame, required: tuple[str, ...] = TICKERS, min_months: int = MIN_MONTHS) -> pd.DataFrame:
    """Validate data for ETFs + an optional user-defined stock universe.

    Only *complete-case observed* daily rows survive; no forward-filled stock
    prices or invented observations are inserted.
    """
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        raise DataError("Price table is empty.")
    prices = prices.copy()
    prices.columns = [str(x).upper().strip() for x in prices.columns]
    if prices.columns.duplicated().any():
        raise DataError("Duplicate ticker columns are not allowed.")
    missing = set(required) - set(prices.columns)
    if missing:
        raise DataError(f"Required benchmark columns missing: {', '.join(sorted(missing))}.")
    try:
        prices.index = pd.to_datetime(prices.index, errors="raise", utc=True).tz_convert(None).normalize()
    except Exception as exc:
        raise DataError("Dates must be valid YYYY-MM-DD values.") from exc
    if prices.index.duplicated().any():
        raise DataError("Duplicate dates in adjusted prices.")
    prices = prices.sort_index()
    prices = prices.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if (prices.dropna(how="all") <= 0).any().any():
        raise DataError("Observed adjusted prices must be strictly positive.")
    prices = prices.dropna(how="any")
    if not len(prices):
        raise DataError("No shared dates with observed prices for every selected asset.")
    if len(prices) < 30 or len(monthly_returns(prices)) < min_months:
        raise DataError(f"Need at least {min_months} common, complete monthly return observations.")
    if (prices.index[-1] - prices.index[0]).days < min_months * 27:
        raise DataError("Insufficient calendar history across your selected assets.")
    return prices


def load_universe_csv(data: bytes | str, required: tuple[str, ...] = TICKERS, *, align: bool = True) -> pd.DataFrame:
    """CSV must contain Date,SPY,SPUS,HLAL plus any desired stock tickers."""
    try:
        frame = pd.read_csv(BytesIO(data) if isinstance(data, bytes) else StringIO(data))
        if "Date" not in frame.columns:
            raise DataError("Stock-universe CSV needs a Date column.")
        frame["Date"] = pd.to_datetime(frame["Date"], errors="raise")
        frame = frame.set_index("Date")
        if align:
            return validate_universe_prices(frame, required=required)
        frame.columns = frame.columns.str.strip().str.upper()
        if frame.columns.duplicated().any() or not set(required).issubset(frame.columns):
            raise DataError("Use unique ticker columns and include every required benchmark.")
        frame.index = pd.to_datetime(frame.index, utc=True).tz_convert(None).normalize()
        return frame.sort_index()
    except DataError:
        raise
    except Exception as exc:
        raise DataError("Could not read adjusted-price CSV; check date and ticker columns.") from exc


def download_universe_prices(start_date: date, end_date: date, tickers: tuple[str, ...]) -> pd.DataFrame:
    """Fetch adjusted daily closes in one yfinance call; reject incomplete data.

    The raw frame is aligned in a later step so the UI can diagnose missing
    stock histories instead of silently excluding requested names.
    """
    if start_date >= end_date or end_date > date.today():
        raise DataError("Use a valid historical download date range.")
    if len(tickers) < 3 or any(not isinstance(t, str) for t in tickers):
        raise DataError("Provide ETF benchmarks and optional stock tickers.")
    try:
        import yfinance as yf
        raw = yf.download(
            tickers=list(tickers), start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            interval="1d", auto_adjust=True, actions=False,
            progress=False, threads=True, group_by="column",
        )
        if raw is None or raw.empty or "Close" not in raw:
            raise DataError("Yahoo Finance returned no adjusted closes.")
        closes = raw["Close"].copy()
        if isinstance(closes, pd.Series):
            closes = closes.to_frame(name=tickers[0])
        closes.columns = [str(x).upper().strip() for x in closes.columns]
        closes.index = pd.to_datetime(closes.index, utc=True).tz_convert(None).normalize()
        closes = closes.sort_index()
        for name in TICKERS:
            if name not in closes or closes[name].notna().sum() < 30:
                raise DataError(f"No sufficient observations for required benchmark {name}.")
        return closes
    except DataError:
        raise
    except Exception as exc:
        raise DataError("Yahoo download failed; retry later or upload adjusted historical prices.") from exc

"""Download research price histories; never treat them as executable quotes.

Yahoo Finance is accessed through yfinance for exploratory research only.
The script saves adjusted closes (used by the prototype), raw closes (audit
context only), and a manifest. The default end date is exclusive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DEFAULT_TICKERS = (
    "V", "MA", "KO", "PEP", "XOM", "CVX", "SPY", "XLF", "XLP", "XLE"
)


def _field(data: pd.DataFrame, ticker: str, name: str) -> pd.Series | None:
    if not isinstance(data.columns, pd.MultiIndex):
        if name not in data.columns:
            return None
        return pd.to_numeric(data[name], errors="coerce")
    candidates = ((ticker, name), (name, ticker))
    for key in candidates:
        if key in data.columns:
            return pd.to_numeric(data[key], errors="coerce")
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(tickers: list[str], start: str, end: str, outdir: Path) -> dict:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise SystemExit("Install dependencies: python -m pip install -r requirements.txt") from exc

    data = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )
    if data is None or data.empty:
        raise RuntimeError(
            "No prices returned. Check provider access, requested dates, and tickers."
        )

    adjusted: dict[str, pd.Series] = {}
    raw: dict[str, pd.Series] = {}
    warnings: list[str] = []
    for ticker in tickers:
        adj = _field(data, ticker, "Adj Close")
        close = _field(data, ticker, "Close")
        if adj is None and close is not None:
            adj = close.copy()
            warnings.append(f"{ticker}: adjusted close unavailable; copied raw close")
        if adj is None or adj.dropna().empty:
            warnings.append(f"{ticker}: no usable adjusted close")
            continue
        adjusted[ticker] = adj
        if close is not None:
            raw[ticker] = close

    adjusted_frame = pd.DataFrame(adjusted).sort_index()
    raw_frame = pd.DataFrame(raw).reindex(adjusted_frame.index).sort_index()
    adjusted_frame.index = pd.to_datetime(adjusted_frame.index).tz_localize(None).normalize()
    raw_frame.index = adjusted_frame.index
    adjusted_frame.index.name = raw_frame.index.name = "Date"
    if len(adjusted_frame.columns) < 3:
        raise RuntimeError("Too few valid securities returned; stop rather than silently shrinking the study.")
    missing_entirely = sorted(set(tickers) - set(adjusted_frame.columns))
    if missing_entirely:
        raise RuntimeError(f"Missing complete histories for: {missing_entirely}")

    outdir.mkdir(parents=True, exist_ok=True)
    adjusted_path = outdir / "adjusted_close.csv"
    raw_path = outdir / "raw_close.csv"
    adjusted_frame.to_csv(adjusted_path, float_format="%.10f")
    raw_frame.to_csv(raw_path, float_format="%.10f")
    manifest = {
        "provider": "Yahoo Finance through yfinance (unofficial; exploratory research only)",
        "source_url": "https://ranaroussi.github.io/yfinance/",
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start": start,
        "requested_end_exclusive": end,
        "tickers": list(adjusted_frame.columns),
        "model_input": "adjusted_close.csv",
        "price_basis": (
            "Adjusted Close approximates total return after vendor corporate-action adjustments; "
            "it is not a historical executable fill price. raw_close.csv is audit context only."
        ),
        "rows": int(len(adjusted_frame)),
        "earliest_date": str(adjusted_frame.index.min().date()),
        "latest_date": str(adjusted_frame.index.max().date()),
        "missing_per_ticker": {
            key: int(value) for key, value in adjusted_frame.isna().sum().items()
        },
        "file_sha256": {
            "adjusted_close.csv": _sha256(adjusted_path),
            "raw_close.csv": _sha256(raw_path),
        },
        "warnings": warnings,
        "limitations": [
            "modern ticker list creates survivorship and point-in-time membership bias",
            "vendor data can be revised and may omit delistings or corrections",
            "adjusted prices are total-return approximations, not executable quotes",
            "raw closes do not by themselves model splits, dividends, spreads, or slippage",
            "daily bars cannot establish next-open or intraday fill quality",
            "redistribution rights must be checked; raw downloads are gitignored",
        ],
    }
    (outdir / "download_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Saved {len(adjusted_frame)} dates for {len(adjusted_frame.columns)} tickers; "
        f"coverage {manifest['earliest_date']} through {manifest['latest_date']}"
    )
    print("Research-only adjusted prices are not executable historical fills.")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS))
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-10-17", help="exclusive (YYYY-MM-DD)")
    parser.add_argument("--outdir", type=Path, default=Path("data"))
    args = parser.parse_args()
    download([ticker.upper() for ticker in args.tickers], args.start, args.end, args.outdir)


if __name__ == "__main__":
    main()


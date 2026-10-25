"""Download official Kenneth French daily factors for local research."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DEFAULT_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_Factors_daily_CSV.zip"
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fetch_archive(url: str, retries: int = 3) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "MonteCarloInvestmentLab/0.5"})
    retryable = {429, 500, 502, 503, 504}
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in retryable or attempt == retries:
                raise
        except urllib.error.URLError:
            if attempt == retries:
                raise
        time.sleep(2 ** (attempt - 1))
    raise RuntimeError("unreachable")


def download(url: str, outdir: Path, retries: int = 3) -> dict:
    archive = fetch_archive(url, retries=retries)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        names = bundle.namelist()
        if len(names) != 1:
            raise RuntimeError(f"Expected one factor CSV in archive, found {names}")
        text = bundle.read(names[0]).decode("utf-8", errors="strict")

    lines = text.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if "Mkt-RF" in line and "SMB" in line),
        None,
    )
    if header_index is None:
        raise RuntimeError("Could not locate Kenneth French factor header.")
    rows: list[list[str]] = []
    for line in lines[header_index + 1:]:
        fields = [field.strip() for field in line.split(",")]
        if not fields or re.fullmatch(r"\d{8}", fields[0]) is None:
            break
        if len(fields) < 5:
            raise RuntimeError(f"Unexpected factor row: {line}")
        rows.append(fields[:5])
    if not rows:
        raise RuntimeError("No daily factor rows parsed.")

    factors = pd.DataFrame(rows, columns=["Date", "Mkt-RF", "SMB", "HML", "RF"])
    factors["Date"] = pd.to_datetime(factors["Date"], format="%Y%m%d")
    for column in ["Mkt-RF", "SMB", "HML", "RF"]:
        factors[column] = pd.to_numeric(factors[column], errors="raise") / 100.0
    factors = factors.set_index("Date").sort_index()

    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "french_factors_daily.csv"
    factors.to_csv(path, float_format="%.8f")
    manifest = {
        "provider": "Kenneth R. French Data Library",
        "source_url": url,
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": sha256_bytes(archive),
        "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": int(len(factors)),
        "first_date": str(factors.index.min().date()),
        "last_date": str(factors.index.max().date()),
        "columns": list(factors.columns),
        "units": "decimal daily returns; source percentages divided by 100",
        "limitations": [
            "factor definitions and historical values can be revised",
            "HAC regression is descriptive and does not prove alpha",
            "factor data do not solve execution, borrow, or selection bias",
        ],
    }
    (outdir / "french_factors_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Saved {len(factors)} official factor rows through {manifest['last_date']}"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--outdir", type=Path, default=Path("data"))
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    if args.retries < 1:
        raise ValueError("--retries must be at least 1")
    download(args.url, args.outdir, retries=args.retries)


if __name__ == "__main__":
    main()


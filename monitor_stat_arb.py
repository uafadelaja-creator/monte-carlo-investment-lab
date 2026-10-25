"""Append an idempotent, frozen-protocol monitoring snapshot.

This ledger makes repeated weekly evaluation explicit. It records aggregate
out-of-sample evidence without changing pair hypotheses or model parameters.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import date
from pathlib import Path

import pandas as pd


KEYS = ["observed_on", "data_through", "pair", "protocol_sha256"]


def _load_reports(results: Path) -> dict[str, dict]:
    reports: dict[str, dict] = {}
    for path in sorted(results.glob("*_report.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        pair = "/".join(report["pair"])
        reports[pair] = report
    if not reports:
        raise ValueError(f"No pair reports found in {results}")
    return reports


def _protocol(reports: dict[str, dict]) -> tuple[dict, str]:
    settings = {json.dumps(report["settings"], sort_keys=True) for report in reports.values()}
    starts = {report["test_start"] for report in reports.values()}
    if len(settings) != 1 or len(starts) != 1:
        raise ValueError("Pair reports do not share one frozen protocol.")
    protocol = {
        "pairs": sorted(reports),
        "test_start": next(iter(starts)),
        "settings": json.loads(next(iter(settings))),
    }
    canonical = json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode()
    return protocol, hashlib.sha256(canonical).hexdigest()


def _manifest(results: Path, reports: dict[str, dict], path: Path | None) -> dict:
    if path is not None:
        return json.loads(path.read_text(encoding="utf-8"))
    manifests = [report.get("download_manifest") for report in reports.values()]
    manifests = [value for value in manifests if value]
    if not manifests:
        raise ValueError("No download manifest supplied or embedded in reports.")
    return manifests[0]


def _bootstrap(results: Path, pair: str, horizon: int) -> pd.Series:
    frame = pd.read_csv(results / f"{pair.replace('/', '_')}_bootstrap.csv")
    row = frame.loc[frame["horizon_months"] == horizon]
    if len(row) != 1:
        raise ValueError(f"Expected one {horizon}-month row for {pair}")
    return row.iloc[0]


def build_snapshot(
    results: Path,
    observed_on: str,
    manifest_path: Path | None = None,
) -> tuple[pd.DataFrame, dict, dict]:
    reports = _load_reports(results)
    protocol, protocol_hash = _protocol(reports)
    manifest = _manifest(results, reports, manifest_path)
    price_hash = manifest.get("file_sha256", {}).get("adjusted_close.csv", "")
    rows: list[dict] = []
    for pair, report in reports.items():
        one_year = _bootstrap(results, pair, 12)
        three_year = _bootstrap(results, pair, 36)
        strategy = report["strategy_net"]
        rows.append(
            {
                "observed_on": observed_on,
                "data_through": manifest["latest_date"],
                "pair": pair,
                "protocol_sha256": protocol_hash,
                "adjusted_close_sha256": price_hash,
                "test_sessions": strategy["n_sessions"],
                "entries": report["executed_entry_count"],
                "exposure_fraction": report["exposure_fraction"],
                "net_cumulative_return": strategy["cumulative_return"],
                "max_drawdown": strategy["max_drawdown"],
                "twelve_month_median_return": one_year["median_return"],
                "twelve_month_probability_profitable": one_year[
                    "probability_profitable"
                ],
                "twelve_month_probability_loss": one_year["probability_loss"],
                "thirty_six_month_median_return": three_year["median_return"],
                "thirty_six_month_probability_profitable": three_year[
                    "probability_profitable"
                ],
                "thirty_six_month_probability_loss": three_year["probability_loss"],
            }
        )
    return pd.DataFrame(rows), manifest, protocol


def prefix_sha256(prices_path: Path, through: str) -> str:
    frame = pd.read_csv(prices_path, index_col=0, parse_dates=True).sort_index()
    frame = frame.loc[:pd.Timestamp(through)]
    stream = io.StringIO()
    frame.to_csv(stream, float_format="%.10f")
    return hashlib.sha256(stream.getvalue().encode()).hexdigest()


def update_ledger(existing: pd.DataFrame, snapshot: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return snapshot.sort_values(KEYS).reset_index(drop=True)
    if set(existing["protocol_sha256"]) != set(snapshot["protocol_sha256"]):
        raise ValueError(
            "Protocol fingerprint changed. Preserve the old ledger and start a new protocol series."
        )
    combined = pd.concat([existing, snapshot], ignore_index=True)
    return combined.drop_duplicates(KEYS, keep="last").sort_values(KEYS).reset_index(drop=True)


def previous_data_date(existing: pd.DataFrame, current_date: str) -> str | None:
    if existing.empty:
        return None
    dates = sorted(
        value for value in existing["data_through"].astype(str).unique()
        if value < current_date
    )
    return dates[-1] if dates else None


def monitoring_report(
    ledger: pd.DataFrame,
    current: pd.DataFrame,
    manifest: dict,
    protocol: dict,
    prefix_matches: bool | None,
) -> str:
    current_date = current["data_through"].iloc[0]
    prior = ledger.loc[ledger["data_through"] < current_date]
    lines = [
        "# Sequential evidence monitor",
        "",
        f"Current data through: **{current_date}**",
        f"Price source: **{manifest['provider']}**",
        f"Protocol SHA-256: `{current['protocol_sha256'].iloc[0]}`",
        "",
        "The pair list and protocol remain frozen. This page reports evidence drift; it does not",
        "select a winning pair, revise parameters, or issue a trade alert.",
        "",
        "| Pair | New sessions | New entries | Net return | Change | 12m P(loss) | 36m P(loss) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in current.sort_values("pair").iterrows():
        historical = prior.loc[prior["pair"] == row["pair"]].sort_values("data_through")
        if historical.empty:
            sessions_delta = entries_delta = 0
            return_delta = 0.0
        else:
            previous = historical.iloc[-1]
            sessions_delta = int(row["test_sessions"] - previous["test_sessions"])
            entries_delta = int(row["entries"] - previous["entries"])
            return_delta = row["net_cumulative_return"] - previous["net_cumulative_return"]
        lines.append(
            f"| {row['pair']} | {sessions_delta} | {entries_delta} | "
            f"{row['net_cumulative_return']:.3%} | {return_delta:+.3%} | "
            f"{row['twelve_month_probability_loss']:.1%} | "
            f"{row['thirty_six_month_probability_loss']:.1%} |"
        )
    lines += ["", "## Integrity checks", ""]
    if prefix_matches is None:
        lines.append("- Prior-prefix vendor revision check: unavailable for the first snapshot.")
    elif prefix_matches:
        lines.append("- Prior-prefix vendor revision check: exact byte-level match.")
    else:
        lines.append(
            "- Prior-prefix vendor revision check: **hash changed**. Aggregate result drift must be "
            "interpreted as a combination of new sessions and upstream adjusted-price revisions."
        )
    lines += [
        f"- Frozen pairs: {', '.join(protocol['pairs'])}.",
        f"- Model input SHA-256: `{current['adjusted_close_sha256'].iloc[0]}`.",
        "- Zero trades or a zero simulated loss rate denotes inactivity, not evidence of success.",
        "- Repeated weekly checks are descriptive monitoring, not independent hypothesis tests.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--observed-on", default=date.today().isoformat())
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--prices", type=Path)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    snapshot, manifest, protocol = build_snapshot(
        args.results, args.observed_on, args.manifest
    )
    existing = pd.read_csv(args.ledger) if args.ledger.exists() else pd.DataFrame()
    current_date = str(snapshot["data_through"].iloc[0])
    prior_date = previous_data_date(existing, current_date)
    prefix_matches: bool | None = None
    if prior_date is not None and args.prices is not None:
        prior_hash = existing.loc[
            existing["data_through"] == prior_date, "adjusted_close_sha256"
        ].iloc[0]
        prefix_matches = prefix_sha256(args.prices, prior_date) == prior_hash

    ledger = update_ledger(existing, snapshot)
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(args.ledger, index=False, float_format="%.10f")
    args.report.write_text(
        monitoring_report(ledger, snapshot, manifest, protocol, prefix_matches),
        encoding="utf-8",
    )
    print(args.report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

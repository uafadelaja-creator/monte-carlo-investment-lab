"""Append a tamper-evident, forward-only paper-signal audit.

The audit begins when it is initialized. It does not reconstruct hypothetical
signals before that date. Each run freezes the final completed-session state for
every predeclared pair. A newly observed entry can only be resolved on a later
run, after the next completed session exists in the downloaded data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from monitor_stat_arb import _load_reports, _protocol


ENTRY_EVENTS = {"INITIAL_ENTRY", "ENTRY", "REVERSAL"}
INT_COLUMNS = {"sequence", "signal_side"}
FLOAT_COLUMNS = {
    "zscore",
    "cointegration_p",
    "hedge_beta",
    "target_weight_a",
    "target_weight_b",
    "adjusted_price_a",
    "adjusted_price_b",
    "raw_open_a",
    "raw_open_b",
    "raw_close_a",
    "raw_close_b",
    "median_dollar_volume_20d_a",
    "median_dollar_volume_20d_b",
    "daily_range_proxy_a",
    "daily_range_proxy_b",
    "model_borrow_apr",
}
LEDGER_COLUMNS = [
    "sequence",
    "record_key",
    "record_type",
    "observed_on",
    "data_through",
    "pair",
    "protocol_sha256",
    "source_sha256",
    "signal_date",
    "signal_event",
    "signal_side",
    "signal_state",
    "zscore",
    "cointegration_p",
    "hedge_beta",
    "target_weight_a",
    "target_weight_b",
    "execution_date",
    "adjusted_price_a",
    "adjusted_price_b",
    "raw_open_a",
    "raw_open_b",
    "raw_close_a",
    "raw_close_b",
    "median_dollar_volume_20d_a",
    "median_dollar_volume_20d_b",
    "daily_range_proxy_a",
    "daily_range_proxy_b",
    "spread_observation",
    "borrow_availability",
    "model_borrow_apr",
    "execution_status",
    "previous_row_sha256",
    "row_sha256",
]


def _read_table(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    return frame


def _value(frame: pd.DataFrame, when: pd.Timestamp, ticker: str) -> float | None:
    if ticker not in frame or when not in frame.index:
        return None
    value = frame.at[when, ticker]
    return float(value) if pd.notna(value) else None


def _target(side: int, beta: float) -> tuple[float, float]:
    if side == 0 or not np.isfinite(beta) or beta <= 0:
        return 0.0, 0.0
    return side / (1 + beta), -side * beta / (1 + beta)


def _state(side: int) -> str:
    return {
        -1: "short_first_long_second",
        0: "flat",
        1: "long_first_short_second",
    }[side]


def _event(previous: int | None, current: int) -> str:
    if previous is None:
        return "INITIAL_ENTRY" if current else "INITIAL_FLAT"
    if previous == current:
        return "HOLD" if current else "FLAT"
    if previous == 0 and current != 0:
        return "ENTRY"
    if previous != 0 and current == 0:
        return "EXIT"
    return "REVERSAL"


def _canonical_value(column: str, value: object) -> object:
    if value is None or value == "" or pd.isna(value):
        return ""
    if column in INT_COLUMNS:
        return int(float(value))
    if column in FLOAT_COLUMNS:
        # Significant-digit normalization survives CSV -> IEEE-754 round trips,
        # including large dollar-volume fields where ten decimal places do not.
        return format(float(value), ".12g")
    return str(value)


def _row_hash(row: dict) -> str:
    payload = {
        key: _canonical_value(key, row.get(key))
        for key in LEDGER_COLUMNS
        if key not in {"row_sha256"}
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def append_rows(existing: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    ledger = existing.copy()
    if ledger.empty:
        ledger = pd.DataFrame(columns=LEDGER_COLUMNS)
    known = set(ledger.get("record_key", pd.Series(dtype=str)).astype(str))
    previous_hash = "" if ledger.empty else str(ledger.iloc[-1]["row_sha256"])
    sequence = len(ledger)
    additions: list[dict] = []
    for row in rows:
        if row["record_key"] in known:
            continue
        sequence += 1
        row = {column: row.get(column, "") for column in LEDGER_COLUMNS}
        row["sequence"] = sequence
        row["previous_row_sha256"] = previous_hash
        row["row_sha256"] = _row_hash(row)
        previous_hash = row["row_sha256"]
        additions.append(row)
        known.add(row["record_key"])
    if additions:
        addition_frame = pd.DataFrame(additions, columns=LEDGER_COLUMNS)
        ledger = addition_frame if ledger.empty else pd.concat(
            [ledger, addition_frame], ignore_index=True
        )
    return ledger[LEDGER_COLUMNS]


def verify_chain(ledger: pd.DataFrame) -> bool:
    previous = ""
    for _, series in ledger.iterrows():
        row = series.to_dict()
        if str(row.get("previous_row_sha256", "")) != previous:
            return False
        if str(row.get("row_sha256", "")) != _row_hash(row):
            return False
        previous = str(row["row_sha256"])
    return True


def _market_context(
    market: dict[str, pd.DataFrame], when: pd.Timestamp, ticker: str
) -> dict[str, float | None]:
    close = _value(market["raw_close"], when, ticker)
    high = _value(market["raw_high"], when, ticker)
    low = _value(market["raw_low"], when, ticker)
    volume = market["volume"].get(ticker, pd.Series(dtype=float)).loc[:when].tail(20)
    raw_close = market["raw_close"].get(ticker, pd.Series(dtype=float)).loc[:when].tail(20)
    dollar_volume = (raw_close * volume).dropna()
    return {
        "raw_open": _value(market["raw_open"], when, ticker),
        "raw_close": close,
        "median_dollar_volume_20d": (
            float(dollar_volume.median()) if not dollar_volume.empty else None
        ),
        "daily_range_proxy": (
            float((high - low) / close)
            if close and high is not None and low is not None
            else None
        ),
    }


def build_records(
    results: Path,
    data: Path,
    existing: pd.DataFrame,
    observed_on: str,
) -> tuple[list[dict], dict, str]:
    reports = _load_reports(results)
    protocol, protocol_sha = _protocol(reports)
    manifest = json.loads((data / "download_manifest.json").read_text(encoding="utf-8"))
    market = {
        name: _read_table(data / f"{name}.csv")
        for name in ("adjusted_close", "raw_open", "raw_high", "raw_low", "raw_close", "volume")
    }
    records: list[dict] = []

    # Resolve only entry observations that were frozen on an earlier run.
    if not existing.empty:
        observations = existing.loc[
            (existing["record_type"] == "observation")
            & (existing["signal_event"].isin(ENTRY_EVENTS))
        ]
        resolved_signal_dates = set(
            zip(
                existing.loc[existing["record_type"] == "resolution", "pair"],
                existing.loc[existing["record_type"] == "resolution", "signal_date"],
            )
        )
        for _, observation in observations.iterrows():
            pair = str(observation["pair"])
            signal_date = str(observation["signal_date"])
            if (pair, signal_date) in resolved_signal_dates:
                continue
            a, b = pair.split("/")
            daily = _read_table(results / f"{a}_{b}_daily.csv")
            later = daily.index[daily.index > pd.Timestamp(signal_date)]
            if later.empty:
                continue
            execution_date = later[0]
            context_a = _market_context(market, execution_date, a)
            context_b = _market_context(market, execution_date, b)
            records.append(
                {
                    **observation.to_dict(),
                    "record_key": f"resolution|{pair}|{signal_date}|{execution_date.date()}",
                    "record_type": "resolution",
                    "observed_on": observed_on,
                    "data_through": manifest["latest_date"],
                    "execution_date": str(execution_date.date()),
                    "adjusted_price_a": _value(market["adjusted_close"], execution_date, a),
                    "adjusted_price_b": _value(market["adjusted_close"], execution_date, b),
                    "raw_open_a": context_a["raw_open"],
                    "raw_open_b": context_b["raw_open"],
                    "raw_close_a": context_a["raw_close"],
                    "raw_close_b": context_b["raw_close"],
                    "median_dollar_volume_20d_a": context_a["median_dollar_volume_20d"],
                    "median_dollar_volume_20d_b": context_b["median_dollar_volume_20d"],
                    "daily_range_proxy_a": context_a["daily_range_proxy"],
                    "daily_range_proxy_b": context_b["daily_range_proxy"],
                    "execution_status": "resolved_next_session_close_audit",
                    "previous_row_sha256": "",
                    "row_sha256": "",
                }
            )

    for pair, report in sorted(reports.items()):
        a, b = pair.split("/")
        daily = _read_table(results / f"{a}_{b}_daily.csv")
        signal_date = daily.index[-1]
        latest = daily.iloc[-1]
        side = int(latest["signal_side"])
        beta = float(latest["hedge_beta"]) if pd.notna(latest["hedge_beta"]) else float("nan")
        target_a, target_b = _target(side, beta)
        previous_rows = existing.loc[
            (existing.get("record_type", "") == "observation")
            & (existing.get("pair", "") == pair)
        ] if not existing.empty else pd.DataFrame()
        previous_side = None if previous_rows.empty else int(previous_rows.iloc[-1]["signal_side"])
        event = _event(previous_side, side)
        context_a = _market_context(market, signal_date, a)
        context_b = _market_context(market, signal_date, b)
        records.append(
            {
                "record_key": f"observation|{pair}|{signal_date.date()}|{observed_on}",
                "record_type": "observation",
                "observed_on": observed_on,
                "data_through": manifest["latest_date"],
                "pair": pair,
                "protocol_sha256": protocol_sha,
                "source_sha256": manifest["file_sha256"]["adjusted_close.csv"],
                "signal_date": str(signal_date.date()),
                "signal_event": event,
                "signal_side": side,
                "signal_state": _state(side),
                "zscore": latest["zscore"],
                "cointegration_p": latest["cointegration_p"],
                "hedge_beta": beta,
                "target_weight_a": target_a,
                "target_weight_b": target_b,
                "adjusted_price_a": _value(market["adjusted_close"], signal_date, a),
                "adjusted_price_b": _value(market["adjusted_close"], signal_date, b),
                "raw_open_a": context_a["raw_open"],
                "raw_open_b": context_b["raw_open"],
                "raw_close_a": context_a["raw_close"],
                "raw_close_b": context_b["raw_close"],
                "median_dollar_volume_20d_a": context_a["median_dollar_volume_20d"],
                "median_dollar_volume_20d_b": context_b["median_dollar_volume_20d"],
                "daily_range_proxy_a": context_a["daily_range_proxy"],
                "daily_range_proxy_b": context_b["daily_range_proxy"],
                "spread_observation": "unobserved; daily_range_proxy_is_not_bid_ask_spread",
                "borrow_availability": "unobserved",
                "model_borrow_apr": report["settings"]["hypothetical_short_borrow_apr"],
                "execution_status": (
                    "pending_next_session_close_audit" if event in ENTRY_EVENTS else "not_applicable"
                ),
            }
        )
    return records, protocol, protocol_sha


def render_report(ledger: pd.DataFrame, protocol: dict, protocol_sha: str) -> str:
    observations = ledger.loc[ledger["record_type"] == "observation"]
    latest = observations.sort_values("sequence").groupby("pair", as_index=False).tail(1)
    resolutions = ledger.loc[ledger["record_type"] == "resolution"]
    lines = [
        "# Forward paper-signal audit",
        "",
        f"Protocol SHA-256: `{protocol_sha}`",
        f"Frozen pairs: {', '.join(protocol['pairs'])}",
        "",
        "This append-only audit begins at its initialization date; it does not backfill",
        "historical signals as if they had been observed in real time.",
        "",
        "| Pair | Signal date | Event | State | Z-score | Coint. p | Execution audit |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for _, row in latest.sort_values("pair").iterrows():
        zscore = (
            "n/a"
            if row["zscore"] == "" or pd.isna(row["zscore"])
            else f"{float(row['zscore']):.2f}"
        )
        pvalue = (
            "n/a"
            if row["cointegration_p"] == "" or pd.isna(row["cointegration_p"])
            else f"{float(row['cointegration_p']):.3f}"
        )
        lines.append(
            f"| {row['pair']} | {row['signal_date']} | {row['signal_event']} | "
            f"{row['signal_state']} | {zscore} | {pvalue} | {row['execution_status']} |"
        )
    lines += [
        "",
        f"Resolved prospective entries: **{len(resolutions)}**.",
        "",
        "## Interpretation limits",
        "",
        "- Adjusted closes remain model inputs, not trade-executable quotes.",
        "- Raw next-session closes are audit references; they do not prove fill quality.",
        "- The daily range proxy is not a bid/ask spread estimate.",
        "- Borrow inventory and actual borrow rates remain unobserved; the model uses a 3% APR scenario.",
        "- Weekly observations can miss intraweek signal changes and are not trade alerts.",
        f"- Hash chain status: **{'valid' if verify_chain(ledger) else 'INVALID'}**.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--observed-on", default=date.today().isoformat())
    args = parser.parse_args()

    existing = pd.read_csv(args.ledger, keep_default_na=False) if args.ledger.exists() else pd.DataFrame()
    if not existing.empty and not verify_chain(existing):
        raise ValueError("Existing forward ledger hash chain is invalid; refusing to append.")
    records, protocol, protocol_sha = build_records(
        args.results, args.data, existing, args.observed_on
    )
    ledger = append_rows(existing, records)
    if not verify_chain(ledger):
        raise ValueError("Forward ledger hash chain failed after append.")
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(args.ledger, index=False, float_format="%.12g")
    args.report.write_text(render_report(ledger, protocol, protocol_sha), encoding="utf-8")
    print(args.report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

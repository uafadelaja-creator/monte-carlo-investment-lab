#!/usr/bin/env python3
"""Independent, fail-closed audit of PAIR//LAB's currently published daily model.

Uses the exact, SHA-256 preserved price file used by the scanner.
This proves internal reproducibility, NOT vendor accuracy, future returns or
tradeability. Any mismatches stop publication and leave prior reports intact.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

HERE = Path(__file__).resolve().parent
DATA = HERE / "stat-arb-dashboard" / "data"
SCAN = DATA / "daily_discovery.json"
REVIEWS = DATA / "review_history.json"
AUDIT = DATA / "daily_audit.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def comparable(a: object, b: object, tolerance: float, label: str) -> None:
    require(isinstance(a, (float, int)) and math.isfinite(float(a)), label + " non-finite/missing actual")
    require(isinstance(b, (float, int)) and math.isfinite(float(b)), label + " non-finite/missing recomputation")
    require(abs(float(a)-float(b)) <= tolerance, f"{label}: published {a}, recomputed {b}")


def independent_measure(prices: pd.DataFrame, a: str, b: str, cutoff: str) -> dict | None:
    if a not in prices or b not in prices:
        return None
    xy=prices.loc[:cutoff, [a, b]].dropna()
    if len(xy) < 320 or str(xy.index[-1].date()) != cutoff:
        return None
    logged=np.log(xy.iloc[-253:])
    train=logged.iloc[:-1]
    y=train[a].to_numpy(dtype=float)
    x=train[b].to_numpy(dtype=float)
    if np.std(x) < 1e-7 or np.std(y) < 1e-7:
        return None
    design=np.column_stack((np.ones(len(x)), x))
    intercept, beta=np.linalg.lstsq(design,y,rcond=None)[0]
    residual=y-intercept-beta*x
    scale=np.std(residual[-60:],ddof=1)
    if not np.isfinite(scale) or scale < 1e-9:
        return None
    obs=logged.iloc[-1]
    z=(float(obs[a])-intercept-beta*float(obs[b])-np.mean(residual[-60:]))/scale
    changes=train.diff().dropna().iloc[-90:]
    corr=float(changes[a].corr(changes[b]))
    beta_early=float(np.linalg.lstsq(np.column_stack((np.ones(126),x[:126])),y[:126],rcond=None)[0][1])
    beta_late=float(np.linalg.lstsq(np.column_stack((np.ones(126),x[-126:])),y[-126:],rcond=None)[0][1])
    drift=100*abs(beta_late-beta_early)/max(abs(beta_early),.10)
    if not np.isfinite([beta,z,corr,drift]).all():
        return None
    tested=corr > .50
    p=float(coint(y,x,trend="c",autolag="aic")[1]) if tested else 1.0
    require(np.isfinite(p) and 0<=p<=1,f"Unexpected p-value for {a}/{b}")
    return {"correlation":corr,"z":z,"beta":beta,"beta_drift_pct":drift,
            "p":p,"cointegration_tested":tested}


def adjusted_q(pvalues: list[float]) -> list[float]:
    arr=np.array(pvalues,dtype=float)
    require(len(arr)>0 and np.isfinite(arr).all() and ((arr>=0)&(arr<=1)).all(),
            "BH adjustment invalid p-values")
    order=np.argsort(arr)
    output=np.ones(len(arr))
    running=1.0
    for j in range(len(order)-1,-1,-1):
        ix=order[j]
        running=min(running, float(arr[ix])*len(arr)/(j+1))
        output[ix]=running
    return output.tolist()


def load_checkpoint(scan: dict) -> tuple[pd.DataFrame, str, Path]:
    meta=scan.get("input_provenance") or {}
    rel=meta.get("path","")
    require(rel.startswith("stat-arb-dashboard/data/source-snapshots/") and
            rel.endswith(".csv.gz") and ".." not in rel, "Unsafe/missing source checkpoint")
    snapshot=HERE / rel
    require(snapshot.is_file(),"Missing price snapshot: "+rel)
    raw=gzip.decompress(snapshot.read_bytes())
    sha=hashlib.sha256(raw).hexdigest()
    require(sha==meta.get("sha256_uncompressed_csv"),"Input price SHA-256 mismatch")
    prices=pd.read_csv(snapshot,index_col="date",parse_dates=["date"])
    require(prices.index.is_monotonic_increasing and prices.index.is_unique,
            "Input dates not unique and increasing")
    require(prices.columns.is_unique,"Input tickers duplicated")
    require(len(prices)==meta["calendar_rows"] and len(prices.columns)==meta["ticker_count"],
            "Price checkpoint dimensions mismatch")
    require(prices.index.max().date().isoformat()==scan["as_of"], "Price checkpoint does not end on scan date")
    require(prices.shape[1]>=20 and prices.shape[0]>=320,"Price checkpoint unexpectedly small")
    return prices,sha,snapshot


def check_replay_examples(record:dict, prices: pd.DataFrame) -> int:
    pair=record["pair"]
    names=[record["a"],record["b"]]
    frame=prices.loc[:record["data_through"],names].dropna()
    by_date={str(idx.date()):idx for idx in frame.index}
    rep=record.get("retrospective_replay") or {}
    require(rep.get("label","").startswith("RETROSPECTIVE"),f"{pair} replay mislabeled")
    require(rep.get("equal_dollar_legs") is True,f"{pair} replay missing simplified hedge disclosure")
    examples=rep.get("examples",[])
    require(len(examples)<=rep.get("events",0),f"{pair} example count exceeds events")
    for ex in examples:
        a,b,c=ex["signal_date"],ex["entry_date"],ex["exit_date"]
        require(a in by_date and b in by_date and c in by_date and a<b<c,
                f"{pair} replay dates invalid")
        dates=list(frame.index)
        ix=dates.index(by_date[b]);jx=dates.index(by_date[c])
        require(jx-ix==5,f"{pair} replay does not hold five sessions")
        entry=frame.iloc[ix];end=frame.iloc[jx]
        ra=float(end.iloc[0]/entry.iloc[0]-1)
        rb=float(end.iloc[1]/entry.iloc[1]-1)
        direction=-1 if ex["direction"]=="SHORT_A_LONG_B" else 1
        require(ex["direction"] in ("SHORT_A_LONG_B","LONG_A_SHORT_B"),
                f"{pair} unknown trade direction")
        gross=100*.5*direction*(ra-rb)
        net=gross-100*(2*.001+.5*.03*5/252)
        comparable(ex["gross_return_pct"],gross,.0002,f"{pair} replay gross")
        comparable(ex["net_return_pct"],net,.0002,f"{pair} replay net")
    return len(examples)


def audit(scan_path:Path=SCAN, reviews_path:Path=REVIEWS) -> dict:
    scan=json.loads(scan_path.read_text(encoding="utf-8"))
    reviews=json.loads(reviews_path.read_text(encoding="utf-8"))
    require(scan.get("schema_version")==1 and reviews.get("schema_version")==1,"Unsupported JSON schema")
    require(scan.get("kind")=="DAILY_EXPLORATORY_DISCOVERY_NOT_TRADE_SIGNALS","Wrong data kind")
    market_date=scan["as_of"]
    require(datetime.strptime(market_date,"%Y-%m-%d").date() <= datetime.now(timezone.utc).date(),
            "Scan market date is in the future")
    prices,price_sha,snapshot=load_checkpoint(scan)
    rows=scan["pairs"]
    require(len(rows)>=150,"Abruptly reduced screening universe")
    require(len({r["pair"] for r in rows})==len(rows),"Duplicate daily pair")
    independent=[]
    unavailable=0
    for row in rows:
        a,b=row["a"],row["b"]
        require(row["pair"]==a+"/"+b and a!=b,f"Malformed pair {row}")
        measured=independent_measure(prices,a,b,market_date)
        if measured is None:
            unavailable+=1
            require(row["status"]=="data_unavailable" and row["p"]==1.0,
                    f"{row['pair']} missing data must be explicitly unavailable")
            independent.append(None)
            continue
        require(row["status"]!="data_unavailable",f"{row['pair']} incorrectly unavailable")
        for key,tol in (("p",.00001),("z",.0002),("correlation",.00002),
                        ("beta",.00002),("beta_drift_pct",.06)):
            comparable(row.get(key),measured[key],tol,row["pair"]+" "+key)
        require(row["cointegration_tested"]==measured["cointegration_tested"],
                row["pair"]+" tested flag mismatch")
        independent.append(measured)

    # Null/untested rows all contribute p=1 to the multiplicity family.
    q=adjusted_q([m["p"] if m else 1.0 for m in independent])
    classifications={}
    for row,measure,adjusted in zip(rows,independent,q):
        comparable(row["q"],adjusted,.000001,row["pair"]+" BH q")
        if measure is None:
            classifications[row["pair"]]="data_unavailable"
            continue
        nominal=measure["p"]<.05 and measure["correlation"]>.75 and abs(measure["z"])>=2
        stable=measure["beta"]>0 and measure["beta_drift_pct"]<=30
        qualified=nominal and adjusted<.05 and stable
        expected=("research_candidate" if qualified else "preliminary_watch"
                  if nominal else "not_qualified")
        require(row["status"]==expected,row["pair"]+" false classification")
        calculated_gates={
            "cointegration":measure["p"]<.05,"correlation":measure["correlation"]>.75,
            "deviation":abs(measure["z"])>=2,"fdr":adjusted<.05,"beta_stable":stable,
        }
        require(row.get("gates")==calculated_gates,row["pair"]+" gate mismatch")
        classifications[row["pair"]]=expected
    summary=scan["summary"]
    require(summary["pairs_enumerated"]==len(rows),"Wrong number of generated pairs")
    require(summary["pairs_unavailable"]==unavailable,"Wrong unavailable count")
    require(summary["pairs_tested_cointegration"]==
            sum(bool(m and m["cointegration_tested"]) for m in independent),
            "Wrong tested count")
    require(summary["research_candidates"]==sum(x=="research_candidate" for x in classifications.values()),
            "Wrong candidate count")
    require(summary["fdr_survivors"]==sum(value<.05 for value in q),
            "Wrong FDR count")
    require(summary["nominal_combined_gates"]==sum(x in ("research_candidate","preliminary_watch") for x in classifications.values()),
            "Wrong preliminary count")

    records=reviews["records"]
    require(len(records)==reviews["total_reviews"],"Incorrect total archived reviews")
    require(len({(r["review_date"],r["pair"]) for r in records})==len(records),
            "Duplicate dated reviews")
    require(len({r["pair"] for r in records})==reviews["unique_pairs_reviewed"],
            "Incorrect unique pair count")
    legacy=0
    checked=0
    replay_checked=0
    for r in records:
        require(r["review_date"]>=r["data_through"],"Review predates market data")
        ref=r.get("input_provenance")
        if not ref:
            legacy+=1
            require(r.get("provenance_status")=="legacy_no_preserved_price_input",
                    "Unverified legacy record not disclosed")
            continue
        previous_path=ref["path"]
        require(previous_path.startswith("stat-arb-dashboard/data/source-snapshots/") and
                ".." not in previous_path,"Unsafe historical checkpoint path")
        saved=HERE / previous_path
        require(saved.exists(),"Missing historical review price input")
        raw=gzip.decompress(saved.read_bytes())
        require(hashlib.sha256(raw).hexdigest()==ref["sha256_uncompressed_csv"],
                "Historical review price data has been altered")
        if ref["sha256_uncompressed_csv"]==price_sha:
            match=next((z for z in rows if z["pair"]==r["pair"]),None)
            require(match is not None,"Deep-reviewed pair missing from broad scan")
            metrics=r["metrics"]
            for source,target,tol in (("p","engle_granger_p",.00001),
                                      ("q","universe_fdr_q",.00001),
                                      ("correlation","correlation_90d",.00001),
                                      ("z","z_score_60d",.0001)):
                comparable(metrics[target],match[source],tol,r["pair"]+" deep review "+target)
            replay_checked+=check_replay_examples(r,prices)
            checked+=1
    require(sum(r["review_date"]==max(x["review_date"] for x in records) for r in records)==2,
            "Latest review date must contain exactly two records")
    return {
        "schema_version":1,"status":"PASS",
        "meaning":"Scanner arithmetic and captured price-input integrity independently rechecked. Not validation of the price provider, future performance, trading costs or executable prices.",
        "audited_at_utc":datetime.now(timezone.utc).isoformat(),
        "market_date":market_date,
        "scan_sha256":digest(scan_path),
        "review_history_sha256":digest(reviews_path),
        "input_prices_sha256":price_sha,
        "input_file":str(snapshot.relative_to(HERE)),
        "all_pairs_recomputed":len(rows)-unavailable,
        "all_pairs_enumerated":len(rows),
        "independently_rechecked_eg_tests":sum(bool(m and m["cointegration_tested"]) for m in independent),
        "review_records":len(records),
        "deep_reviews_checked_against_latest_checkpoint":checked,
        "replay_examples_checked":replay_checked,
        "legacy_reviews_without_preserved_input":legacy,
        "limitations":[
            "SHA-256 verifies exact saved historical inputs, not vendor accuracy.",
            "Yahoo Finance historical adjusted closes are not a licensed real-time exchange feed.",
            "The model and retrospective paper-replay logic do not prove predictive profitability.",
            "Legacy reviews before this audit remain explicitly unverified.",
        ],
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=AUDIT)
    args=parser.parse_args()
    result=audit()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()

"""Read existing monthly contracts and aggregate accepted clean bars, without fit.

Only writes to this research line. Raw market coverage is an upper envelope,
never an economic label or the legacy 108-feature model training dataset.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from stage002_cohort_contract import build_cohort_bounds

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
PRIOR = ROOT / "research/lines/futures_trend_rollover_shape_same_volume/outputs"
OUT = LINE / "outputs/stage002_readiness_audit"


def receipt(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def counts(frame):
    return dict(rows=len(frame), months=int(frame.eval_date.nunique()))


def legacy_audit():
    parent = PRIOR / "stage267_monthly_samples_final"
    previous = json.loads((parent / "sample_summary.json").read_text())
    inputs = []
    for filename in ["all_sample_contract.csv", "informative_samples.csv"]:
        path = parent / filename
        actual = receipt(path)
        expected = next(x for x in previous["outputs"] if Path(x["path"]).name == filename)
        if actual["sha256"] != expected["sha256"]:
            raise ValueError("Stage267 input changed: " + filename)
        inputs.append(actual)
    original = pd.read_csv(parent / "all_sample_contract.csv")
    bounded = build_cohort_bounds(original)
    old = pd.read_csv(parent / "informative_samples.csv", usecols=["eval_date", "product_vt_symbol", "target_future_top_half_60d"])
    old["eval_date"] = pd.to_datetime(old.eval_date)
    final = old.merge(bounded, on=["eval_date", "product_vt_symbol"], validate="one_to_one", suffixes=("_legacy", ""))
    mature = bounded.loc[bounded.asof_member & bounded.label_complete]
    censored = mature.loc[~mature.label_observable]
    impacted = final.loc[final.unknown_label_count.gt(0)]
    ambiguous = final.loc[final.target_state.eq("ambiguous")]
    complete = final.loc[final.unknown_label_count.eq(0)]
    mismatched = final.loc[(final.target_state.eq("identified_top_half") & final.target_future_top_half_60d_legacy.ne(1)) |
                           (final.target_state.eq("identified_bottom_half") & final.target_future_top_half_60d_legacy.ne(0))]
    bounded.to_csv(OUT / "legacy_asof_cohort_bounds.csv", index=False)
    ambiguous.to_csv(OUT / "legacy_ambiguous_targets.csv", index=False)
    final.assign(year=final.eval_date.dt.year).groupby("year").agg(
        rows=("product_vt_symbol", "size"), months=("eval_date", "nunique"),
        ambiguous=("target_state", lambda x: int(x.eq("ambiguous").sum())),
        incomplete_cohort=("unknown_label_count", lambda x: int(x.gt(0).sum()))
    ).to_csv(OUT / "legacy_annual_diagnostics.csv")
    return dict(inputs=inputs, all_rows=len(original),
                mature_asof_universe=counts(mature), future_censored_asof_members=counts(censored),
                old_informative=counts(final), impacted_legacy_members=counts(impacted),
                ambiguous_legacy_targets=counts(ambiguous),
                no_future_coverage_deletion=counts(complete),
                identified_target_disagreements=len(mismatched),
                interpretation="Missing-label rank bounds only; not confidence bounds, new labels or PIT/OOS certification.")


def market_envelope():
    manifest_path = PRIOR / "stage266_clean_daily/dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    db = Path(manifest["database"]["path"])
    before = db.stat()
    if before.st_size != manifest["database"]["bytes"]:
        raise ValueError("accepted clean database size changed")
    calendar_path = PRIOR / "stage265_deep_daily/rqalpha/trading_dates.npy"
    raw = np.load(calendar_path, allow_pickle=False)
    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError("calendar requires explicit YYYYMMDD integers")
    calendar = pd.DatetimeIndex(pd.to_datetime(raw.astype(str), format="%Y%m%d"))
    start, end = map(pd.Timestamp, manifest["scope"])
    calendar = calendar[(calendar >= start) & (calendar <= end)]
    if calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("calendar must be ordered and unique")
    # Last observed day in October does not certify a completed October month.
    month_ends = pd.Series(calendar, index=calendar).groupby(calendar.to_period("M")).max()
    month_ends = month_ends.loc[month_ends.index < end.to_period("M")]
    conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        products = pd.read_sql_query("SELECT exchange,product,COUNT(*) AS metadata_contracts FROM contracts GROUP BY exchange,product", conn)
        daily = pd.read_sql_query("SELECT exchange,product,trade_date,COUNT(*) AS observed_contracts FROM daily_bars GROUP BY exchange,product,trade_date", conn)
    finally:
        conn.close()
    after = db.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("database changed during read-only audit")
    daily["trade_date"] = pd.to_datetime(daily.trade_date)
    if not daily.trade_date.isin(calendar).all():
        raise ValueError("observed trade date outside inherited calendar scope")
    by_product = {(str(ex), str(pr)): group for (ex, pr), group in daily.groupby(["exchange", "product"])}
    rows = []
    for item in products.itertuples(index=False):
        key = (str(item.exchange), str(item.product))
        observed = pd.Series(False, index=calendar)
        group = by_product.get(key)
        if group is not None:
            observed.loc[group.trade_date] = True
        past = observed.astype(int).rolling(120, min_periods=120).sum().eq(120)
        future = observed.astype(int).iloc[::-1].rolling(60, min_periods=60).sum().iloc[::-1].shift(-1).eq(60)
        for day in month_ends:
            index = int(calendar.get_loc(day))
            mature = index + 60 < len(calendar)
            rows.append(dict(eval_date=day, exchange=key[0], product=key[1],
                             product_vt_symbol=key[1]+"."+key[0],
                             monthly_average_F=key[1].endswith("_F"),
                             financial_future=key[0] == "CFFEX", observed_asof=bool(observed.loc[day]),
                             history120_coverage=bool(past.loc[day]),
                             asof_bar_envelope=bool(observed.loc[day] and past.loc[day]),
                             horizon60_mature=mature,
                             future60_coverage=bool(future.loc[day]),
                             label_end=(calendar[index+60] if mature else pd.NaT)))
    frame = pd.DataFrame(rows)
    frame["covered_120_60_envelope"] = frame.asof_bar_envelope & frame.horizon60_mature & frame.future60_coverage
    frame.to_csv(OUT / "all_market_monthly_bar_envelope.csv", index=False)
    products["has_observation"] = [tuple(x) in by_product for x in products[["exchange", "product"]].itertuples(index=False, name=None)]
    products.to_csv(OUT / "all_market_metadata_domain.csv", index=False)
    frame.assign(year=frame.eval_date.dt.year).groupby("year").agg(
        metadata_rows=("product", "size"), asof_bar_envelope=("asof_bar_envelope", "sum"),
        covered_120_60_envelope=("covered_120_60_envelope", "sum")
    ).to_csv(OUT / "all_market_annual_envelope.csv")
    ordinary = frame.loc[~frame.monthly_average_F]
    def summary(part):
        selected = part.loc[part.covered_120_60_envelope]
        asof = part.loc[part.asof_bar_envelope]
        return dict(metadata_rows=len(part), asof_bar_envelope=counts(asof),
                    covered_120_60_envelope=counts(selected),
                    pre2020_covered=counts(selected.loc[selected.eval_date.lt("2020-01-01")]),
                    historical_products_with_covered_envelope=int(selected.product_vt_symbol.nunique()))
    return dict(scope=manifest["scope"], accepted_bar_rows=manifest["records"],
                metadata_product_count=len(products), observed_product_count=len(by_product),
                no_observation_metadata=products.loc[~products.has_observation, ["exchange", "product"]].to_dict("records"),
                all_products=summary(frame), ordinary_futures_excluding_monthly_average_F=summary(ordinary),
                monthly_average_F=summary(frame.loc[frame.monthly_average_F]),
                inputs=[receipt(manifest_path), receipt(calendar_path)],
                database=dict(path=str(db), bytes=before.st_size, mtime_ns=before.st_mtime_ns,
                              inherited_accepted_sha256=manifest["database"]["sha256"],
                              current_full_sha256_recomputed=False, unchanged_during_audit=True),
                interpretation="Product-date bar presence only. Not 108-feature samples, strategy labels, independent observations, liquidity, verified historical listing or per-exchange PIT calendars.")


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    legacy = legacy_audit()
    market = market_envelope()
    result = dict(started_at_cst=started, completed_at_cst=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                  status="DATA_COHORT_AUDIT_ONLY_NO_MODEL_FIT", legacy=legacy, market=market,
                  scripts=[receipt(Path(__file__)), receipt(LINE / "tools/stage002_cohort_contract.py")],
                  model_fits=0, financial_backtests=0, orders=0,
                  formal_comparison_arms_created=False, training_ready=False,
                  reason="New economic label source, universe contract and upstream freeze clock remain unresolved; formal production identities missing.")
    (OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

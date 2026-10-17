"""Strict monthly sample census on fixed source artifacts; no model or replay.

Original 108 feature functions are called unchanged. Coverage, 120 complete past
source dates and 60 strictly subsequent source dates govern eligibility. Opening
OI is not a direct monthly feature requirement. Source-PNL conditions are not PIT
or deployable-strategy proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

import stage262_ai_sample_contract as window_contract

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
ORIGINAL_PATH = ROOT / "examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_walkforward.py"
ORIGINAL_SHA = "7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4"
WINDOW_CONTRACT_SHA = "6617da56dded1d16eb7215affb966b7498063fc706b38562e91df7f574c2ba7c"
BASELINE = LINE / "outputs/stage263_ai_data_expansion"
FIXED_PRODUCTS = ("lc.GFEX", "au.SHFE", "cu.SHFE", "MA.CZCE", "OI.CZCE", "AP.CZCE", "SM.CZCE", "SA.CZCE", "rb.SHFE", "jm.DCE", "hc.SHFE", "CF.CZCE", "FG.CZCE", "SH.CZCE", "si.GFEX", "ru.SHFE", "lh.DCE", "sp.SHFE")
KEYS = ["eval_date", "product_vt_symbol"]
DAILY_KEYS = ["date", "product_vt_symbol"]
HISTORY = 120
HORIZON = 60
MIN_CROSS_SECTION = 8
FUTURE = window_contract.FUTURE


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def receipt(path):
    path = Path(path).resolve()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


@lru_cache(maxsize=1)
def load_original():
    if sha(ORIGINAL_PATH) != ORIGINAL_SHA:
        raise ValueError("original_monthly_feature_source_changed")
    sys.path.insert(0, str(ORIGINAL_PATH.parent))
    spec = importlib.util.spec_from_file_location("stage267_original_monthly", ORIGINAL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if set(module.VT_SYMBOLS) != set(FIXED_PRODUCTS):
        raise ValueError("original_fixed_18_product_pool_changed")
    return module


def frozen_features():
    schema = json.loads((BASELINE / "expansion_summary.json").read_text())
    columns = schema["feature_columns"]
    if len(columns) != 108 or columns != sorted(set(columns)) or any(x.startswith("future_") for x in columns):
        raise ValueError("frozen_108_feature_schema_invalid")
    return columns


def explicit_booleans(values):
    mapping = {"true": True, "false": False, "1": True, "0": False}
    text = values.astype(str).str.lower().str.strip()
    if not text.isin(mapping).all():
        raise ValueError("coverage_flags_must_be_explicit_True_False_or_1_0")
    return text.map(mapping).astype(bool)


def days(values, label):
    parsed = pd.DatetimeIndex(pd.to_datetime(values, errors="raise"))
    if parsed.hasnans or parsed.tz is not None or not parsed.equals(parsed.normalize()):
        raise ValueError(label + " must be timezone-free midnight dates")
    return parsed


def calendar_days(values):
    result = days(values, "source calendar")
    if result.empty or result.has_duplicates or not result.is_monotonic_increasing:
        raise ValueError("source calendar must be nonempty, unique and increasing")
    return result


def authoritative_month_ends(calendar, source_end):
    """A truncated last calendar month is not certified by its last observed day."""
    dates = pd.Series(calendar, index=calendar)
    ends = dates.groupby(calendar.to_period("M")).max()
    final_month = calendar[-1].to_period("M")
    if not calendar[-1].is_month_end:
        ends = ends.loc[ends.index < final_month]
    return pd.DatetimeIndex(ends.loc[ends <= source_end])


def construct_samples(featured, coverage, calendar, *, source_end):
    if sha(window_contract.__file__) != WINDOW_CONTRACT_SHA:
        raise ValueError("frozen_stage262_window_contract_changed")
    calendar = calendar_days(calendar)
    source_end = pd.Timestamp(source_end)
    if source_end.tzinfo is not None or source_end != source_end.normalize() or source_end not in calendar:
        raise ValueError("source_end must be an explicit source-calendar date")
    frame = featured.copy()
    frame["date"] = days(frame.date, "daily date")
    if frame.duplicated(DAILY_KEYS).any():
        raise ValueError("duplicate daily product-date")
    if set(frame.product_vt_symbol) != set(FIXED_PRODUCTS):
        raise ValueError("daily must contain exactly the fixed 18 product pool")
    frame = frame.loc[frame.date <= source_end].sort_values(["product_vt_symbol", "date"]).reset_index(drop=True)
    used_calendar = calendar[(calendar >= frame.date.min()) & (calendar <= source_end)]
    grid = pd.MultiIndex.from_product([used_calendar, FIXED_PRODUCTS], names=DAILY_KEYS)
    if set(map(tuple, frame[DAILY_KEYS].to_numpy())) != set(grid) or len(frame) != len(grid):
        raise ValueError("daily must retain every expected source-calendar product row")
    features = frozen_features()
    generated = sorted(c for c in frame if any(c.endswith(f"_{w}d") for w in (20,60,120)) and not c.startswith(("future_", "target_", "sample_weight_")))
    if generated != features or not np.isfinite(frame[features].to_numpy(dtype=float)).all():
        raise ValueError("original_108_feature_columns_or_values_changed")
    if not np.isfinite(pd.to_numeric(frame.net_pnl, errors="raise")).all():
        raise ValueError("daily_net_pnl_must_be_finite")
    cov = coverage.copy()
    cov["date"] = days(cov.date, "coverage date")
    if cov.duplicated(DAILY_KEYS).any():
        raise ValueError("duplicate product coverage date")
    if not set(cov.product_vt_symbol) <= set(FIXED_PRODUCTS):
        raise ValueError("coverage outside fixed 18 product pool")
    for flag in ("observed", "mapped"):
        cov[flag] = explicit_booleans(cov[flag])
    cov = cov.set_index(DAILY_KEYS).reindex(grid)
    cov[["observed", "mapped"]] = cov[["observed", "mapped"]].fillna(False).astype(bool)
    cov = cov.reset_index()
    metadata = window_contract.build_window_metadata(frame, cov, history=HISTORY, horizon=HORIZON)
    valid = cov.assign(_valid=(cov.observed & cov.mapped).astype(int)).sort_values(["product_vt_symbol", "date"])
    valid["feature_observed_days"] = valid.groupby("product_vt_symbol")["_valid"].transform(lambda x: x.rolling(HISTORY, min_periods=1).sum()).astype(int)
    metadata = metadata.merge(valid[["date", "product_vt_symbol", "feature_observed_days"]].rename(columns={"date": "eval_date"}), on=KEYS, validate="one_to_one")
    # Exact forward sum is recomputed to prevent the legacy min_periods=30 label.
    frame["_strict_future"] = frame.groupby("product_vt_symbol")["net_pnl"].transform(lambda x: x.iloc[::-1].rolling(HORIZON, min_periods=HORIZON).sum().iloc[::-1].shift(-1))
    frame["legacy_partial_future_net_pnl_60d"] = frame[FUTURE]
    eval_dates = authoritative_month_ends(calendar, source_end)
    all_samples = frame.loc[frame.date.isin(eval_dates)].rename(columns={"date": "eval_date"}).merge(metadata, on=KEYS, validate="one_to_one")
    valid_label = all_samples.label_complete & all_samples.label_coverage_ok & all_samples._strict_future.notna()
    all_samples[FUTURE] = all_samples._strict_future.where(valid_label)
    all_samples.drop(columns="_strict_future", inplace=True)
    all_samples["eligible_before_cross_section"] = all_samples.eligible & all_samples[FUTURE].notna()
    all_samples["eligible_cross_section_count"] = all_samples.groupby("eval_date").eligible_before_cross_section.transform("sum").astype(int)
    all_samples["eligible"] = all_samples.eligible_before_cross_section & all_samples.eligible_cross_section_count.ge(MIN_CROSS_SECTION)
    all_samples["all_future_pnl_zero"] = False
    all_samples["constant_future_pnl"] = False
    all_samples["informative"] = False
    for name in ("future_rank_pct_60d", "future_rank_centered_60d", window_contract.TARGET, window_contract.WEIGHT):
        all_samples[name] = np.nan
    for _, group in all_samples.loc[all_samples.eligible].groupby("eval_date", sort=True):
        zero = bool(group[FUTURE].eq(0).all())
        constant = group[FUTURE].nunique() == 1
        all_samples.loc[group.index, "all_future_pnl_zero"] = zero
        all_samples.loc[group.index, "constant_future_pnl"] = constant
        if not constant:
            ranks = group[FUTURE].rank(method="average", pct=True)
            all_samples.loc[group.index, "informative"] = True
            all_samples.loc[group.index, "future_rank_pct_60d"] = ranks
            all_samples.loc[group.index, "future_rank_centered_60d"] = ranks-.5
            all_samples.loc[group.index, window_contract.TARGET] = ((ranks-.5)>0).astype(int)
            all_samples.loc[group.index, window_contract.WEIGHT] = (ranks-.5).abs().clip(.20,.60)
    all_samples.sort_values(KEYS, inplace=True)
    all_samples.reset_index(drop=True, inplace=True)
    return {"all_samples": all_samples, "qualified_samples": all_samples.loc[all_samples.eligible].copy(),
            "informative_samples": all_samples.loc[all_samples.informative].copy(), "feature_columns": features,
            "used_source_calendar": used_calendar}


def compare_baseline(current, baseline):
    current_keys = {(pd.Timestamp(r.eval_date), r.product_vt_symbol) for r in current[KEYS].itertuples(index=False)}
    baseline_keys = {(pd.Timestamp(r.eval_date), r.product_vt_symbol) for r in baseline[KEYS].itertuples(index=False)}
    if len(current_keys) != len(current) or len(baseline_keys) != len(baseline):
        raise ValueError("duplicate baseline/current monthly key")
    new, lost = current_keys-baseline_keys, baseline_keys-current_keys
    return {"current_rows": len(current_keys), "baseline_rows": len(baseline_keys), "common_rows": len(current_keys & baseline_keys),
            "new_rows": len(new), "lost_rows": len(lost), "current_months": len({k[0] for k in current_keys}),
            "baseline_months": len({k[0] for k in baseline_keys}), "new_months": len({k[0] for k in current_keys}-{k[0] for k in baseline_keys}),
            "lost_months": len({k[0] for k in baseline_keys}-{k[0] for k in current_keys}),
            "new_rows_by_year": {str(y): sum(k[0].year==y for k in new) for y in sorted({k[0].year for k in new})},
            "boundary": "Exact product-month key comparison only; changed replay path means this is not an expansion causal effect."}


def prepare_daily(positions, entries, coverage, calendar):
    original = load_original()
    required_position = ["date", "vt_symbol", "start_pos", "end_pos", "pos_change", "trade_count", "turnover", "commission", "slippage", "holding_pnl", "trading_pnl", "total_pnl", "net_pnl"]
    position = pd.read_csv(positions, usecols=required_position)
    position["date"] = days(position.date, "position date")
    if position.duplicated(["date", "vt_symbol"]).any():
        raise ValueError("duplicate source contract-date PNL")
    position["product_vt_symbol"] = position.vt_symbol.map(original.product_from_contract)
    if not set(position.product_vt_symbol) <= set(FIXED_PRODUCTS):
        raise ValueError("position source outside original 18 product pool")
    for name in required_position[2:]:
        if not np.isfinite(pd.to_numeric(position[name], errors="raise")).all():
            raise ValueError("position economic column must be finite, never filled:" + name)
    if not position.date.isin(calendar).all():
        raise ValueError("position source date absent from explicit calendar")
    source_end = position.date.max()
    candidate = pd.read_csv(entries, usecols=["date", "product_vt_symbol", "candidate_status"])
    if not candidate.empty:
        candidate["date"] = days(candidate.date, "candidate date")
        if not set(candidate.product_vt_symbol) <= set(FIXED_PRODUCTS):
            raise ValueError("candidate source outside original 18 product pool")
        if not candidate.date.isin(calendar).all() or candidate.date.gt(source_end).any():
            raise ValueError("candidate source dates outside explicit PNL/calendar interval")
    previous_paths = original.POSITION_CHANGES_PATH, original.ENTRY_SNAPSHOTS_PATH
    try:
        original.POSITION_CHANGES_PATH, original.ENTRY_SNAPSHOTS_PATH = Path(positions), Path(entries)
        daily = original.build_product_daily()
    finally:
        original.POSITION_CHANGES_PATH, original.ENTRY_SNAPSHOTS_PATH = previous_paths
    used = calendar[calendar <= source_end]
    grid = pd.MultiIndex.from_product([used, FIXED_PRODUCTS], names=DAILY_KEYS)
    daily = daily.set_index(DAILY_KEYS).reindex(grid).reset_index()
    numeric = [c for c in daily if c not in DAILY_KEYS]
    daily[numeric] = daily[numeric].fillna(0.0)
    # The original empty-file branch returns only keys. Complete its no-event
    # schema with the same 0/neutral1 values used on no-event days of a nonempty
    # candidate file; never fabricate a candidate or an economic observation.
    candidate_aggregates = ["candidate_count", "opened_count", "selected_volume_sum", "selected_volume_ungated_sum", "corr_gate_enabled_count", "volume_tilt_applied_count",
                            "avg_corr_gate_weight", "avg_same_direction_active_count", "avg_same_direction_max_corr", "avg_pairwise_score", "best_pairwise_rank",
                            "avg_volume_tilt_multiplier", "avg_volume_tilt_score_gap", "avg_volume_tilt_top_gap", "avg_active_positions_before", "breakout_rate",
                            "bullish_alignment_rate", "bearish_alignment_rate", "avg_rsi", "avg_loss_streak", "opened_rate"]
    for column in candidate_aggregates:
        if column not in daily:
            if not candidate.empty:
                raise ValueError("nonempty_original_candidate_aggregation_schema_missing:" + column)
            daily[column] = 1.0 if column in {"avg_corr_gate_weight", "avg_volume_tilt_multiplier"} else 0.0
    observed = set(map(tuple, position[DAILY_KEYS].drop_duplicates().to_numpy()))
    stated = coverage.loc[explicit_booleans(coverage.observed), DAILY_KEYS]
    if not set(map(tuple, stated.to_numpy())) <= observed:
        raise ValueError("coverage_observed_without_source_PNL_observation")
    return original.add_rolling_features(daily), source_end


def row_stats(frame):
    return {"rows": len(frame), "months": frame.eval_date.nunique(),
            "first": None if frame.empty else str(frame.eval_date.min().date()), "last": None if frame.empty else str(frame.eval_date.max().date()),
            "zero_future_rows": int(frame[FUTURE].eq(0).sum()), "max_label_end": None if frame.empty or frame.label_end.isna().all() else str(frame.label_end.max().date())}


def write_json(path, value):
    def convert(x):
        if isinstance(x, (np.integer, np.bool_)): return int(x)
        if isinstance(x, (pd.Timestamp, datetime)): return x.isoformat()
        raise TypeError(type(x).__name__)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=convert, allow_nan=False)+"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positions", type=Path, required=True)
    parser.add_argument("--entries", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=LINE/"outputs/stage267_monthly_samples")
    parser.add_argument("--baseline-samples", type=Path, default=BASELINE/"eligible_samples.csv")
    parser.add_argument("--asof", help="Explicit after-close date for mature training-row census only")
    args = parser.parse_args(argv)
    if (args.output_dir/"sample_summary.json").exists():
        raise FileExistsError("monthly census already exists; do not silently overwrite")
    paths = {k: getattr(args,k) for k in ("positions","entries","coverage","calendar","baseline_samples")}
    inputs = {k: receipt(v) for k,v in paths.items()}
    calendar = calendar_days(pd.read_csv(args.calendar)["date"])
    coverage = pd.read_csv(args.coverage)
    coverage["date"] = days(coverage.date,"coverage date")
    featured, source_end = prepare_daily(args.positions,args.entries,coverage,calendar)
    result = construct_samples(featured,coverage,calendar,source_end=source_end)
    baseline = pd.read_csv(args.baseline_samples,parse_dates=["eval_date"])
    all_rows,qualified,informative = (result[k] for k in ("all_samples","qualified_samples","informative_samples"))
    asof = source_end if args.asof is None else pd.Timestamp(args.asof)
    if asof.tzinfo is not None or asof!=asof.normalize() or asof>source_end:
        raise ValueError("asof must be a timezone-free source date no later than source_end")
    mature = informative.loc[informative.label_end.le(asof)&informative.eval_date.lt(asof)]
    months = []
    for day,group in all_rows.groupby("eval_date",sort=True):
        q=group.loc[group.eligible]; info=group.loc[group.informative]
        months.append({"eval_date":day,"all_rows":len(group),"qualified_rows":len(q),"informative_rows":len(info),
                       "all_future_pnl_zero":bool(len(q) and q[FUTURE].eq(0).all()),"constant_future_pnl":bool(len(q) and q[FUTURE].nunique()==1),
                       "label_end":None if q.empty else q.label_end.max(), "history_rejected":int((~group.history_ok).sum()),
                       "feature_coverage_rejected":int((~group.feature_coverage_ok).sum()),"label_incomplete":int((~group.label_complete).sum()),
                       "label_coverage_rejected":int((~group.label_coverage_ok).sum())})
    monthly = pd.DataFrame(months)
    annual=[]
    for year,group in all_rows.groupby(all_rows.eval_date.dt.year,sort=True):
        annual.append({"year":int(year),**{"all_"+k:v for k,v in row_stats(group).items()},
                       **{"qualified_"+k:v for k,v in row_stats(group.loc[group.eligible]).items()},
                       **{"informative_"+k:v for k,v in row_stats(group.loc[group.informative]).items()}})
    args.output_dir.mkdir(parents=True,exist_ok=True)
    outputs=[]
    for filename,frame in (("all_sample_contract.csv",all_rows),("qualified_samples.csv",qualified),("informative_samples.csv",informative),("monthly_counts.csv",monthly),("annual_sample_counts.csv",pd.DataFrame(annual))):
        path=args.output_dir/filename;frame.to_csv(path,index=False);outputs.append(receipt(path))
    feature_contract={"feature_count":108,"feature_columns":result["feature_columns"],"original_module":receipt(ORIGINAL_PATH),
                      "window_contract_module":receipt(window_contract.__file__),"feature_schema_reference":receipt(BASELINE/"expansion_summary.json"),
                      "history_source_dates":HISTORY,"label_source_dates":HORIZON,"label_interval":"(eval_date, label_end]", "original_18_products":list(FIXED_PRODUCTS),
                      "open_oi_direct_dependency":False,"financial_backtests":0,"model_fits":0}
    write_json(args.output_dir/"feature_contract.json",feature_contract)
    if inputs!={k:receipt(v) for k,v in paths.items()}:
        raise RuntimeError("source_input_changed_while_constructing_census")
    summary={"generated_at":datetime.now().astimezone().isoformat(),"status":"STRICT_MONTHLY_SAMPLE_CENSUS_NO_MODEL_FIT","inputs":inputs,
             "runtime":{"python":platform.python_version(),"pandas":pd.__version__,"numpy":np.__version__},
             "script":receipt(__file__),"feature_contract":receipt(args.output_dir/"feature_contract.json"),"outputs":outputs,
             "source_start":str(result["used_source_calendar"][0].date()),"source_end":str(source_end.date()),"all":row_stats(all_rows),"qualified":row_stats(qualified),"informative":row_stats(informative),
             "all_zero_future_months":int(monthly.all_future_pnl_zero.sum()),"all_zero_future_rows":int(qualified.all_future_pnl_zero.sum()),
             "constant_nonzero_future_months":int((monthly.constant_future_pnl&~monthly.all_future_pnl_zero).sum()),
             "mature_asof":{"date":str(asof.date()),**row_stats(mature)},"vs_stage263_informative_sample_keys":compare_baseline(informative,baseline),
             "same_source_history_split":{
                 "method":"Filter eval_date on identical source, features, coverage, ranks, targets and weights; no replay/window reset or model fit.",
                 "qualified":{name:row_stats(data) for name,data in {"all_history":qualified,"eval_2020_plus":qualified.loc[qualified.eval_date.ge("2020-01-01")],"eval_pre2020":qualified.loc[qualified.eval_date.lt("2020-01-01")]}.items()},
                 "informative":{name:row_stats(data) for name,data in {"all_history":informative,"eval_2020_plus":informative.loc[informative.eval_date.ge("2020-01-01")],"eval_pre2020":informative.loc[informative.eval_date.lt("2020-01-01")]}.items()},
                 "informative_mature_asof":{name:row_stats(data) for name,data in {"all_history":mature,"eval_2020_plus":mature.loc[mature.eval_date.ge("2020-01-01")],"eval_pre2020":mature.loc[mature.eval_date.lt("2020-01-01")]}.items()},
             },
             "feature_count":108,"feature_values_from_original_functions":True,"original_pool_count":18,"strict_month_end_from_explicit_calendar":True,
             "model_fits":0,"financial_backtests":0,"orders":0,"main_database_writes":0,"training_models_ready":False,
             "limits":["Same 108 feature functions; full120 coverage and60 labels are stricter eligibility than original partial windows.",
                       "Zero/constant target months excluded from informative set independently of model outcomes; qualified rows retain null ranks/targets for those months.",
                       "Exact added sample keys vs Stage263 are availability counts, not causal performance improvement or independent observations.",
                       "Source strategy is fixed ex-post specification; this census does not establish historical PIT, execution or profitability.",
                       "legacy108_row_usable/open_oi CSV gates are not necessary monthly108 eligibility conditions."]}
    write_json(args.output_dir/"sample_summary.json",summary)
    print(json.dumps({k:summary[k] for k in ("status","all","qualified","informative","all_zero_future_months","vs_stage263_informative_sample_keys")},ensure_ascii=False))
    return 0


if __name__=="__main__":raise SystemExit(main())

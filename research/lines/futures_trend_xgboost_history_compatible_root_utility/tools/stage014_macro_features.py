from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/stage013b_cffex_root_source_http"
OUTPUT = ROOT / "artifacts/stage014_macro_features"
BASE_SPEC = ROOT / "stages/stage004_model_spec.json"
EVENTS = ROOT / "artifacts/stage001_history_qualification/event_features.csv"
ROOTS = ("IF", "IH", "IC", "T", "TF", "TS")
RAW_FEATURES = ["cffex_equity_momentum_20d", "cffex_rates_momentum_20d", "cffex_equity_vol_ratio_20_120",
                "cffex_rates_vol_ratio_20_120", "cffex_equity_rates_corr_60d"]
FEATURES = ["directional_" + name if index < 2 else name for index, name in enumerate(RAW_FEATURES)]


def identity(path):
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def validate_dates(values):
    if not values.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise RuntimeError("macro_date_format_invalid")
    try:
        pd.to_datetime(values, format="%Y-%m-%d", errors="raise")
    except ValueError as exc:
        raise RuntimeError("macro_date_value_invalid") from exc


def daily_factors(selected):
    data = selected[["date", "root", "product_return"]].copy()
    validate_dates(data.date)
    if data.duplicated(["date", "root"]).any():
        raise RuntimeError("macro_duplicate_root_date")
    if set(data.root.unique()) != set(ROOTS):
        raise RuntimeError("macro_root_inventory_invalid")
    wide = data.pivot(index="date", columns="root", values="product_return").reindex(columns=ROOTS).sort_index()
    if not np.isfinite(wide.to_numpy(dtype=float)).all() or wide.le(-1).any().any():
        raise RuntimeError("macro_root_return_missing_or_invalid")
    equity = wide[["IF", "IH", "IC"]].mean(axis=1)
    rates = wide[["T", "TF", "TS"]].mean(axis=1)
    frame = pd.DataFrame(index=wide.index)
    frame["equity_return"] = equity
    frame["rates_return"] = rates
    for name, values in (("equity", equity), ("rates", rates)):
        frame[f"cffex_{name}_momentum_20d"] = values.rolling(20, min_periods=20).apply(
            lambda window: np.prod(1.0 + window) - 1.0, raw=True)
        denominator = values.rolling(120, min_periods=120).std(ddof=1)
        frame[f"cffex_{name}_vol_ratio_20_120"] = values.rolling(20, min_periods=20).std(ddof=1) / denominator.where(denominator.gt(0))
    frame["cffex_equity_rates_corr_60d"] = equity.rolling(60, min_periods=60).corr(rates)
    return frame.reset_index()


def decision_context(factors, mapping):
    dates = mapping[["decision_date", "source_date", "coverage_status"]].copy()
    validate_dates(dates.decision_date)
    validate_dates(dates.source_date)
    if dates.decision_date.duplicated().any() or factors.date.duplicated().any():
        raise RuntimeError("macro_decision_or_source_duplicate")
    if not dates.source_date.lt(dates.decision_date).all():
        raise RuntimeError("macro_source_not_strictly_prior")
    if not dates.coverage_status.eq("available").all():
        raise RuntimeError("macro_source_not_available")
    result = dates.merge(factors[["date", *RAW_FEATURES]].rename(columns={"date": "source_date"}),
                         on="source_date", how="left", validate="many_to_one", sort=False)
    if not np.isfinite(result[RAW_FEATURES].to_numpy(dtype=float)).all():
        raise RuntimeError("macro_decision_features_nonfinite")
    return result


def features_for_decision(context, day, direction):
    if direction not in ("long", "short"):
        raise RuntimeError("macro_direction_invalid")
    row = context.loc[context.decision_date.eq(day)]
    if len(row) != 1 or not row.source_date.lt(day).all() or not row.coverage_status.eq("available").all():
        raise RuntimeError("macro_decision_context_missing_or_invalid")
    values = row[RAW_FEATURES].iloc[0].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise RuntimeError("macro_decision_features_nonfinite")
    side = 1 if direction == "long" else -1
    return {name: float(value * (side if index < 2 else 1)) for index, (name, value) in enumerate(zip(FEATURES, values))}


def candidate_spec(original):
    result = copy.deepcopy(original)
    if set(FEATURES) & set(result["features"]):
        raise RuntimeError("macro_candidate_features_already_present")
    result["features"] = [*result["features"], *FEATURES]
    return result


def source_inputs():
    summary_path = SOURCE / "summary.json"
    if identity(summary_path)["sha256"] != "2214130f71e7ce115d1a16953500d444ac5900a9f895ec4ac6c2628a393b466c":
        raise RuntimeError("macro_source_summary_changed")
    summary = json.loads(summary_path.read_text())
    if summary["status"] != "source_qualified_for_feature_contract" or summary["event_coverage"] != {"available": 276}:
        raise RuntimeError("macro_source_qualification_failed")
    for name, expected in summary["outputs"].items():
        if identity(SOURCE / name) != expected:
            raise RuntimeError(f"macro_source_output_changed:{name}")
    files = json.loads((SOURCE / "input_manifest.json").read_text())
    if any(identity(Path(path)) != expected for path, expected in files.items()):
        raise RuntimeError("macro_source_inputs_changed")
    if identity(BASE_SPEC)["sha256"] != "9065479d7c5ac457c2f92ba3e8aa4ec5a3b7c9150dcf6497deeb815957d44a16":
        raise RuntimeError("macro_original_model_spec_changed")
    files.update({str(SOURCE / name): expected for name, expected in summary["outputs"].items()})
    added = [summary_path, BASE_SPEC, Path(__file__), ROOT / "tests/test_stage014_macro_features.py",
             ROOT / "stages/20260906_0332_stage014_macro_feature_contract.md"]
    files.update({str(path): identity(path) for path in added})
    return files, summary


def run():
    if OUTPUT.exists():
        raise RuntimeError("macro_feature_output_already_exists")
    files, source_summary = source_inputs()
    OUTPUT.mkdir(parents=True)
    save(OUTPUT / "input_manifest.json", files)
    selected = pd.read_csv(SOURCE / "same_contract_returns.csv.gz", float_precision="round_trip")
    factors = daily_factors(selected)
    calendar = pd.read_csv(SOURCE / "calendar_coverage.csv")
    context = decision_context(factors, calendar)
    event_columns = ["event_id", "candidate_index", "decision_date", "product_vt_symbol", "contract_vt_symbol", "direction"]
    events = pd.read_csv(EVENTS, usecols=event_columns)
    source_events = pd.read_csv(SOURCE / "event_coverage.csv")
    if len(events) != 276 or events.event_id.duplicated().any() or set(events.event_id) != set(source_events.event_id):
        raise RuntimeError("macro_event_inventory_changed")
    records = []
    for row in events.to_dict("records"):
        values = features_for_decision(context, row["decision_date"], row["direction"])
        source_date = context.loc[context.decision_date.eq(row["decision_date"]), "source_date"].iloc[0]
        previous = source_events.loc[source_events.event_id.eq(row["event_id"])].iloc[0]
        if source_date != previous.source_date or any(row[key] != previous[key] for key in event_columns if key != "candidate_index"):
            raise RuntimeError("macro_event_source_identity_mismatch")
        records.append({**row, "source_date": source_date, **values})
    features = pd.DataFrame(records)
    new_spec = candidate_spec(json.loads(BASE_SPEC.read_text()))
    if len(new_spec["features"]) != 15 or len(context) != 1614:
        raise RuntimeError("macro_frozen_dimensions_changed")
    for name, data in {"macro_daily.csv": factors, "decision_context.csv": context, "event_macro_features.csv": features}.items():
        data.to_csv(OUTPUT / name, index=False)
    save(OUTPUT / "candidate_model_spec.json", new_spec)
    if any(identity(Path(path)) != expected for path, expected in files.items()):
        raise RuntimeError("macro_inputs_changed_during_run")
    outputs = {path.name: identity(path) for path in OUTPUT.iterdir() if path.is_file()}
    summary = {"status": "features_qualified_no_models", "event_count": len(features), "calendar_count": len(context),
               "source_factor_days": len(factors), "added_features": FEATURES, "total_candidate_features": 15,
               "event_feature_unique_counts": features[FEATURES].nunique().to_dict(),
               "event_features_finite": bool(np.isfinite(features[FEATURES].to_numpy()).all()),
               "first_month_60_mature": source_summary["first_month_60_available_mature"],
               "new_historical_fits": 0, "new_predictions": 0, "new_labels": 0, "new_backtests": 0, "reviewers": 0,
               "historical_vintage_verified": False, "input_count": len(files), "outputs": outputs,
               "created_at_utc": datetime.now(timezone.utc).isoformat()}
    save(OUTPUT / "summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=False))

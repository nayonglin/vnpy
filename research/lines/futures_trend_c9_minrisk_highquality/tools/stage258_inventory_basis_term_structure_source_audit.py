from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage258"
MODEL_TAG = "stage258_inventory_basis_term_structure_source_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage258_inventory_basis_term_structure_source_audit"

SUPPLY_CACHE_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs" / "external_supply_demand_cache"
BASIS_CACHE_FILES = (
    SUPPLY_CACHE_DIR / "supply_demand_basis_20200101_20221231.csv",
    SUPPLY_CACHE_DIR / "supply_demand_basis_20230101_20260417.csv",
)
WAREHOUSE_CACHE_FILES = (
    SUPPLY_CACHE_DIR / "supply_demand_warehouse_20200101_20221231.csv",
    SUPPLY_CACHE_DIR / "supply_demand_warehouse_20230101_20260417.csv",
)

STAGE026_DIR = LINE_DIR / "outputs" / "stage026_term_structure_carry_alignment_forensics"
STAGE026_PREFIX = "qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics"
STAGE026_TAG = "stage026_term_structure_carry_alignment_forensics_v1"

STAGE027_DIR = LINE_DIR / "outputs" / "stage027_supply_demand_inventory_forensics"
STAGE027_PREFIX = "qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics"
STAGE027_TAG = "stage027_supply_demand_inventory_forensics_v1"

STAGE060_DIR = LINE_DIR / "outputs" / "stage060_relative_basis_shock_audit"
STAGE060_PREFIX = "qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit"
STAGE060_TAG = "stage060_relative_basis_shock_audit_v1"

STAGE087_DIR = LINE_DIR / "outputs" / "stage087_external_preentry_authorized_coverage_gap_audit"
STAGE087_PREFIX = "qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit"
STAGE087_TAG = "stage087_external_preentry_authorized_coverage_gap_audit_v1"

STAGE095_DIR = LINE_DIR / "outputs" / "stage095_full_numeric_feature_extraction_stability_audit"
STAGE095_PREFIX = "qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit"
STAGE095_TAG = "stage095_full_numeric_feature_extraction_stability_audit_v1"

STAGE099_DIR = LINE_DIR / "outputs" / "stage099_finer_source_feasibility_manifest"
STAGE099_PREFIX = "qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest"
STAGE099_TAG = "stage099_finer_source_feasibility_manifest_v1"

STAGE239_DIR = LINE_DIR / "outputs" / "stage239_read_only_universal_signal_quality_audit"
STAGE239_PREFIX = "qmt_roll_stage239_c9_minrisk_read_only_universal_signal_quality_audit"
STAGE239_TAG = "stage239_read_only_universal_signal_quality_audit_v1"

STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"

STAGE026_FEATURE_IN = STAGE026_DIR / f"{STAGE026_PREFIX}_features_{STAGE026_TAG}.csv"
STAGE027_FEATURE_IN = STAGE027_DIR / f"{STAGE027_PREFIX}_features_{STAGE027_TAG}.csv"
STAGE060_FEATURE_IN = STAGE060_DIR / f"{STAGE060_PREFIX}_features_{STAGE060_TAG}.csv"
STAGE087_SCORECARD_IN = STAGE087_DIR / f"{STAGE087_PREFIX}_source_scorecard_{STAGE087_TAG}.csv"
STAGE095_FIELD_IN = STAGE095_DIR / f"{STAGE095_PREFIX}_field_summary_{STAGE095_TAG}.csv"
STAGE095_FEATURE_IN = STAGE095_DIR / f"{STAGE095_PREFIX}_feature_rows_{STAGE095_TAG}.csv"
STAGE095_AGG_IN = STAGE095_DIR / f"{STAGE095_PREFIX}_aggregation_source_summary_{STAGE095_TAG}.csv"
STAGE099_MANIFEST_IN = STAGE099_DIR / f"{STAGE099_PREFIX}_manifest_{STAGE099_TAG}.csv"
STAGE239_JOINED_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_joined_signal_label_audit_{STAGE239_TAG}.csv"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ASSET_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_asset_inventory_{MODEL_TAG}.csv"
FIELD_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_contract_{MODEL_TAG}.csv"
ENTRY_COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_coverage_{MODEL_TAG}.csv"
ENTRY_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_exchange_year_coverage_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_physical_contract_coverage_{MODEL_TAG}.png"
FIELD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_readiness_heatmap_{MODEL_TAG}.png"
ASSET_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_asset_inventory_chart_{MODEL_TAG}.png"
ENTRY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_exchange_year_coverage_heatmap_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"

LOOKBACK_DAYS = 7

REQUIRED_FIELDS = [
    "trade_date",
    "product",
    "exchange_inventory",
    "warehouse_receipt",
    "warehouse_change",
    "spot_price",
    "near_future_price",
    "deferred_future_price",
    "basis",
    "curve_slope",
    "source_timestamp",
    "publication_lag_calendar",
    "raw_path",
    "raw_hash",
    "source_license",
    "unit",
    "product_mapping",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _product_root(vt_symbol: Any, product: Any = "") -> str:
    product_text = str(product) if not pd.isna(product) else ""
    if product_text and product_text.lower() != "nan":
        return product_text.split(".")[0].upper()
    match = re.match(r"^([A-Za-z]+)", str(vt_symbol))
    return match.group(1).upper() if match else str(vt_symbol).split(".")[0].upper()


def _entry_key(vt_symbol: Any, date_value: Any) -> str:
    date = pd.to_datetime(date_value, errors="coerce")
    if pd.isna(date):
        return f"{vt_symbol}|"
    return f"{vt_symbol}|{date.strftime('%Y-%m-%d')}"


def _row(frame: pd.DataFrame, **equals: str) -> dict[str, Any]:
    current = frame
    for column, value in equals.items():
        if column not in current.columns:
            return {}
        current = current[current[column].astype(str).eq(str(value))]
    if current.empty:
        return {}
    return current.iloc[0].to_dict()


def _load_supply_cache(files: tuple[Path, ...], kind: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in files:
        frame = _read_csv(path)
        frame["source_file"] = str(path)
        frames.append(frame)
    cache = pd.concat(frames, ignore_index=True)
    cache["date_dt"] = pd.to_datetime(cache["date"].astype(str), format="%Y%m%d", errors="coerce")
    if kind == "basis":
        cache["product_root"] = cache["symbol"].astype(str).str.upper()
    else:
        cache["product_root"] = cache["product_code"].astype(str).str.upper()
    cache = cache[cache["date_dt"].notna()].copy()
    cache.sort_values(["product_root", "date_dt"], inplace=True)
    cache.reset_index(drop=True, inplace=True)
    return cache


def _load_inputs() -> dict[str, Any]:
    return {
        "basis_cache": _load_supply_cache(BASIS_CACHE_FILES, "basis"),
        "warehouse_cache": _load_supply_cache(WAREHOUSE_CACHE_FILES, "warehouse"),
        "stage026_feature": _read_csv(STAGE026_FEATURE_IN),
        "stage027_feature": _read_csv(STAGE027_FEATURE_IN),
        "stage060_feature": _read_csv(STAGE060_FEATURE_IN),
        "stage087_scorecard": _read_csv(STAGE087_SCORECARD_IN),
        "stage095_field": _read_csv(STAGE095_FIELD_IN),
        "stage095_feature": _read_csv(STAGE095_FEATURE_IN),
        "stage095_agg": _read_csv(STAGE095_AGG_IN),
        "stage099_manifest": _read_csv(STAGE099_MANIFEST_IN),
        "stage239_joined": _read_csv(STAGE239_JOINED_IN),
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
    }


def _cache_stats(cache: pd.DataFrame, kind: str) -> dict[str, Any]:
    if cache.empty:
        return {
            "row_count": 0,
            "product_count": 0,
            "date_count": 0,
            "start_date": "",
            "end_date": "",
            "source_count": 0,
        }
    return {
        "row_count": len(cache),
        "product_count": int(cache["product_root"].nunique()),
        "date_count": int(cache["date_dt"].nunique()),
        "start_date": cache["date_dt"].min().strftime("%Y-%m-%d"),
        "end_date": cache["date_dt"].max().strftime("%Y-%m-%d"),
        "source_count": int(cache["source_file"].nunique()),
        "kind": kind,
    }


def _find_prior(cache: pd.DataFrame, product_root: str, entry_date: pd.Timestamp) -> dict[str, Any]:
    if pd.isna(entry_date):
        return {}
    product_cache = cache[cache["product_root"].eq(product_root)]
    if product_cache.empty:
        return {}
    target = entry_date - pd.Timedelta(days=1)
    floor = entry_date - pd.Timedelta(days=LOOKBACK_DAYS)
    subset = product_cache[(product_cache["date_dt"] <= target) & (product_cache["date_dt"] >= floor)]
    if subset.empty:
        return {}
    return subset.iloc[-1].to_dict()


def _build_asset_inventory(inputs: dict[str, Any]) -> pd.DataFrame:
    basis_cache = inputs["basis_cache"]
    warehouse_cache = inputs["warehouse_cache"]
    stage026 = inputs["stage026_feature"]
    stage027 = inputs["stage027_feature"]
    stage060 = inputs["stage060_feature"]
    stage095_feature = inputs["stage095_feature"]
    stage095_agg = inputs["stage095_agg"]
    scorecard = inputs["stage087_scorecard"]
    manifest = inputs["stage099_manifest"]

    basis_stats = _cache_stats(basis_cache, "basis")
    warehouse_stats = _cache_stats(warehouse_cache, "warehouse")
    warehouse_feature = stage095_feature[stage095_feature["source_family"].astype(str).eq("warehouse")].copy()
    warehouse_agg = stage095_agg[stage095_agg["source_family"].astype(str).eq("warehouse")].copy()
    route = _row(manifest, route_id="inventory_basis_term_structure")
    basis_score = _row(scorecard, source_id="basis")
    warehouse_score = _row(scorecard, source_id="warehouse")

    rows = [
        {
            "asset_id": "legacy_supply_demand_basis_cache",
            "asset_family": "basis",
            "layer": "spot_basis_near_dominant_cache",
            "row_count": basis_stats["row_count"],
            "file_count": basis_stats["source_count"],
            "product_count": basis_stats["product_count"],
            "date_count": basis_stats["date_count"],
            "linked_lot_or_entry_count": _to_float(basis_score.get("ready_lot_count"), 0.0),
            "start_date": basis_stats["start_date"],
            "end_date": basis_stats["end_date"],
            "has_inventory": 0,
            "has_spot_price": 1,
            "has_basis": 1,
            "has_curve_slope": 0,
            "has_raw_hash": 0,
            "has_source_timestamp": 0,
            "has_source_license": 0,
            "prior_direct_rule_closed": 1,
            "strategy_rule_allowed": 0,
            "notes": "Spot/near/dominant basis cache is available, but provenance, publication timestamp, and license are absent.",
        },
        {
            "asset_id": "legacy_supply_demand_warehouse_cache",
            "asset_family": "warehouse",
            "layer": "warehouse_receipt_product_cache",
            "row_count": warehouse_stats["row_count"],
            "file_count": warehouse_stats["source_count"],
            "product_count": warehouse_stats["product_count"],
            "date_count": warehouse_stats["date_count"],
            "linked_lot_or_entry_count": _to_float(warehouse_score.get("ready_lot_count"), 0.0),
            "start_date": warehouse_stats["start_date"],
            "end_date": warehouse_stats["end_date"],
            "has_inventory": 1,
            "has_spot_price": 0,
            "has_basis": 0,
            "has_curve_slope": 0,
            "has_raw_hash": 0,
            "has_source_timestamp": 0,
            "has_source_license": 0,
            "prior_direct_rule_closed": 1,
            "strategy_rule_allowed": 0,
            "notes": "Product-level warehouse cache is available, but DCE/SHFE provenance and raw hashes are not complete.",
        },
        {
            "asset_id": "stage095_official_czce_gfex_warehouse_numeric",
            "asset_family": "warehouse",
            "layer": "official_raw_parsed_product_numeric",
            "row_count": len(warehouse_feature),
            "file_count": 1,
            "product_count": int(warehouse_feature["product_root"].nunique()) if not warehouse_feature.empty else 0,
            "date_count": int(warehouse_feature["target_date"].nunique()) if not warehouse_feature.empty else 0,
            "linked_lot_or_entry_count": int(warehouse_feature["lot_id"].nunique()) if not warehouse_feature.empty else 0,
            "start_date": str(warehouse_feature["target_date"].min()) if not warehouse_feature.empty else "",
            "end_date": str(warehouse_feature["target_date"].max()) if not warehouse_feature.empty else "",
            "has_inventory": 1,
            "has_spot_price": 0,
            "has_basis": 0,
            "has_curve_slope": 0,
            "has_raw_hash": int("sha256" in warehouse_feature.columns),
            "has_source_timestamp": 0,
            "has_source_license": 0,
            "prior_direct_rule_closed": 0,
            "strategy_rule_allowed": 0,
            "notes": "CZCE/GFEX official raw warehouse files have hashes, but only limited exchange/product coverage and no spot/basis link.",
        },
        {
            "asset_id": "stage026_term_structure_carry_features",
            "asset_family": "term_structure",
            "layer": "historical_carry_curve_features",
            "row_count": len(stage026),
            "file_count": 1,
            "product_count": int(stage026["product_key"].nunique()) if "product_key" in stage026.columns else 0,
            "date_count": int(pd.to_datetime(stage026.get("entry_date"), errors="coerce").nunique()),
            "linked_lot_or_entry_count": len(stage026),
            "start_date": str(pd.to_datetime(stage026.get("entry_date"), errors="coerce").min().date()),
            "end_date": str(pd.to_datetime(stage026.get("entry_date"), errors="coerce").max().date()),
            "has_inventory": 0,
            "has_spot_price": 0,
            "has_basis": 0,
            "has_curve_slope": 1,
            "has_raw_hash": 0,
            "has_source_timestamp": 0,
            "has_source_license": 0,
            "prior_direct_rule_closed": 1,
            "strategy_rule_allowed": 0,
            "notes": "Term-structure direct rule was closed in Stage026; keep as context only.",
        },
        {
            "asset_id": "stage027_stage060_closed_supply_basis_features",
            "asset_family": "prior_forensics",
            "layer": "closed_direct_rule_evidence",
            "row_count": len(stage027) + len(stage060),
            "file_count": 2,
            "product_count": np.nan,
            "date_count": np.nan,
            "linked_lot_or_entry_count": np.nan,
            "start_date": "",
            "end_date": "",
            "has_inventory": 1,
            "has_spot_price": 1,
            "has_basis": 1,
            "has_curve_slope": 0,
            "has_raw_hash": 0,
            "has_source_timestamp": 0,
            "has_source_license": 0,
            "prior_direct_rule_closed": 1,
            "strategy_rule_allowed": 0,
            "notes": "Stage027 and Stage060 already blocked direct supply/basis rules due right-tail conflict.",
        },
        {
            "asset_id": "stage099_inventory_basis_term_structure_manifest",
            "asset_family": "route_contract",
            "layer": "required_fields_only",
            "row_count": 1 if route else 0,
            "file_count": 1,
            "product_count": np.nan,
            "date_count": np.nan,
            "linked_lot_or_entry_count": np.nan,
            "start_date": "",
            "end_date": "",
            "has_inventory": 0,
            "has_spot_price": 0,
            "has_basis": 0,
            "has_curve_slope": 0,
            "has_raw_hash": 0,
            "has_source_timestamp": 0,
            "has_source_license": 0,
            "prior_direct_rule_closed": 0,
            "strategy_rule_allowed": _to_int(route.get("direct_rule_allowed"), 0),
            "notes": "Manifest asks for inventory + licensed spot/basis + term structure link; it is not data.",
        },
    ]
    return pd.DataFrame(rows)


def _build_field_contract(inputs: dict[str, Any]) -> pd.DataFrame:
    field = inputs["stage095_field"]
    warehouse_fields = set(field[field["source_family"].astype(str).eq("warehouse")]["field"].astype(str))
    basis_cols = set(inputs["basis_cache"].columns)
    warehouse_cols = set(inputs["warehouse_cache"].columns)
    stage026_cols = set(inputs["stage026_feature"].columns)

    readiness = {
        "trade_date": (1, 1, 1, 1, "date keys exist across caches"),
        "product": (1, 1, 1, 1, "product keys exist, though mapping still needs a contract"),
        "exchange_inventory": (1, 1, 0, 0, "warehouse source exists but all-exchange official provenance is incomplete"),
        "warehouse_receipt": (int("warehouse_receipt_quantity" in warehouse_cols), int("warehouse_receipt_qty_sum" in warehouse_fields), 0, 1, "warehouse receipt quantity exists"),
        "warehouse_change": (int("warehouse_receipt_change" in warehouse_cols), int("warehouse_change_qty_sum" in warehouse_fields), 0, 1, "warehouse daily change exists"),
        "spot_price": (int("spot_price" in basis_cols), 0, 0, 1, "spot price exists only in legacy basis cache"),
        "near_future_price": (int("near_contract_price" in basis_cols), 0, 0, 1, "near future price exists only in legacy basis cache"),
        "deferred_future_price": (int("dominant_contract_price" in basis_cols), 0, 0, 0, "dominant price exists, but full deferred curve source is absent"),
        "basis": (int({"near_basis", "dom_basis"}.issubset(basis_cols)), 0, 0, 1, "near/dominant basis exists only in legacy cache"),
        "curve_slope": (0, 0, int("curve_slope" in stage026_cols), 0, "Stage026 curve slope exists but direct route is closed and raw provenance is absent"),
        "source_timestamp": (0, 0, 0, 0, "exact publication/vendor timestamp is absent"),
        "publication_lag_calendar": (0, 0, 0, 0, "publication lag is not explicitly encoded"),
        "raw_path": (0, 1, 0, 1, "Stage095 official warehouse raw_file exists for limited sources"),
        "raw_hash": (0, 1, 0, 1, "Stage095 official warehouse sha256 exists for limited sources"),
        "source_license": (0, 0, 0, 0, "explicit license/authorization metadata is absent"),
        "unit": (0, int("unit" in inputs["stage095_feature"].columns), 0, 0, "unit exists in Stage095 limited official warehouse rows, not in basis cache"),
        "product_mapping": (1, 1, 1, 1, "product mapping exists but needs formal source contract"),
    }
    rows = []
    blocking = {
        "exchange_inventory",
        "deferred_future_price",
        "curve_slope",
        "source_timestamp",
        "publication_lag_calendar",
        "source_license",
        "unit",
    }
    for field_name in REQUIRED_FIELDS:
        legacy_basis, official_warehouse, term_structure, cache_level = readiness[field_name][:4]
        notes = readiness[field_name][4]
        rows.append(
            {
                "field": field_name,
                "required_for_inventory_basis_term_structure_rule": 1,
                "legacy_basis_cache_ready": legacy_basis,
                "stage095_official_warehouse_ready": official_warehouse,
                "stage026_term_structure_ready": term_structure,
                "cache_level_available": cache_level,
                "rule_ready": 0 if field_name in blocking else int(bool(cache_level or official_warehouse or term_structure)),
                "blocking_if_missing": int(field_name in blocking),
                "notes": notes,
            }
        )
    return pd.DataFrame(rows)


def _build_entry_coverage(inputs: dict[str, Any]) -> pd.DataFrame:
    joined = inputs["stage239_joined"].copy()
    basis_cache = inputs["basis_cache"]
    warehouse_cache = inputs["warehouse_cache"]
    stage095_feature = inputs["stage095_feature"]

    joined["entry_date"] = pd.to_datetime(joined.get("official_open_date"), errors="coerce")
    joined["entry_year"] = joined["entry_date"].dt.year
    joined["product_root_clean"] = [_product_root(vt, prod) for vt, prod in zip(joined["vt_symbol"], joined["product"])]
    joined["entry_key"] = [_entry_key(vt, date) for vt, date in zip(joined["vt_symbol"], joined["entry_date"])]

    warehouse_feature = stage095_feature[stage095_feature["source_family"].astype(str).eq("warehouse")].copy()
    if not warehouse_feature.empty:
        warehouse_feature["entry_key"] = [
            _entry_key(vt, date) for vt, date in zip(warehouse_feature["vt_symbol"], warehouse_feature["entry_date"])
        ]
        official_warehouse = (
            warehouse_feature.groupby("entry_key", as_index=False)
            .agg(
                official_warehouse_numeric_ready=("numeric_feature_ready", "max"),
                official_warehouse_row_count=("feature_row_id", "count"),
                official_warehouse_target_date_count=("target_date", "nunique"),
                official_warehouse_raw_hash_ready=("sha256", lambda values: int(values.notna().any())),
            )
        )
    else:
        official_warehouse = pd.DataFrame(columns=["entry_key", "official_warehouse_numeric_ready"])

    rows: list[dict[str, Any]] = []
    for _, row in joined.iterrows():
        product = str(row["product_root_clean"])
        entry_date = row["entry_date"]
        basis = _find_prior(basis_cache, product, entry_date)
        warehouse = _find_prior(warehouse_cache, product, entry_date)
        rows.append(
            {
                "request_id": row.get("request_id"),
                "entry_key": row.get("entry_key"),
                "exchange": row.get("exchange"),
                "product": row.get("product"),
                "product_root_clean": product,
                "vt_symbol": row.get("vt_symbol"),
                "direction": row.get("direction"),
                "decision_ts": row.get("decision_ts"),
                "official_open_date": row.get("official_open_date"),
                "entry_year": row.get("entry_year"),
                "risk_bad_label": _to_int(row.get("risk_bad_label"), 0),
                "right_tail_label": _to_int(row.get("right_tail_label"), 0),
                "bottom_loss_visual": _to_int(row.get("bottom_loss_visual"), 0),
                "maxdd_context": _to_int(row.get("maxdd_context"), 0),
                "basis_cache_ready": int(bool(basis)),
                "basis_source_date": basis.get("date_dt", pd.NaT).strftime("%Y-%m-%d") if basis else "",
                "basis_signal_age_days": int((entry_date - basis.get("date_dt")).days) if basis and not pd.isna(entry_date) else np.nan,
                "spot_price_ready": int(bool(basis) and pd.notna(basis.get("spot_price"))),
                "near_future_price_ready": int(bool(basis) and pd.notna(basis.get("near_contract_price"))),
                "dominant_future_price_ready": int(bool(basis) and pd.notna(basis.get("dominant_contract_price"))),
                "basis_rate_ready": int(bool(basis) and pd.notna(basis.get("dom_basis_rate"))),
                "warehouse_cache_ready": int(bool(warehouse)),
                "warehouse_source_date": warehouse.get("date_dt", pd.NaT).strftime("%Y-%m-%d") if warehouse else "",
                "warehouse_signal_age_days": int((entry_date - warehouse.get("date_dt")).days) if warehouse and not pd.isna(entry_date) else np.nan,
                "warehouse_receipt_ready": int(bool(warehouse) and pd.notna(warehouse.get("warehouse_receipt_quantity"))),
                "warehouse_change_ready": int(bool(warehouse) and pd.notna(warehouse.get("warehouse_receipt_change"))),
            }
        )
    frame = pd.DataFrame(rows)
    frame = frame.merge(official_warehouse, on="entry_key", how="left") if "entry_key" in official_warehouse.columns else frame
    if "official_warehouse_numeric_ready" not in frame.columns:
        frame["official_warehouse_numeric_ready"] = 0
    for column in [
        "official_warehouse_numeric_ready",
        "official_warehouse_row_count",
        "official_warehouse_target_date_count",
        "official_warehouse_raw_hash_ready",
    ]:
        if column not in frame.columns:
            frame[column] = 0
        frame[column] = frame[column].fillna(0).astype(int)
    frame["cache_joint_basis_warehouse_ready"] = (
        frame["basis_cache_ready"].eq(1) & frame["warehouse_cache_ready"].eq(1)
    ).astype(int)
    frame["cache_joint_plus_official_warehouse_ready"] = (
        frame["cache_joint_basis_warehouse_ready"].eq(1) & frame["official_warehouse_numeric_ready"].eq(1)
    ).astype(int)
    frame["source_timestamp_ready"] = 0
    frame["source_license_ready"] = 0
    frame["publication_lag_ready"] = 0
    frame["curve_slope_contract_ready"] = 0
    frame["inventory_basis_term_rule_ready"] = 0
    frame["missing_reason"] = np.select(
        [
            frame["cache_joint_basis_warehouse_ready"].eq(0),
            frame["cache_joint_plus_official_warehouse_ready"].eq(0),
        ],
        [
            "basis_or_warehouse_cache_missing",
            "legacy_cache_joint_ready_but_official_warehouse_or_hash_link_missing",
        ],
        default="cache_components_present_but_timestamp_license_curve_contract_missing",
    )
    return frame


def _build_entry_heatmap(entry_coverage: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        entry_coverage.groupby(["exchange", "entry_year"], dropna=False)
        .agg(
            entry_count=("request_id", "count"),
            basis_cache_ready_count=("basis_cache_ready", "sum"),
            warehouse_cache_ready_count=("warehouse_cache_ready", "sum"),
            cache_joint_ready_count=("cache_joint_basis_warehouse_ready", "sum"),
            official_warehouse_ready_count=("official_warehouse_numeric_ready", "sum"),
            full_contract_rule_ready_count=("inventory_basis_term_rule_ready", "sum"),
            risk_bad_count=("risk_bad_label", "sum"),
            right_tail_count=("right_tail_label", "sum"),
        )
        .reset_index()
    )
    for column in [
        "basis_cache_ready_count",
        "warehouse_cache_ready_count",
        "cache_joint_ready_count",
        "official_warehouse_ready_count",
        "full_contract_rule_ready_count",
    ]:
        grouped[column.replace("_count", "_pct")] = grouped.apply(
            lambda row, col=column: _safe_div(row[col], row["entry_count"]), axis=1
        )
    return grouped


def _build_summary(
    inputs: dict[str, Any],
    assets: pd.DataFrame,
    field_contract: pd.DataFrame,
    entry_coverage: pd.DataFrame,
    gate: pd.DataFrame,
) -> dict[str, Any]:
    stage251_summary = inputs["stage251_summary"]
    official = stage251_summary[stage251_summary.get("arm", pd.Series(dtype=str)).astype(str).eq("A_official_stage847_c9_15w")]
    official_row = official.iloc[0].to_dict() if not official.empty else stage251_summary.iloc[0].to_dict()
    basis_score = _row(inputs["stage087_scorecard"], source_id="basis")
    warehouse_score = _row(inputs["stage087_scorecard"], source_id="warehouse")

    entry_count = len(entry_coverage)
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage258_inventory_basis_term_structure_contract_incomplete_no_rule",
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_end_equity": _to_float(official_row.get("end_equity")),
        "official_total_return_pct": _to_float(official_row.get("total_return_pct")),
        "official_max_dd_pct": _to_float(official_row.get("max_dd_pct")),
        "official_sharpe": _to_float(official_row.get("sharpe")),
        "official_total_slippage": _to_float(official_row.get("total_slippage")),
        "official_total_trade_count": _to_float(official_row.get("total_trade_count")),
        "official_win_rate_pct": _to_float(official_row.get("nonzero_daily_win_rate_pct")),
        "entry_count": entry_count,
        "basis_cache_row_count": len(inputs["basis_cache"]),
        "basis_cache_product_count": int(inputs["basis_cache"]["product_root"].nunique()),
        "warehouse_cache_row_count": len(inputs["warehouse_cache"]),
        "warehouse_cache_product_count": int(inputs["warehouse_cache"]["product_root"].nunique()),
        "stage087_basis_ready_lot_pct": _to_float(basis_score.get("ready_lot_pct")),
        "stage087_basis_missing_big_winner_count": _to_float(basis_score.get("missing_big_winner_count")),
        "stage087_warehouse_ready_lot_pct": _to_float(warehouse_score.get("ready_lot_pct")),
        "stage087_warehouse_missing_big_winner_count": _to_float(warehouse_score.get("missing_big_winner_count")),
        "basis_cache_ready_entry_count": int(entry_coverage["basis_cache_ready"].sum()),
        "basis_cache_ready_entry_pct": _safe_div(entry_coverage["basis_cache_ready"].sum(), entry_count),
        "warehouse_cache_ready_entry_count": int(entry_coverage["warehouse_cache_ready"].sum()),
        "warehouse_cache_ready_entry_pct": _safe_div(entry_coverage["warehouse_cache_ready"].sum(), entry_count),
        "cache_joint_ready_entry_count": int(entry_coverage["cache_joint_basis_warehouse_ready"].sum()),
        "cache_joint_ready_entry_pct": _safe_div(entry_coverage["cache_joint_basis_warehouse_ready"].sum(), entry_count),
        "official_warehouse_ready_entry_count": int(entry_coverage["official_warehouse_numeric_ready"].sum()),
        "official_warehouse_ready_entry_pct": _safe_div(entry_coverage["official_warehouse_numeric_ready"].sum(), entry_count),
        "cache_joint_plus_official_warehouse_ready_count": int(entry_coverage["cache_joint_plus_official_warehouse_ready"].sum()),
        "cache_joint_plus_official_warehouse_ready_pct": _safe_div(entry_coverage["cache_joint_plus_official_warehouse_ready"].sum(), entry_count),
        "full_contract_rule_ready_entry_count": int(entry_coverage["inventory_basis_term_rule_ready"].sum()),
        "full_contract_rule_ready_entry_pct": _safe_div(entry_coverage["inventory_basis_term_rule_ready"].sum(), entry_count),
        "source_timestamp_ready_entry_count": int(entry_coverage["source_timestamp_ready"].sum()),
        "source_license_ready_entry_count": int(entry_coverage["source_license_ready"].sum()),
        "publication_lag_ready_entry_count": int(entry_coverage["publication_lag_ready"].sum()),
        "curve_slope_contract_ready_entry_count": int(entry_coverage["curve_slope_contract_ready"].sum()),
        "required_field_count": len(field_contract),
        "rule_ready_field_count": int(field_contract["rule_ready"].sum()),
        "blocking_missing_field_count": int(field_contract.query("blocking_if_missing == 1 and rule_ready == 0").shape[0]),
        "asset_count": len(assets),
        "gate_pass_count": int(gate["passed"].sum()),
        "gate_total_count": len(gate),
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
    }
    return summary


def _build_gate(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("official_warehouse_sources_exist", 1, "SHFE/CZCE/DCE/GFEX publish warehouse or delivery reports."),
        ("local_basis_cache_present", int(summary["basis_cache_row_count"] > 0), "Local basis cache exists."),
        ("local_warehouse_cache_present", int(summary["warehouse_cache_row_count"] > 0), "Local warehouse cache exists."),
        ("stage095_official_warehouse_parse_ready", int(summary["official_warehouse_ready_entry_count"] > 0), "Stage095 official CZCE/GFEX warehouse parse exists."),
        ("entry_cache_joint_nonzero", int(summary["cache_joint_ready_entry_count"] > 0), "Some entries have both basis and warehouse cache."),
        ("full_entry_contract_coverage", int(summary["full_contract_rule_ready_entry_count"] == summary["entry_count"]), "Every entry needs the full physical-market contract."),
        ("spot_basis_authorized_provenance", 0, "Spot/basis cache lacks explicit official or licensed provenance."),
        ("source_timestamp_publication_lag_ready", 0, "Exact publication or vendor timestamps and lag calendar are absent."),
        ("all_exchange_official_warehouse_raw_ready", 0, "DCE/SHFE official raw warehouse history remains incomplete or partial."),
        ("right_tail_missing_safe", 0, "Stage087 basis/warehouse missing groups still contain big winners."),
        ("prior_direct_rules_not_closed", 0, "Stage026/027/060 already closed direct carry/supply/basis rules."),
        ("true_engine_allowed", 0, "This is a source-contract audit only."),
    ]
    frame = pd.DataFrame(rows, columns=["gate", "passed", "reason"])
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    return frame


def _plot_official_path(inputs: dict[str, Any], entry_coverage: pd.DataFrame) -> None:
    curve = inputs["stage251_curve"].copy()
    if "arm" in curve.columns:
        curve = curve[curve["arm"].astype(str).eq("A_official_stage847_c9_15w")].copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    curve = curve[curve["date"].notna()].sort_values("date")
    events = entry_coverage.copy()
    events["date"] = pd.to_datetime(events["official_open_date"], errors="coerce")
    events = events[events["date"].notna()].sort_values("date")
    event_curve = pd.merge_asof(events, curve[["date", "account_equity", "drawdown_pct"]], on="date", direction="backward")

    fig, ax1 = plt.subplots(figsize=(13, 6))
    ax1.plot(curve["date"], curve["account_equity"] / 1_000_000.0, color="#0f766e", linewidth=2.0, label="Official equity")
    full_missing = event_curve[event_curve["inventory_basis_term_rule_ready"].eq(0)]
    ax1.scatter(
        full_missing["date"],
        full_missing["account_equity"] / 1_000_000.0,
        s=24,
        color="#b91c1c",
        marker="x",
        alpha=0.75,
        label="Full physical contract missing",
    )
    cache_joint = event_curve[event_curve["cache_joint_basis_warehouse_ready"].eq(1)]
    ax1.scatter(
        cache_joint["date"],
        cache_joint["account_equity"] / 1_000_000.0,
        s=24,
        facecolor="none",
        edgecolor="#2563eb",
        alpha=0.82,
        label="Basis + warehouse cache only",
    )
    official_wh = event_curve[event_curve["official_warehouse_numeric_ready"].eq(1)]
    ax1.scatter(
        official_wh["date"],
        official_wh["account_equity"] / 1_000_000.0,
        s=20,
        facecolor="none",
        edgecolor="#f97316",
        marker="s",
        alpha=0.78,
        label="Official warehouse numeric only",
    )
    ax1.set_title("Official path with inventory/basis/term contract coverage")
    ax1.set_ylabel("Equity (million CNY)")
    ax1.grid(True, alpha=0.25)

    ax2 = ax1.twinx()
    ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#f59e0b", alpha=0.16, label="Drawdown")
    ax2.set_ylabel("Drawdown %")
    ax2.set_ylim(min(-55, float(curve["drawdown_pct"].min()) - 3), 5)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_field_heatmap(field_contract: pd.DataFrame) -> None:
    columns = [
        "legacy_basis_cache_ready",
        "stage095_official_warehouse_ready",
        "stage026_term_structure_ready",
        "cache_level_available",
        "rule_ready",
    ]
    matrix = field_contract.set_index("field")[columns].astype(float)
    fig, ax = plt.subplots(figsize=(11, 7))
    image = ax.imshow(matrix.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(["Basis cache", "Official warehouse", "Term structure", "Cache-level", "Rule ready"], rotation=30, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            ax.text(x, y, "1" if matrix.iloc[y, x] >= 0.5 else "0", ha="center", va="center", fontsize=8)
    ax.set_title("Field contract readiness for inventory + basis + term structure")
    fig.colorbar(image, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(FIELD_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_asset_inventory(assets: pd.DataFrame) -> None:
    frame = assets.copy()
    frame["quantity"] = frame["row_count"].fillna(frame["file_count"]).fillna(0).astype(float)
    colors = np.where(frame["strategy_rule_allowed"].astype(int).eq(1), "#16a34a", "#dc2626")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.barh(frame["asset_id"], np.maximum(frame["quantity"], 1), color=colors, alpha=0.82)
    ax.set_xscale("log")
    ax.set_xlabel("Rows or files (log scale, min=1)")
    ax.set_title("Local physical-market assets: data exists, source contract incomplete")
    for y, (_, row) in enumerate(frame.iterrows()):
        label = f"hash={int(row['has_raw_hash'])}, ts={int(row['has_source_timestamp'])}, lic={int(row['has_source_license'])}"
        ax.text(max(float(row["quantity"]), 1) * 1.08, y, label, va="center", fontsize=8)
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ASSET_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_entry_heatmap(entry_heatmap: pd.DataFrame) -> None:
    pivot = entry_heatmap.pivot(index="exchange", columns="entry_year", values="full_contract_rule_ready_pct").fillna(0.0)
    count_pivot = entry_heatmap.pivot(index="exchange", columns="entry_year", values="entry_count").fillna(0).astype(int)
    joint_pivot = entry_heatmap.pivot(index="exchange", columns="entry_year", values="cache_joint_ready_count").fillna(0).astype(int)
    official_pivot = entry_heatmap.pivot(index="exchange", columns="entry_year", values="official_warehouse_ready_count").fillna(0).astype(int)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    image = ax.imshow(pivot.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) if not pd.isna(col) else "NA" for col in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y, exchange in enumerate(pivot.index):
        for x, year in enumerate(pivot.columns):
            total = int(count_pivot.loc[exchange, year])
            joint = int(joint_pivot.loc[exchange, year])
            official = int(official_pivot.loc[exchange, year])
            ax.text(x, y, f"rule 0/{total}\ncache {joint}/{total}\noffwh {official}/{total}", ha="center", va="center", fontsize=8)
    ax.set_title("Entry coverage by exchange/year: full physical contract remains 0")
    ax.set_xlabel("Entry year")
    ax.set_ylabel("Exchange")
    fig.colorbar(image, ax=ax, shrink=0.85, label="Full-contract ready pct")
    fig.tight_layout()
    fig.savefig(ENTRY_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    frame = gate.copy().iloc[::-1]
    colors = np.where(frame["passed"].eq(1), "#16a34a", "#dc2626")
    fig, ax = plt.subplots(figsize=(10.5, 6))
    ax.barh(frame["gate"], frame["passed"], color=colors, alpha=0.85)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Pass")
    ax.set_title("Promotion gate: physical-market source contract only")
    for y, (_, row) in enumerate(frame.iterrows()):
        ax.text(0.03, y, "PASS" if row["passed"] else "BLOCK", va="center", fontsize=8, color="#111827")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=180)
    plt.close(fig)


def _write_report(summary: dict[str, Any]) -> None:
    report = f"""# Stage258 inventory + basis + term-structure source audit

Decision: `{summary['decision']}`

This stage is a read-only source-contract audit. It does not create a trading rule, does not run a true engine, does not trigger A/B, does not change the official configuration, and does not call any order API.

## Main result

- Stage239 entry rows: `{summary['entry_count']}`
- Basis cache ready entries: `{summary['basis_cache_ready_entry_count']}/{summary['entry_count']}` (`{summary['basis_cache_ready_entry_pct']:.4%}`)
- Warehouse cache ready entries: `{summary['warehouse_cache_ready_entry_count']}/{summary['entry_count']}` (`{summary['warehouse_cache_ready_entry_pct']:.4%}`)
- Basis + warehouse cache joint entries: `{summary['cache_joint_ready_entry_count']}/{summary['entry_count']}` (`{summary['cache_joint_ready_entry_pct']:.4%}`)
- Stage095 official warehouse numeric entries: `{summary['official_warehouse_ready_entry_count']}/{summary['entry_count']}` (`{summary['official_warehouse_ready_entry_pct']:.4%}`)
- Cache joint + official warehouse entries: `{summary['cache_joint_plus_official_warehouse_ready_count']}/{summary['entry_count']}` (`{summary['cache_joint_plus_official_warehouse_ready_pct']:.4%}`)
- Full physical contract rule-ready entries: `{summary['full_contract_rule_ready_entry_count']}/{summary['entry_count']}` (`{summary['full_contract_rule_ready_entry_pct']:.4%}`)
- Blocking missing field count: `{summary['blocking_missing_field_count']}`
- Gate: `{summary['gate_pass_count']}/{summary['gate_total_count']}`

## Interpretation

The current repo has useful physical-market context, but not a rule-ready source contract. Basis cache has spot and near/dominant futures prices but lacks publication timestamps, raw hashes, and explicit license metadata. Official warehouse raw parsing exists for limited CZCE/GFEX sources, but does not link to authorized spot/basis or a full term-structure curve. Stage026, Stage027, and Stage060 already showed direct carry/supply/basis rules are closed due right-tail conflict.

The practical answer is: cache-level context can be counted, but the full inventory + basis + term-structure route is still missing `{summary['entry_count']}` out of `{summary['entry_count']}` entry decisions at rule-ready level. This is a source-contract and provenance gap, not a simple threshold issue.

## Files

- `{ASSET_INVENTORY_OUT}`
- `{FIELD_CONTRACT_OUT}`
- `{ENTRY_COVERAGE_OUT}`
- `{ENTRY_HEATMAP_OUT}`
- `{GATE_OUT}`
- `{PATH_CHART_OUT}`
- `{FIELD_CHART_OUT}`
- `{ASSET_CHART_OUT}`
- `{ENTRY_CHART_OUT}`
- `{GATE_CHART_OUT}`
"""
    _write_text(REPORT_OUT, report)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = _load_inputs()
    assets = _build_asset_inventory(inputs)
    field_contract = _build_field_contract(inputs)
    entry_coverage = _build_entry_coverage(inputs)
    entry_heatmap = _build_entry_heatmap(entry_coverage)
    placeholder = {
        "basis_cache_row_count": len(inputs["basis_cache"]),
        "warehouse_cache_row_count": len(inputs["warehouse_cache"]),
        "official_warehouse_ready_entry_count": int(entry_coverage["official_warehouse_numeric_ready"].sum()),
        "cache_joint_ready_entry_count": int(entry_coverage["cache_joint_basis_warehouse_ready"].sum()),
        "full_contract_rule_ready_entry_count": int(entry_coverage["inventory_basis_term_rule_ready"].sum()),
        "entry_count": len(entry_coverage),
    }
    gate = _build_gate(placeholder)
    summary = _build_summary(inputs, assets, field_contract, entry_coverage, gate)
    gate = _build_gate(summary)
    summary["gate_pass_count"] = int(gate["passed"].sum())
    summary["gate_total_count"] = len(gate)

    _write_csv(assets, ASSET_INVENTORY_OUT)
    _write_csv(field_contract, FIELD_CONTRACT_OUT)
    _write_csv(entry_coverage, ENTRY_COVERAGE_OUT)
    _write_csv(entry_heatmap, ENTRY_HEATMAP_OUT)
    _write_csv(gate, GATE_OUT)
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_json(DECISION_OUT, summary)
    _write_report(summary)

    _plot_official_path(inputs, entry_coverage)
    _plot_field_heatmap(field_contract)
    _plot_asset_inventory(assets)
    _plot_entry_heatmap(entry_heatmap)
    _plot_gate(gate)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

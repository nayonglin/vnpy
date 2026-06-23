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
STAGE = "Stage257"
MODEL_TAG = "stage257_member_category_seat_structure_source_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage257_c9_minrisk_member_category_seat_structure_source_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage257_member_category_seat_structure_source_audit"

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

MEMBER_CACHE = (
    REPO_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "external_domestic_member_rank_cache"
    / "member_rank_sum_daily_20230101_20260417.csv"
)

STAGE091_RAW_CZCE_MEMBER_DIR = (
    LINE_DIR
    / "outputs"
    / "stage091_preentry_window_raw_full_backfill"
    / "raw"
    / "czce_member_rank"
)

STAGE095_FIELD_IN = STAGE095_DIR / f"{STAGE095_PREFIX}_field_summary_{STAGE095_TAG}.csv"
STAGE095_FEATURE_IN = STAGE095_DIR / f"{STAGE095_PREFIX}_feature_rows_{STAGE095_TAG}.csv"
STAGE095_LOT_IN = STAGE095_DIR / f"{STAGE095_PREFIX}_lot_summary_{STAGE095_TAG}.csv"
STAGE095_AGG_IN = STAGE095_DIR / f"{STAGE095_PREFIX}_aggregation_source_summary_{STAGE095_TAG}.csv"

STAGE087_SCORECARD_IN = STAGE087_DIR / f"{STAGE087_PREFIX}_source_scorecard_{STAGE087_TAG}.csv"
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

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_member_role_coverage_{MODEL_TAG}.png"
FIELD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_readiness_heatmap_{MODEL_TAG}.png"
ASSET_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_asset_inventory_chart_{MODEL_TAG}.png"
ENTRY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_exchange_year_coverage_heatmap_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"

REQUIRED_ROLE_FIELDS = [
    "trade_date",
    "exchange",
    "product",
    "contract_month_source",
    "member_or_seat_id",
    "member_short_name",
    "member_category",
    "seat_id",
    "rank_type",
    "volume",
    "volume_change",
    "long_oi",
    "long_oi_change",
    "short_oi",
    "short_oi_change",
    "publish_timestamp",
    "raw_path",
    "raw_hash",
    "source_license",
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


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


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


def _product_root(vt_symbol: Any, product: Any = "") -> str:
    product_text = str(product) if not pd.isna(product) else ""
    if product_text and product_text.lower() != "nan":
        return product_text.split(".")[0]
    match = re.match(r"^([A-Za-z]+)", str(vt_symbol))
    return match.group(1) if match else str(vt_symbol).split(".")[0]


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


def _load_inputs() -> dict[str, pd.DataFrame]:
    return {
        "stage087_scorecard": _read_csv(STAGE087_SCORECARD_IN),
        "stage095_field": _read_csv(STAGE095_FIELD_IN),
        "stage095_feature": _read_csv(STAGE095_FEATURE_IN),
        "stage095_lot": _read_csv(STAGE095_LOT_IN),
        "stage095_agg": _read_csv(STAGE095_AGG_IN),
        "stage099_manifest": _read_csv(STAGE099_MANIFEST_IN),
        "stage239_joined": _read_csv(STAGE239_JOINED_IN),
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
    }


def _member_cache_stats() -> dict[str, Any]:
    if not MEMBER_CACHE.exists():
        return {
            "present": 0,
            "row_count": 0,
            "product_count": 0,
            "symbol_count": 0,
            "date_count": 0,
            "start_date": "",
            "end_date": "",
            "column_count": 0,
        }
    cache = pd.read_csv(MEMBER_CACHE, encoding="utf-8-sig")
    date_series = pd.to_datetime(cache.get("date"), errors="coerce")
    return {
        "present": 1,
        "row_count": len(cache),
        "product_count": cache["variety"].nunique() if "variety" in cache.columns else 0,
        "symbol_count": cache["symbol"].nunique() if "symbol" in cache.columns else 0,
        "date_count": date_series.nunique(),
        "start_date": date_series.min().strftime("%Y-%m-%d") if date_series.notna().any() else "",
        "end_date": date_series.max().strftime("%Y-%m-%d") if date_series.notna().any() else "",
        "column_count": len(cache.columns),
        "has_member_detail": 0,
        "has_member_category": 0,
        "has_seat_id": 0,
        "has_raw_hash": 0,
    }


def _raw_file_stats() -> dict[str, Any]:
    files = sorted(STAGE091_RAW_CZCE_MEMBER_DIR.glob("czce_member_rank_*")) if STAGE091_RAW_CZCE_MEMBER_DIR.exists() else []
    by_suffix: dict[str, int] = {}
    for path in files:
        suffix = path.suffix.lower().lstrip(".") or "no_suffix"
        by_suffix[suffix] = by_suffix.get(suffix, 0) + 1
    dates: list[pd.Timestamp] = []
    for path in files:
        match = re.search(r"(\d{8})", path.name)
        if match:
            parsed = pd.to_datetime(match.group(1), format="%Y%m%d", errors="coerce")
            if not pd.isna(parsed):
                dates.append(parsed)
    return {
        "present": int(bool(files)),
        "file_count": len(files),
        "total_bytes": int(sum(path.stat().st_size for path in files)),
        "suffix_breakdown": ";".join(f"{key}:{value}" for key, value in sorted(by_suffix.items())),
        "date_count": len(set(dates)),
        "start_date": min(dates).strftime("%Y-%m-%d") if dates else "",
        "end_date": max(dates).strftime("%Y-%m-%d") if dates else "",
    }


def _build_asset_inventory(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    field = inputs["stage095_field"]
    feature = inputs["stage095_feature"]
    agg = inputs["stage095_agg"]
    scorecard = inputs["stage087_scorecard"]
    manifest = inputs["stage099_manifest"]

    cache_stats = _member_cache_stats()
    raw_stats = _raw_file_stats()

    member_feature = feature[feature["source_family"].astype(str).eq("member_rank")].copy()
    member_agg = agg[agg["source_family"].astype(str).eq("member_rank")].copy()
    member_score = _row(scorecard, source_id="member_rank")
    route = _row(manifest, route_id="member_category_seat_structure")
    member_fields = field[field["source_family"].astype(str).eq("member_rank")].copy()

    rows = [
        {
            "asset_id": "legacy_member_rank_sum_daily_cache",
            "asset_family": "member_rank",
            "layer": "legacy_topn_product_total_cache",
            "present": cache_stats["present"],
            "file_count": cache_stats["present"],
            "row_count": cache_stats["row_count"],
            "product_count": cache_stats["product_count"],
            "symbol_count": cache_stats["symbol_count"],
            "date_count": cache_stats["date_count"],
            "linked_lot_or_entry_count": _to_float(member_score.get("ready_lot_count"), 0.0),
            "start_date": cache_stats["start_date"],
            "end_date": cache_stats["end_date"],
            "has_product_total_numeric": 1,
            "has_member_detail": 0,
            "has_member_or_seat_id": 0,
            "has_member_category": 0,
            "has_seat_id": 0,
            "has_contract_month_source": 1,
            "has_raw_hash": 0,
            "strategy_rule_allowed": 0,
            "notes": "topN aggregates only; no member identity/category/seat mapping retained",
        },
        {
            "asset_id": "stage091_czce_member_rank_raw_files",
            "asset_family": "member_rank",
            "layer": "official_public_raw_files",
            "present": raw_stats["present"],
            "file_count": raw_stats["file_count"],
            "row_count": np.nan,
            "product_count": np.nan,
            "symbol_count": np.nan,
            "date_count": raw_stats["date_count"],
            "linked_lot_or_entry_count": np.nan,
            "start_date": raw_stats["start_date"],
            "end_date": raw_stats["end_date"],
            "has_product_total_numeric": 1,
            "has_member_detail": 1,
            "has_member_or_seat_id": 0,
            "has_member_category": 0,
            "has_seat_id": 0,
            "has_contract_month_source": 0,
            "has_raw_hash": 1,
            "strategy_rule_allowed": 0,
            "notes": f"raw report files exist ({raw_stats['suffix_breakdown']}); raw header has member names but no role/category/seat classification",
        },
        {
            "asset_id": "stage095_czce_member_rank_numeric_features",
            "asset_family": "member_rank",
            "layer": "parsed_product_total_numeric_features",
            "present": int(not member_feature.empty),
            "file_count": 1,
            "row_count": len(member_feature),
            "product_count": member_feature["product_root"].nunique() if "product_root" in member_feature.columns else np.nan,
            "symbol_count": member_feature["vt_symbol"].nunique() if "vt_symbol" in member_feature.columns else np.nan,
            "date_count": member_feature["target_date"].nunique() if "target_date" in member_feature.columns else np.nan,
            "linked_lot_or_entry_count": member_feature["lot_id"].nunique() if "lot_id" in member_feature.columns else np.nan,
            "start_date": str(member_feature["target_date"].min()) if "target_date" in member_feature.columns and not member_feature.empty else "",
            "end_date": str(member_feature["target_date"].max()) if "target_date" in member_feature.columns and not member_feature.empty else "",
            "has_product_total_numeric": 1,
            "has_member_detail": 0,
            "has_member_or_seat_id": 0,
            "has_member_category": 0,
            "has_seat_id": 0,
            "has_contract_month_source": 0,
            "has_raw_hash": int("sha256" in member_feature.columns),
            "strategy_rule_allowed": 0,
            "notes": "Stage095 parser keeps official_product_total_row sums only",
        },
        {
            "asset_id": "stage095_member_rank_field_summary",
            "asset_family": "member_rank",
            "layer": "field_summary",
            "present": int(not member_fields.empty),
            "file_count": 1,
            "row_count": len(member_fields),
            "product_count": np.nan,
            "symbol_count": np.nan,
            "date_count": np.nan,
            "linked_lot_or_entry_count": np.nan,
            "start_date": "",
            "end_date": "",
            "has_product_total_numeric": 1,
            "has_member_detail": 0,
            "has_member_or_seat_id": 0,
            "has_member_category": 0,
            "has_seat_id": 0,
            "has_contract_month_source": 0,
            "has_raw_hash": 1,
            "strategy_rule_allowed": 0,
            "notes": "six numeric aggregate fields; all trading_rule_allowed=0",
        },
        {
            "asset_id": "stage099_member_category_seat_route_manifest",
            "asset_family": "member_rank",
            "layer": "route_contract",
            "present": int(bool(route)),
            "file_count": 1,
            "row_count": 1,
            "product_count": np.nan,
            "symbol_count": np.nan,
            "date_count": np.nan,
            "linked_lot_or_entry_count": np.nan,
            "start_date": "",
            "end_date": "",
            "has_product_total_numeric": 0,
            "has_member_detail": 0,
            "has_member_or_seat_id": 0,
            "has_member_category": 0,
            "has_seat_id": 0,
            "has_contract_month_source": 0,
            "has_raw_hash": 0,
            "strategy_rule_allowed": _to_int(route.get("direct_rule_allowed"), 0),
            "notes": "manifest defines required fields only; current repo status says category/seat coverage absent",
        },
    ]
    return pd.DataFrame(rows)


def _build_field_contract(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    feature = inputs["stage095_feature"]
    member_feature = feature[feature["source_family"].astype(str).eq("member_rank")].copy()
    header_signature = "|".join(member_feature.get("header_signature", pd.Series(dtype=str)).dropna().astype(str).unique()[:5])
    raw_member_name_seen = int("member" in header_signature.lower() or "会员" in header_signature)
    if not raw_member_name_seen:
        raw_member_name_seen = int(member_feature.get("header_signature", pd.Series(dtype=str)).astype(str).str.contains("会员", regex=False).any())

    ready_map = {
        "trade_date": (1, 1, 1, 1, "target_date/date keys are available"),
        "exchange": (1, 1, 1, 1, "exchange/source ids are available"),
        "product": (1, 1, 1, 1, "product_root is available"),
        "contract_month_source": (0, 0, 1, 0, "entry vt_symbol has month, but Stage095 member rank aggregation is official_product_total_row"),
        "member_or_seat_id": (0, 0, 0, 0, "no stable member id or seat id is parsed or cached"),
        "member_short_name": (0, raw_member_name_seen, 0, 0, "raw report header includes member short-name columns, but parsed features discard them"),
        "member_category": (0, 0, 0, 0, "no category/role mapping such as producer/commercial/financial is present"),
        "seat_id": (0, 0, 0, 0, "no trading seat id is present"),
        "rank_type": (1, 1, 1, 1, "volume/long/short ranking groups are present"),
        "volume": (1, 1, 1, 1, "aggregate numeric volume is present"),
        "volume_change": (1, 1, 1, 1, "aggregate numeric volume change is present"),
        "long_oi": (1, 1, 1, 1, "aggregate long open interest is present"),
        "long_oi_change": (1, 1, 1, 1, "aggregate long open-interest change is present"),
        "short_oi": (1, 1, 1, 1, "aggregate short open interest is present"),
        "short_oi_change": (1, 1, 1, 1, "aggregate short open-interest change is present"),
        "publish_timestamp": (0, 0, 0, 0, "only target trade date is retained; exact publication timestamp is absent"),
        "raw_path": (1, 1, 0, 1, "raw_file path is present in Stage095"),
        "raw_hash": (1, 1, 0, 1, "sha256 is present in Stage095"),
        "source_license": (0, 0, 0, 0, "explicit license/authorization metadata is absent"),
    }
    rows = []
    for field in REQUIRED_ROLE_FIELDS:
        parsed, raw, legacy, rule_ready, notes = ready_map[field]
        rows.append(
            {
                "field": field,
                "required_for_member_category_seat_rule": 1,
                "stage095_parsed_product_total_ready": parsed,
                "stage091_raw_report_inferred_ready": raw,
                "legacy_topn_cache_ready": legacy,
                "rule_ready": rule_ready,
                "blocking_if_missing": int(field in {"contract_month_source", "member_or_seat_id", "member_category", "seat_id", "publish_timestamp", "source_license"}),
                "notes": notes,
            }
        )
    return pd.DataFrame(rows)


def _build_entry_coverage(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    joined = inputs["stage239_joined"].copy()
    lots = inputs["stage095_lot"].copy()

    joined["entry_date"] = pd.to_datetime(joined.get("official_open_date"), errors="coerce").dt.strftime("%Y-%m-%d")
    joined["decision_date"] = pd.to_datetime(joined.get("decision_ts"), errors="coerce").dt.strftime("%Y-%m-%d")
    joined["entry_year"] = pd.to_datetime(joined["entry_date"], errors="coerce").dt.year
    joined["product_root_clean"] = [
        _product_root(vt, prod) for vt, prod in zip(joined.get("vt_symbol", []), joined.get("product", []))
    ]
    joined["entry_key"] = [_entry_key(vt, date) for vt, date in zip(joined["vt_symbol"], joined["entry_date"])]

    lots["entry_key"] = [_entry_key(vt, date) for vt, date in zip(lots["vt_symbol"], lots["entry_date"])]
    lot_ready = (
        lots.groupby("entry_key", as_index=False)
        .agg(
            stage095_lot_joined=("all_present_numeric_ready", "max"),
            stage095_numeric_ready_count=("numeric_ready_count", "max"),
            stage095_source_count=("source_count", "max"),
            stage095_first_target_date=("first_target_date", "min"),
            stage095_last_target_date=("last_target_date", "max"),
        )
    )
    frame = joined.merge(lot_ready, on="entry_key", how="left")
    frame["stage095_lot_joined"] = frame["stage095_lot_joined"].fillna(0).astype(int)
    frame["member_product_total_numeric_ready"] = frame["stage095_lot_joined"].astype(int)
    frame["member_detail_ready"] = 0
    frame["member_or_seat_id_ready"] = 0
    frame["member_category_ready"] = 0
    frame["seat_structure_ready"] = 0
    frame["contract_month_member_rank_source_ready"] = 0
    frame["member_role_structure_rule_ready"] = 0
    frame["missing_reason"] = np.where(
        frame["member_product_total_numeric_ready"].eq(1),
        "product_total_numeric_ready_but_no_member_category_or_seat_fields",
        "no_joined_product_total_feature_and_no_member_category_or_seat_fields",
    )
    keep = [
        "request_id",
        "exchange",
        "product",
        "product_root_clean",
        "vt_symbol",
        "direction",
        "decision_ts",
        "official_open_date",
        "entry_year",
        "risk_bad_label",
        "right_tail_label",
        "bottom_loss_visual",
        "maxdd_context",
        "stage095_lot_joined",
        "member_product_total_numeric_ready",
        "member_detail_ready",
        "member_or_seat_id_ready",
        "member_category_ready",
        "seat_structure_ready",
        "contract_month_member_rank_source_ready",
        "member_role_structure_rule_ready",
        "missing_reason",
    ]
    return frame[[column for column in keep if column in frame.columns]].copy()


def _build_entry_heatmap(entry_coverage: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        entry_coverage.groupby(["exchange", "entry_year"], dropna=False)
        .agg(
            entry_count=("request_id", "count"),
            product_total_ready_count=("member_product_total_numeric_ready", "sum"),
            role_ready_count=("member_role_structure_rule_ready", "sum"),
            risk_bad_count=("risk_bad_label", "sum"),
            right_tail_count=("right_tail_label", "sum"),
        )
        .reset_index()
    )
    grouped["product_total_ready_pct"] = grouped.apply(
        lambda row: _safe_div(row["product_total_ready_count"], row["entry_count"]), axis=1
    )
    grouped["role_ready_pct"] = grouped.apply(lambda row: _safe_div(row["role_ready_count"], row["entry_count"]), axis=1)
    return grouped


def _build_gate(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("public_rank_reports_exist", 1, "Official/public member volume and OI ranking reports exist."),
        ("local_raw_files_present", int(summary["stage091_raw_file_count"] > 0), "Stage091 CZCE raw files are present."),
        ("raw_hash_provenance_present", int(summary["stage095_member_raw_hash_ready_count"] > 0), "Stage095 keeps raw sha256."),
        ("product_total_numeric_parse_ready", int(summary["stage095_member_numeric_feature_rows"] > 0), "Product-total numeric rank fields are parsed."),
        ("entry_product_total_join_nonzero", int(summary["entry_product_total_numeric_ready_count"] > 0), "Some Stage239 entries can join product-total numeric context."),
        ("all_entries_have_role_fields", int(summary["role_ready_entry_count"] == summary["entry_count"]), "Every entry needs member role/category/seat fields."),
        ("member_or_seat_id_parsed", int(summary["member_or_seat_id_ready_entry_count"] == summary["entry_count"]), "Stable member/seat id must be parsed."),
        ("member_category_mapping_present", int(summary["member_category_ready_entry_count"] == summary["entry_count"]), "Member category or role mapping must exist."),
        ("contract_month_member_rank_source_present", int(summary["contract_month_source_ready_entry_count"] == summary["entry_count"]), "Member rank must be tied to contract month, not only product total."),
        ("publish_timestamp_and_license_ready", 0, "Publication timestamp and explicit license metadata are absent."),
        ("true_engine_allowed", 0, "This is a data-source audit; no true engine candidate exists."),
    ]
    frame = pd.DataFrame(rows, columns=["gate", "passed", "reason"])
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    return frame


def _build_summary(
    inputs: dict[str, pd.DataFrame],
    assets: pd.DataFrame,
    field_contract: pd.DataFrame,
    entry_coverage: pd.DataFrame,
    gate: pd.DataFrame,
) -> dict[str, Any]:
    feature = inputs["stage095_feature"]
    member_feature = feature[feature["source_family"].astype(str).eq("member_rank")].copy()
    stage251_summary = inputs["stage251_summary"]
    official = stage251_summary[stage251_summary.get("arm", pd.Series(dtype=str)).astype(str).eq("A_official_stage847_c9_15w")]
    official_row = official.iloc[0].to_dict() if not official.empty else stage251_summary.iloc[0].to_dict()

    raw_stats = _raw_file_stats()
    entry_count = len(entry_coverage)
    product_total_ready = int(entry_coverage["member_product_total_numeric_ready"].sum())
    role_ready = int(entry_coverage["member_role_structure_rule_ready"].sum())
    missing_role = entry_count - role_ready
    blocking_missing_fields = int(field_contract.query("blocking_if_missing == 1 and rule_ready == 0").shape[0])

    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage257_member_category_seat_structure_fields_absent_no_rule",
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
        "stage095_member_numeric_feature_rows": len(member_feature),
        "stage095_member_linked_lot_count": int(member_feature["lot_id"].nunique()) if "lot_id" in member_feature.columns else 0,
        "stage095_member_product_count": int(member_feature["product_root"].nunique()) if "product_root" in member_feature.columns else 0,
        "stage095_member_target_date_count": int(member_feature["target_date"].nunique()) if "target_date" in member_feature.columns else 0,
        "stage095_member_raw_hash_ready_count": int(member_feature["sha256"].notna().sum()) if "sha256" in member_feature.columns else 0,
        "stage091_raw_file_count": raw_stats["file_count"],
        "entry_product_total_numeric_ready_count": product_total_ready,
        "entry_product_total_numeric_ready_pct": _safe_div(product_total_ready, entry_count),
        "role_ready_entry_count": role_ready,
        "role_ready_entry_pct": _safe_div(role_ready, entry_count),
        "missing_role_structure_entry_count": missing_role,
        "member_or_seat_id_ready_entry_count": int(entry_coverage["member_or_seat_id_ready"].sum()),
        "member_category_ready_entry_count": int(entry_coverage["member_category_ready"].sum()),
        "seat_structure_ready_entry_count": int(entry_coverage["seat_structure_ready"].sum()),
        "contract_month_source_ready_entry_count": int(entry_coverage["contract_month_member_rank_source_ready"].sum()),
        "required_field_count": len(field_contract),
        "rule_ready_field_count": int(field_contract["rule_ready"].sum()),
        "blocking_missing_field_count": blocking_missing_fields,
        "asset_count": len(assets),
        "gate_pass_count": int(gate["passed"].sum()),
        "gate_total_count": len(gate),
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
    }
    return summary


def _plot_official_path(inputs: dict[str, pd.DataFrame], entry_coverage: pd.DataFrame) -> None:
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
    ax1.scatter(
        event_curve["date"],
        event_curve["account_equity"] / 1_000_000.0,
        s=24,
        color="#b91c1c",
        marker="x",
        alpha=0.78,
        label="Role/category/seat missing",
    )
    ready = event_curve[event_curve["member_product_total_numeric_ready"].eq(1)]
    ax1.scatter(
        ready["date"],
        ready["account_equity"] / 1_000_000.0,
        s=22,
        facecolor="none",
        edgecolor="#2563eb",
        linewidth=0.9,
        alpha=0.8,
        label="Product-total numeric context only",
    )
    ax1.set_ylabel("Equity (million CNY)")
    ax1.set_title("Official path with member role coverage status")
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
        "stage095_parsed_product_total_ready",
        "stage091_raw_report_inferred_ready",
        "legacy_topn_cache_ready",
        "rule_ready",
    ]
    matrix = field_contract.set_index("field")[columns].astype(float)
    fig, ax = plt.subplots(figsize=(10, 7.5))
    image = ax.imshow(matrix.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(["Stage095 parsed", "Stage091 raw", "Legacy cache", "Rule ready"], rotation=30, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            value = matrix.iloc[y, x]
            label = "1" if value >= 0.75 else ("partial" if value > 0 else "0")
            ax.text(x, y, label, ha="center", va="center", fontsize=8, color="#111827")
    ax.set_title("Field contract readiness for member category / seat structure")
    fig.colorbar(image, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(FIELD_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_asset_inventory(assets: pd.DataFrame) -> None:
    frame = assets.copy()
    frame["quantity"] = frame["row_count"].fillna(frame["file_count"]).fillna(0).astype(float)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    colors = np.where(
        frame["has_member_category"].astype(int).eq(1) | frame["has_seat_id"].astype(int).eq(1),
        "#16a34a",
        "#dc2626",
    )
    ax.barh(frame["asset_id"], np.maximum(frame["quantity"], 1), color=colors, alpha=0.82)
    ax.set_xscale("log")
    ax.set_xlabel("Rows or files (log scale, min=1)")
    ax.set_title("Local member-rank assets: quantity exists, role fields do not")
    for y, (_, row) in enumerate(frame.iterrows()):
        ax.text(
            max(float(row["quantity"]), 1) * 1.08,
            y,
            f"cat={int(row['has_member_category'])}, seat={int(row['has_seat_id'])}",
            va="center",
            fontsize=8,
        )
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ASSET_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_entry_heatmap(entry_heatmap: pd.DataFrame) -> None:
    pivot = entry_heatmap.pivot(index="exchange", columns="entry_year", values="role_ready_pct").fillna(0.0)
    count_pivot = entry_heatmap.pivot(index="exchange", columns="entry_year", values="entry_count").fillna(0).astype(int)
    product_pivot = entry_heatmap.pivot(index="exchange", columns="entry_year", values="product_total_ready_count").fillna(0).astype(int)
    if pivot.empty:
        pivot = pd.DataFrame([[0.0]], index=["none"], columns=["none"])
        count_pivot = pd.DataFrame([[0]], index=["none"], columns=["none"])
        product_pivot = pd.DataFrame([[0]], index=["none"], columns=["none"])

    fig, ax = plt.subplots(figsize=(11, 4.8))
    image = ax.imshow(pivot.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) if not pd.isna(col) else "NA" for col in pivot.columns], rotation=0)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y, exchange in enumerate(pivot.index):
        for x, year in enumerate(pivot.columns):
            total = int(count_pivot.loc[exchange, year])
            product_ready = int(product_pivot.loc[exchange, year])
            ax.text(x, y, f"role 0/{total}\nprod {product_ready}/{total}", ha="center", va="center", fontsize=8)
    ax.set_title("Entry coverage by exchange/year: role structure remains 0")
    ax.set_xlabel("Entry year")
    ax.set_ylabel("Exchange")
    fig.colorbar(image, ax=ax, shrink=0.85, label="Role-ready pct")
    fig.tight_layout()
    fig.savefig(ENTRY_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    frame = gate.copy().iloc[::-1]
    colors = np.where(frame["passed"].eq(1), "#16a34a", "#dc2626")
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.barh(frame["gate"], frame["passed"], color=colors, alpha=0.85)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Pass")
    ax.set_title("Promotion gate: data-source audit only")
    for y, (_, row) in enumerate(frame.iterrows()):
        ax.text(0.03 if row["passed"] else 0.03, y, "PASS" if row["passed"] else "BLOCK", va="center", fontsize=8, color="#111827")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=180)
    plt.close(fig)


def _write_report(summary: dict[str, Any]) -> None:
    report = f"""# Stage257 member category / seat structure source audit

Decision: `{summary['decision']}`

This stage is a read-only source and field-contract audit. It does not create a trading rule, does not run a true engine, does not trigger A/B, does not change the official configuration, and does not call any order API.

## Main result

- Stage239 entry rows: `{summary['entry_count']}`
- Product-total member-rank numeric context joined to entries: `{summary['entry_product_total_numeric_ready_count']}/{summary['entry_count']}` (`{summary['entry_product_total_numeric_ready_pct']:.4%}`)
- Member role/category/seat rule-ready entries: `{summary['role_ready_entry_count']}/{summary['entry_count']}` (`{summary['role_ready_entry_pct']:.4%}`)
- Missing role-structure entries: `{summary['missing_role_structure_entry_count']}`
- Blocking missing field count: `{summary['blocking_missing_field_count']}`
- Gate: `{summary['gate_pass_count']}/{summary['gate_total_count']}`

## Interpretation

Local files already contain useful public ranking material and Stage095 can parse CZCE product-total numeric sums. That is not the same as a role-aware member/seat structure. The required fields missing for a rule are stable member or seat id, member category, seat id, contract-month member-rank source, exact publication timestamp, and explicit license metadata.

The practical answer to the coverage question is: local product-total context can be counted, but the member category / seat structure route is still missing `{summary['missing_role_structure_entry_count']}` out of `{summary['entry_count']}` entry decisions. This is a field/schema gap, not a few-date backfill gap.

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
    placeholder_summary = {
        "stage091_raw_file_count": int(assets.loc[assets["asset_id"].eq("stage091_czce_member_rank_raw_files"), "file_count"].max()),
        "stage095_member_raw_hash_ready_count": int(
            inputs["stage095_feature"].loc[
                inputs["stage095_feature"]["source_family"].astype(str).eq("member_rank"),
                "sha256",
            ].notna().sum()
        ),
        "stage095_member_numeric_feature_rows": int(
            inputs["stage095_feature"]["source_family"].astype(str).eq("member_rank").sum()
        ),
        "entry_product_total_numeric_ready_count": int(entry_coverage["member_product_total_numeric_ready"].sum()),
        "entry_count": len(entry_coverage),
        "role_ready_entry_count": int(entry_coverage["member_role_structure_rule_ready"].sum()),
        "member_or_seat_id_ready_entry_count": int(entry_coverage["member_or_seat_id_ready"].sum()),
        "member_category_ready_entry_count": int(entry_coverage["member_category_ready"].sum()),
        "contract_month_source_ready_entry_count": int(entry_coverage["contract_month_member_rank_source_ready"].sum()),
    }
    gate = _build_gate(placeholder_summary)
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

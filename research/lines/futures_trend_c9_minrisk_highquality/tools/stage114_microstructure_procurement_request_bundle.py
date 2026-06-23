from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage114"
MODEL_TAG = "stage114_microstructure_procurement_request_bundle_v1"
OUTPUT_PREFIX = "qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage114_microstructure_procurement_request_bundle"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE113_WINDOWS_IN = (
    LINE_DIR
    / "outputs"
    / "stage113_microstructure_required_window_coverage"
    / "qmt_roll_stage113_c9_minrisk_microstructure_required_window_coverage_required_windows_"
    "stage113_microstructure_required_window_coverage_v1.csv"
)
STAGE113_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage113_microstructure_required_window_coverage"
    / "qmt_roll_stage113_c9_minrisk_microstructure_required_window_coverage_summary_"
    "stage113_microstructure_required_window_coverage_v1.csv"
)

REQUEST_MERGE_GAP_MINUTES = 10
MIN_REQUEST_SECONDS = 60
MBO_POLICY_NAMES = {"mbo_l3_preferred_mbp10_minimum"}
MBP_MIN_POLICY_NAMES = {"mbp10_minimum_mbo_accepted", "mbp10_or_mbo"}

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUEST_INTERVALS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_intervals_{MODEL_TAG}.csv"
PROCUREMENT_BATCHES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_procurement_batches_{MODEL_TAG}.csv"
REQUEST_PRIORITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_priority_queue_{MODEL_TAG}.csv"
PRODUCT_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_matrix_{MODEL_TAG}.csv"
STORAGE_LAYOUT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_storage_layout_plan_{MODEL_TAG}.csv"
MANIFEST_TEMPLATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_procurement_manifest_template_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_procurement_gate_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_request_priority_{MODEL_TAG}.png"
INTERVAL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_interval_chart_{MODEL_TAG}.png"
PRODUCT_YEAR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_heatmap_{MODEL_TAG}.png"
BATCH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_batch_complexity_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _product_from_vt_symbol(vt_symbol: str) -> str:
    symbol = vt_symbol.split(".")[0]
    matched = re.match(r"([A-Za-z]+)", symbol)
    return matched.group(1) if matched else symbol


def _exchange_from_vt_symbol(vt_symbol: str) -> str:
    return vt_symbol.split(".")[-1] if "." in vt_symbol else ""


def _request_schema(policy_values: list[str]) -> str:
    policies = set(policy_values)
    if policies & MBO_POLICY_NAMES:
        return "authorized_mbo_l3_preferred"
    if policies & MBP_MIN_POLICY_NAMES:
        return "authorized_mbp10_l2_minimum"
    return "authorized_mbp10_or_mbo"


def _load_windows() -> pd.DataFrame:
    windows = _read_csv(STAGE113_WINDOWS_IN)
    if windows.empty:
        raise RuntimeError(f"missing Stage113 required windows: {STAGE113_WINDOWS_IN}")
    for column in ["anchor_time", "window_start", "window_end"]:
        windows[column] = pd.to_datetime(windows[column], errors="coerce")
    windows = windows[windows["window_start"].notna() & windows["window_end"].notna()].copy()
    windows["exchange"] = windows["vt_symbol"].map(_exchange_from_vt_symbol)
    windows["product"] = windows["vt_symbol"].map(_product_from_vt_symbol)
    windows["trading_day"] = pd.to_datetime(windows["official_open_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    windows["year"] = pd.to_datetime(windows["official_open_date"], errors="coerce").dt.year.astype("Int64")
    windows["window_seconds"] = pd.to_numeric(windows["window_seconds"], errors="coerce").fillna(
        (windows["window_end"] - windows["window_start"]).dt.total_seconds()
    )
    return windows.sort_values(["vt_symbol", "trading_day", "window_start", "window_end"]).reset_index(drop=True)


def _build_request_intervals(windows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    merge_gap = pd.Timedelta(minutes=REQUEST_MERGE_GAP_MINUTES)
    request_index = 0
    group_cols = ["vt_symbol", "trading_day"]
    for (vt_symbol, trading_day), group in windows.groupby(group_cols, dropna=False):
        current: dict[str, Any] | None = None
        for _, row in group.sort_values("window_start").iterrows():
            start = pd.Timestamp(row["window_start"])
            end = pd.Timestamp(row["window_end"])
            if current is None or start > current["request_end"] + merge_gap:
                if current is not None:
                    rows.append(current)
                request_index += 1
                current = {
                    "request_id": f"stage114_req_{request_index:04d}",
                    "vt_symbol": vt_symbol,
                    "exchange": row["exchange"],
                    "product": row["product"],
                    "trading_day": trading_day,
                    "year": int(row["year"]) if pd.notna(row["year"]) else "",
                    "request_start": start,
                    "request_end": end,
                    "covered_window_ids": [row["window_id"]],
                    "candidate_indices": [int(row["candidate_index"])],
                    "window_types": [row["window_type"]],
                    "schema_policies": [row["required_schema_policy"]],
                    "visual_priority_count": int(row["visual_priority"]),
                    "right_tail_window_count": int(row["right_tail_visual"]),
                    "bottom_loss_window_count": int(row["bottom_loss_visual"]),
                    "maxdd_context_window_count": int(row["maxdd_context"]),
                    "orderflow_required_window_count": int(row["orderflow_required"]),
                    "low_resolution_window_count": int(row["low_resolution_zone"]),
                    "realized_pnl_sum": float(pd.to_numeric(row["order_realized_pnl"], errors="coerce") or 0),
                }
                continue
            current["request_end"] = max(current["request_end"], end)
            current["covered_window_ids"].append(row["window_id"])
            current["candidate_indices"].append(int(row["candidate_index"]))
            current["window_types"].append(row["window_type"])
            current["schema_policies"].append(row["required_schema_policy"])
            current["visual_priority_count"] += int(row["visual_priority"])
            current["right_tail_window_count"] += int(row["right_tail_visual"])
            current["bottom_loss_window_count"] += int(row["bottom_loss_visual"])
            current["maxdd_context_window_count"] += int(row["maxdd_context"])
            current["orderflow_required_window_count"] += int(row["orderflow_required"])
            current["low_resolution_window_count"] += int(row["low_resolution_zone"])
            current["realized_pnl_sum"] += float(pd.to_numeric(row["order_realized_pnl"], errors="coerce") or 0)
        if current is not None:
            rows.append(current)

    intervals = pd.DataFrame(rows)
    if intervals.empty:
        return intervals
    intervals["request_seconds"] = (intervals["request_end"] - intervals["request_start"]).dt.total_seconds().clip(lower=MIN_REQUEST_SECONDS).astype(int)
    intervals["window_count"] = intervals["covered_window_ids"].map(len)
    intervals["candidate_count"] = intervals["candidate_indices"].map(lambda values: len(set(values)))
    intervals["window_type_set"] = intervals["window_types"].map(lambda values: ";".join(sorted(set(map(str, values)))))
    intervals["window_types"] = intervals["window_types"].map(lambda values: ";".join(map(str, values)))
    intervals["required_schema_request"] = intervals["schema_policies"].map(_request_schema)
    intervals["covered_window_ids"] = intervals["covered_window_ids"].map(lambda values: ";".join(map(str, values)))
    intervals["candidate_indices"] = intervals["candidate_indices"].map(lambda values: ";".join(map(str, sorted(set(values)))))
    intervals["schema_policies"] = intervals["schema_policies"].map(lambda values: ";".join(sorted(set(map(str, values)))))
    intervals["priority_score"] = (
        intervals["visual_priority_count"] * 100
        + intervals["right_tail_window_count"] * 80
        + intervals["bottom_loss_window_count"] * 80
        + intervals["maxdd_context_window_count"] * 50
        + intervals["orderflow_required_window_count"] * 10
        + intervals["window_count"]
    )
    intervals["request_start"] = pd.to_datetime(intervals["request_start"], errors="coerce")
    intervals["request_end"] = pd.to_datetime(intervals["request_end"], errors="coerce")
    return intervals.sort_values(["priority_score", "request_start"], ascending=[False, True]).reset_index(drop=True)


def _build_batches(intervals: pd.DataFrame) -> pd.DataFrame:
    if intervals.empty:
        return pd.DataFrame()
    rows = []
    for (year, exchange, product, schema), group in intervals.groupby(["year", "exchange", "product", "required_schema_request"], dropna=False):
        rows.append(
            {
                "batch_id": f"stage114_batch_{len(rows)+1:03d}",
                "year": year,
                "exchange": exchange,
                "product": product,
                "required_schema_request": schema,
                "request_count": len(group),
                "symbol_count": group["vt_symbol"].nunique(),
                "trading_day_count": group["trading_day"].nunique(),
                "window_count": int(group["window_count"].sum()),
                "visual_priority_count": int(group["visual_priority_count"].sum()),
                "right_tail_window_count": int(group["right_tail_window_count"].sum()),
                "bottom_loss_window_count": int(group["bottom_loss_window_count"].sum()),
                "maxdd_context_window_count": int(group["maxdd_context_window_count"].sum()),
                "total_request_seconds": int(group["request_seconds"].sum()),
                "query_start_min": group["request_start"].min(),
                "query_end_max": group["request_end"].max(),
                "vt_symbols": ";".join(sorted(group["vt_symbol"].unique())),
                "request_ids": ";".join(group["request_id"].tolist()),
            }
        )
    batches = pd.DataFrame(rows)
    batches["priority_score"] = (
        batches["visual_priority_count"] * 100
        + batches["right_tail_window_count"] * 80
        + batches["bottom_loss_window_count"] * 80
        + batches["maxdd_context_window_count"] * 50
        + batches["window_count"]
    )
    return batches.sort_values(["priority_score", "year", "exchange", "product"], ascending=[False, True, True, True]).reset_index(drop=True)


def _priority_queue(intervals: pd.DataFrame) -> pd.DataFrame:
    if intervals.empty:
        return pd.DataFrame()
    cols = [
        "request_id",
        "priority_score",
        "vt_symbol",
        "exchange",
        "product",
        "trading_day",
        "request_start",
        "request_end",
        "request_seconds",
        "required_schema_request",
        "window_count",
        "candidate_count",
        "visual_priority_count",
        "right_tail_window_count",
        "bottom_loss_window_count",
        "maxdd_context_window_count",
        "orderflow_required_window_count",
        "window_type_set",
        "covered_window_ids",
    ]
    return intervals[cols].sort_values(["priority_score", "request_start"], ascending=[False, True]).reset_index(drop=True)


def _product_year_matrix(intervals: pd.DataFrame) -> pd.DataFrame:
    if intervals.empty:
        return pd.DataFrame()
    matrix = (
        intervals.groupby(["product", "exchange", "year"], as_index=False)
        .agg(
            request_count=("request_id", "count"),
            symbol_count=("vt_symbol", "nunique"),
            trading_day_count=("trading_day", "nunique"),
            window_count=("window_count", "sum"),
            visual_priority_count=("visual_priority_count", "sum"),
            right_tail_window_count=("right_tail_window_count", "sum"),
            bottom_loss_window_count=("bottom_loss_window_count", "sum"),
            maxdd_context_window_count=("maxdd_context_window_count", "sum"),
            total_request_seconds=("request_seconds", "sum"),
        )
        .sort_values(["visual_priority_count", "window_count", "year"], ascending=[False, False, True])
    )
    return matrix.reset_index(drop=True)


def _storage_layout_plan() -> pd.DataFrame:
    rows = [
        {
            "layout_id": "raw_vendor_archive",
            "root": "raw/{source_vendor}/{schema_type}/exchange={exchange}/product={product}/trading_day={YYYY-MM-DD}/",
            "file_rule": "preserve_original_vendor_payload_or_archive_name",
            "partition_reason": "keeps raw provenance and exchange/product/day lookup without per-window tiny files",
            "required_manifest_fields": "source_vendor;schema_type;exchange;product;trading_day;raw_file;raw_sha256;query_params;source_license",
        },
        {
            "layout_id": "normalized_event_parquet",
            "root": "data/{source_vendor}/{schema_type}/exchange={exchange}/product={product}/year={YYYY}/trading_day={YYYY-MM-DD}/",
            "file_rule": "one_or_few_parquet_files_per_product_day_schema_after_compaction",
            "partition_reason": "supports window filtering by symbol/time while avoiding candidate-level fragmentation",
            "required_manifest_fields": "data_file;schema_hash;row_count;min_ts_event;max_ts_event;sequence_gap_count;covered_window_ids",
        },
        {
            "layout_id": "coverage_proof",
            "root": "proof/{source_vendor}/{schema_type}/exchange={exchange}/product={product}/trading_day={YYYY-MM-DD}/",
            "file_rule": "coverage_proof_json_or_csv_per_product_day",
            "partition_reason": "stores sequence-gap and window-span proof separate from strategy features",
            "required_manifest_fields": "proof_file;proof_sha256;sequence_gap_count;capture_start;capture_end;window_ids",
        },
    ]
    return pd.DataFrame(rows)


def _manifest_template(intervals: pd.DataFrame) -> pd.DataFrame:
    sample = intervals.head(12).copy() if not intervals.empty else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, row in sample.iterrows():
        rows.append(
            {
                "example_only": 1,
                "request_id": row["request_id"],
                "dataset_id": "authorized_vendor_or_exchange_dataset",
                "source_vendor": "authorized_vendor_or_exchange",
                "schema_type": row["required_schema_request"],
                "exchange": row["exchange"],
                "product": row["product"],
                "vt_symbol": row["vt_symbol"],
                "trading_day": row["trading_day"],
                "query_start": row["request_start"],
                "query_end": row["request_end"],
                "timezone": "Asia/Shanghai",
                "query_params": "symbols/schema/start/end/split_duration/or_vendor_equivalent",
                "raw_file": "raw/{vendor}/{schema}/exchange={exchange}/product={product}/trading_day={day}/source_payload.bin",
                "raw_sha256": "required_raw_sha256_hex",
                "data_file": "data/{vendor}/{schema}/exchange={exchange}/product={product}/year={YYYY}/trading_day={day}/events.parquet",
                "schema_hash": "required_schema_hash_hex",
                "source_license": "research_allowed_contract_or_written_permission",
                "sequence_gap_count": 0,
                "coverage_proof": "proof json/csv path with ts_event span and sequence continuity",
                "covered_window_ids": row["covered_window_ids"],
                "notes": "Example row only; not accepted until Stage112 and Stage113 both pass.",
            }
        )
    return pd.DataFrame(rows)


def _procurement_gate(intervals: pd.DataFrame, batches: pd.DataFrame, manifest_template: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "gate_id": "request_intervals_built",
            "observed": str(len(intervals)),
            "required": ">0 request intervals",
            "pass_now": int(len(intervals) > 0),
            "severity": "soft_planning",
        },
        {
            "gate_id": "all_stage113_windows_mapped_to_requests",
            "observed": str(int(intervals["window_count"].sum()) if not intervals.empty else 0),
            "required": "485 windows",
            "pass_now": int((int(intervals["window_count"].sum()) if not intervals.empty else 0) == 485),
            "severity": "hard_planning",
        },
        {
            "gate_id": "procurement_batches_built",
            "observed": str(len(batches)),
            "required": ">0 grouped batches",
            "pass_now": int(len(batches) > 0),
            "severity": "soft_planning",
        },
        {
            "gate_id": "manifest_template_built",
            "observed": str(len(manifest_template)),
            "required": ">0 template rows",
            "pass_now": int(len(manifest_template) > 0),
            "severity": "soft_planning",
        },
        {
            "gate_id": "authorized_data_downloaded",
            "observed": "0",
            "required": "raw/data/proof files present after vendor/exchange delivery",
            "pass_now": 0,
            "severity": "hard_data",
        },
        {
            "gate_id": "stage112_stage113_acceptance_passed",
            "observed": "0",
            "required": "Stage112 and Stage113 hard gates pass after data arrival",
            "pass_now": 0,
            "severity": "hard_data",
        },
    ]
    return pd.DataFrame(rows)


def _summary(
    windows: pd.DataFrame,
    intervals: pd.DataFrame,
    batches: pd.DataFrame,
    product_year: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    stage113 = _read_csv(STAGE113_SUMMARY_IN)
    stage113_row = stage113.iloc[0] if not stage113.empty else pd.Series(dtype=object)
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage114_procurement_request_bundle_built_no_data_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "required_window_count": int(len(windows)),
                "request_interval_count": int(len(intervals)),
                "procurement_batch_count": int(len(batches)),
                "product_year_cell_count": int(len(product_year)),
                "unique_vt_symbol_count": int(intervals["vt_symbol"].nunique()) if not intervals.empty else 0,
                "unique_product_count": int(intervals["product"].nunique()) if not intervals.empty else 0,
                "unique_exchange_count": int(intervals["exchange"].nunique()) if not intervals.empty else 0,
                "unique_trading_day_count": int(intervals["trading_day"].nunique()) if not intervals.empty else 0,
                "total_request_seconds": int(intervals["request_seconds"].sum()) if not intervals.empty else 0,
                "total_request_hours": float(intervals["request_seconds"].sum() / 3600.0) if not intervals.empty else 0.0,
                "mbo_preferred_request_count": int(intervals["required_schema_request"].eq("authorized_mbo_l3_preferred").sum()) if not intervals.empty else 0,
                "mbp10_minimum_request_count": int(intervals["required_schema_request"].eq("authorized_mbp10_l2_minimum").sum()) if not intervals.empty else 0,
                "visual_priority_request_count": int(intervals["visual_priority_count"].gt(0).sum()) if not intervals.empty else 0,
                "right_tail_request_count": int(intervals["right_tail_window_count"].gt(0).sum()) if not intervals.empty else 0,
                "bottom_loss_request_count": int(intervals["bottom_loss_window_count"].gt(0).sum()) if not intervals.empty else 0,
                "maxdd_context_request_count": int(intervals["maxdd_context_window_count"].gt(0).sum()) if not intervals.empty else 0,
                "procurement_gate_count": int(len(gate)),
                "procurement_gate_pass_count": int(gate["pass_now"].sum()) if not gate.empty else 0,
                "next_recommended_route": "send_or_execute_procurement_bundle_then_drop_files_into_stage112_intake_root",
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(stage113_row.get("end_equity", 0) or 0),
                "total_return_pct": float(stage113_row.get("total_return_pct", 0) or 0),
                "max_drawdown_pct": float(stage113_row.get("max_drawdown_pct", 0) or 0),
                "sharpe": float(stage113_row.get("sharpe", 0) or 0),
                "total_slippage": float(stage113_row.get("total_slippage", 0) or 0),
                "total_trade_count": float(stage113_row.get("total_trade_count", 0) or 0),
                "closed_lot_win_rate_pct": float(stage113_row.get("closed_lot_win_rate_pct", 0) or 0),
                "max_broker10_margin_to_equity_pct": float(stage113_row.get("max_broker10_margin_to_equity_pct", 0) or 0),
            }
        ]
    )


def _plot_path(curve: pd.DataFrame, intervals: pd.DataFrame) -> None:
    if intervals.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, "No request intervals", ha="center", va="center")
        ax.axis("off")
        fig.savefig(PATH_CHART_OUT, dpi=160)
        plt.close(fig)
        return
    by_day = (
        intervals.groupby("trading_day", as_index=False)
        .agg(
            priority_score=("priority_score", "sum"),
            visual_priority_count=("visual_priority_count", "sum"),
            request_count=("request_id", "count"),
        )
        .sort_values("trading_day")
    )
    by_day["trading_day"] = pd.to_datetime(by_day["trading_day"], errors="coerce")
    points = _nearest_curve_points(curve, by_day["trading_day"]).reset_index(drop=True)
    if len(by_day) == len(points):
        by_day = pd.concat([by_day.reset_index(drop=True), points[["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]]], axis=1)
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#111827", lw=1.2)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.0)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8)
    sizes = 20 + np.sqrt(by_day["priority_score"].clip(lower=1)) * 3
    colors = np.where(by_day["visual_priority_count"].gt(0), "#dc2626", "#64748b")
    for ax, column, scale in [
        (axes[0], "account_equity", 1_000_000),
        (axes[1], "drawdown_pct", 1),
        (axes[2], "broker10_margin_to_equity_pct", 1),
    ]:
        ax.scatter(
            by_day["trading_day"],
            by_day[column] / scale,
            s=sizes,
            c=colors,
            edgecolors="#111827",
            linewidths=0.4,
            alpha=0.78,
        )
    axes[0].set_title("Stage114 official path: procurement request priority across equity/drawdown path")
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_interval_chart(intervals: pd.DataFrame) -> None:
    data = (
        intervals.groupby("year", as_index=False)
        .agg(
            request_count=("request_id", "count"),
            total_request_seconds=("request_seconds", "sum"),
            visual_priority_count=("visual_priority_count", "sum"),
        )
        .sort_values("year")
    )
    fig, ax1 = plt.subplots(figsize=(12, 5.5))
    ax1.bar(data["year"].astype(str), data["request_count"], color="#64748b", alpha=0.86, label="request count")
    ax2 = ax1.twinx()
    ax2.plot(data["year"].astype(str), data["total_request_seconds"] / 3600.0, color="#dc2626", marker="o", label="request hours")
    ax1.set_ylabel("request count")
    ax2.set_ylabel("request hours")
    ax1.set_title("Stage114 request intervals by year")
    ax1.grid(axis="y", alpha=0.25)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(INTERVAL_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year(product_year: pd.DataFrame) -> None:
    if product_year.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, "No product-year matrix", ha="center", va="center")
        ax.axis("off")
        fig.savefig(PRODUCT_YEAR_CHART_OUT, dpi=160)
        plt.close(fig)
        return
    data = product_year.copy()
    data["product_exchange"] = data["product"].astype(str) + "." + data["exchange"].astype(str)
    pivot = data.pivot_table(index="product_exchange", columns="year", values="window_count", aggfunc="sum", fill_value=0)
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(12, max(5.5, 0.28 * len(pivot))))
    im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="YlGnBu")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(col) for col in pivot.columns])
    ax.set_title("Stage114 product-year required window count")
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            value = int(pivot.iloc[y, x])
            if value:
                ax.text(x, y, str(value), ha="center", va="center", color="#111827", fontsize=7)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_batch_chart(batches: pd.DataFrame) -> None:
    top = batches.head(20).copy()
    labels = top["product"].astype(str) + "." + top["exchange"].astype(str) + " " + top["year"].astype(str)
    fig, ax = plt.subplots(figsize=(12, max(5.5, 0.36 * len(top))))
    ax.barh(labels, top["window_count"], color="#0369a1", alpha=0.86, label="windows")
    ax.barh(labels, top["visual_priority_count"], color="#dc2626", alpha=0.62, label="visual priority")
    ax.invert_yaxis()
    ax.set_xlabel("count")
    ax.set_title("Stage114 top procurement batches by required windows")
    ax.legend(fontsize=8)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(BATCH_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    intervals: pd.DataFrame,
    batches: pd.DataFrame,
    product_year: pd.DataFrame,
    storage_layout: pd.DataFrame,
    manifest_template: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage114 microstructure procurement request bundle",
        "",
        "## Decision",
        "",
        f"- decision: `{row['decision']}`",
        "- nature: read-only procurement/request bundle; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.",
        "- question: can Stage113 required windows be converted into an executable vendor-neutral request and storage manifest?",
        "",
        "## Baseline Path",
        "",
        f"- end equity: `{row['end_equity']:,.2f}`",
        f"- total return: `{row['total_return_pct']:.4f}%`",
        f"- max drawdown: `{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe: `{row['sharpe']:.4f}`",
        f"- total slippage: `{row['total_slippage']:,.0f}`",
        f"- total trade count: `{row['total_trade_count']:.0f}`",
        f"- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`",
        "",
        "## Key Metrics",
        "",
        _md_table(summary),
        "",
        "## Request Intervals",
        "",
        _md_table(intervals.head(25), max_rows=25),
        "",
        "## Procurement Batches",
        "",
        _md_table(batches.head(25), max_rows=25),
        "",
        "## Product-Year Matrix",
        "",
        _md_table(product_year.head(40), max_rows=40),
        "",
        "## Storage Layout",
        "",
        _md_table(storage_layout, max_rows=10),
        "",
        "## Manifest Template Sample",
        "",
        _md_table(manifest_template.head(12), max_rows=12),
        "",
        "## Procurement Gates",
        "",
        _md_table(gate, max_rows=10),
        "",
        "## Visual Outputs",
        "",
        f"- official path request priority: `{PATH_CHART_OUT}`",
        f"- request interval chart: `{INTERVAL_CHART_OUT}`",
        f"- product-year heatmap: `{PRODUCT_YEAR_CHART_OUT}`",
        f"- batch complexity chart: `{BATCH_CHART_OUT}`",
        "",
        "## External Research Judgment",
        "",
        (
            "Historical data APIs commonly organize requests by symbols, schema, start/end and split duration. "
            "Parquet/Arrow partitioning can help query by date/product, but overly fine candidate-level partitions create small-file risk. "
            "Stage114 therefore groups windows by vt_symbol/trading day for requests and proposes product/day parquet partitions with raw/proof manifests."
        ),
        "",
        "## Judgment",
        "",
        (
            "This stage converts the blocker into a concrete procurement plan. It still does not create strategy evidence: "
            "only after raw/data/proof files arrive and pass Stage112 and Stage113 can a microstructure rule preflight begin."
        ),
        "",
    ]
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    windows = _load_windows()
    intervals = _build_request_intervals(windows)
    batches = _build_batches(intervals)
    priority = _priority_queue(intervals)
    product_year = _product_year_matrix(intervals)
    storage_layout = _storage_layout_plan()
    manifest_template = _manifest_template(intervals)
    gate = _procurement_gate(intervals, batches, manifest_template)
    summary = _summary(windows, intervals, batches, product_year, gate)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(intervals, REQUEST_INTERVALS_OUT)
    _write_csv(batches, PROCUREMENT_BATCHES_OUT)
    _write_csv(priority, REQUEST_PRIORITY_OUT)
    _write_csv(product_year, PRODUCT_YEAR_OUT)
    _write_csv(storage_layout, STORAGE_LAYOUT_OUT)
    _write_csv(manifest_template, MANIFEST_TEMPLATE_OUT)
    _write_csv(gate, GATE_OUT)

    _plot_path(curve, intervals)
    _plot_interval_chart(intervals)
    _plot_product_year(product_year)
    _plot_batch_chart(batches)
    _write_report(summary, intervals, batches, product_year, storage_layout, manifest_template, gate)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "request_intervals_path": str(REQUEST_INTERVALS_OUT),
        "procurement_batches_path": str(PROCUREMENT_BATCHES_OUT),
        "request_priority_queue_path": str(REQUEST_PRIORITY_OUT),
        "product_year_matrix_path": str(PRODUCT_YEAR_OUT),
        "storage_layout_plan_path": str(STORAGE_LAYOUT_OUT),
        "manifest_template_path": str(MANIFEST_TEMPLATE_OUT),
        "procurement_gate_path": str(GATE_OUT),
        "charts": [str(PATH_CHART_OUT), str(INTERVAL_CHART_OUT), str(PRODUCT_YEAR_CHART_OUT), str(BATCH_CHART_OUT)],
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

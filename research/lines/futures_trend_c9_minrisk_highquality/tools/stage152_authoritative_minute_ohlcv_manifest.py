from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage152"
MODEL_TAG = "stage152_authoritative_minute_ohlcv_manifest_v1"
OUTPUT_PREFIX = "qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage152_authoritative_minute_ohlcv_manifest"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE102_ROWS_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_resolution_rows_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)
STAGE151_DIR = LINE_DIR / "outputs" / "stage151_point_in_time_external_source_router"
STAGE151_PREFIX = "qmt_roll_stage151_c9_minrisk_point_in_time_external_source_router"
STAGE151_TAG = "stage151_point_in_time_external_source_router_v1"
STAGE151_SUMMARY_IN = STAGE151_DIR / f"{STAGE151_PREFIX}_summary_{STAGE151_TAG}.csv"
STAGE151_REQUIREMENTS_IN = STAGE151_DIR / f"{STAGE151_PREFIX}_manifest_requirements_{STAGE151_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FIELD_SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_schema_{MODEL_TAG}.csv"
WINDOW_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_window_contract_{MODEL_TAG}.csv"
REQUEST_TEMPLATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_manifest_template_{MODEL_TAG}.csv"
COVERAGE_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_gate_{MODEL_TAG}.csv"
OPERATOR_CHECKLIST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_intake_checklist_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_manifest_status_{MODEL_TAG}.png"
FIELD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_schema_matrix_{MODEL_TAG}.png"
WINDOW_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_window_heatmap_{MODEL_TAG}.png"
REQUEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_template_product_chart_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

WINDOW_SPECS = [
    {
        "window_type": "entry_pre30_post120",
        "start_offset_minutes": -30,
        "end_offset_minutes": 120,
        "anchor": "scan_start",
        "purpose": "entry quality and high-quality signal context",
    },
    {
        "window_type": "event_buffer_15m",
        "start_offset_minutes": -15,
        "end_offset_minutes": 15,
        "anchor": "event_time",
        "purpose": "event touch and orderability context",
    },
    {
        "window_type": "session_guard_to_event_or_240m",
        "start_offset_minutes": 0,
        "end_offset_minutes": None,
        "anchor": "scan_start",
        "purpose": "full survival path until event or four-hour guardrail",
    },
]


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
        else:
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|"))
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(number) or np.isinf(number):
        return default
    return number


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(_num(row, key, float(default))))


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _exchange_from_symbol(vt_symbol: Any) -> str:
    text = "" if pd.isna(vt_symbol) else str(vt_symbol)
    return text.rsplit(".", 1)[-1] if "." in text else "UNKNOWN"


def _product_from_symbol(row: pd.Series) -> str:
    product = row.get("product")
    if pd.notna(product) and str(product).strip():
        return str(product)
    symbol = str(row.get("vt_symbol", "UNKNOWN"))
    exchange = _exchange_from_symbol(symbol)
    root = "".join(ch for ch in symbol.split(".")[0] if ch.isalpha()) or symbol.split(".")[0]
    return f"{root}.{exchange}"


def _priority_class(row: pd.Series) -> str:
    if int(row.get("right_tail_visual", 0)) == 1:
        return "right_tail"
    if int(row.get("bottom_loss_visual", 0)) == 1:
        return "bottom_loss"
    if int(row.get("maxdd_context", 0)) == 1:
        return "maxdd_context"
    if int(row.get("low_resolution_zone", 0)) == 1:
        return "low_resolution"
    return "ordinary"


def _prepare_stage102_rows(rows102: pd.DataFrame) -> pd.DataFrame:
    if rows102.empty:
        raise RuntimeError(f"missing Stage102 rows input: {STAGE102_ROWS_IN}")
    rows = rows102.copy()
    rows["official_open_date"] = pd.to_datetime(rows["official_open_date"], errors="coerce").dt.normalize()
    rows["replay_event_time_parsed"] = pd.to_datetime(rows["replay_c9_first_event_time"], errors="coerce")
    numeric_cols = [
        "candidate_index",
        "minutes_from_open_to_event",
        "right_tail_visual",
        "bottom_loss_visual",
        "maxdd_context",
        "low_resolution_zone",
        "completed_bars_before_event",
        "order_realized_pnl",
        "order_lot_count",
    ]
    for column in numeric_cols:
        rows[column] = pd.to_numeric(rows.get(column, 0), errors="coerce").fillna(0)
    rows["vt_symbol"] = rows["vt_symbol"].fillna("UNKNOWN")
    rows["exchange"] = rows["vt_symbol"].map(_exchange_from_symbol)
    rows["product"] = rows.apply(_product_from_symbol, axis=1)
    rows["priority_class"] = rows.apply(_priority_class, axis=1)
    rows["event_time_missing"] = rows["replay_event_time_parsed"].isna().astype(int)

    fallback_scan_start = rows["official_open_date"] + pd.Timedelta(hours=9)
    minutes_delta = pd.to_timedelta(rows["minutes_from_open_to_event"].clip(lower=0), unit="m")
    rows["anchor_scan_start"] = rows["replay_event_time_parsed"] - minutes_delta
    rows.loc[rows["anchor_scan_start"].isna(), "anchor_scan_start"] = fallback_scan_start
    rows["anchor_event_time"] = rows["replay_event_time_parsed"]
    rows.loc[rows["anchor_event_time"].isna(), "anchor_event_time"] = (
        rows.loc[rows["anchor_event_time"].isna(), "anchor_scan_start"]
        + pd.to_timedelta(rows.loc[rows["anchor_event_time"].isna(), "minutes_from_open_to_event"].clip(lower=0), unit="m")
    )
    rows["anchor_event_time_source"] = np.where(
        rows["event_time_missing"].eq(1),
        "fallback_from_open_date_plus_minutes",
        "stage102_replay_c9_first_event_time",
    )
    return rows.reset_index(drop=True)


def _build_required_windows(rows: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        scan_start = pd.Timestamp(row["anchor_scan_start"])
        event_time = pd.Timestamp(row["anchor_event_time"])
        for spec in WINDOW_SPECS:
            if spec["anchor"] == "event_time":
                anchor_time = event_time
            else:
                anchor_time = scan_start
            start_ts = anchor_time + pd.Timedelta(minutes=int(spec["start_offset_minutes"]))
            if spec["window_type"] == "session_guard_to_event_or_240m":
                end_ts = max(event_time, scan_start + pd.Timedelta(minutes=240))
            else:
                end_ts = anchor_time + pd.Timedelta(minutes=int(spec["end_offset_minutes"]))
            if end_ts < start_ts:
                end_ts = start_ts
            duration_minutes = max(0.0, (end_ts - start_ts).total_seconds() / 60.0)
            estimated_bars = int(np.ceil(duration_minutes)) + 1
            candidate_index = int(row["candidate_index"])
            records.append(
                {
                    "window_id": f"stage152_{candidate_index:04d}_{spec['window_type']}",
                    "candidate_index": candidate_index,
                    "official_open_trade_id": row.get("official_open_trade_id", ""),
                    "vt_symbol": row["vt_symbol"],
                    "exchange": row["exchange"],
                    "product": row["product"],
                    "direction": row.get("direction", ""),
                    "official_open_date": pd.Timestamp(row["official_open_date"]).strftime("%Y-%m-%d"),
                    "anchor_scan_start": scan_start.strftime("%Y-%m-%d %H:%M:%S"),
                    "anchor_event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "anchor_event_time_source": row["anchor_event_time_source"],
                    "window_type": spec["window_type"],
                    "window_purpose": spec["purpose"],
                    "window_start_ts": start_ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "window_end_ts": end_ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "request_date": start_ts.strftime("%Y-%m-%d"),
                    "duration_minutes": duration_minutes,
                    "estimated_required_1m_bars": estimated_bars,
                    "priority_class": row["priority_class"],
                    "right_tail_visual": int(row["right_tail_visual"]),
                    "bottom_loss_visual": int(row["bottom_loss_visual"]),
                    "maxdd_context": int(row["maxdd_context"]),
                    "low_resolution_zone": int(row["low_resolution_zone"]),
                    "event_time_missing": int(row["event_time_missing"]),
                    "resolution_bucket": row.get("resolution_bucket", ""),
                    "must_cover": 1,
                    "data_ready_now": 0,
                    "rule_allowed": 0,
                }
            )
    return pd.DataFrame(records)


def _field_schema(stage151_requirements: pd.DataFrame) -> pd.DataFrame:
    stage151_hard = set()
    if not stage151_requirements.empty and "field" in stage151_requirements.columns:
        hard = pd.to_numeric(stage151_requirements.get("hard_gate", 0), errors="coerce").fillna(0).eq(1)
        stage151_hard = set(stage151_requirements.loc[hard, "field"].astype(str))
    rows = [
        ("vendor_name", "provenance", "string", 1, 1, "Licensed data vendor or exchange source name."),
        ("vendor_license", "provenance", "string", 1, 1, "License proof allowing strategy research and derived artifacts."),
        ("dataset_id", "provenance", "string", 1, 1, "Dataset or product code used for the query."),
        ("query_params", "provenance", "json", 1, 1, "Exact symbol/date/session/interval/adjustment parameters."),
        ("raw_file", "path", "path", 1, 1, "Immutable original file before normalization."),
        ("raw_sha256", "hash", "hex64", 1, 1, "SHA256 of raw file."),
        ("schema_hash", "hash", "hex64", 1, 1, "Stable hash of raw and normalized schema."),
        ("normalization_version", "provenance", "string", 1, 1, "Parser version used for normalized file."),
        ("exchange", "identity", "string", 1, 1, "Exchange code matching vt_symbol suffix."),
        ("vt_symbol", "identity", "string", 1, 1, "Contract-level symbol, never product aggregate only."),
        ("bar_start_ts", "timestamp", "datetime64[ns]", 1, 1, "Bar start timestamp in Asia/Shanghai convention."),
        ("bar_end_ts", "timestamp", "datetime64[ns]", 1, 1, "Bar end timestamp or declared end-exclusive convention."),
        ("timezone", "calendar", "string", 1, 1, "Timezone; expected Asia/Shanghai for domestic futures."),
        ("session_calendar", "calendar", "string/json", 1, 1, "Night/day session and holiday stitching convention."),
        ("open", "price", "float64", 1, 1, "Unadjusted bar open."),
        ("high", "price", "float64", 1, 1, "Unadjusted bar high."),
        ("low", "price", "float64", 1, 1, "Unadjusted bar low."),
        ("close", "price", "float64", 1, 1, "Unadjusted bar close."),
        ("volume", "liquidity", "float64", 1, 1, "Real traded volume; proxy zero-volume bars are not enough."),
        ("turnover", "liquidity", "float64", 1, 0, "Turnover if provided; unit must be declared."),
        ("open_interest", "liquidity", "float64", 1, 0, "Contract-level OI if provided at minute or session close."),
        ("sequence_gap_count", "quality", "int64", 1, 1, "Missing expected minute slots inside required windows."),
        ("duplicate_bar_count", "quality", "int64", 1, 1, "Duplicate bar_start_ts count inside required windows."),
        ("right_tail_window_coverage", "coverage", "float64", 1, 1, "Coverage ratio for right-tail context windows."),
        ("bottom_loss_window_coverage", "coverage", "float64", 1, 1, "Coverage ratio for bottom-loss context windows."),
        ("maxdd_window_coverage", "coverage", "float64", 1, 1, "Coverage ratio for maxDD-context windows."),
        ("no_trade_bar_policy", "quality", "string", 1, 1, "Explicit handling of no-trade intervals and absent bars."),
        ("synthetic_or_adjusted_flag", "quality", "int64", 1, 1, "Must prove no synthetic/smoke/future-adjusted bars are used."),
    ]
    frame = pd.DataFrame(
        [
            {
                "field": field,
                "field_group": group,
                "canonical_dtype": dtype,
                "required_for_stage152_manifest": required,
                "hard_gate": hard_gate,
                "also_required_by_stage151": int(field in stage151_hard),
                "contract_defined": 1,
                "current_ready": 0,
                "description": description,
            }
            for field, group, dtype, required, hard_gate, description in rows
        ]
    )
    return frame


def _build_request_template(windows: pd.DataFrame) -> pd.DataFrame:
    if windows.empty:
        return pd.DataFrame()
    priority_weight = {
        "right_tail": 5,
        "bottom_loss": 4,
        "maxdd_context": 3,
        "low_resolution": 2,
        "ordinary": 1,
    }
    temp = windows.copy()
    temp["priority_weight"] = temp["priority_class"].map(priority_weight).fillna(1).astype(int)
    grouped = (
        temp.groupby(["exchange", "product", "vt_symbol", "request_date"], dropna=False)
        .agg(
            request_start_ts=("window_start_ts", "min"),
            request_end_ts=("window_end_ts", "max"),
            required_window_count=("window_id", "count"),
            estimated_required_1m_bars=("estimated_required_1m_bars", "sum"),
            right_tail_window_count=("right_tail_visual", "sum"),
            bottom_loss_window_count=("bottom_loss_visual", "sum"),
            maxdd_window_count=("maxdd_context", "sum"),
            low_resolution_window_count=("low_resolution_zone", "sum"),
            missing_event_time_window_count=("event_time_missing", "sum"),
            priority_score=("priority_weight", "sum"),
        )
        .reset_index()
        .sort_values(["priority_score", "required_window_count", "exchange", "product", "vt_symbol"], ascending=[False, False, True, True, True])
        .reset_index(drop=True)
    )
    records: list[dict[str, Any]] = []
    for i, row in grouped.iterrows():
        request_no = i + 1
        date_compact = str(row["request_date"]).replace("-", "")
        symbol_slug = str(row["vt_symbol"]).replace(".", "_")
        request_id = f"stage152_req_{request_no:04d}_{symbol_slug}_{date_compact}"
        base = f"stage152_authoritative_minute_ohlcv/{row['exchange']}/{symbol_slug}/{date_compact}/{request_id}"
        records.append(
            {
                "request_id": request_id,
                "exchange": row["exchange"],
                "product": row["product"],
                "vt_symbol": row["vt_symbol"],
                "request_date": row["request_date"],
                "request_start_ts": row["request_start_ts"],
                "request_end_ts": row["request_end_ts"],
                "required_window_count": int(row["required_window_count"]),
                "estimated_required_1m_bars": int(row["estimated_required_1m_bars"]),
                "right_tail_window_count": int(row["right_tail_window_count"]),
                "bottom_loss_window_count": int(row["bottom_loss_window_count"]),
                "maxdd_window_count": int(row["maxdd_window_count"]),
                "low_resolution_window_count": int(row["low_resolution_window_count"]),
                "missing_event_time_window_count": int(row["missing_event_time_window_count"]),
                "priority_score": int(row["priority_score"]),
                "expected_raw_file": f"incoming/{base}.raw.csv.zst",
                "expected_normalized_file": f"incoming/{base}.normalized.parquet",
                "expected_proof_file": f"incoming/{base}.proof.json",
                "raw_file_present": 0,
                "normalized_file_present": 0,
                "proof_file_present": 0,
                "request_ready": 0,
                "stage153_intake_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _operator_checklist(requests: pd.DataFrame, schema: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "step_no": 1,
                "action_id": "procure_authoritative_minute_ohlcv",
                "action": "Acquire licensed 1m OHLCV files for every request_id in the manifest template.",
                "hard_gate": 1,
                "ready_now": 0,
                "expected_count": int(len(requests)),
            },
            {
                "step_no": 2,
                "action_id": "preserve_raw_and_sha256",
                "action": "Store immutable raw files and compute SHA256 before parsing.",
                "hard_gate": 1,
                "ready_now": 0,
                "expected_count": int(len(requests)),
            },
            {
                "step_no": 3,
                "action_id": "write_vendor_proof_json",
                "action": "Attach vendor/license/query/session/no-trade policy proof JSON for each request.",
                "hard_gate": 1,
                "ready_now": 0,
                "expected_count": int(len(requests)),
            },
            {
                "step_no": 4,
                "action_id": "normalize_to_canonical_schema",
                "action": "Normalize bars to the Stage152 canonical schema without future adjustment or synthetic fills.",
                "hard_gate": 1,
                "ready_now": 0,
                "expected_count": int(schema["hard_gate"].sum()),
            },
            {
                "step_no": 5,
                "action_id": "verify_required_window_coverage",
                "action": "Check all required windows, including right-tail, bottom-loss, and maxDD context windows.",
                "hard_gate": 1,
                "ready_now": 0,
                "expected_count": int(len(windows)),
            },
            {
                "step_no": 6,
                "action_id": "only_then_run_stage153_intake",
                "action": "Run the next intake validator only after raw, proof, normalized, and coverage gates pass.",
                "hard_gate": 1,
                "ready_now": 0,
                "expected_count": 1,
            },
        ]
    )


def _coverage_gate(requests: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    request_count = int(len(requests))
    window_count = int(len(windows))
    right_tail_windows = int(windows["right_tail_visual"].sum()) if not windows.empty else 0
    bottom_loss_windows = int(windows["bottom_loss_visual"].sum()) if not windows.empty else 0
    maxdd_windows = int(windows["maxdd_context"].sum()) if not windows.empty else 0
    low_resolution_windows = int(windows["low_resolution_zone"].sum()) if not windows.empty else 0
    rows = [
        ("manifest_contract_defined", 1, 1, "contract", "Stage152 contract exists."),
        ("required_windows_materialized", window_count, window_count, "contract", "All Stage102 contexts have fixed data windows."),
        ("request_templates_materialized", request_count, request_count, "contract", "Vendor request templates exist."),
        ("raw_authoritative_files_present", 0, request_count, "data_hard", "No licensed raw data is present yet."),
        ("proof_files_present", 0, request_count, "data_hard", "No vendor proof JSON is present yet."),
        ("normalized_files_present", 0, request_count, "data_hard", "No normalized canonical bars are present yet."),
        ("all_required_windows_covered", 0, window_count, "coverage_hard", "No window coverage has been verified yet."),
        ("right_tail_windows_covered", 0, right_tail_windows, "coverage_hard", "Right-tail windows must be covered before any rule."),
        ("bottom_loss_windows_covered", 0, bottom_loss_windows, "coverage_hard", "Bottom-loss windows must be covered before any rule."),
        ("maxdd_windows_covered", 0, maxdd_windows, "coverage_hard", "MaxDD-context windows must be covered before any rule."),
        ("low_resolution_windows_covered", 0, low_resolution_windows, "coverage_hard", "Low-resolution windows must be covered before any rule."),
        ("sequence_gap_verified", 0, request_count, "quality_hard", "Sequence gaps are unknown until real data arrives."),
        ("real_volume_not_proxy_verified", 0, request_count, "quality_hard", "Volume must be real traded volume, not replay proxy."),
        ("no_internal_replay_fallback", 1, 1, "anti_overfit_hard", "Internal replay labels are forbidden as source fields."),
        ("strategy_rule_created", 0, 0, "strategy_hard", "This stage must create no trading rule."),
        ("true_engine_run", 0, 0, "strategy_hard", "This stage must not run true engine."),
        ("order_api_called", 0, 0, "execution_hard", "This stage has no live or simulated order side effect."),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": observed,
                "required": required,
                "pass_now": int(observed == required),
                "severity": severity,
                "interpretation": interpretation,
            }
            for gate_id, observed, required, severity, interpretation in rows
        ]
    )


def _gate_status(coverage_gate: pd.DataFrame, summary_dict: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("manifest_contract_ready", int(summary_dict["manifest_contract_ready"]), 1, "data_contract_hard"),
        ("stage151_route_followed", int(summary_dict["selected_next_route"] == "authoritative_minute_ohlcv_volume"), 1, "route_hard"),
        ("required_window_contract_ready", int(summary_dict["required_window_count"]), int(summary_dict["stage102_context_order_count"] * len(WINDOW_SPECS)), "coverage_contract_hard"),
        ("request_manifest_ready", int(summary_dict["request_template_count"] > 0), 1, "data_contract_hard"),
        ("data_gate_all_passed", int(coverage_gate["pass_now"].min()), 1, "data_hard"),
        ("stage153_intake_allowed", int(summary_dict["stage153_intake_allowed"]), 0, "intake_hard"),
        ("strategy_rule_created", int(summary_dict["strategy_rule_created"]), 0, "strategy_hard"),
        ("true_engine_run", int(summary_dict["true_engine_run"]), 0, "strategy_hard"),
        ("side_effect_count", int(summary_dict["side_effect_count"]), 0, "execution_hard"),
    ]
    records = []
    for gate_id, observed, required, severity in rows:
        if gate_id == "required_window_contract_ready":
            pass_now = int(observed == required)
        else:
            pass_now = int(observed == required)
        records.append(
            {
                "gate_id": gate_id,
                "observed": observed,
                "required": required,
                "pass_now": pass_now,
                "severity": severity,
            }
        )
    return pd.DataFrame(records)


def _write_report(
    summary: pd.DataFrame,
    schema: pd.DataFrame,
    windows: pd.DataFrame,
    requests: pd.DataFrame,
    coverage_gate: pd.DataFrame,
    checklist: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    request_sample_cols = [
        "request_id",
        "exchange",
        "product",
        "vt_symbol",
        "request_date",
        "required_window_count",
        "priority_score",
        "request_ready",
    ]
    window_sample_cols = [
        "window_id",
        "vt_symbol",
        "window_type",
        "window_start_ts",
        "window_end_ts",
        "priority_class",
        "must_cover",
        "data_ready_now",
    ]
    lines = [
        f"# {STAGE} 权威分钟 OHLCV 清单和覆盖闸门",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只生成点时化数据合同和可视化闸门，不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- Databento 的 OHLCV 与 Historical API 文档、CME DataMine、IBKR historical bars、FirstRateData 等资料共同说明：期货分钟 OHLCV/volume 可以由授权历史数据源取得，但必须保留 raw 文件、query 参数、schema/hash、license、timestamp convention 与 no-trade bar policy。",
        "- 关键判断：供应商有可能只返回有成交的分钟 bar，因此序列缺口必须被显式标注，不能把无成交间隔误读成缺失 alpha，也不能用本地 Stage102/150 回放标签补量能或补时间。",
        "- 对本线目标的含义：在真实、可授权、点时化分钟 OHLCV 到货前，只允许推进数据契约；任何从当前回放事件族直接抽规则的做法都属于过拟合风险。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Field Schema",
        "",
        _md_table(schema),
        "",
        "## Required Window Contract Sample",
        "",
        _md_table(windows[window_sample_cols], max_rows=20),
        "",
        "## Request Manifest Template Sample",
        "",
        _md_table(requests[request_sample_cols], max_rows=20),
        "",
        "## Coverage Gate",
        "",
        _md_table(coverage_gate),
        "",
        "## Operator Intake Checklist",
        "",
        _md_table(checklist),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{FIELD_CHART_OUT.name}`",
        f"- `{WINDOW_CHART_OUT.name}`",
        f"- `{REQUEST_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage152 authoritative 1m OHLCV manifest status on official path", fontsize=14, fontweight="bold")
    x = curve["date"].to_numpy()
    axes[0].plot(x, curve["account_equity"].to_numpy() / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(x, curve["drawdown_pct"].to_numpy(), 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(x, curve["broker10_margin_to_equity_pct"].to_numpy(), color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["windows", "requests", "raw_ready", "coverage", "rule", "engine"]
    values = [
        row["required_window_count"],
        row["request_template_count"],
        row["data_file_present_count"],
        row["coverage_ready_window_count"],
        row["strategy_rule_created"],
        row["true_engine_run"],
    ]
    colors = ["#0F766E", "#3657D6", "#B91C1C", "#B91C1C", "#111827", "#111827"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("Contract generated; real data still absent, so no strategy candidate")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_matrix(frame: pd.DataFrame, index_col: str, value_cols: list[str], title: str, path: Path) -> None:
    matrix = frame.set_index(index_col)[value_cols].copy()
    for column in value_cols:
        matrix[column] = pd.to_numeric(matrix[column], errors="coerce").fillna(0).clip(lower=0, upper=1)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.45), max(5.0, len(matrix) * 0.42)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(value_cols)))
    ax.set_xticklabels(value_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=7)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _plot_window_heatmap(windows: pd.DataFrame) -> None:
    priority_order = ["right_tail", "bottom_loss", "maxdd_context", "low_resolution", "ordinary"]
    matrix = pd.crosstab(windows["window_type"], windows["priority_class"]).reindex(columns=priority_order, fill_value=0)
    fig, ax = plt.subplots(figsize=(12, 5.6))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="YlGnBu")
    ax.set_title("Required 1m OHLCV windows by purpose and priority class")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(WINDOW_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_request_chart(requests: pd.DataFrame) -> None:
    data = (
        requests.groupby("product", dropna=False)
        .agg(request_count=("request_id", "count"), window_count=("required_window_count", "sum"), priority_score=("priority_score", "sum"))
        .reset_index()
        .sort_values(["priority_score", "window_count"], ascending=False)
        .head(18)
        .sort_values("priority_score", ascending=True)
    )
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(data["product"], data["priority_score"], color="#0F766E", alpha=0.85)
    ax.set_title("Top Stage152 minute OHLCV request groups by priority score")
    ax.set_xlabel("priority score")
    ax.grid(axis="x", alpha=0.25)
    for bar, (_, row) in zip(bars, data.iterrows(), strict=False):
        ax.text(
            bar.get_width() + 0.2,
            bar.get_y() + bar.get_height() / 2,
            f"req={int(row['request_count'])}, win={int(row['window_count'])}",
            va="center",
            fontsize=8,
        )
    fig.tight_layout()
    fig.savefig(REQUEST_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    curve = _load_curve()
    rows102 = _prepare_stage102_rows(_read_csv(STAGE102_ROWS_IN))
    stage151 = _row(STAGE151_SUMMARY_IN)
    if not stage151:
        raise RuntimeError(f"missing Stage151 summary input: {STAGE151_SUMMARY_IN}")
    stage151_requirements = _read_csv(STAGE151_REQUIREMENTS_IN)

    schema = _field_schema(stage151_requirements)
    windows = _build_required_windows(rows102)
    requests = _build_request_template(windows)
    checklist = _operator_checklist(requests, schema, windows)
    coverage_gate = _coverage_gate(requests, windows)
    coverage_pass_count = int(coverage_gate["pass_now"].sum())
    coverage_gate_count = int(len(coverage_gate))

    decision = "stage152_authoritative_minute_ohlcv_manifest_ready_no_data_no_rule"
    summary_dict: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "stage153_authoritative_minute_ohlcv_intake_validator_after_real_data",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "selected_next_route": stage151.get("selected_next_route", ""),
        "manifest_contract_ready": 1,
        "stage151_manifest_requirement_count": int(len(stage151_requirements)),
        "field_schema_count": int(len(schema)),
        "hard_field_count": int(schema["hard_gate"].sum()),
        "stage102_context_order_count": int(len(rows102)),
        "required_window_count": int(len(windows)),
        "request_template_count": int(len(requests)),
        "unique_vt_symbol_count": int(rows102["vt_symbol"].nunique()),
        "unique_product_count": int(rows102["product"].nunique()),
        "unique_exchange_count": int(rows102["exchange"].nunique()),
        "unique_request_day_count": int(requests["request_date"].nunique()) if not requests.empty else 0,
        "right_tail_context_order_count": int(rows102["right_tail_visual"].sum()),
        "bottom_loss_context_order_count": int(rows102["bottom_loss_visual"].sum()),
        "maxdd_context_order_count": int(rows102["maxdd_context"].sum()),
        "low_resolution_context_order_count": int(rows102["low_resolution_zone"].sum()),
        "event_time_missing_context_order_count": int(rows102["event_time_missing"].sum()),
        "right_tail_required_window_count": int(windows["right_tail_visual"].sum()),
        "bottom_loss_required_window_count": int(windows["bottom_loss_visual"].sum()),
        "maxdd_required_window_count": int(windows["maxdd_context"].sum()),
        "low_resolution_required_window_count": int(windows["low_resolution_zone"].sum()),
        "missing_event_time_required_window_count": int(windows["event_time_missing"].sum()),
        "estimated_required_1m_bar_count": int(windows["estimated_required_1m_bars"].sum()),
        "max_window_duration_minutes": float(windows["duration_minutes"].max()) if not windows.empty else 0.0,
        "data_file_present_count": 0,
        "normalized_file_present_count": 0,
        "proof_file_present_count": 0,
        "coverage_ready_window_count": 0,
        "request_ready_count": 0,
        "coverage_gate_pass_count": coverage_pass_count,
        "coverage_gate_count": coverage_gate_count,
        "stage153_intake_allowed": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage151.get("end_equity", np.nan)),
        "total_return_pct": float(stage151.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage151.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage151.get("sharpe", np.nan)),
        "total_slippage": float(stage151.get("total_slippage", np.nan)),
        "total_trade_count": float(stage151.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage151.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage151.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(coverage_gate, summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(schema, FIELD_SCHEMA_OUT)
    _write_csv(windows, WINDOW_CONTRACT_OUT)
    _write_csv(requests, REQUEST_TEMPLATE_OUT)
    _write_csv(coverage_gate, COVERAGE_GATE_OUT)
    _write_csv(checklist, OPERATOR_CHECKLIST_OUT)
    _write_csv(gate, GATE_OUT)

    _write_report(summary, schema, windows, requests, coverage_gate, checklist, gate)
    _plot_path(curve, summary)
    _plot_matrix(
        schema,
        "field",
        ["required_for_stage152_manifest", "hard_gate", "also_required_by_stage151", "contract_defined", "current_ready"],
        "Stage152 canonical field schema readiness",
        FIELD_CHART_OUT,
    )
    _plot_window_heatmap(windows)
    _plot_request_chart(requests)
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage152 gate status", GATE_CHART_OUT)

    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "curve": str(CURVE_IN),
                "stage102_rows": str(STAGE102_ROWS_IN),
                "stage151_summary": str(STAGE151_SUMMARY_IN),
                "stage151_manifest_requirements": str(STAGE151_REQUIREMENTS_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "field_schema": str(FIELD_SCHEMA_OUT),
                "required_window_contract": str(WINDOW_CONTRACT_OUT),
                "request_manifest_template": str(REQUEST_TEMPLATE_OUT),
                "coverage_gate": str(COVERAGE_GATE_OUT),
                "operator_intake_checklist": str(OPERATOR_CHECKLIST_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(FIELD_CHART_OUT),
                    str(WINDOW_CHART_OUT),
                    str(REQUEST_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "external_research_sources": [
                "https://databento.com/docs/schemas-and-data-formats/ohlcv",
                "https://databento.com/docs/api-reference-historical/client/historical",
                "https://www.cmegroup.com/datamine.html",
                "https://interactivebrokers.github.io/tws-api/historical_bars.html",
                "https://firstratedata.com/",
            ],
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "current_package_promotion_allowed": 0,
                "strategy_feature_usable": 0,
                "stage153_intake_allowed": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

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
STAGE = "Stage177"
MODEL_TAG = "stage177_predecision_lookback_extension_manifest_v1"
OUTPUT_PREFIX = "qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest"

TARGET_MIN_PREDECISION_CLOSED_BARS = 61
UNIVERSAL_LOOKBACK_CALENDAR_DAYS = 14

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage177_predecision_lookback_extension_manifest"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE152_DIR = LINE_DIR / "outputs" / "stage152_authoritative_minute_ohlcv_manifest"
STAGE152_PREFIX = "qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest"
STAGE152_TAG = "stage152_authoritative_minute_ohlcv_manifest_v1"
STAGE152_WINDOWS_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_required_window_contract_{STAGE152_TAG}.csv"

STAGE176_DIR = LINE_DIR / "outputs" / "stage176_point_in_time_feature_materialization_gate"
STAGE176_PREFIX = "qmt_roll_stage176_c9_minrisk_point_in_time_feature_materialization_gate"
STAGE176_TAG = "stage176_point_in_time_feature_materialization_gate_v1"
STAGE176_SUMMARY_IN = STAGE176_DIR / f"{STAGE176_PREFIX}_summary_{STAGE176_TAG}.csv"
STAGE176_AUDIT_IN = STAGE176_DIR / f"{STAGE176_PREFIX}_window_decision_materialization_audit_{STAGE176_TAG}.csv"
STAGE176_REQUIREMENTS_IN = STAGE176_DIR / f"{STAGE176_PREFIX}_feature_lookback_requirement_{STAGE176_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
LOOKBACK_POLICY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lookback_policy_{MODEL_TAG}.csv"
EXTENSION_WINDOWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extension_window_contract_{MODEL_TAG}.csv"
REQUEST_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_manifest_{MODEL_TAG}.csv"
SHORTFALL_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_current_shortfall_audit_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_manifest_status_{MODEL_TAG}.png"
SHORTFALL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predecision_shortfall_distribution_{MODEL_TAG}.png"
REQUEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_manifest_load_{MODEL_TAG}.png"
DURATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lookback_duration_by_priority_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"


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


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        number = float(row.get(key, default))
    except (TypeError, ValueError):
        return default
    return default if np.isnan(number) or np.isinf(number) else number


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(_num(row, key, float(default))))


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _resolve_path(text: Any) -> Path:
    path = Path(str(text))
    return path if path.is_absolute() else REPO_DIR / path


def _lookback_policy(requirements: pd.DataFrame) -> pd.DataFrame:
    max_requirement = int(
        pd.to_numeric(requirements.get("min_predecision_closed_bars", pd.Series(dtype=float)), errors="coerce")
        .fillna(0)
        .max()
    )
    return pd.DataFrame(
        [
            {
                "policy_id": "target_min_predecision_closed_bars",
                "value": TARGET_MIN_PREDECISION_CLOSED_BARS,
                "source": "Stage176 max Stage156 feature lookback requirement",
                "pass_now": int(TARGET_MIN_PREDECISION_CLOSED_BARS >= max_requirement),
                "trade_rule_allowed": 0,
            },
            {
                "policy_id": "universal_calendar_lookback_days",
                "value": UNIVERSAL_LOOKBACK_CALENDAR_DAYS,
                "source": "fixed predeclared cushion for weekend and holiday session breaks",
                "pass_now": 1,
                "trade_rule_allowed": 0,
            },
            {
                "policy_id": "feature_cutoff_rule",
                "value": "bar_end_ts <= decision_ts",
                "source": "point-in-time closed-bar materialization rule",
                "pass_now": 1,
                "trade_rule_allowed": 0,
            },
            {
                "policy_id": "no_synthetic_fill_for_session_gaps",
                "value": "preserve no-trade intervals; validator blocks if delivered bars still < target",
                "source": "Stage152/153 no-trade proof discipline",
                "pass_now": 1,
                "trade_rule_allowed": 0,
            },
            {
                "policy_id": "no_tail_product_year_specific_lookback",
                "value": "one lookback for all products, years, directions, and priority classes",
                "source": "anti-overfit guard",
                "pass_now": 1,
                "trade_rule_allowed": 0,
            },
        ]
    )


def _stage152_entry_meta(windows152: pd.DataFrame) -> pd.DataFrame:
    if windows152.empty:
        raise RuntimeError(f"missing Stage152 window contract: {STAGE152_WINDOWS_IN}")
    entry = windows152[windows152["window_type"].astype(str).eq("entry_pre30_post120")].copy()
    keep = [
        "window_id",
        "candidate_index",
        "official_open_trade_id",
        "direction",
        "official_open_date",
        "anchor_scan_start",
        "anchor_event_time",
        "anchor_event_time_source",
        "right_tail_visual",
        "bottom_loss_visual",
        "maxdd_context",
        "low_resolution_zone",
        "event_time_missing",
        "resolution_bucket",
    ]
    for column in keep:
        if column not in entry.columns:
            entry[column] = ""
    return entry[keep]


def _build_extension_windows(audit176: pd.DataFrame, windows152: pd.DataFrame) -> pd.DataFrame:
    if audit176.empty:
        raise RuntimeError(f"missing Stage176 materialization audit: {STAGE176_AUDIT_IN}")
    entry = audit176[audit176["entry_candidate_context"].eq(1)].copy()
    if entry.empty:
        raise RuntimeError("Stage176 audit has no entry candidate context rows")
    meta = _stage152_entry_meta(windows152)
    entry = entry.merge(meta, on="window_id", how="left", validate="one_to_one")
    entry["decision_ts"] = pd.to_datetime(entry["decision_ts"], errors="coerce")
    if entry["decision_ts"].isna().any():
        raise RuntimeError("entry decision_ts contains unparsable timestamps")
    entry["current_closed_bar_count_before_decision"] = pd.to_numeric(
        entry["closed_bar_count_before_decision"], errors="coerce"
    ).fillna(0).astype(int)
    entry["additional_closed_bars_needed"] = (
        TARGET_MIN_PREDECISION_CLOSED_BARS - entry["current_closed_bar_count_before_decision"]
    ).clip(lower=0)
    entry["extension_start_ts"] = entry["decision_ts"] - pd.Timedelta(days=UNIVERSAL_LOOKBACK_CALENDAR_DAYS)
    entry["extension_end_ts"] = entry["decision_ts"]
    entry["extension_duration_calendar_minutes"] = (
        (entry["extension_end_ts"] - entry["extension_start_ts"]).dt.total_seconds() / 60.0
    )
    entry["estimated_calendar_1m_slots"] = np.ceil(entry["extension_duration_calendar_minutes"]).astype(int) + 1
    records: list[dict[str, Any]] = []
    for _, row in entry.sort_values(["decision_ts", "exchange", "vt_symbol", "window_id"]).iterrows():
        candidate_index = int(row["candidate_index"]) if pd.notna(row.get("candidate_index")) else -1
        records.append(
            {
                "extension_window_id": f"stage177_{candidate_index:04d}_predecision_14d_lookback",
                "source_stage152_window_id": row["window_id"],
                "source_stage152_request_id": row["request_id"],
                "candidate_index": candidate_index,
                "official_open_trade_id": row.get("official_open_trade_id", ""),
                "vt_symbol": row["vt_symbol"],
                "exchange": row["exchange"],
                "product": row["product"],
                "direction": row.get("direction", ""),
                "official_open_date": row.get("official_open_date", ""),
                "priority_class": row["priority_class"],
                "right_tail_visual": int(row.get("right_tail_visual", 0)),
                "bottom_loss_visual": int(row.get("bottom_loss_visual", 0)),
                "maxdd_context": int(row.get("maxdd_context", 0)),
                "low_resolution_zone": int(row.get("low_resolution_zone", 0)),
                "event_time_missing": int(row.get("event_time_missing", 0)),
                "resolution_bucket": row.get("resolution_bucket", ""),
                "anchor_scan_start": row.get("anchor_scan_start", ""),
                "anchor_event_time": row.get("anchor_event_time", ""),
                "anchor_event_time_source": row.get("anchor_event_time_source", ""),
                "decision_ts": row["decision_ts"].strftime("%Y-%m-%d %H:%M:%S"),
                "decision_ts_rule": row["decision_ts_rule"],
                "extension_start_ts": row["extension_start_ts"].strftime("%Y-%m-%d %H:%M:%S"),
                "extension_end_ts": row["extension_end_ts"].strftime("%Y-%m-%d %H:%M:%S"),
                "target_min_predecision_closed_bars": TARGET_MIN_PREDECISION_CLOSED_BARS,
                "current_closed_bar_count_before_decision": int(row["current_closed_bar_count_before_decision"]),
                "additional_closed_bars_needed": int(row["additional_closed_bars_needed"]),
                "current_core_30m_ready": int(row["core_30m_features_ready"]),
                "current_full_60m_ready": int(row["full_60m_contract_features_ready"]),
                "extension_duration_calendar_minutes": float(row["extension_duration_calendar_minutes"]),
                "estimated_calendar_1m_slots": int(row["estimated_calendar_1m_slots"]),
                "feature_cutoff_rule": "bar_end_ts <= decision_ts",
                "allow_post_decision_bar": 0,
                "synthetic_fill_allowed": 0,
                "delivery_ready": 0,
                "feature_table_row_allowed_now": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _build_request_manifest(extension_windows: pd.DataFrame) -> pd.DataFrame:
    if extension_windows.empty:
        return pd.DataFrame()
    priority_weight = {
        "right_tail": 5,
        "bottom_loss": 4,
        "maxdd_context": 3,
        "low_resolution": 2,
        "ordinary": 1,
    }
    temp = extension_windows.copy()
    temp["decision_date"] = pd.to_datetime(temp["decision_ts"], errors="coerce").dt.strftime("%Y-%m-%d")
    temp["priority_weight"] = temp["priority_class"].map(priority_weight).fillna(1).astype(int)
    grouped = (
        temp.groupby(["exchange", "product", "vt_symbol", "decision_date"], dropna=False)
        .agg(
            request_start_ts=("extension_start_ts", "min"),
            request_end_ts=("extension_end_ts", "max"),
            extension_window_count=("extension_window_id", "count"),
            target_entry_decision_count=("decision_ts", "count"),
            target_min_predecision_closed_bars=("target_min_predecision_closed_bars", "max"),
            current_closed_bar_count_sum=("current_closed_bar_count_before_decision", "sum"),
            additional_closed_bars_needed_sum=("additional_closed_bars_needed", "sum"),
            estimated_calendar_1m_slots=("estimated_calendar_1m_slots", "sum"),
            right_tail_window_count=("right_tail_visual", "sum"),
            bottom_loss_window_count=("bottom_loss_visual", "sum"),
            maxdd_window_count=("maxdd_context", "sum"),
            low_resolution_window_count=("low_resolution_zone", "sum"),
            priority_score=("priority_weight", "sum"),
            extension_window_ids=("extension_window_id", lambda values: ";".join(map(str, values))),
        )
        .reset_index()
        .sort_values(
            ["priority_score", "extension_window_count", "exchange", "product", "vt_symbol", "decision_date"],
            ascending=[False, False, True, True, True, True],
        )
        .reset_index(drop=True)
    )
    records: list[dict[str, Any]] = []
    for i, row in grouped.iterrows():
        request_no = i + 1
        date_compact = str(row["decision_date"]).replace("-", "")
        symbol_slug = str(row["vt_symbol"]).replace(".", "_")
        request_id = f"stage177_req_{request_no:04d}_{symbol_slug}_{date_compact}"
        base = f"stage177_predecision_lookback_extension/{row['exchange']}/{symbol_slug}/{date_compact}/{request_id}"
        expected_raw = f"incoming/{base}.raw.csv.zst"
        expected_normalized = f"incoming/{base}.normalized.parquet"
        expected_proof = f"incoming/{base}.proof.json"
        raw_present = int(_resolve_path(expected_raw).exists())
        normalized_present = int(_resolve_path(expected_normalized).exists())
        proof_present = int(_resolve_path(expected_proof).exists())
        records.append(
            {
                "request_id": request_id,
                "exchange": row["exchange"],
                "product": row["product"],
                "vt_symbol": row["vt_symbol"],
                "decision_date": row["decision_date"],
                "request_start_ts": row["request_start_ts"],
                "request_end_ts": row["request_end_ts"],
                "lookback_calendar_days": UNIVERSAL_LOOKBACK_CALENDAR_DAYS,
                "extension_window_count": int(row["extension_window_count"]),
                "target_entry_decision_count": int(row["target_entry_decision_count"]),
                "target_min_predecision_closed_bars": int(row["target_min_predecision_closed_bars"]),
                "current_closed_bar_count_sum": int(row["current_closed_bar_count_sum"]),
                "additional_closed_bars_needed_sum": int(row["additional_closed_bars_needed_sum"]),
                "estimated_calendar_1m_slots": int(row["estimated_calendar_1m_slots"]),
                "right_tail_window_count": int(row["right_tail_window_count"]),
                "bottom_loss_window_count": int(row["bottom_loss_window_count"]),
                "maxdd_window_count": int(row["maxdd_window_count"]),
                "low_resolution_window_count": int(row["low_resolution_window_count"]),
                "priority_score": int(row["priority_score"]),
                "extension_window_ids": row["extension_window_ids"],
                "expected_raw_file": expected_raw,
                "expected_normalized_file": expected_normalized,
                "expected_proof_file": expected_proof,
                "raw_file_present": raw_present,
                "normalized_file_present": normalized_present,
                "proof_file_present": proof_present,
                "request_ready": int(raw_present == 1 and normalized_present == 1 and proof_present == 1),
                "delivery_step_allowed_after_manifest": 1,
                "stage179_point_in_time_validator_required": 1,
                "feature_table_write_allowed": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _shortfall_audit(extension_windows: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        extension_windows.groupby(["exchange", "priority_class"], dropna=False)
        .agg(
            entry_window_count=("extension_window_id", "count"),
            min_current_closed_bars=("current_closed_bar_count_before_decision", "min"),
            median_current_closed_bars=("current_closed_bar_count_before_decision", "median"),
            max_current_closed_bars=("current_closed_bar_count_before_decision", "max"),
            total_additional_closed_bars_needed=("additional_closed_bars_needed", "sum"),
            current_core_30m_ready_count=("current_core_30m_ready", "sum"),
            current_full_60m_ready_count=("current_full_60m_ready", "sum"),
        )
        .reset_index()
    )
    grouped["target_min_predecision_closed_bars"] = TARGET_MIN_PREDECISION_CLOSED_BARS
    grouped["strategy_rule_allowed"] = 0
    return grouped


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage176_loaded", summary["stage176_entry_window_count"], summary["entry_window_count"], "dependency_hard"),
        ("all_entry_windows_in_extension_manifest", summary["extension_required_window_count"], summary["entry_window_count"], "manifest_hard"),
        ("request_manifest_ready", summary["extension_request_count"], summary["extension_request_count"], "manifest_hard"),
        ("target_closed_bars_declared", summary["target_min_predecision_closed_bars"], TARGET_MIN_PREDECISION_CLOSED_BARS, "point_in_time_hard"),
        ("universal_lookback_days_declared", summary["universal_lookback_calendar_days"], UNIVERSAL_LOOKBACK_CALENDAR_DAYS, "anti_overfit_hard"),
        ("entry_60m_ready_before_extension", summary["stage176_entry_full_60m_ready_count"], summary["entry_window_count"], "known_blocker"),
        ("extension_raw_files_present", summary["extension_raw_file_present_count"], summary["extension_request_count"], "data_hard"),
        ("extension_normalized_files_present", summary["extension_normalized_file_present_count"], summary["extension_request_count"], "data_hard"),
        ("extension_proof_files_present", summary["extension_proof_file_present_count"], summary["extension_request_count"], "data_hard"),
        ("feature_table_row_written", summary["feature_table_row_written_count"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "execution_hard"),
        ("official_config_changed", summary["official_config_changed"], 0, "execution_hard"),
    ]
    records = []
    for gate_id, observed, required, severity in rows:
        records.append(
            {
                "gate_id": gate_id,
                "observed": int(observed),
                "required": int(required),
                "pass_now": int(int(observed) == int(required)),
                "severity": severity,
            }
        )
    return pd.DataFrame(records)


def _write_report(
    summary: pd.DataFrame,
    policy: pd.DataFrame,
    extension_windows: pd.DataFrame,
    requests: pd.DataFrame,
    shortfall: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    summary_row = summary.iloc[0]
    window_cols = [
        "extension_window_id",
        "source_stage152_window_id",
        "vt_symbol",
        "priority_class",
        "decision_ts",
        "extension_start_ts",
        "target_min_predecision_closed_bars",
        "current_closed_bar_count_before_decision",
        "additional_closed_bars_needed",
        "strategy_rule_allowed",
    ]
    request_cols = [
        "request_id",
        "exchange",
        "product",
        "vt_symbol",
        "decision_date",
        "request_start_ts",
        "request_end_ts",
        "extension_window_count",
        "additional_closed_bars_needed_sum",
        "request_ready",
    ]
    lines = [
        "# Stage177 predecision lookback extension manifest",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary_row['decision']}`",
        "- 本阶段只生成入场决策前 lookback 扩展合同、请求清单和视觉闸门；不写 feature table、不创建策略规则、不运行 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- pandas rolling 文档说明滚动窗口的边界由 `closed` 控制，user guide 明确左侧窗口可以用于避免当前信息污染过去信息；本阶段因此把特征材料化固定为 `bar_end_ts <= decision_ts`。",
        "- vn.py 的 `TickData`/`BarData` 字段包含 datetime、volume、turnover、open_interest 与 OHLC，适合继续沿原 proofed tick-to-minute 合同扩展，而不是换一套语义。",
        "- 金融回测过拟合研究强调要防止时间泄漏和 OOS 假象；本阶段只修点时化数据可见性，不根据收益、年份、品种、方向或尾部标签改变 lookback。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Lookback Policy",
        "",
        _md_table(policy),
        "",
        "## Current Shortfall",
        "",
        _md_table(shortfall),
        "",
        "## Extension Window Contract Sample",
        "",
        _md_table(extension_windows[window_cols], max_rows=30),
        "",
        "## Request Manifest Sample",
        "",
        _md_table(requests[request_cols], max_rows=30),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{SHORTFALL_CHART_OUT.name}`",
        f"- `{REQUEST_CHART_OUT.name}`",
        f"- `{DURATION_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_title("Official path unchanged; Stage177 builds predecision lookback manifest")
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["entry windows", "extension windows", "requests", "60m ready", "rows written"]
    values = [
        summary["entry_window_count"],
        summary["extension_required_window_count"],
        summary["extension_request_count"],
        summary["stage176_entry_full_60m_ready_count"],
        summary["feature_table_row_written_count"],
    ]
    axes[3].bar(labels, values, color=["#0F766E", "#3657D6", "#92400E", "#991B1B", "#111827"])
    axes[3].set_ylabel("count")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_shortfall(extension_windows: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.8))
    axes[0].hist(
        extension_windows["current_closed_bar_count_before_decision"],
        bins=range(0, TARGET_MIN_PREDECISION_CLOSED_BARS + 6, 5),
        color="#3657D6",
        alpha=0.82,
    )
    axes[0].axvline(31, color="#B45309", linestyle="--", linewidth=1.0, label="30m core minimum")
    axes[0].axvline(61, color="#991B1B", linestyle="--", linewidth=1.0, label="60m contract minimum")
    axes[0].set_title("Current closed bars before entry decision")
    axes[0].set_xlabel("closed 1m bars")
    axes[0].set_ylabel("entry windows")
    axes[0].legend()
    data = [
        extension_windows.loc[extension_windows["exchange"].eq(exchange), "additional_closed_bars_needed"].to_numpy()
        for exchange in sorted(extension_windows["exchange"].dropna().unique())
    ]
    labels = sorted(extension_windows["exchange"].dropna().unique())
    axes[1].boxplot(data, tick_labels=labels, showfliers=False)
    axes[1].set_title("Additional closed bars needed by exchange")
    axes[1].set_ylabel("bars")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(SHORTFALL_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_request_load(requests: pd.DataFrame) -> None:
    grouped = (
        requests.groupby("exchange")
        .agg(
            request_count=("request_id", "count"),
            extension_window_count=("extension_window_count", "sum"),
            additional_bars_needed=("additional_closed_bars_needed_sum", "sum"),
        )
        .sort_index()
    )
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))
    x = np.arange(len(grouped.index))
    width = 0.35
    axes[0].bar(x - width / 2, grouped["request_count"], width=width, label="requests", color="#0F766E")
    axes[0].bar(x + width / 2, grouped["extension_window_count"], width=width, label="entry windows", color="#3657D6")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(grouped.index)
    axes[0].set_title("Stage177 manifest load by exchange")
    axes[0].legend()
    axes[1].bar(grouped.index, grouped["additional_bars_needed"], color="#92400E")
    axes[1].set_title("Total additional closed bars needed")
    axes[1].set_ylabel("bars")
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(REQUEST_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_duration(extension_windows: pd.DataFrame) -> None:
    grouped = (
        extension_windows.groupby(["priority_class", "exchange"], dropna=False)
        .agg(
            window_count=("extension_window_id", "count"),
            median_slots=("estimated_calendar_1m_slots", "median"),
        )
        .reset_index()
    )
    pivot = grouped.pivot_table(index="priority_class", columns="exchange", values="window_count", fill_value=0)
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8))
    bottom = np.zeros(len(pivot.index))
    palette = ["#3657D6", "#0F766E", "#B45309", "#991B1B", "#4B5563"]
    for idx, column in enumerate(pivot.columns):
        values = pivot[column].to_numpy()
        axes[0].bar(pivot.index, values, bottom=bottom, label=column, color=palette[idx % len(palette)])
        bottom += values
    axes[0].set_title("Extension windows by priority and exchange")
    axes[0].set_ylabel("entry windows")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].legend()
    duration = extension_windows.groupby("priority_class")["extension_duration_calendar_minutes"].median().sort_index()
    axes[1].bar(duration.index, duration.to_numpy() / 60.0, color="#0F766E")
    axes[1].set_title("Universal calendar lookback duration")
    axes[1].set_ylabel("hours")
    axes[1].tick_params(axis="x", rotation=20)
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(DURATION_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.5, max(5.5, len(gate) * 0.44)))
    matrix = gate.set_index("gate_id")[["pass_now"]]
    data = matrix.to_numpy(dtype=float)
    ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage177 gate status")
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for r in range(data.shape[0]):
        ax.text(0, r, int(data[r, 0]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curve = _load_curve()
    stage176 = _row(STAGE176_SUMMARY_IN)
    audit176 = _read_csv(STAGE176_AUDIT_IN)
    requirements = _read_csv(STAGE176_REQUIREMENTS_IN)
    windows152 = _read_csv(STAGE152_WINDOWS_IN)
    if not stage176 or audit176.empty or requirements.empty or windows152.empty:
        raise RuntimeError("missing Stage176/Stage152 inputs for Stage177")

    policy = _lookback_policy(requirements)
    extension_windows = _build_extension_windows(audit176, windows152)
    requests = _build_request_manifest(extension_windows)
    shortfall = _shortfall_audit(extension_windows)

    entry_window_count = int(len(extension_windows))
    raw_present_count = int(requests["raw_file_present"].sum()) if not requests.empty else 0
    normalized_present_count = int(requests["normalized_file_present"].sum()) if not requests.empty else 0
    proof_present_count = int(requests["proof_file_present"].sum()) if not requests.empty else 0
    request_ready_count = int(requests["request_ready"].sum()) if not requests.empty else 0
    decision = "stage177_predecision_lookback_extension_manifest_ready_wait_delivery_no_rule"
    summary_dict = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "stage178_deliver_predecision_lookback_requests_then_stage179_point_in_time_validator_before_feature_table",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage176_entry_window_count": _int(stage176, "entry_window_count"),
        "stage176_entry_one_min_ready_count": _int(stage176, "entry_one_min_ready_count"),
        "stage176_entry_core_30m_ready_count": _int(stage176, "entry_core_30m_ready_count"),
        "stage176_entry_full_60m_ready_count": _int(stage176, "entry_full_60m_ready_count"),
        "stage176_entry_feature_row_allowed_count": _int(stage176, "entry_feature_row_allowed_count"),
        "entry_window_count": entry_window_count,
        "entry_shortfall_window_count": int(extension_windows["additional_closed_bars_needed"].gt(0).sum()),
        "target_min_predecision_closed_bars": TARGET_MIN_PREDECISION_CLOSED_BARS,
        "universal_lookback_calendar_days": UNIVERSAL_LOOKBACK_CALENDAR_DAYS,
        "extension_required_window_count": entry_window_count,
        "extension_request_count": int(len(requests)),
        "extension_raw_file_present_count": raw_present_count,
        "extension_normalized_file_present_count": normalized_present_count,
        "extension_proof_file_present_count": proof_present_count,
        "extension_request_ready_count": request_ready_count,
        "extension_expected_file_count": int(len(requests) * 3),
        "total_additional_closed_bars_needed": int(extension_windows["additional_closed_bars_needed"].sum()),
        "min_current_closed_bars": int(extension_windows["current_closed_bar_count_before_decision"].min()),
        "median_current_closed_bars": float(extension_windows["current_closed_bar_count_before_decision"].median()),
        "max_current_closed_bars": int(extension_windows["current_closed_bar_count_before_decision"].max()),
        "estimated_calendar_1m_slot_upper_bound": int(requests["estimated_calendar_1m_slots"].sum()) if not requests.empty else 0,
        "delivery_step_allowed_after_manifest": 1,
        "stage179_point_in_time_validator_required": 1,
        "feature_table_row_written_count": 0,
        "feature_table_file_written": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage176.get("end_equity", np.nan)),
        "total_return_pct": float(stage176.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage176.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage176.get("sharpe", np.nan)),
        "total_slippage": float(stage176.get("total_slippage", np.nan)),
        "total_trade_count": float(stage176.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage176.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage176.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(policy, LOOKBACK_POLICY_OUT)
    _write_csv(extension_windows, EXTENSION_WINDOWS_OUT)
    _write_csv(requests, REQUEST_MANIFEST_OUT)
    _write_csv(shortfall, SHORTFALL_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, policy, extension_windows, requests, shortfall, gate)
    _plot_path(curve, summary_dict)
    _plot_shortfall(extension_windows)
    _plot_request_load(requests)
    _plot_duration(extension_windows)
    _plot_gate(gate)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "summary": summary_dict,
            "inputs": {
                "curve": str(CURVE_IN),
                "stage152_window_contract": str(STAGE152_WINDOWS_IN),
                "stage176_summary": str(STAGE176_SUMMARY_IN),
                "stage176_window_decision_materialization_audit": str(STAGE176_AUDIT_IN),
                "stage176_feature_lookback_requirement": str(STAGE176_REQUIREMENTS_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "lookback_policy": str(LOOKBACK_POLICY_OUT),
                "extension_window_contract": str(EXTENSION_WINDOWS_OUT),
                "request_manifest": str(REQUEST_MANIFEST_OUT),
                "current_shortfall_audit": str(SHORTFALL_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(SHORTFALL_CHART_OUT),
                    str(REQUEST_CHART_OUT),
                    str(DURATION_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "external_research_sources": [
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html",
                "https://pandas.pydata.org/docs/user_guide/window.html",
                "https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py",
                "https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py",
                "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4686376",
            ],
            "locks": {
                "target_min_predecision_closed_bars": TARGET_MIN_PREDECISION_CLOSED_BARS,
                "universal_lookback_calendar_days": UNIVERSAL_LOOKBACK_CALENDAR_DAYS,
                "feature_table_row_written_count": 0,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "current_package_promotion_allowed": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary_dict), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

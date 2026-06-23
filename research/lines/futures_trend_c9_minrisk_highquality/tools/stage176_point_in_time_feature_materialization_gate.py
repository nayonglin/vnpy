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
STAGE = "Stage176"
MODEL_TAG = "stage176_point_in_time_feature_materialization_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage176_c9_minrisk_point_in_time_feature_materialization_gate"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage176_point_in_time_feature_materialization_gate"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE153_DIR = LINE_DIR / "outputs" / "stage153_authoritative_minute_ohlcv_intake_validator"
STAGE153_PREFIX = "qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator"
STAGE153_TAG = "stage153_authoritative_minute_ohlcv_intake_validator_v1"
STAGE153_SUMMARY_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_summary_{STAGE153_TAG}.csv"
STAGE153_REQUEST_AUDIT_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_request_file_audit_{STAGE153_TAG}.csv"
STAGE153_WINDOW_COVERAGE_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_window_coverage_audit_{STAGE153_TAG}.csv"

STAGE156_DIR = LINE_DIR / "outputs" / "stage156_authoritative_minute_feature_prebuild_gate"
STAGE156_PREFIX = "qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate"
STAGE156_TAG = "stage156_authoritative_minute_feature_prebuild_gate_v1"
STAGE156_SUMMARY_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_summary_{STAGE156_TAG}.csv"
STAGE156_FEATURE_CONTRACT_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_feature_contract_{STAGE156_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FEATURE_REQUIREMENT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_lookback_requirement_{MODEL_TAG}.csv"
WINDOW_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_decision_materialization_audit_{MODEL_TAG}.csv"
CONTEXT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_context_readiness_summary_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_materialization_status_{MODEL_TAG}.png"
CLOSED_BAR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_bar_distribution_{MODEL_TAG}.png"
FEATURE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_readiness_by_context_{MODEL_TAG}.png"
ENTRY_PRIORITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_priority_readiness_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"


FEATURE_REQUIREMENTS = [
    ("bar_return_1m", "price_path", 2),
    ("range_ratio_1m", "price_path", 1),
    ("directional_efficiency_30m", "price_path", 31),
    ("realized_volatility_30m", "volatility", 31),
    ("true_range_median_30m", "volatility", 31),
    ("volume_participation_30m", "participation", 30),
    ("volume_zscore_60m", "participation", 60),
    ("open_interest_delta_60m", "positioning", 61),
    ("turnover_vwap_gap_30m", "participation", 30),
    ("closed_bar_count_coverage", "data_quality", 60),
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
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _feature_requirements(feature_contract: pd.DataFrame) -> pd.DataFrame:
    declared = set(feature_contract["feature_id"].astype(str)) if not feature_contract.empty and "feature_id" in feature_contract else set()
    rows = []
    for feature_id, family, min_closed_bars in FEATURE_REQUIREMENTS:
        rows.append(
            {
                "feature_id": feature_id,
                "family": family,
                "min_predecision_closed_bars": min_closed_bars,
                "declared_by_stage156": int(feature_id in declared),
                "future_data_allowed": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(rows)


def _decision_timestamp(row: pd.Series) -> tuple[pd.Timestamp, str, int, str]:
    start = pd.to_datetime(row["window_start_ts"], errors="coerce")
    if str(row["window_type"]) == "entry_pre30_post120":
        return start + pd.Timedelta(minutes=30), "entry_decision", 1, "window_start_plus_30m_scan_start"
    if str(row["window_type"]) == "event_buffer_15m":
        return start + pd.Timedelta(minutes=15), "event_diagnostic", 0, "window_start_plus_15m_event_time"
    return start, "session_path_diagnostic", 0, "window_start_scan_start"


def _materialization_audit(windows: pd.DataFrame, requests: pd.DataFrame, requirements: pd.DataFrame) -> pd.DataFrame:
    normalized_by_request = requests.set_index("request_id")["expected_normalized_file"].to_dict()
    request_ready_by_request = requests.set_index("request_id")["request_ready"].to_dict()
    cache: dict[str, pd.DataFrame] = {}
    records = []
    for _, row in windows.iterrows():
        request_id = str(row["request_id"])
        if request_id not in cache:
            path = Path(str(normalized_by_request.get(request_id, "")))
            if not path.is_absolute():
                path = REPO_DIR / path
            bars = pd.read_parquet(path)
            bars["bar_end_ts"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
            cache[request_id] = bars
        bars = cache[request_id]
        decision_ts, context, entry_candidate_context, decision_rule = _decision_timestamp(row)
        mask = (
            bars["vt_symbol"].astype(str).eq(str(row["vt_symbol"]))
            & bars["bar_end_ts"].notna()
            & bars["bar_end_ts"].le(decision_ts)
        )
        closed = bars.loc[mask].sort_values("bar_end_ts")
        closed_bar_count = int(len(closed))
        ready_by_feature = {
            str(req.feature_id): int(closed_bar_count >= int(req.min_predecision_closed_bars))
            for req in requirements.itertuples()
        }
        one_min_ready = int(ready_by_feature["bar_return_1m"] == 1 and ready_by_feature["range_ratio_1m"] == 1)
        core_30m_ready = int(
            ready_by_feature["directional_efficiency_30m"] == 1
            and ready_by_feature["realized_volatility_30m"] == 1
            and ready_by_feature["true_range_median_30m"] == 1
            and ready_by_feature["volume_participation_30m"] == 1
            and ready_by_feature["turnover_vwap_gap_30m"] == 1
        )
        full_60m_ready = int(
            core_30m_ready == 1
            and ready_by_feature["volume_zscore_60m"] == 1
            and ready_by_feature["open_interest_delta_60m"] == 1
            and ready_by_feature["closed_bar_count_coverage"] == 1
        )
        entry_feature_row_allowed = int(entry_candidate_context == 1 and full_60m_ready == 1)
        if entry_candidate_context == 0:
            block_reason = "diagnostic_context_not_entry_rule"
        elif full_60m_ready == 1:
            block_reason = ""
        elif core_30m_ready == 0:
            block_reason = "insufficient_predecision_closed_bars_for_30m_features"
        else:
            block_reason = "insufficient_predecision_closed_bars_for_60m_features"
        records.append(
            {
                "window_id": row["window_id"],
                "request_id": request_id,
                "vt_symbol": row["vt_symbol"],
                "exchange": row["exchange"],
                "product": row["product"],
                "window_type": row["window_type"],
                "priority_class": row["priority_class"],
                "decision_context": context,
                "decision_ts": decision_ts.strftime("%Y-%m-%d %H:%M:%S"),
                "decision_ts_rule": decision_rule,
                "entry_candidate_context": entry_candidate_context,
                "request_ready": int(request_ready_by_request.get(request_id, 0)),
                "coverage_pass": int(row.get("coverage_pass", 0)),
                "closed_bar_count_before_decision": closed_bar_count,
                "one_min_features_ready": one_min_ready,
                "core_30m_features_ready": core_30m_ready,
                "full_60m_contract_features_ready": full_60m_ready,
                "entry_feature_row_allowed": entry_feature_row_allowed,
                "feature_table_row_written": 0,
                "primary_block_reason": block_reason,
                "strategy_rule_allowed": 0,
                **{f"{feature_id}_ready": ready for feature_id, ready in ready_by_feature.items()},
            }
        )
    return pd.DataFrame(records)


def _context_summary(audit: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        audit.groupby(["decision_context", "window_type"], dropna=False)
        .agg(
            window_count=("window_id", "count"),
            entry_candidate_context_count=("entry_candidate_context", "sum"),
            min_closed_bars=("closed_bar_count_before_decision", "min"),
            median_closed_bars=("closed_bar_count_before_decision", "median"),
            max_closed_bars=("closed_bar_count_before_decision", "max"),
            one_min_ready_count=("one_min_features_ready", "sum"),
            core_30m_ready_count=("core_30m_features_ready", "sum"),
            full_60m_ready_count=("full_60m_contract_features_ready", "sum"),
            entry_feature_row_allowed_count=("entry_feature_row_allowed", "sum"),
        )
        .reset_index()
    )
    return grouped


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage153_all_requests_ready", summary["stage153_request_ready_count"], summary["stage153_request_count"], "data_hard"),
        ("stage153_all_windows_covered", summary["stage153_window_coverage_pass_count"], summary["stage153_required_window_count"], "coverage_hard"),
        ("stage156_all_windows_feature_ready", summary["stage156_feature_ready_window_count"], summary["stage153_required_window_count"], "feature_contract_hard"),
        ("decision_timestamp_defined", summary["decision_timestamp_defined_count"], summary["window_count"], "point_in_time_hard"),
        ("entry_30m_features_ready", summary["entry_core_30m_ready_count"], summary["entry_window_count"], "entry_feature_hard"),
        ("entry_60m_contract_ready", summary["entry_full_60m_ready_count"], summary["entry_window_count"], "entry_feature_hard"),
        ("entry_feature_row_allowed", summary["entry_feature_row_allowed_count"], summary["entry_window_count"], "entry_feature_hard"),
        ("feature_table_row_written", summary["feature_table_row_written_count"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "execution_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": int(observed),
                "required": int(required),
                "pass_now": int(int(observed) == int(required)),
                "severity": severity,
            }
            for gate_id, observed, required, severity in rows
        ]
    )


def _write_report(summary: pd.DataFrame, requirements: pd.DataFrame, context: pd.DataFrame, audit: pd.DataFrame, gate: pd.DataFrame) -> None:
    lines = [
        "# Stage176 Point-in-Time Feature Materialization Gate",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- This stage writes no feature table and creates no strategy rule. It audits whether Stage156 features can be materialized before the decision timestamp without future leakage.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Feature Lookback Requirements",
        "",
        _md_table(requirements),
        "",
        "## Context Summary",
        "",
        _md_table(context),
        "",
        "## Window Audit Sample",
        "",
        _md_table(
            audit[
                [
                    "window_id",
                    "window_type",
                    "priority_class",
                    "decision_context",
                    "closed_bar_count_before_decision",
                    "one_min_features_ready",
                    "core_30m_features_ready",
                    "full_60m_contract_features_ready",
                    "entry_feature_row_allowed",
                    "primary_block_reason",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_title("Official path unchanged; Stage176 audits point-in-time feature materialization")
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["windows", "entry", "entry 1m", "entry 30m", "entry 60m", "rows"]
    values = [
        summary["window_count"],
        summary["entry_window_count"],
        summary["entry_one_min_ready_count"],
        summary["entry_core_30m_ready_count"],
        summary["entry_full_60m_ready_count"],
        summary["feature_table_row_written_count"],
    ]
    axes[3].bar(labels, values, color=["#3657D6", "#0F766E", "#B45309", "#B91C1C", "#991B1B", "#111827"])
    axes[3].set_ylabel("count")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_closed_bars(audit: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    contexts = list(audit["decision_context"].drop_duplicates())
    data = [audit.loc[audit["decision_context"].eq(context), "closed_bar_count_before_decision"].to_numpy() for context in contexts]
    ax.boxplot(data, tick_labels=contexts, showfliers=False)
    ax.axhline(31, color="#B45309", linestyle="--", linewidth=1.0, label="30m feature minimum")
    ax.axhline(61, color="#991B1B", linestyle="--", linewidth=1.0, label="60m feature minimum")
    ax.set_title("Closed bars available before decision timestamp")
    ax.set_ylabel("closed 1m bars")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(CLOSED_BAR_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_feature_matrix(context: pd.DataFrame) -> None:
    matrix = context.set_index("decision_context")[
        ["window_count", "one_min_ready_count", "core_30m_ready_count", "full_60m_ready_count", "entry_feature_row_allowed_count"]
    ]
    fig, ax = plt.subplots(figsize=(12.5, 5.5))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=max(1, data.max()))
    ax.set_title("Feature readiness by point-in-time context")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for r in range(data.shape[0]):
        for c in range(data.shape[1]):
            ax.text(c, r, int(data[r, c]), ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(FEATURE_MATRIX_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_entry_priority(audit: pd.DataFrame) -> None:
    entry = audit[audit["entry_candidate_context"].eq(1)].copy()
    grouped = (
        entry.groupby("priority_class")
        .agg(
            window_count=("window_id", "count"),
            one_min_ready=("one_min_features_ready", "sum"),
            core_30m_ready=("core_30m_features_ready", "sum"),
            full_60m_ready=("full_60m_contract_features_ready", "sum"),
        )
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(12.5, 6))
    x = np.arange(len(grouped.index))
    width = 0.2
    for idx, col in enumerate(["window_count", "one_min_ready", "core_30m_ready", "full_60m_ready"]):
        ax.bar(x + (idx - 1.5) * width, grouped[col].to_numpy(), width=width, label=col)
    ax.set_xticks(x)
    ax.set_xticklabels(grouped.index, rotation=20, ha="right")
    ax.set_title("Entry decision readiness by priority class")
    ax.set_ylabel("window count")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(ENTRY_PRIORITY_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, max(5.5, len(gate) * 0.45)))
    matrix = gate.set_index("gate_id")[["pass_now"]]
    data = matrix.to_numpy(dtype=float)
    ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage176 gate status")
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
    stage153 = _row(STAGE153_SUMMARY_IN)
    stage156 = _row(STAGE156_SUMMARY_IN)
    requests = _read_csv(STAGE153_REQUEST_AUDIT_IN)
    windows = _read_csv(STAGE153_WINDOW_COVERAGE_IN)
    feature_contract = _read_csv(STAGE156_FEATURE_CONTRACT_IN)
    if not stage153 or not stage156 or requests.empty or windows.empty or feature_contract.empty:
        raise RuntimeError("missing Stage153/156 inputs for Stage176")

    requirements = _feature_requirements(feature_contract)
    audit = _materialization_audit(windows, requests, requirements)
    context = _context_summary(audit)
    entry = audit[audit["entry_candidate_context"].eq(1)]
    decision = "stage176_point_in_time_feature_materialization_blocks_entry_features_extend_predecision_lookback_no_rule"
    summary_dict = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "extend_predecision_authoritative_minute_manifest_or_predeclare_shorter_lookback_features_before_any_rule",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage153_request_count": _int(stage153, "request_count"),
        "stage153_request_ready_count": _int(stage153, "request_ready_count"),
        "stage153_required_window_count": _int(stage153, "required_window_count"),
        "stage153_window_coverage_pass_count": _int(stage153, "window_coverage_pass_count"),
        "stage156_feature_ready_window_count": _int(stage156, "feature_ready_window_count"),
        "stage156_positioning_feature_ready_window_count": _int(stage156, "positioning_feature_ready_window_count"),
        "window_count": int(len(audit)),
        "decision_timestamp_defined_count": int(audit["decision_ts"].astype(str).ne("").sum()),
        "entry_window_count": int(len(entry)),
        "entry_one_min_ready_count": int(entry["one_min_features_ready"].sum()),
        "entry_core_30m_ready_count": int(entry["core_30m_features_ready"].sum()),
        "entry_full_60m_ready_count": int(entry["full_60m_contract_features_ready"].sum()),
        "entry_feature_row_allowed_count": int(entry["entry_feature_row_allowed"].sum()),
        "feature_table_row_written_count": 0,
        "feature_table_file_written": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage153.get("end_equity", np.nan)),
        "total_return_pct": float(stage153.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage153.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage153.get("sharpe", np.nan)),
        "total_slippage": float(stage153.get("total_slippage", np.nan)),
        "total_trade_count": float(stage153.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage153.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage153.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(requirements, FEATURE_REQUIREMENT_OUT)
    _write_csv(audit, WINDOW_AUDIT_OUT)
    _write_csv(context, CONTEXT_SUMMARY_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, requirements, context, audit, gate)
    _plot_path(curve, summary_dict)
    _plot_closed_bars(audit)
    _plot_feature_matrix(context)
    _plot_entry_priority(audit)
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
                "stage153_summary": str(STAGE153_SUMMARY_IN),
                "stage153_request_audit": str(STAGE153_REQUEST_AUDIT_IN),
                "stage153_window_coverage": str(STAGE153_WINDOW_COVERAGE_IN),
                "stage156_summary": str(STAGE156_SUMMARY_IN),
                "stage156_feature_contract": str(STAGE156_FEATURE_CONTRACT_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "feature_lookback_requirement": str(FEATURE_REQUIREMENT_OUT),
                "window_decision_materialization_audit": str(WINDOW_AUDIT_OUT),
                "context_readiness_summary": str(CONTEXT_SUMMARY_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(CLOSED_BAR_CHART_OUT),
                    str(FEATURE_MATRIX_CHART_OUT),
                    str(ENTRY_PRIORITY_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "external_research_sources": [
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html",
                "https://pandas.pydata.org/docs/user_guide/window.html",
                "https://www.w3.org/TR/prov-dm/",
            ],
            "locks": {
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

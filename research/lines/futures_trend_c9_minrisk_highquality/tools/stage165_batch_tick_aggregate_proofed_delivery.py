from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage165"
MODEL_TAG = "stage165_batch_tick_aggregate_proofed_delivery_v1"
OUTPUT_PREFIX = "qmt_roll_stage165_c9_minrisk_batch_tick_aggregate_proofed_delivery"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage165_batch_tick_aggregate_proofed_delivery"

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
STAGE152_REQUEST_TEMPLATE_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_request_manifest_template_{STAGE152_TAG}.csv"

STAGE153_DIR = LINE_DIR / "outputs" / "stage153_authoritative_minute_ohlcv_intake_validator"
STAGE153_PREFIX = "qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator"
STAGE153_TAG = "stage153_authoritative_minute_ohlcv_intake_validator_v1"
STAGE153_REQUEST_AUDIT_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_request_file_audit_{STAGE153_TAG}.csv"

STAGE160_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage160_authoritative_minute_arrival_monitor"
    / "qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_"
    "stage160_authoritative_minute_arrival_monitor_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SELECTED_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_requests_{MODEL_TAG}.csv"
REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_run_status_{MODEL_TAG}.csv"
DELIVERY_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_audit_{MODEL_TAG}.csv"
WINDOW_PRECHECK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_batch_status_{MODEL_TAG}.png"
SELECTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_request_priority_{MODEL_TAG}.png"
DELIVERY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_matrix_{MODEL_TAG}.png"
WINDOW_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

MAX_REQUESTS = int(os.getenv("STAGE165_MAX_REQUESTS", "5"))
WRITE_INCOMING = os.getenv("STAGE165_WRITE_INCOMING", "1").strip() != "0"
OVERWRITE_EXISTING = os.getenv("STAGE165_OVERWRITE_EXISTING", "0").strip() == "1"
MAX_SECONDS_TICK = int(os.getenv("STAGE165_MAX_SECONDS_TICK", "90"))
TICK_DATA_LENGTH = int(os.getenv("STAGE165_TICK_DATA_LENGTH", "120000"))
MIN_NORMALIZED_ROWS = int(os.getenv("STAGE165_MIN_NORMALIZED_ROWS", "10"))


def _load_stage164_helpers():
    path = TOOLS_DIR / "stage164_tick_aggregate_full_request_proofed_delivery_smoke.py"
    spec = importlib.util.spec_from_file_location("stage164_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Stage164 helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.WRITE_INCOMING = WRITE_INCOMING
    module.OVERWRITE_EXISTING = OVERWRITE_EXISTING
    module.MAX_SECONDS_TICK = MAX_SECONDS_TICK
    module.TICK_DATA_LENGTH = TICK_DATA_LENGTH
    module.MIN_NORMALIZED_ROWS = MIN_NORMALIZED_ROWS
    module.PROOF_NORMALIZATION_VERSION = MODEL_TAG
    return module


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
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
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.6f}")
        else:
            data[column] = data[column].map(
                lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|").replace("\n", "<br>")
            )
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        number = float(row.get(key, default))
    except (TypeError, ValueError):
        return default
    return default if not np.isfinite(number) else number


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage160 = _read_csv(STAGE160_SUMMARY_IN, required=False)
    if not stage160.empty:
        row = stage160.iloc[0].to_dict()
        return {
            "end_equity": _num(row, "end_equity", np.nan),
            "total_return_pct": _num(row, "total_return_pct", np.nan),
            "max_drawdown_pct": _num(row, "max_drawdown_pct", np.nan),
            "sharpe": _num(row, "sharpe", np.nan),
            "total_slippage": _num(row, "total_slippage", np.nan),
            "total_trade_count": _num(row, "total_trade_count", np.nan),
            "closed_lot_win_rate_pct": _num(row, "closed_lot_win_rate_pct", np.nan),
            "max_broker10_margin_to_equity_pct": _num(row, "max_broker10_margin_to_equity_pct", np.nan),
        }
    equity = curve["account_equity"].dropna()
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": (float(equity.iloc[-1]) / float(equity.iloc[0]) - 1.0) * 100.0,
        "max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "sharpe": np.nan,
        "total_slippage": np.nan,
        "total_trade_count": np.nan,
        "closed_lot_win_rate_pct": np.nan,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
    }


def _ready_request_ids() -> set[str]:
    audit = _read_csv(STAGE153_REQUEST_AUDIT_IN, required=False)
    if audit.empty or "request_ready" not in audit.columns:
        return set()
    return set(audit.loc[pd.to_numeric(audit["request_ready"], errors="coerce").fillna(0).eq(1), "request_id"].astype(str))


def _select_batch(manifest: pd.DataFrame, ready_ids: set[str]) -> pd.DataFrame:
    data = manifest[~manifest["request_id"].astype(str).isin(ready_ids)].copy()
    for column in [
        "priority_score",
        "right_tail_window_count",
        "bottom_loss_window_count",
        "maxdd_window_count",
        "low_resolution_window_count",
        "required_window_count",
        "estimated_required_1m_bars",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0).astype(int)
    data["selection_rank"] = np.arange(1, len(data) + 1)
    selected = data.sort_values(
        [
            "priority_score",
            "right_tail_window_count",
            "bottom_loss_window_count",
            "maxdd_window_count",
            "low_resolution_window_count",
            "request_id",
        ],
        ascending=[False, False, False, False, False, True],
    ).head(MAX_REQUESTS)
    selected = selected.reset_index(drop=True)
    selected["batch_rank"] = np.arange(1, len(selected) + 1)
    selected["selection_policy"] = (
        "missing_stage153_ready_then_priority_score_desc_window_counts_desc_request_id_asc_not_pnl"
    )
    return selected


def _run_request(helper: Any, row: pd.Series, credential: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    started = datetime.now()
    raw_ticks, fetch_status = helper._fetch_ticks(row, credential)
    normalized = helper._aggregate_ticks(row, raw_ticks)
    window_precheck = helper._window_precheck(row, normalized)
    delivery, delivery_row = helper._write_delivery(row, raw_ticks, normalized, fetch_status, window_precheck)
    finished = datetime.now()
    status = {
        "request_id": str(row["request_id"]),
        "batch_rank": int(row["batch_rank"]),
        "vt_symbol": str(row["vt_symbol"]),
        "exchange": str(row["exchange"]),
        "product": str(row["product"]),
        "request_date": str(row["request_date"]),
        "priority_score": int(row["priority_score"]),
        "right_tail_window_count": int(row["right_tail_window_count"]),
        "bottom_loss_window_count": int(row["bottom_loss_window_count"]),
        "maxdd_window_count": int(row["maxdd_window_count"]),
        "low_resolution_window_count": int(row["low_resolution_window_count"]),
        "tick_fetch_status": str(fetch_status.get("tick_fetch_status", "")),
        "raw_tick_row_count": int(len(raw_ticks)),
        "normalized_row_count": int(len(normalized)),
        "positive_volume_row_count": int(pd.to_numeric(normalized.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0).sum()),
        "positive_turnover_row_count": int(pd.to_numeric(normalized.get("turnover", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0).sum()),
        "window_precheck_count": int(len(window_precheck)),
        "window_precheck_pass_count": int(window_precheck["coverage_precheck_pass"].sum()) if not window_precheck.empty else 0,
        "expected_files_written": int(delivery_row["expected_files_written"]),
        "raw_written": int(delivery_row["raw_written"]),
        "normalized_written": int(delivery_row["normalized_written"]),
        "proof_written": int(delivery_row["proof_written"]),
        "write_blocker": str(delivery_row.get("write_blocker", "")),
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round((finished - started).total_seconds(), 2),
    }
    delivery = delivery.copy()
    delivery["batch_rank"] = int(row["batch_rank"])
    window_precheck = window_precheck.copy()
    window_precheck["request_id"] = str(row["request_id"])
    window_precheck["batch_rank"] = int(row["batch_rank"])
    return status, delivery, window_precheck


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    gates = [
        ("selected_request_count", summary["selected_request_count"], min(MAX_REQUESTS, summary["remaining_before_count"]), "selection_hard"),
        ("credentials_present", summary["credential_present"], 1, "source_hard"),
        ("fetch_attempted_count", summary["fetch_attempted_count"], summary["selected_request_count"], "source_hard"),
        ("delivery_success_count", summary["delivery_success_count"], 1, "delivery_hard"),
        ("expected_files_written", summary["expected_files_written"], summary["delivery_success_count"] * 3, "delivery_hard"),
        ("window_precheck_all_pass_for_written", summary["window_precheck_fail_for_written_count"], 0, "coverage_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "safety_hard"),
    ]
    rows = []
    for gate_id, observed, required, severity in gates:
        observed_int = int(observed)
        required_int = int(required)
        rows.append(
            {
                "gate_id": gate_id,
                "observed": observed_int,
                "required": required_int,
                "pass_now": int(observed_int >= required_int) if required_int > 0 else int(observed_int == 0),
                "severity": severity,
            }
        )
    return pd.DataFrame(rows)


def _write_report(
    summary: dict[str, Any],
    selected: pd.DataFrame,
    request_status: pd.DataFrame,
    delivery: pd.DataFrame,
    window_precheck: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    text = "\n".join(
        [
            "# Stage165 Batch Tick Aggregate Proofed Delivery",
            "",
            f"- model_tag: `{MODEL_TAG}`",
            f"- decision: `{summary['decision']}`",
            "- Scope: deterministic small batch expansion of Stage152 request delivery.",
            "- Hard lock: no strategy rule, no true engine, no A/B, no CTP, no order API, no official config change.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Selected Requests",
            "",
            _md_table(selected),
            "",
            "## Request Run Status",
            "",
            _md_table(request_status),
            "",
            "## Delivery Audit",
            "",
            _md_table(delivery),
            "",
            "## Window Precheck",
            "",
            _md_table(window_precheck, max_rows=30),
            "",
            "## Gate Status",
            "",
            _md_table(gate),
            "",
            "## Next",
            "",
            "- Rerun Stage160 and Stage153 after any files are written.",
            "- Do not enter feature building or strategy work until full package gates pass.",
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(text, encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.8)
    axes[0].set_title("Official Path Unchanged; Stage165 Batch Delivery Status")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.25)
    axes[0].text(
        0.01,
        0.95,
        f"delivered={summary['delivery_success_count']}/{summary['selected_request_count']} | files={summary['expected_files_written']}",
        transform=axes[0].transAxes,
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.9},
    )
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.3)
    axes[1].axhline(-30, color="#888888", linestyle="--", linewidth=0.9)
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#9467bd", linewidth=1.2)
    axes[2].axhline(100, color="#888888", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("Broker10 %")
    axes[2].grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_selection(selected: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 6))
    data = selected.copy()
    ax.barh(data["request_id"], data["priority_score"], color="#1f77b4", alpha=0.85, label="priority")
    ax.barh(data["request_id"], data["right_tail_window_count"], color="#2ca02c", alpha=0.45, label="right-tail windows")
    ax.set_title("Stage165 Deterministic Batch Selection")
    ax.set_xlabel("count / score")
    ax.grid(axis="x", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(SELECTION_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_delivery(request_status: pd.DataFrame) -> None:
    cols = ["raw_written", "normalized_written", "proof_written"]
    fig, ax = plt.subplots(figsize=(10, max(4, len(request_status) * 0.55)))
    matrix = request_status[cols].to_numpy(dtype=float) if not request_status.empty else np.zeros((1, len(cols)))
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(request_status)))
    ax.set_yticklabels(request_status["request_id"].tolist())
    ax.set_title("Stage165 Delivery Matrix")
    for r in range(matrix.shape[0]):
        for c in range(matrix.shape[1]):
            ax.text(c, r, int(matrix[r, c]), ha="center", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(DELIVERY_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_windows(window_precheck: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, max(5, len(window_precheck) * 0.28)))
    if window_precheck.empty:
        ax.text(0.5, 0.5, "No windows", ha="center", va="center")
        ax.axis("off")
    else:
        cols = ["observed_bar_count", "positive_volume_bar_count", "coverage_precheck_pass"]
        matrix = window_precheck[cols].to_numpy(dtype=float)
        scale = matrix.copy()
        if scale[:, :2].max() > 0:
            scale[:, :2] = scale[:, :2] / scale[:, :2].max()
        ax.imshow(scale, aspect="auto", cmap=plt.get_cmap("YlGn"), vmin=0, vmax=1)
        labels = [f"{r.request_id}:{r.window_type}" for r in window_precheck.itertuples()]
        ax.set_yticks(np.arange(len(labels)))
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_xticks(np.arange(len(cols)))
        ax.set_xticklabels(cols, rotation=20, ha="right")
        ax.set_title("Stage165 Window Precheck")
    fig.tight_layout()
    fig.savefig(WINDOW_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 7))
    matrix = gate[["pass_now"]].to_numpy(dtype=float)
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_yticks(np.arange(len(gate)))
    ax.set_yticklabels(gate["gate_id"].tolist())
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_title("Stage165 Gate Status Matrix")
    for row_idx, row in gate.iterrows():
        ax.text(0, row_idx, f"{int(row['observed'])}/{int(row['required'])}", ha="center", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    helper = _load_stage164_helpers()
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    manifest = _read_csv(STAGE152_REQUEST_TEMPLATE_IN)
    ready_ids = _ready_request_ids()
    selected = _select_batch(manifest, ready_ids)
    credential = helper._credentials()

    statuses: list[dict[str, Any]] = []
    deliveries: list[pd.DataFrame] = []
    windows: list[pd.DataFrame] = []
    for _, row in selected.iterrows():
        print(f"{STAGE} {int(row['batch_rank'])}/{len(selected)} {row['request_id']} {row['vt_symbol']}", flush=True)
        status, delivery, window_precheck = _run_request(helper, row, credential)
        statuses.append(status)
        deliveries.append(delivery)
        windows.append(window_precheck)

    request_status = pd.DataFrame(statuses)
    delivery_audit = pd.concat(deliveries, ignore_index=True) if deliveries else pd.DataFrame()
    window_precheck = pd.concat(windows, ignore_index=True) if windows else pd.DataFrame()
    delivery_success_count = int(request_status["expected_files_written"].eq(3).sum()) if not request_status.empty else 0
    written_windows = window_precheck[window_precheck["request_id"].isin(request_status.loc[request_status["expected_files_written"].eq(3), "request_id"])] if not window_precheck.empty else pd.DataFrame()
    window_fail_for_written = int((written_windows["coverage_precheck_pass"].eq(0)).sum()) if not written_windows.empty else 0
    decision = (
        "stage165_batch_tick_aggregate_delivery_written_run_stage160_153_no_rule"
        if delivery_success_count > 0
        else "stage165_batch_tick_aggregate_delivery_none_written_no_rule"
    )
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": created_at,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "rerun_stage160_then_stage153" if delivery_success_count > 0 else "inspect_batch_failures_or_reduce_batch",
        "selection_policy": "missing_stage153_ready_then_priority_score_desc_window_counts_desc_request_id_asc_not_pnl",
        "max_requests": MAX_REQUESTS,
        "remaining_before_count": int(len(manifest) - len(ready_ids)),
        "ready_before_count": int(len(ready_ids)),
        "selected_request_count": int(len(selected)),
        "credential_present": int(credential["username_present"] and credential["password_present"]),
        "fetch_attempted_count": int(len(request_status)),
        "fetch_extracted_count": int(request_status["tick_fetch_status"].isin(["extracted", "timeout"]).sum()) if not request_status.empty else 0,
        "delivery_success_count": delivery_success_count,
        "expected_files_written": int(request_status["expected_files_written"].sum()) if not request_status.empty else 0,
        "raw_written_count": int(request_status["raw_written"].sum()) if not request_status.empty else 0,
        "normalized_written_count": int(request_status["normalized_written"].sum()) if not request_status.empty else 0,
        "proof_written_count": int(request_status["proof_written"].sum()) if not request_status.empty else 0,
        "raw_tick_row_count": int(request_status["raw_tick_row_count"].sum()) if not request_status.empty else 0,
        "normalized_row_count": int(request_status["normalized_row_count"].sum()) if not request_status.empty else 0,
        "positive_volume_row_count": int(request_status["positive_volume_row_count"].sum()) if not request_status.empty else 0,
        "window_precheck_count": int(len(window_precheck)),
        "window_precheck_pass_count": int(window_precheck["coverage_precheck_pass"].sum()) if not window_precheck.empty else 0,
        "window_precheck_fail_for_written_count": window_fail_for_written,
        "write_incoming_enabled": int(WRITE_INCOMING),
        "overwrite_existing": int(OVERWRITE_EXISTING),
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "side_effect_count": delivery_success_count,
        "visual_output_count": 5,
    }
    summary.update(metrics)
    gate = _gate_status(summary)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(selected, SELECTED_OUT)
    _write_csv(request_status, REQUEST_STATUS_OUT)
    _write_csv(delivery_audit, DELIVERY_AUDIT_OUT)
    _write_csv(window_precheck, WINDOW_PRECHECK_OUT)
    _write_csv(gate, GATE_OUT)
    _write_json(
        DECISION_OUT,
        {
            "decision": decision,
            "summary": summary,
            "outputs": {
                "summary": SUMMARY_OUT,
                "selected": SELECTED_OUT,
                "request_status": REQUEST_STATUS_OUT,
                "delivery_audit": DELIVERY_AUDIT_OUT,
                "window_precheck": WINDOW_PRECHECK_OUT,
                "gate_status": GATE_OUT,
                "report": REPORT_OUT,
                "charts": [PATH_CHART_OUT, SELECTION_CHART_OUT, DELIVERY_CHART_OUT, WINDOW_CHART_OUT, GATE_CHART_OUT],
            },
        },
    )
    _write_report(summary, selected, request_status, delivery_audit, window_precheck, gate)
    _plot_path(curve, summary)
    _plot_selection(selected)
    _plot_delivery(request_status)
    _plot_windows(window_precheck)
    _plot_gate(gate)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

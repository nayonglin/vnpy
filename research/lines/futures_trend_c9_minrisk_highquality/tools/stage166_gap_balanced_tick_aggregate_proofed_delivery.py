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
STAGE = "Stage166"
MODEL_TAG = "stage166_gap_balanced_tick_aggregate_proofed_delivery_v1"
OUTPUT_PREFIX = "qmt_roll_stage166_c9_minrisk_gap_balanced_tick_aggregate_proofed_delivery"
SELECTION_POLICY = "missing_stage153_ready_then_manifest_coverage_gap_bottom_loss_maxdd_right_tail_request_id_not_trade_rule"
REPORT_TITLE = "Stage166 Gap Balanced Tick Aggregate Proofed Delivery"
SCOPE_NOTE = "deterministic Stage152 coverage-gap batch expansion."
SELECTION_NOTE = "bottom-loss/maxDD classes are used only as manifest coverage obligations, not as a trade filter."
PATH_CHART_TITLE = "Official Path Unchanged; Stage166 Gap-Balanced Delivery"
SELECTION_CHART_TITLE = "Stage166 Manifest Coverage-Gap Selection"
DELIVERY_CHART_TITLE = "Stage166 Delivery Matrix"
WINDOW_CHART_TITLE = "Stage166 Window Precheck"
GATE_CHART_TITLE = "Stage166 Gate Status Matrix"
DECISION_WRITTEN = "stage166_gap_balanced_tick_aggregate_delivery_written_run_stage160_153_no_rule"
DECISION_NONE_WRITTEN = "stage166_gap_balanced_tick_aggregate_delivery_none_written_no_rule"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage166_gap_balanced_tick_aggregate_proofed_delivery"

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

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_gap_batch_status_{MODEL_TAG}.png"
SELECTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_gap_priority_{MODEL_TAG}.png"
DELIVERY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_matrix_{MODEL_TAG}.png"
WINDOW_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

MAX_REQUESTS = int(os.getenv("STAGE166_MAX_REQUESTS", "8"))
WRITE_INCOMING = os.getenv("STAGE166_WRITE_INCOMING", "1").strip() != "0"
OVERWRITE_EXISTING = os.getenv("STAGE166_OVERWRITE_EXISTING", "0").strip() == "1"
MAX_SECONDS_TICK = int(os.getenv("STAGE166_MAX_SECONDS_TICK", "90"))
TICK_DATA_LENGTH = int(os.getenv("STAGE166_TICK_DATA_LENGTH", "120000"))
MIN_NORMALIZED_ROWS = int(os.getenv("STAGE166_MIN_NORMALIZED_ROWS", "10"))


def _load_stage165_base() -> Any:
    path = TOOLS_DIR / "stage165_batch_tick_aggregate_proofed_delivery.py"
    spec = importlib.util.spec_from_file_location("stage165_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Stage165 base from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_stage165_base()


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


def _load_stage164_helpers() -> Any:
    BASE.WRITE_INCOMING = WRITE_INCOMING
    BASE.OVERWRITE_EXISTING = OVERWRITE_EXISTING
    BASE.MAX_SECONDS_TICK = MAX_SECONDS_TICK
    BASE.TICK_DATA_LENGTH = TICK_DATA_LENGTH
    BASE.MIN_NORMALIZED_ROWS = MIN_NORMALIZED_ROWS
    BASE.MODEL_TAG = MODEL_TAG
    return BASE._load_stage164_helpers()


def _ready_request_ids() -> set[str]:
    audit = _read_csv(STAGE153_REQUEST_AUDIT_IN, required=False)
    if audit.empty or "request_ready" not in audit.columns:
        return set()
    ready = pd.to_numeric(audit["request_ready"], errors="coerce").fillna(0).eq(1)
    return set(audit.loc[ready, "request_id"].astype(str))


def _select_batch(manifest: pd.DataFrame, ready_ids: set[str]) -> pd.DataFrame:
    data = manifest[~manifest["request_id"].astype(str).isin(ready_ids)].copy()
    numeric_columns = [
        "priority_score",
        "right_tail_window_count",
        "bottom_loss_window_count",
        "maxdd_window_count",
        "low_resolution_window_count",
        "required_window_count",
        "estimated_required_1m_bars",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0).astype(int)
    data["manifest_coverage_gap_score"] = (
        data["bottom_loss_window_count"] * 100
        + data["maxdd_window_count"] * 60
        + data["right_tail_window_count"] * 20
        + data["low_resolution_window_count"] * 5
        + data["priority_score"]
    )
    selected = data.sort_values(
        [
            "bottom_loss_window_count",
            "maxdd_window_count",
            "right_tail_window_count",
            "low_resolution_window_count",
            "priority_score",
            "request_id",
        ],
        ascending=[False, False, False, False, False, True],
    ).head(MAX_REQUESTS)
    selected = selected.reset_index(drop=True)
    selected["batch_rank"] = np.arange(1, len(selected) + 1)
    selected["selection_policy"] = SELECTION_POLICY
    return selected


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
            f"# {REPORT_TITLE}",
            "",
            f"- model_tag: `{MODEL_TAG}`",
            f"- decision: `{summary['decision']}`",
            f"- Scope: {SCOPE_NOTE}",
            "- Hard lock: no strategy rule, no true engine, no A/B, no CTP, no order API, no official config change.",
            f"- Selection note: {SELECTION_NOTE}",
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
            _md_table(window_precheck, max_rows=40),
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
    axes[0].set_title(PATH_CHART_TITLE)
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
    fig, ax = plt.subplots(figsize=(13, max(5, len(selected) * 0.58)))
    labels = selected["request_id"].tolist()
    y = np.arange(len(selected))
    left = np.zeros(len(selected))
    specs = [
        ("bottom_loss_window_count", "#d62728", "bottom-loss"),
        ("maxdd_window_count", "#ff7f0e", "maxDD"),
        ("right_tail_window_count", "#2ca02c", "right-tail"),
        ("low_resolution_window_count", "#1f77b4", "low-resolution"),
    ]
    for column, color, label in specs:
        values = pd.to_numeric(selected[column], errors="coerce").fillna(0).to_numpy(dtype=float)
        ax.barh(y, values, left=left, color=color, alpha=0.82, label=label)
        left += values
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_title(SELECTION_CHART_TITLE)
    ax.set_xlabel("required windows by manifest class")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="lower right")
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
    ax.set_title(DELIVERY_CHART_TITLE)
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
        ax.set_title(WINDOW_CHART_TITLE)
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
    ax.set_title(GATE_CHART_TITLE)
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
        status, delivery, window_precheck = BASE._run_request(helper, row, credential)
        statuses.append(status)
        deliveries.append(delivery)
        windows.append(window_precheck)

    request_status = pd.DataFrame(statuses)
    delivery_audit = pd.concat(deliveries, ignore_index=True) if deliveries else pd.DataFrame()
    window_precheck = pd.concat(windows, ignore_index=True) if windows else pd.DataFrame()
    delivery_success_count = int(request_status["expected_files_written"].eq(3).sum()) if not request_status.empty else 0
    written_ids = request_status.loc[request_status["expected_files_written"].eq(3), "request_id"] if not request_status.empty else []
    written_windows = window_precheck[window_precheck["request_id"].isin(written_ids)] if not window_precheck.empty else pd.DataFrame()
    window_fail_for_written = int((written_windows["coverage_precheck_pass"].eq(0)).sum()) if not written_windows.empty else 0
    selected_target_windows = int(
        pd.to_numeric(selected.get("bottom_loss_window_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
        + pd.to_numeric(selected.get("maxdd_window_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    )
    delivered_target_windows = int(
        pd.to_numeric(request_status.get("bottom_loss_window_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
        + pd.to_numeric(request_status.get("maxdd_window_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    )
    delivered_right_tail_windows = int(pd.to_numeric(request_status.get("right_tail_window_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    delivered_bottom_loss_windows = int(pd.to_numeric(request_status.get("bottom_loss_window_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    delivered_maxdd_windows = int(pd.to_numeric(request_status.get("maxdd_window_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    delivered_low_resolution_windows = int(pd.to_numeric(request_status.get("low_resolution_window_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    decision = (
        DECISION_WRITTEN
        if delivery_success_count > 0
        else DECISION_NONE_WRITTEN
    )
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": created_at,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "rerun_stage160_then_stage153" if delivery_success_count > 0 else "inspect_gap_batch_failures_or_reduce_batch",
        "selection_policy": SELECTION_POLICY,
        "max_requests": MAX_REQUESTS,
        "remaining_before_count": int(len(manifest) - len(ready_ids)),
        "ready_before_count": int(len(ready_ids)),
        "selected_request_count": int(len(selected)),
        "selected_bottom_loss_window_count": int(selected["bottom_loss_window_count"].sum()) if not selected.empty else 0,
        "selected_maxdd_window_count": int(selected["maxdd_window_count"].sum()) if not selected.empty else 0,
        "selected_right_tail_window_count": int(selected["right_tail_window_count"].sum()) if not selected.empty else 0,
        "selected_low_resolution_window_count": int(selected["low_resolution_window_count"].sum()) if not selected.empty else 0,
        "selected_target_bottom_loss_plus_maxdd_window_count": selected_target_windows,
        "credential_present": int(credential["username_present"] and credential["password_present"]),
        "fetch_attempted_count": int(len(request_status)),
        "fetch_extracted_count": int(request_status["tick_fetch_status"].isin(["extracted", "timeout"]).sum()) if not request_status.empty else 0,
        "delivery_success_count": delivery_success_count,
        "delivered_right_tail_window_count": delivered_right_tail_windows if delivery_success_count > 0 else 0,
        "delivered_bottom_loss_window_count": delivered_bottom_loss_windows if delivery_success_count > 0 else 0,
        "delivered_maxdd_window_count": delivered_maxdd_windows if delivery_success_count > 0 else 0,
        "delivered_low_resolution_window_count": delivered_low_resolution_windows if delivery_success_count > 0 else 0,
        "delivered_bottom_loss_plus_maxdd_window_count": delivered_target_windows if delivery_success_count > 0 else 0,
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

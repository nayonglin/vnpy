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
STAGE = "Stage178"
MODEL_TAG = "stage178_predecision_lookback_tick_aggregate_delivery_batch_v1"
OUTPUT_PREFIX = "qmt_roll_stage178_c9_minrisk_predecision_lookback_tick_aggregate_delivery_batch"
SELECTION_POLICY = "stage177_remaining_highest_priority_exchange_round_robin_no_pnl_no_rule"
REPORT_TITLE = "Stage178 Predecision Lookback Tick Aggregate Delivery Batch"
SCOPE_NOTE = "Stage177 predecision lookback raw/normalized/proof delivery batch."
SELECTION_NOTE = "priority classes are Stage177 coverage obligations only, not trade filters."
SUCCESS_DECISION = "stage178_predecision_lookback_tick_aggregate_delivery_written_wait_stage179_no_rule"
FAIL_DECISION = "stage178_predecision_lookback_tick_aggregate_delivery_none_written_need_source_route_repair_no_rule"
SUCCESS_NEXT_ACTION = "stage179_point_in_time_validator_for_written_requests"
FAIL_NEXT_ACTION = "repair_stage178_source_or_reduce_batch_before_stage179"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage178_predecision_lookback_tick_aggregate_delivery_batch"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE160_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage160_authoritative_minute_arrival_monitor"
    / "qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_"
    "stage160_authoritative_minute_arrival_monitor_v1.csv"
)

STAGE177_DIR = LINE_DIR / "outputs" / "stage177_predecision_lookback_extension_manifest"
STAGE177_PREFIX = "qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest"
STAGE177_TAG = "stage177_predecision_lookback_extension_manifest_v1"
STAGE177_SUMMARY_IN = STAGE177_DIR / f"{STAGE177_PREFIX}_summary_{STAGE177_TAG}.csv"
STAGE177_REQUEST_MANIFEST_IN = STAGE177_DIR / f"{STAGE177_PREFIX}_request_manifest_{STAGE177_TAG}.csv"
STAGE177_EXTENSION_WINDOWS_IN = STAGE177_DIR / f"{STAGE177_PREFIX}_extension_window_contract_{STAGE177_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SELECTED_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_requests_{MODEL_TAG}.csv"
REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_run_status_{MODEL_TAG}.csv"
DELIVERY_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_audit_{MODEL_TAG}.csv"
WINDOW_PRECHECK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_precheck_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_delivery_status_{MODEL_TAG}.png"
SELECTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_exchange_priority_{MODEL_TAG}.png"
DELIVERY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delivery_matrix_{MODEL_TAG}.png"
WINDOW_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predecision_window_precheck_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

MAX_REQUESTS = int(os.getenv("STAGE178_MAX_REQUESTS", "4"))
WRITE_INCOMING = os.getenv("STAGE178_WRITE_INCOMING", "1").strip() != "0"
OVERWRITE_EXISTING = os.getenv("STAGE178_OVERWRITE_EXISTING", "0").strip() == "1"
MAX_SECONDS_TICK = int(os.getenv("STAGE178_MAX_SECONDS_TICK", "240"))
TICK_DATA_LENGTH = int(os.getenv("STAGE178_TICK_DATA_LENGTH", "10000"))
MIN_NORMALIZED_ROWS = int(os.getenv("STAGE178_MIN_NORMALIZED_ROWS", "61"))
MIN_POSITIVE_VOLUME_BARS = int(os.getenv("STAGE178_MIN_POSITIVE_VOLUME_BARS", "60"))


def _load_stage165_base() -> Any:
    path = TOOLS_DIR / "stage165_batch_tick_aggregate_proofed_delivery.py"
    spec = importlib.util.spec_from_file_location("stage165_base_for_stage178", path)
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


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(_num(row, key, float(default))))


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path, required=False)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _resolve_path(path_text: Any) -> Path:
    path = Path(str(path_text))
    return path if path.is_absolute() else REPO_DIR / path


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage160 = _row(STAGE160_SUMMARY_IN)
    if stage160:
        return {
            "end_equity": _num(stage160, "end_equity", np.nan),
            "total_return_pct": _num(stage160, "total_return_pct", np.nan),
            "max_drawdown_pct": _num(stage160, "max_drawdown_pct", np.nan),
            "sharpe": _num(stage160, "sharpe", np.nan),
            "total_slippage": _num(stage160, "total_slippage", np.nan),
            "total_trade_count": _num(stage160, "total_trade_count", np.nan),
            "closed_lot_win_rate_pct": _num(stage160, "closed_lot_win_rate_pct", np.nan),
            "max_broker10_margin_to_equity_pct": _num(stage160, "max_broker10_margin_to_equity_pct", np.nan),
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


def _load_stage164_helper() -> Any:
    BASE.WRITE_INCOMING = WRITE_INCOMING
    BASE.OVERWRITE_EXISTING = OVERWRITE_EXISTING
    BASE.MAX_SECONDS_TICK = MAX_SECONDS_TICK
    BASE.TICK_DATA_LENGTH = TICK_DATA_LENGTH
    BASE.MIN_NORMALIZED_ROWS = MIN_NORMALIZED_ROWS
    BASE.MODEL_TAG = MODEL_TAG
    helper = BASE._load_stage164_helpers()
    helper.WRITE_INCOMING = WRITE_INCOMING
    helper.OVERWRITE_EXISTING = OVERWRITE_EXISTING
    helper.MAX_SECONDS_TICK = MAX_SECONDS_TICK
    helper.TICK_DATA_LENGTH = TICK_DATA_LENGTH
    helper.MIN_NORMALIZED_ROWS = MIN_NORMALIZED_ROWS
    helper.PROOF_NORMALIZATION_VERSION = MODEL_TAG
    return helper


def _present_triplet(row: pd.Series) -> int:
    return int(
        _resolve_path(row["expected_raw_file"]).exists()
        and _resolve_path(row["expected_normalized_file"]).exists()
        and _resolve_path(row["expected_proof_file"]).exists()
    )


def _select_batch(manifest: pd.DataFrame) -> pd.DataFrame:
    data = manifest.copy()
    for column in [
        "priority_score",
        "extension_window_count",
        "target_entry_decision_count",
        "target_min_predecision_closed_bars",
        "additional_closed_bars_needed_sum",
        "right_tail_window_count",
        "bottom_loss_window_count",
        "maxdd_window_count",
        "low_resolution_window_count",
    ]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0).astype(int)
    data["triplet_present"] = data.apply(_present_triplet, axis=1)
    data = data[data["triplet_present"].eq(0)].copy()
    selected_rows: list[pd.Series] = []
    for priority in sorted(data["priority_score"].dropna().unique(), reverse=True):
        tier = data[data["priority_score"].eq(priority)].copy()
        exchanges = sorted(tier["exchange"].dropna().unique())
        while len(selected_rows) < MAX_REQUESTS and not tier.empty:
            progressed = False
            for exchange in exchanges:
                if len(selected_rows) >= MAX_REQUESTS:
                    break
                candidates = tier[tier["exchange"].eq(exchange)].sort_values(
                    ["additional_closed_bars_needed_sum", "decision_date", "request_id"],
                    ascending=[False, True, True],
                )
                if candidates.empty:
                    continue
                pick = candidates.iloc[0]
                selected_rows.append(pick)
                tier = tier[tier["request_id"].astype(str).ne(str(pick["request_id"]))]
                progressed = True
            if not progressed:
                break
        if len(selected_rows) >= MAX_REQUESTS:
            break
    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    if selected.empty:
        return selected
    selected["request_date"] = selected["decision_date"]
    selected["required_window_count"] = selected["extension_window_count"]
    selected["estimated_required_1m_bars"] = selected["target_min_predecision_closed_bars"]
    selected["batch_rank"] = np.arange(1, len(selected) + 1)
    selected["selection_policy"] = SELECTION_POLICY
    return selected


def _window_precheck_stage177(selected: pd.Series, normalized: pd.DataFrame, extension_windows: pd.DataFrame) -> pd.DataFrame:
    window_ids = {item for item in str(selected["extension_window_ids"]).split(";") if item}
    selected_windows = extension_windows[extension_windows["extension_window_id"].astype(str).isin(window_ids)].copy()
    bars = normalized.copy()
    if not bars.empty:
        bars["bar_end_ts_dt"] = pd.to_datetime(bars["bar_end_ts"], errors="coerce")
        bars["bar_start_ts_dt"] = pd.to_datetime(bars["bar_start_ts"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for _, window in selected_windows.iterrows():
        start = pd.Timestamp(window["extension_start_ts"])
        decision_ts = pd.Timestamp(window["decision_ts"])
        target = int(window["target_min_predecision_closed_bars"])
        observed = pd.DataFrame()
        if not bars.empty:
            observed = bars[
                bars["bar_end_ts_dt"].ge(start)
                & bars["bar_end_ts_dt"].le(decision_ts)
                & bars["bar_start_ts_dt"].notna()
            ].copy()
        duplicate_count = int(observed["bar_start_ts"].duplicated().sum()) if not observed.empty else 0
        positive_volume = (
            int(pd.to_numeric(observed["volume"], errors="coerce").fillna(0).gt(0).sum())
            if not observed.empty
            else 0
        )
        rows.append(
            {
                "request_id": str(selected["request_id"]),
                "extension_window_id": window["extension_window_id"],
                "source_stage152_window_id": window["source_stage152_window_id"],
                "vt_symbol": window["vt_symbol"],
                "exchange": window["exchange"],
                "product": window["product"],
                "priority_class": window["priority_class"],
                "decision_ts": window["decision_ts"],
                "extension_start_ts": window["extension_start_ts"],
                "extension_end_ts": window["extension_end_ts"],
                "target_min_predecision_closed_bars": target,
                "current_closed_bar_count_before_decision": int(window["current_closed_bar_count_before_decision"]),
                "observed_predecision_closed_bar_count": int(len(observed)),
                "duplicate_bar_count": duplicate_count,
                "positive_volume_bar_count": positive_volume,
                "min_positive_volume_bars_required": MIN_POSITIVE_VOLUME_BARS,
                "first_observed_bar_end_ts": ""
                if observed.empty
                else pd.Timestamp(observed["bar_end_ts_dt"].min()).strftime("%Y-%m-%d %H:%M:%S"),
                "last_observed_bar_end_ts": ""
                if observed.empty
                else pd.Timestamp(observed["bar_end_ts_dt"].max()).strftime("%Y-%m-%d %H:%M:%S"),
                "feature_cutoff_rule": "bar_end_ts <= decision_ts",
                "coverage_precheck_pass": int(
                    len(observed) >= target
                    and positive_volume >= MIN_POSITIVE_VOLUME_BARS
                    and duplicate_count == 0
                ),
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(rows)


def _run_request(
    helper: Any,
    row: pd.Series,
    credential: dict[str, Any],
    extension_windows: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    started = datetime.now()
    raw_ticks, fetch_status = helper._fetch_ticks(row, credential)
    normalized = helper._aggregate_ticks(row, raw_ticks)
    window_precheck = _window_precheck_stage177(row, normalized, extension_windows)
    delivery, delivery_row = helper._write_delivery(row, raw_ticks, normalized, fetch_status, window_precheck)
    finished = datetime.now()
    status = {
        "request_id": str(row["request_id"]),
        "batch_rank": int(row["batch_rank"]),
        "vt_symbol": str(row["vt_symbol"]),
        "exchange": str(row["exchange"]),
        "product": str(row["product"]),
        "decision_date": str(row["decision_date"]),
        "request_start_ts": str(row["request_start_ts"]),
        "request_end_ts": str(row["request_end_ts"]),
        "priority_score": int(row["priority_score"]),
        "right_tail_window_count": int(row["right_tail_window_count"]),
        "bottom_loss_window_count": int(row["bottom_loss_window_count"]),
        "maxdd_window_count": int(row["maxdd_window_count"]),
        "low_resolution_window_count": int(row["low_resolution_window_count"]),
        "target_min_predecision_closed_bars": int(row["target_min_predecision_closed_bars"]),
        "additional_closed_bars_needed_sum": int(row["additional_closed_bars_needed_sum"]),
        "tick_fetch_status": str(fetch_status.get("tick_fetch_status", "")),
        "tick_fetch_message": str(fetch_status.get("message", "")),
        "tick_query_start_ts": str(fetch_status.get("query_start_ts", "")),
        "tick_query_end_ts": str(fetch_status.get("query_end_ts", "")),
        "raw_tick_row_count": int(len(raw_ticks)),
        "normalized_row_count": int(len(normalized)),
        "positive_volume_row_count": int(
            pd.to_numeric(normalized.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0).sum()
        ),
        "window_precheck_count": int(len(window_precheck)),
        "window_precheck_pass_count": int(window_precheck["coverage_precheck_pass"].sum()) if not window_precheck.empty else 0,
        "min_observed_predecision_closed_bar_count": int(window_precheck["observed_predecision_closed_bar_count"].min())
        if not window_precheck.empty
        else 0,
        "max_observed_predecision_closed_bar_count": int(window_precheck["observed_predecision_closed_bar_count"].max())
        if not window_precheck.empty
        else 0,
        "raw_written": int(delivery_row["raw_written"]),
        "normalized_written": int(delivery_row["normalized_written"]),
        "proof_written": int(delivery_row["proof_written"]),
        "expected_files_written": int(delivery_row["expected_files_written"]),
        "write_blocker": str(delivery_row.get("write_blocker", "")),
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds_wall": round((finished - started).total_seconds(), 2),
        "feature_table_row_written": 0,
        "strategy_rule_allowed": 0,
    }
    return status, delivery, window_precheck


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    gates = [
        ("selected_request_count", summary["selected_request_count"], min(MAX_REQUESTS, summary["remaining_before_count"]), "selection_hard"),
        ("credentials_present", summary["credential_present"], 1, "source_hard"),
        ("fetch_attempted_count", summary["fetch_attempted_count"], summary["selected_request_count"], "source_hard"),
        ("all_written_windows_pass_predecision", summary["window_precheck_fail_for_written_count"], 0, "point_in_time_hard"),
        ("delivery_success_count", summary["delivery_success_count"], 1, "delivery_soft"),
        ("expected_files_written", summary["expected_files_written"], summary["delivery_success_count"] * 3, "delivery_hard"),
        ("feature_table_row_written", summary["feature_table_row_written_count"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_hard"),
        ("order_api_called", summary["order_api_called"], 0, "safety_hard"),
        ("official_config_changed", summary["official_config_changed"], 0, "safety_hard"),
    ]
    rows = []
    for gate_id, observed, required, severity in gates:
        observed_int = int(observed)
        required_int = int(required)
        pass_now = int(observed_int >= required_int) if required_int > 0 else int(observed_int == 0)
        rows.append(
            {
                "gate_id": gate_id,
                "observed": observed_int,
                "required": required_int,
                "pass_now": pass_now,
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
    lines = [
        f"# {REPORT_TITLE}",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary['decision']}`",
        f"- Scope: {SCOPE_NOTE}",
        "- Hard lock: no feature table, no strategy rule, no true engine, no A/B, no CTP, no order API, no official config change.",
        f"- Selection note: {SELECTION_NOTE}",
        "",
        "## External Research Judgment",
        "",
        "- TqSdk `get_tick_serial` has a documented serial length limit, so this stage intentionally uses small batches and validates actual predecision closed bars instead of assuming a 14-day request is complete.",
        "- pandas rolling/window documentation supports strict endpoint discipline; this stage accepts only `bar_end_ts <= decision_ts` as feature-visible data.",
        "- vn.py BarGenerator semantics update volume and turnover by non-negative tick deltas; Stage178 keeps that same aggregation rule through Stage164 helpers.",
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
        "## Predecision Window Precheck",
        "",
        _md_table(window_precheck, max_rows=50),
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
    axes[0].set_title(f"Official path unchanged; {STAGE} delivers predecision lookback data")
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["selected", "delivered", "precheck pass", "files", "rows written"]
    values = [
        summary["selected_request_count"],
        summary["delivery_success_count"],
        summary["window_precheck_pass_count"],
        summary["expected_files_written"],
        summary["feature_table_row_written_count"],
    ]
    axes[3].bar(labels, values, color=["#3657D6", "#0F766E", "#B45309", "#92400E", "#111827"])
    axes[3].set_ylabel("count")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_selection(selected: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.8))
    if selected.empty:
        for ax in axes:
            ax.text(0.5, 0.5, "No selection", ha="center", va="center")
            ax.axis("off")
    else:
        exchange_counts = selected.groupby("exchange")["request_id"].count().sort_index()
        axes[0].bar(exchange_counts.index, exchange_counts.to_numpy(), color="#0F766E")
        axes[0].set_title("Selected requests by exchange")
        axes[0].set_ylabel("requests")
        priority_counts = selected.groupby("priority_score")["request_id"].count().sort_index(ascending=False)
        axes[1].bar(priority_counts.index.astype(str), priority_counts.to_numpy(), color="#3657D6")
        axes[1].set_title("Selected requests by Stage177 priority")
        axes[1].set_xlabel("priority_score")
        for ax in axes:
            ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SELECTION_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_delivery(request_status: pd.DataFrame) -> None:
    cols = ["raw_written", "normalized_written", "proof_written"]
    fig, ax = plt.subplots(figsize=(10, max(4, len(request_status) * 0.58)))
    matrix = request_status[cols].to_numpy(dtype=float) if not request_status.empty else np.zeros((1, len(cols)))
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(request_status)))
    ax.set_yticklabels(request_status["request_id"].tolist() if not request_status.empty else ["none"], fontsize=8)
    ax.set_title(f"{STAGE} delivery matrix")
    for r in range(matrix.shape[0]):
        for c in range(matrix.shape[1]):
            ax.text(c, r, int(matrix[r, c]), ha="center", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(DELIVERY_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_windows(window_precheck: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, max(4.5, len(window_precheck) * 0.52)))
    if window_precheck.empty:
        ax.text(0.5, 0.5, "No windows", ha="center", va="center")
        ax.axis("off")
    else:
        cols = [
            "observed_predecision_closed_bar_count",
            "positive_volume_bar_count",
            "target_min_predecision_closed_bars",
            "coverage_precheck_pass",
        ]
        matrix = window_precheck[cols].to_numpy(dtype=float)
        scale = matrix.copy()
        max_count = max(1.0, float(scale[:, :3].max()))
        scale[:, :3] = scale[:, :3] / max_count
        ax.imshow(scale, aspect="auto", cmap=plt.get_cmap("YlGn"), vmin=0, vmax=1)
        labels = [f"{row.request_id}:{row.priority_class}" for row in window_precheck.itertuples()]
        ax.set_yticks(np.arange(len(labels)))
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xticks(np.arange(len(cols)))
        ax.set_xticklabels(cols, rotation=24, ha="right")
        ax.set_title(f"{STAGE} point-in-time predecision window precheck")
        for r in range(matrix.shape[0]):
            for c in range(matrix.shape[1]):
                ax.text(c, r, int(matrix[r, c]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(WINDOW_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, max(5.5, len(gate) * 0.45)))
    matrix = gate[["pass_now"]].to_numpy(dtype=float)
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_yticks(np.arange(len(gate)))
    ax.set_yticklabels(gate["gate_id"].tolist(), fontsize=8)
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_title(f"{STAGE} gate status")
    for row_idx, row in gate.iterrows():
        ax.text(0, row_idx, f"{int(row['observed'])}/{int(row['required'])}", ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    helper = _load_stage164_helper()
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    stage177 = _row(STAGE177_SUMMARY_IN)
    manifest = _read_csv(STAGE177_REQUEST_MANIFEST_IN)
    extension_windows = _read_csv(STAGE177_EXTENSION_WINDOWS_IN)
    selected = _select_batch(manifest)
    credential = helper._credentials()

    statuses: list[dict[str, Any]] = []
    deliveries: list[pd.DataFrame] = []
    windows: list[pd.DataFrame] = []
    for _, row in selected.iterrows():
        print(f"{STAGE} {int(row['batch_rank'])}/{len(selected)} {row['request_id']} {row['vt_symbol']}", flush=True)
        status, delivery, window_precheck = _run_request(helper, row, credential, extension_windows)
        statuses.append(status)
        deliveries.append(delivery)
        windows.append(window_precheck)

    request_status = pd.DataFrame(statuses)
    delivery_audit = pd.concat(deliveries, ignore_index=True) if deliveries else pd.DataFrame()
    window_precheck = pd.concat(windows, ignore_index=True) if windows else pd.DataFrame()
    delivery_success_count = int(request_status["expected_files_written"].eq(3).sum()) if not request_status.empty else 0
    written_ids = (
        set(request_status.loc[request_status["expected_files_written"].eq(3), "request_id"].astype(str))
        if not request_status.empty
        else set()
    )
    written_windows = window_precheck[window_precheck["request_id"].astype(str).isin(written_ids)] if not window_precheck.empty else pd.DataFrame()
    window_fail_for_written = int(written_windows["coverage_precheck_pass"].eq(0).sum()) if not written_windows.empty else 0
    decision = SUCCESS_DECISION if delivery_success_count > 0 else FAIL_DECISION
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": created_at,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": SUCCESS_NEXT_ACTION if delivery_success_count > 0 else FAIL_NEXT_ACTION,
        "selection_policy": SELECTION_POLICY,
        "max_requests": MAX_REQUESTS,
        "stage177_extension_request_count": _int(stage177, "extension_request_count"),
        "stage177_entry_window_count": _int(stage177, "entry_window_count"),
        "remaining_before_count": int(len(manifest) - manifest.apply(_present_triplet, axis=1).sum()),
        "selected_request_count": int(len(selected)),
        "selected_right_tail_window_count": int(selected["right_tail_window_count"].sum()) if not selected.empty else 0,
        "selected_bottom_loss_window_count": int(selected["bottom_loss_window_count"].sum()) if not selected.empty else 0,
        "selected_maxdd_window_count": int(selected["maxdd_window_count"].sum()) if not selected.empty else 0,
        "selected_low_resolution_window_count": int(selected["low_resolution_window_count"].sum()) if not selected.empty else 0,
        "credential_present": int(credential["username_present"] and credential["password_present"]),
        "fetch_attempted_count": int(len(request_status)),
        "fetch_extracted_or_timeout_count": int(request_status["tick_fetch_status"].isin(["extracted", "timeout"]).sum()) if not request_status.empty else 0,
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
        "min_observed_predecision_closed_bar_count": int(window_precheck["observed_predecision_closed_bar_count"].min()) if not window_precheck.empty else 0,
        "max_observed_predecision_closed_bar_count": int(window_precheck["observed_predecision_closed_bar_count"].max()) if not window_precheck.empty else 0,
        "target_min_predecision_closed_bars": int(extension_windows["target_min_predecision_closed_bars"].max()) if not extension_windows.empty else 61,
        "min_positive_volume_bars_required": MIN_POSITIVE_VOLUME_BARS,
        "tick_data_length": TICK_DATA_LENGTH,
        "max_seconds_tick": MAX_SECONDS_TICK,
        "write_incoming_enabled": int(WRITE_INCOMING),
        "overwrite_existing": int(OVERWRITE_EXISTING),
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "feature_table_row_written_count": 0,
        "feature_table_file_written": 0,
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
    _write_report(summary, selected, request_status, delivery_audit, window_precheck, gate)
    _plot_path(curve, summary)
    _plot_selection(selected)
    _plot_delivery(request_status)
    _plot_windows(window_precheck)
    _plot_gate(gate)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "summary": summary,
            "inputs": {
                "stage177_summary": str(STAGE177_SUMMARY_IN),
                "stage177_request_manifest": str(STAGE177_REQUEST_MANIFEST_IN),
                "stage177_extension_window_contract": str(STAGE177_EXTENSION_WINDOWS_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "selected": str(SELECTED_OUT),
                "request_status": str(REQUEST_STATUS_OUT),
                "delivery_audit": str(DELIVERY_AUDIT_OUT),
                "window_precheck": str(WINDOW_PRECHECK_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [str(PATH_CHART_OUT), str(SELECTION_CHART_OUT), str(DELIVERY_CHART_OUT), str(WINDOW_CHART_OUT), str(GATE_CHART_OUT)],
            },
            "external_research_sources": [
                "https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html",
                "https://pandas.pydata.org/docs/user_guide/window.html",
                "https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py",
            ],
            "locks": {
                "feature_cutoff_rule": "bar_end_ts <= decision_ts",
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
    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

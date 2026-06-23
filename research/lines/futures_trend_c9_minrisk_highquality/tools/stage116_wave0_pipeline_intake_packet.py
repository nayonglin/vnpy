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
STAGE = "Stage116"
MODEL_TAG = "stage116_wave0_pipeline_intake_packet_v1"
OUTPUT_PREFIX = "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage116_wave0_pipeline_intake_packet"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE115_DIR = LINE_DIR / "outputs" / "stage115_procurement_wave_antiselection_plan"
STAGE115_SUMMARY_IN = (
    STAGE115_DIR
    / "qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan_summary_"
    "stage115_procurement_wave_antiselection_plan_v1.csv"
)
STAGE115_BATCHES_IN = (
    STAGE115_DIR
    / "qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan_wave_batch_assignments_"
    "stage115_procurement_wave_antiselection_plan_v1.csv"
)
STAGE115_INTERVALS_IN = (
    STAGE115_DIR
    / "qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan_wave_request_intervals_"
    "stage115_procurement_wave_antiselection_plan_v1.csv"
)
STAGE115_SUPPLIER_CHECKLIST_IN = (
    STAGE115_DIR
    / "qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan_supplier_checklist_"
    "stage115_procurement_wave_antiselection_plan_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
W0_REQUEST_PACKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_request_packet_{MODEL_TAG}.csv"
W0_BATCH_PACKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_batch_packet_{MODEL_TAG}.csv"
W0_MANIFEST_TEMPLATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_delivery_manifest_template_{MODEL_TAG}.csv"
W0_ACCEPTANCE_TESTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_acceptance_tests_{MODEL_TAG}.csv"
W0_COVERAGE_PROBE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_coverage_probe_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_w0_intake_map_{MODEL_TAG}.png"
REQUEST_DURATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_request_duration_chart_{MODEL_TAG}.png"
SCHEMA_EXCHANGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_schema_exchange_matrix_{MODEL_TAG}.png"
PRODUCT_YEAR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_product_year_heatmap_{MODEL_TAG}.png"

WAVE_ID = "W0_pipeline_smoke"
DECISION = "stage116_wave0_packet_built_no_data_no_rule"


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


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.DataFrame]:
    intervals = _read_csv(STAGE115_INTERVALS_IN)
    batches = _read_csv(STAGE115_BATCHES_IN)
    summary = _read_csv(STAGE115_SUMMARY_IN)
    supplier_checklist = _read_csv(STAGE115_SUPPLIER_CHECKLIST_IN)
    if intervals.empty or batches.empty:
        raise RuntimeError("missing Stage115 wave packet inputs")
    for frame in [intervals, batches]:
        for column in ["request_start", "request_end", "query_start_min", "query_end_max", "trading_day"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return intervals, batches, summary.iloc[0] if not summary.empty else pd.Series(dtype=object), supplier_checklist


def _build_manifest_template(w0_requests: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in w0_requests.iterrows():
        rows.append(
            {
                "wave_id": WAVE_ID,
                "request_id": row["request_id"],
                "batch_id": row["batch_id"],
                "vendor": "",
                "license_id": "",
                "dataset": "",
                "required_schema_request": row["required_schema_request"],
                "schema_delivered": "",
                "exchange": row["exchange"],
                "product": row["product"],
                "vt_symbol": row["vt_symbol"],
                "trading_day": pd.Timestamp(row["trading_day"]).strftime("%Y-%m-%d"),
                "request_start": pd.Timestamp(row["request_start"]).strftime("%Y-%m-%d %H:%M:%S"),
                "request_end": pd.Timestamp(row["request_end"]).strftime("%Y-%m-%d %H:%M:%S"),
                "covered_window_ids": row["covered_window_ids"],
                "raw_file": "",
                "raw_sha256": "",
                "normalized_parquet_file": "",
                "proof_file": "",
                "schema_hash": "",
                "field_dictionary_version": "",
                "ts_event_timezone": "",
                "ts_recv_timezone": "",
                "first_ts_event": "",
                "last_ts_event": "",
                "row_count": "",
                "sequence_gap_count": "",
                "capture_continuity_proof": "",
                "acceptance_status": "pending_delivery",
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_now": 0,
                "notes": "",
            }
        )
    return pd.DataFrame(rows)


def _build_acceptance_tests(w0_requests: pd.DataFrame, w0_batches: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    raw_file_count = int(manifest["raw_file"].astype(str).str.strip().ne("").sum())
    data_file_count = int(manifest["normalized_parquet_file"].astype(str).str.strip().ne("").sum())
    proof_file_count = int(manifest["proof_file"].astype(str).str.strip().ne("").sum())
    hash_count = int(manifest["raw_sha256"].astype(str).str.strip().ne("").sum())
    seq_zero_count = int(
        pd.to_numeric(manifest["sequence_gap_count"], errors="coerce").fillna(-1).eq(0).sum()
    )
    request_count = len(w0_requests)
    tests = [
        {
            "gate_id": "w0_request_packet_nonempty",
            "observed": str(request_count),
            "required": ">0",
            "pass_now": int(request_count > 0),
            "severity": "planning_hard",
        },
        {
            "gate_id": "w0_batch_packet_nonempty",
            "observed": str(len(w0_batches)),
            "required": ">0",
            "pass_now": int(len(w0_batches) > 0),
            "severity": "planning_hard",
        },
        {
            "gate_id": "w0_request_id_unique",
            "observed": f"{w0_requests['request_id'].nunique()}/{request_count}",
            "required": "unique request_id",
            "pass_now": int(w0_requests["request_id"].nunique() == request_count),
            "severity": "planning_hard",
        },
        {
            "gate_id": "w0_strategy_use_locked_zero",
            "observed": "strategy_use_allowed_now=0; rule_preflight_allowed_now=0",
            "required": "0",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "candidate_level_partition_disallowed",
            "observed": "manifest keys are wave/request/batch/product/day/schema",
            "required": "no candidate-level storage partition",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "raw_files_declared",
            "observed": f"{raw_file_count}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(raw_file_count == request_count and request_count > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "normalized_files_declared",
            "observed": f"{data_file_count}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(data_file_count == request_count and request_count > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "proof_files_declared",
            "observed": f"{proof_file_count}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(proof_file_count == request_count and request_count > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "raw_sha256_declared",
            "observed": f"{hash_count}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(hash_count == request_count and request_count > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "sequence_gap_zero_declared",
            "observed": f"{seq_zero_count}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(seq_zero_count == request_count and request_count > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "stage112_intake_allowed",
            "observed": "0",
            "required": "all W0 raw/data/proof gates pass first",
            "pass_now": 0,
            "severity": "data_hard",
        },
    ]
    return pd.DataFrame(tests)


def _build_coverage_probe(w0_requests: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["exchange", "product", "year", "required_schema_request"]
    probe = (
        w0_requests.groupby(group_cols, dropna=False)
        .agg(
            request_count=("request_id", "nunique"),
            symbol_count=("vt_symbol", "nunique"),
            trading_day_count=("trading_day", "nunique"),
            window_count=("window_count", "sum"),
            total_request_hours=("request_seconds", lambda values: float(pd.to_numeric(values, errors="coerce").fillna(0).sum()) / 3600.0),
            visual_priority_count=("visual_priority_count", "sum"),
            right_tail_window_count=("right_tail_window_count", "sum"),
            bottom_loss_window_count=("bottom_loss_window_count", "sum"),
            maxdd_context_window_count=("maxdd_context_window_count", "sum"),
        )
        .reset_index()
    )
    return probe.sort_values(["window_count", "total_request_hours"], ascending=[False, False]).reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _plot_official_path(curve: pd.DataFrame, w0_requests: pd.DataFrame) -> None:
    points = _nearest_curve_points(curve, w0_requests["trading_day"])
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#202939", linewidth=1.2)
    axes[0].scatter(points["date"], points["account_equity"] / 1_000_000, color="#0F766E", s=70, alpha=0.75, label="W0 request days")
    axes[0].set_ylabel("equity (m)")
    axes[0].legend(loc="upper left")
    axes[0].grid(alpha=0.25)

    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#DC2626", linewidth=1.1)
    axes[1].scatter(points["date"], points["drawdown_pct"], color="#0F766E", s=65, alpha=0.75)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)

    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369A1", linewidth=1.0)
    axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"], color="#0F766E", s=65, alpha=0.75)
    axes[2].axhline(100, color="#B91C1C", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    axes[2].grid(alpha=0.25)
    fig.suptitle("Stage116 W0 intake map: pipeline sample only, not a strategy signal")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_request_duration(w0_requests: pd.DataFrame) -> None:
    chart = w0_requests.sort_values("request_seconds", ascending=False).head(20).copy()
    chart["hours"] = pd.to_numeric(chart["request_seconds"], errors="coerce").fillna(0) / 3600.0
    chart["label"] = chart["request_id"] + "\n" + chart["vt_symbol"].astype(str)
    colors = chart["required_schema_request"].map(
        {
            "authorized_mbo_l3_preferred": "#0F766E",
            "authorized_mbp10_l2_minimum": "#A16207",
        }
    ).fillna("#475569")
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.barh(chart["label"], chart["hours"], color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("request hours")
    ax.set_title("Stage116 W0 request duration; operational sizing only")
    ax.grid(axis="x", alpha=0.25)
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    fig.savefig(REQUEST_DURATION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema_exchange(w0_requests: pd.DataFrame) -> None:
    pivot = (
        w0_requests.pivot_table(
            index="exchange",
            columns="required_schema_request",
            values="request_id",
            aggfunc="nunique",
            fill_value=0,
        )
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            ax.text(x, y, int(pivot.iloc[y, x]), ha="center", va="center", color="#111827")
    ax.set_title("Stage116 W0 schema x exchange request count")
    fig.colorbar(image, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(SCHEMA_EXCHANGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year(w0_requests: pd.DataFrame) -> None:
    pivot = (
        w0_requests.pivot_table(index="product", columns="year", values="request_id", aggfunc="nunique", fill_value=0)
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(13, 7))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            value = int(pivot.iloc[y, x])
            if value > 0:
                ax.text(x, y, str(value), ha="center", va="center", color="#F8FAFC", fontsize=9)
    ax.set_title("Stage116 W0 product-year request count")
    fig.colorbar(image, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_CHART_OUT, dpi=160)
    plt.close(fig)


def _build_summary(
    w0_requests: pd.DataFrame,
    w0_batches: pd.DataFrame,
    acceptance_tests: pd.DataFrame,
    stage115_summary: pd.Series,
) -> pd.DataFrame:
    pass_count = int(acceptance_tests["pass_now"].sum())
    gate_count = int(len(acceptance_tests))
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": DECISION,
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "wave_id": WAVE_ID,
        "w0_batch_count": int(len(w0_batches)),
        "w0_request_count": int(len(w0_requests)),
        "w0_window_count": int(pd.to_numeric(w0_requests["window_count"], errors="coerce").fillna(0).sum()),
        "w0_unique_vt_symbol_count": int(w0_requests["vt_symbol"].nunique()),
        "w0_unique_product_count": int(w0_requests["product"].nunique()),
        "w0_unique_exchange_count": int(w0_requests["exchange"].nunique()),
        "w0_unique_year_count": int(w0_requests["year"].nunique()),
        "w0_total_request_hours": float(pd.to_numeric(w0_requests["request_seconds"], errors="coerce").fillna(0).sum() / 3600.0),
        "w0_visual_priority_count": int(pd.to_numeric(w0_requests["visual_priority_count"], errors="coerce").fillna(0).sum()),
        "w0_right_tail_window_count": int(pd.to_numeric(w0_requests["right_tail_window_count"], errors="coerce").fillna(0).sum()),
        "w0_bottom_loss_window_count": int(pd.to_numeric(w0_requests["bottom_loss_window_count"], errors="coerce").fillna(0).sum()),
        "w0_maxdd_context_window_count": int(pd.to_numeric(w0_requests["maxdd_context_window_count"], errors="coerce").fillna(0).sum()),
        "w0_mbo_preferred_request_count": int(w0_requests["required_schema_request"].eq("authorized_mbo_l3_preferred").sum()),
        "w0_mbp10_minimum_request_count": int(w0_requests["required_schema_request"].eq("authorized_mbp10_l2_minimum").sum()),
        "acceptance_gate_count": gate_count,
        "acceptance_gate_pass_count": pass_count,
        "accepted_raw_file_count_now": 0,
        "accepted_data_file_count_now": 0,
        "accepted_proof_file_count_now": 0,
        "accepted_window_coverage_pct_now": 0.0,
        "stage112_intake_allowed_now": 0,
        "next_recommended_route": "deliver_w0_raw_data_then_run_stage112_intake_only_no_strategy",
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "end_equity": float(stage115_summary.get("end_equity", np.nan)),
        "total_return_pct": float(stage115_summary.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage115_summary.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage115_summary.get("sharpe", np.nan)),
        "total_slippage": float(stage115_summary.get("total_slippage", np.nan)),
        "total_trade_count": float(stage115_summary.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage115_summary.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage115_summary.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    return pd.DataFrame([summary])


def _write_report(
    summary: pd.DataFrame,
    w0_batches: pd.DataFrame,
    coverage_probe: pd.DataFrame,
    acceptance_tests: pd.DataFrame,
    supplier_checklist: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    report = f"""# Stage116 W0 pipeline intake packet

## Decision

- decision: `{row['decision']}`
- nature: read-only W0 delivery/intake packet; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.
- question: can W0 be handed to a supplier/data-engineering path with hard anti-selection locks and immediate intake gates?

## Baseline Path

- end equity: `{row['end_equity']:,.2f}`
- total return: `{row['total_return_pct']:.4f}%`
- max drawdown: `{row['max_drawdown_pct']:.4f}%`
- Sharpe: `{row['sharpe']:.4f}`
- total slippage: `{row['total_slippage']:,.0f}`
- total trade count: `{row['total_trade_count']:,.0f}`
- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`

## Summary

{_md_table(summary)}

## W0 Batch Packet

{_md_table(w0_batches[['batch_id', 'year', 'exchange', 'product', 'required_schema_request', 'request_count', 'window_count', 'total_request_seconds', 'strategy_use_allowed_now', 'rule_preflight_allowed_after_wave']])}

## W0 Coverage Probe

{_md_table(coverage_probe, max_rows=30)}

## Acceptance Tests

{_md_table(acceptance_tests)}

## Supplier Checklist

{_md_table(supplier_checklist)}

## Visual Outputs

- official path W0 intake map: `{PATH_CHART_OUT}`
- W0 request duration chart: `{REQUEST_DURATION_CHART_OUT}`
- W0 schema/exchange matrix: `{SCHEMA_EXCHANGE_CHART_OUT}`
- W0 product-year heatmap: `{PRODUCT_YEAR_CHART_OUT}`

## Judgment

W0 is now a concrete delivery packet, but it remains pipeline-only. It can validate license, raw/data/proof layout, schema, timestamp and sequence-continuity fields. It cannot be used for signal research, product/year conclusions, PnL attribution, rule preflight or position sizing. Stage112 intake remains blocked until all W0 raw/data/proof rows are filled and continuity proof is present.
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    intervals, batches, stage115_summary, supplier_checklist = _load_inputs()
    w0_requests = intervals[intervals["wave_id"].eq(WAVE_ID)].copy().reset_index(drop=True)
    w0_batches = batches[batches["wave_id"].eq(WAVE_ID)].copy().reset_index(drop=True)
    if w0_requests.empty or w0_batches.empty:
        raise RuntimeError("W0 packet is empty")

    for column in ["request_seconds", "window_count", "visual_priority_count", "right_tail_window_count", "bottom_loss_window_count", "maxdd_context_window_count"]:
        w0_requests[column] = pd.to_numeric(w0_requests[column], errors="coerce").fillna(0)
    w0_requests["strategy_use_allowed_now"] = 0
    w0_requests["rule_preflight_allowed_now"] = 0

    manifest = _build_manifest_template(w0_requests)
    acceptance_tests = _build_acceptance_tests(w0_requests, w0_batches, manifest)
    coverage_probe = _build_coverage_probe(w0_requests)
    summary = _build_summary(w0_requests, w0_batches, acceptance_tests, stage115_summary)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(w0_requests, W0_REQUEST_PACKET_OUT)
    _write_csv(w0_batches, W0_BATCH_PACKET_OUT)
    _write_csv(manifest, W0_MANIFEST_TEMPLATE_OUT)
    _write_csv(acceptance_tests, W0_ACCEPTANCE_TESTS_OUT)
    _write_csv(coverage_probe, W0_COVERAGE_PROBE_OUT)

    _plot_official_path(curve, w0_requests)
    _plot_request_duration(w0_requests)
    _plot_schema_exchange(w0_requests)
    _plot_product_year(w0_requests)
    _write_report(summary, w0_batches, coverage_probe, acceptance_tests, supplier_checklist)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": DECISION,
        "summary_path": SUMMARY_OUT,
        "w0_request_packet_path": W0_REQUEST_PACKET_OUT,
        "w0_batch_packet_path": W0_BATCH_PACKET_OUT,
        "w0_manifest_template_path": W0_MANIFEST_TEMPLATE_OUT,
        "w0_acceptance_tests_path": W0_ACCEPTANCE_TESTS_OUT,
        "w0_coverage_probe_path": W0_COVERAGE_PROBE_OUT,
        "report_path": REPORT_OUT,
        "charts": [
            PATH_CHART_OUT,
            REQUEST_DURATION_CHART_OUT,
            SCHEMA_EXCHANGE_CHART_OUT,
            PRODUCT_YEAR_CHART_OUT,
        ],
        "stage112_intake_allowed_now": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

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
STAGE = "Stage115"
MODEL_TAG = "stage115_procurement_wave_antiselection_plan_v1"
OUTPUT_PREFIX = "qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage115_procurement_wave_antiselection_plan"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE114_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage114_microstructure_procurement_request_bundle"
    / "qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_summary_"
    "stage114_microstructure_procurement_request_bundle_v1.csv"
)
STAGE114_INTERVALS_IN = (
    LINE_DIR
    / "outputs"
    / "stage114_microstructure_procurement_request_bundle"
    / "qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_request_intervals_"
    "stage114_microstructure_procurement_request_bundle_v1.csv"
)
STAGE114_BATCHES_IN = (
    LINE_DIR
    / "outputs"
    / "stage114_microstructure_procurement_request_bundle"
    / "qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_procurement_batches_"
    "stage114_microstructure_procurement_request_bundle_v1.csv"
)
STAGE114_PRODUCT_YEAR_IN = (
    LINE_DIR
    / "outputs"
    / "stage114_microstructure_procurement_request_bundle"
    / "qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_product_year_matrix_"
    "stage114_microstructure_procurement_request_bundle_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
WAVE_ASSIGNMENT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_wave_batch_assignments_{MODEL_TAG}.csv"
WAVE_INTERVALS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_wave_request_intervals_{MODEL_TAG}.csv"
WAVE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_wave_summary_{MODEL_TAG}.csv"
CUMULATIVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cumulative_plan_{MODEL_TAG}.csv"
ANTI_SELECTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anti_selection_gate_{MODEL_TAG}.csv"
SUPPLIER_CHECKLIST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_supplier_checklist_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_wave_plan_{MODEL_TAG}.png"
WAVE_BAR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_wave_bar_chart_{MODEL_TAG}.png"
CUMULATIVE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cumulative_coverage_chart_{MODEL_TAG}.png"
PRODUCT_YEAR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_wave_heatmap_{MODEL_TAG}.png"

WAVE_META = {
    "W0_pipeline_smoke": {
        "wave_order": 0,
        "purpose": "smallest deterministic cross-section to validate license, raw/data/proof layout, schema, timestamp and sequence proof",
        "allowed_use": "pipeline/schema/provenance validation only",
        "blocked_use": "no signal research, no rule preflight, no PnL attribution, no product/year conclusion",
    },
    "W1_tail_visual_coverage": {
        "wave_order": 1,
        "purpose": "complete high-visual-priority, right-tail, bottom-loss and maxDD-context procurement after the smoke path works",
        "allowed_use": "coverage and visual QA only",
        "blocked_use": "no strategy comparison before W2 and Stage112/113 full pass",
    },
    "W2_full_population": {
        "wave_order": 2,
        "purpose": "complete the remaining required population so later rule preflight cannot be based on a selected subset",
        "allowed_use": "only after Stage112 and Stage113 hard data gates pass",
        "blocked_use": "no automatic promotion; only enables future read-only preflight",
    },
}


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


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    intervals = _read_csv(STAGE114_INTERVALS_IN)
    batches = _read_csv(STAGE114_BATCHES_IN)
    product_year = _read_csv(STAGE114_PRODUCT_YEAR_IN)
    summary = _read_csv(STAGE114_SUMMARY_IN)
    if intervals.empty or batches.empty:
        raise RuntimeError("missing Stage114 procurement inputs")
    for frame in [intervals, batches]:
        for column in ["request_start", "request_end", "query_start_min", "query_end_max"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return intervals, batches, product_year, summary.iloc[0] if not summary.empty else pd.Series(dtype=object)


def _choose_wave0_batches(batches: pd.DataFrame) -> set[str]:
    selected: set[str] = set()
    ranked = batches.sort_values(["priority_score", "window_count"], ascending=[False, False])

    def add_first(frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        selected.add(str(frame.iloc[0]["batch_id"]))

    for _, frame in ranked.groupby("required_schema_request", dropna=False):
        add_first(frame)
    for _, frame in ranked.groupby("exchange", dropna=False):
        add_first(frame)
    for period_name, mask in [
        ("early_2020_2021", ranked["year"].between(2020, 2021)),
        ("maxdd_2022_2023", ranked["year"].between(2022, 2023)),
        ("recent_2024_2026", ranked["year"].between(2024, 2026)),
    ]:
        _ = period_name
        add_first(ranked[mask])
    for _, frame in ranked.groupby("product", dropna=False):
        if len(selected) >= 12:
            break
        add_first(frame)
    return selected


def _assign_waves(batches: pd.DataFrame) -> pd.DataFrame:
    wave0 = _choose_wave0_batches(batches)
    rows = []
    for _, row in batches.iterrows():
        batch_id = str(row["batch_id"])
        tail_or_visual = (
            int(row.get("visual_priority_count", 0))
            + int(row.get("right_tail_window_count", 0))
            + int(row.get("bottom_loss_window_count", 0))
            + int(row.get("maxdd_context_window_count", 0))
        )
        if batch_id in wave0:
            wave_id = "W0_pipeline_smoke"
            assignment_reason = "deterministic diversity sample across schema/exchange/period/product; no strategy use"
        elif tail_or_visual > 0:
            wave_id = "W1_tail_visual_coverage"
            assignment_reason = "visual or tail-risk batch; coverage QA only before full population"
        else:
            wave_id = "W2_full_population"
            assignment_reason = "remaining population required to avoid selected-subset research"
        meta = WAVE_META[wave_id]
        rows.append(
            {
                **row.to_dict(),
                "wave_id": wave_id,
                "wave_order": meta["wave_order"],
                "wave_purpose": meta["purpose"],
                "allowed_use": meta["allowed_use"],
                "blocked_use": meta["blocked_use"],
                "assignment_reason": assignment_reason,
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_after_wave": int(wave_id == "W2_full_population"),
            }
        )
    return pd.DataFrame(rows).sort_values(["wave_order", "priority_score"], ascending=[True, False]).reset_index(drop=True)


def _interval_wave(intervals: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, batch in assignments.iterrows():
        request_ids = [_clean(value) for value in str(batch["request_ids"]).split(";") if _clean(value)]
        for request_id in request_ids:
            rows.append({"request_id": request_id, "batch_id": batch["batch_id"], "wave_id": batch["wave_id"], "wave_order": batch["wave_order"]})
    mapping = pd.DataFrame(rows)
    merged = intervals.merge(mapping, on="request_id", how="left")
    merged["wave_id"] = merged["wave_id"].fillna("W2_full_population")
    merged["wave_order"] = pd.to_numeric(merged["wave_order"], errors="coerce").fillna(2).astype(int)
    return merged.sort_values(["wave_order", "priority_score"], ascending=[True, False]).reset_index(drop=True)


def _wave_summary(assignments: pd.DataFrame, wave_intervals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for wave_id, meta in WAVE_META.items():
        batches = assignments[assignments["wave_id"].eq(wave_id)]
        intervals = wave_intervals[wave_intervals["wave_id"].eq(wave_id)]
        rows.append(
            {
                "wave_id": wave_id,
                "wave_order": meta["wave_order"],
                "purpose": meta["purpose"],
                "allowed_use": meta["allowed_use"],
                "blocked_use": meta["blocked_use"],
                "batch_count": len(batches),
                "request_count": len(intervals),
                "window_count": int(intervals["window_count"].sum()) if not intervals.empty else 0,
                "visual_priority_count": int(intervals["visual_priority_count"].sum()) if not intervals.empty else 0,
                "right_tail_window_count": int(intervals["right_tail_window_count"].sum()) if not intervals.empty else 0,
                "bottom_loss_window_count": int(intervals["bottom_loss_window_count"].sum()) if not intervals.empty else 0,
                "maxdd_context_window_count": int(intervals["maxdd_context_window_count"].sum()) if not intervals.empty else 0,
                "mbo_preferred_request_count": int(intervals["required_schema_request"].eq("authorized_mbo_l3_preferred").sum()) if not intervals.empty else 0,
                "mbp10_minimum_request_count": int(intervals["required_schema_request"].eq("authorized_mbp10_l2_minimum").sum()) if not intervals.empty else 0,
                "unique_product_count": int(intervals["product"].nunique()) if not intervals.empty else 0,
                "unique_exchange_count": int(intervals["exchange"].nunique()) if not intervals.empty else 0,
                "unique_year_count": int(intervals["year"].nunique()) if not intervals.empty else 0,
                "total_request_hours": float(intervals["request_seconds"].sum() / 3600.0) if not intervals.empty else 0.0,
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_after_wave": int(wave_id == "W2_full_population"),
            }
        )
    return pd.DataFrame(rows).sort_values("wave_order").reset_index(drop=True)


def _cumulative_plan(wave_summary: pd.DataFrame, total_windows: int) -> pd.DataFrame:
    rows = []
    cumulative = {
        "batch_count": 0,
        "request_count": 0,
        "window_count": 0,
        "visual_priority_count": 0,
        "right_tail_window_count": 0,
        "bottom_loss_window_count": 0,
        "maxdd_context_window_count": 0,
        "total_request_hours": 0.0,
    }
    for _, row in wave_summary.sort_values("wave_order").iterrows():
        for key in cumulative:
            cumulative[key] += row[key]
        rows.append(
            {
                "through_wave_id": row["wave_id"],
                "through_wave_order": int(row["wave_order"]),
                **cumulative,
                "planned_window_coverage_pct": float(cumulative["window_count"] / total_windows * 100.0) if total_windows else 0.0,
                "accepted_window_count_now": 0,
                "accepted_window_coverage_pct_now": 0.0,
                "rule_preflight_allowed_now": 0,
                "rule_preflight_allowed_if_all_data_arrives_and_stage112_113_pass": int(cumulative["window_count"] == total_windows),
            }
        )
    return pd.DataFrame(rows)


def _anti_selection_gate(assignments: pd.DataFrame, cumulative: pd.DataFrame, total_windows: int) -> pd.DataFrame:
    mapped = int(assignments["window_count"].sum())
    rows = [
        {
            "gate_id": "all_stage114_windows_assigned_to_waves",
            "observed": f"{mapped}/{total_windows}",
            "required": f"{total_windows}/{total_windows}",
            "pass_now": int(mapped == total_windows),
            "severity": "planning_hard",
        },
        {
            "gate_id": "wave0_pipeline_only_no_strategy",
            "observed": "strategy_use_allowed_now=0",
            "required": "0",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "wave1_tail_visual_only_no_strategy",
            "observed": "strategy_use_allowed_now=0",
            "required": "0",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "priority_queue_not_trading_signal",
            "observed": "documented",
            "required": "priority only controls procurement order",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "full_population_required_before_preflight",
            "observed": str(int(cumulative.iloc[-1]["rule_preflight_allowed_if_all_data_arrives_and_stage112_113_pass"]) if not cumulative.empty else 0),
            "required": "only after all waves and Stage112/113 hard gates pass",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "authorized_data_delivered",
            "observed": "0",
            "required": "raw/data/proof files delivered",
            "pass_now": 0,
            "severity": "data_hard",
        },
        {
            "gate_id": "stage112_stage113_acceptance_passed",
            "observed": "0",
            "required": "Stage112 and Stage113 hard data gates pass",
            "pass_now": 0,
            "severity": "data_hard",
        },
    ]
    return pd.DataFrame(rows)


def _supplier_checklist() -> pd.DataFrame:
    rows = [
        ("license", "written authorization for research/backtest use", "must cover raw archive and derived parquet", 1),
        ("schema", "MBO/L3 or MBP-10/L2 event schema", "L1-only delivery remains TCA/forward-watch only", 1),
        ("timestamps", "ts_event and ts_recv or exchange/receive equivalents", "timezone and calendar must be declared", 1),
        ("continuity", "sequence_gap_count or equivalent capture continuity proof", "gap count must be zero for accepted windows", 1),
        ("raw_provenance", "raw_file and raw_sha256", "do not overwrite or normalize away original payload", 1),
        ("schema_provenance", "schema_hash and field dictionary/version", "needed before binding features", 1),
        ("coverage", "covered_window_ids from Stage113", "all 485 windows before any rule preflight", 1),
        ("delivery", "raw/data/proof layout matching Stage114 storage plan", "candidate-level tiny files are disallowed", 0),
        ("anti_selection", "wave delivery labels preserved", "Wave0/Wave1 cannot be used for strategy research", 1),
    ]
    return pd.DataFrame(rows, columns=["check_group", "requirement", "acceptance_rule", "hard_gate"])


def _summary(assignments: pd.DataFrame, wave_summary: pd.DataFrame, cumulative: pd.DataFrame, gate: pd.DataFrame, stage114: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage115_procurement_waves_built_no_data_no_rule",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "total_batch_count": int(len(assignments)),
                "total_request_count": int(wave_summary["request_count"].sum()),
                "total_window_count": int(wave_summary["window_count"].sum()),
                "wave_count": int(len(wave_summary)),
                "wave0_batch_count": int(wave_summary.loc[wave_summary["wave_id"].eq("W0_pipeline_smoke"), "batch_count"].sum()),
                "wave1_batch_count": int(wave_summary.loc[wave_summary["wave_id"].eq("W1_tail_visual_coverage"), "batch_count"].sum()),
                "wave2_batch_count": int(wave_summary.loc[wave_summary["wave_id"].eq("W2_full_population"), "batch_count"].sum()),
                "wave0_window_count": int(wave_summary.loc[wave_summary["wave_id"].eq("W0_pipeline_smoke"), "window_count"].sum()),
                "wave1_window_count": int(wave_summary.loc[wave_summary["wave_id"].eq("W1_tail_visual_coverage"), "window_count"].sum()),
                "wave2_window_count": int(wave_summary.loc[wave_summary["wave_id"].eq("W2_full_population"), "window_count"].sum()),
                "planned_full_window_coverage_pct": float(cumulative.iloc[-1]["planned_window_coverage_pct"]) if not cumulative.empty else 0.0,
                "accepted_window_coverage_pct_now": 0.0,
                "anti_selection_gate_count": int(len(gate)),
                "anti_selection_gate_pass_count": int(gate["pass_now"].sum()) if not gate.empty else 0,
                "next_recommended_route": "deliver_wave0_for_pipeline_only_then_stage112_113_acceptance_no_strategy_until_all_waves_pass",
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(stage114.get("end_equity", 0) or 0),
                "total_return_pct": float(stage114.get("total_return_pct", 0) or 0),
                "max_drawdown_pct": float(stage114.get("max_drawdown_pct", 0) or 0),
                "sharpe": float(stage114.get("sharpe", 0) or 0),
                "total_slippage": float(stage114.get("total_slippage", 0) or 0),
                "total_trade_count": float(stage114.get("total_trade_count", 0) or 0),
                "closed_lot_win_rate_pct": float(stage114.get("closed_lot_win_rate_pct", 0) or 0),
                "max_broker10_margin_to_equity_pct": float(stage114.get("max_broker10_margin_to_equity_pct", 0) or 0),
            }
        ]
    )


def _plot_path(curve: pd.DataFrame, wave_intervals: pd.DataFrame) -> None:
    by_day = (
        wave_intervals.groupby(["trading_day", "wave_id", "wave_order"], as_index=False)
        .agg(priority_score=("priority_score", "sum"), request_count=("request_id", "count"))
        .sort_values(["trading_day", "wave_order"])
    )
    by_day["trading_day"] = pd.to_datetime(by_day["trading_day"], errors="coerce")
    points = _nearest_curve_points(curve, by_day["trading_day"]).reset_index(drop=True)
    if len(by_day) == len(points):
        by_day = pd.concat([by_day.reset_index(drop=True), points[["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]]], axis=1)
    colors = {"W0_pipeline_smoke": "#0f766e", "W1_tail_visual_coverage": "#dc2626", "W2_full_population": "#64748b"}
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#111827", lw=1.2)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.0)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8)
    for wave_id, group in by_day.groupby("wave_id"):
        sizes = 18 + np.sqrt(group["priority_score"].clip(lower=1)) * 3
        for ax, column, scale in [
            (axes[0], "account_equity", 1_000_000),
            (axes[1], "drawdown_pct", 1),
            (axes[2], "broker10_margin_to_equity_pct", 1),
        ]:
            ax.scatter(
                group["trading_day"],
                group[column] / scale,
                s=sizes,
                c=colors.get(wave_id, "#64748b"),
                edgecolors="#111827",
                linewidths=0.35,
                alpha=0.72,
                label=wave_id if ax is axes[0] else None,
            )
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].set_title("Stage115 official path: procurement waves are data-ordering only, not strategy signals")
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_wave_bar(wave_summary: pd.DataFrame) -> None:
    data = wave_summary.sort_values("wave_order")
    x = np.arange(len(data))
    fig, ax1 = plt.subplots(figsize=(12, 5.5))
    ax1.bar(x - 0.22, data["batch_count"], width=0.22, color="#64748b", label="batches")
    ax1.bar(x, data["request_count"], width=0.22, color="#0369a1", label="requests")
    ax1.bar(x + 0.22, data["window_count"], width=0.22, color="#dc2626", label="windows")
    ax1.set_xticks(x)
    ax1.set_xticklabels(data["wave_id"], rotation=12, ha="right")
    ax1.set_ylabel("count")
    ax1.set_title("Stage115 wave scope; all waves are required before any rule preflight")
    ax1.legend(fontsize=8)
    ax1.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(WAVE_BAR_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_cumulative(cumulative: pd.DataFrame) -> None:
    data = cumulative.sort_values("through_wave_order")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(data["through_wave_id"], data["planned_window_coverage_pct"], marker="o", color="#0369a1", label="planned if delivered")
    ax.plot(data["through_wave_id"], data["accepted_window_coverage_pct_now"], marker="o", color="#dc2626", label="accepted now")
    ax.axhline(100, color="#111827", ls="--", lw=0.8)
    ax.set_ylim(0, 105)
    ax.set_ylabel("window coverage %")
    ax.set_title("Stage115 planned vs accepted cumulative coverage")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CUMULATIVE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year_wave(wave_intervals: pd.DataFrame) -> None:
    data = wave_intervals.copy()
    data["product_exchange"] = data["product"].astype(str) + "." + data["exchange"].astype(str)
    pivot = data.pivot_table(index="product_exchange", columns="year", values="wave_order", aggfunc="min", fill_value=np.nan)
    pivot = pivot.loc[pivot.notna().sum(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(12, max(5.5, 0.28 * len(pivot))))
    masked = np.ma.masked_invalid(pivot.to_numpy(dtype=float))
    im = ax.imshow(masked, aspect="auto", cmap="viridis_r", vmin=0, vmax=2)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(col) for col in pivot.columns])
    ax.set_title("Stage115 earliest procurement wave by product-year")
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            value = pivot.iloc[y, x]
            if pd.notna(value):
                ax.text(x, y, f"W{int(value)}", ha="center", va="center", color="#111827", fontsize=7)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, wave_summary: pd.DataFrame, cumulative: pd.DataFrame, gate: pd.DataFrame, checklist: pd.DataFrame) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage115 procurement wave anti-selection plan",
        "",
        "## Decision",
        "",
        f"- decision: `{row['decision']}`",
        "- nature: read-only procurement wave plan; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.",
        "- question: can the Stage114 request bundle be delivered in practical waves without allowing cherry-picking or premature rule research?",
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
        "## Wave Summary",
        "",
        _md_table(wave_summary, max_rows=10),
        "",
        "## Cumulative Plan",
        "",
        _md_table(cumulative, max_rows=10),
        "",
        "## Anti-Selection Gates",
        "",
        _md_table(gate, max_rows=20),
        "",
        "## Supplier Checklist",
        "",
        _md_table(checklist, max_rows=20),
        "",
        "## Visual Outputs",
        "",
        f"- official path wave plan: `{PATH_CHART_OUT}`",
        f"- wave bar chart: `{WAVE_BAR_CHART_OUT}`",
        f"- cumulative coverage chart: `{CUMULATIVE_CHART_OUT}`",
        f"- product-year wave heatmap: `{PRODUCT_YEAR_CHART_OUT}`",
        "",
        "## External Research Judgment",
        "",
        (
            "Limited or non-representative data can create selection and sampling bias. Stage115 therefore separates "
            "delivery order from research permission: early waves can validate data plumbing, but cannot be used for "
            "strategy conclusions. Partitioning is kept product/day-oriented to avoid candidate-level small-file bias and operational overhead."
        ),
        "",
        "## Judgment",
        "",
        (
            "Wave delivery is now practical, but the line remains data-blocked for strategy work. W0/W1 are explicitly "
            "not research samples. Only a full W2 population plus Stage112/113 hard-gate pass can unlock future read-only preflight."
        ),
        "",
    ]
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    intervals, batches, product_year, stage114 = _load_inputs()
    assignments = _assign_waves(batches)
    wave_intervals = _interval_wave(intervals, assignments)
    wave_summary = _wave_summary(assignments, wave_intervals)
    cumulative = _cumulative_plan(wave_summary, int(stage114.get("required_window_count", 485) or 485))
    gate = _anti_selection_gate(assignments, cumulative, int(stage114.get("required_window_count", 485) or 485))
    checklist = _supplier_checklist()
    summary = _summary(assignments, wave_summary, cumulative, gate, stage114)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(assignments, WAVE_ASSIGNMENT_OUT)
    _write_csv(wave_intervals, WAVE_INTERVALS_OUT)
    _write_csv(wave_summary, WAVE_SUMMARY_OUT)
    _write_csv(cumulative, CUMULATIVE_OUT)
    _write_csv(gate, ANTI_SELECTION_GATE_OUT)
    _write_csv(checklist, SUPPLIER_CHECKLIST_OUT)

    _plot_path(curve, wave_intervals)
    _plot_wave_bar(wave_summary)
    _plot_cumulative(cumulative)
    _plot_product_year_wave(wave_intervals)
    _write_report(summary, wave_summary, cumulative, gate, checklist)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "wave_assignment_path": str(WAVE_ASSIGNMENT_OUT),
        "wave_intervals_path": str(WAVE_INTERVALS_OUT),
        "wave_summary_path": str(WAVE_SUMMARY_OUT),
        "cumulative_plan_path": str(CUMULATIVE_OUT),
        "anti_selection_gate_path": str(ANTI_SELECTION_GATE_OUT),
        "supplier_checklist_path": str(SUPPLIER_CHECKLIST_OUT),
        "charts": [str(PATH_CHART_OUT), str(WAVE_BAR_CHART_OUT), str(CUMULATIVE_CHART_OUT), str(PRODUCT_YEAR_CHART_OUT)],
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

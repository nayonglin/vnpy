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
STAGE = "Stage149"
MODEL_TAG = "stage149_predeclared_replay_hypothesis_spec_v1"
OUTPUT_PREFIX = "qmt_roll_stage149_c9_minrisk_predeclared_replay_hypothesis_spec"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage149_predeclared_replay_hypothesis_spec"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE045_LEDGER_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_event_sync_ledger_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE102_ROWS_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_resolution_rows_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)
STAGE148_DIR = LINE_DIR / "outputs" / "stage148_objective_gap_route_audit"
STAGE148_PREFIX = "qmt_roll_stage148_c9_minrisk_objective_gap_route_audit"
STAGE148_TAG = "stage148_objective_gap_route_audit_v1"
STAGE148_SUMMARY_IN = STAGE148_DIR / f"{STAGE148_PREFIX}_summary_{STAGE148_TAG}.csv"
STAGE148_REQUIREMENT_IN = STAGE148_DIR / f"{STAGE148_PREFIX}_objective_requirement_gap_{STAGE148_TAG}.csv"
STAGE148_ROUTE_IN = STAGE148_DIR / f"{STAGE148_PREFIX}_route_scorecard_{STAGE148_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SPEC_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_hypothesis_spec_{MODEL_TAG}.csv"
COLLISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_route_collision_{MODEL_TAG}.csv"
EVIDENCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_requirements_{MODEL_TAG}.csv"
CONTEXT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sample_context_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_spec_status_{MODEL_TAG}.png"
COLLISION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_route_collision_matrix_{MODEL_TAG}.png"
EVIDENCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_requirement_matrix_{MODEL_TAG}.png"
CONTEXT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sample_context_matrix_{MODEL_TAG}.png"
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


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _hypothesis_spec() -> pd.DataFrame:
    rows = [
        {
            "spec_id": "H3_event_maturity_continuation_predeclared_spec",
            "field": "hypothesis",
            "value": (
                "A future minute overlay may only reduce risk or restore risk when independent, "
                "point-in-time evidence shows a mature continuation state with enough actionable lead time."
            ),
            "current_status": "predeclared_spec_only",
            "allowed_now": 1,
        },
        {
            "spec_id": "H3_event_maturity_continuation_predeclared_spec",
            "field": "first_principle",
            "value": (
                "Trend following survives by preserving right-tail convexity; a minute overlay must remove "
                "low-quality exposure without cutting the structural winners."
            ),
            "current_status": "principle_locked",
            "allowed_now": 1,
        },
        {
            "spec_id": "H3_event_maturity_continuation_predeclared_spec",
            "field": "observable_universe",
            "value": "Stage045 timestamp_ready=1 calibrated replay subset; fallback/no-proxy samples keep official path.",
            "current_status": "bounded",
            "allowed_now": 1,
        },
        {
            "spec_id": "H3_event_maturity_continuation_predeclared_spec",
            "field": "noncausal_warning",
            "value": (
                "Stage045/102 replay event family is a research label, not an entry-time signal; it cannot "
                "be used directly as a trade condition."
            ),
            "current_status": "hard_lock",
            "allowed_now": 1,
        },
        {
            "spec_id": "H3_event_maturity_continuation_predeclared_spec",
            "field": "forbidden_inputs",
            "value": (
                "final PnL, maxDD labels, residual mismatches, no-follow, opening-range hard exit, default "
                "minimum-risk restore, breakeven, absorption/reclaim, near-touch OHLC, far-from-touch, "
                "Tq topbook transforms, account-vol/fixed-capital overlays"
            ),
            "current_status": "hard_lock",
            "allowed_now": 1,
        },
        {
            "spec_id": "H3_event_maturity_continuation_predeclared_spec",
            "field": "rule_entry_barrier",
            "value": (
                "Before any true engine run, prove same-source or authorized minute/quote/orderflow data, "
                "lead-time actionability, right-tail protection, LOYO, monthly-start and product-family stability."
            ),
            "current_status": "not_satisfied",
            "allowed_now": 0,
        },
        {
            "spec_id": "H3_event_maturity_continuation_predeclared_spec",
            "field": "decision_lock",
            "value": "This stage creates no strategy rule, no feature package, no true-engine candidate, no A/B trigger.",
            "current_status": "hard_lock",
            "allowed_now": 1,
        },
    ]
    return pd.DataFrame(rows)


def _closed_route_collision() -> pd.DataFrame:
    route_rows = [
        ("no_follow_30m", "post-entry no-follow/reduce/exit/restore family", 0),
        ("opening_range_adverse_exit", "first minutes adverse break hard exit", 0),
        ("default_minrisk_restore", "default minimum risk then restore on clean path", 0),
        ("confirmed_breakeven_exit", "confirmed then entry-price or breakeven stop", 0),
        ("absorption_reclaim", "adverse touch then reclaim/no-reclaim state", 0),
        ("near_touch_minute_ohlc", "close/next-bar rule around C9 stop/progress touch", 0),
        ("far_from_touch_no_event", "far-from-touch or day-end no event proxy", 0),
        ("tq_topbook_transform", "existing Tq topbook/tick transform route", 0),
        ("maxdd_or_final_pnl_label", "labels derived from final loss or maxDD episode", 0),
        ("account_vol_fixed_capital", "account-vol, CPPI/TIPP, fixed-capital overlay", 0),
        ("oi_member_warehouse_state", "closed external cache or readiness/missingness state", 0),
    ]
    return pd.DataFrame(
        [
            {
                "closed_route_id": route_id,
                "closed_route_shape": shape,
                "collision_flag": collision,
                "distinct_from_spec": int(collision == 0),
                "comment": "Spec forbids this input/shape; no parameter rescue is allowed.",
            }
            for route_id, shape, collision in route_rows
        ]
    )


def _evidence_requirements() -> pd.DataFrame:
    rows = [
        ("stage045_replay_subset_defined", "Stage045 calibrated replay subset is available for context only.", 1, "Stage045"),
        ("fallback_no_proxy_kept_official", "Fallback/no-proxy samples are not forced into a minute rule.", 1, "Stage040-045"),
        ("no_final_pnl_or_maxdd_label", "Spec forbids final PnL and maxDD-derived labels.", 1, "Stage149"),
        ("no_closed_route_feature", "Spec does not reuse closed route features.", 1, "Stage149"),
        ("same_source_or_authorized_minute_k_ready", "Same-source or authorized minute/quote/orderflow data is ready.", 0, "Stage103-148"),
        ("lead_time_actionability_verified", "Candidate has actionable lead time before any order change.", 0, "Stage101/102/149"),
        ("right_tail_bottom_loss_atlas_ready", "Right-tail and bottom-loss visual atlas exists for this hypothesis.", 0, "Stage149 future"),
        ("walkforward_loyo_ready", "Leave-one-year-out or equivalent OOS evidence exists.", 0, "Stage149 future"),
        ("monthly_start_ready", "Monthly cold-start evidence exists.", 0, "Stage149 future"),
        ("product_family_ready", "Cross-product-family stability is proven.", 0, "Stage149 future"),
        ("stage145_package_ready", "A real candidate package can pass Stage145 before Stage142/143.", 0, "Stage145 future"),
    ]
    return pd.DataFrame(
        [
            {
                "evidence_id": evidence_id,
                "requirement": requirement,
                "ready_now": ready,
                "evidence_stage": stage,
                "blocking_rule_entry": int(ready == 0),
            }
            for evidence_id, requirement, ready, stage in rows
        ]
    )


def _sample_context(ledger: pd.DataFrame, rows102: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        raise RuntimeError(f"missing ledger input: {STAGE045_LEDGER_IN}")
    if rows102.empty:
        raise RuntimeError(f"missing Stage102 input: {STAGE102_ROWS_IN}")

    rows = []
    family_counts = (
        ledger.assign(
            context_group=ledger["replay_event_family"].fillna("missing"),
            order_count=1,
        )
        .groupby("context_group", dropna=False)
        .agg(order_count=("order_count", "sum"), full_sync_rate=("full_event_sync_exact", "mean"))
        .reset_index()
    )
    for _, row in family_counts.iterrows():
        rows.append(
            {
                "context_type": "stage045_replay_event_family",
                "context_group": row["context_group"],
                "order_count": int(row["order_count"]),
                "pnl_sum": np.nan,
                "right_tail_count": np.nan,
                "bottom_loss_count": np.nan,
                "full_sync_rate": float(row["full_sync_rate"]),
                "rule_interpretation_allowed": 0,
            }
        )

    useful_cols = ["resolution_bucket", "replay_event_family"]
    for col in useful_cols:
        if col not in rows102.columns:
            rows102[col] = "missing"
    for col in ["order_realized_pnl", "right_tail_visual", "bottom_loss_visual"]:
        if col in rows102.columns:
            rows102[col] = pd.to_numeric(rows102[col], errors="coerce").fillna(0)
        else:
            rows102[col] = 0
    resolution_counts = (
        rows102.assign(
            context_group=rows102["resolution_bucket"].fillna("missing"),
            order_count=1,
        )
        .groupby("context_group", dropna=False)
        .agg(
            order_count=("order_count", "sum"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
        )
        .reset_index()
    )
    for _, row in resolution_counts.iterrows():
        rows.append(
            {
                "context_type": "stage102_resolution_bucket",
                "context_group": row["context_group"],
                "order_count": int(row["order_count"]),
                "pnl_sum": float(row["pnl_sum"]),
                "right_tail_count": int(row["right_tail_count"]),
                "bottom_loss_count": int(row["bottom_loss_count"]),
                "full_sync_rate": np.nan,
                "rule_interpretation_allowed": 0,
            }
        )

    product_counts = (
        rows102.assign(context_group=rows102.get("product", pd.Series("missing", index=rows102.index)).fillna("missing"))
        .groupby("context_group", dropna=False)
        .agg(
            order_count=("official_open_trade_id", "count"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
        )
        .reset_index()
        .sort_values(["right_tail_count", "bottom_loss_count", "order_count"], ascending=[False, False, False])
        .head(12)
    )
    for _, row in product_counts.iterrows():
        rows.append(
            {
                "context_type": "top_product_context_not_rule",
                "context_group": row["context_group"],
                "order_count": int(row["order_count"]),
                "pnl_sum": float(row["pnl_sum"]),
                "right_tail_count": int(row["right_tail_count"]),
                "bottom_loss_count": int(row["bottom_loss_count"]),
                "full_sync_rate": np.nan,
                "rule_interpretation_allowed": 0,
            }
        )
    return pd.DataFrame(rows)


def _gate_status(summary: pd.DataFrame, collision: pd.DataFrame, evidence: pd.DataFrame) -> pd.DataFrame:
    row = summary.iloc[0].to_dict()
    rows = [
        ("spec_written", _int(row, "hypothesis_spec_ready"), 1, "contract_hard"),
        ("no_closed_route_collision", int(collision["collision_flag"].sum()), 0, "anti_rescue_hard"),
        ("same_source_data_blocks_rule", _int(row, "same_source_or_authorized_data_ready"), 0, "data_hard"),
        ("no_true_engine_or_ab", _int(row, "true_engine_run") + _int(row, "ab_triggered"), 0, "execution_hard"),
        ("no_official_or_order_side_effect", _int(row, "side_effect_count"), 0, "execution_hard"),
        ("rule_entry_blocked_until_evidence", _int(row, "preflight_rule_allowed"), 0, "anti_overclaim_hard"),
        ("evidence_gaps_remain", int((evidence["ready_now"] == 0).sum()), 1, "reality_check_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": observed,
                "required": required,
                "pass_now": int(observed == required if gate_id != "evidence_gaps_remain" else observed >= required),
                "severity": severity,
            }
            for gate_id, observed, required, severity in rows
        ]
    )


def _write_report(
    summary: pd.DataFrame,
    spec: pd.DataFrame,
    collision: pd.DataFrame,
    evidence: pd.DataFrame,
    context: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} 预声明 replay 假设规格",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只写假设与证据合同，不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- Moskowitz/Ooi/Pedersen 的 time-series momentum 证据支持跨资产、跨周期的持续趋势效应，但不支持从单段分钟亏损残差反推规则。",
        "- Hurst/Ooi/Pedersen 的百年趋势跟随证据强调长期稳健性和危机凸性，因此分钟 overlay 必须先证明不砍右尾。",
        "- GitHub 上的 PyTrendFollow、MLM trend-following 等开源系统多是日线/组合层框架，不能解决本线同源分钟 K 或盘口执行证据缺口。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Hypothesis Spec",
        "",
        _md_table(spec),
        "",
        "## Closed Route Collision",
        "",
        _md_table(collision),
        "",
        "## Evidence Requirements",
        "",
        _md_table(evidence),
        "",
        "## Sample Context",
        "",
        _md_table(context, max_rows=40),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{COLLISION_CHART_OUT.name}`",
        f"- `{EVIDENCE_CHART_OUT.name}`",
        f"- `{CONTEXT_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage149 predeclared hypothesis spec on official path", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    labels = ["spec", "collision", "evidence_ready", "rule_allowed", "side_effect"]
    values = [
        row["hypothesis_spec_ready"],
        row["closed_route_collision_count"],
        row["evidence_ready_count"],
        row["preflight_rule_allowed"],
        row["side_effect_count"],
    ]
    colors = ["#0F766E", "#B91C1C", "#3657D6", "#B45309", "#B91C1C"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("Spec status, not a strategy candidate")
    axes[3].set_ylabel("count / flag")
    axes[3].tick_params(axis="x", labelrotation=20)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_matrix(frame: pd.DataFrame, index_col: str, value_cols: list[str], title: str, path: Path) -> None:
    matrix = frame.set_index(index_col)[value_cols].copy()
    for column in value_cols:
        matrix[column] = pd.to_numeric(matrix[column], errors="coerce").fillna(0).clip(upper=1)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.45), max(4.8, len(matrix) * 0.56)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(value_cols)))
    ax.set_xticklabels(value_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _plot_context(context: pd.DataFrame) -> None:
    plot_frame = context.head(30).copy()
    plot_frame["label"] = plot_frame["context_type"].str.replace("_", " ") + ": " + plot_frame["context_group"].astype(str)
    fig, ax = plt.subplots(figsize=(13, max(6, len(plot_frame) * 0.32)))
    colors = ["#3657D6" if item.startswith("stage045") else "#0F766E" if item.startswith("stage102") else "#B45309" for item in plot_frame["context_type"]]
    ax.barh(plot_frame["label"], plot_frame["order_count"], color=colors)
    ax.set_title("Stage149 sample context only; no rule interpretation")
    ax.set_xlabel("order count")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CONTEXT_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    curve = _load_curve()
    ledger = _read_csv(STAGE045_LEDGER_IN)
    rows102 = _read_csv(STAGE102_ROWS_IN)
    stage148 = _read_csv(STAGE148_SUMMARY_IN)
    if stage148.empty:
        raise RuntimeError(f"missing Stage148 summary input: {STAGE148_SUMMARY_IN}")
    stage148_row = stage148.iloc[0].to_dict()

    spec = _hypothesis_spec()
    collision = _closed_route_collision()
    evidence = _evidence_requirements()
    context = _sample_context(ledger, rows102)

    side_effect_count = 0
    closed_collision_count = int(pd.to_numeric(collision["collision_flag"], errors="coerce").fillna(0).sum())
    evidence_ready_count = int(pd.to_numeric(evidence["ready_now"], errors="coerce").fillna(0).sum())
    evidence_missing_count = int((pd.to_numeric(evidence["ready_now"], errors="coerce").fillna(0) == 0).sum())
    same_source_ready = int(
        evidence.loc[evidence["evidence_id"] == "same_source_or_authorized_minute_k_ready", "ready_now"].iloc[0]
    )
    preflight_rule_allowed = 0
    decision = "stage149_predeclared_replay_hypothesis_spec_ready_no_rule"
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "next_best_action": "stage150_readonly_feasibility_or_wait_real_w0",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "true_engine_run_count": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "side_effect_count": side_effect_count,
                "hypothesis_spec_ready": 1,
                "closed_route_collision_count": closed_collision_count,
                "evidence_requirement_count": len(evidence),
                "evidence_ready_count": evidence_ready_count,
                "evidence_missing_count": evidence_missing_count,
                "same_source_or_authorized_data_ready": same_source_ready,
                "stage045_replay_order_count": int(len(ledger)),
                "stage102_context_order_count": int(len(rows102)),
                "sample_context_row_count": int(len(context)),
                "preflight_rule_allowed": preflight_rule_allowed,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "current_package_promotion_allowed": 0,
                "objective_completion_proven": 0,
                "end_equity": float(stage148_row.get("end_equity", np.nan)),
                "total_return_pct": float(stage148_row.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(stage148_row.get("max_drawdown_pct", np.nan)),
                "sharpe": float(stage148_row.get("sharpe", np.nan)),
                "total_slippage": float(stage148_row.get("total_slippage", np.nan)),
                "total_trade_count": float(stage148_row.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(stage148_row.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(
                    stage148_row.get("max_broker10_margin_to_equity_pct", np.nan)
                ),
            }
        ]
    )
    gate = _gate_status(summary, collision, evidence)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(spec, SPEC_OUT)
    _write_csv(collision, COLLISION_OUT)
    _write_csv(evidence, EVIDENCE_OUT)
    _write_csv(context, CONTEXT_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, spec, collision, evidence, context, gate)
    _plot_path(curve, summary)
    _plot_matrix(collision, "closed_route_id", ["collision_flag", "distinct_from_spec"], "Stage149 closed route collision", COLLISION_CHART_OUT)
    _plot_matrix(evidence, "evidence_id", ["ready_now", "blocking_rule_entry"], "Stage149 evidence requirements", EVIDENCE_CHART_OUT)
    _plot_context(context)
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage149 gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "curve": str(CURVE_IN),
                "stage045_ledger": str(STAGE045_LEDGER_IN),
                "stage102_rows": str(STAGE102_ROWS_IN),
                "stage148_summary": str(STAGE148_SUMMARY_IN),
                "stage148_requirement": str(STAGE148_REQUIREMENT_IN),
                "stage148_route": str(STAGE148_ROUTE_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "hypothesis_spec": str(SPEC_OUT),
                "closed_route_collision": str(COLLISION_OUT),
                "evidence_requirements": str(EVIDENCE_OUT),
                "sample_context": str(CONTEXT_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(COLLISION_CHART_OUT),
                    str(EVIDENCE_CHART_OUT),
                    str(CONTEXT_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "preflight_rule_allowed": 0,
                "current_package_promotion_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

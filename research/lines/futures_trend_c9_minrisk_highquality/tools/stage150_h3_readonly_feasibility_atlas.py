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
STAGE = "Stage150"
MODEL_TAG = "stage150_h3_readonly_feasibility_atlas_v1"
OUTPUT_PREFIX = "qmt_roll_stage150_c9_minrisk_h3_readonly_feasibility_atlas"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage150_h3_readonly_feasibility_atlas"

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
STAGE149_DIR = LINE_DIR / "outputs" / "stage149_predeclared_replay_hypothesis_spec"
STAGE149_PREFIX = "qmt_roll_stage149_c9_minrisk_predeclared_replay_hypothesis_spec"
STAGE149_TAG = "stage149_predeclared_replay_hypothesis_spec_v1"
STAGE149_SUMMARY_IN = STAGE149_DIR / f"{STAGE149_PREFIX}_summary_{STAGE149_TAG}.csv"
STAGE149_SPEC_IN = STAGE149_DIR / f"{STAGE149_PREFIX}_hypothesis_spec_{STAGE149_TAG}.csv"
STAGE149_EVIDENCE_IN = STAGE149_DIR / f"{STAGE149_PREFIX}_evidence_requirements_{STAGE149_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVIDENCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feasibility_evidence_{MODEL_TAG}.csv"
ROUTE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocked_feature_routes_{MODEL_TAG}.csv"
TAIL_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_conflict_matrix_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_r_path_summary_atlas_manifest_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_h3_status_{MODEL_TAG}.png"
EVIDENCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feasibility_evidence_matrix_{MODEL_TAG}.png"
TAIL_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_conflict_heatmap_{MODEL_TAG}.png"
LEADTIME_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leadtime_runway_distribution_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_r_path_summary_atlas_page{{page:03d}}_{MODEL_TAG}.png"

ATLAS_ROWS = 24
ATLAS_PER_PAGE = 6


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


def _prepare_rows(rows102: pd.DataFrame) -> pd.DataFrame:
    if rows102.empty:
        raise RuntimeError(f"missing Stage102 rows input: {STAGE102_ROWS_IN}")
    rows = rows102.copy()
    rows["official_open_date"] = pd.to_datetime(rows["official_open_date"], errors="coerce").dt.normalize()
    numeric_cols = [
        "order_realized_pnl",
        "right_tail_visual",
        "bottom_loss_visual",
        "maxdd_context",
        "completed_bars_before_event",
        "minutes_from_open_to_event",
        "pre_event_mfe_r",
        "pre_event_mae_r",
        "pre_event_close_r",
        "event_bar_high_r",
        "event_bar_low_r",
        "event_bar_close_r",
        "low_resolution_zone",
        "same_bar_stop_progress_ambiguous",
        "first_bar_event",
        "close_signal_next_bar_collision",
        "gt_five_bar_runway",
    ]
    for column in numeric_cols:
        rows[column] = pd.to_numeric(rows.get(column, 0), errors="coerce").fillna(0)
    rows["replay_event_family"] = rows["replay_event_family"].fillna("missing")
    rows["resolution_bucket"] = rows["resolution_bucket"].fillna("missing")
    rows["tail_class"] = "ordinary"
    rows.loc[rows["right_tail_visual"].eq(1), "tail_class"] = "right_tail"
    rows.loc[rows["bottom_loss_visual"].eq(1), "tail_class"] = "bottom_loss"
    rows.loc[rows["right_tail_visual"].eq(1) & rows["bottom_loss_visual"].eq(1), "tail_class"] = "both_tail_flags"
    rows["leadtime_bucket"] = pd.cut(
        rows["completed_bars_before_event"],
        bins=[-0.1, 0, 1, 5, 20, 10_000],
        labels=["0_bar", "1_bar", "2_5_bars", "6_20_bars", "gt20_bars"],
    ).astype(str)
    return rows


def _tail_conflict_matrix(rows: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        rows.groupby(["replay_event_family", "resolution_bucket"], dropna=False)
        .agg(
            order_count=("official_open_trade_id", "nunique"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
            median_completed_bars=("completed_bars_before_event", "median"),
        )
        .reset_index()
    )
    grouped["tail_conflict"] = (grouped["right_tail_count"].gt(0) & grouped["bottom_loss_count"].gt(0)).astype(int)
    grouped["rule_interpretation_allowed"] = 0
    return grouped.sort_values(["tail_conflict", "order_count"], ascending=[False, False]).reset_index(drop=True)


def _blocked_routes(rows: pd.DataFrame, tail_matrix: pd.DataFrame) -> pd.DataFrame:
    right_tail = int(rows["right_tail_visual"].sum())
    bottom_loss = int(rows["bottom_loss_visual"].sum())
    low_resolution = int(rows["low_resolution_zone"].sum())
    tail_conflict_cells = int(tail_matrix["tail_conflict"].sum())
    return pd.DataFrame(
        [
            {
                "route_id": "h3_event_family_direct_rule",
                "route_description": "Use Stage045/102 event family as the minute decision signal.",
                "current_evidence": f"event family exists for {len(rows)} rows but is known after replay/entry.",
                "blocked_reason": "noncausal_post_entry_research_label",
                "rule_feasible_now": 0,
                "next_allowed_action": "keep as research label only",
            },
            {
                "route_id": "h3_runway_bucket_rule",
                "route_description": "Use completed bars/runway bucket to decide whether to reduce or restore risk.",
                "current_evidence": f"low_resolution={low_resolution}, tail_conflict_cells={tail_conflict_cells}.",
                "blocked_reason": "collides_with_stage102_and_far_from_touch_closed_shape",
                "rule_feasible_now": 0,
                "next_allowed_action": "visual context only; no threshold or bucket rule",
            },
            {
                "route_id": "h3_tail_separation_by_existing_ohlc",
                "route_description": "Separate right-tail and bottom-loss using current Stage102 minute OHLC fields.",
                "current_evidence": f"right_tail={right_tail}, bottom_loss={bottom_loss}, mixed cells={tail_conflict_cells}.",
                "blocked_reason": "right_tail_bottom_loss_not_separable_without_overfit",
                "rule_feasible_now": 0,
                "next_allowed_action": "require stronger independent evidence before any true engine",
            },
            {
                "route_id": "h3_authorized_orderflow_continuation",
                "route_description": "Use authorized tick/depth/orderflow to confirm mature continuation before risk change.",
                "current_evidence": "Stage149 same_source_or_authorized_data_ready=0.",
                "blocked_reason": "real_w0_or_authorized_data_missing",
                "rule_feasible_now": 0,
                "next_allowed_action": "if data arrives, run Stage125 -> Stage133 -> Stage112/113 first",
            },
            {
                "route_id": "h3_broker_execution_replay_maturity",
                "route_description": "Use same-source broker execution replay to prove actionability and lead time.",
                "current_evidence": "No accepted broker/production execution replay package is available in this line.",
                "blocked_reason": "execution_replay_missing",
                "rule_feasible_now": 0,
                "next_allowed_action": "wait for real execution replay, then intake gate before rule research",
            },
        ]
    )


def _feasibility_evidence(stage149_evidence: pd.DataFrame, rows: pd.DataFrame, tail_matrix: pd.DataFrame) -> pd.DataFrame:
    ready_lookup = {}
    if not stage149_evidence.empty and {"evidence_id", "ready_now"}.issubset(stage149_evidence.columns):
        ready_lookup = dict(zip(stage149_evidence["evidence_id"], stage149_evidence["ready_now"]))
    tail_conflict_cells = int(tail_matrix["tail_conflict"].sum())
    rows_out = [
        ("stage149_h3_spec_exists", "H3 predeclared spec exists and forbids closed-route reuse.", 1, 1, "Stage149"),
        ("stage102_visual_context_available", "Stage102 replay rows are available for visual context.", int(len(rows) > 0), 1, "Stage102"),
        ("event_family_noncausal_guard", "Event family is treated as a research label, not as a trade condition.", 1, 1, "Stage149/150"),
        (
            "same_source_or_authorized_minute_k_ready",
            "Same-source or authorized minute/quote/orderflow data is available.",
            int(float(ready_lookup.get("same_source_or_authorized_minute_k_ready", 0)) == 1),
            0,
            "Stage149",
        ),
        (
            "lead_time_actionability_verified",
            "Independent lead time before any order change is verified.",
            int(float(ready_lookup.get("lead_time_actionability_verified", 0)) == 1),
            0,
            "Stage101/102/149",
        ),
        (
            "right_tail_bottom_loss_atlas_generated",
            "This stage generates a right-tail/bottom-loss visual atlas.",
            1,
            1,
            "Stage150",
        ),
        (
            "right_tail_bottom_loss_separable",
            "Current context separates right-tail from bottom-loss without closed-route features.",
            int(tail_conflict_cells == 0),
            0,
            "Stage150",
        ),
        ("walkforward_loyo_ready", "LOYO or comparable OOS proof exists for H3.", 0, 0, "future"),
        ("monthly_start_ready", "Monthly cold-start evidence exists for H3.", 0, 0, "future"),
        ("product_family_ready", "Cross-product family stability is proven for H3.", 0, 0, "future"),
        ("stage145_package_ready", "A real candidate package can pass Stage145.", 0, 0, "future"),
    ]
    return pd.DataFrame(
        [
            {
                "evidence_id": evidence_id,
                "requirement": requirement,
                "observed_ready": observed_ready,
                "pass_for_readonly_stage": pass_for_readonly,
                "pass_for_rule_entry": 0 if evidence_id not in {"stage149_h3_spec_exists", "stage102_visual_context_available", "event_family_noncausal_guard"} else observed_ready,
                "evidence_stage": stage,
            }
            for evidence_id, requirement, observed_ready, pass_for_readonly, stage in rows_out
        ]
    )


def _select_atlas_rows(rows: pd.DataFrame) -> pd.DataFrame:
    selected_indices: list[int] = []
    ordered_groups = [
        rows[rows["right_tail_visual"].eq(1)].assign(priority_group="right_tail"),
        rows[rows["bottom_loss_visual"].eq(1)].assign(priority_group="bottom_loss"),
        rows[rows["maxdd_context"].eq(1)].assign(priority_group="maxdd_context"),
        rows[rows["low_resolution_zone"].eq(1)].assign(priority_group="low_resolution"),
        rows.assign(priority_group="abs_pnl_context"),
    ]
    for group in ordered_groups:
        group = group.reindex(group["order_realized_pnl"].abs().sort_values(ascending=False).index)
        for idx in group.index:
            if idx not in selected_indices:
                selected_indices.append(idx)
            if len(selected_indices) >= ATLAS_ROWS:
                break
        if len(selected_indices) >= ATLAS_ROWS:
            break
    out = rows.loc[selected_indices].copy()
    out["atlas_rank"] = range(1, len(out) + 1)
    return out


def _plot_atlas(rows: pd.DataFrame) -> pd.DataFrame:
    selected = _select_atlas_rows(rows)
    manifest_rows: list[dict[str, Any]] = []
    total_pages = int(np.ceil(len(selected) / ATLAS_PER_PAGE)) if len(selected) else 0
    for page in range(total_pages):
        chunk = selected.iloc[page * ATLAS_PER_PAGE : (page + 1) * ATLAS_PER_PAGE]
        out_path = Path(str(ATLAS_TEMPLATE).format(page=page + 1))
        fig, axes = plt.subplots(len(chunk), 1, figsize=(13, max(3.0, 2.15 * len(chunk))), squeeze=False)
        for ax, (_, row) in zip(axes[:, 0], chunk.iterrows()):
            xs = np.array([0, 1, 2, 4, 5, 6], dtype=float)
            labels = ["pre_low", "pre_close", "pre_high", "event_low", "event_close", "event_high"]
            values = np.array(
                [
                    row["pre_event_mae_r"],
                    row["pre_event_close_r"],
                    row["pre_event_mfe_r"],
                    row["event_bar_low_r"],
                    row["event_bar_close_r"],
                    row["event_bar_high_r"],
                ],
                dtype=float,
            )
            color = "#0F766E"
            if int(row["right_tail_visual"]) == 1:
                color = "#14532D"
            if int(row["bottom_loss_visual"]) == 1:
                color = "#B91C1C"
            if int(row["maxdd_context"]) == 1 and int(row["bottom_loss_visual"]) == 0:
                color = "#B45309"
            ax.plot(xs[:3], values[:3], color=color, marker="o", linewidth=1.4, label="pre-event R range")
            ax.plot(xs[3:], values[3:], color="#3657D6", marker="o", linewidth=1.4, label="event-bar R range")
            ax.fill_between([0, 2], values[0], values[2], color=color, alpha=0.12)
            ax.fill_between([4, 6], values[3], values[5], color="#3657D6", alpha=0.12)
            ax.axhline(0, color="#111827", linewidth=0.75)
            ax.axhline(0.5, color="#16A34A", linestyle="--", linewidth=0.75)
            ax.axhline(-0.5, color="#DC2626", linestyle="--", linewidth=0.75)
            ax.set_xticks(xs)
            ax.set_xticklabels(labels, fontsize=8)
            title = (
                f"#{int(row['atlas_rank'])} {row['vt_symbol']} {row['direction']} "
                f"{pd.Timestamp(row['official_open_date']).date()} | {row['resolution_bucket']} | "
                f"{row['replay_event_family']} | pnl={row['order_realized_pnl']:,.0f} | "
                f"rt={int(row['right_tail_visual'])} bl={int(row['bottom_loss_visual'])} md={int(row['maxdd_context'])}"
            )
            ax.set_title(title, fontsize=8)
            ax.set_ylabel("R")
            ax.grid(True, alpha=0.25)
            manifest_rows.append(
                {
                    "page": page + 1,
                    "atlas_rank": int(row["atlas_rank"]),
                    "candidate_index": row["candidate_index"],
                    "official_open_trade_id": row["official_open_trade_id"],
                    "vt_symbol": row["vt_symbol"],
                    "direction": row["direction"],
                    "official_open_date": row["official_open_date"],
                    "replay_event_family": row["replay_event_family"],
                    "resolution_bucket": row["resolution_bucket"],
                    "order_realized_pnl": row["order_realized_pnl"],
                    "right_tail_visual": row["right_tail_visual"],
                    "bottom_loss_visual": row["bottom_loss_visual"],
                    "maxdd_context": row["maxdd_context"],
                    "atlas_path": str(out_path),
                }
            )
        axes[0, 0].legend(loc="upper right", fontsize=7)
        fig.suptitle("Stage150 H3 R-path summary atlas: visual context only, not a minute-K trade rule", y=0.995)
        fig.tight_layout()
        fig.savefig(out_path, dpi=170)
        plt.close(fig)
    return pd.DataFrame(manifest_rows)


def _gate_status(summary: pd.DataFrame, evidence: pd.DataFrame, routes: pd.DataFrame) -> pd.DataFrame:
    row = summary.iloc[0].to_dict()
    rows = [
        ("readonly_feasibility_generated", _int(row, "h3_feasibility_audit_ready"), 1, "audit_hard"),
        ("visual_atlas_generated", _int(row, "atlas_page_count"), 1, "visual_hard_min"),
        ("no_rule_or_engine", _int(row, "strategy_rule_created") + _int(row, "true_engine_run"), 0, "execution_hard"),
        ("no_official_or_order_side_effect", _int(row, "side_effect_count"), 0, "execution_hard"),
        ("rule_entry_blocked", _int(row, "h3_rule_feasible_now"), 0, "anti_overclaim_hard"),
        ("blocked_routes_present", int((routes["rule_feasible_now"] == 0).sum()), 1, "reality_check_hard"),
        ("rule_evidence_incomplete", int((evidence["pass_for_rule_entry"] == 0).sum()), 1, "evidence_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": observed,
                "required": required,
                "pass_now": int(observed == required if gate_id not in {"visual_atlas_generated", "blocked_routes_present", "rule_evidence_incomplete"} else observed >= required),
                "severity": severity,
            }
            for gate_id, observed, required, severity in rows
        ]
    )


def _write_report(
    summary: pd.DataFrame,
    evidence: pd.DataFrame,
    routes: pd.DataFrame,
    tail_matrix: pd.DataFrame,
    atlas_manifest: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} H3 只读可行性与视觉 atlas",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只做 H3 证据可行性和视觉上下文，不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- Research Affiliates 的趋势跟随 tradeoff 资料强调正偏/右尾和回撤之间存在取舍；这支持先保护右尾，而不是为了回撤平滑先砍趋势暴露。",
        "- Man AHL 关于 trend following drawdown 的材料强调趋势跟随凸性常来自极端阶段；分钟 overlay 如果没有同源执行证据，容易把危机 alpha 或趋势右尾误删。",
        "- GitHub walk-forward/backtesting 项目强调验证框架，但没有解决本线需要的授权同源分钟 K/盘口执行证据缺口。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Feasibility Evidence",
        "",
        _md_table(evidence),
        "",
        "## Blocked Feature Routes",
        "",
        _md_table(routes),
        "",
        "## Tail Conflict Matrix",
        "",
        _md_table(tail_matrix, max_rows=40),
        "",
        "## Atlas Manifest",
        "",
        _md_table(atlas_manifest, max_rows=40),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{EVIDENCE_CHART_OUT.name}`",
        f"- `{TAIL_CHART_OUT.name}`",
        f"- `{LEADTIME_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
        "- R-path summary atlas pages listed in atlas manifest.",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, rows: pd.DataFrame, summary: pd.DataFrame) -> None:
    data = curve.copy()
    points = rows.merge(data[["date", "account_equity"]], left_on="official_open_date", right_on="date", how="left")
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    axes[0].plot(data["date"], data["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    right = points[points["right_tail_visual"].eq(1)]
    bottom = points[points["bottom_loss_visual"].eq(1)]
    axes[0].scatter(right["official_open_date"], right["account_equity"] / 1_000_000, color="#0F766E", s=26, label="right tail context", alpha=0.75)
    axes[0].scatter(bottom["official_open_date"], bottom["account_equity"] / 1_000_000, color="#B91C1C", s=26, label="bottom loss context", alpha=0.75)
    axes[0].set_ylabel("equity (m)")
    axes[0].legend(fontsize=8)
    axes[1].fill_between(data["date"], data["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(data["date"], data["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["rule_feasible", "auth_data", "tail_conflict", "atlas_pages", "side_effect"]
    row = summary.iloc[0]
    values = [
        row["h3_rule_feasible_now"],
        row["same_source_or_authorized_data_ready"],
        row["tail_conflict_cell_count"],
        row["atlas_page_count"],
        row["side_effect_count"],
    ]
    axes[3].bar(labels, values, color=["#B91C1C", "#B45309", "#B91C1C", "#0F766E", "#B91C1C"])
    axes[3].set_title("Stage150 H3 readiness: visual context generated, rule remains blocked")
    axes[3].set_ylabel("count / flag")
    axes[3].tick_params(axis="x", labelrotation=15)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_matrix(frame: pd.DataFrame, index_col: str, value_cols: list[str], title: str, path: Path) -> None:
    matrix = frame.set_index(index_col)[value_cols].copy()
    for column in value_cols:
        matrix[column] = pd.to_numeric(matrix[column], errors="coerce").fillna(0).clip(upper=1)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.55), max(4.8, len(matrix) * 0.5)))
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


def _plot_tail_heatmap(tail_matrix: pd.DataFrame) -> None:
    pivot = tail_matrix.pivot_table(
        index="replay_event_family",
        columns="resolution_bucket",
        values="tail_conflict",
        aggfunc="max",
        fill_value=0,
    )
    counts = tail_matrix.pivot_table(
        index="replay_event_family",
        columns="resolution_bucket",
        values="order_count",
        aggfunc="sum",
        fill_value=0,
    ).reindex_like(pivot)
    fig, ax = plt.subplots(figsize=(13, 6.2))
    data = pivot.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="Reds", vmin=0, vmax=1)
    ax.set_title("Stage150 right-tail / bottom-loss conflict cells")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, f"{int(data[i, j])}\nN={int(counts.iloc[i, j])}", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(TAIL_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_leadtime(rows: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=False)
    for label, color in [("right_tail", "#0F766E"), ("bottom_loss", "#B91C1C"), ("ordinary", "#64748B")]:
        values = rows.loc[rows["tail_class"].eq(label), "completed_bars_before_event"]
        if not values.empty:
            axes[0].hist(values.clip(upper=120), bins=24, alpha=0.45, label=label, color=color)
    axes[0].set_title("Completed bars before C9 event or day-end context")
    axes[0].set_xlabel("completed bars, clipped at 120")
    axes[0].set_ylabel("orders")
    axes[0].legend(fontsize=8)
    cross = pd.crosstab(rows["leadtime_bucket"], rows["tail_class"])
    cross = cross.reindex(["0_bar", "1_bar", "2_5_bars", "6_20_bars", "gt20_bars"]).fillna(0)
    bottom = np.zeros(len(cross))
    colors = {"ordinary": "#64748B", "right_tail": "#0F766E", "bottom_loss": "#B91C1C", "both_tail_flags": "#7C2D12"}
    for column in cross.columns:
        axes[1].bar(cross.index, cross[column], bottom=bottom, label=column, color=colors.get(column, "#3657D6"))
        bottom += cross[column].to_numpy()
    axes[1].set_title("Lead-time buckets are context only; no threshold is promoted")
    axes[1].set_ylabel("orders")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(LEADTIME_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    curve = _load_curve()
    rows = _prepare_rows(_read_csv(STAGE102_ROWS_IN))
    stage149_summary = _read_csv(STAGE149_SUMMARY_IN)
    stage149_spec = _read_csv(STAGE149_SPEC_IN)
    stage149_evidence = _read_csv(STAGE149_EVIDENCE_IN)
    if stage149_summary.empty:
        raise RuntimeError(f"missing Stage149 summary input: {STAGE149_SUMMARY_IN}")
    stage149_row = stage149_summary.iloc[0].to_dict()

    tail_matrix = _tail_conflict_matrix(rows)
    routes = _blocked_routes(rows, tail_matrix)
    evidence = _feasibility_evidence(stage149_evidence, rows, tail_matrix)
    atlas_manifest = _plot_atlas(rows)
    side_effect_count = 0
    rule_feasible_now = 0
    decision = "stage150_h3_readonly_feasibility_blocks_rule_no_candidate"
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "next_best_action": "wait_real_w0_or_find_new_point_in_time_external_source",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "true_engine_run_count": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "side_effect_count": side_effect_count,
                "h3_feasibility_audit_ready": 1,
                "h3_rule_feasible_now": rule_feasible_now,
                "same_source_or_authorized_data_ready": _int(stage149_row, "same_source_or_authorized_data_ready"),
                "stage102_context_order_count": int(len(rows)),
                "right_tail_order_count": int(rows["right_tail_visual"].sum()),
                "bottom_loss_order_count": int(rows["bottom_loss_visual"].sum()),
                "maxdd_context_order_count": int(rows["maxdd_context"].sum()),
                "low_resolution_order_count": int(rows["low_resolution_zone"].sum()),
                "tail_conflict_cell_count": int(tail_matrix["tail_conflict"].sum()),
                "blocked_feature_route_count": int(len(routes)),
                "rule_feasible_route_count": int(routes["rule_feasible_now"].sum()),
                "feasibility_evidence_count": int(len(evidence)),
                "rule_entry_evidence_pass_count": int(evidence["pass_for_rule_entry"].sum()),
                "atlas_row_count": int(len(atlas_manifest)),
                "atlas_page_count": int(atlas_manifest["page"].nunique()) if not atlas_manifest.empty else 0,
                "current_package_promotion_allowed": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "objective_completion_proven": 0,
                "stage149_spec_row_count": int(len(stage149_spec)),
                "end_equity": float(stage149_row.get("end_equity", np.nan)),
                "total_return_pct": float(stage149_row.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(stage149_row.get("max_drawdown_pct", np.nan)),
                "sharpe": float(stage149_row.get("sharpe", np.nan)),
                "total_slippage": float(stage149_row.get("total_slippage", np.nan)),
                "total_trade_count": float(stage149_row.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(stage149_row.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(
                    stage149_row.get("max_broker10_margin_to_equity_pct", np.nan)
                ),
            }
        ]
    )
    gate = _gate_status(summary, evidence, routes)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(evidence, EVIDENCE_OUT)
    _write_csv(routes, ROUTE_OUT)
    _write_csv(tail_matrix, TAIL_MATRIX_OUT)
    _write_csv(atlas_manifest, ATLAS_MANIFEST_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, evidence, routes, tail_matrix, atlas_manifest, gate)
    _plot_path(curve, rows, summary)
    _plot_matrix(evidence, "evidence_id", ["observed_ready", "pass_for_rule_entry"], "Stage150 H3 feasibility evidence", EVIDENCE_CHART_OUT)
    _plot_tail_heatmap(tail_matrix)
    _plot_leadtime(rows)
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage150 gate status", GATE_CHART_OUT)
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
                "stage149_summary": str(STAGE149_SUMMARY_IN),
                "stage149_spec": str(STAGE149_SPEC_IN),
                "stage149_evidence": str(STAGE149_EVIDENCE_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "feasibility_evidence": str(EVIDENCE_OUT),
                "blocked_feature_routes": str(ROUTE_OUT),
                "tail_conflict_matrix": str(TAIL_MATRIX_OUT),
                "atlas_manifest": str(ATLAS_MANIFEST_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(EVIDENCE_CHART_OUT),
                    str(TAIL_CHART_OUT),
                    str(LEADTIME_CHART_OUT),
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
                "h3_rule_feasible_now": 0,
                "current_package_promotion_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

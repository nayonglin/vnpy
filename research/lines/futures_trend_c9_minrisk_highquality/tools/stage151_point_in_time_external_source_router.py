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
STAGE = "Stage151"
MODEL_TAG = "stage151_point_in_time_external_source_router_v1"
OUTPUT_PREFIX = "qmt_roll_stage151_c9_minrisk_point_in_time_external_source_router"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage151_point_in_time_external_source_router"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE150_DIR = LINE_DIR / "outputs" / "stage150_h3_readonly_feasibility_atlas"
STAGE150_PREFIX = "qmt_roll_stage150_c9_minrisk_h3_readonly_feasibility_atlas"
STAGE150_TAG = "stage150_h3_readonly_feasibility_atlas_v1"
STAGE150_SUMMARY_IN = STAGE150_DIR / f"{STAGE150_PREFIX}_summary_{STAGE150_TAG}.csv"
STAGE150_ROUTES_IN = STAGE150_DIR / f"{STAGE150_PREFIX}_blocked_feature_routes_{STAGE150_TAG}.csv"

STAGE099_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage099_finer_source_feasibility_manifest"
    / "qmt_roll_stage099_c9_minrisk_finer_source_feasibility_manifest_summary_"
    "stage099_finer_source_feasibility_manifest_v1.csv"
)
STAGE107_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage107_contract_month_oi_patched_root_reaudit"
    / "qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_summary_"
    "stage107_contract_month_oi_patched_root_reaudit_v1.csv"
)
STAGE114_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage114_microstructure_procurement_request_bundle"
    / "qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_summary_"
    "stage114_microstructure_procurement_request_bundle_v1.csv"
)
STAGE115_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage115_procurement_wave_antiselection_plan"
    / "qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan_summary_"
    "stage115_procurement_wave_antiselection_plan_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ROUTE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_route_scorecard_{MODEL_TAG}.csv"
REQUIREMENT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_requirements_{MODEL_TAG}.csv"
ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_source_status_{MODEL_TAG}.png"
ROUTE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_score_matrix_{MODEL_TAG}.png"
PRIORITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_priority_bars_{MODEL_TAG}.png"
REQUIREMENT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_requirement_matrix_{MODEL_TAG}.png"
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


def _source_routes(context: dict[str, dict[str, Any]]) -> pd.DataFrame:
    s114 = context["stage114"]
    s115 = context["stage115"]
    s099 = context["stage099"]
    s107 = context["stage107"]
    s150 = context["stage150"]
    routes = [
        {
            "route_id": "authoritative_minute_ohlcv_volume",
            "route_name": "授权/权威 1m OHLCV + volume/OI 分钟K",
            "source_family": "minute_k_external",
            "external_reference": "Databento/Firstratedata/IBKR-style historical futures minute data; domestic equivalent must be licensed.",
            "local_stage_evidence": "Stage150 blocks internal replay; Stage058/077 local raw bars are not sufficient provenance.",
            "point_in_time_possible": 1,
            "minute_or_execution_level": 1,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "universal_cross_product_potential": 1,
            "current_local_data_ready": 0,
            "procurement_or_backfill_required": 1,
            "closed_route_collision": 0,
            "rule_feasible_now": 0,
            "next_research_value": 5,
            "priority_rank": 1,
            "recommended_next_action": "Stage152 build fixed manifest for authoritative minute OHLCV/volume/OI coverage.",
        },
        {
            "route_id": "authorized_mbp_mbo_orderflow_w0",
            "route_name": "授权 MBP-10/MBO orderflow W0/W1/W2",
            "source_family": "microstructure_external",
            "external_reference": "CME DataMine/Databento-style MBO, MBP-10, PCAP datasets.",
            "local_stage_evidence": (
                f"Stage114 requests={_int(s114, 'request_interval_count')}, windows={_int(s114, 'required_window_count')}; "
                f"Stage115 accepted_coverage={_num(s115, 'accepted_window_coverage_pct_now'):.1f}%."
            ),
            "point_in_time_possible": 1,
            "minute_or_execution_level": 1,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "universal_cross_product_potential": 1,
            "current_local_data_ready": 0,
            "procurement_or_backfill_required": 1,
            "closed_route_collision": 0,
            "rule_feasible_now": 0,
            "next_research_value": 4,
            "priority_rank": 2,
            "recommended_next_action": "Wait real W0 drop; run Stage125 -> Stage133 -> Stage112/113 before signal work.",
        },
        {
            "route_id": "broker_execution_replay",
            "route_name": "同源 broker/production execution replay",
            "source_family": "execution_replay_external",
            "external_reference": "Broker order/trade/tick replay with bridge_signal_id -> order_reference -> fill joins.",
            "local_stage_evidence": "Stage150 broker_execution_replay_maturity blocked; no accepted replay package.",
            "point_in_time_possible": 1,
            "minute_or_execution_level": 1,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "universal_cross_product_potential": 1,
            "current_local_data_ready": 0,
            "procurement_or_backfill_required": 1,
            "closed_route_collision": 0,
            "rule_feasible_now": 0,
            "next_research_value": 4,
            "priority_rank": 3,
            "recommended_next_action": "Define accepted replay manifest only if actual production/broker logs are delivered.",
        },
        {
            "route_id": "commodity_options_iv_skew",
            "route_name": "商品期权 IV/skew 风险状态",
            "source_family": "options_external",
            "external_reference": "CME CVOL/skew and commodity option implied-volatility literature.",
            "local_stage_evidence": "No local option IV chain cache for C9 universe; coverage likely product-limited.",
            "point_in_time_possible": 1,
            "minute_or_execution_level": 0,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "universal_cross_product_potential": 0,
            "current_local_data_ready": 0,
            "procurement_or_backfill_required": 1,
            "closed_route_collision": 0,
            "rule_feasible_now": 0,
            "next_research_value": 2,
            "priority_rank": 4,
            "recommended_next_action": "Only after minute/execution sources stall; first audit product coverage and timestamp provenance.",
        },
        {
            "route_id": "full_contract_curve_carry_basis",
            "route_name": "全合约期限结构/carry/basis",
            "source_family": "daily_curve_external",
            "external_reference": "Commodity carry literature; complete settlement curve required.",
            "local_stage_evidence": "Stage026 carry route closed for direct rule; Stage049 trend t-stat coverage insufficient.",
            "point_in_time_possible": 1,
            "minute_or_execution_level": 0,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "universal_cross_product_potential": 1,
            "current_local_data_ready": 0,
            "procurement_or_backfill_required": 1,
            "closed_route_collision": 1,
            "rule_feasible_now": 0,
            "next_research_value": 1,
            "priority_rank": 5,
            "recommended_next_action": "Data engineering only; no direct rule or threshold rescue.",
        },
        {
            "route_id": "official_inventory_member_warehouse_raw",
            "route_name": "官方仓单/库存/会员持仓 raw provenance",
            "source_family": "fundamental_external",
            "external_reference": "Exchange raw warehouse/member rank files; full raw provenance required.",
            "local_stage_evidence": (
                f"Stage099 direct_rule_allowed={_int(s099, 'direct_rule_allowed_count')}; "
                f"Stage107 panel_rule_allowed={_int(s107, 'panel_feature_rule_allowed')}."
            ),
            "point_in_time_possible": 1,
            "minute_or_execution_level": 0,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "universal_cross_product_potential": 0,
            "current_local_data_ready": 0,
            "procurement_or_backfill_required": 1,
            "closed_route_collision": 1,
            "rule_feasible_now": 0,
            "next_research_value": 1,
            "priority_rank": 6,
            "recommended_next_action": "Only raw/provenance/coverage repair; no product/year/missingness rule.",
        },
        {
            "route_id": "macro_weather_news_event",
            "route_name": "宏观/天气/新闻事件源",
            "source_family": "slow_or_discretionary_external",
            "external_reference": "Managed futures quantamental literature; not minute execution evidence.",
            "local_stage_evidence": "No point-in-time event cache, no C9 universe mapping, no minute actionability.",
            "point_in_time_possible": 1,
            "minute_or_execution_level": 0,
            "entry_visible_possible": 0,
            "independent_of_final_pnl": 1,
            "universal_cross_product_potential": 0,
            "current_local_data_ready": 0,
            "procurement_or_backfill_required": 1,
            "closed_route_collision": 0,
            "rule_feasible_now": 0,
            "next_research_value": 0,
            "priority_rank": 7,
            "recommended_next_action": "Not aligned with current minute-K execution objective.",
        },
        {
            "route_id": "existing_internal_replay_labels",
            "route_name": "现有 Stage102/150 internal replay labels",
            "source_family": "internal_replay_not_external",
            "external_reference": "None; already local replay label context.",
            "local_stage_evidence": (
                f"Stage150 h3_rule_feasible_now={_int(s150, 'h3_rule_feasible_now')}, "
                f"tail_conflict_cells={_int(s150, 'tail_conflict_cell_count')}."
            ),
            "point_in_time_possible": 0,
            "minute_or_execution_level": 1,
            "entry_visible_possible": 0,
            "independent_of_final_pnl": 1,
            "universal_cross_product_potential": 0,
            "current_local_data_ready": 1,
            "procurement_or_backfill_required": 0,
            "closed_route_collision": 1,
            "rule_feasible_now": 0,
            "next_research_value": 0,
            "priority_rank": 8,
            "recommended_next_action": "Stop using this as a rule source; visual context only.",
        },
    ]
    route_df = pd.DataFrame(routes)
    score_cols = [
        "point_in_time_possible",
        "minute_or_execution_level",
        "entry_visible_possible",
        "independent_of_final_pnl",
        "universal_cross_product_potential",
    ]
    route_df["evidence_fit_score"] = route_df[score_cols].sum(axis=1) - route_df["closed_route_collision"]
    route_df["data_gap"] = (route_df["current_local_data_ready"].eq(0) & route_df["procurement_or_backfill_required"].eq(1)).astype(int)
    return route_df.sort_values("priority_rank").reset_index(drop=True)


def _manifest_requirements() -> pd.DataFrame:
    rows = [
        ("raw_file", "path", "Original licensed raw minute file, immutable after intake.", 1, 1),
        ("raw_sha256", "hash", "SHA256 of raw file before parsing.", 1, 1),
        ("schema_hash", "hash", "Stable hash of raw and normalized schemas.", 1, 1),
        ("vendor_license", "provenance", "Permission proving strategy research use is allowed.", 1, 1),
        ("query_params", "provenance", "Exact symbol, date, session, interval, and adjustment parameters.", 1, 1),
        ("exchange", "identity", "Exchange code aligned to C9 vt_symbol universe.", 1, 1),
        ("vt_symbol", "identity", "Contract-level symbol, not product-only aggregate.", 1, 1),
        ("bar_start_ts", "timestamp", "Timezone-aware bar start timestamp.", 1, 1),
        ("bar_end_ts", "timestamp", "Timezone-aware bar end timestamp or convention flag.", 1, 1),
        ("open_high_low_close", "price", "Raw OHLC fields with no future adjustment.", 1, 1),
        ("volume", "liquidity", "Real traded volume, not zero-volume proxy.", 1, 1),
        ("turnover", "liquidity", "Turnover if available; unit must be declared.", 1, 0),
        ("open_interest", "liquidity", "Contract-level OI if available at minute or daily close.", 1, 0),
        ("session_calendar", "calendar", "Night/day session stitching and holiday convention.", 1, 1),
        ("sequence_gap_count", "quality", "Missing/duplicate minute bars in required windows.", 1, 1),
        ("right_tail_window_coverage", "coverage", "Coverage proof for right-tail windows.", 1, 1),
        ("bottom_loss_window_coverage", "coverage", "Coverage proof for bottom-loss windows.", 1, 1),
        ("maxdd_window_coverage", "coverage", "Coverage proof for maxDD-context windows.", 1, 1),
    ]
    return pd.DataFrame(
        [
            {
                "field": field,
                "field_group": group,
                "requirement": requirement,
                "required_for_stage152_manifest": required,
                "hard_gate": hard_gate,
            }
            for field, group, requirement, required, hard_gate in rows
        ]
    )


def _action_queue(routes: pd.DataFrame) -> pd.DataFrame:
    top_route = routes.iloc[0]
    return pd.DataFrame(
        [
            {
                "priority": 1,
                "action_id": "stage152_authoritative_minute_ohlcv_manifest",
                "action": "Build a fixed manifest and required-window coverage contract for authoritative 1m OHLCV/volume/OI.",
                "why": "This is the only new route that stays minute-K aligned while avoiding internal replay labels.",
                "allowed_now": 1,
                "linked_route": top_route["route_id"],
            },
            {
                "priority": 2,
                "action_id": "wait_real_w0_orderflow",
                "action": "If W0 orderflow arrives, run Stage125 -> Stage133 -> Stage112/113 before signal research.",
                "why": "Orderflow remains the strongest execution/actionability source, but current accepted coverage is zero.",
                "allowed_now": 0,
                "linked_route": "authorized_mbp_mbo_orderflow_w0",
            },
            {
                "priority": 3,
                "action_id": "do_not_use_internal_replay_as_rule",
                "action": "Keep Stage102/150 replay labels as visual context only.",
                "why": "Event family and runway buckets are post-entry labels or closed-route collisions.",
                "allowed_now": 1,
                "linked_route": "existing_internal_replay_labels",
            },
            {
                "priority": 4,
                "action_id": "defer_slow_external_sources",
                "action": "Defer IV/skew, carry, warehouse/member and macro/news routes until minute/execution sources are exhausted.",
                "why": "They are not direct minute-K execution evidence and many collide with closed external routes.",
                "allowed_now": 1,
                "linked_route": "non_minute_external_sources",
            },
        ]
    )


def _gate_status(summary: pd.DataFrame, routes: pd.DataFrame, requirements: pd.DataFrame) -> pd.DataFrame:
    row = summary.iloc[0].to_dict()
    rows = [
        ("route_screen_generated", _int(row, "source_route_screen_ready"), 1, "audit_hard"),
        ("selected_next_route_not_rule", _int(row, "selected_next_route_rule_feasible_now"), 0, "anti_overclaim_hard"),
        ("no_current_rule_candidate", _int(row, "rule_feasible_route_count"), 0, "strategy_hard"),
        ("manifest_requirements_written", int(len(requirements)), 1, "data_contract_hard"),
        ("internal_replay_not_selected", int(routes.iloc[0]["route_id"] == "existing_internal_replay_labels"), 0, "anti_rescue_hard"),
        ("no_execution_side_effect", _int(row, "side_effect_count"), 0, "execution_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": observed,
                "required": required,
                "pass_now": int(observed == required if gate_id != "manifest_requirements_written" else observed >= required),
                "severity": severity,
            }
            for gate_id, observed, required, severity in rows
        ]
    )


def _write_report(
    summary: pd.DataFrame,
    routes: pd.DataFrame,
    requirements: pd.DataFrame,
    actions: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} 点时化外生源路线筛选",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只筛数据路线，不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- Databento/CME DataMine/Firstratedata/IBKR 等资料证明历史期货分钟K、tick、MBO/MBP 数据可以以授权方式取得，但必须保留 raw、schema、license 与 timestamp provenance。",
        "- CME CVOL/skew 与商品期权 IV 文献说明期权波动率可能有风险状态信息，但覆盖与分钟执行相关性不足，不能优先于分钟K/盘口/执行回放。",
        "- commodity carry、仓单、会员持仓等外生源有经济含义，但本线此前已证明粗粒度/缺 provenance 的版本不能直接规则化。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Source Route Scorecard",
        "",
        _md_table(routes),
        "",
        "## Stage152 Manifest Requirements",
        "",
        _md_table(requirements),
        "",
        "## Next Action Queue",
        "",
        _md_table(actions),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{ROUTE_MATRIX_CHART_OUT.name}`",
        f"- `{PRIORITY_CHART_OUT.name}`",
        f"- `{REQUIREMENT_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage151 external source router on official path", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["routes", "rule_ok", "data_eng", "selected_rule", "side_effect"]
    values = [
        row["source_route_count"],
        row["rule_feasible_route_count"],
        row["data_engineering_route_count"],
        row["selected_next_route_rule_feasible_now"],
        row["side_effect_count"],
    ]
    axes[3].bar(labels, values, color=["#3657D6", "#B91C1C", "#0F766E", "#B45309", "#B91C1C"])
    axes[3].set_title("Route screen: next step is data manifest, not a strategy candidate")
    axes[3].set_ylabel("count / flag")
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


def _plot_priority(routes: pd.DataFrame) -> None:
    data = routes.sort_values("priority_rank", ascending=False)
    fig, ax = plt.subplots(figsize=(13, 6.2))
    colors = np.where(data["closed_route_collision"].eq(1), "#B91C1C", "#0F766E")
    ax.barh(data["route_id"], data["next_research_value"], color=colors, alpha=0.85)
    ax.set_title("Stage151 source priority; green still means data route, not rule")
    ax.set_xlabel("next research value")
    ax.grid(axis="x", alpha=0.25)
    for i, (_, row) in enumerate(data.iterrows()):
        ax.text(0.05, i, f"rank={int(row['priority_rank'])}, ready={int(row['current_local_data_ready'])}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(PRIORITY_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    curve = _load_curve()
    context = {
        "stage099": _row(STAGE099_SUMMARY_IN),
        "stage107": _row(STAGE107_SUMMARY_IN),
        "stage114": _row(STAGE114_SUMMARY_IN),
        "stage115": _row(STAGE115_SUMMARY_IN),
        "stage150": _row(STAGE150_SUMMARY_IN),
    }
    if not context["stage150"]:
        raise RuntimeError(f"missing Stage150 summary input: {STAGE150_SUMMARY_IN}")
    routes = _source_routes(context)
    requirements = _manifest_requirements()
    actions = _action_queue(routes)
    stage150 = context["stage150"]
    selected = routes.iloc[0].to_dict()
    side_effect_count = 0
    decision = "stage151_external_source_router_selects_minute_ohlcv_manifest_no_rule"
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "next_best_action": "stage152_authoritative_minute_ohlcv_manifest",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "true_engine_run_count": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "side_effect_count": side_effect_count,
                "source_route_screen_ready": 1,
                "source_route_count": int(len(routes)),
                "data_engineering_route_count": int(routes["procurement_or_backfill_required"].sum()),
                "closed_route_collision_count": int(routes["closed_route_collision"].sum()),
                "rule_feasible_route_count": int(routes["rule_feasible_now"].sum()),
                "current_data_ready_route_count": int(routes["current_local_data_ready"].sum()),
                "selected_next_route": selected["route_id"],
                "selected_next_route_priority_rank": int(selected["priority_rank"]),
                "selected_next_route_rule_feasible_now": int(selected["rule_feasible_now"]),
                "selected_next_route_requires_manifest": int(selected["procurement_or_backfill_required"]),
                "stage152_manifest_requirement_count": int(len(requirements)),
                "stage152_manifest_hard_gate_count": int(requirements["hard_gate"].sum()),
                "stage150_h3_rule_feasible_now": _int(stage150, "h3_rule_feasible_now"),
                "stage150_tail_conflict_cell_count": _int(stage150, "tail_conflict_cell_count"),
                "current_package_promotion_allowed": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "objective_completion_proven": 0,
                "end_equity": float(stage150.get("end_equity", np.nan)),
                "total_return_pct": float(stage150.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(stage150.get("max_drawdown_pct", np.nan)),
                "sharpe": float(stage150.get("sharpe", np.nan)),
                "total_slippage": float(stage150.get("total_slippage", np.nan)),
                "total_trade_count": float(stage150.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(stage150.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(
                    stage150.get("max_broker10_margin_to_equity_pct", np.nan)
                ),
            }
        ]
    )
    gate = _gate_status(summary, routes, requirements)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(routes, ROUTE_OUT)
    _write_csv(requirements, REQUIREMENT_OUT)
    _write_csv(actions, ACTION_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, routes, requirements, actions, gate)
    _plot_path(curve, summary)
    _plot_matrix(
        routes,
        "route_id",
        [
            "point_in_time_possible",
            "minute_or_execution_level",
            "entry_visible_possible",
            "independent_of_final_pnl",
            "universal_cross_product_potential",
            "current_local_data_ready",
            "closed_route_collision",
            "rule_feasible_now",
        ],
        "Stage151 source route score matrix",
        ROUTE_MATRIX_CHART_OUT,
    )
    _plot_priority(routes)
    _plot_matrix(
        requirements,
        "field",
        ["required_for_stage152_manifest", "hard_gate"],
        "Stage152 authoritative minute OHLCV manifest requirements",
        REQUIREMENT_CHART_OUT,
    )
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage151 gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "curve": str(CURVE_IN),
                "stage150_summary": str(STAGE150_SUMMARY_IN),
                "stage150_routes": str(STAGE150_ROUTES_IN),
                "stage099_summary": str(STAGE099_SUMMARY_IN),
                "stage107_summary": str(STAGE107_SUMMARY_IN),
                "stage114_summary": str(STAGE114_SUMMARY_IN),
                "stage115_summary": str(STAGE115_SUMMARY_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "source_route_scorecard": str(ROUTE_OUT),
                "manifest_requirements": str(REQUIREMENT_OUT),
                "next_action_queue": str(ACTION_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(ROUTE_MATRIX_CHART_OUT),
                    str(PRIORITY_CHART_OUT),
                    str(REQUIREMENT_CHART_OUT),
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
                "current_package_promotion_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_TAG = "stage609_independent_risk_slot_next_path_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage609_independent_risk_slot_next_path_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE604_DECISION = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_decision_stage604_low_single_risk_slot_allocator_audit_v1.json"
STAGE604_SLOT_INVENTORY = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_slot_inventory_stage604_low_single_risk_slot_allocator_audit_v1.csv"
STAGE604_ALLOCATOR = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_allocator_scenarios_stage604_low_single_risk_slot_allocator_audit_v1.csv"
STAGE604_ANNUAL = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_annual_capture_stage604_low_single_risk_slot_allocator_audit_v1.csv"
STAGE604_HOLDING = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_holding_boundary_stage604_low_single_risk_slot_allocator_audit_v1.csv"
STAGE604_GATES = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_gates_stage604_low_single_risk_slot_allocator_audit_v1.csv"
STAGE602_FAMILY = OUTPUT_DIR / "qmt_roll_stage602_full57_non_dce_new_family_scout_family_summary_stage602_full57_non_dce_new_family_scout_v1.csv"
STAGE601_FAMILY = OUTPUT_DIR / "qmt_roll_stage601_risk_slot_source_first_rescreen_family_rescreen_stage601_risk_slot_source_first_rescreen_v1.csv"
STAGE597_FAMILY = OUTPUT_DIR / "qmt_roll_stage597_new_family_source_tca_worklist_family_worklist_stage597_new_family_source_tca_worklist_v1.csv"
STAGE597_PRODUCT = OUTPUT_DIR / "qmt_roll_stage597_new_family_source_tca_worklist_product_worklist_stage597_new_family_source_tca_worklist_v1.csv"
STAGE608_DECISION = OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_probe_contract_audit_decision_stage608_readonly_tick_probe_contract_audit_v1.json"

FAMILY_LADDER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_ladder_{MODEL_TAG}.csv"
ACTION_QUEUE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_action_queue_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TARGET_EFFECTIVE_SLOTS = 7
PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0
MAX_CORE_CORR_PREFERRED = 0.10
SOURCE_READY_PCT = 60.0
MATERIAL_FAMILY_PNL = 25_000.0


REFERENCE_LINKS = [
    "Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix",
    "Trend Following, Risk Parity and Momentum in Commodity Futures: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813",
    "pysystemtrade instrument diversification/correlation framework: https://github.com/robcarver17/pysystemtrade",
    "PyPortfolioOpt HRP/covariance tooling: https://github.com/PyPortfolio/PyPortfolioOpt",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _merge_family_context(slot_inventory: pd.DataFrame) -> pd.DataFrame:
    ladder = slot_inventory.copy()
    ladder["product_family"] = ladder["product_family"].astype(str)
    ladder["slot_role"] = ladder["slot_role"].astype(str)
    ladder["best_product"] = ladder["best_product"].astype(str)
    for column in [
        "best_product_pnl",
        "slot_total_pnl_sum",
        "max_abs_core_corr",
        "avg_source_component_pct",
        "structural_slot_now",
        "structural_slot_if_black_ferrous_source_tca_resolved",
        "deployable_selector_slot_now",
    ]:
        ladder[column] = _num(ladder, column)

    stage601 = _read_csv(STAGE601_FAMILY)
    stage601["product_family"] = stage601["product_family"].astype(str)
    keep601 = [
        "product_family",
        "family_positive_pnl_sum",
        "family_total_pnl_sum",
        "family_max_abs_core_corr",
        "capacity_pass_products",
        "source_live_products",
        "avg_source_component_pct",
        "family_status",
        "worklist_reason",
    ]
    stage601 = stage601[[column for column in keep601 if column in stage601.columns]].rename(
        columns={
            "family_positive_pnl_sum": "stage601_positive_pnl_sum",
            "family_total_pnl_sum": "stage601_total_pnl_sum",
            "family_max_abs_core_corr": "stage601_max_abs_core_corr",
            "avg_source_component_pct": "stage601_source_pct",
            "family_status": "stage601_status",
        }
    )
    ladder = ladder.merge(stage601, on="product_family", how="left")

    stage597 = _read_csv(STAGE597_FAMILY)
    stage597["product_family"] = stage597["product_family"].astype(str)
    keep597 = [
        "product_family",
        "capacity_pass_products",
        "source_live_products",
        "avg_source_component_pct",
        "family_status",
        "worklist_reason",
    ]
    stage597 = stage597[[column for column in keep597 if column in stage597.columns]].rename(
        columns={
            "capacity_pass_products": "stage597_capacity_pass_products",
            "source_live_products": "stage597_source_live_products",
            "avg_source_component_pct": "stage597_source_pct",
            "family_status": "stage597_status",
            "worklist_reason": "stage597_worklist_reason",
        }
    )
    ladder = ladder.merge(stage597, on="product_family", how="left")

    stage602 = _read_csv(STAGE602_FAMILY)
    stage602["product_family"] = stage602["product_family"].astype(str)
    keep602 = [
        "product_family",
        "family_status",
        "best_product_total_pnl",
        "positive_noncore_pnl_sum",
        "source_rich_noncore_products",
        "judgement",
    ]
    stage602 = stage602[[column for column in keep602 if column in stage602.columns]].rename(
        columns={
            "family_status": "stage602_status",
            "best_product_total_pnl": "stage602_best_product_total_pnl",
            "positive_noncore_pnl_sum": "stage602_positive_noncore_pnl_sum",
            "source_rich_noncore_products": "stage602_source_rich_noncore_products",
            "judgement": "stage602_judgement",
        }
    )
    ladder = ladder.merge(stage602, on="product_family", how="left")

    for column in [
        "stage601_positive_pnl_sum",
        "stage601_total_pnl_sum",
        "stage601_max_abs_core_corr",
        "stage601_source_pct",
        "stage597_capacity_pass_products",
        "stage597_source_live_products",
        "stage597_source_pct",
        "stage602_best_product_total_pnl",
        "stage602_positive_noncore_pnl_sum",
        "stage602_source_rich_noncore_products",
    ]:
        ladder[column] = _num(ladder, column)

    ladder["evidence_low_corr"] = (ladder["max_abs_core_corr"] <= MAX_CORE_CORR_PREFERRED).astype(int)
    ladder["evidence_material"] = (
        (ladder["slot_total_pnl_sum"] >= MATERIAL_FAMILY_PNL)
        | (ladder["best_product_pnl"] >= 10_000.0)
        | (ladder["stage601_positive_pnl_sum"] >= MATERIAL_FAMILY_PNL)
    ).astype(int)
    ladder["evidence_source"] = (
        (ladder["avg_source_component_pct"] >= SOURCE_READY_PCT)
        | (ladder["stage601_source_pct"] >= SOURCE_READY_PCT)
        | (ladder["stage597_source_pct"] >= SOURCE_READY_PCT)
    ).astype(int)
    ladder["evidence_capacity_hint"] = (ladder["stage597_capacity_pass_products"] > 0).astype(int)
    ladder["evidence_tca"] = 0
    ladder["evidence_new_independent_slot"] = (
        ladder["structural_slot_if_black_ferrous_source_tca_resolved"].gt(ladder["structural_slot_now"])
    ).astype(int)
    ladder["deployable_now"] = ladder["deployable_selector_slot_now"].astype(int)

    def classify(row: pd.Series) -> tuple[str, int, str]:
        role = str(row["slot_role"])
        family = str(row["product_family"])
        if row["structural_slot_now"] >= 1:
            return (
                "P0_existing_slot_needs_execution_source_tca",
                0,
                "先补执行无偏差和source/TCA；它是现有槽，不增加槽数。",
            )
        if role == "p1_new_family_blocked":
            return (
                "P1_new_independent_slot_blocked",
                1,
                "唯一当前可补的新独立槽线索；source/TCA闭合后也只把总槽数从4推到5。",
            )
        if role == "source_rich_no_edge_monitor":
            return (
                "P2_forward_monitor_only",
                2,
                "source和低相关较好，但历史材料性不足；只能低频forward观察，不投入TCA。",
            )
        if role == "reject_high_core_corr":
            return (
                "Reject_high_core_corr",
                4,
                "有收益也不能作为分散槽，压力期可能和核心同向。",
            )
        if family in {"financial_index", "livestock"}:
            return (
                "Observe_no_current_materiality",
                3,
                "当前缺材料性或source/TCA闭环，只保留观察。",
            )
        return (
            "Reject_or_observe",
            5,
            "当前证据不足以进入扩池工作流。",
        )

    classified = ladder.apply(classify, axis=1)
    ladder["next_bucket"] = [item[0] for item in classified]
    ladder["next_rank"] = [item[1] for item in classified]
    ladder["next_reason"] = [item[2] for item in classified]

    readiness_cols = [
        "evidence_low_corr",
        "evidence_material",
        "evidence_source",
        "evidence_capacity_hint",
        "evidence_tca",
        "evidence_new_independent_slot",
    ]
    ladder["readiness_score"] = ladder[readiness_cols].sum(axis=1)
    ladder = ladder.sort_values(["next_rank", "readiness_score", "slot_total_pnl_sum"], ascending=[True, False, False])
    return ladder


def _build_action_queue(ladder: pd.DataFrame, decision604: dict[str, Any], decision608: dict[str, Any]) -> pd.DataFrame:
    current_slots = int(decision604.get("effective_slots_now", 4))
    if_black_slots = int(decision604.get("effective_slots_if_black_ferrous_source_tca_resolved", 5))
    target_slots = int(decision604.get("target_effective_slots", TARGET_EFFECTIVE_SLOTS))
    fresh_tick_gate = 1 if str(decision608.get("decision", "")).endswith("no_live_ticks_yet") is False else 0

    rows = [
        {
            "priority": 0,
            "action_item": "close_execution_no_bias_readonly_tick_tca",
            "scope": "all current/P0 slots",
            "adds_effective_slots": 0,
            "progress_pct": 25.0 if fresh_tick_gate == 0 else 60.0,
            "current_evidence": "Stage608 code-ready dry-run; fresh live ticks/TCA still missing",
            "why": "不先闭合真实快照和TCA，任何扩池都只是纸面可交易。",
            "allowed_now": 1,
        },
        {
            "priority": 1,
            "action_item": "resolve_black_ferrous_source_and_tca",
            "scope": "j.DCE/i.DCE one family slot",
            "adds_effective_slots": max(0, if_black_slots - current_slots),
            "progress_pct": 35.0,
            "current_evidence": "low core corr, some materiality; DCE member/warehouse and TCA blocked",
            "why": "这是当前唯一能把4槽推进到5槽的新独立风险族。",
            "allowed_now": 1,
        },
        {
            "priority": 2,
            "action_item": "forward_monitor_source_rich_low_corr_families",
            "scope": "soft_agri / precious_metals",
            "adds_effective_slots": 0,
            "progress_pct": 30.0,
            "current_evidence": "source rich and low corr; historical materiality weak",
            "why": "不能用历史回测硬救，只能累计point-in-time状态和趋势机会。",
            "allowed_now": 1,
        },
        {
            "priority": 3,
            "action_item": "search_two_new_non_dce_independent_drivers",
            "scope": "outside current full57 evidence or new data routes",
            "adds_effective_slots": max(0, target_slots - if_black_slots),
            "progress_pct": 0.0,
            "current_evidence": "Stage602 full57 non-DCE scout found 0 deployable new families",
            "why": "即便j/i闭合也只有5槽，目标7槽仍差2个。",
            "allowed_now": 1,
        },
        {
            "priority": 4,
            "action_item": "reject_high_corr_material_winners",
            "scope": "rubber/br and similar",
            "adds_effective_slots": 0,
            "progress_pct": 100.0,
            "current_evidence": "br.SHFE profitable but core corr 0.2783",
            "why": "收益赢家不等于独立风险槽；压力期共振会放大尾部。",
            "allowed_now": 0,
        },
    ]
    return pd.DataFrame(rows)


def _build_gates(decision604: dict[str, Any], ladder: pd.DataFrame, action_queue: pd.DataFrame) -> pd.DataFrame:
    current_slots = int(decision604.get("effective_slots_now", 4))
    if_black_slots = int(decision604.get("effective_slots_if_black_ferrous_source_tca_resolved", 5))
    deployable_now = int(decision604.get("deployable_selector_slots_now", 0))
    annual_positive = int(decision604.get("annual_top6_positive_years", 0))
    annual_years = int(decision604.get("annual_top6_years", 7))
    source_rich_monitor_count = int(ladder["next_bucket"].eq("P2_forward_monitor_only").sum())

    rows = [
        {
            "gate": "breadth_thesis_still_valid",
            "actual": f"{annual_positive}/{annual_years} annual top6 positive",
            "threshold": "annual top6 opportunity exists",
            "passed": int(annual_positive == annual_years and annual_years > 0),
            "hard_gate": 0,
            "judgement": "年度非核心趋势机会存在，方向不是空想。",
        },
        {
            "gate": "current_slots_sufficient",
            "actual": f"{current_slots}/{TARGET_EFFECTIVE_SLOTS}",
            "threshold": f">={TARGET_EFFECTIVE_SLOTS}",
            "passed": int(current_slots >= TARGET_EFFECTIVE_SLOTS),
            "hard_gate": 1,
            "judgement": "当前有效槽太少，单槽风险仍高。",
        },
        {
            "gate": "after_black_ferrous_sufficient",
            "actual": f"{if_black_slots}/{TARGET_EFFECTIVE_SLOTS}",
            "threshold": f">={TARGET_EFFECTIVE_SLOTS}",
            "passed": int(if_black_slots >= TARGET_EFFECTIVE_SLOTS),
            "hard_gate": 0,
            "judgement": "j/i补完也只到5槽，仍差2个新独立族。",
        },
        {
            "gate": "deployable_selector_slots_now",
            "actual": f"{deployable_now}",
            "threshold": ">0 only after source/TCA/live context",
            "passed": int(deployable_now > 0),
            "hard_gate": 1,
            "judgement": "现在不能发布白名单或paper selector。",
        },
        {
            "gate": "new_independent_slot_candidate_exists",
            "actual": f"{int(ladder['next_bucket'].eq('P1_new_independent_slot_blocked').sum())}",
            "threshold": ">=1 worklist candidate",
            "passed": int(ladder["next_bucket"].eq("P1_new_independent_slot_blocked").sum() >= 1),
            "hard_gate": 0,
            "judgement": "black_ferrous 是可继续补证线索，不是可交易版本。",
        },
        {
            "gate": "source_rich_monitor_queue_exists",
            "actual": f"{source_rich_monitor_count}",
            "threshold": ">=1 forward monitor family",
            "passed": int(source_rich_monitor_count >= 1),
            "hard_gate": 0,
            "judgement": "有低频观察队列，但不能当历史alpha。",
        },
        {
            "gate": "blind_backtest_allowed",
            "actual": "0",
            "threshold": "must remain 0",
            "passed": 1,
            "hard_gate": 1,
            "judgement": "本阶段没有宽池收益扫描，没有白名单。",
        },
        {
            "gate": "two_new_slots_identified",
            "actual": f"{max(0, TARGET_EFFECTIVE_SLOTS - if_black_slots)} missing after j/i",
            "threshold": "0 missing",
            "passed": int(if_black_slots >= TARGET_EFFECTIVE_SLOTS),
            "hard_gate": 1,
            "judgement": "当前证据仍无法找齐目标7槽。",
        },
    ]
    return pd.DataFrame(rows)


def _make_chart(ladder: pd.DataFrame, action_queue: pd.DataFrame, gates: pd.DataFrame, decision604: dict[str, Any]) -> None:
    plt.rcParams["font.family"] = "Arial Unicode MS"
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(
        "Stage609 independent risk-slot path: breadth thesis valid, deployment still blocked by slots/source/TCA",
        fontsize=15,
        fontweight="bold",
    )

    ax = axes[0, 0]
    current_slots = float(decision604.get("effective_slots_now", 4))
    if_black_slots = float(decision604.get("effective_slots_if_black_ferrous_source_tca_resolved", 5))
    target_slots = float(decision604.get("target_effective_slots", TARGET_EFFECTIVE_SLOTS))
    bars = ax.bar(
        ["current", "+ j/i resolved", "target"],
        [current_slots, if_black_slots, target_slots],
        color=["#3182ce", "#dd6b20", "#2f855a"],
    )
    ax.axhline(target_slots, color="#2f855a", linestyle="--", linewidth=1)
    ax.set_ylim(0, max(target_slots + 1, 8))
    ax.set_ylabel("effective independent risk slots")
    ax.set_title("Slot count, not product count, controls single-risk budget")
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15, f"{bar.get_height():.0f}", ha="center", fontsize=11)
    ax.text(0.05, 0.90, "4 slots = about 25% per slot\n7 slots = about 14.3% per slot", transform=ax.transAxes, fontsize=10)

    ax = axes[0, 1]
    color_map = {
        "P0_existing_slot_needs_execution_source_tca": "#3182ce",
        "P1_new_independent_slot_blocked": "#dd6b20",
        "P2_forward_monitor_only": "#805ad5",
        "Reject_high_core_corr": "#e53e3e",
        "Observe_no_current_materiality": "#718096",
        "Reject_or_observe": "#a0aec0",
    }
    plot_ladder = ladder.copy()
    plot_ladder["scatter_x"] = plot_ladder["max_abs_core_corr"].clip(lower=0.0, upper=0.35)
    plot_ladder["scatter_y"] = plot_ladder["slot_total_pnl_sum"].clip(lower=-20_000, upper=120_000)
    for bucket, group in plot_ladder.groupby("next_bucket"):
        ax.scatter(
            group["scatter_x"],
            group["scatter_y"],
            s=90 + group["readiness_score"] * 35,
            alpha=0.82,
            label=bucket.replace("_", " "),
            color=color_map.get(bucket, "#a0aec0"),
            edgecolor="#1a202c",
            linewidth=0.5,
        )
        for row in group.itertuples(index=False):
            ax.text(row.scatter_x + 0.004, row.scatter_y + 1500, str(row.product_family), fontsize=8)
    ax.axvline(MAX_CORE_CORR_PREFERRED, color="#e53e3e", linestyle="--", linewidth=1)
    ax.axhline(MATERIAL_FAMILY_PNL, color="#2f855a", linestyle="--", linewidth=1)
    ax.set_xlabel("max abs correlation vs core")
    ax.set_ylabel("slot/family opportunity pnl proxy")
    ax.set_title("Independent-slot candidates must pass correlation and materiality")
    ax.legend(fontsize=7, loc="upper right")

    ax = axes[1, 0]
    heat_cols = [
        "evidence_low_corr",
        "evidence_material",
        "evidence_source",
        "evidence_capacity_hint",
        "evidence_tca",
        "evidence_new_independent_slot",
    ]
    heat = ladder.sort_values(["next_rank", "product_family"])[["product_family", *heat_cols]].set_index("product_family")
    matrix = heat.to_numpy(dtype=float)
    ax.imshow(matrix, aspect="auto", cmap=matplotlib.colors.ListedColormap(["#fed7d7", "#9ae6b4"]), vmin=0, vmax=1)
    ax.set_xticks(range(len(heat_cols)))
    ax.set_xticklabels(["low corr", "material", "source", "capacity", "TCA", "new slot"], rotation=35, ha="right")
    ax.set_yticks(range(len(heat.index)))
    ax.set_yticklabels(heat.index, fontsize=8)
    ax.set_title("Readiness heatmap: TCA is still red everywhere")
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            ax.text(x, y, "1" if matrix[y, x] else "0", ha="center", va="center", fontsize=8)

    ax = axes[1, 1]
    queue = action_queue.sort_values("priority", ascending=False)
    colors = ["#2f855a" if item >= 80 else "#dd6b20" if item >= 30 else "#e53e3e" for item in queue["progress_pct"]]
    ax.barh(queue["action_item"], queue["progress_pct"], color=colors)
    ax.set_xlim(0, 105)
    ax.set_xlabel("evidence progress pct")
    ax.set_title("Next path: source/TCA first, not blind expansion")
    for row in queue.itertuples(index=False):
        ax.text(float(row.progress_pct) + 2, row.Index if hasattr(row, "Index") else 0, "", fontsize=1)
    for idx, row in enumerate(queue.itertuples(index=False)):
        ax.text(row.progress_pct + 1.5, idx, f"+{row.adds_effective_slots} slot", va="center", fontsize=8)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    ladder: pd.DataFrame,
    action_queue: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage609 Independent Risk Slot Next Path Audit",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- generated_at：`{decision['generated_at']}`",
        f"- decision：`{decision['decision']}`",
        f"- promotion_allowed：`{decision['promotion_allowed']}`",
        f"- paper_selector_allowed：`{decision['paper_selector_allowed']}`",
        f"- trading_whitelist_allowed：`{decision['trading_whitelist_allowed']}`",
        f"- hard_gates：`{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## 外部调研判断",
        "",
        "- 趋势组合研究支持扩大市场集合，但前提是波动、相关、流动性和交易成本共同约束。",
        "- 风险预算/HRP/maximum diversification 的思想支持用相关性管理组合风险，但本仓库不能直接套黑箱优化器。",
        "- 本阶段判断：用户提出的“低单笔风险 + 扩池 + 避免高相关 + 选对品种”方向继续成立；但选品必须先表现为独立风险槽和 point-in-time source/TCA 证据，而不是历史赢家白名单。",
        "",
        "参考：",
        *[f"- {link}" for link in REFERENCE_LINKS],
        "",
        "## 本阶段做了什么",
        "",
        "- 只读合成 Stage597/601/602/604/608 证据。",
        "- 不重放交易引擎、不改策略、不扫宽池收益、不生成白名单。",
        "- 把扩池下一步拆成：现有P0补证、P1新独立槽、P2低频forward monitor、高相关拒绝。",
        "",
        "## 风险槽候选阶梯",
        "",
        _md_table(
            ladder,
            [
                "product_family",
                "slot_role",
                "best_product",
                "slot_total_pnl_sum",
                "max_abs_core_corr",
                "avg_source_component_pct",
                "readiness_score",
                "next_bucket",
                "next_reason",
            ],
        ),
        "",
        "## 下一步行动队列",
        "",
        _md_table(
            action_queue,
            [
                "priority",
                "action_item",
                "scope",
                "adds_effective_slots",
                "progress_pct",
                "allowed_now",
                "why",
            ],
        ),
        "",
        "## 闸门",
        "",
        _md_table(gates, ["gate", "actual", "threshold", "passed", "hard_gate", "judgement"]),
        "",
        "## 结论",
        "",
        f"- 当前有效独立风险槽仍为 `{decision['effective_slots_now']}`，目标 `{decision['target_effective_slots']}`；当前单槽风险约 `{decision['single_slot_risk_pct_now']:.2f}%`。",
        f"- `black_ferrous(j/i)` 是当前唯一能新增独立槽的线索，但补完 source/TCA 也只是 `{decision['effective_slots_if_black_ferrous_source_tca_resolved']}` 槽，仍差 `{decision['slots_gap_if_black_ferrous_resolved']}` 槽。",
        "- `soft_agri/precious_metals` 属于低相关、source较好但历史机会不足的观察队列；现在投入TCA或历史回测会变成数据可得性过拟合。",
        "- `rubber/br` 这类有收益但核心相关偏高的品种继续拒绝，不能用历史赢家冒充分散。",
        "- 因此下一步不是扩名单，而是：先闭合执行无偏差/TCA；并行补 `j/i` source/TCA；再用forward ledger寻找两个真正新独立驱动。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段不根据收益挑白名单，只把已有证据拆成风险槽、source、TCA和相关性。",
        "- 运行后判断：否。高收益高相关的 `br.SHFE` 被继续拒绝，source好但无材料性的族不投入TCA，说明没有用历史赢家救结果。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。该阶段把用户的扩池直觉转成可执行证据队列。",
        "- 运行后判断：有价值但必须收敛。扩池方向值得继续，但只能沿 source/TCA/forward monitor 推进，不能宽池回测。",
        "",
        "## 输出文件",
        "",
        f"- family_ladder：`{FAMILY_LADDER_PATH}`",
        f"- action_queue：`{ACTION_QUEUE_PATH}`",
        f"- gates：`{GATES_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    decision604 = _read_json(STAGE604_DECISION)
    decision608 = _read_json(STAGE608_DECISION)
    slot_inventory = _read_csv(STAGE604_SLOT_INVENTORY)
    allocator = _read_csv(STAGE604_ALLOCATOR)
    _read_csv(STAGE604_ANNUAL)
    _read_csv(STAGE604_HOLDING)
    _read_csv(STAGE604_GATES)
    _read_csv(STAGE597_FAMILY)
    _read_csv(STAGE597_PRODUCT)

    ladder = _merge_family_context(slot_inventory)
    action_queue = _build_action_queue(ladder, decision604, decision608)
    gates = _build_gates(decision604, ladder, action_queue)

    hard = gates[gates["hard_gate"].astype(int).eq(1)]
    hard_passed = int(hard["passed"].astype(int).sum())
    hard_total = int(len(hard))
    effective_slots_now = int(decision604.get("effective_slots_now", 4))
    effective_slots_if_black = int(decision604.get("effective_slots_if_black_ferrous_source_tca_resolved", 5))
    target_slots = int(decision604.get("target_effective_slots", TARGET_EFFECTIVE_SLOTS))

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "decision": "breadth_thesis_valid_next_path_source_tca_forward_monitor_no_backtest",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "new_backtest_run": False,
        "strategy_changed": False,
        "effective_slots_now": effective_slots_now,
        "effective_slots_if_black_ferrous_source_tca_resolved": effective_slots_if_black,
        "target_effective_slots": target_slots,
        "slots_gap_now": max(0, target_slots - effective_slots_now),
        "slots_gap_if_black_ferrous_resolved": max(0, target_slots - effective_slots_if_black),
        "single_slot_risk_pct_now": 100.0 / effective_slots_now if effective_slots_now else None,
        "single_slot_risk_pct_if_black_ferrous_resolved": 100.0 / effective_slots_if_black if effective_slots_if_black else None,
        "preferred_single_slot_risk_pct": PREFERRED_SINGLE_SLOT_RISK_PCT,
        "deployable_selector_slots_now": int(decision604.get("deployable_selector_slots_now", 0)),
        "p1_new_independent_slot_candidates": int(ladder["next_bucket"].eq("P1_new_independent_slot_blocked").sum()),
        "p2_forward_monitor_families": int(ladder["next_bucket"].eq("P2_forward_monitor_only").sum()),
        "blind_backtest_run": False,
        "hard_gates_passed": hard_passed,
        "hard_gates_total": hard_total,
        "failed_hard_gates": hard_total - hard_passed,
        "visual_chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
    }

    ladder.to_csv(FAMILY_LADDER_PATH, index=False, encoding="utf-8-sig")
    action_queue.to_csv(ACTION_QUEUE_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _make_chart(ladder, action_queue, gates, decision604)
    _write_report(ladder, action_queue, gates, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

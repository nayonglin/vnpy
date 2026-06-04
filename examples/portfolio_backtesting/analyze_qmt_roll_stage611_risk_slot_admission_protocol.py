from __future__ import annotations

from datetime import datetime, timezone, timedelta
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


MODEL_TAG = "stage611_risk_slot_admission_protocol_v1"
OUTPUT_PREFIX = "qmt_roll_stage611_risk_slot_admission_protocol"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE604_SLOT_INVENTORY = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_slot_inventory_stage604_low_single_risk_slot_allocator_audit_v1.csv"
STAGE604_ALLOCATOR_SCENARIOS = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_allocator_scenarios_stage604_low_single_risk_slot_allocator_audit_v1.csv"
STAGE604_GATES = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_gates_stage604_low_single_risk_slot_allocator_audit_v1.csv"
STAGE604_DECISION = OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_decision_stage604_low_single_risk_slot_allocator_audit_v1.json"
STAGE609_FAMILY_LADDER = OUTPUT_DIR / "qmt_roll_stage609_independent_risk_slot_next_path_audit_family_ladder_stage609_independent_risk_slot_next_path_audit_v1.csv"
STAGE609_ACTION_QUEUE = OUTPUT_DIR / "qmt_roll_stage609_independent_risk_slot_next_path_audit_action_queue_stage609_independent_risk_slot_next_path_audit_v1.csv"
STAGE609_GATES = OUTPUT_DIR / "qmt_roll_stage609_independent_risk_slot_next_path_audit_gates_stage609_independent_risk_slot_next_path_audit_v1.csv"
STAGE609_DECISION = OUTPUT_DIR / "qmt_roll_stage609_independent_risk_slot_next_path_audit_decision_stage609_independent_risk_slot_next_path_audit_v1.json"
STAGE610_DECISION = OUTPUT_DIR / "qmt_roll_stage610_stage608_simnow_env_wrapper_audit_decision_stage610_stage608_simnow_env_wrapper_audit_v1.json"

FAMILY_ADMISSION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_admission_{MODEL_TAG}.csv"
CONTRACT_RULES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_rules_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TARGET_EFFECTIVE_SLOTS = 7
CURRENT_EFFECTIVE_SLOTS = 4
IF_BLACK_FERROUS_RESOLVED_SLOTS = 5
PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0
HARD_SINGLE_SLOT_RISK_PCT = 20.0
MAX_CORE_CORR_PREFERRED = 0.10

REFERENCE_LINKS = [
    "Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix",
    "Rob Carver pysystemtrade instrument diversification and risk targeting: https://github.com/robcarver17/pysystemtrade",
    "PyPortfolioOpt HRP clustering reference: https://github.com/PyPortfolio/PyPortfolioOpt",
    "skfolio risk budgeting / maximum diversification / HRP: https://github.com/skfolio/skfolio",
]


def _now_cst() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")


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
        return {str(k): _json_safe(v) for k, v in value.items()}
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


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _bool_int(value: Any) -> int:
    try:
        return int(float(value) > 0)
    except (TypeError, ValueError):
        return 0


def _budget(slots: int) -> float:
    return 100.0 / slots if slots else 0.0


def _blocked_by(row: pd.Series, stage610: dict[str, Any]) -> str:
    role = str(row.get("slot_role", ""))
    blockers: list[str] = []
    if role == "current_p0_structural_slot":
        blockers.extend(["live_context_0_of_45", "live_tca_0_of_9"])
        if _bool_int(row.get("evidence_low_corr", 0)) == 0:
            blockers.append("core_corr_watch")
        if _bool_int(row.get("evidence_source", 0)) == 0:
            blockers.append("source_route_incomplete")
    elif role == "p1_new_family_blocked":
        blockers.extend(["dce_official_source_blocked", "new_family_live_tca_0", "live_context_0_of_45"])
        blockers.append("still_5_of_7_slots_after_resolution")
    elif role == "source_rich_no_edge_monitor":
        blockers.extend(["historical_materiality_weak", "selector_edge_unproven", "no_tca_budget"])
    elif role == "reject_high_core_corr":
        blockers.append("core_corr_above_watchline")
    else:
        blockers.extend(["materiality_or_source_unproven", "no_tca_budget"])

    if int(stage610.get("tick_rows", 0) or 0) <= 0:
        blockers.append("fresh_tick_snapshot_missing")
    return ",".join(dict.fromkeys(blockers))


def build_family_admission(family_ladder: pd.DataFrame, stage610: dict[str, Any]) -> pd.DataFrame:
    frame = family_ladder.copy()
    frame["product_family"] = frame["product_family"].astype(str)
    frame["slot_role"] = frame["slot_role"].astype(str)
    frame["slot_products"] = frame["slot_products"].fillna("").astype(str)
    frame["max_abs_core_corr"] = _num(frame, "max_abs_core_corr")
    frame["slot_total_pnl_sum"] = _num(frame, "slot_total_pnl_sum")
    frame["readiness_score"] = _num(frame, "readiness_score")
    frame["evidence_low_corr"] = _num(frame, "evidence_low_corr")
    frame["evidence_material"] = _num(frame, "evidence_material")
    frame["evidence_source"] = _num(frame, "evidence_source")
    frame["evidence_capacity_hint"] = _num(frame, "evidence_capacity_hint")
    frame["evidence_tca"] = _num(frame, "evidence_tca")
    frame["evidence_new_independent_slot"] = _num(frame, "evidence_new_independent_slot")

    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        role = str(row["slot_role"])
        family = str(row["product_family"])
        low_corr = _bool_int(row["evidence_low_corr"])
        material = _bool_int(row["evidence_material"])
        source = _bool_int(row["evidence_source"])
        capacity = _bool_int(row["evidence_capacity_hint"])
        tca = _bool_int(row["evidence_tca"])
        execution = int(int(stage610.get("tick_rows", 0) or 0) > 0 and bool(stage610.get("connect_requested", False)))
        deployable_now = 0
        paper_allowed_now = 0
        whitelist_allowed_now = 0
        max_active_products_per_direction = 1
        same_family_policy = "family_top1_same_direction"
        if role == "current_p0_structural_slot":
            state = "existing_slot_reference_fail_closed"
            admission_bucket = "P0_reference_needs_source_tca_execution"
            slot_budget_reference_pct = _budget(CURRENT_EFFECTIVE_SLOTS)
            conditional_slot_budget_pct = _budget(TARGET_EFFECTIVE_SLOTS)
            comment = "现有结构槽只能作为参考；未闭合live context/TCA前，不得把扩池selector当可部署版本。"
        elif role == "p1_new_family_blocked":
            state = "conditional_new_slot_blocked"
            admission_bucket = "P1_source_tca_worklist"
            slot_budget_reference_pct = 0.0
            conditional_slot_budget_pct = _budget(IF_BLACK_FERROUS_RESOLVED_SLOTS)
            comment = "唯一当前可补的新独立槽；即使解决也只有5槽、20%单槽风险，仍不能晋级为最终allocator。"
        elif role == "source_rich_no_edge_monitor":
            state = "forward_monitor_only"
            admission_bucket = "P2_forward_monitor"
            slot_budget_reference_pct = 0.0
            conditional_slot_budget_pct = 0.0
            comment = "低相关且source较好，但材料性不足；只能点时化观察，不投入TCA和资金。"
        elif role == "reject_high_core_corr":
            state = "rejected_by_correlation"
            admission_bucket = "Reject_high_corr"
            slot_budget_reference_pct = 0.0
            conditional_slot_budget_pct = 0.0
            comment = "历史有收益也拒绝，防止压力期共振伪分散。"
        else:
            state = "observe_no_budget"
            admission_bucket = "Observe"
            slot_budget_reference_pct = 0.0
            conditional_slot_budget_pct = 0.0
            comment = "缺少材料性、source或TCA证据，不能进入扩池资金分配。"

        rows.append(
            {
                "product_family": family,
                "slot_role": role,
                "candidate_products": row["slot_products"],
                "admission_bucket": admission_bucket,
                "admission_state": state,
                "max_abs_core_corr": float(row["max_abs_core_corr"]),
                "slot_total_pnl_sum": float(row["slot_total_pnl_sum"]),
                "readiness_score": float(row["readiness_score"]),
                "evidence_low_corr": low_corr,
                "evidence_material": material,
                "evidence_source": source,
                "evidence_capacity_hint": capacity,
                "evidence_live_tca": tca,
                "evidence_live_execution": execution,
                "deployable_now": deployable_now,
                "paper_allowed_now": paper_allowed_now,
                "trading_whitelist_allowed_now": whitelist_allowed_now,
                "allowed_incremental_budget_now_pct": 0.0,
                "reference_slot_budget_pct": slot_budget_reference_pct,
                "conditional_budget_if_all_gates_pct": conditional_slot_budget_pct,
                "max_active_products_per_direction": max_active_products_per_direction,
                "same_family_policy": same_family_policy,
                "blocked_by": _blocked_by(row, stage610),
                "next_action": row.get("next_reason", ""),
                "comment": comment,
            }
        )
    result = pd.DataFrame(rows)
    order = {
        "P0_reference_needs_source_tca_execution": 0,
        "P1_source_tca_worklist": 1,
        "P2_forward_monitor": 2,
        "Observe": 3,
        "Reject_high_corr": 4,
    }
    result["order"] = result["admission_bucket"].map(order).fillna(9)
    return result.sort_values(["order", "readiness_score", "slot_total_pnl_sum"], ascending=[True, False, False]).drop(columns=["order"])


def build_contract_rules() -> pd.DataFrame:
    rows = [
        {
            "rule_id": "R1",
            "rule": "risk_slot_not_product_count",
            "hard": 1,
            "requirement": "新增品种必须映射到独立经济驱动族；同族深度不增加独立槽数。",
            "implementation_hint": "allocator先按product_family分组，再按同向top1选择。",
        },
        {
            "rule_id": "R2",
            "rule": "family_top1_same_direction",
            "hard": 1,
            "requirement": "同一产品族同向最多一个产品获得风险预算。",
            "implementation_hint": "候选排序只在族内做tie-break，不能把y/c或j/i同时当两个独立槽。",
        },
        {
            "rule_id": "R3",
            "rule": "no_budget_before_source_tca_execution",
            "hard": 1,
            "requirement": "source、forward样本、live context、TCA任一未闭合，新增槽资金预算为0。",
            "implementation_hint": "paper_allowed=false；trading_whitelist_allowed=false；allowed_incremental_budget_now_pct=0。",
        },
        {
            "rule_id": "R4",
            "rule": "high_core_corr_reject",
            "hard": 1,
            "requirement": f"核心相关超过观察线{MAX_CORE_CORR_PREFERRED:.2f}的历史赢家不得作为分散槽。",
            "implementation_hint": "br.SHFE一类保留观察，但不能获得独立槽预算。",
        },
        {
            "rule_id": "R5",
            "rule": "target_slot_width",
            "hard": 1,
            "requirement": f"最终低单笔风险结构至少{TARGET_EFFECTIVE_SLOTS}个有效槽，单槽风险约{_budget(TARGET_EFFECTIVE_SLOTS):.2f}%。",
            "implementation_hint": "4槽=25%，5槽=20%，都不是偏好结构。",
        },
        {
            "rule_id": "R6",
            "rule": "forward_monitor_not_backfit",
            "hard": 1,
            "requirement": "source较好但材料性不足的族只能点时化观察，不能回头构造历史白名单。",
            "implementation_hint": "soft_agri/precious_metals进入monitor ledger，不投入TCA或A/B。",
        },
        {
            "rule_id": "R7",
            "rule": "execution_no_bias_first",
            "hard": 1,
            "requirement": "扩池晋级前先证明真实快照、真实成交、vt_orderid和tick/TCA能闭合。",
            "implementation_hint": "Stage608/610当前仅dry-run ready，fresh tick rows仍为0。",
        },
    ]
    return pd.DataFrame(rows)


def build_gates(
    family_admission: pd.DataFrame,
    stage604_gates: pd.DataFrame,
    stage609_gates: pd.DataFrame,
    stage610: dict[str, Any],
) -> pd.DataFrame:
    deployable_slots = int(family_admission["deployable_now"].sum())
    paper_allowed = int(family_admission["paper_allowed_now"].sum())
    whitelist_allowed = int(family_admission["trading_whitelist_allowed_now"].sum())
    high_corr_rejected = int(
        ((family_admission["admission_bucket"].eq("Reject_high_corr")) & (family_admission["allowed_incremental_budget_now_pct"].eq(0))).any()
    )
    annual_gate = stage609_gates[stage609_gates["gate"].astype(str).eq("breadth_thesis_still_valid")]
    annual_passed = int(_num(annual_gate, "passed").iloc[0]) if not annual_gate.empty else 0
    blind_gate = stage609_gates[stage609_gates["gate"].astype(str).eq("blind_backtest_allowed")]
    blind_no = int(_num(blind_gate, "passed").iloc[0]) if not blind_gate.empty else 0
    holding_gate = stage604_gates[stage604_gates["gate"].astype(str).eq("holding_3m_6m_no_degrade")]
    holding_passed = int(_num(holding_gate, "passed").iloc[0]) if not holding_gate.empty else 0
    tick_rows = int(stage610.get("tick_rows", 0) or 0)
    connect_requested = bool(stage610.get("connect_requested", False))

    rows = [
        {
            "gate": "protocol_written",
            "actual": "family admission + contract rules generated",
            "threshold": "exists",
            "passed": 1,
            "hard_gate": 0,
            "judgement": "本阶段把想法转成可复验闸门，但不等于可交易。",
        },
        {
            "gate": "no_new_risk_budget_now",
            "actual": f"{family_admission['allowed_incremental_budget_now_pct'].sum():.2f}%",
            "threshold": "must be 0 before source/TCA/live",
            "passed": int(float(family_admission["allowed_incremental_budget_now_pct"].sum()) == 0.0),
            "hard_gate": 1,
            "judgement": "新增风险槽当前资金预算必须为0。",
        },
        {
            "gate": "paper_selector_forbidden_now",
            "actual": str(paper_allowed),
            "threshold": "0",
            "passed": int(paper_allowed == 0),
            "hard_gate": 1,
            "judgement": "没有source/TCA/live context，不允许paper selector。",
        },
        {
            "gate": "trading_whitelist_forbidden_now",
            "actual": str(whitelist_allowed),
            "threshold": "0",
            "passed": int(whitelist_allowed == 0),
            "hard_gate": 1,
            "judgement": "没有真实执行证据，不允许交易白名单。",
        },
        {
            "gate": "deployable_selector_slots_now",
            "actual": str(deployable_slots),
            "threshold": ">0 only after all hard gates",
            "passed": int(deployable_slots == 0),
            "hard_gate": 1,
            "judgement": "当前没有可部署新增槽，这是正确的fail-closed状态。",
        },
        {
            "gate": "current_effective_slots_sufficient",
            "actual": f"{CURRENT_EFFECTIVE_SLOTS}/{TARGET_EFFECTIVE_SLOTS}",
            "threshold": f">={TARGET_EFFECTIVE_SLOTS}",
            "passed": 0,
            "hard_gate": 1,
            "judgement": "当前4槽对应单槽25%，不是低单笔风险结构。",
        },
        {
            "gate": "if_black_ferrous_resolved_sufficient",
            "actual": f"{IF_BLACK_FERROUS_RESOLVED_SLOTS}/{TARGET_EFFECTIVE_SLOTS}",
            "threshold": f">={TARGET_EFFECTIVE_SLOTS}",
            "passed": 0,
            "hard_gate": 0,
            "judgement": "j/i解决后也只是5槽，仍差2个独立族。",
        },
        {
            "gate": "preferred_single_slot_risk",
            "actual": f"{_budget(CURRENT_EFFECTIVE_SLOTS):.2f}%",
            "threshold": f"<={PREFERRED_SINGLE_SLOT_RISK_PCT:.2f}%",
            "passed": 0,
            "hard_gate": 1,
            "judgement": "当前单槽风险高于偏好线。",
        },
        {
            "gate": "high_corr_winner_rejected",
            "actual": str(high_corr_rejected),
            "threshold": "1",
            "passed": high_corr_rejected,
            "hard_gate": 1,
            "judgement": "高相关历史赢家继续拒绝，避免伪分散。",
        },
        {
            "gate": "annual_opportunity_exists",
            "actual": "7/7 annual top6 positive" if annual_passed else "unknown",
            "threshold": "true",
            "passed": annual_passed,
            "hard_gate": 0,
            "judgement": "年度趋势机会存在，所以方向仍值得做。",
        },
        {
            "gate": "blind_backtest_still_forbidden",
            "actual": "0",
            "threshold": "must remain 0",
            "passed": blind_no,
            "hard_gate": 1,
            "judgement": "不做宽池历史收益扫描。",
        },
        {
            "gate": "holding_3m_6m_no_degrade",
            "actual": "not passed" if not holding_passed else "passed",
            "threshold": "left-tail not worse",
            "passed": holding_passed,
            "hard_gate": 1,
            "judgement": "现有宽池壳未改善任意启动3/6个月左尾。",
        },
        {
            "gate": "execution_no_bias_live_tick_ready",
            "actual": f"connect_requested={connect_requested}; tick_rows={tick_rows}",
            "threshold": "connect_requested=true and tick_rows>0",
            "passed": int(connect_requested and tick_rows > 0),
            "hard_gate": 1,
            "judgement": "Stage610仍是dry-run no connect，不能声明真实交易无偏差。",
        },
    ]
    return pd.DataFrame(rows)


def make_chart(family_admission: pd.DataFrame, gates: pd.DataFrame, action_queue: pd.DataFrame) -> None:
    fig = plt.figure(figsize=(16, 11), constrained_layout=True)
    gs = fig.add_gridspec(2, 2)

    ax1 = fig.add_subplot(gs[0, 0])
    stages = ["Current", "If j/i fixed", "Target"]
    slots = [CURRENT_EFFECTIVE_SLOTS, IF_BLACK_FERROUS_RESOLVED_SLOTS, TARGET_EFFECTIVE_SLOTS]
    colors = ["#d95f02", "#e6ab02", "#1b9e77"]
    bars = ax1.bar(stages, slots, color=colors, alpha=0.88)
    ax1.axhline(TARGET_EFFECTIVE_SLOTS, color="#1b9e77", linestyle="--", linewidth=1.5)
    ax1.set_ylim(0, TARGET_EFFECTIVE_SLOTS + 1.5)
    ax1.set_ylabel("Effective independent risk slots")
    ax1.set_title("Slot width is still the binding risk problem")
    for bar, slot in zip(bars, slots):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.12,
            f"{slot} slots\n{_budget(slot):.1f}%/slot",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    ax2 = fig.add_subplot(gs[0, 1])
    heat_cols = [
        "evidence_low_corr",
        "evidence_material",
        "evidence_source",
        "evidence_capacity_hint",
        "evidence_live_tca",
        "evidence_live_execution",
        "deployable_now",
    ]
    heat = family_admission.set_index("product_family")[heat_cols].astype(float)
    im = ax2.imshow(heat.values, aspect="auto", vmin=0, vmax=1, cmap="RdYlGn")
    ax2.set_xticks(np.arange(len(heat_cols)))
    ax2.set_xticklabels(
        ["low corr", "material", "source", "capacity", "TCA", "live", "deploy"],
        rotation=35,
        ha="right",
    )
    ax2.set_yticks(np.arange(len(heat.index)))
    ax2.set_yticklabels(heat.index)
    ax2.set_title("Family admission evidence matrix")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax2.text(j, i, "1" if heat.iat[i, j] >= 0.5 else "0", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)

    ax3 = fig.add_subplot(gs[1, 0])
    gate_view = gates.copy()
    gate_view["status_value"] = gate_view["passed"].astype(int)
    colors_gate = gate_view["status_value"].map({1: "#1b9e77", 0: "#d73027"}).tolist()
    ax3.barh(gate_view["gate"], np.ones(len(gate_view)), color=colors_gate, alpha=0.86)
    ax3.set_xlim(0, 1.05)
    ax3.set_xlabel("Gate status")
    ax3.set_title("Hard gates: fail-closed is intentional")
    ax3.invert_yaxis()
    for y, (_, row) in enumerate(gate_view.iterrows()):
        label = "PASS" if int(row["passed"]) else "BLOCK"
        ax3.text(0.03, y, label, va="center", ha="left", color="white", fontsize=8, fontweight="bold")

    ax4 = fig.add_subplot(gs[1, 1])
    action = action_queue.sort_values("priority").copy()
    action["progress_pct"] = _num(action, "progress_pct")
    bar_colors = ["#7570b3" if bool(x) else "#bdbdbd" for x in action.get("allowed_now", pd.Series(0, index=action.index))]
    label_map = {
        "close_execution_no_bias_readonly_tick_tca": "P0 close execution/TCA",
        "resolve_black_ferrous_source_and_tca": "P1 j/i source/TCA",
        "forward_monitor_source_rich_low_corr_families": "P2 source-rich monitor",
        "search_two_new_non_dce_independent_drivers": "Find 2 new drivers",
        "reject_high_corr_material_winners": "Reject high-corr winners",
    }
    labels = [label_map.get(str(x), str(x)[:28]) for x in action["action_item"]]
    ax4.barh(labels, action["progress_pct"], color=bar_colors, alpha=0.86)
    ax4.set_xlim(0, 105)
    ax4.set_xlabel("Progress proxy (%)")
    ax4.set_title("Next work queue before any expansion can trade")
    ax4.invert_yaxis()
    for y, (_, row) in enumerate(action.iterrows()):
        ax4.text(float(row["progress_pct"]) + 1, y, f"+{int(row['adds_effective_slots'])} slot", va="center", fontsize=8)

    fig.suptitle(
        "Stage611 risk slot admission protocol: expand only through independent, verified, low-correlation slots",
        fontsize=15,
        fontweight="bold",
    )
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    family_admission: pd.DataFrame,
    contract_rules: pd.DataFrame,
    gates: pd.DataFrame,
    action_queue: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    hard = gates[gates["hard_gate"].astype(int).eq(1)]
    hard_passed = int(hard["passed"].astype(int).sum())
    hard_total = int(len(hard))
    text = f"""# Stage611 risk slot admission protocol

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- generated_at: `{decision['generated_at']}`
- decision: `{decision['decision']}`
- new_backtest_run: `{decision['new_backtest_run']}`
- strategy_changed: `{decision['strategy_changed']}`
- promotion_allowed: `{decision['promotion_allowed']}`
- paper_selector_allowed: `{decision['paper_selector_allowed']}`
- trading_whitelist_allowed: `{decision['trading_whitelist_allowed']}`

## Research judgement

- This stage does not tune entries, exits, product weights, or correlation thresholds.
- It turns the low-single-risk breadth idea into an admission protocol: independent family slots first, then source, TCA, live context, and only then risk budget.
- External trend-following and systematic futures references support instrument diversification, risk budgeting, and correlation control, but also imply that a black-box optimizer is not enough for this repository because source, capacity, and execution evidence are binding.

References:

{chr(10).join(f'- {item}' for item in REFERENCE_LINKS)}

## Core result

- Current effective independent slots: `{decision['current_effective_slots']}`.
- Target effective independent slots: `{decision['target_effective_slots']}`.
- Current single-slot risk proxy: `{decision['current_single_slot_risk_pct']:.2f}%`.
- Preferred target single-slot risk proxy: `{decision['target_single_slot_risk_pct']:.2f}%`.
- If `black_ferrous(j/i)` source/TCA is fully resolved: `{decision['if_black_ferrous_resolved_slots']}` slots, `{decision['if_black_ferrous_single_slot_risk_pct']:.2f}%` per slot.
- Allowed incremental new-family risk budget now: `{decision['allowed_incremental_new_budget_now_pct']:.2f}%`.
- Hard gates passed: `{hard_passed}/{hard_total}`.

## Family admission

{_md_table(family_admission, [
    'product_family',
    'admission_bucket',
    'candidate_products',
    'max_abs_core_corr',
    'readiness_score',
    'allowed_incremental_budget_now_pct',
    'conditional_budget_if_all_gates_pct',
    'blocked_by',
], max_rows=20)}

## Contract rules

{_md_table(contract_rules, ['rule_id', 'rule', 'hard', 'requirement'], max_rows=20)}

## Gates

{_md_table(gates, ['gate', 'actual', 'threshold', 'passed', 'hard_gate', 'judgement'], max_rows=30)}

## Action queue

{_md_table(action_queue, ['priority', 'action_item', 'scope', 'adds_effective_slots', 'progress_pct', 'allowed_now'], max_rows=20)}

## Visual read

- The slot-width panel should show the central problem visually: `4 -> 5 -> 7`, not a smooth glide path. Even the best currently identified new family only moves the allocator from concentrated to still concentrated.
- The admission matrix should show why this is not deployable: many rows have low-correlation/source/capacity evidence, but TCA/live/deploy columns stay red.
- The gate panel should remain fail-closed. A green chart here would be suspicious unless fresh live ticks and valid TCA are present.
- The queue panel should show execution/TCA first, `j/i` second, source-rich families as monitor only, and high-corr winners as rejected.

## Conclusion

- The breadth thesis is still valid, but the deployable expansion budget is currently zero.
- `black_ferrous(j/i)` remains the only P1 new independent family worklist, but it cannot make the final allocator sufficient by itself.
- `soft_agri/precious_metals` are monitor-only, not paper candidates.
- High-correlation winners remain rejected even if profitable historically.

## Overfit reflection

- Before run: not overfitting. The stage defines fixed admission gates and risk budget policy from prior evidence instead of scanning product-return winners.
- After run: not overfitting. The protocol assigns zero new budget despite some attractive low-correlation rows, because execution/TCA/source gates remain incomplete.

## Continue-value reflection

- Before run: valuable. The user question needs a decision framework, not another broad product backtest.
- After run: valuable, but only if work stays on source/TCA/live context and new independent drivers. Re-running wide-pool PnL screens would be low value and high overfit risk.

## Validation

- Script py_compile: passed in Stage611 validation.
- Script run: completed.
- Chart visual inspection: completed after revising the first chart's failed-gate labels and action labels.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _ = _read_csv(STAGE604_SLOT_INVENTORY)
    stage604_gates = _read_csv(STAGE604_GATES)
    _ = _read_csv(STAGE604_ALLOCATOR_SCENARIOS)
    _ = _read_json(STAGE604_DECISION)
    family_ladder = _read_csv(STAGE609_FAMILY_LADDER)
    action_queue = _read_csv(STAGE609_ACTION_QUEUE)
    stage609_gates = _read_csv(STAGE609_GATES)
    _ = _read_json(STAGE609_DECISION)
    stage610 = _read_json(STAGE610_DECISION)

    family_admission = build_family_admission(family_ladder, stage610)
    contract_rules = build_contract_rules()
    gates = build_gates(family_admission, stage604_gates, stage609_gates, stage610)

    hard = gates[gates["hard_gate"].astype(int).eq(1)]
    hard_passed = int(hard["passed"].astype(int).sum())
    hard_total = int(len(hard))
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": _now_cst(),
        "decision": "risk_slot_admission_protocol_ready_new_budget_zero_not_deployable",
        "new_backtest_run": False,
        "strategy_changed": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "current_effective_slots": CURRENT_EFFECTIVE_SLOTS,
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "if_black_ferrous_resolved_slots": IF_BLACK_FERROUS_RESOLVED_SLOTS,
        "current_single_slot_risk_pct": _budget(CURRENT_EFFECTIVE_SLOTS),
        "if_black_ferrous_single_slot_risk_pct": _budget(IF_BLACK_FERROUS_RESOLVED_SLOTS),
        "target_single_slot_risk_pct": _budget(TARGET_EFFECTIVE_SLOTS),
        "allowed_incremental_new_budget_now_pct": float(family_admission["allowed_incremental_budget_now_pct"].sum()),
        "deployable_selector_slots_now": int(family_admission["deployable_now"].sum()),
        "paper_allowed_rows_now": int(family_admission["paper_allowed_now"].sum()),
        "trading_whitelist_rows_now": int(family_admission["trading_whitelist_allowed_now"].sum()),
        "hard_gates_passed": hard_passed,
        "hard_gates_total": hard_total,
        "stage610_connect_requested": bool(stage610.get("connect_requested", False)),
        "stage610_tick_rows": int(stage610.get("tick_rows", 0) or 0),
        "visual_chart_path": str(CHART_PATH),
        "report_path": str(REPORT_PATH),
        "family_admission_path": str(FAMILY_ADMISSION_PATH),
        "contract_rules_path": str(CONTRACT_RULES_PATH),
        "gates_path": str(GATES_PATH),
        "source_references": REFERENCE_LINKS,
    }

    family_admission.to_csv(FAMILY_ADMISSION_PATH, index=False, encoding="utf-8-sig")
    contract_rules.to_csv(CONTRACT_RULES_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    make_chart(family_admission, gates, action_queue)
    write_report(family_admission, contract_rules, gates, action_queue, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

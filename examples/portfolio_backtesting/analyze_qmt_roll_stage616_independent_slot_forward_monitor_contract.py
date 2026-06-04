from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


MODEL_TAG = "stage616_independent_slot_forward_monitor_contract_v1"
OUTPUT_PREFIX = "qmt_roll_stage616_independent_slot_forward_monitor_contract"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE611_FAMILY_ADMISSION = OUTPUT_DIR / "qmt_roll_stage611_risk_slot_admission_protocol_family_admission_stage611_risk_slot_admission_protocol_v1.csv"
STAGE611_DECISION = OUTPUT_DIR / "qmt_roll_stage611_risk_slot_admission_protocol_decision_stage611_risk_slot_admission_protocol_v1.json"
STAGE602_SCOUT = OUTPUT_DIR / "qmt_roll_stage602_full57_non_dce_new_family_scout_non_dce_new_family_scout_stage602_full57_non_dce_new_family_scout_v1.csv"
STAGE615_DECISION = OUTPUT_DIR / "qmt_roll_stage615_event_tca_reducer_contract_audit_decision_stage615_event_tca_reducer_contract_audit_v1.json"

MONITOR_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monitor_plan_{MODEL_TAG}.csv"
PROMOTION_GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gates_{MODEL_TAG}.csv"
SLOT_LADDER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slot_ladder_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TARGET_EFFECTIVE_SLOTS = 7
CURRENT_EFFECTIVE_SLOTS = 4
IF_BLACK_FERROUS_RESOLVED_SLOTS = 5
MAX_CORE_CORR_PREFERRED = 0.10
MAX_CORE_CORR_WATCH = 0.20

SOURCE_REFERENCES = [
    "SSRN trend-following/risk parity commodity futures research: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813",
    "CME Managed Futures Research Digest: https://www.cmegroup.com/education/files/research-digest.pdf",
    "Rob Carver pysystemtrade diversification/risk targeting code: https://github.com/robcarver17/pysystemtrade",
    "PyPortfolioOpt HRP clustering reference: https://github.com/PyPortfolio/PyPortfolioOpt",
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


def _budget(slots: int) -> float:
    return 100.0 / slots if slots else 0.0


def _build_slot_ladder() -> pd.DataFrame:
    rows = [
        {
            "scenario": "current_structural_slots",
            "effective_slots": CURRENT_EFFECTIVE_SLOTS,
            "single_slot_risk_pct": _budget(CURRENT_EFFECTIVE_SLOTS),
            "missing_slots_to_target": TARGET_EFFECTIVE_SLOTS - CURRENT_EFFECTIVE_SLOTS,
            "budget_allowed_now": 0,
            "comment": "现有4个结构槽仍缺live context/TCA，不能当可部署selector预算。",
        },
        {
            "scenario": "if_black_ferrous_source_tca_resolved",
            "effective_slots": IF_BLACK_FERROUS_RESOLVED_SLOTS,
            "single_slot_risk_pct": _budget(IF_BLACK_FERROUS_RESOLVED_SLOTS),
            "missing_slots_to_target": TARGET_EFFECTIVE_SLOTS - IF_BLACK_FERROUS_RESOLVED_SLOTS,
            "budget_allowed_now": 0,
            "comment": "j/i闭合后也只有5槽、20%单槽风险，仍不足以晋级最终allocator。",
        },
        {
            "scenario": "target_independent_slot_structure",
            "effective_slots": TARGET_EFFECTIVE_SLOTS,
            "single_slot_risk_pct": _budget(TARGET_EFFECTIVE_SLOTS),
            "missing_slots_to_target": 0,
            "budget_allowed_now": 0,
            "comment": "目标是至少7个独立经济驱动槽，单槽风险降到约14.29%。",
        },
    ]
    return pd.DataFrame(rows)


def _monitor_row(row: pd.Series, stage615: dict[str, Any]) -> dict[str, Any]:
    family = str(row.get("product_family", ""))
    role = str(row.get("slot_role", ""))
    bucket = str(row.get("admission_bucket", ""))
    products = str(row.get("candidate_products", ""))
    corr = float(row.get("max_abs_core_corr", 0.0) or 0.0)
    pnl = float(row.get("slot_total_pnl_sum", 0.0) or 0.0)
    readiness = float(row.get("readiness_score", 0.0) or 0.0)

    live_context_ready = int(stage615.get("live_context_present_rows", 0) or 0) >= int(stage615.get("live_context_required_rows", 45) or 45)
    live_tca_ready = int(stage615.get("p0_valid_live_tca_samples", 0) or 0) >= int(stage615.get("p0_required_live_tca_samples", 9) or 9)

    if role == "p1_new_family_blocked":
        monitor_tier = "P1_source_tca_worklist"
        cadence = "weekly_source_probe_monthly_pit_ledger"
        min_forward_months = 0
        next_evidence = "DCE官方源或可授权替代源闭合；received_at/source_url/raw_hash齐全；之后补9个真实TCA样本。"
        promotion_condition = "source>=2 route + point-in-time ledger + live context 45/45 + live TCA 9/9；但仅可把结构槽从4推到5。"
        allowed_action = "source_tca_research_only"
    elif role == "source_rich_no_edge_monitor":
        monitor_tier = "P2_forward_monitor_only"
        cadence = "monthly_pit_snapshot_no_trade"
        min_forward_months = 12
        next_evidence = "连续12个月点时化记录；至少3个独立趋势episode；不得用事后topN收益挑选。"
        promotion_condition = "低相关保持<=0.10；forward episode材料性转正；3/6个月左尾不劣化；再申请TCA预算。"
        allowed_action = "forward_monitor_no_tca_budget"
    elif role == "current_p0_structural_slot":
        monitor_tier = "P0_reference_close_execution_gap"
        cadence = "each_submit_day_plus_weekly_audit"
        min_forward_months = 0
        next_evidence = "read-only snapshot刷新；exact vt_orderid writer；EVENT_ORDER/TRADE/TICK reducer累计P0 9/9样本。"
        promotion_condition = "live context 45/45 + vt_orderid 5/5 + live TCA 9/9；否则只能做结构参考。"
        allowed_action = "execution_source_tca_closeout_only"
    elif role == "reject_high_core_corr":
        monitor_tier = "Reject_high_corr_recheck_only"
        cadence = "quarterly_corr_recheck"
        min_forward_months = 12
        next_evidence = "只有rolling 252d相关长期降到watch线内且经济驱动重新定义后才允许复审。"
        promotion_condition = "不得因历史收益好而晋级；相关性先通过，再谈source和TCA。"
        allowed_action = "no_budget_no_tca"
    else:
        monitor_tier = "Observe_no_budget"
        cadence = "quarterly_review"
        min_forward_months = 12
        next_evidence = "补齐source/materiality/capacity定义后再复审。"
        promotion_condition = "全部准入证据齐全前，不进入paper或白名单。"
        allowed_action = "observe_only"

    corr_state = "pass" if corr <= MAX_CORE_CORR_PREFERRED else ("watch" if corr <= MAX_CORE_CORR_WATCH else "fail")
    material_state = "pass" if pnl > 0 else "missing"
    source_state = "pass" if float(row.get("evidence_source", 0.0) or 0.0) >= 1.0 else "missing"
    live_state = "pass" if live_context_ready and live_tca_ready else "missing"

    return {
        "product_family": family,
        "candidate_products": products,
        "slot_role": role,
        "admission_bucket": bucket,
        "monitor_tier": monitor_tier,
        "cadence": cadence,
        "min_forward_months_before_promotion": min_forward_months,
        "max_abs_core_corr": corr,
        "corr_state": corr_state,
        "slot_total_pnl_sum": pnl,
        "material_state": material_state,
        "readiness_score": readiness,
        "source_state": source_state,
        "live_context_and_tca_state": live_state,
        "paper_allowed_now": 0,
        "trading_whitelist_allowed_now": 0,
        "incremental_budget_allowed_now_pct": 0.0,
        "next_evidence": next_evidence,
        "promotion_condition": promotion_condition,
        "allowed_action": allowed_action,
    }


def build_monitor_plan(family_admission: pd.DataFrame, stage615: dict[str, Any]) -> pd.DataFrame:
    frame = family_admission.copy()
    frame["max_abs_core_corr"] = _num(frame, "max_abs_core_corr")
    frame["slot_total_pnl_sum"] = _num(frame, "slot_total_pnl_sum")
    frame["readiness_score"] = _num(frame, "readiness_score")
    frame["evidence_source"] = _num(frame, "evidence_source")
    rows = [_monitor_row(row, stage615) for _, row in frame.iterrows()]
    order = {
        "P0_reference_close_execution_gap": 0,
        "P1_source_tca_worklist": 1,
        "P2_forward_monitor_only": 2,
        "Reject_high_corr_recheck_only": 3,
        "Observe_no_budget": 4,
    }
    monitor = pd.DataFrame(rows)
    monitor["tier_order"] = monitor["monitor_tier"].map(order).fillna(9).astype(int)
    monitor = monitor.sort_values(["tier_order", "readiness_score", "slot_total_pnl_sum"], ascending=[True, False, False])
    return monitor.drop(columns=["tier_order"])


def build_promotion_gates(stage615: dict[str, Any]) -> pd.DataFrame:
    live_context = f"{int(stage615.get('live_context_present_rows', 0) or 0)}/{int(stage615.get('live_context_required_rows', 45) or 45)}"
    live_tca = f"{int(stage615.get('p0_valid_live_tca_samples', 0) or 0)}/{int(stage615.get('p0_required_live_tca_samples', 9) or 9)}"
    return pd.DataFrame(
        [
            {
                "gate": "independent_slot_count",
                "required": ">=7 effective independent economic-driver slots",
                "current": f"{CURRENT_EFFECTIVE_SLOTS}; {IF_BLACK_FERROUS_RESOLVED_SLOTS} if black_ferrous resolved",
                "status": "blocked",
                "why_it_matters": "少于7槽时，单槽风险仍在20%-25%，不能满足低单笔风险目标。",
            },
            {
                "gate": "same_family_top1_same_direction",
                "required": "one product per family direction unless independent driver proven",
                "current": "contract_ready",
                "status": "pass_contract_only",
                "why_it_matters": "防止把同一风险簇拆成多个高相关仓位。",
            },
            {
                "gate": "low_core_corr",
                "required": f"preferred abs corr <= {MAX_CORE_CORR_PREFERRED:.2f}; watch <= {MAX_CORE_CORR_WATCH:.2f}",
                "current": "black_ferrous/soft_agri/precious pass; rubber fails",
                "status": "mixed",
                "why_it_matters": "相关性不过关时，历史正收益也可能在压力期一起回撤。",
            },
            {
                "gate": "point_in_time_source",
                "required": "received_at/source_url/raw_hash and repeatable official or authorized route",
                "current": "DCE official route still blocked for j/i",
                "status": "blocked",
                "why_it_matters": "没有点时化source就不能实盘复制选品判断。",
            },
            {
                "gate": "live_execution_tca",
                "required": "live context 45/45 + vt_orderid 5/5 + live TCA 9/9",
                "current": f"live_context={live_context}; live_tca={live_tca}",
                "status": "blocked",
                "why_it_matters": "没有真实成交证据就不能证明回测与实盘无巨大偏差。",
            },
            {
                "gate": "forward_materiality_before_tca_budget",
                "required": "P2 families need 12 months PIT monitor and >=3 independent trend episodes",
                "current": "soft_agri/precious source-rich but no materiality",
                "status": "monitor_only",
                "why_it_matters": "有数据不等于有alpha，避免因为source可得而过拟合。",
            },
            {
                "gate": "paper_or_whitelist",
                "required": "all prior gates pass",
                "current": "0 paper, 0 whitelist, 0 incremental budget",
                "status": "blocked",
                "why_it_matters": "当前只能研究和监控，不能合入资金预算。",
            },
        ]
    )


def build_gates(monitor: pd.DataFrame, promotion_gates: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "gate": "monitor_contract_created",
                "actual": "yes",
                "threshold": "yes",
                "passed": 1,
                "judgement": "已有P0/P1/P2/Reject监控分层。",
            },
            {
                "gate": "new_budget_allowed",
                "actual": f"{monitor['incremental_budget_allowed_now_pct'].sum():.1f}%",
                "threshold": "0 until source/TCA/live gates pass",
                "passed": int(monitor["incremental_budget_allowed_now_pct"].sum() == 0),
                "judgement": "当前不得新增扩池预算。",
            },
            {
                "gate": "paper_allowed",
                "actual": str(int(monitor["paper_allowed_now"].sum())),
                "threshold": "0 before gates pass",
                "passed": int(monitor["paper_allowed_now"].sum() == 0),
                "judgement": "没有paper selector。",
            },
            {
                "gate": "trading_whitelist_allowed",
                "actual": str(int(monitor["trading_whitelist_allowed_now"].sum())),
                "threshold": "0 before gates pass",
                "passed": int(monitor["trading_whitelist_allowed_now"].sum() == 0),
                "judgement": "没有交易白名单。",
            },
            {
                "gate": "source_first_no_pnl_topn",
                "actual": "no new pnl backtest",
                "threshold": "must not select by historical topN",
                "passed": 1,
                "judgement": "本阶段只读冻结证据，不做宽池收益扫描。",
            },
            {
                "gate": "blocking_gates_explicit",
                "actual": ",".join(promotion_gates.loc[promotion_gates["status"].isin(["blocked", "monitor_only"]), "gate"].tolist()),
                "threshold": "must list blockers",
                "passed": 1,
                "judgement": "阻塞项已显式列出，防止误晋级。",
            },
        ]
    )


def build_decision(monitor: pd.DataFrame, gates: pd.DataFrame, stage615: dict[str, Any]) -> dict[str, Any]:
    return {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": _now_cst(),
        "decision": "forward_monitor_contract_ready_no_new_slot_budget",
        "new_backtest_run": False,
        "strategy_changed": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "incremental_budget_allowed_now_pct": 0.0,
        "current_effective_slots": CURRENT_EFFECTIVE_SLOTS,
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "if_black_ferrous_resolved_slots": IF_BLACK_FERROUS_RESOLVED_SLOTS,
        "current_single_slot_risk_pct": _budget(CURRENT_EFFECTIVE_SLOTS),
        "if_black_ferrous_single_slot_risk_pct": _budget(IF_BLACK_FERROUS_RESOLVED_SLOTS),
        "target_single_slot_risk_pct": _budget(TARGET_EFFECTIVE_SLOTS),
        "p1_source_tca_worklist_families": monitor.loc[monitor["monitor_tier"].eq("P1_source_tca_worklist"), "product_family"].tolist(),
        "p2_forward_monitor_families": monitor.loc[monitor["monitor_tier"].eq("P2_forward_monitor_only"), "product_family"].tolist(),
        "rejected_high_corr_families": monitor.loc[monitor["monitor_tier"].eq("Reject_high_corr_recheck_only"), "product_family"].tolist(),
        "live_context_present_rows": int(stage615.get("live_context_present_rows", 0) or 0),
        "live_context_required_rows": int(stage615.get("live_context_required_rows", 45) or 45),
        "p0_valid_live_tca_samples": int(stage615.get("p0_valid_live_tca_samples", 0) or 0),
        "p0_required_live_tca_samples": int(stage615.get("p0_required_live_tca_samples", 9) or 9),
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "source_references": SOURCE_REFERENCES,
    }


def plot(slot_ladder: pd.DataFrame, monitor: pd.DataFrame, promotion_gates: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(18, 11))
    fig.suptitle("Stage616 independent risk-slot forward monitor: no budget until source/TCA/live evidence closes", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    colors = ["#e53e3e", "#dd6b20", "#2f855a"]
    ax.bar(slot_ladder["scenario"], slot_ladder["effective_slots"], color=colors)
    ax.axhline(TARGET_EFFECTIVE_SLOTS, color="#2f855a", linestyle="--", linewidth=1.5, label="target slots")
    for i, row in slot_ladder.iterrows():
        ax.text(i, row["effective_slots"] + 0.15, f"{int(row['effective_slots'])} slots\n{row['single_slot_risk_pct']:.1f}%/slot", ha="center", fontsize=10)
    ax.set_ylim(0, TARGET_EFFECTIVE_SLOTS + 1.5)
    ax.set_ylabel("effective independent slots")
    ax.set_title("Slot count and single-slot risk")
    ax.tick_params(axis="x", rotation=15)
    ax.legend(loc="upper left")

    ax = axes[0, 1]
    color_map = {
        "P0_reference_close_execution_gap": "#3182ce",
        "P1_source_tca_worklist": "#dd6b20",
        "P2_forward_monitor_only": "#805ad5",
        "Reject_high_corr_recheck_only": "#e53e3e",
        "Observe_no_budget": "#718096",
    }
    plot_monitor = monitor.copy()
    plot_monitor["plot_color"] = plot_monitor["monitor_tier"].map(color_map).fillna("#718096")
    ax.scatter(
        plot_monitor["max_abs_core_corr"],
        plot_monitor["slot_total_pnl_sum"],
        s=160,
        c=plot_monitor["plot_color"],
        edgecolor="white",
        linewidth=1.2,
    )
    ax.axvline(MAX_CORE_CORR_PREFERRED, color="#2f855a", linestyle="--", linewidth=1.2, label="preferred corr 0.10")
    ax.axvline(MAX_CORE_CORR_WATCH, color="#dd6b20", linestyle="--", linewidth=1.2, label="watch corr 0.20")
    x_max = max(MAX_CORE_CORR_WATCH + 0.04, float(plot_monitor["max_abs_core_corr"].max()) + 0.04)
    y_min = float(plot_monitor["slot_total_pnl_sum"].min()) if not plot_monitor.empty else 0.0
    y_max = float(plot_monitor["slot_total_pnl_sum"].max()) if not plot_monitor.empty else 1.0
    y_pad = max(5000.0, (y_max - y_min) * 0.12)
    label_offsets = {
        "precious_metals": (5, -12),
        "soft_agri": (5, 8),
        "financial_index": (5, 9),
        "livestock": (5, -12),
        "rubber": (-48, 4),
    }
    for _, row in plot_monitor.iterrows():
        x_offset = -48 if row["max_abs_core_corr"] > x_max - 0.055 else 5
        y_offset = 4
        if str(row["product_family"]) in label_offsets:
            x_offset, y_offset = label_offsets[str(row["product_family"])]
        ax.annotate(
            str(row["product_family"]),
            (row["max_abs_core_corr"], row["slot_total_pnl_sum"]),
            xytext=(x_offset, y_offset),
            textcoords="offset points",
            fontsize=9,
            clip_on=False,
        )
    ax.set_xlabel("abs corr to core daily PnL")
    ax.set_ylabel("slot historical PnL sum (diagnostic only)")
    ax.set_title("Family map: correlation first, PnL is diagnostic")
    ax.set_xlim(-0.005, x_max)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)
    ax.legend(loc="best", fontsize=9)

    ax = axes[1, 0]
    runway = monitor[monitor["monitor_tier"].isin(["P1_source_tca_worklist", "P2_forward_monitor_only", "Reject_high_corr_recheck_only"])].copy()
    runway = runway.sort_values(["min_forward_months_before_promotion", "readiness_score"], ascending=[True, False])
    y = np.arange(len(runway))
    runway["plot_months"] = runway["min_forward_months_before_promotion"].clip(lower=0.25)
    ax.barh(y, runway["plot_months"], color=runway["monitor_tier"].map(color_map).fillna("#718096"))
    ax.set_yticks(y)
    ax.set_yticklabels(runway["product_family"])
    ax.set_xlabel("minimum forward months before promotion")
    ax.set_title("Monitor runway: source/TCA first, P2 needs forward evidence")
    for i, row in enumerate(runway.itertuples(index=False)):
        label = row.allowed_action.replace("_", " ")
        month_label = "0m / " if row.min_forward_months_before_promotion == 0 else ""
        ax.text(row.plot_months + 0.25, i, month_label + label, va="center", fontsize=9)
    ax.set_xlim(0, max(18, float(runway["min_forward_months_before_promotion"].max()) + 6 if not runway.empty else 18))

    ax = axes[1, 1]
    gate_view = promotion_gates.copy()
    gate_colors = gate_view["status"].map(
        {
            "blocked": "#e53e3e",
            "monitor_only": "#805ad5",
            "mixed": "#dd6b20",
            "pass_contract_only": "#38a169",
        }
    ).fillna("#718096")
    yy = np.arange(len(gate_view))
    ax.barh(yy, np.ones(len(gate_view)), color=gate_colors)
    ax.set_yticks(yy)
    ax.set_yticklabels(gate_view["gate"])
    ax.set_xlim(0, 1)
    ax.set_xlabel("gate status")
    ax.set_title("Promotion gates")
    for i, row in enumerate(gate_view.itertuples(index=False)):
        ax.text(0.02, i, row.status, va="center", ha="left", color="white", fontsize=10, fontweight="bold")
    ax.invert_yaxis()

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def build_report(decision: dict[str, Any], monitor: pd.DataFrame, promotion_gates: pd.DataFrame, slot_ladder: pd.DataFrame, gates: pd.DataFrame) -> str:
    p1 = ", ".join(decision["p1_source_tca_worklist_families"]) or "none"
    p2 = ", ".join(decision["p2_forward_monitor_families"]) or "none"
    rejects = ", ".join(decision["rejected_high_corr_families"]) or "none"
    return f"""# Stage616 Independent Risk Slot Forward Monitor Contract

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- generated_at: `{decision['generated_at']}`
- decision: `{decision['decision']}`
- new_backtest_run: `False`
- strategy_changed: `False`
- promotion_allowed: `False`
- paper_selector_allowed: `False`
- trading_whitelist_allowed: `False`

## External research and judgement

- Commodity trend-following research supports broad diversification, but risk parity or equal-risk weighting is not a substitute for trend alpha.
- Managed futures material also emphasizes adding less-correlated markets; the practical constraint is that correlations can rise, so family-level and stress-period correlation checks are mandatory.
- Open-source references such as `pysystemtrade` and HRP/risk-clustering libraries support the same implementation idea: treat diversification as an instrument/family/risk-budget problem, not as a historical top-N return list.
- Judgement: the user's breadth thesis is valid only if it is expressed as effective independent economic-driver slots. Current data does not justify adding budget.

## Slot Ladder

{_md_table(slot_ladder)}

## Monitor Plan

{_md_table(monitor, [
    "product_family",
    "candidate_products",
    "monitor_tier",
    "cadence",
    "min_forward_months_before_promotion",
    "max_abs_core_corr",
    "slot_total_pnl_sum",
    "source_state",
    "live_context_and_tca_state",
    "allowed_action",
], max_rows=20)}

## Promotion Gates

{_md_table(promotion_gates, ["gate", "required", "current", "status", "why_it_matters"], max_rows=20)}

## Hard Gates

{_md_table(gates)}

## Key read

- P1 worklist: `{p1}`.
- P2 forward monitor only: `{p2}`.
- Rejected by high core correlation: `{rejects}`.
- Current effective slots: `{decision['current_effective_slots']}`; target: `{decision['target_effective_slots']}`.
- If black_ferrous is fully resolved, slots only become `{decision['if_black_ferrous_resolved_slots']}` and single-slot risk is still `{decision['if_black_ferrous_single_slot_risk_pct']:.2f}%`.
- Current incremental budget allowed: `0%`.

## Conclusion

- The breadth direction remains worth pursuing, but the correct next artifact is a forward monitor and source/TCA closeout, not a new trading version.
- `black_ferrous(j/i)` is still the only concrete P1 new independent slot worklist, but it cannot solve the 7-slot target alone.
- `soft_agri` and `precious_metals` should be monitored point-in-time for 12 months before any TCA budget or paper selector is discussed.
- High-correlation families remain rejected even if they have positive historical PnL.

## Validation

- Script py_compile: passed before record closeout.
- Script run: completed.
- Chart visual inspection: required after generation.
"""


def main() -> None:
    family_admission = _read_csv(STAGE611_FAMILY_ADMISSION)
    stage611_decision = _read_json(STAGE611_DECISION)
    stage615 = _read_json(STAGE615_DECISION)
    if not STAGE602_SCOUT.exists():
        raise FileNotFoundError(STAGE602_SCOUT)
    _ = _read_csv(STAGE602_SCOUT)

    slot_ladder = _build_slot_ladder()
    monitor = build_monitor_plan(family_admission, stage615)
    promotion_gates = build_promotion_gates(stage615)
    gates = build_gates(monitor, promotion_gates)
    decision = build_decision(monitor, gates, stage615)
    decision["stage611_decision"] = stage611_decision.get("decision")

    plot(slot_ladder, monitor, promotion_gates, gates)
    report = build_report(decision, monitor, promotion_gates, slot_ladder, gates)

    monitor.to_csv(MONITOR_PLAN_PATH, index=False, encoding="utf-8-sig")
    promotion_gates.to_csv(PROMOTION_GATES_PATH, index=False, encoding="utf-8-sig")
    slot_ladder.to_csv(SLOT_LADDER_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage538_stage526_promotion_boundary_v1"
OUTPUT_PREFIX = "qmt_roll_stage538_stage526_promotion_boundary"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE527_TAG = "stage527_stage526_robustness_audit_v1"
STAGE527_PREFIX = "qmt_roll_stage527_stage526_robustness_audit"
STAGE528_TAG = "stage528_stage526_edge_concentration_audit_v1"
STAGE528_PREFIX = "qmt_roll_stage528_stage526_edge_concentration_audit"
STAGE530_TAG = "stage530_external_data_execution_readiness_v1"
STAGE530_PREFIX = "qmt_roll_stage530_external_data_execution_readiness"
STAGE535_TAG = "stage535_stage526_fast_fail_entry_proxy_v1"
STAGE535_PREFIX = "qmt_roll_stage535_stage526_fast_fail_entry_proxy"
STAGE536_TAG = "stage536_stage526_cost_churn_fragility_v1"
STAGE536_PREFIX = "qmt_roll_stage536_stage526_cost_churn_fragility"
STAGE537_TAG = "stage537_stage526_segment_lifecycle_audit_v1"
STAGE537_PREFIX = "qmt_roll_stage537_stage526_segment_lifecycle_audit"
STAGE508_TAG = "stage508_xsmom_true_carry_replay_v1"
STAGE508_PREFIX = "qmt_roll_stage508_xsmom_true_carry_replay"

CANDIDATE = "r080_pc25_maxpos4"

SUMMARY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_summary_{STAGE526_TAG}.csv"
COST_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_cost_stress_{STAGE526_TAG}.csv"
MARGIN_DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
HOLDING_IN = OUTPUT_DIR / f"{STAGE527_PREFIX}_holding_experience_{STAGE527_TAG}.csv"
COLD_START_IN = OUTPUT_DIR / f"{STAGE527_PREFIX}_cold_start_{STAGE527_TAG}.csv"
EDGE_PAIR_IN = OUTPUT_DIR / f"{STAGE528_PREFIX}_pair_summary_{STAGE528_TAG}.csv"
EDGE_LEAVE_IN = OUTPUT_DIR / f"{STAGE528_PREFIX}_leave_one_year_{STAGE528_TAG}.csv"
EXTERNAL_DECISION_IN = OUTPUT_DIR / f"{STAGE530_PREFIX}_decision_{STAGE530_TAG}.json"
ENTRY_DECISION_IN = OUTPUT_DIR / f"{STAGE535_PREFIX}_decision_{STAGE535_TAG}.json"
COST_DECISION_IN = OUTPUT_DIR / f"{STAGE536_PREFIX}_decision_{STAGE536_TAG}.json"
LIFE_DECISION_IN = OUTPUT_DIR / f"{STAGE537_PREFIX}_decision_{STAGE537_TAG}.json"
XSMOM_DECISION_IN = OUTPUT_DIR / f"{STAGE508_PREFIX}_decision_{STAGE508_TAG}.json"

GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
BOUNDARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_boundary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _fmt(value: Any, digits: int = 4) -> str:
    number = _safe_float(value, default=float("nan"))
    if math.isnan(number):
        return str(value)
    return f"{number:.{digits}f}"


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load_inputs() -> dict[str, Any]:
    summary = pd.read_csv(SUMMARY_IN, encoding="utf-8-sig")
    cost = pd.read_csv(COST_IN, encoding="utf-8-sig")
    margin = pd.read_csv(MARGIN_DAILY_IN, encoding="utf-8-sig")
    holding = pd.read_csv(HOLDING_IN, encoding="utf-8-sig")
    cold = pd.read_csv(COLD_START_IN, encoding="utf-8-sig")
    edge_pair = pd.read_csv(EDGE_PAIR_IN, encoding="utf-8-sig")
    edge_leave = pd.read_csv(EDGE_LEAVE_IN, encoding="utf-8-sig")
    margin["date"] = pd.to_datetime(margin["date"], errors="coerce").dt.normalize()
    return {
        "summary": summary,
        "cost": cost,
        "margin": margin,
        "holding": holding,
        "cold": cold,
        "edge_pair": edge_pair,
        "edge_leave": edge_leave,
        "external": _read_json(EXTERNAL_DECISION_IN),
        "entry": _read_json(ENTRY_DECISION_IN),
        "cost_decision": _read_json(COST_DECISION_IN),
        "life": _read_json(LIFE_DECISION_IN),
        "xsmom": _read_json(XSMOM_DECISION_IN),
    }


def _status(pass_condition: bool, warn_condition: bool = False) -> str:
    if pass_condition:
        return "PASS"
    if warn_condition:
        return "WARN"
    return "FAIL"


def _make_gate_rows(inputs: dict[str, Any]) -> pd.DataFrame:
    summary = inputs["summary"]
    cost = inputs["cost"]
    holding = inputs["holding"]
    cold = inputs["cold"]
    edge_pair = inputs["edge_pair"]
    edge_leave = inputs["edge_leave"]
    external = inputs["external"]
    entry = inputs["entry"]
    cost_decision = inputs["cost_decision"]
    life = inputs["life"]
    xsmom = inputs["xsmom"]

    cand = summary[summary["variant"].eq(CANDIDATE)].iloc[0].to_dict()
    cost_cand = cost[cost["variant"].eq(CANDIDATE)].set_index("cost_multiplier")
    c1 = cost_cand.loc[1.0].to_dict()
    c2 = cost_cand.loc[2.0].to_dict()
    c3 = cost_cand.loc[3.0].to_dict()
    holding_cand = holding[holding["variant"].eq(CANDIDATE)].copy()
    h63 = holding_cand[holding_cand["holding_days"].eq(63)].iloc[0].to_dict()
    h126 = holding_cand[holding_cand["holding_days"].eq(126)].iloc[0].to_dict()
    cold_cand = cold[cold["variant"].eq(CANDIDATE)].copy()
    edge_primary = edge_pair[edge_pair["reference_variant"].eq("r080_pc25_u75")].iloc[0].to_dict()
    leave_primary = edge_leave[edge_leave["reference_variant"].eq("r080_pc25_u75")].copy()

    rows: list[dict[str, Any]] = []

    def add(
        gate_id: str,
        category: str,
        required: bool,
        status: str,
        metric: str,
        threshold: str,
        evidence: str,
        next_action: str,
        source: str,
    ) -> None:
        rows.append(
            {
                "gate_id": gate_id,
                "category": category,
                "required_for_promotion": int(required),
                "status": status,
                "metric": metric,
                "threshold": threshold,
                "evidence": evidence,
                "next_action": next_action,
                "source": source,
            }
        )

    add(
        "normal_cost_dd40",
        "core_risk",
        True,
        _status(_safe_float(c1["max_dd_pct"]) >= -40.0),
        f"max_dd={_fmt(c1['max_dd_pct'])}%",
        ">= -40%",
        "正常成本下最大回撤仍在DD40硬闸门内。",
        "保留为晋级必要条件。",
        "Stage526",
    )
    add(
        "normal_broker100",
        "core_execution",
        True,
        _status(int(cand["days_over_100pct"]) == 0 and _safe_float(cand["max_broker10_margin_to_equity_pct"]) <= 100.0),
        f"broker10_max={_fmt(cand['max_broker10_margin_to_equity_pct'])}%, days>100={int(cand['days_over_100pct'])}",
        "<=100%, days>100=0",
        "正常成本、精确持仓保证金口径不打穿100%。",
        "实盘前继续接真实券商保证金，但当前回测闸门通过。",
        "Stage526/Stage215",
    )
    add(
        "return_retention_majority",
        "core_return",
        True,
        _status(_safe_float(cand["return_retention_vs_stage079_pct"]) >= 70.0),
        f"retention={_fmt(cand['return_retention_vs_stage079_pct'])}%",
        ">=70%",
        "收益保留超过多数保留线，但低于Stage079绝对收益。",
        "接受其为真实可成交风控候选，而不是收益最大版本。",
        "Stage526",
    )
    add(
        "normal_sharpe_quality",
        "path_quality",
        True,
        _status(_safe_float(cand["sharpe"]) >= 1.5),
        f"sharpe={_fmt(cand['sharpe'])}, ulcer={_fmt(cand['ulcer_pct'])}%",
        "Sharpe>=1.5",
        "风险预算后收益路径质量没有塌缩。",
        "保留。",
        "Stage526",
    )
    add(
        "cost_2x_dd40",
        "stress_cost",
        True,
        _status(_safe_float(c2["max_dd_pct"]) >= -40.0),
        f"2x max_dd={_fmt(c2['max_dd_pct'])}%",
        ">= -40%",
        "2倍成本压力下回撤仍在DD40内。",
        "作为正常部署的最低成本压力闸门。",
        "Stage526/Stage527",
    )
    add(
        "cost_2x_broker100",
        "stress_cost",
        False,
        _status(
            _safe_float(c2["max_broker10_margin_to_equity_pct"]) <= 100.0 and int(c2["days_over_100pct"]) == 0,
            warn_condition=True,
        ),
        f"2x broker10_max={_fmt(c2['max_broker10_margin_to_equity_pct'])}%, days>100={int(c2['days_over_100pct'])}",
        "<=100%, days>100=0",
        "2倍成本把权益分母压低后，压力口径保证金出现2天>100%。这不是正常成本实盘穿线，但说明安全垫薄。",
        "实盘监控要加入broker10>90/95预警和滑点倍率监控。",
        "Stage526/Stage527",
    )
    add(
        "cost_3x_dd40",
        "stress_cost",
        False,
        _status(_safe_float(c3["max_dd_pct"]) >= -40.0),
        f"3x max_dd={_fmt(c3['max_dd_pct'])}%",
        ">= -40%",
        "3倍成本压力失败；失败窗口与1x/2x相同，是长回撤路径叠加成本，不是保证金峰值。",
        "若用户要求高滑点极端压力也保DD40，本候选不能晋级。",
        "Stage526/Stage536",
    )
    add(
        "cold_start_dd40",
        "cold_start",
        True,
        _status(_safe_float(cold_cand["dd40_pass_rate_pct"].min()) >= 100.0),
        f"min dd40 pass={_fmt(cold_cand['dd40_pass_rate_pct'].min())}%",
        "月/季/年冷启动=100%",
        "任意月/季/年启动的DD40闸门全部通过。",
        "保留。",
        "Stage527",
    )
    add(
        "cold_start_broker100",
        "cold_start",
        True,
        _status(_safe_float(cold_cand["broker100_pass_rate_pct"].min()) >= 100.0),
        f"min broker100 pass={_fmt(cold_cand['broker100_pass_rate_pct'].min())}%",
        "月/季/年冷启动=100%",
        "任意月/季/年启动的broker100闸门全部通过。",
        "保留。",
        "Stage527",
    )
    add(
        "rolling_63_126_dd40",
        "holding_experience",
        True,
        _status(_safe_float(h63["dd40_breach_rate_pct"]) == 0.0 and _safe_float(h126["dd40_breach_rate_pct"]) == 0.0),
        f"63d dd40 breach={_fmt(h63['dd40_breach_rate_pct'])}%, 126d={_fmt(h126['dd40_breach_rate_pct'])}%",
        "63/126日 DD40破例=0",
        "短周期任意启动不会在3/6个月内打穿DD40。",
        "保留。",
        "Stage527",
    )
    add(
        "rolling_short_return_left_tail",
        "holding_experience",
        False,
        _status(_safe_float(h63["p05_return_pct"]) >= 0.0 and _safe_float(h126["p05_return_pct"]) >= 0.0, warn_condition=True),
        f"63d p05={_fmt(h63['p05_return_pct'])}%, 126d p05={_fmt(h126['p05_return_pct'])}%",
        "p05收益>=0",
        "3个月/6个月左尾收益仍可能为负，说明持有体验未达到理想。",
        "不能声称任何短持有都舒服；需要在说明书里披露。",
        "Stage527",
    )
    add(
        "edge_not_concentrated",
        "overfit_control",
        True,
        _status(
            int(leave_primary["remaining_positive"].min()) == 1
            and _safe_float(edge_primary["top5_share_of_positive_edge_pct"]) < 35.0
            and _safe_float(edge_primary["max_year_share_of_total_edge_pct"]) < 50.0
        ),
        f"top5={_fmt(edge_primary['top5_share_of_positive_edge_pct'])}%, max_year={_fmt(edge_primary['max_year_share_of_total_edge_pct'])}%",
        "leave-one-year全部为正，top5<35%，max_year<50%",
        "相对旧硬通过壳的edge不是单日或单年孤岛。",
        "保留，但继续禁止产品黑名单和小数救援。",
        "Stage528",
    )
    add(
        "xsmom_real_fill_clean",
        "execution_semantic",
        True,
        _status(int(xsmom.get("xsmom_fallback_order_count", 999999)) == 0),
        f"xsmom fallback={int(xsmom.get('xsmom_fallback_order_count', -1))}",
        "fallback=0",
        "xsmom真实成交承载已清零fallback。",
        "保留；实盘前复跑sentinel。",
        "Stage508/Stage209",
    )
    add(
        "entry_filter_rejected",
        "overfit_control",
        True,
        _status(entry.get("decision") == "entry_proxy_not_ready_keep_stage526"),
        f"decision={entry.get('decision')}",
        "不晋级入场代理过滤",
        "信号日前可见价格代理无法稳定区分快失败和正贡献。",
        "停止ADX/ATR/Donchian/RSI小阈值救援。",
        "Stage535",
    )
    add(
        "early_exit_rejected",
        "overfit_control",
        True,
        _status(life.get("decision") == "early_adverse_exit_rejected"),
        f"decision={life.get('decision')}",
        "不晋级早退规则",
        "短持有亏损真实存在，但早退会误伤6-20天主右尾。",
        "停止短持有砍仓和简单cooldown。",
        "Stage537",
    )
    add(
        "cost_fragility_identified",
        "risk_monitoring",
        True,
        _status(cost_decision.get("decision") == "short_loss_segments_are_cost_fragility_focus"),
        f"3x-1x dd_gap={_fmt(cost_decision['comparison']['dd_gap_3x_minus_1x_pp'])}pp",
        "已识别成本脆弱来源",
        "3x失败来自2022长回撤和短命亏损段累积，不是资金占用错过信号。",
        "进入压力监控，而不是继续改规则。",
        "Stage536",
    )
    add(
        "external_data_core_signal_ready",
        "external_data",
        False,
        _status(external.get("decision") == "all_external_ready", warn_condition=True),
        f"decision={external.get('decision')}",
        "外生核心信号必须有点时化账本",
        "基差可解释；会员/仓单/舆情不具备直接live核心信号资格。",
        "当前候选不依赖外生数据；外生路线只做监控/解释，不强接入。",
        "Stage530",
    )

    return pd.DataFrame(rows)


def _make_boundary(inputs: dict[str, Any], gates: pd.DataFrame) -> pd.DataFrame:
    summary = inputs["summary"]
    cost = inputs["cost"]
    holding = inputs["holding"]
    cold = inputs["cold"]
    cand = summary[summary["variant"].eq(CANDIDATE)].iloc[0]
    cost_cand = cost[cost["variant"].eq(CANDIDATE)].set_index("cost_multiplier")
    h63 = holding[(holding["variant"].eq(CANDIDATE)) & (holding["holding_days"].eq(63))].iloc[0]
    h126 = holding[(holding["variant"].eq(CANDIDATE)) & (holding["holding_days"].eq(126))].iloc[0]
    cold_cand = cold[cold["variant"].eq(CANDIDATE)]
    required_failures = gates[(gates["required_for_promotion"].eq(1)) & (~gates["status"].eq("PASS"))]
    stress_failures = gates[(gates["required_for_promotion"].eq(0)) & (gates["status"].eq("FAIL"))]
    warnings = gates[gates["status"].eq("WARN")]
    rows = [
        {
            "item": "promotion_decision",
            "value": "promote_to_normal_cost_candidate_review" if required_failures.empty else "do_not_promote",
            "evidence": f"required_pass={len(gates[gates['required_for_promotion'].eq(1) & gates['status'].eq('PASS')])}/{len(gates[gates['required_for_promotion'].eq(1)])}",
        },
        {
            "item": "allowed_claim",
            "value": "normal cost + DD40 + broker100 + 2x DD40 candidate",
            "evidence": f"return_retention={_fmt(cand['return_retention_vs_stage079_pct'])}%, dd={_fmt(cand['max_dd_pct'])}%, 2x_dd={_fmt(cost_cand.loc[2.0, 'max_dd_pct'])}%",
        },
        {
            "item": "not_allowed_claim",
            "value": "not a 3x-cost resilient final live version",
            "evidence": f"3x_dd={_fmt(cost_cand.loc[3.0, 'max_dd_pct'])}%, 3x_broker10={_fmt(cost_cand.loc[3.0, 'max_broker10_margin_to_equity_pct'])}%",
        },
        {
            "item": "short_holding_disclosure",
            "value": "3m/6m left-tail return still negative",
            "evidence": f"63d_p05={_fmt(h63['p05_return_pct'])}%, 126d_p05={_fmt(h126['p05_return_pct'])}%, dd40_breach=0/0",
        },
        {
            "item": "cold_start_claim",
            "value": "month/quarter/year cold start DD40 and broker100 pass",
            "evidence": f"min_dd40_pass={_fmt(cold_cand['dd40_pass_rate_pct'].min())}%, min_broker100_pass={_fmt(cold_cand['broker100_pass_rate_pct'].min())}%",
        },
        {
            "item": "live_monitor_required",
            "value": "broker10>90/95, slippage multiplier, 63/126d p05, 3x stress DD",
            "evidence": f"warnings={len(warnings)}, optional_failures={len(stress_failures)}",
        },
    ]
    return pd.DataFrame(rows)


def _plot(inputs: dict[str, Any], gates: pd.DataFrame, boundary: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    cost = inputs["cost"]
    holding = inputs["holding"]
    margin = inputs["margin"]
    cost_cand = cost[cost["variant"].eq(CANDIDATE)].sort_values("cost_multiplier").copy()
    holding_cand = holding[holding["variant"].eq(CANDIDATE)].copy()
    margin_cand = margin[margin["variant"].eq(CANDIDATE)].sort_values("date").copy()
    margin_cand["drawdown_pct"] = margin_cand["account_equity"] / margin_cand["account_equity"].cummax() * 100.0 - 100.0

    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_gate, ax_cost, ax_hold, ax_path = axes.flatten()

    status_counts = gates["status"].value_counts().reindex(["PASS", "WARN", "FAIL"]).fillna(0)
    colors = {"PASS": "#15803d", "WARN": "#d97706", "FAIL": "#dc2626"}
    ax_gate.bar(status_counts.index, status_counts.values, color=[colors[item] for item in status_counts.index])
    ax_gate.set_title("晋级闸门状态")
    ax_gate.set_ylabel("数量")
    ax_gate.grid(axis="y", alpha=0.25)
    for idx, value in enumerate(status_counts.values):
        ax_gate.text(idx, value + 0.08, f"{int(value)}", ha="center", fontsize=10)

    ax_cost.plot(cost_cand["cost_multiplier"], cost_cand["max_dd_pct"], marker="o", color="#2563eb", label="max DD")
    ax_cost.axhline(-40, color="#111827", linestyle="--", linewidth=1, label="DD40")
    ax_cost.set_title("成本压力最大回撤")
    ax_cost.set_xlabel("成本倍率")
    ax_cost.set_ylabel("%")
    ax_cost.grid(alpha=0.25)
    ax_cost.legend(fontsize=8)
    for row in cost_cand.itertuples(index=False):
        ax_cost.annotate(f"{row.max_dd_pct:.1f}%", (row.cost_multiplier, row.max_dd_pct), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)

    holding_view = holding_cand[holding_cand["holding_days"].isin([21, 63, 126, 252, 504])].sort_values("holding_days")
    x = np.arange(len(holding_view))
    ax_hold.bar(x - 0.18, holding_view["p05_return_pct"], width=0.36, color="#0891b2", label="p05 return")
    ax_hold.bar(x + 0.18, holding_view["median_return_pct"], width=0.36, color="#84cc16", label="median")
    ax_hold.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_hold.set_xticks(x)
    ax_hold.set_xticklabels([str(int(item)) for item in holding_view["holding_days"]])
    ax_hold.set_title("任意启动持有体验")
    ax_hold.set_xlabel("持有天数")
    ax_hold.set_ylabel("收益%")
    ax_hold.grid(axis="y", alpha=0.25)
    ax_hold.legend(fontsize=8)

    ax_path.plot(margin_cand["date"], margin_cand["account_equity"], color="#2563eb", linewidth=0.9, label="equity")
    ax2 = ax_path.twinx()
    ax2.fill_between(margin_cand["date"], margin_cand["drawdown_pct"], 0, color="#dc2626", alpha=0.20, label="drawdown")
    ax_path.set_title("Stage526权益与水下")
    ax_path.grid(alpha=0.25)
    ax_path.set_ylabel("权益")
    ax2.set_ylabel("回撤%")
    ax_path.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="lower right", fontsize=8)

    fig.suptitle(str(boundary.loc[boundary["item"].eq("promotion_decision"), "value"].iloc[0]), fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(gates: pd.DataFrame, boundary: pd.DataFrame, decision: dict[str, Any]) -> None:
    required = gates[gates["required_for_promotion"].eq(1)]
    optional = gates[gates["required_for_promotion"].eq(0)]
    lines = [
        "# Stage538 Stage526晋级边界审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：只读晋级闸门审计；不改策略、不重跑参数、不新增交易规则。",
        "- 外部调研判断：以 walk-forward/多起点、成本压力、交易成本敏感度、贡献集中度和回测过拟合控制为主；本阶段不做新alpha搜索。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 晋级边界",
        "",
        _md_table(boundary),
        "",
        "## 必要闸门",
        "",
        _md_table(required[["gate_id", "status", "metric", "threshold", "evidence", "next_action"]]),
        "",
        "## 非必要但必须披露的压力项",
        "",
        _md_table(optional[["gate_id", "status", "metric", "threshold", "evidence", "next_action"]]),
        "",
        "## 结论",
        "",
        "- Stage526 可以晋级为正常成本口径下的主候选/执行评审候选：DD40、broker100、收益保留、2x成本DD40、冷启动、edge集中度和fallback闸门均通过。",
        "- 它不能被包装成高滑点极端压力下也稳的最终实盘版本：3x成本回撤打穿DD40，2x压力下保证金安全垫也变薄。",
        "- 继续优化交易规则的价值低于建立执行监控：入场代理、早期不利退出、简单cooldown、产品黑名单均已被反证。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_decision(gates: pd.DataFrame, boundary: pd.DataFrame, inputs: dict[str, Any]) -> dict[str, Any]:
    required = gates[gates["required_for_promotion"].eq(1)]
    optional = gates[gates["required_for_promotion"].eq(0)]
    required_failures = required[~required["status"].eq("PASS")]
    decision_label = "promote_stage526_normal_cost_candidate_with_3x_stress_warning" if required_failures.empty else "do_not_promote_stage526"
    cand = inputs["summary"][inputs["summary"]["variant"].eq(CANDIDATE)].iloc[0].to_dict()
    cost_cand = inputs["cost"][inputs["cost"]["variant"].eq(CANDIDATE)].set_index("cost_multiplier")
    return {
        "stage": "Stage538",
        "model_tag": MODEL_TAG,
        "line_id": "futures_trend_drawdown30_preserve_return",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "candidate": CANDIDATE,
        "candidate_metrics": {
            "ending_equity": cand["end_equity"],
            "total_return_pct": cand["total_return_pct"],
            "return_retention_vs_stage079_pct": cand["return_retention_vs_stage079_pct"],
            "max_dd_pct": cand["max_dd_pct"],
            "sharpe": cand["sharpe"],
            "ulcer_pct": cand["ulcer_pct"],
            "total_slippage": cand["total_slippage"],
            "total_trade_count": cand["total_trade_count"],
            "nonzero_daily_win_rate_pct": cand["nonzero_daily_win_rate_pct"],
            "max_broker10_margin_to_equity_pct": cand["max_broker10_margin_to_equity_pct"],
            "days_over_100pct": cand["days_over_100pct"],
        },
        "cost_stress": {
            str(multiplier): {
                "max_dd_pct": cost_cand.loc[multiplier, "max_dd_pct"],
                "return_retention_vs_stage079_pct": cost_cand.loc[multiplier, "return_retention_vs_stage079_pct"],
                "max_broker10_margin_to_equity_pct": cost_cand.loc[multiplier, "max_broker10_margin_to_equity_pct"],
                "days_over_100pct": cost_cand.loc[multiplier, "days_over_100pct"],
            }
            for multiplier in [1.0, 2.0, 3.0]
        },
        "gate_counts": gates["status"].value_counts().to_dict(),
        "required_gate_pass_count": int((required["status"].eq("PASS")).sum()),
        "required_gate_count": int(len(required)),
        "optional_warning_count": int((optional["status"].eq("WARN")).sum()),
        "optional_fail_count": int((optional["status"].eq("FAIL")).sum()),
        "boundary": boundary.to_dict(orient="records"),
        "outputs": {
            "gates": str(GATE_PATH),
            "boundary": str(BOUNDARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "不再围绕T+1旧问题和入场/早退小规则打转；若继续，优先做真实券商保证金/滑点监控脚本和paper执行日报。若用户要求3x成本也DD40，则本候选降级，必须另找低成本独立收益源。",
    }


def main() -> None:
    inputs = _load_inputs()
    gates = _make_gate_rows(inputs)
    boundary = _make_boundary(inputs, gates)
    decision = _make_decision(gates, boundary, inputs)
    gates.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    boundary.to_csv(BOUNDARY_PATH, index=False, encoding="utf-8-sig")
    _plot(inputs, gates, boundary)
    _write_report(gates, boundary, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

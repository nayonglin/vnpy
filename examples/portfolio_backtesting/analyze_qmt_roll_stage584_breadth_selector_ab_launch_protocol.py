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


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage584_breadth_selector_ab_launch_protocol_v1"
OUTPUT_PREFIX = "qmt_roll_stage584_breadth_selector_ab_launch_protocol"

STAGE582_TAG = "stage582_breadth_selector_operational_gate_v1"
STAGE582_PREFIX = "qmt_roll_stage582_breadth_selector_operational_gate"
STAGE571_TAG = "stage571_external_selector_source_priority_audit_v1"
STAGE571_PREFIX = "qmt_roll_stage571_external_selector_source_priority_audit"
STAGE561_TAG = "stage561_selector_predictive_audit_protocol_v1"
STAGE561_PREFIX = "qmt_roll_stage561_selector_predictive_audit_protocol"
STAGE560_TAG = "stage560_forward_collection_run_gate_v1"
STAGE560_PREFIX = "qmt_roll_stage560_forward_collection_run_gate"

STAGE582_WATCHLIST = OUTPUT_DIR / f"{STAGE582_PREFIX}_watchlist_{STAGE582_TAG}.csv"
STAGE582_ROUTE_MATRIX = OUTPUT_DIR / f"{STAGE582_PREFIX}_route_matrix_{STAGE582_TAG}.csv"
STAGE582_FAMILY_BUDGET = OUTPUT_DIR / f"{STAGE582_PREFIX}_family_budget_{STAGE582_TAG}.csv"
STAGE582_GATES = OUTPUT_DIR / f"{STAGE582_PREFIX}_gates_{STAGE582_TAG}.csv"
STAGE571_SOURCE_PRIORITY = OUTPUT_DIR / f"{STAGE571_PREFIX}_source_priority_{STAGE571_TAG}.csv"
STAGE561_GATES = OUTPUT_DIR / f"{STAGE561_PREFIX}_gates_{STAGE561_TAG}.csv"
STAGE560_RUN_QUALITY = OUTPUT_DIR / f"{STAGE560_PREFIX}_run_quality_{STAGE560_TAG}.csv"
STAGE560_ROUTE_HEALTH = OUTPUT_DIR / f"{STAGE560_PREFIX}_route_latest_health_{STAGE560_TAG}.csv"

AB_ARMS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ab_arms_{MODEL_TAG}.csv"
SELECTOR_BLUEPRINT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selector_blueprint_{MODEL_TAG}.csv"
TIE_BREAK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_tie_break_{MODEL_TAG}.csv"
LAUNCH_GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_launch_gates_{MODEL_TAG}.csv"
RUNBOOK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_runbook_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20
MIN_READY_ROUTES_PER_P0 = 2
MIN_EVENT_READY_PRODUCTS = 5
MAX_AVG_PAIRWISE_ABS_CORR = 0.20
MAX_PAIRWISE_ABS_CORR = 0.50
MAX_FAMILY_BUDGET_PCT = 20.0
MAX_PRODUCT_RISK_UNIT = 0.20
MAX_SELECTOR_TRIALS = 1
MIN_MEAN_SPEARMAN_IC = 0.05
MIN_POSITIVE_IC_RATE_PCT = 60.0


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
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
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _gate_row(gate: str, passed: bool, actual: str, required: str, severity: str, judgement: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": int(bool(passed)),
        "actual": actual,
        "required": required,
        "severity": severity,
        "judgement": judgement,
    }


def _parse_progress(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).split("/")[0].strip()))
    except (TypeError, ValueError):
        return default


def load_context() -> dict[str, pd.DataFrame]:
    watch = _read_csv(STAGE582_WATCHLIST)
    routes = _read_csv(STAGE582_ROUTE_MATRIX)
    family = _read_csv(STAGE582_FAMILY_BUDGET)
    stage582_gates = _read_csv(STAGE582_GATES)
    source_priority = _read_csv(STAGE571_SOURCE_PRIORITY)
    stage561_gates = _read_csv(STAGE561_GATES)
    run_quality = _read_csv(STAGE560_RUN_QUALITY)
    route_health = _read_csv(STAGE560_ROUTE_HEALTH)
    return {
        "watch": watch,
        "routes": routes,
        "family": family,
        "stage582_gates": stage582_gates,
        "source_priority": source_priority,
        "stage561_gates": stage561_gates,
        "run_quality": run_quality,
        "route_health": route_health,
    }


def build_ab_arms() -> pd.DataFrame:
    rows = [
        {
            "arm": "A_stage526_control",
            "purpose": "当前主研究候选/控制组",
            "definition": "risk0.80 + productcap25 + maxpos4; no breadth selector sleeve",
            "status_now": "ready_as_control_reference",
            "must_not_change": "Stage526 alpha, entry, exit, AI pool eval_date semantics",
            "launch_condition": "available as benchmark only; live TCA evidence remains separate open risk",
            "promotion_role": "baseline",
        },
        {
            "arm": "B_breadth_selector_sleeve_standalone",
            "purpose": "验证低单笔风险扩池是否有独立趋势来源",
            "definition": "P0 watchlist only; product risk unit <=0.20; family cap <=20%; same-family same-direction top1 only; point-in-time selector score required",
            "status_now": "blocked_by_selector_evidence",
            "must_not_change": "no hindsight top products, no future labels, no TopN/risk/corr grid",
            "launch_condition": "Stage561 20/20 + P0 route/event coverage + frozen IC/bucket pass",
            "promotion_role": "information value; not enough alone to replace Stage526",
        },
        {
            "arm": "C_stage526_plus_breadth_selector_sleeve",
            "purpose": "真实晋级候选，检验是否改善3/6个月体验且不劣化Stage526",
            "definition": "Stage526 unchanged + frozen B sleeve; core positions are not replaced by new products",
            "status_now": "blocked_by_selector_evidence",
            "must_not_change": "no capital taken away from Stage526 core until paper sleeve passes; exact margin/TCA gates required",
            "launch_condition": "B passes fixed predictive audit and one frozen paper replay; then run A/C only once",
            "promotion_role": "only promotable arm",
        },
    ]
    return pd.DataFrame(rows)


def build_selector_blueprint(source_priority: pd.DataFrame) -> pd.DataFrame:
    priority_lookup = {
        str(row["source_route"]): row.to_dict()
        for _, row in source_priority.iterrows()
        if "source_route" in source_priority.columns
    }
    rows: list[dict[str, Any]] = []
    feature_defs = [
        ("basis_rank", "basis", 0.25, "cross-sectional rank within received_date; missing stays missing", "candidate feature after 20-date PIT gate"),
        ("inventory_rank", "inventory", 0.25, "cross-sectional rank within received_date; missing stays missing", "candidate feature after 20-date PIT gate"),
        ("event_alignment", "sentiment_news_manual_event", 0.25, "real event direction/relevance already received before eval_time; no relabeling", "only if real event row exists"),
        ("market_state_guardrail", "market_state_guardrail", 0.25, "capacity/liquidity/core-corr guardrail; not alpha by itself", "risk guardrail"),
    ]
    for component, route_key, frozen_weight, transform, role in feature_defs:
        source = priority_lookup.get(route_key, {})
        if route_key == "sentiment_news_manual_event":
            source = priority_lookup.get("sentiment_news", priority_lookup.get("manual_event", {}))
        rows.append(
            {
                "component": component,
                "source_route": route_key,
                "frozen_weight_if_audit_allowed": frozen_weight,
                "transform": transform,
                "role": role,
                "latest_forward_ready_products": source.get("latest_forward_ready_products", ""),
                "history_ready_products": source.get("history_ready_products", ""),
                "current_status": source.get("standalone_predictive_status", "not_yet_audited"),
                "allowed_now": 0,
                "why_not_allowed_now": "Stage561 data depth and P0 operational gates are not complete",
            }
        )
    rows.append(
        {
            "component": "forbidden_hindsight",
            "source_route": "future_outcomes",
            "frozen_weight_if_audit_allowed": 0.0,
            "transform": "never use future_* / oracle / historical top winners as features",
            "role": "forbidden",
            "latest_forward_ready_products": "",
            "history_ready_products": "",
            "current_status": "forbidden",
            "allowed_now": 0,
            "why_not_allowed_now": "not available at selector_eval_time",
        }
    )
    return pd.DataFrame(rows)


def build_tie_break(watch: pd.DataFrame, family: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, fam in family.iterrows():
        products = [item.strip() for item in str(fam.get("p0_products", "")).split(",") if item.strip()]
        family_name = str(fam.get("product_family", ""))
        group = watch[watch["product_vt_symbol"].astype(str).isin(products)].copy()
        for column in ["total_pnl", "route_ready_count", "abs_core_daily_pnl_corr", "max_abs_pairwise_corr_in_p0"]:
            group[column] = _num(group, column)
        if len(group) > 1:
            group = group.sort_values(
                ["route_ready_count", "total_pnl", "abs_core_daily_pnl_corr"],
                ascending=[False, False, True],
            )
            provisional_monitor_rank = list(group["product_vt_symbol"].astype(str))
            rule = (
                "If same-family products have same-direction sleeve signals, allocate only to the highest frozen "
                "point-in-time selector score. If selector score is unavailable or tied, do not add sleeve risk for the family."
            )
        else:
            provisional_monitor_rank = list(group["product_vt_symbol"].astype(str))
            rule = "Single P0 product in family; family cap still applies."
        rows.append(
            {
                "product_family": family_name,
                "p0_products": ",".join(products),
                "p0_product_count": len(products),
                "family_budget_cap_pct": float(fam.get("suggested_family_budget_cap_pct", MAX_FAMILY_BUDGET_PCT)),
                "same_family_tie_break_required": int(len(products) > 1),
                "provisional_monitor_rank_not_trade_rule": ",".join(provisional_monitor_rank),
                "frozen_trade_rule": rule,
                "trading_allowed_now": 0,
            }
        )
    return pd.DataFrame(rows)


def build_launch_gates(
    watch: pd.DataFrame,
    routes: pd.DataFrame,
    family_tie: pd.DataFrame,
    stage561_gates: pd.DataFrame,
    run_quality: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    p0_count = int(len(watch))
    route_ready_products = int((_num(watch, "route_ready_count") >= MIN_READY_ROUTES_PER_P0).sum())
    event_ready_products = int(_num(watch, "sentiment_news_manual_event_ready").sum())
    avg_pair_abs = float(_num(watch, "max_abs_pairwise_corr_in_p0").mean()) if p0_count else 0.0
    max_pair_abs = float(_num(watch, "max_abs_pairwise_corr_in_p0").max()) if p0_count else 0.0
    forward_runs = 0
    forward_dates = 0
    for _, row in stage561_gates.iterrows():
        gate = str(row.get("gate", ""))
        if gate == "forward_runs_ready":
            forward_runs = _parse_progress(row.get("current", 0))
        if gate == "forward_dates_ready":
            forward_dates = _parse_progress(row.get("current", 0))
    qualified_runs = int(_num(run_quality, "qualified_for_selector_depth").sum()) if not run_quality.empty else 0
    qualified_dates = (
        int(run_quality.loc[_num(run_quality, "qualified_for_selector_depth").ge(1), "received_date"].nunique())
        if not run_quality.empty and "received_date" in run_quality.columns
        else 0
    )
    same_family_rules_frozen = int((family_tie["same_family_tie_break_required"].fillna(0).astype(int) > 0).sum())
    same_family_rules_frozen = bool(len(family_tie) > 0 and family_tie["frozen_trade_rule"].fillna("").astype(str).str.len().gt(0).all())

    rows = [
        _gate_row(
            "ab_arms_predeclared",
            True,
            "A/B/C frozen",
            "A/B/C frozen before new selector results",
            "hard",
            "防止看到结果后重新定义对照组。",
        ),
        _gate_row(
            "p0_watchlist_ready",
            p0_count >= 5,
            f"{p0_count} P0",
            ">=5 P0 products",
            "hard",
            "观察池够用，但仍不是交易白名单。",
        ),
        _gate_row(
            "p0_route_coverage_ready",
            route_ready_products == p0_count and p0_count > 0,
            f"{route_ready_products}/{p0_count}",
            f"each P0 has >= {MIN_READY_ROUTES_PER_P0} routes",
            "hard",
            "每个P0都要有至少两条点时化外生路线。",
        ),
        _gate_row(
            "p0_event_coverage_ready",
            event_ready_products >= MIN_EVENT_READY_PRODUCTS,
            f"{event_ready_products}/{p0_count}",
            f">={MIN_EVENT_READY_PRODUCTS} event-ready P0 products",
            "hard",
            "舆情/事件覆盖不足时不能做全池事件selector。",
        ),
        _gate_row(
            "pairwise_corr_budget_ready",
            avg_pair_abs <= MAX_AVG_PAIRWISE_ABS_CORR and max_pair_abs <= MAX_PAIRWISE_ABS_CORR,
            f"avg max-peer={avg_pair_abs:.4f}, max={max_pair_abs:.4f}",
            f"avg<={MAX_AVG_PAIRWISE_ABS_CORR}, max<={MAX_PAIRWISE_ABS_CORR}",
            "hard",
            "当前高相关不是主要瓶颈，但预算仍要固定。",
        ),
        _gate_row(
            "same_family_tie_break_frozen",
            same_family_rules_frozen,
            "frozen" if same_family_rules_frozen else "missing",
            "frozen tie-break before selector replay",
            "hard",
            "y/c 等同族同向不能同时吃满 sleeve 风险。",
        ),
        _gate_row(
            "forward_runs_ready",
            forward_runs >= MIN_FORWARD_RUNS and qualified_runs >= MIN_FORWARD_RUNS,
            f"stage561={forward_runs}, qualified={qualified_runs}",
            f">={MIN_FORWARD_RUNS}",
            "hard",
            "forward样本不足前禁止收益回测化selector。",
        ),
        _gate_row(
            "forward_dates_ready",
            forward_dates >= MIN_FORWARD_DATES and qualified_dates >= MIN_FORWARD_DATES,
            f"stage561={forward_dates}, qualified={qualified_dates}",
            f">={MIN_FORWARD_DATES}",
            "hard",
            "同日重复采集不能增加样本深度。",
        ),
        _gate_row(
            "fixed_ic_bucket_rules_predeclared",
            True,
            f"IC>={MIN_MEAN_SPEARMAN_IC}, posIC>={MIN_POSITIVE_IC_RATE_PCT:.0f}%",
            "predeclared",
            "hard",
            "未来只允许一次冻结IC/bucket审计，不允许扫TopN/权重。",
        ),
        _gate_row(
            "selector_backtest_allowed_now",
            False,
            "not allowed",
            "only after all hard data gates pass",
            "hard",
            "本阶段明确禁止收益回测和交易候选晋级。",
        ),
    ]
    gates = pd.DataFrame(rows)
    hard = gates[gates["severity"].eq("hard")]
    launch_allowed = bool(int(hard["passed"].sum()) == len(hard))
    summary = {
        "p0_count": p0_count,
        "route_ready_products": route_ready_products,
        "event_ready_products": event_ready_products,
        "avg_p0_max_peer_abs_corr": avg_pair_abs,
        "max_p0_peer_abs_corr": max_pair_abs,
        "forward_runs": forward_runs,
        "forward_dates": forward_dates,
        "qualified_runs": qualified_runs,
        "qualified_dates": qualified_dates,
        "hard_gate_pass_count": int(hard["passed"].sum()),
        "hard_gate_count": int(len(hard)),
        "all_gate_pass_count": int(gates["passed"].sum()),
        "all_gate_count": int(len(gates)),
        "launch_allowed": launch_allowed,
    }
    return gates, summary


def write_chart(
    arms: pd.DataFrame,
    routes: pd.DataFrame,
    family_tie: pd.DataFrame,
    gates: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    fig.suptitle("Stage584 breadth selector A/B launch protocol", fontsize=16, fontweight="bold")

    ax = axes[0, 0]
    arm_status = arms.copy()
    arm_status["ready_score"] = np.where(arm_status["status_now"].astype(str).str.contains("ready"), 1, 0)
    ax.barh(arm_status["arm"], arm_status["ready_score"], color=np.where(arm_status["ready_score"].eq(1), "#2f9e44", "#e03131"))
    ax.set_xlim(0, 1)
    ax.set_title("A/B/C arms: only control is currently runnable")
    for idx, row in arm_status.iterrows():
        ax.text(0.03, idx, row["status_now"], va="center", fontsize=8, color="white" if row["ready_score"] else "black")

    ax = axes[0, 1]
    route_cols = ["basis_ready", "inventory_ready", "sentiment_news_manual_event_ready"]
    matrix = routes.set_index("product_vt_symbol")[[col for col in route_cols if col in routes.columns]].fillna(0).astype(float)
    im = ax.imshow(matrix.values, vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels([col.replace("_ready", "") for col in matrix.columns], rotation=25, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, int(matrix.iloc[i, j]), ha="center", va="center", fontsize=10)
    ax.set_title("P0 point-in-time route coverage")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 0]
    fam = family_tie.sort_values(["same_family_tie_break_required", "p0_product_count"], ascending=[True, True])
    colors = np.where(fam["same_family_tie_break_required"].astype(int).eq(1), "#ffa94d", "#4dabf7")
    ax.barh(fam["product_family"], fam["p0_product_count"], color=colors)
    ax.set_title("Family cap and tie-break")
    ax.set_xlabel("P0 count")
    for _, row in fam.iterrows():
        text = f"cap {row['family_budget_cap_pct']:.0f}%"
        if int(row["same_family_tie_break_required"]):
            text += " / top1 only"
        ax.text(row["p0_product_count"] + 0.03, row["product_family"], text, va="center", fontsize=9)
    ax.set_xlim(0, max(2.5, float(fam["p0_product_count"].max()) + 0.5))

    ax = axes[1, 1]
    gate_plot = gates.copy()
    gate_plot["score"] = gate_plot["passed"].astype(int)
    ax.barh(gate_plot["gate"], gate_plot["score"], color=np.where(gate_plot["score"].eq(1), "#2f9e44", "#e03131"))
    ax.set_xlim(0, 1)
    ax.set_title(f"Launch gates {summary['all_gate_pass_count']}/{summary['all_gate_count']} | hard {summary['hard_gate_pass_count']}/{summary['hard_gate_count']}")
    for idx, row in gate_plot.iterrows():
        ax.text(0.03, idx, row["actual"], va="center", fontsize=8, color="white" if row["score"] else "black")

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_runbook(arms: pd.DataFrame, blueprint: pd.DataFrame, tie: pd.DataFrame, gates: pd.DataFrame) -> None:
    text = f"""# Stage584 future A/B launch runbook

This runbook is frozen before selector labels mature.

## Current Arms

{_md_table(arms, ["arm", "purpose", "status_now", "launch_condition"], 10)}

## Frozen Selector Blueprint

{_md_table(blueprint, ["component", "source_route", "frozen_weight_if_audit_allowed", "transform", "allowed_now"], 20)}

## Family Tie-Break

{_md_table(tie, ["product_family", "p0_products", "family_budget_cap_pct", "same_family_tie_break_required", "frozen_trade_rule"], 20)}

## Launch Gates

{_md_table(gates, max_rows=30)}

## Forbidden Actions

- Do not use historical top winners, Stage541/543 `future_*`, Oracle fields, or realized future PnL as selector features.
- Do not change TopN, risk unit, family cap, correlation threshold, or feature weights after 63d/126d labels are seen.
- Do not let the breadth sleeve replace Stage526 core positions in the first A/C replay.
- Do not promote B. Only C can be a promotion candidate.
- Do not claim live feasibility until Stage526 TCA P0 evidence and new-sleeve liquidity gates pass.
"""
    RUNBOOK_PATH.write_text(text, encoding="utf-8")


def write_report(
    arms: pd.DataFrame,
    blueprint: pd.DataFrame,
    tie: pd.DataFrame,
    gates: pd.DataFrame,
    summary: dict[str, Any],
    decision: dict[str, Any],
) -> None:
    text = f"""# Stage584 breadth selector A/B launch protocol

- line_id: `{LINE_ID}`
- generated_at: `{decision["generated_at_cst"]} CST`
- decision: `{decision["decision"]}`
- launch_allowed: `{summary["launch_allowed"]}`
- hard gates: `{summary["hard_gate_pass_count"]}/{summary["hard_gate_count"]}`
- all gates: `{summary["all_gate_pass_count"]}/{summary["all_gate_count"]}`

## Research Judgement

外部 CTA/趋势跟踪资料支持跨市场分散、风险预算和相关性治理，但不支持事后赢家白名单。结合本地 Stage257/264/282 结果，本阶段判断是：低单笔风险扩池方向有价值，但当前不能回测或晋级；必须先把 A/B/C 对照、selector 特征、同族 tie-break 和禁止事项冻结。

这不是一次收益回测，也不是新交易版本。它是未来开跑前的防过拟合闸门。

## A/B/C Arms

{_md_table(arms, ["arm", "purpose", "definition", "status_now", "launch_condition", "promotion_role"], 20)}

## Frozen Selector Blueprint

{_md_table(blueprint, ["component", "source_route", "frozen_weight_if_audit_allowed", "current_status", "allowed_now", "why_not_allowed_now"], 20)}

## Family Tie-Break

{_md_table(tie, ["product_family", "p0_products", "family_budget_cap_pct", "same_family_tie_break_required", "provisional_monitor_rank_not_trade_rule", "frozen_trade_rule"], 20)}

## Launch Gates

{_md_table(gates, max_rows=30)}

## Visual Review Notes

- 左上图显示只有 `A_stage526_control` 当前可作为对照，B/C 都被 selector 证据阻塞。
- 右上图显示 P0 的 basis/inventory 覆盖较好，但事件/舆情覆盖仍集中在 `y/c`，`v/lu/ao` 不足。
- 左下图显示 `grains_oilseeds` 家族有 `y/c` 双 P0，必须 top1 tie-break，不能同族同向等权加风险。
- 右下图显示 launch gate 主要失败在 P0 route/event 覆盖、forward `20/20` 样本和 selector backtest allowed；相关性预算和 tie-break 已经不是当前主瓶颈。

## Conclusion

当前只允许继续 point-in-time forward collection 和标签等待。未达硬闸门前，禁止：

- P0 交易白名单。
- B/C 收益回测。
- TopN/risk/corr/family cap 小数扫描。
- 用历史赢家或 future label 训练 selector。
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    ctx = load_context()
    watch = ctx["watch"]
    routes = ctx["routes"]
    family = ctx["family"]
    source_priority = ctx["source_priority"]
    stage561_gates = ctx["stage561_gates"]
    run_quality = ctx["run_quality"]

    arms = build_ab_arms()
    blueprint = build_selector_blueprint(source_priority)
    tie = build_tie_break(watch, family)
    gates, summary = build_launch_gates(watch, routes, tie, stage561_gates, run_quality)

    decision_label = "breadth_selector_ab_launch_not_allowed_protocol_frozen"
    if summary["launch_allowed"]:
        decision_label = "breadth_selector_ab_launch_allowed_after_protocol_gate"
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "summary": summary,
        "strategy_changed": False,
        "backtest_rerun": False,
        "new_trade_candidate": False,
        "promotion_allowed": False,
        "ab_launch_allowed": bool(summary["launch_allowed"]),
        "max_selector_trials": MAX_SELECTOR_TRIALS,
        "overfit_assessment": "not overfit: this freezes arms, features and tie-break before selector labels are mature; no return backtest is run",
        "continue_value": "yes: this makes the breadth route executable later without allowing hindsight selector tuning",
        "references": [
            "A Century of Evidence on Trend-Following Investing: https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing-executive-summ",
            "Optimal Allocation of Trend Following Strategies: https://arxiv.org/abs/1410.8409",
            "pysystemtrade repository and documentation on diversification/correlation/risk budgeting: https://github.com/robcarver17/pysystemtrade",
            "Trend following instrument diversification / CTA universe reference: https://www.iasg.com/blog/2019/11/29/commodity-trading-advisors-ctas-in-perspective",
        ],
        "outputs": {
            "ab_arms": str(AB_ARMS_PATH),
            "selector_blueprint": str(SELECTOR_BLUEPRINT_PATH),
            "family_tie_break": str(TIE_BREAK_PATH),
            "launch_gates": str(LAUNCH_GATES_PATH),
            "runbook": str(RUNBOOK_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    arms.to_csv(AB_ARMS_PATH, index=False, encoding="utf-8-sig")
    blueprint.to_csv(SELECTOR_BLUEPRINT_PATH, index=False, encoding="utf-8-sig")
    tie.to_csv(TIE_BREAK_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(LAUNCH_GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_runbook(arms, blueprint, tie, gates)
    write_chart(arms, routes, tie, gates, summary)
    write_report(arms, blueprint, tie, gates, summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

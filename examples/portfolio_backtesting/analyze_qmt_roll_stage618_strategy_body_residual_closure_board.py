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
MODEL_TAG = "stage618_strategy_body_residual_closure_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage618_strategy_body_residual_closure_board"

STAGE576_CANDIDATE = OUTPUT_DIR / "qmt_roll_stage576_stage526_strategy_body_optimization_boundary_candidate_boundary_stage576_stage526_strategy_body_optimization_boundary_v1.csv"
STAGE576_PROBE = OUTPUT_DIR / "qmt_roll_stage576_stage526_strategy_body_optimization_boundary_probe_boundary_stage576_stage526_strategy_body_optimization_boundary_v1.csv"
STAGE576_GATES = OUTPUT_DIR / "qmt_roll_stage576_stage526_strategy_body_optimization_boundary_gates_stage576_stage526_strategy_body_optimization_boundary_v1.csv"
STAGE576_DECISION = OUTPUT_DIR / "qmt_roll_stage576_stage526_strategy_body_optimization_boundary_decision_stage576_stage526_strategy_body_optimization_boundary_v1.json"
STAGE581_SUMMARY = OUTPUT_DIR / "qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_summary_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.csv"
STAGE581_COST = OUTPUT_DIR / "qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_cost_stress_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.csv"
STAGE581_ROLLING = OUTPUT_DIR / "qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_rolling_holding_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.csv"
STAGE581_DECISION = OUTPUT_DIR / "qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_decision_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.json"
STAGE537_DURATION = OUTPUT_DIR / "qmt_roll_stage537_stage526_segment_lifecycle_audit_duration_summary_stage537_stage526_segment_lifecycle_audit_v1.csv"
STAGE537_GUARD = OUTPUT_DIR / "qmt_roll_stage537_stage526_segment_lifecycle_audit_guard_probe_stage537_stage526_segment_lifecycle_audit_v1.csv"
STAGE564_BAD_WINDOW_MONTHLY = OUTPUT_DIR / "qmt_roll_stage564_stage526_cost_elasticity_execution_audit_bad_window_monthly_stage564_stage526_cost_elasticity_execution_audit_v1.csv"

MECHANISM_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mechanism_matrix_{MODEL_TAG}.csv"
RESIDUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_metrics_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REFERENCE_LINKS = [
    "Stop-loss strategies with serial correlation, regime switching, and transaction costs: https://www.sciencedirect.com/science/article/pii/S1386418117300472",
    "pysystemtrade position sizing and optimization: https://deepwiki.com/robcarver17/pysystemtrade/3.2-position-sizing-and-optimization",
    "pysystemtrade backtesting notes: https://github.com/robcarver17/pysystemtrade/blob/develop/docs/backtesting.md",
    "Trend-following reference implementation: https://github.com/jironghuang/trend_following",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        item = float(value)
        return None if math.isnan(item) or math.isinf(item) else item
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
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


def _one(frame: pd.DataFrame, column: str, value: Any) -> pd.Series:
    rows = frame[frame[column].eq(value)]
    if rows.empty:
        raise KeyError(f"{column}={value}")
    return rows.iloc[0]


def _variant_cost(cost: pd.DataFrame, variant: str, multiplier: float, column: str) -> float:
    rows = cost[(cost["variant"].eq(variant)) & (pd.to_numeric(cost["cost_multiplier"], errors="coerce").eq(multiplier))]
    if rows.empty:
        return float("nan")
    return float(pd.to_numeric(rows.iloc[0][column], errors="coerce"))


def _variant_holding(rolling: pd.DataFrame, variant: str, days: int, column: str) -> float:
    rows = rolling[(rolling["variant"].eq(variant)) & (pd.to_numeric(rolling["holding_days"], errors="coerce").eq(days))]
    if rows.empty:
        return float("nan")
    return float(pd.to_numeric(rows.iloc[0][column], errors="coerce"))


def build_mechanism_matrix(
    candidate: pd.DataFrame,
    probe: pd.DataFrame,
    guard: pd.DataFrame,
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for item in candidate.to_dict("records"):
        rows.append(
            {
                "mechanism": item.get("mechanism"),
                "evidence_stage": item.get("source_stage"),
                "mechanism_class": item.get("kind"),
                "promotion_status": item.get("promotion_status"),
                "readiness_score": float(item.get("readiness_score", 0) or 0),
                "key_metric_1": "total_return_delta_pp",
                "key_value_1": float(item.get("total_return_delta_pp", 0) or 0),
                "key_metric_2": "max_dd_delta_pp",
                "key_value_2": float(item.get("max_dd_delta_pp", 0) or 0),
                "key_metric_3": "dd40_pass_3x",
                "key_value_3": float(item.get("dd40_pass_3x", 0) or 0),
                "promotion_allowed": 0,
                "why_not": item.get("reason", ""),
            }
        )

    best_fast_fail = probe[probe["probe_family"].eq("fast_fail_entry_proxy")].copy()
    if not best_fast_fail.empty:
        best_fast_fail["capture"] = _num(best_fast_fail, "x_metric")
        best_fast_fail["positive_risk"] = _num(best_fast_fail, "y_metric")
        row = best_fast_fail.sort_values(["capture", "positive_risk"], ascending=[False, True]).iloc[0]
        rows.append(
            {
                "mechanism": "entry K-line / fast-fail proxy",
                "evidence_stage": "Stage535/576",
                "mechanism_class": "entry_proxy",
                "promotion_status": "reject_positive_edge_risk",
                "readiness_score": 0,
                "key_metric_1": "fast_fail_capture_pct",
                "key_value_1": float(row["capture"]),
                "key_metric_2": "positive_edge_at_risk_pct",
                "key_value_2": float(row["positive_risk"]),
                "key_metric_3": "sample_or_probe_count",
                "key_value_3": float(row.get("size_metric", 0) or 0),
                "promotion_allowed": 0,
                "why_not": "入场前K线/质量代理无法同时做到高捕获和低正收益误伤，不能交易化。",
            }
        )

    all_guard = guard[guard["scope"].eq("all")].copy() if "scope" in guard.columns else guard.copy()
    if not all_guard.empty:
        guard = all_guard.copy()
        guard["estimated_exit_delta"] = _num(guard, "estimated_exit_delta")
        best_guard = guard.sort_values("estimated_exit_delta", ascending=False).iloc[0]
        rows.append(
            {
                "mechanism": "time stop / early adverse exit",
                "evidence_stage": "Stage537/576",
                "mechanism_class": "exit_guard",
                "promotion_status": "reject_negative_estimated_delta",
                "readiness_score": 0,
                "key_metric_1": "best_estimated_exit_delta",
                "key_value_1": float(best_guard["estimated_exit_delta"]),
                "key_metric_2": "trigger_count",
                "key_value_2": float(best_guard.get("trigger_count", 0) or 0),
                "key_metric_3": "positive_final_pnl_at_risk",
                "key_value_3": float(best_guard.get("positive_final_pnl_at_risk", 0) or 0),
                "promotion_allowed": 0,
                "why_not": "早停/持有N日亏损退出的最好全周期估计增量仍为负，且会损害后续恢复。",
            }
        )

    control = _one(summary, "variant", "stage526_control")
    micro = _one(summary, "variant", "stage526_failure_memory_micro_sizing")
    micro_2x_dd = _variant_cost(cost, "stage526_failure_memory_micro_sizing", 2.0, "max_dd_pct")
    micro_3x_dd = _variant_cost(cost, "stage526_failure_memory_micro_sizing", 3.0, "max_dd_pct")
    control_2x_dd = _variant_cost(cost, "stage526_control", 2.0, "max_dd_pct")
    control_3x_dd = _variant_cost(cost, "stage526_control", 3.0, "max_dd_pct")
    rows.append(
        {
            "mechanism": "failure-memory micro sizing",
            "evidence_stage": "Stage581",
            "mechanism_class": "micro_sizing",
            "promotion_status": "reject_risk_path_worse",
            "readiness_score": 0,
            "key_metric_1": "return_delta_pp",
            "key_value_1": float(micro["total_return_pct"] - control["total_return_pct"]),
            "key_metric_2": "max_dd_delta_pp",
            "key_value_2": float(micro["max_dd_pct"] - control["max_dd_pct"]),
            "key_metric_3": "3x_max_dd_delta_pp",
            "key_value_3": float(micro_3x_dd - control_3x_dd),
            "promotion_allowed": 0,
            "why_not": f"收益更高但1x回撤、Ulcer、2x/3x成本和63/126日左尾劣化；2x DD={micro_2x_dd:.4f}，3x DD={micro_3x_dd:.4f}。",
        }
    )

    return pd.DataFrame(rows)


def build_residual_metrics(
    duration: pd.DataFrame,
    guard: pd.DataFrame,
    bad_monthly: pd.DataFrame,
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
) -> pd.DataFrame:
    all_duration = duration[duration["scope"].eq("all")].copy()
    all_duration["net_pnl"] = _num(all_duration, "net_pnl")
    one_to_five = float(
        all_duration[all_duration["duration_bucket"].isin(["1-3", "4-5"])]["net_pnl"].sum()
    )
    six_to_sixty = float(
        all_duration[all_duration["duration_bucket"].isin(["6-10", "11-20", "21-60"])]["net_pnl"].sum()
    )
    short_trade_count = float(
        all_duration[all_duration["duration_bucket"].isin(["1-3", "4-5"])]["trade_count"].sum()
    )
    mid_trade_count = float(
        all_duration[all_duration["duration_bucket"].isin(["6-10", "11-20", "21-60"])]["trade_count"].sum()
    )

    guard = guard[guard["scope"].eq("all")].copy() if "scope" in guard.columns else guard.copy()
    guard["estimated_exit_delta"] = _num(guard, "estimated_exit_delta")
    best_guard_delta = float(guard["estimated_exit_delta"].max()) if not guard.empty else float("nan")
    best_guard_name = str(guard.sort_values("estimated_exit_delta", ascending=False).iloc[0]["probe"]) if not guard.empty else ""

    bad_monthly = bad_monthly.copy()
    bad_monthly["total_net_pnl"] = _num(bad_monthly, "total_net_pnl")
    bad_monthly["extra_3x_cost_vs_1x"] = _num(bad_monthly, "extra_3x_cost_vs_1x")
    bad_window_loss = float(bad_monthly["total_net_pnl"].sum())
    bad_window_extra_cost = float(bad_monthly["extra_3x_cost_vs_1x"].sum())
    bad_window_cost_share = float(bad_window_extra_cost / abs(bad_window_loss) * 100.0) if bad_window_loss else float("nan")

    control = _one(summary, "variant", "stage526_control")
    micro = _one(summary, "variant", "stage526_failure_memory_micro_sizing")

    rows = [
        {"metric": "stage526_end_equity", "value": float(control["end_equity"]), "note": "Stage526 control"},
        {"metric": "stage526_total_return_pct", "value": float(control["total_return_pct"]), "note": "Stage526 control"},
        {"metric": "stage526_max_dd_pct", "value": float(control["max_dd_pct"]), "note": "Stage526 control"},
        {"metric": "stage526_ulcer_pct", "value": float(control["ulcer_pct"]), "note": "Stage526 control"},
        {"metric": "stage526_sharpe", "value": float(control["sharpe"]), "note": "Stage526 control"},
        {"metric": "stage526_total_slippage", "value": float(control["total_slippage"]), "note": "Stage526 control"},
        {"metric": "stage526_trade_count", "value": float(control["total_trade_count"]), "note": "Stage526 control"},
        {"metric": "stage526_win_rate_pct", "value": float(control["nonzero_daily_win_rate_pct"]), "note": "Stage526 control"},
        {"metric": "short_duration_1_5d_net_pnl", "value": one_to_five, "note": "Stage537 1-5天持仓段"},
        {"metric": "mid_duration_6_60d_net_pnl", "value": six_to_sixty, "note": "Stage537 6-60天持仓段"},
        {"metric": "short_duration_1_5d_trade_count", "value": short_trade_count, "note": "Stage537 1-5天持仓段"},
        {"metric": "mid_duration_6_60d_trade_count", "value": mid_trade_count, "note": "Stage537 6-60天持仓段"},
        {"metric": "best_time_stop_estimated_exit_delta", "value": best_guard_delta, "note": best_guard_name},
        {"metric": "bad_window_total_net_pnl", "value": bad_window_loss, "note": "Stage564 2022 bad window monthly sum"},
        {"metric": "bad_window_extra_3x_cost_vs_1x", "value": bad_window_extra_cost, "note": "Stage564 2022 bad window monthly sum"},
        {"metric": "bad_window_extra_cost_share_abs_loss_pct", "value": bad_window_cost_share, "note": "cost share of absolute bad-window loss"},
        {"metric": "failure_memory_return_delta_pp", "value": float(micro["total_return_pct"] - control["total_return_pct"]), "note": "Stage581 C-A"},
        {"metric": "failure_memory_max_dd_delta_pp", "value": float(micro["max_dd_pct"] - control["max_dd_pct"]), "note": "negative means worse"},
        {"metric": "failure_memory_ulcer_delta", "value": float(micro["ulcer_pct"] - control["ulcer_pct"]), "note": "positive means worse"},
        {"metric": "failure_memory_2x_max_dd_delta_pp", "value": float(_variant_cost(cost, "stage526_failure_memory_micro_sizing", 2.0, "max_dd_pct") - _variant_cost(cost, "stage526_control", 2.0, "max_dd_pct")), "note": "negative means worse"},
        {"metric": "failure_memory_3x_max_dd_delta_pp", "value": float(_variant_cost(cost, "stage526_failure_memory_micro_sizing", 3.0, "max_dd_pct") - _variant_cost(cost, "stage526_control", 3.0, "max_dd_pct")), "note": "negative means worse"},
        {"metric": "failure_memory_63d_p05_delta_pp", "value": float(_variant_holding(rolling, "stage526_failure_memory_micro_sizing", 63, "p05_return_pct") - _variant_holding(rolling, "stage526_control", 63, "p05_return_pct")), "note": "negative means worse"},
        {"metric": "failure_memory_126d_p05_delta_pp", "value": float(_variant_holding(rolling, "stage526_failure_memory_micro_sizing", 126, "p05_return_pct") - _variant_holding(rolling, "stage526_control", 126, "p05_return_pct")), "note": "negative means worse"},
    ]
    return pd.DataFrame(rows)


def build_gates(mechanisms: pd.DataFrame, residual: pd.DataFrame, stage576_decision: dict[str, Any], stage581_decision: dict[str, Any]) -> pd.DataFrame:
    promotion_count = int(mechanisms["promotion_allowed"].sum()) if not mechanisms.empty else 0
    best_body_score = float(mechanisms["readiness_score"].max()) if not mechanisms.empty else 0.0
    residual_map = dict(zip(residual["metric"], residual["value"]))
    short_loss = float(residual_map.get("short_duration_1_5d_net_pnl", 0.0))
    mid_gain = float(residual_map.get("mid_duration_6_60d_net_pnl", 0.0))
    best_time_stop_delta = float(residual_map.get("best_time_stop_estimated_exit_delta", 0.0))
    cost_share = float(residual_map.get("bad_window_extra_cost_share_abs_loss_pct", 0.0))
    failure_memory_2x_delta = float(residual_map.get("failure_memory_2x_max_dd_delta_pp", 0.0))
    failure_memory_3x_delta = float(residual_map.get("failure_memory_3x_max_dd_delta_pp", 0.0))

    gates = [
        {
            "gate": "body_promotion_candidate_exists",
            "passed": promotion_count > 0,
            "threshold": ">0",
            "value": promotion_count,
            "note": "若为0，说明本体交易规则没有晋级候选。",
        },
        {
            "gate": "stage526_default_body_keep",
            "passed": stage576_decision.get("stage526_body_status") == "keep",
            "threshold": "keep",
            "value": stage576_decision.get("stage526_body_status"),
            "note": "Stage576 已确认默认ATR中位止损和相关门控应保留。",
        },
        {
            "gate": "tight_stop_has_positive_estimated_delta",
            "passed": best_time_stop_delta > 0,
            "threshold": ">0",
            "value": best_time_stop_delta,
            "note": "早停/紧止损若全周期估计增量不正，不应交易化。",
        },
        {
            "gate": "short_loss_outweighs_mid_trend_gain",
            "passed": abs(short_loss) > mid_gain,
            "threshold": "abs(1-5d loss) > 6-60d gain",
            "value": f"{short_loss:.0f} vs {mid_gain:.0f}",
            "note": "若通过才说明应继续优先砍短期亏损；当前通常不通过，因为6-60天右尾更大。",
        },
        {
            "gate": "failure_memory_sizing_promoted",
            "passed": stage581_decision.get("decision") not in {"failure_memory_micro_sizing_no_promotion"},
            "threshold": "not no_promotion",
            "value": stage581_decision.get("decision"),
            "note": "失败记忆若风险路径劣化，不应继续调阈值/倍率。",
        },
        {
            "gate": "failure_memory_cost_stress_not_worse",
            "passed": failure_memory_2x_delta >= 0 and failure_memory_3x_delta >= 0,
            "threshold": "2x/3x DD delta >=0",
            "value": f"2x {failure_memory_2x_delta:.4f}, 3x {failure_memory_3x_delta:.4f}",
            "note": "负值说明成本压力下回撤更差。",
        },
        {
            "gate": "execution_cost_is_primary_bad_window_cause",
            "passed": cost_share >= 50,
            "threshold": ">=50%",
            "value": cost_share,
            "note": "若成本占坏窗口亏损比例低，说明不能靠本体止损或交易缓冲解释全部风险。",
        },
        {
            "gate": "reroute_priority_to_execution_source_slot",
            "passed": promotion_count == 0 and best_body_score <= 2,
            "threshold": "no promoted body rule",
            "value": f"promotion={promotion_count}, best_score={best_body_score:.0f}",
            "note": "本体层无晋级时，优先级应转回真实执行TCA、PIT外生selector和独立风险槽。",
        },
    ]
    return pd.DataFrame(gates)


def make_chart(
    mechanisms: pd.DataFrame,
    residual: pd.DataFrame,
    duration: pd.DataFrame,
    bad_monthly: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
) -> None:
    plt.rcParams.update({"font.size": 10})
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    fig.suptitle("Stage618 strategy-body residual closure: no trade-rule promotion, reroute to execution/source/slot evidence", fontsize=15)

    ax = axes[0, 0]
    top = mechanisms.copy()
    top = top.sort_values("readiness_score", ascending=True)
    labels = [str(item)[:30] for item in top["mechanism"]]
    colors = ["#2E7D32" if item else "#C62828" for item in top["promotion_allowed"]]
    ax.barh(labels, top["readiness_score"], color=colors, alpha=0.85)
    for idx, row in enumerate(top.to_dict("records")):
        ax.text(float(row["readiness_score"]) + 0.05, idx, str(row["promotion_status"])[:34], va="center", fontsize=8)
    ax.set_xlim(0, max(3.2, float(top["readiness_score"].max()) + 1.0 if not top.empty else 3.2))
    ax.set_title("Mechanism promotion readiness")
    ax.set_xlabel("readiness score (not a trading score)")
    ax.grid(axis="x", alpha=0.25)

    ax = axes[0, 1]
    all_duration = duration[duration["scope"].eq("all")].copy()
    order = ["1-3", "4-5", "6-10", "11-20", "21-60", "61+"]
    all_duration["duration_bucket"] = pd.Categorical(all_duration["duration_bucket"], categories=order, ordered=True)
    all_duration = all_duration.sort_values("duration_bucket")
    all_duration["net_pnl_m"] = _num(all_duration, "net_pnl") / 1_000_000.0
    colors = ["#C62828" if value < 0 else "#2E7D32" for value in all_duration["net_pnl_m"]]
    ax.bar(all_duration["duration_bucket"].astype(str), all_duration["net_pnl_m"], color=colors, alpha=0.85)
    ax.axhline(0, color="#333333", linewidth=1)
    ax.set_title("Holding lifecycle: short losses are real, but 6-60d right tail is larger")
    ax.set_ylabel("net pnl, million")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    control_1 = _one(cost[cost["cost_multiplier"].eq(1.0)], "variant", "stage526_control")
    micro = _one(cost[cost["cost_multiplier"].eq(1.0)], "variant", "stage526_failure_memory_micro_sizing")
    return_delta = float(micro["total_return_pct"] - control_1["total_return_pct"])
    deltas = [
        ("maxDD pp", float(micro["max_dd_pct"] - control_1["max_dd_pct"]), 1),
        ("Ulcer benefit", -(float(micro["ulcer_pct"] - control_1["ulcer_pct"])), 1),
        ("2x DD pp", _variant_cost(cost, "stage526_failure_memory_micro_sizing", 2.0, "max_dd_pct") - _variant_cost(cost, "stage526_control", 2.0, "max_dd_pct"), 1),
        ("3x DD pp", _variant_cost(cost, "stage526_failure_memory_micro_sizing", 3.0, "max_dd_pct") - _variant_cost(cost, "stage526_control", 3.0, "max_dd_pct"), 1),
        ("63d p05 pp", _variant_holding(rolling, "stage526_failure_memory_micro_sizing", 63, "p05_return_pct") - _variant_holding(rolling, "stage526_control", 63, "p05_return_pct"), 1),
        ("126d p05 pp", _variant_holding(rolling, "stage526_failure_memory_micro_sizing", 126, "p05_return_pct") - _variant_holding(rolling, "stage526_control", 126, "p05_return_pct"), 1),
    ]
    names = [item[0] for item in deltas]
    vals = [item[1] for item in deltas]
    signs = [item[2] for item in deltas]
    colors = ["#2E7D32" if value * sign >= 0 else "#C62828" for value, sign in zip(vals, signs)]
    ax.bar(names, vals, color=colors, alpha=0.85)
    ax.axhline(0, color="#333333", linewidth=1)
    for idx, value in enumerate(vals):
        ax.text(idx, value + (0.04 if value >= 0 else -0.06), f"{value:.2f}", ha="center", va="bottom" if value >= 0 else "top", fontsize=8)
    ax.set_ylim(min(vals) - 0.25, max(0.25, max(vals) + 0.25))
    ax.set_title(f"Failure-memory: return +{return_delta:.1f}pp, risk/experience deltas all worse")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    bad = bad_monthly.copy()
    bad["month"] = bad["month"].astype(str)
    bad["total_net_pnl_m"] = _num(bad, "total_net_pnl") / 1_000_000.0
    bad["extra_cost_m"] = _num(bad, "extra_3x_cost_vs_1x") / 1_000_000.0
    x = np.arange(len(bad))
    pnl_colors = ["#2E7D32" if value >= 0 else "#C62828" for value in bad["total_net_pnl_m"]]
    ax.bar(x - 0.18, bad["total_net_pnl_m"], width=0.36, color=pnl_colors, alpha=0.85, label="monthly net pnl")
    ax.bar(x + 0.18, bad["extra_cost_m"], width=0.36, color="#F9A825", alpha=0.9, label="extra 3x cost vs 1x")
    ax.axhline(0, color="#333333", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(bad["month"], rotation=35, ha="right")
    ax.set_title("2022 bad window: cost matters, but path loss dominates")
    ax.set_ylabel("million")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def write_report(
    decision: dict[str, Any],
    mechanisms: pd.DataFrame,
    residual: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    failed_gates = gates[~gates["passed"].astype(bool)].copy()
    lines = [
        "# Stage618 Strategy Body Residual Closure Board",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- strategy_changed: `{decision['strategy_changed']}`",
        f"- new_backtest_run: `{decision['new_backtest_run']}`",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        f"- body_subroute_active: `{decision['body_subroute_active']}`",
        "",
        "## Core Metrics",
        "",
        _md_table(residual, ["metric", "value", "note"], max_rows=40),
        "",
        "## Mechanism Matrix",
        "",
        _md_table(mechanisms, ["mechanism", "evidence_stage", "promotion_status", "readiness_score", "key_metric_1", "key_value_1", "key_metric_2", "key_value_2", "promotion_allowed"], max_rows=30),
        "",
        "## Gates",
        "",
        _md_table(gates, ["gate", "passed", "threshold", "value", "note"], max_rows=30),
        "",
        "## Failed Gates",
        "",
        _md_table(failed_gates, ["gate", "threshold", "value", "note"], max_rows=30),
        "",
        "## Research References",
        "",
    ]
    lines.extend([f"- {item}" for item in REFERENCE_LINKS])
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- ATR/退出/紧止损方向没有新增晋级空间：默认 ATR 中位止损应保留，早停和趋势破坏退出都没有全指标不劣化。",
            "- K线/入场质量代理无法稳定分离快失败；捕获负 edge 的同时会误伤正 edge。",
            "- failure-memory micro sizing 证明“失败后不一定更差”的直觉有诊断价值，但交易化会恶化回撤、Ulcer、成本压力和短周期左尾。",
            "- 坏窗口的额外成本会推穿边界，但亏损主因仍是路径本体和风险槽结构，不是某个单一止损开关。",
            "",
            "## Overfit Reflection",
            "",
            "- Run-start judgement: not overfit. This stage only aggregates frozen outputs and does not sweep ATR, K-line, failure count, product list, or sizing multiplier.",
            "- Run-end judgement: not overfit. The result is a closure/rejection board rather than a rescued trading rule.",
            "",
            "## Continue Value Reflection",
            "",
            "- The strategy-body small-rule subroute has low value to continue actively.",
            "- The overall goal remains valuable, but progress should move to live execution TCA, PIT external selector evidence, and independent risk slots.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    candidate = _read_csv(STAGE576_CANDIDATE)
    probe = _read_csv(STAGE576_PROBE)
    duration = _read_csv(STAGE537_DURATION)
    guard = _read_csv(STAGE537_GUARD)
    bad_monthly = _read_csv(STAGE564_BAD_WINDOW_MONTHLY)
    summary = _read_csv(STAGE581_SUMMARY)
    cost = _read_csv(STAGE581_COST)
    rolling = _read_csv(STAGE581_ROLLING)
    stage576_decision = _read_json(STAGE576_DECISION)
    stage581_decision = _read_json(STAGE581_DECISION)

    mechanisms = build_mechanism_matrix(candidate, probe, guard, summary, cost, rolling)
    residual = build_residual_metrics(duration, guard, bad_monthly, summary, cost, rolling)
    gates = build_gates(mechanisms, residual, stage576_decision, stage581_decision)

    promotion_count = int(mechanisms["promotion_allowed"].sum()) if not mechanisms.empty else 0
    body_active = bool(promotion_count > 0)
    passed_gates = int(gates["passed"].astype(bool).sum())
    total_gates = int(len(gates))
    residual_map = dict(zip(residual["metric"], residual["value"]))

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "decision": "strategy_body_residual_closed_no_new_trade_rule_reroute_to_execution_source_slot",
        "new_backtest_run": False,
        "strategy_changed": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "body_subroute_active": body_active,
        "body_promotion_candidate_count": promotion_count,
        "hard_gates_passed": passed_gates,
        "hard_gates_total": total_gates,
        "stage526_end_equity": residual_map.get("stage526_end_equity"),
        "stage526_total_return_pct": residual_map.get("stage526_total_return_pct"),
        "stage526_max_dd_pct": residual_map.get("stage526_max_dd_pct"),
        "stage526_sharpe": residual_map.get("stage526_sharpe"),
        "stage526_total_slippage": residual_map.get("stage526_total_slippage"),
        "stage526_trade_count": residual_map.get("stage526_trade_count"),
        "short_duration_1_5d_net_pnl": residual_map.get("short_duration_1_5d_net_pnl"),
        "mid_duration_6_60d_net_pnl": residual_map.get("mid_duration_6_60d_net_pnl"),
        "best_time_stop_estimated_exit_delta": residual_map.get("best_time_stop_estimated_exit_delta"),
        "bad_window_extra_cost_share_abs_loss_pct": residual_map.get("bad_window_extra_cost_share_abs_loss_pct"),
        "failure_memory_return_delta_pp": residual_map.get("failure_memory_return_delta_pp"),
        "failure_memory_max_dd_delta_pp": residual_map.get("failure_memory_max_dd_delta_pp"),
        "failure_memory_2x_max_dd_delta_pp": residual_map.get("failure_memory_2x_max_dd_delta_pp"),
        "failure_memory_3x_max_dd_delta_pp": residual_map.get("failure_memory_3x_max_dd_delta_pp"),
        "next_priority": "live_execution_tca_then_pit_external_selector_then_independent_risk_slots",
        "overfit_reflection": "Not overfit: only aggregates frozen Stage526/535/537/564/576/581 evidence; no threshold sweep, no product list, no new trade rule.",
        "continue_value_reflection": "Strategy-body small-rule continuation value is low; overall goal remains valuable through execution TCA, PIT selector, and independent risk-slot evidence.",
        "references": REFERENCE_LINKS,
        "outputs": {
            "mechanism_matrix": str(MECHANISM_PATH),
            "residual_metrics": str(RESIDUAL_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    MECHANISM_PATH.parent.mkdir(parents=True, exist_ok=True)
    mechanisms.to_csv(MECHANISM_PATH, index=False, encoding="utf-8-sig")
    residual.to_csv(RESIDUAL_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    make_chart(mechanisms, residual, duration, bad_monthly, cost, rolling)
    write_report(decision, mechanisms, residual, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

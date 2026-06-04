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


MODEL_TAG = "stage576_stage526_strategy_body_optimization_boundary_v1"
OUTPUT_PREFIX = "qmt_roll_stage576_stage526_strategy_body_optimization_boundary"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE531_SUMMARY = OUTPUT_DIR / "qmt_roll_stage531_stage526_exit_shape_frontier_summary_stage531_stage526_exit_shape_frontier_v1.csv"
STAGE531_COST = OUTPUT_DIR / "qmt_roll_stage531_stage526_exit_shape_frontier_cost_stress_stage531_stage526_exit_shape_frontier_v1.csv"
STAGE531_HOLDING = OUTPUT_DIR / "qmt_roll_stage531_stage526_exit_shape_frontier_rolling_holding_stage531_stage526_exit_shape_frontier_v1.csv"
STAGE532_SUMMARY = OUTPUT_DIR / "qmt_roll_stage532_stage526_corr_gate_frontier_summary_stage532_stage526_corr_gate_frontier_v1.csv"
STAGE532_COST = OUTPUT_DIR / "qmt_roll_stage532_stage526_corr_gate_frontier_cost_stress_stage532_stage526_corr_gate_frontier_v1.csv"
STAGE532_HOLDING = OUTPUT_DIR / "qmt_roll_stage532_stage526_corr_gate_frontier_rolling_holding_stage532_stage526_corr_gate_frontier_v1.csv"
STAGE533_AGG = OUTPUT_DIR / "qmt_roll_stage533_stage526_corr_gate_event_attribution_aggregate_stage533_stage526_corr_gate_event_attribution_v1.csv"
STAGE535_PROBE = OUTPUT_DIR / "qmt_roll_stage535_stage526_fast_fail_entry_proxy_rule_probe_stage535_stage526_fast_fail_entry_proxy_v1.csv"
STAGE536_PROBE = OUTPUT_DIR / "qmt_roll_stage536_stage526_cost_churn_fragility_rule_probe_stage536_stage526_cost_churn_fragility_v1.csv"
STAGE537_DURATION = OUTPUT_DIR / "qmt_roll_stage537_stage526_segment_lifecycle_audit_duration_summary_stage537_stage526_segment_lifecycle_audit_v1.csv"
STAGE537_GUARD = OUTPUT_DIR / "qmt_roll_stage537_stage526_segment_lifecycle_audit_guard_probe_stage537_stage526_segment_lifecycle_audit_v1.csv"
STAGE562_PROBE = OUTPUT_DIR / "qmt_roll_stage562_stage526_failure_memory_audit_rule_probe_stage562_stage526_failure_memory_audit_v1.csv"
STAGE562_BUCKET = OUTPUT_DIR / "qmt_roll_stage562_stage526_failure_memory_audit_bucket_summary_stage562_stage526_failure_memory_audit_v1.csv"

MECHANISM_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mechanism_summary_{MODEL_TAG}.csv"
CANDIDATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_boundary_{MODEL_TAG}.csv"
PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_boundary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

CONTROL_VARIANT = "r080_pc25_maxpos4_control"

REFERENCE_LINKS = [
    "AQR/academic long-horizon trend evidence: https://arxiv.org/abs/1404.3274",
    "Commodity futures trend/risk-parity evidence: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813",
    "Correlated trend-following allocation: https://arxiv.org/abs/1410.8409",
    "Stop-loss cost/autocorrelation caveat: https://www.sciencedirect.com/science/article/abs/pii/S1386418117300472",
    "GitHub futures trend-following reference: https://github.com/jironghuang/trend_following",
]


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


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
    if isinstance(value, (np.bool_, bool)):
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


def _row(frame: pd.DataFrame, variant: str) -> pd.Series:
    rows = frame[frame["variant"].eq(variant)]
    if rows.empty:
        raise KeyError(variant)
    return rows.iloc[0]


def _metric_delta(candidate: pd.Series, control: pd.Series) -> dict[str, float]:
    return {
        "end_equity_delta": float(candidate["end_equity"] - control["end_equity"]),
        "total_return_delta_pp": float(candidate["total_return_pct"] - control["total_return_pct"]),
        "max_dd_delta_pp": float(candidate["max_dd_pct"] - control["max_dd_pct"]),
        "ulcer_delta": float(candidate["ulcer_pct"] - control["ulcer_pct"]),
        "sharpe_delta": float(candidate["sharpe"] - control["sharpe"]),
        "broker10_max_delta_pp": float(candidate["max_broker10_margin_to_equity_pct"] - control["max_broker10_margin_to_equity_pct"]),
        "total_slippage_delta": float(candidate["total_slippage"] - control["total_slippage"]),
        "trade_count_delta": float(candidate["total_trade_count"] - control["total_trade_count"]),
    }


def _holding_metric(holding: pd.DataFrame, variant: str, holding_days: int, column: str) -> float:
    rows = holding[(holding["variant"].eq(variant)) & (holding["holding_days"].eq(holding_days))]
    if rows.empty:
        return np.nan
    return float(rows.iloc[0][column])


def _cost_metric(cost: pd.DataFrame, variant: str, cost_multiplier: float, column: str) -> float:
    rows = cost[(cost["variant"].eq(variant)) & (cost["cost_multiplier"].eq(cost_multiplier))]
    if rows.empty:
        return np.nan
    return float(rows.iloc[0][column])


def _build_variant_boundary() -> pd.DataFrame:
    exit_summary = _read_csv(STAGE531_SUMMARY)
    exit_cost = _read_csv(STAGE531_COST)
    exit_holding = _read_csv(STAGE531_HOLDING)
    corr_summary = _read_csv(STAGE532_SUMMARY)
    corr_cost = _read_csv(STAGE532_COST)
    corr_holding = _read_csv(STAGE532_HOLDING)
    corr_attr = _read_csv(STAGE533_AGG)

    for frame in [exit_summary, exit_cost, exit_holding, corr_summary, corr_cost, corr_holding, corr_attr]:
        for column in frame.columns:
            if column not in {"variant", "label", "note", "group_type", "group_value", "worst_return_start", "worst_return_end"}:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

    control = _row(exit_summary, CONTROL_VARIANT)
    corr_control = _row(corr_summary, CONTROL_VARIANT)
    control_h63 = _holding_metric(exit_holding, CONTROL_VARIANT, 63, "p05_return_pct")
    control_h126 = _holding_metric(exit_holding, CONTROL_VARIANT, 126, "p05_return_pct")

    direct_corr = corr_attr[
        corr_attr["group_type"].eq("layer") & corr_attr["group_value"].eq("direct_corr_scaled_delta")
    ]
    direct_corr_edge = float(direct_corr["edge_net_pnl_sum"].iloc[0]) if not direct_corr.empty else np.nan
    downstream = corr_attr[
        corr_attr["group_type"].eq("layer") & corr_attr["group_value"].eq("downstream_equity_sizing_delta")
    ]
    downstream_edge = float(downstream["edge_net_pnl_sum"].iloc[0]) if not downstream.empty else np.nan

    variant_specs = [
        {
            "mechanism": "ATR mid stop",
            "variant": "r080_pc25_maxpos4_no_atr_mid",
            "source_stage": "Stage531",
            "kind": "ablation",
            "candidate_label": "disable ATR mid stop",
            "promotion_status": "reject_keep_default",
            "readiness_score": 0,
            "reason": "关闭ATR中位止损后1x最大回撤恶化到-39.5864%，2x/3x成本也失败，说明默认ATR止损有真实保护作用。",
            "summary": exit_summary,
            "cost": exit_cost,
            "holding": exit_holding,
            "control": control,
            "h63_control": control_h63,
            "h126_control": control_h126,
            "direct_corr_edge": np.nan,
            "downstream_edge": np.nan,
        },
        {
            "mechanism": "alignment break exit",
            "variant": "r080_pc25_maxpos4_align_break",
            "source_stage": "Stage531",
            "kind": "exit_shape",
            "candidate_label": "trend alignment break exit",
            "promotion_status": "reject_observe_only",
            "readiness_score": 1,
            "reason": "收益上升但broker10超过100%、3x最大回撤-44.0674%，且63/126日左尾变差，属于更激进路径而非稳健晋级。",
            "summary": exit_summary,
            "cost": exit_cost,
            "holding": exit_holding,
            "control": control,
            "h63_control": control_h63,
            "h126_control": control_h126,
            "direct_corr_edge": np.nan,
            "downstream_edge": np.nan,
        },
        {
            "mechanism": "profit giveback stop",
            "variant": "r080_pc25_maxpos4_profit_giveback",
            "source_stage": "Stage531",
            "kind": "exit_shape",
            "candidate_label": "profit giveback stop",
            "promotion_status": "reject_return_too_low",
            "readiness_score": 0,
            "reason": "回撤/Ulcer略好但总收益下降约801pp，收益保留不够且broker10超过100%，不符合现有指标不能劣化。",
            "summary": exit_summary,
            "cost": exit_cost,
            "holding": exit_holding,
            "control": control,
            "h63_control": control_h63,
            "h126_control": control_h126,
            "direct_corr_edge": np.nan,
            "downstream_edge": np.nan,
        },
        {
            "mechanism": "corr gate floor50",
            "variant": "r080_pc25_maxpos4_corr20_f50",
            "source_stage": "Stage532/533",
            "kind": "corr_gate",
            "candidate_label": "same-direction corr floor35 -> floor50",
            "promotion_status": "paper_observation_not_replacement",
            "readiness_score": 2,
            "reason": "1x路径收益、回撤、Ulcer均略好，但3x仍破40%，63日p05略差；Stage533显示直接相关门控事件edge为负，优势主要来自后续权益 sizing 差异，暂不能当规则晋级。",
            "summary": corr_summary,
            "cost": corr_cost,
            "holding": corr_holding,
            "control": corr_control,
            "h63_control": _holding_metric(corr_holding, CONTROL_VARIANT, 63, "p05_return_pct"),
            "h126_control": _holding_metric(corr_holding, CONTROL_VARIANT, 126, "p05_return_pct"),
            "direct_corr_edge": direct_corr_edge,
            "downstream_edge": downstream_edge,
        },
        {
            "mechanism": "remove corr gate",
            "variant": "r080_pc25_maxpos4_no_corr_gate",
            "source_stage": "Stage532",
            "kind": "corr_gate_ablation",
            "candidate_label": "disable same-direction corr gate",
            "promotion_status": "reject_keep_default",
            "readiness_score": 0,
            "reason": "关闭同向相关门控后1x最大回撤恶化到-45.3266%、Ulcer 17.1767、broker10超过100%，说明高相关风险必须保留硬约束。",
            "summary": corr_summary,
            "cost": corr_cost,
            "holding": corr_holding,
            "control": corr_control,
            "h63_control": _holding_metric(corr_holding, CONTROL_VARIANT, 63, "p05_return_pct"),
            "h126_control": _holding_metric(corr_holding, CONTROL_VARIANT, 126, "p05_return_pct"),
            "direct_corr_edge": np.nan,
            "downstream_edge": np.nan,
        },
    ]

    rows: list[dict[str, Any]] = []
    for spec in variant_specs:
        summary = spec["summary"]
        candidate = _row(summary, spec["variant"])
        deltas = _metric_delta(candidate, spec["control"])
        h63 = _holding_metric(spec["holding"], spec["variant"], 63, "p05_return_pct")
        h126 = _holding_metric(spec["holding"], spec["variant"], 126, "p05_return_pct")
        row = {
            "mechanism": spec["mechanism"],
            "variant": spec["variant"],
            "source_stage": spec["source_stage"],
            "kind": spec["kind"],
            "candidate_label": spec["candidate_label"],
            "promotion_status": spec["promotion_status"],
            "readiness_score": spec["readiness_score"],
            "end_equity": float(candidate["end_equity"]),
            "total_return_pct": float(candidate["total_return_pct"]),
            "max_dd_pct": float(candidate["max_dd_pct"]),
            "ulcer_pct": float(candidate["ulcer_pct"]),
            "sharpe": float(candidate["sharpe"]),
            "max_broker10_margin_to_equity_pct": float(candidate["max_broker10_margin_to_equity_pct"]),
            "days_over_100pct": int(candidate["days_over_100pct"]),
            "total_slippage": float(candidate["total_slippage"]),
            "total_trade_count": float(candidate["total_trade_count"]),
            "dd40_pass_1x": int(candidate["dd40_pass"]),
            "broker10_100_pass_1x": int(candidate["broker10_100_pass"]),
            "max_dd_pct_2x": _cost_metric(spec["cost"], spec["variant"], 2.0, "max_dd_pct"),
            "max_dd_pct_3x": _cost_metric(spec["cost"], spec["variant"], 3.0, "max_dd_pct"),
            "dd40_pass_3x": int(_cost_metric(spec["cost"], spec["variant"], 3.0, "dd40_pass")),
            "h63_p05_return_pct": h63,
            "h126_p05_return_pct": h126,
            "h63_p05_delta_pp": float(h63 - spec["h63_control"]) if pd.notna(h63) else np.nan,
            "h126_p05_delta_pp": float(h126 - spec["h126_control"]) if pd.notna(h126) else np.nan,
            "direct_corr_scaled_edge_pnl": spec["direct_corr_edge"],
            "downstream_equity_sizing_edge_pnl": spec["downstream_edge"],
            "reason": spec["reason"],
        }
        row.update(deltas)
        row["all_no_degrade_pass"] = int(
            row["total_return_delta_pp"] >= 0
            and row["max_dd_delta_pp"] >= 0
            and row["ulcer_delta"] <= 0
            and row["h63_p05_delta_pp"] >= 0
            and row["h126_p05_delta_pp"] >= 0
            and row["broker10_100_pass_1x"] == 1
            and row["dd40_pass_3x"] == 1
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _build_mechanism_summary(candidate_boundary: pd.DataFrame) -> pd.DataFrame:
    duration = _read_csv(STAGE537_DURATION)
    guard = _read_csv(STAGE537_GUARD)
    cost_probe = _read_csv(STAGE536_PROBE)
    failure_bucket = _read_csv(STAGE562_BUCKET)
    failure_probe = _read_csv(STAGE562_PROBE)
    fast_probe = _read_csv(STAGE535_PROBE)

    for frame in [duration, guard, cost_probe, failure_bucket, failure_probe, fast_probe]:
        for column in frame.columns:
            if column not in {"scope", "duration_bucket", "probe", "mode", "bucket_type", "bucket"}:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

    all_duration = duration[duration["scope"].eq("all")].copy()
    short_loss_net = float(all_duration[all_duration["duration_bucket"].isin(["1-3", "4-5"])]["net_pnl"].sum())
    long_trend_net = float(all_duration[all_duration["duration_bucket"].isin(["6-10", "11-20", "21-60"])]["net_pnl"].sum())
    short_loss_slippage = float(all_duration[all_duration["duration_bucket"].isin(["1-3", "4-5"])]["slippage"].sum())
    segment_short = cost_probe[cost_probe["probe"].eq("segment_short_loss_le10d")]
    segment_short_net = float(segment_short["net_pnl"].iloc[0]) if not segment_short.empty else np.nan
    guard_all = guard[guard["scope"].eq("all")].copy()
    guard_best_delta = (
        float(pd.to_numeric(guard_all.get("estimated_exit_delta", pd.Series(dtype=float)), errors="coerce").max())
        if not guard_all.empty
        else np.nan
    )

    fast_best = fast_probe.sort_values(["coverage_of_total_negative_edge_pct", "positive_edge_at_risk_pct"], ascending=[False, True]).head(1)
    fast_best_capture = float(fast_best["coverage_of_total_negative_edge_pct"].iloc[0]) if not fast_best.empty else np.nan
    fast_best_positive_risk = float(fast_best["positive_edge_at_risk_pct"].iloc[0]) if not fast_best.empty else np.nan
    fast_best_edge = float(fast_best["edge_sum"].iloc[0]) if not fast_best.empty else np.nan

    failure_loss_ge2 = failure_bucket[
        failure_bucket["bucket_type"].eq("consecutive_loss_bucket") & failure_bucket["bucket"].astype(str).isin(["2", "3+"])
    ]
    if not failure_loss_ge2.empty:
        loss_ge2_net = float(failure_loss_ge2["net_pnl"].sum())
        loss_ge2_count = float(failure_loss_ge2["segment_count"].sum())
        loss_ge2_win = (
            float((failure_loss_ge2["win_rate_pct"] * failure_loss_ge2["segment_count"]).sum() / loss_ge2_count)
            if loss_ge2_count > 0
            else np.nan
        )
    else:
        loss_ge2_net = np.nan
        loss_ge2_win = np.nan
    failure_best = failure_probe[failure_probe["probe"].eq("only_after_consecutive_loss_ge1")]
    failure_best_delta = float(failure_best["estimated_delta_vs_control"].iloc[0]) if not failure_best.empty else np.nan
    failure_best_positive_risk = float(failure_best["positive_pnl_at_risk_pct"].iloc[0]) if not failure_best.empty else np.nan

    promoted_count = int(candidate_boundary["all_no_degrade_pass"].sum())
    corr_observation = candidate_boundary[candidate_boundary["variant"].eq("r080_pc25_maxpos4_corr20_f50")].iloc[0]

    rows = [
        {
            "mechanism": "default Stage526 body",
            "status": "keep_as_base",
            "evidence": "Stage526/531/532复刻为当前策略本体基准；现有ATR、同向相关、pc25、maxpos4共同构成可执行边界。",
            "readiness_score": 3,
            "numeric_evidence_1": float(_row(_read_csv(STAGE531_SUMMARY), CONTROL_VARIANT)["total_return_pct"]),
            "numeric_evidence_2": float(_row(_read_csv(STAGE531_SUMMARY), CONTROL_VARIANT)["max_dd_pct"]),
            "next_action": "保留为主研究候选，不在本体层做替换。",
        },
        {
            "mechanism": "exit shape replacements",
            "status": "no_promotion",
            "evidence": f"Stage531三个退出形状中全指标不劣化通过数={promoted_count}；alignment/profit_giveback/no_atr_mid均有收益、左尾、保证金或成本压力缺陷。",
            "readiness_score": 0,
            "numeric_evidence_1": promoted_count,
            "numeric_evidence_2": float(candidate_boundary[candidate_boundary["source_stage"].str.contains("Stage531")]["all_no_degrade_pass"].sum()),
            "next_action": "停止继续扫退出小条件；只保留默认ATR中位止损。",
        },
        {
            "mechanism": "same-direction corr gate",
            "status": "keep_default_floor35_observe_floor50",
            "evidence": "关闭相关门控直接把1x最大回撤推到-45.3266%；floor50虽全周期更好，但3x成本仍破40且直接corr事件edge为负。",
            "readiness_score": 2,
            "numeric_evidence_1": float(corr_observation["total_return_delta_pp"]),
            "numeric_evidence_2": float(corr_observation["max_dd_delta_pp"]),
            "next_action": "floor50只做paper观察，不继续扫0.60/0.70/0.80。",
        },
        {
            "mechanism": "fast-fail entry proxy",
            "status": "reject",
            "evidence": f"Stage535最宽fast-fail代理捕获负edge约{fast_best_capture:.4f}%，但正edge风险约{fast_best_positive_risk:.4f}%，edge_sum={fast_best_edge:.0f}。",
            "readiness_score": 0,
            "numeric_evidence_1": fast_best_capture,
            "numeric_evidence_2": fast_best_positive_risk,
            "next_action": "不把快失败代理写成开仓过滤；等待外生selector或真实前置信号。",
        },
        {
            "mechanism": "early adverse exit",
            "status": "reject",
            "evidence": f"1-5天段净亏{short_loss_net:.0f}、6-60天段净赚{long_trend_net:.0f}；Stage537所有早停守卫全周期delta不正，最好delta约{guard_best_delta:.0f}。",
            "readiness_score": 0,
            "numeric_evidence_1": short_loss_net,
            "numeric_evidence_2": long_trend_net,
            "next_action": "不晋级时间止损/早停；避免砍掉6-60天右尾。",
        },
        {
            "mechanism": "cost churn fragility",
            "status": "execution_monitor_not_trade_rule",
            "evidence": f"Stage536短命亏损段<=10日净亏{segment_short_net:.0f}，但窗口额外成本不是主因；短段1-5天滑点{short_loss_slippage:.0f}。",
            "readiness_score": 1,
            "numeric_evidence_1": segment_short_net,
            "numeric_evidence_2": short_loss_slippage,
            "next_action": "继续用真实执行TCA监控成本倍率，不写no-trade buffer。",
        },
        {
            "mechanism": "failure memory",
            "status": "diagnostic_only",
            "evidence": f"连续失败后胜率/净额有正诊断，但only_after_consecutive_loss_ge1的正PnL风险仍{failure_best_positive_risk:.4f}%，delta={failure_best_delta:.0f}。",
            "readiness_score": 1,
            "numeric_evidence_1": failure_best_delta,
            "numeric_evidence_2": failure_best_positive_risk,
            "next_action": "不做失败次数门禁；若未来继续，只允许一次冻结低幅度micro-sizing paper，不扫阈值。",
        },
    ]
    if pd.notna(loss_ge2_net):
        rows.append(
            {
                "mechanism": "failure memory loss_ge2 bucket",
                "status": "supporting_diagnostic",
                "evidence": "连续失败>=2后的段表现支持'震荡后趋势更可能爆发'这个直觉，但不能直接选出未来可交易段。",
                "readiness_score": 1,
                "numeric_evidence_1": loss_ge2_net,
                "numeric_evidence_2": loss_ge2_win,
                "next_action": "只作为人类复盘和paper候选来源。",
            }
        )
    return pd.DataFrame(rows)


def _build_probe_boundary() -> pd.DataFrame:
    fast = _read_csv(STAGE535_PROBE)
    failure = _read_csv(STAGE562_PROBE)
    guard = _read_csv(STAGE537_GUARD)

    fast_rows = fast.assign(
        probe_family="fast_fail_entry_proxy",
        x_metric=_num(fast, "coverage_of_total_negative_edge_pct"),
        y_metric=_num(fast, "positive_edge_at_risk_pct"),
        size_metric=_num(fast, "event_count"),
        value_metric=_num(fast, "edge_sum"),
        status="reject_positive_edge_risk_or_low_capture",
    )[
        [
            "probe_family",
            "probe",
            "x_metric",
            "y_metric",
            "size_metric",
            "value_metric",
            "status",
        ]
    ]
    failure_rows = failure.assign(
        probe_family="failure_memory",
        x_metric=_num(failure, "win_rate_improvement_pp"),
        y_metric=_num(failure, "positive_pnl_at_risk_pct"),
        size_metric=_num(failure, "trigger_count"),
        value_metric=_num(failure, "estimated_delta_vs_control"),
        status=np.where(
            (_num(failure, "estimated_delta_vs_control") > 0) & (_num(failure, "positive_pnl_at_risk_pct") <= 10),
            "diagnostic_not_trade_gate",
            "reject_or_diagnostic_only",
        ),
    )[
        [
            "probe_family",
            "probe",
            "x_metric",
            "y_metric",
            "size_metric",
            "value_metric",
            "status",
        ]
    ]
    value_col = "estimated_exit_delta" if "estimated_exit_delta" in guard.columns else "estimated_delta_vs_control"
    if value_col not in guard.columns:
        guard[value_col] = np.nan
    guard_rows = guard.assign(
        probe_family="early_adverse_exit",
        x_metric=_num(guard, value_col),
        y_metric=_num(guard, "trigger_count"),
        size_metric=_num(guard, "trigger_count"),
        value_metric=_num(guard, value_col),
        status="reject_full_period_delta_not_positive",
    )[
        [
            "probe_family",
            "probe",
            "x_metric",
            "y_metric",
            "size_metric",
            "value_metric",
            "status",
        ]
    ]
    return pd.concat([fast_rows, failure_rows, guard_rows], ignore_index=True)


def _build_gates(candidate_boundary: pd.DataFrame, mechanism_summary: pd.DataFrame) -> pd.DataFrame:
    floor50 = candidate_boundary[candidate_boundary["variant"].eq("r080_pc25_maxpos4_corr20_f50")].iloc[0]
    no_corr = candidate_boundary[candidate_boundary["variant"].eq("r080_pc25_maxpos4_no_corr_gate")].iloc[0]
    exit_promotions = int(candidate_boundary[candidate_boundary["source_stage"].str.contains("Stage531")]["all_no_degrade_pass"].sum())
    diagnostic_failure = mechanism_summary[mechanism_summary["mechanism"].eq("failure memory")].iloc[0]
    gates = [
        {
            "gate": "default_stage526_body_kept",
            "passed": 1,
            "threshold": "当前基准不被新本体规则替换",
            "value": "keep",
            "note": "本阶段没有发现更稳健的本体替换规则。",
        },
        {
            "gate": "exit_shape_promotion_exists",
            "passed": int(exit_promotions > 0),
            "threshold": "至少1个退出形状全指标不劣化",
            "value": exit_promotions,
            "note": "Stage531无退出形状满足不劣化。",
        },
        {
            "gate": "corr_gate_default_required",
            "passed": int(float(no_corr["max_dd_pct"]) < -40.0),
            "threshold": "关闭相关门控后风险明显恶化",
            "value": float(no_corr["max_dd_pct"]),
            "note": "关闭同向相关门控后DD穿-40，默认floor35应保留。",
        },
        {
            "gate": "corr_floor50_replacement_ready",
            "passed": int(
                float(floor50["all_no_degrade_pass"]) == 1
                and float(floor50["direct_corr_scaled_edge_pnl"]) > 0
            ),
            "threshold": "全指标不劣化且直接相关事件edge为正",
            "value": float(floor50["direct_corr_scaled_edge_pnl"]),
            "note": "floor50可观察但不是替换候选。",
        },
        {
            "gate": "fast_fail_entry_proxy_ready",
            "passed": 0,
            "threshold": "高捕获、低正edge风险、入场前可识别",
            "value": "not_ready",
            "note": "Stage535无法在入场前稳定分离快失败。",
        },
        {
            "gate": "early_adverse_exit_ready",
            "passed": 0,
            "threshold": "全周期delta为正且不砍右尾",
            "value": "not_ready",
            "note": "Stage537早停反证，6-60日右尾不可误伤。",
        },
        {
            "gate": "failure_memory_trade_gate_ready",
            "passed": 0,
            "threshold": "低正PnL风险且真实引擎固定重放通过",
            "value": float(diagnostic_failure["numeric_evidence_2"]),
            "note": "失败记忆有诊断价值，但正PnL风险太高，不能写成门禁。",
        },
        {
            "gate": "single_fixed_micro_sizing_probe_allowed",
            "passed": 1,
            "threshold": "只允许一个冻结paper探针，不扫阈值",
            "value": "allowed_paper_only",
            "note": "若继续本体方向，唯一合理小步是失败记忆低幅micro-sizing paper，不是正式晋级。",
        },
    ]
    return pd.DataFrame(gates)


def _plot(candidate_boundary: pd.DataFrame, mechanism_summary: pd.DataFrame, probe_boundary: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle("Stage576 Strategy Body Optimization Boundary", fontsize=17, fontweight="bold")

    labels = candidate_boundary["mechanism"].tolist()
    x = np.arange(len(labels))
    ax = axes[0, 0]
    colors = ["#1b9e77" if v >= 0 else "#d95f02" for v in candidate_boundary["total_return_delta_pp"]]
    ax.bar(x, candidate_boundary["total_return_delta_pp"], width=0.48, color=colors, label="return delta pp")
    ax.axhline(0, color="#444444", linewidth=0.8)
    ax.set_title("Total Return vs Max DD Delta to Stage526")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("return delta pp")
    ax.grid(axis="y", alpha=0.25)
    ax2 = ax.twinx()
    dd_colors = ["#1b9e77" if v >= 0 else "#d95f02" for v in candidate_boundary["max_dd_delta_pp"]]
    ax2.plot(x, candidate_boundary["max_dd_delta_pp"], color="#2166ac", marker="o", linewidth=2.0, label="max DD delta pp")
    for xi, yi, color in zip(x, candidate_boundary["max_dd_delta_pp"], dd_colors):
        ax2.scatter([xi], [yi], s=68, color=color, edgecolor="#222222", zorder=5)
        ax2.annotate(f"{yi:+.2f}", (xi, yi), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8)
    ax2.axhline(0, color="#444444", linewidth=0.8, linestyle=":")
    ax2.set_ylabel("max DD delta pp")
    left_handles, left_labels = ax.get_legend_handles_labels()
    right_handles, right_labels = ax2.get_legend_handles_labels()
    ax.legend(left_handles + right_handles, left_labels + right_labels, loc="best")

    ax = axes[0, 1]
    ax.scatter(
        candidate_boundary["h63_p05_delta_pp"],
        candidate_boundary["h126_p05_delta_pp"],
        s=np.clip(candidate_boundary["readiness_score"].astype(float) + 1, 1, 4) * 80,
        c=["#1b9e77" if status.startswith("paper") else "#d95f02" for status in candidate_boundary["promotion_status"]],
        alpha=0.85,
        edgecolor="#222222",
        linewidth=0.7,
    )
    for _, row in candidate_boundary.iterrows():
        ax.annotate(row["mechanism"], (row["h63_p05_delta_pp"], row["h126_p05_delta_pp"]), xytext=(5, 4), textcoords="offset points", fontsize=9)
    ax.axhline(0, color="#444444", linewidth=0.8)
    ax.axvline(0, color="#444444", linewidth=0.8)
    ax.set_title("3M/6M Left-tail Experience Delta")
    ax.set_xlabel("63d p05 return delta pp")
    ax.set_ylabel("126d p05 return delta pp")
    ax.grid(alpha=0.25)

    ax = axes[1, 0]
    fast = probe_boundary[probe_boundary["probe_family"].eq("fast_fail_entry_proxy")]
    failure = probe_boundary[probe_boundary["probe_family"].eq("failure_memory")]
    if not fast.empty:
        ax.scatter(
            fast["x_metric"],
            fast["y_metric"],
            s=np.clip(fast["size_metric"], 5, 80) * 3,
            c="#d95f02",
            alpha=0.72,
            label="fast-fail proxy",
            edgecolor="#222222",
            linewidth=0.5,
        )
    if not failure.empty:
        ax.scatter(
            failure["x_metric"],
            failure["y_metric"],
            s=np.clip(failure["size_metric"], 5, 120) * 1.6,
            c="#7570b3",
            alpha=0.72,
            label="failure memory",
            edgecolor="#222222",
            linewidth=0.5,
        )
    ax.axhline(10, color="#777777", linestyle="--", linewidth=0.9)
    ax.axvline(0, color="#777777", linestyle="--", linewidth=0.9)
    ax.set_title("Proxy Capture vs Positive PnL at Risk")
    ax.set_xlabel("x: negative-edge capture or win-rate improvement")
    ax.set_ylabel("positive PnL at risk pct")
    ax.legend(loc="best")
    ax.grid(alpha=0.25)

    ax = axes[1, 1]
    status_order = mechanism_summary[~mechanism_summary["mechanism"].eq("failure memory loss_ge2 bucket")].copy()
    status_colors = {
        "keep_as_base": "#1b9e77",
        "keep_default_floor35_observe_floor50": "#66a61e",
        "diagnostic_only": "#e6ab02",
        "execution_monitor_not_trade_rule": "#e6ab02",
        "no_promotion": "#d95f02",
        "reject": "#d95f02",
    }
    colors = [status_colors.get(status, "#999999") for status in status_order["status"]]
    ax.barh(status_order["mechanism"], status_order["readiness_score"], color=colors)
    ax.set_xlim(0, 3.2)
    ax.set_xlabel("readiness score")
    ax.set_title("Mechanism Readiness")
    ax.grid(axis="x", alpha=0.25)
    for i, (_, row) in enumerate(status_order.iterrows()):
        ax.text(float(row["readiness_score"]) + 0.05, i, row["status"], va="center", fontsize=9)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _build_report(
    candidate_boundary: pd.DataFrame,
    mechanism_summary: pd.DataFrame,
    probe_boundary: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    return f"""# Stage576 Stage526策略本体优化边界审计

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- 生成时间: `{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`
- 阶段性质: 只读归因汇总；不改策略、不扫阈值、不生成新交易版本。

## 外部调研与判断

- 参考资料:
{chr(10).join(f"  - {item}" for item in REFERENCE_LINKS)}
- 判断: 趋势策略长期优势更依赖多品种/多资产趋势暴露、风险预算与相关性治理；紧止损和早停只有在足够自相关且交易成本可覆盖时才可能改善。对本仓库而言，现有证据已经显示短期亏损段很多，但6-60天右尾更关键，所以本体优化必须先保护右尾。

## 决策

- decision: `{decision["decision"]}`
- promotion: `{decision["promotion"]}`
- gates_passed: `{decision["gates_passed"]}/{decision["gates_total"]}`
- 主判断: `{decision["primary_judgement"]}`
- 下一步: `{decision["next_step"]}`

## 候选边界

{_md_table(candidate_boundary, [
    "mechanism",
    "promotion_status",
    "total_return_delta_pp",
    "max_dd_delta_pp",
    "ulcer_delta",
    "h63_p05_delta_pp",
    "h126_p05_delta_pp",
    "max_dd_pct_3x",
    "all_no_degrade_pass",
], max_rows=20)}

## 机制归因

{_md_table(mechanism_summary, [
    "mechanism",
    "status",
    "readiness_score",
    "numeric_evidence_1",
    "numeric_evidence_2",
    "next_action",
], max_rows=20)}

## 探针边界

{_md_table(probe_boundary.sort_values(["probe_family", "value_metric"], ascending=[True, False]), [
    "probe_family",
    "probe",
    "x_metric",
    "y_metric",
    "size_metric",
    "value_metric",
    "status",
], max_rows=30)}

## 闸门

{_md_table(gates, ["gate", "passed", "threshold", "value", "note"], max_rows=20)}

## 图表

- chart: `{CHART_PATH}`

## 过拟合反思

- 运行前: 否。本阶段是汇总已冻结候选与已完成反证，不引入新阈值。
- 运行后: 否。结论主要是停止晋级和保留默认，而不是用历史窗口拟合新规则。

## 继续价值反思

- 运行前: 是。需要把多条策略本体线索收束，避免反复扫同类规则。
- 运行后: 有，但范围变窄。策略本体层暂无可晋级规则；若继续，只能做一个冻结的失败记忆低幅micro-sizing paper探针，或转回执行/TCA和外生selector。
"""


def main() -> None:
    candidate_boundary = _build_variant_boundary()
    mechanism_summary = _build_mechanism_summary(candidate_boundary)
    probe_boundary = _build_probe_boundary()
    gates = _build_gates(candidate_boundary, mechanism_summary)

    gates_passed = int(gates["passed"].sum())
    gates_total = int(len(gates))
    promotion_ready = int(candidate_boundary["all_no_degrade_pass"].sum())
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "strategy_body_no_new_promotion_keep_stage526_floor50_observation_failure_memory_diagnostic",
        "promotion": "none",
        "stage526_body_status": "keep",
        "gates_passed": gates_passed,
        "gates_total": gates_total,
        "promotion_ready_variant_count": promotion_ready,
        "primary_judgement": (
            "Stage526策略本体当前不应被退出形状、快失败代理、早停或失败记忆门禁替换；"
            "默认ATR中位止损和同向相关floor35应保留，floor50只做paper观察。"
        ),
        "next_step": (
            "不继续扫本体小条件；如果仍要在本体层推进，只允许一个预注册的低幅failure-memory micro-sizing paper探针，"
            "否则优先推进真实执行TCA和外生point-in-time selector。"
        ),
        "reference_links": REFERENCE_LINKS,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "outputs": {
            "mechanism_summary": str(MECHANISM_PATH),
            "candidate_boundary": str(CANDIDATE_PATH),
            "probe_boundary": str(PROBE_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidate_boundary.to_csv(CANDIDATE_PATH, index=False, encoding="utf-8-sig")
    mechanism_summary.to_csv(MECHANISM_PATH, index=False, encoding="utf-8-sig")
    probe_boundary.to_csv(PROBE_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(candidate_boundary, mechanism_summary, probe_boundary, gates, decision), encoding="utf-8")
    _plot(candidate_boundary, mechanism_summary, probe_boundary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

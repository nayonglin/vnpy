from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage451_true_path_1455_vwap_replay as s451  # noqa: E402


MODEL_TAG = "stage507_next_real_xsmom_frozen_carrier_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage507_next_real_xsmom_frozen_carrier_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
XSMOM_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"

STAGE506_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage506_next_real_forward_risk_signal_frontier_daily_stage506_next_real_forward_risk_signal_frontier_v1.csv"
)
STAGE403_SATELLITE_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage403_stage079_xsmom_execution_margin_audit_satellite_daily_stage403_stage079_xsmom_execution_margin_audit_v1.csv"
)

BASE_C3_VARIANTS = (
    "stage079_next_real_risk060_clean",
    "stage079_next_real_risk070_clean",
    "stage079_next_real_r080_vol60_t60_min50_entry",
    "stage079_next_real_r080_vol20_t60_min50_entry",
)

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
FRONTIER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _load_stage506_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE506_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "slippage", "trade_count", "account_equity"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["variant", "date"]).reset_index(drop=True)


def _load_xsmom_satellite() -> pd.DataFrame:
    frame = pd.read_csv(STAGE403_SATELLITE_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["satellite_daily_pnl", "satellite_slippage_cost", "satellite_turnover_contracts", "satellite_margin"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame = frame[frame["variant"].eq(XSMOM_VARIANT) & frame["window_name"].eq("start_2020")].copy()
    return (
        frame.groupby("date", as_index=False)
        .agg(
            satellite_daily_pnl=("satellite_daily_pnl", "sum"),
            satellite_slippage_cost=("satellite_slippage_cost", "sum"),
            satellite_turnover_contracts=("satellite_turnover_contracts", "sum"),
            satellite_margin=("satellite_margin", "max"),
        )
        .sort_values("date")
    )


def _combine_daily(stage506: pd.DataFrame, satellite: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []

    baseline = stage506[stage506["variant"].eq(BASELINE_VARIANT)].copy()
    baseline["label"] = "Stage079 same-day baseline"
    rows.append(
        baseline[["date", "variant", "label", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    )

    for variant in BASE_C3_VARIANTS:
        base = stage506[stage506["variant"].eq(variant)].copy()
        if base.empty:
            continue
        base["label"] = f"{variant} clean no xsmom"
        rows.append(base[["date", "variant", "label", "account_equity", "slippage", "trade_count", "net_pnl"]].copy())

        combo = base[["date", "net_pnl", "slippage", "trade_count"]].merge(satellite, on="date", how="left")
        for column in ["satellite_daily_pnl", "satellite_slippage_cost", "satellite_turnover_contracts", "satellite_margin"]:
            combo[column] = pd.to_numeric(combo.get(column, 0.0), errors="coerce").fillna(0.0)
        combo["account_equity"] = ACCOUNT_CAPITAL + (
            combo["net_pnl"].astype(float) + combo["satellite_daily_pnl"].astype(float)
        ).cumsum()
        combo["slippage"] = combo["slippage"].astype(float) + combo["satellite_slippage_cost"].astype(float)
        combo["trade_count"] = combo["trade_count"].astype(float) + combo["satellite_turnover_contracts"].astype(float)
        combo["variant"] = f"{variant}_plus_stage103_xsmom_frozen"
        combo["label"] = f"{variant} + frozen Stage103 xsmom"
        rows.append(combo[["date", "variant", "label", "account_equity", "slippage", "trade_count", "net_pnl"]].copy())

    return pd.concat(rows, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)


def _frontier(summary: pd.DataFrame) -> pd.DataFrame:
    baseline_return = _safe_float(summary[summary["variant"].eq(BASELINE_VARIANT)]["total_return_pct"].iloc[0])
    frame = summary.copy()
    frame["return_retention_vs_stage079_pct"] = frame["total_return_pct"].astype(float) / baseline_return * 100.0
    frame["dd40_pass"] = frame["max_dd_pct"].astype(float).ge(-40.0).astype(int)
    frame["return65_pass"] = frame["return_retention_vs_stage079_pct"].ge(65.0).astype(int)
    frame["diagnostic_gate_pass"] = (frame["dd40_pass"].eq(1) & frame["return65_pass"].eq(1)).astype(int)
    frame["is_frozen_xsmom_combo"] = frame["variant"].str.contains("plus_stage103_xsmom_frozen").astype(int)
    return frame[
        [
            "variant",
            "end_equity",
            "total_return_pct",
            "return_retention_vs_stage079_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "rolling252_dd30_breach_rate",
            "rolling504_dd30_breach_rate",
            "dd40_pass",
            "return65_pass",
            "diagnostic_gate_pass",
            "is_frozen_xsmom_combo",
        ]
    ].sort_values(["diagnostic_gate_pass", "max_dd_pct", "total_return_pct"], ascending=[False, False, False])


def _plot(long_daily: pd.DataFrame) -> None:
    keep = [
        BASELINE_VARIANT,
        "stage079_next_real_risk060_clean",
        "stage079_next_real_risk060_clean_plus_stage103_xsmom_frozen",
        "stage079_next_real_risk070_clean_plus_stage103_xsmom_frozen",
        "stage079_next_real_r080_vol60_t60_min50_entry_plus_stage103_xsmom_frozen",
    ]
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily[long_daily["variant"].isin(keep)].groupby("variant", sort=False):
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=str(frame["label"].iloc[0]), linewidth=1.1)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=str(frame["label"].iloc[0]), linewidth=1.0)
    axes[0].set_title("Stage507 next-real C3 + frozen Stage103 xsmom diagnostic")
    axes[0].set_ylabel("NAV")
    axes[0].legend(fontsize=8)
    axes[1].set_title("Underwater drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    axes[1].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    cost: pd.DataFrame,
    frontier: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "variant",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "annual_cold_start_dd30_pass_rate",
        "quarter_cold_start_dd30_pass_rate",
    ]
    horizon_cols = [
        "variant",
        "horizon_days",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "max_dd_worst_pct",
        "dd30_breach_rate",
        "ulcer_p95_pct",
    ]
    report = [
        "# Stage207 下一真实窗口 + 冻结Stage103 xsmom承载诊断",
        "",
        f"- 生成时间：{decision['generated_at']}",
        "- 阶段性质：工程化前值判断；不新增策略参数，不修改 Stage079/C3/Stage103 规则。",
        "- 关键限制：xsmom腿沿用 Stage103 已冻结日级整数手数结果，尚未按下一真实窗口分钟成交重放；因此本阶段只能判断是否值得做完整工程，不是候选晋级。",
        "",
        "## 外部调研判断",
        "",
        "- 时间序列动量和商品横截面动量是文献中常见的独立期货收益源；仓库内 Stage103 也显示 xsmom 是少数能改善 Stage079 平滑度的固定结构。",
        "- 因 Stage206 已反证继续压 C3 本体风险的价值，本阶段用冻结 xsmom 日腿做 value-of-information 诊断。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最佳诊断版本：`{decision['best_diagnostic_variant']}`。",
        f"- 最佳诊断收益保留：`{decision['best_diagnostic_return_retention_vs_stage079_pct']:.4f}%`。",
        f"- 最佳诊断最大回撤：`{decision['best_diagnostic_max_dd_pct']:.4f}%`。",
        f"- 是否晋级为候选：否，原因是 `{decision['promotion_blocker']}`。",
        "",
        "## 前沿汇总",
        "",
        _md_table(frontier),
        "",
        "## 全周期指标",
        "",
        _md_table(summary[summary_cols]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[horizon_cols].sort_values(["variant", "horizon_days"])),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "slippage_multiplier",
                    "max_dd_pct",
                    "baseline_stage079_max_dd_pct",
                    "not_worse_than_stage079_stress",
                ]
            ]
        ),
        "",
        "## 图表视觉复盘",
        "",
        "- 需要重点看 xsmom 是否抬起 2021-2022 深水，而不是只在后段增加收益。",
        "- 若组合仍长时间贴近 `-40%`，只能说明独立腿有帮助但安全垫不足。",
        "- 若 NAV 相比 `risk060_clean` 明显上移且水下抬升，才值得进入 xsmom 真实窗口成交工程。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。本阶段复用已冻结 Stage103/xsmom 规则，没有新调窗口、阈值、权重或品种。",
        "- 运行后过拟合反思：诊断通过不等于候选通过；若继续只能做完整真实执行重放，不能调 xsmom 参数救结果。",
        "- 运行前继续价值反思：是。Stage206 后继续压 C3 风险价值低，独立收益源是更有第一性原理的方向。",
        "- 运行后继续价值反思：以决策标签为准；若诊断边际充分，下一步做 xsmom 腿真实可成交工程。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    stage506 = _load_stage506_daily()
    satellite = _load_xsmom_satellite()
    long_daily = _combine_daily(stage506, satellite)
    summary, horizon, score, cost, gate = s451._evaluate(long_daily)
    frontier = _frontier(summary)
    _plot(long_daily)

    diagnostic = frontier[frontier["is_frozen_xsmom_combo"].eq(1) & frontier["diagnostic_gate_pass"].eq(1)].copy()
    if diagnostic.empty:
        decision_label = "frozen_xsmom_diagnostic_no_dd40_return65_edge"
        best = frontier[frontier["is_frozen_xsmom_combo"].eq(1)].iloc[0]
    else:
        decision_label = "frozen_xsmom_diagnostic_edge_requires_true_execution"
        best = diagnostic.iloc[0]

    decision = {
        "stage": "Stage207",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "best_diagnostic_variant": str(best["variant"]),
        "best_diagnostic_end_equity": _safe_float(best["end_equity"]),
        "best_diagnostic_total_return_pct": _safe_float(best["total_return_pct"]),
        "best_diagnostic_return_retention_vs_stage079_pct": _safe_float(
            best["return_retention_vs_stage079_pct"]
        ),
        "best_diagnostic_max_dd_pct": _safe_float(best["max_dd_pct"]),
        "best_diagnostic_sharpe": _safe_float(best["sharpe"]),
        "best_diagnostic_ulcer_pct": _safe_float(best["ulcer_pct"]),
        "promotion_blocker": "xsmom_leg_is_frozen_daily_not_next_real_window_replayed",
        "outputs": {
            "daily": str(DAILY_PATH.resolve()),
            "summary": str(SUMMARY_PATH.resolve()),
            "horizon": str(HORIZON_PATH.resolve()),
            "score": str(SCORE_PATH.resolve()),
            "cost": str(COST_PATH.resolve()),
            "gate": str(GATE_PATH.resolve()),
            "frontier": str(FRONTIER_PATH.resolve()),
            "chart": str(CHART_PATH.resolve()),
            "report": str(REPORT_PATH.resolve()),
        },
        "next_step": "若诊断通过，进入xsmom腿下一真实窗口成交工程；若不通过，停止Stage103真实承载方向。",
    }

    long_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    frontier.to_csv(FRONTIER_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, frontier, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()

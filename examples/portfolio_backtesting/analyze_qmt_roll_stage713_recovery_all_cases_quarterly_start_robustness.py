from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage713_recovery_all_cases_quarterly_start_robustness_v1"
OUTPUT_PREFIX = "qmt_roll_stage713_recovery_all_cases_quarterly_start_robustness"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = s707.BASE_VARIANT
CANDIDATE_VARIANT = s707.CANDIDATE_VARIANT
ANALYSIS_END = pd.Timestamp("2026-04-30")
START_DATES = tuple(pd.date_range("2020-01-01", "2026-01-01", freq="QS").strftime("%Y-%m-%d"))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s707._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s707._md_table(frame, max_rows=max_rows)


def _quarter_label(start: str) -> str:
    ts = pd.Timestamp(start)
    return f"{ts.year}Q{((ts.month - 1) // 3) + 1}"


def _windows() -> tuple[tuple[str, str, str, str, str], ...]:
    rows: list[tuple[str, str, str, str, str]] = []
    for start in START_DATES:
        label = _quarter_label(start)
        rows.append(
            (
                f"qstart_{label.lower()}",
                f"{label} 独立启动至 2026-04-30",
                "quarterly_start",
                start,
                ANALYSIS_END.strftime("%Y-%m-%d"),
            )
        )
    return tuple(rows)


def _comparison_with_flags(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    comparison = s707._comparison(summary, cost)
    if comparison.empty:
        return comparison
    comparison["candidate_return_wins"] = (
        comparison["candidate_total_return_pct"].astype(float) > comparison["base_total_return_pct"].astype(float)
    ).astype(int)
    comparison["candidate_dd_wins"] = (
        comparison["candidate_max_dd_pct"].astype(float) >= comparison["base_max_dd_pct"].astype(float)
    ).astype(int)
    comparison["candidate_both_return_dd_wins"] = (
        comparison["candidate_return_wins"].eq(1) & comparison["candidate_dd_wins"].eq(1)
    ).astype(int)
    comparison["candidate_negative_return"] = (comparison["candidate_total_return_pct"].astype(float) < 0.0).astype(int)
    comparison["candidate_dd30_fail"] = (comparison["candidate_max_dd_pct"].astype(float) < -30.0).astype(int)
    return comparison


def _checks(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        rows.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    if comparison.empty:
        add("comparison_non_empty", "fail", 0.0, "> 0", "没有生成季度启动对比。")
        return pd.DataFrame(rows)

    csum = summary[summary["variant"].eq(CANDIDATE_VARIANT)].copy()
    ccost2 = cost[(cost["variant"].eq(CANDIDATE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].copy()

    start_count = float(len(comparison))
    return_win_rate = float(comparison["candidate_return_wins"].mean() * 100.0)
    dd_win_rate = float(comparison["candidate_dd_wins"].mean() * 100.0)
    both_win_rate = float(comparison["candidate_both_return_dd_wins"].mean() * 100.0)
    negative_count = float(comparison["candidate_negative_return"].sum())
    dd30_fail_count = float(comparison["candidate_dd30_fail"].sum())
    retention_p10 = float(comparison["return_retention_pct"].quantile(0.10))
    retention_median = float(comparison["return_retention_pct"].median())
    worst_dd = float(csum["max_dd_pct"].min())
    worst_cost2_dd = float(ccost2["max_dd_pct"].min()) if not ccost2.empty else float("nan")

    add("quarterly_start_count", "pass", start_count, ">= 20", "覆盖 2020Q1 至 2026Q1 的季度独立启动。")
    add(
        "return_win_rate_ge50",
        "pass" if return_win_rate >= 50.0 else "fail",
        return_win_rate,
        ">= 50%",
        "候选不能只靠少数起点赢。",
    )
    add(
        "dd_win_rate_ge70",
        "pass" if dd_win_rate >= 70.0 else "fail",
        dd_win_rate,
        ">= 70%",
        "作为风控机制，候选应在大多数启动点改善或不恶化回撤。",
    )
    add(
        "both_return_dd_win_rate_ge40",
        "pass" if both_win_rate >= 40.0 else "watch",
        both_win_rate,
        ">= 40%",
        "同时改善收益和回撤的启动点比例，用于衡量不是单纯降风险壳。",
    )
    add(
        "negative_start_count_eq0",
        "pass" if negative_count == 0.0 else "fail",
        negative_count,
        "= 0",
        "任意季度独立启动不应转为负收益。",
    )
    add(
        "dd30_fail_count_eq0",
        "pass" if dd30_fail_count == 0.0 else "fail",
        dd30_fail_count,
        "= 0",
        "DD30 目标要求季度启动也不能破 30 回撤。",
    )
    add(
        "retention_p10_ge70",
        "pass" if retention_p10 >= 70.0 else "fail",
        retention_p10,
        ">= 70%",
        "收益保留的尾部启动点不能过差。",
    )
    add(
        "retention_median_ge80",
        "pass" if retention_median >= 80.0 else "fail",
        retention_median,
        ">= 80%",
        "中位启动点应保持足够收益。",
    )
    add(
        "worst_dd30_pass",
        "pass" if worst_dd >= -30.0 else "fail",
        worst_dd,
        ">= -30%",
        "候选最差季度启动也要符合本线回撤目标。",
    )
    add(
        "cost2_worst_dd40_pass",
        "pass" if worst_cost2_dd >= -40.0 else "fail",
        worst_cost2_dd,
        "2x cost worst DD >= -40%",
        "2x 成本压力不能破生存边界。",
    )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision = (
        "recovery_all_cases_quarterly_start_validation_pass_watch"
        if not hard_fail
        else "recovery_all_cases_quarterly_start_not_promoted"
    )
    return {
        "stage": "Stage427",
        "script_stage": "Stage713",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "validation_only": True,
            "candidate_source": "Stage421/Script707 recovery all native entry cases",
            "quarterly_start_dates": list(START_DATES),
            "analysis_end": ANALYSIS_END.strftime("%Y-%m-%d"),
        },
        "checks": checks.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "curves": str(CURVES_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot(comparison: pd.DataFrame) -> None:
    if comparison.empty:
        return
    data = comparison.copy()
    data["start_label"] = data["window_name"].astype(str).str.replace("qstart_", "", regex=False).str.upper()
    x = np.arange(len(data))

    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    axes[0].bar(x - 0.18, data["base_total_return_pct"], width=0.36, label="A official", color="#ea580c")
    axes[0].bar(x + 0.18, data["candidate_total_return_pct"], width=0.36, label="C all-cases recovery", color="#2563eb")
    axes[0].axhline(0, color="#334155", linewidth=0.8)
    axes[0].set_ylabel("Return %")
    axes[0].legend(loc="upper right")
    axes[0].grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.35)

    axes[1].plot(x, data["base_max_dd_pct"], label="A official DD", color="#ea580c", linewidth=1.4)
    axes[1].plot(x, data["candidate_max_dd_pct"], label="C candidate DD", color="#2563eb", linewidth=1.4)
    axes[1].axhline(-30, color="#ef4444", linestyle="--", linewidth=0.9)
    axes[1].set_ylabel("Max DD %")
    axes[1].legend(loc="lower left")
    axes[1].grid(True, linestyle="--", linewidth=0.5, alpha=0.35)

    axes[2].bar(x, data["return_retention_pct"], color="#0f766e")
    axes[2].axhline(70, color="#f97316", linestyle="--", linewidth=0.9)
    axes[2].axhline(100, color="#64748b", linestyle=":", linewidth=0.9)
    axes[2].set_ylabel("Retention %")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(data["start_label"], rotation=45, ha="right")
    axes[2].grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.35)

    fig.suptitle("Stage427 / Script713 Quarterly Start Robustness: Official vs Stage421 All-Cases Recovery")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    cost: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    stats = {
        "quarterly_start_count": len(comparison),
        "return_win_rate_pct": float(comparison["candidate_return_wins"].mean() * 100.0) if not comparison.empty else 0.0,
        "dd_win_rate_pct": float(comparison["candidate_dd_wins"].mean() * 100.0) if not comparison.empty else 0.0,
        "both_win_rate_pct": float(comparison["candidate_both_return_dd_wins"].mean() * 100.0)
        if not comparison.empty
        else 0.0,
        "negative_start_count": int(comparison["candidate_negative_return"].sum()) if not comparison.empty else 0,
        "dd30_fail_count": int(comparison["candidate_dd30_fail"].sum()) if not comparison.empty else 0,
        "retention_median_pct": float(comparison["return_retention_pct"].median()) if not comparison.empty else 0.0,
        "retention_p10_pct": float(comparison["return_retention_pct"].quantile(0.10)) if not comparison.empty else 0.0,
    }
    key_cols = [
        "window_name",
        "return_retention_pct",
        "base_total_return_pct",
        "candidate_total_return_pct",
        "base_max_dd_pct",
        "candidate_max_dd_pct",
        "delta_max_dd_pct",
        "base_sharpe",
        "candidate_sharpe",
        "candidate_return_wins",
        "candidate_dd_wins",
        "candidate_negative_return",
        "candidate_dd30_fail",
    ]
    lines = [
        "# Stage427 / Script713 Recovery All Cases Quarterly Start Robustness",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前正式 Stage372/20w。",
        "- C：Stage421 all-cases recovery，保持 `streak_risk_multipliers=1,1,1,0.1`，仅把 clean-book recovery lift 从 `case1a` 扩到全部原生趋势 case。",
        "- 本阶段是验证脚本，不新增候选参数、不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Stats",
        "",
        _md_table(pd.DataFrame([stats])),
        "",
        "## Checks",
        "",
        _md_table(checks),
        "",
        "## Quarterly Comparison",
        "",
        _md_table(comparison[key_cols], max_rows=80),
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## Cost Stress",
        "",
        _md_table(cost, max_rows=120),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    base_spec = s660._official_spec(metadata)
    candidate_spec = s707._candidate_spec(metadata)
    specs = [base_spec, candidate_spec]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, window_label, window_group, start, end in _windows():
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        for spec in specs:
            print(f"[stage713] running {window_name} {spec.capital.variant}", flush=True)
            frame, forced_events = s660._run_independent_window(
                spec=spec,
                metadata=metadata,
                analysis_start=start_ts,
                analysis_end=end_ts,
            )
            row, curve, costs = s707._metric_row(
                frame,
                spec=spec,
                window_name=window_name,
                window_label=window_label,
                window_group=window_group,
                forced_events=forced_events,
            )
            summary_rows.append(row)
            curve_frames.append(curve)
            cost_rows.extend(costs)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    comparison = _comparison_with_flags(summary, cost)
    checks = _checks(summary, comparison, cost)
    decision = _decision(summary, comparison, cost, checks)

    _plot(comparison)
    _write_report(summary, comparison, cost, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

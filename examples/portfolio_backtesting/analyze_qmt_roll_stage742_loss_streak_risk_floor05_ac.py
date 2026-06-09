from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
import analyze_qmt_roll_stage738_postentry_quality_add_real_ac as s738
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage742_loss_streak_risk_floor05_ac_v1"
OUTPUT_PREFIX = "qmt_roll_stage742_loss_streak_risk_floor05_ac"
LINE_ID = "futures_trend_loss_streak_risk_floor"

BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
CANDIDATE_VARIANT = f"{OFFICIAL_LIVE_PROFILE_NAME}_lossfloor05_stage742"
BASE_MULTIPLIERS = "1.0,1.0,1.0,0.1"
CANDIDATE_MULTIPLIERS = "1.0,1.0,1.0,0.5"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_stats_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _candidate_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    base = s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="C loss streak risk floor 0.5",
        note=(
            "Official Stage372/20w unchanged except loss-streak risk multipliers are relaxed from "
            f"{BASE_MULTIPLIERS} to {CANDIDATE_MULTIPLIERS}. AI pool, product pool, recovery sleeve, maxpos "
            "and margin deleveraging are unchanged."
        ),
    )
    overrides = {**base.overrides, "streak_risk_multipliers": CANDIDATE_MULTIPLIERS}
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_loss_streak_floor05_stage742")


def _base_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    base = s660._official_spec(metadata)
    overrides = {**base.overrides, "streak_risk_multipliers": BASE_MULTIPLIERS}
    return replace(base, overrides=overrides)


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    fields = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "max_broker10_margin_to_equity_pct",
        "p95_broker10_margin_to_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
    ]
    for window_name, group in summary.groupby("window_name", sort=False):
        base = group[group["variant"].eq(BASE_VARIANT)]
        candidate = group[group["variant"].eq(CANDIDATE_VARIANT)]
        if base.empty or candidate.empty:
            continue
        b = base.iloc[0]
        c = candidate.iloc[0]
        base_ret = float(b["total_return_pct"])
        cand_ret = float(c["total_return_pct"])
        row: dict[str, Any] = {
            "window_name": window_name,
            "window_group": str(c["window_group"]),
            "candidate_variant": CANDIDATE_VARIANT,
            "base_return_pct": base_ret,
            "candidate_return_pct": cand_ret,
            "return_retention_pct": cand_ret / base_ret * 100.0 if base_ret > 0 else 0.0,
        }
        for field in fields:
            row[f"base_{field}"] = float(b.get(field, 0.0) or 0.0)
            row[f"candidate_{field}"] = float(c.get(field, 0.0) or 0.0)
            row[f"delta_{field}"] = row[f"candidate_{field}"] - row[f"base_{field}"]
        for multiplier in (2.0, 3.0):
            bcost = cost[
                cost["variant"].eq(BASE_VARIANT)
                & cost["window_name"].eq(window_name)
                & cost["cost_multiplier"].eq(multiplier)
            ]
            ccost = cost[
                cost["variant"].eq(CANDIDATE_VARIANT)
                & cost["window_name"].eq(window_name)
                & cost["cost_multiplier"].eq(multiplier)
            ]
            if not bcost.empty and not ccost.empty:
                row[f"base_{multiplier:.0f}x_max_dd_pct"] = float(bcost["max_dd_pct"].iloc[0])
                row[f"candidate_{multiplier:.0f}x_max_dd_pct"] = float(ccost["max_dd_pct"].iloc[0])
                row[f"delta_{multiplier:.0f}x_max_dd_pct"] = (
                    float(ccost["max_dd_pct"].iloc[0]) - float(bcost["max_dd_pct"].iloc[0])
                )
                row[f"candidate_{multiplier:.0f}x_deployable_pass"] = int(ccost["deployable_pass"].iloc[0])
        rows.append(row)
    return pd.DataFrame(rows)


def _entry_risk_stats(entry_risk: pd.DataFrame) -> pd.DataFrame:
    if entry_risk.empty:
        return pd.DataFrame()
    data = entry_risk.copy()
    for column in [
        "risk_multiplier",
        "loss_streak",
        "selected_volume",
        "target_risk_amount",
        "actual_risk_amount",
        "contracts_by_risk",
        "contracts_by_margin",
        "streak_entry_structure_risk_recovery_applied",
        "streak_entry_structure_risk_recovery_base_multiplier",
        "streak_entry_structure_risk_recovery_effective_multiplier",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    rows: list[dict[str, Any]] = []
    for (variant, window_name, window_group), group in data.groupby(["variant", "window_name", "window_group"], sort=False):
        opened = group[group["selected_volume"].gt(0)].copy()
        severe_opened = opened[opened["loss_streak"].ge(3)]
        rows.append(
            {
                "variant": variant,
                "window_name": window_name,
                "window_group": window_group,
                "candidate_rows": int(len(group)),
                "opened_rows": int(len(opened)),
                "severe_opened_rows": int(len(severe_opened)),
                "floor01_opened_rows": int(opened["risk_multiplier"].le(0.100001).sum()),
                "floor05_opened_rows": int(opened["risk_multiplier"].between(0.100001, 0.500001).sum()),
                "fullrisk_opened_rows": int(opened["risk_multiplier"].ge(0.999999).sum()),
                "avg_opened_risk_multiplier": float(opened["risk_multiplier"].mean()) if not opened.empty else 0.0,
                "avg_severe_opened_risk_multiplier": float(severe_opened["risk_multiplier"].mean()) if not severe_opened.empty else 0.0,
                "sum_opened_target_risk": float(opened["target_risk_amount"].sum()),
                "sum_opened_actual_risk": float(opened["actual_risk_amount"].sum()),
                "sum_severe_opened_target_risk": float(severe_opened["target_risk_amount"].sum()),
                "sum_severe_opened_actual_risk": float(severe_opened["actual_risk_amount"].sum()),
                "recovery_applied_rows": int(opened["streak_entry_structure_risk_recovery_applied"].eq(1).sum()),
            }
        )
    return pd.DataFrame(rows)


def _check_rows(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        checks.append(
            {
                "candidate_variant": CANDIDATE_VARIANT,
                "check_name": name,
                "status": status,
                "value": value,
                "threshold": threshold,
                "comment": comment,
            }
        )

    full = comparison[comparison["window_name"].eq("full_2020_20260430")].iloc[0]
    start_years = comparison[comparison["window_group"].eq("start_year")].copy()
    phases = comparison[comparison["window_group"].eq("phase")].copy()
    cand_summary = summary[summary["variant"].eq(CANDIDATE_VARIANT)].copy()
    cand_full = cand_summary[cand_summary["window_name"].eq("full_2020_20260430")].iloc[0]
    cand_cost2_full = cost[
        cost["variant"].eq(CANDIDATE_VARIANT)
        & cost["window_name"].eq("full_2020_20260430")
        & cost["cost_multiplier"].eq(2.0)
    ].iloc[0]

    add("full_end_equity_delta_gt0", "pass" if float(full["delta_end_equity"]) > 0 else "fail", float(full["delta_end_equity"]), "> 0", "放宽风险地板必须提升全周期绝对收益。")
    add("full_dd40_pass", "pass" if float(full["candidate_max_dd_pct"]) >= -40.0 else "fail", float(full["candidate_max_dd_pct"]), ">= -40%", "正式风控变更不能打穿全周期生存线。")
    add("full_dd_not_worse_3pp", "pass" if float(full["delta_max_dd_pct"]) >= -3.0 else "fail", float(full["delta_max_dd_pct"]), ">= -3pp", "半防守地板不能明显加深最大回撤。")
    add("full_sharpe_not_worse_005", "pass" if float(full["delta_sharpe"]) >= -0.05 else "fail", float(full["delta_sharpe"]), ">= -0.05", "收益如果上升，也不能显著牺牲单位波动效率。")
    add("full_broker10_100_pass", "pass" if int(cand_full["broker10_100_pass"]) == 1 else "fail", float(full["candidate_max_broker10_margin_to_equity_pct"]), "<= 100%", "不能靠保证金穿线换收益。")
    add("cost2_dd_not_worse_3pp", "pass" if float(full.get("delta_2x_max_dd_pct", -999.0)) >= -3.0 else "fail", float(full.get("delta_2x_max_dd_pct", 0.0)), ">= -3pp", "2x成本下不能明显脆弱化。")
    add("cost2_deployable_pass", "pass" if int(cand_cost2_full["deployable_pass"]) == 1 else "fail", float(cand_cost2_full["max_dd_pct"]), "2x cost deployable", "2x成本下仍需满足DD40、broker100和账户生存。")
    add("cost3_dd_not_worse_3pp", "pass" if float(full.get("delta_3x_max_dd_pct", -999.0)) >= -3.0 else "fail", float(full.get("delta_3x_max_dd_pct", 0.0)), ">= -3pp", "3x成本压力不能比正式版明显更差。")
    add("start_year_min_retention_ge80", "pass" if float(start_years["return_retention_pct"].min()) >= 80.0 else "fail", float(start_years["return_retention_pct"].min()), ">= 80%", "不能只靠2020全周期复利路径胜出。")
    add("start_year_dd_not_worse_3pp", "pass" if float(start_years["delta_max_dd_pct"].min()) >= -3.0 else "fail", float(start_years["delta_max_dd_pct"].min()), ">= -3pp", "年度独立起点回撤不能明显恶化。")
    add("start_year_dd40_all_pass", "pass" if int(cand_summary[cand_summary["window_group"].eq("start_year")]["dd40_pass"].min()) == 1 else "fail", float(cand_summary[cand_summary["window_group"].eq("start_year")]["max_dd_pct"].min()), "all start-year DD >= -40%", "年度冷启动不能打穿生存线。")
    add("phase_min_retention_ge75", "pass" if float(phases["return_retention_pct"].min()) >= 75.0 else "fail", float(phases["return_retention_pct"].min()), ">= 75%", "分段窗口不能高度依赖单一周期。")
    add("phase_dd_not_worse_3pp", "pass" if float(phases["delta_max_dd_pct"].min()) >= -3.0 else "fail", float(phases["delta_max_dd_pct"].min()), ">= -3pp", "阶段窗口回撤不能明显恶化。")
    return pd.DataFrame(checks)


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fails = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    full = comparison[comparison["window_name"].eq("full_2020_20260430")].iloc[0].to_dict()
    return {
        "stage": "Stage001",
        "script_stage": "Stage742",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "baseline_multipliers": BASE_MULTIPLIERS,
        "candidate_multipliers": CANDIDATE_MULTIPLIERS,
        "decision": "loss_streak_floor05_next_validation_candidate" if not hard_fails else "loss_streak_floor05_not_promoted",
        "hard_fail_checks": hard_fails,
        "full_comparison": full,
        "checks": checks.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "curves": str(CURVES_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_stats": str(ENTRY_STATS_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot(curves: pd.DataFrame) -> None:
    plot_windows = ["full_2020_20260430", "since_2022", "phase_2024_2025"]
    labels = {
        BASE_VARIANT: "A official floor 0.1",
        CANDIDATE_VARIANT: "C floor 0.5",
    }
    colors = {
        BASE_VARIANT: "#d97706",
        CANDIDATE_VARIANT: "#2563eb",
    }
    fig, axes = plt.subplots(len(plot_windows), 1, figsize=(14, 11), sharex=False)
    for ax, window_name in zip(axes, plot_windows):
        window = curves[curves["window_name"].eq(window_name)].copy()
        for variant in [BASE_VARIANT, CANDIDATE_VARIANT]:
            data = window[window["variant"].eq(variant)].sort_values("date")
            if data.empty:
                continue
            ax.plot(data["date"], data["account_equity"], label=labels[variant], color=colors[variant], linewidth=1.7)
        ax.axhline(OFFICIAL_LIVE_CAPITAL, color="#9ca3af", linestyle="--", linewidth=0.9)
        ax.set_title(window_name)
        ax.set_ylabel("Account equity")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left")
    axes[-1].set_xlabel("Date")
    fig.suptitle("Stage742 Loss-Streak Risk Floor A/C: official 0.1 vs candidate 0.5", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    cost: pd.DataFrame,
    annual: pd.DataFrame,
    entry_stats: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    full_cols = [
        "variant",
        "label",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "max_broker10_margin_to_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "forced_margin_deleverage_count",
    ]
    comp_cols = [
        "window_name",
        "window_group",
        "return_retention_pct",
        "delta_end_equity",
        "delta_max_dd_pct",
        "delta_sharpe",
        "delta_total_slippage",
        "delta_total_trade_count",
    ]
    full_summary = summary[summary["window_name"].eq("full_2020_20260430")][full_cols].copy()
    full_entry = entry_stats[entry_stats["window_name"].eq("full_2020_20260430")].copy()
    text = [
        "# Stage742 / Stage001 连败风险地板 0.5 A/C",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- A：正式 `streak_risk_multipliers={BASE_MULTIPLIERS}`。",
        f"- C：仅改为 `streak_risk_multipliers={CANDIDATE_MULTIPLIERS}`。",
        "- 不改 AI、不改品种池、不改 recovery sleeve、不改 maxpos、不改保证金强制减仓；不连接 CTP，不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- Backtrader 的 sizer 设计把仓位大小从信号逻辑中分离，说明风险地板属于资金管理层，不是新的 alpha 信号。",
        "- 趋势跟随资料普遍强调 money management 和 initial risk 决定持仓大小；连败后降风险是防守问题，不应只用收益最大化选择。",
        "- Turtle 相关风控资料也支持回撤期降低 unit size；本实验的关键是检验 `0.5` 是否仍保留足够防守性。",
        "",
        "## 全周期结果",
        "",
        _md_table(full_summary, max_rows=10),
        "",
        "## 多起点对照",
        "",
        _md_table(comparison[comp_cols], max_rows=80),
        "",
        "## 成本压力",
        "",
        _md_table(cost[cost["window_name"].eq("full_2020_20260430")], max_rows=10),
        "",
        "## 全周期开仓风险诊断",
        "",
        _md_table(full_entry, max_rows=10),
        "",
        "## 年度结果",
        "",
        _md_table(annual, max_rows=40),
        "",
        "## 预声明闸门",
        "",
        _md_table(checks, max_rows=80),
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 过拟合反思",
        "",
        "- 运行前：中等风险。`0.5` 是用户指定的单点倍率，结构问题真实存在，但不能用单一路径曲线判断。",
        "- 运行后：以预声明闸门为准；若失败，不继续扫倍率小数救参。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前：有价值。它直接回答正式版 `0.1` 是否过于保守。",
        "- 运行后：若 C 未过，继续价值转向独立外生 selector 或 forward watch，而不是倍率地板扫描。",
    ]
    REPORT_PATH.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    s738.POST_COUNT_COLUMNS = []
    metadata = s513._metadata()
    specs = [_base_spec(metadata), _candidate_spec(metadata)]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    entry_frames: list[pd.DataFrame] = []
    total_runs = len(s707.WINDOWS) * len(specs)
    run_index = 0
    for window_name, window_label, window_group, start, end in s707.WINDOWS:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        for spec in specs:
            run_index += 1
            print(f"[stage742] {run_index}/{total_runs} {window_name} {spec.capital.variant}", flush=True)
            frame, forced_events, entry_risk = s738._run_independent_window(
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
            if not entry_risk.empty:
                tagged = entry_risk.copy()
                tagged["window_name"] = window_name
                tagged["window_label"] = window_label
                tagged["window_group"] = window_group
                entry_frames.append(tagged)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    entry_risk = pd.concat(entry_frames, ignore_index=True, sort=False) if entry_frames else pd.DataFrame()
    entry_stats = _entry_risk_stats(entry_risk)
    comparison = _comparison(summary, cost)
    annual, monthly = s707._annual_monthly(curves)
    checks = _check_rows(summary, comparison, cost)
    decision = _decision(summary, comparison, cost, checks)

    _plot(curves)
    _write_report(summary, comparison, cost, annual, entry_stats, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_stats.to_csv(ENTRY_STATS_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(summary[summary["window_name"].eq("full_2020_20260430")].to_string(index=False))
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()

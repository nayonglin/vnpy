from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
import analyze_qmt_roll_stage738_postentry_quality_add_real_ac as s738
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage741_postentry_quality_prev2day_relax_ac_v1"
OUTPUT_PREFIX = "qmt_roll_stage741_postentry_quality_prev2day_relax_ac"
LINE_ID = "futures_trend_winner_trade_forensics"

BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
COUNT_COLUMNS = ["post_entry_quality_prev2day_relax_skip_count"]
CANDIDATES: tuple[dict[str, str], ...] = (
    {
        "variant": "stage526_200k_force95_to80_post1_smooth_prev2delay_once_stage741",
        "label": "C1 post1 smooth once-delay prev2day stop",
        "feature": "post1_smooth_directional_combo",
    },
    {
        "variant": "stage526_200k_force95_to80_post5_long60le20_prev2delay_once_stage741",
        "label": "C2 post5 long60<=20 once-delay prev2day stop",
        "feature": "post5_long60_ratio_le20",
    },
)
CANDIDATE_VARIANTS = tuple(item["variant"] for item in CANDIDATES)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _candidate_spec(metadata: dict[str, Any], candidate: dict[str, str]):
    base = s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=candidate["variant"],
        label=candidate["label"],
        note=(
            "Official Stage372 unchanged; after a predeclared post-entry candle-quality feature is visible, "
            "delay one prev2day_stop trigger at most once for the current position. No added size, no initial "
            "risk expansion, no product-pool change."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_post_entry_quality_add": False,
        "enable_post_entry_quality_prev2day_relax": True,
        "post_entry_quality_prev2day_relax_feature": candidate["feature"],
        "post_entry_quality_add_body_pct_min": 0.60,
        "post_entry_quality_add_body_ratio_min": 0.50,
        "post_entry_quality_add_directional_close_strength_min": 0.60,
        "post_entry_quality_add_short_wick_ratio_min": 0.50,
        "post_entry_quality_add_long_wick_ratio_max": 0.20,
        "post_entry_quality_add_adverse_wick_pct_max": 0.25,
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
    }
    return replace(
        base,
        capital=capital,
        overrides=overrides,
        profile=f"official_stage372_post_entry_quality_prev2day_relax_{candidate['feature']}_stage741",
    )


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    fields = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "max_broker10_margin_to_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        *COUNT_COLUMNS,
    ]
    for window_name, group in summary.groupby("window_name", sort=False):
        base = group[group["variant"].eq(BASE_VARIANT)]
        if base.empty:
            continue
        b = base.iloc[0]
        for candidate_variant in CANDIDATE_VARIANTS:
            candidate = group[group["variant"].eq(candidate_variant)]
            if candidate.empty:
                continue
            c = candidate.iloc[0]
            base_ret = float(b["total_return_pct"])
            cand_ret = float(c["total_return_pct"])
            row: dict[str, Any] = {
                "window_name": window_name,
                "window_group": str(c["window_group"]),
                "candidate_variant": candidate_variant,
                "candidate_label": str(c["label"]),
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
                    cost["variant"].eq(candidate_variant)
                    & cost["window_name"].eq(window_name)
                    & cost["cost_multiplier"].eq(multiplier)
                ]
                if not bcost.empty and not ccost.empty:
                    row[f"base_{multiplier:.0f}x_max_dd_pct"] = float(bcost["max_dd_pct"].iloc[0])
                    row[f"candidate_{multiplier:.0f}x_max_dd_pct"] = float(ccost["max_dd_pct"].iloc[0])
                    row[f"delta_{multiplier:.0f}x_max_dd_pct"] = (
                        float(ccost["max_dd_pct"].iloc[0]) - float(bcost["max_dd_pct"].iloc[0])
                    )
            rows.append(row)
    return pd.DataFrame(rows)


def _check_rows(summary: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(candidate: str, name: str, status: str, value: float, threshold: str, comment: str) -> None:
        checks.append(
            {
                "candidate_variant": candidate,
                "check_name": name,
                "status": status,
                "value": value,
                "threshold": threshold,
                "comment": comment,
            }
        )

    count_col = "candidate_post_entry_quality_prev2day_relax_skip_count"
    for candidate in CANDIDATE_VARIANTS:
        rows = comparison[comparison["candidate_variant"].eq(candidate)].copy()
        if rows.empty:
            continue
        full = rows[rows["window_name"].eq("full_2020_20260430")].iloc[0]
        cand_summary = summary[
            summary["variant"].eq(candidate) & summary["window_name"].eq("full_2020_20260430")
        ].iloc[0]
        start_years = rows[rows["window_group"].eq("start_year")].copy()
        phases = rows[rows["window_group"].eq("phase")].copy()

        add(candidate, "full_end_equity_delta_gt0", "pass" if float(full["delta_end_equity"]) > 0 else "fail", float(full["delta_end_equity"]), "> 0", "退出延迟必须提升全周期绝对收益。")
        add(candidate, "full_dd_not_worse_2pp", "pass" if float(full["delta_max_dd_pct"]) >= -2.0 else "fail", float(full["delta_max_dd_pct"]), ">= -2pp", "减少过早退出不能显著放大回撤。")
        add(candidate, "full_sharpe_not_worse_003", "pass" if float(full["delta_sharpe"]) >= -0.03 else "fail", float(full["delta_sharpe"]), ">= -0.03", "持仓规则不能显著恶化单位波动收益。")
        add(candidate, "full_trade_count_le110pct", "pass" if float(full["candidate_total_trade_count"]) <= float(full["base_total_trade_count"]) * 1.10 else "fail", float(full["candidate_total_trade_count"] / max(float(full["base_total_trade_count"]), 1.0) * 100.0), "<= 110%", "不加仓版本不应显著增加换手。")
        add(candidate, "full_slippage_le110pct", "pass" if float(full["candidate_total_slippage"]) <= float(full["base_total_slippage"]) * 1.10 else "fail", float(full["candidate_total_slippage"] / max(float(full["base_total_slippage"]), 1.0) * 100.0), "<= 110%", "不加仓版本成本应基本可控。")
        add(candidate, "full_broker10_100_pass", "pass" if int(cand_summary["broker10_100_pass"]) == 1 else "fail", float(full["candidate_max_broker10_margin_to_equity_pct"]), "<= 100%", "不能用保证金打穿换收益。")
        add(candidate, "cost2_dd_not_worse_3pp", "pass" if float(full.get("delta_2x_max_dd_pct", -999.0)) >= -3.0 else "fail", float(full.get("delta_2x_max_dd_pct", float("nan"))), ">= -3pp", "2x成本压力下不能明显脆弱化。")
        add(candidate, "cost3_dd_not_worse_3pp", "pass" if float(full.get("delta_3x_max_dd_pct", -999.0)) >= -3.0 else "fail", float(full.get("delta_3x_max_dd_pct", float("nan"))), ">= -3pp", "3x成本压力不能显著更差。")
        add(candidate, "start_year_min_retention_ge80", "pass" if float(start_years["return_retention_pct"].min()) >= 80.0 else "fail", float(start_years["return_retention_pct"].min()), ">= 80%", "多起点不能只靠某一段行情。")
        add(candidate, "start_year_min_dd_delta_ge_minus3", "pass" if float(start_years["delta_max_dd_pct"].min()) >= -3.0 else "fail", float(start_years["delta_max_dd_pct"].min()), ">= -3pp", "年度冷启动回撤不能明显恶化。")
        add(candidate, "phase_min_dd_delta_ge_minus3", "pass" if float(phases["delta_max_dd_pct"].min()) >= -3.0 else "fail", float(phases["delta_max_dd_pct"].min()), ">= -3pp", "分段冷启动回撤不能明显恶化。")
        add(candidate, "relax_skip_count_gt0", "pass" if float(full[count_col]) > 0 else "fail", float(full[count_col]), "> 0", "如果没有真实触发，就只是空通过。")
    return pd.DataFrame(checks)


def _decision(comparison: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for candidate in CANDIDATE_VARIANTS:
        cchecks = checks[checks["candidate_variant"].eq(candidate)]
        full = comparison[
            comparison["candidate_variant"].eq(candidate) & comparison["window_name"].eq("full_2020_20260430")
        ]
        if full.empty:
            decisions.append({"candidate_variant": candidate, "decision": "not_run", "reason": "missing_full_window"})
            continue
        hard_fails = cchecks[cchecks["status"].eq("fail")]["check_name"].tolist()
        row = full.iloc[0]
        decisions.append(
            {
                "candidate_variant": candidate,
                "candidate_label": str(row["candidate_label"]),
                "decision": "next_validation_candidate" if not hard_fails else "not_promoted",
                "reason": "all_predeclared_hard_gates_pass" if not hard_fails else "failed: " + ",".join(hard_fails),
                "full_end_equity": float(row["candidate_end_equity"]),
                "full_end_equity_delta": float(row["delta_end_equity"]),
                "full_total_return_pct": float(row["candidate_total_return_pct"]),
                "full_max_dd_pct": float(row["candidate_max_dd_pct"]),
                "full_delta_max_dd_pct": float(row["delta_max_dd_pct"]),
                "full_sharpe": float(row["candidate_sharpe"]),
                "relax_skip_count": float(row["candidate_post_entry_quality_prev2day_relax_skip_count"]),
            }
        )
    return {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "baseline": BASE_VARIANT,
        "candidate_decisions": decisions,
        "overall_decision": (
            "has_next_validation_candidate"
            if any(item["decision"] == "next_validation_candidate" for item in decisions)
            else "no_promotion"
        ),
        "chart_path": str(CHART_PATH),
        "report_path": str(REPORT_PATH),
    }


def _plot(curves: pd.DataFrame) -> None:
    full_windows = ["full_2020_20260430", "since_2022", "phase_2024_2025"]
    labels = {
        BASE_VARIANT: "A official",
        CANDIDATES[0]["variant"]: "C1 post1 smooth delay",
        CANDIDATES[1]["variant"]: "C2 post5 long60 delay",
    }
    colors = {
        BASE_VARIANT: "#d97706",
        CANDIDATES[0]["variant"]: "#2563eb",
        CANDIDATES[1]["variant"]: "#16a34a",
    }
    fig, axes = plt.subplots(len(full_windows), 1, figsize=(14, 12), sharex=False)
    for ax, window_name in zip(axes, full_windows):
        window = curves[curves["window_name"].eq(window_name)].copy()
        for variant in [BASE_VARIANT, *CANDIDATE_VARIANTS]:
            data = window[window["variant"].eq(variant)].sort_values("date")
            if data.empty:
                continue
            ax.plot(
                data["date"],
                data["account_equity"],
                label=labels.get(variant, variant),
                linewidth=1.8,
                color=colors.get(variant),
            )
        ax.axhline(OFFICIAL_LIVE_CAPITAL, color="#9ca3af", linestyle="--", linewidth=1.0)
        ax.set_title(window_name)
        ax.set_ylabel("Account equity")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left")
    axes[-1].set_xlabel("Date")
    fig.suptitle("Stage741 Real A/C: one-shot prev2day delay after post-entry quality", fontsize=16)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    cost: pd.DataFrame,
    annual: pd.DataFrame,
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
        "total_slippage",
        "total_trade_count",
        *COUNT_COLUMNS,
    ]
    comp_cols = [
        "candidate_variant",
        "window_name",
        "return_retention_pct",
        "delta_end_equity",
        "delta_max_dd_pct",
        "delta_sharpe",
        "candidate_post_entry_quality_prev2day_relax_skip_count",
    ]
    full_summary = summary[summary["window_name"].eq("full_2020_20260430")][full_cols].copy()
    text = [
        "# Stage741 入场后顺畅K线一次性延迟 prev2day_stop 真实 A/C",
        "",
        f"- 生成时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        f"- 研究线：`{LINE_ID}`",
        f"- 基准：`{BASE_VARIANT}`",
        "- A：正式 Stage372/20万，不改。",
        "- C1：`post1_smooth_directional_combo` 出现后，当前持仓最多一次延迟 `prev2day_stop`。",
        "- C2：`post5_long60_ratio_le20` 出现后，当前持仓最多一次延迟 `prev2day_stop`。",
        "- 不加仓、不扩大初始风险、不改 AI、不改品种池、不扫延迟天数。",
        "",
        "## 全周期结果",
        "",
        _md_table(full_summary, max_rows=10),
        "",
        "## 多起点对照",
        "",
        _md_table(comparison[comp_cols], max_rows=60),
        "",
        "## 成本压力",
        "",
        _md_table(cost[cost["window_name"].eq("full_2020_20260430")], max_rows=12),
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
        "- 运行前：中等风险，但特征来自 Stage740 固定观察闸门；本阶段只测两个标签，不扫阈值。",
        "- 运行后：若失败，不允许用延迟2/3天、叠年份/品种/方向或放宽标签救参。",
    ]
    REPORT_PATH.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    s738.POST_COUNT_COLUMNS = COUNT_COLUMNS

    metadata = s513._metadata()
    base_spec = s660._official_spec(metadata)
    specs = [base_spec] + [_candidate_spec(metadata, item) for item in CANDIDATES]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, window_label, window_group, start, end in s707.WINDOWS:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        for spec in specs:
            print(f"[stage741] running {window_name} {spec.capital.variant}", flush=True)
            frame, forced_events, _entry_risk = s738._run_independent_window(
                spec=spec,
                metadata=metadata,
                analysis_start=start_ts,
                analysis_end=end_ts,
            )
            row, curve, costs = s738._metric_row_with_counts(
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
    comparison = _comparison(summary, cost)
    annual, monthly = s738._annual_monthly(curves)
    checks = _check_rows(summary, comparison)
    decision = _decision(comparison, checks)

    _plot(curves)
    _write_report(summary, comparison, cost, annual, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(summary[summary["window_name"].eq("full_2020_20260430")].to_string(index=False))


if __name__ == "__main__":
    main()

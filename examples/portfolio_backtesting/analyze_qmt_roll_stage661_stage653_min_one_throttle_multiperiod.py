from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as s659
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage661_stage653_min_one_throttle_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage661_stage653_min_one_throttle_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_SUMMARY_PATH = s660.SUMMARY_PATH
BASELINE_COST_PATH = s660.COST_PATH

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _install_min_one_throttle_patch() -> None:
    original = QmtRollPortfolioStrategy._calculate_entry_sizing

    def patched_calculate_entry_sizing(self: QmtRollPortfolioStrategy, *args: Any, **kwargs: Any) -> dict[str, Any]:
        sizing = dict(original(self, *args, **kwargs))
        entry_context = str(kwargs.get("entry_context", "flat_entry"))
        if entry_context != "flat_entry":
            sizing["min_one_throttle_applied"] = 0
            return sizing

        selected = int(sizing.get("selected_volume") or 0)
        contracts_by_risk = int(sizing.get("contracts_by_risk") or 0)
        contracts_by_margin = int(sizing.get("contracts_by_margin") or 0)
        contracts_by_single = int(sizing.get("contracts_by_single_trade_cap") or 0)
        cluster_max = int(sizing.get("risk_cluster_max_volume") or 0)
        risk_multiplier = float(sizing.get("risk_multiplier") or 0.0)
        margin_per_contract = float(sizing.get("margin_per_contract") or 0.0)
        limited_balance = float(sizing.get("limited_balance") or 0.0)

        can_afford_one = (
            margin_per_contract > 0.0
            and limited_balance >= margin_per_contract
            and contracts_by_margin >= 1
            and contracts_by_single >= 1
            and cluster_max >= 1
        )
        should_lift = (
            selected <= 0
            and contracts_by_risk <= 0
            and risk_multiplier <= 0.1000001
            and can_afford_one
        )
        sizing["min_one_throttle_applied"] = int(should_lift)
        sizing["min_one_throttle_selected_volume_before"] = selected
        if should_lift:
            sizing["selected_volume"] = 1
        return sizing

    QmtRollPortfolioStrategy._calculate_entry_sizing = patched_calculate_entry_sizing


def _run_latest_ytd_min_one(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily, positions, _usage, forced_events = s659._run_variant_dynamic(
        spec,
        metadata,
        datetime.strptime("2026-01-01", "%Y-%m-%d"),
        datetime.strptime("2026-06-04", "%Y-%m-%d"),
        s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve(),
    )
    daily["account_capital"] = spec.capital.account_capital
    daily["c3_capital"] = spec.capital.c3_capital
    daily["profile"] = spec.profile
    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, forced_events


def _rolling_metrics(full_curve: pd.DataFrame) -> pd.DataFrame:
    ordered = full_curve.sort_values("date").reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for holding_days in (63, 126, 252):
        returns: list[float] = []
        dds: list[float] = []
        starts: list[str] = []
        ends: list[str] = []
        for start in range(0, len(ordered) - holding_days + 1):
            window = ordered.iloc[start : start + holding_days].copy()
            equity = window["rebased_equity"].astype(float).reset_index(drop=True)
            if len(equity) < 2 or float(equity.iloc[0]) <= 0:
                continue
            ret = float((equity.iloc[-1] / equity.iloc[0] - 1.0) * 100.0)
            dd = float(s660._drawdown_pct(equity).min())
            returns.append(ret)
            dds.append(dd)
            starts.append(pd.Timestamp(window["date"].iloc[0]).date().isoformat())
            ends.append(pd.Timestamp(window["date"].iloc[-1]).date().isoformat())
        if returns:
            ret_series = pd.Series(returns)
            worst_idx = int(ret_series.idxmin())
            rows.append(
                {
                    "holding_days": holding_days,
                    "sample_count": int(len(returns)),
                    "min_return_pct": float(ret_series.min()),
                    "p05_return_pct": float(ret_series.quantile(0.05)),
                    "median_return_pct": float(ret_series.median()),
                    "positive_rate_pct": float(ret_series.gt(0.0).mean() * 100.0),
                    "min_window_dd_pct": float(min(dds)),
                    "worst_return_start": starts[worst_idx],
                    "worst_return_end": ends[worst_idx],
                }
            )
    return pd.DataFrame(rows)


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    baseline_summary = pd.read_csv(BASELINE_SUMMARY_PATH, encoding="utf-8-sig")
    baseline_cost = pd.read_csv(BASELINE_COST_PATH, encoding="utf-8-sig")
    b = baseline_summary.set_index("window_name")
    c = summary.set_index("window_name")
    rows: list[dict[str, Any]] = []
    for name in c.index:
        if name not in b.index:
            continue
        brow = b.loc[name]
        crow = c.loc[name]
        rows.append(
            {
                "window_name": name,
                "window_label": crow["window_label"],
                "baseline_return_pct": float(brow["rebased_total_return_pct"]),
                "candidate_return_pct": float(crow["rebased_total_return_pct"]),
                "delta_return_pct": float(crow["rebased_total_return_pct"] - brow["rebased_total_return_pct"]),
                "baseline_max_dd_pct": float(brow["rebased_max_dd_pct"]),
                "candidate_max_dd_pct": float(crow["rebased_max_dd_pct"]),
                "delta_max_dd_pct": float(crow["rebased_max_dd_pct"] - brow["rebased_max_dd_pct"]),
                "baseline_trades": float(brow["total_trade_count"]),
                "candidate_trades": float(crow["total_trade_count"]),
                "delta_trades": float(crow["total_trade_count"] - brow["total_trade_count"]),
                "baseline_slippage": float(brow["total_slippage"]),
                "candidate_slippage": float(crow["total_slippage"]),
                "delta_slippage": float(crow["total_slippage"] - brow["total_slippage"]),
                "baseline_margin_peak_pct": float(brow["max_broker10_margin_to_rebased_equity_pct"]),
                "candidate_margin_peak_pct": float(crow["max_broker10_margin_to_rebased_equity_pct"]),
                "delta_margin_peak_pct": float(
                    crow["max_broker10_margin_to_rebased_equity_pct"]
                    - brow["max_broker10_margin_to_rebased_equity_pct"]
                ),
            }
        )

    baseline_cost = baseline_cost[baseline_cost["cost_multiplier"].eq(2.0)].set_index("window_name")
    candidate_cost = cost[cost["cost_multiplier"].eq(2.0)].set_index("window_name")
    for row in rows:
        name = str(row["window_name"])
        if name in baseline_cost.index and name in candidate_cost.index:
            row["baseline_2x_max_dd_pct"] = float(baseline_cost.loc[name, "max_dd_pct"])
            row["candidate_2x_max_dd_pct"] = float(candidate_cost.loc[name, "max_dd_pct"])
            row["delta_2x_max_dd_pct"] = float(
                candidate_cost.loc[name, "max_dd_pct"] - baseline_cost.loc[name, "max_dd_pct"]
            )
    return pd.DataFrame(rows)


def _check_rows(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        rows.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    full = summary[summary["window_name"].eq("full_2020_20260430")].iloc[0]
    add("full_dd40", "pass" if float(full["rebased_max_dd_pct"]) >= -40.0 else "fail", float(full["rebased_max_dd_pct"]), ">= -40", "全周期正常成本最大回撤。")
    add("full_margin100", "pass" if int(full["days_over_100pct"]) == 0 else "fail", float(full["days_over_100pct"]), "0 days", "全周期 broker10 保证金不穿100%。")
    c2 = cost[(cost["window_name"].eq("full_2020_20260430")) & (cost["cost_multiplier"].eq(2.0))].iloc[0]
    add("full_2x_cost_dd40", "pass" if float(c2["max_dd_pct"]) >= -40.0 else "fail", float(c2["max_dd_pct"]), ">= -40", "全周期2x成本压力最大回撤。")
    s2022 = summary[summary["window_name"].eq("since_2022")].iloc[0]
    add("since_2022_return_positive", "pass" if float(s2022["rebased_total_return_pct"]) > 0 else "fail", float(s2022["rebased_total_return_pct"]), "> 0", "用户关注的2022冷启动是否修复。")
    s2021 = summary[summary["window_name"].eq("since_2021")].iloc[0]
    add("since_2021_dd40", "pass" if float(s2021["rebased_max_dd_pct"]) >= -40.0 else "fail", float(s2021["rebased_max_dd_pct"]), ">= -40", "2021起点最大回撤。")
    if not comparison.empty:
        full_cmp = comparison[comparison["window_name"].eq("full_2020_20260430")].iloc[0]
        status = "pass" if float(full_cmp["delta_max_dd_pct"]) >= -2.0 else "fail"
        add("full_dd_not_materially_worse_vs_baseline", status, float(full_cmp["delta_max_dd_pct"]), ">= -2pp", "候选不能显著恶化全周期回撤。")
    if not rolling.empty:
        p05_min = float(rolling["p05_return_pct"].min())
        add("rolling_p05_watch", "pass" if p05_min >= 0.0 else "watch", p05_min, ">= 0 preferred", "任意启动短周期左尾。")
    return pd.DataFrame(rows)


def _plot_report(summary: pd.DataFrame, curves: pd.DataFrame, comparison: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), dpi=160)
    ax_nav, ax_dd, ax_cmp, ax_margin = axes.flatten()

    full = curves[curves["window_name"].eq("full_2020_20260430")].sort_values("date")
    ax_nav.plot(pd.to_datetime(full["date"]), full["rebased_nav"], color="#1f77b4", linewidth=1.3)
    ax_nav.set_title("Candidate full-period NAV")
    ax_nav.grid(alpha=0.25)

    ax_dd.fill_between(pd.to_datetime(full["date"]), full["drawdown_pct"].astype(float), 0.0, color="#d62728", alpha=0.35)
    ax_dd.set_title("Candidate full-period drawdown")
    ax_dd.grid(alpha=0.25)

    start_windows = summary[summary["window_group"].eq("start_year")].copy()
    ax_cmp.bar(start_windows["window_name"], start_windows["rebased_total_return_pct"].astype(float), color="#2ca02c")
    ax_cmp.axhline(0.0, color="#333333", linewidth=0.8)
    ax_cmp.set_title("Start-window total return")
    ax_cmp.tick_params(axis="x", rotation=35)
    ax_cmp.grid(axis="y", alpha=0.25)

    ax_margin.plot(pd.to_datetime(full["date"]), full["broker10_margin_to_rebased_equity_pct"], color="#ff7f0e", linewidth=1.1)
    ax_margin.axhline(90.0, color="#d62728", linestyle="--", linewidth=0.8)
    ax_margin.axhline(100.0, color="#8c0000", linestyle="--", linewidth=0.8)
    ax_margin.set_title("Broker10 margin / equity")
    ax_margin.grid(alpha=0.25)

    fig.suptitle("Stage661 Stage653 Min-One Throttle Multiperiod Candidate", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    comparison: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage661 Stage653 最少1手降风险修复多周期审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        "- 候选假设：当连续亏损把风险倍率压到0.1且信号/过滤/保证金仍允许至少1手时，将 `selected_volume=0` 提升为 `1`，避免小账户冷启动后永久熄火。",
        "- 本阶段不修改官方实盘配置、不连接 CTP、不调用下单。",
        "",
        "## 决策检查",
        "",
        _md_table(checks),
        "",
        "## 候选多周期结果",
        "",
        _md_table(
            summary[
                [
                    "window_name",
                    "window_label",
                    "analysis_start",
                    "analysis_end",
                    "rebased_end_equity",
                    "rebased_total_return_pct",
                    "rebased_cagr_pct",
                    "rebased_max_dd_pct",
                    "rebased_sharpe",
                    "max_broker10_margin_to_rebased_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "deployable_pass",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## A/C 对比",
        "",
        _md_table(comparison, max_rows=80),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=120),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 硬失败项：`{', '.join(decision['hard_fail_checks']) or '无'}`。",
        f"- 观察项：`{', '.join(decision['watch_checks']) or '无'}`。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _install_min_one_throttle_patch()

    metadata = s513._metadata()
    spec = s660._official_spec(metadata)

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    cost_rows: list[dict[str, Any]] = []
    annual_source_daily: pd.DataFrame | None = None
    all_forced_events: list[pd.DataFrame] = []

    for window_name, window_label, group, start, end in s660.WINDOWS:
        analysis_start = pd.Timestamp(start)
        analysis_end = pd.Timestamp(end) if end else pd.Timestamp("2026-04-30")
        print(f"[stage661] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)
        frame, forced_events = s660._run_independent_window(
            spec=spec,
            metadata=metadata,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
        if window_name == "full_2020_20260430":
            annual_source_daily = frame.copy()
        if not forced_events.empty:
            forced_events["window_name"] = window_name
            all_forced_events.append(forced_events)
        row, curve, costs = s660._window_metrics(
            frame,
            window_name=window_name,
            window_label=window_label,
            group=group,
            source_name="stage653_min_one_throttle_independent_window",
            caveat="历史窗口独立重跑，20万 fresh capital；风险倍率0.1导致0手时，若保证金/过滤允许则最少1手。",
            forced_events=forced_events,
        )
        summary_rows.append(row)
        curve_frames.append(curve)
        cost_rows.extend(costs)

    ytd_frame, ytd_forced = _run_latest_ytd_min_one(spec=spec, metadata=metadata)
    ytd_row, ytd_curve, ytd_costs = s660._window_metrics(
        ytd_frame,
        window_name="ytd_2026_latest_ai_min_one",
        window_label="2026年初至2026-06-04最新AI池最少1手候选",
        group="latest_ytd",
        source_name="stage653_min_one_throttle_latest_ai_ytd",
        caveat="最新 AI 池独立年初至今影子盘；同样应用最少1手降风险修复。",
        forced_events=ytd_forced,
    )
    summary_rows.append(ytd_row)
    curve_frames.append(ytd_curve)
    cost_rows.extend(ytd_costs)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    if annual_source_daily is None:
        raise RuntimeError("full window daily not generated")
    annual, monthly = s660._annual_monthly(annual_source_daily, "stage653_min_one_throttle_full_path")
    rolling = _rolling_metrics(curves[curves["window_name"].eq("full_2020_20260430")])
    comparison = _comparison(summary, cost)
    checks = _check_rows(summary, cost, comparison, rolling)
    hard_fail_checks = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch_checks = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision_label = (
        "stage653_min_one_throttle_candidate_rejected"
        if hard_fail_checks
        else "stage653_min_one_throttle_candidate_watch_pass"
    )
    decision = {
        "stage": "Stage371",
        "script_stage": "Stage661",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline": "A=Stage653 official_live_stage653_20w_force95_to80",
        "candidate": "C=Stage653 + min-one when risk_multiplier<=0.1 and risk sizing returns zero while margin allows one contract",
        "decision": decision_label,
        "hard_fail_checks": hard_fail_checks,
        "watch_checks": watch_checks,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "curves": str(CURVES_PATH),
            "rolling": str(ROLLING_PATH),
            "comparison": str(COMPARISON_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }

    _plot_report(summary, curves, comparison)
    _write_report(summary, cost, rolling, comparison, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage738_postentry_quality_add_real_ac_v1"
OUTPUT_PREFIX = "qmt_roll_stage738_postentry_quality_add_real_ac"
LINE_ID = "futures_trend_winner_trade_forensics"

BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
CANDIDATES: tuple[dict[str, str], ...] = (
    {
        "variant": "stage526_200k_force95_to80_post1_body60_qadd05_stage738",
        "label": "C1 post1 body60 ratio >=50 qadd0.5",
        "feature": "post1_body60_ratio_ge50",
    },
    {
        "variant": "stage526_200k_force95_to80_post1_directional_close_strength_qadd05_stage738",
        "label": "C2 post1 directional close strength >=60 qadd0.5",
        "feature": "post1_avg_directional_close_strength_ge60",
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
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

POST_COUNT_COLUMNS = [
    "post_entry_quality_add_signal_count",
    "post_entry_quality_add_zero_volume_count",
    "post_entry_quality_add_count",
]


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _candidate_spec(metadata: dict[str, Any], candidate: dict[str, str]) -> s653.ForcedVariant:
    base = s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=candidate["variant"],
        label=candidate["label"],
        note=(
            "Official Stage372 unchanged; add one post-entry quality confirmation layer only after the first "
            "new daily bar confirms the predeclared candle-quality feature. Confirmation volume is "
            "floor(base_volume * 0.5), so sub-one-contract adds are not force-rounded."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_post_entry_quality_add": True,
        "post_entry_quality_add_feature": candidate["feature"],
        "post_entry_quality_add_volume_multiplier": 0.5,
        "post_entry_quality_add_max_layers": 1,
        "post_entry_quality_add_use_day_extreme_stop": True,
        "post_entry_quality_add_triggers_add_profit_lock": True,
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
        profile=f"official_stage372_post_entry_quality_add_{candidate['feature']}_stage738",
    )


def _run_independent_window(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    try:
        s653.s517.START_DT = analysis_start.to_pydatetime()
        s653.s517.END_DT = analysis_end.to_pydatetime()

        s653.s517.assert_stage196_database_sentinels()
        s653.s517.s506._patch_stage506_raw_roots()
        c3_overrides = s513._c3_overrides(s653.s517.START_DT)
        preload_start = max(s653.s517.PRELOAD_START_DT, s653.s517.START_DT - timedelta(days=365))
        _, open_map = s653.s517.s506.s501._seed_proxy_maps()
        engine = s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s653.s517.Interval.DAILY,
            start=preload_start,
            end=s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s653.s517.build_roll_setting(
            metadata["margin_ratios"],
            risk_ratio=s653.s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
            strategy_overrides=c3_overrides,
        )
        setting["capital_base"] = spec.capital.c3_capital
        setting.update(spec.overrides)
        engine.add_strategy(QmtRollPortfolioStrategy, setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end

    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty daily result: {spec.capital.variant}")

    daily = daily_df.copy()
    daily = daily.loc[
        (daily.index >= analysis_start.date()) & (daily.index <= analysis_end.date())
    ].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["c3_equity"] = spec.capital.c3_capital + daily["net_pnl"].cumsum()
    daily["variant"] = spec.capital.variant
    daily["combo_variant"] = spec.capital.variant
    daily["label"] = spec.capital.label
    daily["risk_multiplier"] = spec.capital.risk_multiplier
    daily["note"] = spec.capital.note
    daily["profile"] = spec.profile

    strategy = getattr(engine, "strategy", None)
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
        *POST_COUNT_COLUMNS,
    ]:
        daily[column] = getattr(strategy, column, 0) if strategy else 0

    positions = s653.s517.build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.capital.variant}")
    positions["variant"] = spec.capital.variant
    positions["combo_variant"] = spec.capital.variant
    positions["label"] = spec.capital.label
    positions["risk_multiplier"] = spec.capital.risk_multiplier
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
        *POST_COUNT_COLUMNS,
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0

    forced_events = pd.DataFrame(getattr(strategy, "forced_margin_deleverage_events", []) if strategy else [])
    if not forced_events.empty:
        forced_events["variant"] = spec.capital.variant
        forced_events["label"] = spec.capital.label
        forced_events["profile"] = spec.profile

    entry_risk = pd.DataFrame(getattr(strategy, "entry_risk_diagnostics", []) if strategy else [])
    if not entry_risk.empty:
        entry_risk["variant"] = spec.capital.variant
        entry_risk["label"] = spec.capital.label
        entry_risk["profile"] = spec.profile
    return combined, forced_events, entry_risk


def _metric_row_with_counts(
    frame: pd.DataFrame,
    *,
    spec: s653.ForcedVariant,
    window_name: str,
    window_label: str,
    window_group: str,
    forced_events: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    row, curve, costs = s707._metric_row(
        frame,
        spec=spec,
        window_name=window_name,
        window_label=window_label,
        window_group=window_group,
        forced_events=forced_events,
    )
    for column in POST_COUNT_COLUMNS:
        row[column] = int(pd.to_numeric(frame.get(column, 0), errors="coerce").fillna(0).iloc[0])
    return row, curve, costs


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
        "forced_margin_deleverage_closed_volume",
        *POST_COUNT_COLUMNS,
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
            row = {
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
                    row[f"candidate_{multiplier:.0f}x_deployable_pass"] = int(ccost["deployable_pass"].iloc[0])
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

        add(candidate, "full_end_equity_delta_gt0", "pass" if float(full["delta_end_equity"]) > 0 else "fail", float(full["delta_end_equity"]), "> 0", "真实引擎全周期必须比正式版多赚钱。")
        add(candidate, "full_dd_not_worse_3pp", "pass" if float(full["delta_max_dd_pct"]) >= -3.0 else "fail", float(full["delta_max_dd_pct"]), ">= -3pp", "确认仓是收益增强，不应显著放大回撤。")
        add(candidate, "full_sharpe_not_worse_005", "pass" if float(full["delta_sharpe"]) >= -0.05 else "fail", float(full["delta_sharpe"]), ">= -0.05", "额外交易不能明显降低单位波动收益。")
        add(candidate, "full_trade_count_le135pct", "pass" if float(full["candidate_total_trade_count"]) <= float(full["base_total_trade_count"]) * 1.35 else "fail", float(full["candidate_total_trade_count"] / max(float(full["base_total_trade_count"]), 1.0) * 100.0), "<= 135%", "确认仓会增加交易，但不能把系统变成换手策略。")
        add(candidate, "full_slippage_le135pct", "pass" if float(full["candidate_total_slippage"]) <= float(full["base_total_slippage"]) * 1.35 else "fail", float(full["candidate_total_slippage"] / max(float(full["base_total_slippage"]), 1.0) * 100.0), "<= 135%", "真实成本压力必须可控。")
        add(candidate, "full_broker10_100_pass", "pass" if int(cand_summary["broker10_100_pass"]) == 1 else "fail", float(full["candidate_max_broker10_margin_to_equity_pct"]), "<= 100%", "不能用保证金打穿换收益。")
        add(candidate, "cost2_dd_not_worse_5pp", "pass" if float(full.get("delta_2x_max_dd_pct", -999.0)) >= -5.0 else "fail", float(full.get("delta_2x_max_dd_pct", float("nan"))), ">= -5pp", "2x成本压力下不能明显脆弱化。")
        add(candidate, "start_year_min_retention_ge70", "pass" if float(start_years["return_retention_pct"].min()) >= 70.0 else "fail", float(start_years["return_retention_pct"].min()), ">= 70%", "多起点不能只靠早期复利。")
        add(candidate, "start_year_min_dd_delta_ge_minus5", "pass" if float(start_years["delta_max_dd_pct"].min()) >= -5.0 else "fail", float(start_years["delta_max_dd_pct"].min()), ">= -5pp", "年度冷启动回撤不能明显恶化。")
        add(candidate, "phase_min_dd_delta_ge_minus5", "pass" if float(phases["delta_max_dd_pct"].min()) >= -5.0 else "fail", float(phases["delta_max_dd_pct"].min()), ">= -5pp", "阶段冷启动回撤不能明显恶化。")
        add(candidate, "post_quality_add_count_gt0", "pass" if float(full["candidate_post_entry_quality_add_count"]) > 0 else "fail", float(full["candidate_post_entry_quality_add_count"]), "> 0", "若真实整数手完全不能成交，overlay优势不可执行。")
        signal_count = float(full["candidate_post_entry_quality_add_signal_count"])
        add(candidate, "zero_volume_signal_share_watch", "watch", float(full["candidate_post_entry_quality_add_zero_volume_count"] / max(signal_count, 1.0) * 100.0), "watch", "特征通过后被整数手挡住的比例，用于判断代理失真程度。")
    return pd.DataFrame(checks)


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
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
        decision = "next_validation_candidate" if not hard_fails else "not_promoted"
        reason = "all_predeclared_hard_gates_pass" if not hard_fails else "failed: " + ",".join(hard_fails)
        decisions.append(
            {
                "candidate_variant": candidate,
                "candidate_label": str(row["candidate_label"]),
                "decision": decision,
                "reason": reason,
                "full_end_equity": float(row["candidate_end_equity"]),
                "full_end_equity_delta": float(row["delta_end_equity"]),
                "full_total_return_pct": float(row["candidate_total_return_pct"]),
                "full_max_dd_pct": float(row["candidate_max_dd_pct"]),
                "full_delta_max_dd_pct": float(row["delta_max_dd_pct"]),
                "full_sharpe": float(row["candidate_sharpe"]),
                "post_quality_add_count": float(row["candidate_post_entry_quality_add_count"]),
                "post_quality_signal_count": float(row["candidate_post_entry_quality_add_signal_count"]),
                "post_quality_zero_volume_count": float(row["candidate_post_entry_quality_add_zero_volume_count"]),
            }
        )
    best = sorted(decisions, key=lambda item: float(item.get("full_end_equity", -1.0)), reverse=True)[0]
    return {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "baseline": BASE_VARIANT,
        "candidate_decisions": decisions,
        "best_by_full_equity": best,
        "overall_decision": (
            "has_next_validation_candidate"
            if any(item["decision"] == "next_validation_candidate" for item in decisions)
            else "no_promotion"
        ),
        "chart_path": str(CHART_PATH),
        "report_path": str(REPORT_PATH),
    }


def _annual_monthly(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return s707._annual_monthly(curves)


def _plot(curves: pd.DataFrame) -> None:
    full_windows = ["full_2020_20260430", "since_2022", "phase_2024_2025"]
    labels = {
        BASE_VARIANT: "A official",
        CANDIDATES[0]["variant"]: "C1 body60 qadd0.5",
        CANDIDATES[1]["variant"]: "C2 dirclose qadd0.5",
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
            ax.plot(data["date"], data["account_equity"], label=labels.get(variant, variant), linewidth=1.8, color=colors.get(variant))
        ax.axhline(OFFICIAL_LIVE_CAPITAL, color="#9ca3af", linestyle="--", linewidth=1.0)
        ax.set_title(window_name)
        ax.set_ylabel("Account equity")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left")
    axes[-1].set_xlabel("Date")
    fig.suptitle("Stage738 Real A/C: official vs post-entry quality confirmation add", fontsize=16)
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
        *POST_COUNT_COLUMNS,
    ]
    full_summary = summary[summary["window_name"].eq("full_2020_20260430")][full_cols].copy()
    comp_cols = [
        "candidate_variant",
        "window_name",
        "return_retention_pct",
        "delta_end_equity",
        "delta_max_dd_pct",
        "delta_sharpe",
        "candidate_post_entry_quality_add_count",
        "candidate_post_entry_quality_add_signal_count",
        "candidate_post_entry_quality_add_zero_volume_count",
    ]
    text = [
        f"# Stage738 入场后质量确认仓真实 A/C",
        "",
        f"- 生成时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 研究线：`{LINE_ID}`",
        f"- 基准：`{BASE_VARIANT}`",
        "- 候选：C1 `post1_body60_ratio_ge50`，C2 `post1_avg_directional_close_strength_ge60`，确认仓手数 `floor(base_volume * 0.5)`。",
        "- 运行前反过拟合判断：不是按红框救参，属于趋势跟随中的确认后加小仓；但仍需真实整数手、保证金、成本和多起点验证。",
        "",
        "## 全周期结果",
        "",
        _md_table(full_summary, max_rows=10),
        "",
        "## 多起点对照",
        "",
        _md_table(comparison[comp_cols], max_rows=40),
        "",
        "## 成本压力",
        "",
        _md_table(cost[cost["window_name"].eq("full_2020_20260430")], max_rows=12),
        "",
        "## 年度结果",
        "",
        _md_table(annual, max_rows=30),
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
    ]
    REPORT_PATH.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    base_spec = s660._official_spec(metadata)
    specs = [base_spec] + [_candidate_spec(metadata, item) for item in CANDIDATES]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    for window_name, window_label, window_group, start, end in s707.WINDOWS:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        for spec in specs:
            print(f"[stage738] running {window_name} {spec.capital.variant}", flush=True)
            frame, forced_events, entry_risk = _run_independent_window(
                spec=spec,
                metadata=metadata,
                analysis_start=start_ts,
                analysis_end=end_ts,
            )
            if not entry_risk.empty:
                entry_risk["window_name"] = window_name
                entry_risk_frames.append(entry_risk)
            row, curve, costs = _metric_row_with_counts(
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
    annual, monthly = _annual_monthly(curves)
    checks = _check_rows(summary, comparison)
    decision = _decision(summary, comparison, checks)

    _plot(curves)
    _write_report(summary, comparison, cost, annual, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    if entry_risk_frames:
        pd.concat(entry_risk_frames, ignore_index=True, sort=False).to_csv(
            ENTRY_RISK_PATH,
            index=False,
            encoding="utf-8-sig",
        )
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

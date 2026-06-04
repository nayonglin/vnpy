from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650  # noqa: E402
import analyze_qmt_roll_stage651_stage526_200k_dynamic_margin_gate as s651  # noqa: E402


MODEL_TAG = "stage652_stage526_200k_capital_participation_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage652_stage526_200k_capital_participation_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_200K = 200_000.0
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
BASELINE_VARIANT = "stage526_200k_allin_r080_pc25_maxpos4"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_days_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
SIZING_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sizing_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _product_cap_base(identity_map: str, product_cap_ratio: float, maxpos: int) -> dict[str, Any]:
    return {
        **s519._product_cap_overrides(product_cap_ratio, identity_map),
        "max_concurrent_positions": int(maxpos),
    }


def _profit_participation_overrides(
    identity_map: str,
    participation: float,
    max_cap: float,
) -> dict[str, Any]:
    return {
        **_product_cap_base(identity_map, 0.25, 4),
        "enable_dynamic_sizing_equity_soft_cap": True,
        "dynamic_sizing_equity_soft_cap_base": ACCOUNT_200K,
        "dynamic_sizing_equity_soft_cap_max": float(max_cap),
        "dynamic_sizing_equity_soft_cap_participation": float(participation),
        # Disable the release-weight leg for this clean capital-participation test.
        "dynamic_sizing_equity_soft_cap_margin_start_ratio": 10.0,
        "dynamic_sizing_equity_soft_cap_margin_full_ratio": 11.0,
        "dynamic_sizing_equity_soft_cap_drawdown_start_ratio": 10.0,
        "dynamic_sizing_equity_soft_cap_drawdown_full_ratio": 11.0,
    }


def _capital(
    variant: str,
    label: str,
    risk_multiplier: float,
    product_cap_ratio: float,
    maxpos: int,
    note: str,
) -> s650.CapitalVariant:
    return s650.CapitalVariant(
        variant=variant,
        label=label,
        account_capital=ACCOUNT_200K,
        c3_capital=ACCOUNT_200K,
        risk_multiplier=float(risk_multiplier),
        product_cap_ratio=float(product_cap_ratio),
        max_concurrent_positions=int(maxpos),
        note=note,
    )


def _variants(identity_map: str) -> list[s651.DynamicVariant]:
    return [
        s651.DynamicVariant(
            capital=_capital(
                BASELINE_VARIANT,
                "20w all-in Stage526 core r080 pc25 maxpos4",
                0.80,
                0.25,
                4,
                "Stage350/351 原版 20万 all-in 对照；默认 sizing 随盈利参与到策略上限。",
            ),
            overrides=_product_cap_base(identity_map, 0.25, 4),
            profile="baseline_profit_reinvest",
        ),
        s651.DynamicVariant(
            capital=_capital(
                "stage526_200k_no_reinvest_cap200k_r080_pc25_maxpos4",
                "20w Stage526 no reinvest cap200k r080 pc25 maxpos4",
                0.80,
                0.25,
                4,
                "固定 sizing_equity_cap=20万；盈利不再参与后续开仓 sizing。",
            ),
            overrides={
                **_product_cap_base(identity_map, 0.25, 4),
                "sizing_equity_cap": ACCOUNT_200K,
            },
            profile="no_profit_reinvest_cap200k",
        ),
        s651.DynamicVariant(
            capital=_capital(
                "stage526_200k_profit25_cap500k_r080_pc25_maxpos4",
                "20w Stage526 profit25 cap500k r080 pc25 maxpos4",
                0.80,
                0.25,
                4,
                "盈利部分25%参与后续 sizing，最高按50万 sizing；不启用保证金/回撤 release-weight。",
            ),
            overrides=_profit_participation_overrides(identity_map, 0.25, 500_000.0),
            profile="profit_participation25_cap500k",
        ),
        s651.DynamicVariant(
            capital=_capital(
                "stage526_200k_profit50_cap500k_r080_pc25_maxpos4",
                "20w Stage526 profit50 cap500k r080 pc25 maxpos4",
                0.80,
                0.25,
                4,
                "盈利部分50%参与后续 sizing，最高按50万 sizing；作为粗档中间风险口径。",
            ),
            overrides=_profit_participation_overrides(identity_map, 0.50, 500_000.0),
            profile="profit_participation50_cap500k",
        ),
        s651.DynamicVariant(
            capital=_capital(
                "stage526_200k_defensive_r050_pc25_maxpos2",
                "20w defensive probe r050 pc25 maxpos2",
                0.50,
                0.25,
                2,
                "Stage350 防守探针复验；降低风险倍率并限制最多2个同时持仓品种。",
            ),
            overrides=_product_cap_base(identity_map, 0.25, 2),
            profile="defensive_r050_maxpos2",
        ),
    ]


def _sizing_summary(spec: s651.DynamicVariant, candidates: pd.DataFrame) -> dict[str, Any]:
    row: dict[str, Any] = {
        "variant": spec.capital.variant,
        "label": spec.capital.label,
        "profile": spec.profile,
        "candidate_count": 0,
        "opened_candidate_count": 0,
        "dynamic_enabled_count": 0,
        "median_effective_sizing_cap": 0.0,
        "max_effective_sizing_cap": 0.0,
        "max_dynamic_raw_cap": 0.0,
        "min_release_weight": 0.0,
        "median_selected_volume": 0.0,
        "max_selected_volume": 0.0,
    }
    if candidates.empty:
        return row

    frame = candidates.copy()
    for column in [
        "effective_sizing_equity_cap",
        "dynamic_sizing_equity_soft_cap_enabled",
        "dynamic_sizing_equity_soft_cap_raw_cap",
        "dynamic_sizing_equity_soft_cap_release_weight",
        "selected_volume",
    ]:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    row.update(
        {
            "candidate_count": int(len(frame)),
            "opened_candidate_count": int(frame["candidate_status"].astype(str).eq("opened").sum())
            if "candidate_status" in frame.columns
            else 0,
            "dynamic_enabled_count": int(frame["dynamic_sizing_equity_soft_cap_enabled"].gt(0).sum()),
            "median_effective_sizing_cap": float(frame["effective_sizing_equity_cap"].median()),
            "max_effective_sizing_cap": float(frame["effective_sizing_equity_cap"].max()),
            "max_dynamic_raw_cap": float(frame["dynamic_sizing_equity_soft_cap_raw_cap"].max()),
            "min_release_weight": float(frame["dynamic_sizing_equity_soft_cap_release_weight"].min()),
            "median_selected_volume": float(frame["selected_volume"].median()),
            "max_selected_volume": float(frame["selected_volume"].max()),
        }
    )
    return row


def _metrics_with_profile(frame: pd.DataFrame, spec: s651.DynamicVariant, cost_multiplier: float) -> dict[str, Any]:
    row = s650._metrics(frame, spec.capital, cost_multiplier)
    row["profile"] = spec.profile
    return row


def _add_retention(summary: pd.DataFrame, cost: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)]
    baseline_return = float(baseline["total_return_pct"].iloc[0]) if not baseline.empty else math.nan
    for frame in [summary, cost]:
        if baseline_return and not math.isnan(baseline_return):
            frame["return_retention_vs_20w_baseline_pct"] = (
                frame["total_return_pct"].astype(float) / baseline_return * 100.0
            )
        else:
            frame["return_retention_vs_20w_baseline_pct"] = 0.0
    return summary, cost


def _decision(summary: pd.DataFrame, cost: pd.DataFrame) -> dict[str, Any]:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    rows: list[dict[str, Any]] = []
    for item in summary.to_dict(orient="records"):
        variant = str(item["variant"])
        cost2_row = cost2.loc[variant].to_dict() if variant in cost2.index else {}
        hard_pass = int(
            int(item.get("deployable_pass", 0) or 0) == 1
            and float(cost2_row.get("max_dd_pct", -999.0)) >= -40.0
            and int(cost2_row.get("account_survival_pass", 0) or 0) == 1
        )
        ranked_item = dict(item)
        ranked_item["cost2_dd40_pass"] = int(float(cost2_row.get("max_dd_pct", -999.0)) >= -40.0)
        ranked_item["cost2_survival_pass"] = int(cost2_row.get("account_survival_pass", 0) or 0)
        ranked_item["hard_pass"] = hard_pass
        rows.append(ranked_item)

    ranked = sorted(
        rows,
        key=lambda row: (
            int(row["variant"] != BASELINE_VARIANT),
            int(row["hard_pass"]),
            float(row["total_return_pct"]),
        ),
        reverse=True,
    )
    non_baseline_hard = [
        row for row in ranked if row["variant"] != BASELINE_VARIANT and int(row["hard_pass"]) == 1
    ]
    best = non_baseline_hard[0] if non_baseline_hard else (ranked[0] if ranked else {})
    label = (
        "stage526_200k_capital_participation_hard_pass"
        if non_baseline_hard
        else "stage526_200k_capital_participation_not_ready"
    )
    return {
        "stage": "Stage352",
        "script_stage": "Stage652",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "best_variant": best,
        "ranked_variants": ranked,
        "pass_definition": (
            "1x: account equity > 0, max drawdown >= -40%, broker10 margin/equity <= 100%; "
            "2x cost: max drawdown >= -40% and account equity > 0."
        ),
    }


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    events: pd.DataFrame,
    sizing_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    result_view = summary.sort_values(["hard_pass", "total_return_pct"], ascending=[False, False])
    cost_view = cost.sort_values(["variant", "cost_multiplier"])
    lines = [
        "# Stage652 Stage526 20万资本参与率边界",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：部署资金层 A/C；不改 Stage526 alpha，不连接 CTP，不调用下单。",
        "- A：`stage526_200k_allin_r080_pc25_maxpos4`。",
        "- C：同一信号叠加固定资本参与机制：不复投、盈利25%/50%参与、以及防守风险口径。",
        "- 候选假设：20万原版失败不是因为开仓日预算不足，而是盈利复投后风险预算放大；限制盈利参与应降低次日路径保证金风险。",
        "- 运行前过拟合判断：否。测试的是粗粒度资金参与结构，不按日期、品种或小数保证金阈值救援。",
        "- 运行前继续价值判断：是。用户真实资金改为20万，必须找能先通过保证金/回撤基础闸门的可执行资金口径。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py PortfolioStrategy 可承载多合约组合策略，但实盘前需要确认合约列表、策略参数和运行状态。",
        "- vn.py RiskManager 属于委托发出前风控，能限制单笔量、委托流控、活动委托和撤单等；但账户级保证金路径仍应在策略 sizing 层先控制。",
        "- 因此本阶段不继续调开仓保证金小数，而是测试资本参与率这种更稳定的资金层规则。",
        "",
        "## 预声明通过标准",
        "",
        "- 正常成本：账户权益始终大于0，最大回撤 `>= -40%`。",
        "- 正常成本：broker10 保证金/权益全程 `<= 100%`。",
        "- 2x 成本：账户权益始终大于0，最大回撤 `>= -40%`。",
        "",
        "## 核心结果",
        "",
        _md_table(
            result_view[
                [
                    "variant",
                    "profile",
                    "end_equity",
                    "total_return_pct",
                    "return_retention_vs_20w_baseline_pct",
                    "cagr_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "hard_pass",
                ]
            ]
        ),
        "",
        "## Sizing 诊断",
        "",
        _md_table(sizing_summary),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost_view[
                [
                    "variant",
                    "cost_multiplier",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "deployable_pass",
                ]
            ],
            max_rows=60,
        ),
        "",
        "## 63/126/252日任意启动体验",
        "",
        _md_table(
            rolling[
                [
                    "variant",
                    "holding_days",
                    "p05_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ],
            max_rows=90,
        ),
        "",
        "## 关键风险日",
        "",
        _md_table(events, max_rows=60),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最优候选：`{decision.get('best_variant', {}).get('variant', '')}`。",
        "- 若只有防守版通过，说明 20万实盘需要承认它已经不是原 Stage526 风险口径；后续应按独立小资金候选补冷启动、成本、保证金和 live TCA。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    identity_map = s519._product_identity_cluster_map(metadata)
    specs = _variants(identity_map)

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []
    sizing_rows: list[dict[str, Any]] = []

    for spec in specs:
        print(f"[stage652] running {spec.capital.variant}", flush=True)
        daily, positions, usage, candidates, _ = s651._run_variant(spec, metadata)
        daily["account_capital"] = spec.capital.account_capital
        daily["c3_capital"] = spec.capital.c3_capital
        positions["account_capital"] = spec.capital.account_capital
        positions["c3_capital"] = spec.capital.c3_capital
        c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
        combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
        combined["profile"] = spec.profile

        daily_frames.append(combined)
        position_frames.append(positions)
        product_frames.append(product_margin)
        sizing_rows.append(_sizing_summary(spec, candidates))
        if not usage.empty:
            usage["account_capital"] = spec.capital.account_capital
            usage["c3_capital"] = spec.capital.c3_capital
            usage_frames.append(usage)
        if not candidates.empty:
            candidates["profile"] = spec.profile
            candidate_frames.append(candidates)

    combo_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    product_margin_all = pd.concat(product_frames, ignore_index=True, sort=False)
    usage_all = pd.concat(usage_frames, ignore_index=True, sort=False) if usage_frames else pd.DataFrame()
    candidates_all = (
        pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    )
    sizing_summary = pd.DataFrame(sizing_rows)

    spec_map = {spec.capital.variant: spec for spec in specs}
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        for cost_multiplier in COST_MULTIPLIERS:
            row = _metrics_with_profile(frame, spec, cost_multiplier)
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    summary, cost = _add_retention(summary, cost)
    decision = _decision(summary, cost)

    hard_map = {row["variant"]: row for row in decision["ranked_variants"]}
    summary["hard_pass"] = summary["variant"].map(lambda variant: int(hard_map.get(variant, {}).get("hard_pass", 0)))
    cost["hard_pass"] = cost["variant"].map(lambda variant: int(hard_map.get(variant, {}).get("hard_pass", 0)))

    rolling = s650._rolling_holding(combo_daily)
    events = s650._event_days(combo_daily, product_margin_all)
    original_chart_path = s650.CHART_PATH
    try:
        s650.CHART_PATH = CHART_PATH
        s650._plot(combo_daily, summary)
    finally:
        s650.CHART_PATH = original_chart_path
    _write_report(summary, cost, rolling, events, sizing_summary, decision)

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin_all.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    if not usage_all.empty:
        usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    if not candidates_all.empty:
        candidates_all.to_csv(CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    sizing_summary.to_csv(SIZING_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

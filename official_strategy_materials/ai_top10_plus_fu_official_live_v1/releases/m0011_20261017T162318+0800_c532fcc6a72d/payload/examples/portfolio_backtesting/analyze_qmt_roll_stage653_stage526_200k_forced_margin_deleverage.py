from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402


MODEL_TAG = "stage653_stage526_200k_forced_margin_deleverage_v1"
OUTPUT_PREFIX = "qmt_roll_stage653_stage526_200k_forced_margin_deleverage"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_200K = 200_000.0
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
BASELINE_VARIANT = "stage526_200k_allin_r080_pc25_maxpos4"
# The strategy runtime margin estimator peaks at 81.28% while the exact broker10
# audit peaks at 120.10% for the same all-in path. Live deployment should use
# broker account margin directly; this multiplier aligns the backtest trigger
# with the exact margin audit used for pass/fail.
FORCED_MARGIN_BACKTEST_BROKER_MULTIPLIER = 1.65

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_days_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
FORCED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
FORCED_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class ForcedVariant:
    capital: s650.CapitalVariant
    overrides: dict[str, Any]
    profile: str


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _product_cap_base(identity_map: str) -> dict[str, Any]:
    return {
        **s519._product_cap_overrides(0.25, identity_map),
        "max_concurrent_positions": 4,
    }


def _forced_overrides(identity_map: str, trigger: float, target: float) -> dict[str, Any]:
    return {
        **_product_cap_base(identity_map),
        "enable_forced_margin_deleverage": True,
        "forced_margin_deleverage_trigger_ratio": float(trigger),
        "forced_margin_deleverage_target_ratio": float(target),
        "forced_margin_deleverage_broker_multiplier": FORCED_MARGIN_BACKTEST_BROKER_MULTIPLIER,
        "forced_margin_deleverage_priority": "largest_margin",
        "forced_margin_deleverage_max_reductions_per_day": 100,
    }


def _capital(variant: str, label: str, note: str) -> s650.CapitalVariant:
    return s650.CapitalVariant(
        variant=variant,
        label=label,
        account_capital=ACCOUNT_200K,
        c3_capital=ACCOUNT_200K,
        risk_multiplier=0.80,
        product_cap_ratio=0.25,
        max_concurrent_positions=4,
        note=note,
    )


def _variants(identity_map: str) -> list[ForcedVariant]:
    return [
        ForcedVariant(
            capital=_capital(
                BASELINE_VARIANT,
                "20w all-in Stage526 core r080 pc25 maxpos4",
                "Stage350/351/352 原版 20万 all-in 对照；不启用强制减仓。",
            ),
            overrides=_product_cap_base(identity_map),
            profile="baseline_no_forced_deleverage",
        ),
        ForcedVariant(
            capital=_capital(
                "stage526_200k_force100_to85_largest_margin_r080_pc25_maxpos4",
                "20w Stage526 force broker10 100%->85% largest margin",
                "broker10 保证金/权益超过100%后，按最大保证金占用品种逐手减到85%。",
            ),
            overrides=_forced_overrides(identity_map, 1.00, 0.85),
            profile="forced_margin_100_to_85_largest_margin",
        ),
        ForcedVariant(
            capital=_capital(
                "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4",
                "20w Stage526 force broker10 95%->80% largest margin",
                "broker10 保证金/权益超过95%后，按最大保证金占用品种逐手减到80%。",
            ),
            overrides=_forced_overrides(identity_map, 0.95, 0.80),
            profile="forced_margin_95_to_80_largest_margin",
        ),
        ForcedVariant(
            capital=_capital(
                "stage526_200k_force90_to75_largest_margin_r080_pc25_maxpos4",
                "20w Stage526 force broker10 90%->75% largest margin",
                "broker10 保证金/权益超过90%后，按最大保证金占用品种逐手减到75%。",
            ),
            overrides=_forced_overrides(identity_map, 0.90, 0.75),
            profile="forced_margin_90_to_75_largest_margin",
        ),
    ]


def _run_variant(
    spec: ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    s517.assert_stage196_database_sentinels()
    s517.s506._patch_stage506_raw_roots()
    c3_overrides = s513._c3_overrides(s517.START_DT)
    preload_start = max(s517.PRELOAD_START_DT, s517.START_DT - timedelta(days=365))
    _, open_map = s517.s506.s501._seed_proxy_maps()
    engine = s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=s517.Interval.DAILY,
        start=preload_start,
        end=s517.END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=spec.capital.c3_capital,
    )
    setting = s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
        strategy_overrides=c3_overrides,
    )
    setting["capital_base"] = spec.capital.c3_capital
    setting.update(spec.overrides)
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty daily result: {spec.capital.variant}")

    daily = daily_df.copy()
    daily = daily.loc[
        (daily.index >= s517.START_DT.date()) & (daily.index <= s517.END_DT.date())
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

    strategy = getattr(engine, "strategy", None)
    daily["forced_margin_deleverage_count"] = int(
        getattr(strategy, "forced_margin_deleverage_count", 0) or 0
    )
    daily["forced_margin_deleverage_closed_volume"] = int(
        getattr(strategy, "forced_margin_deleverage_closed_volume", 0) or 0
    )
    daily["forced_margin_deleverage_ratio"] = float(
        getattr(strategy, "forced_margin_deleverage_ratio", 0.0) or 0.0
    )
    daily["forced_margin_deleverage_max_observed_ratio"] = float(
        getattr(strategy, "forced_margin_deleverage_max_observed_ratio", 0.0) or 0.0
    )

    positions = s517.build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.capital.variant}")
    positions["variant"] = spec.capital.variant
    positions["combo_variant"] = spec.capital.variant
    positions["label"] = spec.capital.label
    positions["risk_multiplier"] = spec.capital.risk_multiplier

    usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    if not usage.empty:
        usage["variant"] = spec.capital.variant
        usage["label"] = spec.capital.label
        usage["risk_multiplier"] = spec.capital.risk_multiplier

    forced_events = pd.DataFrame(getattr(strategy, "forced_margin_deleverage_events", []) if strategy else [])
    if not forced_events.empty:
        forced_events["variant"] = spec.capital.variant
        forced_events["label"] = spec.capital.label
        forced_events["profile"] = spec.profile
    return daily, positions, usage, forced_events


def _forced_summary(specs: list[ForcedVariant], forced_events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        frame = (
            forced_events[forced_events["variant"].eq(spec.capital.variant)].copy()
            if not forced_events.empty
            else pd.DataFrame()
        )
        row: dict[str, Any] = {
            "variant": spec.capital.variant,
            "label": spec.capital.label,
            "profile": spec.profile,
            "forced_event_count": 0,
            "total_reduce_volume": 0,
            "first_forced_date": "",
            "max_ratio_before_pct": 0.0,
            "max_ratio_after_pct": 0.0,
            "top_reduced_products": "",
        }
        if not frame.empty:
            frame["reduce_volume"] = pd.to_numeric(frame["reduce_volume"], errors="coerce").fillna(0.0)
            top_products = (
                frame.groupby("product_vt_symbol")["reduce_volume"].sum().sort_values(ascending=False).head(5)
            )
            row.update(
                {
                    "forced_event_count": int(len(frame)),
                    "total_reduce_volume": int(frame["reduce_volume"].sum()),
                    "first_forced_date": str(pd.to_datetime(frame["date"]).min().date()),
                    "max_ratio_before_pct": float(pd.to_numeric(frame["ratio_before"], errors="coerce").max() * 100.0),
                    "max_ratio_after_pct": float(pd.to_numeric(frame["ratio_after"], errors="coerce").max() * 100.0),
                    "top_reduced_products": ",".join(f"{idx}:{int(value)}" for idx, value in top_products.items()),
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _metrics_with_profile(frame: pd.DataFrame, spec: ForcedVariant, cost_multiplier: float) -> dict[str, Any]:
    row = s650._metrics(frame, spec.capital, cost_multiplier)
    row["profile"] = spec.profile
    row["forced_margin_deleverage_count"] = int(frame["forced_margin_deleverage_count"].max())
    row["forced_margin_deleverage_closed_volume"] = int(frame["forced_margin_deleverage_closed_volume"].max())
    row["forced_margin_deleverage_max_observed_ratio_pct"] = float(
        frame["forced_margin_deleverage_max_observed_ratio"].max() * 100.0
    )
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
        "stage526_200k_forced_margin_deleverage_hard_pass"
        if non_baseline_hard
        else "stage526_200k_forced_margin_deleverage_not_ready"
    )
    return {
        "stage": "Stage353",
        "script_stage": "Stage653",
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
    forced_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    result_view = summary.sort_values(["hard_pass", "total_return_pct"], ascending=[False, False])
    cost_view = cost.sort_values(["variant", "cost_multiplier"])
    lines = [
        "# Stage653 Stage526 20万强制保证金减仓",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：部署资金层 A/C；不改 Stage526 alpha，不连接 CTP，不调用下单。",
        "- A：`stage526_200k_allin_r080_pc25_maxpos4`。",
        "- C：同一信号叠加持仓后强制保证金减仓，按最大保证金占用品种逐手平到目标线。",
        "- 候选假设：保留原版 all-in 的收益弹性，同时在 broker10 保证金/权益超阈值时自动释放保证金，避免真实账户被强平。",
        "- 运行前过拟合判断：否。账户生存风控是结构约束，不按日期、品种或交易信号调参。",
        "- 运行前继续价值判断：是。它是保留 all-in 高收益的最直接机制。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py PortfolioStrategy 支持多合约组合策略和目标持仓调仓，适合在组合目标仓位生成后追加账户级风险约束。",
        "- vn.py RiskManager 是事前风控模块，但持仓后保证金超限需要策略侧或账户侧主动减仓，不能只靠开仓前检查。",
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
                    "forced_margin_deleverage_count",
                    "forced_margin_deleverage_closed_volume",
                    "forced_margin_deleverage_max_observed_ratio_pct",
                    "hard_pass",
                ]
            ]
        ),
        "",
        "## 强制减仓事件",
        "",
        _md_table(forced_summary),
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
            max_rows=50,
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
            max_rows=80,
        ),
        "",
        "## 关键风险日",
        "",
        _md_table(events, max_rows=50),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最优候选：`{decision.get('best_variant', {}).get('variant', '')}`。",
        "- 如果强制减仓保留了大部分收益且消除穿线，后续仍需做真实交易可成交性和TCA验收。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    identity_map = s519._product_identity_cluster_map(metadata)
    specs = _variants(identity_map)

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    forced_event_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []

    for spec in specs:
        print(f"[stage653] running {spec.capital.variant}", flush=True)
        daily, positions, usage, forced_events = _run_variant(spec, metadata)
        daily["account_capital"] = spec.capital.account_capital
        daily["c3_capital"] = spec.capital.c3_capital
        daily["profile"] = spec.profile
        positions["account_capital"] = spec.capital.account_capital
        positions["c3_capital"] = spec.capital.c3_capital
        c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
        combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
        combined["profile"] = spec.profile
        for column in [
            "forced_margin_deleverage_count",
            "forced_margin_deleverage_closed_volume",
            "forced_margin_deleverage_ratio",
            "forced_margin_deleverage_max_observed_ratio",
        ]:
            combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0

        daily_frames.append(combined)
        position_frames.append(positions)
        product_frames.append(product_margin)
        if not usage.empty:
            usage["account_capital"] = spec.capital.account_capital
            usage["c3_capital"] = spec.capital.c3_capital
            usage_frames.append(usage)
        if not forced_events.empty:
            forced_event_frames.append(forced_events)

    combo_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    product_margin_all = pd.concat(product_frames, ignore_index=True, sort=False)
    usage_all = pd.concat(usage_frames, ignore_index=True, sort=False) if usage_frames else pd.DataFrame()
    forced_events_all = (
        pd.concat(forced_event_frames, ignore_index=True, sort=False) if forced_event_frames else pd.DataFrame()
    )
    forced_summary = _forced_summary(specs, forced_events_all)

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
    _write_report(summary, cost, rolling, events, forced_summary, decision)

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin_all.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    if not usage_all.empty:
        usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    if not forced_events_all.empty:
        forced_events_all.to_csv(FORCED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    forced_summary.to_csv(FORCED_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

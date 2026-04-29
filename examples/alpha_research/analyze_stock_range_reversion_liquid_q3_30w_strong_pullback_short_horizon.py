from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    FEATURE,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    pct,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_momentum_pullback_attribution_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_momentum_pullback_attribution_v1"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_strong_pullback_short_horizon_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_strong_pullback_short_horizon_v1"

ACCOUNT_SIZE_CNY: float = 300_000.0
HORIZONS: tuple[int, ...] = (3, 5)
TOP_KS: tuple[int, ...] = (3, 5)
BASKET_GROSS_WEIGHTS: tuple[float, ...] = (0.50, 0.70, 1.00)
MAX_PER_INDUSTRY_VALUES: tuple[int, ...] = (1, 2)
MAX_DRAWDOWN_LIMIT: float = -0.20
HIGH_RETURN_TARGET: float = 1.00

SIGNAL_SCOPES: tuple[tuple[str, str, pl.Expr], ...] = (
    (
        "market60_q4q5",
        "中期市场相对强势：60日跳10日市场相对强度q4-q5内的短期回调",
        pl.col("strength_market_q60") >= 4,
    ),
    (
        "industry60_q4q5",
        "中期行业相对强势：60日跳10日行业相对强度q4-q5内的短期回调",
        pl.col("strength_industry_q60") >= 4,
    ),
    (
        "dual60_q4q5",
        "中期双强：市场相对强q4-q5且行业相对强q4-q5内的短期回调",
        (pl.col("strength_market_q60") >= 4) & (pl.col("strength_industry_q60") >= 4),
    ),
    (
        "market60_q3q5",
        "中期市场相对不弱：60日跳10日市场相对强度q3-q5内的短期回调",
        pl.col("strength_market_q60") >= 3,
    ),
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "QuantConnect momentum short-term reversal strategy",
        "https://www.quantconnect.com/learning/articles/investment-strategy-library/momentum-short-term-reversal-strategy",
    ),
    (
        "Short-Term Reversals and Longer-Term Momentum around the World",
        "https://academic.oup.com/rfs/article/38/12/3673/8240327",
    ),
    (
        "Mean reversion strategy on strong liquid stocks experiencing pullback",
        "https://alvarezquanttrading.com/wp-content/uploads/2019/02/StrategyDescriptionResults.pdf",
    ),
    (
        "SSE trading mechanism: board lot constraints",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "SZSE board lot rules",
        "https://www.szse.cn/enSzhk/tradeMechanism/tradeRules/index.html",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / (variance**0.5) * (TRADING_DAYS**0.5)


def read_base_selected() -> pl.DataFrame:
    return (
        pl.read_csv(
            SOURCE_DIR / f"{SOURCE_PREFIX}_base_selected.csv",
            try_parse_dates=True,
            schema_overrides={
                "symbol": pl.Utf8,
                "vt_symbol": pl.Utf8,
                "bs_code": pl.Utf8,
                "code": pl.Utf8,
            },
        )
        .unique(subset=["datetime", "symbol"])
        .filter(pl.col(FEATURE).is_not_null() & pl.col(FEATURE).is_finite())
        .sort(["datetime", FEATURE, "adv20_turnover"], descending=[False, True, True])
    )


def build_selected_variant(
    base: pl.DataFrame,
    scope_name: str,
    scope_desc: str,
    scope_filter: pl.Expr,
    horizon: int,
    top_k: int,
    basket_gross_weight: float,
    max_per_industry: int,
) -> pl.DataFrame:
    scenario = f"{scope_name}_h{horizon}_top{top_k}_gross{int(basket_gross_weight * 100)}_ind{max_per_industry}"
    selected = (
        base.filter(scope_filter)
        .with_columns(
            pl.col(FEATURE).rank("ordinal", descending=True).over(["datetime", "industry"]).alias("_industry_rank")
        )
        .filter(pl.col("_industry_rank") <= max_per_industry)
        .with_columns(pl.col(FEATURE).rank("ordinal", descending=True).over("datetime").alias("_rank_after_industry"))
        .filter(pl.col("_rank_after_industry") <= top_k)
        .with_columns(
            pl.len().over("datetime").alias("candidate_count"),
            pl.col("industry").n_unique().over("datetime").alias("selected_industry_count"),
            pl.len().over(["datetime", "industry"]).alias("selected_industry_stock_count"),
        )
        .filter(pl.col("candidate_count") > 0)
        .with_columns((pl.lit(basket_gross_weight) / pl.col("candidate_count")).alias("basket_weight"))
        .with_columns(
            pl.col("basket_weight").sum().over("datetime").alias("basket_gross_weight"),
            pl.lit(scenario).alias("scenario"),
            pl.lit(scope_name).alias("signal_scope"),
            pl.lit(scope_desc).alias("signal_scope_description"),
            pl.lit("liquid_q3").alias("bucket"),
            pl.lit("30w_strong_pullback_equal").alias("weight_mode"),
            pl.lit(horizon).alias("shape_horizon"),
            pl.lit(top_k).alias("shape_top_k"),
            pl.lit(basket_gross_weight).alias("shape_basket_gross_weight"),
            pl.lit(max_per_industry).alias("shape_max_per_industry"),
        )
        .drop(["_industry_rank", "_rank_after_industry"])
    )
    return selected


def build_lots_for_horizon(selected: pl.DataFrame, horizon: int) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    extra_cols = [
        col
        for col in [
            "signal_scope",
            "signal_scope_description",
            "bucket",
            "weight_mode",
            "industry",
            "market",
            "adv20_turnover",
            "turnover_rate_f",
            "circ_mv",
            "total_mv",
            "candidate_count",
            "selected_industry_count",
            "selected_industry_stock_count",
            "basket_gross_weight",
            "shape_horizon",
            "shape_top_k",
            "shape_basket_gross_weight",
            "shape_max_per_industry",
        ]
        if col in selected.columns
    ]
    for day in range(1, horizon + 1):
        parts.append(
            selected.select(
                "scenario",
                pl.col("datetime").alias("signal_date"),
                "symbol",
                FEATURE,
                "basket_weight",
                *extra_cols,
                pl.col(f"start_date_{day}").alias("target_date"),
                pl.col(f"pnl_date_{day}").alias("pnl_date"),
                pl.col(f"stock_daily_ret_{day}").alias("stock_daily_ret"),
            )
            .with_columns(
                pl.lit(day).alias("holding_day"),
                (pl.col("basket_weight") / horizon).alias("lot_weight"),
            )
            .filter(
                pl.col("target_date").is_not_null()
                & pl.col("pnl_date").is_not_null()
                & pl.col("stock_daily_ret").is_not_null()
                & pl.col("stock_daily_ret").is_finite()
            )
        )
    return pl.concat(parts, how="vertical").sort(["scenario", "target_date", "signal_date", "symbol"])


def build_symbol_daily(lots: pl.DataFrame) -> pl.DataFrame:
    agg_exprs: list[pl.Expr] = [
        pl.col("lot_weight").sum().alias("target_weight"),
        pl.len().alias("active_lots"),
        pl.col("stock_daily_ret").first().alias("stock_daily_ret"),
        pl.col("signal_date").n_unique().alias("source_signal_days"),
        pl.col("holding_day").min().alias("min_holding_day"),
        pl.col("holding_day").max().alias("max_holding_day"),
    ]
    for col in [
        "signal_scope",
        "signal_scope_description",
        "industry",
        "market",
        "adv20_turnover",
        "turnover_rate_f",
        "circ_mv",
        "total_mv",
        "shape_horizon",
        "shape_top_k",
        "shape_basket_gross_weight",
        "shape_max_per_industry",
    ]:
        if col in lots.columns:
            agg_exprs.append(pl.col(col).first().alias(col))
    return (
        lots.group_by(["scenario", "target_date", "pnl_date", "symbol"])
        .agg(agg_exprs)
        .sort(["scenario", "target_date", "symbol"])
    )


def build_target_weights(selected: pl.DataFrame) -> pl.DataFrame:
    lots = build_lots_for_horizon(selected, int(selected["shape_horizon"][0]))
    symbol_daily = build_symbol_daily(lots)
    keep_cols = [
        col
        for col in [
            "scenario",
            "target_date",
            "symbol",
            "target_weight",
            "industry",
            "market",
            "adv20_turnover",
            "turnover_rate_f",
            "circ_mv",
            "total_mv",
            "signal_scope",
            "signal_scope_description",
            "shape_horizon",
            "shape_top_k",
            "shape_basket_gross_weight",
            "shape_max_per_industry",
        ]
        if col in symbol_daily.columns
    ]
    return symbol_daily.select(keep_cols).unique(subset=["scenario", "target_date", "symbol"]).sort(
        ["scenario", "target_date", "symbol"]
    )


def summarize_daily_extra(summary: dict[str, Any], daily: pl.DataFrame) -> dict[str, Any]:
    if daily.is_empty():
        return summary
    active = daily.filter((pl.col("actual_gross_weight") > 0) | (pl.col("filled_amount_sum_cny") > 0))
    returns = daily["strategy_daily_ret_min_fee"].to_list()
    summary["avg_actual_symbol_count"] = to_float(daily["actual_symbol_count"].mean())
    summary["avg_actual_gross_weight"] = to_float(daily["actual_gross_weight"].mean())
    summary["max_actual_gross_weight"] = to_float(daily["actual_gross_weight"].max())
    summary["active_or_trade_day_ratio"] = active.height / daily.height if daily.height else 0.0
    summary["net_active_day_win_rate"] = to_float((active["strategy_daily_ret_min_fee"] > 0).mean()) if active.height else 0.0
    summary["return_over_max_dd"] = (
        to_float(summary.get("total_return_min_fee")) / abs(to_float(summary.get("max_drawdown_min_fee")))
        if to_float(summary.get("max_drawdown_min_fee")) < 0
        else 0.0
    )
    summary["min_fee_equity_gap"] = to_float(summary.get("final_equity_bps_only")) - to_float(
        summary.get("final_equity_min_fee")
    )
    summary["latest_exposure_capture_ratio"] = (
        to_float(summary.get("latest_rounded_target_amount_sum_cny"))
        / to_float(summary.get("latest_target_amount_sum_cny"))
        if to_float(summary.get("latest_target_amount_sum_cny")) > 0
        else 0.0
    )
    summary["annualized_sharpe_recalc"] = annualized_sharpe(returns)
    return summary


def replay_variant(
    scenario: str,
    target_weights: pl.DataFrame,
    selected: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    exec_info: dict[tuple[Any, str], Any],
) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    scenario_targets = target_weights.filter(pl.col("scenario") == scenario).drop("scenario")
    target_maps = lot.build_target_maps(scenario_targets)
    dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
    orders, daily, _curve = lot.replay_lot_account(target_maps, dates, exec_info)
    if not orders.is_empty():
        orders = orders.with_columns(pl.lit(scenario).alias("scenario"))
    if not daily.is_empty():
        daily = daily.with_columns(pl.lit(scenario).alias("scenario"))
    summary = lot.summarize_orders(orders, daily)
    meta = (
        selected.filter(pl.col("scenario") == scenario)
        .select(
            "signal_scope",
            "signal_scope_description",
            "shape_horizon",
            "shape_top_k",
            "shape_basket_gross_weight",
            "shape_max_per_industry",
        )
        .row(0, named=True)
    )
    summary.update(meta)
    summary["scenario"] = scenario
    summary = summarize_daily_extra(summary, daily)
    yearly = build_yearly(scenario, daily)
    return summary, orders, daily, yearly


def build_yearly(scenario: str, daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    return (
        daily.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by("year")
        .agg(
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("year_return_min_fee"),
            pl.col("drawdown_min_fee").min().alias("year_curve_drawdown_min_fee"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("zero_lot_target_count").sum().alias("zero_lot_target_count"),
            pl.col("target_symbol_count").sum().alias("target_symbol_count"),
        )
        .with_columns(
            (pl.col("zero_lot_target_count") / pl.col("target_symbol_count")).alias("zero_lot_target_ratio"),
            pl.lit(scenario).alias("scenario"),
        )
        .sort(["scenario", "year"])
    )


def build_quality(summary: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in summary.iter_rows(named=True):
        scenario = row["scenario"]
        total_return = to_float(row.get("total_return_min_fee"))
        max_dd = to_float(row.get("max_drawdown_min_fee"))
        zero_ratio = to_float(row.get("zero_lot_target_ratio"))
        latest_capture = to_float(row.get("latest_exposure_capture_ratio"))
        min_fee_gap = to_float(row.get("min_fee_equity_gap"))
        active_win = to_float(row.get("net_active_day_win_rate"))
        rows.extend(
            [
                {
                    "scenario": scenario,
                    "checkpoint": "max_drawdown_within_20pct",
                    "status": "pass" if max_dd >= MAX_DRAWDOWN_LIMIT else "fail",
                    "value": pct(max_dd),
                    "expected": ">=-20%",
                    "note": "用户可接受的回测最大回撤边界。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "high_return_target",
                    "status": "pass" if total_return >= HIGH_RETURN_TARGET else "warn",
                    "value": pct(total_return),
                    "expected": ">=100%",
                    "note": "高收益候选目标，不单独作为上线依据。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "zero_lot_target_ratio",
                    "status": "fail" if zero_ratio > 0.20 else "warn" if zero_ratio > 0.10 else "pass",
                    "value": pct(zero_ratio),
                    "expected": "<=10% preferred, <=20% hard",
                    "note": "30万专属版本仍需尽量减少买不到一手。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "latest_exposure_capture_ratio",
                    "status": "fail" if latest_capture < 0.50 else "warn" if latest_capture < 0.70 else "pass",
                    "value": pct(latest_capture),
                    "expected": ">=70% preferred, >=50% hard",
                    "note": "最新目标日取整后市值相对目标市值的捕获率。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "min_fee_equity_gap",
                    "status": "warn" if min_fee_gap > 0.10 else "pass",
                    "value": f"{min_fee_gap:.4f}",
                    "expected": "<=0.10 equity gap",
                    "note": "最低佣金相对bps成本的额外权益拖累。",
                },
                {
                    "scenario": scenario,
                    "checkpoint": "active_day_win_rate",
                    "status": "warn" if active_win < 0.50 else "pass",
                    "value": pct(active_win),
                    "expected": ">=50%",
                    "note": "短周期策略至少应有稳定的活跃日胜率基础。",
                },
            ]
        )
    return pl.DataFrame(rows).sort(["scenario", "checkpoint"])


def write_report(summary: pl.DataFrame, quality: pl.DataFrame, yearly: pl.DataFrame, paths: dict[str, Path]) -> Path:
    report_path = paths["report"]
    pass_dd = summary.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).sort(
        ["total_return_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    best = pass_dd.row(0, named=True) if pass_dd.height else None
    high_return = summary.filter(pl.col("total_return_min_fee") >= HIGH_RETURN_TARGET).sort(
        ["max_drawdown_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    best_high = high_return.row(0, named=True) if high_return.height else None
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")

    lines = [
        "# 股票震荡liquid_q3 30万强势股短期回调 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：从30万本金出发，测试强势股短期回调是否优于弱势股反弹。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；最大回撤目标：`20%`以内。",
        f"- 预注册结构：强势池`{[item[0] for item in SIGNAL_SCOPES]}`；持有期`{HORIZONS}`；top_k `{TOP_KS}`；信号篮子总暴露`{BASKET_GROSS_WEIGHTS}`；单行业最多`{MAX_PER_INDUSTRY_VALUES}`只。",
        "- A/B判断：30万候选研究，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 短期反转与中期动量结合有学术和业界样例支持，合理形态是在中期强势结构里买短期过度回撤。",
        "- 对30万账户，强势股回调若可行，应体现为短持有期、较高暴露、但回撤不失控。",
        "- 本阶段仍是样本内结构测试；若出现候选，下一步必须做walk-forward和年份启动验证。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(["", "## 核心摘要", ""])
    if best:
        lines.append(
            f"- 回撤20%以内最高收益候选：`{best['scenario']}`，期末权益`{best['final_equity_min_fee']:.4f}`，总收益`{pct(best['total_return_min_fee'])}`，最大回撤`{pct(best['max_drawdown_min_fee'])}`，Sharpe `{best['sharpe_min_fee']:.3f}`。"
        )
    else:
        lines.append("- 回撤20%以内候选：本轮无。")
    if best_high:
        lines.append(
            f"- 收益100%以上里回撤最浅候选：`{best_high['scenario']}`，总收益`{pct(best_high['total_return_min_fee'])}`，最大回撤`{pct(best_high['max_drawdown_min_fee'])}`，Sharpe `{best_high['sharpe_min_fee']:.3f}`。"
        )
    else:
        lines.append("- 收益100%以上候选：本轮无。")
    lines.extend(
        [
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "- 判断：若强势回调仍不能兼顾收益和回撤，30万高收益目标需要进一步换到ETF/行业轮动或带明确止损/止盈的交易周期。",
            "",
            "## 场景汇总Top80",
            "",
            markdown_table(
                summary,
                [
                    "scenario",
                    "signal_scope",
                    "shape_horizon",
                    "shape_top_k",
                    "shape_basket_gross_weight",
                    "shape_max_per_industry",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "return_over_max_dd",
                    "zero_lot_target_ratio",
                    "latest_exposure_capture_ratio",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "net_active_day_win_rate",
                    "min_fee_equity_gap",
                ],
                max_rows=80,
            ),
            "",
            "## 回撤20%以内候选",
            "",
            "无数据"
            if pass_dd.is_empty()
            else markdown_table(
                pass_dd,
                [
                    "scenario",
                    "signal_scope",
                    "shape_horizon",
                    "shape_top_k",
                    "shape_basket_gross_weight",
                    "shape_max_per_industry",
                    "final_equity_min_fee",
                    "total_return_min_fee",
                    "max_drawdown_min_fee",
                    "sharpe_min_fee",
                    "zero_lot_target_ratio",
                    "latest_exposure_capture_ratio",
                ],
                max_rows=80,
            ),
            "",
            "## 年度拆分Top候选",
            "",
            markdown_table(
                yearly.join(
                    summary.select(["scenario", "total_return_min_fee"]).sort("total_return_min_fee", descending=True).head(12).select("scenario"),
                    on="scenario",
                    how="inner",
                ),
                [
                    "scenario",
                    "year",
                    "year_return_min_fee",
                    "year_curve_drawdown_min_fee",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "zero_lot_target_ratio",
                ],
                max_rows=140,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["scenario", "checkpoint", "status", "value", "expected", "note"], max_rows=220),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：中等风险。",
            "- 原因：本阶段有结构网格，但信号池、持有期和账户结构都预先限定，没有根据结果继续调alpha。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：需要看结果后再决定是否继续。",
            "- 原因：若只有少数高收益候选但年度不稳定，不能继续沿样本内最优深挖。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：弱势反弹方向已失败，强势股回调是更符合30万高收益目标的下一条自然路线。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：取决于是否存在回撤20%以内且收益显著高于弱势低暴露版本的候选。",
            "- 原因：如果仍不成立，应转向ETF/行业轮动或显式止盈止损归因。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = read_base_selected()
    selected_frames: list[pl.DataFrame] = []
    for scope_name, scope_desc, scope_filter in SIGNAL_SCOPES:
        for horizon in HORIZONS:
            for top_k in TOP_KS:
                for gross in BASKET_GROSS_WEIGHTS:
                    for max_industry in MAX_PER_INDUSTRY_VALUES:
                        selected_frames.append(
                            build_selected_variant(
                                base,
                                scope_name,
                                scope_desc,
                                scope_filter,
                                horizon,
                                top_k,
                                gross,
                                max_industry,
                            )
                        )
    selected = pl.concat(selected_frames, how="vertical").sort(["scenario", "datetime", FEATURE])
    target_frames: list[pl.DataFrame] = []
    for scenario in selected["scenario"].unique().sort().to_list():
        scenario_selected = selected.filter(pl.col("scenario") == scenario)
        target_frames.append(build_target_weights(scenario_selected))
    target_weights = pl.concat(target_frames, how="vertical").sort(["scenario", "target_date", "symbol"])

    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)
    summaries: list[dict[str, Any]] = []
    orders_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    yearly_frames: list[pl.DataFrame] = []
    for scenario in selected["scenario"].unique().sort().to_list():
        summary, orders, daily, yearly = replay_variant(scenario, target_weights, selected, benchmark_df, exec_info)
        summaries.append(summary)
        if not orders.is_empty():
            orders_frames.append(orders)
        if not daily.is_empty():
            daily_frames.append(daily)
        if not yearly.is_empty():
            yearly_frames.append(yearly)

    summary = pl.DataFrame(summaries).sort(
        ["total_return_min_fee", "max_drawdown_min_fee", "sharpe_min_fee"], descending=[True, True, True]
    )
    quality = build_quality(summary)
    orders = pl.concat(orders_frames, how="vertical") if orders_frames else pl.DataFrame()
    daily = pl.concat(daily_frames, how="vertical") if daily_frames else pl.DataFrame()
    yearly = pl.concat(yearly_frames, how="vertical").sort(["scenario", "year"]) if yearly_frames else pl.DataFrame()

    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "selected": OUTPUT_DIR / f"{PREFIX}_selected.csv",
        "target_weights": OUTPUT_DIR / f"{PREFIX}_target_weights.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.write_csv(paths["summary"])
    quality.write_csv(paths["quality"])
    yearly.write_csv(paths["yearly"])
    selected.write_csv(paths["selected"])
    target_weights.write_csv(paths["target_weights"])
    orders.write_csv(paths["orders"])
    daily.write_csv(paths["daily"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "signal_scopes": [(name, desc) for name, desc, _expr in SIGNAL_SCOPES],
            "horizons": HORIZONS,
            "top_ks": TOP_KS,
            "basket_gross_weights": BASKET_GROSS_WEIGHTS,
            "max_per_industry_values": MAX_PER_INDUSTRY_VALUES,
            "feature": FEATURE,
            "research_sources": RESEARCH_SOURCES,
        },
    )
    report_path = write_report(summary, quality, yearly, paths)
    print(f"report={report_path}")
    print(summary)
    print(quality)


if __name__ == "__main__":
    main()

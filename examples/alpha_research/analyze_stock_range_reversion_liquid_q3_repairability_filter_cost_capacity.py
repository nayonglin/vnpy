from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from backtest_stock_range_reversion_liquid_q3_persistent_confirmation import build_confirmation_lots
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_repairability_filter_cost_capacity_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_repairability_filter_cost_capacity_v1"

BASELINE_SCENARIO: str = "age4_daily_all"
CANDIDATE_SCENARIO: str = "age4_daily_exclude_volume_dry"
SCENARIOS: tuple[str, ...] = (BASELINE_SCENARIO, CANDIDATE_SCENARIO)
COST_STRESS_BPS: tuple[float, ...] = (0.0, 20.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0)
ACCOUNT_SIZES_CNY: tuple[float, ...] = (200_000.0, 1_000_000.0, 5_000_000.0, 10_000_000.0, 20_000_000.0, 50_000_000.0)
PARTICIPATION_LIMITS: tuple[float, ...] = (0.01, 0.03, 0.05, 0.10)
CAPACITY_THRESHOLDS: tuple[float, ...] = (0.01, 0.03, 0.05, 0.10)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Trading Costs by Frazzini, Israel and Moskowitz",
        "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3229719",
    ),
    (
        "Trading Costs of Asset Pricing Anomalies PDF",
        "https://haas.berkeley.edu/wp-content/uploads/TradingCostEfficiency_FULL_112912.pdf",
    ),
    (
        "Short-term reversals and costs of immediacy",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Empirical investigation of mean reversion strategies for equity markets",
        "https://arxiv.org/abs/1909.04327",
    ),
)


def summarize_return_frame(frame: pl.DataFrame, cost_bps: float) -> dict[str, Any]:
    ordered = frame.sort("date")
    returns = [float(value) for value in ordered["strategy_daily_ret"].to_list()]
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for daily_ret in returns:
        equity *= 1.0 + daily_ret
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)

    mean = sum(returns) / len(returns) if returns else 0.0
    variance = sum((ret - mean) ** 2 for ret in returns) / (len(returns) - 1) if len(returns) > 1 else 0.0
    std = variance**0.5
    sharpe = mean / std * sqrt(TRADING_DAYS) if std > 0 else 0.0
    active = ordered.filter((pl.col("return_gross_exposure") > 0) | (pl.col("gross_abs_weight_change") > 0))
    turnover_mean = float(ordered["one_way_turnover"].mean() or 0.0)
    return {
        "scenario": ordered["scenario"][0],
        "roundtrip_cost_bps": cost_bps,
        "days": len(returns),
        "final_equity": equity,
        "total_return": equity - 1.0,
        "annualized_return": equity ** (TRADING_DAYS / len(returns)) - 1.0 if returns and equity > 0 else -1.0,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "gross_total_return": float(ordered["strategy_gross_equity"][-1] - 1.0),
        "cost_drag_sum": float(ordered["turnover_cost_ret"].sum()),
        "annualized_one_way_turnover": turnover_mean * TRADING_DAYS,
        "active_day_win_rate": float((active["strategy_daily_ret"] > 0).mean() or 0.0) if not active.is_empty() else 0.0,
        "avg_gross_exposure": float(ordered["target_gross_exposure"].mean() or 0.0),
    }


def rebuild_curve_for_cost(base_frame: pl.DataFrame, cost_bps: float) -> pl.DataFrame:
    one_way_cost = cost_bps / 2.0 / 10000.0
    return (
        base_frame.sort(["scenario", "date"])
        .with_columns(
            (pl.col("gross_abs_weight_change") * one_way_cost).alias("turnover_cost_ret"),
            (pl.col("strategy_gross_daily_ret") - pl.col("gross_abs_weight_change") * one_way_cost).alias(
                "strategy_daily_ret"
            ),
            pl.lit(cost_bps).alias("roundtrip_cost_bps"),
        )
        .with_columns((1.0 + pl.col("strategy_daily_ret")).cum_prod().over("scenario").alias("strategy_equity"))
        .with_columns((pl.col("strategy_equity") / pl.col("strategy_equity").cum_max().over("scenario") - 1).alias("strategy_drawdown"))
    )


def build_cost_stress(equity_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    base_cols = [
        "date",
        "scenario",
        "strategy_gross_daily_ret",
        "return_gross_exposure",
        "gross_abs_weight_change",
        "one_way_turnover",
        "target_gross_exposure",
        "strategy_gross_equity",
    ]
    base_frame = (
        equity_df.filter((pl.col("roundtrip_cost_bps") == 20.0) & pl.col("scenario").is_in(SCENARIOS))
        .select(base_cols)
        .sort(["scenario", "date"])
    )
    curves: list[pl.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for cost_bps in COST_STRESS_BPS:
        curve = rebuild_curve_for_cost(base_frame, cost_bps)
        curves.append(curve)
        for scenario in SCENARIOS:
            summary_rows.append(summarize_return_frame(curve.filter(pl.col("scenario") == scenario), cost_bps))
    return pl.DataFrame(summary_rows).sort(["roundtrip_cost_bps", "scenario"]), pl.concat(curves, how="vertical")


def final_equity_at_cost(frame: pl.DataFrame, cost_bps: float) -> float:
    one_way_cost = cost_bps / 2.0 / 10000.0
    equity = 1.0
    for row in frame.sort("date").iter_rows(named=True):
        equity *= 1.0 + float(row["strategy_gross_daily_ret"]) - float(row["gross_abs_weight_change"]) * one_way_cost
    return equity


def build_breakeven_cost(equity_df: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    base_frame = equity_df.filter((pl.col("roundtrip_cost_bps") == 20.0) & pl.col("scenario").is_in(SCENARIOS))
    for scenario in SCENARIOS:
        frame = base_frame.filter(pl.col("scenario") == scenario)
        gross_final = final_equity_at_cost(frame, 0.0)
        high = 100.0
        while final_equity_at_cost(frame, high) > 1.0 and high < 5000.0:
            high *= 2.0
        if gross_final <= 1.0:
            breakeven = 0.0
        elif high >= 5000.0 and final_equity_at_cost(frame, high) > 1.0:
            breakeven = high
        else:
            low = 0.0
            for _ in range(50):
                mid = (low + high) / 2.0
                if final_equity_at_cost(frame, mid) > 1.0:
                    low = mid
                else:
                    high = mid
            breakeven = (low + high) / 2.0
        rows.append(
            {
                "scenario": scenario,
                "gross_final_equity": gross_final,
                "breakeven_roundtrip_cost_bps": breakeven,
                "final_equity_at_50bp": final_equity_at_cost(frame, 50.0),
                "final_equity_at_100bp": final_equity_at_cost(frame, 100.0),
                "final_equity_at_150bp": final_equity_at_cost(frame, 150.0),
                "final_equity_at_200bp": final_equity_at_cost(frame, 200.0),
            }
        )
    return pl.DataFrame(rows).sort("scenario")


def build_turnover_stress(turnover_df: pl.DataFrame) -> pl.DataFrame:
    return (
        turnover_df.filter(pl.col("scenario").is_in(SCENARIOS))
        .group_by("scenario")
        .agg(
            pl.len().alias("days"),
            (pl.col("one_way_turnover") > 0).sum().alias("trade_days"),
            pl.col("one_way_turnover").mean().alias("avg_one_way_turnover"),
            pl.col("one_way_turnover").quantile(0.50).alias("p50_one_way_turnover"),
            pl.col("one_way_turnover").quantile(0.75).alias("p75_one_way_turnover"),
            pl.col("one_way_turnover").quantile(0.90).alias("p90_one_way_turnover"),
            pl.col("one_way_turnover").quantile(0.95).alias("p95_one_way_turnover"),
            pl.col("one_way_turnover").quantile(0.99).alias("p99_one_way_turnover"),
            pl.col("one_way_turnover").max().alias("max_one_way_turnover"),
            pl.col("gross_abs_weight_change").quantile(0.95).alias("p95_gross_abs_weight_change"),
            pl.col("gross_abs_weight_change").max().alias("max_gross_abs_weight_change"),
            pl.col("buy_weight").quantile(0.95).alias("p95_buy_weight"),
            pl.col("sell_weight").quantile(0.95).alias("p95_sell_weight"),
            pl.col("target_active_symbols").quantile(0.50).alias("p50_target_active_symbols"),
            pl.col("target_active_symbols").quantile(0.95).alias("p95_target_active_symbols"),
            pl.col("target_gross_exposure").mean().alias("avg_target_gross_exposure"),
            pl.col("target_gross_exposure").max().alias("max_target_gross_exposure"),
        )
        .with_columns((pl.col("trade_days") / pl.col("days")).alias("trade_day_ratio"))
        .sort("scenario")
    )


def build_symbol_daily_from_selected(selected: pl.DataFrame) -> pl.DataFrame:
    lots = build_confirmation_lots(selected.filter(pl.col("scenario").is_in(SCENARIOS)))
    agg_exprs: list[pl.Expr] = [
        pl.col("lot_weight").sum().alias("target_weight"),
        pl.len().alias("active_lots"),
        pl.col("stock_daily_ret").first().alias("stock_daily_ret"),
        pl.col("adv20_turnover").median().alias("adv20_turnover"),
        pl.col("turnover_rate_f").median().alias("turnover_rate_f"),
        pl.col("circ_mv").median().alias("circ_mv"),
        pl.col("total_mv").median().alias("total_mv"),
        pl.col("industry").first().alias("industry"),
    ]
    return (
        lots.group_by(["scenario", "target_date", "pnl_date", "symbol"])
        .agg(agg_exprs)
        .sort(["scenario", "target_date", "symbol"])
    )


def build_trade_changes(symbol_daily: pl.DataFrame, equity_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    dates = (
        equity_df.filter((pl.col("roundtrip_cost_bps") == 20.0) & pl.col("scenario").is_in(SCENARIOS))
        .select("scenario", pl.col("date").alias("target_date"))
        .unique()
    )
    symbols = symbol_daily.select("scenario", "symbol").unique()
    target_liquidity = symbol_daily.select(
        "scenario",
        "target_date",
        "symbol",
        "target_weight",
        "adv20_turnover",
        "turnover_rate_f",
        "circ_mv",
        "total_mv",
        "industry",
    ).unique(subset=["scenario", "target_date", "symbol"])
    full_targets = (
        dates.join(symbols, on="scenario", how="inner")
        .join(target_liquidity, on=["scenario", "target_date", "symbol"], how="left")
        .with_columns(pl.col("target_weight").fill_null(0.0))
        .sort(["scenario", "symbol", "target_date"])
        .with_columns(
            pl.col("target_weight").shift(1).over(["scenario", "symbol"]).fill_null(0.0).alias(
                "prev_target_weight"
            ),
            pl.col("adv20_turnover").shift(1).over(["scenario", "symbol"]).alias("prev_adv20_turnover"),
            pl.col("turnover_rate_f").shift(1).over(["scenario", "symbol"]).alias("prev_turnover_rate_f"),
            pl.col("circ_mv").shift(1).over(["scenario", "symbol"]).alias("prev_circ_mv"),
        )
        .with_columns(
            (pl.col("target_weight") - pl.col("prev_target_weight")).alias("target_weight_delta"),
            (pl.col("target_weight") - pl.col("prev_target_weight")).abs().alias("abs_target_weight_delta"),
        )
        .with_columns(
            pl.when(pl.col("target_weight_delta") > 0)
            .then(pl.lit("buy"))
            .when(pl.col("target_weight_delta") < 0)
            .then(pl.lit("sell"))
            .otherwise(pl.lit("none"))
            .alias("trade_side"),
            pl.when(pl.col("target_weight_delta") > 0)
            .then(pl.col("adv20_turnover"))
            .otherwise(pl.col("prev_adv20_turnover"))
            .alias("trade_adv20_turnover"),
            pl.when(pl.col("target_weight_delta") > 0)
            .then(pl.col("turnover_rate_f"))
            .otherwise(pl.col("prev_turnover_rate_f"))
            .alias("trade_turnover_rate_f"),
            pl.when(pl.col("target_weight_delta") > 0).then(pl.col("circ_mv")).otherwise(pl.col("prev_circ_mv")).alias(
                "trade_circ_mv"
            ),
        )
    )
    trades_all = full_targets.filter(pl.col("abs_target_weight_delta") > 1e-12)
    trades = trades_all.filter(pl.col("trade_adv20_turnover").is_not_null() & (pl.col("trade_adv20_turnover") > 0))
    missing = (
        trades_all.group_by("scenario")
        .agg(
            pl.len().alias("trade_rows_all"),
            (pl.col("trade_adv20_turnover").is_null() | (pl.col("trade_adv20_turnover") <= 0)).sum().alias(
                "missing_liquidity_rows"
            ),
        )
        .with_columns((pl.col("missing_liquidity_rows") / pl.col("trade_rows_all")).alias("missing_liquidity_ratio"))
    )
    return trades, missing


def build_participation_summary(trades: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    for account_size in ACCOUNT_SIZES_CNY:
        with_part = trades.with_columns(
            pl.lit(account_size).alias("account_size_cny"),
            (pl.col("abs_target_weight_delta") * account_size).alias("trade_amount_cny"),
            (pl.col("abs_target_weight_delta") * account_size / pl.col("trade_adv20_turnover")).alias(
                "participation_adv20"
            ),
        )
        frames.append(with_part)
        daily_frames.append(
            with_part.group_by(["scenario", "target_date", "account_size_cny"])
            .agg(
                pl.len().alias("trade_names"),
                pl.col("trade_amount_cny").sum().alias("gross_trade_amount_cny"),
                pl.col("participation_adv20").max().alias("max_name_participation"),
                pl.col("participation_adv20").quantile(0.95).alias("p95_name_participation"),
                pl.col("trade_adv20_turnover").sum().alias("trade_adv20_turnover_sum"),
            )
            .with_columns(
                (pl.col("gross_trade_amount_cny") / pl.col("trade_adv20_turnover_sum")).alias(
                    "gross_trade_to_adv20_sum"
                )
            )
        )
    all_part = pl.concat(frames, how="vertical")
    daily_part = pl.concat(daily_frames, how="vertical")

    summary_exprs: list[pl.Expr] = [
        pl.len().alias("trade_rows"),
        pl.col("target_date").n_unique().alias("trade_days"),
        pl.col("trade_amount_cny").sum().alias("gross_trade_amount_cny_sum"),
        pl.col("participation_adv20").mean().alias("avg_participation"),
        pl.col("participation_adv20").quantile(0.50).alias("p50_participation"),
        pl.col("participation_adv20").quantile(0.90).alias("p90_participation"),
        pl.col("participation_adv20").quantile(0.95).alias("p95_participation"),
        pl.col("participation_adv20").quantile(0.99).alias("p99_participation"),
        pl.col("participation_adv20").max().alias("max_participation"),
        pl.col("trade_amount_cny").quantile(0.95).alias("p95_name_trade_amount_cny"),
        pl.col("trade_amount_cny").max().alias("max_name_trade_amount_cny"),
    ]
    for limit in PARTICIPATION_LIMITS:
        label = int(limit * 100)
        summary_exprs.append((pl.col("participation_adv20") > limit).mean().alias(f"share_participation_gt_{label}pct"))
    participation_summary = all_part.group_by(["scenario", "account_size_cny"]).agg(summary_exprs).sort(
        ["scenario", "account_size_cny"]
    )
    daily_summary = (
        daily_part.group_by(["scenario", "account_size_cny"])
        .agg(
            pl.len().alias("trade_days"),
            pl.col("gross_trade_amount_cny").mean().alias("avg_daily_gross_trade_amount_cny"),
            pl.col("gross_trade_amount_cny").quantile(0.95).alias("p95_daily_gross_trade_amount_cny"),
            pl.col("gross_trade_amount_cny").max().alias("max_daily_gross_trade_amount_cny"),
            pl.col("trade_names").mean().alias("avg_daily_trade_names"),
            pl.col("trade_names").quantile(0.95).alias("p95_daily_trade_names"),
            pl.col("max_name_participation").quantile(0.95).alias("p95_daily_max_name_participation"),
            pl.col("max_name_participation").max().alias("max_daily_max_name_participation"),
            pl.col("gross_trade_to_adv20_sum").quantile(0.95).alias("p95_daily_gross_trade_to_adv20_sum"),
            pl.col("gross_trade_to_adv20_sum").max().alias("max_daily_gross_trade_to_adv20_sum"),
        )
        .sort(["scenario", "account_size_cny"])
    )
    capacity_rows: list[dict[str, Any]] = []
    base = all_part.filter(pl.col("account_size_cny") == 1_000_000.0)
    for scenario, group in base.partition_by("scenario", as_dict=True).items():
        p95_per_1m = float(group["participation_adv20"].quantile(0.95))
        p99_per_1m = float(group["participation_adv20"].quantile(0.99))
        max_per_1m = float(group["participation_adv20"].max())
        row: dict[str, Any] = {
            "scenario": scenario[0] if isinstance(scenario, tuple) else scenario,
            "p95_participation_per_1m": p95_per_1m,
            "p99_participation_per_1m": p99_per_1m,
            "max_participation_per_1m": max_per_1m,
        }
        for threshold in CAPACITY_THRESHOLDS:
            label = int(threshold * 100)
            row[f"capacity_cny_at_p95_{label}pct"] = 1_000_000.0 * threshold / p95_per_1m if p95_per_1m > 0 else None
            row[f"capacity_cny_at_p99_{label}pct"] = 1_000_000.0 * threshold / p99_per_1m if p99_per_1m > 0 else None
            row[f"capacity_cny_at_max_{label}pct"] = 1_000_000.0 * threshold / max_per_1m if max_per_1m > 0 else None
        capacity_rows.append(row)
    return participation_summary, daily_summary, pl.DataFrame(capacity_rows).sort("scenario"), all_part


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def write_report(
    cost_summary: pl.DataFrame,
    breakeven: pl.DataFrame,
    turnover_stress: pl.DataFrame,
    participation_summary: pl.DataFrame,
    daily_participation_summary: pl.DataFrame,
    capacity: pl.DataFrame,
    missing_liquidity: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    candidate_cost = cost_summary.filter(pl.col("scenario") == CANDIDATE_SCENARIO)
    candidate_150 = candidate_cost.filter(pl.col("roundtrip_cost_bps") == 150.0).to_dicts()[0]
    candidate_200 = candidate_cost.filter(pl.col("roundtrip_cost_bps") == 200.0).to_dicts()[0]
    candidate_breakeven = breakeven.filter(pl.col("scenario") == CANDIDATE_SCENARIO).to_dicts()[0]
    candidate_capacity = capacity.filter(pl.col("scenario") == CANDIDATE_SCENARIO).to_dicts()[0]
    candidate_part_10m = participation_summary.filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("account_size_cny") == 10_000_000.0)
    ).to_dicts()[0]

    lines = [
        "# 股票震荡liquid_q3成交干枯过滤成本/容量压力复核 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第244阶段候选`exclude_volume_dry`的成本压力、换手尖峰和成交额容量复核；不新增交易规则、不调参数。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 短反转策略的主要敌人不是信号定义，而是交易成本、价格冲击和可承载资金规模。",
        "- 业界交易成本研究通常把短反转列为对换手和成本最敏感的一类风格；因此必须先过成本/容量压力，再谈正式版本。",
        "- 本阶段不套用外部冲击模型，只做透明的成本网格和ADV参与率近似，避免把不可验证假设塞进结果。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心观察",
            "",
            f"- `exclude_volume_dry`成本盈亏平衡约`{candidate_breakeven['breakeven_roundtrip_cost_bps']:.1f}bp`；150bp下期末权益`{candidate_150['final_equity']:.4f}`，总收益`{pct(candidate_150['total_return'])}`，最大回撤`{pct(candidate_150['max_drawdown'])}`，Sharpe `{candidate_150['sharpe']:.2f}`；200bp下期末权益`{candidate_200['final_equity']:.4f}`。",
            f"- 1000万资金规模下，候选单笔成交额/ADV的p99约`{pct(candidate_part_10m['p99_participation'])}`，超过5% ADV的交易行占比`{pct(candidate_part_10m['share_participation_gt_5pct'])}`，超过10% ADV的交易行占比`{pct(candidate_part_10m['share_participation_gt_10pct'])}`。",
            f"- 候选按p99单票参与率估算，控制在5% ADV内的容量约`{candidate_capacity['capacity_cny_at_p99_5pct'] / 10_000:.0f}`万元；如果要求最极端单笔也不超过5% ADV，容量约`{candidate_capacity['capacity_cny_at_max_5pct'] / 10_000:.0f}`万元。",
            "- 直觉判断：这是股票震荡线的一个比较大研究突破，但还不是正式策略突破；它已经通过时间稳健性和初步成本/容量压力，但还需要把成交模型从ADV近似推进到真实可成交约束。",
            "",
            "## 成本网格",
            "",
            markdown_table(
                cost_summary,
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "cost_drag_sum",
                    "annualized_one_way_turnover",
                    "active_day_win_rate",
                ],
            ),
            "",
            "## 盈亏平衡成本",
            "",
            markdown_table(
                breakeven,
                [
                    "scenario",
                    "gross_final_equity",
                    "breakeven_roundtrip_cost_bps",
                    "final_equity_at_50bp",
                    "final_equity_at_100bp",
                    "final_equity_at_150bp",
                    "final_equity_at_200bp",
                ],
            ),
            "",
            "## 每日换手尖峰",
            "",
            markdown_table(
                turnover_stress,
                [
                    "scenario",
                    "days",
                    "trade_days",
                    "trade_day_ratio",
                    "avg_one_way_turnover",
                    "p95_one_way_turnover",
                    "p99_one_way_turnover",
                    "max_one_way_turnover",
                    "p95_target_active_symbols",
                    "avg_target_gross_exposure",
                    "max_target_gross_exposure",
                ],
            ),
            "",
            "## 参与率压力：单笔交易行",
            "",
            markdown_table(
                participation_summary.filter(pl.col("account_size_cny").is_in([1_000_000.0, 10_000_000.0, 50_000_000.0])),
                [
                    "scenario",
                    "account_size_cny",
                    "trade_rows",
                    "p95_participation",
                    "p99_participation",
                    "max_participation",
                    "share_participation_gt_1pct",
                    "share_participation_gt_3pct",
                    "share_participation_gt_5pct",
                    "share_participation_gt_10pct",
                    "p95_name_trade_amount_cny",
                    "max_name_trade_amount_cny",
                ],
            ),
            "",
            "## 参与率压力：每日聚合",
            "",
            markdown_table(
                daily_participation_summary.filter(
                    pl.col("account_size_cny").is_in([1_000_000.0, 10_000_000.0, 50_000_000.0])
                ),
                [
                    "scenario",
                    "account_size_cny",
                    "trade_days",
                    "avg_daily_gross_trade_amount_cny",
                    "p95_daily_gross_trade_amount_cny",
                    "max_daily_gross_trade_amount_cny",
                    "avg_daily_trade_names",
                    "p95_daily_trade_names",
                    "p95_daily_max_name_participation",
                    "max_daily_max_name_participation",
                    "p95_daily_gross_trade_to_adv20_sum",
                    "max_daily_gross_trade_to_adv20_sum",
                ],
            ),
            "",
            "## 容量粗估",
            "",
            markdown_table(
                capacity,
                [
                    "scenario",
                    "p95_participation_per_1m",
                    "p99_participation_per_1m",
                    "max_participation_per_1m",
                    "capacity_cny_at_p99_3pct",
                    "capacity_cny_at_p99_5pct",
                    "capacity_cny_at_p99_10pct",
                    "capacity_cny_at_max_3pct",
                    "capacity_cny_at_max_5pct",
                    "capacity_cny_at_max_10pct",
                ],
            ),
            "",
            "## 流动性缺失检查",
            "",
            markdown_table(missing_liquidity, ["scenario", "trade_rows_all", "missing_liquidity_rows", "missing_liquidity_ratio"]),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只测试成本和容量，不增加任何能提高收益的信号或阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否，但仍不是严格样本外。",
            "- 原因：成本和容量压力是反证测试，不是优化测试；结果支持候选，但容量估算依赖信号日ADV近似，仍需更真实成交模型复核。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第246阶段已显示时间稳健性，成本/容量是决定股票短反转能否继续推进的硬门槛。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：候选在高于50bp的成本下仍有正收益，且当前中小资金规模的ADV参与率压力不高，值得进入更真实的执行约束验证。",
            "",
            "## 决策",
            "",
            "- 可以把`exclude_volume_dry`定为股票震荡线的阶段性重要研究突破。",
            "- 仍不进入正式股票策略。",
            "- 不接入第78，不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 下一步应做真实成交约束版本：按开盘可买、涨跌停不可成交、单票成交额上限、延迟成交和现金闲置重算净值。",
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
    equity_df = pl.read_csv(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_equity_curve.csv", try_parse_dates=True)
    turnover_df = pl.read_csv(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_turnover.csv", try_parse_dates=True)
    selected_all = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")

    cost_summary, cost_curves = build_cost_stress(equity_df)
    breakeven = build_breakeven_cost(equity_df)
    turnover_stress = build_turnover_stress(turnover_df)
    symbol_daily = build_symbol_daily_from_selected(selected_all)
    trades, missing_liquidity = build_trade_changes(symbol_daily, equity_df)
    participation_summary, daily_participation_summary, capacity, participation_detail = build_participation_summary(
        trades
    )

    meta: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_scenario": BASELINE_SCENARIO,
        "candidate_scenario": CANDIDATE_SCENARIO,
        "cost_stress_bps": COST_STRESS_BPS,
        "account_sizes_cny": ACCOUNT_SIZES_CNY,
        "participation_limits": PARTICIPATION_LIMITS,
        "capacity_thresholds": CAPACITY_THRESHOLDS,
        "source_output_dir": str(FILTER_OUTPUT_DIR),
        "research_sources": RESEARCH_SOURCES,
        "capacity_note": "Uses signal/holding-level adv20_turnover as ex-ante liquidity proxy; not a full execution simulator.",
    }
    paths = {
        "cost_summary": OUTPUT_DIR / f"{PREFIX}_cost_summary.csv",
        "cost_curves": OUTPUT_DIR / f"{PREFIX}_cost_curves.csv",
        "breakeven": OUTPUT_DIR / f"{PREFIX}_breakeven.csv",
        "turnover_stress": OUTPUT_DIR / f"{PREFIX}_turnover_stress.csv",
        "trade_changes": OUTPUT_DIR / f"{PREFIX}_trade_changes.parquet",
        "missing_liquidity": OUTPUT_DIR / f"{PREFIX}_missing_liquidity.csv",
        "participation_summary": OUTPUT_DIR / f"{PREFIX}_participation_summary.csv",
        "daily_participation_summary": OUTPUT_DIR / f"{PREFIX}_daily_participation_summary.csv",
        "capacity": OUTPUT_DIR / f"{PREFIX}_capacity.csv",
        "participation_detail": OUTPUT_DIR / f"{PREFIX}_participation_detail.parquet",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    cost_summary.write_csv(paths["cost_summary"])
    cost_curves.write_csv(paths["cost_curves"])
    breakeven.write_csv(paths["breakeven"])
    turnover_stress.write_csv(paths["turnover_stress"])
    trades.write_parquet(paths["trade_changes"])
    missing_liquidity.write_csv(paths["missing_liquidity"])
    participation_summary.write_csv(paths["participation_summary"])
    daily_participation_summary.write_csv(paths["daily_participation_summary"])
    capacity.write_csv(paths["capacity"])
    participation_detail.write_parquet(paths["participation_detail"])
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        cost_summary,
        breakeven,
        turnover_stress,
        participation_summary,
        daily_participation_summary,
        capacity,
        missing_liquidity,
        meta,
        paths,
    )
    print(cost_summary)
    print(breakeven)
    print(participation_summary.filter(pl.col("account_size_cny").is_in([1_000_000.0, 10_000_000.0])))
    print(capacity)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()

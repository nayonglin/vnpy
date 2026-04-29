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
    HORIZON,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    build_lots,
    build_symbol_daily,
    pct,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_momentum_pullback_attribution_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_momentum_pullback_attribution_v1"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_high_return_shape_grid_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_high_return_shape_grid_v1"

SOURCE_SCENARIO: str = "weak_market60_q1q2_reallocated"
ACCOUNT_SIZE_CNY: float = 300_000.0
TOP_KS: tuple[int, ...] = (3, 5, 8)
BASKET_GROSS_WEIGHTS: tuple[float, ...] = (0.30, 0.50, 0.70)
MAX_PER_INDUSTRY_VALUES: tuple[int, ...] = (1, 2)
MAX_DRAWDOWN_LIMIT: float = -0.20
HIGH_RETURN_TARGET: float = 1.00

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "SSE trading mechanism: board lot constraints",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "SZSE board lot rules",
        "https://www.szse.cn/enSzhk/tradeMechanism/tradeRules/index.html",
    ),
    (
        "Position sizing for systematic trading",
        "https://www.monstertradingsystems.com/position-sizing-models-for-systematic-trading/",
    ),
    (
        "Mean reversion position sizing risks",
        "https://setupalpha.com/blogs/articles/mean-reversion-strategy-failures-complete-fix-guide",
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
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((item - mean) ** 2 for item in values) / (len(values) - 1)
    if variance <= 0:
        return 0.0
    return mean / (variance**0.5) * (TRADING_DAYS**0.5)


def read_source_candidates() -> pl.DataFrame:
    return (
        pl.read_csv(
            SOURCE_DIR / f"{SOURCE_PREFIX}_selected_variants.csv",
            try_parse_dates=True,
            schema_overrides={
                "symbol": pl.Utf8,
                "vt_symbol": pl.Utf8,
                "bs_code": pl.Utf8,
                "code": pl.Utf8,
            },
        )
        .filter(pl.col("scenario") == SOURCE_SCENARIO)
        .unique(subset=["datetime", "symbol"])
        .sort(["datetime", FEATURE, "adv20_turnover"], descending=[False, True, True])
    )


def build_concentrated_selected(
    base: pl.DataFrame,
    top_k: int,
    basket_gross_weight: float,
    max_per_industry: int,
) -> pl.DataFrame:
    scenario = f"top{top_k}_gross{int(basket_gross_weight * 100)}_ind{max_per_industry}"
    description = (
        f"30万专属：每日按{FEATURE}选top{top_k}，单行业最多{max_per_industry}只，"
        f"信号篮子目标总暴露{basket_gross_weight:.0%}"
    )
    selected = (
        base.with_columns(
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
            pl.lit(description).alias("scenario_description"),
            pl.lit("liquid_q3").alias("bucket"),
            pl.lit("30w_concentrated_equal").alias("weight_mode"),
            pl.lit(top_k).alias("shape_top_k"),
            pl.lit(basket_gross_weight).alias("shape_basket_gross_weight"),
            pl.lit(max_per_industry).alias("shape_max_per_industry"),
        )
        .drop(["_industry_rank", "_rank_after_industry"])
    )
    return selected


def build_target_weights(selected: pl.DataFrame) -> pl.DataFrame:
    lots = build_lots(selected)
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
    ret = daily["strategy_daily_ret_min_fee"].to_list()
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
    summary["annualized_sharpe_recalc"] = annualized_sharpe(ret)
    return summary


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
            pl.col("filled_amount_sum_cny").sum().alias("filled_amount_sum_cny"),
        )
        .with_columns(
            (pl.col("zero_lot_target_count") / pl.col("target_symbol_count")).alias("zero_lot_target_ratio"),
            pl.lit(scenario).alias("scenario"),
        )
        .sort(["scenario", "year"])
    )


def replay_shape(
    scenario: str,
    selected: pl.DataFrame,
    target_weights: pl.DataFrame,
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
    shape_meta = selected.filter(pl.col("scenario") == scenario).select(
        "shape_top_k", "shape_basket_gross_weight", "shape_max_per_industry", "scenario_description"
    ).row(0, named=True)
    summary.update(shape_meta)
    summary["scenario"] = scenario
    summary = summarize_daily_extra(summary, daily)
    yearly = build_yearly(scenario, daily)
    return summary, orders, daily, yearly


def build_quality(summary: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in summary.iter_rows(named=True):
        scenario = row["scenario"]
        total_return = to_float(row.get("total_return_min_fee"))
        max_dd = to_float(row.get("max_drawdown_min_fee"))
        zero_ratio = to_float(row.get("zero_lot_target_ratio"))
        latest_capture = to_float(row.get("latest_exposure_capture_ratio"))
        min_fee_gap = to_float(row.get("min_fee_equity_gap"))
        avg_symbols = to_float(row.get("avg_actual_symbol_count"))
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
                    "checkpoint": "avg_actual_symbol_count",
                    "status": "warn" if avg_symbols < 3 else "pass",
                    "value": f"{avg_symbols:.2f}",
                    "expected": ">=3",
                    "note": "过少会变成单票路径押注，过多则30万一手颗粒度不足。",
                },
            ]
        )
    return pl.DataFrame(rows).sort(["scenario", "checkpoint"])


def write_report(
    summary: pl.DataFrame,
    quality: pl.DataFrame,
    yearly: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    pass_dd = summary.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).sort(
        ["total_return_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    all_pass_scenarios = (
        quality.group_by("scenario")
        .agg((pl.col("status") == "pass").all().alias("all_pass"))
        .filter(pl.col("all_pass"))
        .select("scenario")
    )
    all_pass = summary.join(all_pass_scenarios, on="scenario", how="inner").sort(
        ["total_return_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    best_dd = pass_dd.row(0, named=True) if pass_dd.height else None
    best_all_pass = all_pass.row(0, named=True) if all_pass.height else None
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")

    lines = [
        "# 股票震荡liquid_q3 30万高收益组合形状网格 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：固定`weak_market60_q1q2`信号，只研究30万账户可承载的组合形状。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；最大回撤目标：`20%`以内。",
        f"- 结构网格：top_k `{TOP_KS}`；信号篮子总暴露 `{BASKET_GROSS_WEIGHTS}`；单行业最多 `{MAX_PER_INDUSTRY_VALUES}`只。",
        "- A/B判断：30万专属候选研究，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 30万本金下，100股整手使多标的小权重组合天然失真。",
        "- 均值回归系统的核心风险不只是信号，而是仓位大小、组合热度和亏损簇。",
        "- 因此本阶段只动组合形状，不动alpha阈值；后续必须做walk-forward验证，不能直接上线。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(["", "## 核心摘要", ""])
    if best_dd:
        lines.append(
            f"- 回撤20%以内最高收益候选：`{best_dd['scenario']}`，期末权益`{best_dd['final_equity_min_fee']:.4f}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，Sharpe `{best_dd['sharpe_min_fee']:.3f}`。"
        )
    else:
        lines.append("- 回撤20%以内候选：本轮无。")
    if best_all_pass:
        lines.append(
            f"- 全部质量项通过最高收益候选：`{best_all_pass['scenario']}`，总收益`{pct(best_all_pass['total_return_min_fee'])}`，最大回撤`{pct(best_all_pass['max_drawdown_min_fee'])}`，zero-lot `{pct(best_all_pass['zero_lot_target_ratio'])}`。"
        )
    else:
        lines.append("- 全部质量项通过候选：本轮无。")
    lines.extend(
        [
            f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
            "- 解释：这是30万账户的结构探索，不是最终策略；如果最佳候选来自更高暴露，需要单独做滚动验证和年份拆分。",
            "",
            "## 场景汇总",
            "",
            markdown_table(
                summary,
                [
                    "scenario",
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
                    "avg_actual_symbol_count",
                    "avg_actual_gross_weight",
                    "max_actual_gross_weight",
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
                max_rows=40,
            ),
            "",
            "## 年度拆分",
            "",
            markdown_table(
                yearly,
                [
                    "scenario",
                    "year",
                    "year_return_min_fee",
                    "year_curve_drawdown_min_fee",
                    "avg_actual_gross_weight",
                    "avg_actual_symbol_count",
                    "zero_lot_target_ratio",
                ],
                max_rows=160,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["scenario", "checkpoint", "status", "value", "expected", "note"], max_rows=160),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：有风险，但可控。",
            "- 原因：用户目标明确要求30万高收益且回撤20%以内，容易诱发参数搜索；本阶段只限定为账户结构参数，不改alpha信号。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：仍有风险。",
            "- 原因：即便出现高收益候选，也只是结构网格内样本内结果；必须继续做walk-forward、年份启动和假阳性审计。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：30万目标已经明确，当前大资金分散组合不适配，必须研究30万专属组合形状。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：看是否存在回撤20%以内且执行质量不差的候选。",
            "- 原因：如果有，下一步做稳健性验证；如果没有，应换信号或交易周期，而不是继续加参数。",
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
    base = read_source_candidates()
    selected_frames: list[pl.DataFrame] = []
    for top_k in TOP_KS:
        for basket_gross_weight in BASKET_GROSS_WEIGHTS:
            for max_per_industry in MAX_PER_INDUSTRY_VALUES:
                selected_frames.append(build_concentrated_selected(base, top_k, basket_gross_weight, max_per_industry))
    selected = pl.concat(selected_frames, how="vertical").sort(["scenario", "datetime", FEATURE])
    target_weights = build_target_weights(selected)
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    summaries: list[dict[str, Any]] = []
    orders_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    yearly_frames: list[pl.DataFrame] = []
    for scenario in selected["scenario"].unique().sort().to_list():
        summary, orders, daily, yearly = replay_shape(scenario, selected, target_weights, benchmark_df, exec_info)
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
            "source_scenario": SOURCE_SCENARIO,
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "top_ks": TOP_KS,
            "basket_gross_weights": BASKET_GROSS_WEIGHTS,
            "max_per_industry_values": MAX_PER_INDUSTRY_VALUES,
            "feature": FEATURE,
            "horizon": HORIZON,
            "research_sources": RESEARCH_SOURCES,
        },
    )
    report_path = write_report(summary, quality, yearly, paths)
    print(f"report={report_path}")
    print(summary)
    print(quality)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

import analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid as shape_grid
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_residual_increment_layer_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_residual_increment_layer_v1"

ACCOUNT_SIZE_CNY: float = 300_000.0
ROLLING_WINDOW: int = 252
USER_RETURN_TARGET: float = 1.0
USER_MAX_DRAWDOWN_LIMIT: float = -0.20

SHAPES: tuple[tuple[int, float, int], ...] = (
    (8, 0.50, 2),
    (5, 0.50, 2),
)

RANK_VARIANTS: tuple[dict[str, str], ...] = (
    {
        "rank_variant": "simple_ret20",
        "rank_col": "rank_simple_ret20",
        "description": "Stage332母本：裸20日超跌排序。",
    },
    {
        "rank_variant": "market_resid20",
        "rank_col": "rank_market_resid20",
        "description": "20日收益减同日候选池中位数，理论上应接近裸20日排序，用作残差管线对照。",
    },
    {
        "rank_variant": "industry_resid20",
        "rank_col": "rank_industry_resid20",
        "description": "20日收益减同行业候选池同日均值，买行业内相对更弱的短期回落。",
    },
    {
        "rank_variant": "blend_simple_industry_resid20",
        "rank_col": "rank_blend_simple_industry_resid20",
        "description": "裸20日超跌分位与行业残差超跌分位等权混合。",
    },
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Short-Term Residual Reversal PDF",
        "https://www.efmaefm.org/0EFMSYMPOSIUM/2012/papers/017_update.pdf",
    ),
    (
        "Cross-sectional mean reversion implementation note",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "Short-term reversals, turnover, and news-driven trading",
        "https://www.sciencedirect.com/science/article/pii/S0378426621000261",
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


def add_residual_rank_scores(base: pl.DataFrame) -> pl.DataFrame:
    work = (
        base.with_columns(
            pl.col("ret_20").median().over("datetime").alias("_market_median_ret20"),
            pl.col("ret_20").sum().over(["datetime", "industry"]).alias("_industry_sum_ret20"),
            pl.col("ret_20").count().over(["datetime", "industry"]).alias("_industry_count_ret20"),
        )
        .with_columns(
            pl.when(pl.col("_industry_count_ret20") > 1)
            .then((pl.col("_industry_sum_ret20") - pl.col("ret_20")) / (pl.col("_industry_count_ret20") - 1))
            .otherwise(None)
            .alias("_industry_peer_ret20")
        )
        .with_columns(
            (pl.col("ret_20") - pl.col("_market_median_ret20")).alias("market_resid_ret20"),
            (pl.col("ret_20") - pl.col("_industry_peer_ret20")).alias("industry_resid_ret20"),
            pl.col("score_oversold_ret_20").alias("rank_simple_ret20"),
            (-(pl.col("ret_20") - pl.col("_market_median_ret20"))).alias("rank_market_resid20"),
            (-(pl.col("ret_20") - pl.col("_industry_peer_ret20"))).alias("rank_industry_resid20"),
        )
        .with_columns(
            pl.col("rank_simple_ret20").rank("average").over("datetime").alias("_simple_rank"),
            pl.col("rank_industry_resid20").rank("average").over("datetime").alias("_industry_resid_rank"),
            pl.col("rank_industry_resid20").is_not_null().sum().over("datetime").alias("_industry_resid_n"),
            pl.len().over("datetime").alias("_daily_n"),
        )
        .with_columns(
            (pl.col("_simple_rank") / pl.col("_daily_n")).alias("_simple_pct"),
            pl.when(pl.col("_industry_resid_n") > 0)
            .then(pl.col("_industry_resid_rank") / pl.col("_industry_resid_n"))
            .otherwise(None)
            .alias("_industry_resid_pct"),
        )
        .with_columns(
            ((pl.col("_simple_pct") + pl.col("_industry_resid_pct")) / 2.0).alias(
                "rank_blend_simple_industry_resid20"
            )
        )
    )
    return work.drop([col for col in work.columns if col.startswith("_")])


def scenario_name(rank_variant: str, top_k: int, basket_gross_weight: float, max_per_industry: int) -> str:
    return f"{rank_variant}__top{top_k}_gross{int(basket_gross_weight * 100)}_ind{max_per_industry}"


def shape_name(top_k: int, basket_gross_weight: float, max_per_industry: int) -> str:
    return f"top{top_k}_gross{int(basket_gross_weight * 100)}_ind{max_per_industry}"


def build_ranked_selected(
    base: pl.DataFrame,
    rank_variant: str,
    rank_col: str,
    rank_description: str,
    top_k: int,
    basket_gross_weight: float,
    max_per_industry: int,
) -> pl.DataFrame:
    scenario = scenario_name(rank_variant, top_k, basket_gross_weight, max_per_industry)
    shape = shape_name(top_k, basket_gross_weight, max_per_industry)
    description = (
        f"30万残差增量层：{rank_description}；每日top{top_k}，单行业最多{max_per_industry}只，"
        f"信号篮子目标总暴露{basket_gross_weight:.0%}。"
    )
    return (
        base.filter(pl.col(rank_col).is_not_null() & pl.col(rank_col).is_finite())
        .with_columns(pl.col(rank_col).rank("ordinal", descending=True).over(["datetime", "industry"]).alias("_industry_rank"))
        .filter(pl.col("_industry_rank") <= max_per_industry)
        .with_columns(pl.col(rank_col).rank("ordinal", descending=True).over("datetime").alias("_rank_after_industry"))
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
            pl.lit("30w_residual_increment_equal").alias("weight_mode"),
            pl.lit(top_k).alias("shape_top_k"),
            pl.lit(basket_gross_weight).alias("shape_basket_gross_weight"),
            pl.lit(max_per_industry).alias("shape_max_per_industry"),
            pl.lit(shape).alias("shape_id"),
            pl.lit(rank_variant).alias("rank_variant"),
            pl.lit(rank_col).alias("rank_col"),
            pl.lit(rank_description).alias("rank_description"),
            pl.col(rank_col).alias("rank_score"),
        )
        .drop(["_industry_rank", "_rank_after_industry"])
    )


def build_all_selected(base: pl.DataFrame) -> pl.DataFrame:
    selected_frames: list[pl.DataFrame] = []
    for variant in RANK_VARIANTS:
        for top_k, basket_gross_weight, max_per_industry in SHAPES:
            selected_frames.append(
                build_ranked_selected(
                    base,
                    variant["rank_variant"],
                    variant["rank_col"],
                    variant["description"],
                    top_k,
                    basket_gross_weight,
                    max_per_industry,
                )
            )
    return pl.concat(selected_frames, how="vertical").sort(["scenario", "datetime", "rank_score"])


def replay_scenarios(selected: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    target_weights = shape_grid.build_target_weights(selected)
    stock_df, benchmark_df = shape_grid.load_panels()
    exec_info = shape_grid.build_exec_info(stock_df)

    summaries: list[dict[str, Any]] = []
    orders_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    yearly_frames: list[pl.DataFrame] = []
    for scenario in selected["scenario"].unique().sort().to_list():
        summary, orders, daily, yearly = shape_grid.replay_shape(scenario, selected, target_weights, benchmark_df, exec_info)
        meta = (
            selected.filter(pl.col("scenario") == scenario)
            .select("shape_id", "rank_variant", "rank_col", "rank_description")
            .row(0, named=True)
        )
        summary.update(meta)
        summaries.append(summary)
        if not orders.is_empty():
            orders_frames.append(orders)
        if not daily.is_empty():
            daily_frames.append(daily)
        if not yearly.is_empty():
            yearly_frames.append(yearly)

    summary = pl.DataFrame(summaries).sort(["shape_id", "rank_variant"])
    orders = pl.concat(orders_frames, how="vertical") if orders_frames else pl.DataFrame()
    daily = pl.concat(daily_frames, how="vertical") if daily_frames else pl.DataFrame()
    yearly = pl.concat(yearly_frames, how="vertical").sort(["scenario", "year"]) if yearly_frames else pl.DataFrame()
    return summary, orders, daily, yearly


def build_delta(summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("rank_variant") == "simple_ret20")
        .select(
            "shape_id",
            pl.col("scenario").alias("base_scenario"),
            pl.col("total_return_min_fee").alias("base_total_return_min_fee"),
            pl.col("max_drawdown_min_fee").alias("base_max_drawdown_min_fee"),
            pl.col("sharpe_min_fee").alias("base_sharpe_min_fee"),
            pl.col("return_over_max_dd").alias("base_return_over_max_dd"),
            pl.col("zero_lot_target_ratio").alias("base_zero_lot_target_ratio"),
            pl.col("avg_actual_symbol_count").alias("base_avg_actual_symbol_count"),
        )
    )
    return (
        summary.join(base, on="shape_id", how="left")
        .with_columns(
            (pl.col("total_return_min_fee") - pl.col("base_total_return_min_fee")).alias("delta_total_return_min_fee"),
            (pl.col("max_drawdown_min_fee") - pl.col("base_max_drawdown_min_fee")).alias("delta_max_drawdown_min_fee"),
            (pl.col("sharpe_min_fee") - pl.col("base_sharpe_min_fee")).alias("delta_sharpe_min_fee"),
            (pl.col("return_over_max_dd") - pl.col("base_return_over_max_dd")).alias("delta_return_over_max_dd"),
            (pl.col("zero_lot_target_ratio") - pl.col("base_zero_lot_target_ratio")).alias(
                "delta_zero_lot_target_ratio"
            ),
            (pl.col("avg_actual_symbol_count") - pl.col("base_avg_actual_symbol_count")).alias(
                "delta_avg_actual_symbol_count"
            ),
        )
        .with_columns(
            (
                (pl.col("delta_total_return_min_fee") > 0)
                & (pl.col("delta_max_drawdown_min_fee") >= 0)
                & (pl.col("delta_sharpe_min_fee") >= 0)
            ).alias("beats_simple_return_dd_sharpe"),
            (
                (pl.col("total_return_min_fee") >= USER_RETURN_TARGET)
                & (pl.col("max_drawdown_min_fee") >= USER_MAX_DRAWDOWN_LIMIT)
            ).alias("meets_user_goal"),
        )
        .sort(["shape_id", "rank_variant"])
    )


def rolling_window_drawdown(values: np.ndarray) -> float:
    equity = np.cumprod(1.0 + values)
    high = np.maximum.accumulate(equity)
    drawdown = equity / high - 1.0
    return float(drawdown.min())


def build_rolling(daily: pl.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if daily.is_empty():
        return pd.DataFrame(), pd.DataFrame()
    work = daily.select(
        "scenario",
        "date",
        "strategy_daily_ret_min_fee",
        "actual_gross_weight",
        "actual_symbol_count",
    ).to_pandas()
    work["date"] = pd.to_datetime(work["date"])
    rows: list[pd.DataFrame] = []
    for scenario, group in work.groupby("scenario"):
        group = group.sort_values("date").reset_index(drop=True)
        returns = group["strategy_daily_ret_min_fee"].astype(float)
        rolling_return = (1.0 + returns).rolling(ROLLING_WINDOW).apply(np.prod, raw=True) - 1.0
        rolling_dd = returns.rolling(ROLLING_WINDOW).apply(rolling_window_drawdown, raw=True)
        rolling_sharpe = returns.rolling(ROLLING_WINDOW).mean() / returns.rolling(ROLLING_WINDOW).std(ddof=1) * np.sqrt(
            252
        )
        rows.append(
            pd.DataFrame(
                {
                    "scenario": scenario,
                    "window_end": group["date"],
                    "rolling_return_252": rolling_return,
                    "rolling_drawdown_252": rolling_dd,
                    "rolling_sharpe_252": rolling_sharpe,
                    "rolling_avg_gross_weight_252": group["actual_gross_weight"].rolling(ROLLING_WINDOW).mean(),
                    "rolling_avg_symbol_count_252": group["actual_symbol_count"].rolling(ROLLING_WINDOW).mean(),
                }
            ).dropna(subset=["rolling_return_252", "rolling_drawdown_252"])
        )
    rolling = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if rolling.empty:
        return rolling, pd.DataFrame()
    aggregate = (
        rolling.groupby("scenario", as_index=False)
        .agg(
            rolling_window_count=("rolling_return_252", "count"),
            positive_rolling_return_ratio=("rolling_return_252", lambda item: float((item > 0).mean())),
            median_rolling_return=("rolling_return_252", "median"),
            worst_rolling_return=("rolling_return_252", "min"),
            median_rolling_drawdown=("rolling_drawdown_252", "median"),
            worst_rolling_drawdown=("rolling_drawdown_252", "min"),
            median_rolling_sharpe=("rolling_sharpe_252", "median"),
            pct_windows_drawdown_within_20=("rolling_drawdown_252", lambda item: float((item >= -0.20).mean())),
        )
        .sort_values("scenario")
    )
    return rolling, aggregate


def build_signal_diagnostics(selected: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    signal_cols = [
        "scenario",
        "shape_id",
        "rank_variant",
        "market_state_20d",
        "industry",
        "basket_weight",
        "ret_20",
        "market_resid_ret20",
        "industry_resid_ret20",
        "score_oversold_ret_20",
        "rank_score",
        "fwd_ret_10",
        "fwd_excess_ret_10",
        "mfe_close_10",
        "mae_close_10",
        "adv20_turnover",
    ]
    frame = selected.select([col for col in signal_cols if col in selected.columns])
    by_state = (
        frame.group_by(["scenario", "shape_id", "rank_variant", "market_state_20d"])
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("basket_weight").sum().alias("basket_weight_sum"),
            pl.col("ret_20").mean().alias("avg_ret_20"),
            pl.col("market_resid_ret20").mean().alias("avg_market_resid_ret20"),
            pl.col("industry_resid_ret20").mean().alias("avg_industry_resid_ret20"),
            pl.col("score_oversold_ret_20").mean().alias("avg_score_oversold_ret_20"),
            pl.col("rank_score").mean().alias("avg_rank_score"),
            pl.col("fwd_ret_10").mean().alias("avg_fwd_ret_10"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
            pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
            pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
        )
        .sort(["shape_id", "rank_variant", "avg_fwd_excess_ret_10"], descending=[False, False, False])
    )
    by_industry = (
        frame.group_by(["scenario", "shape_id", "rank_variant", "industry"])
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("basket_weight").sum().alias("basket_weight_sum"),
            pl.col("fwd_ret_10").mean().alias("avg_fwd_ret_10"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
            pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
            pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
        )
        .filter(pl.col("selected_rows") >= 20)
        .sort(["shape_id", "rank_variant", "avg_fwd_excess_ret_10"], descending=[False, False, False])
    )
    return by_state, by_industry


def build_quality(delta: pl.DataFrame, rolling_agg: pd.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    goal_hits = delta.filter(pl.col("meets_user_goal")).height
    top8_improvers = delta.filter(
        (pl.col("shape_id") == "top8_gross50_ind2")
        & (pl.col("rank_variant") != "simple_ret20")
        & pl.col("beats_simple_return_dd_sharpe")
    ).height
    top5_improvers = delta.filter(
        (pl.col("shape_id") == "top5_gross50_ind2")
        & (pl.col("rank_variant") != "simple_ret20")
        & pl.col("beats_simple_return_dd_sharpe")
    ).height
    rolling = pl.from_pandas(rolling_agg) if not rolling_agg.empty else pl.DataFrame()
    if not rolling.is_empty():
        rolling_delta = build_delta(
            delta.select(
                "scenario",
                "shape_id",
                "rank_variant",
                pl.col("positive_rolling_return_ratio").alias("total_return_min_fee"),
                pl.col("worst_rolling_drawdown").alias("max_drawdown_min_fee"),
                pl.col("median_rolling_sharpe").alias("sharpe_min_fee"),
                pl.lit(0.0).alias("return_over_max_dd"),
                pl.lit(0.0).alias("zero_lot_target_ratio"),
                pl.lit(0.0).alias("avg_actual_symbol_count"),
            ).join(rolling, on="scenario", how="left")
        )
        rolling_improvers = rolling_delta.filter(
            (pl.col("rank_variant") != "simple_ret20")
            & (pl.col("delta_total_return_min_fee") > 0)
            & (pl.col("delta_max_drawdown_min_fee") >= 0)
        ).height
    else:
        rolling_improvers = 0

    rows.extend(
        [
            {
                "checkpoint": "fixed_shapes_only",
                "status": "pass" if delta.select("shape_id").n_unique() == len(SHAPES) else "fail",
                "value": f"shape_count={delta.select('shape_id').n_unique()}",
                "expected": "only top8_gross50_ind2 and top5_gross50_ind2",
                "judgement": "本阶段只做母本和可交易性护栏，不扩组合形态网格。",
            },
            {
                "checkpoint": "user_goal_hit",
                "status": "pass" if goal_hits > 0 else "fail",
                "value": f"goal_hit_count={goal_hits}",
                "expected": "total_return>=100% and max_drawdown>=-20%",
                "judgement": "若为0，说明残差层还不是正式候选。",
            },
            {
                "checkpoint": "top8_residual_increment",
                "status": "pass" if top8_improvers > 0 else "fail",
                "value": f"improver_count={top8_improvers}",
                "expected": "至少一个残差/混合排序同时提升收益、回撤和Sharpe",
                "judgement": "研究母本必须相对简单超跌证明真实增益。",
            },
            {
                "checkpoint": "top5_tradability_guard_increment",
                "status": "pass" if top5_improvers > 0 else "fail",
                "value": f"improver_count={top5_improvers}",
                "expected": "至少一个残差/混合排序在top5护栏上也同向提升",
                "judgement": "如果只改善top8但恶化top5，可能只是小目标颗粒度幻觉。",
            },
            {
                "checkpoint": "rolling_increment_present",
                "status": "pass" if rolling_improvers > 0 else "warn",
                "value": f"rolling_improver_count={rolling_improvers}",
                "expected": "残差/混合排序在252日滚动正收益率和最差滚动回撤上有同向改善",
                "judgement": "滚动层面用于防止单段样本把总收益抬高。",
            },
            {
                "checkpoint": "formal_candidate_status",
                "status": "warn",
                "value": "not_formal_candidate",
                "expected": "需要后续walk-forward/年份启动反证",
                "judgement": "本阶段只是layer1，不触发A/B、不接paper、不接第78。",
            },
        ]
    )
    return pl.DataFrame(rows)


def add_delta_display(delta: pl.DataFrame) -> pl.DataFrame:
    pct_cols = [
        "total_return_min_fee",
        "max_drawdown_min_fee",
        "zero_lot_target_ratio",
        "avg_actual_gross_weight",
        "delta_total_return_min_fee",
        "delta_max_drawdown_min_fee",
        "delta_zero_lot_target_ratio",
    ]
    exprs: list[pl.Expr] = []
    for col in pct_cols:
        if col in delta.columns:
            exprs.append(pl.col(col).map_elements(pct, return_dtype=pl.Utf8).alias(f"{col}_pct"))
    return delta.with_columns(exprs) if exprs else delta


def write_report(
    summary: pl.DataFrame,
    delta: pl.DataFrame,
    quality: pl.DataFrame,
    yearly: pl.DataFrame,
    rolling_agg: pd.DataFrame,
    state: pl.DataFrame,
    industry: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    delta_display = add_delta_display(delta)
    summary_display = add_delta_display(summary)
    rolling_display = rolling_agg.copy()
    for col in (
        "positive_rolling_return_ratio",
        "median_rolling_return",
        "worst_rolling_return",
        "median_rolling_drawdown",
        "worst_rolling_drawdown",
        "pct_windows_drawdown_within_20",
    ):
        if col in rolling_display.columns:
            rolling_display[f"{col}_pct"] = rolling_display[col].map(lambda value: pct(to_float(value, float("nan"))))

    improvers = delta.filter((pl.col("rank_variant") != "simple_ret20") & pl.col("beats_simple_return_dd_sharpe"))
    best = delta.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(0, named=True)
    lines = [
        "# 股票震荡30万残差增量层 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day",
        "- line_id：`stock_range_30w_industry_resid_core`",
        "- 阶段性质：第333阶段，layer1残差增量验证，不触发A/B。",
        "- 账户规模：`300,000 CNY`。",
        "- 固定形态：`top8_gross50_ind2`研究母本、`top5_gross50_ind2`可交易性护栏。",
        "- 数据区间：沿用源候选和30万整手回放，约2018-04-20到2026-04-27。",
        "",
        "## 外部调研与判断",
        "",
        "- 残差短反文献支持先剥离共同因子/行业暴露，再观察短期反转；这符合本阶段只换排序口径的设计。",
        "- 横截面均值回归的业界模板强调相对收益而不是绝对下跌，本阶段把裸20日超跌作为母本，用市场/行业相对超跌做增量对照。",
        "- turnover/news研究提醒：高换手新闻驱动样本可能延续而不是反转，所以本阶段不因为残差文献就默认残差一定更好，必须用同形态回放反证。",
        "- 我的判断：残差层有研究价值，但只有在同时改善母本与top5护栏时，才值得进入下一层状态预算。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心结论",
            "",
            f"- 最高收益场景：`{best['scenario']}`，总收益`{pct(best['total_return_min_fee'])}`，最大回撤`{pct(best['max_drawdown_min_fee'])}`，Sharpe `{to_float(best['sharpe_min_fee']):.4f}`。",
            f"- 同时改善收益、回撤和Sharpe的残差/混合场景数：`{improvers.height}`。",
            "- 是否是重要突破：看下方质量检查；若没有top8和top5同时通过，只能算方向筛选，不算正式候选。",
            "",
            "## 场景汇总",
            "",
            markdown_table(
                summary_display,
                [
                    "scenario",
                    "shape_id",
                    "rank_variant",
                    "final_equity_min_fee",
                    "total_return_min_fee_pct",
                    "max_drawdown_min_fee_pct",
                    "sharpe_min_fee",
                    "return_over_max_dd",
                    "zero_lot_target_ratio_pct",
                    "avg_actual_symbol_count",
                    "avg_actual_gross_weight_pct",
                ],
                max_rows=80,
            ),
            "",
            "## 相对简单母本Delta",
            "",
            markdown_table(
                delta_display,
                [
                    "scenario",
                    "shape_id",
                    "rank_variant",
                    "base_scenario",
                    "delta_total_return_min_fee_pct",
                    "delta_max_drawdown_min_fee_pct",
                    "delta_sharpe_min_fee",
                    "delta_return_over_max_dd",
                    "delta_zero_lot_target_ratio_pct",
                    "beats_simple_return_dd_sharpe",
                    "meets_user_goal",
                ],
                max_rows=80,
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
                max_rows=120,
            ),
            "",
            "## 252日滚动",
            "",
            "\n无数据。\n"
            if rolling_display.empty
            else rolling_display[
                [
                    col
                    for col in [
                        "scenario",
                        "rolling_window_count",
                        "positive_rolling_return_ratio_pct",
                        "median_rolling_return_pct",
                        "worst_rolling_return_pct",
                        "median_rolling_drawdown_pct",
                        "worst_rolling_drawdown_pct",
                        "pct_windows_drawdown_within_20_pct",
                        "median_rolling_sharpe",
                    ]
                    if col in rolling_display.columns
                ]
            ].to_markdown(index=False),
            "",
            "## 市场状态画像",
            "",
            markdown_table(
                state,
                [
                    "scenario",
                    "market_state_20d",
                    "selected_rows",
                    "avg_ret_20",
                    "avg_industry_resid_ret20",
                    "avg_fwd_excess_ret_10",
                    "positive_excess_10_ratio",
                    "avg_mfe_close_10",
                    "avg_mae_close_10",
                ],
                max_rows=120,
            ),
            "",
            "## 行业尾部画像",
            "",
            markdown_table(
                industry,
                [
                    "scenario",
                    "industry",
                    "selected_rows",
                    "avg_fwd_excess_ret_10",
                    "positive_excess_10_ratio",
                    "avg_mfe_close_10",
                    "avg_mae_close_10",
                    "median_adv20_turnover",
                ],
                max_rows=120,
            ),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "judgement"], max_rows=80),
            "",
            "## 过拟合反思",
            "",
            "- 运行前判断：否，风险可控。",
            "- 运行前原因：只使用Stage332预注册的两个固定形态，排序口径只有四个，且市场残差是理论等价对照。",
            "- 运行后判断：否，但不能升级正式候选。",
            "- 运行后原因：本阶段是同形态归因，不根据结果继续扫阈值；若有改善，下一步仍要做walk-forward/年份启动反证。",
            "",
            "## 继续价值反思",
            "",
            "- 运行前判断：是。",
            "- 运行前原因：残差层直接检验股票震荡策略是否该从裸超跌转为行业内相对超跌。",
            "- 运行后判断：根据质量检查决定；若top8和top5没有共同改善，就不继续残差微调，转向状态预算或ETF卫星。",
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
    base = add_residual_rank_scores(shape_grid.read_source_candidates())
    selected = build_all_selected(base)
    summary, orders, daily, yearly = replay_scenarios(selected)
    delta = build_delta(summary)
    rolling, rolling_agg = build_rolling(daily)
    state, industry = build_signal_diagnostics(selected)
    rolling_agg_pl = pl.from_pandas(rolling_agg) if not rolling_agg.empty else pl.DataFrame()
    delta_for_quality = delta.join(rolling_agg_pl, on="scenario", how="left") if not rolling_agg_pl.is_empty() else delta
    quality = build_quality(delta_for_quality, rolling_agg)

    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "delta": OUTPUT_DIR / f"{PREFIX}_delta_vs_simple.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "rolling": OUTPUT_DIR / f"{PREFIX}_rolling_252.csv",
        "rolling_aggregate": OUTPUT_DIR / f"{PREFIX}_rolling_aggregate.csv",
        "state": OUTPUT_DIR / f"{PREFIX}_state_diagnostics.csv",
        "industry": OUTPUT_DIR / f"{PREFIX}_industry_diagnostics.csv",
        "selected": OUTPUT_DIR / f"{PREFIX}_selected.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    summary.write_csv(paths["summary"])
    delta.write_csv(paths["delta"])
    quality.write_csv(paths["quality"])
    yearly.write_csv(paths["yearly"])
    rolling.to_csv(paths["rolling"], index=False)
    rolling_agg.to_csv(paths["rolling_aggregate"], index=False)
    state.write_csv(paths["state"])
    industry.write_csv(paths["industry"])
    selected.write_csv(paths["selected"])
    orders.write_csv(paths["orders"])
    daily.write_csv(paths["daily"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "source_dir": str(shape_grid.SOURCE_DIR),
            "source_prefix": shape_grid.SOURCE_PREFIX,
            "source_scenario": shape_grid.SOURCE_SCENARIO,
            "shapes": SHAPES,
            "rank_variants": RANK_VARIANTS,
            "research_sources": RESEARCH_SOURCES,
            "line_id": "stock_range_30w_industry_resid_core",
            "stage": 333,
            "ab_triggered": False,
        },
    )
    report_path = write_report(summary, delta, quality, yearly, rolling_agg, state, industry, paths)
    print(f"report={report_path}")
    print(delta.select(["scenario", "total_return_min_fee", "max_drawdown_min_fee", "sharpe_min_fee", "delta_total_return_min_fee", "delta_max_drawdown_min_fee", "beats_simple_return_dd_sharpe"]))
    print(quality)


if __name__ == "__main__":
    main()

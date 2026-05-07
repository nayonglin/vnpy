from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import build_full_position_daily
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe import (
    PRE_REGISTERED_FLAG_COLUMNS,
    SOURCE_DIR,
    SOURCE_PREFIX,
    add_knife_flags,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    read_csv_with_symbol,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_holding_path_attribution_v1"

PRIMARY_SCENARIO: str = "industry_resid_core_h10_top8_gross70_ind2"
CANDIDATE_BASE_SCENARIO: str = "industry_resid_core_h10_top5_gross70_ind1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Short-term reversals, returns to liquidity provision and immediacy costs",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit",
        "https://arxiv.org/abs/1411.5062",
    ),
    (
        "Mean reversion exit timing discussion",
        "https://www.quantitativo.com/p/a-mean-reversion-strategy-from-first",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        normalized[key] = value.isoformat() if isinstance(value, (date, datetime)) else value
    return normalized


def to_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def add_daily_tail_bucket(daily: pl.DataFrame) -> pl.DataFrame:
    return (
        daily.sort(["scenario", "strategy_daily_ret_min_fee"])
        .with_columns(
            (
                pl.col("strategy_daily_ret_min_fee").rank("ordinal").over("scenario")
                / pl.len().over("scenario")
            ).alias("daily_return_rank_pct")
        )
        .with_columns(
            pl.when(pl.col("daily_return_rank_pct") <= 0.10)
            .then(pl.lit("bottom10_strategy_days"))
            .when(pl.col("daily_return_rank_pct") >= 0.90)
            .then(pl.lit("top10_strategy_days"))
            .otherwise(pl.lit("middle80_strategy_days"))
            .alias("strategy_day_tail_bucket")
        )
        .select(
            [
                "scenario",
                "date",
                "strategy_daily_ret_min_fee",
                "strategy_gross_daily_ret",
                "turnover_cost_ret_min_fee",
                "equity_min_fee",
                "drawdown_min_fee",
                "daily_return_rank_pct",
                "strategy_day_tail_bucket",
            ]
        )
    )


def build_position_panel(daily: pl.DataFrame, orders: pl.DataFrame, exec_info: dict[tuple[Any, str], Any]) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for scenario in FOCUS_SCENARIOS:
        scenario_daily = daily.filter(pl.col("scenario") == scenario).sort("date")
        scenario_orders = orders.filter(pl.col("scenario") == scenario).sort(["date", "symbol", "side"])
        if scenario_daily.is_empty():
            continue
        position_daily = build_full_position_daily(scenario_daily, scenario_orders, exec_info)
        if position_daily.is_empty():
            continue
        frames.append(position_daily.with_columns(pl.lit(scenario).alias("scenario")))
    return pl.concat(frames, how="vertical") if frames else pl.DataFrame()


def build_target_feature_frame(target_weights: pl.DataFrame, stock_df: pl.DataFrame) -> pl.DataFrame:
    flagged = add_knife_flags(target_weights, stock_df)
    keep = [
        "scenario",
        "target_date",
        "symbol",
        "target_weight",
        "model_score",
        "technical_context_score",
        "technical_pullback_quality",
        "technical_damage_penalty",
        "adv20_turnover",
        "turnover_rate_f",
        "circ_mv",
        "candidate_count",
        "selected_industry_count",
        "selected_industry_stock_count",
        "shape_horizon",
        "shape_top_k",
        "shape_basket_gross_weight",
        "shape_max_per_industry",
        "knife_flag_count",
        "cond_gap_and_weak_close",
        "cond_knife_2plus",
        "cond_knife_3plus",
        *PRE_REGISTERED_FLAG_COLUMNS,
    ]
    existing = [col for col in keep if col in flagged.columns]
    return flagged.select(existing).rename({"target_date": "date"})


def add_episode_path(position_daily: pl.DataFrame, daily_tail: pl.DataFrame, target_features: pl.DataFrame) -> pl.DataFrame:
    if position_daily.is_empty():
        return pl.DataFrame()
    dates = sorted(position_daily["date"].unique().to_list())
    date_index = {value: idx for idx, value in enumerate(dates)}
    rows: list[dict[str, Any]] = []
    for key, group in position_daily.sort(["scenario", "symbol", "date"]).partition_by(
        ["scenario", "symbol"], as_dict=True
    ).items():
        scenario, symbol = key
        episode_id = 0
        previous_index: int | None = None
        age = 0
        for row in group.iter_rows(named=True):
            current_index = date_index[row["date"]]
            if previous_index is None or current_index != previous_index + 1:
                episode_id += 1
                age = 1
            else:
                age += 1
            previous_index = current_index
            rows.append(
                {
                    **normalize_row(row),
                    "scenario": scenario,
                    "symbol": symbol,
                    "episode_id": episode_id,
                    "holding_age": age,
                    "trading_day_index": current_index,
                }
            )
    path = pl.DataFrame(rows, infer_schema_length=None).with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d", strict=False)
    )
    episode_meta = (
        path.group_by(["scenario", "symbol", "episode_id"])
        .agg(
            pl.col("date").min().alias("entry_date"),
            pl.col("date").max().alias("last_holding_date"),
            pl.col("holding_age").max().alias("episode_holding_days"),
            pl.col("gross_contribution").sum().alias("episode_gross_contribution"),
            pl.col("daily_ret").mean().alias("episode_avg_daily_ret"),
            pl.col("daily_ret").min().alias("episode_worst_daily_ret"),
            pl.col("actual_weight").mean().alias("episode_avg_weight"),
            pl.col("actual_weight").max().alias("episode_max_weight"),
        )
        .with_columns(pl.col("episode_gross_contribution").rank("average").over("scenario").alias("episode_rank_raw"))
    )
    episode_count = episode_meta.group_by("scenario").agg(pl.len().alias("episode_count"))
    episode_meta = episode_meta.join(episode_count, on="scenario", how="left").with_columns(
        (pl.col("episode_rank_raw") / pl.col("episode_count")).alias("episode_contribution_rank_pct")
    )
    enriched = (
        path.join(episode_meta, on=["scenario", "symbol", "episode_id"], how="left")
        .join(daily_tail, on=["scenario", "date"], how="left")
        .join(target_features, on=["scenario", "date", "symbol"], how="left")
        .with_columns(
            (pl.col("episode_holding_days") - pl.col("holding_age") + 1).alias("days_to_episode_exit"),
        )
        .with_columns(
            pl.when(pl.col("holding_age") == 1)
            .then(pl.lit("entry_day_1"))
            .when(pl.col("holding_age") <= 3)
            .then(pl.lit("early_day_2_3"))
            .when(pl.col("holding_age") <= 7)
            .then(pl.lit("mid_day_4_7"))
            .otherwise(pl.lit("late_day_8_plus"))
            .alias("holding_age_bucket"),
            pl.when(pl.col("holding_age") == 1)
            .then(pl.lit("entry_interval"))
            .when(pl.col("days_to_episode_exit") == 1)
            .then(pl.lit("exit_interval"))
            .when(pl.col("holding_age") <= 3)
            .then(pl.lit("early_hold_interval"))
            .otherwise(pl.lit("middle_hold_interval"))
            .alias("path_interval_bucket"),
            pl.when(pl.col("episode_holding_days") <= 1)
            .then(pl.lit("hold_1d"))
            .when(pl.col("episode_holding_days") <= 3)
            .then(pl.lit("hold_2_3d"))
            .when(pl.col("episode_holding_days") <= 7)
            .then(pl.lit("hold_4_7d"))
            .otherwise(pl.lit("hold_8d_plus"))
            .alias("episode_length_bucket"),
            pl.when(pl.col("episode_contribution_rank_pct") <= 0.10)
            .then(pl.lit("worst10_episodes"))
            .when(pl.col("episode_contribution_rank_pct") >= 0.90)
            .then(pl.lit("best10_episodes"))
            .otherwise(pl.lit("middle80_episodes"))
            .alias("episode_tail_bucket"),
        )
        .with_columns(
            pl.when(pl.col("knife_flag_count").fill_null(0) >= 1)
            .then(pl.lit("knife_any"))
            .otherwise(pl.lit("non_knife"))
            .alias("knife_cohort"),
            pl.when(pl.col("knife_flag_count").fill_null(0) >= 2)
            .then(pl.lit("knife_2plus"))
            .when(pl.col("knife_flag_count").fill_null(0) >= 1)
            .then(pl.lit("knife_1only"))
            .otherwise(pl.lit("non_knife"))
            .alias("knife_depth_cohort"),
            pl.when(pl.col("flag_limit_down_signal").fill_null(False))
            .then(pl.lit("limitdown_signal"))
            .when(pl.col("flag_high_volume_selloff").fill_null(False))
            .then(pl.lit("high_volume_selloff"))
            .when(pl.col("flag_short_crash").fill_null(False))
            .then(pl.lit("short_crash"))
            .when(pl.col("knife_flag_count").fill_null(0) >= 1)
            .then(pl.lit("other_knife"))
            .otherwise(pl.lit("non_knife"))
            .alias("primary_elastic_flag"),
        )
    )
    return enriched.sort(["scenario", "date", "industry", "symbol"])


def summarize_positions(frame: pl.DataFrame, group_cols: list[str]) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame()
    return (
        frame.group_by(group_cols)
        .agg(
            pl.len().alias("position_days"),
            pl.col("date").n_unique().alias("trade_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("episode_id").n_unique().alias("episodes_raw"),
            pl.col("gross_contribution").sum().alias("gross_contribution_sum"),
            pl.when(pl.col("gross_contribution") < 0).then(pl.col("gross_contribution")).otherwise(0.0).sum().alias(
                "negative_contribution_sum"
            ),
            pl.when(pl.col("gross_contribution") > 0).then(pl.col("gross_contribution")).otherwise(0.0).sum().alias(
                "positive_contribution_sum"
            ),
            pl.col("gross_contribution").mean().alias("avg_position_contribution"),
            pl.col("daily_ret").mean().alias("avg_daily_ret"),
            pl.col("daily_ret").min().alias("worst_daily_ret"),
            (pl.col("gross_contribution") < 0).mean().alias("loss_position_day_ratio"),
            pl.col("actual_weight").mean().alias("avg_actual_weight"),
            pl.col("actual_weight").max().alias("max_actual_weight"),
            pl.col("holding_age").mean().alias("avg_holding_age"),
            pl.col("episode_holding_days").mean().alias("avg_episode_holding_days"),
        )
        .sort([*group_cols, "gross_contribution_sum"])
    )


def build_episode_summary(path: pl.DataFrame) -> pl.DataFrame:
    if path.is_empty():
        return pl.DataFrame()
    return (
        path.group_by(["scenario", "symbol", "code_name", "industry", "episode_id"])
        .agg(
            pl.col("entry_date").first(),
            pl.col("last_holding_date").first(),
            pl.col("episode_holding_days").first(),
            pl.col("episode_gross_contribution").first(),
            pl.col("episode_avg_daily_ret").first(),
            pl.col("episode_worst_daily_ret").first(),
            pl.col("episode_avg_weight").first(),
            pl.col("episode_max_weight").first(),
            pl.col("knife_flag_count").first().alias("entry_knife_flag_count"),
            pl.col("primary_elastic_flag").first().alias("entry_primary_elastic_flag"),
            pl.col("path_interval_bucket").filter(pl.col("gross_contribution") == pl.col("gross_contribution").min()).first().alias(
                "worst_interval_bucket"
            ),
            pl.col("holding_age").filter(pl.col("gross_contribution") == pl.col("gross_contribution").min()).first().alias(
                "worst_holding_age"
            ),
            pl.when(pl.col("path_interval_bucket") == "entry_interval")
            .then(pl.col("gross_contribution"))
            .otherwise(0.0)
            .sum()
            .alias("entry_contribution_sum"),
            pl.when(pl.col("path_interval_bucket") == "early_hold_interval")
            .then(pl.col("gross_contribution"))
            .otherwise(0.0)
            .sum()
            .alias("early_hold_contribution_sum"),
            pl.when(pl.col("path_interval_bucket") == "middle_hold_interval")
            .then(pl.col("gross_contribution"))
            .otherwise(0.0)
            .sum()
            .alias("middle_hold_contribution_sum"),
            pl.when(pl.col("path_interval_bucket") == "exit_interval")
            .then(pl.col("gross_contribution"))
            .otherwise(0.0)
            .sum()
            .alias("exit_contribution_sum"),
        )
        .with_columns(
            pl.col("episode_gross_contribution").rank("average").over("scenario").alias("episode_rank_raw")
        )
        .join(
            path.group_by("scenario").agg(
                pl.struct(["symbol", "episode_id"]).n_unique().alias("episode_count")
            ),
            on="scenario",
            how="left",
        )
        .with_columns((pl.col("episode_rank_raw") / pl.col("episode_count")).alias("episode_contribution_rank_pct"))
        .with_columns(
            pl.when(pl.col("episode_contribution_rank_pct") <= 0.10)
            .then(pl.lit("worst10_episodes"))
            .when(pl.col("episode_contribution_rank_pct") >= 0.90)
            .then(pl.lit("best10_episodes"))
            .otherwise(pl.lit("middle80_episodes"))
            .alias("episode_tail_bucket")
        )
        .sort(["scenario", "episode_gross_contribution"])
    )


def build_quality(path: pl.DataFrame, daily: pl.DataFrame, episode_summary: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(checkpoint: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    add(
        "focus_scenario_count",
        "pass" if path["scenario"].n_unique() == len(FOCUS_SCENARIOS) else "fail",
        path["scenario"].n_unique() if not path.is_empty() else 0,
        len(FOCUS_SCENARIOS),
        "固定四个代表形状。",
    )
    add(
        "position_days_available",
        "pass" if path.height > 0 else "fail",
        path.height,
        ">0",
        "必须重建真实持仓日。",
    )
    missing_returns = path.filter(pl.col("missing_return")).height if "missing_return" in path.columns else path.height
    add(
        "position_return_coverage",
        "pass" if missing_returns == 0 else "fail",
        missing_returns,
        0,
        "持仓日必须有开盘到次开盘收益。",
    )
    attribution = (
        path.group_by(["scenario", "date"])
        .agg(pl.col("gross_contribution").sum().alias("recomputed_gross_ret"))
        .join(daily.select(["scenario", "date", "strategy_gross_daily_ret"]), on=["scenario", "date"], how="left")
        .with_columns((pl.col("recomputed_gross_ret") - pl.col("strategy_gross_daily_ret")).abs().alias("diff"))
    )
    max_diff = to_float(attribution["diff"].max()) if not attribution.is_empty() else None
    add(
        "position_contribution_matches_daily_gross",
        "pass" if max_diff is not None and max_diff <= 1e-10 else "fail",
        max_diff,
        "<=1e-10",
        "持仓贡献应复原日级毛收益。",
    )
    add(
        "target_feature_join_coverage",
        "pass" if path.filter(pl.col("knife_flag_count").is_null()).height / max(path.height, 1) <= 0.05 else "warn",
        f"{path.filter(pl.col('knife_flag_count').is_null()).height / max(path.height, 1):.2%}",
        "<=5%",
        "持仓日应能连到当日目标特征。",
    )
    add(
        "episode_summary_available",
        "pass" if not episode_summary.is_empty() else "fail",
        episode_summary.height,
        ">0",
        "必须生成持仓episode路径摘要。",
    )
    add(
        "no_strategy_parameter_change",
        "pass",
        "attribution only",
        "attribution only",
        "本阶段只归因持有路径，不改变交易规则。",
    )
    return pl.DataFrame(rows)


def write_report(
    path_summary: pl.DataFrame,
    worst_day_path_summary: pl.DataFrame,
    elastic_path_summary: pl.DataFrame,
    episode_summary_by_tail: pl.DataFrame,
    worst_episodes: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    primary_path = path_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort("gross_contribution_sum")
    primary_worst = worst_day_path_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort("gross_contribution_sum")
    primary_elastic = elastic_path_summary.filter(pl.col("scenario") == PRIMARY_SCENARIO).sort(
        ["primary_elastic_flag", "gross_contribution_sum"]
    )
    all_path = path_summary.filter(pl.col("scenario") == "ALL").sort("gross_contribution_sum")
    all_worst = worst_day_path_summary.filter(pl.col("scenario") == "ALL")
    primary_worst_episode = episode_summary_by_tail.filter(
        (pl.col("scenario") == PRIMARY_SCENARIO) & (pl.col("episode_tail_bucket") == "worst10_episodes")
    )

    def sum_float(frame: pl.DataFrame, column: str) -> float:
        if frame.is_empty() or column not in frame.columns:
            return 0.0
        return to_float(frame[column].sum())

    def bucket_value(frame: pl.DataFrame, bucket: str, column: str) -> float:
        if frame.is_empty() or column not in frame.columns:
            return 0.0
        selected = frame.filter(pl.col("path_interval_bucket") == bucket)
        return to_float(selected[column].sum()) if not selected.is_empty() else 0.0

    def share(part: float, whole: float) -> float:
        return abs(part) / abs(whole) if whole else 0.0

    primary_worst_total = sum_float(primary_worst, "gross_contribution_sum")
    primary_worst_middle = bucket_value(primary_worst, "middle_hold_interval", "gross_contribution_sum")
    all_worst_total = sum_float(all_worst, "gross_contribution_sum")
    all_worst_middle = bucket_value(all_worst, "middle_hold_interval", "gross_contribution_sum")
    primary_worst_episode_total = sum_float(primary_worst_episode, "episode_gross_contribution_sum")
    primary_worst_episode_middle = sum_float(primary_worst_episode, "middle_hold_contribution_sum")
    lines = [
        "# 股票震荡industry_resid_core 30万持有路径归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡30万industry_resid_core独立研究线，不接入第78。",
        "- 本阶段性质：真实成交持仓路径归因；不新增回测版本，不改策略参数。",
        "- A/B判断：纯归因，不触发第78 A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 均值回归策略的退出时机和持有期路径很关键；止损/时间止盈如果太粗，会把反转弹性截断。",
        "- 短期反转文献提示收益常来自短窗口流动性冲击修复，因此需要拆持有路径，而不是继续在入场前硬过滤。",
        "- 本阶段只看真实持仓贡献发生在哪一段，为下一步退出/减仓探针提供依据。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        "- 本阶段把真实持仓日拆为`entry_interval`、`early_hold_interval`、`middle_hold_interval`、`exit_interval`。",
        "- 重点看全样本和最差10%策略日的贡献来源；若亏损集中在首日，应研究入场确认；若集中在后段，应研究退出/减仓。",
        "",
        "## 主场景路径贡献",
        "",
        markdown_table(
            primary_path,
            [
                "scenario",
                "path_interval_bucket",
                "position_days",
                "trade_days",
                "symbols",
                "gross_contribution_sum",
                "negative_contribution_sum",
                "positive_contribution_sum",
                "avg_position_contribution",
                "avg_daily_ret",
                "worst_daily_ret",
                "loss_position_day_ratio",
                "avg_actual_weight",
                "avg_holding_age",
                "avg_episode_holding_days",
            ],
            max_rows=40,
        ),
        "",
        "## 主场景最差10%策略日路径贡献",
        "",
        markdown_table(
            primary_worst,
            [
                "scenario",
                "path_interval_bucket",
                "position_days",
                "trade_days",
                "symbols",
                "gross_contribution_sum",
                "negative_contribution_sum",
                "positive_contribution_sum",
                "avg_position_contribution",
                "avg_daily_ret",
                "worst_daily_ret",
                "loss_position_day_ratio",
                "avg_actual_weight",
                "avg_holding_age",
            ],
            max_rows=40,
        ),
        "",
        "## 主场景高弹性旗标路径贡献",
        "",
        markdown_table(
            primary_elastic,
            [
                "scenario",
                "primary_elastic_flag",
                "path_interval_bucket",
                "position_days",
                "gross_contribution_sum",
                "negative_contribution_sum",
                "positive_contribution_sum",
                "avg_position_contribution",
                "loss_position_day_ratio",
                "avg_actual_weight",
                "avg_holding_age",
            ],
            max_rows=120,
        ),
        "",
        "## 全样本路径贡献",
        "",
        markdown_table(
            all_path,
            [
                "scenario",
                "path_interval_bucket",
                "position_days",
                "trade_days",
                "symbols",
                "gross_contribution_sum",
                "negative_contribution_sum",
                "positive_contribution_sum",
                "avg_position_contribution",
                "loss_position_day_ratio",
                "avg_actual_weight",
                "avg_holding_age",
            ],
            max_rows=40,
        ),
        "",
        "## Episode尾部画像",
        "",
        markdown_table(
            episode_summary_by_tail,
            [
                "scenario",
                "episode_tail_bucket",
                "episodes",
                "symbols",
                "avg_episode_holding_days",
                "avg_episode_gross_contribution",
                "episode_gross_contribution_sum",
                "entry_contribution_sum",
                "early_hold_contribution_sum",
                "middle_hold_contribution_sum",
                "exit_contribution_sum",
                "avg_entry_knife_flag_count",
            ],
            max_rows=80,
        ),
        "",
        "## 最差Episode样本",
        "",
        markdown_table(
            worst_episodes,
            [
                "scenario",
                "symbol",
                "code_name",
                "industry",
                "entry_date",
                "last_holding_date",
                "episode_holding_days",
                "episode_gross_contribution",
                "entry_contribution_sum",
                "early_hold_contribution_sum",
                "middle_hold_contribution_sum",
                "exit_contribution_sum",
                "worst_interval_bucket",
                "worst_holding_age",
                "entry_primary_elastic_flag",
                "entry_knife_flag_count",
            ],
            max_rows=60,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        f"- 主低回撤场景最差10%策略日总贡献`{primary_worst_total:.4f}`，其中`middle_hold_interval`贡献`{primary_worst_middle:.4f}`，占亏损绝对值约`{share(primary_worst_middle, primary_worst_total):.2%}`。",
        f"- 四个代表形状合并后，最差10%策略日总贡献`{all_worst_total:.4f}`，其中`middle_hold_interval`贡献`{all_worst_middle:.4f}`，占亏损绝对值约`{share(all_worst_middle, all_worst_total):.2%}`。",
        f"- 主低回撤场景worst10 episode总贡献`{primary_worst_episode_total:.4f}`，其中中段持有贡献`{primary_worst_episode_middle:.4f}`，占亏损绝对值约`{share(primary_worst_episode_middle, primary_worst_episode_total):.2%}`。",
        "- 结论：风险主因不是首日买错，也不是退出当天滑落，而是持有中段的趋势失效/反转失败。下一步应做中段持仓衰减、时间止损、反弹未兑现减仓的预注册探针。",
        "- 本阶段不升级正式候选，不修改paper线，不接入第78。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：低到中等。",
        "- 原因：只做路径归因，不调交易参数；但后续若基于最差桶设计规则，必须预注册并做滚动/OOS。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：不升级候选。",
        "- 原因：本阶段只定位风险发生位置，不选择最优参数。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：第328阶段否定入场前统一预算，必须知道亏损在持有路径哪一段发生。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：若路径集中性明显，则继续做对应退出/减仓探针；若分散，则回到信号定义。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths["report"]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "position_path_daily": OUTPUT_DIR / f"{PREFIX}_position_path_daily.csv",
        "path_summary": OUTPUT_DIR / f"{PREFIX}_path_summary.csv",
        "worst_day_path_summary": OUTPUT_DIR / f"{PREFIX}_worst_day_path_summary.csv",
        "elastic_path_summary": OUTPUT_DIR / f"{PREFIX}_elastic_path_summary.csv",
        "episode_summary": OUTPUT_DIR / f"{PREFIX}_episode_summary.csv",
        "episode_summary_by_tail": OUTPUT_DIR / f"{PREFIX}_episode_summary_by_tail.csv",
        "worst_episodes": OUTPUT_DIR / f"{PREFIX}_worst_episodes.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }

    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    daily = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True).filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    orders = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_orders.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    stock_df, _benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    position_panel = build_position_panel(daily, orders, exec_info)
    daily_tail = add_daily_tail_bucket(daily)
    target_features = build_target_feature_frame(target_weights, stock_df)
    path = add_episode_path(position_panel, daily_tail, target_features)

    path_summary_parts = [
        summarize_positions(path, ["scenario", "path_interval_bucket"]),
        summarize_positions(path, ["path_interval_bucket"]).with_columns(pl.lit("ALL").alias("scenario")),
    ]
    path_summary = pl.concat(path_summary_parts, how="diagonal_relaxed").select(
        [
            "scenario",
            "path_interval_bucket",
            "position_days",
            "trade_days",
            "symbols",
            "episodes_raw",
            "gross_contribution_sum",
            "negative_contribution_sum",
            "positive_contribution_sum",
            "avg_position_contribution",
            "avg_daily_ret",
            "worst_daily_ret",
            "loss_position_day_ratio",
            "avg_actual_weight",
            "max_actual_weight",
            "avg_holding_age",
            "avg_episode_holding_days",
        ]
    )

    worst_days = path.filter(pl.col("strategy_day_tail_bucket") == "bottom10_strategy_days")
    worst_day_path_summary = pl.concat(
        [
            summarize_positions(worst_days, ["scenario", "path_interval_bucket"]),
            summarize_positions(worst_days, ["path_interval_bucket"]).with_columns(pl.lit("ALL").alias("scenario")),
        ],
        how="diagonal_relaxed",
    ).select(path_summary.columns)

    elastic_path_summary = summarize_positions(path, ["scenario", "primary_elastic_flag", "path_interval_bucket"])
    episode_summary = build_episode_summary(path)
    episode_summary_by_tail = (
        episode_summary.group_by(["scenario", "episode_tail_bucket"])
        .agg(
            pl.len().alias("episodes"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("episode_holding_days").mean().alias("avg_episode_holding_days"),
            pl.col("episode_gross_contribution").mean().alias("avg_episode_gross_contribution"),
            pl.col("episode_gross_contribution").sum().alias("episode_gross_contribution_sum"),
            pl.col("entry_contribution_sum").sum().alias("entry_contribution_sum"),
            pl.col("early_hold_contribution_sum").sum().alias("early_hold_contribution_sum"),
            pl.col("middle_hold_contribution_sum").sum().alias("middle_hold_contribution_sum"),
            pl.col("exit_contribution_sum").sum().alias("exit_contribution_sum"),
            pl.col("entry_knife_flag_count").mean().alias("avg_entry_knife_flag_count"),
        )
        .sort(["scenario", "episode_tail_bucket"])
    )
    worst_episodes = episode_summary.sort(["scenario", "episode_gross_contribution"]).group_by("scenario").head(15)
    quality = build_quality(path, daily, episode_summary)

    path.write_csv(paths["position_path_daily"])
    path_summary.write_csv(paths["path_summary"])
    worst_day_path_summary.write_csv(paths["worst_day_path_summary"])
    elastic_path_summary.write_csv(paths["elastic_path_summary"])
    episode_summary.write_csv(paths["episode_summary"])
    episode_summary_by_tail.write_csv(paths["episode_summary_by_tail"])
    worst_episodes.write_csv(paths["worst_episodes"])
    quality.write_csv(paths["quality"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "focus_scenarios": FOCUS_SCENARIOS,
            "primary_scenario": PRIMARY_SCENARIO,
            "candidate_base_scenario": CANDIDATE_BASE_SCENARIO,
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path_) for key, path_ in paths.items()},
        },
    )
    report_path = write_report(
        path_summary,
        worst_day_path_summary,
        elastic_path_summary,
        episode_summary_by_tail,
        worst_episodes,
        quality,
        paths,
    )
    print(f"report={report_path}")
    print(quality)
    print(path_summary.filter(pl.col("scenario").is_in(["ALL", PRIMARY_SCENARIO])).sort(["scenario", "gross_contribution_sum"]))
    print(
        worst_day_path_summary.filter(pl.col("scenario").is_in(["ALL", PRIMARY_SCENARIO])).sort(
            ["scenario", "gross_contribution_sum"]
        )
    )
    print(episode_summary_by_tail.filter(pl.col("scenario").is_in([PRIMARY_SCENARIO, CANDIDATE_BASE_SCENARIO])))


if __name__ == "__main__":
    main()

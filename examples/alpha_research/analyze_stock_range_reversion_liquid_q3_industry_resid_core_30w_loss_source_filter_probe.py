from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    summarize_daily_extra,
    to_float,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    read_csv_with_symbol,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_v1"

CANDIDATE_BASE_SCENARIO: str = "industry_resid_core_h10_top5_gross70_ind1"
STAGE323_WEAK_INDUSTRIES: tuple[str, ...] = ("软件服务", "建筑工程")
SELECTED_SCORE_TOP_BUCKET: str = "selected_score_top20"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Short-Term Return Reversal decomposition",
        "https://therobusttrader.com/short-term-reversal-effect-in-stocks/",
    ),
    (
        "Backtesting a Cross-Sectional Mean Reversion Strategy in Python",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "Mean Reversion Trading risk management",
        "https://www.tradewink.com/learn/mean-reversion-trading-strategy",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


@dataclass(frozen=True)
class FilterProbe:
    name: str
    description: str
    weak_industry_scale: float | None = None
    drop_score_top20: bool = False


FILTER_PROBES: tuple[FilterProbe, ...] = (
    FilterProbe(
        name="half_stage323_weak_industries",
        description="Stage323弱贡献行业`软件服务/建筑工程`目标权重减半，不把释放现金再分配。",
        weak_industry_scale=0.50,
    ),
    FilterProbe(
        name="drop_stage323_weak_industries",
        description="剔除Stage323弱贡献行业`软件服务/建筑工程`，不把释放现金再分配。",
        weak_industry_scale=0.00,
    ),
    FilterProbe(
        name="drop_selected_score_top20",
        description="剔除每个目标日选中股票内部模型分数最高20%桶，验证高分桶是否反而带来尾部风险。",
        drop_score_top20=True,
    ),
    FilterProbe(
        name="drop_score_top20_and_weak_industries",
        description="同时剔除选中分数最高20%桶与Stage323弱贡献行业，不把释放现金再分配。",
        weak_industry_scale=0.00,
        drop_score_top20=True,
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def normalize_summary_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (date, datetime)):
            normalized[key] = value.isoformat()
        else:
            normalized[key] = value
    return normalized


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def add_selected_score_bucket(target_weights: pl.DataFrame) -> pl.DataFrame:
    return (
        target_weights.with_columns(
            (
                pl.col("model_score").rank("average").over(["scenario", "target_date"])
                / pl.len().over(["scenario", "target_date"])
            ).alias("selected_score_rank_pct")
        )
        .with_columns(
            pl.when(pl.col("selected_score_rank_pct") >= 0.80)
            .then(pl.lit("selected_score_top20"))
            .when(pl.col("selected_score_rank_pct") >= 0.50)
            .then(pl.lit("selected_score_mid"))
            .otherwise(pl.lit("selected_score_low"))
            .alias("selected_score_bucket")
        )
    )


def build_stock_next_open_returns(stock_df: pl.DataFrame) -> pl.DataFrame:
    return (
        stock_df.select(["datetime", "symbol", "trade_open"])
        .sort(["symbol", "datetime"])
        .with_columns(pl.col("trade_open").shift(-1).over("symbol").alias("next_trade_open"))
        .with_columns(
            pl.when(
                pl.col("trade_open").is_not_null()
                & (pl.col("trade_open") > 0)
                & pl.col("next_trade_open").is_not_null()
                & (pl.col("next_trade_open") > 0)
            )
            .then(pl.col("next_trade_open") / pl.col("trade_open") - 1.0)
            .otherwise(None)
            .alias("open_to_next_open_ret")
        )
        .select(["datetime", "symbol", "open_to_next_open_ret"])
    )


def build_daily_tail_bucket(base_daily: pl.DataFrame) -> pl.DataFrame:
    return (
        base_daily.sort(["scenario", "strategy_daily_ret_min_fee"])
        .with_columns(
            (pl.col("strategy_daily_ret_min_fee").rank("ordinal").over("scenario") / pl.len().over("scenario")).alias(
                "daily_return_rank_pct"
            )
        )
        .with_columns(
            pl.when(pl.col("daily_return_rank_pct") <= 0.10)
            .then(pl.lit("bottom10_loss_days"))
            .when(pl.col("daily_return_rank_pct") >= 0.90)
            .then(pl.lit("top10_win_days"))
            .otherwise(pl.lit("middle80_days"))
            .alias("daily_tail_bucket")
        )
        .select(
            [
                "scenario",
                pl.col("date").alias("target_date"),
                "strategy_daily_ret_min_fee",
                "daily_return_rank_pct",
                "daily_tail_bucket",
            ]
        )
    )


def build_target_contribution_frame(
    target_weights: pl.DataFrame,
    base_daily: pl.DataFrame,
    stock_df: pl.DataFrame,
) -> pl.DataFrame:
    stock_ret = build_stock_next_open_returns(stock_df)
    tail = build_daily_tail_bucket(base_daily)
    return (
        add_selected_score_bucket(target_weights)
        .join(stock_ret, left_on=["target_date", "symbol"], right_on=["datetime", "symbol"], how="left")
        .join(tail, on=["scenario", "target_date"], how="left")
        .with_columns(
            (pl.col("target_weight") * pl.col("open_to_next_open_ret").fill_null(0.0)).alias("raw_target_contribution"),
            pl.col("open_to_next_open_ret").fill_null(0.0).alias("open_to_next_open_ret_filled"),
        )
    )


def grouped_contribution(frame: pl.DataFrame, group_cols: list[str]) -> pl.DataFrame:
    if frame.is_empty():
        return pl.DataFrame()
    return (
        frame.group_by(group_cols)
        .agg(
            pl.len().alias("target_rows"),
            pl.col("target_date").n_unique().alias("target_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("raw_target_contribution").sum().alias("raw_contribution_sum"),
            pl.col("open_to_next_open_ret_filled").mean().alias("avg_open_to_next_open_ret"),
            (pl.col("open_to_next_open_ret_filled") > 0).mean().alias("positive_row_ratio"),
            pl.col("target_weight").sum().alias("target_weight_sum"),
            pl.col("model_score").mean().alias("avg_model_score"),
            pl.col("technical_context_score").mean().alias("avg_technical_context_score"),
            pl.col("technical_pullback_quality").mean().alias("avg_pullback_quality"),
            pl.col("technical_damage_penalty").mean().alias("avg_damage_penalty"),
        )
        .sort(group_cols)
    )


def build_loss_source_tables(contrib: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    industry = grouped_contribution(contrib, ["scenario", "daily_tail_bucket", "industry"]).sort(
        ["scenario", "daily_tail_bucket", "raw_contribution_sum"]
    )
    score = grouped_contribution(contrib, ["scenario", "daily_tail_bucket", "selected_score_bucket"]).sort(
        ["scenario", "daily_tail_bucket", "raw_contribution_sum"]
    )
    signal = (
        contrib.group_by(["scenario", "daily_tail_bucket"])
        .agg(
            pl.len().alias("target_rows"),
            pl.col("target_date").n_unique().alias("target_days"),
            pl.col("raw_target_contribution").sum().alias("raw_contribution_sum"),
            pl.col("open_to_next_open_ret_filled").mean().alias("avg_open_to_next_open_ret"),
            (pl.col("open_to_next_open_ret_filled") > 0).mean().alias("positive_row_ratio"),
            pl.col("model_score").mean().alias("avg_model_score"),
            pl.col("technical_context_score").mean().alias("avg_technical_context_score"),
            pl.col("technical_pullback_quality").mean().alias("avg_pullback_quality"),
            pl.col("technical_damage_penalty").mean().alias("avg_damage_penalty"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
            pl.col("turnover_rate_f").median().alias("median_turnover_rate_f"),
            pl.col("circ_mv").median().alias("median_circ_mv"),
        )
        .sort(["scenario", "daily_tail_bucket"])
    )
    return industry, score, signal


def apply_filter_probe(target_weights: pl.DataFrame, probe: FilterProbe) -> tuple[pl.DataFrame, pl.DataFrame]:
    work = add_selected_score_bucket(target_weights)
    multiplier = pl.lit(1.0)
    if probe.weak_industry_scale is not None:
        multiplier = pl.when(pl.col("industry").is_in(STAGE323_WEAK_INDUSTRIES)).then(
            pl.lit(probe.weak_industry_scale)
        ).otherwise(multiplier)
    if probe.drop_score_top20:
        multiplier = pl.when(pl.col("selected_score_bucket") == SELECTED_SCORE_TOP_BUCKET).then(pl.lit(0.0)).otherwise(
            multiplier
        )
    scaled = (
        work.with_columns(
            pl.col("target_weight").alias("base_target_weight"),
            multiplier.alias("filter_weight_multiplier"),
            (pl.col("target_weight") * multiplier).alias("target_weight"),
            pl.lit(probe.name).alias("filter_probe_name"),
            pl.lit(probe.description).alias("filter_probe_description"),
        )
        .filter(pl.col("target_weight") > 0)
        .sort(["target_date", "symbol"])
    )
    scale_daily = (
        work.with_columns(multiplier.alias("filter_weight_multiplier"))
        .group_by(["scenario", "target_date"])
        .agg(
            pl.col("target_weight").sum().alias("base_target_gross_weight"),
            (pl.col("target_weight") * pl.col("filter_weight_multiplier")).sum().alias("filtered_target_gross_weight"),
            (pl.col("filter_weight_multiplier") < 0.999999).sum().alias("filtered_row_count"),
            pl.len().alias("base_row_count"),
        )
        .with_columns(
            pl.lit(probe.name).alias("filter_probe_name"),
            (pl.col("filtered_row_count") / pl.col("base_row_count")).alias("filtered_row_ratio"),
        )
    )
    return scaled, scale_daily


def add_base_deltas(summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("filter_probe_name") == "base_rerun")
        .select(
            "base_scenario",
            pl.col("final_equity_min_fee").alias("base_final_equity_min_fee"),
            pl.col("total_return_min_fee").alias("base_total_return_min_fee"),
            pl.col("max_drawdown_min_fee").alias("base_max_drawdown_min_fee"),
            pl.col("sharpe_min_fee").alias("base_sharpe_min_fee"),
            pl.col("avg_actual_gross_weight").alias("base_avg_actual_gross_weight"),
        )
    )
    return (
        summary.join(base, on="base_scenario", how="left")
        .with_columns(
            (pl.col("final_equity_min_fee") - pl.col("base_final_equity_min_fee")).alias("delta_final_equity_min_fee"),
            (pl.col("total_return_min_fee") - pl.col("base_total_return_min_fee")).alias("delta_total_return_min_fee"),
            (pl.col("max_drawdown_min_fee") - pl.col("base_max_drawdown_min_fee")).alias("delta_max_drawdown_min_fee"),
            (pl.col("sharpe_min_fee") - pl.col("base_sharpe_min_fee")).alias("delta_sharpe_min_fee"),
            (pl.col("avg_actual_gross_weight") - pl.col("base_avg_actual_gross_weight")).alias(
                "delta_avg_actual_gross_weight"
            ),
        )
        .drop(
            [
                "base_final_equity_min_fee",
                "base_total_return_min_fee",
                "base_max_drawdown_min_fee",
                "base_sharpe_min_fee",
                "base_avg_actual_gross_weight",
            ]
        )
    )


def build_quality(summary: pl.DataFrame, loss_industry: pl.DataFrame, loss_score: pl.DataFrame) -> pl.DataFrame:
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

    stress = summary.filter(pl.col("filter_probe_name") != "base_rerun")
    improve_dd = stress.filter(pl.col("delta_max_drawdown_min_fee") > 0)
    improve_both = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    candidate = stress.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO)
    candidate_target = candidate.filter(
        (pl.col("total_return_min_fee") >= HIGH_RETURN_TARGET) & (pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT)
    )
    add(
        "focus_scenario_count",
        "pass" if summary["base_scenario"].n_unique() == len(FOCUS_SCENARIOS) else "fail",
        summary["base_scenario"].n_unique(),
        len(FOCUS_SCENARIOS),
        "固定四个代表形状。",
    )
    add(
        "filter_probe_count",
        "pass" if stress["filter_probe_name"].n_unique() == len(FILTER_PROBES) else "fail",
        stress["filter_probe_name"].n_unique(),
        len(FILTER_PROBES),
        "只运行预注册减亏过滤探针。",
    )
    add(
        "loss_source_industry_available",
        "pass" if not loss_industry.is_empty() else "fail",
        loss_industry.height,
        ">0",
        "必须生成前10%亏损日行业来源。",
    )
    add(
        "loss_source_score_available",
        "pass" if not loss_score.is_empty() else "fail",
        loss_score.height,
        ">0",
        "必须生成前10%亏损日分数桶来源。",
    )
    add(
        "any_filter_improves_drawdown",
        "pass" if not improve_dd.is_empty() else "warn",
        f"{improve_dd.height}/{stress.height}",
        ">0",
        "信号层过滤至少应改善部分回撤。",
    )
    add(
        "any_filter_improves_return_and_drawdown",
        "pass" if not improve_both.is_empty() else "warn",
        f"{improve_both.height}/{stress.height}",
        ">0",
        "若只是降仓改善回撤但收益下降，不能作为高收益候选。",
    )
    add(
        "candidate_high_return_and_within_20pct",
        "pass" if not candidate_target.is_empty() else "warn",
        f"{candidate_target.height}/{candidate.height}",
        ">0",
        "30万目标是高收益且回撤20%以内。",
    )
    add(
        "no_reallocation_of_freed_cash",
        "pass",
        "cash freed",
        "cash freed",
        "本阶段过滤不把释放现金重分配，避免把行业/分数过滤伪装成加仓。",
    )
    add(
        "exploratory_same_sample_filter",
        "warn",
        "same-sample probe",
        "needs OOS before candidate",
        "弱行业和分数桶来自同样本归因，只能作为探针。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: pl.DataFrame,
    loss_industry: pl.DataFrame,
    loss_score: pl.DataFrame,
    loss_signal: pl.DataFrame,
    scale_daily: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    stress = summary.filter(pl.col("filter_probe_name") != "base_rerun")
    best_return = stress.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    best_dd = stress.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(0, named=True)
    improve_both = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    candidate = stress.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO)
    candidate_best = candidate.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    lines = [
        "# 股票震荡industry_resid_core 30万亏损来源/信号层过滤探针 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡30万industry_resid_core独立研究线，不接入第78。",
        "- 本阶段性质：拆前10%亏损日来源，并测试少数减亏型行业/分数过滤探针。",
        f"- 账户规模：`{lot.ACCOUNT_SIZE_CNY:,.0f}`元；过滤释放现金不重分配。",
        "- A/B判断：独立研究线归因/探针，不触发第78 A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 短期反转文献强调残差和行业内结构，普通反转容易带有动态因子/行业暴露。",
        "- 均值回归最大风险是买到继续下跌的“接刀子”样本；因此比起状态加仓，先处理尾部亏损来源更接近本质。",
        "- 本阶段不发明新alpha，只验证Stage323暴露出的弱行业和分数桶是否能减少尾部。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        f"- 同时改善收益和回撤的过滤探针：`{improve_both.height}/{stress.height}`。",
        f"- 收益最高过滤探针：`{best_return['scenario']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`，Sharpe `{best_return['sharpe_min_fee']:.3f}`。",
        f"- 回撤最浅过滤探针：`{best_dd['scenario']}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，Sharpe `{best_dd['sharpe_min_fee']:.3f}`。",
        f"- 第320候选形状回撤最浅过滤：`{candidate_best['filter_probe_name']}`，总收益`{pct(candidate_best['total_return_min_fee'])}`，最大回撤`{pct(candidate_best['max_drawdown_min_fee'])}`。",
        "",
        "## 前10%亏损日行业来源",
        "",
        markdown_table(
            loss_industry.filter(pl.col("daily_tail_bucket") == "bottom10_loss_days").sort(
                ["scenario", "raw_contribution_sum"]
            ),
            [
                "scenario",
                "industry",
                "target_rows",
                "target_days",
                "symbols",
                "raw_contribution_sum",
                "avg_open_to_next_open_ret",
                "positive_row_ratio",
                "avg_model_score",
                "avg_technical_context_score",
                "avg_pullback_quality",
                "avg_damage_penalty",
            ],
            max_rows=80,
        ),
        "",
        "## 前10%亏损日分数桶来源",
        "",
        markdown_table(
            loss_score.filter(pl.col("daily_tail_bucket") == "bottom10_loss_days").sort(
                ["scenario", "raw_contribution_sum"]
            ),
            [
                "scenario",
                "selected_score_bucket",
                "target_rows",
                "target_days",
                "symbols",
                "raw_contribution_sum",
                "avg_open_to_next_open_ret",
                "positive_row_ratio",
                "avg_model_score",
                "avg_technical_context_score",
                "avg_pullback_quality",
                "avg_damage_penalty",
            ],
            max_rows=80,
        ),
        "",
        "## 亏损/盈利日信号画像",
        "",
        markdown_table(
            loss_signal,
            [
                "scenario",
                "daily_tail_bucket",
                "target_rows",
                "target_days",
                "raw_contribution_sum",
                "avg_open_to_next_open_ret",
                "positive_row_ratio",
                "avg_model_score",
                "avg_technical_context_score",
                "avg_pullback_quality",
                "avg_damage_penalty",
                "median_adv20_turnover",
                "median_turnover_rate_f",
                "median_circ_mv",
            ],
            max_rows=80,
        ),
        "",
        "## 过滤探针汇总",
        "",
        markdown_table(
            summary,
            [
                "base_scenario",
                "filter_probe_name",
                "final_equity_min_fee",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "avg_actual_gross_weight",
                "avg_filtered_target_gross_weight",
                "avg_filtered_row_ratio",
                "return_over_max_dd",
            ],
            max_rows=120,
        ),
        "",
        "## 过滤日统计",
        "",
        markdown_table(
            scale_daily.group_by(["base_scenario", "filter_probe_name"]).agg(
                pl.col("base_target_gross_weight").mean().alias("avg_base_target_gross_weight"),
                pl.col("filtered_target_gross_weight").mean().alias("avg_filtered_target_gross_weight"),
                pl.col("filtered_row_ratio").mean().alias("avg_filtered_row_ratio"),
                pl.col("filtered_row_count").sum().alias("filtered_row_count_sum"),
                pl.col("base_row_count").sum().alias("base_row_count_sum"),
            ),
            [
                "base_scenario",
                "filter_probe_name",
                "avg_base_target_gross_weight",
                "avg_filtered_target_gross_weight",
                "avg_filtered_row_ratio",
                "filtered_row_count_sum",
                "base_row_count_sum",
            ],
            max_rows=80,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        "- 若过滤只降低回撤同时明显降低收益，说明问题不是某个行业/分数桶能简单剔除。",
        "- 若剔除高分桶改善，说明当前模型分数不是仓位权重函数，应回到因子定义而不是继续加仓。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：中等偏高。",
        "- 原因：弱行业和分数桶来自同样本收益来源归因，因此本阶段只能是探针。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：根据质量检查，不直接升级候选。",
        "- 原因：同样本过滤即使改善，也必须后续做滚动/OOS。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：Stage323已经否定粗粒度加仓，下一步必须拆亏损尾部。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：若没有同向改善，则转向重新定义信号；若有同向改善，再做OOS。",
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
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "loss_industry": OUTPUT_DIR / f"{PREFIX}_loss_industry.csv",
        "loss_score": OUTPUT_DIR / f"{PREFIX}_loss_score.csv",
        "loss_signal": OUTPUT_DIR / f"{PREFIX}_loss_signal.csv",
        "scale_daily": OUTPUT_DIR / f"{PREFIX}_scale_daily.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }

    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    base_daily = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True).filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    base_summary = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_summary.csv", try_parse_dates=True).filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    contrib = build_target_contribution_frame(target_weights, base_daily, stock_df)
    loss_industry, loss_score, loss_signal = build_loss_source_tables(contrib)

    summary_rows: list[dict[str, Any]] = []
    orders_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    scale_frames: list[pl.DataFrame] = []
    for row in base_summary.iter_rows(named=True):
        base_scenario = str(row["scenario"])
        base_row = dict(row)
        base_row["base_scenario"] = base_scenario
        base_row["filter_probe_name"] = "base_rerun"
        base_row["filter_probe_description"] = "不做信号层过滤。"
        base_row["avg_filtered_target_gross_weight"] = base_row.get("shape_basket_gross_weight")
        base_row["avg_filtered_row_ratio"] = 0.0
        summary_rows.append(normalize_summary_row(base_row))

    for base_scenario in FOCUS_SCENARIOS:
        scenario_targets = target_weights.filter(pl.col("scenario") == base_scenario)
        original_dates = lot.build_tracking_dates(scenario_targets.drop("scenario"), benchmark_df)
        for probe in FILTER_PROBES:
            filtered_targets, scale_daily = apply_filter_probe(scenario_targets, probe)
            target_maps = lot.build_target_maps(filtered_targets.drop("scenario"))
            orders, daily, _curves = lot.replay_lot_account(target_maps, original_dates, exec_info)
            scenario_name = f"{base_scenario}_{probe.name}"
            orders = orders.with_columns(
                pl.lit(scenario_name).alias("scenario"),
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(probe.name).alias("filter_probe_name"),
            )
            daily = daily.with_columns(
                pl.lit(scenario_name).alias("scenario"),
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(probe.name).alias("filter_probe_name"),
            )
            scale_daily = scale_daily.with_columns(
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(probe.description).alias("filter_probe_description"),
            )
            summary = lot.summarize_orders(orders, daily)
            summary = summarize_daily_extra(summary, daily)
            summary.update(
                {
                    "scenario": scenario_name,
                    "base_scenario": base_scenario,
                    "filter_probe_name": probe.name,
                    "filter_probe_description": probe.description,
                    "avg_filtered_target_gross_weight": to_float(scale_daily["filtered_target_gross_weight"].mean()),
                    "avg_base_target_gross_weight": to_float(scale_daily["base_target_gross_weight"].mean()),
                    "avg_filtered_row_ratio": to_float(scale_daily["filtered_row_ratio"].mean()),
                    "max_filtered_target_gross_weight": to_float(scale_daily["filtered_target_gross_weight"].max()),
                }
            )
            summary_rows.append(normalize_summary_row(summary))
            orders_frames.append(orders)
            daily_frames.append(daily)
            scale_frames.append(scale_daily)

    summary = add_base_deltas(pl.DataFrame(summary_rows, infer_schema_length=None)).sort(
        ["base_scenario", "filter_probe_name"]
    )
    orders_all = pl.concat(orders_frames, how="diagonal_relaxed") if orders_frames else pl.DataFrame()
    daily_all = pl.concat(daily_frames, how="diagonal_relaxed") if daily_frames else pl.DataFrame()
    scale_all = pl.concat(scale_frames, how="diagonal_relaxed") if scale_frames else pl.DataFrame()
    quality = build_quality(summary, loss_industry, loss_score)
    report_path = write_report(summary, loss_industry, loss_score, loss_signal, scale_all, quality, paths)

    summary.write_csv(paths["summary"])
    loss_industry.write_csv(paths["loss_industry"])
    loss_score.write_csv(paths["loss_score"])
    loss_signal.write_csv(paths["loss_signal"])
    scale_all.write_csv(paths["scale_daily"])
    daily_all.write_csv(paths["daily"])
    orders_all.write_csv(paths["orders"])
    quality.write_csv(paths["quality"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "focus_scenarios": FOCUS_SCENARIOS,
            "candidate_base_scenario": CANDIDATE_BASE_SCENARIO,
            "stage323_weak_industries": STAGE323_WEAK_INDUSTRIES,
            "selected_score_top_bucket": SELECTED_SCORE_TOP_BUCKET,
            "filter_probes": [
                {
                    "name": item.name,
                    "description": item.description,
                    "weak_industry_scale": item.weak_industry_scale,
                    "drop_score_top20": item.drop_score_top20,
                }
                for item in FILTER_PROBES
            ],
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    print(f"report={report_path}")
    print(quality)
    print(
        summary.select(
            [
                "base_scenario",
                "filter_probe_name",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "avg_actual_gross_weight",
                "avg_filtered_target_gross_weight",
                "avg_filtered_row_ratio",
            ]
        )
    )


if __name__ == "__main__":
    main()

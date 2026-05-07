from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
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
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe import (
    BASE_FILTER_NAME,
    CANDIDATE_BASE_SCENARIO,
    PRIMARY_SCENARIO,
    ROLLING_WINDOWS,
    SOURCE_DIR,
    SOURCE_PREFIX,
    add_base_deltas,
    add_knife_flags,
    build_delta,
    build_rolling_summary,
    build_scorecard,
    build_segment_summary,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    read_csv_with_symbol,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term reversals, returns to liquidity provision and immediacy costs",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Volatility-adjusted position sizing discussion",
        "https://breakingalpha.io/insights/volatility-adjusted-position-sizing",
    ),
    (
        "Trade sizing techniques for drawdown and tail risk control",
        "https://libertyroadcapital.com/trade-sizing-techniques-for-drawdown-and-tail-risk-control/",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


@dataclass(frozen=True)
class TailControl:
    name: str
    description: str
    soft_knife_any: float | None = None
    soft_knife_2plus: float | None = None
    soft_limit_down: float | None = None
    soft_high_volume: float | None = None
    cap_knife_2plus_daily: float | None = None
    cap_limit_down_daily: float | None = None
    cap_high_volume_daily: float | None = None


TAIL_CONTROLS: tuple[TailControl, ...] = (
    TailControl(
        name="soft_knife_any_90",
        description="至少1个接刀子旗标的目标权重乘以0.90，保留大部分弹性。",
        soft_knife_any=0.90,
    ),
    TailControl(
        name="soft_knife2plus_75",
        description="至少2个接刀子旗标的目标权重乘以0.75，压最厚尾部。",
        soft_knife_2plus=0.75,
    ),
    TailControl(
        name="soft_limitdown_50",
        description="上一交易日跌停/一字跌停目标权重乘以0.50，只降最极端流动性冲击。",
        soft_limit_down=0.50,
    ),
    TailControl(
        name="cap_knife2plus_daily_20pct",
        description="每日knife_2plus目标总权重上限20%，超出部分按比例缩放。",
        cap_knife_2plus_daily=0.20,
    ),
    TailControl(
        name="cap_knife2plus_daily_15pct",
        description="每日knife_2plus目标总权重上限15%，更强约束但仍不清零。",
        cap_knife_2plus_daily=0.15,
    ),
    TailControl(
        name="cap_limitdown_daily_5pct",
        description="每日跌停/一字跌停目标总权重上限5%，避免单日极端冲击过度集中。",
        cap_limit_down_daily=0.05,
    ),
    TailControl(
        name="cap_high_volume_daily_8pct",
        description="每日放量下跌目标总权重上限8%，只限制高换手卖压集中日。",
        cap_high_volume_daily=0.08,
    ),
    TailControl(
        name="hybrid_elastic_tail_budget",
        description="组合预算：knife_2plus日上限20%，跌停日上限5%，放量下跌目标乘以0.85。",
        soft_high_volume=0.85,
        cap_knife_2plus_daily=0.20,
        cap_limit_down_daily=0.05,
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        normalized[key] = value.isoformat() if isinstance(value, (date, datetime)) else value
    return normalized


def multiply_if(condition: pl.Expr, multiplier: float) -> pl.Expr:
    return pl.when(condition.fill_null(False)).then(pl.lit(multiplier)).otherwise(pl.lit(1.0))


def add_base_multiplier(frame: pl.DataFrame, control: TailControl) -> pl.DataFrame:
    multiplier = pl.lit(1.0)
    if control.soft_knife_any is not None:
        multiplier = multiplier * multiply_if(pl.col("knife_flag_count") >= 1, control.soft_knife_any)
    if control.soft_knife_2plus is not None:
        multiplier = multiplier * multiply_if(pl.col("knife_flag_count") >= 2, control.soft_knife_2plus)
    if control.soft_limit_down is not None:
        multiplier = multiplier * multiply_if(pl.col("flag_limit_down_signal"), control.soft_limit_down)
    if control.soft_high_volume is not None:
        multiplier = multiplier * multiply_if(pl.col("flag_high_volume_selloff"), control.soft_high_volume)
    return frame.with_columns(multiplier.alias("base_tail_multiplier"))


def apply_daily_cap(
    frame: pl.DataFrame,
    condition_col: str,
    cap_weight: float,
    scale_col: str,
) -> pl.DataFrame:
    daily = (
        frame.with_columns(
            pl.when(pl.col(condition_col).fill_null(False))
            .then(pl.col("target_weight") * pl.col("tail_weight_multiplier"))
            .otherwise(0.0)
            .alias("_cohort_weight")
        )
        .group_by(["scenario", "target_date"])
        .agg(pl.col("_cohort_weight").sum().alias("_cohort_weight_sum"))
        .with_columns(
            pl.when(pl.col("_cohort_weight_sum") > cap_weight)
            .then(cap_weight / pl.col("_cohort_weight_sum"))
            .otherwise(1.0)
            .alias(scale_col)
        )
        .select(["scenario", "target_date", scale_col])
    )
    return (
        frame.join(daily, on=["scenario", "target_date"], how="left")
        .with_columns(
            pl.when(pl.col(condition_col).fill_null(False))
            .then(pl.col("tail_weight_multiplier") * pl.col(scale_col).fill_null(1.0))
            .otherwise(pl.col("tail_weight_multiplier"))
            .alias("tail_weight_multiplier")
        )
        .drop(scale_col)
    )


def apply_tail_control(enriched_targets: pl.DataFrame, control: TailControl) -> tuple[pl.DataFrame, pl.DataFrame]:
    work = add_base_multiplier(enriched_targets, control).with_columns(
        pl.col("base_tail_multiplier").alias("tail_weight_multiplier")
    )
    if control.cap_knife_2plus_daily is not None:
        work = apply_daily_cap(work, "cond_knife_2plus", control.cap_knife_2plus_daily, "_knife2plus_cap_scale")
    if control.cap_limit_down_daily is not None:
        work = apply_daily_cap(work, "flag_limit_down_signal", control.cap_limit_down_daily, "_limitdown_cap_scale")
    if control.cap_high_volume_daily is not None:
        work = apply_daily_cap(work, "flag_high_volume_selloff", control.cap_high_volume_daily, "_high_volume_cap_scale")

    scaled_all = work.with_columns(
        pl.col("target_weight").alias("base_target_weight"),
        (pl.col("target_weight") * pl.col("tail_weight_multiplier")).alias("target_weight"),
        pl.lit(control.name).alias("tail_control_name"),
        pl.lit(control.description).alias("tail_control_description"),
    )
    scale_daily = (
        scaled_all.group_by(["scenario", "target_date"])
        .agg(
            pl.col("base_target_weight").sum().alias("base_target_gross_weight"),
            pl.col("target_weight").sum().alias("controlled_target_gross_weight"),
            (pl.col("tail_weight_multiplier") < 0.999999).sum().alias("controlled_row_count"),
            pl.len().alias("base_row_count"),
            pl.when(pl.col("knife_flag_count") >= 1)
            .then(pl.col("base_target_weight"))
            .otherwise(0.0)
            .sum()
            .alias("base_knife_any_weight"),
            pl.when(pl.col("knife_flag_count") >= 1).then(pl.col("target_weight")).otherwise(0.0).sum().alias(
                "controlled_knife_any_weight"
            ),
            pl.when(pl.col("knife_flag_count") >= 2)
            .then(pl.col("base_target_weight"))
            .otherwise(0.0)
            .sum()
            .alias("base_knife2plus_weight"),
            pl.when(pl.col("knife_flag_count") >= 2).then(pl.col("target_weight")).otherwise(0.0).sum().alias(
                "controlled_knife2plus_weight"
            ),
            pl.when(pl.col("flag_limit_down_signal"))
            .then(pl.col("base_target_weight"))
            .otherwise(0.0)
            .sum()
            .alias("base_limitdown_weight"),
            pl.when(pl.col("flag_limit_down_signal")).then(pl.col("target_weight")).otherwise(0.0).sum().alias(
                "controlled_limitdown_weight"
            ),
        )
        .with_columns(
            pl.lit(control.name).alias("tail_control_name"),
            pl.lit(control.description).alias("tail_control_description"),
            (pl.col("controlled_row_count") / pl.col("base_row_count")).alias("controlled_row_ratio"),
            (pl.col("controlled_target_gross_weight") / pl.col("base_target_gross_weight")).alias(
                "gross_retention_ratio"
            ),
        )
    )
    return scaled_all.filter(pl.col("target_weight") > 0).sort(["target_date", "symbol"]), scale_daily


def build_quality(
    summary: pl.DataFrame,
    year_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
) -> pl.DataFrame:
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

    stress = summary.filter(pl.col("filter_probe_name") != BASE_FILTER_NAME)
    improve_both = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    improve_dd_preserve_half_return = stress.filter(
        (pl.col("delta_max_drawdown_min_fee") > 0)
        & (pl.col("total_return_min_fee") >= pl.col("base_total_return_min_fee_for_quality") * 0.50)
    )
    high_target = stress.filter(
        (pl.col("total_return_min_fee") >= HIGH_RETURN_TARGET) & (pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT)
    )
    primary_rolling = rolling_scorecard.filter(
        (pl.col("base_scenario") == PRIMARY_SCENARIO) & (pl.col("window_days") == 252)
    )
    primary_rolling_good = primary_rolling.filter(pl.col("return_and_drawdown_beat_ratio") >= 0.50)
    year_good = year_scorecard.filter(pl.col("return_and_drawdown_beat_ratio") >= 0.50)
    add(
        "tail_control_count",
        "pass" if stress["filter_probe_name"].n_unique() == len(TAIL_CONTROLS) else "fail",
        stress["filter_probe_name"].n_unique(),
        len(TAIL_CONTROLS),
        "只运行预注册高弹性尾部控制探针。",
    )
    add(
        "any_full_sample_improves_both",
        "pass" if improve_both.height > 0 else "warn",
        f"{improve_both.height}/{stress.height}",
        ">0",
        "收益和回撤同向改善才可能继续策略化。",
    )
    add(
        "drawdown_improve_without_gutting_return",
        "pass" if improve_dd_preserve_half_return.height > 0 else "warn",
        f"{improve_dd_preserve_half_return.height}/{stress.height}",
        ">0",
        "允许收益下降，但不能把高弹性alpha砍到不足基准一半。",
    )
    add(
        "candidate_high_return_and_within_20pct",
        "pass" if high_target.height > 0 else "warn",
        f"{high_target.height}/{stress.height}",
        ">0",
        "30万目标是高收益且回撤20%以内。",
    )
    add(
        "yearly_any_control_majority",
        "pass" if year_good.height > 0 else "warn",
        f"{year_good.height}/{year_scorecard.height}",
        ">0",
        "年度多数同向改善比单一全样本更重要。",
    )
    add(
        "primary_252d_any_control_majority",
        "pass" if primary_rolling_good.height > 0 else "warn",
        f"{primary_rolling_good.height}/{primary_rolling.height}",
        ">0",
        "主场景252日滚动同向改善率需要过半。",
    )
    add(
        "no_reallocation_of_freed_cash",
        "pass",
        "cash freed",
        "cash freed",
        "尾部控制释放现金不重分配，避免把风险控制伪装成加仓。",
    )
    add(
        "prior_day_feature_alignment",
        "pass",
        "prior-day flags",
        "no same-day close at execution open",
        "接刀子旗标使用上一交易日收盘后已知信息。",
    )
    add(
        "exploratory_tail_budget_warning",
        "warn",
        "pre-registered probes",
        "needs OOS before candidate",
        "本阶段是尾部控制探针，不直接升级正式候选。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: pl.DataFrame,
    scale_daily: pl.DataFrame,
    year_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    stress = summary.filter(pl.col("filter_probe_name") != BASE_FILTER_NAME)
    improve_both = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    best_return = stress.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    best_dd = stress.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(0, named=True)
    primary_rolling_252 = rolling_scorecard.filter(
        (pl.col("base_scenario") == PRIMARY_SCENARIO) & (pl.col("window_days") == 252)
    ).sort("return_and_drawdown_beat_ratio", descending=True)
    primary_summary = summary.filter(pl.col("base_scenario") == PRIMARY_SCENARIO).sort(
        ["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]
    )
    scale_summary = (
        scale_daily.group_by(["base_scenario", "tail_control_name"])
        .agg(
            pl.col("base_target_gross_weight").mean().alias("avg_base_target_gross_weight"),
            pl.col("controlled_target_gross_weight").mean().alias("avg_controlled_target_gross_weight"),
            pl.col("controlled_row_ratio").mean().alias("avg_controlled_row_ratio"),
            pl.col("gross_retention_ratio").mean().alias("avg_gross_retention_ratio"),
            pl.col("base_knife_any_weight").mean().alias("avg_base_knife_any_weight"),
            pl.col("controlled_knife_any_weight").mean().alias("avg_controlled_knife_any_weight"),
            pl.col("base_knife2plus_weight").mean().alias("avg_base_knife2plus_weight"),
            pl.col("controlled_knife2plus_weight").mean().alias("avg_controlled_knife2plus_weight"),
            pl.col("base_limitdown_weight").mean().alias("avg_base_limitdown_weight"),
            pl.col("controlled_limitdown_weight").mean().alias("avg_controlled_limitdown_weight"),
        )
        .sort(["base_scenario", "tail_control_name"])
    )
    lines = [
        "# 股票震荡industry_resid_core 30万高弹性尾部控制探针 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡30万industry_resid_core独立研究线，不接入第78。",
        "- 本阶段性质：保留高弹性接刀子样本，测试温和降权/暴露上限是否改善尾部。",
        f"- 账户规模：`{lot.ACCOUNT_SIZE_CNY:,.0f}`元；释放现金不重分配。",
        "- 特征时间对齐：接刀子旗标使用上一交易日收盘后已知信息。",
        "- A/B判断：独立研究线探针，不触发第78 A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 短期反转更像流动性供给补偿，高波动样本不能简单删除。",
        "- 业界风险控制常用暴露上限、波动缩放、尾部预算；这比硬过滤更符合第327阶段发现。",
        "- 本阶段只做少量预注册预算探针，不根据最优结果继续扫阈值。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        f"- 全样本收益和回撤同时改善：`{improve_both.height}/{stress.height}`。",
        f"- 收益最高探针：`{best_return['scenario']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`，Sharpe `{best_return['sharpe_min_fee']:.3f}`。",
        f"- 回撤最浅探针：`{best_dd['scenario']}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，Sharpe `{best_dd['sharpe_min_fee']:.3f}`。",
        "",
        "## 主场景结果",
        "",
        markdown_table(
            primary_summary,
            [
                "base_scenario",
                "filter_probe_name",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "delta_sharpe_min_fee",
                "avg_actual_gross_weight",
                "avg_controlled_target_gross_weight",
                "avg_controlled_row_ratio",
                "avg_gross_retention_ratio",
            ],
            max_rows=80,
        ),
        "",
        "## 全样本汇总",
        "",
        markdown_table(
            summary,
            [
                "base_scenario",
                "filter_probe_name",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "delta_sharpe_min_fee",
                "avg_actual_gross_weight",
                "avg_controlled_target_gross_weight",
                "avg_controlled_row_ratio",
                "avg_gross_retention_ratio",
            ],
            max_rows=180,
        ),
        "",
        "## 控制强度统计",
        "",
        markdown_table(
            scale_summary,
            [
                "base_scenario",
                "tail_control_name",
                "avg_base_target_gross_weight",
                "avg_controlled_target_gross_weight",
                "avg_controlled_row_ratio",
                "avg_gross_retention_ratio",
                "avg_base_knife_any_weight",
                "avg_controlled_knife_any_weight",
                "avg_base_knife2plus_weight",
                "avg_controlled_knife2plus_weight",
                "avg_base_limitdown_weight",
                "avg_controlled_limitdown_weight",
            ],
            max_rows=180,
        ),
        "",
        "## 年度记分",
        "",
        markdown_table(
            year_scorecard,
            [
                "base_scenario",
                "filter_probe_name",
                "sample_count",
                "return_beat_ratio",
                "drawdown_beat_ratio",
                "sharpe_beat_ratio",
                "return_and_drawdown_beat_ratio",
                "avg_period_return_delta",
                "worst_period_return_delta",
                "avg_max_drawdown_improvement",
                "worst_max_drawdown_improvement",
                "avg_sharpe_delta",
            ],
            max_rows=180,
        ),
        "",
        "## 主场景252日滚动记分",
        "",
        markdown_table(
            primary_rolling_252,
            [
                "base_scenario",
                "filter_probe_name",
                "window_days",
                "sample_count",
                "return_beat_ratio",
                "drawdown_beat_ratio",
                "sharpe_beat_ratio",
                "return_and_drawdown_beat_ratio",
                "avg_period_return_delta",
                "median_period_return_delta",
                "worst_period_return_delta",
                "avg_max_drawdown_improvement",
                "median_max_drawdown_improvement",
                "worst_max_drawdown_improvement",
                "avg_sharpe_delta",
            ],
            max_rows=120,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        "- 若温和预算能改善回撤但明显损失收益，说明尾部控制仍在误伤弹性来源。",
        "- 若全样本、年度、滚动均有同向改善，下一阶段再做更严格walk-forward。",
        "- 本阶段不升级正式候选，不修改paper线，不接入第78。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：中等。",
        "- 原因：控制规则来自第327机制发现和外部风险预算思想，且数量少；但仍在同一历史样本上测试。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：根据质量检查，不直接升级候选。",
        "- 原因：任何看起来好的尾部预算都需要后续滚动/OOS，不能按本阶段结果细调阈值。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：第327证明高弹性样本是收益来源，风险控制必须从硬过滤转向预算化。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：若不能同向改善，则转向持有路径归因；若可以同向改善，再做walk-forward。",
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
        "scale_daily": OUTPUT_DIR / f"{PREFIX}_scale_daily.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "year_summary": OUTPUT_DIR / f"{PREFIX}_year_summary.csv",
        "year_delta": OUTPUT_DIR / f"{PREFIX}_year_delta.csv",
        "year_scorecard": OUTPUT_DIR / f"{PREFIX}_year_scorecard.csv",
        "rolling_summary": OUTPUT_DIR / f"{PREFIX}_rolling_summary.csv",
        "rolling_delta": OUTPUT_DIR / f"{PREFIX}_rolling_delta.csv",
        "rolling_scorecard": OUTPUT_DIR / f"{PREFIX}_rolling_scorecard.csv",
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

    enriched_targets = add_knife_flags(target_weights, stock_df)
    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pl.DataFrame] = []
    orders_frames: list[pl.DataFrame] = []
    scale_frames: list[pl.DataFrame] = []

    base_daily_for_segments = base_daily.with_columns(
        pl.col("scenario").alias("base_scenario"),
        pl.lit(BASE_FILTER_NAME).alias("filter_probe_name"),
    )
    daily_frames.append(base_daily_for_segments)
    for row in base_summary.iter_rows(named=True):
        base_scenario = str(row["scenario"])
        base_row = dict(row)
        base_row["base_scenario"] = base_scenario
        base_row["filter_probe_name"] = BASE_FILTER_NAME
        base_row["filter_probe_description"] = "不做高弹性尾部预算控制。"
        base_row["avg_controlled_target_gross_weight"] = base_row.get("shape_basket_gross_weight")
        base_row["avg_controlled_row_ratio"] = 0.0
        base_row["avg_gross_retention_ratio"] = 1.0
        summary_rows.append(normalize_row(base_row))

    for base_scenario in FOCUS_SCENARIOS:
        scenario_targets = enriched_targets.filter(pl.col("scenario") == base_scenario)
        original_dates = lot.build_tracking_dates(scenario_targets.drop("scenario"), benchmark_df)
        for control in TAIL_CONTROLS:
            controlled_targets, scale_daily = apply_tail_control(scenario_targets, control)
            target_maps = lot.build_target_maps(controlled_targets.drop("scenario"))
            orders, daily, _curves = lot.replay_lot_account(target_maps, original_dates, exec_info)
            scenario_name = f"{base_scenario}_{control.name}"
            orders = orders.with_columns(
                pl.lit(scenario_name).alias("scenario"),
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(control.name).alias("filter_probe_name"),
            )
            daily = daily.with_columns(
                pl.lit(scenario_name).alias("scenario"),
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(control.name).alias("filter_probe_name"),
            )
            scale_daily = scale_daily.with_columns(
                pl.lit(base_scenario).alias("base_scenario"),
                pl.lit(control.description).alias("tail_control_description"),
            )
            summary = lot.summarize_orders(orders, daily)
            summary = summarize_daily_extra(summary, daily)
            summary.update(
                {
                    "scenario": scenario_name,
                    "base_scenario": base_scenario,
                    "filter_probe_name": control.name,
                    "filter_probe_description": control.description,
                    "avg_controlled_target_gross_weight": to_float(scale_daily["controlled_target_gross_weight"].mean()),
                    "avg_base_target_gross_weight": to_float(scale_daily["base_target_gross_weight"].mean()),
                    "avg_controlled_row_ratio": to_float(scale_daily["controlled_row_ratio"].mean()),
                    "avg_gross_retention_ratio": to_float(scale_daily["gross_retention_ratio"].mean()),
                    "avg_controlled_knife_any_weight": to_float(scale_daily["controlled_knife_any_weight"].mean()),
                    "avg_controlled_knife2plus_weight": to_float(scale_daily["controlled_knife2plus_weight"].mean()),
                    "avg_controlled_limitdown_weight": to_float(scale_daily["controlled_limitdown_weight"].mean()),
                }
            )
            summary_rows.append(normalize_row(summary))
            daily_frames.append(daily)
            orders_frames.append(orders)
            scale_frames.append(scale_daily)

    summary = add_base_deltas(pl.DataFrame(summary_rows, infer_schema_length=None)).sort(
        ["base_scenario", "filter_probe_name"]
    )
    base_for_quality = (
        summary.filter(pl.col("filter_probe_name") == BASE_FILTER_NAME)
        .select("base_scenario", pl.col("total_return_min_fee").alias("base_total_return_min_fee_for_quality"))
    )
    summary = summary.join(base_for_quality, on="base_scenario", how="left")

    daily_all = pl.concat(daily_frames, how="diagonal_relaxed")
    orders_all = pl.concat(orders_frames, how="diagonal_relaxed") if orders_frames else pl.DataFrame()
    scale_all = pl.concat(scale_frames, how="diagonal_relaxed") if scale_frames else pl.DataFrame()

    year_summary = build_segment_summary(
        daily_all.with_columns(pl.col("date").dt.year().alias("year")),
        ["base_scenario", "filter_probe_name", "year"],
        segment_col="year",
    )
    year_delta = build_delta(year_summary, ["base_scenario", "year"])
    year_scorecard = build_scorecard(year_delta, ["base_scenario", "filter_probe_name"])
    rolling_summary = build_rolling_summary(daily_all)
    rolling_delta = build_delta(rolling_summary, ["base_scenario", "window_days", "window_start", "window_end"])
    rolling_scorecard = build_scorecard(rolling_delta, ["base_scenario", "filter_probe_name", "window_days"])
    quality = build_quality(summary, year_scorecard, rolling_scorecard)

    summary.write_csv(paths["summary"])
    scale_all.write_csv(paths["scale_daily"])
    daily_all.write_csv(paths["daily"])
    orders_all.write_csv(paths["orders"])
    year_summary.write_csv(paths["year_summary"])
    year_delta.write_csv(paths["year_delta"])
    year_scorecard.write_csv(paths["year_scorecard"])
    rolling_summary.write_csv(paths["rolling_summary"])
    rolling_delta.write_csv(paths["rolling_delta"])
    rolling_scorecard.write_csv(paths["rolling_scorecard"])
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
            "tail_controls": [
                {
                    "name": control.name,
                    "description": control.description,
                    "soft_knife_any": control.soft_knife_any,
                    "soft_knife_2plus": control.soft_knife_2plus,
                    "soft_limit_down": control.soft_limit_down,
                    "soft_high_volume": control.soft_high_volume,
                    "cap_knife_2plus_daily": control.cap_knife_2plus_daily,
                    "cap_limit_down_daily": control.cap_limit_down_daily,
                    "cap_high_volume_daily": control.cap_high_volume_daily,
                }
                for control in TAIL_CONTROLS
            ],
            "rolling_windows": ROLLING_WINDOWS,
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    report_path = write_report(summary, scale_all, year_scorecard, rolling_scorecard, quality, paths)
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
                "avg_controlled_row_ratio",
                "avg_gross_retention_ratio",
            ]
        )
    )
    print(year_scorecard)
    print(rolling_scorecard.filter((pl.col("base_scenario") == PRIMARY_SCENARIO) & (pl.col("window_days") == 252)))


if __name__ == "__main__":
    main()

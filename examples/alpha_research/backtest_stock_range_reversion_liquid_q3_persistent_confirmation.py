from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_industry_signal_lifecycle import (
    add_industry_rank_lifecycle,
    build_base_frame,
)
from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    COST_BPS,
    FEATURE,
    HORIZON,
    INITIAL_EQUITY,
    MAX_INDUSTRY_WEIGHT_PER_BASKET,
    MAX_STOCK_WEIGHT_PER_BASKET,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    add_path_columns,
    build_benchmark_daily,
    build_calendar,
    build_concentration,
    build_daily_gross,
    build_equity_curve,
    build_symbol_daily,
    build_turnover,
    build_yearly_summary,
    pct,
    summarize_curve,
)


OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_persistent_confirmation_2018_2026"),
    )
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_persistent_confirmation_v1"

ENTRY_AGE_MIN_SET: tuple[int, ...] = tuple(
    int(item) for item in os.getenv("ENTRY_AGE_MIN_SET", "2,4").split(",") if item
)
CADENCE_STEPS: tuple[int, ...] = tuple(
    int(item) for item in os.getenv("CADENCE_STEPS", "1,5").split(",") if item
)


def scenario_name(entry_age_min: int, cadence_step: int, phase: int) -> str:
    return f"liquid_q3_age{entry_age_min}plus_cadence{cadence_step}d_p{phase}"


def scenario_definitions() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for entry_age_min in ENTRY_AGE_MIN_SET:
        for cadence_step in CADENCE_STEPS:
            for phase in range(cadence_step):
                variants.append(
                    {
                        "scenario": scenario_name(entry_age_min, cadence_step, phase),
                        "description": (
                            f"liquid_q3行业内top20连续停留至少{entry_age_min}天，"
                            f"每{cadence_step}个交易日建一篮子，相位{phase}"
                        ),
                        "bucket": "liquid_q3",
                        "weight_mode": "persistent_confirmation_scaled",
                        "entry_age_min": entry_age_min,
                        "cadence_step": cadence_step,
                        "phase": phase,
                    }
                )
    return variants


def build_confirmed_base(path_df: pl.DataFrame, lifecycle_df: pl.DataFrame) -> pl.DataFrame:
    joined = path_df.join(
        lifecycle_df.select("datetime", "symbol", "top_age", "top_age_bucket", "transition_from"),
        on=["datetime", "symbol"],
        how="inner",
    )
    dates = joined.select("datetime").unique().sort("datetime").with_row_index("signal_index")
    return joined.join(dates, on="datetime", how="left")


def apply_capped_weights(df: pl.DataFrame, entry_age_min: int) -> pl.DataFrame:
    filtered = df.filter(pl.col("top_age") >= entry_age_min)
    if filtered.is_empty():
        return pl.DataFrame()
    return (
        filtered.with_columns(
            pl.len().over("datetime").alias("candidate_count"),
            pl.col("industry").n_unique().over("datetime").alias("selected_industry_count"),
            pl.len().over(["datetime", "industry"]).alias("selected_industry_stock_count"),
        )
        .with_columns(
            pl.min_horizontal(
                1.0 / pl.col("selected_industry_count"),
                pl.lit(MAX_INDUSTRY_WEIGHT_PER_BASKET),
            ).alias("_industry_budget")
        )
        .with_columns(
            pl.min_horizontal(
                pl.col("_industry_budget") / pl.col("selected_industry_stock_count"),
                pl.lit(MAX_STOCK_WEIGHT_PER_BASKET),
            ).alias("basket_weight")
        )
        .with_columns(
            pl.col("basket_weight").sum().over("datetime").alias("basket_gross_weight"),
            pl.lit(entry_age_min).alias("entry_age_min"),
        )
        .drop("_industry_budget")
    )


def build_selected_by_variant(confirmed_base: pl.DataFrame) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    weighted_by_age: dict[int, pl.DataFrame] = {
        entry_age_min: apply_capped_weights(confirmed_base, entry_age_min)
        for entry_age_min in ENTRY_AGE_MIN_SET
    }
    for variant in scenario_definitions():
        base = weighted_by_age[variant["entry_age_min"]]
        if base.is_empty():
            continue
        selected = (
            base.filter((pl.col("signal_index") % variant["cadence_step"]) == variant["phase"])
            .with_columns(
                pl.lit(variant["scenario"]).alias("scenario"),
                pl.lit(variant["description"]).alias("scenario_description"),
                pl.lit(variant["bucket"]).alias("bucket"),
                pl.lit(variant["weight_mode"]).alias("weight_mode"),
                pl.lit(variant["cadence_step"]).alias("cadence_step"),
                pl.lit(variant["phase"]).alias("phase"),
            )
        )
        if not selected.is_empty():
            frames.append(selected)
    if not frames:
        raise RuntimeError("No persistent confirmation candidates.")
    return pl.concat(frames, how="vertical").sort(["scenario", "datetime", "industry", FEATURE])


def build_confirmation_lots(selected: pl.DataFrame) -> pl.DataFrame:
    parts: list[pl.DataFrame] = []
    extra_cols = [
        col
        for col in [
            "scenario_description",
            "bucket",
            "weight_mode",
            "entry_age_min",
            "cadence_step",
            "phase",
            "signal_index",
            "industry",
            "market",
            "adv20_turnover",
            "turnover_rate_f",
            "adv20_turnover_q",
            "turnover_rate_f_q",
            "circ_mv",
            "total_mv",
            "candidate_count",
            "selected_industry_count",
            "selected_industry_stock_count",
            "basket_gross_weight",
            "top_age",
            "top_age_bucket",
            "transition_from",
        ]
        if col in selected.columns
    ]
    for day in range(1, HORIZON + 1):
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
            .with_columns(pl.lit(day).alias("holding_day"))
            .filter(
                pl.col("target_date").is_not_null()
                & pl.col("pnl_date").is_not_null()
                & pl.col("stock_daily_ret").is_not_null()
                & pl.col("stock_daily_ret").is_finite()
            )
        )
    raw_lots = pl.concat(parts, how="vertical")
    active_sleeves = (
        raw_lots.select("scenario", "target_date", "signal_date")
        .unique()
        .group_by(["scenario", "target_date"])
        .agg(pl.len().alias("active_sleeves"))
    )
    return (
        raw_lots.join(active_sleeves, on=["scenario", "target_date"], how="left")
        .with_columns((pl.col("basket_weight") / pl.col("active_sleeves")).alias("lot_weight"))
        .sort(["scenario", "target_date", "signal_date", "symbol"])
    )


def summarize_phases(summary_df: pl.DataFrame) -> pl.DataFrame:
    return (
        summary_df.group_by(["entry_age_min", "cadence_step", "roundtrip_cost_bps"])
        .agg(
            pl.len().alias("phase_count"),
            pl.col("final_equity").mean().alias("mean_final_equity"),
            pl.col("final_equity").min().alias("min_final_equity"),
            pl.col("final_equity").max().alias("max_final_equity"),
            pl.col("total_return").mean().alias("mean_total_return"),
            pl.col("total_return").min().alias("min_total_return"),
            pl.col("total_return").max().alias("max_total_return"),
            pl.col("max_drawdown").mean().alias("mean_max_drawdown"),
            pl.col("max_drawdown").min().alias("worst_max_drawdown"),
            pl.col("max_drawdown").max().alias("best_max_drawdown"),
            pl.col("sharpe").mean().alias("mean_sharpe"),
            pl.col("sharpe").min().alias("min_sharpe"),
            pl.col("avg_return_gross_exposure").mean().alias("mean_gross_exposure"),
            pl.col("annualized_one_way_turnover").mean().alias("mean_annualized_one_way_turnover"),
            pl.col("annualized_one_way_turnover").min().alias("min_annualized_one_way_turnover"),
            pl.col("annualized_one_way_turnover").max().alias("max_annualized_one_way_turnover"),
            pl.col("cost_drag_sum").mean().alias("mean_cost_drag_sum"),
            pl.col("net_active_day_win_rate").mean().alias("mean_net_active_day_win_rate"),
        )
        .sort(["roundtrip_cost_bps", "entry_age_min", "cadence_step"])
    )


def build_selected_daily_summary(selected: pl.DataFrame) -> pl.DataFrame:
    return (
        selected.group_by(["scenario", "datetime"])
        .agg(
            pl.len().alias("candidate_count"),
            pl.col("industry").n_unique().alias("selected_industry_count"),
            pl.col("basket_weight").sum().alias("basket_gross_weight"),
            pl.col("basket_weight").max().alias("max_basket_stock_weight"),
            pl.col("top_age").mean().alias("avg_top_age"),
        )
        .sort(["scenario", "datetime"])
    )


def build_age_bucket_contribution(lots: pl.DataFrame) -> pl.DataFrame:
    return (
        lots.with_columns((pl.col("lot_weight") * pl.col("stock_daily_ret")).alias("weighted_stock_ret"))
        .group_by(["scenario", "top_age_bucket"])
        .agg(
            pl.col("weighted_stock_ret").sum().alias("gross_contribution_sum"),
            pl.col("lot_weight").mean().alias("avg_target_weight"),
            pl.col("lot_weight").max().alias("max_target_weight"),
            pl.len().alias("symbol_day_count"),
            pl.col("symbol").n_unique().alias("symbol_count"),
            pl.col("industry").n_unique().alias("industry_count"),
        )
        .sort(["scenario", "gross_contribution_sum"], descending=[False, True])
    )


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def write_report(
    summary_df: pl.DataFrame,
    phase_summary: pl.DataFrame,
    yearly: pl.DataFrame,
    age_bucket_contribution: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    best_50 = (
        summary_df.filter(pl.col("roundtrip_cost_bps") == 50.0)
        .sort(["final_equity", "max_drawdown"], descending=[True, True])
        .head(1)
        .to_dicts()
    )
    best = best_50[0] if best_50 else None
    lines = [
        "# 股票震荡liquid_q3持续确认低频账本 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：生命周期归因后的固定确认账本，不是正式交易版本。",
        "",
        "## 方法",
        "",
        f"- 固定信号：`{FEATURE}`，行业内top20，流动性桶`liquid_q3`。",
        f"- 入场确认：连续处于行业top20至少`{ENTRY_AGE_MIN_SET}`天；这是粗粒度确认，不直接采用最强的`8-15天`桶。",
        f"- 建篮节奏：`{CADENCE_STEPS}`个交易日；5日节奏保留全部相位，观察相位风险。",
        f"- 持有路径：次日收盘入场，固定持有`{HORIZON}`日，多篮子重叠时按活跃篮子数缩放。",
        f"- 单篮子约束：行业上限`{MAX_INDUSTRY_WEIGHT_PER_BASKET:.0%}`，单票上限`{MAX_STOCK_WEIGHT_PER_BASKET:.0%}`，未用完资金留现金。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，股票数`{meta['symbol_count']}`。",
        "",
        "## 核心观察",
        "",
    ]
    if best:
        lines.append(
            f"- 50bp成本下期末权益最高的是`{best['scenario']}`：期末权益`{best['final_equity']:.4f}`，"
            f"总收益`{pct(best['total_return'])}`，最大回撤`{pct(best['max_drawdown'])}`，"
            f"Sharpe `{best['sharpe']:.2f}`，年化单边换手`{best['annualized_one_way_turnover']:.2f}`倍。"
        )
    lines.extend(
        [
            "- 这一步只验证确认与节奏是否缓解换手，不把最优相位当成策略参数。",
            "- 若5日节奏的相位差异很大，说明策略仍依赖入场时点，不能贸然正式化。",
            "",
            "## 汇总结果",
            "",
            markdown_table(
                summary_df.sort(["roundtrip_cost_bps", "entry_age_min", "cadence_step", "phase"]),
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "entry_age_min",
                    "cadence_step",
                    "phase",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "avg_return_gross_exposure",
                    "annualized_one_way_turnover",
                    "avg_active_symbols_when_active",
                    "avg_active_industries_when_active",
                    "avg_effective_names_when_active",
                    "cost_drag_sum",
                ],
                max_rows=80,
            ),
            "",
            "## 相位聚合",
            "",
            markdown_table(
                phase_summary,
                [
                    "entry_age_min",
                    "cadence_step",
                    "roundtrip_cost_bps",
                    "phase_count",
                    "mean_final_equity",
                    "min_final_equity",
                    "max_final_equity",
                    "mean_max_drawdown",
                    "worst_max_drawdown",
                    "mean_sharpe",
                    "min_sharpe",
                    "mean_gross_exposure",
                    "mean_annualized_one_way_turnover",
                    "mean_cost_drag_sum",
                ],
            ),
            "",
            "## 年度结果",
            "",
            markdown_table(
                yearly.sort(["roundtrip_cost_bps", "scenario", "year"]),
                [
                    "scenario",
                    "roundtrip_cost_bps",
                    "year",
                    "year_return",
                    "year_gross_return",
                    "year_benchmark_return",
                    "year_cost_drag",
                    "avg_gross_exposure",
                ],
                max_rows=120,
            ),
            "",
            "## 生命周期贡献",
            "",
            markdown_table(
                age_bucket_contribution,
                [
                    "scenario",
                    "top_age_bucket",
                    "gross_contribution_sum",
                    "avg_target_weight",
                    "max_target_weight",
                    "symbol_day_count",
                    "symbol_count",
                    "industry_count",
                ],
                max_rows=80,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：确认门槛只测试`2天以上`和`4天以上`两个粗粒度解释型条件，不直接锁定上一阶段收益最强的生命周期桶；5日节奏保留全部相位，不挑单一最优相位。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否，但不能引用最优相位作为策略结论。",
            "- 原因：`4天确认+每日建篮`在50bp下期末权益约2.13、最大回撤约-27.48%、年化单边换手约11.28倍，方向来自确认机制而不是挑相位；5日节奏虽然有最优相位更高，但相位间分布很宽，不能把`p1`当作可交易参数。",
            "- 风险：确认条件降低了暴露和换手，也牺牲了部分收益；这说明它是交易化缓解，不是新的alpha突破。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第239阶段显示持续top信号没有快速衰减，本阶段检验它能否转化为更低换手账本。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是，但方向要收窄。",
            "- 原因：`4天确认`把换手从第230阶段`liquid_q3_capped`约15.6倍降到约11.3倍，同时回撤有所收窄，证明生命周期确认有交易化价值；但收益没有超过原始`liquid_q3_capped`，所以不应继续调确认天数或相位。",
            "- 下一步：以`4天确认+每日建篮`为底稿做市场状态过滤/年份回撤归因，重点判断2018、2022、2025这些低效阶段是否能被外生状态识别。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不基于本阶段选择正式参数。",
            "- 下一步不继续扫描确认天数/相位，转向`4天确认+每日建篮`的市场状态过滤和失效年份归因。",
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
    base = build_base_frame()
    _, benchmark_df = load_panels()
    path_df = add_path_columns(base)
    lifecycle_df = add_industry_rank_lifecycle(base, "liquid_q3")
    confirmed_base = build_confirmed_base(path_df, lifecycle_df)
    selected_all = build_selected_by_variant(confirmed_base)
    lots_all = build_confirmation_lots(selected_all)
    symbol_daily_all = build_symbol_daily(lots_all)
    benchmark_daily = build_benchmark_daily(benchmark_df)

    all_curves: list[pl.DataFrame] = []
    all_summary: list[dict[str, Any]] = []
    all_turnover: list[pl.DataFrame] = []
    all_targets: list[pl.DataFrame] = []
    all_concentration: list[pl.DataFrame] = []

    variant_lookup = {item["scenario"]: item for item in scenario_definitions()}
    for scenario in scenario_definitions():
        scenario_name_value = scenario["scenario"]
        scenario_symbol_daily = symbol_daily_all.filter(pl.col("scenario") == scenario_name_value)
        scenario_selected = selected_all.filter(pl.col("scenario") == scenario_name_value)
        if scenario_symbol_daily.is_empty():
            continue
        min_date = min(scenario_symbol_daily["target_date"].min(), scenario_symbol_daily["pnl_date"].min())
        max_date = max(scenario_symbol_daily["target_date"].max(), scenario_symbol_daily["pnl_date"].max())
        calendar = build_calendar(benchmark_df, min_date, max_date)
        turnover, targets = build_turnover(scenario_symbol_daily, calendar, scenario_name_value)
        concentration, _industry_daily = build_concentration(scenario_symbol_daily, calendar, scenario_name_value)
        daily_gross = build_daily_gross(scenario_symbol_daily)
        all_turnover.append(turnover)
        all_targets.append(targets)
        all_concentration.append(concentration)
        for cost_bps in COST_BPS:
            curve = build_equity_curve(
                scenario_name_value, daily_gross, turnover, benchmark_daily, calendar, cost_bps
            )
            all_curves.append(curve)
            row = summarize_curve(curve, turnover, concentration, scenario_selected, scenario, cost_bps)
            row["entry_age_min"] = scenario["entry_age_min"]
            row["cadence_step"] = scenario["cadence_step"]
            row["phase"] = scenario["phase"]
            all_summary.append(row)

    summary_df = pl.DataFrame(all_summary).sort(["roundtrip_cost_bps", "entry_age_min", "cadence_step", "phase"])
    equity_df = pl.concat(all_curves, how="vertical").sort(["roundtrip_cost_bps", "scenario", "date"])
    turnover_df = pl.concat(all_turnover, how="vertical").sort(["scenario", "target_date"])
    target_weights_df = pl.concat(all_targets, how="vertical").sort(["scenario", "target_date", "symbol"])
    concentration_df = pl.concat(all_concentration, how="vertical").sort(["scenario", "target_date"])
    yearly_df = (
        build_yearly_summary(equity_df)
        .join(summary_df.select("scenario", "entry_age_min", "cadence_step", "phase").unique(), on="scenario", how="left")
        .sort(["roundtrip_cost_bps", "entry_age_min", "cadence_step", "phase", "year"])
    )
    selected_daily_df = build_selected_daily_summary(selected_all)
    phase_summary_df = summarize_phases(summary_df)
    age_bucket_contribution_df = build_age_bucket_contribution(lots_all)

    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "date_min": str(selected_all["datetime"].min()),
        "date_max": str(selected_all["datetime"].max()),
        "symbol_count": selected_all["symbol"].n_unique(),
        "feature": FEATURE,
        "horizon": HORIZON,
        "cost_bps": COST_BPS,
        "entry_age_min_set": ENTRY_AGE_MIN_SET,
        "cadence_steps": CADENCE_STEPS,
        "initial_equity": INITIAL_EQUITY,
        "trading_days": TRADING_DAYS,
        "max_industry_weight_per_basket": MAX_INDUSTRY_WEIGHT_PER_BASKET,
        "max_stock_weight_per_basket": MAX_STOCK_WEIGHT_PER_BASKET,
        "scenarios": list(variant_lookup.values()),
    }

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    phase_summary_path = OUTPUT_DIR / f"{PREFIX}_phase_summary.csv"
    equity_path = OUTPUT_DIR / f"{PREFIX}_equity_curve.csv"
    yearly_path = OUTPUT_DIR / f"{PREFIX}_yearly.csv"
    concentration_path = OUTPUT_DIR / f"{PREFIX}_daily_concentration.csv"
    turnover_path = OUTPUT_DIR / f"{PREFIX}_turnover.csv"
    target_weights_path = OUTPUT_DIR / f"{PREFIX}_target_weights.csv"
    selected_daily_path = OUTPUT_DIR / f"{PREFIX}_selected_daily.csv"
    age_bucket_contribution_path = OUTPUT_DIR / f"{PREFIX}_age_bucket_contribution.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    phase_summary_df.write_csv(phase_summary_path)
    equity_df.write_csv(equity_path)
    yearly_df.write_csv(yearly_path)
    concentration_df.write_csv(concentration_path)
    turnover_df.write_csv(turnover_path)
    target_weights_df.write_csv(target_weights_path)
    selected_daily_df.write_csv(selected_daily_path)
    age_bucket_contribution_df.write_csv(age_bucket_contribution_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        phase_summary_df,
        yearly_df,
        age_bucket_contribution_df,
        meta,
        {
            "summary": summary_path,
            "phase_summary": phase_summary_path,
            "equity_curve": equity_path,
            "yearly": yearly_path,
            "daily_concentration": concentration_path,
            "turnover": turnover_path,
            "target_weights": target_weights_path,
            "selected_daily": selected_daily_path,
            "age_bucket_contribution": age_bucket_contribution_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()

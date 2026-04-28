from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_active_bucket_stability import (
    active_bucket_definitions,
    add_groups,
    finite_signal_filter,
)
from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = Path(
    os.getenv(
        "OUTPUT_DIR",
        str(NATIVE_RESULTS_DIR / "stock_range_reversion_cost_capacity_2018_2026"),
    )
).expanduser().resolve()

PREFIX: str = "stock_range_reversion_cost_capacity_v1"
FEATURES: tuple[str, ...] = tuple(
    item.strip()
    for item in os.getenv(
        "FEATURES",
        "score_oversold_ret_5,score_oversold_ret_10,score_oversold_ret_20",
    ).split(",")
    if item.strip()
)
HORIZONS: tuple[int, ...] = tuple(int(item) for item in os.getenv("HORIZONS", "5,10").split(",") if item.strip())
COST_BPS: tuple[float, ...] = tuple(float(item) for item in os.getenv("COST_BPS", "10,20,50,100,150").split(",") if item.strip())
PARTICIPATION_RATES: tuple[float, ...] = tuple(
    float(item) for item in os.getenv("PARTICIPATION_RATES", "0.01,0.02,0.05,0.10").split(",") if item.strip()
)


def t_stat(mean: float, std: float | None, n: int) -> float:
    """Return simple t-stat for daily mean series."""
    if not std or std <= 0 or n <= 1:
        return 0.0
    return mean / (std / (n**0.5))


def summarize_daily(
    bucket: str,
    description: str,
    feature: str,
    horizon: int,
    daily: pl.DataFrame,
) -> dict[str, Any]:
    """Summarize daily top-group return and liquidity profile."""
    gross_mean = float(daily["gross_top_excess_mean"].mean()) if daily.height else 0.0
    gross_std = float(daily["gross_top_excess_mean"].std()) if daily.height else 0.0
    return {
        "bucket": bucket,
        "bucket_description": description,
        "feature": feature,
        "horizon": horizon,
        "days": daily.height,
        "avg_candidate_count": float(daily["candidate_count"].mean()) if daily.height else 0.0,
        "median_candidate_count": float(daily["candidate_count"].median()) if daily.height else 0.0,
        "gross_top_excess_mean": gross_mean,
        "gross_top_excess_t": t_stat(gross_mean, gross_std, daily.height),
        "gross_top_excess_positive_ratio": float((daily["gross_top_excess_mean"] > 0).mean()) if daily.height else 0.0,
        "gross_top_abs_ret_mean": float(daily["gross_top_abs_ret_mean"].mean()) if daily.height else 0.0,
        "median_sum_adv20_turnover_yuan": float(daily["sum_adv20_turnover"].median()) if daily.height else 0.0,
        "median_p10_adv20_turnover_yuan": float(daily["p10_adv20_turnover"].median()) if daily.height else 0.0,
        "median_p20_adv20_turnover_yuan": float(daily["p20_adv20_turnover"].median()) if daily.height else 0.0,
        "median_median_adv20_turnover_yuan": float(daily["median_adv20_turnover"].median()) if daily.height else 0.0,
    }


def evaluate_one_bucket(df: pl.DataFrame, bucket: str, description: str, expr: pl.Expr) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[pl.DataFrame]]:
    """Evaluate all features/horizons for one active bucket."""
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    capacity_rows: list[dict[str, Any]] = []
    industry_frames: list[pl.DataFrame] = []

    for feature in FEATURES:
        for horizon in HORIZONS:
            label_col = f"fwd_excess_ret_{horizon}"
            abs_col = f"fwd_ret_{horizon}"
            work = df.filter(
                expr
                & finite_signal_filter(feature, horizon)
                & pl.col("adv20_turnover").is_not_null()
                & (pl.col("adv20_turnover") > 0)
            )
            if work.is_empty():
                continue

            grouped = add_groups(work, feature, [])
            top = grouped.filter(pl.col("feature_group") == 5)
            if top.is_empty():
                continue

            daily = (
                top.group_by("datetime")
                .agg(
                    pl.len().alias("candidate_count"),
                    pl.col(label_col).mean().alias("gross_top_excess_mean"),
                    pl.col(abs_col).mean().alias("gross_top_abs_ret_mean"),
                    pl.col("adv20_turnover").sum().alias("sum_adv20_turnover"),
                    pl.col("adv20_turnover").quantile(0.1).alias("p10_adv20_turnover"),
                    pl.col("adv20_turnover").quantile(0.2).alias("p20_adv20_turnover"),
                    pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
                )
                .sort("datetime")
            )

            summary_rows.append(summarize_daily(bucket, description, feature, horizon, daily))

            for cost_bps in COST_BPS:
                cost_return = cost_bps / 10000.0
                net = daily.with_columns((pl.col("gross_top_excess_mean") - cost_return).alias("net_top_excess_mean"))
                net_mean = float(net["net_top_excess_mean"].mean())
                net_std = float(net["net_top_excess_mean"].std())
                cost_rows.append(
                    {
                        "bucket": bucket,
                        "bucket_description": description,
                        "feature": feature,
                        "horizon": horizon,
                        "roundtrip_cost_bps": cost_bps,
                        "days": net.height,
                        "net_top_excess_mean": net_mean,
                        "net_top_excess_t": t_stat(net_mean, net_std, net.height),
                        "net_top_excess_positive_ratio": float((net["net_top_excess_mean"] > 0).mean()),
                    }
                )

            for participation in PARTICIPATION_RATES:
                capacity = daily.with_columns(
                    (pl.col("sum_adv20_turnover") * participation).alias("sum_capacity_yuan"),
                    (pl.col("candidate_count") * pl.col("p10_adv20_turnover") * participation).alias("equal_weight_capacity_p10_yuan"),
                    (pl.col("candidate_count") * pl.col("p20_adv20_turnover") * participation).alias("equal_weight_capacity_p20_yuan"),
                    (pl.col("p10_adv20_turnover") * participation).alias("position_cap_p10_yuan"),
                    (pl.col("p20_adv20_turnover") * participation).alias("position_cap_p20_yuan"),
                )
                capacity_rows.append(
                    {
                        "bucket": bucket,
                        "bucket_description": description,
                        "feature": feature,
                        "horizon": horizon,
                        "participation_rate": participation,
                        "days": capacity.height,
                        "median_sum_capacity_yuan": float(capacity["sum_capacity_yuan"].median()),
                        "p25_sum_capacity_yuan": float(capacity["sum_capacity_yuan"].quantile(0.25)),
                        "median_equal_weight_capacity_p10_yuan": float(capacity["equal_weight_capacity_p10_yuan"].median()),
                        "median_equal_weight_capacity_p20_yuan": float(capacity["equal_weight_capacity_p20_yuan"].median()),
                        "median_position_cap_p10_yuan": float(capacity["position_cap_p10_yuan"].median()),
                        "median_position_cap_p20_yuan": float(capacity["position_cap_p20_yuan"].median()),
                    }
                )

            if "industry" in top.columns:
                industry = (
                    top.filter(pl.col("industry").is_not_null())
                    .group_by("industry")
                    .agg(
                        pl.len().alias("rows"),
                        pl.col("datetime").n_unique().alias("days"),
                        pl.col(label_col).mean().alias("gross_top_excess_mean"),
                        pl.col("adv20_turnover").median().alias("median_adv20_turnover_yuan"),
                    )
                    .with_columns(
                        (pl.col("rows") / pl.lit(top.height)).alias("row_share"),
                        pl.lit(bucket).alias("bucket"),
                        pl.lit(description).alias("bucket_description"),
                        pl.lit(feature).alias("feature"),
                        pl.lit(horizon).alias("horizon"),
                    )
                    .sort("row_share", descending=True)
                )
                industry_frames.append(industry)

    return summary_rows, cost_rows, capacity_rows, industry_frames


def build_year_cost_grid(df: pl.DataFrame) -> pl.DataFrame:
    """Evaluate net top-group excess by year under cost scenarios."""
    frames: list[pl.DataFrame] = []
    for bucket, description, expr in active_bucket_definitions():
        for feature in FEATURES:
            for horizon in HORIZONS:
                label_col = f"fwd_excess_ret_{horizon}"
                work = df.filter(expr & finite_signal_filter(feature, horizon))
                if work.is_empty():
                    continue
                top = add_groups(work, feature, []).filter(pl.col("feature_group") == 5)
                daily = (
                    top.group_by("datetime")
                    .agg(pl.col(label_col).mean().alias("gross_top_excess_mean"))
                    .with_columns(pl.col("datetime").dt.year().alias("year"))
                )
                for cost_bps in COST_BPS:
                    cost_return = cost_bps / 10000.0
                    year = (
                        daily.with_columns((pl.col("gross_top_excess_mean") - cost_return).alias("net_top_excess_mean"))
                        .group_by("year")
                        .agg(
                            pl.len().alias("days"),
                            pl.col("net_top_excess_mean").mean().alias("net_top_excess_mean"),
                            pl.col("net_top_excess_mean").std().alias("net_top_excess_std"),
                            (pl.col("net_top_excess_mean") > 0).mean().alias("net_top_excess_positive_ratio"),
                        )
                        .with_columns(
                            pl.when((pl.col("net_top_excess_std").is_not_null()) & (pl.col("net_top_excess_std") > 0))
                            .then(pl.col("net_top_excess_mean") / (pl.col("net_top_excess_std") / pl.col("days").sqrt()))
                            .otherwise(0.0)
                            .alias("net_top_excess_t"),
                            pl.lit(cost_bps).alias("roundtrip_cost_bps"),
                            pl.lit(bucket).alias("bucket"),
                            pl.lit(description).alias("bucket_description"),
                            pl.lit(feature).alias("feature"),
                            pl.lit(horizon).alias("horizon"),
                        )
                        .drop("net_top_excess_std")
                    )
                    frames.append(year)
    return pl.concat(frames, how="vertical") if frames else pl.DataFrame()


def write_report(
    summary_df: pl.DataFrame,
    cost_df: pl.DataFrame,
    capacity_df: pl.DataFrame,
    year_cost_df: pl.DataFrame,
    industry_df: pl.DataFrame,
    meta: dict[str, Any],
    paths: dict[str, Path],
) -> Path:
    """Write Chinese report for cost and capacity pressure."""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    lines = [
        "# 股票震荡成本容量压力估算 v1",
        "",
        "## 核心结论",
        "",
        "- 本阶段不是回测，也不新增交易规则；只用固定高活跃桶候选信号，估算毛超额在交易成本情境下是否还有边际，以及候选池容量大概在哪里。",
        f"- 样本：`{meta['date_min']}`到`{meta['date_max']}`，`{meta['symbol_count']}`只股票，`{meta['row_count']:,}`行。",
        "- 成本以单笔完整买卖的 roundtrip bps 情境扣减；容量以候选股20日平均成交额的参与率估算。",
        "",
        "## 10日核心信号成本压力",
        "",
    ]

    focus_cost = cost_df.filter(
        (pl.col("horizon") == 10)
        & pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
        & pl.col("roundtrip_cost_bps").is_in([20.0, 50.0, 100.0])
    ).sort(["feature", "bucket", "roundtrip_cost_bps"])
    for row in focus_cost.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['bucket']}` 成本`{row['roundtrip_cost_bps']:.0f}bp`："
            f"净超额`{row['net_top_excess_mean']:.4%}`，t `{row['net_top_excess_t']:.2f}`，"
            f"正向日`{row['net_top_excess_positive_ratio']:.2%}`。"
        )

    lines.extend(["", "## 5% ADV容量估算", ""])
    focus_capacity = capacity_df.filter(
        (pl.col("horizon") == 10)
        & pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
        & (pl.col("participation_rate") == 0.05)
    ).sort(["feature", "bucket"])
    for row in focus_capacity.iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['bucket']}`：候选池合计容量中位约`{row['median_sum_capacity_yuan'] / 1e8:.2f}`亿元，"
            f"等权p20容量中位约`{row['median_equal_weight_capacity_p20_yuan'] / 1e8:.2f}`亿元，"
            f"单票p20仓位上限中位约`{row['median_position_cap_p20_yuan'] / 1e4:.1f}`万元。"
        )

    lines.extend(["", "## 100bp成本后的年度观察", ""])
    focus_year = year_cost_df.filter(
        (pl.col("horizon") == 10)
        & pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
        & (pl.col("roundtrip_cost_bps") == 100.0)
        & (pl.col("year") >= 2024)
    ).sort(["feature", "bucket", "year"])
    for row in focus_year.iter_rows(named=True):
        lines.append(
            f"- `{row['year']}` `{row['feature']}` `{row['bucket']}`：100bp后净超额`{row['net_top_excess_mean']:.4%}`，"
            f"t `{row['net_top_excess_t']:.2f}`。"
        )

    lines.extend(["", "## 候选池行业集中", ""])
    focus_industry = industry_df.filter(
        (pl.col("horizon") == 10)
        & pl.col("feature").is_in(["score_oversold_ret_10", "score_oversold_ret_20"])
        & pl.col("bucket").is_in(["turnover_f_q5", "dual_turnover_q5"])
    ).sort(["feature", "bucket", "row_share"], descending=[False, False, True])
    for row in focus_industry.head(24).iter_rows(named=True):
        lines.append(
            f"- `{row['feature']}` `{row['bucket']}` `{row['industry']}`：候选占比`{row['row_share']:.2%}`，"
            f"毛超额`{row['gross_top_excess_mean']:.4%}`。"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 如果100bp成本后仍为正，只能说明信号有成本缓冲；还不能说明真实可交易，因为这里没有处理T+1、调仓冲突、涨跌停排队和实际下单冲击。",
            "- 如果容量估算主要来自高活跃桶，后续组合化应优先控制单票成交额占比，而不是追求更集中信号。",
            "- 这一步仍不触发第78 A/B，也不进入正式股票组合回测。",
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
    """Run stock range-reversion cost/capacity pressure estimates."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()
    df = add_forward_returns(add_price_features(stock_df), benchmark_df).join(
        layer_tags, on=["datetime", "symbol"], how="left"
    )
    meta: dict[str, Any] = {
        "row_count": df.height,
        "symbol_count": df["symbol"].n_unique(),
        "date_min": str(df["datetime"].min()),
        "date_max": str(df["datetime"].max()),
        "features": FEATURES,
        "horizons": HORIZONS,
        "cost_bps": COST_BPS,
        "participation_rates": PARTICIPATION_RATES,
    }

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    capacity_rows: list[dict[str, Any]] = []
    industry_frames: list[pl.DataFrame] = []
    for bucket, description, expr in active_bucket_definitions():
        summary, costs, capacities, industries = evaluate_one_bucket(df, bucket, description, expr)
        summary_rows.extend(summary)
        cost_rows.extend(costs)
        capacity_rows.extend(capacities)
        industry_frames.extend(industries)

    summary_df = pl.DataFrame(summary_rows)
    cost_df = pl.DataFrame(cost_rows)
    capacity_df = pl.DataFrame(capacity_rows)
    industry_df = pl.concat(industry_frames, how="vertical") if industry_frames else pl.DataFrame()
    year_cost_df = build_year_cost_grid(df)

    summary_path = OUTPUT_DIR / f"{PREFIX}_summary.csv"
    cost_path = OUTPUT_DIR / f"{PREFIX}_cost_grid.csv"
    capacity_path = OUTPUT_DIR / f"{PREFIX}_capacity_grid.csv"
    year_cost_path = OUTPUT_DIR / f"{PREFIX}_year_cost_grid.csv"
    industry_path = OUTPUT_DIR / f"{PREFIX}_industry_concentration.csv"
    meta_path = OUTPUT_DIR / f"{PREFIX}_meta.json"

    summary_df.write_csv(summary_path)
    cost_df.write_csv(cost_path)
    capacity_df.write_csv(capacity_path)
    year_cost_df.write_csv(year_cost_path)
    industry_df.write_csv(industry_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    report_path = write_report(
        summary_df,
        cost_df,
        capacity_df,
        year_cost_df,
        industry_df,
        meta,
        {
            "summary": summary_path,
            "cost_grid": cost_path,
            "capacity_grid": capacity_path,
            "year_cost_grid": year_cost_path,
            "industry_concentration": industry_path,
            "meta": meta_path,
        },
    )
    print(summary_df)
    print(f"report={report_path}")


if __name__ == "__main__":
    main()

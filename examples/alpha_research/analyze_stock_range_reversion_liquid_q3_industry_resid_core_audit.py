from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_liquid_q3_alt_strong_pullback_definitions import t_stat, write_json
from analyze_stock_range_reversion_signal_attribution import to_float
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_technical_pullback_composite_factor_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_technical_pullback_composite_factor_v1"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_audit_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_audit_v1"

TARGET_MODEL: str = "industry_resid_core"
CORE_INDUSTRY_COUNT: int = 5
MIN_SIGNAL_DAYS: int = 120

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Alphalens factor analysis toolkit",
        "https://github.com/quantopian/alphalens",
    ),
    (
        "Alphalens group neutral/by group analysis docs",
        "https://quantopian.github.io/alphalens/alphalens.html",
    ),
    (
        "Factor investing concentration versus diversification",
        "https://link.springer.com/article/10.1057/s41260-021-00226-0",
    ),
    (
        "Factor Replication with Industry Stratification",
        "https://www.tandfonline.com/doi/full/10.1080/0015198X.2023.2215252",
    ),
)


def read_source_selected() -> pl.DataFrame:
    path = SOURCE_DIR / f"{SOURCE_PREFIX}_selected.csv"
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8}).filter(
        pl.col("model") == TARGET_MODEL
    )


def summarize_daily_curve(selected: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, Any]]:
    daily = (
        selected.group_by("datetime")
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("industry").n_unique().alias("industries"),
            pl.col("fwd_excess_ret_10").mean().alias("daily_fwd_excess_ret_10"),
            pl.col("fwd_ret_10").mean().alias("daily_fwd_ret_10"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_ratio"),
        )
        .sort("datetime")
        .with_columns(pl.col("daily_fwd_excess_ret_10").cum_sum().alias("cum_daily_excess_sum"))
    )
    returns = [float(value) for value in daily["daily_fwd_excess_ret_10"].to_list()]
    mean_ret = sum(returns) / len(returns) if returns else 0.0
    std_ret = (sum((item - mean_ret) ** 2 for item in returns) / (len(returns) - 1)) ** 0.5 if len(returns) > 1 else 0.0
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    summary = {
        "signal_days": daily.height,
        "selected_rows": selected.height,
        "symbols": selected["symbol"].n_unique(),
        "industries": selected["industry"].n_unique(),
        "start_date": str(daily["datetime"].min()) if daily.height else "",
        "end_date": str(daily["datetime"].max()) if daily.height else "",
        "daily_avg_fwd_excess_ret_10": to_float(daily["daily_fwd_excess_ret_10"].mean()) if daily.height else 0.0,
        "daily_t_stat_excess_10": t_stat(
            to_float(daily["daily_fwd_excess_ret_10"].mean()) if daily.height else 0.0,
            to_float(daily["daily_fwd_excess_ret_10"].std()) if daily.height else 0.0,
            daily.height,
        ),
        "compounded_daily_excess": equity - 1.0,
        "max_drawdown_on_daily_excess": max_dd,
        "daily_excess_sharpe": mean_ret / std_ret * sqrt(TRADING_DAYS) if std_ret > 0 else 0.0,
    }
    return daily, summary


def build_yearly(selected: pl.DataFrame) -> pl.DataFrame:
    daily = (
        selected.with_columns(pl.col("datetime").dt.year().alias("year"))
        .group_by(["year", "datetime"])
        .agg(pl.col("fwd_excess_ret_10").mean().alias("daily_fwd_excess_ret_10"))
    )
    return (
        selected.with_columns(pl.col("datetime").dt.year().alias("year"))
        .group_by("year")
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("industry").n_unique().alias("industries"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
            pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
            pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
        )
        .join(
            daily.group_by("year").agg(
                pl.col("daily_fwd_excess_ret_10").mean().alias("daily_avg_fwd_excess_ret_10"),
                pl.col("daily_fwd_excess_ret_10").std().alias("daily_std_fwd_excess_ret_10"),
                pl.len().alias("_daily_n"),
            ),
            on="year",
            how="left",
        )
        .with_columns(
            pl.struct(["daily_avg_fwd_excess_ret_10", "daily_std_fwd_excess_ret_10", "_daily_n"])
            .map_elements(
                lambda row: t_stat(
                    float(row["daily_avg_fwd_excess_ret_10"] or 0.0),
                    float(row["daily_std_fwd_excess_ret_10"] or 0.0),
                    int(row["_daily_n"] or 0),
                ),
                return_dtype=pl.Float64,
            )
            .alias("daily_t_stat_excess_10")
        )
        .drop("_daily_n")
        .sort("year")
    )


def build_industry_contribution(selected: pl.DataFrame) -> pl.DataFrame:
    total_abs = to_float(selected["fwd_excess_ret_10"].abs().sum())
    positive_total = to_float(selected.filter(pl.col("fwd_excess_ret_10") > 0)["fwd_excess_ret_10"].sum())
    return (
        selected.group_by("industry")
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            pl.col("fwd_excess_ret_10").sum().alias("excess_sum"),
            pl.when(pl.col("fwd_excess_ret_10") > 0).then(pl.col("fwd_excess_ret_10")).otherwise(0.0).sum().alias(
                "positive_excess_sum"
            ),
            pl.col("fwd_excess_ret_10").abs().sum().alias("abs_excess_sum"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
            pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
            pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
        )
        .with_columns(
            (pl.col("selected_rows") / selected.height).alias("row_share"),
            (pl.col("positive_excess_sum") / positive_total).alias("positive_excess_share") if positive_total > 0 else pl.lit(0.0),
            (pl.col("abs_excess_sum") / total_abs).alias("abs_excess_share") if total_abs > 0 else pl.lit(0.0),
        )
        .sort("positive_excess_sum", descending=True)
    )


def build_symbol_contribution(selected: pl.DataFrame) -> pl.DataFrame:
    total_abs = to_float(selected["fwd_excess_ret_10"].abs().sum())
    return (
        selected.group_by(["symbol", "code_name", "industry"])
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            pl.col("fwd_excess_ret_10").sum().alias("excess_sum"),
            pl.col("fwd_excess_ret_10").abs().sum().alias("abs_excess_sum"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
            pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
            pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
        )
        .with_columns((pl.col("abs_excess_sum") / total_abs).alias("abs_excess_share") if total_abs > 0 else pl.lit(0.0))
        .sort("abs_excess_sum", descending=True)
    )


def build_daily_industry_concentration(selected: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    industry_daily = (
        selected.group_by(["datetime", "industry"])
        .agg(
            pl.len().alias("industry_rows"),
            pl.col("symbol").n_unique().alias("industry_symbols"),
            pl.col("fwd_excess_ret_10").mean().alias("industry_avg_fwd_excess_ret_10"),
        )
        .with_columns(
            pl.col("industry_rows").sum().over("datetime").alias("daily_rows"),
        )
        .with_columns((pl.col("industry_rows") / pl.col("daily_rows")).alias("industry_row_share"))
        .sort(["datetime", "industry_row_share"], descending=[False, True])
    )
    daily = (
        industry_daily.group_by("datetime")
        .agg(
            pl.col("industry").n_unique().alias("active_industries"),
            pl.col("industry_row_share").max().alias("max_industry_row_share"),
            pl.col("industry_row_share").sort(descending=True).head(CORE_INDUSTRY_COUNT).sum().alias("top5_industry_row_share"),
            (1.0 / (pl.col("industry_row_share").pow(2).sum())).alias("effective_industries"),
        )
        .sort("datetime")
    )
    return daily, industry_daily


def build_year_industry_cross(selected: pl.DataFrame) -> pl.DataFrame:
    return (
        selected.with_columns(pl.col("datetime").dt.year().alias("year"))
        .group_by(["year", "industry"])
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            pl.col("fwd_excess_ret_10").sum().alias("excess_sum"),
            pl.col("fwd_excess_ret_10").abs().sum().alias("abs_excess_sum"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
        )
        .sort(["year", "excess_sum"], descending=[False, True])
    )


def summarize_subset(selected: pl.DataFrame, label: str) -> dict[str, Any]:
    daily, summary = summarize_daily_curve(selected)
    return {
        "case": label,
        "selected_rows": selected.height,
        "signal_days": daily.height,
        "symbols": selected["symbol"].n_unique() if not selected.is_empty() else 0,
        "industries": selected["industry"].n_unique() if not selected.is_empty() else 0,
        **summary,
    }


def build_industry_leave_one_out(selected: pl.DataFrame, industry_contribution: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    full = summarize_subset(selected, "__none__")
    rows.append({"removed_industry": "__none__", "removed_count": 0, **full})
    full_daily = to_float(full["daily_avg_fwd_excess_ret_10"])
    full_sharpe = to_float(full["daily_excess_sharpe"])
    core_industries = industry_contribution.head(CORE_INDUSTRY_COUNT)["industry"].to_list()
    for industry in core_industries:
        subset = selected.filter(pl.col("industry") != industry)
        summary = summarize_subset(subset, industry)
        rows.append(
            {
                "removed_industry": industry,
                "removed_count": 1,
                **summary,
                "delta_daily_avg_excess_vs_full": to_float(summary["daily_avg_fwd_excess_ret_10"]) - full_daily,
                "delta_sharpe_vs_full": to_float(summary["daily_excess_sharpe"]) - full_sharpe,
                "sharpe_drop_ratio_vs_full": (full_sharpe - to_float(summary["daily_excess_sharpe"])) / full_sharpe
                if full_sharpe > 0
                else 0.0,
            }
        )
    subset = selected.filter(~pl.col("industry").is_in(core_industries))
    summary = summarize_subset(subset, "__top5_core_combined__")
    rows.append(
        {
            "removed_industry": "__top5_core_combined__",
            "removed_count": len(core_industries),
            **summary,
            "delta_daily_avg_excess_vs_full": to_float(summary["daily_avg_fwd_excess_ret_10"]) - full_daily,
            "delta_sharpe_vs_full": to_float(summary["daily_excess_sharpe"]) - full_sharpe,
            "sharpe_drop_ratio_vs_full": (full_sharpe - to_float(summary["daily_excess_sharpe"])) / full_sharpe
            if full_sharpe > 0
            else 0.0,
        }
    )
    return pl.DataFrame(rows).sort(["removed_count", "removed_industry"])


def build_concentration_summary(daily_concentration: pl.DataFrame) -> pl.DataFrame:
    return daily_concentration.select(
        pl.len().alias("signal_days"),
        pl.col("active_industries").mean().alias("avg_active_industries"),
        pl.col("active_industries").quantile(0.05).alias("p05_active_industries"),
        pl.col("max_industry_row_share").mean().alias("avg_max_industry_row_share"),
        pl.col("max_industry_row_share").max().alias("max_industry_row_share"),
        pl.col("top5_industry_row_share").mean().alias("avg_top5_industry_row_share"),
        pl.col("top5_industry_row_share").max().alias("max_top5_industry_row_share"),
        pl.col("effective_industries").mean().alias("avg_effective_industries"),
        pl.col("effective_industries").quantile(0.05).alias("p05_effective_industries"),
    )


def top_symbol_abs_share(symbol_contribution: pl.DataFrame, top_n: int) -> float:
    total = to_float(symbol_contribution["abs_excess_sum"].sum())
    if total <= 0:
        return 0.0
    return to_float(symbol_contribution.head(top_n)["abs_excess_sum"].sum()) / total


def build_quality(
    overview: dict[str, Any],
    yearly: pl.DataFrame,
    industry_contribution: pl.DataFrame,
    symbol_contribution: pl.DataFrame,
    concentration_summary: pl.DataFrame,
    leave_one_out: pl.DataFrame,
) -> pl.DataFrame:
    rows: list[dict[str, str]] = []

    def add(checkpoint: str, status: str, value: Any, expected: str, note: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": str(value),
                "expected": expected,
                "note": note,
            }
        )

    signal_days = int(overview.get("signal_days") or 0)
    add("coverage_signal_days", "pass" if signal_days >= MIN_SIGNAL_DAYS else "fail", signal_days, f">={MIN_SIGNAL_DAYS}", "信号日太少容易偶然。")

    positive_years = int((yearly["daily_avg_fwd_excess_ret_10"] > 0).sum()) if not yearly.is_empty() else 0
    year_count = yearly.height
    positive_year_ratio = positive_years / year_count if year_count else 0.0
    add(
        "positive_year_ratio",
        "pass" if positive_year_ratio >= 0.70 else "warn" if positive_year_ratio >= 0.55 else "fail",
        f"{positive_years}/{year_count}={positive_year_ratio:.2%}",
        ">=70% preferred",
        "年度稳定性不足时不应直接进入交易化。",
    )

    top5_positive_share = to_float(industry_contribution.head(CORE_INDUSTRY_COUNT)["positive_excess_share"].sum())
    top5_abs_share = to_float(industry_contribution.sort("abs_excess_sum", descending=True).head(CORE_INDUSTRY_COUNT)["abs_excess_share"].sum())
    add(
        "top5_positive_industry_share",
        "fail" if top5_positive_share >= 0.90 else "warn" if top5_positive_share >= 0.75 else "pass",
        f"{top5_positive_share:.2%}",
        "<75% preferred, <90% hard",
        "正贡献若过度集中在少数行业，信号可能只是历史赛道行情。",
    )
    add(
        "top5_abs_industry_share",
        "fail" if top5_abs_share >= 0.90 else "warn" if top5_abs_share >= 0.75 else "pass",
        f"{top5_abs_share:.2%}",
        "<75% preferred, <90% hard",
        "绝对贡献过度集中说明路径来自行业簇，而不是分散截面边际。",
    )

    top10_symbol_share = top_symbol_abs_share(symbol_contribution, 10)
    top20_symbol_share = top_symbol_abs_share(symbol_contribution, 20)
    add("top10_symbol_abs_share", "fail" if top10_symbol_share > 0.30 else "pass", f"{top10_symbol_share:.2%}", "<=30%", "少数股票贡献过高时视为样本伪象。")
    add("top20_symbol_abs_share", "fail" if top20_symbol_share > 0.45 else "pass", f"{top20_symbol_share:.2%}", "<=45%", "top20单票贡献过高时应降级。")

    avg_industries = to_float(concentration_summary["avg_active_industries"][0]) if not concentration_summary.is_empty() else 0.0
    p05_industries = to_float(concentration_summary["p05_active_industries"][0]) if not concentration_summary.is_empty() else 0.0
    add("avg_active_industries", "pass" if avg_industries >= 4 else "fail", f"{avg_industries:.2f}", ">=4", "平均活跃行业过少会削弱穿越周期能力。")
    add("p05_active_industries", "pass" if p05_industries > 2 else "fail", f"{p05_industries:.2f}", ">2", "低分位行业数过低，说明日常候选太窄。")

    single_loo = leave_one_out.filter(pl.col("removed_count") == 1)
    worst_drop = to_float(single_loo["sharpe_drop_ratio_vs_full"].max()) if not single_loo.is_empty() else 0.0
    add(
        "single_core_industry_sharpe_drop",
        "fail" if worst_drop > 0.30 else "pass",
        f"{worst_drop:.2%}",
        "<=30%",
        "去掉任一核心行业后Sharpe大幅下降，说明行业依赖过强。",
    )
    top5_removed = leave_one_out.filter(pl.col("removed_industry") == "__top5_core_combined__")
    top5_removed_daily = to_float(top5_removed["daily_avg_fwd_excess_ret_10"][0]) if not top5_removed.is_empty() else 0.0
    add(
        "top5_removed_still_positive",
        "fail" if top5_removed_daily <= 0 else "pass",
        pct(top5_removed_daily),
        ">0",
        "去掉核心行业簇后若不再为正，应降级为行业簇现象。",
    )
    return pl.DataFrame(rows)


def write_report(
    overview: dict[str, Any],
    yearly: pl.DataFrame,
    industry_contribution: pl.DataFrame,
    symbol_contribution: pl.DataFrame,
    daily_concentration_summary: pl.DataFrame,
    leave_one_out: pl.DataFrame,
    year_industry_cross: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    top5_positive_share = to_float(industry_contribution.head(CORE_INDUSTRY_COUNT)["positive_excess_share"].sum())
    top5_abs_share = to_float(industry_contribution.sort("abs_excess_sum", descending=True).head(CORE_INDUSTRY_COUNT)["abs_excess_share"].sum())
    top10_symbol_share = top_symbol_abs_share(symbol_contribution, 10)
    positive_years = int((yearly["daily_avg_fwd_excess_ret_10"] > 0).sum()) if not yearly.is_empty() else 0
    lines = [
        "# 股票震荡liquid_q3 industry_resid_core反证审计 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：对第306阶段最优技术面子因子做行业集中、年度稳定、行业留一和单票贡献审计；不做30万整手复放。",
        "- A/B判断：纯反证归因，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- Alphalens类因子研究强调分位、行业/组别、换手和稳定性检查。",
        "- 因子组合存在集中度陷阱，强因子暴露并不等于更稳；行业分层和行业留一是必要反证。",
        "- GitHub工具可借鉴tear sheet思路，但A股必须单独处理复权、涨跌停、ST、流动性和小账户整手约束。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            f"- 样本区间：`{overview['start_date']}` 到 `{overview['end_date']}`，信号日 `{overview['signal_days']}`，样本行 `{overview['selected_rows']}`，股票 `{overview['symbols']}`，行业 `{overview['industries']}`。",
            f"- 日均10日超额：`{pct(overview['daily_avg_fwd_excess_ret_10'])}`，t值 `{overview['daily_t_stat_excess_10']:.3f}`，日度超额Sharpe近似 `{overview['daily_excess_sharpe']:.3f}`。",
            f"- 年度正向：`{positive_years}/{yearly.height}`。",
            f"- top5行业正贡献占比：`{top5_positive_share:.2%}`；top5行业绝对贡献占比：`{top5_abs_share:.2%}`；top10股票绝对贡献占比：`{top10_symbol_share:.2%}`。",
            f"- 质量检查fail `{failed.height}`项，warn `{warned.height}`项。",
        ]
    )
    if failed.height:
        lines.append("- 初步判断：存在红灯，暂不进入30万整手复放。")
    elif warned.height:
        lines.append("- 初步判断：无红灯但有黄灯，下一步可以做小范围30万复放，同时保留行业集中警戒。")
    else:
        lines.append("- 初步判断：反证审计通过，可以进入30万整手复放。")
    lines.extend(
        [
            "",
            "## 年度稳定",
            "",
            markdown_table(yearly, yearly.columns, max_rows=80),
            "",
            "## 行业贡献Top30",
            "",
            markdown_table(industry_contribution, industry_contribution.columns, max_rows=30),
            "",
            "## 行业留一",
            "",
            markdown_table(leave_one_out, leave_one_out.columns, max_rows=20),
            "",
            "## 每日行业集中摘要",
            "",
            markdown_table(daily_concentration_summary, daily_concentration_summary.columns, max_rows=10),
            "",
            "## 单票贡献Top30",
            "",
            markdown_table(symbol_contribution, symbol_contribution.columns, max_rows=30),
            "",
            "## 年份×行业Top80",
            "",
            markdown_table(year_industry_cross, year_industry_cross.columns, max_rows=80),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, quality.columns, max_rows=80),
            "",
            "## 运行后结论",
            "",
            "- 本阶段只判断第306阶段最优子因子是否可能是行业/年份/个股伪象。",
            "- 若无fail但存在行业集中warn，后续30万复放必须加入行业上限和年度拆分；若出现fail，则不应继续交易化。",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "industry": OUTPUT_DIR / f"{PREFIX}_industry_contribution.csv",
        "symbol": OUTPUT_DIR / f"{PREFIX}_symbol_contribution.csv",
        "daily_concentration": OUTPUT_DIR / f"{PREFIX}_daily_industry_concentration.csv",
        "industry_daily": OUTPUT_DIR / f"{PREFIX}_industry_daily.csv",
        "concentration_summary": OUTPUT_DIR / f"{PREFIX}_concentration_summary.csv",
        "leave_one_out": OUTPUT_DIR / f"{PREFIX}_industry_leave_one_out.csv",
        "year_industry": OUTPUT_DIR / f"{PREFIX}_year_industry_cross.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
    }
    selected = read_source_selected()
    daily, overview = summarize_daily_curve(selected)
    yearly = build_yearly(selected)
    industry_contribution = build_industry_contribution(selected)
    symbol_contribution = build_symbol_contribution(selected)
    daily_concentration, industry_daily = build_daily_industry_concentration(selected)
    concentration_summary = build_concentration_summary(daily_concentration)
    leave_one_out = build_industry_leave_one_out(selected, industry_contribution)
    year_industry = build_year_industry_cross(selected)
    quality = build_quality(
        overview,
        yearly,
        industry_contribution,
        symbol_contribution,
        concentration_summary,
        leave_one_out,
    )
    daily.write_csv(paths["daily"])
    yearly.write_csv(paths["yearly"])
    industry_contribution.write_csv(paths["industry"])
    symbol_contribution.write_csv(paths["symbol"])
    daily_concentration.write_csv(paths["daily_concentration"])
    industry_daily.write_csv(paths["industry_daily"])
    concentration_summary.write_csv(paths["concentration_summary"])
    leave_one_out.write_csv(paths["leave_one_out"])
    year_industry.write_csv(paths["year_industry"])
    quality.write_csv(paths["quality"])
    report_path = write_report(
        overview,
        yearly,
        industry_contribution,
        symbol_contribution,
        concentration_summary,
        leave_one_out,
        year_industry,
        quality,
        paths,
    )
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "target_model": TARGET_MODEL,
            "overview": overview,
            "outputs": {key: str(path) for key, path in paths.items()},
            "report": str(report_path),
        },
    )
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()

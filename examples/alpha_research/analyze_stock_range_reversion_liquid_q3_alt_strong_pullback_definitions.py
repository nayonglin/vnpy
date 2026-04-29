from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels
from analyze_stock_range_reversion_signal_attribution import add_forward_returns, add_price_features, to_float
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import (
    FEATURE,
    HORIZON,
    MIN_INDUSTRY_DAILY_WIDTH,
    NATIVE_RESULTS_DIR,
    TRADING_DAYS,
    bucket_expr,
    pct,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_alt_strong_pullback_definitions_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_alt_strong_pullback_definitions_v1"

TOP_K: int = 10
MIN_SIGNAL_DAYS: int = 120

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term reversals and longer-term momentum",
        "https://academic.oup.com/rfs/article/38/12/3673/8240327",
    ),
    (
        "Short-term momentum and reversals, turnover, and 52-week-high ratio",
        "https://www.sciencedirect.com/science/article/pii/S0927539824000902",
    ),
    (
        "Alpha Architect: short-term momentum definitions",
        "https://alphaarchitect.com/2022/06/short-term-momentum/",
    ),
    (
        "Advisor Perspectives: industry momentum and skip-month logic",
        "https://www.advisorperspectives.com/articles/2024/04/29/industry-momentum-harry-mamaysky",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def t_stat(mean_value: float, std_value: float, n: int) -> float:
    if n <= 1 or std_value <= 0:
        return 0.0
    return mean_value / (std_value / (n**0.5))


def add_skip_momentum(work: pl.DataFrame) -> pl.DataFrame:
    out = work.sort(["symbol", "datetime"])
    for lookback in (60, 120, 252):
        skip = 10 if lookback == 60 else 20
        out = out.with_columns(
            pl.col("close").shift(skip).over("symbol").alias(f"_close_skip_{skip}_{lookback}"),
            pl.col("close").shift(skip + lookback).over("symbol").alias(f"_close_skip_lb_{skip}_{lookback}"),
        ).with_columns(
            (pl.col(f"_close_skip_{skip}_{lookback}") / pl.col(f"_close_skip_lb_{skip}_{lookback}") - 1).alias(
                f"mom{lookback}_skip{skip}"
            )
        )
    return out.drop([col for col in out.columns if col.startswith("_close_skip")])


def add_extra_shape_features(work: pl.DataFrame) -> pl.DataFrame:
    out = work.sort(["symbol", "datetime"])
    out = out.with_columns(
        pl.col("close").rolling_mean(60).over("symbol").alias("close_ma60"),
        pl.col("close").rolling_mean(120).over("symbol").alias("close_ma120"),
        pl.col("close").rolling_max(120).over("symbol").alias("high_close_120"),
        pl.col("close").rolling_max(252).over("symbol").alias("high_close_252"),
    ).with_columns(
        (pl.col("close") / pl.col("high_close_120")).alias("close_to_high_120"),
        (pl.col("close") / pl.col("high_close_252")).alias("close_to_high_252"),
        (
            pl.when(pl.col("high") > pl.col("low"))
            .then((pl.col("close") - pl.col("low")) / (pl.col("high") - pl.col("low")))
            .otherwise(None)
        ).alias("ibs"),
        (pl.col("close") / pl.col("close_ma60") - 1).alias("dist_ma60"),
        (pl.col("close") / pl.col("close_ma120") - 1).alias("dist_ma120"),
    )
    for day in range(1, HORIZON + 1):
        out = out.with_columns(
            (pl.col("close").shift(-(day + 1)).over("symbol") / pl.col("entry_close") - 1).alias(
                f"path_close_ret_{day}"
            )
        )
    return out.with_columns(
        pl.max_horizontal([pl.col(f"path_close_ret_{day}") for day in range(1, HORIZON + 1)]).alias("mfe_close_10"),
        pl.min_horizontal([pl.col(f"path_close_ret_{day}") for day in range(1, HORIZON + 1)]).alias("mae_close_10"),
    )


def add_industry_relative_features(work: pl.DataFrame) -> pl.DataFrame:
    out = work
    for col in ["mom60_skip10", "mom120_skip20", "mom252_skip20", "ret_5", "ret_10", "ret_20"]:
        out = out.with_columns(
            pl.col(col).mean().over(["datetime", "industry"]).alias(f"industry_mean_{col}"),
            pl.len().over(["datetime", "industry"]).alias(f"industry_width_{col}"),
        ).with_columns((pl.col(col) - pl.col(f"industry_mean_{col}")).alias(f"resid_{col}"))

    industry_frames: list[pl.DataFrame] = []
    for col in ["mom60_skip10", "mom120_skip20", "mom252_skip20"]:
        industry_frames.append(
            out.filter(pl.col("industry").is_not_null() & pl.col(col).is_not_null() & pl.col(col).is_finite())
            .group_by(["datetime", "industry"])
            .agg(pl.col(col).mean().alias(f"industry_{col}"), pl.len().alias("_industry_symbols"))
            .filter(pl.col("_industry_symbols") >= MIN_INDUSTRY_DAILY_WIDTH)
            .with_columns(
                pl.col(f"industry_{col}").rank("ordinal").over("datetime").alias("_rank"),
                pl.len().over("datetime").alias("_n"),
            )
            .with_columns(((((pl.col("_rank") - 1) * 5) / pl.col("_n")).floor().cast(pl.Int64) + 1).clip(1, 5).alias(f"industry_{col}_q"))
            .select(["datetime", "industry", f"industry_{col}", f"industry_{col}_q"])
        )
    for frame in industry_frames:
        out = out.join(frame, on=["datetime", "industry"], how="left")
    return out


def add_market_quintiles(work: pl.DataFrame) -> pl.DataFrame:
    out = work
    base_filter = bucket_expr("liquid_q3") & pl.col("industry").is_not_null()
    for col in ["mom60_skip10", "mom120_skip20", "mom252_skip20", "ret_5", "ret_10", "resid_ret_5", "resid_ret_10"]:
        ranks = (
            out.filter(base_filter & pl.col(col).is_not_null() & pl.col(col).is_finite())
            .with_columns(
                pl.col(col).rank("ordinal").over("datetime").alias("_rank"),
                pl.len().over("datetime").alias("_n"),
            )
            .filter(pl.col("_n") >= 50)
            .with_columns(((((pl.col("_rank") - 1) * 5) / pl.col("_n")).floor().cast(pl.Int64) + 1).clip(1, 5).alias(f"{col}_q"))
            .select(["datetime", "symbol", f"{col}_q"])
        )
        out = out.join(ranks, on=["datetime", "symbol"], how="left")
    return out


def prepare_panel() -> pl.DataFrame:
    stock_df, benchmark_df = load_panels()
    tags = load_layer_tags()
    work = (
        stock_df.join(tags, on=["datetime", "symbol"], how="left")
        .pipe(add_price_features)
        .pipe(add_forward_returns, benchmark_df)
        .pipe(add_skip_momentum)
        .pipe(add_extra_shape_features)
        .pipe(add_industry_relative_features)
        .pipe(add_market_quintiles)
    )
    return work


def definition_specs() -> list[dict[str, Any]]:
    return [
        {
            "definition": "old_market60_ret20_proxy",
            "description": "旧定义近似：60日跳10日市场相对强q4-q5 + 20日超跌。",
            "filter": (pl.col("mom60_skip10_q") >= 4) & (pl.col("ret_20") < 0),
            "score": -pl.col("ret_20"),
        },
        {
            "definition": "mom120_skip20_ret5_pullback",
            "description": "中期120日跳20日动量q4-q5 + 5日回调。",
            "filter": (pl.col("mom120_skip20_q") >= 4) & (pl.col("ret_5") < 0),
            "score": -pl.col("ret_5"),
        },
        {
            "definition": "mom252_skip20_ret10_pullback",
            "description": "长期252日跳20日动量q4-q5 + 10日回调。",
            "filter": (pl.col("mom252_skip20_q") >= 4) & (pl.col("ret_10") < 0),
            "score": -pl.col("ret_10"),
        },
        {
            "definition": "industry120_resid5_pullback",
            "description": "强行业120日动量q4-q5 + 个股5日行业残差回调。",
            "filter": (pl.col("industry_mom120_skip20_q") >= 4) & (pl.col("resid_ret_5") < 0),
            "score": -pl.col("resid_ret_5"),
        },
        {
            "definition": "industry252_resid10_pullback",
            "description": "强行业252日动量q4-q5 + 个股10日行业残差回调。",
            "filter": (pl.col("industry_mom252_skip20_q") >= 4) & (pl.col("resid_ret_10") < 0),
            "score": -pl.col("resid_ret_10"),
        },
        {
            "definition": "near_252_high_low_ibs",
            "description": "接近252日高点且短期回撤，收盘位于日内低位。",
            "filter": (pl.col("close_to_high_252") >= 0.85) & (pl.col("ret_5") < 0) & (pl.col("ibs") <= 0.30),
            "score": (-pl.col("ret_5")) + (0.30 - pl.col("ibs")).clip(0, 0.30),
        },
        {
            "definition": "trend_ma_lowvol_ret5_pullback",
            "description": "均线趋势完整 + 5日回调 + 缩量回踩。",
            "filter": (
                (pl.col("close") > pl.col("close_ma120"))
                & (pl.col("close_ma20") > pl.col("close_ma60"))
                & (pl.col("close_ma60") > pl.col("close_ma120"))
                & (pl.col("ret_5") < 0)
                & (pl.col("volume_ratio_20") <= 0.90)
            ),
            "score": -pl.col("ret_5"),
        },
        {
            "definition": "mom120_lowvol_ret10_pullback",
            "description": "120日中期动量q4-q5 + 10日回调 + 缩量。",
            "filter": (pl.col("mom120_skip20_q") >= 4) & (pl.col("ret_10") < 0) & (pl.col("volume_ratio_20") <= 0.80),
            "score": -pl.col("ret_10"),
        },
        {
            "definition": "strong_industry_near_high_resid5",
            "description": "强行业 + 个股仍接近252日高点 + 个股5日相对行业回调。",
            "filter": (pl.col("industry_mom120_skip20_q") >= 4) & (pl.col("close_to_high_252") >= 0.85) & (pl.col("resid_ret_5") < 0),
            "score": -pl.col("resid_ret_5"),
        },
    ]


def build_selected(work: pl.DataFrame) -> pl.DataFrame:
    base_filter = (
        bucket_expr("liquid_q3")
        & pl.col(f"final_keep_{HORIZON}").fill_null(False)
        & pl.col("final_keep_5").fill_null(False)
        & pl.col(FEATURE).is_not_null()
        & pl.col(FEATURE).is_finite()
        & pl.col("industry").is_not_null()
    )
    frames: list[pl.DataFrame] = []
    keep_cols = [
        "datetime",
        "symbol",
        "code_name",
        "industry",
        "market",
        "adv20_turnover",
        "turnover_rate_f",
        "circ_mv",
        "total_mv",
        FEATURE,
        "ret_5",
        "ret_10",
        "ret_20",
        "resid_ret_5",
        "resid_ret_10",
        "volume_ratio_20",
        "ibs",
        "close_to_high_252",
        "mom60_skip10",
        "mom120_skip20",
        "mom252_skip20",
        "industry_mom120_skip20",
        "industry_mom252_skip20",
        "mfe_close_10",
        "mae_close_10",
        "fwd_ret_5",
        "fwd_excess_ret_5",
        "fwd_ret_10",
        "fwd_excess_ret_10",
    ]
    for spec in definition_specs():
        scoped = (
            work.filter(base_filter & spec["filter"])
            .with_columns(
                spec["score"].alias("pullback_score"),
                pl.lit(spec["definition"]).alias("definition"),
                pl.lit(spec["description"]).alias("definition_description"),
            )
            .with_columns(
                pl.col("pullback_score").rank("ordinal", descending=True).over("datetime").alias("daily_rank"),
                pl.len().over("datetime").alias("daily_candidates"),
            )
            .filter(pl.col("daily_rank") <= TOP_K)
            .select([col for col in [*keep_cols, "definition", "definition_description", "pullback_score", "daily_rank", "daily_candidates"] if col in work.columns or col in {"definition", "definition_description", "pullback_score", "daily_rank", "daily_candidates"}])
        )
        if not scoped.is_empty():
            frames.append(scoped)
    return pl.concat(frames, how="vertical").sort(["definition", "datetime", "daily_rank"]) if frames else pl.DataFrame()


def summarize_selected(selected: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for definition, frame in selected.partition_by("definition", as_dict=True).items():
        if isinstance(definition, tuple):
            definition = definition[0]
        daily = (
            frame.group_by("datetime")
            .agg(
                pl.len().alias("daily_selected"),
                pl.col("fwd_ret_5").mean().alias("daily_fwd_ret_5"),
                pl.col("fwd_excess_ret_5").mean().alias("daily_fwd_excess_ret_5"),
                pl.col("fwd_ret_10").mean().alias("daily_fwd_ret_10"),
                pl.col("fwd_excess_ret_10").mean().alias("daily_fwd_excess_ret_10"),
            )
            .sort("datetime")
        )
        desc = frame["definition_description"][0]
        daily_excess10 = daily["daily_fwd_excess_ret_10"].to_list()
        rows.append(
            {
                "definition": definition,
                "definition_description": desc,
                "selected_rows": frame.height,
                "signal_days": daily.height,
                "symbols": frame["symbol"].n_unique(),
                "avg_daily_selected": to_float(daily["daily_selected"].mean()),
                "avg_daily_candidates_before_topk": to_float(frame["daily_candidates"].mean()),
                "avg_ret_5": to_float(frame["ret_5"].mean()),
                "avg_ret_10": to_float(frame["ret_10"].mean()),
                "avg_ret_20": to_float(frame["ret_20"].mean()),
                "avg_resid_ret_5": to_float(frame["resid_ret_5"].mean()),
                "avg_volume_ratio_20": to_float(frame["volume_ratio_20"].mean()),
                "avg_ibs": to_float(frame["ibs"].mean()),
                "avg_close_to_high_252": to_float(frame["close_to_high_252"].mean()),
                "avg_mom120_skip20": to_float(frame["mom120_skip20"].mean()),
                "avg_industry_mom120_skip20": to_float(frame["industry_mom120_skip20"].mean()),
                "avg_fwd_ret_5": to_float(frame["fwd_ret_5"].mean()),
                "avg_fwd_excess_ret_5": to_float(frame["fwd_excess_ret_5"].mean()),
                "positive_excess_5_ratio": to_float((frame["fwd_excess_ret_5"] > 0).mean()),
                "avg_fwd_ret_10": to_float(frame["fwd_ret_10"].mean()),
                "avg_fwd_excess_ret_10": to_float(frame["fwd_excess_ret_10"].mean()),
                "median_fwd_excess_ret_10": to_float(frame["fwd_excess_ret_10"].median()),
                "positive_excess_10_ratio": to_float((frame["fwd_excess_ret_10"] > 0).mean()),
                "daily_avg_fwd_excess_ret_10": to_float(daily["daily_fwd_excess_ret_10"].mean()),
                "daily_t_stat_excess_10": t_stat(
                    to_float(daily["daily_fwd_excess_ret_10"].mean()),
                    to_float(daily["daily_fwd_excess_ret_10"].std()),
                    daily.height,
                ),
                "avg_mfe_close_10": to_float(frame["mfe_close_10"].mean()),
                "avg_mae_close_10": to_float(frame["mae_close_10"].mean()),
                "definition_coverage_ok": daily.height >= MIN_SIGNAL_DAYS,
            }
        )
    return pl.DataFrame(rows).sort(["daily_avg_fwd_excess_ret_10", "avg_fwd_excess_ret_10"], descending=[True, True])


def summarize_yearly(selected: pl.DataFrame) -> pl.DataFrame:
    return (
        selected.with_columns(pl.col("datetime").dt.year().alias("year"))
        .group_by(["definition", "year"])
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("datetime").n_unique().alias("signal_days"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
            pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
            pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
        )
        .sort(["definition", "year"])
    )


def build_quality(summary: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, str]] = []
    for row in summary.iter_rows(named=True):
        excess = to_float(row.get("daily_avg_fwd_excess_ret_10"))
        t_value = to_float(row.get("daily_t_stat_excess_10"))
        days = int(row.get("signal_days") or 0)
        mae = to_float(row.get("avg_mae_close_10"))
        definition = row["definition"]
        rows.extend(
            [
                {
                    "definition": definition,
                    "checkpoint": "coverage",
                    "status": "pass" if days >= MIN_SIGNAL_DAYS else "warn",
                    "value": str(days),
                    "expected": f">={MIN_SIGNAL_DAYS}",
                    "note": "信号日太少容易样本内偶然。",
                },
                {
                    "definition": definition,
                    "checkpoint": "daily_excess_positive",
                    "status": "pass" if excess > 0 else "fail",
                    "value": pct(excess),
                    "expected": ">0",
                    "note": "日均10日前向超额需要为正。",
                },
                {
                    "definition": definition,
                    "checkpoint": "t_stat",
                    "status": "pass" if t_value >= 1.0 else "warn" if t_value > 0 else "fail",
                    "value": f"{t_value:.3f}",
                    "expected": ">=1 preferred",
                    "note": "归因阶段只看方向，不把t值当上线标准。",
                },
                {
                    "definition": definition,
                    "checkpoint": "tail_risk_mae",
                    "status": "warn" if mae < -0.08 else "pass",
                    "value": pct(mae),
                    "expected": ">-8%",
                    "note": "平均10日MAE过深，后续30万复放容易被尾部击穿。",
                },
            ]
        )
    return pl.DataFrame(rows).sort(["definition", "checkpoint"])


def write_report(summary: pl.DataFrame, yearly: pl.DataFrame, quality: pl.DataFrame, paths: dict[str, Path]) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    best = summary.row(0, named=True) if not summary.is_empty() else None
    pass_defs = quality.group_by("definition").agg((pl.col("status") == "fail").sum().alias("fails")).filter(pl.col("fails") == 0)
    lines = [
        "# 股票震荡liquid_q3 强势回调定义归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：只比较强势股短期回调的不同定义，不做30万整手复放，不修改paper入口。",
        f"- 每个定义每日最多取top `{TOP_K}` 个回调最强样本。",
        "- A/B判断：纯信号归因，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 短期反转和中长期动量应分开定义，强势最好跳过最近一个月或数周。",
        "- 52周高点、换手/成交量、行业动量都会改变短期反转是否成立。",
        "- 因此本阶段测试中期动量、强行业残差、接近高点、均线结构、缩量回踩等定义，而不是继续沿用单一60日强度。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(["", "## 核心摘要", ""])
    if best:
        lines.append(
            f"- 日均10日超额最高定义：`{best['definition']}`，日均10日超额`{pct(best['daily_avg_fwd_excess_ret_10'])}`，样本10日超额`{pct(best['avg_fwd_excess_ret_10'])}`，正超额比例`{pct(best['positive_excess_10_ratio'])}`，t值`{best['daily_t_stat_excess_10']:.3f}`。"
        )
    lines.append(f"- 无fail定义数量：`{pass_defs.height}`。质量检查fail `{failed.height}`项，warn `{warned.height}`项。")
    lines.append("- 判断：信号层若没有稳定正超额，不进入30万整手复放；若有候选，下一步才做执行可行性。")
    display_cols = [
        "definition",
        "signal_days",
        "selected_rows",
        "avg_daily_candidates_before_topk",
        "avg_ret_5",
        "avg_ret_10",
        "avg_volume_ratio_20",
        "avg_ibs",
        "avg_close_to_high_252",
        "avg_mom120_skip20",
        "avg_industry_mom120_skip20",
        "avg_fwd_excess_ret_5",
        "avg_fwd_excess_ret_10",
        "daily_avg_fwd_excess_ret_10",
        "daily_t_stat_excess_10",
        "positive_excess_10_ratio",
        "avg_mfe_close_10",
        "avg_mae_close_10",
    ]
    lines.extend(
        [
            "",
            "## 定义汇总",
            "",
            markdown_table(summary, [col for col in display_cols if col in summary.columns], max_rows=80),
            "",
            "## 定义说明",
            "",
            markdown_table(summary.select(["definition", "definition_description"]), ["definition", "definition_description"], max_rows=80),
            "",
            "## 年度拆分",
            "",
            markdown_table(yearly, yearly.columns, max_rows=160),
            "",
            "## 质量检查",
            "",
            markdown_table(quality, quality.columns, max_rows=160),
            "",
            "## 运行后结论",
            "",
            "- 本阶段只用于决定哪些定义值得进入30万整手复放。",
            "- 如果候选收益来自样本太少、t值很弱或MAE过深，应视为黄灯，不应直接交易化。",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "selected": OUTPUT_DIR / f"{PREFIX}_selected.csv",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
    }
    work = prepare_panel()
    selected = build_selected(work)
    summary = summarize_selected(selected)
    yearly = summarize_yearly(selected)
    quality = build_quality(summary)
    selected.write_csv(paths["selected"])
    summary.write_csv(paths["summary"])
    yearly.write_csv(paths["yearly"])
    quality.write_csv(paths["quality"])
    report_path = write_report(summary, yearly, quality, paths)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "top_k": TOP_K,
            "min_signal_days": MIN_SIGNAL_DAYS,
            "definitions": [
                {"definition": item["definition"], "description": item["description"]} for item in definition_specs()
            ],
            "outputs": {key: str(path) for key, path in paths.items()},
            "report": str(report_path),
        },
    )
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()

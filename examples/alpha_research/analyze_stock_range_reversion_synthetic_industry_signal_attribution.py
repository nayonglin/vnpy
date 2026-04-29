from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from analyze_stock_range_reversion_etf_industry_rotation_readiness import pct, safe_float
from analyze_stock_range_reversion_layer_attribution import load_layer_tags, load_panels


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_synthetic_industry_signal_attribution_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_synthetic_industry_signal_attribution_v1"

HORIZONS: tuple[int, ...] = (5, 10, 20)
MIN_INDUSTRY_STOCKS: int = 5
MIN_DAILY_INDUSTRIES: int = 20
TOP_N: int = 5


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def to_float(value: Any, default: float = float("nan")) -> float:
    return safe_float(value, default)


def t_stat(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if len(clean) < 3:
        return float("nan")
    std = clean.std(ddof=1)
    if not std:
        return float("nan")
    return float(clean.mean() / std * (len(clean) ** 0.5))


def build_synthetic_industry_daily() -> tuple[pd.DataFrame, dict[str, Any]]:
    stock_df, benchmark_df = load_panels()
    layer_tags = load_layer_tags()

    base = (
        stock_df.select(
            [
                "datetime",
                "symbol",
                "pct_chg",
                "close",
                "adv20_turnover",
                "eligible_component_row",
                "is_st",
                "is_suspended",
                "is_oneword_limit_up",
                "is_oneword_limit_down",
                "is_limit_up_close",
                "is_limit_down_close",
            ]
        )
        .join(
            layer_tags.select(
                [
                    "datetime",
                    "symbol",
                    "industry",
                    "market",
                    "adv20_turnover_q",
                    "turnover_rate_f_q",
                    "turnover_rate_f",
                    "circ_mv",
                    "total_mv",
                ]
            ),
            on=["datetime", "symbol"],
            how="left",
        )
        .filter(
            pl.col("eligible_component_row").fill_null(False)
            & pl.col("industry").is_not_null()
            & pl.col("pct_chg").is_not_null()
            & pl.col("pct_chg").is_finite()
            & pl.col("close").is_not_null()
            & pl.col("close").is_finite()
            & (~pl.col("is_st").fill_null(True))
            & (~pl.col("is_suspended").fill_null(True))
            & (pl.col("adv20_turnover_q") >= 3)
            & (pl.col("turnover_rate_f_q") >= 3)
        )
        .with_columns((pl.col("pct_chg") / 100.0).alias("stock_daily_ret"))
    )

    industry_daily = (
        base.group_by(["datetime", "industry"])
        .agg(
            pl.col("stock_daily_ret").mean().alias("daily_ret"),
            pl.col("stock_daily_ret").median().alias("median_stock_daily_ret"),
            pl.len().alias("stock_count"),
            pl.col("symbol").n_unique().alias("symbol_count"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
            pl.col("turnover_rate_f").median().alias("median_turnover_rate_f"),
            pl.col("circ_mv").median().alias("median_circ_mv"),
            pl.col("is_limit_up_close").fill_null(False).mean().alias("limit_up_close_ratio"),
            pl.col("is_limit_down_close").fill_null(False).mean().alias("limit_down_close_ratio"),
            pl.col("is_oneword_limit_up").fill_null(False).mean().alias("oneword_limit_up_ratio"),
            pl.col("is_oneword_limit_down").fill_null(False).mean().alias("oneword_limit_down_ratio"),
        )
        .filter(pl.col("stock_count") >= MIN_INDUSTRY_STOCKS)
        .sort(["industry", "datetime"])
    )

    market_daily = (
        base.group_by("datetime")
        .agg(
            pl.col("stock_daily_ret").mean().alias("synthetic_market_ret"),
            pl.col("industry").n_unique().alias("available_industries_raw"),
            pl.len().alias("stock_rows_raw"),
        )
        .sort("datetime")
    )
    benchmark_daily = benchmark_df.select(
        "datetime",
        (pl.col("pct_chg") / 100.0).alias("benchmark_daily_ret"),
    )

    panel = industry_daily.join(market_daily, on="datetime", how="left").join(benchmark_daily, on="datetime", how="left")
    panel = panel.with_columns(pl.col("industry").n_unique().over("datetime").alias("available_industry_count"))
    panel = panel.filter(pl.col("available_industry_count") >= MIN_DAILY_INDUSTRIES)

    meta = {
        "stock_rows_loaded": int(stock_df.height),
        "stock_rows_after_filter": int(base.height),
        "industry_daily_rows": int(panel.height),
        "industry_count": int(panel.select("industry").n_unique()),
        "min_industry_stocks": MIN_INDUSTRY_STOCKS,
        "min_daily_industries": MIN_DAILY_INDUSTRIES,
    }
    return panel.to_pandas(), meta


def add_forward_returns(group: pd.DataFrame) -> pd.DataFrame:
    work = group.sort_values("date").copy()
    gross = 1.0 + pd.to_numeric(work["daily_ret"], errors="coerce")
    for horizon in HORIZONS:
        future_gross = gross.shift(-1)
        work[f"fwd_ret_{horizon}d"] = (
            future_gross.rolling(horizon, min_periods=horizon).apply(np.prod, raw=True).shift(-(horizon - 1)) - 1.0
        )
    return work


def add_indicators(group: pd.DataFrame) -> pd.DataFrame:
    work = group.sort_values("date").copy()
    close = pd.to_numeric(work["industry_close"], errors="coerce")
    ret = pd.to_numeric(work["daily_ret"], errors="coerce")
    work["ret_5"] = close / close.shift(5) - 1.0
    work["ret_10"] = close / close.shift(10) - 1.0
    work["ret_20"] = close / close.shift(20) - 1.0
    work["mom_63_21"] = close.shift(21) / close.shift(63) - 1.0
    work["mom_126_21"] = close.shift(21) / close.shift(126) - 1.0
    work["mom_252_21"] = close.shift(21) / close.shift(252) - 1.0
    work["high_252"] = close.rolling(252, min_periods=126).max()
    work["near_high_252"] = close / work["high_252"]
    work["ma200"] = close.rolling(200, min_periods=120).mean()
    work["above_ma200"] = close > work["ma200"]
    work["volatility_20"] = ret.rolling(20, min_periods=15).std(ddof=0)
    work["volatility_60"] = ret.rolling(60, min_periods=30).std(ddof=0)
    work["volatility_ratio_20_60"] = work["volatility_20"] / work["volatility_60"]
    return add_forward_returns(work)


def rank_pct(frame: pd.DataFrame, column: str, ascending: bool) -> pd.Series:
    return frame.groupby("date")[column].rank(pct=True, ascending=ascending)


def build_feature_panel(industry_daily: pd.DataFrame) -> pd.DataFrame:
    work = industry_daily.copy()
    work["date"] = pd.to_datetime(work["datetime"], errors="coerce")
    for column in ("daily_ret", "synthetic_market_ret", "benchmark_daily_ret"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=["date", "industry", "daily_ret"]).sort_values(["industry", "date"])
    work["industry_close"] = work.groupby("industry")["daily_ret"].transform(lambda s: (1.0 + s.fillna(0.0)).cumprod())
    work = pd.concat([add_indicators(group) for _, group in work.groupby("industry", sort=False)], ignore_index=True)

    for horizon in HORIZONS:
        all_industry_mean = work.groupby("date")[f"fwd_ret_{horizon}d"].mean().rename(f"all_industry_fwd_ret_{horizon}d")
        work = work.merge(all_industry_mean, on="date", how="left")
        work[f"fwd_excess_{horizon}d"] = work[f"fwd_ret_{horizon}d"] - work[f"all_industry_fwd_ret_{horizon}d"]

    for column, ascending in (
        ("mom_63_21", False),
        ("mom_126_21", False),
        ("mom_252_21", False),
        ("near_high_252", False),
        ("ret_5", True),
        ("ret_10", True),
        ("ret_20", True),
        ("volatility_ratio_20_60", True),
        ("stock_count", False),
    ):
        work[f"{column}_rank"] = rank_pct(work, column, ascending=ascending)

    work["strength_core_score"] = (
        0.38 * work["mom_126_21_rank"]
        + 0.22 * work["mom_63_21_rank"]
        + 0.20 * work["mom_252_21_rank"]
        + 0.15 * work["near_high_252_rank"]
        + 0.05 * work["above_ma200"].astype(float)
    )
    work["pullback_quality_score"] = (
        0.48 * work["ret_5_rank"]
        + 0.30 * work["ret_10_rank"]
        + 0.12 * work["ret_20_rank"]
        + 0.10 * work["volatility_ratio_20_60_rank"]
    )
    work["strong_pullback_score"] = 0.62 * work["strength_core_score"] + 0.38 * work["pullback_quality_score"]
    return work


def select_model(panel: pd.DataFrame, model: str) -> pd.DataFrame:
    work = panel[panel["available_industry_count"] >= MIN_DAILY_INDUSTRIES].copy()
    if model == "strong_industry_pullback_core":
        selected = work[
            (work["strength_core_score"] >= 0.65)
            & (work["pullback_quality_score"] >= 0.60)
            & (work["above_ma200"])
        ].copy()
        selected["model_score"] = selected["strong_pullback_score"]
    elif model == "industry_momentum_control":
        selected = work[(work["strength_core_score"] >= 0.80) & (work["above_ma200"])].copy()
        selected["model_score"] = selected["strength_core_score"]
    elif model == "weak_industry_oversold_negative_control":
        selected = work[(work["strength_core_score"] <= 0.40) & (work["pullback_quality_score"] >= 0.60)].copy()
        selected["model_score"] = selected["pullback_quality_score"] - selected["strength_core_score"]
    elif model == "pure_cross_industry_reversal":
        selected = work[(work["ret_20_rank"] >= 0.80)].copy()
        selected["model_score"] = selected["ret_20_rank"]
    elif model == "near_high_pullback":
        selected = work[
            (work["near_high_252_rank"] >= 0.70)
            & (work["ret_5_rank"] >= 0.60)
            & (work["above_ma200"])
        ].copy()
        selected["model_score"] = 0.55 * selected["near_high_252_rank"] + 0.45 * selected["ret_5_rank"]
    else:
        raise ValueError(f"Unknown model: {model}")
    if selected.empty:
        return selected
    selected["model"] = model
    selected["daily_rank"] = selected.groupby("date")["model_score"].rank(method="first", ascending=False)
    return selected[selected["daily_rank"] <= TOP_N].copy()


def build_selected(panel: pd.DataFrame) -> pd.DataFrame:
    models = [
        "strong_industry_pullback_core",
        "near_high_pullback",
        "industry_momentum_control",
        "pure_cross_industry_reversal",
        "weak_industry_oversold_negative_control",
    ]
    parts = [select_model(panel, model) for model in models]
    parts = [part for part in parts if not part.empty]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True, sort=False)


def summarize_selected(selected: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if selected.empty:
        return pd.DataFrame()
    for model, group in selected.groupby("model"):
        for horizon in HORIZONS:
            daily = (
                group.groupby("date")
                .agg(
                    selected_count=("industry", "nunique"),
                    fwd_ret=(f"fwd_ret_{horizon}d", "mean"),
                    fwd_excess=(f"fwd_excess_{horizon}d", "mean"),
                )
                .dropna(subset=["fwd_ret", "fwd_excess"])
            )
            rows.append(
                {
                    "model": model,
                    "horizon": horizon,
                    "signal_days": int(len(daily)),
                    "selected_rows": int(len(group.dropna(subset=[f"fwd_ret_{horizon}d"]))),
                    "avg_selected_count": float(daily["selected_count"].mean()) if not daily.empty else float("nan"),
                    "mean_fwd_ret": float(daily["fwd_ret"].mean()) if not daily.empty else float("nan"),
                    "mean_fwd_excess": float(daily["fwd_excess"].mean()) if not daily.empty else float("nan"),
                    "median_fwd_excess": float(daily["fwd_excess"].median()) if not daily.empty else float("nan"),
                    "t_stat_excess": t_stat(daily["fwd_excess"]),
                    "positive_excess_day_ratio": float((daily["fwd_excess"] > 0).mean()) if not daily.empty else float("nan"),
                }
            )
    return pd.DataFrame(rows).sort_values(["horizon", "mean_fwd_excess"], ascending=[True, False])


def build_yearly(selected: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if selected.empty:
        return pd.DataFrame()
    selected = selected.copy()
    selected["year"] = selected["date"].dt.year
    for (model, year), group in selected.groupby(["model", "year"]):
        for horizon in HORIZONS:
            daily = group.groupby("date")[f"fwd_excess_{horizon}d"].mean().dropna()
            rows.append(
                {
                    "model": model,
                    "year": int(year),
                    "horizon": horizon,
                    "signal_days": int(len(daily)),
                    "mean_fwd_excess": float(daily.mean()) if not daily.empty else float("nan"),
                    "positive_excess_day_ratio": float((daily > 0).mean()) if not daily.empty else float("nan"),
                }
            )
    return pd.DataFrame(rows).sort_values(["model", "horizon", "year"])


def build_score_bucket(panel: pd.DataFrame) -> pd.DataFrame:
    work = panel[
        (panel["available_industry_count"] >= MIN_DAILY_INDUSTRIES)
        & panel["strong_pullback_score"].notna()
        & panel["fwd_ret_10d"].notna()
    ].copy()
    if work.empty:
        return pd.DataFrame()
    work["score_quintile"] = work.groupby("date")["strong_pullback_score"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=["q1_low", "q2", "q3", "q4", "q5_high"])
        if s.notna().sum() >= 5
        else pd.Series([pd.NA] * len(s), index=s.index)
    )
    return (
        work.dropna(subset=["score_quintile"])
        .groupby("score_quintile", observed=False)
        .agg(
            rows=("industry", "count"),
            mean_fwd_ret_10d=("fwd_ret_10d", "mean"),
            mean_fwd_excess_10d=("fwd_excess_10d", "mean"),
            positive_excess_ratio=("fwd_excess_10d", lambda s: float((s > 0).mean())),
        )
        .reset_index()
    )


def build_industry_contribution(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    group = selected[selected["model"] == "strong_industry_pullback_core"].copy()
    if group.empty:
        return pd.DataFrame()
    return (
        group.groupby("industry")
        .agg(
            active_days=("date", "nunique"),
            selected_rows=("industry", "count"),
            mean_fwd_excess_10d=("fwd_excess_10d", "mean"),
            mean_fwd_excess_20d=("fwd_excess_20d", "mean"),
            positive_excess_10d=("fwd_excess_10d", lambda s: float((s > 0).mean())),
        )
        .reset_index()
        .sort_values(["active_days", "mean_fwd_excess_10d"], ascending=False)
    )


def build_quality(summary: pd.DataFrame, score_bucket: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    model10 = summary[summary["horizon"] == 10].copy()
    core = model10[model10["model"] == "strong_industry_pullback_core"]
    weak = model10[model10["model"] == "weak_industry_oversold_negative_control"]
    reversal = model10[model10["model"] == "pure_cross_industry_reversal"]
    momentum = model10[model10["model"] == "industry_momentum_control"]
    core_excess = to_float(core["mean_fwd_excess"].iloc[0]) if not core.empty else float("nan")
    core_t = to_float(core["t_stat_excess"].iloc[0]) if not core.empty else float("nan")
    weak_excess = to_float(weak["mean_fwd_excess"].iloc[0]) if not weak.empty else float("nan")
    reversal_excess = to_float(reversal["mean_fwd_excess"].iloc[0]) if not reversal.empty else float("nan")
    momentum_excess = to_float(momentum["mean_fwd_excess"].iloc[0]) if not momentum.empty else float("nan")
    q5 = score_bucket[score_bucket["score_quintile"].astype(str) == "q5_high"]
    q1 = score_bucket[score_bucket["score_quintile"].astype(str) == "q1_low"]
    q5_excess = to_float(q5["mean_fwd_excess_10d"].iloc[0]) if not q5.empty else float("nan")
    q1_excess = to_float(q1["mean_fwd_excess_10d"].iloc[0]) if not q1.empty else float("nan")
    rows.extend(
        [
            {
                "checkpoint": "core_10d_excess_positive",
                "status": "pass" if core_excess > 0 else "fail",
                "value": pct(core_excess),
                "expected": ">0",
                "judgement": "强行业短回撤的10日行业超额应为正。",
            },
            {
                "checkpoint": "core_10d_t_stat",
                "status": "pass" if core_t >= 2.0 else "warn" if core_t > 0 else "fail",
                "value": f"{core_t:.3f}" if np.isfinite(core_t) else "NA",
                "expected": ">=2.0 preferred",
                "judgement": "行业合成样本比ETF样本更宽，应要求更高。",
            },
            {
                "checkpoint": "core_beats_weak_oversold",
                "status": "pass" if core_excess > weak_excess else "warn",
                "value": f"core={pct(core_excess)}, weak={pct(weak_excess)}",
                "expected": "core > weak",
                "judgement": "跨行业不能只买弱，强行业回撤应优于弱行业超跌。",
            },
            {
                "checkpoint": "core_beats_pure_reversal",
                "status": "pass" if core_excess > reversal_excess else "warn",
                "value": f"core={pct(core_excess)}, reversal={pct(reversal_excess)}",
                "expected": "core > pure reversal",
                "judgement": "如果纯行业反转更强，则强行业假设不成立。",
            },
            {
                "checkpoint": "momentum_control_nonnegative",
                "status": "pass" if momentum_excess >= 0 else "warn",
                "value": pct(momentum_excess),
                "expected": ">=0",
                "judgement": "跨行业动量若为负，行业强势底层需要重查。",
            },
            {
                "checkpoint": "score_q5_beats_q1",
                "status": "pass" if q5_excess > q1_excess else "warn",
                "value": f"q5={pct(q5_excess)}, q1={pct(q1_excess)}",
                "expected": "q5 > q1",
                "judgement": "综合分数至少应有端点方向性。",
            },
            {
                "checkpoint": "signal_span_days",
                "status": "pass" if selected["date"].nunique() >= 1000 else "warn",
                "value": str(int(selected["date"].nunique())) if not selected.empty else "0",
                "expected": ">=1000",
                "judgement": "行业信号应覆盖足够多交易日。",
            },
        ]
    )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: list[str] | None = None, limit: int = 40) -> str:
    if frame.empty:
        return "\n无数据。\n"
    work = frame.copy()
    if columns is not None:
        work = work[[col for col in columns if col in work.columns]]
    if limit > 0:
        work = work.head(limit)
    return work.to_markdown(index=False)


def format_pct_columns(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    for column in list(work.columns):
        if any(token in column for token in ("ret", "excess", "ratio")) and column not in {"horizon"}:
            work[f"{column}_pct"] = work[column].map(pct)
    return work


def build_report(
    panel: pd.DataFrame,
    selected: pd.DataFrame,
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    score_bucket: pd.DataFrame,
    industry_contribution: pd.DataFrame,
    quality: pd.DataFrame,
    meta: dict[str, Any],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    summary_display = format_pct_columns(summary)
    yearly_display = format_pct_columns(yearly)
    bucket_display = format_pct_columns(score_bucket)
    contribution_display = format_pct_columns(industry_contribution)
    return f"""# 股票震荡合成行业指数信号归因 v1

- 记录时间：{now}
- 当前研究线：股票震荡独立策略研究，不接入第78。
- 本阶段性质：本地股票面板合成行业指数的信号层归因，不是策略回测。
- 股票过滤：历史中证1000成分、非ST、非停牌、成交额和自由换手均不低于Q3。
- 行业日收益：行业内股票等权平均日收益。
- 合成行业数：`{meta.get("industry_count")}`。
- 合成行业日线行数：`{meta.get("industry_daily_rows")}`。
- 样本区间：`{panel["date"].min().date() if not panel.empty else "NA"}` 到 `{panel["date"].max().date() if not panel.empty else "NA"}`。

## 外部调研落点

- 行业ETF轮动的常见系统以中期行业相对动量做资产选择，而不是每日买最超跌行业。
- 短期反转文献提示，跨行业反转会被行业动量削弱，反转更自然的位置是行业内个股层。
- 因此本阶段重点比较：强行业回撤、纯行业动量、弱行业超跌、纯跨行业反转。

## 核心结果

{markdown_table(summary_display, ["model", "horizon", "signal_days", "selected_rows", "avg_selected_count", "mean_fwd_ret_pct", "mean_fwd_excess_pct", "median_fwd_excess_pct", "t_stat_excess", "positive_excess_day_ratio_pct"], 60)}

## 10日综合分数五分位

{markdown_table(bucket_display, ["score_quintile", "rows", "mean_fwd_ret_10d_pct", "mean_fwd_excess_10d_pct", "positive_excess_ratio_pct"], 10)}

## 强行业回撤贡献行业摘录

{markdown_table(contribution_display, ["industry", "active_days", "selected_rows", "mean_fwd_excess_10d_pct", "mean_fwd_excess_20d_pct", "positive_excess_10d_pct"], 40)}

## 年度摘录：10日超额

{markdown_table(yearly_display[yearly_display["horizon"] == 10], ["model", "year", "signal_days", "mean_fwd_excess_pct", "positive_excess_day_ratio_pct"], 120)}

## 质量检查

{markdown_table(quality, ["checkpoint", "status", "value", "expected", "judgement"], 20)}

## 运行前过拟合反思

- 判断：否。
- 原因：本阶段用本地股票面板合成行业指数，验证事前定义的行业强弱/回撤关系，不做交易参数搜索。

## 运行后过拟合反思

- 判断：否，但若直接交易化会过拟合。
- 原因：归因覆盖较多行业和日期，但仍是信号层；没有考虑ETF映射、买卖成本、容量和真实组合路径。

## 运行前继续价值反思

- 判断：是。
- 原因：13只ETF样本太小，合成行业指数可以先扩大信号层样本，判断行业强势回撤是否真实。

## 运行后继续价值反思

- 判断：取决于强行业回撤是否显著优于弱行业超跌和纯跨行业反转。
- 原因：如果强行业假设成立，下一步再补ETF映射/行业指数；如果不成立，应回到行业内个股残差路线。

## 输出文件

- `{PREFIX}_industry_daily.csv`
- `{PREFIX}_feature_panel.csv`
- `{PREFIX}_selected.csv`
- `{PREFIX}_summary.csv`
- `{PREFIX}_yearly.csv`
- `{PREFIX}_score_bucket.csv`
- `{PREFIX}_industry_contribution.csv`
- `{PREFIX}_quality_checkpoints.csv`
- `{PREFIX}_meta.json`
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    industry_daily, meta = build_synthetic_industry_daily()
    panel = build_feature_panel(industry_daily)
    selected = build_selected(panel)
    summary = summarize_selected(selected)
    yearly = build_yearly(selected)
    score_bucket = build_score_bucket(panel)
    industry_contribution = build_industry_contribution(selected)
    quality = build_quality(summary, score_bucket, selected)

    industry_daily.to_csv(OUTPUT_DIR / f"{PREFIX}_industry_daily.csv", index=False, encoding="utf-8-sig")
    panel.to_csv(OUTPUT_DIR / f"{PREFIX}_feature_panel.csv", index=False, encoding="utf-8-sig")
    selected.to_csv(OUTPUT_DIR / f"{PREFIX}_selected.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_summary.csv", index=False, encoding="utf-8-sig")
    yearly.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly.csv", index=False, encoding="utf-8-sig")
    score_bucket.to_csv(OUTPUT_DIR / f"{PREFIX}_score_bucket.csv", index=False, encoding="utf-8-sig")
    industry_contribution.to_csv(OUTPUT_DIR / f"{PREFIX}_industry_contribution.csv", index=False, encoding="utf-8-sig")
    quality.to_csv(OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv", index=False, encoding="utf-8-sig")

    meta.update(
        {
            "generated_at": datetime.now().isoformat(),
            "panel_rows": int(len(panel)),
            "selected_rows": int(len(selected)),
            "selected_signal_days": int(selected["date"].nunique()) if not selected.empty else 0,
            "horizons": HORIZONS,
            "top_n": TOP_N,
        }
    )
    write_json(OUTPUT_DIR / f"{PREFIX}_meta.json", meta)

    report = build_report(panel, selected, summary, yearly, score_bucket, industry_contribution, quality, meta)
    (OUTPUT_DIR / f"{PREFIX}_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()

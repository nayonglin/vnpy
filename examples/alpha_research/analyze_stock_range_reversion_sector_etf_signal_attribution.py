from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_stock_range_reversion_etf_industry_rotation_readiness import pct, safe_float


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
SOURCE_DIR: Path = NATIVE_RESULTS_DIR / "stock_range_reversion_sector_etf_data_2018_2026"
SOURCE_PREFIX: str = "stock_range_reversion_sector_etf_data_v1"
DAILY_PATH: Path = SOURCE_DIR / f"{SOURCE_PREFIX}_selected_daily.csv"
SUMMARY_PATH: Path = SOURCE_DIR / f"{SOURCE_PREFIX}_summary.csv"

OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_sector_etf_signal_attribution_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_sector_etf_signal_attribution_v1"

HORIZONS: tuple[int, ...] = (5, 10, 20)
MIN_DAILY_ETF_COUNT: int = 8


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def to_float(value: Any, default: float = float("nan")) -> float:
    return safe_float(value, default)


def add_forward_returns(group: pd.DataFrame) -> pd.DataFrame:
    work = group.sort_values("date").copy()
    gross = 1.0 + pd.to_numeric(work["daily_ret"], errors="coerce")
    for horizon in HORIZONS:
        future_gross = gross.shift(-1)
        fwd = future_gross.rolling(horizon, min_periods=horizon).apply(np.prod, raw=True).shift(-(horizon - 1)) - 1.0
        work[f"fwd_ret_{horizon}d"] = fwd
    return work


def add_indicators(group: pd.DataFrame) -> pd.DataFrame:
    work = group.sort_values("date").copy()
    close = pd.to_numeric(work["close"], errors="coerce")
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
    work["amount_20"] = pd.to_numeric(work["amount"], errors="coerce").rolling(20, min_periods=10).median()
    return add_forward_returns(work)


def rank_pct(frame: pd.DataFrame, column: str, ascending: bool) -> pd.Series:
    return frame.groupby("date")[column].rank(pct=True, ascending=ascending)


def build_feature_panel(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return daily
    work = daily.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    for column in ("close", "daily_ret", "amount"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=["date", "ts_code", "close", "daily_ret"]).sort_values(["ts_code", "date"])
    work = pd.concat([add_indicators(group) for _, group in work.groupby("ts_code", sort=False)], ignore_index=True)
    for column, ascending in (
        ("mom_63_21", False),
        ("mom_126_21", False),
        ("mom_252_21", False),
        ("near_high_252", False),
        ("ret_5", True),
        ("ret_10", True),
        ("ret_20", True),
        ("volatility_ratio_20_60", True),
    ):
        work[f"{column}_rank"] = rank_pct(work, column, ascending=ascending)
    work["available_etf_count"] = work.groupby("date")["ts_code"].transform("nunique")
    work["strength_core_score"] = (
        0.45 * work["mom_126_21_rank"]
        + 0.25 * work["mom_63_21_rank"]
        + 0.20 * work["near_high_252_rank"]
        + 0.10 * work["above_ma200"].astype(float)
    )
    work["pullback_quality_score"] = (
        0.55 * work["ret_5_rank"]
        + 0.25 * work["ret_10_rank"]
        + 0.20 * work["volatility_ratio_20_60_rank"]
    )
    work["strong_pullback_score"] = 0.62 * work["strength_core_score"] + 0.38 * work["pullback_quality_score"]
    return work


def select_model(panel: pd.DataFrame, model: str) -> pd.DataFrame:
    work = panel[panel["available_etf_count"] >= MIN_DAILY_ETF_COUNT].copy()
    if model == "strong_industry_pullback_core":
        selected = work[
            (work["strength_core_score"] >= 0.60)
            & (work["pullback_quality_score"] >= 0.60)
            & (work["above_ma200"])
        ].copy()
        selected["model_score"] = selected["strong_pullback_score"]
    elif model == "near_high_pullback":
        selected = work[
            (work["near_high_252_rank"] >= 0.60)
            & (work["ret_5_rank"] >= 0.60)
            & (work["above_ma200"])
        ].copy()
        selected["model_score"] = 0.55 * selected["near_high_252_rank"] + 0.45 * selected["ret_5_rank"]
    elif model == "momentum_only_control":
        selected = work[(work["strength_core_score"] >= 0.75) & (work["above_ma200"])].copy()
        selected["model_score"] = selected["strength_core_score"]
    elif model == "weak_oversold_negative_control":
        selected = work[(work["strength_core_score"] <= 0.40) & (work["pullback_quality_score"] >= 0.60)].copy()
        selected["model_score"] = selected["pullback_quality_score"] - selected["strength_core_score"]
    else:
        raise ValueError(f"Unknown model: {model}")
    if selected.empty:
        return selected
    selected["model"] = model
    selected["daily_rank"] = selected.groupby("date")["model_score"].rank(method="first", ascending=False)
    return selected[selected["daily_rank"] <= 3].copy()


def build_selected(panel: pd.DataFrame) -> pd.DataFrame:
    models = [
        "strong_industry_pullback_core",
        "near_high_pullback",
        "momentum_only_control",
        "weak_oversold_negative_control",
    ]
    parts = [select_model(panel, model) for model in models]
    parts = [part for part in parts if not part.empty]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True, sort=False)


def attach_excess(panel: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return selected
    benchmark = panel[panel["available_etf_count"] >= MIN_DAILY_ETF_COUNT].copy()
    for horizon in HORIZONS:
        date_mean = benchmark.groupby("date")[f"fwd_ret_{horizon}d"].mean().rename(f"bench_fwd_ret_{horizon}d")
        selected = selected.merge(date_mean, on="date", how="left")
        selected[f"fwd_excess_{horizon}d"] = selected[f"fwd_ret_{horizon}d"] - selected[f"bench_fwd_ret_{horizon}d"]
    return selected


def t_stat(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if len(clean) < 3:
        return float("nan")
    std = clean.std(ddof=1)
    if not std:
        return float("nan")
    return float(clean.mean() / std * (len(clean) ** 0.5))


def summarize_selected(selected: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if selected.empty:
        return pd.DataFrame()
    for model, group in selected.groupby("model"):
        for horizon in HORIZONS:
            daily = (
                group.groupby("date")
                .agg(
                    selected_count=("ts_code", "nunique"),
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
        (panel["available_etf_count"] >= MIN_DAILY_ETF_COUNT)
        & panel["strong_pullback_score"].notna()
        & panel["fwd_ret_10d"].notna()
    ].copy()
    if work.empty:
        return pd.DataFrame()
    work["score_tertile"] = work.groupby("date")["strong_pullback_score"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=["low", "mid", "high"])
        if s.notna().sum() >= 3
        else pd.Series([pd.NA] * len(s), index=s.index)
    )
    date_mean = work.groupby("date")["fwd_ret_10d"].mean().rename("bench_fwd_ret_10d")
    work = work.merge(date_mean, on="date", how="left")
    work["fwd_excess_10d"] = work["fwd_ret_10d"] - work["bench_fwd_ret_10d"]
    return (
        work.dropna(subset=["score_tertile"])
        .groupby("score_tertile", observed=False)
        .agg(
            rows=("ts_code", "count"),
            mean_fwd_ret_10d=("fwd_ret_10d", "mean"),
            mean_fwd_excess_10d=("fwd_excess_10d", "mean"),
            positive_excess_ratio=("fwd_excess_10d", lambda s: float((s > 0).mean())),
        )
        .reset_index()
    )


def build_quality(summary: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    model10 = summary[summary["horizon"] == 10].copy()
    core = model10[model10["model"] == "strong_industry_pullback_core"]
    negative = model10[model10["model"] == "weak_oversold_negative_control"]
    core_excess = to_float(core["mean_fwd_excess"].iloc[0]) if not core.empty else float("nan")
    core_t = to_float(core["t_stat_excess"].iloc[0]) if not core.empty else float("nan")
    neg_excess = to_float(negative["mean_fwd_excess"].iloc[0]) if not negative.empty else float("nan")
    rows.append(
        {
            "checkpoint": "core_10d_excess_positive",
            "status": "pass" if core_excess > 0 else "fail",
            "value": pct(core_excess),
            "expected": ">0",
            "judgement": "强行业短回撤的10日超额应为正。",
        }
    )
    rows.append(
        {
            "checkpoint": "core_10d_t_stat",
            "status": "pass" if core_t >= 1.5 else "warn" if core_t > 0 else "fail",
            "value": f"{core_t:.3f}" if np.isfinite(core_t) else "NA",
            "expected": ">=1.5 preferred",
            "judgement": "样本只有13只ETF，t值只做方向参考。",
        }
    )
    rows.append(
        {
            "checkpoint": "negative_control_weaker",
            "status": "pass" if core_excess > neg_excess else "warn",
            "value": f"core={pct(core_excess)}, negative={pct(neg_excess)}",
            "expected": "core > negative",
            "judgement": "如果弱行业超跌也同样强，说明不是行业强势逻辑。",
        }
    )
    rows.append(
        {
            "checkpoint": "signal_span_days",
            "status": "pass" if selected["date"].nunique() >= 500 else "warn",
            "value": str(int(selected["date"].nunique())) if not selected.empty else "0",
            "expected": ">=500",
            "judgement": "信号日跨度越短，越不能策略化。",
        }
    )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: list[str] | None = None, limit: int = 30) -> str:
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
    for column in work.columns:
        if any(token in column for token in ("ret", "excess", "ratio")) and column not in {"horizon"}:
            work[f"{column}_pct"] = work[column].map(pct)
    return work


def build_report(
    panel: pd.DataFrame,
    selected: pd.DataFrame,
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    score_bucket: pd.DataFrame,
    quality: pd.DataFrame,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    summary_display = format_pct_columns(summary)
    yearly_display = format_pct_columns(yearly)
    bucket_display = format_pct_columns(score_bucket)
    return f"""# 股票震荡行业/主题ETF信号归因 v1

- 记录时间：{now}
- 当前研究线：股票震荡独立策略研究，不接入第78。
- 本阶段性质：13只长历史行业/主题ETF的信号层归因，不是策略回测。
- 输入数据：`{DAILY_PATH}`
- ETF数量：`{panel["ts_code"].nunique() if not panel.empty else 0}`。
- 样本区间：`{panel["date"].min().date() if not panel.empty else "NA"}` 到 `{panel["date"].max().date() if not panel.empty else "NA"}`。
- 模型口径：中期强势使用`63/126/252日跳过近21日动量`和`接近252日高点`，短期回撤使用`5/10日回撤`和`短期波动收缩`。

## 核心结果

{markdown_table(summary_display, ["model", "horizon", "signal_days", "selected_rows", "avg_selected_count", "mean_fwd_ret_pct", "mean_fwd_excess_pct", "median_fwd_excess_pct", "t_stat_excess", "positive_excess_day_ratio_pct"], 40)}

## 10日综合分数三分位

{markdown_table(bucket_display, ["score_tertile", "rows", "mean_fwd_ret_10d_pct", "mean_fwd_excess_10d_pct", "positive_excess_ratio_pct"], 10)}

## 年度摘录

{markdown_table(yearly_display[yearly_display["horizon"] == 10], ["model", "year", "signal_days", "mean_fwd_excess_pct", "positive_excess_day_ratio_pct"], 80)}

## 质量检查

{markdown_table(quality, ["checkpoint", "status", "value", "expected", "judgement"], 20)}

## 运行前过拟合反思

- 判断：否。
- 原因：本阶段只验证事前定义的行业强势和短期回撤是否有方向，不做交易参数搜索。

## 运行后过拟合反思

- 判断：暂不构成过拟合，但不能策略化。
- 原因：样本只有13只ETF，适合看方向和反证，不足以定参数或上线。

## 运行前继续价值反思

- 判断：是。
- 原因：行业ETF数据包已覆盖主要行业，能先验证强行业回撤逻辑是否优于弱行业超跌。

## 运行后继续价值反思

- 判断：取决于核心模型是否显著优于负对照。
- 原因：若强行业短回撤有正超额且负对照更弱，则值得补全ETF/行业指数后扩样本；否则应暂停行业ETF路线。

## 输出文件

- `{PREFIX}_feature_panel.csv`
- `{PREFIX}_selected.csv`
- `{PREFIX}_summary.csv`
- `{PREFIX}_yearly.csv`
- `{PREFIX}_score_bucket.csv`
- `{PREFIX}_quality_checkpoints.csv`
- `{PREFIX}_meta.json`
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily = read_csv(DAILY_PATH)
    source_summary = read_csv(SUMMARY_PATH)
    if daily.empty:
        raise FileNotFoundError(f"Sector ETF daily data not found: {DAILY_PATH}")
    panel = build_feature_panel(daily)
    selected = attach_excess(panel, build_selected(panel))
    summary = summarize_selected(selected)
    yearly = build_yearly(selected)
    score_bucket = build_score_bucket(panel)
    quality = build_quality(summary, selected)

    panel.to_csv(OUTPUT_DIR / f"{PREFIX}_feature_panel.csv", index=False, encoding="utf-8-sig")
    selected.to_csv(OUTPUT_DIR / f"{PREFIX}_selected.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_summary.csv", index=False, encoding="utf-8-sig")
    yearly.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly.csv", index=False, encoding="utf-8-sig")
    score_bucket.to_csv(OUTPUT_DIR / f"{PREFIX}_score_bucket.csv", index=False, encoding="utf-8-sig")
    quality.to_csv(OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv", index=False, encoding="utf-8-sig")

    meta = {
        "generated_at": datetime.now().isoformat(),
        "source_daily": str(DAILY_PATH),
        "source_summary": str(SUMMARY_PATH),
        "source_etf_count": int(source_summary["ts_code"].nunique()) if not source_summary.empty else 0,
        "panel_rows": int(len(panel)),
        "selected_rows": int(len(selected)),
        "selected_signal_days": int(selected["date"].nunique()) if not selected.empty else 0,
        "horizons": HORIZONS,
        "min_daily_etf_count": MIN_DAILY_ETF_COUNT,
    }
    write_json(OUTPUT_DIR / f"{PREFIX}_meta.json", meta)

    report = build_report(panel, selected, summary, yearly, score_bucket, quality)
    (OUTPUT_DIR / f"{PREFIX}_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()

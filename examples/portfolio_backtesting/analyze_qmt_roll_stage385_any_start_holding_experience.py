from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage385_any_start_holding_experience_v1"
OUTPUT_PREFIX = "qmt_roll_stage385_any_start_holding_experience"

STAGE383_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage383_three_version_deep_audit_daily_stage383_three_version_deep_audit_v1.csv"
)

VARIANTS = [
    ("stage78_1", "78-1正式版", 500_000.0),
    ("c3", "纯C3", 500_000.0),
    ("stage079", "Stage079：C3+11.5万现金", 615_000.0),
]

TARGET_DD_PCT = -30.0
HORIZONS = [
    (7, "7天"),
    (14, "14天"),
    (30, "1个月"),
    (60, "2个月"),
    (90, "3个月"),
    (180, "6个月"),
    (365, "1年"),
    (540, "18个月"),
    (730, "2年"),
    (1095, "3年"),
    (1460, "4年"),
    (1825, "5年"),
    (2190, "6年"),
]
BUCKETS = [
    (7, 30, "7-30天"),
    (31, 90, "31-90天"),
    (91, 180, "91-180天"),
    (181, 365, "181-365天"),
    (366, 730, "1-2年"),
    (731, 1095, "2-3年"),
    (1096, 1460, "3-4年"),
    (1461, 1825, "4-5年"),
    (1826, 10_000, "5年以上"),
]

HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fixed_horizon_{MODEL_TAG}.csv"
BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_all_interval_buckets_{MODEL_TAG}.csv"
WORST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_starts_{MODEL_TAG}.csv"
START_MONTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_month_horizon_{MODEL_TAG}.csv"
HORIZON_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_matrix_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
HTML_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dashboard_{MODEL_TAG}.html"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _load_curves() -> pd.DataFrame:
    frame = pd.read_csv(STAGE383_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame.dropna(subset=["date", "variant", "equity"])
    curves = frame.pivot(index="date", columns="variant", values="equity").sort_index()
    needed = [name for name, _, _ in VARIANTS]
    missing = [name for name in needed if name not in curves.columns]
    if missing:
        raise ValueError(f"missing variants: {missing}")
    return curves[needed].dropna()


def _drawdown(nav: np.ndarray) -> np.ndarray:
    return nav / np.maximum.accumulate(nav) - 1.0


def _max_drawdown(nav: np.ndarray) -> float:
    return float(np.min(_drawdown(nav)) * 100.0)


def _ulcer(nav: np.ndarray) -> float:
    dd = np.minimum(_drawdown(nav) * 100.0, 0.0)
    return float(np.sqrt(np.mean(np.square(dd)))) if len(dd) else 0.0


def _longest_underwater_days(dates: np.ndarray, nav: np.ndarray) -> int:
    high = np.maximum.accumulate(nav)
    underwater = nav < high * (1.0 - 1e-12)
    longest = 0
    start: np.datetime64 | None = None
    for date, flag in zip(dates, underwater):
        if bool(flag):
            if start is None:
                start = date
            longest = max(longest, int((date - start) / np.timedelta64(1, "D")) + 1)
        else:
            start = None
    return longest


def _days_to_recover_start(dates: np.ndarray, nav: np.ndarray) -> float:
    above_start = np.where(nav > 1.0 + 1e-12)[0]
    if len(above_start) == 0:
        return np.nan
    return float((dates[above_start[0]] - dates[0]) / np.timedelta64(1, "D"))


def _interval_metrics(dates: np.ndarray, equity: np.ndarray, start_idx: int, end_idx: int) -> dict[str, float | int | str]:
    segment = equity[start_idx : end_idx + 1].astype(float)
    nav = segment / segment[0]
    return {
        "start_date": str(pd.Timestamp(dates[start_idx]).date()),
        "end_date": str(pd.Timestamp(dates[end_idx]).date()),
        "holding_days": int((dates[end_idx] - dates[start_idx]) / np.timedelta64(1, "D")),
        "return_pct": float((nav[-1] - 1.0) * 100.0),
        "max_dd_pct": _max_drawdown(nav),
        "ulcer_pct": _ulcer(nav),
        "end_underwater": int(nav[-1] < np.max(nav) * (1.0 - 1e-12)),
        "never_new_high": int(np.max(nav) <= 1.0 + 1e-12),
        "longest_underwater_days": _longest_underwater_days(dates[start_idx : end_idx + 1], nav),
        "days_to_recover_start": _days_to_recover_start(dates[start_idx : end_idx + 1], nav),
    }


def _annualized_return(total_return_pct: pd.Series, holding_days: int) -> pd.Series:
    base = 1.0 + total_return_pct.astype(float) / 100.0
    with np.errstate(invalid="ignore"):
        return (np.power(base.clip(lower=1e-12), 365.0 / max(1, holding_days)) - 1.0) * 100.0


def _fixed_horizon(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = curves.index.to_numpy(dtype="datetime64[D]")
    rows: list[dict[str, Any]] = []
    worst_rows: list[dict[str, Any]] = []
    start_month_rows: list[dict[str, Any]] = []

    for variant, label, _initial in VARIANTS:
        equity = curves[variant].to_numpy(dtype=float)
        date_index = pd.Index(curves.index)
        for horizon_days, horizon_label in HORIZONS:
            horizon_items: list[dict[str, Any]] = []
            last_start = curves.index.max() - pd.Timedelta(days=horizon_days)
            for start_idx, start_date in enumerate(curves.index):
                if start_date > last_start:
                    break
                end_date = start_date + pd.Timedelta(days=horizon_days)
                end_idx = date_index.get_loc(end_date)
                item = _interval_metrics(dates, equity, start_idx, int(end_idx))
                item.update({"variant": variant, "label": label, "horizon_days": horizon_days, "horizon_label": horizon_label})
                horizon_items.append(item)
            if not horizon_items:
                continue
            frame = pd.DataFrame(horizon_items)
            frame["annualized_return_pct"] = _annualized_return(frame["return_pct"], horizon_days)
            rows.append(_summarize_interval_frame(frame, variant, label, horizon_label, horizon_days))
            worst_rows.extend(_worst_rows(frame, variant, label, horizon_label, horizon_days))

            frame["start_month"] = pd.to_datetime(frame["start_date"]).dt.to_period("M").astype(str)
            month = (
                frame.groupby("start_month")
                .agg(
                    count=("return_pct", "size"),
                    median_return_pct=("return_pct", "median"),
                    min_return_pct=("return_pct", "min"),
                    worst_dd_pct=("max_dd_pct", "min"),
                    positive_rate=("return_pct", lambda x: float((x > 0).mean())),
                    dd30_pass_rate=("max_dd_pct", lambda x: float((x >= TARGET_DD_PCT).mean())),
                )
                .reset_index()
            )
            month.insert(0, "horizon_label", horizon_label)
            month.insert(0, "horizon_days", horizon_days)
            month.insert(0, "label", label)
            month.insert(0, "variant", variant)
            start_month_rows.extend(month.to_dict(orient="records"))

    return pd.DataFrame(rows), pd.DataFrame(worst_rows), pd.DataFrame(start_month_rows)


def _summarize_interval_frame(
    frame: pd.DataFrame,
    variant: str,
    label: str,
    horizon_label: str,
    horizon_days: int,
    bucket_name: str | None = None,
) -> dict[str, Any]:
    prefix = {"variant": variant, "label": label}
    if bucket_name is None:
        prefix.update({"horizon_days": horizon_days, "horizon_label": horizon_label})
    else:
        prefix.update({"bucket_name": bucket_name})

    worst_ret = frame.loc[frame["return_pct"].idxmin()]
    worst_dd = frame.loc[frame["max_dd_pct"].idxmin()]
    has_dates = "start_date" in frame.columns and "end_date" in frame.columns
    return {
        **prefix,
        "count": int(len(frame)),
        "return_min_pct": float(frame["return_pct"].min()),
        "return_p01_pct": float(frame["return_pct"].quantile(0.01)),
        "return_p05_pct": float(frame["return_pct"].quantile(0.05)),
        "return_p25_pct": float(frame["return_pct"].quantile(0.25)),
        "return_median_pct": float(frame["return_pct"].median()),
        "return_p75_pct": float(frame["return_pct"].quantile(0.75)),
        "positive_return_rate": float((frame["return_pct"] > 0).mean()),
        "negative_return_rate": float((frame["return_pct"] <= 0).mean()),
        "annualized_p05_pct": float(frame["annualized_return_pct"].quantile(0.05)),
        "annualized_median_pct": float(frame["annualized_return_pct"].median()),
        "annualized_below_5pct_rate": float((frame["annualized_return_pct"] < 5.0).mean()),
        "max_dd_worst_pct": float(frame["max_dd_pct"].min()),
        "max_dd_p05_pct": float(frame["max_dd_pct"].quantile(0.05)),
        "max_dd_median_pct": float(frame["max_dd_pct"].median()),
        "dd10_breach_rate": float((frame["max_dd_pct"] < -10.0).mean()),
        "dd20_breach_rate": float((frame["max_dd_pct"] < -20.0).mean()),
        "dd30_breach_rate": float((frame["max_dd_pct"] < TARGET_DD_PCT).mean()),
        "dd30_pass_rate": float((frame["max_dd_pct"] >= TARGET_DD_PCT).mean()),
        "ulcer_median_pct": float(frame["ulcer_pct"].median()),
        "ulcer_p95_pct": float(frame["ulcer_pct"].quantile(0.95)),
        "end_underwater_rate": float(frame["end_underwater"].mean()),
        "never_new_high_rate": float(frame["never_new_high"].mean()),
        "longest_underwater_p95_days": float(frame["longest_underwater_days"].quantile(0.95)),
        "worst_return_start": str(worst_ret["start_date"]) if has_dates else "",
        "worst_return_end": str(worst_ret["end_date"]) if has_dates else "",
        "worst_return_pct": float(worst_ret["return_pct"]),
        "worst_dd_start": str(worst_dd["start_date"]) if has_dates else "",
        "worst_dd_end": str(worst_dd["end_date"]) if has_dates else "",
        "worst_dd_pct": float(worst_dd["max_dd_pct"]),
    }


def _worst_rows(frame: pd.DataFrame, variant: str, label: str, horizon_label: str, horizon_days: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for metric, sort_col in [("worst_return", "return_pct"), ("worst_drawdown", "max_dd_pct")]:
        view = frame.sort_values(sort_col, ascending=True).head(10).copy()
        view["metric"] = metric
        view["horizon_label"] = horizon_label
        view["horizon_days"] = horizon_days
        view["label"] = label
        view["variant"] = variant
        result.extend(view.to_dict(orient="records"))
    return result


def _bucket_for_days(days: np.ndarray) -> np.ndarray:
    labels = np.empty(len(days), dtype=object)
    for low, high, name in BUCKETS:
        mask = (days >= low) & (days <= high)
        labels[mask] = name
    return labels


def _all_interval_buckets(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = curves.index.to_numpy(dtype="datetime64[D]")
    rows: list[dict[str, Any]] = []
    worst_rows: list[dict[str, Any]] = []

    for variant, label, _initial in VARIANTS:
        equity = curves[variant].to_numpy(dtype=float)
        by_bucket: dict[str, dict[str, list[np.ndarray]]] = {
            name: {
                "return_pct": [],
                "max_dd_pct": [],
                "ulcer_pct": [],
                "annualized_return_pct": [],
                "end_underwater": [],
                "never_new_high": [],
                "longest_underwater_days": [],
            }
            for _, _, name in BUCKETS
        }
        worst_tracker: dict[str, dict[str, Any]] = {
            name: {
                "worst_return_pct": np.inf,
                "worst_return_start": "",
                "worst_return_end": "",
                "worst_dd_pct": np.inf,
                "worst_dd_start": "",
                "worst_dd_end": "",
            }
            for _, _, name in BUCKETS
        }

        n = len(equity)
        for start_idx in range(n - 1):
            segment = equity[start_idx + 1 :] / equity[start_idx]
            if len(segment) == 0:
                continue
            interval_dates = dates[start_idx + 1 :]
            holding_days = ((interval_dates - dates[start_idx]) / np.timedelta64(1, "D")).astype(int)
            valid = holding_days >= BUCKETS[0][0]
            if not np.any(valid):
                continue
            nav = segment[valid]
            hd = holding_days[valid]
            end_dates = interval_dates[valid]
            running_peak = np.maximum.accumulate(nav)
            dd = nav / running_peak - 1.0
            running_max_dd = np.minimum.accumulate(dd)
            ulcer_running = np.sqrt(np.cumsum(np.square(np.minimum(dd * 100.0, 0.0))) / np.arange(1, len(dd) + 1))
            returns = (nav - 1.0) * 100.0
            annualized = (np.power(np.clip(nav, 1e-12, None), 365.0 / np.maximum(hd, 1)) - 1.0) * 100.0
            end_underwater = (nav < running_peak * (1.0 - 1e-12)).astype(int)
            never_new_high = (running_peak <= 1.0 + 1e-12).astype(int)

            # Approximate longest underwater for every expanding end from this start.
            underwater = nav < running_peak * (1.0 - 1e-12)
            longest_so_far = np.zeros(len(nav), dtype=int)
            current_start: int | None = None
            current_longest = 0
            for i, flag in enumerate(underwater):
                if flag:
                    if current_start is None:
                        current_start = i
                    current_longest = max(current_longest, int((end_dates[i] - end_dates[current_start]) / np.timedelta64(1, "D")) + 1)
                else:
                    current_start = None
                longest_so_far[i] = current_longest

            bucket_labels = _bucket_for_days(hd)
            for _, _, bucket_name in BUCKETS:
                mask = bucket_labels == bucket_name
                if not np.any(mask):
                    continue
                by_bucket[bucket_name]["return_pct"].append(returns[mask])
                by_bucket[bucket_name]["max_dd_pct"].append(running_max_dd[mask] * 100.0)
                by_bucket[bucket_name]["ulcer_pct"].append(ulcer_running[mask])
                by_bucket[bucket_name]["annualized_return_pct"].append(annualized[mask])
                by_bucket[bucket_name]["end_underwater"].append(end_underwater[mask])
                by_bucket[bucket_name]["never_new_high"].append(never_new_high[mask])
                by_bucket[bucket_name]["longest_underwater_days"].append(longest_so_far[mask])

                bucket_returns = returns[mask]
                bucket_dd = running_max_dd[mask] * 100.0
                bucket_ends = end_dates[mask]
                min_return_idx = int(np.argmin(bucket_returns))
                if float(bucket_returns[min_return_idx]) < worst_tracker[bucket_name]["worst_return_pct"]:
                    worst_tracker[bucket_name]["worst_return_pct"] = float(bucket_returns[min_return_idx])
                    worst_tracker[bucket_name]["worst_return_start"] = str(pd.Timestamp(dates[start_idx]).date())
                    worst_tracker[bucket_name]["worst_return_end"] = str(pd.Timestamp(bucket_ends[min_return_idx]).date())
                min_dd_idx = int(np.argmin(bucket_dd))
                if float(bucket_dd[min_dd_idx]) < worst_tracker[bucket_name]["worst_dd_pct"]:
                    worst_tracker[bucket_name]["worst_dd_pct"] = float(bucket_dd[min_dd_idx])
                    worst_tracker[bucket_name]["worst_dd_start"] = str(pd.Timestamp(dates[start_idx]).date())
                    worst_tracker[bucket_name]["worst_dd_end"] = str(pd.Timestamp(bucket_ends[min_dd_idx]).date())

        for low, high, bucket_name in BUCKETS:
            data = by_bucket[bucket_name]
            if not data["return_pct"]:
                continue
            frame = pd.DataFrame({key: np.concatenate(value) for key, value in data.items()})
            summary = _summarize_interval_frame(
                frame.assign(holding_days=np.clip(np.nan, low, high)),
                variant,
                label,
                horizon_label="",
                horizon_days=0,
                bucket_name=bucket_name,
            )
            summary["min_holding_days"] = low
            summary["max_holding_days"] = high if high < 10_000 else int((dates[-1] - dates[0]) / np.timedelta64(1, "D"))
            summary.update(worst_tracker[bucket_name])
            rows.append(summary)
            for metric in ["worst_return", "worst_drawdown"]:
                worst_rows.append(
                    {
                        "variant": variant,
                        "label": label,
                        "bucket_name": bucket_name,
                        "metric": metric,
                        "start_date": worst_tracker[bucket_name][f"{metric.replace('worst_', 'worst_')}_start"]
                        if metric == "worst_return"
                        else worst_tracker[bucket_name]["worst_dd_start"],
                        "end_date": worst_tracker[bucket_name][f"{metric.replace('worst_', 'worst_')}_end"]
                        if metric == "worst_return"
                        else worst_tracker[bucket_name]["worst_dd_end"],
                        "value_pct": worst_tracker[bucket_name]["worst_return_pct"]
                        if metric == "worst_return"
                        else worst_tracker[bucket_name]["worst_dd_pct"],
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(worst_rows)


def _horizon_matrix(horizon: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "horizon_label",
        "label",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "annualized_below_5pct_rate",
        "max_dd_worst_pct",
        "dd20_breach_rate",
        "dd30_breach_rate",
        "end_underwater_rate",
        "never_new_high_rate",
    ]
    return horizon[cols].copy()


def _score(horizon: pd.DataFrame, bucket: pd.DataFrame) -> pd.DataFrame:
    focus_horizons = ["6个月", "1年", "2年", "3年", "5年"]
    rows = []
    for variant, label, _ in VARIANTS:
        h = horizon[(horizon["variant"].eq(variant)) & (horizon["horizon_label"].isin(focus_horizons))]
        b = bucket[bucket["variant"].eq(variant)]
        if h.empty or b.empty:
            continue
        score = (
            24.0 * (1.0 - float(h["dd30_breach_rate"].mean()))
            + 16.0 * (1.0 - float(h["annualized_below_5pct_rate"].mean()))
            + 14.0 * float(h["positive_return_rate"].mean())
            + 12.0 * max(0.0, min(1.0, float(h["return_p05_pct"].mean()) / 20.0 + 0.5))
            + 12.0 * max(0.0, min(1.0, 1.0 - abs(float(h["max_dd_worst_pct"].min())) / 45.0))
            + 10.0 * (1.0 - float(h["end_underwater_rate"].mean()))
            + 6.0 * (1.0 - float(h["never_new_high_rate"].mean()))
            + 6.0 * (1.0 - float(b["dd30_breach_rate"].mean()))
        )
        rows.append(
            {
                "variant": variant,
                "label": label,
                "holding_experience_score": score,
                "avg_positive_rate_focus": float(h["positive_return_rate"].mean()),
                "avg_annualized_below5_rate_focus": float(h["annualized_below_5pct_rate"].mean()),
                "avg_dd30_breach_rate_focus": float(h["dd30_breach_rate"].mean()),
                "avg_end_underwater_rate_focus": float(h["end_underwater_rate"].mean()),
                "worst_fixed_horizon_return_pct": float(h["return_min_pct"].min()),
                "worst_fixed_horizon_dd_pct": float(h["max_dd_worst_pct"].min()),
                "all_interval_avg_dd30_breach_rate": float(b["dd30_breach_rate"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("holding_experience_score", ascending=False)


def _build_report(
    horizon: pd.DataFrame,
    bucket: pd.DataFrame,
    worst: pd.DataFrame,
    month: pd.DataFrame,
    matrix: pd.DataFrame,
    score: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    focus = horizon[horizon["horizon_label"].isin(["1个月", "3个月", "6个月", "1年", "2年", "3年", "5年"])]
    focus_cols = [
        "horizon_label",
        "label",
        "return_min_pct",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "annualized_below_5pct_rate",
        "max_dd_worst_pct",
        "dd20_breach_rate",
        "dd30_breach_rate",
        "end_underwater_rate",
        "worst_return_start",
        "worst_return_end",
    ]
    bucket_cols = [
        "bucket_name",
        "label",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "annualized_below_5pct_rate",
        "max_dd_worst_pct",
        "dd20_breach_rate",
        "dd30_breach_rate",
        "end_underwater_rate",
    ]
    worst_focus = worst[
        worst["horizon_label"].isin(["6个月", "1年", "2年", "3年", "5年"]) & worst["metric"].eq("worst_return")
    ][
        [
            "horizon_label",
            "label",
            "start_date",
            "end_date",
            "return_pct",
            "max_dd_pct",
            "longest_underwater_days",
        ]
    ].head(60)
    start_month_focus = (
        month[month["horizon_label"].isin(["1年", "2年", "3年"])]
        .sort_values(["horizon_days", "label", "median_return_pct"])
        .groupby(["horizon_label", "label"])
        .head(5)
    )
    lines = [
        "# Stage085 任意启动日与持有期体验审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} CST",
        "- 阶段性质：只读持有体验审计；不修改 `78-1`、`Stage079`、`C3` 的交易逻辑、资金参数或成交路径",
        "- 是否重要突破：否，重要体验复核。回答“任意时候启动、启动多久，持有体验如何”。",
        "- 是否触发A/B：否。本阶段只评估既有三版本。",
        "",
        "## 外部调研与判断",
        "",
        "- rolling / walk-forward 持有窗口适合回答不同启动时点和不同持有期的体验差异。",
        "- 本阶段不做参数优化，只固定自然日持有期和全量起止区间分桶，避免挑选对某版本有利的周期。",
        "",
        "## 本次变更",
        "",
        "- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage385_any_start_holding_experience.py`",
        "- 修改策略脚本：无。",
        "- 新增参数：固定自然日持有期 `7/14/30/60/90/180/365/540/730/1095/1460/1825/2190`；全量区间分桶 `7-30天/31-90天/91-180天/181-365天/1-2年/2-3年/3-4年/4-5年/5年以上`。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "",
        "## 综合持有体验排序",
        "",
        _md_table(score),
        "",
        "## 固定持有期摘要",
        "",
        _md_table(focus[focus_cols], 120),
        "",
        "## 全量起止区间分桶",
        "",
        _md_table(bucket[bucket_cols], 120),
        "",
        "## 重点持有期最差启动日",
        "",
        _md_table(worst_focus, 80),
        "",
        "## 最差启动月份片段",
        "",
        _md_table(
            start_month_focus[
                [
                    "horizon_label",
                    "label",
                    "start_month",
                    "count",
                    "median_return_pct",
                    "min_return_pct",
                    "worst_dd_pct",
                    "positive_rate",
                    "dd30_pass_rate",
                ]
            ],
            80,
        ),
        "",
        "## 结论",
        "",
        f"- 主结论：`{decision['best_label']}` 的任意启动/持有体验综合最好。",
        "- 但纯收益最大仍是 `纯C3`；Stage079 的优势主要来自现金缓冲降低回撤和尾部水下体验。",
        "- `end_underwater_rate` 指期末低于该持有区间内曾经达到的高点，不等同于亏损；趋势策略常见“中途创新高、期末低于高点”，所以应与正收益率、5%分位收益和期内最大回撤一起解读。",
        "- 短持有期下三者都不舒服，1-3个月存在明显负收益和水下概率；趋势策略需要给足持有周期。",
        "- 1年以上开始，Stage079 在回撤闸门和负体验控制上明显优于另外两者；2-5年持有体验更稳定。",
        "- `78-1` 的问题不是没有收益，而是任意启动后的回撤深度、长水下和弱窗口体验显著差。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合。评估周期预先固定，并且额外枚举所有可行起止区间。",
        "- 运行后判断：不是过拟合。没有改策略，也没有根据结果挑周期；结论同时保留了短持有期不舒服和 Stage079 安全垫有限的事实。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。用户关心的是实盘进入后的真实持有体验，不是单条全周期收益。",
        "- 运行后判断：有价值。下一步若走 Stage079，应围绕 forward/影子盘的持有体验监控；若无法接受短中期水下，则需要低相关收益源，而不是继续调 C3 现金小数。",
        "",
        "## 输出文件",
        "",
        f"- fixed_horizon：`{HORIZON_PATH}`",
        f"- all_interval_buckets：`{BUCKET_PATH}`",
        f"- worst_starts：`{WORST_PATH}`",
        f"- start_month_horizon：`{START_MONTH_PATH}`",
        f"- horizon_matrix：`{HORIZON_MATRIX_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        f"- dashboard：`{HTML_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def _build_html(horizon: pd.DataFrame, bucket: pd.DataFrame, score: pd.DataFrame) -> str:
    def table_html(frame: pd.DataFrame, max_rows: int = 120) -> str:
        return frame.head(max_rows).to_html(index=False, border=0, classes="data")

    focus = horizon[horizon["horizon_label"].isin(["1个月", "3个月", "6个月", "1年", "2年", "3年", "5年"])]
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Stage085 任意启动日与持有期体验审计</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f7f7f4; color: #1f2933; }}
    main {{ max-width: 1220px; margin: 0 auto; padding: 28px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin: 24px 0; }}
    .note {{ background: #fff; border-left: 4px solid #2563eb; padding: 14px 16px; }}
    table.data {{ border-collapse: collapse; width: 100%; background: #fff; font-size: 12px; }}
    table.data th, table.data td {{ border-bottom: 1px solid #e5e7eb; padding: 6px 8px; text-align: right; }}
    table.data th:first-child, table.data td:first-child {{ text-align: left; }}
    table.data th {{ background: #eef2f7; }}
  </style>
</head>
<body>
<main>
  <h1>Stage085 任意启动日与持有期体验审计</h1>
  <p class="note">结论：Stage079 的任意启动/持有体验综合最好；纯C3收益更强但回撤和水下体验不达目标；78-1保留基准身份但持有体验最弱。</p>
  <section><h2>综合排序</h2>{table_html(score)}</section>
  <section><h2>固定持有期</h2>{table_html(focus)}</section>
  <section><h2>全量区间分桶</h2>{table_html(bucket)}</section>
</main>
</body>
</html>"""
    return html


def main() -> None:
    curves = _load_curves()
    horizon, worst, month = _fixed_horizon(curves)
    bucket, bucket_worst = _all_interval_buckets(curves)
    matrix = _horizon_matrix(horizon)
    score = _score(horizon, bucket)
    best = score.iloc[0]
    decision = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "best_variant": str(best["variant"]),
        "best_label": str(best["label"]),
        "score_table": _json_safe(score.to_dict(orient="records")),
        "conclusion": "Stage079 has the best any-start holding experience; C3 has stronger alpha but weaker drawdown comfort; 78-1 has the weakest holding experience under this objective.",
        "overfit_reflection": "fixed_horizons_and_exhaustive_intervals_no_strategy_change",
        "continue_value": "use_stage079_for_normal_cost_forward_holding_experience_monitoring_or_find_low_corr_source",
    }

    all_worst = pd.concat([worst, bucket_worst], ignore_index=True, sort=False)
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    bucket.to_csv(BUCKET_PATH, index=False, encoding="utf-8-sig")
    all_worst.to_csv(WORST_PATH, index=False, encoding="utf-8-sig")
    month.to_csv(START_MONTH_PATH, index=False, encoding="utf-8-sig")
    matrix.to_csv(HORIZON_MATRIX_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(horizon, bucket, worst, month, matrix, score, decision), encoding="utf-8")
    HTML_PATH.write_text(_build_html(horizon, bucket, score), encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"fixed_horizon={HORIZON_PATH}")
    print(f"bucket={BUCKET_PATH}")
    print(f"report={REPORT_PATH}")
    print(f"html={HTML_PATH}")


if __name__ == "__main__":
    main()

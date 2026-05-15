from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage261_stage78_1_time_to_positive_v1"
OUTPUT_PREFIX = "qmt_roll_stage261_stage78_1_time_to_positive"
TRADING_DAYS_PER_YEAR = 240

LATEST_AI_ELIGIBILITY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_"
    "stage182_ai_product_pool_live_inference_v1.csv"
)

SUMMARY_CSV_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DAILY_CSV_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
JSON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _quarter_starts(start: datetime, end: datetime) -> list[datetime]:
    starts = pd.date_range(start, end, freq="QS")
    if starts.empty or starts[0].to_pydatetime().date() != start.date():
        starts = pd.DatetimeIndex([pd.Timestamp(start), *starts])
    return [ts.to_pydatetime() for ts in starts if ts.to_pydatetime() <= end]


def _annual_starts(start: datetime, end: datetime) -> list[datetime]:
    return [datetime(year, 1, 1) for year in range(start.year, end.year + 1) if datetime(year, 1, 1) <= end]


def _underwater_runs(is_underwater: pd.Series, dates: pd.Series) -> tuple[int, int, str, str]:
    max_len = 0
    current_len = 0
    current_start = ""
    max_start = ""
    max_end = ""
    for flag, date_value in zip(is_underwater.tolist(), dates.dt.date.astype(str).tolist(), strict=False):
        if bool(flag):
            if current_len == 0:
                current_start = date_value
            current_len += 1
            if current_len > max_len:
                max_len = current_len
                max_start = current_start
                max_end = date_value
        else:
            current_len = 0
            current_start = ""
    tail_len = 0
    if not is_underwater.empty and bool(is_underwater.iloc[-1]):
        tail_len = current_len
    return max_len, tail_len, max_start, max_end


def _path_metrics(
    analysis_df: pd.DataFrame,
    *,
    window_name: str,
    window_group: str,
    analysis_start: datetime,
    analysis_end: datetime,
    capital: float,
) -> tuple[dict[str, Any], pd.DataFrame]:
    if analysis_df is None or analysis_df.empty:
        empty_row = {
            "window_name": window_name,
            "window_group": window_group,
            "analysis_start": analysis_start.date().isoformat(),
            "analysis_end": analysis_end.date().isoformat(),
            "day_count": 0,
            "turned_positive": 0,
            "first_positive_date": "",
            "trading_days_to_first_positive": np.nan,
            "calendar_days_to_first_positive": np.nan,
            "first_trade_date": "",
            "trading_days_from_first_trade_to_positive": np.nan,
            "end_balance": capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "max_underwater_trading_days": 0,
            "current_underwater_trading_days": 0,
            "underwater_start_date": "",
            "underwater_end_date": "",
            "min_return_before_positive_pct": 0.0,
            "sharpe_ratio": 0.0,
            "total_trade_count": 0,
            "total_slippage": 0.0,
        }
        return empty_row, pd.DataFrame()

    frame = analysis_df.copy()
    frame = frame.reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame.dropna(subset=["date"], inplace=True)
    frame.sort_values("date", inplace=True)
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce").ffill().fillna(capital)
    frame["net_pnl"] = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    frame["trade_count"] = pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    frame["slippage"] = pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0)
    frame["normalized_nav"] = frame["balance"] / capital
    frame["return_pct"] = (frame["normalized_nav"] - 1.0) * 100.0
    high_with_initial = pd.concat([pd.Series([capital]), frame["balance"]], ignore_index=True).cummax().iloc[1:]
    frame["high_water"] = high_with_initial.to_numpy(dtype=float)
    frame["drawdown_pct"] = (frame["balance"] / frame["high_water"].replace(0.0, np.nan) - 1.0).fillna(0.0) * 100.0
    frame["window_name"] = window_name
    frame["window_group"] = window_group

    positive_mask = frame["balance"] > capital
    first_positive_date = ""
    trading_days_to_first_positive: float = np.nan
    calendar_days_to_first_positive: float = np.nan
    trading_days_from_first_trade_to_positive: float = np.nan
    turned_positive = int(bool(positive_mask.any()))
    first_positive_idx: int | None = None
    if turned_positive:
        first_positive_idx = int(np.flatnonzero(positive_mask.to_numpy())[0])
        first_positive_ts = pd.Timestamp(frame.iloc[first_positive_idx]["date"])
        first_positive_date = first_positive_ts.date().isoformat()
        trading_days_to_first_positive = float(first_positive_idx + 1)
        calendar_days_to_first_positive = float((first_positive_ts.to_pydatetime().date() - analysis_start.date()).days)

    trade_mask = frame["trade_count"] > 0
    first_trade_date = ""
    if trade_mask.any():
        first_trade_idx = int(np.flatnonzero(trade_mask.to_numpy())[0])
        first_trade_date = pd.Timestamp(frame.iloc[first_trade_idx]["date"]).date().isoformat()
        if first_positive_idx is not None and first_positive_idx >= first_trade_idx:
            trading_days_from_first_trade_to_positive = float(first_positive_idx - first_trade_idx + 1)

    min_slice = frame.iloc[: first_positive_idx + 1] if first_positive_idx is not None else frame
    min_return_before_positive_pct = float(min_slice["return_pct"].min()) if not min_slice.empty else 0.0

    is_underwater = frame["balance"] < frame["high_water"]
    max_underwater, current_underwater, underwater_start, underwater_end = _underwater_runs(is_underwater, frame["date"])

    previous_balance = frame["balance"].shift(1).fillna(capital).replace(0.0, np.nan)
    daily_return = (frame["net_pnl"] / previous_balance).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    daily_std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / daily_std * math.sqrt(TRADING_DAYS_PER_YEAR)) if daily_std > 1e-12 else 0.0

    row = {
        "window_name": window_name,
        "window_group": window_group,
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "day_count": int(len(frame)),
        "turned_positive": turned_positive,
        "first_positive_date": first_positive_date,
        "trading_days_to_first_positive": trading_days_to_first_positive,
        "calendar_days_to_first_positive": calendar_days_to_first_positive,
        "first_trade_date": first_trade_date,
        "trading_days_from_first_trade_to_positive": trading_days_from_first_trade_to_positive,
        "end_balance": float(frame["balance"].iloc[-1]),
        "total_return_pct": float(frame["return_pct"].iloc[-1]),
        "max_dd_percent": float(frame["drawdown_pct"].min()),
        "max_underwater_trading_days": int(max_underwater),
        "current_underwater_trading_days": int(current_underwater),
        "underwater_start_date": underwater_start,
        "underwater_end_date": underwater_end,
        "min_return_before_positive_pct": min_return_before_positive_pct,
        "sharpe_ratio": sharpe,
        "total_trade_count": int(frame["trade_count"].sum()),
        "total_slippage": float(frame["slippage"].sum()),
    }
    keep = [
        "date",
        "window_name",
        "window_group",
        "balance",
        "normalized_nav",
        "return_pct",
        "drawdown_pct",
        "net_pnl",
        "trade_count",
        "slippage",
    ]
    return row, frame[keep].copy()


def _run_window(
    *,
    window_name: str,
    window_group: str,
    analysis_start: datetime,
    analysis_end: datetime,
    capital: float,
    ai_eligibility_path: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    overrides = build_official_stage78_overrides()
    overrides["trade_start_date"] = analysis_start.date().isoformat()
    overrides["ai_product_pool_eligibility_path"] = str(ai_eligibility_path)
    preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    print(f"[stage261] {window_name}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)
    _, analysis_df, _ = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=overrides,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        preload_start=preload_start,
        capital=capital,
        save_artifacts=False,
        include_start_year_sweep=False,
    )
    return _path_metrics(
        analysis_df,
        window_name=window_name,
        window_group=window_group,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        capital=capital,
    )


def _to_markdown_table(df: pd.DataFrame, columns: list[str], *, max_rows: int = 50) -> str:
    if df.empty:
        return "_empty_\n"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: "" if pd.isna(value) else f"{value:,.4f}")
    return view.to_markdown(index=False) + "\n"


def _write_report(summary_df: pd.DataFrame, payload: dict[str, Any]) -> None:
    turned = summary_df[summary_df["turned_positive"].astype(int).eq(1)].copy()
    not_turned = summary_df[summary_df["turned_positive"].astype(int).eq(0)].copy()
    completed_for_wait = turned[turned["window_group"].isin(["quarter_start", "annual_start"])].copy()
    longest_wait = completed_for_wait.sort_values("trading_days_to_first_positive", ascending=False).head(10)
    worst_underwater = summary_df.sort_values("max_underwater_trading_days", ascending=False).head(10)
    current_2026 = summary_df[summary_df["window_name"].eq("q2026_1")]

    lines = [
        "# Stage261 Stage78-1 多周期转正等待期评测",
        "",
        "## 定位",
        "",
        "- 本阶段不改策略、不加参数、不做择优；只评估 78-1 在不同冷启动点的持有体验。",
        "- `转正`定义：冷启动后日终权益首次严格高于初始本金。",
        "- `水下期`定义：日终权益低于此前最高权益的连续交易日数，初始本金也算初始高水位。",
        "",
        "## 样本",
        "",
        f"- 策略版本：`{payload['official_version']}`",
        f"- 初始资金：`{payload['capital']:,.0f}`",
        f"- 分析截止：`{payload['analysis_end']}`",
        f"- AI池文件：`{payload['ai_eligibility_path']}`",
        f"- 窗口数：`{len(summary_df)}`",
        "",
        "## 核心结论",
        "",
        f"- 已转正窗口数：`{int(summary_df['turned_positive'].sum())}` / `{len(summary_df)}`",
        f"- 未转正窗口数：`{len(not_turned)}`",
        f"- 已转正窗口最长等待：`{payload['aggregate']['max_trading_days_to_first_positive']}` 个交易日 / `{payload['aggregate']['max_calendar_days_to_first_positive']}` 个自然日",
        f"- 已转正窗口等待中位数：`{payload['aggregate']['median_trading_days_to_first_positive']}` 个交易日",
        f"- 全窗口最长水下期：`{payload['aggregate']['max_underwater_trading_days']}` 个交易日",
        "",
        "## 2026当前段",
        "",
        _to_markdown_table(
            current_2026,
            [
                "window_name",
                "analysis_start",
                "analysis_end",
                "day_count",
                "turned_positive",
                "first_positive_date",
                "trading_days_to_first_positive",
                "end_balance",
                "total_return_pct",
                "max_dd_percent",
                "current_underwater_trading_days",
                "max_underwater_trading_days",
            ],
            max_rows=5,
        ),
        "",
        "## 等待转正最长的已转正窗口",
        "",
        _to_markdown_table(
            longest_wait,
            [
                "window_name",
                "window_group",
                "analysis_start",
                "first_positive_date",
                "trading_days_to_first_positive",
                "calendar_days_to_first_positive",
                "min_return_before_positive_pct",
                "end_balance",
                "total_return_pct",
                "max_dd_percent",
            ],
            max_rows=10,
        ),
        "",
        "## 水下期最长窗口",
        "",
        _to_markdown_table(
            worst_underwater,
            [
                "window_name",
                "window_group",
                "analysis_start",
                "analysis_end",
                "max_underwater_trading_days",
                "current_underwater_trading_days",
                "underwater_start_date",
                "underwater_end_date",
                "max_dd_percent",
                "total_return_pct",
            ],
            max_rows=10,
        ),
        "",
        "## 未转正窗口",
        "",
        _to_markdown_table(
            not_turned.sort_values(["analysis_start", "window_name"]),
            [
                "window_name",
                "window_group",
                "analysis_start",
                "analysis_end",
                "day_count",
                "end_balance",
                "total_return_pct",
                "max_dd_percent",
                "current_underwater_trading_days",
            ],
            max_rows=20,
        ),
        "",
        "## 输出文件",
        "",
        f"- summary：`{SUMMARY_CSV_PATH}`",
        f"- daily：`{DAILY_CSV_PATH}`",
        f"- json：`{JSON_PATH}`",
        "",
        "## 反思",
        "",
        "- 运行前过拟合判断：否。本阶段只测固定版本的路径特征，不根据结果修改参数。",
        "- 运行后过拟合判断：否。输出的是不利体验指标，没有挑选更优品种或阈值。",
        "- 运行前继续价值判断：是。当前 2026 回撤体验必须和历史冷启动等待期比较。",
        "- 运行后继续价值判断：是。该评测可以作为影子盘 `review` 是否仍在预期内的量化参照。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Stage78-1 time to first positive return across cold starts.")
    parser.add_argument("--analysis-end", default="2026-05-12")
    parser.add_argument("--capital", type=float, default=OFFICIAL_STAGE78_CAPITAL)
    parser.add_argument("--ai-eligibility-path", default=str(LATEST_AI_ELIGIBILITY_PATH))
    parser.add_argument("--annual", action="store_true", help="Also run annual starts; quarter starts already include Q1.")
    args = parser.parse_args()

    analysis_end = datetime.strptime(str(args.analysis_end), "%Y-%m-%d")
    capital = float(args.capital)
    ai_eligibility_path = Path(str(args.ai_eligibility_path)).expanduser().resolve()
    if not ai_eligibility_path.exists():
        raise FileNotFoundError(ai_eligibility_path)

    window_specs: list[tuple[str, str, datetime]] = []
    for start in _quarter_starts(START_DT, analysis_end):
        quarter = ((start.month - 1) // 3) + 1
        window_specs.append((f"q{start.year}_{quarter}", "quarter_start", start))
    if bool(args.annual):
        for start in _annual_starts(START_DT, analysis_end):
            window_specs.append((f"y{start.year}", "annual_start", start))

    rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    for window_name, window_group, analysis_start in window_specs:
        row, daily = _run_window(
            window_name=window_name,
            window_group=window_group,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            capital=capital,
            ai_eligibility_path=ai_eligibility_path,
        )
        rows.append(row)
        if not daily.empty:
            daily_frames.append(daily)

    summary_df = pd.DataFrame(rows)
    summary_df.sort_values(["window_group", "analysis_start", "window_name"], inplace=True)
    daily_df = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    if not daily_df.empty:
        daily_df.sort_values(["window_group", "window_name", "date"], inplace=True)

    turned = summary_df[summary_df["turned_positive"].astype(int).eq(1)].copy()
    aggregate = {
        "window_count": int(len(summary_df)),
        "turned_positive_count": int(summary_df["turned_positive"].sum()),
        "not_turned_positive_count": int((summary_df["turned_positive"].astype(int) == 0).sum()),
        "max_trading_days_to_first_positive": int(turned["trading_days_to_first_positive"].max()) if not turned.empty else None,
        "max_calendar_days_to_first_positive": int(turned["calendar_days_to_first_positive"].max()) if not turned.empty else None,
        "median_trading_days_to_first_positive": _safe_float(turned["trading_days_to_first_positive"].median()) if not turned.empty else None,
        "p75_trading_days_to_first_positive": _safe_float(turned["trading_days_to_first_positive"].quantile(0.75)) if not turned.empty else None,
        "p90_trading_days_to_first_positive": _safe_float(turned["trading_days_to_first_positive"].quantile(0.90)) if not turned.empty else None,
        "max_underwater_trading_days": int(summary_df["max_underwater_trading_days"].max()) if not summary_df.empty else None,
        "worst_max_dd_percent": _safe_float(summary_df["max_dd_percent"].min()) if not summary_df.empty else None,
    }
    payload = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "manifest": build_official_stage78_manifest(),
        "capital": capital,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "ai_eligibility_path": str(ai_eligibility_path),
        "base_risk_ratio": BASE_RISK_RATIO,
        "aggregate": aggregate,
        "outputs": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "daily_csv": str(DAILY_CSV_PATH),
            "summary_json": str(JSON_PATH),
            "report": str(REPORT_PATH),
        },
        "judgement": {
            "overfit_before": "否。只统计固定Stage78-1路径指标。",
            "overfit_after": "否。没有新增或调优策略参数。",
            "continue_before": "是。当前2026回撤需要历史等待期参照。",
            "continue_after": "是。可作为影子盘review预期边界。",
        },
    }

    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    daily_df.to_csv(DAILY_CSV_PATH, index=False, encoding="utf-8-sig")
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(summary_df, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

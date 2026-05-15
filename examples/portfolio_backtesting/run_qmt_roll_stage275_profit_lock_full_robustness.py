from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
MODEL_TAG: str = "stage275_profit_lock_full_robustness_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage275_profit_lock_full_robustness"
TRADING_DAYS_PER_YEAR: float = 240.0
HORIZONS: tuple[int, ...] = (63, 126, 252)
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0, 10.0)


@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    overrides: dict[str, Any]


def _variants() -> list[Variant]:
    official = build_official_stage78_overrides()
    two_segment = dict(official)
    two_segment["profit_lock_tiers"] = "0.30:0.270,0.20:0.180,0.10:0.090,0.05:0.015,0.03:0.009,0.02:0.006"
    return [
        Variant("A_stage78_1_current", "Current Stage78-1 profit lock tiers.", official),
        Variant(
            "D_two_segment_30_90",
            "Stage274 engine-gate survivor: retain 30% on low tiers and 90% on high tiers.",
            two_segment,
        ),
    ]


def _start_years() -> list[datetime]:
    return [
        START_DT,
        datetime(2021, 1, 1),
        datetime(2022, 1, 1),
        datetime(2023, 1, 1),
        datetime(2024, 1, 1),
        datetime(2025, 1, 1),
        datetime(2026, 1, 1),
    ]


def _quarter_starts() -> list[datetime]:
    starts = pd.date_range(START_DT, END_DT, freq="QS")
    if starts.empty or starts[0].to_pydatetime() != START_DT:
        starts = pd.DatetimeIndex([pd.Timestamp(START_DT), *starts])
    return [ts.to_pydatetime() for ts in starts if START_DT <= ts.to_pydatetime() <= END_DT]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _run_variant(variant: Variant, analysis_start: datetime) -> tuple[pd.DataFrame, dict[str, Any]]:
    print(f"[stage275] {variant.name} {analysis_start.date()} -> {END_DT.date()}", flush=True)
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            _, daily, stats = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=variant.overrides,
                analysis_start=analysis_start,
                analysis_end=END_DT,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{OUTPUT_PREFIX}_{variant.name}_{analysis_start.date().isoformat()}",
                chart_title=f"{variant.name} {analysis_start.date().isoformat()}",
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise
    daily_df = daily.copy() if daily is not None else pd.DataFrame()
    if not daily_df.empty:
        daily_df.sort_index(inplace=True)
    return daily_df, stats


def _path_metrics_from_daily(daily: pd.DataFrame, *, capital: float, horizon_days: int | None = None) -> dict[str, float]:
    if daily.empty:
        return {
            "end_balance": capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "day_count": 0.0,
            "complete_horizon": False,
        }

    view = daily.iloc[:horizon_days].copy() if horizon_days is not None else daily.copy()
    complete_horizon = bool(horizon_days is None or len(view) >= horizon_days)
    if view.empty:
        return {
            "end_balance": capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "day_count": 0.0,
            "complete_horizon": complete_horizon,
        }

    balance = pd.to_numeric(view["balance"], errors="coerce").ffill().fillna(capital)
    net_pnl = pd.to_numeric(view.get("net_pnl", pd.Series(0.0, index=view.index)), errors="coerce").fillna(0.0)
    previous_balance = balance.shift(1).fillna(capital).replace(0.0, np.nan)
    daily_return = (net_pnl / previous_balance).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    high_water = pd.concat([pd.Series([capital]), balance.reset_index(drop=True)]).cummax().iloc[1:].reset_index(drop=True)
    dd_pct = (balance.reset_index(drop=True) / high_water.replace(0.0, np.nan) - 1.0).fillna(0.0) * 100.0
    std = float(daily_return.std(ddof=1)) if len(daily_return) > 1 else 0.0
    sharpe = float(daily_return.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 1e-12 else 0.0
    end_balance = float(balance.iloc[-1])
    return {
        "end_balance": end_balance,
        "total_return_pct": (end_balance - capital) / capital * 100.0,
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
        "total_slippage": float(pd.to_numeric(view.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(view.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "day_count": float(len(view)),
        "complete_horizon": complete_horizon,
    }


def _stats_row(variant: Variant, analysis_start: datetime, daily: pd.DataFrame, stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant": variant.name,
        "variant_description": variant.description,
        "window_name": f"since_{analysis_start.year}" if analysis_start.month == 1 else analysis_start.date().isoformat(),
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "end_balance": _safe_float(stats.get("end_balance")),
        "total_return_pct": _safe_float(stats.get("total_return")),
        "max_dd_percent": _safe_float(stats.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(stats.get("sharpe_ratio")),
        "total_slippage": _safe_float(stats.get("total_slippage")),
        "total_trade_count": float(stats.get("total_trade_count", 0) or 0),
        "win_ratio_pct": _safe_float(stats.get("win_ratio")),
        "daily_day_count": float(len(daily)),
    }


def _compare_pairs(df: pd.DataFrame, keys: list[str], value_prefix: str = "d") -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in df.groupby(keys, dropna=False):
        by_variant = {str(row["variant"]): row for row in group.to_dict("records")}
        base = by_variant.get("A_stage78_1_current")
        candidate = by_variant.get("D_two_segment_30_90")
        if not base or not candidate:
            continue
        row = {key: candidate[key] for key in keys}
        row.update(
            {
                f"{value_prefix}_end_minus_a": _safe_float(candidate.get("end_balance")) - _safe_float(base.get("end_balance")),
                f"{value_prefix}_return_minus_a_pct": _safe_float(candidate.get("total_return_pct")) - _safe_float(base.get("total_return_pct")),
                f"{value_prefix}_dd_minus_a_pct": _safe_float(candidate.get("max_dd_percent")) - _safe_float(base.get("max_dd_percent")),
                f"{value_prefix}_sharpe_minus_a": _safe_float(candidate.get("sharpe_ratio")) - _safe_float(base.get("sharpe_ratio")),
                f"{value_prefix}_trade_count_minus_a": _safe_float(candidate.get("total_trade_count")) - _safe_float(base.get("total_trade_count")),
                "a_end_balance": _safe_float(base.get("end_balance")),
                "d_end_balance": _safe_float(candidate.get("end_balance")),
                "a_max_dd_percent": _safe_float(base.get("max_dd_percent")),
                "d_max_dd_percent": _safe_float(candidate.get("max_dd_percent")),
                "a_sharpe": _safe_float(base.get("sharpe_ratio")),
                "d_sharpe": _safe_float(candidate.get("sharpe_ratio")),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _build_horizon_rows(
    runs: dict[tuple[str, str], tuple[pd.DataFrame, dict[str, Any]]],
    variants: list[Variant],
    quarter_starts: list[datetime],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant in variants:
        for start in quarter_starts:
            daily, _ = runs[(variant.name, start.date().isoformat())]
            for horizon in HORIZONS:
                metrics = _path_metrics_from_daily(daily, capital=OFFICIAL_STAGE78_CAPITAL, horizon_days=horizon)
                rows.append(
                    {
                        "variant": variant.name,
                        "analysis_start": start.date().isoformat(),
                        "window_name": f"q{start.year}_{((start.month - 1) // 3) + 1}",
                        "horizon": horizon,
                        **metrics,
                    }
                )
            metrics = _path_metrics_from_daily(daily, capital=OFFICIAL_STAGE78_CAPITAL, horizon_days=None)
            rows.append(
                {
                    "variant": variant.name,
                    "analysis_start": start.date().isoformat(),
                    "window_name": f"q{start.year}_{((start.month - 1) // 3) + 1}",
                    "horizon": "to_end",
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def _aggregate_horizons(horizon_df: pd.DataFrame) -> pd.DataFrame:
    complete = horizon_df[horizon_df["complete_horizon"].astype(bool)].copy()
    if complete.empty:
        return pd.DataFrame()
    aggregate = (
        complete.groupby(["variant", "horizon"], as_index=False)
        .agg(
            window_count=("window_name", "count"),
            positive_return_count=("total_return_pct", lambda s: int((s > 0).sum())),
            median_return_pct=("total_return_pct", "median"),
            worst_return_pct=("total_return_pct", "min"),
            best_return_pct=("total_return_pct", "max"),
            median_max_dd_percent=("max_dd_percent", "median"),
            worst_max_dd_percent=("max_dd_percent", "min"),
            median_sharpe=("sharpe_ratio", "median"),
            worst_sharpe=("sharpe_ratio", "min"),
            median_trade_count=("total_trade_count", "median"),
            median_slippage=("total_slippage", "median"),
        )
        .sort_values(["horizon", "variant"])
        .reset_index(drop=True)
    )
    aggregate["positive_return_rate_pct"] = (
        aggregate["positive_return_count"] / aggregate["window_count"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    return aggregate


def _path_metrics_from_pnl(net_pnl: np.ndarray, initial_capital: float) -> dict[str, float]:
    if net_pnl.size == 0:
        return {
            "end_balance": initial_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    equity = initial_capital + np.cumsum(net_pnl)
    previous = np.concatenate([[initial_capital], equity[:-1]])
    returns = np.divide(net_pnl, previous, out=np.zeros_like(net_pnl, dtype=float), where=previous != 0)
    high = np.maximum.accumulate(np.insert(equity, 0, initial_capital))[1:]
    dd_pct = np.divide(equity - high, high, out=np.zeros_like(equity, dtype=float), where=high != 0) * 100.0
    std = float(np.std(returns, ddof=1)) if returns.size > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 1e-12 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / initial_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _build_slippage_stress(
    runs: dict[tuple[str, str], tuple[pd.DataFrame, dict[str, Any]]],
    variants: list[Variant],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    full_key = START_DT.date().isoformat()
    for variant in variants:
        daily, _ = runs[(variant.name, full_key)]
        if daily.empty:
            continue
        net_pnl = pd.to_numeric(daily.get("net_pnl", 0.0), errors="coerce").fillna(0.0).to_numpy(dtype=float)
        slippage = pd.to_numeric(daily.get("slippage", 0.0), errors="coerce").fillna(0.0).to_numpy(dtype=float)
        for multiplier in SLIPPAGE_MULTIPLIERS:
            stressed_net_pnl = net_pnl - (multiplier - 1.0) * slippage
            rows.append(
                {
                    "variant": variant.name,
                    "slippage_multiplier": multiplier,
                    **_path_metrics_from_pnl(stressed_net_pnl, OFFICIAL_STAGE78_CAPITAL),
                    "total_slippage": float(slippage.sum() * multiplier),
                    "total_net_pnl": float(stressed_net_pnl.sum()),
                }
            )
    return pd.DataFrame(rows)


def _decision(
    *,
    start_year_comparison: pd.DataFrame,
    horizon_comparison: pd.DataFrame,
    horizon_aggregate: pd.DataFrame,
    slippage_comparison: pd.DataFrame,
) -> dict[str, Any]:
    full = start_year_comparison[start_year_comparison["analysis_start"].eq(START_DT.date().isoformat())].iloc[0]
    latest = start_year_comparison[start_year_comparison["analysis_start"].eq("2026-01-01")].iloc[0]

    start_year_win_count = int((start_year_comparison["d_end_minus_a"] > 0).sum())
    start_year_dd_ok_count = int((start_year_comparison["d_dd_minus_a_pct"] >= -2.0).sum())
    completed_horizon = horizon_comparison[horizon_comparison["horizon"].isin(list(HORIZONS))].copy()
    horizon_win_rate_pct = float((completed_horizon["d_end_minus_a"] > 0).mean() * 100.0) if not completed_horizon.empty else 0.0
    horizon_dd_ok_rate_pct = float((completed_horizon["d_dd_minus_a_pct"] >= -2.0).mean() * 100.0) if not completed_horizon.empty else 0.0

    aggregate_pass_count = 0
    aggregate_checks: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        pair = horizon_aggregate[horizon_aggregate["horizon"].astype(str).eq(str(horizon))]
        by_variant = {str(row["variant"]): row for row in pair.to_dict("records")}
        base = by_variant.get("A_stage78_1_current")
        candidate = by_variant.get("D_two_segment_30_90")
        if not base or not candidate:
            continue
        positive_rate_diff = _safe_float(candidate["positive_return_rate_pct"]) - _safe_float(base["positive_return_rate_pct"])
        median_return_diff = _safe_float(candidate["median_return_pct"]) - _safe_float(base["median_return_pct"])
        worst_return_diff = _safe_float(candidate["worst_return_pct"]) - _safe_float(base["worst_return_pct"])
        pass_horizon = bool(positive_rate_diff >= -5.0 and median_return_diff >= -1.0 and worst_return_diff >= -10.0)
        aggregate_pass_count += int(pass_horizon)
        aggregate_checks.append(
            {
                "horizon": horizon,
                "positive_rate_diff": positive_rate_diff,
                "median_return_diff": median_return_diff,
                "worst_return_diff": worst_return_diff,
                "pass_horizon": pass_horizon,
            }
        )

    slip_5x = slippage_comparison[slippage_comparison["slippage_multiplier"].eq(5.0)].iloc[0]
    slip_10x = slippage_comparison[slippage_comparison["slippage_multiplier"].eq(10.0)].iloc[0]

    pass_full = bool(float(full["d_end_minus_a"]) > 0.0 and float(full["d_dd_minus_a_pct"]) >= -2.0)
    pass_start_year = bool(start_year_win_count >= 5 and start_year_dd_ok_count >= 6)
    pass_latest = bool(float(latest["d_end_minus_a"]) >= -50_000.0 and float(latest["d_dd_minus_a_pct"]) >= -5.0)
    pass_horizon = bool(horizon_win_rate_pct >= 50.0 and horizon_dd_ok_rate_pct >= 80.0 and aggregate_pass_count >= 2)
    pass_slippage = bool(float(slip_5x["d_end_minus_a"]) > 0.0 and float(slip_5x["d_dd_minus_a_pct"]) >= -2.0)
    pass_watch = bool(float(slip_10x["d_end_minus_a"]) > 0.0)

    pass_stage275 = bool(pass_full and pass_start_year and pass_latest and pass_horizon and pass_slippage)
    return {
        "baseline_version": OFFICIAL_STAGE78_VERSION,
        "candidate": "D_two_segment_30_90",
        "candidate_tiers": "0.30:0.270,0.20:0.180,0.10:0.090,0.05:0.015,0.03:0.009,0.02:0.006",
        "official_manifest_capital": build_official_stage78_manifest().get("capital"),
        "pass_stage275": pass_stage275,
        "promotion_decision": "research_candidate_not_formal_until_stage276_trade_drilldown" if pass_stage275 else "hold_no_promotion",
        "pass_full": pass_full,
        "pass_start_year": pass_start_year,
        "pass_latest_2026": pass_latest,
        "pass_horizon": pass_horizon,
        "pass_slippage_5x": pass_slippage,
        "pass_slippage_10x_watch": pass_watch,
        "start_year_win_count": start_year_win_count,
        "start_year_dd_ok_count": start_year_dd_ok_count,
        "horizon_pair_win_rate_pct": horizon_win_rate_pct,
        "horizon_pair_dd_ok_rate_pct": horizon_dd_ok_rate_pct,
        "horizon_aggregate_pass_count": aggregate_pass_count,
        "horizon_aggregate_checks": aggregate_checks,
        "full_end_minus_a": float(full["d_end_minus_a"]),
        "full_dd_minus_a_pct": float(full["d_dd_minus_a_pct"]),
        "latest_2026_end_minus_a": float(latest["d_end_minus_a"]),
        "slippage_5x_end_minus_a": float(slip_5x["d_end_minus_a"]),
        "slippage_10x_end_minus_a": float(slip_10x["d_end_minus_a"]),
        "next_step": (
            "stage276_trade_drilldown_and_parameter_freeze_review"
            if pass_stage275
            else "stop_or_return_to_mechanism_level_design"
        ),
    }


def _format_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "- 无数据"
    view = df[[column for column in columns if column in df.columns]].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def _write_report(
    *,
    start_year_summary: pd.DataFrame,
    start_year_comparison: pd.DataFrame,
    horizon_aggregate: pd.DataFrame,
    horizon_comparison: pd.DataFrame,
    slippage_stress: pd.DataFrame,
    slippage_comparison: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    report = f"""# Stage275 盈利锁定 D 候选全稳健性验证

## 设计

- A：Stage78-1 当前正式盈利锁定档位。
- D：`30%->27% / 20%->18% / 10%->9% / 5%->1.5% / 3%->0.9% / 2%->0.6%`。
- 本阶段只验证 Stage274 通过 engine gate 的 D 候选，不继续搜索新参数。
- 检查维度：起始年份、季度冷启动、63/126/252交易日短窗口、1x/2x/3x/5x/10x 滑点压力。

## 判定

```json
{json.dumps(decision, ensure_ascii=False, indent=2)}
```

## 起始年份 A/D 原始结果

{_format_table(start_year_summary, ["variant", "window_name", "analysis_start", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage", "total_trade_count", "win_ratio_pct"])}

## 起始年份 D 相对 A

{_format_table(start_year_comparison, ["analysis_start", "d_end_minus_a", "d_return_minus_a_pct", "d_dd_minus_a_pct", "d_sharpe_minus_a", "d_trade_count_minus_a", "a_end_balance", "d_end_balance", "a_max_dd_percent", "d_max_dd_percent"])}

## 季度冷启动聚合

{_format_table(horizon_aggregate, ["variant", "horizon", "window_count", "positive_return_count", "positive_return_rate_pct", "median_return_pct", "worst_return_pct", "median_max_dd_percent", "worst_max_dd_percent", "median_sharpe", "worst_sharpe"])}

## 季度冷启动 D 相对 A 摘要

{_format_table(horizon_comparison, ["analysis_start", "horizon", "d_end_minus_a", "d_return_minus_a_pct", "d_dd_minus_a_pct", "d_sharpe_minus_a", "a_end_balance", "d_end_balance"], 60)}

## 滑点压力

{_format_table(slippage_stress, ["variant", "slippage_multiplier", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage"])}

## 滑点压力 D 相对 A

{_format_table(slippage_comparison, ["slippage_multiplier", "d_end_minus_a", "d_return_minus_a_pct", "d_dd_minus_a_pct", "d_sharpe_minus_a", "a_end_balance", "d_end_balance"])}

## 结论

- 通过 Stage275 也不直接替换正式 78-1，只能进入 Stage276 逐笔归因和冻结审查。
- 如果任一关键闸门失败，D 只能作为研究候选，不改正式实盘/影子盘口径。

## 输出文件

- start_year_summary：`{paths["start_year_summary"].name}`
- start_year_comparison：`{paths["start_year_comparison"].name}`
- horizon_summary：`{paths["horizon_summary"].name}`
- horizon_aggregate：`{paths["horizon_aggregate"].name}`
- horizon_comparison：`{paths["horizon_comparison"].name}`
- slippage_stress：`{paths["slippage_stress"].name}`
- slippage_comparison：`{paths["slippage_comparison"].name}`
- decision：`{paths["decision"].name}`
"""
    paths["report"].write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    variants = _variants()
    start_years = _start_years()
    quarters = _quarter_starts()
    unique_starts = sorted({start.date().isoformat(): start for start in [*start_years, *quarters]}.values())

    runs: dict[tuple[str, str], tuple[pd.DataFrame, dict[str, Any]]] = {}
    for variant in variants:
        for start in unique_starts:
            runs[(variant.name, start.date().isoformat())] = _run_variant(variant, start)

    start_year_rows: list[dict[str, Any]] = []
    for variant in variants:
        for start in start_years:
            daily, stats = runs[(variant.name, start.date().isoformat())]
            start_year_rows.append(_stats_row(variant, start, daily, stats))
    start_year_summary = pd.DataFrame(start_year_rows)
    start_year_comparison = _compare_pairs(start_year_summary, ["analysis_start"], value_prefix="d")

    horizon_summary = _build_horizon_rows(runs, variants, quarters)
    horizon_aggregate = _aggregate_horizons(horizon_summary)
    horizon_comparison = _compare_pairs(horizon_summary, ["analysis_start", "horizon"], value_prefix="d")

    slippage_stress = _build_slippage_stress(runs, variants)
    slippage_comparison = _compare_pairs(slippage_stress, ["slippage_multiplier"], value_prefix="d")
    decision = _decision(
        start_year_comparison=start_year_comparison,
        horizon_comparison=horizon_comparison,
        horizon_aggregate=horizon_aggregate,
        slippage_comparison=slippage_comparison,
    )

    paths = {
        "start_year_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_summary_{MODEL_TAG}.csv",
        "start_year_comparison": OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_comparison_{MODEL_TAG}.csv",
        "horizon_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv",
        "horizon_aggregate": OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv",
        "horizon_comparison": OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_{MODEL_TAG}.csv",
        "slippage_stress": OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv",
        "slippage_comparison": OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_comparison_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
    }
    start_year_summary.to_csv(paths["start_year_summary"], index=False, encoding="utf-8-sig")
    start_year_comparison.to_csv(paths["start_year_comparison"], index=False, encoding="utf-8-sig")
    horizon_summary.to_csv(paths["horizon_summary"], index=False, encoding="utf-8-sig")
    horizon_aggregate.to_csv(paths["horizon_aggregate"], index=False, encoding="utf-8-sig")
    horizon_comparison.to_csv(paths["horizon_comparison"], index=False, encoding="utf-8-sig")
    slippage_stress.to_csv(paths["slippage_stress"], index=False, encoding="utf-8-sig")
    slippage_comparison.to_csv(paths["slippage_comparison"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(
        start_year_summary=start_year_summary,
        start_year_comparison=start_year_comparison,
        horizon_aggregate=horizon_aggregate,
        horizon_comparison=horizon_comparison,
        slippage_stress=slippage_stress,
        slippage_comparison=slippage_comparison,
        decision=decision,
        paths=paths,
    )

    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print(f"report: {paths['report']}")


if __name__ == "__main__":
    main()

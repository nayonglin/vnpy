from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from vnpy.trader.utility import ArrayManager


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage772_am40_80_120_oi_monthly_v1"
OUTPUT_PREFIX = "qmt_roll_stage772_am40_80_120_oi_monthly"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
MONTH_STARTS = tuple(pd.date_range("2018-01-01", "2026-05-01", freq="MS"))
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE772_MAX_WORKERS", "4"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
PROFILE_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profile_aggregate_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_am120_{MODEL_TAG}.csv"
PHASE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_phase_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmaps_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmaps_{MODEL_TAG}.png"
COMPARISON_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_chart_{MODEL_TAG}.png"

_WORKER_METADATA: dict[str, Any] | None = None
_WORKER_PROFILE_BY_NAME: dict[str, dict[str, Any]] | None = None


class QmtRollPortfolioStrategyExactAm(QmtRollPortfolioStrategy):
    """Research-only wrapper that replaces ArrayManager size after normal init."""

    research_exact_array_manager_size: int = 0
    parameters = [
        *QmtRollPortfolioStrategy.parameters,
        "research_exact_array_manager_size",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        exact_size = int(self.research_exact_array_manager_size or 0)
        if exact_size > 0:
            self.ams = {vt_symbol: ArrayManager(exact_size) for vt_symbol in self.vt_symbols}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _window_name(start: pd.Timestamp) -> str:
    return f"mstart_{start.strftime('%Y_%m')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} independent start to {ANALYSIS_END.strftime('%Y-%m-%d')}"


def _preload_for_start(start: pd.Timestamp) -> pd.Timestamp:
    if start < pd.Timestamp("2020-01-01"):
        return (start - pd.Timedelta(days=365)).normalize()
    return max(pd.Timestamp(s653.s517.PRELOAD_START_DT).normalize(), (start - pd.Timedelta(days=365)).normalize())


def _profile_specs(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    base_nooi = s748._candidate_500k_spec(metadata)
    base_oi = s757._candidate_spec(metadata)
    rows: list[dict[str, Any]] = []
    for oi_mode, base_spec in [("no_oi", base_nooi), ("oi_restore", base_oi)]:
        for am_label, am_size, strategy_cls, overrides, note in [
            (
                "am120",
                120,
                QmtRollPortfolioStrategy,
                {},
                "Default current AM gate. Effective AM size remains 120.",
            ),
            (
                "am80",
                80,
                QmtRollPortfolioStrategy,
                {"array_manager_size_floor": 40},
                "Lower floor to 40 but keep legacy formula, so effective AM size is 80.",
            ),
            (
                "am40",
                41,
                QmtRollPortfolioStrategyExactAm,
                {"array_manager_size_floor": 40, "research_exact_array_manager_size": 41},
                "Research-only AM40 minimum. AM=41 because signal compares current and previous MA40.",
            ),
        ]:
            profile = f"{oi_mode}_{am_label}"
            capital = replace(
                base_spec.capital,
                variant=f"stage772_{profile}",
                label=f"Stage772 {oi_mode} {am_label}",
                note=f"{base_spec.capital.note} | {note}",
            )
            spec = replace(base_spec, capital=capital, overrides={**base_spec.overrides, **overrides}, profile=profile)
            rows.append(
                {
                    "profile": profile,
                    "oi_mode": oi_mode,
                    "am_label": am_label,
                    "declared_am_size": am_size,
                    "strategy_cls": strategy_cls,
                    "spec": spec,
                    "note": note,
                }
            )
    return rows


def _build_setting(
    *,
    metadata: dict[str, Any],
    spec: s653.ForcedVariant,
    base_c3_overrides: dict[str, Any],
    start: pd.Timestamp,
) -> dict[str, Any]:
    c3_overrides = dict(base_c3_overrides)
    c3_overrides["trade_start_date"] = start.date().isoformat()
    setting = s653.s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s653.s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
        strategy_overrides=c3_overrides,
    )
    setting["capital_base"] = spec.capital.c3_capital
    setting.update(spec.overrides)
    return setting


def _run_engine(
    *,
    profile: dict[str, Any],
    start: pd.Timestamp,
    metadata: dict[str, Any],
    base_c3_overrides: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec: s653.ForcedVariant = replace(profile["spec"])
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    original_preload = s653.s517.PRELOAD_START_DT
    try:
        s653.s517.START_DT = start.to_pydatetime()
        s653.s517.END_DT = ANALYSIS_END.to_pydatetime()
        s653.s517.PRELOAD_START_DT = _preload_for_start(start).to_pydatetime()

        s653.s517.assert_stage196_database_sentinels()
        s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(s653.s517.PRELOAD_START_DT, s653.s517.START_DT - timedelta(days=365))
        _, open_map = s653.s517.s506.s501._seed_proxy_maps()
        engine = s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s653.s517.Interval.DAILY,
            start=preload_start,
            end=s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = _build_setting(metadata=metadata, spec=spec, base_c3_overrides=base_c3_overrides, start=start)
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result: {profile['profile']} {start.date()}")

        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= start.date()) & (daily.index <= ANALYSIS_END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        strategy = getattr(engine, "strategy", None)
        for column, value in [
            ("forced_margin_deleverage_count", int(getattr(strategy, "forced_margin_deleverage_count", 0) or 0)),
            (
                "forced_margin_deleverage_closed_volume",
                int(getattr(strategy, "forced_margin_deleverage_closed_volume", 0) or 0),
            ),
            ("forced_margin_deleverage_ratio", float(getattr(strategy, "forced_margin_deleverage_ratio", 0.0) or 0.0)),
            (
                "forced_margin_deleverage_max_observed_ratio",
                float(getattr(strategy, "forced_margin_deleverage_max_observed_ratio", 0.0) or 0.0),
            ),
        ]:
            daily[column] = value

        positions = s653.s517.build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
        else:
            c3_margin_daily = pd.DataFrame(columns=["variant", "combo_variant", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"])

        combined = _combine_daily(daily, c3_margin_daily, spec)
        forced_events = pd.DataFrame(getattr(strategy, "forced_margin_deleverage_events", []) if strategy else [])
        if not forced_events.empty:
            forced_events["variant"] = spec.capital.variant
            forced_events["label"] = spec.capital.label
            forced_events["profile"] = spec.profile
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end
        s653.s517.PRELOAD_START_DT = original_preload
    return combined, forced_events


def _combine_daily(daily: pd.DataFrame, margin_daily: pd.DataFrame, spec: s653.ForcedVariant) -> pd.DataFrame:
    merged = daily.sort_values("date").merge(
        margin_daily[margin_daily["variant"].eq(spec.capital.variant)][
            ["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
        ],
        on="date",
        how="left",
    )
    for column in ["c3_margin_exact", "c3_active_contracts", "c3_active_products"]:
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
    merged["total_net_pnl"] = pd.to_numeric(merged["net_pnl"], errors="coerce").fillna(0.0)
    merged["total_slippage"] = pd.to_numeric(merged["slippage"], errors="coerce").fillna(0.0)
    merged["account_equity"] = float(spec.capital.account_capital) + merged["total_net_pnl"].cumsum()
    merged["total_margin_exact"] = merged["c3_margin_exact"]
    merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * float(s650.BROKER_MARGIN_MULTIPLIER)
    merged["broker10_margin_to_equity_pct"] = (
        merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return merged


def _metric_common(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["source_name"] = "stage772_am40_80_120_oi_monthly"
    out["rebased_end_equity"] = out["end_equity"]
    out["rebased_total_return_pct"] = out["total_return_pct"]
    out["rebased_cagr_pct"] = out["cagr_pct"]
    out["rebased_max_dd_pct"] = out["max_dd_pct"]
    out["rebased_sharpe"] = out["sharpe"]
    out["rebased_min_equity"] = out["min_equity"]
    out["max_broker10_margin_to_rebased_equity_pct"] = out["max_broker10_margin_to_equity_pct"]
    out["p95_broker10_margin_to_rebased_equity_pct"] = out["p95_broker10_margin_to_equity_pct"]
    out["nav_end"] = float(out["end_equity"]) / float(out["account_capital"])
    return out


def _curve_common(curve: pd.DataFrame) -> pd.DataFrame:
    frame = curve.copy()
    frame["source_name"] = "stage772_am40_80_120_oi_monthly"
    frame["rebased_equity"] = frame["account_equity"]
    frame["rebased_nav"] = frame["nav"]
    frame["broker10_margin_to_rebased_equity_pct"] = frame["broker10_margin_to_equity_pct"]
    return frame


def _add_month_fields(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    frame["start_month"] = frame["requested_start_month"].astype(str)
    start_ts = pd.to_datetime(frame["start_month"] + "-01", errors="coerce")
    frame["start_year"] = start_ts.dt.year
    frame["start_month_num"] = start_ts.dt.month
    frame["positive_return"] = (pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce") > 0.0).astype(int)
    frame["mature_63d"] = (pd.to_numeric(frame["trading_days"], errors="coerce") >= 63).astype(int)
    frame["mature_126d"] = (pd.to_numeric(frame["trading_days"], errors="coerce") >= 126).astype(int)
    frame["mature_252d"] = (pd.to_numeric(frame["trading_days"], errors="coerce") >= 252).astype(int)
    frame["dd40_fail"] = (pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce") < -40.0).astype(int)
    frame["dd50_fail"] = (pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce") < -50.0).astype(int)
    return frame


def _run_one(task: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    global _WORKER_METADATA, _WORKER_PROFILE_BY_NAME
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
        _WORKER_PROFILE_BY_NAME = {profile["profile"]: profile for profile in _profile_specs(_WORKER_METADATA)}
    metadata = _WORKER_METADATA
    profile_by_name = _WORKER_PROFILE_BY_NAME or {}
    profile = profile_by_name[str(task["profile"])]
    start = pd.Timestamp(task["start"])
    base_c3_overrides = dict(task["base_c3_overrides"])
    frame, forced_events = _run_engine(
        profile=profile,
        start=start,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    spec: s653.ForcedVariant = profile["spec"]
    row, curve, costs = s748._metric_row(
        frame,
        spec=spec,
        window_name=_window_name(start),
        window_label=_window_label(start),
        window_group="monthly_start",
        forced_events=forced_events,
    )
    row = _metric_common(row)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size", "note"]:
        row[key] = profile[key]
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    curve = _curve_common(curve)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size"]:
        curve[key] = profile[key]
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    for cost in costs:
        for key in ["profile", "oi_mode", "am_label", "declared_am_size"]:
            cost[key] = profile[key]
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
        cost["variant"] = spec.capital.variant
    return row, costs, curve


def _run_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    profiles = _profile_specs(metadata)
    base_c3_overrides = dict(s513._c3_overrides(MONTH_STARTS[0].to_pydatetime()))
    tasks = [
        {
            "profile": profile["profile"],
            "start": start.strftime("%Y-%m-%d"),
            "base_c3_overrides": base_c3_overrides,
        }
        for profile in profiles
        for start in MONTH_STARTS
    ]

    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage772] launching {len(tasks)} runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage772] running {idx}/{len(tasks)} {task['profile']} {task['start']}", flush=True)
            row, costs, curve = _run_one(task)
            rows.append(row)
            cost_rows.extend(costs)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, costs, curve = future.result()
                rows.append(row)
                cost_rows.extend(costs)
                curves.append(curve)
                print(f"[stage772] completed {idx}/{len(tasks)} {task['profile']} {task['start']}", flush=True)

    summary = _add_month_fields(pd.DataFrame(rows)).sort_values(["oi_mode", "am_label", "start_month"]).reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["oi_mode", "am_label", "start_month", "cost_multiplier"]).reset_index(drop=True)
    curves_all = pd.concat(curves, ignore_index=True, sort=False).sort_values(["oi_mode", "am_label", "start_month", "date"]).reset_index(drop=True)
    return summary, cost, curves_all


def _profile_aggregate(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (oi_mode, am_label), group in summary.groupby(["oi_mode", "am_label"], sort=True):
        mature = group[group["mature_252d"].eq(1)].copy()
        for bucket, frame in [("all", group), ("mature_252d", mature)]:
            returns = pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce")
            dds = pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce")
            sharpes = pd.to_numeric(frame["rebased_sharpe"], errors="coerce")
            rows.append(
                {
                    "oi_mode": oi_mode,
                    "am_label": am_label,
                    "bucket": bucket,
                    "start_count": int(len(frame)),
                    "positive_count": int(frame["positive_return"].sum()) if len(frame) else 0,
                    "positive_rate_pct": float(frame["positive_return"].mean() * 100.0) if len(frame) else 0.0,
                    "median_return_pct": float(returns.median()) if len(frame) else 0.0,
                    "p10_return_pct": float(returns.quantile(0.10)) if len(frame) else 0.0,
                    "min_return_pct": float(returns.min()) if len(frame) else 0.0,
                    "median_dd_pct": float(dds.median()) if len(frame) else 0.0,
                    "worst_dd_pct": float(dds.min()) if len(frame) else 0.0,
                    "dd40_fail_count": int(frame["dd40_fail"].sum()) if len(frame) else 0,
                    "dd50_fail_count": int(frame["dd50_fail"].sum()) if len(frame) else 0,
                    "median_sharpe": float(sharpes.median()) if len(frame) else 0.0,
                    "trade_count_median": float(pd.to_numeric(frame["total_trade_count"], errors="coerce").median()) if len(frame) else 0.0,
                    "trade_count_sum": float(pd.to_numeric(frame["total_trade_count"], errors="coerce").sum()) if len(frame) else 0.0,
                }
            )
    cost_view = cost[cost["cost_multiplier"].isin([2.0, 3.0])].copy()
    if not cost_view.empty:
        cost_view["dd40_fail"] = (pd.to_numeric(cost_view["max_dd_pct"], errors="coerce") < -40.0).astype(int)
        cost_agg = (
            cost_view.groupby(["oi_mode", "am_label", "cost_multiplier"], as_index=False)
            .agg(cost_dd40_fail_count=("dd40_fail", "sum"), cost_median_return_pct=("total_return_pct", "median"))
        )
        for _, cost_row in cost_agg.iterrows():
            rows.append(
                {
                    "oi_mode": cost_row["oi_mode"],
                    "am_label": cost_row["am_label"],
                    "bucket": f"cost_{cost_row['cost_multiplier']}x_all",
                    "start_count": int((summary["oi_mode"].eq(cost_row["oi_mode"]) & summary["am_label"].eq(cost_row["am_label"])).sum()),
                    "dd40_fail_count": int(cost_row["cost_dd40_fail_count"]),
                    "median_return_pct": float(cost_row["cost_median_return_pct"]),
                }
            )
    return pd.DataFrame(rows).sort_values(["oi_mode", "am_label", "bucket"]).reset_index(drop=True)


def _comparison_vs_am120(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for oi_mode, mode_group in summary.groupby("oi_mode", sort=True):
        base = mode_group[mode_group["am_label"].eq("am120")].copy()
        for am_label in ["am40", "am80"]:
            candidate = mode_group[mode_group["am_label"].eq(am_label)].copy()
            merged = base.merge(candidate, on="start_month", suffixes=("_base", "_candidate"), how="inner")
            merged["return_delta_pct"] = (
                pd.to_numeric(merged["rebased_total_return_pct_candidate"], errors="coerce")
                - pd.to_numeric(merged["rebased_total_return_pct_base"], errors="coerce")
            )
            merged["dd_delta_pp"] = (
                pd.to_numeric(merged["rebased_max_dd_pct_candidate"], errors="coerce")
                - pd.to_numeric(merged["rebased_max_dd_pct_base"], errors="coerce")
            )
            merged["sharpe_delta"] = (
                pd.to_numeric(merged["rebased_sharpe_candidate"], errors="coerce")
                - pd.to_numeric(merged["rebased_sharpe_base"], errors="coerce")
            )
            merged["candidate_return_win"] = (merged["return_delta_pct"] > 0.0).astype(int)
            merged["candidate_dd_win"] = (merged["dd_delta_pp"] > 0.0).astype(int)
            for bucket, frame in [("all", merged), ("mature_252d", merged[merged["mature_252d_base"].eq(1)])]:
                rows.append(
                    {
                        "oi_mode": oi_mode,
                        "candidate_am_label": am_label,
                        "baseline_am_label": "am120",
                        "bucket": bucket,
                        "start_count": int(len(frame)),
                        "return_win_count": int(frame["candidate_return_win"].sum()) if len(frame) else 0,
                        "return_win_rate_pct": float(frame["candidate_return_win"].mean() * 100.0) if len(frame) else 0.0,
                        "dd_win_count": int(frame["candidate_dd_win"].sum()) if len(frame) else 0,
                        "dd_win_rate_pct": float(frame["candidate_dd_win"].mean() * 100.0) if len(frame) else 0.0,
                        "median_return_delta_pct": float(frame["return_delta_pct"].median()) if len(frame) else 0.0,
                        "p10_return_delta_pct": float(frame["return_delta_pct"].quantile(0.10)) if len(frame) else 0.0,
                        "min_return_delta_pct": float(frame["return_delta_pct"].min()) if len(frame) else 0.0,
                        "median_dd_delta_pp": float(frame["dd_delta_pp"].median()) if len(frame) else 0.0,
                        "median_sharpe_delta": float(frame["sharpe_delta"].median()) if len(frame) else 0.0,
                    }
                )
    return pd.DataFrame(rows).sort_values(["oi_mode", "candidate_am_label", "bucket"]).reset_index(drop=True)


def _phase_summary(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    frame["start_phase"] = pd.cut(
        pd.to_numeric(frame["start_year"], errors="coerce"),
        bins=[2017, 2019, 2021, 2023, 2025, 2026],
        labels=["2018-2019", "2020-2021", "2022-2023", "2024-2025", "2026"],
        include_lowest=True,
    ).astype(str)
    rows: list[dict[str, Any]] = []
    for (oi_mode, am_label, phase), group in frame.groupby(["oi_mode", "am_label", "start_phase"], sort=True):
        rows.append(
            {
                "oi_mode": oi_mode,
                "am_label": am_label,
                "start_phase": phase,
                "start_count": int(len(group)),
                "median_return_pct": float(pd.to_numeric(group["rebased_total_return_pct"], errors="coerce").median()),
                "p10_return_pct": float(pd.to_numeric(group["rebased_total_return_pct"], errors="coerce").quantile(0.10)),
                "min_return_pct": float(pd.to_numeric(group["rebased_total_return_pct"], errors="coerce").min()),
                "median_dd_pct": float(pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce").median()),
                "dd40_fail_count": int(group["dd40_fail"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["oi_mode", "am_label", "start_phase"]).reset_index(drop=True)


def _plot_heatmaps(summary: pd.DataFrame, value_column: str, path: Path, title: str, cmap: str, vcenter: float) -> None:
    profiles = ["no_oi_am120", "no_oi_am80", "no_oi_am40", "oi_restore_am120", "oi_restore_am80", "oi_restore_am40"]
    fig, axes = plt.subplots(2, 3, figsize=(18, 8.5), constrained_layout=True)
    values = pd.to_numeric(summary[value_column], errors="coerce")
    vmin = float(np.nanpercentile(values, 5)) if values.notna().any() else -1.0
    vmax = float(np.nanpercentile(values, 95)) if values.notna().any() else 1.0
    if value_column == "rebased_total_return_pct":
        vmin, vmax = -100.0, max(400.0, float(np.nanpercentile(values, 90)))
    norm = TwoSlopeNorm(vcenter=vcenter, vmin=min(vmin, vcenter - 1e-6), vmax=max(vmax, vcenter + 1e-6))
    for ax, profile in zip(axes.ravel(), profiles, strict=False):
        data = summary[(summary["oi_mode"] + "_" + summary["am_label"]).eq(profile)].copy()
        pivot = data.pivot_table(index="start_year", columns="start_month_num", values=value_column, aggfunc="first")
        im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap, norm=norm)
        ax.set_title(profile)
        ax.set_xticks(range(12))
        ax.set_xticklabels(range(1, 13))
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([str(int(item)) for item in pivot.index])
        for i, year in enumerate(pivot.index):
            for j, month in enumerate(pivot.columns):
                value = pivot.loc[year, month]
                if pd.notna(value):
                    ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")
    fig.suptitle(title)
    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.75)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_comparison(comparison: pd.DataFrame, path: Path) -> None:
    view = comparison[comparison["bucket"].eq("mature_252d")].copy()
    labels = [f"{row.oi_mode}\n{row.candidate_am_label}" for row in view.itertuples(index=False)]
    x = np.arange(len(view))
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
    axes[0].bar(x, view["return_win_rate_pct"], color="#2563eb")
    axes[0].axhline(55.0, color="#ef4444", linestyle="--", linewidth=1)
    axes[0].set_ylabel("Return win rate vs AM120 %")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(x, view["median_return_delta_pct"], color="#059669")
    axes[1].axhline(0.0, color="#111827", linewidth=1)
    axes[1].set_ylabel("Median return delta pp")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("Stage772 AM40/80 vs AM120 mature monthly starts")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _build_decision(profile_agg: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    mature = comparison[comparison["bucket"].eq("mature_252d")].copy()
    candidates: list[dict[str, Any]] = []
    for row in mature.itertuples(index=False):
        pass_basic = (
            float(row.return_win_rate_pct) >= 55.0
            and float(row.median_return_delta_pct) >= 0.0
            and float(row.p10_return_delta_pct) >= -25.0
            and float(row.median_dd_delta_pp) >= -2.0
        )
        candidates.append(
            {
                "oi_mode": row.oi_mode,
                "candidate_am_label": row.candidate_am_label,
                "pass_basic": bool(pass_basic),
                "return_win_rate_pct": float(row.return_win_rate_pct),
                "median_return_delta_pct": float(row.median_return_delta_pct),
                "p10_return_delta_pct": float(row.p10_return_delta_pct),
                "median_dd_delta_pp": float(row.median_dd_delta_pp),
            }
        )
    promoted = [item for item in candidates if item["pass_basic"]]
    return {
        "stage": "Stage772",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "analysis_start_first": MONTH_STARTS[0].date().isoformat(),
        "analysis_start_last": MONTH_STARTS[-1].date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "profile_count": 6,
        "monthly_start_count_per_profile": len(MONTH_STARTS),
        "decision": "am_gate_candidate_passed_basic_screen" if promoted else "am_gate_no_candidate_passed_basic_screen",
        "candidate_screen": candidates,
        "overfit_judgment": (
            "medium: AM gate is an engineering prior, but AM40/80 must pass across mature monthly starts, weak phases, and cost stress before promotion"
        ),
        "continue_value": (
            "yes: if AM80 is not worse than AM120 across OI/no-OI, next audit incremental trades; if not, keep AM120 formal"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "profile_aggregate": str(PROFILE_AGG_PATH),
            "comparison_vs_am120": str(COMPARISON_PATH),
            "phase_summary": str(PHASE_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "dd_heatmap": str(DD_HEATMAP_PATH),
            "comparison_chart": str(COMPARISON_CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _write_report(profile_agg: pd.DataFrame, comparison: pd.DataFrame, phase: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage772 AM40/80/120 × OI 月度启动验证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 起点：`{MONTH_STARTS[0].strftime('%Y-%m')}` 到 `{MONTH_STARTS[-1].strftime('%Y-%m')}`；终点 `{ANALYSIS_END.date()}`。",
        "- 六组：无OI/有OI × AM120/AM80/AM40。AM40 为研究专用 AM=41。",
        "",
        "## Profile Aggregate",
        "",
        _md_table(profile_agg, max_rows=80),
        "",
        "## Comparison Vs AM120",
        "",
        _md_table(comparison, max_rows=40),
        "",
        "## Phase Summary",
        "",
        _md_table(phase, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合判断：`{decision['overfit_judgment']}`",
        f"- 继续价值：`{decision['continue_value']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, cost, curves = _run_all()
    profile_agg = _profile_aggregate(summary, cost)
    comparison = _comparison_vs_am120(summary)
    phase = _phase_summary(summary)
    decision = _build_decision(profile_agg, comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    profile_agg.to_csv(PROFILE_AGG_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    phase.to_csv(PHASE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_heatmaps(summary, "rebased_total_return_pct", RETURN_HEATMAP_PATH, "Stage772 Return % Heatmaps", "RdYlGn", 0.0)
    _plot_heatmaps(summary, "rebased_max_dd_pct", DD_HEATMAP_PATH, "Stage772 Max DD % Heatmaps", "RdYlGn", -40.0)
    _plot_comparison(comparison, COMPARISON_CHART_PATH)
    _write_report(profile_agg, comparison, phase, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

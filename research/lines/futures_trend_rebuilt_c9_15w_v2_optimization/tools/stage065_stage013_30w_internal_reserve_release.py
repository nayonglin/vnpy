from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
THIS_TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
UPSTREAM_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
for candidate in (str(THIS_TOOLS_DIR), str(UPSTREAM_TOOLS_DIR), str(PORTFOLIO_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import stage064_stage013_reserve_topup_true_engine as s064


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage065"
MODEL_TAG = "stage065_stage013_30w_internal_reserve_release_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage065_stage013_30w_internal_reserve_release"

REQUESTED_START = pd.Timestamp("2021-07-01")
REQUESTED_END = pd.Timestamp("2026-07-02")
START_MONTHS = (1, 7)
BASE_TRADING_CAPITAL = float(s064.BASE_TRADING_CAPITAL)
RESERVE_CAPITAL = 150_000.0
TOTAL_INITIAL_CAPITAL = BASE_TRADING_CAPITAL + RESERVE_CAPITAL

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage065_stage013_30w_internal_reserve_release"
STAGES_DIR = LINE_DIR / "stages"
BACK_LOG_PATH = ROOT / "back_log.md"

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
KEY_STARTS_PATH = OUT / f"{OUTPUT_PREFIX}_key_starts_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
MONTH_END_CASHFLOW_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_month_end_cashflow_events_{MODEL_TAG}.csv"
MONTH_END_ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_month_end_entry_candidates_{MODEL_TAG}.csv.gz"
MONTH_END_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_month_end_trades_{MODEL_TAG}.csv.gz"
MONTH_END_TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_month_end_trade_events_{MODEL_TAG}.csv.gz"
ACCOUNTING_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_accounting_audit_{MODEL_TAG}.csv"
CHART_KEY_PATH = OUT / f"{OUTPUT_PREFIX}_key_start_total_equity_{MODEL_TAG}.png"
CHART_ALL_NAV_PATH = OUT / f"{OUTPUT_PREFIX}_all_start_total_nav_{MODEL_TAG}.png"
CHART_VARIANT_PATH = OUT / f"{OUTPUT_PREFIX}_variant_underwater_summary_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s064._json_safe(value)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    return s064._safe_sum(frame, column)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s064._drawdown_pct(equity)


def _daily_sharpe(nav: pd.Series) -> float:
    return s064._daily_sharpe(nav)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _build_start_dates() -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    latest_start = pd.Timestamp("2026-01-01")
    for year in range(REQUESTED_START.year, REQUESTED_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= min(REQUESTED_END, latest_start):
                starts.append(start)
    return starts


class QmtRollPortfolioStrategyStage065MonthEndReserve(s064.QmtRollPortfolioStrategyStage064ReserveTopup):
    enable_stage065_month_end_release: bool = False

    parameters = s064.QmtRollPortfolioStrategyStage064ReserveTopup.parameters + [
        "enable_stage065_month_end_release",
    ]

    def _stage065_is_month_end_release_day(self) -> bool:
        if not bool(getattr(self, "enable_stage065_month_end_release", False)):
            return True
        if self.current_bar_date is None:
            return False

        current = pd.Timestamp(self.current_bar_date).normalize()
        dates = pd.DatetimeIndex([pd.Timestamp(item).normalize() for item in getattr(self, "available_trade_dates", [])])
        if dates.empty:
            return False
        index = dates.searchsorted(current, side="left")
        if index >= len(dates) or dates[index] != current:
            return False
        if index == len(dates) - 1:
            return True
        return pd.Timestamp(dates[index + 1]).to_period("M") != current.to_period("M")

    def _stage064_maybe_topup(self) -> None:
        strategy_equity = max(0.0, float(self.estimated_equity or self.base_capital or 0.0))
        self._stage064_set_broker_equity_from_strategy(strategy_equity)
        if not self._stage064_enabled() or not self._stage065_is_month_end_release_day():
            return

        floor = self._stage064_floor()
        pre_broker_equity = float(self.stage064_broker_equity_for_sizing)
        reserve_before = max(0.0, float(self.stage064_reserve_remaining or 0.0))
        requested_topup = max(0.0, floor - pre_broker_equity)
        min_amount = max(0.0, float(self.stage064_topup_min_amount or 0.0))
        topup = min(reserve_before, requested_topup) if requested_topup >= min_amount else 0.0
        if topup <= 0.0:
            return

        self.stage064_external_cashflow_cumulative += topup
        self.stage064_reserve_remaining = max(0.0, reserve_before - topup)
        self.stage064_topup_count += 1
        post_broker_equity = strategy_equity + self.stage064_external_cashflow_cumulative
        self.stage064_broker_equity_for_sizing = post_broker_equity
        current_date = self.current_bar_date
        date_text = _date_text(current_date) if current_date is not None else ""
        self.stage064_cashflow_events.append(
            {
                "datetime": pd.Timestamp(current_date).to_pydatetime() if current_date is not None else "",
                "date": date_text,
                "cashflow_type": "reserve_topup",
                "amount": topup,
                "strategy_equity_ex_cashflow_before": strategy_equity,
                "broker_equity_with_cashflow_before": pre_broker_equity,
                "broker_equity_with_cashflow_after": post_broker_equity,
                "external_cashflow_cumulative_after": self.stage064_external_cashflow_cumulative,
                "reserve_remaining_before": reserve_before,
                "reserve_remaining_after": self.stage064_reserve_remaining,
                "topup_floor_equity": floor,
                "reason": "month_end_broker_equity_below_floor",
            }
        )


def _stage065_month_end_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s064.s013._stage013_profile(metadata)
    spec = profile["spec"]
    profile_name = "stage065_stage013_30w_month_end_reserve_15w"
    capital = replace(
        spec.capital,
        variant=profile_name,
        label="Stage065 Stage013 30w account, 15w trading sleeve, month-end reserve release",
        account_capital=BASE_TRADING_CAPITAL,
        c3_capital=BASE_TRADING_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage065 keeps total account capital at 300,000 from day one; "
            "15w starts as trading sleeve, 15w starts as idle reserve. Month-end only top-up restores "
            "broker sizing equity to 150,000 when below floor. Reserve transfer is internal capital "
            "reallocation, not alpha PnL."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage064_reserve_topup": True,
        "enable_stage065_month_end_release": True,
        "stage064_initial_reserve_capital": RESERVE_CAPITAL,
        "stage064_base_trading_capital": BASE_TRADING_CAPITAL,
        "stage064_topup_floor_equity": BASE_TRADING_CAPITAL,
        "stage064_topup_min_amount": 1.0,
    }
    result = dict(profile)
    result["profile"] = profile_name
    result["strategy_cls"] = QmtRollPortfolioStrategyStage065MonthEndReserve
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=profile_name)
    return result


def _run_live_stage065_month_end(
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s064.s013.s847.START
    original_end = s064.s013.s847.END
    original_minute_by_symbol = s064.s013.s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s064.s901._ensure_c9_minute_bars(metadata)
    try:
        s064.s013.s847.START = analysis_start.normalize()
        s064.s013.s847.END = analysis_end.normalize()
        profile = _stage065_month_end_profile(metadata)
        combined, frames = s064._run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        s064.s013.s847.START = original_start
        s064.s013.s847.END = original_end
        s064.s013.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol

    combined["account_capital"] = spec.capital.account_capital
    combined["c3_capital"] = spec.capital.c3_capital
    combined["profile"] = spec.profile
    for frame in frames.values():
        if frame.empty:
            continue
        frame["account_capital"] = spec.capital.account_capital
        frame["c3_capital"] = spec.capital.c3_capital
        frame["profile"] = spec.profile
    return combined, frames, spec


def _with_run_columns(frame: pd.DataFrame, start: pd.Timestamp, version: str, frame_name: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["version"] = version
    result["reserve_capital"] = RESERVE_CAPITAL
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    result["frame_name"] = frame_name
    return result


def _apply_idle_reserve_to_baseline(baseline_curves: pd.DataFrame) -> pd.DataFrame:
    curves = baseline_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves = curves.dropna(subset=["date"]).sort_values(["requested_start_month", "date"]).reset_index(drop=True)
    curves["stage"] = STAGE
    curves["model_tag"] = MODEL_TAG
    curves["version"] = "stage065_30w_idle_reserve_no_release"
    curves["reserve_capital"] = RESERVE_CAPITAL
    curves["strategy_equity_ex_cashflow"] = pd.to_numeric(curves["account_equity"], errors="coerce").ffill()
    curves["external_cashflow"] = 0.0
    curves["external_cashflow_cumulative"] = 0.0
    curves["reserve_remaining"] = RESERVE_CAPITAL
    curves["broker_equity_with_cashflow"] = curves["strategy_equity_ex_cashflow"]
    curves["total_account_equity"] = curves["broker_equity_with_cashflow"] + RESERVE_CAPITAL
    curves["strategy_nav_ex_cashflow"] = curves["strategy_equity_ex_cashflow"] / BASE_TRADING_CAPITAL
    curves["broker_nav_vs_base_not_return"] = curves["broker_equity_with_cashflow"] / BASE_TRADING_CAPITAL
    curves["total_account_nav"] = curves["total_account_equity"] / TOTAL_INITIAL_CAPITAL
    for _, idx in curves.groupby("requested_start_month").groups.items():
        subset = curves.loc[idx, "strategy_equity_ex_cashflow"]
        curves.loc[idx, "strategy_drawdown_pct_ex_cashflow"] = _drawdown_pct(subset).to_numpy()
        curves.loc[idx, "broker_drawdown_pct_with_cashflow"] = curves.loc[idx, "strategy_drawdown_pct_ex_cashflow"]
        curves.loc[idx, "total_account_drawdown_pct"] = _drawdown_pct(curves.loc[idx, "total_account_equity"]).to_numpy()
        curves.loc[idx, "days_since_start"] = np.arange(len(idx), dtype=int)
    return curves


def _summary_from_curve(curve: pd.DataFrame, version: str, start: pd.Timestamp) -> dict[str, Any]:
    summary = s064._summarize_curve(curve, RESERVE_CAPITAL, start)
    frame = curve.copy().sort_values("date").reset_index(drop=True)
    total_equity = pd.to_numeric(frame["total_account_equity"], errors="coerce").ffill()
    broker_equity = pd.to_numeric(frame["broker_equity_with_cashflow"], errors="coerce").ffill()
    total_below = total_equity < TOTAL_INITIAL_CAPITAL - 1e-9
    broker_below = broker_equity < BASE_TRADING_CAPITAL - 1e-9
    last_total_below = frame.loc[total_below, "date"].max() if total_below.any() else pd.NaT
    last_broker_below = frame.loc[broker_below, "date"].max() if broker_below.any() else pd.NaT
    summary.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "version": version,
            "release_rule": version,
            "reserve_capital": RESERVE_CAPITAL,
            "total_initial_capital_with_reserve": TOTAL_INITIAL_CAPITAL,
            "total_account_days_below_initial": int(total_below.sum()),
            "total_account_last_below_initial": _date_text(last_total_below) if pd.notna(last_total_below) else "",
            "broker_last_below_base": _date_text(last_broker_below) if pd.notna(last_broker_below) else "",
        }
    )
    return summary


def _load_daily_reference(starts: list[pd.Timestamp]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not s064.SUMMARY_PATH.exists() or not s064.CURVES_PATH.exists():
        raise RuntimeError(f"missing Stage064 daily-topup outputs: {s064.SUMMARY_PATH} / {s064.CURVES_PATH}")
    allowed = {_start_month_text(start) for start in starts}
    summary = pd.read_csv(s064.SUMMARY_PATH, encoding="utf-8-sig")
    curves = pd.read_csv(s064.CURVES_PATH, encoding="utf-8-sig")
    summary = summary[
        summary["requested_start_month"].astype(str).isin(allowed)
        & np.isclose(pd.to_numeric(summary["reserve_capital"], errors="coerce"), RESERVE_CAPITAL)
    ].copy()
    curves = curves[
        curves["requested_start_month"].astype(str).isin(allowed)
        & np.isclose(pd.to_numeric(curves["reserve_capital"], errors="coerce"), RESERVE_CAPITAL)
    ].copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["stage"] = STAGE
    curves["model_tag"] = MODEL_TAG
    curves["version"] = "stage064_30w_daily_floor_release_reference"
    summary_rows = []
    for start_text, group in curves.groupby("requested_start_month"):
        summary_rows.append(_summary_from_curve(group, "stage064_30w_daily_floor_release_reference", pd.Timestamp(f"{start_text}-01")))
    return pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True), curves


def _variant_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version, group in summary.groupby("version", sort=False):
        strategy_returns = pd.to_numeric(group["strategy_total_return_ex_cashflow_pct"], errors="coerce")
        strategy_dds = pd.to_numeric(group["strategy_max_dd_ex_cashflow_pct"], errors="coerce")
        total_returns = pd.to_numeric(group["total_account_return_pct"], errors="coerce")
        total_dds = pd.to_numeric(group["total_account_max_dd_pct"], errors="coerce")
        rows.append(
            {
                "version": version,
                "start_count": int(len(group)),
                "positive_strategy_count": int(strategy_returns.gt(0.0).sum()),
                "positive_total_account_count": int(total_returns.gt(0.0).sum()),
                "min_strategy_return_pct": float(strategy_returns.min()),
                "median_strategy_return_pct": float(strategy_returns.median()),
                "worst_strategy_dd_pct": float(strategy_dds.min()),
                "min_total_account_return_pct": float(total_returns.min()),
                "median_total_account_return_pct": float(total_returns.median()),
                "worst_total_account_dd_pct": float(total_dds.min()),
                "sum_total_account_days_below_initial": int(
                    pd.to_numeric(group["total_account_days_below_initial"], errors="coerce").fillna(0).sum()
                ),
                "max_total_account_days_below_initial": int(
                    pd.to_numeric(group["total_account_days_below_initial"], errors="coerce").fillna(0).max()
                ),
                "max_external_cashflow_used": float(
                    pd.to_numeric(group["max_external_cashflow_used"], errors="coerce").fillna(0.0).max()
                ),
                "cashflow_event_count_sum": int(
                    pd.to_numeric(group["cashflow_event_count"], errors="coerce").fillna(0).sum()
                ),
                "broker_below_base_days_sum": int(
                    pd.to_numeric(group["broker_days_below_base"], errors="coerce").fillna(0).sum()
                ),
                "total_trade_count_sum": float(pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0).sum()),
                "total_slippage_sum": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0).sum()),
                "audit_pass_count": int(pd.to_numeric(group["audit_pass"], errors="coerce").fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _key_start_table(summary: pd.DataFrame) -> pd.DataFrame:
    key_starts = {"2022-01", "2022-07", "2023-01", "2023-07", "2026-01"}
    columns = [
        "version",
        "requested_start_month",
        "strategy_total_return_ex_cashflow_pct",
        "total_account_return_pct",
        "total_account_max_dd_pct",
        "total_account_days_below_initial",
        "total_account_last_below_initial",
        "max_external_cashflow_used",
        "cashflow_event_count",
        "total_trade_count",
        "audit_pass",
    ]
    return summary[summary["requested_start_month"].astype(str).isin(key_starts)][columns].sort_values(
        ["requested_start_month", "version"]
    )


def run_backtests() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    if not s064.CANDIDATE_AI_PATH.exists():
        print("[stage065] Stage062 candidate AI file missing; rebuilding AI file only", flush=True)
        s064.s062.build_full_monthly_ai_file()

    starts = _build_start_dates()
    _, baseline_curves_raw = s064._load_baseline_frames(starts)
    idle_curves = _apply_idle_reserve_to_baseline(baseline_curves_raw)
    idle_summary_rows = []
    for start_text, group in idle_curves.groupby("requested_start_month"):
        idle_summary_rows.append(_summary_from_curve(group, "stage065_30w_idle_reserve_no_release", pd.Timestamp(f"{start_text}-01")))
    idle_summary = pd.DataFrame(idle_summary_rows).sort_values("requested_start").reset_index(drop=True)

    daily_summary, daily_curves = _load_daily_reference(starts)
    metadata = s064.s901.s513._metadata()
    month_summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []
    cashflow_frames: list[pd.DataFrame] = []
    audit_rows: list[dict[str, Any]] = []

    with s064.s062._patched_live_ai_path(s064.CANDIDATE_AI_PATH):
        for index, start in enumerate(starts, start=1):
            print(f"[stage065] run {index}/{len(starts)} month-end reserve start={_date_text(start)}", flush=True)
            combined, frames, _spec = _run_live_stage065_month_end(metadata, start, REQUESTED_END)
            curve = s064._apply_cashflow_to_curve(
                combined=combined,
                cashflow_events=frames.get("cashflow_events", pd.DataFrame()),
                daily_accounting=frames.get("daily_accounting", pd.DataFrame()),
                reserve_capital=RESERVE_CAPITAL,
            )
            curve = _with_run_columns(curve, start, "stage065_30w_month_end_floor_release", "curves")
            curve["days_since_start"] = np.arange(len(curve), dtype=int)
            curve_frames.append(curve)
            summary = _summary_from_curve(curve, "stage065_30w_month_end_floor_release", start)
            month_summary_rows.append(summary)
            audit_rows.append(
                {
                    "version": "stage065_30w_month_end_floor_release",
                    "requested_start_month": _start_month_text(start),
                    **{k: v for k, v in summary.items() if k.endswith("_max_abs") or k == "audit_pass"},
                }
            )
            candidate_frames.append(
                _with_run_columns(
                    frames.get("entry_candidates", pd.DataFrame()),
                    start,
                    "stage065_30w_month_end_floor_release",
                    "entry_candidates",
                )
            )
            trade_frames.append(
                _with_run_columns(frames.get("trades", pd.DataFrame()), start, "stage065_30w_month_end_floor_release", "trades")
            )
            trade_event_frames.append(
                _with_run_columns(
                    frames.get("trade_events", pd.DataFrame()),
                    start,
                    "stage065_30w_month_end_floor_release",
                    "trade_events",
                )
            )
            cashflow_frames.append(
                _with_run_columns(
                    frames.get("cashflow_events", pd.DataFrame()),
                    start,
                    "stage065_30w_month_end_floor_release",
                    "cashflow_events",
                )
            )

    month_summary = pd.DataFrame(month_summary_rows).sort_values("requested_start").reset_index(drop=True)
    all_summary = pd.concat([idle_summary, daily_summary, month_summary], ignore_index=True, sort=False)
    all_curves = pd.concat([idle_curves, daily_curves, *curve_frames], ignore_index=True, sort=False)
    return {
        "summary": all_summary,
        "variant_summary": _variant_summary(all_summary),
        "key_starts": _key_start_table(all_summary),
        "curves": all_curves,
        "month_end_cashflow_events": pd.concat([f for f in cashflow_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in cashflow_frames)
        else pd.DataFrame(),
        "month_end_entry_candidates": pd.concat([f for f in candidate_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in candidate_frames)
        else pd.DataFrame(),
        "month_end_trades": pd.concat([f for f in trade_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in trade_frames)
        else pd.DataFrame(),
        "month_end_trade_events": pd.concat([f for f in trade_event_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in trade_event_frames)
        else pd.DataFrame(),
        "accounting_audit": pd.DataFrame(audit_rows).sort_values("requested_start_month").reset_index(drop=True),
    }


def _plot_outputs(curves: pd.DataFrame, summary: pd.DataFrame, variant_summary: pd.DataFrame) -> None:
    labels = {
        "stage065_30w_idle_reserve_no_release": "30w idle reserve, no release",
        "stage064_30w_daily_floor_release_reference": "30w daily floor release",
        "stage065_30w_month_end_floor_release": "30w month-end floor release",
    }
    colors = {
        "stage065_30w_idle_reserve_no_release": "#6b7280",
        "stage064_30w_daily_floor_release_reference": "#2563eb",
        "stage065_30w_month_end_floor_release": "#f97316",
    }
    key_starts = ["2022-01", "2022-07", "2023-01", "2023-07"]
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), sharex=False, constrained_layout=True)
    for ax, start in zip(axes.ravel(), key_starts, strict=False):
        for version, label in labels.items():
            frame = curves[
                curves["requested_start_month"].astype(str).eq(start) & curves["version"].astype(str).eq(version)
            ].sort_values("date")
            if frame.empty:
                continue
            ax.plot(frame["date"], frame["total_account_equity"], linewidth=1.1, label=label, color=colors.get(version))
        ax.axhline(TOTAL_INITIAL_CAPITAL, linestyle="--", linewidth=0.9, color="#111827")
        ax.set_title(f"Total account equity start {start}")
        ax.set_ylabel("equity")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_KEY_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for version, label in labels.items():
        subset = curves[curves["version"].astype(str).eq(version)].copy()
        if subset.empty:
            continue
        grouped = (
            subset.groupby("date", as_index=False)
            .agg(
                median_nav=("total_account_nav", "median"),
                min_nav=("total_account_nav", "min"),
                worst_dd=("total_account_drawdown_pct", "min"),
                median_dd=("total_account_drawdown_pct", "median"),
            )
            .sort_values("date")
        )
        axes[0].plot(grouped["date"], grouped["median_nav"], label=label, linewidth=1.2, color=colors.get(version))
        axes[0].fill_between(grouped["date"], grouped["min_nav"], grouped["median_nav"], alpha=0.08, color=colors.get(version))
        axes[1].plot(grouped["date"], grouped["worst_dd"], label=label, linewidth=1.0, color=colors.get(version))
    axes[0].axhline(1.0, linestyle="--", linewidth=0.9, color="#111827")
    axes[0].set_title("All starts: median and weakest total-account NAV")
    axes[0].set_ylabel("NAV vs 300k")
    axes[1].set_title("All starts: worst total-account drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    axes[0].grid(True, alpha=0.25)
    axes[1].legend(fontsize=8, loc="best")
    fig.savefig(CHART_ALL_NAV_PATH, dpi=160)
    plt.close(fig)

    plot = variant_summary.copy()
    x = np.arange(len(plot))
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), constrained_layout=True)
    axes[0].bar(x - 0.18, plot["min_total_account_return_pct"], width=0.36, label="min return %", color="#ef4444")
    axes[0].bar(x + 0.18, plot["median_total_account_return_pct"], width=0.36, label="median return %", color="#22c55e")
    axes[0].axhline(0.0, linewidth=0.9, color="#111827")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(plot["version"].astype(str), rotation=20, ha="right")
    axes[0].set_ylabel("return %")
    axes[0].legend(loc="best")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(x - 0.18, plot["worst_total_account_dd_pct"], width=0.36, label="worst DD %", color="#2563eb")
    axes[1].bar(
        x + 0.18,
        plot["max_total_account_days_below_initial"],
        width=0.36,
        label="max days below 300k",
        color="#f97316",
    )
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(plot["version"].astype(str), rotation=20, ha="right")
    axes[1].legend(loc="best")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_VARIANT_PATH, dpi=160)
    plt.close(fig)


def write_report_and_records(decision: dict[str, Any]) -> Path:
    now = datetime.now()
    summary = pd.read_csv(SUMMARY_PATH)
    variant_summary = pd.read_csv(VARIANT_SUMMARY_PATH)
    key_starts = pd.read_csv(KEY_STARTS_PATH)
    audit = pd.read_csv(ACCOUNTING_AUDIT_PATH)

    report_lines = [
        "# Stage065 Stage013 30w internal reserve release",
        "",
        f"- generated_at: `{decision['generated_at']}`",
        f"- line_id: `{LINE_ID}`",
        f"- candidate: `{decision['candidate']}`",
        f"- AI file: `{s064.CANDIDATE_AI_PATH}`",
        f"- start range: `{REQUESTED_START.date()}` to `{REQUESTED_END.date()}`; half-year starts",
        "- live config changed: `false`; CTP connected: `false`; order API calls: `0`",
        "",
        "## Research Judgment",
        "",
        "- 30w is treated as internal account capital from day one. NAV denominator is always 300,000.",
        "- 15w trading sleeve produces PnL. 15w reserve sleeve is idle cash until released into broker sizing equity.",
        "- Reserve release is not alpha and is not counted as strategy PnL.",
        "- Month-end release is predeclared from monthly AI/settlement cadence; daily release is kept as an aggressive reference.",
        "",
        "## Variant Summary",
        "",
        _md_table(variant_summary),
        "",
        "## Key Starts",
        "",
        _md_table(key_starts, max_rows=30),
        "",
        "## Accounting Audit",
        "",
        f"- month-end audit pass: `{int(pd.to_numeric(audit['audit_pass'], errors='coerce').fillna(0).sum())}/{len(audit)}`",
        f"- max residual: `{decision['max_accounting_residual']:.8f}`",
        "",
        _md_table(audit, max_rows=20),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- reason: {decision['decision_reason']}",
        f"- overfit reflection before: {decision['overfit_reflection_before']}",
        f"- overfit reflection after: {decision['overfit_reflection_after']}",
        f"- continue value before: {decision['continue_value_before']}",
        f"- continue value after: {decision['continue_value_after']}",
        "",
        "## Outputs",
        "",
    ]
    for key, value in decision["outputs"].items():
        report_lines.append(f"- {key}: `{value}`")
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    month = summary[summary["version"].eq("stage065_30w_month_end_floor_release")].copy()
    daily = summary[summary["version"].eq("stage064_30w_daily_floor_release_reference")].copy()
    idle = summary[summary["version"].eq("stage065_30w_idle_reserve_no_release")].copy()
    month_ret = pd.to_numeric(month["total_account_return_pct"], errors="coerce")
    month_dd = pd.to_numeric(month["total_account_max_dd_pct"], errors="coerce")
    month_days = pd.to_numeric(month["total_account_days_below_initial"], errors="coerce").fillna(0)
    daily_ret = pd.to_numeric(daily["total_account_return_pct"], errors="coerce")
    daily_dd = pd.to_numeric(daily["total_account_max_dd_pct"], errors="coerce")
    idle_ret = pd.to_numeric(idle["total_account_return_pct"], errors="coerce")
    idle_dd = pd.to_numeric(idle["total_account_max_dd_pct"], errors="coerce")
    month_trades = float(pd.to_numeric(month["total_trade_count"], errors="coerce").fillna(0.0).sum())
    month_slippage = float(pd.to_numeric(month["total_slippage"], errors="coerce").fillna(0.0).sum())

    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage065_30w_internal_reserve_release.md"
    stage_lines = [
        "# Stage065 30w internal reserve release",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 是否重要突破：否，资金治理候选研究；不是 alpha 突破",
        "- 是否触发A/B：是；资金/保证金治理层与候选正式部署相关，按 A vs C 口径记录",
        "",
        "## 外部调研与判断",
        "",
        "- GIPS/TWR 口径强调现金流必须与投资收益分离；本阶段 30w 从第一天作为总账户分母，避免把储备释放误算成收益。",
        "- pysystemtrade capital correction 思路支持把资本变化作为 deployment/capital multiplier 问题，而不是信号 alpha。",
        "- CPPI/动态资金配置资料支持 risky sleeve + safety sleeve 的结构性思考，但本策略不做 CPPI 乘数扫参，只测试固定 15w/15w 和固定释放节奏。",
        "- 本次判断：候选释放规则以月末为主，日级只保留为容量上限参考；不按 2022/2023 亏损低点定制日期、金额或阈值。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无正式入口修改",
        "- 删除脚本：无",
        "- 新增参数：`enable_stage065_month_end_release`；复用 Stage064 的 `stage064_initial_reserve_capital`、`stage064_topup_floor_equity` 等会计字段",
        "- 修改参数：无正式交易参数；研究固定 `30w total = 15w trading + 15w reserve`",
        "- 删除参数：无",
        "",
        "## 回测参数",
        "",
        "- 版本：Stage013 account-state pilot + 30w internal reserve release",
        "- 对照臂：A0 `30w idle reserve no release`，C1 `30w daily floor release reference`，C2 `30w month-end floor release`",
        "- 起点：`2021-07` 到 `2026-01` 逐半年",
        "- 终点：`2026-07-02`",
        "- 交易袖本金：`150,000`",
        "- 储备袖本金：`150,000`",
        f"- AI 池：`{s064.CANDIDATE_AI_PATH}`",
        "",
        "## 结果（月末释放主候选）",
        "",
        f"- 逐起点详见 `{SUMMARY_PATH}`",
        f"- 总账户正收益：`{int(month_ret.gt(0.0).sum())}/{len(month)}`",
        f"- 总账户最小/中位收益：`{float(month_ret.min()):.4f}% / {float(month_ret.median()):.4f}%`",
        f"- 总账户最差最大回撤：`{float(month_dd.min()):.4f}%`",
        f"- 最大水下天数：`{int(month_days.max())}`",
        f"- 总滑点：`{month_slippage:.4f}`",
        f"- 总交易次数：`{month_trades:.0f}`",
        "- 胜率：本阶段不新增逐笔胜率口径，避免把资金转移误读为交易胜负。",
        f"- 会计校验：`{decision['accounting_audit_pass_count']}/{decision['accounting_audit_row_count']}` 通过，最大残差 `{decision['max_accounting_residual']:.8f}`",
        "",
        "## 对照摘要",
        "",
        f"- A0 不释放：最小/中位总账户收益 `{float(idle_ret.min()):.4f}%/{float(idle_ret.median()):.4f}%`，最差回撤 `{float(idle_dd.min()):.4f}%`。",
        f"- C1 日级释放：最小/中位总账户收益 `{float(daily_ret.min()):.4f}%/{float(daily_ret.median()):.4f}%`，最差回撤 `{float(daily_dd.min()):.4f}%`。",
        f"- C2 月末释放：最小/中位总账户收益 `{float(month_ret.min()):.4f}%/{float(month_ret.median()):.4f}%`，最差回撤 `{float(month_dd.min()):.4f}%`。",
        "",
        "## 统计口径 Review",
        "",
        "- 总账户权益 `total_account_equity = broker_equity_with_cashflow + reserve_remaining`。",
        "- 总账户收益分母固定 `300,000`，不允许用 `150,000` 作为含储备收益分母。",
        "- 储备释放是内部资金搬运，必须满足 `total_account_equity - 300000 = cumulative net_pnl`。",
        "- 水下天数按 `total_account_equity < 300000`，不是按 broker sleeve 是否低于 `150000`。",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 原因：{decision['decision_reason']}",
        "",
        "## 后续规划和 TODO",
        "",
        "- 若继续，应优先做 month-end vs daily 的新增手数/品种/月度归因，看释放是否只是放大坏交易。",
        "- 不继续 sweep 储备比例、释放阈值或具体日期；这些会把资金治理变成针对历史弱窗口的过拟合。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    stage_path.write_text("\n".join(stage_lines) + "\n", encoding="utf-8")

    back_log_entry = (
        f"\n{now.strftime('%Y-%m-%d %H:%M')} CST：`{LINE_ID}` Stage065 完成 30w 内部储备袖释放研究。"
        f"脚本 `{Path(__file__).relative_to(ROOT)}`；固定 `30w total = 15w trading + 15w reserve`，"
        f"起点 2021-07 到 2026-01 逐半年，终点 2026-07-02；对照 A0 不释放、C1 日级释放、C2 月末释放。"
        f"C2 月末释放总账户正收益 `{int(month_ret.gt(0.0).sum())}/{len(month)}`，"
        f"最小/中位总账户收益 `{float(month_ret.min()):.4f}%/{float(month_ret.median()):.4f}%`，"
        f"最差最大回撤 `{float(month_dd.min()):.4f}%`，最大水下天数 `{int(month_days.max())}`，"
        f"总滑点 `{month_slippage:.4f}`，总交易次数 `{month_trades:.0f}`；"
        f"会计校验 `{decision['accounting_audit_pass_count']}/{decision['accounting_audit_row_count']}` 通过，"
        f"最大残差 `{decision['max_accounting_residual']:.8f}`。决策 `{decision['decision']}`：{decision['decision_reason']} "
        f"未改正式配置、未连接 CTP、未调用订单 API。过拟合反思：{decision['overfit_reflection_after']} "
        f"继续价值：{decision['continue_value_after']}\n"
    )
    with BACK_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(back_log_entry)
    return stage_path


def main() -> None:
    print("[stage065] run 30w internal reserve release study", flush=True)
    results = run_backtests()
    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["key_starts"].to_csv(KEY_STARTS_PATH, index=False, encoding="utf-8-sig")
    results["curves"].to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    results["month_end_cashflow_events"].to_csv(MONTH_END_CASHFLOW_EVENTS_PATH, index=False, encoding="utf-8-sig")
    results["month_end_entry_candidates"].to_csv(MONTH_END_ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    results["month_end_trades"].to_csv(MONTH_END_TRADES_PATH, index=False, encoding="utf-8-sig")
    results["month_end_trade_events"].to_csv(MONTH_END_TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    results["accounting_audit"].to_csv(ACCOUNTING_AUDIT_PATH, index=False, encoding="utf-8-sig")
    _plot_outputs(results["curves"], results["summary"], results["variant_summary"])

    audit = results["accounting_audit"].copy()
    residual_cols = [column for column in audit.columns if column.endswith("_max_abs") and not column.startswith("engine_")]
    max_residual = float(audit[residual_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).max().max())
    audit_pass_count = int(pd.to_numeric(audit["audit_pass"], errors="coerce").fillna(0).sum())

    variant = results["variant_summary"].set_index("version")
    month = variant.loc["stage065_30w_month_end_floor_release"]
    daily = variant.loc["stage064_30w_daily_floor_release_reference"]
    idle = variant.loc["stage065_30w_idle_reserve_no_release"]

    decision_name = "stage065_month_end_release_keep_research_only"
    reason = (
        "30w 总账户口径更清晰；月末释放是低自由度规则，水下天数优于不释放和日级释放，"
        "但收益中位数低于日级释放、2023-01 起点仍未回到 30w、最差回撤未改善，因此暂不直接晋级，"
        "先保留为资金治理候选。"
    )
    if (
        audit_pass_count == len(audit)
        and float(month["positive_total_account_count"]) >= float(idle["positive_total_account_count"])
        and float(month["worst_total_account_dd_pct"]) > float(idle["worst_total_account_dd_pct"])
        and float(month["max_total_account_days_below_initial"]) < float(idle["max_total_account_days_below_initial"])
    ):
        decision_name = "stage065_month_end_release_candidate_for_capital_governance_shadow"
        reason = (
            "月末释放在固定 30w 分母下改善不释放基线的左尾和水下天数，且会计校验全部通过；"
            "但日级释放仍是容量上限参考，下一步必须做新增手数归因后才能考虑部署。"
        )
    if float(daily["max_total_account_days_below_initial"]) < float(month["max_total_account_days_below_initial"]):
        reason += " 当前结果提示日级释放对缩短最长水下期更有效，月末规则偏稳但可能释放太慢。"

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_mode": "day",
        "candidate": "stage013_30w_total_15w_trading_15w_internal_reserve_release",
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "base_trading_capital": BASE_TRADING_CAPITAL,
        "reserve_capital": RESERVE_CAPITAL,
        "total_initial_capital": TOTAL_INITIAL_CAPITAL,
        "arms": [
            "stage065_30w_idle_reserve_no_release",
            "stage064_30w_daily_floor_release_reference",
            "stage065_30w_month_end_floor_release",
        ],
        "accounting_audit_pass_count": audit_pass_count,
        "accounting_audit_row_count": int(len(audit)),
        "max_accounting_residual": max_residual,
        "decision": decision_name,
        "decision_reason": reason,
        "strategy_changed": True,
        "official_live_config_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": (
            "否。金额来自用户实际资金结构 15w/15w，释放节奏只测试结构性日级/月末规则，没有按亏损月份、产品或阈值反推。"
        ),
        "overfit_reflection_after": (
            "基本否。本阶段没有 sweep 储备比例、释放阈值或具体日期；若继续为了 2022/2023 曲线去调释放日或金额，就会变成过拟合。"
        ),
        "continue_value_before": (
            "有。它把账户分母、交易袖容量和储备释放拆开，可直接回答 30w 账户下水下期是否仍长。"
        ),
        "continue_value_after": (
            "有，但只作为资金治理继续。若要晋级，需要先确认新增手数不是集中放大坏交易，并在 shadow 资金层观察。"
        ),
        "external_research": {
            "gips_calculation_methodology": "https://www.gipsstandards.org/wp-content/uploads/2021/03/calculation_methodology_gs_2011.pdf",
            "pysystemtrade_capital_correction": "https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html",
            "cppi_intro": "https://quantpedia.com/introduction-to-cppi-constant-proportion-portfolio-insurance/",
            "margin_management": "https://www.returnstacked.com/margin-management-in-return-stacking/",
            "judgment": (
                "Treat reserve release as internal capital allocation/capacity governance, not strategy alpha."
            ),
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "key_starts": str(KEY_STARTS_PATH),
            "curves": str(CURVES_PATH),
            "month_end_cashflow_events": str(MONTH_END_CASHFLOW_EVENTS_PATH),
            "month_end_entry_candidates": str(MONTH_END_ENTRY_CANDIDATES_PATH),
            "month_end_trades": str(MONTH_END_TRADES_PATH),
            "month_end_trade_events": str(MONTH_END_TRADE_EVENTS_PATH),
            "accounting_audit": str(ACCOUNTING_AUDIT_PATH),
            "chart_key": str(CHART_KEY_PATH),
            "chart_all_nav": str(CHART_ALL_NAV_PATH),
            "chart_variant": str(CHART_VARIANT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stage_path = write_report_and_records(decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()

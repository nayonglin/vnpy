from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517  # noqa: E402
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650  # noqa: E402
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653  # noqa: E402
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748  # noqa: E402
import analyze_qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare as s749  # noqa: E402
import analyze_qmt_roll_stage750_official_500k_vs_c50_monthly_start as s750  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402


MODEL_TAG = "stage751_cash_reserve_bucket_monthly_start_v1"
OUTPUT_PREFIX = "qmt_roll_stage751_cash_reserve_bucket_monthly_start"
LINE_ID = "futures_trend_cash_reserve_bucket"

ANALYSIS_END = s750.ANALYSIS_END
MONTH_STARTS = s750.MONTH_STARTS
TOTAL_CAPITAL = 500_000.0
TRADING_BUCKET_CAPITAL = 400_000.0
RESERVE_CAPITAL = TOTAL_CAPITAL - TRADING_BUCKET_CAPITAL
CASH_RESERVE_VARIANT = "stage526_500k_total_400k_bucket_100k_reserve_topup_r080_pc25_maxpos4_stage751"

A50_ARM = "A50_official"
C_ARM = "C_cash_reserve_40w_bucket"
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE751_MAX_WORKERS", "4"))))
MONTH_LIMIT = max(0, int(os.environ.get("STAGE751_MONTH_LIMIT", "0")))
MONTH_FILTER = {
    item.strip()
    for item in str(os.environ.get("STAGE751_MONTHS", "")).split(",")
    if item.strip()
}

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
RESERVE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reserve_events_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_heatmap_{MODEL_TAG}.png"
FOCUS_202205_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_focus_202205_{MODEL_TAG}.png"


class CashReserveBucketStrategy(QmtRollPortfolioStrategy):
    enable_cash_reserve_bucket: bool = False
    cash_reserve_bucket_trading_target: float = 0.0
    cash_reserve_bucket_initial_reserve: float = 0.0
    cash_reserve_bucket_only_after_trade_start: bool = True

    parameters = list(QmtRollPortfolioStrategy.parameters) + [
        "enable_cash_reserve_bucket",
        "cash_reserve_bucket_trading_target",
        "cash_reserve_bucket_initial_reserve",
        "cash_reserve_bucket_only_after_trade_start",
    ]
    variables = list(QmtRollPortfolioStrategy.variables) + [
        "cash_reserve_bucket_remaining",
        "cash_reserve_bucket_cumulative_injection",
        "cash_reserve_bucket_topup_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.cash_reserve_bucket_remaining: float = max(0.0, float(self.cash_reserve_bucket_initial_reserve or 0.0))
        self.cash_reserve_bucket_cumulative_injection: float = 0.0
        self.cash_reserve_bucket_topup_count: int = 0
        self.cash_reserve_bucket_events: list[dict[str, Any]] = []

    def _cash_reserve_bucket_trade_started(self) -> bool:
        if not self.cash_reserve_bucket_only_after_trade_start:
            return True
        if self.current_bar_date is None:
            return False
        start_text = str(self.trade_start_date or "").strip()
        if not start_text:
            return True
        try:
            return self.current_bar_date >= pd.Timestamp(start_text).normalize()
        except Exception:
            return True

    def _apply_cash_reserve_bucket_topup(self) -> None:
        if not self.enable_cash_reserve_bucket:
            return
        if not self._cash_reserve_bucket_trade_started():
            return
        target = max(0.0, float(self.cash_reserve_bucket_trading_target or 0.0))
        remaining = max(0.0, float(self.cash_reserve_bucket_remaining or 0.0))
        if target <= 0.0 or remaining <= 0.0:
            return
        before = float(self.estimated_equity or 0.0)
        if before >= target:
            return
        injection = min(target - before, remaining)
        if injection <= 1e-9:
            return

        self.estimated_equity = before + injection
        self.settled_balance = float(self.settled_balance or 0.0) + injection
        self.cash_reserve_bucket_remaining = remaining - injection
        self.cash_reserve_bucket_cumulative_injection += injection
        self.cash_reserve_bucket_topup_count += 1
        date_text = self.current_bar_date.date().isoformat() if self.current_bar_date is not None else ""
        self.cash_reserve_bucket_events.append(
            {
                "date": date_text,
                "estimated_equity_before": before,
                "injection": injection,
                "estimated_equity_after": float(self.estimated_equity),
                "reserve_remaining_after": float(self.cash_reserve_bucket_remaining),
                "topup_count": int(self.cash_reserve_bucket_topup_count),
            }
        )

    def _refresh_risk_state(self, bars) -> None:
        self.estimated_equity = self._estimate_equity(bars)
        self._apply_cash_reserve_bucket_topup()
        self._refresh_portfolio_drawdown_state()
        self._refresh_portfolio_volatility_budget_state()
        self._record_portfolio_volatility_budget_scale_snapshot(bars)
        self._refresh_portfolio_overheat_cooldown_state()
        self._record_portfolio_overheat_cooldown_scale_snapshot(bars)
        self.total_margin_in_use = self._estimate_margin_usage(bars)
        self.cluster_margin_usage = self._estimate_margin_usage_by_cluster(bars)
        self.cluster_unrealized_pnl = self._estimate_unrealized_pnl_by_cluster(bars)
        self._refresh_portfolio_margin_deleverage_state()
        self.risk_cluster_margin_in_use = max(self.cluster_margin_usage.values(), default=0.0)
        self.risk_cluster_unrealized_loss_in_use = max(
            (max(0.0, -float(value)) for value in self.cluster_unrealized_pnl.values()),
            default=0.0,
        )
        self._refresh_risk_cluster_heat_pressure_snapshot()
        self.risk_cluster_heat_gate_weight = self._current_min_risk_cluster_heat_gate_weight()
        limited_balance = self._limited_available_balance()
        self.current_risk_per_trade = self._risk_amount_from_ratio(self.risk_ratio_of_total_assets, limited_balance)
        self.risk_multiplier = self._current_streak_multiplier()


def _json_safe(value: Any) -> Any:
    return s749._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s749._md_table(frame, max_rows=max_rows)


def _window_name(start: pd.Timestamp) -> str:
    return f"mstart_{start.strftime('%Y_%m')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} independent start to {ANALYSIS_END.strftime('%Y-%m-%d')}"


def _selected_month_starts() -> list[pd.Timestamp]:
    starts = list(MONTH_STARTS)
    if MONTH_FILTER:
        starts = [item for item in starts if item.strftime("%Y-%m") in MONTH_FILTER]
    if MONTH_LIMIT > 0:
        starts = starts[:MONTH_LIMIT]
    return starts


def _add_month_fields(summary: pd.DataFrame) -> pd.DataFrame:
    return s750._add_month_fields(summary)


def _row_to_common(row: dict[str, Any], source_name: str) -> dict[str, Any]:
    out = dict(row)
    out["source_name"] = source_name
    out["rebased_end_equity"] = out["end_equity"]
    out["rebased_total_return_pct"] = out["total_return_pct"]
    out["rebased_cagr_pct"] = out["cagr_pct"]
    out["rebased_max_dd_pct"] = out["max_dd_pct"]
    out["rebased_sharpe"] = out["sharpe"]
    out["rebased_min_equity"] = out["min_equity"]
    out["max_broker10_margin_to_rebased_equity_pct"] = out["max_broker10_margin_to_equity_pct"]
    out["p95_broker10_margin_to_rebased_equity_pct"] = out["p95_broker10_margin_to_equity_pct"]
    out["dd40_pass"] = int(float(out["max_dd_pct"]) >= -40.0)
    out["broker10_90_watch_pass"] = int(float(out["max_broker10_margin_to_equity_pct"]) < 90.0)
    out["nav_end"] = float(out["end_equity"]) / float(out["account_capital"])
    return out


def _curve_to_common(curve: pd.DataFrame, source_name: str) -> pd.DataFrame:
    frame = curve.copy()
    frame["source_name"] = source_name
    frame["rebased_equity"] = frame["account_equity"]
    frame["rebased_nav"] = frame["nav"]
    frame["broker10_margin_to_rebased_equity_pct"] = frame["broker10_margin_to_equity_pct"]
    return frame


def _cash_reserve_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    base = s750._official_500k_spec(metadata)
    capital = replace(
        base.capital,
        variant=CASH_RESERVE_VARIANT,
        label="Stage751 official logic, 500k total / 400k trading bucket / 100k reserve top-up",
        account_capital=TOTAL_CAPITAL,
        c3_capital=TRADING_BUCKET_CAPITAL,
        risk_multiplier=0.80,
        note=(
            "Official Stage372 signal/universe/risk logic unchanged. Strategy trades with a 400k bucket; "
            "a 100k reserve bucket tops the trading bucket back toward 400k after losses."
        ),
    )
    overrides = dict(base.overrides)
    overrides.update(
        {
            "enable_cash_reserve_bucket": True,
            "cash_reserve_bucket_trading_target": TRADING_BUCKET_CAPITAL,
            "cash_reserve_bucket_initial_reserve": RESERVE_CAPITAL,
            "cash_reserve_bucket_only_after_trade_start": True,
        }
    )
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_cash_reserve_bucket_stage751")


def _run_cash_reserve_variant(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    try:
        s653.s517.START_DT = analysis_start.to_pydatetime()
        s653.s517.END_DT = analysis_end.to_pydatetime()

        s517.assert_stage196_database_sentinels()
        s517.s506._patch_stage506_raw_roots()
        c3_overrides = s513._c3_overrides(s517.START_DT)
        preload_start = max(s517.PRELOAD_START_DT, s517.START_DT - timedelta(days=365))
        _, open_map = s517.s506.s501._seed_proxy_maps()
        engine = s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s517.Interval.DAILY,
            start=preload_start,
            end=s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s517.build_roll_setting(
            metadata["margin_ratios"],
            risk_ratio=s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
            strategy_overrides=c3_overrides,
        )
        setting["capital_base"] = spec.capital.c3_capital
        setting.update(spec.overrides)
        setting["trade_start_date"] = analysis_start.date().isoformat()

        engine.add_strategy(CashReserveBucketStrategy, setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result: {spec.capital.variant}")

        daily = daily_df.copy()
        daily = daily.loc[
            (daily.index >= analysis_start.date()) & (daily.index <= analysis_end.date())
        ].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)

        strategy = getattr(engine, "strategy", None)
        reserve_events = pd.DataFrame(getattr(strategy, "cash_reserve_bucket_events", []) if strategy else [])
        if not reserve_events.empty:
            reserve_events["date"] = pd.to_datetime(reserve_events["date"], errors="coerce").dt.normalize()
            reserve_events = reserve_events[
                reserve_events["date"].ge(analysis_start.normalize())
                & reserve_events["date"].le(analysis_end.normalize())
            ].copy()
        grouped_injection = (
            reserve_events.groupby("date")["injection"].sum() if not reserve_events.empty else pd.Series(dtype=float)
        )
        daily["reserve_injection"] = daily["date"].map(grouped_injection).fillna(0.0).astype(float)
        daily["reserve_injection_cumsum"] = daily["reserve_injection"].cumsum()
        daily["reserve_remaining"] = (RESERVE_CAPITAL - daily["reserve_injection_cumsum"]).clip(lower=0.0)
        daily["trading_bucket_equity"] = (
            TRADING_BUCKET_CAPITAL + daily["net_pnl"].cumsum() + daily["reserve_injection_cumsum"]
        )
        daily["account_equity"] = TOTAL_CAPITAL + daily["net_pnl"].cumsum()
        daily["c3_equity"] = daily["trading_bucket_equity"]
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        daily["forced_margin_deleverage_count"] = int(
            getattr(strategy, "forced_margin_deleverage_count", 0) or 0
        )
        daily["forced_margin_deleverage_closed_volume"] = int(
            getattr(strategy, "forced_margin_deleverage_closed_volume", 0) or 0
        )
        daily["forced_margin_deleverage_ratio"] = float(
            getattr(strategy, "forced_margin_deleverage_ratio", 0.0) or 0.0
        )
        daily["forced_margin_deleverage_max_observed_ratio"] = float(
            getattr(strategy, "forced_margin_deleverage_max_observed_ratio", 0.0) or 0.0
        )

        positions = s517.build_positions_df(engine)
        if positions.empty:
            raise RuntimeError(f"empty positions: {spec.capital.variant}")
        positions["variant"] = spec.capital.variant
        positions["combo_variant"] = spec.capital.variant
        positions["label"] = spec.capital.label
        positions["risk_multiplier"] = spec.capital.risk_multiplier
        positions["account_capital"] = spec.capital.account_capital
        positions["c3_capital"] = spec.capital.c3_capital
        c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)

        combined = _combine_cash_daily(daily, c3_margin_daily, spec)
        combined["profile"] = spec.profile
        for column in [
            "forced_margin_deleverage_count",
            "forced_margin_deleverage_closed_volume",
            "forced_margin_deleverage_ratio",
            "forced_margin_deleverage_max_observed_ratio",
        ]:
            combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0

        forced_events = pd.DataFrame(getattr(strategy, "forced_margin_deleverage_events", []) if strategy else [])
        if not forced_events.empty:
            forced_events["variant"] = spec.capital.variant
            forced_events["label"] = spec.capital.label
            forced_events["profile"] = spec.profile
        if not reserve_events.empty:
            reserve_events["variant"] = spec.capital.variant
            reserve_events["label"] = spec.capital.label
            reserve_events["profile"] = spec.profile
            reserve_events["window_name"] = _window_name(analysis_start)
            reserve_events["requested_start_month"] = analysis_start.strftime("%Y-%m")
        return combined, forced_events, reserve_events
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end


def _combine_cash_daily(c3_daily: pd.DataFrame, margin_daily: pd.DataFrame, spec: s653.ForcedVariant) -> pd.DataFrame:
    merged = c3_daily.sort_values("date").merge(
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
    merged["account_equity"] = TOTAL_CAPITAL + merged["total_net_pnl"].cumsum()
    merged["trading_bucket_equity"] = (
        TRADING_BUCKET_CAPITAL + merged["total_net_pnl"].cumsum() + merged["reserve_injection_cumsum"]
    )
    merged["reserve_remaining"] = (RESERVE_CAPITAL - merged["reserve_injection_cumsum"]).clip(lower=0.0)
    merged["total_margin_exact"] = merged["c3_margin_exact"]
    merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * s650.BROKER_MARGIN_MULTIPLIER
    merged["broker10_margin_to_equity_pct"] = (
        merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    merged["broker10_margin_to_bucket_equity_pct"] = (
        merged["broker10_total_margin_exact"] / merged["trading_bucket_equity"].replace(0.0, np.nan) * 100.0
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    merged["xsmom_enabled"] = 0
    return merged


def _metric_row_cash(
    frame: pd.DataFrame,
    *,
    spec: s653.ForcedVariant,
    window_name: str,
    window_label: str,
    window_group: str,
    forced_events: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    row, curve, costs = s748._metric_row(
        frame,
        spec=spec,
        window_name=window_name,
        window_label=window_label,
        window_group=window_group,
        forced_events=forced_events,
    )
    ordered = frame.sort_values("date").reset_index(drop=True)
    bucket_equity = pd.to_numeric(ordered["trading_bucket_equity"], errors="coerce").ffill().fillna(TRADING_BUCKET_CAPITAL)
    bucket_dd = s748._drawdown_pct(bucket_equity)
    bucket_margin = pd.to_numeric(ordered["broker10_margin_to_bucket_equity_pct"], errors="coerce").fillna(0.0)
    reserve_deployed = pd.to_numeric(ordered["reserve_injection_cumsum"], errors="coerce").fillna(0.0)
    reserve_remaining = pd.to_numeric(ordered["reserve_remaining"], errors="coerce").fillna(RESERVE_CAPITAL)
    reserve_injection = pd.to_numeric(ordered["reserve_injection"], errors="coerce").fillna(0.0)

    first_topup_date = ""
    if reserve_injection.gt(0.0).any():
        first_topup_date = pd.Timestamp(ordered.loc[reserve_injection.gt(0.0), "date"].iloc[0]).date().isoformat()
    row.update(
        {
            "total_capital": TOTAL_CAPITAL,
            "trading_bucket_capital": TRADING_BUCKET_CAPITAL,
            "reserve_initial_capital": RESERVE_CAPITAL,
            "reserve_deployed_end": float(reserve_deployed.iloc[-1]) if len(reserve_deployed) else 0.0,
            "reserve_remaining_end": float(reserve_remaining.iloc[-1]) if len(reserve_remaining) else RESERVE_CAPITAL,
            "reserve_topup_count": int(reserve_injection.gt(0.0).sum()),
            "first_reserve_topup_date": first_topup_date,
            "trading_bucket_end_equity": float(bucket_equity.iloc[-1]) if len(bucket_equity) else TRADING_BUCKET_CAPITAL,
            "trading_bucket_min_equity": float(bucket_equity.min()) if len(bucket_equity) else TRADING_BUCKET_CAPITAL,
            "trading_bucket_max_dd_pct": float(bucket_dd.min()) if len(bucket_dd) else 0.0,
            "max_broker10_margin_to_bucket_equity_pct": float(bucket_margin.max()) if len(bucket_margin) else 0.0,
            "p95_broker10_margin_to_bucket_equity_pct": float(bucket_margin.quantile(0.95)) if len(bucket_margin) else 0.0,
        }
    )
    extra_columns = [
        "date",
        "trading_bucket_equity",
        "reserve_injection",
        "reserve_injection_cumsum",
        "reserve_remaining",
        "broker10_margin_to_bucket_equity_pct",
    ]
    curve = curve.merge(ordered[extra_columns], on="date", how="left")
    curve["trading_bucket_nav"] = curve["trading_bucket_equity"] / TRADING_BUCKET_CAPITAL
    curve["reserve_deployed_pct"] = curve["reserve_injection_cumsum"] / RESERVE_CAPITAL * 100.0
    return row, curve, costs


def _run_cash_reserve_month(
    start_iso: str,
    metadata: dict[str, Any],
    spec: s653.ForcedVariant,
    base_c3_overrides: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    s749._install_stable_c3_overrides(base_c3_overrides)
    start = pd.Timestamp(start_iso)
    frame, forced_events, reserve_events = _run_cash_reserve_variant(
        spec=spec,
        metadata=metadata,
        analysis_start=start,
        analysis_end=ANALYSIS_END,
    )
    row, curve, costs = _metric_row_cash(
        frame,
        spec=spec,
        window_name=_window_name(start),
        window_label=_window_label(start),
        window_group="monthly_start",
        forced_events=forced_events,
    )
    row = _row_to_common(row, "stage751_cash_reserve_bucket_monthly_start")
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    row["arm"] = C_ARM
    row["caveat"] = (
        "fresh independent monthly start; official Stage372 logic; "
        "total capital=500k, trading bucket=400k, reserve top-up=100k"
    )

    curve = _curve_to_common(curve, "stage751_cash_reserve_bucket_monthly_start")
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    curve["arm"] = C_ARM
    for cost in costs:
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
        cost["arm"] = C_ARM
        cost["variant"] = spec.capital.variant
    return row, costs, curve, reserve_events


def _run_cash_reserve_monthly() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s749.s744.s513._metadata()
    spec = _cash_reserve_spec(metadata)
    base_c3_overrides = dict(s749.ORIGINAL_C3_OVERRIDES(MONTH_STARTS[0].to_pydatetime()))
    starts = _selected_month_starts()
    start_items = [start.strftime("%Y-%m-%d") for start in starts]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    reserve_frames: list[pd.DataFrame] = []
    print(f"[stage751] launching {len(start_items)} cash-reserve monthly starts with workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, start_iso in enumerate(start_items, start=1):
            print(f"[stage751] running {idx}/{len(start_items)} {_window_name(pd.Timestamp(start_iso))}", flush=True)
            row, costs, curve, reserve_events = _run_cash_reserve_month(start_iso, metadata, spec, base_c3_overrides)
            summary_rows.append(row)
            cost_rows.extend(costs)
            curve_frames.append(curve)
            if not reserve_events.empty:
                reserve_frames.append(reserve_events)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_run_cash_reserve_month, start_iso, metadata, spec, base_c3_overrides): start_iso
                for start_iso in start_items
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                start_iso = futures[future]
                row, costs, curve, reserve_events = future.result()
                summary_rows.append(row)
                cost_rows.extend(costs)
                curve_frames.append(curve)
                if not reserve_events.empty:
                    reserve_frames.append(reserve_events)
                print(f"[stage751] completed {idx}/{len(start_items)} {_window_name(pd.Timestamp(start_iso))}", flush=True)

    candidate = _add_month_fields(pd.DataFrame(summary_rows)).sort_values("start_month").reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["start_month", "cost_multiplier"]).reset_index(drop=True)
    curves = (
        pd.concat(curve_frames, ignore_index=True, sort=False)
        .sort_values(["start_month", "date"])
        .reset_index(drop=True)
        if curve_frames
        else pd.DataFrame()
    )
    reserve = (
        pd.concat(reserve_frames, ignore_index=True, sort=False)
        .sort_values(["requested_start_month", "date"])
        .reset_index(drop=True)
        if reserve_frames
        else pd.DataFrame()
    )
    return candidate, cost, curves, reserve


def _load_a50_monthly() -> tuple[pd.DataFrame, pd.DataFrame]:
    if s750.A50_SUMMARY_PATH.exists() and s750.CURVES_PATH.exists():
        summary = pd.read_csv(s750.A50_SUMMARY_PATH, encoding="utf-8-sig")
        curves = pd.read_csv(s750.CURVES_PATH, encoding="utf-8-sig")
        curves = curves[curves["arm"].astype(str).eq(s750.A50_ARM)].copy()
    else:
        summary, _cost, curves = s750._run_a50_monthly()
    if MONTH_FILTER:
        summary = summary[summary["start_month"].astype(str).isin(MONTH_FILTER)].copy()
        curves = curves[curves["start_month"].astype(str).isin(MONTH_FILTER)].copy()
    if MONTH_LIMIT > 0:
        keep = [item.strftime("%Y-%m") for item in _selected_month_starts()]
        summary = summary[summary["start_month"].astype(str).isin(keep)].copy()
        curves = curves[curves["start_month"].astype(str).isin(keep)].copy()
    summary["arm"] = A50_ARM
    curves["arm"] = A50_ARM
    return _add_month_fields(summary).sort_values("start_month").reset_index(drop=True), curves


def _build_comparison(a50: pd.DataFrame, candidate: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "start_month",
        "window_name",
        "analysis_start",
        "analysis_end",
        "trading_days",
        "account_capital",
        "nav_end",
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_cagr_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "max_broker10_margin_to_rebased_equity_pct",
        "p95_broker10_margin_to_rebased_equity_pct",
        "days_over_100pct",
        "days_over_90pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "deployable_pass",
        "mature_63d",
        "mature_126d",
        "mature_252d",
        "start_year",
        "start_month_num",
    ]
    candidate_extra = [
        "trading_bucket_capital",
        "reserve_initial_capital",
        "reserve_deployed_end",
        "reserve_remaining_end",
        "reserve_topup_count",
        "first_reserve_topup_date",
        "trading_bucket_end_equity",
        "trading_bucket_max_dd_pct",
        "max_broker10_margin_to_bucket_equity_pct",
    ]
    left = a50[keep].copy().add_prefix("a50_")
    right = candidate[keep + candidate_extra].copy().add_prefix("c_")
    merged = left.merge(right, left_on="a50_start_month", right_on="c_start_month", how="inner")
    merged["start_month"] = merged["a50_start_month"]
    merged["start_ts"] = pd.to_datetime(merged["start_month"] + "-01", errors="coerce")
    merged["start_year"] = merged["a50_start_year"]
    merged["start_month_num"] = merged["a50_start_month_num"]
    merged["trading_days"] = merged["a50_trading_days"]
    merged["mature_63d"] = merged["a50_mature_63d"]
    merged["mature_126d"] = merged["a50_mature_126d"]
    merged["mature_252d"] = merged["a50_mature_252d"]
    merged["return_delta_pct"] = merged["c_rebased_total_return_pct"] - merged["a50_rebased_total_return_pct"]
    merged["return_retention_pct"] = np.where(
        merged["a50_rebased_total_return_pct"].abs() > 1e-9,
        merged["c_rebased_total_return_pct"] / merged["a50_rebased_total_return_pct"] * 100.0,
        np.nan,
    )
    merged["nav_delta"] = merged["c_nav_end"] - merged["a50_nav_end"]
    merged["dd_delta_pp"] = merged["c_rebased_max_dd_pct"] - merged["a50_rebased_max_dd_pct"]
    merged["sharpe_delta"] = merged["c_rebased_sharpe"] - merged["a50_rebased_sharpe"]
    merged["margin_peak_delta_pp"] = (
        merged["c_max_broker10_margin_to_rebased_equity_pct"]
        - merged["a50_max_broker10_margin_to_rebased_equity_pct"]
    )
    merged["trade_count_delta"] = merged["c_total_trade_count"] - merged["a50_total_trade_count"]
    merged["slippage_delta"] = merged["c_total_slippage"] - merged["a50_total_slippage"]
    merged["c_return_wins"] = (merged["return_delta_pct"] > 0.0).astype(int)
    merged["c_dd_wins"] = (merged["dd_delta_pp"] > 0.0).astype(int)
    merged["c_sharpe_wins"] = (merged["sharpe_delta"] > 0.0).astype(int)
    merged["c_both_return_dd_wins"] = (merged["c_return_wins"].eq(1) & merged["c_dd_wins"].eq(1)).astype(int)
    merged["a50_both_return_dd_wins"] = (
        merged["return_delta_pct"].lt(0.0) & merged["dd_delta_pp"].lt(0.0)
    ).astype(int)
    merged["c_positive_return"] = (merged["c_rebased_total_return_pct"] > 0.0).astype(int)
    merged["a50_positive_return"] = (merged["a50_rebased_total_return_pct"] > 0.0).astype(int)
    merged["c_dd30_fail"] = (merged["c_rebased_max_dd_pct"] < -30.0).astype(int)
    merged["a50_dd30_fail"] = (merged["a50_rebased_max_dd_pct"] < -30.0).astype(int)
    merged["c_dd40_fail"] = (merged["c_rebased_max_dd_pct"] < -40.0).astype(int)
    merged["a50_dd40_fail"] = (merged["a50_rebased_max_dd_pct"] < -40.0).astype(int)
    return merged.sort_values("start_ts").reset_index(drop=True)


def _bucket_stats(label: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"bucket": label, "start_count": 0}
    ret_delta = pd.to_numeric(frame["return_delta_pct"], errors="coerce")
    dd_delta = pd.to_numeric(frame["dd_delta_pp"], errors="coerce")
    retention = pd.to_numeric(frame["return_retention_pct"], errors="coerce")
    reserve_deployed = pd.to_numeric(frame["c_reserve_deployed_end"], errors="coerce").fillna(0.0)
    return {
        "bucket": label,
        "start_count": int(len(frame)),
        "c_return_win_count": int(frame["c_return_wins"].sum()),
        "c_return_win_rate_pct": float(frame["c_return_wins"].mean() * 100.0),
        "c_dd_win_count": int(frame["c_dd_wins"].sum()),
        "c_dd_win_rate_pct": float(frame["c_dd_wins"].mean() * 100.0),
        "c_both_return_dd_win_count": int(frame["c_both_return_dd_wins"].sum()),
        "a50_both_return_dd_win_count": int(frame["a50_both_return_dd_wins"].sum()),
        "c_positive_count": int(frame["c_positive_return"].sum()),
        "a50_positive_count": int(frame["a50_positive_return"].sum()),
        "c_dd30_fail_count": int(frame["c_dd30_fail"].sum()),
        "a50_dd30_fail_count": int(frame["a50_dd30_fail"].sum()),
        "c_dd40_fail_count": int(frame["c_dd40_fail"].sum()),
        "a50_dd40_fail_count": int(frame["a50_dd40_fail"].sum()),
        "median_return_delta_pct": float(ret_delta.median()),
        "p10_return_delta_pct": float(ret_delta.quantile(0.10)),
        "median_return_retention_pct": float(retention.median()),
        "median_dd_delta_pp": float(dd_delta.median()),
        "worst_dd_delta_pp": float(dd_delta.min()),
        "best_dd_delta_pp": float(dd_delta.max()),
        "reserve_used_count": int(reserve_deployed.gt(0.0).sum()),
        "median_reserve_deployed": float(reserve_deployed.median()),
        "max_reserve_deployed": float(reserve_deployed.max()),
        "worst_return_delta_start": str(frame.loc[ret_delta.idxmin(), "start_month"]),
        "best_return_delta_start": str(frame.loc[ret_delta.idxmax(), "start_month"]),
    }


def _checks(comparison: pd.DataFrame) -> pd.DataFrame:
    rows = [
        _bucket_stats("all_monthly_starts", comparison),
        _bucket_stats("mature_ge63_trading_days", comparison[comparison["mature_63d"].eq(1)]),
        _bucket_stats("mature_ge126_trading_days", comparison[comparison["mature_126d"].eq(1)]),
        _bucket_stats("mature_ge252_trading_days", comparison[comparison["mature_252d"].eq(1)]),
    ]
    for year, group in comparison.groupby("start_year", sort=True):
        rows.append(_bucket_stats(f"start_year_{int(year)}", group))
    focus = comparison[comparison["start_month"].eq("2022-05")]
    if not focus.empty:
        row = focus.iloc[0]
        rows.append(
            {
                "bucket": "focus_2022_05",
                "start_count": 1,
                "c_return_win_count": int(row["c_return_wins"]),
                "c_dd_win_count": int(row["c_dd_wins"]),
                "median_return_delta_pct": float(row["return_delta_pct"]),
                "median_return_retention_pct": float(row["return_retention_pct"]),
                "median_dd_delta_pp": float(row["dd_delta_pp"]),
                "reserve_used_count": int(float(row["c_reserve_deployed_end"]) > 0.0),
                "median_reserve_deployed": float(row["c_reserve_deployed_end"]),
                "max_reserve_deployed": float(row["c_reserve_deployed_end"]),
            }
        )
    return pd.DataFrame(rows)


def _decision(comparison: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    mature = checks[checks["bucket"].eq("mature_ge252_trading_days")].iloc[0]
    all_row = checks[checks["bucket"].eq("all_monthly_starts")].iloc[0]
    focus = comparison[comparison["start_month"].eq("2022-05")]
    focus_row = focus.iloc[0] if not focus.empty else None
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(mature["c_return_win_count"]) < int(mature["start_count"]) * 0.45:
        hard_fail.append("mature252_c_return_wins_lt45pct")
    if float(mature["median_return_delta_pct"]) < 0.0:
        hard_fail.append("mature252_median_return_delta_negative")
    if int(mature["c_dd40_fail_count"]) > int(mature["a50_dd40_fail_count"]):
        watch.append("mature252_c_dd40_fail_more_than_a50")
    if int(all_row["c_both_return_dd_win_count"]) <= int(all_row["a50_both_return_dd_win_count"]):
        watch.append("all_c_both_wins_not_more_than_a50_both_wins")
    if focus_row is not None and float(focus_row["return_delta_pct"]) <= 0.0:
        watch.append("focus_2022_05_not_repaired_vs_a50")
    decision = "cash_reserve_bucket_not_promoted" if hard_fail else "cash_reserve_bucket_watch"
    return {
        "stage": "Stage440",
        "script_stage": "Stage751",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_a50": s750.A50_VARIANT,
        "candidate": CASH_RESERVE_VARIANT,
        "analysis_start_first": _selected_month_starts()[0].strftime("%Y-%m-%d"),
        "analysis_start_last": _selected_month_starts()[-1].strftime("%Y-%m-%d"),
        "analysis_end": ANALYSIS_END.strftime("%Y-%m-%d"),
        "monthly_start_count": len(comparison),
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "a50_account_capital": TOTAL_CAPITAL,
            "a50_c3_capital": TOTAL_CAPITAL,
            "candidate_total_capital": TOTAL_CAPITAL,
            "candidate_trading_bucket_capital": TRADING_BUCKET_CAPITAL,
            "candidate_reserve_capital": RESERVE_CAPITAL,
            "risk_multiplier": 0.80,
            "loss_streak_and_recovery_sleeve_enabled": True,
        },
        "checks": checks.to_dict("records"),
        "focus_2022_05": focus_row.to_dict() if focus_row is not None else {},
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "candidate_summary": str(CANDIDATE_SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "curves": str(CURVES_PATH),
            "reserve_events": str(RESERVE_EVENTS_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "heatmap": str(HEATMAP_PATH),
            "focus_202205": str(FOCUS_202205_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot_main(comparison: pd.DataFrame) -> None:
    data = comparison.sort_values("start_ts").copy()
    x = np.arange(len(data))
    labels = data["start_month"].tolist()
    tick_idx = [idx for idx, label in enumerate(labels) if label.endswith("-01") or idx == len(labels) - 1]

    fig, axes = plt.subplots(5, 1, figsize=(18, 16), sharex=True)
    ax_ret, ax_delta, ax_dd, ax_reserve, ax_margin = axes
    ax_ret.plot(x, data["a50_rebased_total_return_pct"], color="#ea580c", linewidth=1.8, label="A50 official return")
    ax_ret.plot(x, data["c_rebased_total_return_pct"], color="#059669", linewidth=1.8, label="C reserve-bucket return")
    ax_ret.axhline(0.0, color="#111827", linewidth=0.8)
    ax_ret.set_ylabel("Total return %")
    ax_ret.set_title("Monthly independent starts to 2026-04-30: total return")
    ax_ret.grid(axis="y", alpha=0.25)
    ax_ret.legend(loc="upper right")

    colors = np.where(data["return_delta_pct"] >= 0.0, "#059669", "#dc2626")
    ax_delta.bar(x, data["return_delta_pct"], color=colors, alpha=0.88, width=0.82)
    ax_delta.axhline(0.0, color="#111827", linewidth=0.9)
    ax_delta.set_ylabel("C - A50 return pp")
    ax_delta.set_title("Return difference: green means reserve bucket beats A50")
    ax_delta.grid(axis="y", alpha=0.22)

    ax_dd.plot(x, data["a50_rebased_max_dd_pct"], color="#ea580c", linewidth=1.7, label="A50 max DD")
    ax_dd.plot(x, data["c_rebased_max_dd_pct"], color="#059669", linewidth=1.7, label="C max DD")
    ax_dd.axhline(-30.0, color="#f97316", linestyle="--", linewidth=0.9, label="DD -30%")
    ax_dd.axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.9, label="DD -40%")
    ax_dd.set_ylabel("Max DD %")
    ax_dd.set_title("Account-level max drawdown by start month")
    ax_dd.grid(axis="y", alpha=0.25)
    ax_dd.legend(loc="lower right", ncol=2)

    ax_reserve.bar(x, data["c_reserve_deployed_end"], color="#2563eb", alpha=0.82, width=0.82)
    ax_reserve.axhline(RESERVE_CAPITAL, color="#64748b", linestyle="--", linewidth=0.9)
    ax_reserve.set_ylabel("Reserve used")
    ax_reserve.set_title("Reserve deployed by end of each independent start")
    ax_reserve.grid(axis="y", alpha=0.22)

    ax_margin.plot(
        x,
        data["a50_max_broker10_margin_to_rebased_equity_pct"],
        color="#ea580c",
        linewidth=1.6,
        label="A50 account margin peak",
    )
    ax_margin.plot(
        x,
        data["c_max_broker10_margin_to_rebased_equity_pct"],
        color="#059669",
        linewidth=1.6,
        label="C account margin peak",
    )
    ax_margin.plot(
        x,
        data["c_max_broker10_margin_to_bucket_equity_pct"],
        color="#2563eb",
        linewidth=1.2,
        linestyle="--",
        label="C bucket margin peak",
    )
    ax_margin.axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9)
    ax_margin.set_ylabel("Broker10 margin %")
    ax_margin.set_title("Margin pressure: account level vs active trading bucket")
    ax_margin.grid(axis="y", alpha=0.22)
    ax_margin.legend(loc="upper right", ncol=3)
    ax_margin.set_xticks(tick_idx)
    ax_margin.set_xticklabels([labels[i] for i in tick_idx], rotation=45, ha="right")

    mature = data[data["mature_252d"].eq(1)]
    fig.suptitle(
        (
            "Stage751 cash reserve bucket vs Stage750 A50 | "
            f"C return wins {int(data['c_return_wins'].sum())}/{len(data)}, "
            f"mature wins {int(mature['c_return_wins'].sum())}/{len(mature)}, "
            f"median reserve used {data['c_reserve_deployed_end'].median():,.0f}"
        ),
        fontsize=15,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _heat_values(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        frame.pivot_table(index="start_year", columns="start_month_num", values=column, aggfunc="first")
        .sort_index()
        .reindex(columns=list(range(1, 13)))
    )


def _plot_heatmap(comparison: pd.DataFrame) -> None:
    tables = [
        (_heat_values(comparison, "c_rebased_total_return_pct"), "C reserve-bucket total return %", "Return %", "{:.0f}"),
        (_heat_values(comparison, "return_delta_pct"), "C - A50 total return pp", "Return pp", "{:.0f}"),
        (_heat_values(comparison, "c_reserve_deployed_end"), "C reserve deployed by end", "Reserve", "{:.0f}"),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(17, 12))
    for ax, table, title, cbar_label, fmt in zip(axes, *zip(*tables)):
        values = table.to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if "C - A50" in title:
            limit = max(float(np.nanpercentile(np.abs(finite), 90)), 1.0) if finite.size else 1.0
            norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
            cmap = "RdYlGn"
        elif "reserve" in title.lower():
            norm = None
            cmap = "Blues"
        else:
            norm = TwoSlopeNorm(vmin=-100.0, vcenter=0.0, vmax=max(float(np.nanmax(finite)), 100.0) if finite.size else 100.0)
            cmap = "RdYlGn"
        image = ax.imshow(values, aspect="auto", cmap=cmap, norm=norm)
        ax.set_title(title)
        ax.set_yticks(np.arange(len(table.index)))
        ax.set_yticklabels([str(int(item)) for item in table.index])
        ax.set_xticks(np.arange(12))
        ax.set_xticklabels([str(i) for i in range(1, 13)])
        ax.set_xlabel("Start month")
        ax.set_ylabel("Start year")
        for y in range(values.shape[0]):
            for x in range(values.shape[1]):
                value = values[y, x]
                if not np.isfinite(value):
                    continue
                ax.text(x, y, fmt.format(value), ha="center", va="center", fontsize=8, color="#111827")
        fig.colorbar(image, ax=ax, fraction=0.018, pad=0.01, label=cbar_label)
    fig.suptitle("Stage751 monthly-start heatmaps", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(HEATMAP_PATH, dpi=170)
    plt.close(fig)


def _plot_focus_202205(curves: pd.DataFrame) -> None:
    data = curves[curves["start_month"].astype(str).eq("2022-05")].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    for arm, color, label in [(A50_ARM, "#ea580c", "A50 official"), (C_ARM, "#059669", "C reserve bucket")]:
        frame = data[data["arm"].astype(str).eq(arm)].sort_values("date")
        if frame.empty:
            continue
        axes[0].plot(frame["date"], frame["account_equity"], color=color, linewidth=1.8, label=label)
        axes[1].plot(frame["date"], frame["drawdown_pct"], color=color, linewidth=1.5, label=label)
    c_frame = data[data["arm"].astype(str).eq(C_ARM)].sort_values("date")
    if not c_frame.empty:
        axes[2].plot(c_frame["date"], c_frame["trading_bucket_equity"], color="#2563eb", linewidth=1.5, label="C trading bucket equity")
        axes[2].plot(c_frame["date"], c_frame["reserve_remaining"], color="#7c3aed", linewidth=1.5, label="C reserve remaining")
        axes[2].fill_between(
            c_frame["date"],
            0,
            c_frame["reserve_injection_cumsum"],
            color="#bfdbfe",
            alpha=0.45,
            label="C reserve deployed",
        )
    axes[0].axhline(TOTAL_CAPITAL, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("Account equity")
    axes[0].set_title("2022-05 independent start: account equity")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(loc="upper left")
    axes[1].axhline(-30.0, color="#f97316", linestyle="--", linewidth=0.8)
    axes[1].axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("Drawdown %")
    axes[1].set_title("2022-05 independent start: account drawdown")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend(loc="lower left")
    axes[2].axhline(TRADING_BUCKET_CAPITAL, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("Bucket / reserve")
    axes[2].set_title("C reserve bucket mechanics")
    axes[2].grid(axis="y", alpha=0.25)
    axes[2].legend(loc="upper left", ncol=3)
    fig.suptitle("Stage751 focus: 2022-05 start", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FOCUS_202205_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    candidate: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    checks: pd.DataFrame,
    reserve_events: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    columns = [
        "start_month",
        "trading_days",
        "a50_nav_end",
        "c_nav_end",
        "a50_rebased_total_return_pct",
        "c_rebased_total_return_pct",
        "return_delta_pct",
        "return_retention_pct",
        "a50_rebased_max_dd_pct",
        "c_rebased_max_dd_pct",
        "dd_delta_pp",
        "a50_rebased_sharpe",
        "c_rebased_sharpe",
        "sharpe_delta",
        "a50_total_trade_count",
        "c_total_trade_count",
        "trade_count_delta",
        "c_reserve_deployed_end",
        "c_reserve_topup_count",
        "c_first_reserve_topup_date",
    ]
    reserve_cols = [
        "requested_start_month",
        "date",
        "estimated_equity_before",
        "injection",
        "estimated_equity_after",
        "reserve_remaining_after",
        "topup_count",
    ]
    lines = [
        "# Stage440 / Script751 现金备用桶逐月启动验证",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- A50：`{s750.A50_VARIANT}`，复用或重跑 Stage750 A50。",
        f"- C：`{CASH_RESERVE_VARIANT}`，正式逻辑不变，总资金 50万，交易桶 40万，备用桶 10万。",
        f"- 起点范围：`{_selected_month_starts()[0].strftime('%Y-%m')}` 至 `{_selected_month_starts()[-1].strftime('%Y-%m')}`，共 `{len(comparison)}` 个逐月独立启动；统一终点 `{ANALYSIS_END.strftime('%Y-%m-%d')}`。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- 固定比例/固定风险 sizing 的第一性原理是账户权益、风险比例和止损距离共同决定手数；冷启动亏损会机械降低后续风险预算。",
        "- 资金分层/备用金更像 capital allocation 和 path-risk 管理，不是 alpha；必须用多起点 walk-forward 看是否降低路径依赖，而不能只看单一路径。",
        "- 本阶段只验证一个预声明结构，不扫备用比例，降低参数过拟合风险。",
        "",
        "## 检查聚合",
        "",
        _md_table(checks, max_rows=40),
        "",
        "## 2022-05 重点起点",
        "",
        _md_table(comparison[comparison["start_month"].eq("2022-05")][columns], max_rows=5),
        "",
        "## 最伤收益的起点",
        "",
        _md_table(comparison.sort_values("return_delta_pct").head(15)[columns], max_rows=15),
        "",
        "## 收益相对最好的起点",
        "",
        _md_table(comparison.sort_values("return_delta_pct", ascending=False).head(15)[columns], max_rows=15),
        "",
        "## 全部月起点明细",
        "",
        _md_table(comparison[columns], max_rows=90),
        "",
        "## C 成本压力",
        "",
        _md_table(cost, max_rows=90),
        "",
        "## 备用桶事件样例",
        "",
        _md_table(reserve_events[reserve_cols].head(60) if not reserve_events.empty else reserve_events, max_rows=60),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
        "",
        "## 输出",
        "",
        f"- chart：`{CHART_PATH}`",
        f"- heatmap：`{HEATMAP_PATH}`",
        f"- focus_202205：`{FOCUS_202205_PATH}`",
        f"- comparison：`{COMPARISON_PATH}`",
        f"- reserve_events：`{RESERVE_EVENTS_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    a50, a50_curves = _load_a50_monthly()
    candidate, cost, candidate_curves, reserve_events = _run_cash_reserve_monthly()
    comparison = _build_comparison(a50, candidate)
    checks = _checks(comparison)
    decision = _decision(comparison, checks)

    summary = pd.concat([a50, candidate], ignore_index=True, sort=False)
    curves = pd.concat([a50_curves, candidate_curves], ignore_index=True, sort=False)
    _plot_main(comparison)
    _plot_heatmap(comparison)
    _plot_focus_202205(curves)
    _write_report(summary, candidate, cost, comparison, checks, reserve_events, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate.to_csv(CANDIDATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    reserve_events.to_csv(RESERVE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

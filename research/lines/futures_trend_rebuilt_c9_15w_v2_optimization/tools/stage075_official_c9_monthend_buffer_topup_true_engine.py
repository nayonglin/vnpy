from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
import itertools
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from vnpy_portfoliostrategy.backtesting import PortfolioDailyResult


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
UPSTREAM_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
for candidate in (str(PORTFOLIO_DIR), str(UPSTREAM_TOOLS_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit as s167
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage075"
MODEL_TAG = "stage075_official_c9_monthend_buffer_topup_true_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage075_official_c9_monthend_buffer_topup_true_engine"

REQUESTED_START = pd.Timestamp("2020-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTHS = (1, 7)
BASE_TRADING_CAPITAL = float(OFFICIAL_LIVE_CAPITAL)
RESERVE_CAPITAL = 150_000.0
TOTAL_ACCOUNT_CAPITAL = BASE_TRADING_CAPITAL + RESERVE_CAPITAL

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage075_official_c9_monthend_buffer_topup_true_engine"
STAGES_DIR = LINE_DIR / "stages"
STAGE167_OUT = PORTFOLIO_DIR / "backtest_outputs"

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_vs_official_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
RAW_COMBINED_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_raw_combined_{MODEL_TAG}.csv.gz"
ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_candidates_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trades_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trade_events_{MODEL_TAG}.csv.gz"
CASHFLOW_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_cashflow_events_{MODEL_TAG}.csv"
DAILY_ACCOUNTING_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_daily_accounting_{MODEL_TAG}.csv.gz"
AI_MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_ai_month_audit_{MODEL_TAG}.csv"
ACCOUNTING_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_accounting_audit_{MODEL_TAG}.csv"
CHART_EQUITY_PATH = OUT / f"{OUTPUT_PREFIX}_equity_recent_starts_{MODEL_TAG}.png"
CHART_RETURN_DD_PATH = OUT / f"{OUTPUT_PREFIX}_return_dd_by_start_{MODEL_TAG}.png"
CHART_UNDERWATER_PATH = OUT / f"{OUTPUT_PREFIX}_underwater_by_start_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

STAGE167_CURVES_PATH = (
    STAGE167_OUT / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)

OFFICIAL_VERSION = "official_c9_15w_reference"
CANDIDATE_VERSION = "monthend_buffer_topup_true_engine"
VARIANTS = (OFFICIAL_VERSION, CANDIDATE_VERSION)
VARIANT_LABELS = {
    OFFICIAL_VERSION: "Official C9 15w reference",
    CANDIDATE_VERSION: "Month-end buffer top-up true engine",
}
VARIANT_COLORS = {
    OFFICIAL_VERSION: "#111827",
    CANDIDATE_VERSION: "#059669",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, str | bytes):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _naive_day(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)
    return timestamp.normalize()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _max_consecutive_true(mask: pd.Series) -> int:
    runs = (len(list(group)) for value, group in itertools.groupby(mask.astype(bool).tolist()) if value)
    return int(max(runs, default=0))


def _build_start_dates() -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    latest_start = pd.Timestamp("2026-01-01")
    for year in range(REQUESTED_START.year, REQUESTED_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= min(REQUESTED_END, latest_start):
                starts.append(start)
    return starts


class QmtRollPortfolioStrategyStage075MonthEndBufferTopup(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage075_monthend_buffer_topup: bool = False
    stage075_initial_reserve_capital: float = 0.0
    stage075_base_trading_capital: float = BASE_TRADING_CAPITAL
    stage075_topup_floor_equity: float = BASE_TRADING_CAPITAL
    stage075_topup_min_amount: float = 1.0

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage075_monthend_buffer_topup",
        "stage075_initial_reserve_capital",
        "stage075_base_trading_capital",
        "stage075_topup_floor_equity",
        "stage075_topup_min_amount",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage075_external_cashflow_cumulative",
        "stage075_reserve_remaining",
        "stage075_topup_count",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        reserve = max(0.0, float(getattr(self, "stage075_initial_reserve_capital", 0.0) or 0.0))
        self.stage075_external_cashflow_cumulative: float = 0.0
        self.stage075_reserve_remaining: float = reserve
        self.stage075_topup_count: int = 0
        self.stage075_cashflow_events: list[dict[str, Any]] = []
        self.stage075_daily_accounting: list[dict[str, Any]] = []
        self.stage075_strategy_equity_for_sizing: float = self.base_capital
        self.stage075_broker_equity_for_sizing: float = self.base_capital
        self.stage075_ledger_pre_closes: dict[str, float] = {}
        self.stage075_ledger_start_poses: dict[str, float] = {}
        self.stage075_last_accounted_date: pd.Timestamp | None = None

    def _stage075_enabled(self) -> bool:
        return bool(self.enable_stage075_monthend_buffer_topup) and float(self.stage075_initial_reserve_capital or 0.0) > 0.0

    def _stage075_floor(self) -> float:
        floor = float(self.stage075_topup_floor_equity or 0.0)
        if floor <= 0.0:
            floor = float(self.stage075_base_trading_capital or self.base_capital or 0.0)
        return max(0.0, floor)

    def _stage075_set_broker_equity_from_strategy(self, strategy_equity: float) -> None:
        self.stage075_strategy_equity_for_sizing = float(strategy_equity or 0.0)
        self.stage075_broker_equity_for_sizing = max(
            0.0,
            self.stage075_strategy_equity_for_sizing + float(self.stage075_external_cashflow_cumulative or 0.0),
        )

    @contextmanager
    def _stage075_broker_equity_context(self):
        original_equity = self.estimated_equity
        try:
            if self._stage075_enabled():
                self.estimated_equity = max(
                    0.0,
                    float(self.stage075_broker_equity_for_sizing or original_equity or self.base_capital or 0.0),
                )
            yield
        finally:
            self.estimated_equity = original_equity

    def _stage075_is_month_end_release_day(self) -> bool:
        if self.current_bar_date is None:
            return False
        current = _naive_day(self.current_bar_date)
        dates = pd.DatetimeIndex([_naive_day(item) for item in getattr(self, "available_trade_dates", [])])
        if dates.empty:
            return False
        index = dates.searchsorted(current, side="left")
        if index >= len(dates) or dates[index] != current:
            return False
        if index == len(dates) - 1:
            return True
        return pd.Timestamp(dates[index + 1]).to_period("M") != current.to_period("M")

    def _stage075_maybe_monthend_topup_after_close(self, strategy_equity: float | None = None) -> None:
        if strategy_equity is None:
            strategy_equity = float(self.stage075_strategy_equity_for_sizing or self.base_capital or 0.0)
        self._stage075_set_broker_equity_from_strategy(strategy_equity)
        if not self._stage075_enabled() or not self._stage075_is_month_end_release_day():
            return

        floor = self._stage075_floor()
        pre_broker_equity = float(self.stage075_broker_equity_for_sizing)
        reserve_before = max(0.0, float(self.stage075_reserve_remaining or 0.0))
        requested_topup = max(0.0, floor - pre_broker_equity)
        min_amount = max(0.0, float(self.stage075_topup_min_amount or 0.0))
        topup = min(reserve_before, requested_topup) if requested_topup >= min_amount else 0.0
        if topup <= 0.0:
            return

        self.stage075_external_cashflow_cumulative += topup
        self.stage075_reserve_remaining = max(0.0, reserve_before - topup)
        self.stage075_topup_count += 1
        post_broker_equity = max(0.0, strategy_equity + self.stage075_external_cashflow_cumulative)
        self.stage075_broker_equity_for_sizing = post_broker_equity
        current_date = self.current_bar_date
        self.stage075_cashflow_events.append(
            {
                "datetime": pd.Timestamp(current_date).to_pydatetime() if current_date is not None else "",
                "date": _date_text(current_date) if current_date is not None else "",
                "cashflow_type": "reserve_topup",
                "amount": topup,
                "strategy_equity_ex_cashflow_before": strategy_equity,
                "broker_equity_with_cashflow_before": pre_broker_equity,
                "broker_equity_with_cashflow_after": post_broker_equity,
                "external_cashflow_cumulative_after": self.stage075_external_cashflow_cumulative,
                "reserve_remaining_before": reserve_before,
                "reserve_remaining_after": self.stage075_reserve_remaining,
                "topup_floor_equity": floor,
                "reason": "month_end_after_close_broker_equity_below_floor",
            }
        )

    def _refresh_risk_state(self, bars: dict[str, Any]) -> None:
        if not self._stage075_enabled():
            super()._refresh_risk_state(bars)
            return
        with self._stage075_broker_equity_context():
            super()._refresh_risk_state(bars)
        broker_equity = max(0.0, float(self.stage075_broker_equity_for_sizing or self.base_capital or 0.0))
        self.portfolio_equity_high_water = max(
            float(self.portfolio_equity_high_water or self.base_capital),
            broker_equity,
            float(self.base_capital),
        )
        if self.portfolio_equity_high_water > 0:
            self.portfolio_drawdown_pct = max(
                0.0,
                (self.portfolio_equity_high_water - broker_equity) / self.portfolio_equity_high_water,
            )
        self._refresh_portfolio_margin_deleverage_state()
        self.risk_cluster_heat_gate_weight = self._current_min_risk_cluster_heat_gate_weight()
        limited_balance = self._limited_available_balance()
        self.current_risk_per_trade = self._risk_amount_from_ratio(self.risk_ratio_of_total_assets, limited_balance)

    def _sizing_equity_snapshot(self) -> dict[str, float | int]:
        if not self._stage075_enabled():
            return super()._sizing_equity_snapshot()
        with self._stage075_broker_equity_context():
            fields = dict(super()._sizing_equity_snapshot())
        fields.update(
            {
                "stage075_monthend_buffer_topup_enabled": 1,
                "stage075_initial_reserve_capital": float(self.stage075_initial_reserve_capital or 0.0),
                "stage075_external_cashflow_cumulative": float(self.stage075_external_cashflow_cumulative or 0.0),
                "stage075_reserve_remaining": float(self.stage075_reserve_remaining or 0.0),
                "stage075_strategy_equity_ex_cashflow": float(self.stage075_strategy_equity_for_sizing or 0.0),
                "stage075_broker_equity_for_sizing": float(self.stage075_broker_equity_for_sizing or 0.0),
                "stage075_topup_floor_equity": self._stage075_floor(),
            }
        )
        return fields

    def _calculate_entry_sizing(
        self,
        vt_symbol: str,
        direction: str,
        bar: Any,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        risk_mode_override: str | None = None,
        entry_context: str = "flat_entry",
        apply_env_gate: bool = True,
        active_positions_before: int | None = None,
        correlation_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._stage075_enabled():
            return super()._calculate_entry_sizing(
                vt_symbol,
                direction,
                bar,
                history,
                signal_data,
                risk_mode_override=risk_mode_override,
                entry_context=entry_context,
                apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before,
                correlation_snapshot=correlation_snapshot,
            )
        with self._stage075_broker_equity_context():
            sizing = dict(
                super()._calculate_entry_sizing(
                    vt_symbol,
                    direction,
                    bar,
                    history,
                    signal_data,
                    risk_mode_override=risk_mode_override,
                    entry_context=entry_context,
                    apply_env_gate=apply_env_gate,
                    active_positions_before=active_positions_before,
                    correlation_snapshot=correlation_snapshot,
                )
            )
        sizing.update(
            {
                "stage075_monthend_buffer_topup_enabled": 1,
                "stage075_initial_reserve_capital": float(self.stage075_initial_reserve_capital or 0.0),
                "stage075_external_cashflow_cumulative": float(self.stage075_external_cashflow_cumulative or 0.0),
                "stage075_reserve_remaining": float(self.stage075_reserve_remaining or 0.0),
                "stage075_strategy_equity_ex_cashflow": float(self.stage075_strategy_equity_for_sizing or 0.0),
                "stage075_broker_equity_for_sizing": float(self.stage075_broker_equity_for_sizing or 0.0),
                "stage075_topup_floor_equity": self._stage075_floor(),
            }
        )
        return sizing

    def _refresh_portfolio_margin_deleverage_state(self) -> None:
        if not self._stage075_enabled():
            super()._refresh_portfolio_margin_deleverage_state()
            return
        with self._stage075_broker_equity_context():
            super()._refresh_portfolio_margin_deleverage_state()

    def _process_forced_margin_deleverage(self, bars: dict[str, Any]) -> None:
        if not self._stage075_enabled():
            super()._process_forced_margin_deleverage(bars)
            return
        with self._stage075_broker_equity_context():
            super()._process_forced_margin_deleverage(bars)

    def on_bars(self, bars: dict[str, Any]) -> None:
        super().on_bars(bars)
        if not self._stage075_enabled():
            return
        # Daily PnL/cashflow accounting is updated by the Stage075 engine after close prices
        # and same-day fills have been recorded. Reading estimated_equity here would capture
        # an unstable strategy-internal mark, not the portfolio backtest ledger.

    def stage075_after_engine_daily_close(self, dt: Any, bars: dict[str, Any], trades: dict[str, Any]) -> None:
        if not self._stage075_enabled() or not getattr(self, "trading", False):
            return
        current = _naive_day(dt)
        if self.stage075_last_accounted_date is not None and current <= self.stage075_last_accounted_date:
            return

        close_prices = {str(vt_symbol): float(bar.close_price) for vt_symbol, bar in bars.items() if bar is not None}
        day_trades = [
            trade
            for trade in trades.values()
            if _naive_day(getattr(trade, "datetime", dt)) == current
        ]
        for trade in day_trades:
            if trade.vt_symbol not in close_prices:
                close_prices[trade.vt_symbol] = float(trade.price)

        daily_result = PortfolioDailyResult(current.date(), close_prices)
        for trade in day_trades:
            daily_result.add_trade(trade)
        engine = self.strategy_engine
        daily_result.calculate_pnl(
            self.stage075_ledger_pre_closes,
            self.stage075_ledger_start_poses,
            getattr(engine, "sizes", {}),
            getattr(engine, "rates", {}),
            getattr(engine, "slippages", {}),
        )
        self.stage075_ledger_pre_closes = dict(daily_result.close_prices)
        self.stage075_ledger_start_poses = dict(daily_result.end_poses)
        strategy_equity = float(self.stage075_strategy_equity_for_sizing or self.base_capital or 0.0) + float(
            daily_result.net_pnl or 0.0
        )
        self.current_bar_date = current
        self._stage075_maybe_monthend_topup_after_close(strategy_equity)

        broker_equity = max(0.0, float(self.stage075_broker_equity_for_sizing or 0.0))
        reserve_remaining = max(0.0, float(self.stage075_reserve_remaining or 0.0))
        total_account_equity = strategy_equity + float(self.stage075_initial_reserve_capital or 0.0)
        self.stage075_daily_accounting.append(
            {
                "date": _date_text(current),
                "strategy_equity_ex_cashflow": strategy_equity,
                "broker_equity_with_cashflow": broker_equity,
                "reserve_remaining": reserve_remaining,
                "external_cashflow_cumulative": float(self.stage075_external_cashflow_cumulative or 0.0),
                "total_account_equity": total_account_equity,
                "topup_count": int(self.stage075_topup_count),
                "active_count": int(self.active_count),
                "total_margin_in_use": float(self.total_margin_in_use or 0.0),
                "portfolio_drawdown_pct_ex_cashflow": float(self.portfolio_drawdown_pct or 0.0),
                "broker_equity_for_sizing": float(self.stage075_broker_equity_for_sizing or 0.0),
                "daily_net_pnl": float(daily_result.net_pnl or 0.0),
                "daily_trade_count": int(daily_result.trade_count or 0),
            }
        )
        self.stage075_last_accounted_date = current


class Stage075MonthEndBufferTopupEngine(s847.Stage847StopRetryEngine):
    def new_bars(self, dt: datetime) -> None:
        super().new_bars(dt)
        strategy = getattr(self, "strategy", None)
        hook = getattr(strategy, "stage075_after_engine_daily_close", None)
        if hook and getattr(strategy, "inited", False):
            hook(dt, dict(getattr(self, "bars", {}) or {}), dict(getattr(self, "trades", {}) or {}))


def _stage075_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    profile_name = "stage075_official_c9_30w_monthend_buffer_topup"
    capital = replace(
        spec.capital,
        variant=profile_name,
        label="Stage075 official C9 30w account, 15w trading sleeve, month-end buffer top-up",
        account_capital=BASE_TRADING_CAPITAL,
        c3_capital=BASE_TRADING_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage075 keeps total account capital at 300,000 from day one; "
            "15w starts as trading sleeve and 15w starts as reserve. At month-end after close, reserve "
            "is transferred only if broker sizing equity is below 150,000. Transfer is internal cashflow, "
            "not alpha PnL."
        ),
    )
    overrides = {
        **spec.overrides,
        **s901.build_official_live_strategy_overrides(),
        "enable_stage075_monthend_buffer_topup": True,
        "stage075_initial_reserve_capital": RESERVE_CAPITAL,
        "stage075_base_trading_capital": BASE_TRADING_CAPITAL,
        "stage075_topup_floor_equity": BASE_TRADING_CAPITAL,
        "stage075_topup_min_amount": 1.0,
    }
    result = dict(profile)
    result["profile"] = profile_name
    result["strategy_cls"] = QmtRollPortfolioStrategyStage075MonthEndBufferTopup
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=profile_name)
    return result


def _run_profile(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s847.s827.s778.s653.s517.START_DT
    original_end = s847.s827.s778.s653.s517.END_DT
    original_preload = s847.s827.s778.s653.s517.PRELOAD_START_DT
    try:
        s847.s827.s778.s653.s517.START_DT = s847.START.to_pydatetime()
        s847.s827.s778.s653.s517.END_DT = s847.END.to_pydatetime()
        s847.s827.s778.s653.s517.PRELOAD_START_DT = s847.s827.s772._preload_for_start(s847.START).to_pydatetime()
        s847.s827.s778.s653.s517.assert_stage196_database_sentinels()
        s847.s827.s778.s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(
            s847.s827.s778.s653.s517.PRELOAD_START_DT,
            s847.s827.s778.s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta(),
        )
        _, open_map = s847.s827.s778.s653.s517.s506.s501._seed_proxy_maps()
        engine = Stage075MonthEndBufferTopupEngine(open_map)
        engine.output = lambda msg: print(f"[stage075-engine] {msg}") if "异常" in str(msg) or "Traceback" in str(msg) else None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s847.s827.Interval.DAILY,
            start=preload_start,
            end=s847.s827.s778.s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s847.s827.s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=dict(s847.s513._c3_overrides(s847.START.to_pydatetime())),
            start=s847.START,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            daily_df = pd.DataFrame(
                [{"net_pnl": 0.0, "trade_count": 0.0, "slippage": 0.0, "commission": 0.0, "turnover": 0.0}],
                index=pd.Index([s847.END.date()], name="date"),
            )
        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= s847.START.date()) & (daily.index <= s847.END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        positions = s847.s827.s778.build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            margin_daily, _ = s847.s513._position_margin(positions, metadata)
        else:
            margin_daily = pd.DataFrame(
                columns=["variant", "combo_variant", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            )
        combined = s847.s827.s772._combine_daily(daily, margin_daily, spec)
        strategy = getattr(engine, "strategy", None)
        c2_events = pd.DataFrame(getattr(strategy, "stage827_intraday_c2_events", []) if strategy else [])
        stop_retry_events = pd.DataFrame(getattr(strategy, "stage847_stop_retry_events", []) if strategy else [])
        if not stop_retry_events.empty and "synthetic_trades" in stop_retry_events.columns:
            stop_retry_events = stop_retry_events.drop(columns=["synthetic_trades"])
        intraday_events = pd.concat([c2_events, stop_retry_events], ignore_index=True, sort=False)
        frames = {
            "trades": s847.s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s847.s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s847.s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "pending_orders": s847._active_limit_orders_frame(engine),
            "cashflow_events": pd.DataFrame(getattr(strategy, "stage075_cashflow_events", []) if strategy else []),
            "daily_accounting": pd.DataFrame(getattr(strategy, "stage075_daily_accounting", []) if strategy else []),
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["start_month"] = s847.START.strftime("%Y-%m")
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s847.s827.s778.s653.s517.START_DT = original_start
        s847.s827.s778.s653.s517.END_DT = original_end
        s847.s827.s778.s653.s517.PRELOAD_START_DT = original_preload


def _run_stage075(metadata: dict[str, Any], analysis_start: pd.Timestamp, analysis_end: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s847.START
    original_end = s847.END
    original_minute_by_symbol = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s901._ensure_c9_minute_bars(metadata)
    try:
        s847.START = analysis_start.normalize()
        s847.END = analysis_end.normalize()
        profile = _stage075_profile(metadata)
        combined, frames = _run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol
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


def _read_official_curves() -> pd.DataFrame:
    frame = pd.read_csv(STAGE167_CURVES_PATH)
    frame = frame[frame["requested_start_month"].astype(str).isin([_start_month_text(item) for item in _build_start_dates()])].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[pd.to_datetime(frame["date"], errors="coerce").le(REQUESTED_END)].copy()
    frame["version"] = OFFICIAL_VERSION
    frame["variant_label"] = VARIANT_LABELS[OFFICIAL_VERSION]
    frame["account_capital_for_metrics"] = BASE_TRADING_CAPITAL
    frame["account_equity_for_metrics"] = pd.to_numeric(frame["account_equity"], errors="coerce")
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    frame["line_id"] = LINE_ID
    return frame


def _candidate_curve(combined: pd.DataFrame, daily_accounting: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    frame = combined.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    accounting = daily_accounting.copy()
    if not accounting.empty:
        accounting["date"] = pd.to_datetime(accounting["date"], errors="coerce").dt.normalize()
        accounting = accounting.dropna(subset=["date"])
        keep = [
            "date",
            "strategy_equity_ex_cashflow",
            "broker_equity_with_cashflow",
            "reserve_remaining",
            "external_cashflow_cumulative",
            "total_account_equity",
            "topup_count",
            "broker_equity_for_sizing",
        ]
        frame = frame.merge(accounting[[column for column in keep if column in accounting.columns]], on="date", how="left")
    frame["strategy_equity_ex_cashflow"] = pd.to_numeric(
        frame.get("strategy_equity_ex_cashflow", frame["account_equity"]), errors="coerce"
    ).fillna(pd.to_numeric(frame["account_equity"], errors="coerce"))
    frame["total_account_equity"] = pd.to_numeric(frame.get("total_account_equity"), errors="coerce")
    frame["total_account_equity"] = frame["total_account_equity"].fillna(frame["strategy_equity_ex_cashflow"] + RESERVE_CAPITAL)
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    frame["line_id"] = LINE_ID
    frame["version"] = CANDIDATE_VERSION
    frame["variant_label"] = VARIANT_LABELS[CANDIDATE_VERSION]
    frame["requested_start"] = _date_text(start)
    frame["requested_start_month"] = _start_month_text(start)
    frame["requested_end"] = _date_text(REQUESTED_END)
    frame["account_capital_for_metrics"] = TOTAL_ACCOUNT_CAPITAL
    frame["account_equity_for_metrics"] = frame["total_account_equity"]
    return frame


def _summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    frame = frame.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity_for_metrics"], errors="coerce").ffill()
    capital = float(frame["account_capital_for_metrics"].iloc[0])
    drawdown = _drawdown_pct(equity)
    below = equity < capital - 1e-9
    min_idx = int(equity.idxmin())
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": str(frame["version"].iloc[0]),
        "variant_label": str(frame["variant_label"].iloc[0]),
        "requested_start_month": str(frame["requested_start_month"].iloc[0]),
        "actual_start": _date_text(frame["date"].iloc[0]),
        "actual_end": _date_text(frame["date"].iloc[-1]),
        "trading_days": int(len(frame)),
        "account_capital": capital,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / capital - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min()),
        "sharpe": _daily_sharpe(equity),
        "min_equity": float(equity.iloc[min_idx]),
        "min_equity_date": _date_text(frame["date"].iloc[min_idx]),
        "days_below_initial": int(below.sum()),
        "max_consecutive_below_initial_days": _max_consecutive_true(below),
        "total_slippage": _safe_sum(frame, "slippage"),
        "total_trade_count": _safe_sum(frame, "trade_count"),
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(frame.get("broker10_margin_to_equity_pct", pd.Series(dtype=float)), errors="coerce").max()
        )
        if "broker10_margin_to_equity_pct" in frame.columns
        else np.nan,
    }


def _variant_summary(summary: pd.DataFrame) -> pd.DataFrame:
    official = summary[summary["version"].eq(OFFICIAL_VERSION)].set_index("requested_start_month")
    rows: list[dict[str, Any]] = []
    for version in VARIANTS:
        group = summary[summary["version"].eq(version)].copy()
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["max_drawdown_pct"], errors="coerce")
        days = pd.to_numeric(group["days_below_initial"], errors="coerce")
        retention: list[float] = []
        for _, row in group.iterrows():
            start = str(row["requested_start_month"])
            if start in official.index and float(official.loc[start, "total_return_pct"]):
                retention.append(float(row["total_return_pct"] / official.loc[start, "total_return_pct"]))
        rows.append(
            {
                "version": version,
                "variant_label": VARIANT_LABELS[version],
                "start_count": int(len(group)),
                "positive_count": int(returns.gt(0).sum()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "min_return_retention_ratio": float(np.nanmin(retention)) if retention else np.nan,
                "median_return_retention_ratio": float(np.nanmedian(retention)) if retention else np.nan,
                "worst_drawdown_pct": float(dds.min()),
                "median_drawdown_pct": float(dds.median()),
                "max_days_below_initial": int(days.max()),
                "median_days_below_initial": float(days.median()),
                "max_consecutive_below_initial_days": int(
                    pd.to_numeric(group["max_consecutive_below_initial_days"], errors="coerce").max()
                ),
                "total_slippage_sum": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0.0).sum()),
                "total_trade_count_sum": float(
                    pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0.0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _retention(summary: pd.DataFrame) -> pd.DataFrame:
    official = summary[summary["version"].eq(OFFICIAL_VERSION)].set_index("requested_start_month")
    rows: list[dict[str, Any]] = []
    for _, row in summary[summary["version"].eq(CANDIDATE_VERSION)].iterrows():
        start = str(row["requested_start_month"])
        base = official.loc[start]
        rows.append(
            {
                "requested_start_month": start,
                "return_delta_pct": float(row["total_return_pct"] - base["total_return_pct"]),
                "return_retention_ratio": float(row["total_return_pct"] / base["total_return_pct"])
                if float(base["total_return_pct"])
                else np.nan,
                "drawdown_delta_pct": float(row["max_drawdown_pct"] - base["max_drawdown_pct"]),
                "days_below_delta": int(row["days_below_initial"] - base["days_below_initial"]),
                "max_consecutive_below_delta": int(
                    row["max_consecutive_below_initial_days"] - base["max_consecutive_below_initial_days"]
                ),
                "official_return_pct": float(base["total_return_pct"]),
                "candidate_return_pct": float(row["total_return_pct"]),
                "official_max_drawdown_pct": float(base["max_drawdown_pct"]),
                "candidate_max_drawdown_pct": float(row["max_drawdown_pct"]),
                "official_days_below_initial": int(base["days_below_initial"]),
                "candidate_days_below_initial": int(row["days_below_initial"]),
            }
        )
    return pd.DataFrame(rows)


def _accounting_audit(candidate_curves: pd.DataFrame, daily_accounting: pd.DataFrame) -> pd.DataFrame:
    if daily_accounting.empty:
        return pd.DataFrame()
    frame = candidate_curves[["requested_start_month", "date", "account_equity", "total_account_equity"]].copy()
    accounting = daily_accounting.copy()
    accounting["date"] = pd.to_datetime(accounting["date"], errors="coerce").dt.normalize()
    merged = frame.merge(
        accounting[
            [
                column
                for column in [
                    "requested_start_month",
                    "date",
                    "strategy_equity_ex_cashflow",
                    "external_cashflow_cumulative",
                    "reserve_remaining",
                    "total_account_equity",
                ]
                if column in accounting.columns
            ]
        ],
        on=["requested_start_month", "date"],
        how="left",
        suffixes=("_curve", "_accounting"),
    )
    merged["accounting_identity_residual"] = (
        pd.to_numeric(merged["strategy_equity_ex_cashflow"], errors="coerce")
        + pd.to_numeric(merged["external_cashflow_cumulative"], errors="coerce")
        + pd.to_numeric(merged["reserve_remaining"], errors="coerce")
        - pd.to_numeric(merged["total_account_equity_accounting"], errors="coerce")
    )
    return (
        merged.groupby("requested_start_month", dropna=False)
        .agg(
            rows=("date", "size"),
            max_abs_accounting_residual=("accounting_identity_residual", lambda s: float(pd.to_numeric(s, errors="coerce").abs().max())),
            min_reserve_remaining=("reserve_remaining", "min"),
            max_external_cashflow_cumulative=("external_cashflow_cumulative", "max"),
        )
        .reset_index()
    )


def build() -> dict[str, pd.DataFrame]:
    metadata = s847.s513._metadata()
    official_curves = _read_official_curves()
    candidate_curves: list[pd.DataFrame] = []
    raw_combined_frames: list[pd.DataFrame] = []
    entry_candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []
    cashflow_frames: list[pd.DataFrame] = []
    daily_accounting_frames: list[pd.DataFrame] = []

    starts = _build_start_dates()
    for index, start in enumerate(starts, start=1):
        print(f"[stage075] run {index}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = _run_stage075(metadata, start, REQUESTED_END)
        combined = combined.copy()
        combined["requested_start"] = _date_text(start)
        combined["requested_start_month"] = _start_month_text(start)
        combined["requested_end"] = _date_text(REQUESTED_END)
        raw_combined_frames.append(combined)
        daily_accounting = frames.get("daily_accounting", pd.DataFrame()).copy()
        if not daily_accounting.empty:
            daily_accounting["requested_start_month"] = _start_month_text(start)
            daily_accounting_frames.append(daily_accounting)
        candidate_curves.append(_candidate_curve(combined, daily_accounting, start))
        for name, target in (
            ("entry_candidates", entry_candidate_frames),
            ("trades", trade_frames),
            ("trade_events", trade_event_frames),
            ("cashflow_events", cashflow_frames),
        ):
            frame = frames.get(name, pd.DataFrame()).copy()
            if frame.empty:
                continue
            frame["stage"] = STAGE
            frame["model_tag"] = MODEL_TAG
            frame["line_id"] = LINE_ID
            frame["version"] = CANDIDATE_VERSION
            frame["requested_start"] = _date_text(start)
            frame["requested_start_month"] = _start_month_text(start)
            frame["requested_end"] = _date_text(REQUESTED_END)
            target.append(frame)

    candidate = pd.concat(candidate_curves, ignore_index=True, sort=False)
    raw_combined = pd.concat(raw_combined_frames, ignore_index=True, sort=False)
    entry_candidates = pd.concat(entry_candidate_frames, ignore_index=True, sort=False) if entry_candidate_frames else pd.DataFrame()
    trades = pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame()
    trade_events = pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame()
    cashflow_events = pd.concat(cashflow_frames, ignore_index=True, sort=False) if cashflow_frames else pd.DataFrame()
    daily_accounting = (
        pd.concat(daily_accounting_frames, ignore_index=True, sort=False) if daily_accounting_frames else pd.DataFrame()
    )
    curves = pd.concat([official_curves, candidate], ignore_index=True, sort=False)
    curves = curves.sort_values(["version", "requested_start_month", "date"]).reset_index(drop=True)
    summary = pd.DataFrame([_summarize_curve(group) for _, group in curves.groupby(["version", "requested_start_month"])])
    summary = summary.sort_values(["requested_start_month", "version"]).reset_index(drop=True)
    ai_month_audit = pd.DataFrame()
    if not entry_candidates.empty:
        pool, _pool_audit = s167._load_ai_pool()
        ai_month_audit = s167._ai_month_audit(entry_candidates, summary[summary["version"].eq(CANDIDATE_VERSION)], pool)
    return {
        "curves": curves,
        "summary": summary,
        "variant_summary": _variant_summary(summary),
        "retention": _retention(summary),
        "raw_combined": raw_combined,
        "entry_candidates": entry_candidates,
        "trades": trades,
        "trade_events": trade_events,
        "cashflow_events": cashflow_events,
        "daily_accounting": daily_accounting,
        "ai_month_audit": ai_month_audit,
        "accounting_audit": _accounting_audit(candidate, daily_accounting),
    }


def plot_outputs(results: dict[str, pd.DataFrame]) -> None:
    curves = results["curves"].copy()
    summary = results["summary"].copy()
    starts = sorted(summary["requested_start_month"].astype(str).unique())
    x = np.arange(len(starts))
    width = 0.35

    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    for offset, version in zip((-width / 2, width / 2), VARIANTS, strict=True):
        group = summary[summary["version"].eq(version)].set_index("requested_start_month").loc[starts]
        axes[0].bar(x + offset, group["total_return_pct"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
        axes[1].bar(x + offset, group["max_drawdown_pct"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
    axes[0].set_title("Terminal return by start")
    axes[0].set_ylabel("return %")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].set_title("Max drawdown by start")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(starts, rotation=45, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].legend(ncol=2)
    fig.savefig(CHART_RETURN_DD_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    for offset, version in zip((-width / 2, width / 2), VARIANTS, strict=True):
        group = summary[summary["version"].eq(version)].set_index("requested_start_month").loc[starts]
        axes[0].bar(x + offset, group["days_below_initial"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
        axes[1].bar(
            x + offset,
            group["max_consecutive_below_initial_days"],
            width=width,
            label=VARIANT_LABELS[version],
            color=VARIANT_COLORS[version],
        )
    axes[0].set_title("Total days below initial capital")
    axes[0].set_ylabel("days")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].set_title("Max consecutive days below initial capital")
    axes[1].set_ylabel("days")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(starts, rotation=45, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].legend(ncol=2)
    fig.savefig(CHART_UNDERWATER_PATH, dpi=160)
    plt.close(fig)

    focus_starts = [item for item in starts if item >= "2021-07"]
    fig, axes = plt.subplots(2, 1, figsize=(18, 12), sharex=True, constrained_layout=True)
    for ax, version in zip(axes, VARIANTS, strict=True):
        subset = curves[curves["version"].eq(version) & curves["requested_start_month"].astype(str).isin(focus_starts)]
        for start, group in subset.groupby("requested_start_month", sort=True):
            group = group.sort_values("date")
            ax.plot(group["date"], group["account_equity_for_metrics"], linewidth=1.0, alpha=0.8, label=str(start))
        capital = BASE_TRADING_CAPITAL if version == OFFICIAL_VERSION else TOTAL_ACCOUNT_CAPITAL
        ax.axhline(capital, color="#6b7280", linestyle="--", linewidth=0.9)
        ax.set_title(VARIANT_LABELS[version])
        ax.set_ylabel("account equity")
        ax.grid(True, alpha=0.25)
        ax.legend(ncol=5, fontsize=8)
    axes[-1].set_xlabel("date")
    fig.savefig(CHART_EQUITY_PATH, dpi=160)
    plt.close(fig)


def write_outputs(results: dict[str, pd.DataFrame]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    results["curves"].to_csv(CURVES_PATH, index=False, compression="gzip")
    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["retention"].to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    results["raw_combined"].to_csv(RAW_COMBINED_PATH, index=False, compression="gzip")
    results["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, compression="gzip")
    results["trades"].to_csv(TRADES_PATH, index=False, compression="gzip")
    results["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, compression="gzip")
    results["cashflow_events"].to_csv(CASHFLOW_EVENTS_PATH, index=False, encoding="utf-8-sig")
    results["daily_accounting"].to_csv(DAILY_ACCOUNTING_PATH, index=False, compression="gzip")
    results["ai_month_audit"].to_csv(AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    results["accounting_audit"].to_csv(ACCOUNTING_AUDIT_PATH, index=False, encoding="utf-8-sig")
    plot_outputs(results)

    variant_summary = results["variant_summary"].copy()
    retention = results["retention"].copy()
    accounting = results["accounting_audit"].copy()
    ai_audit = results["ai_month_audit"].copy()
    fail_ai = int(ai_audit["status"].astype(str).eq("FAIL").sum()) if not ai_audit.empty and "status" in ai_audit.columns else 0
    candidate = variant_summary[variant_summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    official = variant_summary[variant_summary["version"].eq(OFFICIAL_VERSION)].iloc[0].to_dict()
    promoted = (
        candidate["min_return_retention_ratio"] >= 0.5 - 1e-9
        and candidate["worst_drawdown_pct"] > official["worst_drawdown_pct"]
        and candidate["max_days_below_initial"] < official["max_days_below_initial"]
        and fail_ai == 0
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage075_true_engine_promoted_to_next_review" if promoted else "stage075_true_engine_not_promoted",
        "promoted_to_next_review": promoted,
        "candidate_summary": candidate,
        "official_summary": official,
        "ai_fail_rows": fail_ai,
        "max_abs_accounting_residual": float(
            pd.to_numeric(accounting.get("max_abs_accounting_residual", pd.Series(dtype=float)), errors="coerce").max()
        )
        if not accounting.empty
        else np.nan,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Stage075 official C9 month-end buffer top-up true engine",
        "",
        "## 口径",
        "",
        "- A：读取 Stage167 已有正式 C9/15w 真实引擎曲线。",
        "- C：正式 C9 信号、AI、0.5R 止损重试、保证金和整数手不变；总账户 30w，15w 交易袖 + 15w 储备，月末收盘后若 broker sizing equity 低于 15w，则用储备补回。",
        "- 内部补款不计入 alpha PnL；总账户收益分母固定 300,000。",
        "- 本阶段不连接 CTP、不读取账户、不调用订单 API。",
        "",
        "## 汇总",
        "",
        _md_table(variant_summary),
        "",
        "## 逐起点对比",
        "",
        _md_table(retention.round(6), 80),
        "",
        "## 会计审计",
        "",
        _md_table(accounting, 80),
        "",
        "## AI 审计状态",
        "",
        _md_table(ai_audit.groupby("status", dropna=False).size().reset_index(name="rows") if not ai_audit.empty else pd.DataFrame()),
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 是否进入下一步 review：`{promoted}`。",
        "",
        "## 输出文件",
        "",
        f"- curves：`{CURVES_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- variant_summary：`{VARIANT_SUMMARY_PATH}`",
        f"- retention_vs_official：`{RETENTION_PATH}`",
        f"- cashflow_events：`{CASHFLOW_EVENTS_PATH}`",
        f"- daily_accounting：`{DAILY_ACCOUNTING_PATH}`",
        f"- accounting_audit：`{ACCOUNTING_AUDIT_PATH}`",
        f"- AI month audit：`{AI_MONTH_AUDIT_PATH}`",
        f"- equity chart：`{CHART_EQUITY_PATH}`",
        f"- return/dd chart：`{CHART_RETURN_DD_PATH}`",
        f"- underwater chart：`{CHART_UNDERWATER_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")

    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage075_official_c9_monthend_buffer_topup_true_engine.md"
    stage_record = [
        "# Stage075 official C9 month-end buffer top-up true engine",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 阶段性质：正式 C9 30w 月末缓冲补款真实引擎 A/C",
        f"- 是否重要突破：{'是，若指标通过则为资金治理候选' if promoted else '否，真实引擎未通过新目标'}",
        "- 是否触发A/B：是；A=正式 C9/15w，C=正式 C9 + 30w 月末缓冲补款资金治理",
        "",
        "## 外部调研与判断",
        "",
        "- CPPI/TIPP 和 capital correction 支持资金安全垫思路，但 Stage074 已显示单纯降风险会拉长水下；本阶段只验证月末补回交易袖。",
        "- 新目标：收益率保留 `50%`，同时减少水下时间和最大回撤。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无正式入口修改。",
        "- 删除脚本：无。",
        "- 新增参数：`enable_stage075_monthend_buffer_topup`、`stage075_initial_reserve_capital=150000`、`stage075_topup_floor_equity=150000`。",
        "- 修改参数：无正式交易信号参数；只改变研究候选的资金治理层。",
        "- 删除参数：无。",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：`2020-01` 到 `2026-01` 逐半年起点，统一终点 `2026-06-30`。",
        "- 账户规模：A `150,000`；C 总账户 `300,000=150,000交易袖+150,000储备`。",
        "- 成本口径：沿用正式真实引擎成本。",
        "- 样本过滤：无。",
        "- 策略/归因口径：C 的补款发生在月末收盘后，只影响后续 sizing；补款不计入收益。",
        "",
        "## 结果",
        "",
        _md_table(variant_summary),
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- daily：`{CURVES_PATH}`",
        f"- orders：`{TRADES_PATH}`",
        f"- quality：`{AI_MONTH_AUDIT_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`。",
        f"- 是否进入下一步：`{promoted}`。",
        "- 下一步：若通过，拉独立 agent 做代码与统计口径 review，再决定是否做更密集逐月起点；若未通过，停止补款频率/比例救参。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。资金结构由实际 30w/15w+15w 给定，月末频率来自低频资金治理，不按亏损窗口调参。",
        "- 运行后判断：见结论；不按失败起点继续调补款日期或金额。",
        "- 原因：继续扫补款频率、floor 或储备比例会变成资金曲线救参。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有。Stage074 代理通过新目标，值得真实引擎确认。",
        f"- 运行后判断：{'有，若通过需进入独立 review 和逐月扩样本' if promoted else '有限，若未通过应停止该形状'}。",
        "- 原因：真实引擎决定补款是否真的改善整数手和保证金路径。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：独立 review 后再更新。",
        "- 是否更新 `research/registry.md`：否。",
        "- 是否追加根目录 `memory.md/back_log.md`：独立 review 后再决定。",
    ]
    stage_path.write_text("\n".join(stage_record) + "\n", encoding="utf-8")


def main() -> None:
    results = build()
    write_outputs(results)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "summary": results["variant_summary"].to_dict(orient="records"),
                "retention": results["retention"].to_dict(orient="records"),
                "ai_fail_rows": int(results["ai_month_audit"]["status"].astype(str).eq("FAIL").sum())
                if not results["ai_month_audit"].empty and "status" in results["ai_month_audit"].columns
                else 0,
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

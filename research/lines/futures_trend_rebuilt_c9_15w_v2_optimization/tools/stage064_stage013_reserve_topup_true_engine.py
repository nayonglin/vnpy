from __future__ import annotations

from contextlib import contextmanager
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
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
UPSTREAM_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
THIS_TOOLS_DIR = Path(__file__).resolve().parent
for candidate in (str(PORTFOLIO_DIR), str(UPSTREAM_TOOLS_DIR), str(THIS_TOOLS_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
import stage013_account_state_pilot_gate_engine as s013
import stage062_stage013_full_monthly_ai_candidate_official as s062
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage064"
MODEL_TAG = "stage064_stage013_reserve_topup_true_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage064_stage013_reserve_topup_true_engine"

REQUESTED_START = pd.Timestamp("2021-07-01")
REQUESTED_END = pd.Timestamp("2026-07-02")
START_MONTHS = (1, 7)
RESERVE_VARIANTS = (50_000.0, 100_000.0, 150_000.0)
PRIMARY_RESERVE = 100_000.0
BASE_TRADING_CAPITAL = float(OFFICIAL_LIVE_CAPITAL)

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage064_stage013_reserve_topup_true_engine"
STAGES_DIR = LINE_DIR / "stages"
BACK_LOG_PATH = ROOT / "back_log.md"

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv.gz"
CASHFLOW_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_cashflow_events_{MODEL_TAG}.csv"
ACCOUNTING_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_accounting_audit_{MODEL_TAG}.csv"
PRIMARY_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_primary_reserve_100k_vs_baseline_{MODEL_TAG}.png"
RESERVE_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_reserve_sensitivity_{MODEL_TAG}.png"
DEFECT_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_drawdown_defect_by_start_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

BASELINE_SUMMARY_PATH = s062.SUMMARY_PATH
BASELINE_CURVES_PATH = s062.CURVES_PATH
CANDIDATE_AI_PATH = s062.CANDIDATE_AI_PATH


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    return value


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(nav: pd.Series) -> float:
    returns = pd.to_numeric(nav, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _build_start_dates() -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    latest_start = pd.Timestamp("2026-01-01")
    for year in range(REQUESTED_START.year, REQUESTED_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= min(REQUESTED_END, latest_start):
                starts.append(start)
    return starts


class QmtRollPortfolioStrategyStage064ReserveTopup(s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate):
    enable_stage064_reserve_topup: bool = False
    stage064_initial_reserve_capital: float = 0.0
    stage064_base_trading_capital: float = BASE_TRADING_CAPITAL
    stage064_topup_floor_equity: float = BASE_TRADING_CAPITAL
    stage064_topup_min_amount: float = 1.0

    parameters = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage064_reserve_topup",
        "stage064_initial_reserve_capital",
        "stage064_base_trading_capital",
        "stage064_topup_floor_equity",
        "stage064_topup_min_amount",
    ]
    variables = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage064_external_cashflow_cumulative",
        "stage064_reserve_remaining",
        "stage064_topup_count",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        reserve = max(0.0, float(getattr(self, "stage064_initial_reserve_capital", 0.0) or 0.0))
        self.stage064_external_cashflow_cumulative: float = 0.0
        self.stage064_reserve_remaining: float = reserve
        self.stage064_topup_count: int = 0
        self.stage064_cashflow_events: list[dict[str, Any]] = []
        self.stage064_daily_accounting: list[dict[str, Any]] = []
        self.stage064_strategy_equity_for_sizing: float = self.base_capital
        self.stage064_broker_equity_for_sizing: float = self.base_capital

    def _stage064_enabled(self) -> bool:
        return bool(self.enable_stage064_reserve_topup) and float(self.stage064_initial_reserve_capital or 0.0) > 0.0

    def _stage064_floor(self) -> float:
        floor = float(self.stage064_topup_floor_equity or 0.0)
        if floor <= 0.0:
            floor = float(self.stage064_base_trading_capital or self.base_capital or 0.0)
        return max(0.0, floor)

    def _stage064_set_broker_equity_from_strategy(self, strategy_equity: float) -> None:
        self.stage064_strategy_equity_for_sizing = max(0.0, float(strategy_equity or 0.0))
        self.stage064_broker_equity_for_sizing = max(
            0.0,
            self.stage064_strategy_equity_for_sizing + float(self.stage064_external_cashflow_cumulative or 0.0),
        )

    def _stage064_maybe_topup(self) -> None:
        strategy_equity = max(0.0, float(self.estimated_equity or self.base_capital or 0.0))
        self._stage064_set_broker_equity_from_strategy(strategy_equity)
        if not self._stage064_enabled():
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
                "reason": "broker_equity_below_floor",
            }
        )

    @contextmanager
    def _stage064_broker_equity_context(self):
        original_equity = self.estimated_equity
        try:
            if self._stage064_enabled():
                self.estimated_equity = max(
                    0.0,
                    float(self.stage064_broker_equity_for_sizing or original_equity or self.base_capital or 0.0),
                )
            yield
        finally:
            self.estimated_equity = original_equity

    def _refresh_risk_state(self, bars: dict[str, Any]) -> None:
        super()._refresh_risk_state(bars)
        self._stage064_maybe_topup()
        if not self._stage064_enabled():
            return
        self._refresh_portfolio_margin_deleverage_state()
        self.risk_cluster_heat_gate_weight = self._current_min_risk_cluster_heat_gate_weight()
        limited_balance = self._limited_available_balance()
        self.current_risk_per_trade = self._risk_amount_from_ratio(self.risk_ratio_of_total_assets, limited_balance)

    def _sizing_equity_snapshot(self) -> dict[str, float | int]:
        if not self._stage064_enabled():
            return super()._sizing_equity_snapshot()
        with self._stage064_broker_equity_context():
            fields = dict(super()._sizing_equity_snapshot())
        fields.update(
            {
                "stage064_reserve_topup_enabled": 1,
                "stage064_initial_reserve_capital": float(self.stage064_initial_reserve_capital or 0.0),
                "stage064_external_cashflow_cumulative": float(self.stage064_external_cashflow_cumulative or 0.0),
                "stage064_reserve_remaining": float(self.stage064_reserve_remaining or 0.0),
                "stage064_strategy_equity_ex_cashflow": float(self.stage064_strategy_equity_for_sizing or 0.0),
                "stage064_broker_equity_for_sizing": float(self.stage064_broker_equity_for_sizing or 0.0),
                "stage064_topup_floor_equity": self._stage064_floor(),
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
        if not self._stage064_enabled():
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
        with self._stage064_broker_equity_context():
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
                "stage064_reserve_topup_enabled": 1,
                "stage064_initial_reserve_capital": float(self.stage064_initial_reserve_capital or 0.0),
                "stage064_external_cashflow_cumulative": float(self.stage064_external_cashflow_cumulative or 0.0),
                "stage064_reserve_remaining": float(self.stage064_reserve_remaining or 0.0),
                "stage064_strategy_equity_ex_cashflow": float(self.stage064_strategy_equity_for_sizing or 0.0),
                "stage064_broker_equity_for_sizing": float(self.stage064_broker_equity_for_sizing or 0.0),
                "stage064_topup_floor_equity": self._stage064_floor(),
            }
        )
        return sizing

    def _refresh_portfolio_margin_deleverage_state(self) -> None:
        if not self._stage064_enabled():
            super()._refresh_portfolio_margin_deleverage_state()
            return
        with self._stage064_broker_equity_context():
            super()._refresh_portfolio_margin_deleverage_state()

    def _process_forced_margin_deleverage(self, bars: dict[str, Any]) -> None:
        if not self._stage064_enabled():
            super()._process_forced_margin_deleverage(bars)
            return
        with self._stage064_broker_equity_context():
            super()._process_forced_margin_deleverage(bars)

    def on_bars(self, bars: dict[str, Any]) -> None:
        super().on_bars(bars)
        if not self._stage064_enabled():
            return
        strategy_equity = max(0.0, float(self.estimated_equity or self.base_capital or 0.0))
        broker_equity = strategy_equity + float(self.stage064_external_cashflow_cumulative or 0.0)
        reserve_remaining = max(0.0, float(self.stage064_reserve_remaining or 0.0))
        total_account_equity = broker_equity + reserve_remaining
        current_date = self.current_bar_date
        self.stage064_daily_accounting.append(
            {
                "date": _date_text(current_date) if current_date is not None else "",
                "strategy_equity_ex_cashflow": strategy_equity,
                "broker_equity_with_cashflow": broker_equity,
                "reserve_remaining": reserve_remaining,
                "external_cashflow_cumulative": float(self.stage064_external_cashflow_cumulative or 0.0),
                "total_account_equity": total_account_equity,
                "topup_count": int(self.stage064_topup_count),
                "active_count": int(self.active_count),
                "total_margin_in_use": float(self.total_margin_in_use or 0.0),
                "portfolio_drawdown_pct_ex_cashflow": float(self.portfolio_drawdown_pct or 0.0),
                "broker_equity_for_sizing": float(self.stage064_broker_equity_for_sizing or 0.0),
            }
        )


def _stage064_profile(metadata: dict[str, Any], reserve_capital: float) -> dict[str, Any]:
    profile = s013._stage013_profile(metadata)
    spec = profile["spec"]
    reserve_label = f"{int(round(reserve_capital / 10_000.0))}w"
    profile_name = f"stage064_stage013_reserve_topup_{reserve_label}"
    capital = replace(
        spec.capital,
        variant=profile_name,
        label=f"Stage064 Stage013 reserve-topup true engine {reserve_label}",
        account_capital=BASE_TRADING_CAPITAL,
        c3_capital=BASE_TRADING_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage064 keeps strategy PnL ex-cashflow, "
            f"but uses a fixed {reserve_capital:,.0f} reserve to top up broker sizing equity to "
            f"{BASE_TRADING_CAPITAL:,.0f} when below floor. External cashflow is not counted as alpha."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage064_reserve_topup": True,
        "stage064_initial_reserve_capital": float(reserve_capital),
        "stage064_base_trading_capital": BASE_TRADING_CAPITAL,
        "stage064_topup_floor_equity": BASE_TRADING_CAPITAL,
        "stage064_topup_min_amount": 1.0,
    }
    result = dict(profile)
    result["profile"] = profile_name
    result["strategy_cls"] = QmtRollPortfolioStrategyStage064ReserveTopup
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=profile_name)
    return result


def _run_profile(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s013.s847.s827.s778.s653.s517.START_DT
    original_end = s013.s847.s827.s778.s653.s517.END_DT
    original_preload = s013.s847.s827.s778.s653.s517.PRELOAD_START_DT
    try:
        s013.s847.s827.s778.s653.s517.START_DT = s013.s847.START.to_pydatetime()
        s013.s847.s827.s778.s653.s517.END_DT = s013.s847.END.to_pydatetime()
        s013.s847.s827.s778.s653.s517.PRELOAD_START_DT = s013.s847.s827.s772._preload_for_start(
            s013.s847.START
        ).to_pydatetime()

        s013.s847.s827.s778.s653.s517.assert_stage196_database_sentinels()
        s013.s847.s827.s778.s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(
            s013.s847.s827.s778.s653.s517.PRELOAD_START_DT,
            s013.s847.s827.s778.s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta(),
        )
        _, open_map = s013.s847.s827.s778.s653.s517.s506.s501._seed_proxy_maps()
        engine = s013.s847.Stage847StopRetryEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s013.s847.s827.Interval.DAILY,
            start=preload_start,
            end=s013.s847.s827.s778.s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s013.s847.s827.s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=dict(s013.s847.s513._c3_overrides(s013.s847.START.to_pydatetime())),
            start=s013.s847.START,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            daily_df = pd.DataFrame(
                [{"net_pnl": 0.0, "trade_count": 0.0, "slippage": 0.0, "commission": 0.0, "turnover": 0.0}],
                index=pd.Index([s013.s847.END.date()], name="date"),
            )

        daily = daily_df.copy()
        daily = daily.loc[
            (daily.index >= s013.s847.START.date()) & (daily.index <= s013.s847.END.date())
        ].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        positions = s013.s847.s827.s778.build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            margin_daily, _ = s013.s847.s513._position_margin(positions, metadata)
        else:
            margin_daily = pd.DataFrame(
                columns=["variant", "combo_variant", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            )
        combined = s013.s847.s827.s772._combine_daily(daily, margin_daily, spec)
        strategy = getattr(engine, "strategy", None)
        c2_events = pd.DataFrame(getattr(strategy, "stage827_intraday_c2_events", []) if strategy else [])
        stop_retry_events = pd.DataFrame(getattr(strategy, "stage847_stop_retry_events", []) if strategy else [])
        if not stop_retry_events.empty and "synthetic_trades" in stop_retry_events.columns:
            stop_retry_events = stop_retry_events.drop(columns=["synthetic_trades"])
        pilot_gate_events = pd.DataFrame(getattr(strategy, "stage013_pilot_gate_events", []) if strategy else [])
        intraday_events = pd.concat([c2_events, stop_retry_events], ignore_index=True, sort=False)
        frames = {
            "trades": s013.s847.s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s013.s847.s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s013.s847.s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "pilot_gate_events": pilot_gate_events,
            "pending_orders": s013.s847._active_limit_orders_frame(engine),
            "cashflow_events": pd.DataFrame(getattr(strategy, "stage064_cashflow_events", []) if strategy else []),
            "daily_accounting": pd.DataFrame(getattr(strategy, "stage064_daily_accounting", []) if strategy else []),
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["start_month"] = s013.s847.START.strftime("%Y-%m")
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s013.s847.s827.s778.s653.s517.START_DT = original_start
        s013.s847.s827.s778.s653.s517.END_DT = original_end
        s013.s847.s827.s778.s653.s517.PRELOAD_START_DT = original_preload


def _run_live_stage064(
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
    reserve_capital: float,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s013.s847.START
    original_end = s013.s847.END
    original_minute_by_symbol = s013.s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s901._ensure_c9_minute_bars(metadata)
    try:
        s013.s847.START = analysis_start.normalize()
        s013.s847.END = analysis_end.normalize()
        profile = _stage064_profile(metadata, reserve_capital)
        combined, frames = _run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        s013.s847.START = original_start
        s013.s847.END = original_end
        s013.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol

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


def _apply_cashflow_to_curve(
    combined: pd.DataFrame,
    cashflow_events: pd.DataFrame,
    daily_accounting: pd.DataFrame,
    reserve_capital: float,
) -> pd.DataFrame:
    curve = combined.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    curve["strategy_equity_ex_cashflow"] = pd.to_numeric(curve["account_equity"], errors="coerce").ffill()
    event_daily = pd.DataFrame({"date": curve["date"], "external_cashflow": 0.0})
    if not cashflow_events.empty:
        cash = cashflow_events.copy()
        cash["date"] = pd.to_datetime(cash["date"], errors="coerce").dt.normalize()
        cash["amount"] = pd.to_numeric(cash["amount"], errors="coerce").fillna(0.0)
        grouped = cash.groupby("date", as_index=False).agg(external_cashflow=("amount", "sum"))
        event_daily = event_daily.drop(columns=["external_cashflow"]).merge(grouped, on="date", how="left")
        event_daily["external_cashflow"] = pd.to_numeric(event_daily["external_cashflow"], errors="coerce").fillna(0.0)
    curve["external_cashflow"] = event_daily["external_cashflow"].to_numpy(dtype=float)
    curve["external_cashflow_cumulative"] = curve["external_cashflow"].cumsum()
    curve["reserve_remaining"] = reserve_capital - curve["external_cashflow_cumulative"]
    curve["broker_equity_with_cashflow"] = curve["strategy_equity_ex_cashflow"] + curve["external_cashflow_cumulative"]
    curve["total_account_equity"] = curve["broker_equity_with_cashflow"] + curve["reserve_remaining"]
    curve["strategy_nav_ex_cashflow"] = curve["strategy_equity_ex_cashflow"] / BASE_TRADING_CAPITAL
    curve["broker_nav_vs_base_not_return"] = curve["broker_equity_with_cashflow"] / BASE_TRADING_CAPITAL
    curve["total_account_nav"] = curve["total_account_equity"] / (BASE_TRADING_CAPITAL + reserve_capital)
    curve["strategy_drawdown_pct_ex_cashflow"] = _drawdown_pct(curve["strategy_equity_ex_cashflow"])
    curve["broker_drawdown_pct_with_cashflow"] = _drawdown_pct(curve["broker_equity_with_cashflow"])
    curve["total_account_drawdown_pct"] = _drawdown_pct(curve["total_account_equity"])
    if not daily_accounting.empty:
        acc = daily_accounting.copy()
        acc["date"] = pd.to_datetime(acc["date"], errors="coerce").dt.normalize()
        acc = acc.drop_duplicates("date", keep="last")
        cols = [
            "date",
            "strategy_equity_ex_cashflow",
            "broker_equity_with_cashflow",
            "reserve_remaining",
            "external_cashflow_cumulative",
            "total_account_equity",
            "broker_equity_for_sizing",
            "portfolio_drawdown_pct_ex_cashflow",
        ]
        present = [c for c in cols if c in acc.columns]
        acc = acc[present].rename(columns={c: f"engine_{c}" for c in present if c != "date"})
        curve = curve.merge(acc, on="date", how="left")
    return curve


def _accounting_audit(curve: pd.DataFrame, reserve_capital: float) -> dict[str, Any]:
    frame = curve.copy()
    net_pnl_cumsum = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0).cumsum()
    account_equity = pd.to_numeric(frame["strategy_equity_ex_cashflow"], errors="coerce").ffill()
    cash_cum = pd.to_numeric(frame["external_cashflow_cumulative"], errors="coerce").fillna(0.0)
    reserve_remaining = pd.to_numeric(frame["reserve_remaining"], errors="coerce").fillna(0.0)
    broker_equity = pd.to_numeric(frame["broker_equity_with_cashflow"], errors="coerce").ffill()
    total_account = pd.to_numeric(frame["total_account_equity"], errors="coerce").ffill()
    pnl_identity = (account_equity - BASE_TRADING_CAPITAL - net_pnl_cumsum).abs().max()
    broker_identity = (broker_equity - account_equity - cash_cum).abs().max()
    reserve_identity = (reserve_remaining + cash_cum - reserve_capital).abs().max()
    total_identity = (total_account - broker_equity - reserve_remaining).abs().max()
    total_pnl_identity = (total_account - (BASE_TRADING_CAPITAL + reserve_capital) - net_pnl_cumsum).abs().max()
    engine_broker_identity = np.nan
    if "engine_broker_equity_with_cashflow" in frame.columns:
        engine_broker = pd.to_numeric(frame["engine_broker_equity_with_cashflow"], errors="coerce")
        matched = engine_broker.notna()
        if matched.any():
            engine_broker_identity = float((engine_broker[matched] - broker_equity[matched]).abs().max())
    hard_gate_residual = max(
        float(pnl_identity),
        float(broker_identity),
        float(reserve_identity),
        float(total_identity),
        float(total_pnl_identity),
    )
    return {
        "pnl_identity_max_abs": float(pnl_identity),
        "broker_identity_max_abs": float(broker_identity),
        "reserve_identity_max_abs": float(reserve_identity),
        "total_identity_max_abs": float(total_identity),
        "total_pnl_identity_max_abs": float(total_pnl_identity),
        "engine_broker_identity_max_abs": float(engine_broker_identity) if np.isfinite(engine_broker_identity) else np.nan,
        "engine_broker_identity_hard_gate": 0,
        "audit_pass": int(hard_gate_residual < 1e-5),
    }


def _summarize_curve(curve: pd.DataFrame, reserve_capital: float, requested_start: pd.Timestamp) -> dict[str, Any]:
    frame = curve.copy().sort_values("date").reset_index(drop=True)
    strategy_equity = pd.to_numeric(frame["strategy_equity_ex_cashflow"], errors="coerce").ffill()
    broker_equity = pd.to_numeric(frame["broker_equity_with_cashflow"], errors="coerce").ffill()
    total_equity = pd.to_numeric(frame["total_account_equity"], errors="coerce").ffill()
    cash_cum = pd.to_numeric(frame["external_cashflow_cumulative"], errors="coerce").fillna(0.0)
    reserve_remaining = pd.to_numeric(frame["reserve_remaining"], errors="coerce").fillna(0.0)
    strategy_nav = strategy_equity / BASE_TRADING_CAPITAL
    total_nav = total_equity / (BASE_TRADING_CAPITAL + reserve_capital)
    broker_below = broker_equity < BASE_TRADING_CAPITAL - 1e-9
    strategy_below = strategy_equity < BASE_TRADING_CAPITAL - 1e-9
    audit = _accounting_audit(frame, reserve_capital)
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": f"stage013_reserve_topup_{int(reserve_capital)}",
        "reserve_capital": float(reserve_capital),
        "requested_start": _date_text(requested_start),
        "requested_start_month": _start_month_text(requested_start),
        "requested_end": _date_text(REQUESTED_END),
        "actual_start": _date_text(frame["date"].iloc[0]),
        "actual_end": _date_text(frame["date"].iloc[-1]),
        "trading_days": int(len(frame)),
        "base_trading_capital": BASE_TRADING_CAPITAL,
        "total_initial_capital_with_reserve": BASE_TRADING_CAPITAL + reserve_capital,
        "strategy_end_equity_ex_cashflow": float(strategy_equity.iloc[-1]),
        "strategy_total_return_ex_cashflow_pct": float((strategy_equity.iloc[-1] / BASE_TRADING_CAPITAL - 1.0) * 100.0),
        "strategy_max_dd_ex_cashflow_pct": float(_drawdown_pct(strategy_equity).min()),
        "broker_end_equity_with_cashflow": float(broker_equity.iloc[-1]),
        "broker_max_dd_with_cashflow_pct": float(_drawdown_pct(broker_equity).min()),
        "broker_days_below_base": int(broker_below.sum()),
        "strategy_days_below_base": int(strategy_below.sum()),
        "total_account_end_equity": float(total_equity.iloc[-1]),
        "total_account_return_pct": float((total_equity.iloc[-1] / (BASE_TRADING_CAPITAL + reserve_capital) - 1.0) * 100.0),
        "total_account_max_dd_pct": float(_drawdown_pct(total_equity).min()),
        "max_external_cashflow_used": float(cash_cum.max()),
        "reserve_remaining_end": float(reserve_remaining.iloc[-1]),
        "reserve_exhausted": int(reserve_remaining.min() <= 1e-9),
        "cashflow_event_count": int((pd.to_numeric(frame["external_cashflow"], errors="coerce").fillna(0.0) > 0).sum()),
        "sharpe_strategy_ex_cashflow": _daily_sharpe(strategy_nav),
        "sharpe_total_account": _daily_sharpe(total_nav),
        "total_slippage": _safe_sum(frame, "slippage"),
        "total_trade_count": _safe_sum(frame, "trade_count"),
        **audit,
    }


def _with_run_columns(frame: pd.DataFrame, start: pd.Timestamp, reserve_capital: float, name: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["version"] = f"stage013_reserve_topup_{int(reserve_capital)}"
    result["reserve_capital"] = float(reserve_capital)
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    result["frame_name"] = name
    return result


def _load_baseline_frames(starts: list[pd.Timestamp]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not BASELINE_SUMMARY_PATH.exists() or not BASELINE_CURVES_PATH.exists():
        raise RuntimeError(f"missing Stage062 baseline outputs: {BASELINE_SUMMARY_PATH} / {BASELINE_CURVES_PATH}")
    allowed = {_start_month_text(start) for start in starts}
    summary = pd.read_csv(BASELINE_SUMMARY_PATH, encoding="utf-8-sig")
    curves = pd.read_csv(BASELINE_CURVES_PATH, encoding="utf-8-sig")
    summary = summary[summary["requested_start_month"].astype(str).isin(allowed)].copy()
    curves = curves[curves["requested_start_month"].astype(str).isin(allowed)].copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["version"] = "stage062_stage013_no_reserve_baseline"
    curves["reserve_capital"] = 0.0
    curves["strategy_equity_ex_cashflow"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    curves["broker_equity_with_cashflow"] = curves["strategy_equity_ex_cashflow"]
    curves["total_account_equity"] = curves["strategy_equity_ex_cashflow"]
    curves["strategy_drawdown_pct_ex_cashflow"] = _drawdown_pct(curves["strategy_equity_ex_cashflow"])
    curves["broker_drawdown_pct_with_cashflow"] = curves["strategy_drawdown_pct_ex_cashflow"]
    curves["total_account_drawdown_pct"] = curves["strategy_drawdown_pct_ex_cashflow"]
    curves["total_account_nav"] = curves["strategy_equity_ex_cashflow"] / BASE_TRADING_CAPITAL
    return summary, curves


def run_backtests() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    if not CANDIDATE_AI_PATH.exists():
        print("[stage064] Stage062 candidate AI file missing; rebuilding AI file only", flush=True)
        s062.build_full_monthly_ai_file()

    starts = _build_start_dates()
    metadata = s901.s513._metadata()
    summary_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []
    cashflow_frames: list[pd.DataFrame] = []

    total_runs = len(starts) * len(RESERVE_VARIANTS)
    run_index = 0
    with s062._patched_live_ai_path(CANDIDATE_AI_PATH):
        for reserve_capital in RESERVE_VARIANTS:
            for start in starts:
                run_index += 1
                print(
                    f"[stage064] run {run_index}/{total_runs} reserve={reserve_capital:,.0f} start={_date_text(start)}",
                    flush=True,
                )
                combined, frames, _spec = _run_live_stage064(metadata, start, REQUESTED_END, reserve_capital)
                curve = _apply_cashflow_to_curve(
                    combined=combined,
                    cashflow_events=frames.get("cashflow_events", pd.DataFrame()),
                    daily_accounting=frames.get("daily_accounting", pd.DataFrame()),
                    reserve_capital=reserve_capital,
                )
                curve = _with_run_columns(curve, start, reserve_capital, "curves")
                curve["days_since_start"] = np.arange(len(curve), dtype=int)
                curve_frames.append(curve)
                summary = _summarize_curve(curve, reserve_capital, start)
                summary_rows.append(summary)
                audit_rows.append(
                    {
                        "reserve_capital": float(reserve_capital),
                        "requested_start_month": _start_month_text(start),
                        **{k: v for k, v in summary.items() if k.endswith("_max_abs") or k == "audit_pass"},
                    }
                )
                candidate_frames.append(
                    _with_run_columns(frames.get("entry_candidates", pd.DataFrame()), start, reserve_capital, "entry_candidates")
                )
                trade_frames.append(_with_run_columns(frames.get("trades", pd.DataFrame()), start, reserve_capital, "trades"))
                trade_event_frames.append(
                    _with_run_columns(frames.get("trade_events", pd.DataFrame()), start, reserve_capital, "trade_events")
                )
                cashflow_frames.append(
                    _with_run_columns(frames.get("cashflow_events", pd.DataFrame()), start, reserve_capital, "cashflow_events")
                )

    summary_df = pd.DataFrame(summary_rows).sort_values(["reserve_capital", "requested_start"]).reset_index(drop=True)
    curves_df = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    return {
        "summary": summary_df,
        "curves": curves_df,
        "entry_candidates": pd.concat([f for f in candidate_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in candidate_frames)
        else pd.DataFrame(),
        "trades": pd.concat([f for f in trade_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in trade_frames)
        else pd.DataFrame(),
        "trade_events": pd.concat([f for f in trade_event_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in trade_event_frames)
        else pd.DataFrame(),
        "cashflow_events": pd.concat([f for f in cashflow_frames if not f.empty], ignore_index=True, sort=False)
        if any(not f.empty for f in cashflow_frames)
        else pd.DataFrame(),
        "accounting_audit": pd.DataFrame(audit_rows).sort_values(["reserve_capital", "requested_start_month"]).reset_index(drop=True),
    }


def _variant_summary(summary: pd.DataFrame, baseline_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base_returns = pd.to_numeric(baseline_summary["total_return_pct"], errors="coerce")
    base_dds = pd.to_numeric(baseline_summary["max_dd_pct"], errors="coerce")
    rows.append(
        {
            "version": "stage062_stage013_no_reserve_baseline",
            "reserve_capital": 0.0,
            "start_count": int(len(baseline_summary)),
            "positive_strategy_count": int(base_returns.gt(0.0).sum()),
            "min_strategy_return_pct": float(base_returns.min()),
            "median_strategy_return_pct": float(base_returns.median()),
            "max_strategy_return_pct": float(base_returns.max()),
            "worst_strategy_dd_pct": float(base_dds.min()),
            "median_strategy_dd_pct": float(base_dds.median()),
            "min_total_account_return_pct": float(base_returns.min()),
            "median_total_account_return_pct": float(base_returns.median()),
            "worst_total_account_dd_pct": float(base_dds.min()),
            "positive_total_account_count": int(base_returns.gt(0.0).sum()),
            "max_external_cashflow_used": 0.0,
            "reserve_exhausted_count": 0,
            "broker_below_base_days_sum": 0,
            "audit_pass_count": int(len(baseline_summary)),
        }
    )
    for reserve_capital, group in summary.groupby("reserve_capital"):
        strategy_returns = pd.to_numeric(group["strategy_total_return_ex_cashflow_pct"], errors="coerce")
        strategy_dds = pd.to_numeric(group["strategy_max_dd_ex_cashflow_pct"], errors="coerce")
        total_returns = pd.to_numeric(group["total_account_return_pct"], errors="coerce")
        total_dds = pd.to_numeric(group["total_account_max_dd_pct"], errors="coerce")
        rows.append(
            {
                "version": f"stage064_stage013_reserve_topup_{int(reserve_capital)}",
                "reserve_capital": float(reserve_capital),
                "start_count": int(len(group)),
                "positive_strategy_count": int(strategy_returns.gt(0.0).sum()),
                "min_strategy_return_pct": float(strategy_returns.min()),
                "median_strategy_return_pct": float(strategy_returns.median()),
                "max_strategy_return_pct": float(strategy_returns.max()),
                "worst_strategy_dd_pct": float(strategy_dds.min()),
                "median_strategy_dd_pct": float(strategy_dds.median()),
                "min_total_account_return_pct": float(total_returns.min()),
                "median_total_account_return_pct": float(total_returns.median()),
                "worst_total_account_dd_pct": float(total_dds.min()),
                "positive_total_account_count": int(total_returns.gt(0.0).sum()),
                "max_external_cashflow_used": float(pd.to_numeric(group["max_external_cashflow_used"], errors="coerce").max()),
                "reserve_exhausted_count": int(pd.to_numeric(group["reserve_exhausted"], errors="coerce").fillna(0).sum()),
                "broker_below_base_days_sum": int(pd.to_numeric(group["broker_days_below_base"], errors="coerce").fillna(0).sum()),
                "audit_pass_count": int(pd.to_numeric(group["audit_pass"], errors="coerce").fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot_outputs(curves: pd.DataFrame, baseline_curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    primary = curves[np.isclose(pd.to_numeric(curves["reserve_capital"], errors="coerce"), PRIMARY_RESERVE)].copy()
    baseline = baseline_curves.copy()
    starts = sorted(set(primary["requested_start_month"].astype(str)) | set(baseline["requested_start_month"].astype(str)))

    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for start in starts:
        b = baseline[baseline["requested_start_month"].astype(str).eq(start)].sort_values("date")
        p = primary[primary["requested_start_month"].astype(str).eq(start)].sort_values("date")
        if not b.empty:
            axes[0].plot(b["date"], b["strategy_equity_ex_cashflow"], linewidth=0.8, alpha=0.35, color="#6b7280")
        if not p.empty:
            axes[0].plot(p["date"], p["broker_equity_with_cashflow"], linewidth=0.9, alpha=0.78, label=start)
            axes[1].plot(p["date"], p["strategy_drawdown_pct_ex_cashflow"], linewidth=0.7, alpha=0.35, color="#ef4444")
            axes[1].plot(p["date"], p["total_account_drawdown_pct"], linewidth=0.9, alpha=0.78, label=start)
    axes[0].axhline(BASE_TRADING_CAPITAL, color="#111827", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage064 100k Reserve: Broker Equity With Cashflow; gray = Stage062 no-reserve strategy equity")
    axes[0].set_ylabel("equity")
    axes[1].set_title("Stage064 100k Reserve: Total Account Drawdown; faint red = strategy drawdown ex-cashflow")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=4, loc="best")
    fig.savefig(PRIMARY_CHART_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for reserve_capital, group in curves.groupby("reserve_capital"):
        label = f"{int(float(reserve_capital) / 10_000)}w reserve"
        agg = (
            group.groupby("date", as_index=False)
            .agg(
                median_total_nav=("total_account_nav", "median"),
                min_total_nav=("total_account_nav", "min"),
                median_total_dd=("total_account_drawdown_pct", "median"),
                worst_total_dd=("total_account_drawdown_pct", "min"),
            )
            .sort_values("date")
        )
        axes[0].plot(agg["date"], agg["median_total_nav"], linewidth=1.2, label=label)
        axes[0].fill_between(agg["date"], agg["min_total_nav"], agg["median_total_nav"], alpha=0.08)
        axes[1].plot(agg["date"], agg["worst_total_dd"], linewidth=1.0, label=label)
    axes[0].set_title("Stage064 Reserve Sensitivity: Median Total Account NAV")
    axes[0].set_ylabel("total account NAV")
    axes[1].set_title("Stage064 Reserve Sensitivity: Worst Start Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    fig.savefig(RESERVE_CHART_PATH, dpi=160)
    plt.close(fig)

    plot = summary[np.isclose(pd.to_numeric(summary["reserve_capital"], errors="coerce"), PRIMARY_RESERVE)].copy()
    plot.sort_values("requested_start_month", inplace=True)
    x = np.arange(len(plot))
    fig, ax1 = plt.subplots(figsize=(16, 7), constrained_layout=True)
    ax1.bar(x - 0.18, plot["strategy_max_dd_ex_cashflow_pct"], width=0.36, color="#f97316", label="strategy DD ex-cashflow")
    ax1.bar(x + 0.18, plot["total_account_max_dd_pct"], width=0.36, color="#2563eb", label="total account DD")
    ax1.set_xticks(x)
    ax1.set_xticklabels(plot["requested_start_month"].astype(str), rotation=45, ha="right")
    ax1.set_ylabel("max drawdown %")
    ax1.set_title("Stage064 100k Reserve: Drawdown Defect By Start")
    ax1.grid(True, axis="y", alpha=0.25)
    ax1.legend(loc="best")
    fig.savefig(DEFECT_CHART_PATH, dpi=160)
    plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def write_report_and_records(decision: dict[str, Any]) -> Path:
    now = datetime.now()
    summary = pd.read_csv(SUMMARY_PATH)
    variant_summary = pd.read_csv(VARIANT_SUMMARY_PATH)
    audit = pd.read_csv(ACCOUNTING_AUDIT_PATH)
    primary = summary[np.isclose(pd.to_numeric(summary["reserve_capital"], errors="coerce"), PRIMARY_RESERVE)].copy()
    primary_view = primary[
        [
            "requested_start_month",
            "strategy_total_return_ex_cashflow_pct",
            "strategy_max_dd_ex_cashflow_pct",
            "total_account_return_pct",
            "total_account_max_dd_pct",
            "max_external_cashflow_used",
            "reserve_remaining_end",
            "broker_days_below_base",
            "total_trade_count",
            "audit_pass",
        ]
    ]
    report_lines = [
        "# Stage064 Stage013 reserve-topup true-engine study",
        "",
        f"- generated_at: `{decision['generated_at']}`",
        f"- line_id: `{LINE_ID}`",
        f"- candidate: `Stage013 + reserve top-up sizing equity`",
        f"- AI file: `{CANDIDATE_AI_PATH}`",
        f"- start range: `{REQUESTED_START.date()}` to `{REQUESTED_END.date()}`; half-year starts, latest meaningful start `2026-01`",
        "- live config changed: `false`; CTP connected: `false`; order API calls: `0`",
        "",
        "## External Research Judgment",
        "",
        "- Capital correction / deployment-layer references support treating additional capital as capacity governance, not alpha.",
        "- Time-weighted return references support stripping external cashflow from strategy performance. This report therefore separates strategy PnL, broker equity with top-up, and total account equity.",
        "- Judgment: fixed broad reserve levels are acceptable for a deployment study; choosing top-up dates or amounts from 2022/2023 troughs would be overfitting and is not done here.",
        "",
        "## Accounting Rules",
        "",
        "- `strategy_equity_ex_cashflow = 150000 + cumulative net_pnl`; this is the only strategy-return numerator.",
        "- `broker_equity_with_cashflow = strategy_equity_ex_cashflow + cumulative reserve top-up`; this can affect sizing and margin capacity.",
        "- `total_account_equity = broker_equity_with_cashflow + reserve_remaining`; reserve transfers do not create PnL.",
        "- Primary deployment return uses `(total_account_equity / (150000 + reserve_capital) - 1)`; broker equity with deposits is not reported as strategy return.",
        "",
        "## Variant Summary",
        "",
        _md_table(variant_summary, max_rows=20),
        "",
        "## Primary 100k Reserve",
        "",
        _md_table(primary_view, max_rows=30),
        "",
        "## Accounting Audit",
        "",
        f"- audit pass rows: `{int(pd.to_numeric(audit['audit_pass'], errors='coerce').fillna(0).sum())}/{len(audit)}`",
        f"- max residual: `{decision['max_accounting_residual']:.8f}`",
        "",
        _md_table(audit.head(30), max_rows=30),
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

    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage064_stage013_reserve_topup_true_engine.md"
    primary_min_ret = float(pd.to_numeric(primary["strategy_total_return_ex_cashflow_pct"], errors="coerce").min())
    primary_median_ret = float(pd.to_numeric(primary["strategy_total_return_ex_cashflow_pct"], errors="coerce").median())
    primary_worst_dd = float(pd.to_numeric(primary["strategy_max_dd_ex_cashflow_pct"], errors="coerce").min())
    primary_total_min_ret = float(pd.to_numeric(primary["total_account_return_pct"], errors="coerce").min())
    primary_total_worst_dd = float(pd.to_numeric(primary["total_account_max_dd_pct"], errors="coerce").min())
    primary_trades = float(pd.to_numeric(primary["total_trade_count"], errors="coerce").fillna(0.0).sum())
    primary_slippage = float(pd.to_numeric(primary["total_slippage"], errors="coerce").fillna(0.0).sum())
    primary_positive = int(pd.to_numeric(primary["strategy_total_return_ex_cashflow_pct"], errors="coerce").gt(0.0).sum())
    stage_lines = [
        "# Stage064 Stage013 reserve-topup true-engine",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 是否重要突破：否，资金部署层候选研究；不是 alpha 突破",
        "- 是否触发A/B：是；资金/保证金治理层和候选正式版可能相关，因此按 A vs C 思路记录",
        "",
        "## 外部调研与判断",
        "",
        "- Capital correction / pysystemtrade 类资料支持把实际账户资本变化作为资金部署问题。",
        "- TWR/MWR 资料提醒外部入金必须从策略收益里剥离，否则会把补钱误算成收益。",
        "- 本次判断：储备金只允许影响 broker sizing equity 和保证金容量，不允许计入策略 alpha；不做按 2022/2023 低点定制的充值日期或金额。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无正式入口修改",
        "- 删除脚本：无",
        "- 新增参数：`stage064_initial_reserve_capital`、`stage064_topup_floor_equity`、`stage064_base_trading_capital`、`stage064_topup_min_amount`",
        "- 修改参数：无正式交易参数",
        "- 删除参数：无",
        "",
        "## 回测参数",
        "",
        "- 版本：Stage013 account-state pilot + reserve top-up true-engine sizing equity",
        "- 储备金档位：`50,000`、`100,000`、`150,000`；主口径为 `100,000`",
        "- 起点：`2021-07` 到 `2026-01` 逐半年",
        "- 终点：`2026-07-02`",
        "- 交易袖本金：`150,000`",
        f"- AI 池：`{CANDIDATE_AI_PATH}`",
        "",
        "## 结果（100k 主口径）",
        "",
        f"- 期末权益/总收益：逐起点详见 `{SUMMARY_PATH}`",
        f"- 策略自身正收益：`{primary_positive}/{len(primary)}`",
        f"- 策略自身最小/中位收益：`{primary_min_ret:.4f}% / {primary_median_ret:.4f}%`",
        f"- 策略自身最大回撤最差值：`{primary_worst_dd:.4f}%`",
        f"- 总账户最小收益：`{primary_total_min_ret:.4f}%`",
        f"- 总账户最大回撤最差值：`{primary_total_worst_dd:.4f}%`",
        f"- 总滑点：`{primary_slippage:.4f}`",
        f"- 总交易次数：`{primary_trades:.0f}`",
        "- 胜率：本阶段沿用日线/成交汇总，不新增逐笔胜率口径，避免把资金转账当交易胜负。",
        f"- 会计校验：`{decision['accounting_audit_pass_count']}/{decision['accounting_audit_row_count']}` 通过，最大残差 `{decision['max_accounting_residual']:.8f}`",
        "",
        "## 统计口径 Review",
        "",
        "- 策略收益只看 `strategy_equity_ex_cashflow`，对应 `150000 + cumulative net_pnl`。",
        "- 储备金转入只增加 `broker_equity_with_cashflow`，用于手数/保证金容量，不写入 `net_pnl`。",
        "- 总账户收益用 `150000 + reserve_capital` 做分母；如果用 150000 分母算含入金权益，会虚增收益，禁止作为结论。",
        "- `total_account_equity - (150000 + reserve_capital)` 必须等于累计 `net_pnl`；本阶段以此做强校验。",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 原因：{decision['decision_reason']}",
        "",
        "## 后续规划和 TODO",
        "",
        "- 如果保留，下一步只做 forward/shadow 资金层演练，不把储备金本身写入 alpha 或 AI 特征。",
        "- 如果继续，优先检查新增手数集中在哪些月份/品种，以及是否只是放大 2022/2023 亏损。",
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
        f"\n{now.strftime('%Y-%m-%d %H:%M')} CST：`{LINE_ID}` Stage064 完成 Stage013 候选版储备金真实引擎资金层研究。"
        f"脚本 `{Path(__file__).relative_to(ROOT)}`；起点 2021-07 到 2026-01 逐半年，终点 2026-07-02；"
        f"储备金档位 5w/10w/15w，主口径 10w。主口径策略自身正收益 `{primary_positive}/{len(primary)}`，"
        f"策略自身最小/中位收益 `{primary_min_ret:.4f}%/{primary_median_ret:.4f}%`，"
        f"策略自身最差最大回撤 `{primary_worst_dd:.4f}%`；总账户最小收益 `{primary_total_min_ret:.4f}%`，"
        f"总账户最差最大回撤 `{primary_total_worst_dd:.4f}%`；总滑点 `{primary_slippage:.4f}`，总交易次数 `{primary_trades:.0f}`。"
        f"会计校验通过 `{decision['accounting_audit_pass_count']}/{decision['accounting_audit_row_count']}`，"
        f"最大残差 `{decision['max_accounting_residual']:.8f}`。决策 `{decision['decision']}`：{decision['decision_reason']} "
        f"未改正式配置、未连接 CTP、未调用订单 API。过拟合反思：{decision['overfit_reflection_after']} "
        f"继续价值：{decision['continue_value_after']}\n"
    )
    with BACK_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(back_log_entry)
    return stage_path


def main() -> None:
    print("[stage064] run reserve true-engine study", flush=True)
    results = run_backtests()
    starts = _build_start_dates()
    baseline_summary, baseline_curves = _load_baseline_frames(starts)
    variant_summary = _variant_summary(results["summary"], baseline_summary)

    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["curves"].to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    results["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    results["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    results["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    results["cashflow_events"].to_csv(CASHFLOW_EVENTS_PATH, index=False, encoding="utf-8-sig")
    results["accounting_audit"].to_csv(ACCOUNTING_AUDIT_PATH, index=False, encoding="utf-8-sig")
    _plot_outputs(results["curves"], baseline_curves, results["summary"])

    audit = results["accounting_audit"].copy()
    residual_cols = [c for c in audit.columns if c.endswith("_max_abs") and not c.startswith("engine_")]
    max_residual = float(audit[residual_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).max().max())
    audit_pass_count = int(pd.to_numeric(audit["audit_pass"], errors="coerce").fillna(0).sum())
    primary = results["summary"][
        np.isclose(pd.to_numeric(results["summary"]["reserve_capital"], errors="coerce"), PRIMARY_RESERVE)
    ].copy()
    primary_total_returns = pd.to_numeric(primary["total_account_return_pct"], errors="coerce")
    primary_strategy_returns = pd.to_numeric(primary["strategy_total_return_ex_cashflow_pct"], errors="coerce")
    primary_total_dd = pd.to_numeric(primary["total_account_max_dd_pct"], errors="coerce")
    baseline_subset = baseline_summary[baseline_summary["requested_start_month"].isin(primary["requested_start_month"])].copy()
    baseline_returns = pd.to_numeric(baseline_subset["total_return_pct"], errors="coerce")
    baseline_dd = pd.to_numeric(baseline_subset["max_dd_pct"], errors="coerce")
    decision_name = "stage064_reserve_topup_keep_research_only"
    reason = (
        "资金层确实降低总账户回撤/水下压力，但它不是 alpha；是否晋级要看策略自身收益和新增手数是否稳定，"
        "且必须先接受总资金分母被扩大后的收益稀释。当前只建议保留为资金治理研究线，不直接替换正式策略。"
    )
    if (
        audit_pass_count == len(audit)
        and primary_strategy_returns.gt(0.0).all()
        and float(primary_total_dd.min()) > float(baseline_dd.min())
        and float(primary_total_returns.min()) > 0.0
    ):
        decision_name = "stage064_reserve_topup_candidate_for_shadow_capital_governance"
        reason = (
            "会计校验全部通过，100k 储备金在总账户口径改善左尾且没有出现负总账户收益；"
            "但仍属于资金治理层，下一步只能进入 shadow 资金层演练，不能把入金计为策略收益。"
        )

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_mode": "day",
        "candidate": "stage013_account_state_pilot_with_reserve_topup",
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "reserve_variants": list(RESERVE_VARIANTS),
        "primary_reserve": PRIMARY_RESERVE,
        "baseline_min_return_pct": float(baseline_returns.min()),
        "baseline_median_return_pct": float(baseline_returns.median()),
        "baseline_worst_dd_pct": float(baseline_dd.min()),
        "primary_strategy_min_return_pct": float(primary_strategy_returns.min()),
        "primary_strategy_median_return_pct": float(primary_strategy_returns.median()),
        "primary_total_min_return_pct": float(primary_total_returns.min()),
        "primary_total_median_return_pct": float(primary_total_returns.median()),
        "primary_total_worst_dd_pct": float(primary_total_dd.min()),
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
            "否。储备金档位和补入规则是固定、低自由度、跨起点评估；没有按 2022/2023 低点定制日期或金额。"
        ),
        "overfit_reflection_after": (
            "基本否。若后续用某个坏起点反推专属储备金额、充值日期或 sweep 规则，就会转为过拟合；本阶段没有这样做。"
        ),
        "continue_value_before": (
            "有。用户实际资金不止 15 万，资金治理层可以回答是否因 15 万袖口亏损后容量下降导致回本慢。"
        ),
        "continue_value_after": (
            "有，但只作为资金治理继续；是否上线要和 alpha 晋级分开，后续看 shadow 资金层和新增手数归因。"
        ),
        "external_research": {
            "capital_correction": "https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html",
            "pysystemtrade": "https://github.com/pst-group/pysystemtrade",
            "time_weighted_return": "https://www.investopedia.com/terms/t/time-weightedror.asp",
            "twr_mwr_context": "https://www.sharesight.com/blog/time-weighted-vs-money-weighted-rates-of-return/",
            "judgment": (
                "Reserve/top-up is a capital deployment layer. External cashflow must be separated from strategy PnL."
            ),
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trades": str(TRADES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "cashflow_events": str(CASHFLOW_EVENTS_PATH),
            "accounting_audit": str(ACCOUNTING_AUDIT_PATH),
            "primary_chart": str(PRIMARY_CHART_PATH),
            "reserve_chart": str(RESERVE_CHART_PATH),
            "defect_chart": str(DEFECT_CHART_PATH),
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

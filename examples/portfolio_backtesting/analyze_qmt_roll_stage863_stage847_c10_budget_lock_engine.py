from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap as s830
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage861_stage860_full_visual_atlas as s861
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage863"
MODEL_TAG = "stage863_stage847_c10_budget_lock_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"

C4_ARM = s830.CAP_ARM
C9_ARM = s847.C9_ARM
C10_ARM = "stage863_stage819_c4_c9_budget_lock"

START = s847.START
END = s847.END

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
BUDGET_LOCK_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_budget_lock_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_stage861_full_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    if s861.FULL_MINUTE_BARS_PATH.exists():
        data = pd.read_csv(s861.FULL_MINUTE_BARS_PATH, encoding="utf-8-sig")
    else:
        data = s861._load_full_minute_bars(vt_symbols)
    data = data[data["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    if "bar_date" not in data.columns:
        data["bar_date"] = data["bar_datetime"].dt.normalize()
    else:
        data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "open", "high", "low", "close"]).reset_index(drop=True)


class QmtRollPortfolioStrategyStage863C10BudgetLock(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage863_stop_retry_budget_lock: bool = False

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage863_stop_retry_budget_lock",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage863_budget_lock_create_count",
        "stage863_budget_lock_reduce_count",
        "stage863_budget_lock_block_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage863_budget_locks: dict[tuple[str, str], dict[str, Any]] = {}
        self.stage863_budget_lock_events: list[dict[str, Any]] = []
        self.stage863_budget_lock_create_count: int = 0
        self.stage863_budget_lock_reduce_count: int = 0
        self.stage863_budget_lock_block_count: int = 0

    def stage827_intraday_exit_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        event = super().stage827_intraday_exit_after_open_trade(trade)
        if event and bool(self.enable_stage863_stop_retry_budget_lock) and "final_state" in event:
            self._stage863_register_budget_lock(trade, event)
        return event

    def _stage863_lock_key(self, product_vt_symbol: str, direction: str) -> tuple[str, str]:
        return str(product_vt_symbol), str(direction)

    def _stage863_state_for_product(self, product_vt_symbol: str) -> Any | None:
        state = self.states.get(product_vt_symbol)
        if state is not None:
            return state
        for item in self.states.values():
            if str(getattr(item, "product_vt_symbol", "")) == str(product_vt_symbol):
                return item
        return None

    def _stage863_active_volume(self, product_vt_symbol: str, direction: str) -> int:
        state = self._stage863_state_for_product(product_vt_symbol)
        if state is None or str(getattr(state, "direction", "")) != str(direction):
            return 0
        return max(0, int(state.active_volume()))

    def _stage863_append_budget_event(self, event: dict[str, Any]) -> None:
        self.stage863_budget_lock_events.append(event)
        diagnostics = getattr(self, "trade_event_diagnostics", None)
        if diagnostics is not None:
            diagnostics.append(event)

    def _stage863_register_budget_lock(self, trade: s827.TradeData, stop_retry_event: dict[str, Any]) -> None:
        product_vt_symbol = str(stop_retry_event.get("product_vt_symbol") or "")
        direction = str(stop_retry_event.get("direction") or "")
        if not product_vt_symbol or not direction:
            return
        final_state = str(stop_retry_event.get("final_state") or "")
        source_volume = max(0, int(stop_retry_event.get("volume") or 0))
        ceiling_volume = source_volume if final_state == "open_after_reentry" else 0
        key = self._stage863_lock_key(product_vt_symbol, direction)
        self.stage863_budget_locks[key] = {
            "product_vt_symbol": product_vt_symbol,
            "direction": direction,
            "ceiling_volume": ceiling_volume,
            "source_volume": source_volume,
            "source_final_state": final_state,
            "source_trade_id": stop_retry_event.get("trade_id", ""),
            "created_datetime": pd.Timestamp(trade.datetime).isoformat(),
            "created_vt_symbol": str(trade.vt_symbol),
        }
        self.stage863_budget_lock_create_count += 1
        self._stage863_append_budget_event(
            {
                "datetime": trade.datetime,
                "date": pd.Timestamp(trade.datetime).normalize().date().isoformat(),
                "vt_symbol": str(trade.vt_symbol),
                "product_vt_symbol": product_vt_symbol,
                "contract_vt_symbol": str(trade.vt_symbol),
                "position_direction": direction,
                "direction": direction,
                "offset": "RiskLock",
                "reason": "stage863_budget_lock_created",
                "entry_context": "intraday_stop_retry",
                "price": float(stop_retry_event.get("entry_price") or 0.0),
                "volume": source_volume,
                "selected_volume_before": source_volume,
                "selected_volume_after": ceiling_volume,
                "reduced_volume": 0,
                "locked_source_volume": max(0, source_volume - ceiling_volume),
                "active_volume": self._stage863_active_volume(product_vt_symbol, direction),
                "lock_ceiling_volume": ceiling_volume,
                "source_final_state": final_state,
                "source_trade_id": stop_retry_event.get("trade_id", ""),
            }
        )

    def _stage863_prune_budget_locks(self) -> None:
        released: list[tuple[str, str]] = []
        for key, lock in list(self.stage863_budget_locks.items()):
            active_volume = self._stage863_active_volume(str(lock["product_vt_symbol"]), str(lock["direction"]))
            if active_volume > 0:
                continue
            released.append(key)
            self.stage863_budget_locks.pop(key, None)
            self._stage863_append_budget_event(
                {
                    "datetime": getattr(self.strategy_engine, "datetime", None),
                    "date": "",
                    "vt_symbol": str(lock.get("created_vt_symbol", "")),
                    "product_vt_symbol": str(lock["product_vt_symbol"]),
                    "contract_vt_symbol": str(lock.get("created_vt_symbol", "")),
                    "position_direction": str(lock["direction"]),
                    "direction": str(lock["direction"]),
                    "offset": "RiskLock",
                    "reason": "stage863_budget_lock_released_flat",
                    "entry_context": "flat_observed",
                    "price": 0.0,
                    "volume": 0,
                    "selected_volume_before": 0,
                    "selected_volume_after": 0,
                    "reduced_volume": 0,
                    "locked_source_volume": 0,
                    "active_volume": 0,
                    "lock_ceiling_volume": int(lock.get("ceiling_volume") or 0),
                    "source_final_state": str(lock.get("source_final_state", "")),
                    "source_trade_id": str(lock.get("source_trade_id", "")),
                }
            )
        if released:
            self.stage863_budget_locks = dict(self.stage863_budget_locks)

    def _stage863_apply_budget_lock_to_volume(
        self,
        *,
        vt_symbol: str,
        product_vt_symbol: str,
        direction: str,
        proposed_volume: int,
        entry_context: str,
        signal: str,
        price: float,
        event_datetime: Any,
    ) -> tuple[int, dict[str, Any]]:
        before = max(0, int(proposed_volume))
        fields: dict[str, Any] = {
            "stage863_budget_lock_enabled": int(bool(self.enable_stage863_stop_retry_budget_lock)),
            "stage863_budget_lock_applied": 0,
            "stage863_budget_lock_reason": "disabled",
            "stage863_budget_lock_selected_volume_before": before,
            "stage863_budget_lock_selected_volume_after": before,
            "stage863_budget_lock_reduced_volume": 0,
            "stage863_budget_lock_ceiling_volume": np.nan,
            "stage863_budget_lock_active_volume": self._stage863_active_volume(product_vt_symbol, direction),
            "stage863_budget_lock_remaining_volume": np.nan,
        }
        if not bool(self.enable_stage863_stop_retry_budget_lock):
            return before, fields
        self._stage863_prune_budget_locks()
        fields["stage863_budget_lock_reason"] = "no_active_lock"
        if before <= 0:
            fields["stage863_budget_lock_reason"] = "zero_selected_volume"
            return before, fields

        key = self._stage863_lock_key(product_vt_symbol, direction)
        lock = self.stage863_budget_locks.get(key)
        if not lock:
            return before, fields

        active_volume = self._stage863_active_volume(product_vt_symbol, direction)
        ceiling_volume = max(0, int(lock.get("ceiling_volume") or 0))
        remaining = max(0, ceiling_volume - active_volume)
        after = min(before, remaining)
        if 0 < after < self.min_position_size:
            after = 0
        reduced = max(0, before - after)
        reason = "within_stage863_budget_lock"
        if reduced > 0:
            reason = "stage863_budget_lock_reduce" if after > 0 else "stage863_budget_lock_block"
            self.stage863_budget_lock_reduce_count += 1
            if after <= 0:
                self.stage863_budget_lock_block_count += 1
            self._stage863_append_budget_event(
                {
                    "datetime": event_datetime,
                    "date": pd.Timestamp(event_datetime).normalize().date().isoformat()
                    if event_datetime is not None
                    else "",
                    "vt_symbol": str(vt_symbol),
                    "product_vt_symbol": str(product_vt_symbol),
                    "contract_vt_symbol": str(vt_symbol),
                    "position_direction": str(direction),
                    "direction": str(direction),
                    "offset": "RiskSizing",
                    "reason": reason,
                    "entry_context": entry_context,
                    "price": float(price or 0.0),
                    "volume": reduced,
                    "signal": signal,
                    "selected_volume_before": before,
                    "selected_volume_after": after,
                    "reduced_volume": reduced,
                    "active_volume": active_volume,
                    "lock_ceiling_volume": ceiling_volume,
                    "remaining_volume": remaining,
                    "source_final_state": str(lock.get("source_final_state", "")),
                    "source_trade_id": str(lock.get("source_trade_id", "")),
                }
            )

        fields.update(
            {
                "stage863_budget_lock_applied": int(reduced > 0),
                "stage863_budget_lock_reason": reason,
                "stage863_budget_lock_selected_volume_after": after,
                "stage863_budget_lock_reduced_volume": reduced,
                "stage863_budget_lock_ceiling_volume": ceiling_volume,
                "stage863_budget_lock_active_volume": active_volume,
                "stage863_budget_lock_remaining_volume": remaining,
            }
        )
        return after, fields

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
        product_vt_symbol = self.source_symbol_by_contract.get(vt_symbol, self._product_vt_symbol(vt_symbol))
        after, fields = self._stage863_apply_budget_lock_to_volume(
            vt_symbol=vt_symbol,
            product_vt_symbol=product_vt_symbol,
            direction=direction,
            proposed_volume=int(sizing.get("selected_volume") or 0),
            entry_context=entry_context,
            signal=str(signal_data.get("signal", "")),
            price=float(getattr(bar, "close_price", 0.0) or 0.0),
            event_datetime=getattr(bar, "datetime", None),
        )
        sizing["selected_volume"] = after
        sizing.update(fields)
        return sizing

    def _stage863_adjust_add_volume(self, state: Any, proposed_volume: int, entry_context: str) -> int:
        after, _ = self._stage863_apply_budget_lock_to_volume(
            vt_symbol=str(getattr(state, "contract_vt_symbol", "")),
            product_vt_symbol=str(getattr(state, "product_vt_symbol", "")),
            direction=str(getattr(state, "direction", "")),
            proposed_volume=proposed_volume,
            entry_context=entry_context,
            signal=entry_context,
            price=0.0,
            event_datetime=getattr(self.strategy_engine, "datetime", None),
        )
        return after

    def _calculate_post_entry_quality_add_volume(self, state: Any) -> int:
        volume = super()._calculate_post_entry_quality_add_volume(state)
        return self._stage863_adjust_add_volume(state, volume, "post_quality_add")

    def _calculate_regular_add_volume(self, state: Any) -> int:
        volume = super()._calculate_regular_add_volume(state)
        return self._stage863_adjust_add_volume(state, volume, "regular_add")

    def _calculate_donchian_add_volume(self, state: Any) -> int:
        volume = super()._calculate_donchian_add_volume(state)
        return self._stage863_adjust_add_volume(state, volume, "donchian_add")


def _c10_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C10_ARM}_2018",
        label="Stage863 Stage819 C4 plus C9 stop/retry with product-direction budget lock",
        note=(
            f"{spec.capital.note} | Stage863 C10. Keep Stage847/C9 0.5R stop and one same-day reclaim retry. "
            "After a stop/retry event, the same product-direction cannot add or reopen above the stopped/reentered "
            "volume while that direction remains active; the lock releases only after the direction is flat."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage863_stop_retry_budget_lock": True,
    }
    result = dict(profile)
    result["profile"] = C10_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage863C10BudgetLock
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    return result


def _run_profile(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s827.s778.s653.s517.START_DT
    original_end = s827.s778.s653.s517.END_DT
    original_preload = s827.s778.s653.s517.PRELOAD_START_DT
    try:
        s827.s778.s653.s517.START_DT = START.to_pydatetime()
        s827.s778.s653.s517.END_DT = END.to_pydatetime()
        s827.s778.s653.s517.PRELOAD_START_DT = s827.s772._preload_for_start(START).to_pydatetime()

        s827.s778.s653.s517.assert_stage196_database_sentinels()
        s827.s778.s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(
            s827.s778.s653.s517.PRELOAD_START_DT,
            s827.s778.s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta(),
        )
        _, open_map = s827.s778.s653.s517.s506.s501._seed_proxy_maps()
        engine = s847.Stage847StopRetryEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s827.Interval.DAILY,
            start=preload_start,
            end=s827.s778.s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s827.s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=dict(s513._c3_overrides(START.to_pydatetime())),
            start=START,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result: {profile['profile']}")

        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= START.date()) & (daily.index <= END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        positions = s827.s778.build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            margin_daily, _ = s513._position_margin(positions, metadata)
        else:
            margin_daily = pd.DataFrame(
                columns=["variant", "combo_variant", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            )
        combined = s827.s772._combine_daily(daily, margin_daily, spec)
        strategy = getattr(engine, "strategy", None)
        c2_events = pd.DataFrame(getattr(strategy, "stage827_intraday_c2_events", []) if strategy else [])
        stop_retry_events = pd.DataFrame(getattr(strategy, "stage847_stop_retry_events", []) if strategy else [])
        if not stop_retry_events.empty and "synthetic_trades" in stop_retry_events.columns:
            stop_retry_events = stop_retry_events.drop(columns=["synthetic_trades"])
        budget_lock_events = pd.DataFrame(getattr(strategy, "stage863_budget_lock_events", []) if strategy else [])
        intraday_events = pd.concat([c2_events, stop_retry_events], ignore_index=True, sort=False)
        frames = {
            "trades": s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "budget_lock_events": budget_lock_events,
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["start_month"] = START.strftime("%Y-%m")
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s827.s778.s653.s517.START_DT = original_start
        s827.s778.s653.s517.END_DT = original_end
        s827.s778.s653.s517.PRELOAD_START_DT = original_preload


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    c4 = summary[summary["arm"].eq(C4_ARM)].iloc[0]
    c9 = summary[summary["arm"].eq(C9_ARM)].iloc[0]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        rows.append(
            {
                "arm": row["arm"],
                "end_equity": row["end_equity"],
                "end_equity_delta_vs_C4": row["end_equity"] - c4["end_equity"],
                "end_equity_delta_vs_C9": row["end_equity"] - c9["end_equity"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_pct": row["max_dd_pct"],
                "max_dd_delta_vs_C4": row["max_dd_pct"] - c4["max_dd_pct"],
                "max_dd_delta_vs_C9": row["max_dd_pct"] - c9["max_dd_pct"],
                "sharpe": row["sharpe"],
                "sharpe_delta_vs_C4": row["sharpe"] - c4["sharpe"],
                "sharpe_delta_vs_C9": row["sharpe"] - c9["sharpe"],
                "total_slippage": row["total_slippage"],
                "total_trade_count": row["total_trade_count"],
                "win_rate_pct": row["nonzero_daily_win_rate_pct"],
                "max_broker10_margin_to_equity_pct": row.get("max_broker10_margin_to_equity_pct", np.nan),
                "p95_broker10_margin_to_equity_pct": row.get("p95_broker10_margin_to_equity_pct", np.nan),
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve[curve["arm"].isin([C4_ARM, C9_ARM, C10_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {C4_ARM: "#16a34a", C9_ARM: "#7c3aed", C10_ARM: "#0891b2"}
    labels = {
        C4_ARM: "C4 broker10 cap",
        C9_ARM: "C9 0.5R stop + retry",
        C10_ARM: "C10 C9 + budget lock",
    }
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[1].plot(group["date"], group["drawdown_pct"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[2].plot(
            group["date"],
            group["broker10_margin_to_equity_pct"],
            label=labels.get(arm, arm),
            color=colors.get(arm),
        )
    axes[0].set_title("Stage863 equity path")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _path_diagnostics(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve[curve["arm"].isin([C4_ARM, C9_ARM, C10_ARM])].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed").dt.normalize()
    rows: list[dict[str, Any]] = []
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        trough = group.loc[group["drawdown_pct"].idxmin()]
        before = group[group["date"].le(trough["date"])]
        peak = before.loc[before["account_equity"].idxmax()]
        rows.append(
            {
                "arm": arm,
                "peak_date": pd.Timestamp(peak["date"]).date().isoformat(),
                "peak_equity": float(peak["account_equity"]),
                "trough_date": pd.Timestamp(trough["date"]).date().isoformat(),
                "trough_equity": float(trough["account_equity"]),
                "trough_dd_pct": float(trough["drawdown_pct"]),
                "max_broker10_margin_to_equity_pct": float(group["broker10_margin_to_equity_pct"].max()),
                "p95_broker10_margin_to_equity_pct": float(group["broker10_margin_to_equity_pct"].quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def _events_by_reason(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["reduced_volume"] = pd.to_numeric(data.get("reduced_volume", 0), errors="coerce").fillna(0.0)
    return (
        data.groupby(["profile", "reason"], dropna=False)
        .agg(events=("reason", "size"), reduced_volume=("reduced_volume", "sum"))
        .reset_index()
        .sort_values(["profile", "events"], ascending=[True, False])
    )


def _write_report(
    comparison: pd.DataFrame,
    path_diag: pd.DataFrame,
    stop_retry_events: pd.DataFrame,
    budget_lock_events: pd.DataFrame,
) -> None:
    effective_budget = (
        budget_lock_events[
            budget_lock_events["reason"].astype(str).isin(["stage863_budget_lock_reduce", "stage863_budget_lock_block"])
        ].copy()
        if not budget_lock_events.empty and "reason" in budget_lock_events.columns
        else pd.DataFrame()
    )
    c10_row = comparison[comparison["arm"].eq(C10_ARM)].iloc[0] if not comparison.empty else pd.Series(dtype=object)
    c10_changed_c9 = any(
        abs(_safe_float(c10_row.get(column), 0.0)) > 1e-9
        for column in ["end_equity_delta_vs_C9", "max_dd_delta_vs_C9", "sharpe_delta_vs_C9"]
    )
    lines = [
        "# Stage863 C10 止损重试预算锁真实引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：Stage819 候选研究线隔离回放；不改 Stage372 正式实盘版本、不改候选配置、不连接 CTP、不调用下单。",
        "- 分钟K口径：使用 Stage861 full minute bars，即 Stage825 原始分钟源 + Stage860 patch 去重后的全周期覆盖。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py GitHub：https://github.com/vnpy/vnpy",
        "- backtesting.py 逐 bar 回放文档：https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html",
        "- 我的判断：外部资料只支持事件驱动回放和风险约束隔离的工程纪律，不能提供可直接搬用的日内阈值；本阶段沿用已冻结的 Stage847 参数，不新增参数搜索。",
        "",
        "## 预声明规则",
        "",
        "- C4：Stage830/C4，C2 同日 `1R` 止损 + broker10 projected margin/equity `100%` 上限。",
        "- C9：Stage847/C9，在 C4 之上加入 `0.5R` 先逆向止损、同日重回原入场价只重试一次、二次 `0.5R` 失败即平。",
        "- C10：保持 C9；当同品种同方向触发止损重试事件后，只要该方向仍有持仓，后续 flat/reverse/add sizing 不能让新增手数超过锁内剩余额度；方向归零后释放。",
        "- 不扫描 R 倍数、重试次数、年份、品种、方向、分钟窗口或 OR 过滤。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Path Diagnostics",
        "",
        _md_table(path_diag, max_rows=10),
        "",
        "## Stop/Retry Events By Final State",
        "",
        _md_table(s847._stop_retry_event_summary(stop_retry_events), max_rows=20),
        "",
        "## Budget Lock Events By Reason",
        "",
        _md_table(_events_by_reason(budget_lock_events), max_rows=20),
        "",
        "## Chart",
        "",
        f"- path chart：`{PATH_CHART_PATH}`",
        "",
        "## Judgment",
        "",
        (
            "- 本轮结果：C10 与 C9 路径完全重合，预算锁只有创建/释放事件，没有产生真实 `reduce/block`；"
            "因此 Stage863 不是有效新增规则，不能晋级。"
            if effective_budget.empty and not c10_changed_c9
            else "- 本轮结果：C10 已改变 C9 路径，需要按收益、回撤和 broker10 路径综合判定。"
        ),
        "- 若 C10 不能在 C9 基础上修复回撤或 broker10 路径，则说明 Stage847 的主要问题不只是加仓预算复用，应停止在该分支继续微调。",
        "- 若 C10 保留 C9 收益且回撤/broker10 变好，下一步才允许做成本压力和滚动起点稳定性，不直接晋级官方版本。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = _load_stage861_full_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profiles = [s830._cap_profile(metadata), s847._c9_profile(metadata), _c10_profile(metadata)]
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    merged_frames: dict[str, list[pd.DataFrame]] = {
        "trades": [],
        "entry_risk": [],
        "entry_candidates": [],
        "trade_events": [],
        "intraday_events": [],
        "stop_retry_events": [],
        "budget_lock_events": [],
    }
    closed_frames: list[pd.DataFrame] = []

    for profile in profiles:
        combined, frames = _run_profile(profile, metadata)
        summary, curve = s827._metric(profile, combined)
        summary["arm"] = profile["profile"]
        curve["arm"] = profile["profile"]
        summaries.append(summary)
        curves.append(curve)
        for key in merged_frames:
            frame = frames.get(key, pd.DataFrame())
            if not frame.empty:
                merged_frames[key].append(frame)
        trades = frames.get("trades", pd.DataFrame()).copy()
        entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
        entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
        closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
        if not closed.empty:
            closed["arm"] = profile["profile"]
            closed["variant"] = profile["spec"].capital.variant
            closed_frames.append(closed)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    comparison = _comparison(summary)
    output_frames = {
        key: pd.concat(value, ignore_index=True, sort=False) if value else pd.DataFrame()
        for key, value in merged_frames.items()
    }
    output_frames["closed_lots"] = pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame()
    path_diag = _path_diagnostics(curve)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    output_frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    output_frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["intraday_events"].to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["stop_retry_events"].to_csv(STOP_RETRY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["budget_lock_events"].to_csv(BUDGET_LOCK_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["closed_lots"].to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(
        comparison,
        path_diag,
        output_frames["stop_retry_events"],
        output_frames["budget_lock_events"],
    )

    c10_row = comparison[comparison["arm"].eq(C10_ARM)].iloc[0].to_dict()
    c9_row = comparison[comparison["arm"].eq(C9_ARM)].iloc[0].to_dict()
    budget_events = output_frames["budget_lock_events"]
    effective_budget_events = (
        budget_events[budget_events["reason"].astype(str).isin(["stage863_budget_lock_reduce", "stage863_budget_lock_block"])]
        if not budget_events.empty and "reason" in budget_events.columns
        else pd.DataFrame()
    )
    c10_changed_c9 = any(
        abs(float(c10_row[column])) > 1e-9
        for column in ["end_equity_delta_vs_C9", "max_dd_delta_vs_C9", "sharpe_delta_vs_C9"]
    )
    c10_beats_c9_return = float(c10_row["end_equity_delta_vs_C9"]) >= 0
    c10_repairs_c9_dd = float(c10_row["max_dd_delta_vs_C9"]) >= 0
    c10_repairs_c9_broker = float(c10_row["max_broker10_margin_to_equity_pct"]) <= float(
        c9_row["max_broker10_margin_to_equity_pct"]
    )
    decision_label = (
        "stage863_c10_no_effect_budget_lock_not_promoted"
        if effective_budget_events.empty and not c10_changed_c9
        else "stage863_c10_promising_needs_cost_and_rolling_start_stress"
        if c10_beats_c9_return and c10_repairs_c9_dd and c10_repairs_c9_broker
        else "stage863_c10_budget_lock_not_promoted"
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "minute_source": {
            "stage861_full_minute_bars": str(s861.FULL_MINUTE_BARS_PATH),
            "loaded_minute_bars": int(len(minute_bars)),
            "loaded_symbols": int(minute_bars["vt_symbol"].astype(str).nunique()) if not minute_bars.empty else 0,
        },
        "rule_type": "c9_stop_retry_with_product_direction_budget_lock",
        "rule": {
            "base_arm": C4_ARM,
            "stop_retry_r": s847.STOP_RETRY_R,
            "max_retries": s847.MAX_RETRIES,
            "budget_lock_scope": "same product-direction while active",
            "budget_lock_release": "flat observed",
            "no_parameter_scan": True,
        },
        "event_summary": {
            "stop_retry_events": int(len(output_frames["stop_retry_events"])),
            "budget_lock_events": int(len(budget_events)),
            "budget_lock_created": int(budget_events["reason"].astype(str).eq("stage863_budget_lock_created").sum())
            if not budget_events.empty
            else 0,
            "budget_lock_blocked": int(budget_events["reason"].astype(str).eq("stage863_budget_lock_block").sum())
            if not budget_events.empty
            else 0,
            "budget_lock_reduced_volume": float(
                pd.to_numeric(effective_budget_events.get("reduced_volume", 0), errors="coerce").fillna(0).sum()
            )
            if not effective_budget_events.empty
            else 0.0,
            "budget_lock_effective_events": int(len(effective_budget_events)),
            "c10_changed_vs_c9": bool(c10_changed_c9),
        },
        "comparison": comparison.to_dict("records"),
        "path_diagnostics": path_diag.to_dict("records"),
        "budget_lock_by_reason": _events_by_reason(budget_events).to_dict("records") if not budget_events.empty else [],
        "decision": decision_label,
        "candidate_result": c10_row,
        "overfit_reflection": (
            "不是过拟合式调参。本阶段只在 Stage847 已冻结的 0.5R/一次重试规则外增加一个非参数化的预算复用约束，"
            "且用 Stage861 全量分钟K统一重跑 C4/C9/C10，没有按年份、品种、方向或阈值筛选。"
        ),
        "continue_value": (
            "C10 本轮没有改变 C9 路径，说明同品种同方向加仓预算锁不是当前矛盾；仍有价值继续研究 C9 本身，"
            "但下一步应归因 broker10 峰值来自哪一天/哪组持仓，而不是继续微调这个锁。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "comparison": str(COMPARISON_PATH),
            "curve": str(CURVE_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "stop_retry_events": str(STOP_RETRY_EVENTS_PATH),
            "budget_lock_events": str(BUDGET_LOCK_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))
    print("budget_lock_by_reason")
    print(_events_by_reason(budget_events).to_string(index=False) if not budget_events.empty else "empty")


if __name__ == "__main__":
    main()

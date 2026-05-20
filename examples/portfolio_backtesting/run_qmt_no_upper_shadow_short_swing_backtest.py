from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_no_lower_shadow_swing_backtest import (
    ANNUAL_TRADING_DAYS,
    DEFAULT_CAPITAL,
    DEFAULT_END,
    DEFAULT_MAPPING_PATH,
    DEFAULT_MAX_CONCURRENT_POSITIONS,
    DEFAULT_RISK_RATIO,
    DEFAULT_START,
    DEFAULT_UNIVERSE_PATH,
    MAX_CAPITAL_USAGE_RATIO,
    MAX_SINGLE_TRADE_CAPITAL_USAGE_RATIO,
    BacktestConfig,
    MarketBar,
    OUTPUT_DIR,
    Position,
    _active_margin,
    _bar,
    _load_inputs,
    _mapping_indexes,
    _tick_units,
    _trade_cost,
    first_day_half_exit_volume,
)


MODEL_TAG = "no_upper_shadow_short_swing_stage006"
COMPARE_PREFIX = "qmt_no_upper_shadow_short_swing_stage006"
STOP_MODE_RUNS: tuple[tuple[str, str], ...] = (
    ("signal2_high", "qmt_no_upper_shadow_short_swing_stage006_signal2high"),
    ("two_signal_high", "qmt_no_upper_shadow_short_swing_stage006_twosignalhigh"),
)

SUMMARY_CSV = OUTPUT_DIR / f"{COMPARE_PREFIX}_summary.csv"
SUMMARY_JSON = OUTPUT_DIR / f"{COMPARE_PREFIX}_summary.json"
REPORT_MD = OUTPUT_DIR / f"{COMPARE_PREFIX}_report.md"


def is_strict_no_upper_shadow_falling(bar: MarketBar, pricetick: float) -> bool:
    """Strict short signal bar: rounded open equals high, and close is below open."""
    if min(bar.open, bar.high, bar.close) <= 0:
        return False
    open_units = _tick_units(bar.open, pricetick)
    high_units = _tick_units(bar.high, pricetick)
    close_units = _tick_units(bar.close, pricetick)
    return open_units == high_units and close_units < open_units


def calculate_short_position_size(
    *,
    equity: float,
    risk_ratio: float,
    entry_price: float,
    stop_price: float,
    size: int,
    pricetick: float,
    margin_ratio: float,
    active_margin: float,
    capital_usage_ratio: float = MAX_CAPITAL_USAGE_RATIO,
    single_trade_capital_usage_ratio: float = MAX_SINGLE_TRADE_CAPITAL_USAGE_RATIO,
) -> dict[str, Any]:
    risk_amount = max(0.0, equity * risk_ratio)
    risk_distance = stop_price - entry_price
    min_risk_per_contract = max(pricetick * size, 1.0)
    risk_per_contract = max(risk_distance * size, min_risk_per_contract)
    margin_per_contract = entry_price * size * max(margin_ratio, 0.0)
    allowed_margin = max(0.0, equity * capital_usage_ratio - active_margin)
    single_trade_margin = max(0.0, equity * single_trade_capital_usage_ratio)

    contracts_by_risk = int(risk_amount // risk_per_contract) if risk_per_contract > 0 else 0
    contracts_by_margin = int(allowed_margin // margin_per_contract) if margin_per_contract > 0 else 0
    contracts_by_single_trade_cap = int(single_trade_margin // margin_per_contract) if margin_per_contract > 0 else 0
    selected_volume = max(0, min(contracts_by_risk, contracts_by_margin, contracts_by_single_trade_cap))

    return {
        "risk_amount": risk_amount,
        "risk_distance": risk_distance,
        "risk_per_contract": risk_per_contract,
        "margin_per_contract": margin_per_contract,
        "allowed_margin": allowed_margin,
        "single_trade_margin": single_trade_margin,
        "contracts_by_risk": contracts_by_risk,
        "contracts_by_margin": contracts_by_margin,
        "contracts_by_single_trade_cap": contracts_by_single_trade_cap,
        "selected_volume": selected_volume,
    }


def update_trailing_stop_short(current_stop: float, previous_high: float) -> float:
    return min(float(current_stop), float(previous_high))


def stop_exit_price_short(bar: MarketBar, stop_price: float) -> float | None:
    if stop_price <= 0:
        return None
    if bar.open >= stop_price:
        return float(bar.open)
    if bar.high >= stop_price:
        return float(stop_price)
    return None


def stop_anchor_price_short(signal_bar_1: MarketBar, signal_bar_2: MarketBar, stop_mode: str) -> float:
    if stop_mode == "signal2_high":
        return float(signal_bar_2.high)
    if stop_mode == "two_signal_high":
        return max(float(signal_bar_1.high), float(signal_bar_2.high))
    raise ValueError(f"Unsupported stop_mode: {stop_mode}")


def _position_unrealized_short(
    position: Position,
    bar_cache: dict[str, dict[pd.Timestamp, MarketBar]],
    date: pd.Timestamp,
) -> float:
    bar = _bar(bar_cache, position.contract_vt_symbol, date)
    price = bar.close if bar is not None else position.entry_price
    return (position.entry_price - price) * position.size * position.volume


class NoUpperShadowShortSwingBacktester:
    def __init__(
        self,
        config: BacktestConfig,
        mapping: pd.DataFrame,
        metadata: dict[str, Any],
        bar_cache: dict[str, dict[pd.Timestamp, MarketBar]],
        *,
        stop_mode: str,
    ) -> None:
        self.config = config
        self.mapping = mapping
        self.metadata = metadata
        self.bar_cache = bar_cache
        self.product_dates, self.contract_by_product_date = _mapping_indexes(mapping)
        self.priceticks: dict[str, float] = metadata["priceticks"]
        self.sizes: dict[str, int] = metadata["sizes"]
        self.margin_ratios: dict[str, float] = metadata["margin_ratios"]
        self.rates: dict[str, float] = metadata["rates"]
        self.slippages: dict[str, float] = metadata["slippages"]
        self.stop_mode = stop_mode

        self.cash = float(config.capital)
        self.positions: dict[str, Position] = {}
        self.daily_rows: list[dict[str, Any]] = []
        self.trade_rows: list[dict[str, Any]] = []
        self.position_rows: list[dict[str, Any]] = []
        self.candidate_rows: list[dict[str, Any]] = []
        self.roundtrip_rows: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        all_dates = sorted(
            {
                date
                for dates in self.product_dates.values()
                for date in dates
                if pd.Timestamp(self.config.start) <= date <= pd.Timestamp(self.config.end)
            }
        )
        previous_equity = float(self.config.capital)
        for date in all_dates:
            trade_count_before = len(self.trade_rows)
            self._prepare_stops_before_open(date)
            self._open_new_positions(date, previous_equity)
            self._process_open_positions(date)
            daily = self._build_daily_row(date, previous_equity, len(self.trade_rows) - trade_count_before)
            self.daily_rows.append(daily)
            previous_equity = float(daily["balance"])
            self._record_end_positions(date)
        return self._statistics()

    def _prepare_stops_before_open(self, date: pd.Timestamp) -> None:
        for product, position in list(self.positions.items()):
            if position.entry_date >= date:
                continue
            product_dates = self.product_dates.get(product, [])
            if date not in product_dates:
                continue
            index = product_dates.index(date)
            if index <= 0:
                continue
            previous_date = product_dates[index - 1]
            previous_contract = self.contract_by_product_date.get((product, previous_date), "")
            if previous_contract != position.contract_vt_symbol:
                continue
            previous_bar = _bar(self.bar_cache, position.contract_vt_symbol, previous_date)
            if previous_bar is None:
                continue
            position.stop_price = update_trailing_stop_short(position.stop_price, previous_bar.high)

    def _open_new_positions(self, date: pd.Timestamp, equity_before_open: float) -> None:
        if equity_before_open <= 0:
            return

        active_at_open = len(self.positions)
        active_margin = _active_margin(self.positions, self.bar_cache, date)
        for product in sorted(self.product_dates):
            if product in self.positions:
                continue
            product_dates = self.product_dates[product]
            if date not in product_dates:
                continue
            index = product_dates.index(date)
            if index < 2:
                continue

            signal_date_1 = product_dates[index - 2]
            signal_date_2 = product_dates[index - 1]
            entry_contract = self.contract_by_product_date.get((product, date), "")
            signal_contract_1 = self.contract_by_product_date.get((product, signal_date_1), "")
            signal_contract_2 = self.contract_by_product_date.get((product, signal_date_2), "")
            if not entry_contract or not signal_contract_1 or not signal_contract_2:
                continue

            pricetick = float(self.priceticks.get(entry_contract, 1.0) or 1.0)
            signal_bar_1 = _bar(self.bar_cache, signal_contract_1, signal_date_1)
            signal_bar_2 = _bar(self.bar_cache, signal_contract_2, signal_date_2)
            entry_bar = _bar(self.bar_cache, entry_contract, date)
            if signal_bar_1 is None or signal_bar_2 is None:
                continue
            if not (
                is_strict_no_upper_shadow_falling(signal_bar_1, pricetick)
                and is_strict_no_upper_shadow_falling(signal_bar_2, pricetick)
            ):
                continue

            base_row = {
                "candidate_index": len(self.candidate_rows) + 1,
                "date": date.date().isoformat(),
                "product_vt_symbol": product,
                "signal_date_1": signal_date_1.date().isoformat(),
                "signal_date_2": signal_date_2.date().isoformat(),
                "signal_contract_1": signal_contract_1,
                "signal_contract_2": signal_contract_2,
                "entry_contract_vt_symbol": entry_contract,
                "signal": "two_strict_no_upper_shadow_falling",
                "direction": "short",
                "stop_mode": self.stop_mode,
                "estimated_equity": equity_before_open,
                "active_positions_before": active_at_open,
                "max_concurrent_positions": self.config.max_concurrent_positions,
            }
            if signal_contract_1 != entry_contract or signal_contract_2 != entry_contract:
                self._record_candidate(base_row, "skipped", "rollover_between_signal_and_entry")
                continue
            if entry_bar is None:
                self._record_candidate(base_row, "skipped", "missing_entry_bar")
                continue
            if active_at_open >= self.config.max_concurrent_positions:
                self._record_candidate(base_row, "skipped", "max_concurrent_positions")
                continue

            entry_price = float(entry_bar.open)
            stop_price = stop_anchor_price_short(signal_bar_1, signal_bar_2, self.stop_mode)
            size = int(self.sizes.get(entry_contract, 1) or 1)
            margin_ratio = float(self.margin_ratios.get(entry_contract, 0.15) or 0.15)
            sizing = calculate_short_position_size(
                equity=equity_before_open,
                risk_ratio=self.config.risk_ratio,
                entry_price=entry_price,
                stop_price=stop_price,
                size=size,
                pricetick=pricetick,
                margin_ratio=margin_ratio,
                active_margin=active_margin,
            )
            base_row.update(
                {
                    "entry_price": entry_price,
                    "entry_bar_open": float(entry_bar.open),
                    "entry_bar_high": float(entry_bar.high),
                    "entry_bar_low": float(entry_bar.low),
                    "entry_bar_close": float(entry_bar.close),
                    "stop_price": stop_price,
                    "stop_distance": stop_price - entry_price,
                    "size": size,
                    "pricetick": pricetick,
                    "margin_ratio": margin_ratio,
                    **sizing,
                }
            )
            if entry_price >= stop_price:
                self._record_candidate(base_row, "skipped", "entry_open_not_below_stop")
                continue
            volume = int(sizing["selected_volume"])
            if volume <= 0:
                reason = "risk_budget_below_one_contract"
                if int(sizing["contracts_by_risk"]) > 0 and int(sizing["contracts_by_margin"]) <= 0:
                    reason = "margin_budget_below_one_contract"
                elif int(sizing["contracts_by_risk"]) > 0 and int(sizing["contracts_by_single_trade_cap"]) <= 0:
                    reason = "single_trade_cap_below_one_contract"
                self._record_candidate(base_row, "skipped", reason)
                continue

            rate = float(self.rates.get(entry_contract, 0.0) or 0.0)
            slippage = float(self.slippages.get(entry_contract, pricetick) or pricetick)
            cost, commission_cash, slippage_cash = _trade_cost(
                entry_price,
                volume,
                size=size,
                rate=rate,
                slippage=slippage,
            )
            self.cash -= cost
            position = Position(
                product_vt_symbol=product,
                contract_vt_symbol=entry_contract,
                entry_date=date,
                entry_price=entry_price,
                stop_price=stop_price,
                volume=volume,
                original_volume=volume,
                size=size,
                pricetick=pricetick,
                margin_ratio=margin_ratio,
                rate=rate,
                slippage=slippage,
                lifecycle_pnl=-cost,
                lifecycle_slippage=slippage_cash,
                lifecycle_commission=commission_cash,
            )
            self.positions[product] = position
            active_at_open += 1
            active_margin += float(sizing["margin_per_contract"]) * volume
            base_row["planned_half_exit_volume"] = first_day_half_exit_volume(volume)
            self._record_candidate(base_row, "opened", "")
            self._record_trade(
                date=date,
                product=product,
                contract=entry_contract,
                direction="Short",
                offset="Open",
                reason="entry_open_short",
                price=entry_price,
                volume=volume,
                commission=commission_cash,
                slippage_cash=slippage_cash,
                pnl=0.0,
            )

    def _record_candidate(self, row: dict[str, Any], status: str, reason: str) -> None:
        item = dict(row)
        item["candidate_status"] = status
        item["skip_reason"] = reason
        self.candidate_rows.append(item)

    def _process_open_positions(self, date: pd.Timestamp) -> None:
        for product, position in list(self.positions.items()):
            target_contract = self.contract_by_product_date.get((product, date), "")
            bar = _bar(self.bar_cache, position.contract_vt_symbol, date)
            if target_contract and target_contract != position.contract_vt_symbol:
                exit_bar = bar or _bar(self.bar_cache, target_contract, date)
                if exit_bar is not None:
                    self._close_position(product, position, exit_bar.close, date, "rollover_forced_exit")
                continue
            if bar is None:
                continue

            exit_price = stop_exit_price_short(bar, position.stop_price)
            if exit_price is not None:
                reason = "short_initial_stop" if position.entry_date == date else "short_trailing_stop"
                if bar.open >= position.stop_price:
                    reason = "short_gap_stop"
                self._close_position(product, position, exit_price, date, reason)
                continue

            if position.entry_date == date and not position.half_exit_done:
                reduce_volume = first_day_half_exit_volume(position.volume)
                position.half_exit_done = True
                if reduce_volume <= 0:
                    continue
                self._reduce_position(product, position, reduce_volume, bar.close, date, "first_day_half_exit")

    def _reduce_position(
        self,
        product: str,
        position: Position,
        volume: int,
        price: float,
        date: pd.Timestamp,
        reason: str,
    ) -> None:
        close_volume = min(max(0, int(volume)), position.volume)
        if close_volume <= 0:
            return
        cost, commission_cash, slippage_cash = _trade_cost(
            price,
            close_volume,
            size=position.size,
            rate=position.rate,
            slippage=position.slippage,
        )
        pnl = (position.entry_price - price) * position.size * close_volume
        net_pnl = pnl - cost
        self.cash += net_pnl
        position.lifecycle_pnl += net_pnl
        position.lifecycle_slippage += slippage_cash
        position.lifecycle_commission += commission_cash
        position.volume -= close_volume
        self._record_trade(
            date=date,
            product=product,
            contract=position.contract_vt_symbol,
            direction="Long",
            offset="Close",
            reason=reason,
            price=price,
            volume=close_volume,
            commission=commission_cash,
            slippage_cash=slippage_cash,
            pnl=net_pnl,
        )
        if position.volume <= 0:
            self._record_roundtrip(position, date, reason)
            self.positions.pop(product, None)

    def _close_position(self, product: str, position: Position, price: float, date: pd.Timestamp, reason: str) -> None:
        self._reduce_position(product, position, position.volume, price, date, reason)

    def _record_roundtrip(self, position: Position, exit_date: pd.Timestamp, exit_reason: str) -> None:
        self.roundtrip_rows.append(
            {
                "product_vt_symbol": position.product_vt_symbol,
                "contract_vt_symbol": position.contract_vt_symbol,
                "entry_date": position.entry_date.date().isoformat(),
                "exit_date": exit_date.date().isoformat(),
                "exit_reason": exit_reason,
                "original_volume": position.original_volume,
                "entry_price": position.entry_price,
                "final_stop_price": position.stop_price,
                "net_pnl": position.lifecycle_pnl,
                "slippage": position.lifecycle_slippage,
                "commission": position.lifecycle_commission,
                "holding_days": int((exit_date - position.entry_date).days) + 1,
            }
        )

    def _record_trade(
        self,
        *,
        date: pd.Timestamp,
        product: str,
        contract: str,
        direction: str,
        offset: str,
        reason: str,
        price: float,
        volume: int,
        commission: float,
        slippage_cash: float,
        pnl: float,
    ) -> None:
        self.trade_rows.append(
            {
                "trade_index": len(self.trade_rows) + 1,
                "datetime": date.isoformat(),
                "date": date.date().isoformat(),
                "product_vt_symbol": product,
                "vt_symbol": contract,
                "direction": direction,
                "offset": offset,
                "reason": reason,
                "price": price,
                "volume": int(volume),
                "turnover": price * volume,
                "commission": commission,
                "slippage": slippage_cash,
                "net_pnl": pnl,
            }
        )

    def _build_daily_row(self, date: pd.Timestamp, previous_equity: float, trade_count: int) -> dict[str, Any]:
        unrealized = sum(_position_unrealized_short(position, self.bar_cache, date) for position in self.positions.values())
        balance = self.cash + unrealized
        net_pnl = balance - previous_equity
        active_margin = _active_margin(self.positions, self.bar_cache, date)
        peak = max([self.config.capital, *[float(row["balance"]) for row in self.daily_rows], balance])
        drawdown = balance - peak
        drawdown_pct = drawdown / peak * 100.0 if peak > 0 else 0.0
        todays_trades = [row for row in self.trade_rows if row["date"] == date.date().isoformat()]
        return {
            "date": date.date().isoformat(),
            "balance": balance,
            "net_pnl": net_pnl,
            "return_pct": net_pnl / previous_equity * 100.0 if previous_equity > 0 else 0.0,
            "drawdown": drawdown,
            "drawdown_pct": drawdown_pct,
            "active_positions": len(self.positions),
            "active_margin": active_margin,
            "trade_count": trade_count,
            "turnover": sum(float(row["turnover"]) for row in todays_trades),
            "commission": sum(float(row["commission"]) for row in todays_trades),
            "slippage": sum(float(row["slippage"]) for row in todays_trades),
        }

    def _record_end_positions(self, date: pd.Timestamp) -> None:
        for position in self.positions.values():
            bar = _bar(self.bar_cache, position.contract_vt_symbol, date)
            close_price = bar.close if bar is not None else position.entry_price
            self.position_rows.append(
                {
                    "date": date.date().isoformat(),
                    "product_vt_symbol": position.product_vt_symbol,
                    "contract_vt_symbol": position.contract_vt_symbol,
                    "direction": "short",
                    "volume": position.volume,
                    "entry_date": position.entry_date.date().isoformat(),
                    "entry_price": position.entry_price,
                    "close_price": close_price,
                    "stop_price": position.stop_price,
                    "unrealized_pnl": (position.entry_price - close_price) * position.size * position.volume,
                    "half_exit_done": int(position.half_exit_done),
                }
            )

    def _statistics(self) -> dict[str, Any]:
        daily = pd.DataFrame(self.daily_rows)
        trades = pd.DataFrame(self.trade_rows)
        roundtrips = pd.DataFrame(self.roundtrip_rows)
        if daily.empty:
            end_balance = self.config.capital
            returns = pd.Series(dtype="float64")
            max_drawdown = 0.0
            max_dd_percent = 0.0
        else:
            end_balance = float(daily["balance"].iloc[-1])
            returns = pd.to_numeric(daily["return_pct"], errors="coerce").fillna(0.0) / 100.0
            max_drawdown = float(pd.to_numeric(daily["drawdown"], errors="coerce").min())
            max_dd_percent = float(pd.to_numeric(daily["drawdown_pct"], errors="coerce").min())
        std = float(returns.std(ddof=0)) if not returns.empty else 0.0
        sharpe = float(returns.mean() / std * math.sqrt(ANNUAL_TRADING_DAYS)) if std > 0 else 0.0
        wins = int((roundtrips["net_pnl"] > 0).sum()) if not roundtrips.empty else 0
        total_roundtrips = int(len(roundtrips))
        win_ratio = wins / total_roundtrips * 100.0 if total_roundtrips else 0.0
        return {
            "model_tag": MODEL_TAG,
            "analysis_start": self.config.start.date().isoformat(),
            "analysis_end": self.config.end.date().isoformat(),
            "capital": self.config.capital,
            "risk_ratio": self.config.risk_ratio,
            "direction": "short",
            "signal": "two_strict_no_upper_shadow_falling",
            "stop_mode": self.stop_mode,
            "end_balance": end_balance,
            "total_return_pct": (end_balance / self.config.capital - 1.0) * 100.0 if self.config.capital else 0.0,
            "max_drawdown": max_drawdown,
            "max_dd_percent": max_dd_percent,
            "sharpe_ratio": sharpe,
            "total_trade_count": int(len(trades)),
            "round_trip_count": total_roundtrips,
            "win_count": wins,
            "win_ratio_pct": win_ratio,
            "total_slippage": float(trades["slippage"].sum()) if not trades.empty else 0.0,
            "total_commission": float(trades["commission"].sum()) if not trades.empty else 0.0,
            "candidate_count": int(len(self.candidate_rows)),
            "opened_candidate_count": int(
                sum(1 for row in self.candidate_rows if row.get("candidate_status") == "opened")
            ),
            "open_positions_end": int(len(self.positions)),
        }

    def output_frames(self) -> dict[str, pd.DataFrame]:
        return {
            "daily": pd.DataFrame(self.daily_rows),
            "trades": pd.DataFrame(self.trade_rows),
            "positions": pd.DataFrame(self.position_rows),
            "candidates": pd.DataFrame(self.candidate_rows),
            "roundtrips": pd.DataFrame(self.roundtrip_rows),
        }


def _summary_table(df: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if df.empty or group_column not in df.columns:
        return pd.DataFrame()
    grouped = df.groupby(group_column, dropna=False)
    return grouped.agg(
        net_pnl=("net_pnl", "sum"),
        round_trip_count=("net_pnl", "size"),
        win_ratio_pct=("net_pnl", lambda values: float((values > 0).mean() * 100.0)),
        avg_holding_days=("holding_days", "mean"),
        slippage=("slippage", "sum"),
        commission=("commission", "sum"),
    ).reset_index()


def _markdown_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _build_variant_report(
    stats: dict[str, Any],
    product_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    exit_summary: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# 期货无上影线空头波段 Stage006 归因报告",
            "",
            "## 总览",
            "",
            f"- 止损锚点：`{stats['stop_mode']}`",
            f"- 期末权益：`{stats['end_balance']:,.2f}`",
            f"- 总收益：`{stats['total_return_pct']:.4f}%`",
            f"- 最大回撤：`{stats['max_dd_percent']:.4f}%`",
            f"- Sharpe：`{stats['sharpe_ratio']:.4f}`",
            f"- 候选数/开仓数：`{stats['candidate_count']}` / `{stats['opened_candidate_count']}`",
            f"- 总交易次数：`{stats['total_trade_count']}`",
            f"- 胜率：`{stats['win_ratio_pct']:.4f}%`",
            f"- 总滑点：`{stats['total_slippage']:,.2f}`",
            "",
            "## 年度归因",
            "",
            _markdown_table(year_summary),
            "",
            "## 品种归因",
            "",
            _markdown_table(product_summary.sort_values("net_pnl", ascending=False) if not product_summary.empty else product_summary),
            "",
            "## 退出原因归因",
            "",
            _markdown_table(exit_summary),
            "",
        ]
    )


def _write_outputs(config: BacktestConfig, stats: dict[str, Any], frames: dict[str, pd.DataFrame]) -> dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = config.output_prefix
    paths: dict[str, str] = {}
    for name, frame in frames.items():
        path = OUTPUT_DIR / f"{prefix}_{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        paths[name] = str(path)

    stats_path = OUTPUT_DIR / f"{prefix}_statistics.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["statistics"] = str(stats_path)

    roundtrips = frames["roundtrips"].copy()
    if not roundtrips.empty:
        roundtrips["entry_year"] = pd.to_datetime(roundtrips["entry_date"]).dt.year
    product_summary = _summary_table(roundtrips, "product_vt_symbol")
    year_summary = _summary_table(roundtrips, "entry_year")
    exit_summary = _summary_table(roundtrips, "exit_reason")

    for name, frame in {
        "product_summary": product_summary,
        "year_summary": year_summary,
        "exit_reason_summary": exit_summary,
    }.items():
        path = OUTPUT_DIR / f"{prefix}_{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        paths[name] = str(path)

    report_path = OUTPUT_DIR / f"{prefix}_attribution_report.md"
    report_path.write_text(_build_variant_report(stats, product_summary, year_summary, exit_summary), encoding="utf-8")
    paths["report"] = str(report_path)
    return paths


def _exit_reason_stats(roundtrips: pd.DataFrame) -> dict[str, dict[str, float]]:
    if roundtrips.empty:
        return {}
    grouped = roundtrips.groupby("exit_reason", dropna=False).agg(
        count=("net_pnl", "size"),
        net_pnl=("net_pnl", "sum"),
    )
    return {
        str(index): {"count": int(row["count"]), "net_pnl": float(row["net_pnl"])}
        for index, row in grouped.iterrows()
    }


def _skip_reason_stats(candidates: pd.DataFrame) -> dict[str, int]:
    if candidates.empty:
        return {}
    skipped = candidates[candidates["candidate_status"].astype(str).eq("skipped")].copy()
    if skipped.empty:
        return {}
    counts = skipped["skip_reason"].fillna("").astype(str).value_counts().sort_index()
    return {str(index): int(value) for index, value in counts.items()}


def _summary_row(
    *,
    stop_mode: str,
    output_prefix: str,
    stats: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    paths: dict[str, str],
) -> dict[str, Any]:
    exit_stats = _exit_reason_stats(frames["roundtrips"])
    initial_stop = exit_stats.get("short_initial_stop", {"count": 0, "net_pnl": 0.0})
    trailing_stop = exit_stats.get("short_trailing_stop", {"count": 0, "net_pnl": 0.0})
    gap_stop = exit_stats.get("short_gap_stop", {"count": 0, "net_pnl": 0.0})
    rollover = exit_stats.get("rollover_forced_exit", {"count": 0, "net_pnl": 0.0})
    first_day_half = frames["trades"]
    if not first_day_half.empty:
        first_day_half = first_day_half[first_day_half["reason"].astype(str).eq("first_day_half_exit")]
    return {
        "model_tag": MODEL_TAG,
        "direction": "short",
        "signal": "two_strict_no_upper_shadow_falling",
        "stop_mode": stop_mode,
        "output_prefix": output_prefix,
        "candidate_count": stats["candidate_count"],
        "opened_candidate_count": stats["opened_candidate_count"],
        "round_trip_count": stats["round_trip_count"],
        "total_trade_count": stats["total_trade_count"],
        "end_balance": stats["end_balance"],
        "total_return_pct": stats["total_return_pct"],
        "max_dd_percent": stats["max_dd_percent"],
        "sharpe_ratio": stats["sharpe_ratio"],
        "win_ratio_pct": stats["win_ratio_pct"],
        "total_slippage": stats["total_slippage"],
        "first_day_half_exit_count": int(len(first_day_half)),
        "first_day_half_exit_net_pnl": float(first_day_half["net_pnl"].sum()) if not first_day_half.empty else 0.0,
        "initial_stop_count": initial_stop["count"],
        "initial_stop_net_pnl": initial_stop["net_pnl"],
        "trailing_stop_count": trailing_stop["count"],
        "trailing_stop_net_pnl": trailing_stop["net_pnl"],
        "gap_stop_count": gap_stop["count"],
        "gap_stop_net_pnl": gap_stop["net_pnl"],
        "rollover_count": rollover["count"],
        "rollover_net_pnl": rollover["net_pnl"],
        "skip_summary": _skip_reason_stats(frames["candidates"]),
        "exit_summary": exit_stats,
        "paths": paths,
    }


def _build_compare_report(summary_df: pd.DataFrame, rows: list[dict[str, Any]]) -> str:
    key_columns = [
        "stop_mode",
        "candidate_count",
        "opened_candidate_count",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "win_ratio_pct",
        "initial_stop_count",
        "initial_stop_net_pnl",
        "trailing_stop_net_pnl",
        "total_slippage",
    ]
    lines = [
        "# 期货无上影线空头波段 Stage006 对比",
        "",
        "## 参数",
        "",
        "- 信号：连续两根严格 `open == high` 且 `close < open`。",
        "- 方向：只做空。",
        "- 入场：第三天主力合约开盘价做空。",
        "- 首日处理：若未先触发止损，收盘回补一半；一手仓无法减半则保留。",
        "- 移动止损：剩余仓以前一交易日最高价做只下移止损。",
        "- 止损锚点：`signal2_high` 与 `two_signal_high` 两档。",
        "",
        "## 核心结果",
        "",
        _markdown_table(summary_df[key_columns]),
        "",
        "## 跳过与退出摘要",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['stop_mode']}",
                "",
                f"- skip_summary：`{json.dumps(row['skip_summary'], ensure_ascii=False)}`",
                f"- exit_summary：`{json.dumps(row['exit_summary'], ensure_ascii=False)}`",
                f"- report：`{row['paths'].get('report', '')}`",
                "",
            ]
        )
    return "\n".join(lines)


def run_compare(base_config: BacktestConfig) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping, metadata, bar_cache = _load_inputs(base_config)
    rows: list[dict[str, Any]] = []
    for stop_mode, output_prefix in STOP_MODE_RUNS:
        config = replace(base_config, output_prefix=output_prefix, save_outputs=True)
        backtester = NoUpperShadowShortSwingBacktester(config, mapping, metadata, bar_cache, stop_mode=stop_mode)
        stats = backtester.run()
        frames = backtester.output_frames()
        paths = _write_outputs(config, stats, frames)
        rows.append(
            _summary_row(
                stop_mode=stop_mode,
                output_prefix=output_prefix,
                stats=stats,
                frames=frames,
                paths=paths,
            )
        )

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")
    SUMMARY_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_build_compare_report(summary_df, rows), encoding="utf-8")
    return summary_df, rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run no-upper-shadow short-only futures swing backtest.")
    parser.add_argument("--start", default=DEFAULT_START.date().isoformat())
    parser.add_argument("--end", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    parser.add_argument("--risk-ratio", type=float, default=DEFAULT_RISK_RATIO)
    parser.add_argument("--max-concurrent", type=int, default=DEFAULT_MAX_CONCURRENT_POSITIONS)
    parser.add_argument("--mapping-path", default=str(DEFAULT_MAPPING_PATH))
    parser.add_argument("--universe-path", default=str(DEFAULT_UNIVERSE_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_config = BacktestConfig(
        start=datetime.fromisoformat(args.start),
        end=datetime.fromisoformat(args.end),
        capital=float(args.capital),
        risk_ratio=float(args.risk_ratio),
        max_concurrent_positions=int(args.max_concurrent),
        mapping_path=Path(args.mapping_path),
        universe_path=Path(args.universe_path),
        save_outputs=True,
    )
    summary_df, rows = run_compare(base_config)
    print(summary_df.to_json(orient="records", force_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "summary_csv": str(SUMMARY_CSV.resolve()),
                "summary_json": str(SUMMARY_JSON.resolve()),
                "report": str(REPORT_MD.resolve()),
                "variant_reports": {row["stop_mode"]: row["paths"].get("report", "") for row in rows},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

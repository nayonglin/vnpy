from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_no_lower_shadow_swing_backtest import (
    DEFAULT_CAPITAL,
    DEFAULT_END,
    DEFAULT_MAPPING_PATH,
    DEFAULT_MAX_CONCURRENT_POSITIONS,
    DEFAULT_RISK_RATIO,
    DEFAULT_START,
    DEFAULT_UNIVERSE_PATH,
    BacktestConfig,
    MarketBar,
    NoLowerShadowSwingBacktester,
    OUTPUT_DIR,
    Position,
    _active_margin,
    _bar,
    _load_inputs,
    _trade_cost,
    _write_outputs,
    calculate_position_size,
    first_day_half_exit_volume,
    is_no_lower_shadow_rising,
)
from run_qmt_no_lower_shadow_swing_top_down_weekly_stage008 import (
    WEEKLY_MA_WEEKS,
    WEEKLY_WARMUP_DAYS,
    _build_adjusted_index_for_product,
    _exit_reason_stats,
    _markdown_table,
    _skip_reason_stats,
    build_weekly_trend_state_map,
)


MODEL_TAG = "no_lower_shadow_swing_top_down_pullback_stage009"
OUTPUT_PREFIX = "qmt_no_lower_shadow_swing_stage009_weekly_pullback_ignition"
DAILY_MA_DAYS = 20
PULLBACK_LOOKBACK_DAYS = 5
PULLBACK_MA_BUFFER_PCT = 0.01
RECENT_IGNITION_BLOCK_DAYS = 3
SUMMARY_JSON = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_down_summary.json"
REPORT_MD = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_down_report.md"


@dataclass(frozen=True)
class PullbackIgnitionState:
    product_vt_symbol: str
    date: pd.Timestamp
    adjusted_close: float
    daily_ma20: float
    previous_close: float
    previous_5_low: float
    pullback_near_ma20: bool
    close_above_ma20: bool
    close_above_previous: bool
    setup_passed: bool


def _normalize_date(value: object) -> pd.Timestamp:
    return pd.Timestamp(value).tz_localize(None).normalize()


def _daily_pullback_table(adjusted_daily: pd.DataFrame) -> pd.DataFrame:
    if adjusted_daily.empty:
        return pd.DataFrame()
    table = adjusted_daily[["date", "adjusted_close"]].copy()
    table.sort_values("date", inplace=True)
    close = pd.to_numeric(table["adjusted_close"], errors="coerce")
    table["daily_ma20"] = close.rolling(DAILY_MA_DAYS, min_periods=DAILY_MA_DAYS).mean()
    table["previous_close"] = close.shift(1)
    table["previous_5_low"] = close.shift(1).rolling(PULLBACK_LOOKBACK_DAYS, min_periods=PULLBACK_LOOKBACK_DAYS).min()
    table["pullback_near_ma20"] = table["previous_5_low"] <= table["daily_ma20"] * (1.0 + PULLBACK_MA_BUFFER_PCT)
    table["close_above_ma20"] = close > table["daily_ma20"]
    table["close_above_previous"] = close > table["previous_close"]
    table["setup_passed"] = (
        table["daily_ma20"].notna()
        & table["previous_close"].notna()
        & table["previous_5_low"].notna()
        & table["pullback_near_ma20"].fillna(False)
        & table["close_above_ma20"].fillna(False)
        & table["close_above_previous"].fillna(False)
    )
    return table


def build_pullback_state_map(
    *,
    product_dates: dict[str, list[pd.Timestamp]],
    contract_by_product_date: dict[tuple[str, pd.Timestamp], str],
    bar_cache: dict[str, dict[pd.Timestamp, MarketBar]],
) -> dict[tuple[str, pd.Timestamp], PullbackIgnitionState]:
    state_map: dict[tuple[str, pd.Timestamp], PullbackIgnitionState] = {}
    for product, dates in product_dates.items():
        adjusted_daily = _build_adjusted_index_for_product(
            product=product,
            product_dates=dates,
            contract_by_product_date=contract_by_product_date,
            bar_cache=bar_cache,
        )
        table = _daily_pullback_table(adjusted_daily)
        for row in table.itertuples(index=False):
            date = _normalize_date(row.date)
            state_map[(product, date)] = PullbackIgnitionState(
                product_vt_symbol=product,
                date=date,
                adjusted_close=float(row.adjusted_close),
                daily_ma20=float(row.daily_ma20) if pd.notna(row.daily_ma20) else math.nan,
                previous_close=float(row.previous_close) if pd.notna(row.previous_close) else math.nan,
                previous_5_low=float(row.previous_5_low) if pd.notna(row.previous_5_low) else math.nan,
                pullback_near_ma20=bool(row.pullback_near_ma20) if pd.notna(row.pullback_near_ma20) else False,
                close_above_ma20=bool(row.close_above_ma20) if pd.notna(row.close_above_ma20) else False,
                close_above_previous=bool(row.close_above_previous) if pd.notna(row.close_above_previous) else False,
                setup_passed=bool(row.setup_passed) if pd.notna(row.setup_passed) else False,
            )
    return state_map


def _recent_strict_ignition_exists(
    *,
    product: str,
    signal_index: int,
    product_dates: list[pd.Timestamp],
    contract_by_product_date: dict[tuple[str, pd.Timestamp], str],
    bar_cache: dict[str, dict[pd.Timestamp, MarketBar]],
    pricetick: float,
    lookback_days: int = RECENT_IGNITION_BLOCK_DAYS,
) -> bool:
    start_index = max(0, signal_index - lookback_days)
    for previous_index in range(start_index, signal_index):
        previous_date = product_dates[previous_index]
        previous_contract = contract_by_product_date.get((product, previous_date), "")
        previous_bar = _bar(bar_cache, previous_contract, previous_date) if previous_contract else None
        if previous_bar is not None and is_no_lower_shadow_rising(previous_bar, pricetick, "strict"):
            return True
    return False


def _pullback_stop_price(
    *,
    product: str,
    signal_index: int,
    product_dates: list[pd.Timestamp],
    contract: str,
    contract_by_product_date: dict[tuple[str, pd.Timestamp], str],
    bar_cache: dict[str, dict[pd.Timestamp, MarketBar]],
    lookback_days: int = PULLBACK_LOOKBACK_DAYS,
) -> tuple[float, int]:
    start_index = max(0, signal_index - lookback_days)
    lows: list[float] = []
    for index in range(start_index, signal_index + 1):
        date = product_dates[index]
        if contract_by_product_date.get((product, date), "") != contract:
            continue
        bar = _bar(bar_cache, contract, date)
        if bar is not None:
            lows.append(float(bar.low))
    if not lows:
        return math.nan, 0
    return min(lows), len(lows)


class WeeklyPullbackIgnitionBacktester(NoLowerShadowSwingBacktester):
    def __init__(
        self,
        config: BacktestConfig,
        mapping: pd.DataFrame,
        metadata: dict[str, Any],
        bar_cache: dict[str, dict[pd.Timestamp, MarketBar]],
    ) -> None:
        super().__init__(config, mapping, metadata, bar_cache)
        self.weekly_state_map = build_weekly_trend_state_map(
            product_dates=self.product_dates,
            contract_by_product_date=self.contract_by_product_date,
            bar_cache=bar_cache,
        )
        self.pullback_state_map = build_pullback_state_map(
            product_dates=self.product_dates,
            contract_by_product_date=self.contract_by_product_date,
            bar_cache=bar_cache,
        )

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
            if index < 1:
                continue

            signal_index = index - 1
            signal_date = product_dates[signal_index]
            entry_contract = self.contract_by_product_date.get((product, date), "")
            signal_contract = self.contract_by_product_date.get((product, signal_date), "")
            if not entry_contract or not signal_contract:
                continue

            pricetick = float(self.priceticks.get(entry_contract, 1.0) or 1.0)
            signal_bar = _bar(self.bar_cache, signal_contract, signal_date)
            entry_bar = _bar(self.bar_cache, entry_contract, date)
            if signal_bar is None:
                continue
            if not is_no_lower_shadow_rising(signal_bar, pricetick, self.config.signal_variant):
                continue

            weekly_state = self.weekly_state_map.get((product, _normalize_date(date)))
            pullback_state = self.pullback_state_map.get((product, _normalize_date(signal_date)))
            recent_ignition = _recent_strict_ignition_exists(
                product=product,
                signal_index=signal_index,
                product_dates=product_dates,
                contract_by_product_date=self.contract_by_product_date,
                bar_cache=self.bar_cache,
                pricetick=pricetick,
            )
            base_row = {
                "candidate_index": len(self.candidate_rows) + 1,
                "date": date.date().isoformat(),
                "product_vt_symbol": product,
                "signal_date": signal_date.date().isoformat(),
                "signal_contract": signal_contract,
                "entry_contract_vt_symbol": entry_contract,
                "signal": f"first_{self.config.signal_variant}_no_lower_shadow_after_pullback",
                "signal_variant": self.config.signal_variant,
                "direction": "long",
                "top_down_filter": "previous_completed_week_close_gt_ma20_and_ma20_slope_up",
                "pullback_filter": "previous_5d_low_near_ma20_then_strict_no_lower_shadow_reclaim_ma20",
                "weekly_state_date": (
                    weekly_state.weekly_state_date.date().isoformat()
                    if weekly_state and weekly_state.weekly_state_date is not None
                    else ""
                ),
                "weekly_adjusted_close": weekly_state.adjusted_close if weekly_state else math.nan,
                "weekly_ma20": weekly_state.weekly_ma20 if weekly_state else math.nan,
                "weekly_ma20_prev": weekly_state.weekly_ma20_prev if weekly_state else math.nan,
                "weekly_ma20_slope": weekly_state.weekly_ma20_slope if weekly_state else math.nan,
                "weekly_warmup_ready": int(bool(weekly_state.weekly_warmup_ready)) if weekly_state else 0,
                "weekly_trend_up": int(bool(weekly_state.weekly_trend_up)) if weekly_state else 0,
                "weekly_trend_gate_passed": int(bool(weekly_state and weekly_state.weekly_trend_up)),
                "daily_adjusted_close": pullback_state.adjusted_close if pullback_state else math.nan,
                "daily_ma20": pullback_state.daily_ma20 if pullback_state else math.nan,
                "previous_close": pullback_state.previous_close if pullback_state else math.nan,
                "previous_5_low": pullback_state.previous_5_low if pullback_state else math.nan,
                "pullback_near_ma20": int(bool(pullback_state.pullback_near_ma20)) if pullback_state else 0,
                "close_above_ma20": int(bool(pullback_state.close_above_ma20)) if pullback_state else 0,
                "close_above_previous": int(bool(pullback_state.close_above_previous)) if pullback_state else 0,
                "pullback_setup_passed": int(bool(pullback_state.setup_passed)) if pullback_state else 0,
                "recent_ignition_blocked": int(recent_ignition),
                "stop_mode": "pullback_low",
                "estimated_equity": equity_before_open,
                "active_positions_before": active_at_open,
                "max_concurrent_positions": self.config.max_concurrent_positions,
            }
            if signal_contract != entry_contract:
                self._record_candidate(base_row, "skipped", "rollover_between_signal_and_entry")
                continue
            if entry_bar is None:
                self._record_candidate(base_row, "skipped", "missing_entry_bar")
                continue
            if weekly_state is None or not weekly_state.weekly_warmup_ready:
                self._record_candidate(base_row, "skipped", "weekly_trend_warmup_missing")
                continue
            if not weekly_state.weekly_trend_up:
                self._record_candidate(base_row, "skipped", "weekly_trend_gate_failed")
                continue
            if pullback_state is None or not pullback_state.setup_passed:
                self._record_candidate(base_row, "skipped", "pullback_setup_failed")
                continue
            if recent_ignition:
                self._record_candidate(base_row, "skipped", "recent_ignition_already_fired")
                continue
            if active_at_open >= self.config.max_concurrent_positions:
                self._record_candidate(base_row, "skipped", "max_concurrent_positions")
                continue

            stop_price, stop_bar_count = _pullback_stop_price(
                product=product,
                signal_index=signal_index,
                product_dates=product_dates,
                contract=entry_contract,
                contract_by_product_date=self.contract_by_product_date,
                bar_cache=self.bar_cache,
            )
            base_row["pullback_stop_bar_count"] = stop_bar_count
            if not math.isfinite(stop_price) or stop_bar_count < 3:
                self._record_candidate(base_row, "skipped", "pullback_stop_history_missing")
                continue

            entry_price = float(entry_bar.open)
            size = int(self.sizes.get(entry_contract, 1) or 1)
            margin_ratio = float(self.margin_ratios.get(entry_contract, 0.15) or 0.15)
            sizing = calculate_position_size(
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
                    "entry_bar_low": float(entry_bar.low),
                    "entry_bar_close": float(entry_bar.close),
                    "stop_price": stop_price,
                    "stop_distance": entry_price - stop_price,
                    "size": size,
                    "pricetick": pricetick,
                    "margin_ratio": margin_ratio,
                    **sizing,
                }
            )
            if entry_price <= stop_price:
                self._record_candidate(base_row, "skipped", "entry_open_not_above_stop")
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
                direction="Long",
                offset="Open",
                reason="entry_open_weekly_pullback_ignition",
                price=entry_price,
                volume=volume,
                commission=commission_cash,
                slippage_cash=slippage_cash,
                pnl=0.0,
            )

    def _statistics(self) -> dict[str, Any]:
        stats = super()._statistics()
        candidates = pd.DataFrame(self.candidate_rows)
        if candidates.empty:
            weekly_pass = 0
            pullback_pass = 0
            recent_blocks = 0
        else:
            weekly_pass = int(pd.to_numeric(candidates.get("weekly_trend_gate_passed"), errors="coerce").fillna(0).sum())
            pullback_pass = int(pd.to_numeric(candidates.get("pullback_setup_passed"), errors="coerce").fillna(0).sum())
            recent_blocks = int(pd.to_numeric(candidates.get("recent_ignition_blocked"), errors="coerce").fillna(0).sum())
        stats.update(
            {
                "model_tag": MODEL_TAG,
                "top_down_filter": "previous_completed_week_close_gt_ma20_and_ma20_slope_up",
                "pullback_filter": "previous_5d_low_near_ma20_then_strict_no_lower_shadow_reclaim_ma20",
                "weekly_ma_weeks": WEEKLY_MA_WEEKS,
                "daily_ma_days": DAILY_MA_DAYS,
                "pullback_lookback_days": PULLBACK_LOOKBACK_DAYS,
                "pullback_ma_buffer_pct": PULLBACK_MA_BUFFER_PCT,
                "recent_ignition_block_days": RECENT_IGNITION_BLOCK_DAYS,
                "stop_mode": "pullback_low",
                "weekly_gate_pass_count": weekly_pass,
                "pullback_setup_pass_count": pullback_pass,
                "recent_ignition_block_count": recent_blocks,
            }
        )
        return stats


def _build_top_down_report(
    *,
    stats: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    paths: dict[str, str],
) -> str:
    roundtrips = frames["roundtrips"].copy()
    if not roundtrips.empty:
        roundtrips["entry_year"] = pd.to_datetime(roundtrips["entry_date"]).dt.year
    year_summary = (
        roundtrips.groupby("entry_year", dropna=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            round_trip_count=("net_pnl", "size"),
            win_ratio_pct=("net_pnl", lambda values: float((values > 0).mean() * 100.0)),
            slippage=("slippage", "sum"),
        )
        .reset_index()
        if not roundtrips.empty
        else pd.DataFrame()
    )
    product_summary = (
        roundtrips.groupby("product_vt_symbol", dropna=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            round_trip_count=("net_pnl", "size"),
            win_ratio_pct=("net_pnl", lambda values: float((values > 0).mean() * 100.0)),
            slippage=("slippage", "sum"),
        )
        .reset_index()
        if not roundtrips.empty
        else pd.DataFrame()
    )
    exit_summary = (
        roundtrips.groupby("exit_reason", dropna=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            round_trip_count=("net_pnl", "size"),
            win_ratio_pct=("net_pnl", lambda values: float((values > 0).mean() * 100.0)),
            slippage=("slippage", "sum"),
        )
        .reset_index()
        if not roundtrips.empty
        else pd.DataFrame()
    )
    return "\n".join(
        [
            "# 期货无下影线波段 Stage009 看大做小回撤点火报告",
            "",
            "## 参数",
            "",
            "- 大周期：上一完整周的连续收益指数收盘 > 20周均线，且20周均线斜率向上。",
            "- 中周期：过去5日最低的连续收益指数触及/低于20日均线1%缓冲范围。",
            "- 小周期：第一根日线 strict `open == low` 且 `close > open`，并收回20日均线上方。",
            "- 冷却：信号日前3日不能已有 strict 无下影线点火。",
            "- 入场：信号次日开盘做多。",
            "- 止损：过去5日回撤低点和信号日低点的低点。",
            "",
            "## 总览",
            "",
            f"- 期末权益：`{stats['end_balance']:,.2f}`",
            f"- 总收益：`{stats['total_return_pct']:.4f}%`",
            f"- 最大回撤：`{stats['max_dd_percent']:.4f}%`",
            f"- Sharpe：`{stats['sharpe_ratio']:.4f}`",
            f"- 候选数/开仓数：`{stats['candidate_count']}` / `{stats['opened_candidate_count']}`",
            f"- 周线门通过数：`{stats['weekly_gate_pass_count']}`",
            f"- 回撤点火条件通过数：`{stats['pullback_setup_pass_count']}`",
            f"- 近期点火阻断数：`{stats['recent_ignition_block_count']}`",
            f"- 总交易次数：`{stats['total_trade_count']}`",
            f"- 胜率：`{stats['win_ratio_pct']:.4f}%`",
            f"- 总滑点：`{stats['total_slippage']:,.2f}`",
            "",
            "## 跳过摘要",
            "",
            f"`{json.dumps(_skip_reason_stats(frames['candidates']), ensure_ascii=False)}`",
            "",
            "## 退出摘要",
            "",
            f"`{json.dumps(_exit_reason_stats(frames['roundtrips']), ensure_ascii=False)}`",
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
            "## 输出",
            "",
            f"- statistics：`{paths.get('statistics', '')}`",
            f"- candidates：`{paths.get('candidates', '')}`",
            f"- trades：`{paths.get('trades', '')}`",
            f"- roundtrips：`{paths.get('roundtrips', '')}`",
            "",
        ]
    )


def run_backtest(config: BacktestConfig) -> tuple[dict[str, Any], dict[str, pd.DataFrame], dict[str, str]]:
    load_config = replace(config, start=config.start - timedelta(days=WEEKLY_WARMUP_DAYS))
    mapping, metadata, bar_cache = _load_inputs(load_config)
    backtester = WeeklyPullbackIgnitionBacktester(config, mapping, metadata, bar_cache)
    stats = backtester.run()
    frames = backtester.output_frames()
    paths = _write_outputs(config, stats, frames) if config.save_outputs else {}
    if config.save_outputs:
        summary = {
            "stats": stats,
            "skip_summary": _skip_reason_stats(frames["candidates"]),
            "exit_summary": _exit_reason_stats(frames["roundtrips"]),
            "paths": paths,
        }
        SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        REPORT_MD.write_text(_build_top_down_report(stats=stats, frames=frames, paths=paths), encoding="utf-8")
        paths["top_down_summary"] = str(SUMMARY_JSON)
        paths["top_down_report"] = str(REPORT_MD)
    return stats, frames, paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run top-down weekly pullback ignition no-lower-shadow Stage009.")
    parser.add_argument("--start", default=DEFAULT_START.date().isoformat())
    parser.add_argument("--end", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    parser.add_argument("--risk-ratio", type=float, default=DEFAULT_RISK_RATIO)
    parser.add_argument("--max-concurrent", type=int, default=DEFAULT_MAX_CONCURRENT_POSITIONS)
    parser.add_argument("--mapping-path", default=str(DEFAULT_MAPPING_PATH))
    parser.add_argument("--universe-path", default=str(DEFAULT_UNIVERSE_PATH))
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    parser.add_argument("--no-save", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BacktestConfig(
        start=datetime.fromisoformat(args.start),
        end=datetime.fromisoformat(args.end),
        capital=float(args.capital),
        risk_ratio=float(args.risk_ratio),
        max_concurrent_positions=int(args.max_concurrent),
        mapping_path=Path(args.mapping_path),
        universe_path=Path(args.universe_path),
        output_prefix=str(args.output_prefix),
        signal_variant="strict",
        save_outputs=not bool(args.no_save),
    )
    stats, _, paths = run_backtest(config)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if paths:
        print(json.dumps(paths, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

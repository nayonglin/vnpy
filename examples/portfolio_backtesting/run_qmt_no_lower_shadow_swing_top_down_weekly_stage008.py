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
    ANNUAL_TRADING_DAYS,
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


MODEL_TAG = "no_lower_shadow_swing_top_down_weekly_stage008"
OUTPUT_PREFIX = "qmt_no_lower_shadow_swing_stage008_weekly_trend_long"
WEEKLY_MA_WEEKS = 20
WEEKLY_WARMUP_DAYS = 540
SUMMARY_JSON = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_down_summary.json"
REPORT_MD = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_down_report.md"


@dataclass(frozen=True)
class WeeklyTrendState:
    product_vt_symbol: str
    date: pd.Timestamp
    weekly_state_date: pd.Timestamp | None
    adjusted_close: float
    weekly_ma20: float
    weekly_ma20_prev: float
    weekly_ma20_slope: float
    weekly_trend_up: bool
    weekly_warmup_ready: bool


def _normalize_date(value: object) -> pd.Timestamp:
    return pd.Timestamp(value).tz_localize(None).normalize()


def _build_adjusted_index_for_product(
    *,
    product: str,
    product_dates: list[pd.Timestamp],
    contract_by_product_date: dict[tuple[str, pd.Timestamp], str],
    bar_cache: dict[str, dict[pd.Timestamp, MarketBar]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    adjusted_close = 100.0
    previous_date: pd.Timestamp | None = None
    for date in sorted(product_dates):
        contract = contract_by_product_date.get((product, date), "")
        bar = _bar(bar_cache, contract, date) if contract else None
        if bar is None or bar.close <= 0:
            continue
        if previous_date is not None:
            previous_same_contract_bar = _bar(bar_cache, contract, previous_date)
            if previous_same_contract_bar is not None and previous_same_contract_bar.close > 0:
                daily_return = float(bar.close) / float(previous_same_contract_bar.close) - 1.0
            else:
                # Roll day without same-contract previous close: neutralize the spread jump.
                daily_return = 0.0
            adjusted_close *= max(0.01, 1.0 + daily_return)
        rows.append(
            {
                "date": date,
                "contract_vt_symbol": contract,
                "raw_close": float(bar.close),
                "adjusted_close": float(adjusted_close),
            }
        )
        previous_date = date
    return pd.DataFrame(rows)


def _weekly_trend_table(adjusted_daily: pd.DataFrame, ma_weeks: int = WEEKLY_MA_WEEKS) -> pd.DataFrame:
    if adjusted_daily.empty:
        return pd.DataFrame()
    series = adjusted_daily.set_index("date")["adjusted_close"].sort_index()
    weekly_close = series.resample("W-FRI").last().dropna()
    if weekly_close.empty:
        return pd.DataFrame()
    weekly = pd.DataFrame({"adjusted_close": weekly_close})
    weekly["weekly_ma20"] = weekly["adjusted_close"].rolling(ma_weeks, min_periods=ma_weeks).mean()
    weekly["weekly_ma20_prev"] = weekly["weekly_ma20"].shift(1)
    weekly["weekly_ma20_slope"] = weekly["weekly_ma20"] - weekly["weekly_ma20_prev"]
    weekly["weekly_trend_up"] = (
        (weekly["adjusted_close"] > weekly["weekly_ma20"])
        & (weekly["weekly_ma20"] > weekly["weekly_ma20_prev"])
    )
    weekly["weekly_warmup_ready"] = weekly["weekly_ma20"].notna() & weekly["weekly_ma20_prev"].notna()
    return weekly


def last_completed_weekly_state(
    weekly: pd.DataFrame,
    *,
    product: str,
    date: pd.Timestamp,
) -> WeeklyTrendState:
    date = _normalize_date(date)
    if weekly.empty:
        return WeeklyTrendState(product, date, None, math.nan, math.nan, math.nan, math.nan, False, False)
    eligible = weekly[weekly.index < date]
    if eligible.empty:
        return WeeklyTrendState(product, date, None, math.nan, math.nan, math.nan, math.nan, False, False)
    row = eligible.iloc[-1]
    state_date = _normalize_date(eligible.index[-1])
    warmup_ready = bool(row.get("weekly_warmup_ready", False))
    trend_up = bool(row.get("weekly_trend_up", False)) if warmup_ready else False
    return WeeklyTrendState(
        product_vt_symbol=product,
        date=date,
        weekly_state_date=state_date,
        adjusted_close=float(row.get("adjusted_close", math.nan)),
        weekly_ma20=float(row.get("weekly_ma20", math.nan)),
        weekly_ma20_prev=float(row.get("weekly_ma20_prev", math.nan)),
        weekly_ma20_slope=float(row.get("weekly_ma20_slope", math.nan)),
        weekly_trend_up=trend_up,
        weekly_warmup_ready=warmup_ready,
    )


def build_weekly_trend_state_map(
    *,
    product_dates: dict[str, list[pd.Timestamp]],
    contract_by_product_date: dict[tuple[str, pd.Timestamp], str],
    bar_cache: dict[str, dict[pd.Timestamp, MarketBar]],
) -> dict[tuple[str, pd.Timestamp], WeeklyTrendState]:
    state_map: dict[tuple[str, pd.Timestamp], WeeklyTrendState] = {}
    for product, dates in product_dates.items():
        adjusted_daily = _build_adjusted_index_for_product(
            product=product,
            product_dates=dates,
            contract_by_product_date=contract_by_product_date,
            bar_cache=bar_cache,
        )
        weekly = _weekly_trend_table(adjusted_daily)
        for date in dates:
            state_map[(product, _normalize_date(date))] = last_completed_weekly_state(
                weekly,
                product=product,
                date=date,
            )
    return state_map


class WeeklyTrendNoLowerShadowSwingBacktester(NoLowerShadowSwingBacktester):
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
                is_no_lower_shadow_rising(signal_bar_1, pricetick, self.config.signal_variant)
                and is_no_lower_shadow_rising(signal_bar_2, pricetick, self.config.signal_variant)
            ):
                continue

            weekly_state = self.weekly_state_map.get((product, _normalize_date(date)))
            base_row = {
                "candidate_index": len(self.candidate_rows) + 1,
                "date": date.date().isoformat(),
                "product_vt_symbol": product,
                "signal_date_1": signal_date_1.date().isoformat(),
                "signal_date_2": signal_date_2.date().isoformat(),
                "signal_contract_1": signal_contract_1,
                "signal_contract_2": signal_contract_2,
                "entry_contract_vt_symbol": entry_contract,
                "signal": f"two_{self.config.signal_variant}_no_lower_shadow_rising",
                "signal_variant": self.config.signal_variant,
                "direction": "long",
                "top_down_filter": "previous_completed_week_close_gt_ma20_and_ma20_slope_up",
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
                "stop_mode": "two_signal_low",
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
            if weekly_state is None or not weekly_state.weekly_warmup_ready:
                self._record_candidate(base_row, "skipped", "weekly_trend_warmup_missing")
                continue
            if not weekly_state.weekly_trend_up:
                self._record_candidate(base_row, "skipped", "weekly_trend_gate_failed")
                continue
            if active_at_open >= self.config.max_concurrent_positions:
                self._record_candidate(base_row, "skipped", "max_concurrent_positions")
                continue

            entry_price = float(entry_bar.open)
            stop_price = min(float(signal_bar_1.low), float(signal_bar_2.low))
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
                reason="entry_open_weekly_trend",
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
            weekly_fail = 0
            weekly_warmup_missing = 0
        else:
            weekly_pass = int(pd.to_numeric(candidates.get("weekly_trend_gate_passed"), errors="coerce").fillna(0).sum())
            weekly_fail = int(candidates["skip_reason"].fillna("").astype(str).eq("weekly_trend_gate_failed").sum())
            weekly_warmup_missing = int(
                candidates["skip_reason"].fillna("").astype(str).eq("weekly_trend_warmup_missing").sum()
            )
        stats.update(
            {
                "model_tag": MODEL_TAG,
                "top_down_filter": "previous_completed_week_close_gt_ma20_and_ma20_slope_up",
                "weekly_ma_weeks": WEEKLY_MA_WEEKS,
                "stop_mode": "two_signal_low",
                "weekly_gate_pass_count": weekly_pass,
                "weekly_gate_fail_count": weekly_fail,
                "weekly_warmup_missing_count": weekly_warmup_missing,
            }
        )
        return stats


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
            "# 期货无下影线波段 Stage008 看大做小周线顺势报告",
            "",
            "## 参数",
            "",
            "- 大周期：上一完整周的连续收益指数收盘 > 20周均线，且20周均线斜率向上。",
            "- 小周期：连续两根日线 strict `open == low` 且 `close > open`。",
            "- 入场：第三天开盘做多。",
            "- 止损：两根信号K线低点 `two_signal_low`。",
            "- 周线连续收益指数在换月首日中性化价差跳变。",
            "",
            "## 总览",
            "",
            f"- 期末权益：`{stats['end_balance']:,.2f}`",
            f"- 总收益：`{stats['total_return_pct']:.4f}%`",
            f"- 最大回撤：`{stats['max_dd_percent']:.4f}%`",
            f"- Sharpe：`{stats['sharpe_ratio']:.4f}`",
            f"- 候选数/开仓数：`{stats['candidate_count']}` / `{stats['opened_candidate_count']}`",
            f"- 周线门通过数：`{stats['weekly_gate_pass_count']}`",
            f"- 周线门失败数：`{stats['weekly_gate_fail_count']}`",
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
    backtester = WeeklyTrendNoLowerShadowSwingBacktester(config, mapping, metadata, bar_cache)
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
    parser = argparse.ArgumentParser(description="Run top-down weekly trend no-lower-shadow swing Stage008.")
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

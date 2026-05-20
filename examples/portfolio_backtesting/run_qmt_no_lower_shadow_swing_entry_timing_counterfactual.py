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
    DEFAULT_CAPITAL,
    DEFAULT_END,
    DEFAULT_MAPPING_PATH,
    DEFAULT_MAX_CONCURRENT_POSITIONS,
    DEFAULT_RISK_RATIO,
    DEFAULT_START,
    DEFAULT_UNIVERSE_PATH,
    BacktestConfig,
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


MODEL_TAG = "no_lower_shadow_swing_entry_timing_stage005"
COMPARE_PREFIX = "qmt_no_lower_shadow_swing_entry_timing_counterfactual_stage005"

ENTRY_TIMING_RUNS: tuple[tuple[str, str, str], ...] = (
    ("open", "signal2_low", "qmt_no_lower_shadow_swing_stage005_open_signal2low"),
    ("open", "two_signal_low", "qmt_no_lower_shadow_swing_stage005_open_twosignallow"),
    ("pullback_signal2_close", "signal2_low", "qmt_no_lower_shadow_swing_stage005_closepb_signal2low"),
    ("pullback_signal2_mid", "signal2_low", "qmt_no_lower_shadow_swing_stage005_midpb_signal2low"),
    ("pullback_signal2_close", "two_signal_low", "qmt_no_lower_shadow_swing_stage005_closepb_twosignallow"),
    ("pullback_signal2_mid", "two_signal_low", "qmt_no_lower_shadow_swing_stage005_midpb_twosignallow"),
)

SUMMARY_CSV = OUTPUT_DIR / f"{COMPARE_PREFIX}_summary.csv"
SUMMARY_JSON = OUTPUT_DIR / f"{COMPARE_PREFIX}_summary.json"
REPORT_MD = OUTPUT_DIR / f"{COMPARE_PREFIX}_report.md"


def ceil_price_to_tick(price: float, pricetick: float) -> float:
    tick = float(pricetick) if pricetick > 0 else 1.0
    return round(math.ceil(float(price) / tick - 1e-12) * tick, 10)


def entry_trigger_price(signal_bar_2: Any, pricetick: float, entry_timing_variant: str) -> float | None:
    if entry_timing_variant == "open":
        return None
    if entry_timing_variant == "pullback_signal2_close":
        return ceil_price_to_tick(float(signal_bar_2.close), pricetick)
    if entry_timing_variant == "pullback_signal2_mid":
        body_mid = (float(signal_bar_2.open) + float(signal_bar_2.close)) / 2.0
        return ceil_price_to_tick(body_mid, pricetick)
    raise ValueError(f"Unsupported entry_timing_variant: {entry_timing_variant}")


def stop_anchor_price(signal_bar_1: Any, signal_bar_2: Any, stop_mode: str) -> float:
    if stop_mode == "signal2_low":
        return float(signal_bar_2.low)
    if stop_mode == "two_signal_low":
        return min(float(signal_bar_1.low), float(signal_bar_2.low))
    raise ValueError(f"Unsupported stop_mode: {stop_mode}")


class EntryTimingCounterfactualBacktester(NoLowerShadowSwingBacktester):
    def __init__(
        self,
        config: BacktestConfig,
        mapping: pd.DataFrame,
        metadata: dict[str, Any],
        bar_cache: dict[str, dict[pd.Timestamp, Any]],
        *,
        entry_timing_variant: str,
        stop_mode: str,
    ) -> None:
        super().__init__(config, mapping, metadata, bar_cache)
        self.entry_timing_variant = entry_timing_variant
        self.stop_mode = stop_mode

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
                "entry_timing_variant": self.entry_timing_variant,
                "stop_mode": self.stop_mode,
                "direction": "long",
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

            stop_price = stop_anchor_price(signal_bar_1, signal_bar_2, self.stop_mode)
            trigger_price = entry_trigger_price(signal_bar_2, pricetick, self.entry_timing_variant)
            if self.entry_timing_variant == "open":
                entry_price = float(entry_bar.open)
                entry_reason = "entry_open"
            else:
                if trigger_price is None:
                    raise ValueError("Pullback entry requires a trigger price")
                base_row["entry_trigger_price"] = trigger_price
                if trigger_price <= stop_price:
                    self._record_candidate(base_row, "skipped", "entry_trigger_not_above_stop")
                    continue
                if float(entry_bar.open) <= stop_price:
                    self._record_candidate(base_row, "skipped", "entry_open_not_above_stop")
                    continue
                if float(entry_bar.low) > trigger_price:
                    self._record_candidate(base_row, "skipped", "entry_pullback_not_touched")
                    continue
                entry_price = float(trigger_price)
                entry_reason = f"entry_{self.entry_timing_variant}"

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
                reason=entry_reason,
                price=entry_price,
                volume=volume,
                commission=commission_cash,
                slippage_cash=slippage_cash,
                pnl=0.0,
            )

    def _statistics(self) -> dict[str, Any]:
        stats = super()._statistics()
        stats.update(
            {
                "model_tag": MODEL_TAG,
                "entry_timing_variant": self.entry_timing_variant,
                "stop_mode": self.stop_mode,
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


def _summary_row(
    *,
    entry_timing_variant: str,
    stop_mode: str,
    output_prefix: str,
    stats: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    paths: dict[str, str],
) -> dict[str, Any]:
    exit_stats = _exit_reason_stats(frames["roundtrips"])
    initial_stop = exit_stats.get("long_initial_stop", {"count": 0, "net_pnl": 0.0})
    trailing_stop = exit_stats.get("long_trailing_stop", {"count": 0, "net_pnl": 0.0})
    gap_stop = exit_stats.get("long_gap_stop", {"count": 0, "net_pnl": 0.0})
    rollover = exit_stats.get("rollover_forced_exit", {"count": 0, "net_pnl": 0.0})
    first_day_half = frames["trades"]
    if not first_day_half.empty:
        first_day_half = first_day_half[first_day_half["reason"].astype(str).eq("first_day_half_exit")]
    return {
        "model_tag": MODEL_TAG,
        "entry_timing_variant": entry_timing_variant,
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


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    view = df.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:,.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _build_report(summary_df: pd.DataFrame, rows: list[dict[str, Any]]) -> str:
    key_columns = [
        "entry_timing_variant",
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
        "# 期货无下影线波段 Stage005 入场执行反事实",
        "",
        "## 参数",
        "",
        "- 信号固定为 `strict`：连续两根 `open == low` 且 `close > open`。",
        "- 入场执行：`open`、`pullback_signal2_close`、`pullback_signal2_mid`。",
        "- 止损锚点：`signal2_low` 或 `two_signal_low`。",
        "- 回踩单只允许入场日当日触发；若当日最低价未触发，则记录 `entry_pullback_not_touched` 并跳过。",
        "- 对回踩单的日内路径采用保守假设：一旦同日最低价触及止损，按入场后止损处理。",
        "",
        "## 核心结果",
        "",
        _markdown_table(summary_df[key_columns]),
        "",
        "## 跳过与退出摘要",
        "",
    ]
    for row in rows:
        name = f"{row['entry_timing_variant']} + {row['stop_mode']}"
        lines.extend(
            [
                f"### {name}",
                "",
                f"- skip_summary：`{json.dumps(row['skip_summary'], ensure_ascii=False)}`",
                f"- exit_summary：`{json.dumps(row['exit_summary'], ensure_ascii=False)}`",
                f"- report：`{row['paths'].get('report', '')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## 初步判断框架",
            "",
            "- 如果回踩入场明显减少初始止损亏损但收益仍不稳，说明方向判断仍弱，只是买点更好。",
            "- 如果两日低点止损改善亏损尾部但拖累收益，说明问题偏风险距离/手数，而不是信号强度。",
            "- 如果所有执行反事实仍为负，应停止本线，不继续加趋势/量能/指标过滤硬救。",
            "",
        ]
    )
    return "\n".join(lines)


def run_compare(base_config: BacktestConfig) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping, metadata, bar_cache = _load_inputs(base_config)
    rows: list[dict[str, Any]] = []
    for entry_timing_variant, stop_mode, output_prefix in ENTRY_TIMING_RUNS:
        config = replace(
            base_config,
            output_prefix=output_prefix,
            signal_variant="strict",
            save_outputs=True,
        )
        backtester = EntryTimingCounterfactualBacktester(
            config,
            mapping,
            metadata,
            bar_cache,
            entry_timing_variant=entry_timing_variant,
            stop_mode=stop_mode,
        )
        stats = backtester.run()
        frames = backtester.output_frames()
        paths = _write_outputs(config, stats, frames)
        rows.append(
            _summary_row(
                entry_timing_variant=entry_timing_variant,
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
    REPORT_MD.write_text(_build_report(summary_df, rows), encoding="utf-8")
    return summary_df, rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare no-lower-shadow swing entry timing counterfactuals.")
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
                "variant_reports": {
                    f"{row['entry_timing_variant']}+{row['stop_mode']}": row["paths"].get("report", "")
                    for row in rows
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

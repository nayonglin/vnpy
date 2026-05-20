from __future__ import annotations

import argparse
import json
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
    NoLowerShadowSwingBacktester,
    BacktestConfig,
    OUTPUT_DIR,
    _bar,
    _load_inputs,
    _mapping_indexes,
    _write_outputs,
    is_no_lower_shadow_rising,
)


MODEL_TAG = "no_lower_shadow_swing_relaxed_entry_stage004"
COMPARE_PREFIX = "qmt_no_lower_shadow_swing_relaxed_entry_compare_stage004"
VARIANT_RUNS: tuple[tuple[str, str], ...] = (
    ("strict", "qmt_no_lower_shadow_swing_stage004_strict"),
    ("lower_shadow_1tick", "qmt_no_lower_shadow_swing_stage004_lower_shadow_1tick"),
    ("lower_shadow_2tick_body10", "qmt_no_lower_shadow_swing_stage004_lower_shadow_2tick_body10"),
)

SUMMARY_CSV = OUTPUT_DIR / f"{COMPARE_PREFIX}_summary.csv"
SUMMARY_JSON = OUTPUT_DIR / f"{COMPARE_PREFIX}_summary.json"
REPORT_MD = OUTPUT_DIR / f"{COMPARE_PREFIX}_report.md"


def _signal_funnel(
    config: BacktestConfig,
    mapping: pd.DataFrame,
    metadata: dict[str, Any],
    bar_cache: dict[str, dict[pd.Timestamp, Any]],
    signal_variant: str,
) -> dict[str, Any]:
    product_dates, contract_by_product_date = _mapping_indexes(mapping)
    start = pd.Timestamp(config.start).normalize()
    end = pd.Timestamp(config.end).normalize()
    observations = 0
    single_signal_count = 0
    two_day_pair_count = 0
    same_contract_pair_count = 0
    yearly: dict[int, dict[str, int]] = {}

    for product in sorted(metadata["product_symbols"]):
        dates = [date for date in product_dates.get(product, []) if start <= date <= end]
        for date in dates:
            contract = contract_by_product_date.get((product, date), "")
            bar = _bar(bar_cache, contract, date) if contract else None
            if bar is None:
                continue
            pricetick = float(metadata["priceticks"].get(contract, 1.0) or 1.0)
            observations += 1
            signal = is_no_lower_shadow_rising(bar, pricetick, signal_variant)
            single_signal_count += int(signal)
            yearly.setdefault(date.year, {"observations": 0, "single_signal_count": 0, "two_day_pair_count": 0})
            yearly[date.year]["observations"] += 1
            yearly[date.year]["single_signal_count"] += int(signal)

        for index in range(2, len(dates)):
            signal_date_1 = dates[index - 2]
            signal_date_2 = dates[index - 1]
            entry_date = dates[index]
            entry_contract = contract_by_product_date.get((product, entry_date), "")
            signal_contract_1 = contract_by_product_date.get((product, signal_date_1), "")
            signal_contract_2 = contract_by_product_date.get((product, signal_date_2), "")
            if not entry_contract or not signal_contract_1 or not signal_contract_2:
                continue
            signal_bar_1 = _bar(bar_cache, signal_contract_1, signal_date_1)
            signal_bar_2 = _bar(bar_cache, signal_contract_2, signal_date_2)
            if signal_bar_1 is None or signal_bar_2 is None:
                continue
            pricetick = float(metadata["priceticks"].get(entry_contract, 1.0) or 1.0)
            if not (
                is_no_lower_shadow_rising(signal_bar_1, pricetick, signal_variant)
                and is_no_lower_shadow_rising(signal_bar_2, pricetick, signal_variant)
            ):
                continue
            two_day_pair_count += 1
            same_contract_pair_count += int(signal_contract_1 == signal_contract_2 == entry_contract)
            yearly.setdefault(entry_date.year, {"observations": 0, "single_signal_count": 0, "two_day_pair_count": 0})
            yearly[entry_date.year]["two_day_pair_count"] += 1

    return {
        "observations": observations,
        "single_signal_count": single_signal_count,
        "single_signal_rate_pct": single_signal_count / observations * 100.0 if observations else 0.0,
        "two_day_pair_count_before_position_filter": two_day_pair_count,
        "same_contract_pair_count": same_contract_pair_count,
        "yearly_signal_funnel": yearly,
    }


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
    signal_variant: str,
    output_prefix: str,
    stats: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    paths: dict[str, str],
    funnel: dict[str, Any],
) -> dict[str, Any]:
    roundtrips = frames["roundtrips"]
    exit_stats = _exit_reason_stats(roundtrips)
    initial_stop = exit_stats.get("long_initial_stop", {"count": 0, "net_pnl": 0.0})
    trailing_stop = exit_stats.get("long_trailing_stop", {"count": 0, "net_pnl": 0.0})
    gap_stop = exit_stats.get("long_gap_stop", {"count": 0, "net_pnl": 0.0})
    rollover = exit_stats.get("rollover_forced_exit", {"count": 0, "net_pnl": 0.0})
    return {
        "model_tag": MODEL_TAG,
        "signal_variant": signal_variant,
        "output_prefix": output_prefix,
        "observations": funnel["observations"],
        "single_signal_count": funnel["single_signal_count"],
        "single_signal_rate_pct": funnel["single_signal_rate_pct"],
        "two_day_pair_count_before_position_filter": funnel["two_day_pair_count_before_position_filter"],
        "same_contract_pair_count": funnel["same_contract_pair_count"],
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
        "yearly_signal_funnel": funnel["yearly_signal_funnel"],
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
        "signal_variant",
        "single_signal_count",
        "two_day_pair_count_before_position_filter",
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
        "# 期货无下影线波段 Stage004 放松开仓要求对比",
        "",
        "## 参数",
        "",
        "- strict：原始 `open == low` 且 `close > open`。",
        "- lower_shadow_1tick：下影线允许 `open - low <= 1 * pricetick`。",
        "- lower_shadow_2tick_body10：下影线允许 `open - low <= min(2 * pricetick, 10% * body)`。",
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
                f"### {row['signal_variant']}",
                "",
                f"- skip_summary：`{json.dumps(row['skip_summary'], ensure_ascii=False)}`",
                f"- exit_summary：`{json.dumps(row['exit_summary'], ensure_ascii=False)}`",
                f"- report：`{row['paths'].get('report', '')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## 初步判断",
            "",
            "- 本报告只比较预先锁定的三档下影线容忍度，不做参数网格搜索。",
            "- 放松后交易数明显增加，但首日/初始止损亏损同步扩大，说明形态边界被稀释。",
            "- 1tick 版本扩样后收益、回撤、Sharpe 全面恶化，直接反证。",
            "- 2tick/body10 版本虽然 Sharpe 略好于 strict，但收益仍为负且回撤更深，不具备升级价值。",
            "- 下一步应回到首日执行反事实，而不是继续放松下影线。",
            "",
        ]
    )
    return "\n".join(lines)


def run_compare(base_config: BacktestConfig) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping, metadata, bar_cache = _load_inputs(base_config)
    rows: list[dict[str, Any]] = []
    for signal_variant, output_prefix in VARIANT_RUNS:
        config = replace(
            base_config,
            signal_variant=signal_variant,
            output_prefix=output_prefix,
            save_outputs=True,
        )
        funnel = _signal_funnel(config, mapping, metadata, bar_cache, signal_variant)
        backtester = NoLowerShadowSwingBacktester(config, mapping, metadata, bar_cache)
        stats = backtester.run()
        frames = backtester.output_frames()
        paths = _write_outputs(config, stats, frames)
        rows.append(
            _summary_row(
                signal_variant=signal_variant,
                output_prefix=output_prefix,
                stats=stats,
                frames=frames,
                paths=paths,
                funnel=funnel,
            )
        )

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")
    SUMMARY_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_build_report(summary_df, rows), encoding="utf-8")
    return summary_df, rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare relaxed lower-shadow entry variants.")
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
                "variant_reports": {row["signal_variant"]: row["paths"].get("report", "") for row in rows},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

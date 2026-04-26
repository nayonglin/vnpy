from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_no_streak_kill_v3"
MODEL_TAG: str = "range_reversion_core4_v3_exit_structure_v1"

TRADES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"
ROUND_TRIPS_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v3_round_trips_{MODEL_TAG}.csv"
EXIT_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v3_exit_summary_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v3_product_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v3_year_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v3_exit_structure_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v3_exit_structure_report_{MODEL_TAG}.md"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not TRADES_PATH.exists():
        raise FileNotFoundError(TRADES_PATH)
    if not ENTRY_RISK_PATH.exists():
        raise FileNotFoundError(ENTRY_RISK_PATH)
    trades = pd.read_csv(TRADES_PATH)
    entries = pd.read_csv(ENTRY_RISK_PATH)
    return trades, entries


def _build_round_trips(trades: pd.DataFrame, entries: pd.DataFrame) -> pd.DataFrame:
    size_by_contract = {
        str(row.contract_vt_symbol): float(row.size)
        for row in entries.itertuples(index=False)
        if str(row.contract_vt_symbol)
    }
    product_by_contract = {
        str(row.contract_vt_symbol): str(row.product_vt_symbol)
        for row in entries.itertuples(index=False)
        if str(row.contract_vt_symbol)
    }

    queues: dict[tuple[str, str], list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    trades = trades.sort_values(["datetime", "trade_id"]).reset_index(drop=True)
    for trade in trades.itertuples(index=False):
        vt_symbol = str(trade.vt_symbol)
        direction = str(trade.direction)
        offset = str(trade.offset)
        price = float(trade.price)
        volume = float(trade.volume)
        if offset == "Open":
            position_direction = "long" if direction == "Long" else "short"
            queues.setdefault((vt_symbol, position_direction), []).append(
                {
                    "entry_datetime": str(trade.datetime),
                    "entry_price": price,
                    "volume": volume,
                    "product_vt_symbol": product_by_contract.get(vt_symbol, ""),
                }
            )
            continue

        position_direction = "long" if direction == "Short" else "short"
        queue = queues.setdefault((vt_symbol, position_direction), [])
        remaining = volume
        while remaining > 1e-9 and queue:
            entry = queue[0]
            matched_volume = min(remaining, float(entry["volume"]))
            entry_price = float(entry["entry_price"])
            size = float(size_by_contract.get(vt_symbol, 1.0))
            if position_direction == "long":
                pnl = (price - entry_price) * matched_volume * size
            else:
                pnl = (entry_price - price) * matched_volume * size
            rows.append(
                {
                    "product_vt_symbol": entry["product_vt_symbol"],
                    "contract_vt_symbol": vt_symbol,
                    "direction": position_direction,
                    "entry_datetime": entry["entry_datetime"],
                    "exit_datetime": str(trade.datetime),
                    "entry_price": entry_price,
                    "exit_price": price,
                    "volume": matched_volume,
                    "pnl": pnl,
                    "exit_reason": str(getattr(trade, "exit_reason", "") or ""),
                }
            )
            entry["volume"] = float(entry["volume"]) - matched_volume
            remaining -= matched_volume
            if float(entry["volume"]) <= 1e-9:
                queue.pop(0)
    round_trips = pd.DataFrame(rows)
    if not round_trips.empty:
        round_trips["entry_datetime"] = pd.to_datetime(round_trips["entry_datetime"])
        round_trips["exit_datetime"] = pd.to_datetime(round_trips["exit_datetime"])
        round_trips["entry_year"] = round_trips["entry_datetime"].dt.year
    return round_trips


def _summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    summary = frame.groupby(group_cols, dropna=False).agg(
        round_trips=("pnl", "size"),
        pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        win_rate=("pnl", lambda s: float((s > 0).mean())),
        worst_pnl=("pnl", "min"),
        best_pnl=("pnl", "max"),
    ).reset_index()
    return summary.sort_values(["pnl", "round_trips"], ascending=[False, False]).reset_index(drop=True)


def _write_report(
    round_trips: pd.DataFrame,
    exit_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
) -> None:
    lines: list[str] = [
        "# QMT Range Reversion Core4 V3 Exit Structure",
        "",
        "## 结论",
        f"- 回合数：`{len(round_trips)}`。",
        f"- 合计PnL：`{float(round_trips['pnl'].sum()) if not round_trips.empty else 0.0:.2f}`。",
        "- 本报告只解释v3真实成交，不做参数优化。",
        "",
        "## 按退出原因",
        exit_summary.to_markdown(index=False) if not exit_summary.empty else "- 无。",
        "",
        "## 按产品",
        product_summary.to_markdown(index=False) if not product_summary.empty else "- 无。",
        "",
        "## 按年份",
        year_summary.to_markdown(index=False) if not year_summary.empty else "- 无。",
        "",
        "## 输出",
        f"- round_trips: `{ROUND_TRIPS_PATH}`",
        f"- exit_summary: `{EXIT_SUMMARY_PATH}`",
        f"- product_summary: `{PRODUCT_SUMMARY_PATH}`",
        f"- year_summary: `{YEAR_SUMMARY_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    trades, entries = _load_inputs()
    round_trips = _build_round_trips(trades, entries)
    exit_summary = _summarize(round_trips, ["exit_reason"])
    product_summary = _summarize(round_trips, ["product_vt_symbol", "direction"])
    year_summary = _summarize(round_trips, ["entry_year"])

    round_trips.to_csv(ROUND_TRIPS_PATH, index=False, encoding="utf-8-sig")
    exit_summary.to_csv(EXIT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "round_trips": int(len(round_trips)),
        "total_pnl": float(round_trips["pnl"].sum()) if not round_trips.empty else 0.0,
        "win_rate": float((round_trips["pnl"] > 0).mean()) if not round_trips.empty else 0.0,
        "outputs": {
            "round_trips": str(ROUND_TRIPS_PATH),
            "exit_summary": str(EXIT_SUMMARY_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "year_summary": str(YEAR_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(round_trips, exit_summary, product_summary, year_summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(exit_summary.to_string(index=False))
    print(product_summary.to_string(index=False))
    print(year_summary.to_string(index=False))


if __name__ == "__main__":
    main()

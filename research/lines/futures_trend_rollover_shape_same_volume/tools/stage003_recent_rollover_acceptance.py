from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from qmt_universe import MARGIN_RATIOS, PRICETICKS, SIZES


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = (
    LINE_DIR
    / "artifacts"
    / "stage003"
    / "stage003_recent_rollover_acceptance.csv"
)

EVENTS: tuple[dict[str, str], ...] = (
    {
        "date": "2026-08-18",
        "product_vt_symbol": "si.GFEX",
        "old_contract": "si2609",
        "target_contract": "si2611",
        "exchange": "GFEX",
        "direction": "long",
    },
    {
        "date": "2026-08-19",
        "product_vt_symbol": "jm.DCE",
        "old_contract": "jm2609",
        "target_contract": "jm2701",
        "exchange": "DCE",
        "direction": "long",
    },
)


def _load_daily_bars(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    exchange: str,
    end_date: str,
) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT datetime, open_price, high_price, low_price, close_price, volume, open_interest
        FROM dbbardata
        WHERE symbol = ? AND exchange = ? AND interval = 'd'
          AND substr(datetime, 1, 10) <= ?
        ORDER BY datetime
        """,
        connection,
        params=(symbol, exchange, end_date),
    )


def _shape_strategy() -> QmtRollPortfolioStrategy:
    strategy = object.__new__(QmtRollPortfolioStrategy)
    strategy.ma_short = 5
    strategy.ma_mid = 10
    strategy.ma_long = 20
    strategy.ma_extra_long = 40
    strategy.long_entry_enabled = True
    strategy.short_entry_enabled = True
    return strategy


def _evaluate_event(
    connection: sqlite3.Connection,
    event: dict[str, str],
) -> dict[str, Any]:
    old_bars = _load_daily_bars(
        connection,
        symbol=event["old_contract"],
        exchange=event["exchange"],
        end_date=event["date"],
    )
    target_bars = _load_daily_bars(
        connection,
        symbol=event["target_contract"],
        exchange=event["exchange"],
        end_date=event["date"],
    )
    old_history = old_bars.tail(41).reset_index(drop=True)
    if old_history.empty or target_bars.empty:
        raise RuntimeError(f"recent_rollover_bar_missing:{event}")
    target_bar = target_bars.iloc[-1]
    prices = [
        float(target_bar["open_price"]),
        float(target_bar["high_price"]),
        float(target_bar["low_price"]),
        float(target_bar["close_price"]),
    ]
    same_day_bar_ready = str(target_bar["datetime"])[:10] == event["date"]
    market_data_ready = bool(
        all(np.isfinite(value) and value > 0 for value in prices)
        and prices[1] >= max(prices)
        and prices[2] <= min(prices)
        and np.isfinite(float(target_bar["volume"]))
        and float(target_bar["volume"]) > 0
    )
    product_vt_symbol = event["product_vt_symbol"]
    size = int(SIZES.get(product_vt_symbol, 0))
    pricetick = float(PRICETICKS.get(product_vt_symbol, 0.0))
    margin_ratio = float(MARGIN_RATIOS.get(product_vt_symbol, 0.0))
    metadata_ready = bool(size > 0 and pricetick > 0 and margin_ratio > 0)

    old_close = float(old_history.iloc[-1]["close_price"])
    ratio = float(target_bar["close_price"]) / old_close
    history = pd.DataFrame(
        {
            "open": pd.to_numeric(old_history["open_price"]) * ratio,
            "high": pd.to_numeric(old_history["high_price"]) * ratio,
            "low": pd.to_numeric(old_history["low_price"]) * ratio,
            "close": pd.to_numeric(old_history["close_price"]) * ratio,
            "volume": pd.to_numeric(old_history["volume"]),
            "open_interest": pd.to_numeric(old_history["open_interest"]),
        }
    )
    target_row = {
        "open": prices[0],
        "high": prices[1],
        "low": prices[2],
        "close": prices[3],
        "volume": float(target_bar["volume"]),
        "open_interest": float(target_bar["open_interest"]),
    }
    old_last_bar_date = str(old_history.iloc[-1]["datetime"])[:10]
    target_last_bar_date = str(target_bar["datetime"])[:10]
    target_bar_appended = int(old_last_bar_date != target_last_bar_date)
    if target_bar_appended:
        history = pd.concat([history, pd.DataFrame([target_row])], ignore_index=True)
    else:
        history.loc[history.index[-1], list(target_row)] = list(target_row.values())
    shape = _shape_strategy()._rollover_shape_continuation_snapshot(
        event["direction"],
        history,
    )
    target_history_gate_bypassed = bool(
        0 < len(target_bars) < int(shape["required_bar_count"])
        and len(old_history) >= int(shape["required_bar_count"])
        and same_day_bar_ready
        and market_data_ready
        and metadata_ready
    )
    return {
        **event,
        "old_last_bar_date": old_last_bar_date,
        "target_last_bar_date": target_last_bar_date,
        "target_observed_bar_count": int(len(target_bars)),
        "source_observed_bar_count": int(len(old_history)),
        "indicator_observed_bar_count": int(len(history)),
        "target_bar_appended": target_bar_appended,
        "required_bar_count": int(shape["required_bar_count"]),
        "same_day_bar_ready": int(same_day_bar_ready),
        "market_data_ready": int(market_data_ready),
        "metadata_ready": int(metadata_ready),
        "contract_size": size,
        "pricetick": pricetick,
        "margin_ratio": margin_ratio,
        "roll_adjustment_ratio": ratio,
        "bullish_alignment": int(shape["bullish_alignment"]),
        "bearish_alignment": int(shape["bearish_alignment"]),
        "macd_hist": float(shape["macd_hist"]),
        "shape_allowed": int(shape["allowed"]),
        "shape_reason": str(shape["reason"]),
        "target_history_gate_bypassed": int(target_history_gate_bypassed),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    database_path = args.database.resolve()
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        result = pd.DataFrame([_evaluate_event(connection, event) for event in EVENTS])
    finally:
        connection.close()
    if not result["target_history_gate_bypassed"].eq(1).all():
        raise RuntimeError("stage003_recent_target_history_bypass_failed")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(result.to_json(orient="records", force_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Build a 15-minute chart atlas for Stage847-C9-15w >=2R winners."""

from __future__ import annotations

import numpy as np
import pandas as pd


EXPECTED_EVENT_COUNT = 309
EXPECTED_WINNER_COUNT = 71
WINNER_R_THRESHOLD = 2.0


def build_winner_events(
    closed_lots: pd.DataFrame,
    *,
    enforce_expected_counts: bool = True,
) -> pd.DataFrame:
    """Aggregate closed lots into frozen entry events and keep >=2R winners."""
    frame = closed_lots[
        closed_lots["requested_start_month"].astype(str).eq("2020-01")
    ].copy()
    for column in ["realized_pnl", "risk_amount", "entry_price"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["entry_date", "exit_date"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()

    grouped = (
        frame.sort_values(["open_trade_id", "entry_date", "exit_date", "lot_id"])
        .groupby(
            ["open_trade_id", "vt_symbol", "direction", "entry_date", "entry_price"],
            dropna=False,
        )
        .agg(
            exit_date=("exit_date", "max"),
            realized_pnl=("realized_pnl", "sum"),
            risk_amount=("risk_amount", "sum"),
            lot_count=("lot_id", "size"),
        )
        .reset_index()
    )
    grouped["aggregate_r"] = grouped["realized_pnl"] / grouped[
        "risk_amount"
    ].replace(0.0, np.nan)

    if enforce_expected_counts and len(grouped) != EXPECTED_EVENT_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_EVENT_COUNT} events, got {len(grouped)}"
        )

    winners = grouped[grouped["aggregate_r"].ge(WINNER_R_THRESHOLD)].copy()
    if enforce_expected_counts and len(winners) != EXPECTED_WINNER_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_WINNER_COUNT} winners, got {len(winners)}"
        )

    winners = winners.sort_values(
        ["aggregate_r", "realized_pnl", "entry_date", "open_trade_id"],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)
    winners.insert(0, "winner_rank", np.arange(1, len(winners) + 1, dtype=int))
    return winners


def build_trading_calendar(curves: pd.DataFrame) -> pd.DatetimeIndex:
    """Return the ordered official trading dates for the 2020-start curve."""
    frame = curves[
        curves["requested_start_month"].astype(str).eq("2020-01")
    ].copy()
    dates = (
        pd.to_datetime(frame["date"], errors="coerce")
        .dropna()
        .dt.normalize()
        .drop_duplicates()
        .sort_values()
    )
    return pd.DatetimeIndex(dates)


def assign_trading_day(
    bars: pd.DataFrame,
    calendar: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Map night bars to the next available official trading day."""
    result = bars.copy()
    result["bar_datetime"] = pd.to_datetime(result["bar_datetime"], errors="coerce")
    normalized_calendar = pd.DatetimeIndex(calendar).normalize().sort_values().unique()
    natural_days = result["bar_datetime"].dt.normalize()
    targets = natural_days.where(
        result["bar_datetime"].dt.hour.lt(20),
        natural_days + pd.Timedelta(days=1),
    )
    positions = normalized_calendar.searchsorted(targets, side="left")
    mapped = np.full(len(result), np.datetime64("NaT"), dtype="datetime64[ns]")
    valid = positions < len(normalized_calendar)
    if valid.any():
        mapped[valid] = normalized_calendar.take(positions[valid]).to_numpy()
    result["trading_day"] = pd.to_datetime(mapped)
    return result


def select_window_days(
    entry_day: pd.Timestamp,
    calendar: pd.DatetimeIndex,
    before: int = 5,
    after: int = 5,
) -> list[pd.Timestamp]:
    """Select an entry day's bounded official trading-day context window."""
    normalized = pd.Timestamp(entry_day).normalize()
    normalized_calendar = pd.DatetimeIndex(calendar).normalize()
    positions = np.flatnonzero(normalized_calendar == normalized)
    if len(positions) != 1:
        raise RuntimeError(
            f"entry day not uniquely present in calendar: {normalized.date()}"
        )
    position = int(positions[0])
    return list(
        normalized_calendar[
            max(0, position - before) : min(
                len(normalized_calendar), position + after + 1
            )
        ]
    )


def resample_15m(bars: pd.DataFrame) -> pd.DataFrame:
    """Aggregate observed minute bars into non-filled 15-minute buckets."""
    frame = bars.copy()
    frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce")
    frame["trading_day"] = pd.to_datetime(
        frame["trading_day"], errors="coerce"
    ).dt.normalize()
    frame["bar_15m"] = frame["bar_datetime"].dt.floor("15min")
    result = (
        frame.dropna(subset=["vt_symbol", "trading_day", "bar_15m"])
        .sort_values(["vt_symbol", "trading_day", "bar_datetime"])
        .groupby(["vt_symbol", "trading_day", "bar_15m"], as_index=False)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            open_oi=("open_oi", "first"),
            close_oi=("close_oi", "last"),
        )
        .sort_values(["vt_symbol", "trading_day", "bar_15m"])
        .reset_index(drop=True)
    )
    return result

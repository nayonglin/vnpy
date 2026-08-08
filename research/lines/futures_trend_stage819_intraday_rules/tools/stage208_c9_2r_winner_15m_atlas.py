"""Build a 15-minute chart atlas for Stage847-C9-15w >=2R winners."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd


EXPECTED_EVENT_COUNT = 309
EXPECTED_WINNER_COUNT = 71
WINNER_R_THRESHOLD = 2.0
REPO_ROOT = Path(__file__).resolve().parents[4]
LINE_ROOT = REPO_ROOT / "research/lines/futures_trend_stage819_intraday_rules"
OUTPUT_DIR = LINE_ROOT / "outputs/stage208_c9_2r_winner_15m_atlas"
CLOSED_LOTS_PATH = REPO_ROOT / (
    "research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/"
    "stage006_current_quality_feature_binder/"
    "rebuilt_c9_stage006_current_quality_feature_binder_closed_lots_"
    "stage006_current_quality_feature_binder_v1.csv"
)
CURVES_PATH = REPO_ROOT / (
    "research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/"
    "stage006_current_quality_feature_binder/"
    "rebuilt_c9_stage006_current_quality_feature_binder_curves_"
    "stage006_current_quality_feature_binder_v1.csv"
)
TRADES_PATH = REPO_ROOT / (
    "research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/"
    "stage006_current_quality_feature_binder/"
    "rebuilt_c9_stage006_current_quality_feature_binder_trades_"
    "stage006_current_quality_feature_binder_v1.csv"
)
MINUTE_PATH = REPO_ROOT / (
    "examples/portfolio_backtesting/backtest_outputs/"
    "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_"
    "stage861_stage860_full_visual_atlas_v1.csv"
)
MINUTE_CACHE_ROOT = REPO_ROOT / "examples/portfolio_backtesting/downloaded_futures"
OFFICIAL_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
DAILY_SOURCE = "vnpy_local_database_exact_contract_daily"


def daily_bars_to_frame(vt_symbol: str, bars: list[object]) -> pd.DataFrame:
    """Convert vn.py daily bars into a timezone-naive exact-contract frame."""
    rows: list[dict[str, object]] = []
    for bar in bars:
        trade_date = pd.Timestamp(bar.datetime)
        if trade_date.tzinfo is not None:
            trade_date = trade_date.tz_convert("Asia/Shanghai").tz_localize(None)
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "trade_date": trade_date.normalize(),
                "open": float(bar.open_price),
                "high": float(bar.high_price),
                "low": float(bar.low_price),
                "close": float(bar.close_price),
                "volume": float(bar.volume),
            }
        )
    return pd.DataFrame(
        rows,
        columns=["vt_symbol", "trade_date", "open", "high", "low", "close", "volume"],
    )


def select_daily_window(
    event: pd.Series,
    daily_bars: pd.DataFrame,
    before: int = 60,
    after: int = 5,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Select exact-contract daily context around the full holding period."""
    frame = daily_bars.copy()
    if frame.empty:
        return frame, {
            "daily_bar_count": 0,
            "daily_before_count": 0,
            "daily_holding_count": 0,
            "daily_after_count": 0,
            "daily_coverage_state": "missing",
            "daily_source": DAILY_SOURCE,
        }

    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
    entry_day = pd.Timestamp(event["entry_date"]).normalize()
    exit_day = pd.Timestamp(event["exit_date"]).normalize()
    before_frame = frame[frame["trade_date"].lt(entry_day)].tail(before)
    holding_frame = frame[
        frame["trade_date"].ge(entry_day) & frame["trade_date"].le(exit_day)
    ]
    after_frame = frame[frame["trade_date"].gt(exit_day)].head(after)
    window = pd.concat([before_frame, holding_frame, after_frame], ignore_index=True)
    has_entry = bool(frame["trade_date"].eq(entry_day).any())
    has_exit = bool(frame["trade_date"].eq(exit_day).any())
    state = (
        "complete"
        if len(before_frame) == before
        and len(after_frame) == after
        and has_entry
        and has_exit
        else "partial"
    )
    return window, {
        "daily_bar_count": int(len(window)),
        "daily_before_count": int(len(before_frame)),
        "daily_holding_count": int(len(holding_frame)),
        "daily_after_count": int(len(after_frame)),
        "daily_coverage_state": state,
        "daily_source": DAILY_SOURCE,
    }


def load_daily_context(
    winners: pd.DataFrame,
    database: object | None = None,
) -> dict[str, pd.DataFrame]:
    """Load exact monthly-contract daily bars from the local vn.py database."""
    from vnpy.trader.constant import Exchange, Interval

    if database is None:
        from vnpy.trader.database import get_database

        database = get_database()

    context: dict[str, pd.DataFrame] = {}
    for vt_symbol in sorted(winners["vt_symbol"].dropna().astype(str).unique()):
        if vt_symbol.count(".") != 1:
            raise ValueError(f"invalid exact vt_symbol: {vt_symbol}")
        symbol, exchange_code = vt_symbol.split(".", 1)
        bars = database.load_bar_data(
            symbol,
            Exchange(exchange_code),
            Interval.DAILY,
            datetime(2010, 1, 1),
            datetime(2026, 7, 15),
        )
        context[vt_symbol] = daily_bars_to_frame(vt_symbol, list(bars))
    return context


def build_daily_source_manifest(
    daily_context: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Describe and hash the canonical exact-contract daily-bar inputs."""
    rows: list[dict[str, object]] = []
    for vt_symbol in sorted(daily_context):
        frame = daily_context[vt_symbol].copy().sort_values("trade_date")
        if frame.empty:
            minimum = ""
            maximum = ""
        else:
            dates = pd.to_datetime(frame["trade_date"], errors="coerce")
            minimum = dates.min().date().isoformat()
            maximum = dates.max().date().isoformat()
        canonical = frame[
            ["vt_symbol", "trade_date", "open", "high", "low", "close", "volume"]
        ].copy()
        canonical["trade_date"] = pd.to_datetime(
            canonical["trade_date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        payload = canonical.to_csv(
            index=False,
            lineterminator="\n",
            float_format="%.10g",
        ).encode("utf-8")
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "row_count": int(len(frame)),
                "min_trade_date": minimum,
                "max_trade_date": maximum,
                "canonical_sha256": hashlib.sha256(payload).hexdigest(),
                "source": DAILY_SOURCE,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "vt_symbol",
            "row_count",
            "min_trade_date",
            "max_trade_date",
            "canonical_sha256",
            "source",
        ],
    )


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


MINUTE_COLUMNS = [
    "vt_symbol",
    "bar_datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_oi",
    "close_oi",
]


def discover_contract_cache_paths(
    cache_root: Path,
    winners: pd.DataFrame,
) -> list[Path]:
    """Find exact per-contract minute caches without prefix or exchange leakage."""
    targets = {
        (str(symbol).split(".", 1)[0].lower(), str(symbol).split(".", 1)[1].upper())
        for symbol in winners["vt_symbol"].astype(str)
        if "." in str(symbol)
    }
    matches: list[Path] = []
    for path in cache_root.rglob("*minute_backtest.csv"):
        contract = path.name.split("_", 1)[0].lower()
        exchange = path.parent.name.upper()
        if (contract, exchange) in targets:
            matches.append(path)
    return sorted(matches)


def load_target_minutes(
    path: Path,
    winners: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    *,
    fallback_paths: list[Path] | None = None,
    chunksize: int = 250_000,
) -> pd.DataFrame:
    """Load only symbols and official trading-day windows needed by winners."""
    target_days: dict[str, set[pd.Timestamp]] = {}
    for event in winners.itertuples(index=False):
        symbol = str(event.vt_symbol)
        window = select_window_days(pd.Timestamp(event.entry_date), calendar)
        target_days.setdefault(symbol, set()).update(window)

    selected: list[pd.DataFrame] = []
    target_symbols = set(target_days)
    source_specs = [(path, "primary", 1)] + [
        (fallback_path, "local_contract_cache", 0)
        for fallback_path in (fallback_paths or [])
    ]
    for source_path, source_kind, source_priority in source_specs:
        for chunk in pd.read_csv(
            source_path,
            usecols=lambda column: column in MINUTE_COLUMNS,
            chunksize=chunksize,
        ):
            if not {"vt_symbol", "bar_datetime"}.issubset(chunk.columns):
                continue
            chunk = chunk[
                chunk["vt_symbol"].astype(str).isin(target_symbols)
            ].copy()
            if chunk.empty:
                continue
            chunk["bar_datetime"] = pd.to_datetime(
                chunk["bar_datetime"], errors="coerce"
            )
            for column in [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "open_oi",
                "close_oi",
            ]:
                if column not in chunk.columns:
                    chunk[column] = np.nan
                chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
            chunk = assign_trading_day(chunk, calendar)
            keep = pd.Series(False, index=chunk.index)
            for symbol, days in target_days.items():
                keep |= chunk["vt_symbol"].eq(symbol) & chunk["trading_day"].isin(
                    days
                )
            if keep.any():
                chosen = chunk.loc[keep].copy()
                chosen["minute_source_kind"] = source_kind
                chosen["minute_source_path"] = str(source_path)
                chosen["_source_priority"] = source_priority
                selected.append(chosen)

    if not selected:
        return pd.DataFrame(
            columns=[
                *MINUTE_COLUMNS,
                "trading_day",
                "minute_source_kind",
                "minute_source_path",
            ]
        )
    return (
        pd.concat(selected, ignore_index=True)
        .sort_values(["vt_symbol", "bar_datetime", "_source_priority"])
        .drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
        .sort_values(["vt_symbol", "bar_datetime"])
        .drop(columns="_source_priority")
        .reset_index(drop=True)
    )


def write_placeholder(event: pd.Series, output_path: Path, reason: str) -> None:
    """Render a non-silent placeholder when local minute coverage is absent."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(18, 9), dpi=150)
    axis.set_axis_off()
    identity = (
        f"Rank {int(event['winner_rank']):02d} | {event['vt_symbol']} | "
        f"{event['direction']} | entry {pd.Timestamp(event['entry_date']).date()} | "
        f"R {float(event['aggregate_r']):.4f}"
    )
    axis.text(
        0.5,
        0.58,
        identity,
        ha="center",
        va="center",
        fontsize=24,
        fontweight="bold",
        transform=axis.transAxes,
    )
    axis.text(
        0.5,
        0.45,
        "15-minute chart unavailable",
        ha="center",
        va="center",
        fontsize=20,
        color="#b91c1c",
        transform=axis.transAxes,
    )
    axis.text(
        0.5,
        0.36,
        reason,
        ha="center",
        va="center",
        fontsize=16,
        color="#475569",
        transform=axis.transAxes,
    )
    figure.savefig(output_path, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def _safe_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_")


def _chart_filename(event: pd.Series) -> str:
    return (
        f"winner_{int(event['winner_rank']):04d}_"
        f"{_safe_name(event['vt_symbol'])}_{_safe_name(event['open_trade_id'])}.png"
    )


def _draw_candles(axis: object, frame: pd.DataFrame, x_values: np.ndarray) -> np.ndarray:
    """Draw red-up/green-down candles and return their colors."""
    upward = frame["close"].ge(frame["open"])
    colors = np.where(upward, "#d62728", "#159447")
    price_span = float(frame["high"].max() - frame["low"].min())
    minimum_body = max(
        price_span * 0.0008,
        abs(float(frame["close"].mean())) * 1e-6,
        1e-9,
    )
    for x_value, row, color in zip(x_values, frame.itertuples(), colors):
        axis.vlines(x_value, row.low, row.high, color=color, linewidth=0.7)
        lower = min(row.open, row.close)
        height = max(abs(row.close - row.open), minimum_body)
        axis.add_patch(
            Rectangle(
                (x_value - 0.34, lower),
                0.68,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.6,
            )
        )
    return colors


def create_winner_figure(
    event: pd.Series,
    bars15: pd.DataFrame,
    window_days: list[pd.Timestamp],
    daily_bars: pd.DataFrame,
) -> object:
    """Create a 15m-price, daily-price and daily-volume three-layer figure."""
    figure = plt.figure(figsize=(18, 12), dpi=150)
    grid = figure.add_gridspec(3, 1, height_ratios=[5, 2.6, 1], hspace=0.12)
    price15_axis = figure.add_subplot(grid[0])
    daily_price_axis = figure.add_subplot(grid[1])
    daily_volume_axis = figure.add_subplot(grid[2], sharex=daily_price_axis)

    entry_day = pd.Timestamp(event["entry_date"]).normalize()
    exit_day = pd.Timestamp(event["exit_date"]).normalize()
    frame15 = bars15.copy()
    day_positions: list[tuple[pd.Timestamp, int, int]] = []
    if frame15.empty:
        price15_axis.text(
            0.5,
            0.5,
            "15-minute chart unavailable: no local bars in requested window",
            ha="center",
            va="center",
            color="#b91c1c",
            fontsize=15,
            transform=price15_axis.transAxes,
        )
    else:
        frame15 = frame15.sort_values(["trading_day", "bar_15m"]).reset_index(drop=True)
        x15 = np.arange(len(frame15), dtype=float)
        _draw_candles(price15_axis, frame15, x15)
        for trading_day, day_frame in frame15.groupby("trading_day", sort=True):
            start = int(day_frame.index.min())
            end = int(day_frame.index.max())
            normalized_day = pd.Timestamp(trading_day).normalize()
            day_positions.append((normalized_day, start, end))
            price15_axis.axvline(start - 0.5, color="#cbd5e1", linewidth=0.6)
            if normalized_day == entry_day:
                price15_axis.axvspan(
                    start - 0.5,
                    end + 0.5,
                    color="#f59e0b",
                    alpha=0.13,
                    label="Entry trading day",
                )
        price15_axis.axvline(len(frame15) - 0.5, color="#cbd5e1", linewidth=0.6)
        tick_positions = [(start + end) / 2 for _, start, end in day_positions]
        tick_labels = [day.strftime("%Y-%m-%d") for day, _, _ in day_positions]
        price15_axis.set_xticks(tick_positions, tick_labels, rotation=25, ha="right")
        price15_axis.set_xlim(-1, len(frame15))

        entry_datetime = pd.to_datetime(
            event.get("entry_datetime", pd.NaT), errors="coerce"
        )
        if pd.notna(entry_datetime) and entry_datetime.time() != datetime.min.time():
            entry_bucket = pd.Timestamp(entry_datetime).floor("15min")
            matches = frame15.index[frame15["bar_15m"].eq(entry_bucket)]
            if len(matches):
                price15_axis.scatter(
                    float(matches[0]),
                    float(event["entry_price"]),
                    s=48,
                    marker="o",
                    color="#2563eb",
                    edgecolor="white",
                    linewidth=0.8,
                    zorder=5,
                    label="Exact entry bucket",
                )
    price15_axis.axhline(
        float(event["entry_price"]),
        color="#2563eb",
        linestyle="--",
        linewidth=1.0,
        label=f"Entry price {float(event['entry_price']):g}",
    )

    daily = daily_bars.copy()
    if daily.empty:
        daily_price_axis.text(
            0.5,
            0.5,
            "Daily chart unavailable: no exact-contract daily bars",
            ha="center",
            va="center",
            color="#b91c1c",
            fontsize=12,
            transform=daily_price_axis.transAxes,
        )
        daily_volume_axis.text(
            0.5,
            0.5,
            "Daily volume unavailable",
            ha="center",
            va="center",
            color="#64748b",
            fontsize=11,
            transform=daily_volume_axis.transAxes,
        )
    else:
        daily = daily.sort_values("trade_date").reset_index(drop=True)
        x_daily = np.arange(len(daily), dtype=float)
        daily_colors = _draw_candles(daily_price_axis, daily, x_daily)
        daily_volume_axis.bar(
            x_daily,
            daily["volume"],
            width=0.72,
            color=daily_colors,
            alpha=0.72,
        )
        for day, color, label in [
            (entry_day, "#f59e0b", "Entry day"),
            (exit_day, "#7c3aed", "Final exit day"),
        ]:
            matches = daily.index[daily["trade_date"].eq(day)]
            if len(matches):
                position = float(matches[0])
                daily_price_axis.axvspan(
                    position - 0.5,
                    position + 0.5,
                    color=color,
                    alpha=0.16,
                    label=label,
                )
                daily_volume_axis.axvspan(
                    position - 0.5,
                    position + 0.5,
                    color=color,
                    alpha=0.16,
                )
        daily_price_axis.axhline(
            float(event["entry_price"]),
            color="#2563eb",
            linestyle="--",
            linewidth=1.0,
            label=f"Entry price {float(event['entry_price']):g}",
        )
        tick_count = min(12, len(daily))
        tick_positions = np.unique(
            np.linspace(0, len(daily) - 1, tick_count, dtype=int)
        )
        tick_labels = [
            pd.Timestamp(daily.iloc[position]["trade_date"]).strftime("%Y-%m-%d")
            for position in tick_positions
        ]
        daily_volume_axis.set_xticks(
            tick_positions,
            tick_labels,
            rotation=30,
            ha="right",
        )
        daily_volume_axis.set_xlim(-1, len(daily))
        daily_price_axis.legend(loc="upper left", fontsize=8, framealpha=0.9, ncols=3)

    title = (
        f"Rank {int(event['winner_rank']):02d} | {event['vt_symbol']} | "
        f"{str(event['direction']).upper()} | Entry {entry_day.date()} | "
        f"Exit {exit_day.date()} | Price {float(event['entry_price']):g} | "
        f"R {float(event['aggregate_r']):.4f} | PnL {float(event['realized_pnl']):,.2f}"
    )
    price15_axis.set_title(title, fontsize=15, pad=12, fontweight="bold")
    price15_axis.set_ylabel("15m Price")
    daily_price_axis.set_ylabel("Daily Price")
    daily_volume_axis.set_ylabel("Daily Volume")
    daily_volume_axis.set_xlabel("Exact-contract daily bars")
    for axis in [price15_axis, daily_price_axis, daily_volume_axis]:
        axis.grid(axis="y", color="#e2e8f0", linewidth=0.55)
    handles, labels = price15_axis.get_legend_handles_labels()
    if handles:
        price15_axis.legend(loc="upper left", fontsize=8, framealpha=0.9)
    daily_price_axis.tick_params(labelbottom=False)
    figure.subplots_adjust(left=0.065, right=0.99, top=0.94, bottom=0.08)
    return figure


def plot_winner(
    event: pd.Series,
    bars15: pd.DataFrame,
    window_days: list[pd.Timestamp],
    output_path: Path,
    *,
    raw_1m_bars: int,
    daily_bars: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Render one three-layer winner chart and return minute coverage facts."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = bars15.sort_values(["trading_day", "bar_15m"]).reset_index(drop=True)
    actual_days = pd.DatetimeIndex(frame["trading_day"].dropna().unique()).normalize()
    expected_days = pd.DatetimeIndex(window_days).normalize()
    figure = create_winner_figure(
        event,
        frame,
        window_days,
        daily_bars if daily_bars is not None else pd.DataFrame(),
    )
    figure.savefig(output_path, facecolor="white")
    plt.close(figure)

    if frame.empty:
        state = "missing"
    else:
        state = "complete" if len(actual_days) == len(expected_days) else "partial"
    entry_day = pd.Timestamp(event["entry_date"]).normalize()
    return {
        "winner_rank": int(event["winner_rank"]),
        "open_trade_id": str(event["open_trade_id"]),
        "vt_symbol": str(event["vt_symbol"]),
        "entry_date": entry_day.date().isoformat(),
        "raw_1m_bars": int(raw_1m_bars),
        "aggregated_15m_bars": int(len(frame)),
        "actual_trading_days": int(len(actual_days)),
        "expected_trading_days": int(len(expected_days)),
        "coverage_state": state,
        "chart_path": output_path.name,
    }


def _write_atlas_pages(chart_paths: list[Path], output_dir: Path) -> list[Path]:
    atlas_paths: list[Path] = []
    for page_number, start in enumerate(range(0, len(chart_paths), 4), start=1):
        page_paths = chart_paths[start : start + 4]
        figure, axes = plt.subplots(2, 2, figsize=(24, 16), dpi=100)
        for axis, chart_path in zip(axes.flat, page_paths):
            axis.imshow(plt.imread(chart_path))
            axis.set_axis_off()
        for axis in axes.flat[len(page_paths) :]:
            axis.set_axis_off()
        figure.suptitle(
            f"Stage847-C9-15w >=2R Winner Atlas | Page {page_number:03d}",
            fontsize=17,
            fontweight="bold",
        )
        figure.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.01, wspace=0.01, hspace=0.04)
        atlas_path = output_dir / f"atlas_page{page_number:03d}.png"
        figure.savefig(atlas_path, facecolor="white")
        plt.close(figure)
        atlas_paths.append(atlas_path)
    return atlas_paths


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_outputs(
    winners: pd.DataFrame,
    minutes: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    output_dir: Path,
    *,
    event_count: int,
    input_hashes: dict[str, str],
    cache_file_count: int = 0,
    daily_context: dict[str, pd.DataFrame] | None = None,
) -> dict[str, object]:
    """Write manifests, charts, atlas pages, hashes, decision and report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ["winner_*.png", "atlas_page*.png"]:
        for stale_path in output_dir.glob(pattern):
            stale_path.unlink()

    manifest = winners.copy().sort_values("winner_rank").reset_index(drop=True)
    manifest.to_csv(output_dir / "winner_manifest.csv", index=False, encoding="utf-8-sig")
    daily_context = daily_context or {}
    daily_source_manifest = build_daily_source_manifest(daily_context)
    daily_source_manifest.to_csv(
        output_dir / "daily_source_manifest.csv",
        index=False,
        encoding="utf-8-sig",
    )
    bars15 = resample_15m(minutes) if not minutes.empty else pd.DataFrame()
    coverage_rows: list[dict[str, object]] = []
    chart_paths: list[Path] = []
    for _, event in manifest.iterrows():
        window_days = select_window_days(event["entry_date"], calendar)
        symbol = str(event["vt_symbol"])
        raw_event = minutes[
            minutes["vt_symbol"].eq(symbol)
            & minutes["trading_day"].isin(window_days)
        ]
        if bars15.empty:
            event_bars15 = pd.DataFrame()
        else:
            event_bars15 = bars15[
                bars15["vt_symbol"].eq(symbol)
                & bars15["trading_day"].isin(window_days)
            ]
        daily_window, daily_facts = select_daily_window(
            event,
            daily_context.get(symbol, pd.DataFrame()),
        )
        chart_path = output_dir / _chart_filename(event)
        coverage_row = plot_winner(
            event,
            event_bars15,
            window_days,
            chart_path,
            raw_1m_bars=len(raw_event),
            daily_bars=daily_window,
        )
        coverage_row.update(daily_facts)
        if "minute_source_kind" in raw_event.columns:
            coverage_row["minute_source_kinds"] = "|".join(
                sorted(raw_event["minute_source_kind"].dropna().astype(str).unique())
            )
            coverage_row["minute_source_file_count"] = int(
                raw_event["minute_source_path"].dropna().nunique()
            )
        else:
            coverage_row["minute_source_kinds"] = ""
            coverage_row["minute_source_file_count"] = 0
        coverage_rows.append(coverage_row)
        chart_paths.append(chart_path)

    coverage = pd.DataFrame(coverage_rows).sort_values("winner_rank")
    coverage.to_csv(output_dir / "coverage_summary.csv", index=False, encoding="utf-8-sig")
    atlas_paths = _write_atlas_pages(chart_paths, output_dir)
    all_pngs = chart_paths + atlas_paths
    pd.DataFrame(
        [{"path": path.name, "sha256": _sha256(path)} for path in all_pngs]
    ).to_csv(output_dir / "png_sha256.csv", index=False, encoding="utf-8-sig")

    state_counts = coverage["coverage_state"].value_counts().to_dict()
    daily_state_counts = coverage["daily_coverage_state"].value_counts().to_dict()
    completed_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    decision: dict[str, object] = {
        "official_version": OFFICIAL_VERSION,
        "requested_start_month": "2020-01",
        "winner_definition": "aggregate realized_pnl / aggregate risk_amount >= 2.0",
        "sort_order": "aggregate_r desc, realized_pnl desc, entry_date asc, open_trade_id asc",
        "timeframe": "15min + daily",
        "layout": "15m_kline+daily_kline+daily_volume",
        "window": "5 official trading days before + entry day + 5 after",
        "daily_window": "60 exact-contract daily bars before entry + holding period + 5 after final exit",
        "daily_source": DAILY_SOURCE,
        "completed_at_asia_shanghai": completed_at,
        "input_sha256": input_hashes,
        "local_contract_cache_file_count": int(cache_file_count),
        "event_count": int(event_count),
        "winner_count": int(len(manifest)),
        "coverage_complete_count": int(state_counts.get("complete", 0)),
        "coverage_partial_count": int(state_counts.get("partial", 0)),
        "coverage_missing_count": int(state_counts.get("missing", 0)),
        "daily_complete_count": int(daily_state_counts.get("complete", 0)),
        "daily_partial_count": int(daily_state_counts.get("partial", 0)),
        "daily_missing_count": int(daily_state_counts.get("missing", 0)),
        "daily_contract_count": int(len(daily_source_manifest)),
        "single_chart_count": int(len(chart_paths)),
        "atlas_page_count": int(len(atlas_paths)),
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "pre_run_overfit_assessment": "否；只解释冻结回测样本，不调参、不改策略。",
        "post_run_overfit_assessment": "否；图谱是事后法证输出，未反向生成规则。",
        "continue_value_assessment": "有；可用于识别赢家形态与数据覆盖问题，但不能单独证明可交易规律。",
    }
    (output_dir / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = f"""# Stage210 C9/15万 >=2R 大赢家三层K线图谱

- 正式版本：`{OFFICIAL_VERSION}`
- 样本起点：`2020-01`
- 聚合事件：{event_count}
- >=2R赢家：{len(manifest)}
- 排序：聚合R降序，其次已实现收益降序、开仓日升序、open_trade_id升序
- 窗口：开仓日前5个正式交易日 + 开仓日 + 后5个正式交易日
- 布局：15分钟K线（无分钟成交量）+ 日K + 日成交量
- 日线窗口：开仓前60根精确合约日K + 完整持仓期 + 最终平仓后5根日K
- 日线来源：`{DAILY_SOURCE}`
- 完整覆盖：{state_counts.get('complete', 0)}
- 部分覆盖：{state_counts.get('partial', 0)}
- 缺失占位：{state_counts.get('missing', 0)}
- 日线完整/部分/缺失：{daily_state_counts.get('complete', 0)} / {daily_state_counts.get('partial', 0)} / {daily_state_counts.get('missing', 0)}
- 本地逐合约分钟缓存文件：{cache_file_count}
- 单图：{len(chart_paths)}
- Atlas页：{len(atlas_paths)}
- 下单/撤单API：0 / 0；CTP未连接

## 判断

本图谱是冻结回测结果的事后法证，不是新回测，也没有修改正式策略。它适合观察赢家路径和本地分钟数据覆盖，但不能把赢家共有形态直接当成未来规则，否则会产生幸存者偏差与过拟合。
"""
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    return decision


def _attach_entry_datetimes(winners: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    frame = trades[
        trades["requested_start_month"].astype(str).eq("2020-01")
    ].copy()
    frame["trade_id"] = frame["trade_id"].astype(str)
    frame["entry_datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    lookup = (
        frame.sort_values("entry_datetime")
        .drop_duplicates("trade_id", keep="first")
        .set_index("trade_id")["entry_datetime"]
    )
    result = winners.copy()
    result["entry_datetime"] = result["open_trade_id"].astype(str).map(lookup)
    trustworthy = result["entry_datetime"].notna() & result["entry_datetime"].dt.time.ne(
        datetime.min.time()
    )
    result.loc[~trustworthy, "entry_datetime"] = pd.NaT
    return result


def run(output_dir: Path = OUTPUT_DIR) -> dict[str, object]:
    """Run the frozen, read-only Stage208 atlas build."""
    input_paths = {
        "closed_lots": CLOSED_LOTS_PATH,
        "curves": CURVES_PATH,
        "trades": TRADES_PATH,
        "minute_bars": MINUTE_PATH,
    }
    missing_inputs = [str(path) for path in input_paths.values() if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"missing frozen inputs: {missing_inputs}")

    closed_lots = pd.read_csv(CLOSED_LOTS_PATH, low_memory=False)
    curves = pd.read_csv(CURVES_PATH, low_memory=False)
    trades = pd.read_csv(TRADES_PATH, low_memory=False)
    winners = build_winner_events(closed_lots)
    winners = _attach_entry_datetimes(winners, trades)
    calendar = build_trading_calendar(curves)
    cache_paths = discover_contract_cache_paths(MINUTE_CACHE_ROOT, winners)
    minutes = load_target_minutes(
        MINUTE_PATH,
        winners,
        calendar,
        fallback_paths=cache_paths,
    )
    daily_context = load_daily_context(winners)
    input_hashes = {name: _sha256(path) for name, path in input_paths.items()}
    cache_hash_rows = [
        {"path": str(path.relative_to(REPO_ROOT)), "sha256": _sha256(path)}
        for path in cache_paths
    ]
    cache_bundle = hashlib.sha256()
    for row in cache_hash_rows:
        cache_bundle.update(f"{row['path']}\0{row['sha256']}\n".encode())
    input_hashes["local_contract_cache_bundle"] = cache_bundle.hexdigest()
    daily_bundle = hashlib.sha256()
    for row in build_daily_source_manifest(daily_context).itertuples(index=False):
        daily_bundle.update(
            f"{row.vt_symbol}\0{row.canonical_sha256}\n".encode("utf-8")
        )
    input_hashes["daily_context_bundle"] = daily_bundle.hexdigest()
    decision = write_outputs(
        winners,
        minutes,
        calendar,
        output_dir,
        event_count=EXPECTED_EVENT_COUNT,
        input_hashes=input_hashes,
        cache_file_count=len(cache_paths),
        daily_context=daily_context,
    )
    pd.DataFrame(cache_hash_rows).to_csv(
        output_dir / "minute_cache_sha256.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return decision


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time, timedelta
import hashlib
import html
import json
import math
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs
from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim


REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLES_DIR = REPO_ROOT / "examples" / "portfolio_backtesting"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719  # noqa: E402
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: E402
from qmt_roll_official_live_config import (  # noqa: E402
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_VERSION,
)
from vnpy.trader.setting import SETTINGS  # noqa: E402
from vnpy.trader.utility import ZoneInfo  # noqa: E402


LINE_ID = "futures_trend_winner_trade_forensics"
STAGE = "Stage038"
MODEL_TAG = "stage038_c9_15w_big_winner_multiscale_html_v1"
OUTPUT_DIR = (
    REPO_ROOT
    / "research"
    / "lines"
    / LINE_ID
    / "outputs"
    / "stage038_c9_15w_big_winner_multiscale_html"
)
HTML_PATH = OUTPUT_DIR / "index.html"
CLOSED_LOTS_PATH = OUTPUT_DIR / "closed_lots.csv"
WINNERS_PATH = OUTPUT_DIR / "big_winners.csv"
SELECTED_EPISODES_PATH = OUTPUT_DIR / "selected_profit_loss_episodes.csv"
MINUTE_15M_PATH = OUTPUT_DIR / "winner_bars_15m.csv"
STRATEGY_DAILY_PATH = OUTPUT_DIR / "strategy_daily.csv"
MANIFEST_PATH = OUTPUT_DIR / "chart_manifest.csv"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"
DAILY_PATH = EXAMPLES_DIR / "backtest_outputs" / (
    "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_daily_"
    "stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
)
DATABASE_PATH = REPO_ROOT / ".vntrader" / "database.db"
MAPPING_PATH = EXAMPLES_DIR / "backtest_outputs" / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"

START = pd.Timestamp("2018-01-01")
DEFAULT_END = pd.Timestamp("2026-08-12")
DAILY_PRE = 30
DAILY_POST = 30
INTRADAY_PRE = 5
INTRADAY_POST = 5
CHINA_TZ = ZoneInfo("Asia/Shanghai")
MA_PERIODS = (5, 10, 20, 40)
# Include a small whole-week cushion because the earliest available source
# week can be partial even when the product calendar contains that period.
WEEKLY_MA_WARMUP_WEEKS = max(MA_PERIODS) + 5


@dataclass(frozen=True)
class FetchStatus:
    vt_symbol: str
    tq_symbol: str
    start: str
    end: str
    rows: int
    elapsed_seconds: float
    status: str
    message: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _latest_completed_date() -> pd.Timestamp:
    if DAILY_PATH.exists():
        daily = pd.read_csv(DAILY_PATH, usecols=["date"])
        values = pd.to_datetime(daily["date"], errors="coerce").dropna()
        if len(values):
            return pd.Timestamp(values.max()).normalize()
    return DEFAULT_END


def _run_current_c9(end: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], Any]:
    metadata = s513._metadata()
    combined, frames, spec = s901._run_live_c9(metadata, START, end)
    closed = s719._build_closed_lots(
        frames.get("trades", pd.DataFrame()),
        frames.get("entry_risk", pd.DataFrame()),
        frames.get("entry_candidates", pd.DataFrame()),
        metadata,
    )
    if closed.empty:
        raise RuntimeError("Current C9/15w replay produced no closed lots.")
    closed["official_live_version"] = OFFICIAL_LIVE_VERSION
    closed["account_capital"] = OFFICIAL_LIVE_CAPITAL
    selected = _selected_tail_episodes(closed)
    if selected.empty:
        raise RuntimeError("Current C9/15w replay produced no profit/loss tail episodes.")
    return combined, closed, frames, spec


def _trade_episodes(closed: pd.DataFrame) -> pd.DataFrame:
    """Collapse every entry and its partial exits into one complete episode."""
    rows: list[dict[str, Any]] = []
    for open_trade_id, group in closed.groupby("open_trade_id", sort=False):
        group = group.sort_values(["exit_date", "lot_id"]).reset_index(drop=True)
        first, final = group.iloc[0], group.iloc[-1]
        risk_amount = pd.to_numeric(group["risk_amount"], errors="coerce").sum(min_count=1)
        realized_pnl = float(pd.to_numeric(group["realized_pnl"], errors="coerce").sum())
        rows.append(
            {
                **first.to_dict(),
                "lot_id": ",".join(group["lot_id"].astype(str)),
                "close_trade_id": ",".join(group["close_trade_id"].astype(str)),
                "open_trade_id": str(open_trade_id),
                "exit_date": final["exit_date"],
                "exit_price": float(final["exit_price"]),
                "exit_reason": str(final["exit_reason"]),
                "volume": float(pd.to_numeric(group["volume"], errors="coerce").sum()),
                "realized_pnl": realized_pnl,
                "risk_amount": risk_amount,
                "r_multiple": realized_pnl / risk_amount if pd.notna(risk_amount) and risk_amount else np.nan,
                "holding_calendar_days": int((pd.Timestamp(final["exit_date"]) - pd.Timestamp(first["entry_date"])).days),
                "lot_count": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def _selected_tail_episodes(closed: pd.DataFrame) -> pd.DataFrame:
    """Select symmetric profit/loss R tails from complete entry episodes."""
    episodes = _trade_episodes(closed)
    positive = episodes[episodes["realized_pnl"].gt(0.0)]
    negative = episodes[episodes["realized_pnl"].lt(0.0)]
    profit_r_threshold = float(positive.loc[positive["r_multiple"].gt(0.0), "r_multiple"].quantile(0.80))
    profit_pnl_threshold = float(positive["realized_pnl"].quantile(0.80))
    loss_r_threshold = float(negative.loc[negative["r_multiple"].lt(0.0), "r_multiple"].quantile(0.20))
    loss_pnl_threshold = float(negative["realized_pnl"].quantile(0.20))
    profit_selected = episodes["realized_pnl"].gt(0.0) & (
        episodes["r_multiple"].ge(profit_r_threshold)
        | (episodes["r_multiple"].isna() & episodes["realized_pnl"].ge(profit_pnl_threshold))
    )
    loss_selected = episodes["realized_pnl"].lt(0.0) & (
        episodes["r_multiple"].le(loss_r_threshold)
        | (episodes["r_multiple"].isna() & episodes["realized_pnl"].le(loss_pnl_threshold))
    )
    episodes["result_type"] = np.where(
        profit_selected,
        "profit",
        np.where(loss_selected, "loss", "not_selected"),
    )
    episodes["selection_basis"] = np.where(
        episodes["r_multiple"].ge(profit_r_threshold) & profit_selected,
        "episode R前20%",
        np.where(
            episodes["r_multiple"].isna() & profit_selected,
            "episode盈利额前20%（R缺失）",
            np.where(
                episodes["r_multiple"].le(loss_r_threshold) & loss_selected,
                "episode亏损R最差20%",
                np.where(
                    episodes["r_multiple"].isna() & loss_selected,
                    "episode亏损额最差20%（R缺失）",
                    "未入选",
                ),
            ),
        ),
    )
    episodes["profit_r_threshold"] = profit_r_threshold
    episodes["profit_pnl_threshold"] = profit_pnl_threshold
    episodes["loss_r_threshold"] = loss_r_threshold
    episodes["loss_pnl_threshold"] = loss_pnl_threshold
    result = episodes[episodes["result_type"].ne("not_selected")].copy()
    result["r_magnitude"] = result["r_multiple"].abs()
    result = result.sort_values(
        ["result_type", "r_magnitude", "realized_pnl"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    result["result_rank"] = result.groupby("result_type", sort=False).cumcount() + 1
    return result


def _contract_daily(vt_symbol: str) -> pd.DataFrame:
    bars = s719._read_contract_bars(vt_symbol).copy()
    if bars.empty:
        symbol, exchange = vt_symbol.split(".", 1)
        with sqlite3.connect(DATABASE_PATH) as connection:
            bars = pd.read_sql_query(
                """
                SELECT datetime AS date,
                       open_price AS open,
                       high_price AS high,
                       low_price AS low,
                       close_price AS close,
                       volume,
                       open_interest AS close_oi
                  FROM dbbardata
                 WHERE symbol = ? AND exchange = ? AND interval = 'd'
                 ORDER BY datetime
                """,
                connection,
                params=(symbol, exchange),
            )
    if bars.empty:
        raise RuntimeError(f"Missing daily bars in CSV and vn.py database for {vt_symbol}.")
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars = bars.dropna(subset=["date", "open", "high", "low", "close"]).copy()
    if "volume" not in bars.columns:
        bars["volume"] = 0.0
    bars["volume"] = pd.to_numeric(bars["volume"], errors="coerce").fillna(0.0)
    return bars.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def _date_index(daily: pd.DataFrame, value: Any, *, exact: bool = False) -> int:
    date = pd.Timestamp(value).normalize()
    dates = daily["date"].to_numpy(dtype="datetime64[ns]")
    matches = np.flatnonzero(dates == np.datetime64(date))
    if len(matches):
        return int(matches[0])
    if exact:
        raise RuntimeError(f"Required trading day {date.date()} is absent from the chart calendar.")
    position = int(np.searchsorted(dates, np.datetime64(date)))
    return min(max(position, 0), len(daily) - 1)


def _window_dates(daily: pd.DataFrame, entry: Any, exit_: Any, pre: int, post: int) -> list[pd.Timestamp]:
    entry_index = _date_index(daily, entry, exact=True)
    exit_index = _date_index(daily, exit_, exact=True)
    start = max(0, entry_index - pre)
    end = min(len(daily), exit_index + post + 1)
    return [pd.Timestamp(value).normalize() for value in daily.iloc[start:end]["date"]]


def _main_mapping() -> pd.DataFrame:
    mapping = pd.read_csv(MAPPING_PATH, encoding="utf-8-sig")
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    mapping = mapping.dropna(subset=["date", "main_contract_vt"]).copy()
    return mapping.sort_values(["product", "exchange", "date"]).reset_index(drop=True)


def _product_calendar(mapping: pd.DataFrame, vt_symbol: str) -> list[pd.Timestamp]:
    exchange = str(vt_symbol).split(".", 1)[1]
    product = s719._infer_product(vt_symbol)
    values = mapping[
        mapping["product"].astype(str).str.lower().eq(product.lower()) & mapping["exchange"].eq(exchange)
    ]["date"].drop_duplicates().sort_values()
    if values.empty:
        raise RuntimeError(f"Missing product trading calendar for {vt_symbol}.")
    return [pd.Timestamp(value).normalize() for value in values]


def _context_daily(
    row: Any,
    mapping: pd.DataFrame,
    bar_cache: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    product_value = str(row.product)
    if "." in product_value:
        product, exchange = product_value.split(".", 1)
    else:
        product = product_value
        exchange = str(row.vt_symbol).split(".", 1)[1]
    calendar = mapping[
        mapping["product"].astype(str).str.lower().eq(product.lower()) & mapping["exchange"].eq(exchange)
    ].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    entry_date = pd.Timestamp(row.entry_date).normalize()
    exit_date = pd.Timestamp(row.exit_date).normalize()
    entry_index = _date_index(calendar, entry_date, exact=True)
    exit_index = _date_index(calendar, exit_date, exact=True)
    display_start = max(0, entry_index - DAILY_PRE)
    display_end = min(len(calendar), exit_index + DAILY_POST + 1)
    first_period = calendar.loc[display_start, "date"].to_period("W-FRI")
    last_period = calendar.loc[display_end - 1, "date"].to_period("W-FRI")
    while display_start > 0 and calendar.loc[display_start - 1, "date"].to_period("W-FRI") == first_period:
        display_start -= 1
    while display_end < len(calendar) and calendar.loc[display_end, "date"].to_period("W-FRI") == last_period:
        display_end += 1
    display_dates = set(calendar.iloc[display_start:display_end]["date"])

    # Keep the requested chart window unchanged, but load enough earlier daily
    # bars to seed a genuine 40-week moving average on the first visible week.
    warmup_start = display_start
    if display_start > 0:
        prior_periods = (
            calendar.iloc[:display_start]["date"]
            .dt.to_period("W-FRI")
            .drop_duplicates()
            .tail(WEEKLY_MA_WARMUP_WEEKS)
        )
        if len(prior_periods):
            first_warmup_period = prior_periods.iloc[0]
            warmup_start = int(
                calendar.index[
                    calendar["date"].dt.to_period("W-FRI").eq(first_warmup_period)
                ][0]
            )
    wanted = calendar.iloc[warmup_start:display_end].copy()
    def bars(source: str) -> pd.DataFrame:
        if source not in bar_cache:
            bar_cache[source] = _contract_daily(source)
        return bar_cache[source]

    exact_bars = bars(str(row.vt_symbol))
    exact_by_date = exact_bars.set_index("date")
    output: list[dict[str, Any]] = []
    for item in wanted.itertuples(index=False):
        source = str(row.vt_symbol) if item.date in exact_by_date.index else str(item.main_contract_vt)
        source_bars = bars(source)
        matched = source_bars[source_bars["date"].eq(item.date)]
        if matched.empty:
            downloaded = _fetch_daily_tq(source, wanted["date"].min(), wanted["date"].max())
            source_bars = (
                pd.concat([source_bars, downloaded], ignore_index=True, sort=False)
                .drop_duplicates("date", keep="last")
                .sort_values("date")
                .reset_index(drop=True)
            )
            bar_cache[source] = source_bars
            matched = source_bars[source_bars["date"].eq(item.date)]
        if matched.empty:
            raise RuntimeError(f"Missing daily context bar for {row.open_trade_id}: {source} {item.date.date()}.")
        bar = matched.iloc[0].to_dict()
        bar["source_vt_symbol"] = source
        bar["context_fallback"] = int(source != str(row.vt_symbol))
        bar["display"] = int(item.date in display_dates)
        output.append(bar)
    daily = pd.DataFrame(output).sort_values("date").reset_index(drop=True)
    _date_index(daily, entry_date, exact=True)
    _date_index(daily, exit_date, exact=True)
    intraday_dates = _window_dates(calendar, entry_date, exit_date, INTRADAY_PRE, INTRADAY_POST)
    return daily, intraday_dates


def _to_tq_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _normalize_tq_datetime(value: Any) -> pd.Timestamp:
    timestamp = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(timestamp):
        return pd.NaT
    return timestamp.tz_convert(CHINA_TZ).tz_localize(None)


def _fetch_15m(vt_symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, FetchStatus]:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    tq_symbol = _to_tq_symbol(vt_symbol)
    replay_start = (start - pd.Timedelta(days=3)).to_pydatetime()
    # Keep enough future time for the final requested bar to become the
    # completed previous row even across Golden Week / Spring Festival.
    replay_end = (end + pd.Timedelta(days=14, hours=23, minutes=59)).to_pydatetime()
    api: TqApi | None = None
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    status = "unknown"
    message = ""
    started = time.time()
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=replay_start, end_dt=replay_end),
            auth=TqAuth(username, password),
        )
        serial = api.get_kline_serial(tq_symbol, duration_seconds=15 * 60, data_length=500)
        while True:
            api.wait_update()
            if not api.is_changing(serial.iloc[-1], "datetime"):
                continue
            # The last row is the newly forming bar.  Only the previous row is
            # complete and carries authoritative OHLC/volume.
            raw = serial.iloc[-2].to_dict()
            bar_id = int(raw.get("id", -1))
            if bar_id in seen:
                continue
            seen.add(bar_id)
            bar_datetime = _normalize_tq_datetime(raw.get("datetime"))
            if pd.isna(bar_datetime):
                continue
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "tq_symbol": tq_symbol,
                    "bar_datetime": bar_datetime,
                    "bar_id": bar_id,
                    "open": float(raw.get("open", np.nan)),
                    "high": float(raw.get("high", np.nan)),
                    "low": float(raw.get("low", np.nan)),
                    "close": float(raw.get("close", np.nan)),
                    "volume": float(raw.get("volume", np.nan)),
                    "open_oi": float(raw.get("open_oi", np.nan)),
                    "close_oi": float(raw.get("close_oi", np.nan)),
                }
            )
    except BacktestFinished:
        status = "extracted"
    except Exception as exc:
        status = "failed"
        message = repr(exc)
    finally:
        if api is not None:
            api.close()
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.dropna(subset=["bar_datetime", "open", "high", "low", "close"])
        frame = frame.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values("bar_datetime").reset_index(drop=True)
    if status == "unknown":
        status = "extracted" if len(frame) else "failed"
    fetch_status = FetchStatus(
        vt_symbol=vt_symbol,
        tq_symbol=tq_symbol,
        start=start.date().isoformat(),
        end=end.date().isoformat(),
        rows=int(len(frame)),
        elapsed_seconds=round(time.time() - started, 3),
        status=status,
        message=message,
    )
    if status != "extracted" or frame.empty:
        raise RuntimeError(f"15m fetch failed for {vt_symbol}: {asdict(fetch_status)}")
    return frame, fetch_status


def _fetch_daily_tq(vt_symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    api: TqApi | None = None
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(
                start_dt=(start - pd.Timedelta(days=20)).to_pydatetime(),
                end_dt=(end + pd.Timedelta(days=20)).to_pydatetime(),
            ),
            auth=TqAuth(username, password),
        )
        serial = api.get_kline_serial(_to_tq_symbol(vt_symbol), duration_seconds=24 * 60 * 60, data_length=200)
        while True:
            api.wait_update()
            if not api.is_changing(serial.iloc[-1], "datetime"):
                continue
            raw = serial.iloc[-2].to_dict()
            bar_id = int(raw.get("id", -1))
            if bar_id in seen:
                continue
            seen.add(bar_id)
            value = _normalize_tq_datetime(raw.get("datetime"))
            if pd.isna(value):
                continue
            rows.append(
                {
                    "date": value.normalize(),
                    "open": float(raw.get("open", np.nan)),
                    "high": float(raw.get("high", np.nan)),
                    "low": float(raw.get("low", np.nan)),
                    "close": float(raw.get("close", np.nan)),
                    "volume": float(raw.get("volume", np.nan)),
                    "close_oi": float(raw.get("close_oi", np.nan)),
                }
            )
    except BacktestFinished:
        pass
    finally:
        if api is not None:
            api.close()
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.dropna(subset=["date", "open", "high", "low", "close"]).drop_duplicates("date").reset_index(drop=True)


def _assign_trading_day(frame: pd.DataFrame, daily_dates: list[pd.Timestamp]) -> pd.DataFrame:
    result = frame.copy()
    dates = np.array(daily_dates, dtype="datetime64[ns]")

    def resolve(value: Any) -> pd.Timestamp | pd.NaT:
        timestamp = pd.Timestamp(value)
        calendar_date = timestamp.normalize()
        clock = timestamp.time()
        side = "right" if clock >= dt_time(20, 0) else "left"
        position = int(np.searchsorted(dates, np.datetime64(calendar_date), side=side))
        if position >= len(dates):
            return pd.NaT
        candidate = pd.Timestamp(dates[position]).normalize()
        if dt_time(3, 0) <= clock < dt_time(20, 0) and candidate != calendar_date:
            return pd.NaT
        return candidate

    result["trading_day"] = result["bar_datetime"].map(resolve)
    return result.dropna(subset=["trading_day"]).reset_index(drop=True)


def _weekly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    data = daily.copy()
    data["week"] = data["date"].dt.to_period("W-FRI").astype(str)
    return (
        data.groupby("week", sort=False)
        .agg(
            date_start=("date", "min"),
            date_end=("date", "max"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )


def _add_moving_averages(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = pd.to_numeric(result["close"], errors="coerce")
    for period in MA_PERIODS:
        result[f"ma{period}"] = close.rolling(period, min_periods=period).mean()
    return result


def _records(
    winners: pd.DataFrame,
    daily_by_episode: dict[str, pd.DataFrame],
    intraday_dates_by_episode: dict[str, list[pd.Timestamp]],
    bars_15m: pd.DataFrame,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    minute_by_symbol = {key: group.copy() for key, group in bars_15m.groupby("vt_symbol", sort=False)}
    records: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for row in winners.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        episode_id = str(row.open_trade_id)
        daily_full = daily_by_episode[episode_id].copy().reset_index(drop=True)
        daily = daily_full[daily_full["display"].eq(1)].copy().reset_index(drop=True)
        entry_date = pd.Timestamp(row.entry_date).normalize()
        exit_date = pd.Timestamp(row.exit_date).normalize()
        entry_index = _date_index(daily, entry_date, exact=True)
        exit_index = _date_index(daily, exit_date, exact=True)
        day_positions = {date: index for index, date in enumerate(daily["date"])}
        daily["x"] = np.arange(len(daily), dtype=float) + 0.5
        intraday_dates = intraday_dates_by_episode[episode_id]
        minute_parts: list[pd.DataFrame] = []
        for trading_day in intraday_dates:
            daily_row = daily[daily["date"].eq(trading_day)]
            if daily_row.empty:
                continue
            source = str(daily_row.iloc[0]["source_vt_symbol"])
            source_minute = minute_by_symbol.get(source, pd.DataFrame())
            if not source_minute.empty:
                minute_parts.append(source_minute[source_minute["trading_day"].eq(trading_day)].copy())
        minute = pd.concat(minute_parts, ignore_index=True, sort=False) if minute_parts else pd.DataFrame()
        minute = minute.sort_values(["trading_day", "bar_datetime"]).reset_index(drop=True)
        # Within the shared 15m window, derive the daily candle from the very
        # same intraday source.  This avoids provider-specific volume scaling
        # and rollover-day OHLC disagreements between unrelated feeds.
        aggregated_days: list[str] = []
        for trading_day, group in minute.groupby("trading_day", sort=False):
            target = daily_full.index[daily_full["date"].eq(trading_day)]
            if len(target) != 1:
                continue
            index = int(target[0])
            daily_full.loc[index, ["open", "high", "low", "close", "volume"]] = [
                group["open"].iloc[0],
                group["high"].max(),
                group["low"].min(),
                group["close"].iloc[-1],
                group["volume"].sum(),
            ]
            aggregated_days.append(pd.Timestamp(trading_day).date().isoformat())
        daily_full = _add_moving_averages(daily_full)
        weekly_full = _add_moving_averages(_weekly_from_daily(daily_full))
        display_start_date = daily.loc[0, "date"]
        display_end_date = daily.loc[len(daily) - 1, "date"]
        daily = daily_full[daily_full["display"].eq(1)].copy().reset_index(drop=True)
        weekly = weekly_full[
            weekly_full["date_start"].ge(display_start_date)
            & weekly_full["date_end"].le(display_end_date)
        ].copy().reset_index(drop=True)
        day_positions = {date: index for index, date in enumerate(daily["date"])}
        daily["x"] = np.arange(len(daily), dtype=float) + 0.5
        weekly["x"] = [
            float(np.mean([day_positions[value] + 0.5 for value in daily.loc[daily["date"].between(start, end), "date"]]))
            for start, end in zip(weekly["date_start"], weekly["date_end"], strict=False)
        ]
        weekly["width"] = [
            int(daily["date"].between(start, end).sum()) * 0.78
            for start, end in zip(weekly["date_start"], weekly["date_end"], strict=False)
        ]
        minute["x"] = np.nan
        for trading_day, indices in minute.groupby("trading_day", sort=False).groups.items():
            if trading_day not in day_positions:
                continue
            index_list = list(indices)
            count = len(index_list)
            minute.loc[index_list, "x"] = day_positions[trading_day] + (np.arange(count) + 0.5) / count
        minute = minute.dropna(subset=["x"]).reset_index(drop=True)
        minute = _add_moving_averages(minute)
        covered_dates = set(pd.to_datetime(minute["trading_day"]).dt.normalize())
        missing_dates = [value.date().isoformat() for value in intraday_dates if value not in covered_dates]
        entry_x = float(day_positions[entry_date] + 0.5)
        exit_x = float(day_positions[exit_date] + 0.5)
        fallback_days = [
            value.date().isoformat() for value in daily.loc[daily["context_fallback"].eq(1), "date"]
        ]
        entry_source = str(daily.loc[daily["date"].eq(entry_date), "source_vt_symbol"].iloc[0])
        exit_source = str(daily.loc[daily["date"].eq(exit_date), "source_vt_symbol"].iloc[0])
        source_switch_x = [
            float(index + 0.5)
            for index in range(1, len(daily))
            if daily.loc[index, "source_vt_symbol"] != daily.loc[index - 1, "source_vt_symbol"]
        ]

        def series(frame: pd.DataFrame, column: str) -> list[Any]:
            return [_json_safe(item) for item in frame[column].tolist()]

        record = {
            "meta": {
                "result_rank": int(row.result_rank),
                "result_type": str(row.result_type),
                "lot_id": str(row.lot_id),
                "lot_count": int(row.lot_count),
                "open_trade_id": str(row.open_trade_id),
                "close_trade_id": str(row.close_trade_id),
                "vt_symbol": vt_symbol,
                "product": str(row.product),
                "direction": str(row.direction),
                "entry_date": entry_date.date().isoformat(),
                "exit_date": exit_date.date().isoformat(),
                "entry_price": float(row.entry_price),
                "exit_price": float(row.exit_price),
                "volume": float(row.volume),
                "realized_pnl": float(row.realized_pnl),
                "r_multiple": float(row.r_multiple),
                "selection_basis": str(row.selection_basis),
                "holding_calendar_days": int(row.holding_calendar_days),
                "exit_reason": str(row.exit_reason),
                "signal": str(row.signal),
                "profit_r_threshold": float(row.profit_r_threshold),
                "loss_r_threshold": float(row.loss_r_threshold),
                "entry_x": entry_x,
                "exit_x": exit_x,
                "daily_start": daily["date"].iloc[0].date().isoformat(),
                "daily_end": daily["date"].iloc[-1].date().isoformat(),
                "intraday_start": intraday_dates[0].date().isoformat(),
                "intraday_end": intraday_dates[-1].date().isoformat(),
                "missing_15m_dates": missing_dates,
                "context_fallback_dates": fallback_days,
                "source_switch_x": source_switch_x,
                "entry_source": entry_source,
                "exit_source": exit_source,
                "entry_marker_price": float(row.entry_price) if entry_source == vt_symbol else None,
                "exit_marker_price": float(row.exit_price) if exit_source == vt_symbol else None,
                "daily_from_15m_dates": aggregated_days,
            },
            "daily": {
                "x": series(daily, "x"),
                "date": [value.date().isoformat() for value in daily["date"]],
                "open": series(daily, "open"),
                "high": series(daily, "high"),
                "low": series(daily, "low"),
                "close": series(daily, "close"),
                "volume": series(daily, "volume"),
                "source": daily["source_vt_symbol"].tolist(),
                **{f"ma{period}": series(daily, f"ma{period}") for period in MA_PERIODS},
            },
            "weekly": {
                "x": series(weekly, "x"),
                "label": weekly["week"].tolist(),
                "open": series(weekly, "open"),
                "high": series(weekly, "high"),
                "low": series(weekly, "low"),
                "close": series(weekly, "close"),
                "volume": series(weekly, "volume"),
                "width": series(weekly, "width"),
                **{f"ma{period}": series(weekly, f"ma{period}") for period in MA_PERIODS},
            },
            "intraday": {
                "x": series(minute, "x"),
                "datetime": [pd.Timestamp(value).strftime("%Y-%m-%d %H:%M") for value in minute["bar_datetime"]],
                "trading_day": [pd.Timestamp(value).date().isoformat() for value in minute["trading_day"]],
                "open": series(minute, "open"),
                "high": series(minute, "high"),
                "low": series(minute, "low"),
                "close": series(minute, "close"),
                "volume": series(minute, "volume"),
                "source": minute["vt_symbol"].tolist(),
                **{f"ma{period}": series(minute, f"ma{period}") for period in MA_PERIODS},
            },
        }
        records.append(record)
        manifest_rows.append(
            {
                **record["meta"],
                "daily_bars": len(daily),
                "weekly_bars": len(weekly),
                "bars_15m": len(minute),
                "intraday_expected_days": len(intraday_dates),
                "intraday_covered_days": len(covered_dates.intersection(intraday_dates)),
                "intraday_missing_days": len(missing_dates),
                "context_fallback_days": len(fallback_days),
            }
        )
    return records, pd.DataFrame(manifest_rows)


def _html(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    records_json = json.dumps(_json_safe(records), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    summary_json = json.dumps(_json_safe(summary), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    plotly_js = get_plotlyjs()
    title = "C9/15万历史盈亏尾部：周K × 日K × 15分钟K 逐笔复盘"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><script>{plotly_js}</script>
<style>
:root{{--bg:#f4f6f8;--panel:#fff;--line:#d9dee7;--text:#17202a;--muted:#667085;--blue:#2563eb;--purple:#9333ea}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.page{{max-width:1760px;margin:0 auto;padding:16px}} h1{{font-size:24px;margin:0 0 10px}}
.note{{font-size:13px;color:var(--muted);margin-bottom:12px}} .toolbar{{display:grid;grid-template-columns:160px 180px 150px 170px minmax(300px,1fr) auto auto;gap:8px;margin-bottom:10px}}
select,button{{height:38px;border:1px solid var(--line);border-radius:7px;background:#fff;padding:0 10px;font-size:13px}} button{{cursor:pointer}}
.metrics{{display:grid;grid-template-columns:repeat(8,minmax(120px,1fr));gap:8px;margin-bottom:10px}} .metric{{background:#fff;border:1px solid var(--line);border-radius:7px;padding:8px 10px}}
.metric .k{{font-size:11px;color:var(--muted)}} .metric .v{{font-size:16px;font-weight:700;margin-top:3px}}
.panel{{background:#fff;border:1px solid var(--line);border-radius:8px}} #chart{{height:1240px;width:100%}}
.footer{{font-size:12px;color:var(--muted);padding:10px 2px}} .warn{{color:#b42318;font-weight:600}}
@media(max-width:1000px){{.toolbar{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,1fr)}}#chart{{height:1050px}}}}
</style></head><body><div class="page"><h1>{html.escape(title)}</h1>
<div class="note">每周、每日和每个15分钟柱共用交易日坐标，并分别叠加 MA5/10/20/40；周K和日K使用图窗外历史预热，历史不足完整周期时均线留空，不用短样本冒充。蓝线=开仓日，紫线=最终平仓日，淡黄色=持仓区间。15m窗口内的日K由同一批15m聚合；灰虚线表示精确合约缺历史数据后切到当日主力上下文。成交线只定位交易日，不伪造分钟成交时刻；若平仓日已切换上下文，则不把旧合约成交价画到代理K线上。</div>
<div class="toolbar"><select id="result"><option value="profit">盈利交易</option><option value="loss">亏损交易</option></select><select id="sort"><option value="extreme">R绝对值从大到小</option><option value="near">R绝对值从小到大</option></select><select id="year"></select><select id="product"></select><select id="trade"></select><button id="prev">上一笔</button><button id="next">下一笔</button></div>
<div id="metrics" class="metrics"></div><div class="panel"><div id="chart"></div></div>
<div class="footer">数据：当前正式 {html.escape(OFFICIAL_LIVE_ALIAS)}（{html.escape(OFFICIAL_LIVE_VERSION)}）；盈利侧=正R前20%，亏损侧=负R最差20%，两侧均可补入R缺失时的同方向盈亏额尾部；部分平仓按一次开仓聚合到最终平仓。本图用于对照复盘，不是交易规则。</div>
</div><script>
const records={records_json}; const summary={summary_json}; let filtered=[]; let active=0;
const resultEl=document.getElementById('result'), sortEl=document.getElementById('sort'), yearEl=document.getElementById('year'), productEl=document.getElementById('product'), tradeEl=document.getElementById('trade');
const fmt=(v,d=2)=>Number(v).toLocaleString('zh-CN',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const uniq=a=>[...new Set(a)].sort();
function options(el,values,label){{el.innerHTML=`<option value="">全部${{label}}</option>`+values.map(v=>`<option value="${{v}}">${{v}}</option>`).join('')}}
options(yearEl,uniq(records.map(r=>r.meta.entry_date.slice(0,4))),'年份'); options(productEl,uniq(records.map(r=>r.meta.product)),'品种');
function apply(){{const result=resultEl.value,y=yearEl.value,p=productEl.value,extreme=sortEl.value==='extreme';filtered=records.filter(r=>r.meta.result_type===result&&(!y||r.meta.entry_date.startsWith(y))&&(!p||r.meta.product===p));filtered.sort((a,b)=>{{const ar=a.meta.r_multiple===null?null:Math.abs(Number(a.meta.r_multiple)),br=b.meta.r_multiple===null?null:Math.abs(Number(b.meta.r_multiple));if(ar===null&&br===null)return Math.abs(b.meta.realized_pnl)-Math.abs(a.meta.realized_pnl);if(ar===null)return 1;if(br===null)return -1;return extreme?br-ar:ar-br}});active=0;refreshSelect();render()}}
function rfmt(v){{return v===null?'N/A':fmt(v)}}
function refreshSelect(){{tradeEl.innerHTML=filtered.map((r,i)=>`<option value="${{i}}">#${{i+1}} ${{r.meta.vt_symbol}} ${{r.meta.direction}} R=${{rfmt(r.meta.r_multiple)}} ${{r.meta.entry_date}}→${{r.meta.exit_date}}</option>`).join('');tradeEl.value=String(active)}}
function colors(o,c){{return o.map((v,i)=>c[i]>=v?'#d92d20':'#039855')}}
function render(){{if(!filtered.length){{Plotly.purge('chart');document.getElementById('metrics').innerHTML='<div class="warn">没有符合筛选条件的交易</div>';return}}
 const r=filtered[active],m=r.meta,d=r.daily,w=r.weekly,q=r.intraday; tradeEl.value=String(active);
 const missing=m.missing_15m_dates.length?`<span class="warn">${{m.missing_15m_dates.length}}日缺15m</span>`:'完整';
 const source=m.context_fallback_dates.length?`${{m.context_fallback_dates.length}}日主力代理`:'全程精确合约';
 const resultLabel=m.result_type==='profit'?'盈利':'亏损';
 const metric=[['R排序',`#${{active+1}}`],['结果',resultLabel],['合约',m.vt_symbol],['方向',m.direction],['净利润',fmt(m.realized_pnl,0)],['R倍数',rfmt(m.r_multiple)],['平仓lot',m.lot_count],['15m覆盖',missing]];
 document.getElementById('metrics').innerHTML=metric.map(([k,v])=>`<div class="metric"><div class="k">${{k}}</div><div class="v">${{v}}</div></div>`).join('');
 const traces=[
  {{type:'candlestick',x:w.x,open:w.open,high:w.high,low:w.low,close:w.close,name:'周K',yaxis:'y',showlegend:false,increasing:{{line:{{color:'#d92d20'}}}},decreasing:{{line:{{color:'#039855'}}}}}},
  {{type:'scatter',mode:'lines',x:w.x,y:w.ma5,yaxis:'y',name:'周MA5',showlegend:false,line:{{color:'#f59e0b',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:w.x,y:w.ma10,yaxis:'y',name:'周MA10',showlegend:false,line:{{color:'#2563eb',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:w.x,y:w.ma20,yaxis:'y',name:'周MA20',showlegend:false,line:{{color:'#9333ea',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:w.x,y:w.ma40,yaxis:'y',name:'周MA40',showlegend:false,line:{{color:'#111827',width:1.5}}}},
  {{type:'bar',x:w.x,y:w.volume,width:w.width,marker:{{color:colors(w.open,w.close),opacity:.55}},name:'周成交量',yaxis:'y2',showlegend:false,hovertext:w.label,hovertemplate:'%{{hovertext}}<br>Vol=%{{y:,.0f}}<extra></extra>'}},
  {{type:'candlestick',x:d.x,open:d.open,high:d.high,low:d.low,close:d.close,name:'日K',yaxis:'y3',showlegend:false,customdata:d.source,hovertemplate:'%{{customdata}}<br>O=%{{open}} H=%{{high}}<br>L=%{{low}} C=%{{close}}<extra></extra>',increasing:{{line:{{color:'#d92d20'}}}},decreasing:{{line:{{color:'#039855'}}}}}},
  {{type:'scatter',mode:'lines',x:d.x,y:d.ma5,yaxis:'y3',name:'MA5',legendgroup:'ma',line:{{color:'#f59e0b',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:d.x,y:d.ma10,yaxis:'y3',name:'MA10',legendgroup:'ma',line:{{color:'#2563eb',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:d.x,y:d.ma20,yaxis:'y3',name:'MA20',legendgroup:'ma',line:{{color:'#9333ea',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:d.x,y:d.ma40,yaxis:'y3',name:'MA40',legendgroup:'ma',line:{{color:'#111827',width:1.5}}}},
  {{type:'bar',x:d.x,y:d.volume,width:.72,marker:{{color:colors(d.open,d.close),opacity:.55}},name:'日成交量',yaxis:'y4',showlegend:false,customdata:d.date,hovertemplate:'%{{customdata}}<br>Vol=%{{y:,.0f}}<extra></extra>'}},
  {{type:'candlestick',x:q.x,open:q.open,high:q.high,low:q.low,close:q.close,name:'15分钟K',yaxis:'y5',showlegend:false,customdata:q.datetime.map((v,i)=>[v,q.source[i]]),hovertemplate:'%{{customdata[0]}} %{{customdata[1]}}<br>O=%{{open}} H=%{{high}}<br>L=%{{low}} C=%{{close}}<extra></extra>',increasing:{{line:{{color:'#d92d20'}}}},decreasing:{{line:{{color:'#039855'}}}}}},
  {{type:'scatter',mode:'lines',x:q.x,y:q.ma5,yaxis:'y5',name:'15m MA5',showlegend:false,line:{{color:'#f59e0b',width:1.2}}}},
  {{type:'scatter',mode:'lines',x:q.x,y:q.ma10,yaxis:'y5',name:'15m MA10',showlegend:false,line:{{color:'#2563eb',width:1.2}}}},
  {{type:'scatter',mode:'lines',x:q.x,y:q.ma20,yaxis:'y5',name:'15m MA20',showlegend:false,line:{{color:'#9333ea',width:1.2}}}},
  {{type:'scatter',mode:'lines',x:q.x,y:q.ma40,yaxis:'y5',name:'15m MA40',showlegend:false,line:{{color:'#111827',width:1.3}}}},
  {{type:'bar',x:q.x,y:q.volume,marker:{{color:colors(q.open,q.close),opacity:.6}},name:'15分钟成交量',yaxis:'y6',showlegend:false,customdata:q.datetime,hovertemplate:'%{{customdata}}<br>Vol=%{{y:,.0f}}<extra></extra>'}},
  {{type:'scatter',mode:'markers',x:[m.entry_x,m.exit_x],y:[m.entry_marker_price,m.exit_marker_price],yaxis:'y3',name:'同源成交价格（日）',marker:{{symbol:['triangle-up','triangle-down'],size:12,color:['#2563eb','#9333ea']}}}}
 ];
 const tickStep=Math.max(1,Math.ceil(d.date.length/18)),tickvals=d.x.filter((_,i)=>i%tickStep===0),ticktext=d.date.filter((_,i)=>i%tickStep===0);
 const switches=m.source_switch_x.map(x=>({{type:'line',xref:'x',yref:'paper',x0:x,x1:x,y0:0,y1:1,line:{{color:'#98a2b3',width:1,dash:'dash'}}}}));
 const layout={{title:{{text:`${{resultLabel}} #${{active+1}} ${{m.vt_symbol}} ${{m.direction}}｜${{m.entry_date}} → ${{m.exit_date}}｜R=${{rfmt(m.r_multiple)}}｜PnL=${{fmt(m.realized_pnl,0)}}｜${{m.selection_basis}}｜${{source}}`,x:.01}},
  margin:{{l:72,r:28,t:54,b:76}},paper_bgcolor:'#fff',plot_bgcolor:'#fff',hovermode:'x unified',showlegend:true,legend:{{orientation:'h',y:1.04,x:1,xanchor:'right'}},
  xaxis:{{range:[0,d.x.length],tickvals,ticktext,tickangle:-35,showgrid:false,rangeslider:{{visible:false}},title:'交易日（周/日/15分钟垂直对齐，可框选缩放）'}},
  yaxis:{{domain:[.83,1],title:'周K',showgrid:true,gridcolor:'#eef1f4'}},yaxis2:{{domain:[.75,.81],title:'周量',showgrid:true,gridcolor:'#f2f4f7'}},
  yaxis3:{{domain:[.48,.73],title:'日K',showgrid:true,gridcolor:'#eef1f4'}},yaxis4:{{domain:[.40,.46],title:'日量',showgrid:true,gridcolor:'#f2f4f7'}},
  yaxis5:{{domain:[.11,.38],title:'15分钟K',showgrid:true,gridcolor:'#eef1f4'}},yaxis6:{{domain:[0,.09],title:'15m量',showgrid:true,gridcolor:'#f2f4f7'}},
  shapes:[{{type:'rect',xref:'x',yref:'paper',x0:m.entry_x,x1:m.exit_x,y0:0,y1:1,fillcolor:'#fef3c7',opacity:.17,line:{{width:0}}}},{{type:'line',xref:'x',yref:'paper',x0:m.entry_x,x1:m.entry_x,y0:0,y1:1,line:{{color:'#2563eb',width:1.5,dash:'dot'}}}},{{type:'line',xref:'x',yref:'paper',x0:m.exit_x,x1:m.exit_x,y0:0,y1:1,line:{{color:'#9333ea',width:1.5,dash:'dot'}}}},...switches],
  annotations:[{{xref:'x',yref:'paper',x:m.entry_x,y:1,text:'开仓',showarrow:false,font:{{color:'#2563eb'}}}},{{xref:'x',yref:'paper',x:m.exit_x,y:1,text:'平仓',showarrow:false,font:{{color:'#9333ea'}}}}]}};
 Plotly.react('chart',traces,layout,{{responsive:true,displaylogo:false,scrollZoom:true}})
}}
resultEl.onchange=apply;sortEl.onchange=apply;yearEl.onchange=apply;productEl.onchange=apply;tradeEl.onchange=()=>{{active=Number(tradeEl.value);render()}};
document.getElementById('prev').onclick=()=>{{if(filtered.length){{active=(active-1+filtered.length)%filtered.length;render()}}}};
document.getElementById('next').onclick=()=>{{if(filtered.length){{active=(active+1)%filtered.length;render()}}}};
apply();
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build C9/15w historical big-winner weekly/daily/15m HTML atlas.")
    parser.add_argument("--end", default=_latest_completed_date().date().isoformat())
    parser.add_argument("--reuse-market", action="store_true", help="Reuse the already materialized 15m market file.")
    args = parser.parse_args()
    end = pd.Timestamp(args.end).normalize()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    started = time.time()
    combined, closed, frames, spec = _run_current_c9(end)
    selected = _selected_tail_episodes(closed)
    closed.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    selected[selected["result_type"].eq("profit")].to_csv(WINNERS_PATH, index=False, encoding="utf-8-sig")
    selected.to_csv(SELECTED_EPISODES_PATH, index=False, encoding="utf-8-sig")
    combined.to_csv(STRATEGY_DAILY_PATH, index=False, encoding="utf-8-sig")

    mapping = _main_mapping()
    bar_cache: dict[str, pd.DataFrame] = {}
    daily_by_episode: dict[str, pd.DataFrame] = {}
    intraday_dates_by_episode: dict[str, list[pd.Timestamp]] = {}
    for row in selected.itertuples(index=False):
        daily, intraday_dates = _context_daily(row, mapping, bar_cache)
        daily_by_episode[str(row.open_trade_id)] = daily
        intraday_dates_by_episode[str(row.open_trade_id)] = intraday_dates
    source_ranges: dict[str, list[pd.Timestamp]] = {}
    for row in selected.itertuples(index=False):
        daily = daily_by_episode[str(row.open_trade_id)].set_index("date")
        for trading_day in intraday_dates_by_episode[str(row.open_trade_id)]:
            source = str(daily.loc[trading_day, "source_vt_symbol"])
            source_ranges.setdefault(source, []).append(trading_day)
    fetch_rows: list[FetchStatus] = []
    if args.reuse_market and MINUTE_15M_PATH.exists():
        bars_15m = pd.read_csv(MINUTE_15M_PATH, encoding="utf-8-sig")
        bars_15m["bar_datetime"] = pd.to_datetime(bars_15m["bar_datetime"], errors="coerce")
        bars_15m = pd.concat(
            [
                _assign_trading_day(group.drop(columns=["trading_day"], errors="ignore"), _product_calendar(mapping, symbol))
                for symbol, group in bars_15m.groupby("vt_symbol", sort=False)
            ],
            ignore_index=True,
            sort=False,
        )
        supplemental_frames: list[pd.DataFrame] = []
        for vt_symbol, all_dates in sorted(source_ranges.items()):
            required = {pd.Timestamp(value).normalize() for value in all_dates}
            available = set(
                pd.to_datetime(
                    bars_15m.loc[bars_15m["vt_symbol"].eq(vt_symbol), "trading_day"],
                    errors="coerce",
                ).dropna().dt.normalize()
            )
            missing = sorted(required.difference(available))
            if not missing:
                continue
            frame, fetch_status = _fetch_15m(vt_symbol, min(missing), max(missing))
            frame = _assign_trading_day(frame, _product_calendar(mapping, vt_symbol))
            supplemental_frames.append(frame)
            fetch_rows.append(fetch_status)
            print(
                f"15m supplement {vt_symbol}: {len(frame)} rows for {len(missing)} missing days "
                f"in {fetch_status.elapsed_seconds:.3f}s",
                flush=True,
            )
        if supplemental_frames:
            bars_15m = (
                pd.concat([bars_15m, *supplemental_frames], ignore_index=True, sort=False)
                .drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
                .sort_values(["vt_symbol", "bar_datetime"])
                .reset_index(drop=True)
            )
            bars_15m.to_csv(MINUTE_15M_PATH, index=False, encoding="utf-8-sig")
    else:
        minute_frames: list[pd.DataFrame] = []
        for vt_symbol, all_dates in sorted(source_ranges.items()):
            daily = bar_cache[vt_symbol]
            start = min(all_dates)
            finish = max(all_dates)
            frame, fetch_status = _fetch_15m(vt_symbol, start, finish)
            frame = _assign_trading_day(frame, _product_calendar(mapping, vt_symbol))
            minute_frames.append(frame)
            fetch_rows.append(fetch_status)
            print(f"15m {vt_symbol}: {len(frame)} rows in {fetch_status.elapsed_seconds:.3f}s", flush=True)
        bars_15m = pd.concat(minute_frames, ignore_index=True, sort=False)
        bars_15m.to_csv(MINUTE_15M_PATH, index=False, encoding="utf-8-sig")
    records, manifest = _records(selected, daily_by_episode, intraday_dates_by_episode, bars_15m)
    missing_intraday_days = int(manifest["intraday_missing_days"].sum())
    if missing_intraday_days:
        missing_rows = manifest.loc[
            manifest["intraday_missing_days"].gt(0),
            ["result_type", "result_rank", "open_trade_id", "vt_symbol", "intraday_missing_days"],
        ].to_dict("records")
        raise RuntimeError(f"Selected profit/loss episodes have incomplete 15m coverage: {missing_rows}")
    manifest.to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")

    equity_column = "account_equity" if "account_equity" in combined.columns else "equity"
    metrics = s901.s650._metrics(combined, spec.capital, 1.0)
    summary = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "account_capital": OFFICIAL_LIVE_CAPITAL,
        "analysis_start": START.date().isoformat(),
        "requested_end": end.date().isoformat(),
        "effective_data_end": pd.to_datetime(combined["date"], errors="coerce").max().date().isoformat(),
        "closed_lots": int(len(closed)),
        "winner_lots": int(closed["winner"].sum()),
        "big_winner_lots": int(selected["result_type"].eq("profit").sum()),
        "big_winner_episodes": int(selected["result_type"].eq("profit").sum()),
        "big_loser_episodes": int(selected["result_type"].eq("loss").sum()),
        "selected_episode_closed_lots": int(pd.to_numeric(selected["lot_count"], errors="coerce").sum()),
        "episode_closed_lots": int(pd.to_numeric(selected.loc[selected["result_type"].eq("profit"), "lot_count"], errors="coerce").sum()),
        "big_winner_threshold_r": float(selected["profit_r_threshold"].iloc[0]),
        "big_loser_threshold_r": float(selected["loss_r_threshold"].iloc[0]),
        "unique_contracts": int(selected["vt_symbol"].nunique()),
        "bars_15m": int(len(bars_15m)),
        "intraday_missing_days": int(manifest["intraday_missing_days"].sum()),
        "context_fallback_days": int(manifest["context_fallback_days"].sum()),
        "winner_selection": "Profit episodes selected by top-20% R, plus top-20% realized profit when R is unavailable.",
        "loser_selection": "Loss episodes selected by bottom-20% R, plus bottom-20% realized loss when R is unavailable.",
        "end_equity": float(pd.to_numeric(combined[equity_column], errors="coerce").dropna().iloc[-1])
        if equity_column in combined.columns and combined[equity_column].notna().any()
        else None,
        "backtest_metrics": _json_safe(metrics),
        "strategy_profile": str(spec.profile),
        "fetch_status": [asdict(item) for item in fetch_rows],
        "elapsed_seconds": round(time.time() - started, 3),
        "artifacts": {
            "html": str(HTML_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "big_winners": str(WINNERS_PATH),
            "selected_episodes": str(SELECTED_EPISODES_PATH),
            "bars_15m": str(MINUTE_15M_PATH),
            "strategy_daily": str(STRATEGY_DAILY_PATH),
            "manifest": str(MANIFEST_PATH),
        },
        "anti_overfit_note": "Visualization only. Winner-only inspection is hypothesis generation, not rule validation.",
    }
    HTML_PATH.write_text(_html(records, summary), encoding="utf-8")
    summary["artifact_sha256"] = {
        "html": _sha256(HTML_PATH),
        "closed_lots": _sha256(CLOSED_LOTS_PATH),
        "big_winners": _sha256(WINNERS_PATH),
        "selected_episodes": _sha256(SELECTED_EPISODES_PATH),
        "bars_15m": _sha256(MINUTE_15M_PATH),
        "strategy_daily": _sha256(STRATEGY_DAILY_PATH),
        "manifest": _sha256(MANIFEST_PATH),
    }
    SUMMARY_PATH.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ["closed_lots", "winner_lots", "big_winner_episodes", "big_loser_episodes", "big_winner_threshold_r", "big_loser_threshold_r", "bars_15m", "intraday_missing_days", "elapsed_seconds"]}, ensure_ascii=False, indent=2))
    print(HTML_PATH)


if __name__ == "__main__":
    main()

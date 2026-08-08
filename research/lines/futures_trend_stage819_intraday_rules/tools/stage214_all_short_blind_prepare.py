"""Prepare frozen all-short pre-entry data for the Stage214 blind validation."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_EVENT_COUNT = 309
EXPECTED_SHORT_EVENT_COUNT = 64
EXPECTED_ZERO_RISK_OPEN_TRADE_IDS = frozenset(
    {"BACKTESTING.166", "BACKTESTING.265", "BACKTESTING.589"}
)

_STAGE208_PATH = Path(__file__).with_name("stage208_c9_2r_winner_15m_atlas.py")
_STAGE208_SPEC = importlib.util.spec_from_file_location("stage208", _STAGE208_PATH)
assert _STAGE208_SPEC and _STAGE208_SPEC.loader
_stage208 = importlib.util.module_from_spec(_STAGE208_SPEC)
_STAGE208_SPEC.loader.exec_module(_stage208)

build_trading_calendar = _stage208.build_trading_calendar
assign_trading_day = _stage208.assign_trading_day
resample_15m = _stage208.resample_15m
discover_contract_cache_paths = _stage208.discover_contract_cache_paths


def build_short_events(
    closed_lots: pd.DataFrame,
    enforce_expected_counts: bool = True,
) -> pd.DataFrame:
    """Freeze the 2020-start monthly-contract short entries without dropping zero risk."""
    frame = closed_lots[
        closed_lots["requested_start_month"].astype(str).eq("2020-01")
    ].copy()
    frame["direction"] = frame["direction"].astype(str).str.strip().str.lower()
    for column in ["realized_pnl", "risk_amount", "entry_price"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["entry_date", "exit_date"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()

    all_events = (
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
    if enforce_expected_counts and len(all_events) != EXPECTED_EVENT_COUNT:
        raise RuntimeError(f"expected {EXPECTED_EVENT_COUNT} events, got {len(all_events)}")

    events = all_events[all_events["direction"].eq("short")].copy()
    if enforce_expected_counts and len(events) != EXPECTED_SHORT_EVENT_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_SHORT_EVENT_COUNT} short events, got {len(events)}"
        )

    events["aggregate_r"] = events["realized_pnl"] / events["risk_amount"].replace(
        0.0, np.nan
    )
    if enforce_expected_counts:
        zero_risk_ids = frozenset(
            events.loc[events["risk_amount"].eq(0.0), "open_trade_id"].astype(str)
        )
        if zero_risk_ids != EXPECTED_ZERO_RISK_OPEN_TRADE_IDS:
            raise RuntimeError(
                "expected zero-risk open_trade_ids "
                f"{sorted(EXPECTED_ZERO_RISK_OPEN_TRADE_IDS)}, got {sorted(zero_risk_ids)}"
            )
    events["outcome_ge_2r"] = events["aggregate_r"].ge(2.0)
    events["outcome_profitable"] = events["realized_pnl"].gt(0.0)
    events["entry_year"] = events["entry_date"].dt.year.astype("Int64")
    return events.sort_values(["entry_date", "open_trade_id"]).reset_index(drop=True)


def select_preentry_days(
    entry_day: pd.Timestamp,
    calendar: pd.DatetimeIndex,
) -> list[pd.Timestamp]:
    """Return exactly the five official trading days before an entry day."""
    normalized_calendar = pd.DatetimeIndex(calendar).normalize().sort_values().unique()
    normalized_entry = pd.Timestamp(entry_day).normalize()
    positions = np.flatnonzero(normalized_calendar == normalized_entry)
    if len(positions) != 1:
        raise RuntimeError(
            f"entry day not uniquely present in calendar: {normalized_entry.date()}"
        )
    position = int(positions[0])
    if position < 5:
        raise RuntimeError(
            f"entry day has fewer than five preceding trading days: {normalized_entry.date()}"
        )
    return list(normalized_calendar[position - 5 : position])


_MINUTE_COLUMNS = [
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
_MANIFEST_COLUMNS = [
    "vt_symbol",
    "source",
    "path",
    "row_count",
    "min_datetime",
    "max_datetime",
    "sha256",
    "result_status",
    "query_start",
    "query_end",
    "query_descriptor",
]


def _target_days_by_symbol(
    events: pd.DataFrame,
    calendar: pd.DatetimeIndex,
) -> dict[str, set[pd.Timestamp]]:
    target_days: dict[str, set[pd.Timestamp]] = {}
    for event in events.itertuples(index=False):
        symbol = str(event.vt_symbol)
        target_days.setdefault(symbol, set()).update(
            select_preentry_days(pd.Timestamp(event.entry_date), calendar)
        )
    return target_days


def _canonicalize_minutes(
    frame: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    target_days: dict[str, set[pd.Timestamp]],
) -> pd.DataFrame:
    result = frame.copy()
    for column in _MINUTE_COLUMNS:
        if column not in result.columns:
            result[column] = np.nan
    result = result[_MINUTE_COLUMNS]
    result["bar_datetime"] = pd.to_datetime(result["bar_datetime"], errors="coerce")
    for column in _MINUTE_COLUMNS[2:]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result[result["vt_symbol"].astype(str).isin(target_days)].copy()
    if result.empty:
        return result.assign(trading_day=pd.Series(dtype="datetime64[ns]"))
    result["vt_symbol"] = result["vt_symbol"].astype(str)
    result = assign_trading_day(result, calendar)
    keep = pd.Series(False, index=result.index)
    for vt_symbol, days in target_days.items():
        keep |= result["vt_symbol"].eq(vt_symbol) & result["trading_day"].isin(days)
    return result.loc[keep].reset_index(drop=True)


def _stable_frame_sha256(frame: pd.DataFrame) -> str:
    canonical = frame.copy().sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)
    canonical["bar_datetime"] = pd.to_datetime(
        canonical["bar_datetime"], errors="coerce"
    ).dt.strftime("%Y-%m-%dT%H:%M:%S")
    payload = canonical.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.10g",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _manifest_rows(
    frame: pd.DataFrame,
    *,
    target_symbols: list[str],
    source: str,
    path: str,
    sha256: str,
    result_status: str,
    query_start: pd.Timestamp | None = None,
    query_end: pd.Timestamp | None = None,
    query_descriptor: str = "",
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for vt_symbol in sorted(target_symbols):
        symbol_rows = frame[frame["vt_symbol"].eq(vt_symbol)]
        datetimes = pd.to_datetime(symbol_rows["bar_datetime"], errors="coerce")
        rows.append(
            {
                "vt_symbol": str(vt_symbol),
                "source": source,
                "path": path,
                "row_count": int(len(symbol_rows)),
                "min_datetime": datetimes.min().isoformat() if not datetimes.empty else "",
                "max_datetime": datetimes.max().isoformat() if not datetimes.empty else "",
                "sha256": sha256,
                "result_status": result_status if symbol_rows.empty else "selected",
                "query_start": "" if query_start is None else query_start.isoformat(),
                "query_end": "" if query_end is None else query_end.isoformat(),
                "query_descriptor": query_descriptor,
            }
        )
    return rows


def _database_query_window(
    entry_day: pd.Timestamp,
    calendar: pd.DatetimeIndex,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Build [previous-official-night, entry-day-00:00) for one frozen event."""
    preentry_days = select_preentry_days(entry_day, calendar)
    normalized_calendar = pd.DatetimeIndex(calendar).normalize().sort_values().unique()
    first_position = int(np.flatnonzero(normalized_calendar == preentry_days[0])[0])
    if first_position == 0:
        raise RuntimeError(
            "no previous official trading day for pre-entry night window: "
            f"{preentry_days[0].date()}"
        )
    query_start = normalized_calendar[first_position - 1] + pd.Timedelta(hours=20)
    query_end = pd.Timestamp(entry_day).normalize()
    return query_start, query_end


def _database_bars_to_frame(vt_symbol: str, bars: list[object]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for bar in bars:
        bar_datetime = pd.Timestamp(bar.datetime)
        if bar_datetime.tzinfo is not None:
            bar_datetime = bar_datetime.tz_convert("Asia/Shanghai").tz_localize(None)
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "bar_datetime": bar_datetime,
                "open": float(bar.open_price),
                "high": float(bar.high_price),
                "low": float(bar.low_price),
                "close": float(bar.close_price),
                "volume": float(bar.volume),
                "open_oi": float(bar.open_interest),
                "close_oi": float(bar.open_interest),
            }
        )
    return pd.DataFrame(rows, columns=_MINUTE_COLUMNS)


def merge_minute_sources(
    events: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    stage861_path: Path,
    cache_paths: list[Path],
    database: object,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge exact-contract minute sources with Stage861 as the authoritative duplicate."""
    from vnpy.trader.constant import Exchange, Interval

    target_days = _target_days_by_symbol(events, calendar)
    target_symbols = sorted(target_days)
    selected: list[pd.DataFrame] = []
    manifest: list[dict[str, object]] = []

    file_sources = [(Path(stage861_path), "stage861", 3)] + [
        (Path(path), "local_cache", 2) for path in cache_paths
    ]
    for path, source, priority in file_sources:
        exists = path.exists()
        raw = (
            pd.read_csv(path, usecols=lambda column: column in _MINUTE_COLUMNS)
            if exists
            else pd.DataFrame(columns=_MINUTE_COLUMNS)
        )
        frame = _canonicalize_minutes(raw, calendar, target_days)
        manifest.extend(
            _manifest_rows(
                frame,
                target_symbols=target_symbols,
                source=source,
                path=str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest() if exists else "",
                result_status=(
                    "attempted_no_target_rows" if exists else "source_unavailable"
                ),
            )
        )
        if frame.empty:
            continue
        frame["minute_source_kind"] = source
        frame["minute_source_path"] = str(path)
        frame["source_priority"] = priority
        selected.append(frame)

    for event in events.itertuples(index=False):
        vt_symbol = str(event.vt_symbol)
        if vt_symbol.count(".") != 1:
            raise ValueError(f"invalid exact vt_symbol: {vt_symbol}")
        symbol, exchange_code = vt_symbol.split(".", 1)
        start, end = _database_query_window(pd.Timestamp(event.entry_date), calendar)
        bars = database.load_bar_data(
            symbol,
            Exchange(exchange_code),
            Interval.MINUTE,
            start.to_pydatetime(),
            end.to_pydatetime(),
        )
        raw_frame = _database_bars_to_frame(vt_symbol, list(bars))
        frame = _canonicalize_minutes(
            raw_frame, calendar, target_days
        )
        source_path = f"vnpy_database://{vt_symbol}"
        descriptor = (
            "exact_contract_minute:"
            f"symbol={symbol};exchange={exchange_code};interval=1m"
        )
        manifest.extend(
            _manifest_rows(
                frame,
                target_symbols=[vt_symbol],
                source="vnpy_database",
                path=source_path,
                sha256=_stable_frame_sha256(raw_frame),
                result_status="attempted_no_target_rows",
                query_start=start,
                query_end=end,
                query_descriptor=descriptor,
            )
        )
        if frame.empty:
            continue
        frame["minute_source_kind"] = "vnpy_database"
        frame["minute_source_path"] = source_path
        frame["source_priority"] = 1
        selected.append(frame)

    columns = [
        *_MINUTE_COLUMNS,
        "trading_day",
        "minute_source_kind",
        "minute_source_path",
        "source_priority",
    ]
    sources = pd.DataFrame(manifest, columns=_MANIFEST_COLUMNS)
    if not selected:
        minutes = pd.DataFrame(columns=columns)
        minutes.attrs["source_manifest"] = sources
        return minutes, sources
    minutes = (
        pd.concat(selected, ignore_index=True)
        .sort_values(["vt_symbol", "bar_datetime", "source_priority"], ascending=[True, True, False])
        .drop_duplicates(["vt_symbol", "bar_datetime"], keep="first")
        .sort_values(["vt_symbol", "bar_datetime"])
        .reset_index(drop=True)
    )
    minutes = minutes[columns]
    minutes.attrs["source_manifest"] = sources
    return minutes, sources


def resolve_risk_zero_events(
    events: pd.DataFrame,
    closed_lots: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mark zero frozen risk as unresolved without inferring it from realized PnL."""
    del closed_lots  # No closed-lot PnL transformation can reconstruct a missing risk basis.
    resolved = events.copy()
    risk_amount = pd.to_numeric(resolved["risk_amount"], errors="coerce")
    resolved["risk_status"] = np.where(
        risk_amount.gt(0.0), "resolved", "unresolved"
    )
    if "aggregate_r" not in resolved.columns:
        resolved["aggregate_r"] = np.nan
    resolved.loc[resolved["risk_status"].eq("unresolved"), "aggregate_r"] = np.nan
    audit_columns = [
        column
        for column in [
            "open_trade_id",
            "vt_symbol",
            "entry_date",
            "realized_pnl",
            "risk_amount",
            "aggregate_r",
            "risk_status",
        ]
        if column in resolved.columns
    ]
    risk_audit = resolved.loc[
        resolved["risk_status"].eq("unresolved"), audit_columns
    ].copy()
    risk_audit["resolution_method"] = "unresolved_no_frozen_risk_basis"
    return resolved, risk_audit.reset_index(drop=True)


def build_data_gap_audit(
    events: pd.DataFrame,
    minutes: pd.DataFrame,
    calendar: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Audit each frozen event's five pre-entry trading days and risk provenance."""
    source_manifest = minutes.attrs.get("source_manifest")
    minute_frame = minutes.copy()
    if "trading_day" not in minute_frame.columns:
        minute_frame["trading_day"] = pd.NaT
    minute_frame["trading_day"] = pd.to_datetime(
        minute_frame["trading_day"], errors="coerce"
    ).dt.normalize()
    rows: list[dict[str, object]] = []
    for event in events.itertuples(index=False):
        event_data = event._asdict()
        vt_symbol = str(event_data["vt_symbol"])
        target_days = select_preentry_days(pd.Timestamp(event_data["entry_date"]), calendar)
        event_minutes = minute_frame[
            minute_frame["vt_symbol"].astype(str).eq(vt_symbol)
            & minute_frame["trading_day"].isin(target_days)
        ]
        actual_days = sorted(
            pd.DatetimeIndex(event_minutes["trading_day"].dropna().unique()).normalize()
        )
        missing_days = [day for day in target_days if day not in actual_days]
        if len(actual_days) == len(target_days):
            coverage_state = "complete"
        elif actual_days:
            coverage_state = "partial"
        else:
            coverage_state = "missing"
        source_column = "minute_source_kind"
        attempted_sources: list[str] = []
        if isinstance(source_manifest, pd.DataFrame):
            attempted_sources = source_manifest.loc[
                source_manifest["vt_symbol"].astype(str).eq(vt_symbol), "source"
            ].dropna().astype(str).unique().tolist()
        if not attempted_sources and source_column in event_minutes.columns:
            attempted_sources = event_minutes[source_column].dropna().astype(str).unique().tolist()
        source_order = {"stage861": 0, "local_cache": 1, "vnpy_database": 2}
        attempted_sources = sorted(
            attempted_sources,
            key=lambda source: (source_order.get(source, len(source_order)), source),
        )
        risk_status = event_data.get("risk_status")
        if risk_status is None:
            risk_status = (
                "resolved"
                if pd.to_numeric(event_data.get("risk_amount"), errors="coerce") > 0.0
                else "unresolved"
            )
        rows.append(
            {
                "open_trade_id": event_data.get("open_trade_id"),
                "vt_symbol": vt_symbol,
                "entry_date": pd.Timestamp(event_data["entry_date"]).date().isoformat(),
                "target_days": "|".join(day.date().isoformat() for day in target_days),
                "actual_days": "|".join(day.date().isoformat() for day in actual_days),
                "missing_days": "|".join(day.date().isoformat() for day in missing_days),
                "coverage_state": coverage_state,
                "attempted_sources": "|".join(attempted_sources),
                "risk_status": risk_status,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "open_trade_id",
            "vt_symbol",
            "entry_date",
            "target_days",
            "actual_days",
            "missing_days",
            "coverage_state",
            "attempted_sources",
            "risk_status",
        ],
    )


def build_preentry_15m(
    minutes: pd.DataFrame,
    events: pd.DataFrame,
    calendar: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Produce sparse Stage208-compatible 15-minute bars for the frozen pre-entry days."""
    target_days = _target_days_by_symbol(events, calendar)
    frame = minutes.copy()
    frame["trading_day"] = pd.to_datetime(
        frame["trading_day"], errors="coerce"
    ).dt.normalize()
    keep = pd.Series(False, index=frame.index)
    for vt_symbol, days in target_days.items():
        keep |= frame["vt_symbol"].astype(str).eq(vt_symbol) & frame["trading_day"].isin(days)
    return resample_15m(frame.loc[keep].copy())

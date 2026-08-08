"""Prepare frozen all-short pre-entry data for the Stage214 blind validation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
from PIL import Image


EXPECTED_EVENT_COUNT = 309
EXPECTED_SHORT_EVENT_COUNT = 64
EXPECTED_ZERO_RISK_OPEN_TRADE_IDS = frozenset(
    {"BACKTESTING.166", "BACKTESTING.265", "BACKTESTING.589"}
)
MIN_QUALITY_DAY_BARS = 30
MIN_REFERENCE_BAR_RATIO = 0.80
SESSION_BOUNDARY_TOLERANCE_MINUTES = 15

_STAGE208_PATH = Path(__file__).with_name("stage208_c9_2r_winner_15m_atlas.py")
_STAGE208_SPEC = importlib.util.spec_from_file_location("stage208", _STAGE208_PATH)
assert _STAGE208_SPEC and _STAGE208_SPEC.loader
_stage208 = importlib.util.module_from_spec(_STAGE208_SPEC)
_STAGE208_SPEC.loader.exec_module(_stage208)

build_trading_calendar = _stage208.build_trading_calendar
assign_trading_day = _stage208.assign_trading_day
resample_15m = _stage208.resample_15m
discover_contract_cache_paths = _stage208.discover_contract_cache_paths

REPO_ROOT = Path(__file__).resolve().parents[4]
LINE_ROOT = REPO_ROOT / "research/lines/futures_trend_stage819_intraday_rules"
OUTPUT_DIR = LINE_ROOT / "outputs/stage214_all_short_preentry_blind_validation"
CLOSED_LOTS_PATH = _stage208.CLOSED_LOTS_PATH
CURVES_PATH = _stage208.CURVES_PATH
MINUTE_PATH = _stage208.MINUTE_PATH
MINUTE_CACHE_ROOT = _stage208.MINUTE_CACHE_ROOT
BLIND_MAPPING_SEED = 21420260808
CALIBRATION_CASE_COUNT = 12
REVIEWER_MANIFEST_COLUMNS = [
    "case_id",
    "chart_file",
    "available_day_count",
    "bar_count",
]
_ALLOWED_PNG_TEXT = {"Software": "stage214_blind_chart"}
_OUTCOME_TOKEN = re.compile(
    r"\b(?:winner|loser|outcome|aggregate[_ ]?r|realized[_ ]?pnl|"
    r"risk[_ ]?amount|return|profit|loss|r_multiple|\d+(?:\.\d+)?r)\b",
    flags=re.IGNORECASE,
)
_DATE_TOKEN = re.compile(r"\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b")
_CONTRACT_TOKEN = re.compile(r"\b[a-z]{1,4}\d{3,4}\.[a-z]{2,6}\b", re.IGNORECASE)


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
    resolved_r = pd.to_numeric(events["aggregate_r"], errors="coerce")
    valid_r = pd.Series(np.isfinite(resolved_r), index=events.index)
    events["outcome_ge_2r"] = pd.Series(pd.NA, index=events.index, dtype="boolean")
    events["outcome_profitable"] = pd.Series(pd.NA, index=events.index, dtype="boolean")
    events.loc[valid_r, "outcome_ge_2r"] = resolved_r.loc[valid_r].ge(2.0)
    events.loc[valid_r, "outcome_profitable"] = events.loc[valid_r, "realized_pnl"].gt(0.0)
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
    *,
    authorized_cache_paths: list[Path] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge exact-contract minutes with qualified completed days dominant as a whole."""
    from vnpy.trader.constant import Exchange, Interval

    target_days = _target_days_by_symbol(events, calendar)
    target_symbols = sorted(target_days)
    selected: list[pd.DataFrame] = []
    manifest: list[dict[str, object]] = []

    authorized_cache_paths = authorized_cache_paths or []
    file_sources = [
        (Path(path), "authorized_tqsdk_completed", 4)
        for path in authorized_cache_paths
    ] + [(Path(stage861_path), "stage861", 3)] + [
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
    combined = pd.concat(selected, ignore_index=True)
    authorized = combined[
        combined["minute_source_kind"].eq("authorized_tqsdk_completed")
    ].copy()
    if not authorized.empty:
        authorized_quality = build_minute_day_quality(authorized)
        dominant_days = {
            (str(row.vt_symbol), pd.Timestamp(row.trading_day).normalize())
            for row in authorized_quality.itertuples(index=False)
            if bool(row.quality_passed)
        }
        if dominant_days:
            on_dominant_day = pd.Series(
                [
                    (str(vt_symbol), pd.Timestamp(trading_day).normalize())
                    in dominant_days
                    for vt_symbol, trading_day in zip(
                        combined["vt_symbol"], combined["trading_day"]
                    )
                ],
                index=combined.index,
            )
            combined = combined[
                ~on_dominant_day
                | combined["minute_source_kind"].eq("authorized_tqsdk_completed")
            ].copy()
    minutes = (
        combined
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


def build_minute_day_quality(minutes: pd.DataFrame) -> pd.DataFrame:
    """Validate completed exact-contract minute sessions before coverage credit."""
    columns = [
        "vt_symbol",
        "trading_day",
        "row_count",
        "unique_timestamp_count",
        "has_day_session",
        "has_night_session",
        "min_datetime",
        "max_datetime",
        "has_session_end_1459",
        "reference_bar_count",
        "expected_night_session",
        "authoritative_completed_source",
        "quality_passed",
        "failure_reasons",
    ]
    if minutes.empty:
        return pd.DataFrame(columns=columns)
    frame = minutes.copy()
    frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce")
    frame["trading_day"] = pd.to_datetime(frame["trading_day"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["vt_symbol", "bar_datetime", "trading_day"])
    if frame.empty:
        return pd.DataFrame(columns=columns)
    for column in ["open", "high", "low", "close", "volume"]:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    metrics: list[dict[str, object]] = []
    for (vt_symbol, trading_day), group in frame.groupby(
        ["vt_symbol", "trading_day"], sort=True
    ):
        ordered = group.sort_values("bar_datetime")
        ohlc = ordered[["open", "high", "low", "close"]]
        valid_ohlc = bool(
            ohlc.notna().all().all()
            and ordered["high"].ge(ohlc[["open", "close", "low"]].max(axis=1)).all()
            and ordered["low"].le(ohlc[["open", "close", "high"]].min(axis=1)).all()
        )
        flat_rows = ohlc.nunique(axis=1, dropna=False).eq(1)
        zero_volume = ordered["volume"].fillna(0.0).eq(0.0)
        times = ordered["bar_datetime"]
        minute_of_day = times.dt.hour * 60 + times.dt.minute
        has_day = bool(minute_of_day.between(8 * 60, 18 * 60 - 1).any())
        has_night = bool(((minute_of_day >= 18 * 60) | (minute_of_day < 8 * 60)).any())
        has_session_end_1459 = bool(minute_of_day.eq(14 * 60 + 59).any())
        source_kind = ordered.get(
            "minute_source_kind", pd.Series("", index=ordered.index, dtype="object")
        ).astype(str)
        authoritative_completed = bool(
            not source_kind.empty
            and source_kind.eq("authorized_tqsdk_completed").all()
        )
        offsets = (times - pd.Timestamp(trading_day)).dt.total_seconds() / 60.0
        row_count = int(len(ordered))
        unique_count = int(times.nunique())
        all_flat_zero = bool(flat_rows.all() and zero_volume.all())
        basic_trusted = bool(
            row_count >= MIN_QUALITY_DAY_BARS
            and unique_count == row_count
            and valid_ohlc
            and not all_flat_zero
            and has_day
        )
        metrics.append(
            {
                "vt_symbol": str(vt_symbol),
                "trading_day": pd.Timestamp(trading_day),
                "row_count": row_count,
                "unique_timestamp_count": unique_count,
                "has_day_session": has_day,
                "has_night_session": has_night,
                "min_datetime": times.min(),
                "max_datetime": times.max(),
                "has_session_end_1459": has_session_end_1459,
                "min_offset_minutes": float(offsets.min()),
                "max_offset_minutes": float(offsets.max()),
                "valid_ohlc": valid_ohlc,
                "all_flat_zero": all_flat_zero,
                "basic_trusted": basic_trusted,
                "authoritative_completed_source": authoritative_completed,
            }
        )
    quality = pd.DataFrame(metrics)
    output_rows: list[dict[str, object]] = []
    for vt_symbol, symbol_days in quality.groupby("vt_symbol", sort=False):
        trusted = symbol_days[symbol_days["basic_trusted"]].copy()
        expected_night = bool(trusted["has_night_session"].mean() >= 0.5) if not trusted.empty else False
        reference = trusted[
            trusted["has_day_session"]
            & trusted["has_night_session"].eq(expected_night)
        ]
        if reference.empty:
            reference = trusted
        reference_count = float(reference["row_count"].median()) if not reference.empty else np.nan
        reference_start = float(reference["min_offset_minutes"].median()) if not reference.empty else np.nan
        reference_end = float(reference["max_offset_minutes"].median()) if not reference.empty else np.nan
        for row in symbol_days.itertuples(index=False):
            reasons: list[str] = []
            authoritative_no_night = bool(
                row.authoritative_completed_source
                and row.basic_trusted
                and not row.has_night_session
            )
            if row.unique_timestamp_count != row.row_count:
                reasons.append("duplicate_timestamps")
            if not row.valid_ohlc:
                reasons.append("invalid_ohlc")
            if row.all_flat_zero:
                reasons.append("all_ohlc_flat_and_zero_volume")
            if row.row_count < MIN_QUALITY_DAY_BARS:
                reasons.append("insufficient_bar_count")
            if not row.has_day_session:
                reasons.append("missing_day_session")
            if row.authoritative_completed_source and not row.has_session_end_1459:
                reasons.append("missing_session_end_1459")
            if expected_night and not row.has_night_session and not authoritative_no_night:
                reasons.append("missing_night_session")
            if np.isfinite(reference_count):
                minimum_count = int(np.ceil(reference_count * MIN_REFERENCE_BAR_RATIO))
                if row.row_count < minimum_count and not authoritative_no_night:
                    reasons.append("insufficient_relative_bar_count")
            if (
                np.isfinite(reference_start)
                and row.min_offset_minutes > reference_start + SESSION_BOUNDARY_TOLERANCE_MINUTES
                and not authoritative_no_night
            ):
                reasons.append("session_start_too_late")
            if np.isfinite(reference_end) and row.max_offset_minutes < reference_end - SESSION_BOUNDARY_TOLERANCE_MINUTES:
                reasons.append("session_end_too_early")
            output_rows.append(
                {
                    "vt_symbol": str(vt_symbol),
                    "trading_day": pd.Timestamp(row.trading_day),
                    "row_count": int(row.row_count),
                    "unique_timestamp_count": int(row.unique_timestamp_count),
                    "has_day_session": bool(row.has_day_session),
                    "has_night_session": bool(row.has_night_session),
                    "min_datetime": pd.Timestamp(row.min_datetime).isoformat(),
                    "max_datetime": pd.Timestamp(row.max_datetime).isoformat(),
                    "has_session_end_1459": bool(row.has_session_end_1459),
                    "reference_bar_count": reference_count,
                    "expected_night_session": expected_night,
                    "authoritative_completed_source": bool(row.authoritative_completed_source),
                    "quality_passed": not reasons,
                    "failure_reasons": "|".join(reasons),
                }
            )
    return pd.DataFrame(output_rows, columns=columns)


def build_data_gap_audit(
    events: pd.DataFrame,
    minutes: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    day_quality: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Audit each frozen event's five pre-entry trading days and risk provenance."""
    source_manifest = minutes.attrs.get("source_manifest")
    minute_frame = minutes.copy()
    if "trading_day" not in minute_frame.columns:
        minute_frame["trading_day"] = pd.NaT
    minute_frame["trading_day"] = pd.to_datetime(
        minute_frame["trading_day"], errors="coerce"
    ).dt.normalize()
    if day_quality is None:
        day_quality = build_minute_day_quality(minute_frame)
    quality_frame = day_quality.copy()
    if not quality_frame.empty:
        quality_frame["trading_day"] = pd.to_datetime(
            quality_frame["trading_day"], errors="coerce"
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
        observed_days = sorted(
            pd.DatetimeIndex(event_minutes["trading_day"].dropna().unique()).normalize()
        )
        event_quality = quality_frame[
            quality_frame["vt_symbol"].astype(str).eq(vt_symbol)
            & quality_frame["trading_day"].isin(target_days)
        ]
        passed_days = sorted(
            pd.DatetimeIndex(
                event_quality.loc[event_quality["quality_passed"].astype(bool), "trading_day"].unique()
            ).normalize()
        )
        missing_days = [day for day in target_days if day not in passed_days]
        failure_details: list[str] = []
        for day in missing_days:
            day_rows = event_quality[event_quality["trading_day"].eq(day)]
            reason = (
                str(day_rows.iloc[0]["failure_reasons"])
                if not day_rows.empty and str(day_rows.iloc[0]["failure_reasons"])
                else "no_minute_rows"
            )
            failure_details.append(f"{day.date().isoformat()}:{reason}")
        if len(passed_days) == len(target_days):
            coverage_state = "complete"
        elif observed_days:
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
                "actual_days": "|".join(day.date().isoformat() for day in passed_days),
                "observed_days": "|".join(day.date().isoformat() for day in observed_days),
                "missing_days": "|".join(day.date().isoformat() for day in missing_days),
                "failure_reasons": ";".join(failure_details),
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
            "observed_days",
            "missing_days",
            "failure_reasons",
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


def build_blind_mapping(
    events: pd.DataFrame,
    seed: int = BLIND_MAPPING_SEED,
) -> pd.DataFrame:
    """Assign reproducible anonymous case IDs after an identity-only stable ordering."""
    if "open_trade_id" not in events.columns:
        raise ValueError("events missing open_trade_id")
    mapping = events.copy()
    mapping["open_trade_id"] = mapping["open_trade_id"].astype(str)
    if mapping["open_trade_id"].duplicated().any():
        raise ValueError("open_trade_id must be unique for blind mapping")
    mapping = mapping.sort_values("open_trade_id", kind="mergesort").reset_index(drop=True)
    indices = list(range(len(mapping)))
    random.Random(seed).shuffle(indices)
    case_ids = [""] * len(mapping)
    for case_number, source_index in enumerate(indices, start=1):
        case_ids[source_index] = f"CASE-{case_number:03d}"
    mapping.insert(0, "case_id", case_ids)
    return mapping


def build_calibration_cases(
    reviewer_manifest: pd.DataFrame,
    seed: int = BLIND_MAPPING_SEED,
) -> pd.DataFrame:
    """Select the frozen reviewer-only calibration cases without identity data."""
    if "case_id" not in reviewer_manifest.columns:
        raise ValueError("reviewer manifest missing case_id")
    case_ids = reviewer_manifest["case_id"].astype(str)
    if not case_ids.map(lambda value: bool(re.fullmatch(r"CASE-\d{3}", value))).all():
        raise ValueError("calibration case IDs must be canonical")
    if case_ids.duplicated().any():
        raise ValueError("calibration case IDs must be unique")
    if len(case_ids) < CALIBRATION_CASE_COUNT:
        raise ValueError(
            f"calibration requires at least {CALIBRATION_CASE_COUNT} reviewer cases"
        )
    candidates = sorted(case_ids.tolist())
    random.Random(seed).shuffle(candidates)
    return pd.DataFrame(
        {"case_id": candidates[:CALIBRATION_CASE_COUNT]},
        columns=["case_id"],
    )


def normalize_preentry_bars(bars15: pd.DataFrame) -> pd.DataFrame:
    """Scale every OHLC field to the first displayed close equal to 100."""
    required_columns = ["open", "high", "low", "close"]
    missing_columns = [column for column in required_columns if column not in bars15.columns]
    if missing_columns:
        raise ValueError(f"bars15 missing OHLC columns: {missing_columns}")
    normalized = bars15.copy().reset_index(drop=True)
    for column in required_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=required_columns).reset_index(drop=True)
    if normalized.empty:
        raise ValueError("cannot normalize empty OHLC bars")
    first_close = float(normalized.loc[0, "close"])
    if not np.isfinite(first_close) or first_close <= 0.0:
        raise ValueError("first displayed close must be finite and positive")
    scale = 100.0 / first_close
    normalized.loc[:, required_columns] = normalized[required_columns] * scale
    return normalized


def render_blind_chart(
    case_id: str,
    bars15: pd.DataFrame,
    target_days: list[pd.Timestamp],
    output_path: Path,
) -> dict[str, object]:
    """Render a no-volume, date-free, pre-entry-only normalized OHLC chart."""
    if not re.fullmatch(r"CASE-\d{3}", str(case_id)):
        raise ValueError(f"invalid blind case ID: {case_id}")
    if "trading_day" not in bars15.columns:
        raise ValueError("bars15 missing trading_day")
    time_column = "bar_15m" if "bar_15m" in bars15.columns else "bar_datetime"
    if time_column not in bars15.columns:
        raise ValueError("bars15 missing bar_15m or bar_datetime")

    normalized_target_days = pd.DatetimeIndex(target_days).normalize()
    if (
        len(normalized_target_days) != 5
        or normalized_target_days.hasnans
        or not normalized_target_days.is_unique
        or not normalized_target_days.is_monotonic_increasing
    ):
        raise ValueError("target_days must contain exactly five unique increasing days")
    frame = bars15.copy()
    frame["trading_day"] = pd.to_datetime(frame["trading_day"], errors="coerce").dt.normalize()
    frame[time_column] = pd.to_datetime(frame[time_column], errors="coerce")
    frame = frame[frame["trading_day"].isin(normalized_target_days)].copy()
    frame = frame.sort_values(["trading_day", time_column]).reset_index(drop=True)
    frame = normalize_preentry_bars(frame)
    if frame.empty:
        raise ValueError(f"no pre-entry bars for {case_id}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    x_values = np.arange(len(frame), dtype=float)
    figure, axis = plt.subplots(figsize=(10, 4.8), dpi=150)
    for x_value, bar in zip(x_values, frame.itertuples(index=False), strict=True):
        open_price = float(bar.open)
        high_price = float(bar.high)
        low_price = float(bar.low)
        close_price = float(bar.close)
        color = "#2a9d8f" if close_price >= open_price else "#e76f51"
        axis.vlines(x_value, low_price, high_price, color=color, linewidth=0.8)
        body_low = min(open_price, close_price)
        body_height = abs(close_price - open_price)
        axis.add_patch(
            Rectangle(
                (x_value - 0.32, body_low),
                0.64,
                body_height if body_height else 0.02,
                facecolor=color,
                edgecolor=color,
                linewidth=0.8,
            )
        )

    day_labels: list[str] = []
    day_positions: list[float] = []
    for day_number, day in enumerate(normalized_target_days, start=1):
        positions = np.flatnonzero(frame["trading_day"].to_numpy() == day)
        if len(positions):
            day_labels.append(f"Day {day_number}")
            day_positions.append(float(positions.mean()))
    axis.set_title(str(case_id))
    axis.set_xlabel("")
    axis.set_ylabel("Normalized price")
    axis.set_xticks(day_positions, day_labels)
    axis.grid(axis="y", color="#d9d9d9", linewidth=0.6)
    axis.margins(x=0.01)
    figure.tight_layout()
    figure.savefig(output_path, format="png", metadata={"Software": "stage214_blind_chart"})
    plt.close(figure)
    return {
        "case_id": str(case_id),
        "chart_file": output_path.name,
        "available_day_count": int(frame["trading_day"].nunique()),
        "bar_count": int(len(frame)),
    }


def _sensitive_values(sealed_mapping: pd.DataFrame) -> set[str]:
    values: set[str] = set()
    for column in ["open_trade_id", "vt_symbol", "entry_date", "exit_date"]:
        if column not in sealed_mapping.columns:
            continue
        if column.endswith("_date"):
            values.update(
                pd.to_datetime(sealed_mapping[column], errors="coerce")
                .dropna()
                .dt.strftime("%Y-%m-%d")
                .tolist()
            )
        else:
            values.update(sealed_mapping[column].dropna().astype(str).tolist())
    return {value.lower() for value in values if value}


def _find_leak_tokens(text: str, sensitive_values: set[str]) -> list[str]:
    normalized = str(text).lower()
    leaks = [value for value in sorted(sensitive_values) if value in normalized]
    for pattern in [_OUTCOME_TOKEN, _DATE_TOKEN, _CONTRACT_TOKEN]:
        leaks.extend(match.group(0) for match in pattern.finditer(str(text)))
    return sorted(set(leaks))


def audit_blind_artifacts(
    chart_dir: Path,
    reviewer_manifest: pd.DataFrame,
    sealed_mapping: pd.DataFrame,
) -> dict[str, object]:
    """Reject chart-package identity and outcome leakage before reviewer handoff."""
    violations: list[str] = []
    chart_dir = Path(chart_dir)
    expected_columns = REVIEWER_MANIFEST_COLUMNS
    if reviewer_manifest.columns.tolist() != expected_columns:
        violations.append("reviewer_manifest_columns_not_exact")
    sensitive_values = _sensitive_values(sealed_mapping)

    expected_chart_files = set(reviewer_manifest.get("chart_file", pd.Series(dtype=str)).astype(str))
    if len(expected_chart_files) != len(reviewer_manifest):
        violations.append("reviewer_manifest_duplicate_chart_file")
    if "case_id" in reviewer_manifest.columns and "chart_file" in reviewer_manifest.columns:
        for row in reviewer_manifest.itertuples(index=False):
            expected_name = f"{row.case_id}.png"
            if str(row.chart_file) != expected_name:
                violations.append(
                    f"reviewer_manifest_case_filename_mismatch:{row.case_id}:{row.chart_file}"
                )

    for column in reviewer_manifest.columns:
        for row_number, value in enumerate(reviewer_manifest[column].fillna(""), start=1):
            leaks = _find_leak_tokens(f"{column}={value}", sensitive_values)
            if leaks:
                violations.append(
                    f"reviewer_manifest_row_{row_number}_{column}_leak:{'|'.join(leaks)}"
                )

    if not chart_dir.is_dir():
        violations.append("blind_chart_directory_missing")
        return {"ok": False, "violations": violations}
    chart_entries = sorted(chart_dir.iterdir(), key=lambda path: path.name)
    actual_chart_files: set[str] = set()
    for chart_path in chart_entries:
        if chart_path.is_symlink():
            violations.append(f"blind_chart_symlink_forbidden:{chart_path.name}")
            continue
        if not chart_path.is_file():
            violations.append(f"blind_chart_nonfile_forbidden:{chart_path.name}")
            continue
        if chart_path.name not in expected_chart_files:
            violations.append(f"blind_chart_unlisted_entry:{chart_path.name}")
            continue
        if not re.fullmatch(r"CASE-\d{3}\.png", chart_path.name):
            violations.append(f"unsafe_chart_filename:{chart_path.name}")
            continue
        actual_chart_files.add(chart_path.name)
        filename_leaks = _find_leak_tokens(chart_path.name, sensitive_values)
        if filename_leaks:
            violations.append(
                f"chart_filename_leak:{chart_path.name}:{'|'.join(filename_leaks)}"
            )
        try:
            with Image.open(chart_path) as image:
                for key, value in image.text.items():
                    if _ALLOWED_PNG_TEXT.get(key) != value:
                        violations.append(
                            f"png_text_not_allowlisted:{chart_path.name}:{key}"
                        )
        except OSError as error:
            violations.append(f"blind_chart_not_readable:{chart_path.name}:{error}")
    if actual_chart_files != expected_chart_files:
        violations.append("blind_chart_manifest_set_mismatch")
    return {"ok": not violations, "violations": violations}


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8")


def prepare(
    output_dir: Path = OUTPUT_DIR,
    *,
    database: object | None = None,
) -> dict[str, object]:
    """Build sealed controller artifacts and the separate reviewer-safe blind package."""
    input_paths = {
        "closed_lots": CLOSED_LOTS_PATH,
        "curves": CURVES_PATH,
        "minute_bars": MINUTE_PATH,
    }
    missing_inputs = [str(path) for path in input_paths.values() if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"missing frozen inputs: {missing_inputs}")
    if database is None:
        from vnpy.trader.database import get_database

        database = get_database()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    closed_lots = pd.read_csv(CLOSED_LOTS_PATH, low_memory=False)
    curves = pd.read_csv(CURVES_PATH, low_memory=False)
    events = build_short_events(closed_lots)
    events, _ = resolve_risk_zero_events(events, closed_lots)
    calendar = build_trading_calendar(curves)
    cache_paths = discover_contract_cache_paths(MINUTE_CACHE_ROOT, events)
    authorized_cache_paths = sorted(
        (output_dir / "authorized_tqsdk_raw").rglob("*.csv")
    )
    minutes, source_manifest = merge_minute_sources(
        events,
        calendar,
        MINUTE_PATH,
        cache_paths,
        database,
        authorized_cache_paths=authorized_cache_paths,
    )
    day_quality = build_minute_day_quality(minutes)
    gap_audit = build_data_gap_audit(events, minutes, calendar, day_quality)
    bars15 = build_preentry_15m(minutes, events, calendar)
    sealed_mapping = build_blind_mapping(events)

    _write_csv(events, output_dir / "short_event_manifest.csv")
    _write_csv(source_manifest, output_dir / "minute_source_manifest.csv")
    _write_csv(day_quality, output_dir / "minute_day_quality.csv")
    _write_csv(gap_audit, output_dir / "data_gap_audit.csv")
    _write_csv(sealed_mapping, output_dir / "blind_mapping.csv")

    chartable_ids = set(
        gap_audit.loc[gap_audit["coverage_state"].eq("complete"), "open_trade_id"].astype(str)
    )
    aggregate_r = pd.to_numeric(events.get("aggregate_r"), errors="coerce")
    result_analyzable_ids = set(
        events.loc[
            events["open_trade_id"].astype(str).isin(chartable_ids)
            & pd.Series(np.isfinite(aggregate_r), index=events.index),
            "open_trade_id",
        ].astype(str)
    )
    chart_dir = output_dir / "blind_charts"
    chart_dir.mkdir(exist_ok=True)
    reviewer_rows: list[dict[str, object]] = []
    for event in sealed_mapping.itertuples(index=False):
        if str(event.open_trade_id) not in chartable_ids:
            continue
        target_days = select_preentry_days(pd.Timestamp(event.entry_date), calendar)
        event_bars = bars15[bars15["vt_symbol"].astype(str).eq(str(event.vt_symbol))]
        reviewer_rows.append(
            render_blind_chart(
                str(event.case_id),
                event_bars,
                target_days,
                chart_dir / f"{event.case_id}.png",
            )
        )
    reviewer_manifest = pd.DataFrame(reviewer_rows, columns=REVIEWER_MANIFEST_COLUMNS)
    _write_csv(reviewer_manifest, output_dir / "reviewer_manifest.csv")
    calibration_cases = build_calibration_cases(reviewer_manifest)
    _write_csv(calibration_cases, output_dir / "calibration_cases.csv")

    expected_chart_files = set(reviewer_manifest["chart_file"].astype(str))
    actual_chart_files = {path.name for path in chart_dir.glob("*.png")}
    audit = audit_blind_artifacts(chart_dir, reviewer_manifest, sealed_mapping)
    blocking_reasons: list[str] = []
    if len(events) != EXPECTED_SHORT_EVENT_COUNT:
        blocking_reasons.append("event_count_not_64")
    if len(chartable_ids) != EXPECTED_SHORT_EVENT_COUNT:
        blocking_reasons.append("chartable_event_count_not_64")
    if len(result_analyzable_ids) < 60:
        blocking_reasons.append("result_analyzable_event_count_below_60")
    if actual_chart_files != expected_chart_files:
        blocking_reasons.append("chart_set_mismatch")
    if not audit["ok"]:
        blocking_reasons.append("blind_artifact_audit_failed")
    decision = {
        "status": "blocked" if blocking_reasons else "ready",
        "event_count": int(len(events)),
        "chartable_event_count": int(len(chartable_ids)),
        "result_analyzable_event_count": int(len(result_analyzable_ids)),
        "chart_count": int(len(actual_chart_files)),
        "chart_set_matches_reviewer_manifest": actual_chart_files == expected_chart_files,
        "blind_artifact_audit": audit,
        "blocking_reasons": blocking_reasons,
    }
    (output_dir / "prepare_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if blocking_reasons:
        raise RuntimeError(f"prepare blocked: {blocking_reasons}")
    return decision


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))

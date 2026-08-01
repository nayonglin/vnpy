from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit as s167  # noqa: E402
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719  # noqa: E402
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: E402
from qmt_roll_official_live_config import (  # noqa: E402
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)


LINE_ID = "futures_trend_tight_stop_quality_sizing"
STAGE = "Stage001"
MODEL_TAG = "stage001_baseline_technical_attribution_v1"
OUTPUT_PREFIX = "tight_stop_quality_stage001"
START = pd.Timestamp("2020-01-01")
END = pd.Timestamp("2026-06-30")
EXPECTED_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
EXPECTED_CAPITAL = 150_000.0

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage001_baseline_technical_attribution"
DATABASE_PATH = ROOT / ".vntrader" / "database.db"

BASELINE_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_daily_{MODEL_TAG}.csv.gz"
BASELINE_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_summary_{MODEL_TAG}.csv"
BASELINE_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_trades_{MODEL_TAG}.csv.gz"
BASELINE_ENTRY_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_entry_risk_{MODEL_TAG}.csv.gz"
BASELINE_ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_entry_candidates_evidence_only_{MODEL_TAG}.csv.gz"
BASELINE_TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_trade_events_{MODEL_TAG}.csv.gz"
BASELINE_STOP_RETRY_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_stop_retry_events_{MODEL_TAG}.csv.gz"
CLOSED_LOTS_PATH = OUT / f"{OUTPUT_PREFIX}_closed_lots_sanitized_{MODEL_TAG}.csv.gz"
OPEN_LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_open_lineage_{MODEL_TAG}.csv.gz"
ENTRY_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_entry_events_technical_features_{MODEL_TAG}.csv.gz"
THRESHOLDS_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_thresholds_{MODEL_TAG}.csv"
FEATURE_BIN_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_feature_bin_summary_{MODEL_TAG}.csv"
COMPOSITE_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_composite_rule_summary_{MODEL_TAG}.csv"
COMPOSITE_YEAR_PATH = OUT / f"{OUTPUT_PREFIX}_composite_rule_years_{MODEL_TAG}.csv"
ANNUAL_PATH = OUT / f"{OUTPUT_PREFIX}_annual_attribution_{MODEL_TAG}.csv"
DRAWDOWN_EPISODES_PATH = OUT / f"{OUTPUT_PREFIX}_drawdown_episodes_{MODEL_TAG}.csv"
FEATURE_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_feature_usage_audit_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
BASELINE_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_path_{MODEL_TAG}.png"
TECHNICAL_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_technical_attribution_{MODEL_TAG}.png"
DRAWDOWN_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_drawdown_attribution_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

TECHNICAL_FEATURE_COLUMNS = (
    "atr14",
    "atr_pct",
    "adx14",
    "directional_return20",
    "directional_return60",
    "efficiency20",
    "efficiency60",
    "directional_range_position20",
    "directional_range_position60",
    "di_spread14",
    "ma_stack_5_20_60",
    "directional_clv",
    "body_ratio",
    "adverse_wick_ratio",
    "support_wick_ratio",
    "nr7",
    "inside_bar",
    "compression7_atr",
)

THRESHOLD_COLUMNS = [
    "stop_atr14",
    "directional_range_position20",
    "adx14",
    "directional_clv",
    "body_ratio",
]

QUARTILE_FEATURES = (
    "stop_atr14",
    "directional_return20",
    "directional_return60",
    "efficiency20",
    "efficiency60",
    "directional_range_position20",
    "directional_range_position60",
    "adx14",
    "di_spread14",
    "directional_clv",
    "body_ratio",
    "adverse_wick_ratio",
    "compression7_atr",
)

RULE_ORDER = (
    "tight_directional_efficiency",
    "tight_range_position",
    "tight_ma_adx",
    "tight_strong_close",
)

SANITIZED_CLOSED_LOT_COLUMNS = (
    "lot_id",
    "open_trade_id",
    "close_trade_id",
    "vt_symbol",
    "product",
    "direction",
    "entry_date",
    "exit_date",
    "holding_calendar_days",
    "entry_price",
    "exit_price",
    "volume",
    "size",
    "realized_pnl",
    "risk_amount",
    "risk_per_contract",
    "r_multiple",
    "exit_reason",
    "signal",
    "risk_mode",
    "entry_context",
    "layer_kind",
    "risk_multiplier",
    "target_risk_amount",
    "selected_volume",
    "contracts_by_risk",
    "contracts_by_margin",
    "stop_distance",
    "entry_risk_distance_pct",
    "path_bar_count",
    "mfe_cash",
    "mae_cash",
    "mfe_r",
    "mae_r",
    "exit_efficiency",
    "days_to_mfe",
    "days_to_mae",
)

EXTERNAL_RESEARCH = (
    {
        "source": "Trends' Signal Strength and the Performance of CTAs",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2772047",
        "finding": "Multi-horizon signal aggregation can express trend strength, but does not validate this strategy's rule.",
    },
    {
        "source": "Time series momentum and volatility scaling",
        "url": "https://www.sciencedirect.com/science/article/pii/S1386418116301379",
        "finding": "Volatility scaling may drive a large share of futures momentum returns, so leverage and selection must be separated.",
    },
    {
        "source": "TA-Lib official GitHub organization",
        "url": "https://github.com/ta-lib",
        "finding": "ATR, ADX/DI and candlestick primitives have transparent conventional implementations.",
    },
    {
        "source": "Backtrader official GitHub",
        "url": "https://github.com/mementum/backtrader",
        "finding": "Stop, bracket and sizing semantics must remain explicit in a backtest engine.",
    },
)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def assert_no_ai_features(frame: pd.DataFrame) -> None:
    forbidden = [column for column in frame.columns if "ai_" in column.lower() or column.lower().startswith("ai")]
    if forbidden:
        raise ValueError(f"AI-derived columns are forbidden in technical feature output: {forbidden}")


def _wilder_average(series: pd.Series, period: int) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    result = np.full(len(values), np.nan, dtype=float)
    start = None
    for end in range(period - 1, len(values)):
        window = values[end - period + 1 : end + 1]
        if np.isfinite(window).all():
            result[end] = float(window.mean())
            start = end
            break
    if start is None:
        return pd.Series(result, index=series.index, dtype=float)
    for index in range(start + 1, len(values)):
        current = values[index]
        previous = result[index - 1]
        if np.isfinite(current) and np.isfinite(previous):
            result[index] = (previous * (period - 1) + current) / period
    return pd.Series(result, index=series.index, dtype=float)


def _prepare_bars(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(bars.columns)
    if missing:
        raise ValueError(f"bars missing required columns: {sorted(missing)}")
    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "close_oi"]:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    return frame.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def load_contract_bars_from_database(vt_symbol: Any, db_path: Path = DATABASE_PATH) -> pd.DataFrame:
    text = str(vt_symbol or "")
    if "." not in text or not db_path.exists():
        return pd.DataFrame()
    symbol, exchange = text.split(".", 1)
    query = """
        SELECT
            datetime AS date,
            open_price AS open,
            high_price AS high,
            low_price AS low,
            close_price AS close,
            volume,
            open_interest AS close_oi
        FROM dbbardata
        WHERE symbol = ? AND exchange = ? AND interval = 'd'
        ORDER BY datetime
    """
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        frame = pd.read_sql_query(query, connection, params=(symbol, exchange))
    return _prepare_bars(frame) if not frame.empty else frame


def indicator_panel(bars: pd.DataFrame) -> pd.DataFrame:
    frame = _prepare_bars(bars)
    if frame.empty:
        return frame
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    true_range.iloc[0] = np.nan
    frame["true_range"] = true_range
    frame["atr14"] = _wilder_average(true_range, 14)

    up_move = frame["high"].diff()
    down_move = -frame["low"].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=frame.index)
    plus_dm.iloc[0] = np.nan
    minus_dm.iloc[0] = np.nan
    plus_smoothed = _wilder_average(plus_dm, 14)
    minus_smoothed = _wilder_average(minus_dm, 14)
    atr = frame["atr14"].replace(0.0, np.nan)
    frame["plus_di14"] = 100.0 * plus_smoothed / atr
    frame["minus_di14"] = 100.0 * minus_smoothed / atr
    denominator = (frame["plus_di14"] + frame["minus_di14"]).replace(0.0, np.nan)
    dx = 100.0 * (frame["plus_di14"] - frame["minus_di14"]).abs() / denominator
    frame["adx14"] = _wilder_average(dx, 14)

    absolute_change = frame["close"].diff().abs()
    for period in (20, 60):
        frame[f"return{period}"] = frame["close"] / frame["close"].shift(period) - 1.0
        path = absolute_change.rolling(period, min_periods=period).sum().replace(0.0, np.nan)
        frame[f"efficiency{period}"] = (frame["close"] - frame["close"].shift(period)) / path
        rolling_high = frame["high"].rolling(period, min_periods=period).max()
        rolling_low = frame["low"].rolling(period, min_periods=period).min()
        frame[f"range_position{period}"] = (frame["close"] - rolling_low) / (rolling_high - rolling_low).replace(0.0, np.nan)

    for period in (5, 20, 60):
        frame[f"ma{period}"] = frame["close"].rolling(period, min_periods=period).mean()

    bar_range = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    upper_body = frame[["open", "close"]].max(axis=1)
    lower_body = frame[["open", "close"]].min(axis=1)
    frame["clv"] = (frame["close"] - frame["low"]) / bar_range
    frame["body_ratio"] = (frame["close"] - frame["open"]).abs() / bar_range
    frame["upper_wick_ratio"] = (frame["high"] - upper_body) / bar_range
    frame["lower_wick_ratio"] = (lower_body - frame["low"]) / bar_range
    frame["nr7"] = (bar_range <= bar_range.rolling(7, min_periods=7).min() + 1e-12).astype(float)
    frame["inside_bar"] = ((frame["high"] <= frame["high"].shift(1)) & (frame["low"] >= frame["low"].shift(1))).astype(float)
    range7 = frame["high"].rolling(7, min_periods=7).max() - frame["low"].rolling(7, min_periods=7).min()
    frame["compression7_atr"] = range7 / atr
    frame["atr_pct"] = frame["atr14"] / frame["close"].replace(0.0, np.nan)
    return frame


def _features_from_panel(panel: pd.DataFrame, entry_date: Any, direction: str) -> dict[str, Any]:
    entry = pd.Timestamp(entry_date).normalize()
    history = panel[pd.to_datetime(panel["date"], errors="coerce").dt.normalize() < entry]
    if history.empty:
        return {"feature_date": pd.NaT, "feature_bar_count": 0, **{column: np.nan for column in TECHNICAL_FEATURE_COLUMNS}}
    row = history.iloc[-1]
    sign = 1.0 if str(direction).lower() == "long" else -1.0
    range20 = _safe_float(row.get("range_position20"))
    range60 = _safe_float(row.get("range_position60"))
    clv = _safe_float(row.get("clv"))
    if sign > 0:
        directional_range20 = range20
        directional_range60 = range60
        directional_clv = clv
        adverse_wick = _safe_float(row.get("upper_wick_ratio"))
        support_wick = _safe_float(row.get("lower_wick_ratio"))
        ma_stack = float(row.get("ma5", np.nan) > row.get("ma20", np.nan) > row.get("ma60", np.nan))
    else:
        directional_range20 = 1.0 - range20 if np.isfinite(range20) else np.nan
        directional_range60 = 1.0 - range60 if np.isfinite(range60) else np.nan
        directional_clv = 1.0 - clv if np.isfinite(clv) else np.nan
        adverse_wick = _safe_float(row.get("lower_wick_ratio"))
        support_wick = _safe_float(row.get("upper_wick_ratio"))
        ma_stack = float(row.get("ma5", np.nan) < row.get("ma20", np.nan) < row.get("ma60", np.nan))
    result = {
        "feature_date": pd.Timestamp(row["date"]).normalize(),
        "feature_bar_count": int(len(history)),
        "atr14": _safe_float(row.get("atr14")),
        "atr_pct": _safe_float(row.get("atr_pct")),
        "adx14": _safe_float(row.get("adx14")),
        "directional_return20": sign * _safe_float(row.get("return20")),
        "directional_return60": sign * _safe_float(row.get("return60")),
        "efficiency20": sign * _safe_float(row.get("efficiency20")),
        "efficiency60": sign * _safe_float(row.get("efficiency60")),
        "directional_range_position20": directional_range20,
        "directional_range_position60": directional_range60,
        "di_spread14": sign * (_safe_float(row.get("plus_di14")) - _safe_float(row.get("minus_di14"))),
        "ma_stack_5_20_60": ma_stack,
        "directional_clv": directional_clv,
        "body_ratio": _safe_float(row.get("body_ratio")),
        "adverse_wick_ratio": adverse_wick,
        "support_wick_ratio": support_wick,
        "nr7": _safe_float(row.get("nr7")),
        "inside_bar": _safe_float(row.get("inside_bar")),
        "compression7_atr": _safe_float(row.get("compression7_atr")),
    }
    return result


def technical_features_before_entry(bars: pd.DataFrame, entry_date: Any, direction: str) -> dict[str, Any]:
    return _features_from_panel(indicator_panel(bars), entry_date, direction)


def _local_naive_datetime(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce", utc=True)
    return parsed.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)


def _source_text(source: dict[str, Any], key: str, default: str = "") -> str:
    value = source.get(key)
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    return text if text and text.lower() not in {"nan", "nat", "none"} else default


def _canonical_product_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    symbol, separator, exchange = text.partition(".")
    product = "".join(char for char in symbol if char.isalpha())
    return f"{product}.{exchange}" if product and separator and exchange else product


def _match_source_rows_to_open_trades(
    trades: pd.DataFrame,
    source: pd.DataFrame,
    *,
    source_kind: str,
    volume_column: str,
    source_id_column: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if trades.empty or source.empty:
        return {}, {
            "source_kind": source_kind,
            "source_row_count": int(len(source)),
            "matched_source_count": 0,
            "unmatched_source_count": int(len(source)),
        }
    opens = trades[trades["offset"].astype(str).str.lower().eq("open")].copy()
    order_ids = opens.get("order_id", pd.Series("", index=opens.index, dtype=object)).astype(str)
    opens = opens[~order_ids.str.contains(".stage847_c9.2", regex=False)].copy()
    opens["match_datetime"] = _local_naive_datetime(opens["datetime"])
    opens["match_direction"] = opens["direction"].astype(str).str.lower()
    opens["match_volume"] = pd.to_numeric(opens["volume"], errors="coerce")
    opens["match_trade_sequence"] = pd.to_numeric(
        opens["trade_id"].astype(str).str.extract(r"(\d+)$", expand=False),
        errors="coerce",
    )
    opens.sort_values(["match_datetime", "vt_symbol", "match_trade_sequence", "trade_id"], inplace=True)

    candidates = source.copy()
    candidates["match_source_row"] = np.arange(len(candidates), dtype=int)
    candidates["match_datetime"] = _local_naive_datetime(candidates["datetime"])
    candidates["match_direction"] = candidates["direction"].astype(str).str.lower()
    candidates["match_volume"] = pd.to_numeric(candidates[volume_column], errors="coerce")
    candidates.sort_values(["match_datetime", "contract_vt_symbol", source_id_column], inplace=True)

    matched: dict[str, dict[str, Any]] = {}
    used_source_rows: set[int] = set()
    match_lag_days: list[float] = []
    match_volume_mismatches: list[float] = []
    unmatched_open_ids: list[str] = []
    for open_row in opens.to_dict("records"):
        open_dt = pd.Timestamp(open_row["match_datetime"])
        eligible = candidates[
            candidates["contract_vt_symbol"].astype(str).eq(str(open_row["vt_symbol"]))
            & candidates["match_direction"].eq(str(open_row["match_direction"]))
            & candidates["match_datetime"].le(open_dt)
            & candidates["match_datetime"].ge(open_dt - pd.Timedelta(days=15))
            & ~candidates["match_source_row"].isin(used_source_rows)
        ].copy()
        if eligible.empty:
            unmatched_open_ids.append(str(open_row.get("trade_id", "")))
            continue
        eligible["volume_mismatch"] = (
            pd.to_numeric(eligible["match_volume"], errors="coerce") - _safe_float(open_row.get("match_volume"))
        ).abs()
        eligible["lag_seconds"] = (open_dt - eligible["match_datetime"]).dt.total_seconds()
        eligible.sort_values(["lag_seconds", "volume_mismatch", source_id_column], inplace=True)
        source_row = eligible.iloc[0].to_dict()
        trade_id = str(open_row["trade_id"])
        clean_source = {
            key: value
            for key, value in source_row.items()
            if not key.startswith("match_") and key not in {"volume_mismatch", "lag_seconds"}
        }
        clean_source["lineage_source_kind"] = source_kind
        clean_source["lineage_source_datetime"] = source_row["match_datetime"]
        clean_source["lineage_match_lag_seconds"] = float(source_row["lag_seconds"])
        clean_source["lineage_volume_mismatch"] = float(source_row["volume_mismatch"])
        matched[trade_id] = clean_source
        used_source_rows.add(int(source_row["match_source_row"]))
        match_lag_days.append(float(source_row["lag_seconds"]) / 86_400.0)
        match_volume_mismatches.append(float(source_row["volume_mismatch"]))
    unmatched = candidates[~candidates["match_source_row"].isin(used_source_rows)]
    unmatched_source_ids = unmatched[source_id_column].astype(str).tolist()
    return matched, {
        "source_kind": source_kind,
        "source_row_count": int(len(candidates)),
        "matched_source_count": int(len(matched)),
        "unmatched_source_count": int(len(unmatched_source_ids)),
        "unmatched_source_ids": unmatched_source_ids,
        "eligible_root_open_count": int(len(opens)),
        "unmatched_root_open_count": int(len(unmatched_open_ids)),
        "unmatched_root_open_ids": unmatched_open_ids,
        "volume_mismatch_match_count": int(sum(value > 1e-8 for value in match_volume_mismatches)),
        "max_volume_mismatch": max(match_volume_mismatches, default=0.0),
        "max_match_lag_days": max(match_lag_days, default=0.0),
    }


def build_complete_closed_lot_lineage(
    closed_lots: pd.DataFrame,
    trades: pd.DataFrame,
    entry_risk: pd.DataFrame,
    entry_candidates: pd.DataFrame,
    *,
    priceticks: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    data = closed_lots.copy()
    trade_data = trades.copy()
    trade_data["datetime_local"] = _local_naive_datetime(trade_data["datetime"])
    trade_data["date_local"] = trade_data["datetime_local"].dt.normalize()
    trade_data.sort_values(["datetime_local", "vt_symbol", "trade_id"], inplace=True)

    risk_map, risk_audit = _match_source_rows_to_open_trades(
        trade_data,
        entry_risk,
        source_kind="entry_risk",
        volume_column="volume",
        source_id_column="entry_index",
    )
    opened_candidates = (
        entry_candidates[entry_candidates["candidate_status"].astype(str).eq("opened")].copy()
        if not entry_candidates.empty and "candidate_status" in entry_candidates.columns
        else pd.DataFrame()
    )
    candidate_map, candidate_audit = _match_source_rows_to_open_trades(
        trade_data,
        opened_candidates,
        source_kind="entry_candidate",
        volume_column="selected_volume",
        source_id_column="candidate_index",
    )

    opens = trade_data[trade_data["offset"].astype(str).str.lower().eq("open")].copy()
    open_by_id = {str(row["trade_id"]): row for row in opens.to_dict("records")}
    open_trade_id_by_order = {str(row.get("order_id", "")): str(row["trade_id"]) for row in opens.to_dict("records")}
    source_by_open: dict[str, dict[str, Any]] = {}
    attempt_kind_by_open: dict[str, str] = {}
    for open_id, open_row in open_by_id.items():
        order_id = str(open_row.get("order_id", ""))
        source_row = risk_map.get(open_id) or candidate_map.get(open_id) or {}
        context = str(source_row.get("entry_context", "") or "")
        if ".stage847_c9.2" in order_id:
            attempt_kind = "stop_retry"
        elif context == "flat_entry":
            attempt_kind = "flat_entry"
        elif context == "rollover_reopen":
            attempt_kind = "rollover_reopen"
        else:
            attempt_kind = "unclassified"
        source_by_open[open_id] = source_row
        attempt_kind_by_open[open_id] = attempt_kind

    lots_by_close_id: dict[str, list[str]] = {}
    for row in data.to_dict("records"):
        lots_by_close_id.setdefault(str(row["close_trade_id"]), []).append(str(row["open_trade_id"]))

    parent_by_open: dict[str, str] = {}
    lineage_reason_by_open: dict[str, str] = {}
    open_rows = opens.sort_values(["datetime_local", "trade_id"]).to_dict("records")
    close_rows = trade_data[trade_data["offset"].astype(str).str.lower().eq("close")].to_dict("records")
    for open_row in open_rows:
        open_id = str(open_row["trade_id"])
        attempt_kind = attempt_kind_by_open[open_id]
        if attempt_kind == "flat_entry":
            parent_by_open[open_id] = open_id
            lineage_reason_by_open[open_id] = "flat_entry_parent"
            continue
        if attempt_kind == "stop_retry":
            root_order_id = str(open_row.get("order_id", "")).split(".stage847_c9.", 1)[0]
            root_open_id = open_trade_id_by_order.get(root_order_id, "")
            root_parent = parent_by_open.get(root_open_id, "")
            if root_parent:
                parent_by_open[open_id] = root_parent
                lineage_reason_by_open[open_id] = f"retry_root:{root_open_id}"
            continue
        if attempt_kind == "rollover_reopen":
            open_date = pd.Timestamp(open_row["date_local"])
            product = s719._infer_product(open_row["vt_symbol"])
            position_direction = str(open_row["direction"]).lower()
            possible_closes: list[dict[str, Any]] = []
            for close_row in close_rows:
                if pd.Timestamp(close_row["date_local"]) != open_date:
                    continue
                if s719._infer_product(close_row["vt_symbol"]) != product:
                    continue
                close_position_direction = "long" if str(close_row["direction"]).lower() == "short" else "short"
                if close_position_direction != position_direction:
                    continue
                if pd.Timestamp(close_row["datetime_local"]) > pd.Timestamp(open_row["datetime_local"]):
                    continue
                possible_closes.append(close_row)
            possible_closes.sort(
                key=lambda row: (
                    0 if str(row.get("exit_reason", "")) == "rollover_close" else 1,
                    -pd.Timestamp(row["datetime_local"]).value,
                    str(row["trade_id"]),
                )
            )
            for close_row in possible_closes:
                prior_open_ids = lots_by_close_id.get(str(close_row["trade_id"]), [])
                prior_parents = {parent_by_open.get(item, "") for item in prior_open_ids} - {""}
                if len(prior_parents) == 1:
                    parent_by_open[open_id] = prior_parents.pop()
                    lineage_reason_by_open[open_id] = f"rollover_close:{close_row['trade_id']}"
                    break

    lineage_rows: list[dict[str, Any]] = []
    for open_row in open_rows:
        open_id = str(open_row["trade_id"])
        source_row = source_by_open.get(open_id, {})
        attempt_kind = attempt_kind_by_open[open_id]
        parent_event_id = parent_by_open.get(open_id, "")
        risk_source = source_row
        if attempt_kind == "stop_retry":
            root_order_id = str(open_row.get("order_id", "")).split(".stage847_c9.", 1)[0]
            root_open_id = open_trade_id_by_order.get(root_order_id, "")
            risk_source = source_by_open.get(root_open_id, {})
        planned_stop_distance = _safe_float(risk_source.get("stop_distance"))
        size = _safe_float(risk_source.get("size"))
        if not np.isfinite(size) or size <= 0:
            matching_lots = data[data["open_trade_id"].astype(str).eq(open_id)]
            size = _safe_float(matching_lots["size"].iloc[0]) if not matching_lots.empty else np.nan
        planned_risk_per_contract = _safe_float(risk_source.get("risk_per_contract"))
        if (
            (not np.isfinite(planned_risk_per_contract) or planned_risk_per_contract <= 0)
            and np.isfinite(planned_stop_distance)
            and np.isfinite(size)
        ):
            planned_risk_per_contract = planned_stop_distance * size
        actual_entry_price = _safe_float(open_row.get("price"))
        planned_entry_price = _safe_float(
            risk_source.get("planned_entry_price"),
            _safe_float(risk_source.get("entry_price")),
        )
        stop_price = _safe_float(risk_source.get("stop_price"))
        price_tick = _safe_float((priceticks or {}).get(str(open_row.get("vt_symbol", ""))))
        actual_stop_distance = (
            abs(actual_entry_price - stop_price)
            if actual_entry_price > 0 and np.isfinite(stop_price)
            else np.nan
        )
        min_risk = max(price_tick * size, 1.0) if price_tick > 0 and size > 0 else 1.0
        actual_risk_recomputed = int(
            np.isfinite(actual_stop_distance)
            and actual_stop_distance >= 0
            and np.isfinite(size)
            and size > 0
        )
        risk_per_contract = (
            max(actual_stop_distance * size, min_risk)
            if actual_risk_recomputed
            else planned_risk_per_contract
        )
        source_selected_volume = _safe_float(
            risk_source.get("selected_volume"),
            _safe_float(risk_source.get("volume")),
        )
        product = _source_text(
            risk_source,
            "product_vt_symbol",
            _canonical_product_vt_symbol(open_row.get("vt_symbol")),
        )
        lineage_rows.append(
            {
                "open_trade_id": open_id,
                "open_order_id": str(open_row.get("order_id", "")),
                "datetime": open_row["datetime_local"],
                "vt_symbol": str(open_row["vt_symbol"]),
                "direction": str(open_row["direction"]).lower(),
                "volume": _safe_float(open_row.get("volume")),
                "attempt_kind": attempt_kind,
                "parent_event_id": parent_event_id,
                "lineage_reason": lineage_reason_by_open.get(open_id, ""),
                "source_kind": _source_text(risk_source, "lineage_source_kind"),
                "source_datetime": risk_source.get("lineage_source_datetime", pd.NaT),
                "source_match_lag_seconds": _safe_float(risk_source.get("lineage_match_lag_seconds")),
                "source_volume_mismatch": _safe_float(risk_source.get("lineage_volume_mismatch")),
                "source_context": _source_text(risk_source, "entry_context"),
                "source_id": _source_text(
                    risk_source,
                    "entry_index",
                    _source_text(risk_source, "candidate_index"),
                ),
                "product": product,
                "signal": _source_text(risk_source, "signal"),
                "risk_mode": _source_text(risk_source, "risk_mode"),
                "layer_kind": _source_text(risk_source, "layer_kind"),
                "size": size,
                "risk_multiplier": _safe_float(risk_source.get("risk_multiplier")),
                "target_risk_amount": _safe_float(risk_source.get("target_risk_amount")),
                "source_selected_volume": source_selected_volume,
                "contracts_by_risk": _safe_float(risk_source.get("contracts_by_risk")),
                "contracts_by_margin": _safe_float(risk_source.get("contracts_by_margin")),
                "stop_price": stop_price,
                "planned_entry_price": planned_entry_price,
                "actual_entry_price": actual_entry_price,
                "planned_stop_distance": planned_stop_distance,
                "actual_stop_distance": actual_stop_distance,
                "stop_distance": planned_stop_distance,
                "planned_risk_per_contract": planned_risk_per_contract,
                "risk_per_contract": risk_per_contract,
                "actual_risk_recomputed": actual_risk_recomputed,
                "planned_entry_risk_distance_pct": (
                    planned_stop_distance / planned_entry_price
                    if planned_entry_price > 0 and np.isfinite(planned_stop_distance)
                    else np.nan
                ),
                "entry_risk_distance_pct": (
                    actual_stop_distance / actual_entry_price
                    if actual_entry_price > 0 and np.isfinite(actual_stop_distance)
                    else np.nan
                ),
            }
        )
    lineage = pd.DataFrame(lineage_rows)
    unresolved = lineage[lineage["parent_event_id"].astype(str).eq("")]
    if not unresolved.empty:
        raise RuntimeError(
            "unresolved open lineage: "
            + ",".join(unresolved["open_trade_id"].astype(str).tolist())
        )

    lineage_by_open = lineage.set_index("open_trade_id").to_dict("index")
    enriched_rows: list[dict[str, Any]] = []
    for row in data.to_dict("records"):
        open_id = str(row["open_trade_id"])
        lineage_row = lineage_by_open[open_id]
        risk_per_contract = _safe_float(lineage_row.get("risk_per_contract"))
        volume = _safe_float(row.get("volume"))
        risk_amount = risk_per_contract * volume if risk_per_contract > 0 and volume > 0 else np.nan
        planned_stop_distance = _safe_float(lineage_row.get("planned_stop_distance"))
        actual_stop_distance = _safe_float(lineage_row.get("actual_stop_distance"))
        realized_pnl = _safe_float(row.get("realized_pnl"), 0.0)
        size = _safe_float(lineage_row.get("size"), _safe_float(row.get("size")))
        enriched_rows.append(
            {
                **row,
                "open_order_id": lineage_row["open_order_id"],
                "product": lineage_row["product"],
                "size": size,
                "signal": lineage_row["signal"],
                "risk_mode": lineage_row["risk_mode"],
                "entry_context": lineage_row["source_context"],
                "layer_kind": lineage_row["layer_kind"],
                "risk_multiplier": lineage_row["risk_multiplier"],
                "target_risk_amount": lineage_row["target_risk_amount"],
                "selected_volume": lineage_row["source_selected_volume"],
                "contracts_by_risk": lineage_row["contracts_by_risk"],
                "contracts_by_margin": lineage_row["contracts_by_margin"],
                "attempt_kind": lineage_row["attempt_kind"],
                "parent_event_id": lineage_row["parent_event_id"],
                "lineage_reason": lineage_row["lineage_reason"],
                "lineage_source_kind": lineage_row["source_kind"],
                "lineage_source_id": lineage_row["source_id"],
                "source_selected_volume": lineage_row["source_selected_volume"],
                "stop_price": lineage_row["stop_price"],
                "planned_entry_price": lineage_row["planned_entry_price"],
                "actual_entry_price": lineage_row["actual_entry_price"],
                "planned_stop_distance": planned_stop_distance,
                "actual_stop_distance": actual_stop_distance,
                "stop_distance": planned_stop_distance,
                "planned_entry_risk_distance_pct": lineage_row["planned_entry_risk_distance_pct"],
                "entry_risk_distance_pct": lineage_row["entry_risk_distance_pct"],
                "planned_risk_per_contract": lineage_row["planned_risk_per_contract"],
                "risk_per_contract": risk_per_contract,
                "actual_risk_recomputed": lineage_row["actual_risk_recomputed"],
                "risk_amount": risk_amount,
                "r_multiple": realized_pnl / risk_amount if risk_amount > 0 else np.nan,
            }
        )
    enriched = pd.DataFrame(enriched_rows)
    audit = {
        "closed_lot_count": int(len(enriched)),
        "closed_lot_gross_pnl": float(pd.to_numeric(enriched["realized_pnl"], errors="coerce").sum()),
        "open_trade_count": int(len(lineage)),
        "flat_entry_open_count": int(lineage["attempt_kind"].eq("flat_entry").sum()),
        "stop_retry_open_count": int(lineage["attempt_kind"].eq("stop_retry").sum()),
        "rollover_reopen_count": int(lineage["attempt_kind"].eq("rollover_reopen").sum()),
        "unclassified_open_count": int(lineage["attempt_kind"].eq("unclassified").sum()),
        "orphan_open_count": int(lineage["parent_event_id"].astype(str).eq("").sum()),
        "actual_risk_recomputed_open_count": int(lineage["actual_risk_recomputed"].eq(1).sum()),
        "actual_risk_missing_open_ids": lineage.loc[
            lineage["actual_risk_recomputed"].ne(1), "open_trade_id"
        ].astype(str).tolist(),
        "risk_source_audit": risk_audit,
        "candidate_source_audit": candidate_audit,
    }
    return enriched, lineage, audit


def aggregate_entry_events(closed_lots: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {
        "open_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "entry_price",
        "volume",
        "risk_amount",
        "realized_pnl",
        "stop_distance",
        "entry_context",
    }
    missing = required - set(closed_lots.columns)
    if missing:
        raise ValueError(f"closed lots missing columns: {sorted(missing)}")
    data = closed_lots.copy()
    if "parent_event_id" not in data.columns:
        data = data[data["entry_context"].astype(str).eq("flat_entry")].copy()
        data["parent_event_id"] = data["open_trade_id"].astype(str)
        data["attempt_kind"] = "flat_entry"
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    for column in [
        "entry_price",
        "volume",
        "risk_amount",
        "realized_pnl",
        "stop_distance",
        "actual_stop_distance",
    ]:
        if column not in data.columns:
            data[column] = np.nan
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["open_trade_id", "parent_event_id", "entry_date", "entry_price", "risk_amount", "realized_pnl"])

    consistency_columns = [
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "entry_price",
        "stop_distance",
        "actual_stop_distance",
    ]
    inconsistent_groups: list[str] = []
    rows: list[dict[str, Any]] = []
    for parent_event_id, group in data.groupby("parent_event_id", sort=False):
        initial = group[
            group["attempt_kind"].astype(str).eq("flat_entry")
            & group["open_trade_id"].astype(str).eq(str(parent_event_id))
        ]
        if initial.empty or any(initial[column].nunique(dropna=False) > 1 for column in consistency_columns):
            inconsistent_groups.append(str(parent_event_id))
            continue
        risk_rows = group[group["attempt_kind"].astype(str).isin(["flat_entry", "stop_retry"])]
        risk_amount = float(risk_rows["risk_amount"].sum())
        realized_pnl = float(group["realized_pnl"].sum())
        rows.append(
            {
                "open_trade_id": str(parent_event_id),
                "vt_symbol": str(initial["vt_symbol"].iloc[0]),
                "product": str(initial["product"].iloc[0]),
                "direction": str(initial["direction"].iloc[0]).lower(),
                "entry_date": pd.Timestamp(initial["entry_date"].iloc[0]).normalize(),
                "exit_date": pd.Timestamp(group["exit_date"].max()).normalize(),
                "entry_price": float(initial["entry_price"].iloc[0]),
                "volume": float(initial["volume"].sum()),
                "risk_amount": risk_amount,
                "realized_pnl": realized_pnl,
                "r_multiple": realized_pnl / risk_amount if risk_amount > 0 else np.nan,
                "stop_distance": float(initial["stop_distance"].iloc[0]),
                "planned_stop_distance": float(initial["stop_distance"].iloc[0]),
                "actual_stop_distance": float(initial["actual_stop_distance"].iloc[0]),
                "closed_lot_count": int(len(group)),
                "attempt_count": int(group["open_trade_id"].astype(str).nunique()),
                "retry_attempt_count": int(group.loc[group["attempt_kind"].eq("stop_retry"), "open_trade_id"].nunique()),
                "rollover_attempt_count": int(group.loc[group["attempt_kind"].eq("rollover_reopen"), "open_trade_id"].nunique()),
                "initial_pnl": float(group.loc[group["attempt_kind"].eq("flat_entry"), "realized_pnl"].sum()),
                "retry_pnl": float(group.loc[group["attempt_kind"].eq("stop_retry"), "realized_pnl"].sum()),
                "rollover_pnl": float(group.loc[group["attempt_kind"].eq("rollover_reopen"), "realized_pnl"].sum()),
                "exit_reason_count": int(group.get("exit_reason", pd.Series(index=group.index, dtype=object)).nunique()),
            }
        )
    events = pd.DataFrame(rows)
    if not events.empty:
        events.sort_values(["entry_date", "open_trade_id"], inplace=True)
        events.reset_index(drop=True, inplace=True)
    audit = {
        "input_closed_lot_count": int(len(closed_lots)),
        "attributed_closed_lot_count": int(len(data)),
        "entry_event_count": int(len(events)),
        "inconsistent_group_count": int(len(inconsistent_groups)),
        "inconsistent_open_trade_ids": inconsistent_groups,
        "closed_lot_pnl": float(data["realized_pnl"].sum()) if not data.empty else 0.0,
        "entry_event_pnl": float(events["realized_pnl"].sum()) if not events.empty else 0.0,
        "closed_lot_risk": float(data.loc[data["attempt_kind"].isin(["flat_entry", "stop_retry"]), "risk_amount"].sum()) if not data.empty else 0.0,
        "entry_event_risk": float(events["risk_amount"].sum()) if not events.empty else 0.0,
    }
    return events, audit


def _sample_segment(entry_date: Any) -> str:
    year = pd.Timestamp(entry_date).year
    if year <= 2022:
        return "discovery"
    if year <= 2024:
        return "validation"
    return "holdout"


def attach_technical_features(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if events.empty:
        return events.copy(), pd.DataFrame()
    cache: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    database_exists = DATABASE_PATH.exists()
    database_bytes = int(DATABASE_PATH.stat().st_size) if database_exists else 0
    database_sha256 = _sha256(DATABASE_PATH) if database_exists else ""
    for event in events.to_dict("records"):
        vt_symbol = str(event["vt_symbol"])
        if vt_symbol not in cache:
            bars = load_contract_bars_from_database(vt_symbol)
            cache[vt_symbol] = indicator_panel(bars) if not bars.empty else pd.DataFrame()
            source_rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "path": str(DATABASE_PATH),
                    "exists": bool(not bars.empty),
                    "database_exists": database_exists,
                    "bytes": database_bytes,
                    "sha256": database_sha256,
                    "bar_count": int(len(cache[vt_symbol])),
                    "first_bar_date": bars["date"].min() if not bars.empty else pd.NaT,
                    "last_bar_date": bars["date"].max() if not bars.empty else pd.NaT,
                }
            )
        panel = cache[vt_symbol]
        features = (
            _features_from_panel(panel, event["entry_date"], str(event["direction"]))
            if not panel.empty
            else {"feature_date": pd.NaT, "feature_bar_count": 0, **{column: np.nan for column in TECHNICAL_FEATURE_COLUMNS}}
        )
        stop_distance = _safe_float(event.get("stop_distance"))
        entry_price = _safe_float(event.get("entry_price"))
        atr14 = _safe_float(features.get("atr14"))
        row = {
            **event,
            **features,
            "stop_pct": stop_distance / entry_price if entry_price > 0 else np.nan,
            "stop_atr14": stop_distance / atr14 if atr14 > 0 else np.nan,
            "entry_year": int(pd.Timestamp(event["entry_date"]).year),
            "sample_segment": _sample_segment(event["entry_date"]),
            "feature_future_violation": int(
                pd.notna(features.get("feature_date"))
                and pd.Timestamp(features["feature_date"]).normalize() >= pd.Timestamp(event["entry_date"]).normalize()
            ),
        }
        rows.append(row)
    result = pd.DataFrame(rows)
    assert_no_ai_features(result)
    return result, pd.DataFrame(source_rows).sort_values("vt_symbol").reset_index(drop=True)


def discovery_thresholds(frame: pd.DataFrame) -> dict[str, float]:
    discovery = frame[frame["sample_segment"].astype(str).eq("discovery")]
    if discovery.empty:
        raise ValueError("discovery segment is empty")

    def quantile(column: str, value: float) -> float:
        series = pd.to_numeric(discovery[column], errors="coerce").dropna()
        if series.empty:
            raise ValueError(f"discovery feature is empty: {column}")
        return float(series.quantile(value))

    return {
        "stop_atr14_q25": quantile("stop_atr14", 0.25),
        "directional_range_position20_q75": quantile("directional_range_position20", 0.75),
        "adx14_q50": quantile("adx14", 0.50),
        "directional_clv_q75": quantile("directional_clv", 0.75),
        "body_ratio_q50": quantile("body_ratio", 0.50),
    }


def apply_composite_rules(frame: pd.DataFrame, thresholds: dict[str, float]) -> pd.DataFrame:
    result = frame.copy()
    tight = pd.to_numeric(result["stop_atr14"], errors="coerce").le(thresholds["stop_atr14_q25"])
    result["tight_directional_efficiency"] = (
        tight
        & pd.to_numeric(result["efficiency20"], errors="coerce").gt(0.0)
        & pd.to_numeric(result["efficiency60"], errors="coerce").gt(0.0)
    )
    result["tight_range_position"] = tight & pd.to_numeric(
        result["directional_range_position20"], errors="coerce"
    ).ge(thresholds["directional_range_position20_q75"])
    result["tight_ma_adx"] = (
        tight
        & pd.to_numeric(result["ma_stack_5_20_60"], errors="coerce").eq(1.0)
        & pd.to_numeric(result["di_spread14"], errors="coerce").gt(0.0)
        & pd.to_numeric(result["adx14"], errors="coerce").ge(thresholds["adx14_q50"])
    )
    result["tight_strong_close"] = (
        tight
        & pd.to_numeric(result["directional_clv"], errors="coerce").ge(thresholds["directional_clv_q75"])
        & pd.to_numeric(result["body_ratio"], errors="coerce").ge(thresholds["body_ratio_q50"])
    )
    return result


def _year_rule_rows(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for rule in RULE_ORDER:
        selected = frame[frame[rule].fillna(False)].copy()
        for year, group in selected.groupby("entry_year"):
            all_year = frame[frame["entry_year"].eq(year)]
            positive_total = float(pd.to_numeric(all_year.loc[all_year["r_multiple"] > 0, "r_multiple"], errors="coerce").sum())
            negative_total = float(-pd.to_numeric(all_year.loc[all_year["r_multiple"] < 0, "r_multiple"], errors="coerce").sum())
            positive_selected = float(pd.to_numeric(group.loc[group["r_multiple"] > 0, "r_multiple"], errors="coerce").sum())
            negative_selected = float(-pd.to_numeric(group.loc[group["r_multiple"] < 0, "r_multiple"], errors="coerce").sum())
            gain_share = positive_selected / positive_total if positive_total > 0 else np.nan
            loss_share = negative_selected / negative_total if negative_total > 0 else np.nan
            rows.append(
                {
                    "rule": rule,
                    "entry_year": int(year),
                    "event_count": int(len(group)),
                    "product_count": int(group["product"].nunique()),
                    "r_sum": float(pd.to_numeric(group["r_multiple"], errors="coerce").sum()),
                    "pnl_sum": float(pd.to_numeric(group["realized_pnl"], errors="coerce").sum()),
                    "gain_capture_share": gain_share,
                    "loss_capture_share": loss_share,
                    "gain_minus_loss_share": gain_share - loss_share if np.isfinite(gain_share) and np.isfinite(loss_share) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def composite_rule_summary(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    year_rows = _year_rule_rows(frame)
    total_positive = float(pd.to_numeric(frame.loc[frame["r_multiple"] > 0, "r_multiple"], errors="coerce").sum())
    total_negative = float(-pd.to_numeric(frame.loc[frame["r_multiple"] < 0, "r_multiple"], errors="coerce").sum())
    rows: list[dict[str, Any]] = []
    selected_rule = ""
    for rule in RULE_ORDER:
        selected = frame[frame[rule].fillna(False)].copy()
        years = year_rows[year_rows["rule"].eq(rule)] if not year_rows.empty else pd.DataFrame()
        segment_sums = {
            segment: float(pd.to_numeric(selected.loc[selected["sample_segment"].eq(segment), "r_multiple"], errors="coerce").sum())
            for segment in ("discovery", "validation", "holdout")
        }
        positive_selected = float(pd.to_numeric(selected.loc[selected["r_multiple"] > 0, "r_multiple"], errors="coerce").sum())
        negative_selected = float(-pd.to_numeric(selected.loc[selected["r_multiple"] < 0, "r_multiple"], errors="coerce").sum())
        gain_share = positive_selected / total_positive if total_positive > 0 else np.nan
        loss_share = negative_selected / total_negative if total_negative > 0 else np.nan
        positive_years = int((years["r_sum"] > 0).sum()) if not years.empty else 0
        negative_years = int((years["r_sum"] < 0).sum()) if not years.empty else 0
        year_edge_count = int((years["gain_minus_loss_share"] > 0).sum()) if not years.empty else 0
        positive_by_year = years.loc[years["r_sum"] > 0, "r_sum"] if not years.empty else pd.Series(dtype=float)
        best_year_share = (
            float(positive_by_year.max() / positive_by_year.sum()) if len(positive_by_year) and positive_by_year.sum() > 0 else np.nan
        )
        gates = {
            "event_count_ge40": int(len(selected)) >= 40,
            "product_count_ge5": int(selected["product"].nunique()) >= 5 if not selected.empty else False,
            "direction_count_eq2": int(selected["direction"].nunique()) == 2 if not selected.empty else False,
            "year_count_ge5": int(selected["entry_year"].nunique()) >= 5 if not selected.empty else False,
            "all_segments_positive": all(value > 0.0 for value in segment_sums.values()),
            "positive_years_ge5": positive_years >= 5,
            "negative_years_le1": negative_years <= 1,
            "gain_capture_gt_loss_capture": bool(np.isfinite(gain_share) and np.isfinite(loss_share) and gain_share > loss_share),
            "year_edge_count_ge5": year_edge_count >= 5,
            "best_year_share_le60pct": bool(np.isfinite(best_year_share) and best_year_share <= 0.60),
        }
        passed = all(gates.values())
        if passed and not selected_rule:
            selected_rule = rule
        rows.append(
            {
                "rule": rule,
                "event_count": int(len(selected)),
                "product_count": int(selected["product"].nunique()) if not selected.empty else 0,
                "direction_count": int(selected["direction"].nunique()) if not selected.empty else 0,
                "year_count": int(selected["entry_year"].nunique()) if not selected.empty else 0,
                "r_sum": float(pd.to_numeric(selected["r_multiple"], errors="coerce").sum()) if not selected.empty else 0.0,
                "pnl_sum": float(pd.to_numeric(selected["realized_pnl"], errors="coerce").sum()) if not selected.empty else 0.0,
                "r_mean": float(pd.to_numeric(selected["r_multiple"], errors="coerce").mean()) if not selected.empty else np.nan,
                "winner_rate": float(pd.to_numeric(selected["r_multiple"], errors="coerce").gt(0).mean()) if not selected.empty else np.nan,
                "discovery_r_sum": segment_sums["discovery"],
                "validation_r_sum": segment_sums["validation"],
                "holdout_r_sum": segment_sums["holdout"],
                "positive_years": positive_years,
                "negative_years": negative_years,
                "gain_capture_share": gain_share,
                "loss_capture_share": loss_share,
                "gain_minus_loss_share": gain_share - loss_share if np.isfinite(gain_share) and np.isfinite(loss_share) else np.nan,
                "year_edge_count": year_edge_count,
                "best_positive_year_share": best_year_share,
                **{name: int(value) for name, value in gates.items()},
                "qualification_pass": int(passed),
            }
        )
    return pd.DataFrame(rows), year_rows, selected_rule


def _quartile_boundaries(discovery: pd.Series) -> list[float]:
    values = pd.to_numeric(discovery, errors="coerce").dropna()
    if values.empty:
        return []
    boundaries = [float(values.quantile(value)) for value in (0.0, 0.25, 0.50, 0.75, 1.0)]
    for index in range(1, len(boundaries)):
        if boundaries[index] <= boundaries[index - 1]:
            boundaries[index] = np.nextafter(boundaries[index - 1], np.inf)
    boundaries[0] = -np.inf
    boundaries[-1] = np.inf
    return boundaries


def feature_bin_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    discovery = frame[frame["sample_segment"].eq("discovery")]
    for feature in QUARTILE_FEATURES:
        boundaries = _quartile_boundaries(discovery[feature])
        if not boundaries:
            continue
        bins = pd.cut(
            pd.to_numeric(frame[feature], errors="coerce"),
            bins=boundaries,
            labels=["Q1", "Q2", "Q3", "Q4"],
            include_lowest=True,
        )
        for segment in ("discovery", "validation", "holdout"):
            part = frame[frame["sample_segment"].eq(segment)].copy()
            part["feature_bin"] = bins.loc[part.index]
            for label, group in part.groupby("feature_bin", observed=False):
                values = pd.to_numeric(group["r_multiple"], errors="coerce")
                rows.append(
                    {
                        "feature": feature,
                        "sample_segment": segment,
                        "feature_bin": str(label),
                        "event_count": int(values.notna().sum()),
                        "r_sum": float(values.sum()),
                        "r_mean": float(values.mean()) if values.notna().any() else np.nan,
                        "r_median": float(values.median()) if values.notna().any() else np.nan,
                        "winner_rate": float(values.gt(0).mean()) if values.notna().any() else np.nan,
                        "pnl_sum": float(pd.to_numeric(group["realized_pnl"], errors="coerce").sum()),
                        "boundary_0": boundaries[0],
                        "boundary_25": boundaries[1],
                        "boundary_50": boundaries[2],
                        "boundary_75": boundaries[3],
                        "boundary_100": boundaries[4],
                    }
                )
    return pd.DataFrame(rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax().replace(0.0, np.nan)
    return (values / peak - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    return float(returns.mean() / std * np.sqrt(252.0)) if std > 0 and np.isfinite(std) else 0.0


def summarize_baseline(daily: pd.DataFrame, capital: float) -> dict[str, Any]:
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if frame.empty:
        raise ValueError("baseline daily is empty")
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    drawdown = _drawdown_pct(equity)
    underwater = drawdown.lt(0.0)
    longest = 0
    current = 0
    for value in underwater:
        current = current + 1 if bool(value) else 0
        longest = max(longest, current)
    end_equity = float(equity.iloc[-1])
    elapsed_days = max(1, int((frame["date"].iloc[-1] - frame["date"].iloc[0]).days))
    return {
        "start_date": frame["date"].iloc[0].date().isoformat(),
        "end_date": frame["date"].iloc[-1].date().isoformat(),
        "trading_days": int(len(frame)),
        "capital": float(capital),
        "end_equity": end_equity,
        "total_return_pct": (end_equity / float(capital) - 1.0) * 100.0,
        "cagr_pct": ((end_equity / float(capital)) ** (365.25 / elapsed_days) - 1.0) * 100.0,
        "max_dd_pct": float(drawdown.min()),
        "sharpe": _daily_sharpe(equity),
        "total_slippage": float(pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "nonzero_daily_win_rate_pct": float(
            (equity.pct_change().dropna().loc[lambda series: series.ne(0.0)] > 0).mean() * 100.0
        ),
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(frame.get("broker10_margin_to_equity_pct", 0.0), errors="coerce").fillna(0.0).max()
        ),
        "longest_underwater_trading_days": int(longest),
    }


def drawdown_episodes(daily: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame.sort_values("date", inplace=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    running_peak = equity.cummax()
    drawdown = equity / running_peak.replace(0.0, np.nan) - 1.0
    rows: list[dict[str, Any]] = []
    in_episode = False
    start_idx = 0
    for index, value in enumerate(drawdown.to_numpy(dtype=float)):
        below = np.isfinite(value) and value < -1e-12
        if below and not in_episode:
            in_episode = True
            start_idx = max(0, index - 1)
        is_last = index == len(frame) - 1
        if in_episode and (not below or is_last):
            end_idx = index if not below else index
            episode = frame.iloc[start_idx : end_idx + 1].copy()
            episode_equity = pd.to_numeric(episode["account_equity"], errors="coerce")
            peak_equity = float(episode_equity.iloc[0])
            trough_pos = int(episode_equity.argmin())
            trough_row = episode.iloc[trough_pos]
            peak_date = pd.Timestamp(episode.iloc[0]["date"]).normalize()
            trough_date = pd.Timestamp(trough_row["date"]).normalize()
            recovery_date = pd.Timestamp(episode.iloc[-1]["date"]).normalize() if not below else pd.NaT
            selected = events[
                (pd.to_datetime(events["entry_date"]).dt.normalize() > peak_date)
                & (pd.to_datetime(events["entry_date"]).dt.normalize() <= trough_date)
            ]
            rows.append(
                {
                    "peak_date": peak_date,
                    "trough_date": trough_date,
                    "recovery_date": recovery_date,
                    "peak_equity": peak_equity,
                    "trough_equity": float(trough_row["account_equity"]),
                    "drawdown_pct": (float(trough_row["account_equity"]) / peak_equity - 1.0) * 100.0 if peak_equity else np.nan,
                    "underwater_trading_days": int(len(episode) - 1),
                    "entry_event_count_peak_to_trough": int(len(selected)),
                    "entry_event_pnl_peak_to_trough": float(pd.to_numeric(selected["realized_pnl"], errors="coerce").sum()),
                    "entry_event_r_sum_peak_to_trough": float(pd.to_numeric(selected["r_multiple"], errors="coerce").sum()),
                    "recovered": int(pd.notna(recovery_date)),
                }
            )
            in_episode = False
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values("drawdown_pct", inplace=True)
        result.reset_index(drop=True, inplace=True)
        result.insert(0, "episode_rank", np.arange(1, len(result) + 1))
    return result


def annual_attribution(daily: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    day = daily.copy()
    day["year"] = pd.to_datetime(day["date"], errors="coerce").dt.year
    daily_year = day.groupby("year", as_index=False).agg(
        daily_net_pnl=("net_pnl", "sum"),
        daily_slippage=("slippage", "sum"),
        daily_trade_count=("trade_count", "sum"),
    )
    event_year = events.groupby("entry_year", as_index=False).agg(
        entry_event_count=("open_trade_id", "size"),
        entry_event_pnl=("realized_pnl", "sum"),
        entry_event_r_sum=("r_multiple", "sum"),
        entry_event_winner_rate=("r_multiple", lambda series: float((pd.to_numeric(series, errors="coerce") > 0).mean())),
    )
    event_year.rename(columns={"entry_year": "year"}, inplace=True)
    return daily_year.merge(event_year, on="year", how="outer").sort_values("year").reset_index(drop=True)


def _plot_baseline(daily: pd.DataFrame, annual: pd.DataFrame) -> None:
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    drawdown = _drawdown_pct(equity)
    rolling_return = equity / equity.shift(252) - 1.0
    fig, axes = plt.subplots(2, 2, figsize=(17, 10), constrained_layout=True)
    axes[0, 0].plot(frame["date"], equity, color="#1565c0", linewidth=1.2)
    axes[0, 0].axhline(EXPECTED_CAPITAL, color="#5f6368", linestyle="--", linewidth=0.8)
    axes[0, 0].set_title("Official C9/15w absolute equity")
    axes[0, 0].set_ylabel("equity")
    axes[0, 0].grid(alpha=0.22)
    axes[0, 1].fill_between(frame["date"], drawdown, 0.0, color="#c62828", alpha=0.28)
    axes[0, 1].plot(frame["date"], drawdown, color="#c62828", linewidth=0.8)
    axes[0, 1].set_title("Drawdown from account high-water mark")
    axes[0, 1].set_ylabel("drawdown %")
    axes[0, 1].grid(alpha=0.22)
    axes[1, 0].plot(frame["date"], rolling_return * 100.0, color="#00897b", linewidth=1.0)
    axes[1, 0].axhline(0.0, color="#5f6368", linewidth=0.8)
    axes[1, 0].set_title("Rolling 252-trading-day return")
    axes[1, 0].set_ylabel("return %")
    axes[1, 0].grid(alpha=0.22)
    colors = np.where(pd.to_numeric(annual["daily_net_pnl"], errors="coerce") >= 0, "#2e7d32", "#c62828")
    axes[1, 1].bar(annual["year"].astype(str), annual["daily_net_pnl"], color=colors)
    axes[1, 1].set_title("Annual net PnL")
    axes[1, 1].grid(axis="y", alpha=0.22)
    fig.savefig(BASELINE_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_technical(frame: pd.DataFrame, bins: pd.DataFrame, composites: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(17, 11), constrained_layout=True)
    plot = frame.dropna(subset=["stop_atr14", "r_multiple"]).copy()
    clipped_r = pd.to_numeric(plot["r_multiple"], errors="coerce").clip(-5, 10)
    segment_colors = plot["sample_segment"].map({"discovery": "#1565c0", "validation": "#ef6c00", "holdout": "#2e7d32"})
    axes[0, 0].scatter(plot["stop_atr14"], clipped_r, c=segment_colors, s=18, alpha=0.58)
    axes[0, 0].axhline(0.0, color="#5f6368", linewidth=0.8)
    axes[0, 0].set_xlabel("planned stop / ATR14")
    axes[0, 0].set_ylabel("realized R (clipped -5..10)")
    axes[0, 0].set_title("Stop geometry versus realized outcome")
    axes[0, 0].grid(alpha=0.2)

    stop_bins = bins[(bins["feature"].eq("stop_atr14")) & (bins["sample_segment"].eq("discovery"))]
    axes[0, 1].bar(stop_bins["feature_bin"], stop_bins["r_mean"], color="#5e35b1")
    axes[0, 1].axhline(0.0, color="#5f6368", linewidth=0.8)
    axes[0, 1].set_title("Discovery mean R by stop/ATR quartile")
    axes[0, 1].set_ylabel("mean R")
    axes[0, 1].grid(axis="y", alpha=0.2)

    candidate_long = composites.melt(
        id_vars=["rule"],
        value_vars=["discovery_r_sum", "validation_r_sum", "holdout_r_sum"],
        var_name="segment",
        value_name="segment_r_sum",
    )
    x = np.arange(len(composites))
    width = 0.25
    for index, segment in enumerate(["discovery_r_sum", "validation_r_sum", "holdout_r_sum"]):
        values = candidate_long[candidate_long["segment"].eq(segment)]["segment_r_sum"].to_numpy(dtype=float)
        axes[1, 0].bar(x + (index - 1) * width, values, width=width, label=segment.replace("_r_sum", ""))
    axes[1, 0].axhline(0.0, color="#5f6368", linewidth=0.8)
    axes[1, 0].set_xticks(x, [str(item).replace("tight_", "") for item in composites["rule"]], rotation=18)
    axes[1, 0].set_title("Predeclared tight-stop rule R by segment")
    axes[1, 0].legend()
    axes[1, 0].grid(axis="y", alpha=0.2)

    kline = bins[(bins["feature"].eq("directional_clv")) & (bins["sample_segment"].eq("discovery"))]
    axes[1, 1].bar(kline["feature_bin"], kline["r_mean"], color="#00897b")
    axes[1, 1].axhline(0.0, color="#5f6368", linewidth=0.8)
    axes[1, 1].set_title("Discovery mean R by directional close-location quartile")
    axes[1, 1].set_ylabel("mean R")
    axes[1, 1].grid(axis="y", alpha=0.2)
    fig.savefig(TECHNICAL_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_drawdowns(episodes: pd.DataFrame) -> None:
    top = episodes.head(10).copy()
    if top.empty:
        return
    labels = top["peak_date"].astype(str) + "\n" + top["trough_date"].astype(str)
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), constrained_layout=True)
    axes[0].bar(labels, top["drawdown_pct"], color="#c62828")
    axes[0].set_title("Largest account drawdown episodes")
    axes[0].set_ylabel("drawdown %")
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].grid(axis="y", alpha=0.2)
    colors = np.where(top["entry_event_pnl_peak_to_trough"] >= 0, "#2e7d32", "#ef6c00")
    axes[1].bar(labels, top["entry_event_pnl_peak_to_trough"], color=colors)
    axes[1].set_title("Realized outcome of entries opened from peak to trough")
    axes[1].set_ylabel("event realized PnL")
    axes[1].tick_params(axis="x", rotation=35)
    axes[1].grid(axis="y", alpha=0.2)
    fig.savefig(DRAWDOWN_CHART_PATH, dpi=160)
    plt.close(fig)


def _input_audit(contract_sources: pd.DataFrame) -> pd.DataFrame:
    paths = [
        ("source", Path(s901.__file__)),
        ("source", Path(s719.__file__)),
        ("source", Path(s167.__file__)),
        ("source", Path(__file__)),
        ("history_database", DATABASE_PATH),
        ("official_ai_path_evidence_only_not_feature", Path(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)),
    ]
    rows: list[dict[str, Any]] = []
    for role, path in paths:
        rows.append(
            {
                "role": role,
                "path": str(path),
                "exists": bool(path.exists()),
                "bytes": int(path.stat().st_size) if path.exists() else 0,
                "sha256": _sha256(path) if path.exists() else "",
            }
        )
    if not contract_sources.empty:
        rows.extend(
            {
                "role": "contract_daily_feature_coverage",
                "path": str(row.path),
                "exists": bool(row.exists),
                "bytes": int(row.bytes),
                "sha256": str(row.sha256),
                "vt_symbol": str(row.vt_symbol),
                "bar_count": int(row.bar_count),
                "first_bar_date": row.first_bar_date,
                "last_bar_date": row.last_bar_date,
            }
            for row in contract_sources.itertuples(index=False)
        )
    return pd.DataFrame(rows)


def _feature_usage_audit(events: pd.DataFrame) -> pd.DataFrame:
    allowed = {
        "stop_pct",
        "stop_atr14",
        *TECHNICAL_FEATURE_COLUMNS,
        *RULE_ORDER,
    }
    rows = [
        {
            "field": field,
            "role": "rule_or_attribution_feature",
            "allowed": 1,
            "ai_derived": 0,
            "future_outcome": 0,
        }
        for field in sorted(allowed)
        if field in events.columns
    ]
    rows.extend(
        [
            {"field": "realized_pnl", "role": "outcome_only", "allowed": 0, "ai_derived": 0, "future_outcome": 1},
            {"field": "r_multiple", "role": "outcome_only", "allowed": 0, "ai_derived": 0, "future_outcome": 1},
            {"field": "sample_segment", "role": "evaluation_partition_only", "allowed": 0, "ai_derived": 0, "future_outcome": 0},
        ]
    )
    result = pd.DataFrame(rows)
    if any("ai" in str(field).lower() for field in result.loc[result["allowed"].eq(1), "field"]):
        raise ValueError("AI field leaked into allowed feature usage")
    return result


def _write_report(
    summary: pd.DataFrame,
    aggregation_audit: dict[str, Any],
    coverage: dict[str, Any],
    thresholds: pd.DataFrame,
    composites: pd.DataFrame,
    years: pd.DataFrame,
    annual: pd.DataFrame,
    episodes: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage001 当前主策略基准可视化与纯规则技术归因",
        "",
        "## 外部调研与判断",
        "",
        _md_table(pd.DataFrame(EXTERNAL_RESEARCH)),
        "",
        "我的判断：趋势质量可以影响仓位，但必须与单纯杠杆效应分开。本阶段只做严格 T-1 的价格/止损几何资格审计。",
        "",
        "## 主策略 Fresh Baseline",
        "",
        _md_table(summary),
        "",
        f"- closed-lot 聚合审计：`{json.dumps(_json_safe(aggregation_audit), ensure_ascii=False)}`",
        f"- 特征覆盖审计：`{json.dumps(_json_safe(coverage), ensure_ascii=False)}`",
        "",
        "## Discovery 阈值",
        "",
        _md_table(thresholds),
        "",
        "## 预声明复合规则",
        "",
        _md_table(composites),
        "",
        "## 规则年度分解",
        "",
        _md_table(years, max_rows=60),
        "",
        "## 年度归因",
        "",
        _md_table(annual),
        "",
        "## 最大回撤事件",
        "",
        _md_table(episodes.head(10)),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 资格规则：`{decision.get('selected_rule') or '无'}`。",
        f"- 是否允许 Stage002：`{decision['stage002_allowed']}`。",
        f"- 下一步：{decision['next_step']}",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_before']}",
        f"- 运行后：{decision['overfit_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_before']}",
        f"- 运行后：{decision['continue_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_manifest(paths: list[Path]) -> pd.DataFrame:
    rows = []
    for path in paths:
        rows.append(
            {
                "path": str(path),
                "relative_path": str(path.relative_to(OUT)),
                "bytes": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
        )
    manifest = pd.DataFrame(rows).sort_values("relative_path").reset_index(drop=True)
    manifest.to_csv(MANIFEST_PATH, index=False)
    return manifest


def run_fresh_baseline() -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any, dict[str, Any]]:
    if OFFICIAL_LIVE_VERSION != EXPECTED_VERSION:
        raise RuntimeError(f"official live version drift: {OFFICIAL_LIVE_VERSION}")
    if OFFICIAL_LIVE_PROFILE_NAME != "stage847_c9_15w_stage819_05r_stop_retry_live":
        raise RuntimeError(f"official profile drift: {OFFICIAL_LIVE_PROFILE_NAME}")
    if abs(float(OFFICIAL_LIVE_CAPITAL) - EXPECTED_CAPITAL) > 1e-9:
        raise RuntimeError(f"official capital drift: {OFFICIAL_LIVE_CAPITAL}")
    metadata = s901.s513._metadata()
    combined, frames, spec = s901._run_live_c9(metadata, START, END)
    if combined.empty:
        raise RuntimeError("fresh official baseline returned empty daily curve")
    return combined, frames, spec, metadata


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    database_sha256_before = _sha256(DATABASE_PATH)
    print("[stage001] fresh official baseline start", flush=True)
    daily, frames, spec, metadata = run_fresh_baseline()
    summary_row = summarize_baseline(daily, EXPECTED_CAPITAL)
    summary_row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_profile": OFFICIAL_LIVE_PROFILE_NAME,
        }
    )
    summary = pd.DataFrame([summary_row])

    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame()).copy()
    closed_raw = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    closed_raw = s719._finalize_path_efficiency(closed_raw)
    available = [column for column in SANITIZED_CLOSED_LOT_COLUMNS if column in closed_raw.columns]
    closed = closed_raw.loc[:, available].copy()
    closed, open_lineage, lineage_audit = build_complete_closed_lot_lineage(
        closed,
        trades,
        entry_risk,
        entry_candidates,
        priceticks=metadata.get("priceticks", {}),
    )
    assert_no_ai_features(closed)
    events, aggregation_audit = aggregate_entry_events(closed)
    aggregation_audit["lineage_audit"] = lineage_audit
    if aggregation_audit["inconsistent_group_count"]:
        raise RuntimeError(f"inconsistent partial-close groups: {aggregation_audit['inconsistent_open_trade_ids']}")
    if abs(aggregation_audit["closed_lot_pnl"] - aggregation_audit["entry_event_pnl"]) > 1e-6:
        raise RuntimeError("entry opportunity PnL does not reconcile to all closed lots")
    daily_gross_pnl = float(
        (
            pd.to_numeric(daily["net_pnl"], errors="coerce").fillna(0.0)
            + pd.to_numeric(daily.get("slippage", 0.0), errors="coerce").fillna(0.0)
            + pd.to_numeric(daily.get("commission", 0.0), errors="coerce").fillna(0.0)
        ).sum()
    )
    aggregation_audit["daily_gross_pnl"] = daily_gross_pnl
    aggregation_audit["daily_gross_minus_event_pnl"] = daily_gross_pnl - aggregation_audit["entry_event_pnl"]
    if abs(aggregation_audit["daily_gross_minus_event_pnl"]) > 1e-6:
        raise RuntimeError("entry opportunity PnL does not reconcile to daily gross PnL")
    events, contract_sources = attach_technical_features(events)
    if int(events["feature_future_violation"].sum()) != 0:
        raise RuntimeError("technical feature future-date violation")

    thresholds_dict = discovery_thresholds(events)
    thresholds = pd.DataFrame([thresholds_dict])
    events = apply_composite_rules(events, thresholds_dict)
    assert_no_ai_features(events)
    bins = feature_bin_summary(events)
    composites, composite_years, selected_rule = composite_rule_summary(events)
    annual = annual_attribution(daily, events)
    episodes = drawdown_episodes(daily, events)
    feature_usage = _feature_usage_audit(events)

    core_columns = ["stop_atr14", "efficiency20", "efficiency60", "directional_range_position20", "adx14", "directional_clv", "body_ratio"]
    core_complete = events[core_columns].notna().all(axis=1)
    coverage = {
        "entry_event_count": int(len(events)),
        "core_complete_count": int(core_complete.sum()),
        "core_coverage_ratio": float(core_complete.mean()) if len(events) else 0.0,
        "future_violation_count": int(events["feature_future_violation"].sum()),
        "missing_contract_source_count": int((~contract_sources["exists"]).sum()) if not contract_sources.empty else 0,
        "feature_table_ai_column_count": int(sum("ai" in column.lower() for column in events.columns)),
    }
    selected_row = composites[composites["rule"].eq(selected_rule)].head(1)
    qualification_pass = bool(selected_rule) and coverage["core_coverage_ratio"] >= 0.90
    database_sha256_after = _sha256(DATABASE_PATH)
    if database_sha256_before != database_sha256_after:
        raise RuntimeError("history database changed during Stage001 run")
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "fresh_baseline": True,
        "old_research_result_reused": False,
        "strategy_changed": False,
        "ai_feature_used": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "selected_rule": selected_rule,
        "selected_rule_metrics": selected_row.to_dict("records")[0] if not selected_row.empty else {},
        "core_coverage_ratio": coverage["core_coverage_ratio"],
        "qualification_pass": qualification_pass,
        "stage002_allowed": False,
        "decision": "stage001_pending_independent_review" if qualification_pass else "stage001_no_rule_qualified_pending_independent_review",
        "next_step": (
            "独立 agent 复算；若无影响结果问题且资格门保持通过，再冻结唯一 Stage002 真引擎候选。"
            if qualification_pass
            else "独立 agent 复算；若资格门确认失败，关闭当前四个紧止损规则，不做参数救援。"
        ),
        "overfit_before": "中高但受控；特征族、规则顺序、时间切分和资格门均在结果前冻结。",
        "overfit_after": "待独立 review；本次没有根据结果新增阈值、产品或年份例外。",
        "continue_before": "有；直接验证小止损高质量机会是否真实存在。",
        "continue_after": "待独立 review。",
        "baseline_summary": summary_row,
        "aggregation_audit": aggregation_audit,
        "feature_coverage": coverage,
        "history_database_snapshot_complete": True,
        "history_database_path": str(DATABASE_PATH),
        "history_database_sha256_before": database_sha256_before,
        "history_database_sha256_after": database_sha256_after,
        "history_database_unchanged": database_sha256_before == database_sha256_after,
    }

    daily.to_csv(BASELINE_DAILY_PATH, index=False, compression="gzip")
    summary.to_csv(BASELINE_SUMMARY_PATH, index=False)
    trades.to_csv(BASELINE_TRADES_PATH, index=False, compression="gzip")
    entry_risk.to_csv(BASELINE_ENTRY_RISK_PATH, index=False, compression="gzip")
    entry_candidates.to_csv(BASELINE_ENTRY_CANDIDATES_PATH, index=False, compression="gzip")
    trade_events.to_csv(BASELINE_TRADE_EVENTS_PATH, index=False, compression="gzip")
    stop_retry_events.to_csv(BASELINE_STOP_RETRY_EVENTS_PATH, index=False, compression="gzip")
    closed.to_csv(CLOSED_LOTS_PATH, index=False, compression="gzip")
    open_lineage.to_csv(OPEN_LINEAGE_PATH, index=False, compression="gzip")
    events.to_csv(ENTRY_EVENTS_PATH, index=False, compression="gzip")
    thresholds.to_csv(THRESHOLDS_PATH, index=False)
    bins.to_csv(FEATURE_BIN_SUMMARY_PATH, index=False)
    composites.to_csv(COMPOSITE_SUMMARY_PATH, index=False)
    composite_years.to_csv(COMPOSITE_YEAR_PATH, index=False)
    annual.to_csv(ANNUAL_PATH, index=False)
    episodes.to_csv(DRAWDOWN_EPISODES_PATH, index=False)
    feature_usage.to_csv(FEATURE_USAGE_PATH, index=False)
    input_audit = _input_audit(contract_sources)
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False)
    _plot_baseline(daily, annual)
    _plot_technical(events, bins, composites)
    _plot_drawdowns(episodes)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregation_audit, coverage, thresholds, composites, composite_years, annual, episodes, decision)

    output_paths = [
        BASELINE_DAILY_PATH,
        BASELINE_SUMMARY_PATH,
        BASELINE_TRADES_PATH,
        BASELINE_ENTRY_RISK_PATH,
        BASELINE_ENTRY_CANDIDATES_PATH,
        BASELINE_TRADE_EVENTS_PATH,
        BASELINE_STOP_RETRY_EVENTS_PATH,
        CLOSED_LOTS_PATH,
        OPEN_LINEAGE_PATH,
        ENTRY_EVENTS_PATH,
        THRESHOLDS_PATH,
        FEATURE_BIN_SUMMARY_PATH,
        COMPOSITE_SUMMARY_PATH,
        COMPOSITE_YEAR_PATH,
        ANNUAL_PATH,
        DRAWDOWN_EPISODES_PATH,
        FEATURE_USAGE_PATH,
        INPUT_AUDIT_PATH,
        BASELINE_CHART_PATH,
        TECHNICAL_CHART_PATH,
        DRAWDOWN_CHART_PATH,
        DECISION_PATH,
        REPORT_PATH,
    ]
    _write_manifest([path for path in output_paths if path.exists()])
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

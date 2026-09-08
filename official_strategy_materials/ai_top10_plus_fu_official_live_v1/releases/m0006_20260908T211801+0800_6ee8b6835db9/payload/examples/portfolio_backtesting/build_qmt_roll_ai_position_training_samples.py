from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, SIZES
from run_qmt_alignment_backtest import (
    _build_trade_link_map,
    _match_entry_risk_to_trades,
    _normalize_trade_review_input,
)

PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
DATA_ROOT: Path = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"

ENTRY_RISK_PATH: Path = OUTPUT_DIR / "qmt_roll_entry_risk_diagnostics_2020_2026_04.csv"
TRADES_PATH: Path = OUTPUT_DIR / "qmt_roll_trades_2020_2026_04.csv"

SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_position_training_samples.csv"
SCHEMA_OUTPUT_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_position_training_schema.json"

FORWARD_WINDOWS: tuple[int, ...] = (3, 5, 10, 20)
CROSS_SECTIONAL_FEATURE_COLUMNS: tuple[str, ...] = (
    "feature_ret_signed_5d",
    "feature_mid_term_momentum_signed",
    "feature_close_vs_prev20_high_pct",
    "feature_close_vs_prev20_low_pct",
    "feature_close_position_20d",
    "feature_close_position_60d",
    "feature_volume_ratio_2v2",
    "feature_volume_ratio_1d_20d_zscore_120",
    "feature_oi_delta_1d_pct_zscore_120",
    "feature_atr14_pct_zscore_120",
    "feature_range_pct_zscore_120",
)

BAR_CACHE: dict[str, pd.DataFrame] = {}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _safe_ratio(numerator: float, denominator: float) -> float:
    if abs(denominator) < 1e-12:
        return 0.0
    return float(numerator / denominator)


def _clip(value: float, lower: float, upper: float) -> float:
    return float(min(max(value, lower), upper))


def _series_safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.astype("float64").replace(0.0, float("nan"))
    ratio = numerator.astype("float64").divide(denominator)
    return ratio.replace([math.inf, -math.inf], float("nan"))


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std(ddof=0).replace(0.0, float("nan"))
    zscore = (series - rolling_mean).divide(rolling_std)
    return zscore.replace([math.inf, -math.inf], float("nan"))


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, exchange


def _extract_product_symbol(contract_symbol: str) -> str:
    matched = re.match(r"([A-Za-z]+)", contract_symbol)
    return matched.group(1) if matched else contract_symbol


def _contract_csv_path(vt_symbol: str) -> Path:
    contract_symbol, exchange = _parse_vt_symbol(vt_symbol)
    return DATA_ROOT / exchange / f"{contract_symbol}.csv"


def load_contract_bars(vt_symbol: str) -> pd.DataFrame:
    cached = BAR_CACHE.get(vt_symbol)
    if cached is not None:
        return cached

    csv_path = _contract_csv_path(vt_symbol)
    if not csv_path.exists():
        BAR_CACHE[vt_symbol] = pd.DataFrame()
        return BAR_CACHE[vt_symbol]

    bars_df = pd.read_csv(csv_path)
    if bars_df.empty:
        BAR_CACHE[vt_symbol] = pd.DataFrame()
        return BAR_CACHE[vt_symbol]

    bars_df["date"] = pd.to_datetime(bars_df["trade_date"]).dt.normalize()
    numeric_columns = ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    for column in numeric_columns:
        bars_df[column] = pd.to_numeric(bars_df[column], errors="coerce")
    bars_df.sort_values("date", inplace=True)
    bars_df.drop_duplicates(subset=["date"], keep="last", inplace=True)
    bars_df.reset_index(drop=True, inplace=True)
    BAR_CACHE[vt_symbol] = bars_df
    return bars_df


def _locate_entry_index(bars_df: pd.DataFrame, entry_date: pd.Timestamp) -> int | None:
    if bars_df.empty:
        return None

    matching = bars_df.index[bars_df["date"] == entry_date].tolist()
    if matching:
        return int(matching[0])

    insertion = int(bars_df["date"].searchsorted(entry_date, side="left"))
    if insertion <= 0:
        return None
    return insertion - 1


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    components = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    return components.max(axis=1)


def extract_market_features(
    bars_df: pd.DataFrame,
    *,
    entry_date: pd.Timestamp,
    direction: str,
    signal: str,
    risk_mode: str,
) -> dict[str, Any]:
    entry_index = _locate_entry_index(bars_df, entry_date)
    if entry_index is None or entry_index < 40:
        return {}

    hist = bars_df.iloc[: entry_index + 1].copy()
    close = hist["close"].astype("float64")
    high = hist["high"].astype("float64")
    low = hist["low"].astype("float64")
    volume = hist["volume"].astype("float64")
    open_oi = hist["open_oi"].astype("float64")
    close_oi = hist["close_oi"].astype("float64")

    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    ma40 = close.rolling(40).mean()
    atr14 = _true_range(high, low, close).rolling(14).mean()
    ret1 = close.pct_change(1)
    ret5 = close.pct_change(5)
    ret10 = close.pct_change(10)
    ret20 = close.pct_change(20)
    vol20 = close.pct_change().rolling(20).std(ddof=0)
    vol60 = close.pct_change().rolling(60).std(ddof=0)
    atr14_pct_series = _series_safe_ratio(atr14, close)
    range_pct_series = _series_safe_ratio(high - low, close)
    volume_mean_20_series = volume.rolling(20).mean()
    volume_ratio_1d_20d_series = _series_safe_ratio(volume, volume_mean_20_series)
    oi_delta_1d_pct_series = _series_safe_ratio(close_oi.diff(1), close_oi.shift(1).abs())
    oi_delta_5d_pct_series = _series_safe_ratio(close_oi.diff(5), close_oi.shift(5).abs())
    close_position_20d_series = _series_safe_ratio(
        close - low.rolling(20).min(),
        high.rolling(20).max() - low.rolling(20).min(),
    )
    close_position_60d_series = _series_safe_ratio(
        close - low.rolling(60).min(),
        high.rolling(60).max() - low.rolling(60).min(),
    )

    latest_close = _safe_float(close.iloc[-1])
    latest_high = _safe_float(high.iloc[-1])
    latest_low = _safe_float(low.iloc[-1])
    latest_open_oi = _safe_float(open_oi.iloc[-1])
    latest_close_oi = _safe_float(close_oi.iloc[-1])
    latest_volume = _safe_float(volume.iloc[-1])
    price_range = max(latest_high - latest_low, 0.0)

    previous20_high = _safe_float(high.iloc[-21:-1].max()) if len(high) >= 21 else latest_high
    previous20_low = _safe_float(low.iloc[-21:-1].min()) if len(low) >= 21 else latest_low
    prev_5_close = _safe_float(close.iloc[-6]) if len(close) >= 6 else latest_close
    prev_10_close = _safe_float(close.iloc[-11]) if len(close) >= 11 else latest_close
    prev_close = _safe_float(close.iloc[-2]) if len(close) >= 2 else latest_close
    latest_atr14 = _safe_float(atr14.iloc[-1])
    oi_sum_latest = _safe_float(close_oi.iloc[-1] + close_oi.iloc[-2]) if len(close_oi) >= 2 else latest_close_oi
    oi_sum_prev = _safe_float(close_oi.iloc[-3] + close_oi.iloc[-4]) if len(close_oi) >= 4 else 0.0
    vol_sum_latest = _safe_float(volume.iloc[-1] + volume.iloc[-2]) if len(volume) >= 2 else latest_volume
    vol_sum_prev = _safe_float(volume.iloc[-3] + volume.iloc[-4]) if len(volume) >= 4 else 0.0
    volume_mean_20 = _safe_float(volume.tail(20).mean())
    volume_std_20 = _safe_float(volume.tail(20).std(ddof=0))
    oi_delta_1d = latest_close_oi - _safe_float(close_oi.iloc[-2]) if len(close_oi) >= 2 else 0.0
    oi_delta_5d = latest_close_oi - _safe_float(close_oi.iloc[-6]) if len(close_oi) >= 6 else 0.0

    upper_wick = latest_high - max(latest_close, _safe_float(hist["open"].iloc[-1]))
    lower_wick = min(latest_close, _safe_float(hist["open"].iloc[-1])) - latest_low
    signed_direction = 1.0 if direction == "long" else -1.0

    feature_row: dict[str, Any] = {
        "feature_signal": signal,
        "feature_risk_mode": risk_mode,
        "feature_direction": direction,
        "feature_close": latest_close,
        "feature_ret_1d": _safe_float(ret1.iloc[-1]),
        "feature_ret_5d": _safe_float(ret5.iloc[-1]),
        "feature_ret_10d": _safe_float(ret10.iloc[-1]),
        "feature_ret_20d": _safe_float(ret20.iloc[-1]),
        "feature_ret_signed_5d": signed_direction * _safe_float(ret5.iloc[-1]),
        "feature_trend_ma5_gap_pct": _safe_ratio(latest_close - _safe_float(ma5.iloc[-1]), latest_close),
        "feature_trend_ma10_gap_pct": _safe_ratio(latest_close - _safe_float(ma10.iloc[-1]), latest_close),
        "feature_trend_ma20_gap_pct": _safe_ratio(latest_close - _safe_float(ma20.iloc[-1]), latest_close),
        "feature_ma5_ma10_gap_pct": _safe_ratio(_safe_float(ma5.iloc[-1]) - _safe_float(ma10.iloc[-1]), latest_close),
        "feature_ma10_ma20_gap_pct": _safe_ratio(_safe_float(ma10.iloc[-1]) - _safe_float(ma20.iloc[-1]), latest_close),
        "feature_ma20_ma40_gap_pct": _safe_ratio(_safe_float(ma20.iloc[-1]) - _safe_float(ma40.iloc[-1]), latest_close),
        "feature_ma_alignment_long": float(
            _safe_float(ma5.iloc[-1]) > _safe_float(ma10.iloc[-1]) > _safe_float(ma20.iloc[-1]) > _safe_float(ma40.iloc[-1])
        ),
        "feature_ma_alignment_short": float(
            _safe_float(ma5.iloc[-1]) < _safe_float(ma10.iloc[-1]) < _safe_float(ma20.iloc[-1]) < _safe_float(ma40.iloc[-1])
        ),
        "feature_close_vs_prev20_high_pct": _safe_ratio(latest_close - previous20_high, latest_close),
        "feature_close_vs_prev20_low_pct": _safe_ratio(latest_close - previous20_low, latest_close),
        "feature_atr14_pct": _safe_ratio(latest_atr14, latest_close),
        "feature_range_pct": _safe_ratio(price_range, latest_close),
        "feature_atr14_pct_zscore_120": _safe_float(_rolling_zscore(atr14_pct_series, 120).iloc[-1]),
        "feature_range_pct_zscore_120": _safe_float(_rolling_zscore(range_pct_series, 120).iloc[-1]),
        "feature_ret_20d_zscore_120": _safe_float(_rolling_zscore(ret20, 120).iloc[-1]),
        "feature_upper_wick_pct": _safe_ratio(upper_wick, latest_close),
        "feature_lower_wick_pct": _safe_ratio(lower_wick, latest_close),
        "feature_vol20": _safe_float(vol20.iloc[-1]),
        "feature_vol60": _safe_float(vol60.iloc[-1]),
        "feature_volume_zscore_20": _safe_ratio(latest_volume - volume_mean_20, volume_std_20),
        "feature_volume_ratio_1d_20d": _safe_ratio(latest_volume, volume_mean_20),
        "feature_volume_ratio_1d_20d_zscore_120": _safe_float(_rolling_zscore(volume_ratio_1d_20d_series, 120).iloc[-1]),
        "feature_open_oi": latest_open_oi,
        "feature_close_oi": latest_close_oi,
        "feature_oi_delta_1d": oi_delta_1d,
        "feature_oi_delta_5d": oi_delta_5d,
        "feature_oi_delta_1d_pct": _safe_float(oi_delta_1d_pct_series.iloc[-1]),
        "feature_oi_delta_5d_pct": _safe_float(oi_delta_5d_pct_series.iloc[-1]),
        "feature_oi_delta_1d_pct_zscore_120": _safe_float(_rolling_zscore(oi_delta_1d_pct_series, 120).iloc[-1]),
        "feature_oi_ratio_2v2": _safe_ratio(oi_sum_latest, oi_sum_prev),
        "feature_volume_ratio_2v2": _safe_ratio(vol_sum_latest, vol_sum_prev),
        "feature_volume_oi_surge_flag": float(
            vol_sum_prev > 0.0 and oi_sum_prev > 0.0 and vol_sum_latest > vol_sum_prev * 2.0 and oi_sum_latest > oi_sum_prev
        ),
        "feature_close_position_20d": _safe_float(close_position_20d_series.iloc[-1]),
        "feature_close_position_60d": _safe_float(close_position_60d_series.iloc[-1]),
        "feature_signal_strength_signed": signed_direction * _safe_ratio(latest_close - prev_5_close, prev_5_close),
        "feature_reversal_pressure_signed": signed_direction * _safe_ratio(latest_close - prev_close, prev_close),
        "feature_mid_term_momentum_signed": signed_direction * _safe_ratio(latest_close - prev_10_close, prev_10_close),
    }
    return feature_row


def _position_direction_from_entry_trade(entry_trade: dict[str, Any]) -> str:
    return "long" if str(entry_trade["direction"]) == "Long" else "short"


def build_label_row(
    *,
    entry_trade_id: str,
    entry_trade_row: dict[str, Any],
    linked_exit_rows: list[dict[str, Any]],
    risk_row: dict[str, Any],
    bars_df: pd.DataFrame,
) -> dict[str, Any]:
    entry_price = _safe_float(entry_trade_row["price"])
    entry_volume = _safe_float(entry_trade_row["volume"])
    contract_size = _safe_float(SIZES.get(str(risk_row["product_vt_symbol"]), 0.0), 1.0)
    entry_date = pd.Timestamp(entry_trade_row["date"]).normalize()
    direction = _position_direction_from_entry_trade(entry_trade_row)
    direction_sign = 1.0 if direction == "long" else -1.0
    stop_distance = max(_safe_float(risk_row.get("stop_distance")), 1e-9)
    actual_risk_amount = max(_safe_float(risk_row.get("actual_risk_amount")), 1e-9)

    if linked_exit_rows:
        exit_df = pd.DataFrame(linked_exit_rows).sort_values(["datetime", "trade_id"])
        exit_price_weighted = _safe_ratio(
            float((pd.to_numeric(exit_df["price"], errors="coerce") * pd.to_numeric(exit_df["volume"], errors="coerce")).sum()),
            float(pd.to_numeric(exit_df["volume"], errors="coerce").sum()),
        )
        exit_date = pd.Timestamp(exit_df["date"].iloc[-1]).normalize()
        closed_volume = _safe_float(exit_df["volume"].sum())
    else:
        exit_price_weighted = entry_price
        exit_date = entry_date
        closed_volume = entry_volume

    realized_price_move = direction_sign * (exit_price_weighted - entry_price)
    realized_pnl_amount = realized_price_move * closed_volume * contract_size
    realized_return_pct = _safe_ratio(realized_price_move, entry_price)
    realized_r_multiple = _safe_ratio(realized_pnl_amount, actual_risk_amount)
    holding_days = int(max((exit_date - entry_date).days, 0))

    entry_index = _locate_entry_index(bars_df, entry_date)
    exit_index = _locate_entry_index(bars_df, exit_date)
    if entry_index is None:
        return {}
    if exit_index is None or exit_index < entry_index:
        exit_index = entry_index

    path_df = bars_df.iloc[entry_index : exit_index + 1].copy()
    if path_df.empty:
        path_df = bars_df.iloc[entry_index : entry_index + 1].copy()

    max_high = _safe_float(path_df["high"].max(), entry_price)
    min_low = _safe_float(path_df["low"].min(), entry_price)
    if direction == "long":
        mfe_price = max_high - entry_price
        mae_price = entry_price - min_low
    else:
        mfe_price = entry_price - min_low
        mae_price = max_high - entry_price

    label_row: dict[str, Any] = {
        "label_entry_trade_id": entry_trade_id,
        "label_exit_trade_count": len(linked_exit_rows),
        "label_closed_volume": closed_volume,
        "label_exit_price_weighted": exit_price_weighted,
        "label_exit_date": exit_date.date().isoformat(),
        "label_holding_days": holding_days,
        "label_realized_pnl_amount": realized_pnl_amount,
        "label_realized_return_pct": realized_return_pct,
        "label_realized_r_multiple": realized_r_multiple,
        "label_stop_distance_pct": _safe_ratio(stop_distance, entry_price),
        "label_mfe_pct_until_exit": _safe_ratio(mfe_price, entry_price),
        "label_mae_pct_until_exit": _safe_ratio(mae_price, entry_price),
        "label_mfe_r_until_exit": _safe_ratio(mfe_price, stop_distance),
        "label_mae_r_until_exit": _safe_ratio(mae_price, stop_distance),
    }

    if entry_index is not None:
        for forward_window in FORWARD_WINDOWS:
            forward_index = min(entry_index + forward_window, len(bars_df) - 1)
            forward_close = _safe_float(bars_df.iloc[forward_index]["close"], entry_price)
            signed_forward_return = direction_sign * _safe_ratio(forward_close - entry_price, entry_price)
            label_row[f"label_forward_{forward_window}d_return_pct"] = signed_forward_return
            label_row[f"label_forward_{forward_window}d_r_multiple"] = _safe_ratio(forward_close - entry_price, stop_distance) * direction_sign

        lookahead_df = bars_df.iloc[entry_index : min(entry_index + 20, len(bars_df) - 1) + 1]
        lookahead_high = _safe_float(lookahead_df["high"].max(), entry_price)
        lookahead_low = _safe_float(lookahead_df["low"].min(), entry_price)
        if direction == "long":
            lookahead_mfe = lookahead_high - entry_price
            lookahead_mae = entry_price - lookahead_low
        else:
            lookahead_mfe = entry_price - lookahead_low
            lookahead_mae = lookahead_high - entry_price
        label_row["label_20d_mfe_r"] = _safe_ratio(lookahead_mfe, stop_distance)
        label_row["label_20d_mae_r"] = _safe_ratio(lookahead_mae, stop_distance)

    quality_score = (
        0.45 * label_row.get("label_realized_r_multiple", 0.0)
        + 0.35 * label_row.get("label_20d_mfe_r", 0.0)
        - 0.20 * label_row.get("label_20d_mae_r", 0.0)
    )
    quality_score_v2 = (
        0.35 * _clip(label_row.get("label_realized_r_multiple", 0.0), -3.0, 5.0)
        + 0.20 * _clip(label_row.get("label_forward_10d_r_multiple", 0.0), -3.0, 4.0)
        + 0.25 * _clip(label_row.get("label_forward_20d_r_multiple", 0.0), -3.0, 5.0)
        + 0.20
        * (
            _clip(label_row.get("label_20d_mfe_r", 0.0), 0.0, 6.0)
            - _clip(label_row.get("label_20d_mae_r", 0.0), 0.0, 4.0)
        )
    )
    label_row["label_quality_score"] = quality_score
    label_row["label_quality_score_v2"] = quality_score_v2
    if quality_score >= 1.5:
        label_row["label_size_bucket"] = "large"
    elif quality_score >= 0.5:
        label_row["label_size_bucket"] = "normal"
    else:
        label_row["label_size_bucket"] = "small"
    if quality_score_v2 >= 1.0:
        label_row["label_size_bucket_v2"] = "large"
    elif quality_score_v2 >= 0.0:
        label_row["label_size_bucket_v2"] = "normal"
    else:
        label_row["label_size_bucket_v2"] = "small"
    return label_row


def build_training_samples() -> pd.DataFrame:
    entry_risk_df = pd.read_csv(ENTRY_RISK_PATH)
    trades_df = pd.read_csv(TRADES_PATH)

    normalized_trades = _normalize_trade_review_input(trades_df, "datetime")
    normalized_risks = _normalize_trade_review_input(entry_risk_df, "datetime")
    risk_by_trade_id = _match_entry_risk_to_trades(normalized_trades, normalized_risks)
    trade_link_map = _build_trade_link_map(normalized_trades)
    trade_row_by_id = {str(row["trade_id"]): row for row in normalized_trades.to_dict("records")}

    open_trades = normalized_trades[normalized_trades["offset"] == "Open"].copy()
    open_trades.sort_values(["datetime", "vt_symbol", "trade_id"], inplace=True)

    sample_rows: list[dict[str, Any]] = []
    for open_trade in open_trades.to_dict("records"):
        entry_trade_id = str(open_trade["trade_id"])
        risk_row = risk_by_trade_id.get(entry_trade_id)
        if risk_row is None:
            continue

        vt_symbol = str(open_trade["vt_symbol"])
        bars_df = load_contract_bars(vt_symbol)
        if bars_df.empty:
            continue

        direction = _position_direction_from_entry_trade(open_trade)
        signal = str(risk_row.get("signal", ""))
        risk_mode = str(risk_row.get("risk_mode", ""))
        entry_date = pd.Timestamp(open_trade["date"]).normalize()

        feature_row = extract_market_features(
            bars_df,
            entry_date=entry_date,
            direction=direction,
            signal=signal,
            risk_mode=risk_mode,
        )
        if not feature_row:
            continue

        trade_link = trade_link_map.get(entry_trade_id, {})
        linked_exit_ids = [str(item) for item in trade_link.get("exit_trade_ids", [])]
        linked_exit_rows = [trade_row_by_id[item] for item in linked_exit_ids if item in trade_row_by_id]
        label_row = build_label_row(
            entry_trade_id=entry_trade_id,
            entry_trade_row=open_trade,
            linked_exit_rows=linked_exit_rows,
            risk_row=risk_row,
            bars_df=bars_df,
        )
        if not label_row:
            continue

        sample_row: dict[str, Any] = {
            "sample_id": entry_trade_id,
            "entry_trade_id": entry_trade_id,
            "entry_datetime": pd.Timestamp(open_trade["datetime"]).isoformat(),
            "entry_date": entry_date.date().isoformat(),
            "product_vt_symbol": str(risk_row.get("product_vt_symbol", "")),
            "contract_vt_symbol": str(risk_row.get("contract_vt_symbol", vt_symbol)),
            "exchange": _parse_vt_symbol(vt_symbol)[1],
            "contract_symbol": _parse_vt_symbol(vt_symbol)[0],
            "product_symbol": _extract_product_symbol(_parse_vt_symbol(vt_symbol)[0]),
            "direction": direction,
            "signal": signal,
            "risk_mode": risk_mode,
            "layer_kind": str(risk_row.get("layer_kind", "")),
            "sizing_method": str(risk_row.get("sizing_method", "")),
            "entry_price": _safe_float(open_trade.get("price")),
            "entry_volume": _safe_float(open_trade.get("volume")),
            "contract_size": _safe_float(SIZES.get(str(risk_row.get("product_vt_symbol", "")), 0.0), 1.0),
            "stop_price": _safe_float(risk_row.get("stop_price")),
            "stop_distance": _safe_float(risk_row.get("stop_distance")),
            "risk_ratio": _safe_float(risk_row.get("risk_ratio")),
            "risk_multiplier": _safe_float(risk_row.get("risk_multiplier")),
            "actual_risk_amount": _safe_float(risk_row.get("actual_risk_amount")),
            "actual_margin_amount": _safe_float(risk_row.get("actual_margin_amount")),
            "estimated_equity": _safe_float(risk_row.get("estimated_equity")),
            "allowed_capital": _safe_float(risk_row.get("allowed_capital")),
            "single_trade_capital_limit": _safe_float(risk_row.get("single_trade_capital_limit")),
            "loss_streak": int(_safe_float(risk_row.get("loss_streak"))),
            "feature_source": "entry_risk_diagnostics + local_daily_csv",
        }
        estimated_equity = sample_row["estimated_equity"]
        entry_notional = sample_row["entry_price"] * sample_row["entry_volume"] * sample_row["contract_size"]
        sample_row["feature_stop_distance_pct"] = _safe_ratio(sample_row["stop_distance"], sample_row["entry_price"])
        sample_row["feature_actual_risk_to_equity"] = _safe_ratio(sample_row["actual_risk_amount"], estimated_equity)
        sample_row["feature_actual_margin_to_equity"] = _safe_ratio(sample_row["actual_margin_amount"], estimated_equity)
        sample_row["feature_allowed_capital_to_equity"] = _safe_ratio(sample_row["allowed_capital"], estimated_equity)
        sample_row["feature_single_trade_capital_limit_to_equity"] = _safe_ratio(
            sample_row["single_trade_capital_limit"], estimated_equity
        )
        sample_row["feature_entry_notional"] = entry_notional
        sample_row["feature_entry_notional_to_equity"] = _safe_ratio(entry_notional, estimated_equity)
        sample_row.update(feature_row)
        sample_row.update(label_row)
        sample_rows.append(sample_row)

    samples_df = pd.DataFrame(sample_rows)
    samples_df.sort_values(["entry_datetime", "entry_trade_id"], inplace=True)
    samples_df.reset_index(drop=True, inplace=True)
    samples_df = add_cross_sectional_relative_columns(samples_df)
    return samples_df


def add_cross_sectional_relative_columns(samples_df: pd.DataFrame) -> pd.DataFrame:
    if samples_df.empty:
        return samples_df

    enriched_df = samples_df.copy()
    group_size = enriched_df.groupby("entry_date")["sample_id"].transform("count").astype("float64")
    enriched_df["feature_cross_section_count_1d"] = group_size

    for column in CROSS_SECTIONAL_FEATURE_COLUMNS:
        if column not in enriched_df.columns:
            continue
        rank_pct = (
            enriched_df.groupby("entry_date")[column]
            .rank(method="average")
            .astype("float64")
        )
        normalized_rank = pd.Series(0.5, index=enriched_df.index, dtype="float64")
        mask = group_size > 1
        normalized_rank.loc[mask] = (rank_pct.loc[mask] - 1.0) / (group_size.loc[mask] - 1.0)
        enriched_df[f"{column}_cs_rank_pct_1d"] = normalized_rank
        enriched_df[f"{column}_cs_rank_centered_1d"] = (normalized_rank - 0.5) * 2.0

    quality_rank = (
        enriched_df.groupby("entry_date")["label_quality_score_v2"]
        .rank(method="average")
        .astype("float64")
    )
    quality_rank_pct = pd.Series(0.5, index=enriched_df.index, dtype="float64")
    mask = group_size > 1
    quality_rank_pct.loc[mask] = (quality_rank.loc[mask] - 1.0) / (group_size.loc[mask] - 1.0)
    quality_rank_centered = (quality_rank_pct - 0.5) * 2.0
    quality_v2_clipped = enriched_df["label_quality_score_v2"].clip(-3.0, 3.0) / 3.0
    quality_score_v3 = 0.65 * quality_rank_centered + 0.35 * quality_v2_clipped

    enriched_df["label_cross_section_count_1d"] = group_size
    enriched_df["label_quality_score_v2_rank_pct_1d"] = quality_rank_pct
    enriched_df["label_quality_score_v2_rank_centered_1d"] = quality_rank_centered
    enriched_df["label_quality_score_v3"] = quality_score_v3
    enriched_df["label_quality_score_v3_is_cross_sectional"] = (group_size > 1).astype(float)
    enriched_df["label_quality_score_v3_bucket"] = "normal"
    enriched_df.loc[quality_score_v3 >= 0.25, "label_quality_score_v3_bucket"] = "large"
    enriched_df.loc[quality_score_v3 <= -0.25, "label_quality_score_v3_bucket"] = "small"
    return enriched_df


def build_schema(samples_df: pd.DataFrame) -> dict[str, Any]:
    categorical_columns = [
        column
        for column in samples_df.columns
        if column
        in {
            "product_vt_symbol",
            "contract_vt_symbol",
            "exchange",
            "contract_symbol",
            "product_symbol",
            "direction",
            "signal",
            "risk_mode",
            "layer_kind",
            "sizing_method",
            "feature_signal",
            "feature_risk_mode",
            "feature_direction",
            "label_size_bucket",
            "label_size_bucket_v2",
            "label_quality_score_v3_bucket",
        }
    ]
    numeric_columns = [
        column
        for column in samples_df.columns
        if column not in categorical_columns and column not in {"sample_id", "entry_trade_id", "entry_datetime", "entry_date", "label_exit_date", "feature_source"}
    ]
    return {
        "dataset_name": "qmt_roll_ai_position_training_samples",
        "row_definition": "每一行对应一笔规则策略已触发并实际成交的开仓交易（Open trade）。",
        "target_recommendation": {
            "primary_regression_label": "label_quality_score_v3",
            "alternative_regression_labels": [
                "label_quality_score_v2",
                "label_quality_score",
                "label_quality_score_v2_rank_centered_1d",
            ],
            "classification_label": "label_quality_score_v3_bucket",
        },
        "categorical_columns": categorical_columns,
        "numeric_columns": numeric_columns,
        "feature_prefixes": ["feature_"],
        "label_prefixes": ["label_"],
        "notes": [
            "推荐先做离线 quality_score 回归，再将模型输出映射到 0.7x/1.0x/1.2x 仓位倍率。",
            "所有特征均限制为开仓当日可观测数据，不使用未来信息。",
            "v2 标签使用截断后的 realized/forward/MFE/MAE 复合分数，目标是降低单笔噪声和极端值影响。",
            "v3 标签进一步引入同日横截面相对排名，避免模型只学习绝对分数而忽略同批候选之间的优先级。",
            "若后续引入更长周期或跨品种特征，可在 extract_market_features() 中继续扩展。",
        ],
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples_df = build_training_samples()
    samples_df.to_csv(SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    schema = build_schema(samples_df)
    SCHEMA_OUTPUT_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ai-samples] rows: {len(samples_df)}")
    print(f"[ai-samples] samples csv: {SAMPLES_OUTPUT_PATH}")
    print(f"[ai-samples] schema json: {SCHEMA_OUTPUT_PATH}")
    if not samples_df.empty:
        preview_columns = [
            "entry_date",
            "product_symbol",
            "direction",
            "signal",
            "risk_mode",
            "feature_atr14_pct",
            "feature_ret_20d_zscore_120",
            "feature_volume_ratio_2v2",
            "label_realized_r_multiple",
            "label_quality_score",
            "label_quality_score_v2",
            "label_quality_score_v3",
            "label_quality_score_v3_bucket",
        ]
        preview_columns = [column for column in preview_columns if column in samples_df.columns]
        print(samples_df[preview_columns].head(10).to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


class DirectionProxyError(ValueError):
    pass


@dataclass(frozen=True)
class DirectionSettings:
    ma_short: int = 5
    ma_mid: int = 10
    ma_long: int = 20
    ma_extra_long: int = 40
    exact_am_size: int = 41
    long_entry_enabled: bool = True
    short_entry_enabled: bool = True
    rollover_reopen_enabled: bool = True
    reverse_on_opposite_signal: bool = False
    ma5_extreme_filter_enabled: bool = True
    ma5_extreme_compare_days: int = 3
    ma5_angle_reversal_filter_enabled: bool = False
    ma5_angle_reversal_lookback_days: int = 10
    ma5_angle_reversal_angle_threshold_deg: float = 45.0
    short_ma5_slope_filter_enabled: bool = True
    wick_chop_filter_enabled: bool = True
    wick_chop_filter_lookback: int = 10
    wick_chop_filter_max_days: int = 5
    enable_rsi_filter: bool = False
    rsi_length: int = 6
    donchian_entry_period: int = 20

    @property
    def ma_periods(self) -> tuple[int, int, int, int]:
        return (self.ma_short, self.ma_mid, self.ma_long, self.ma_extra_long)


@dataclass(frozen=True)
class HistorySelection:
    observable: bool
    reason: str
    history: pd.DataFrame
    available_bar_count: int
    post_query_bar_usage_count: int = 0
    flat_fill_bar_usage_count: int = 0


REQUIRED_BAR_COLUMNS = ("trade_date", "open", "high", "low", "close")


def prepare_contract_bars(raw: pd.DataFrame, vt_symbol: str) -> pd.DataFrame:
    missing = sorted(set(REQUIRED_BAR_COLUMNS) - set(raw.columns))
    if missing:
        raise DirectionProxyError(f"raw_bar_columns_missing:{vt_symbol}:{','.join(missing)}")

    frame = raw.loc[:, REQUIRED_BAR_COLUMNS].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    if frame["trade_date"].isna().any():
        raise DirectionProxyError(f"raw_bar_date_invalid:{vt_symbol}")
    if frame["trade_date"].duplicated().any():
        raise DirectionProxyError(f"raw_bar_date_duplicate:{vt_symbol}")
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.sort_values("trade_date", kind="mergesort").reset_index(drop=True)
    frame.attrs["vt_symbol"] = str(vt_symbol)
    return frame


def _validate_used_ohlc(history: pd.DataFrame, vt_symbol: str) -> None:
    values = history[["open", "high", "low", "close"]].to_numpy(dtype=float)
    finite_positive = np.isfinite(values).all(axis=1) & (values > 0).all(axis=1)
    open_ = values[:, 0]
    high = values[:, 1]
    low = values[:, 2]
    close = values[:, 3]
    envelope = (high >= np.maximum(open_, close)) & (low <= np.minimum(open_, close)) & (high >= low)
    if not bool(np.all(finite_positive & envelope)):
        raise DirectionProxyError(f"used_ohlc_invalid:{vt_symbol}")


def select_am_history(
    prepared: pd.DataFrame,
    query_date: Any,
    *,
    size: int = 41,
) -> HistorySelection:
    query = pd.Timestamp(query_date).normalize()
    vt_symbol = str(prepared.attrs.get("vt_symbol", "unknown"))
    available = prepared.loc[prepared["trade_date"].le(query)].copy()
    count = int(len(available))
    if available.empty or pd.Timestamp(available["trade_date"].iloc[-1]) != query:
        return HistorySelection(False, "query_date_real_bar_missing", available.tail(size), count)
    if count < int(size):
        return HistorySelection(False, "insufficient_observed_bars", available.copy(), count)

    history = available.tail(int(size)).reset_index(drop=True)
    if bool(history["trade_date"].gt(query).any()):
        raise DirectionProxyError(f"post_query_bar_used:{vt_symbol}:{query.date().isoformat()}")
    _validate_used_ohlc(history, vt_symbol)
    return HistorySelection(True, "", history, count)


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=9, adjust=False).mean()
    return dif, dea, (dif - dea) * 2


def _latest_ma_extreme(history: pd.DataFrame, period: int, compare_days: int, mode: str) -> bool:
    close = pd.to_numeric(history["close"], errors="coerce")
    ma = close.rolling(window=max(int(period), 1)).mean().dropna()
    compare = max(int(compare_days), 1)
    if len(ma) < compare:
        return False
    recent = [float(value) for value in ma.iloc[-compare:].tolist() if pd.notna(value)]
    if len(recent) < compare:
        return False
    latest = recent[-1]
    if compare >= 3:
        prev1 = recent[-2]
        prev2 = recent[-3]
        if mode == "min":
            return not ((prev1 < latest) and (prev2 < prev1))
        return not ((prev1 > latest) and (prev2 > prev1))
    if mode == "min":
        return latest <= min(recent)
    return latest >= max(recent)


def _ma_slope(history: pd.DataFrame, period: int) -> float:
    close = pd.to_numeric(history["close"], errors="coerce")
    ma = close.rolling(window=int(period)).mean()
    if len(ma) < 2 or pd.isna(ma.iloc[-1]) or pd.isna(ma.iloc[-2]):
        return 0.0
    return float(ma.iloc[-1] - ma.iloc[-2])


def _wick_filter(history: pd.DataFrame, lookback: int, max_days: int) -> tuple[bool, int]:
    count_window = max(int(lookback), 1)
    frame = history[["open", "high", "low", "close"]].tail(count_window).dropna()
    if len(frame) < count_window:
        return True, 0
    count = 0
    for row in frame.itertuples(index=False):
        body = abs(float(row.close) - float(row.open))
        upper = float(row.high) - max(float(row.open), float(row.close))
        lower = min(float(row.open), float(row.close)) - float(row.low)
        if upper > body or lower > body:
            count += 1
    return count <= int(max_days), count


def _simple_ma_trend(history: pd.DataFrame, direction: str, settings: DirectionSettings) -> bool:
    slope_lookback = 3
    need = settings.ma_extra_long + slope_lookback + 2
    if len(history) < need:
        return False
    close = pd.to_numeric(history["close"], errors="coerce")
    close_last = float(close.iloc[-1])
    short = float(close.rolling(settings.ma_short).mean().iloc[-1])
    mid = float(close.rolling(settings.ma_mid).mean().iloc[-1])
    long = float(close.rolling(settings.ma_long).mean().iloc[-1])
    extra = float(close.rolling(settings.ma_extra_long).mean().iloc[-1])
    long_prev = float(close.rolling(settings.ma_long).mean().iloc[-1 - slope_lookback])
    if direction == "long":
        return short > mid > long > extra and long > long_prev and close_last > long
    return short < mid < long < extra and long < long_prev and close_last < long


def _manual_filter_details(
    history: pd.DataFrame,
    direction: str,
    settings: DirectionSettings,
) -> dict[str, Any]:
    extreme_pass = True
    if settings.ma5_extreme_filter_enabled:
        extreme_pass = _latest_ma_extreme(
            history,
            settings.ma_short,
            settings.ma5_extreme_compare_days,
            "max" if direction == "long" else "min",
        )

    slope = _ma_slope(history, settings.ma_short)
    slope_pass = not (
        direction == "short" and settings.short_ma5_slope_filter_enabled and slope > 0
    )

    simple_trend = _simple_ma_trend(history, direction, settings)
    wick_pass, wick_count = _wick_filter(
        history,
        settings.wick_chop_filter_lookback,
        settings.wick_chop_filter_max_days,
    )
    if not settings.wick_chop_filter_enabled or simple_trend:
        wick_pass = True

    return {
        "extreme_filter_pass": bool(extreme_pass),
        "ma5_slope": float(slope),
        "slope_filter_pass": bool(slope_pass),
        "simple_ma_trend": bool(simple_trend),
        "wick_filter_pass": bool(wick_pass),
        "wick_count": int(wick_count),
        "entry_filters_pass": bool(extreme_pass and slope_pass and wick_pass),
    }


def _manual_direction(history: pd.DataFrame, settings: DirectionSettings) -> dict[str, Any]:
    if len(history) != settings.exact_am_size:
        raise DirectionProxyError(f"am_history_size_mismatch:{len(history)}")
    close = pd.to_numeric(history["close"], errors="coerce")
    ma_values = [float(close.rolling(period).mean().iloc[-1]) for period in settings.ma_periods]
    bullish = bool(ma_values[0] > ma_values[1] > ma_values[2] > ma_values[3])
    bearish = bool(ma_values[0] < ma_values[1] < ma_values[2] < ma_values[3])
    _, _, hist = _macd(close)
    macd_hist = float(hist.iloc[-1])
    long_filters = _manual_filter_details(history, "long", settings)
    short_filters = _manual_filter_details(history, "short", settings)
    long_allowed = bool(
        settings.long_entry_enabled and bullish and macd_hist > 0 and long_filters["entry_filters_pass"]
    )
    short_allowed = bool(
        settings.short_entry_enabled and bearish and macd_hist < 0 and short_filters["entry_filters_pass"]
    )
    if long_allowed and short_allowed:
        raise DirectionProxyError("direction_proxy_double_true")
    direction = 1 if long_allowed else -1 if short_allowed else 0
    return {
        "ma5": ma_values[0],
        "ma10": ma_values[1],
        "ma20": ma_values[2],
        "ma40": ma_values[3],
        "bullish_alignment": bullish,
        "bearish_alignment": bearish,
        "macd_hist": macd_hist,
        "long_allowed": long_allowed,
        "short_allowed": short_allowed,
        "direction_proxy": direction,
        **{f"long_{key}": value for key, value in long_filters.items()},
        **{f"short_{key}": value for key, value in short_filters.items()},
    }


def _formal_direction(history: pd.DataFrame, settings: DirectionSettings) -> tuple[bool, bool]:
    from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import (
        QmtRollPortfolioStrategyStage847C9StopRetry,
    )
    from vnpy.trader.constant import Exchange, Interval
    from vnpy.trader.object import BarData
    from vnpy.trader.utility import ArrayManager

    strategy = object.__new__(QmtRollPortfolioStrategyStage847C9StopRetry)
    for name, value in vars(settings).items():
        if name == "exact_am_size":
            continue
        setattr(strategy, name, value)

    vt_symbol = str(history.attrs.get("vt_symbol", "rb.SHFE"))
    try:
        symbol, exchange_code = vt_symbol.rsplit(".", 1)
        exchange = Exchange(exchange_code)
    except (ValueError, TypeError) as exc:
        raise DirectionProxyError(f"formal_oracle_vt_symbol_invalid:{vt_symbol}") from exc

    formal_history = history.copy()
    formal_history["volume"] = 0.0
    formal_history["open_interest"] = 0.0
    am = ArrayManager(settings.exact_am_size)
    for row in formal_history.itertuples(index=False):
        am.update_bar(
            BarData(
                gateway_name="stage001_direction_oracle",
                symbol=symbol,
                exchange=exchange,
                datetime=pd.Timestamp(row.trade_date).to_pydatetime(),
                interval=Interval.DAILY,
                open_price=float(row.open),
                high_price=float(row.high),
                low_price=float(row.low),
                close_price=float(row.close),
                volume=float(row.volume),
                open_interest=float(row.open_interest),
            )
        )

    signal_data = strategy._generate_signal(am, formal_history)
    long_allowed = bool(strategy._rollover_reopen_allowed("long", formal_history, signal_data))
    short_allowed = bool(strategy._rollover_reopen_allowed("short", formal_history, signal_data))
    return long_allowed, short_allowed


def evaluate_direction_proxy(
    prepared: pd.DataFrame,
    query_date: Any,
    settings: DirectionSettings | None = None,
) -> dict[str, Any]:
    settings = settings or DirectionSettings()
    selected = select_am_history(prepared, query_date, size=settings.exact_am_size)
    base: dict[str, Any] = {
        "proxy_observable": bool(selected.observable),
        "proxy_unobservable_reason": selected.reason,
        "available_bar_count": selected.available_bar_count,
        "history_first_date": (
            pd.Timestamp(selected.history["trade_date"].iloc[0]).date().isoformat()
            if not selected.history.empty
            else ""
        ),
        "history_last_date": (
            pd.Timestamp(selected.history["trade_date"].iloc[-1]).date().isoformat()
            if not selected.history.empty
            else ""
        ),
        "post_query_bar_usage_count": selected.post_query_bar_usage_count,
        "flat_fill_bar_usage_count": selected.flat_fill_bar_usage_count,
    }
    if not selected.observable:
        return {
            **base,
            "direction_proxy": None,
            "long_allowed": None,
            "short_allowed": None,
            "formula_mismatch": False,
        }

    manual = _manual_direction(selected.history, settings)
    formal_long, formal_short = _formal_direction(selected.history, settings)
    mismatch = bool(
        formal_long != manual["long_allowed"] or formal_short != manual["short_allowed"]
    )
    return {
        **base,
        **manual,
        "formal_oracle_class": (
            "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine."
            "QmtRollPortfolioStrategyStage847C9StopRetry"
        ),
        "formal_long_allowed": formal_long,
        "formal_short_allowed": formal_short,
        "formula_mismatch": mismatch,
    }


def build_cost_metadata(
    products: Sequence[str],
    product_metadata: pd.DataFrame,
    *,
    rates: Mapping[str, float],
    slippages: Mapping[str, float],
    sizes: Mapping[str, int],
    priceticks: Mapping[str, float],
) -> pd.DataFrame:
    metadata = product_metadata.copy()
    if "symbol_kind" in metadata.columns:
        metadata = metadata.loc[metadata["symbol_kind"].astype(str).eq("product_cont")].copy()
    if "vt_symbol" not in metadata.columns or metadata["vt_symbol"].duplicated().any():
        raise DirectionProxyError("cost_metadata_identity_invalid")
    by_product = metadata.set_index("vt_symbol", drop=False)

    rows: list[dict[str, Any]] = []
    for product in sorted(set(str(item) for item in products)):
        explicit = product in rates
        row = by_product.loc[product] if product in by_product.index else None
        metadata_size = float(pd.to_numeric(row.get("volume_multiple"), errors="coerce")) if row is not None else np.nan
        metadata_tick = float(pd.to_numeric(row.get("price_tick"), errors="coerce")) if row is not None else np.nan
        if explicit:
            rate = float(rates.get(product, np.nan))
            size = float(sizes.get(product, np.nan))
            tick = float(priceticks.get(product, np.nan))
            slippage = float(slippages.get(product, np.nan))
            source = "formal_explicit_legacy_universe"
        else:
            rate = 0.0
            size = metadata_size
            tick = metadata_tick
            slippage = metadata_tick
            source = "research_metadata_fallback"
        values = np.asarray([rate, size, tick, slippage], dtype=float)
        if not bool(np.isfinite(values).all()) or size <= 0 or tick <= 0 or slippage <= 0:
            raise DirectionProxyError(f"cost_metadata_invalid:{product}")
        rows.append(
            {
                "product_vt_symbol": product,
                "cost_contract_name": "research_code_defined_cost_proxy",
                "cost_source": source,
                "rate": rate,
                "slippage": slippage,
                "size": int(round(size)),
                "pricetick": tick,
                "metadata_size": metadata_size,
                "metadata_pricetick": metadata_tick,
                "historical_real_fee_claimed": False,
                "production_cost_claimed": False,
            }
        )
    return pd.DataFrame(rows)

"""Pure signal semantics migrated from qmt_stock/357.py.

RSI intentionally preserves the source's simple rolling average and NaN when
there are no losses. MACD is reseeded on the latest lookback window; replacing
either indicator with a library's default would change the strategy.
"""

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SignalSettings:
    bb_period: int = 20
    bb_std: float = 2
    rsi_period: int = 14
    rsi_oversold: float = 40
    macd_fast: int = 5
    macd_slow: int = 20
    macd_signal: int = 9
    selection_mode: str = "flexible"
    min_conditions: int = 2
    lookback: int = 60


def market_allows_entry(closes: Sequence[float]) -> bool:
    """沪深300当日不下跌，且 MA5 > MA10 > MA20。"""
    try:
        values = np.asarray(closes, dtype=float)[-20:]
    except (TypeError, ValueError):
        return False
    if values.ndim != 1 or len(values) < 20:
        return False
    if not np.isfinite(values).all() or (values <= 0).any():
        return False
    return bool(
        values[-1] >= values[-2]
        and values[-5:].mean() > values[-10:].mean() > values.mean()
    )


def _source_rsi(prices: pd.Series, period: int) -> pd.Series:
    delta = prices.diff()
    gain = delta.copy()
    loss = delta.copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0
    loss = -loss
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = pd.Series(np.nan, index=prices.index, dtype=float)
    mask = avg_loss > 0
    rs[mask] = avg_gain[mask] / avg_loss[mask]
    return 100 - 100 / (1 + rs)


def evaluate_signal(
    frame: pd.DataFrame, settings: SignalSettings = SignalSettings()
) -> dict | None:
    """Evaluate one symbol as of the final row, without account/execution state.

    None means unusable data or exclusion by the source's broad trend filter.
    Otherwise ``eligible`` records whether the selected signal combination
    qualifies. Volume and the unused high/low fields do not affect this alpha.
    """
    if settings.lookback <= 0 or not {"open", "close"}.issubset(frame.columns):
        return None
    data = frame.iloc[-settings.lookback:]
    minimum = max(40, settings.bb_period + 5, settings.macd_slow + settings.macd_signal + 5)
    if len(data) < minimum:
        return None
    try:
        close = data["close"].astype(float)
        opens = data["open"].iloc[-3:].astype(float)
    except (TypeError, ValueError):
        return None
    if (
        not np.isfinite(close).all()
        or not np.isfinite(opens).all()
        or (close <= 0).any()
        or (opens <= 0).any()
    ):
        return None

    latest = float(close.iloc[-1])
    ma20 = close.iloc[-20:].mean()
    ma40 = close.iloc[-40:].mean()
    if not (latest >= ma20 * 0.95 or ma20 >= ma40 * 0.98):
        return None

    middle = close.rolling(window=settings.bb_period).mean()
    lower = middle.iloc[-1] - settings.bb_std * close.rolling(window=settings.bb_period).std().iloc[-1]
    bollinger = bool(
        opens.iloc[-3] >= middle.iloc[-3]
        and close.iloc[-3] >= middle.iloc[-3]
        and opens.iloc[-2] >= middle.iloc[-2]
        and close.iloc[-2] < middle.iloc[-2]
        and latest > middle.iloc[-1]
    )

    rsi_values = _source_rsi(close, settings.rsi_period)
    if not np.isfinite(rsi_values.iloc[-2:]).all():
        return None
    rsi_yesterday = float(rsi_values.iloc[-2])
    rsi_today = float(rsi_values.iloc[-1])
    rsi_condition = rsi_yesterday < settings.rsi_oversold and rsi_today > rsi_yesterday

    ema_fast = close.ewm(span=settings.macd_fast, adjust=False).mean()
    ema_slow = close.ewm(span=settings.macd_slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=settings.macd_signal, adjust=False).mean()
    histogram = macd_line - signal_line
    macd_condition = bool(
        (macd_line.iloc[-2] < signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1])
        or (histogram.iloc[-2] < 0 and histogram.iloc[-1] > 0)
    )

    count = int(bollinger) + int(rsi_condition) + int(macd_condition)
    eligible = (
        settings.selection_mode == "strict" and count == 3
    ) or (
        settings.selection_mode == "flexible" and count >= settings.min_conditions
    )
    prices = close.iloc[-21:].to_numpy()
    volatility = np.std(np.diff(prices) / prices[:-1]) * np.sqrt(252)
    price_change = (latest - close.iloc[-2]) / close.iloc[-2]
    band_distance = (latest - middle.iloc[-1]) / middle.iloc[-1]
    rsi_change = rsi_today - rsi_yesterday
    macd_strength = histogram.iloc[-1] - histogram.iloc[-2]
    score = (
        price_change * 0.3
        + (1 - band_distance) * 0.2
        + volatility * 0.1
        + rsi_change / 100 * 0.2
        + (1 if macd_strength > 0 else 0) * 0.2
    ) * (0.7 + 0.3 * count / 3)

    return {
        "eligible": bool(eligible),
        "bollinger": bollinger,
        "rsi": bool(rsi_condition),
        "macd": macd_condition,
        "condition_count": count,
        "score": float(score),
        "close": latest,
        "rsi_value": rsi_today,
        "rsi_change": rsi_change,
        "macd_hist": float(histogram.iloc[-1]),
        "middle_band": float(middle.iloc[-1]),
        "lower_band": float(lower),
    }

"""Add audited, point-in-time BB20 overlays to frozen stock recap records.

This module reads caller-supplied data only. It neither imports the strategy nor
replays the engine. RSI/MACD flags remain the frozen log's facts; only Bollinger
geometry and its original three-day predicate are independently checked here.
"""
from collections import Counter
from copy import deepcopy

import numpy as np
import pandas as pd


def _dates(values, label):
    try:
        result = pd.DatetimeIndex(pd.to_datetime(values, errors="raise"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label} dates") from exc
    if result.isna().any() or result.tz is not None:
        raise ValueError(f"Missing or timezone-ambiguous {label} dates")
    return result.normalize()


def _boolean(value, label):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    if isinstance(value, (int, np.integer)) and value in (0, 1):
        return bool(value)
    raise ValueError(f"Invalid boolean in {label}: {value!r}")


def _match(actual, expected, label):
    try:
        left, right = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Non-numeric {label}") from exc
    if (left.shape != right.shape or not np.isfinite(left).all()
            or not np.isfinite(right).all()
            or not np.allclose(left, right, rtol=1e-10, atol=1e-8)):
        raise ValueError(f"Price-basis or frozen-log mismatch: {label}")
    return float(np.max(np.abs(left - right))) if left.size else 0.


def enrich_records(records: list, panel: pd.DataFrame, signals: pd.DataFrame,
                   signal_settings: dict) -> tuple[list, dict]:
    """Deep-copy records, add daily BB arrays and verify every entry marker.

    Each displayed t uses historical close[s] * factor[s] / factor[t], s <= t.
    Nineteen unavailable warmup values stay null. Entry signals, unlike display
    warmup, require the source's full minimum history and unambiguous log parity.
    """
    if signal_settings.get("bb_period") != 20 or signal_settings.get("bb_std") != 2:
        raise ValueError("The frozen display contract requires BB20 plus/minus 2 sigma")
    lookback = signal_settings.get("lookback")
    minimum = max(40, 25, signal_settings.get("macd_slow", 20)
                  + signal_settings.get("macd_signal", 9) + 5)
    if not isinstance(lookback, (int, np.integer)) or lookback < minimum:
        raise ValueError("Insufficient source signal lookback")
    required_panel = {"date", "vt_symbol", "open", "high", "low", "close", "adj_factor"}
    required_logs = {"date", "vt_symbol", "raw_close", "middle_band", "lower_band",
                     "bollinger", "rsi", "macd", "condition_count"}
    if not required_panel.issubset(panel.columns) or not required_logs.issubset(signals.columns):
        raise ValueError("Missing frozen panel or signal-log columns")

    result = deepcopy(records)
    wanted_symbols = {record["meta"]["vt_symbol"] for record in result}
    data = panel.loc[panel.vt_symbol.isin(wanted_symbols), sorted(required_panel)].copy()
    data["date"] = _dates(data.date, "panel")
    if data.duplicated(["vt_symbol", "date"]).any():
        raise ValueError("Duplicate panel symbol/date")
    logs = signals.copy(deep=True)
    logs["date"] = _dates(logs.date, "signal")
    if logs.duplicated(["vt_symbol", "date"]).any():
        raise ValueError("Duplicate frozen signal symbol/date")
    logs = logs.set_index(["vt_symbol", "date"])

    histories = {}
    for symbol, group in data.groupby("vt_symbol", sort=False):
        frame = group.sort_values("date").set_index("date")
        try:
            values = frame[["open", "high", "low", "close", "adj_factor"]].to_numpy(dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Non-numeric panel prices or factors: {symbol}") from exc
        if not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError(f"Missing/nonpositive panel prices or factors: {symbol}")
        # A past-only normalization keeps magnitudes manageable; the constant
        # cancels and does not use a future terminal factor.
        factor = frame.adj_factor / float(frame.adj_factor.iloc[0])
        adjusted = frame.close * factor
        middle = adjusted.rolling(20, min_periods=20).mean() / factor
        std = adjusted.rolling(20, min_periods=20).std(ddof=1) / factor
        frame["bb_middle"], frame["bb_upper"], frame["bb_lower"] = middle, middle + 2 * std, middle - 2 * std
        histories[symbol] = frame

    audit = dict(entries_checked=0, bollinger_true=0, bollinger_false=0,
                 condition_combinations={}, max_middle_band_error=0.,
                 max_lower_band_error=0., max_upper_band_error=0.,
                 max_raw_close_error=0., max_daily_ohlc_error=0.,
                 displayed_daily_bars=0, displayed_bb_missing_bars=0,
                 bb_period=20, bb_std=2, ddof=1,
                 price_basis="historical_point_in_time_adjusted_to_each_daily_raw_price",
                 rsi_macd_source="frozen_signal_log_not_recomputed")
    combinations = Counter()
    used_entry_keys = set()
    for record in result:
        meta, daily = record["meta"], record["daily"]
        symbol = meta["vt_symbol"]
        if meta.get("price_basis") != "unadjusted" or symbol not in histories:
            raise ValueError(f"Missing raw stock history or wrong price basis: {symbol}")
        frame = histories[symbol]
        dates = _dates(daily["date"], "daily")
        if not len(dates) or dates.has_duplicates or not dates.is_monotonic_increasing:
            raise ValueError(f"Missing, duplicate or unordered displayed dates: {symbol}")
        for field in ("x", "open", "high", "low", "close"):
            if field not in daily or len(daily[field]) != len(dates):
                raise ValueError(f"Inconsistent displayed {field} length: {symbol}")
        x_values = np.asarray(daily["x"], dtype=float)
        if not np.isfinite(x_values).all() or (np.diff(x_values) <= 0).any():
            raise ValueError(f"Invalid daily coordinates: {symbol}")
        if not dates.isin(frame.index).all():
            raise ValueError(f"Displayed day absent from frozen panel: {symbol}")
        visible = frame.loc[dates]
        for field in ("open", "high", "low", "close"):
            error = _match(daily[field], visible[field].to_numpy(), f"{symbol} daily {field}")
            audit["max_daily_ohlc_error"] = max(audit["max_daily_ohlc_error"], error)
        for field in ("bb_middle", "bb_upper", "bb_lower"):
            daily[field] = [None if pd.isna(value) else float(value) for value in visible[field]]
        audit["displayed_daily_bars"] += len(dates)
        audit["displayed_bb_missing_bars"] += int(visible.bb_middle.isna().sum())

        signal_date, entry_date = _dates([meta["entry_signal_date"], meta["entry_date"]], "entry")
        if signal_date >= entry_date or entry_date not in frame.index:
            raise ValueError(f"Signal must precede a real entry session: {symbol}")
        if signal_date not in frame.index or signal_date not in dates:
            raise ValueError(f"Signal day missing from displayed/frozen history: {symbol}")
        entry_pos = frame.index.get_loc(entry_date)
        if entry_pos == 0 or frame.index[entry_pos - 1] != signal_date:
            raise ValueError(f"Signal is not the most recent session before entry: {symbol}")
        key = (symbol, signal_date)
        if key in used_entry_keys:
            raise ValueError(f"Duplicate entry record for frozen signal: {key}")
        used_entry_keys.add(key)
        if key not in logs.index:
            raise ValueError(f"Missing frozen entry signal: {symbol} {signal_date.date()}")
        log = logs.loc[key]
        flags = {field: _boolean(log[field], field) for field in ("bollinger", "rsi", "macd")}
        count = sum(flags.values())
        if not np.isfinite(float(log.condition_count)) or float(log.condition_count) != count:
            raise ValueError(f"Condition count disagrees with frozen booleans: {key}")
        if "eligible" in log and not _boolean(log.eligible, "eligible"):
            raise ValueError(f"Entry log is not eligible: {key}")
        mode = signal_settings.get("selection_mode", "flexible")
        eligible = ((mode == "strict" and count == 3)
                    or (mode == "flexible" and count >= signal_settings.get("min_conditions", 2)))
        if not eligible:
            raise ValueError(f"Entry flags violate frozen selection contract: {key}")

        # Recreate only the BB predicate on the signal day's exact adjustment
        # basis, including prior opens; no order, selection or strategy execution.
        window = frame.loc[:signal_date].tail(lookback)
        if len(window) < minimum:
            raise ValueError(f"Insufficient pre-signal history: {key}")
        scales = window.adj_factor / float(window.adj_factor.iloc[-1])
        close = window.close * scales
        opens = window.open * scales
        middle = close.rolling(20, min_periods=20).mean()
        lower = float(middle.iloc[-1] - 2 * close.rolling(20, min_periods=20).std(ddof=1).iloc[-1])
        condition = bool(opens.iloc[-3] >= middle.iloc[-3]
                         and close.iloc[-3] >= middle.iloc[-3]
                         and opens.iloc[-2] >= middle.iloc[-2]
                         and close.iloc[-2] < middle.iloc[-2]
                         and close.iloc[-1] > middle.iloc[-1])
        if condition != flags["bollinger"]:
            raise ValueError(f"Original three-day Bollinger condition disagrees with log: {key}")
        checks = dict(middle_band=(float(middle.iloc[-1]), float(log.middle_band)),
                      lower_band=(lower, float(log.lower_band)),
                      raw_close=(float(window.close.iloc[-1]), float(log.raw_close)))
        if "close" in log:
            _match(float(log.close), float(log.raw_close), f"{key} logged close/raw_close")
        for name, (actual, expected) in checks.items():
            error = _match(actual, expected, f"{key} {name}")
            audit[f"max_{name}_error"] = max(audit[f"max_{name}_error"], error)
        # Upper band is absent from original logs, so use their symmetric BB
        # identity as an independent bridge from the displayed band to the log.
        upper = 2 * float(log.middle_band) - float(log.lower_band)
        for name, expected in (("middle", float(log.middle_band)),
                               ("lower", float(log.lower_band)), ("upper", upper)):
            error = _match(float(frame.loc[signal_date, f"bb_{name}"]), expected,
                           f"{key} displayed {name} band")
            audit[f"max_{name}_band_error"] = max(audit[f"max_{name}_band_error"], error)
        meta["entry_signal"] = dict(date=str(signal_date.date()),
                                    x=float(x_values[dates.get_loc(signal_date)]),
                                    raw_close=float(log.raw_close), **flags,
                                    condition_count=count, middle_band=float(log.middle_band),
                                    lower_band=float(log.lower_band), upper_band=upper)
        audit["entries_checked"] += 1
        audit["bollinger_true" if flags["bollinger"] else "bollinger_false"] += 1
        combinations[",".join(f"{name}={int(value)}" for name, value in flags.items())] += 1
    audit["condition_combinations"] = dict(sorted(combinations.items()))
    return result, audit

"""Pure, source-bound Stage124 EMA limit features and independent DAY state.

This module neither qualifies market data nor opens an account. A caller must
provide the accepted exact real-contract keys and qualifier fingerprint. Source
bytes are hashed and parsed once; qualification is a reference, not a grant.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import io
import json
import math
from pathlib import Path
import re
from typing import Mapping, Sequence

MECHANISM_ID = "stage124_ema_limit_v1"
_COLUMNS = ("date", "vt_symbol", "open", "high", "low", "close", "volume")


def _day(value, name):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError(f"invalid_{name}")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid_{name}") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"invalid_{name}")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"invalid_{name}")
    return value


def _finite(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _positive(value, name):
    number = _finite(value)
    if number is None or number <= 0:
        raise ValueError(f"invalid_{name}")
    return number


def _sha(value, name):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"invalid_{name}_sha256")
    return value


def _contract(value):
    value = _text(value, "contract")
    match = re.fullmatch(r"[A-Za-z]+(\d{3,4})\.[A-Z]+", value)
    if match is None or match[1] in ("888", "889", "999", "8888", "8899", "9999", "0000"):
        raise ValueError("not_real_contract")
    return value


def _identity(kind, *values):
    payload = json.dumps([MECHANISM_ID, kind, *values], ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    return f"{MECHANISM_ID}:{kind}:" + hashlib.sha256(payload.encode()).hexdigest()


def load_bound_daily_csv(path: Path, *, sha256: str,
                         qualified_keys: frozenset[tuple[str, str]],
                         qualifier_sha256: str) -> tuple[list[dict], dict]:
    """Hash and parse the same single byte read of a canonical daily export."""
    expected = _sha(sha256, "source")
    qualifier = _sha(qualifier_sha256, "qualifier")
    if not isinstance(qualified_keys, frozenset):
        raise ValueError("invalid_qualified_keys")
    for key in qualified_keys:
        if not isinstance(key, tuple) or len(key) != 2:
            raise ValueError("invalid_qualified_key")
        _contract(key[0])
        _day(key[1], "qualified_day")
    source_path = str(Path(path).resolve())
    data = Path(path).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError("source_sha256_mismatch")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != list(_COLUMNS):
        raise ValueError("invalid_real_daily_csv_schema")
    bindings = dict(source_path=source_path, source_sha256=actual,
                    qualifier_sha256=qualifier, qualified_keys=tuple(sorted(qualified_keys)),
                    price_basis="real_contract_unadjusted")
    output, seen = [], set()
    for raw in reader:
        if None in raw or any(value is None for value in raw.values()):
            raise ValueError("invalid_daily_csv_row")
        day, contract = _day(raw["date"], "date"), _contract(raw["vt_symbol"])
        key = (contract, day)
        if key in seen:
            raise ValueError("duplicate_contract_date")
        if key not in qualified_keys:
            raise ValueError("unqualified_contract_date")
        seen.add(key)
        row = dict(date=day, vt_symbol=contract)
        row.update((name, _finite(raw[name])) for name in _COLUMNS[2:])
        row.update(source_path=source_path, source_sha256=actual,
                   qualifier_sha256=qualifier, qualified_key=key,
                   price_basis="real_contract_unadjusted")
        output.append(row)
    return output, bindings


def build_ema_rows(rows: Sequence[Mapping], calendar: Sequence[str], *,
                   source_bindings: Mapping) -> list[dict]:
    """Build prefix-invariant EMA13 and 26-valid-bar positive penetrations.

    Missing required calendar sessions and invalid OHLC discard the segment.
    Rows from another contract never contribute to a contract's seed or window.
    """
    bindings = dict(source_bindings)
    for field in ("source_sha256", "qualifier_sha256"):
        _sha(bindings.get(field), field.removesuffix("_sha256"))
    _text(bindings.get("source_path"), "source_path")
    if bindings.get("price_basis") != "real_contract_unadjusted":
        raise ValueError("invalid_source_price_basis")
    qualified = frozenset(tuple(key) for key in bindings.get("qualified_keys", ()))
    days = [_day(day, "calendar_day") for day in calendar]
    if len(days) != len(set(days)):
        raise ValueError("duplicate_calendar_day")
    index = {day: i for i, day in enumerate(sorted(days))}
    grouped, seen = {}, set()
    for row in rows:
        day, contract = _day(row["date"], "date"), _contract(row["vt_symbol"])
        key = (contract, day)
        if key in seen:
            raise ValueError("duplicate_contract_date")
        seen.add(key)
        if day not in index:
            raise ValueError("noncalendar_date")
        if key not in qualified or tuple(row.get("qualified_key", ())) != key:
            raise ValueError("unqualified_contract_date")
        if any(row.get(name) != bindings[name] for name in
               ("source_path", "source_sha256", "qualifier_sha256", "price_basis")):
            raise ValueError("source_binding_mismatch")
        grouped.setdefault(contract, []).append(row)
    output = []
    for contract in sorted(grouped):
        previous_index = None
        seed, window = [], []
        ema = segment_start = None
        for row in sorted(grouped[contract], key=lambda item: item["date"]):
            day = row["date"]
            gap = previous_index is not None and index[day] != previous_index + 1
            values = [_finite(row.get(name)) for name in ("open", "high", "low", "close")]
            valid = (all(value is not None and value > 0 for value in values) and
                     values[2] <= min(values[0], values[3]) <=
                     max(values[0], values[3]) <= values[1])
            if gap or not valid:
                seed, window, ema, segment_start = [], [], None, None
            previous_ema = ema
            if valid:
                opening, high, low, close = values
                if segment_start is None:
                    segment_start = day
                if ema is None:
                    seed.append(close)
                    if len(seed) == 13:
                        ema = math.fsum(seed) / 13
                else:
                    ema = (1 / 7) * close + (6 / 7) * ema
                if ema is not None:
                    window.append((max(ema - low, 0), max(high - ema, 0)))
                    window = window[-26:]
            down = [pair[0] for pair in window if pair[0] > 0]
            up = [pair[1] for pair in window if pair[1] > 0]
            ready = valid and len(window) == 26
            reason = ("invalid_ohlc" if not valid else "ready" if ready else
                      "calendar_gap" if gap else "warmup_ema" if ema is None else "warmup_window")
            output.append(dict(asof=day, contract=contract, ready=ready, reason=reason,
                ema=ema, ema_prev=previous_ema,
                mean_down=math.fsum(down) / len(down) if down else None,
                mean_up=math.fsum(up) / len(up) if up else None,
                positive_down_count=len(down), positive_up_count=len(up),
                valid_ema_count=len(window), segment_start=segment_start,
                source_bindings=dict(bindings)))
            previous_index = index[day]
    return output


def limit_quote(feature: Mapping, *, direction: int, execution_tick: float) -> dict | None:
    """Return the sole next-session price, or unknown; never use a fallback."""
    if isinstance(direction, bool) or direction not in (-1, 1):
        raise ValueError("invalid_direction")
    tick = _finite(execution_tick)
    if not feature.get("ready") or tick is None or tick <= 0:
        return None
    side = "down" if direction == 1 else "up"
    ema, previous, mean = (_finite(feature.get(name)) for name in
                           ("ema", "ema_prev", f"mean_{side}"))
    if (ema is None or previous is None or mean is None or mean <= 0 or
            feature.get(f"positive_{side}_count", 0) <= 0):
        return None
    decimal_tick = Decimal(str(tick))
    raw = 2 * Decimal(str(ema)) - Decimal(str(previous)) - direction * Decimal(str(mean))
    rounded = (raw / decimal_tick).to_integral_value(
        rounding=ROUND_FLOOR if direction == 1 else ROUND_CEILING) * decimal_tick
    price = float(rounded)
    if not math.isfinite(price) or price <= 0:
        return None
    return dict(feature, direction=direction, limit_price=price, execution_tick=tick)


@dataclass
class _Product:
    day: str
    contract: str | None = None
    epoch_id: str | None = None
    direction: int | None = None
    setup: dict | None = None
    intent: dict | None = None


class EmaLimitSetupMachine:
    """Ordered week/FI preparation with an independent EMA limit namespace."""

    def __init__(self):
        self._products = {}

    @staticmethod
    def _result(state, decision, cancel_reason=None):
        return dict(mechanism_id=MECHANISM_ID, epoch_id=state.epoch_id, decision=decision,
                    setup_id=state.setup["setup_id"] if state.setup else None,
                    setup_day=state.setup["setup_day"] if state.setup else None,
                    intent=dict(state.intent) if state.intent else None,
                    baseline_fallback=False, cancel_reason=cancel_reason)

    def on_close(self, observation: Mapping, quote: Mapping | None) -> dict:
        required = ("product", "contract", "day", "next_day", "high", "low", "tick",
                    "weekly_ready", "weekly_direction", "weekly_asof", "fi_ready", "fi2",
                    "eligible", "position_open", "native_signal")
        if any(key not in observation for key in required):
            raise ValueError("missing_observation_field")
        obs = observation
        product, contract = _text(obs["product"], "product"), _contract(obs["contract"])
        day = _day(obs["day"], "day")
        next_day = _day(obs["next_day"], "next_day") if obs["next_day"] is not None else None
        if next_day is not None and next_day <= day:
            raise ValueError("next_day_not_later")
        high, low = _positive(obs["high"], "high"), _positive(obs["low"], "low")
        _positive(obs["tick"], "tick")
        if high < low:
            raise ValueError("high_below_low")
        for name in ("weekly_ready", "fi_ready", "eligible", "position_open"):
            if not isinstance(obs[name], bool):
                raise ValueError(f"invalid_{name}")
        direction = weekly_asof = None
        if obs["weekly_ready"]:
            direction = obs["weekly_direction"]
            if isinstance(direction, bool) or direction not in (-1, 0, 1):
                raise ValueError("invalid_weekly_direction")
            weekly_asof = _day(obs["weekly_asof"], "weekly_asof")
            if date.fromisoformat(weekly_asof).isocalendar()[:2] >= date.fromisoformat(day).isocalendar()[:2]:
                raise ValueError("weekly_asof_not_previous_completed_week")
        fi2 = _finite(obs["fi2"]) if obs["fi_ready"] else None
        if obs["fi_ready"] and fi2 is None:
            raise ValueError("invalid_fi2")
        if obs["native_signal"] is not None:
            raise ValueError("native_signal_must_be_none")
        rank = obs.get("rank", 0)
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0:
            raise ValueError("invalid_rank")
        if quote is not None:
            if quote.get("asof") != day:
                raise ValueError("quote_asof_mismatch")
            if quote.get("contract") != contract:
                raise ValueError("quote_contract_mismatch")
            if direction in (-1, 1) and quote.get("direction") != direction:
                raise ValueError("quote_direction_mismatch")
            if quote.get("ready") is not True:
                raise ValueError("quote_not_ready")
            limit = _positive(quote.get("limit_price"), "limit_price")
            tick = _positive(quote.get("execution_tick"), "execution_tick")
            if Decimal(str(limit)) % Decimal(str(tick)) != 0:
                raise ValueError("quote_not_on_execution_tick")
        state = self._products.get(product)
        if state is not None and day <= state.day:
            raise ValueError("nonincreasing_product_day")
        if state is None:
            state = _Product(day=day)
            self._products[product] = state
        epoch_changed = state.contract is not None and state.contract != contract
        direction_changed = state.direction is not None and state.direction != direction
        reason = "intent_expired" if state.intent is not None else None
        state.intent = None
        if state.contract != contract:
            state.epoch_id = _identity("epoch", product, contract, day)
        state.day, state.contract, state.direction = day, contract, direction
        if epoch_changed:
            state.setup, reason = None, "epoch_changed"
        if direction_changed:
            state.setup, reason = None, "weekly_direction_changed"
        if obs["position_open"] or not obs["eligible"]:
            state.setup = None
            return self._result(state, "blocked", "position_open" if obs["position_open"] else "ineligible")
        if not obs["weekly_ready"] or not obs["fi_ready"]:
            state.setup = None
            return self._result(state, "waiting", "weekly_unknown" if not obs["weekly_ready"] else "fi_unknown")
        if direction == 0:
            state.setup = None
            return self._result(state, "blocked", "weekly_neutral")
        if state.setup is None and fi2 * direction < 0:
            state.setup = dict(setup_id=_identity("setup", product, state.epoch_id, day, direction),
                               setup_day=day)
        if state.setup is None or next_day is None:
            return self._result(state, "waiting", reason)
        if quote is None:
            return self._result(state, "waiting", reason or "ema_unknown")
        identity = _identity("intent", product, contract, state.epoch_id,
                             state.setup["setup_id"], day, next_day, direction, limit,
                             tick, weekly_asof, rank)
        state.intent = dict(mechanism_id=MECHANISM_ID, epoch_id=state.epoch_id,
                            setup_id=state.setup["setup_id"], setup_day=state.setup["setup_day"],
                            intent_id=identity, signal_day=day, execution_day=next_day,
                            product=product, contract=contract, direction=direction,
                            limit_price=limit, execution_tick=tick, trigger=limit,
                            order_type="limit", weekly_asof=weekly_asof,
                            native_signal=None, rank=rank)
        return self._result(state, "intent", reason)

    def cancel(self, product: str, day: str, reason: str) -> dict:
        product, day, reason = _text(product, "product"), _day(day, "day"), _text(reason, "reason")
        state = self._products.get(product)
        if state is not None and day <= state.day:
            raise ValueError("nonincreasing_product_day")
        if state is None:
            state = _Product(day=day)
            self._products[product] = state
        state.day = day
        state.direction = state.setup = state.intent = None
        return self._result(state, "blocked", reason)

    def on_fill(self, intent_id: str, execution_day: str) -> dict:
        intent_id, execution_day = _text(intent_id, "intent_id"), _day(execution_day, "execution_day")
        state = next((state for state in self._products.values()
                      if state.intent and state.intent["intent_id"] == intent_id), None)
        if state is None:
            raise ValueError("unknown_or_expired_intent")
        if execution_day != state.intent["execution_day"]:
            raise ValueError("fill_outside_execution_day")
        receipt = dict(mechanism_id=MECHANISM_ID, intent_id=intent_id,
                       execution_day=execution_day, setup_id=state.setup["setup_id"], consumed=True)
        state.setup = state.intent = None
        return receipt

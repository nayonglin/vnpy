"""Pure, durable state reducer for the official C9 intraday stop/retry rule.

The module deliberately has no broker, CTP, clock, or filesystem dependency.  A
caller persists the returned JSON-friendly dictionary and feeds broker-confirmed
fills back through the explicit transition functions below.

The reducer models exactly two generations:

* attempt 0: the original position, where progress permanently waives the
  initial stop;
* attempt 1: the single retry, which can only be armed after both the close fill
  and broker-flat observations are known.

Ticks are consumed by ``feed_session_id/seq`` with sequence authoritative inside
one feed.  ``received_at`` remains the event-time cutoff and a regressing/bad
clock latches a coverage gap instead of silently discarding a later risk tick.
Replaying a tick or restoring a JSON snapshot and replaying an old tail is safe.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping


STATE_SCHEMA_VERSION = 1
STOP_RETRY_R = 0.5
DEFAULT_LIVE_UTC_OFFSET_HOURS = 8

# These constants are part of the durable action identity contract.  Changing
# their values would deliberately create a new idempotency namespace.
C9_ACTION_ROOT = "official_live_stage904_c9_intraday"
INITIAL_ACTION_CYCLE = "cycle0"
RETRY_ACTION_CYCLE = "cycle1"
INITIAL_STOP_ACTION_ROLE = "c9_initial_stop_close"
RETRY_OPEN_ACTION_ROLE = "c9_retry_open_once"
RETRY_STOP_ACTION_ROLE = "c9_retry_failed_stop_close"

ATTEMPT_INITIAL = 0
ATTEMPT_RETRY = 1

PHASE_INITIAL_ARMED = "initial_armed"
PHASE_INITIAL_PROGRESS_LATCHED = "initial_progress_latched"
PHASE_INITIAL_STOP_LATCHED = "initial_stop_latched"
PHASE_RETRY_WAIT = "retry_wait"
PHASE_RETRY_RECLAIM_LATCHED = "retry_reclaim_latched"
PHASE_RETRY_OPEN = "retry_open"
PHASE_RETRY_STOP_LATCHED = "retry_stop_latched"
PHASE_DONE = "done"

ACTION_OPEN = "open"
ACTION_CLOSE = "close"

_VALID_PHASES = {
    PHASE_INITIAL_ARMED,
    PHASE_INITIAL_PROGRESS_LATCHED,
    PHASE_INITIAL_STOP_LATCHED,
    PHASE_RETRY_WAIT,
    PHASE_RETRY_RECLAIM_LATCHED,
    PHASE_RETRY_OPEN,
    PHASE_RETRY_STOP_LATCHED,
    PHASE_DONE,
}

__all__ = [
    "STATE_SCHEMA_VERSION",
    "STOP_RETRY_R",
    "DEFAULT_LIVE_UTC_OFFSET_HOURS",
    "C9_ACTION_ROOT",
    "INITIAL_ACTION_CYCLE",
    "RETRY_ACTION_CYCLE",
    "INITIAL_STOP_ACTION_ROLE",
    "RETRY_OPEN_ACTION_ROLE",
    "RETRY_STOP_ACTION_ROLE",
    "ATTEMPT_INITIAL",
    "ATTEMPT_RETRY",
    "PHASE_INITIAL_ARMED",
    "PHASE_INITIAL_PROGRESS_LATCHED",
    "PHASE_INITIAL_STOP_LATCHED",
    "PHASE_RETRY_WAIT",
    "PHASE_RETRY_RECLAIM_LATCHED",
    "PHASE_RETRY_OPEN",
    "PHASE_RETRY_STOP_LATCHED",
    "PHASE_DONE",
    "ACTION_OPEN",
    "ACTION_CLOSE",
    "generation_for_action",
    "generate_root_position_id",
    "generate_position_cycle_id",
    "generate_position_epoch_id",
    "generate_action_id",
    "new_state",
    "consume_tick",
    "consume_ticks",
    "mark_feed_gap",
    "arm_retry_after_close",
    "mark_retry_filled",
    "update_current_position_volume",
    "mark_position_flat",
    "get_pending_action",
    "dumps_state",
    "loads_state",
]


def _canonical_time(value: Any, *, field: str) -> str:
    """Return UTC ISO; naive official-live timestamps are Asia/Shanghai wall time."""

    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field} is required")
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"invalid {field}: {value!r}") from exc

    # Existing official-live CSV/JSON artifacts use naive China-local strings,
    # while native feeds may include +08:00.  Normalizing both conventions here
    # prevents a silent eight-hour cutoff error when the two sources are mixed.
    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone(timedelta(hours=DEFAULT_LIVE_UTC_OFFSET_HOURS))
        )
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _time_value(value: Any, *, field: str) -> int:
    canonical = _canonical_time(value, field=field)
    parsed = datetime.fromisoformat(canonical.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1_000_000)


def _positive_float(value: Any, *, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return result


def _nonnegative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if result < 0:
        raise ValueError(f"{field} must be nonnegative")
    return result


def _normalized_direction(value: Any) -> str:
    direction = str(value or "").strip().lower()
    aliases = {
        "long": "long",
        "buy": "long",
        "多": "long",
        "short": "short",
        "sell": "short",
        "空": "short",
    }
    if direction not in aliases:
        raise ValueError("direction must be long or short")
    return aliases[direction]


def _required_text(value: Any, *, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{field} is required")
    return result


def _stable_digest(payload: Mapping[str, Any], *, length: int = 24) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


def generation_for_action(*, attempt_no: int, action: str) -> dict[str, str]:
    """Return the durable root/cycle/role tuple for one legal C9 action."""

    action = str(action or "").strip().lower()
    if attempt_no == ATTEMPT_INITIAL and action == ACTION_CLOSE:
        return {
            "root": C9_ACTION_ROOT,
            "cycle": INITIAL_ACTION_CYCLE,
            "role": INITIAL_STOP_ACTION_ROLE,
        }
    if attempt_no == ATTEMPT_RETRY and action == ACTION_OPEN:
        return {
            "root": C9_ACTION_ROOT,
            "cycle": RETRY_ACTION_CYCLE,
            "role": RETRY_OPEN_ACTION_ROLE,
        }
    if attempt_no == ATTEMPT_RETRY and action == ACTION_CLOSE:
        return {
            "root": C9_ACTION_ROOT,
            "cycle": RETRY_ACTION_CYCLE,
            "role": RETRY_STOP_ACTION_ROLE,
        }
    raise ValueError(f"unsupported generation: attempt_no={attempt_no}, action={action}")


def generate_root_position_id(
    *, target_date: str, vt_symbol: str, direction: str
) -> str:
    """Build the strategy root identity from its three reconstructable fields."""

    payload = {
        "target_date": _required_text(target_date, field="target_date"),
        "vt_symbol": _required_text(vt_symbol, field="vt_symbol").upper(),
        "direction": _normalized_direction(direction),
    }
    return f"c9root-{_stable_digest(payload)}"


def generate_position_cycle_id(*, root_position_id: str, cycle_no: int) -> str:
    """Build a readable/reconstructable cycle0 or cycle1 identity."""

    root = _required_text(root_position_id, field="root_position_id")
    if cycle_no == ATTEMPT_INITIAL:
        cycle = INITIAL_ACTION_CYCLE
    elif cycle_no == ATTEMPT_RETRY:
        cycle = RETRY_ACTION_CYCLE
    else:
        raise ValueError("C9 only supports cycle_no 0 or 1")
    return f"{root}:{cycle}"


def generate_position_epoch_id(
    *,
    target_date: str,
    vt_symbol: str,
    direction: str,
    entry_filled_at: Any,
    fill_identity: str,
) -> str:
    """Generate a stable position epoch when the broker adapter has no native id."""

    payload = {
        "target_date": _required_text(target_date, field="target_date"),
        "vt_symbol": _required_text(vt_symbol, field="vt_symbol").upper(),
        "direction": _normalized_direction(direction),
        "entry_filled_at": _canonical_time(entry_filled_at, field="entry_filled_at"),
        "fill_identity": _required_text(fill_identity, field="fill_identity"),
    }
    return f"c9pos-{_stable_digest(payload)}"


def generate_action_id(
    *,
    target_date: str,
    vt_symbol: str,
    direction: str,
    attempt_no: int,
    action: str,
    position_epoch_id: str | None = None,
) -> str:
    """Generate an idempotency key independent of tick time and process lifetime.

    ``position_epoch_id`` is optional only for backwards-compatible callers of
    this helper.  Durable state actions always provide it, so two independent
    fills in the same symbol/direction/day cannot share an action identity.
    """

    normalized_action = str(action or "").strip().lower()
    generation = generation_for_action(
        attempt_no=attempt_no,
        action=normalized_action,
    )
    root_position_id = generate_root_position_id(
        target_date=target_date,
        vt_symbol=vt_symbol,
        direction=direction,
    )
    position_cycle_id = generate_position_cycle_id(
        root_position_id=root_position_id,
        cycle_no=attempt_no,
    )
    payload = {
        **generation,
        "root_position_id": root_position_id,
        "position_cycle_id": position_cycle_id,
        "intent_role": generation["role"],
        "attempt_no": attempt_no,
        "action": normalized_action,
    }
    if position_epoch_id is not None:
        payload["position_epoch_id"] = _required_text(
            position_epoch_id, field="position_epoch_id"
        )
    return f"c9act-{_stable_digest(payload)}"


def new_state(
    *,
    target_date: str,
    vt_symbol: str,
    direction: str,
    position_epoch_id: str,
    entry_filled_at: Any,
    entry_price: float,
    original_stop_price: float,
    volume: int,
    stop_retry_r: float = STOP_RETRY_R,
) -> dict[str, Any]:
    """Create the initial-attempt state after the original entry is filled."""

    normalized_direction = _normalized_direction(direction)
    normalized_entry = _positive_float(entry_price, field="entry_price")
    normalized_original_stop = _positive_float(
        original_stop_price, field="original_stop_price"
    )
    normalized_r = _positive_float(stop_retry_r, field="stop_retry_r")
    normalized_volume = _nonnegative_int(volume, field="volume")
    if normalized_volume == 0:
        raise ValueError("volume must be positive")

    if normalized_direction == "long" and normalized_original_stop >= normalized_entry:
        raise ValueError("long original_stop_price must be below entry_price")
    if normalized_direction == "short" and normalized_original_stop <= normalized_entry:
        raise ValueError("short original_stop_price must be above entry_price")

    risk_price = abs(normalized_entry - normalized_original_stop)
    sign = 1.0 if normalized_direction == "long" else -1.0
    c9_stop_price = normalized_entry - sign * normalized_r * risk_price
    c9_progress_price = normalized_entry + sign * normalized_r * risk_price
    if c9_stop_price <= 0 or c9_progress_price <= 0:
        raise ValueError("computed C9 stop/progress prices must be positive")

    normalized_target_date = _required_text(target_date, field="target_date")
    normalized_vt_symbol = _required_text(vt_symbol, field="vt_symbol").upper()
    root_position_id = generate_root_position_id(
        target_date=normalized_target_date,
        vt_symbol=normalized_vt_symbol,
        direction=normalized_direction,
    )
    state: dict[str, Any] = {
        "schema_version": STATE_SCHEMA_VERSION,
        "target_date": normalized_target_date,
        "vt_symbol": normalized_vt_symbol,
        "direction": normalized_direction,
        "root_position_id": root_position_id,
        "position_cycle_no": ATTEMPT_INITIAL,
        "position_cycle_id": generate_position_cycle_id(
            root_position_id=root_position_id,
            cycle_no=ATTEMPT_INITIAL,
        ),
        "position_epoch_id": _required_text(
            position_epoch_id, field="position_epoch_id"
        ),
        "entry_filled_at": _canonical_time(entry_filled_at, field="entry_filled_at"),
        "entry_price": normalized_entry,
        "original_stop_price": normalized_original_stop,
        "risk_price": risk_price,
        "stop_retry_r": normalized_r,
        "c9_stop_price": c9_stop_price,
        "c9_progress_price": c9_progress_price,
        "volume": normalized_volume,
        "phase": PHASE_INITIAL_ARMED,
        "attempt_no": ATTEMPT_INITIAL,
        "feed_gap_latched": False,
        "feed_gap_at": None,
        "feed_gap_reason": None,
        "last_tick_order_key": None,
        "last_seq_by_feed": {},
        "last_tick_at": None,
        "last_adverse_price": None,
        "last_progress_price": None,
        "initial_progress_latched_at": None,
        "initial_progress_latched_price": None,
        "initial_stop_latched_at": None,
        "initial_stop_latched_price": None,
        "close_fill_at": None,
        "broker_flat_at": None,
        "retry_armed_after": None,
        "retry_reclaim_latched_at": None,
        "retry_reclaim_latched_price": None,
        "retry_current_favorable": False,
        "retry_fresh_tick_required": False,
        "retry_action_id": None,
        "retry_fill_at": None,
        "retry_fill_price": None,
        "retry_target_volume": normalized_volume,
        "retry_filled_volume": 0,
        "current_position_volume": normalized_volume,
        "retry_stop_latched_at": None,
        "retry_stop_latched_price": None,
        "flat_at": None,
        "pending_action": None,
        "revision": 0,
        "transitions": [],
        "counters": {
            "accepted_ticks": 0,
            "unusable_tick_envelopes": 0,
            "tick_time_errors": 0,
            "ignored_before_entry_ticks": 0,
            "ignored_before_retry_cutoff_ticks": 0,
            "ignored_before_retry_fill_ticks": 0,
            "progress_blocked_by_feed_gap": 0,
            "retry_reclaim_blocked_by_feed_gap": 0,
            "retry_late_open_blocked_unfavorable": 0,
        },
    }
    return _refresh_pending_action(state)


def _validate_state(state: Mapping[str, Any]) -> None:
    if int(state.get("schema_version", -1)) != STATE_SCHEMA_VERSION:
        raise ValueError("unsupported C9 state schema_version")
    if state.get("phase") not in _VALID_PHASES:
        raise ValueError(f"invalid C9 phase: {state.get('phase')!r}")
    direction = _normalized_direction(state.get("direction"))
    target_date = _required_text(state.get("target_date"), field="target_date")
    vt_symbol = _required_text(state.get("vt_symbol"), field="vt_symbol")
    _required_text(state.get("position_epoch_id"), field="position_epoch_id")
    for field in (
        "entry_price",
        "original_stop_price",
        "risk_price",
        "stop_retry_r",
        "c9_stop_price",
        "c9_progress_price",
    ):
        _positive_float(state.get(field), field=field)
    expected_root = generate_root_position_id(
        target_date=target_date,
        vt_symbol=vt_symbol,
        direction=direction,
    )
    if state.get("root_position_id") != expected_root:
        raise ValueError("root_position_id does not match target_date/symbol/direction")
    cycle_no = int(state.get("position_cycle_no", -1))
    if int(state.get("attempt_no", -1)) != cycle_no:
        raise ValueError("attempt_no and position_cycle_no must match")
    initial_phases = {
        PHASE_INITIAL_ARMED,
        PHASE_INITIAL_PROGRESS_LATCHED,
        PHASE_INITIAL_STOP_LATCHED,
    }
    retry_phases = {
        PHASE_RETRY_WAIT,
        PHASE_RETRY_RECLAIM_LATCHED,
        PHASE_RETRY_OPEN,
        PHASE_RETRY_STOP_LATCHED,
    }
    if state["phase"] in initial_phases and cycle_no != ATTEMPT_INITIAL:
        raise ValueError("initial phase must use cycle0")
    if state["phase"] in retry_phases and cycle_no != ATTEMPT_RETRY:
        raise ValueError("retry phase must use cycle1")
    expected_cycle = generate_position_cycle_id(
        root_position_id=expected_root,
        cycle_no=cycle_no,
    )
    if state.get("position_cycle_id") != expected_cycle:
        raise ValueError("position_cycle_id does not match root_position_id/cycle_no")


def _copy_state(state: Mapping[str, Any]) -> dict[str, Any]:
    _validate_state(state)
    return copy.deepcopy(dict(state))


def _increment(state: dict[str, Any], counter: str) -> None:
    counters = state.setdefault("counters", {})
    counters[counter] = int(counters.get(counter, 0)) + 1


def _transition(
    state: dict[str, Any],
    *,
    phase: str,
    at: str,
    reason: str,
    feed_session_id: str | None = None,
    seq: int | None = None,
) -> None:
    previous = state["phase"]
    state["phase"] = phase
    state.setdefault("transitions", []).append(
        {
            "from": previous,
            "to": phase,
            "at": at,
            "reason": reason,
            "feed_session_id": feed_session_id,
            "seq": seq,
        }
    )


def _build_action(
    state: Mapping[str, Any],
    *,
    attempt_no: int,
    action: str,
    triggered_at: str,
    trigger_price: float,
    reason: str,
) -> dict[str, Any]:
    generation = generation_for_action(attempt_no=attempt_no, action=action)
    action_id = generate_action_id(
        target_date=str(state["target_date"]),
        vt_symbol=str(state["vt_symbol"]),
        direction=str(state["direction"]),
        attempt_no=attempt_no,
        action=action,
        position_epoch_id=str(state["position_epoch_id"]),
    )
    position_direction = str(state["direction"])
    if action == ACTION_CLOSE:
        order_direction = "short" if position_direction == "long" else "long"
        offset = "close"
    else:
        order_direction = position_direction
        offset = "open"
    action_volume = state["volume"]
    if action == ACTION_CLOSE:
        action_volume = state.get(
            "current_position_volume",
            state.get("retry_filled_volume", state["volume"]),
        )
    return {
        "action_id": action_id,
        **generation,
        "attempt_no": attempt_no,
        "action": action,
        "offset": offset,
        "target_date": state["target_date"],
        "vt_symbol": state["vt_symbol"],
        "root_position_id": state["root_position_id"],
        "position_cycle_id": state["position_cycle_id"],
        "position_cycle_no": state["position_cycle_no"],
        "intent_role": generation["role"],
        "position_epoch_id": state["position_epoch_id"],
        "position_direction": position_direction,
        "order_direction": order_direction,
        "volume": action_volume,
        "triggered_at": triggered_at,
        "trigger_price": trigger_price,
        "reason": reason,
        "ready": True,
    }


def _refresh_pending_action(state: dict[str, Any]) -> dict[str, Any]:
    phase = state["phase"]
    pending: dict[str, Any] | None = None
    if phase == PHASE_INITIAL_STOP_LATCHED:
        pending = _build_action(
            state,
            attempt_no=ATTEMPT_INITIAL,
            action=ACTION_CLOSE,
            triggered_at=str(state["initial_stop_latched_at"]),
            trigger_price=float(state["initial_stop_latched_price"]),
            reason="initial_stop_crossed_before_progress",
        )
    elif phase == PHASE_RETRY_RECLAIM_LATCHED:
        if (
            not state.get("feed_gap_latched")
            and not state.get("retry_fresh_tick_required")
            and state.get("retry_current_favorable")
        ):
            pending = _build_action(
                state,
                attempt_no=ATTEMPT_RETRY,
                action=ACTION_OPEN,
                triggered_at=str(state["retry_reclaim_latched_at"]),
                trigger_price=float(state["retry_reclaim_latched_price"]),
                reason="original_entry_reclaimed_after_confirmed_flat",
            )
            state["retry_action_id"] = pending["action_id"]
    elif phase == PHASE_RETRY_STOP_LATCHED:
        pending = _build_action(
            state,
            attempt_no=ATTEMPT_RETRY,
            action=ACTION_CLOSE,
            triggered_at=str(state["retry_stop_latched_at"]),
            trigger_price=float(state["retry_stop_latched_price"]),
            reason="retry_failed_at_c9_stop",
        )
    state["pending_action"] = pending
    return state


def _tick_order(tick: Mapping[str, Any]) -> tuple[int, str, int, str]:
    received_at = _canonical_time(tick.get("received_at"), field="received_at")
    feed_session_id = _required_text(
        tick.get("feed_session_id"), field="feed_session_id"
    )
    seq = _nonnegative_int(tick.get("seq"), field="seq")
    return (
        _time_value(received_at, field="received_at"),
        feed_session_id,
        seq,
        received_at,
    )


def _stored_order_tuple(key: Any) -> tuple[int, str, int] | None:
    if not isinstance(key, list) or len(key) != 3:
        return None
    return (
        _time_value(key[0], field="last_tick_order_key.received_at"),
        str(key[1]),
        int(key[2]),
    )


def _price_values(tick: Mapping[str, Any], names: Iterable[str]) -> list[float]:
    values: list[float] = []
    for name in names:
        raw = tick.get(name)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            values.append(value)
    return values


def _adverse_and_progress_prices(
    state: Mapping[str, Any], tick: Mapping[str, Any]
) -> tuple[float | None, float | None]:
    """Return risk-side executable evidence and trade-price progress evidence.

    A bid/ask quote may prove that a protective close is executable, but a wide
    spread alone must never permanently waive the initial stop.  The original
    Stage847 progress rule was based on traded high/low, so only exchange trade
    price fields are eligible for ``progress``.
    """

    common = ("last_price", "price", "close_price")
    progress_values = _price_values(tick, common)
    if state["direction"] == "long":
        adverse_values = _price_values(tick, (*common, "bid_price_1"))
        adverse = min(adverse_values) if adverse_values else None
        progress = max(progress_values) if progress_values else None
        return adverse, progress
    adverse_values = _price_values(tick, (*common, "ask_price_1"))
    adverse = max(adverse_values) if adverse_values else None
    progress = min(progress_values) if progress_values else None
    return adverse, progress


def _retry_reclaim_price(
    state: Mapping[str, Any], tick: Mapping[str, Any]
) -> float | None:
    """Return a price at which the one-shot retry is currently executable."""

    common = ("last_price", "price", "close_price")
    if state["direction"] == "long":
        values = _price_values(tick, (*common, "ask_price_1"))
        return max(values) if values else None
    values = _price_values(tick, (*common, "bid_price_1"))
    return min(values) if values else None


def _is_adverse_cross(state: Mapping[str, Any], price: float) -> bool:
    if state["direction"] == "long":
        return price <= float(state["c9_stop_price"])
    return price >= float(state["c9_stop_price"])


def _is_favorable(state: Mapping[str, Any], price: float) -> bool:
    if state["direction"] == "long":
        return price >= float(state["entry_price"])
    return price <= float(state["entry_price"])


def _is_progress_cross(state: Mapping[str, Any], price: float) -> bool:
    if state["direction"] == "long":
        return price >= float(state["c9_progress_price"])
    return price <= float(state["c9_progress_price"])


def _latch_feed_gap_in_place(
    state: dict[str, Any],
    *,
    detected_at: str,
    reason: str,
    feed_session_id: str | None = None,
    seq: int | None = None,
) -> bool:
    """Latch the first coverage gap; return whether this call changed state."""

    if state.get("feed_gap_latched"):
        return False
    state["feed_gap_latched"] = True
    state["feed_gap_at"] = detected_at
    state["feed_gap_reason"] = str(reason or "unspecified_feed_gap")
    state.setdefault("transitions", []).append(
        {
            "from": state["phase"],
            "to": state["phase"],
            "at": detected_at,
            "reason": "feed_gap_latched",
            "detail": state["feed_gap_reason"],
            "feed_session_id": feed_session_id,
            "seq": seq,
        }
    )
    return True


def consume_tick(
    state: Mapping[str, Any], tick: Mapping[str, Any]
) -> dict[str, Any]:
    """Consume one tick, returning a new state without mutating either input."""

    result = _copy_state(state)
    tick_symbol = str(tick.get("vt_symbol") or "").strip().upper()
    if tick_symbol and tick_symbol != result["vt_symbol"]:
        return _refresh_pending_action(result)

    try:
        feed_session_id = _required_text(
            tick.get("feed_session_id"), field="feed_session_id"
        )
        seq = _nonnegative_int(tick.get("seq"), field="seq")
    except (TypeError, ValueError):
        return _refresh_pending_action(result)

    previous_seq = result.setdefault("last_seq_by_feed", {}).get(feed_session_id)
    if previous_seq is not None and seq <= int(previous_seq):
        return _refresh_pending_action(result)

    try:
        order_micros, _, _, received_at = _tick_order(tick)
    except (TypeError, ValueError):
        # A sequence-advancing tick with an unusable wall clock proves a hole in
        # the ordered history.  Consume its sequence and latch the coverage gap
        # so replay is idempotent, but never use it to waive risk or open retry.
        result["last_seq_by_feed"][feed_session_id] = seq
        result["revision"] = int(result.get("revision", 0)) + 1
        _increment(result, "tick_time_errors")
        _latch_feed_gap_in_place(
            result,
            detected_at=str(result.get("last_tick_at") or result["entry_filled_at"]),
            reason="invalid_tick_received_at_with_sequence_advance",
            feed_session_id=feed_session_id,
            seq=seq,
        )
        return _refresh_pending_action(result)

    previous_key = result.get("last_tick_order_key")
    previous_order = _stored_order_tuple(previous_key)
    same_feed_clock_regressed = bool(
        previous_order is not None
        and str(previous_order[1]) == feed_session_id
        and order_micros < int(previous_order[0])
    )

    after_entry = order_micros >= _time_value(
        result["entry_filled_at"], field="entry_filled_at"
    )
    if same_feed_clock_regressed:
        # Sequence is authoritative within one feed session.  A wall-clock
        # rollback is coverage degradation, not a reason to discard a later
        # adverse tick.  Once a prior tick was post-entry, keep processing the
        # advancing sequence as post-entry as well.
        previous_after_entry = int(previous_order[0]) >= _time_value(
            result["entry_filled_at"], field="entry_filled_at"
        )
        after_entry = after_entry or previous_after_entry
    result["last_seq_by_feed"][feed_session_id] = seq
    result["last_tick_order_key"] = [received_at, feed_session_id, seq]
    result["last_tick_at"] = received_at
    result["revision"] = int(result.get("revision", 0)) + 1

    if same_feed_clock_regressed:
        _latch_feed_gap_in_place(
            result,
            detected_at=received_at,
            reason="tick_received_at_regressed_with_sequence_advance",
            feed_session_id=feed_session_id,
            seq=seq,
        )

    if not after_entry:
        _increment(result, "ignored_before_entry_ticks")
        return _refresh_pending_action(result)

    adverse_price, progress_price = _adverse_and_progress_prices(result, tick)
    retry_reclaim_price = _retry_reclaim_price(result, tick)
    if adverse_price is None or progress_price is None:
        _increment(result, "unusable_tick_envelopes")
        _latch_feed_gap_in_place(
            result,
            detected_at=received_at,
            reason="incomplete_or_nonfinite_tick_price",
            feed_session_id=feed_session_id,
            seq=seq,
        )

    result["last_adverse_price"] = adverse_price
    result["last_progress_price"] = progress_price
    if adverse_price is not None or progress_price is not None:
        _increment(result, "accepted_ticks")

    phase = result["phase"]
    if phase == PHASE_INITIAL_ARMED:
        adverse_cross = adverse_price is not None and _is_adverse_cross(
            result, adverse_price
        )
        progress_cross = progress_price is not None and _is_progress_cross(
            result, progress_price
        )
        # Stop-first is intentional when one wide/spread tick crosses both.
        if adverse_cross:
            result["initial_stop_latched_at"] = received_at
            result["initial_stop_latched_price"] = adverse_price
            _transition(
                result,
                phase=PHASE_INITIAL_STOP_LATCHED,
                at=received_at,
                reason="initial_stop_crossed_before_progress",
                feed_session_id=feed_session_id,
                seq=seq,
            )
        elif progress_cross:
            if result.get("feed_gap_latched"):
                _increment(result, "progress_blocked_by_feed_gap")
            else:
                result["initial_progress_latched_at"] = received_at
                result["initial_progress_latched_price"] = progress_price
                _transition(
                    result,
                    phase=PHASE_INITIAL_PROGRESS_LATCHED,
                    at=received_at,
                    reason="initial_progress_permanently_waived_stop",
                    feed_session_id=feed_session_id,
                    seq=seq,
                )
    elif phase == PHASE_RETRY_WAIT:
        cutoff = result.get("retry_armed_after")
        if cutoff is None:
            raise ValueError("retry_wait state is missing retry_armed_after")
        if order_micros <= _time_value(cutoff, field="retry_armed_after"):
            _increment(result, "ignored_before_retry_cutoff_ticks")
        elif retry_reclaim_price is not None and _is_favorable(result, retry_reclaim_price):
            if result.get("feed_gap_latched"):
                _increment(result, "retry_reclaim_blocked_by_feed_gap")
            else:
                result["retry_reclaim_latched_at"] = received_at
                result["retry_reclaim_latched_price"] = retry_reclaim_price
                result["retry_current_favorable"] = True
                result["retry_fresh_tick_required"] = False
                result["retry_action_id"] = generate_action_id(
                    target_date=result["target_date"],
                    vt_symbol=result["vt_symbol"],
                    direction=result["direction"],
                    attempt_no=ATTEMPT_RETRY,
                    action=ACTION_OPEN,
                    position_epoch_id=result["position_epoch_id"],
                )
                _transition(
                    result,
                    phase=PHASE_RETRY_RECLAIM_LATCHED,
                    at=received_at,
                    reason="original_entry_reclaimed_after_confirmed_flat",
                    feed_session_id=feed_session_id,
                    seq=seq,
                )
    elif phase == PHASE_RETRY_RECLAIM_LATCHED:
        currently_favorable = (
            retry_reclaim_price is not None
            and _is_favorable(result, retry_reclaim_price)
        )
        if result.get("retry_current_favorable") and not currently_favorable:
            _increment(result, "retry_late_open_blocked_unfavorable")
        result["retry_current_favorable"] = currently_favorable
        result["retry_fresh_tick_required"] = False
    elif phase == PHASE_RETRY_OPEN:
        retry_fill_at = result.get("retry_fill_at")
        if retry_fill_at is None:
            raise ValueError("retry_open state is missing retry_fill_at")
        if order_micros <= _time_value(retry_fill_at, field="retry_fill_at"):
            _increment(result, "ignored_before_retry_fill_ticks")
        elif adverse_price is not None and _is_adverse_cross(result, adverse_price):
            result["retry_stop_latched_at"] = received_at
            result["retry_stop_latched_price"] = adverse_price
            _transition(
                result,
                phase=PHASE_RETRY_STOP_LATCHED,
                at=received_at,
                reason="retry_failed_at_c9_stop",
                feed_session_id=feed_session_id,
                seq=seq,
            )

    # Progress/stop latches and DONE deliberately ignore later market reversals.
    return _refresh_pending_action(result)


def consume_ticks(
    state: Mapping[str, Any], ticks: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Sort each feed by sequence and consume the batch exactly once."""

    materialized = list(ticks)

    def sort_key(tick: Mapping[str, Any]) -> tuple[str, int, int]:
        try:
            feed_session_id = _required_text(
                tick.get("feed_session_id"), field="feed_session_id"
            )
            seq = _nonnegative_int(tick.get("seq"), field="seq")
            try:
                micros = _time_value(tick.get("received_at"), field="received_at")
            except (TypeError, ValueError):
                micros = 2**63 - 1
            return feed_session_id, seq, micros
        except (TypeError, ValueError):
            return ("\uffff", 2**63 - 1, 2**63 - 1)

    result = _copy_state(state)
    for tick in sorted(materialized, key=sort_key):
        result = consume_tick(result, tick)
    return result


def mark_feed_gap(
    state: Mapping[str, Any], *, detected_at: Any, reason: str
) -> dict[str, Any]:
    """Latch incomplete market-data coverage for this position epoch."""

    result = _copy_state(state)
    canonical = _canonical_time(detected_at, field="detected_at")
    if _latch_feed_gap_in_place(
        result,
        detected_at=canonical,
        reason=reason,
    ):
        result["revision"] = int(result.get("revision", 0)) + 1
    return _refresh_pending_action(result)


def arm_retry_after_close(
    state: Mapping[str, Any], *, close_fill_at: Any, broker_flat_at: Any
) -> dict[str, Any]:
    """Acknowledge the initial close and arm retry strictly after both facts."""

    result = _copy_state(state)
    if result["phase"] != PHASE_INITIAL_STOP_LATCHED:
        raise ValueError("retry can only be armed from initial_stop_latched")
    close_at = _canonical_time(close_fill_at, field="close_fill_at")
    flat_at = _canonical_time(broker_flat_at, field="broker_flat_at")
    cutoff = close_at
    if _time_value(flat_at, field="broker_flat_at") > _time_value(
        close_at, field="close_fill_at"
    ):
        cutoff = flat_at
    result["close_fill_at"] = close_at
    result["broker_flat_at"] = flat_at
    result["retry_armed_after"] = cutoff
    result["attempt_no"] = ATTEMPT_RETRY
    result["position_cycle_no"] = ATTEMPT_RETRY
    result["position_cycle_id"] = generate_position_cycle_id(
        root_position_id=result["root_position_id"],
        cycle_no=ATTEMPT_RETRY,
    )
    result["retry_current_favorable"] = False
    result["retry_fresh_tick_required"] = False
    _transition(
        result,
        phase=PHASE_RETRY_WAIT,
        at=cutoff,
        reason="close_filled_and_broker_flat_confirmed",
    )
    result["revision"] = int(result.get("revision", 0)) + 1
    return _refresh_pending_action(result)


def mark_retry_filled(
    state: Mapping[str, Any],
    *,
    retry_fill_at: Any,
    retry_fill_price: float | None = None,
    retry_fill_volume: int | None = None,
) -> dict[str, Any]:
    """Acknowledge any positive retry fill and protect the actually filled size.

    A partially-filled retry is already market risk.  It must therefore enter
    ``retry_open`` immediately instead of waiting for the original target size.
    The caller may subsequently refresh ``current_position_volume`` from the
    broker snapshot before producing the second-stop close action.
    """

    result = _copy_state(state)
    if result["phase"] != PHASE_RETRY_RECLAIM_LATCHED:
        raise ValueError("retry fill can only follow a latched reclaim")
    canonical = _canonical_time(retry_fill_at, field="retry_fill_at")
    result["retry_fill_at"] = canonical
    if retry_fill_price is not None:
        result["retry_fill_price"] = _positive_float(
            retry_fill_price, field="retry_fill_price"
        )
    if retry_fill_volume is None:
        normalized_fill_volume = _nonnegative_int(
            result.get("volume"), field="volume"
        )
    else:
        normalized_fill_volume = _nonnegative_int(
            retry_fill_volume, field="retry_fill_volume"
        )
    if normalized_fill_volume <= 0:
        raise ValueError("retry_fill_volume must be positive")
    result["retry_target_volume"] = _nonnegative_int(
        result.get("retry_target_volume", result.get("volume")),
        field="retry_target_volume",
    )
    result["retry_filled_volume"] = normalized_fill_volume
    result["current_position_volume"] = normalized_fill_volume
    result["attempt_no"] = ATTEMPT_RETRY
    result["retry_current_favorable"] = False
    result["retry_fresh_tick_required"] = False
    _transition(
        result,
        phase=PHASE_RETRY_OPEN,
        at=canonical,
        reason="retry_fill_confirmed",
    )
    result["revision"] = int(result.get("revision", 0)) + 1
    return _refresh_pending_action(result)


def update_current_position_volume(
    state: Mapping[str, Any], *, volume: int
) -> dict[str, Any]:
    """Refresh the exact broker/ledger residual used by a protective close."""

    normalized_volume = _nonnegative_int(volume, field="current_position_volume")
    if normalized_volume <= 0:
        raise ValueError("current_position_volume must be positive")
    result = _copy_state(state)
    if int(result.get("current_position_volume", 0)) != normalized_volume:
        result["current_position_volume"] = normalized_volume
        result["revision"] = int(result.get("revision", 0)) + 1
    return _refresh_pending_action(result)


def mark_position_flat(state: Mapping[str, Any], *, flat_at: Any) -> dict[str, Any]:
    """Finalize the epoch after a close fill or an external flattening decision."""

    result = _copy_state(state)
    canonical = _canonical_time(flat_at, field="flat_at")
    if result["phase"] != PHASE_DONE:
        result["flat_at"] = canonical
        _transition(result, phase=PHASE_DONE, at=canonical, reason="position_flat")
        result["revision"] = int(result.get("revision", 0)) + 1
    return _refresh_pending_action(result)


def get_pending_action(state: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a copy of the currently executable action, if any."""

    refreshed = _refresh_pending_action(_copy_state(state))
    pending = refreshed.get("pending_action")
    return copy.deepcopy(pending) if pending is not None else None


def dumps_state(state: Mapping[str, Any]) -> str:
    """Serialize state deterministically; useful for atomic caller-side storage."""

    _validate_state(state)
    return json.dumps(
        dict(state),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def loads_state(payload: str) -> dict[str, Any]:
    """Restore and validate a state snapshot, regenerating pending action data."""

    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise ValueError("C9 state JSON must contain an object")
    result = _copy_state(decoded)
    if result["phase"] == PHASE_RETRY_RECLAIM_LATCHED:
        # A process restart creates an unobserved market-data interval.  Preserve
        # the reclaim/action-id latch, but require a newer favorable tick before
        # exposing a risk-increasing retry open again.
        result["retry_current_favorable"] = False
        result["retry_fresh_tick_required"] = True
        result["pending_action"] = None
    return _refresh_pending_action(result)

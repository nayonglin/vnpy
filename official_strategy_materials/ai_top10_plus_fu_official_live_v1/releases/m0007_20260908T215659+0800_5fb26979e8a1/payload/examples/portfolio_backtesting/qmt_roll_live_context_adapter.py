from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
import math
from pathlib import Path
from typing import Any

import pandas as pd

from ctp_execution_safety import (
    clean_text,
    normalize_direction,
    normalize_offset,
    price_on_tick,
    split_vt_symbol,
    to_float,
)


REQUIRED_LIVE_CONTEXT_FIELDS = [
    "fresh_contract_snapshot",
    "fresh_account_snapshot",
    "fresh_position_snapshot",
    "live_limit_price",
    "account_equity_before",
    "broker_margin_before",
    "price_band_checked",
    "margin_available_checked",
    "operator_confirmed",
]

ACCOUNT_MARGIN_FIELD_CANDIDATES = [
    "margin",
    "curr_margin",
    "CurrMargin",
    "current_margin",
    "CurrentMargin",
    "position_margin",
    "PositionMargin",
    "occupied_margin",
    "OccupiedMargin",
    "use_margin",
    "UseMargin",
]

PRE_SUBMIT_HEATMAP_FIELDS = [
    "order_reference_ready",
    "dry_run_payload_ready",
    "fresh_contract_snapshot",
    "fresh_account_snapshot",
    "fresh_position_snapshot",
    "live_limit_price",
    "price_band_checked",
    "margin_available_checked",
    "operator_confirmed",
]


def _object_to_row(obj: Any, snapshot_at: datetime | None = None) -> dict[str, Any]:
    if obj is None:
        return {}
    if is_dataclass(obj):
        row = asdict(obj)
    elif hasattr(obj, "__dict__"):
        row = dict(obj.__dict__)
    else:
        row = {"value": str(obj)}
    for attr in ["vt_symbol", "vt_orderid", "vt_tradeid", "vt_positionid", "vt_accountid", "available"]:
        if hasattr(obj, attr):
            row[attr] = getattr(obj, attr)
    for key, value in list(row.items()):
        if isinstance(value, (datetime, pd.Timestamp)):
            row[key] = value.isoformat()
        elif hasattr(value, "value"):
            row[key] = value.value
        elif value is None:
            row[key] = ""
    if snapshot_at is not None:
        row["snapshot_at"] = snapshot_at.isoformat()
    return row


def collect_snapshot_from_main_engine(main_engine: Any, vt_symbols: list[str], now: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
    """Collect cached live context from an already-connected MainEngine.

    The function does not connect gateways, subscribe symbols, send orders, or
    cancel orders. It only reads the current OMS cache exposed by MainEngine.
    """
    snapshot_at = now or datetime.now()
    contracts: list[dict[str, Any]] = []
    ticks: list[dict[str, Any]] = []
    accounts: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []

    for vt_symbol in vt_symbols:
        get_contract = getattr(main_engine, "get_contract", None)
        get_tick = getattr(main_engine, "get_tick", None)
        if callable(get_contract):
            contract = get_contract(vt_symbol)
            if contract is not None:
                contracts.append(_object_to_row(contract, snapshot_at))
        if callable(get_tick):
            tick = get_tick(vt_symbol)
            if tick is not None:
                ticks.append(_object_to_row(tick, snapshot_at))

    get_accounts = getattr(main_engine, "get_all_accounts", None)
    if callable(get_accounts):
        accounts = [_object_to_row(item, snapshot_at) for item in get_accounts()]

    get_positions = getattr(main_engine, "get_all_positions", None)
    if callable(get_positions):
        positions = [_object_to_row(item, snapshot_at) for item in get_positions()]

    return {
        "contracts": contracts,
        "ticks": ticks,
        "accounts": accounts,
        "positions": positions,
        "meta": [{"snapshot_at": snapshot_at.isoformat(), "source": "main_engine_cache"}],
    }


def _read_csv_rows(path: str | Path | None, snapshot_at: str = "") -> list[dict[str, Any]]:
    if not path:
        return []
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    try:
        frame = pd.read_csv(csv_path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return []
    rows = frame.to_dict(orient="records")
    if snapshot_at:
        for row in rows:
            row.setdefault("snapshot_at", snapshot_at)
            row.setdefault("generated_at", snapshot_at)
    return rows


def load_readonly_snapshot_files(summary: dict[str, Any] | None, source: str = "readonly_probe_files") -> dict[str, list[dict[str, Any]]]:
    """Load persisted read-only CSV outputs into validator snapshots.

    The loader is file-only. It does not refresh broker state, connect CTP, or
    infer missing tick data from historical reference prices.
    """
    summary = summary or {}
    outputs = summary.get("outputs", {}) if isinstance(summary.get("outputs", {}), dict) else {}
    generated_at = clean_text(summary.get("generated_at"))
    broker_snapshot = summary.get("broker_snapshot", {}) if isinstance(summary.get("broker_snapshot", {}), dict) else {}
    position_state = clean_text(broker_snapshot.get("position_snapshot_state"))
    return {
        "contracts": _read_csv_rows(outputs.get("contracts"), generated_at),
        "accounts": _read_csv_rows(outputs.get("accounts"), generated_at),
        "positions": _read_csv_rows(outputs.get("positions"), generated_at),
        "ticks": _read_csv_rows(outputs.get("ticks"), generated_at),
        "meta": [
            {
                "snapshot_at": generated_at,
                "generated_at": generated_at,
                "source": source,
                "status": clean_text(summary.get("status")),
                "position_snapshot_state": position_state,
                "position_rows": broker_snapshot.get("position_rows", ""),
                "nonzero_position_rows": broker_snapshot.get("nonzero_position_rows", ""),
            }
        ],
    }


def load_stage174_readonly_snapshot(summary: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    """Backward-compatible Stage174 file loader."""
    return load_readonly_snapshot_files(summary, source="stage174_readonly_probe_files")


def _parse_datetime(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _age_seconds(row: dict[str, Any], now: datetime, *keys: str) -> float | None:
    for key in keys:
        dt = _parse_datetime(row.get(key))
        if dt is None:
            continue
        if dt.tzinfo is not None and now.tzinfo is None:
            now_for_diff = now.astimezone(dt.tzinfo)
        elif dt.tzinfo is None and now.tzinfo is not None:
            dt = dt.replace(tzinfo=now.tzinfo)
            now_for_diff = now
        else:
            now_for_diff = now
        return round((now_for_diff - dt).total_seconds(), 3)
    return None


def _vt_symbol_from_row(row: dict[str, Any]) -> str:
    vt_symbol = clean_text(row.get("vt_symbol"))
    if vt_symbol:
        return vt_symbol
    symbol = clean_text(row.get("symbol"))
    exchange = clean_text(row.get("exchange"))
    return f"{symbol}.{exchange}" if symbol and exchange else ""


def _lookup_by_vt_symbol(rows: list[dict[str, Any]], vt_symbol: str) -> dict[str, Any] | None:
    target = vt_symbol.lower()
    for row in rows:
        if _vt_symbol_from_row(row).lower() == target:
            return row
    return None


def _account_margin_value(account: dict[str, Any] | None) -> tuple[float, str]:
    """Return broker current margin from explicit account fields only.

    vn.py's CTP gateway maps AccountData.frozen from FrozenMargin/FrozenCash/
    FrozenCommission. That is not the same as CTP CurrMargin, so it must not
    be used as the trigger source for forced margin deleveraging.
    """
    if not account:
        return 0.0, ""
    for key in ACCOUNT_MARGIN_FIELD_CANDIDATES:
        if key not in account:
            continue
        value = to_float(account.get(key), math.nan)
        if not math.isnan(value) and value >= 0:
            return value, key
    return 0.0, ""


def _any_fresh_row(rows: list[dict[str, Any]], now: datetime, max_age_seconds: int) -> tuple[dict[str, Any] | None, float | None]:
    for row in rows:
        age = _age_seconds(row, now, "snapshot_at", "datetime", "localtime", "generated_at")
        if age is not None and age <= max_age_seconds:
            return row, age
    return None, None


def _fresh_symbol_row(rows: list[dict[str, Any]], vt_symbol: str, now: datetime, max_age_seconds: int, *time_keys: str) -> tuple[dict[str, Any] | None, float | None]:
    row = _lookup_by_vt_symbol(rows, vt_symbol)
    if row is None:
        return None, None
    age = _age_seconds(row, now, *(time_keys or ("snapshot_at", "datetime", "localtime", "generated_at")))
    if age is None or age > max_age_seconds:
        return None, age
    return row, age


def _opposite_position_direction(order_direction: str) -> str:
    if order_direction == "long":
        return "short"
    if order_direction == "short":
        return "long"
    return ""


def _position_available(positions: list[dict[str, Any]], vt_symbol: str, direction: str) -> float:
    total = 0.0
    target = vt_symbol.lower()
    for row in positions:
        if _vt_symbol_from_row(row).lower() != target:
            continue
        if normalize_direction(row.get("direction")) != direction:
            continue
        volume = to_float(row.get("volume"), 0.0)
        frozen = to_float(row.get("frozen"), 0.0)
        total += max(0.0, volume - frozen)
    return total


def _derive_limit_price(order_direction: str, row_limit_price: float, tick: dict[str, Any] | None, contract: dict[str, Any] | None, extra_ticks: int = 1) -> tuple[float, str]:
    if row_limit_price > 0:
        return row_limit_price, "explicit_live_limit_price"
    if tick is None or contract is None:
        return 0.0, "missing_tick_or_contract"
    pricetick = to_float(contract.get("pricetick"), 0.0)
    if pricetick <= 0:
        return 0.0, "missing_pricetick"
    bid = to_float(tick.get("bid_price_1"), 0.0)
    ask = to_float(tick.get("ask_price_1"), 0.0)
    last = to_float(tick.get("last_price"), 0.0)
    if order_direction == "long":
        anchor = ask if ask > 0 else last
        price = anchor + max(1, int(extra_ticks)) * pricetick
        limit_up = to_float(tick.get("limit_up"), 0.0)
        if limit_up > 0:
            price = min(price, limit_up)
    elif order_direction == "short":
        anchor = bid if bid > 0 else last
        price = anchor - max(1, int(extra_ticks)) * pricetick
        limit_down = to_float(tick.get("limit_down"), 0.0)
        if limit_down > 0:
            price = max(price, limit_down)
    else:
        return 0.0, "invalid_direction"
    if anchor <= 0:
        return 0.0, "missing_bid_ask_last"
    return round(round(price / pricetick) * pricetick, 10), "derived_from_live_tick"


def _price_band_ok(price: float, tick: dict[str, Any] | None, contract: dict[str, Any] | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if price <= 0:
        reasons.append("missing_live_limit_price")
    if tick is None:
        reasons.append("missing_live_tick")
    if contract is None:
        reasons.append("missing_contract")
    if price <= 0 or tick is None or contract is None:
        return False, reasons
    pricetick = to_float(contract.get("pricetick"), 0.0)
    if not price_on_tick(price, pricetick):
        reasons.append("limit_price_not_on_tick")
    limit_up = to_float(tick.get("limit_up"), 0.0)
    limit_down = to_float(tick.get("limit_down"), 0.0)
    if limit_up > 0 and price > limit_up:
        reasons.append("limit_price_above_limit_up")
    if limit_down > 0 and price < limit_down:
        reasons.append("limit_price_below_limit_down")
    return not reasons, reasons


def _field_result(
    *,
    bridge_signal_id: str,
    vt_symbol: str,
    watch_priority: str,
    required_field: str,
    passed: bool,
    observed: str,
    source: str,
    blocker: str,
) -> dict[str, Any]:
    return {
        "bridge_signal_id": bridge_signal_id,
        "vt_symbol": vt_symbol,
        "watch_priority": watch_priority,
        "required_field": required_field,
        "present_in_adapter": int(bool(passed)),
        "required_before_real_submit": 1,
        "observed": observed,
        "source": source,
        "blocker": blocker,
    }


def evaluate_live_context_for_order(
    order_row: dict[str, Any],
    *,
    snapshots: dict[str, list[dict[str, Any]]] | None,
    now: datetime | None = None,
    operator_confirmed: bool = False,
    max_snapshot_age_seconds: int = 300,
    max_tick_age_seconds: int = 10,
    allow_historical_reference_price: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshots = snapshots or {}
    now = now or datetime.now()
    contracts = snapshots.get("contracts", [])
    accounts = snapshots.get("accounts", [])
    positions = snapshots.get("positions", [])
    ticks = snapshots.get("ticks", [])
    meta = snapshots.get("meta", [])

    bridge_signal_id = clean_text(order_row.get("bridge_signal_id"))
    vt_symbol = clean_text(order_row.get("vt_symbol"))
    watch_priority = clean_text(order_row.get("watch_priority"))
    order_reference = clean_text(order_row.get("order_reference"))
    expected_reference = f"Stage526TCA:{bridge_signal_id}" if bridge_signal_id else ""
    order_direction = normalize_direction(order_row.get("direction"))
    offset = normalize_offset(order_row.get("offset"))
    planned_volume = to_float(order_row.get("planned_volume"), 0.0)
    row_limit_price = to_float(order_row.get("limit_price"), 0.0)
    reference_price = to_float(order_row.get("reference_price"), 0.0)

    field_rows: list[dict[str, Any]] = []
    blockers: list[str] = []

    contract, contract_age = _fresh_symbol_row(contracts, vt_symbol, now, max_snapshot_age_seconds, "snapshot_at", "generated_at")
    contract_ok = bool(contract and to_float(contract.get("size"), 0.0) > 0 and to_float(contract.get("pricetick"), 0.0) > 0)
    if not contract_ok:
        blockers.append("fresh_contract_snapshot_missing_or_invalid")
    field_rows.append(
        _field_result(
            bridge_signal_id=bridge_signal_id,
            vt_symbol=vt_symbol,
            watch_priority=watch_priority,
            required_field="fresh_contract_snapshot",
            passed=contract_ok,
            observed=f"age={contract_age}" if contract_age is not None else "missing",
            source="MainEngine.get_contract / EVENT_CONTRACT",
            blocker="" if contract_ok else "missing_contract_or_size_pricetick",
        )
    )

    account, account_age = _any_fresh_row(accounts, now, max_snapshot_age_seconds)
    account_ok = bool(account and to_float(account.get("balance"), 0.0) > 0)
    if not account_ok:
        blockers.append("fresh_account_snapshot_missing")
    field_rows.append(
        _field_result(
            bridge_signal_id=bridge_signal_id,
            vt_symbol=vt_symbol,
            watch_priority=watch_priority,
            required_field="fresh_account_snapshot",
            passed=account_ok,
            observed=f"age={account_age}" if account_age is not None else "missing",
            source="MainEngine.get_all_accounts / EVENT_ACCOUNT",
            blocker="" if account_ok else "missing_fresh_account_balance",
        )
    )

    position_snapshot_state = clean_text(meta[0].get("position_snapshot_state") if meta else "")
    meta_age = _age_seconds(meta[0] if meta else {}, now, "snapshot_at", "generated_at")
    meta_fresh = meta_age is not None and meta_age <= max_snapshot_age_seconds
    position_row, position_age = _any_fresh_row(positions, now, max_snapshot_age_seconds)
    position_snapshot_ok = bool(position_row) or (meta_fresh and position_snapshot_state in {"confirmed_flat", "positions_received"})
    close_match_ok = True
    close_available = 0.0
    if offset == "close":
        target_direction = _opposite_position_direction(order_direction)
        close_available = _position_available(positions, vt_symbol, target_direction)
        close_match_ok = close_available >= planned_volume > 0
    if not position_snapshot_ok:
        blockers.append("fresh_position_snapshot_missing")
    if position_snapshot_ok and not close_match_ok:
        blockers.append("matching_close_position_missing_or_insufficient")
    field_rows.append(
        _field_result(
            bridge_signal_id=bridge_signal_id,
            vt_symbol=vt_symbol,
            watch_priority=watch_priority,
            required_field="fresh_position_snapshot",
            passed=position_snapshot_ok and close_match_ok,
            observed=f"age={position_age};meta_age={meta_age};close_available={close_available:.4f};state={position_snapshot_state}" if position_age is not None or position_snapshot_state else "missing",
            source="MainEngine.get_all_positions / EVENT_POSITION",
            blocker="" if position_snapshot_ok and close_match_ok else "missing_position_snapshot_or_matching_close_position",
        )
    )

    tick, tick_age = _fresh_symbol_row(ticks, vt_symbol, now, max_tick_age_seconds, "localtime", "datetime", "snapshot_at")
    tick_ok = bool(tick)
    live_limit_price, price_source = _derive_limit_price(order_direction, row_limit_price, tick, contract)
    if not allow_historical_reference_price and row_limit_price <= 0 and not tick_ok:
        blockers.append("live_limit_price_missing_no_historical_fallback_allowed")
    live_limit_ok = live_limit_price > 0 and price_source != "missing_tick_or_contract"
    field_rows.append(
        _field_result(
            bridge_signal_id=bridge_signal_id,
            vt_symbol=vt_symbol,
            watch_priority=watch_priority,
            required_field="live_limit_price",
            passed=live_limit_ok,
            observed=f"{live_limit_price:.6f};source={price_source};tick_age={tick_age}" if live_limit_price > 0 else f"missing;reference_price={reference_price:.6f};fallback_allowed={int(allow_historical_reference_price)}",
            source="MainEngine.get_tick / EVENT_TICK",
            blocker="" if live_limit_ok else "missing_live_tick_or_limit_policy",
        )
    )

    account_equity = to_float(account.get("balance") if account else None, 0.0)
    account_equity_ok = account_equity > 0
    if not account_equity_ok:
        blockers.append("account_equity_before_missing")
    field_rows.append(
        _field_result(
            bridge_signal_id=bridge_signal_id,
            vt_symbol=vt_symbol,
            watch_priority=watch_priority,
            required_field="account_equity_before",
            passed=account_equity_ok,
            observed=f"{account_equity:.2f}" if account_equity > 0 else "missing",
            source="fresh AccountData.balance",
            blocker="" if account_equity_ok else "missing_account_equity_before",
        )
    )

    broker_margin_before, broker_margin_source = _account_margin_value(account)
    broker_margin_ok = bool(account and broker_margin_source and broker_margin_before >= 0)
    if not broker_margin_ok:
        blockers.append("broker_margin_before_missing")
    field_rows.append(
        _field_result(
            bridge_signal_id=bridge_signal_id,
            vt_symbol=vt_symbol,
            watch_priority=watch_priority,
            required_field="broker_margin_before",
            passed=broker_margin_ok,
            observed=f"{broker_margin_before:.2f};source={broker_margin_source}" if broker_margin_ok else "missing_explicit_margin_field",
            source="fresh AccountData explicit margin field / raw CTP CurrMargin",
            blocker="" if broker_margin_ok else "missing_explicit_broker_current_margin",
        )
    )

    band_ok, band_reasons = _price_band_ok(live_limit_price, tick, contract)
    if not band_ok:
        blockers.append("price_band_check_failed")
    field_rows.append(
        _field_result(
            bridge_signal_id=bridge_signal_id,
            vt_symbol=vt_symbol,
            watch_priority=watch_priority,
            required_field="price_band_checked",
            passed=band_ok,
            observed=f"price={live_limit_price:.6f}" if live_limit_price > 0 else "missing",
            source="TickData.limit_up/down + ContractData.pricetick",
            blocker=";".join(band_reasons),
        )
    )

    available = to_float(account.get("available") if account else None, math.nan)
    if math.isnan(available) and account:
        available = to_float(account.get("balance"), 0.0) - to_float(account.get("frozen"), 0.0)
    margin_available_ok = bool(account and not math.isnan(available) and available >= 0 and broker_margin_ok)
    if offset == "open":
        margin_available_ok = margin_available_ok and live_limit_ok and contract_ok
    if not margin_available_ok:
        blockers.append("margin_available_check_failed_or_missing")
    field_rows.append(
        _field_result(
            bridge_signal_id=bridge_signal_id,
            vt_symbol=vt_symbol,
            watch_priority=watch_priority,
            required_field="margin_available_checked",
            passed=margin_available_ok,
            observed=f"available={available:.2f}" if not math.isnan(available) else "missing",
            source="fresh AccountData.available + planned order",
            blocker="" if margin_available_ok else "missing_available_or_margin_model",
        )
    )

    if not operator_confirmed:
        blockers.append("operator_confirmation_missing")
    field_rows.append(
        _field_result(
            bridge_signal_id=bridge_signal_id,
            vt_symbol=vt_symbol,
            watch_priority=watch_priority,
            required_field="operator_confirmed",
            passed=operator_confirmed,
            observed=str(bool(operator_confirmed)),
            source="explicit operator confirmation token",
            blocker="" if operator_confirmed else "operator_confirmation_missing",
        )
    )

    reference_ready = int(bool(order_reference and expected_reference and order_reference == expected_reference))
    payload_ready = int(clean_text(order_row.get("submit_status")) == "dry_run_order_request_payload_ready")
    context_passed = sum(int(row["present_in_adapter"]) for row in field_rows)
    real_submit_allowed = int(reference_ready and payload_ready and context_passed == len(REQUIRED_LIVE_CONTEXT_FIELDS) and not blockers)

    summary = {
        "bridge_signal_id": bridge_signal_id,
        "vt_symbol": vt_symbol,
        "watch_priority": watch_priority,
        "order_reference_ready": reference_ready,
        "dry_run_payload_ready": payload_ready,
        "live_context_passed_fields": context_passed,
        "live_context_total_fields": len(REQUIRED_LIVE_CONTEXT_FIELDS),
        "real_submit_allowed": real_submit_allowed,
        "live_limit_price": live_limit_price,
        "live_limit_price_source": price_source,
        "account_equity_before": account_equity,
        "broker_margin_before": broker_margin_before if broker_margin_ok else 0.0,
        "close_available_volume": close_available,
        "blockers": ";".join(dict.fromkeys(blockers)),
        "next_blocker_class": "ready_for_test_submit" if real_submit_allowed else (blockers[0] if blockers else "unknown_blocker"),
    }
    return field_rows, summary


def evaluate_submit_plan_live_context(
    submit_plan: pd.DataFrame,
    *,
    snapshots: dict[str, list[dict[str, Any]]] | None = None,
    now: datetime | None = None,
    operator_confirmed: bool = False,
    max_snapshot_age_seconds: int = 300,
    max_tick_age_seconds: int = 10,
    allow_historical_reference_price: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for row in submit_plan.to_dict(orient="records"):
        field_rows, summary = evaluate_live_context_for_order(
            row,
            snapshots=snapshots,
            now=now,
            operator_confirmed=operator_confirmed,
            max_snapshot_age_seconds=max_snapshot_age_seconds,
            max_tick_age_seconds=max_tick_age_seconds,
            allow_historical_reference_price=allow_historical_reference_price,
        )
        rows.extend(field_rows)
        summaries.append(summary)
    return pd.DataFrame(rows), pd.DataFrame(summaries)


def build_pre_submit_heatmap_rows(readiness: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    context_lookup = {
        (row["bridge_signal_id"], row["required_field"]): int(row["present_in_adapter"])
        for row in context.to_dict(orient="records")
    }
    for row in readiness.to_dict(orient="records"):
        bridge_signal_id = row["bridge_signal_id"]
        values = {
            "order_reference_ready": int(row["order_reference_ready"]),
            "dry_run_payload_ready": int(row["dry_run_payload_ready"]),
        }
        for field in REQUIRED_LIVE_CONTEXT_FIELDS:
            values[field] = context_lookup.get((bridge_signal_id, field), 0)
        for field in PRE_SUBMIT_HEATMAP_FIELDS:
            rows.append(
                {
                    "bridge_signal_id": bridge_signal_id,
                    "vt_symbol": row["vt_symbol"],
                    "watch_priority": row["watch_priority"],
                    "field": field,
                    "passed": values[field],
                }
            )
    return pd.DataFrame(rows)

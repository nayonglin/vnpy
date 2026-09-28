"""Pure volume/open-interest audits for roll-aware label paths."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


class TradeabilityError(RuntimeError):
    pass


LEG_COLUMNS = [
    "query_date",
    "product_vt_symbol",
    "leg_index",
    "previous_date",
    "return_date",
    "selected_contract_vt",
]


def _require_columns(
    frame: pd.DataFrame, columns: Iterable[str], name: str
) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise TradeabilityError(f"missing_columns:{name}:{','.join(missing)}")


def _date(values: pd.Series) -> pd.Series:
    result = pd.to_datetime(values, errors="coerce").dt.normalize()
    if result.isna().any():
        raise TradeabilityError("invalid_date")
    return result


def audit_leg_endpoints(
    legs: pd.DataFrame,
    liquidity: pd.DataFrame,
) -> pd.DataFrame:
    """Attach endpoint volume/OI and reject stale observations."""
    _require_columns(legs, LEG_COLUMNS, "legs")
    _require_columns(
        liquidity,
        ["date", "contract_vt_symbol", "volume", "open_interest"],
        "liquidity",
    )
    result = legs.copy()
    for column in ("query_date", "previous_date", "return_date"):
        result[column] = _date(result[column])
    if result.duplicated(
        ["query_date", "product_vt_symbol", "leg_index"]
    ).any():
        raise TradeabilityError("duplicate_leg_identity")

    clean = liquidity[
        ["date", "contract_vt_symbol", "volume", "open_interest"]
    ].copy()
    clean["date"] = _date(clean["date"])
    clean["contract_vt_symbol"] = clean["contract_vt_symbol"].astype(str)
    for column in ("volume", "open_interest"):
        clean[column] = pd.to_numeric(clean[column], errors="coerce")
    if clean.duplicated(["date", "contract_vt_symbol"]).any():
        raise TradeabilityError("duplicate_liquidity_identity")

    previous = clean.rename(
        columns={
            "date": "previous_date",
            "contract_vt_symbol": "selected_contract_vt",
            "volume": "previous_volume",
            "open_interest": "previous_open_interest",
        }
    )
    returns = clean.rename(
        columns={
            "date": "return_date",
            "contract_vt_symbol": "selected_contract_vt",
            "volume": "return_volume",
            "open_interest": "return_open_interest",
        }
    )
    result = result.merge(
        previous,
        how="left",
        on=["previous_date", "selected_contract_vt"],
        validate="many_to_one",
    ).merge(
        returns,
        how="left",
        on=["return_date", "selected_contract_vt"],
        validate="many_to_one",
    )
    result["previous_price_quality"] = (
        np.isfinite(result["previous_volume"])
        & np.isfinite(result["previous_open_interest"])
        & result["previous_volume"].gt(0)
        & result["previous_open_interest"].gt(0)
    )
    result["return_price_quality"] = (
        np.isfinite(result["return_volume"])
        & np.isfinite(result["return_open_interest"])
        & result["return_volume"].gt(0)
        & result["return_open_interest"].gt(0)
    )
    reasons = np.full(len(result), "", dtype=object)
    checks = [
        (~np.isfinite(result["previous_volume"]), "previous_volume_missing"),
        (result["previous_volume"].le(0), "previous_volume_nonpositive"),
        (
            ~np.isfinite(result["previous_open_interest"]),
            "previous_open_interest_missing",
        ),
        (
            result["previous_open_interest"].le(0),
            "previous_open_interest_nonpositive",
        ),
        (~np.isfinite(result["return_volume"]), "return_volume_missing"),
        (result["return_volume"].le(0), "return_volume_nonpositive"),
        (
            ~np.isfinite(result["return_open_interest"]),
            "return_open_interest_missing",
        ),
        (
            result["return_open_interest"].le(0),
            "return_open_interest_nonpositive",
        ),
    ]
    for mask, reason in checks:
        assign = np.asarray(mask) & (reasons == "")
        reasons[assign] = reason
    result["price_observation_failure_reason"] = reasons
    result["price_observation_valid"] = reasons == ""
    return result


def build_execution_events(audited_legs: pd.DataFrame) -> pd.DataFrame:
    """Build entry/exit events without treating daily holding as trading."""
    required = [
        *LEG_COLUMNS,
        "previous_volume",
        "previous_open_interest",
        "return_volume",
        "return_open_interest",
    ]
    _require_columns(audited_legs, required, "audited_legs")
    keys = ["query_date", "product_vt_symbol"]
    legs = audited_legs.sort_values([*keys, "leg_index"], kind="mergesort").copy()
    grouped = legs.groupby(keys, sort=False)
    legs["prior_contract_vt"] = grouped["selected_contract_vt"].shift(1)
    legs["prior_return_date"] = grouped["return_date"].shift(1)
    legs["prior_return_volume"] = grouped["return_volume"].shift(1)
    legs["prior_return_open_interest"] = grouped[
        "return_open_interest"
    ].shift(1)
    roll_mask = (
        legs["prior_contract_vt"].notna()
        & legs["selected_contract_vt"].ne(legs["prior_contract_vt"])
    )
    if not legs.loc[roll_mask, "previous_date"].equals(
        legs.loc[roll_mask, "prior_return_date"]
    ):
        raise TradeabilityError("roll_boundary_date_mismatch")
    first = legs.groupby(keys, sort=False).head(1)
    last = legs.groupby(keys, sort=False).tail(1)
    rolls = legs[roll_mask]
    entry = pd.DataFrame(
        {
            "query_date": first["query_date"],
            "product_vt_symbol": first["product_vt_symbol"],
            "leg_index": first["leg_index"],
            "event_role": "entry",
            "event_date": first["previous_date"],
            "contract_vt_symbol": first["selected_contract_vt"],
            "volume": first["previous_volume"],
            "open_interest": first["previous_open_interest"],
            "event_order": 0,
        }
    )
    exit_events = pd.DataFrame(
        {
            "query_date": last["query_date"],
            "product_vt_symbol": last["product_vt_symbol"],
            "leg_index": last["leg_index"],
            "event_role": "exit",
            "event_date": last["return_date"],
            "contract_vt_symbol": last["selected_contract_vt"],
            "volume": last["return_volume"],
            "open_interest": last["return_open_interest"],
            "event_order": 3,
        }
    )
    roll_close = pd.DataFrame(
        {
            "query_date": rolls["query_date"],
            "product_vt_symbol": rolls["product_vt_symbol"],
            "leg_index": rolls["leg_index"],
            "event_role": "roll_close",
            "event_date": rolls["previous_date"],
            "contract_vt_symbol": rolls["prior_contract_vt"],
            "volume": rolls["prior_return_volume"],
            "open_interest": rolls["prior_return_open_interest"],
            "event_order": 1,
        }
    )
    roll_open = pd.DataFrame(
        {
            "query_date": rolls["query_date"],
            "product_vt_symbol": rolls["product_vt_symbol"],
            "leg_index": rolls["leg_index"],
            "event_role": "roll_open",
            "event_date": rolls["previous_date"],
            "contract_vt_symbol": rolls["selected_contract_vt"],
            "volume": rolls["previous_volume"],
            "open_interest": rolls["previous_open_interest"],
            "event_order": 2,
        }
    )
    result = pd.concat(
        [entry, roll_close, roll_open, exit_events], ignore_index=True
    )
    return result.sort_values(
        [*keys, "event_date", "event_order", "leg_index"], kind="mergesort"
    ).reset_index(drop=True)


def assess_event_capacity(
    events: pd.DataFrame,
    *,
    order_quantity: int = 1,
    maximum_share_pct: float = 1.0,
) -> pd.DataFrame:
    """Apply the frozen one-lot 1% volume and OI capacity bounds."""
    _require_columns(
        events,
        [
            "query_date",
            "product_vt_symbol",
            "event_role",
            "event_date",
            "contract_vt_symbol",
            "volume",
            "open_interest",
        ],
        "events",
    )
    if order_quantity <= 0 or not np.isfinite(maximum_share_pct) or maximum_share_pct <= 0:
        raise TradeabilityError("capacity_parameters_invalid")
    result = events.copy()
    result["event_date"] = _date(result["event_date"])
    for column in ("volume", "open_interest"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    minimum_capacity = float(order_quantity) * 100.0 / float(maximum_share_pct)
    result["order_quantity"] = int(order_quantity)
    result["minimum_volume"] = minimum_capacity
    result["minimum_open_interest"] = minimum_capacity
    result["order_volume_share_pct"] = np.where(
        np.isfinite(result["volume"]) & result["volume"].gt(0),
        float(order_quantity) / result["volume"] * 100.0,
        np.inf,
    )
    result["position_oi_share_pct"] = np.where(
        np.isfinite(result["open_interest"]) & result["open_interest"].gt(0),
        float(order_quantity) / result["open_interest"] * 100.0,
        np.inf,
    )
    volume_valid = (
        np.isfinite(result["volume"])
        & result["volume"].ge(minimum_capacity)
    )
    oi_valid = (
        np.isfinite(result["open_interest"])
        & result["open_interest"].ge(minimum_capacity)
    )
    result["volume_capacity_valid"] = volume_valid
    result["open_interest_capacity_valid"] = oi_valid
    result["capacity_valid"] = volume_valid & oi_valid
    reasons = np.full(len(result), "", dtype=object)
    volume_failed = ~np.asarray(volume_valid)
    oi_failed = ~np.asarray(oi_valid)
    reasons[volume_failed & ~oi_failed] = "volume_below_one_lot_capacity"
    reasons[~volume_failed & oi_failed] = (
        "open_interest_below_one_lot_capacity"
    )
    reasons[volume_failed & oi_failed] = (
        "volume_below_one_lot_capacity|open_interest_below_one_lot_capacity"
    )
    result["capacity_failure_reason"] = reasons
    return result

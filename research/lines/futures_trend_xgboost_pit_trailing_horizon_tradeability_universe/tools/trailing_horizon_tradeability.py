"""Causal universe qualification from a mirrored trailing execution horizon."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


class TrailingUniverseError(RuntimeError):
    pass


def _require_columns(
    frame: pd.DataFrame, columns: Iterable[str], name: str
) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise TrailingUniverseError(
            f"missing_columns:{name}:{','.join(missing)}"
        )


def _normalise_dates(
    frame: pd.DataFrame,
    columns: Iterable[str],
    *,
    allow_missing: bool = False,
) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(
            result[column], errors="coerce"
        ).dt.normalize()
        if not allow_missing and result[column].isna().any():
            raise TrailingUniverseError(f"invalid_date:{column}")
    return result


def _global_dates(values: Iterable[object]) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(list(values), errors="coerce"))
    if dates.isna().any():
        raise TrailingUniverseError("invalid_global_date")
    dates = dates.normalize().drop_duplicates().sort_values()
    if dates.empty:
        raise TrailingUniverseError("empty_global_calendar")
    return dates


def build_trailing_windows(
    windows: pd.DataFrame,
    global_dates: Iterable[object],
    *,
    lookback: int = 20,
) -> pd.DataFrame:
    """Mirror each future label window into the immediately preceding horizon."""
    required = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        "entry_date",
        "label_end",
        "source_partition",
    ]
    _require_columns(windows, required, "windows")
    if lookback <= 0:
        raise TrailingUniverseError("invalid_lookback")
    dates = _global_dates(global_dates)
    result = _normalise_dates(
        windows, ["query_date", "entry_date", "label_end"]
    )
    keys = ["query_date", "product_vt_symbol"]
    if result.duplicated(keys).any():
        raise TrailingUniverseError("duplicate_window_identity")
    query_positions = dates.get_indexer(result["query_date"])
    if (query_positions < lookback + 1).any():
        raise TrailingUniverseError("history_calendar_insufficient")
    result = result.rename(
        columns={
            "entry_date": "future_entry_date",
            "label_end": "future_label_end",
        }
    )
    result["entry_date"] = dates.take(query_positions - lookback)
    result["label_end"] = result["query_date"]
    result["history_return_leg_count"] = int(lookback)
    result["history_information_cutoff"] = result["query_date"]
    ordered = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        "entry_date",
        "label_end",
        "source_partition",
        "future_entry_date",
        "future_label_end",
        "history_return_leg_count",
        "history_information_cutoff",
    ]
    optional = [column for column in result.columns if column not in ordered]
    return result[[*ordered, *optional]].sort_values(
        keys, kind="mergesort"
    ).reset_index(drop=True)


def _empty_indexed_summary(
    keys: list[str], columns: list[str]
) -> pd.DataFrame:
    return pd.DataFrame(columns=[*keys, *columns]).set_index(keys)


def build_universe_qualification(
    windows: pd.DataFrame,
    historical_legs: pd.DataFrame,
    historical_audit: pd.DataFrame,
    historical_events: pd.DataFrame,
    future_leg1_mapping: pd.DataFrame,
    *,
    lookback: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select candidates using observations no later than each query date."""
    window_columns = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        "entry_date",
        "label_end",
        "source_partition",
    ]
    _require_columns(windows, window_columns, "windows")
    _require_columns(
        historical_legs,
        [
            "query_date",
            "product_vt_symbol",
            "leg_index",
            "selection_date",
            "previous_date",
            "return_date",
            "selected_contract_vt",
            "roll_event",
            "mapping_valid",
            "expiry_valid",
            "exact_previous_session",
            "leg_valid",
        ],
        "historical_legs",
    )
    _require_columns(
        historical_audit,
        [
            "query_date",
            "product_vt_symbol",
            "leg_index",
            "return_date",
            "price_observation_valid",
        ],
        "historical_audit",
    )
    _require_columns(
        historical_events,
        [
            "query_date",
            "product_vt_symbol",
            "event_role",
            "event_date",
            "capacity_valid",
        ],
        "historical_events",
    )
    _require_columns(
        future_leg1_mapping,
        [
            "execution_date",
            "return_date",
            "selection_date",
            "product_vt_symbol",
            "selected_contract_vt",
            "selected_expire_date",
            "mapping_valid",
            "mapping_failure_reason",
        ],
        "future_leg1_mapping",
    )
    if lookback <= 0:
        raise TrailingUniverseError("invalid_lookback")
    keys = ["query_date", "product_vt_symbol"]
    base = _normalise_dates(
        windows, ["query_date", "entry_date", "label_end"]
    )
    if base.duplicated(keys).any():
        raise TrailingUniverseError("duplicate_window_identity")
    legs = _normalise_dates(
        historical_legs,
        ["query_date", "selection_date", "previous_date", "return_date"],
        allow_missing=True,
    )
    if legs.duplicated([*keys, "leg_index"]).any():
        raise TrailingUniverseError("duplicate_historical_leg_identity")
    audit = _normalise_dates(
        historical_audit, ["query_date", "return_date"], allow_missing=True
    )
    events = _normalise_dates(
        historical_events, ["query_date", "event_date"], allow_missing=True
    )
    future = _normalise_dates(
        future_leg1_mapping,
        [
            "execution_date",
            "return_date",
            "selection_date",
            "selected_expire_date",
        ],
        allow_missing=True,
    )
    if future.duplicated(["execution_date", "product_vt_symbol"]).any():
        raise TrailingUniverseError("duplicate_future_leg1_mapping")

    if legs.empty:
        leg_summary = _empty_indexed_summary(
            keys,
            [
                "historical_leg_count",
                "historical_roll_count",
                "historical_mapping_invalid_leg_count",
                "historical_leg_structure_valid",
                "historical_exact_lag_valid",
                "historical_expiry_valid",
                "historical_max_selection_date",
                "historical_max_return_date",
            ],
        )
    else:
        leg_summary = legs.groupby(keys, sort=False).agg(
            historical_leg_count=("leg_index", "size"),
            historical_roll_count=("roll_event", "sum"),
            historical_mapping_invalid_leg_count=(
                "mapping_valid",
                lambda values: int(
                    (~values.fillna(False).astype(bool)).sum()
                ),
            ),
            historical_leg_structure_valid=("leg_valid", "all"),
            historical_exact_lag_valid=("exact_previous_session", "all"),
            historical_expiry_valid=("expiry_valid", "all"),
            historical_max_selection_date=("selection_date", "max"),
            historical_max_return_date=("return_date", "max"),
        )
    if audit.empty:
        audit_summary = _empty_indexed_summary(
            keys,
            [
                "historical_audited_leg_count",
                "historical_price_invalid_leg_count",
                "historical_price_observation_valid",
                "historical_audit_max_return_date",
            ],
        )
    else:
        audit_summary = audit.groupby(keys, sort=False).agg(
            historical_audited_leg_count=("leg_index", "size"),
            historical_price_invalid_leg_count=(
                "price_observation_valid", lambda values: int((~values).sum())
            ),
            historical_price_observation_valid=(
                "price_observation_valid", "all"
            ),
            historical_audit_max_return_date=("return_date", "max"),
        )
    if events.empty:
        event_summary = _empty_indexed_summary(
            keys,
            [
                "historical_execution_event_count",
                "historical_capacity_invalid_event_count",
                "historical_event_capacity_valid",
                "historical_max_event_date",
            ],
        )
    else:
        event_summary = events.groupby(keys, sort=False).agg(
            historical_execution_event_count=("event_role", "size"),
            historical_capacity_invalid_event_count=(
                "capacity_valid", lambda values: int((~values).sum())
            ),
            historical_event_capacity_valid=("capacity_valid", "all"),
            historical_max_event_date=("event_date", "max"),
        )
    result = (
        base.merge(
            leg_summary.reset_index(), on=keys, how="left", validate="one_to_one"
        )
        .merge(
            audit_summary.reset_index(),
            on=keys,
            how="left",
            validate="one_to_one",
        )
        .merge(
            event_summary.reset_index(),
            on=keys,
            how="left",
            validate="one_to_one",
        )
    )
    future_columns = [
        "execution_date",
        "return_date",
        "selection_date",
        "product_vt_symbol",
        "selected_contract_vt",
        "selected_expire_date",
        "mapping_valid",
        "mapping_failure_reason",
    ]
    future = future[future_columns].rename(
        columns={
            "execution_date": "entry_date",
            "return_date": "future_leg1_return_date",
            "selection_date": "future_leg1_selection_date",
            "selected_contract_vt": "future_leg1_contract_vt",
            "selected_expire_date": "future_leg1_expire_date",
            "mapping_valid": "future_leg1_raw_mapping_valid",
            "mapping_failure_reason": "future_leg1_mapping_failure_reason",
        }
    )
    result = result.merge(
        future,
        on=["entry_date", "product_vt_symbol"],
        how="left",
        validate="many_to_one",
    )
    integer_columns = [
        "historical_leg_count",
        "historical_roll_count",
        "historical_mapping_invalid_leg_count",
        "historical_audited_leg_count",
        "historical_price_invalid_leg_count",
        "historical_execution_event_count",
        "historical_capacity_invalid_event_count",
    ]
    for column in integer_columns:
        result[column] = result[column].fillna(0).astype(int)
    for column in (
        "historical_leg_structure_valid",
        "historical_exact_lag_valid",
        "historical_expiry_valid",
        "historical_price_observation_valid",
        "historical_event_capacity_valid",
        "future_leg1_raw_mapping_valid",
    ):
        result[column] = result[column].eq(True)
    result["historical_expected_event_count"] = (
        2 + 2 * result["historical_roll_count"]
    )
    observation_columns = [
        "historical_max_selection_date",
        "historical_max_return_date",
        "historical_audit_max_return_date",
        "historical_max_event_date",
    ]
    result["historical_observation_max_date"] = result[
        observation_columns
    ].max(axis=1)
    result["historical_future_observation_violation"] = result[
        "historical_observation_max_date"
    ].gt(result["query_date"])
    result["historical_event_structure_valid"] = result[
        "historical_execution_event_count"
    ].eq(result["historical_expected_event_count"])
    result["historical_tradeability_valid"] = (
        result["historical_leg_count"].eq(lookback)
        & result["historical_mapping_invalid_leg_count"].eq(0)
        & result["historical_leg_structure_valid"]
        & result["historical_exact_lag_valid"]
        & result["historical_expiry_valid"]
        & result["historical_audited_leg_count"].eq(lookback)
        & result["historical_price_observation_valid"]
        & result["historical_event_structure_valid"]
        & result["historical_event_capacity_valid"]
        & ~result["historical_future_observation_violation"]
    )
    result["future_leg1_mapping_present"] = result[
        "future_leg1_selection_date"
    ].notna()
    result["future_leg1_same_day_or_future_violation"] = result[
        "future_leg1_selection_date"
    ].ge(result["entry_date"])
    result["future_leg1_query_date_selected"] = result[
        "future_leg1_selection_date"
    ].eq(result["query_date"])
    result["future_leg1_expiry_valid"] = result[
        "future_leg1_expire_date"
    ].ge(result["future_leg1_return_date"])
    result["future_leg1_mapping_valid"] = (
        result["future_leg1_mapping_present"]
        & result["future_leg1_raw_mapping_valid"]
        & result["future_leg1_contract_vt"].notna()
        & result["future_leg1_query_date_selected"]
        & ~result["future_leg1_same_day_or_future_violation"]
        & result["future_leg1_expiry_valid"]
    )
    result["universe_eligible"] = (
        result["historical_tradeability_valid"]
        & result["future_leg1_mapping_valid"]
    )
    reasons = np.full(len(result), "", dtype=object)
    reason_checks = [
        (
            result["historical_leg_count"].ne(lookback)
            | result["historical_mapping_invalid_leg_count"].gt(0)
            | ~result["historical_leg_structure_valid"],
            "historical_mapping_or_structure_invalid",
        ),
        (
            result["historical_future_observation_violation"],
            "historical_observation_after_query",
        ),
        (
            result["historical_audited_leg_count"].ne(lookback)
            | ~result["historical_price_observation_valid"],
            "historical_endpoint_quality_invalid",
        ),
        (
            ~result["historical_event_structure_valid"],
            "historical_event_structure_invalid",
        ),
        (
            ~result["historical_event_capacity_valid"],
            "historical_event_capacity_invalid",
        ),
        (
            ~result["future_leg1_mapping_present"]
            | ~result["future_leg1_raw_mapping_valid"],
            "future_leg1_mapping_invalid",
        ),
        (
            result["future_leg1_mapping_present"]
            & ~result["future_leg1_query_date_selected"],
            "future_leg1_not_query_date_selected",
        ),
        (
            result["future_leg1_mapping_present"]
            & ~result["future_leg1_expiry_valid"],
            "future_leg1_expiry_invalid",
        ),
    ]
    for mask, reason in reason_checks:
        assign = np.asarray(mask) & (reasons == "")
        reasons[assign] = reason
    result["universe_rejection_reason"] = reasons
    result.loc[result["universe_eligible"], "universe_rejection_reason"] = ""
    result = result.sort_values(keys, kind="mergesort").reset_index(drop=True)
    selected = result.loc[result["universe_eligible"], window_columns].copy()
    return result, selected.reset_index(drop=True)

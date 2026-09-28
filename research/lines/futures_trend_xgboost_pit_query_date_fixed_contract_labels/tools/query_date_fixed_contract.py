"""Causal query-date contract selection and fixed-horizon path construction."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


class FixedContractError(RuntimeError):
    pass


WINDOW_COLUMNS = [
    "query_date",
    "product_vt_symbol",
    "main_contract_vt",
    "entry_date",
    "label_end",
    "source_partition",
]


def _require_columns(
    frame: pd.DataFrame, columns: Iterable[str], name: str
) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise FixedContractError(f"missing_columns:{name}:{','.join(missing)}")


def _date(values: pd.Series) -> pd.Series:
    result = pd.to_datetime(values, errors="coerce").dt.normalize()
    if result.isna().any():
        raise FixedContractError("invalid_date")
    return result


def _calendar(values: Iterable[pd.Timestamp]) -> pd.DatetimeIndex:
    result = pd.DatetimeIndex(pd.to_datetime(list(values), errors="coerce"))
    result = result[~result.isna()].normalize().unique().sort_values()
    if result.empty:
        raise FixedContractError("empty_global_calendar")
    return result


def _normalise_windows(windows: pd.DataFrame) -> pd.DataFrame:
    _require_columns(windows, WINDOW_COLUMNS, "windows")
    result = windows[WINDOW_COLUMNS].copy()
    for column in ("query_date", "entry_date", "label_end"):
        result[column] = _date(result[column])
    for column in (
        "product_vt_symbol",
        "main_contract_vt",
        "source_partition",
    ):
        result[column] = result[column].astype(str).str.strip()
        if result[column].eq("").any():
            raise FixedContractError(f"invalid_identity:{column}")
    if result.duplicated(["query_date", "product_vt_symbol"]).any():
        raise FixedContractError("duplicate_window_identity")
    return result.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def _history_counts(
    candidates: pd.DataFrame,
    liquidity: pd.DataFrame,
    *,
    history_window: int,
    minimum_volume: float,
    minimum_open_interest: float,
) -> tuple[np.ndarray, np.ndarray]:
    observations = np.zeros(len(candidates), dtype=np.int64)
    capacity_days = np.zeros(len(candidates), dtype=np.int64)
    histories = liquidity.sort_values(
        ["contract_vt_symbol", "session_position"], kind="mergesort"
    ).groupby("contract_vt_symbol", sort=False)
    for contract, candidate_group in candidates.groupby(
        "contract_vt_symbol", sort=False
    ):
        history = histories.get_group(contract)
        positions = history["session_position"].to_numpy(dtype=np.int64)
        valid = (
            np.isfinite(history["volume"])
            & np.isfinite(history["open_interest"])
            & history["volume"].ge(minimum_volume)
            & history["open_interest"].ge(minimum_open_interest)
        ).to_numpy(dtype=np.int64)
        prefix = np.concatenate(([0], np.cumsum(valid, dtype=np.int64)))
        query_positions = candidate_group["query_position"].to_numpy(
            dtype=np.int64
        )
        left = np.searchsorted(
            positions, query_positions - history_window + 1, side="left"
        )
        right = np.searchsorted(positions, query_positions, side="right")
        row_positions = candidates.index.get_indexer(candidate_group.index)
        observations[row_positions] = right - left
        capacity_days[row_positions] = prefix[right] - prefix[left]
    return observations, capacity_days


def select_query_date_contracts(
    windows: pd.DataFrame,
    catalog: pd.DataFrame,
    liquidity: pd.DataFrame,
    global_dates: Iterable[pd.Timestamp],
    *,
    history_window: int = 20,
    required_capacity_days: int = 18,
    minimum_volume: float = 100.0,
    minimum_open_interest: float = 100.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Select one expiry-covering contract using query-date-visible data."""
    if (
        history_window <= 0
        or required_capacity_days <= 0
        or required_capacity_days > history_window
        or not np.isfinite(minimum_volume)
        or not np.isfinite(minimum_open_interest)
        or minimum_volume <= 0
        or minimum_open_interest <= 0
    ):
        raise FixedContractError("selection_parameters_invalid")

    clean_windows = _normalise_windows(windows)
    clean_windows["selection_row"] = np.arange(
        len(clean_windows), dtype=np.int64
    )
    calendar = _calendar(global_dates)
    calendar_positions = pd.Series(
        np.arange(len(calendar), dtype=np.int64), index=calendar
    )
    query_positions = clean_windows["query_date"].map(calendar_positions)
    if query_positions.isna().any():
        raise FixedContractError("query_date_outside_calendar")
    if query_positions.lt(history_window - 1).any():
        raise FixedContractError("insufficient_calendar_history")
    clean_windows["query_position"] = query_positions.astype(np.int64)

    _require_columns(
        catalog,
        ["vt_symbol", "product_vt_symbol", "expire_date"],
        "catalog",
    )
    clean_catalog = catalog[
        ["vt_symbol", "product_vt_symbol", "expire_date"]
    ].copy()
    clean_catalog["contract_vt_symbol"] = (
        clean_catalog["vt_symbol"].astype(str).str.strip()
    )
    clean_catalog["product_vt_symbol"] = (
        clean_catalog["product_vt_symbol"].astype(str).str.strip()
    )
    clean_catalog["expire_date"] = _date(clean_catalog["expire_date"])
    if clean_catalog.duplicated("contract_vt_symbol").any():
        raise FixedContractError("duplicate_catalog_contract")

    _require_columns(
        liquidity,
        ["date", "contract_vt_symbol", "volume", "open_interest"],
        "liquidity",
    )
    clean_liquidity = liquidity[
        ["date", "contract_vt_symbol", "volume", "open_interest"]
    ].copy()
    clean_liquidity["date"] = _date(clean_liquidity["date"])
    clean_liquidity["contract_vt_symbol"] = (
        clean_liquidity["contract_vt_symbol"].astype(str).str.strip()
    )
    for column in ("volume", "open_interest"):
        clean_liquidity[column] = pd.to_numeric(
            clean_liquidity[column], errors="coerce"
        ).astype(float)
    if clean_liquidity.duplicated(["date", "contract_vt_symbol"]).any():
        raise FixedContractError("duplicate_liquidity_identity")
    clean_liquidity["session_position"] = clean_liquidity["date"].map(
        calendar_positions
    )
    clean_liquidity = clean_liquidity[
        clean_liquidity["session_position"].notna()
    ].copy()
    clean_liquidity["session_position"] = clean_liquidity[
        "session_position"
    ].astype(np.int64)

    query_chain = clean_liquidity.merge(
        clean_catalog.drop(columns="vt_symbol"),
        how="inner",
        on="contract_vt_symbol",
        validate="many_to_one",
    ).rename(
        columns={
            "date": "query_date",
            "volume": "query_volume",
            "open_interest": "query_open_interest",
        }
    )
    candidates = clean_windows.merge(
        query_chain[
            [
                "query_date",
                "product_vt_symbol",
                "contract_vt_symbol",
                "expire_date",
                "query_volume",
                "query_open_interest",
            ]
        ],
        how="inner",
        on=["query_date", "product_vt_symbol"],
        validate="one_to_many",
    ).reset_index(drop=True)
    candidates["future_selection_rows_used"] = 0
    if not candidates.empty:
        observations, capacity_days = _history_counts(
            candidates,
            clean_liquidity,
            history_window=history_window,
            minimum_volume=minimum_volume,
            minimum_open_interest=minimum_open_interest,
        )
        candidates["history_observation_days"] = observations
        candidates[f"capacity_days_{history_window}"] = capacity_days
    else:
        candidates["history_observation_days"] = pd.Series(dtype="int64")
        candidates[f"capacity_days_{history_window}"] = pd.Series(dtype="int64")
    candidates["history_missing_days"] = (
        history_window - candidates["history_observation_days"]
    )
    candidates["query_volume_capacity_valid"] = (
        np.isfinite(candidates["query_volume"])
        & candidates["query_volume"].ge(minimum_volume)
    )
    candidates["query_open_interest_capacity_valid"] = (
        np.isfinite(candidates["query_open_interest"])
        & candidates["query_open_interest"].ge(minimum_open_interest)
    )
    candidates["expiry_valid"] = candidates["expire_date"].ge(
        candidates["label_end"]
    )
    candidates["history_capacity_valid"] = candidates[
        f"capacity_days_{history_window}"
    ].ge(required_capacity_days)
    candidates["selection_eligible"] = (
        candidates["expiry_valid"]
        & candidates["query_volume_capacity_valid"]
        & candidates["query_open_interest_capacity_valid"]
        & candidates["history_capacity_valid"]
    )

    reasons = np.full(len(candidates), "", dtype=object)
    checks = [
        (~candidates["expiry_valid"], "expires_before_label_end"),
        (
            candidates["expiry_valid"]
            & ~candidates["query_volume_capacity_valid"],
            "query_volume_below_minimum",
        ),
        (
            candidates["expiry_valid"]
            & candidates["query_volume_capacity_valid"]
            & ~candidates["query_open_interest_capacity_valid"],
            "query_open_interest_below_minimum",
        ),
        (
            candidates["expiry_valid"]
            & candidates["query_volume_capacity_valid"]
            & candidates["query_open_interest_capacity_valid"]
            & ~candidates["history_capacity_valid"],
            f"history_capacity_days_below_{required_capacity_days}",
        ),
    ]
    for mask, reason in checks:
        assign = np.asarray(mask) & (reasons == "")
        reasons[assign] = reason
    candidates["selection_failure_reason"] = reasons

    eligible = candidates[candidates["selection_eligible"]].sort_values(
        [
            "selection_row",
            "query_open_interest",
            "query_volume",
            "expire_date",
            "contract_vt_symbol",
        ],
        ascending=[True, False, False, True, True],
        kind="mergesort",
    )
    eligible = eligible.copy()
    eligible["selection_rank"] = (
        eligible.groupby("selection_row", sort=False).cumcount() + 1
    )
    candidates = candidates.merge(
        eligible[["selection_row", "contract_vt_symbol", "selection_rank"]],
        how="left",
        on=["selection_row", "contract_vt_symbol"],
        validate="one_to_one",
    )
    selected = eligible[eligible["selection_rank"].eq(1)].copy()
    selected = selected.rename(
        columns={
            "contract_vt_symbol": "selected_contract_vt",
            "expire_date": "selected_expire_date",
            f"capacity_days_{history_window}": "capacity_days_20",
        }
    )
    selected["selection_source_date"] = selected["query_date"]
    selected["future_selection_rows_used"] = 0
    selected = selected.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    candidates = candidates.rename(
        columns={f"capacity_days_{history_window}": "capacity_days_20"}
    ).sort_values(
        ["query_date", "product_vt_symbol", "contract_vt_symbol"],
        kind="mergesort",
    ).reset_index(drop=True)
    rejected = candidates[~candidates["selection_eligible"]].reset_index(
        drop=True
    )
    return selected, candidates, rejected


def build_fixed_contract_legs(
    selected: pd.DataFrame,
    global_dates: Iterable[pd.Timestamp],
    *,
    holding_period: int = 20,
) -> pd.DataFrame:
    """Build a same-contract path from next session through label end."""
    if holding_period <= 0:
        raise FixedContractError("invalid_holding_period")
    required = [
        *WINDOW_COLUMNS,
        "selected_contract_vt",
        "selected_expire_date",
    ]
    _require_columns(selected, required, "selected")
    windows = selected.copy()
    for column in (
        "query_date",
        "entry_date",
        "label_end",
        "selected_expire_date",
    ):
        windows[column] = _date(windows[column])
    calendar = _calendar(global_dates)
    positions = pd.Series(np.arange(len(calendar), dtype=np.int64), index=calendar)
    query_positions = windows["query_date"].map(positions)
    if query_positions.isna().any():
        raise FixedContractError("query_date_outside_calendar")
    query_positions = query_positions.astype(np.int64)
    if (query_positions + holding_period + 1 >= len(calendar)).any():
        raise FixedContractError("label_end_outside_calendar")
    expected_entry = calendar.take((query_positions + 1).to_numpy())
    expected_end = calendar.take(
        (query_positions + holding_period + 1).to_numpy()
    )
    if not np.array_equal(windows["entry_date"].to_numpy(), expected_entry):
        raise FixedContractError("entry_date_calendar_mismatch")
    if not np.array_equal(windows["label_end"].to_numpy(), expected_end):
        raise FixedContractError("label_end_calendar_mismatch")
    if windows["selected_expire_date"].lt(windows["label_end"]).any():
        raise FixedContractError("selected_contract_expires_before_label_end")

    repeated = windows.loc[
        windows.index.repeat(holding_period)
    ].reset_index(drop=True)
    leg_index = np.tile(np.arange(1, holding_period + 1), len(windows))
    repeated_query_positions = np.repeat(query_positions.to_numpy(), holding_period)
    repeated["leg_index"] = leg_index
    repeated["previous_date"] = calendar.take(
        repeated_query_positions + leg_index
    )
    repeated["return_date"] = calendar.take(
        repeated_query_positions + leg_index + 1
    )
    repeated["roll_event"] = False
    return repeated.sort_values(
        ["query_date", "product_vt_symbol", "leg_index"], kind="mergesort"
    ).reset_index(drop=True)

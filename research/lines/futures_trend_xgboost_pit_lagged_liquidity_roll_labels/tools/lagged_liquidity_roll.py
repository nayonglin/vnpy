"""Causal daily contract mapping from prior-session liquidity only."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd


class LaggedRollError(RuntimeError):
    pass


def _require_columns(
    frame: pd.DataFrame, columns: Iterable[str], name: str
) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise LaggedRollError(f"missing_columns:{name}:{','.join(missing)}")


def _dates(values: Iterable[object], *, allow_missing: bool = False) -> pd.Series:
    result = pd.to_datetime(pd.Series(values), errors="coerce").dt.normalize()
    if not allow_missing and result.isna().any():
        raise LaggedRollError("invalid_date")
    return result


def _global_dates(values: Iterable[object]) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(list(values), errors="coerce"))
    if dates.isna().any():
        raise LaggedRollError("invalid_global_date")
    dates = dates.normalize().drop_duplicates().sort_values()
    if len(dates) < 3:
        raise LaggedRollError("insufficient_global_dates")
    return dates


def _clean_catalog(catalog: pd.DataFrame) -> pd.DataFrame:
    _require_columns(
        catalog,
        ["vt_symbol", "product_vt_symbol", "expire_date"],
        "catalog",
    )
    result = catalog[
        ["vt_symbol", "product_vt_symbol", "expire_date"]
    ].copy()
    result["vt_symbol"] = result["vt_symbol"].astype(str)
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)
    result["expire_date"] = _dates(result["expire_date"])
    if result.duplicated("vt_symbol").any():
        raise LaggedRollError("duplicate_catalog_contract")
    return result


def _clean_liquidity(liquidity: pd.DataFrame) -> pd.DataFrame:
    _require_columns(
        liquidity,
        ["date", "contract_vt_symbol", "volume", "open_interest"],
        "liquidity",
    )
    result = liquidity[
        ["date", "contract_vt_symbol", "volume", "open_interest"]
    ].copy()
    result["date"] = _dates(result["date"])
    result["contract_vt_symbol"] = result["contract_vt_symbol"].astype(str)
    for column in ("volume", "open_interest"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result.duplicated(["date", "contract_vt_symbol"]).any():
        raise LaggedRollError("duplicate_liquidity_identity")
    return result


def _build_requests(
    execution_dates: Sequence[object] | pd.Series | pd.DatetimeIndex,
    products: Sequence[str] | pd.Series | pd.Index,
    dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    executions = pd.DatetimeIndex(
        pd.to_datetime(list(execution_dates), errors="coerce")
    )
    if executions.isna().any():
        raise LaggedRollError("invalid_execution_date")
    executions = executions.normalize().drop_duplicates().sort_values()
    product_values = pd.Index([str(value) for value in products]).drop_duplicates()
    if executions.empty or product_values.empty:
        raise LaggedRollError("empty_mapping_request")
    positions = dates.get_indexer(executions)
    if (positions < 1).any() or (positions >= len(dates) - 1).any():
        raise LaggedRollError("execution_date_without_adjacent_sessions")
    date_frame = pd.DataFrame(
        {
            "execution_date": executions,
            "selection_date": dates.take(positions - 1),
            "return_date": dates.take(positions + 1),
        }
    )
    product_frame = pd.DataFrame(
        {"product_vt_symbol": product_values.astype(str)}
    )
    requests = date_frame.merge(product_frame, how="cross")
    requests = requests.sort_values(
        ["product_vt_symbol", "execution_date"], kind="mergesort"
    ).reset_index(drop=True)
    requests["request_id"] = np.arange(len(requests), dtype=np.int64)
    return requests


def build_lagged_contract_map(
    execution_dates: Sequence[object] | pd.Series | pd.DatetimeIndex,
    products: Sequence[str] | pd.Series | pd.Index,
    catalog: pd.DataFrame,
    liquidity: pd.DataFrame,
    global_dates: Iterable[object],
    *,
    minimum_volume: float = 100.0,
    minimum_open_interest: float = 100.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select each execution day's contract from the immediately prior session."""
    if (
        not np.isfinite(minimum_volume)
        or not np.isfinite(minimum_open_interest)
        or minimum_volume <= 0
        or minimum_open_interest <= 0
    ):
        raise LaggedRollError("invalid_capacity_threshold")
    dates = _global_dates(global_dates)
    requests = _build_requests(execution_dates, products, dates)
    clean_catalog = _clean_catalog(catalog).rename(
        columns={"vt_symbol": "contract_vt_symbol"}
    )
    clean_liquidity = _clean_liquidity(liquidity)
    chain = clean_liquidity.merge(
        clean_catalog,
        how="inner",
        on="contract_vt_symbol",
        validate="many_to_one",
    )
    candidates = requests.merge(
        chain,
        how="inner",
        left_on=["selection_date", "product_vt_symbol"],
        right_on=["date", "product_vt_symbol"],
        validate="one_to_many",
    ).drop(columns="date")
    candidates["future_or_same_day_source"] = candidates[
        "selection_date"
    ].ge(candidates["execution_date"])
    candidates["volume_capacity_valid"] = (
        np.isfinite(candidates["volume"])
        & candidates["volume"].ge(minimum_volume)
    )
    candidates["open_interest_capacity_valid"] = (
        np.isfinite(candidates["open_interest"])
        & candidates["open_interest"].ge(minimum_open_interest)
    )
    candidates["capacity_valid"] = (
        candidates["volume_capacity_valid"]
        & candidates["open_interest_capacity_valid"]
    )
    candidates["expiry_valid"] = candidates["expire_date"].ge(
        candidates["return_date"]
    )
    candidates["raw_selection_eligible"] = (
        ~candidates["future_or_same_day_source"]
        & candidates["capacity_valid"]
        & candidates["expiry_valid"]
    )
    candidates = candidates.sort_values(
        [
            "request_id",
            "open_interest",
            "volume",
            "expire_date",
            "contract_vt_symbol",
        ],
        ascending=[True, False, False, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    candidates["raw_selection_rank"] = pd.Series(
        pd.NA, index=candidates.index, dtype="Int64"
    )
    eligible_index = candidates.index[candidates["raw_selection_eligible"]]
    candidates.loc[eligible_index, "raw_selection_rank"] = (
        candidates.loc[eligible_index]
        .groupby("request_id", sort=False)
        .cumcount()
        .add(1)
        .astype("Int64")
    )
    reasons = np.full(len(candidates), "", dtype=object)
    reason_checks = [
        (
            candidates["future_or_same_day_source"],
            "future_or_same_day_source",
        ),
        (~candidates["expiry_valid"], "expires_before_return_date"),
        (
            candidates["expiry_valid"]
            & ~candidates["volume_capacity_valid"],
            "selection_volume_below_minimum",
        ),
        (
            candidates["expiry_valid"]
            & candidates["volume_capacity_valid"]
            & ~candidates["open_interest_capacity_valid"],
            "selection_open_interest_below_minimum",
        ),
    ]
    for mask, reason in reason_checks:
        assign = np.asarray(mask) & (reasons == "")
        reasons[assign] = reason
    candidates["selection_failure_reason"] = reasons
    candidates["monotone_selection_eligible"] = False
    candidates["monotone_selection_rank"] = pd.Series(
        pd.NA, index=candidates.index, dtype="Int64"
    )
    candidates["selected"] = False

    candidate_groups = {
        int(request_id): group.index
        for request_id, group in candidates.groupby("request_id", sort=False)
    }
    mapping_rows: list[dict[str, object]] = []
    for product, product_requests in requests.groupby(
        "product_vt_symbol", sort=False
    ):
        prior_expiry = pd.NaT
        for request in product_requests.itertuples(index=False):
            index = candidate_groups.get(int(request.request_id), pd.Index([]))
            group = candidates.loc[index]
            raw_eligible = group["raw_selection_eligible"].astype(bool)
            if pd.isna(prior_expiry):
                monotone_eligible = raw_eligible
            else:
                monotone_eligible = raw_eligible & group["expire_date"].ge(
                    prior_expiry
                )
                rejected_rollback = raw_eligible & ~group["expire_date"].ge(
                    prior_expiry
                )
                candidates.loc[
                    group.index[rejected_rollback], "selection_failure_reason"
                ] = "earlier_than_prior_expiry"
            eligible_rows = group.index[monotone_eligible]
            candidates.loc[
                eligible_rows, "monotone_selection_eligible"
            ] = True
            if len(eligible_rows):
                candidates.loc[
                    eligible_rows, "monotone_selection_rank"
                ] = pd.array(
                    np.arange(1, len(eligible_rows) + 1), dtype="Int64"
                )
                selected_index = int(eligible_rows[0])
                candidates.loc[selected_index, "selected"] = True
                selected = candidates.loc[selected_index]
                selected_expiry = pd.Timestamp(selected["expire_date"])
                mapping_valid = True
                failure_reason = ""
                prior_for_row = prior_expiry
                prior_expiry = selected_expiry
                selected_contract = str(selected["contract_vt_symbol"])
                selected_volume = float(selected["volume"])
                selected_open_interest = float(selected["open_interest"])
                selected_rank = 1
            else:
                prior_for_row = prior_expiry
                selected_expiry = pd.NaT
                mapping_valid = False
                failure_reason = (
                    "no_eligible_contract"
                    if pd.isna(prior_expiry)
                    else "no_eligible_same_or_later_contract"
                )
                selected_contract = pd.NA
                selected_volume = np.nan
                selected_open_interest = np.nan
                selected_rank = pd.NA
            mapping_rows.append(
                {
                    "execution_date": request.execution_date,
                    "return_date": request.return_date,
                    "selection_date": request.selection_date,
                    "product_vt_symbol": product,
                    "selected_contract_vt": selected_contract,
                    "selected_expire_date": selected_expiry,
                    "selection_volume": selected_volume,
                    "selection_open_interest": selected_open_interest,
                    "selection_rank": selected_rank,
                    "raw_candidate_count": int(raw_eligible.sum()),
                    "monotone_candidate_count": int(monotone_eligible.sum()),
                    "prior_selected_expire_date": prior_for_row,
                    "mapping_valid": mapping_valid,
                    "mapping_failure_reason": failure_reason,
                }
            )
    mapping = pd.DataFrame(mapping_rows).sort_values(
        ["execution_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    mapping["selection_rank"] = pd.array(
        mapping["selection_rank"], dtype="Int64"
    )
    if mapping.duplicated(["execution_date", "product_vt_symbol"]).any():
        raise LaggedRollError("duplicate_mapping_identity")
    candidates = candidates.sort_values(
        ["execution_date", "product_vt_symbol", "raw_selection_rank", "contract_vt_symbol"],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)
    return mapping, candidates


def build_dynamic_legs(
    windows: pd.DataFrame,
    daily_mapping: pd.DataFrame,
    global_dates: Iterable[object],
    *,
    holding_period: int = 20,
) -> pd.DataFrame:
    """Expand frozen windows and join the causal daily contract mapping."""
    _require_columns(
        windows,
        [
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
            "source_partition",
        ],
        "windows",
    )
    _require_columns(
        daily_mapping,
        [
            "execution_date",
            "return_date",
            "selection_date",
            "product_vt_symbol",
            "selected_contract_vt",
            "selected_expire_date",
            "selection_volume",
            "selection_open_interest",
            "mapping_valid",
            "mapping_failure_reason",
        ],
        "daily_mapping",
    )
    if holding_period <= 0:
        raise LaggedRollError("invalid_holding_period")
    dates = _global_dates(global_dates)
    clean_windows = windows.copy()
    for column in ("query_date", "entry_date", "label_end"):
        clean_windows[column] = _dates(clean_windows[column]).to_numpy()
    keys = ["query_date", "product_vt_symbol"]
    if clean_windows.duplicated(keys).any():
        raise LaggedRollError("duplicate_window_identity")
    entry_positions = dates.get_indexer(clean_windows["entry_date"])
    end_positions = dates.get_indexer(clean_windows["label_end"])
    if (entry_positions < 1).any() or (end_positions < 0).any():
        raise LaggedRollError("window_date_outside_global_calendar")
    if not np.all(end_positions - entry_positions == holding_period):
        raise LaggedRollError("window_holding_period_mismatch")

    repeated_rows = np.repeat(np.arange(len(clean_windows)), holding_period)
    leg_offsets = np.tile(np.arange(holding_period), len(clean_windows))
    legs = clean_windows.iloc[repeated_rows].reset_index(drop=True)
    legs["leg_index"] = leg_offsets + 1
    previous_positions = np.repeat(entry_positions, holding_period) + leg_offsets
    legs["previous_date"] = dates.take(previous_positions)
    legs["return_date"] = dates.take(previous_positions + 1)
    legs["expected_selection_date"] = dates.take(previous_positions - 1)

    mapping = daily_mapping.copy()
    for column in (
        "execution_date",
        "return_date",
        "selection_date",
        "selected_expire_date",
    ):
        mapping[column] = _dates(mapping[column], allow_missing=True).to_numpy()
    if mapping.duplicated(["execution_date", "product_vt_symbol"]).any():
        raise LaggedRollError("duplicate_mapping_identity")
    mapping = mapping.rename(
        columns={
            "execution_date": "previous_date",
            "return_date": "mapping_return_date",
        }
    )
    legs = legs.merge(
        mapping,
        how="left",
        on=["previous_date", "product_vt_symbol"],
        validate="many_to_one",
    )
    mapping_present = legs["mapping_valid"].notna()
    mapping_valid = legs["mapping_valid"].fillna(False).astype(bool)
    exact_previous = legs["selection_date"].eq(
        legs["expected_selection_date"]
    )
    strictly_lagged = legs["selection_date"].lt(legs["previous_date"])
    return_matches = legs["mapping_return_date"].eq(legs["return_date"])
    expiry_valid = legs["selected_expire_date"].ge(legs["return_date"])
    contract_present = legs["selected_contract_vt"].notna()
    legs["mapping_present"] = mapping_present
    legs["exact_previous_session"] = exact_previous
    legs["same_day_or_future_selection_violation"] = (
        legs["selection_date"].notna() & ~strictly_lagged
    )
    legs["selection_after_query"] = legs["selection_date"].gt(
        legs["query_date"]
    )
    legs["expiry_valid"] = expiry_valid
    legs["leg_valid"] = (
        mapping_present
        & mapping_valid
        & exact_previous
        & strictly_lagged
        & return_matches
        & expiry_valid
        & contract_present
    )
    reasons = np.full(len(legs), "", dtype=object)
    for index in legs.index:
        if not mapping_present.iloc[index]:
            reasons[index] = "daily_mapping_missing"
        elif not mapping_valid.iloc[index]:
            reason = str(legs.at[index, "mapping_failure_reason"] or "")
            reasons[index] = reason or "daily_mapping_invalid"
        elif not bool(exact_previous.iloc[index]) or not bool(
            strictly_lagged.iloc[index]
        ):
            reasons[index] = "selection_not_previous_session"
        elif not bool(return_matches.iloc[index]):
            reasons[index] = "mapping_return_date_mismatch"
        elif not bool(expiry_valid.iloc[index]):
            reasons[index] = "selected_contract_expired_before_return"
        elif not bool(contract_present.iloc[index]):
            reasons[index] = "selected_contract_missing"
    legs["leg_failure_reason"] = reasons
    current_contract = legs["selected_contract_vt"].astype("string")
    prior_contract = current_contract.groupby(
        [legs[key] for key in keys], sort=False
    ).shift(1)
    legs["roll_event"] = (
        prior_contract.notna()
        & current_contract.notna()
        & current_contract.ne(prior_contract).fillna(False)
    ).astype(bool)
    return legs.sort_values([*keys, "leg_index"], kind="mergesort").reset_index(
        drop=True
    )

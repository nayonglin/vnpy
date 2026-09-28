"""Pure identity-only transformations for roll-aware product label paths."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


class PlanError(RuntimeError):
    pass


KEY_COLUMNS = ["query_date", "product_vt_symbol"]
IDENTITY_COLUMNS = [*KEY_COLUMNS, "main_contract_vt"]
WINDOW_COLUMNS = [*IDENTITY_COLUMNS, "entry_date", "label_end"]


def _require_columns(
    frame: pd.DataFrame, columns: Iterable[str], name: str
) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise PlanError(f"missing_columns:{name}:{','.join(missing)}")


def _normalise_date(series: pd.Series, *, allow_missing: bool = False) -> pd.Series:
    result = pd.to_datetime(series, errors="coerce").dt.normalize()
    if not allow_missing and result.isna().any():
        raise PlanError("invalid_date")
    return result


def _clean_windows(frame: pd.DataFrame, *, name: str) -> pd.DataFrame:
    _require_columns(frame, WINDOW_COLUMNS, name)
    result = frame[WINDOW_COLUMNS].copy()
    result["query_date"] = _normalise_date(result["query_date"])
    result["entry_date"] = _normalise_date(
        result["entry_date"], allow_missing=True
    )
    result["label_end"] = _normalise_date(
        result["label_end"], allow_missing=True
    )
    for column in ("product_vt_symbol", "main_contract_vt"):
        result[column] = result[column].astype("string").str.strip()
        if result[column].isna().any() or result[column].eq("").any():
            raise PlanError(f"invalid_identity:{name}:{column}")
        result[column] = result[column].astype(str)
    return result


def partition_windows(
    base_panel: pd.DataFrame,
    accepted_label_plan: pd.DataFrame,
    rejected_label_plan: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Partition the frozen base universe without reading any label values."""
    _require_columns(base_panel, IDENTITY_COLUMNS, "base_panel")
    base = base_panel[IDENTITY_COLUMNS].copy()
    base["query_date"] = _normalise_date(base["query_date"])
    for column in ("product_vt_symbol", "main_contract_vt"):
        base[column] = base[column].astype(str).str.strip()
    if base.duplicated(KEY_COLUMNS).any():
        raise PlanError("duplicate_base_key")

    accepted = _clean_windows(accepted_label_plan, name="accepted_label_plan")
    accepted["source_partition"] = "fixed_label_accepted"

    _require_columns(rejected_label_plan, [*WINDOW_COLUMNS, "rejection_reason"], "rejected_label_plan")
    rejected = _clean_windows(rejected_label_plan, name="rejected_label_plan")
    rejected["rejection_reason"] = (
        rejected_label_plan["rejection_reason"].astype(str).str.strip().to_numpy()
    )
    supported = {"exit_bar_missing", "exit_date_outside_cutoff"}
    unexpected = sorted(set(rejected["rejection_reason"]).difference(supported))
    if unexpected:
        raise PlanError("unsupported_rejection_reason:" + ",".join(unexpected))

    exit_missing = rejected[
        rejected["rejection_reason"].eq("exit_bar_missing")
    ].copy()
    exit_missing["source_partition"] = "fixed_exit_bar_missing"
    cutoff = rejected[
        rejected["rejection_reason"].eq("exit_date_outside_cutoff")
    ].copy()
    cutoff["source_partition"] = "fixed_exit_date_outside_cutoff"

    candidates = pd.concat([accepted, exit_missing], ignore_index=True)
    partitioned = pd.concat([candidates, cutoff], ignore_index=True)
    if partitioned.duplicated(KEY_COLUMNS).any():
        raise PlanError("duplicate_partition_key")

    base_identity = base.sort_values(KEY_COLUMNS, kind="mergesort").reset_index(
        drop=True
    )
    partition_identity = partitioned[IDENTITY_COLUMNS].sort_values(
        KEY_COLUMNS, kind="mergesort"
    ).reset_index(drop=True)
    if not base_identity.equals(partition_identity):
        raise PlanError("partition_key_mismatch")
    if candidates[["entry_date", "label_end"]].isna().any().any():
        raise PlanError("candidate_window_missing")

    sort_columns = ["query_date", "product_vt_symbol"]
    candidates = candidates[
        [*WINDOW_COLUMNS, "source_partition"]
    ].sort_values(sort_columns, kind="mergesort").reset_index(drop=True)
    cutoff = cutoff[
        [*WINDOW_COLUMNS, "source_partition", "rejection_reason"]
    ].sort_values(sort_columns, kind="mergesort").reset_index(drop=True)
    diagnostics = {
        "base_rows": int(len(base)),
        "base_qids": int(base["query_date"].nunique()),
        "fixed_label_accepted_rows": int(len(accepted)),
        "fixed_exit_bar_missing_rows": int(len(exit_missing)),
        "exit_date_outside_cutoff_rows": int(len(cutoff)),
        "candidate_rows": int(len(candidates)),
        "cutoff_rows": int(len(cutoff)),
    }
    return candidates, cutoff, diagnostics


def build_roll_aware_paths(
    candidates: pd.DataFrame,
    mapping: pd.DataFrame,
    bar_presence: pd.DataFrame,
    global_dates: Iterable[pd.Timestamp],
    *,
    holding_period: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build identity-only same-contract legs using only prior-known mappings."""
    if holding_period <= 0:
        raise PlanError("invalid_holding_period")
    _require_columns(
        candidates, [*WINDOW_COLUMNS, "source_partition"], "candidates"
    )
    windows = _clean_windows(candidates, name="candidates")
    windows["source_partition"] = candidates["source_partition"].astype(str).to_numpy()
    if windows.duplicated(KEY_COLUMNS).any():
        raise PlanError("duplicate_candidate_key")
    windows = windows.sort_values(KEY_COLUMNS, kind="mergesort").reset_index(
        drop=True
    )
    windows["path_row_id"] = np.arange(len(windows), dtype=np.int64)

    calendar = pd.DatetimeIndex(pd.to_datetime(list(global_dates), errors="coerce"))
    calendar = calendar[~calendar.isna()].normalize().unique().sort_values()
    if calendar.empty:
        raise PlanError("empty_global_calendar")
    calendar_positions = pd.Series(
        np.arange(len(calendar), dtype=np.int64), index=calendar
    )
    query_positions = windows["query_date"].map(calendar_positions)
    if query_positions.isna().any():
        raise PlanError("query_date_outside_calendar")
    query_positions = query_positions.astype(np.int64)
    if (query_positions + holding_period + 1 >= len(calendar)).any():
        raise PlanError("label_end_outside_calendar")
    expected_entry = pd.Series(
        calendar.take((query_positions + 1).to_numpy()), index=windows.index
    )
    expected_end = pd.Series(
        calendar.take((query_positions + holding_period + 1).to_numpy()),
        index=windows.index,
    )
    if not windows["entry_date"].equals(expected_entry) or not windows[
        "label_end"
    ].equals(expected_end):
        raise PlanError("window_calendar_mismatch")

    _require_columns(
        mapping,
        ["date", "continuous_symbol_vt", "main_contract_vt"],
        "mapping",
    )
    clean_mapping = mapping[
        [
            "date",
            "continuous_symbol_vt",
            "main_contract_vt",
            *( ["mapping_resolution"] if "mapping_resolution" in mapping.columns else [] ),
        ]
    ].copy()
    clean_mapping["date"] = _normalise_date(clean_mapping["date"])
    clean_mapping["continuous_symbol_vt"] = (
        clean_mapping["continuous_symbol_vt"].astype("string").str.strip()
    )
    clean_mapping["main_contract_vt"] = (
        clean_mapping["main_contract_vt"].astype("string").str.strip()
    )
    if "mapping_resolution" not in clean_mapping.columns:
        clean_mapping["mapping_resolution"] = "resolved"
    else:
        clean_mapping["mapping_resolution"] = (
            clean_mapping["mapping_resolution"].astype(str).str.strip()
        )
    if clean_mapping.duplicated(["date", "continuous_symbol_vt"]).any():
        raise PlanError("duplicate_mapping_key")
    clean_mapping = clean_mapping.rename(
        columns={
            "date": "mapping_date",
            "continuous_symbol_vt": "product_vt_symbol",
            "main_contract_vt": "mapped_contract_vt",
        }
    )

    if set(bar_presence.columns) != {"date", "contract_vt_symbol"}:
        raise PlanError("bar_presence_columns_invalid")
    presence = bar_presence.copy()
    presence["date"] = _normalise_date(presence["date"])
    presence["contract_vt_symbol"] = (
        presence["contract_vt_symbol"].astype(str).str.strip()
    )
    if presence.duplicated(["date", "contract_vt_symbol"]).any():
        raise PlanError("duplicate_bar_presence")
    presence_index = pd.MultiIndex.from_frame(
        presence[["date", "contract_vt_symbol"]]
    )

    row_indices = np.repeat(windows.index.to_numpy(), holding_period)
    leg_indices = np.tile(
        np.arange(1, holding_period + 1, dtype=np.int16), len(windows)
    )
    repeated = windows.loc[row_indices].reset_index(drop=True)
    repeated["leg_index"] = leg_indices
    repeated_query_positions = np.repeat(query_positions.to_numpy(), holding_period)
    previous_positions = repeated_query_positions + leg_indices
    return_positions = previous_positions + 1
    repeated["previous_date"] = calendar.take(previous_positions)
    repeated["return_date"] = calendar.take(return_positions)
    repeated["mapping_date"] = repeated["previous_date"]
    first_leg = repeated["leg_index"].eq(1)
    repeated.loc[first_leg, "mapping_date"] = repeated.loc[
        first_leg, "query_date"
    ].to_numpy()

    legs = repeated.merge(
        clean_mapping,
        how="left",
        on=["mapping_date", "product_vt_symbol"],
        validate="many_to_one",
    )
    legs["selected_contract_vt"] = legs["mapped_contract_vt"]
    legs.loc[first_leg, "selected_contract_vt"] = legs.loc[
        first_leg, "main_contract_vt"
    ].to_numpy()
    query_mapping_match = (
        ~first_leg
        | legs["mapped_contract_vt"].notna()
        & legs["mapped_contract_vt"].eq(legs["main_contract_vt"])
    )
    mapping_present = (
        legs["mapped_contract_vt"].notna()
        & legs["mapped_contract_vt"].astype("string").str.strip().ne("")
    )
    mapping_resolved = legs["mapping_resolution"].eq("resolved")
    mapping_is_prior = legs["mapping_date"].lt(legs["return_date"])

    previous_keys = pd.MultiIndex.from_arrays(
        [legs["previous_date"], legs["selected_contract_vt"]]
    )
    return_keys = pd.MultiIndex.from_arrays(
        [legs["return_date"], legs["selected_contract_vt"]]
    )
    legs["previous_bar_present"] = previous_keys.isin(presence_index)
    legs["return_bar_present"] = return_keys.isin(presence_index)

    reasons = np.full(len(legs), "", dtype=object)
    reason_masks = [
        (~mapping_present, "mapping_missing"),
        (mapping_present & ~mapping_resolved, "mapping_unresolved"),
        (mapping_present & mapping_resolved & ~query_mapping_match, "query_mapping_mismatch"),
        (mapping_present & mapping_resolved & query_mapping_match & ~mapping_is_prior, "future_mapping"),
        (
            mapping_present
            & mapping_resolved
            & query_mapping_match
            & mapping_is_prior
            & ~legs["previous_bar_present"],
            "previous_bar_missing",
        ),
        (
            mapping_present
            & mapping_resolved
            & query_mapping_match
            & mapping_is_prior
            & legs["previous_bar_present"]
            & ~legs["return_bar_present"],
            "return_bar_missing",
        ),
    ]
    for mask, reason in reason_masks:
        assign = np.asarray(mask) & (reasons == "")
        reasons[assign] = reason
    legs["failure_reason"] = reasons
    legs["leg_valid"] = legs["failure_reason"].eq("")

    previous_contract = legs.groupby("path_row_id", sort=False)[
        "selected_contract_vt"
    ].shift(1)
    legs["roll_event"] = (
        previous_contract.notna()
        & legs["selected_contract_vt"].notna()
        & legs["selected_contract_vt"].ne(previous_contract)
    )

    aggregates = legs.groupby("path_row_id", sort=False).agg(
        leg_count=("leg_index", "size"),
        roll_count=("roll_event", "sum"),
        path_valid=("leg_valid", "all"),
        failure_count=("leg_valid", lambda values: int((~values).sum())),
    )
    summary = windows.merge(
        aggregates.reset_index(), on="path_row_id", validate="one_to_one"
    )
    summary["leg_count"] = summary["leg_count"].astype(int)
    summary["roll_count"] = summary["roll_count"].astype(int)
    summary["failure_count"] = summary["failure_count"].astype(int)

    leg_columns = [
        "query_date",
        "product_vt_symbol",
        "source_partition",
        "leg_index",
        "previous_date",
        "return_date",
        "mapping_date",
        "selected_contract_vt",
        "previous_bar_present",
        "return_bar_present",
        "roll_event",
        "leg_valid",
        "failure_reason",
    ]
    legs = legs[leg_columns].sort_values(
        ["query_date", "product_vt_symbol", "leg_index"], kind="mergesort"
    ).reset_index(drop=True)
    failures = legs[~legs["leg_valid"]].copy().reset_index(drop=True)
    summary = summary[
        [
            *WINDOW_COLUMNS,
            "source_partition",
            "leg_count",
            "roll_count",
            "failure_count",
            "path_valid",
        ]
    ].sort_values(KEY_COLUMNS, kind="mergesort").reset_index(drop=True)
    return summary, legs, failures

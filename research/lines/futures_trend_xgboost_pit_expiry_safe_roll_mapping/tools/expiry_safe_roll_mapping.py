"""Expiry-safe contract selection using mapping-date information only."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


class SelectionError(RuntimeError):
    pass


LEG_COLUMNS = [
    "query_date",
    "product_vt_symbol",
    "leg_index",
    "mapping_date",
    "previous_date",
    "return_date",
    "selected_contract_vt",
]


def _require_columns(
    frame: pd.DataFrame, columns: Iterable[str], name: str
) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise SelectionError(f"missing_columns:{name}:{','.join(missing)}")


def _normalise_date(values: pd.Series) -> pd.Series:
    result = pd.to_datetime(values, errors="coerce").dt.normalize()
    if result.isna().any():
        raise SelectionError("invalid_date")
    return result


def select_expiry_safe_contracts(
    legs: pd.DataFrame,
    catalog: pd.DataFrame,
    liquidity: pd.DataFrame,
) -> pd.DataFrame:
    """Keep contracts that are known to remain valid through return date."""
    _require_columns(legs, LEG_COLUMNS, "legs")
    _require_columns(
        catalog,
        ["vt_symbol", "product_vt_symbol", "expire_date"],
        "catalog",
    )
    _require_columns(
        liquidity,
        ["date", "contract_vt_symbol", "volume", "open_interest"],
        "liquidity",
    )

    result = legs[LEG_COLUMNS].copy()
    for column in ("query_date", "mapping_date", "previous_date", "return_date"):
        result[column] = _normalise_date(result[column])
    if result.duplicated(
        ["query_date", "product_vt_symbol", "leg_index"]
    ).any():
        raise SelectionError("duplicate_leg_identity")
    result["original_contract_vt"] = result["selected_contract_vt"].astype(str)

    clean_catalog = catalog[
        ["vt_symbol", "product_vt_symbol", "expire_date"]
    ].copy()
    clean_catalog["vt_symbol"] = clean_catalog["vt_symbol"].astype(str)
    clean_catalog["expire_date"] = _normalise_date(clean_catalog["expire_date"])
    if clean_catalog.duplicated("vt_symbol").any():
        raise SelectionError("duplicate_catalog_contract")
    catalog_index = clean_catalog.set_index("vt_symbol")
    result["original_expire_date"] = result["original_contract_vt"].map(
        catalog_index["expire_date"]
    )
    if result["original_expire_date"].isna().any():
        raise SelectionError("original_contract_catalog_missing")
    original_products = result["original_contract_vt"].map(
        catalog_index["product_vt_symbol"]
    )
    if not original_products.eq(result["product_vt_symbol"]).all():
        raise SelectionError("original_contract_product_mismatch")

    result["selected_expire_date"] = result["original_expire_date"]
    result["selection_source_date"] = result["mapping_date"]
    result["future_selection_rows_used"] = 0
    result["selection_reason"] = "original_expiry_valid"
    result["expiry_fallback"] = False
    result["fallback_rank"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["fallback_candidate_count"] = 0
    result["fallback_open_interest"] = np.nan
    result["fallback_volume"] = np.nan
    result["selection_valid"] = True
    result["selection_failure_reason"] = ""

    fallback_mask = result["original_expire_date"].lt(result["return_date"])
    if fallback_mask.any():
        result.loc[fallback_mask, "selection_reason"] = "expiry_fallback_failed"
        result.loc[fallback_mask, "expiry_fallback"] = True
        clean_liquidity = liquidity[
            ["date", "contract_vt_symbol", "volume", "open_interest"]
        ].copy()
        clean_liquidity["date"] = _normalise_date(clean_liquidity["date"])
        clean_liquidity["contract_vt_symbol"] = clean_liquidity[
            "contract_vt_symbol"
        ].astype(str)
        for column in ("volume", "open_interest"):
            clean_liquidity[column] = pd.to_numeric(
                clean_liquidity[column], errors="coerce"
            )
        if clean_liquidity.duplicated(["date", "contract_vt_symbol"]).any():
            raise SelectionError("duplicate_liquidity_key")

        requests = result.loc[
            fallback_mask,
            ["product_vt_symbol", "mapping_date", "return_date"],
        ].copy()
        requests["selection_row"] = requests.index
        relevant_dates = set(requests["mapping_date"])
        candidate_universe = clean_liquidity[
            clean_liquidity["date"].isin(relevant_dates)
        ].merge(
            clean_catalog.rename(
                columns={
                    "vt_symbol": "contract_vt_symbol",
                    "product_vt_symbol": "catalog_product_vt_symbol",
                }
            ),
            how="inner",
            on="contract_vt_symbol",
            validate="many_to_one",
        )
        finite_liquidity = (
            np.isfinite(candidate_universe["open_interest"])
            & np.isfinite(candidate_universe["volume"])
            & candidate_universe["open_interest"].ge(0)
            & candidate_universe["volume"].ge(0)
        )
        candidate_universe = candidate_universe[finite_liquidity].copy()
        candidates = requests.merge(
            candidate_universe,
            how="left",
            left_on=["mapping_date", "product_vt_symbol"],
            right_on=["date", "catalog_product_vt_symbol"],
        )
        candidates = candidates[
            candidates["contract_vt_symbol"].notna()
            & candidates["expire_date"].ge(candidates["return_date"])
        ].copy()
        candidates = candidates.sort_values(
            [
                "selection_row",
                "open_interest",
                "volume",
                "expire_date",
                "contract_vt_symbol",
            ],
            ascending=[True, False, False, True, True],
            kind="mergesort",
        )
        candidates["fallback_rank"] = (
            candidates.groupby("selection_row", sort=False).cumcount() + 1
        )
        candidate_counts = candidates.groupby("selection_row", sort=False).size()
        selected = candidates[candidates["fallback_rank"].eq(1)].set_index(
            "selection_row"
        )
        missing_rows = sorted(set(requests["selection_row"]).difference(selected.index))
        if missing_rows:
            result.loc[missing_rows, "selection_valid"] = False
            result.loc[missing_rows, "selection_failure_reason"] = (
                "expiry_fallback_candidate_missing"
            )
        selected_rows = selected.index
        result.loc[selected_rows, "selected_contract_vt"] = selected[
            "contract_vt_symbol"
        ]
        result.loc[selected_rows, "selected_expire_date"] = selected[
            "expire_date"
        ]
        result.loc[selected_rows, "selection_reason"] = (
            "expiry_fallback_liquidity"
        )
        result.loc[selected_rows, "expiry_fallback"] = True
        result.loc[selected_rows, "fallback_rank"] = selected["fallback_rank"].astype(
            "Int64"
        )
        result.loc[selected_rows, "fallback_candidate_count"] = candidate_counts
        result.loc[selected_rows, "fallback_open_interest"] = selected[
            "open_interest"
        ]
        result.loc[selected_rows, "fallback_volume"] = selected["volume"]

    return result


def validate_selected_endpoints(
    selected_legs: pd.DataFrame,
    bar_presence: pd.DataFrame,
) -> pd.DataFrame:
    """Validate frozen selections without using endpoint data to reselect."""
    required = [
        *LEG_COLUMNS,
        "original_contract_vt",
        "selected_expire_date",
        "selection_source_date",
        "selection_valid",
        "selection_failure_reason",
    ]
    _require_columns(selected_legs, required, "selected_legs")
    _require_columns(
        bar_presence, ["date", "contract_vt_symbol"], "bar_presence"
    )
    result = selected_legs.copy()
    for column in (
        "query_date",
        "mapping_date",
        "previous_date",
        "return_date",
        "selected_expire_date",
        "selection_source_date",
    ):
        result[column] = _normalise_date(result[column])

    presence = bar_presence[["date", "contract_vt_symbol"]].copy()
    presence["date"] = _normalise_date(presence["date"])
    presence["contract_vt_symbol"] = presence["contract_vt_symbol"].astype(str)
    if presence.duplicated(["date", "contract_vt_symbol"]).any():
        raise SelectionError("duplicate_bar_presence")
    presence_index = pd.MultiIndex.from_frame(
        presence[["date", "contract_vt_symbol"]]
    )
    previous_keys = pd.MultiIndex.from_arrays(
        [result["previous_date"], result["selected_contract_vt"]]
    )
    return_keys = pd.MultiIndex.from_arrays(
        [result["return_date"], result["selected_contract_vt"]]
    )
    result["previous_bar_present"] = previous_keys.isin(presence_index)
    result["return_bar_present"] = return_keys.isin(presence_index)
    result["endpoint_reselection_count"] = 0

    selection_valid = result["selection_valid"].astype(bool)
    source_valid = (
        result["selection_source_date"].eq(result["mapping_date"])
        & result["selection_source_date"].lt(result["return_date"])
    )
    expiry_valid = result["selected_expire_date"].ge(result["return_date"])
    reasons = np.full(len(result), "", dtype=object)
    reason_masks = [
        (~selection_valid, result["selection_failure_reason"].astype(str)),
        (selection_valid & ~source_valid, "future_or_mismatched_selection_source"),
        (
            selection_valid & source_valid & ~expiry_valid,
            "selected_contract_expired_before_return",
        ),
        (
            selection_valid
            & source_valid
            & expiry_valid
            & ~result["previous_bar_present"],
            "previous_bar_missing_after_selection",
        ),
        (
            selection_valid
            & source_valid
            & expiry_valid
            & result["previous_bar_present"]
            & ~result["return_bar_present"],
            "return_bar_missing_after_selection",
        ),
    ]
    for mask, reason in reason_masks:
        assign = np.asarray(mask) & (reasons == "")
        if isinstance(reason, pd.Series):
            reasons[assign] = reason.to_numpy()[assign]
        else:
            reasons[assign] = reason
    result["failure_reason"] = reasons
    result["leg_valid"] = result["failure_reason"].eq("")
    return result

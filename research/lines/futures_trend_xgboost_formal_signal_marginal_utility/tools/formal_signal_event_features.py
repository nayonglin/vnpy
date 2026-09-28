from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


FIXED_PRODUCT = "fu.SHFE"
ANALYSIS_START = "2020-01-02"
ANALYSIS_END = "2026-08-28"
STATIC_PRE_AI_EVAL_DATE = "2019-12-31"
STATIC_PRE_AI_SCORE_TYPE = "stage182_promoted_static18_pre_ai_boundary"
EXPECTED_DYNAMIC_MODEL_COUNT = 10
EXPECTED_DYNAMIC_EVAL_DATES = (
    "2022-01-28",
    "2022-02-28",
    "2022-03-31",
    "2022-04-29",
    "2022-05-31",
    "2022-06-30",
    "2022-07-29",
    "2022-08-31",
    "2022-09-30",
    "2022-10-31",
    "2022-11-30",
    "2022-12-30",
    "2023-01-31",
    "2023-02-28",
    "2023-03-31",
    "2023-04-28",
    "2023-05-31",
    "2023-06-30",
    "2023-07-31",
    "2023-08-31",
    "2023-09-28",
    "2023-10-31",
    "2023-11-30",
    "2023-12-29",
    "2024-01-31",
    "2024-02-29",
    "2024-03-29",
    "2024-04-30",
    "2024-05-31",
    "2024-06-28",
    "2024-07-31",
    "2024-08-30",
    "2024-09-30",
    "2024-10-31",
    "2024-11-29",
    "2024-12-31",
    "2025-01-27",
    "2025-02-28",
    "2025-03-31",
    "2025-04-30",
    "2025-05-30",
    "2025-06-30",
    "2025-07-31",
    "2025-08-29",
    "2025-09-30",
    "2025-10-31",
    "2025-11-28",
    "2025-12-31",
    "2026-01-30",
    "2026-02-27",
    "2026-03-31",
    "2026-04-30",
    "2026-05-29",
    "2026-06-30",
    "2026-07-31",
    "2026-08-31",
)

FEATURE_COLUMNS = (
    "formal_rank_percentile",
    "formal_score_margin_to_cutoff",
    "directional_rsi",
    "directional_ma_gap",
    "directional_ma_slope",
    "open_interest_change_pct",
    "stop_distance_pct",
    "portfolio_drawdown_pct",
    "margin_to_equity_before",
    "active_positions_fraction",
    "same_direction_correlation",
    "loss_streak",
)

TRACE_COLUMNS = (
    "same_direction_correlation_gate_enabled",
    "same_direction_correlation_active_count",
    "same_direction_correlation_corr_count",
    "same_direction_correlation_candidate_return_count",
    "same_direction_correlation_min_required_count",
    "same_direction_correlation_candidate_history_available",
    "same_direction_correlation_active_count_recomputed",
    "same_direction_correlation_corr_count_recomputed",
    "same_direction_correlation_max_corr_recomputed",
    "same_direction_correlation_trace_exact",
)

IDENTITY_KEYS = (
    "formal_release_id",
    "formal_strategy",
    "official_live_version",
    "formal_material_manifest_sha256",
)

CANDIDATE_REQUIRED_COLUMNS = (
    "candidate_index",
    "datetime",
    "date",
    "product_vt_symbol",
    "contract_vt_symbol",
    "entry_context",
    "direction",
    "signal",
    "candidate_status",
    "is_opened",
    "ai_product_pool_strategy",
    "ai_product_pool_signal_date",
    "ai_product_pool_score",
    "ai_product_pool_rank",
    "ai_product_pool_top_n",
    "rsi_value",
    "ma_mid_value",
    "ma_long_value",
    "ma_mid_prev_value",
    "ma_long_prev_value",
    "planned_entry_price",
    "oi_price_confirm_entry_oi",
    "oi_price_confirm_prev_oi",
    "stop_distance",
    "portfolio_drawdown_pct",
    "estimated_equity",
    "total_margin_in_use_before",
    "active_positions_before",
    "max_concurrent_positions",
    "same_direction_correlation_gate_enabled",
    "same_direction_correlation_active_count",
    "same_direction_correlation_corr_count",
    "same_direction_correlation_max_corr",
    "same_direction_correlation_candidate_return_count",
    "same_direction_correlation_min_required_count",
    "same_direction_correlation_candidate_history_available",
    "same_direction_correlation_active_count_recomputed",
    "same_direction_correlation_corr_count_recomputed",
    "same_direction_correlation_max_corr_recomputed",
    "same_direction_correlation_trace_exact",
    "loss_streak",
)

ELIGIBILITY_REQUIRED_COLUMNS = (
    "strategy",
    "score_type",
    "eval_date",
    "product_vt_symbol",
    "score",
    "score_rank",
    "top_n",
)

OUTPUT_COLUMNS = (
    "event_id",
    "formal_release_id",
    "formal_strategy",
    "official_live_version",
    "formal_material_manifest_sha256",
    "analysis_start",
    "analysis_end",
    "candidate_index",
    "decision_datetime",
    "decision_date",
    "product_vt_symbol",
    "contract_vt_symbol",
    "direction",
    "signal",
    "entry_context",
    "candidate_status",
    "is_opened",
    "ai_eval_date",
    "formal_score_type",
    "formal_score",
    "formal_rank",
    "formal_top_n",
    "formal_model_count",
    "formal_cutoff_score",
    *TRACE_COLUMNS,
    *FEATURE_COLUMNS,
)

FORBIDDEN_OUTPUT_TOKENS = (
    "future",
    "label",
    "realized",
    "gross_pnl",
    "net_pnl",
    "mfe",
    "mae",
    "exit_",
)


class FeatureContractError(RuntimeError):
    pass


class QualificationThresholds:
    def __init__(
        self,
        *,
        min_events: int = 150,
        min_events_per_full_year: int = 24,
        min_events_per_direction: int = 40,
        min_products: int = 15,
        min_unique_per_feature: int = 2,
        min_high_cardinality_features: int = 8,
        high_cardinality_unique_values: int = 20,
        full_years: tuple[int, ...] = (2022, 2023, 2024, 2025),
    ) -> None:
        self.min_events = int(min_events)
        self.min_events_per_full_year = int(min_events_per_full_year)
        self.min_events_per_direction = int(min_events_per_direction)
        self.min_products = int(min_products)
        self.min_unique_per_feature = int(min_unique_per_feature)
        self.min_high_cardinality_features = int(min_high_cardinality_features)
        self.high_cardinality_unique_values = int(high_cardinality_unique_values)
        self.full_years = tuple(int(year) for year in full_years)


def _require_columns(frame: pd.DataFrame, required: tuple[str, ...], source: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise FeatureContractError(f"{source}_columns_missing:{','.join(missing)}")


def _require_identity(identity: Mapping[str, str]) -> dict[str, str]:
    missing = [key for key in IDENTITY_KEYS if not str(identity.get(key, "")).strip()]
    if missing:
        raise FeatureContractError(f"formal_identity_missing:{','.join(missing)}")
    result = {key: str(identity[key]).strip() for key in IDENTITY_KEYS}
    digest = result["formal_material_manifest_sha256"]
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
        raise FeatureContractError("formal_material_manifest_sha256_invalid")
    return result


def _numeric(frame: pd.DataFrame, column: str, source: str = "candidate") -> pd.Series:
    try:
        values = pd.to_numeric(frame[column], errors="raise").astype(float)
    except (TypeError, ValueError) as exc:
        raise FeatureContractError(f"{source}_numeric_invalid:{column}") from exc
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise FeatureContractError(f"{source}_numeric_non_finite:{column}")
    return values


def _integer(frame: pd.DataFrame, column: str, source: str = "candidate") -> pd.Series:
    values = _numeric(frame, column, source)
    rounded = np.rint(values.to_numpy(dtype=float))
    if not np.isclose(
        values.to_numpy(dtype=float),
        rounded,
        rtol=0.0,
        atol=1e-12,
    ).all():
        raise FeatureContractError(f"{source}_integer_invalid:{column}")
    return pd.Series(rounded.astype(np.int64), index=values.index, name=column)


def _positive(frame: pd.DataFrame, column: str) -> pd.Series:
    values = _numeric(frame, column)
    if not values.gt(0.0).all():
        raise FeatureContractError(f"candidate_non_positive:{column}")
    return values


def _canonical_date(series: pd.Series, source: str) -> pd.Series:
    try:
        parsed = pd.to_datetime(series, errors="raise")
    except (TypeError, ValueError) as exc:
        raise FeatureContractError(f"{source}_date_invalid") from exc
    if parsed.isna().any():
        raise FeatureContractError(f"{source}_date_invalid")
    return parsed.dt.date.astype(str)


def _canonical_datetime(series: pd.Series) -> pd.Series:
    try:
        parsed = pd.to_datetime(series, errors="raise")
    except (TypeError, ValueError) as exc:
        raise FeatureContractError("candidate_datetime_invalid") from exc
    if parsed.isna().any():
        raise FeatureContractError("candidate_datetime_invalid")
    return parsed.map(lambda value: pd.Timestamp(value).isoformat())


def _require_text(frame: pd.DataFrame, columns: tuple[str, ...], source: str) -> None:
    for column in columns:
        values = frame[column].fillna("").astype(str).str.strip()
        if values.eq("").any() or values.str.lower().isin({"nan", "nat", "none"}).any():
            raise FeatureContractError(f"{source}_text_missing:{column}")


def _prepare_eligibility(
    eligibility: pd.DataFrame,
    identity: Mapping[str, str],
) -> pd.DataFrame:
    _require_columns(eligibility, ELIGIBILITY_REQUIRED_COLUMNS, "eligibility")
    table = eligibility.loc[:, ELIGIBILITY_REQUIRED_COLUMNS].copy()
    _require_text(
        table,
        ("strategy", "score_type", "product_vt_symbol"),
        "eligibility",
    )
    table["eval_date"] = _canonical_date(table["eval_date"], "eligibility_eval")
    table["score"] = _numeric(table, "score", "eligibility")
    table["score_rank"] = _integer(table, "score_rank", "eligibility")
    table["top_n"] = _integer(table, "top_n", "eligibility")
    if table.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise FeatureContractError("duplicate_eligibility_product_month")
    strategies = set(table["strategy"].astype(str))
    if strategies != {identity["formal_strategy"]}:
        raise FeatureContractError("eligibility_strategy_mismatch")

    static_rows = table["score_type"].astype(str).eq(STATIC_PRE_AI_SCORE_TYPE)
    if int(static_rows.sum()) != 18:
        raise FeatureContractError("eligibility_static_boundary_count")
    if set(table.loc[static_rows, "eval_date"].astype(str)) != {
        STATIC_PRE_AI_EVAL_DATE
    }:
        raise FeatureContractError("eligibility_static_boundary_date")
    observed_dynamic_dates = tuple(
        sorted(
            set(table["eval_date"].astype(str)) - {STATIC_PRE_AI_EVAL_DATE}
        )
    )
    if observed_dynamic_dates != EXPECTED_DYNAMIC_EVAL_DATES:
        raise FeatureContractError("eligibility_dynamic_calendar_mismatch")

    for eval_date, month in table.groupby("eval_date", sort=False):
        if month["top_n"].nunique() != 1 or int(month["top_n"].iloc[0]) != len(month):
            raise FeatureContractError(f"eligibility_top_n_shape:{eval_date}")
        ranks = sorted(int(value) for value in month["score_rank"])
        if ranks != list(range(1, len(month) + 1)):
            raise FeatureContractError(f"eligibility_rank_shape:{eval_date}")
        score_types = set(month["score_type"].astype(str))
        fixed_count = int(month["product_vt_symbol"].eq(FIXED_PRODUCT).sum())
        is_static_boundary = score_types == {STATIC_PRE_AI_SCORE_TYPE}
        if is_static_boundary:
            if (
                eval_date != STATIC_PRE_AI_EVAL_DATE
                or len(month) != 18
                or fixed_count != 0
                or not np.isclose(
                    month["score"].to_numpy(dtype=float),
                    0.0,
                    rtol=0.0,
                    atol=1e-12,
                ).all()
            ):
                raise FeatureContractError(f"eligibility_static_boundary_shape:{eval_date}")
            table.loc[month.index, "ranking_regime"] = "static_pre_ai_excluded"
            continue
        if STATIC_PRE_AI_SCORE_TYPE in score_types:
            raise FeatureContractError(f"eligibility_static_boundary_mixed:{eval_date}")
        if fixed_count != 1:
            raise FeatureContractError(f"eligibility_fixed_product_count:{eval_date}")
        model_count = int((~month["product_vt_symbol"].eq(FIXED_PRODUCT)).sum())
        if model_count != EXPECTED_DYNAMIC_MODEL_COUNT:
            raise FeatureContractError(f"eligibility_dynamic_model_count:{eval_date}")
        if len(month) != EXPECTED_DYNAMIC_MODEL_COUNT + 1:
            raise FeatureContractError(f"eligibility_dynamic_month_shape:{eval_date}")
        fixed_rank = int(month.loc[month["product_vt_symbol"].eq(FIXED_PRODUCT), "score_rank"].iloc[0])
        if fixed_rank != EXPECTED_DYNAMIC_MODEL_COUNT + 1:
            raise FeatureContractError(f"eligibility_fixed_product_not_last:{eval_date}")
        model_ranks = sorted(
            int(value)
            for value in month.loc[
                ~month["product_vt_symbol"].eq(FIXED_PRODUCT), "score_rank"
            ]
        )
        if model_ranks != list(range(1, EXPECTED_DYNAMIC_MODEL_COUNT + 1)):
            raise FeatureContractError(f"eligibility_dynamic_model_rank_shape:{eval_date}")
        table.loc[month.index, "ranking_regime"] = "dynamic_model_ranked"
    return table


def _event_id(row: Mapping[str, Any], identity: Mapping[str, str]) -> str:
    payload = {
        "formal_release_id": identity["formal_release_id"],
        "formal_strategy": identity["formal_strategy"],
        "official_live_version": identity["official_live_version"],
        "formal_material_manifest_sha256": identity[
            "formal_material_manifest_sha256"
        ],
        "analysis_start": ANALYSIS_START,
        "analysis_end": ANALYSIS_END,
        "candidate_index": int(row["candidate_index"]),
        "decision_datetime": str(row["decision_datetime"]),
        "decision_date": str(row["decision_date"]),
        "product_vt_symbol": str(row["product_vt_symbol"]),
        "contract_vt_symbol": str(row["contract_vt_symbol"]),
        "direction": str(row["direction"]),
        "signal": str(row["signal"]),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_output_schema(frame: pd.DataFrame) -> None:
    if tuple(frame.columns) != OUTPUT_COLUMNS:
        raise FeatureContractError("output_schema_drift")
    forbidden = sorted(
        column
        for column in frame.columns
        if any(token in column.lower() for token in FORBIDDEN_OUTPUT_TOKENS)
    )
    if forbidden:
        raise FeatureContractError(f"forbidden_output_columns:{','.join(forbidden)}")


def build_formal_root_event_features(
    candidates: pd.DataFrame,
    eligibility: pd.DataFrame,
    formal_identity: Mapping[str, str],
) -> pd.DataFrame:
    identity = _require_identity(formal_identity)
    _require_columns(candidates, CANDIDATE_REQUIRED_COLUMNS, "candidate")
    table = candidates.loc[:, CANDIDATE_REQUIRED_COLUMNS].copy()
    frozen = _prepare_eligibility(eligibility, identity)

    opened = _integer(table, "is_opened").eq(1)
    root = table["entry_context"].astype(str).eq("flat_entry")
    status = table["candidate_status"].astype(str).eq("opened")
    model_ranked = ~table["product_vt_symbol"].astype(str).eq(FIXED_PRODUCT)
    table = table.loc[opened & root & status & model_ranked].copy().reset_index(drop=True)
    _require_text(
        table,
        (
            "product_vt_symbol",
            "contract_vt_symbol",
            "entry_context",
            "direction",
            "signal",
            "candidate_status",
            "ai_product_pool_strategy",
        ),
        "candidate",
    )
    directions = set(table["direction"].astype(str).str.lower())
    if not directions.issubset({"long", "short"}):
        raise FeatureContractError(f"candidate_direction_invalid:{sorted(directions)}")
    if set(table["ai_product_pool_strategy"].astype(str)) != {identity["formal_strategy"]}:
        raise FeatureContractError("candidate_strategy_mismatch")

    table["decision_datetime"] = _canonical_datetime(table["datetime"])
    table["decision_date"] = _canonical_date(table["date"], "candidate")
    decision_datetime_dates = pd.to_datetime(
        table["decision_datetime"], errors="raise"
    ).map(lambda value: pd.Timestamp(value).date().isoformat())
    if not decision_datetime_dates.equals(table["decision_date"]):
        raise FeatureContractError("candidate_date_datetime_mismatch")
    table["ai_eval_date"] = _canonical_date(
        table["ai_product_pool_signal_date"],
        "candidate_ai_eval",
    )
    decision_dates = pd.to_datetime(table["decision_date"], errors="raise")
    if decision_dates.lt(pd.Timestamp(ANALYSIS_START)).any() or decision_dates.gt(
        pd.Timestamp(ANALYSIS_END)
    ).any():
        raise FeatureContractError("candidate_decision_outside_analysis_interval")
    ai_eval_dates = pd.to_datetime(table["ai_eval_date"], errors="raise")
    if ai_eval_dates.ge(decision_dates).any():
        raise FeatureContractError("candidate_ai_eval_not_before_decision")
    dynamic_eval_dates = set(
        frozen.loc[frozen["ranking_regime"].eq("dynamic_model_ranked"), "eval_date"]
    )
    table = table.loc[table["ai_eval_date"].isin(dynamic_eval_dates)].copy().reset_index(
        drop=True
    )
    if table.empty:
        raise FeatureContractError("no_model_ranked_root_events")
    table["candidate_index"] = _integer(table, "candidate_index")
    if table["candidate_index"].duplicated().any():
        raise FeatureContractError("duplicate_event_identity:candidate_index")

    positive_columns = (
        "planned_entry_price",
        "oi_price_confirm_entry_oi",
        "oi_price_confirm_prev_oi",
        "estimated_equity",
        "max_concurrent_positions",
    )
    values: dict[str, pd.Series] = {
        column: _positive(table, column) for column in positive_columns
    }
    numeric_columns = (
        "ai_product_pool_score",
        "ai_product_pool_rank",
        "ai_product_pool_top_n",
        "rsi_value",
        "ma_mid_value",
        "ma_long_value",
        "ma_mid_prev_value",
        "ma_long_prev_value",
        "stop_distance",
        "portfolio_drawdown_pct",
        "total_margin_in_use_before",
        "active_positions_before",
        "same_direction_correlation_gate_enabled",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_candidate_return_count",
        "same_direction_correlation_min_required_count",
        "same_direction_correlation_candidate_history_available",
        "same_direction_correlation_active_count_recomputed",
        "same_direction_correlation_corr_count_recomputed",
        "same_direction_correlation_max_corr_recomputed",
        "same_direction_correlation_trace_exact",
        "loss_streak",
    )
    values.update({column: _numeric(table, column) for column in numeric_columns})
    for column in (
        "ai_product_pool_rank",
        "ai_product_pool_top_n",
        "active_positions_before",
        "max_concurrent_positions",
        "same_direction_correlation_gate_enabled",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "same_direction_correlation_candidate_return_count",
        "same_direction_correlation_min_required_count",
        "same_direction_correlation_candidate_history_available",
        "same_direction_correlation_active_count_recomputed",
        "same_direction_correlation_corr_count_recomputed",
        "same_direction_correlation_trace_exact",
        "loss_streak",
    ):
        values[column] = _integer(table, column)
    for column in (
        "stop_distance",
        "total_margin_in_use_before",
        "active_positions_before",
        "same_direction_correlation_gate_enabled",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "same_direction_correlation_candidate_return_count",
        "same_direction_correlation_min_required_count",
        "same_direction_correlation_candidate_history_available",
        "same_direction_correlation_active_count_recomputed",
        "same_direction_correlation_corr_count_recomputed",
        "same_direction_correlation_trace_exact",
        "loss_streak",
    ):
        if values[column].lt(0.0).any():
            raise FeatureContractError(f"candidate_negative:{column}")

    correlation_enabled = values["same_direction_correlation_gate_enabled"]
    correlation_active = values["same_direction_correlation_active_count"]
    correlation_count = values["same_direction_correlation_corr_count"]
    correlation_max = values["same_direction_correlation_max_corr"]
    candidate_return_count = values[
        "same_direction_correlation_candidate_return_count"
    ]
    min_required_count = values["same_direction_correlation_min_required_count"]
    history_available = values[
        "same_direction_correlation_candidate_history_available"
    ]
    recomputed_active = values[
        "same_direction_correlation_active_count_recomputed"
    ]
    recomputed_count = values["same_direction_correlation_corr_count_recomputed"]
    recomputed_max = values["same_direction_correlation_max_corr_recomputed"]
    trace_exact = values["same_direction_correlation_trace_exact"]
    if not correlation_enabled.eq(1).all():
        raise FeatureContractError("same_direction_correlation_gate_not_enabled")
    if not min_required_count.gt(0).all():
        raise FeatureContractError("same_direction_correlation_min_required_invalid")
    if (
        not history_available.eq(1).all()
        or candidate_return_count.lt(min_required_count).any()
    ):
        raise FeatureContractError(
            "same_direction_correlation_candidate_history_unavailable"
        )
    if recomputed_count.gt(recomputed_active).any():
        raise FeatureContractError("same_direction_correlation_recomputed_count_invalid")
    if recomputed_count.lt(recomputed_active).any():
        raise FeatureContractError("same_direction_correlation_recomputed_unavailable")
    source_matches_trace = (
        correlation_active.eq(recomputed_active)
        & correlation_count.eq(recomputed_count)
        & pd.Series(
            np.isclose(
                correlation_max.to_numpy(dtype=float),
                recomputed_max.to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-12,
            ),
            index=table.index,
        )
    )
    if not trace_exact.eq(1).all() or not source_matches_trace.all():
        raise FeatureContractError("same_direction_correlation_trace_mismatch")
    if correlation_count.gt(correlation_active).any():
        raise FeatureContractError("same_direction_correlation_count_invalid")
    if correlation_count.lt(correlation_active).any():
        raise FeatureContractError("same_direction_correlation_unavailable")
    zero_active = correlation_active.eq(0)
    if (zero_active & ~np.isclose(correlation_max, 0.0, rtol=0.0, atol=1e-12)).any():
        raise FeatureContractError("same_direction_correlation_zero_semantics_invalid")

    frozen_lookup = frozen.set_index(["eval_date", "product_vt_symbol"], drop=False)
    result_rows: list[dict[str, Any]] = []
    for position, row in table.iterrows():
        lookup_key = (str(row["ai_eval_date"]), str(row["product_vt_symbol"]))
        if lookup_key not in frozen_lookup.index:
            raise FeatureContractError(
                f"candidate_not_in_frozen_eligibility:{lookup_key[0]}:{lookup_key[1]}"
            )
        formal = frozen_lookup.loc[lookup_key]
        if isinstance(formal, pd.DataFrame):
            raise FeatureContractError("duplicate_eligibility_lookup")
        comparisons = {
            "ai_product_pool_score": (float(values["ai_product_pool_score"].loc[position]), float(formal["score"])),
            "ai_product_pool_rank": (float(values["ai_product_pool_rank"].loc[position]), float(formal["score_rank"])),
            "ai_product_pool_top_n": (float(values["ai_product_pool_top_n"].loc[position]), float(formal["top_n"])),
        }
        for column, (observed, expected) in comparisons.items():
            if not np.isclose(observed, expected, rtol=0.0, atol=1e-12):
                raise FeatureContractError(
                    f"candidate_eligibility_value_mismatch:{column}:{lookup_key[0]}:{lookup_key[1]}"
                )

        month = frozen[frozen["eval_date"].eq(lookup_key[0])]
        model_month = month[~month["product_vt_symbol"].eq(FIXED_PRODUCT)].copy()
        model_count = int(len(model_month))
        if model_count != EXPECTED_DYNAMIC_MODEL_COUNT:
            raise FeatureContractError(f"formal_model_month_shape:{lookup_key[0]}")
        formal_rank = int(formal["score_rank"])
        if formal_rank < 1 or formal_rank > model_count:
            raise FeatureContractError(
                f"candidate_not_model_ranked:{lookup_key[0]}:{lookup_key[1]}:{formal_rank}"
            )
        cutoff_rows = model_month[model_month["score_rank"].eq(model_count)]
        if len(cutoff_rows) != 1:
            raise FeatureContractError(f"formal_model_cutoff_shape:{lookup_key[0]}")
        cutoff_score = float(cutoff_rows.iloc[0]["score"])
        direction = str(row["direction"]).lower()
        sign = 1.0 if direction == "long" else -1.0
        entry_price = float(values["planned_entry_price"].loc[position])
        event: dict[str, Any] = {
            **identity,
            "analysis_start": ANALYSIS_START,
            "analysis_end": ANALYSIS_END,
            "candidate_index": int(row["candidate_index"]),
            "decision_datetime": str(row["decision_datetime"]),
            "decision_date": str(row["decision_date"]),
            "product_vt_symbol": str(row["product_vt_symbol"]),
            "contract_vt_symbol": str(row["contract_vt_symbol"]),
            "direction": direction,
            "signal": str(row["signal"]),
            "entry_context": "flat_entry",
            "candidate_status": "opened",
            "is_opened": 1,
            "ai_eval_date": str(row["ai_eval_date"]),
            "formal_score_type": str(formal["score_type"]),
            "formal_score": float(formal["score"]),
            "formal_rank": formal_rank,
            "formal_top_n": int(formal["top_n"]),
            "formal_model_count": model_count,
            "formal_cutoff_score": cutoff_score,
            "same_direction_correlation_gate_enabled": int(
                values["same_direction_correlation_gate_enabled"].loc[position]
            ),
            "same_direction_correlation_active_count": int(
                values["same_direction_correlation_active_count"].loc[position]
            ),
            "same_direction_correlation_corr_count": int(
                values["same_direction_correlation_corr_count"].loc[position]
            ),
            "same_direction_correlation_candidate_return_count": int(
                values[
                    "same_direction_correlation_candidate_return_count"
                ].loc[position]
            ),
            "same_direction_correlation_min_required_count": int(
                values["same_direction_correlation_min_required_count"].loc[position]
            ),
            "same_direction_correlation_candidate_history_available": int(
                values[
                    "same_direction_correlation_candidate_history_available"
                ].loc[position]
            ),
            "same_direction_correlation_active_count_recomputed": int(
                values[
                    "same_direction_correlation_active_count_recomputed"
                ].loc[position]
            ),
            "same_direction_correlation_corr_count_recomputed": int(
                values[
                    "same_direction_correlation_corr_count_recomputed"
                ].loc[position]
            ),
            "same_direction_correlation_max_corr_recomputed": float(
                values[
                    "same_direction_correlation_max_corr_recomputed"
                ].loc[position]
            ),
            "same_direction_correlation_trace_exact": int(
                values["same_direction_correlation_trace_exact"].loc[position]
            ),
            "formal_rank_percentile": 1.0 - (formal_rank - 1.0) / (model_count - 1.0),
            "formal_score_margin_to_cutoff": float(formal["score"]) - cutoff_score,
            "directional_rsi": sign * (float(values["rsi_value"].loc[position]) - 50.0) / 50.0,
            "directional_ma_gap": sign
            * (
                float(values["ma_mid_value"].loc[position])
                - float(values["ma_long_value"].loc[position])
            )
            / entry_price,
            "directional_ma_slope": sign
            * (
                (
                    float(values["ma_mid_value"].loc[position])
                    - float(values["ma_mid_prev_value"].loc[position])
                    + float(values["ma_long_value"].loc[position])
                    - float(values["ma_long_prev_value"].loc[position])
                )
                / 2.0
            )
            / entry_price,
            "open_interest_change_pct": (
                float(values["oi_price_confirm_entry_oi"].loc[position])
                / float(values["oi_price_confirm_prev_oi"].loc[position])
                - 1.0
            ),
            "stop_distance_pct": float(values["stop_distance"].loc[position]) / entry_price,
            "portfolio_drawdown_pct": float(values["portfolio_drawdown_pct"].loc[position]),
            "margin_to_equity_before": float(values["total_margin_in_use_before"].loc[position])
            / float(values["estimated_equity"].loc[position]),
            "active_positions_fraction": float(values["active_positions_before"].loc[position])
            / float(values["max_concurrent_positions"].loc[position]),
            "same_direction_correlation": float(recomputed_max.loc[position]),
            "loss_streak": float(values["loss_streak"].loc[position]),
        }
        event["event_id"] = _event_id(event, identity)
        result_rows.append(event)

    result = pd.DataFrame(result_rows)
    result = result.loc[:, OUTPUT_COLUMNS].sort_values(
        ["decision_date", "candidate_index", "product_vt_symbol"],
        kind="mergesort",
    ).reset_index(drop=True)
    if result.duplicated(
        [
            "formal_release_id",
            "official_live_version",
            "candidate_index",
            "decision_datetime",
            "product_vt_symbol",
            "contract_vt_symbol",
            "direction",
            "signal",
        ]
    ).any() or result["event_id"].duplicated().any():
        raise FeatureContractError("duplicate_event_identity")
    _validate_output_schema(result)
    feature_values = result.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(feature_values).all():
        raise FeatureContractError("feature_matrix_non_finite")
    return result


def evaluate_feature_qualification(
    features: pd.DataFrame,
    *,
    thresholds: QualificationThresholds | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or QualificationThresholds()
    _validate_output_schema(features)
    feature_values = features.loc[:, FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    finite = bool(np.isfinite(feature_values.to_numpy(dtype=float)).all())
    dates = pd.to_datetime(features["decision_date"], errors="coerce")
    yearly_counts = {
        str(year): int(dates.dt.year.eq(year).sum()) for year in thresholds.full_years
    }
    direction_counts = {
        direction: int(features["direction"].astype(str).eq(direction).sum())
        for direction in ("long", "short")
    }
    feature_unique_counts = {
        feature: int(feature_values[feature].nunique(dropna=True))
        for feature in FEATURE_COLUMNS
    }
    high_cardinality_count = sum(
        count >= thresholds.high_cardinality_unique_values
        for count in feature_unique_counts.values()
    )
    fixed_fu_event_count = int(
        features["product_vt_symbol"].astype(str).eq(FIXED_PRODUCT).sum()
    )
    gates = {
        "event_count_min": len(features) >= thresholds.min_events,
        "full_year_coverage_min": all(
            count >= thresholds.min_events_per_full_year
            for count in yearly_counts.values()
        ),
        "direction_coverage_min": all(
            count >= thresholds.min_events_per_direction
            for count in direction_counts.values()
        ),
        "product_coverage_min": features["product_vt_symbol"].nunique()
        >= thresholds.min_products,
        "event_identity_unique": not features["event_id"].duplicated().any(),
        "root_open_semantics": bool(
            features["entry_context"].astype(str).eq("flat_entry").all()
            and features["candidate_status"].astype(str).eq("opened").all()
            and pd.to_numeric(features["is_opened"], errors="coerce").eq(1).all()
        ),
        "fixed_fu_excluded": fixed_fu_event_count == 0,
        "all_features_finite": finite,
        "all_features_nonconstant": all(
            count >= thresholds.min_unique_per_feature
            for count in feature_unique_counts.values()
        ),
        "high_cardinality_feature_count": high_cardinality_count
        >= thresholds.min_high_cardinality_features,
    }
    metrics = {
        "event_count": int(len(features)),
        "feature_count": len(FEATURE_COLUMNS),
        "product_count": int(features["product_vt_symbol"].nunique()),
        "fixed_fu_event_count": fixed_fu_event_count,
        "yearly_counts": yearly_counts,
        "direction_counts": direction_counts,
        "feature_unique_counts": feature_unique_counts,
        "high_cardinality_feature_count": int(high_cardinality_count),
    }
    return {
        "passed": bool(all(gates.values())),
        "gates": gates,
        "metrics": metrics,
    }

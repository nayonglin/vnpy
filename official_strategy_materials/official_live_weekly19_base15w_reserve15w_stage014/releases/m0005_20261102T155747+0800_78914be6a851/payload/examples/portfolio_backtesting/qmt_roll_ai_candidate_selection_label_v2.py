from __future__ import annotations

import numpy as np
import pandas as pd

QUALITY_COLUMN_V2: str = "label_selection_quality_score_v2p"
QUALITY_BUCKET_COLUMN_V2: str = "label_selection_quality_bucket_v2p"
QUALITY_RANK_PCT_COLUMN_V2: str = "label_selection_quality_score_v2p_rank_pct_1d"
QUALITY_RANK_CENTERED_COLUMN_V2: str = "label_selection_quality_score_v2p_rank_centered_1d"
SAMPLE_WEIGHT_COLUMN_V2: str = "label_selection_sample_weight_v2p"


def _clip_series(series: pd.Series, lower: float, upper: float) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0).astype("float64")
    return numeric.clip(lower=lower, upper=upper)


def _excess_positive(series: pd.Series, threshold: float, upper: float) -> pd.Series:
    return (_clip_series(series, threshold, upper) - threshold).clip(lower=0.0)


def _clip01(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0).astype("float64")


def add_selection_quality_v2_labels(samples_df: pd.DataFrame) -> pd.DataFrame:
    if samples_df.empty:
        return samples_df.copy()

    enriched_df = samples_df.copy()

    forward_5d = _clip_series(enriched_df["label_candidate_forward_5d_r_multiple"], -3.0, 4.0)
    forward_10d = _clip_series(enriched_df["label_candidate_forward_10d_r_multiple"], -4.0, 6.0)
    forward_20d = _clip_series(enriched_df["label_candidate_forward_20d_r_multiple"], -5.0, 8.0)
    forward_20d_tail_bonus = _excess_positive(enriched_df["label_candidate_forward_20d_r_multiple"], 5.0, 20.0)

    mfe_20d = _clip_series(enriched_df["label_candidate_20d_mfe_r"], 0.0, 10.0)
    mae_20d = _clip_series(enriched_df["label_candidate_20d_mae_r"], 0.0, 6.0)

    quality_score_v2p = (
        0.20 * forward_5d
        + 0.25 * forward_10d
        + 0.30 * forward_20d
        + 0.10 * forward_20d_tail_bonus
        + 0.15 * mfe_20d
        - 0.20 * mae_20d
    )
    enriched_df[QUALITY_COLUMN_V2] = quality_score_v2p.astype("float64")

    enriched_df[QUALITY_BUCKET_COLUMN_V2] = "small"
    enriched_df.loc[enriched_df[QUALITY_COLUMN_V2] >= 0.0, QUALITY_BUCKET_COLUMN_V2] = "normal"
    enriched_df.loc[enriched_df[QUALITY_COLUMN_V2] >= 1.0, QUALITY_BUCKET_COLUMN_V2] = "large"

    range_tail = _excess_positive(enriched_df["feature_range_pct_zscore_120"], 0.8, 3.5) / (3.5 - 0.8)
    momentum_tail = _excess_positive(enriched_df["feature_ret_20d_zscore_120"], 1.0, 3.5) / (3.5 - 1.0)
    trend_extreme = _excess_positive(
        pd.to_numeric(enriched_df["feature_trend_ma20_gap_pct_cs_rank_centered_1d"], errors="coerce").abs(),
        0.5,
        1.0,
    ) / (1.0 - 0.5)
    structure_extreme = _excess_positive(
        pd.to_numeric(enriched_df["feature_ma20_ma40_gap_pct_cs_zscore_1d"], errors="coerce").abs(),
        1.0,
        4.0,
    ) / (4.0 - 1.0)
    close_position_extreme = _excess_positive(
        pd.to_numeric(enriched_df["feature_close_position_60d_cs_zscore_1d"], errors="coerce").abs(),
        1.0,
        4.0,
    ) / (4.0 - 1.0)

    noise_score = (
        0.28 * _clip01(range_tail)
        + 0.24 * _clip01(momentum_tail)
        + 0.20 * _clip01(trend_extreme)
        + 0.16 * _clip01(structure_extreme)
        + 0.12 * _clip01(close_position_extreme)
    )
    sample_weight = 1.0 - 0.55 * noise_score
    sample_weight = sample_weight.clip(lower=0.35, upper=1.0)
    enriched_df[SAMPLE_WEIGHT_COLUMN_V2] = sample_weight.astype("float64")

    group_size = enriched_df.groupby("candidate_date")["sample_id"].transform("count").astype("float64")
    quality_rank = enriched_df.groupby("candidate_date")[QUALITY_COLUMN_V2].rank(method="average").astype("float64")
    quality_rank_pct = pd.Series(0.5, index=enriched_df.index, dtype="float64")
    mask = group_size > 1
    quality_rank_pct.loc[mask] = (quality_rank.loc[mask] - 1.0) / (group_size.loc[mask] - 1.0)
    enriched_df[QUALITY_RANK_PCT_COLUMN_V2] = quality_rank_pct
    enriched_df[QUALITY_RANK_CENTERED_COLUMN_V2] = (quality_rank_pct - 0.5) * 2.0

    return enriched_df

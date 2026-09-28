"""Label-free, point-in-time futures curve feature construction."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


PASS_DECISION = "stage002_curve_features_pass_ready_for_account_label_contract"
FAIL_DECISION = "stage002_curve_features_fail_stop_no_labels"
RAW_CURVE_FEATURES = [
    "front_next_basis_annualized",
    "full_curve_backwardation_slope",
    "full_curve_fit_rmse",
    "open_interest_hhi",
    "volume_hhi",
    "oi_weighted_maturity_days",
]
CURVE_DELTA_FEATURES = [f"{name}_delta_vs_rank10" for name in RAW_CURVE_FEATURES]
MODEL_FEATURES = [
    "formal_probability_delta_vs_rank10",
    "formal_rank_distance",
    *CURVE_DELTA_FEATURES,
]


class CurveFeatureError(RuntimeError):
    """Raised when the frozen feature contract cannot be evaluated."""


def _required_columns(frame: pd.DataFrame, columns: set[str], name: str) -> None:
    if missing := sorted(columns - set(frame.columns)):
        raise CurveFeatureError(f"{name}_columns_missing:{','.join(missing)}")


def _month_serial(value: pd.Timestamp) -> int:
    return int(value.year * 12 + value.month)


def _normalise_panel(panel: pd.DataFrame) -> pd.DataFrame:
    required = {
        "eval_date",
        "product_vt_symbol",
        "pit_logistic_probability",
        "window_id",
        "a_rank",
        "role",
    }
    _required_columns(panel, required, "panel")
    frame = panel.loc[:, sorted(required)].copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str).str.strip()
    frame["pit_logistic_probability"] = pd.to_numeric(
        frame["pit_logistic_probability"], errors="raise"
    ).astype(float)
    frame["window_id"] = frame["window_id"].astype(str).str.strip()
    frame["a_rank"] = pd.to_numeric(frame["a_rank"], errors="raise").astype(int)
    frame["role"] = frame["role"].astype(str).str.strip()
    if not np.isfinite(frame["pit_logistic_probability"].to_numpy(float)).all():
        raise CurveFeatureError("panel_probability_nonfinite")
    if frame.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise CurveFeatureError("panel_eval_product_duplicate")
    if frame.duplicated(["eval_date", "a_rank"]).any():
        raise CurveFeatureError("panel_eval_rank_duplicate")
    for _, month in frame.groupby("eval_date", sort=True):
        ranks = sorted(month["a_rank"].astype(int).tolist())
        if ranks != list(range(min(ranks), max(ranks) + 1)):
            raise CurveFeatureError("panel_rank_not_contiguous")
        if month["window_id"].nunique() != 1:
            raise CurveFeatureError("panel_month_window_not_unique")
    return frame.sort_values(["eval_date", "a_rank"], kind="mergesort").reset_index(drop=True)


def compute_curve_descriptors(
    snapshots: pd.DataFrame,
    *,
    minimum_contracts: int,
) -> pd.DataFrame:
    if minimum_contracts < 3:
        raise CurveFeatureError("minimum_contracts_below_curve_fit_requirement")
    required = {
        "eval_date",
        "feature_date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "contract_maturity",
        "close_price",
        "open_interest",
        "volume",
    }
    _required_columns(snapshots, required, "snapshots")
    frame = snapshots.loc[:, sorted(required)].copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    frame["feature_date"] = pd.to_datetime(frame["feature_date"], errors="raise").dt.normalize()
    frame["contract_maturity"] = pd.to_datetime(
        frame["contract_maturity"], errors="raise"
    ).dt.normalize()
    for column in ["close_price", "open_interest", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    if not np.isfinite(frame[["close_price", "open_interest", "volume"]].to_numpy(float)).all():
        raise CurveFeatureError("snapshot_numeric_nonfinite")
    if (
        frame["close_price"].le(0.0).any()
        or frame["open_interest"].le(0.0).any()
        or frame["volume"].le(0.0).any()
    ):
        raise CurveFeatureError("snapshot_numeric_nonpositive")
    if not frame["feature_date"].eq(frame["eval_date"]).all():
        raise CurveFeatureError("snapshot_feature_date_not_exact")
    if frame.duplicated(["eval_date", "contract_vt_symbol"]).any():
        raise CurveFeatureError("snapshot_contract_duplicate")
    if frame.duplicated(["eval_date", "product_vt_symbol", "contract_maturity"]).any():
        raise CurveFeatureError("snapshot_maturity_duplicate")

    rows: list[dict[str, Any]] = []
    for (eval_date, product), curve in frame.groupby(
        ["eval_date", "product_vt_symbol"], sort=True
    ):
        curve = curve.sort_values(
            ["contract_maturity", "contract_vt_symbol"], kind="mergesort"
        ).copy()
        if len(curve) < minimum_contracts:
            raise CurveFeatureError(f"curve_contract_count_below_minimum:{eval_date}:{product}")
        eval_month = pd.Timestamp(eval_date.year, eval_date.month, 1)
        maturity_months = np.asarray(
            [
                _month_serial(pd.Timestamp(value)) - _month_serial(eval_month)
                for value in curve["contract_maturity"]
            ],
            dtype=float,
        )
        if np.any(maturity_months < 0.0) or np.any(np.diff(maturity_months) <= 0.0):
            raise CurveFeatureError(f"curve_maturity_order_invalid:{eval_date}:{product}")
        maturity_days = maturity_months * (365.25 / 12.0)
        log_prices = np.log(curve["close_price"].to_numpy(float))
        front_next_day_gap = float(maturity_days[1] - maturity_days[0])
        if front_next_day_gap <= 0.0 or float(np.ptp(maturity_days)) <= 0.0:
            raise CurveFeatureError(f"curve_maturity_span_invalid:{eval_date}:{product}")
        front_next_basis = float((log_prices[0] - log_prices[1]) * 365.0 / front_next_day_gap)
        design = np.column_stack([maturity_days, np.ones(len(maturity_days))])
        slope, intercept = np.linalg.lstsq(design, log_prices, rcond=None)[0]
        fitted = slope * maturity_days + intercept
        rmse = float(np.sqrt(np.mean(np.square(log_prices - fitted))))
        oi = curve["open_interest"].to_numpy(float)
        volume = curve["volume"].to_numpy(float)
        oi_share = oi / oi.sum()
        volume_share = volume / volume.sum()
        values = {
            "front_next_basis_annualized": front_next_basis,
            "full_curve_backwardation_slope": float(-365.0 * slope),
            "full_curve_fit_rmse": rmse,
            "open_interest_hhi": float(np.square(oi_share).sum()),
            "volume_hhi": float(np.square(volume_share).sum()),
            "oi_weighted_maturity_days": float(np.dot(oi_share, maturity_days)),
        }
        if not np.isfinite(list(values.values())).all():
            raise CurveFeatureError(f"curve_descriptor_nonfinite:{eval_date}:{product}")
        rows.append(
            {
                "eval_date": pd.Timestamp(eval_date),
                "product_vt_symbol": str(product),
                "eligible_contract_count": int(len(curve)),
                "front_maturity_months": int(maturity_months[0]),
                "last_maturity_months": int(maturity_months[-1]),
                **values,
                "threshold_features_created": 0,
                "future_label_rows_read": 0,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["eval_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def build_candidate_feature_matrix(
    panel: pd.DataFrame,
    descriptors: pd.DataFrame,
    *,
    anchor_rank: int,
) -> pd.DataFrame:
    ranked = _normalise_panel(panel)
    _required_columns(
        descriptors,
        {"eval_date", "product_vt_symbol", *RAW_CURVE_FEATURES},
        "descriptors",
    )
    desc = descriptors.copy()
    desc["eval_date"] = pd.to_datetime(desc["eval_date"], errors="raise").dt.normalize()
    if desc.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise CurveFeatureError("descriptor_eval_product_duplicate")
    merged = ranked.merge(
        desc[["eval_date", "product_vt_symbol", *RAW_CURVE_FEATURES]],
        on=["eval_date", "product_vt_symbol"],
        how="left",
        validate="one_to_one",
    )
    if merged[RAW_CURVE_FEATURES].isna().any().any():
        raise CurveFeatureError("descriptor_panel_coverage_incomplete")
    candidate = merged[merged["a_rank"].ge(anchor_rank)].copy()
    if candidate.empty:
        raise CurveFeatureError("candidate_group_empty")

    parts: list[pd.DataFrame] = []
    for eval_date, month in candidate.groupby("eval_date", sort=True):
        month = month.sort_values("a_rank", kind="mergesort").copy()
        ranks = month["a_rank"].astype(int).tolist()
        if ranks != list(range(anchor_rank, max(ranks) + 1)):
            raise CurveFeatureError(f"candidate_rank_not_contiguous:{eval_date}")
        anchor = month[month["a_rank"].eq(anchor_rank)]
        if len(anchor) != 1:
            raise CurveFeatureError(f"candidate_anchor_count:{eval_date}:{len(anchor)}")
        anchor_row = anchor.iloc[0]
        month["formal_probability_delta_vs_rank10"] = (
            month["pit_logistic_probability"] - float(anchor_row["pit_logistic_probability"])
        )
        month["formal_rank_distance"] = month["a_rank"].astype(float) - float(anchor_rank)
        for raw_feature, delta_feature in zip(
            RAW_CURVE_FEATURES, CURVE_DELTA_FEATURES, strict=True
        ):
            month[delta_feature] = month[raw_feature] - float(anchor_row[raw_feature])
        parts.append(month)
    result = pd.concat(parts, ignore_index=True).sort_values(
        ["eval_date", "a_rank"], kind="mergesort"
    ).reset_index(drop=True)
    if not np.isfinite(result[MODEL_FEATURES].to_numpy(float)).all():
        raise CurveFeatureError("model_feature_nonfinite")
    return result


def assess_curve_features(
    panel: pd.DataFrame,
    descriptors: pd.DataFrame,
    features: pd.DataFrame,
    *,
    expected_rows: int,
    expected_months: int,
    expected_anchor_rows: int,
    expected_challenger_rows: int,
    expected_folds: int,
    anchor_rank: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    ranked = _normalise_panel(panel)
    anchors = features[features["a_rank"].eq(anchor_rank)]
    challengers = features[features["a_rank"].gt(anchor_rank)]
    anchor_values = anchors[MODEL_FEATURES].to_numpy(float)
    model_values = features[MODEL_FEATURES].to_numpy(float)
    diagnostic_rows: list[dict[str, Any]] = []
    for feature in MODEL_FEATURES:
        challenger_values = challengers[feature].to_numpy(float)
        nonzero_folds = 0
        for _, fold in challengers.groupby("window_id", sort=True):
            if np.any(np.abs(fold[feature].to_numpy(float)) > 1e-15):
                nonzero_folds += 1
        diagnostic_rows.append(
            {
                "feature": feature,
                "candidate_std": float(features[feature].std(ddof=0)),
                "challenger_unique_values": int(pd.Series(challenger_values).nunique()),
                "challenger_nonzero_rows": int(np.sum(np.abs(challenger_values) > 1e-15)),
                "folds_with_nonzero_challenger": int(nonzero_folds),
            }
        )
    diagnostics = pd.DataFrame(diagnostic_rows)
    curve_diagnostics = diagnostics[diagnostics["feature"].isin(CURVE_DELTA_FEATURES)]
    gates = {
        "descriptor_panel_coverage": len(descriptors) == len(ranked),
        "candidate_row_count": len(features) == int(expected_rows),
        "candidate_month_count": features["eval_date"].nunique() == int(expected_months),
        "anchor_row_count": len(anchors) == int(expected_anchor_rows),
        "challenger_row_count": len(challengers) == int(expected_challenger_rows),
        "fold_count": features["window_id"].nunique() == int(expected_folds),
        "model_feature_count": len(MODEL_FEATURES) == 8,
        "all_model_features_finite": bool(np.isfinite(model_values).all()),
        "anchor_features_exact_zero": bool(np.array_equal(anchor_values, np.zeros_like(anchor_values))),
        "all_features_nonzero_for_challenger": bool(
            diagnostics["challenger_nonzero_rows"].gt(0).all()
        ),
        "all_features_nonconstant_with_anchor": bool(diagnostics["candidate_std"].gt(0.0).all()),
        "curve_features_nonzero_in_every_fold": bool(
            curve_diagnostics["folds_with_nonzero_challenger"].eq(expected_folds).all()
        ),
        "future_label_rows_read_zero": int(
            descriptors.get("future_label_rows_read", pd.Series(0, index=descriptors.index)).sum()
        ) == 0,
    }
    passed = bool(all(gates.values()))
    return (
        {
            "decision": PASS_DECISION if passed else FAIL_DECISION,
            "all_gates_passed": passed,
            "gates": gates,
            "descriptor_rows": int(len(descriptors)),
            "candidate_rows": int(len(features)),
            "months": int(features["eval_date"].nunique()),
            "anchor_rows": int(len(anchors)),
            "challenger_rows": int(len(challengers)),
            "folds": int(features["window_id"].nunique()),
            "feature_count": int(len(MODEL_FEATURES)),
            "future_label_rows_read": int(
                descriptors.get("future_label_rows_read", pd.Series(0, index=descriptors.index)).sum()
            ),
            "threshold_features_created": int(
                descriptors.get("threshold_features_created", pd.Series(0, index=descriptors.index)).sum()
            ),
        },
        diagnostics,
    )

"""Research cohort contract. No strategy import, fitting or broker access.

Intervals express missing-label identification, not confidence intervals. They
do not cure upstream policy hindsight or non-random missingness.
"""
import numpy as np
import pandas as pd

KEYS = ["eval_date", "product_vt_symbol"]
FLAGS = ["history_ok", "feature_coverage_ok", "tradable_asof",
         "label_complete", "label_coverage_ok"]


def build_cohort_bounds(frame):
    result = frame.copy().reset_index(drop=True)
    result["eval_date"] = pd.to_datetime(result.eval_date, errors="raise")
    dates = result.eval_date
    if dates.isna().any() or dates.dt.tz is not None or not dates.equals(dates.dt.normalize()):
        raise ValueError("evaluation date must be nonempty timezone-free midnight")
    products = result.product_vt_symbol
    if products.isna().any() or products.astype(str).str.strip().eq("").any():
        raise ValueError("product key must be nonempty")
    if result.duplicated(KEYS).any():
        raise ValueError("duplicate product-month")
    for column in FLAGS:
        values = result[column].astype(str).str.strip().str.lower()
        if not values.isin(["true", "false", "1", "0"]).all():
            raise ValueError("explicit boolean required: " + column)
        result[column] = values.isin(["true", "1"])
    ends = pd.to_datetime(result.label_end, errors="raise")
    if (result.label_complete & (ends.isna() | ends.le(result.eval_date))).any():
        raise ValueError("complete label end must be after evaluation date")
    values = pd.to_numeric(result.future_net_pnl_60d, errors="raise")
    stated = result.label_complete & result.label_coverage_ok
    if (stated & ~np.isfinite(values)).any():
        raise ValueError("observable label must be finite")
    result["asof_member"] = (result.history_ok & result.feature_coverage_ok & result.tradable_asof)
    result["label_observable"] = result.asof_member & stated
    result["rank_lower"] = np.nan
    result["rank_upper"] = np.nan
    result["asof_universe_count"] = 0
    result["known_label_count"] = 0
    result["unknown_label_count"] = 0
    result["constant_observed_target"] = False
    result["point_target_identified"] = False
    result["target_state"] = "outside_asof_universe"
    for _, group in result.groupby("eval_date", sort=True):
        members = group.index[group.asof_member]
        known = group.index[group.label_observable]
        total, observed = len(members), len(known)
        missing = total - observed
        result.loc[group.index, ["asof_universe_count", "known_label_count", "unknown_label_count"]] = [total, observed, missing]
        result.loc[members, "target_state"] = "unknown_label"
        if not observed:
            continue
        # Unknown members can be anywhere in the future ranking. Preserve N.
        known_ranks = values.loc[known].rank(method="average")
        lower, upper = known_ranks / total, (known_ranks + missing) / total
        result.loc[known, "rank_lower"] = lower
        result.loc[known, "rank_upper"] = upper
        result.loc[known, "target_state"] = "ambiguous"
        top, bottom = lower.index[lower.gt(.5)], upper.index[upper.le(.5)]
        result.loc[top, "target_state"] = "identified_top_half"
        result.loc[bottom, "target_state"] = "identified_bottom_half"
        result.loc[top.union(bottom), "point_target_identified"] = True
        if missing == 0 and values.loc[known].nunique() == 1:
            result.loc[members, "constant_observed_target"] = True
            result.loc[members, "point_target_identified"] = False
            result.loc[members, "target_state"] = "constant_uninformative"
    return result

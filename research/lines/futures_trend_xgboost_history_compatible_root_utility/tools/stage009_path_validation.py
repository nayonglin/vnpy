from __future__ import annotations

import importlib.util
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def batch_module():
    spec = importlib.util.spec_from_file_location("path_validation_batch", ROOT / "tools/stage004_label_batch.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def primary_comparison(a, c):
    keys = ("total_return_pct", "max_drawdown_pct")
    if not all(math.isfinite(row[key]) for row in (a, c) for key in keys):
        raise RuntimeError("comparison_metrics_nonfinite")
    ret = c[keys[0]] - a[keys[0]]
    dd = c[keys[1]] - a[keys[1]]
    passed = ret > 0 and dd > 0
    return {"return_change_pp": ret, "signed_drawdown_change_pp": dd, "primary_gate_passed": passed,
            "valuable_candidate_verified": False, "reviewer_started": False,
            "decision": "continue_fixed_robustness_checks" if passed else "fixed_candidate_failed_no_parameter_rescue"}


def validate_decisions(candidates, decisions, formal, predictor):
    import pandas as pd

    batch = batch_module()
    h = batch.load_history()
    skipped = candidates.candidate_status.eq("skipped") & candidates.skip_reason.eq("research_xgb_predicted_harm")
    eligible = candidates.entry_context.eq("flat_entry") & candidates.product_vt_symbol.ne("fu.SHFE")
    accepted = eligible & candidates.candidate_status.eq("opened") & candidates.is_opened.eq(1)
    if (skipped & (~eligible | candidates.is_opened.ne(0))).any():
        raise RuntimeError("decision_skip_snapshot_invalid")
    selected = candidates.loc[accepted | skipped].copy()
    if (len(decisions) != len(selected) or decisions.candidate_index.duplicated().any()
            or set(decisions.candidate_index) != set(selected.candidate_index)):
        raise RuntimeError("decision_event_inventory_mismatch")
    if selected.empty:
        return {"decision_count": 0, "skip_count": 0, "first_skip_date": None, "first_skip_candidate_index": None}
    selected["candidate_status"] = "opened"
    selected["is_opened"] = 1
    rebuilt = h.build_features(selected, formal).sort_values("candidate_index").reset_index(drop=True)
    observed = decisions.sort_values("candidate_index").reset_index(drop=True)
    batch.frame_equal(rebuilt, observed.loc[:, rebuilt.columns])
    by_index = candidates.set_index("candidate_index")
    for event, record in zip(rebuilt.to_dict("records"), observed.to_dict("records")):
        expected = predictor(event)
        for key, value in expected.items():
            actual = record[key]
            if pd.isna(actual):
                actual = None
            if actual != value:
                raise RuntimeError(f"decision_prediction_mismatch:{event['candidate_index']}:{key}")
        was_skipped = by_index.loc[event["candidate_index"], "skip_reason"] == "research_xgb_predicted_harm"
        if bool(expected["skip"]) != was_skipped:
            raise RuntimeError("decision_action_snapshot_mismatch")
    skips = observed.loc[observed.skip]
    return {"decision_count": len(observed), "skip_count": len(skips),
            "first_skip_date": str(skips.iloc[0].decision_date) if len(skips) else None,
            "first_skip_candidate_index": int(skips.iloc[0].candidate_index) if len(skips) else None}


def validate_prefix(a, c, first_date, first_index):
    batch = batch_module()
    for name, column in (("daily", "date"), ("trades", "datetime"), ("positions", "date")):
        left, right = a[name], c[name]
        if not left.empty:
            left = left.loc[left[column].astype(str).str[:10].lt(first_date)]
        if not right.empty:
            right = right.loc[right[column].astype(str).str[:10].lt(first_date)]
        batch.frame_equal(left, right)
    left, right = a["entry_candidates"], c["entry_candidates"]
    batch.frame_equal(left.loc[left.candidate_index.lt(first_index)], right.loc[right.candidate_index.lt(first_index)])

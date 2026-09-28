from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/formal_signal_event_features.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("formal_signal_event_features", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def module():
    return _load_module()


def _identity() -> dict[str, str]:
    return {
        "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
        "formal_strategy": "ai_top10_plus_fu_official_live_v1",
        "official_live_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        "formal_material_manifest_sha256": "a" * 64,
    }


def _static_boundary(module) -> list[dict[str, object]]:
    return [
        {
            "strategy": "ai_top10_plus_fu_official_live_v1",
            "score_type": module.STATIC_PRE_AI_SCORE_TYPE,
            "eval_date": module.STATIC_PRE_AI_EVAL_DATE,
            "product_vt_symbol": f"static{rank}.SHFE",
            "score": 0.0,
            "score_rank": rank,
            "top_n": 18,
        }
        for rank in range(1, 19)
    ]


def _dynamic_month(
    eval_date: str,
    *,
    model_count: int = 10,
) -> list[dict[str, object]]:
    products = (
        "rb.SHFE",
        "cu.SHFE",
        "al.SHFE",
        "zn.SHFE",
        "ni.SHFE",
        "ru.SHFE",
        "TA.CZCE",
        "MA.CZCE",
        "i.DCE",
        "m.DCE",
        "pp.DCE",
    )
    scores = (0.80, 0.60, 0.55, 0.50, 0.45, 0.40, 0.35, 0.30, 0.20, 0.10, 0.05)
    rows = [
        {
            "strategy": "ai_top10_plus_fu_official_live_v1",
            "score_type": "model_probability",
            "eval_date": eval_date,
            "product_vt_symbol": products[rank - 1],
            "score": scores[rank - 1],
            "score_rank": rank,
            "top_n": model_count + 1,
        }
        for rank in range(1, model_count + 1)
    ]
    rows.append(
        {
            "strategy": "ai_top10_plus_fu_official_live_v1",
            "score_type": "fixed_fu_satellite",
            "eval_date": eval_date,
            "product_vt_symbol": "fu.SHFE",
            "score": 0.05,
            "score_rank": model_count + 1,
            "top_n": model_count + 1,
        }
    )
    return rows


def _eligibility(module) -> pd.DataFrame:
    rows = _static_boundary(module)
    for eval_date in module.EXPECTED_DYNAMIC_EVAL_DATES:
        rows.extend(_dynamic_month(eval_date))
    return pd.DataFrame(rows)


def _candidate(
    *,
    candidate_index: int = 7,
    product: str = "rb.SHFE",
    direction: str = "long",
    score: float = 0.80,
    rank: int = 1,
) -> dict[str, object]:
    return {
        "candidate_index": candidate_index,
        "datetime": "2026-08-03 15:00:00+08:00",
        "date": "2026-08-03",
        "product_vt_symbol": product,
        "contract_vt_symbol": product.replace(".", "2610."),
        "entry_context": "flat_entry",
        "direction": direction,
        "signal": "long_case2" if direction == "long" else "short_case2",
        "candidate_status": "opened",
        "is_opened": 1,
        "ai_product_pool_strategy": "ai_top10_plus_fu_official_live_v1",
        "ai_product_pool_signal_date": "2026-07-31",
        "ai_product_pool_score": score,
        "ai_product_pool_rank": rank,
        "ai_product_pool_top_n": 11,
        "rsi_value": 70.0,
        "ma_mid_value": 110.0,
        "ma_long_value": 100.0,
        "ma_mid_prev_value": 108.0,
        "ma_long_prev_value": 99.0,
        "planned_entry_price": 200.0,
        "oi_price_confirm_entry_oi": 1_100.0,
        "oi_price_confirm_prev_oi": 1_000.0,
        "stop_distance": 4.0,
        "portfolio_drawdown_pct": 0.12,
        "estimated_equity": 150_000.0,
        "total_margin_in_use_before": 30_000.0,
        "active_positions_before": 2,
        "max_concurrent_positions": 4,
        "same_direction_correlation_gate_enabled": 1,
        "same_direction_correlation_active_count": 1,
        "same_direction_correlation_corr_count": 1,
        "same_direction_correlation_max_corr": 0.35,
        "same_direction_correlation_candidate_return_count": 20,
        "same_direction_correlation_min_required_count": 10,
        "same_direction_correlation_candidate_history_available": 1,
        "same_direction_correlation_active_count_recomputed": 1,
        "same_direction_correlation_corr_count_recomputed": 1,
        "same_direction_correlation_max_corr_recomputed": 0.35,
        "same_direction_correlation_trace_exact": 1,
        "loss_streak": 2,
    }


def test_build_features_uses_model_cutoff_and_excludes_fixed_fu(module) -> None:
    candidates = pd.DataFrame(
        [
            _candidate(),
            _candidate(
                candidate_index=8,
                product="fu.SHFE",
                score=0.599999,
                rank=3,
            ),
        ]
    )

    result = module.build_formal_root_event_features(
        candidates,
        _eligibility(module),
        _identity(),
    )

    assert result["product_vt_symbol"].tolist() == ["rb.SHFE"]
    row = result.iloc[0]
    assert row["formal_model_count"] == 10
    assert row["formal_cutoff_score"] == pytest.approx(0.10)
    assert row["formal_rank_percentile"] == pytest.approx(1.0)
    assert row["formal_score_margin_to_cutoff"] == pytest.approx(0.70)
    assert row["directional_rsi"] == pytest.approx(0.40)
    assert row["directional_ma_gap"] == pytest.approx(0.05)
    assert row["directional_ma_slope"] == pytest.approx(0.0075)
    assert row["open_interest_change_pct"] == pytest.approx(0.10)
    assert row["stop_distance_pct"] == pytest.approx(0.02)
    assert row["margin_to_equity_before"] == pytest.approx(0.20)
    assert row["active_positions_fraction"] == pytest.approx(0.50)


def test_short_direction_normalizes_directional_features(module) -> None:
    candidate = _candidate(direction="short")
    result = module.build_formal_root_event_features(
        pd.DataFrame([candidate]),
        _eligibility(module),
        _identity(),
    )

    row = result.iloc[0]
    assert row["directional_rsi"] == pytest.approx(-0.40)
    assert row["directional_ma_gap"] == pytest.approx(-0.05)
    assert row["directional_ma_slope"] == pytest.approx(-0.0075)


def test_same_direction_correlation_zero_is_only_valid_without_active_peers(module) -> None:
    candidate = _candidate()
    candidate["same_direction_correlation_active_count"] = 0
    candidate["same_direction_correlation_corr_count"] = 0
    candidate["same_direction_correlation_max_corr"] = 0.0
    candidate["same_direction_correlation_active_count_recomputed"] = 0
    candidate["same_direction_correlation_corr_count_recomputed"] = 0
    candidate["same_direction_correlation_max_corr_recomputed"] = 0.0

    result = module.build_formal_root_event_features(
        pd.DataFrame([candidate]),
        _eligibility(module),
        _identity(),
    )

    row = result.iloc[0]
    assert row["same_direction_correlation_active_count"] == 0
    assert row["same_direction_correlation_corr_count"] == 0
    assert row["same_direction_correlation"] == pytest.approx(0.0)


def test_same_direction_correlation_fails_closed_when_active_peer_is_unmeasured(
    module,
) -> None:
    candidate = _candidate()
    candidate["same_direction_correlation_active_count"] = 1
    candidate["same_direction_correlation_corr_count"] = 0
    candidate["same_direction_correlation_max_corr"] = 0.0
    candidate["same_direction_correlation_active_count_recomputed"] = 1
    candidate["same_direction_correlation_corr_count_recomputed"] = 0
    candidate["same_direction_correlation_max_corr_recomputed"] = 0.0

    with pytest.raises(
        module.FeatureContractError,
        match="same_direction_correlation_recomputed_unavailable",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


def test_same_direction_correlation_counts_must_be_internally_consistent(module) -> None:
    candidate = _candidate()
    candidate["same_direction_correlation_active_count"] = 1
    candidate["same_direction_correlation_corr_count"] = 2
    candidate["same_direction_correlation_active_count_recomputed"] = 1
    candidate["same_direction_correlation_corr_count_recomputed"] = 2

    with pytest.raises(
        module.FeatureContractError,
        match="same_direction_correlation_recomputed_count_invalid",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


def test_same_direction_correlation_candidate_history_unknown_fails_closed(module) -> None:
    candidate = _candidate()
    candidate["same_direction_correlation_active_count"] = 0
    candidate["same_direction_correlation_corr_count"] = 0
    candidate["same_direction_correlation_max_corr"] = 0.0
    candidate["same_direction_correlation_candidate_return_count"] = 9
    candidate["same_direction_correlation_candidate_history_available"] = 0
    candidate["same_direction_correlation_active_count_recomputed"] = 1
    candidate["same_direction_correlation_corr_count_recomputed"] = 0
    candidate["same_direction_correlation_max_corr_recomputed"] = 0.0
    candidate["same_direction_correlation_trace_exact"] = 0

    with pytest.raises(
        module.FeatureContractError,
        match="same_direction_correlation_candidate_history_unavailable",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


def test_same_direction_correlation_independent_trace_mismatch_fails_closed(module) -> None:
    candidate = _candidate()
    candidate["same_direction_correlation_active_count_recomputed"] = 2
    candidate["same_direction_correlation_corr_count_recomputed"] = 2
    candidate["same_direction_correlation_trace_exact"] = 0

    with pytest.raises(
        module.FeatureContractError,
        match="same_direction_correlation_trace_mismatch",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


@pytest.mark.parametrize(
    ("column", "value", "error_code"),
    [
        ("rsi_value", np.nan, "candidate_numeric_non_finite:rsi_value"),
        ("planned_entry_price", 0.0, "candidate_non_positive:planned_entry_price"),
        ("oi_price_confirm_prev_oi", 0.0, "candidate_non_positive:oi_price_confirm_prev_oi"),
        ("max_concurrent_positions", 0, "candidate_non_positive:max_concurrent_positions"),
    ],
)
def test_invalid_numeric_inputs_fail_closed(module, column, value, error_code) -> None:
    candidate = _candidate()
    candidate[column] = value

    with pytest.raises(module.FeatureContractError, match=error_code):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


def test_missing_required_column_fails_closed(module) -> None:
    candidate = _candidate()
    candidate.pop("ma_long_prev_value")

    with pytest.raises(
        module.FeatureContractError,
        match="candidate_columns_missing:ma_long_prev_value",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


def test_candidate_must_match_frozen_eligibility(module) -> None:
    candidate = _candidate(score=0.79)

    with pytest.raises(
        module.FeatureContractError,
        match="candidate_eligibility_value_mismatch:ai_product_pool_score",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


def test_duplicate_event_identity_fails_closed(module) -> None:
    candidate = _candidate()

    with pytest.raises(module.FeatureContractError, match="duplicate_event_identity"):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate, dict(candidate)]),
            _eligibility(module),
            _identity(),
        )


def test_output_schema_cannot_contain_outcomes(module) -> None:
    result = module.build_formal_root_event_features(
        pd.DataFrame([_candidate()]),
        _eligibility(module),
        _identity(),
    )

    assert tuple(result.columns) == module.OUTPUT_COLUMNS
    assert result["analysis_start"].tolist() == ["2020-01-02"]
    assert result["analysis_end"].tolist() == ["2026-08-28"]
    assert set(module.FEATURE_COLUMNS).issubset(result.columns)
    forbidden = ("future", "label", "realized", "gross_pnl", "net_pnl", "mfe", "mae", "exit_")
    assert not any(token in column.lower() for column in result.columns for token in forbidden)


def test_event_identity_is_bound_to_frozen_analysis_interval(module) -> None:
    row = _candidate()
    result = module.build_formal_root_event_features(
        pd.DataFrame([row]),
        _eligibility(module),
        _identity(),
    )

    payload = {
        "formal_release_id": _identity()["formal_release_id"],
        "formal_strategy": _identity()["formal_strategy"],
        "official_live_version": _identity()["official_live_version"],
        "formal_material_manifest_sha256": _identity()["formal_material_manifest_sha256"],
        "analysis_start": module.ANALYSIS_START,
        "analysis_end": module.ANALYSIS_END,
        "candidate_index": row["candidate_index"],
        "decision_datetime": pd.Timestamp(row["datetime"]).isoformat(),
        "decision_date": row["date"],
        "product_vt_symbol": row["product_vt_symbol"],
        "contract_vt_symbol": row["contract_vt_symbol"],
        "direction": row["direction"],
        "signal": row["signal"],
    }
    import hashlib
    import json

    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert result.iloc[0]["event_id"] == expected


@pytest.mark.parametrize(
    ("column", "value", "error_code"),
    [
        ("candidate_index", 7.5, "candidate_integer_invalid:candidate_index"),
        ("is_opened", 1.5, "candidate_integer_invalid:is_opened"),
        ("ai_product_pool_rank", 1.5, "candidate_integer_invalid:ai_product_pool_rank"),
        ("ai_product_pool_top_n", 3.5, "candidate_integer_invalid:ai_product_pool_top_n"),
    ],
)
def test_discrete_candidate_fields_must_be_exact_integers(
    module,
    column,
    value,
    error_code,
) -> None:
    candidate = _candidate()
    candidate[column] = value

    with pytest.raises(module.FeatureContractError, match=error_code):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


def test_candidate_date_must_match_decision_datetime(module) -> None:
    candidate = _candidate()
    candidate["date"] = "2026-09-01"

    with pytest.raises(module.FeatureContractError, match="candidate_date_datetime_mismatch"):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


def test_each_formal_month_requires_fixed_fu_satellite(module) -> None:
    eligibility = _eligibility(module).query("product_vt_symbol != 'fu.SHFE'").copy()
    dynamic = eligibility["eval_date"].ne(module.STATIC_PRE_AI_EVAL_DATE)
    eligibility.loc[dynamic, "top_n"] = 10

    with pytest.raises(module.FeatureContractError, match="eligibility_fixed_product_count"):
        module.build_formal_root_event_features(
            pd.DataFrame([_candidate(rank=1)]),
            eligibility,
            _identity(),
        )


def test_formal_cutoff_uses_last_model_rank_even_when_scores_are_not_monotonic(module) -> None:
    eligibility = _eligibility(module)
    eligibility.loc[eligibility["product_vt_symbol"].eq("rb.SHFE"), "score"] = 0.50
    eligibility.loc[eligibility["product_vt_symbol"].eq("cu.SHFE"), "score"] = 0.80
    selected_month = eligibility["eval_date"].eq("2026-07-31")
    rank10 = eligibility["score_rank"].eq(10)
    eligibility.loc[selected_month & rank10, "score"] = 0.80
    eligibility.loc[selected_month & eligibility["product_vt_symbol"].eq("fu.SHFE"), "score"] = 0.40

    result = module.build_formal_root_event_features(
        pd.DataFrame([_candidate(score=0.50)]),
        eligibility,
        _identity(),
    )

    assert result.iloc[0]["formal_cutoff_score"] == pytest.approx(0.80)
    assert result.iloc[0]["formal_score_margin_to_cutoff"] == pytest.approx(-0.30)


def test_static_pre_ai_boundary_is_validated_but_excluded_from_events(module) -> None:
    eligibility = _eligibility(module)
    old = _candidate(candidate_index=1, product="static1.SHFE", score=0.0, rank=1)
    old["datetime"] = "2021-06-01 15:00:00+08:00"
    old["date"] = "2021-06-01"
    old["ai_product_pool_signal_date"] = module.STATIC_PRE_AI_EVAL_DATE
    old["ai_product_pool_top_n"] = 18
    current = _candidate(candidate_index=2)

    result = module.build_formal_root_event_features(
        pd.DataFrame([old, current]),
        eligibility,
        _identity(),
    )

    assert result["candidate_index"].tolist() == [2]
    assert result["ai_eval_date"].tolist() == ["2026-07-31"]


def test_static_boundary_and_exact_dynamic_calendar_are_mandatory(module) -> None:
    missing_static = _eligibility(module).query(
        "eval_date != @module.STATIC_PRE_AI_EVAL_DATE"
    ).copy()
    with pytest.raises(
        module.FeatureContractError,
        match="eligibility_static_boundary_count",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([_candidate()]),
            missing_static,
            _identity(),
        )

    missing_dynamic = _eligibility(module).query("eval_date != '2022-01-28'").copy()
    with pytest.raises(
        module.FeatureContractError,
        match="eligibility_dynamic_calendar_mismatch",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([_candidate()]),
            missing_dynamic,
            _identity(),
        )

    extra_dynamic = pd.concat(
        [_eligibility(module), pd.DataFrame(_dynamic_month("2026-09-30"))],
        ignore_index=True,
    )
    with pytest.raises(
        module.FeatureContractError,
        match="eligibility_dynamic_calendar_mismatch",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([_candidate()]),
            extra_dynamic,
            _identity(),
        )


@pytest.mark.parametrize("model_count", [9, 11])
def test_each_dynamic_month_requires_exactly_ten_model_rows_plus_fu(
    module,
    model_count,
) -> None:
    eligibility = _eligibility(module)
    selected = eligibility["eval_date"].ne("2026-07-31")
    replacement = pd.DataFrame(_dynamic_month("2026-07-31", model_count=model_count))
    eligibility = pd.concat([eligibility.loc[selected], replacement], ignore_index=True)

    with pytest.raises(
        module.FeatureContractError,
        match="eligibility_dynamic_model_count:2026-07-31",
    ):
        module.build_formal_root_event_features(
            pd.DataFrame([_candidate()]),
            eligibility,
            _identity(),
        )


@pytest.mark.parametrize(
    ("eval_date", "decision_datetime", "decision_date", "error_code"),
    [
        (
            "2026-07-31",
            "2026-07-31 15:00:00+08:00",
            "2026-07-31",
            "candidate_ai_eval_not_before_decision",
        ),
        (
            "2026-07-31",
            "2019-12-31 15:00:00+08:00",
            "2019-12-31",
            "candidate_decision_outside_analysis_interval",
        ),
        (
            "2026-07-31",
            "2026-08-29 15:00:00+08:00",
            "2026-08-29",
            "candidate_decision_outside_analysis_interval",
        ),
    ],
)
def test_candidate_event_chronology_and_frozen_interval_are_hard_gates(
    module,
    eval_date,
    decision_datetime,
    decision_date,
    error_code,
) -> None:
    candidate = _candidate()
    candidate["ai_product_pool_signal_date"] = eval_date
    candidate["datetime"] = decision_datetime
    candidate["date"] = decision_date

    with pytest.raises(module.FeatureContractError, match=error_code):
        module.build_formal_root_event_features(
            pd.DataFrame([candidate]),
            _eligibility(module),
            _identity(),
        )


def test_qualification_reports_all_frozen_gates(module) -> None:
    base = module.build_formal_root_event_features(
        pd.DataFrame([_candidate()]),
        _eligibility(module),
        _identity(),
    )
    rows = []
    for year in range(2020, 2026):
        for index in range(2):
            row = base.iloc[0].copy()
            row["event_id"] = f"{year}-{index}"
            row["decision_date"] = f"{year}-02-01"
            row["candidate_index"] = year * 10 + index
            row["product_vt_symbol"] = f"p{index}.SHFE"
            row["direction"] = "long" if index == 0 else "short"
            for feature_index, feature in enumerate(module.FEATURE_COLUMNS):
                row[feature] = float(year * 10 + index + feature_index)
            rows.append(row)
    frame = pd.DataFrame(rows, columns=module.OUTPUT_COLUMNS)
    thresholds = module.QualificationThresholds(
        min_events=12,
        min_events_per_full_year=2,
        min_events_per_direction=6,
        min_products=2,
        min_unique_per_feature=2,
        min_high_cardinality_features=12,
        high_cardinality_unique_values=10,
    )

    result = module.evaluate_feature_qualification(frame, thresholds=thresholds)

    assert result["passed"] is True
    assert all(result["gates"].values())
    assert result["metrics"]["fixed_fu_event_count"] == 0
    assert result["metrics"]["feature_count"] == 12

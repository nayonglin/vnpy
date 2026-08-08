from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest
from scipy.stats import fisher_exact
from scipy.stats.contingency import odds_ratio
from sklearn.metrics import cohen_kappa_score


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "stage214_all_short_blind_stats.py"
)
SPEC = importlib.util.spec_from_file_location("stage214_blind_stats", MODULE_PATH)
assert SPEC and SPEC.loader
stats = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stats)


def _labels(values: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "case_id": [f"CASE-{index:03d}" for index in range(1, len(values) + 1)],
            "label": values,
            "reason": [f"visual evidence {index}" for index in range(1, len(values) + 1)],
            "confidence": [
                ["high", "medium", "low"][index % 3]
                for index in range(len(values))
            ],
            "timestamp": ["2026-08-08T10:00:00+08:00"] * len(values),
        }
    )


def test_validate_reviewer_labels_accepts_all_four_frozen_labels() -> None:
    labels = _labels(
        [
            "trend_same_direction",
            "range_or_compression",
            "mixed_or_opposite",
            "insufficient",
        ]
    )

    stats.validate_reviewer_labels(labels, labels["case_id"])


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True), "duplicate"),
        (lambda frame: frame.iloc[:-1], "case set"),
        (lambda frame: frame.assign(case_id=[None, *frame["case_id"].iloc[1:]]), "case_id"),
        (
            lambda frame: frame.assign(
                case_id=[f"{frame.loc[0, 'case_id']} ", *frame["case_id"].iloc[1:]]
            ),
            "normalized",
        ),
        (
            lambda frame: frame.assign(
                label=[f" {frame.loc[0, 'label']}", *frame["label"].iloc[1:]]
            ),
            "normalized",
        ),
        (lambda frame: frame.assign(label=["bad", *frame["label"].iloc[1:]]), "label"),
        (lambda frame: frame.assign(reason=[" ", *frame["reason"].iloc[1:]]), "reason"),
        (
            lambda frame: frame.assign(
                confidence=["certain", *frame["confidence"].iloc[1:]]
            ),
            "confidence",
        ),
    ],
)
def test_validate_reviewer_labels_rejects_protocol_violations(mutate, match) -> None:
    labels = _labels(
        [
            "trend_same_direction",
            "range_or_compression",
            "mixed_or_opposite",
            "insufficient",
        ]
    )

    with pytest.raises(ValueError, match=match):
        stats.validate_reviewer_labels(mutate(labels), labels["case_id"])


def test_compute_agreement_matches_hand_checked_fixture() -> None:
    labels_a = _labels(
        [
            "trend_same_direction",
            "range_or_compression",
            "mixed_or_opposite",
            "insufficient",
        ]
    )
    labels_b = _labels(
        [
            "trend_same_direction",
            "mixed_or_opposite",
            "mixed_or_opposite",
            "insufficient",
        ]
    )

    result = stats.compute_agreement(labels_a, labels_b)

    expected_kappa = cohen_kappa_score(labels_a["label"], labels_b["label"])
    assert result == pytest.approx(
        {
            "case_count": 4,
            "matching_case_count": 3,
            "raw_agreement": 0.75,
            "cohen_kappa": expected_kappa,
        }
    )


def test_build_adjudicated_labels_requires_exact_disagreement_set() -> None:
    labels_a = _labels(
        [
            "trend_same_direction",
            "range_or_compression",
            "mixed_or_opposite",
            "insufficient",
        ]
    )
    labels_b = _labels(
        [
            "trend_same_direction",
            "mixed_or_opposite",
            "mixed_or_opposite",
            "insufficient",
        ]
    )
    adjudication = labels_b.iloc[[1]].copy()

    result = stats.build_adjudicated_labels(labels_a, labels_b, adjudication)

    assert result["case_id"].tolist() == labels_a["case_id"].tolist()
    assert result["label"].tolist() == [
        "trend_same_direction",
        "mixed_or_opposite",
        "mixed_or_opposite",
        "insufficient",
    ]
    assert result["label_source"].tolist() == [
        "reviewer_agreement",
        "third_party_adjudication",
        "reviewer_agreement",
        "reviewer_agreement",
    ]

    with pytest.raises(ValueError, match="adjudication case set"):
        stats.build_adjudicated_labels(
            labels_a, labels_b, adjudication.iloc[0:0]
        )
    with pytest.raises(ValueError, match="adjudication case set"):
        stats.build_adjudicated_labels(labels_a, labels_b, labels_b.iloc[[0, 1]])


def test_compute_primary_statistics_matches_hand_checked_table_and_exact_interval() -> None:
    table = [[12, 8], [5, 39]]
    labels = ["trend_same_direction"] * 20 + ["range_or_compression"] * 44
    aggregate_r = [3.0] * 12 + [-1.0] * 8 + [3.0] * 5 + [-1.0] * 39
    joined = pd.DataFrame(
        {
            "case_id": [f"CASE-{index:03d}" for index in range(1, 65)],
            "label": labels,
            "aggregate_r": aggregate_r,
        }
    )
    joined = pd.concat(
        [
            joined,
            pd.DataFrame(
                [{"case_id": "CASE-999", "label": "insufficient", "aggregate_r": 100.0}]
            ),
        ],
        ignore_index=True,
    )

    result = stats.compute_primary_statistics(joined)

    expected_conditional = odds_ratio(table, kind="conditional")
    expected_interval = expected_conditional.confidence_interval(0.95)
    assert result["contingency_table"] == table
    assert result["analyzable_case_count"] == 64
    assert result["fisher_exact_two_sided_pvalue"] == pytest.approx(
        fisher_exact(table, alternative="two-sided").pvalue
    )
    assert result["sample_odds_ratio"] == pytest.approx(12 * 39 / (8 * 5))
    assert result["conditional_odds_ratio"] == pytest.approx(
        expected_conditional.statistic
    )
    assert result["conditional_odds_ratio_ci95_lower"] == pytest.approx(
        expected_interval.low
    )
    assert result["conditional_odds_ratio_ci95_upper"] == pytest.approx(
        expected_interval.high
    )
    assert result["risk_difference"] == pytest.approx(12 / 20 - 5 / 44)
    assert result["signal_positive_median_aggregate_r"] == 3.0
    assert result["signal_negative_median_aggregate_r"] == -1.0
    assert result["signal_positive_profit_probability"] == pytest.approx(12 / 20)
    assert result["signal_negative_profit_probability"] == pytest.approx(5 / 44)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"case_id": ["CASE-001 ", "CASE-002"]}, "case_id.*normalized"),
        (
            {"label": [" trend_same_direction", "range_or_compression"]},
            "final_label.*normalized",
        ),
        ({"case_id": [None, "CASE-002"]}, "case_id.*non-empty"),
        (
            {"label": [None, "range_or_compression"]},
            "final_label.*non-empty",
        ),
        ({"case_id": ["CASE-001", "CASE-001"]}, "case_id.*unique"),
    ],
)
def test_compute_primary_statistics_rejects_noncanonical_case_and_final_label(
    mutation: dict[str, list[object]],
    match: str,
) -> None:
    joined = pd.DataFrame(
        {
            "case_id": ["CASE-001", "CASE-002"],
            "label": ["trend_same_direction", "range_or_compression"],
            "aggregate_r": [3.0, -1.0],
        }
    ).assign(**mutation)

    with pytest.raises(ValueError, match=match):
        stats.compute_primary_statistics(joined)


def _loo_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "case_id": [f"CASE-{index:03d}" for index in range(1, 9)],
            "label": [
                "trend_same_direction",
                "range_or_compression",
                "trend_same_direction",
                "range_or_compression",
                "trend_same_direction",
                "range_or_compression",
                "trend_same_direction",
                "range_or_compression",
            ],
            "aggregate_r": [3.0, -1.0, 3.0, -1.0, 3.0, -1.0, -1.0, 3.0],
            "entry_year": [2021, 2021, 2021, 2021, 2022, 2022, 2022, 2022],
            "product": ["A", "A", "B", "B", "A", "A", "B", "B"],
        }
    )


def test_compute_leave_one_out_removes_only_each_group_and_selects_tie_by_name() -> None:
    joined = _loo_fixture()

    year_result = stats.compute_leave_one_out(joined, "entry_year")
    product_result = stats.compute_leave_one_out(joined, "product")

    assert year_result["excluded_group"].tolist() == [2021, 2022]
    assert year_result["excluded_count"].tolist() == [4, 4]
    assert year_result["remaining_case_count"].tolist() == [4, 4]
    assert product_result["excluded_group"].tolist() == ["A"]
    assert product_result["excluded_count"].tolist() == [4]
    assert product_result["selected_highest_frequency"].tolist() == [True]
    assert product_result.iloc[0]["selection_evidence"] == "frequency=4;tie_break=ascending_group_name"


def test_compute_leave_one_out_records_degenerate_omission_as_failed_direction() -> None:
    joined = pd.DataFrame(
        {
            "case_id": ["CASE-001", "CASE-002", "CASE-003", "CASE-004"],
            "label": [
                "trend_same_direction",
                "trend_same_direction",
                "range_or_compression",
                "range_or_compression",
            ],
            "aggregate_r": [3.0, -1.0, 3.0, -1.0],
            "product": ["A", "A", "B", "B"],
        }
    )

    result = stats.compute_leave_one_out(joined, "product")

    assert result["excluded_group"].tolist() == ["A"]
    assert result["conditional_odds_ratio"].isna().all()
    assert result["remaining_case_count"].tolist() == [2]


def test_compute_gap_bounds_enumerates_all_aggregate_allocations_including_mixed_worst() -> None:
    joined = pd.DataFrame(
        {
            "case_id": [f"CASE-{index:03d}" for index in range(1, 7)],
            "label": ["trend_same_direction"] * 3 + ["range_or_compression"] * 3,
            "aggregate_r": [3.0, 3.0, -1.0, 3.0, -1.0, -1.0],
        }
    )
    unresolved = pd.DataFrame({"case_id": ["GAP-1", "GAP-2"]})

    result = stats.compute_gap_bounds(joined, unresolved)

    assert result["unresolved_case_count"] == 2
    assert len(result["scenarios"]) == 10
    assert {
        tuple(scenario["allocation"].values()) for scenario in result["scenarios"]
    } == {
        (a, b, c, 2 - a - b - c)
        for a in range(3)
        for b in range(3 - a)
        for c in range(3 - a - b)
    }
    assert result["most_adverse"]["allocation"] == {
        "signal_positive_outcome_ge_2r": 0,
        "signal_positive_outcome_lt_2r": 1,
        "signal_negative_outcome_ge_2r": 1,
        "signal_negative_outcome_lt_2r": 0,
    }
    assert result["most_adverse"]["contingency_table"] == [[2, 2], [2, 2]]
    assert result["most_adverse"]["risk_difference"] == 0.0
    assert result["worst_case_direction_preserved"] is False


def test_compute_gap_bounds_zero_gap_vacuously_passes_with_base_as_both_bounds() -> None:
    joined = pd.DataFrame(
        {
            "case_id": [f"CASE-{index:03d}" for index in range(1, 7)],
            "label": ["trend_same_direction"] * 3 + ["range_or_compression"] * 3,
            "aggregate_r": [3.0, -1.0, -1.0, 3.0, 3.0, -1.0],
        }
    )

    result = stats.compute_gap_bounds(joined, pd.DataFrame(columns=["case_id"]))

    assert result["unresolved_case_count"] == 0
    assert len(result["scenarios"]) == 1
    assert result["most_favorable"]["contingency_table"] == [[1, 2], [2, 1]]
    assert result["most_adverse"]["contingency_table"] == [[1, 2], [2, 1]]
    assert result["worst_case_direction_preserved"] is True


def _passing_metrics() -> dict[str, object]:
    return {
        "risk_difference": 0.20,
        "sample_odds_ratio": 3.0,
        "conditional_odds_ratio": 2.8,
        "conditional_odds_ratio_ci95_lower": 1.2,
        "conditional_odds_ratio_ci95_upper": 7.0,
        "fisher_exact_two_sided_pvalue": 0.01,
        "signal_positive_median_aggregate_r": 2.5,
        "signal_negative_median_aggregate_r": 0.5,
        "signal_positive_profit_probability": 0.70,
        "signal_negative_profit_probability": 0.45,
    }


def _passing_loo() -> tuple[pd.DataFrame, pd.DataFrame]:
    year = pd.DataFrame(
        {
            "excluded_group": [2021, 2022],
            "conditional_odds_ratio": [1.5, 1.2],
        }
    )
    product = pd.DataFrame(
        {
            "excluded_group": ["A"],
            "conditional_odds_ratio": [1.3],
            "selected_highest_frequency": [True],
        }
    )
    return year, product


def test_evaluate_decision_enforces_all_gates_and_stage214_precedence() -> None:
    metrics = _passing_metrics()
    agreement = {"raw_agreement": 0.85, "cohen_kappa": 0.65}
    year, product = _passing_loo()
    gap = {"worst_case_direction_preserved": True, "most_adverse": {"risk_difference": 0.01}}

    passing = stats.evaluate_decision(metrics, agreement, year, product, gap)

    assert passing["decision"] == "qualified_for_numeric_translation"
    assert len(passing["gates"]) == 11
    assert all(set(gate) == {"name", "value", "threshold", "passed", "evidence"} for gate in passing["gates"])
    assert all(gate["passed"] for gate in passing["gates"])

    flipped_gap = {"worst_case_direction_preserved": False, "most_adverse": {"risk_difference": -0.01}}
    p_failed = dict(metrics, fisher_exact_two_sided_pvalue=0.05)
    assert stats.evaluate_decision(p_failed, agreement, year, product, flipped_gap)["decision"] == "reject_signal"

    unreliable = dict(agreement, cohen_kappa=0.59)
    assert stats.evaluate_decision(metrics, unreliable, year, product, gap)["decision"] == "visual_definition_not_reproducible"

    unstable_year = year.copy()
    unstable_year.loc[1, "conditional_odds_ratio"] = 1.0
    assert stats.evaluate_decision(metrics, agreement, unstable_year, product, gap)["decision"] == "phase_specific_attribution"

    assert stats.evaluate_decision(metrics, agreement, year, product, flipped_gap)["decision"] == "insufficient_data"


def test_sample_odds_ratio_above_two_gate_does_not_use_conditional_estimate() -> None:
    joined = pd.DataFrame(
        {
            "case_id": [f"CASE-{index:03d}" for index in range(1, 18)],
            "label": ["trend_same_direction"] * 8 + ["range_or_compression"] * 9,
            "aggregate_r": [3.0] * 5 + [-1.0] * 3 + [3.0] * 4 + [-1.0] * 5,
        }
    )
    observed = stats.compute_primary_statistics(joined)
    assert observed["sample_odds_ratio"] == pytest.approx(25 / 12)
    assert observed["conditional_odds_ratio"] == pytest.approx(1.9935, abs=0.0001)
    metrics = dict(
        _passing_metrics(),
        sample_odds_ratio=observed["sample_odds_ratio"],
        conditional_odds_ratio=observed["conditional_odds_ratio"],
    )
    agreement = {"raw_agreement": 0.85, "cohen_kappa": 0.65}
    year, product = _passing_loo()
    gap = {"worst_case_direction_preserved": True, "most_adverse": {"risk_difference": 0.01}}

    decision = stats.evaluate_decision(metrics, agreement, year, product, gap)

    odds_gate = next(gate for gate in decision["gates"] if gate["name"] == "sample_odds_ratio_above_2")
    assert odds_gate["value"] == pytest.approx(25 / 12)
    assert odds_gate["passed"] is True
    assert decision["decision"] == "qualified_for_numeric_translation"


def _write_reveal_inputs(output_dir: Path) -> pd.DataFrame:
    labels = ["trend_same_direction"] * 20 + ["range_or_compression"] * 44
    aggregate_r = [3.0] * 12 + [-1.0] * 8 + [3.0] * 5 + [-1.0] * 39
    reviewer_labels = _labels(labels)
    reviewer_labels.to_csv(output_dir / "reviewer_a_labels.csv", index=False)
    reviewer_labels.to_csv(output_dir / "reviewer_b_labels.csv", index=False)
    pd.DataFrame(columns=stats.LABEL_COLUMNS).to_csv(
        output_dir / "adjudication_labels.csv", index=False
    )
    pd.DataFrame({"case_id": reviewer_labels["case_id"]}).to_csv(
        output_dir / "reviewer_manifest.csv", index=False
    )
    mapping = pd.DataFrame(
        {
            "case_id": reviewer_labels["case_id"],
            "aggregate_r": aggregate_r,
            "entry_year": [2021 if index % 2 else 2022 for index in range(64)],
            "vt_symbol": ["A2401.TEST" if index % 4 < 2 else "B2401.TEST" for index in range(64)],
        }
    )
    mapping.to_csv(output_dir / "blind_mapping.csv", index=False)
    return mapping


def test_reveal_reads_frozen_named_inputs_and_writes_machine_outputs(tmp_path: Path) -> None:
    _write_reveal_inputs(tmp_path)

    result = stats.reveal(tmp_path)

    assert result["primary_statistics"]["contingency_table"] == [[12, 8], [5, 39]]
    assert result["agreement"]["raw_agreement"] == 1.0
    for filename in [
        "agreement.json",
        "adjudicated_labels.csv",
        "primary_statistics.json",
        "year_leave_one_out.csv",
        "product_leave_one_out.csv",
        "gap_bounds.json",
        "decision.json",
    ]:
        assert (tmp_path / filename).is_file()
    decision = json.loads((tmp_path / "decision.json").read_text(encoding="utf-8"))
    assert all("evidence" in gate for gate in decision["gates"])


@pytest.mark.parametrize("mutation", ["extra", "missing", "duplicate"])
def test_reveal_rejects_mapping_case_set_or_uniqueness_mismatch(
    tmp_path: Path,
    mutation: str,
) -> None:
    mapping = _write_reveal_inputs(tmp_path)
    if mutation == "extra":
        mapping = pd.concat(
            [
                mapping,
                pd.DataFrame(
                    [
                        {
                            "case_id": "CASE-999",
                            "aggregate_r": 3.0,
                            "entry_year": 2022,
                            "vt_symbol": "A2401.TEST",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    elif mutation == "missing":
        mapping = mapping.iloc[:-1].copy()
    else:
        mapping = pd.concat([mapping, mapping.iloc[[0]]], ignore_index=True)
    mapping.to_csv(tmp_path / "blind_mapping.csv", index=False)

    with pytest.raises(ValueError, match="mapping.*case set|unique case_id"):
        stats.reveal(tmp_path)


def test_reveal_rejects_manifest_and_adjudicated_case_set_mismatch(tmp_path: Path) -> None:
    _write_reveal_inputs(tmp_path)
    manifest = pd.read_csv(tmp_path / "reviewer_manifest.csv")
    manifest = pd.concat(
        [manifest, pd.DataFrame([{"case_id": "CASE-999"}])],
        ignore_index=True,
    )
    manifest.to_csv(tmp_path / "reviewer_manifest.csv", index=False)

    with pytest.raises(ValueError, match="case set"):
        stats.reveal(tmp_path)

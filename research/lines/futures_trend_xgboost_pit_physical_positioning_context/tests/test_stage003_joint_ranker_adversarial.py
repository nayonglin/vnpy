from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest


LINE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = LINE_DIR / "tools/stage003_joint_ranker_development_oos.py"
SPEC = importlib.util.spec_from_file_location("stage003_joint_ranker_adversarial", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class CountingLabelStore:
    def __init__(self) -> None:
        self.load_calls = 0

    def load(self, job_ids: list[str]) -> list[dict[str, Any]]:
        self.load_calls += 1
        return [{"job_id": job_id} for job_id in job_ids]


def _active_payloads(eval_date: str = "2024-01-31") -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fold_input = {
        "eval_date": eval_date,
        "feature_order": module.MODEL_FEATURES,
        "qid": [0, 0, 1, 1],
        "group_boundaries": [0, 2, 4],
        "ordered_training_job_identities": [
            {"job_id": "m1_r10", "eval_date": "2023-11-30", "next_eval_date": "2023-12-29", "product_vt_symbol": "MA.CZCE", "a_rank": 10},
            {"job_id": "m1_r11", "eval_date": "2023-11-30", "next_eval_date": "2023-12-29", "product_vt_symbol": "rb.SHFE", "a_rank": 11},
            {"job_id": "m2_r10", "eval_date": "2023-12-29", "next_eval_date": "2024-01-31", "product_vt_symbol": "MA.CZCE", "a_rank": 10},
            {"job_id": "m2_r11", "eval_date": "2023-12-29", "next_eval_date": "2024-01-31", "product_vt_symbol": "au.SHFE", "a_rank": 11},
        ],
        "ordered_test_keys": [
            {"eval_date": eval_date, "product_vt_symbol": "MA.CZCE", "a_rank": 10},
            {"eval_date": eval_date, "product_vt_symbol": "rb.SHFE", "a_rank": 11},
            {"eval_date": eval_date, "product_vt_symbol": "au.SHFE", "a_rank": 12},
        ],
    }
    raw_rows = module._build_prediction_payload(
        eval_date,
        module._prediction_frame_for_test(
            [
                ("MA.CZCE", 10, 0.90, 0.0, 0.0),
                ("rb.SHFE", 11, 0.80, 2.0, 2.0),
                ("au.SHFE", 12, 0.70, 1.0, 1.0),
            ],
            eval_date,
        ),
    )
    selection = module._build_selection_payload(raw_rows)
    return fold_input, raw_rows, selection


def _persist(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fold_input, prediction, selection = _active_payloads()
    module._persist_active_fold(
        root,
        "2024-01-31",
        primary_model_bytes=b"deterministic-model-bytes",
        repeat_model_bytes=b"deterministic-model-bytes",
        fold_input=fold_input,
        prediction=prediction,
        selection=selection,
        label_read_count_before_seal=0,
    )
    return fold_input, prediction, selection


@pytest.mark.parametrize(
    "relative_path",
    [
        "models/2024-01-31_primary.ubj",
        "models/2024-01-31_repeat.ubj",
        "fold_inputs/2024-01-31.json",
        "predictions/2024-01-31.json",
        "selections/2024-01-31.json",
        "pre_effect_seals/2024-01-31.json",
    ],
)
def test_any_active_payload_tamper_blocks_before_label_store_load(
    tmp_path: Path, relative_path: str
) -> None:
    fold_input, _, _ = _persist(tmp_path)
    path = tmp_path / relative_path
    path.write_bytes(path.read_bytes() + b"tamper")
    store = CountingLabelStore()

    with pytest.raises(module.Stage003SealError):
        module._effect_open(
            tmp_path,
            "2024-01-31",
            expected_fold_input=fold_input,
            label_store=store,
            job_ids=["test_r10", "test_r11", "test_r12"],
        )
    assert store.load_calls == 0


def test_active_seal_is_create_once_and_recomputed_selection_is_used(tmp_path: Path) -> None:
    fold_input, _, selection = _persist(tmp_path)
    with pytest.raises(module.Stage003SealError, match="already_exists"):
        _persist(tmp_path)
    store = CountingLabelStore()

    result = module._effect_open(
        tmp_path,
        "2024-01-31",
        expected_fold_input=fold_input,
        label_store=store,
        job_ids=["test_r10", "test_r11", "test_r12"],
    )

    assert result["selection"] == selection
    assert store.load_calls == 1


def test_fallback_seal_has_exact_schema_and_never_loads_labels(tmp_path: Path) -> None:
    arm = {"a_rank": 10, "product_vt_symbol": "MA.CZCE"}
    module._persist_fallback_seal(tmp_path, "2024-02-29", arm)
    verified = module._verify_fallback_seal(tmp_path, "2024-02-29", arm)
    assert verified["label_read_count_before_seal"] == 0
    assert verified["label_read_count_after_seal"] == 0

    path = tmp_path / "pre_effect_seals/2024-02-29.json"
    payload = json.loads(path.read_text())
    payload["extra"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.Stage003SealError, match="fallback_seal_keys"):
        module._verify_fallback_seal(tmp_path, "2024-02-29", arm)


def _projection_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_rows = []
    split_rows = []
    for rank, symbol, probability in [(10, "MA.CZCE", 0.6), (11, "rb.SHFE", 0.7)]:
        feature_rows.append(
            {
                "eval_date": "2024-01-31",
                "product_vt_symbol": symbol,
                "a_rank": rank,
                **{
                    feature: (
                        probability - 0.6
                        if feature == "formal_probability_delta_vs_rank10"
                        else (0.0 if rank == 10 else 0.1)
                    )
                    for feature in module.MODEL_FEATURES
                },
            }
        )
        split_rows.append(
            [
                "2024-01-31",
                "2024-02-29",
                symbol,
                rank,
                "development",
                probability,
            ]
        )
    return pd.DataFrame(feature_rows), pd.DataFrame(
        split_rows, columns=module.FULL_SPLIT_ALLOWED_COLUMNS
    )


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("extra_column", "projection_columns"),
        ("feature_duplicate", "feature_key_duplicate"),
        ("split_duplicate", "split_key_duplicate"),
        ("missing_match", "projection_join_missing"),
        ("right_only_row", "projection_right_only_source_invalid"),
        ("nan_probability", "probability_type_or_finite"),
        ("string_probability", "probability_type_or_finite"),
        ("bool_probability", "probability_type_or_finite"),
        ("low_probability", "probability_out_of_range"),
        ("high_probability", "probability_out_of_range"),
        ("delta_as_raw_probability", "probability_out_of_range"),
    ],
)
def test_raw_probability_projection_fails_closed(mutation: str, error: str) -> None:
    features, split = _projection_inputs()
    if mutation == "extra_column":
        split["role"] = "forbidden"
    elif mutation == "feature_duplicate":
        features = pd.concat([features, features.iloc[[0]]], ignore_index=True)
    elif mutation == "split_duplicate":
        split = pd.concat([split, split.iloc[[0]]], ignore_index=True)
    elif mutation == "missing_match":
        split = split.iloc[[0]].copy()
    elif mutation == "right_only_row":
        split.loc[len(split)] = [
            "2024-02-29",
            "2024-03-29",
            "au.SHFE",
            10,
            "development",
            0.5,
        ]
    elif mutation == "nan_probability":
        split.loc[1, "pit_logistic_probability"] = np.nan
    elif mutation == "string_probability":
        split["pit_logistic_probability"] = split["pit_logistic_probability"].astype(object)
        split.loc[1, "pit_logistic_probability"] = "0.7"
    elif mutation == "bool_probability":
        split["pit_logistic_probability"] = split["pit_logistic_probability"].astype(object)
        split.loc[1, "pit_logistic_probability"] = True
    elif mutation == "low_probability":
        split.loc[1, "pit_logistic_probability"] = -0.01
    elif mutation == "high_probability":
        split.loc[1, "pit_logistic_probability"] = 1.01
    elif mutation == "delta_as_raw_probability":
        split["pit_logistic_probability"] = [0.0, -0.1]

    with pytest.raises(module.Stage003Error, match=error):
        module._join_raw_probability_projection(features, split)


def test_ranker_matrix_rejects_raw_probability_or_any_nonfrozen_column() -> None:
    features, split = _projection_inputs()
    panel, _ = module._join_raw_probability_projection(features, split)

    with pytest.raises(module.Stage003Error, match="ranker_feature_order"):
        module._extract_ranker_matrix(
            panel, [*module.MODEL_FEATURES, "pit_logistic_probability"]
        )


def test_physical_split_audit_requires_each_model_and_three_distinct_features() -> None:
    active_dates = ["2023-07-31", "2023-08-31", "2023-09-28"]
    valid = {
        active_dates[0]: {module.PHYSICAL_FEATURES[0]: 2, module.MODEL_FEATURES[0]: 1},
        active_dates[1]: {module.PHYSICAL_FEATURES[1]: 1},
        active_dates[2]: {module.PHYSICAL_FEATURES[2]: 3},
    }

    audit = module._physical_split_audit(valid, active_dates)
    assert audit["passed"] is True
    assert audit["models_with_physical_split"] == 3
    assert audit["distinct_physical_features_used"] == 3

    missing_one = dict(valid)
    missing_one[active_dates[1]] = {module.MODEL_FEATURES[0]: 2}
    assert module._physical_split_audit(missing_one, active_dates)["passed"] is False

    only_two = {
        date: {module.PHYSICAL_FEATURES[index % 2]: 1}
        for index, date in enumerate(active_dates)
    }
    assert module._physical_split_audit(only_two, active_dates)["passed"] is False


def test_effect_sequence_rejects_missing_duplicate_or_nonzero_fallback_months() -> None:
    contract = json.loads(
        (LINE_DIR / "contracts/stage003_joint_ranker_development_oos_training_contract.json").read_text()
    )
    active = [
        {
            "eval_date": date,
            "arm_c_replaced": False,
            "arm_c_product_vt_symbol": "MA.CZCE",
            "return_delta": 0.0,
            "drawdown_improvement": 0.0,
            "seal_type": "active_model_fold",
        }
        for date in contract["folds"]["active_test_dates"]
    ]
    fallback = [
        module._fallback_effect_row(
            date, {"a_rank": 10, "product_vt_symbol": "MA.CZCE"}
        )
        for date in contract["folds"]["fallback_test_dates"]
    ]

    with pytest.raises(module.Stage003Error, match="effect_sequence"):
        module._assemble_effect_sequence(active[:-1], fallback, contract)
    with pytest.raises(module.Stage003Error, match="effect_sequence"):
        module._assemble_effect_sequence([*active, active[0]], fallback, contract)
    bad_fallback = [dict(row) for row in fallback]
    bad_fallback[0]["return_delta"] = 0.01
    with pytest.raises(module.Stage003Error, match="fallback_effect_nonzero"):
        module._assemble_effect_sequence(active, bad_fallback, contract)


def test_execution_scope_cannot_be_forged_by_training_summary_counts() -> None:
    ledger = module.ExecutionEventLedger()
    training = {
        "active_seal_count": 13,
        "fit_call_count": 26,
        "prepublication_artifact_audit": {
            "passed": True,
            "missing_files": [],
            "unexpected_files": [],
            "unobserved_files": [],
        },
    }
    static_scope = {
        "passed": True,
        "counts": {
            "parameter_searches": 0,
            "feature_searches": 0,
            "seed_searches": 0,
            "early_stopping_runs": 0,
            "true_engine_runs": 0,
            "production_writes": 0,
            "ctp_connections": 0,
            "order_api_calls": 0,
            "unexpected_commands": 0,
        },
    }

    audit = module._build_execution_scope_audit(
        training,
        event_ledger=ledger,
        static_scope_audit=static_scope,
    )

    assert audit["passed"] is False
    assert audit["counts"]["primary_fit_calls"] == 0
    assert audit["counts"]["repeat_fit_calls"] == 0
    assert audit["counts"]["total_fit_calls"] == 0


def test_static_scope_audit_rejects_command_and_order_nodes(tmp_path: Path) -> None:
    current = module._static_runner_scope_audit(MODULE_PATH)
    assert current["passed"] is True
    assert current["fit_call_site_count"] == 1
    assert all(value == 0 for value in current["counts"].values())

    bad = tmp_path / "bad_runner.py"
    bad.write_text(
        "import subprocess\n"
        "def run():\n"
        "    subprocess.run([\"echo\", \"bad\"])\n"
        "    gateway.send_order({})\n",
        encoding="utf-8",
    )
    audit = module._static_runner_scope_audit(bad)
    assert audit["passed"] is False
    assert audit["counts"]["unexpected_commands"] >= 1
    assert audit["counts"]["order_api_calls"] >= 1

from __future__ import annotations

import hashlib
import importlib.util
import json
import multiprocessing
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest


LINE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = LINE_DIR / "tools/stage003_joint_ranker_development_oos.py"
CONTRACT_PATH = LINE_DIR / "contracts/stage003_joint_ranker_development_oos_training_contract.json"
SPEC = importlib.util.spec_from_file_location("stage003_joint_ranker_state_machine", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(root: Path) -> tuple[Path, Path, dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    bound_dir = root / "bound"
    bound_dir.mkdir()
    bound_paths: dict[str, str] = {}
    bound_files: dict[str, dict[str, str]] = {}
    for key in module.BOUND_FILE_KEYS:
        path = bound_dir / f"{key}.txt"
        path.write_text(f"{key}\n", encoding="utf-8")
        bound_paths[key] = str(path.resolve())
        bound_files[key] = {"path": str(path.resolve()), "sha256": _sha256(path)}
    receipt = root / "authorization.consumed.json"
    result_dir = root / "result"
    contract = {
        "authorization": {
            "path": str((root / "authorization.json").resolve()),
            "consumption_receipt_path": str(receipt.resolve()),
            "result_dir": str(result_dir.resolve()),
            "temp_result_dir": str((root / "result.tmp").resolve()),
            "decision": "AUTHORIZE_ONE_STAGE003_DEVELOPMENT_OOS_RUN",
            "scope": "one_new_stage003_development_oos_run_only",
            "bound_file_keys": module.BOUND_FILE_KEYS,
            "bound_file_paths": bound_paths,
        }
    }
    authorization = {
        "decision": contract["authorization"]["decision"],
        "scope": contract["authorization"]["scope"],
        "nonce": "a" * 64,
        "bound_files": bound_files,
        "result_dir": str(result_dir.resolve()),
        "consumption_receipt_path": str(receipt.resolve()),
    }
    contract_path = root / "contract.json"
    authorization_path = root / "authorization.json"
    contract_path.write_text(json.dumps(contract, sort_keys=True), encoding="utf-8")
    authorization_path.write_text(json.dumps(authorization, sort_keys=True), encoding="utf-8")
    return authorization_path, contract_path, contract


@pytest.mark.parametrize("nonce", [True, 1, None, "A" * 64, "a" * 63, "g" * 64])
def test_authorization_rejects_noncanonical_nonce_types(tmp_path: Path, nonce: object) -> None:
    authorization_path, contract_path, _ = _fixture(tmp_path)
    authorization = json.loads(authorization_path.read_text())
    authorization["nonce"] = nonce
    authorization_path.write_text(json.dumps(authorization), encoding="utf-8")

    with pytest.raises(module.Stage003AuthorizationError, match="nonce"):
        module._consume_authorization_from_paths(authorization_path, contract_path)


def test_authorization_consumes_once_and_serial_retry_fails_before_result_creation(tmp_path: Path) -> None:
    authorization_path, contract_path, contract = _fixture(tmp_path)

    receipt = module._consume_authorization_from_paths(authorization_path, contract_path)

    assert receipt["decision"] == "STAGE003_AUTHORIZATION_CONSUMED"
    assert Path(contract["authorization"]["consumption_receipt_path"]).is_file()
    assert not Path(contract["authorization"]["result_dir"]).exists()
    with pytest.raises(module.Stage003AuthorizationError, match="already_exists"):
        module._consume_authorization_from_paths(authorization_path, contract_path)


def test_authorization_validation_is_side_effect_free_until_explicit_consumption(
    tmp_path: Path,
) -> None:
    authorization_path, contract_path, contract = _fixture(tmp_path)

    validated = module._validate_authorization_from_paths(
        authorization_path, contract_path
    )

    assert validated["receipt"]["decision"] == "STAGE003_AUTHORIZATION_CONSUMED"
    assert validated["receipt_path"] == Path(
        contract["authorization"]["consumption_receipt_path"]
    )
    assert not validated["receipt_path"].exists()
    assert not Path(contract["authorization"]["result_dir"]).exists()
    assert not Path(contract["authorization"]["temp_result_dir"]).exists()

    receipt = module._persist_validated_authorization(validated)
    assert receipt == validated["receipt"]
    assert validated["receipt_path"].is_file()


def _consume_worker(module_path: str, authorization_path: str, contract_path: str, queue: Any) -> None:
    spec = importlib.util.spec_from_file_location("stage003_consume_worker", module_path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    try:
        loaded._consume_authorization_from_paths(Path(authorization_path), Path(contract_path))
        queue.put("consumed")
    except Exception as exc:  # noqa: BLE001 - child reports fail-closed outcome
        queue.put(f"blocked:{type(exc).__name__}")


def test_two_processes_racing_same_receipt_have_exactly_one_winner(tmp_path: Path) -> None:
    authorization_path, contract_path, contract = _fixture(tmp_path)
    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    processes = [
        context.Process(
            target=_consume_worker,
            args=(str(MODULE_PATH), str(authorization_path), str(contract_path), queue),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    outcomes = sorted(queue.get(timeout=2) for _ in processes)

    assert outcomes[0].startswith("blocked:Stage003AuthorizationError")
    assert outcomes[1] == "consumed"
    assert Path(contract["authorization"]["consumption_receipt_path"]).is_file()
    assert not Path(contract["authorization"]["result_dir"]).exists()
    assert not Path(contract["authorization"]["temp_result_dir"]).exists()


def test_authorization_rejects_extra_keys_and_bound_path_aliases(tmp_path: Path) -> None:
    authorization_path, contract_path, _ = _fixture(tmp_path)
    authorization = json.loads(authorization_path.read_text())
    authorization["unexpected"] = False
    authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
    with pytest.raises(module.Stage003AuthorizationError, match="top_level_keys"):
        module._consume_authorization_from_paths(authorization_path, contract_path)

    authorization_path, contract_path, _ = _fixture(tmp_path / "alias")
    authorization = json.loads(authorization_path.read_text())
    first = module.BOUND_FILE_KEYS[0]
    authorization["bound_files"][first]["path"] = str(
        Path(authorization["bound_files"][first]["path"]).parent / "." / Path(
            authorization["bound_files"][first]["path"]
        ).name
    )
    authorization["bound_files"][first]["path"] += "/../invalid"
    authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
    with pytest.raises(module.Stage003AuthorizationError, match="bound_path"):
        module._consume_authorization_from_paths(authorization_path, contract_path)


def test_csv_identity_verification_hashes_whole_file_but_parses_header_only(
    tmp_path: Path,
) -> None:
    path = tmp_path / "aggregate.csv"
    payload = b"job_id,future_return\n\xff\xfeunparseable-tail\n"
    path.write_bytes(payload)

    audit = module._verify_csv_identity_and_header_only(
        path,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        expected_header=["job_id", "future_return"],
    )

    assert audit["data_rows_parsed"] == 0
    assert audit["header"] == ["job_id", "future_return"]
    assert audit["sha256"] == hashlib.sha256(payload).hexdigest()


def test_csv_identity_verification_rejects_tail_drift_even_when_header_matches(
    tmp_path: Path,
) -> None:
    path = tmp_path / "aggregate.csv"
    original = b"job_id,future_return\na,1\n"
    path.write_bytes(original)
    expected = hashlib.sha256(original).hexdigest()
    path.write_bytes(b"job_id,future_return\na,2\n")

    with pytest.raises(module.Stage003Error, match="frozen_input_sha256_mismatch"):
        module._verify_csv_identity_and_header_only(
            path,
            expected_sha256=expected,
            expected_header=["job_id", "future_return"],
        )


def test_actual_frozen_data_identity_preflight_never_parses_aggregate_rows() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    audit = module._verify_frozen_data_inputs(contract)

    assert audit["all_input_identities_verified"] is True
    assert audit["development_labels_aggregate"]["data_rows_parsed"] == 0
    assert audit["reconciliation_aggregate"]["data_rows_parsed"] == 0
    assert audit["aggregate_data_rows_parsed"] == 0


@pytest.mark.parametrize(
    "invalid",
    [
        True,
        1,
        None,
        "a" * 49,
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
    ],
)
def test_input_sha_contract_rejects_non_string_or_noncanonical_hashes(
    invalid: object,
) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["input_sha256"]["full_feature_split"] = invalid

    with pytest.raises(module.Stage003Error, match="input_hash_contract_invalid"):
        module._validate_input_sha256_contract(contract)


def test_input_sha_contract_has_exact_keys_and_lowercase_64hex_values() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    hashes = module._validate_input_sha256_contract(contract)

    assert set(hashes) == set(module.FROZEN_INPUT_SHA_KEYS)
    assert all(type(value) is str for value in hashes.values())
    assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes.values())


def _write_synthetic_label(
    root: Path,
    manifest: dict[str, dict[str, Any]],
    job_id: str,
    *,
    base_equity: float,
    future_return: float,
    future_max_drawdown: float,
) -> None:
    payload = {
        "base_equity": base_equity,
        "end_equity": base_equity * (1.0 + future_return),
        "future_return": future_return,
        "future_max_drawdown": future_max_drawdown,
        "future_net_pnl": base_equity * future_return,
        "future_slippage": 1.0,
        "future_trade_count": 2.0,
        "future_trading_days": 20.0,
    }
    path = root / job_id / "label.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    manifest[f"job_outputs/{job_id}/label.json"] = {
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _synthetic_label_store(tmp_path: Path) -> tuple[Any, dict[str, list[str]]]:
    rows = []
    manifest: dict[str, dict[str, Any]] = {}
    ids: dict[str, list[str]] = {}
    months = [
        ("2023-06-30", "2023-07-31", [0.10, 0.20, 0.05], [-0.20, -0.10, -0.30]),
        ("2023-07-31", "2023-08-31", [0.05, 0.08, 0.01], [-0.15, -0.10, -0.20]),
    ]
    products = ["MA.CZCE", "rb.SHFE", "au.SHFE"]
    for eval_date, next_eval_date, returns, drawdowns in months:
        month_ids = []
        for offset, (product, future_return, future_drawdown) in enumerate(
            zip(products, returns, drawdowns)
        ):
            rank = 10 + offset
            job_id = f"{eval_date.replace('-', '')}_R{rank}"
            month_ids.append(job_id)
            eligibility_path = tmp_path / "eligibility" / f"{job_id}.csv"
            eligibility_path.parent.mkdir(parents=True, exist_ok=True)
            eligibility_path.write_text(
                f"job_id,eligible\n{job_id},1\n", encoding="utf-8"
            )
            eligibility_sha256 = _sha256(eligibility_path)
            manifest[f"eligibility/{job_id}.csv"] = {
                "size": eligibility_path.stat().st_size,
                "sha256": eligibility_sha256,
            }
            rows.append(
                {
                    "eval_date": eval_date,
                    "next_eval_date": next_eval_date,
                    "product_vt_symbol": product,
                    "a_rank": rank,
                    "split": "development",
                    "job_type": "main",
                    "job_id": job_id,
                    "eligibility_key": job_id,
                    "eligibility_sha256": eligibility_sha256,
                }
            )
            _write_synthetic_label(
                tmp_path / "labels",
                manifest,
                job_id,
                base_equity=200_000.0,
                future_return=future_return,
                future_max_drawdown=future_drawdown,
            )
        ids[eval_date] = month_ids
    store = module.PhaseGatedJobLabelStore(
        metadata=pd.DataFrame(rows),
        label_root=tmp_path / "labels",
        manifest_files=manifest,
        initial_dates=["2023-06-30"],
        test_dates=["2023-07-31"],
    )
    return store, ids


def _synthetic_active_payloads(
    eval_date: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fold_input = {
        "eval_date": eval_date,
        "feature_order": module.MODEL_FEATURES,
        "qid": [0, 0, 0],
        "group_boundaries": [0, 3],
        "ordered_training_job_identities": [
            {
                "job_id": f"20230630_R{rank}",
                "eval_date": "2023-06-30",
                "next_eval_date": eval_date,
                "product_vt_symbol": product,
                "a_rank": rank,
            }
            for rank, product in [(10, "MA.CZCE"), (11, "rb.SHFE"), (12, "au.SHFE")]
        ],
        "ordered_test_keys": [
            {"eval_date": eval_date, "product_vt_symbol": product, "a_rank": rank}
            for rank, product in [(10, "MA.CZCE"), (11, "rb.SHFE"), (12, "au.SHFE")]
        ],
    }
    prediction = module._build_prediction_payload(
        eval_date,
        module._prediction_frame_for_test(
            [
                ("MA.CZCE", 10, 0.6, 0.0, 0.0),
                ("rb.SHFE", 11, 0.5, 2.0, 2.0),
                ("au.SHFE", 12, 0.4, 1.0, 1.0),
            ],
            eval_date,
        ),
    )
    selection = module._build_selection_payload(prediction)
    return fold_input, prediction, selection


def test_phase_gated_job_labels_open_initial_then_test_only_after_verified_seal(
    tmp_path: Path,
) -> None:
    store, ids = _synthetic_label_store(tmp_path)
    initial = store.open_initial_labels()
    assert len(initial) == 3
    assert initial.loc[initial["a_rank"].eq(10), "return_delta"].item() == 0.0
    assert (
        initial.loc[initial["a_rank"].eq(10), "drawdown_improvement"].item()
        == 0.0
    )
    fold_input, prediction, selection = _synthetic_active_payloads("2023-07-31")
    module._persist_active_fold(
        tmp_path / "run",
        "2023-07-31",
        primary_model_bytes=b"deterministic-model-bytes",
        repeat_model_bytes=b"deterministic-model-bytes",
        fold_input=fold_input,
        prediction=prediction,
        selection=selection,
        label_read_count_before_seal=0,
    )

    opened = module._effect_open(
        tmp_path / "run",
        "2023-07-31",
        expected_fold_input=fold_input,
        label_store=store,
        job_ids=ids["2023-07-31"],
    )

    assert len(opened["labels"]) == 3
    assert len(store.opened_labels()) == 6
    assert store.final_audit() == {
        "aggregate_development_label_data_rows_parsed": 0,
        "aggregate_reconciliation_data_rows_parsed": 0,
        "initial_mature_label_rows_opened": 3,
        "oos_test_label_rows_opened_before_own_pre_effect_seal": 0,
        "oos_test_label_rows_opened_after_own_pre_effect_seal": 3,
        "unique_job_label_rows_opened": 6,
        "other_development_main_label_rows_read": 0,
        "a2_label_rows_read": 0,
        "sealed_holdout_label_rows_read": 0,
        "same_fold_test_label_rows_used_for_training": 0,
        "test_label_rows_used_for_preprocessing_or_selection": 0,
    }
    with pytest.raises(module.Stage003Error, match="test_label_month_already_opened"):
        store.load(ids["2023-07-31"])


def test_phase_gated_job_store_rejects_wrong_job_set_and_manifest_tamper(
    tmp_path: Path,
) -> None:
    store, ids = _synthetic_label_store(tmp_path)
    store.open_initial_labels()
    with pytest.raises(module.Stage003Error, match="test_label_job_ids_invalid"):
        store.load(ids["2023-07-31"][:-1])

    store.event_ledger.record(
        "active_seal_verified",
        eval_date="2023-07-31",
        seal_sha256="a" * 64,
    )
    path = tmp_path / "labels" / ids["2023-07-31"][0] / "label.json"
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(module.Stage003Error, match="label_identity_mismatch"):
        store.load(ids["2023-07-31"])


def test_phase_gated_job_store_rejects_eligibility_identity_tamper(
    tmp_path: Path,
) -> None:
    store, ids = _synthetic_label_store(tmp_path)
    store.open_initial_labels()
    store.event_ledger.record(
        "active_seal_verified",
        eval_date="2023-07-31",
        seal_sha256="a" * 64,
    )
    path = tmp_path / "eligibility" / f"{ids['2023-07-31'][0]}.csv"
    path.write_bytes(path.read_bytes() + b"tamper")

    with pytest.raises(module.Stage003Error, match="eligibility_identity_mismatch"):
        store.load(ids["2023-07-31"])


class _FakeBooster:
    def save_raw(self, *, raw_format: str) -> bytes:
        assert raw_format == "ubj"
        return b"frozen-fake-ranker"

    def get_score(self, *, importance_type: str) -> dict[str, int]:
        assert importance_type == "weight"
        return {
            module.PHYSICAL_FEATURES[0]: 2,
            module.PHYSICAL_FEATURES[1]: 1,
            module.PHYSICAL_FEATURES[2]: 1,
        }


class _FakeRanker:
    def __init__(self, **params: Any) -> None:
        assert params == module.MODEL_PARAMS

    def fit(
        self,
        matrix: pd.DataFrame,
        target: np.ndarray,
        *,
        qid: np.ndarray,
        verbose: bool,
    ) -> "_FakeRanker":
        assert list(matrix.columns) == module.MODEL_FEATURES
        assert len(target) == len(qid) == len(matrix)
        assert verbose is False
        return self

    def predict(self, matrix: pd.DataFrame) -> np.ndarray:
        assert list(matrix.columns) == module.MODEL_FEATURES
        return np.asarray([0.0, 2.0, 1.0], dtype="float64")

    def get_booster(self) -> _FakeBooster:
        return _FakeBooster()


def test_frozen_training_sequences_active_seal_label_open_and_zero_label_fallback(
    tmp_path: Path,
) -> None:
    store, _ = _synthetic_label_store(tmp_path)
    development = store.metadata.copy()
    development["pit_logistic_probability"] = development["a_rank"].map(
        {10: 0.9, 11: 0.8, 12: 0.7}
    )
    for feature_index, feature in enumerate(module.MODEL_FEATURES, start=1):
        development[feature] = np.where(
            development["a_rank"].eq(10),
            0.0,
            (development["a_rank"] - 10) * feature_index,
        )
    initial = development[development["eval_date"].eq("2023-06-30")].copy()
    test = development[development["eval_date"].eq("2023-07-31")].copy()
    state = {
        "initial_training_panel": initial,
        "active_folds": [
            {
                "test_eval_date": "2023-07-31",
                "train_rows": 3,
                "train_qids": 1,
                "test_rows": 3,
                "train_panel": initial,
                "test_panel": test,
                "qid": [0, 0, 0],
                "group_boundaries": [0, 3],
                "ranker_feature_order": list(module.MODEL_FEATURES),
                "train_label_end_max": "2023-07-31",
            }
        ],
        "fallback_months": pd.DataFrame(
            [
                {
                    "eval_date": "2023-08-31",
                    "product_vt_symbol": "MA.CZCE",
                    "a_rank": 10,
                }
            ]
        ),
        "oos_calendar_dates": ["2023-07-31", "2023-08-31"],
    }
    contract = {
        "folds": {
            "active_fold_count": 1,
            "active_test_dates": ["2023-07-31"],
            "fallback_month_count": 1,
            "fallback_test_dates": ["2023-08-31"],
            "initial_training_rows": 3,
            "initial_training_qids": 1,
            "training_rows": [3],
            "training_qids": [1],
            "test_rows": [3],
        },
        "model": {"class": "xgboost.XGBRanker", "params": module.MODEL_PARAMS, "fit_count": 2},
        "label_access": {
            "aggregate_data_rows_parsed": 0,
            "holdout_label_rows_read": 0,
            "initial_job_label_rows": 3,
            "other_development_main_label_rows_read": 0,
            "test_job_label_rows": 3,
            "unique_job_label_rows": 6,
        },
    }
    (tmp_path / "run").mkdir()

    result = module._run_frozen_training(
        state=state,
        label_store=store,
        contract=contract,
        staging_dir=tmp_path / "run",
        ranker_factory=_FakeRanker,
        event_ledger=store.event_ledger,
    )

    assert result["fit_call_count"] == 2
    assert len(result["fold_audit"]) == 1
    assert len(result["ordered_oos_predictions"]) == 3
    assert len(result["effect_sequence"]) == 2
    assert result["active_seal_count"] == 1
    assert result["fallback_seal_count"] == 1
    assert result["selection_recomputed_before_effect_open_count"] == 1
    assert result["prepublication_artifact_audit"]["passed"] is True
    assert result["prepublication_artifact_audit"]["expected_file_count"] == 7
    assert result["prepublication_artifact_audit"]["unexpected_files"] == []
    assert len(
        [
            event
            for event in store.event_ledger.events()
            if event["event_type"] == "fit_completed"
        ]
    ) == 2
    assert result["label_access_audit"]["initial_mature_label_rows_opened"] == 3
    assert result["label_access_audit"]["oos_test_label_rows_opened_after_own_pre_effect_seal"] == 3
    assert result["label_access_audit"]["unique_job_label_rows_opened"] == 6
    fallback = result["effect_sequence"].loc[
        result["effect_sequence"]["eval_date"].eq("2023-08-31")
    ].iloc[0]
    assert fallback["return_delta"] == 0.0
    assert fallback["drawdown_improvement"] == 0.0
    assert (tmp_path / "run/pre_effect_seals/2023-07-31.json").is_file()
    assert (tmp_path / "run/pre_effect_seals/2023-08-31.json").is_file()


def test_label_access_audit_is_derived_from_events_not_zero_literals(
    tmp_path: Path,
) -> None:
    store, _ = _synthetic_label_store(tmp_path)
    store.event_ledger.record(
        "label_file_read",
        phase="effect_open",
        eval_date="2024-12-31",
        next_eval_date="2025-01-31",
        product_vt_symbol="rb.SHFE",
        a_rank=10,
        job_id="forbidden_holdout_job",
        job_type="main",
        split="sealed_account_label_holdout",
    )

    audit = store.final_audit()

    assert audit["sealed_holdout_label_rows_read"] == 1
    assert audit["oos_test_label_rows_opened_before_own_pre_effect_seal"] == 1
    assert audit["unique_job_label_rows_opened"] == 1


def test_result_bundle_publish_is_atomic_and_manifest_covers_existing_and_new_files(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "result.tmp"
    result = tmp_path / "result"
    (staging / "models").mkdir(parents=True)
    (staging / "models/2023-07-31_primary.ubj").write_bytes(b"model")
    expected_files = {
        "decision.json",
        "effect_sequence.csv",
        "models/2023-07-31_primary.ubj",
        "report.md",
    }

    manifest = module._publish_result_bundle(
        staging,
        result,
        csv_frames={"effect_sequence.csv": pd.DataFrame([{"eval_date": "2023-07-31"}])},
        json_payloads={"decision.json": {"decision": "technical_only"}},
        text_payloads={"report.md": "# report\n"},
        expected_relative_files=expected_files,
    )

    assert result.is_dir()
    assert not staging.exists()
    assert set(manifest["artifacts"]) == expected_files
    persisted = json.loads((result / "artifact_manifest.json").read_text())
    assert persisted == manifest
    for relative, identity in manifest["artifacts"].items():
        path = result / relative
        assert identity == {"size": path.stat().st_size, "sha256": _sha256(path)}
    with pytest.raises(module.Stage003Error, match="result_already_exists"):
        module._publish_result_bundle(
            staging,
            result,
            csv_frames={},
            json_payloads={},
            text_payloads={},
            expected_relative_files=set(),
        )


def test_result_bundle_rejects_unexpected_final_artifact_before_publish(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "result.tmp"
    result = tmp_path / "result"
    staging.mkdir()
    (staging / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(module.Stage003Error, match="final_artifact_set_mismatch"):
        module._publish_result_bundle(
            staging,
            result,
            csv_frames={"fold_audit.csv": pd.DataFrame([{"fold": 1}])},
            json_payloads={},
            text_payloads={},
            expected_relative_files={"fold_audit.csv"},
        )

    assert not result.exists()

from __future__ import annotations

import copy
import concurrent.futures
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage006_dual_ranker_development_oos.py"
)


def load_module():
    assert MODULE_PATH.exists(), "Stage006 dual ranker is not implemented"
    spec = importlib.util.spec_from_file_location(
        "stage006_dual_ranker_development_oos", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synthetic_metadata(module, *, months: int = 5):
    dates = pd.date_range("2022-01-31", periods=months + 1, freq="ME")
    features: list[dict[str, object]] = []
    splits: list[dict[str, object]] = []
    jobs: list[dict[str, object]] = []
    for month_index, eval_date in enumerate(dates[:-1]):
        ranks = range(10, 12 + (month_index % 2))
        for rank in ranks:
            product = f"r{rank}_{month_index}.TEST"
            common = {
                "eval_date": eval_date.date().isoformat(),
                "product_vt_symbol": product,
                "a_rank": rank,
            }
            feature = dict(common)
            feature.update(
                {
                    name: float(rank - 10) + month_index / 100.0
                    for name in module.MODEL_FEATURE_COLUMNS
                }
            )
            if rank == 10:
                feature.update({name: 0.0 for name in module.MODEL_FEATURE_COLUMNS})
            features.append(feature)
            splits.append(
                {
                    **common,
                    "next_eval_date": dates[month_index + 1].date().isoformat(),
                    "split": "development",
                    "label_values_read_allowed": True,
                    "account_label_qid": month_index,
                }
            )
            jobs.append(
                {
                    "eval_date": common["eval_date"],
                    "next_eval_date": dates[month_index + 1].date().isoformat(),
                    "product_vt_symbol": product,
                    "candidate_rank": rank,
                    "split": "development",
                    "job_type": "main",
                    "job_id": f"{eval_date:%Y%m%d}_R{rank}",
                }
            )
    contract = copy.deepcopy(module.load_frozen_contract()[0])
    contract["inputs"]["development_labels"]["rows"] = len(jobs)
    contract["inputs"]["development_labels"]["months"] = months
    contract["pit_split"]["development_months"] = months
    contract["pit_split"]["sealed_holdout_months"] = 0
    contract["pit_split"]["sealed_holdout_feature_rows"] = 0
    return pd.DataFrame(features), pd.DataFrame(splits), pd.DataFrame(jobs), contract


def test_frozen_contract_runtime_and_review_identities_match() -> None:
    module = load_module()

    contract, audit = module.load_frozen_contract()
    runtime = module.current_runtime_identity()

    assert contract["contract_version"] == 2
    assert contract["status"] == "prerun_block_remediated_pending_independent_rereview"
    assert audit["contract_sha256"] == module.EXPECTED_CONTRACT_SHA256
    assert audit["preregistration_sha256"] == module.EXPECTED_PREREGISTRATION_SHA256
    assert audit["runtime_identity_sha256"] == module.EXPECTED_RUNTIME_IDENTITY_SHA256
    assert audit["prerun_review_sha256"] == module.EXPECTED_PRERUN_REVIEW_SHA256
    assert runtime == module.load_frozen_runtime_identity()


def test_metadata_panel_enforces_finite_features_rank_shape_and_holdout_exclusion() -> None:
    module = load_module()
    features, splits, jobs, contract = _synthetic_metadata(module)

    panel, audit = module.build_development_metadata_panel(
        features, splits, jobs, contract
    )

    assert len(panel) == len(jobs)
    assert audit["development_months"] == 5
    assert audit["holdout_feature_rows"] == 0
    assert audit["holdout_prediction_rows"] == 0
    assert panel.groupby("eval_date")["candidate_rank"].min().eq(10).all()

    features.loc[1, module.MODEL_FEATURE_COLUMNS[0]] = np.nan
    with pytest.raises(RuntimeError, match="feature_values_nonfinite"):
        module.build_development_metadata_panel(features, splits, jobs, contract)


def test_metadata_panel_rejects_rank_gap_and_duplicate_product() -> None:
    module = load_module()
    features, splits, jobs, contract = _synthetic_metadata(module)
    first_month = splits["eval_date"].iloc[0]
    rank11 = splits["eval_date"].eq(first_month) & splits["a_rank"].eq(11)
    features = features.loc[~rank11].copy()
    splits = splits.loc[~rank11].copy()
    jobs = jobs.loc[
        ~(
            jobs["eval_date"].eq(first_month)
            & jobs["candidate_rank"].eq(11)
        )
    ].copy()
    features.loc[len(features)] = features.iloc[0]
    splits.loc[len(splits)] = splits.iloc[0]
    jobs.loc[len(jobs)] = jobs.iloc[0]

    with pytest.raises(RuntimeError, match="monthly_key_or_rank_contract"):
        module.build_development_metadata_panel(features, splits, jobs, contract)


def test_pit_folds_support_variable_month_sizes_and_label_maturity() -> None:
    module = load_module()
    features, splits, jobs, contract = _synthetic_metadata(module, months=6)
    panel, _ = module.build_development_metadata_panel(features, splits, jobs, contract)

    folds = module.build_pit_folds(panel, minimum_train_months=3)

    assert len(folds) == 3
    assert [len(fold.train_dates) for fold in folds] == [3, 4, 5]
    assert all(fold.train_label_end_max <= fold.test_date for fold in folds)
    assert all(max(fold.train_dates) < fold.test_date for fold in folds)
    assert [len(fold.test_indices) for fold in folds] == [3, 2, 3]


def test_monthly_dense_relevance_preserves_ties_and_ranker_qid_is_contiguous() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "eval_date": ["2022-01-31"] * 4 + ["2022-02-28"] * 4,
            "candidate_rank": [13, 10, 12, 11] * 2,
            "product_vt_symbol": ["d", "a", "c", "b"] * 2,
            "return_delta": [-1.0, 0.0, 1.0, 1.0, 3.0, 1.0, 2.0, 0.0],
            "drawdown_improvement": [0.0, 0.0, 2.0, 1.0, -1.0, 0.0, 1.0, 2.0],
            "f1": np.arange(8, dtype=float),
        }
    )

    labeled = module.add_monthly_relevance(frame)
    january = labeled[labeled["eval_date"].eq("2022-01-31")].set_index(
        "candidate_rank"
    )
    assert january.loc[11, "return_relevance"] == january.loc[12, "return_relevance"]
    assert sorted(january["return_relevance"].unique()) == [0, 1, 2]

    ordered, x, y, qid = module.ranker_training_arrays(
        labeled, ["f1"], "return_relevance"
    )
    assert ordered[["eval_date", "candidate_rank"]].values.tolist()[:4] == [
        ["2022-01-31", 10],
        ["2022-01-31", 11],
        ["2022-01-31", 12],
        ["2022-01-31", 13],
    ]
    assert list(x.columns) == ["f1"]
    assert y.dtype == np.int64
    assert qid.tolist() == [0, 0, 0, 0, 1, 1, 1, 1]


def test_selector_uses_average_percentiles_and_strict_dual_anchor_gate() -> None:
    module = load_module()
    month = pd.DataFrame(
        {
            "eval_date": ["2024-04-30"] * 3,
            "product_vt_symbol": ["r10.TEST", "r11.TEST", "r12.TEST"],
            "candidate_rank": [10, 11, 12],
            "raw_return_score": [0.2, 0.9, 0.5],
            "raw_drawdown_score": [0.2, 0.3, 0.8],
        }
    )

    scored, selection = module.score_and_select_month(month)

    assert scored["return_percentile"].tolist() == pytest.approx([1 / 3, 1.0, 2 / 3])
    assert scored["drawdown_percentile"].tolist() == pytest.approx([1 / 3, 2 / 3, 1.0])
    assert selection["arm_a_candidate_rank"] == 10
    assert selection["arm_b_candidate_rank"] == 11
    assert selection["arm_c_candidate_rank"] == 11
    assert selection["arm_c_replaced"] is True

    month.loc[1, "raw_drawdown_score"] = 0.2
    month.loc[2, "raw_drawdown_score"] = -1.0
    _, fallback = module.score_and_select_month(month)
    assert fallback["arm_b_candidate_rank"] == 11
    assert fallback["arm_c_candidate_rank"] == 10
    assert fallback["arm_c_replaced"] is False


def test_effect_gate_requires_full_zero_filled_sequence_and_both_objectives() -> None:
    module = load_module()
    contract = copy.deepcopy(module.load_frozen_contract()[0])
    contract["effect_gates"]["sequence_months"] = 4
    months = pd.DataFrame(
        {
            "eval_date": ["2023-11-30", "2023-12-29", "2024-01-31", "2024-02-29"],
            "arm_c_candidate_rank": [11, 12, 13, 14],
            "arm_c_replaced": [True, True, True, True],
            "arm_c_realized_return_delta": [1.0, 1.0, 1.0, 1.0],
            "arm_c_realized_drawdown_improvement": [1.0, 1.0, 1.0, 1.0],
        }
    )

    result = module.evaluate_effect_qualification(months, contract)
    assert result["passed"] is True
    assert len(result["gates"]) == 9

    months.loc[0, ["arm_c_candidate_rank", "arm_c_replaced"]] = [10, False]
    months.loc[0, "arm_c_realized_return_delta"] = 0.1
    with pytest.raises(RuntimeError, match="nonreplacement_effect_not_zero"):
        module.evaluate_effect_qualification(months, contract)


def test_technical_failure_never_calls_effect_evaluator() -> None:
    module = load_module()
    calls = {"effect": 0}

    def effect(_rows, _contract):
        calls["effect"] += 1
        return {"passed": True}

    result, decision = module.resolve_stage006_outcome(
        technical={"passed": False},
        monthly_selections=pd.DataFrame(),
        contract={},
        effect_evaluator=effect,
    )

    assert result is None
    assert decision == "stage006_contract_or_pit_invalid_stop_no_effect_claim"
    assert calls["effect"] == 0


class _FakeBooster:
    def __init__(self, payload: bytes):
        self.payload = payload

    def save_raw(self, raw_format: str):
        assert raw_format == "ubj"
        return self.payload


class _FakeRanker:
    fit_qids: list[list[int]] = []

    def __init__(self, **params):
        self.params = params

    def fit(self, x, y, *, qid, verbose=False):
        assert verbose is False
        assert len(x) == len(y) == len(qid)
        type(self).fit_qids.append(list(qid))
        return self

    def predict(self, x):
        return np.arange(len(x), dtype=float)

    def get_booster(self):
        return _FakeBooster(b"deterministic-model")


def test_repeated_ranker_uses_qid_and_requires_nonconstant_predictions() -> None:
    module = load_module()
    _FakeRanker.fit_qids.clear()
    train = pd.DataFrame({"f": [0.0, 1.0, 2.0, 3.0]})
    predict = pd.DataFrame({"f": [4.0, 5.0]})

    result = module.fit_repeated_ranker(
        train,
        np.array([0, 1, 0, 1], dtype=np.int64),
        np.array([0, 0, 1, 1], dtype=np.int64),
        predict,
        params={"objective": "rank:ndcg"},
        tolerance=1e-12,
        ranker_factory=_FakeRanker,
    )

    assert result["predictions"].tolist() == [0.0, 1.0]
    assert result["model_sha256"] == result["repeat_model_sha256"]
    assert _FakeRanker.fit_qids == [[0, 0, 1, 1], [0, 0, 1, 1]]


def test_estimator_audit_requires_exact_frozen_xgboost_ranker_and_params() -> None:
    module = load_module()
    contract = module.load_frozen_contract()[0]

    frozen = module.build_estimator_audit(
        module.XGBRanker, contract["xgboost"]["params"]
    )
    replacement = module.build_estimator_audit(
        _FakeRanker, contract["xgboost"]["params"]
    )

    assert frozen["passed"] is True
    assert frozen["factory_is_exact_xgboost_ranker"] is True
    assert frozen["params_exact"] is True
    assert replacement["passed"] is False
    assert replacement["factory_is_exact_xgboost_ranker"] is False


def test_frozen_xgboost_params_are_deterministic_on_synthetic_ranking_data() -> None:
    module = load_module()
    contract = module.load_frozen_contract()[0]
    columns = module.MODEL_FEATURE_COLUMNS
    train = pd.DataFrame(
        np.arange(12 * len(columns), dtype=float).reshape(12, len(columns)),
        columns=columns,
    )
    train[columns[1]] = np.tile([0.0, 1.0, 2.0, 3.0], 3)
    predict = pd.DataFrame(
        np.arange(4 * len(columns), dtype=float).reshape(4, len(columns)),
        columns=columns,
    )
    predict[columns[1]] = [0.0, 1.0, 2.0, 3.0]

    result = module.fit_repeated_ranker(
        train,
        np.tile(np.array([0, 1, 2, 3], dtype=np.int64), 3),
        np.repeat(np.arange(3, dtype=np.int64), 4),
        predict,
        params=contract["xgboost"]["params"],
        tolerance=contract["xgboost"]["repeat_fit_prediction_tolerance"],
    )

    assert len(np.unique(result["predictions"])) == 4
    assert result["prediction_repeat_max_abs_difference"] == 0.0
    assert result["model_sha256"] == result["repeat_model_sha256"]


def _synthetic_label(value: float) -> dict[str, float]:
    return {
        "base_equity": 100.0,
        "end_equity": 100.0 + value,
        "future_return": value / 100.0,
        "future_max_drawdown": -1.0 + value / 200.0,
        "future_net_pnl": value,
        "future_slippage": abs(value),
        "future_trade_count": abs(value),
        "future_trading_days": 20.0,
    }


def test_phase_gated_label_store_requires_fsynced_seal_before_test_open(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "job_outputs"
    jobs = pd.DataFrame(
        [
            {
                "eval_date": "2022-01-31",
                "next_eval_date": "2022-02-28",
                "product_vt_symbol": f"r{rank}.TEST",
                "candidate_rank": rank,
                "job_type": "main",
                "job_id": f"20220131_R{rank}",
            }
            for rank in (10, 11)
        ]
        + [
            {
                "eval_date": "2022-02-28",
                "next_eval_date": "2022-03-31",
                "product_vt_symbol": f"r{rank}.TEST",
                "candidate_rank": rank,
                "job_type": "main",
                "job_id": f"20220228_R{rank}",
            }
            for rank in (10, 11)
        ]
    )
    manifest_files = {}
    for row in jobs.itertuples(index=False):
        path = root / row.job_id / "label.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(_synthetic_label(float(row.candidate_rank - 10))),
            encoding="utf-8",
        )
        manifest_files[f"job_outputs/{row.job_id}/label.json"] = {
            "size": path.stat().st_size,
            "sha256": _sha(path),
        }
    store = module.PhaseGatedLabelStore(
        jobs=jobs,
        label_root=root,
        manifest_files=manifest_files,
        initial_dates=["2022-01-31"],
        test_dates=["2022-02-28"],
    )

    initial = store.open_initial_labels()
    assert len(initial) == 2
    prediction = pd.DataFrame(
        {
            "eval_date": ["2022-02-28", "2022-02-28"],
            "candidate_rank": [10, 11],
            "raw_return_score": [0.0, 1.0],
            "raw_drawdown_score": [0.0, 1.0],
        }
    )
    primary = {"return": b"a", "drawdown": b"b"}
    repeat = {"return": b"a", "drawdown": b"b"}
    selection = {"arm_a_candidate_rank": 10, "arm_b_candidate_rank": 11}
    with pytest.raises(RuntimeError, match="pre_effect_seal_missing"):
        store.open_test_month(
            "2022-02-28",
            tmp_path / "missing.json",
            model_payloads=primary,
            repeat_model_payloads=repeat,
            predictions=prediction,
            selection=selection,
        )

    seal = module.write_pre_effect_seal(
        tmp_path / "pre_effect_seals",
        test_eval_date="2022-02-28",
        model_payloads=primary,
        repeat_model_payloads=repeat,
        predictions=prediction,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )
    with pytest.raises(RuntimeError, match="pre_effect_payload_sha_mismatch"):
        store.open_test_month(
            "2022-02-28",
            seal,
            model_payloads={**primary, "return": b"tampered"},
            repeat_model_payloads=repeat,
            predictions=prediction,
            selection=selection,
        )
    assert store.final_audit()[
        "oos_test_label_rows_opened_after_own_pre_effect_seal"
    ] == 0
    opened = store.open_test_month(
        "2022-02-28",
        seal,
        model_payloads=primary,
        repeat_model_payloads=repeat,
        predictions=prediction,
        selection=selection,
    )

    assert len(opened) == 2
    audit = store.final_audit()
    assert audit["initial_mature_label_rows_opened"] == 2
    assert audit["oos_test_label_rows_opened_before_own_pre_effect_seal"] == 0
    assert audit["oos_test_label_rows_opened_after_own_pre_effect_seal"] == 2


@pytest.mark.parametrize(
    "tamper",
    ["primary_model", "repeat_model", "predictions", "selection"],
)
def test_pre_effect_seal_recomputes_every_bound_payload_before_label_open(
    tmp_path: Path, tamper: str
) -> None:
    module = load_module()
    primary = {"return": b"return-primary", "drawdown": b"drawdown-primary"}
    repeat = {"return": b"return-repeat", "drawdown": b"drawdown-repeat"}
    predictions = pd.DataFrame(
        {
            "eval_date": ["2022-02-28", "2022-02-28"],
            "candidate_rank": [10, 11],
            "raw_return_score": [0.0, 1.0],
            "raw_drawdown_score": [0.0, 1.0],
        }
    )
    selection = {"arm_a_candidate_rank": 10, "arm_b_candidate_rank": 11}
    seal = module.write_pre_effect_seal(
        tmp_path / "pre_effect_seals",
        test_eval_date="2022-02-28",
        model_payloads=primary,
        repeat_model_payloads=repeat,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )
    checked_primary = dict(primary)
    checked_repeat = dict(repeat)
    checked_predictions = predictions.copy()
    checked_selection = dict(selection)
    if tamper == "primary_model":
        checked_primary["return"] = b"tampered"
    elif tamper == "repeat_model":
        checked_repeat["drawdown"] = b"tampered"
    elif tamper == "predictions":
        checked_predictions.loc[1, "raw_return_score"] = 999.0
    else:
        checked_selection["arm_b_candidate_rank"] = 12

    with pytest.raises(RuntimeError, match="pre_effect_payload_sha_mismatch"):
        module.verify_pre_effect_seal(
            seal,
            "2022-02-28",
            model_payloads=checked_primary,
            repeat_model_payloads=checked_repeat,
            predictions=checked_predictions,
            selection=checked_selection,
        )


def test_pre_effect_seal_rejects_malformed_model_digest(tmp_path: Path) -> None:
    module = load_module()
    primary = {"return": b"return-primary", "drawdown": b"drawdown-primary"}
    repeat = {"return": b"return-repeat", "drawdown": b"drawdown-repeat"}
    predictions = pd.DataFrame(
        {
            "eval_date": ["2022-02-28", "2022-02-28"],
            "candidate_rank": [10, 11],
        }
    )
    selection = {"arm_a_candidate_rank": 10, "arm_b_candidate_rank": 11}
    seal = module.write_pre_effect_seal(
        tmp_path / "pre_effect_seals",
        test_eval_date="2022-02-28",
        model_payloads=primary,
        repeat_model_payloads=repeat,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )
    payload = json.loads(seal.read_text(encoding="utf-8"))
    payload["primary_model_sha256"]["return"] = "NOT_A_SHA"
    seal.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="pre_effect_seal_invalid"):
        module.verify_pre_effect_seal(
            seal,
            "2022-02-28",
            model_payloads=primary,
            repeat_model_payloads=repeat,
            predictions=predictions,
            selection=selection,
        )


def test_authorization_binds_files_nonce_and_single_scope(tmp_path: Path) -> None:
    module = load_module()
    bound = {}
    for name in module.AUTHORIZATION_BOUND_FILE_NAMES:
        path = tmp_path / f"{name}.txt"
        path.write_text(name, encoding="utf-8")
        bound[name] = path
    payload = {
        "line_id": module.LINE_ID,
        "stage": "Stage006",
        "decision": "ALLOW_FROZEN_STAGE006_DEVELOPMENT_RUN",
        "scope": module.RUN_AUTHORIZATION_SCOPE,
        "run_nonce": "a" * 64,
        "bound_files": {
            name: {"path": str(path), "sha256": _sha(path)}
            for name, path in bound.items()
        },
    }
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps(payload), encoding="utf-8")

    loaded, audit = module.load_run_authorization(
        authorization_path=authorization,
        bound_paths=bound,
        expected_authorization_sha256=_sha(authorization),
    )

    assert loaded == payload
    assert audit["run_nonce"] == "a" * 64
    bound["runner"].write_text("drift", encoding="utf-8")
    with pytest.raises(RuntimeError, match="frozen_input_sha_mismatch:runner"):
        module.load_run_authorization(
            authorization_path=authorization,
            bound_paths=bound,
            expected_authorization_sha256=_sha(authorization),
        )


def test_artifact_bundle_is_atomic_manifested_and_non_overwritable(tmp_path: Path) -> None:
    module = load_module()
    result_dir = tmp_path / "frozen_run"

    published = module.publish_artifact_bundle(
        result_dir,
        csv_frames={"rows.csv": pd.DataFrame({"a": [1]})},
        json_payloads={"decision.json": {"passed": False}},
        text_payloads={"report.md": "# report\n"},
        model_payloads={"20240131_return.ubj": b"model"},
        seal_payloads={"2024-01-31.json": {"sealed": True}},
    )

    assert "artifact_manifest.json" in published
    assert "pre_effect_seals/2024-01-31.json" in published
    manifest = json.loads((result_dir / "artifact_manifest.json").read_text())
    assert "artifact_manifest.json" not in manifest["artifacts"]
    with pytest.raises(RuntimeError, match="stage006_result_already_exists"):
        module.publish_artifact_bundle(
            result_dir,
            csv_frames={},
            json_payloads={},
            text_payloads={},
            model_payloads={},
            seal_payloads={},
        )


def test_csv_identity_header_reader_never_parses_data_rows(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "labels.csv"
    path.write_text("a,b\n1,secret\n2,secret\n", encoding="utf-8")

    result = module.verify_csv_identity_and_header_only(
        path, expected_sha256=_sha(path), expected_header=["a", "b"]
    )

    assert result["data_rows_parsed"] == 0
    assert result["sha256"] == _sha(path)


def test_metadata_loader_never_passes_aggregate_label_csvs_to_pandas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    paths = {
        "FEATURE_PANEL_PATH": tmp_path / "features.csv",
        "FULL_SPLIT_PATH": tmp_path / "splits.csv",
        "DEVELOPMENT_JOBS_PATH": tmp_path / "jobs.csv",
        "DEVELOPMENT_LABELS_PATH": tmp_path / "development_labels.csv",
        "RECONCILIATION_PATH": tmp_path / "reconciliation.csv",
        "STAGE005_MANIFEST_PATH": tmp_path / "manifest.json",
    }
    for name, path in paths.items():
        monkeypatch.setattr(module, name, path)
    paths["FEATURE_PANEL_PATH"].write_text("feature\n1\n", encoding="utf-8")
    paths["FULL_SPLIT_PATH"].write_text("split\n1\n", encoding="utf-8")
    paths["DEVELOPMENT_JOBS_PATH"].write_text("job\n1\n", encoding="utf-8")
    paths["DEVELOPMENT_LABELS_PATH"].write_text(
        "secret\nnever-parse\n", encoding="utf-8"
    )
    paths["RECONCILIATION_PATH"].write_text(
        "secret\nnever-parse\n", encoding="utf-8"
    )
    paths["STAGE005_MANIFEST_PATH"].write_text(
        json.dumps({"file_count_excluding_manifest": 0, "files": {}}),
        encoding="utf-8",
    )
    original_read_csv = module.pd.read_csv
    reads: list[Path] = []

    def tracked_read_csv(path, *args, **kwargs):
        resolved = Path(path)
        reads.append(resolved)
        if resolved in {
            paths["DEVELOPMENT_LABELS_PATH"],
            paths["RECONCILIATION_PATH"],
        }:
            pytest.fail("aggregate label data must remain outside pandas")
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(module.pd, "read_csv", tracked_read_csv)
    module.load_stage006_metadata()

    assert reads == [
        paths["FEATURE_PANEL_PATH"],
        paths["FULL_SPLIT_PATH"],
        paths["DEVELOPMENT_JOBS_PATH"],
    ]


def _synthetic_store(module, jobs: pd.DataFrame, root: Path):
    manifest_files = {}
    for row in jobs.itertuples(index=False):
        path = root / row.job_id / "label.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_synthetic_label(float(row.candidate_rank - 10))),
            encoding="utf-8",
        )
        manifest_files[f"job_outputs/{row.job_id}/label.json"] = {
            "size": path.stat().st_size,
            "sha256": _sha(path),
        }
    return manifest_files


def test_sequential_oos_seals_each_fold_before_opening_test_labels(tmp_path: Path) -> None:
    module = load_module()
    features, splits, jobs, contract = _synthetic_metadata(module, months=5)
    panel, _ = module.build_development_metadata_panel(features, splits, jobs, contract)
    folds = module.build_pit_folds(panel, minimum_train_months=2)
    initial_dates = sorted(panel["eval_date"].unique())[:2]
    test_dates = [fold.test_date.date().isoformat() for fold in folds]
    root = tmp_path / "job_outputs"
    manifest_files = _synthetic_store(module, jobs, root)
    store = module.PhaseGatedLabelStore(
        jobs=jobs,
        label_root=root,
        manifest_files=manifest_files,
        initial_dates=initial_dates,
        test_dates=test_dates,
    )
    contract["pit_split"].update(
        {
            "minimum_train_months": 2,
            "test_folds": 3,
            "test_start": test_dates[0],
            "test_end": test_dates[-1],
            "initial_mature_training_months": 2,
            "initial_mature_training_rows": 5,
            "oos_test_rows": 7,
            "expected_train_month_counts": "2..4",
        }
    )
    contract["xgboost"].update(
        {
            "primary_model_count": 6,
            "repeat_model_count": 6,
            "total_fit_call_count": 12,
        }
    )
    contract["execution_scope"].update(
        {
            "primary_fit_calls": 6,
            "repeat_fit_calls": 6,
            "total_fit_calls": 12,
        }
    )
    contract["label_access_state_machine"]["required_final_integer_counts"].update(
        {
            "initial_mature_label_rows_opened": 5,
            "oos_test_label_rows_opened_after_own_pre_effect_seal": 7,
            "oos_test_label_rows_used_for_effect_after_seal": 7,
        }
    )

    result = module.train_sequential_oos(
        panel=panel,
        folds=folds,
        label_store=store,
        contract=contract,
        pre_effect_dir=tmp_path / "pre_effect_seals",
        ranker_factory=_FakeRanker,
    )

    assert len(result["predictions"]) == 7
    assert len(result["monthly_selections"]) == 3
    assert len(result["fold_audit"]) == 3
    assert len(result["model_payloads"]) == 6
    assert len(result["seal_payloads"]) == 3
    assert result["fit_call_count"] == 12
    assert result["label_access_audit"]["initial_mature_label_rows_opened"] == 5
    assert (
        result["label_access_audit"][
            "oos_test_label_rows_opened_before_own_pre_effect_seal"
        ]
        == 0
    )
    assert result["label_access_audit"]["oos_test_label_rows_opened_after_own_pre_effect_seal"] == 7


def test_technical_gate_and_realized_effect_attachment_are_mechanical(tmp_path: Path) -> None:
    module = load_module()
    features, splits, jobs, contract = _synthetic_metadata(module, months=5)
    panel, panel_audit = module.build_development_metadata_panel(
        features, splits, jobs, contract
    )
    folds = module.build_pit_folds(panel, minimum_train_months=2)
    initial_dates = sorted(panel["eval_date"].unique())[:2]
    test_dates = [fold.test_date.date().isoformat() for fold in folds]
    root = tmp_path / "job_outputs"
    store = module.PhaseGatedLabelStore(
        jobs=jobs,
        label_root=root,
        manifest_files=_synthetic_store(module, jobs, root),
        initial_dates=initial_dates,
        test_dates=test_dates,
    )
    contract["pit_split"].update(
        {
            "minimum_train_months": 2,
            "test_folds": 3,
            "test_start": test_dates[0],
            "test_end": test_dates[-1],
            "initial_mature_training_rows": 5,
            "oos_test_rows": 7,
            "expected_train_month_counts": "2..4",
        }
    )
    contract["xgboost"].update(
        {
            "primary_model_count": 6,
            "repeat_model_count": 6,
            "total_fit_call_count": 12,
        }
    )
    contract["execution_scope"].update(
        {
            "primary_fit_calls": 6,
            "repeat_fit_calls": 6,
            "total_fit_calls": 12,
        }
    )
    contract["effect_gates"].update(
        {"sequence_months": 3}
    )
    contract["effect_gates"]["replacement_months"]["threshold"] = 3
    contract["effect_gates"]["replacement_years"]["required"] = [2022]
    required_counts = contract["label_access_state_machine"][
        "required_final_integer_counts"
    ]
    required_counts["initial_mature_label_rows_opened"] = 5
    required_counts["oos_test_label_rows_opened_after_own_pre_effect_seal"] = 7
    required_counts["oos_test_label_rows_used_for_effect_after_seal"] = 7
    training = module.train_sequential_oos(
        panel=panel,
        folds=folds,
        label_store=store,
        contract=contract,
        pre_effect_dir=tmp_path / "pre_effect_seals",
        ranker_factory=_FakeRanker,
    )
    assert training["estimator_audit"]["passed"] is False
    runtime = {"frozen": True}
    scope = module.build_execution_scope_audit(training, contract)
    rejected = module.evaluate_technical_qualification(
        input_audit={"all_input_identities_verified": True},
        panel_audit=panel_audit,
        folds=folds,
        training_result=training,
        contract=contract,
        runtime_identities=[runtime, runtime, runtime],
        execution_scope=scope,
    )
    assert rejected["passed"] is False
    assert rejected["gates"]["frozen_estimator_and_params_exact"] is False

    training["estimator_audit"] = module.build_estimator_audit(
        module.XGBRanker, contract["xgboost"]["params"]
    )
    technical = module.evaluate_technical_qualification(
        input_audit={"all_input_identities_verified": True},
        panel_audit=panel_audit,
        folds=folds,
        training_result=training,
        contract=contract,
        runtime_identities=[runtime, runtime, runtime],
        execution_scope=scope,
    )

    assert technical["passed"] is True, {
        key: value for key, value in technical["gates"].items() if not value
    }
    realized = module.attach_realized_effects(
        training["monthly_selections"], store.opened_labels()
    )
    effect = module.evaluate_effect_qualification(realized, contract)
    assert effect["passed"] is True
    assert realized["arm_c_realized_return_delta"].gt(0).all()
    assert realized["arm_c_realized_drawdown_improvement"].gt(0).all()


def test_authorization_consumption_is_single_use(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "consumption.json"
    authorization = {
        "scope": module.RUN_AUTHORIZATION_SCOPE,
        "run_nonce": "b" * 64,
    }
    audit = {"authorization_sha256": "c" * 64}

    receipt = module.consume_run_authorization(
        authorization, audit, consumption_path=path
    )

    assert receipt["run_nonce"] == "b" * 64
    assert path.is_file()
    with pytest.raises(RuntimeError, match="authorization_already_consumed"):
        module.consume_run_authorization(
            authorization, audit, consumption_path=path
        )


def test_authorization_consumption_has_one_winner_under_concurrency(
    tmp_path: Path,
) -> None:
    module = load_module()
    path = tmp_path / "consumption.json"
    authorization = {
        "scope": module.RUN_AUTHORIZATION_SCOPE,
        "run_nonce": "d" * 64,
    }
    audit = {"authorization_sha256": "e" * 64}

    def consume() -> bool:
        try:
            module.consume_run_authorization(
                authorization, audit, consumption_path=path
            )
            return True
        except RuntimeError as error:
            assert "authorization_already_consumed" in str(error)
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        outcomes = list(executor.map(lambda _index: consume(), range(16)))

    assert sum(outcomes) == 1
    assert path.is_file()


def _fake_execution_checkpoint(module, contract, name: str) -> dict[str, object]:
    return {
        "checkpoint": name,
        "contract": contract,
        "contract_audit": {"contract_sha256": "1" * 64},
        "authorization": {
            "scope": module.RUN_AUTHORIZATION_SCOPE,
            "run_nonce": "2" * 64,
        },
        "authorization_audit": {
            "authorization_sha256": "3" * 64,
            "run_nonce": "2" * 64,
            "scope": module.RUN_AUTHORIZATION_SCOPE,
            "bound_file_identities": {"runner": {"sha256": "4" * 64}},
        },
        "runtime_identity": {"frozen_runtime": True},
        "input_identity_audit": {
            "all_input_identities_verified": True,
            "identity_digest": "5" * 64,
            "aggregate_development_label_data_rows_parsed": 0,
            "aggregate_reconciliation_data_rows_parsed": 0,
        },
    }


def _fake_training_result() -> dict[str, object]:
    return {
        "predictions": pd.DataFrame(
            {
                "eval_date": ["2024-01-31"],
                "candidate_rank": [10],
                "product_vt_symbol": ["r10.TEST"],
            }
        ),
        "monthly_selections": pd.DataFrame(
            {
                "eval_date": ["2024-01-31"],
                "arm_a_candidate_rank": [10],
                "arm_b_candidate_rank": [10],
                "arm_c_candidate_rank": [10],
                "arm_c_replaced": [False],
            }
        ),
        "fold_audit": pd.DataFrame({"test_eval_date": ["2024-01-31"]}),
        "model_payloads": {"20240131_return_relevance.ubj": b"model"},
        "repeat_model_hashes": {
            "20240131_return_relevance.ubj": "6" * 64
        },
        "seal_payloads": {"2024-01-31.json": {"sealed": True}},
        "fit_call_count": 2,
        "label_access_audit": {
            "aggregate_development_label_data_rows_parsed": 0,
            "aggregate_reconciliation_data_rows_parsed": 0,
        },
    }


class _FakeOpenedLabelStore:
    def opened_labels(self) -> pd.DataFrame:
        return pd.DataFrame()


def test_frozen_run_requires_authorization_before_any_data_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    calls = {"checkpoint": 0, "prepare": 0, "consume": 0}

    monkeypatch.setattr(
        module,
        "capture_execution_checkpoint",
        lambda **_kwargs: calls.__setitem__("checkpoint", calls["checkpoint"] + 1),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "prepare_stage006_run_data",
        lambda _contract: calls.__setitem__("prepare", calls["prepare"] + 1),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "consume_run_authorization",
        lambda *_args, **_kwargs: calls.__setitem__("consume", calls["consume"] + 1),
    )

    with pytest.raises(RuntimeError, match="stage006_run_authorization_sha_required"):
        module.run_frozen_stage006(
            expected_authorization_sha256=None,
        )

    assert calls == {"checkpoint": 0, "prepare": 0, "consume": 0}


def test_production_run_signature_has_no_path_or_ranker_overrides() -> None:
    module = load_module()
    signature = inspect.signature(module.run_frozen_stage006)

    assert set(signature.parameters) == {"expected_authorization_sha256"}
    assert module._canonical_stage006_run_paths() == {
        "authorization": module.RUN_AUTHORIZATION_PATH,
        "consumption": module.AUTHORIZATION_CONSUMPTION_PATH,
        "result": module.RESULT_DIR,
    }
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        module.run_frozen_stage006(
            expected_authorization_sha256="a" * 64,
            consumption_path=Path("different-consumption.json"),
        )


def test_frozen_run_preflights_nonoverwrite_before_consuming_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    calls = {"checkpoint": 0, "consume": 0}
    monkeypatch.setattr(
        module,
        "capture_execution_checkpoint",
        lambda **_kwargs: calls.__setitem__("checkpoint", calls["checkpoint"] + 1),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "consume_run_authorization",
        lambda *_args, **_kwargs: calls.__setitem__("consume", calls["consume"] + 1),
    )
    monkeypatch.setattr(
        module,
        "_canonical_stage006_run_paths",
        lambda: {
            "authorization": tmp_path / "authorization.json",
            "consumption": tmp_path / "consumption.json",
            "result": result_dir,
        },
    )

    with pytest.raises(RuntimeError, match="stage006_result_already_exists"):
        module.run_frozen_stage006(
            expected_authorization_sha256="a" * 64,
        )

    assert calls == {"checkpoint": 0, "consume": 0}


def test_technical_failure_publishes_diagnostics_without_model_prediction_or_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    contract = copy.deepcopy(module.load_frozen_contract()[0])
    checkpoints: list[str] = []
    published: dict[str, object] = {}

    def capture(*, checkpoint, **_kwargs):
        checkpoints.append(checkpoint)
        return _fake_execution_checkpoint(module, contract, checkpoint)

    monkeypatch.setattr(module, "capture_execution_checkpoint", capture, raising=False)
    monkeypatch.setattr(
        module,
        "consume_run_authorization",
        lambda *_args, **_kwargs: {"consumed": True},
    )
    monkeypatch.setattr(
        module,
        "prepare_stage006_run_data",
        lambda _contract: {
            "panel": pd.DataFrame(),
            "panel_audit": {},
            "folds": [],
            "label_store": _FakeOpenedLabelStore(),
        },
        raising=False,
    )
    monkeypatch.setattr(module, "train_sequential_oos", lambda **_kwargs: _fake_training_result())
    monkeypatch.setattr(
        module,
        "build_execution_scope_audit",
        lambda *_args, **_kwargs: {"passed": False},
    )
    monkeypatch.setattr(
        module,
        "evaluate_technical_qualification",
        lambda **_kwargs: {"passed": False, "gates": {"scope": False}},
    )
    monkeypatch.setattr(
        module,
        "attach_realized_effects",
        lambda *_args, **_kwargs: pytest.fail("effect rows must not be attached"),
    )
    monkeypatch.setattr(
        module,
        "evaluate_effect_qualification",
        lambda *_args, **_kwargs: pytest.fail("effect gate must not run"),
    )

    def publish(_result_dir, **kwargs):
        published.update(kwargs)
        return {"artifact_manifest.json": {"sha256": "7" * 64}}

    monkeypatch.setattr(module, "publish_artifact_bundle", publish)
    monkeypatch.setattr(
        module,
        "_canonical_stage006_run_paths",
        lambda: {
            "authorization": tmp_path / "authorization.json",
            "consumption": tmp_path / "consumption.json",
            "result": tmp_path / "result",
        },
    )
    result = module.run_frozen_stage006(
        expected_authorization_sha256="a" * 64,
    )

    assert checkpoints == ["before_training", "after_all_models"]
    assert result["decision"] == "stage006_contract_or_pit_invalid_stop_no_effect_claim"
    assert set(published["csv_frames"]) == {"fold_audit.csv"}
    assert "effect_qualification.json" not in published["json_payloads"]
    assert "model_manifest.json" not in published["json_payloads"]
    assert published["model_payloads"] == {}
    assert published["seal_payloads"] == {}


def test_successful_frozen_run_reverifies_after_effect_and_publishes_complete_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    contract = copy.deepcopy(module.load_frozen_contract()[0])
    checkpoints: list[str] = []
    published: dict[str, object] = {}
    training = _fake_training_result()

    def capture(*, checkpoint, **_kwargs):
        checkpoints.append(checkpoint)
        return _fake_execution_checkpoint(module, contract, checkpoint)

    monkeypatch.setattr(module, "capture_execution_checkpoint", capture, raising=False)
    monkeypatch.setattr(
        module,
        "consume_run_authorization",
        lambda *_args, **_kwargs: {"consumed": True},
    )
    monkeypatch.setattr(
        module,
        "prepare_stage006_run_data",
        lambda _contract: {
            "panel": pd.DataFrame(),
            "panel_audit": {},
            "folds": [],
            "label_store": _FakeOpenedLabelStore(),
        },
        raising=False,
    )
    monkeypatch.setattr(module, "train_sequential_oos", lambda **_kwargs: training)
    monkeypatch.setattr(
        module,
        "build_execution_scope_audit",
        lambda *_args, **_kwargs: {"passed": True},
    )
    monkeypatch.setattr(
        module,
        "evaluate_technical_qualification",
        lambda **_kwargs: {"passed": True, "gates": {"all": True}},
    )
    realized = training["monthly_selections"].copy()
    realized["arm_c_realized_return_delta"] = 0.0
    realized["arm_c_realized_drawdown_improvement"] = 0.0
    monkeypatch.setattr(module, "attach_realized_effects", lambda *_args: realized)
    monkeypatch.setattr(
        module,
        "evaluate_effect_qualification",
        lambda *_args: {"passed": True, "gates": {"all": True}},
    )

    def publish(_result_dir, **kwargs):
        published.update(kwargs)
        return {"artifact_manifest.json": {"sha256": "8" * 64}}

    monkeypatch.setattr(module, "publish_artifact_bundle", publish)
    monkeypatch.setattr(
        module,
        "_canonical_stage006_run_paths",
        lambda: {
            "authorization": tmp_path / "authorization.json",
            "consumption": tmp_path / "consumption.json",
            "result": tmp_path / "result",
        },
    )
    result = module.run_frozen_stage006(
        expected_authorization_sha256="a" * 64,
    )

    assert checkpoints == [
        "before_training",
        "after_all_models",
        "after_effect_evaluation",
    ]
    assert result["decision"] == (
        "stage006_dual_ranker_development_oos_pass_allow_true_engine_ac_preregistration"
    )
    assert set(published["csv_frames"]) == {
        "ordered_oos_predictions.csv",
        "monthly_arm_selections.csv",
        "fold_audit.csv",
    }
    assert "effect_qualification.json" in published["json_payloads"]
    assert "model_manifest.json" in published["json_payloads"]
    assert published["model_payloads"] == training["model_payloads"]
    assert published["seal_payloads"] == training["seal_payloads"]

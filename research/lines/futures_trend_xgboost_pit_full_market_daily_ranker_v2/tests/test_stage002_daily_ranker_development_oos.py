from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage002_daily_ranker_development_oos as stage002


def _plan_and_prices() -> tuple[pd.DataFrame, pd.DataFrame]:
    products = ["a.EX", "b.EX", "c.EX", "d.EX", "e.EX"]
    rows: list[dict[str, object]] = []
    prices: list[dict[str, object]] = []
    for query_date, entry_date, label_end, prefix in (
        ("2024-01-02", "2024-01-03", "2024-01-31", "JAN"),
        ("2024-02-01", "2024-02-02", "2024-02-29", "FEB"),
    ):
        for index, product in enumerate(products, start=1):
            contract = f"{prefix}{index}.EX"
            rows.append(
                {
                    "query_date": query_date,
                    "product_vt_symbol": product,
                    "main_contract_vt": contract,
                    "entry_date": entry_date,
                    "label_end": label_end,
                }
            )
            prices.extend(
                [
                    {
                        "date": entry_date,
                        "contract_vt_symbol": contract,
                        "close_price": 100.0,
                    },
                    {
                        "date": label_end,
                        "contract_vt_symbol": contract,
                        "close_price": 100.0 + index,
                    },
                ]
            )
    return pd.DataFrame(rows), pd.DataFrame(prices)


def _prediction_payload() -> tuple[pd.DataFrame, dict[str, object], dict[str, str]]:
    predictions = pd.DataFrame(
        {
            "test_eval_date": ["2024-02-01", "2024-02-01"],
            "product_vt_symbol": ["a.EX", "b.EX"],
            "xgb_score": [0.2, 0.1],
        }
    )
    selection = {
        "test_eval_date": "2024-02-01",
        "anchor_product": "a.EX",
        "challenger_product": "b.EX",
        "selected_product": "a.EX",
        "replaced": False,
    }
    hashes = {"primary": "1" * 64, "repeat": "1" * 64}
    return predictions, selection, hashes


def test_phase_store_opens_only_mature_training_labels() -> None:
    plan, prices = _plan_and_prices()
    store = stage002.PhaseGatedLabelStore(plan, prices)

    assert store.audit()["unique_label_rows_opened"] == 0

    opened = store.open_training_labels(pd.Timestamp("2024-02-01"))

    assert opened["query_date"].nunique() == 1
    assert opened["query_date"].max() == pd.Timestamp("2024-01-02")
    assert opened["label_end"].max() < pd.Timestamp("2024-02-01")
    assert opened["relevance"].notna().all()
    assert store.audit()["unique_label_rows_opened"] == 5
    assert store.audit()["close_value_reads"] == 10

    reopened = store.open_training_labels(pd.Timestamp("2024-02-01"))
    assert len(reopened) == 5
    assert store.audit()["close_value_reads"] == 10


def test_phase_store_rejects_test_effect_access_before_matching_seal(
    tmp_path: Path,
) -> None:
    plan, prices = _plan_and_prices()
    store = stage002.PhaseGatedLabelStore(plan, prices)
    predictions, selection, hashes = _prediction_payload()
    missing_seal = tmp_path / "missing.json"

    with pytest.raises(stage002.Stage002Error, match="effect_seal_missing"):
        store.open_effect_labels(
            pd.Timestamp("2024-02-01"),
            ["a.EX", "b.EX"],
            seal_path=missing_seal,
            model_hashes=hashes,
            predictions=predictions,
            selection=selection,
        )

    seal = stage002.write_pre_effect_seal(
        tmp_path,
        test_eval_date=pd.Timestamp("2024-02-01"),
        model_hashes=hashes,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )
    opened = store.open_effect_labels(
        pd.Timestamp("2024-02-01"),
        ["a.EX", "b.EX"],
        seal_path=seal,
        model_hashes=hashes,
        predictions=predictions,
        selection=selection,
    )
    assert len(opened) == 2
    assert store.audit()["unique_label_rows_opened"] == 2
    assert store.label_rows_opened_for(pd.Timestamp("2024-02-01")) == 2

    tampered = dict(selection)
    tampered["selected_product"] = "b.EX"
    with pytest.raises(stage002.Stage002Error, match="pre_effect_seal_mismatch"):
        stage002.verify_pre_effect_seal(
            seal,
            model_hashes=hashes,
            predictions=predictions,
            selection=tampered,
        )


def test_highest_challenger_without_plan_is_technical_failure_without_fallback(
    tmp_path: Path,
) -> None:
    plan, prices = _plan_and_prices()
    store = stage002.PhaseGatedLabelStore(plan, prices)
    predictions, selection, hashes = _prediction_payload()
    predictions.loc[predictions["product_vt_symbol"].eq("b.EX"), "product_vt_symbol"] = (
        "missing.EX"
    )
    selection["challenger_product"] = "missing.EX"
    selection["selected_product"] = "missing.EX"
    selection["replaced"] = True
    seal = stage002.write_pre_effect_seal(
        tmp_path,
        test_eval_date=pd.Timestamp("2024-02-01"),
        model_hashes=hashes,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )

    with pytest.raises(stage002.Stage002Error, match="effect_label_missing"):
        store.open_effect_labels(
            pd.Timestamp("2024-02-01"),
            ["a.EX", "missing.EX"],
            seal_path=seal,
            model_hashes=hashes,
            predictions=predictions,
            selection=selection,
        )
    assert selection["challenger_product"] == "missing.EX"
    assert store.audit()["effect_label_rows_opened"] == 0


def _passing_technical() -> dict[str, object]:
    return {
        "input_identity_stable": True,
        "authorization_valid": True,
        "label_plan_rows": 52484,
        "opened_label_rows": 52427,
        "opened_training_qids": 1045,
        "close_value_reads": 104854,
        "future_return_calculations": 52427,
        "relevance_level_failure_count": 0,
        "fold_count": 37,
        "fit_call_count": 74,
        "future_train_qid_count": 0,
        "estimator_audit_passed": True,
        "repeat_prediction_max_abs_difference": 0.0,
        "repeat_model_hash_mismatch_count": 0,
        "constant_prediction_fold_count": 0,
        "zero_split_fold_count": 0,
        "seal_count": 37,
        "test_label_rows_read_before_seal": 0,
        "effect_fold_count": 36,
        "effect_label_rows_opened": 72,
        "inference_fold_count": 1,
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
    }


def test_technical_assessment_requires_every_frozen_counter() -> None:
    passing = stage002.assess_technical_gates(_passing_technical())
    assert passing["passed"] is True

    for field in _passing_technical():
        failed = _passing_technical()
        value = failed[field]
        failed[field] = False if value is True else (1 if value == 0 else 0)
        result = stage002.assess_technical_gates(failed)
        assert result["passed"] is False, field


def test_execution_event_is_exclusive_and_records_authorization_sha(
    tmp_path: Path,
) -> None:
    event_path = tmp_path / "execution_event.json"

    stage002.create_execution_event(
        event_path,
        authorization_sha256="a" * 64,
        nonce="nonce-1",
    )

    payload = json.loads(event_path.read_text("utf-8"))
    assert payload["authorization_sha256"] == "a" * 64
    assert payload["nonce"] == "nonce-1"
    with pytest.raises(stage002.Stage002Error, match="execution_event_exists"):
        stage002.create_execution_event(
            event_path,
            authorization_sha256="a" * 64,
            nonce="nonce-1",
        )


def _authorization_fixture() -> dict[str, object]:
    return {
        "line_id": stage002.LINE_ID,
        "stage": stage002.STAGE,
        "authorized": True,
        "nonce": "fixture-nonce",
    }


def test_event_is_consumed_before_input_loading_and_load_failure_is_manifested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    line_dir = tmp_path / "line"
    output_dir = line_dir / "artifacts" / "final"
    event_path = line_dir / "artifacts" / "event.json"
    authorization_path = line_dir / "stages" / "authorization.json"
    authorization_path.parent.mkdir(parents=True)
    authorization_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        stage002,
        "verify_authorization",
        lambda *_args, **_kwargs: _authorization_fixture(),
    )

    def fail_loading(_paths: object) -> dict[str, object]:
        assert event_path.is_file()
        raise stage002.Stage002Error("fixture_load_failure")

    monkeypatch.setattr(stage002, "_load_inputs", fail_loading)

    summary = stage002.run_stage002(
        line_dir=line_dir,
        output_dir=output_dir,
        authorization_path=authorization_path,
        execution_event_path=event_path,
        input_paths={},
        expected_sha256={},
    )

    assert summary["decision"] == stage002.TECHNICAL_FAIL_DECISION
    assert summary["failure_phase"] == "before_progress_initialization"
    assert stage002.verify_published_bundle(output_dir)["verified"] is True
    event = json.loads(event_path.read_text("utf-8"))
    assert event["status"] == "completed"


def test_partial_failure_bundle_preserves_models_seals_and_actual_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    line_dir = tmp_path / "line"
    output_dir = line_dir / "artifacts" / "final"
    event_path = line_dir / "artifacts" / "event.json"
    authorization_path = line_dir / "stages" / "authorization.json"
    authorization_path.parent.mkdir(parents=True)
    authorization_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        stage002,
        "verify_authorization",
        lambda *_args, **_kwargs: _authorization_fixture(),
    )
    monkeypatch.setattr(stage002, "_load_inputs", lambda _paths: {})

    def fail_after_partial_evidence(
        staging: Path,
        **_kwargs: object,
    ) -> dict[str, object]:
        (staging / "models").mkdir(parents=True)
        (staging / "pre_effect_seals").mkdir()
        (staging / "models" / "fold_primary.ubj").write_bytes(b"model")
        (staging / "pre_effect_seals" / "2024-03-29.json").write_text(
            "{}\n", encoding="utf-8"
        )
        stage002._write_json(
            staging / "label_access_audit.json",
            {"effect_label_rows_opened": 14, "unique_label_rows_opened": 100},
        )
        stage002._write_json(
            staging / "run_progress.json",
            {
                "phase": "effect_labels_opened",
                "current_test_date": "2024-03-29",
                "last_completed_fold": "2024-02-29",
            },
        )
        raise stage002.Stage002Error("fixture_partial_failure")

    monkeypatch.setattr(stage002, "_execute_stage002", fail_after_partial_evidence)

    summary = stage002.run_stage002(
        line_dir=line_dir,
        output_dir=output_dir,
        authorization_path=authorization_path,
        execution_event_path=event_path,
        input_paths={},
        expected_sha256={},
    )

    assert summary["effect"]["not_opened"] is False
    assert summary["effect"]["partial_effect_label_rows_opened"] == 14
    assert summary["last_completed_fold"] == "2024-02-29"
    assert (output_dir / "models" / "fold_primary.ubj").is_file()
    assert (output_dir / "pre_effect_seals" / "2024-03-29.json").is_file()
    assert stage002.verify_published_bundle(output_dir)["verified"] is True

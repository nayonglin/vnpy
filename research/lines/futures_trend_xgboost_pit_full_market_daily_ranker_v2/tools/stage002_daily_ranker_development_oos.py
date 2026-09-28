from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import xgboost
from xgboost import XGBRanker

from daily_ranker_development import (
    MODEL_PARAMS,
    ContractPriceIndex,
    DevelopmentError,
    add_cross_sectional_relevance,
    assess_effect_gates,
    build_estimator_audit,
    build_ranker_arrays,
    compute_effect_metrics,
    fit_repeated_ranker,
    generate_label_values,
    select_one_slot,
)


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
UPSTREAM_LINE_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker"
)
UPSTREAM_TOOLS = UPSTREAM_LINE_DIR / "tools"
if str(UPSTREAM_TOOLS) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_TOOLS))

import daily_ranker_contract as upstream_contract
import stage001_daily_ranker_contract as upstream_stage001


LINE_ID = "futures_trend_xgboost_pit_full_market_daily_ranker_v2"
STAGE = "stage002_daily_ranker_development_oos"
TECHNICAL_FAIL_DECISION = (
    "stage002_daily_ranker_contract_or_pit_invalid_stop_no_effect_claim"
)
EFFECT_FAIL_DECISION = (
    "stage002_daily_ranker_development_oos_fail_stop_no_true_engine"
)
PASS_DECISION = (
    "stage002_daily_ranker_development_oos_pass_allow_true_engine_ac_"
    "preregistration_only"
)

V2_STAGE001_DIR = LINE_DIR / "artifacts/stage001_v2_contract_requalification"
V1_STAGE001_DIR = UPSTREAM_LINE_DIR / "artifacts/stage001_daily_ranker_contract"
SOURCE_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/"
    "artifacts/stage002_endofday_source_rebuild"
)
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage002_daily_ranker_development_oos"
DEFAULT_AUTHORIZATION_PATH = (
    LINE_DIR / "stages/20260904_stage002_execution_authorization.json"
)
DEFAULT_EXECUTION_EVENT_PATH = LINE_DIR / "artifacts/stage002_execution_event.json"
PREREGISTRATION_PATH = (
    LINE_DIR
    / "stages/20260904_2340_stage002_daily_ranker_development_oos_"
    "preregistration.md"
)

DEFAULT_INPUT_PATHS = {
    "v2_manifest": V2_STAGE001_DIR / "artifact_manifest.json",
    "v2_summary": V2_STAGE001_DIR / "summary.json",
    "v1_manifest": V1_STAGE001_DIR / "artifact_manifest.json",
    "model_features": V1_STAGE001_DIR / "model_feature_panel.csv.gz",
    "label_plan": V1_STAGE001_DIR / "label_plan.csv.gz",
    "formal_scoring": V1_STAGE001_DIR / "formal_scoring_plan.csv",
    "fold_plan": V1_STAGE001_DIR / "fold_plan.csv",
    "bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
}
DEFAULT_EXPECTED_SHA256 = {
    "v2_manifest": "7428e753607ff44b39f0e3510e29493ec96b4163a35fa261791da7d819b27b79",
    "v2_summary": "a25817cbbd6da47dde8d711adf35ef70cc37422476060a2e652db37aaed7536d",
    "v1_manifest": "0ec63c32cf8fbe33a85bed16d20a94aaeb7d2ee9a5906670819e91d3671e702a",
    "model_features": "1e4ebb1942dc066eb1164dc82e7e0412fe10d433e57aa5b8b8ab3b71822344ac",
    "label_plan": "426c40e5f0bc1a819e291abcc66c7f35eae6b9c5015634ddf8c42878c6afbc42",
    "formal_scoring": "ed83264188655939cb1289d75f480174be3bdcc50e7ed2a9daf0731a48a73ed2",
    "fold_plan": "3c9514e7fe10b36a775cd8c9bfd16641d493cc8a64209319780326ba0f9fbb32",
    "bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
}


class Stage002Error(RuntimeError):
    pass


def _json_default(value: object) -> object:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"not_json_serializable:{type(value).__name__}")


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _frame_sha256(frame: pd.DataFrame) -> str:
    ordered = frame.copy()
    for column in ordered.columns:
        if pd.api.types.is_datetime64_any_dtype(ordered[column]):
            ordered[column] = ordered[column].dt.strftime("%Y-%m-%dT%H:%M:%S")
    payload = ordered.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return _sha256_bytes(payload)


def _seal_expected_payload(
    *,
    test_eval_date: pd.Timestamp,
    model_hashes: Mapping[str, str],
    predictions: pd.DataFrame,
    selection: Mapping[str, object],
    test_label_rows_read_before_seal: int,
) -> dict[str, object]:
    return {
        "stage": STAGE,
        "test_eval_date": pd.Timestamp(test_eval_date).date().isoformat(),
        "model_hashes": dict(sorted(model_hashes.items())),
        "predictions_sha256": _frame_sha256(predictions),
        "selection_sha256": _sha256_bytes(_canonical_json_bytes(dict(selection))),
        "test_label_rows_read_before_seal": int(
            test_label_rows_read_before_seal
        ),
    }


def write_pre_effect_seal(
    seal_dir: Path,
    *,
    test_eval_date: pd.Timestamp,
    model_hashes: Mapping[str, str],
    predictions: pd.DataFrame,
    selection: Mapping[str, object],
    test_label_rows_read_before_seal: int,
) -> Path:
    if test_label_rows_read_before_seal != 0:
        raise Stage002Error("test_label_read_before_seal")
    directory = Path(seal_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{pd.Timestamp(test_eval_date):%Y-%m-%d}.json"
    if target.exists():
        raise Stage002Error(f"pre_effect_seal_exists:{target}")
    payload = _seal_expected_payload(
        test_eval_date=test_eval_date,
        model_hashes=model_hashes,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=test_label_rows_read_before_seal,
    )
    with target.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return target


def verify_pre_effect_seal(
    seal_path: Path,
    *,
    model_hashes: Mapping[str, str],
    predictions: pd.DataFrame,
    selection: Mapping[str, object],
) -> dict[str, object]:
    path = Path(seal_path)
    if not path.is_file():
        raise Stage002Error("effect_seal_missing")
    actual = json.loads(path.read_text(encoding="utf-8"))
    expected = _seal_expected_payload(
        test_eval_date=pd.Timestamp(actual["test_eval_date"]),
        model_hashes=model_hashes,
        predictions=predictions,
        selection=selection,
        test_label_rows_read_before_seal=0,
    )
    if actual != expected:
        raise Stage002Error("pre_effect_seal_mismatch")
    return actual


class PhaseGatedLabelStore:
    def __init__(
        self,
        label_plan: pd.DataFrame,
        contract_prices: pd.DataFrame,
    ) -> None:
        required = {
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
        }
        if not required.issubset(label_plan.columns):
            raise Stage002Error("label_plan_store_columns_missing")
        if set(contract_prices.columns) != {
            "date",
            "contract_vt_symbol",
            "close_price",
        }:
            raise Stage002Error("contract_price_store_columns_invalid")
        self._plan = label_plan[list(required)].copy()
        for column in ("query_date", "entry_date", "label_end"):
            self._plan[column] = pd.to_datetime(
                self._plan[column], errors="raise"
            ).dt.normalize()
        for column in ("product_vt_symbol", "main_contract_vt"):
            self._plan[column] = self._plan[column].astype(str)
        if self._plan.duplicated(["query_date", "product_vt_symbol"]).any():
            raise Stage002Error("label_plan_store_duplicate")
        self._price_index = ContractPriceIndex(contract_prices)
        self._opened = pd.DataFrame(
            columns=[
                "query_date",
                "product_vt_symbol",
                "main_contract_vt",
                "entry_date",
                "label_end",
                "forward_log_return",
                "relevance",
            ]
        )
        self._opened_keys: set[tuple[str, str]] = set()
        self._relevance_ready_qids: set[str] = set()
        self._training_keys_opened: set[tuple[str, str]] = set()
        self._effect_keys_opened: set[tuple[str, str]] = set()
        self._effect_rows_by_date: dict[str, int] = {}

    @staticmethod
    def _key(query_date: pd.Timestamp, product: str) -> tuple[str, str]:
        return (pd.Timestamp(query_date).date().isoformat(), str(product))

    def _open_new_plan_rows(self, planned: pd.DataFrame) -> None:
        missing_mask = [
            self._key(row.query_date, row.product_vt_symbol)
            not in self._opened_keys
            for row in planned.itertuples(index=False)
        ]
        missing_plan = planned.loc[missing_mask].copy()
        if missing_plan.empty:
            return
        opened, _ = generate_label_values(missing_plan, self._price_index)
        opened["relevance"] = pd.Series(pd.NA, index=opened.index, dtype="Int64")
        self._opened = (
            opened.copy()
            if self._opened.empty
            else pd.concat([self._opened, opened], ignore_index=True)
        )
        for row in opened[["query_date", "product_vt_symbol"]].itertuples(
            index=False
        ):
            self._opened_keys.add(self._key(row.query_date, row.product_vt_symbol))

    def _materialize_relevance(self, qids: Sequence[pd.Timestamp]) -> None:
        qid_keys = {pd.Timestamp(qid).date().isoformat() for qid in qids}
        pending = sorted(qid_keys.difference(self._relevance_ready_qids))
        if not pending:
            return
        pending_dates = pd.to_datetime(pending)
        pending_plan = self._plan[
            self._plan["query_date"].isin(pending_dates)
        ].copy()
        self._open_new_plan_rows(pending_plan)
        for qid in pending_dates:
            qid_rows = self._opened[self._opened["query_date"].eq(qid)].copy()
            expected_count = int(self._plan["query_date"].eq(qid).sum())
            if len(qid_rows) != expected_count:
                raise Stage002Error(f"training_qid_not_fully_opened:{qid.date()}")
            ranked = add_cross_sectional_relevance(qid_rows)
            relevance_by_product = ranked.set_index("product_vt_symbol")[
                "relevance"
            ]
            mask = self._opened["query_date"].eq(qid)
            self._opened.loc[mask, "relevance"] = (
                self._opened.loc[mask, "product_vt_symbol"]
                .map(relevance_by_product)
                .astype("Int64")
            )
            self._relevance_ready_qids.add(qid.date().isoformat())

    def open_training_labels(self, test_eval_date: pd.Timestamp) -> pd.DataFrame:
        test_date = pd.Timestamp(test_eval_date).normalize()
        mature_plan = self._plan[self._plan["label_end"].lt(test_date)].copy()
        mature_qids = sorted(mature_plan["query_date"].unique())
        self._materialize_relevance(mature_qids)
        opened = self._opened[
            self._opened["query_date"].isin(mature_qids)
        ].copy()
        if len(opened) != len(mature_plan) or opened["relevance"].isna().any():
            raise Stage002Error("mature_training_labels_incomplete")
        for row in opened[["query_date", "product_vt_symbol"]].itertuples(
            index=False
        ):
            self._training_keys_opened.add(
                self._key(row.query_date, row.product_vt_symbol)
            )
        return opened

    def label_rows_opened_for(self, test_eval_date: pd.Timestamp) -> int:
        key = pd.Timestamp(test_eval_date).date().isoformat()
        return sum(1 for query_date, _ in self._opened_keys if query_date == key)

    def open_effect_labels(
        self,
        test_eval_date: pd.Timestamp,
        products: Sequence[str],
        *,
        seal_path: Path,
        model_hashes: Mapping[str, str],
        predictions: pd.DataFrame,
        selection: Mapping[str, object],
    ) -> pd.DataFrame:
        verify_pre_effect_seal(
            seal_path,
            model_hashes=model_hashes,
            predictions=predictions,
            selection=selection,
        )
        test_date = pd.Timestamp(test_eval_date).normalize()
        key = test_date.date().isoformat()
        if self._effect_rows_by_date.get(key, 0):
            raise Stage002Error(f"effect_labels_already_opened:{key}")
        product_list = [str(product) for product in products]
        if len(product_list) != len(set(product_list)):
            raise Stage002Error("effect_product_duplicate")
        selected_plan = self._plan[
            self._plan["query_date"].eq(test_date)
            & self._plan["product_vt_symbol"].isin(product_list)
        ].copy()
        if len(selected_plan) != len(product_list) or set(
            selected_plan["product_vt_symbol"]
        ) != set(product_list):
            raise Stage002Error(f"effect_label_missing:{key}")
        self._open_new_plan_rows(selected_plan)
        opened = self._opened[
            self._opened["query_date"].eq(test_date)
            & self._opened["product_vt_symbol"].isin(product_list)
        ].copy()
        self._effect_rows_by_date[key] = int(len(opened))
        for row in opened[["query_date", "product_vt_symbol"]].itertuples(
            index=False
        ):
            self._effect_keys_opened.add(
                self._key(row.query_date, row.product_vt_symbol)
            )
        return opened

    def opened_labels(self) -> pd.DataFrame:
        return self._opened.sort_values(
            ["query_date", "product_vt_symbol"], kind="mergesort"
        ).reset_index(drop=True)

    def audit(self) -> dict[str, int]:
        return {
            "label_plan_rows": int(len(self._plan)),
            "unique_label_rows_opened": int(len(self._opened_keys)),
            "close_value_reads": int(self._price_index.lookup_count),
            "future_return_calculations": int(len(self._opened_keys)),
            "opened_training_qids": int(len(self._relevance_ready_qids)),
            "unique_training_label_rows_opened": len(self._training_keys_opened),
            "effect_label_rows_opened": len(self._effect_keys_opened),
        }


def assess_technical_gates(observed: Mapping[str, object]) -> dict[str, object]:
    gates = {
        "identity_and_authorization": bool(observed.get("input_identity_stable"))
        and bool(observed.get("authorization_valid")),
        "label_contract": int(observed.get("label_plan_rows", -1)) == 52_484
        and int(observed.get("opened_label_rows", -1)) == 52_427
        and int(observed.get("opened_training_qids", -1)) == 1_045
        and int(observed.get("close_value_reads", -1)) == 104_854
        and int(observed.get("future_return_calculations", -1)) == 52_427
        and int(observed.get("relevance_level_failure_count", -1)) == 0,
        "fold_and_estimator_contract": int(observed.get("fold_count", -1)) == 37
        and int(observed.get("fit_call_count", -1)) == 74
        and int(observed.get("future_train_qid_count", -1)) == 0
        and bool(observed.get("estimator_audit_passed")),
        "determinism_and_model_shape": float(
            observed.get("repeat_prediction_max_abs_difference", np.inf)
        )
        <= 1e-12
        and int(observed.get("repeat_model_hash_mismatch_count", -1)) == 0
        and int(observed.get("constant_prediction_fold_count", -1)) == 0
        and int(observed.get("zero_split_fold_count", -1)) == 0,
        "pre_effect_state_machine": int(observed.get("seal_count", -1)) == 37
        and int(observed.get("test_label_rows_read_before_seal", -1)) == 0
        and int(observed.get("effect_fold_count", -1)) == 36
        and int(observed.get("effect_label_rows_opened", -1)) == 72
        and int(observed.get("inference_fold_count", -1)) == 1,
        "isolated_side_effects": int(observed.get("strategy_backtest_runs", -1))
        == 0
        and int(observed.get("sealed_holdout_rows", -1)) == 0
        and int(observed.get("ctp_connection_count", -1)) == 0
        and int(observed.get("order_api_called_count", -1)) == 0
        and int(observed.get("production_files_written", -1)) == 0,
    }
    return {"passed": all(gates.values()), "gates": gates}


def create_execution_event(
    event_path: Path,
    *,
    authorization_sha256: str,
    nonce: str,
) -> None:
    path = Path(event_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "status": "started",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "authorization_sha256": authorization_sha256,
        "nonce": nonce,
    }
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise Stage002Error(f"execution_event_exists:{path}") from error


def _complete_execution_event(
    event_path: Path,
    *,
    decision: str,
    final_manifest_sha256: str,
) -> None:
    path = Path(event_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(
        {
            "status": "completed",
            "completed_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "decision": decision,
            "final_manifest_sha256": final_manifest_sha256,
        }
    )
    temporary = path.with_name(f".{path.name}.tmp.{uuid.uuid4().hex}")
    temporary.write_bytes(_canonical_json_bytes(payload))
    os.replace(temporary, path)


def _implementation_paths() -> dict[str, Path]:
    return {
        "core": LINE_DIR / "tools/daily_ranker_development.py",
        "runner": Path(__file__),
        "core_tests": LINE_DIR / "tests/test_daily_ranker_development.py",
        "runner_tests": (
            LINE_DIR / "tests/test_stage002_daily_ranker_development_oos.py"
        ),
        "preregistration": PREREGISTRATION_PATH,
    }


def verify_authorization(
    authorization_path: Path,
    input_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    path = Path(authorization_path)
    if not path.is_file():
        raise Stage002Error(f"authorization_missing:{path}")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if (
        receipt.get("line_id") != LINE_ID
        or receipt.get("stage") != STAGE
        or receipt.get("authorized") is not True
        or not receipt.get("nonce")
    ):
        raise Stage002Error("authorization_header_invalid")
    expected_inputs = {
        name: identity["sha256"] for name, identity in input_identities.items()
    }
    if receipt.get("input_sha256") != expected_inputs:
        raise Stage002Error("authorization_input_binding_invalid")
    actual_implementation = {
        name: upstream_stage001.sha256_file(path)
        for name, path in _implementation_paths().items()
    }
    if receipt.get("implementation_sha256") != actual_implementation:
        raise Stage002Error("authorization_implementation_binding_invalid")
    runtime = receipt.get("runtime", {})
    if runtime != {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "xgboost": xgboost.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }:
        raise Stage002Error("authorization_runtime_binding_invalid")
    if receipt.get("model_params") != MODEL_PARAMS:
        raise Stage002Error("authorization_model_params_invalid")
    return receipt


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(_canonical_json_bytes(value))


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    if path.suffix == ".gz":
        frame.to_csv(
            path,
            index=False,
            encoding="utf-8",
            compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
        )
    else:
        frame.to_csv(path, index=False, encoding="utf-8")


def _build_manifest(directory: Path, input_identities: Mapping[str, object]) -> None:
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    manifest = {
        "artifacts": {
            str(path.relative_to(directory)): {
                "sha256": upstream_stage001.sha256_file(path),
                "size": int(path.stat().st_size),
            }
            for path in files
        },
        "input_identities": dict(input_identities),
    }
    _write_json(directory / "artifact_manifest.json", manifest)


def verify_published_bundle(
    final_dir: Path,
    *,
    verify_inputs: bool = False,
) -> dict[str, object]:
    directory = Path(final_dir).resolve()
    manifest_path = directory / "artifact_manifest.json"
    if not manifest_path.is_file():
        return {"verified": False, "errors": ["manifest_missing"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    expected = set(manifest.get("artifacts", {})) | {"artifact_manifest.json"}
    actual = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file()
    }
    for name in sorted(actual - expected):
        errors.append(f"unmanifested_artifact:{name}")
    for name in sorted(expected - actual):
        errors.append(f"artifact_missing:{name}")
    for name, identity in manifest.get("artifacts", {}).items():
        path = directory / name
        if not path.is_file():
            continue
        if path.stat().st_size != identity.get("size"):
            errors.append(f"artifact_size_mismatch:{name}")
        if upstream_stage001.sha256_file(path) != identity.get("sha256"):
            errors.append(f"artifact_sha256_mismatch:{name}")
    if verify_inputs:
        for name, identity in manifest.get("input_identities", {}).items():
            path = Path(str(identity.get("path", "")))
            if not path.is_file():
                errors.append(f"input_missing:{name}")
                continue
            stat = path.stat()
            if stat.st_size != identity.get("size"):
                errors.append(f"input_size_mismatch:{name}")
            if stat.st_mtime_ns != identity.get("mtime_ns"):
                errors.append(f"input_mtime_mismatch:{name}")
            if upstream_stage001.sha256_file(path) != identity.get("sha256"):
                errors.append(f"input_sha256_mismatch:{name}")
    return {
        "verified": not errors,
        "errors": errors,
        "artifact_count": len(manifest.get("artifacts", {})),
        "input_count": len(manifest.get("input_identities", {})),
    }


def _atomic_publish(staging: Path, final_dir: Path) -> None:
    if final_dir.exists():
        raise Stage002Error(f"final_output_exists:{final_dir}")
    os.replace(staging, final_dir)


def _load_inputs(input_paths: Mapping[str, Path]) -> dict[str, object]:
    v2_summary = json.loads(Path(input_paths["v2_summary"]).read_text("utf-8"))
    if (
        v2_summary.get("decision")
        != "stage001_daily_ranker_v2_contract_pass_allow_stage002_preregistration_only"
        or v2_summary.get("all_gates_passed") is not True
    ):
        raise Stage002Error("v2_stage001_not_passed")
    v2_verify = upstream_stage001.verify_published_bundle(
        V2_STAGE001_DIR, verify_inputs=True
    )
    v1_verify = upstream_stage001.verify_published_bundle(
        V1_STAGE001_DIR, verify_inputs=True
    )
    if not v2_verify["verified"] or not v1_verify["verified"]:
        raise Stage002Error("upstream_bundle_verification_failed")
    return {
        "v2_summary": v2_summary,
        "model_features": pd.read_csv(input_paths["model_features"]),
        "label_plan": pd.read_csv(input_paths["label_plan"]),
        "formal_scoring": pd.read_csv(input_paths["formal_scoring"]),
        "fold_plan": pd.read_csv(input_paths["fold_plan"]),
        "bars": pd.read_csv(
            input_paths["bars"],
            encoding="utf-8-sig",
            usecols=[
                "datetime",
                "symbol",
                "exchange",
                "interval",
                "close_price",
            ],
        ),
        "upstream_verification": {"v1": v1_verify, "v2": v2_verify},
    }


def _contract_prices(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars.copy()
    frame = frame[frame["interval"].astype(str).eq("d")].copy()
    frame["date"] = pd.to_datetime(frame["datetime"], errors="raise").dt.normalize()
    frame["contract_vt_symbol"] = (
        frame["symbol"].astype(str).str.strip()
        + "."
        + frame["exchange"].astype(str).str.strip()
    )
    result = frame[["date", "contract_vt_symbol", "close_price"]].copy()
    if result.duplicated(["date", "contract_vt_symbol"]).any():
        raise Stage002Error("duplicate_contract_price")
    return result


def _decision(technical_pass: bool, effect_pass: bool) -> str:
    if not technical_pass:
        return TECHNICAL_FAIL_DECISION
    return PASS_DECISION if effect_pass else EFFECT_FAIL_DECISION


def _report(summary: Mapping[str, object]) -> str:
    technical = summary.get("technical", {})
    effect = summary.get("effect", {})
    return (
        "# Stage002 日级XGBRanker Development OOS\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 技术门：{'通过' if technical.get('passed') else '失败'}\n"
        f"- 效果门：{'通过' if effect.get('passed') else '失败或未开放'}\n"
        f"- folds/fits：{summary.get('fold_count', 0)}/"
        f"{summary.get('fit_call_count', 0)}\n"
        f"- replacement：{summary.get('effect_metrics', {}).get('replacement_count', 0)}\n"
        f"- sum(C-A)：{summary.get('effect_metrics', {}).get('sum_return_delta', 'NA')}\n"
        f"- drawdown improvement："
        f"{summary.get('effect_metrics', {}).get('drawdown_improvement', 'NA')}\n"
        "- strategy backtest、holdout、CTP、订单和生产写入：全部为0\n"
    )


def _write_progress_state(
    staging: Path,
    *,
    phase: str,
    current_test_date: pd.Timestamp | None,
    last_completed_fold: pd.Timestamp | None,
    label_store: PhaseGatedLabelStore,
    effect_rows: int,
    persist_opened_labels: bool,
) -> None:
    audit = label_store.audit()
    payload = {
        "phase": phase,
        "current_test_date": (
            pd.Timestamp(current_test_date).date().isoformat()
            if current_test_date is not None
            else None
        ),
        "last_completed_fold": (
            pd.Timestamp(last_completed_fold).date().isoformat()
            if last_completed_fold is not None
            else None
        ),
        "seal_count": len(list((staging / "pre_effect_seals").glob("*.json"))),
        "model_file_count": len(list((staging / "models").glob("*.ubj"))),
        "effect_month_rows_persisted": int(effect_rows),
        "label_access_audit": audit,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    _write_json(staging / "run_progress.json", payload)
    _write_json(staging / "label_access_audit.json", audit)
    if persist_opened_labels:
        _write_csv(
            label_store.opened_labels(),
            staging / "opened_label_values.csv.gz",
        )


def _write_partial_frames(
    staging: Path,
    *,
    prediction_frames: Sequence[pd.DataFrame],
    selections: Sequence[Mapping[str, object]],
    fold_audits: Sequence[Mapping[str, object]],
    effect_rows: Sequence[Mapping[str, object]],
) -> None:
    if prediction_frames:
        _write_csv(
            pd.concat(prediction_frames, ignore_index=True),
            staging / "predictions.csv.gz",
        )
    if selections:
        _write_csv(pd.DataFrame(selections), staging / "monthly_selections.csv")
    if fold_audits:
        _write_csv(pd.DataFrame(fold_audits), staging / "fold_audit.csv")
    if effect_rows:
        _write_csv(pd.DataFrame(effect_rows), staging / "effect_monthly.csv")


def _execute_stage002(
    staging: Path,
    *,
    inputs: Mapping[str, object],
    input_identities: Mapping[str, Mapping[str, object]],
    authorization: Mapping[str, object],
) -> dict[str, object]:
    model_features = inputs["model_features"].copy()
    label_plan = inputs["label_plan"].copy()
    scoring = inputs["formal_scoring"].copy()
    folds = inputs["fold_plan"].copy()
    for frame, columns in (
        (model_features, ["query_date"]),
        (label_plan, ["query_date", "entry_date", "label_end"]),
        (scoring, ["test_eval_date"]),
        (folds, ["test_eval_date", "maximum_train_label_end"]),
    ):
        for column in columns:
            frame[column] = pd.to_datetime(frame[column], errors="raise").dt.normalize()
    prices = _contract_prices(inputs["bars"])
    label_store = PhaseGatedLabelStore(label_plan, prices)
    feature_columns = list(upstream_contract.MODEL_FEATURES)
    estimator_audit = build_estimator_audit(XGBRanker, MODEL_PARAMS)
    if not estimator_audit["passed"]:
        raise Stage002Error("estimator_audit_failed")

    staging.mkdir(parents=True)
    models_dir = staging / "models"
    seals_dir = staging / "pre_effect_seals"
    models_dir.mkdir()
    seals_dir.mkdir()
    prediction_frames: list[pd.DataFrame] = []
    selections: list[dict[str, object]] = []
    fold_audits: list[dict[str, object]] = []
    effect_rows: list[dict[str, object]] = []
    fit_call_count = 0
    last_completed_fold: pd.Timestamp | None = None
    _write_progress_state(
        staging,
        phase="initialized",
        current_test_date=None,
        last_completed_fold=None,
        label_store=label_store,
        effect_rows=0,
        persist_opened_labels=False,
    )

    for fold in folds.sort_values("test_eval_date", kind="mergesort").itertuples(
        index=False
    ):
        test_date = pd.Timestamp(fold.test_eval_date).normalize()
        _write_progress_state(
            staging,
            phase="fold_started",
            current_test_date=test_date,
            last_completed_fold=last_completed_fold,
            label_store=label_store,
            effect_rows=len(effect_rows),
            persist_opened_labels=False,
        )
        training_labels = label_store.open_training_labels(test_date)
        _write_progress_state(
            staging,
            phase="training_labels_opened",
            current_test_date=test_date,
            last_completed_fold=last_completed_fold,
            label_store=label_store,
            effect_rows=len(effect_rows),
            persist_opened_labels=True,
        )
        train_qids = int(training_labels["query_date"].nunique())
        if train_qids != int(fold.train_qid_count):
            raise Stage002Error(
                f"fold_train_qid_count_mismatch:{test_date.date()}:{train_qids}:"
                f"{fold.train_qid_count}"
            )
        train = model_features.merge(
            training_labels[
                [
                    "query_date",
                    "product_vt_symbol",
                    "main_contract_vt",
                    "label_end",
                    "relevance",
                ]
            ],
            on=["query_date", "product_vt_symbol", "main_contract_vt"],
            how="inner",
            validate="one_to_one",
        )
        if len(train) != len(training_labels):
            raise Stage002Error(f"training_feature_join_mismatch:{test_date.date()}")
        if train["label_end"].ge(test_date).any():
            raise Stage002Error(f"future_training_label:{test_date.date()}")
        _, train_x, train_y, train_qid = build_ranker_arrays(
            train, feature_columns
        )

        test_scoring = scoring[scoring["test_eval_date"].eq(test_date)].copy()
        test_features = test_scoring.merge(
            model_features,
            left_on=["test_eval_date", "product_vt_symbol"],
            right_on=["query_date", "product_vt_symbol"],
            how="inner",
            validate="one_to_one",
        ).sort_values("product_vt_symbol", kind="mergesort")
        if len(test_features) != len(test_scoring):
            raise Stage002Error(f"test_feature_join_mismatch:{test_date.date()}")
        predict_x = test_features[feature_columns].apply(
            pd.to_numeric, errors="coerce"
        ).astype(float)
        fitted = fit_repeated_ranker(
            train_x,
            train_y,
            train_qid,
            predict_x,
            params=MODEL_PARAMS,
            tolerance=1e-12,
            ranker_factory=XGBRanker,
        )
        fit_call_count += 2
        date_name = f"{test_date:%Y-%m-%d}"
        primary_path = models_dir / f"{date_name}_primary.ubj"
        repeat_path = models_dir / f"{date_name}_repeat.ubj"
        primary_path.write_bytes(fitted["primary_model_raw"])
        repeat_path.write_bytes(fitted["repeat_model_raw"])
        predicted = test_features[
            ["test_eval_date", "product_vt_symbol", "role"]
        ].copy()
        predicted["xgb_score"] = fitted["predictions"]
        predicted["train_qid_count"] = train_qids
        predicted["train_row_count"] = int(len(train))
        selection = select_one_slot(predicted)
        selection["effect_evaluable"] = bool(fold.effect_evaluable)
        selection["inference_only"] = bool(fold.inference_only)
        selection["train_qid_count"] = train_qids
        model_hashes = {
            "primary": str(fitted["primary_model_sha256"]),
            "repeat": str(fitted["repeat_model_sha256"]),
        }
        before_seal = label_store.label_rows_opened_for(test_date)
        seal_path = write_pre_effect_seal(
            seals_dir,
            test_eval_date=test_date,
            model_hashes=model_hashes,
            predictions=predicted,
            selection=selection,
            test_label_rows_read_before_seal=before_seal,
        )
        _write_progress_state(
            staging,
            phase="pre_effect_sealed",
            current_test_date=test_date,
            last_completed_fold=last_completed_fold,
            label_store=label_store,
            effect_rows=len(effect_rows),
            persist_opened_labels=False,
        )
        if bool(fold.effect_evaluable):
            opened = label_store.open_effect_labels(
                test_date,
                [selection["anchor_product"], selection["challenger_product"]],
                seal_path=seal_path,
                model_hashes=model_hashes,
                predictions=predicted,
                selection=selection,
            ).set_index("product_vt_symbol")
            _write_progress_state(
                staging,
                phase="effect_labels_opened",
                current_test_date=test_date,
                last_completed_fold=last_completed_fold,
                label_store=label_store,
                effect_rows=len(effect_rows),
                persist_opened_labels=True,
            )
            a_return = float(
                opened.loc[selection["anchor_product"], "forward_log_return"]
            )
            challenger_return = float(
                opened.loc[
                    selection["challenger_product"], "forward_log_return"
                ]
            )
            c_return = challenger_return if selection["replaced"] else a_return
            effect_rows.append(
                {
                    "test_eval_date": test_date,
                    "anchor_product": selection["anchor_product"],
                    "challenger_product": selection["challenger_product"],
                    "selected_product": selection["selected_product"],
                    "replaced": selection["replaced"],
                    "a_return": a_return,
                    "challenger_return": challenger_return,
                    "c_return": c_return,
                    "return_delta": c_return - a_return,
                }
            )
        prediction_frames.append(predicted)
        selections.append(selection)
        fold_audits.append(
            {
                "test_eval_date": test_date,
                "train_qid_count": train_qids,
                "train_row_count": int(len(train)),
                "maximum_train_label_end": train["label_end"].max(),
                "test_row_count": int(len(predicted)),
                "effect_evaluable": bool(fold.effect_evaluable),
                "inference_only": bool(fold.inference_only),
                "primary_model_sha256": fitted["primary_model_sha256"],
                "repeat_model_sha256": fitted["repeat_model_sha256"],
                "prediction_repeat_max_abs_difference": fitted[
                    "prediction_repeat_max_abs_difference"
                ],
                "unique_prediction_count": fitted["unique_prediction_count"],
                "split_count": fitted["split_count"],
                "pre_effect_seal_sha256": upstream_stage001.sha256_file(seal_path),
                "test_label_rows_read_before_seal": before_seal,
            }
        )
        last_completed_fold = test_date
        _write_partial_frames(
            staging,
            prediction_frames=prediction_frames,
            selections=selections,
            fold_audits=fold_audits,
            effect_rows=effect_rows,
        )
        _write_progress_state(
            staging,
            phase="fold_completed",
            current_test_date=test_date,
            last_completed_fold=last_completed_fold,
            label_store=label_store,
            effect_rows=len(effect_rows),
            persist_opened_labels=True,
        )

    predictions = pd.concat(prediction_frames, ignore_index=True)
    monthly_selections = pd.DataFrame(selections).sort_values(
        "test_eval_date", kind="mergesort"
    )
    fold_audit = pd.DataFrame(fold_audits).sort_values(
        "test_eval_date", kind="mergesort"
    )
    effect_monthly = pd.DataFrame(effect_rows).sort_values(
        "test_eval_date", kind="mergesort"
    )
    labels = label_store.opened_labels()
    label_access = label_store.audit()
    training_labels_with_relevance = labels[labels["relevance"].notna()].copy()
    relevance_failures = int(
        training_labels_with_relevance.groupby("query_date", sort=False)[
            "relevance"
        ]
        .nunique()
        .lt(2)
        .sum()
    )
    observed = {
        "input_identity_stable": True,
        "authorization_valid": True,
        "label_plan_rows": int(label_access["label_plan_rows"]),
        "opened_label_rows": int(label_access["unique_label_rows_opened"]),
        "opened_training_qids": int(label_access["opened_training_qids"]),
        "close_value_reads": int(label_access["close_value_reads"]),
        "future_return_calculations": int(
            label_access["future_return_calculations"]
        ),
        "relevance_level_failure_count": relevance_failures,
        "fold_count": int(len(fold_audit)),
        "fit_call_count": int(fit_call_count),
        "future_train_qid_count": int(
            pd.to_datetime(fold_audit["maximum_train_label_end"])
            .ge(pd.to_datetime(fold_audit["test_eval_date"]))
            .sum()
        ),
        "estimator_audit_passed": bool(estimator_audit["passed"]),
        "repeat_prediction_max_abs_difference": float(
            fold_audit["prediction_repeat_max_abs_difference"].max()
        ),
        "repeat_model_hash_mismatch_count": int(
            fold_audit["primary_model_sha256"]
            .ne(fold_audit["repeat_model_sha256"])
            .sum()
        ),
        "constant_prediction_fold_count": int(
            fold_audit["unique_prediction_count"].lt(2).sum()
        ),
        "zero_split_fold_count": int(fold_audit["split_count"].lt(1).sum()),
        "seal_count": len(list(seals_dir.glob("*.json"))),
        "test_label_rows_read_before_seal": int(
            fold_audit["test_label_rows_read_before_seal"].sum()
        ),
        "effect_fold_count": int(fold_audit["effect_evaluable"].astype(bool).sum()),
        "effect_label_rows_opened": int(
            label_access["effect_label_rows_opened"]
        ),
        "inference_fold_count": int(
            fold_audit["inference_only"].astype(bool).sum()
        ),
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
    }
    technical = assess_technical_gates(observed)
    if technical["passed"]:
        effect_metrics = compute_effect_metrics(effect_monthly)
        effect = assess_effect_gates(effect_metrics)
    else:
        effect_metrics = {}
        effect = {"passed": False, "gates": {}, "not_opened": True}
    decision = _decision(bool(technical["passed"]), bool(effect["passed"]))
    summary = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision,
        "all_gates_passed": bool(technical["passed"] and effect["passed"]),
        "technical": technical,
        "effect": effect,
        "effect_metrics": effect_metrics,
        **observed,
        "label_access_audit": label_access,
        "estimator_audit": estimator_audit,
        "model_params": MODEL_PARAMS,
        "authorization_nonce": authorization["nonce"],
        "development_only": True,
        "sealed_holdout_used": False,
        "independent_reviewer_required": True,
    }
    _write_csv(labels, staging / "opened_label_values.csv.gz")
    _write_csv(predictions, staging / "predictions.csv.gz")
    _write_csv(monthly_selections, staging / "monthly_selections.csv")
    _write_csv(fold_audit, staging / "fold_audit.csv")
    _write_csv(effect_monthly, staging / "effect_monthly.csv")
    _write_json(staging / "summary.json", summary)
    _write_json(staging / "input_identities.json", input_identities)
    _write_json(staging / "authorization_receipt.json", authorization)
    (staging / "report.md").write_text(_report(summary), encoding="utf-8")
    return summary


def _publish_failure(
    staging: Path,
    *,
    error: Exception,
    input_identities: Mapping[str, object],
    authorization: Mapping[str, object],
) -> dict[str, object]:
    staging.mkdir(parents=True, exist_ok=True)
    progress_path = staging / "run_progress.json"
    progress = (
        json.loads(progress_path.read_text(encoding="utf-8"))
        if progress_path.is_file()
        else {}
    )
    label_audit_path = staging / "label_access_audit.json"
    label_audit = (
        json.loads(label_audit_path.read_text(encoding="utf-8"))
        if label_audit_path.is_file()
        else {}
    )
    effect_rows_opened = int(label_audit.get("effect_label_rows_opened", 0))
    seal_count = len(list((staging / "pre_effect_seals").glob("*.json")))
    model_file_count = len(list((staging / "models").glob("*.ubj")))
    summary = {
        "line_id": LINE_ID,
        "stage": STAGE,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": TECHNICAL_FAIL_DECISION,
        "all_gates_passed": False,
        "technical": {"passed": False, "gates": {}},
        "effect": {
            "passed": False,
            "not_opened": effect_rows_opened == 0,
            "partial_effect_label_rows_opened": effect_rows_opened,
            "gates": {},
        },
        "error_type": type(error).__name__,
        "error": str(error),
        "failure_phase": progress.get("phase", "before_progress_initialization"),
        "current_test_date": progress.get("current_test_date"),
        "last_completed_fold": progress.get("last_completed_fold"),
        "seal_count": seal_count,
        "model_file_count": model_file_count,
        "label_access_audit": label_audit,
        "partial_artifacts_preserved": True,
        "strategy_backtest_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
        "authorization_nonce": authorization.get("nonce"),
        "independent_reviewer_required": True,
    }
    _write_json(staging / "summary.json", summary)
    _write_json(staging / "input_identities.json", input_identities)
    _write_json(staging / "authorization_receipt.json", authorization)
    (staging / "report.md").write_text(_report(summary), encoding="utf-8")
    return summary


def run_stage002(
    *,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    authorization_path: Path = DEFAULT_AUTHORIZATION_PATH,
    execution_event_path: Path = DEFAULT_EXECUTION_EVENT_PATH,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
) -> dict[str, object]:
    final_path = upstream_stage001.assert_line_local_output(line_dir, output_dir)
    event_path = upstream_stage001.assert_line_local_output(
        line_dir, execution_event_path
    )
    if final_path.exists():
        raise Stage002Error(f"final_output_exists:{final_path}")
    input_identities_before = upstream_stage001.collect_input_identities(
        input_paths, expected_sha256
    )
    authorization = verify_authorization(
        authorization_path, input_identities_before
    )
    authorization_sha = upstream_stage001.sha256_file(authorization_path)
    create_execution_event(
        event_path,
        authorization_sha256=authorization_sha,
        nonce=str(authorization["nonce"]),
    )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    staging = final_path.parent / f".stage002.tmp.{uuid.uuid4().hex}"
    try:
        inputs = _load_inputs(input_paths)
        summary = _execute_stage002(
            staging,
            inputs=inputs,
            input_identities=input_identities_before,
            authorization=authorization,
        )
        input_identities_after = upstream_stage001.collect_input_identities(
            input_paths, expected_sha256
        )
        if input_identities_before != input_identities_after:
            raise Stage002Error("input_identity_changed_during_run")
        summary["input_identities_before"] = input_identities_before
        summary["input_identities_after"] = input_identities_after
        _write_json(staging / "summary.json", summary)
        _build_manifest(staging, input_identities_before)
        verification = verify_published_bundle(staging)
        if not verification["verified"]:
            raise Stage002Error(
                "staging_manifest_invalid:" + ",".join(verification["errors"])
            )
        _atomic_publish(staging, final_path)
        final_verification = verify_published_bundle(
            final_path, verify_inputs=True
        )
        if not final_verification["verified"]:
            raise Stage002Error(
                "final_manifest_invalid:"
                + ",".join(final_verification["errors"])
            )
    except Exception as primary_error:
        if final_path.exists() and not staging.exists():
            os.replace(final_path, staging)
        summary = _publish_failure(
            staging,
            error=primary_error,
            input_identities=input_identities_before,
            authorization=authorization,
        )
        try:
            _build_manifest(staging, input_identities_before)
            failure_verification = verify_published_bundle(staging)
            if not failure_verification["verified"]:
                raise Stage002Error(
                    "failure_staging_manifest_invalid:"
                    + ",".join(failure_verification["errors"])
                )
            _atomic_publish(staging, final_path)
            final_verification = verify_published_bundle(
                final_path, verify_inputs=True
            )
            if not final_verification["verified"]:
                raise Stage002Error(
                    "failure_final_manifest_invalid:"
                    + ",".join(final_verification["errors"])
                )
        except Exception as terminal_error:
            _complete_execution_event(
                event_path,
                decision=TECHNICAL_FAIL_DECISION,
                final_manifest_sha256="",
            )
            raise Stage002Error(
                f"terminal_failure_bundle_error:{type(terminal_error).__name__}:"
                f"{terminal_error}"
            ) from terminal_error
    manifest_sha = upstream_stage001.sha256_file(
        final_path / "artifact_manifest.json"
    )
    _complete_execution_event(
        event_path,
        decision=str(summary["decision"]),
        final_manifest_sha256=manifest_sha,
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage002 daily XGBRanker OOS")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.verify_only:
        result = verify_published_bundle(DEFAULT_OUTPUT_DIR, verify_inputs=True)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["verified"] else 1
    try:
        summary = run_stage002()
    except (Stage002Error, DevelopmentError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, default=_json_default))
    return 0 if summary["decision"] == PASS_DECISION else 2


if __name__ == "__main__":
    raise SystemExit(main())

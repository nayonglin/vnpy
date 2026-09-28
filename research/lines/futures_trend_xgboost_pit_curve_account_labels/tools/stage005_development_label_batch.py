"""Run the frozen Stage005 development account-label campaign."""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Final, Mapping, Sequence

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import development_label_batch as batch_core  # noqa: E402
import stage004_runtime_smoke as stage004  # noqa: E402
import stage005a_runtime_identity_remediation as runtime_v2  # noqa: E402


PREDECISION_NAMES = batch_core.PREDECISION_NAMES

LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SOURCE_LINE = (
    WORKSPACE_ROOT
    / "research/lines/futures_trend_xgboost_pit_market_context_after_listing"
)
OLD_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_ai_xgboost_ensemble"
PRODUCTION_ROOT = stage004.PRODUCTION_ROOT
PRODUCTION_DATABASE = runtime_v2.FROZEN_SOURCE_DATABASE
RUNTIME_ROOT = runtime_v2.RUNTIME_ROOT
RUNTIME_DATABASE = runtime_v2.RUNTIME_DATABASE
RUNTIME_SETTING = runtime_v2.RUNTIME_SETTING
RUNTIME_LOG_DIR = runtime_v2.RUNTIME_LOG_DIR
FROZEN_MAPPING = runtime_v2.FROZEN_MAPPING
FROZEN_MINUTE_BARS = runtime_v2.FROZEN_MINUTE_BARS
FROZEN_CONTRACT_METADATA = runtime_v2.FROZEN_CONTRACT_METADATA
RUNTIME_RECEIPT = runtime_v2.RUNTIME_RECEIPT
TMP_ROOT = Path("/private/tmp/vnpy-stage005-curve-account-labels")
BASE_OUT = LINE_DIR / "artifacts/stage005_development_label_batch"
CAMPAIGN_ROOT = BASE_OUT / "campaigns"
AUTHORIZATION_CONSUMPTION = BASE_OUT / "authorization_consumption.json"
STAGE003_DIR = LINE_DIR / "artifacts/stage003_account_label_plan"
STAGE003_SUMMARY = STAGE003_DIR / "stage003_summary.json"
STAGE003_JOBS = STAGE003_DIR / "development_jobs.csv"
STAGE003_AUDIT = STAGE003_DIR / "development_eligibility_audit.csv"
STAGE003_MANIFEST = STAGE003_DIR / "artifact_manifest.json"
FULL_FEATURE_SPLIT = STAGE003_DIR / "full_feature_split.csv"
RANKED_PANEL = (
    SOURCE_LINE / "artifacts/stage001_market_context_coverage/ranked_a_panel.csv"
)
FORMAL_ELIGIBILITY = stage004.FORMAL_ELIGIBILITY
FORMAL_CURRENT = stage004.FORMAL_CURRENT
PREREGISTRATION = (
    LINE_DIR
    / "stages/20260902_1635_stage005_development_label_batch_preregistration.md"
)
STAGE004_RESULT = (
    LINE_DIR / "stages/20260902_1625_stage004_runtime_smoke_result.md"
)
STAGE004_REVIEW = LINE_DIR / "reviews/20260902_stage004_independent_review.md"
STAGE004_SMOKE_RECEIPT = (
    LINE_DIR
    / "artifacts/stage004_runtime_smoke/campaigns"
    / "campaign_20260902T153215+0800_55582/smoke_receipt.json"
)
STAGE004_RUNTIME_RECEIPT = (
    LINE_DIR / "artifacts/stage004_runtime_smoke/runtime_snapshot_receipt.json"
)
STAGE005A_CAMPAIGN = (
    LINE_DIR
    / "artifacts/stage005a_runtime_identity_remediation/campaigns"
    / "campaign_20260902T192840+0800_77391"
)
STAGE005A_SMOKE_RECEIPT = STAGE005A_CAMPAIGN / "smoke_receipt.json"
STAGE005A_SCOPE_AUDIT = STAGE005A_CAMPAIGN / "execution_scope_audit.json"
STAGE005A_POSTRUN_REVIEW = (
    LINE_DIR / "reviews/20260902_stage005a_postrun_independent_review.md"
)
STAGE005A_POSTRUN_REVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005a_postrun_review_decision.json"
)
V2_MIGRATION_PREREGISTRATION = (
    LINE_DIR
    / "stages/20260902_2012_stage005b_v2_batch_integration_preregistration.md"
)
PRERUN_BLOCK_REMEDIATION_PREREGISTRATION = (
    LINE_DIR
    / "stages/20260902_2036_stage005b_prerun_block_remediation_preregistration.md"
)
SECOND_BLOCK_REMEDIATION_PREREGISTRATION = (
    LINE_DIR
    / "stages/20260902_2101_stage005b_second_block_receipt_remediation_preregistration.md"
)
THIRD_BLOCK_REMEDIATION_PREREGISTRATION = (
    LINE_DIR
    / "stages/20260902_2119_stage005b_third_block_exact_type_remediation_preregistration.md"
)
INITIAL_PRERUN_REVIEW = (
    LINE_DIR / "reviews/20260902_stage005_prerun_independent_review.md"
)
INITIAL_PRERUN_REVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005_prerun_review_decision.json"
)
BLOCK_REREVIEW = LINE_DIR / "reviews/20260902_stage005_prerun_rereview.md"
BLOCK_REREVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005_prerun_rereview_decision.json"
)
SECOND_BLOCK_REREVIEW = (
    LINE_DIR / "reviews/20260902_stage005_prerun_second_rereview.md"
)
SECOND_BLOCK_REREVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005_prerun_second_rereview_decision.json"
)
THIRD_BLOCK_REREVIEW = (
    LINE_DIR / "reviews/20260902_stage005_prerun_third_rereview.md"
)
THIRD_BLOCK_REREVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005_prerun_third_rereview_decision.json"
)
PRERUN_REVIEW = (
    LINE_DIR / "reviews/20260902_stage005_prerun_fourth_rereview.md"
)
PRERUN_REVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005_prerun_fourth_rereview_decision.json"
)
RUN_AUTHORIZATION = LINE_DIR / "reviews/20260902_stage005_run_authorization.json"
AUTHORIZATION_SCOPE = "one_new_stage005_campaign_only"
CORE_HELPER = TOOL_DIR / "development_label_batch.py"
CORE_TEST = LINE_DIR / "tests/test_development_label_batch.py"
RUNNER_TEST = LINE_DIR / "tests/test_stage005_development_label_batch.py"
MAX_WORKERS = 2
MAX_JOB_SECONDS = 600.0
PROFILE = "stage005_curve_account_development_label"
EXPECTED_MAIN_JOBS = 266
EXPECTED_A2_JOBS = 4
EXPECTED_TOTAL_JOBS = 270
EXPECTED_DEVELOPMENT_MONTHS = 35
EXPECTED_PREDECISION_FILES = 175
EXPECTED_PRODUCTION_HEAD = stage004.EXPECTED_PRODUCTION_HEAD
EXPECTED_DATABASE_SHA256 = runtime_v2.EXPECTED_DATABASE_SHA256
EXPECTED_SETTING_SHA256 = runtime_v2.EXPECTED_SETTING_SHA256
EXPECTED_JOB_OUTPUT_FILES = {
    "summary.csv",
    "label.json",
    "curve.csv",
    "combined.csv",
    "trades.csv",
    "entry_candidates.csv",
    "entry_risk.csv",
    "trade_events.csv",
    "worker_receipt.json",
}
AA_COMPARE_FILES = {
    "label.json",
    "curve.csv",
    "combined.csv",
    "trades.csv",
    "entry_candidates.csv",
    "entry_risk.csv",
    "trade_events.csv",
}
EXPECTED_STATIC_SHA256: Final = {
    "stage003_summary": "b44e21dc5070675b23c03a26973cc76f4ad8c93d79c6add7be4fd480cd945c0a",
    "stage003_jobs": "7ee2062e9700d1c1e8800f42ce8dd0ba75470e4953e30c099c37741aed39b8f3",
    "stage003_audit": "9bb8bbe8749b69f9436ef6bbb1a9665b7c58eb332859f1468b2eb0c2ffc642ed",
    "stage003_manifest": "a1832f8d1313574296af6973c6e0aff56dc74d75310c2c85c2672a4f54465d77",
    "full_feature_split": "a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1",
    "ranked_panel": "1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2",
    "stage004_runtime_receipt": "5a0ec07374276e890815bbe3722f46524e4482fca54865e0d39f9f8945deae8b",
    "stage004_smoke_receipt": "89af0420628167796921621b47f9d893e01f675df36111b61c17a42f482a0671",
    "stage004_result": "59c561058bb50394204e3c5012e0259559ea1f4c09e7f6d382c9d468a2e36eeb",
    "stage004_review": "60a4741da6a87c18f4c92c2f8ca078c6d1c2c7e32bceedfd7f9c8649258f4a46",
    "stage004_runner": "8c8de4037e4bc64096b88a87a1a76a18a17033f2a9b16ce6c3aa3238fb1bc819",
    "runtime_core": "c651cac7d515189edbed22b107899fef5464e5179179320b341e0e1f12a055e4",
    "preregistration": "ec96369d156b40f0b0400a68bdc7f45934e628a2aba4001af85a2102ed2a68cd",
    "stage005a_runtime_receipt": "f67186f8e1603c81afeb5800e3e742287228862e61e984aac6c843a1a69bf0c2",
    "stage005a_smoke_receipt": "d373a16588f2a2ce4125982ebe5bcbaa21534b25ba02c935d9376b818ef2e053",
    "stage005a_scope_audit": "a9ffbb58520f94c0c2bbb6af530afa0fd4eb12530c90f60e0fa575d8833de3bc",
    "stage005a_postrun_review": "a97e9ca9a65bac290192f89f0a08cce192e1af1eaef492d20798c08c8cfe8511",
    "stage005a_postrun_review_decision": "631d5e8842362e421c08cd0e1209beadeaa1b7e9e69d4da5fa0161c3c290bcf8",
    "v2_migration_preregistration": "dd67ce27e3a18d582371c102e1607a34b3b524fab5b3d7daf25e71e8d2b3a148",
    "prerun_block_remediation_preregistration": "8c1250a9e447a5815c962a96dfea22e8c7f6b30aedd0ec826136a07f2582e638",
    "block_rereview": "44e889d7a15d0b738d2ce9cafddd9aab397b45d8ba46f0e125c00b48ce97c55b",
    "block_rereview_decision": "aa396094e22b71f5b6fc11ead06a4323ff42c3e65cb35af53b621b3b8b8377d0",
    "second_block_remediation_preregistration": "68c791301435f5619489ca8ed9191629e0441beb3ee16c9d85a29e1fa7756793",
    "second_block_rereview": "0a7f0acf0a9c10f83ae8c891af47a589ad4fbce4ab01ec639df7b44a76bb1a12",
    "second_block_rereview_decision": "24558271506bb7f378b007065382b9ae9135f6ebc163f4ee4de1a415286382d1",
    "third_block_remediation_preregistration": "3068aea1c40a1c5a14ed5fc478738754538da48fdea32486c21d518b59b49142",
    "third_block_rereview": "859dfad1e958db24053b0d62bd0c0add871bd9f171c9372ac4ea012489750841",
    "third_block_rereview_decision": "0ca5b5d0cb7db64668d095e734b07f9c78713884ead4b62258be0b845253e900",
}


class Stage005Error(RuntimeError):
    """Raised when the frozen Stage005 campaign must fail closed."""


def worker_command(campaign_dir: Path, job_id: str) -> list[str]:
    return [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--worker",
        str(job_id),
        "--campaign-dir",
        str(Path(campaign_dir).resolve()),
    ]


def _canonical_predecision_payloads(
    legacy: Any,
    payloads: Mapping[str, pd.DataFrame],
    eval_date: pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    return {
        name: legacy._canonical_payload(
            legacy._period_rows(payloads[name], through=eval_date)
        )
        for name in PREDECISION_NAMES
    }


def expected_predecision_signatures(
    legacy: Any,
    payloads: Mapping[str, pd.DataFrame],
    eval_date: pd.Timestamp,
) -> dict[str, str]:
    canonical = _canonical_predecision_payloads(legacy, payloads, eval_date)
    return {
        name: hashlib.sha256(
            frame.to_csv(
                index=False,
                lineterminator="\n",
                date_format="%Y-%m-%dT%H:%M:%S.%f",
            ).encode("utf-8")
        ).hexdigest()
        for name, frame in canonical.items()
    }


def persist_predecision_evidence(
    legacy: Any,
    payloads: Mapping[str, pd.DataFrame],
    eval_date: pd.Timestamp,
    output_dir: Path,
    expected_signatures: Mapping[str, str],
) -> dict[str, str]:
    canonical = _canonical_predecision_payloads(legacy, payloads, eval_date)
    observed = batch_core.write_predecision_evidence(canonical, output_dir)
    if observed != dict(expected_signatures):
        raise RuntimeError(
            f"predecision_raw_evidence_sha_mismatch:{observed}:{expected_signatures}"
        )
    return observed


def _sha256(path: Path) -> str:
    return batch_core._sha256(path)


def _stable_json(path: Path, payload: Any, *, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"append_only_json_exists:{path}")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _configure_v2_runtime() -> None:
    runtime_v2._configure_stage004()


def _v2_runtime_gate() -> dict[str, Any]:
    _configure_v2_runtime()
    return runtime_v2._runtime_receipt_gate()


def _static_paths() -> dict[str, Path]:
    return {
        "stage003_summary": STAGE003_SUMMARY,
        "stage003_jobs": STAGE003_JOBS,
        "stage003_audit": STAGE003_AUDIT,
        "stage003_manifest": STAGE003_MANIFEST,
        "full_feature_split": FULL_FEATURE_SPLIT,
        "ranked_panel": RANKED_PANEL,
        "stage004_runtime_receipt": STAGE004_RUNTIME_RECEIPT,
        "stage004_smoke_receipt": STAGE004_SMOKE_RECEIPT,
        "stage004_result": STAGE004_RESULT,
        "stage004_review": STAGE004_REVIEW,
        "stage004_runner": TOOL_DIR / "stage004_runtime_smoke.py",
        "runtime_core": TOOL_DIR / "runtime_smoke.py",
        "preregistration": PREREGISTRATION,
        "stage005a_runtime_receipt": RUNTIME_RECEIPT,
        "stage005a_smoke_receipt": STAGE005A_SMOKE_RECEIPT,
        "stage005a_scope_audit": STAGE005A_SCOPE_AUDIT,
        "stage005a_postrun_review": STAGE005A_POSTRUN_REVIEW,
        "stage005a_postrun_review_decision": (
            STAGE005A_POSTRUN_REVIEW_DECISION
        ),
        "v2_migration_preregistration": V2_MIGRATION_PREREGISTRATION,
        "prerun_block_remediation_preregistration": (
            PRERUN_BLOCK_REMEDIATION_PREREGISTRATION
        ),
        "block_rereview": BLOCK_REREVIEW,
        "block_rereview_decision": BLOCK_REREVIEW_DECISION,
        "second_block_remediation_preregistration": (
            SECOND_BLOCK_REMEDIATION_PREREGISTRATION
        ),
        "second_block_rereview": SECOND_BLOCK_REREVIEW,
        "second_block_rereview_decision": SECOND_BLOCK_REREVIEW_DECISION,
        "third_block_remediation_preregistration": (
            THIRD_BLOCK_REMEDIATION_PREREGISTRATION
        ),
        "third_block_rereview": THIRD_BLOCK_REREVIEW,
        "third_block_rereview_decision": THIRD_BLOCK_REREVIEW_DECISION,
    }


def _verify_static_inputs() -> dict[str, dict[str, Any]]:
    _v2_runtime_gate()
    identities: dict[str, dict[str, Any]] = {}
    for name, path in sorted(_static_paths().items()):
        if not path.is_file():
            raise Stage005Error(f"stage005_static_input_missing:{name}:{path}")
        digest = _sha256(path)
        if digest != EXPECTED_STATIC_SHA256[name]:
            raise Stage005Error(f"stage005_static_input_drift:{name}:{digest}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    smoke = json.loads(STAGE004_SMOKE_RECEIPT.read_text(encoding="utf-8"))
    review = STAGE004_REVIEW.read_text(encoding="utf-8")
    if (
        smoke.get("passed") is not True
        or smoke.get("decision")
        != "stage004_runtime_smoke_pass_allow_development_label_batch_preregistration"
        or "ALLOW_STAGE005_PREREG_ONLY" not in review
        or "P0：0项" not in review
        or "P1：0项" not in review
    ):
        raise Stage005Error("stage004_authorization_contract_not_satisfied")
    v2_smoke = json.loads(
        STAGE005A_SMOKE_RECEIPT.read_text(encoding="utf-8")
    )
    scope = json.loads(STAGE005A_SCOPE_AUDIT.read_text(encoding="utf-8"))
    postrun = json.loads(
        STAGE005A_POSTRUN_REVIEW_DECISION.read_text(encoding="utf-8")
    )
    if (
        v2_smoke.get("passed") is not True
        or v2_smoke.get("decision")
        != "stage005a_runtime_identity_smoke_pass_allow_stage005_batch_rereview_only"
        or scope.get("passed") is not True
        or any(int(value) != 0 for value in scope.get("counts", {}).values())
        or postrun.get("decision")
        != "allow_stage005_migration_to_v2_and_batch_prereview_only"
        or postrun.get("allowed") is not True
        or postrun.get("findings")
        != {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        or "run_any_of_270_jobs"
        not in set(postrun.get("explicitly_not_authorized", []))
    ):
        raise Stage005Error("stage005a_v2_migration_contract_not_satisfied")
    return identities


def _authorization_bindings() -> dict[str, Path]:
    return {
        "runner": Path(__file__).resolve(),
        "core": CORE_HELPER,
        "core_tests": CORE_TEST,
        "runner_tests": RUNNER_TEST,
        "preregistration": PREREGISTRATION,
        "v2_migration_preregistration": V2_MIGRATION_PREREGISTRATION,
        "prerun_block_remediation_preregistration": (
            PRERUN_BLOCK_REMEDIATION_PREREGISTRATION
        ),
        "block_rereview": BLOCK_REREVIEW,
        "block_rereview_decision": BLOCK_REREVIEW_DECISION,
        "second_block_remediation_preregistration": (
            SECOND_BLOCK_REMEDIATION_PREREGISTRATION
        ),
        "second_block_rereview": SECOND_BLOCK_REREVIEW,
        "second_block_rereview_decision": SECOND_BLOCK_REREVIEW_DECISION,
        "third_block_remediation_preregistration": (
            THIRD_BLOCK_REMEDIATION_PREREGISTRATION
        ),
        "third_block_rereview": THIRD_BLOCK_REREVIEW,
        "third_block_rereview_decision": THIRD_BLOCK_REREVIEW_DECISION,
        "stage005a_runner": Path(runtime_v2.__file__).resolve(),
        "stage005a_runner_tests": runtime_v2.TEST_FILE,
        "stage005a_smoke_authorization": runtime_v2.RUN_AUTHORIZATION,
        "stage005a_runtime_receipt": RUNTIME_RECEIPT,
        "stage005a_smoke_receipt": STAGE005A_SMOKE_RECEIPT,
        "stage005a_scope_audit": STAGE005A_SCOPE_AUDIT,
        "stage005a_postrun_review": STAGE005A_POSTRUN_REVIEW,
        "stage005a_postrun_review_decision": (
            STAGE005A_POSTRUN_REVIEW_DECISION
        ),
        "prerun_review": PRERUN_REVIEW,
        "prerun_review_decision": PRERUN_REVIEW_DECISION,
    }


def _verify_run_authorization() -> dict[str, Any]:
    if (
        not PRERUN_REVIEW.is_file()
        or not PRERUN_REVIEW_DECISION.is_file()
        or not RUN_AUTHORIZATION.is_file()
    ):
        raise Stage005Error("stage005_prerun_review_or_authorization_missing")
    review_audit = batch_core.validate_structured_review_decision(
        PRERUN_REVIEW_DECISION, PRERUN_REVIEW
    )
    if not review_audit["passed"]:
        raise Stage005Error("stage005_prerun_review_not_allowing_batch")
    audit = batch_core.validate_run_authorization(
        RUN_AUTHORIZATION,
        _authorization_bindings(),
        expected_scope=AUTHORIZATION_SCOPE,
        require_campaign_nonce=True,
    )
    if not audit["passed"]:
        raise Stage005Error(f"stage005_run_authorization_failed:{audit}")
    return audit


def _authorization_unconsumed_gate(
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    passed = bool(
        authorization.get("scope") == AUTHORIZATION_SCOPE
        and isinstance(authorization.get("campaign_nonce"), str)
        and len(str(authorization["campaign_nonce"])) == 64
        and not AUTHORIZATION_CONSUMPTION.exists()
    )
    audit = {
        "passed": passed,
        "scope": authorization.get("scope"),
        "campaign_nonce": authorization.get("campaign_nonce"),
        "consumption_path": str(AUTHORIZATION_CONSUMPTION.resolve()),
        "already_consumed": AUTHORIZATION_CONSUMPTION.exists(),
    }
    if not passed:
        raise Stage005Error(f"stage005_authorization_already_consumed:{audit}")
    return audit


def _consume_campaign_authorization(
    authorization: Mapping[str, Any], campaign_id: str
) -> dict[str, Any]:
    if (
        authorization.get("scope") != AUTHORIZATION_SCOPE
        or not isinstance(authorization.get("campaign_nonce"), str)
        or len(str(authorization["campaign_nonce"])) != 64
        or not isinstance(authorization.get("authorization_sha256"), str)
    ):
        raise Stage005Error("stage005_authorization_consumption_input_invalid")
    payload = {
        "decision": "stage005_authorization_consumed_for_one_campaign",
        "generated_at": datetime.now()
        .astimezone()
        .isoformat(timespec="seconds"),
        "authorization_sha256": str(authorization["authorization_sha256"]),
        "campaign_nonce": str(authorization["campaign_nonce"]),
        "scope": str(authorization["scope"]),
        "campaign_id": str(campaign_id),
    }
    batch_core._write_new_json(AUTHORIZATION_CONSUMPTION, payload)
    return payload


def _authorization_campaign_gate(
    authorization: Mapping[str, Any], campaign_dir: Path
) -> dict[str, Any]:
    if not AUTHORIZATION_CONSUMPTION.is_file():
        raise Stage005Error("stage005_authorization_consumption_missing")
    payload = json.loads(
        AUTHORIZATION_CONSUMPTION.read_text(encoding="utf-8")
    )
    expected = {
        "decision": "stage005_authorization_consumed_for_one_campaign",
        "authorization_sha256": str(authorization["authorization_sha256"]),
        "campaign_nonce": str(authorization["campaign_nonce"]),
        "scope": AUTHORIZATION_SCOPE,
        "campaign_id": Path(campaign_dir).name,
    }
    passed = bool(
        all(payload.get(name) == value for name, value in expected.items())
        and isinstance(payload.get("generated_at"), str)
    )
    audit = {
        "passed": passed,
        "consumption_path": str(AUTHORIZATION_CONSUMPTION.resolve()),
        "consumption_sha256": _sha256(AUTHORIZATION_CONSUMPTION),
        "campaign_id": payload.get("campaign_id"),
        "campaign_nonce": payload.get("campaign_nonce"),
        "scope": payload.get("scope"),
    }
    if not passed:
        raise Stage005Error(f"stage005_authorization_consumption_mismatch:{audit}")
    return audit


def _install_parent_environment() -> dict[str, str]:
    environment = batch_core.parent_environment(os.environ, TMP_ROOT)
    Path(environment["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    os.environ.update(environment)
    return environment


def _jobs_contract() -> pd.DataFrame:
    jobs = pd.read_csv(STAGE003_JOBS, dtype={"job_id": str, "eligibility_key": str})
    if (
        len(jobs) != EXPECTED_TOTAL_JOBS
        or jobs["job_id"].nunique() != EXPECTED_TOTAL_JOBS
        or int(jobs["job_type"].eq("main").sum()) != EXPECTED_MAIN_JOBS
        or int(jobs["job_type"].eq("A2_sentinel").sum()) != EXPECTED_A2_JOBS
        or jobs["eval_date"].nunique() != EXPECTED_DEVELOPMENT_MONTHS
        or set(jobs["split"].astype(str)) != {"development"}
        or jobs["eval_date"].astype(str).str.contains("holdout", case=False).any()
    ):
        raise Stage005Error("stage005_jobs_contract_drift")
    return jobs


def _holdout_dates() -> set[str]:
    frame = pd.read_csv(FULL_FEATURE_SPLIT)
    result = set(
        frame.loc[
            frame["split"].astype(str).eq("sealed_account_label_holdout"),
            "eval_date",
        ].astype(str)
    )
    if len(result) != 12:
        raise Stage005Error(f"stage005_holdout_date_contract_drift:{sorted(result)}")
    return result


def _configure_legacy() -> Any:
    _configure_v2_runtime()
    legacy = stage004._load_legacy_stage015()
    legacy.BASE_OUT = BASE_OUT
    legacy.TMP_ROOT = TMP_ROOT
    legacy.PROFILE = PROFILE
    legacy.PREREGISTRATION = PREREGISTRATION
    legacy.MAX_WORKERS = MAX_WORKERS
    legacy.MAX_JOB_SECONDS = MAX_JOB_SECONDS
    original_collect = legacy._collect_campaign_files

    def collect_campaign_files(campaign_dir: Path, *, s901: Any) -> dict[str, Path]:
        files = original_collect(campaign_dir, s901=s901)
        files.update(
            {
                "stage005_orchestrator": Path(__file__).resolve(),
                "stage005_core": CORE_HELPER,
                "stage005_preregistration": PREREGISTRATION,
                "stage005_v2_migration_preregistration": (
                    V2_MIGRATION_PREREGISTRATION
                ),
                "stage005_prerun_block_remediation_preregistration": (
                    PRERUN_BLOCK_REMEDIATION_PREREGISTRATION
                ),
                "stage005_second_block_remediation_preregistration": (
                    SECOND_BLOCK_REMEDIATION_PREREGISTRATION
                ),
                "stage005_third_block_remediation_preregistration": (
                    THIRD_BLOCK_REMEDIATION_PREREGISTRATION
                ),
                "stage005_initial_prerun_review": INITIAL_PRERUN_REVIEW,
                "stage005_initial_prerun_review_decision": (
                    INITIAL_PRERUN_REVIEW_DECISION
                ),
                "stage005_block_rereview": BLOCK_REREVIEW,
                "stage005_block_rereview_decision": BLOCK_REREVIEW_DECISION,
                "stage005_second_block_rereview": SECOND_BLOCK_REREVIEW,
                "stage005_second_block_rereview_decision": (
                    SECOND_BLOCK_REREVIEW_DECISION
                ),
                "stage005_third_block_rereview": THIRD_BLOCK_REREVIEW,
                "stage005_third_block_rereview_decision": (
                    THIRD_BLOCK_REREVIEW_DECISION
                ),
                "stage005_prerun_review": PRERUN_REVIEW,
                "stage005_prerun_review_decision": PRERUN_REVIEW_DECISION,
                "stage005_run_authorization": RUN_AUTHORIZATION,
                "stage005_authorization_consumption": (
                    AUTHORIZATION_CONSUMPTION
                ),
                "stage005_stage004_result": STAGE004_RESULT,
                "stage005_stage004_review": STAGE004_REVIEW,
                "stage005_stage004_smoke_receipt": STAGE004_SMOKE_RECEIPT,
                "stage005_stage005a_smoke_receipt": STAGE005A_SMOKE_RECEIPT,
                "stage005_stage005a_scope_audit": STAGE005A_SCOPE_AUDIT,
                "stage005_stage005a_postrun_review": STAGE005A_POSTRUN_REVIEW,
                "stage005_stage005a_postrun_review_decision": (
                    STAGE005A_POSTRUN_REVIEW_DECISION
                ),
                "stage005_full_feature_split": FULL_FEATURE_SPLIT,
            }
        )
        for name, path in files.items():
            if not Path(path).is_file():
                raise Stage005Error(f"stage005_manifest_input_missing:{name}:{path}")
        return files

    legacy._collect_campaign_files = collect_campaign_files
    legacy.WORKER_EXECUTION_EXACT_KEYS = set(legacy.WORKER_EXECUTION_EXACT_KEYS) | {
        "stage005_orchestrator",
        "stage005_core",
        "stage005_preregistration",
        "stage005_v2_migration_preregistration",
        "stage005_prerun_block_remediation_preregistration",
        "stage005_second_block_remediation_preregistration",
        "stage005_third_block_remediation_preregistration",
        "stage005_initial_prerun_review",
        "stage005_initial_prerun_review_decision",
        "stage005_block_rereview",
        "stage005_block_rereview_decision",
        "stage005_second_block_rereview",
        "stage005_second_block_rereview_decision",
        "stage005_third_block_rereview",
        "stage005_third_block_rereview_decision",
        "stage005_prerun_review",
        "stage005_prerun_review_decision",
        "stage005_run_authorization",
        "stage005_authorization_consumption",
        "stage005_stage004_result",
        "stage005_stage004_review",
        "stage005_stage004_smoke_receipt",
        "stage005_stage005a_smoke_receipt",
        "stage005_stage005a_scope_audit",
        "stage005_stage005a_postrun_review",
        "stage005_stage005a_postrun_review_decision",
        "stage005_full_feature_split",
    }
    original_predecision = legacy._predecision_signatures

    def capture_predecision(
        payloads: Mapping[str, pd.DataFrame], eval_date: pd.Timestamp
    ) -> dict[str, str]:
        signatures = original_predecision(payloads, eval_date)
        campaign_value = os.environ.get("STAGE015_CAMPAIGN_DIR")
        job_id = os.environ.get("STAGE015_JOB_ID")
        if not campaign_value or not job_id:
            raise Stage005Error("stage005_predecision_worker_environment_missing")
        campaign_dir = Path(campaign_value).resolve()
        job = legacy._read_job(campaign_dir, job_id)
        if str(job["job_type"]) == "main" and int(job["candidate_rank"]) == 10:
            run_token = Path(os.environ.get("TMPDIR", "missing")).parent.name
            partial = (
                campaign_dir
                / ".partial"
                / f"{job_id}_{os.getpid()}_{run_token}"
                / "predecision"
            )
            persist_predecision_evidence(
                legacy,
                payloads,
                eval_date,
                partial,
                signatures,
            )
        return signatures

    legacy._predecision_signatures = capture_predecision
    return legacy


def prepare_campaign() -> Path:
    _verify_static_inputs()
    authorization = _verify_run_authorization()
    _authorization_unconsumed_gate(authorization)
    stage004._production_identity()
    _install_parent_environment()
    RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
    BASE_OUT.mkdir(parents=True, exist_ok=True)
    CAMPAIGN_ROOT.mkdir(parents=True, exist_ok=True)
    campaign_id = (
        datetime.now().astimezone().strftime("campaign_%Y%m%dT%H%M%S%z")
        + f"_{os.getpid()}"
    )
    consumption = _consume_campaign_authorization(authorization, campaign_id)
    campaign_dir = CAMPAIGN_ROOT / campaign_id
    campaign_dir.mkdir(parents=False, exist_ok=False)
    tombstone = campaign_dir / "ABANDONED.json"
    _stable_json(
        tombstone,
        {
            "status": "prepare_failed",
            "decision": "stage005_prepare_failed_cross_campaign_reuse_forbidden",
            "reuse_forbidden": True,
            "authorization_consumption_sha256": _sha256(
                AUTHORIZATION_CONSUMPTION
            ),
        },
        overwrite=False,
    )
    for name in ("eligibility", "logs", "locks", ".partial", "attempts"):
        (campaign_dir / name).mkdir()
    try:
        jobs = _jobs_contract()
        jobs.to_csv(campaign_dir / "jobs.csv", index=False, lineterminator="\n")
        expected_audit = pd.read_csv(STAGE003_AUDIT, dtype={"job_id": str})
        expected_by_job = expected_audit.set_index("job_id")
        if len(expected_audit) != EXPECTED_MAIN_JOBS:
            raise Stage005Error("stage005_eligibility_audit_count_drift")
        formal = pd.read_csv(FORMAL_ELIGIBILITY)
        ranking = pd.read_csv(RANKED_PANEL)
        audit_rows: list[dict[str, Any]] = []
        for job in jobs[jobs["job_type"].eq("main")].itertuples(index=False):
            candidate, audit = stage004.account_plan.build_path_consistent_eligibility(
                formal,
                ranking,
                eval_date=str(job.eval_date),
                candidate_rank=int(job.candidate_rank),
                fixed_product="fu.SHFE",
            )
            expected = expected_by_job.loc[str(job.job_id)]
            expected_sha = str(expected["candidate_eligibility_sha256"])
            if (
                audit["candidate_eligibility_sha256"] != expected_sha
                or str(expected["product_vt_symbol"]) != str(job.product_vt_symbol)
            ):
                raise Stage005Error(f"stage005_eligibility_plan_drift:{job.job_id}")
            target = campaign_dir / "eligibility" / f"{job.eligibility_key}.csv"
            stage004._write_eligibility(candidate, target)
            actual_sha = _sha256(target)
            if actual_sha != expected_sha:
                raise Stage005Error(
                    f"stage005_eligibility_file_sha_mismatch:{job.job_id}:{actual_sha}"
                )
            audit_rows.append(
                {
                    "job_id": str(job.job_id),
                    "eligibility_key": str(job.eligibility_key),
                    "eligibility_sha256": actual_sha,
                }
            )
        shutil.copy2(STAGE003_AUDIT, campaign_dir / "eligibility_audit.csv")
        _stable_json(
            campaign_dir / "ranking_alignment.json",
            {
                "passed": len(audit_rows) == EXPECTED_MAIN_JOBS,
                "checked_main_jobs": len(audit_rows),
                "eligibility_sha_mismatch_count": 0,
                "a2_reuses_rank10_count": EXPECTED_A2_JOBS,
            },
        )
        legacy = _configure_legacy()
        old_stage004 = legacy._load_stage004()
        live_cfg, _s513, _s827, s901 = old_stage004._load_production_modules()
        legacy._assert_active_release(live_cfg)
        legacy._freeze_official_overrides(campaign_dir, live_cfg)
        legacy._freeze_stage819_profile_overrides(campaign_dir, s901)
        manifest = legacy._campaign_manifest(campaign_dir, s901=s901)
        if (
            manifest["files"]["runtime_database"]["sha256"]
            != EXPECTED_DATABASE_SHA256
            or manifest["files"]["production_database_source"]["sha256"]
            != EXPECTED_DATABASE_SHA256
        ):
            raise Stage005Error("stage005_campaign_database_identity_drift")
        _stable_json(campaign_dir / "campaign_identity.json", manifest)
        status = {
            "campaign_id": campaign_id,
            "campaign_path": str(campaign_dir.resolve()),
            "status": "prepared",
            "completed_jobs": 0,
            "total_jobs": EXPECTED_TOTAL_JOBS,
            "campaign_file_contract_sha256": manifest["file_contract_sha256"],
            "authorization_consumption_sha256": _sha256(
                AUTHORIZATION_CONSUMPTION
            ),
            "campaign_nonce": consumption["campaign_nonce"],
        }
        _stable_json(campaign_dir / "progress.json", status)
        _stable_json(BASE_OUT / "LATEST.json", status)
        tombstone.unlink()
        print(str(campaign_dir.resolve()), flush=True)
        return campaign_dir
    except BaseException:
        raise


def _campaign_target(campaign_dir: Path) -> Path:
    target = Path(campaign_dir).resolve()
    if not target.is_relative_to(CAMPAIGN_ROOT.resolve()):
        raise Stage005Error(f"stage005_campaign_outside_root:{target}")
    if (target / "ABANDONED.json").exists():
        raise Stage005Error("stage005_campaign_abandoned")
    return target


def _resume_identity_gate(legacy: Any, campaign_dir: Path) -> dict[str, Any]:
    _verify_static_inputs()
    authorization = _verify_run_authorization()
    stage004._production_identity()
    target = _campaign_target(campaign_dir)
    _authorization_campaign_gate(authorization, target)
    identity = json.loads(
        (target / "campaign_identity.json").read_text(encoding="utf-8")
    )
    old_stage004 = legacy._load_stage004()
    live_cfg, _s513, _s827, s901 = old_stage004._load_production_modules()
    legacy._assert_active_release(live_cfg)
    current = legacy._campaign_manifest(
        target,
        s901=s901,
        frozen_runtime=identity["runtime"],
    )
    if current != identity:
        raise Stage005Error("stage005_campaign_identity_drift_before_resume")
    return identity


def _worker_environment(legacy: Any, campaign_dir: Path, job_id: str) -> dict[str, str]:
    run_id = f"run_{time.time_ns()}_{os.getpid()}_{threading.get_ident()}"
    environment = legacy.worker_environment(
        os.environ,
        TMP_ROOT / campaign_dir.name,
        job_id,
        run_id=run_id,
    )
    environment["STAGE015_CAMPAIGN_DIR"] = str(campaign_dir.resolve())
    Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    Path(environment["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    return environment


def _run_worker_subprocess(legacy: Any, campaign_dir: Path, job_id: str) -> None:
    environment = _worker_environment(legacy, campaign_dir, job_id)
    command = worker_command(campaign_dir, job_id)
    log_path = campaign_dir / "logs" / f"{job_id}_{time.time_ns()}.log"
    with log_path.open("w", encoding="utf-8") as stream:
        try:
            completed = subprocess.run(
                command,
                cwd=RUNTIME_ROOT,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=MAX_JOB_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise Stage005Error(f"stage005_worker_timeout:{job_id}") from exc
    if completed.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise Stage005Error(
            f"stage005_worker_failed:{job_id}:{completed.returncode}:{tail}"
        )


def _validate_completed_stage005_job(
    legacy: Any,
    campaign_dir: Path,
    job: pd.Series,
    campaign_contract: str,
) -> bool:
    if not legacy._validate_completed_job(
        campaign_dir, job, campaign_contract
    ):
        return False
    if str(job["job_type"]) != "main" or int(job["candidate_rank"]) != 10:
        return True
    try:
        output = campaign_dir / "job_outputs" / str(job["job_id"])
        receipt = json.loads(
            (output / "worker_receipt.json").read_text(encoding="utf-8")
        )
        audit = batch_core.validate_predecision_evidence(
            output / "predecision", [receipt]
        )
        return bool(
            audit["passed"]
            and audit["file_count"] == len(PREDECISION_NAMES)
            and audit["receipt_count"] == 1
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _completed_job_ids(
    legacy: Any,
    campaign_dir: Path,
    jobs: pd.DataFrame,
    contract: str,
) -> set[str]:
    by_id = {str(row["job_id"]): row for _, row in jobs.iterrows()}
    return {
        job_id
        for job_id in by_id
        if _validate_completed_stage005_job(
            legacy, campaign_dir, by_id[job_id], contract
        )
    }


def _new_attempt_id() -> str:
    return (
        datetime.now().astimezone().strftime("attempt_%Y%m%dT%H%M%S%z")
        + f"_{os.getpid()}_{time.time_ns()}"
    )


def _write_attempt_post_failure(
    campaign_dir: Path, *, attempt_id: str, error: str
) -> None:
    _stable_json(
        campaign_dir / "attempts" / f"{attempt_id}_post_failure.json",
        {
            "attempt_id": attempt_id,
            "phase": "post_failure",
            "status": "failed_after_complete_marker",
            "generated_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "error": error,
        },
        overwrite=False,
    )


def _record_attempt_failure(
    campaign_dir: Path,
    *,
    attempt_id: str,
    completed_job_ids: Sequence[str],
    error: str,
) -> None:
    end_path = campaign_dir / "attempts" / f"{attempt_id}_end.json"
    if end_path.exists():
        post_failure = (
            campaign_dir / "attempts" / f"{attempt_id}_post_failure.json"
        )
        if not post_failure.exists():
            _write_attempt_post_failure(
                campaign_dir, attempt_id=attempt_id, error=error
            )
    else:
        batch_core.write_attempt_end(
            campaign_dir,
            attempt_id=attempt_id,
            status="failed",
            completed_job_ids=completed_job_ids,
            error=error,
        )
    attempt_audit = _attempt_receipt_gate(campaign_dir)
    _stable_json(campaign_dir / "attempt_audit.json", attempt_audit)
    decision_path = campaign_dir / "decision.json"
    if decision_path.is_file():
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        gates = dict(decision.get("gates", {}))
        gates.pop("attempt_validation_lifecycle_active", None)
        gates["attempt_recovery_receipts_complete"] = False
        decision.update(
            {
                "passed": False,
                "decision": (
                    "stage005_development_label_contract_failed_stop_no_training"
                ),
                "gates": gates,
                "attempt_audit": attempt_audit,
                "failure": error,
            }
        )
        _stable_json(decision_path, decision)
    jobs = pd.read_csv(campaign_dir / "jobs.csv", dtype={"job_id": str})
    progress = {
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "status": "failed_resumable_same_campaign_only",
        "attempt_id": attempt_id,
        "completed_jobs": len(set(map(str, completed_job_ids))),
        "total_jobs": len(jobs),
        "error": error,
    }
    _stable_json(campaign_dir / "progress.json", progress)
    _stable_json(BASE_OUT / "LATEST.json", progress)
    _artifact_manifest(campaign_dir)


def _finalize_completed_attempt(
    campaign_dir: Path, attempt_id: str
) -> dict[str, Any]:
    attempt_audit = _attempt_receipt_gate(campaign_dir)
    _stable_json(campaign_dir / "attempt_audit.json", attempt_audit)
    decision_path = campaign_dir / "decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    gates = dict(decision["gates"])
    gates.pop("attempt_validation_lifecycle_active", None)
    gates["attempt_recovery_receipts_complete"] = attempt_audit["passed"]
    passed = bool(all(gates.values()))
    decision_name = (
        "stage005_development_account_labels_complete_allow_stage006_training_preregistration"
        if passed
        else "stage005_development_label_contract_failed_stop_no_training"
    )
    decision.update(
        {
            "decision": decision_name,
            "passed": passed,
            "gates": gates,
            "attempt_audit": attempt_audit,
        }
    )
    _stable_json(decision_path, decision)
    report_path = campaign_dir / "report.md"
    report = report_path.read_text(encoding="utf-8").splitlines()
    if len(report) >= 3:
        report[2] = f"- 决策：`{decision_name}`"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    progress = {
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "status": "complete" if passed else "failed",
        "attempt_id": attempt_id,
        "completed_jobs": int(decision["job_counts"]["total"]),
        "total_jobs": int(decision["job_counts"]["total"]),
        "decision": decision_name,
        "campaign_file_contract_sha256": decision[
            "campaign_file_contract_sha256"
        ],
    }
    _stable_json(campaign_dir / "progress.json", progress)
    _stable_json(BASE_OUT / "LATEST.json", progress)
    manifest = _artifact_manifest(campaign_dir)
    print(
        json.dumps(
            {
                **progress,
                "artifact_file_count": manifest[
                    "file_count_excluding_manifest"
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    if not passed:
        raise Stage005Error(
            f"stage005_finalize_attempt_failed:{attempt_audit}"
        )
    return decision


def _complete_attempt_with_aggregate(
    legacy: Any,
    campaign_dir: Path,
    identity_before: Mapping[str, Any],
    *,
    attempt_id: str,
    completed_job_ids: Sequence[str],
) -> dict[str, Any]:
    try:
        aggregate_campaign(
            legacy,
            campaign_dir,
            identity_before,
            active_attempt_id=attempt_id,
        )
        batch_core.write_attempt_end(
            campaign_dir,
            attempt_id=attempt_id,
            status="complete",
            completed_job_ids=completed_job_ids,
            error=None,
        )
        return _finalize_completed_attempt(campaign_dir, attempt_id)
    except BaseException as exc:
        error = f"{type(exc).__name__}:{exc}"
        try:
            _record_attempt_failure(
                campaign_dir,
                attempt_id=attempt_id,
                completed_job_ids=completed_job_ids,
                error=error,
            )
        except BaseException as audit_exc:
            raise Stage005Error(
                f"stage005_attempt_failure_audit_failed:{audit_exc}"
            ) from exc
        raise


def run_batch(campaign_dir: Path) -> None:
    _install_parent_environment()
    legacy = _configure_legacy()
    target = _campaign_target(campaign_dir)
    identity = _resume_identity_gate(legacy, target)
    contract = str(identity["file_contract_sha256"])
    jobs = pd.read_csv(target / "jobs.csv", dtype={"job_id": str})
    by_id = {str(row["job_id"]): row for _, row in jobs.iterrows()}
    completed_before = _completed_job_ids(legacy, target, jobs, contract)
    invalid_existing = {
        path.name
        for path in (target / "job_outputs").glob("*")
        if path.is_dir() and path.name not in completed_before
    } if (target / "job_outputs").is_dir() else set()
    if invalid_existing:
        raise Stage005Error(
            f"stage005_invalid_existing_job_outputs:{sorted(invalid_existing)[:3]}"
        )
    pending = [
        str(job_id)
        for job_id in jobs["job_id"]
        if str(job_id) not in completed_before
    ]
    attempt_id = _new_attempt_id()
    commands = [worker_command(target, job_id) for job_id in pending]
    batch_core.write_attempt_start(
        target,
        attempt_id=attempt_id,
        campaign_contract_sha256=contract,
        completed_job_ids=sorted(completed_before),
        pending_job_ids=pending,
        worker_commands=commands,
    )
    progress = {
        "campaign_id": target.name,
        "campaign_path": str(target),
        "status": "running",
        "attempt_id": attempt_id,
        "completed_jobs": len(completed_before),
        "total_jobs": len(jobs),
        "selected_job_count": len(pending),
        "campaign_file_contract_sha256": contract,
    }
    _stable_json(target / "progress.json", progress)
    _stable_json(BASE_OUT / "LATEST.json", progress)
    if not pending:
        _complete_attempt_with_aggregate(
            legacy,
            target,
            attempt_id=attempt_id,
            identity_before=identity,
            completed_job_ids=sorted(completed_before),
        )
        return

    iterator = iter(pending)
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    active: dict[Future[None], str] = {}
    try:
        for _ in range(min(MAX_WORKERS, len(pending))):
            job_id = next(iterator)
            active[executor.submit(_run_worker_subprocess, legacy, target, job_id)] = job_id
        while active:
            finished, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in finished:
                job_id = active.pop(future)
                future.result()
                if not _validate_completed_stage005_job(
                    legacy, target, by_id[job_id], contract
                ):
                    raise Stage005Error(f"stage005_completed_job_invalid:{job_id}")
                completed_before.add(job_id)
                progress["completed_jobs"] = len(completed_before)
                progress["last_completed_job"] = job_id
                _stable_json(target / "progress.json", progress)
                _stable_json(BASE_OUT / "LATEST.json", progress)
                if len(completed_before) % 10 == 0:
                    print(
                        json.dumps(
                            {
                                "campaign": target.name,
                                "completed": len(completed_before),
                                "total": len(jobs),
                            },
                            separators=(",", ":"),
                        ),
                        flush=True,
                    )
                try:
                    next_job = next(iterator)
                except StopIteration:
                    continue
                active[
                    executor.submit(
                        _run_worker_subprocess, legacy, target, next_job
                    )
                ] = next_job
    except BaseException as exc:
        for future in active:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        completed_after = _completed_job_ids(legacy, target, jobs, contract)
        _record_attempt_failure(
            target,
            attempt_id=attempt_id,
            completed_job_ids=sorted(completed_after),
            error=f"{type(exc).__name__}:{exc}",
        )
        raise
    else:
        executor.shutdown(wait=True)
    _complete_attempt_with_aggregate(
        legacy,
        target,
        identity,
        attempt_id=attempt_id,
        completed_job_ids=sorted(completed_before),
    )


def _read_label(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {name: float(value) for name, value in payload.items()}


def _quantized_money_delta(value: float, baseline: float) -> float:
    return batch_core.quantized_money_reconciliation_error(
        additions=[value],
        subtractions=[baseline],
    )


def _target_reconciliation(
    output_dir: Path, label: Mapping[str, float]
) -> dict[str, float]:
    curve = pd.read_csv(output_dir / "curve.csv")
    combined = pd.read_csv(output_dir / "combined.csv")
    trades = pd.read_csv(output_dir / "trades.csv")
    curve_slippage = "slippage" if "slippage" in curve else "total_slippage"
    return {
        "end_equity_vs_net_pnl_error": batch_core.quantized_money_reconciliation_error(
            additions=[label["end_equity"]],
            subtractions=[label["base_equity"], label["future_net_pnl"]],
        ),
        "curve_net_pnl_error": batch_core.quantized_money_reconciliation_error(
            additions=[
                batch_core.quantized_money_sum(
                    pd.to_numeric(curve["net_pnl"], errors="raise").tolist()
                )
            ],
            subtractions=[label["future_net_pnl"]],
        ),
        "curve_slippage_error": batch_core.quantized_money_reconciliation_error(
            additions=[
                batch_core.quantized_money_sum(
                    pd.to_numeric(curve[curve_slippage], errors="raise").tolist()
                )
            ],
            subtractions=[label["future_slippage"]],
        ),
        "combined_net_pnl_error": batch_core.quantized_money_reconciliation_error(
            additions=[
                batch_core.quantized_money_sum(
                    pd.to_numeric(combined["net_pnl"], errors="raise").tolist()
                )
            ],
            subtractions=[label["future_net_pnl"]],
        ),
        "combined_slippage_error": batch_core.quantized_money_reconciliation_error(
            additions=[
                batch_core.quantized_money_sum(
                    pd.to_numeric(combined["slippage"], errors="raise").tolist()
                )
            ],
            subtractions=[label["future_slippage"]],
        ),
        "curve_trade_count_error": float(
            pd.to_numeric(curve["trade_count"], errors="raise").sum()
            - label["future_trade_count"]
        ),
        "combined_trade_count_error": float(
            pd.to_numeric(combined["trade_count"], errors="raise").sum()
            - label["future_trade_count"]
        ),
        "trade_rows_error": float(len(trades) - label["future_trade_count"]),
    }


def _attempt_commands(campaign_dir: Path) -> list[list[str]]:
    commands: list[list[str]] = []
    for path in sorted((campaign_dir / "attempts").glob("*_start.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        commands.extend([list(map(str, command)) for command in payload["worker_commands"]])
    return commands


def _canonical_string_list(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and all(isinstance(item, str) and bool(item) for item in value)
        and value == sorted(set(value))
    )


def _attempt_receipt_gate(
    campaign_dir: Path, *, active_attempt_id: str | None = None
) -> dict[str, Any]:
    starts = sorted((campaign_dir / "attempts").glob("*_start.json"))
    ends = sorted((campaign_dir / "attempts").glob("*_end.json"))
    post_failures = sorted(
        (campaign_dir / "attempts").glob("*_post_failure.json")
    )
    start_by_id: dict[str, dict[str, Any]] = {}
    starts_valid = True
    for path in starts:
        attempt_id = path.name.removesuffix("_start.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        sequence = payload.get("attempt_sequence")
        completed_before = payload.get("completed_job_ids_before")
        pending_before = payload.get("pending_job_ids_before")
        worker_commands = payload.get("worker_commands")
        completed_before_count = payload.get(
            "same_campaign_revalidated_job_count"
        )
        pending_before_count = payload.get("pending_job_count")
        starts_valid = bool(
            starts_valid
            and payload.get("attempt_id") == attempt_id
            and payload.get("phase") == "start"
            and payload.get("status") == "running"
            and type(sequence) is int
            and sequence > 0
            and isinstance(payload.get("generated_at"), str)
            and isinstance(payload.get("campaign_contract_sha256"), str)
            and bool(
                re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(payload.get("campaign_contract_sha256")),
                )
            )
            and _canonical_string_list(completed_before)
            and _canonical_string_list(pending_before)
            and not (set(completed_before) & set(pending_before))
            and type(completed_before_count) is int
            and completed_before_count == len(completed_before)
            and type(pending_before_count) is int
            and pending_before_count == len(pending_before)
            and isinstance(worker_commands, list)
            and all(
                isinstance(command, list)
                and bool(command)
                and all(
                    isinstance(part, str) and bool(part) for part in command
                )
                for command in worker_commands
            )
        )
        start_by_id[attempt_id] = payload
    end_by_id: dict[str, str] = {}
    ends_valid = True
    for path in ends:
        attempt_id = path.name.removesuffix("_end.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        status = payload.get("status")
        completed_after = payload.get("completed_job_ids_after")
        completed_after_count = payload.get("completed_job_count_after")
        error = payload.get("error")
        ends_valid = bool(
            ends_valid
            and payload.get("attempt_id") == attempt_id
            and payload.get("phase") == "end"
            and status in {"complete", "failed"}
            and isinstance(payload.get("generated_at"), str)
            and _canonical_string_list(completed_after)
            and type(completed_after_count) is int
            and completed_after_count == len(completed_after)
            and (
                (status == "complete" and error is None)
                or (
                    status == "failed"
                    and isinstance(error, str)
                    and bool(error.strip())
                )
            )
        )
        end_by_id[attempt_id] = str(status)
    start_ids = set(start_by_id)
    end_ids = set(end_by_id)
    sequences = [payload.get("attempt_sequence") for payload in start_by_id.values()]
    sequence_unique = bool(
        starts_valid and len(sequences) == len(set(sequences))
    )
    sequence_contiguous = bool(
        sequence_unique
        and sorted(sequences) == list(range(1, len(sequences) + 1))
    )
    ordered_ids = sorted(
        start_ids,
        key=lambda attempt_id: (
            start_by_id[attempt_id].get("attempt_sequence")
            if type(start_by_id[attempt_id].get("attempt_sequence")) is int
            else -1,
            attempt_id,
        ),
    )
    latest_attempt_id = ordered_ids[-1] if ordered_ids else None
    statuses = [
        end_by_id[attempt_id]
        for attempt_id in ordered_ids
        if attempt_id in end_by_id
    ]
    receipts_valid = starts_valid and ends_valid and sequence_contiguous
    if active_attempt_id is None:
        passed = bool(
            receipts_valid
            and starts
            and start_ids == end_ids
            and latest_attempt_id is not None
            and end_by_id.get(latest_attempt_id) == "complete"
            and not post_failures
        )
        mode = "finalized"
    else:
        passed = bool(
            receipts_valid
            and active_attempt_id == latest_attempt_id
            and active_attempt_id in start_ids
            and active_attempt_id not in end_ids
            and start_ids == end_ids | {active_attempt_id}
            and not post_failures
        )
        mode = "active_validation"
    return {
        "passed": passed,
        "mode": mode,
        "active_attempt_id": active_attempt_id,
        "attempt_count": len(starts),
        "post_failure_count": len(post_failures),
        "receipt_shape_valid": starts_valid and ends_valid,
        "attempt_sequence_unique": sequence_unique,
        "attempt_sequence_contiguous": sequence_contiguous,
        "start_end_exact": start_ids == end_ids,
        "latest_attempt_id": latest_attempt_id,
        "statuses": statuses,
        "final_status": end_by_id.get(latest_attempt_id),
    }


def _artifact_manifest(campaign_dir: Path) -> dict[str, Any]:
    manifest_path = campaign_dir / "artifact_manifest.json"
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(campaign_dir.rglob("*")):
        if not path.is_file() or path == manifest_path:
            continue
        relative = path.relative_to(campaign_dir).as_posix()
        files[relative] = {
            "size": int(path.stat().st_size),
            "sha256": _sha256(path),
        }
    payload = {
        "campaign_id": campaign_dir.name,
        "file_count_excluding_manifest": len(files),
        "files": files,
    }
    _stable_json(manifest_path, payload)
    return payload


def _allowed_campaign_artifacts(
    campaign_dir: Path, jobs: pd.DataFrame
) -> set[Path]:
    job_ids = set(jobs["job_id"].astype(str))
    allowed = {
        campaign_dir / name
        for name in (
            "jobs.csv",
            "eligibility_audit.csv",
            "ranking_alignment.json",
            "official_overrides.json",
            "official_product_universe.csv",
            "stage819_profile_overrides.json",
            "stage819_profile_eligibility.csv",
            "campaign_identity.json",
            "campaign_identity_after.json",
            "progress.json",
            "execution_scope_audit.json",
            "predecision_evidence_audit.json",
            "A2_audit.json",
            "attempt_audit.json",
            "development_labels.csv",
            "reconciliation.csv",
            "decision.json",
            "report.md",
            "artifact_manifest.json",
        )
    }
    allowed.update(
        campaign_dir / "eligibility" / f"{key}.csv"
        for key in jobs.loc[jobs["job_type"].eq("main"), "eligibility_key"].astype(str)
    )
    for path in (campaign_dir / "logs").glob("*.log"):
        if any(path.name.startswith(f"{job_id}_") for job_id in job_ids):
            allowed.add(path)
    for path in (campaign_dir / "locks").glob("*.lock"):
        if path.stem in job_ids:
            allowed.add(path)
    for path in (campaign_dir / "attempts").glob("*.json"):
        if path.name.startswith("attempt_") and (
            path.name.endswith("_start.json") or path.name.endswith("_end.json")
            or path.name.endswith("_post_failure.json")
        ):
            allowed.add(path)
    for job in jobs.itertuples(index=False):
        output = campaign_dir / "job_outputs" / str(job.job_id)
        allowed.update(output / name for name in EXPECTED_JOB_OUTPUT_FILES)
        if str(job.job_type) == "main" and int(job.candidate_rank) == 10:
            allowed.update(
                output / "predecision" / f"{name}.csv"
                for name in PREDECISION_NAMES
            )
    return {path.resolve() for path in allowed if path.is_file()}


def _decision_scope_fields(counts: Mapping[str, int]) -> dict[str, Any]:
    model_count = sum(
        int(counts[name])
        for name in (
            "model_training_command_count",
            "model_artifact_count",
            "model_training_log_event_count",
        )
    )
    ctp_count = sum(
        int(counts[name])
        for name in (
            "ctp_connect_command_count",
            "ctp_connect_log_event_count",
        )
    )
    order_count = sum(
        int(counts[name])
        for name in ("order_command_count", "order_log_event_count")
    )
    return {
        "trains_model": model_count > 0,
        "sealed_holdout_label_count": int(counts["holdout_label_count"]),
        "order_api_called_count": order_count,
        "ctp_connected": ctp_count > 0,
    }


def aggregate_campaign(
    legacy: Any,
    campaign_dir: Path,
    identity_before: Mapping[str, Any],
    *,
    active_attempt_id: str,
) -> dict[str, Any]:
    jobs = pd.read_csv(campaign_dir / "jobs.csv", dtype={"job_id": str})
    contract = str(identity_before["file_contract_sha256"])
    if _completed_job_ids(legacy, campaign_dir, jobs, contract) != set(
        jobs["job_id"].astype(str)
    ):
        raise Stage005Error("stage005_campaign_outputs_incomplete")
    output_ids = {
        path.name
        for path in (campaign_dir / "job_outputs").iterdir()
        if path.is_dir()
    }
    expected_ids = set(jobs["job_id"].astype(str))
    if output_ids != expected_ids:
        raise Stage005Error("stage005_output_job_set_drift")

    receipts: dict[str, dict[str, Any]] = {}
    labels: list[dict[str, Any]] = []
    for job in jobs.itertuples(index=False):
        output = campaign_dir / "job_outputs" / job.job_id
        receipt = json.loads(
            (output / "worker_receipt.json").read_text(encoding="utf-8")
        )
        receipts[str(job.job_id)] = receipt
        labels.append(
            {
                "job_id": str(job.job_id),
                "job_type": str(job.job_type),
                "eval_date": str(job.eval_date),
                "next_eval_date": str(job.next_eval_date),
                "product_vt_symbol": str(job.product_vt_symbol),
                "candidate_rank": int(job.candidate_rank),
                **_read_label(output / "label.json"),
            }
        )
    label_frame = pd.DataFrame(labels)
    main = label_frame[label_frame["job_type"].eq("main")].copy()

    reconciliation_rows: list[dict[str, Any]] = []
    for eval_date, month in main.groupby("eval_date", sort=True):
        baseline_rows = month[month["candidate_rank"].eq(10)]
        if len(baseline_rows) != 1:
            raise Stage005Error(f"stage005_baseline_shape:{eval_date}")
        baseline = baseline_rows.iloc[0]
        for _, candidate in month.sort_values("candidate_rank").iterrows():
            output = campaign_dir / "job_outputs" / str(candidate["job_id"])
            reconciliation_rows.append(
                {
                    "job_id": str(candidate["job_id"]),
                    "eval_date": str(eval_date),
                    "candidate_rank": int(candidate["candidate_rank"]),
                    "base_equity_delta": batch_core.quantized_money_reconciliation_error(
                        additions=[candidate["base_equity"]],
                        subtractions=[baseline["base_equity"]],
                    ),
                    "end_equity_delta_vs_net_pnl_delta_error": (
                        batch_core.quantized_money_reconciliation_error(
                            additions=[
                                candidate["end_equity"],
                                baseline["future_net_pnl"],
                            ],
                            subtractions=[
                                baseline["end_equity"],
                                candidate["future_net_pnl"],
                            ],
                        )
                    ),
                    "return_delta": float(
                        candidate["future_return"] - baseline["future_return"]
                    ),
                    "drawdown_improvement": float(
                        candidate["future_max_drawdown"]
                        - baseline["future_max_drawdown"]
                    ),
                    "net_pnl_delta": _quantized_money_delta(
                        candidate["future_net_pnl"],
                        baseline["future_net_pnl"],
                    ),
                    "slippage_delta": _quantized_money_delta(
                        candidate["future_slippage"],
                        baseline["future_slippage"],
                    ),
                    "trade_count_delta": float(
                        candidate["future_trade_count"]
                        - baseline["future_trade_count"]
                    ),
                    **_target_reconciliation(output, candidate.to_dict()),
                }
            )
    reconciliation = pd.DataFrame(reconciliation_rows)
    error_columns = [name for name in reconciliation if name.endswith("_error")]
    reconciliation_pass = bool(
        not reconciliation.empty
        and reconciliation[error_columns].abs().max().max() <= 1e-9
        and reconciliation["base_equity_delta"].abs().max() <= 1e-9
    )

    predecision_audit: dict[str, Any] = {}
    for eval_date, month_jobs in jobs.groupby("eval_date", sort=True):
        baseline_job = month_jobs[
            month_jobs["job_type"].eq("main")
            & month_jobs["candidate_rank"].eq(10)
        ]
        if len(baseline_job) != 1:
            raise Stage005Error(f"stage005_predecision_baseline_shape:{eval_date}")
        baseline_id = str(baseline_job.iloc[0]["job_id"])
        month_receipts = [
            receipts[str(job_id)] for job_id in month_jobs["job_id"].astype(str)
        ]
        predecision_audit[str(eval_date)] = batch_core.validate_predecision_evidence(
            campaign_dir / "job_outputs" / baseline_id / "predecision",
            month_receipts,
        )
    predecision_file_count = sum(
        int(value["file_count"]) for value in predecision_audit.values()
    )
    predecision_pass = bool(
        len(predecision_audit) == EXPECTED_DEVELOPMENT_MONTHS
        and predecision_file_count == EXPECTED_PREDECISION_FILES
        and all(value["passed"] for value in predecision_audit.values())
    )

    a2_audit: dict[str, Any] = {}
    for sentinel in label_frame[
        label_frame["job_type"].eq("A2_sentinel")
    ].itertuples(index=False):
        baseline = label_frame[
            label_frame["job_type"].eq("main")
            & label_frame["eval_date"].eq(sentinel.eval_date)
            & label_frame["candidate_rank"].eq(10)
        ].iloc[0]
        left = campaign_dir / "job_outputs" / str(baseline["job_id"])
        right = campaign_dir / "job_outputs" / str(sentinel.job_id)
        file_gates = {
            name: _sha256(left / name) == _sha256(right / name)
            for name in sorted(AA_COMPARE_FILES)
        }
        a2_audit[str(sentinel.job_id)] = {
            "baseline_job_id": str(baseline["job_id"]),
            "passed": all(file_gates.values()),
            "files": file_gates,
        }
    a2_pass = bool(
        len(a2_audit) == EXPECTED_A2_JOBS
        and all(value["passed"] for value in a2_audit.values())
    )

    runtime_hashes = {
        str(receipt["normalized_runtime_sha256"]) for receipt in receipts.values()
    }
    worker_identity_pass = all(
        receipt.get("input_identity_pass") is True
        and receipt.get("checkpoint_reused") is False
        and receipt.get("completed_result_reused") is False
        and float(receipt.get("wall_seconds", MAX_JOB_SECONDS + 1)) <= MAX_JOB_SECONDS
        and receipt.get("campaign_file_contract_sha256") == contract
        and legacy._shared_builder_receipt_gate(receipt)
        for receipt in receipts.values()
    )
    worker_isolation_pass = bool(
        len({int(value["fresh_process_pid"]) for value in receipts.values()})
        == EXPECTED_TOTAL_JOBS
        and len({str(value["tmpdir"]) for value in receipts.values()})
        == EXPECTED_TOTAL_JOBS
        and len({str(value["mplconfigdir"]) for value in receipts.values()})
        == EXPECTED_TOTAL_JOBS
        and len(runtime_hashes) == 1
    )
    boundary_pass = all(
        receipt.get("entry_candidate_boundary_gate", {}).get("passed") is True
        for receipt in receipts.values()
    )

    old_stage004 = legacy._load_stage004()
    live_cfg, _s513, _s827, s901 = old_stage004._load_production_modules()
    legacy._assert_active_release(live_cfg)
    identity_after = legacy._campaign_manifest(
        campaign_dir,
        s901=s901,
        frozen_runtime=identity_before["runtime"],
    )
    identity_pass = identity_after == dict(identity_before)
    _stable_json(campaign_dir / "campaign_identity_after.json", identity_after)
    snapshot_after = stage004.smoke_core.validate_runtime_snapshot(
        PRODUCTION_DATABASE,
        RUNTIME_DATABASE,
        RUNTIME_SETTING,
        expected_database_sha256=EXPECTED_DATABASE_SHA256,
        expected_database_size=runtime_v2.EXPECTED_DATABASE_SIZE,
        expected_setting_sha256=EXPECTED_SETTING_SHA256,
        expected_bar_rows=runtime_v2.EXPECTED_BAR_ROWS,
        expected_max_datetime=runtime_v2.EXPECTED_MAX_DATETIME,
    )
    production_after = stage004._production_identity()

    artifact_paths = [
        path for path in campaign_dir.rglob("*") if path.is_file()
    ]
    log_texts = [
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted((campaign_dir / "logs").glob("*.log"))
    ]
    scope_audit = batch_core.build_execution_scope_audit(
        jobs=jobs,
        output_job_ids=output_ids,
        worker_commands=_attempt_commands(campaign_dir),
        expected_worker_commands={
            tuple(worker_command(campaign_dir, str(job_id)))
            for job_id in jobs["job_id"].astype(str)
        },
        artifact_paths=artifact_paths,
        allowed_artifact_paths=_allowed_campaign_artifacts(campaign_dir, jobs),
        log_texts=log_texts,
        holdout_dates=_holdout_dates(),
    )
    _stable_json(campaign_dir / "execution_scope_audit.json", scope_audit)
    _stable_json(campaign_dir / "predecision_evidence_audit.json", predecision_audit)
    _stable_json(campaign_dir / "A2_audit.json", a2_audit)
    attempt_audit = _attempt_receipt_gate(
        campaign_dir, active_attempt_id=active_attempt_id
    )
    _stable_json(campaign_dir / "attempt_audit.json", attempt_audit)

    gates = {
        "campaign_input_identity_stable": identity_pass,
        "all_270_cold_jobs_complete": len(receipts) == EXPECTED_TOTAL_JOBS,
        "worker_identity_and_wall_time": worker_identity_pass,
        "worker_pid_tmp_runtime_isolation": worker_isolation_pass,
        "entry_candidate_boundary_semantics": boundary_pass,
        "four_A2_sentinels_exact": a2_pass,
        "monthly_raw_predecision_evidence_exact": predecision_pass,
        "quantized_label_reconciliation_exact": reconciliation_pass,
        "development_labels_266_rows": len(main) == EXPECTED_MAIN_JOBS,
        "development_months_35_exact": main["eval_date"].nunique()
        == EXPECTED_DEVELOPMENT_MONTHS,
        "execution_scope_explicit_zero_counts": scope_audit["passed"],
        "attempt_validation_lifecycle_active": attempt_audit["passed"],
        "runtime_snapshot_unchanged": snapshot_after["passed"] is True,
        "production_checkout_unchanged": production_after
        == {"head": EXPECTED_PRODUCTION_HEAD, "clean": True},
    }
    passed = bool(all(gates.values()))
    if passed:
        main.to_csv(
            campaign_dir / "development_labels.csv",
            index=False,
            lineterminator="\n",
        )
        reconciliation.to_csv(
            campaign_dir / "reconciliation.csv",
            index=False,
            lineterminator="\n",
        )
    decision_name = (
        "stage005_development_account_labels_complete_allow_stage006_training_preregistration"
        if passed
        else "stage005_development_label_contract_failed_stop_no_training"
    )
    decision = {
        "line_id": "futures_trend_xgboost_pit_curve_account_labels",
        "stage": "Stage005",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "campaign_id": campaign_dir.name,
        "decision": decision_name,
        "passed": passed,
        "gates": gates,
        "job_counts": {
            "main": int(jobs["job_type"].eq("main").sum()),
            "A2_sentinel": int(jobs["job_type"].eq("A2_sentinel").sum()),
            "total": len(jobs),
        },
        "campaign_file_contract_sha256": contract,
        "normalized_runtime_sha256": (
            next(iter(runtime_hashes)) if len(runtime_hashes) == 1 else None
        ),
        "max_worker_wall_seconds": max(
            float(value["wall_seconds"]) for value in receipts.values()
        ),
        "subprocess_timeout_seconds": MAX_JOB_SECONDS,
        "monetary_quantization_order": (
            "quantize_each_operand_to_0.000001_then_add_subtract"
        ),
        "reconciliation_max_abs_error": float(
            reconciliation[error_columns].abs().max().max()
        ),
        "predecision_month_count": len(predecision_audit),
        "predecision_raw_file_count": predecision_file_count,
        "execution_scope_counts": scope_audit["counts"],
        "attempt_audit": attempt_audit,
        "runs_backtest": True,
        **_decision_scope_fields(scope_audit["counts"]),
    }
    _stable_json(campaign_dir / "decision.json", decision)
    report = [
        "# Stage005 development账户边际标签批量生产",
        "",
        f"- 决策：`{decision_name}`",
        f"- 任务：266个主标签 + 4个A/A哨兵；完成：`{len(receipts) == 270}`。",
        f"- 35个月原始predecision证据：`{predecision_file_count}/175`；通过：`{predecision_pass}`。",
        f"- 逐操作数1e-6量化后reconciliation：`{reconciliation_pass}`。",
        f"- 显式holdout/model/CTP/order零计数：`{scope_audit['passed']}`。",
        "- 互斥反事实标签不得聚合为一条组合策略曲线。",
        "",
    ]
    (campaign_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    progress = {
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "status": (
            "validated_pending_attempt_completion" if passed else "failed"
        ),
        "completed_jobs": len(receipts),
        "total_jobs": len(jobs),
        "decision": decision_name,
        "campaign_file_contract_sha256": contract,
    }
    _stable_json(campaign_dir / "progress.json", progress)
    _stable_json(BASE_OUT / "LATEST.json", progress)
    if not passed:
        raise Stage005Error(f"stage005_aggregate_failed:{gates}")
    return decision


def validate_campaign(campaign_dir: Path) -> dict[str, Any]:
    _install_parent_environment()
    legacy = _configure_legacy()
    target = _campaign_target(campaign_dir)
    identity = _resume_identity_gate(legacy, target)
    contract = str(identity["file_contract_sha256"])
    jobs = pd.read_csv(target / "jobs.csv", dtype={"job_id": str})
    completed = _completed_job_ids(legacy, target, jobs, contract)
    pending = sorted(set(jobs["job_id"].astype(str)) - completed)
    attempt_id = _new_attempt_id()
    batch_core.write_attempt_start(
        target,
        attempt_id=attempt_id,
        campaign_contract_sha256=contract,
        completed_job_ids=sorted(completed),
        pending_job_ids=pending,
        worker_commands=[],
    )
    progress = {
        "campaign_id": target.name,
        "campaign_path": str(target.resolve()),
        "status": "validating",
        "attempt_id": attempt_id,
        "completed_jobs": len(completed),
        "total_jobs": len(jobs),
        "selected_job_count": 0,
        "campaign_file_contract_sha256": contract,
    }
    _stable_json(target / "progress.json", progress)
    _stable_json(BASE_OUT / "LATEST.json", progress)
    return _complete_attempt_with_aggregate(
        legacy,
        target,
        identity,
        attempt_id=attempt_id,
        completed_job_ids=sorted(completed),
    )


def preflight() -> dict[str, Any]:
    environment = _install_parent_environment()
    static = _verify_static_inputs()
    authorization = _verify_run_authorization()
    consumption = _authorization_unconsumed_gate(authorization)
    production = stage004._production_identity()
    runtime = json.loads(RUNTIME_RECEIPT.read_text(encoding="utf-8"))
    jobs = _jobs_contract()
    result = {
        "decision": "stage005_preflight_pass_ready_prepare_campaign",
        "passed": True,
        "static_input_count": len(static),
        "authorization_sha256": authorization["authorization_sha256"],
        "authorization_scope": authorization["scope"],
        "campaign_nonce": authorization["campaign_nonce"],
        "authorization_unconsumed": consumption["passed"],
        "production": production,
        "runtime_database_sha256": runtime["snapshot"]["clone_sha256"],
        "job_count": len(jobs),
        "main_job_count": int(jobs["job_type"].eq("main").sum()),
        "A2_job_count": int(jobs["job_type"].eq("A2_sentinel").sum()),
        "development_month_count": jobs["eval_date"].nunique(),
        "parent_environment": {
            name: environment[name]
            for name in (
                "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR",
                "MPLCONFIGDIR",
                "TMPDIR",
            )
        },
        "runs_backtest": False,
        "trains_model": False,
        "sealed_holdout_label_count": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return result


def _worker_environment_gate(
    campaign_dir: Path, job_id: str
) -> dict[str, str]:
    environment = {
        name: str(os.environ.get(name, ""))
        for name in (
            "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR",
            "TMPDIR",
            "MPLCONFIGDIR",
        )
    }
    tmpdir = Path(environment["TMPDIR"]).resolve()
    mplconfigdir = Path(environment["MPLCONFIGDIR"]).resolve()
    expected_root = (TMP_ROOT / Path(campaign_dir).name / str(job_id)).resolve()
    if (
        environment["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] != "1"
        or not tmpdir.is_relative_to(expected_root)
        or not mplconfigdir.is_relative_to(expected_root)
        or tmpdir.parent != mplconfigdir.parent
        or tmpdir.name != "tmp"
        or mplconfigdir.name != "mplconfig"
    ):
        raise Stage005Error(
            f"stage005_worker_environment_invalid:{environment}"
        )
    return environment


def run_worker(job_id: str, campaign_dir: Path) -> None:
    authorization = _verify_run_authorization()
    _configure_v2_runtime()
    target = _campaign_target(campaign_dir)
    _authorization_campaign_gate(authorization, target)
    _worker_environment_gate(target, str(job_id))
    legacy = _configure_legacy()
    with legacy._exclusive_lock(target / f"locks/{job_id}.lock"):
        legacy._run_worker(job_id, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--prepare-campaign", action="store_true")
    parser.add_argument("--run-batch", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--worker")
    parser.add_argument("--campaign-dir")
    args = parser.parse_args()
    selected = sum(
        bool(value)
        for value in (
            args.preflight,
            args.prepare_campaign,
            args.run_batch,
            args.validate_only,
            args.worker,
        )
    )
    if selected != 1:
        raise Stage005Error("select_exactly_one_stage005_mode")
    campaign = Path(args.campaign_dir).resolve() if args.campaign_dir else None
    if args.worker:
        if campaign is None:
            raise Stage005Error("stage005_worker_campaign_required")
        run_worker(str(args.worker), campaign)
        return
    _install_parent_environment()
    if args.preflight:
        if campaign is not None:
            raise Stage005Error("stage005_preflight_campaign_forbidden")
        preflight()
    elif args.prepare_campaign:
        if campaign is not None:
            raise Stage005Error("stage005_prepare_campaign_arg_forbidden")
        prepare_campaign()
    elif args.run_batch:
        if campaign is None:
            raise Stage005Error("stage005_run_campaign_required")
        run_batch(campaign)
    else:
        if campaign is None:
            raise Stage005Error("stage005_validate_campaign_required")
        validate_campaign(campaign)


if __name__ == "__main__":
    main()

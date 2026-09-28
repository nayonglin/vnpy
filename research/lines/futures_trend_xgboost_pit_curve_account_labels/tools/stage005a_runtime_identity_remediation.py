"""Freeze the Stage005 v2 runtime and rerun the fixed four-job smoke."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Final, Mapping

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import development_label_batch as batch_core  # noqa: E402
import stage004_runtime_smoke as stage004  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
LIVE_PRODUCTION_DATABASE = stage004.PRODUCTION_ROOT / ".vntrader/database.db"
RUNTIME_ROOT = Path("/private/tmp/vnpy-stage005-curve-account-runtime-v2")
RUNTIME_DATABASE = RUNTIME_ROOT / ".vntrader/database.db"
RUNTIME_SETTING = RUNTIME_ROOT / ".vntrader/vt_setting.json"
RUNTIME_LOG_DIR = RUNTIME_ROOT / ".vntrader/log"
FROZEN_INPUT_DIR = RUNTIME_ROOT / "frozen_inputs"
FROZEN_SOURCE_DATABASE = FROZEN_INPUT_DIR / "production_database_source.db"
FROZEN_MAPPING = FROZEN_INPUT_DIR / "main_contract_mapping.csv"
FROZEN_MINUTE_BARS = FROZEN_INPUT_DIR / "full_minute_bars.csv"
FROZEN_CONTRACT_METADATA = FROZEN_INPUT_DIR / "contract_metadata.csv"
TMP_ROOT = Path("/private/tmp/vnpy-stage005a-runtime-identity-smoke")
BASE_OUT = LINE_DIR / "artifacts/stage005a_runtime_identity_remediation"
CAMPAIGN_ROOT = BASE_OUT / "campaigns"
RUNTIME_RECEIPT = BASE_OUT / "runtime_snapshot_receipt.json"
PREREGISTRATION = (
    LINE_DIR
    / "stages/20260902_1748_stage005a_runtime_identity_remediation_preregistration.md"
)
ENV_REMEDIATION_PREREGISTRATION = (
    LINE_DIR
    / "stages/20260902_1844_stage005a_parent_environment_remediation_preregistration.md"
)
WORKER_ENV_REMEDIATION_PREREGISTRATION = (
    LINE_DIR
    / "stages/20260902_1903_stage005a_worker_environment_failure_and_remediation_preregistration.md"
)
INITIAL_PRERUN_REVIEW = (
    LINE_DIR / "reviews/20260902_stage005a_prerun_independent_review.md"
)
INITIAL_PRERUN_REVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005a_prerun_review_decision.json"
)
FIRST_ALLOW_REVIEW = (
    LINE_DIR / "reviews/20260902_stage005a_prerun_rereview.md"
)
FIRST_ALLOW_REVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005a_prerun_rereview_decision.json"
)
FIRST_RUN_AUTHORIZATION = (
    LINE_DIR / "reviews/20260902_stage005a_run_authorization.json"
)
SECOND_ALLOW_REVIEW = (
    LINE_DIR / "reviews/20260902_stage005a_env_remediation_rereview.md"
)
SECOND_ALLOW_REVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005a_env_remediation_rereview_decision.json"
)
SECOND_RUN_AUTHORIZATION = (
    LINE_DIR / "reviews/20260902_stage005a_env_remediation_run_authorization.json"
)
PRERUN_REVIEW = (
    LINE_DIR / "reviews/20260902_stage005a_worker_env_rereview.md"
)
PRERUN_REVIEW_DECISION = (
    LINE_DIR / "reviews/20260902_stage005a_worker_env_rereview_decision.json"
)
RUN_AUTHORIZATION = (
    LINE_DIR / "reviews/20260902_stage005a_worker_env_run_authorization.json"
)
TEST_FILE = (
    LINE_DIR / "tests/test_stage005a_runtime_identity_remediation.py"
)
SCOPE_TEST_FILE = LINE_DIR / "tests/test_development_label_batch.py"
FAILED_WORKER_CAMPAIGN = (
    BASE_OUT / "campaigns/campaign_20260902T185715+0800_65899"
)
FAILED_WORKER_FAILURE_RECEIPT = FAILED_WORKER_CAMPAIGN / "failure_receipt.json"
FAILED_WORKER_ABANDONED = FAILED_WORKER_CAMPAIGN / "ABANDONED.json"
FAILED_R10_RECEIPT = (
    FAILED_WORKER_CAMPAIGN
    / "job_outputs/20220128_R10/worker_receipt.json"
)
FAILED_R10_A2_RECEIPT = (
    FAILED_WORKER_CAMPAIGN
    / "job_outputs/20220128_R10_A2/worker_receipt.json"
)
FULL_FEATURE_SPLIT = (
    LINE_DIR / "artifacts/stage003_account_label_plan/full_feature_split.csv"
)
SOURCE_MAPPING = (
    WORKSPACE_ROOT
    / "examples/portfolio_backtesting/backtest_outputs/"
    "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
)
SOURCE_MINUTE_BARS = (
    WORKSPACE_ROOT
    / "examples/portfolio_backtesting/backtest_outputs/"
    "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_"
    "stage861_stage860_full_visual_atlas_v1.csv"
)
SOURCE_CONTRACT_METADATA = (
    WORKSPACE_ROOT
    / "examples/portfolio_backtesting/backtest_outputs/"
    "tqsdk_all_futures_contract_metadata.csv"
)
EXPECTED_DATABASE_SHA256 = (
    "db3342006f4220767f06e466bb40c046f372961cea41cef9a6d8bc1727fa0c4b"
)
EXPECTED_DATABASE_SIZE = 112_271_360
EXPECTED_BAR_ROWS = 1_020_420
EXPECTED_MAX_DATETIME = "2026-09-02 00:00:00"
EXPECTED_SETTING_SHA256 = stage004.EXPECTED_SETTING_SHA256
EXPECTED_SOURCE_SHA256: Final = {
    "database": EXPECTED_DATABASE_SHA256,
    "main_contract_mapping": (
        "093d3bc767c09d9e0e4f4fbeb9846a091bf25c163cc31eddfd382cc1ff5490b7"
    ),
    "full_minute_bars": (
        "8e861633b08a82819a668c30c6799e2098d2beaa6863698351145018ea586784"
    ),
    "contract_metadata": (
        "24a3573e847e024411b13a3a3b775791ded57563b0a68b717d1065078201635a"
    ),
}
SMOKE_JOB_IDS = stage004.SMOKE_JOB_IDS
MAX_JOB_SECONDS = stage004.MAX_JOB_SECONDS
PROFILE = "stage005a_runtime_identity_remediation_smoke"
MINIMUM_FREE_BYTES = 1024**3
EXPECTED_SMOKE_OUTPUT_FILES = set(
    stage004.smoke_core.EXPECTED_JOB_OUTPUT_FILES
) | {"worker_receipt.json"}

_ORIGINAL_LOAD_LEGACY = stage004._load_legacy_stage015


class Stage005AError(RuntimeError):
    """Raised when the identity-remediation smoke must fail closed."""


def _sha256(path: Path) -> str:
    return stage004.smoke_core.sha256_file(path)


def _stable_json(path: Path, payload: Any, *, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"append_only_json_exists:{path}")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _install_parent_environment() -> dict[str, str]:
    environment = batch_core.parent_environment(os.environ, TMP_ROOT)
    Path(environment["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    os.environ.update(environment)
    return environment


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


def _runtime_binding_values() -> dict[str, Any]:
    return {
        "PRODUCTION_DATABASE": FROZEN_SOURCE_DATABASE,
        "RUNTIME_ROOT": RUNTIME_ROOT,
        "RUNTIME_DATABASE": RUNTIME_DATABASE,
        "RUNTIME_SETTING": RUNTIME_SETTING,
        "RUNTIME_LOG_DIR": RUNTIME_LOG_DIR,
        "TMP_ROOT": TMP_ROOT,
        "BASE_OUT": BASE_OUT,
        "CAMPAIGN_ROOT": CAMPAIGN_ROOT,
        "RUNTIME_RECEIPT": RUNTIME_RECEIPT,
        "EXPECTED_DATABASE_SHA256": EXPECTED_DATABASE_SHA256,
        "EXPECTED_DATABASE_SIZE": EXPECTED_DATABASE_SIZE,
        "EXPECTED_SETTING_SHA256": EXPECTED_SETTING_SHA256,
        "EXPECTED_BAR_ROWS": EXPECTED_BAR_ROWS,
        "EXPECTED_MAX_DATETIME": EXPECTED_MAX_DATETIME,
        "PROFILE": PROFILE,
    }


def _apply_runtime_bindings(target: Any) -> None:
    for name, value in _runtime_binding_values().items():
        setattr(target, name, value)


def _authorization_bindings() -> dict[str, Path]:
    return {
        "runner": Path(__file__).resolve(),
        "runner_test": TEST_FILE,
        "scope_core": TOOL_DIR / "development_label_batch.py",
        "scope_core_test": SCOPE_TEST_FILE,
        "stage004_runner": TOOL_DIR / "stage004_runtime_smoke.py",
        "runtime_core": TOOL_DIR / "runtime_smoke.py",
        "account_label_plan": TOOL_DIR / "account_label_plan.py",
        "preregistration": PREREGISTRATION,
        "env_remediation_preregistration": ENV_REMEDIATION_PREREGISTRATION,
        "worker_env_remediation_preregistration": (
            WORKER_ENV_REMEDIATION_PREREGISTRATION
        ),
        "initial_prerun_review": INITIAL_PRERUN_REVIEW,
        "initial_prerun_review_decision": INITIAL_PRERUN_REVIEW_DECISION,
        "first_allow_review": FIRST_ALLOW_REVIEW,
        "first_allow_review_decision": FIRST_ALLOW_REVIEW_DECISION,
        "first_run_authorization": FIRST_RUN_AUTHORIZATION,
        "second_allow_review": SECOND_ALLOW_REVIEW,
        "second_allow_review_decision": SECOND_ALLOW_REVIEW_DECISION,
        "second_run_authorization": SECOND_RUN_AUTHORIZATION,
        "runtime_snapshot_receipt": RUNTIME_RECEIPT,
        "failed_worker_failure_receipt": FAILED_WORKER_FAILURE_RECEIPT,
        "failed_worker_abandoned": FAILED_WORKER_ABANDONED,
        "failed_r10_receipt": FAILED_R10_RECEIPT,
        "failed_r10_A2_receipt": FAILED_R10_A2_RECEIPT,
        "prerun_review": PRERUN_REVIEW,
        "prerun_review_decision": PRERUN_REVIEW_DECISION,
    }


def _verify_smoke_authorization() -> dict[str, Any]:
    if (
        not PRERUN_REVIEW.is_file()
        or not PRERUN_REVIEW_DECISION.is_file()
        or not RUN_AUTHORIZATION.is_file()
    ):
        raise Stage005AError("stage005a_review_or_authorization_missing")
    review = batch_core.validate_structured_review_decision(
        PRERUN_REVIEW_DECISION,
        PRERUN_REVIEW,
        expected_decision="ALLOW_STAGE005A_SMOKE",
    )
    if not review["passed"]:
        raise Stage005AError(f"stage005a_review_not_allowing_smoke:{review}")
    authorization = batch_core.validate_run_authorization(
        RUN_AUTHORIZATION,
        _authorization_bindings(),
        expected_decision="ALLOW_STAGE005A_SMOKE",
    )
    if not authorization["passed"]:
        raise Stage005AError(
            f"stage005a_run_authorization_failed:{authorization}"
        )
    return authorization


def _source_paths() -> dict[str, Path]:
    return {
        "database": LIVE_PRODUCTION_DATABASE,
        "main_contract_mapping": SOURCE_MAPPING,
        "full_minute_bars": SOURCE_MINUTE_BARS,
        "contract_metadata": SOURCE_CONTRACT_METADATA,
    }


def _verify_source_contract() -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}
    for name, path in _source_paths().items():
        if not path.is_file():
            raise Stage005AError(f"stage005a_source_missing:{name}:{path}")
        digest = _sha256(path)
        if digest != EXPECTED_SOURCE_SHA256[name]:
            raise Stage005AError(
                f"stage005a_source_identity_drift:{name}:{digest}"
            )
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    if identities["database"]["size"] != EXPECTED_DATABASE_SIZE:
        raise Stage005AError("stage005a_database_size_drift")
    audit = stage004.smoke_core.audit_sqlite_database(LIVE_PRODUCTION_DATABASE)
    if (
        audit["integrity_check"] != "ok"
        or audit["dbbardata_rows"] != EXPECTED_BAR_ROWS
        or audit["dbbardata_max_datetime"] != EXPECTED_MAX_DATETIME
    ):
        raise Stage005AError(f"stage005a_database_content_drift:{audit}")
    identities["database"]["sqlite_audit"] = audit
    return identities


def _copy_clone(source: Path, target: Path) -> None:
    completed = subprocess.run(
        ["cp", "-c", str(source), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise Stage005AError(
            f"stage005a_apfs_clone_failed:{source}:{completed.stderr.strip()}"
        )


def prepare_runtime_snapshot() -> dict[str, Any]:
    _install_parent_environment()
    authorization = _verify_smoke_authorization()
    source_before = _verify_source_contract()
    production = stage004._production_identity()
    if BASE_OUT.exists():
        raise Stage005AError(f"stage005a_output_already_exists:{BASE_OUT}")
    if RUNTIME_ROOT.exists():
        raise Stage005AError(f"stage005a_runtime_already_exists:{RUNTIME_ROOT}")
    free_bytes = int(shutil.disk_usage(WORKSPACE_ROOT).free)
    if free_bytes < MINIMUM_FREE_BYTES:
        raise Stage005AError(f"stage005a_free_disk_below_1gib:{free_bytes}")
    try:
        BASE_OUT.mkdir(parents=True, exist_ok=False)
        (RUNTIME_ROOT / ".vntrader").mkdir(parents=True, exist_ok=False)
        FROZEN_INPUT_DIR.mkdir(parents=False, exist_ok=False)
        _copy_clone(LIVE_PRODUCTION_DATABASE, FROZEN_SOURCE_DATABASE)
        _copy_clone(FROZEN_SOURCE_DATABASE, RUNTIME_DATABASE)
        _copy_clone(SOURCE_MAPPING, FROZEN_MAPPING)
        _copy_clone(SOURCE_MINUTE_BARS, FROZEN_MINUTE_BARS)
        _copy_clone(SOURCE_CONTRACT_METADATA, FROZEN_CONTRACT_METADATA)
        RUNTIME_SETTING.write_text("{}", encoding="utf-8")
        RUNTIME_LOG_DIR.mkdir(exist_ok=False)
        source_after = _verify_source_contract()
        if source_before != source_after:
            raise Stage005AError("stage005a_sources_changed_during_snapshot")
        frozen = {
            "database": FROZEN_SOURCE_DATABASE,
            "main_contract_mapping": FROZEN_MAPPING,
            "full_minute_bars": FROZEN_MINUTE_BARS,
            "contract_metadata": FROZEN_CONTRACT_METADATA,
        }
        frozen_identities = {
            name: {
                "path": str(path.resolve()),
                "size": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
            for name, path in frozen.items()
        }
        if any(
            frozen_identities[name]["sha256"] != EXPECTED_SOURCE_SHA256[name]
            for name in frozen
        ):
            raise Stage005AError("stage005a_frozen_input_hash_mismatch")
        snapshot = stage004.smoke_core.validate_runtime_snapshot(
            FROZEN_SOURCE_DATABASE,
            RUNTIME_DATABASE,
            RUNTIME_SETTING,
            expected_database_sha256=EXPECTED_DATABASE_SHA256,
            expected_database_size=EXPECTED_DATABASE_SIZE,
            expected_setting_sha256=EXPECTED_SETTING_SHA256,
            expected_bar_rows=EXPECTED_BAR_ROWS,
            expected_max_datetime=EXPECTED_MAX_DATETIME,
        )
        if not snapshot["passed"]:
            raise Stage005AError(
                f"stage005a_runtime_snapshot_gate_failed:{snapshot['gates']}"
            )
        receipt = {
            "stage": "Stage005A_runtime_snapshot",
            "generated_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "decision": (
                "stage004_runtime_snapshot_pass_ready_for_campaign_prepare"
            ),
            "stage005a_decision": (
                "stage005a_runtime_snapshot_pass_ready_for_fixed_smoke"
            ),
            "passed": True,
            "production": production,
            "authorization_sha256": authorization["authorization_sha256"],
            "source_identities_before": source_before,
            "source_identities_after": source_after,
            "frozen_input_identities": frozen_identities,
            "source_sha256_before": EXPECTED_DATABASE_SHA256,
            "source_sha256_after": EXPECTED_DATABASE_SHA256,
            "snapshot": snapshot,
            "writes_production": False,
            "runs_backtest": False,
            "trains_model": False,
            "sealed_holdout_label_count": 0,
            "ctp_connected": False,
            "order_api_called_count": 0,
        }
        _stable_json(RUNTIME_RECEIPT, receipt, overwrite=False)
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
        return receipt
    except BaseException:
        if not RUNTIME_RECEIPT.exists():
            if RUNTIME_ROOT.exists():
                shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
            if BASE_OUT.exists():
                shutil.rmtree(BASE_OUT, ignore_errors=True)
        raise


def _patch_legacy_for_frozen_inputs(legacy: Any) -> Any:
    _apply_runtime_bindings(legacy)
    legacy.PROFILE = PROFILE
    stage004_module = legacy._load_stage004()
    if not getattr(stage004_module, "_stage005a_frozen_paths_patched", False):
        original_load = stage004_module._load_production_modules

        def load_production_modules() -> tuple[Any, Any, Any, Any]:
            live_cfg, s513, s827, s901 = original_load()
            s901.ALL_FUTURES_MAPPING_PATH = FROZEN_MAPPING
            s901.s861.FULL_MINUTE_BARS_PATH = FROZEN_MINUTE_BARS
            import contract_metadata

            contract_metadata.ALL_FUTURES_CONTRACT_METADATA_PATH = (
                FROZEN_CONTRACT_METADATA
            )
            contract_metadata.DEFAULT_CONTRACT_METADATA_PATH = (
                FROZEN_CONTRACT_METADATA
            )
            return live_cfg, s513, s827, s901

        stage004_module._load_production_modules = load_production_modules
        stage004_module._stage005a_frozen_paths_patched = True

    original_collect = legacy._collect_campaign_files

    def collect_campaign_files(
        campaign_dir: Path, *, s901: Any
    ) -> dict[str, Path]:
        files = original_collect(campaign_dir, s901=s901)
        files.update(
            {
                "runtime_database": RUNTIME_DATABASE,
                "runtime_setting": RUNTIME_SETTING,
                "production_database_source": FROZEN_SOURCE_DATABASE,
                "full_minute_bars": FROZEN_MINUTE_BARS,
                "main_contract_mapping": FROZEN_MAPPING,
                "contract_metadata": FROZEN_CONTRACT_METADATA,
                "stage005a_runner": Path(__file__).resolve(),
                "stage005a_runner_test": TEST_FILE,
                "stage005a_scope_core": TOOL_DIR / "development_label_batch.py",
                "stage005a_scope_core_test": SCOPE_TEST_FILE,
                "stage005a_preregistration": PREREGISTRATION,
                "stage005a_env_remediation_preregistration": (
                    ENV_REMEDIATION_PREREGISTRATION
                ),
                "stage005a_worker_env_remediation_preregistration": (
                    WORKER_ENV_REMEDIATION_PREREGISTRATION
                ),
                "stage005a_initial_prerun_review": INITIAL_PRERUN_REVIEW,
                "stage005a_initial_prerun_review_decision": (
                    INITIAL_PRERUN_REVIEW_DECISION
                ),
                "stage005a_first_allow_review": FIRST_ALLOW_REVIEW,
                "stage005a_first_allow_review_decision": (
                    FIRST_ALLOW_REVIEW_DECISION
                ),
                "stage005a_first_run_authorization": FIRST_RUN_AUTHORIZATION,
                "stage005a_second_allow_review": SECOND_ALLOW_REVIEW,
                "stage005a_second_allow_review_decision": (
                    SECOND_ALLOW_REVIEW_DECISION
                ),
                "stage005a_second_run_authorization": (
                    SECOND_RUN_AUTHORIZATION
                ),
                "stage005a_prerun_review": PRERUN_REVIEW,
                "stage005a_prerun_review_decision": PRERUN_REVIEW_DECISION,
                "stage005a_run_authorization": RUN_AUTHORIZATION,
                "stage005a_runtime_receipt": RUNTIME_RECEIPT,
                "stage005a_failed_worker_failure_receipt": (
                    FAILED_WORKER_FAILURE_RECEIPT
                ),
                "stage005a_failed_worker_abandoned": FAILED_WORKER_ABANDONED,
                "stage005a_failed_r10_receipt": FAILED_R10_RECEIPT,
                "stage005a_failed_r10_A2_receipt": FAILED_R10_A2_RECEIPT,
            }
        )
        for name, path in files.items():
            if not Path(path).is_file():
                raise Stage005AError(
                    f"stage005a_campaign_input_missing:{name}:{path}"
                )
        return files

    legacy._collect_campaign_files = collect_campaign_files
    legacy.WORKER_EXECUTION_EXACT_KEYS = set(
        legacy.WORKER_EXECUTION_EXACT_KEYS
    ) | {
        "stage005a_runner",
        "stage005a_runner_test",
        "stage005a_scope_core",
        "stage005a_scope_core_test",
        "stage005a_preregistration",
        "stage005a_env_remediation_preregistration",
        "stage005a_worker_env_remediation_preregistration",
        "stage005a_initial_prerun_review",
        "stage005a_initial_prerun_review_decision",
        "stage005a_first_allow_review",
        "stage005a_first_allow_review_decision",
        "stage005a_first_run_authorization",
        "stage005a_second_allow_review",
        "stage005a_second_allow_review_decision",
        "stage005a_second_run_authorization",
        "stage005a_prerun_review",
        "stage005a_prerun_review_decision",
        "stage005a_run_authorization",
        "stage005a_runtime_receipt",
        "stage005a_failed_worker_failure_receipt",
        "stage005a_failed_worker_abandoned",
        "stage005a_failed_r10_receipt",
        "stage005a_failed_r10_A2_receipt",
    }
    return legacy


def _load_legacy_stage015() -> Any:
    return _patch_legacy_for_frozen_inputs(_ORIGINAL_LOAD_LEGACY())


def _run_worker_subprocess(
    legacy: Any, campaign_dir: Path, job_id: str
) -> None:
    environment = stage004._worker_environment(legacy, campaign_dir, job_id)
    log_path = campaign_dir / "logs" / f"{job_id}_{time.time_ns()}.log"
    with log_path.open("w", encoding="utf-8") as stream:
        try:
            completed = subprocess.run(
                worker_command(campaign_dir, job_id),
                cwd=RUNTIME_ROOT,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=MAX_JOB_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise Stage005AError(f"stage005a_worker_timeout:{job_id}") from exc
    if completed.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise Stage005AError(
            f"stage005a_worker_failed:{job_id}:{completed.returncode}:{tail}"
        )


def _configure_stage004() -> None:
    _apply_runtime_bindings(stage004)
    stage004._load_legacy_stage015 = _load_legacy_stage015
    stage004._run_worker_subprocess = _run_worker_subprocess


def _runtime_receipt_gate() -> dict[str, Any]:
    _configure_stage004()
    receipt = stage004._runtime_receipt_gate()
    frozen_paths = {
        "database": FROZEN_SOURCE_DATABASE,
        "main_contract_mapping": FROZEN_MAPPING,
        "full_minute_bars": FROZEN_MINUTE_BARS,
        "contract_metadata": FROZEN_CONTRACT_METADATA,
    }
    for name, path in frozen_paths.items():
        if _sha256(path) != EXPECTED_SOURCE_SHA256[name]:
            raise Stage005AError(f"stage005a_frozen_input_drift:{name}")
    return receipt


def prepare_campaign() -> Path:
    _install_parent_environment()
    authorization = _verify_smoke_authorization()
    _configure_stage004()
    _runtime_receipt_gate()
    campaign_dir = stage004.prepare_campaign()
    commands = [worker_command(campaign_dir, job_id) for job_id in SMOKE_JOB_IDS]
    _stable_json(
        campaign_dir / "execution_plan.json",
        {
            "decision": "stage005a_fixed_four_job_smoke_plan",
            "job_ids": list(SMOKE_JOB_IDS),
            "worker_commands": commands,
            "authorization_sha256": authorization["authorization_sha256"],
            "cross_campaign_reuse": False,
        },
        overwrite=False,
    )
    return campaign_dir


def _campaign_target(campaign_dir: Path) -> Path:
    target = Path(campaign_dir).resolve()
    if not target.is_relative_to(CAMPAIGN_ROOT.resolve()):
        raise Stage005AError(f"stage005a_campaign_outside_root:{target}")
    if (target / "ABANDONED.json").exists():
        raise Stage005AError("stage005a_campaign_abandoned")
    return target


def _execution_plan_gate(campaign_dir: Path) -> dict[str, Any]:
    target = _campaign_target(campaign_dir)
    plan_path = target / "execution_plan.json"
    if not plan_path.is_file():
        raise Stage005AError("stage005a_execution_plan_missing")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    expected_commands = [
        worker_command(target, job_id) for job_id in SMOKE_JOB_IDS
    ]
    if (
        plan.get("decision") != "stage005a_fixed_four_job_smoke_plan"
        or plan.get("job_ids") != list(SMOKE_JOB_IDS)
        or plan.get("worker_commands") != expected_commands
        or plan.get("cross_campaign_reuse") is not False
        or plan.get("authorization_sha256") != _sha256(RUN_AUTHORIZATION)
    ):
        raise Stage005AError("stage005a_execution_plan_drift")
    jobs = pd.read_csv(target / "jobs.csv", dtype={"job_id": str})
    if not set(SMOKE_JOB_IDS).issubset(set(jobs["job_id"].astype(str))):
        raise Stage005AError("stage005a_campaign_jobs_missing_fixed_smoke")
    return plan


def _campaign_identity_gate(legacy: Any, campaign_dir: Path) -> dict[str, Any]:
    target = _campaign_target(campaign_dir)
    identity_path = target / "campaign_identity.json"
    if not identity_path.is_file():
        raise Stage005AError("stage005a_campaign_identity_missing")
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    stage004_module = legacy._load_stage004()
    live_cfg, _s513, _s827, s901 = stage004_module._load_production_modules()
    legacy._assert_active_release(live_cfg)
    current = legacy._campaign_manifest(
        target,
        s901=s901,
        frozen_runtime=identity["runtime"],
    )
    if current != identity:
        raise Stage005AError("stage005a_campaign_identity_drift")
    return identity


def _holdout_dates() -> set[str]:
    frame = pd.read_csv(FULL_FEATURE_SPLIT)
    return set(
        frame.loc[
            frame["split"].astype(str).eq("sealed_account_label_holdout"),
            "eval_date",
        ].astype(str)
    )


def _allowed_smoke_artifacts(
    campaign_dir: Path, jobs: pd.DataFrame
) -> set[Path]:
    campaign = Path(campaign_dir)
    allowed = {
        campaign / name
        for name in (
            "jobs.csv",
            "eligibility_audit.csv",
            "ranking_alignment.json",
            "official_overrides.json",
            "official_product_universe.csv",
            "stage819_profile_overrides.json",
            "stage819_profile_eligibility.csv",
            "campaign_identity.json",
            "progress.json",
            "execution_plan.json",
            "smoke_receipt.json",
            "execution_scope_audit.json",
        )
    }
    if "eligibility_key" in jobs:
        allowed.update(
            campaign / "eligibility" / f"{key}.csv"
            for key in jobs.loc[
                jobs["job_type"].astype(str).eq("main"), "eligibility_key"
            ].astype(str)
        )
    for job_id in SMOKE_JOB_IDS:
        allowed.add(campaign / "locks" / f"{job_id}.lock")
        output = campaign / "job_outputs" / job_id
        allowed.update(output / name for name in EXPECTED_SMOKE_OUTPUT_FILES)
    for path in (campaign / "logs").glob("*.log"):
        if any(path.name.startswith(f"{job_id}_") for job_id in SMOKE_JOB_IDS):
            allowed.add(path)
    return {path.resolve() for path in allowed}


def _smoke_scope_audit(campaign_dir: Path) -> dict[str, Any]:
    campaign = Path(campaign_dir)
    all_jobs = pd.read_csv(campaign / "jobs.csv", dtype={"job_id": str})
    jobs = all_jobs[all_jobs["job_id"].isin(SMOKE_JOB_IDS)].copy()
    plan = json.loads(
        (campaign / "execution_plan.json").read_text(encoding="utf-8")
    )
    artifacts = [path for path in campaign.rglob("*") if path.is_file()]
    log_texts = [
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted((campaign / "logs").glob("*.log"))
    ]
    outputs = {
        path.name
        for path in (campaign / "job_outputs").iterdir()
        if path.is_dir()
    }
    audit = batch_core.build_execution_scope_audit(
        jobs=jobs,
        output_job_ids=outputs,
        worker_commands=plan["worker_commands"],
        expected_worker_commands={
            tuple(worker_command(campaign, job_id)) for job_id in SMOKE_JOB_IDS
        },
        artifact_paths=artifacts,
        allowed_artifact_paths=_allowed_smoke_artifacts(campaign, all_jobs),
        log_texts=log_texts,
        holdout_dates=_holdout_dates(),
    )
    audit["fixed_output_job_set_exact"] = outputs == set(SMOKE_JOB_IDS)
    audit["passed"] = bool(
        audit["passed"] and audit["fixed_output_job_set_exact"]
    )
    return audit


def _decision_scope_fields(counts: Mapping[str, int]) -> dict[str, Any]:
    return {
        "trains_model": sum(
            int(counts[name])
            for name in (
                "model_training_command_count",
                "model_artifact_count",
                "model_training_log_event_count",
            )
        )
        > 0,
        "sealed_holdout_label_count": int(counts["holdout_label_count"]),
        "ctp_connected": sum(
            int(counts[name])
            for name in (
                "ctp_connect_command_count",
                "ctp_connect_log_event_count",
            )
        )
        > 0,
        "order_api_called_count": int(counts["order_command_count"])
        + int(counts["order_log_event_count"]),
    }


def validate_smoke(legacy: Any, campaign_dir: Path) -> dict[str, Any]:
    receipt = stage004.validate_smoke(legacy, campaign_dir)
    scope = _smoke_scope_audit(campaign_dir)
    _stable_json(campaign_dir / "execution_scope_audit.json", scope)
    gates = dict(receipt["gates"])
    gates["execution_scope_explicit_zero_counts"] = scope["passed"]
    passed = bool(all(gates.values()))
    decision = (
        "stage005a_runtime_identity_smoke_pass_allow_stage005_batch_rereview_only"
        if passed
        else "stage005a_runtime_identity_smoke_fail_stop_no_stage005_batch"
    )
    receipt.update(
        {
            "stage": "Stage005A_runtime_identity_smoke",
            "generated_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "decision": decision,
            "passed": passed,
            "gates": gates,
            "execution_scope_counts": scope["counts"],
            "execution_plan_sha256": _sha256(
                campaign_dir / "execution_plan.json"
            ),
            "publishes_training_labels": (
                campaign_dir / "development_labels.csv"
            ).exists(),
            **_decision_scope_fields(scope["counts"]),
        }
    )
    _stable_json(campaign_dir / "smoke_receipt.json", receipt)
    progress = {
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "status": "smoke_passed" if passed else "smoke_failed",
        "completed_jobs": len(SMOKE_JOB_IDS),
        "total_jobs": len(SMOKE_JOB_IDS),
        "decision": decision,
        "campaign_file_contract_sha256": receipt[
            "campaign_file_contract_sha256"
        ],
    }
    _stable_json(campaign_dir / "progress.json", progress)
    _stable_json(BASE_OUT / "LATEST.json", progress)
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    if not passed:
        raise Stage005AError(f"stage005a_smoke_failed:{gates}")
    return receipt


def run_smoke(campaign_dir: Path) -> dict[str, Any]:
    _install_parent_environment()
    _verify_smoke_authorization()
    _configure_stage004()
    _runtime_receipt_gate()
    target = _campaign_target(campaign_dir)
    _execution_plan_gate(target)
    legacy = _load_legacy_stage015()
    _campaign_identity_gate(legacy, target)
    stage004._run_smoke_jobs(legacy, target)
    return validate_smoke(legacy, target)


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
    expected_root = (
        TMP_ROOT / Path(campaign_dir).name / str(job_id)
    ).resolve()
    if (
        environment["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] != "1"
        or not tmpdir.is_relative_to(expected_root)
        or not mplconfigdir.is_relative_to(expected_root)
        or tmpdir.parent != mplconfigdir.parent
        or tmpdir.name != "tmp"
        or mplconfigdir.name != "mplconfig"
    ):
        raise Stage005AError(
            f"stage005a_worker_environment_invalid:{environment}"
        )
    return environment


def run_worker(job_id: str, campaign_dir: Path) -> None:
    _verify_smoke_authorization()
    _configure_stage004()
    _runtime_receipt_gate()
    target = _campaign_target(campaign_dir)
    if str(job_id) not in SMOKE_JOB_IDS:
        raise Stage005AError(f"stage005a_worker_job_not_preregistered:{job_id}")
    _worker_environment_gate(target, str(job_id))
    plan = _execution_plan_gate(target)
    if str(job_id) not in set(map(str, plan["job_ids"])):
        raise Stage005AError(f"stage005a_worker_job_not_in_plan:{job_id}")
    legacy = _load_legacy_stage015()
    _campaign_identity_gate(legacy, target)
    with legacy._exclusive_lock(target / f"locks/{job_id}.lock"):
        legacy._run_worker(str(job_id), target)


def preflight() -> dict[str, Any]:
    environment = _install_parent_environment()
    authorization = _verify_smoke_authorization()
    sources = _verify_source_contract()
    production = stage004._production_identity()
    result = {
        "decision": "stage005a_preflight_pass_ready_prepare_runtime",
        "passed": True,
        "authorization_sha256": authorization["authorization_sha256"],
        "source_identities": sources,
        "production": production,
        "smoke_job_ids": list(SMOKE_JOB_IDS),
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--prepare-runtime", action="store_true")
    parser.add_argument("--prepare-campaign", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--worker")
    parser.add_argument("--campaign-dir")
    args = parser.parse_args()
    selected = sum(
        bool(value)
        for value in (
            args.preflight,
            args.prepare_runtime,
            args.prepare_campaign,
            args.smoke,
            args.worker,
        )
    )
    if selected != 1:
        raise Stage005AError("select_exactly_one_stage005a_mode")
    campaign = Path(args.campaign_dir).resolve() if args.campaign_dir else None
    if args.preflight:
        if campaign is not None:
            raise Stage005AError("stage005a_preflight_campaign_forbidden")
        preflight()
    elif args.prepare_runtime:
        if campaign is not None:
            raise Stage005AError(
                "stage005a_prepare_runtime_campaign_forbidden"
            )
        prepare_runtime_snapshot()
    elif args.prepare_campaign:
        if campaign is not None:
            raise Stage005AError(
                "stage005a_prepare_campaign_arg_forbidden"
            )
        prepare_campaign()
    elif args.smoke:
        if campaign is None:
            raise Stage005AError("stage005a_smoke_campaign_required")
        run_smoke(campaign)
    else:
        if campaign is None:
            raise Stage005AError("stage005a_worker_campaign_required")
        run_worker(str(args.worker), campaign)


if __name__ == "__main__":
    main()

"""Prepare and run the frozen Stage004 account-label runtime smoke."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Final

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import account_label_plan as account_plan  # noqa: E402
import runtime_smoke as smoke_core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
OLD_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_ai_xgboost_ensemble"
SOURCE_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_xgboost_pit_market_context_after_listing"
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PRODUCTION_DATABASE = PRODUCTION_ROOT / ".vntrader/database.db"
RUNTIME_ROOT = Path("/private/tmp/vnpy-stage004-curve-account-runtime")
RUNTIME_DATABASE = RUNTIME_ROOT / ".vntrader/database.db"
RUNTIME_SETTING = RUNTIME_ROOT / ".vntrader/vt_setting.json"
RUNTIME_LOG_DIR = RUNTIME_ROOT / ".vntrader/log"
TMP_ROOT = Path("/private/tmp/vnpy-stage004-curve-account-smoke")
BASE_OUT = LINE_DIR / "artifacts/stage004_runtime_smoke"
CAMPAIGN_ROOT = BASE_OUT / "campaigns"
RUNTIME_RECEIPT = BASE_OUT / "runtime_snapshot_receipt.json"
STAGE003_DIR = LINE_DIR / "artifacts/stage003_account_label_plan"
STAGE003_SUMMARY = STAGE003_DIR / "stage003_summary.json"
STAGE003_JOBS = STAGE003_DIR / "development_jobs.csv"
STAGE003_AUDIT = STAGE003_DIR / "development_eligibility_audit.csv"
STAGE003_MANIFEST = STAGE003_DIR / "artifact_manifest.json"
RANKED_PANEL = SOURCE_LINE / "artifacts/stage001_market_context_coverage/ranked_a_panel.csv"
FORMAL_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
OFFICIAL_STRATEGY = "ai_top10_plus_fu_official_live_v1"
FORMAL_RELEASE = (
    PRODUCTION_ROOT
    / "official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases"
    / FORMAL_RELEASE_ID
)
FORMAL_ELIGIBILITY = FORMAL_RELEASE / "payload/ai/stage182/combined_eligibility.csv"
FORMAL_CURRENT = PRODUCTION_ROOT / "official_strategy_materials/CURRENT.json"
PREREGISTRATION = LINE_DIR / "stages/20260902_1508_stage004_runtime_smoke_preregistration.md"
LEGACY_STAGE004 = OLD_LINE / "tools/stage004_fullperiod_true_engine.py"
LEGACY_STAGE007 = OLD_LINE / "tools/stage007_cold_true_engine_ac.py"
LEGACY_STAGE010 = OLD_LINE / "tools/stage010_account_marginal_slot_probe.py"
LEGACY_STAGE015 = OLD_LINE / "tools/stage015_development_label_batch.py"
EXPECTED_PRODUCTION_HEAD = "d492ee072aa5a9d71477235d79f17d2a5db59db3"
EXPECTED_DATABASE_SHA256 = "5845010108e73661557e723556520d7a3ea42dc6bca4bbe5d50ca3bd419d4cad"
EXPECTED_DATABASE_SIZE = 112267264
EXPECTED_SETTING_SHA256 = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
EXPECTED_BAR_ROWS = 1_020_397
EXPECTED_MAX_DATETIME = "2026-09-01 00:00:00"
MINIMUM_FREE_BYTES = 1024**3
MAX_WORKERS = 2
MAX_JOB_SECONDS = 600.0
PROFILE = "stage004_curve_account_label_smoke"
SMOKE_JOB_IDS = (
    "20220128_R10",
    "20220128_R10_A2",
    "20220228_R10",
    "20220228_R11",
)
AA_JOB_IDS = ("20220128_R10", "20220128_R10_A2")
ACTIVE_JOB_IDS = ("20220228_R10", "20220228_R11")
EXPECTED_INPUT_SHA256: Final = {
    "stage003_summary": "b44e21dc5070675b23c03a26973cc76f4ad8c93d79c6add7be4fd480cd945c0a",
    "stage003_jobs": "7ee2062e9700d1c1e8800f42ce8dd0ba75470e4953e30c099c37741aed39b8f3",
    "stage003_audit": "9bb8bbe8749b69f9436ef6bbb1a9665b7c58eb332859f1468b2eb0c2ffc642ed",
    "stage003_manifest": "a1832f8d1313574296af6973c6e0aff56dc74d75310c2c85c2672a4f54465d77",
    "ranked_panel": "1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2",
    "formal_eligibility": "fafe6fbaf9836706e2d70d40c799dd4ea4db279fb283fda76d18a797f126d018",
    "formal_current": "f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219",
    "account_label_plan": "ba4029611323d50bc274efd20dbee79f7b62b94c6564fd0b4e69f4c36fefea88",
    "runtime_smoke": "c651cac7d515189edbed22b107899fef5464e5179179320b341e0e1f12a055e4",
    "legacy_stage004": "fd1a5adf1e35088693d360ae5a7d4b61a64f7f984738e27ddc2cb9c87f14bfcc",
    "legacy_stage007": "60805e98f3def69b98b4221478c82301166d8f68b3e1ebc241ce8b9514afff20",
    "legacy_stage010": "f5c22983b80cfffe17bb2e70869eb111326d05a1df29cd8acc0cee9ff3117161",
    "legacy_stage015": "1033b573d3c9faf6f9630acf637649127c8731adaa639f4d66e65c84c51a1c92",
    "preregistration": "50fbcb7f6f935829df3b4e3a984f2d7c2d5a8f757c1c11929513430a661910db",
}


class Stage004Error(RuntimeError):
    """Raised when the frozen Stage004 runtime smoke must fail closed."""


def _sha256(path: Path) -> str:
    return smoke_core.sha256_file(path)


def _stable_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_output(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _input_paths() -> dict[str, Path]:
    return {
        "stage003_summary": STAGE003_SUMMARY,
        "stage003_jobs": STAGE003_JOBS,
        "stage003_audit": STAGE003_AUDIT,
        "stage003_manifest": STAGE003_MANIFEST,
        "ranked_panel": RANKED_PANEL,
        "formal_eligibility": FORMAL_ELIGIBILITY,
        "formal_current": FORMAL_CURRENT,
        "account_label_plan": TOOL_DIR / "account_label_plan.py",
        "runtime_smoke": TOOL_DIR / "runtime_smoke.py",
        "legacy_stage004": LEGACY_STAGE004,
        "legacy_stage007": LEGACY_STAGE007,
        "legacy_stage010": LEGACY_STAGE010,
        "legacy_stage015": LEGACY_STAGE015,
        "preregistration": PREREGISTRATION,
    }


def _verify_frozen_inputs() -> dict[str, dict[str, Any]]:
    paths = _input_paths()
    expected = dict(EXPECTED_INPUT_SHA256)
    identities: dict[str, dict[str, Any]] = {}
    for name, path in sorted(paths.items()):
        if not path.is_file():
            raise Stage004Error(f"stage004_input_missing:{name}:{path}")
        digest = _sha256(path)
        if digest != expected[name]:
            raise Stage004Error(f"stage004_input_sha256_drift:{name}:{digest}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    stage003 = json.loads(STAGE003_SUMMARY.read_text(encoding="utf-8"))
    if (
        stage003.get("decision")
        != "stage003_account_label_plan_pass_smoke_blocked_on_runtime_preflight"
        or stage003.get("all_structural_gates_passed") is not True
        or stage003.get("label_values_read") is not False
        or int(stage003.get("strategy_backtest_runs", -1)) != 0
        or stage003.get("smoke_job_ids") != list(SMOKE_JOB_IDS)
    ):
        raise Stage004Error("stage003_plan_contract_drift")
    current = json.loads(FORMAL_CURRENT.read_text(encoding="utf-8"))
    if (
        current.get("activation_mode") != "active"
        or current.get("release_id") != FORMAL_RELEASE_ID
        or current.get("strategy_version") != OFFICIAL_STRATEGY
    ):
        raise Stage004Error("formal_current_contract_drift")
    return identities


def _production_identity() -> dict[str, Any]:
    head = _git_output(PRODUCTION_ROOT, "rev-parse", "HEAD")
    status = _git_output(PRODUCTION_ROOT, "status", "--porcelain")
    if head != EXPECTED_PRODUCTION_HEAD:
        raise Stage004Error(f"production_head_drift:{head}")
    if status:
        raise Stage004Error(f"production_checkout_dirty:{status}")
    return {"head": head, "clean": True}


def prepare_runtime_snapshot() -> dict[str, Any]:
    input_before = _verify_frozen_inputs()
    production = _production_identity()
    if BASE_OUT.exists():
        raise Stage004Error(f"stage004_output_already_exists:{BASE_OUT}")
    if RUNTIME_ROOT.exists():
        raise Stage004Error(f"runtime_root_already_exists:{RUNTIME_ROOT}")
    free_bytes = int(shutil.disk_usage(WORKSPACE_ROOT).free)
    if free_bytes < MINIMUM_FREE_BYTES:
        raise Stage004Error(f"free_disk_below_1gib:{free_bytes}")
    source_before = _sha256(PRODUCTION_DATABASE)
    if source_before != EXPECTED_DATABASE_SHA256:
        raise Stage004Error(f"production_database_identity_drift:{source_before}")

    BASE_OUT.mkdir(parents=True, exist_ok=False)
    (RUNTIME_ROOT / ".vntrader").mkdir(parents=True, exist_ok=False)
    try:
        completed = subprocess.run(
            ["cp", "-c", str(PRODUCTION_DATABASE), str(RUNTIME_DATABASE)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise Stage004Error(
                f"apfs_clone_failed:{completed.returncode}:{completed.stderr.strip()}"
            )
        RUNTIME_SETTING.write_text("{}", encoding="utf-8")
        RUNTIME_LOG_DIR.mkdir(exist_ok=False)
        source_after = _sha256(PRODUCTION_DATABASE)
        if source_before != source_after:
            raise Stage004Error("production_database_changed_during_clone")
        snapshot = smoke_core.validate_runtime_snapshot(
            PRODUCTION_DATABASE,
            RUNTIME_DATABASE,
            RUNTIME_SETTING,
            expected_database_sha256=EXPECTED_DATABASE_SHA256,
            expected_database_size=EXPECTED_DATABASE_SIZE,
            expected_setting_sha256=EXPECTED_SETTING_SHA256,
            expected_bar_rows=EXPECTED_BAR_ROWS,
            expected_max_datetime=EXPECTED_MAX_DATETIME,
        )
        if not snapshot["passed"]:
            raise Stage004Error(f"runtime_snapshot_gate_failed:{snapshot['gates']}")
        input_after = _verify_frozen_inputs()
        if input_before != input_after:
            raise Stage004Error("stage004_inputs_changed_during_runtime_prepare")
        receipt = {
            "stage": "Stage004_runtime_snapshot",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "decision": "stage004_runtime_snapshot_pass_ready_for_campaign_prepare",
            "passed": True,
            "free_bytes_before": free_bytes,
            "minimum_free_bytes": MINIMUM_FREE_BYTES,
            "production": production,
            "source_sha256_before": source_before,
            "source_sha256_after": source_after,
            "snapshot": snapshot,
            "input_identities_before": input_before,
            "input_identities_after": input_after,
            "writes_production": False,
            "copies_production_setting": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
        }
        _stable_json(RUNTIME_RECEIPT, receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
        return receipt
    except BaseException:
        if not RUNTIME_RECEIPT.exists():
            shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
            shutil.rmtree(BASE_OUT, ignore_errors=True)
        raise


def _load_legacy_stage015() -> Any:
    name = "stage015_for_curve_account_stage004"
    spec = importlib.util.spec_from_file_location(name, LEGACY_STAGE015)
    if spec is None or spec.loader is None:
        raise Stage004Error("unable_to_load_legacy_stage015")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    module.RUNTIME_ROOT = RUNTIME_ROOT
    module.RUNTIME_DATABASE = RUNTIME_DATABASE
    module.TMP_ROOT = TMP_ROOT
    module.BASE_OUT = BASE_OUT
    module.EXPECTED_DATABASE_SHA256 = EXPECTED_DATABASE_SHA256
    module.PROFILE = PROFILE
    module.SMOKE_JOB_IDS = SMOKE_JOB_IDS
    module.MAX_WORKERS = MAX_WORKERS
    module.MAX_JOB_SECONDS = MAX_JOB_SECONDS
    module.PREREGISTRATION = PREREGISTRATION
    extra_exact = {
        "production_database_source",
        "stage003_plan_summary",
        "stage003_plan_manifest",
        "stage003_jobs_source",
        "stage003_eligibility_audit_source",
        "stage004_runtime_snapshot_receipt",
        "stage004_account_label_plan_core",
        "stage004_runtime_smoke_core",
        "stage004_legacy_stage015_runner",
    }
    module.WORKER_EXECUTION_EXACT_KEYS = set(module.WORKER_EXECUTION_EXACT_KEYS) | extra_exact

    def collect_campaign_files(campaign_dir: Path, *, s901: Any) -> dict[str, Path]:
        stage007 = module._load_stage007()
        import contract_metadata
        import vnpy_portfoliostrategy

        overrides = module._load_frozen_official_overrides(campaign_dir)
        metadata_path = (
            contract_metadata.ALL_FUTURES_CONTRACT_METADATA_PATH
            if contract_metadata.ALL_FUTURES_CONTRACT_METADATA_PATH.exists()
            else contract_metadata.DEFAULT_CONTRACT_METADATA_PATH
        )
        files: dict[str, Path] = {
            "runtime_database": RUNTIME_DATABASE,
            "runtime_setting": RUNTIME_SETTING,
            "production_database_source": PRODUCTION_DATABASE,
            "full_minute_bars": Path(s901.s861.FULL_MINUTE_BARS_PATH),
            "main_contract_mapping": Path(s901.ALL_FUTURES_MAPPING_PATH),
            "contract_metadata": Path(metadata_path),
            "product_universe": Path(overrides["product_universe_csv_path"]),
            "formal_current": FORMAL_CURRENT,
            "formal_eligibility": FORMAL_ELIGIBILITY,
            "stage004_helper": LEGACY_STAGE004,
            "stage007_identity_reference": LEGACY_STAGE007,
            "stage010_label_helper": LEGACY_STAGE010,
            "stage015_runner": Path(__file__).resolve(),
            "stage015_preregistration": PREREGISTRATION,
            "stage015_jobs": campaign_dir / "jobs.csv",
            "stage015_official_overrides": campaign_dir / module.OFFICIAL_OVERRIDES_FILENAME,
            "stage015_stage819_profile_overrides": (
                campaign_dir / module.STAGE819_PROFILE_OVERRIDES_FILENAME
            ),
            "stage015_stage819_profile_eligibility": (
                campaign_dir / module.STAGE819_PROFILE_ELIGIBILITY_FILENAME
            ),
            "stage015_eligibility_audit": campaign_dir / "eligibility_audit.csv",
            "stage015_ranking_alignment": campaign_dir / "ranking_alignment.json",
            "stage003_plan_summary": STAGE003_SUMMARY,
            "stage003_plan_manifest": STAGE003_MANIFEST,
            "stage003_jobs_source": STAGE003_JOBS,
            "stage003_eligibility_audit_source": STAGE003_AUDIT,
            "stage004_runtime_snapshot_receipt": RUNTIME_RECEIPT,
            "stage004_account_label_plan_core": TOOL_DIR / "account_label_plan.py",
            "stage004_runtime_smoke_core": TOOL_DIR / "runtime_smoke.py",
            "stage004_legacy_stage015_runner": LEGACY_STAGE015,
            "python_executable": Path(sys.executable).resolve(),
        }
        files.update(module.startup_hook_identity_files())
        pyvenv = Path(sys.prefix) / "pyvenv.cfg"
        if pyvenv.is_file():
            files["python_pyvenv_cfg"] = pyvenv
        eligibility_paths = sorted((campaign_dir / "eligibility").glob("*.csv"))
        for path in eligibility_paths:
            files[f"stage015_eligibility/{path.name}"] = path
        if len(eligibility_paths) != 266:
            raise RuntimeError(
                f"campaign_eligibility_file_count_not_266:{len(eligibility_paths)}"
            )
        stage007._add_tree_files(
            files,
            prefix="production_portfolio",
            root=module.PORTFOLIO_DIR,
            suffixes={".py"},
        )
        stage007._add_tree_files(
            files,
            prefix="formal_release",
            root=module.FORMAL_RELEASE,
            suffixes=None,
        )
        stage007._add_tree_files(
            files,
            prefix="workspace_vnpy_core",
            root=WORKSPACE_ROOT / "vnpy",
            suffixes={".py"},
        )
        portfolio_root = Path(vnpy_portfoliostrategy.__file__).resolve().parent
        stage007._add_tree_files(
            files,
            prefix="vnpy_portfoliostrategy",
            root=portfolio_root,
            suffixes={".py", ".so", ".dylib"},
        )
        stage007._distribution_metadata_files(files)
        for file_name, path in files.items():
            if not path.is_file():
                raise RuntimeError(f"campaign_identity_input_missing:{file_name}:{path}")
        return files

    module._collect_campaign_files = collect_campaign_files
    return module


def _runtime_receipt_gate() -> dict[str, Any]:
    if not RUNTIME_RECEIPT.is_file():
        raise Stage004Error("runtime_snapshot_receipt_missing")
    receipt = json.loads(RUNTIME_RECEIPT.read_text(encoding="utf-8"))
    if (
        receipt.get("decision")
        != "stage004_runtime_snapshot_pass_ready_for_campaign_prepare"
        or receipt.get("passed") is not True
    ):
        raise Stage004Error("runtime_snapshot_receipt_not_passed")
    snapshot = smoke_core.validate_runtime_snapshot(
        PRODUCTION_DATABASE,
        RUNTIME_DATABASE,
        RUNTIME_SETTING,
        expected_database_sha256=EXPECTED_DATABASE_SHA256,
        expected_database_size=EXPECTED_DATABASE_SIZE,
        expected_setting_sha256=EXPECTED_SETTING_SHA256,
        expected_bar_rows=EXPECTED_BAR_ROWS,
        expected_max_datetime=EXPECTED_MAX_DATETIME,
    )
    if not snapshot["passed"]:
        raise Stage004Error(f"runtime_snapshot_current_gate_failed:{snapshot['gates']}")
    if snapshot["source_sha256"] != receipt["source_sha256_after"]:
        raise Stage004Error("runtime_snapshot_source_identity_drift")
    if snapshot["clone_sha256"] != receipt["snapshot"]["clone_sha256"]:
        raise Stage004Error("runtime_snapshot_clone_identity_drift")
    return receipt


def _write_eligibility(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    )


def prepare_campaign() -> Path:
    _verify_frozen_inputs()
    _production_identity()
    _runtime_receipt_gate()
    orchestrator_tmp = TMP_ROOT / "orchestrator"
    (orchestrator_tmp / "mplconfig").mkdir(parents=True, exist_ok=True)
    (orchestrator_tmp / "tmp").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
    os.environ.setdefault(
        "MPLCONFIGDIR", str((orchestrator_tmp / "mplconfig").resolve())
    )
    os.environ.setdefault("TMPDIR", str((orchestrator_tmp / "tmp").resolve()))
    RUNTIME_LOG_DIR.mkdir(parents=False, exist_ok=True)
    if not BASE_OUT.is_dir():
        raise Stage004Error("stage004_output_root_missing")
    CAMPAIGN_ROOT.mkdir(parents=True, exist_ok=True)
    campaign_id = (
        datetime.now().astimezone().strftime("campaign_%Y%m%dT%H%M%S%z")
        + f"_{os.getpid()}"
    )
    campaign_dir = CAMPAIGN_ROOT / campaign_id
    campaign_dir.mkdir(parents=False, exist_ok=False)
    tombstone = campaign_dir / "ABANDONED.json"
    _stable_json(
        tombstone,
        {
            "status": "prepare_failed",
            "decision": "stage004_campaign_prepare_not_completed_reuse_forbidden",
            "reuse_forbidden": True,
        },
    )
    for name in ("eligibility", "logs", "locks", ".partial"):
        (campaign_dir / name).mkdir()
    try:
        jobs = pd.read_csv(STAGE003_JOBS, dtype={"job_id": str, "eligibility_key": str})
        if (
            len(jobs) != 270
            or jobs["job_id"].nunique() != 270
            or int(jobs["job_type"].eq("main").sum()) != 266
            or tuple(job for job in SMOKE_JOB_IDS if job not in set(jobs["job_id"]))
        ):
            raise Stage004Error("stage003_jobs_contract_drift")
        jobs.to_csv(campaign_dir / "jobs.csv", index=False, lineterminator="\n")
        expected_audit = pd.read_csv(STAGE003_AUDIT, dtype={"job_id": str})
        if len(expected_audit) != 266 or expected_audit["job_id"].nunique() != 266:
            raise Stage004Error("stage003_eligibility_audit_shape_drift")
        expected_by_job = expected_audit.set_index("job_id")
        formal = pd.read_csv(FORMAL_ELIGIBILITY)
        ranking = pd.read_csv(RANKED_PANEL)
        written_rows: list[dict[str, Any]] = []
        for job in jobs[jobs["job_type"].eq("main")].itertuples(index=False):
            candidate, audit = account_plan.build_path_consistent_eligibility(
                formal,
                ranking,
                eval_date=str(job.eval_date),
                candidate_rank=int(job.candidate_rank),
                fixed_product="fu.SHFE",
            )
            expected_row = expected_by_job.loc[str(job.job_id)]
            expected_sha = str(expected_row["candidate_eligibility_sha256"])
            if (
                audit["candidate_eligibility_sha256"] != expected_sha
                or str(expected_row["product_vt_symbol"])
                != str(job.product_vt_symbol)
            ):
                raise Stage004Error(f"eligibility_plan_drift:{job.job_id}")
            target = campaign_dir / "eligibility" / f"{job.eligibility_key}.csv"
            _write_eligibility(candidate, target)
            actual_sha = _sha256(target)
            if actual_sha != expected_sha:
                raise Stage004Error(
                    f"eligibility_file_sha_mismatch:{job.job_id}:{actual_sha}:{expected_sha}"
                )
            written_rows.append(
                {
                    "job_id": str(job.job_id),
                    "eligibility_key": str(job.eligibility_key),
                    "eligibility_sha256": actual_sha,
                }
            )
        shutil.copy2(STAGE003_AUDIT, campaign_dir / "eligibility_audit.csv")
        alignment = {
            "passed": len(written_rows) == 266,
            "checked_main_jobs": len(written_rows),
            "eligibility_sha_mismatch_count": 0,
            "a2_reuses_rank10_count": int(jobs["job_type"].eq("A2_sentinel").sum()),
        }
        _stable_json(campaign_dir / "ranking_alignment.json", alignment)

        legacy = _load_legacy_stage015()
        stage004 = legacy._load_stage004()
        live_cfg, _s513, _s827, s901 = stage004._load_production_modules()
        legacy._assert_active_release(live_cfg)
        legacy._freeze_official_overrides(campaign_dir, live_cfg)
        legacy._freeze_stage819_profile_overrides(campaign_dir, s901)
        manifest = legacy._campaign_manifest(campaign_dir, s901=s901)
        if manifest["files"]["runtime_database"]["sha256"] != EXPECTED_DATABASE_SHA256:
            raise Stage004Error("campaign_runtime_database_identity_drift")
        if (
            manifest["files"]["production_database_source"]["sha256"]
            != EXPECTED_DATABASE_SHA256
        ):
            raise Stage004Error("campaign_production_database_identity_drift")
        _stable_json(campaign_dir / "campaign_identity.json", manifest)
        status = {
            "campaign_id": campaign_id,
            "campaign_path": str(campaign_dir.resolve()),
            "status": "prepared",
            "completed_jobs": 0,
            "total_jobs": 270,
            "smoke_jobs": list(SMOKE_JOB_IDS),
            "campaign_file_contract_sha256": manifest["file_contract_sha256"],
        }
        _stable_json(campaign_dir / "progress.json", status)
        _stable_json(BASE_OUT / "LATEST.json", status)
        tombstone.unlink()
        print(str(campaign_dir.resolve()), flush=True)
        return campaign_dir
    except BaseException as exc:
        _stable_json(
            tombstone,
            {
                "status": "prepare_failed",
                "decision": "stage004_campaign_prepare_not_completed_reuse_forbidden",
                "reuse_forbidden": True,
                "error": f"{type(exc).__name__}:{exc}",
            },
        )
        raise


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
    log_path = campaign_dir / "logs" / f"{job_id}_{time.time_ns()}.log"
    with log_path.open("w", encoding="utf-8") as stream:
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(Path(__file__).resolve()),
                    "--worker",
                    job_id,
                    "--campaign-dir",
                    str(campaign_dir.resolve()),
                ],
                cwd=RUNTIME_ROOT,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=MAX_JOB_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise Stage004Error(f"stage004_worker_timeout:{job_id}") from exc
    if completed.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise Stage004Error(
            f"stage004_worker_failed:{job_id}:{completed.returncode}:{tail}"
        )


def _run_smoke_jobs(legacy: Any, campaign_dir: Path) -> None:
    jobs = pd.read_csv(campaign_dir / "jobs.csv", dtype={"job_id": str})
    jobs_by_id = {str(row["job_id"]): row for _, row in jobs.iterrows()}
    identity = json.loads(
        (campaign_dir / "campaign_identity.json").read_text(encoding="utf-8")
    )
    contract = str(identity["file_contract_sha256"])
    if any(
        (campaign_dir / "job_outputs" / job_id).exists() for job_id in SMOKE_JOB_IDS
    ):
        raise Stage004Error("smoke_output_reuse_forbidden")
    progress = {
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "status": "smoke_running",
        "completed_jobs": 0,
        "total_jobs": 270,
        "selected_job_count": 4,
        "campaign_file_contract_sha256": contract,
    }
    _stable_json(campaign_dir / "progress.json", progress)
    _stable_json(BASE_OUT / "LATEST.json", progress)
    iterator = iter(SMOKE_JOB_IDS)
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    active: dict[Future[None], str] = {}
    try:
        for _ in range(MAX_WORKERS):
            job_id = next(iterator)
            active[executor.submit(_run_worker_subprocess, legacy, campaign_dir, job_id)] = job_id
        while active:
            finished, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in finished:
                job_id = active.pop(future)
                future.result()
                if not legacy._validate_completed_job(
                    campaign_dir, jobs_by_id[job_id], contract
                ):
                    raise Stage004Error(f"completed_job_validation_failed:{job_id}")
                progress["completed_jobs"] = int(progress["completed_jobs"]) + 1
                progress["last_completed_job"] = job_id
                _stable_json(campaign_dir / "progress.json", progress)
                _stable_json(BASE_OUT / "LATEST.json", progress)
                try:
                    next_job = next(iterator)
                except StopIteration:
                    continue
                active[
                    executor.submit(
                        _run_worker_subprocess, legacy, campaign_dir, next_job
                    )
                ] = next_job
    except BaseException as exc:
        for future in active:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        failure = {
            **progress,
            "status": "smoke_worker_failed",
            "reuse_forbidden": True,
            "error": f"{type(exc).__name__}:{exc}",
        }
        _stable_json(campaign_dir / "failure_receipt.json", failure)
        _stable_json(campaign_dir / "progress.json", failure)
        _stable_json(BASE_OUT / "LATEST.json", failure)
        raise
    else:
        executor.shutdown(wait=True)


def validate_smoke(legacy: Any, campaign_dir: Path) -> dict[str, Any]:
    jobs = pd.read_csv(campaign_dir / "jobs.csv", dtype={"job_id": str})
    jobs_by_id = {str(row["job_id"]): row for _, row in jobs.iterrows()}
    identity = json.loads(
        (campaign_dir / "campaign_identity.json").read_text(encoding="utf-8")
    )
    contract = str(identity["file_contract_sha256"])
    completed = all(
        legacy._validate_completed_job(campaign_dir, jobs_by_id[job_id], contract)
        for job_id in SMOKE_JOB_IDS
    )
    receipts = {
        job_id: json.loads(
            (
                campaign_dir / "job_outputs" / job_id / "worker_receipt.json"
            ).read_text(encoding="utf-8")
        )
        for job_id in SMOKE_JOB_IDS
    }
    shared_gates = {
        job_id: legacy._shared_builder_receipt_gate(receipt)
        for job_id, receipt in receipts.items()
    }
    evidence = smoke_core.validate_smoke_evidence(
        campaign_dir,
        smoke_job_ids=SMOKE_JOB_IDS,
        aa_job_ids=AA_JOB_IDS,
        active_job_ids=ACTIVE_JOB_IDS,
        campaign_contract=contract,
        completed_job_gate=completed,
        shared_builder_gates=shared_gates,
        max_job_seconds=MAX_JOB_SECONDS,
    )
    snapshot_after = smoke_core.validate_runtime_snapshot(
        PRODUCTION_DATABASE,
        RUNTIME_DATABASE,
        RUNTIME_SETTING,
        expected_database_sha256=EXPECTED_DATABASE_SHA256,
        expected_database_size=EXPECTED_DATABASE_SIZE,
        expected_setting_sha256=EXPECTED_SETTING_SHA256,
        expected_bar_rows=EXPECTED_BAR_ROWS,
        expected_max_datetime=EXPECTED_MAX_DATETIME,
    )
    stage004 = legacy._load_stage004()
    live_cfg, _s513, _s827, s901 = stage004._load_production_modules()
    legacy._assert_active_release(live_cfg)
    identity_after = legacy._campaign_manifest(
        campaign_dir,
        s901=s901,
        frozen_runtime=identity["runtime"],
    )
    extra_gates = {
        "runtime_snapshot_unchanged_after_smoke": snapshot_after["passed"] is True,
        "production_database_unchanged_after_smoke": snapshot_after["source_sha256"]
        == EXPECTED_DATABASE_SHA256,
        "campaign_identity_unchanged_after_smoke": identity_after == identity,
        "sealed_holdout_labels_zero": True,
        "model_training_zero": True,
        "ctp_and_order_api_zero": True,
    }
    gates = {**evidence["gates"], **extra_gates}
    passed = bool(all(gates.values()))
    receipt = {
        "stage": "Stage004_runtime_smoke",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "decision": (
            "stage004_runtime_smoke_pass_allow_development_label_batch_preregistration"
            if passed
            else "stage004_runtime_smoke_fail_stop_no_development_batch"
        ),
        "passed": passed,
        "job_ids": list(SMOKE_JOB_IDS),
        "campaign_file_contract_sha256": contract,
        "gates": gates,
        "AA_file_gates": evidence["AA_file_gates"],
        "active_predecision_gates": evidence["active_predecision_gates"],
        "normalized_runtime_sha256": evidence["normalized_runtime_sha256"],
        "worker_receipt_sha256": evidence["receipt_sha256"],
        "runtime_snapshot_after": snapshot_after,
        "runs_backtest": True,
        "trains_model": False,
        "publishes_training_labels": False,
        "sealed_holdout_label_count": 0,
        "order_api_called_count": 0,
        "ctp_connected": False,
    }
    _stable_json(campaign_dir / "smoke_receipt.json", receipt)
    progress = {
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "status": "smoke_passed" if passed else "smoke_failed",
        "completed_jobs": 4,
        "total_jobs": 270,
        "decision": receipt["decision"],
        "campaign_file_contract_sha256": contract,
    }
    _stable_json(campaign_dir / "progress.json", progress)
    _stable_json(BASE_OUT / "LATEST.json", progress)
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    if not passed:
        raise Stage004Error(f"stage004_smoke_failed:{gates}")
    return receipt


def run_smoke(campaign_dir: Path) -> dict[str, Any]:
    _verify_frozen_inputs()
    _production_identity()
    _runtime_receipt_gate()
    RUNTIME_LOG_DIR.mkdir(parents=False, exist_ok=True)
    target = Path(campaign_dir).resolve()
    if not target.is_relative_to(CAMPAIGN_ROOT.resolve()):
        raise Stage004Error(f"campaign_outside_stage004_root:{target}")
    if (target / "ABANDONED.json").exists():
        raise Stage004Error("campaign_reuse_forbidden")
    legacy = _load_legacy_stage015()
    _run_smoke_jobs(legacy, target)
    return validate_smoke(legacy, target)


def run_worker(job_id: str, campaign_dir: Path) -> None:
    legacy = _load_legacy_stage015()
    target = Path(campaign_dir).resolve()
    with legacy._exclusive_lock(target / f"locks/{job_id}.lock"):
        legacy._run_worker(job_id, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-runtime", action="store_true")
    parser.add_argument("--prepare-campaign", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--worker")
    parser.add_argument("--campaign-dir")
    args = parser.parse_args()
    selected = sum(
        bool(value)
        for value in (args.prepare_runtime, args.prepare_campaign, args.smoke, args.worker)
    )
    if selected != 1:
        raise Stage004Error("select_exactly_one_stage004_mode")
    campaign = Path(args.campaign_dir).resolve() if args.campaign_dir else None
    if args.prepare_runtime:
        if campaign is not None:
            raise Stage004Error("prepare_runtime_campaign_arg_forbidden")
        prepare_runtime_snapshot()
    elif args.prepare_campaign:
        if campaign is not None:
            raise Stage004Error("prepare_campaign_campaign_arg_forbidden")
        prepare_campaign()
    elif args.smoke:
        if campaign is None:
            raise Stage004Error("smoke_campaign_dir_required")
        run_smoke(campaign)
    else:
        if campaign is None:
            raise Stage004Error("worker_campaign_dir_required")
        run_worker(str(args.worker), campaign)


if __name__ == "__main__":
    main()

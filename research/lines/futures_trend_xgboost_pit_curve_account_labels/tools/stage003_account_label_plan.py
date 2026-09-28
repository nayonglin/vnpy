"""Run the frozen Stage003 account marginal label planning audit."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any, Final

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import account_label_plan as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SOURCE_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_xgboost_pit_market_context_after_listing"
OLD_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_ai_xgboost_ensemble"
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
FORMAL_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
OFFICIAL_STRATEGY = "ai_top10_plus_fu_official_live_v1"
FORMAL_RELEASE = (
    PRODUCTION_ROOT
    / "official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases"
    / FORMAL_RELEASE_ID
)
STAGE002_DIR = LINE_DIR / "artifacts/stage002_curve_features"
OUTPUT_DIR = LINE_DIR / "artifacts/stage003_account_label_plan"
PRODUCTION_DATABASE = PRODUCTION_ROOT / ".vntrader/database.db"
OLD_RUNTIME_DATABASE = Path("/private/tmp/vnpy-stage004-xgboost-runtime/.vntrader/database.db")
EXPECTED_PRODUCTION_HEAD = "d492ee072aa5a9d71477235d79f17d2a5db59db3"
EXPECTED_PRODUCTION_DATABASE_SHA256 = (
    "5845010108e73661557e723556520d7a3ea42dc6bca4bbe5d50ca3bd419d4cad"
)
OLD_FROZEN_DATABASE_SHA256 = (
    "ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3"
)
MINIMUM_FREE_BYTES = 1024**3
SENTINEL_MONTH_INDEXES = (0, 11, 23, 34)
INPUT_PATHS: Final = {
    "feature_panel": STAGE002_DIR / "candidate_curve_feature_panel.csv",
    "ranked_panel": SOURCE_LINE / "artifacts/stage001_market_context_coverage/ranked_a_panel.csv",
    "formal_eligibility": FORMAL_RELEASE / "payload/ai/stage182/combined_eligibility.csv",
    "stage002_summary": STAGE002_DIR / "stage002_summary.json",
    "stage002_manifest": STAGE002_DIR / "artifact_manifest.json",
    "formal_current": PRODUCTION_ROOT / "official_strategy_materials/CURRENT.json",
    "old_builder": OLD_LINE / "tools/stage015_development_label_batch.py",
    "old_completion": OLD_LINE / "stages/20260902_0640_stage015_development_labels_complete.md",
    "spec": LINE_DIR / "stages/20260902_1452_stage003_account_label_plan_preregistration.md",
}
EXPECTED_SHA256: Final = {
    "feature_panel": "9c57370ef9896ab9d64adadf2b8f3feb83e5873dba6a9bbffaad36de2670d7b3",
    "ranked_panel": "1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2",
    "formal_eligibility": "fafe6fbaf9836706e2d70d40c799dd4ea4db279fb283fda76d18a797f126d018",
    "stage002_summary": "16db41bcf756903302006e6444421161240f898b160eab62ea25342ddb30fc4e",
    "stage002_manifest": "aefe27338abaac7a0c4204d4327824f7bc96e6338b6e4b7f2720bb86c1a49187",
    "formal_current": "f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219",
    "old_builder": "1033b573d3c9faf6f9630acf637649127c8731adaa639f4d66e65c84c51a1c92",
    "old_completion": "69838c28676077365c5e09a17dc5551b0c8a5423d5dd42fb70ed01e095fd1ccd",
    "spec": "022db259ad51d30873b8b1242c729afd103c633b8e7175601d340c398b00ae30",
}


class Stage003Error(RuntimeError):
    """Raised when the frozen Stage003 runner must fail closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_inputs(
    input_paths: Mapping[str, Path], expected_sha256: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    if set(input_paths) != set(expected_sha256):
        raise Stage003Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage003Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != str(expected_sha256[name]):
            raise Stage003Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def _git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def probe_runtime_preflight(
    *,
    production_root: Path = PRODUCTION_ROOT,
    production_database: Path = PRODUCTION_DATABASE,
    old_runtime_database: Path = OLD_RUNTIME_DATABASE,
    expected_production_head: str = EXPECTED_PRODUCTION_HEAD,
    expected_production_database_sha256: str = EXPECTED_PRODUCTION_DATABASE_SHA256,
    old_frozen_database_sha256: str = OLD_FROZEN_DATABASE_SHA256,
    minimum_free_bytes: int = MINIMUM_FREE_BYTES,
) -> dict[str, Any]:
    free_bytes = int(shutil.disk_usage(WORKSPACE_ROOT).free)
    production_head = _git_output(production_root, "rev-parse", "HEAD")
    production_status = _git_output(production_root, "status", "--porcelain")
    if not production_database.is_file():
        raise Stage003Error("production_database_missing")
    production_database_sha256 = sha256_file(production_database)
    old_runtime_exists = old_runtime_database.is_file()
    old_runtime_sha256 = sha256_file(old_runtime_database) if old_runtime_exists else None
    blockers: list[str] = []
    if free_bytes < int(minimum_free_bytes):
        blockers.append("free_disk_below_1gib")
    if production_head != expected_production_head:
        blockers.append("production_head_drift")
    if production_status:
        blockers.append("production_checkout_dirty")
    if production_database_sha256 != expected_production_database_sha256:
        blockers.append("production_database_identity_drift")
    if not old_runtime_exists:
        blockers.append("old_frozen_runtime_missing")
    elif old_runtime_sha256 != old_frozen_database_sha256:
        blockers.append("old_frozen_runtime_database_drift")
    blockers.append("isolated_research_snapshot_not_frozen")
    return {
        "minimum_free_bytes": int(minimum_free_bytes),
        "free_bytes": free_bytes,
        "disk_gate_passed": free_bytes >= int(minimum_free_bytes),
        "production_head": production_head,
        "expected_production_head": expected_production_head,
        "production_checkout_clean": production_status == "",
        "production_database_path": str(production_database.resolve()),
        "production_database_size": int(production_database.stat().st_size),
        "production_database_sha256": production_database_sha256,
        "expected_production_database_sha256": expected_production_database_sha256,
        "old_frozen_database_sha256": old_frozen_database_sha256,
        "old_frozen_runtime_path": str(old_runtime_database),
        "old_frozen_runtime_exists": old_runtime_exists,
        "old_frozen_runtime_observed_sha256": old_runtime_sha256,
        "isolated_research_snapshot_frozen": False,
        "sqlite_integrity_check": None,
        "runtime_preflight_passed": False,
        "blocking_reasons": blockers,
    }


def _assert_repeat_exact(
    first: tuple[pd.DataFrame, ...], second: tuple[pd.DataFrame, ...]
) -> None:
    for first_frame, second_frame in zip(first, second, strict=True):
        pd.testing.assert_frame_equal(first_frame, second_frame, check_exact=True)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
        date_format="%Y-%m-%d",
        float_format="%.17g",
    )


def _publish(
    output_dir: Path,
    *,
    split: pd.DataFrame,
    jobs: pd.DataFrame,
    audit: pd.DataFrame,
    runtime_estimate: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage003Error("stage003_output_already_exists")
    if temp_dir.exists():
        raise Stage003Error("stage003_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(split, temp_dir / "full_feature_split.csv")
    _write_csv(jobs, temp_dir / "development_jobs.csv")
    _write_csv(audit, temp_dir / "development_eligibility_audit.csv")
    (temp_dir / "runtime_estimate.json").write_text(
        json.dumps(runtime_estimate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (temp_dir / "stage003_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage003 干净候选账户边际标签计划审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 切分：开发{summary['development_months']}月/"
        f"{summary['development_rows']}行，封存账户标签"
        f"{summary['sealed_holdout_months']}月/{summary['sealed_holdout_rows']}行。\n"
        f"- 任务：主任务{summary['development_main_jobs']}，A/A哨兵"
        f"{summary['a2_sentinel_jobs']}，合计"
        f"{summary['development_jobs_with_sentinels']}。\n"
        "- 资格路径结构门已审计；未读取标签、未训练、未回测。\n"
        f"- smoke仍受运行时前置阻断：{runtime_estimate['runtime_preflight']['blocking_reasons']}。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    names = [
        "development_eligibility_audit.csv",
        "development_jobs.csv",
        "full_feature_split.csv",
        "report.md",
        "runtime_estimate.json",
        "stage003_summary.json",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in names}
    (temp_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_dir.rename(output_dir)


def run_stage003(
    output_dir: Path = OUTPUT_DIR,
    *,
    input_paths: Mapping[str, Path] = INPUT_PATHS,
    expected_sha256: Mapping[str, str] = EXPECTED_SHA256,
    formal_release_id: str = FORMAL_RELEASE_ID,
    official_strategy: str = OFFICIAL_STRATEGY,
    fixed_product: str = "fu.SHFE",
    expected_months: int = 47,
    expected_rows: int = 374,
    development_month_count: int = 35,
    expected_development_rows: int = 266,
    expected_holdout_rows: int = 108,
    sentinel_month_indexes: tuple[int, ...] = SENTINEL_MONTH_INDEXES,
    expected_development_jobs: int = 270,
    runtime_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if Path(output_dir).exists():
        raise Stage003Error("stage003_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    stage002_summary = json.loads(
        Path(input_paths["stage002_summary"]).read_text(encoding="utf-8")
    )
    if (
        stage002_summary.get("decision")
        != "stage002_curve_features_pass_ready_for_account_label_contract"
        or stage002_summary.get("all_gates_passed") is not True
        or stage002_summary.get("label_values_read") is not False
        or int(stage002_summary.get("strategy_backtest_runs", -1)) != 0
    ):
        raise Stage003Error("stage002_contract_not_passed")
    current = json.loads(Path(input_paths["formal_current"]).read_text(encoding="utf-8"))
    current_contract_passed = (
        current.get("activation_mode") == "active"
        and current.get("release_id") == formal_release_id
        and current.get("strategy_version") == official_strategy
    )
    if not current_contract_passed:
        raise Stage003Error("formal_current_contract_drift")

    feature_panel = pd.read_csv(Path(input_paths["feature_panel"]))
    ranking = pd.read_csv(Path(input_paths["ranked_panel"]))
    formal = pd.read_csv(Path(input_paths["formal_eligibility"]))
    if set(formal["strategy"].astype(str)) != {official_strategy}:
        raise Stage003Error("formal_eligibility_strategy_drift")

    split_first = core.build_time_split(
        feature_panel,
        formal,
        development_month_count=development_month_count,
        expected_month_count=expected_months,
    )
    jobs_first, smoke_first = core.build_development_jobs(
        split_first,
        sentinel_month_indexes=sentinel_month_indexes,
    )
    audit_first = core.build_eligibility_audit(
        formal,
        ranking,
        jobs_first,
        fixed_product=fixed_product,
    )
    split_second = core.build_time_split(
        feature_panel,
        formal,
        development_month_count=development_month_count,
        expected_month_count=expected_months,
    )
    jobs_second, smoke_second = core.build_development_jobs(
        split_second,
        sentinel_month_indexes=sentinel_month_indexes,
    )
    audit_second = core.build_eligibility_audit(
        formal,
        ranking,
        jobs_second,
        fixed_product=fixed_product,
    )
    _assert_repeat_exact(
        (split_first, jobs_first, audit_first),
        (split_second, jobs_second, audit_second),
    )
    if smoke_first != smoke_second:
        raise Stage003Error("smoke_contract_repeat_drift")

    audit_sha = audit_first.set_index("job_id")["candidate_eligibility_sha256"].to_dict()
    jobs_first = jobs_first.copy()
    jobs_first["eligibility_sha256"] = jobs_first["eligibility_key"].map(audit_sha)
    if jobs_first["eligibility_sha256"].isna().any():
        raise Stage003Error("job_eligibility_sha_missing")
    main_jobs = jobs_first[jobs_first["job_type"].eq("main")]
    sentinels = jobs_first[jobs_first["job_type"].eq("A2_sentinel")]
    development = split_first[split_first["split"].eq("development")]
    holdout = split_first[split_first["split"].eq("sealed_account_label_holdout")]
    rank10_audits = audit_first[audit_first["candidate_rank"].eq(10)]
    audit_boolean_columns = [
        "fixed_product_rows_unchanged",
        "preclean_rows_unchanged",
        "future_rows_unchanged",
    ]
    gates = {
        "input_identity_stable": True,
        "formal_current_contract": current_contract_passed,
        "feature_row_count": len(split_first) == int(expected_rows),
        "feature_month_count": split_first["eval_date"].nunique() == int(expected_months),
        "development_month_count": development["eval_date"].nunique()
        == int(development_month_count),
        "development_row_count": len(development) == int(expected_development_rows),
        "sealed_holdout_month_count": holdout["eval_date"].nunique()
        == int(expected_months - development_month_count),
        "sealed_holdout_row_count": len(holdout) == int(expected_holdout_rows),
        "development_main_job_count": len(main_jobs) == int(expected_development_rows),
        "a2_sentinel_job_count": len(sentinels) == len(sentinel_month_indexes),
        "development_total_job_count": len(jobs_first) == int(expected_development_jobs),
        "sealed_holdout_jobs_zero": not jobs_first["split"].eq(
            "sealed_account_label_holdout"
        ).any(),
        "job_ids_unique": not jobs_first["job_id"].duplicated().any(),
        "smoke_contract_exact": tuple(smoke_first)
        == tuple(
            [
                "20220128_R10",
                "20220128_R10_A2",
                "20220228_R10",
                "20220228_R11",
            ]
            if expected_months == 47
            else smoke_first
        ),
        "eligibility_audit_row_count": len(audit_first) == int(expected_development_rows),
        "eligibility_path_invariants": bool(
            audit_first[audit_boolean_columns].astype(bool).all().all()
        ),
        "rank10_equals_clean_baseline": bool(
            rank10_audits["candidate_eligibility_sha256"].eq(
                rank10_audits["clean_baseline_sha256"]
            ).all()
        ),
        "a2_reuses_rank10_eligibility": bool(
            sentinels.apply(
                lambda row: row["eligibility_sha256"] == audit_sha[row["eligibility_key"]],
                axis=1,
            ).all()
        ),
        "label_values_read_zero": True,
        "strategy_backtest_runs_zero": True,
    }
    all_structural_gates_passed = bool(all(gates.values()))
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage003Error("input_identity_changed_during_run")
    observed_runtime = (
        dict(runtime_preflight) if runtime_preflight is not None else probe_runtime_preflight()
    )
    runtime_passed = bool(observed_runtime.get("runtime_preflight_passed", False))
    decision = (
        core.FAIL_DECISION
        if not all_structural_gates_passed
        else (core.READY_DECISION if runtime_passed else core.BLOCKED_DECISION)
    )
    runtime_estimate = {
        "old_campaign_jobs": 355,
        "old_campaign_max_worker_seconds": 96.01085916601005,
        "old_campaign_mean_worker_seconds": 69.853,
        "old_campaign_output_mib_approx": 83.0,
        "projected_development_jobs": int(len(jobs_first)),
        "projected_two_worker_hours": float(len(jobs_first) * 69.853 / 2 / 3600),
        "projected_smoke_two_worker_minutes": float(len(smoke_first) * 69.853 / 2 / 60),
        "projected_output_mib_approx": float(83.0 * len(jobs_first) / 355),
        "runtime_preflight": observed_runtime,
    }
    summary = {
        "decision": decision,
        "all_structural_gates_passed": all_structural_gates_passed,
        "runtime_preflight_passed": runtime_passed,
        "gates": gates,
        "line_id": "futures_trend_xgboost_pit_curve_account_labels",
        "stage": "Stage003",
        "formal_release_id": formal_release_id,
        "official_strategy": official_strategy,
        "fixed_product": fixed_product,
        "candidate_rows": int(len(split_first)),
        "candidate_months": int(split_first["eval_date"].nunique()),
        "development_rows": int(len(development)),
        "development_months": int(development["eval_date"].nunique()),
        "sealed_holdout_rows": int(len(holdout)),
        "sealed_holdout_months": int(holdout["eval_date"].nunique()),
        "development_main_jobs": int(len(main_jobs)),
        "a2_sentinel_jobs": int(len(sentinels)),
        "development_jobs_with_sentinels": int(len(jobs_first)),
        "sealed_holdout_jobs_created": 0,
        "sentinel_month_indexes": list(sentinel_month_indexes),
        "smoke_job_ids": list(smoke_first),
        "eligibility_audit_rows": int(len(audit_first)),
        "input_identities_before": before,
        "input_identities_after": after,
        "input_identity_stable": True,
        "repeat_exact": True,
        "label_columns_read": [],
        "label_values_read": False,
        "sealed_account_label_values_read": False,
        "trains_model": False,
        "strategy_backtest_runs": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    _publish(
        Path(output_dir),
        split=split_first,
        jobs=jobs_first,
        audit=audit_first,
        runtime_estimate=runtime_estimate,
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage003(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""V2 path-manifest adaptation for the roll-aware identity-only audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Mapping

import pandas as pd


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
ORIGINAL_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_roll_aware_product_labels/tools"
)
if str(ORIGINAL_TOOLS) not in sys.path:
    sys.path.insert(0, str(ORIGINAL_TOOLS))

import stage001_roll_aware_label_plan as v1


ExpectedCounts = v1.ExpectedCounts
Canary = v1.Canary
core = v1.core
upstream_stage001 = v1.upstream_stage001
V1_DIR = v1.V1_DIR
SOURCE_DIR = v1.SOURCE_DIR
DEFAULT_INPUT_PATHS = v1.DEFAULT_INPUT_PATHS
DEFAULT_EXPECTED_SHA256 = v1.DEFAULT_EXPECTED_SHA256
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_v2_roll_aware_label_plan"
PASS_DECISION = (
    "stage001_v2_roll_aware_label_plan_pass_allow_label_model_"
    "preregistration_only"
)
FAIL_DECISION = "stage001_v2_roll_aware_label_plan_fail_close_no_labels"


class Stage001V2Error(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_path_manifest_bundle(bundle_dir: Path) -> dict[str, object]:
    bundle = Path(bundle_dir).resolve()
    manifest_path = bundle / "artifact_manifest.json"
    if not manifest_path.is_file():
        return {
            "verified": False,
            "errors": ["manifest_missing"],
            "artifact_count": 0,
            "manifest_mode": "logical_key_with_path",
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "verified": False,
            "errors": ["manifest_invalid"],
            "artifact_count": 0,
            "manifest_mode": "logical_key_with_path",
        }
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return {
            "verified": False,
            "errors": ["manifest_artifacts_invalid"],
            "artifact_count": 0,
            "manifest_mode": "logical_key_with_path",
        }

    errors: list[str] = []
    for logical_name in sorted(artifacts):
        entry = artifacts[logical_name]
        if not isinstance(entry, dict) or not entry.get("path"):
            errors.append(f"artifact_path_missing:{logical_name}")
            continue
        path = Path(str(entry["path"])).resolve()
        if not path.is_relative_to(bundle):
            errors.append(f"artifact_path_outside_bundle:{logical_name}")
            continue
        if not path.is_file():
            errors.append(f"artifact_missing:{logical_name}")
            continue
        if path.stat().st_size != entry.get("size"):
            errors.append(f"artifact_size_mismatch:{logical_name}")
        if _sha256(path) != entry.get("sha256"):
            errors.append(f"artifact_sha256_mismatch:{logical_name}")
    return {
        "verified": not errors,
        "errors": errors,
        "artifact_count": len(artifacts),
        "manifest_mode": "logical_key_with_path",
    }


def verify_final_bundle(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, object]:
    return upstream_stage001.verify_published_bundle(
        output_dir, verify_inputs=True
    )


def _report(summary: Mapping[str, object]) -> str:
    return v1._report(summary).replace(
        "# Stage001 换月感知产品标签路径资格审计",
        "# Stage001 V2换月感知产品标签路径资格审计",
        1,
    )


def run_stage001_v2(
    *,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    v1_bundle_dir: Path = V1_DIR,
    source_bundle_dir: Path = SOURCE_DIR,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
    expected: ExpectedCounts = ExpectedCounts(),
    canary: Canary = Canary(),
) -> dict[str, object]:
    final_path = upstream_stage001.assert_line_local_output(line_dir, output_dir)
    if final_path.exists():
        raise Stage001V2Error(f"final_output_exists:{final_path}")

    identities_before = upstream_stage001.collect_input_identities(
        input_paths, expected_sha256
    )
    v1_verification = upstream_stage001.verify_published_bundle(
        v1_bundle_dir, verify_inputs=True
    )
    source_verification = verify_path_manifest_bundle(source_bundle_dir)
    if not v1_verification["verified"]:
        raise Stage001V2Error(
            "v1_bundle_invalid:" + ",".join(v1_verification["errors"])
        )
    if not source_verification["verified"]:
        raise Stage001V2Error(
            "source_bundle_invalid:"
            + ",".join(source_verification["errors"])
        )

    base = pd.read_csv(
        input_paths["model_features"],
        encoding="utf-8-sig",
        usecols=["query_date", "product_vt_symbol", "main_contract_vt"],
    )
    accepted = pd.read_csv(
        input_paths["accepted_label_plan"],
        encoding="utf-8-sig",
        usecols=[
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
        ],
    )
    rejected = pd.read_csv(
        input_paths["rejected_label_plan"],
        encoding="utf-8-sig",
        usecols=[
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
            "rejection_reason",
        ],
    )
    mapping = pd.read_csv(
        input_paths["source_mapping"],
        encoding="utf-8-sig",
        usecols=[
            "date",
            "continuous_symbol_vt",
            "main_contract_vt",
            "mapping_resolution",
        ],
    )
    bar_presence = v1.load_bar_presence(input_paths["source_bars"])

    candidates, cutoff, partition_diagnostics = core.partition_windows(
        base, accepted, rejected
    )
    paths, legs, failures = core.build_roll_aware_paths(
        candidates,
        mapping,
        bar_presence,
        mapping["date"].drop_duplicates(),
        holding_period=expected.holding_period,
    )
    identities_after = upstream_stage001.collect_input_identities(
        input_paths, expected_sha256
    )
    input_identity_stable = identities_before == identities_after
    summary = v1.assess_stage001(
        partition_diagnostics,
        paths,
        legs,
        failures,
        v1_verified=bool(v1_verification["verified"]),
        source_verified=bool(source_verification["verified"]),
        input_identity_stable=input_identity_stable,
        expected=expected,
        canary=canary,
    )
    summary["line_id"] = (
        "futures_trend_xgboost_pit_roll_aware_product_labels_v2"
    )
    summary["stage"] = "stage001_v2_roll_aware_label_plan_qualification"
    summary["upstream_base_decision"] = summary["decision"]
    summary["decision"] = (
        PASS_DECISION if summary["all_gates_passed"] else FAIL_DECISION
    )
    summary["input_identities_before"] = identities_before
    summary["input_identities_after"] = identities_after
    summary["v1_verification"] = v1_verification
    summary["source_verification"] = source_verification
    summary["opened_bar_columns"] = [
        "datetime",
        "symbol",
        "exchange",
        "interval",
    ]
    summary["forbidden_bar_value_columns_opened"] = 0
    summary["implementation_identities"] = {
        "runner_sha256": upstream_stage001.sha256_file(Path(__file__)),
        "original_runner_sha256": upstream_stage001.sha256_file(
            Path(v1.__file__)
        ),
        "core_sha256": upstream_stage001.sha256_file(Path(core.__file__)),
    }

    frames = {
        "roll_aware_label_plan.csv.gz": paths,
        "roll_aware_legs.csv.gz": legs,
        "path_failures.csv.gz": failures,
        "cutoff_rows.csv.gz": cutoff,
    }
    documents = {
        "summary.json": summary,
        "partition_diagnostics.json": partition_diagnostics,
        "input_identities.json": identities_after,
        "upstream_verification.json": {
            "v1": v1_verification,
            "source": source_verification,
        },
        "report.md": _report(summary),
    }
    upstream_stage001.publish_bundle(
        frames,
        documents,
        line_dir=line_dir,
        final_dir=final_path,
        input_identities=identities_after,
    )
    verification = verify_final_bundle(final_path)
    if not verification["verified"]:
        raise Stage001V2Error(
            "published_bundle_invalid:" + ",".join(verification["errors"])
        )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage001 V2 roll-aware identity-only label path audit"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.verify_only:
        result = verify_final_bundle()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["verified"] else 1
    try:
        summary = run_stage001_v2()
    except (
        Stage001V2Error,
        v1.Stage001Error,
        core.PlanError,
        upstream_stage001.Stage001Error,
    ) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

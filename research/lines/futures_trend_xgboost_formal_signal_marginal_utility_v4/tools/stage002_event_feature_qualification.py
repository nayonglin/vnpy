from __future__ import annotations

import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


LINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = LINE_ROOT.parents[2]
PREFLIGHT_TOOL = LINE_ROOT / "tools/stage001_replay_profile_preflight.py"
V3_TOOL = (
    LINE_ROOT.parent / "futures_trend_xgboost_formal_signal_marginal_utility_v3"
    / "tools/stage002_event_feature_qualification.py"
)
STAGE = "stage002_event_feature_qualification"
LINE_ID = LINE_ROOT.name
EXPECTED_INPUT_FILE_COUNT = 1458
PREFLIGHT_ARTIFACT = LINE_ROOT / "artifacts/stage001_replay_profile_side_effect_preflight"
PREFLIGHT_RECORD = LINE_ROOT / "stages/20260905_1907_stage001_profile_preflight_pass.md"
PREREGISTRATION = LINE_ROOT / "stages/20260905_1907_stage002_event_feature_preregistration.md"
CANDIDATE_MODULE_NAME = (
    "run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest"
)


class EventQualificationError(RuntimeError):
    pass


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path.resolve(strict=True))
    if spec is None or spec.loader is None:
        raise EventQualificationError(f"module_spec_failed:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def collect_input_files() -> dict[str, Path]:
    preflight = _load("v4_event_profile_support", PREFLIGHT_TOOL)
    files = dict(preflight.collect_input_files())
    files.update({
        "v4_stage002_runner": Path(__file__).resolve(),
        "v4_stage002_tests": LINE_ROOT / "tests/test_stage002_event_feature_qualification.py",
        "v4_stage002_preregistration": PREREGISTRATION,
        "v4_stage001_record": PREFLIGHT_RECORD,
        "v4_stage001_summary": PREFLIGHT_ARTIFACT / "summary.json",
        "v4_stage001_input_manifest": PREFLIGHT_ARTIFACT / "input_manifest.json",
    })
    for worker in ("A1", "A2"):
        root = PREFLIGHT_ARTIFACT / "workers" / worker
        files[f"v4_stage001_{worker}_receipt"] = root / "receipt.json"
        files[f"v4_stage001_{worker}_universe"] = root / "derived/static18_plus_fu.csv"
        files[f"v4_stage001_{worker}_eligibility"] = root / "derived/post_signal_eligibility.csv"
    if len(files) != EXPECTED_INPUT_FILE_COUNT:
        raise EventQualificationError(f"input_count_mismatch:{len(files)}")
    for key, path in files.items():
        if path.is_symlink() or not path.is_file():
            raise EventQualificationError(f"input_file_invalid:{key}")
    return dict(sorted(files.items()))


def extract_formal_event_features(
    context: Mapping[str, Any],
    *,
    worker_root: Path,
    expected_outputs: Mapping[str, Path],
    expected_candidate_module_path: Path,
    v1: Any,
    feature_module: Any,
    metadata_preflight: Any,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    candidate = sys.modules.get(CANDIDATE_MODULE_NAME)
    if candidate is None:
        raise EventQualificationError("candidate_module_missing")
    module_file = Path(str(candidate.__file__)).resolve(strict=True)
    if module_file != expected_candidate_module_path.resolve(strict=True):
        raise EventQualificationError("candidate_module_identity_mismatch")
    original_universe = candidate.UNIVERSE_PATH
    original_eligibility = candidate.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
    formal = dict(v1._active_formal_identity())
    strategy_class = context["s901"].s847.QmtRollPortfolioStrategyStage847C9StopRetry

    # Profile construction repeats metadata writes inside the replay itself.
    with metadata_preflight.redirect_metadata_outputs(candidate, worker_root) as targets:
        metadata = context["s901"].s513._metadata()
        metadata_summary = metadata_preflight.metadata_contract(metadata)
        metadata_preflight.verify_derived_outputs(targets, expected_outputs)
        restore_trace = v1._install_correlation_trace_instrumentation(strategy_class)
        try:
            combined, frames, live_spec = context["s901"]._run_live_c9(
                metadata, v1.START, v1.END,
            )
        finally:
            restore_trace()
        derived_outputs = metadata_preflight.verify_derived_outputs(targets, expected_outputs)

    restored = (
        candidate.UNIVERSE_PATH is original_universe
        and candidate.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH is original_eligibility
    )
    if not restored:
        raise EventQualificationError("metadata_output_paths_not_restored")
    if float(live_spec.capital.account_capital) != float(v1.EXPECTED_CAPITAL):
        raise EventQualificationError("worker_capital_drift")
    if str(live_spec.profile) != str(context["live_config"].OFFICIAL_LIVE_PROFILE_NAME):
        raise EventQualificationError("worker_profile_drift")
    candidate_frame = frames.get("entry_candidates")
    if candidate_frame is None:
        candidate_frame = v1.pd.DataFrame()
    candidates = candidate_frame.copy()
    del combined, frames, live_spec
    if bool(getattr(candidates, "empty", False)):
        raise EventQualificationError("worker_entry_candidates_empty")
    eligibility = v1.pd.read_csv(formal["eligibility_path"])
    features = feature_module.build_formal_root_event_features(candidates, eligibility, formal)
    return features, formal, {
        "candidate_module_path": str(module_file),
        "metadata": metadata_summary,
        "derived_outputs": derived_outputs,
        "metadata_output_paths_restored": restored,
    }


def load_runner() -> Any:
    # A fresh research module reuses the frozen worker/claim protocol without
    # changing any upstream file or any production module's execution behavior.
    runner = _load("v4_event_frozen_runner_support", V3_TOOL)
    runner.__file__ = str(Path(__file__).resolve())
    runner.LINE_ROOT = LINE_ROOT
    runner.LINE_ID = LINE_ID
    runner.STAGE = STAGE
    runner.EXPECTED_INPUT_FILE_COUNT = EXPECTED_INPUT_FILE_COUNT
    runner.EXECUTION_STATE_DIR = LINE_ROOT / "stages/20260905_stage002_execution_state"
    runner.CLAIM_PATH = runner.EXECUTION_STATE_DIR / "claim.json"
    runner.INPUT_FREEZE_PATH = LINE_ROOT / "stages/20260905_stage002a_input_contract_freeze.json"
    runner.ARTIFACT_ROOT = LINE_ROOT / "artifacts"
    runner.FINAL_DIR = runner.ARTIFACT_ROOT / STAGE
    runner.FAILURE_DIR = runner.ARTIFACT_ROOT / f"{STAGE}_failed"
    runner.collect_input_files = collect_input_files
    runner.extract_formal_event_features = extract_formal_event_features
    return runner


if __name__ == "__main__":
    raise SystemExit(load_runner().main())

"""Probe the first mechanically qualified active marginal-slot month."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import site
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PORTFOLIO_DIR = PRODUCTION_ROOT / "examples/portfolio_backtesting"
RUNTIME_ROOT = Path("/private/tmp/vnpy-stage004-xgboost-runtime")
RUNTIME_DATABASE = RUNTIME_ROOT / ".vntrader/database.db"
TMP_ROOT = Path("/private/tmp/vnpy-stage012-active-account-slot-probe")
BASE_OUT = LINE / "artifacts/stage012_active_account_slot_probe"
STAGE004_TOOL = LINE / "tools/stage004_fullperiod_true_engine.py"
STAGE005_TOOL = LINE / "tools/stage005_current_snapshot_true_engine.py"
STAGE007_TOOL = LINE / "tools/stage007_cold_true_engine_ac.py"
STAGE009_RANKING = (
    LINE / "artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv"
)
STAGE009_AUDIT = LINE / "artifacts/stage009_formal_full_ranking_recovery/audit.json"
STAGE010_TOOL = LINE / "tools/stage010_account_marginal_slot_probe.py"
STAGE011_SELECTION = (
    LINE / "artifacts/stage011_marginal_slot_activity_qualification/selection.json"
)
STAGE011_AUDIT = (
    LINE / "artifacts/stage011_marginal_slot_activity_qualification/activity_audit.csv"
)
PREREGISTRATION = LINE / "stages/20260901_1749_stage012_active_account_slot_probe.md"

FORMAL_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
FORMAL_RELEASE = (
    PRODUCTION_ROOT
    / "official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases"
    / FORMAL_RELEASE_ID
)
FORMAL_ELIGIBILITY = FORMAL_RELEASE / "payload/ai/stage182/combined_eligibility.csv"
FORMAL_CURRENT = PRODUCTION_ROOT / "official_strategy_materials/CURRENT.json"
EXPECTED_PRODUCTION_HEAD = "d492ee072aa5a9d71477235d79f17d2a5db59db3"
EXPECTED_DATABASE_SHA256 = "ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3"
OFFICIAL_STRATEGY = "ai_top10_plus_fu_official_live_v1"
START = pd.Timestamp("2018-01-01")
ARM_SEQUENCE = ("A1", "A2", "C12", "C13")
ELIGIBILITY_KEYS = {"A1": "A", "A2": "A", "C12": "C12", "C13": "C13"}
EXPECTED_SELECTION = {
    "decision": "stage011_first_active_marginal_month_qualified",
    "eval_date": "2022-05-31",
    "next_eval_date": "2022-06-30",
    "baseline_rank": 10,
    "challenger_ranks": [12, 13],
}
DIAGNOSTIC_FRAMES = ("entry_candidates", "entry_risk", "trade_events")

_STAGE004 = None
_STAGE005 = None
_STAGE007 = None
_STAGE010 = None


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable_to_load_module:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_stage004():
    global _STAGE004
    if _STAGE004 is None:
        _STAGE004 = _load_module(STAGE004_TOOL, "stage004_for_stage012")
    return _STAGE004


def _load_stage005():
    global _STAGE005
    if _STAGE005 is None:
        _STAGE005 = _load_module(STAGE005_TOOL, "stage005_for_stage012")
    return _STAGE005


def _load_stage007():
    global _STAGE007
    if _STAGE007 is None:
        _STAGE007 = _load_module(STAGE007_TOOL, "stage007_for_stage012")
    return _STAGE007


def _load_stage010():
    global _STAGE010
    if _STAGE010 is None:
        _STAGE010 = _load_module(STAGE010_TOOL, "stage010_for_stage012")
    return _STAGE010


def probe_spec_from_selection(selection: dict[str, Any]) -> dict[str, Any]:
    observed = {key: selection.get(key) for key in EXPECTED_SELECTION}
    if observed != EXPECTED_SELECTION:
        raise RuntimeError(f"stage011_selection_drift:{observed}")
    return {
        "eval_date": EXPECTED_SELECTION["eval_date"],
        "end": pd.Timestamp(EXPECTED_SELECTION["next_eval_date"]),
        "candidate_ranks": {"A": 10, "C12": 12, "C13": 13},
    }


def _load_probe_spec() -> dict[str, Any]:
    selection = json.loads(STAGE011_SELECTION.read_text(encoding="utf-8"))
    return probe_spec_from_selection(selection)


def startup_hook_identity_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for root_index, root_value in enumerate(site.getsitepackages()):
        root = Path(root_value).resolve()
        for path in sorted(root.glob("*.pth")):
            files[f"python_site_pth/{root_index}/{path.name}"] = path
    for module_name in ("_distutils_hack", "sitecustomize", "usercustomize"):
        module = sys.modules.get(module_name)
        module_file = getattr(module, "__file__", None) if module is not None else None
        if module_file:
            path = Path(module_file).resolve()
            if path.is_file():
                key = (
                    "python_sitecustomize"
                    if module_name == "sitecustomize"
                    else f"python_startup_module/{module_name}"
                )
                files[key] = path
    return files


def build_probe_eligibilities(
    formal: pd.DataFrame,
    ranking: pd.DataFrame,
    *,
    spec: dict[str, Any],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    stage010 = _load_stage010()
    candidates, audit = stage010.build_probe_eligibilities(
        formal,
        ranking,
        eval_date=spec["eval_date"],
        candidate_ranks=spec["candidate_ranks"],
    )
    formal_exact = formal.loc[:, stage010.ELIGIBILITY_COLUMNS].copy()
    formal_exact["eval_date"] = stage010._canonical_dates(formal_exact["eval_date"])
    target_non_tenth = formal_exact[
        formal_exact["eval_date"].eq(spec["eval_date"])
        & formal_exact["score_rank"].ne(10)
    ].copy()
    for arm in ("C12", "C13"):
        frame = candidates[arm]
        candidate_tenth = frame[
            frame["eval_date"].eq(spec["eval_date"])
            & frame["score_rank"].eq(10)
        ].copy()
        if len(candidate_tenth) != 1:
            raise RuntimeError(f"stage012_candidate_tenth_shape:{arm}")
        candidate_tenth.loc[:, "score_type"] = "stage012_active_account_slot_probe"
        replacement = pd.concat([target_non_tenth, candidate_tenth], ignore_index=True)
        replacement.sort_values("score_rank", inplace=True, kind="mergesort")
        non_target = frame[~frame["eval_date"].eq(spec["eval_date"])].copy()
        repaired = pd.concat([non_target, replacement], ignore_index=True)
        repaired.sort_values(["eval_date", "score_rank"], inplace=True, kind="mergesort")
        repaired.reset_index(drop=True, inplace=True)
        observed_unchanged = repaired[
            ~repaired["eval_date"].eq(spec["eval_date"])
            | repaired["score_rank"].ne(10)
        ].reset_index(drop=True)
        expected_unchanged = formal_exact[
            ~formal_exact["eval_date"].eq(spec["eval_date"])
            | formal_exact["score_rank"].ne(10)
        ].sort_values(["eval_date", "score_rank"], kind="mergesort").reset_index(drop=True)
        if not expected_unchanged.equals(observed_unchanged):
            raise RuntimeError(f"stage012_non_tenth_field_drift:{arm}")
        candidates[arm] = repaired
    return candidates, audit


def worker_environment(base: dict[str, str], tmp_root: Path, arm: str) -> dict[str, str]:
    if arm not in ARM_SEQUENCE:
        raise ValueError(f"unknown_arm:{arm}")
    arm_root = tmp_root / arm
    environment = dict(base)
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR": "1",
            "MPLCONFIGDIR": str((arm_root / "mplconfig").resolve()),
            "TMPDIR": str((arm_root / "tmp").resolve()),
        }
    )
    return environment


def _git_output(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repository_state() -> dict[str, str]:
    production_head = _git_output(PRODUCTION_ROOT, "rev-parse", "HEAD")
    production_status = _git_output(PRODUCTION_ROOT, "status", "--porcelain")
    workspace_vnpy_status = _git_output(
        WORKSPACE_ROOT, "status", "--porcelain", "--", "vnpy"
    )
    if production_head != EXPECTED_PRODUCTION_HEAD:
        raise RuntimeError(f"production_head_drift:{production_head}")
    if production_status:
        raise RuntimeError(f"production_worktree_dirty:{production_status}")
    if workspace_vnpy_status:
        raise RuntimeError(f"workspace_vnpy_core_dirty:{workspace_vnpy_status}")
    return {
        "production_head": production_head,
        "production_status": production_status,
        "workspace_vnpy_status": workspace_vnpy_status,
    }


def _file_contract_sha256(files: dict[str, dict[str, Any]]) -> str:
    payload = {
        name: {"size": value["size"], "sha256": value["sha256"]}
        for name, value in sorted(files.items())
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _collect_identity_files(
    attempt_dir: Path,
    *,
    live_cfg: Any,
    s901: Any,
) -> dict[str, Path]:
    stage007 = _load_stage007()
    import contract_metadata
    import vnpy_portfoliostrategy

    overrides = live_cfg.build_official_live_strategy_overrides()
    metadata_path = (
        contract_metadata.ALL_FUTURES_CONTRACT_METADATA_PATH
        if contract_metadata.ALL_FUTURES_CONTRACT_METADATA_PATH.exists()
        else contract_metadata.DEFAULT_CONTRACT_METADATA_PATH
    )
    files: dict[str, Path] = {
        "runtime_database": RUNTIME_DATABASE,
        "runtime_setting": RUNTIME_ROOT / ".vntrader/vt_setting.json",
        "full_minute_bars": Path(s901.s861.FULL_MINUTE_BARS_PATH),
        "main_contract_mapping": Path(s901.ALL_FUTURES_MAPPING_PATH),
        "contract_metadata": Path(metadata_path),
        "product_universe": Path(overrides["product_universe_csv_path"]),
        "formal_current": FORMAL_CURRENT,
        "formal_eligibility": FORMAL_ELIGIBILITY,
        "stage004_helper": STAGE004_TOOL,
        "stage005_helper": STAGE005_TOOL,
        "stage007_identity_reference": STAGE007_TOOL,
        "stage009_full_ranking": STAGE009_RANKING,
        "stage009_audit": STAGE009_AUDIT,
        "stage010_helper": STAGE010_TOOL,
        "stage011_selection": STAGE011_SELECTION,
        "stage011_activity_audit": STAGE011_AUDIT,
        "stage012_runner": Path(__file__).resolve(),
        "stage012_preregistration": PREREGISTRATION,
        "eligibility_A": attempt_dir / "eligibility/A.csv",
        "eligibility_C12": attempt_dir / "eligibility/C12.csv",
        "eligibility_C13": attempt_dir / "eligibility/C13.csv",
        "eligibility_audit": attempt_dir / "eligibility_audit.csv",
        "python_executable": Path(sys.executable).resolve(),
    }
    files.update(startup_hook_identity_files())
    pyvenv = Path(sys.prefix) / "pyvenv.cfg"
    if pyvenv.is_file():
        files["python_pyvenv_cfg"] = pyvenv
    stage007._add_tree_files(
        files,
        prefix="production_portfolio",
        root=PORTFOLIO_DIR,
        suffixes={".py"},
    )
    stage007._add_tree_files(
        files,
        prefix="formal_release",
        root=FORMAL_RELEASE,
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
    for name, path in files.items():
        if not path.is_file():
            raise RuntimeError(f"identity_input_missing:{name}:{path}")
    return files


def _runtime_contract() -> dict[str, Any]:
    packages = _load_stage007().package_version_rows()
    return {
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "cwd": str(Path.cwd().resolve()),
        "sys_path": [str(Path(value).resolve()) if value else "" for value in sys.path],
        "environment": {
            key: os.environ.get(key, "")
            for key in (
                "PYTHONHASHSEED",
                "PYTHONDONTWRITEBYTECODE",
                "PYTHONNOUSERSITE",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR",
                "MPLCONFIGDIR",
                "TMPDIR",
                "STAGE012_ATTEMPT_DIR",
            )
        },
        "repository": _repository_state(),
        "packages": packages,
        "startup_hooks": {
            name: str(path.resolve())
            for name, path in sorted(startup_hook_identity_files().items())
        },
    }


def _identity_manifest(attempt_dir: Path, live_cfg: Any, s901: Any) -> dict[str, Any]:
    stage007 = _load_stage007()
    manifest = stage007.build_identity_manifest(
        _collect_identity_files(attempt_dir, live_cfg=live_cfg, s901=s901),
        runtime=_runtime_contract(),
    )
    manifest["file_contract_sha256"] = _file_contract_sha256(manifest["files"])
    return manifest


def _eligibility_path(attempt_dir: Path, arm: str) -> Path:
    return attempt_dir / "eligibility" / f"{ELIGIBILITY_KEYS[arm]}.csv"


def _run_worker(arm: str, attempt_dir: Path) -> None:
    if arm not in ARM_SEQUENCE:
        raise ValueError(f"unknown_arm:{arm}")
    if Path.cwd().resolve() != RUNTIME_ROOT.resolve():
        raise RuntimeError(f"worker_wrong_runtime:{Path.cwd().resolve()}")
    arm_dir = attempt_dir / "arms" / arm
    if arm_dir.exists():
        raise RuntimeError(f"cold_arm_output_already_exists:{arm_dir}")
    started = time.monotonic()
    spec = _load_probe_spec()
    stage004 = _load_stage004()
    live_cfg, s513, s827, s901 = stage004._load_production_modules()
    metadata = s513._metadata()
    s901._ensure_c9_minute_bars(metadata)
    if live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_ID != FORMAL_RELEASE_ID:
        raise RuntimeError("active_release_drift")
    if Path(live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve() != FORMAL_ELIGIBILITY.resolve():
        raise RuntimeError("active_eligibility_path_drift")
    before = _identity_manifest(attempt_dir, live_cfg, s901)
    if before["files"]["runtime_database"]["sha256"] != EXPECTED_DATABASE_SHA256:
        raise RuntimeError("runtime_database_identity_drift")

    official_builder = live_cfg.build_official_live_strategy_overrides
    eligibility_path = _eligibility_path(attempt_dir, arm)

    def candidate_builder() -> dict[str, Any]:
        overrides = dict(official_builder())
        overrides["ai_product_pool_eligibility_path"] = str(eligibility_path.resolve())
        overrides["ai_product_pool_strategy"] = OFFICIAL_STRATEGY
        return overrides

    profile_name = f"stage012_{arm}_active_account_slot_probe"
    original_builder = s901.build_official_live_strategy_overrides
    try:
        s901.build_official_live_strategy_overrides = candidate_builder
        combined, frames, live_spec = s901._run_live_c9(metadata, START, spec["end"])
    finally:
        s901.build_official_live_strategy_overrides = original_builder
    capital = replace(live_spec.capital, variant=profile_name, label=profile_name)
    metric_spec = replace(live_spec, capital=capital, profile=profile_name)
    summary, curve = s827._metric(
        {"profile": profile_name, "spec": metric_spec}, combined
    )
    summary["experiment_arm"] = arm
    summary["window_name"] = "stage012_2018_to_20220630"
    summary["window_label"] = "2018-01-01_to_2022-06-30"
    curve["experiment_arm"] = arm
    trades = frames.get("trades", pd.DataFrame()).copy()
    trades["experiment_arm"] = arm
    diagnostics: dict[str, pd.DataFrame] = {}
    for key in DIAGNOSTIC_FRAMES:
        frame = frames.get(key, pd.DataFrame()).copy()
        frame["experiment_arm"] = arm
        diagnostics[key] = frame

    after_runtime = _runtime_contract()
    _load_stage010().validate_runtime_stability(before["runtime"], after_runtime)
    after = _identity_manifest(attempt_dir, live_cfg, s901)
    if before != after:
        raise RuntimeError("worker_input_identity_changed")
    wall_seconds = time.monotonic() - started
    arm_dir.mkdir(parents=True, exist_ok=False)
    summary.to_csv(arm_dir / "summary.csv", index=False)
    curve.to_csv(arm_dir / "curve.csv", index=False)
    trades.to_csv(arm_dir / "trades.csv", index=False)
    for key, frame in diagnostics.items():
        frame.to_csv(arm_dir / f"{key}.csv", index=False)
    (arm_dir / "identity_manifest_before.json").write_text(
        json.dumps(before, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (arm_dir / "identity_manifest_after.json").write_text(
        json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    receipt = {
        "arm": arm,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fresh_process_pid": os.getpid(),
        "checkpoint_reused": False,
        "input_identity_pass": True,
        "contract_sha256": before["contract_sha256"],
        "file_contract_sha256": before["file_contract_sha256"],
        "wall_seconds": wall_seconds,
        "tmpdir": os.environ.get("TMPDIR", ""),
        "mplconfigdir": os.environ.get("MPLCONFIGDIR", ""),
        "diagnostic_rows": {key: int(len(frame)) for key, frame in diagnostics.items()},
    }
    (arm_dir / "worker_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)


def _read_arm(
    attempt_dir: Path, arm: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    root = attempt_dir / "arms" / arm
    return (
        pd.read_csv(root / "summary.csv"),
        pd.read_csv(root / "curve.csv"),
        pd.read_csv(root / "trades.csv"),
        json.loads((root / "worker_receipt.json").read_text(encoding="utf-8")),
    )


def _run_subprocess(arm: str, attempt_dir: Path) -> None:
    environment = worker_environment(os.environ, TMP_ROOT / attempt_dir.name, arm)
    environment["STAGE012_ATTEMPT_DIR"] = str(attempt_dir.resolve())
    Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    Path(environment["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "--worker",
            arm,
            "--attempt-dir",
            str(attempt_dir),
        ],
        cwd=RUNTIME_ROOT,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"stage012_worker_failed:{arm}:{completed.returncode}")


def _predecision_rows(frame: pd.DataFrame, eval_date: pd.Timestamp) -> pd.DataFrame:
    date_column = next(
        (name for name in ("date", "datetime", "trading_day") if name in frame.columns),
        None,
    )
    if date_column is None:
        raise RuntimeError("predecision_payload_date_column_missing")
    values = pd.to_datetime(frame[date_column], errors="raise", utc=True).dt.tz_convert(None)
    return frame[values.dt.normalize().le(eval_date.normalize())].reset_index(drop=True)


def _predecision_path_gate(
    attempt_dir: Path,
    curves: dict[str, pd.DataFrame],
    trades: dict[str, pd.DataFrame],
    eval_date: pd.Timestamp,
) -> dict[str, Any]:
    stage005 = _load_stage005()
    reference = curves["A1"].copy()
    reference["date"] = pd.to_datetime(reference["date"]).dt.normalize()
    reference = reference[reference["date"].le(eval_date)]
    gates: dict[str, dict[str, bool]] = {}
    errors: dict[str, float] = {}
    reference_trades = _predecision_rows(trades["A1"], eval_date)
    reference_diagnostics = {
        key: _predecision_rows(
            pd.read_csv(attempt_dir / "arms/A1" / f"{key}.csv"), eval_date
        )
        for key in DIAGNOSTIC_FRAMES
    }
    for arm, curve in curves.items():
        observed = curve.copy()
        observed["date"] = pd.to_datetime(observed["date"]).dt.normalize()
        observed = observed[observed["date"].le(eval_date)]
        passed, error = stage005._numeric_frame_equal(
            reference,
            observed,
            columns=stage005.CURVE_PAYLOAD_COLUMNS,
            text_columns={"date"},
        )
        arm_gates = {
            "curve_payload_exact": bool(passed),
            "trade_payload_exact": stage005._trade_payload_equal(
                reference_trades, _predecision_rows(trades[arm], eval_date)
            ),
        }
        for key in DIAGNOSTIC_FRAMES:
            observed = _predecision_rows(
                pd.read_csv(attempt_dir / "arms" / arm / f"{key}.csv"), eval_date
            )
            arm_gates[f"{key}_payload_exact"] = stage005._trade_payload_equal(
                reference_diagnostics[key], observed
            )
        gates[arm] = arm_gates
        errors[arm] = float(error)
    return {
        "passed": all(all(values.values()) for values in gates.values()),
        "gates": gates,
        "curve_max_abs_errors": errors,
    }


def _target_diagnostic_counts(attempt_dir: Path, eval_date: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for arm in ARM_SEQUENCE:
        arm_dir = attempt_dir / "arms" / arm
        for key in DIAGNOSTIC_FRAMES:
            frame = pd.read_csv(arm_dir / f"{key}.csv")
            total_rows = len(frame)
            target_rows = total_rows
            date_column = next(
                (name for name in ("date", "datetime", "trading_day") if name in frame.columns),
                None,
            )
            if date_column is not None and total_rows:
                values = pd.to_datetime(frame[date_column], errors="coerce").dt.tz_localize(None)
                target_rows = int(values.gt(eval_date).sum())
            rows.append(
                {
                    "arm": arm,
                    "frame": key,
                    "date_column": date_column or "",
                    "all_rows": int(total_rows),
                    "target_period_rows": int(target_rows),
                }
            )
    return pd.DataFrame(rows)


def _orchestrate() -> None:
    if not RUNTIME_DATABASE.is_file():
        raise RuntimeError("runtime_database_missing")
    spec = _load_probe_spec()
    eval_date = pd.Timestamp(spec["eval_date"])
    BASE_OUT.mkdir(parents=True, exist_ok=True)
    attempt_id = (
        datetime.now().astimezone().strftime("attempt_%Y%m%dT%H%M%S%z")
        + f"_{os.getpid()}"
    )
    attempt_dir = BASE_OUT / attempt_id
    attempt_dir.mkdir(parents=False, exist_ok=False)
    eligibility_dir = attempt_dir / "eligibility"
    eligibility_dir.mkdir()
    formal = pd.read_csv(FORMAL_ELIGIBILITY)
    ranking = pd.read_csv(STAGE009_RANKING)
    eligibilities, audit = build_probe_eligibilities(formal, ranking, spec=spec)
    for key, frame in eligibilities.items():
        frame.to_csv(
            eligibility_dir / f"{key}.csv", index=False, encoding="utf-8-sig"
        )
    audit.to_csv(
        attempt_dir / "eligibility_audit.csv", index=False, encoding="utf-8-sig"
    )

    for arm in ARM_SEQUENCE:
        _run_subprocess(arm, attempt_dir)

    summaries: dict[str, pd.DataFrame] = {}
    curves: dict[str, pd.DataFrame] = {}
    trades: dict[str, pd.DataFrame] = {}
    receipts: dict[str, dict[str, Any]] = {}
    for arm in ARM_SEQUENCE:
        summaries[arm], curves[arm], trades[arm], receipts[arm] = _read_arm(
            attempt_dir, arm
        )
    stage005 = _load_stage005()
    repeat = stage005.compare_baseline_repeat(
        summaries["A1"],
        summaries["A2"],
        curves["A1"],
        curves["A2"],
        trades["A1"],
        trades["A2"],
    )
    for key in DIAGNOSTIC_FRAMES:
        left = pd.read_csv(attempt_dir / "arms/A1" / f"{key}.csv")
        right = pd.read_csv(attempt_dir / "arms/A2" / f"{key}.csv")
        repeat["gates"][f"{key}_payload_exact"] = stage005._trade_payload_equal(
            left, right
        )
    repeat["passed"] = all(repeat["gates"].values())
    predecision = _predecision_path_gate(
        attempt_dir, curves, trades, eval_date
    )
    file_contracts = {receipt["file_contract_sha256"] for receipt in receipts.values()}
    identity_pass = (
        len(file_contracts) == 1
        and all(bool(receipt["input_identity_pass"]) for receipt in receipts.values())
        and len({receipt["tmpdir"] for receipt in receipts.values()}) == len(ARM_SEQUENCE)
        and len({receipt["mplconfigdir"] for receipt in receipts.values()})
        == len(ARM_SEQUENCE)
    )
    stage010 = _load_stage010()
    labels = []
    for arm in ARM_SEQUENCE:
        label = stage010.future_period_label(curves[arm], eval_date)
        label["arm"] = arm
        label["candidate_source_rank"] = 10 if arm in {"A1", "A2"} else int(arm[1:])
        labels.append(label)
    labels_frame = pd.DataFrame(labels)
    a = labels_frame[labels_frame["arm"].eq("A1")].iloc[0]
    delta_columns = (
        "future_return",
        "future_max_drawdown",
        "future_net_pnl",
        "future_slippage",
        "future_trade_count",
    )
    for column in delta_columns:
        labels_frame[f"delta_vs_A1_{column}"] = labels_frame[column] - float(a[column])
    candidate_rows = labels_frame[labels_frame["arm"].isin(["C12", "C13"])]
    label_identifiable = bool(
        (
            candidate_rows["delta_vs_A1_future_return"].abs().gt(1e-12)
            | candidate_rows["delta_vs_A1_future_max_drawdown"].abs().gt(1e-12)
        ).any()
    )
    runtime_pass = all(
        float(receipt["wall_seconds"]) <= 600.0 for receipt in receipts.values()
    )
    gates = {
        "input_identity_complete_and_stable": identity_pass,
        "A1_A2_deterministic": bool(repeat["passed"]),
        "predecision_path_identical_all_arms": bool(predecision["passed"]),
        "account_label_identifiable": label_identifiable,
        "each_arm_wall_seconds_le_600": runtime_pass,
    }
    passed = all(gates.values())
    decision_name = (
        "stage012_account_label_identifiable_continue_coverage_study"
        if passed
        else "stage012_account_label_constant_stop_month_rescue"
    )
    summary_frame = pd.concat(
        [summaries[arm] for arm in ARM_SEQUENCE], ignore_index=True
    )
    summary_frame.to_csv(
        attempt_dir / "summary.csv", index=False, encoding="utf-8-sig"
    )
    labels_frame.to_csv(
        attempt_dir / "account_labels.csv", index=False, encoding="utf-8-sig"
    )
    diagnostic_counts = _target_diagnostic_counts(attempt_dir, eval_date)
    diagnostic_counts.to_csv(
        attempt_dir / "diagnostic_counts.csv", index=False, encoding="utf-8-sig"
    )
    decision = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage012",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "attempt_id": attempt_id,
        "decision": decision_name,
        "passed": passed,
        "gates": gates,
        "selection": json.loads(STAGE011_SELECTION.read_text(encoding="utf-8")),
        "baseline_repeat": repeat,
        "predecision_path": predecision,
        "identity_hardening": {
            "sitecustomize_included": True,
            "effective_pth_included": True,
            "loaded_startup_modules_included": True,
            "eligibility_only_target_rank10_row_changed": True,
            "predecision_curve_trade_and_diagnostics_compared": True,
        },
        "file_contract_sha256": (
            next(iter(file_contracts)) if len(file_contracts) == 1 else None
        ),
        "worker_receipts": receipts,
        "labels": labels_frame.to_dict(orient="records"),
        "diagnostic_counts": diagnostic_counts.to_dict(orient="records"),
        "runs_backtest": True,
        "trains_model": False,
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }
    (attempt_dir / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_lines = [
        "# Stage012 首个活跃边际月份账户标签探针",
        "",
        f"- 决策：`{decision_name}`",
        f"- A/A确定性：`{repeat['passed']}`；决策日前路径同一：`{predecision['passed']}`。",
        f"- 完整输入身份：`{identity_pass}`；标签可识别：`{label_identifiable}`；单臂<=600秒：`{runtime_pass}`。",
        "- 本阶段不训练模型，不据单月结果选择候选，不连接CTP，不调用订单API。",
        "",
        labels_frame.to_markdown(index=False),
        "",
        diagnostic_counts.to_markdown(index=False),
        "",
    ]
    (attempt_dir / "report.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )
    latest = {
        "attempt_id": attempt_id,
        "attempt_path": str(attempt_dir.resolve()),
        "decision": decision_name,
    }
    (BASE_OUT / "LATEST.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=ARM_SEQUENCE)
    parser.add_argument("--attempt-dir")
    args = parser.parse_args()
    if args.worker:
        if not args.attempt_dir:
            raise RuntimeError("worker_attempt_dir_missing")
        _run_worker(args.worker, Path(args.attempt_dir).resolve())
    else:
        _orchestrate()


if __name__ == "__main__":
    main()

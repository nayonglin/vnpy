"""Run the frozen current-m0005 A/A/C PIT-listing eligibility backtest."""

from __future__ import annotations

import gc
import hashlib
import importlib.metadata
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


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PORTFOLIO_DIR = PRODUCTION_ROOT / "examples/portfolio_backtesting"
RUNTIME_ROOT = Path("/private/tmp/vnpy-stage004-xgboost-runtime")
RUNTIME_DATABASE = RUNTIME_ROOT / ".vntrader/database.db"
RUNTIME_SETTING = RUNTIME_ROOT / ".vntrader/vt_setting.json"
TMP_ROOT = Path("/private/tmp/vnpy-stage002-pit-listing-ac")
BASE_OUT = LINE_DIR / "artifacts/stage002_frozen_current_m0005_ac"
UPSTREAM = WORKSPACE_ROOT / "research/lines/futures_trend_ai_xgboost_ensemble"
STAGE004_TOOL = UPSTREAM / "tools/stage004_fullperiod_true_engine.py"
STAGE005_TOOL = UPSTREAM / "tools/stage005_current_snapshot_true_engine.py"
STAGE007_TOOL = UPSTREAM / "tools/stage007_cold_true_engine_ac.py"
CORE_TOOL = LINE_DIR / "tools/pit_listing_eligibility.py"
STAGE001_TOOL = LINE_DIR / "tools/stage001_pit_listing_membership.py"
STAGE001_OUT = LINE_DIR / "artifacts/stage001_pit_listing_membership"
CANDIDATE_ELIGIBILITY = STAGE001_OUT / "candidate_eligibility.csv"
STAGE001_AUDIT = STAGE001_OUT / "membership_audit.csv"
STAGE001_SUMMARY = STAGE001_OUT / "stage001_summary.json"
STAGE001_MANIFEST = STAGE001_OUT / "artifact_manifest.json"
PREREGISTRATION = (
    LINE_DIR
    / "stages/20260902_1219_stage002_frozen_current_m0005_ac_preregistration.md"
)
TEST_PATH = LINE_DIR / "tests/test_stage002_frozen_current_m0005_ac.py"

FORMAL_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
FORMAL_RELEASE = (
    PRODUCTION_ROOT
    / "official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases"
    / FORMAL_RELEASE_ID
)
FORMAL_ELIGIBILITY = FORMAL_RELEASE / "payload/ai/stage182/combined_eligibility.csv"
FORMAL_CURRENT = PRODUCTION_ROOT / "official_strategy_materials/CURRENT.json"
OFFICIAL_STRATEGY = "ai_top10_plus_fu_official_live_v1"
EXPECTED_PRODUCTION_HEAD = "d492ee072aa5a9d71477235d79f17d2a5db59db3"
EXPECTED_DATABASE_SHA256 = "ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3"
EXPECTED_STAGE001_SHA256 = {
    "candidate_eligibility": "a9a1501543a02481e690e4ec29aaeb7a522547a105d79cb2f6214fcffc6073ca",
    "membership_audit": "76093dbd3475c906e760ea31105b3de2b751cc4423b669a68ec7716baa73ce00",
    "summary": "9dfca5bc4129c90db945e9d04ac1cee32ec36e10ff78cfb91c57ad09a5f57e10",
    "manifest": "a8d28e6b5e8ec4aa34352b3e049298bb2751c3b4c0068e70490047033e5b4976",
}
START = pd.Timestamp("2020-01-01")
END = pd.Timestamp("2026-06-30")
EXPECTED_FIRST_TRADING_DAY = pd.Timestamp("2020-01-02")
FIRST_CHANGED_EVAL_DATE = pd.Timestamp("2022-01-28")
ARM_SEQUENCE = ("A1", "A2", "C")
CHECKPOINT_REUSE_ALLOWED = False
PASS_DECISION = "stage002_fullperiod_pass_allow_robustness_not_labels"
FAIL_DECISION = "stage002_fullperiod_fail_stop_pit_listing_candidate"

BASELINE_ORACLE = {
    "end_equity": 5_996_631.0,
    "total_return_pct": 3_897.7540,
    "max_dd_pct": -55.370112,
    "sharpe": 1.396723,
    "total_slippage": 759_970.0,
    "total_trade_count": 641.0,
    "nonzero_daily_win_rate_pct": 52.830189,
}
BASELINE_TOLERANCE = {key: 1e-6 for key in BASELINE_ORACLE}
BASELINE_TOLERANCE.update(
    {
        "end_equity": 0.01,
        "total_slippage": 0.01,
        "total_trade_count": 0.01,
    }
)
IDENTITY_COLUMNS = {
    "profile",
    "variant",
    "label",
    "version",
    "experiment_arm",
    "arm",
}

_STAGE004 = None
_STAGE005 = None
_STAGE007 = None


class Stage002Error(RuntimeError):
    """Raised when the frozen Stage002 run must fail closed."""


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stage002Error(f"unable_to_load_module:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_stage004():
    global _STAGE004
    if _STAGE004 is None:
        _STAGE004 = _load_module(STAGE004_TOOL, "stage004_for_pit_listing_stage002")
    return _STAGE004


def _load_stage005():
    global _STAGE005
    if _STAGE005 is None:
        _STAGE005 = _load_module(STAGE005_TOOL, "stage005_for_pit_listing_stage002")
    return _STAGE005


def _load_stage007():
    global _STAGE007
    if _STAGE007 is None:
        _STAGE007 = _load_module(STAGE007_TOOL, "stage007_for_pit_listing_stage002")
    return _STAGE007


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_attempt_absent(path: Path) -> None:
    if Path(path).exists():
        raise Stage002Error(f"attempt_output_already_exists:{path}")


def worker_environment(base: dict[str, str], tmp_root: Path, arm: str) -> dict[str, str]:
    if arm not in ARM_SEQUENCE:
        raise ValueError(f"unknown_arm:{arm}")
    arm_root = Path(tmp_root) / arm
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


def evaluate_baseline_oracle(row: dict[str, Any] | pd.Series) -> dict[str, Any]:
    values = dict(row)
    deltas = {
        key: float(values[key]) - float(expected)
        for key, expected in BASELINE_ORACLE.items()
    }
    gates = {
        f"{key}_within_tolerance": abs(deltas[key]) <= BASELINE_TOLERANCE[key]
        for key in BASELINE_ORACLE
    }
    return {
        "passed": all(gates.values()),
        "gates": gates,
        "expected": BASELINE_ORACLE,
        "actual": {key: float(values[key]) for key in BASELINE_ORACLE},
        "deltas": deltas,
        "tolerances": BASELINE_TOLERANCE,
    }


def evaluate_fullperiod_gates(
    baseline: dict[str, Any] | pd.Series,
    candidate: dict[str, Any] | pd.Series,
    *,
    baseline_repeat_pass: bool,
    baseline_oracle_pass: bool,
    predecision_path_pass: bool,
    identity_pass: bool,
    membership_contract_pass: bool,
    coverage_pass: bool,
) -> dict[str, Any]:
    a = dict(baseline)
    c = dict(candidate)
    gates = {
        "input_identity_pass": bool(identity_pass),
        "baseline_repeat_pass": bool(baseline_repeat_pass),
        "baseline_oracle_pass": bool(baseline_oracle_pass),
        "predecision_path_pass": bool(predecision_path_pass),
        "membership_contract_pass": bool(membership_contract_pass),
        "coverage_pass": bool(coverage_pass),
        "end_equity_strictly_higher": float(c["end_equity"]) > float(a["end_equity"]),
        "total_return_strictly_higher": float(c["total_return_pct"])
        > float(a["total_return_pct"]),
        "max_drawdown_strictly_better": float(c["max_dd_pct"]) > float(a["max_dd_pct"]),
        "sharpe_noninferior": float(c["sharpe"]) >= float(a["sharpe"]),
        "slippage_le_105pct": float(c["total_slippage"])
        <= 1.05 * float(a["total_slippage"]) + 1e-9,
        "trade_count_positive": float(c["total_trade_count"]) > 0.0,
        "account_survival_pass": bool(int(c["account_survival_pass"])),
        "broker10_peak_le_100pct": float(c["max_broker10_margin_to_equity_pct"])
        <= 100.0,
        "days_over_100pct_not_worse": int(c["days_over_100pct"])
        <= int(a["days_over_100pct"]),
    }
    delta_keys = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    ]
    deltas = {
        key: float(c[key]) - float(a[key])
        for key in delta_keys
        if key in a and key in c
    }
    return {"passed": all(gates.values()), "gates": gates, "deltas": deltas}


def _payload_equal(left: pd.DataFrame, right: pd.DataFrame) -> tuple[bool, float]:
    left_columns = [column for column in left.columns if column not in IDENTITY_COLUMNS]
    right_columns = [column for column in right.columns if column not in IDENTITY_COLUMNS]
    if set(left_columns) != set(right_columns) or len(left) != len(right):
        return False, float("inf")
    right = right.loc[:, left_columns]
    left = left.loc[:, left_columns]
    max_error = 0.0
    for column in left_columns:
        a = left[column].reset_index(drop=True)
        b = right[column].reset_index(drop=True)
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            av = pd.to_numeric(a, errors="coerce").to_numpy(dtype=float)
            bv = pd.to_numeric(b, errors="coerce").to_numpy(dtype=float)
            if not np.array_equal(np.isnan(av), np.isnan(bv)):
                return False, float("inf")
            finite = np.isfinite(av) & np.isfinite(bv)
            error = float(np.max(np.abs(av[finite] - bv[finite]))) if finite.any() else 0.0
            max_error = max(max_error, error)
            if error > 1e-9:
                return False, max_error
        elif not a.fillna("").astype(str).equals(b.fillna("").astype(str)):
            return False, float("inf")
    return True, max_error


def _rows_through(frame: pd.DataFrame, boundary: pd.Timestamp) -> pd.DataFrame:
    date_column = next(
        (name for name in ("date", "datetime", "trading_day") if name in frame.columns),
        None,
    )
    if date_column is None:
        raise Stage002Error("payload_date_column_missing")
    dates = pd.to_datetime(frame[date_column], errors="raise", utc=True).dt.tz_convert(None)
    return frame[dates.dt.normalize().le(pd.Timestamp(boundary).normalize())].reset_index(drop=True)


def predecision_path_gate(
    curves: dict[str, pd.DataFrame],
    trades: dict[str, pd.DataFrame],
    *,
    boundary: pd.Timestamp,
) -> dict[str, Any]:
    if "A1" not in curves or "A1" not in trades:
        raise Stage002Error("predecision_reference_missing")
    reference_curve = _rows_through(curves["A1"], boundary)
    reference_trades = _rows_through(trades["A1"], boundary)
    gates: dict[str, bool] = {}
    errors: dict[str, float] = {}
    for arm in curves:
        curve_equal, curve_error = _payload_equal(
            reference_curve, _rows_through(curves[arm], boundary)
        )
        trade_equal, trade_error = _payload_equal(
            reference_trades, _rows_through(trades[arm], boundary)
        )
        gates[f"{arm}_curve_exact"] = curve_equal
        gates[f"{arm}_trades_exact"] = trade_equal
        errors[f"{arm}_curve"] = curve_error
        errors[f"{arm}_trades"] = trade_error
    return {"passed": all(gates.values()), "gates": gates, "max_abs_errors": errors}


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
        raise Stage002Error(f"production_head_drift:{production_head}")
    if production_status:
        raise Stage002Error(f"production_worktree_dirty:{production_status}")
    if workspace_vnpy_status:
        raise Stage002Error(f"workspace_vnpy_core_dirty:{workspace_vnpy_status}")
    return {
        "production_head": production_head,
        "production_status": production_status,
        "workspace_vnpy_status": workspace_vnpy_status,
    }


def _startup_hook_files() -> dict[str, Path]:
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
                files[f"python_startup_module/{module_name}"] = path
    return files


def _runtime_contract() -> dict[str, Any]:
    stage007 = _load_stage007()
    packages = stage007.package_version_rows()
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
                "STAGE002_ATTEMPT_DIR",
            )
        },
        "repository": _repository_state(),
        "packages": packages,
        "startup_hooks": {
            name: str(path.resolve()) for name, path in sorted(_startup_hook_files().items())
        },
    }


def _collect_identity_files(live_cfg: Any, s901: Any) -> dict[str, Path]:
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
        "runtime_setting": RUNTIME_SETTING,
        "full_minute_bars": Path(s901.s861.FULL_MINUTE_BARS_PATH),
        "main_contract_mapping": Path(s901.ALL_FUTURES_MAPPING_PATH),
        "contract_metadata": Path(metadata_path),
        "product_universe": Path(overrides["product_universe_csv_path"]),
        "formal_current": FORMAL_CURRENT,
        "formal_eligibility": FORMAL_ELIGIBILITY,
        "formal_release_manifest": FORMAL_RELEASE / "MANIFEST.json",
        "candidate_eligibility": CANDIDATE_ELIGIBILITY,
        "stage001_audit": STAGE001_AUDIT,
        "stage001_summary": STAGE001_SUMMARY,
        "stage001_manifest": STAGE001_MANIFEST,
        "stage001_core": CORE_TOOL,
        "stage001_runner": STAGE001_TOOL,
        "stage002_preregistration": PREREGISTRATION,
        "stage002_runner": Path(__file__).resolve(),
        "stage002_tests": TEST_PATH,
        "stage004_loader": STAGE004_TOOL,
        "stage005_comparator": STAGE005_TOOL,
        "stage007_identity_helper": STAGE007_TOOL,
        "python_executable": Path(sys.executable).resolve(),
    }
    files.update(_startup_hook_files())
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
    stage007._add_tree_files(
        files,
        prefix="vnpy_portfoliostrategy",
        root=Path(vnpy_portfoliostrategy.__file__).resolve().parent,
        suffixes={".py", ".so", ".dylib"},
    )
    stage007._distribution_metadata_files(files)
    for name, path in files.items():
        if not path.is_file():
            raise Stage002Error(f"identity_input_missing:{name}:{path}")
    return files


def _file_contract_sha256(files: dict[str, dict[str, Any]]) -> str:
    payload = {
        name: {"size": value["size"], "sha256": value["sha256"]}
        for name, value in sorted(files.items())
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _identity_manifest(live_cfg: Any, s901: Any) -> dict[str, Any]:
    stage007 = _load_stage007()
    manifest = stage007.build_identity_manifest(
        _collect_identity_files(live_cfg, s901), runtime=_runtime_contract()
    )
    manifest["file_contract_sha256"] = _file_contract_sha256(manifest["files"])
    return manifest


def _validate_stage001_inputs() -> dict[str, Any]:
    paths = {
        "candidate_eligibility": CANDIDATE_ELIGIBILITY,
        "membership_audit": STAGE001_AUDIT,
        "summary": STAGE001_SUMMARY,
        "manifest": STAGE001_MANIFEST,
    }
    for name, path in paths.items():
        actual = sha256_file(path)
        if actual != EXPECTED_STAGE001_SHA256[name]:
            raise Stage002Error(f"stage001_input_sha256_drift:{name}:{actual}")
    summary = json.loads(STAGE001_SUMMARY.read_text(encoding="utf-8"))
    if (
        summary.get("decision")
        != "stage001_pit_listing_membership_pass_allow_frozen_ac_design"
        or summary.get("all_gates_passed") is not True
        or int(summary.get("changed_months", -1)) != 16
        or int(summary.get("unavailable_formal_top10_slots", -1)) != 35
        or int(summary.get("candidate_unavailable_count", -1)) != 0
    ):
        raise Stage002Error("stage001_membership_contract_drift")
    audit = pd.read_csv(STAGE001_AUDIT)
    changed = audit[audit["membership_changed"].astype(bool)]
    if (
        len(changed) != 16
        or int(audit["formal_unavailable_top10_count"].sum()) != 35
        or pd.Timestamp(changed["eval_date"].min()) != pd.Timestamp("2022-01-28")
        or pd.Timestamp(changed["eval_date"].max()) != pd.Timestamp("2023-08-31")
        or audit.loc[
            pd.to_datetime(audit["eval_date"]).ge(pd.Timestamp("2023-09-28")),
            "membership_changed",
        ].astype(bool).any()
    ):
        raise Stage002Error("stage001_audit_contract_drift")
    return summary


def _warm_and_load_production() -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    stage004 = _load_stage004()
    live_cfg, s513, s827, s901 = stage004._load_production_modules()
    if live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_ID != FORMAL_RELEASE_ID:
        raise Stage002Error("active_release_drift")
    if Path(live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve() != FORMAL_ELIGIBILITY.resolve():
        raise Stage002Error("active_eligibility_path_drift")
    metadata = s513._metadata()
    s901._ensure_c9_minute_bars(metadata)
    return live_cfg, s513, s827, s901, metadata


def _arm_directory(attempt_dir: Path, arm: str) -> Path:
    return Path(attempt_dir) / "arms" / arm


def _run_worker(arm: str, attempt_dir: Path) -> None:
    if arm not in ARM_SEQUENCE:
        raise Stage002Error(f"unknown_arm:{arm}")
    if Path.cwd().resolve() != RUNTIME_ROOT.resolve():
        raise Stage002Error(f"worker_wrong_runtime:{Path.cwd().resolve()}")
    if CHECKPOINT_REUSE_ALLOWED:
        raise Stage002Error("checkpoint_reuse_must_remain_disabled")
    arm_dir = _arm_directory(attempt_dir, arm)
    ensure_attempt_absent(arm_dir)
    started = time.monotonic()
    _validate_stage001_inputs()
    live_cfg, _s513, s827, s901, metadata = _warm_and_load_production()
    before = _identity_manifest(live_cfg, s901)
    if before["files"]["runtime_database"]["sha256"] != EXPECTED_DATABASE_SHA256:
        raise Stage002Error("runtime_database_identity_drift")

    official_builder = live_cfg.build_official_live_strategy_overrides

    def candidate_builder() -> dict[str, Any]:
        overrides = dict(official_builder())
        overrides["ai_product_pool_eligibility_path"] = str(CANDIDATE_ELIGIBILITY.resolve())
        overrides["ai_product_pool_strategy"] = OFFICIAL_STRATEGY
        return overrides

    builder = candidate_builder if arm == "C" else official_builder
    profile_name = (
        "stage002_C_pit_listing_eligible_formal_pool"
        if arm == "C"
        else f"stage002_{arm}_current_m0005_formal_pool"
    )
    original_builder = s901.build_official_live_strategy_overrides
    try:
        s901.build_official_live_strategy_overrides = builder
        combined, frames, live_spec = s901._run_live_c9(metadata, START, END)
    finally:
        s901.build_official_live_strategy_overrides = original_builder
    capital = replace(live_spec.capital, variant=profile_name, label=profile_name)
    metric_spec = replace(live_spec, capital=capital, profile=profile_name)
    summary, curve = s827._metric(
        {"profile": profile_name, "spec": metric_spec}, combined
    )
    summary["experiment_arm"] = arm
    summary["window_name"] = "stage002_20200102_20260630"
    curve["experiment_arm"] = arm
    trades = frames.get("trades", pd.DataFrame()).copy()
    trades["experiment_arm"] = arm

    after = _identity_manifest(live_cfg, s901)
    if before != after:
        raise Stage002Error("worker_input_identity_changed")
    arm_dir.mkdir(parents=True, exist_ok=False)
    summary.to_csv(arm_dir / "summary.csv", index=False, encoding="utf-8-sig")
    curve.to_csv(arm_dir / "curve.csv", index=False, encoding="utf-8-sig")
    trades.to_csv(arm_dir / "trades.csv", index=False, encoding="utf-8-sig")
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
        "wall_seconds": time.monotonic() - started,
        "tmpdir": os.environ.get("TMPDIR", ""),
        "mplconfigdir": os.environ.get("MPLCONFIGDIR", ""),
    }
    (arm_dir / "worker_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "worker_receipt": receipt,
                "metrics": {
                    key: float(summary.iloc[0][key])
                    for key in BASELINE_ORACLE
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    del combined, frames
    gc.collect()


def _run_subprocess(arm: str, attempt_dir: Path) -> None:
    environment = worker_environment(os.environ, TMP_ROOT / attempt_dir.name, arm)
    environment["STAGE002_ATTEMPT_DIR"] = str(attempt_dir.resolve())
    Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    Path(environment["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", arm],
        cwd=RUNTIME_ROOT,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise Stage002Error(f"worker_failed:{arm}:{completed.returncode}")


def _read_arm(
    attempt_dir: Path, arm: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    root = _arm_directory(attempt_dir, arm)
    return (
        pd.read_csv(root / "summary.csv"),
        pd.read_csv(root / "curve.csv"),
        pd.read_csv(root / "trades.csv"),
        json.loads((root / "worker_receipt.json").read_text(encoding="utf-8")),
    )


def _coverage(curves: dict[str, pd.DataFrame]) -> dict[str, Any]:
    dates: dict[str, pd.DatetimeIndex] = {}
    gates: dict[str, bool] = {}
    for arm, frame in curves.items():
        values = pd.DatetimeIndex(pd.to_datetime(frame["date"], errors="raise").normalize())
        dates[arm] = values
        gates[f"{arm}_dates_unique"] = not values.duplicated().any()
        gates[f"{arm}_first_date_exact"] = values.min() == EXPECTED_FIRST_TRADING_DAY
        gates[f"{arm}_last_date_exact"] = values.max() == END
    gates["all_arm_dates_equal"] = all(dates["A1"].equals(values) for values in dates.values())
    return {
        "passed": all(gates.values()),
        "gates": gates,
        "row_counts": {arm: int(len(values)) for arm, values in dates.items()},
    }


def _metric_payload(frame: pd.DataFrame) -> dict[str, float]:
    row = frame.iloc[0]
    keys = [
        *BASELINE_ORACLE,
        "account_survival_pass",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    ]
    return {key: float(row[key]) for key in keys}


def _write_stop_decision(
    attempt_dir: Path,
    name: str,
    payload: dict[str, Any],
) -> None:
    decision = {
        "decision": name,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        **payload,
        "safety": {
            "writes_production": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
            "automatic_promotion": False,
        },
    }
    (attempt_dir / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _output_manifest(attempt_dir: Path) -> dict[str, Any]:
    files = sorted(
        path for path in attempt_dir.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    payload = {
        path.relative_to(attempt_dir).as_posix(): {
            "size": int(path.stat().st_size),
            "sha256": sha256_file(path),
        }
        for path in files
    }
    (attempt_dir / "artifact_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _report(decision: dict[str, Any]) -> str:
    metrics = decision["metrics"]
    lines = [
        "# Stage002 当前m0005 PIT上市资格全周期A/A/C",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- A/A确定性：`{decision['baseline_repeat']['passed']}`；正式基准复现："
        f"`{decision['baseline_oracle']['passed']}`。",
        f"- 首次成员变化日前路径一致：`{decision['predecision_path']['passed']}`。",
        "",
        "| 臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 交易次数 | 非零日胜率 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A1", "C"):
        row = metrics[arm]
        lines.append(
            f"| {arm} | {row['end_equity']:,.2f} | {row['total_return_pct']:.6f}% | "
            f"{row['max_dd_pct']:.6f}% | {row['sharpe']:.6f} | "
            f"{row['total_slippage']:,.0f} | {int(row['total_trade_count'])} | "
            f"{row['nonzero_daily_win_rate_pct']:.6f}% |"
        )
    lines.extend(["", "## 硬门", ""])
    for name, passed in decision["qualification"]["gates"].items():
        lines.append(f"- `{'PASS' if passed else 'FAIL'}` `{name}`")
    lines.extend(
        [
            "",
            "- 离线研究；未修改生产目录，未连接CTP，未调用订单API，未自动晋级。",
            "",
        ]
    )
    return "\n".join(lines)


def _preflight() -> dict[str, Any]:
    if Path.cwd().resolve() != RUNTIME_ROOT.resolve():
        raise Stage002Error(f"preflight_wrong_runtime:{Path.cwd().resolve()}")
    if os.environ.get("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR") != "1":
        raise Stage002Error("runtime_guard_override_missing")
    stage001 = _validate_stage001_inputs()
    repository = _repository_state()
    if sha256_file(RUNTIME_DATABASE) != EXPECTED_DATABASE_SHA256:
        raise Stage002Error("runtime_database_identity_drift")
    live_cfg, _s513, _s827, s901, _metadata = _warm_and_load_production()
    identity = _identity_manifest(live_cfg, s901)
    boundary = _load_stage007().database_boundary_parity(
        PRODUCTION_ROOT / ".vntrader/database.db",
        RUNTIME_DATABASE,
        "2026-06-30 23:59:59",
    )
    if not boundary["passed"]:
        raise Stage002Error(f"database_boundary_parity_failed:{boundary}")
    return {
        "stage001_contract": {
            "decision": stage001["decision"],
            "changed_months": stage001["changed_months"],
            "unavailable_formal_top10_slots": stage001["unavailable_formal_top10_slots"],
        },
        "repository": repository,
        "runtime_database_sha256": EXPECTED_DATABASE_SHA256,
        "production_vs_runtime_database_boundary": boundary,
        "file_contract_sha256": identity["file_contract_sha256"],
        "arm_sequence": list(ARM_SEQUENCE),
        "checkpoint_reuse_allowed": CHECKPOINT_REUSE_ALLOWED,
    }


def _orchestrate() -> None:
    if Path.cwd().resolve() != RUNTIME_ROOT.resolve():
        raise Stage002Error(f"orchestrator_wrong_runtime:{Path.cwd().resolve()}")
    preflight = _preflight()
    BASE_OUT.mkdir(parents=True, exist_ok=True)
    attempt_id = (
        datetime.now().astimezone().strftime("attempt_%Y%m%dT%H%M%S%z")
        + f"_{os.getpid()}"
    )
    attempt_dir = BASE_OUT / attempt_id
    ensure_attempt_absent(attempt_dir)
    attempt_dir.mkdir(parents=False, exist_ok=False)
    (attempt_dir / "arms").mkdir()
    (attempt_dir / "preflight.json").write_text(
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    _run_subprocess("A1", attempt_dir)
    _run_subprocess("A2", attempt_dir)
    a1_summary, a1_curve, a1_trades, a1_receipt = _read_arm(attempt_dir, "A1")
    a2_summary, a2_curve, a2_trades, a2_receipt = _read_arm(attempt_dir, "A2")
    baseline_repeat = _load_stage005().compare_baseline_repeat(
        a1_summary,
        a2_summary,
        a1_curve,
        a2_curve,
        a1_trades,
        a2_trades,
    )
    baseline_oracle = evaluate_baseline_oracle(a1_summary.iloc[0])
    (attempt_dir / "baseline_repeat.json").write_text(
        json.dumps(baseline_repeat, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (attempt_dir / "baseline_oracle.json").write_text(
        json.dumps(baseline_oracle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not baseline_repeat["passed"] or not baseline_oracle["passed"]:
        _write_stop_decision(
            attempt_dir,
            "stage002_baseline_gate_failed_stop_before_candidate",
            {
                "preflight": preflight,
                "baseline_repeat": baseline_repeat,
                "baseline_oracle": baseline_oracle,
            },
        )
        _output_manifest(attempt_dir)
        raise Stage002Error("baseline_gate_failed_stop_before_candidate")

    _run_subprocess("C", attempt_dir)
    c_summary, c_curve, c_trades, c_receipt = _read_arm(attempt_dir, "C")
    summaries = {"A1": a1_summary, "A2": a2_summary, "C": c_summary}
    curves = {"A1": a1_curve, "A2": a2_curve, "C": c_curve}
    trades = {"A1": a1_trades, "A2": a2_trades, "C": c_trades}
    receipts = {"A1": a1_receipt, "A2": a2_receipt, "C": c_receipt}
    file_contracts = {receipt["file_contract_sha256"] for receipt in receipts.values()}
    identity_pass = (
        len(file_contracts) == 1
        and all(receipt["input_identity_pass"] is True for receipt in receipts.values())
        and len({receipt["fresh_process_pid"] for receipt in receipts.values()}) == 3
        and len({receipt["tmpdir"] for receipt in receipts.values()}) == 3
        and len({receipt["mplconfigdir"] for receipt in receipts.values()}) == 3
    )
    coverage = _coverage(curves)
    predecision = predecision_path_gate(
        curves,
        trades,
        boundary=FIRST_CHANGED_EVAL_DATE,
    )
    membership_contract_pass = _validate_stage001_inputs()["all_gates_passed"] is True
    metrics = {arm: _metric_payload(summary) for arm, summary in summaries.items()}
    qualification = evaluate_fullperiod_gates(
        metrics["A1"],
        metrics["C"],
        baseline_repeat_pass=baseline_repeat["passed"],
        baseline_oracle_pass=baseline_oracle["passed"],
        predecision_path_pass=predecision["passed"],
        identity_pass=identity_pass,
        membership_contract_pass=membership_contract_pass,
        coverage_pass=coverage["passed"],
    )
    decision_name = PASS_DECISION if qualification["passed"] else FAIL_DECISION
    decision = {
        "line_id": "futures_trend_ai_pit_listing_eligibility",
        "stage": "Stage002",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "attempt_id": attempt_id,
        "decision": decision_name,
        "status_scope": "development_fullperiod_not_independent_final_oos",
        "formal_release_id": FORMAL_RELEASE_ID,
        "window": {
            "requested_start": START.date().isoformat(),
            "expected_first_trading_day": EXPECTED_FIRST_TRADING_DAY.date().isoformat(),
            "end": END.date().isoformat(),
        },
        "preflight": preflight,
        "baseline_repeat": baseline_repeat,
        "baseline_oracle": baseline_oracle,
        "predecision_path": predecision,
        "coverage": coverage,
        "identity_pass": identity_pass,
        "membership_contract_pass": membership_contract_pass,
        "worker_receipts": receipts,
        "metrics": metrics,
        "qualification": qualification,
        "safety": {
            "strategy_backtest_ran": True,
            "writes_production": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
            "automatic_promotion": False,
            "sealed_holdout_rows_read": 0,
        },
    }
    pd.concat(summaries.values(), ignore_index=True).to_csv(
        attempt_dir / "summary.csv", index=False, encoding="utf-8-sig"
    )
    pd.concat(curves.values(), ignore_index=True).to_csv(
        attempt_dir / "equity_curve.csv.gz", index=False, compression="gzip"
    )
    pd.concat(trades.values(), ignore_index=True).to_csv(
        attempt_dir / "trades.csv.gz", index=False, compression="gzip"
    )
    (attempt_dir / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (attempt_dir / "report.md").write_text(_report(decision), encoding="utf-8")
    manifest = _output_manifest(attempt_dir)
    print(
        json.dumps(
            {
                "decision": decision_name,
                "metrics": metrics,
                "qualification": qualification,
                "artifact_count": len(manifest),
                "attempt_dir": str(attempt_dir.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=ARM_SEQUENCE)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    attempt_env = os.environ.get("STAGE002_ATTEMPT_DIR", "")
    if args.worker:
        if not attempt_env:
            raise Stage002Error("worker_attempt_dir_missing")
        _run_worker(args.worker, Path(attempt_env))
        return
    if args.preflight:
        print(json.dumps(_preflight(), ensure_ascii=False, indent=2))
        return
    _orchestrate()


if __name__ == "__main__":
    main()

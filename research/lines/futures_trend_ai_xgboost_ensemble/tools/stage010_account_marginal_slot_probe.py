"""Probe account-level labels for the formal AI pool's marginal tenth slot."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
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
TMP_ROOT = Path("/private/tmp/vnpy-stage010-account-slot-probe")
BASE_OUT = LINE / "artifacts/stage010_account_marginal_slot_probe"
STAGE004_TOOL = LINE / "tools/stage004_fullperiod_true_engine.py"
STAGE005_TOOL = LINE / "tools/stage005_current_snapshot_true_engine.py"
STAGE007_TOOL = LINE / "tools/stage007_cold_true_engine_ac.py"
STAGE009_RANKING = LINE / "artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv"
STAGE009_AUDIT = LINE / "artifacts/stage009_formal_full_ranking_recovery/audit.json"
PREREGISTRATION = LINE / "stages/20260901_1729_stage010_account_marginal_slot_probe.md"

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
FIXED_PRODUCT = "fu.SHFE"
TARGET_EVAL_DATE = "2022-04-29"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2022-05-31")
ARM_SEQUENCE = ("A1", "A2", "C11", "C18")
ELIGIBILITY_KEYS = {"A1": "A", "A2": "A", "C11": "C11", "C18": "C18"}
CANDIDATE_RANKS = {"A": 10, "C11": 11, "C18": 18}
ELIGIBILITY_COLUMNS = [
    "strategy",
    "score_type",
    "eval_date",
    "product_vt_symbol",
    "score",
    "score_rank",
    "top_n",
]

_STAGE004 = None
_STAGE005 = None
_STAGE007 = None


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
        _STAGE004 = _load_module(STAGE004_TOOL, "stage004_for_stage010")
    return _STAGE004


def _load_stage005():
    global _STAGE005
    if _STAGE005 is None:
        _STAGE005 = _load_module(STAGE005_TOOL, "stage005_for_stage010")
    return _STAGE005


def _load_stage007():
    global _STAGE007
    if _STAGE007 is None:
        _STAGE007 = _load_module(STAGE007_TOOL, "stage007_for_stage010")
    return _STAGE007


def _canonical_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="raise").dt.date.astype(str)


def build_probe_eligibilities(
    formal: pd.DataFrame,
    full_ranking: pd.DataFrame,
    *,
    eval_date: str = TARGET_EVAL_DATE,
    candidate_ranks: dict[str, int] = CANDIDATE_RANKS,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    missing_formal = set(ELIGIBILITY_COLUMNS) - set(formal.columns)
    missing_ranking = {
        "eval_date",
        "product_vt_symbol",
        "score",
        "score_rank",
    } - set(full_ranking.columns)
    if missing_formal:
        raise RuntimeError(f"formal_columns_missing:{sorted(missing_formal)}")
    if missing_ranking:
        raise RuntimeError(f"ranking_columns_missing:{sorted(missing_ranking)}")
    formal = formal.loc[:, ELIGIBILITY_COLUMNS].copy()
    formal["eval_date"] = _canonical_dates(formal["eval_date"])
    ranking = full_ranking.copy()
    ranking["eval_date"] = _canonical_dates(ranking["eval_date"])
    ranking["score_rank"] = pd.to_numeric(ranking["score_rank"], errors="raise").astype(int)
    ranking["score"] = pd.to_numeric(ranking["score"], errors="raise").astype(float)

    target_formal = formal[formal["eval_date"].eq(eval_date)].sort_values("score_rank")
    target_ranking = ranking[ranking["eval_date"].eq(eval_date)].sort_values("score_rank")
    if len(target_formal) != 11 or len(target_ranking) != 18:
        raise RuntimeError(f"target_month_shape:{len(target_formal)}:{len(target_ranking)}")
    if target_ranking["product_vt_symbol"].duplicated().any():
        raise RuntimeError("target_ranking_duplicate")
    if target_ranking["score_rank"].tolist() != list(range(1, 19)):
        raise RuntimeError("target_ranking_rank_shape")
    formal_non_fu = target_formal[
        ~target_formal["product_vt_symbol"].astype(str).eq(FIXED_PRODUCT)
    ]
    if formal_non_fu["product_vt_symbol"].tolist() != target_ranking.head(10)[
        "product_vt_symbol"
    ].tolist():
        raise RuntimeError("formal_prefix_not_exact")
    fixed = target_formal[target_formal["product_vt_symbol"].astype(str).eq(FIXED_PRODUCT)]
    if len(fixed) != 1 or int(fixed.iloc[0]["score_rank"]) != 11:
        raise RuntimeError("fixed_fu_contract_drift")

    core = target_formal[target_formal["score_rank"].le(9)].copy()
    strategy_values = set(formal["strategy"].astype(str))
    if len(strategy_values) != 1:
        raise RuntimeError("formal_strategy_count")
    strategy = next(iter(strategy_values))
    results: dict[str, pd.DataFrame] = {}
    audit_rows: list[dict[str, Any]] = []
    for arm, candidate_rank in candidate_ranks.items():
        candidate = target_ranking[target_ranking["score_rank"].eq(candidate_rank)]
        if len(candidate) != 1:
            raise RuntimeError(f"candidate_rank_missing:{arm}:{candidate_rank}")
        candidate_row = candidate.iloc[0]
        if candidate_row["product_vt_symbol"] in set(core["product_vt_symbol"]):
            raise RuntimeError(f"candidate_already_in_core:{arm}")
        if arm == "A":
            replacement = target_formal.copy()
        else:
            tenth_score = float(candidate_row["score"])
            tenth = pd.DataFrame(
                [
                    {
                        "strategy": strategy,
                        "score_type": "stage010_account_marginal_slot_probe",
                        "eval_date": eval_date,
                        "product_vt_symbol": str(candidate_row["product_vt_symbol"]),
                        "score": tenth_score,
                        "score_rank": 10,
                        "top_n": 11,
                    }
                ]
            )
            fixed_row = fixed.copy()
            fixed_row.loc[:, "score_type"] = "stage010_account_marginal_slot_probe"
            fixed_row.loc[:, "score"] = tenth_score - 1e-6
            replacement = pd.concat([core, tenth, fixed_row], ignore_index=True)
        replacement = replacement.loc[:, ELIGIBILITY_COLUMNS].sort_values("score_rank")
        candidate_frame = formal[~formal["eval_date"].eq(eval_date)].copy()
        candidate_frame = pd.concat([candidate_frame, replacement], ignore_index=True)
        candidate_frame.sort_values(["eval_date", "score_rank"], inplace=True, kind="mergesort")
        candidate_frame.reset_index(drop=True, inplace=True)
        unchanged = formal[~formal["eval_date"].eq(eval_date)].sort_values(
            ["eval_date", "score_rank"], kind="mergesort"
        ).reset_index(drop=True)
        observed = candidate_frame[~candidate_frame["eval_date"].eq(eval_date)].reset_index(drop=True)
        if not unchanged.equals(observed):
            raise RuntimeError(f"non_target_month_drift:{arm}")
        target_products = replacement["product_vt_symbol"].astype(str).tolist()
        if len(target_products) != 11 or target_products[-1] != FIXED_PRODUCT:
            raise RuntimeError(f"candidate_month_contract:{arm}")
        results[arm] = candidate_frame
        formal_products = set(target_formal["product_vt_symbol"].astype(str)) - {FIXED_PRODUCT}
        candidate_products = set(target_products) - {FIXED_PRODUCT}
        audit_rows.append(
            {
                "arm": arm,
                "candidate_source_rank": candidate_rank,
                "candidate_product": str(candidate_row["product_vt_symbol"]),
                "removed_product": ",".join(sorted(formal_products - candidate_products)),
                "added_product": ",".join(sorted(candidate_products - formal_products)),
                "changed_slots": len(candidate_products - formal_products),
                "core_signature": ",".join(core["product_vt_symbol"].astype(str)),
                "fixed_fu_present": FIXED_PRODUCT in target_products,
            }
        )
    return results, pd.DataFrame(audit_rows)


def future_period_label(curve: pd.DataFrame, eval_date: pd.Timestamp) -> dict[str, float]:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame.sort_values("date", inplace=True)
    prior = frame[frame["date"].le(eval_date.normalize())]
    future = frame[frame["date"].gt(eval_date.normalize())]
    if prior.empty or future.empty:
        raise RuntimeError("future_period_boundary_missing")
    base_equity = float(prior.iloc[-1]["account_equity"])
    future_equity = pd.to_numeric(future["account_equity"], errors="raise").to_numpy(float)
    wealth = np.concatenate(([1.0], future_equity / base_equity))
    drawdown = wealth / np.maximum.accumulate(wealth) - 1.0
    slippage_column = "slippage" if "slippage" in future.columns else "total_slippage"
    return {
        "base_equity": base_equity,
        "end_equity": float(future_equity[-1]),
        "future_return": float(future_equity[-1] / base_equity - 1.0),
        "future_max_drawdown": float(drawdown.min()),
        "future_net_pnl": float(pd.to_numeric(future["net_pnl"], errors="raise").sum()),
        "future_slippage": float(pd.to_numeric(future[slippage_column], errors="raise").sum()),
        "future_trade_count": float(pd.to_numeric(future["trade_count"], errors="raise").sum()),
        "future_trading_days": float(len(future)),
    }


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


def validate_runtime_stability(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            raise RuntimeError(f"runtime_contract_changed:{key}")


def validate_repository_values(
    production_head: str,
    production_status: str,
    workspace_vnpy_status: str,
) -> dict[str, str]:
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


def _git_output(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repository_state() -> dict[str, str]:
    return validate_repository_values(
        _git_output(PRODUCTION_ROOT, "rev-parse", "HEAD"),
        _git_output(PRODUCTION_ROOT, "status", "--porcelain"),
        _git_output(WORKSPACE_ROOT, "status", "--porcelain", "--", "vnpy"),
    )


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
    stage004: Any,
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
        "stage010_runner": Path(__file__).resolve(),
        "stage010_preregistration": PREREGISTRATION,
        "eligibility_A": attempt_dir / "eligibility/A.csv",
        "eligibility_C11": attempt_dir / "eligibility/C11.csv",
        "eligibility_C18": attempt_dir / "eligibility/C18.csv",
        "eligibility_audit": attempt_dir / "eligibility_audit.csv",
        "python_executable": Path(sys.executable).resolve(),
    }
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
                "STAGE010_ATTEMPT_DIR",
            )
        },
        "repository": _repository_state(),
        "packages": packages,
    }


def _identity_manifest(attempt_dir: Path, stage004: Any, live_cfg: Any, s901: Any) -> dict[str, Any]:
    stage007 = _load_stage007()
    manifest = stage007.build_identity_manifest(
        _collect_identity_files(
            attempt_dir,
            stage004=stage004,
            live_cfg=live_cfg,
            s901=s901,
        ),
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
    stage004 = _load_stage004()
    live_cfg, s513, s827, s901 = stage004._load_production_modules()
    metadata = s513._metadata()
    s901._ensure_c9_minute_bars(metadata)
    if live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_ID != FORMAL_RELEASE_ID:
        raise RuntimeError("active_release_drift")
    if Path(live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve() != FORMAL_ELIGIBILITY.resolve():
        raise RuntimeError("active_eligibility_path_drift")
    before = _identity_manifest(attempt_dir, stage004, live_cfg, s901)
    if before["files"]["runtime_database"]["sha256"] != EXPECTED_DATABASE_SHA256:
        raise RuntimeError("runtime_database_identity_drift")

    official_builder = live_cfg.build_official_live_strategy_overrides
    eligibility_path = _eligibility_path(attempt_dir, arm)

    def candidate_builder() -> dict[str, Any]:
        overrides = dict(official_builder())
        overrides["ai_product_pool_eligibility_path"] = str(eligibility_path.resolve())
        overrides["ai_product_pool_strategy"] = OFFICIAL_STRATEGY
        return overrides

    profile_name = f"stage010_{arm}_account_marginal_slot_probe"
    original_builder = s901.build_official_live_strategy_overrides
    try:
        s901.build_official_live_strategy_overrides = candidate_builder
        combined, frames, live_spec = s901._run_live_c9(metadata, START, END)
    finally:
        s901.build_official_live_strategy_overrides = original_builder
    capital = replace(live_spec.capital, variant=profile_name, label=profile_name)
    metric_spec = replace(live_spec, capital=capital, profile=profile_name)
    summary, curve = s827._metric({"profile": profile_name, "spec": metric_spec}, combined)
    summary["experiment_arm"] = arm
    summary["window_name"] = "stage010_2018_to_20220531"
    curve["experiment_arm"] = arm
    trades = frames.get("trades", pd.DataFrame()).copy()
    trades["experiment_arm"] = arm

    after_runtime = _runtime_contract()
    validate_runtime_stability(before["runtime"], after_runtime)
    after = _identity_manifest(attempt_dir, stage004, live_cfg, s901)
    if before != after:
        raise RuntimeError("worker_input_identity_changed")
    wall_seconds = time.monotonic() - started
    arm_dir.mkdir(parents=True, exist_ok=False)
    summary.to_csv(arm_dir / "summary.csv", index=False)
    curve.to_csv(arm_dir / "curve.csv", index=False)
    trades.to_csv(arm_dir / "trades.csv", index=False)
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
    }
    (arm_dir / "worker_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)


def _read_arm(attempt_dir: Path, arm: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    root = attempt_dir / "arms" / arm
    return (
        pd.read_csv(root / "summary.csv"),
        pd.read_csv(root / "curve.csv"),
        pd.read_csv(root / "trades.csv"),
        json.loads((root / "worker_receipt.json").read_text(encoding="utf-8")),
    )


def _run_subprocess(arm: str, attempt_dir: Path) -> None:
    environment = worker_environment(os.environ, TMP_ROOT / attempt_dir.name, arm)
    environment["STAGE010_ATTEMPT_DIR"] = str(attempt_dir.resolve())
    Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    Path(environment["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", arm, "--attempt-dir", str(attempt_dir)],
        cwd=RUNTIME_ROOT,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"stage010_worker_failed:{arm}:{completed.returncode}")


def _predecision_curve_gate(curves: dict[str, pd.DataFrame]) -> dict[str, Any]:
    stage005 = _load_stage005()
    reference = curves["A1"].copy()
    reference["date"] = pd.to_datetime(reference["date"]).dt.normalize()
    reference = reference[reference["date"].le(pd.Timestamp(TARGET_EVAL_DATE))]
    gates: dict[str, bool] = {}
    errors: dict[str, float] = {}
    for arm, curve in curves.items():
        observed = curve.copy()
        observed["date"] = pd.to_datetime(observed["date"]).dt.normalize()
        observed = observed[observed["date"].le(pd.Timestamp(TARGET_EVAL_DATE))]
        passed, error = stage005._numeric_frame_equal(
            reference,
            observed,
            columns=stage005.CURVE_PAYLOAD_COLUMNS,
            text_columns={"date"},
        )
        gates[arm] = bool(passed)
        errors[arm] = float(error)
    return {"passed": all(gates.values()), "gates": gates, "max_abs_errors": errors}


def _orchestrate() -> None:
    if not RUNTIME_DATABASE.is_file():
        raise RuntimeError("runtime_database_missing")
    BASE_OUT.mkdir(parents=True, exist_ok=True)
    attempt_id = datetime.now().astimezone().strftime("attempt_%Y%m%dT%H%M%S%z") + f"_{os.getpid()}"
    attempt_dir = BASE_OUT / attempt_id
    attempt_dir.mkdir(parents=False, exist_ok=False)
    eligibility_dir = attempt_dir / "eligibility"
    eligibility_dir.mkdir()
    formal = pd.read_csv(FORMAL_ELIGIBILITY)
    ranking = pd.read_csv(STAGE009_RANKING)
    eligibilities, audit = build_probe_eligibilities(formal, ranking)
    for key, frame in eligibilities.items():
        frame.to_csv(eligibility_dir / f"{key}.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(attempt_dir / "eligibility_audit.csv", index=False, encoding="utf-8-sig")

    for arm in ARM_SEQUENCE:
        _run_subprocess(arm, attempt_dir)

    summaries: dict[str, pd.DataFrame] = {}
    curves: dict[str, pd.DataFrame] = {}
    trades: dict[str, pd.DataFrame] = {}
    receipts: dict[str, dict[str, Any]] = {}
    for arm in ARM_SEQUENCE:
        summaries[arm], curves[arm], trades[arm], receipts[arm] = _read_arm(attempt_dir, arm)
    stage005 = _load_stage005()
    repeat = stage005.compare_baseline_repeat(
        summaries["A1"],
        summaries["A2"],
        curves["A1"],
        curves["A2"],
        trades["A1"],
        trades["A2"],
    )
    predecision = _predecision_curve_gate(curves)
    file_contracts = {receipt["file_contract_sha256"] for receipt in receipts.values()}
    identity_pass = (
        len(file_contracts) == 1
        and all(bool(receipt["input_identity_pass"]) for receipt in receipts.values())
        and len({receipt["tmpdir"] for receipt in receipts.values()}) == len(ARM_SEQUENCE)
        and len({receipt["mplconfigdir"] for receipt in receipts.values()}) == len(ARM_SEQUENCE)
    )
    labels = []
    for arm in ARM_SEQUENCE:
        label = future_period_label(curves[arm], pd.Timestamp(TARGET_EVAL_DATE))
        label["arm"] = arm
        label["candidate_source_rank"] = 10 if arm in {"A1", "A2"} else int(arm[1:])
        labels.append(label)
    labels_frame = pd.DataFrame(labels)
    a = labels_frame[labels_frame["arm"].eq("A1")].iloc[0]
    for column in ("future_return", "future_max_drawdown", "future_net_pnl", "future_slippage", "future_trade_count"):
        labels_frame[f"delta_vs_A1_{column}"] = labels_frame[column] - float(a[column])
    candidate_rows = labels_frame[labels_frame["arm"].isin(["C11", "C18"])]
    label_identifiable = bool(
        (
            candidate_rows["delta_vs_A1_future_return"].abs().gt(1e-12)
            | candidate_rows["delta_vs_A1_future_max_drawdown"].abs().gt(1e-12)
        ).any()
    )
    runtime_pass = all(float(receipt["wall_seconds"]) <= 600.0 for receipt in receipts.values())
    gates = {
        "input_identity_complete_and_stable": identity_pass,
        "A1_A2_deterministic": bool(repeat["passed"]),
        "predecision_curve_identical_all_arms": bool(predecision["passed"]),
        "account_label_identifiable": label_identifiable,
        "each_arm_wall_seconds_le_600": runtime_pass,
    }
    passed = all(gates.values())
    decision_name = (
        "stage010_account_label_probe_pass_expand_all_ranks"
        if passed
        else "stage010_account_label_probe_fail_stop"
    )
    summary_frame = pd.concat([summaries[arm] for arm in ARM_SEQUENCE], ignore_index=True)
    summary_frame.to_csv(attempt_dir / "summary.csv", index=False, encoding="utf-8-sig")
    labels_frame.to_csv(attempt_dir / "account_labels.csv", index=False, encoding="utf-8-sig")
    decision = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage010",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "attempt_id": attempt_id,
        "decision": decision_name,
        "passed": passed,
        "gates": gates,
        "baseline_repeat": repeat,
        "predecision_curve": predecision,
        "file_contract_sha256": next(iter(file_contracts)) if len(file_contracts) == 1 else None,
        "worker_receipts": receipts,
        "labels": labels_frame.to_dict(orient="records"),
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
        "# Stage010 账户第10席位探针",
        "",
        f"- 决策：`{decision_name}`",
        f"- A/A确定性：`{repeat['passed']}`；决策日前路径同一：`{predecision['passed']}`。",
        f"- 完整输入身份：`{identity_pass}`；标签可识别：`{label_identifiable}`；单臂<=600秒：`{runtime_pass}`。",
        "- 本阶段不训练模型，不据单月结果选择候选，不连接CTP，不调用订单API。",
        "",
        labels_frame.to_markdown(index=False),
        "",
    ]
    (attempt_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    latest = {"attempt_id": attempt_id, "attempt_path": str(attempt_dir.resolve()), "decision": decision_name}
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

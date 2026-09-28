"""Run Stage006 A/A/C in separate cold processes with a frozen runtime contract."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import sqlite3
import subprocess
import sys
import gc
from argparse import ArgumentParser
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


LINE = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PORTFOLIO_DIR = PRODUCTION_ROOT / "examples/portfolio_backtesting"
RUNTIME_ROOT = Path("/private/tmp/vnpy-stage004-xgboost-runtime")
RUNTIME_DATABASE = RUNTIME_ROOT / ".vntrader/database.db"
TMP_ROOT = Path("/private/tmp/vnpy-stage007-cold-runtime")
OUT = LINE / "artifacts/stage007_cold_true_engine_ac"
ARMS_DIR = OUT / "arms"
IDENTITY_BEFORE = OUT / "identity_manifest_before.json"
STAGE004_TOOL = LINE / "tools/stage004_fullperiod_true_engine.py"
STAGE005_TOOL = LINE / "tools/stage005_current_snapshot_true_engine.py"
STAGE006_TOOL = LINE / "tools/stage006_pit_corrected_ranker.py"
STAGE006_OUT = LINE / "artifacts/stage006_pit_corrected_ranker"
STAGE006_SUMMARY = STAGE006_OUT / "summary.json"
STAGE006_PREDICTIONS = STAGE006_OUT / "oos_predictions.csv"
STAGE006_REVIEW_RECEIPT = LINE / "reviews/20260901_stage006_independent_review.json"
PREREGISTRATION_PATH = LINE / "stages/20260901_1627_stage007_cold_true_engine_ac.md"
CANDIDATE_ELIGIBILITY = OUT / "stage007_candidate_eligibility.csv"
MEMBERSHIP_AUDIT = OUT / "stage007_membership_audit.csv"

CHECKPOINT_REUSE_ALLOWED = False
ARM_SEQUENCE = ("A1", "A2", "C")
FORMAL_RELEASE_ID = "m0004_20260831T112631+0800_2485073e9594"
EXPECTED_PRODUCTION_HEAD = "1961d98ccb2b9129e35fe982b7330ae4217dcde6"
EXPECTED_DATABASE_SHA256 = "ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3"
EXPECTED_OOS_MONTHS = 49
EXPECTED_FIRST_OOS_DATE = "2022-04-29"
EXPECTED_LAST_OOS_DATE = "2026-04-30"
CANDIDATE_SCORE_TYPE = "stage006_pit_corrected_two_month_confirmed_xgboost_top10_plus_fixed_fu"

_STAGE004_MODULE = None
_STAGE005_MODULE = None


def _file_identity(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"file_changed_while_hashing:{path}")
    return {
        "path": str(path.resolve()),
        "size": after.st_size,
        "sha256": digest.hexdigest(),
    }


def build_identity_manifest(
    files: dict[str, Path],
    *,
    runtime: dict[str, Any],
) -> dict[str, Any]:
    identities = {name: _file_identity(files[name]) for name in sorted(files)}
    contract_payload = {
        "files": {
            name: {"size": value["size"], "sha256": value["sha256"]}
            for name, value in identities.items()
        },
        "runtime": runtime,
    }
    encoded = json.dumps(
        contract_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return {
        "contract_sha256": hashlib.sha256(encoded).hexdigest(),
        "files": identities,
        "runtime": runtime,
    }


def assert_cold_arm_output(path: Path) -> None:
    if path.exists():
        raise RuntimeError(f"cold_arm_output_already_exists:{path}")


def worker_command(script: Path, arm: str) -> list[str]:
    if arm not in ARM_SEQUENCE:
        raise ValueError(f"unknown_arm:{arm}")
    return [sys.executable, "-B", str(script), "--worker", arm]


def worker_environment(base: dict[str, str], tmp_root: Path) -> dict[str, str]:
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
            "MPLCONFIGDIR": str((tmp_root / "mplconfig").resolve()),
            "TMPDIR": str((tmp_root / "tmp").resolve()),
        }
    )
    return environment


def validate_stage006_upstream(summary: dict[str, Any]) -> None:
    if summary.get("decision") != "stage006_pit_corrected_confirmed_pass_development_only":
        raise RuntimeError("stage006_decision_not_qualified")
    pit = summary.get("pit_audit", {})
    if any(int(pit.get(key, -1)) != 0 for key in (
        "violation_rows",
        "violation_train_months",
        "violation_folds",
    )):
        raise RuntimeError("stage006_pit_not_clean")
    if not bool(summary.get("qualification", {}).get("C3_confirmed", {}).get("passed")):
        raise RuntimeError("stage006_original_c3_gates_not_passed")
    if summary.get("status_scope") != "development_only_not_independent_final_oos":
        raise RuntimeError("stage006_scope_drift")


def validate_stage006_review_receipt(
    receipt: dict[str, Any],
    *,
    expected_summary_sha256: str,
) -> None:
    if receipt.get("verdict") != "PASS" or receipt.get("allow_development_true_engine") is not True:
        raise RuntimeError("stage006_review_not_passed")
    if receipt.get("reviewed_stage006_summary_sha256") != expected_summary_sha256:
        raise RuntimeError("stage006_review_summary_identity_drift")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable_to_load_module:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_stage004():
    global _STAGE004_MODULE
    if _STAGE004_MODULE is None:
        _STAGE004_MODULE = _load_module(STAGE004_TOOL, "stage004_for_stage007")
    return _STAGE004_MODULE


def _load_stage005():
    global _STAGE005_MODULE
    if _STAGE005_MODULE is None:
        _STAGE005_MODULE = _load_module(STAGE005_TOOL, "stage005_for_stage007")
    return _STAGE005_MODULE


def _git_output(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def assert_repository_state() -> dict[str, str]:
    production_head = _git_output(PRODUCTION_ROOT, "rev-parse", "HEAD")
    production_status = _git_output(PRODUCTION_ROOT, "status", "--porcelain")
    workspace_vnpy_status = _git_output(
        WORKSPACE_ROOT,
        "status",
        "--porcelain",
        "--",
        "vnpy",
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


def _add_tree_files(
    files: dict[str, Path],
    *,
    prefix: str,
    root: Path,
    suffixes: set[str] | None = None,
) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if suffixes is not None and path.suffix not in suffixes:
            continue
        files[f"{prefix}/{path.relative_to(root).as_posix()}"] = path


def package_version_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name") or "unknown"
        location = str(Path(distribution.locate_file("")).resolve())
        rows.append(
            {
                "name": name,
                "version": distribution.version,
                "location": location,
            }
        )
    return sorted(rows, key=lambda row: (row["name"].lower(), row["version"], row["location"]))


def _distribution_metadata_files(files: dict[str, Path]) -> None:
    wanted = {"METADATA", "RECORD", "direct_url.json", "WHEEL"}
    for distribution in importlib.metadata.distributions():
        name = (distribution.metadata.get("Name") or "unknown").replace("/", "_")
        version = distribution.version
        location = str(Path(distribution.locate_file("")).resolve())
        location_key = hashlib.sha256(location.encode()).hexdigest()[:12]
        for relative in distribution.files or []:
            relative_path = Path(str(relative))
            if relative_path.name not in wanted or ".dist-info" not in relative_path.as_posix():
                continue
            path = Path(distribution.locate_file(relative))
            if path.is_file():
                key = f"distribution_metadata/{name}/{version}/{location_key}/{relative_path.name}"
                files[key] = path


def collect_identity_files() -> dict[str, Path]:
    stage004 = _load_stage004()
    files: dict[str, Path] = {
        "formal_current": stage004.FORMAL_CURRENT,
        "formal_eligibility": stage004.FORMAL_ELIGIBILITY,
        "runtime_database": RUNTIME_DATABASE,
        "stage004_helper": STAGE004_TOOL,
        "stage005_repeat_helper": STAGE005_TOOL,
        "stage006_tool": STAGE006_TOOL,
        "stage006_summary": STAGE006_SUMMARY,
        "stage006_predictions": STAGE006_PREDICTIONS,
        "stage006_review_receipt": STAGE006_REVIEW_RECEIPT,
        "stage007_preregistration": PREREGISTRATION_PATH,
        "stage007_runner": Path(__file__).resolve(),
        "candidate_eligibility": CANDIDATE_ELIGIBILITY,
        "python_executable": Path(sys.executable).resolve(),
    }
    pyvenv = Path(sys.prefix) / "pyvenv.cfg"
    if pyvenv.is_file():
        files["python_pyvenv_cfg"] = pyvenv
    _add_tree_files(
        files,
        prefix="production_portfolio",
        root=PORTFOLIO_DIR,
        suffixes={".py"},
    )
    _add_tree_files(
        files,
        prefix="formal_release",
        root=stage004.FORMAL_RELEASE,
        suffixes=None,
    )
    _add_tree_files(
        files,
        prefix="workspace_vnpy_core",
        root=WORKSPACE_ROOT / "vnpy",
        suffixes={".py"},
    )
    portfolio_spec = importlib.util.find_spec("vnpy_portfoliostrategy")
    if portfolio_spec is None or portfolio_spec.origin is None:
        raise RuntimeError("vnpy_portfoliostrategy_not_found")
    portfolio_package = Path(portfolio_spec.origin).resolve().parent
    _add_tree_files(
        files,
        prefix="vnpy_portfoliostrategy",
        root=portfolio_package,
        suffixes={".py", ".so", ".dylib"},
    )
    _distribution_metadata_files(files)
    return files


def collect_runtime_contract() -> dict[str, Any]:
    packages = package_version_rows()
    packages_encoded = json.dumps(
        packages,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    repository = assert_repository_state()
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
            )
        },
        "repository": repository,
        "packages": packages,
        "packages_sha256": hashlib.sha256(packages_encoded).hexdigest(),
    }


def validate_runtime_stability(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> None:
    for key, expected_value in expected.items():
        if key == "sys_path":
            continue
        if actual.get(key) != expected_value:
            raise RuntimeError(f"runtime_contract_changed:{key}")


def current_identity_manifest() -> dict[str, Any]:
    return build_identity_manifest(
        collect_identity_files(),
        runtime=collect_runtime_contract(),
    )


def identity_manifest_with_frozen_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    current_runtime = collect_runtime_contract()
    validate_runtime_stability(runtime, current_runtime)
    return build_identity_manifest(collect_identity_files(), runtime=runtime)


def _verify_database_identity(manifest: dict[str, Any]) -> None:
    actual = manifest["files"]["runtime_database"]["sha256"]
    if actual != EXPECTED_DATABASE_SHA256:
        raise RuntimeError(f"runtime_database_identity_drift:{actual}")


def database_boundary_parity(
    live_path: Path,
    frozen_path: Path,
    end_datetime: str,
) -> dict[str, Any]:
    columns = (
        "symbol,exchange,datetime,interval,volume,turnover,open_interest,"
        "open_price,high_price,low_price,close_price"
    )
    connection = sqlite3.connect(f"file:{live_path.resolve()}?mode=ro", uri=True)
    try:
        connection.execute(
            "ATTACH DATABASE ? AS frozen",
            (f"file:{frozen_path.resolve()}?mode=ro",),
        )
        live_rows = int(
            connection.execute(
                "SELECT COUNT(*) FROM main.dbbardata WHERE datetime <= ?",
                (end_datetime,),
            ).fetchone()[0]
        )
        frozen_rows = int(
            connection.execute(
                "SELECT COUNT(*) FROM frozen.dbbardata WHERE datetime <= ?",
                (end_datetime,),
            ).fetchone()[0]
        )
        live_minus_frozen = int(
            connection.execute(
                f"SELECT COUNT(*) FROM ("
                f"SELECT {columns} FROM main.dbbardata WHERE datetime <= ? "
                f"EXCEPT SELECT {columns} FROM frozen.dbbardata WHERE datetime <= ?)",
                (end_datetime, end_datetime),
            ).fetchone()[0]
        )
        frozen_minus_live = int(
            connection.execute(
                f"SELECT COUNT(*) FROM ("
                f"SELECT {columns} FROM frozen.dbbardata WHERE datetime <= ? "
                f"EXCEPT SELECT {columns} FROM main.dbbardata WHERE datetime <= ?)",
                (end_datetime, end_datetime),
            ).fetchone()[0]
        )
        live_max_datetime = connection.execute(
            "SELECT MAX(datetime) FROM main.dbbardata"
        ).fetchone()[0]
        frozen_max_datetime = connection.execute(
            "SELECT MAX(datetime) FROM frozen.dbbardata"
        ).fetchone()[0]
    finally:
        connection.close()
    passed = (
        live_rows == frozen_rows
        and live_minus_frozen == 0
        and frozen_minus_live == 0
    )
    return {
        "passed": passed,
        "boundary_end": end_datetime,
        "live_rows": live_rows,
        "frozen_rows": frozen_rows,
        "live_minus_frozen": live_minus_frozen,
        "frozen_minus_live": frozen_minus_live,
        "live_max_datetime": live_max_datetime,
        "frozen_max_datetime": frozen_max_datetime,
        "live_sha256_at_check": _file_identity(live_path)["sha256"],
        "frozen_sha256": _file_identity(frozen_path)["sha256"],
    }


def build_candidate() -> tuple[pd.DataFrame, pd.DataFrame]:
    stage004 = _load_stage004()
    upstream = json.loads(STAGE006_SUMMARY.read_text())
    validate_stage006_upstream(upstream)
    review_receipt = json.loads(STAGE006_REVIEW_RECEIPT.read_text())
    validate_stage006_review_receipt(
        review_receipt,
        expected_summary_sha256=_file_identity(STAGE006_SUMMARY)["sha256"],
    )
    formal = pd.read_csv(stage004.FORMAL_ELIGIBILITY)
    predictions = pd.read_csv(STAGE006_PREDICTIONS)
    original_score_type = stage004.CANDIDATE_SCORE_TYPE
    try:
        stage004.CANDIDATE_SCORE_TYPE = CANDIDATE_SCORE_TYPE
        candidate, audit = stage004.build_candidate_eligibility(
            formal,
            predictions,
            expected_oos_months=EXPECTED_OOS_MONTHS,
        )
    finally:
        stage004.CANDIDATE_SCORE_TYPE = original_score_type
    audit = audit.copy()
    audit["source"] = audit["source"].replace("stage003_oos", "stage006_oos")
    oos_dates = audit.loc[audit["source"].eq("stage006_oos"), "eval_date"].tolist()
    if (
        len(oos_dates) != EXPECTED_OOS_MONTHS
        or min(oos_dates) != EXPECTED_FIRST_OOS_DATE
        or max(oos_dates) != EXPECTED_LAST_OOS_DATE
    ):
        raise RuntimeError(
            f"stage007_oos_boundary_drift:{len(oos_dates)}:{min(oos_dates)}:{max(oos_dates)}"
        )
    return candidate, audit


def _arm_directory(arm: str) -> Path:
    if arm not in ARM_SEQUENCE:
        raise ValueError(f"unknown_arm:{arm}")
    return ARMS_DIR / arm


def _read_arm(arm: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    directory = _arm_directory(arm)
    return (
        pd.read_csv(directory / "summary.csv"),
        pd.read_csv(directory / "curve.csv"),
        pd.read_csv(directory / "trades.csv"),
    )


def _run_worker(arm: str) -> None:
    if Path.cwd().resolve() != RUNTIME_ROOT.resolve():
        raise RuntimeError(f"stage007_worker_wrong_runtime:{Path.cwd().resolve()}")
    if CHECKPOINT_REUSE_ALLOWED:
        raise RuntimeError("stage007_checkpoint_reuse_must_remain_disabled")
    directory = _arm_directory(arm)
    assert_cold_arm_output(directory)
    expected_contract = os.environ.get("STAGE007_CONTRACT_SHA256", "")
    if not expected_contract:
        raise RuntimeError("stage007_worker_contract_missing")
    before = current_identity_manifest()
    _verify_database_identity(before)
    if before["contract_sha256"] != expected_contract:
        raise RuntimeError(
            f"stage007_worker_contract_drift_before:{before['contract_sha256']}:{expected_contract}"
        )

    stage004 = _load_stage004()
    live_cfg, s513, s827, s901 = stage004._load_production_modules()
    if live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_ID != FORMAL_RELEASE_ID:
        raise RuntimeError("stage007_active_release_drift")
    if Path(live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve() != stage004.FORMAL_ELIGIBILITY.resolve():
        raise RuntimeError("stage007_formal_eligibility_resolution_drift")
    metadata = s513._metadata()
    official_builder = live_cfg.build_official_live_strategy_overrides

    def candidate_builder() -> dict[str, Any]:
        overrides = dict(official_builder())
        overrides["ai_product_pool_eligibility_path"] = str(CANDIDATE_ELIGIBILITY.resolve())
        overrides["ai_product_pool_strategy"] = stage004.OFFICIAL_STRATEGY
        return overrides

    builder = candidate_builder if arm == "C" else official_builder
    profile_name = (
        "stage007_C_stage006_pit_confirmed_xgboost_pool"
        if arm == "C"
        else f"stage007_{arm}_official_logistic_pool"
    )
    label = (
        "C Stage006 PIT-confirmed XGBoost pool"
        if arm == "C"
        else f"{arm} formal AI pool"
    )
    original_builder = s901.build_official_live_strategy_overrides
    try:
        s901.build_official_live_strategy_overrides = builder
        combined, frames, live_spec = s901._run_live_c9(
            metadata,
            stage004.START,
            stage004.END,
        )
    finally:
        s901.build_official_live_strategy_overrides = original_builder
    capital = replace(live_spec.capital, variant=profile_name, label=label)
    metric_spec = replace(live_spec, capital=capital, profile=profile_name)
    summary, curve = s827._metric(
        {"profile": profile_name, "spec": metric_spec},
        combined,
    )
    summary["experiment_arm"] = arm
    summary["window_name"] = "full_2018_20260828"
    curve["experiment_arm"] = arm
    trades = frames.get("trades", pd.DataFrame()).copy()
    trades["experiment_arm"] = arm

    after = identity_manifest_with_frozen_runtime(before["runtime"])
    _verify_database_identity(after)
    if after["contract_sha256"] != expected_contract or before != after:
        raise RuntimeError("stage007_worker_input_identity_changed")
    directory.mkdir(parents=True, exist_ok=False)
    summary.to_csv(directory / "summary.csv", index=False)
    curve.to_csv(directory / "curve.csv", index=False)
    trades.to_csv(directory / "trades.csv", index=False)
    (directory / "worker_receipt.json").write_text(
        json.dumps(
            {
                "arm": arm,
                "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "contract_sha256": expected_contract,
                "checkpoint_reused": False,
                "fresh_process_pid": os.getpid(),
                "input_identity_pass": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    payload = summary.iloc[0]
    print(
        json.dumps(
            {
                "worker_arm": arm,
                "end_equity": float(payload["end_equity"]),
                "total_return_pct": float(payload["total_return_pct"]),
                "max_dd_pct": float(payload["max_dd_pct"]),
                "sharpe": float(payload["sharpe"]),
                "total_slippage": float(payload["total_slippage"]),
                "total_trade_count": float(payload["total_trade_count"]),
                "contract_sha256": expected_contract,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    del combined, frames
    gc.collect()


def _run_worker_subprocess(arm: str, contract_sha256: str) -> None:
    directory = _arm_directory(arm)
    assert_cold_arm_output(directory)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    (TMP_ROOT / "mplconfig").mkdir(parents=True, exist_ok=True)
    (TMP_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    environment = worker_environment(os.environ, TMP_ROOT)
    environment["STAGE007_CONTRACT_SHA256"] = contract_sha256
    completed = subprocess.run(
        worker_command(Path(__file__).resolve(), arm),
        cwd=RUNTIME_ROOT,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"stage007_worker_failed:{arm}:{completed.returncode}")
    receipt = json.loads((directory / "worker_receipt.json").read_text())
    if receipt.get("checkpoint_reused") is not False:
        raise RuntimeError(f"stage007_worker_checkpoint_contract_failed:{arm}")
    if receipt.get("contract_sha256") != contract_sha256:
        raise RuntimeError(f"stage007_worker_receipt_contract_drift:{arm}")


def _metrics(frame: pd.DataFrame, arm: str, columns: list[str]) -> dict[str, float]:
    row = frame.iloc[0]
    return {column: float(row[column]) for column in columns} | {"arm": arm}


def _report(
    summary: pd.DataFrame,
    repeat: dict[str, Any],
    qualification: dict[str, Any],
) -> str:
    indexed = summary.set_index("experiment_arm")
    lines = [
        "# Stage007 冷进程全周期真引擎A/A/C",
        "",
        f"- 决策：`{'PASS' if qualification['passed'] else 'FAIL'}`",
        f"- A1/A2逐日逐笔确定性：`{'PASS' if repeat['passed'] else 'FAIL'}`",
        "- A1、A2、C均为独立python -B冷进程；checkpoint复用为false。",
        "- 49个月候选仍是开发样本，不是独立最终OOS。",
        "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 交易次数 | 胜率 | broker10峰值 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, label in (("A1", "A正式逻辑回归池"), ("C", "C Stage006 XGBoost池")):
        row = indexed.loc[arm]
        lines.append(
            f"| {label} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | "
            f"{row['total_slippage']:,.0f} | {int(row['total_trade_count'])} | "
            f"{row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% |"
        )
    lines.extend(["", "## 预声明全周期门", ""])
    for name, passed in qualification["gates"].items():
        lines.append(f"- `{'PASS' if passed else 'FAIL'}` `{name}`")
    lines.extend(
        [
            "",
            "- 离线研究；未连接CTP，未调用订单API，未修改生产目录，未自动晋升。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_stop_decision(name: str, payload: dict[str, Any]) -> None:
    decision = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": name,
        **payload,
        "safety": {
            "writes_production": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "automatic_promotion": False,
        },
    }
    (OUT / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )


def _preflight() -> dict[str, Any]:
    if Path.cwd().resolve() != RUNTIME_ROOT.resolve():
        raise RuntimeError(f"stage007_wrong_runtime:{Path.cwd().resolve()}")
    if os.environ.get("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR") != "1":
        raise RuntimeError("stage007_runtime_guard_override_missing")
    if OUT.exists():
        raise RuntimeError(f"stage007_output_already_exists:{OUT}")
    upstream = json.loads(STAGE006_SUMMARY.read_text())
    validate_stage006_upstream(upstream)
    repository = assert_repository_state()
    candidate, audit = build_candidate()
    runtime_database = _file_identity(RUNTIME_DATABASE)
    if runtime_database["sha256"] != EXPECTED_DATABASE_SHA256:
        raise RuntimeError("stage007_runtime_database_drift")
    boundary_parity = database_boundary_parity(
        PRODUCTION_ROOT / ".vntrader/database.db",
        RUNTIME_DATABASE,
        "2026-08-28 23:59:59",
    )
    if not boundary_parity["passed"]:
        raise RuntimeError(f"stage007_database_boundary_drift:{boundary_parity}")
    return {
        "repository": repository,
        "candidate_rows": len(candidate),
        "candidate_dates": int(candidate["eval_date"].nunique()),
        "oos_months": int(audit["source"].eq("stage006_oos").sum()),
        "mean_changed_member_count_vs_formal": float(
            audit.loc[audit["source"].eq("stage006_oos"), "changed_member_count"].mean()
        ),
        "runtime_database_sha256": runtime_database["sha256"],
        "production_vs_runtime_boundary_parity": boundary_parity,
        "checkpoint_reuse_allowed": CHECKPOINT_REUSE_ALLOWED,
        "arm_sequence": list(ARM_SEQUENCE),
    }


def _orchestrate() -> None:
    preflight = _preflight()
    candidate, audit = build_candidate()
    OUT.mkdir(parents=True, exist_ok=False)
    candidate.to_csv(CANDIDATE_ELIGIBILITY, index=False)
    audit.to_csv(MEMBERSHIP_AUDIT, index=False)
    before = current_identity_manifest()
    _verify_database_identity(before)
    IDENTITY_BEFORE.write_text(
        json.dumps(before, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    contract = before["contract_sha256"]

    _run_worker_subprocess("A1", contract)
    after_a1 = current_identity_manifest()
    if after_a1 != before:
        raise RuntimeError("stage007_identity_changed_after_A1")
    _run_worker_subprocess("A2", contract)
    after_a2 = current_identity_manifest()
    if after_a2 != before:
        raise RuntimeError("stage007_identity_changed_after_A2")

    stage005 = _load_stage005()
    a1_summary, a1_curve, a1_trades = _read_arm("A1")
    a2_summary, a2_curve, a2_trades = _read_arm("A2")
    repeat = stage005.compare_baseline_repeat(
        a1_summary,
        a2_summary,
        a1_curve,
        a2_curve,
        a1_trades,
        a2_trades,
    )
    (OUT / "baseline_repeat.json").write_text(
        json.dumps(repeat, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    if not repeat["passed"]:
        _write_stop_decision(
            "stage007_cold_baseline_nondeterministic_stop_before_candidate",
            {"baseline_repeat": repeat, "preflight": preflight},
        )
        raise RuntimeError("stage007_cold_baseline_repeat_failed")

    _run_worker_subprocess("C", contract)
    after_c = current_identity_manifest()
    input_identity_pass = after_c == before
    if not input_identity_pass:
        raise RuntimeError("stage007_identity_changed_after_C")
    boundary_parity_after = database_boundary_parity(
        PRODUCTION_ROOT / ".vntrader/database.db",
        RUNTIME_DATABASE,
        "2026-08-28 23:59:59",
    )
    if not boundary_parity_after["passed"]:
        raise RuntimeError(f"stage007_database_boundary_changed_after_C:{boundary_parity_after}")
    c_summary, c_curve, c_trades = _read_arm("C")

    stage004 = _load_stage004()
    coverage = stage004._coverage({"A": a1_curve, "C": c_curve})
    baseline_row = a1_summary.iloc[0]
    candidate_row = c_summary.iloc[0]
    qualification = stage004.evaluate_fullperiod_gates(
        baseline_row,
        candidate_row,
        baseline_reproduction_pass=repeat["passed"],
        coverage_pass=coverage["passed"],
        input_identity_pass=input_identity_pass,
    )
    decision_name = (
        "stage007_fullperiod_pass_allow_robustness_not_promotion"
        if qualification["passed"]
        else "stage007_fullperiod_fail_stop_xgboost_c3"
    )
    summary = pd.concat([a1_summary, a2_summary, c_summary], ignore_index=True)
    curves = pd.concat([a1_curve, a2_curve, c_curve], ignore_index=True)
    trades = pd.concat([a1_trades, a2_trades, c_trades], ignore_index=True)
    metrics_columns = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "account_survival_pass",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    ]
    metrics = {
        arm: _metrics(frame, arm, metrics_columns)
        for arm, frame in (("A1", a1_summary), ("A2", a2_summary), ("C", c_summary))
    }
    decision = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision_name,
        "formal_release_id": FORMAL_RELEASE_ID,
        "status_scope": "development_candidate_not_independent_final_oos",
        "preflight": preflight,
        "identity_contract_sha256": contract,
        "input_identity_pass": input_identity_pass,
        "production_vs_runtime_boundary_parity_before": preflight[
            "production_vs_runtime_boundary_parity"
        ],
        "production_vs_runtime_boundary_parity_after": boundary_parity_after,
        "checkpoint_reuse_allowed": CHECKPOINT_REUSE_ALLOWED,
        "arm_sequence": list(ARM_SEQUENCE),
        "baseline_repeat": repeat,
        "coverage": coverage,
        "qualification": qualification,
        "metrics": metrics,
        "candidate_pool": {
            "oos_months": int(audit["source"].eq("stage006_oos").sum()),
            "first_oos_date": EXPECTED_FIRST_OOS_DATE,
            "last_oos_date": EXPECTED_LAST_OOS_DATE,
            "mean_changed_member_count_vs_formal": float(
                audit.loc[
                    audit["source"].eq("stage006_oos"),
                    "changed_member_count",
                ].mean()
            ),
            "pre_and_post_oos_formal_rows_preserved": True,
            "fixed_fu_rank": 11,
        },
        "adaptive_reuse_warning": (
            "Stage001-003 used the same 49 months adaptively; even a Stage007 pass "
            "requires untouched or new forward shadow evidence"
        ),
        "safety": {
            "strategy_backtest_ran": True,
            "writes_production": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "automatic_promotion": False,
        },
    }
    summary.to_csv(OUT / "summary.csv", index=False)
    curves.to_csv(OUT / "equity_curve.csv", index=False)
    trades.to_csv(OUT / "trades.csv", index=False)
    (OUT / "identity_manifest_after.json").write_text(
        json.dumps(after_c, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    (OUT / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    (OUT / "report.md").write_text(_report(summary, repeat, qualification))
    print(
        json.dumps(
            {
                "decision": decision_name,
                "identity_contract_sha256": contract,
                "baseline_repeat": repeat,
                "metrics": metrics,
                "qualification": qualification,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--worker", choices=ARM_SEQUENCE)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.worker:
        _run_worker(args.worker)
        return
    if args.preflight:
        print(json.dumps(_preflight(), ensure_ascii=False, indent=2))
        return
    _orchestrate()


if __name__ == "__main__":
    main()

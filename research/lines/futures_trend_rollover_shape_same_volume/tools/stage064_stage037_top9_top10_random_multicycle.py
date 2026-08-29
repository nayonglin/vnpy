from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime
import gzip
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from random import Random
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for directory in (TOOLS_DIR, PORTFOLIO_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import stage029_stage028_multicycle_abc as s29  # noqa: E402
import stage063_stage037_top9_top10_multicycle as s63  # noqa: E402


LINE_ID = "futures_trend_rollover_shape_same_volume"
STAGE = "Stage064"
LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage064_stage037_top9_top10_random_multicycle"
INPUT_DIR = LINE_DIR / "inputs"
WINDOW_PLAN_PATH = INPUT_DIR / "stage064_stage037_top9_top10_random_windows.csv"
CHECKPOINT_DIR = PROJECT_DIR / ".tools" / "stage064_random_multicycle_checkpoints"
CHECKPOINT_INPUT_DIR = CHECKPOINT_DIR / "inputs"
STAGE063_SOURCE_COMMIT = "81bb5e5779caf545513770e6afb157be89fea09e"
STAGE063_DIR = s63.OUTPUT_DIR
STAGE061_DIR = s63.s61.OUTPUT_DIR
STAGE062_DIR = s63.s62.OUTPUT_DIR

DURATIONS_YEARS = (1, 2, 3)
SAMPLES_PER_DURATION = 64
EXPECTED_RANDOM_WINDOW_COUNT = len(DURATIONS_YEARS) * SAMPLES_PER_DURATION
EXPECTED_ENGINE_RUN_COUNT = EXPECTED_RANDOM_WINDOW_COUNT * 3
ARMS = s63.ARMS
COMPARISONS = s63.COMPARISONS
DATA_START = s63.DATA_START
DATA_END = s63.DATA_END
USER_OFFLINE_OVERRIDE = (
    "2026-08-29 user authorized continuing offline Stage037 comparisons despite "
    "stable production remaining Stage021-Q; Stage064 only adds frozen random windows"
)
RENDER_ARMS = tuple(
    {
        **arm,
        "plot_label": {
            "A": "Formal Stage037 Top8+fu",
            "B": "Top9+fu",
            "C": "Top10+fu",
        }[arm["arm"]],
    }
    for arm in ARMS
)

CHART_FILES = {
    "full_period": "stage064_full_period_equity_abc.png",
    "1y": "stage064_random_equity_fan_1y_abc.png",
    "2y": "stage064_random_equity_fan_2y_abc.png",
    "3y": "stage064_random_equity_fan_3y_abc.png",
    "aggregate": "stage064_random_aggregate_abc.png",
}
SUMMARY_NAME = "stage064_random_window_summary.csv"
COMPARISON_NAME = "stage064_random_window_comparison.csv"
AGGREGATE_NAME = "stage064_random_cycle_aggregate.csv"
CURVE_NAME = "stage064_random_equity_curves.csv.gz"
DECISION_NAME = "stage064_decision.json"
REPORT_NAME = "stage064_random_multicycle_report.md"
REUSE_SOURCE_PATHS = (
    STAGE063_DIR / s63.DECISION_NAME,
    STAGE063_DIR / s63.SUMMARY_NAME,
    STAGE063_DIR / s63.CURVE_NAME,
    STAGE061_DIR / s63.s61.ELIGIBILITY_NAME,
    STAGE062_DIR / s63.s62.ELIGIBILITY_NAME,
)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gzip_uncompressed_sha256(path: Path) -> str:
    digest = sha256()
    with gzip.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(payload: dict[str, Any]) -> str:
    return sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _git_blob_sha256(commit: str, path: Path) -> str:
    relative = path.resolve().relative_to(PROJECT_DIR.resolve())
    payload = subprocess.run(
        ["git", "show", f"{commit}:{relative.as_posix()}"],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
    ).stdout
    return sha256(payload).hexdigest()


def _assert_reuse_sources_frozen() -> dict[str, Any]:
    source_dirs = sorted({str(path.parent.relative_to(PROJECT_DIR)) for path in REUSE_SOURCE_PATHS})
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *source_dirs],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if untracked:
        raise RuntimeError(f"stage064_reuse_source_untracked_drift:{untracked}")
    files: dict[str, dict[str, str]] = {}
    for path in REUSE_SOURCE_PATHS:
        relative = str(path.resolve().relative_to(PROJECT_DIR.resolve()))
        workspace_sha = _file_sha256(path)
        git_blob_sha = _git_blob_sha256(STAGE063_SOURCE_COMMIT, path)
        if workspace_sha != git_blob_sha:
            raise RuntimeError(
                "stage064_reuse_source_git_drift:"
                f"{relative}:workspace={workspace_sha}:git={git_blob_sha}"
            )
        files[relative] = {
            "workspace_sha256": workspace_sha,
            "git_blob_sha256": git_blob_sha,
        }
    return {"commit": STAGE063_SOURCE_COMMIT, "files": files}


def _derive_random_seed(source_commit: str, database_sha256: str) -> int:
    material = f"{STAGE}|{source_commit}|{database_sha256}|random-start-v1"
    return int.from_bytes(sha256(material.encode("utf-8")).digest()[:8], "big")


def _build_random_windows(
    trading_dates: pd.DatetimeIndex,
    seed: int,
    samples_per_duration: int = SAMPLES_PER_DURATION,
) -> pd.DataFrame:
    dates = pd.DatetimeIndex(pd.to_datetime(trading_dates)).normalize().drop_duplicates()
    if not dates.is_monotonic_increasing:
        dates = dates.sort_values()
    if dates.empty:
        raise RuntimeError("stage064_no_trading_dates")
    rng = Random(int(seed))
    rows: list[dict[str, Any]] = []
    data_end = dates[-1]
    for years in DURATIONS_YEARS:
        valid = [
            date
            for date in dates
            if date + pd.DateOffset(years=years) - pd.Timedelta(days=1) <= data_end
        ]
        if len(valid) < samples_per_duration:
            raise RuntimeError(
                f"stage064_insufficient_random_starts:{years}:{len(valid)}:{samples_per_duration}"
            )
        for draw_index, start in enumerate(rng.sample(valid, samples_per_duration), start=1):
            end = start + pd.DateOffset(years=years) - pd.Timedelta(days=1)
            rows.append(
                {
                    "window_id": f"random_{years}y_{draw_index:03d}_{start.strftime('%Y%m%d')}",
                    "window_group": f"random_{years}y",
                    "duration_years": years,
                    "draw_index": draw_index,
                    "requested_start": str(start.date()),
                    "requested_end": str(end.date()),
                    "start_month_num": int(start.month),
                    "complete_window": 1,
                    "terminal_near_complete": 0,
                }
            )
    return pd.DataFrame(rows)


def _freeze_window_plan(
    trading_dates: pd.DatetimeIndex,
    database_sha256: str,
    path: Path = WINDOW_PLAN_PATH,
) -> dict[str, Any]:
    seed = _derive_random_seed(STAGE063_SOURCE_COMMIT, database_sha256)
    plan = _build_random_windows(trading_dates, seed)
    plan.insert(0, "random_seed", seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    plan.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)
    return {
        "random_seed": seed,
        "window_count": len(plan),
        "plan_sha256": _file_sha256(path),
    }


def _load_frozen_window_plan(
    path: Path,
    trading_dates: pd.DatetimeIndex,
    expected_seed: int,
) -> pd.DataFrame:
    plan = pd.read_csv(path)
    required = {
        "random_seed",
        "window_id",
        "window_group",
        "duration_years",
        "draw_index",
        "requested_start",
        "requested_end",
        "start_month_num",
        "complete_window",
        "terminal_near_complete",
    }
    if set(plan.columns) != required:
        raise RuntimeError(f"stage064_window_plan_columns:{sorted(plan.columns)}")
    if len(plan) != EXPECTED_RANDOM_WINDOW_COUNT:
        raise RuntimeError(f"stage064_window_plan_count:{len(plan)}")
    if plan["window_id"].duplicated().any():
        raise RuntimeError("stage064_window_plan_duplicate")
    if not pd.to_numeric(plan["random_seed"], errors="raise").eq(expected_seed).all():
        raise RuntimeError("stage064_window_plan_seed_drift")
    counts = plan.groupby("duration_years").size().to_dict()
    if counts != {years: SAMPLES_PER_DURATION for years in DURATIONS_YEARS}:
        raise RuntimeError(f"stage064_window_plan_horizon_count:{counts}")
    date_set = set(pd.DatetimeIndex(pd.to_datetime(trading_dates)).strftime("%Y-%m-%d"))
    if not plan["requested_start"].astype(str).isin(date_set).all():
        raise RuntimeError("stage064_window_plan_nontrading_start")
    for row in plan.itertuples(index=False):
        start = pd.Timestamp(row.requested_start)
        expected_end = start + pd.DateOffset(years=int(row.duration_years)) - pd.Timedelta(days=1)
        if str(expected_end.date()) != str(row.requested_end):
            raise RuntimeError(f"stage064_window_plan_end_drift:{row.window_id}")
        if int(row.start_month_num) != int(start.month):
            raise RuntimeError(f"stage064_window_plan_month_drift:{row.window_id}")
        if int(row.complete_window) != 1 or int(row.terminal_near_complete) != 0:
            raise RuntimeError(f"stage064_window_plan_incomplete:{row.window_id}")
    return plan


def _random_aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        selected = comparison[comparison["comparison"].astype(str).eq(comparison_name)]
        if selected.empty:
            continue
        rows.append(s29._aggregate_row(comparison_name, 0, "random_all", selected))
        for years in DURATIONS_YEARS:
            group = selected[selected["duration_years"].eq(years)]
            if group.empty:
                raise RuntimeError(f"stage064_missing_random_horizon:{comparison_name}:{years}")
            rows.append(s29._aggregate_row(comparison_name, years, "random", group))
    if not rows:
        raise RuntimeError("stage064_no_random_comparison_rows")
    return pd.DataFrame(rows)


def _random_cycle_gates(row: dict[str, Any]) -> dict[str, bool]:
    gates = s29._cycle_gates(row)
    gates["aggregate_slippage_le_105pct"] = gates.pop("slippage_ratio_le_105pct")
    return gates


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_DIR, check=True, capture_output=True, text=True
    ).stdout.strip()


def _write_canonical_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def _source_decision() -> dict[str, Any]:
    return json.loads((STAGE063_DIR / s63.DECISION_NAME).read_text(encoding="utf-8"))


def _trading_dates() -> pd.DatetimeIndex:
    curve = pd.read_csv(STAGE063_DIR / s63.CURVE_NAME, low_memory=False)
    selected = curve[
        curve["window_group"].astype(str).eq("full_period")
        & curve["promotion_arm"].astype(str).eq("A")
    ]
    dates = pd.DatetimeIndex(pd.to_datetime(selected["date"], errors="raise")).normalize()
    dates = dates.drop_duplicates().sort_values()
    if len(dates) != 2101 or dates[0] > DATA_START + pd.Timedelta(days=7) or dates[-1] != DATA_END:
        raise RuntimeError(
            f"stage064_trading_date_source_drift:{len(dates)}:{dates[0]}:{dates[-1]}"
        )
    return dates


def _prepare_eligibility_paths() -> dict[str, Path]:
    top9 = pd.read_csv(STAGE062_DIR / s63.s62.ELIGIBILITY_NAME)
    all_topn = pd.read_csv(STAGE061_DIR / s63.s61.ELIGIBILITY_NAME)
    top10 = all_topn[pd.to_numeric(all_topn["requested_top_n"]).eq(10)].copy()
    if len(top9) != 568 or len(top10) != 623:
        raise RuntimeError(
            f"stage064_eligibility_count_drift:top9={len(top9)}:top10={len(top10)}"
        )
    paths = {
        "B": CHECKPOINT_INPUT_DIR / "stage064_top9_eligibility.csv",
        "C": CHECKPOINT_INPUT_DIR / "stage064_top10_eligibility.csv",
    }
    _write_canonical_csv(top9, paths["B"])
    _write_canonical_csv(top10, paths["C"])
    return paths


def _window_plan_git_contract() -> dict[str, str]:
    relative = WINDOW_PLAN_PATH.resolve().relative_to(PROJECT_DIR.resolve())
    commit = _git("log", "-1", "--format=%H", "--", relative.as_posix())
    if not commit:
        raise RuntimeError("stage064_window_plan_not_committed")
    workspace_sha = _file_sha256(WINDOW_PLAN_PATH)
    git_blob_sha = _git_blob_sha256(commit, WINDOW_PLAN_PATH)
    if workspace_sha != git_blob_sha:
        raise RuntimeError(
            f"stage064_window_plan_git_drift:workspace={workspace_sha}:git={git_blob_sha}"
        )
    return {
        "commit": commit,
        "path": relative.as_posix(),
        "workspace_sha256": workspace_sha,
        "git_blob_sha256": git_blob_sha,
    }


def _runtime_contract_hash(
    eligibility_paths: dict[str, Path], plan_contract: dict[str, str]
) -> str:
    digest = sha256(b"stage064_random_multicycle_runtime_v1")
    for path in (
        Path(__file__),
        Path(s63.__file__),
        Path(s63.s56.__file__),
        Path(s63.s61.candidate_cfg.__file__),
        Path(s63.s62.candidate_cfg.__file__),
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_portfolio_strategy.py",
        *REUSE_SOURCE_PATHS,
        WINDOW_PLAN_PATH,
        eligibility_paths["B"],
        eligibility_paths["C"],
    ):
        digest.update(str(path.resolve()).encode("utf-8"))
        digest.update(path.read_bytes())
    digest.update(json.dumps(plan_contract, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def _preflight() -> tuple[dict[str, Any], dict[str, Path], pd.DataFrame]:
    reuse_contract = _assert_reuse_sources_frozen()
    source_decision = _source_decision()
    database_sha = _file_sha256(s63.s56.DATABASE_PATH)
    expected_database_sha = str(source_decision["identity"]["database_sha256"])
    if database_sha != expected_database_sha:
        raise RuntimeError(
            f"stage064_database_drift:actual={database_sha}:expected={expected_database_sha}"
        )
    dates = _trading_dates()
    expected_seed = _derive_random_seed(STAGE063_SOURCE_COMMIT, database_sha)
    plan = _load_frozen_window_plan(WINDOW_PLAN_PATH, dates, expected_seed)
    plan_contract = _window_plan_git_contract()
    eligibility_paths = _prepare_eligibility_paths()

    checkout = asdict(s63.s56.assert_official_checkout_matches_active_material(PROJECT_DIR))
    production = asdict(
        s63.s56.assert_official_checkout_matches_active_material(s63.s56.PRODUCTION_ROOT)
    )
    remote_master = _git("rev-parse", "origin/master")
    identity = s63._assert_offline_identity_contract(checkout, production, remote_master)
    if not identity["user_authorized_offline_identity_override"]:
        raise RuntimeError("stage064_expected_offline_identity_override_missing")
    identity["user_authorized_offline_identity_override_reason"] = USER_OFFLINE_OVERRIDE
    for arm, path in eligibility_paths.items():
        diff = {
            key
            for key, values in (
                s63.s62.candidate_cfg.override_diff(path).items()
                if arm == "B"
                else s63.s61.candidate_cfg.override_diff(10, path).items()
            )
            if values[0] != values[1]
        }
        if diff != {"ai_product_pool_eligibility_path", "ai_product_pool_strategy"}:
            raise RuntimeError(f"stage064_candidate_scope_drift:{arm}:{sorted(diff)}")
    return (
        {
            **identity,
            "checkout_identity": checkout,
            "production_identity": production,
            "checkout_head": _git("rev-parse", "HEAD"),
            "production_head": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=s63.s56.PRODUCTION_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "remote_master": remote_master,
            "database_path": str(s63.s56.DATABASE_PATH.resolve()),
            "database_sha256": database_sha,
            "random_seed": expected_seed,
            "window_plan": plan_contract,
            "reuse_source_contract": reuse_contract,
            "eligibility_sha256": {
                arm: _file_sha256(path) for arm, path in eligibility_paths.items()
            },
            "runtime_contract_sha256": _runtime_contract_hash(
                eligibility_paths, plan_contract
            ),
        },
        eligibility_paths,
        plan,
    )


def _window_dict(row: Any) -> dict[str, Any]:
    return {
        "window_id": str(row.window_id),
        "window_group": str(row.window_group),
        "duration_years": int(row.duration_years),
        "start": pd.Timestamp(row.requested_start),
        "end": pd.Timestamp(row.requested_end),
        "start_month_num": int(row.start_month_num),
        "complete": True,
        "terminal_near_complete": False,
        "draw_index": int(row.draw_index),
    }


def _window_common(window: dict[str, Any], arm: str) -> dict[str, Any]:
    start, end = pd.Timestamp(window["start"]), pd.Timestamp(window["end"])
    return {
        "window_id": str(window["window_id"]),
        "window_group": str(window["window_group"]),
        "duration_years": int(window["duration_years"]),
        "requested_start": str(start.date()),
        "requested_end": str(end.date()),
        "complete_window": 1,
        "terminal_near_complete": 0,
        "promotion_arm": arm,
        "window_name": str(window["window_id"]),
        "window_label": f"{start.date()} random independent start to {end.date()}",
        "requested_start_month": start.strftime("%Y-%m"),
        "start_month": start.strftime("%Y-%m"),
        "start_year": int(start.year),
        "start_month_num": int(start.month),
        "random_draw_index": int(window["draw_index"]),
    }


def _arm_overrides(arm: str, eligibility_paths: dict[str, Path]) -> dict[str, Any]:
    if arm == "A":
        return s63.s56.candidate_cfg.live_cfg.build_official_live_strategy_overrides()
    return s63._candidate_overrides(arm, eligibility_paths[arm])


def _run_window(
    metadata: dict[str, Any],
    window: dict[str, Any],
    arm: dict[str, Any],
    eligibility_paths: dict[str, Path],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    original_builder = s63.s56.s28.s901.build_official_live_strategy_overrides
    try:
        s63.s56.s28.s901.build_official_live_strategy_overrides = lambda: _arm_overrides(
            arm["arm"], eligibility_paths
        )
        combined, _frames, live_spec = s63.s56.s28.s901._run_live_c9(
            metadata, pd.Timestamp(window["start"]), pd.Timestamp(window["end"])
        )
    finally:
        s63.s56.s28.s901.build_official_live_strategy_overrides = original_builder
    profile = f"stage064_{arm['arm']}_{window['window_id']}"
    capital = replace(live_spec.capital, variant=profile, label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=profile)
    summary, curve = s63.s56.s28.s827._metric(
        {"profile": profile, "spec": metric_spec}, combined
    )
    summary["experiment_arm"] = arm["arm"]
    curve["experiment_arm"] = arm["arm"]
    summary["arm"] = arm["arm"]
    curve["arm"] = arm["arm"]
    summary["requested_top_n"] = arm["top_n"]
    curve["requested_top_n"] = arm["top_n"]
    for key, value in _window_common(window, arm["arm"]).items():
        summary[key] = value
        curve[key] = value
    return summary, curve


def _checkpoint_contract(
    preflight: dict[str, Any], window: dict[str, Any], arm: dict[str, Any]
) -> dict[str, Any]:
    eligibility_sha = (
        preflight["eligibility_sha256"].get(arm["arm"], "formal-stage037")
    )
    return {
        "schema_version": 1,
        "runtime_contract_sha256": preflight["runtime_contract_sha256"],
        "database_sha256": preflight["database_sha256"],
        "window_plan_sha256": preflight["window_plan"]["workspace_sha256"],
        "eligibility_sha256": eligibility_sha,
        "window_id": str(window["window_id"]),
        "requested_start": str(pd.Timestamp(window["start"]).date()),
        "requested_end": str(pd.Timestamp(window["end"]).date()),
        "arm": arm["arm"],
    }


def _checkpoint_path(contract: dict[str, Any]) -> Path:
    key = sha256(json.dumps(contract, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    return CHECKPOINT_DIR / f"{contract['window_id']}__{contract['arm']}__{key}"


def _load_checkpoint(
    preflight: dict[str, Any], window: dict[str, Any], arm: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    contract = _checkpoint_contract(preflight, window, arm)
    directory = _checkpoint_path(contract)
    meta_path, summary_path, curve_path = (
        directory / "meta.json",
        directory / "summary.csv",
        directory / "curve.csv",
    )
    if not all(path.exists() for path in (meta_path, summary_path, curve_path)):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        summary, curve = pd.read_csv(summary_path), pd.read_csv(curve_path, low_memory=False)
        if meta.get("contract") != contract:
            return None
        if meta.get("summary_sha256") != _file_sha256(summary_path):
            return None
        if meta.get("curve_sha256") != _file_sha256(curve_path):
            return None
        return (summary, curve) if s29._checkpoint_frames_valid(summary, curve, contract) else None
    except Exception:
        return None


def _write_checkpoint(
    preflight: dict[str, Any],
    window: dict[str, Any],
    arm: dict[str, Any],
    summary: pd.DataFrame,
    curve: pd.DataFrame,
) -> None:
    contract = _checkpoint_contract(preflight, window, arm)
    directory = _checkpoint_path(contract)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage064-checkpoint-", dir=CHECKPOINT_DIR))
    try:
        summary_path, curve_path = temporary / "summary.csv", temporary / "curve.csv"
        summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
        curve.to_csv(curve_path, index=False, encoding="utf-8-sig")
        (temporary / "meta.json").write_text(
            json.dumps(
                {
                    "contract": contract,
                    "summary_sha256": _file_sha256(summary_path),
                    "curve_sha256": _file_sha256(curve_path),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if directory.exists():
            shutil.rmtree(directory)
        os.replace(temporary, directory)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def _validate_outputs(
    summary: pd.DataFrame, curve: pd.DataFrame, windows: list[dict[str, Any]]
) -> None:
    expected = {
        (str(window["window_id"]), str(arm["arm"]))
        for window in windows
        for arm in ARMS
    }
    actual = set(
        zip(summary["window_id"].astype(str), summary["promotion_arm"].astype(str), strict=False)
    )
    curve_pairs = set(
        zip(curve["window_id"].astype(str), curve["promotion_arm"].astype(str), strict=False)
    )
    if len(summary) != len(expected) or actual != expected or curve_pairs != expected:
        raise RuntimeError("stage064_window_arm_identity_mismatch")
    for row in summary.to_dict(orient="records"):
        contract = {
            "window_id": str(row["window_id"]),
            "arm": str(row["promotion_arm"]),
            "requested_start": str(row["requested_start"]),
            "requested_end": str(row["requested_end"]),
        }
        pair_curve = curve[
            curve["window_id"].astype(str).eq(contract["window_id"])
            & curve["promotion_arm"].astype(str).eq(contract["arm"])
        ]
        if not s29._checkpoint_frames_valid(pd.DataFrame([row]), pair_curve, contract):
            raise RuntimeError(
                f"stage064_window_coverage_invalid:{contract['window_id']}:{contract['arm']}"
            )
    if not pd.to_numeric(summary["account_capital"], errors="raise").eq(150_000.0).all():
        raise RuntimeError("stage064_capital_drift")


def _load_full_period_source() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(STAGE063_DIR / s63.SUMMARY_NAME, low_memory=False)
    curve = pd.read_csv(STAGE063_DIR / s63.CURVE_NAME, low_memory=False)
    summary = summary[summary["window_group"].astype(str).eq("full_period")].copy()
    curve = curve[curve["window_group"].astype(str).eq("full_period")].copy()
    if len(summary) != 3 or curve.groupby("promotion_arm").size().to_dict() != {
        "A": 2101,
        "B": 2101,
        "C": 2101,
    }:
        raise RuntimeError("stage064_full_period_source_drift")
    return summary, curve


def _decision(
    preflight: dict[str, Any],
    aggregate: pd.DataFrame,
    checkpoint_reused: int,
    checkpoint_generated: int,
) -> dict[str, Any]:
    cycle_rows: list[dict[str, Any]] = []
    for row in aggregate.to_dict(orient="records"):
        gates = _random_cycle_gates(row)
        cycle_rows.append(
            {
                "comparison": str(row["comparison"]),
                "duration_years": int(row["duration_years"]),
                "cohort": str(row["start_cohort"]),
                "gates": gates,
                "pass": bool(all(gates.values())),
            }
        )
    random_pass = {
        arm: bool(
            all(
                row["pass"]
                for row in cycle_rows
                if row["comparison"] == comparison
            )
        )
        for arm, comparison in (("B", "A_vs_B"), ("C", "A_vs_C"))
    }
    source = _source_decision()
    prior_fixed_pass = source["candidate_all_multicycle_gates_pass"]
    return {
        "line_id": LINE_ID,
        "stage": STAGE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": preflight,
        "random_design": {
            "sampling": "uniform without replacement from actual trading dates",
            "durations_years": list(DURATIONS_YEARS),
            "samples_per_duration": SAMPLES_PER_DURATION,
            "random_seed": preflight["random_seed"],
            "same_windows_for_all_arms": True,
            "fresh_engine_capital_position_state_per_arm_window": True,
            "overlapping_windows_are_stress_scenarios_not_independent_observations": True,
        },
        "gate_contract": {
            "return_win_rate_ge_50pct": 50.0,
            "median_return_delta_nonnegative": 0.0,
            "dd_noninferior_2pp_rate_ge_80pct": 80.0,
            "sharpe_noninferior_005_rate_ge_80pct": 80.0,
            "aggregate_slippage_le_105pct": 1.05,
            "survival_and_dd50_and_broker100_not_worse": True,
            "fixed_stage063_failures_cannot_be_rescued_by_random_windows": True,
        },
        "run_provenance": {
            "random_window_count": EXPECTED_RANDOM_WINDOW_COUNT,
            "logical_arm_window_count": EXPECTED_ENGINE_RUN_COUNT,
            "new_engine_run_count": checkpoint_generated,
            "checkpoint_reused_count": checkpoint_reused,
            "checkpoint_generated_count": checkpoint_generated,
            "random_windows_redrawn_after_results": False,
            "full_period_reused_from_stage063": True,
        },
        "random_cycle_gates": cycle_rows,
        "random_all_gates_pass": random_pass,
        "stage063_fixed_multicycle_gates_pass": prior_fixed_pass,
        "candidate_all_robustness_gates_pass": {
            arm: bool(random_pass[arm] and prior_fixed_pass[arm]) for arm in ("B", "C")
        },
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
        "promote_to_official": False,
        "decision": "random_stress_diagnostic_only_keep_stage037_stop_topn_scan",
        "overfitting_judgment": "高：Top9/Top10是后验边界候选；随机窗口只做预冻结反证，不构成独立样本外发现。",
        "continued_value_judgment": "本次随机压力测试有一次性价值；结果后不重抽窗口、不继续扫描TopN。",
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _plot_full(curve: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in RENDER_ARMS:
        item = curve[curve["promotion_arm"].astype(str).eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(item["date"]),
            pd.to_numeric(item["account_equity"]) / 10_000,
            color=arm["color"],
            linestyle=arm["linestyle"],
            lw=2.0,
            label=arm["plot_label"],
        )
    ax.set(
        title="OFFLINE RESEARCH — Stage064 Full Period Reference",
        ylabel="Equity (10k CNY)",
    )
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _aligned_equity_matrix(curve: pd.DataFrame, years: int, arm: str) -> np.ndarray:
    grid = np.linspace(0.0, 1.0, 101)
    rows: list[np.ndarray] = []
    selected = curve[
        curve["duration_years"].eq(years)
        & curve["promotion_arm"].astype(str).eq(arm)
    ]
    for _, group in selected.groupby("window_id", sort=False):
        equity = pd.to_numeric(group.sort_values("date")["account_equity"], errors="raise")
        if len(equity) < 2:
            raise RuntimeError(f"stage064_curve_too_short:{years}:{arm}")
        source_grid = np.linspace(0.0, 1.0, len(equity))
        rows.append(np.interp(grid, source_grid, equity.to_numpy(float)) / 10_000)
    if len(rows) != SAMPLES_PER_DURATION:
        raise RuntimeError(f"stage064_fan_window_count:{years}:{arm}:{len(rows)}")
    return np.vstack(rows)


def _plot_random_fan(curve: pd.DataFrame, years: int) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    progress = np.arange(101)
    for arm in RENDER_ARMS:
        matrix = _aligned_equity_matrix(curve, years, arm["arm"])
        low, median, high = np.percentile(matrix, [10, 50, 90], axis=0)
        ax.fill_between(progress, low, high, color=arm["color"], alpha=0.10)
        ax.plot(
            progress,
            median,
            color=arm["color"],
            linestyle=arm["linestyle"],
            lw=2.0,
            label=f"{arm['plot_label']} median (P10-P90 band)",
        )
    ax.set(
        title=f"OFFLINE RESEARCH — Stage064 {years}Y Random Starts: 64 Paired Windows",
        xlabel="Window progress (%)",
        ylabel="Equity (10k CNY)",
    )
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _plot_aggregate(aggregate: pd.DataFrame) -> bytes:
    metrics = (
        ("return_win_rate_pct", "Return win/non-inferior rate (%)", "YlGn", 0, 100),
        ("median_return_delta_pct", "Median return delta (pp)", "coolwarm", None, None),
        ("dd_noninferior_2pp_rate_pct", "DD non-inferior <=2pp (%)", "YlOrBr", 0, 100),
        ("sharpe_noninferior_005_rate_pct", "Sharpe non-inferior (%)", "PuBuGn", 0, 100),
        ("slippage_ratio", "Aggregate slippage ratio", "Reds", 1.0, None),
        ("right_worst_return_pct", "Candidate worst return (%)", "coolwarm", None, None),
    )
    row_keys = [
        (comparison, years)
        for comparison in ("A_vs_B", "A_vs_C")
        for years in (0, 1, 2, 3)
    ]
    row_labels = [
        f"{'Top9' if comparison == 'A_vs_B' else 'Top10'} {'All' if years == 0 else f'{years}Y'}"
        for comparison, years in row_keys
    ]
    fig, axes = plt.subplots(2, 3, figsize=(17, 10))
    for ax, (column, title, cmap, fixed_min, fixed_max) in zip(
        axes.ravel(), metrics, strict=True
    ):
        values = np.array(
            [
                [
                    float(
                        aggregate[
                            aggregate["comparison"].eq(comparison)
                            & aggregate["duration_years"].eq(years)
                        ].iloc[0][column]
                    )
                ]
                for comparison, years in row_keys
            ]
        )
        vmin, vmax = fixed_min, fixed_max
        if vmin is None:
            bound = max(float(np.abs(values).max()), 1.0)
            vmin, vmax = -bound, bound
        elif vmax is None:
            vmax = max(float(values.max()), vmin + 0.01)
        image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        for i in range(values.shape[0]):
            ax.text(0, i, f"{values[i, 0]:.2f}", ha="center", va="center")
        ax.set_title(title)
        ax.set_xticks([0], ["Value"])
        ax.set_yticks(range(len(row_labels)), row_labels)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("OFFLINE RESEARCH — Stage064 Random-Start Robustness", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _report(
    full_summary: pd.DataFrame,
    comparison: pd.DataFrame,
    aggregate: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    full = full_summary.set_index("promotion_arm")
    lines = [
        "# Stage064 Stage037、Top9、Top10随机多周期压力测试",
        "",
        f"结论：`{decision['decision']}`。仅离线研究，不改正式物料或稳定生产。",
        "",
        "## 冻结口径",
        "",
        f"- 随机种子：`{decision['random_design']['random_seed']}`。",
        "- 1/2/3年各64个真实交易日起点，均匀无放回抽样；三臂使用相同窗口。",
        "- 共192个随机窗口、576个独立真引擎臂窗；每窗15万元空仓冷启动。",
        "- 窗口可能重叠，因此是压力场景而非192个统计独立样本；结果后不重抽。",
        "- Stage063固定1月/6月门已经失败，本随机压力测试不能覆盖或救回既有失败。",
        "",
        "## 全周期参考",
        "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 交易次数 | 胜率 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A", "B", "C"):
        row = full.loc[arm]
        lines.append(
            f"| {arm} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | "
            f"{row['total_slippage']:,.0f} | {int(row['total_trade_count'])} | "
            f"{row['nonzero_daily_win_rate_pct']:.4f}% |"
        )
    for comparison_name, title in (("A_vs_B", "Top9 对正式版"), ("A_vs_C", "Top10 对正式版")):
        lines += [
            "",
            f"## {title}",
            "",
            "| 范围 | 窗口 | 收益胜/非劣率 | 收益差中位 | DD非劣率 | Sharpe非劣率 | 滑点比 | 候选最差收益 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in aggregate[aggregate["comparison"].eq(comparison_name)].itertuples(index=False):
            label = "全部" if row.duration_years == 0 else f"{row.duration_years}年"
            lines.append(
                f"| {label} | {row.window_count} | {row.return_win_rate_pct:.2f}% | "
                f"{row.median_return_delta_pct:+.4f}pp | {row.dd_noninferior_2pp_rate_pct:.2f}% | "
                f"{row.sharpe_noninferior_005_rate_pct:.2f}% | {row.slippage_ratio:.4f} | "
                f"{row.right_worst_return_pct:.4f}% |"
            )
        lines += ["", "最弱收益差窗口："]
        for row in (
            comparison[comparison["comparison"].eq(comparison_name)]
            .nsmallest(10, "delta_return_pct")
            .itertuples(index=False)
        ):
            lines.append(
                f"- `{row.window_id}` `{row.requested_start}`：候选-正式收益 "
                f"`{row.delta_return_pct:+.4f}pp`，回撤恶化 `{row.dd_worsening_pp:.4f}pp`，"
                f"Sharpe差 `{row.delta_sharpe:+.4f}`。"
            )
    lines += [
        "",
        "## 决策与安全边界",
        "",
        f"- Top9随机门通过：`{decision['random_all_gates_pass']['B']}`；全部稳健性门通过：`{decision['candidate_all_robustness_gates_pass']['B']}`。",
        f"- Top10随机门通过：`{decision['random_all_gates_pass']['C']}`；全部稳健性门通过：`{decision['candidate_all_robustness_gates_pass']['C']}`。",
        "- 不连接CTP，不调用order/send/cancel API，不改正式物料、master或稳定生产。",
        "- 过拟合：高；本次只做固定随机反证，不按结果重抽或改门槛。",
        "- 继续价值：本次完成后停止TopN与随机窗口扫描。",
        "",
    ]
    return "\n".join(lines)


def _runtime_contract_layers(
    decision: dict[str, Any], current_runner_runtime_sha256: str
) -> dict[str, Any]:
    engine_sha = str(decision["identity"]["runtime_contract_sha256"])
    return {
        "engine_checkpoint": {
            "sha256": engine_sha,
            "scope": "576 Stage064 engine checkpoints and their published numerical evidence",
            "generated_before_publication_hardening": engine_sha
            != current_runner_runtime_sha256,
        },
        "current_runner": {
            "sha256": current_runner_runtime_sha256,
            "scope": "future engine/checkpoint runs and deterministic gzip publication",
            "matches_engine_checkpoint_contract": engine_sha
            == current_runner_runtime_sha256,
        },
    }


def _publish(
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
    charts: dict[str, bytes],
    report: str,
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage064.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage064.backup-{uuid4().hex}")
    try:
        for name, frame in frames.items():
            compression = (
                {"method": "gzip", "compresslevel": 9, "mtime": 0}
                if name.endswith(".gz")
                else None
            )
            frame.to_csv(
                temporary / name,
                index=False,
                encoding="utf-8-sig",
                compression=compression,
            )
        chart_sha = {name: sha256(payload).hexdigest() for name, payload in charts.items()}
        existing_render = decision.get("render_provenance")
        if existing_render is None:
            decision["render_provenance"] = {
                "generator": str(Path(__file__).resolve().relative_to(PROJECT_DIR.resolve())),
                "generator_sha256": _file_sha256(Path(__file__)),
                "chart_sha256": chart_sha,
            }
        elif existing_render.get("chart_sha256") != chart_sha:
            raise RuntimeError("stage064_repack_chart_sha_drift")

        curve_path = temporary / CURVE_NAME
        curve_frame = frames[CURVE_NAME]
        curve_provenance = {
            "path": CURVE_NAME,
            "compression": "gzip-mtime-0",
            "compressed_sha256": _file_sha256(curve_path),
            "uncompressed_sha256": _gzip_uncompressed_sha256(curve_path),
            "compressed_size_bytes": curve_path.stat().st_size,
            "row_count": int(len(curve_frame)),
            "arm_window_count": int(
                curve_frame.groupby(["window_id", "promotion_arm"]).ngroups
            ),
        }
        decision["artifact_provenance"] = {
            "random_equity_curves": curve_provenance,
        }
        publication_payload = {
            "publisher_sha256": _file_sha256(Path(__file__)),
            "runtime_contracts": decision["runtime_contracts"],
            "curve": curve_provenance,
            "chart_sha256": chart_sha,
        }
        decision["publication_provenance"] = {
            **publication_payload,
            "sha256": _json_sha256(publication_payload),
            "atomic_directory_replace": True,
        }
        (temporary / DECISION_NAME).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temporary / REPORT_NAME).write_text(report, encoding="utf-8")
        for name, payload in charts.items():
            (temporary / name).write_bytes(payload)
        if OUTPUT_DIR.exists():
            os.replace(OUTPUT_DIR, backup)
        os.replace(temporary, OUTPUT_DIR)
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def _freeze_only() -> None:
    _assert_reuse_sources_frozen()
    source = _source_decision()
    database_sha = _file_sha256(s63.s56.DATABASE_PATH)
    expected = str(source["identity"]["database_sha256"])
    if database_sha != expected:
        raise RuntimeError(
            f"stage064_database_drift:actual={database_sha}:expected={expected}"
        )
    metadata = _freeze_window_plan(_trading_dates(), database_sha, WINDOW_PLAN_PATH)
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)


def _repack_existing() -> None:
    if not OUTPUT_DIR.exists():
        raise RuntimeError("stage064_repack_output_missing")
    preflight, _eligibility_paths, plan = _preflight()
    paths = {
        SUMMARY_NAME: OUTPUT_DIR / SUMMARY_NAME,
        COMPARISON_NAME: OUTPUT_DIR / COMPARISON_NAME,
        AGGREGATE_NAME: OUTPUT_DIR / AGGREGATE_NAME,
        CURVE_NAME: OUTPUT_DIR / CURVE_NAME,
    }
    if not all(path.exists() for path in paths.values()):
        raise RuntimeError(f"stage064_repack_artifact_missing:{paths}")
    frames = {
        SUMMARY_NAME: pd.read_csv(paths[SUMMARY_NAME], low_memory=False),
        COMPARISON_NAME: pd.read_csv(paths[COMPARISON_NAME]),
        AGGREGATE_NAME: pd.read_csv(paths[AGGREGATE_NAME]),
        CURVE_NAME: pd.read_csv(paths[CURVE_NAME], low_memory=False),
    }
    windows = [_window_dict(row) for row in plan.itertuples(index=False)]
    _validate_outputs(frames[SUMMARY_NAME], frames[CURVE_NAME], windows)
    rebuilt_aggregate = _random_aggregate(frames[COMPARISON_NAME])
    pd.testing.assert_frame_equal(
        rebuilt_aggregate.reset_index(drop=True),
        frames[AGGREGATE_NAME].reset_index(drop=True),
        check_dtype=False,
        rtol=1e-12,
        atol=1e-9,
    )
    decision = json.loads((OUTPUT_DIR / DECISION_NAME).read_text(encoding="utf-8"))
    decision["runtime_contracts"] = _runtime_contract_layers(
        decision, preflight["runtime_contract_sha256"]
    )
    charts = {name: (OUTPUT_DIR / name).read_bytes() for name in CHART_FILES.values()}
    report = (OUTPUT_DIR / REPORT_NAME).read_text(encoding="utf-8")
    _publish(frames, decision, charts, report)
    print(
        json.dumps(
            {
                "repacked": True,
                "engine_runtime": decision["runtime_contracts"]["engine_checkpoint"][
                    "sha256"
                ],
                "current_runner_runtime": decision["runtime_contracts"]["current_runner"][
                    "sha256"
                ],
                "curve": decision["artifact_provenance"]["random_equity_curves"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--repack-existing", action="store_true")
    args = parser.parse_args()
    if args.freeze_only:
        _freeze_only()
        return
    if args.repack_existing:
        _repack_existing()
        return

    preflight, eligibility_paths, plan = _preflight()
    metadata = s63.s56.s28.s513._metadata()
    windows = [_window_dict(row) for row in plan.itertuples(index=False)]
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    reused = generated = 0
    total = len(windows) * len(ARMS)
    index = 0
    for window in windows:
        for arm in ARMS:
            index += 1
            cached = _load_checkpoint(preflight, window, arm)
            if cached is None:
                print(
                    f"[stage064] {index}/{total} run {window['window_id']} arm={arm['arm']}",
                    flush=True,
                )
                summary, curve = _run_window(metadata, window, arm, eligibility_paths)
                _write_checkpoint(preflight, window, arm, summary, curve)
                generated += 1
            else:
                summary, curve = cached
                reused += 1
                print(
                    f"[stage064] {index}/{total} reuse {window['window_id']} arm={arm['arm']}",
                    flush=True,
                )
            summaries.append(summary)
            curves.append(curve)
    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    window_order = {str(item["window_id"]): i for i, item in enumerate(windows)}
    arm_order = {item["arm"]: i for i, item in enumerate(ARMS)}
    summary = (
        summary.assign(
            _window_order=summary["window_id"].map(window_order),
            _arm_order=summary["promotion_arm"].map(arm_order),
        )
        .sort_values(["_window_order", "_arm_order"])
        .drop(columns=["_window_order", "_arm_order"])
    )
    curve = (
        curve.assign(
            _window_order=curve["window_id"].map(window_order),
            _arm_order=curve["promotion_arm"].map(arm_order),
        )
        .sort_values(["_window_order", "_arm_order", "date"])
        .drop(columns=["_window_order", "_arm_order"])
    )
    _validate_outputs(summary, curve, windows)
    s29.COMPARISONS = COMPARISONS
    comparison = s29._comparison(summary)
    aggregate = _random_aggregate(comparison)
    full_summary, full_curve = _load_full_period_source()
    decision = _decision(preflight, aggregate, reused, generated)
    decision["runtime_contracts"] = _runtime_contract_layers(
        decision, preflight["runtime_contract_sha256"]
    )
    charts = {
        CHART_FILES["full_period"]: _plot_full(full_curve),
        CHART_FILES["1y"]: _plot_random_fan(curve, 1),
        CHART_FILES["2y"]: _plot_random_fan(curve, 2),
        CHART_FILES["3y"]: _plot_random_fan(curve, 3),
        CHART_FILES["aggregate"]: _plot_aggregate(aggregate),
    }
    _publish(
        {
            SUMMARY_NAME: summary,
            COMPARISON_NAME: comparison,
            AGGREGATE_NAME: aggregate,
            CURVE_NAME: curve,
        },
        decision,
        charts,
        _report(full_summary, comparison, aggregate, decision),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

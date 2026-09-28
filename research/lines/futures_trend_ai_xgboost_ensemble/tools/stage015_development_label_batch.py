"""Produce the frozen development account-marginal label grid."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import site
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PORTFOLIO_DIR = PRODUCTION_ROOT / "examples/portfolio_backtesting"
RUNTIME_ROOT = Path("/private/tmp/vnpy-stage004-xgboost-runtime")
RUNTIME_DATABASE = RUNTIME_ROOT / ".vntrader/database.db"
TMP_ROOT = Path("/private/tmp/vnpy-stage015-development-label-batch")
BASE_OUT = LINE / "artifacts/stage015_development_label_batch"

STAGE004_TOOL = LINE / "tools/stage004_fullperiod_true_engine.py"
STAGE005_TOOL = LINE / "tools/stage005_current_snapshot_true_engine.py"
STAGE007_TOOL = LINE / "tools/stage007_cold_true_engine_ac.py"
STAGE009_TOOL = LINE / "tools/stage009_formal_full_ranking_recovery.py"
STAGE010_TOOL = LINE / "tools/stage010_account_marginal_slot_probe.py"
STAGE012_TOOL = LINE / "tools/stage012_active_account_slot_probe.py"
STAGE013_TOOL = LINE / "tools/stage013_label_grid_coverage.py"
STAGE014_TOOL = LINE / "tools/stage014_prelabel_feature_contract.py"

FULL_RANKING = LINE / "artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv"
STAGE009_AUDIT = LINE / "artifacts/stage009_formal_full_ranking_recovery/audit.json"
STAGE012_ATTEMPT = (
    LINE
    / "artifacts/stage012_active_account_slot_probe"
    / "attempt_20260901T181032+0800_58383"
)
STAGE012_DECISION = STAGE012_ATTEMPT / "decision.json"
STAGE012_REVIEW = LINE / "reviews/20260901_stage012_independent_review.md"
STAGE013_PLAN = LINE / "artifacts/stage013_label_grid_coverage/full_grid_label_plan.csv"
STAGE013_SUMMARY = LINE / "artifacts/stage013_label_grid_coverage/summary.json"
FEATURE_PANEL = LINE / "artifacts/stage014_prelabel_feature_contract/prelabel_feature_panel.csv"
MONTH_SPLIT = LINE / "artifacts/stage014_prelabel_feature_contract/month_split.csv"
FEATURE_CONTRACT = LINE / "artifacts/stage014_prelabel_feature_contract/feature_contract.json"
PREREGISTRATION = LINE / "stages/20260901_1830_stage015_development_label_batch.md"
OFFICIAL_OVERRIDES_FILENAME = "official_overrides.json"
OFFICIAL_PRODUCT_UNIVERSE_FILENAME = "official_product_universe.csv"
STAGE819_PROFILE_OVERRIDES_FILENAME = "stage819_profile_overrides.json"
STAGE819_PROFILE_ELIGIBILITY_FILENAME = "stage819_profile_eligibility.csv"
REQUIRED_SHARED_BUILDER_BINDINGS = (
    "origin:build_static18_plus_fu_universe",
    "origin:build_ai_satellite_post_signal_eligibility",
    "stage78:build_static18_plus_fu_universe",
    "stage78:build_ai_satellite_post_signal_eligibility",
    "stage777:build_static18_plus_fu_universe",
    "stage777:build_ai_satellite_post_signal_eligibility",
)

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
PROFILE = "stage015_development_account_marginal_label"
MAX_WORKERS = 2
MAX_JOB_SECONDS = 600.0
MONEY_QUANTUM = Decimal("0.000001")
SENTINEL_MONTH_INDEXES = (0, 12, 24, 36)
SMOKE_JOB_IDS = (
    "20220429_R10",
    "20220429_R10_A2",
    "20220531_R10",
    "20220531_R12",
)
EXPECTED_DEVELOPMENT_DATES = (
    "2022-04-29",
    "2022-05-31",
    "2022-06-30",
    "2022-07-29",
    "2022-08-31",
    "2022-09-30",
    "2022-10-31",
    "2022-11-30",
    "2022-12-30",
    "2023-01-31",
    "2023-02-28",
    "2023-03-31",
    "2023-04-28",
    "2023-05-31",
    "2023-06-30",
    "2023-07-31",
    "2023-08-31",
    "2023-09-28",
    "2023-10-31",
    "2023-11-30",
    "2023-12-29",
    "2024-01-31",
    "2024-02-29",
    "2024-03-29",
    "2024-04-30",
    "2024-05-31",
    "2024-06-28",
    "2024-07-31",
    "2024-08-30",
    "2024-09-30",
    "2024-10-31",
    "2024-11-29",
    "2024-12-31",
    "2025-01-27",
    "2025-02-28",
    "2025-03-31",
    "2025-04-30",
    "2025-05-30",
    "2025-06-30",
)
EXPECTED_HOLDOUT_DATES = (
    "2025-07-31",
    "2025-08-29",
    "2025-09-30",
    "2025-10-31",
    "2025-11-28",
    "2025-12-31",
    "2026-01-30",
    "2026-02-27",
    "2026-03-31",
    "2026-04-30",
    "2026-05-29",
    "2026-06-30",
)
PAYLOAD_NAMES = (
    "curve",
    "combined",
    "trades",
    "entry_candidates",
    "entry_risk",
    "trade_events",
)
PREDECISION_NAMES = (
    "curve",
    "trades",
    "entry_candidates",
    "entry_risk",
    "trade_events",
)
EXPECTED_JOB_OUTPUT_FILES = frozenset(
    {"summary.csv", "label.json"} | {f"{name}.csv" for name in PAYLOAD_NAMES}
)
IDENTITY_COLUMNS = {"profile", "variant", "label", "experiment_arm", "arm"}
RUNTIME_NORMALIZED_ENV_KEYS = {
    "TMPDIR",
    "MPLCONFIGDIR",
    "STAGE015_CAMPAIGN_DIR",
    "STAGE015_JOB_ID",
}
WORKER_EXECUTION_EXACT_KEYS = {
    "runtime_database",
    "runtime_setting",
    "full_minute_bars",
    "main_contract_mapping",
    "contract_metadata",
    "product_universe",
    "formal_current",
    "formal_eligibility",
    "stage004_helper",
    "stage007_identity_reference",
    "stage010_label_helper",
    "stage015_runner",
    "stage015_preregistration",
    "stage015_jobs",
    "stage015_official_overrides",
    "stage015_stage819_profile_overrides",
    "stage015_stage819_profile_eligibility",
    "python_executable",
    "python_pyvenv_cfg",
    "python_sitecustomize",
}
WORKER_EXECUTION_PREFIXES = (
    "python_site_pth/",
    "python_startup_module/",
    "production_portfolio/",
    "formal_release/",
    "workspace_vnpy_core/",
    "vnpy_portfoliostrategy/",
    "distribution_metadata/",
)

_STAGE004 = None
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
        _STAGE004 = _load_module(STAGE004_TOOL, "stage004_for_stage015")
    return _STAGE004


def _load_stage007():
    global _STAGE007
    if _STAGE007 is None:
        _STAGE007 = _load_module(STAGE007_TOOL, "stage007_for_stage015")
    return _STAGE007


def _load_stage010():
    global _STAGE010
    if _STAGE010 is None:
        _STAGE010 = _load_module(STAGE010_TOOL, "stage010_for_stage015")
    return _STAGE010


def _stable_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def _sha256(path: Path) -> str:
    return _load_stage007()._file_identity(path)["sha256"]


def _file_contract_sha256(files: dict[str, dict[str, Any]]) -> str:
    payload = {
        name: {"size": value["size"], "sha256": value["sha256"]}
        for name, value in sorted(files.items())
    }
    return hashlib.sha256(_stable_json(payload)).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    _write_json(temporary, payload)
    temporary.replace(path)


def _canonical_date_strings(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="raise").dt.normalize().dt.date.astype(str)


def canonical_eligibility(formal: pd.DataFrame) -> pd.DataFrame:
    required = {
        "strategy",
        "score_type",
        "eval_date",
        "product_vt_symbol",
        "score",
        "score_rank",
        "top_n",
    }
    missing = required - set(formal.columns)
    if missing:
        raise RuntimeError(f"formal_eligibility_columns_missing:{sorted(missing)}")
    frame = formal.copy()
    frame["eval_date"] = _canonical_date_strings(frame["eval_date"])
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["score_rank"] = pd.to_numeric(frame["score_rank"], errors="raise").astype(int)
    frame["top_n"] = pd.to_numeric(frame["top_n"], errors="raise").astype(int)
    frame.sort_values(["eval_date", "score_rank"], inplace=True, kind="mergesort")
    frame.reset_index(drop=True, inplace=True)
    return frame


def build_candidate_eligibility(
    formal: pd.DataFrame,
    ranking: pd.DataFrame,
    *,
    eval_date: str,
    candidate_rank: int,
) -> pd.DataFrame:
    if candidate_rank not in range(10, 19):
        raise ValueError(f"candidate_rank_out_of_range:{candidate_rank}")
    result = canonical_eligibility(formal)
    target_date = pd.Timestamp(eval_date).date().isoformat()
    target_mask = result["eval_date"].eq(target_date) & result["score_rank"].eq(10)
    if int(target_mask.sum()) != 1:
        raise RuntimeError(f"formal_target_rank10_shape:{target_date}:{int(target_mask.sum())}")
    if candidate_rank == 10:
        return result

    source = ranking.copy()
    required = {"eval_date", "product_vt_symbol", "score", "score_rank", "score_type"}
    missing = required - set(source.columns)
    if missing:
        raise RuntimeError(f"ranking_columns_missing:{sorted(missing)}")
    source["eval_date"] = _canonical_date_strings(source["eval_date"])
    source["score_rank"] = pd.to_numeric(source["score_rank"], errors="raise").astype(int)
    candidate = source[
        source["eval_date"].eq(target_date) & source["score_rank"].eq(candidate_rank)
    ]
    if len(candidate) != 1:
        raise RuntimeError(
            f"candidate_source_shape:{target_date}:{candidate_rank}:{len(candidate)}"
        )
    row = candidate.iloc[0]
    result.loc[target_mask, "product_vt_symbol"] = str(row["product_vt_symbol"])
    result.loc[target_mask, "score"] = float(row["score"])
    result.loc[target_mask, "score_type"] = "stage015_account_marginal_slot_label"

    baseline = canonical_eligibility(formal)
    unchanged_mask = ~target_mask
    if not baseline.loc[unchanged_mask].reset_index(drop=True).equals(
        result.loc[unchanged_mask].reset_index(drop=True)
    ):
        raise RuntimeError(f"non_target_eligibility_drift:{target_date}:{candidate_rank}")
    changed_rows = baseline.ne(result).any(axis=1)
    if int(changed_rows.sum()) != 1 or not bool(changed_rows[target_mask].all()):
        raise RuntimeError(f"eligibility_change_scope_invalid:{target_date}:{candidate_rank}")
    return result


def build_development_jobs(panel: pd.DataFrame) -> pd.DataFrame:
    required = {
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "score_rank",
        "split",
        "label_values_read_allowed",
    }
    missing = required - set(panel.columns)
    if missing:
        raise RuntimeError(f"feature_panel_columns_missing:{sorted(missing)}")
    frame = panel.copy()
    frame["eval_date"] = _canonical_date_strings(frame["eval_date"])
    frame["next_eval_date"] = _canonical_date_strings(frame["next_eval_date"])
    frame["candidate_rank"] = pd.to_numeric(frame["score_rank"], errors="raise").astype(int)
    split = pd.read_csv(MONTH_SPLIT)
    split["eval_date"] = _canonical_date_strings(split["eval_date"])
    if split["eval_date"].duplicated().any():
        raise RuntimeError("month_split_duplicate_eval_date")
    observed_development = tuple(
        split.loc[split["split"].eq("development"), "eval_date"].tolist()
    )
    observed_holdout = tuple(
        split.loc[split["split"].eq("sealed_holdout"), "eval_date"].tolist()
    )
    if observed_development != EXPECTED_DEVELOPMENT_DATES:
        raise RuntimeError(f"development_month_contract_drift:{observed_development}")
    if observed_holdout != EXPECTED_HOLDOUT_DATES:
        raise RuntimeError(f"holdout_month_contract_drift:{observed_holdout}")
    split_by_date = split.set_index("eval_date")
    panel_dates = tuple(sorted(frame["eval_date"].unique()))
    expected_panel_dates = tuple(
        sorted(EXPECTED_DEVELOPMENT_DATES + EXPECTED_HOLDOUT_DATES)
    )
    if panel_dates != expected_panel_dates:
        raise RuntimeError("feature_panel_months_do_not_match_frozen_split")
    for eval_date, month in frame.groupby("eval_date", sort=True):
        expected_split = str(split_by_date.at[eval_date, "split"])
        expected_allowed = bool(split_by_date.at[eval_date, "label_values_read_allowed"])
        if set(month["split"].astype(str)) != {expected_split}:
            raise RuntimeError(f"feature_panel_split_drift:{eval_date}")
        allowed_values = month["label_values_read_allowed"].astype(str).str.lower().isin(
            {"true", "1"}
        )
        if set(allowed_values.tolist()) != {expected_allowed}:
            raise RuntimeError(f"feature_panel_label_permission_drift:{eval_date}")
    ordered_eval_dates = EXPECTED_DEVELOPMENT_DATES + EXPECTED_HOLDOUT_DATES
    expected_next = dict(zip(ordered_eval_dates[:-1], ordered_eval_dates[1:]))
    for eval_date in EXPECTED_DEVELOPMENT_DATES:
        next_values = set(
            frame.loc[frame["eval_date"].eq(eval_date), "next_eval_date"].astype(str)
        )
        if next_values != {expected_next[eval_date]}:
            raise RuntimeError(
                f"development_next_eval_date_drift:{eval_date}:{sorted(next_values)}"
            )
    frame = frame[
        frame["split"].eq("development")
        & frame["candidate_rank"].between(10, 18)
    ].copy()
    allowed = frame["label_values_read_allowed"].astype(str).str.lower().isin(
        {"true", "1"}
    )
    if not allowed.all():
        raise RuntimeError("development_label_read_permission_missing")
    frame.sort_values(["eval_date", "candidate_rank"], inplace=True, kind="mergesort")
    frame.reset_index(drop=True, inplace=True)
    if len(frame) != 351 or frame["eval_date"].nunique() != 39:
        raise RuntimeError(
            f"development_grid_shape:{len(frame)}:{frame['eval_date'].nunique()}"
        )
    counts = frame.groupby("eval_date")["candidate_rank"].apply(list)
    if not counts.map(lambda values: values == list(range(10, 19))).all():
        raise RuntimeError("development_rank_grid_incomplete")

    main = frame[
        [
            "eval_date",
            "next_eval_date",
            "product_vt_symbol",
            "candidate_rank",
            "split",
        ]
    ].copy()
    main["job_type"] = "main"
    main["job_id"] = main.apply(
        lambda row: f"{row['eval_date'].replace('-', '')}_R{int(row['candidate_rank'])}",
        axis=1,
    )
    main["eligibility_key"] = main["job_id"]
    months = list(EXPECTED_DEVELOPMENT_DATES)
    sentinels: list[dict[str, Any]] = []
    for index in SENTINEL_MONTH_INDEXES:
        eval_date = months[index]
        baseline = main[
            main["eval_date"].eq(eval_date) & main["candidate_rank"].eq(10)
        ].iloc[0]
        sentinels.append(
            {
                **baseline.to_dict(),
                "job_type": "A2_sentinel",
                "job_id": f"{eval_date.replace('-', '')}_R10_A2",
                "eligibility_key": baseline["job_id"],
            }
        )
    jobs = pd.concat([main, pd.DataFrame(sentinels)], ignore_index=True)
    job_type_order = pd.Categorical(
        jobs["job_type"], categories=["main", "A2_sentinel"], ordered=True
    )
    jobs = jobs.assign(_job_type_order=job_type_order)
    jobs.sort_values(
        ["eval_date", "candidate_rank", "_job_type_order"],
        inplace=True,
        kind="mergesort",
    )
    jobs.drop(columns="_job_type_order", inplace=True)
    jobs.reset_index(drop=True, inplace=True)
    if len(jobs) != 355 or jobs["job_id"].nunique() != 355:
        raise RuntimeError(f"development_job_count:{len(jobs)}")
    if jobs["split"].eq("sealed_holdout").any():
        raise RuntimeError("sealed_holdout_job_present")
    return jobs


def validate_job_ranking_alignment(
    jobs: pd.DataFrame, ranking: pd.DataFrame
) -> dict[str, Any]:
    source = ranking.copy()
    source["eval_date"] = _canonical_date_strings(source["eval_date"])
    source["score_rank"] = pd.to_numeric(
        source["score_rank"], errors="raise"
    ).astype(int)
    source = source[
        source["eval_date"].isin(EXPECTED_DEVELOPMENT_DATES)
        & source["score_rank"].between(10, 18)
    ][["eval_date", "score_rank", "product_vt_symbol"]].copy()
    source.rename(
        columns={
            "score_rank": "candidate_rank",
            "product_vt_symbol": "ranking_product_vt_symbol",
        },
        inplace=True,
    )
    if len(source) != 351 or source.duplicated(
        ["eval_date", "candidate_rank"]
    ).any():
        raise RuntimeError(f"development_ranking_grid_shape:{len(source)}")
    main = jobs[jobs["job_type"].eq("main")].copy()
    merged = main.merge(
        source,
        on=["eval_date", "candidate_rank"],
        how="left",
        validate="one_to_one",
    )
    mismatched = merged[
        merged["product_vt_symbol"].astype(str)
        != merged["ranking_product_vt_symbol"].astype(str)
    ]
    if len(merged) != 351 or not mismatched.empty:
        raise RuntimeError(
            f"feature_panel_ranking_product_mismatch:{len(mismatched)}"
        )
    return {
        "passed": True,
        "checked_rows": 351,
        "mismatch_count": 0,
    }


def worker_environment(
    base: dict[str, str],
    tmp_root: Path,
    job_id: str,
    *,
    run_id: str | None = None,
) -> dict[str, str]:
    root = tmp_root / job_id / (run_id or f"run_{job_id}")
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
            "MPLCONFIGDIR": str((root / "mplconfig").resolve()),
            "TMPDIR": str((root / "tmp").resolve()),
            "STAGE015_CAMPAIGN_DIR": str(tmp_root.resolve()),
            "STAGE015_JOB_ID": job_id,
        }
    )
    return environment


@contextmanager
def _exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"lock_already_held:{path}") from exc
        stream.seek(0)
        stream.truncate()
        stream.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "acquired_at": datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    ),
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        stream.flush()
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def normalized_runtime_sha256(runtime: dict[str, Any]) -> str:
    normalized = json.loads(json.dumps(runtime, ensure_ascii=True))
    environment = normalized.get("environment", {})
    if not isinstance(environment, dict):
        raise RuntimeError("runtime_environment_not_mapping")
    for key in RUNTIME_NORMALIZED_ENV_KEYS:
        if key in environment:
            environment[key] = f"<{key}>"
    return hashlib.sha256(_stable_json(normalized)).hexdigest()


def reconcile_label_pair(
    baseline_label: dict[str, Any], candidate_label: dict[str, Any]
) -> dict[str, float]:
    base_equity = float(baseline_label["base_equity"])
    candidate_base_equity = float(candidate_label["base_equity"])
    end_equity_delta = float(candidate_label["end_equity"]) - float(
        baseline_label["end_equity"]
    )
    net_pnl_delta = float(candidate_label["future_net_pnl"]) - float(
        baseline_label["future_net_pnl"]
    )
    return_delta = float(candidate_label["future_return"]) - float(
        baseline_label["future_return"]
    )
    drawdown_improvement = float("nan")
    if "future_max_drawdown" in baseline_label and "future_max_drawdown" in candidate_label:
        drawdown_improvement = float(candidate_label["future_max_drawdown"]) - float(
            baseline_label["future_max_drawdown"]
        )
    equity_error = float(
        _quantized_money(candidate_label["end_equity"])
        - _quantized_money(baseline_label["end_equity"])
        - _quantized_money(candidate_label["future_net_pnl"])
        + _quantized_money(baseline_label["future_net_pnl"])
    )
    return_error = return_delta - end_equity_delta / base_equity
    if abs(equity_error) < 1e-15:
        equity_error = 0.0
    if abs(return_error) < 1e-15:
        return_error = 0.0
    return {
        "base_equity_delta": candidate_base_equity - base_equity,
        "end_equity_delta": end_equity_delta,
        "net_pnl_delta": net_pnl_delta,
        "return_delta": return_delta,
        "drawdown_improvement": drawdown_improvement,
        "slippage_delta": float(candidate_label["future_slippage"])
        - float(baseline_label["future_slippage"]),
        "trade_count_delta": float(candidate_label["future_trade_count"])
        - float(baseline_label["future_trade_count"]),
        "end_equity_vs_net_pnl_delta_error": equity_error,
        "return_vs_equity_delta_error": return_error,
    }


def _quantized_money(value: Any) -> Decimal:
    return Decimal(str(float(value))).quantize(MONEY_QUANTUM)


def monetary_reconciliation_error(
    *,
    end_equity: Any,
    base_equity: Any,
    net_pnl: Any,
) -> float:
    return float(
        _quantized_money(end_equity)
        - _quantized_money(base_equity)
        - _quantized_money(net_pnl)
    )


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
                "STAGE015_CAMPAIGN_DIR",
                "STAGE015_JOB_ID",
            )
        },
        "repository": _repository_state(),
        "packages": packages,
        "startup_hooks": {
            name: str(path.resolve())
            for name, path in sorted(startup_hook_identity_files().items())
        },
    }


def _assert_runtime_stable(before: dict[str, Any], after: dict[str, Any]) -> None:
    if before != after:
        changed = [key for key in before if before.get(key) != after.get(key)]
        raise RuntimeError(f"worker_runtime_changed:{changed}")


def _collect_campaign_files(campaign_dir: Path, *, s901: Any) -> dict[str, Path]:
    stage007 = _load_stage007()
    import contract_metadata
    import vnpy_portfoliostrategy

    overrides = _load_frozen_official_overrides(campaign_dir)
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
        "stage009_runner": STAGE009_TOOL,
        "stage009_full_ranking": FULL_RANKING,
        "stage009_audit": STAGE009_AUDIT,
        "stage010_label_helper": STAGE010_TOOL,
        "stage012_runner": STAGE012_TOOL,
        "stage012_decision": STAGE012_DECISION,
        "stage012_review": STAGE012_REVIEW,
        "stage013_runner": STAGE013_TOOL,
        "stage013_plan": STAGE013_PLAN,
        "stage013_summary": STAGE013_SUMMARY,
        "stage014_runner": STAGE014_TOOL,
        "stage014_feature_panel": FEATURE_PANEL,
        "stage014_month_split": MONTH_SPLIT,
        "stage014_feature_contract": FEATURE_CONTRACT,
        "stage015_runner": Path(__file__).resolve(),
        "stage015_preregistration": PREREGISTRATION,
        "stage015_jobs": campaign_dir / "jobs.csv",
        "stage015_official_overrides": campaign_dir / OFFICIAL_OVERRIDES_FILENAME,
        "stage015_stage819_profile_overrides": (
            campaign_dir / STAGE819_PROFILE_OVERRIDES_FILENAME
        ),
        "stage015_stage819_profile_eligibility": (
            campaign_dir / STAGE819_PROFILE_ELIGIBILITY_FILENAME
        ),
        "stage015_eligibility_audit": campaign_dir / "eligibility_audit.csv",
        "stage015_ranking_alignment": campaign_dir / "ranking_alignment.json",
        "python_executable": Path(sys.executable).resolve(),
    }
    files.update(startup_hook_identity_files())
    pyvenv = Path(sys.prefix) / "pyvenv.cfg"
    if pyvenv.is_file():
        files["python_pyvenv_cfg"] = pyvenv
    for path in sorted((campaign_dir / "eligibility").glob("*.csv")):
        files[f"stage015_eligibility/{path.name}"] = path
    if len(list((campaign_dir / "eligibility").glob("*.csv"))) != 351:
        raise RuntimeError("campaign_eligibility_file_count_not_351")
    stage007._add_tree_files(
        files, prefix="production_portfolio", root=PORTFOLIO_DIR, suffixes={".py"}
    )
    stage007._add_tree_files(
        files, prefix="formal_release", root=FORMAL_RELEASE, suffixes=None
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
            raise RuntimeError(f"campaign_identity_input_missing:{name}:{path}")
    return files


def _campaign_manifest(
    campaign_dir: Path,
    *,
    s901: Any,
    frozen_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime = _runtime_contract() if frozen_runtime is None else frozen_runtime
    manifest = _load_stage007().build_identity_manifest(
        _collect_campaign_files(campaign_dir, s901=s901),
        runtime=runtime,
    )
    manifest["file_contract_sha256"] = _file_contract_sha256(manifest["files"])
    return manifest


def _is_worker_execution_input(name: str, eligibility_key: str) -> bool:
    if name in WORKER_EXECUTION_EXACT_KEYS:
        return True
    if name == f"stage015_eligibility/{eligibility_key}.csv":
        return True
    return any(name.startswith(prefix) for prefix in WORKER_EXECUTION_PREFIXES)


def _worker_execution_manifest(
    campaign_dir: Path,
    job: pd.Series,
    campaign_identity: dict[str, Any],
) -> dict[str, Any]:
    expected_files = campaign_identity["files"]
    eligibility_key = str(job["eligibility_key"])
    selected = {
        name: value
        for name, value in expected_files.items()
        if _is_worker_execution_input(name, eligibility_key)
    }
    required = WORKER_EXECUTION_EXACT_KEYS - {"python_pyvenv_cfg", "python_sitecustomize"}
    missing = required - set(selected)
    if missing:
        raise RuntimeError(f"worker_execution_identity_keys_missing:{sorted(missing)}")
    eligibility_name = f"stage015_eligibility/{eligibility_key}.csv"
    if eligibility_name not in selected:
        raise RuntimeError(f"worker_eligibility_identity_missing:{eligibility_name}")

    by_path: dict[Path, dict[str, Any]] = {}
    selected_paths: set[Path] = set()
    observed: dict[str, dict[str, Any]] = {}
    for name, expected in sorted(selected.items()):
        path = Path(expected["path"]).resolve()
        selected_paths.add(path)
        if path not in by_path:
            by_path[path] = _load_stage007()._file_identity(path)
        actual = by_path[path]
        if actual["size"] != expected["size"] or actual["sha256"] != expected["sha256"]:
            raise RuntimeError(f"worker_execution_input_drift:{name}:{path}")
        observed[name] = actual
    identity_path = (campaign_dir / "campaign_identity.json").resolve()
    if identity_path not in by_path:
        by_path[identity_path] = _load_stage007()._file_identity(identity_path)
    campaign_identity_file = by_path[identity_path]
    observed["campaign_identity_file"] = campaign_identity_file
    return {
        "files": observed,
        "file_contract_sha256": _file_contract_sha256(observed),
        "unique_physical_file_count": len(selected_paths | {identity_path}),
    }


def _local_datetimes(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, errors="raise", utc=True)
    return values.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)


def _date_column(frame: pd.DataFrame) -> str:
    for name in ("date", "datetime", "trading_day"):
        if name in frame.columns:
            return name
    raise RuntimeError(f"payload_date_column_missing:{list(frame.columns)}")


def _period_rows(
    frame: pd.DataFrame,
    *,
    after: pd.Timestamp | None = None,
    through: pd.Timestamp,
) -> pd.DataFrame:
    column = _date_column(frame)
    values = _local_datetimes(frame[column]).dt.normalize()
    mask = values.le(through.normalize())
    if after is not None:
        mask &= values.gt(after.normalize())
    return frame.loc[mask].reset_index(drop=True)


def _canonical_payload(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.drop(
        columns=[name for name in IDENTITY_COLUMNS if name in frame.columns]
    ).reset_index(drop=True)


def _frame_sha256(frame: pd.DataFrame) -> str:
    payload = _canonical_payload(frame).to_csv(
        index=False, lineterminator="\n", date_format="%Y-%m-%dT%H:%M:%S.%f"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _predecision_signatures(
    payloads: dict[str, pd.DataFrame], eval_date: pd.Timestamp
) -> dict[str, str]:
    return {
        name: _frame_sha256(
            _period_rows(payloads[name], through=eval_date)
        )
        for name in PREDECISION_NAMES
    }


def _target_payloads(
    payloads: dict[str, pd.DataFrame], eval_date: pd.Timestamp, end: pd.Timestamp
) -> dict[str, pd.DataFrame]:
    return {
        name: _canonical_payload(
            _period_rows(payloads[name], after=eval_date, through=end)
        )
        for name in PAYLOAD_NAMES
    }


def _entry_candidate_boundary_gate(
    payloads: dict[str, pd.DataFrame],
    target: dict[str, pd.DataFrame],
    eval_date: pd.Timestamp,
) -> dict[str, Any]:
    frame = payloads["entry_candidates"]
    signal_column = "ai_product_pool_signal_date"
    if signal_column not in frame.columns:
        return {
            "passed": False,
            "reason": "entry_candidate_signal_date_column_missing",
        }
    predecision = _period_rows(frame, through=eval_date)
    predecision_signals = pd.to_datetime(
        predecision[signal_column], errors="coerce"
    ).dropna()
    target_signals = pd.to_datetime(
        target["entry_candidates"][signal_column], errors="coerce"
    ).dropna()
    target_row_count = int(len(target["entry_candidates"]))
    target_nonnull_signal_count = int(len(target_signals))
    predecision_uses_only_prior_snapshot = bool(
        predecision_signals.empty
        or predecision_signals.dt.normalize().lt(eval_date.normalize()).all()
    )
    target_uses_current_snapshot = bool(
        target_nonnull_signal_count == target_row_count
        and (
            target_signals.empty
            or target_signals.dt.normalize().eq(eval_date.normalize()).all()
        )
    )
    return {
        "passed": predecision_uses_only_prior_snapshot and target_uses_current_snapshot,
        "predecision_uses_only_prior_snapshot": predecision_uses_only_prior_snapshot,
        "target_uses_current_snapshot": target_uses_current_snapshot,
        "target_row_count": target_row_count,
        "target_nonnull_signal_count": target_nonnull_signal_count,
        "predecision_signal_dates": sorted(
            predecision_signals.dt.date.astype(str).unique().tolist()
        ),
        "target_signal_dates": sorted(
            target_signals.dt.date.astype(str).unique().tolist()
        ),
        "boundary_policy": "execution_date_le_eval_is_predecision_and_gt_eval_le_next_is_target",
    }


def _read_job(campaign_dir: Path, job_id: str) -> pd.Series:
    jobs = pd.read_csv(campaign_dir / "jobs.csv", dtype={"job_id": str})
    rows = jobs[jobs["job_id"].eq(job_id)]
    if len(rows) != 1:
        raise RuntimeError(f"worker_job_shape:{job_id}:{len(rows)}")
    return rows.iloc[0]


def _assert_active_release(live_cfg: Any) -> None:
    if live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_ID != FORMAL_RELEASE_ID:
        raise RuntimeError("active_release_drift")
    observed = Path(live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH).resolve()
    if observed != FORMAL_ELIGIBILITY.resolve():
        raise RuntimeError(f"active_eligibility_path_drift:{observed}")


def _validate_frozen_official_overrides(
    overrides: Any, *, campaign_dir: Path | None = None
) -> dict[str, Any]:
    if not isinstance(overrides, dict):
        raise RuntimeError("frozen_official_overrides_not_object")
    required = {
        "product_universe_csv_path",
        "ai_product_pool_eligibility_path",
        "ai_product_pool_strategy",
    }
    missing = required - set(overrides)
    if missing:
        raise RuntimeError(f"frozen_official_overrides_missing:{sorted(missing)}")
    invalid_types = {
        key: type(value).__name__
        for key, value in overrides.items()
        if not isinstance(value, (bool, int, float, str))
    }
    if invalid_types:
        raise RuntimeError(f"frozen_official_overrides_non_scalar:{invalid_types}")
    _stable_json(overrides)
    universe_path = Path(str(overrides["product_universe_csv_path"])).resolve()
    if not universe_path.is_file():
        raise RuntimeError(f"frozen_product_universe_missing:{universe_path}")
    if campaign_dir is not None:
        expected_universe = (
            campaign_dir / OFFICIAL_PRODUCT_UNIVERSE_FILENAME
        ).resolve()
        if universe_path != expected_universe:
            raise RuntimeError(
                f"frozen_product_universe_not_campaign_private:{universe_path}"
            )
    eligibility_path = Path(
        str(overrides["ai_product_pool_eligibility_path"])
    ).resolve()
    if eligibility_path != FORMAL_ELIGIBILITY.resolve():
        raise RuntimeError(
            f"frozen_formal_eligibility_drift:{eligibility_path}"
        )
    if str(overrides["ai_product_pool_strategy"]) != OFFICIAL_STRATEGY:
        raise RuntimeError("frozen_official_strategy_drift")
    return dict(overrides)


def _snapshot_product_universe(campaign_dir: Path, source: Path) -> Path:
    destination = campaign_dir / OFFICIAL_PRODUCT_UNIVERSE_FILENAME
    if destination.exists():
        raise RuntimeError(f"frozen_product_universe_already_exists:{destination}")
    source = source.resolve()
    source_before = _load_stage007()._file_identity(source)
    payload = source.read_bytes()
    source_after = _load_stage007()._file_identity(source)
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    if (
        not payload
        or source_before != source_after
        or len(payload) != int(source_before["size"])
        or payload_sha256 != source_before["sha256"]
    ):
        raise RuntimeError("frozen_product_universe_source_unstable")

    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        frame = pd.read_csv(temporary)
        if frame.empty:
            raise RuntimeError("frozen_product_universe_empty")
        symbol_columns = {"product_vt_symbol", "vt_symbol"}.intersection(
            frame.columns
        )
        if not symbol_columns:
            raise RuntimeError("frozen_product_universe_symbol_column_missing")
        symbol_column = (
            "product_vt_symbol"
            if "product_vt_symbol" in symbol_columns
            else "vt_symbol"
        )
        symbols = frame[symbol_column].dropna().astype(str).str.strip()
        if symbols.eq("").all() or symbols.empty:
            raise RuntimeError("frozen_product_universe_symbols_empty")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    destination_identity = _load_stage007()._file_identity(destination)
    if (
        destination_identity["size"] != source_before["size"]
        or destination_identity["sha256"] != source_before["sha256"]
    ):
        raise RuntimeError("frozen_product_universe_copy_mismatch")
    return destination.resolve()


def _freeze_official_overrides(campaign_dir: Path, live_cfg: Any) -> dict[str, Any]:
    path = campaign_dir / OFFICIAL_OVERRIDES_FILENAME
    if path.exists():
        raise RuntimeError(f"frozen_official_overrides_already_exists:{path}")
    overrides = _validate_frozen_official_overrides(
        dict(live_cfg.build_official_live_strategy_overrides())
    )
    source_universe = Path(str(overrides["product_universe_csv_path"]))
    overrides["product_universe_csv_path"] = str(
        _snapshot_product_universe(campaign_dir, source_universe)
    )
    overrides = _validate_frozen_official_overrides(
        overrides, campaign_dir=campaign_dir
    )
    _write_json(path, overrides)
    return overrides


def _load_frozen_official_overrides(campaign_dir: Path) -> dict[str, Any]:
    path = campaign_dir / OFFICIAL_OVERRIDES_FILENAME
    if not path.is_file():
        raise RuntimeError(f"frozen_official_overrides_missing:{path}")
    return _validate_frozen_official_overrides(
        json.loads(path.read_text(encoding="utf-8")),
        campaign_dir=campaign_dir,
    )


def _stage819_config_module(s901: Any) -> Any:
    try:
        return s901.s847.s825.stage819_cfg
    except AttributeError as exc:
        raise RuntimeError("stage819_profile_builder_module_missing") from exc


def _stage777_config_module(stage819_cfg: Any) -> Any:
    try:
        return stage819_cfg.stage813_cfg.stage777_cfg
    except AttributeError as exc:
        raise RuntimeError("stage777_shared_builder_module_missing") from exc


def _validate_stage819_profile_overrides(
    overrides: Any, *, campaign_dir: Path | None = None
) -> dict[str, Any]:
    if not isinstance(overrides, dict):
        raise RuntimeError("stage819_profile_overrides_not_object")
    required = {
        "product_universe_csv_path",
        "ai_product_pool_eligibility_path",
        "ai_product_pool_strategy",
    }
    missing = required - set(overrides)
    if missing:
        raise RuntimeError(f"stage819_profile_overrides_missing:{sorted(missing)}")
    invalid_types = {
        key: type(value).__name__
        for key, value in overrides.items()
        if not isinstance(value, (bool, int, float, str))
    }
    if invalid_types:
        raise RuntimeError(f"stage819_profile_overrides_non_scalar:{invalid_types}")
    _stable_json(overrides)
    universe_path = Path(str(overrides["product_universe_csv_path"])).resolve()
    eligibility_path = Path(
        str(overrides["ai_product_pool_eligibility_path"])
    ).resolve()
    if not universe_path.is_file():
        raise RuntimeError(f"stage819_profile_universe_missing:{universe_path}")
    if not eligibility_path.is_file():
        raise RuntimeError(
            f"stage819_profile_eligibility_missing:{eligibility_path}"
        )
    if not str(overrides["ai_product_pool_strategy"]).strip():
        raise RuntimeError("stage819_profile_strategy_empty")
    if campaign_dir is not None:
        expected_universe = (
            campaign_dir / OFFICIAL_PRODUCT_UNIVERSE_FILENAME
        ).resolve()
        expected_eligibility = (
            campaign_dir / STAGE819_PROFILE_ELIGIBILITY_FILENAME
        ).resolve()
        if universe_path != expected_universe:
            raise RuntimeError("stage819_profile_universe_not_campaign_private")
        if eligibility_path != expected_eligibility:
            raise RuntimeError("stage819_profile_eligibility_not_campaign_private")
    return dict(overrides)


def _snapshot_stage819_profile_eligibility(
    campaign_dir: Path, source: Path
) -> Path:
    destination = campaign_dir / STAGE819_PROFILE_ELIGIBILITY_FILENAME
    if destination.exists():
        raise RuntimeError(
            f"stage819_profile_eligibility_already_exists:{destination}"
        )
    source = source.resolve()
    source_before = _load_stage007()._file_identity(source)
    payload = source.read_bytes()
    source_after = _load_stage007()._file_identity(source)
    if (
        not payload
        or source_before != source_after
        or len(payload) != int(source_before["size"])
        or hashlib.sha256(payload).hexdigest() != source_before["sha256"]
    ):
        raise RuntimeError("stage819_profile_eligibility_source_unstable")
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        frame = pd.read_csv(temporary)
        required = {
            "strategy",
            "eval_date",
            "product_vt_symbol",
            "score",
            "score_rank",
            "top_n",
        }
        missing = required - set(frame.columns)
        if missing:
            raise RuntimeError(
                f"stage819_profile_eligibility_columns_missing:{sorted(missing)}"
            )
        symbols = frame["product_vt_symbol"].dropna().astype(str).str.strip()
        if frame.empty or symbols.empty or symbols.eq("").all():
            raise RuntimeError("stage819_profile_eligibility_empty")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    destination_identity = _load_stage007()._file_identity(destination)
    if (
        destination_identity["size"] != source_before["size"]
        or destination_identity["sha256"] != source_before["sha256"]
    ):
        raise RuntimeError("stage819_profile_eligibility_copy_mismatch")
    return destination.resolve()


def _freeze_stage819_profile_overrides(
    campaign_dir: Path, s901: Any
) -> dict[str, Any]:
    path = campaign_dir / STAGE819_PROFILE_OVERRIDES_FILENAME
    if path.exists():
        raise RuntimeError(f"stage819_profile_overrides_already_exists:{path}")
    stage819_cfg = _stage819_config_module(s901)
    overrides = _validate_stage819_profile_overrides(
        dict(stage819_cfg.build_official_candidate_stage819_30w_overrides())
    )
    shared_universe = Path(str(overrides["product_universe_csv_path"]))
    private_universe = campaign_dir / OFFICIAL_PRODUCT_UNIVERSE_FILENAME
    shared_identity = _load_stage007()._file_identity(shared_universe)
    private_identity = _load_stage007()._file_identity(private_universe)
    if (
        shared_identity["size"] != private_identity["size"]
        or shared_identity["sha256"] != private_identity["sha256"]
    ):
        raise RuntimeError("stage819_profile_universe_snapshot_mismatch")
    private_eligibility = _snapshot_stage819_profile_eligibility(
        campaign_dir,
        Path(str(overrides["ai_product_pool_eligibility_path"])),
    )
    overrides["product_universe_csv_path"] = str(private_universe.resolve())
    overrides["ai_product_pool_eligibility_path"] = str(private_eligibility)
    overrides = _validate_stage819_profile_overrides(
        overrides, campaign_dir=campaign_dir
    )
    _write_json(path, overrides)
    return overrides


def _load_frozen_stage819_profile_overrides(
    campaign_dir: Path,
) -> dict[str, Any]:
    path = campaign_dir / STAGE819_PROFILE_OVERRIDES_FILENAME
    if not path.is_file():
        raise RuntimeError(f"stage819_profile_overrides_missing:{path}")
    return _validate_stage819_profile_overrides(
        json.loads(path.read_text(encoding="utf-8")),
        campaign_dir=campaign_dir,
    )


def _candidate_strategy_overrides(
    campaign_dir: Path, eligibility_path: Path
) -> dict[str, Any]:
    overrides = _load_frozen_official_overrides(campaign_dir)
    overrides["ai_product_pool_eligibility_path"] = str(eligibility_path.resolve())
    overrides["ai_product_pool_strategy"] = OFFICIAL_STRATEGY
    return overrides


def _shared_builder_source_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "dev": int(stat.st_dev),
        "inode": int(stat.st_ino),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "ctime_ns": int(stat.st_ctime_ns),
        "sha256": _sha256(resolved),
    }


def _blocked_original_universe_builder(*_args: Any, **_kwargs: Any) -> Path:
    audit = globals()["__stage015_original_shared_builder_guard_audit__"]
    audit["original_universe_builder_call_count"] += 1
    audit["original_shared_builder_call_count"] += 1
    raise RuntimeError("stage015_original_shared_builder_called:universe")


def _blocked_original_eligibility_builder(*_args: Any, **_kwargs: Any) -> Path:
    audit = globals()["__stage015_original_shared_builder_guard_audit__"]
    audit["original_eligibility_builder_call_count"] += 1
    audit["original_shared_builder_call_count"] += 1
    raise RuntimeError("stage015_original_shared_builder_called:eligibility")


@contextmanager
def _redirect_shared_builder_bindings(
    *,
    s513: Any,
    s901: Any,
    campaign_dir: Path,
):
    stage819_cfg = _stage819_config_module(s901)
    stage777_cfg = _stage777_config_module(stage819_cfg)
    original_universe_builder = stage777_cfg.build_static18_plus_fu_universe
    original_eligibility_builder = (
        stage777_cfg.build_ai_satellite_post_signal_eligibility
    )
    private_universe = (
        campaign_dir / OFFICIAL_PRODUCT_UNIVERSE_FILENAME
    ).resolve()
    private_eligibility = (
        campaign_dir / STAGE819_PROFILE_ELIGIBILITY_FILENAME
    ).resolve()
    if not private_universe.is_file() or not private_eligibility.is_file():
        raise RuntimeError("stage015_private_shared_builder_redirect_input_missing")

    shared_universe = Path(
        original_universe_builder.__globals__["UNIVERSE_PATH"]
    ).resolve()
    shared_eligibility = Path(
        original_eligibility_builder.__globals__[
            "AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH"
        ]
    ).resolve()
    source_identity_before = {
        "universe": _shared_builder_source_identity(shared_universe),
        "eligibility": _shared_builder_source_identity(shared_eligibility),
    }

    audit: dict[str, Any] = {
        "binding_count": 0,
        "universe_binding_count": 0,
        "eligibility_binding_count": 0,
        "universe_redirect_call_count": 0,
        "eligibility_redirect_call_count": 0,
        "original_shared_builder_guard_installed": False,
        "original_universe_builder_call_count": 0,
        "original_eligibility_builder_call_count": 0,
        "original_shared_builder_call_count": 0,
        "shared_builder_source_identity_before": source_identity_before,
        "shared_builder_source_identity_after": None,
        "shared_builder_source_identity_pass": False,
        "shared_builder_required_binding_coverage_pass": False,
        "shared_builder_required_bindings": [],
        "dynamic_binding_restore_count": 0,
        "binding_modules": [],
    }

    def universe_redirect(*_args: Any, **_kwargs: Any) -> Path:
        audit["universe_redirect_call_count"] += 1
        return private_universe

    def eligibility_redirect(*_args: Any, **_kwargs: Any) -> Path:
        audit["eligibility_redirect_call_count"] += 1
        return private_eligibility

    replacements = (
        (original_universe_builder, universe_redirect, "universe"),
        (original_eligibility_builder, eligibility_redirect, "eligibility"),
    )
    bindings: list[tuple[dict[str, Any], str, Any, Any, str]] = []
    seen: set[tuple[int, str]] = set()
    guarded_functions: list[
        tuple[Any, Any, tuple[Any, ...] | None, dict[str, Any] | None]
    ] = []
    guard_namespaces: list[dict[str, Any]] = []
    guard_namespace_ids: set[int] = set()
    guard_global = "__stage015_original_shared_builder_guard_audit__"

    def capture_bindings(*, original_values: bool, dynamic: bool) -> None:
        for module_name, module in tuple(sys.modules.items()):
            namespace = getattr(module, "__dict__", None)
            if not isinstance(namespace, dict):
                continue
            for key, value in tuple(namespace.items()):
                for original, redirect, label in replacements:
                    expected = original if original_values else redirect
                    binding_key = (id(namespace), key)
                    if value is not expected or binding_key in seen:
                        continue
                    seen.add(binding_key)
                    bindings.append((namespace, key, original, redirect, label))
                    if original_values:
                        namespace[key] = redirect
                    audit[f"{label}_binding_count"] += 1
                    audit["binding_modules"].append(f"{module_name}:{key}")
                    if dynamic:
                        audit["dynamic_binding_restore_count"] += 1

    post_error: BaseException | None = None
    try:
        for original, blocker in (
            (original_universe_builder, _blocked_original_universe_builder),
            (
                original_eligibility_builder,
                _blocked_original_eligibility_builder,
            ),
        ):
            if original.__closure__ or blocker.__closure__:
                raise RuntimeError("stage015_original_builder_guard_closure_unsupported")
            namespace = original.__globals__
            namespace_id = id(namespace)
            if namespace_id not in guard_namespace_ids:
                if guard_global in namespace:
                    raise RuntimeError("stage015_original_builder_guard_already_installed")
                namespace[guard_global] = audit
                guard_namespaces.append(namespace)
                guard_namespace_ids.add(namespace_id)
            guarded_functions.append(
                (original, original.__code__, original.__defaults__, original.__kwdefaults__)
            )
            original.__code__ = blocker.__code__
            original.__defaults__ = blocker.__defaults__
            original.__kwdefaults__ = blocker.__kwdefaults__
        audit["original_shared_builder_guard_installed"] = (
            len(guarded_functions) == 2
        )

        capture_bindings(original_values=True, dynamic=False)
        audit["binding_count"] = len(bindings)
        metadata_c3 = s513._metadata.__globals__.get("_c3_overrides")
        stage78_builder = getattr(metadata_c3, "__globals__", {}).get(
            "build_official_stage78_overrides"
        )
        stage78_globals = getattr(stage78_builder, "__globals__", {})
        origin_globals = original_universe_builder.__globals__
        stage777_globals = getattr(stage777_cfg, "__dict__", {})
        required_bindings = (
            (
                origin_globals,
                "build_static18_plus_fu_universe",
                universe_redirect,
                REQUIRED_SHARED_BUILDER_BINDINGS[0],
            ),
            (
                origin_globals,
                "build_ai_satellite_post_signal_eligibility",
                eligibility_redirect,
                REQUIRED_SHARED_BUILDER_BINDINGS[1],
            ),
            (
                stage78_globals,
                "build_static18_plus_fu_universe",
                universe_redirect,
                REQUIRED_SHARED_BUILDER_BINDINGS[2],
            ),
            (
                stage78_globals,
                "build_ai_satellite_post_signal_eligibility",
                eligibility_redirect,
                REQUIRED_SHARED_BUILDER_BINDINGS[3],
            ),
            (
                stage777_globals,
                "build_static18_plus_fu_universe",
                universe_redirect,
                REQUIRED_SHARED_BUILDER_BINDINGS[4],
            ),
            (
                stage777_globals,
                "build_ai_satellite_post_signal_eligibility",
                eligibility_redirect,
                REQUIRED_SHARED_BUILDER_BINDINGS[5],
            ),
        )
        covered = [
            label
            for namespace, key, redirect, label in required_bindings
            if namespace.get(key) is redirect
        ]
        audit["shared_builder_required_bindings"] = covered
        audit["shared_builder_required_binding_coverage_pass"] = (
            tuple(covered) == REQUIRED_SHARED_BUILDER_BINDINGS
        )
        if not audit["shared_builder_required_binding_coverage_pass"]:
            raise RuntimeError("stage78_import_by_value_redirect_missing")
        if (
            audit["universe_binding_count"] < 3
            or audit["eligibility_binding_count"] < 3
        ):
            raise RuntimeError(f"shared_builder_binding_coverage_too_small:{audit}")
        yield audit
    finally:
        try:
            source_identity_after = {
                "universe": _shared_builder_source_identity(shared_universe),
                "eligibility": _shared_builder_source_identity(shared_eligibility),
            }
            audit["shared_builder_source_identity_after"] = source_identity_after
            audit["shared_builder_source_identity_pass"] = (
                source_identity_before == source_identity_after
            )
            if audit["original_shared_builder_call_count"] != 0:
                post_error = RuntimeError(
                    "stage015_original_shared_builder_call_detected"
                )
            elif not audit["shared_builder_source_identity_pass"]:
                post_error = RuntimeError(
                    "stage015_shared_builder_source_identity_changed"
                )
        except BaseException as exc:
            post_error = RuntimeError(
                "stage015_shared_builder_source_identity_unreadable"
            )
            post_error.__cause__ = exc
        finally:
            capture_bindings(original_values=False, dynamic=True)
            audit["binding_count"] = len(bindings)
            for namespace, key, original, _redirect, _label in reversed(bindings):
                namespace[key] = original
            for original, code, defaults, kwdefaults in reversed(guarded_functions):
                original.__code__ = code
                original.__defaults__ = defaults
                original.__kwdefaults__ = kwdefaults
            for namespace in reversed(guard_namespaces):
                namespace.pop(guard_global, None)
        if post_error is not None:
            raise post_error


def _run_live_c9_with_frozen_builders(
    *,
    s901: Any,
    metadata: dict[str, Any],
    campaign_dir: Path,
    eligibility_path: Path,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    stage819_cfg = _stage819_config_module(s901)
    stage777_cfg = _stage777_config_module(stage819_cfg)
    profile_overrides = _load_frozen_stage819_profile_overrides(campaign_dir)

    def candidate_builder() -> dict[str, Any]:
        return _candidate_strategy_overrides(campaign_dir, eligibility_path)

    def profile_builder() -> dict[str, Any]:
        return dict(profile_overrides)

    def forbidden_shared_builder(*_args: Any, **_kwargs: Any) -> Path:
        raise RuntimeError("stage015_worker_shared_builder_forbidden")

    original_live_builder = s901.build_official_live_strategy_overrides
    original_profile_builder = (
        stage819_cfg.build_official_candidate_stage819_30w_overrides
    )
    original_universe_builder = stage777_cfg.build_static18_plus_fu_universe
    original_eligibility_builder = (
        stage777_cfg.build_ai_satellite_post_signal_eligibility
    )
    try:
        s901.build_official_live_strategy_overrides = candidate_builder
        stage819_cfg.build_official_candidate_stage819_30w_overrides = profile_builder
        stage777_cfg.build_static18_plus_fu_universe = forbidden_shared_builder
        stage777_cfg.build_ai_satellite_post_signal_eligibility = (
            forbidden_shared_builder
        )
        return s901._run_live_c9(metadata, START, analysis_end)
    finally:
        s901.build_official_live_strategy_overrides = original_live_builder
        stage819_cfg.build_official_candidate_stage819_30w_overrides = (
            original_profile_builder
        )
        stage777_cfg.build_static18_plus_fu_universe = original_universe_builder
        stage777_cfg.build_ai_satellite_post_signal_eligibility = (
            original_eligibility_builder
        )


def _campaign_reuse_forbidden(campaign_dir: Path) -> bool:
    abandoned = campaign_dir / "ABANDONED.json"
    if abandoned.exists():
        return True
    failure_receipt = campaign_dir / "failure_receipt.json"
    if not failure_receipt.is_file():
        return False
    try:
        payload = json.loads(failure_receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return True
    return (
        payload.get("reuse_forbidden") is True
        or payload.get("campaign_reuse_allowed") is False
        or payload.get("cross_campaign_job_output_reuse_allowed") is False
    )


def _assert_campaign_reusable(campaign_dir: Path) -> None:
    if _campaign_reuse_forbidden(campaign_dir):
        raise RuntimeError(f"campaign_reuse_forbidden:{campaign_dir.resolve()}")


def _output_hashes(directory: Path, names: Iterable[str]) -> dict[str, str]:
    return {name: _sha256(directory / name) for name in sorted(names)}


def _run_worker(job_id: str, campaign_dir: Path) -> None:
    _assert_campaign_reusable(campaign_dir)
    if Path.cwd().resolve() != RUNTIME_ROOT.resolve():
        raise RuntimeError(f"worker_wrong_runtime:{Path.cwd().resolve()}")
    if os.environ.get("STAGE015_CAMPAIGN_DIR") != str(campaign_dir.resolve()):
        raise RuntimeError("worker_campaign_environment_mismatch")
    if os.environ.get("STAGE015_JOB_ID") != job_id:
        raise RuntimeError("worker_job_environment_mismatch")
    job = _read_job(campaign_dir, job_id)
    if str(job["split"]) != "development":
        raise RuntimeError("worker_non_development_job")
    final_dir = campaign_dir / "job_outputs" / job_id
    if final_dir.exists():
        raise RuntimeError(f"cold_job_output_already_exists:{job_id}")
    run_token = Path(os.environ.get("TMPDIR", "missing_tmpdir")).parent.name
    partial_dir = campaign_dir / ".partial" / f"{job_id}_{os.getpid()}_{run_token}"
    if partial_dir.exists():
        raise RuntimeError(f"partial_job_output_exists:{partial_dir}")
    partial_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        campaign_identity = json.loads(
            (campaign_dir / "campaign_identity.json").read_text(encoding="utf-8")
        )
        if (
            campaign_identity["files"]["runtime_database"]["sha256"]
            != EXPECTED_DATABASE_SHA256
        ):
            raise RuntimeError("campaign_database_identity_drift")
        execution_before = _worker_execution_manifest(
            campaign_dir, job, campaign_identity
        )
        stage004 = _load_stage004()
        live_cfg, s513, s827, s901 = stage004._load_production_modules()
        _assert_active_release(live_cfg)
        eligibility_path = (
            campaign_dir / "eligibility" / f"{job['eligibility_key']}.csv"
        )
        eval_date = pd.Timestamp(job["eval_date"])
        end = pd.Timestamp(job["next_eval_date"])
        with _redirect_shared_builder_bindings(
            s513=s513,
            s901=s901,
            campaign_dir=campaign_dir,
        ) as shared_builder_redirect_audit:
            metadata = s513._metadata()
            s901._ensure_c9_minute_bars(metadata)
            runtime_before = _runtime_contract()
            combined, frames, live_spec = _run_live_c9_with_frozen_builders(
                s901=s901,
                metadata=metadata,
                campaign_dir=campaign_dir,
                eligibility_path=eligibility_path,
                analysis_end=end,
            )

        capital = replace(live_spec.capital, variant=PROFILE, label=PROFILE)
        metric_spec = replace(live_spec, capital=capital, profile=PROFILE)
        summary, curve = s827._metric(
            {"profile": PROFILE, "spec": metric_spec}, combined
        )
        true_window = f"2018-01-01_to_{end.date().isoformat()}"
        summary["window_name"] = f"stage015_2018_to_{end.strftime('%Y%m%d')}"
        summary["window_label"] = true_window
        curve["window_name"] = f"stage015_2018_to_{end.strftime('%Y%m%d')}"
        curve["window_label"] = true_window
        payloads = {
            "curve": curve,
            "combined": combined,
            "trades": frames.get("trades", pd.DataFrame()).copy(),
            "entry_candidates": frames.get("entry_candidates", pd.DataFrame()).copy(),
            "entry_risk": frames.get("entry_risk", pd.DataFrame()).copy(),
            "trade_events": frames.get("trade_events", pd.DataFrame()).copy(),
        }
        for name, frame in payloads.items():
            if frame.empty and not any(
                column in frame.columns for column in ("date", "datetime", "trading_day")
            ):
                raise RuntimeError(f"payload_schema_missing_date:{name}:{job_id}")
        predecision = _predecision_signatures(payloads, eval_date)
        target = _target_payloads(payloads, eval_date, end)
        boundary_gate = _entry_candidate_boundary_gate(
            payloads, target, eval_date
        )
        if not boundary_gate["passed"]:
            raise RuntimeError(f"entry_candidate_boundary_failed:{boundary_gate}")
        label = _load_stage010().future_period_label(curve, eval_date)

        internal_errors = {
            "end_equity_vs_future_net_pnl_error": monetary_reconciliation_error(
                end_equity=label["end_equity"],
                base_equity=label["base_equity"],
                net_pnl=label["future_net_pnl"],
            ),
            "target_curve_net_pnl_error": float(
                pd.to_numeric(target["curve"]["net_pnl"], errors="raise").sum()
            )
            - float(label["future_net_pnl"]),
            "target_curve_slippage_error": float(
                pd.to_numeric(
                    target["curve"][
                        "slippage"
                        if "slippage" in target["curve"].columns
                        else "total_slippage"
                    ],
                    errors="raise",
                ).sum()
            )
            - float(label["future_slippage"]),
            "target_curve_trade_count_error": float(
                pd.to_numeric(target["curve"]["trade_count"], errors="raise").sum()
            )
            - float(label["future_trade_count"]),
            "target_combined_net_pnl_error": float(
                pd.to_numeric(target["combined"]["net_pnl"], errors="raise").sum()
            )
            - float(label["future_net_pnl"]),
            "target_combined_slippage_error": float(
                pd.to_numeric(target["combined"]["slippage"], errors="raise").sum()
            )
            - float(label["future_slippage"]),
            "target_combined_trade_count_error": float(
                pd.to_numeric(target["combined"]["trade_count"], errors="raise").sum()
            )
            - float(label["future_trade_count"]),
            "target_trade_rows_error": float(len(target["trades"]))
            - float(label["future_trade_count"]),
        }
        if max(abs(value) for value in internal_errors.values()) > 1e-9:
            raise RuntimeError(f"worker_label_reconciliation_failed:{internal_errors}")

        runtime_after = _runtime_contract()
        _assert_runtime_stable(runtime_before, runtime_after)
        execution_after = _worker_execution_manifest(
            campaign_dir, job, campaign_identity
        )
        if execution_before != execution_after:
            raise RuntimeError("worker_execution_input_identity_changed")

        summary = _canonical_payload(summary)
        summary.to_csv(partial_dir / "summary.csv", index=False, lineterminator="\n")
        _write_json(partial_dir / "label.json", label)
        for name, frame in target.items():
            frame.to_csv(
                partial_dir / f"{name}.csv", index=False, lineterminator="\n"
            )
        output_names = ["summary.csv", "label.json"] + [
            f"{name}.csv" for name in PAYLOAD_NAMES
        ]
        output_hashes = _output_hashes(partial_dir, output_names)
        wall_seconds = time.monotonic() - started
        if wall_seconds > MAX_JOB_SECONDS:
            raise RuntimeError(f"worker_wall_seconds_exceeded:{wall_seconds}")
        receipt = {
            "job_id": job_id,
            "job_type": str(job["job_type"]),
            "eval_date": str(job["eval_date"]),
            "next_eval_date": str(job["next_eval_date"]),
            "candidate_rank": int(job["candidate_rank"]),
            "campaign_id": campaign_dir.name,
            "campaign_path": str(campaign_dir.resolve()),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "fresh_process_pid": os.getpid(),
            "checkpoint_reused": False,
            "completed_result_reused": False,
            "input_identity_pass": True,
            "campaign_file_contract_sha256": campaign_identity[
                "file_contract_sha256"
            ],
            "execution_file_contract_sha256": execution_before[
                "file_contract_sha256"
            ],
            "execution_unique_physical_file_count": execution_before[
                "unique_physical_file_count"
            ],
            "official_overrides_source": "campaign_snapshot",
            "official_overrides_sha256": _sha256(
                campaign_dir / OFFICIAL_OVERRIDES_FILENAME
            ),
            "product_universe_sha256": _sha256(
                campaign_dir / OFFICIAL_PRODUCT_UNIVERSE_FILENAME
            ),
            "stage819_profile_overrides_source": "campaign_snapshot",
            "stage819_profile_overrides_sha256": _sha256(
                campaign_dir / STAGE819_PROFILE_OVERRIDES_FILENAME
            ),
            "stage819_profile_eligibility_sha256": _sha256(
                campaign_dir / STAGE819_PROFILE_ELIGIBILITY_FILENAME
            ),
            "nested_shared_builder_guard_enabled": True,
            "shared_builder_binding_redirect_count": int(
                shared_builder_redirect_audit["binding_count"]
            ),
            "shared_universe_binding_redirect_count": int(
                shared_builder_redirect_audit["universe_binding_count"]
            ),
            "shared_eligibility_binding_redirect_count": int(
                shared_builder_redirect_audit["eligibility_binding_count"]
            ),
            "shared_universe_redirect_call_count": int(
                shared_builder_redirect_audit["universe_redirect_call_count"]
            ),
            "shared_eligibility_redirect_call_count": int(
                shared_builder_redirect_audit["eligibility_redirect_call_count"]
            ),
            "original_shared_builder_guard_installed": bool(
                shared_builder_redirect_audit[
                    "original_shared_builder_guard_installed"
                ]
            ),
            "original_universe_builder_call_count": int(
                shared_builder_redirect_audit[
                    "original_universe_builder_call_count"
                ]
            ),
            "original_eligibility_builder_call_count": int(
                shared_builder_redirect_audit[
                    "original_eligibility_builder_call_count"
                ]
            ),
            "original_shared_builder_call_count": int(
                shared_builder_redirect_audit["original_shared_builder_call_count"]
            ),
            "shared_builder_source_identity_pass": bool(
                shared_builder_redirect_audit[
                    "shared_builder_source_identity_pass"
                ]
            ),
            "shared_builder_source_identity_before": dict(
                shared_builder_redirect_audit[
                    "shared_builder_source_identity_before"
                ]
            ),
            "shared_builder_source_identity_after": dict(
                shared_builder_redirect_audit[
                    "shared_builder_source_identity_after"
                ]
            ),
            "shared_builder_required_binding_coverage_pass": bool(
                shared_builder_redirect_audit[
                    "shared_builder_required_binding_coverage_pass"
                ]
            ),
            "shared_builder_required_bindings": list(
                shared_builder_redirect_audit[
                    "shared_builder_required_bindings"
                ]
            ),
            "dynamic_binding_restore_count": int(
                shared_builder_redirect_audit["dynamic_binding_restore_count"]
            ),
            "shared_builder_redirect_bindings": list(
                shared_builder_redirect_audit["binding_modules"]
            ),
            "runtime": runtime_before,
            "normalized_runtime_sha256": normalized_runtime_sha256(runtime_before),
            "wall_seconds": wall_seconds,
            "tmpdir": os.environ.get("TMPDIR", ""),
            "mplconfigdir": os.environ.get("MPLCONFIGDIR", ""),
            "predecision_sha256": predecision,
            "entry_candidate_boundary_gate": boundary_gate,
            "internal_reconciliation_errors": internal_errors,
            "monetary_reconciliation_quantum": str(MONEY_QUANTUM),
            "output_sha256": output_hashes,
        }
        _write_json(partial_dir / "worker_receipt.json", receipt)
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        partial_dir.rename(final_dir)
        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "wall_seconds": wall_seconds,
                    "completed": True,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
    except BaseException:
        shutil.rmtree(partial_dir, ignore_errors=True)
        raise


def _prepare_campaign() -> Path:
    if not RUNTIME_DATABASE.is_file():
        raise RuntimeError("runtime_database_missing")
    review_text = STAGE012_REVIEW.read_text(encoding="utf-8")
    if "PASS_WITH_P2" not in review_text or "ALLOW_COVERAGE_STUDY_ONLY" not in review_text:
        raise RuntimeError("stage012_review_gate_not_satisfied")
    feature_contract = json.loads(FEATURE_CONTRACT.read_text(encoding="utf-8"))
    if feature_contract.get("decision") != "stage014_nine_feature_prelabel_contract_frozen":
        raise RuntimeError("stage014_feature_contract_not_frozen")
    panel = pd.read_csv(FEATURE_PANEL)
    jobs = build_development_jobs(panel)
    formal = pd.read_csv(FORMAL_ELIGIBILITY)
    ranking = pd.read_csv(FULL_RANKING)
    ranking_alignment = validate_job_ranking_alignment(jobs, ranking)

    BASE_OUT.mkdir(parents=True, exist_ok=True)
    campaign_id = (
        datetime.now().astimezone().strftime("campaign_%Y%m%dT%H%M%S%z")
        + f"_{os.getpid()}"
    )
    campaign_dir = BASE_OUT / campaign_id
    campaign_dir.mkdir(parents=False, exist_ok=False)
    prepare_tombstone = campaign_dir / "ABANDONED.json"
    _atomic_json(
        prepare_tombstone,
        {
            "campaign_id": campaign_id,
            "status": "prepare_failed",
            "decision": "stage015_prepare_not_completed_reuse_forbidden",
            "reuse_forbidden": True,
            "development_labels_published": False,
        },
    )
    (campaign_dir / "eligibility").mkdir()
    (campaign_dir / "logs").mkdir()
    (campaign_dir / "locks").mkdir()
    (campaign_dir / ".partial").mkdir()
    jobs.to_csv(campaign_dir / "jobs.csv", index=False, lineterminator="\n")

    audit_rows: list[dict[str, Any]] = []
    for job in jobs[jobs["job_type"].eq("main")].itertuples(index=False):
        candidate = build_candidate_eligibility(
            formal,
            ranking,
            eval_date=str(job.eval_date),
            candidate_rank=int(job.candidate_rank),
        )
        output = campaign_dir / "eligibility" / f"{job.eligibility_key}.csv"
        candidate.to_csv(output, index=False, lineterminator="\n")
        baseline = canonical_eligibility(formal)
        changed = baseline.ne(candidate).any(axis=1)
        audit_rows.append(
            {
                "job_id": job.job_id,
                "eval_date": job.eval_date,
                "candidate_rank": int(job.candidate_rank),
                "candidate_product": job.product_vt_symbol,
                "changed_row_count": int(changed.sum()),
                "changed_target_rank10_only": bool(
                    int(changed.sum()) == (0 if int(job.candidate_rank) == 10 else 1)
                    and (
                        int(job.candidate_rank) == 10
                        or bool(
                            changed[
                                baseline["eval_date"].eq(str(job.eval_date))
                                & baseline["score_rank"].eq(10)
                            ].all()
                        )
                    )
                ),
            }
        )
    audit = pd.DataFrame(audit_rows)
    if len(audit) != 351 or not audit["changed_target_rank10_only"].all():
        raise RuntimeError("campaign_eligibility_audit_failed")
    audit.to_csv(
        campaign_dir / "eligibility_audit.csv", index=False, lineterminator="\n"
    )
    _write_json(campaign_dir / "ranking_alignment.json", ranking_alignment)

    stage004 = _load_stage004()
    live_cfg, _s513, _s827, s901 = stage004._load_production_modules()
    _assert_active_release(live_cfg)
    _freeze_official_overrides(campaign_dir, live_cfg)
    _freeze_stage819_profile_overrides(campaign_dir, s901)
    manifest = _campaign_manifest(campaign_dir, s901=s901)
    observed_database = manifest["files"]["runtime_database"]["sha256"]
    if observed_database != EXPECTED_DATABASE_SHA256:
        raise RuntimeError(f"runtime_database_identity_drift:{observed_database}")
    _write_json(campaign_dir / "campaign_identity.json", manifest)
    status = {
        "campaign_id": campaign_id,
        "campaign_path": str(campaign_dir.resolve()),
        "status": "prepared",
        "completed_jobs": 0,
        "total_jobs": 355,
        "campaign_file_contract_sha256": manifest["file_contract_sha256"],
    }
    _write_json(campaign_dir / "progress.json", status)
    _write_json(BASE_OUT / "LATEST.json", status)
    prepare_tombstone.unlink()
    return campaign_dir


def _valid_shared_source_identity(identity: Any) -> bool:
    if not isinstance(identity, dict) or set(identity) != {
        "universe",
        "eligibility",
    }:
        return False
    required = {
        "path",
        "dev",
        "inode",
        "size",
        "mtime_ns",
        "ctime_ns",
        "sha256",
    }
    for value in identity.values():
        if not isinstance(value, dict) or set(value) != required:
            return False
        if not Path(str(value["path"])).is_absolute():
            return False
        if any(
            not isinstance(value[key], int)
            for key in ("dev", "inode", "size", "mtime_ns", "ctime_ns")
        ):
            return False
        if len(str(value["sha256"])) != 64:
            return False
    return True


def _shared_builder_receipt_gate(receipt: dict[str, Any]) -> bool:
    try:
        binding_count = int(receipt["shared_builder_binding_redirect_count"])
        universe_binding_count = int(
            receipt["shared_universe_binding_redirect_count"]
        )
        eligibility_binding_count = int(
            receipt["shared_eligibility_binding_redirect_count"]
        )
        original_universe_calls = int(
            receipt["original_universe_builder_call_count"]
        )
        original_eligibility_calls = int(
            receipt["original_eligibility_builder_call_count"]
        )
        original_total_calls = int(receipt["original_shared_builder_call_count"])
        before = receipt["shared_builder_source_identity_before"]
        after = receipt["shared_builder_source_identity_after"]
        bindings = receipt["shared_builder_redirect_bindings"]
        return (
            receipt.get("nested_shared_builder_guard_enabled") is True
            and receipt.get("original_shared_builder_guard_installed") is True
            and receipt.get("shared_builder_source_identity_pass") is True
            and receipt.get("shared_builder_required_binding_coverage_pass") is True
            and receipt.get("shared_builder_required_bindings")
            == list(REQUIRED_SHARED_BUILDER_BINDINGS)
            and universe_binding_count >= 3
            and eligibility_binding_count >= 3
            and binding_count
            == universe_binding_count + eligibility_binding_count
            and isinstance(bindings, list)
            and len(bindings) == binding_count
            and int(receipt.get("shared_universe_redirect_call_count", 0)) >= 1
            and int(receipt.get("shared_eligibility_redirect_call_count", 0)) >= 1
            and original_universe_calls == 0
            and original_eligibility_calls == 0
            and original_total_calls
            == original_universe_calls + original_eligibility_calls
            and int(receipt.get("dynamic_binding_restore_count", -1)) >= 0
            and _valid_shared_source_identity(before)
            and before == after
        )
    except (KeyError, TypeError, ValueError):
        return False


def _validate_completed_job(
    campaign_dir: Path,
    job: pd.Series,
    campaign_contract: str,
) -> bool:
    if _campaign_reuse_forbidden(campaign_dir):
        return False
    job_id = str(job["job_id"])
    directory = campaign_dir / "job_outputs" / job_id
    receipt_path = directory / "worker_receipt.json"
    if not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        expected_metadata = {
            "job_id": job_id,
            "job_type": str(job["job_type"]),
            "eval_date": str(job["eval_date"]),
            "next_eval_date": str(job["next_eval_date"]),
            "candidate_rank": int(job["candidate_rank"]),
        }
        if any(receipt.get(key) != value for key, value in expected_metadata.items()):
            return False
        if (
            receipt.get("campaign_id") != campaign_dir.name
            or receipt.get("campaign_path") != str(campaign_dir.resolve())
        ):
            return False
        if receipt.get("campaign_file_contract_sha256") != campaign_contract:
            return False
        if not receipt.get("input_identity_pass"):
            return False
        execution_contract = receipt.get("execution_file_contract_sha256", "")
        if len(execution_contract) != 64:
            return False
        if receipt.get("official_overrides_source") != "campaign_snapshot":
            return False
        overrides_path = campaign_dir / OFFICIAL_OVERRIDES_FILENAME
        if (
            not overrides_path.is_file()
            or receipt.get("official_overrides_sha256") != _sha256(overrides_path)
        ):
            return False
        universe_path = campaign_dir / OFFICIAL_PRODUCT_UNIVERSE_FILENAME
        if (
            not universe_path.is_file()
            or receipt.get("product_universe_sha256") != _sha256(universe_path)
        ):
            return False
        profile_overrides_path = (
            campaign_dir / STAGE819_PROFILE_OVERRIDES_FILENAME
        )
        profile_eligibility_path = (
            campaign_dir / STAGE819_PROFILE_ELIGIBILITY_FILENAME
        )
        if (
            receipt.get("stage819_profile_overrides_source")
            != "campaign_snapshot"
            or not profile_overrides_path.is_file()
            or receipt.get("stage819_profile_overrides_sha256")
            != _sha256(profile_overrides_path)
            or not profile_eligibility_path.is_file()
            or receipt.get("stage819_profile_eligibility_sha256")
            != _sha256(profile_eligibility_path)
            or not _shared_builder_receipt_gate(receipt)
        ):
            return False
        if not receipt.get("entry_candidate_boundary_gate", {}).get("passed"):
            return False
        runtime = receipt.get("runtime")
        if not isinstance(runtime, dict):
            return False
        environment = runtime.get("environment")
        if not isinstance(environment, dict):
            return False
        if (
            environment.get("STAGE015_CAMPAIGN_DIR")
            != str(campaign_dir.resolve())
            or environment.get("STAGE015_JOB_ID") != job_id
        ):
            return False
        if (
            receipt.get("tmpdir") != environment.get("TMPDIR")
            or receipt.get("mplconfigdir") != environment.get("MPLCONFIGDIR")
        ):
            return False
        tmpdir = Path(str(environment.get("TMPDIR", ""))).resolve()
        mplconfigdir = Path(str(environment.get("MPLCONFIGDIR", ""))).resolve()
        expected_job_tmp_root = (TMP_ROOT / campaign_dir.name / job_id).resolve()
        if (
            not tmpdir.is_relative_to(expected_job_tmp_root)
            or not mplconfigdir.is_relative_to(expected_job_tmp_root)
            or tmpdir.parent != mplconfigdir.parent
            or tmpdir.name != "tmp"
            or mplconfigdir.name != "mplconfig"
        ):
            return False
        if normalized_runtime_sha256(runtime) != receipt.get("normalized_runtime_sha256"):
            return False
        identity = json.loads(
            (campaign_dir / "campaign_identity.json").read_text(encoding="utf-8")
        )
        current_execution = _worker_execution_manifest(
            campaign_dir,
            job,
            identity,
        )
        if (
            receipt.get("execution_file_contract_sha256")
            != current_execution["file_contract_sha256"]
            or receipt.get("execution_unique_physical_file_count")
            != current_execution["unique_physical_file_count"]
        ):
            return False
        output_hashes = receipt.get("output_sha256", {})
        if set(output_hashes) != EXPECTED_JOB_OUTPUT_FILES:
            return False
        return all(
            (directory / name).is_file()
            and _sha256(directory / name) == expected
            for name, expected in output_hashes.items()
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _run_subprocess(campaign_dir: Path, job_id: str) -> None:
    run_id = f"run_{time.time_ns()}_{os.getpid()}_{threading.get_ident()}"
    environment = worker_environment(
        os.environ,
        TMP_ROOT / campaign_dir.name,
        job_id,
        run_id=run_id,
    )
    environment["STAGE015_CAMPAIGN_DIR"] = str(campaign_dir.resolve())
    Path(environment["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    Path(environment["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    log_path = campaign_dir / "logs" / f"{job_id}_{run_id}.log"
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
                    str(campaign_dir),
                ],
                cwd=RUNTIME_ROOT,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=MAX_JOB_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"stage015_worker_timeout:{job_id}:{MAX_JOB_SECONDS}") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"stage015_worker_failed:{job_id}:{completed.returncode}")


def _run_pending_jobs(
    campaign_dir: Path,
    selected_job_ids: tuple[str, ...] | None = None,
) -> None:
    _assert_campaign_reusable(campaign_dir)
    jobs = pd.read_csv(campaign_dir / "jobs.csv", dtype={"job_id": str})
    identity = json.loads(
        (campaign_dir / "campaign_identity.json").read_text(encoding="utf-8")
    )
    contract = identity["file_contract_sha256"]
    jobs_by_id = {
        str(row["job_id"]): row for _, row in jobs.iterrows()
    }
    completed_ids = {
        job_id
        for job_id in jobs["job_id"]
        if _validate_completed_job(
            campaign_dir,
            jobs_by_id[str(job_id)],
            contract,
        )
    }
    invalid_existing = [
        job_id
        for job_id in jobs["job_id"]
        if (campaign_dir / "job_outputs" / job_id).exists()
        and job_id not in completed_ids
    ]
    if invalid_existing:
        raise RuntimeError(f"invalid_completed_job_outputs:{invalid_existing[:3]}")
    selected = (
        set(jobs["job_id"].astype(str))
        if selected_job_ids is None
        else set(selected_job_ids)
    )
    unknown = selected - set(jobs["job_id"].astype(str))
    if unknown:
        raise RuntimeError(f"selected_jobs_unknown:{sorted(unknown)}")
    pending = [
        job_id
        for job_id in jobs["job_id"]
        if job_id in selected and job_id not in completed_ids
    ]
    progress = {
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "status": "running" if selected_job_ids is None else "smoke_running",
        "completed_jobs": len(completed_ids),
        "total_jobs": len(jobs),
        "campaign_file_contract_sha256": contract,
        "selected_job_count": len(selected),
    }
    _atomic_json(campaign_dir / "progress.json", progress)
    _atomic_json(BASE_OUT / "LATEST.json", progress)
    if not pending:
        return

    iterator = iter(pending)
    completed_count = len(completed_ids)
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    active: dict[Future[None], str] = {}
    try:
        for _ in range(min(MAX_WORKERS, len(pending))):
            job_id = next(iterator)
            active[executor.submit(_run_subprocess, campaign_dir, job_id)] = job_id
        while active:
            finished, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in finished:
                job_id = active.pop(future)
                future.result()
                if not _validate_completed_job(
                    campaign_dir, jobs_by_id[job_id], contract
                ):
                    raise RuntimeError(f"completed_job_validation_failed:{job_id}")
                completed_count += 1
                progress["completed_jobs"] = completed_count
                progress["last_completed_job"] = job_id
                _atomic_json(campaign_dir / "progress.json", progress)
                _atomic_json(BASE_OUT / "LATEST.json", progress)
                if completed_count % 10 == 0 or completed_count == len(jobs):
                    print(
                        json.dumps(
                            {
                                "campaign": campaign_dir.name,
                                "completed": completed_count,
                                "total": len(jobs),
                            },
                            separators=(",", ":"),
                        ),
                        flush=True,
                    )
                try:
                    next_job = next(iterator)
                except StopIteration:
                    continue
                active[
                    executor.submit(_run_subprocess, campaign_dir, next_job)
                ] = next_job
    except BaseException:
        progress["status"] = "failed"
        progress["completed_jobs"] = completed_count
        _atomic_json(campaign_dir / "progress.json", progress)
        _atomic_json(BASE_OUT / "LATEST.json", progress)
        for future in active:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)


def _read_label(directory: Path) -> dict[str, float]:
    payload = json.loads((directory / "label.json").read_text(encoding="utf-8"))
    return {key: float(value) for key, value in payload.items()}


def _validate_smoke(
    campaign_dir: Path,
    *,
    emit_progress: bool = True,
) -> dict[str, Any]:
    _assert_campaign_reusable(campaign_dir)
    jobs = pd.read_csv(campaign_dir / "jobs.csv", dtype={"job_id": str})
    jobs_by_id = {str(row["job_id"]): row for _, row in jobs.iterrows()}
    identity = json.loads(
        (campaign_dir / "campaign_identity.json").read_text(encoding="utf-8")
    )
    contract = identity["file_contract_sha256"]
    completed_gate = all(
        _validate_completed_job(
            campaign_dir,
            jobs_by_id[job_id],
            contract,
        )
        for job_id in SMOKE_JOB_IDS
    )
    receipts = {
        job_id: json.loads(
            (
                campaign_dir
                / "job_outputs"
                / job_id
                / "worker_receipt.json"
            ).read_text(encoding="utf-8")
        )
        for job_id in SMOKE_JOB_IDS
    }
    output_bindings = {
        job_id: {
            "worker_receipt_sha256": _sha256(
                campaign_dir / "job_outputs" / job_id / "worker_receipt.json"
            ),
            "output_sha256": receipts[job_id]["output_sha256"],
        }
        for job_id in SMOKE_JOB_IDS
    }
    a1 = campaign_dir / "job_outputs/20220429_R10"
    a2 = campaign_dir / "job_outputs/20220429_R10_A2"
    aa_files = EXPECTED_JOB_OUTPUT_FILES
    aa_file_gates = {
        name: _sha256(a1 / name) == _sha256(a2 / name)
        for name in sorted(aa_files)
    }
    aa_exact = all(aa_file_gates.values())

    active_receipts = [receipts["20220531_R10"], receipts["20220531_R12"]]
    active_predecision_gates = {
        name: len(
            {receipt["predecision_sha256"][name] for receipt in active_receipts}
        )
        == 1
        for name in PREDECISION_NAMES
    }
    active_predecision_exact = all(active_predecision_gates.values())
    boundary_nonempty = all(
        receipt["entry_candidate_boundary_gate"]["passed"]
        and receipt["entry_candidate_boundary_gate"]["target_row_count"] > 0
        and receipt["entry_candidate_boundary_gate"]["target_row_count"]
        == receipt["entry_candidate_boundary_gate"]["target_nonnull_signal_count"]
        for receipt in active_receipts
    )
    reconciliation_exact = all(
        max(abs(float(value)) for value in receipt["internal_reconciliation_errors"].values())
        <= 1e-9
        for receipt in receipts.values()
    )
    runtime_hashes = {
        receipt["normalized_runtime_sha256"] for receipt in receipts.values()
    }
    runtime_exact = len(runtime_hashes) == 1
    isolation_exact = (
        len({receipt["fresh_process_pid"] for receipt in receipts.values()}) == 4
        and len({receipt["tmpdir"] for receipt in receipts.values()}) == 4
        and len({receipt["mplconfigdir"] for receipt in receipts.values()}) == 4
    )
    timeout_and_identity = all(
        float(receipt["wall_seconds"]) <= MAX_JOB_SECONDS
        and receipt["input_identity_pass"]
        and receipt["campaign_file_contract_sha256"] == contract
        and len(receipt["execution_file_contract_sha256"]) == 64
        and receipt["stage819_profile_overrides_source"]
        == "campaign_snapshot"
        and _shared_builder_receipt_gate(receipt)
        for receipt in receipts.values()
    )
    active_label_identifiable = (
        _sha256(campaign_dir / "job_outputs/20220531_R10/label.json")
        != _sha256(campaign_dir / "job_outputs/20220531_R12/label.json")
    )
    gates = {
        "four_smoke_jobs_complete_and_fixed_outputs": completed_gate,
        "rank10_AA_outputs_exact": aa_exact,
        "active_month_predecision_payloads_exact": active_predecision_exact,
        "active_month_boundary_nonempty_and_complete": boundary_nonempty,
        "curve_combined_trades_reconciliation_exact": reconciliation_exact,
        "normalized_runtime_exact": runtime_exact,
        "pid_tmp_mpl_isolation_exact": isolation_exact,
        "timeout_and_execution_identity": timeout_and_identity,
        "active_challenger_label_identifiable": active_label_identifiable,
        "development_labels_not_published": not (
            campaign_dir / "development_labels.csv"
        ).exists(),
    }
    passed = all(gates.values())
    receipt = {
        "stage": "Stage015_smoke",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "campaign_id": campaign_dir.name,
        "decision": (
            "stage015_smoke_pass_allow_full_development_batch"
            if passed
            else "stage015_smoke_fail_stop_full_development_batch"
        ),
        "passed": passed,
        "job_ids": list(SMOKE_JOB_IDS),
        "campaign_file_contract_sha256": contract,
        "smoke_job_output_bindings": output_bindings,
        "gates": gates,
        "AA_file_gates": aa_file_gates,
        "active_predecision_gates": active_predecision_gates,
        "normalized_runtime_sha256": (
            next(iter(runtime_hashes)) if len(runtime_hashes) == 1 else None
        ),
        "subprocess_timeout_seconds": MAX_JOB_SECONDS,
        "runs_backtest": True,
        "trains_model": False,
        "publishes_training_labels": False,
        "sealed_holdout_label_count": 0,
        "order_api_called_count": 0,
        "ctp_connected": False,
    }
    _write_json(campaign_dir / "smoke_receipt.json", receipt)
    progress = {
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "status": "smoke_passed" if passed else "smoke_failed",
        "completed_jobs": len(SMOKE_JOB_IDS),
        "total_jobs": 355,
        "decision": receipt["decision"],
        "campaign_file_contract_sha256": contract,
    }
    _atomic_json(campaign_dir / "progress.json", progress)
    _atomic_json(BASE_OUT / "LATEST.json", progress)
    if emit_progress:
        print(
            json.dumps(progress, ensure_ascii=False, separators=(",", ":")),
            flush=True,
        )
    if not passed:
        raise RuntimeError(f"stage015_smoke_failed:{gates}")
    return receipt


def _aggregate_identity_after(
    campaign_dir: Path, identity_before: dict[str, Any]
) -> dict[str, Any]:
    stage004 = _load_stage004()
    live_cfg, _s513, _s827, s901 = stage004._load_production_modules()
    _assert_active_release(live_cfg)
    return _campaign_manifest(
        campaign_dir,
        s901=s901,
        frozen_runtime=identity_before["runtime"],
    )


def _assert_final_campaign_identity_before_publish(
    campaign_dir: Path, identity_before: dict[str, Any]
) -> dict[str, Any]:
    final_identity = _aggregate_identity_after(campaign_dir, identity_before)
    if final_identity != identity_before:
        raise RuntimeError("campaign_input_identity_drift_before_publish")
    _write_json(
        campaign_dir / "campaign_identity_before_publish.json",
        final_identity,
    )
    return final_identity


def _publish_development_label_outputs(
    campaign_dir: Path,
    identity_before: dict[str, Any],
    *,
    passed: bool,
    main: pd.DataFrame,
    reconciliation: pd.DataFrame,
) -> None:
    _assert_final_campaign_identity_before_publish(campaign_dir, identity_before)
    if not passed:
        return
    main.to_csv(
        campaign_dir / "development_labels.csv",
        index=False,
        lineterminator="\n",
    )
    reconciliation.to_csv(
        campaign_dir / "reconciliation.csv",
        index=False,
        lineterminator="\n",
    )


def _aggregate(campaign_dir: Path) -> dict[str, Any]:
    _assert_campaign_reusable(campaign_dir)
    jobs = pd.read_csv(campaign_dir / "jobs.csv", dtype={"job_id": str})
    identity_before = json.loads(
        (campaign_dir / "campaign_identity.json").read_text(encoding="utf-8")
    )
    contract = identity_before["file_contract_sha256"]
    identity_after = _aggregate_identity_after(campaign_dir, identity_before)
    campaign_identity_stable = identity_before == identity_after
    _write_json(campaign_dir / "campaign_identity_after.json", identity_after)
    if not all(
        _validate_completed_job(
            campaign_dir,
            row,
            contract,
        )
        for _, row in jobs.iterrows()
    ):
        raise RuntimeError("campaign_outputs_incomplete")

    label_rows: list[dict[str, Any]] = []
    receipts: dict[str, dict[str, Any]] = {}
    for job in jobs.itertuples(index=False):
        directory = campaign_dir / "job_outputs" / job.job_id
        label = _read_label(directory)
        label_rows.append(
            {
                "job_id": job.job_id,
                "job_type": job.job_type,
                "eval_date": job.eval_date,
                "next_eval_date": job.next_eval_date,
                "product_vt_symbol": job.product_vt_symbol,
                "candidate_rank": int(job.candidate_rank),
                **label,
            }
        )
        receipts[job.job_id] = json.loads(
            (directory / "worker_receipt.json").read_text(encoding="utf-8")
        )
    labels = pd.DataFrame(label_rows)
    main = labels[labels["job_type"].eq("main")].copy()
    reconciliation_rows: list[dict[str, Any]] = []
    for eval_date, month in main.groupby("eval_date", sort=True):
        baseline_row = month[month["candidate_rank"].eq(10)]
        if len(baseline_row) != 1:
            raise RuntimeError(f"baseline_label_shape:{eval_date}:{len(baseline_row)}")
        baseline = baseline_row.iloc[0].to_dict()
        for _, candidate in month.sort_values("candidate_rank").iterrows():
            pair = reconcile_label_pair(baseline, candidate.to_dict())
            target_curve = pd.read_csv(
                campaign_dir / "job_outputs" / candidate["job_id"] / "curve.csv"
            )
            target_combined = pd.read_csv(
                campaign_dir / "job_outputs" / candidate["job_id"] / "combined.csv"
            )
            target_trades = pd.read_csv(
                campaign_dir / "job_outputs" / candidate["job_id"] / "trades.csv"
            )
            curve_slippage = "slippage" if "slippage" in target_curve.columns else "total_slippage"
            curve_errors = {
                "target_curve_net_pnl_error": float(
                    pd.to_numeric(target_curve["net_pnl"], errors="raise").sum()
                )
                - float(candidate["future_net_pnl"]),
                "target_curve_slippage_error": float(
                    pd.to_numeric(target_curve[curve_slippage], errors="raise").sum()
                )
                - float(candidate["future_slippage"]),
                "target_curve_trade_count_error": float(
                    pd.to_numeric(target_curve["trade_count"], errors="raise").sum()
                )
                - float(candidate["future_trade_count"]),
                "target_combined_net_pnl_error": float(
                    pd.to_numeric(target_combined["net_pnl"], errors="raise").sum()
                )
                - float(candidate["future_net_pnl"]),
                "target_combined_slippage_error": float(
                    pd.to_numeric(target_combined["slippage"], errors="raise").sum()
                )
                - float(candidate["future_slippage"]),
                "target_combined_trade_count_error": float(
                    pd.to_numeric(target_combined["trade_count"], errors="raise").sum()
                )
                - float(candidate["future_trade_count"]),
                "target_trade_rows_error": float(len(target_trades))
                - float(candidate["future_trade_count"]),
            }
            reconciliation_rows.append(
                {
                    "job_id": candidate["job_id"],
                    "eval_date": eval_date,
                    "candidate_rank": int(candidate["candidate_rank"]),
                    **pair,
                    **curve_errors,
                }
            )
    reconciliation = pd.DataFrame(reconciliation_rows)
    error_columns = [name for name in reconciliation if name.endswith("_error")]
    reconciliation_pass = bool(
        reconciliation[error_columns].abs().max().max() <= 1e-9
        and reconciliation["base_equity_delta"].abs().max() <= 1e-9
    )

    pair_by_job = reconciliation.set_index("job_id")
    for column in (
        "return_delta",
        "drawdown_improvement",
        "net_pnl_delta",
        "slippage_delta",
        "trade_count_delta",
    ):
        main[column] = main["job_id"].map(pair_by_job[column])

    predecision_gates: dict[str, dict[str, Any]] = {}
    for eval_date, month_jobs in jobs.groupby("eval_date", sort=True):
        month_receipts = [receipts[job_id] for job_id in month_jobs["job_id"]]
        payload_gate = {
            name: len(
                {
                    receipt["predecision_sha256"][name]
                    for receipt in month_receipts
                }
            )
            == 1
            for name in PREDECISION_NAMES
        }
        predecision_gates[str(eval_date)] = {
            "passed": all(payload_gate.values()),
            "payloads": payload_gate,
        }
    predecision_pass = all(value["passed"] for value in predecision_gates.values())

    a2_gates: dict[str, dict[str, Any]] = {}
    for sentinel in labels[labels["job_type"].eq("A2_sentinel")].itertuples(index=False):
        baseline = labels[
            labels["job_type"].eq("main")
            & labels["eval_date"].eq(sentinel.eval_date)
            & labels["candidate_rank"].eq(10)
        ].iloc[0]
        left = campaign_dir / "job_outputs" / baseline["job_id"]
        right = campaign_dir / "job_outputs" / sentinel.job_id
        files = ["label.json"] + [f"{name}.csv" for name in PAYLOAD_NAMES]
        file_gates = {name: _sha256(left / name) == _sha256(right / name) for name in files}
        a2_gates[sentinel.job_id] = {
            "baseline_job_id": baseline["job_id"],
            "passed": all(file_gates.values()),
            "files": file_gates,
        }
    a2_pass = len(a2_gates) == 4 and all(value["passed"] for value in a2_gates.values())

    runtime_hashes = {
        receipt["normalized_runtime_sha256"] for receipt in receipts.values()
    }
    pids = {int(receipt["fresh_process_pid"]) for receipt in receipts.values()}
    tmpdirs = {receipt["tmpdir"] for receipt in receipts.values()}
    mpldirs = {receipt["mplconfigdir"] for receipt in receipts.values()}
    worker_identity_pass = all(
        receipt["input_identity_pass"]
        and not receipt["checkpoint_reused"]
        and not receipt["completed_result_reused"]
        and float(receipt["wall_seconds"]) <= MAX_JOB_SECONDS
        and receipt["campaign_file_contract_sha256"] == contract
        and receipt["stage819_profile_overrides_source"]
        == "campaign_snapshot"
        and _shared_builder_receipt_gate(receipt)
        for receipt in receipts.values()
    )
    boundary_semantics_pass = all(
        receipt["entry_candidate_boundary_gate"]["passed"]
        for receipt in receipts.values()
    )
    worker_isolation_pass = (
        len(pids) == len(jobs)
        and len(tmpdirs) == len(jobs)
        and len(mpldirs) == len(jobs)
        and len(runtime_hashes) == 1
    )
    observed_main_dates = tuple(sorted(main["eval_date"].astype(str).unique()))
    observed_next_by_date = {
        eval_date: tuple(sorted(month["next_eval_date"].astype(str).unique()))
        for eval_date, month in main.groupby("eval_date", sort=True)
    }
    expected_order = EXPECTED_DEVELOPMENT_DATES + EXPECTED_HOLDOUT_DATES
    expected_next_by_date = {
        eval_date: (expected_order[index + 1],)
        for index, eval_date in enumerate(EXPECTED_DEVELOPMENT_DATES)
    }
    job_date_contract_pass = (
        observed_main_dates == EXPECTED_DEVELOPMENT_DATES
        and observed_next_by_date == expected_next_by_date
    )
    holdout_label_count = int(
        labels["eval_date"].astype(str).isin(EXPECTED_HOLDOUT_DATES).sum()
    )
    expected_output_ids = set(jobs["job_id"].astype(str))
    observed_output_ids = {
        path.name
        for path in (campaign_dir / "job_outputs").iterdir()
        if path.is_dir()
    }
    holdout_absence_pass = (
        holdout_label_count == 0
        and observed_output_ids == expected_output_ids
        and not jobs["split"].eq("sealed_holdout").any()
    )
    gates = {
        "campaign_input_identity_stable": campaign_identity_stable,
        "all_355_cold_jobs_complete": len(receipts) == 355,
        "worker_identity_and_wall_time": worker_identity_pass,
        "worker_pid_tmp_runtime_isolation": worker_isolation_pass,
        "entry_candidate_boundary_semantics": boundary_semantics_pass,
        "four_A2_sentinels_exact": a2_pass,
        "monthly_predecision_payloads_exact": predecision_pass,
        "label_amount_reconciliation_exact": reconciliation_pass,
        "development_labels_351_rows": len(main) == 351,
        "development_and_next_eval_dates_exact": job_date_contract_pass,
        "sealed_holdout_labels_absent": holdout_absence_pass,
    }
    passed = all(gates.values())
    _publish_development_label_outputs(
        campaign_dir,
        identity_before,
        passed=passed,
        main=main,
        reconciliation=reconciliation,
    )
    decision_name = (
        "stage015_development_account_labels_complete_allow_frozen_training"
        if passed
        else "stage015_development_label_contract_failed_stop_training"
    )
    decision = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage015",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "campaign_id": campaign_dir.name,
        "decision": decision_name,
        "passed": passed,
        "gates": gates,
        "job_counts": {
            "main": int((jobs["job_type"] == "main").sum()),
            "A2_sentinel": int((jobs["job_type"] == "A2_sentinel").sum()),
            "total": int(len(jobs)),
        },
        "campaign_file_contract_sha256": contract,
        "normalized_runtime_sha256": next(iter(runtime_hashes)) if len(runtime_hashes) == 1 else None,
        "max_worker_wall_seconds": max(float(value["wall_seconds"]) for value in receipts.values()),
        "subprocess_timeout_seconds": MAX_JOB_SECONDS,
        "reconciliation_max_abs_error": float(
            reconciliation[error_columns].abs().max().max()
        ),
        "predecision_gates": predecision_gates,
        "A2_gates": a2_gates,
        "runs_backtest": True,
        "trains_model": False,
        "sealed_holdout_label_count": holdout_label_count,
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }
    _write_json(campaign_dir / "decision.json", decision)
    report = [
        "# Stage015 development账户边际标签批量生产",
        "",
        f"- 决策：`{decision_name}`",
        f"- 任务：351个主标签 + 4个A/A哨兵；全部完成：`{len(receipts) == 355}`。",
        f"- campaign输入身份始末一致：`{campaign_identity_stable}`；worker隔离与归一化runtime：`{worker_isolation_pass}`。",
        f"- 逐月决策前五类payload一致：`{predecision_pass}`；四个A/A哨兵逐文件一致：`{a2_pass}`。",
        f"- 金额/收益/滑点/交易数对账误差<=1e-9：`{reconciliation_pass}`。",
        "- 本阶段未训练模型，未生成sealed holdout标签，未连接CTP，未调用订单API。",
        "",
    ]
    (campaign_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    progress = {
        "campaign_id": campaign_dir.name,
        "campaign_path": str(campaign_dir.resolve()),
        "status": "complete" if passed else "failed",
        "completed_jobs": len(receipts),
        "total_jobs": len(jobs),
        "decision": decision_name,
        "campaign_file_contract_sha256": contract,
    }
    _atomic_json(campaign_dir / "progress.json", progress)
    _atomic_json(BASE_OUT / "LATEST.json", progress)
    print(json.dumps(progress, ensure_ascii=False, separators=(",", ":")), flush=True)
    return decision


def _resume_identity_gate(campaign_dir: Path) -> None:
    _assert_campaign_reusable(campaign_dir)
    identity = json.loads(
        (campaign_dir / "campaign_identity.json").read_text(encoding="utf-8")
    )
    stage004 = _load_stage004()
    live_cfg, _s513, _s827, s901 = stage004._load_production_modules()
    _assert_active_release(live_cfg)
    current_runtime = _runtime_contract()
    if current_runtime != identity["runtime"]:
        raise RuntimeError("campaign_runtime_identity_drift_before_resume")
    current = _campaign_manifest(
        campaign_dir,
        s901=s901,
        frozen_runtime=identity["runtime"],
    )
    if identity != current:
        raise RuntimeError("campaign_input_identity_drift_before_resume")


def _orchestrate(
    campaign_dir: Path | None,
    prepare_only: bool,
    smoke: bool,
) -> None:
    if prepare_only and smoke:
        raise RuntimeError("prepare_only_and_smoke_are_mutually_exclusive")
    orchestrator_tmp = TMP_ROOT / "orchestrator"
    (orchestrator_tmp / "mplconfig").mkdir(parents=True, exist_ok=True)
    (orchestrator_tmp / "tmp").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
    os.environ.setdefault("MPLCONFIGDIR", str((orchestrator_tmp / "mplconfig").resolve()))
    os.environ.setdefault("TMPDIR", str((orchestrator_tmp / "tmp").resolve()))
    if campaign_dir is None:
        BASE_OUT.mkdir(parents=True, exist_ok=True)
        with _exclusive_lock(BASE_OUT / ".create_campaign.lock"):
            target = _prepare_campaign()
    else:
        target = campaign_dir.resolve()
    _assert_campaign_reusable(target)
    with _exclusive_lock(target / "locks/orchestrator.lock"):
        _resume_identity_gate(target)
        if prepare_only:
            print(str(target), flush=True)
            return
        if smoke:
            _run_pending_jobs(target, SMOKE_JOB_IDS)
            _validate_smoke(target)
            return
        smoke_path = target / "smoke_receipt.json"
        if not smoke_path.is_file():
            raise RuntimeError("stage015_smoke_receipt_missing")
        smoke_receipt = _validate_smoke(target, emit_progress=False)
        if (
            not smoke_receipt.get("passed")
            or smoke_receipt.get("campaign_id") != target.name
            or tuple(smoke_receipt.get("job_ids", [])) != SMOKE_JOB_IDS
            or smoke_receipt.get("campaign_file_contract_sha256")
            != json.loads(
                (target / "campaign_identity.json").read_text(encoding="utf-8")
            )["file_contract_sha256"]
            or smoke_receipt.get("decision")
            != "stage015_smoke_pass_allow_full_development_batch"
        ):
            raise RuntimeError("stage015_smoke_gate_not_satisfied")
        _run_pending_jobs(target)
        _aggregate(target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker")
    parser.add_argument("--campaign-dir")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    campaign_dir = Path(args.campaign_dir).resolve() if args.campaign_dir else None
    if args.worker:
        if campaign_dir is None:
            raise RuntimeError("worker_campaign_dir_missing")
        _assert_campaign_reusable(campaign_dir)
        with _exclusive_lock(campaign_dir / f"locks/{args.worker}.lock"):
            _run_worker(args.worker, campaign_dir)
    else:
        _orchestrate(campaign_dir, args.prepare_only, args.smoke)


if __name__ == "__main__":
    main()

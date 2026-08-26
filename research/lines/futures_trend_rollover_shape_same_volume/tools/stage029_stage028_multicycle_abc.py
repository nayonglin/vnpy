from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import math
import os
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

import stage028_q_delayed_rollover_abc as s28


LINE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage029"
CHECKPOINT_DIR = PROJECT_DIR / ".tools" / "stage029_multicycle_checkpoints"
STAGE028_DIR = LINE_DIR / "artifacts" / "stage028"

DATA_START = pd.Timestamp("2018-01-01")
DATA_END = pd.Timestamp("2026-08-25")
START_MONTHS = (1, 6)
DURATIONS_YEARS = (1, 2, 3)
TERMINAL_TOLERANCE_DAYS = 7
CANDIDATE_LOGIC_COMMIT = "20635f4cb55b20c8ae0c8641a2caa656f988a2b3"
RUNNER_CONTRACT_VERSION = 1

SUMMARY_PATH = OUTPUT_DIR / "stage029_window_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage029_window_comparison.csv"
AGGREGATE_PATH = OUTPUT_DIR / "stage029_cycle_aggregate.csv"
CURVE_PATH = OUTPUT_DIR / "stage029_equity_curves.csv"
DECISION_PATH = OUTPUT_DIR / "stage029_decision.json"
REPORT_PATH = OUTPUT_DIR / "stage029_multicycle_report.md"
CHART_FILES = {
    "full_period": "stage029_full_period_equity_abc.png",
    "1y": "stage029_equity_curves_1y_abc.png",
    "2y": "stage029_equity_curves_2y_abc.png",
    "3y": "stage029_equity_curves_3y_abc.png",
    "aggregate": "stage029_cycle_aggregate_abc.png",
}

ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": "stage029_A_formal_q",
        "label": "A: 当前正式 Q（立即换月、旧主力复权历史）",
        "plot_label": "A Formal Q",
        "color": "#2563eb",
    },
    {
        "arm": "B",
        "profile": "stage029_B_stage027_target_only",
        "label": "B: Stage027（立即换月、新主力自身K线）",
        "plot_label": "B Stage027",
        "color": "#dc2626",
    },
    {
        "arm": "C",
        "profile": "stage029_C_stage028_delay_5td",
        "label": "C: Stage028（延迟5交易日、新主力自身K线）",
        "plot_label": "C Stage028 +5TD",
        "color": "#16a34a",
    },
)
COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_B", "A", "B"),
    ("A_vs_C", "A", "C"),
    ("B_vs_C", "B", "C"),
)
COHORTS: tuple[tuple[str, int | None], ...] = (
    ("combined", None),
    ("january", 1),
    ("june", 6),
)


def _build_windows() -> tuple[dict[str, Any], ...]:
    windows: list[dict[str, Any]] = [
        {
            "window_id": "full_2018_2026",
            "window_group": "full_period",
            "duration_years": 0,
            "start": DATA_START,
            "end": DATA_END,
            "complete": True,
            "terminal_near_complete": False,
        }
    ]
    for years in DURATIONS_YEARS:
        for year in range(DATA_START.year, DATA_END.year + 1):
            for month in START_MONTHS:
                start = pd.Timestamp(year=year, month=month, day=1)
                if start < DATA_START or start > DATA_END:
                    continue
                natural_end = (start + pd.DateOffset(years=years) - pd.Timedelta(days=1)).normalize()
                complete = natural_end <= DATA_END
                gap_days = int((natural_end - DATA_END).days)
                near_complete = not complete and 0 < gap_days <= TERMINAL_TOLERANCE_DAYS
                if not complete and not near_complete:
                    continue
                end = natural_end if complete else DATA_END
                windows.append(
                    {
                        "window_id": (
                            f"roll_{years}y_{start.strftime('%Y_%m')}"
                            + ("_near_complete" if near_complete else "")
                        ),
                        "window_group": f"rolling_{years}y",
                        "duration_years": years,
                        "start": start,
                        "end": end,
                        "complete": complete,
                        "terminal_near_complete": near_complete,
                    }
                )
    return tuple(windows)


WINDOWS = _build_windows()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_DIR, check=True, capture_output=True, text=True
    ).stdout.strip()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_contract_hash() -> str:
    paths = (
        Path(__file__),
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_portfolio_strategy.py",
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_official_live_config.py",
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_candidate_stage027_target_contract_history_config.py",
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_candidate_stage028_delayed_rollover_config.py",
        Path(s28.__file__),
    )
    digest = sha256()
    digest.update(str(RUNNER_CONTRACT_VERSION).encode())
    for path in paths:
        digest.update(str(path.relative_to(PROJECT_DIR)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _preflight() -> dict[str, Any]:
    identity = s28._assert_identity_and_scope()
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANDIDATE_LOGIC_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    if s28.override_diff("B", "C") != {"rollover_delay_trading_days": (None, 5)}:
        raise RuntimeError("stage029_candidate_scope_drift")
    database_path = PROJECT_DIR / ".vntrader" / "database.db"
    if not database_path.exists():
        raise RuntimeError(f"stage029_database_missing:{database_path}")
    return {
        **identity,
        "runner_head": _git("rev-parse", "HEAD"),
        "candidate_logic_commit": CANDIDATE_LOGIC_COMMIT,
        "database_path": str(database_path),
        "database_sha256": _file_sha256(database_path),
        "runtime_contract_sha256": _runtime_contract_hash(),
    }


def _window_common(window: dict[str, Any], arm: str) -> dict[str, Any]:
    start = pd.Timestamp(window["start"])
    end = pd.Timestamp(window["end"])
    start_month = start.strftime("%Y-%m")
    return {
        "window_id": str(window["window_id"]),
        "window_group": str(window["window_group"]),
        "duration_years": int(window["duration_years"]),
        "requested_start": str(start.date()),
        "requested_end": str(end.date()),
        "complete_window": int(bool(window["complete"])),
        "terminal_near_complete": int(bool(window["terminal_near_complete"])),
        "promotion_arm": arm,
        "window_name": str(window["window_id"]),
        "window_label": f"{start.date()} independent start to {end.date()}",
        "requested_start_month": start_month,
        "start_month": start_month,
        "start_year": int(start.year),
        "start_month_num": int(start.month),
    }


def _load_full_period_checkpoint() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(s28.SUMMARY_PATH)
    curve = pd.read_csv(s28.CURVE_PATH)
    expected_arms = {arm["arm"] for arm in ARMS}
    if set(summary["experiment_arm"].astype(str)) != expected_arms or len(summary) != len(ARMS):
        raise RuntimeError("stage029_stage028_full_summary_identity_mismatch")
    if set(curve["experiment_arm"].astype(str)) != expected_arms:
        raise RuntimeError("stage029_stage028_full_curve_identity_mismatch")
    s28._assert_full_period_coverage(summary)
    window = WINDOWS[0]
    summary_frames: list[pd.DataFrame] = []
    curve_frames: list[pd.DataFrame] = []
    for arm in ARMS:
        arm_name = arm["arm"]
        row = summary[summary["experiment_arm"].astype(str).eq(arm_name)].copy()
        arm_curve = curve[curve["experiment_arm"].astype(str).eq(arm_name)].copy()
        for key, value in _window_common(window, arm_name).items():
            row[key] = value
            arm_curve[key] = value
        summary_frames.append(row)
        curve_frames.append(arm_curve)
    return (
        pd.concat(summary_frames, ignore_index=True, sort=False),
        pd.concat(curve_frames, ignore_index=True, sort=False),
    )


def _run_window(
    metadata: dict[str, Any],
    window: dict[str, Any],
    arm: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    old_start, old_end = s28.START, s28.END
    runtime_arm = {
        **arm,
        "profile": f"stage029_{arm['arm']}_{window['window_id']}",
    }
    try:
        s28.START = pd.Timestamp(window["start"])
        s28.END = pd.Timestamp(window["end"])
        summary, curve, _frames = s28._run_arm(runtime_arm, metadata)
    finally:
        s28.START, s28.END = old_start, old_end
    common = _window_common(window, arm["arm"])
    for key, value in common.items():
        summary[key] = value
        curve[key] = value
    return summary, curve


def _checkpoint_contract(
    preflight: dict[str, Any], window: dict[str, Any], arm: dict[str, str]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "runtime_contract_sha256": preflight["runtime_contract_sha256"],
        "database_sha256": preflight["database_sha256"],
        "formal_manifest_sha256": preflight["formal_identity"]["manifest_sha256"],
        "candidate_logic_commit": CANDIDATE_LOGIC_COMMIT,
        "data_cutoff": str(DATA_END.date()),
        "window_id": str(window["window_id"]),
        "requested_start": str(pd.Timestamp(window["start"]).date()),
        "requested_end": str(pd.Timestamp(window["end"]).date()),
        "arm": arm["arm"],
    }


def _checkpoint_path(contract: dict[str, Any]) -> Path:
    key = sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()[:24]
    return CHECKPOINT_DIR / f"{contract['window_id']}__{contract['arm']}__{key}"


def _checkpoint_frames_valid(
    summary: pd.DataFrame,
    curve: pd.DataFrame,
    contract: dict[str, Any],
) -> bool:
    if len(summary) != 1 or curve.empty:
        return False
    if str(summary.iloc[0].get("window_id")) != contract["window_id"]:
        return False
    if str(summary.iloc[0].get("promotion_arm")) != contract["arm"]:
        return False
    if not curve["window_id"].astype(str).eq(contract["window_id"]).all():
        return False
    if not curve["promotion_arm"].astype(str).eq(contract["arm"]).all():
        return False
    critical = summary[
        [
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
            "account_survival_pass",
            "broker10_100_pass",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
        ]
    ].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(critical.to_numpy(dtype=float)).all():
        return False
    equity = pd.to_numeric(curve["account_equity"], errors="coerce")
    if not np.isfinite(equity.to_numpy(dtype=float)).all():
        return False
    actual_end = pd.Timestamp(summary.iloc[0]["analysis_end"]).normalize()
    return actual_end <= pd.Timestamp(contract["requested_end"]).normalize()


def _load_checkpoint(
    preflight: dict[str, Any], window: dict[str, Any], arm: dict[str, str]
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    contract = _checkpoint_contract(preflight, window, arm)
    directory = _checkpoint_path(contract)
    meta_path = directory / "meta.json"
    summary_path = directory / "summary.csv"
    curve_path = directory / "curve.csv"
    if not (meta_path.exists() and summary_path.exists() and curve_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("contract") != contract:
            return None
        if meta.get("summary_sha256") != _file_sha256(summary_path):
            return None
        if meta.get("curve_sha256") != _file_sha256(curve_path):
            return None
        summary = pd.read_csv(summary_path)
        curve = pd.read_csv(curve_path)
        if not _checkpoint_frames_valid(summary, curve, contract):
            return None
        return summary, curve
    except Exception:
        return None


def _write_checkpoint(
    preflight: dict[str, Any],
    window: dict[str, Any],
    arm: dict[str, str],
    summary: pd.DataFrame,
    curve: pd.DataFrame,
) -> None:
    contract = _checkpoint_contract(preflight, window, arm)
    directory = _checkpoint_path(contract)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage029-checkpoint-", dir=CHECKPOINT_DIR))
    try:
        summary_path = temporary / "summary.csv"
        curve_path = temporary / "curve.csv"
        summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
        curve.to_csv(curve_path, index=False, encoding="utf-8-sig")
        meta = {
            "contract": contract,
            "summary_sha256": _file_sha256(summary_path),
            "curve_sha256": _file_sha256(curve_path),
        }
        (temporary / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if directory.exists():
            shutil.rmtree(directory)
        os.replace(temporary, directory)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def _validate_outputs(summary: pd.DataFrame, curves: pd.DataFrame) -> None:
    expected_pairs = {
        (str(window["window_id"]), str(arm["arm"]))
        for window in WINDOWS
        for arm in ARMS
    }
    actual_pairs = set(
        zip(summary["window_id"].astype(str), summary["promotion_arm"].astype(str), strict=False)
    )
    if len(summary) != len(expected_pairs) or actual_pairs != expected_pairs:
        raise RuntimeError("stage029_window_arm_identity_mismatch")
    curve_pairs = set(
        zip(curves["window_id"].astype(str), curves["promotion_arm"].astype(str), strict=False)
    )
    if curve_pairs != expected_pairs:
        raise RuntimeError("stage029_curve_window_arm_identity_mismatch")
    critical = summary[
        [
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
            "account_survival_pass",
            "broker10_100_pass",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
        ]
    ].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(critical.to_numpy(dtype=float)).all():
        raise RuntimeError("stage029_critical_metric_missing")
    equity = pd.to_numeric(curves["account_equity"], errors="coerce")
    if curves.empty or not np.isfinite(equity.to_numpy(dtype=float)).all():
        raise RuntimeError("stage029_curve_missing")
    for years in DURATIONS_YEARS:
        rows = summary[
            summary["duration_years"].eq(years)
            & summary["complete_window"].eq(1)
        ]
        if set(rows["start_month_num"].astype(int)) != {1, 6}:
            raise RuntimeError(f"stage029_missing_january_or_june:{years}")


def _verify_full_identity(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    source_summary = pd.read_csv(s28.SUMMARY_PATH).set_index("experiment_arm")
    source_curve = pd.read_csv(s28.CURVE_PATH)
    full = summary[summary["window_id"].astype(str).eq("full_2018_2026")].set_index("promotion_arm")
    metrics = [
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
    for arm in ("A", "B", "C"):
        if not np.allclose(
            full.loc[arm, metrics].to_numpy(dtype="float64"),
            source_summary.loc[arm, metrics].to_numpy(dtype="float64"),
            rtol=0.0,
            atol=1e-9,
        ):
            raise RuntimeError(f"stage029_full_summary_drift:{arm}")
        left = curve[
            curve["window_id"].astype(str).eq("full_2018_2026")
            & curve["promotion_arm"].astype(str).eq(arm)
        ].sort_values("date")
        right = source_curve[source_curve["experiment_arm"].astype(str).eq(arm)].sort_values("date")
        left_dates = pd.to_datetime(left["date"], errors="raise", format="mixed").dt.strftime("%Y-%m-%d")
        right_dates = pd.to_datetime(right["date"], errors="raise", format="mixed").dt.strftime("%Y-%m-%d")
        if left_dates.tolist() != right_dates.tolist():
            raise RuntimeError(f"stage029_full_curve_date_drift:{arm}")
        if not np.allclose(
            pd.to_numeric(left["account_equity"]).to_numpy(dtype="float64"),
            pd.to_numeric(right["account_equity"]).to_numpy(dtype="float64"),
            rtol=0.0,
            atol=1e-9,
        ):
            raise RuntimeError(f"stage029_full_curve_equity_drift:{arm}")


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_id, group in summary.groupby("window_id", sort=False):
        by_arm = group.set_index("promotion_arm")
        for comparison_name, left_arm, right_arm in COMPARISONS:
            left = by_arm.loc[left_arm]
            right = by_arm.loc[right_arm]
            left_slippage = float(left["total_slippage"])
            right_slippage = float(right["total_slippage"])
            rows.append(
                {
                    "window_id": window_id,
                    "window_group": str(right["window_group"]),
                    "duration_years": int(right["duration_years"]),
                    "requested_start": str(right["requested_start"]),
                    "requested_end": str(right["requested_end"]),
                    "start_month_num": int(right["start_month_num"]),
                    "complete_window": int(right["complete_window"]),
                    "terminal_near_complete": int(right["terminal_near_complete"]),
                    "comparison": comparison_name,
                    "left_arm": left_arm,
                    "right_arm": right_arm,
                    "left_end_equity": float(left["end_equity"]),
                    "right_end_equity": float(right["end_equity"]),
                    "left_return_pct": float(left["total_return_pct"]),
                    "right_return_pct": float(right["total_return_pct"]),
                    "delta_return_pct": float(right["total_return_pct"] - left["total_return_pct"]),
                    "left_max_dd_pct": float(left["max_dd_pct"]),
                    "right_max_dd_pct": float(right["max_dd_pct"]),
                    "dd_worsening_pp": max(0.0, float(left["max_dd_pct"] - right["max_dd_pct"])),
                    "left_sharpe": float(left["sharpe"]),
                    "right_sharpe": float(right["sharpe"]),
                    "delta_sharpe": float(right["sharpe"] - left["sharpe"]),
                    "left_slippage": left_slippage,
                    "right_slippage": right_slippage,
                    "slippage_ratio": right_slippage / left_slippage if left_slippage > 0 else np.nan,
                    "left_trades": int(left["total_trade_count"]),
                    "right_trades": int(right["total_trade_count"]),
                    "left_win_rate_pct": float(left["nonzero_daily_win_rate_pct"]),
                    "right_win_rate_pct": float(right["nonzero_daily_win_rate_pct"]),
                    "left_survival_pass": int(left["account_survival_pass"]),
                    "right_survival_pass": int(right["account_survival_pass"]),
                    "left_broker100_pass": int(left["broker10_100_pass"]),
                    "right_broker100_pass": int(right["broker10_100_pass"]),
                    "left_broker10_peak_pct": float(left["max_broker10_margin_to_equity_pct"]),
                    "right_broker10_peak_pct": float(right["max_broker10_margin_to_equity_pct"]),
                    "left_days_over_100pct": int(left["days_over_100pct"]),
                    "right_days_over_100pct": int(right["days_over_100pct"]),
                    "return_win": int(float(right["total_return_pct"]) >= float(left["total_return_pct"])),
                    "left_positive": int(float(left["total_return_pct"]) > 0.0),
                    "right_positive": int(float(right["total_return_pct"]) > 0.0),
                    "dd_noninferior_2pp": int(
                        max(0.0, float(left["max_dd_pct"] - right["max_dd_pct"])) <= 2.0
                    ),
                    "sharpe_noninferior_005": int(
                        float(right["sharpe"]) >= float(left["sharpe"]) - 0.05
                    ),
                    "left_dd50_fail": int(float(left["max_dd_pct"]) < -50.0),
                    "right_dd50_fail": int(float(right["max_dd_pct"]) < -50.0),
                }
            )
    return pd.DataFrame(rows)


def _aggregate_row(
    comparison_name: str, years: int, cohort: str, group: pd.DataFrame
) -> dict[str, Any]:
    left_slippage = float(group["left_slippage"].sum())
    right_slippage = float(group["right_slippage"].sum())
    return {
        "comparison": comparison_name,
        "duration_years": years,
        "start_cohort": cohort,
        "window_count": int(len(group)),
        "return_win_count": int(group["return_win"].sum()),
        "return_win_rate_pct": float(group["return_win"].mean() * 100.0),
        "median_return_delta_pct": float(group["delta_return_pct"].median()),
        "left_positive_count": int(group["left_positive"].sum()),
        "right_positive_count": int(group["right_positive"].sum()),
        "left_worst_return_pct": float(group["left_return_pct"].min()),
        "right_worst_return_pct": float(group["right_return_pct"].min()),
        "dd_noninferior_2pp_count": int(group["dd_noninferior_2pp"].sum()),
        "dd_noninferior_2pp_rate_pct": float(group["dd_noninferior_2pp"].mean() * 100.0),
        "left_dd50_fail_count": int(group["left_dd50_fail"].sum()),
        "right_dd50_fail_count": int(group["right_dd50_fail"].sum()),
        "sharpe_noninferior_005_count": int(group["sharpe_noninferior_005"].sum()),
        "sharpe_noninferior_005_rate_pct": float(group["sharpe_noninferior_005"].mean() * 100.0),
        "left_slippage": left_slippage,
        "right_slippage": right_slippage,
        "slippage_ratio": right_slippage / left_slippage if left_slippage > 0 else np.nan,
        "left_trades": int(group["left_trades"].sum()),
        "right_trades": int(group["right_trades"].sum()),
        "all_right_survival": int(group["right_survival_pass"].eq(1).all()),
        "left_broker100_fail_count": int(group["left_broker100_pass"].eq(0).sum()),
        "right_broker100_fail_count": int(group["right_broker100_pass"].eq(0).sum()),
    }


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    complete = comparison[
        comparison["complete_window"].eq(1)
        & comparison["duration_years"].isin(DURATIONS_YEARS)
    ]
    for comparison_name, _, _ in COMPARISONS:
        comparison_group = complete[complete["comparison"].eq(comparison_name)]
        for years in DURATIONS_YEARS:
            duration_group = comparison_group[comparison_group["duration_years"].eq(years)]
            for cohort, month in COHORTS:
                group = duration_group if month is None else duration_group[duration_group["start_month_num"].eq(month)]
                if group.empty:
                    raise RuntimeError(f"stage029_missing_complete_cohort:{comparison_name}:{years}:{cohort}")
                rows.append(_aggregate_row(comparison_name, years, cohort, group))
    return pd.DataFrame(rows)


def _full_period_gates(row: pd.Series) -> dict[str, bool]:
    return {
        "return_not_below_left": bool(row["right_return_pct"] >= row["left_return_pct"]),
        "dd_worsening_le_2pp": bool(row["dd_worsening_pp"] <= 2.0),
        "sharpe_noninferior_002": bool(row["delta_sharpe"] >= -0.02),
        "slippage_ratio_le_105pct": bool(row["slippage_ratio"] <= 1.05),
        "right_survival": bool(row["right_survival_pass"] == 1),
        "broker100_fail_count_not_above_left": bool(
            row["right_days_over_100pct"] <= row["left_days_over_100pct"]
        ),
    }


def _cycle_gates(row: dict[str, Any]) -> dict[str, bool]:
    return {
        "return_win_rate_ge_50pct": bool(row["return_win_rate_pct"] >= 50.0),
        "median_return_delta_nonnegative": bool(row["median_return_delta_pct"] >= 0.0),
        "dd_noninferior_2pp_rate_ge_80pct": bool(row["dd_noninferior_2pp_rate_pct"] >= 80.0),
        "dd50_fail_count_not_above_left": bool(
            row["right_dd50_fail_count"] <= row["left_dd50_fail_count"]
        ),
        "sharpe_noninferior_005_rate_ge_80pct": bool(
            row["sharpe_noninferior_005_rate_pct"] >= 80.0
        ),
        "slippage_ratio_le_105pct": bool(row["slippage_ratio"] <= 1.05),
        "all_right_survival": bool(row["all_right_survival"] == 1),
        "broker100_fail_count_not_above_left": bool(
            row["right_broker100_fail_count"] <= row["left_broker100_fail_count"]
        ),
    }


def _decision(
    preflight: dict[str, Any],
    comparison: pd.DataFrame,
    aggregate: pd.DataFrame,
    checkpoint_reused: int,
    checkpoint_generated: int,
) -> dict[str, Any]:
    full_rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        row = comparison[
            comparison["window_group"].eq("full_period")
            & comparison["comparison"].eq(comparison_name)
        ].iloc[0]
        gates = _full_period_gates(row)
        full_rows.append({"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))})
    cycle_rows: list[dict[str, Any]] = []
    for row in aggregate.to_dict(orient="records"):
        gates = _cycle_gates(row)
        cycle_rows.append(
            {
                "comparison": str(row["comparison"]),
                "duration_years": int(row["duration_years"]),
                "start_cohort": str(row["start_cohort"]),
                "gates": gates,
                "pass": bool(all(gates.values())),
            }
        )
    promotion_comparisons = {"A_vs_C", "B_vs_C"}
    relevant_full = [row for row in full_rows if row["comparison"] in promotion_comparisons]
    relevant_cycles = [row for row in cycle_rows if row["comparison"] in promotion_comparisons]
    full_pass = bool(all(row["pass"] for row in relevant_full))
    all_pass = bool(full_pass and all(row["pass"] for row in relevant_cycles))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage029",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "diagnostic_override_reason": "user_requested_multicycle_after_stage028_full_period_gate_failure",
        "identity": preflight,
        "gate_contract": {
            "data_start": str(DATA_START.date()),
            "data_end": str(DATA_END.date()),
            "start_schedule": "January and June",
            "durations_years": list(DURATIONS_YEARS),
            "complete_windows_only_for_decision": True,
            "terminal_near_complete_tolerance_days": TERMINAL_TOLERANCE_DAYS,
            "arms": {arm["arm"]: arm["label"] for arm in ARMS},
            "promotion_comparisons": sorted(promotion_comparisons),
            "full_period_failure_remains_binding": True,
        },
        "run_provenance": {
            "window_count": len(WINDOWS),
            "logical_arm_window_count": len(WINDOWS) * len(ARMS),
            "full_period_reused_and_verified_from_stage028": True,
            "new_independent_run_count": (len(WINDOWS) - 1) * len(ARMS),
            "checkpoint_reused_count": checkpoint_reused,
            "checkpoint_generated_count": checkpoint_generated,
        },
        "full_period_gates": full_rows,
        "cycle_gates": cycle_rows,
        "full_period_failure_is_binding": not full_pass,
        "stage028_all_multicycle_gates_pass": all_pass,
        "decision": (
            "stage028_multicycle_supports_formal_review"
            if all_pass
            else "confirm_stage028_not_promotable_after_multicycle"
        ),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _plot_full(curves: pd.DataFrame) -> bytes:
    frame = curves[curves["window_id"].eq("full_2018_2026")]
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        item = frame[frame["promotion_arm"].eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(item["date"]),
            pd.to_numeric(item["account_equity"]) / 10_000.0,
            color=arm["color"],
            lw=1.45,
            label=arm["plot_label"],
        )
    ax.set_title("Stage029 Full-Period Equity: Formal Q / Stage027 / Stage028 +5TD")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _plot_window_grid(curves: pd.DataFrame, comparison: pd.DataFrame, years: int) -> bytes:
    selected = comparison[
        comparison["duration_years"].eq(years)
        & comparison["comparison"].eq("A_vs_C")
    ].sort_values(["requested_start", "window_id"])
    rows = int(math.ceil(len(selected) / 4.0))
    fig, axes = plt.subplots(rows, 4, figsize=(18, 3.5 * rows), squeeze=False)
    for ax, (_, window) in zip(axes.ravel(), selected.iterrows(), strict=False):
        window_curves = curves[curves["window_id"].eq(window["window_id"])]
        for arm in ARMS:
            frame = window_curves[window_curves["promotion_arm"].eq(arm["arm"])].sort_values("date")
            ax.plot(
                pd.to_datetime(frame["date"]),
                pd.to_numeric(frame["account_equity"]) / 10_000.0,
                color=arm["color"],
                lw=1.0,
                label=arm["plot_label"],
            )
        suffix = " *" if int(window["terminal_near_complete"]) else ""
        ax.set_title(f"{window['requested_start']}  ({years}Y){suffix}", fontsize=10)
        ax.set_ylabel("Equity (10k CNY)")
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", rotation=25, labelsize=8)
    for ax in axes.ravel()[len(selected):]:
        ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(
        f"Stage029 {years}-Year Independent Equity Curves: January + June Starts",
        y=0.998,
        fontsize=15,
    )
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.975), ncol=3, fontsize=8)
    fig.text(0.995, 0.005, "* near-complete terminal window; observation only", ha="right", fontsize=8)
    fig.tight_layout(rect=[0, 0.015, 1, 0.935])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)
    return buffer.getvalue()


def _plot_aggregate(aggregate: pd.DataFrame) -> bytes:
    row_keys = [(comparison, cohort) for comparison, _, _ in COMPARISONS for cohort, _ in COHORTS]
    row_labels = [f"{comparison} {cohort}" for comparison, cohort in row_keys]
    metrics = [
        ("return_win_rate_pct", "Return Win Rate (%)", "YlGn", 0.0, 100.0),
        ("median_return_delta_pct", "Median Return Delta (pp)", "coolwarm", None, None),
        ("dd_noninferior_2pp_rate_pct", "DD Non-Inferior <=2pp (%)", "YlOrBr", 0.0, 100.0),
        ("slippage_ratio", "Aggregate Slippage Ratio (%)", "Reds", None, None),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(18, 16))
    for ax, (column, title, cmap, fixed_min, fixed_max) in zip(axes.ravel(), metrics, strict=True):
        values = np.empty((len(row_keys), len(DURATIONS_YEARS)), dtype=float)
        for row_index, (comparison_name, cohort) in enumerate(row_keys):
            for column_index, years in enumerate(DURATIONS_YEARS):
                row = aggregate[
                    aggregate["comparison"].eq(comparison_name)
                    & aggregate["start_cohort"].eq(cohort)
                    & aggregate["duration_years"].eq(years)
                ].iloc[0]
                value = float(row[column])
                values[row_index, column_index] = value * 100.0 if column == "slippage_ratio" else value
        vmin, vmax = fixed_min, fixed_max
        if column == "median_return_delta_pct":
            bound = max(float(np.abs(values).max()), 1.0)
            vmin, vmax = -bound, bound
        image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        for row_index in range(values.shape[0]):
            for column_index in range(values.shape[1]):
                ax.text(column_index, row_index, f"{values[row_index, column_index]:.1f}", ha="center", va="center", fontsize=8)
        ax.set_title(title)
        ax.set_xticks(range(len(DURATIONS_YEARS)), [f"{years}Y" for years in DURATIONS_YEARS])
        ax.set_yticks(range(len(row_labels)), row_labels, fontsize=8)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Stage029 Multi-Cycle A/B/C: Combined, January, June", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _charts(curve: pd.DataFrame, comparison: pd.DataFrame, aggregate: pd.DataFrame) -> dict[str, bytes]:
    return {
        CHART_FILES["full_period"]: _plot_full(curve),
        CHART_FILES["1y"]: _plot_window_grid(curve, comparison, 1),
        CHART_FILES["2y"]: _plot_window_grid(curve, comparison, 2),
        CHART_FILES["3y"]: _plot_window_grid(curve, comparison, 3),
        CHART_FILES["aggregate"]: _plot_aggregate(aggregate),
    }


def _report(summary: pd.DataFrame, comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> str:
    full = summary[summary["window_id"].eq("full_2018_2026")].set_index("promotion_arm")
    weakest = comparison[
        comparison["complete_window"].eq(1)
        & comparison["comparison"].isin({"A_vs_C", "B_vs_C"})
        & comparison["duration_years"].isin(DURATIONS_YEARS)
    ].sort_values("delta_return_pct").head(8)
    lines = [
        "# Stage029 Stage028 五日延迟换月多周期报告",
        "",
        f"结论：`{decision['decision']}`。完整周期失败保持约束，任何局部窗口优势都不能覆盖正式晋级门失败。",
        "",
        "## 全周期",
        "",
        "| Arm | 期末权益 | 总收益 | 最大回撤 | Sharpe | 滑点 | 交易数 | 胜率 | broker10峰值 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A", "B", "C"):
        row = full.loc[arm]
        lines.append(
            f"| {arm} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | {row['total_slippage']:,.0f} | "
            f"{int(row['total_trade_count'])} | {row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% |"
        )
    lines.extend(["", "## 1/2/3年聚合（combined / January / June）", ""])
    report_aggregate = aggregate[aggregate["comparison"].isin({"A_vs_C", "B_vs_C"})]
    lines.extend(
        [
            "| 对照 | 周期 | 起点 | 窗口 | 收益胜率 | 收益差中位 | DD非劣率 | Sharpe非劣率 | 滑点比 |",
            "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report_aggregate.itertuples(index=False):
        lines.append(
            f"| {row.comparison} | {row.duration_years}年 | {row.start_cohort} | {row.window_count} | "
            f"{row.return_win_rate_pct:.2f}% | {row.median_return_delta_pct:+.4f}pp | "
            f"{row.dd_noninferior_2pp_rate_pct:.2f}% | {row.sharpe_noninferior_005_rate_pct:.2f}% | "
            f"{row.slippage_ratio:.4f} |"
        )
    lines.extend(["", "## 最弱收益窗口", ""])
    for row in weakest.itertuples(index=False):
        lines.append(
            f"- `{row.comparison}` `{row.window_id}`：收益差 `{row.delta_return_pct:+.4f}pp`，"
            f"回撤恶化 `{row.dd_worsening_pp:.4f}pp`，Sharpe差 `{row.delta_sharpe:+.4f}`，"
            f"滑点比 `{row.slippage_ratio:.4f}`。"
        )
    lines.extend(
        [
            "",
            "## 五张固定图片",
            "",
            *[f"- `{filename}`" for filename in CHART_FILES.values()],
            "",
            "## 安全边界",
            "",
            "- 每个滚动窗口均为独立真引擎、独立15万资金与空仓冷启动；未切片全周期曲线。",
            "- 只读取正式AI池/产品池与研究数据库；未连接CTP，未调用下单或撤单API。",
            "- 正式物料、远端master和稳定生产均未改变。",
            "",
        ]
    )
    return "\n".join(lines)


def _publish_atomically(
    frames: dict[str, pd.DataFrame], decision: dict[str, Any], charts: dict[str, bytes], report: str
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage029.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage029.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False, encoding="utf-8-sig")
        (temporary / DECISION_PATH.name).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temporary / REPORT_PATH.name).write_text(report, encoding="utf-8")
        for filename, payload in charts.items():
            (temporary / filename).write_bytes(payload)
        if OUTPUT_DIR.exists():
            os.replace(OUTPUT_DIR, backup)
        try:
            os.replace(temporary, OUTPUT_DIR)
        except Exception:
            if backup.exists() and not OUTPUT_DIR.exists():
                os.replace(backup, OUTPUT_DIR)
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def main() -> None:
    preflight = _preflight()
    metadata = s28.s513._metadata()

    full_summary, full_curve = _load_full_period_checkpoint()
    if len(full_summary) != 3 or set(full_summary["promotion_arm"]) != {"A", "B", "C"}:
        raise RuntimeError("stage029_full_period_precheck_failed")
    _verify_full_identity(full_summary, full_curve)
    print("[stage029] full-period Stage028 checkpoint verified", flush=True)

    summaries = [full_summary]
    curves = [full_curve]
    reused_count = 0
    generated_count = 0
    rolling_windows = WINDOWS[1:]
    run_total = len(rolling_windows) * len(ARMS)
    run_index = 0
    for window in rolling_windows:
        for arm in ARMS:
            run_index += 1
            cached = _load_checkpoint(preflight, window, arm)
            if cached is not None:
                summary, curve = cached
                reused_count += 1
                print(
                    f"[stage029] {run_index}/{run_total} reuse {window['window_id']} arm={arm['arm']}",
                    flush=True,
                )
            else:
                print(
                    f"[stage029] {run_index}/{run_total} run {window['window_id']} arm={arm['arm']}",
                    flush=True,
                )
                summary, curve = _run_window(metadata, window, arm)
                _write_checkpoint(preflight, window, arm, summary, curve)
                generated_count += 1
            summaries.append(summary)
            curves.append(curve)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    window_order = {str(window["window_id"]): index for index, window in enumerate(WINDOWS)}
    arm_order = {str(arm["arm"]): index for index, arm in enumerate(ARMS)}
    summary["_window_order"] = summary["window_id"].astype(str).map(window_order)
    summary["_arm_order"] = summary["promotion_arm"].astype(str).map(arm_order)
    summary = summary.sort_values(["_window_order", "_arm_order"]).drop(columns=["_window_order", "_arm_order"])
    curve["_window_order"] = curve["window_id"].astype(str).map(window_order)
    curve["_arm_order"] = curve["promotion_arm"].astype(str).map(arm_order)
    curve = curve.sort_values(["_window_order", "_arm_order", "date"]).drop(columns=["_window_order", "_arm_order"])
    _validate_outputs(summary, curve)
    _verify_full_identity(summary, curve)
    comparison = _comparison(summary)
    aggregate = _aggregate(comparison)
    decision = _decision(preflight, comparison, aggregate, reused_count, generated_count)
    report = _report(summary, comparison, aggregate, decision)
    _publish_atomically(
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            AGGREGATE_PATH.name: aggregate,
            CURVE_PATH.name: curve,
        },
        decision,
        _charts(curve, comparison, aggregate),
        report,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

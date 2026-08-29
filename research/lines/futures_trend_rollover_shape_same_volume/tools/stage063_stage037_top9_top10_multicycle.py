from __future__ import annotations

from dataclasses import asdict, replace
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


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for directory in (TOOLS_DIR, PORTFOLIO_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import stage029_stage028_multicycle_abc as s29  # noqa: E402
import stage056_stage037_ai_top14_plus_fu_ac as s56  # noqa: E402
import stage059_stage056_vs_stage037_multicycle as s59  # noqa: E402
import stage061_ai_top10_to_top19_fullperiod as s61  # noqa: E402
import stage062_ai_top9_fullperiod as s62  # noqa: E402


LINE_ID = "futures_trend_rollover_shape_same_volume"
STAGE = "Stage063"
LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage063_stage037_top9_top10_multicycle"
CHECKPOINT_DIR = PROJECT_DIR / ".tools" / "stage063_stage037_top9_top10_multicycle_checkpoints"
INPUT_DIR = CHECKPOINT_DIR / "inputs"
STAGE059_DIR = s59.OUTPUT_DIR
STAGE062_DIR = s62.OUTPUT_DIR

DATA_START = pd.Timestamp("2018-01-01")
DATA_END = pd.Timestamp("2026-08-28")
START_MONTHS = (1, 6)
DURATIONS_YEARS = (1, 2, 3)
TERMINAL_TOLERANCE_DAYS = 7
RUNNER_CONTRACT_VERSION = 1

BASE_MASTER_COMMIT = s56.BASE_MASTER_COMMIT
BASE_RULESET_VERSION = s56.BASE_RULESET_VERSION
BASE_RELEASE_ID = "m0016_20260829T034012+0800_374df2d52e4f"
BASE_SOURCE_COMMIT = "374df2d52e4f17220c5e2d4cae76f50d45bec47d"
USER_OFFLINE_OVERRIDE = (
    "2026-08-29 user confirmed offline Stage037 CURRENT/master baseline despite "
    "stable production remaining Stage021-Q"
)

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm": "A",
        "source_arm": "REF",
        "top_n": 8,
        "profile": "stage063_A_formal_stage037_top8_plus_fu",
        "label": "A: 正式Stage037 Top8+fu（9品种）",
        "plot_label": "正式Stage037 Top8+fu",
        "color": "#111827",
        "linestyle": "--",
    },
    {
        "arm": "B",
        "source_arm": "T9",
        "top_n": 9,
        "profile": "stage063_B_stage062_top9_plus_fu",
        "label": "B: Top9+fu（10品种）",
        "plot_label": "Top9+fu",
        "color": "#dc2626",
        "linestyle": "-",
    },
    {
        "arm": "C",
        "source_arm": "T10",
        "top_n": 10,
        "profile": "stage063_C_stage061_top10_plus_fu",
        "label": "C: Top10+fu（11品种）",
        "plot_label": "Top10+fu",
        "color": "#2563eb",
        "linestyle": "-",
    },
)
COMPARISONS = (
    ("A_vs_B", "A", "B"),
    ("A_vs_C", "A", "C"),
    ("B_vs_C", "B", "C"),
)
COHORTS = (("combined", None), ("january", 1), ("june", 6))
CHART_FILES = {
    "full_period": "stage063_full_period_equity_abc.png",
    "1y": "stage063_equity_curves_1y_abc.png",
    "2y": "stage063_equity_curves_2y_abc.png",
    "3y": "stage063_equity_curves_3y_abc.png",
    "aggregate": "stage063_cycle_aggregate_abc.png",
}
SUMMARY_NAME = "stage063_window_summary.csv"
COMPARISON_NAME = "stage063_window_comparison.csv"
AGGREGATE_NAME = "stage063_cycle_aggregate.csv"
CURVE_NAME = "stage063_equity_curves.csv"
DECISION_NAME = "stage063_decision.json"
REPORT_NAME = "stage063_multicycle_report.md"


def _build_windows() -> tuple[dict[str, Any], ...]:
    windows: list[dict[str, Any]] = [
        {
            "window_id": "full_2018_20260828",
            "window_group": "full_period",
            "duration_years": 0,
            "start": DATA_START,
            "end": DATA_END,
            "start_month_num": 1,
            "complete": True,
            "terminal_near_complete": False,
        }
    ]
    for years in DURATIONS_YEARS:
        for year in range(DATA_START.year, DATA_END.year + 1):
            for month in START_MONTHS:
                start = pd.Timestamp(year=year, month=month, day=1)
                end = (start + pd.DateOffset(years=years) - pd.Timedelta(days=1)).normalize()
                if start >= DATA_START and end <= DATA_END:
                    windows.append(
                        {
                            "window_id": f"roll_{years}y_{start.strftime('%Y_%m')}",
                            "window_group": f"rolling_{years}y",
                            "duration_years": years,
                            "start": start,
                            "end": end,
                            "start_month_num": month,
                            "complete": True,
                            "terminal_near_complete": False,
                        }
                    )
    return tuple(windows)


WINDOWS = _build_windows()


def _configure_shared_contract() -> None:
    s29.WINDOWS = WINDOWS
    s29.ARMS = ARMS
    s29.COMPARISONS = COMPARISONS
    s29.COHORTS = COHORTS
    s29.DURATIONS_YEARS = DURATIONS_YEARS
    s29.TERMINAL_TOLERANCE_DAYS = TERMINAL_TOLERANCE_DAYS


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


def _assert_offline_identity_contract(
    checkout_identity: dict[str, Any],
    production_identity: dict[str, Any],
    remote_master: str,
) -> dict[str, Any]:
    expected = {
        "strategy_version": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        "ruleset_version": BASE_RULESET_VERSION,
        "material_release_id": BASE_RELEASE_ID,
        "source_commit": BASE_SOURCE_COMMIT,
    }
    actual = {key: checkout_identity.get(key) for key in expected}
    if actual != expected or remote_master != BASE_MASTER_COMMIT:
        raise RuntimeError(
            "stage063_formal_identity_mismatch:"
            f"actual={actual}:expected={expected}:remote={remote_master}"
        )
    production_matches = all(
        production_identity.get(key) == value for key, value in expected.items()
    )
    return {
        "research_protocol": "user_authorized_offline_stage037_top9_top10_multicycle",
        "checkout_stage037_identity_pass": True,
        "production_identity_matches_stage037": bool(production_matches),
        "user_authorized_offline_identity_override": bool(not production_matches),
        "user_authorized_offline_identity_override_reason": USER_OFFLINE_OVERRIDE,
        "formal_production_ac_compliant": bool(production_matches),
        "promotion_permitted": False,
    }


def _candidate_overrides(arm: str, eligibility_path: Path) -> dict[str, Any]:
    if arm == "B":
        return s62.candidate_cfg.build_candidate_overrides(eligibility_path)
    if arm == "C":
        return s61.candidate_cfg.build_candidate_overrides(10, eligibility_path)
    raise ValueError(f"stage063_candidate_arm_invalid:{arm}")


def _write_canonical_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def _prepare_eligibility_paths() -> dict[str, Path]:
    top9_source = STAGE062_DIR / s62.ELIGIBILITY_NAME
    top10_source = s61.OUTPUT_DIR / s61.ELIGIBILITY_NAME
    top9 = pd.read_csv(top9_source)
    all_topn = pd.read_csv(top10_source)
    top10 = all_topn[pd.to_numeric(all_topn["requested_top_n"]).eq(10)].copy()
    if len(top9) != 568 or len(top10) != 623:
        raise RuntimeError(
            f"stage063_eligibility_count_drift:top9={len(top9)}:top10={len(top10)}"
        )
    paths = {
        "B": INPUT_DIR / "stage063_top9_eligibility.csv",
        "C": INPUT_DIR / "stage063_top10_eligibility.csv",
    }
    _write_canonical_csv(top9, paths["B"])
    _write_canonical_csv(top10, paths["C"])
    return paths


def _runtime_contract_hash(eligibility_paths: dict[str, Path]) -> str:
    digest = sha256(str(RUNNER_CONTRACT_VERSION).encode())
    for path in (
        Path(__file__),
        Path(s29.__file__),
        Path(s56.__file__),
        Path(s61.candidate_cfg.__file__),
        Path(s62.candidate_cfg.__file__),
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_portfolio_strategy.py",
        STAGE059_DIR / s59.DECISION_NAME,
        STAGE062_DIR / s62.DECISION_NAME,
        eligibility_paths["B"],
        eligibility_paths["C"],
    ):
        digest.update(str(path.resolve()).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _preflight() -> tuple[dict[str, Any], dict[str, Path]]:
    eligibility_paths = _prepare_eligibility_paths()
    checkout = asdict(s56.assert_official_checkout_matches_active_material(PROJECT_DIR))
    production = asdict(s56.assert_official_checkout_matches_active_material(s56.PRODUCTION_ROOT))
    remote_master = _git("rev-parse", "origin/master")
    evidence = _assert_offline_identity_contract(checkout, production, remote_master)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_MASTER_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    for arm, path in eligibility_paths.items():
        diff = {
            key
            for key, values in (
                s62.candidate_cfg.override_diff(path).items()
                if arm == "B"
                else s61.candidate_cfg.override_diff(10, path).items()
            )
            if values[0] != values[1]
        }
        if diff != {"ai_product_pool_eligibility_path", "ai_product_pool_strategy"}:
            raise RuntimeError(f"stage063_candidate_scope_drift:{arm}:{sorted(diff)}")
    return (
        {
            **evidence,
            "checkout_identity": checkout,
            "production_identity": production,
            "checkout_head": _git("rev-parse", "HEAD"),
            "production_head": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=s56.PRODUCTION_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "remote_master": remote_master,
            "database_path": str(s56.DATABASE_PATH.resolve()),
            "database_sha256": _file_sha256(s56.DATABASE_PATH),
            "stage059_decision_sha256": _file_sha256(STAGE059_DIR / s59.DECISION_NAME),
            "stage062_decision_sha256": _file_sha256(STAGE062_DIR / s62.DECISION_NAME),
            "eligibility_sha256": {
                arm: _file_sha256(path) for arm, path in eligibility_paths.items()
            },
            "runtime_contract_sha256": _runtime_contract_hash(eligibility_paths),
        },
        eligibility_paths,
    )


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
        "window_label": f"{start.date()} independent start to {end.date()}",
        "requested_start_month": start.strftime("%Y-%m"),
        "start_month": start.strftime("%Y-%m"),
        "start_year": int(start.year),
        "start_month_num": int(start.month),
    }


def _relabel(frame: pd.DataFrame, arm: dict[str, Any]) -> pd.DataFrame:
    result = frame.copy()
    result["source_experiment_arm"] = result["experiment_arm"].astype(str)
    result["experiment_arm"] = arm["arm"]
    result["arm"] = arm["arm"]
    result["profile"] = arm["profile"]
    result["label"] = arm["label"]
    result["requested_top_n"] = arm["top_n"]
    return result


def _load_full_period() -> tuple[pd.DataFrame, pd.DataFrame]:
    source_summary = pd.read_csv(STAGE062_DIR / s62.SUMMARY_NAME)
    source_curve = pd.read_csv(STAGE062_DIR / s62.CURVE_NAME)
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    for arm in ARMS:
        summary = source_summary[
            source_summary["experiment_arm"].astype(str).eq(arm["source_arm"])
        ]
        curve = source_curve[
            source_curve["experiment_arm"].astype(str).eq(arm["source_arm"])
        ]
        if len(summary) != 1 or len(curve) != 2101:
            raise RuntimeError(f"stage063_full_period_source_drift:{arm['arm']}")
        summary = _relabel(summary, arm)
        curve = _relabel(curve, arm)
        for key, value in _window_common(WINDOWS[0], arm["arm"]).items():
            summary[key] = value
            curve[key] = value
        summaries.append(summary)
        curves.append(curve)
    return pd.concat(summaries, ignore_index=True), pd.concat(curves, ignore_index=True)


def _verify_full_identity(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    source_summary = pd.read_csv(STAGE062_DIR / s62.SUMMARY_NAME).set_index("experiment_arm")
    source_curve = pd.read_csv(STAGE062_DIR / s62.CURVE_NAME)
    full = summary[summary["window_group"].eq("full_period")].set_index("promotion_arm")
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
    for arm in ARMS:
        left = pd.to_numeric(full.loc[arm["arm"], metrics], errors="raise").to_numpy(float)
        right = pd.to_numeric(
            source_summary.loc[arm["source_arm"], metrics], errors="raise"
        ).to_numpy(float)
        if not np.allclose(left, right, atol=1e-9, rtol=0):
            raise RuntimeError(f"stage063_full_summary_drift:{arm['arm']}")
        left_curve = curve[
            curve["window_group"].eq("full_period")
            & curve["promotion_arm"].eq(arm["arm"])
        ].sort_values("date")
        right_curve = source_curve[
            source_curve["experiment_arm"].astype(str).eq(arm["source_arm"])
        ].sort_values("date")
        if pd.to_datetime(left_curve["date"]).tolist() != pd.to_datetime(
            right_curve["date"]
        ).tolist():
            raise RuntimeError(f"stage063_full_curve_date_drift:{arm['arm']}")
        if not np.allclose(
            pd.to_numeric(left_curve["account_equity"]),
            pd.to_numeric(right_curve["account_equity"]),
            atol=1e-9,
            rtol=0,
        ):
            raise RuntimeError(f"stage063_full_curve_equity_drift:{arm['arm']}")


def _load_reused_formal_rolling() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(STAGE059_DIR / s59.SUMMARY_NAME)
    curve = pd.read_csv(STAGE059_DIR / s59.CURVE_NAME)
    summary = summary[
        summary["promotion_arm"].astype(str).eq("A")
        & ~summary["window_group"].astype(str).eq("full_period")
    ].copy()
    curve = curve[
        curve["promotion_arm"].astype(str).eq("A")
        & ~curve["window_group"].astype(str).eq("full_period")
    ].copy()
    expected = {str(window["window_id"]) for window in WINDOWS[1:]}
    if len(summary) != 42 or set(summary["window_id"].astype(str)) != expected:
        raise RuntimeError("stage063_formal_rolling_summary_drift")
    for row in summary.to_dict(orient="records"):
        contract = {
            "window_id": str(row["window_id"]),
            "arm": "A",
            "requested_start": str(row["requested_start"]),
            "requested_end": str(row["requested_end"]),
        }
        pair_curve = curve[curve["window_id"].astype(str).eq(contract["window_id"])]
        if not s29._checkpoint_frames_valid(pd.DataFrame([row]), pair_curve, contract):
            raise RuntimeError(f"stage063_formal_rolling_curve_drift:{contract['window_id']}")
    return summary, curve


def _run_window(
    metadata: dict[str, Any],
    window: dict[str, Any],
    arm: dict[str, Any],
    eligibility_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    original_builder = s56.s28.s901.build_official_live_strategy_overrides
    try:
        s56.s28.s901.build_official_live_strategy_overrides = lambda: _candidate_overrides(
            arm["arm"], eligibility_path
        )
        combined, _frames, live_spec = s56.s28.s901._run_live_c9(
            metadata, pd.Timestamp(window["start"]), pd.Timestamp(window["end"])
        )
    finally:
        s56.s28.s901.build_official_live_strategy_overrides = original_builder
    profile = f"stage063_{arm['arm']}_{window['window_id']}"
    capital = replace(live_spec.capital, variant=profile, label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=profile)
    summary, curve = s56.s28.s827._metric(
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
    return {
        "schema_version": 1,
        "runtime_contract_sha256": preflight["runtime_contract_sha256"],
        "database_sha256": preflight["database_sha256"],
        "candidate_eligibility_sha256": preflight["eligibility_sha256"][arm["arm"]],
        "base_master_commit": BASE_MASTER_COMMIT,
        "window_id": str(window["window_id"]),
        "requested_start": str(pd.Timestamp(window["start"]).date()),
        "requested_end": str(pd.Timestamp(window["end"]).date()),
        "arm": arm["arm"],
    }


def _checkpoint_path(contract: dict[str, Any]) -> Path:
    key = sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()[:24]
    return CHECKPOINT_DIR / f"{contract['window_id']}__{contract['arm']}__{key}"


def _load_checkpoint(
    preflight: dict[str, Any], window: dict[str, Any], arm: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    contract = _checkpoint_contract(preflight, window, arm)
    directory = _checkpoint_path(contract)
    meta_path = directory / "meta.json"
    summary_path = directory / "summary.csv"
    curve_path = directory / "curve.csv"
    if not all(path.exists() for path in (meta_path, summary_path, curve_path)):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        summary, curve = pd.read_csv(summary_path), pd.read_csv(curve_path)
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
    temporary = Path(tempfile.mkdtemp(prefix=".stage063-checkpoint-", dir=CHECKPOINT_DIR))
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


def _cycle_gates(row: dict[str, Any]) -> dict[str, bool]:
    gates = s29._cycle_gates(row)
    gates["aggregate_slippage_le_105pct"] = gates.pop("slippage_ratio_le_105pct")
    return gates


def _decision(
    preflight: dict[str, Any],
    comparison: pd.DataFrame,
    aggregate: pd.DataFrame,
    checkpoint_reused: int,
    checkpoint_generated: int,
) -> dict[str, Any]:
    full_rows: list[dict[str, Any]] = []
    cycle_rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        full = comparison[
            comparison["window_group"].eq("full_period")
            & comparison["comparison"].eq(comparison_name)
        ].iloc[0]
        gates = s29._full_period_gates(full)
        full_rows.append(
            {"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))}
        )
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
    candidate_pass: dict[str, bool] = {}
    for arm, comparison_name in (("B", "A_vs_B"), ("C", "A_vs_C")):
        candidate_pass[arm] = bool(
            next(row["pass"] for row in full_rows if row["comparison"] == comparison_name)
            and all(
                row["pass"] for row in cycle_rows if row["comparison"] == comparison_name
            )
        )
    any_pass = any(candidate_pass.values())
    return {
        "line_id": LINE_ID,
        "stage": STAGE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": preflight,
        "gate_contract": {
            "data_start": str(DATA_START.date()),
            "data_end": str(DATA_END.date()),
            "start_schedule": "January and June independent cold starts",
            "durations_years": list(DURATIONS_YEARS),
            "complete_windows_only": True,
            "arms": {arm["arm"]: arm["label"] for arm in ARMS},
            "full_period": "return>=A, DD worsening<=2pp, Sharpe delta>=-0.02, slippage<=105%, survival and broker100 non-worse",
            "cycle": "return wins>=50%, median delta>=0, DD and Sharpe noninferior>=80%, aggregate slippage<=105%, survival and broker100 non-worse",
        },
        "run_provenance": {
            "window_count": len(WINDOWS),
            "logical_arm_window_count": len(WINDOWS) * len(ARMS),
            "full_period_reused_and_verified_from_stage062": True,
            "formal_rolling_reused_and_verified_from_stage059": True,
            "published_reuse_count": 45,
            "new_candidate_run_count": (len(WINDOWS) - 1) * 2,
            "checkpoint_reused_count": checkpoint_reused,
            "checkpoint_generated_count": checkpoint_generated,
        },
        "full_period_gates": full_rows,
        "cycle_gates": cycle_rows,
        "candidate_all_multicycle_gates_pass": candidate_pass,
        "any_candidate_all_multicycle_gates_pass": any_pass,
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
        "promote_to_official": False,
        "decision": (
            "offline_multicycle_evidence_only_identity_override_no_promotion"
            if any_pass
            else "offline_top9_top10_multicycle_has_hard_fail_keep_stage037"
        ),
        "overfitting_judgment": "高：Top9/Top10来自已观察Top10-Top19响应后的后验边界研究；本阶段固定窗口且不再调参。",
        "continued_value_judgment": "有一次性诊断价值：检验Top9/Top10全周期表现是否跨1月与6月冷启动稳定；失败后停止TopN救参。",
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _plot_full(curves: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        item = curves[
            curves["window_group"].eq("full_period")
            & curves["promotion_arm"].eq(arm["arm"])
        ].sort_values("date")
        ax.plot(
            pd.to_datetime(item["date"]),
            pd.to_numeric(item["account_equity"]) / 10_000,
            color=arm["color"],
            linestyle=arm["linestyle"],
            lw=2.2 if arm["arm"] != "A" else 1.8,
            label=arm["plot_label"],
        )
    ax.set(
        title="OFFLINE RESEARCH — Stage063 Full Period: Formal vs Top9 vs Top10",
        ylabel="Equity (10k CNY)",
    )
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _plot_grid(curves: pd.DataFrame, comparison: pd.DataFrame, years: int) -> bytes:
    selected = (
        comparison[
            comparison["duration_years"].eq(years)
            & comparison["comparison"].eq("A_vs_C")
        ]
        .sort_values("requested_start")
        .drop_duplicates("window_id")
    )
    rows = math.ceil(len(selected) / 4)
    fig, axes = plt.subplots(rows, 4, figsize=(18, 3.5 * rows), squeeze=False)
    for ax, (_, window) in zip(axes.ravel(), selected.iterrows(), strict=False):
        data = curves[curves["window_id"].eq(window["window_id"])]
        for arm in ARMS:
            item = data[data["promotion_arm"].eq(arm["arm"])].sort_values("date")
            ax.plot(
                pd.to_datetime(item["date"]),
                pd.to_numeric(item["account_equity"]) / 10_000,
                color=arm["color"],
                linestyle=arm["linestyle"],
                lw=1.2,
                label=arm["plot_label"],
            )
        ax.set_title(f"{window['requested_start']} ({years}Y)", fontsize=10)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", rotation=25, labelsize=8)
    for ax in axes.ravel()[len(selected) :]:
        ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(
        f"OFFLINE RESEARCH — Stage063 {years}-Year Independent Curves: January + June",
        y=0.998,
        fontsize=15,
    )
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.975), ncol=3)
    fig.tight_layout(rect=[0, 0.01, 1, 0.94])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)
    return buffer.getvalue()


def _plot_aggregate(aggregate: pd.DataFrame) -> bytes:
    metrics = (
        ("return_win_rate_pct", "Return win/non-inferior rate (%)", "YlGn", 0, 100),
        ("median_return_delta_pct", "Median return delta (pp)", "coolwarm", None, None),
        ("dd_noninferior_2pp_rate_pct", "DD non-inferior <=2pp (%)", "YlOrBr", 0, 100),
        ("sharpe_noninferior_005_rate_pct", "Sharpe non-inferior (%)", "PuBuGn", 0, 100),
    )
    row_keys = [
        (comparison_name, cohort)
        for comparison_name in ("A_vs_B", "A_vs_C")
        for cohort, _ in COHORTS
    ]
    row_labels = [
        f"{'Top9' if comparison == 'A_vs_B' else 'Top10'} {cohort.title()}"
        for comparison, cohort in row_keys
    ]
    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    for ax, (column, title, cmap, fixed_min, fixed_max) in zip(
        axes.ravel(), metrics, strict=True
    ):
        values = np.array(
            [
                [
                    float(
                        aggregate[
                            aggregate["comparison"].eq(comparison)
                            & aggregate["start_cohort"].eq(cohort)
                            & aggregate["duration_years"].eq(years)
                        ].iloc[0][column]
                    )
                    for years in DURATIONS_YEARS
                ]
                for comparison, cohort in row_keys
            ]
        )
        vmin, vmax = fixed_min, fixed_max
        if vmin is None:
            bound = max(float(np.abs(values).max()), 1.0)
            vmin, vmax = -bound, bound
        image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                ax.text(j, i, f"{values[i, j]:.1f}", ha="center", va="center")
        ax.set_title(title)
        ax.set_xticks(range(3), ["1Y", "2Y", "3Y"])
        ax.set_yticks(range(len(row_labels)), row_labels)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(
        "OFFLINE RESEARCH — Stage063 Top9 / Top10 vs Formal: Combined / January / June",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    aggregate: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    full = summary[summary["window_group"].eq("full_period")].set_index("promotion_arm")
    lines = [
        "# Stage063 正式Stage037、Top9、Top10多周期对比",
        "",
        f"结论：`{decision['decision']}`。仅离线研究，不改正式物料或稳定生产。",
        "",
        "## 固定口径",
        "",
        "- A：正式Stage037 / m0016 / Top8+fu（9品种）。",
        "- B：Stage062 Top9+fu（10品种）。",
        "- C：Stage061 Top10+fu（11品种）。",
        "- 全周期 + 1/2/3年完整独立冷启动；每档包含1月和6月起点；每窗15万元空仓独立启动。",
        "- 用户明确授权：生产仍为Stage021-Q时，允许以CURRENT/远端master的Stage037作为离线正式对照；因此本报告不可晋升。",
        "",
        "## 全周期",
        "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 交易次数 | 胜率 | broker10峰值 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A", "B", "C"):
        row = full.loc[arm]
        lines.append(
            f"| {arm} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | "
            f"{row['total_slippage']:,.0f} | {int(row['total_trade_count'])} | "
            f"{row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% |"
        )
    for comparison_name, title in (("A_vs_B", "Top9 对正式版"), ("A_vs_C", "Top10 对正式版")):
        lines += [
            "",
            f"## {title}：1/2/3年聚合",
            "",
            "| 周期 | 起点 | 窗口 | 收益胜/非劣率 | 收益差中位 | DD非劣率 | Sharpe非劣率 | 滑点比 |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in aggregate[aggregate["comparison"].eq(comparison_name)].itertuples(
            index=False
        ):
            lines.append(
                f"| {row.duration_years}年 | {row.start_cohort} | {row.window_count} | "
                f"{row.return_win_rate_pct:.2f}% | {row.median_return_delta_pct:+.4f}pp | "
                f"{row.dd_noninferior_2pp_rate_pct:.2f}% | "
                f"{row.sharpe_noninferior_005_rate_pct:.2f}% | {row.slippage_ratio:.4f} |"
            )
        lines += ["", "最弱收益窗口："]
        for row in (
            comparison[
                comparison["comparison"].eq(comparison_name)
                & comparison["duration_years"].isin(DURATIONS_YEARS)
            ]
            .nsmallest(5, "delta_return_pct")
            .itertuples(index=False)
        ):
            lines.append(
                f"- `{row.window_id}`：候选-正式收益 `{row.delta_return_pct:+.4f}pp`，"
                f"回撤恶化 `{row.dd_worsening_pp:.4f}pp`，Sharpe差 `{row.delta_sharpe:+.4f}`。"
            )
    lines += [
        "",
        "## 五张固定图片",
        "",
        *[f"- `{name}`" for name in CHART_FILES.values()],
        "",
        "## 边界与判断",
        "",
        f"- Top9全部门通过：`{decision['candidate_all_multicycle_gates_pass']['B']}`。",
        f"- Top10全部门通过：`{decision['candidate_all_multicycle_gates_pass']['C']}`。",
        "- 全周期3臂逐值复用并核验Stage062；A的42个滚动窗逐窗复用并核验Stage059；Top9/Top10新增84次真引擎独立运行。",
        "- 不连接CTP，不调用order/send/cancel API，不改正式物料、master或生产目录。",
        "- 过拟合：高；Top9/Top10是后验TopN边界研究，本阶段不新增阈值、不按失败窗口救参。",
        "- 继续价值：仅本次跨起点诊断有价值；结论产生后停止TopN扫描。",
        "",
    ]
    return "\n".join(lines)


def _publish(
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
    charts: dict[str, bytes],
    report: str,
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage063.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage063.backup-{uuid4().hex}")
    try:
        for name, frame in frames.items():
            frame.to_csv(temporary / name, index=False, encoding="utf-8-sig")
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


def main() -> None:
    _configure_shared_contract()
    preflight, eligibility_paths = _preflight()
    metadata = s56.s28.s513._metadata()
    full_summary, full_curve = _load_full_period()
    _verify_full_identity(full_summary, full_curve)
    print("[stage063] verified Stage062 full-period A/B/C", flush=True)
    formal_summary, formal_curve = _load_reused_formal_rolling()
    print("[stage063] verified and reused 42 Stage059 formal rolling windows", flush=True)
    summaries = [full_summary, formal_summary]
    curves = [full_curve, formal_curve]
    reused = generated = 0
    candidates = [arm for arm in ARMS if arm["arm"] in {"B", "C"}]
    total = (len(WINDOWS) - 1) * len(candidates)
    index = 0
    for window in WINDOWS[1:]:
        for arm in candidates:
            index += 1
            cached = _load_checkpoint(preflight, window, arm)
            if cached is None:
                print(
                    f"[stage063] {index}/{total} run {window['window_id']} arm={arm['arm']}",
                    flush=True,
                )
                summary, curve = _run_window(
                    metadata, window, arm, eligibility_paths[arm["arm"]]
                )
                _write_checkpoint(preflight, window, arm, summary, curve)
                generated += 1
            else:
                summary, curve = cached
                reused += 1
                print(
                    f"[stage063] {index}/{total} reuse {window['window_id']} arm={arm['arm']}",
                    flush=True,
                )
            summaries.append(summary)
            curves.append(curve)
    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    window_order = {str(item["window_id"]): i for i, item in enumerate(WINDOWS)}
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
    s29._validate_outputs(summary, curve)
    _verify_full_identity(summary, curve)
    comparison = s29._comparison(summary)
    aggregate = s29._aggregate(comparison)
    decision = _decision(preflight, comparison, aggregate, reused, generated)
    charts = {
        CHART_FILES["full_period"]: _plot_full(curve),
        CHART_FILES["1y"]: _plot_grid(curve, comparison, 1),
        CHART_FILES["2y"]: _plot_grid(curve, comparison, 2),
        CHART_FILES["3y"]: _plot_grid(curve, comparison, 3),
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
        _report(summary, comparison, aggregate, decision),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

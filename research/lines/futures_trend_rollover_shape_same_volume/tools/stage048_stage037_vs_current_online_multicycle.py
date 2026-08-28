from __future__ import annotations

from dataclasses import replace
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
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(PORTFOLIO_DIR))

import stage029_stage028_multicycle_abc as s29  # noqa: E402
import stage047_stage037_vs_current_online_fullperiod as s47  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage048_stage037_vs_live_multicycle"
CHECKPOINT_DIR = PROJECT_DIR / ".tools" / "stage048_stage037_vs_live_multicycle_checkpoints"
STAGE047_DIR = LINE_DIR / "artifacts" / "stage047_stage037_vs_live"
DATA_START = pd.Timestamp("2018-01-01")
DATA_END = pd.Timestamp("2026-08-28")
START_MONTHS = (1, 6)
DURATIONS_YEARS = (1, 2, 3)
TERMINAL_TOLERANCE_DAYS = 7
CANDIDATE_LOGIC_COMMIT = "827764ed33f95e9aee6cc03b2b6703805a939ace"
STAGE047_RESULT_COMMIT = "a50d83f6d6e45577696cc0181ce70aff50747be1"
RUNNER_CONTRACT_VERSION = 1

ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": "stage048_A_current_online_stage847_c9_15w_q",
        "label": "A: 当前线上 Stage847-C9-15w + Q",
        "plot_label": "A Current Online",
        "color": "#2563eb",
    },
    {
        "arm": "C",
        "profile": "stage048_C_stage037_long_short_mirror_block",
        "label": "C: Stage037 多空镜像硬拦截",
        "plot_label": "C Stage037",
        "color": "#16a34a",
    },
)
COMPARISONS: tuple[tuple[str, str, str], ...] = (("A_vs_C", "A", "C"),)
COHORTS: tuple[tuple[str, int | None], ...] = (
    ("combined", None),
    ("january", 1),
    ("june", 6),
)
CHART_FILES = {
    "full_period": "stage048_full_period_equity_ac.png",
    "1y": "stage048_equity_curves_1y_ac.png",
    "2y": "stage048_equity_curves_2y_ac.png",
    "3y": "stage048_equity_curves_3y_ac.png",
    "aggregate": "stage048_cycle_aggregate_ac.png",
}
SUMMARY_NAME = "stage048_window_summary.csv"
COMPARISON_NAME = "stage048_window_comparison.csv"
AGGREGATE_NAME = "stage048_cycle_aggregate.csv"
CURVE_NAME = "stage048_equity_curves.csv"
DECISION_NAME = "stage048_decision.json"
REPORT_NAME = "stage048_multicycle_report.md"


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
                if start < DATA_START or start > DATA_END:
                    continue
                end = (start + pd.DateOffset(years=years) - pd.Timedelta(days=1)).normalize()
                if end > DATA_END:
                    continue
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


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_DIR, check=True, capture_output=True, text=True
    ).stdout.strip()


def _configure_shared_contract() -> None:
    s29.WINDOWS = WINDOWS
    s29.ARMS = ARMS
    s29.COMPARISONS = COMPARISONS
    s29.COHORTS = COHORTS
    s29.DURATIONS_YEARS = DURATIONS_YEARS
    s29.TERMINAL_TOLERANCE_DAYS = TERMINAL_TOLERANCE_DAYS


def _runtime_contract_hash() -> str:
    digest = sha256(str(RUNNER_CONTRACT_VERSION).encode())
    paths = (
        Path(__file__),
        Path(s47.__file__),
        Path(s47.stage037_cfg.__file__),
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_portfolio_strategy.py",
        s47.PRODUCTION_STRATEGY,
        s47.PRODUCTION_CONFIG,
    )
    for path in paths:
        digest.update(str(path.resolve()).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _preflight() -> dict[str, Any]:
    identity = s47._preflight()
    for commit in (CANDIDATE_LOGIC_COMMIT, STAGE047_RESULT_COMMIT):
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=PROJECT_DIR,
            check=True,
        )
    stage047_decision_path = STAGE047_DIR / s47.DECISION_NAME
    stage047_decision = json.loads(stage047_decision_path.read_text(encoding="utf-8"))
    stage047_runner_sha = _file_sha256(Path(s47.__file__))
    if stage047_decision["identity"]["source_sha256"]["runner"] != stage047_runner_sha:
        raise RuntimeError("stage048_stage047_runner_artifact_identity_drift")
    if not stage047_decision["full_period_comparison_pass"]:
        raise RuntimeError("stage048_stage047_full_period_gate_not_passed")
    if s47.override_diff() != s47._expected_override_diff():
        raise RuntimeError("stage048_candidate_scope_drift")
    return {
        **identity,
        "stage047_result_commit": STAGE047_RESULT_COMMIT,
        "stage047_decision_sha256": _file_sha256(stage047_decision_path),
        "stage047_runner_sha256": stage047_runner_sha,
        "candidate_logic_commit": CANDIDATE_LOGIC_COMMIT,
        "stage048_parent_head": _git("rev-parse", "HEAD"),
        "runtime_contract_sha256": _runtime_contract_hash(),
    }


def _window_common(window: dict[str, Any], arm: str) -> dict[str, Any]:
    start = pd.Timestamp(window["start"])
    end = pd.Timestamp(window["end"])
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
        "requested_start_month": start.strftime("%Y-%m"),
        "start_month": start.strftime("%Y-%m"),
        "start_year": int(start.year),
        "start_month_num": int(start.month),
    }


def _load_full_period() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(STAGE047_DIR / s47.SUMMARY_NAME)
    curve = pd.read_csv(STAGE047_DIR / s47.CURVE_NAME)
    if set(summary["experiment_arm"].astype(str)) != {"A", "C"} or len(summary) != 2:
        raise RuntimeError("stage048_stage047_full_summary_identity_mismatch")
    window = WINDOWS[0]
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    for arm in ("A", "C"):
        item = summary[summary["experiment_arm"].astype(str).eq(arm)].copy()
        arm_curve = curve[curve["experiment_arm"].astype(str).eq(arm)].copy()
        for key, value in _window_common(window, arm).items():
            item[key] = value
            arm_curve[key] = value
        summaries.append(item)
        curves.append(arm_curve)
    return (
        pd.concat(summaries, ignore_index=True, sort=False),
        pd.concat(curves, ignore_index=True, sort=False),
    )


def _run_production_a(window: dict[str, Any], arm: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    with tempfile.TemporaryDirectory(prefix="stage048-production-a-") as directory:
        output_path = Path(directory) / "result.pkl"
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(s47.PRODUCTION_ROOT)
        result = subprocess.run(
            [
                str(s47.PRODUCTION_ROOT / ".py311" / "bin" / "python"),
                "-c",
                s47._PRODUCTION_A_HELPER,
                str(output_path),
                f"stage048_A_{window['window_id']}",
                arm["label"],
                str(pd.Timestamp(window["start"]).date()),
                str(pd.Timestamp(window["end"]).date()),
            ],
            cwd=s47.PRODUCTION_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"stage048_production_a_failed:{result.stderr[-4000:]}")
        payload = pd.read_pickle(output_path)
    s47._validate_production_engine_binding(payload["module_paths"])
    return payload["summary"], payload["curve"]


def _run_stage037_c(
    metadata: dict[str, Any], window: dict[str, Any], arm: dict[str, str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    original_builder = s47.s28.s901.build_official_live_strategy_overrides
    try:
        s47.s28.s901.build_official_live_strategy_overrides = lambda: s47.build_arm_overrides("C")
        combined, _frames, live_spec = s47.s28.s901._run_live_c9(
            metadata,
            pd.Timestamp(window["start"]),
            pd.Timestamp(window["end"]),
        )
    finally:
        s47.s28.s901.build_official_live_strategy_overrides = original_builder
    profile = f"stage048_C_{window['window_id']}"
    capital = replace(live_spec.capital, variant=profile, label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=profile)
    return s47.s28.s827._metric({"profile": profile, "spec": metric_spec}, combined)


def _run_window(
    metadata: dict[str, Any], window: dict[str, Any], arm: dict[str, str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if arm["arm"] == "A":
        summary, curve = _run_production_a(window, arm)
    else:
        summary, curve = _run_stage037_c(metadata, window, arm)
    summary["experiment_arm"] = arm["arm"]
    curve["experiment_arm"] = arm["arm"]
    for key, value in _window_common(window, arm["arm"]).items():
        summary[key] = value
        curve[key] = value
    return summary, curve


def _checkpoint_contract(
    preflight: dict[str, Any], window: dict[str, Any], arm: dict[str, str]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "runtime_contract_sha256": preflight["runtime_contract_sha256"],
        "database_sha256": preflight["runtime_binding"]["database_sha256"],
        "ai_pool_sha256": preflight["ai_pool"]["sha256"],
        "production_head": preflight["production_head"],
        "candidate_logic_commit": CANDIDATE_LOGIC_COMMIT,
        "window_id": str(window["window_id"]),
        "requested_start": str(pd.Timestamp(window["start"]).date()),
        "requested_end": str(pd.Timestamp(window["end"]).date()),
        "arm": arm["arm"],
    }


def _checkpoint_path(contract: dict[str, Any]) -> Path:
    key = sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()[:24]
    return CHECKPOINT_DIR / f"{contract['window_id']}__{contract['arm']}__{key}"


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
        if not s29._checkpoint_frames_valid(summary, curve, contract):
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
    temporary = Path(tempfile.mkdtemp(prefix=".stage048-checkpoint-", dir=CHECKPOINT_DIR))
    try:
        summary_path = temporary / "summary.csv"
        curve_path = temporary / "curve.csv"
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


def _verify_full_identity(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    source_summary = pd.read_csv(STAGE047_DIR / s47.SUMMARY_NAME).set_index("experiment_arm")
    source_curve = pd.read_csv(STAGE047_DIR / s47.CURVE_NAME)
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
    for arm in ("A", "C"):
        if not np.allclose(
            full.loc[arm, metrics].to_numpy(dtype=float),
            source_summary.loc[arm, metrics].to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-9,
        ):
            raise RuntimeError(f"stage048_full_summary_drift:{arm}")
        left = curve[
            curve["window_group"].eq("full_period") & curve["promotion_arm"].eq(arm)
        ].sort_values("date")
        right = source_curve[source_curve["experiment_arm"].eq(arm)].sort_values("date")
        left_dates = pd.to_datetime(left["date"], format="mixed").dt.strftime("%Y-%m-%d")
        right_dates = pd.to_datetime(right["date"], format="mixed").dt.strftime("%Y-%m-%d")
        if left_dates.tolist() != right_dates.tolist() or not np.allclose(
            pd.to_numeric(left["account_equity"]),
            pd.to_numeric(right["account_equity"]),
            rtol=0.0,
            atol=1e-9,
        ):
            raise RuntimeError(f"stage048_full_curve_drift:{arm}")


def _cycle_gates(row: dict[str, Any]) -> dict[str, bool]:
    return s29._cycle_gates(row)


def _decision(
    preflight: dict[str, Any],
    comparison: pd.DataFrame,
    aggregate: pd.DataFrame,
    checkpoint_reused: int,
    checkpoint_generated: int,
) -> dict[str, Any]:
    full_row = comparison[comparison["window_group"].eq("full_period")].iloc[0]
    full_gates = s29._full_period_gates(full_row)
    cycle_rows: list[dict[str, Any]] = []
    for row in aggregate.to_dict(orient="records"):
        gates = _cycle_gates(row)
        cycle_rows.append(
            {
                "duration_years": int(row["duration_years"]),
                "start_cohort": str(row["start_cohort"]),
                "gates": gates,
                "pass": bool(all(gates.values())),
            }
        )
    all_pass = bool(all(full_gates.values()) and all(row["pass"] for row in cycle_rows))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage048",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": preflight,
        "gate_contract": {
            "data_start": str(DATA_START.date()),
            "data_end": str(DATA_END.date()),
            "start_schedule": "January and June independent cold starts",
            "durations_years": list(DURATIONS_YEARS),
            "complete_windows_only": True,
            "arms": {arm["arm"]: arm["label"] for arm in ARMS},
            "full_period_gate": "return>=A, DD worsening<=2pp, Sharpe delta>=-0.02, slippage<=105%, survival and broker100 non-worse",
            "cycle_gate": "return wins>=50%, median delta>=0, DD and Sharpe noninferior>=80%, aggregate slippage<=105%, survival and broker100 non-worse",
        },
        "run_provenance": {
            "window_count": len(WINDOWS),
            "logical_arm_window_count": len(WINDOWS) * len(ARMS),
            "full_period_reused_and_verified_from_stage047": True,
            "new_independent_run_count": (len(WINDOWS) - 1) * len(ARMS),
            "checkpoint_reused_count": checkpoint_reused,
            "checkpoint_generated_count": checkpoint_generated,
        },
        "full_period_gates": full_gates,
        "cycle_gates": cycle_rows,
        "all_multicycle_gates_pass": all_pass,
        "promote_to_official": False,
        "decision": (
            "stage037_multicycle_supports_next_formal_review_no_automatic_promotion"
            if all_pass
            else "stage037_multicycle_has_hard_fail_keep_research"
        ),
        "overfitting_judgment": "固定规则跨起点验证本身不新增过拟合；Stage037历史后验选择风险仍保留。",
        "continued_value_judgment": "只在冻结规则的稳健性与归因层面有价值，不扫描参数救援。",
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _plot_full(curves: pd.DataFrame) -> bytes:
    frame = curves[curves["window_group"].eq("full_period")]
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
    ax.set_title("Stage048 Full Period: Current Online vs Stage037")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _plot_window_grid(curves: pd.DataFrame, comparison: pd.DataFrame, years: int) -> bytes:
    selected = comparison[comparison["duration_years"].eq(years)].sort_values("requested_start")
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
        ax.set_title(f"{window['requested_start']} ({years}Y)", fontsize=10)
        ax.set_ylabel("Equity (10k CNY)")
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", rotation=25, labelsize=8)
    for ax in axes.ravel()[len(selected):]:
        ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(
        f"Stage048 {years}-Year Independent Equity Curves: January + June Starts",
        y=0.998,
        fontsize=15,
    )
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.975), ncol=2)
    fig.tight_layout(rect=[0, 0.01, 1, 0.94])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)
    return buffer.getvalue()


def _plot_aggregate(aggregate: pd.DataFrame) -> bytes:
    row_keys = [(cohort, month) for cohort, month in COHORTS]
    metrics = [
        ("return_win_rate_pct", "Return Win Rate (%)", "YlGn", 0.0, 100.0),
        ("median_return_delta_pct", "Median Return Delta (pp)", "coolwarm", None, None),
        ("dd_noninferior_2pp_rate_pct", "DD Non-Inferior <=2pp (%)", "YlOrBr", 0.0, 100.0),
        ("sharpe_noninferior_005_rate_pct", "Sharpe Non-Inferior (%)", "PuBuGn", 0.0, 100.0),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for ax, (column, title, cmap, fixed_min, fixed_max) in zip(axes.ravel(), metrics, strict=True):
        values = np.empty((len(row_keys), len(DURATIONS_YEARS)))
        for row_index, (cohort, _month) in enumerate(row_keys):
            for column_index, years in enumerate(DURATIONS_YEARS):
                row = aggregate[
                    aggregate["start_cohort"].eq(cohort)
                    & aggregate["duration_years"].eq(years)
                ].iloc[0]
                values[row_index, column_index] = float(row[column])
        vmin, vmax = fixed_min, fixed_max
        if column == "median_return_delta_pct":
            bound = max(float(np.abs(values).max()), 1.0)
            vmin, vmax = -bound, bound
        image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        for row_index in range(values.shape[0]):
            for column_index in range(values.shape[1]):
                ax.text(column_index, row_index, f"{values[row_index, column_index]:.1f}", ha="center", va="center")
        ax.set_title(title)
        ax.set_xticks(range(3), ["1Y", "2Y", "3Y"])
        ax.set_yticks(range(3), [item[0].title() for item in row_keys])
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Stage048 A vs C: Combined / January / June", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
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


def _report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    aggregate: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    full = summary[summary["window_group"].eq("full_period")].set_index("promotion_arm")
    weakest_return = comparison[comparison["duration_years"].isin(DURATIONS_YEARS)].nsmallest(8, "delta_return_pct")
    weakest_dd = comparison[comparison["duration_years"].isin(DURATIONS_YEARS)].nlargest(6, "dd_worsening_pp")
    lines = [
        "# Stage048 Stage037 与当前线上版本多周期报告",
        "",
        f"结论：`{decision['decision']}`。本报告不自动晋升或部署策略。",
        "",
        "## 身份与窗口",
        "",
        f"- 当前线上：`{decision['identity']['online_version']}`；生产/远端master `{decision['identity']['production_head']}`。",
        f"- Stage037：`{s47.stage037_cfg.CANDIDATE_VERSION}`；冻结逻辑提交 `{CANDIDATE_LOGIC_COMMIT}`。",
        f"- 数据截止：`{DATA_END.date()}`；数据库 `{decision['identity']['runtime_binding']['database_sha256']}`；AI池 `{decision['identity']['ai_pool']['sha256']}`。",
        "- 窗口：全周期 + 1/2/3年完整独立冷启动；每个周期固定包含1月和6月起点。A/C每窗均以15万元空仓独立启动。",
        "",
        "## 全周期",
        "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 成交记录 | 胜率 | broker10峰值 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A", "C"):
        row = full.loc[arm]
        lines.append(
            f"| {arm} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | {row['total_slippage']:,.0f} | "
            f"{int(row['total_trade_count'])} | {row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% |"
        )
    lines.extend(
        [
            "",
            "## 1/2/3年聚合（combined / January / June）",
            "",
            "| 周期 | 起点 | 窗口 | C收益胜率 | 收益差中位 | DD非劣率 | Sharpe非劣率 | 滑点比 |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in aggregate.itertuples(index=False):
        lines.append(
            f"| {row.duration_years}年 | {row.start_cohort} | {row.window_count} | "
            f"{row.return_win_rate_pct:.2f}% | {row.median_return_delta_pct:+.4f}pp | "
            f"{row.dd_noninferior_2pp_rate_pct:.2f}% | {row.sharpe_noninferior_005_rate_pct:.2f}% | "
            f"{row.slippage_ratio:.4f} |"
        )
    lines.extend(["", "## 最弱收益窗口", ""])
    for row in weakest_return.itertuples(index=False):
        lines.append(
            f"- `{row.window_id}`：C-A收益 `{row.delta_return_pct:+.4f}pp`，回撤恶化 "
            f"`{row.dd_worsening_pp:.4f}pp`，Sharpe差 `{row.delta_sharpe:+.4f}`。"
        )
    lines.extend(["", "## 最弱回撤窗口", ""])
    for row in weakest_dd.itertuples(index=False):
        lines.append(
            f"- `{row.window_id}`：回撤恶化 `{row.dd_worsening_pp:.4f}pp`，C-A收益 "
            f"`{row.delta_return_pct:+.4f}pp`，Sharpe差 `{row.delta_sharpe:+.4f}`。"
        )
    lines.extend(
        [
            "",
            "## 五张固定图片",
            "",
            *[f"- `{filename}`" for filename in CHART_FILES.values()],
            "",
            "## 安全与研究判断",
            "",
            "- 全周期产物从Stage047复用并逐值校验；其余42窗×2臂均为真引擎独立运行，不是切片全周期曲线。",
            "- 没有连接CTP或调用order/send/cancel API；正式物料、生产worktree和master均未改变。",
            f"- 多周期全部预声明门：`{decision['all_multicycle_gates_pass']}`；`promote_to_official=false`。",
            "- 过拟合：本次固定规则验证不新增过拟合，但Stage037历史后验选择风险仍在；不得按失败窗口继续调参数。",
            "- 继续价值：有冻结规则稳健性判断价值；没有阈值扫描或单窗救援价值。",
            "",
        ]
    )
    return "\n".join(lines)


def _publish_atomically(
    frames: dict[str, pd.DataFrame], decision: dict[str, Any], charts: dict[str, bytes], report: str
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage048.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage048.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary / filename, index=False, encoding="utf-8-sig")
        (temporary / DECISION_NAME).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temporary / REPORT_NAME).write_text(report, encoding="utf-8")
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
    _configure_shared_contract()
    preflight = _preflight()
    metadata = s47.s28.s513._metadata()
    full_summary, full_curve = _load_full_period()
    _verify_full_identity(full_summary, full_curve)
    print("[stage048] full-period Stage047 artifact verified", flush=True)

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
            if cached is None:
                print(
                    f"[stage048] {run_index}/{run_total} run {window['window_id']} arm={arm['arm']}",
                    flush=True,
                )
                summary, curve = _run_window(metadata, window, arm)
                _write_checkpoint(preflight, window, arm, summary, curve)
                generated_count += 1
            else:
                summary, curve = cached
                reused_count += 1
                print(
                    f"[stage048] {run_index}/{run_total} reuse {window['window_id']} arm={arm['arm']}",
                    flush=True,
                )
            summaries.append(summary)
            curves.append(curve)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    window_order = {str(window["window_id"]): index for index, window in enumerate(WINDOWS)}
    arm_order = {str(arm["arm"]): index for index, arm in enumerate(ARMS)}
    summary["_window_order"] = summary["window_id"].map(window_order)
    summary["_arm_order"] = summary["promotion_arm"].map(arm_order)
    summary = summary.sort_values(["_window_order", "_arm_order"]).drop(columns=["_window_order", "_arm_order"])
    curve["_window_order"] = curve["window_id"].map(window_order)
    curve["_arm_order"] = curve["promotion_arm"].map(arm_order)
    curve = curve.sort_values(["_window_order", "_arm_order", "date"]).drop(columns=["_window_order", "_arm_order"])
    s29._validate_outputs(summary, curve)
    _verify_full_identity(summary, curve)
    comparison = s29._comparison(summary)
    aggregate = s29._aggregate(comparison)
    decision = _decision(preflight, comparison, aggregate, reused_count, generated_count)
    _publish_atomically(
        {
            SUMMARY_NAME: summary,
            COMPARISON_NAME: comparison,
            AGGREGATE_NAME: aggregate,
            CURVE_NAME: curve,
        },
        decision,
        _charts(curve, comparison, aggregate),
        _report(summary, comparison, aggregate, decision),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

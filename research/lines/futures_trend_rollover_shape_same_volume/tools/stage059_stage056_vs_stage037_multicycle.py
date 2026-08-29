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


LINE_ID = "futures_trend_rollover_shape_same_volume"
STAGE = "Stage059"
LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage059_stage056_vs_stage037_multicycle"
CHECKPOINT_DIR = PROJECT_DIR / ".tools" / "stage059_stage056_vs_stage037_multicycle_checkpoints"
STAGE056_DIR = s56.OUTPUT_DIR

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

ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "profile": "stage059_A_master_m0016_stage037_top8_plus_fu",
        "label": "A: Stage037 Top8+fu（9品种）",
        "plot_label": "A Stage037 Top8+fu",
        "color": "#2563eb",
    },
    {
        "arm": "C",
        "profile": "stage059_C_stage056_stage037_top14_plus_fu",
        "label": "C: Stage056 Top14+fu（15品种）",
        "plot_label": "C Stage056 Top14+fu",
        "color": "#16a34a",
    },
)
COMPARISONS = (("A_vs_C", "A", "C"),)
COHORTS = (("combined", None), ("january", 1), ("june", 6))
CHART_FILES = {
    "full_period": "stage059_full_period_equity_ac.png",
    "1y": "stage059_equity_curves_1y_ac.png",
    "2y": "stage059_equity_curves_2y_ac.png",
    "3y": "stage059_equity_curves_3y_ac.png",
    "aggregate": "stage059_cycle_aggregate_ac.png",
}
SUMMARY_NAME = "stage059_window_summary.csv"
COMPARISON_NAME = "stage059_window_comparison.csv"
AGGREGATE_NAME = "stage059_cycle_aggregate.csv"
CURVE_NAME = "stage059_equity_curves.csv"
DECISION_NAME = "stage059_decision.json"
REPORT_NAME = "stage059_multicycle_report.md"


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


def _configure_shared_contract() -> None:
    s29.WINDOWS = WINDOWS
    s29.ARMS = ARMS
    s29.COMPARISONS = COMPARISONS
    s29.COHORTS = COHORTS
    s29.DURATIONS_YEARS = DURATIONS_YEARS
    s29.TERMINAL_TOLERANCE_DAYS = TERMINAL_TOLERANCE_DAYS


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
            "stage059_stage037_identity_mismatch:"
            f"actual={actual}:expected={expected}:remote={remote_master}"
        )
    production_matches = all(production_identity.get(key) == value for key, value in expected.items())
    return {
        "research_protocol": "explicit_stage037_vs_stage056_offline",
        "checkout_stage037_identity_pass": True,
        "production_identity_matches_stage037": bool(production_matches),
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
    }


def _runtime_contract_hash() -> str:
    digest = sha256(str(RUNNER_CONTRACT_VERSION).encode())
    for path in (
        Path(__file__),
        Path(s56.__file__),
        Path(s56.candidate_cfg.__file__),
        Path(s29.__file__),
        PROJECT_DIR / "examples" / "portfolio_backtesting" / "qmt_roll_portfolio_strategy.py",
    ):
        digest.update(str(path.resolve()).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _preflight() -> dict[str, Any]:
    checkout = asdict(s56.assert_official_checkout_matches_active_material(PROJECT_DIR))
    production = asdict(s56.assert_official_checkout_matches_active_material(s56.PRODUCTION_ROOT))
    remote_master = _git("rev-parse", "origin/master")
    evidence = _assert_offline_identity_contract(checkout, production, remote_master)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_MASTER_COMMIT, "HEAD"],
        cwd=PROJECT_DIR,
        check=True,
    )
    decision_path = STAGE056_DIR / s56.DECISION_NAME
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    eligibility_path = Path(s56.candidate_cfg.CANDIDATE_ELIGIBILITY_PATH)
    expected_diff = {"ai_product_pool_eligibility_path", "ai_product_pool_strategy"}
    if set(s56.candidate_cfg.override_diff()) != expected_diff:
        raise RuntimeError("stage059_candidate_scope_drift")
    if decision.get("candidate_version") != s56.candidate_cfg.CANDIDATE_VERSION:
        raise RuntimeError("stage059_stage056_artifact_identity_drift")
    return {
        **evidence,
        "checkout_identity": checkout,
        "production_identity": production,
        "checkout_head": _git("rev-parse", "HEAD"),
        "production_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=s56.PRODUCTION_ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.strip(),
        "remote_master": remote_master,
        "stage056_decision_sha256": _file_sha256(decision_path),
        "database_path": str(s56.DATABASE_PATH.resolve()),
        "database_sha256": _file_sha256(s56.DATABASE_PATH),
        "candidate_eligibility_path": str(eligibility_path.resolve()),
        "candidate_eligibility_sha256": _file_sha256(eligibility_path),
        "runtime_contract_sha256": _runtime_contract_hash(),
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
        "window_label": f"{start.date()} independent start to {end.date()}",
        "requested_start_month": start.strftime("%Y-%m"),
        "start_month": start.strftime("%Y-%m"),
        "start_year": int(start.year),
        "start_month_num": int(start.month),
    }


def _load_full_period() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(STAGE056_DIR / s56.SUMMARY_NAME)
    curve = pd.read_csv(STAGE056_DIR / s56.CURVE_NAME)
    if len(summary) != 2 or set(summary["experiment_arm"].astype(str)) != {"A", "C"}:
        raise RuntimeError("stage059_stage056_full_summary_identity_mismatch")
    summaries, curves = [], []
    for arm in ("A", "C"):
        item = summary[summary["experiment_arm"].astype(str).eq(arm)].copy()
        arm_curve = curve[curve["experiment_arm"].astype(str).eq(arm)].copy()
        for key, value in _window_common(WINDOWS[0], arm).items():
            item[key] = value
            arm_curve[key] = value
        summaries.append(item)
        curves.append(arm_curve)
    return pd.concat(summaries, ignore_index=True), pd.concat(curves, ignore_index=True)


def _verify_full_identity(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    source_summary = pd.read_csv(STAGE056_DIR / s56.SUMMARY_NAME).set_index("experiment_arm")
    source_curve = pd.read_csv(STAGE056_DIR / s56.CURVE_NAME)
    full = summary[summary["window_group"].eq("full_period")].set_index("promotion_arm")
    metrics = [
        "end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage",
        "total_trade_count", "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct", "days_over_100pct",
    ]
    for arm in ("A", "C"):
        left_metrics = pd.to_numeric(full.loc[arm, metrics], errors="raise").to_numpy(dtype=float)
        right_metrics = pd.to_numeric(
            source_summary.loc[arm, metrics], errors="raise"
        ).to_numpy(dtype=float)
        if not np.allclose(left_metrics, right_metrics, atol=1e-9, rtol=0):
            raise RuntimeError(f"stage059_full_summary_drift:{arm}")
        left = curve[(curve["window_group"].eq("full_period")) & (curve["promotion_arm"].eq(arm))].sort_values("date")
        right = source_curve[source_curve["experiment_arm"].eq(arm)].sort_values("date")
        if pd.to_datetime(left["date"]).tolist() != pd.to_datetime(right["date"]).tolist():
            raise RuntimeError(f"stage059_full_curve_date_drift:{arm}")
        if not np.allclose(left["account_equity"], right["account_equity"], atol=1e-9, rtol=0):
            raise RuntimeError(f"stage059_full_curve_equity_drift:{arm}")


def _run_window(metadata: dict[str, Any], window: dict[str, Any], arm: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    original_builder = s56.s28.s901.build_official_live_strategy_overrides
    try:
        s56.s28.s901.build_official_live_strategy_overrides = lambda: s56.build_arm_overrides(arm["arm"])
        combined, _frames, live_spec = s56.s28.s901._run_live_c9(
            metadata, pd.Timestamp(window["start"]), pd.Timestamp(window["end"])
        )
    finally:
        s56.s28.s901.build_official_live_strategy_overrides = original_builder
    profile = f"stage059_{arm['arm']}_{window['window_id']}"
    capital = replace(live_spec.capital, variant=profile, label=arm["label"])
    metric_spec = replace(live_spec, capital=capital, profile=profile)
    summary, curve = s56.s28.s827._metric({"profile": profile, "spec": metric_spec}, combined)
    summary["experiment_arm"] = arm["arm"]
    curve["experiment_arm"] = arm["arm"]
    for key, value in _window_common(window, arm["arm"]).items():
        summary[key] = value
        curve[key] = value
    return summary, curve


def _checkpoint_contract(preflight: dict[str, Any], window: dict[str, Any], arm: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "runtime_contract_sha256": preflight["runtime_contract_sha256"],
        "database_sha256": preflight["database_sha256"],
        "candidate_eligibility_sha256": preflight["candidate_eligibility_sha256"],
        "base_master_commit": BASE_MASTER_COMMIT,
        "window_id": str(window["window_id"]),
        "requested_start": str(pd.Timestamp(window["start"]).date()),
        "requested_end": str(pd.Timestamp(window["end"]).date()),
        "arm": arm["arm"],
    }


def _checkpoint_path(contract: dict[str, Any]) -> Path:
    key = sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()[:24]
    return CHECKPOINT_DIR / f"{contract['window_id']}__{contract['arm']}__{key}"


def _load_checkpoint(preflight: dict[str, Any], window: dict[str, Any], arm: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    contract = _checkpoint_contract(preflight, window, arm)
    directory = _checkpoint_path(contract)
    meta_path, summary_path, curve_path = directory / "meta.json", directory / "summary.csv", directory / "curve.csv"
    if not all(path.exists() for path in (meta_path, summary_path, curve_path)):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        summary, curve = pd.read_csv(summary_path), pd.read_csv(curve_path)
        if meta.get("contract") != contract:
            return None
        if meta.get("summary_sha256") != _file_sha256(summary_path) or meta.get("curve_sha256") != _file_sha256(curve_path):
            return None
        return (summary, curve) if s29._checkpoint_frames_valid(summary, curve, contract) else None
    except Exception:
        return None


def _write_checkpoint(preflight: dict[str, Any], window: dict[str, Any], arm: dict[str, str], summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    contract = _checkpoint_contract(preflight, window, arm)
    directory = _checkpoint_path(contract)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage059-checkpoint-", dir=CHECKPOINT_DIR))
    try:
        summary_path, curve_path = temporary / "summary.csv", temporary / "curve.csv"
        summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
        curve.to_csv(curve_path, index=False, encoding="utf-8-sig")
        (temporary / "meta.json").write_text(json.dumps({
            "contract": contract,
            "summary_sha256": _file_sha256(summary_path),
            "curve_sha256": _file_sha256(curve_path),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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


def _decision(preflight: dict[str, Any], comparison: pd.DataFrame, aggregate: pd.DataFrame, reused: int, generated: int) -> dict[str, Any]:
    full_gates = s29._full_period_gates(comparison[comparison["window_group"].eq("full_period")].iloc[0])
    cycle_rows = []
    for row in aggregate.to_dict(orient="records"):
        gates = _cycle_gates(row)
        cycle_rows.append({
            "duration_years": int(row["duration_years"]),
            "start_cohort": str(row["start_cohort"]),
            "gates": gates,
            "pass": bool(all(gates.values())),
        })
    all_pass = bool(all(full_gates.values()) and all(item["pass"] for item in cycle_rows))
    return {
        "line_id": LINE_ID,
        "stage": STAGE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": preflight,
        "gate_contract": {
            "data_start": str(DATA_START.date()), "data_end": str(DATA_END.date()),
            "start_schedule": "January and June independent cold starts",
            "durations_years": list(DURATIONS_YEARS), "complete_windows_only": True,
            "arms": {arm["arm"]: arm["label"] for arm in ARMS},
            "full_period": "return>=A, DD worsening<=2pp, Sharpe delta>=-0.02, slippage<=105%, survival and broker100 non-worse",
            "cycle": "return wins>=50%, median delta>=0, DD and Sharpe noninferior>=80%, aggregate slippage<=105%, survival and broker100 non-worse",
        },
        "run_provenance": {
            "window_count": len(WINDOWS), "logical_arm_window_count": len(WINDOWS) * 2,
            "full_period_reused_and_verified_from_stage056": True,
            "new_independent_run_count": (len(WINDOWS) - 1) * 2,
            "checkpoint_reused_count": reused, "checkpoint_generated_count": generated,
        },
        "full_period_gates": full_gates,
        "cycle_gates": cycle_rows,
        "all_multicycle_gates_pass": all_pass,
        "formal_production_ac_compliant": False,
        "promotion_permitted": False,
        "promote_to_official": False,
        "decision": "offline_research_multicycle_supports_stage056" if all_pass else "offline_research_multicycle_has_hard_fail_keep_stage037",
        "overfitting_judgment": "中等：只验证一个冻结的Top14广度点，没有参数扫描；但Stage056是在已看过Stage037结果后提出。",
        "continued_value_judgment": "有价值：能检验扩大品种池是否跨起点稳定；若失败不做单窗口调参救援。",
        "order_api_called_count": 0, "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0, "ctp_connected": False,
    }


def _plot_full(curves: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        item = curves[(curves["window_group"].eq("full_period")) & (curves["promotion_arm"].eq(arm["arm"]))].sort_values("date")
        ax.plot(pd.to_datetime(item["date"]), pd.to_numeric(item["account_equity"]) / 10_000, color=arm["color"], lw=1.4, label=arm["plot_label"])
    ax.set(title="Stage059 Full Period: Stage037 vs Stage056", ylabel="Equity (10k CNY)")
    ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    buffer = BytesIO(); fig.savefig(buffer, format="png", dpi=170); plt.close(fig)
    return buffer.getvalue()


def _plot_grid(curves: pd.DataFrame, comparison: pd.DataFrame, years: int) -> bytes:
    selected = comparison[comparison["duration_years"].eq(years)].sort_values("requested_start")
    rows = math.ceil(len(selected) / 4)
    fig, axes = plt.subplots(rows, 4, figsize=(18, 3.5 * rows), squeeze=False)
    for ax, (_, window) in zip(axes.ravel(), selected.iterrows(), strict=False):
        data = curves[curves["window_id"].eq(window["window_id"])]
        for arm in ARMS:
            item = data[data["promotion_arm"].eq(arm["arm"])].sort_values("date")
            ax.plot(pd.to_datetime(item["date"]), pd.to_numeric(item["account_equity"]) / 10_000, color=arm["color"], lw=1, label=arm["plot_label"])
        ax.set_title(f"{window['requested_start']} ({years}Y)", fontsize=10); ax.grid(alpha=.22); ax.tick_params(axis="x", rotation=25, labelsize=8)
    for ax in axes.ravel()[len(selected):]: ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(f"Stage059 {years}-Year Independent Equity Curves: January + June Starts", y=.998, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5, .975), ncol=2)
    fig.tight_layout(rect=[0, .01, 1, .94]); buffer = BytesIO(); fig.savefig(buffer, format="png", dpi=150); plt.close(fig)
    return buffer.getvalue()


def _plot_aggregate(aggregate: pd.DataFrame) -> bytes:
    metrics = [("return_win_rate_pct", "Return Win Rate (%)", "YlGn", 0, 100), ("median_return_delta_pct", "Median Return Delta (pp)", "coolwarm", None, None), ("dd_noninferior_2pp_rate_pct", "DD Non-Inferior <=2pp (%)", "YlOrBr", 0, 100), ("sharpe_noninferior_005_rate_pct", "Sharpe Non-Inferior (%)", "PuBuGn", 0, 100)]
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for ax, (column, title, cmap, vmin, vmax) in zip(axes.ravel(), metrics, strict=True):
        values = np.array([[float(aggregate[(aggregate["start_cohort"].eq(cohort)) & (aggregate["duration_years"].eq(years))].iloc[0][column]) for years in DURATIONS_YEARS] for cohort, _ in COHORTS])
        if vmin is None:
            bound = max(float(np.abs(values).max()), 1); vmin, vmax = -bound, bound
        image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        for i in range(3):
            for j in range(3): ax.text(j, i, f"{values[i, j]:.1f}", ha="center", va="center")
        ax.set_title(title); ax.set_xticks(range(3), ["1Y", "2Y", "3Y"]); ax.set_yticks(range(3), [item[0].title() for item in COHORTS]); fig.colorbar(image, ax=ax, fraction=.046, pad=.04)
    fig.suptitle("Stage059 Stage037 vs Stage056: Combined / January / June", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, .97]); buffer = BytesIO(); fig.savefig(buffer, format="png", dpi=170); plt.close(fig)
    return buffer.getvalue()


def _report(summary: pd.DataFrame, comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> str:
    full = summary[summary["window_group"].eq("full_period")].set_index("promotion_arm")
    lines = [
        "# Stage059 Stage056 与 Stage037 多周期对比", "",
        f"结论：`{decision['decision']}`。这是用户明确要求的离线研究比较，不代表当前生产A/C，也不自动晋升。", "",
        "## 固定口径", "",
        "- A：Stage037 / m0016 / Top8+fu（9品种）。",
        "- C：Stage056 / Stage037逻辑不变 / Top14+fu（15品种）。",
        "- 全周期 + 1/2/3年完整独立冷启动；各周期包含1月、6月起点；每窗15万元空仓独立启动。", "",
        "## 全周期", "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 成交记录 | 胜率 | broker10峰值 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A", "C"):
        row = full.loc[arm]
        lines.append(f"| {arm} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | {row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | {row['total_slippage']:,.0f} | {int(row['total_trade_count'])} | {row['nonzero_daily_win_rate_pct']:.4f}% | {row['max_broker10_margin_to_equity_pct']:.4f}% |")
    lines += ["", "## 1/2/3年聚合", "", "| 周期 | 起点 | 窗口 | C收益胜率 | 收益差中位 | DD非劣率 | Sharpe非劣率 | 滑点比 |", "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in aggregate.itertuples(index=False):
        lines.append(f"| {row.duration_years}年 | {row.start_cohort} | {row.window_count} | {row.return_win_rate_pct:.2f}% | {row.median_return_delta_pct:+.4f}pp | {row.dd_noninferior_2pp_rate_pct:.2f}% | {row.sharpe_noninferior_005_rate_pct:.2f}% | {row.slippage_ratio:.4f} |")
    lines += ["", "## 最弱窗口", ""]
    for row in comparison[comparison["duration_years"].isin(DURATIONS_YEARS)].nsmallest(8, "delta_return_pct").itertuples(index=False):
        lines.append(f"- `{row.window_id}`：C-A收益 `{row.delta_return_pct:+.4f}pp`，回撤恶化 `{row.dd_worsening_pp:.4f}pp`，Sharpe差 `{row.delta_sharpe:+.4f}`。")
    lines += ["", "## 五张固定图片", "", *[f"- `{name}`" for name in CHART_FILES.values()], "", "## 边界与判断", "", f"- 全部预声明门通过：`{decision['all_multicycle_gates_pass']}`；`promote_to_official=false`。", "- 全周期复用Stage056并逐值校验；其余42窗×2臂为真引擎独立运行。", "- 不连接CTP，不调用order/send/cancel API，不改正式物料、生产目录或master。", "- 过拟合：中等；固定单点跨起点检验不新增参数拟合，但Top14假设具有后验选择风险。", "- 继续价值：有；用跨周期稳定性决定是否保留Stage056，不按失败窗口调参。", ""]
    return "\n".join(lines)


def _publish(frames: dict[str, pd.DataFrame], decision: dict[str, Any], charts: dict[str, bytes], report: str) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".stage059.tmp-", dir=OUTPUT_DIR.parent))
    backup = OUTPUT_DIR.with_name(f".stage059.backup-{uuid4().hex}")
    try:
        for name, frame in frames.items(): frame.to_csv(temporary / name, index=False, encoding="utf-8-sig")
        (temporary / DECISION_NAME).write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (temporary / REPORT_NAME).write_text(report, encoding="utf-8")
        for name, payload in charts.items(): (temporary / name).write_bytes(payload)
        if OUTPUT_DIR.exists(): os.replace(OUTPUT_DIR, backup)
        os.replace(temporary, OUTPUT_DIR)
        if backup.exists(): shutil.rmtree(backup)
    finally:
        if temporary.exists(): shutil.rmtree(temporary, ignore_errors=True)


def main() -> None:
    _configure_shared_contract()
    preflight = _preflight()
    metadata = s56.s28.s513._metadata()
    full_summary, full_curve = _load_full_period()
    _verify_full_identity(full_summary, full_curve)
    print("[stage059] verified Stage056 full-period artifact", flush=True)
    summaries, curves = [full_summary], [full_curve]
    reused = generated = 0
    total = (len(WINDOWS) - 1) * len(ARMS)
    index = 0
    for window in WINDOWS[1:]:
        for arm in ARMS:
            index += 1
            cached = _load_checkpoint(preflight, window, arm)
            if cached is None:
                print(f"[stage059] {index}/{total} run {window['window_id']} arm={arm['arm']}", flush=True)
                summary, curve = _run_window(metadata, window, arm)
                _write_checkpoint(preflight, window, arm, summary, curve)
                generated += 1
            else:
                summary, curve = cached; reused += 1
                print(f"[stage059] {index}/{total} reuse {window['window_id']} arm={arm['arm']}", flush=True)
            summaries.append(summary); curves.append(curve)
    summary, curve = pd.concat(summaries, ignore_index=True), pd.concat(curves, ignore_index=True)
    window_order = {str(item["window_id"]): i for i, item in enumerate(WINDOWS)}
    arm_order = {item["arm"]: i for i, item in enumerate(ARMS)}
    summary = summary.assign(_w=summary["window_id"].map(window_order), _a=summary["promotion_arm"].map(arm_order)).sort_values(["_w", "_a"]).drop(columns=["_w", "_a"])
    curve = curve.assign(_w=curve["window_id"].map(window_order), _a=curve["promotion_arm"].map(arm_order)).sort_values(["_w", "_a", "date"]).drop(columns=["_w", "_a"])
    s29._validate_outputs(summary, curve); _verify_full_identity(summary, curve)
    comparison, aggregate = s29._comparison(summary), s29._aggregate(s29._comparison(summary))
    decision = _decision(preflight, comparison, aggregate, reused, generated)
    charts = {CHART_FILES["full_period"]: _plot_full(curve), CHART_FILES["1y"]: _plot_grid(curve, comparison, 1), CHART_FILES["2y"]: _plot_grid(curve, comparison, 2), CHART_FILES["3y"]: _plot_grid(curve, comparison, 3), CHART_FILES["aggregate"]: _plot_aggregate(aggregate)}
    _publish({SUMMARY_NAME: summary, COMPARISON_NAME: comparison, AGGREGATE_NAME: aggregate, CURVE_NAME: curve}, decision, charts, _report(summary, comparison, aggregate, decision))
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

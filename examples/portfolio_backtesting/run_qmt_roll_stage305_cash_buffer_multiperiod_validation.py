from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage298_stage78_1_risk_cluster_cap import RISK_CLUSTER_MAP


MODEL_TAG = "stage305_cash_buffer_multiperiod_validation_v1"
OUTPUT_PREFIX = "qmt_roll_stage305_cash_buffer_multiperiod_validation"
LINE_ID = "futures_trend_drawdown30_preserve_return"
CASH_WEIGHT = 0.85


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    overrides: dict[str, Any]


WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("full_2020_2026", "2020起点至今", START_DT, END_DT),
    ("since_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    ("since_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    ("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    ("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    ("since_2025", "2025起点至今", datetime(2025, 1, 1), END_DT),
    ("since_2026", "2026起点至今", datetime(2026, 1, 1), END_DT),
    ("phase_2020_2021", "2020-2021独立启动", datetime(2020, 1, 1), datetime(2021, 12, 31)),
    ("phase_2022_2023", "2022-2023独立启动", datetime(2022, 1, 1), datetime(2023, 12, 31)),
    ("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
    ("phase_2026_latest", "2026独立启动至最新", datetime(2026, 1, 1), END_DT),
)


def _pressure040_overrides() -> dict[str, Any]:
    return {
        "risk_cluster_map": RISK_CLUSTER_MAP,
        "enable_risk_cluster_heat_deleverage": True,
        "risk_cluster_heat_deleverage_target_clusters": "",
        "risk_cluster_heat_deleverage_layer_kinds": "base,add,donchian",
        "risk_cluster_heat_deleverage_min_pressure": 0.40,
        "risk_cluster_heat_gate_drawdown_start_pct": 0.10,
        "risk_cluster_heat_gate_drawdown_full_pct": 0.25,
        "risk_cluster_heat_gate_margin_start_ratio": 0.15,
        "risk_cluster_heat_gate_margin_full_ratio": 0.35,
        "risk_cluster_heat_gate_unrealized_loss_start_ratio": 0.02,
        "risk_cluster_heat_gate_unrealized_loss_full_ratio": 0.08,
    }


PROFILES: tuple[Profile, ...] = (
    Profile("A_baseline_78_1", "78-1正式基准", {}),
    Profile("C_pressure040", "热度降暴露0.40", _pressure040_overrides()),
)


def _path_metrics(equity: pd.Series, *, initial_capital: float = OFFICIAL_STAGE78_CAPITAL) -> dict[str, float]:
    arr = equity.to_numpy(dtype=float)
    high = np.maximum.accumulate(arr)
    drawdown = arr - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0) * 100.0
    returns = pd.Series(arr).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "end_equity": float(arr[-1]),
        "total_return_pct": float((arr[-1] / initial_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "max_drawdown": float(drawdown.min()),
        "sharpe_ratio": sharpe,
    }


def _profile_overrides(profile: Profile, analysis_start: datetime) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["trade_start_date"] = analysis_start.date().isoformat()
    overrides.update(profile.overrides)
    return overrides


def _run_profile(
    profile: Profile,
    window_name: str,
    display_label: str,
    analysis_start: datetime,
    analysis_end: datetime,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    _, analysis_df, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_profile_overrides(profile, analysis_start),
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        preload_start=preload_start,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{profile.name}_{window_name}",
        chart_title=f"Stage305 {profile.label} {display_label}",
    )
    return analysis_df, statistics


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, display_label, analysis_start, analysis_end in WINDOWS:
        for profile in PROFILES:
            print(f"[stage305] {window_name} {profile.name}", flush=True)
            analysis_df, statistics = _run_profile(profile, window_name, display_label, analysis_start, analysis_end)
            summary_rows.append(
                build_summary_row(
                    statistics,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    variant=profile.name,
                    display_label=profile.label,
                    window_name=window_name,
                    official_version=OFFICIAL_STAGE78_VERSION,
                    official_role=OFFICIAL_STAGE78_ROLE,
                    model_tag=MODEL_TAG,
                    capital=OFFICIAL_STAGE78_CAPITAL,
                    base_risk_ratio=BASE_RISK_RATIO,
                    total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                    total_slippage=float(statistics.get("total_slippage", 0) or 0),
                    total_commission=float(statistics.get("total_commission", 0) or 0),
                    profit_days=int(statistics.get("profit_days", 0) or 0),
                    loss_days=int(statistics.get("loss_days", 0) or 0),
                )
            )
            if analysis_df is not None and not analysis_df.empty:
                curve_df = analysis_df[["balance"]].reset_index().rename(columns={"index": "date"})
                curve_df["date"] = pd.to_datetime(curve_df["date"])
                curve_df["variant"] = profile.name
                curve_df["display_label"] = profile.label
                curve_df["window_name"] = window_name
                curve_frames.append(curve_df)
    return pd.DataFrame(summary_rows), pd.concat(curve_frames, ignore_index=True)


def _cash_buffer_comparison(summary_df: pd.DataFrame, curves_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary_df.groupby("window_name", sort=False):
        baseline = group[group["variant"].eq("A_baseline_78_1")]
        if baseline.empty:
            continue
        a = baseline.iloc[0]
        candidate_curve = curves_df[
            curves_df["window_name"].eq(window_name) & curves_df["variant"].eq("C_pressure040")
        ].copy()
        if candidate_curve.empty:
            continue
        candidate_curve = candidate_curve.sort_values("date").reset_index(drop=True)
        nav = candidate_curve["balance"] / OFFICIAL_STAGE78_CAPITAL
        buffered_equity = ((1.0 - CASH_WEIGHT) + CASH_WEIGHT * nav) * OFFICIAL_STAGE78_CAPITAL
        metrics = _path_metrics(buffered_equity)
        baseline_return = float(a["total_return_pct"])
        candidate_return = float(metrics["total_return_pct"])
        retention = candidate_return / baseline_return * 100.0 if baseline_return > 0 else 0.0
        dd_ok = float(metrics["max_dd_percent"]) >= -30.0
        return_ok = retention >= 80.0 if baseline_return > 0 else candidate_return >= baseline_return
        rows.append(
            {
                "window_name": window_name,
                "display_label": str(a["display_label"]),
                "baseline_return_pct": baseline_return,
                "candidate_return_pct": candidate_return,
                "return_retention_pct": retention,
                "baseline_max_dd_pct": float(a["max_dd_percent"]),
                "candidate_max_dd_pct": float(metrics["max_dd_percent"]),
                "max_dd_improvement_pct": float(metrics["max_dd_percent"]) - float(a["max_dd_percent"]),
                "baseline_sharpe": float(a["sharpe_ratio"]),
                "candidate_sharpe": float(metrics["sharpe_ratio"]),
                "cash_weight": CASH_WEIGHT,
                "cash_buffer_pct": (1.0 - CASH_WEIGHT) * 100.0,
                "dd_ok": int(dd_ok),
                "return_ok": int(return_ok),
                "strict_pass": int(dd_ok and return_ok),
            }
        )
    return pd.DataFrame(rows)


def _build_report(comparison_df: pd.DataFrame) -> str:
    lines = [
        "# Stage305 现金缓冲候选多周期验证",
        "",
        "## 目标",
        "",
        f"- 候选：热度降暴露0.40 + `{CASH_WEIGHT:.0%}`策略风险权重 + `{(1-CASH_WEIGHT):.0%}`现金缓冲。",
        "- 本阶段用真实回测引擎逐窗口重跑热度降暴露0.40，再做账户层现金缓冲。",
        "- 仍然不修改第78-1 alpha、AI池和入场逻辑。",
        "",
        "## 多周期结果",
        "",
        comparison_df[
            [
                "window_name",
                "baseline_return_pct",
                "candidate_return_pct",
                "return_retention_pct",
                "baseline_max_dd_pct",
                "candidate_max_dd_pct",
                "max_dd_improvement_pct",
                "candidate_sharpe",
                "strict_pass",
            ]
        ].to_markdown(index=False),
        "",
        "## 阶段判断",
        "",
    ]
    full = comparison_df[comparison_df["window_name"].eq("full_2020_2026")]
    if not full.empty and int(full.iloc[0]["strict_pass"]):
        lines.append("- 全样本通过：候选在账户层口径下进入30%以内，且收益保留超过80%。")
    else:
        lines.append("- 全样本未通过，不能作为候选。")
    weak = comparison_df[(comparison_df["baseline_return_pct"] > 0) & (comparison_df["strict_pass"].eq(0))]
    if weak.empty:
        lines.append("- 正收益起点窗口未出现“收益保留不足且回撤不过线”的反证。")
    else:
        lines.append("- 存在正收益起点窗口未通过，后续必须归因。")
    lines.append("- 注意：这是账户层候选，不是单策略内部神奇修复；实盘落地必须靠资金制度和日报账本执行。")
    return "\n".join(lines) + "\n"


def main() -> None:
    assert_stage196_database_sentinels()
    manifest = build_official_stage78_manifest()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df, curves_df = _run_suite()
    comparison_df = _cash_buffer_comparison(summary_df, curves_df)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    curves_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    comparison_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    curves_df.to_csv(curves_path, index=False, encoding="utf-8-sig")
    comparison_df.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(comparison_df), encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "manifest_reference": manifest,
        "cash_weight": CASH_WEIGHT,
        "cash_buffer_pct": (1.0 - CASH_WEIGHT) * 100.0,
        "full_window": comparison_df[comparison_df["window_name"].eq("full_2020_2026")].to_dict(orient="records"),
        "failed_positive_windows": comparison_df[
            (comparison_df["baseline_return_pct"] > 0) & (comparison_df["strict_pass"].eq(0))
        ].to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "curves": str(curves_path),
            "comparison": str(comparison_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage305] summary={summary_path}")
    print(f"[stage305] curves={curves_path}")
    print(f"[stage305] comparison={comparison_path}")
    print(f"[stage305] report={report_path}")
    print(f"[stage305] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

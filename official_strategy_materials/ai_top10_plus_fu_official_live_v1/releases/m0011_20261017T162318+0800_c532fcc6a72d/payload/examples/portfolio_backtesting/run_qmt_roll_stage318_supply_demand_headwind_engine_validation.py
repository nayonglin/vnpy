from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation import _pressure040_overrides


MODEL_TAG = "stage318_supply_demand_headwind_engine_validation_v1"
OUTPUT_PREFIX = "qmt_roll_stage318_supply_demand_headwind_engine_validation"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SUPPLY_DEMAND_SIGNAL_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage316_supply_demand_quality_probe_external_signals_stage316_supply_demand_quality_probe_v1.csv"
)


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    overrides: dict[str, Any]


WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("full_2020_2026", "2020起点至今", START_DT, END_DT),
    ("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    ("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    ("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
    ("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
)


def _supply_demand_headwind_overrides() -> dict[str, Any]:
    return {
        "enable_supply_demand_headwind_filter": True,
        "supply_demand_signal_path": str(SUPPLY_DEMAND_SIGNAL_PATH),
        "supply_demand_headwind_threshold": -0.35,
        "supply_demand_headwind_weight_floor": 0.0,
        "supply_demand_headwind_max_age_days": 7,
    }


def _merge(*items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        merged.update(item)
    return merged


PROFILES: tuple[Profile, ...] = (
    Profile("A_baseline_78_1", "78-1正式基准", {}),
    Profile("C_pressure040", "热度降暴露0.40", _pressure040_overrides()),
    Profile("C_supply_headwind", "供需强逆风过滤", _supply_demand_headwind_overrides()),
    Profile(
        "C_pressure040_supply_headwind",
        "热度降暴露0.40+供需强逆风过滤",
        _merge(_pressure040_overrides(), _supply_demand_headwind_overrides()),
    ),
)


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
        chart_title=f"Stage318 {profile.label} {display_label}",
    )
    return analysis_df, statistics


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, display_label, analysis_start, analysis_end in WINDOWS:
        for profile in PROFILES:
            print(f"[stage318] {window_name} {profile.name}", flush=True)
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
                first_balance = float(curve_df["balance"].iloc[0] or OFFICIAL_STAGE78_CAPITAL)
                curve_df["normalized_nav"] = curve_df["balance"] / max(1e-9, first_balance)
                curve_frames.append(curve_df)
    summary_df = pd.DataFrame(summary_rows)
    curves_df = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    return summary_df, curves_df


def _comparison(summary_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary_df.groupby("window_name", sort=False):
        formal = group[group["variant"].eq("A_baseline_78_1")]
        pressure = group[group["variant"].eq("C_pressure040")]
        if formal.empty:
            continue
        a = formal.iloc[0]
        p = pressure.iloc[0] if not pressure.empty else a
        formal_return = float(a["total_return_pct"])
        pressure_return = float(p["total_return_pct"])
        pressure_sharpe = float(p["sharpe_ratio"])
        for _, c in group.iterrows():
            candidate_return = float(c["total_return_pct"])
            formal_retention = candidate_return / formal_return * 100.0 if formal_return > 0 else 0.0
            pressure_retention = candidate_return / pressure_return * 100.0 if pressure_return > 0 else 0.0
            dd_ok = float(c["max_dd_percent"]) >= -30.0
            rows.append(
                {
                    "window_name": window_name,
                    "variant": c["variant"],
                    "display_label": c["display_label"],
                    "formal_return_pct": formal_return,
                    "pressure040_return_pct": pressure_return,
                    "candidate_return_pct": candidate_return,
                    "return_retention_vs_formal_pct": formal_retention,
                    "return_retention_vs_pressure040_pct": pressure_retention,
                    "formal_max_dd_pct": float(a["max_dd_percent"]),
                    "pressure040_max_dd_pct": float(p["max_dd_percent"]),
                    "candidate_max_dd_pct": float(c["max_dd_percent"]),
                    "max_dd_improvement_vs_pressure040_pct": float(c["max_dd_percent"]) - float(p["max_dd_percent"]),
                    "pressure040_sharpe": pressure_sharpe,
                    "candidate_sharpe": float(c["sharpe_ratio"]),
                    "candidate_trades": int(c["total_trade_count"]),
                    "candidate_slippage": float(c["total_slippage"]),
                    "candidate_win_rate": float(c.get("win_ratio_pct", 0.0) or 0.0),
                    "dd_ok": int(dd_ok),
                    "return_ok_vs_pressure040": int(pressure_retention >= 80.0),
                    "strict_pass": int(dd_ok and pressure_retention >= 80.0),
                    "research_pass": int(dd_ok and pressure_retention >= 65.0 and float(c["sharpe_ratio"]) >= pressure_sharpe),
                }
            )
    return pd.DataFrame(rows)


def _build_report(summary_df: pd.DataFrame, comparison_df: pd.DataFrame) -> str:
    full_cmp = comparison_df[comparison_df["window_name"].eq("full_2020_2026")].copy()
    full_cmp = full_cmp.sort_values(
        ["strict_pass", "research_pass", "candidate_max_dd_pct", "return_retention_vs_pressure040_pct"],
        ascending=[False, False, False, False],
    )
    multi = (
        comparison_df[comparison_df["variant"].ne("A_baseline_78_1")]
        .groupby("variant", as_index=False)
        .agg(
            strict_pass_count=("strict_pass", "sum"),
            research_pass_count=("research_pass", "sum"),
            min_return_retention_vs_pressure040_pct=("return_retention_vs_pressure040_pct", "min"),
            worst_max_dd_pct=("candidate_max_dd_pct", "min"),
            median_sharpe=("candidate_sharpe", "median"),
        )
        .sort_values(
            ["strict_pass_count", "research_pass_count", "worst_max_dd_pct", "min_return_retention_vs_pressure040_pct"],
            ascending=[False, False, False, False],
        )
    )
    lines = [
        "# Stage318 供需强逆风过滤真实引擎验证",
        "",
        "## 目标",
        "",
        "- A：78-1正式基准。",
        "- C1：Stage012以来最强内部风控线索 `C_pressure040`。",
        "- C2：只加供需强逆风过滤。",
        "- C3：`C_pressure040` 加供需强逆风过滤，作为本阶段真正候选。",
        "- 预注册过滤：方向对应供需分 `<= -0.35` 时，新增开仓手数降为0；不调权重、不做品种黑名单。",
        "",
        "## 全样本对比",
        "",
        to_markdown_table(
            full_cmp[
                [
                    "variant",
                    "candidate_return_pct",
                    "return_retention_vs_pressure040_pct",
                    "candidate_max_dd_pct",
                    "max_dd_improvement_vs_pressure040_pct",
                    "candidate_sharpe",
                    "candidate_trades",
                    "strict_pass",
                    "research_pass",
                ]
            ]
        ),
        "",
        "## 多周期汇总",
        "",
        to_markdown_table(multi),
        "",
        "## 窗口结果",
        "",
        to_markdown_table(
            summary_df[
                [
                    "variant",
                    "window_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                    "total_slippage",
                    "win_ratio_pct",
                ]
            ]
        ),
        "",
        "## 判定",
        "",
    ]
    best = full_cmp[full_cmp["variant"].eq("C_pressure040_supply_headwind")]
    if best.empty:
        lines.append("- 缺少 C3 结果，不能判定。")
    else:
        row = best.iloc[0]
        if int(row["strict_pass"]):
            lines.append("- C3 全样本严格通过，下一步做起始年份、季度冷启动和滑点压力。")
        elif int(row["research_pass"]):
            lines.append("- C3 达到研究通过，但未达到严格通过，下一步只做稳健性反证，不直接合入。")
        else:
            lines.append("- C3 不通过，不合入78-1；供需强逆风最多保留为监控标签。")
    return "\n".join(lines) + "\n"


def main() -> None:
    assert_stage196_database_sentinels()
    if not SUPPLY_DEMAND_SIGNAL_PATH.exists():
        raise FileNotFoundError(SUPPLY_DEMAND_SIGNAL_PATH)
    manifest = build_official_stage78_manifest()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_df, curves_df = _run_suite()
    comparison_df = _comparison(summary_df)
    report = _build_report(summary_df, comparison_df)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    curves_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    comparison_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    curves_df.to_csv(curves_path, index=False, encoding="utf-8-sig")
    comparison_df.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    report_path.write_text(report, encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "manifest": manifest,
        "supply_demand_signal_path": str(SUPPLY_DEMAND_SIGNAL_PATH),
        "profiles": [
            {
                "name": profile.name,
                "label": profile.label,
                "overrides": profile.overrides,
            }
            for profile in PROFILES
        ],
        "windows": [
            {
                "name": name,
                "label": label,
                "start": start.date().isoformat(),
                "end": end.date().isoformat(),
            }
            for name, label, start, end in WINDOWS
        ],
        "paths": {
            "summary": str(summary_path),
            "curves": str(curves_path),
            "comparison": str(comparison_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    print(report)
    print(json.dumps(decision["paths"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
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
from run_qmt_roll_stage298_stage78_1_risk_cluster_cap import _cluster_cap_overrides
from run_qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation import _pressure040_overrides
from run_qmt_roll_stage318_supply_demand_headwind_engine_validation import _supply_demand_headwind_overrides


MODEL_TAG = "stage321_c3_black_cluster_cap_validation_v1"
OUTPUT_PREFIX = "qmt_roll_stage321_c3_black_cluster_cap_validation"
LINE_ID = "futures_trend_drawdown30_preserve_return"


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


def _merge(*items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        merged.update(item)
    return merged


C3_OVERRIDES = _merge(_pressure040_overrides(), _supply_demand_headwind_overrides())


PROFILES: tuple[Profile, ...] = (
    Profile("C_pressure040", "热度降暴露0.40", _pressure040_overrides()),
    Profile("C3_supply_headwind", "热度0.40+供需强逆风", C3_OVERRIDES),
    Profile(
        "C3_black_cluster_cap35",
        "C3+黑色建材簇35%上限",
        _merge(C3_OVERRIDES, _cluster_cap_overrides(0.35, "黑色建材")),
    ),
    Profile(
        "C3_black_cluster_cap25",
        "C3+黑色建材簇25%上限",
        _merge(C3_OVERRIDES, _cluster_cap_overrides(0.25, "黑色建材")),
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
        chart_title=f"Stage321 {profile.label} {display_label}",
    )
    return analysis_df, statistics


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, display_label, analysis_start, analysis_end in WINDOWS:
        for profile in PROFILES:
            print(f"[stage321] {window_name} {profile.name}", flush=True)
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
        pressure = group[group["variant"].eq("C_pressure040")]
        c3 = group[group["variant"].eq("C3_supply_headwind")]
        if pressure.empty or c3.empty:
            continue
        p = pressure.iloc[0]
        c3_row = c3.iloc[0]
        pressure_return = float(p["total_return_pct"])
        c3_return = float(c3_row["total_return_pct"])
        for _, row in group.iterrows():
            candidate_return = float(row["total_return_pct"])
            pressure_retention = candidate_return / pressure_return * 100.0 if pressure_return > 0 else 0.0
            c3_retention = candidate_return / c3_return * 100.0 if c3_return > 0 else 0.0
            dd_ok = float(row["max_dd_percent"]) > -30.0
            rows.append(
                {
                    "window_name": window_name,
                    "variant": row["variant"],
                    "display_label": row["display_label"],
                    "pressure040_return_pct": pressure_return,
                    "c3_return_pct": c3_return,
                    "candidate_return_pct": candidate_return,
                    "return_retention_vs_pressure040_pct": pressure_retention,
                    "return_retention_vs_c3_pct": c3_retention,
                    "pressure040_max_dd_pct": float(p["max_dd_percent"]),
                    "c3_max_dd_pct": float(c3_row["max_dd_percent"]),
                    "candidate_max_dd_pct": float(row["max_dd_percent"]),
                    "candidate_sharpe": float(row["sharpe_ratio"]),
                    "candidate_trades": int(row["total_trade_count"]),
                    "candidate_slippage": float(row["total_slippage"]),
                    "candidate_win_ratio_pct": float(row.get("win_ratio_pct", 0.0) or 0.0),
                    "dd_ok": int(dd_ok),
                    "return_ok_vs_pressure040": int(pressure_retention >= 100.0),
                    "return_ok_vs_c3_80": int(c3_retention >= 80.0),
                    "strict_pass": int(dd_ok and pressure_retention >= 100.0 and c3_retention >= 80.0),
                    "research_pass": int(dd_ok and pressure_retention >= 95.0 and c3_retention >= 70.0),
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
        comparison_df[comparison_df["variant"].str.contains("black_cluster", regex=False)]
        .groupby("variant", as_index=False)
        .agg(
            strict_pass_count=("strict_pass", "sum"),
            research_pass_count=("research_pass", "sum"),
            min_return_retention_vs_pressure040_pct=("return_retention_vs_pressure040_pct", "min"),
            min_return_retention_vs_c3_pct=("return_retention_vs_c3_pct", "min"),
            worst_max_dd_pct=("candidate_max_dd_pct", "min"),
            median_sharpe=("candidate_sharpe", "median"),
        )
        .sort_values(
            ["strict_pass_count", "research_pass_count", "worst_max_dd_pct", "min_return_retention_vs_pressure040_pct"],
            ascending=[False, False, False, False],
        )
    )
    lines = [
        "# Stage321 C3叠加黑色建材簇上限验证",
        "",
        "## 目标",
        "",
        "- Stage320 归因显示 2021 最大回撤主要来自黑色建材簇同步失血。",
        "- 本阶段只测试 `C3 + 黑色建材簇保证金上限35%/25%`，不做单品种黑名单，不改入场阈值。",
        "- 严格通过：全样本最大回撤进入30%以内，收益不低于 `C_pressure040`，且保留 C3 至少80%收益。",
        "",
        "## 全样本对比",
        "",
        to_markdown_table(
            full_cmp[
                [
                    "variant",
                    "candidate_return_pct",
                    "return_retention_vs_pressure040_pct",
                    "return_retention_vs_c3_pct",
                    "candidate_max_dd_pct",
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
    full_candidates = full_cmp[full_cmp["variant"].str.contains("black_cluster", regex=False)]
    passed = full_candidates[full_candidates["strict_pass"].eq(1)]
    if not passed.empty:
        best = passed.iloc[0]
        lines.append(
            f"- `{best['variant']}` 全样本严格通过；下一步做起始年份、季度冷启动、弱窗口和滑点压力，不直接合入。"
        )
    else:
        lines.append("- 黑色建材簇上限候选未在全样本严格通过；不进入后续稳健性。")
    return "\n".join(lines) + "\n"


def main() -> None:
    assert_stage196_database_sentinels()
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

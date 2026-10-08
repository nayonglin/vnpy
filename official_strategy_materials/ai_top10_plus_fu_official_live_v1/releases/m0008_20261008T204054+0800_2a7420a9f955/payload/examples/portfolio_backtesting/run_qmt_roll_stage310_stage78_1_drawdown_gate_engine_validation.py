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
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage298_stage78_1_risk_cluster_cap import RISK_CLUSTER_MAP


MODEL_TAG = "stage310_stage78_1_drawdown_gate_engine_validation_v1"
OUTPUT_PREFIX = "qmt_roll_stage310_stage78_1_drawdown_gate_engine_validation"
LINE_ID = "futures_trend_drawdown30_preserve_return"

DRAWDOWN_GATE_10_30_850: dict[str, Any] = {
    "enable_portfolio_drawdown_gate": True,
    "portfolio_drawdown_gate_start_pct": 0.10,
    "portfolio_drawdown_gate_full_pct": 0.30,
    "portfolio_drawdown_gate_weight_floor": 0.85,
}

ALL_ENTRY_CONTEXTS = "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add"


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    overrides: dict[str, Any]


WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("full_2020_2026", "2020起点至今", START_DT, END_DT),
    ("since_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    ("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    ("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    ("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
    ("phase_2022_2023", "2022-2023独立启动", datetime(2022, 1, 1), datetime(2023, 12, 31)),
    ("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
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


def _drawdown_gate_overrides(entry_contexts: str) -> dict[str, Any]:
    overrides = dict(DRAWDOWN_GATE_10_30_850)
    overrides["portfolio_drawdown_gate_entry_contexts"] = entry_contexts
    return overrides


def _merge(*items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        merged.update(item)
    return merged


PROFILES: tuple[Profile, ...] = (
    Profile("A_baseline_78_1", "78-1正式基准", {}),
    Profile("C_pressure040", "热度降暴露0.40", _pressure040_overrides()),
    Profile(
        "C_pressure040_ddgate_flat",
        "热度降暴露0.40+回撤门禁仅空仓新开",
        _merge(_pressure040_overrides(), _drawdown_gate_overrides("flat_entry")),
    ),
    Profile(
        "C_pressure040_ddgate_all_entries",
        "热度降暴露0.40+回撤门禁覆盖全部开仓上下文",
        _merge(_pressure040_overrides(), _drawdown_gate_overrides(ALL_ENTRY_CONTEXTS)),
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
        chart_title=f"Stage310 {profile.label} {display_label}",
    )
    return analysis_df, statistics


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, display_label, analysis_start, analysis_end in WINDOWS:
        for profile in PROFILES:
            print(f"[stage310] {window_name} {profile.name}", flush=True)
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
        baseline = group[group["variant"].eq("A_baseline_78_1")]
        if baseline.empty:
            continue
        a = baseline.iloc[0]
        baseline_return = float(a["total_return_pct"])
        baseline_sharpe = float(a["sharpe_ratio"])
        for _, c in group[~group["variant"].eq("A_baseline_78_1")].iterrows():
            candidate_return = float(c["total_return_pct"])
            if baseline_return > 0:
                retention = candidate_return / baseline_return * 100.0
                return_ok = retention >= 80.0
            else:
                retention = 0.0
                return_ok = candidate_return >= baseline_return
            dd_ok = float(c["max_dd_percent"]) >= -30.0
            rows.append(
                {
                    "window_name": window_name,
                    "variant": c["variant"],
                    "display_label": c["display_label"],
                    "baseline_return_pct": baseline_return,
                    "candidate_return_pct": candidate_return,
                    "return_retention_pct": retention,
                    "baseline_max_dd_pct": float(a["max_dd_percent"]),
                    "candidate_max_dd_pct": float(c["max_dd_percent"]),
                    "max_dd_improvement_pct": float(c["max_dd_percent"]) - float(a["max_dd_percent"]),
                    "baseline_sharpe": baseline_sharpe,
                    "candidate_sharpe": float(c["sharpe_ratio"]),
                    "baseline_trades": int(a["total_trade_count"]),
                    "candidate_trades": int(c["total_trade_count"]),
                    "dd_ok": int(dd_ok),
                    "return_ok": int(return_ok),
                    "strict_pass": int(dd_ok and return_ok),
                    "research_pass": int(dd_ok and (return_ok or float(c["sharpe_ratio"]) >= baseline_sharpe)),
                }
            )
    return pd.DataFrame(rows)


def _build_report(comparison_df: pd.DataFrame) -> str:
    full_cmp = comparison_df[comparison_df["window_name"].eq("full_2020_2026")].copy()
    full_cmp = full_cmp.sort_values(
        ["strict_pass", "research_pass", "candidate_max_dd_pct", "return_retention_pct"],
        ascending=[False, False, False, False],
    )
    multi = (
        comparison_df.groupby("variant", as_index=False)
        .agg(
            strict_pass_count=("strict_pass", "sum"),
            research_pass_count=("research_pass", "sum"),
            min_return_retention_pct=("return_retention_pct", "min"),
            max_drawdown_floor_pct=("candidate_max_dd_pct", "min"),
            median_sharpe=("candidate_sharpe", "median"),
        )
        .sort_values(
            ["strict_pass_count", "research_pass_count", "max_drawdown_floor_pct", "min_return_retention_pct"],
            ascending=[False, False, False, False],
        )
    )
    lines = [
        "# Stage310 动态回撤门禁真实引擎验证",
        "",
        "## 目标",
        "",
        "- A：78-1正式基准。",
        "- C：不改alpha和品种池，只验证风险覆盖层是否能把最大回撤压到30%以内，同时不显著牺牲收益。",
        "- 本阶段不做小数扫参；沿用前一阶段预声明的回撤门禁：10%开始降暴露、30%达到最低85%权重。",
        "",
        "## 全样本对比",
        "",
        full_cmp[
            [
                "variant",
                "candidate_return_pct",
                "return_retention_pct",
                "candidate_max_dd_pct",
                "max_dd_improvement_pct",
                "candidate_sharpe",
                "candidate_trades",
                "strict_pass",
            ]
        ].to_markdown(index=False),
        "",
        "## 多周期汇总",
        "",
        multi.to_markdown(index=False),
        "",
        "## 阶段判断",
        "",
    ]
    promoted = full_cmp[full_cmp["strict_pass"].eq(1)]
    if promoted.empty:
        lines.append("- 没有真实引擎候选同时满足全样本回撤30%以内和收益保留80%。")
    else:
        best = promoted.iloc[0]
        lines.append(
            f"- 全样本出现严格候选：`{best['variant']}`，"
            f"收益保留 {best['return_retention_pct']:.2f}%，"
            f"最大回撤 {best['candidate_max_dd_pct']:.2f}%。"
        )
    lines.append("- 如果真实引擎候选不过关，说明离线权益叠加层不能直接等同于可交易规则，需要回到持仓路径层面继续找风险来源。")
    return "\n".join(lines) + "\n"


def main() -> None:
    assert_stage196_database_sentinels()
    manifest = build_official_stage78_manifest()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_df, curves_df = _run_suite()
    comparison_df = _comparison(summary_df)
    report = _build_report(comparison_df)

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

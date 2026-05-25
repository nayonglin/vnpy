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
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage295_stage78_1_drawdown_entry_brake_v1"
OUTPUT_PREFIX = "qmt_roll_stage295_stage78_1_drawdown_entry_brake"
LINE_ID = "futures_trend_drawdown30_preserve_return"


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    overrides: dict[str, Any]


WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("full_2020_2026", "2020起点至今", START_DT, END_DT),
    ("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
)


PROFILES: tuple[Profile, ...] = (
    Profile("A_baseline_78_1", "78-1正式基准", {}),
    Profile(
        "C_dd_entry_brake_20_35_floor0",
        "回撤20%-35%只刹新增开仓",
        {
            "enable_portfolio_drawdown_gate": True,
            "portfolio_drawdown_gate_start_pct": 0.20,
            "portfolio_drawdown_gate_full_pct": 0.35,
            "portfolio_drawdown_gate_weight_floor": 0.0,
        },
    ),
    Profile(
        "C_dd_entry_brake_15_30_floor0",
        "回撤15%-30%只刹新增开仓",
        {
            "enable_portfolio_drawdown_gate": True,
            "portfolio_drawdown_gate_start_pct": 0.15,
            "portfolio_drawdown_gate_full_pct": 0.30,
            "portfolio_drawdown_gate_weight_floor": 0.0,
        },
    ),
    Profile(
        "C_dd_entry_brake_20_35_floor25",
        "回撤20%-35%新增开仓保留25%地板",
        {
            "enable_portfolio_drawdown_gate": True,
            "portfolio_drawdown_gate_start_pct": 0.20,
            "portfolio_drawdown_gate_full_pct": 0.35,
            "portfolio_drawdown_gate_weight_floor": 0.25,
        },
    ),
    Profile(
        "C_dd_entry_brake_20_35_rollover30",
        "深回撤新增开仓刹车 + 30%后禁止换月重开",
        {
            "enable_portfolio_drawdown_gate": True,
            "portfolio_drawdown_gate_start_pct": 0.20,
            "portfolio_drawdown_gate_full_pct": 0.35,
            "portfolio_drawdown_gate_weight_floor": 0.0,
            "enable_rollover_reopen_drawdown_guard": True,
            "rollover_reopen_max_portfolio_drawdown_pct": 0.30,
        },
    ),
)


def _profile_overrides(profile: Profile, analysis_start: datetime) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["trade_start_date"] = analysis_start.date().isoformat()
    overrides.update(profile.overrides)
    return overrides


def _run_profile(profile: Profile, window_name: str, display_label: str, analysis_start: datetime, analysis_end: datetime) -> tuple[pd.DataFrame, dict[str, Any]]:
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
        chart_title=f"Stage295 {profile.label} {display_label}",
    )
    return analysis_df, statistics


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    for window_name, display_label, analysis_start, analysis_end in WINDOWS:
        for profile in PROFILES:
            print(f"[stage295] {window_name} {profile.name}", flush=True)
            analysis_df, statistics = _run_profile(profile, window_name, display_label, analysis_start, analysis_end)
            rows.append(
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
                curve = analysis_df[["balance"]].reset_index().rename(columns={"index": "date"})
                curve["date"] = pd.to_datetime(curve["date"])
                curve["variant"] = profile.name
                curve["display_label"] = profile.label
                curve["window_name"] = window_name
                first_balance = float(curve["balance"].iloc[0] or OFFICIAL_STAGE78_CAPITAL)
                curve["normalized_nav"] = curve["balance"] / max(1e-9, first_balance)
                curves.append(curve)
    return pd.DataFrame(rows), pd.concat(curves, ignore_index=True) if curves else pd.DataFrame()


def _comparison(summary_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary_df.groupby("window_name", sort=False):
        base = group[group["variant"].eq("A_baseline_78_1")]
        if base.empty:
            continue
        a = base.iloc[0]
        baseline_return = float(a["total_return_pct"])
        for _, c in group[~group["variant"].eq("A_baseline_78_1")].iterrows():
            retention = float(c["total_return_pct"]) / baseline_return if baseline_return > 0 else 0.0
            dd_ok = float(c["max_dd_percent"]) >= -30.0
            rows.append(
                {
                    "window_name": window_name,
                    "variant": c["variant"],
                    "display_label": c["display_label"],
                    "baseline_return_pct": baseline_return,
                    "candidate_return_pct": float(c["total_return_pct"]),
                    "return_retention_pct": retention * 100.0,
                    "baseline_max_dd_pct": float(a["max_dd_percent"]),
                    "candidate_max_dd_pct": float(c["max_dd_percent"]),
                    "max_dd_improvement_pct": float(c["max_dd_percent"]) - float(a["max_dd_percent"]),
                    "baseline_sharpe": float(a["sharpe_ratio"]),
                    "candidate_sharpe": float(c["sharpe_ratio"]),
                    "baseline_trades": int(a["total_trade_count"]),
                    "candidate_trades": int(c["total_trade_count"]),
                    "strict_pass": int(dd_ok and retention >= 0.80),
                    "research_pass": int(dd_ok and retention >= 0.65 and float(c["sharpe_ratio"]) >= float(a["sharpe_ratio"])),
                }
            )
    return pd.DataFrame(rows)


def _build_report(summary_df: pd.DataFrame, comparison_df: pd.DataFrame) -> str:
    full_cmp = comparison_df[comparison_df["window_name"].eq("full_2020_2026")].copy()
    full_cmp = full_cmp.sort_values(
        ["strict_pass", "research_pass", "candidate_max_dd_pct", "return_retention_pct"],
        ascending=[False, False, False, False],
    )
    strict_count = int((full_cmp["strict_pass"] == 1).sum()) if not full_cmp.empty else 0
    research_count = int((full_cmp["research_pass"] == 1).sum()) if not full_cmp.empty else 0
    lines = [
        "# Stage295 第78-1深回撤新增开仓刹车验证",
        "",
        "## 口径",
        "",
        "- 基于Stage294最大回撤归因：回撤期新增开仓集中发生在组合已回撤20%-35%区间。",
        "- 本轮只限制新开仓，不主动砍已有持仓；目标是避免回撤后继续加风险，同时尽量保留恢复能力。",
        "",
        "## 全样本候选排序",
        "",
        full_cmp[
            [
                "variant",
                "display_label",
                "candidate_return_pct",
                "return_retention_pct",
                "candidate_max_dd_pct",
                "max_dd_improvement_pct",
                "candidate_sharpe",
                "strict_pass",
                "research_pass",
            ]
        ].to_markdown(index=False),
        "",
        "## 窗口结果",
        "",
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
            ]
        ].to_markdown(index=False),
        "",
        "## 阶段判断",
        "",
    ]
    if strict_count:
        lines.append("- 出现严格通过候选，下一步扩展多周期和滑点压力。")
    elif research_count:
        lines.append("- 出现研究通过候选，下一步做多周期确认和交易归因。")
    else:
        lines.append("- 未出现通过候选；如果仍要压到30以内，不能只靠回撤后新仓刹车。")
    return "\n".join(lines) + "\n"


def main() -> None:
    assert_stage196_database_sentinels()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_official_stage78_manifest()
    summary_df, curves_df = _run_suite()
    comparison_df = _comparison(summary_df)
    paths = {
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "comparison": OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv",
        "curves": OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
    }
    summary_df.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    comparison_df.to_csv(paths["comparison"], index=False, encoding="utf-8-sig")
    curves_df.to_csv(paths["curves"], index=False, encoding="utf-8-sig")
    paths["report"].write_text(_build_report(summary_df, comparison_df), encoding="utf-8")
    full_cmp = comparison_df[comparison_df["window_name"].eq("full_2020_2026")].copy()
    best_dd = full_cmp.sort_values(["candidate_max_dd_pct", "return_retention_pct"], ascending=[False, False]).head(1)
    best_return = full_cmp.sort_values(["return_retention_pct", "candidate_max_dd_pct"], ascending=[False, False]).head(1)
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "strict_pass_count": int((full_cmp["strict_pass"] == 1).sum()) if not full_cmp.empty else 0,
        "research_pass_count": int((full_cmp["research_pass"] == 1).sum()) if not full_cmp.empty else 0,
        "best_drawdown_candidate": best_dd.to_dict("records"),
        "best_return_candidate": best_return.to_dict("records"),
        "profiles": [
            {"name": profile.name, "label": profile.label, "overrides": profile.overrides}
            for profile in PROFILES
        ],
        "manifest": manifest,
        "paths": {key: str(path.resolve()) for key, path in paths.items()},
    }
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

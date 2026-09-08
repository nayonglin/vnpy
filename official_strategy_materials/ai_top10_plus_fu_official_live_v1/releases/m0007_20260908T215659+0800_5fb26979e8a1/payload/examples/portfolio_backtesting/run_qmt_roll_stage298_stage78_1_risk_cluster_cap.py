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


MODEL_TAG = "stage298_stage78_1_risk_cluster_cap_v1"
OUTPUT_PREFIX = "qmt_roll_stage298_stage78_1_risk_cluster_cap"
LINE_ID = "futures_trend_drawdown30_preserve_return"


RISK_CLUSTER_MAP = ",".join(
    [
        "AP.CZCE=农业软商品",
        "CF.CZCE=农业软商品",
        "OI.CZCE=农业软商品",
        "lc.GFEX=畜牧养殖",
        "lh.DCE=畜牧养殖",
        "au.SHFE=贵金属",
        "cu.SHFE=有色工业",
        "si.GFEX=有色工业",
        "rb.SHFE=黑色建材",
        "hc.SHFE=黑色建材",
        "jm.DCE=黑色建材",
        "SM.CZCE=黑色建材",
        "sm.CZCE=黑色建材",
        "FG.CZCE=黑色建材",
        "fg.CZCE=黑色建材",
        "SA.CZCE=黑色建材",
        "sa.CZCE=黑色建材",
        "SH.CZCE=黑色建材",
        "sh.CZCE=黑色建材",
        "MA.CZCE=能化工业",
        "ma.CZCE=能化工业",
        "fu.SHFE=能化工业",
        "ru.SHFE=能化工业",
        "sp.SHFE=能化工业",
    ]
)


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    overrides: dict[str, Any]


WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("full_2020_2026", "2020起点至今", START_DT, END_DT),
    ("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
)


def _cluster_cap_overrides(ratio: float, target_clusters: str = "") -> dict[str, Any]:
    return {
        "enable_risk_cluster_margin_cap": True,
        "risk_cluster_margin_cap_ratio": ratio,
        "risk_cluster_target_clusters": target_clusters,
        "risk_cluster_map": RISK_CLUSTER_MAP,
    }


PROFILES: tuple[Profile, ...] = (
    Profile("A_baseline_78_1", "78-1正式基准", {}),
    Profile(
        "C_energy_cluster_cap35",
        "能化工业风险簇上限35%",
        _cluster_cap_overrides(0.35, "能化工业"),
    ),
    Profile(
        "C_energy_cluster_cap25",
        "能化工业风险簇上限25%",
        _cluster_cap_overrides(0.25, "能化工业"),
    ),
    Profile(
        "C_energy_cluster_cap20",
        "能化工业风险簇上限20%",
        _cluster_cap_overrides(0.20, "能化工业"),
    ),
    Profile(
        "C_all_cluster_cap35",
        "所有风险簇上限35%",
        _cluster_cap_overrides(0.35, ""),
    ),
    Profile(
        "C_all_cluster_cap25",
        "所有风险簇上限25%",
        _cluster_cap_overrides(0.25, ""),
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
        chart_title=f"Stage298 {profile.label} {display_label}",
    )
    return analysis_df, statistics


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, display_label, analysis_start, analysis_end in WINDOWS:
        for profile in PROFILES:
            print(f"[stage298] {window_name} {profile.name}", flush=True)
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
            retention = candidate_return / baseline_return if baseline_return > 0 else 0.0
            dd_ok = float(c["max_dd_percent"]) >= -30.0
            strict_pass = bool(dd_ok and retention >= 0.80)
            research_pass = bool(dd_ok and retention >= 0.65 and float(c["sharpe_ratio"]) >= baseline_sharpe)
            rows.append(
                {
                    "window_name": window_name,
                    "variant": c["variant"],
                    "display_label": c["display_label"],
                    "baseline_return_pct": baseline_return,
                    "candidate_return_pct": candidate_return,
                    "return_retention_pct": retention * 100.0,
                    "baseline_max_dd_pct": float(a["max_dd_percent"]),
                    "candidate_max_dd_pct": float(c["max_dd_percent"]),
                    "max_dd_improvement_pct": float(c["max_dd_percent"]) - float(a["max_dd_percent"]),
                    "baseline_sharpe": baseline_sharpe,
                    "candidate_sharpe": float(c["sharpe_ratio"]),
                    "baseline_trades": int(a["total_trade_count"]),
                    "candidate_trades": int(c["total_trade_count"]),
                    "strict_pass": int(strict_pass),
                    "research_pass": int(research_pass),
                }
            )
    return pd.DataFrame(rows)


def _build_report(summary_df: pd.DataFrame, comparison_df: pd.DataFrame) -> str:
    full_cmp = comparison_df[comparison_df["window_name"].eq("full_2020_2026")].copy()
    full_cmp = full_cmp.sort_values(
        ["strict_pass", "research_pass", "candidate_max_dd_pct", "return_retention_pct"],
        ascending=[False, False, False, False],
    )
    ytd_cmp = comparison_df[comparison_df["window_name"].eq("ytd_2026")].copy()
    lines = [
        "# Stage298 第78-1风险簇暴露上限A/C验证",
        "",
        "## 目标",
        "",
        "- A：第78-1正式基准。",
        "- C：只增加风险簇保证金占用上限，不修改入场、出场、AI池，不做单品种黑名单。",
        "- 严格通过：全样本最大回撤小于30%，收益保留不低于80%。",
        "- 研究通过：全样本最大回撤小于30%，收益保留不低于65%，Sharpe不低于A。",
        "",
        "## 全样本候选",
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
                "candidate_trades",
                "strict_pass",
                "research_pass",
            ]
        ].to_markdown(index=False),
        "",
        "## 2026年初至今窗口",
        "",
        ytd_cmp[
            [
                "variant",
                "display_label",
                "candidate_return_pct",
                "return_retention_pct",
                "candidate_max_dd_pct",
                "max_dd_improvement_pct",
                "candidate_sharpe",
                "candidate_trades",
            ]
        ].to_markdown(index=False),
        "",
        "## 阶段判断",
        "",
    ]
    strict_count = int(full_cmp["strict_pass"].sum()) if not full_cmp.empty else 0
    research_count = int(full_cmp["research_pass"].sum()) if not full_cmp.empty else 0
    if strict_count:
        lines.append("- 出现严格通过候选，需要进入起始年份、季度冷启动、弱窗口和滑点压力验证。")
    elif research_count:
        lines.append("- 出现研究通过候选，需要继续做稳健性验证，暂不能推广。")
    else:
        lines.append("- 全样本没有候选同时满足回撤30以内和收益保留要求。")
    lines.append("- 如果风险簇上限只能牺牲复利换回撤，说明第78-1当前收益-回撤前沿仍然较硬。")
    return "\n".join(lines) + "\n"


def main() -> None:
    assert_stage196_database_sentinels()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "manifest_reference": build_official_stage78_manifest(),
        "strict_pass_count": int(full_cmp["strict_pass"].sum()) if not full_cmp.empty else 0,
        "research_pass_count": int(full_cmp["research_pass"].sum()) if not full_cmp.empty else 0,
        "best_by_drawdown": full_cmp.sort_values("candidate_max_dd_pct", ascending=False).head(3).to_dict("records"),
        "best_by_retention": full_cmp.sort_values("return_retention_pct", ascending=False).head(3).to_dict("records"),
        "paths": {key: str(path.resolve()) for key, path in paths.items()},
    }
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

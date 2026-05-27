from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    TOTAL_CAPITAL,
    _c3_overrides,
    _safe_float,
    _to_builtin,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR, build_trades_df
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage363_c3_same_direction_multi_snapshot_validation_v1"
OUTPUT_PREFIX = "qmt_roll_stage363_c3_same_direction_multi_snapshot_validation"
LINE_ID = "futures_trend_drawdown30_preserve_return"


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    overrides: dict[str, Any]


PROFILES: tuple[Profile, ...] = (
    Profile("A_c3_supply_headwind", "C3：当前热度降暴露+供需强逆风", {}),
    Profile(
        "C_same_direction_multi_snapshot",
        "C3：同簇同向多品种时使用热度快照",
        {
            "risk_cluster_heat_deleverage_use_daily_snapshot": True,
            "risk_cluster_heat_deleverage_snapshot_requires_same_direction_multi": True,
        },
    ),
)


def _strategy_overrides(profile: Profile, analysis_start: datetime) -> dict[str, Any]:
    overrides = _c3_overrides(analysis_start)
    overrides.update(profile.overrides)
    return overrides


def _daily_from_analysis(analysis_df: pd.DataFrame | None) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame(columns=["date", "balance"])
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["balance"] = pd.to_numeric(frame.get("balance", TOTAL_CAPITAL), errors="coerce").ffill().fillna(
        TOTAL_CAPITAL
    )
    return frame[["date", "balance"]].sort_values("date").reset_index(drop=True)


def _drawdown_window(daily: pd.DataFrame) -> dict[str, Any]:
    if daily.empty:
        return {"peak_date": "", "trough_date": "", "max_dd_percent": 0.0}
    curve = daily.copy()
    curve["highlevel"] = curve["balance"].cummax()
    curve["ddpercent"] = (curve["balance"] / curve["highlevel"].replace(0.0, pd.NA) - 1.0) * 100.0
    curve["ddpercent"] = pd.to_numeric(curve["ddpercent"], errors="coerce").fillna(0.0)
    trough = curve.loc[curve["ddpercent"].idxmin()]
    peak_candidates = curve[curve["date"] <= trough["date"]]
    peak = peak_candidates.loc[peak_candidates["balance"].idxmax()]
    return {
        "peak_date": pd.Timestamp(peak["date"]).date().isoformat(),
        "trough_date": pd.Timestamp(trough["date"]).date().isoformat(),
        "max_dd_percent": float(trough["ddpercent"]),
    }


def _heat_deleverage_event_count(trades: pd.DataFrame) -> int:
    if trades.empty or "exit_reason" not in trades.columns:
        return 0
    return int(trades["exit_reason"].fillna("").astype(str).str.contains("risk_cluster_heat_deleverage").sum())


def _run_profile(profile: Profile) -> dict[str, Any]:
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    print(f"[stage363] run {profile.name}", flush=True)
    engine, analysis_df, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_strategy_overrides(profile, START_DT),
        analysis_start=START_DT,
        analysis_end=END_DT,
        preload_start=preload_start,
        capital=TOTAL_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{profile.name}",
        chart_title=f"Stage363 {profile.label}",
    )
    trades = build_trades_df(engine)
    daily = _daily_from_analysis(analysis_df)
    drawdown = _drawdown_window(daily)
    return build_summary_row(
        statistics,
        analysis_start=START_DT,
        analysis_end=END_DT,
        variant=profile.name,
        display_label=profile.label,
        official_version=OFFICIAL_STAGE78_VERSION,
        official_role=OFFICIAL_STAGE78_ROLE,
        model_tag=MODEL_TAG,
        capital=TOTAL_CAPITAL,
        base_risk_ratio=BASE_RISK_RATIO,
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
        heat_deleverage_attr_count=int(
            getattr(getattr(engine, "strategy", None), "risk_cluster_heat_deleverage_count", 0) or 0
        ),
        heat_deleverage_trade_count=_heat_deleverage_event_count(trades),
        dd_peak_date=drawdown["peak_date"],
        dd_trough_date=drawdown["trough_date"],
    )


def _comparison(summary_df: pd.DataFrame) -> pd.DataFrame:
    baseline = summary_df[summary_df["variant"].eq("A_c3_supply_headwind")]
    if baseline.empty:
        return pd.DataFrame()
    base = baseline.iloc[0]
    base_return = _safe_float(base["total_return_pct"])
    base_dd = _safe_float(base["max_dd_percent"])
    rows: list[dict[str, Any]] = []
    for _, row in summary_df.iterrows():
        ret = _safe_float(row["total_return_pct"])
        dd = _safe_float(row["max_dd_percent"])
        retention = ret / base_return * 100.0 if base_return > 0 else 0.0
        rows.append(
            {
                "variant": row["variant"],
                "display_label": row["display_label"],
                "total_return_pct": ret,
                "return_retention_vs_c3_pct": retention,
                "max_dd_percent": dd,
                "dd_improvement_pp": dd - base_dd,
                "sharpe_ratio": _safe_float(row["sharpe_ratio"]),
                "total_trade_count": int(row["total_trade_count"]),
                "total_slippage": _safe_float(row["total_slippage"]),
                "win_ratio_pct": _safe_float(row["win_ratio_pct"]),
                "heat_deleverage_trade_count": int(row["heat_deleverage_trade_count"]),
                "strict_gate": int(dd >= -30.0 and retention >= 80.0),
            }
        )
    return pd.DataFrame(rows)


def _decision(comparison_df: pd.DataFrame) -> dict[str, Any]:
    candidate = comparison_df[comparison_df["variant"].eq("C_same_direction_multi_snapshot")]
    if candidate.empty:
        return {"decision_label": "no_candidate_result"}
    row = candidate.iloc[0]
    dd_ok = _safe_float(row["max_dd_percent"]) >= -30.0
    retention_ok = _safe_float(row["return_retention_vs_c3_pct"]) >= 80.0
    if dd_ok and retention_ok:
        label = "full_sample_candidate_requires_multiperiod_pressure"
    elif dd_ok:
        label = "drawdown_pass_return_fail"
    else:
        label = "fail_full_sample_stop_same_direction_multi_snapshot"
    return {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "candidate": "C_same_direction_multi_snapshot",
        "decision_label": label,
        "max_dd_percent": _safe_float(row["max_dd_percent"]),
        "return_retention_vs_c3_pct": _safe_float(row["return_retention_vs_c3_pct"]),
        "dd_improvement_pp": _safe_float(row["dd_improvement_pp"]),
        "heat_deleverage_trade_count": int(row["heat_deleverage_trade_count"]),
        "overfit_reflection": "否。条件来自风险暴露结构：同一风险簇、同方向、多品种；没有删除具体品种或搜索阈值。",
        "continue_value_reflection": "有。若失败，说明同簇同向多品种快照释放也不足，下一步应转向账户部署或真正低相关收益源。",
    }


def _build_report(summary_df: pd.DataFrame, comparison_df: pd.DataFrame, decision: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            f"# Stage363 同簇同向多品种热度快照验证\n\n"
            f"- 研究线：`{LINE_ID}`\n"
            f"- 核心假设：Stage362全簇快照过粗并把最差回撤挪到2020；本阶段只在同风险簇、同方向、至少两个品种同时持仓时使用快照，其余情形保持C3原热度降仓语义。\n"
            f"- 反过拟合判断：否。规则来自Stage361归因的结构性暴露，不针对单品种、单年份或小数阈值。\n"
            f"- 继续价值判断：有。该实验直接区分“结构性同簇拥挤”与“粗暴扩大降仓”的效果。",
            "## 全样本结果\n\n"
            + _to_markdown_table(
                summary_df[
                    [
                        "variant",
                        "display_label",
                        "end_balance",
                        "total_return_pct",
                        "max_dd_percent",
                        "sharpe_ratio",
                        "total_trade_count",
                        "win_ratio_pct",
                        "total_slippage",
                        "heat_deleverage_trade_count",
                        "dd_peak_date",
                        "dd_trough_date",
                    ]
                ],
                max_rows=20,
            ),
            "## A/C对比\n\n"
            + _to_markdown_table(
                comparison_df[
                    [
                        "variant",
                        "total_return_pct",
                        "return_retention_vs_c3_pct",
                        "max_dd_percent",
                        "dd_improvement_pp",
                        "sharpe_ratio",
                        "heat_deleverage_trade_count",
                        "strict_gate",
                    ]
                ],
                max_rows=20,
            ),
            "## 结论\n\n"
            f"- 决策标签：`{decision.get('decision_label')}`\n"
            f"- 候选最大回撤：`{decision.get('max_dd_percent'):.4f}%`\n"
            f"- 相对C3收益保留：`{decision.get('return_retention_vs_c3_pct'):.4f}%`\n"
            f"- 回撤改善：`{decision.get('dd_improvement_pp'):.4f}` 个百分点\n"
            f"- 热度降仓成交事件数：`{decision.get('heat_deleverage_trade_count')}`",
        ]
    )


def main() -> None:
    summary_df = pd.DataFrame([_run_profile(profile) for profile in PROFILES])
    comparison_df = _comparison(summary_df)
    decision = _decision(comparison_df)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    comparison_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

    summary_df.to_csv(summary_path, index=False)
    comparison_df.to_csv(comparison_path, index=False)
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(summary_df, comparison_df, decision), encoding="utf-8")

    print(f"[stage363] summary: {summary_path}")
    print(f"[stage363] comparison: {comparison_path}")
    print(f"[stage363] decision: {decision_path}")
    print(f"[stage363] report: {report_path}")
    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

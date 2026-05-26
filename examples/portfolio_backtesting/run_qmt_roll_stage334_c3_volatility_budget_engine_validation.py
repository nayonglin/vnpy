from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    TOTAL_CAPITAL,
    _c3_overrides,
    _to_builtin,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage334_c3_volatility_budget_engine_validation_v1"
OUTPUT_PREFIX = "qmt_roll_stage334_c3_volatility_budget_engine_validation"
LINE_ID = "futures_trend_drawdown30_preserve_return"


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    overrides: dict[str, Any]
    note: str


def _merge(*items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        merged.update(item)
    return merged


def _vol_budget(lookback: int, target_annual_vol: float) -> dict[str, Any]:
    return {
        "enable_portfolio_volatility_budget": True,
        "portfolio_volatility_budget_lookback": int(lookback),
        "portfolio_volatility_budget_target_annual_vol": float(target_annual_vol),
        "portfolio_volatility_budget_min_scale": 0.0,
        "portfolio_volatility_budget_entry_contexts": "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add",
        "enable_portfolio_volatility_budget_deleverage": True,
    }


PROFILES: tuple[Profile, ...] = (
    Profile(
        "A_c3_supply_headwind",
        "A：C3原始",
        {},
        "C_pressure040叠加供需强逆风过滤，作为当前最强单策略对照。",
    ),
    Profile(
        "C_vol_budget_lb20_target70",
        "C：20日波动预算70%",
        _vol_budget(20, 0.70),
        "Stage033日收益层最高收益候选；快速响应但更需要真实引擎反证。",
    ),
    Profile(
        "C_vol_budget_lb60_target60",
        "C：60日波动预算60%",
        _vol_budget(60, 0.60),
        "更平滑的保守代表，用来检验线索是否不依赖20日快速响应。",
    ),
    Profile(
        "C_vol_budget_lb60_target70",
        "C：60日波动预算70%",
        _vol_budget(60, 0.70),
        "低干预代表，用来观察温和风险预算是否足以压回撤。",
    ),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _profile_overrides(profile: Profile) -> dict[str, Any]:
    return _merge(_c3_overrides(START_DT), profile.overrides)


def _daily_to_frame(analysis_df: pd.DataFrame | None, variant: str) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame()
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"])
    frame["variant"] = variant
    return frame


def _scale_history_to_frame(strategy: Any, variant: str) -> pd.DataFrame:
    rows = getattr(strategy, "portfolio_volatility_budget_scale_history", []) if strategy else []
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["variant"] = variant
    return frame


def _trade_events_to_frame(strategy: Any, variant: str) -> pd.DataFrame:
    rows = getattr(strategy, "trade_event_diagnostics", []) if strategy else []
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["variant"] = variant
    return frame


def _run_profile(profile: Profile) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    print(f"[stage334] run {profile.name}", flush=True)
    engine, analysis_df, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_profile_overrides(profile),
        analysis_start=START_DT,
        analysis_end=END_DT,
        preload_start=preload_start,
        capital=TOTAL_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{profile.name}",
        chart_title=f"Stage334 {profile.label}",
    )
    strategy = getattr(engine, "strategy", None)
    scale_frame = _scale_history_to_frame(strategy, profile.name)
    if scale_frame.empty:
        avg_scale = 1.0
        min_scale = 1.0
        scaled_day_count = 0
    else:
        avg_scale = _safe_float(scale_frame["scale"].mean(), 1.0)
        min_scale = _safe_float(scale_frame["scale"].min(), 1.0)
        scaled_day_count = int((scale_frame["scale"].astype(float) < 0.999999).sum())

    row = build_summary_row(
        statistics,
        variant=profile.name,
        display_label=profile.label,
        note=profile.note,
        analysis_start=START_DT,
        analysis_end=END_DT,
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
        portfolio_volatility_budget_deleverage_count=int(
            getattr(strategy, "portfolio_volatility_budget_deleverage_count", 0) if strategy else 0
        ),
        portfolio_volatility_budget_avg_scale=avg_scale,
        portfolio_volatility_budget_min_scale=min_scale,
        portfolio_volatility_budget_scaled_day_count=scaled_day_count,
    )
    return (
        row,
        _daily_to_frame(analysis_df, profile.name),
        scale_frame,
        _trade_events_to_frame(strategy, profile.name),
    )


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    baseline = summary[summary["variant"].eq("A_c3_supply_headwind")]
    if baseline.empty:
        return summary
    a = baseline.iloc[0]
    base_return = _safe_float(a.get("total_return_pct"))
    base_sharpe = _safe_float(a.get("sharpe_ratio"))
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        candidate_return = _safe_float(row.get("total_return_pct"))
        retention = candidate_return / base_return * 100.0 if base_return > 0 else 0.0
        dd_ok = _safe_float(row.get("max_dd_percent")) >= -30.0
        return_ok = retention >= 80.0
        rows.append(
            {
                **row.to_dict(),
                "baseline_return_pct": base_return,
                "return_retention_vs_c3_pct": retention,
                "baseline_max_dd_pct": _safe_float(a.get("max_dd_percent")),
                "max_dd_improvement_vs_c3_pct": _safe_float(row.get("max_dd_percent")) - _safe_float(a.get("max_dd_percent")),
                "baseline_sharpe": base_sharpe,
                "dd_ok": int(dd_ok),
                "return_ok": int(return_ok),
                "strict_pass": int(dd_ok and return_ok),
                "research_pass": int(dd_ok and retention >= 65.0 and _safe_float(row.get("sharpe_ratio")) >= base_sharpe),
            }
        )
    return pd.DataFrame(rows)


def _build_report(comparison: pd.DataFrame) -> str:
    full = comparison.copy()
    full = full.sort_values(
        ["strict_pass", "research_pass", "max_dd_percent", "return_retention_vs_c3_pct"],
        ascending=[False, False, False, False],
    )
    pass_rows = full[(full["variant"].ne("A_c3_supply_headwind")) & (full["strict_pass"].eq(1))]
    if pass_rows.empty:
        decision = "真实引擎全样本没有候选同时满足最大回撤30以内和C3收益保留80%。"
    else:
        best = pass_rows.iloc[0]
        decision = (
            f"真实引擎全样本出现候选 `{best['variant']}`，收益保留 "
            f"`{best['return_retention_vs_c3_pct']:.2f}%`，最大回撤 `{best['max_dd_percent']:.4f}%`；"
            "需要继续做多起点和滑点压力复验。"
        )
    return "\n".join(
        [
            "# Stage334 C3波动率预算真实引擎验证",
            "",
            "## 目标",
            "",
            "- A：`C3_supply_headwind`，即当前最强单策略底座。",
            "- C：账户层波动预算，同时作用于新开仓、加仓和已有持仓缩放。",
            "- 通过标准：全样本最大回撤进入30%以内，且总收益保留C3至少80%。",
            "",
            "## 候选说明",
            "",
            _to_markdown_table(
                comparison[["variant", "display_label", "note"]].drop_duplicates(),
                ["variant", "display_label", "note"],
                max_rows=20,
            ),
            "",
            "## 全样本结果",
            "",
            _to_markdown_table(
                full,
                [
                    "variant",
                    "total_return_pct",
                    "return_retention_vs_c3_pct",
                    "max_dd_percent",
                    "max_dd_improvement_vs_c3_pct",
                    "sharpe_ratio",
                    "total_trade_count",
                    "total_slippage",
                    "portfolio_volatility_budget_avg_scale",
                    "portfolio_volatility_budget_min_scale",
                    "portfolio_volatility_budget_scaled_day_count",
                    "portfolio_volatility_budget_deleverage_count",
                    "strict_pass",
                ],
                max_rows=20,
            ),
            "",
            "## 阶段判断",
            "",
            f"- {decision}",
            "",
            "## 过拟合反思",
            "",
            "- 运行前：不是过拟合。只验证Stage033预声明的三个粗档位，没有小数救援。",
            "- 运行后：若全样本失败，不继续改成55日或0.67；若全样本通过，也必须做多起点、弱窗口和滑点压力。",
            "",
            "## 继续价值反思",
            "",
            "- 运行前：有价值。日收益层候选必须经过真实引擎反证，避免把线性缩放误认为可交易规则。",
            "- 运行后：继续价值取决于真实引擎是否仍保留回撤/收益结构。",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    scale_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []
    for profile in PROFILES:
        row, daily, scales, events = _run_profile(profile)
        rows.append(row)
        if not daily.empty:
            daily_frames.append(daily)
        if not scales.empty:
            scale_frames.append(scales)
        if not events.empty:
            trade_event_frames.append(events)

    summary = pd.DataFrame(rows)
    comparison = _comparison(summary)
    daily_all = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    scale_all = pd.concat(scale_frames, ignore_index=True) if scale_frames else pd.DataFrame()
    events_all = pd.concat(trade_event_frames, ignore_index=True) if trade_event_frames else pd.DataFrame()

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    comparison_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
    daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
    scale_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scale_history_{MODEL_TAG}.csv"
    events_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    comparison.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    daily_all.to_csv(daily_path, index=False, encoding="utf-8-sig")
    scale_all.to_csv(scale_path, index=False, encoding="utf-8-sig")
    events_all.to_csv(events_path, index=False, encoding="utf-8-sig")
    report = _build_report(comparison)
    report_path.write_text(report, encoding="utf-8")

    pass_rows = comparison[
        comparison["variant"].ne("A_c3_supply_headwind") & comparison["strict_pass"].eq(1)
    ].copy()
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "engine_candidate_requires_multiperiod" if not pass_rows.empty else "engine_full_sample_fail",
        "pass_count": int(len(pass_rows)),
        "best_variant": str(pass_rows.iloc[0]["variant"]) if not pass_rows.empty else "",
        "summary": str(summary_path.resolve()),
        "comparison": str(comparison_path.resolve()),
        "daily": str(daily_path.resolve()),
        "scale_history": str(scale_path.resolve()),
        "trade_events": str(events_path.resolve()),
        "report": str(report_path.resolve()),
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

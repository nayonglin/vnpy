from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
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


MODEL_TAG = "stage332_c3_existing_position_release_screen_v1"
OUTPUT_PREFIX = "qmt_roll_stage332_c3_existing_position_release_screen"
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


def _profit_giveback_default() -> dict[str, Any]:
    return {
        "enable_profit_giveback_stop": True,
        "profit_giveback_trigger_pct": 0.08,
        "profit_giveback_retain_ratio": 0.70,
        "profit_giveback_min_lock_pct": 0.03,
    }


def _portfolio_deleverage(start_pct: float, full_pct: float, floor: float) -> dict[str, Any]:
    return {
        "enable_portfolio_drawdown_deleverage": True,
        "portfolio_drawdown_gate_start_pct": start_pct,
        "portfolio_drawdown_gate_full_pct": full_pct,
        "portfolio_drawdown_gate_weight_floor": floor,
    }


PROFILES: tuple[Profile, ...] = (
    Profile(
        "A_c3_supply_headwind",
        "A：C3原始",
        {},
        "C_pressure040叠加供需强逆风过滤，作为当前最强单策略对照。",
    ),
    Profile(
        "C_profit_giveback_default",
        "C：默认盈利回吐止损",
        _profit_giveback_default(),
        "复用既有默认结构：最大浮盈达到8%后保留70%，最低锁3%；不扫参数。",
    ),
    Profile(
        "C_dd_delev_05_15_floor90",
        "C：组合回撤5-15温和降仓到90%",
        _portfolio_deleverage(0.05, 0.15, 0.90),
        "更早识别权益高位回吐，但只温和释放10%已有仓位风险。",
    ),
    Profile(
        "C_dd_delev_05_15_floor85",
        "C：组合回撤5-15降仓到85%",
        _portfolio_deleverage(0.05, 0.15, 0.85),
        "与旧10-30-85结构做粗档位对照，不做连续阈值搜索。",
    ),
    Profile(
        "C_dd_delev_10_30_floor85",
        "C：组合回撤10-30降仓到85%",
        _portfolio_deleverage(0.10, 0.30, 0.85),
        "复验既有门禁形状在C3底座上的表现。",
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
    overrides = _c3_overrides(START_DT)
    overrides.update(profile.overrides)
    return overrides


def _daily_to_frame(analysis_df: pd.DataFrame | None, variant: str) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame()
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"])
    frame["variant"] = variant
    return frame


def _run_profile(profile: Profile) -> tuple[dict[str, Any], pd.DataFrame]:
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    print(f"[stage332] run {profile.name}", flush=True)
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
        chart_title=f"Stage332 {profile.label}",
    )
    strategy = getattr(engine, "strategy", None)
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
        profit_giveback_stop_update_count=int(getattr(strategy, "profit_giveback_stop_update_count", 0) if strategy else 0),
        portfolio_drawdown_deleverage_count=int(getattr(strategy, "portfolio_drawdown_deleverage_count", 0) if strategy else 0),
    )
    return row, _daily_to_frame(analysis_df, profile.name)


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
    full = full.sort_values(["strict_pass", "research_pass", "max_dd_percent", "return_retention_vs_c3_pct"], ascending=[False, False, False, False])
    pass_rows = full[(full["variant"].ne("A_c3_supply_headwind")) & (full["strict_pass"].eq(1))]
    if pass_rows.empty:
        decision = "没有候选在全样本同时满足最大回撤30以内和C3收益保留80%。"
    else:
        best = pass_rows.iloc[0]
        decision = (
            f"出现全样本候选 `{best['variant']}`，收益保留 `{best['return_retention_vs_c3_pct']:.2f}%`，"
            f"最大回撤 `{best['max_dd_percent']:.4f}%`；需要进入多周期和滑点压力复验。"
        )
    return "\n".join(
        [
            "# Stage032 C3已有仓位风险释放真实引擎筛查",
            "",
            "## 目标",
            "",
            "- A：`C3_supply_headwind`，即当前最强单策略底座。",
            "- C：只动已有仓位风险释放，不改AI池、品种池、入场alpha或供需强逆风过滤。",
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
                    "profit_giveback_stop_update_count",
                    "portfolio_drawdown_deleverage_count",
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
            "- 运行前：不是过拟合。候选来自已有机制或粗档位组合回撤规则，没有新增品种黑名单、单窗口补丁或小数搜索。",
            "- 运行后：若全样本失败，不继续把5/15改成4/13这类救结果；若全样本通过，也必须多起点和滑点压力确认。",
            "",
            "## 继续价值反思",
            "",
            "- 运行前：有价值。Stage031显示剩余回撤来自高点已有仓位，必须验证已有仓位风险释放是否能触及主因。",
            "- 运行后：继续价值取决于是否出现低自由度全样本线索；若没有，策略内持仓释放方向要降级，转向账户层部署。",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    for profile in PROFILES:
        row, daily = _run_profile(profile)
        rows.append(row)
        if not daily.empty:
            daily_frames.append(daily)
    summary = pd.DataFrame(rows)
    comparison = _comparison(summary)
    daily_all = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    comparison_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
    daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    comparison.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    daily_all.to_csv(daily_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(comparison), encoding="utf-8")

    pass_count = int(comparison[(comparison["variant"].ne("A_c3_supply_headwind")) & (comparison["strict_pass"].eq(1))].shape[0])
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "baseline": "C3_supply_headwind",
        "decision": "candidate_requires_multiperiod_validation" if pass_count else "screen_fail_no_full_sample_candidate",
        "pass_count": pass_count,
        "summary": str(summary_path),
        "comparison": str(comparison_path),
        "daily": str(daily_path),
        "report": str(report_path),
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage332] report: {report_path}")


if __name__ == "__main__":
    main()

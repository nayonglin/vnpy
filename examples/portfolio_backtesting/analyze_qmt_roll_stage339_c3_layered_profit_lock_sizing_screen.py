from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
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
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage339_c3_layered_profit_lock_sizing_screen_v1"
OUTPUT_PREFIX = "qmt_roll_stage339_c3_layered_profit_lock_sizing_screen"
LINE_ID = "futures_trend_drawdown30_preserve_return"


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    overrides: dict[str, Any]
    note: str


def _layered(
    *,
    base_equity: float,
    start_equity: float,
    ratio: float,
    tiers: str = "",
) -> dict[str, Any]:
    return {
        "enable_layered_profit_lock_sizing": True,
        "layered_profit_lock_base_equity": base_equity,
        "layered_profit_lock_start_equity": start_equity,
        "layered_profit_lock_ratio": ratio,
        "layered_profit_lock_tiers": tiers,
    }


PROFILES: tuple[Profile, ...] = (
    Profile(
        "A_c3_supply_headwind",
        "A：C3原始",
        {},
        "当前最强单策略底座，不改核心alpha、AI池、品种池或供需过滤。",
    ),
    Profile(
        "C_lock_1m25",
        "C：100万后锁25%利润",
        _layered(base_equity=500_000.0, start_equity=1_000_000.0, ratio=0.25),
        "初始50万正常复利；权益高水位超过100万后，后续sizing只释放75%的新增利润。",
    ),
    Profile(
        "C_lock_1m50",
        "C：100万后锁50%利润",
        _layered(base_equity=500_000.0, start_equity=1_000_000.0, ratio=0.50),
        "比1m25更强的账户级利润留白，用于判断锁定利润能否压住尾部回撤。",
    ),
    Profile(
        "C_lock_2m50",
        "C：200万后锁50%利润",
        _layered(base_equity=500_000.0, start_equity=2_000_000.0, ratio=0.50),
        "更晚触发，尽量保留前期复利，只在权益已经显著放大后降后续风险。",
    ),
    Profile(
        "C_lock_tier_1m25_2m50_5m65",
        "C：阶梯锁盈",
        _layered(
            base_equity=500_000.0,
            start_equity=1_000_000.0,
            ratio=0.25,
            tiers="2000000:0.50,5000000:0.65",
        ),
        "粗粒度阶梯：100万后锁25%，200万后锁50%，500万后锁65%；不做小数救结果。",
    ),
)


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


def _analysis_tail_metrics(analysis_df: pd.DataFrame | None) -> dict[str, Any]:
    if analysis_df is None or analysis_df.empty:
        return {
            "final_sizing_equity": 0.0,
            "final_locked_equity": 0.0,
            "max_locked_equity": 0.0,
            "min_sizing_equity_to_balance_pct": 0.0,
            "final_sizing_equity_to_balance_pct": 0.0,
        }
    frame = analysis_df.copy()
    balance = pd.to_numeric(frame.get("balance", pd.Series(dtype=float)), errors="coerce")
    sizing = pd.to_numeric(frame.get("sizing_equity", pd.Series(dtype=float)), errors="coerce")
    locked = pd.to_numeric(
        frame.get("layered_profit_lock_locked_equity", pd.Series(dtype=float)),
        errors="coerce",
    ).fillna(0.0)
    ratio = sizing / balance.replace(0.0, np.nan) * 100.0
    return {
        "final_sizing_equity": _safe_float(sizing.dropna().iloc[-1] if not sizing.dropna().empty else 0.0),
        "final_locked_equity": _safe_float(locked.dropna().iloc[-1] if not locked.dropna().empty else 0.0),
        "max_locked_equity": _safe_float(locked.max()),
        "min_sizing_equity_to_balance_pct": _safe_float(ratio.min()),
        "final_sizing_equity_to_balance_pct": _safe_float(ratio.dropna().iloc[-1] if not ratio.dropna().empty else 0.0),
    }


def _run_profile(profile: Profile) -> tuple[dict[str, Any], pd.DataFrame]:
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    print(f"[stage339] run {profile.name}", flush=True)
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
        chart_title=f"Stage339 {profile.label}",
    )
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
    )
    row.update(_analysis_tail_metrics(analysis_df))
    row["trade_count"] = int(_safe_float(statistics.get("total_trade_count")))
    row["engine_strategy_class"] = type(getattr(engine, "strategy", object())).__name__
    return row, _daily_to_frame(analysis_df, profile.name)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq("A_c3_supply_headwind")]
    if baseline.empty:
        return summary
    base = baseline.iloc[0]
    base_return = _safe_float(base.get("total_return_pct"))
    base_dd = _safe_float(base.get("max_dd_percent"))
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        total_return = _safe_float(row.get("total_return_pct"))
        max_dd = _safe_float(row.get("max_dd_percent"))
        retention = total_return / base_return * 100.0 if base_return > 0 else math.nan
        rows.append(
            {
                **row.to_dict(),
                "baseline_return_pct": base_return,
                "return_retention_vs_c3_pct": retention,
                "baseline_max_dd_pct": base_dd,
                "max_dd_improvement_vs_c3_pct": max_dd - base_dd,
                "dd_ok": int(max_dd >= -30.0),
                "return80_ok": int(retention >= 80.0 if not math.isnan(retention) else False),
                "strict_pass": int(max_dd >= -30.0 and retention >= 80.0 if not math.isnan(retention) else False),
            }
        )
    return pd.DataFrame(rows)


def _build_report(comparison: pd.DataFrame) -> str:
    full = comparison.sort_values(
        ["strict_pass", "max_dd_percent", "return_retention_vs_c3_pct"],
        ascending=[False, False, False],
    )
    candidates = full[(full["variant"].ne("A_c3_supply_headwind")) & (full["strict_pass"].eq(1))]
    if candidates.empty:
        decision = "没有候选在全样本同时满足最大回撤30以内和C3收益保留80%；该账户级分层锁盈形状不进入多周期复验。"
    else:
        best = candidates.iloc[0]
        decision = (
            f"出现全样本候选 `{best['variant']}`：总收益 `{best['total_return_pct']:.4f}%`，"
            f"最大回撤 `{best['max_dd_percent']:.4f}%`，收益保留 `{best['return_retention_vs_c3_pct']:.2f}%`；"
            "下一步必须做起始年份、弱窗口和滑点压力。"
        )
    return "\n".join(
        [
            "# Stage039 C3账户级分层锁盈sizing筛查",
            "",
            "## 目标",
            "",
            "- 验证账户级利润锁定是否能在不改核心alpha、不改AI池、不改品种池的前提下，把C3最大回撤压到30%以内。",
            "- 分层锁盈只影响后续开仓/加仓使用的sizing权益，不直接改出场信号，也不按单个亏损窗口做补丁。",
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
                    "final_sizing_equity",
                    "final_locked_equity",
                    "min_sizing_equity_to_balance_pct",
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
            "- 运行前：不是过拟合。候选是账户级粗档位利润留白，不使用单品种黑名单、单窗口日期或小数阈值。",
            "- 运行后：若全样本失败，不把100万改成98万、25%改成23%救结果；若全样本通过，也只算筛查候选。",
            "",
            "## 继续价值反思",
            "",
            "- 运行前：有价值。C3剩余回撤接近30%边界，账户级复利控制可能比交易信号补丁更贴近实盘部署。",
            "- 运行后：继续价值取决于是否出现全样本候选；失败则应降级账户级利润锁定方向，继续寻找真正低相关收益源。",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    for profile in PROFILES:
        row, daily = _run_profile(profile)
        summary_rows.append(row)
        if not daily.empty:
            daily_frames.append(daily)

    summary = pd.DataFrame(summary_rows)
    comparison = _comparison(summary)
    daily_df = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()

    paths = {
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "comparison": OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv",
        "daily": OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "manifest": OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    comparison.to_csv(paths["comparison"], index=False, encoding="utf-8-sig")
    daily_df.to_csv(paths["daily"], index=False, encoding="utf-8-sig")
    paths["report"].write_text(_build_report(comparison), encoding="utf-8")
    paths["manifest"].write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "output_prefix": OUTPUT_PREFIX,
                "line_id": LINE_ID,
                "baseline": "A_c3_supply_headwind",
                "profiles": [
                    {
                        "name": profile.name,
                        "label": profile.label,
                        "overrides": _to_builtin(profile.overrides),
                    }
                    for profile in PROFILES
                ],
                "capital": TOTAL_CAPITAL,
                "base_risk_ratio": BASE_RISK_RATIO,
                "paths": {key: str(path) for key, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, ensure_ascii=False, indent=2))
    print(
        comparison[
            [
                "variant",
                "total_return_pct",
                "return_retention_vs_c3_pct",
                "max_dd_percent",
                "max_dd_improvement_vs_c3_pct",
                "sharpe_ratio",
                "strict_pass",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()

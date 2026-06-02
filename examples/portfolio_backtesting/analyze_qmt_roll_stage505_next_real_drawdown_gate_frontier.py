from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage451_true_path_1455_vwap_replay as s451  # noqa: E402
import analyze_qmt_roll_stage501_asymmetric_entry_exit_execution as s501  # noqa: E402
import analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay as s502  # noqa: E402
import analyze_qmt_roll_stage503_next_real_open_risk_frontier as s503  # noqa: E402
import analyze_qmt_roll_stage504_next_real_open_fallback_backfill as s504  # noqa: E402
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage505_next_real_drawdown_gate_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage505_next_real_drawdown_gate_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
MAX_ITERATIONS = 3

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
BACKFILL_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_backfill_status_{MODEL_TAG}.csv"
FALLBACK_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fallback_audit_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
FRONTIER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class GateConfig:
    variant: str
    label: str
    base_risk_multiplier: float
    enable_gate: bool
    start_pct: float = 0.0
    full_pct: float = 0.0
    floor: float = 1.0
    deleverage: bool = False


CONFIGS: tuple[GateConfig, ...] = (
    GateConfig(
        "stage079_next_real_risk060_clean",
        "Stage079 next-real risk 0.60 clean",
        0.6,
        False,
    ),
    GateConfig(
        "stage079_next_real_risk070_clean",
        "Stage079 next-real risk 0.70 clean",
        0.7,
        False,
    ),
    GateConfig(
        "stage079_next_real_r070_dd20_30_f50_delev",
        "Stage079 next-real r0.70 DD gate 20-30 floor50 delever",
        0.7,
        True,
        0.20,
        0.30,
        0.50,
        True,
    ),
    GateConfig(
        "stage079_next_real_r070_dd15_30_f50_delev",
        "Stage079 next-real r0.70 DD gate 15-30 floor50 delever",
        0.7,
        True,
        0.15,
        0.30,
        0.50,
        True,
    ),
    GateConfig(
        "stage079_next_real_r080_dd20_30_f50_delev",
        "Stage079 next-real r0.80 DD gate 20-30 floor50 delever",
        0.8,
        True,
        0.20,
        0.30,
        0.50,
        True,
    ),
    GateConfig(
        "stage079_next_real_r080_dd15_30_f50_delev",
        "Stage079 next-real r0.80 DD gate 15-30 floor50 delever",
        0.8,
        True,
        0.15,
        0.30,
        0.50,
        True,
    ),
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _run_config(config: GateConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    overrides = _c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    _, open_map = s501._seed_proxy_maps()
    engine = s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=C3_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO * float(config.base_risk_multiplier),
        strategy_overrides=overrides,
    )
    setting["capital_base"] = C3_CAPITAL
    if config.enable_gate:
        setting.update(
            {
                "enable_portfolio_drawdown_gate": True,
                "portfolio_drawdown_gate_start_pct": float(config.start_pct),
                "portfolio_drawdown_gate_full_pct": float(config.full_pct),
                "portfolio_drawdown_gate_weight_floor": float(config.floor),
                "portfolio_drawdown_gate_entry_contexts": "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add",
                "enable_portfolio_drawdown_deleverage": bool(config.deleverage),
            }
        )
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty result for {config.variant}")
    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["account_equity"] = ACCOUNT_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = config.variant
    daily["label"] = config.label
    daily["base_risk_multiplier"] = float(config.base_risk_multiplier)
    daily["gate_start_pct"] = float(config.start_pct)
    daily["gate_full_pct"] = float(config.full_pct)
    daily["gate_floor"] = float(config.floor)
    usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    if not usage.empty:
        usage["variant"] = config.variant
        usage["label"] = config.label
        usage["base_risk_multiplier"] = float(config.base_risk_multiplier)
        usage["gate_start_pct"] = float(config.start_pct)
        usage["gate_full_pct"] = float(config.full_pct)
        usage["gate_floor"] = float(config.floor)
        usage["gate_deleverage"] = bool(config.deleverage)
    return daily, usage


def _run_all_configs() -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = s503._load_stage079_baseline()
    daily_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    for config in CONFIGS:
        daily, usage = _run_config(config)
        daily_frames.append(daily)
        usage_frames.append(usage)
    long_daily = s503._build_long_daily(baseline, daily_frames)
    usage_all = pd.concat(usage_frames, ignore_index=True) if usage_frames else pd.DataFrame()
    return long_daily, usage_all


def _source_counts(usage: pd.DataFrame) -> pd.DataFrame:
    if usage.empty:
        return pd.DataFrame(columns=["variant", "price_source", "trade_count"])
    rows = []
    for (variant, source), value in usage.groupby(["variant", "price_source"]).size().items():
        rows.append({"variant": variant, "price_source": source, "trade_count": int(value)})
    return pd.DataFrame(rows)


def _frontier(summary: pd.DataFrame, usage: pd.DataFrame) -> pd.DataFrame:
    stage079_return = _safe_float(summary[summary["variant"].eq(BASELINE_VARIANT)]["total_return_pct"].iloc[0])
    config_map = {config.variant: config for config in CONFIGS}
    fallback_by_variant = (
        usage.assign(is_fallback=usage["price_source"].astype(str).str.startswith("fallback"))
        .groupby("variant")["is_fallback"]
        .sum()
        .astype(int)
        .to_dict()
        if not usage.empty
        else {}
    )
    frame = summary[summary["variant"].isin(config_map)].copy()
    frame["base_risk_multiplier"] = frame["variant"].map(lambda value: config_map[str(value)].base_risk_multiplier)
    frame["gate_start_pct"] = frame["variant"].map(lambda value: config_map[str(value)].start_pct)
    frame["gate_full_pct"] = frame["variant"].map(lambda value: config_map[str(value)].full_pct)
    frame["gate_floor"] = frame["variant"].map(lambda value: config_map[str(value)].floor)
    frame["gate_deleverage"] = frame["variant"].map(lambda value: int(config_map[str(value)].deleverage))
    frame["return_retention_vs_stage079_pct"] = frame["total_return_pct"].astype(float) / stage079_return * 100.0
    frame["dd40_pass"] = frame["max_dd_pct"].astype(float).ge(-40.0).astype(int)
    frame["fallback_trade_count"] = frame["variant"].map(fallback_by_variant).fillna(0).astype(int)
    return frame[
        [
            "variant",
            "base_risk_multiplier",
            "gate_start_pct",
            "gate_full_pct",
            "gate_floor",
            "gate_deleverage",
            "end_equity",
            "total_return_pct",
            "return_retention_vs_stage079_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "dd40_pass",
            "fallback_trade_count",
        ]
    ].sort_values(["dd40_pass", "return_retention_vs_stage079_pct"], ascending=[False, False])


def _plot(long_daily: pd.DataFrame, frontier: pd.DataFrame) -> None:
    keep = [BASELINE_VARIANT, "stage079_next_real_risk060_clean", "stage079_next_real_risk070_clean"]
    candidates = frontier[frontier["dd40_pass"].eq(1)]["variant"].tolist()
    for variant in candidates[:3]:
        if variant not in keep:
            keep.append(variant)
    if len(keep) <= 3:
        best = frontier.sort_values("total_return_pct", ascending=False)["variant"].head(2).tolist()
        for variant in best:
            if variant not in keep:
                keep.append(variant)
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily[long_daily["variant"].isin(keep)].groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, linewidth=1.1)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=label, linewidth=1.0)
    axes[0].set_title("Stage505 next-real drawdown-gate frontier")
    axes[0].set_ylabel("NAV")
    axes[0].legend(fontsize=8)
    axes[1].set_title("Underwater drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    axes[1].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    frontier: pd.DataFrame,
    source_counts: pd.DataFrame,
    backfill_status: pd.DataFrame,
    fallback_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "variant",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "annual_cold_start_dd30_pass_rate",
        "quarter_cold_start_dd30_pass_rate",
    ]
    horizon_cols = [
        "variant",
        "horizon_days",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "max_dd_worst_pct",
        "dd30_breach_rate",
        "ulcer_p95_pct",
    ]
    report = [
        "# Stage205 下一真实窗口组合回撤门控前沿",
        "",
        f"- 生成时间：{decision['generated_at']}",
        "- 阶段性质：真实可成交低自由度风险结构；只使用上一日可见组合权益回撤状态。",
        "- A/B/C判断：A 为 Stage079 原始日线 baseline；B 无独立意义；C 为 Stage079 下一真实窗口 + 固定风险预算 + 组合回撤门控/降仓。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随的波动/风险目标化有研究依据，但本阶段只用粗档组合回撤状态，避免坏窗口补丁。",
        "- 组合回撤门控只读已发生权益高水位和当前权益，理论上不引入未来函数；所有订单仍下一真实窗口成交。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最佳 clean DD40 版本：`{decision['best_clean_dd40_variant']}`。",
        f"- 最佳 clean DD40 收益保留：`{decision['best_clean_dd40_return_retention_vs_stage079_pct']:.4f}%`。",
        f"- 最佳 clean DD40 最大回撤：`{decision['best_clean_dd40_max_dd_pct']:.4f}%`。",
        f"- 剩余 fallback：`{decision['fallback_remaining_count']}`。",
        "",
        "## 前沿汇总",
        "",
        _md_table(frontier),
        "",
        "## 全周期指标",
        "",
        _md_table(summary[summary_cols]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[horizon_cols].sort_values(["variant", "horizon_days"])),
        "",
        "## 成交价格来源",
        "",
        _md_table(source_counts.sort_values(["variant", "trade_count"], ascending=[True, False]), max_rows=80),
        "",
        "## 补数状态",
        "",
        _md_table(backfill_status.sort_values(["iteration", "vt_symbol"]), max_rows=80),
        "",
        "## 剩余 fallback 审计",
        "",
        _md_table(fallback_audit.sort_values(["variant", "signal_date", "vt_symbol"]), max_rows=80),
        "",
        "## 图表视觉复盘",
        "",
        "- 需要结合图形判断门控是否只是把 2022 风险挪到 2025，不能只看最大回撤一个数。",
        "- 若门控版本 NAV 显著低于 clean `risk070`，说明它主要是降杠杆，不是改善结构。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。门控基于组合权益回撤这一通用状态，且只测粗档。",
        "- 运行后过拟合反思：不得继续围绕 `0.17/0.23` 等小数救线。",
        "- 运行前继续价值反思：是。Stage204 已证明固定倍率卡在收益/回撤边界，需要状态风险预算。",
        "- 运行后继续价值反思：以决策标签为准；若无候选，下一步应换结构而非调阈值。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    s504._patch_raw_roots()
    all_status: list[pd.DataFrame] = []
    final_daily = pd.DataFrame()
    final_usage = pd.DataFrame()
    for iteration in range(1, MAX_ITERATIONS + 1):
        final_daily, final_usage = _run_all_configs()
        fallback = final_usage[final_usage["price_source"].astype(str).str.startswith("fallback")].copy()
        if fallback.empty:
            break
        if iteration == MAX_ITERATIONS:
            break
        status, _ = s504._backfill(fallback, iteration)
        if not status.empty:
            all_status.append(status)
        if not status.empty and not status["covered_after_extract"].fillna(False).any():
            break

    summary, horizon, score, cost, gate = s451._evaluate(final_daily)
    source_counts = _source_counts(final_usage)
    frontier = _frontier(summary, final_usage)
    fallback_audit = final_usage[final_usage["price_source"].astype(str).str.startswith("fallback")].copy()
    backfill_status = pd.concat(all_status, ignore_index=True) if all_status else pd.DataFrame()

    clean = frontier[frontier["fallback_trade_count"].eq(0)].copy()
    clean_dd40 = clean[clean["dd40_pass"].eq(1)].copy()
    clean_dd40_return65 = clean_dd40[clean_dd40["return_retention_vs_stage079_pct"].ge(65.0)].copy()
    if not clean_dd40_return65.empty:
        best = clean_dd40_return65.sort_values("total_return_pct", ascending=False).iloc[0]
        decision_label = "drawdown_gate_clean_dd40_return65_candidate_needs_final_audit"
    elif not clean_dd40.empty:
        best = clean_dd40.sort_values("total_return_pct", ascending=False).iloc[0]
        decision_label = "drawdown_gate_clean_dd40_but_return_retention_short"
    else:
        best = frontier.sort_values("total_return_pct", ascending=False).iloc[0]
        decision_label = "drawdown_gate_no_clean_dd40_candidate"

    decision = {
        "stage": "Stage205",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "iterations": int(iteration),
        "fallback_remaining_count": int(len(fallback_audit)),
        "best_clean_dd40_variant": str(best["variant"]) if not clean_dd40.empty else "",
        "best_clean_dd40_end_equity": _safe_float(best["end_equity"]),
        "best_clean_dd40_total_return_pct": _safe_float(best["total_return_pct"]),
        "best_clean_dd40_return_retention_vs_stage079_pct": _safe_float(best["return_retention_vs_stage079_pct"]),
        "best_clean_dd40_max_dd_pct": _safe_float(best["max_dd_pct"]),
        "best_clean_dd40_sharpe": _safe_float(best["sharpe"]),
        "best_clean_dd40_ulcer_pct": _safe_float(best["ulcer_pct"]),
        "outputs": {
            "daily": str(DAILY_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "cost": str(COST_PATH),
            "gate": str(GATE_PATH),
            "frontier": str(FRONTIER_PATH),
            "backfill_status": str(BACKFILL_STATUS_PATH),
            "fallback_audit": str(FALLBACK_AUDIT_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若出现 clean DD40+65 候选，做图形和成本压力复核；若无，停止该门控形状。",
    }

    _plot(final_daily, frontier)
    final_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    final_usage.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    backfill_status.to_csv(BACKFILL_STATUS_PATH, index=False, encoding="utf-8-sig")
    fallback_audit.to_csv(FALLBACK_AUDIT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    frontier.to_csv(FRONTIER_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, frontier, source_counts, backfill_status, fallback_audit, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()

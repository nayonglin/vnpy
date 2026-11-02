from __future__ import annotations

from collections import Counter
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

import analyze_qmt_roll_stage450_minute_execution_equity_rebuild as s450  # noqa: E402
import analyze_qmt_roll_stage451_true_path_1455_vwap_replay as s451  # noqa: E402
import analyze_qmt_roll_stage501_asymmetric_entry_exit_execution as s501  # noqa: E402
import analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay as s502  # noqa: E402
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_roll_backtest import SameDayCloseBacktestingEngine, build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage503_next_real_open_risk_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage503_next_real_open_risk_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
RISK_MULTIPLIERS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
FRONTIER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
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


def _load_stage079_baseline() -> pd.DataFrame:
    frame = pd.read_csv(s450.STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["window_name"].eq("start_2020") & frame["variant"].eq(BASELINE_VARIANT)].copy()
    for column in ["equity", "c3_net_pnl", "c3_slippage", "c3_trade_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _run_variant(multiplier: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
        risk_ratio=BASE_RISK_RATIO * float(multiplier),
        strategy_overrides=overrides,
    )
    setting["capital_base"] = C3_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty result for risk multiplier {multiplier}")
    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    variant = f"stage079_next_real_risk{int(round(multiplier * 100)):03d}"
    daily["account_equity"] = ACCOUNT_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = variant
    daily["label"] = f"Stage079 next-real-open risk {multiplier:.2f}"
    daily["risk_multiplier"] = float(multiplier)
    usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    if not usage.empty:
        usage["variant"] = variant
        usage["risk_multiplier"] = float(multiplier)
    source_counts = pd.DataFrame(
        [
            {"variant": variant, "risk_multiplier": float(multiplier), "price_source": key, "trade_count": int(value)}
            for key, value in getattr(engine, "source_counter", Counter()).items()
        ]
    )
    return daily, usage, source_counts


def _build_long_daily(baseline: pd.DataFrame, variant_daily: list[pd.DataFrame]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    base = baseline[["date", "equity", "c3_slippage", "c3_trade_count", "c3_net_pnl"]].copy()
    base.rename(
        columns={
            "equity": "account_equity",
            "c3_slippage": "slippage",
            "c3_trade_count": "trade_count",
            "c3_net_pnl": "net_pnl",
        },
        inplace=True,
    )
    base["variant"] = BASELINE_VARIANT
    base["label"] = "Stage079 same-day baseline"
    rows.append(base)
    for daily in variant_daily:
        rows.append(daily[["date", "account_equity", "slippage", "trade_count", "net_pnl", "variant", "label"]].copy())
    return pd.concat(rows, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)


def _plot(long_daily: pd.DataFrame, summary: pd.DataFrame) -> None:
    keep = [BASELINE_VARIANT]
    pass40 = summary[summary["max_dd_pct"].ge(-40.0)]["variant"].tolist()
    keep.extend(pass40[:3])
    if "stage079_next_real_risk100" not in keep:
        keep.append("stage079_next_real_risk100")
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily[long_daily["variant"].isin(keep)].groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, linewidth=1.1)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=label, linewidth=1.0)
    axes[0].set_title("Stage079 next-real-open risk frontier")
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
        "# Stage203 下一真实窗口固定风险预算前沿",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：真实可成交结构探索；不改入场/出场信号，只调全局风险预算。",
        "- 执行口径：完整日K确认后，所有订单下一真实可交易窗口成交。",
        "- 固定前沿：`risk_multiplier = 1.0/0.9/0.8/0.7/0.6/0.5`，不扫小数。",
        "",
        "## 外部调研判断",
        "",
        "- 真实可成交基准必须遵循事件顺序；风险预算可以是事前固定账户结构，不引入未来函数。",
        "- 本阶段只测试低自由度风险预算前沿，避免按坏窗口局部补丁救结果。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最佳DD40版本：`{decision['best_dd40_variant']}`。",
        f"- 最佳DD40收益保留：`{decision['best_dd40_return_retention_vs_stage079_pct']:.4f}%`。",
        f"- 最佳DD40最大回撤：`{decision['best_dd40_max_dd_pct']:.4f}%`。",
        f"- 最佳DD40 fallback：`{decision['best_dd40_fallback_trade_count']}`。",
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
        _md_table(source_counts.sort_values(["variant", "trade_count"], ascending=[True, False])),
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。风险预算是固定离散前沿，不使用坏窗口特征。",
        "- 运行后过拟合反思：若只能靠相邻小数才过线，不晋级；若粗前沿自然过线，可进入 fallback 清零和多周期审计。",
        "- 运行前继续价值反思：是。Stage202 显示收益仍在，问题是暴露过大。",
        "- 运行后继续价值反思：若出现DD40且收益保留可接受的粗档位，下一步必须先清零真实窗口 fallback。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    baseline = _load_stage079_baseline()
    daily_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    source_frames: list[pd.DataFrame] = []
    for multiplier in RISK_MULTIPLIERS:
        daily, usage, source_counts = _run_variant(multiplier)
        daily_frames.append(daily)
        usage_frames.append(usage)
        source_frames.append(source_counts)
    long_daily = _build_long_daily(baseline, daily_frames)
    summary, horizon, score, cost, gate = s451._evaluate(long_daily)
    usage_all = pd.concat(usage_frames, ignore_index=True) if usage_frames else pd.DataFrame()
    source_all = pd.concat(source_frames, ignore_index=True) if source_frames else pd.DataFrame()

    stage079_return = _safe_float(summary[summary["variant"].eq(BASELINE_VARIANT)]["total_return_pct"].iloc[0])
    fallback_by_variant = (
        usage_all.assign(is_fallback=usage_all["price_source"].astype(str).str.startswith("fallback"))
        .groupby("variant")["is_fallback"]
        .sum()
        .astype(int)
        .to_dict()
        if not usage_all.empty
        else {}
    )
    risk_map = {
        f"stage079_next_real_risk{int(round(multiplier * 100)):03d}": float(multiplier)
        for multiplier in RISK_MULTIPLIERS
    }
    frontier = summary[summary["variant"].isin(risk_map)].copy()
    frontier["risk_multiplier"] = frontier["variant"].map(risk_map)
    frontier["return_retention_vs_stage079_pct"] = frontier["total_return_pct"].astype(float) / stage079_return * 100.0
    frontier["dd40_pass"] = frontier["max_dd_pct"].astype(float).ge(-40.0).astype(int)
    frontier["fallback_trade_count"] = frontier["variant"].map(fallback_by_variant).fillna(0).astype(int)
    frontier = frontier[
        [
            "variant",
            "risk_multiplier",
            "end_equity",
            "total_return_pct",
            "return_retention_vs_stage079_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "dd40_pass",
            "fallback_trade_count",
        ]
    ].sort_values(["dd40_pass", "total_return_pct"], ascending=[False, False])

    passed = frontier[frontier["dd40_pass"].eq(1)].copy()
    best = passed.iloc[0] if not passed.empty else frontier.iloc[0]
    decision_label = (
        "risk_frontier_has_dd40_candidate_need_fallback_cleaning"
        if not passed.empty and _safe_float(best["return_retention_vs_stage079_pct"]) >= 65.0
        else "risk_frontier_no_dd40_return65_candidate"
    )
    decision = {
        "stage": "Stage203",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "best_dd40_variant": str(best["variant"]) if not passed.empty else "",
        "best_dd40_risk_multiplier": _safe_float(best["risk_multiplier"]),
        "best_dd40_end_equity": _safe_float(best["end_equity"]),
        "best_dd40_total_return_pct": _safe_float(best["total_return_pct"]),
        "best_dd40_return_retention_vs_stage079_pct": _safe_float(best["return_retention_vs_stage079_pct"]),
        "best_dd40_max_dd_pct": _safe_float(best["max_dd_pct"]),
        "best_dd40_fallback_trade_count": int(best["fallback_trade_count"]) if not passed.empty else 0,
        "dd40_pass_variants": passed["variant"].tolist(),
        "outputs": {
            "daily": str(DAILY_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "cost": str(COST_PATH),
            "gate": str(GATE_PATH),
            "frontier": str(FRONTIER_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若有DD40候选，优先补齐其下一真实窗口fallback并做冷启动/成本压力复核；否则转向状态依赖风险预算或独立风险源。",
    }

    _plot(long_daily, summary)
    long_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    frontier.to_csv(FRONTIER_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, frontier, source_all, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()

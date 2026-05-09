from __future__ import annotations

import contextlib
import io
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage199_stage78_2015_2019_deep_signal_trace import (
    build_trades_df,
    install_signal_trace_patch,
    normalize_candidates,
    restore_signal_trace_patch,
    to_markdown_table,
)
from analyze_qmt_roll_stage202_stage78_adjusted_continuous_indicator import (
    _fmt,
    _safe_float,
    _safe_int,
    build_signal_mix,
    install_continuous_indicator_on_bars,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION, build_official_stage78_overrides
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage203_stage78_continuous_diff_formal_oos_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage203_stage78_continuous_diff_formal_oos"

ANALYSIS_START: datetime = START_DT
ANALYSIS_END: datetime = END_DT
PRELOAD_START: datetime = PRELOAD_START_DT
CAPITAL: float = 200_000.0

STATS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
YEARLY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_summary_{MODEL_TAG}.csv"
SIGNAL_MIX_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_mix_{MODEL_TAG}.csv"
TRADES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ADJUSTMENT_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_adjustments_{MODEL_TAG}.csv"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def build_formal_summary(
    readiness_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> pd.DataFrame:
    years = range(ANALYSIS_START.year, ANALYSIS_END.year + 1)
    rows: list[dict[str, Any]] = []
    for year in years:
        readiness = readiness_df[readiness_df["year"] == year] if not readiness_df.empty else pd.DataFrame()
        trace = trace_df[trace_df["year"] == year] if not trace_df.empty else pd.DataFrame()
        candidates = candidate_df[candidate_df["year"] == year] if not candidate_df.empty else pd.DataFrame()
        trades = trades_df[trades_df["year"] == year] if not trades_df.empty else pd.DataFrame()
        raw_signal_rows = trace[trace["raw_signal"].fillna("").astype(str) != ""] if not trace.empty else pd.DataFrame()
        final_signal_rows = trace[trace["final_signal"].fillna("").astype(str) != ""] if not trace.empty else pd.DataFrame()
        blocked_rows = (
            raw_signal_rows[raw_signal_rows["final_signal"].fillna("").astype(str) == ""]
            if not raw_signal_rows.empty
            else pd.DataFrame()
        )
        filter_counts = Counter(blocked_rows.get("filter_block_reason", pd.Series(dtype=str)).fillna("").astype(str))
        raw_signal_counts = Counter(raw_signal_rows.get("raw_signal", pd.Series(dtype=str)).fillna("").astype(str))
        rows.append(
            {
                "year": year,
                "mapped_product_days": int(readiness["has_mapping"].sum()) if not readiness.empty else 0,
                "target_bar_product_days": int(readiness["has_target_bar"].sum()) if not readiness.empty else 0,
                "am_inited_product_days": int(readiness["am_inited"].sum()) if not readiness.empty else 0,
                "signal_function_calls": int(len(trace)),
                "indicator_not_ready_count": int((trace["stage"].astype(str) == "indicator_not_ready").sum())
                if not trace.empty
                else 0,
                "raw_signal_count": int(len(raw_signal_rows)),
                "final_signal_count": int(len(final_signal_rows)),
                "filter_block_count": int(len(blocked_rows)),
                "candidate_count": int(len(candidates)),
                "opened_candidate_count": int((candidates["candidate_status"].astype(str) == "opened").sum())
                if not candidates.empty
                else 0,
                "trade_count": int(len(trades)),
                "open_trade_count": int((trades["offset"].astype(str) == "Open").sum()) if not trades.empty else 0,
                "raw_signal_mix": json.dumps(
                    {key: value for key, value in raw_signal_counts.items() if key},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "filter_block_reasons": json.dumps(
                    {key: value for key, value in filter_counts.items() if key},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    return pd.DataFrame(rows)


def run_case(
    case_name: str,
    *,
    continuous_indicator: bool,
    adjust_mode: str = "contract",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    original_on_bars, original_generate_signal = install_signal_trace_patch()
    if continuous_indicator:
        install_continuous_indicator_on_bars(original_on_bars, adjust_mode)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            engine, _, stats = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=build_official_stage78_overrides(),
                analysis_start=ANALYSIS_START,
                analysis_end=ANALYSIS_END,
                preload_start=PRELOAD_START,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{OUTPUT_PREFIX}_{case_name}",
                chart_title=f"Stage203 {case_name}",
            )
    finally:
        restore_signal_trace_patch(original_on_bars, original_generate_signal)

    strategy = engine.strategy
    readiness_df = pd.DataFrame(getattr(strategy, "stage199_readiness_rows", []))
    trace_df = pd.DataFrame(getattr(strategy, "stage199_signal_trace_rows", []))
    adjustment_df = pd.DataFrame(getattr(strategy, "stage202_adjustment_rows", []))
    candidate_df = normalize_candidates(build_entry_candidate_snapshots_df(engine))
    trades_df = build_trades_df(engine)

    if not readiness_df.empty:
        readiness_df["date"] = pd.to_datetime(readiness_df["date"])
        readiness_df["year"] = readiness_df["date"].dt.year
    if not trace_df.empty:
        trace_df["date"] = pd.to_datetime(trace_df["date"])
        trace_df["year"] = trace_df["date"].dt.year
    if not trades_df.empty:
        trades_df.insert(0, "case_name", case_name)
    if not adjustment_df.empty:
        adjustment_df.insert(0, "case_name", case_name)

    yearly = build_formal_summary(
        readiness_df,
        trace_df,
        candidate_df,
        trades_df.drop(columns=["case_name"], errors="ignore"),
    )
    yearly.insert(0, "case_name", case_name)
    signal_mix = build_signal_mix(case_name, trace_df)

    stats_row = {
        "case_name": case_name,
        "continuous_indicator": int(continuous_indicator),
        "adjust_mode": adjust_mode if continuous_indicator else "contract",
        "end_balance": _safe_float(stats.get("end_balance")),
        "total_return_pct": _safe_float(stats.get("total_return")),
        "max_ddpercent": _safe_float(stats.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(stats.get("sharpe_ratio")),
        "total_trade_count": _safe_int(stats.get("total_trade_count")),
        "total_slippage": _safe_float(stats.get("total_slippage")),
        "total_commission": _safe_float(stats.get("total_commission")),
        "win_ratio_pct": _safe_float(stats.get("win_ratio")),
        "raw_signal_count": int(yearly["raw_signal_count"].sum()),
        "final_signal_count": int(yearly["final_signal_count"].sum()),
        "candidate_count": int(yearly["candidate_count"].sum()),
        "opened_candidate_count": int(yearly["opened_candidate_count"].sum()),
        "am_inited_product_days": int(yearly["am_inited_product_days"].sum()),
        "signal_function_calls": int(yearly["signal_function_calls"].sum()),
        "adjustment_count": int(len(adjustment_df)),
    }
    return yearly, signal_mix, trades_df, adjustment_df, stats_row


def write_report(stats_df: pd.DataFrame, yearly_df: pd.DataFrame, signal_mix_df: pd.DataFrame) -> None:
    compact_stats = stats_df[
        [
            "case_name",
            "adjust_mode",
            "end_balance",
            "total_return_pct",
            "max_ddpercent",
            "sharpe_ratio",
            "total_trade_count",
            "total_slippage",
            "raw_signal_count",
            "candidate_count",
            "opened_candidate_count",
            "am_inited_product_days",
            "adjustment_count",
        ]
    ].copy()
    compact_stats["end_balance"] = compact_stats["end_balance"].map(lambda value: _fmt(value, 2))
    compact_stats["total_slippage"] = compact_stats["total_slippage"].map(lambda value: _fmt(value, 2))
    for column in ["total_return_pct", "max_ddpercent", "sharpe_ratio"]:
        compact_stats[column] = compact_stats[column].map(lambda value: _fmt(value, 4))

    yearly_view = yearly_df[
        [
            "case_name",
            "year",
            "am_inited_product_days",
            "signal_function_calls",
            "raw_signal_count",
            "final_signal_count",
            "candidate_count",
            "opened_candidate_count",
            "trade_count",
            "open_trade_count",
            "raw_signal_mix",
            "filter_block_reasons",
        ]
    ].copy()

    report = f"""# Stage203 第78 连续复权指标正式样本反证

## 口径

- 策略版本：`{OFFICIAL_STAGE78_VERSION}`
- 区间：{ANALYSIS_START.date()} 至 {ANALYSIS_END.date()}
- 预加载：{PRELOAD_START.date()}
- 资金：{CAPITAL:,.0f}
- baseline_contract_am：第78正式合约级AM。
- continuous_diff_back_adjust：差值后复权连续主力指标，真实合约执行。
- 本阶段只做只读验证，不改第78正式策略。

## 总体结果

{to_markdown_table(compact_stats, max_rows=20)}

## 年度漏斗

{to_markdown_table(yearly_view, max_rows=120)}

## 原始信号分布

{to_markdown_table(signal_mix_df, max_rows=160)}

## 结论

1. 若 continuous_diff_back_adjust 在2020-2026正式样本收益/回撤/Sharpe明显劣于 baseline，则不能为了修复2015-2019早期信号而合入正式第78。
2. 连续复权指标可以解释早期合约级AM断裂，但它不是免费的改进：信号分布、开仓密度和风控暴露都必须重新过正式样本闸门。
3. 如果正式样本未通过，本方向暂时只保留为诊断工具；下一步回到正式第78的可交易性、T+1和影子盘，而不是修改指标层。

## 过拟合反思

- 本阶段是反证，不根据结果调参，本身不是过拟合。
- 但如果只因为连续指标让2015-2019变好就采用它，会把早期样本修复变成选择性拟合。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yearly_frames: list[pd.DataFrame] = []
    signal_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    adjustment_frames: list[pd.DataFrame] = []
    stats_rows: list[dict[str, Any]] = []

    cases = [
        ("baseline_contract_am", False, "contract"),
        ("continuous_diff_back_adjust", True, "diff_back_adjust"),
    ]
    for case_name, continuous_indicator, adjust_mode in cases:
        print(f"[stage203] run {case_name}")
        yearly, signal_mix, trades, adjustments, stats_row = run_case(
            case_name,
            continuous_indicator=continuous_indicator,
            adjust_mode=adjust_mode,
        )
        yearly_frames.append(yearly)
        signal_frames.append(signal_mix)
        trade_frames.append(trades)
        adjustment_frames.append(adjustments)
        stats_rows.append(stats_row)

    yearly_df = pd.concat(yearly_frames, ignore_index=True)
    signal_mix_df = pd.concat(signal_frames, ignore_index=True)
    trades_df = pd.concat(trade_frames, ignore_index=True)
    adjustment_df = pd.concat(adjustment_frames, ignore_index=True)
    stats_df = pd.DataFrame(stats_rows)

    stats_df.to_csv(STATS_CSV_PATH, index=False, encoding="utf-8-sig")
    yearly_df.to_csv(YEARLY_CSV_PATH, index=False, encoding="utf-8-sig")
    signal_mix_df.to_csv(SIGNAL_MIX_CSV_PATH, index=False, encoding="utf-8-sig")
    trades_df.to_csv(TRADES_CSV_PATH, index=False, encoding="utf-8-sig")
    adjustment_df.to_csv(ADJUSTMENT_CSV_PATH, index=False, encoding="utf-8-sig")
    write_report(stats_df, yearly_df, signal_mix_df)

    print(f"stats: {STATS_CSV_PATH}")
    print(f"yearly: {YEARLY_CSV_PATH}")
    print(f"signal_mix: {SIGNAL_MIX_CSV_PATH}")
    print(f"trades: {TRADES_CSV_PATH}")
    print(f"adjustments: {ADJUSTMENT_CSV_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

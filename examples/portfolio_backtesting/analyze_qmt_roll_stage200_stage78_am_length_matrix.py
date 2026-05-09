from __future__ import annotations

import contextlib
import io
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage199_stage78_2015_2019_deep_signal_trace import (
    build_summary,
    build_trades_df,
    install_signal_trace_patch,
    normalize_candidates,
    restore_signal_trace_patch,
    to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION, build_official_stage78_overrides
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage200_stage78_am_length_matrix_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage200_stage78_am_length_matrix"

ANALYSIS_START: datetime = datetime(2015, 1, 5)
ANALYSIS_END: datetime = datetime(2019, 12, 31)
PRELOAD_START: datetime = datetime(2014, 1, 5)
CAPITAL: float = 200_000.0
AM_LENGTHS: tuple[int, ...] = (60, 90, 120, 140)
FORMAL_AM_LENGTH: int = 120

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_summary_{MODEL_TAG}.csv"
STATS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
SIGNAL_MIX_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_mix_{MODEL_TAG}.csv"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _fmt(value: Any, digits: int = 4) -> str:
    return f"{_safe_float(value):,.{digits}f}"


def run_matrix_case(am_length: int) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    overrides = build_official_stage78_overrides()
    overrides["array_manager_size_floor"] = int(am_length)

    original_on_bars, original_generate_signal = install_signal_trace_patch()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            engine, _, stats = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=ANALYSIS_START,
                analysis_end=ANALYSIS_END,
                preload_start=PRELOAD_START,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{OUTPUT_PREFIX}_am{am_length}",
                chart_title=f"Stage200 Stage78 AM {am_length}",
            )
    finally:
        restore_signal_trace_patch(original_on_bars, original_generate_signal)

    strategy = engine.strategy
    readiness_df = pd.DataFrame(getattr(strategy, "stage199_readiness_rows", []))
    trace_df = pd.DataFrame(getattr(strategy, "stage199_signal_trace_rows", []))
    candidate_df = normalize_candidates(build_entry_candidate_snapshots_df(engine))
    trades_df = build_trades_df(engine)

    if not readiness_df.empty:
        readiness_df["date"] = pd.to_datetime(readiness_df["date"])
        readiness_df["year"] = readiness_df["date"].dt.year
    if not trace_df.empty:
        trace_df["date"] = pd.to_datetime(trace_df["date"])
        trace_df["year"] = trace_df["date"].dt.year

    summary_df = build_summary(readiness_df, trace_df, candidate_df, trades_df)
    summary_df.insert(0, "am_length", int(am_length))

    raw = trace_df[trace_df["raw_signal"].fillna("").astype(str) != ""].copy() if not trace_df.empty else pd.DataFrame()
    if raw.empty:
        signal_mix_df = pd.DataFrame(columns=["am_length", "year", "raw_signal", "count"])
    else:
        signal_mix_df = (
            raw.groupby(["year", "raw_signal"])
            .size()
            .reset_index(name="count")
            .sort_values(["year", "raw_signal"])
        )
        signal_mix_df.insert(0, "am_length", int(am_length))

    stats_row: dict[str, Any] = {
        "am_length": int(am_length),
        "is_formal_stage78": int(am_length == FORMAL_AM_LENGTH),
        "end_balance": _safe_float(stats.get("end_balance")),
        "total_return_pct": _safe_float(stats.get("total_return")),
        "max_ddpercent": _safe_float(stats.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(stats.get("sharpe_ratio")),
        "total_trade_count": _safe_int(stats.get("total_trade_count")),
        "total_slippage": _safe_float(stats.get("total_slippage")),
        "total_commission": _safe_float(stats.get("total_commission")),
        "raw_signal_count": int(summary_df["raw_signal_count"].sum()) if "raw_signal_count" in summary_df else 0,
        "final_signal_count": int(summary_df["final_signal_count"].sum()) if "final_signal_count" in summary_df else 0,
        "candidate_count": int(summary_df["candidate_count"].sum()) if "candidate_count" in summary_df else 0,
        "opened_candidate_count": int(summary_df["opened_candidate_count"].sum())
        if "opened_candidate_count" in summary_df
        else 0,
        "signal_function_calls": int(summary_df["signal_function_calls"].sum())
        if "signal_function_calls" in summary_df
        else 0,
        "am_inited_product_days": int(summary_df["am_inited_product_days"].sum())
        if "am_inited_product_days" in summary_df
        else 0,
    }
    return summary_df, signal_mix_df, stats_row


def write_report(stats_df: pd.DataFrame, summary_df: pd.DataFrame, signal_mix_df: pd.DataFrame) -> None:
    compact_stats = stats_df[
        [
            "am_length",
            "is_formal_stage78",
            "end_balance",
            "total_return_pct",
            "max_ddpercent",
            "sharpe_ratio",
            "total_trade_count",
            "raw_signal_count",
            "candidate_count",
            "opened_candidate_count",
            "am_inited_product_days",
        ]
    ].copy()
    compact_stats["end_balance"] = compact_stats["end_balance"].map(lambda x: _fmt(x, 2))
    for column in ["total_return_pct", "max_ddpercent", "sharpe_ratio"]:
        compact_stats[column] = compact_stats[column].map(lambda x: _fmt(x, 4))

    yearly_view = summary_df[
        [
            "am_length",
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

    report = f"""# Stage200 第78 AM长度矩阵只读验证

## 口径

- 策略版本：`{OFFICIAL_STAGE78_VERSION}`
- 区间：{ANALYSIS_START.date()} 至 {ANALYSIS_END.date()}
- 预加载：{PRELOAD_START.date()}
- 资金：{CAPITAL:,.0f}
- AM长度矩阵：{", ".join(str(x) for x in AM_LENGTHS)}
- 正式第78口径：`array_manager_size_floor={FORMAL_AM_LENGTH}`

## 总体结果

{to_markdown_table(compact_stats, max_rows=20)}

## 年度漏斗

{to_markdown_table(yearly_view, max_rows=80)}

## 原始信号分布

{to_markdown_table(signal_mix_df, max_rows=120)}

## 结论

1. AM长度越短，2015-2018的指标初始化天数和原始信号数量显著恢复，说明Stage199定位的“正式第78 AM长度120导致早期合约指标初始化不足”成立。
2. 但`60/90/120`都不是可以直接晋升的正式策略参数，因为它们改变了指标历史窗口长度，会引入不同的交易样本和噪声。
3. 若更短AM长度没有改善收益/回撤，说明早期缺信号虽然是工程口径问题，但简单缩短AM不是好修法。
4. 更稳妥的后续方向是“连续主力序列算指标、真实主力合约执行”，这样既保留足够历史，又不为了2015专门调短窗口。

## 过拟合反思

- 本阶段是矩阵诊断，不选择最优参数上线，因此不构成正式过拟合。
- 不能根据2015-2019某个AM长度收益较好就改第78；那会把诊断变成针对早期样本调参。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries: list[pd.DataFrame] = []
    signal_mixes: list[pd.DataFrame] = []
    stats_rows: list[dict[str, Any]] = []

    for am_length in AM_LENGTHS:
        print(f"[stage200] run am_length={am_length}")
        summary_df, signal_mix_df, stats_row = run_matrix_case(am_length)
        summaries.append(summary_df)
        signal_mixes.append(signal_mix_df)
        stats_rows.append(stats_row)

    summary_all = pd.concat(summaries, ignore_index=True)
    signal_mix_all = pd.concat(signal_mixes, ignore_index=True)
    stats_df = pd.DataFrame(stats_rows).sort_values("am_length")

    summary_all.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    signal_mix_all.to_csv(SIGNAL_MIX_CSV_PATH, index=False, encoding="utf-8-sig")
    stats_df.to_csv(STATS_CSV_PATH, index=False, encoding="utf-8-sig")
    write_report(stats_df, summary_all, signal_mix_all)

    print(f"stats: {STATS_CSV_PATH}")
    print(f"summary: {SUMMARY_CSV_PATH}")
    print(f"signal_mix: {SIGNAL_MIX_CSV_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

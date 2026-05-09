from __future__ import annotations

import contextlib
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage199_stage78_2015_2019_deep_signal_trace import (
    _fmt,
    _safe_int,
    build_summary,
    build_trades_df,
    install_signal_trace_patch,
    normalize_candidates,
    restore_signal_trace_patch,
    to_markdown_table,
)
from analyze_qmt_roll_stage205_stage78_fu_legal_mapping_counterfactual import (
    LEGAL_MAPPING_PATH,
    build_fu_legal_mapping,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION, build_official_stage78_overrides
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage206_stage78_fu_legal_signal_funnel_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage206_stage78_fu_legal_signal_funnel"

ANALYSIS_START: datetime = datetime(2015, 1, 5)
ANALYSIS_END: datetime = datetime(2019, 12, 31)
PRELOAD_START: datetime = datetime(2014, 1, 5)
CAPITAL: float = 200_000.0

READINESS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
SIGNAL_TRACE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_trace_{MODEL_TAG}.csv"
CANDIDATES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STATS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
PRODUCT_READINESS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_readiness_{MODEL_TAG}.csv"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def run_profile(profile_name: str, mapping_path: Path | None) -> dict[str, Any]:
    original_on_bars, original_generate_signal = install_signal_trace_patch()
    overrides = build_official_stage78_overrides()
    if mapping_path is not None:
        overrides["mapping_csv_path"] = str(mapping_path)

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
                file_prefix=f"{OUTPUT_PREFIX}_{profile_name}",
                chart_title=f"Stage206 {profile_name}",
            )
    finally:
        restore_signal_trace_patch(original_on_bars, original_generate_signal)

    strategy = engine.strategy
    readiness_df = pd.DataFrame(getattr(strategy, "stage199_readiness_rows", []))
    trace_df = pd.DataFrame(getattr(strategy, "stage199_signal_trace_rows", []))
    candidate_df = normalize_candidates(build_entry_candidate_snapshots_df(engine))
    trades_df = build_trades_df(engine)

    for frame in (readiness_df, trace_df, candidate_df, trades_df):
        if not frame.empty:
            frame.insert(0, "profile_name", profile_name)

    if not readiness_df.empty:
        readiness_df["date"] = pd.to_datetime(readiness_df["date"])
        readiness_df["year"] = readiness_df["date"].dt.year
    if not trace_df.empty:
        trace_df["date"] = pd.to_datetime(trace_df["date"])
        trace_df["year"] = trace_df["date"].dt.year

    summary_df = build_summary(
        readiness_df.drop(columns=["profile_name"], errors="ignore"),
        trace_df.drop(columns=["profile_name"], errors="ignore"),
        candidate_df.drop(columns=["profile_name"], errors="ignore"),
        trades_df.drop(columns=["profile_name"], errors="ignore"),
    )
    summary_df.insert(0, "profile_name", profile_name)

    stats_row = {
        "profile_name": profile_name,
        "mapping_csv_path": str(mapping_path or ""),
        "end_balance": _safe_float(stats.get("end_balance")),
        "total_return_pct": _safe_float(stats.get("total_return")),
        "max_ddpercent": _safe_float(stats.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(stats.get("sharpe_ratio")),
        "total_trade_count": _safe_int(stats.get("total_trade_count")),
        "total_slippage": _safe_float(stats.get("total_slippage")),
        "raw_signal_count": int(summary_df["raw_signal_count"].sum()),
        "final_signal_count": int(summary_df["final_signal_count"].sum()),
        "candidate_count": int(summary_df["candidate_count"].sum()),
        "opened_candidate_count": int(summary_df["opened_candidate_count"].sum()),
        "am_inited_product_days": int(summary_df["am_inited_product_days"].sum()),
        "signal_function_calls": int(summary_df["signal_function_calls"].sum()),
    }

    return {
        "readiness": readiness_df,
        "trace": trace_df,
        "candidates": candidate_df,
        "trades": trades_df,
        "summary": summary_df,
        "stats": stats_row,
    }


def build_product_readiness(readiness_df: pd.DataFrame) -> pd.DataFrame:
    if readiness_df.empty:
        return pd.DataFrame()
    grouped = (
        readiness_df.groupby(["profile_name", "year", "product_vt_symbol"], as_index=False)
        .agg(
            has_mapping_days=("has_mapping", "sum"),
            has_target_bar_days=("has_target_bar", "sum"),
            am_inited_days=("am_inited", "sum"),
        )
        .sort_values(["profile_name", "year", "am_inited_days", "product_vt_symbol"], ascending=[True, True, True, True])
    )
    grouped["target_bar_gap"] = grouped["has_mapping_days"] - grouped["has_target_bar_days"]
    grouped["am_init_gap"] = grouped["has_target_bar_days"] - grouped["am_inited_days"]
    return grouped


def write_report(
    *,
    stats_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    product_readiness_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    mapping_info: dict[str, Any],
) -> None:
    stats_view = stats_df.copy()
    stats_view["end_balance"] = stats_view["end_balance"].map(lambda value: _fmt(value, 2))
    stats_view["total_slippage"] = stats_view["total_slippage"].map(lambda value: _fmt(value, 2))
    for column in ["total_return_pct", "max_ddpercent", "sharpe_ratio"]:
        stats_view[column] = stats_view[column].map(lambda value: _fmt(value, 4))

    summary_view = summary_df[
        [
            "profile_name",
            "year",
            "mapped_product_days",
            "target_bar_product_days",
            "am_inited_product_days",
            "signal_function_calls",
            "indicator_not_ready_count",
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

    key_products = product_readiness_df[
        product_readiness_df["product_vt_symbol"].isin(["fu.SHFE", "SM.CZCE"])
    ].copy()
    key_products = key_products.sort_values(["profile_name", "product_vt_symbol", "year"])

    raw_signals = trace_df[trace_df["raw_signal"].fillna("").astype(str) != ""].copy()
    raw_signal_view = raw_signals[
        [
            "profile_name",
            "date",
            "product_vt_symbol",
            "contract_vt_symbol",
            "raw_signal",
            "final_signal",
            "filter_block_reason",
            "pattern_case",
        ]
    ].copy() if not raw_signals.empty else pd.DataFrame()

    candidate_view = candidate_df[
        [
            "profile_name",
            "date",
            "product_vt_symbol",
            "contract_vt_symbol",
            "direction",
            "signal",
            "candidate_status",
            "skip_reason",
        ]
    ].copy() if not candidate_df.empty else pd.DataFrame()

    report = f"""# Stage206 第78 fu合法映射信号漏斗复核

## 口径

- 策略版本：`{OFFICIAL_STAGE78_VERSION}`
- 区间：{ANALYSIS_START.date()} 至 {ANALYSIS_END.date()}
- 预加载：{PRELOAD_START.date()}
- 资金：{CAPITAL:,.0f}
- baseline_original_mapping：原始全市场主力映射。
- fu_legal_from_20180716：沿用Stage205生成映射，2018-07-16前`fu.SHFE`不参与映射。
- 生成映射：`{mapping_info['legal_mapping_path']}`
- 本阶段只做信号漏斗复核，不改第78正式参数。

## 回测与漏斗汇总

{to_markdown_table(stats_view, max_rows=20)}

## 年度漏斗

{to_markdown_table(summary_view, max_rows=20)}

## fu/SM产品级就绪

{to_markdown_table(key_products, max_rows=80)}

## 原始信号明细

{to_markdown_table(raw_signal_view, max_rows=80)}

## 候选记录

{to_markdown_table(candidate_view, max_rows=80)}

## 成交记录

{to_markdown_table(trades_df, max_rows=80)}

## 判断

1. 如果`fu_legal_from_20180716`显著提升`target_bar_product_days`但`am_inited_product_days/raw_signal_count/candidate_count`仍没有恢复，说明早期无交易不是数据覆盖率本身造成。
2. 如果两组成交完全一致，说明第78历史交易结论不依赖老燃料油缺失映射。
3. 下一步不应为了让2015-2017有交易而放宽入场过滤器；更合理的是把2015-2017标记为第78正式规则的低/无交易冷启动段。

## 过拟合反思

- 本阶段只是同策略、同参数、不同历史合法映射的诊断，不构成过拟合。
- 若后续按早期无交易去调短AM或过滤器，则会构成明显样本定向优化，必须禁止直接合入。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    legal_mapping_path, mapping_info = build_fu_legal_mapping()
    if not legal_mapping_path.exists():
        raise FileNotFoundError(f"legal mapping not found: {legal_mapping_path}")

    profiles: tuple[tuple[str, Path | None], ...] = (
        ("baseline_original_mapping", None),
        ("fu_legal_from_20180716", LEGAL_MAPPING_PATH),
    )

    results: list[dict[str, Any]] = []
    for profile_name, mapping_path in profiles:
        print(f"[stage206] run {profile_name}", flush=True)
        results.append(run_profile(profile_name, mapping_path))

    readiness_df = pd.concat([result["readiness"] for result in results], ignore_index=True)
    trace_df = pd.concat([result["trace"] for result in results], ignore_index=True)
    candidate_df = pd.concat([result["candidates"] for result in results], ignore_index=True)
    trades_df = pd.concat([result["trades"] for result in results], ignore_index=True)
    summary_df = pd.concat([result["summary"] for result in results], ignore_index=True)
    stats_df = pd.DataFrame([result["stats"] for result in results])
    product_readiness_df = build_product_readiness(readiness_df)

    readiness_df.to_csv(READINESS_CSV_PATH, index=False, encoding="utf-8-sig")
    trace_df.to_csv(SIGNAL_TRACE_CSV_PATH, index=False, encoding="utf-8-sig")
    candidate_df.to_csv(CANDIDATES_CSV_PATH, index=False, encoding="utf-8-sig")
    trades_df.to_csv(TRADES_CSV_PATH, index=False, encoding="utf-8-sig")
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    stats_df.to_csv(STATS_CSV_PATH, index=False, encoding="utf-8-sig")
    product_readiness_df.to_csv(PRODUCT_READINESS_CSV_PATH, index=False, encoding="utf-8-sig")
    write_report(
        stats_df=stats_df,
        summary_df=summary_df,
        product_readiness_df=product_readiness_df,
        trace_df=trace_df,
        candidate_df=candidate_df,
        trades_df=trades_df,
        mapping_info=mapping_info,
    )

    print(f"stats: {STATS_CSV_PATH}")
    print(f"summary: {SUMMARY_CSV_PATH}")
    print(f"product_readiness: {PRODUCT_READINESS_CSV_PATH}")
    print(f"readiness: {READINESS_CSV_PATH}")
    print(f"signal_trace: {SIGNAL_TRACE_CSV_PATH}")
    print(f"candidates: {CANDIDATES_CSV_PATH}")
    print(f"trades: {TRADES_CSV_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

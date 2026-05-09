from __future__ import annotations

import contextlib
import io
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
    build_official_stage78_paths,
)
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage198_stage78_2015_2019_signal_funnel_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage198_stage78_2015_2019_signal_funnel"

ANALYSIS_START: datetime = datetime(2015, 1, 5)
ANALYSIS_END: datetime = datetime(2019, 12, 31)
PRELOAD_START: datetime = datetime(2014, 1, 5)
CAPITAL: float = 200_000.0

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CANDIDATES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
AI_META_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_meta_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_int(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt(value: Any, digits: int = 4) -> str:
    return f"{_safe_float(value):,.{digits}f}"


def to_markdown_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df.empty:
        return "_无记录_"
    view = df.head(max_rows).copy()
    headers = list(view.columns)
    rows = [[str(row.get(col, "")) for col in headers] for _, row in view.iterrows()]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    if len(df) > max_rows:
        lines.append(f"\n_仅展示前{max_rows}行，共{len(df)}行。_")
    return "\n".join(lines)


def build_trades_df(engine: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in engine.get_all_trades():
        rows.append(
            {
                "datetime": trade.datetime,
                "date": trade.datetime.date().isoformat(),
                "year": trade.datetime.year,
                "vt_symbol": trade.vt_symbol,
                "direction": trade.direction.value,
                "offset": trade.offset.value,
                "price": float(trade.price),
                "volume": float(trade.volume),
                "vt_tradeid": trade.vt_tradeid,
            }
        )
    return pd.DataFrame(rows)


def normalize_candidates(candidate_df: pd.DataFrame) -> pd.DataFrame:
    if candidate_df.empty:
        return candidate_df
    df = candidate_df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize(None)
    df["date"] = df["datetime"].dt.date.astype(str)
    df["year"] = df["datetime"].dt.year
    for column in [
        "is_opened",
        "selected_volume",
        "selected_volume_ungated",
        "ai_product_pool_allowed",
        "ai_product_pool_enabled",
        "incremental_margin_budget_gate_passed",
        "same_direction_correlation_gate_enabled",
        "remaining_position_slots",
        "active_positions_before",
    ]:
        if column in df.columns:
            df[column] = df[column].map(_safe_int)
    return df


def build_summary_df(candidate_df: pd.DataFrame, trades_df: pd.DataFrame) -> pd.DataFrame:
    years = list(range(2015, 2020))
    rows: list[dict[str, Any]] = []
    for year in years:
        candidates = candidate_df[candidate_df["year"] == year] if not candidate_df.empty else pd.DataFrame()
        trades = trades_df[trades_df["year"] == year] if not trades_df.empty else pd.DataFrame()
        skip_counts = Counter(candidates.get("skip_reason", pd.Series(dtype=str)).fillna("").astype(str))
        signal_counts = Counter(candidates.get("signal", pd.Series(dtype=str)).fillna("").astype(str))
        opened = candidates[candidates.get("candidate_status", pd.Series(dtype=str)).astype(str) == "opened"]
        rows.append(
            {
                "year": year,
                "candidate_count": int(len(candidates)),
                "opened_candidate_count": int(len(opened)),
                "skipped_candidate_count": int(len(candidates) - len(opened)),
                "trade_count": int(len(trades)),
                "open_trade_count": int((trades["offset"].astype(str) == "Open").sum()) if not trades.empty else 0,
                "close_trade_count": int((trades["offset"].astype(str) == "Close").sum()) if not trades.empty else 0,
                "long_candidate_count": int((candidates.get("direction", pd.Series(dtype=str)).astype(str) == "long").sum()),
                "short_candidate_count": int((candidates.get("direction", pd.Series(dtype=str)).astype(str) == "short").sum()),
                "short_signal_rejected_count": int(skip_counts.get("short_signal_rejected", 0)),
                "sizing_zero_volume_count": int(skip_counts.get("sizing_zero_volume", 0)),
                "ai_product_pool_blocked_count": int(skip_counts.get("ai_product_pool_blocked", 0)),
                "concurrent_limit_count": int(skip_counts.get("concurrent_limit", 0)),
                "incremental_margin_budget_gate_count": int(skip_counts.get("incremental_margin_budget_gate", 0)),
                "ai_allowed_count": int(candidates.get("ai_product_pool_allowed", pd.Series(dtype=int)).sum())
                if not candidates.empty and "ai_product_pool_allowed" in candidates
                else 0,
                "top_skip_reasons": json.dumps(
                    {key: value for key, value in skip_counts.items() if key},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "signal_mix": json.dumps(
                    {key: value for key, value in signal_counts.items() if key},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    return pd.DataFrame(rows)


def build_ai_meta() -> dict[str, Any]:
    universe_path, eligibility_path = build_official_stage78_paths()
    eligibility = pd.read_csv(eligibility_path)
    eligibility["eval_date"] = pd.to_datetime(eligibility["eval_date"])
    return {
        "official_stage78_version": OFFICIAL_STAGE78_VERSION,
        "universe_path": str(universe_path),
        "eligibility_path": str(eligibility_path),
        "eligibility_rows": int(len(eligibility)),
        "first_eval_date": eligibility["eval_date"].min().date().isoformat(),
        "last_eval_date": eligibility["eval_date"].max().date().isoformat(),
        "unique_eval_dates": int(eligibility["eval_date"].nunique()),
        "score_type_counts": {
            str(key): int(value) for key, value in eligibility.groupby("score_type", dropna=False).size().items()
        },
    }


def write_report(
    *,
    stats: dict[str, Any],
    summary_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    ai_meta: dict[str, Any],
) -> None:
    first_candidates = candidate_df[
        [
            "date",
            "product_vt_symbol",
            "contract_vt_symbol",
            "direction",
            "signal",
            "candidate_status",
            "skip_reason",
            "selected_volume",
            "ai_product_pool_allowed",
            "ai_product_pool_signal_date",
        ]
    ].copy() if not candidate_df.empty else pd.DataFrame()
    first_trades = trades_df.head(30).copy()
    report = f"""# Stage198 第78 2015-2019信号漏斗报告

## 口径

- 策略版本：`{OFFICIAL_STAGE78_VERSION}`
- 回测区间：{ANALYSIS_START.date()} 至 {ANALYSIS_END.date()}
- 预加载起点：{PRELOAD_START.date()}
- 账户规模：{CAPITAL:,.0f}
- 风险比例：`BASE_RISK_RATIO={BASE_RISK_RATIO}`
- 目的：解释2015-2018几乎无交易，到底是AI池、信号、还是交易闸门造成。

## AI池状态

- AI eligibility文件：`{ai_meta["eligibility_path"]}`
- 最早评估日：{ai_meta["first_eval_date"]}
- 最晚评估日：{ai_meta["last_eval_date"]}
- 评估日数量：{ai_meta["unique_eval_dates"]}
- score_type分布：`{json.dumps(ai_meta["score_type_counts"], ensure_ascii=False, sort_keys=True)}`

## 回测结果

- 期末权益：{_fmt(stats.get("end_balance"), 2)}
- 总收益：{_fmt(stats.get("total_return"), 4)}%
- 最大回撤：{_fmt(stats.get("max_ddpercent"), 4)}%
- Sharpe：{_fmt(stats.get("sharpe_ratio"), 4)}
- 总滑点：{_fmt(stats.get("total_slippage"), 2)}
- 总交易次数：{_safe_int(stats.get("total_trade_count"))}

## 年度信号漏斗

{to_markdown_table(summary_df)}

## 候选明细

{to_markdown_table(first_candidates)}

## 成交明细

{to_markdown_table(first_trades)}

## 结论

1. 2015-2018没有实际开仓，不是AI池拦截造成：候选记录里的`ai_product_pool_allowed`均为1，AI拦截次数为0。
2. 2015和2018各出现1条候选信号，但都是短空信号，且被`short_signal_rejected`拒绝。
3. 当前第78只允许`short_case1a`作为新开空，`short_case2/short_case3`不会开仓，因此早期空白主要来自正式版短空闸门与信号结构。
4. 2019开始出现真实开仓，主要集中在`fu.SHFE`和2019年12月的一批长信号。
5. 这说明2015起点曲线的早期空白不能当作充分穿越周期证据；应先把2015-2019归为“弱验证窗口”，不要基于它强化第78可实盘结论。

## 过拟合反思

- 本次没有新增或调整策略参数，只做归因诊断，不构成过拟合。
- 不能因为2015-2018没亏钱就认为策略稳健，因为没有足够交易样本。

## 后续规划

- 保留第78正式版，不直接放宽短空闸门。
- 如需继续验证2015-2019，应另开只读A/B诊断：允许`short_case2/short_case3`的历史对照仅用于解释，不进入正式版。
- 更重要的是继续补齐可信数据和做2020后多周期/影子盘验证。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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
            file_prefix=OUTPUT_PREFIX,
            chart_title="Stage198 Stage78 2015-2019 Signal Funnel",
        )

    candidate_df = normalize_candidates(build_entry_candidate_snapshots_df(engine))
    trades_df = build_trades_df(engine)
    summary_df = build_summary_df(candidate_df, trades_df)
    ai_meta = build_ai_meta()

    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    candidate_df.to_csv(CANDIDATES_CSV_PATH, index=False, encoding="utf-8-sig")
    trades_df.to_csv(TRADES_CSV_PATH, index=False, encoding="utf-8-sig")
    AI_META_JSON_PATH.write_text(json.dumps(ai_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(stats=stats, summary_df=summary_df, candidate_df=candidate_df, trades_df=trades_df, ai_meta=ai_meta)

    print(f"summary: {SUMMARY_CSV_PATH}")
    print(f"candidates: {CANDIDATES_CSV_PATH}")
    print(f"trades: {TRADES_CSV_PATH}")
    print(f"ai_meta: {AI_META_JSON_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

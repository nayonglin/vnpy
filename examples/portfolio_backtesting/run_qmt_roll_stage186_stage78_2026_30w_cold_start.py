from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage172_stage78_forward_shadow_report import (
    STAGE168_CONFIG_PATH,
    _build_signal_plan,
    _classify_target_day,
    _read_json,
    _to_markdown_table,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage186_stage78_2026_50w_cold_start_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage186_stage78_2026_50w_cold_start"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DAILY_REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_report_{MODEL_TAG}.md"
SIGNAL_PLAN_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_plan_{MODEL_TAG}.csv"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _load_saved_artifacts(backtest_prefix: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_path = OUTPUT_DIR / f"{backtest_prefix}_daily.csv"
    trades_path = OUTPUT_DIR / f"{backtest_prefix}_trades_2020_2026_04.csv"
    if not daily_path.exists():
        raise FileNotFoundError(f"missing daily output: {daily_path}")
    daily = pd.read_csv(daily_path, encoding="utf-8-sig", index_col=0)
    daily.index = pd.to_datetime(daily.index, errors="coerce").strftime("%Y-%m-%d")
    trades = pd.read_csv(trades_path, encoding="utf-8-sig") if trades_path.exists() else pd.DataFrame()
    return daily, trades


def _write_daily_report(
    summary: dict[str, Any],
    daily_row: pd.Series,
    risk: dict[str, Any],
    signal_plan: pd.DataFrame,
) -> None:
    lines = [
        "# Stage186 Stage78 2026冷启动50万影子日报",
        "",
        f"- 目标交易日：`{summary['target_date']}`",
        f"- 冷启动日期：`{summary['analysis_start']}`",
        f"- 初始资金：`{summary['capital']:,.0f}`",
        f"- 策略版本：`{OFFICIAL_STAGE78_VERSION}`",
        "- 真实报单：`false`",
        "",
        "## 今日结论",
        "",
        f"- 风险级别：`{risk['risk_level']}`",
        f"- 是否允许影子盘记录：`{risk['allow_shadow_record']}`",
        f"- 是否允许真实新增开仓：`{risk['allow_real_new_orders']}`",
        f"- 触发原因：`{', '.join(risk['reasons'])}`",
        f"- 当日理论信号数：`{len(signal_plan)}`",
        "",
        "## 信号计划",
        "",
        _to_markdown_table(
            signal_plan,
            [
                "shadow_session_id",
                "vt_symbol",
                "direction",
                "offset",
                "volume",
                "theoretical_price",
                "real_t1_open_proxy_price",
                "day_session_open_proxy_price",
                "proxy_quality",
                "exit_reason",
            ],
            max_rows=40,
        ),
        "",
        "## 风险快照",
        "",
        f"- 当日净盈亏：`{risk['net_pnl']:,.0f}`",
        f"- 期末权益：`{risk['balance']:,.0f}`",
        f"- 当前回撤：`{risk['drawdown_pct_abs']:.4f}%`",
        f"- 当日亏损现金：`{risk['daily_loss_cash']:,.0f}`",
        f"- 日度表余额：`{_safe_float(daily_row.get('balance')):,.0f}`",
        f"- 日度表净盈亏：`{_safe_float(daily_row.get('net_pnl')):,.0f}`",
        "",
        "## 反思",
        "",
        "- 运行前过拟合反思：否。固定Stage78，只改变冷启动日期和初始资金。",
        "- 运行后过拟合反思：否。没有根据2026结果调参数。",
        "- 运行前继续价值反思：是。50万冷启动更贴近当前实盘准备。",
        "- 运行后继续价值反思：是。可与全周期继承状态口径对照。",
    ]
    DAILY_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_report(summary: dict[str, Any], signal_plan: pd.DataFrame) -> None:
    lines = [
        "# Stage186 Stage78 2026冷启动50万回放",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略，不修改Stage78参数，不触发A/B。",
        "- 目标是回答：若2026-01-01以50万资金冷启动，第78到目标日会是什么持仓、信号和风控状态。",
        "",
        "## 汇总",
        "",
        f"- 分析区间：`{summary['analysis_start']}` 到 `{summary['analysis_end']}`",
        f"- 初始资金：`{summary['capital']:,.0f}`",
        f"- 期末权益：`{summary['statistics']['end_balance']:,.0f}`",
        f"- 总收益：`{summary['statistics']['total_return']:.4f}%`",
        f"- 最大回撤：`{summary['statistics']['max_ddpercent']:.4f}%`",
        f"- Sharpe：`{summary['statistics']['sharpe_ratio']:.4f}`",
        f"- 目标日信号数：`{summary['target_signal_count']}`",
        f"- 目标日风险级别：`{summary['risk_snapshot']['risk_level']}`",
        f"- 是否允许真实新增开仓：`{summary['risk_snapshot']['allow_real_new_orders']}`",
        "",
        "## 目标日信号",
        "",
        _to_markdown_table(
            signal_plan,
            ["vt_symbol", "direction", "offset", "volume", "theoretical_price", "proxy_quality", "exit_reason"],
            max_rows=40,
        ),
        "",
        "## 输出文件",
        "",
        _to_markdown_table(
            pd.DataFrame([{"artifact": key, "path": value} for key, value in summary["outputs"].items()]),
            ["artifact", "path"],
            max_rows=20,
        ),
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage78 from 2026-01-01 with 500k capital as cold-start shadow.")
    parser.add_argument("--analysis-start", default="2026-01-01")
    parser.add_argument("--target-date", default="2026-05-08")
    parser.add_argument("--capital", type=float, default=OFFICIAL_STAGE78_CAPITAL)
    args = parser.parse_args()

    analysis_start = datetime.strptime(str(args.analysis_start), "%Y-%m-%d")
    analysis_end = datetime.strptime(str(args.target_date), "%Y-%m-%d")
    target_date = analysis_end.date().isoformat()
    capital = float(args.capital)
    capital_tag = f"{int(round(capital / 10000))}w"
    backtest_prefix = f"{OUTPUT_PREFIX}_{analysis_start:%Y%m%d}_{capital_tag}_to_{analysis_end:%Y%m%d}"

    config = _read_json(STAGE168_CONFIG_PATH)
    preload_start = max(datetime(2020, 1, 1), analysis_start - timedelta(days=365))
    strategy_overrides = {
        **build_official_stage78_overrides(),
        "trade_start_date": analysis_start.date().isoformat(),
    }
    _, _, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=strategy_overrides,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        preload_start=preload_start,
        capital=capital,
        save_artifacts=True,
        include_start_year_sweep=False,
        file_prefix=backtest_prefix,
        chart_title="Stage186 Stage78 2026 50w Cold Start",
    )

    summary_row = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        official_version=OFFICIAL_STAGE78_VERSION,
        official_role=OFFICIAL_STAGE78_ROLE,
        window_name="stage186_2026_50w_cold_start",
        display_label="stage186_cold_start",
        strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
        capital=capital,
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
    )
    pd.DataFrame([summary_row]).to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")

    daily_df, trades_df = _load_saved_artifacts(backtest_prefix)
    if target_date not in daily_df.index:
        raise RuntimeError(f"target date {target_date} missing from cold-start daily output")
    daily_row = daily_df.loc[target_date]
    signal_plan = _build_signal_plan(trades_df, target_date)
    risk = _classify_target_day(daily_row, config)
    risk.update({"target_date": target_date, "signal_count": int(len(signal_plan))})
    signal_plan.to_csv(SIGNAL_PLAN_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "is_strategy_change": False,
        "is_backtest": True,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "capital": capital,
        "target_date": target_date,
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "preload_start": preload_start.date().isoformat(),
        "target_signal_count": int(len(signal_plan)),
        "risk_snapshot": risk,
        "statistics": {
            "end_balance": _safe_float(statistics.get("end_balance")),
            "total_return": _safe_float(statistics.get("total_return")),
            "max_ddpercent": _safe_float(statistics.get("max_ddpercent")),
            "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
            "total_slippage": _safe_float(statistics.get("total_slippage")),
            "total_trade_count": _safe_float(statistics.get("total_trade_count")),
            "win_ratio": _safe_float(statistics.get("win_ratio")),
        },
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "judgement": {
            "overfit_before": "否。固定Stage78，只改变冷启动日期和初始资金。",
            "continue_before": "是。50万冷启动更贴近当前实盘准备。",
            "overfit_after": "否。本阶段没有根据2026结果调参。",
            "continue_after": "是。可与全周期继承状态口径对照，并继续做T+1代理价。",
        },
        "outputs": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "daily_report": str(DAILY_REPORT_PATH),
            "signal_plan": str(SIGNAL_PLAN_PATH),
            "report": str(REPORT_PATH),
            "forward_daily": str(OUTPUT_DIR / f"{backtest_prefix}_daily.csv"),
            "forward_trades": str(OUTPUT_DIR / f"{backtest_prefix}_trades_2020_2026_04.csv"),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_daily_report(summary, daily_row, risk, signal_plan)
    _write_report(summary, signal_plan)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"daily report: {DAILY_REPORT_PATH}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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

MODEL_TAG: str = "stage188_stage78_2026_50w_latest_ai_pool_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage188_stage78_2026_50w_latest_ai_pool"

DEFAULT_LATEST_AI_ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_"
    "stage182_ai_product_pool_live_inference_v1.csv"
)
STAGE186_SUMMARY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage186_stage78_2026_50w_cold_start_summary_stage186_stage78_2026_50w_cold_start_v1.json"
)

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage186_{MODEL_TAG}.csv"
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


def _load_ai_pool_audit(path: Path, strategy_name: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "rows": 0,
            "min_eval_date": "",
            "max_eval_date": "",
            "unique_eval_dates": 0,
            "latest_products": [],
        }
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "strategy" in df.columns:
        df = df[df["strategy"].astype(str).eq(str(strategy_name))].copy()
    if df.empty or "eval_date" not in df.columns:
        return {
            "path": str(path),
            "exists": True,
            "rows": int(len(df)),
            "min_eval_date": "",
            "max_eval_date": "",
            "unique_eval_dates": 0,
            "latest_products": [],
        }
    df["eval_date"] = pd.to_datetime(df["eval_date"], errors="coerce").dt.normalize()
    latest_date = df["eval_date"].max()
    latest = df[df["eval_date"].eq(latest_date)].copy()
    latest.sort_values(["score_rank", "product_vt_symbol"], inplace=True)
    return {
        "path": str(path),
        "exists": True,
        "rows": int(len(df)),
        "min_eval_date": df["eval_date"].min().date().isoformat(),
        "max_eval_date": latest_date.date().isoformat(),
        "unique_eval_dates": int(df["eval_date"].nunique()),
        "latest_products": latest["product_vt_symbol"].astype(str).tolist(),
    }


def _build_comparison(summary: dict[str, Any]) -> pd.DataFrame:
    old_summary = _read_json(STAGE186_SUMMARY_PATH) if STAGE186_SUMMARY_PATH.exists() else {}
    old_stats = old_summary.get("statistics", {})
    new_stats = summary.get("statistics", {})
    rows: list[dict[str, Any]] = []
    for key in ["end_balance", "total_return", "max_ddpercent", "sharpe_ratio", "total_slippage", "total_trade_count", "win_ratio"]:
        old_value = _safe_float(old_stats.get(key))
        new_value = _safe_float(new_stats.get(key))
        rows.append(
            {
                "metric": key,
                "stage186_old_pool": old_value,
                "stage188_latest_ai_pool": new_value,
                "delta": new_value - old_value,
            }
        )
    rows.append(
        {
            "metric": "target_signal_count",
            "stage186_old_pool": int(old_summary.get("target_signal_count", 0) or 0),
            "stage188_latest_ai_pool": int(summary.get("target_signal_count", 0) or 0),
            "delta": int(summary.get("target_signal_count", 0) or 0) - int(old_summary.get("target_signal_count", 0) or 0),
        }
    )
    return pd.DataFrame(rows)


def _write_daily_report(
    summary: dict[str, Any],
    daily_row: pd.Series,
    risk: dict[str, Any],
    signal_plan: pd.DataFrame,
    comparison: pd.DataFrame,
) -> None:
    lines = [
        "# Stage188 Stage78 2026冷启动50万最新AI池影子日报",
        "",
        f"- 目标交易日：`{summary['target_date']}`",
        f"- 冷启动日期：`{summary['analysis_start']}`",
        f"- 初始资金：`{summary['capital']:,.0f}`",
        f"- 策略版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- AI池文件：`{summary['ai_pool_audit']['path']}`",
        f"- AI池最新eval_date：`{summary['ai_pool_audit']['max_eval_date']}`",
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
        "## 对比Stage186旧池",
        "",
        _to_markdown_table(comparison, ["metric", "stage186_old_pool", "stage188_latest_ai_pool", "delta"], max_rows=20),
        "",
        "## 反思",
        "",
        "- 运行前过拟合反思：否。固定Stage78，只补齐月度AI池时序输入。",
        "- 运行后过拟合反思：否。没有根据结果调参数或挑月份。",
        "- 运行前继续价值反思：是。影子盘需要确认最新AI池是否改变信号。",
        "- 运行后继续价值反思：是。可作为月度AI池接入后的冷启动主对照。",
    ]
    DAILY_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_report(summary: dict[str, Any], signal_plan: pd.DataFrame, comparison: pd.DataFrame) -> None:
    lines = [
        "# Stage188 Stage78 2026冷启动50万最新AI池回放",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略，不修改Stage78参数，不触发A/B。",
        "- 目标是回答：如果把Stage182生成的最新月度AI池接入，2026-01-01以来50万冷启动回放是否变化。",
        "",
        "## AI池审计",
        "",
        f"- 文件：`{summary['ai_pool_audit']['path']}`",
        f"- 最早eval_date：`{summary['ai_pool_audit']['min_eval_date']}`",
        f"- 最新eval_date：`{summary['ai_pool_audit']['max_eval_date']}`",
        f"- eval_date数量：`{summary['ai_pool_audit']['unique_eval_dates']}`",
        f"- 最新池品种：`{', '.join(summary['ai_pool_audit']['latest_products'])}`",
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
        "## 对比Stage186旧池",
        "",
        _to_markdown_table(comparison, ["metric", "stage186_old_pool", "stage188_latest_ai_pool", "delta"], max_rows=20),
        "",
        "## 输出文件",
        "",
        _to_markdown_table(
            pd.DataFrame([{"artifact": key, "path": value} for key, value in summary["outputs"].items()]),
            ["artifact", "path"],
            max_rows=30,
        ),
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage78 2026 50w cold-start with latest monthly AI pool.")
    parser.add_argument("--analysis-start", default="2026-01-01")
    parser.add_argument("--target-date", default="2026-05-08")
    parser.add_argument("--capital", type=float, default=OFFICIAL_STAGE78_CAPITAL)
    parser.add_argument("--ai-eligibility-path", default=str(DEFAULT_LATEST_AI_ELIGIBILITY_PATH))
    args = parser.parse_args()

    analysis_start = datetime.strptime(str(args.analysis_start), "%Y-%m-%d")
    analysis_end = datetime.strptime(str(args.target_date), "%Y-%m-%d")
    target_date = analysis_end.date().isoformat()
    capital = float(args.capital)
    capital_tag = f"{int(round(capital / 10000))}w"
    backtest_prefix = f"{OUTPUT_PREFIX}_{analysis_start:%Y%m%d}_{capital_tag}_to_{analysis_end:%Y%m%d}"

    ai_eligibility_path = Path(str(args.ai_eligibility_path)).expanduser().resolve()
    config = _read_json(STAGE168_CONFIG_PATH)
    preload_start = max(datetime(2020, 1, 1), analysis_start - timedelta(days=365))
    strategy_overrides = {
        **build_official_stage78_overrides(),
        "ai_product_pool_eligibility_path": str(ai_eligibility_path),
        "trade_start_date": analysis_start.date().isoformat(),
    }
    ai_pool_audit = _load_ai_pool_audit(ai_eligibility_path, str(strategy_overrides["ai_product_pool_strategy"]))

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
        chart_title="Stage188 Stage78 2026 50w Latest AI Pool",
    )

    summary_row = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        official_version=OFFICIAL_STAGE78_VERSION,
        official_role=OFFICIAL_STAGE78_ROLE,
        window_name="stage188_2026_50w_latest_ai_pool",
        display_label="stage188_latest_ai_pool",
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
        raise RuntimeError(f"target date {target_date} missing from latest-ai-pool daily output")
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
        "ai_pool_audit": ai_pool_audit,
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
            "overfit_before": "否。固定Stage78，只补齐月度AI池时序输入。",
            "continue_before": "是。影子盘需要确认最新AI池是否改变信号。",
            "overfit_after": "否。本阶段没有根据2026结果调参。",
            "continue_after": "是。可作为月度AI池接入后的冷启动对照。",
        },
        "outputs": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "comparison_csv": str(COMPARISON_CSV_PATH),
            "daily_report": str(DAILY_REPORT_PATH),
            "signal_plan": str(SIGNAL_PLAN_PATH),
            "report": str(REPORT_PATH),
            "forward_daily": str(OUTPUT_DIR / f"{backtest_prefix}_daily.csv"),
            "forward_trades": str(OUTPUT_DIR / f"{backtest_prefix}_trades_2020_2026_04.csv"),
            "chart_html": str(OUTPUT_DIR / f"{backtest_prefix}_chart.html"),
            "professional_dashboard_html": str(OUTPUT_DIR / f"{backtest_prefix}_professional_dashboard.html"),
            "trade_review_html": str(OUTPUT_DIR / f"{backtest_prefix}_trade_review.html"),
        },
    }
    comparison = _build_comparison(summary)
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_daily_report(summary, daily_row, risk, signal_plan, comparison)
    _write_report(summary, signal_plan, comparison)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"daily report: {DAILY_REPORT_PATH}")


if __name__ == "__main__":
    main()

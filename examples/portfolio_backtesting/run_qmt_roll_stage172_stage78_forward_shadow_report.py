from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
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


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage172_stage78_forward_shadow_report_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage172_stage78_forward_shadow_report"
BACKTEST_PREFIX: str = "qmt_roll_stage172_stage78_forward_20260507"
STAGE168_PREFIX: str = "qmt_roll_stage168_30w_qmt_shadow_startup"
STAGE168_TAG: str = "stage168_30w_qmt_shadow_startup_v1"

STAGE168_CONFIG_PATH: Path = OUTPUT_DIR / f"{STAGE168_PREFIX}_config_{STAGE168_TAG}.json"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DAILY_REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_report_{MODEL_TAG}.md"
SIGNAL_PLAN_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_plan_{MODEL_TAG}.csv"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _set_backtest_prefix(target_date: str) -> None:
    global BACKTEST_PREFIX
    BACKTEST_PREFIX = f"qmt_roll_stage172_stage78_forward_{target_date.replace('-', '')}"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _classify_target_day(daily_row: pd.Series, config: dict[str, Any]) -> dict[str, Any]:
    risk_policy = config["risk_policy"]
    account = config["account_boundary"]
    dd_abs = abs(min(_safe_float(daily_row.get("ddpercent")), 0.0))
    net_pnl = _safe_float(daily_row.get("net_pnl"))
    daily_loss = abs(min(net_pnl, 0.0))
    execution_adverse = 0.0
    level = "normal"
    reasons: list[str] = []
    allow_real_new_orders = 1

    if dd_abs >= account["drawdown_stop_pct"]:
        level = "stop"
        allow_real_new_orders = 0
        reasons.append("drawdown_stop")
    elif dd_abs >= account["drawdown_review_pct"]:
        level = "review"
        reasons.append("drawdown_review")
    elif dd_abs >= account["drawdown_warn_pct"]:
        level = "watch"
        reasons.append("drawdown_watch")

    if daily_loss >= risk_policy["daily_loss_no_new_orders_cash"]:
        level = "stop"
        allow_real_new_orders = 0
        reasons.append("daily_loss_no_new_orders")
    elif daily_loss >= risk_policy["daily_loss_review_cash"] and level != "stop":
        level = "review"
        reasons.append("daily_loss_review")
    elif daily_loss >= risk_policy["daily_loss_watch_cash"] and level == "normal":
        level = "watch"
        reasons.append("daily_loss_watch")

    if level in {"review", "stop"}:
        allow_real_new_orders = 0

    return {
        "risk_level": level,
        "allow_shadow_record": 1,
        "allow_real_new_orders": int(allow_real_new_orders),
        "reasons": reasons or ["none"],
        "drawdown_pct_abs": dd_abs,
        "daily_loss_cash": daily_loss,
        "net_pnl": net_pnl,
        "balance": _safe_float(daily_row.get("balance")),
        "execution_adverse_cash": execution_adverse,
    }


def _build_signal_plan(trades_df: pd.DataFrame, target_date: str) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame(
            columns=[
                "shadow_session_id",
                "trade_id",
                "vt_symbol",
                "direction",
                "offset",
                "volume",
                "theoretical_price",
                "real_t1_open_proxy_price",
                "day_session_open_proxy_price",
                "proxy_quality",
                "exit_reason",
            ]
        )
    frame = trades_df.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame = frame[frame["date"] == target_date].copy()
    if frame.empty:
        return _build_signal_plan(pd.DataFrame(), target_date)
    frame["shadow_session_id"] = frame["trade_id"].map(lambda value: f"STAGE78FWD-{target_date.replace('-', '')}-{value}")
    frame["real_t1_open_proxy_price"] = ""
    frame["day_session_open_proxy_price"] = ""
    frame["proxy_quality"] = "requires_next_trading_session_minute_or_qmt_bar"
    frame.rename(columns={"price": "theoretical_price"}, inplace=True)
    columns = [
        "shadow_session_id",
        "trade_id",
        "vt_symbol",
        "direction",
        "offset",
        "volume",
        "theoretical_price",
        "real_t1_open_proxy_price",
        "day_session_open_proxy_price",
        "proxy_quality",
        "exit_reason",
    ]
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame.loc[:, columns].sort_values(["vt_symbol", "trade_id"]).reset_index(drop=True)


def _load_saved_artifacts() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_path = OUTPUT_DIR / f"{BACKTEST_PREFIX}_daily.csv"
    trades_path = OUTPUT_DIR / f"{BACKTEST_PREFIX}_trades_2020_2026_04.csv"
    daily = pd.read_csv(daily_path, encoding="utf-8-sig", index_col=0)
    daily.index = pd.to_datetime(daily.index, errors="coerce").strftime("%Y-%m-%d")
    trades = pd.read_csv(trades_path, encoding="utf-8-sig") if trades_path.exists() else pd.DataFrame()
    return daily, trades


def _write_daily_report(
    target_date: str,
    config: dict[str, Any],
    daily_row: pd.Series,
    risk: dict[str, Any],
    signal_plan: pd.DataFrame,
    statistics: dict[str, Any],
) -> None:
    lines = [
        "# Stage172 Stage78前向影子盘日报",
        "",
        f"- 目标交易日：`{target_date}`",
        f"- 策略版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 影子资金边界：`{config['account_boundary']['shadow_capital']:,.0f}`",
        "- 运行模式：`forward_backtest_signal_only`",
        "- 真实报单：`false`",
        "- 夜盘自动报单：`false`",
        "",
        "## 今日结论",
        "",
        f"- 风险级别：`{risk['risk_level']}`",
        f"- 是否允许影子盘记录：`{risk['allow_shadow_record']}`",
        f"- 是否允许真实新增开仓：`{risk['allow_real_new_orders']}`",
        f"- 触发原因：`{', '.join(risk['reasons'])}`",
        f"- 当日Stage78理论信号数：`{len(signal_plan)}`",
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
        f"- 总交易次数：`{_safe_float(statistics.get('total_trade_count')):,.0f}`",
        f"- 总滑点：`{_safe_float(statistics.get('total_slippage')):,.0f}`",
        "",
        "## 异常与缺口",
        "",
        "- `real_t1_open_proxy_price`和`day_session_open_proxy_price`仍需下一交易时段分钟线或QMT行情补齐。",
        "- 本日报仍是前向回测信号日报，不包含真实QMT资金、持仓、委托、成交对账。",
        "",
        "## 反思",
        "",
        "- 运行前过拟合反思：否。固定Stage78，只把行情更新后的目标日信号落表。",
        "- 运行后过拟合反思：否。没有因目标日结果修改参数。",
        "- 运行前继续价值反思：是。前向日报能验证影子盘流程是否追上真实日期。",
        "- 运行后继续价值反思：是。下一步接QMT只读和T+1代理价即可进入真实对账。",
    ]
    DAILY_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_report(summary: dict[str, Any], signal_plan: pd.DataFrame) -> None:
    lines = [
        "# Stage172 Stage78前向信号日报生成",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略，不修改Stage78参数，不触发A/B。",
        "- 目标是使用Stage171补齐后的行情，把冻结Stage78跑到2026-05-07，并生成目标日影子盘信号日报。",
        "",
        "## 汇总",
        "",
        f"- 目标交易日：`{summary['target_date']}`",
        f"- 分析区间：`{summary['analysis_start']}` 到 `{summary['analysis_end']}`",
        f"- 期末权益：`{summary['statistics']['end_balance']:,.0f}`",
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
        "## 反思",
        "",
        f"- 运行前过拟合反思：{summary['judgement']['overfit_before']}",
        f"- 运行前继续价值反思：{summary['judgement']['continue_before']}",
        f"- 运行后过拟合反思：{summary['judgement']['overfit_after']}",
        f"- 运行后继续价值反思：{summary['judgement']['continue_after']}",
        "",
        "## 输出文件",
        "",
        _to_markdown_table(pd.DataFrame([{"artifact": key, "path": value} for key, value in summary["outputs"].items()]), ["artifact", "path"], max_rows=20),
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen Stage78 forward and build target shadow report.")
    parser.add_argument("--target-date", default="2026-05-07", help="Target decision date, YYYY-MM-DD.")
    parser.add_argument("--analysis-start", default="2020-01-01", help="Analysis start, YYYY-MM-DD.")
    args = parser.parse_args()

    target_date = args.target_date
    _set_backtest_prefix(target_date)
    analysis_start = datetime.strptime(args.analysis_start, "%Y-%m-%d")
    analysis_end = datetime.strptime(target_date, "%Y-%m-%d")
    config = _read_json(STAGE168_CONFIG_PATH)
    strategy_overrides = build_official_stage78_overrides()

    engine, analysis_df, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=strategy_overrides,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=True,
        include_start_year_sweep=False,
        file_prefix=BACKTEST_PREFIX,
        chart_title="QMT Roll Stage172 Stage78 Forward Shadow",
    )

    summary_row = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        official_version=OFFICIAL_STAGE78_VERSION,
        official_role=OFFICIAL_STAGE78_ROLE,
        window_name="stage172_forward_to_target",
        display_label="stage172_forward",
        strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
    )
    pd.DataFrame([summary_row]).to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")

    daily_df, trades_df = _load_saved_artifacts()
    if target_date not in daily_df.index:
        raise RuntimeError(f"target date {target_date} missing from daily output")
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
        "target_date": target_date,
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "target_signal_count": int(len(signal_plan)),
        "risk_snapshot": risk,
        "statistics": {
            "end_balance": _safe_float(statistics.get("end_balance")),
            "total_return": _safe_float(statistics.get("total_return")),
            "max_ddpercent": _safe_float(statistics.get("max_ddpercent")),
            "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
            "total_slippage": _safe_float(statistics.get("total_slippage")),
            "total_trade_count": _safe_float(statistics.get("total_trade_count")),
        },
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "judgement": {
            "overfit_before": "否。Stage172使用冻结Stage78和新增行情，不新增参数。",
            "continue_before": "是。Stage171已补齐行情，必须生成目标日影子日报。",
            "overfit_after": "否。本阶段只更新前向信号产物，没有根据结果改规则。",
            "continue_after": "是。下一步补T+1代理价和QMT只读对账。",
        },
        "outputs": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "daily_report": str(DAILY_REPORT_PATH),
            "signal_plan": str(SIGNAL_PLAN_PATH),
            "report": str(REPORT_PATH),
            "forward_daily": str(OUTPUT_DIR / f"{BACKTEST_PREFIX}_daily.csv"),
            "forward_trades": str(OUTPUT_DIR / f"{BACKTEST_PREFIX}_trades_2020_2026_04.csv"),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_daily_report(target_date, config, daily_row, risk, signal_plan, statistics)
    _write_report(summary, signal_plan)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {DAILY_REPORT_PATH}")


if __name__ == "__main__":
    main()

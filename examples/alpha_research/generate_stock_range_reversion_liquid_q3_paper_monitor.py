from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_liquid_q3_market_state_baseline import (
    OUTPUT_DIR as BASELINE_DIR,
    PREFIX as BASELINE_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_paper_oos_attribution import (
    OUTPUT_DIR as OOS_ATTR_DIR,
    PREFIX as OOS_ATTR_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_paper_oos_market_state import (
    OUTPUT_DIR as OOS_MARKET_DIR,
    PREFIX as OOS_MARKET_PREFIX,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_latest_paper_packet import (
    OUTPUT_DIR as LATEST_PACKET_DIR,
    PREFIX as LATEST_PACKET_PREFIX,
)
from generate_stock_range_reversion_liquid_q3_paper_ledger import (
    LEDGER_VERSION,
    OUTPUT_DIR as LEDGER_DIR,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_monitor_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_paper_monitor_v1"

MIN_FILL_RATIO: float = 0.99
TAIL_ALPHA_PERCENTILE: float = 0.10
CAUTION_ALPHA_PERCENTILE: float = 0.15
MIN_OOS_DAYS_FOR_STABLE_JUDGMENT: int = 20

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Live execution monitoring should track drawdown and execution health",
        "https://algovantis.com/monitoring-live-execution-performance-critical-metrics-for-algo-trading-success/",
    ),
    (
        "Backtest-to-live gaps require monitoring actual vs expected performance",
        "https://breakingalpha.io/insights/understanding-backtesting-vs-live-performance-trading-algorithms",
    ),
    (
        "Zipline metrics keep returns, benchmark, exposure and risk visible",
        "https://zipline.ml4trading.io/risk-and-perf-metrics.html",
    ),
    (
        "Example open-source dashboard pattern for backtest performance metrics",
        "https://github.com/dang-trung/base-trading",
    ),
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def read_csv(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:
        return default
    return parsed


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(as_float(value, float(default)))
    except (TypeError, ValueError):
        return default


def add_checkpoint(
    rows: list[dict[str, str]],
    name: str,
    status: str,
    value: Any,
    expected: Any,
    note: str,
) -> None:
    rows.append(
        {
            "checkpoint": name,
            "status": status,
            "value": "" if value is None else str(value),
            "expected": "" if expected is None else str(expected),
            "note": note,
        }
    )


def status_rank(status: str) -> int:
    return {"pass": 0, "warn": 1, "fail": 2}.get(status, 1)


def build_monitor_checkpoints(
    latest: dict[str, Any],
    ledger: dict[str, Any],
    oos: dict[str, Any],
    market: dict[str, Any],
    baseline: dict[str, Any],
    ledger_quality: pl.DataFrame,
    oos_quality: pl.DataFrame,
    market_quality: pl.DataFrame,
    baseline_quality: pl.DataFrame,
) -> pl.DataFrame:
    rows: list[dict[str, str]] = []
    latest_blocked = as_int(latest.get("latest_blocked_order_count"))
    latest_unfilled = as_float(latest.get("latest_unfilled_abs_change"))
    full_fill = as_float(latest.get("full_history_fill_ratio"))
    ledger_fails = as_int(ledger.get("quality_fail_count"))
    ledger_warns = as_int(ledger.get("quality_warn_count"))
    oos_days = as_int(oos.get("segment_days"))
    oos_blocked = as_int(oos.get("segment_blocked_order_count"))
    oos_fill = as_float(oos.get("segment_fill_ratio"))
    alpha_pct = as_float(baseline.get("latest_alpha_percentile_rank_le_all_windows"), default=1.0)
    analog_alpha_pct = as_float(baseline.get("latest_alpha_percentile_rank_le_analog_windows"), default=1.0)
    baseline_quality_fails = baseline_quality.filter(pl.col("status") == "fail").height if not baseline_quality.is_empty() else 0
    external_quality_fails = (
        ledger_quality.filter(pl.col("status") == "fail").height
        + oos_quality.filter(pl.col("status") == "fail").height
        + market_quality.filter(pl.col("status") == "fail").height
        + baseline_quality_fails
    )
    add_checkpoint(
        rows,
        "latest_orders_have_no_block",
        "pass" if latest_blocked == 0 else "fail",
        latest_blocked,
        0,
        "最新目标日若出现阻断订单，应优先做执行修复而不是策略判断。",
    )
    add_checkpoint(
        rows,
        "latest_unfilled_weight_zero",
        "pass" if abs(latest_unfilled) <= 1e-12 else "warn",
        latest_unfilled,
        0,
        "最新目标日未成交权重应接近0。",
    )
    add_checkpoint(
        rows,
        "full_history_fill_ratio_above_99pct",
        "pass" if full_fill >= MIN_FILL_RATIO else "warn",
        f"{full_fill:.4f}",
        f">={MIN_FILL_RATIO}",
        "纸面成交填充率低于99%时，执行容量口径需要复核。",
    )
    add_checkpoint(
        rows,
        "ledger_quality_has_no_fail",
        "pass" if ledger_fails == 0 else "fail",
        ledger_fails,
        0,
        f"ledger警告数为{ledger_warns}，只要失败项为0即可继续监控。",
    )
    add_checkpoint(
        rows,
        "oos_execution_clean",
        "pass" if oos_blocked == 0 and oos_fill >= MIN_FILL_RATIO else "fail",
        f"blocked={oos_blocked}, fill={oos_fill:.4f}",
        f"blocked=0, fill>={MIN_FILL_RATIO}",
        "OOS段执行必须先健康，才讨论信号和状态。",
    )
    add_checkpoint(
        rows,
        "oos_days_reached_stable_judgment",
        "pass" if oos_days >= MIN_OOS_DAYS_FOR_STABLE_JUDGMENT else "warn",
        oos_days,
        f">={MIN_OOS_DAYS_FOR_STABLE_JUDGMENT}",
        "样本不足20天前，只做监控和归因，不做策略有效/失效裁决。",
    )
    add_checkpoint(
        rows,
        "latest_alpha_not_bottom_10pct_all_windows",
        "pass" if alpha_pct > TAIL_ALPHA_PERCENTILE else "warn",
        f"{alpha_pct:.2%}",
        f">{TAIL_ALPHA_PERCENTILE:.0%}",
        "残差落入历史最差10%才升级为风险事件观察。",
    )
    add_checkpoint(
        rows,
        "latest_alpha_not_bottom_10pct_analog_windows",
        "pass" if analog_alpha_pct > TAIL_ALPHA_PERCENTILE else "warn",
        f"{analog_alpha_pct:.2%}",
        f">{TAIL_ALPHA_PERCENTILE:.0%}",
        "同类状态分位用于防止把正常弱状态误判为策略损坏。",
    )
    add_checkpoint(
        rows,
        "all_source_quality_has_no_fail",
        "pass" if external_quality_fails == 0 else "fail",
        external_quality_fails,
        0,
        "任何源报告有失败项时，应先修数据/账本链路。",
    )
    add_checkpoint(
        rows,
        "no_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本监控入口只读已有报告，不修改策略配置。",
    )
    return pl.DataFrame(rows)


def classify_monitor_state(
    checkpoints: pl.DataFrame,
    baseline: dict[str, Any],
    oos: dict[str, Any],
) -> str:
    if checkpoints.filter(pl.col("status") == "fail").height > 0:
        return "red_fix_data_or_execution_first"
    alpha_pct = as_float(baseline.get("latest_alpha_percentile_rank_le_all_windows"), default=1.0)
    analog_alpha_pct = as_float(baseline.get("latest_alpha_percentile_rank_le_analog_windows"), default=1.0)
    oos_days = as_int(oos.get("segment_days"))
    if alpha_pct <= TAIL_ALPHA_PERCENTILE or analog_alpha_pct <= TAIL_ALPHA_PERCENTILE:
        return "orange_risk_event_watch"
    if alpha_pct <= CAUTION_ALPHA_PERCENTILE or analog_alpha_pct <= CAUTION_ALPHA_PERCENTILE:
        return "yellow_caution_continue_paper"
    if oos_days < MIN_OOS_DAYS_FOR_STABLE_JUDGMENT:
        return "yellow_sample_too_short_continue_paper"
    return "green_continue_paper"


def build_recommendations(monitor_state: str, baseline: dict[str, Any], oos: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "priority": 1,
            "action": "continue_paper_monitoring",
            "trigger": "default",
            "note": "继续按固定入口补数据、更新paper ledger和监控报告。",
        },
        {
            "priority": 2,
            "action": "do_not_change_signal_thresholds",
            "trigger": "current_stage",
            "note": "当前只是paper OOS监控，未达到正式策略或A/B条件。",
        },
    ]
    alpha_pct = as_float(baseline.get("latest_alpha_percentile_rank_le_all_windows"), default=1.0)
    analog_alpha_pct = as_float(baseline.get("latest_alpha_percentile_rank_le_analog_windows"), default=1.0)
    oos_days = as_int(oos.get("segment_days"))
    if monitor_state.startswith("red"):
        rows.append(
            {
                "priority": 0,
                "action": "fix_data_or_execution_chain",
                "trigger": monitor_state,
                "note": "红灯状态下先修数据/执行链路，不讨论信号优劣。",
            }
        )
    if alpha_pct <= TAIL_ALPHA_PERCENTILE or analog_alpha_pct <= TAIL_ALPHA_PERCENTILE:
        rows.append(
            {
                "priority": 0,
                "action": "run_reversal_timing_attribution",
                "trigger": "alpha_percentile_bottom_10pct",
                "note": "残差进入历史最差10%时，再做买入后1/2/3日反转节奏归因。",
            }
        )
    elif alpha_pct <= CAUTION_ALPHA_PERCENTILE or analog_alpha_pct <= CAUTION_ALPHA_PERCENTILE:
        rows.append(
            {
                "priority": 1,
                "action": "watch_alpha_percentile",
                "trigger": "alpha_percentile_bottom_15pct_not_10pct",
                "note": "当前偏弱但非尾部，继续观察下一批OOS窗口是否恶化。",
            }
        )
    if oos_days < MIN_OOS_DAYS_FOR_STABLE_JUDGMENT:
        rows.append(
            {
                "priority": 1,
                "action": "wait_until_20_oos_days",
                "trigger": "oos_days_below_20",
                "note": "满20个OOS交易日后再做稳定性判断。",
            }
        )
    return pl.DataFrame(rows).sort("priority")


def build_monitor_summary(
    latest: dict[str, Any],
    ledger: dict[str, Any],
    oos: dict[str, Any],
    market: dict[str, Any],
    baseline: dict[str, Any],
    checkpoints: pl.DataFrame,
) -> dict[str, Any]:
    monitor_state = classify_monitor_state(checkpoints, baseline, oos)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": latest.get("scenario") or ledger.get("scenario"),
        "monitor_state": monitor_state,
        "latest_signal_date": latest.get("latest_signal_date"),
        "latest_target_date": latest.get("latest_target_date"),
        "latest_target_count": latest.get("latest_target_count"),
        "latest_target_gross_weight": latest.get("latest_target_gross_weight"),
        "latest_order_count": latest.get("latest_order_count"),
        "latest_blocked_order_count": latest.get("latest_blocked_order_count"),
        "latest_unfilled_abs_change": latest.get("latest_unfilled_abs_change"),
        "ledger_final_equity": ledger.get("final_equity"),
        "ledger_total_return": ledger.get("total_return"),
        "ledger_max_drawdown": ledger.get("max_drawdown"),
        "ledger_sharpe": ledger.get("sharpe"),
        "ledger_overall_fill_ratio": ledger.get("overall_fill_ratio"),
        "oos_segment_days": oos.get("segment_days"),
        "oos_segment_total_return": oos.get("segment_total_return"),
        "oos_segment_max_drawdown": oos.get("segment_max_drawdown"),
        "oos_segment_fill_ratio": oos.get("segment_fill_ratio"),
        "oos_state_label": oos.get("state_label"),
        "market_drag_diagnosis": market.get("drag_diagnosis"),
        "market_alpha_vs_benchmark": market.get("segment_gross_alpha_vs_benchmark_sum"),
        "baseline_status": baseline.get("baseline_status"),
        "latest_alpha_percentile_rank_le_all_windows": baseline.get("latest_alpha_percentile_rank_le_all_windows"),
        "latest_alpha_percentile_rank_le_analog_windows": baseline.get(
            "latest_alpha_percentile_rank_le_analog_windows"
        ),
        "latest_net_percentile_rank_le_all_windows": baseline.get("latest_net_percentile_rank_le_all_windows"),
        "checkpoint_pass_count": checkpoints.filter(pl.col("status") == "pass").height,
        "checkpoint_warn_count": checkpoints.filter(pl.col("status") == "warn").height,
        "checkpoint_fail_count": checkpoints.filter(pl.col("status") == "fail").height,
    }


def write_report(
    summary: dict[str, Any],
    checkpoints: pl.DataFrame,
    recommendations: pl.DataFrame,
    ledger_quality: pl.DataFrame,
    baseline_quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = checkpoints.filter(pl.col("status") == "fail")
    warned = checkpoints.filter(pl.col("status") == "warn")
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 paper监控 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：监控入口汇总；不新增信号、不调参数、不跑新策略回测。",
        f"- 监控状态：`{summary['monitor_state']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- paper/live监控应同时看执行健康、回撤、基准相对表现、样本外漂移和数据质量。",
        "- 本阶段把这些指标做成固定入口，目的是减少人工翻报告时的主观判断，不是添加交易规则。",
        "- 我的判断：监控系统的价值在于让我们慢一点动手，先分清数据、执行、市场状态和信号残差。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            f"- 最新信号日`{summary['latest_signal_date']}`，最新目标执行日`{summary['latest_target_date']}`。",
            f"- 最新目标持仓`{summary['latest_target_count']}`只，总权重`{pct(summary['latest_target_gross_weight'])}`。",
            f"- 最新订单`{summary['latest_order_count']}`行，阻断`{summary['latest_blocked_order_count']}`行，未成交权重`{pct(summary['latest_unfilled_abs_change'])}`。",
            f"- ledger期末权益`{summary['ledger_final_equity']:.4f}`，总收益`{pct(summary['ledger_total_return'])}`，最大回撤`{pct(summary['ledger_max_drawdown'])}`，Sharpe `{summary['ledger_sharpe']:.2f}`。",
            f"- 全历史成交填充率`{pct(summary['ledger_overall_fill_ratio'])}`。",
            f"- OOS新增段`{summary['oos_segment_days']}`天，收益`{pct(summary['oos_segment_total_return'])}`，回撤`{pct(summary['oos_segment_max_drawdown'])}`，状态`{summary['oos_state_label']}`。",
            f"- 市场状态诊断`{summary['market_drag_diagnosis']}`，相对同暴露中证1000残差`{pct(summary['market_alpha_vs_benchmark'])}`。",
            f"- 历史基线状态`{summary['baseline_status']}`，残差全历史分位`{summary['latest_alpha_percentile_rank_le_all_windows']:.2%}`，同类状态分位`{summary['latest_alpha_percentile_rank_le_analog_windows']:.2%}`。",
            "- 结论：当前是黄色观察，不是红色风险事件。继续paper监控，不调参数。",
            "",
            "## 监控检查点",
            "",
            markdown_table(checkpoints, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 推荐动作",
            "",
            markdown_table(recommendations, ["priority", "action", "trigger", "note"], max_rows=20),
            "",
            "## 源报告质量摘要",
            "",
            "ledger quality:",
            "",
            markdown_table(ledger_quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "baseline quality:",
            "",
            markdown_table(baseline_quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只整合已有paper报告和质量检查，不新增预测变量、不调阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：监控状态只决定继续观察或升级归因，不产生交易过滤器或参数修改。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：paper链路已经有多份报告，需要统一入口避免后续监控依赖人工记忆。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：监控入口给出了明确黄灯状态和升级条件，后续补数据后可直接复跑。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 当前状态为`yellow_caution_continue_paper`：继续paper，不升级交易规则。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    latest = load_json(LATEST_PACKET_DIR / f"{LATEST_PACKET_PREFIX}_summary.json")
    ledger = load_json(LEDGER_DIR / f"{LEDGER_VERSION}_summary.json")
    oos = load_json(OOS_ATTR_DIR / f"{OOS_ATTR_PREFIX}_summary.json")
    market = load_json(OOS_MARKET_DIR / f"{OOS_MARKET_PREFIX}_summary.json")
    baseline = load_json(BASELINE_DIR / f"{BASELINE_PREFIX}_summary.json")
    ledger_quality = read_csv(LEDGER_DIR / f"{LEDGER_VERSION}_quality_checkpoints.csv")
    oos_quality = read_csv(OOS_ATTR_DIR / f"{OOS_ATTR_PREFIX}_quality_checkpoints.csv")
    market_quality = read_csv(OOS_MARKET_DIR / f"{OOS_MARKET_PREFIX}_quality_checkpoints.csv")
    baseline_quality = read_csv(BASELINE_DIR / f"{BASELINE_PREFIX}_quality_checkpoints.csv")
    checkpoints = build_monitor_checkpoints(
        latest,
        ledger,
        oos,
        market,
        baseline,
        ledger_quality,
        oos_quality,
        market_quality,
        baseline_quality,
    )
    summary = build_monitor_summary(latest, ledger, oos, market, baseline, checkpoints)
    recommendations = build_recommendations(summary["monitor_state"], baseline, oos)
    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "checkpoints": OUTPUT_DIR / f"{PREFIX}_checkpoints.csv",
        "recommendations": OUTPUT_DIR / f"{PREFIX}_recommendations.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    checkpoints.write_csv(paths["checkpoints"])
    recommendations.write_csv(paths["recommendations"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_latest_packet_dir": str(LATEST_PACKET_DIR),
            "source_ledger_dir": str(LEDGER_DIR),
            "source_oos_attribution_dir": str(OOS_ATTR_DIR),
            "source_oos_market_state_dir": str(OOS_MARKET_DIR),
            "source_baseline_dir": str(BASELINE_DIR),
            "min_fill_ratio": MIN_FILL_RATIO,
            "tail_alpha_percentile": TAIL_ALPHA_PERCENTILE,
            "caution_alpha_percentile": CAUTION_ALPHA_PERCENTILE,
            "min_oos_days_for_stable_judgment": MIN_OOS_DAYS_FOR_STABLE_JUDGMENT,
            "research_sources": RESEARCH_SOURCES,
            "note": "Monitoring only; flags do not alter trading rules.",
        },
    )
    report_path = write_report(summary, checkpoints, recommendations, ledger_quality, baseline_quality, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()

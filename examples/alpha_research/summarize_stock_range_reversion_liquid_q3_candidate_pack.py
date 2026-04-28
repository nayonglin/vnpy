from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_candidate_pack_2018_2026"
).expanduser().resolve()
PREFIX = "stock_range_reversion_liquid_q3_candidate_pack_v1"

CANDIDATE_SCENARIO = "age4_daily_exclude_volume_dry"
CANDIDATE_VERSION = "stock_range_reversion_liquid_q3_age4_exclude_volume_dry_paper_v3"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    ("Backtrader volume filling", "https://www.backtrader.com/docu/filler/"),
    ("Backtrader slippage", "https://www.backtrader.com/docu/slippage/slippage/"),
    ("Zipline volume-share slippage source", "https://zipline.ml4trading.io/_modules/zipline/finance/slippage.html"),
)


PATHS = {
    "filter_summary": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_v1_summary.csv",
    "filter_retention": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_v1_retention.csv",
    "filter_yearly": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_v1_yearly.csv",
    "rolling_start_year": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_rolling_validation_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_rolling_validation_v1_start_year_scorecard.csv",
    "rolling_window": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_rolling_validation_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_rolling_validation_v1_rolling_scorecard.csv",
    "robustness_year": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_robustness_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_robustness_v1_yearly_scorecard.csv",
    "cost_breakeven": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_cost_capacity_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_cost_capacity_v1_breakeven.csv",
    "cost_summary": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_cost_capacity_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_cost_capacity_v1_cost_summary.csv",
    "execution_constraints": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_execution_constraints_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_execution_constraints_v1_summary.csv",
    "execution_delay": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_repairability_filter_execution_delay_2018_2026"
    / "stock_range_reversion_liquid_q3_repairability_filter_execution_delay_v1_summary.csv",
    "paper_v1": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_paper_tracking_2018_2026"
    / "stock_range_reversion_liquid_q3_paper_tracking_v1_summary.json",
    "paper_v2": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_paper_tracking_v2_adv_quality_2018_2026"
    / "stock_range_reversion_liquid_q3_paper_tracking_v2_adv_quality_summary.json",
    "paper_v3": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality_2018_2026"
    / "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality_summary.json",
    "paper_v3_block": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality_2018_2026"
    / "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality_block_reason_summary.csv",
    "paper_v3_adv": NATIVE_RESULTS_DIR
    / "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality_2018_2026"
    / "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality_adv_quality_summary.csv",
}


def read_csv(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pl.read_csv(path, try_parse_dates=True)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def row_dict(frame: pl.DataFrame) -> dict[str, Any]:
    if frame.is_empty():
        return {}
    return frame.row(0, named=True)


def candidate_cost_rows(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.filter(pl.col("scenario") == CANDIDATE_SCENARIO).sort("roundtrip_cost_bps")


def key_metrics_table(summary: pl.DataFrame) -> pl.DataFrame:
    return candidate_cost_rows(summary).select(
        [
            "roundtrip_cost_bps",
            "final_equity",
            "total_return",
            "max_drawdown",
            "sharpe",
            "annualized_one_way_turnover",
            "cost_drag_sum",
            "net_active_day_win_rate",
            "avg_active_symbols_when_active",
            "avg_return_gross_exposure",
        ]
    )


def paper_summary_table(paper: dict[str, Any], label: str) -> dict[str, Any]:
    return {
        "version": label,
        "final_equity": paper.get("final_equity"),
        "total_return": paper.get("total_return"),
        "max_drawdown": paper.get("max_drawdown"),
        "sharpe": paper.get("sharpe"),
        "overall_fill_ratio": paper.get("overall_fill_ratio"),
        "order_count": paper.get("order_count"),
        "blocked_order_count": paper.get("blocked_order_count"),
        "latest_target_date": paper.get("latest_target_date"),
    }


def build_summary_payload(data: dict[str, Any]) -> dict[str, Any]:
    base_50 = row_dict(
        data["filter_summary"].filter(
            (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("roundtrip_cost_bps") == 50.0)
        )
    )
    retention = row_dict(data["filter_retention"].filter(pl.col("scenario") == CANDIDATE_SCENARIO))
    breakeven = row_dict(data["cost_breakeven"].filter(pl.col("scenario") == CANDIDATE_SCENARIO))
    rolling_start_50 = row_dict(
        data["rolling_start_year"].filter(
            (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("roundtrip_cost_bps") == 50.0)
        )
    )
    rolling_252_50 = row_dict(
        data["rolling_window"].filter(
            (pl.col("scenario") == CANDIDATE_SCENARIO)
            & (pl.col("roundtrip_cost_bps") == 50.0)
            & (pl.col("window_days") == 252)
        )
    )
    robust_year_50 = row_dict(
        data["robustness_year"].filter(
            (pl.col("scenario") == CANDIDATE_SCENARIO) & (pl.col("roundtrip_cost_bps") == 50.0)
        )
    )
    return {
        "candidate_version": CANDIDATE_VERSION,
        "scenario": CANDIDATE_SCENARIO,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "paper_candidate_not_formal",
        "formal_strategy": False,
        "stage78_ab": False,
        "base_50bp": base_50,
        "retention": retention,
        "breakeven": breakeven,
        "rolling_start_year_50bp": rolling_start_50,
        "rolling_252d_50bp": rolling_252_50,
        "robustness_year_50bp": robust_year_50,
        "paper_v3": data["paper_v3"],
        "research_sources": [{"title": title, "url": url} for title, url in RESEARCH_SOURCES],
    }


def build_report(data: dict[str, Any], payload: dict[str, Any], paths: dict[str, Path]) -> str:
    base_50 = payload["base_50bp"]
    retention = payload["retention"]
    breakeven = payload["breakeven"]
    paper_v3 = payload["paper_v3"]
    rolling_start = payload["rolling_start_year_50bp"]
    rolling_252 = payload["rolling_252d_50bp"]
    robust_year = payload["robustness_year_50bp"]

    paper_rows = pl.DataFrame(
        [
            paper_summary_table(data["paper_v1"], "v1_missing_adv_block"),
            paper_summary_table(data["paper_v2"], "v2_adv_quality"),
            paper_summary_table(data["paper_v3"], "v3_exante_adv_quality"),
        ]
    )
    selected_execution = data["execution_constraints"].filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO)
        & pl.col("execution_variant").is_in(
            [
                "open_tradeable_cap5pct_adv_10m_50bp",
                "open_tradeable_cap1pct_adv_50m_50bp",
                "open_tradeable_no_adv_cap_50bp",
            ]
        )
    )
    selected_delay = data["execution_delay"].filter(
        (pl.col("scenario") == CANDIDATE_SCENARIO)
        & pl.col("execution_variant").is_in(
            [
                "delay0d_cap5pct_adv_10m_50bp",
                "delay1d_cap5pct_adv_10m_50bp",
                "delay2d_cap5pct_adv_10m_50bp",
            ]
        )
    )
    lines = [
        "# 股票震荡候选版本包 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        f"- 候选版本：`{CANDIDATE_VERSION}`。",
        f"- 候选场景：`{CANDIDATE_SCENARIO}`。",
        "- 当前状态：纸面候选，不是正式策略，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- Backtrader把成交量填充与滑点作为独立 broker/execution 层处理，说明策略信号和成交假设必须拆开记录。",
        "- Zipline的volume-share slippage把成交量占比作为滑点/容量核心变量，支持我们用ADV参与率做保守成交上限。",
        "- 因此本候选包不再只报收益，而是同时报告信号、过滤、成本、容量、延迟、纸面订单和数据质量标签。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 候选规则",
            "",
            "- 股票池：中证1000历史成分内的可交易股票，要求非ST、上市时间达标、非停牌、成交量/成交额有效，且处于`liquid_q3`流动性层。",
            "- 信号：`score_oversold_ret_20`，在行业内排序；只取行业内最超跌的top组。",
            "- 建仓确认：`ENTRY_AGE_MIN=4`，4天确认后每日建篮。",
            "- 权重：行业中性约束，单行业篮子上限`20%`，单票篮子上限`5%`，未用完资金留现金。",
            "- 过滤：排除信号日`volume_ratio_20 <= 0.70`的`volume_dry`成交干枯样本，不排除`turnover_5_20_contract`。",
            "- 回测成本：核心观察用往返`50bp`，成本压力测试覆盖`0-300bp`。",
            "- 纸面执行主口径：v3 ex-ante ADV质量前置，交易日容量只用上一交易日及更早数据；账户`1000万`，单票单日不超过`5% ADV20`，往返成本`50bp`。",
            "",
            "## 核心证据",
            "",
            f"- 50bp基础回测：期末权益`{base_50.get('final_equity', 0):.4f}`，总收益`{pct(base_50.get('total_return', 0))}`，最大回撤`{pct(base_50.get('max_drawdown', 0))}`，Sharpe `{base_50.get('sharpe', 0):.2f}`。",
            f"- 成本安全垫：盈亏平衡往返成本约`{breakeven.get('breakeven_roundtrip_cost_bps', 0):.1f}bp`；100bp期末权益`{breakeven.get('final_equity_at_100bp', 0):.4f}`，150bp期末权益`{breakeven.get('final_equity_at_150bp', 0):.4f}`。",
            f"- 样本保留：保留信号行`{retention.get('row_retention_ratio', 0):.2%}`，保留信号日`{retention.get('signal_day_retention_ratio', 0):.2%}`，保留篮子权重`{retention.get('basket_weight_retention_ratio', 0):.2%}`。",
            f"- 起始年滚动：50bp下`{rolling_start.get('return_and_drawdown_beat_count', 0)}/{rolling_start.get('start_count', 0)}`个起始年同时胜出收益和回撤；回撤胜出率`{rolling_start.get('drawdown_beat_ratio', 0):.2%}`。",
            f"- 252日滚动：50bp下收益胜出率`{rolling_252.get('return_beat_ratio', 0):.2%}`，回撤胜出率`{rolling_252.get('drawdown_beat_ratio', 0):.2%}`，Sharpe胜出率`{rolling_252.get('sharpe_beat_ratio', 0):.2%}`。",
            f"- 年度稳健性：50bp下`{robust_year.get('beat_year_count', 0)}/{robust_year.get('year_count', 0)}`个年份收益胜出，平均年度收益增量`{pct(robust_year.get('avg_year_return_delta', 0))}`。",
            f"- 纸面v3：期末权益`{paper_v3.get('final_equity', 0):.4f}`，最大回撤`{pct(paper_v3.get('max_drawdown', 0))}`，Sharpe `{paper_v3.get('sharpe', 0):.2f}`，成交填充率`{pct(paper_v3.get('overall_fill_ratio', 0))}`。",
            "",
            "## 基础回测成本表",
            "",
            markdown_table(
                key_metrics_table(data["filter_summary"]),
                [
                    "roundtrip_cost_bps",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "annualized_one_way_turnover",
                    "cost_drag_sum",
                    "net_active_day_win_rate",
                    "avg_active_symbols_when_active",
                    "avg_return_gross_exposure",
                ],
            ),
            "",
            "## 纸面跟踪对照",
            "",
            markdown_table(
                paper_rows,
                [
                    "version",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "overall_fill_ratio",
                    "order_count",
                    "blocked_order_count",
                    "latest_target_date",
                ],
            ),
            "",
            "## v3 ADV质量来源",
            "",
            markdown_table(
                data["paper_v3_adv"],
                [
                    "adv_source",
                    "adv_quality_flag",
                    "orders",
                    "symbols",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                    "filled_weight_ratio",
                    "fallback_allowed_orders",
                ],
            ),
            "",
            "## v3订单阻断",
            "",
            markdown_table(
                data["paper_v3_block"],
                [
                    "status",
                    "blocked_reason",
                    "orders",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                ],
            ),
            "",
            "## 执行约束摘要",
            "",
            markdown_table(
                selected_execution,
                [
                    "execution_variant",
                    "account_size_cny",
                    "max_participation_adv20",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "overall_fill_ratio",
                    "blocked_buy_weight_sum",
                    "blocked_sell_weight_sum",
                    "missing_info_weight_sum",
                ],
            ),
            "",
            "## 延迟执行摘要",
            "",
            markdown_table(
                selected_delay,
                [
                    "execution_variant",
                    "execution_delay_days",
                    "final_equity",
                    "total_return",
                    "max_drawdown",
                    "sharpe",
                    "overall_fill_ratio",
                    "blocked_buy_weight_sum",
                    "blocked_sell_weight_sum",
                    "missing_info_weight_sum",
                ],
            ),
            "",
            "## 复验命令",
            "",
            "```bash",
            ".py311/bin/python examples/alpha_research/backtest_stock_range_reversion_liquid_q3_repairability_filter.py",
            ".py311/bin/python examples/alpha_research/analyze_stock_range_reversion_liquid_q3_repairability_filter_robustness.py",
            ".py311/bin/python examples/alpha_research/analyze_stock_range_reversion_liquid_q3_repairability_filter_rolling_validation.py",
            ".py311/bin/python examples/alpha_research/analyze_stock_range_reversion_liquid_q3_repairability_filter_cost_capacity.py",
            ".py311/bin/python examples/alpha_research/backtest_stock_range_reversion_liquid_q3_repairability_filter_execution_constraints.py",
            ".py311/bin/python examples/alpha_research/backtest_stock_range_reversion_liquid_q3_repairability_filter_execution_delay.py",
            ".py311/bin/python examples/alpha_research/generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality.py",
            ".py311/bin/python examples/alpha_research/summarize_stock_range_reversion_liquid_q3_candidate_pack.py",
            "```",
            "",
            "## 风险边界",
            "",
            "- 这不是正式实盘策略：还需要新增交易日样本外纸面跟踪，而不是只看历史重放。",
            "- 2025年度基础回测接近持平，说明策略不是每年线性赚钱，必须接受冷期。",
            "- 交易口径仍是日线级开盘模拟，没有订单簿排队、盘口冲击、实际券商可成交量。",
            "- v3解决了ADV前视问题，但fallback样本仍需抽样人工审计，确认交易日历和复权口径没有错位。",
            "- A股T+1、涨跌停、停牌、ST变化、指数成分历史偏差仍是后续实盘化前的关键风险。",
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只整理已有候选证据，不新增信号、不调阈值、不选择新参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：候选包只是把已有结果按证据链固化，明确保留风险边界，没有把报告包装成正式策略。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：v3已具备更可信纸面执行口径，需要一份可复验候选说明，防止后续研究失焦。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：候选证据链已闭合到信号、过滤、成本、容量、延迟和纸面订单；下一步可以做新增交易日入口。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "filter_summary": read_csv(PATHS["filter_summary"]),
        "filter_retention": read_csv(PATHS["filter_retention"]),
        "filter_yearly": read_csv(PATHS["filter_yearly"]),
        "rolling_start_year": read_csv(PATHS["rolling_start_year"]),
        "rolling_window": read_csv(PATHS["rolling_window"]),
        "robustness_year": read_csv(PATHS["robustness_year"]),
        "cost_breakeven": read_csv(PATHS["cost_breakeven"]),
        "cost_summary": read_csv(PATHS["cost_summary"]),
        "execution_constraints": read_csv(PATHS["execution_constraints"]),
        "execution_delay": read_csv(PATHS["execution_delay"]),
        "paper_v1": read_json(PATHS["paper_v1"]),
        "paper_v2": read_json(PATHS["paper_v2"]),
        "paper_v3": read_json(PATHS["paper_v3"]),
        "paper_v3_block": read_csv(PATHS["paper_v3_block"]),
        "paper_v3_adv": read_csv(PATHS["paper_v3_adv"]),
    }
    payload = build_summary_payload(data)
    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "artifact_manifest": OUTPUT_DIR / f"{PREFIX}_artifact_manifest.csv",
    }
    report = build_report(data, payload, paths)
    paths["report"].write_text(report, encoding="utf-8")
    paths["summary"].write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    manifest = pl.DataFrame(
        [
            {
                "artifact": name,
                "path": str(path),
                "exists": path.exists(),
            }
            for name, path in PATHS.items()
        ]
    )
    manifest.write_csv(paths["artifact_manifest"])
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"report={paths['report']}")


if __name__ == "__main__":
    main()

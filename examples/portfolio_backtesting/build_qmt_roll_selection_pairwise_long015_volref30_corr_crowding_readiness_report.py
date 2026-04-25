from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

FORMAL_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_summary.json"
NEIGHBOR_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_neighbors_fast_summary.json"
MONITOR_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_summary.json"
CURRENT_SWEEP_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_formal_current_period_sweep_summary.csv"
FLOOR35_SWEEP_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_formal_floor35_period_sweep_summary.csv"

OUTPUT_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_readiness"

SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.json"
REPORT_MD_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report.md"
START_YEAR_COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_comparison.csv"
DAILY_REVIEW_TEMPLATE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_review_template.csv"

CANDIDATE_NAME: str = "selection_pairwise_v2 + long015_volref30 + corr20_06_08_floor35"
BASELINE_NAME: str = "selection_pairwise_v2 + long015_volref30"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_experiment(summary: dict[str, Any], experiment_name: str) -> dict[str, Any]:
    for row in summary.get("experiments", []):
        if str(row.get("experiment_name")) == experiment_name:
            return dict(row)
    raise KeyError(f"experiment not found: {experiment_name}")


def build_start_year_comparison() -> pd.DataFrame:
    current_df = pd.read_csv(CURRENT_SWEEP_PATH)
    floor35_df = pd.read_csv(FLOOR35_SWEEP_PATH)
    merged = current_df.merge(
        floor35_df,
        on=["window_name", "display_label", "analysis_start", "analysis_end"],
        suffixes=("_baseline", "_candidate"),
        how="inner",
    )
    merged["end_balance_diff"] = merged["end_balance_candidate"] - merged["end_balance_baseline"]
    merged["total_return_pct_diff"] = merged["total_return_pct_candidate"] - merged["total_return_pct_baseline"]
    merged["max_dd_percent_diff"] = merged["max_dd_percent_candidate"] - merged["max_dd_percent_baseline"]
    merged["sharpe_ratio_diff"] = merged["sharpe_ratio_candidate"] - merged["sharpe_ratio_baseline"]
    merged["total_trade_count_diff"] = merged["total_trade_count_candidate"] - merged["total_trade_count_baseline"]
    columns = [
        "window_name",
        "display_label",
        "analysis_start",
        "end_balance_baseline",
        "end_balance_candidate",
        "end_balance_diff",
        "total_return_pct_baseline",
        "total_return_pct_candidate",
        "total_return_pct_diff",
        "max_dd_percent_baseline",
        "max_dd_percent_candidate",
        "max_dd_percent_diff",
        "sharpe_ratio_baseline",
        "sharpe_ratio_candidate",
        "sharpe_ratio_diff",
        "total_trade_count_baseline",
        "total_trade_count_candidate",
        "total_trade_count_diff",
    ]
    return merged[columns].copy()


def build_daily_review_template() -> pd.DataFrame:
    columns = [
        "review_date",
        "data_end_date",
        "candidate_name",
        "end_balance",
        "daily_net_pnl",
        "drawdown_pct",
        "trade_count",
        "new_entry_count",
        "same_direction_corr_gate_trigger_count",
        "severe_watch_count",
        "max_warning_score",
        "manual_review_required",
        "review_reason",
        "followup_due_date_20d",
        "followup_relative_pnl_20d",
        "action_taken",
        "notes",
    ]
    return pd.DataFrame(columns=columns)


def fmt_money(value: float) -> str:
    return f"{value:,.0f}"


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_无记录_"
    compact = df.copy()
    for column in compact.columns:
        if pd.api.types.is_float_dtype(compact[column]):
            compact[column] = compact[column].map(lambda value: f"{float(value):.4f}")
    headers = [str(column) for column in compact.columns]
    rows = compact.astype(str).to_numpy().tolist()
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_markdown_report(
    candidate: dict[str, Any],
    baseline: dict[str, Any],
    start_year: pd.DataFrame,
    neighbor_summary: dict[str, Any],
    monitor_summary: dict[str, Any],
) -> str:
    severe_hit_rate = float(monitor_summary["severe_watch_hit_rate_fwd20"])
    non_severe_hit_rate = float(monitor_summary["non_severe_hit_rate_fwd20"])
    neighbor_experiments = pd.DataFrame(neighbor_summary["experiments"])
    neighbor_top = neighbor_experiments.sort_values("end_balance", ascending=False).head(5)

    lines = [
        "# QMT Roll 当前候选准实盘可用性报告",
        "",
        "## 候选结论",
        "",
        f"- 当前冻结候选：`{CANDIDATE_NAME}`",
        f"- 对照基线：`{BASELINE_NAME}`",
        "- 建议状态：`可进入准实盘/纸面跟踪`",
        "- 不建议状态：`无人值守实盘自动运行`",
        "",
        "## 正式回测指标",
        "",
        f"- 期末权益：`{fmt_money(float(candidate['end_balance']))}`",
        f"- 总收益：`{fmt_pct(float(candidate['total_return_pct']))}`",
        f"- 最大回撤：`{fmt_pct(float(candidate['max_dd_percent']))}`",
        f"- Sharpe：`{float(candidate['sharpe_ratio']):.4f}`",
        f"- 总滑点：`{fmt_money(float(candidate['total_slippage']))}`",
        f"- 总交易次数：`{int(candidate['total_trade_count'])}`",
        "",
        "## 相对基线改善",
        "",
        f"- 期末权益差：`{fmt_money(float(candidate['end_balance']) - float(baseline['end_balance']))}`",
        f"- 总收益差：`{float(candidate['total_return_pct']) - float(baseline['total_return_pct']):.2f}` 个百分点",
        f"- 最大回撤差：`{float(candidate['max_dd_percent']) - float(baseline['max_dd_percent']):.2f}` 个百分点",
        f"- Sharpe 差：`{float(candidate['sharpe_ratio']) - float(baseline['sharpe_ratio']):.4f}`",
        f"- 总滑点差：`{fmt_money(float(candidate['total_slippage']) - float(baseline['total_slippage']))}`",
        f"- 总交易次数差：`{int(candidate['total_trade_count']) - int(baseline['total_trade_count'])}`",
        "",
        "## 启动年份稳健性",
        "",
        to_markdown_table(start_year),
        "",
        "## 邻域复核",
        "",
        to_markdown_table(
            neighbor_top[
                [
                    "experiment_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                ]
            ]
        ),
        "",
        "## 监控边界",
        "",
        f"- `severe_watch` 日期数：`{int(monitor_summary['severe_watch_date_count'])}`",
        f"- `severe_watch` 20 日均值：`{fmt_money(float(monitor_summary['severe_watch_mean_fwd20']))}`",
        f"- `severe_watch` 20 日胜率：`{severe_hit_rate:.2%}`",
        f"- 非 `severe_watch` 20 日均值：`{fmt_money(float(monitor_summary['non_severe_mean_fwd20']))}`",
        f"- 非 `severe_watch` 20 日胜率：`{non_severe_hit_rate:.2%}`",
        "",
        "## 操作原则",
        "",
        "- 不再做 `corr` 参数细网格搜索。",
        "- `severe_watch` 只提高复盘优先级，不自动关闭门控。",
        "- 每次门控触发后必须记录 20 日相对路径。",
        "- 未来新增样本不足前，不新增状态化开关。",
        "- 若准实盘连续出现 `severe_watch` 且 20 日路径为负，再复盘是否升级为状态化门控。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    formal_summary = load_json(FORMAL_SUMMARY_PATH)
    neighbor_summary = load_json(NEIGHBOR_SUMMARY_PATH)
    monitor_summary = load_json(MONITOR_SUMMARY_PATH)
    candidate = find_experiment(formal_summary, "volref30_corr20_06_08_floor35")
    baseline = find_experiment(formal_summary, "volref30_current")
    start_year = build_start_year_comparison()
    review_template = build_daily_review_template()

    start_year.to_csv(START_YEAR_COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    review_template.to_csv(DAILY_REVIEW_TEMPLATE_CSV_PATH, index=False, encoding="utf-8-sig")
    REPORT_MD_PATH.write_text(
        build_markdown_report(candidate, baseline, start_year, neighbor_summary, monitor_summary),
        encoding="utf-8",
    )

    readiness_payload: dict[str, Any] = {
        "candidate_name": CANDIDATE_NAME,
        "baseline_name": BASELINE_NAME,
        "readiness_status": "ready_for_paper_trading_review_not_unattended_live",
        "candidate_metrics": candidate,
        "baseline_metrics": baseline,
        "improvement_vs_baseline": {
            "end_balance_diff": float(candidate["end_balance"]) - float(baseline["end_balance"]),
            "total_return_pct_diff": float(candidate["total_return_pct"]) - float(baseline["total_return_pct"]),
            "max_dd_percent_diff": float(candidate["max_dd_percent"]) - float(baseline["max_dd_percent"]),
            "sharpe_ratio_diff": float(candidate["sharpe_ratio"]) - float(baseline["sharpe_ratio"]),
            "total_slippage_diff": float(candidate["total_slippage"]) - float(baseline["total_slippage"]),
            "total_trade_count_diff": int(candidate["total_trade_count"]) - int(baseline["total_trade_count"]),
        },
        "start_year_comparison": start_year.to_dict(orient="records"),
        "monitor_summary": monitor_summary,
        "governance": {
            "freeze_candidate_parameters": True,
            "allow_corr_micro_grid_search": False,
            "use_severe_watch_as_trade_switch": False,
            "require_20d_followup_for_gate_triggers": True,
            "recommended_next_phase": "paper_trading_review",
        },
        "artifacts": {
            "report_md": str(REPORT_MD_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "start_year_comparison_csv": str(START_YEAR_COMPARISON_CSV_PATH),
            "daily_review_template_csv": str(DAILY_REVIEW_TEMPLATE_CSV_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(
        json.dumps(readiness_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"readiness report md: {REPORT_MD_PATH}")
    print(f"readiness summary json: {SUMMARY_JSON_PATH}")
    print(f"daily review template csv: {DAILY_REVIEW_TEMPLATE_CSV_PATH}")
    print(json.dumps(readiness_payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import START_YEAR_WINDOWS, build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    FU_PRODUCT,
    build_ai_satellite_post_signal_eligibility,
    build_static18_plus_fu_universe,
    to_markdown_table,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_comparison.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"

CAPITAL: float = 200_000.0


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_strategy_specs() -> tuple[dict[str, Any], ...]:
    universe_path = build_static18_plus_fu_universe()
    eligibility_path = build_ai_satellite_post_signal_eligibility()

    stage75_overrides: dict[str, Any] = {
        **CORR20_06_08_FLOOR35_OVERRIDES,
        "product_universe_csv_path": str(universe_path),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    }
    profit_shield_overrides: dict[str, Any] = {
        **stage75_overrides,
        "streak_risk_state_excluded_products": FU_PRODUCT,
        "streak_risk_state_exclusion_mode": "profit_only",
    }
    return (
        {
            "strategy_name": "stage75_fu_satellite_post_signal",
            "strategy_overrides": stage75_overrides,
            "universe_path": universe_path,
            "eligibility_path": eligibility_path,
        },
        {
            "strategy_name": "stage78_profit_shield_streak",
            "strategy_overrides": profit_shield_overrides,
            "universe_path": universe_path,
            "eligibility_path": eligibility_path,
        },
    )


def run_start_year_backtests() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in build_strategy_specs():
        strategy_name = str(spec["strategy_name"])
        strategy_overrides = dict(spec["strategy_overrides"])
        universe_path = Path(spec["universe_path"])
        eligibility_path = Path(spec["eligibility_path"])
        for window_name, display_label, analysis_start, analysis_end in START_YEAR_WINDOWS:
            print(
                f"[profit-shield-start-year] {strategy_name} / {window_name}: "
                f"{analysis_start.date()} -> {analysis_end.date()}"
            )
            _, _, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=None,
                chart_title=None,
            )
            rows.append(
                build_summary_row(
                    statistics,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    strategy_name=strategy_name,
                    window_name=window_name,
                    display_label=display_label,
                    universe_path=str(universe_path),
                    ai_product_pool_eligibility_path=str(eligibility_path),
                    ai_product_pool_strategy=AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                    strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                    total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                    total_slippage=float(statistics.get("total_slippage", 0) or 0),
                    total_commission=float(statistics.get("total_commission", 0) or 0),
                    profit_days=int(statistics.get("profit_days", 0) or 0),
                    loss_days=int(statistics.get("loss_days", 0) or 0),
                )
            )
    return pd.DataFrame(rows)


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    stage75 = summary[summary["strategy_name"] == "stage75_fu_satellite_post_signal"].copy()
    shield = summary[summary["strategy_name"] == "stage78_profit_shield_streak"].copy()
    key_columns = ["window_name", "display_label", "analysis_start", "analysis_end"]
    comparison = shield.merge(stage75, on=key_columns, suffixes=("_shield", "_stage75"))
    for column in (
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_trade_count",
        "total_slippage",
    ):
        comparison[f"{column}_diff"] = comparison[f"{column}_shield"] - comparison[f"{column}_stage75"]
    comparison["shield_beats_stage75_end_balance"] = (
        comparison["end_balance_diff"] > 0.0
    ).astype(int)
    comparison["shield_beats_stage75_sharpe"] = (
        comparison["sharpe_ratio_diff"] > 0.0
    ).astype(int)
    return comparison


def build_payload(summary: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    return {
        "experiment_tag": EXPERIMENT_TAG,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "capital": CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "summary": summary.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
        "aggregate": {
            "windows": int(len(comparison)),
            "shield_end_balance_wins": int(comparison["shield_beats_stage75_end_balance"].sum()),
            "shield_sharpe_wins": int(comparison["shield_beats_stage75_sharpe"].sum()),
            "avg_end_balance_diff": float(comparison["end_balance_diff"].mean()) if not comparison.empty else 0.0,
            "avg_sharpe_diff": float(comparison["sharpe_ratio_diff"].mean()) if not comparison.empty else 0.0,
            "avg_slippage_diff": float(comparison["total_slippage_diff"].mean()) if not comparison.empty else 0.0,
        },
        "artifacts": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "comparison_csv": str(COMPARISON_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def build_report(summary: pd.DataFrame, comparison: pd.DataFrame, payload: dict[str, Any]) -> str:
    aggregate = payload.get("aggregate", {})
    view_columns = [
        "window_name",
        "end_balance_shield",
        "end_balance_stage75",
        "end_balance_diff",
        "max_dd_percent_shield",
        "max_dd_percent_stage75",
        "max_dd_percent_diff",
        "sharpe_ratio_shield",
        "sharpe_ratio_stage75",
        "sharpe_ratio_diff",
        "total_slippage_diff",
        "total_trade_count_diff",
    ]
    lines = [
        "# 第78阶段起始年份稳健性反证",
        "",
        "## 设计",
        "",
        "- 对比第75阶段收益上限基准与第78阶段风险治理候选。",
        "- 所有窗口使用同一套参数，只改变起始年份，不做任何再优化。",
        "- 目标是判断第78阶段是否只是在全周期和2026尾部偶然有效。",
        "",
        "## 汇总",
        "",
        f"- 起始年份窗口数：`{int(_safe_float(aggregate.get('windows'))):,}`",
        f"- 第78阶段期末权益胜出窗口：`{int(_safe_float(aggregate.get('shield_end_balance_wins'))):,}`",
        f"- 第78阶段Sharpe胜出窗口：`{int(_safe_float(aggregate.get('shield_sharpe_wins'))):,}`",
        f"- 平均期末权益差额：`{_safe_float(aggregate.get('avg_end_balance_diff')):,.0f}`",
        f"- 平均Sharpe差额：`{_safe_float(aggregate.get('avg_sharpe_diff')):.4f}`",
        f"- 平均滑点差额：`{_safe_float(aggregate.get('avg_slippage_diff')):,.0f}`",
        "",
        "## 起始年份对比",
        "",
        to_markdown_table(comparison[view_columns]),
        "",
        "## 判断",
        "",
        "- 如果第78阶段只在少数窗口改善尾部，但多数起始年份明显输给第75阶段，则不能升级为正式候选。",
        "- 如果第78阶段收益略低但滑点、回撤和最新尾部稳定改善，则保留为风险治理候选。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = run_start_year_backtests()
    comparison = build_comparison(summary)
    payload = build_payload(summary, comparison)
    report = build_report(summary, comparison, payload)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"[profit-shield-start-year] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[profit-shield-start-year] comparison csv: {COMPARISON_CSV_PATH}")
    print(f"[profit-shield-start-year] summary json: {SUMMARY_JSON_PATH}")
    print(f"[profit-shield-start-year] report: {REPORT_PATH}")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()

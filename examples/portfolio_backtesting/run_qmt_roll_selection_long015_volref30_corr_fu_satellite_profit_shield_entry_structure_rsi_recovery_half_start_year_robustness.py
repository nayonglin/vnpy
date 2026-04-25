from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import START_YEAR_WINDOWS, build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    to_markdown_table,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_backtest import (
    CAPITAL,
    ENTRY_STRUCTURE_RECOVERY_MIN_MULTIPLIER,
    EXPERIMENT_NAME as STAGE90_EXPERIMENT_NAME,
    build_strategy_overrides,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_"
    "entry_structure_rsi_recovery_half_start_year"
)
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_comparison.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"

REFERENCE_SUMMARY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness_summary.csv"
)


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def run_start_year_backtests() -> pd.DataFrame:
    strategy_overrides, universe_path, eligibility_path = build_strategy_overrides()
    rows: list[dict[str, Any]] = []
    for window_name, display_label, analysis_start, analysis_end in START_YEAR_WINDOWS:
        print(
            f"[entry-structure-rsi-recovery-half-start-year] {window_name}: "
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
                strategy_name=STAGE90_EXPERIMENT_NAME,
                window_name=window_name,
                display_label=display_label,
                universe_path=str(universe_path),
                ai_product_pool_eligibility_path=str(eligibility_path),
                ai_product_pool_strategy=AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                streak_entry_structure_recovery_min_multiplier=ENTRY_STRUCTURE_RECOVERY_MIN_MULTIPLIER,
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
    return pd.DataFrame(rows)


def load_reference_summary() -> pd.DataFrame:
    if not REFERENCE_SUMMARY_PATH.exists():
        raise FileNotFoundError(REFERENCE_SUMMARY_PATH)
    reference = pd.read_csv(REFERENCE_SUMMARY_PATH)
    reference["analysis_start"] = pd.to_datetime(reference["analysis_start"]).dt.date.astype(str)
    reference["analysis_end"] = pd.to_datetime(reference["analysis_end"]).dt.date.astype(str)
    return reference


def build_comparison(stage90: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    key_columns = ["window_name", "display_label", "analysis_start", "analysis_end"]
    stage90_view = stage90.copy()
    stage90_view["analysis_start"] = pd.to_datetime(stage90_view["analysis_start"]).dt.date.astype(str)
    stage90_view["analysis_end"] = pd.to_datetime(stage90_view["analysis_end"]).dt.date.astype(str)

    stage75 = reference[reference["strategy_name"].astype(str) == "stage75_fu_satellite_post_signal"].copy()
    stage78 = reference[reference["strategy_name"].astype(str) == "stage78_profit_shield_streak"].copy()
    comparison = stage90_view.merge(stage75, on=key_columns, suffixes=("_stage90", "_stage75"))
    comparison = comparison.merge(stage78, on=key_columns, suffixes=("", "_stage78"))
    rename_stage78 = {
        column: f"{column}_stage78"
        for column in stage78.columns
        if column not in key_columns and f"{column}_stage78" not in comparison.columns
    }
    comparison = comparison.rename(columns=rename_stage78)

    for reference_name in ("stage75", "stage78"):
        for column in (
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_trade_count",
            "total_slippage",
        ):
            comparison[f"{column}_diff_vs_{reference_name}"] = (
                comparison[f"{column}_stage90"] - comparison[f"{column}_{reference_name}"]
            )
        comparison[f"stage90_beats_{reference_name}_end_balance"] = (
            comparison[f"end_balance_diff_vs_{reference_name}"] > 0.0
        ).astype(int)
        comparison[f"stage90_beats_{reference_name}_sharpe"] = (
            comparison[f"sharpe_ratio_diff_vs_{reference_name}"] > 0.0
        ).astype(int)
    return comparison


def build_payload(stage90: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    aggregate: dict[str, Any] = {"windows": int(len(comparison))}
    for reference_name in ("stage75", "stage78"):
        aggregate[f"stage90_end_balance_wins_vs_{reference_name}"] = int(
            comparison[f"stage90_beats_{reference_name}_end_balance"].sum()
        )
        aggregate[f"stage90_sharpe_wins_vs_{reference_name}"] = int(
            comparison[f"stage90_beats_{reference_name}_sharpe"].sum()
        )
        aggregate[f"avg_end_balance_diff_vs_{reference_name}"] = float(
            comparison[f"end_balance_diff_vs_{reference_name}"].mean()
        )
        aggregate[f"avg_sharpe_diff_vs_{reference_name}"] = float(
            comparison[f"sharpe_ratio_diff_vs_{reference_name}"].mean()
        )
        aggregate[f"worst_end_balance_diff_vs_{reference_name}"] = float(
            comparison[f"end_balance_diff_vs_{reference_name}"].min()
        )
    return {
        "experiment_tag": EXPERIMENT_TAG,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "capital": CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "streak_entry_structure_recovery_min_multiplier": ENTRY_STRUCTURE_RECOVERY_MIN_MULTIPLIER,
        "stage90_summary": stage90.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
        "aggregate": aggregate,
        "artifacts": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "comparison_csv": str(COMPARISON_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
            "reference_summary": str(REFERENCE_SUMMARY_PATH),
        },
    }


def build_report(stage90: pd.DataFrame, comparison: pd.DataFrame, payload: dict[str, Any]) -> str:
    aggregate = payload.get("aggregate", {})
    view_columns = [
        "window_name",
        "end_balance_stage90",
        "end_balance_stage78",
        "end_balance_diff_vs_stage78",
        "max_dd_percent_stage90",
        "max_dd_percent_stage78",
        "max_dd_percent_diff_vs_stage78",
        "sharpe_ratio_stage90",
        "sharpe_ratio_stage78",
        "sharpe_ratio_diff_vs_stage78",
        "end_balance_diff_vs_stage75",
        "sharpe_ratio_diff_vs_stage75",
    ]
    lines = [
        "# 第90阶段半恢复起始年份稳健性反证",
        "",
        "## 设计",
        "",
        "- 只运行第90阶段同一套参数的起始年份窗口，不做再优化。",
        "- 第75阶段与第78阶段结果直接复用既有起始年份稳健性产物，避免重复回测。",
        "- 目标是确认`0.5`半恢复是否比第86阶段满恢复更能穿越不同起点。",
        "",
        "## 汇总",
        "",
        f"- 起始年份窗口数：`{int(_safe_float(aggregate.get('windows'))):,}`",
        f"- 第90相对第78期末权益胜出窗口：`{int(_safe_float(aggregate.get('stage90_end_balance_wins_vs_stage78'))):,}`",
        f"- 第90相对第78 Sharpe胜出窗口：`{int(_safe_float(aggregate.get('stage90_sharpe_wins_vs_stage78'))):,}`",
        f"- 第90相对第78平均期末权益差额：`{_safe_float(aggregate.get('avg_end_balance_diff_vs_stage78')):,.0f}`",
        f"- 第90相对第78平均Sharpe差额：`{_safe_float(aggregate.get('avg_sharpe_diff_vs_stage78')):.4f}`",
        f"- 第90相对第78最差期末权益差额：`{_safe_float(aggregate.get('worst_end_balance_diff_vs_stage78')):,.0f}`",
        "",
        "## 起始年份对比",
        "",
        to_markdown_table(comparison[view_columns]),
        "",
        "## 第90窗口明细",
        "",
        to_markdown_table(
            stage90[
                [
                    "window_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                ]
            ]
        ),
        "",
        "## 判断",
        "",
        "- 如果第90多数起点胜出且`since_2026`损害可控，可作为收益增强候选继续做滑点压力。",
        "- 如果第90只在少数起点胜出或平均Sharpe显著下降，保留第78为正式风险治理版本。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage90 = run_start_year_backtests()
    reference = load_reference_summary()
    comparison = build_comparison(stage90, reference)
    payload = build_payload(stage90, comparison)
    report = build_report(stage90, comparison, payload)

    stage90.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"[entry-structure-rsi-recovery-half-start-year] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[entry-structure-rsi-recovery-half-start-year] comparison csv: {COMPARISON_CSV_PATH}")
    print(f"[entry-structure-rsi-recovery-half-start-year] summary json: {SUMMARY_JSON_PATH}")
    print(f"[entry-structure-rsi-recovery-half-start-year] report: {REPORT_PATH}")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()

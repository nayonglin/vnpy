from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress import (
    CAPITAL,
    SLIPPAGE_MULTIPLIERS,
    calculate_metrics_from_net_pnl,
)
from run_qmt_roll_backtest import START_YEAR_WINDOWS, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_backtest import (
    build_strategy_overrides as build_stage90_strategy_overrides,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_backtest import (
    build_strategy_overrides as build_stage78_strategy_overrides,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_"
    "entry_structure_rsi_recovery_half_weak_window_stress"
)
STRESS_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_comparison.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report.md"

WEAK_WINDOW_NAMES: tuple[str, ...] = ("since_2022", "since_2026")


def get_weak_windows() -> tuple[tuple[str, str, datetime, datetime], ...]:
    windows = tuple(window for window in START_YEAR_WINDOWS if window[0] in WEAK_WINDOW_NAMES)
    missing = set(WEAK_WINDOW_NAMES) - {window[0] for window in windows}
    if missing:
        raise ValueError(f"Missing start-year windows: {sorted(missing)}")
    return windows


def prepare_daily(analysis_df: pd.DataFrame | None) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        raise ValueError("Empty analysis daily result")
    frame = analysis_df.copy()
    for column in ("net_pnl", "slippage", "trade_count"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame


def build_stress_rows(
    *,
    strategy_name: str,
    window_name: str,
    display_label: str,
    analysis_start: datetime,
    analysis_end: datetime,
    daily: pd.DataFrame,
    statistics: dict[str, Any],
) -> list[dict[str, Any]]:
    net_pnl = daily["net_pnl"].to_numpy(dtype=float)
    slippage = daily["slippage"].to_numpy(dtype=float)
    trade_count = int(daily["trade_count"].sum())
    rows: list[dict[str, Any]] = []

    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed_net_pnl = net_pnl - (multiplier - 1.0) * slippage
        rows.append(
            {
                "strategy_name": strategy_name,
                "window_name": window_name,
                "display_label": display_label,
                "analysis_start": analysis_start.date().isoformat(),
                "analysis_end": analysis_end.date().isoformat(),
                "slippage_multiplier": multiplier,
                "extra_slippage": float(((multiplier - 1.0) * slippage).sum()),
                "total_slippage": float((multiplier * slippage).sum()),
                "total_trade_count": trade_count,
                "engine_end_balance": float(statistics.get("end_balance", 0) or 0),
                "engine_total_return_pct": float(statistics.get("total_return", 0) or 0),
                "engine_max_dd_percent": float(statistics.get("max_ddpercent", 0) or 0),
                "engine_sharpe_ratio": float(statistics.get("sharpe_ratio", 0) or 0),
                **calculate_metrics_from_net_pnl(stressed_net_pnl),
            }
        )
    return rows


def run_weak_window_stress() -> pd.DataFrame:
    stage78_overrides, _, _ = build_stage78_strategy_overrides()
    stage90_overrides, _, _ = build_stage90_strategy_overrides()
    strategy_specs: tuple[tuple[str, dict[str, Any]], ...] = (
        ("stage78_profit_shield_streak", stage78_overrides),
        ("stage90_entry_structure_rsi_recovery_half", stage90_overrides),
    )
    rows: list[dict[str, Any]] = []

    for window_name, display_label, analysis_start, analysis_end in get_weak_windows():
        for strategy_name, strategy_overrides in strategy_specs:
            print(
                f"[entry-structure-rsi-recovery-half-weak-window-stress] "
                f"{strategy_name} / {window_name}: {analysis_start.date()} -> {analysis_end.date()}"
            )
            _, analysis_df, statistics = run_backtest(
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
            daily = prepare_daily(analysis_df)
            rows.extend(
                build_stress_rows(
                    strategy_name=strategy_name,
                    window_name=window_name,
                    display_label=display_label,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    daily=daily,
                    statistics=statistics,
                )
            )

    return pd.DataFrame(rows)


def build_comparison(stress: pd.DataFrame) -> pd.DataFrame:
    stage78 = stress[stress["strategy_name"] == "stage78_profit_shield_streak"].copy()
    stage90 = stress[stress["strategy_name"] == "stage90_entry_structure_rsi_recovery_half"].copy()
    key_columns = ["window_name", "display_label", "analysis_start", "analysis_end", "slippage_multiplier"]
    comparison = stage90.merge(stage78, on=key_columns, suffixes=("_stage90", "_stage78"))
    for column in ("end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage"):
        comparison[f"{column}_diff"] = comparison[f"{column}_stage90"] - comparison[f"{column}_stage78"]
    comparison["stage90_beats_stage78_end_balance"] = (comparison["end_balance_diff"] > 0.0).astype(int)
    comparison["stage90_beats_stage78_sharpe"] = (comparison["sharpe_ratio_diff"] > 0.0).astype(int)
    return comparison


def build_payload(stress: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    aggregate_by_window: dict[str, dict[str, Any]] = {}
    for window_name, group in comparison.groupby("window_name"):
        aggregate_by_window[str(window_name)] = {
            "rows": int(len(group)),
            "stage90_end_balance_wins": int(group["stage90_beats_stage78_end_balance"].sum()),
            "stage90_sharpe_wins": int(group["stage90_beats_stage78_sharpe"].sum()),
            "min_end_balance_diff": float(group["end_balance_diff"].min()),
            "max_end_balance_diff": float(group["end_balance_diff"].max()),
            "min_sharpe_diff": float(group["sharpe_ratio_diff"].min()),
            "max_sharpe_diff": float(group["sharpe_ratio_diff"].max()),
        }
    return {
        "experiment_tag": EXPERIMENT_TAG,
        "weak_windows": list(WEAK_WINDOW_NAMES),
        "slippage_multipliers": list(SLIPPAGE_MULTIPLIERS),
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": CAPITAL,
        "aggregate_by_window": aggregate_by_window,
        "stress": stress.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
        "artifacts": {
            "stress_csv": str(STRESS_CSV_PATH),
            "comparison_csv": str(COMPARISON_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def build_report(stress: pd.DataFrame, comparison: pd.DataFrame, payload: dict[str, Any]) -> str:
    stress_view_columns = [
        "strategy_name",
        "window_name",
        "slippage_multiplier",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    comparison_view_columns = [
        "window_name",
        "slippage_multiplier",
        "end_balance_stage90",
        "end_balance_stage78",
        "end_balance_diff",
        "max_dd_percent_stage90",
        "max_dd_percent_stage78",
        "max_dd_percent_diff",
        "sharpe_ratio_stage90",
        "sharpe_ratio_stage78",
        "sharpe_ratio_diff",
        "total_slippage_diff",
    ]
    aggregate = payload["aggregate_by_window"]
    lines = [
        "# 第90阶段薄弱起点滑点压力交叉验证",
        "",
        "## 设计",
        "",
        "- 只重跑第91阶段暴露出的薄弱起点：`since_2022`和`since_2026`。",
        "- 对第78与第90在同一起点下的日度路径做`1/1.5/2/3/5`倍滑点压力。",
        "- 目标是判断第90在薄弱起点是否经不起交易成本，而不是继续调参。",
        "",
        "## 汇总",
        "",
    ]
    for window_name in WEAK_WINDOW_NAMES:
        item = aggregate.get(window_name, {})
        lines.extend(
            [
                f"- `{window_name}`：第90期末权益胜出`{int(item.get('stage90_end_balance_wins', 0))}/5`，"
                f"Sharpe胜出`{int(item.get('stage90_sharpe_wins', 0))}/5`，"
                f"期末权益差额区间`{float(item.get('min_end_balance_diff', 0.0)):,.0f}`到"
                f"`{float(item.get('max_end_balance_diff', 0.0)):,.0f}`。",
            ]
        )
    lines.extend(
        [
            "",
            "## 压力结果",
            "",
            to_markdown_table(stress[stress_view_columns]),
            "",
            "## 第90相对第78",
            "",
            to_markdown_table(comparison[comparison_view_columns]),
            "",
            "## 判断",
            "",
            "- 如果薄弱起点在高滑点下继续恶化，第90只能保留为研究候选。",
            "- 如果薄弱起点的期末权益优势能跨滑点存在，但Sharpe仍弱，则第90可以作为进攻版本，而非替代第78的防守版本。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stress = run_weak_window_stress()
    comparison = build_comparison(stress)
    payload = build_payload(stress, comparison)

    stress.to_csv(STRESS_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(stress, comparison, payload), encoding="utf-8")

    print(f"[entry-structure-rsi-recovery-half-weak-window-stress] stress csv: {STRESS_CSV_PATH}")
    print(f"[entry-structure-rsi-recovery-half-weak-window-stress] comparison csv: {COMPARISON_CSV_PATH}")
    print(f"[entry-structure-rsi-recovery-half-weak-window-stress] summary json: {SUMMARY_JSON_PATH}")
    print(f"[entry-structure-rsi-recovery-half-weak-window-stress] report: {REPORT_PATH}")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()

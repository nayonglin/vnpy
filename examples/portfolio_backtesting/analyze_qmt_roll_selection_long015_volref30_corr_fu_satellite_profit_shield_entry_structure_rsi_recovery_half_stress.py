from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

STAGE75_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_daily.csv"
STAGE78_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal_daily.csv"
STAGE90_DAILY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_formal_daily.csv"
)

STRESS_CSV_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress.csv"
)
COMPARISON_CSV_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress_comparison.csv"
)
STRESS_REPORT_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress_report.md"
)

CAPITAL: float = 200_000.0
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 5.0)


def calculate_metrics_from_net_pnl(net_pnl: np.ndarray, *, initial_capital: float = CAPITAL) -> dict[str, float]:
    if len(net_pnl) == 0:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }

    equity = initial_capital + np.cumsum(net_pnl.astype(float))
    prev_equity = np.concatenate([[initial_capital], equity[:-1]])
    returns = np.divide(net_pnl, prev_equity, out=np.zeros_like(net_pnl, dtype=float), where=prev_equity != 0)
    high_water = np.maximum.accumulate(equity)
    drawdown_pct = np.divide(equity - high_water, high_water, out=np.zeros_like(equity), where=high_water != 0) * 100.0
    return_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe_ratio = float(np.mean(returns) / return_std * np.sqrt(240)) if return_std > 0 else 0.0
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / initial_capital - 1.0) * 100.0),
        "max_dd_percent": float(drawdown_pct.min()),
        "sharpe_ratio": sharpe_ratio,
    }


def load_daily(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, encoding="utf-8-sig")
    for column in ("net_pnl", "slippage", "trade_count"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame


def build_stress_rows(strategy_name: str, daily: pd.DataFrame) -> list[dict[str, Any]]:
    net_pnl = daily["net_pnl"].to_numpy(dtype=float)
    slippage = daily["slippage"].to_numpy(dtype=float)
    trade_count = int(daily["trade_count"].sum())
    rows: list[dict[str, Any]] = []

    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed_net_pnl = net_pnl - (multiplier - 1.0) * slippage
        rows.append(
            {
                "strategy_name": strategy_name,
                "slippage_multiplier": multiplier,
                "extra_slippage": float(((multiplier - 1.0) * slippage).sum()),
                "total_slippage": float((multiplier * slippage).sum()),
                "total_trade_count": trade_count,
                **calculate_metrics_from_net_pnl(stressed_net_pnl),
            }
        )
    return rows


def build_comparison(stress: pd.DataFrame) -> pd.DataFrame:
    stage75 = stress[stress["strategy_name"] == "stage75_fu_satellite_post_signal"].copy()
    stage78 = stress[stress["strategy_name"] == "stage78_profit_shield_streak"].copy()
    stage90 = stress[stress["strategy_name"] == "stage90_entry_structure_rsi_recovery_half"].copy()

    comparison = stage90.merge(stage78, on="slippage_multiplier", suffixes=("_stage90", "_stage78"))
    comparison = comparison.merge(
        stage75,
        on="slippage_multiplier",
        suffixes=("", "_stage75"),
    )
    comparison = comparison.rename(
        columns={
            "strategy_name": "strategy_name_stage75",
            "extra_slippage": "extra_slippage_stage75",
            "end_balance": "end_balance_stage75",
            "total_return_pct": "total_return_pct_stage75",
            "max_dd_percent": "max_dd_percent_stage75",
            "sharpe_ratio": "sharpe_ratio_stage75",
            "total_slippage": "total_slippage_stage75",
            "total_trade_count": "total_trade_count_stage75",
        }
    )

    for reference in ("stage78", "stage75"):
        for column in ("end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage"):
            comparison[f"{column}_diff_vs_{reference}"] = (
                comparison[f"{column}_stage90"] - comparison[f"{column}_{reference}"]
            )

    return comparison


def build_report(stress: pd.DataFrame, comparison: pd.DataFrame) -> str:
    view_columns = [
        "strategy_name",
        "slippage_multiplier",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    comparison_columns = [
        "slippage_multiplier",
        "end_balance_stage90",
        "end_balance_stage78",
        "end_balance_diff_vs_stage78",
        "sharpe_ratio_stage90",
        "sharpe_ratio_stage78",
        "sharpe_ratio_diff_vs_stage78",
        "max_dd_percent_stage90",
        "max_dd_percent_stage78",
        "max_dd_percent_diff_vs_stage78",
        "end_balance_stage75",
        "end_balance_diff_vs_stage75",
    ]

    lines = [
        "# 第90阶段半恢复滑点压力反证",
        "",
        "## 设计",
        "",
        "- 不重跑策略，不改变入场、出场和仓位路径。",
        "- 基于已保存日度`net_pnl/slippage`，在`1/1.5/2/3/5`倍滑点下重估权益、回撤和Sharpe。",
        "- 对比对象：第75阶段收益上限、第78阶段风险治理候选、第90阶段半恢复收益增强候选。",
        "",
        "## 滑点压力结果",
        "",
        to_markdown_table(stress[view_columns]),
        "",
        "## 第90相对第78和第75",
        "",
        to_markdown_table(comparison[comparison_columns]),
        "",
        "## 判断",
        "",
        "- 如果第90在高滑点下相对第78的全周期优势迅速消失，说明收益增强主要来自更多交易和更高摩擦暴露，不应正式升级。",
        "- 如果第90在高滑点下仍保持权益优势且回撤没有显著恶化，才值得进入更严格的起始年份成本压力。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    stage75 = load_daily(STAGE75_DAILY_PATH)
    stage78 = load_daily(STAGE78_DAILY_PATH)
    stage90 = load_daily(STAGE90_DAILY_PATH)

    stress = pd.DataFrame(
        [
            *build_stress_rows("stage75_fu_satellite_post_signal", stage75),
            *build_stress_rows("stage78_profit_shield_streak", stage78),
            *build_stress_rows("stage90_entry_structure_rsi_recovery_half", stage90),
        ]
    )
    comparison = build_comparison(stress)

    stress.to_csv(STRESS_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    STRESS_REPORT_PATH.write_text(build_report(stress, comparison), encoding="utf-8")

    print(f"[entry-structure-rsi-recovery-half-stress] stress csv: {STRESS_CSV_PATH}")
    print(f"[entry-structure-rsi-recovery-half-stress] comparison csv: {COMPARISON_CSV_PATH}")
    print(f"[entry-structure-rsi-recovery-half-stress] report: {STRESS_REPORT_PATH}")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

STAGE75_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_daily.csv"
PROFIT_SHIELD_DAILY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal_daily.csv"
)

STRESS_CSV_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stress.csv"
)
STRESS_REPORT_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stress_report.md"
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
    for column in ["net_pnl", "slippage", "trade_count"]:
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


def build_report(stress: pd.DataFrame) -> str:
    stage75 = stress[stress["strategy_name"] == "stage75_fu_satellite_post_signal"].copy()
    shield = stress[stress["strategy_name"] == "profit_shield_streak"].copy()
    merged = shield.merge(
        stage75,
        on="slippage_multiplier",
        suffixes=("_shield", "_stage75"),
    )
    merged["end_balance_diff_vs_stage75"] = merged["end_balance_shield"] - merged["end_balance_stage75"]
    merged["sharpe_diff_vs_stage75"] = merged["sharpe_ratio_shield"] - merged["sharpe_ratio_stage75"]
    merged["max_dd_percent_diff_vs_stage75"] = merged["max_dd_percent_shield"] - merged["max_dd_percent_stage75"]

    comparison = merged[
        [
            "slippage_multiplier",
            "end_balance_shield",
            "end_balance_stage75",
            "end_balance_diff_vs_stage75",
            "sharpe_ratio_shield",
            "sharpe_ratio_stage75",
            "sharpe_diff_vs_stage75",
            "max_dd_percent_shield",
            "max_dd_percent_stage75",
            "max_dd_percent_diff_vs_stage75",
        ]
    ].copy()

    lines = [
        "# AI Top8 + fu卫星：盈利屏蔽版滑点压力对比",
        "",
        "## 对比对象",
        "",
        "- `stage75_fu_satellite_post_signal`：第75阶段收益最高候选。",
        "- `profit_shield_streak`：`fu.SHFE`盈利不重置组合连续亏损状态，亏损仍计入。",
        "",
        "## 滑点压力",
        "",
        to_markdown_table(
            stress[
                [
                    "strategy_name",
                    "slippage_multiplier",
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
        "## 相对第75阶段",
        "",
        to_markdown_table(comparison),
        "",
        "## 判断",
        "",
        "- 盈利屏蔽版在1倍滑点下略低于第75阶段，但3倍和5倍滑点下反而超过第75阶段。",
        "- 它不是收益最大化版本，而是用很小全周期收益代价换取更好的2026尾部、更低交易成本和更高成本韧性。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    stage75 = load_daily(STAGE75_DAILY_PATH)
    shield = load_daily(PROFIT_SHIELD_DAILY_PATH)
    stress = pd.DataFrame(
        [
            *build_stress_rows("stage75_fu_satellite_post_signal", stage75),
            *build_stress_rows("profit_shield_streak", shield),
        ]
    )
    stress.to_csv(STRESS_CSV_PATH, index=False, encoding="utf-8-sig")
    STRESS_REPORT_PATH.write_text(build_report(stress), encoding="utf-8")

    print(f"[fu-satellite-profit-shield-stress] csv: {STRESS_CSV_PATH}")
    print(f"[fu-satellite-profit-shield-stress] report: {STRESS_REPORT_PATH}")
    print(stress.to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import run_backtest

SAVE_ARTIFACTS: bool = False
CAPITAL: float = 200_000
ANALYSIS_START: datetime = datetime(2022, 1, 1)
ANALYSIS_END: datetime = END_DT

RISK_OVERRIDES: dict[str, float] = {
    "risk_ratio_of_total_assets": 0.045,
    "risk_ratio_breakout": 0.045,
    "risk_ratio_ma_cross_breakout": 0.045,
    "risk_ratio_open_interest_surge": 0.06,
    "risk_ratio_volume_open_interest_surge": 0.06,
    "risk_ratio_open_interest_decline": 0.025,
}

BASE_STRATEGY_OVERRIDES: dict[str, object] = {
    "max_single_trade_capital_usage_ratio": 0.70,
}

EXPERIMENTS: list[dict[str, Any]] = [
    {
        "label": "streak_defensive_base",
        "description": "第一轮冠军基线",
        "strategy_overrides": {
            "streak_risk_multipliers": "1.0,1.0,0.5,0.25",
        },
    },
    {
        "label": "streak_soft",
        "description": "更温和的连败降风险",
        "strategy_overrides": {
            "streak_risk_multipliers": "1.0,1.0,0.75,0.5",
        },
    },
    {
        "label": "streak_hard_early",
        "description": "更早开始收缩风险",
        "strategy_overrides": {
            "streak_risk_multipliers": "1.0,0.75,0.5,0.25",
        },
    },
    {
        "label": "streak_very_hard",
        "description": "极端保守的连败降风险",
        "strategy_overrides": {
            "streak_risk_multipliers": "1.0,0.5,0.25,0.1",
        },
    },
    {
        "label": "streak_defensive_concurrent3",
        "description": "冠军基线 + 最大并发持仓降到 3",
        "strategy_overrides": {
            "streak_risk_multipliers": "1.0,1.0,0.5,0.25",
            "max_concurrent_positions": 3,
        },
    },
    {
        "label": "streak_defensive_singlecap06",
        "description": "冠军基线 + 单笔资金上限降到 0.60",
        "strategy_overrides": {
            "streak_risk_multipliers": "1.0,1.0,0.5,0.25",
            "max_single_trade_capital_usage_ratio": 0.60,
        },
    },
    {
        "label": "streak_defensive_portcap08",
        "description": "冠军基线 + 组合资金上限降到 0.80",
        "strategy_overrides": {
            "streak_risk_multipliers": "1.0,1.0,0.5,0.25",
            "max_capital_usage_ratio": 0.80,
        },
    },
]


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _compute_score(row: dict[str, Any]) -> float:
    sharpe_ratio: float = _safe_float(row.get("sharpe_ratio"))
    return_drawdown_ratio: float = _safe_float(row.get("return_drawdown_ratio"))
    total_return_pct: float = _safe_float(row.get("total_return_pct"))
    max_dd_percent: float = abs(_safe_float(row.get("max_dd_percent")))
    win_ratio_pct: float = _safe_float(row.get("win_ratio_pct"))
    total_trade_count: float = _safe_float(row.get("total_trade_count"))

    return (
        0.42 * return_drawdown_ratio
        + 0.32 * sharpe_ratio
        + 0.16 * (total_return_pct / 100.0)
        + 0.08 * (win_ratio_pct / 100.0)
        - 0.20 * (max_dd_percent / 100.0)
        - 0.03 * (total_trade_count / 1000.0)
    )


def run_experiments() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for index, experiment in enumerate(EXPERIMENTS, start=1):
        label: str = str(experiment["label"])
        description: str = str(experiment["description"])
        strategy_overrides: dict[str, object] = dict(BASE_STRATEGY_OVERRIDES)
        strategy_overrides.update(dict(experiment.get("strategy_overrides", {})))

        print(f"[weak-window-opt-refined] {index}/{len(EXPERIMENTS)} {label}: {description}")
        _, _, statistics = run_backtest(
            risk_ratio=0.045,
            risk_overrides=RISK_OVERRIDES,
            strategy_overrides=strategy_overrides,
            analysis_start=ANALYSIS_START,
            analysis_end=ANALYSIS_END,
            capital=CAPITAL,
            save_artifacts=SAVE_ARTIFACTS,
            file_prefix=f"qmt_roll_weak_opt_refined_{label}",
            chart_title=f"QMT Roll Weak Window Optimization Refined {label}",
        )

        row: dict[str, Any] = {
            "label": label,
            "description": description,
            "end_balance": _safe_float(statistics.get("end_balance")),
            "total_return_pct": _safe_float(statistics.get("total_return")),
            "annual_return_pct": _safe_float(statistics.get("annual_return")),
            "max_drawdown": _safe_float(statistics.get("max_drawdown")),
            "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
            "max_drawdown_duration": int(_safe_float(statistics.get("max_drawdown_duration"))),
            "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
            "return_drawdown_ratio": _safe_float(statistics.get("return_drawdown_ratio")),
            "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
            "win_count": int(_safe_float(statistics.get("win_count"))),
            "round_trip_count": int(_safe_float(statistics.get("round_trip_count"))),
            "total_trade_count": int(_safe_float(statistics.get("total_trade_count"))),
            "daily_trade_count": _safe_float(statistics.get("daily_trade_count")),
            "total_slippage": _safe_float(statistics.get("total_slippage")),
            "total_turnover": _safe_float(statistics.get("total_turnover")),
            "strategy_overrides": str(strategy_overrides),
        }
        row["score"] = _compute_score(row)
        rows.append(row)

    result_df = pd.DataFrame(rows)
    result_df.sort_values(
        ["score", "max_dd_percent", "sharpe_ratio", "total_return_pct"],
        ascending=[False, False, False, False],
        inplace=True,
    )
    result_df["rank"] = range(1, len(result_df) + 1)
    ordered_columns = [
        "rank",
        "label",
        "description",
        "score",
        "sharpe_ratio",
        "return_drawdown_ratio",
        "max_dd_percent",
        "total_return_pct",
        "annual_return_pct",
        "win_ratio_pct",
        "win_count",
        "round_trip_count",
        "total_trade_count",
        "daily_trade_count",
        "total_slippage",
        "total_turnover",
        "end_balance",
        "max_drawdown",
        "max_drawdown_duration",
        "strategy_overrides",
    ]
    return result_df[ordered_columns]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_df = run_experiments()
    summary_path: Path = (OUTPUT_DIR / "qmt_roll_weak_window_optimization_refined_summary.csv").resolve()
    result_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"[weak-window-opt-refined] summary csv: {summary_path}")
    print("[weak-window-opt-refined] full ranking:")
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()

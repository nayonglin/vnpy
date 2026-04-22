from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import run_backtest

SAVE_ARTIFACTS: bool = False
CAPITAL: float = 200_000

# Second-round refined grid for single-trade capital cap.
SINGLE_CAP_GRID: list[float] = [0.60, 0.65, 0.70, 0.75, 0.80]

RISK_OVERRIDES: dict[str, float] = {
    "risk_ratio_of_total_assets": 0.045,
    "risk_ratio_breakout": 0.045,
    "risk_ratio_ma_cross_breakout": 0.045,
    "risk_ratio_open_interest_surge": 0.06,
    "risk_ratio_volume_open_interest_surge": 0.06,
    "risk_ratio_open_interest_decline": 0.025,
}


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

    return (
        0.45 * return_drawdown_ratio
        + 0.30 * sharpe_ratio
        + 0.15 * (total_return_pct / 100.0)
        + 0.10 * (win_ratio_pct / 100.0)
        - 0.12 * (max_dd_percent / 100.0)
    )


def run_grid() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for index, single_cap_ratio in enumerate(SINGLE_CAP_GRID, start=1):
        ratio_label: str = str(single_cap_ratio).replace(".", "p")
        print(f"[single-cap-refined-grid] {index}/{len(SINGLE_CAP_GRID)} single_cap_ratio={single_cap_ratio:.2f}")
        _, _, statistics = run_backtest(
            risk_ratio=0.045,
            risk_overrides=RISK_OVERRIDES,
            strategy_overrides={
                "max_single_trade_capital_usage_ratio": single_cap_ratio,
            },
            capital=CAPITAL,
            save_artifacts=SAVE_ARTIFACTS,
            file_prefix=f"qmt_roll_single_cap_refined_{ratio_label}",
            chart_title=f"QMT Roll Single Cap Refined Grid {ratio_label}",
        )

        row: dict[str, Any] = {
            "single_trade_capital_usage_ratio": single_cap_ratio,
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
        }
        row["score"] = _compute_score(row)
        rows.append(row)

    result_df = pd.DataFrame(rows)
    result_df.sort_values(
        ["score", "sharpe_ratio", "return_drawdown_ratio", "total_return_pct"],
        ascending=False,
        inplace=True,
    )
    result_df["rank"] = range(1, len(result_df) + 1)
    ordered_columns = [
        "rank",
        "single_trade_capital_usage_ratio",
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
    ]
    return result_df[ordered_columns]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_df = run_grid()
    summary_path: Path = (OUTPUT_DIR / "qmt_roll_single_cap_grid_refined_summary.csv").resolve()
    result_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"[single-cap-refined-grid] summary csv: {summary_path}")
    print("[single-cap-refined-grid] full ranking:")
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()

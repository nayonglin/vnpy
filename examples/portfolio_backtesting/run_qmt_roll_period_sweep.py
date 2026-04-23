from __future__ import annotations

from pathlib import Path

from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import run_start_year_sweep


BASE_RISK_RATIO: float = 0.045
RISK_OVERRIDES: dict[str, float] = {
    "risk_ratio_of_total_assets": 0.045,
    "risk_ratio_open_interest_surge": 0.06,
    "risk_ratio_volume_open_interest_surge": 0.06,
    "risk_ratio_open_interest_decline": 0.025,
}
STRATEGY_OVERRIDES: dict[str, object] = {
    "max_single_trade_capital_usage_ratio": 0.70,
}
CAPITAL: float = 200_000


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_df, curves_df = run_start_year_sweep(
        risk_ratio=BASE_RISK_RATIO,
        risk_overrides=RISK_OVERRIDES,
        strategy_overrides=STRATEGY_OVERRIDES,
        capital=CAPITAL,
    )
    output_path: Path = (OUTPUT_DIR / "qmt_roll_period_sweep_summary.csv").resolve()
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[period] summary csv: {output_path}")
    curves_path: Path = (OUTPUT_DIR / "qmt_roll_period_sweep_equity_curves.csv").resolve()
    curves_df.to_csv(curves_path, index=False, encoding="utf-8-sig")
    print(f"[period] curves csv: {curves_path}")
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()

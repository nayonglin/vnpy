from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_fast"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"

BASE_RISK_RATIO: float = 0.045

VOLREF30_OVERRIDES: dict[str, Any] = {
    "enable_selection_pairwise_v2": True,
    "enable_selection_pairwise_v2_catastrophic_veto": False,
    "enable_selection_pairwise_v2_volume_tilt": True,
    "selection_pairwise_volume_tilt_strength": 0.0,
    "selection_pairwise_volume_tilt_long_strength": 0.15,
    "selection_pairwise_volume_tilt_short_strength": 0.0,
    "selection_pairwise_volume_tilt_long_base_volume_reference": 30.0,
}


def correlation_gate_overrides(
    *,
    start: float,
    full: float,
    weight_floor: float,
    lookback: int = 20,
) -> dict[str, Any]:
    return {
        **VOLREF30_OVERRIDES,
        "enable_same_direction_correlation_gate": True,
        "same_direction_correlation_gate_lookback": lookback,
        "same_direction_correlation_gate_start": start,
        "same_direction_correlation_gate_full": full,
        "same_direction_correlation_gate_weight_floor": weight_floor,
    }


EXPERIMENTS: tuple[dict[str, Any], ...] = (
    {
        "experiment_name": "volref30_current",
        "strategy_overrides": VOLREF30_OVERRIDES,
    },
    {
        "experiment_name": "volref30_corr20_06_08_floor50",
        "strategy_overrides": correlation_gate_overrides(
            start=0.60,
            full=0.80,
            weight_floor=0.50,
        ),
    },
    {
        "experiment_name": "volref30_corr20_06_08_floor35",
        "strategy_overrides": correlation_gate_overrides(
            start=0.60,
            full=0.80,
            weight_floor=0.35,
        ),
    },
    {
        "experiment_name": "volref30_corr20_05_08_floor50",
        "strategy_overrides": correlation_gate_overrides(
            start=0.50,
            full=0.80,
            weight_floor=0.50,
        ),
    },
)


def run_experiments() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for experiment in EXPERIMENTS:
        experiment_name = str(experiment["experiment_name"])
        strategy_overrides = dict(experiment["strategy_overrides"])
        print(f"[volref30-corr-crowding-fast] running {experiment_name}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=START_DT,
            analysis_end=END_DT,
            capital=200_000,
            save_artifacts=False,
            include_start_year_sweep=False,
            file_prefix=f"qmt_roll_{experiment_name}",
            chart_title=f"QMT Roll {experiment_name}",
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=START_DT,
                analysis_end=END_DT,
                experiment_name=experiment_name,
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
    summary_df = pd.DataFrame(rows)
    summary_df.sort_values("experiment_name", inplace=True)
    summary_df.reset_index(drop=True, inplace=True)
    return summary_df


def build_comparison_payload(summary_df: pd.DataFrame) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "experiment_tag": EXPERIMENT_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "experiments": summary_df.to_dict(orient="records"),
    }
    base_df = summary_df[summary_df["experiment_name"] == "volref30_current"]
    if base_df.empty:
        return payload

    base_row = base_df.iloc[0]
    payload["comparison_vs_volref30_current"] = [
        {
            "experiment_name": str(row["experiment_name"]),
            "end_balance_diff": float(row["end_balance"] - base_row["end_balance"]),
            "total_return_pct_diff": float(row["total_return_pct"] - base_row["total_return_pct"]),
            "max_dd_percent_diff": float(row["max_dd_percent"] - base_row["max_dd_percent"]),
            "sharpe_ratio_diff": float(row["sharpe_ratio"] - base_row["sharpe_ratio"]),
            "total_trade_count_diff": int(row["total_trade_count"] - base_row["total_trade_count"]),
            "total_slippage_diff": float(row["total_slippage"] - base_row["total_slippage"]),
        }
        for _, row in summary_df.iterrows()
        if str(row["experiment_name"]) != "volref30_current"
    ]
    return payload


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df = run_experiments()
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(build_comparison_payload(summary_df), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[volref30-corr-crowding-fast] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[volref30-corr-crowding-fast] summary json: {SUMMARY_JSON_PATH}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()

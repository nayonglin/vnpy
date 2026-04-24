from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_pairwise_v2_volume_tilt_directional_backtest"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"

BASE_RISK_RATIO: float = 0.045

COMMON_PAIRWISE_SETTINGS: dict[str, Any] = {
    "enable_selection_pairwise_v2": True,
    "enable_selection_pairwise_v2_catastrophic_veto": False,
    "enable_selection_pairwise_v2_volume_tilt": True,
}

EXPERIMENTS: tuple[dict[str, Any], ...] = (
    {
        "experiment_name": "selection_pairwise_v2",
        "file_prefix": "qmt_roll_selection_pairwise_v2_directional_baseline",
        "chart_title": "QMT Roll Selection Pairwise v2 Directional Baseline",
        "strategy_overrides": {
            "enable_selection_pairwise_v2": True,
            "enable_selection_pairwise_v2_catastrophic_veto": False,
        },
    },
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_short035",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_short035",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Short 0.35",
        "strategy_overrides": {
            **COMMON_PAIRWISE_SETTINGS,
            "selection_pairwise_volume_tilt_strength": 0.0,
            "selection_pairwise_volume_tilt_long_strength": 0.0,
            "selection_pairwise_volume_tilt_short_strength": 0.35,
        },
    },
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long015",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long015",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long 0.15",
        "strategy_overrides": {
            **COMMON_PAIRWISE_SETTINGS,
            "selection_pairwise_volume_tilt_strength": 0.0,
            "selection_pairwise_volume_tilt_long_strength": 0.15,
            "selection_pairwise_volume_tilt_short_strength": 0.0,
        },
    },
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long010_short035",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long010_short035",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long 0.10 Short 0.35",
        "strategy_overrides": {
            **COMMON_PAIRWISE_SETTINGS,
            "selection_pairwise_volume_tilt_strength": 0.0,
            "selection_pairwise_volume_tilt_long_strength": 0.10,
            "selection_pairwise_volume_tilt_short_strength": 0.35,
        },
    },
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long015_short035",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long015_short035",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long 0.15 Short 0.35",
        "strategy_overrides": {
            **COMMON_PAIRWISE_SETTINGS,
            "selection_pairwise_volume_tilt_strength": 0.0,
            "selection_pairwise_volume_tilt_long_strength": 0.15,
            "selection_pairwise_volume_tilt_short_strength": 0.35,
        },
    },
)


def run_experiments() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for experiment in EXPERIMENTS:
        experiment_name = str(experiment["experiment_name"])
        strategy_overrides = dict(experiment.get("strategy_overrides", {}))
        print(f"[selection-pairwise-volume-tilt-directional] running {experiment_name}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=START_DT,
            analysis_end=END_DT,
            capital=200_000,
            save_artifacts=True,
            include_start_year_sweep=True,
            file_prefix=str(experiment["file_prefix"]),
            chart_title=str(experiment["chart_title"]),
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


def build_summary_payload(summary_df: pd.DataFrame) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "experiment_tag": EXPERIMENT_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "experiments": summary_df.to_dict(orient="records"),
    }
    baseline = summary_df[summary_df["experiment_name"] == "selection_pairwise_v2"]
    if baseline.empty:
        return payload

    baseline_row = baseline.iloc[0]
    comparisons: list[dict[str, Any]] = []
    for _, row in summary_df.iterrows():
        experiment_name = str(row["experiment_name"])
        if experiment_name == "selection_pairwise_v2":
            continue
        comparisons.append(
            {
                "experiment_name": experiment_name,
                "end_balance_diff": float(row["end_balance"] - baseline_row["end_balance"]),
                "total_return_pct_diff": float(row["total_return_pct"] - baseline_row["total_return_pct"]),
                "max_dd_percent_diff": float(row["max_dd_percent"] - baseline_row["max_dd_percent"]),
                "sharpe_ratio_diff": float(row["sharpe_ratio"] - baseline_row["sharpe_ratio"]),
                "total_trade_count_diff": int(row["total_trade_count"] - baseline_row["total_trade_count"]),
                "total_slippage_diff": float(row["total_slippage"] - baseline_row["total_slippage"]),
            }
        )
    payload["comparison_vs_pairwise_v2"] = comparisons
    return payload


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df = run_experiments()
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(build_summary_payload(summary_df), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[selection-pairwise-volume-tilt-directional] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[selection-pairwise-volume-tilt-directional] summary json: {SUMMARY_JSON_PATH}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_pairwise_long015_volref30_active_positions_fast_backtest"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"
BASELINE_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_long015_base_volume_neighbors_backtest_summary.csv"

BASE_RISK_RATIO: float = 0.045

BASE_LONG015_VOLREF30: dict[str, Any] = {
    "enable_selection_pairwise_v2": True,
    "enable_selection_pairwise_v2_catastrophic_veto": False,
    "enable_selection_pairwise_v2_volume_tilt": True,
    "selection_pairwise_volume_tilt_strength": 0.0,
    "selection_pairwise_volume_tilt_long_strength": 0.15,
    "selection_pairwise_volume_tilt_short_strength": 0.0,
    "selection_pairwise_volume_tilt_long_base_volume_reference": 30.0,
}

EXPERIMENTS: tuple[dict[str, Any], ...] = (
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long015_volref30_apref2",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_apref2_fast",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long015 VolRef30 APRef2 Fast",
        "strategy_overrides": {
            **BASE_LONG015_VOLREF30,
            "selection_pairwise_volume_tilt_long_active_positions_reference": 2.0,
        },
    },
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long015_volref30_apref25",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_apref25_fast",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long015 VolRef30 APRef25 Fast",
        "strategy_overrides": {
            **BASE_LONG015_VOLREF30,
            "selection_pairwise_volume_tilt_long_active_positions_reference": 2.5,
        },
    },
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long015_volref30_apref3",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_apref3_fast",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long015 VolRef30 APRef3 Fast",
        "strategy_overrides": {
            **BASE_LONG015_VOLREF30,
            "selection_pairwise_volume_tilt_long_active_positions_reference": 3.0,
        },
    },
)


def load_baseline_rows() -> pd.DataFrame:
    baseline_df = pd.read_csv(BASELINE_SUMMARY_PATH)
    keep_names = {
        "selection_pairwise_v2",
        "selection_pairwise_v2_volume_tilt_long015_volref30",
    }
    return baseline_df[baseline_df["experiment_name"].isin(keep_names)].copy()


def run_experiments() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for experiment in EXPERIMENTS:
        experiment_name = str(experiment["experiment_name"])
        strategy_overrides = dict(experiment.get("strategy_overrides", {}))
        print(f"[selection-pairwise-long015-volref30-active-positions-fast] running {experiment_name}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=START_DT,
            analysis_end=END_DT,
            capital=200_000,
            save_artifacts=True,
            include_start_year_sweep=False,
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
    fast_df = pd.DataFrame(rows)
    summary_df = pd.concat([load_baseline_rows(), fast_df], ignore_index=True)
    summary_df.sort_values("experiment_name", inplace=True)
    summary_df.reset_index(drop=True, inplace=True)
    return summary_df


def build_comparison_row(base_row: pd.Series, compare_row: pd.Series) -> dict[str, Any]:
    return {
        "experiment_name": str(compare_row["experiment_name"]),
        "end_balance_diff": float(compare_row["end_balance"] - base_row["end_balance"]),
        "total_return_pct_diff": float(compare_row["total_return_pct"] - base_row["total_return_pct"]),
        "max_dd_percent_diff": float(compare_row["max_dd_percent"] - base_row["max_dd_percent"]),
        "sharpe_ratio_diff": float(compare_row["sharpe_ratio"] - base_row["sharpe_ratio"]),
        "total_trade_count_diff": int(compare_row["total_trade_count"] - base_row["total_trade_count"]),
        "total_slippage_diff": float(compare_row["total_slippage"] - base_row["total_slippage"]),
    }


def build_summary_payload(summary_df: pd.DataFrame) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "experiment_tag": EXPERIMENT_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "analysis_start": START_DT.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "experiments": summary_df.to_dict(orient="records"),
    }
    volref30_row = summary_df[summary_df["experiment_name"] == "selection_pairwise_v2_volume_tilt_long015_volref30"].iloc[0]
    payload["comparison_vs_volref30"] = [
        build_comparison_row(volref30_row, row)
        for _, row in summary_df.iterrows()
        if str(row["experiment_name"]) != "selection_pairwise_v2_volume_tilt_long015_volref30"
    ]
    return payload


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df = run_experiments()
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(build_summary_payload(summary_df), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[selection-pairwise-long015-volref30-active-positions-fast] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[selection-pairwise-long015-volref30-active-positions-fast] summary json: {SUMMARY_JSON_PATH}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()

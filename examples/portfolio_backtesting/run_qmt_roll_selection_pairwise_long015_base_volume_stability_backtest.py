from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_selection_pairwise_long015_base_volume_stability_backtest"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"

BASE_RISK_RATIO: float = 0.045

BASE_PAIRWISE: dict[str, Any] = {
    "enable_selection_pairwise_v2": True,
    "enable_selection_pairwise_v2_catastrophic_veto": False,
}

BASE_LONG015: dict[str, Any] = {
    **BASE_PAIRWISE,
    "enable_selection_pairwise_v2_volume_tilt": True,
    "selection_pairwise_volume_tilt_strength": 0.0,
    "selection_pairwise_volume_tilt_long_strength": 0.15,
    "selection_pairwise_volume_tilt_short_strength": 0.0,
}


def build_base_volume_overrides(reference: float) -> dict[str, Any]:
    return {
        **BASE_LONG015,
        "selection_pairwise_volume_tilt_long_base_volume_reference": reference,
    }


EXPERIMENTS: tuple[dict[str, Any], ...] = (
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long015",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long015_base_volume_stability",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long015 Base Volume Stability",
        "strategy_overrides": BASE_LONG015,
    },
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long015_volref25",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref25_stability",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long015 VolRef25 Stability",
        "strategy_overrides": build_base_volume_overrides(25.0),
    },
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long015_volref30",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_stability",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long015 VolRef30 Stability",
        "strategy_overrides": build_base_volume_overrides(30.0),
    },
    {
        "experiment_name": "selection_pairwise_v2_volume_tilt_long015_volref35",
        "file_prefix": "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref35_stability",
        "chart_title": "QMT Roll Selection Pairwise v2 Volume Tilt Long015 VolRef35 Stability",
        "strategy_overrides": build_base_volume_overrides(35.0),
    },
)


def run_experiments() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for experiment in EXPERIMENTS:
        experiment_name = str(experiment["experiment_name"])
        strategy_overrides = dict(experiment.get("strategy_overrides", {}))
        print(f"[selection-pairwise-long015-base-volume-stability] running {experiment_name}")
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
    long015_df = summary_df[summary_df["experiment_name"] == "selection_pairwise_v2_volume_tilt_long015"]
    if not long015_df.empty:
        long015_row = long015_df.iloc[0]
        payload["comparison_vs_long015"] = [
            build_comparison_row(long015_row, row)
            for _, row in summary_df.iterrows()
            if str(row["experiment_name"]) != "selection_pairwise_v2_volume_tilt_long015"
        ]
    volref30_df = summary_df[summary_df["experiment_name"] == "selection_pairwise_v2_volume_tilt_long015_volref30"]
    if not volref30_df.empty:
        volref30_row = volref30_df.iloc[0]
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
    print(f"[selection-pairwise-long015-base-volume-stability] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[selection-pairwise-long015-base-volume-stability] summary json: {SUMMARY_JSON_PATH}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()

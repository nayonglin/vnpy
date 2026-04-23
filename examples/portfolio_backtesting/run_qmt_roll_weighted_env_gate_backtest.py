from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest

PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_weighted_env_gate_v1"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary.json"

BASE_RISK_RATIO: float = 0.045

EXPERIMENTS: tuple[dict[str, Any], ...] = (
    {
        "experiment_name": "ungated_baseline",
        "file_prefix": "qmt_roll_ungated_baseline",
        "chart_title": "QMT Roll Ungated Baseline",
        "strategy_overrides": {},
    },
    {
        "experiment_name": "weighted_env_gate_v1",
        "file_prefix": "qmt_roll_weighted_env_gate_v1",
        "chart_title": "QMT Roll Weighted Env Gate v1",
        "strategy_overrides": {
            "enable_weighted_env_gate": True,
            "weighted_env_gate_close_position_good_max": 0.25,
            "weighted_env_gate_close_position_bad_min": 0.60,
            "weighted_env_gate_range_good_min": 0.60,
            "weighted_env_gate_range_bad_max": 0.00,
            "weighted_env_gate_selected_rate_good_max": 0.35,
            "weighted_env_gate_selected_rate_bad_min": 0.75,
            "weighted_env_gate_weight_floor": 0.35,
        },
    },
)


def run_experiments() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for experiment in EXPERIMENTS:
        experiment_name = str(experiment["experiment_name"])
        strategy_overrides = dict(experiment.get("strategy_overrides", {}))
        print(f"[weighted-env-gate] running {experiment_name}")
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
        row = build_summary_row(
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
        rows.append(row)
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
    if len(summary_df) >= 2:
        baseline = summary_df[summary_df["experiment_name"] == "ungated_baseline"]
        gated = summary_df[summary_df["experiment_name"] == "weighted_env_gate_v1"]
        if not baseline.empty and not gated.empty:
            baseline_row = baseline.iloc[0]
            gated_row = gated.iloc[0]
            payload["comparison"] = {
                "end_balance_diff": float(gated_row["end_balance"] - baseline_row["end_balance"]),
                "total_return_pct_diff": float(gated_row["total_return_pct"] - baseline_row["total_return_pct"]),
                "max_dd_percent_diff": float(gated_row["max_dd_percent"] - baseline_row["max_dd_percent"]),
                "sharpe_ratio_diff": float(gated_row["sharpe_ratio"] - baseline_row["sharpe_ratio"]),
                "total_trade_count_diff": int(gated_row["total_trade_count"] - baseline_row["total_trade_count"]),
                "total_slippage_diff": float(gated_row["total_slippage"] - baseline_row["total_slippage"]),
            }
    return payload


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df = run_experiments()
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(build_summary_payload(summary_df), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[weighted-env-gate] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[weighted-env-gate] summary json: {SUMMARY_JSON_PATH}")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)
from qmt_universe import START_DT


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage183_ai_product_pool_source_refresh_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage183_ai_product_pool_source_refresh"
DEFAULT_SOURCE_PREFIX: str = "qmt_roll_stage183_ai_source_floor35"

SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _max_csv_date(path: Path, date_columns: tuple[str, ...]) -> str:
    if not path.exists():
        return ""
    df = pd.read_csv(path, usecols=lambda column: column in set(date_columns))
    for column in date_columns:
        if column in df.columns:
            values = pd.to_datetime(df[column], errors="coerce").dropna()
            if not values.empty:
                return pd.Timestamp(values.max()).date().isoformat()
    return ""


def _build_report(summary: dict[str, Any]) -> str:
    outputs = summary["outputs"]
    return "\n".join(
        [
            "# Stage183 AI Product Pool Source Refresh",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Analysis end: `{summary['analysis_end']}`",
            f"- Source prefix: `{summary['source_prefix']}`",
            f"- Position max date: `{summary['artifact_dates']['position_changes_max_date']}`",
            f"- Candidate max date: `{summary['artifact_dates']['entry_candidate_snapshots_max_date']}`",
            f"- End balance: `{summary['statistics']['end_balance']:,.0f}`",
            f"- Max drawdown: `{summary['statistics']['max_dd_percent']:.4f}%`",
            f"- Sharpe: `{summary['statistics']['sharpe_ratio']:.4f}`",
            "",
            "## Outputs",
            "",
            "| artifact | path |",
            "| --- | --- |",
            *[f"| {key} | `{value}` |" for key, value in outputs.items()],
            "",
            "## Boundary",
            "",
            "This refresh only rebuilds the AI product-pool source attribution artifacts. It does not overwrite the official Stage78 eligibility file.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh floor35 source artifacts for Stage182 AI live inference.")
    parser.add_argument("--analysis-end", default="2026-05-07", help="Analysis end date, YYYY-MM-DD.")
    parser.add_argument("--analysis-start", default=START_DT.date().isoformat(), help="Analysis start date, YYYY-MM-DD.")
    parser.add_argument("--source-prefix", default=DEFAULT_SOURCE_PREFIX, help="Output artifact prefix.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    analysis_start = datetime.strptime(str(args.analysis_start), "%Y-%m-%d")
    analysis_end = datetime.strptime(str(args.analysis_end), "%Y-%m-%d")
    source_prefix = str(args.source_prefix)

    _, _, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=CORR20_06_08_FLOOR35_OVERRIDES,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        capital=200_000,
        save_artifacts=True,
        include_start_year_sweep=False,
        file_prefix=source_prefix,
        chart_title="Stage183 AI Source Floor35 Refresh",
    )

    outputs = {
        "daily": str(OUTPUT_DIR / f"{source_prefix}_daily.csv"),
        "trades": str(OUTPUT_DIR / f"{source_prefix}_trades_2020_2026_04.csv"),
        "position_changes": str(OUTPUT_DIR / f"{source_prefix}_position_changes_2020_2026_04.csv"),
        "entry_candidate_snapshots": str(OUTPUT_DIR / f"{source_prefix}_entry_candidate_snapshots_2020_2026_04.csv"),
        "statistics": str(OUTPUT_DIR / f"{source_prefix}_statistics.json"),
        "summary": str(SUMMARY_PATH),
        "report": str(REPORT_PATH),
    }
    position_path = Path(outputs["position_changes"])
    candidate_path = Path(outputs["entry_candidate_snapshots"])
    artifact_dates = {
        "position_changes_max_date": _max_csv_date(position_path, ("date", "datetime")),
        "entry_candidate_snapshots_max_date": _max_csv_date(candidate_path, ("datetime", "date")),
    }
    summary_row = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        model_tag=MODEL_TAG,
        source_prefix=source_prefix,
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
    )
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "source_prefix": source_prefix,
        "statistics": summary_row,
        "artifact_dates": artifact_dates,
        "outputs": outputs,
        "safety": {
            "overwrites_official_stage78_eligibility": False,
            "real_order_enabled": False,
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_SHORT_ALIAS,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
OUTPUT_PREFIX: str = "qmt_roll_official_stage78_1"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.json"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_official_stage78_manifest()
    strategy_overrides = build_official_stage78_overrides()
    _, _, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=strategy_overrides,
        analysis_start=START_DT,
        analysis_end=END_DT,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=True,
        include_start_year_sweep=False,
        file_prefix=OUTPUT_PREFIX,
        chart_title="QMT Roll Official Stage78-1",
    )
    row = build_summary_row(
        statistics,
        analysis_start=START_DT,
        analysis_end=END_DT,
        short_alias=OFFICIAL_STAGE78_SHORT_ALIAS,
        official_version=OFFICIAL_STAGE78_VERSION,
        capital=OFFICIAL_STAGE78_CAPITAL,
        sizing_equity_cap=strategy_overrides.get("sizing_equity_cap"),
        strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
    )
    summary = pd.DataFrame([row])
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    payload: dict[str, Any] = {
        "short_alias": OFFICIAL_STAGE78_SHORT_ALIAS,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "manifest": manifest,
        "summary": row,
        "outputs": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "file_prefix": OUTPUT_PREFIX,
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[{OFFICIAL_STAGE78_SHORT_ALIAS}] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[{OFFICIAL_STAGE78_SHORT_ALIAS}] summary json: {SUMMARY_JSON_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_range_reversion_core4_v3_exit_structure import _build_round_trips
from analyze_qmt_range_reversion_core4_v6_robustness import (
    _drawdown_event,
    _product_year_summary,
    _quarter_summary,
    _rolling_summary,
    _start_year_summary,
    _year_summary,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_back_adjusted_v7"
MODEL_TAG: str = "range_reversion_core4_v7_robustness_v1"

DAILY_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_daily_equity.csv"
TRADES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"

YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_year_summary_{MODEL_TAG}.csv"
QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_quarter_summary_{MODEL_TAG}.csv"
START_YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_start_year_summary_{MODEL_TAG}.csv"
ROLLING_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_rolling_summary_{MODEL_TAG}.csv"
PRODUCT_YEAR_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_product_year_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_robustness_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v7_robustness_report_{MODEL_TAG}.md"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not DAILY_PATH.exists():
        raise FileNotFoundError(DAILY_PATH)
    if not TRADES_PATH.exists():
        raise FileNotFoundError(TRADES_PATH)
    if not ENTRY_RISK_PATH.exists():
        raise FileNotFoundError(ENTRY_RISK_PATH)

    daily = pd.read_csv(DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date").reset_index(drop=True)

    trades = pd.read_csv(TRADES_PATH)
    entries = pd.read_csv(ENTRY_RISK_PATH)
    round_trips = _build_round_trips(trades, entries)
    if not round_trips.empty:
        round_trips["entry_year"] = pd.to_datetime(round_trips["entry_datetime"]).dt.year
        round_trips["entry_quarter"] = pd.to_datetime(round_trips["entry_datetime"]).dt.to_period("Q").astype(str)
    return daily, round_trips


def _write_report(
    year_summary: pd.DataFrame,
    quarter_summary: pd.DataFrame,
    start_year_summary: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    product_year_summary: pd.DataFrame,
    drawdown_event: dict[str, Any],
) -> None:
    worst_rolling = rolling_summary.head(10)
    lines = [
        "# QMT Range Reversion Core4 V7 Robustness",
        "",
        "## Scope",
        "- This report reads the existing v7 curve and trades only; no new backtest is run.",
        "- V7 differs from v6 by using additive back-adjusted product-continuous signal history.",
        "",
        "## Drawdown Event",
        json.dumps(drawdown_event, ensure_ascii=False, indent=2),
        "",
        "## Year Summary",
        year_summary.to_markdown(index=False) if not year_summary.empty else "- Empty.",
        "",
        "## Start-Year Summary",
        start_year_summary.to_markdown(index=False) if not start_year_summary.empty else "- Empty.",
        "",
        "## Worst Rolling Windows",
        worst_rolling.to_markdown(index=False) if not worst_rolling.empty else "- Empty.",
        "",
        "## Quarter Summary",
        quarter_summary.to_markdown(index=False) if not quarter_summary.empty else "- Empty.",
        "",
        "## Product Year Summary",
        product_year_summary.to_markdown(index=False) if not product_year_summary.empty else "- Empty.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    daily, round_trips = _load_inputs()
    year_summary = _year_summary(daily)
    quarter_summary = _quarter_summary(daily)
    start_year_summary = _start_year_summary(daily)
    rolling_summary = _rolling_summary(daily)
    product_year_summary = _product_year_summary(round_trips)
    drawdown_event = _drawdown_event(daily)

    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    quarter_summary.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    start_year_summary.to_csv(START_YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    rolling_summary.to_csv(ROLLING_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_year_summary.to_csv(PRODUCT_YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    negative_years = year_summary[year_summary["net_pnl"] < 0]["year"].astype(str).tolist()
    worst_year = year_summary.sort_values("net_pnl").head(1).to_dict("records")
    worst_252 = rolling_summary[rolling_summary["window_days"].eq(252)].head(1).to_dict("records")
    payload = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "negative_years": negative_years,
        "worst_year": worst_year[0] if worst_year else {},
        "worst_252d_window": worst_252[0] if worst_252 else {},
        "drawdown_event": drawdown_event,
        "outputs": {
            "year_summary": str(YEAR_SUMMARY_PATH),
            "quarter_summary": str(QUARTER_SUMMARY_PATH),
            "start_year_summary": str(START_YEAR_SUMMARY_PATH),
            "rolling_summary": str(ROLLING_SUMMARY_PATH),
            "product_year_summary": str(PRODUCT_YEAR_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(year_summary, quarter_summary, start_year_summary, rolling_summary, product_year_summary, drawdown_event)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(year_summary.to_string(index=False))
    print(start_year_summary.to_string(index=False))
    print(rolling_summary.head(10).to_string(index=False))
    print(product_year_summary.to_string(index=False))


if __name__ == "__main__":
    main()

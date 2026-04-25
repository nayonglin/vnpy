from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    CYCLE_WINDOWS,
    to_markdown_table,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage78_sizing_cap_multicycle_v1"
OUTPUT_PREFIX: str = "qmt_roll_official_stage78_sizing_cap_multicycle"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

DEFAULT_SIZING_EQUITY_CAP: float = 1_000_000.0
DISABLED_SIZING_EQUITY_CAP: float = 0.0

PROFILE_CAPPED: str = "stage78_capped_1m"
PROFILE_NO_CAP: str = "stage78_sizing_cap_off"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_profiles() -> tuple[dict[str, Any], ...]:
    official_overrides = build_official_stage78_overrides()
    return (
        {
            "profile_name": PROFILE_CAPPED,
            "display_name": "Stage78 capped at 1m sizing equity",
            "sizing_equity_cap": DEFAULT_SIZING_EQUITY_CAP,
            "strategy_overrides": {
                **official_overrides,
                "sizing_equity_cap": DEFAULT_SIZING_EQUITY_CAP,
            },
        },
        {
            "profile_name": PROFILE_NO_CAP,
            "display_name": "Stage78 sizing equity cap off",
            "sizing_equity_cap": DISABLED_SIZING_EQUITY_CAP,
            "strategy_overrides": {
                **official_overrides,
                "sizing_equity_cap": DISABLED_SIZING_EQUITY_CAP,
            },
        },
    )


def run_multicycle_backtests() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    profiles = build_profiles()

    for window in CYCLE_WINDOWS:
        window_name = str(window["window_name"])
        display_label = str(window["display_label"])
        analysis_start: datetime = window["analysis_start"]
        analysis_end: datetime = window["analysis_end"]
        for profile in profiles:
            profile_name = str(profile["profile_name"])
            strategy_overrides = dict(profile["strategy_overrides"])
            print(
                f"[stage78-sizing-cap] {window_name} / {profile_name}: "
                f"{analysis_start.date()} -> {analysis_end.date()}"
            )
            _, _, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
            rows.append(
                build_summary_row(
                    statistics,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    official_version=OFFICIAL_STAGE78_VERSION,
                    official_role=OFFICIAL_STAGE78_ROLE,
                    window_name=window_name,
                    display_label=display_label,
                    profile_name=profile_name,
                    display_name=str(profile["display_name"]),
                    sizing_equity_cap=float(profile["sizing_equity_cap"]),
                    strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                    total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                    total_slippage=float(statistics.get("total_slippage", 0) or 0),
                    total_commission=float(statistics.get("total_commission", 0) or 0),
                    profit_days=int(statistics.get("profit_days", 0) or 0),
                    loss_days=int(statistics.get("loss_days", 0) or 0),
                )
            )

    return pd.DataFrame(rows).sort_values(["analysis_start", "profile_name"]).reset_index(drop=True)


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary.groupby("window_name", sort=False):
        capped_rows = group[group["profile_name"] == PROFILE_CAPPED]
        no_cap_rows = group[group["profile_name"] == PROFILE_NO_CAP]
        if capped_rows.empty or no_cap_rows.empty:
            continue
        capped = capped_rows.iloc[0]
        no_cap = no_cap_rows.iloc[0]
        rows.append(
            {
                "window_name": window_name,
                "display_label": str(no_cap["display_label"]),
                "analysis_start": str(no_cap["analysis_start"]),
                "analysis_end": str(no_cap["analysis_end"]),
                "capped_end_balance": _safe_float(capped["end_balance"]),
                "no_cap_end_balance": _safe_float(no_cap["end_balance"]),
                "no_cap_end_balance_diff": _safe_float(no_cap["end_balance"]) - _safe_float(capped["end_balance"]),
                "capped_total_return_pct": _safe_float(capped["total_return_pct"]),
                "no_cap_total_return_pct": _safe_float(no_cap["total_return_pct"]),
                "no_cap_total_return_pct_diff": _safe_float(no_cap["total_return_pct"])
                - _safe_float(capped["total_return_pct"]),
                "capped_max_dd_percent": _safe_float(capped["max_dd_percent"]),
                "no_cap_max_dd_percent": _safe_float(no_cap["max_dd_percent"]),
                "no_cap_max_dd_percent_diff": _safe_float(no_cap["max_dd_percent"])
                - _safe_float(capped["max_dd_percent"]),
                "capped_sharpe": _safe_float(capped["sharpe_ratio"]),
                "no_cap_sharpe": _safe_float(no_cap["sharpe_ratio"]),
                "no_cap_sharpe_diff": _safe_float(no_cap["sharpe_ratio"]) - _safe_float(capped["sharpe_ratio"]),
                "capped_trade_count": int(_safe_float(capped["total_trade_count"])),
                "no_cap_trade_count": int(_safe_float(no_cap["total_trade_count"])),
                "no_cap_trade_count_diff": int(_safe_float(no_cap["total_trade_count"]) - _safe_float(capped["total_trade_count"])),
                "capped_slippage": _safe_float(capped["total_slippage"]),
                "no_cap_slippage": _safe_float(no_cap["total_slippage"]),
                "no_cap_slippage_diff": _safe_float(no_cap["total_slippage"]) - _safe_float(capped["total_slippage"]),
            }
        )
    return pd.DataFrame(rows)


def build_report(summary: pd.DataFrame, comparison: pd.DataFrame) -> str:
    return "\n".join(
        [
            f"# {OFFICIAL_STAGE78_VERSION} Sizing Cap Multicycle Backtest",
            "",
            "## Purpose",
            "",
            "- Compare the official Stage78 defensive profile with and without the 1,000,000 sizing-equity cap.",
            "- This is a research test; the formal Stage78 baseline remains capped unless promoted later.",
            "",
            "## Parameters",
            "",
            f"- Base risk ratio: `{BASE_RISK_RATIO}`",
            f"- Capital: `{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
            f"- Capped sizing equity cap: `{DEFAULT_SIZING_EQUITY_CAP:,.0f}`",
            f"- No-cap sizing equity cap: `{DISABLED_SIZING_EQUITY_CAP:,.0f}`",
            "",
            "## Comparison",
            "",
            to_markdown_table(
                comparison[
                    [
                        "window_name",
                        "capped_end_balance",
                        "no_cap_end_balance",
                        "no_cap_end_balance_diff",
                        "capped_max_dd_percent",
                        "no_cap_max_dd_percent",
                        "no_cap_sharpe",
                        "no_cap_trade_count",
                    ]
                ]
            ),
            "",
            "## Raw Summary",
            "",
            to_markdown_table(
                summary[
                    [
                        "window_name",
                        "profile_name",
                        "end_balance",
                        "total_return_pct",
                        "max_dd_percent",
                        "sharpe_ratio",
                        "total_slippage",
                        "total_trade_count",
                    ]
                ].head(30)
            ),
            "",
            "## Judgement Rules",
            "",
            "- Removing the cap is valuable only if multi-cycle improvement is not just full-cycle compounding.",
            "- If drawdown expands faster than return quality, keep the cap as formal protection.",
            "- Latest-tail and weak-cycle behavior are more important than headline full-cycle equity.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = run_multicycle_backtests()
    comparison = build_comparison(summary)
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "default_sizing_equity_cap": DEFAULT_SIZING_EQUITY_CAP,
        "disabled_sizing_equity_cap": DISABLED_SIZING_EQUITY_CAP,
        "summary": summary.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
        "outputs": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "comparison_csv": str(COMPARISON_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, comparison), encoding="utf-8")
    print(comparison.to_string(index=False))
    print(f"[stage78-sizing-cap] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage78-sizing-cap] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

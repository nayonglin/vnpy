from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage78_400k_margin_profile_surface import OverlayProfile, _run_window
from analyze_qmt_roll_stage78_400k_stage111_margin_overlay import (
    CAPITAL,
    HORIZON_DAYS,
    SIZING_EQUITY_CAP,
    _aggregate_horizons,
    _load_stage78_400k_reference,
    _slice_margin,
    _stage111_reference,
    _summarize_slice,
    _to_markdown_table,
    _window_name,
    quarter_starts,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION
from qmt_roll_stage111_400k_margin_safe_config import STAGE111_VERSION
from qmt_universe import END_DT, START_DT
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage120_stage78_400k_decoupled_margin_surface_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage78_400k_decoupled_margin_surface"

STAGE119_FULL_SUMMARY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_400k_margin_profile_surface_full_summary_"
    "stage119_stage78_400k_margin_profile_surface_v1.csv"
)
STAGE119_HORIZON_AGGREGATE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_400k_margin_profile_surface_horizon_aggregate_"
    "stage119_stage78_400k_margin_profile_surface_v1.csv"
)

QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_summary_{MODEL_TAG}.csv"
HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
HORIZON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv"
FULL_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_summary_{MODEL_TAG}.csv"
FULL_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_comparison_{MODEL_TAG}.csv"
HORIZON_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


RUN_PROFILES: tuple[OverlayProfile, ...] = (
    OverlayProfile("stage78_cap55_single25", 0.55, 0.25),
    OverlayProfile("stage78_cap60_single25", 0.60, 0.25),
)


def _base_fields(profile: OverlayProfile, analysis_start: datetime) -> dict[str, Any]:
    return {
        "model_tag": MODEL_TAG,
        "profile_name": profile.profile_name,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "overlay_version": STAGE111_VERSION,
        "capital": CAPITAL,
        "sizing_equity_cap": SIZING_EQUITY_CAP,
        "base_risk_ratio": BASE_RISK_RATIO,
        "max_capital_usage_ratio": profile.max_capital_usage_ratio,
        "max_single_trade_capital_usage_ratio": profile.max_single_trade_capital_usage_ratio,
        "window_name": _window_name(analysis_start),
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
    }


def _run_profile(profile: OverlayProfile) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    quarter_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    full_row: dict[str, Any] | None = None

    for analysis_start in quarter_starts():
        daily, daily_margin, statistics = _run_window(profile, analysis_start)
        base_fields = _base_fields(profile, analysis_start)
        quarter_row = {**base_fields, "horizon": "to_end", **_summarize_slice(daily, daily_margin)}
        quarter_rows.append(quarter_row)

        if analysis_start == START_DT:
            full_row = {
                "profile_name": profile.profile_name,
                "version": MODEL_TAG,
                "capital": CAPITAL,
                "sizing_equity_cap": SIZING_EQUITY_CAP,
                "max_capital_usage_ratio": profile.max_capital_usage_ratio,
                "max_single_trade_capital_usage_ratio": profile.max_single_trade_capital_usage_ratio,
                "end_balance": float(statistics.get("end_balance", 0.0) or 0.0),
                "total_return_pct": float(statistics.get("total_return", 0.0) or 0.0),
                "max_dd_percent": float(statistics.get("max_ddpercent", 0.0) or 0.0),
                "sharpe_ratio": float(statistics.get("sharpe_ratio", 0.0) or 0.0),
                "total_slippage": float(statistics.get("total_slippage", 0.0) or 0.0),
                "total_trade_count": float(statistics.get("total_trade_count", 0.0) or 0.0),
                "win_ratio_pct": float(statistics.get("win_ratio", 0.0) or 0.0),
                "max_margin_to_balance_pct": quarter_row["max_margin_to_balance_pct"],
                "margin_days_gt_80pct": quarter_row["margin_days_gt_80pct"],
                "margin_days_gt_100pct": quarter_row["margin_days_gt_100pct"],
            }

        for horizon_days in HORIZON_DAYS:
            daily_slice = daily.iloc[:horizon_days].copy()
            horizon_rows.append(
                {
                    **base_fields,
                    "horizon": f"{horizon_days}d",
                    "horizon_days": horizon_days,
                    "complete_horizon": int(len(daily_slice) >= horizon_days),
                    **_summarize_slice(daily_slice, _slice_margin(daily_slice, daily_margin)),
                }
            )

    if full_row is None:
        raise RuntimeError(f"missing full row for {profile.profile_name}")
    return pd.DataFrame(quarter_rows), pd.DataFrame(horizon_rows), full_row


def _reference_full_rows() -> list[dict[str, Any]]:
    stage78_full, _ = _load_stage78_400k_reference()
    stage78_full.update(
        {
            "sizing_equity_cap": SIZING_EQUITY_CAP,
            "max_capital_usage_ratio": 0.90,
            "max_single_trade_capital_usage_ratio": 0.70,
            "margin_days_gt_80pct": np.nan,
            "margin_days_gt_100pct": np.nan,
        }
    )
    stage111_full, _ = _stage111_reference()
    stage111_full.update(
        {
            "sizing_equity_cap": SIZING_EQUITY_CAP,
            "max_capital_usage_ratio": 0.45,
            "max_single_trade_capital_usage_ratio": 0.20,
            "margin_days_gt_80pct": 0.0,
            "margin_days_gt_100pct": 0.0,
        }
    )
    return [stage78_full, stage111_full]


def _load_stage119_references() -> tuple[pd.DataFrame, pd.DataFrame]:
    full = pd.read_csv(STAGE119_FULL_SUMMARY_PATH) if STAGE119_FULL_SUMMARY_PATH.exists() else pd.DataFrame()
    horizon = pd.read_csv(STAGE119_HORIZON_AGGREGATE_PATH) if STAGE119_HORIZON_AGGREGATE_PATH.exists() else pd.DataFrame()
    return full, horizon


def _build_report(full_comparison: pd.DataFrame, horizon_comparison: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage78 400k Decoupled Margin Surface",
            "",
            "## Boundary",
            "",
            "- Keep Stage78 trading logic unchanged.",
            "- Keep single-trade cap at the safer `0.25` from Stage119.",
            "- Only relax total portfolio cap to test whether risk comes from position concurrency or single-trade size.",
            f"- Capital: `{CAPITAL:,.0f}`",
            f"- Sizing equity cap: `{SIZING_EQUITY_CAP:,.0f}`",
            "",
            "## Full Comparison",
            "",
            _to_markdown_table(
                full_comparison,
                [
                    "profile_name",
                    "max_capital_usage_ratio",
                    "max_single_trade_capital_usage_ratio",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                    "win_ratio_pct",
                    "max_margin_to_balance_pct",
                    "margin_days_gt_80pct",
                    "margin_days_gt_100pct",
                ],
                max_rows=30,
            ),
            "",
            "## Horizon Comparison",
            "",
            _to_markdown_table(
                horizon_comparison,
                [
                    "profile_name",
                    "horizon",
                    "window_count",
                    "positive_return_rate_pct",
                    "median_return_pct",
                    "worst_return_pct",
                    "worst_max_dd_percent",
                    "median_sharpe",
                    "worst_sharpe",
                    "max_margin_to_balance_pct",
                    "windows_margin_gt_80pct",
                    "windows_margin_gt_100pct",
                ],
                max_rows=90,
            ),
            "",
            "## Judgement Rule",
            "",
            "- If relaxing total cap improves return without any quarterly margin >80%, concurrency was not the main danger.",
            "- If margin still breaks 80%, Stage78 needs the stricter shell and the combination is not a formal breakthrough.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    quarter_frames: list[pd.DataFrame] = []
    horizon_frames: list[pd.DataFrame] = []
    full_rows: list[dict[str, Any]] = []

    for profile in RUN_PROFILES:
        quarter, horizon, full = _run_profile(profile)
        quarter_frames.append(quarter)
        horizon_frames.append(horizon)
        full_rows.append(full)

    quarter_summary = pd.concat(quarter_frames, ignore_index=True, sort=False)
    horizon_summary = pd.concat(horizon_frames, ignore_index=True, sort=False)
    horizon_aggregate = _aggregate_horizons(horizon_summary)
    new_full_summary = pd.DataFrame(full_rows)

    stage119_full, stage119_horizon = _load_stage119_references()
    full_summary = pd.concat([stage119_full, new_full_summary], ignore_index=True, sort=False)
    full_summary.sort_values(["max_capital_usage_ratio", "max_single_trade_capital_usage_ratio"], ascending=False, inplace=True)
    horizon_comparison = pd.concat([stage119_horizon, horizon_aggregate], ignore_index=True, sort=False)
    horizon_comparison.sort_values(["horizon", "profile_name"], inplace=True)

    full_comparison = pd.concat([pd.DataFrame(_reference_full_rows()), full_summary], ignore_index=True, sort=False)

    quarter_summary.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_summary.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_aggregate.to_csv(HORIZON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    full_summary.to_csv(FULL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    full_comparison.to_csv(FULL_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    horizon_comparison.to_csv(HORIZON_COMPARISON_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "capital": CAPITAL,
        "sizing_equity_cap": SIZING_EQUITY_CAP,
        "run_profiles": [profile.__dict__ for profile in RUN_PROFILES],
        "full_comparison": full_comparison.to_dict(orient="records"),
        "horizon_comparison": horizon_comparison.to_dict(orient="records"),
        "output_paths": {
            "quarter_summary": str(QUARTER_SUMMARY_PATH),
            "horizon_summary": str(HORIZON_SUMMARY_PATH),
            "horizon_aggregate": str(HORIZON_AGGREGATE_PATH),
            "full_summary": str(FULL_SUMMARY_PATH),
            "full_comparison": str(FULL_COMPARISON_PATH),
            "horizon_comparison": str(HORIZON_COMPARISON_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(full_comparison, horizon_comparison), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[stage78-decoupled-margin] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

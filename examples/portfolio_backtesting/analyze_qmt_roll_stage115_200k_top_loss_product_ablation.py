from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import _calculate_daily_risk, _calculate_margin_path
from qmt_roll_stage115_200k_granularity_safe_config import (
    STAGE115_CAPITAL,
    STAGE115_PROFILE_NAME,
    STAGE115_UNIVERSE_PATH,
    STAGE115_VERSION,
    build_stage115_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage117_stage115_200k_top_loss_product_ablation_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage115_200k_top_loss_product_ablation"
STAGE114_HORIZON_SUMMARY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage111_200k_granularity_quarterly_walkforward_horizon_summary_"
    "stage114_stage111_200k_granularity_quarterly_wf_v1.csv"
)
STAGE115_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_stage115_200k_granularity_safe_candidate_summary.json"

WEAK_HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_weak_horizon_summary_{MODEL_TAG}.csv"
WEAK_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_weak_aggregate_{MODEL_TAG}.csv"
FULL_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PROFILE_EXCLUSIONS: dict[str, tuple[str, ...]] = {
    "baseline_stage115": (),
    "exclude_fu": ("fu.SHFE",),
    "exclude_fu_sm": ("fu.SHFE", "SM.CZCE"),
}


def _read_weak_rows() -> pd.DataFrame:
    df = pd.read_csv(STAGE114_HORIZON_SUMMARY_PATH)
    df["complete_horizon"] = pd.to_numeric(df["complete_horizon"], errors="coerce").fillna(0).astype(int)
    df["total_return_pct"] = pd.to_numeric(df["total_return_pct"], errors="coerce").fillna(0.0)
    weak = df[(df["complete_horizon"] == 1) & (df["total_return_pct"] <= 0.0)].copy()
    weak["horizon_days"] = pd.to_numeric(weak["horizon_days"], errors="coerce").fillna(0).astype(int)
    weak["analysis_start_dt"] = pd.to_datetime(weak["analysis_start"])
    weak.sort_values(["analysis_start_dt", "horizon_days"], inplace=True)
    weak.reset_index(drop=True, inplace=True)
    return weak


def _write_profile_universe(profile_name: str, exclusions: tuple[str, ...]) -> Path:
    base = pd.read_csv(STAGE115_UNIVERSE_PATH)
    if "product_vt_symbol" not in base.columns:
        raise ValueError(f"missing product_vt_symbol in {STAGE115_UNIVERSE_PATH}")
    result = base[~base["product_vt_symbol"].astype(str).isin(set(exclusions))].copy()
    result["stage117_profile_name"] = profile_name
    result["stage117_excluded_products"] = ",".join(exclusions)
    path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_{profile_name}_universe_{MODEL_TAG}.csv"
    result.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _build_overrides(universe_path: Path) -> dict[str, Any]:
    overrides = build_stage115_overrides()
    overrides["product_universe_csv_path"] = str(universe_path)
    return overrides


def _calendar_end_for_horizon(analysis_start: pd.Timestamp, max_horizon_days: int) -> datetime:
    calendar_days = int(max_horizon_days * 2 + 45)
    return min(analysis_start.to_pydatetime() + timedelta(days=calendar_days), END_DT)


def _run_window(
    *,
    profile_name: str,
    overrides: dict[str, Any],
    analysis_start: datetime,
    analysis_end: datetime,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    print(f"[stage115-top-loss-ablation] {profile_name} {analysis_start.date()} -> {analysis_end.date()}", flush=True)
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=STAGE115_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise
    daily_df = daily.copy() if daily is not None else pd.DataFrame()
    if not daily_df.empty:
        daily_df.sort_index(inplace=True)
    positions = build_positions_df(engine)
    return daily_df, positions, statistics


def _summarize_daily_slice(daily_slice: pd.DataFrame, positions: pd.DataFrame) -> dict[str, float]:
    if daily_slice.empty:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "max_margin_to_balance_pct": 0.0,
        }
    balance = pd.to_numeric(daily_slice["balance"], errors="coerce").ffill().fillna(STAGE115_CAPITAL)
    net_pnl = pd.to_numeric(daily_slice.get("net_pnl", pd.Series(0.0, index=daily_slice.index)), errors="coerce").fillna(0.0)
    previous_balance = balance.shift(1).fillna(STAGE115_CAPITAL).replace(0.0, np.nan)
    daily_return = (net_pnl / previous_balance).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    high_water = balance.cummax()
    dd_pct = (balance / high_water.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
    std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / std * math.sqrt(240)) if std > 1e-12 else 0.0

    margin_max = 0.0
    if positions is not None and not positions.empty:
        daily_risk = _calculate_daily_risk(daily_slice, STAGE115_CAPITAL)
        daily_margin, _ = _calculate_margin_path(positions, daily_risk, capital=STAGE115_CAPITAL)
        if not daily_margin.empty:
            margin_max = float(pd.to_numeric(daily_margin["total_margin_to_balance_pct"], errors="coerce").fillna(0.0).max())

    end_balance = float(balance.iloc[-1])
    return {
        "end_balance": end_balance,
        "total_return_pct": (end_balance - STAGE115_CAPITAL) / STAGE115_CAPITAL * 100.0,
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
        "total_slippage": float(pd.to_numeric(daily_slice.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(daily_slice.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "max_margin_to_balance_pct": margin_max,
    }


def _full_reference_row() -> dict[str, Any]:
    if not STAGE115_SUMMARY_PATH.exists():
        return {}
    payload = json.loads(STAGE115_SUMMARY_PATH.read_text(encoding="utf-8"))
    row = payload["experiments"][0]
    return {
        "model_tag": MODEL_TAG,
        "profile_name": "baseline_stage115",
        "excluded_products": "",
        "source": "frozen_stage115_reference",
        "end_balance": float(row["end_balance"]),
        "total_return_pct": float(row["total_return_pct"]),
        "max_dd_percent": float(row["max_dd_percent"]),
        "sharpe_ratio": float(row["sharpe_ratio"]),
        "total_slippage": float(row["total_slippage"]),
        "total_trade_count": float(row["total_trade_count"]),
        "win_ratio_pct": float(row["win_ratio_pct"]),
    }


def _aggregate_weak(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    aggregate = (
        rows.groupby("profile_name", as_index=False)
        .agg(
            weak_window_count=("window_name", "count"),
            positive_after_ablation_count=("total_return_pct", lambda s: int((s > 0).sum())),
            non_positive_after_ablation_count=("total_return_pct", lambda s: int((s <= 0).sum())),
            median_return_pct=("total_return_pct", "median"),
            worst_return_pct=("total_return_pct", "min"),
            mean_return_pct=("total_return_pct", "mean"),
            worst_max_dd_percent=("max_dd_percent", "min"),
            max_margin_to_balance_pct=("max_margin_to_balance_pct", "max"),
            total_trade_count=("total_trade_count", "sum"),
        )
        .sort_values("profile_name")
        .reset_index(drop=True)
    )
    aggregate["positive_after_ablation_rate_pct"] = (
        aggregate["positive_after_ablation_count"] / aggregate["weak_window_count"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    return aggregate


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, columns].head(max_rows).copy()
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def _build_report(full_summary: pd.DataFrame, weak_aggregate: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage115 200k Top Loss Product Ablation",
            "",
            "## Boundary",
            "",
            "- This is an ablation, not a promotion.",
            "- Only products identified by Stage116 weak-window attribution are removed.",
            "- The test checks whether removing top weak-window loss products improves cold-start stability enough to justify the full-cycle opportunity cost.",
            "",
            "## Full Window",
            "",
            _to_markdown_table(
                full_summary,
                [
                    "profile_name",
                    "excluded_products",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                ],
                max_rows=10,
            ),
            "",
            "## Weak Window Aggregate",
            "",
            _to_markdown_table(
                weak_aggregate,
                [
                    "profile_name",
                    "weak_window_count",
                    "positive_after_ablation_rate_pct",
                    "median_return_pct",
                    "worst_return_pct",
                    "worst_max_dd_percent",
                    "max_margin_to_balance_pct",
                ],
                max_rows=10,
            ),
            "",
            "## Judgement",
            "",
            "- A product exclusion is only worth considering if it improves weak windows and does not destroy the full-window return/risk profile.",
            "- If the full-window cost is large, prefer targeted risk throttles or accept the weak windows rather than deleting a productive product.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    weak = _read_weak_rows()
    weak_rows: list[dict[str, Any]] = []
    full_rows: list[dict[str, Any]] = []

    baseline_full = _full_reference_row()
    if baseline_full:
        full_rows.append(baseline_full)

    for profile_name, exclusions in PROFILE_EXCLUSIONS.items():
        universe_path = STAGE115_UNIVERSE_PATH if not exclusions else _write_profile_universe(profile_name, exclusions)
        overrides = _build_overrides(universe_path)

        if exclusions:
            daily, _, statistics = _run_window(
                profile_name=profile_name,
                overrides=overrides,
                analysis_start=START_DT,
                analysis_end=END_DT,
            )
            full_rows.append(
                {
                    "model_tag": MODEL_TAG,
                    "profile_name": profile_name,
                    "excluded_products": ",".join(exclusions),
                    "source": "fresh_full_backtest",
                    "end_balance": float(statistics.get("end_balance", 0.0) or 0.0),
                    "total_return_pct": float(statistics.get("total_return", 0.0) or 0.0),
                    "max_dd_percent": float(statistics.get("max_ddpercent", 0.0) or 0.0),
                    "sharpe_ratio": float(statistics.get("sharpe_ratio", 0.0) or 0.0),
                    "total_slippage": float(statistics.get("total_slippage", 0.0) or 0.0),
                    "total_trade_count": float(statistics.get("total_trade_count", 0.0) or 0.0),
                    "win_ratio_pct": float(statistics.get("win_ratio", 0.0) or 0.0),
                }
            )

        grouped = weak.groupby("analysis_start_dt", sort=True)
        for analysis_start, group in grouped:
            max_horizon_days = int(group["horizon_days"].max())
            analysis_end = _calendar_end_for_horizon(analysis_start, max_horizon_days)
            daily, positions, _ = _run_window(
                profile_name=profile_name,
                overrides=overrides,
                analysis_start=analysis_start.to_pydatetime(),
                analysis_end=analysis_end,
            )
            for _, weak_row in group.iterrows():
                horizon_days = int(weak_row["horizon_days"])
                daily_slice = daily.iloc[:horizon_days].copy()
                summary = _summarize_daily_slice(daily_slice, positions)
                weak_rows.append(
                    {
                        "model_tag": MODEL_TAG,
                        "base_version": STAGE115_VERSION,
                        "base_profile_name": STAGE115_PROFILE_NAME,
                        "profile_name": profile_name,
                        "excluded_products": ",".join(exclusions),
                        "window_name": weak_row["window_name"],
                        "analysis_start": weak_row["analysis_start"],
                        "horizon": weak_row["horizon"],
                        "horizon_days": horizon_days,
                        "baseline_return_pct": float(weak_row["total_return_pct"]),
                        "baseline_max_dd_percent": float(weak_row["max_dd_percent"]),
                        **summary,
                    }
                )

    weak_summary = pd.DataFrame(weak_rows)
    weak_aggregate = _aggregate_weak(weak_summary)
    full_summary = pd.DataFrame(full_rows)

    weak_summary.to_csv(WEAK_HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    weak_aggregate.to_csv(WEAK_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    full_summary.to_csv(FULL_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "base_version": STAGE115_VERSION,
        "capital": STAGE115_CAPITAL,
        "profiles": {profile: list(exclusions) for profile, exclusions in PROFILE_EXCLUSIONS.items()},
        "full_summary": full_summary.to_dict(orient="records"),
        "weak_aggregate": weak_aggregate.to_dict(orient="records"),
        "output_paths": {
            "weak_horizon_summary": str(WEAK_HORIZON_SUMMARY_PATH),
            "weak_aggregate": str(WEAK_AGGREGATE_PATH),
            "full_summary": str(FULL_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(full_summary, weak_aggregate), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[stage115-top-loss-ablation] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

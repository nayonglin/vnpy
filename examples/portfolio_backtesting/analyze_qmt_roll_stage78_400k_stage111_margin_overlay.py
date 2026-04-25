from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import _calculate_daily_risk, _calculate_margin_path
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION, build_official_stage78_overrides
from qmt_roll_stage111_400k_margin_safe_config import (
    STAGE111_MARGIN_PROFILE,
    STAGE111_QUARTERLY_VALIDATION,
    STAGE111_REFERENCE_METRICS,
    STAGE111_VERSION,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage118_stage78_400k_stage111_margin_overlay_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage78_400k_stage111_margin_overlay"
CAPITAL: float = 400_000.0
SIZING_EQUITY_CAP: float = 1_000_000.0
TRADING_DAYS_PER_YEAR: int = 240
HORIZON_DAYS: tuple[int, ...] = (63, 126, 252)

STAGE78_400K_BASELINE_HORIZON_AGGREGATE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_horizon_aggregate_"
    "stage78_400k_cap_ladder_quarterly_wf_v1.csv"
)
STAGE78_400K_BASELINE_QUARTER_SUMMARY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_quarter_summary_"
    "stage78_400k_cap_ladder_quarterly_wf_v1.csv"
)

QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_summary_{MODEL_TAG}.csv"
HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
HORIZON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv"
FULL_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_comparison_{MODEL_TAG}.csv"
HORIZON_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def quarter_starts() -> list[datetime]:
    starts = pd.date_range(START_DT, END_DT, freq="QS")
    if not starts.empty and starts[0].to_pydatetime() != START_DT:
        starts = pd.DatetimeIndex([pd.Timestamp(START_DT), *starts])
    return [ts.to_pydatetime() for ts in starts if ts.to_pydatetime() <= END_DT]


def _window_name(analysis_start: datetime) -> str:
    return f"q{analysis_start.year}_{((analysis_start.month - 1) // 3) + 1}"


def build_overlay_overrides() -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["sizing_equity_cap"] = SIZING_EQUITY_CAP
    overrides.update(STAGE111_MARGIN_PROFILE)
    return overrides


def _slice_margin(daily_slice: pd.DataFrame, daily_margin: pd.DataFrame) -> pd.DataFrame:
    if daily_slice.empty or daily_margin.empty:
        return daily_margin.iloc[:0].copy()
    dates = pd.to_datetime(daily_slice.index).normalize()
    return daily_margin[daily_margin["date"].isin(dates)].copy()


def _summarize_slice(daily_slice: pd.DataFrame, margin_slice: pd.DataFrame) -> dict[str, float]:
    if daily_slice.empty:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "day_count": 0.0,
            "max_margin_to_balance_pct": 0.0,
            "margin_days_gt_80pct": 0.0,
            "margin_days_gt_100pct": 0.0,
        }

    balance = pd.to_numeric(daily_slice["balance"], errors="coerce").ffill().fillna(CAPITAL)
    net_pnl = pd.to_numeric(daily_slice.get("net_pnl", pd.Series(0.0, index=daily_slice.index)), errors="coerce").fillna(0.0)
    previous_balance = balance.shift(1).fillna(CAPITAL).replace(0.0, np.nan)
    daily_return = (net_pnl / previous_balance).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    high_water = balance.cummax()
    dd_pct = (balance / high_water.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
    std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 1e-12 else 0.0
    end_balance = float(balance.iloc[-1])

    margin_to_balance = (
        pd.to_numeric(margin_slice["total_margin_to_balance_pct"], errors="coerce").fillna(0.0)
        if not margin_slice.empty
        else pd.Series(dtype=float)
    )
    return {
        "end_balance": end_balance,
        "total_return_pct": (end_balance - CAPITAL) / CAPITAL * 100.0,
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
        "total_slippage": float(pd.to_numeric(daily_slice.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(daily_slice.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "day_count": float(len(daily_slice)),
        "max_margin_to_balance_pct": float(margin_to_balance.max()) if not margin_to_balance.empty else 0.0,
        "margin_days_gt_80pct": float((margin_to_balance > 80.0).sum()) if not margin_to_balance.empty else 0.0,
        "margin_days_gt_100pct": float((margin_to_balance > 100.0).sum()) if not margin_to_balance.empty else 0.0,
    }


def _run_window(analysis_start: datetime) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    print(f"[stage78-111-overlay] {_window_name(analysis_start)}: {analysis_start.date()} -> {END_DT.date()}", flush=True)
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=build_overlay_overrides(),
                analysis_start=analysis_start,
                analysis_end=END_DT,
                capital=CAPITAL,
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
    daily_risk = _calculate_daily_risk(daily_df, CAPITAL)
    daily_margin, _ = _calculate_margin_path(positions, daily_risk, capital=CAPITAL)
    return daily_df, daily_margin, statistics


def _aggregate_horizons(horizon_df: pd.DataFrame) -> pd.DataFrame:
    complete = horizon_df[horizon_df["complete_horizon"].astype(bool)].copy()
    if complete.empty:
        return pd.DataFrame()
    aggregate = (
        complete.groupby(["profile_name", "horizon"], as_index=False)
        .agg(
            window_count=("window_name", "count"),
            positive_return_count=("total_return_pct", lambda s: int((s > 0).sum())),
            non_positive_return_count=("total_return_pct", lambda s: int((s <= 0).sum())),
            median_return_pct=("total_return_pct", "median"),
            worst_return_pct=("total_return_pct", "min"),
            best_return_pct=("total_return_pct", "max"),
            median_max_dd_percent=("max_dd_percent", "median"),
            worst_max_dd_percent=("max_dd_percent", "min"),
            median_sharpe=("sharpe_ratio", "median"),
            worst_sharpe=("sharpe_ratio", "min"),
            max_margin_to_balance_pct=("max_margin_to_balance_pct", "max"),
            windows_margin_gt_80pct=("margin_days_gt_80pct", lambda s: int((s > 0).sum())),
            windows_margin_gt_100pct=("margin_days_gt_100pct", lambda s: int((s > 0).sum())),
            median_trade_count=("total_trade_count", "median"),
            median_slippage=("total_slippage", "median"),
        )
        .sort_values(["horizon", "profile_name"])
        .reset_index(drop=True)
    )
    aggregate["positive_return_rate_pct"] = (
        aggregate["positive_return_count"] / aggregate["window_count"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    return aggregate


def _load_stage78_400k_reference() -> tuple[dict[str, Any], pd.DataFrame]:
    full = {
        "profile_name": "stage78_400k_cap_2_5x_reference",
        "version": OFFICIAL_STAGE78_VERSION,
        "capital": CAPITAL,
        "end_balance": 5_712_450.0,
        "total_return_pct": 1328.1125,
        "max_dd_percent": -38.8476862519,
        "sharpe_ratio": 1.4530869081,
        "total_slippage": 295_970.0,
        "total_trade_count": 820.0,
        "win_ratio_pct": 0.0,
        "max_margin_to_balance_pct": 0.0,
    }
    if not STAGE78_400K_BASELINE_HORIZON_AGGREGATE_PATH.exists():
        return full, pd.DataFrame()
    baseline = pd.read_csv(STAGE78_400K_BASELINE_HORIZON_AGGREGATE_PATH)
    baseline = baseline[baseline["profile_name"].astype(str) == "capital_40w_cap_2_5x"].copy()
    baseline["profile_name"] = "stage78_400k_cap_2_5x_reference"
    return full, baseline


def _stage111_reference() -> tuple[dict[str, Any], pd.DataFrame]:
    full_metrics = STAGE111_REFERENCE_METRICS["full_2020_2026_400k"]
    full = {
        "profile_name": "stage111_400k_margin_safe_reference",
        "version": STAGE111_VERSION,
        "capital": CAPITAL,
        "end_balance": full_metrics["end_balance"],
        "total_return_pct": full_metrics["total_return_pct"],
        "max_dd_percent": full_metrics["max_dd_percent"],
        "sharpe_ratio": full_metrics["sharpe_ratio"],
        "total_slippage": full_metrics["total_slippage"],
        "total_trade_count": full_metrics["total_trade_count"],
        "win_ratio_pct": 0.0,
        "max_margin_to_balance_pct": full_metrics["max_total_margin_to_balance_pct"],
    }
    rows = []
    for horizon, metrics in STAGE111_QUARTERLY_VALIDATION.items():
        rows.append(
            {
                "profile_name": "stage111_400k_margin_safe_reference",
                "horizon": horizon,
                "window_count": metrics["window_count"],
                "positive_return_count": int(round(metrics["window_count"] * metrics["positive_return_rate_pct"] / 100.0)),
                "positive_return_rate_pct": metrics["positive_return_rate_pct"],
                "median_return_pct": metrics["median_return_pct"],
                "worst_return_pct": metrics["worst_return_pct"],
                "worst_max_dd_percent": metrics["worst_max_dd_percent"],
                "max_margin_to_balance_pct": metrics["max_margin_to_balance_pct"],
                "windows_margin_gt_80pct": metrics["windows_margin_gt_80pct"],
                "windows_margin_gt_100pct": metrics["windows_margin_gt_100pct"],
            }
        )
    return full, pd.DataFrame(rows)


def _build_full_comparison(overlay_full: dict[str, Any]) -> pd.DataFrame:
    stage78_full, _ = _load_stage78_400k_reference()
    stage111_full, _ = _stage111_reference()
    return pd.DataFrame([stage78_full, stage111_full, overlay_full])


def _build_horizon_comparison(overlay_aggregate: pd.DataFrame) -> pd.DataFrame:
    _, stage78_horizon = _load_stage78_400k_reference()
    _, stage111_horizon = _stage111_reference()
    frames = [df for df in (stage78_horizon, stage111_horizon, overlay_aggregate) if not df.empty]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _build_report(full_comparison: pd.DataFrame, horizon_comparison: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage78 400k + Stage111 Margin Overlay",
            "",
            "## Boundary",
            "",
            "- Stage78 product universe, AI filter and correlation gate are kept.",
            "- Only Stage111 margin constraints are overlaid.",
            f"- Capital: `{CAPITAL:,.0f}`",
            f"- Sizing equity cap: `{SIZING_EQUITY_CAP:,.0f}`",
            f"- max_capital_usage_ratio: `{STAGE111_MARGIN_PROFILE['max_capital_usage_ratio']}`",
            f"- max_single_trade_capital_usage_ratio: `{STAGE111_MARGIN_PROFILE['max_single_trade_capital_usage_ratio']}`",
            "",
            "## Full Comparison",
            "",
            _to_markdown_table(
                full_comparison,
                [
                    "profile_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                    "win_ratio_pct",
                    "max_margin_to_balance_pct",
                ],
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
                    "max_margin_to_balance_pct",
                    "windows_margin_gt_80pct",
                    "windows_margin_gt_100pct",
                ],
                max_rows=60,
            ),
            "",
            "## Judgement",
            "",
            "- A useful overlay must reduce Stage78 drawdown/margin risk without collapsing the return engine.",
            "- If it merely becomes a lower-return Stage111 clone, it is not a breakthrough.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    quarter_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    full_row: dict[str, Any] | None = None

    for analysis_start in quarter_starts():
        daily, daily_margin, statistics = _run_window(analysis_start)
        window_name = _window_name(analysis_start)
        base_fields = {
            "model_tag": MODEL_TAG,
            "profile_name": "stage78_400k_stage111_margin_overlay",
            "base_version": OFFICIAL_STAGE78_VERSION,
            "overlay_version": STAGE111_VERSION,
            "capital": CAPITAL,
            "sizing_equity_cap": SIZING_EQUITY_CAP,
            "base_risk_ratio": BASE_RISK_RATIO,
            "max_capital_usage_ratio": STAGE111_MARGIN_PROFILE["max_capital_usage_ratio"],
            "max_single_trade_capital_usage_ratio": STAGE111_MARGIN_PROFILE["max_single_trade_capital_usage_ratio"],
            "window_name": window_name,
            "analysis_start": analysis_start.date().isoformat(),
            "analysis_end": END_DT.date().isoformat(),
        }

        quarter_row = {**base_fields, "horizon": "to_end", **_summarize_slice(daily, daily_margin)}
        quarter_rows.append(quarter_row)
        if analysis_start == START_DT:
            full_row = {
                "profile_name": "stage78_400k_stage111_margin_overlay",
                "version": MODEL_TAG,
                "capital": CAPITAL,
                "end_balance": float(statistics.get("end_balance", 0.0) or 0.0),
                "total_return_pct": float(statistics.get("total_return", 0.0) or 0.0),
                "max_dd_percent": float(statistics.get("max_ddpercent", 0.0) or 0.0),
                "sharpe_ratio": float(statistics.get("sharpe_ratio", 0.0) or 0.0),
                "total_slippage": float(statistics.get("total_slippage", 0.0) or 0.0),
                "total_trade_count": float(statistics.get("total_trade_count", 0.0) or 0.0),
                "win_ratio_pct": float(statistics.get("win_ratio", 0.0) or 0.0),
                "max_margin_to_balance_pct": quarter_row["max_margin_to_balance_pct"],
            }

        for horizon_days in HORIZON_DAYS:
            daily_slice = daily.iloc[:horizon_days].copy()
            margin_slice = _slice_margin(daily_slice, daily_margin)
            horizon_rows.append(
                {
                    **base_fields,
                    "horizon": f"{horizon_days}d",
                    "horizon_days": horizon_days,
                    "complete_horizon": int(len(daily_slice) >= horizon_days),
                    **_summarize_slice(daily_slice, margin_slice),
                }
            )

    if full_row is None:
        raise RuntimeError("missing full window row")

    quarter_summary = pd.DataFrame(quarter_rows)
    horizon_summary = pd.DataFrame(horizon_rows)
    horizon_aggregate = _aggregate_horizons(horizon_summary)
    full_comparison = _build_full_comparison(full_row)
    horizon_comparison = _build_horizon_comparison(horizon_aggregate)

    quarter_summary.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_summary.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_aggregate.to_csv(HORIZON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    full_comparison.to_csv(FULL_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    horizon_comparison.to_csv(HORIZON_COMPARISON_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "capital": CAPITAL,
        "sizing_equity_cap": SIZING_EQUITY_CAP,
        "overlay": STAGE111_MARGIN_PROFILE,
        "full_comparison": full_comparison.to_dict(orient="records"),
        "horizon_comparison": horizon_comparison.to_dict(orient="records"),
        "output_paths": {
            "quarter_summary": str(QUARTER_SUMMARY_PATH),
            "horizon_summary": str(HORIZON_SUMMARY_PATH),
            "horizon_aggregate": str(HORIZON_AGGREGATE_PATH),
            "full_comparison": str(FULL_COMPARISON_PATH),
            "horizon_comparison": str(HORIZON_COMPARISON_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(full_comparison, horizon_comparison), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[stage78-111-overlay] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

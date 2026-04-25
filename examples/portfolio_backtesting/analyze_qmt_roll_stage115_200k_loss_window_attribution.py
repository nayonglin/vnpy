from __future__ import annotations

import json
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_stage115_200k_granularity_safe_config import (
    STAGE115_CAPITAL,
    STAGE115_PROFILE_NAME,
    STAGE115_SINGLE_CONTRACT_MARGIN_LIMIT_PCT,
    STAGE115_VERSION,
    build_stage115_overrides,
)
from qmt_universe import END_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage116_stage115_200k_loss_window_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage115_200k_loss_window_attribution"
STAGE114_HORIZON_SUMMARY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage111_200k_granularity_quarterly_walkforward_horizon_summary_"
    "stage114_stage111_200k_granularity_quarterly_wf_v1.csv"
)
WEAK_WINDOW_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_weak_windows_{MODEL_TAG}.csv"
PRODUCT_ATTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_attribution_{MODEL_TAG}.csv"
TOP_LOSS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_loss_products_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _product_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", maxsplit=1)
    product = re.sub(r"\d+$", "", symbol)
    return f"{product}.{exchange}"


def _read_weak_horizon_rows() -> pd.DataFrame:
    if not STAGE114_HORIZON_SUMMARY_PATH.exists():
        raise FileNotFoundError(STAGE114_HORIZON_SUMMARY_PATH)
    df = pd.read_csv(STAGE114_HORIZON_SUMMARY_PATH)
    df["complete_horizon"] = pd.to_numeric(df["complete_horizon"], errors="coerce").fillna(0).astype(int)
    df["total_return_pct"] = pd.to_numeric(df["total_return_pct"], errors="coerce").fillna(0.0)
    weak = df[(df["complete_horizon"] == 1) & (df["total_return_pct"] <= 0.0)].copy()
    weak["horizon_days"] = pd.to_numeric(weak["horizon_days"], errors="coerce").fillna(0).astype(int)
    weak["analysis_start_dt"] = pd.to_datetime(weak["analysis_start"])
    weak.sort_values(["analysis_start_dt", "horizon_days"], inplace=True)
    weak.reset_index(drop=True, inplace=True)
    return weak


def _calendar_end_for_horizon(analysis_start: pd.Timestamp, max_horizon_days: int) -> datetime:
    calendar_days = int(max_horizon_days * 2 + 45)
    analysis_end = analysis_start.to_pydatetime() + timedelta(days=calendar_days)
    return min(analysis_end, END_DT)


def _run_window(analysis_start: pd.Timestamp, max_horizon_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    analysis_end = _calendar_end_for_horizon(analysis_start, max_horizon_days)
    print(
        f"[stage115-loss-attribution] {analysis_start.date()} max_horizon={max_horizon_days}d "
        f"end={analysis_end.date()}",
        flush=True,
    )
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, _ = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=build_stage115_overrides(),
                analysis_start=analysis_start.to_pydatetime(),
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
    return daily_df, positions


def _slice_positions(positions: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    if positions.empty:
        return positions.copy()
    pos = positions.copy()
    pos["date"] = pd.to_datetime(pos["date"]).dt.normalize()
    pos = pos[(pos["date"] >= start_date.normalize()) & (pos["date"] <= end_date.normalize())].copy()
    if pos.empty:
        return pos
    pos["product_vt_symbol"] = pos["vt_symbol"].map(_product_symbol)
    return pos


def _classify_weak_row(row: pd.Series) -> str:
    trades = float(row.get("total_trade_count", 0.0) or 0.0)
    total_return = float(row.get("total_return_pct", 0.0) or 0.0)
    max_dd = float(row.get("max_dd_percent", 0.0) or 0.0)
    if trades <= 0 and abs(total_return) < 1e-9:
        return "no_signal_idle"
    if trades <= 4 and total_return > -1.5:
        return "thin_signal_friction"
    if total_return <= -3.0 or max_dd <= -10.0:
        return "real_loss_window"
    return "mild_chop_window"


def _summarize_product_attribution(
    weak_row: pd.Series,
    daily: pd.DataFrame,
    positions: pd.DataFrame,
) -> list[dict[str, Any]]:
    horizon_days = int(weak_row["horizon_days"])
    daily_slice = daily.iloc[:horizon_days].copy()
    if daily_slice.empty:
        return []
    start_date = pd.to_datetime(daily_slice.index[0]).normalize()
    end_date = pd.to_datetime(daily_slice.index[-1]).normalize()
    pos = _slice_positions(positions, start_date, end_date)
    if pos.empty:
        return []

    numeric_cols = ["net_pnl", "holding_pnl", "trading_pnl", "slippage", "turnover", "trade_count"]
    for col in numeric_cols:
        pos[col] = pd.to_numeric(pos.get(col, 0.0), errors="coerce").fillna(0.0)
    pos["is_active"] = (
        (pd.to_numeric(pos.get("start_pos", 0.0), errors="coerce").fillna(0.0).abs() > 0)
        | (pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0).abs() > 0)
        | (pos["trade_count"] > 0)
    )
    pos["long_day"] = pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0) > 0
    pos["short_day"] = pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0) < 0

    daily_net = pd.to_numeric(daily_slice.get("net_pnl", pd.Series(0.0, index=daily_slice.index)), errors="coerce").fillna(0.0)
    total_window_net = float(daily_net.sum())
    worst_day = pd.to_datetime(daily_net.idxmin()).normalize() if not daily_net.empty else end_date
    worst_day_pos = pos[pos["date"] == worst_day].copy()
    worst_day_by_product = (
        worst_day_pos.groupby("product_vt_symbol")["net_pnl"].sum().sort_values().to_dict()
        if not worst_day_pos.empty
        else {}
    )

    grouped = (
        pos.groupby("product_vt_symbol", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            turnover=("turnover", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("is_active", "sum"),
            long_days=("long_day", "sum"),
            short_days=("short_day", "sum"),
        )
        .sort_values("net_pnl")
        .reset_index(drop=True)
    )
    rows: list[dict[str, Any]] = []
    for rank, product_row in enumerate(grouped.itertuples(index=False), start=1):
        net_pnl = float(product_row.net_pnl)
        loss_share = net_pnl / total_window_net * 100.0 if total_window_net < -1e-9 and net_pnl < 0 else 0.0
        rows.append(
            {
                "model_tag": MODEL_TAG,
                "version": STAGE115_VERSION,
                "profile_name": STAGE115_PROFILE_NAME,
                "capital": STAGE115_CAPITAL,
                "single_contract_margin_limit_pct": STAGE115_SINGLE_CONTRACT_MARGIN_LIMIT_PCT,
                "window_name": weak_row["window_name"],
                "analysis_start": weak_row["analysis_start"],
                "horizon": weak_row["horizon"],
                "horizon_days": horizon_days,
                "horizon_end": end_date.date().isoformat(),
                "weak_class": _classify_weak_row(weak_row),
                "window_total_return_pct": float(weak_row["total_return_pct"]),
                "window_max_dd_percent": float(weak_row["max_dd_percent"]),
                "window_trade_count": float(weak_row["total_trade_count"]),
                "window_net_pnl": total_window_net,
                "worst_day": worst_day.date().isoformat(),
                "worst_day_net_pnl": float(daily_net.min()),
                "product_loss_rank": rank,
                "product_vt_symbol": product_row.product_vt_symbol,
                "net_pnl": net_pnl,
                "loss_share_of_window_loss_pct": loss_share,
                "holding_pnl": float(product_row.holding_pnl),
                "trading_pnl": float(product_row.trading_pnl),
                "slippage": float(product_row.slippage),
                "turnover": float(product_row.turnover),
                "trade_count": float(product_row.trade_count),
                "active_days": int(product_row.active_days),
                "long_days": int(product_row.long_days),
                "short_days": int(product_row.short_days),
                "worst_day_product_net_pnl": float(worst_day_by_product.get(product_row.product_vt_symbol, 0.0)),
            }
        )
    return rows


def _build_summary(weak: pd.DataFrame, product_attr: pd.DataFrame) -> dict[str, Any]:
    class_counts = weak["weak_class"].value_counts().to_dict()
    top_products = []
    if not product_attr.empty:
        losses = product_attr[product_attr["net_pnl"] < 0].copy()
        if not losses.empty:
            product_summary = (
                losses.groupby("product_vt_symbol", as_index=False)
                .agg(
                    weak_loss_count=("window_name", "count"),
                    aggregate_net_pnl=("net_pnl", "sum"),
                    aggregate_slippage=("slippage", "sum"),
                    aggregate_trade_count=("trade_count", "sum"),
                    aggregate_active_days=("active_days", "sum"),
                    max_single_window_loss=("net_pnl", "min"),
                )
                .sort_values("aggregate_net_pnl")
                .reset_index(drop=True)
            )
            top_products = product_summary.head(10).to_dict(orient="records")
    return {
        "model_tag": MODEL_TAG,
        "version": STAGE115_VERSION,
        "profile_name": STAGE115_PROFILE_NAME,
        "capital": STAGE115_CAPITAL,
        "weak_window_count": int(len(weak)),
        "weak_class_counts": class_counts,
        "top_loss_products": top_products,
        "output_paths": {
            "weak_windows": str(WEAK_WINDOW_PATH),
            "product_attribution": str(PRODUCT_ATTRIBUTION_PATH),
            "top_loss_products": str(TOP_LOSS_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, columns].head(max_rows).copy()
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def _build_report(weak: pd.DataFrame, top_loss: pd.DataFrame, summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Stage115 200k Loss Window Attribution",
            "",
            "## Scope",
            "",
            "- Only complete Stage114 horizon rows with non-positive return are rerun.",
            "- Stage115 trading rules are unchanged.",
            "- Attribution is by product-level daily net PnL inside each weak horizon.",
            "",
            "## Weak Window Classes",
            "",
            json.dumps(summary["weak_class_counts"], ensure_ascii=False, indent=2),
            "",
            "## Weak Windows",
            "",
            _to_markdown_table(
                weak,
                [
                    "window_name",
                    "horizon",
                    "total_return_pct",
                    "max_dd_percent",
                    "total_trade_count",
                    "weak_class",
                ],
                max_rows=50,
            ),
            "",
            "## Top Loss Products",
            "",
            _to_markdown_table(
                top_loss,
                [
                    "product_vt_symbol",
                    "weak_loss_count",
                    "aggregate_net_pnl",
                    "aggregate_slippage",
                    "aggregate_trade_count",
                    "max_single_window_loss",
                ],
                max_rows=20,
            ),
            "",
            "## Judgement",
            "",
            "- If losses are concentrated in one or two products across independent weak windows, product-level throttles may be justified.",
            "- If losses are mostly no-signal or low-trade friction windows, adding rules is likely overfitting and the correct response is accepting idle/chop periods.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    weak = _read_weak_horizon_rows()
    if weak.empty:
        raise RuntimeError("No weak windows found.")

    weak["weak_class"] = weak.apply(_classify_weak_row, axis=1)
    weak.to_csv(WEAK_WINDOW_PATH, index=False, encoding="utf-8-sig")

    product_rows: list[dict[str, Any]] = []
    grouped = weak.groupby("analysis_start_dt", sort=True)
    for analysis_start, group in grouped:
        max_horizon_days = int(group["horizon_days"].max())
        daily, positions = _run_window(analysis_start, max_horizon_days)
        for _, weak_row in group.iterrows():
            product_rows.extend(_summarize_product_attribution(weak_row, daily, positions))

    product_attr = pd.DataFrame(product_rows)
    product_attr.to_csv(PRODUCT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")

    if product_attr.empty:
        top_loss = pd.DataFrame()
    else:
        top_loss = (
            product_attr[product_attr["net_pnl"] < 0]
            .groupby("product_vt_symbol", as_index=False)
            .agg(
                weak_loss_count=("window_name", "count"),
                aggregate_net_pnl=("net_pnl", "sum"),
                aggregate_slippage=("slippage", "sum"),
                aggregate_trade_count=("trade_count", "sum"),
                aggregate_active_days=("active_days", "sum"),
                max_single_window_loss=("net_pnl", "min"),
            )
            .sort_values("aggregate_net_pnl")
            .reset_index(drop=True)
        )
    top_loss.to_csv(TOP_LOSS_PATH, index=False, encoding="utf-8-sig")

    summary = _build_summary(weak, product_attr)
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(weak, top_loss, summary), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[stage115-loss-attribution] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

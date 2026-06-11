from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage752_theoretical_winner_kline_atlas as s752
import analyze_qmt_roll_stage777_am41_oi08_monthly as s777
import analyze_qmt_roll_stage797_stage777_top_loss_kline_atlas as s797


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MINUTE_ROOT = PROJECT_DIR / "downloaded_futures"

MODEL_TAG = "stage798_stage777_top20_loss_kline_atlas_v1"
OUTPUT_PREFIX = "qmt_roll_stage798_stage777_top20_loss_kline_atlas"
LINE_ID = "futures_trend_2019_data_extension"

START = pd.Timestamp("2020-01-01")
TOP_N = 20
PER_PAGE = 4

CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
SOURCE_CLOSED_LOTS_CANDIDATES = (
    OUTPUT_DIR
    / "qmt_roll_stage797_stage777_top_loss_kline_atlas_closed_lots_stage797_stage777_top_loss_kline_atlas_v2.csv",
    OUTPUT_DIR
    / "qmt_roll_stage797_stage777_top_loss_kline_atlas_closed_lots_stage797_stage777_top_loss_kline_atlas_v1.csv",
)
TOP_LOSSES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_losses_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_page{{page:02d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _load_closed_lots() -> pd.DataFrame:
    for path in SOURCE_CLOSED_LOTS_CANDIDATES:
        if path.exists():
            closed = pd.read_csv(path, encoding="utf-8-sig")
            for column in ["entry_date", "exit_date"]:
                closed[column] = pd.to_datetime(closed[column], errors="coerce").dt.normalize()
            closed.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
            return closed

    closed = s797._run_closed_lots()
    closed.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    return closed


def _roll_night_bar_to_trading_day(ts: pd.Timestamp) -> pd.Timestamp:
    day = ts.normalize()
    if ts.hour >= 21:
        day += pd.Timedelta(days=1)
    while day.weekday() >= 5:
        day += pd.Timedelta(days=1)
    return day


def _aggregate_minute_file(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty or "bar_datetime" not in frame.columns:
        return pd.DataFrame()
    frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["bar_datetime", "open", "high", "low", "close"]).sort_values("bar_datetime")
    if frame.empty:
        return pd.DataFrame()

    frame["date"] = frame["bar_datetime"].map(_roll_night_bar_to_trading_day)
    grouped = frame.groupby("date", sort=True)
    daily = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        open_oi=("open_oi", "first"),
        close_oi=("close_oi", "last"),
    )
    return daily.reset_index().dropna(subset=["date", "open", "high", "low", "close"]).reset_index(drop=True)


def _read_minute_fallback_bars(vt_symbol: Any) -> pd.DataFrame:
    text = str(vt_symbol or "")
    if "." not in text:
        return pd.DataFrame()
    contract_symbol, exchange = text.split(".", 1)
    names = {
        contract_symbol,
        contract_symbol.lower(),
        contract_symbol.upper(),
    }
    paths: list[Path] = []
    for name in names:
        paths.extend(MINUTE_ROOT.glob(f"*/{exchange}/{name}_completed_minute_backtest.csv"))
        paths.extend(MINUTE_ROOT.glob(f"*/{exchange}/{name}_minute_backtest.csv"))

    best = pd.DataFrame()
    for path in sorted(set(paths)):
        daily = _aggregate_minute_file(path)
        if len(daily) > len(best):
            best = daily
    return best


def _read_plot_bars(vt_symbol: Any) -> tuple[pd.DataFrame, str]:
    bars = s752._read_contract_bars(vt_symbol)
    if not bars.empty:
        return bars, "daily"
    fallback = _read_minute_fallback_bars(vt_symbol)
    if not fallback.empty:
        return fallback, "minute_aggregated"
    return pd.DataFrame(), "missing"


def _select_top_losses(closed: pd.DataFrame) -> pd.DataFrame:
    data = closed.copy()
    data["theory_return_pct"] = pd.to_numeric(data["theory_return_pct"], errors="coerce")
    data["theory_loss_pct"] = -data["theory_return_pct"]
    data["realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce")
    data["r_multiple"] = pd.to_numeric(data["r_multiple"], errors="coerce")
    data["risk_multiplier"] = pd.to_numeric(data.get("risk_multiplier"), errors="coerce")
    data["oi_price_confirm_risk_restore_applied"] = pd.to_numeric(
        data.get("oi_price_confirm_risk_restore_applied"),
        errors="coerce",
    )

    losers = data[data["theory_return_pct"].lt(0.0)].copy()
    losers = losers.dropna(
        subset=["entry_date", "exit_date", "entry_price", "exit_price", "theory_loss_pct"]
    )
    losers.sort_values(
        ["theory_loss_pct", "r_multiple", "realized_pnl"],
        ascending=[False, True, True],
        inplace=True,
    )
    top = losers.head(TOP_N).copy().reset_index(drop=True)
    top["loss_rank"] = np.arange(1, len(top) + 1)
    top["holding_bar_count"] = top.apply(s797._holding_bar_count, axis=1)
    return top


def _plot_page(page_rows: pd.DataFrame, page: int, total_pages: int) -> tuple[Path, list[dict[str, Any]]]:
    chart_records: list[dict[str, Any]] = []
    row_count = max(len(page_rows), 1)
    fig = plt.figure(figsize=(19, 4.9 * row_count), constrained_layout=True)
    outer = fig.add_gridspec(row_count, 1)

    for idx, (_, row) in enumerate(page_rows.iterrows()):
        inner = outer[idx].subgridspec(2, 1, height_ratios=[3.2, 1.0], hspace=0.02)
        price_ax = fig.add_subplot(inner[0])
        volume_ax = fig.add_subplot(inner[1], sharex=price_ax)
        bars, bar_source = _read_plot_bars(row["vt_symbol"])
        if bars.empty:
            price_ax.axis("off")
            volume_ax.axis("off")
            price_ax.text(
                0.5,
                0.5,
                (
                    f"missing bars\n#{int(row['loss_rank'])} lot{int(row['lot_id'])}\n"
                    f"{row['vt_symbol']} {row['direction']}\n"
                    f"{pd.Timestamp(row['entry_date']):%Y-%m-%d}->{pd.Timestamp(row['exit_date']):%Y-%m-%d}\n"
                    f"loss={float(row['theory_loss_pct']):.2f}%"
                ),
                ha="center",
                va="center",
                fontsize=11,
                color="#991b1b",
            )
            chart_records.append(
                {
                    "lot_id": int(row["lot_id"]),
                    "window_bars": 0,
                    "pre_bars_available": 0,
                    "post_bars_available": 0,
                    "chart_start": "",
                    "chart_end": "",
                    "missing_bars": 1,
                    "bar_source": bar_source,
                    "chart_page": page,
                }
            )
            continue

        chart_record = s797._plot_one(price_ax, volume_ax, row, bars)
        chart_record["missing_bars"] = 0
        chart_record["bar_source"] = bar_source
        chart_record["chart_page"] = page
        chart_records.append(chart_record)

    fig.suptitle(
        (
            "Stage798 official candidate Stage777 top 20 theoretical loss trades "
            f"(page {page}/{total_pages}, sorted by loss pct, MA5/10/20/40, pre50/post50)"
        ),
        fontsize=15,
    )
    chart_path = Path(str(CHART_PATH_TEMPLATE).format(page=page))
    fig.savefig(chart_path, dpi=170)
    plt.close(fig)
    return chart_path, chart_records


def _plot_pages(top: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    total_pages = int(math.ceil(len(top) / PER_PAGE)) if len(top) else 1
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        page_rows = top.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        chart_path, chart_records = _plot_page(page_rows, page, total_pages)
        paths.append(chart_path)
        records.extend(chart_records)
    return paths, pd.DataFrame(records)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    closed = _load_closed_lots()
    top = _select_top_losses(closed)
    chart_paths, chart_records = _plot_pages(top)

    top_with_chart = top.merge(chart_records, on="lot_id", how="left")
    top_with_chart.to_csv(TOP_LOSSES_PATH, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "source_version": "official_candidate_stage777_50w_am41_oi08_old_ai_v1",
                "start": START.date().isoformat(),
                "analysis_end": pd.Timestamp(s777.ANALYSIS_END).date().isoformat(),
                "closed_lot_count": int(len(closed)),
                "loser_lot_count": int(pd.to_numeric(closed["theory_return_pct"], errors="coerce").lt(0.0).sum()),
                "top_n": int(len(top)),
                "ma_lines": "5,10,20,40",
                "worst_theory_loss_pct": float(top["theory_loss_pct"].max()) if not top.empty else np.nan,
                "rank20_theory_loss_pct": float(top["theory_loss_pct"].iloc[-1]) if not top.empty else np.nan,
                "worst_r_multiple": float(top["r_multiple"].min()) if not top.empty else np.nan,
                "oi_hit_count_in_top": int(
                    pd.to_numeric(top["oi_price_confirm_risk_restore_applied"], errors="coerce")
                    .fillna(0)
                    .eq(1)
                    .sum()
                )
                if not top.empty
                else 0,
                "missing_bar_lots": int(chart_records["missing_bars"].sum()) if not chart_records.empty else 0,
                "minute_aggregated_lots": int(chart_records["bar_source"].eq("minute_aggregated").sum())
                if not chart_records.empty and "bar_source" in chart_records
                else 0,
                "closed_lots_path": str(CLOSED_LOTS_PATH),
                "top_losses_path": str(TOP_LOSSES_PATH),
                "chart_paths": " | ".join(str(path) for path in chart_paths),
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": "Stage798",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "task": "official candidate Stage777 top 20 theoretical loss K-line atlas",
        "strategy_changed": False,
        "backtest_changed": False,
        "source_version": "official_candidate_stage777_50w_am41_oi08_old_ai_v1",
        "ranking_metric": "theory_loss_pct = -directional(entry->exit return pct)",
        "overfit_reflection": (
            "Low for chart generation because no parameter or rule is changed. It can become overfit only if we "
            "derive a threshold from these 20 trades without forward or multi-start validation."
        ),
        "continue_value": (
            "Yes. Expanding from 5 to 20 loss charts helps inspect whether losing trades share a repeated market "
            "microstructure rather than being isolated accidents."
        ),
        "outputs": {
            "closed_lots": str(CLOSED_LOTS_PATH),
            "top_losses": str(TOP_LOSSES_PATH),
            "summary": str(SUMMARY_PATH),
            "charts": [str(path) for path in chart_paths],
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    display_cols = [
        "loss_rank",
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "theory_loss_pct",
        "realized_pnl",
        "r_multiple",
        "risk_multiplier",
        "oi_price_confirm_risk_restore_applied",
        "signal",
        "exit_reason",
        "chart_page",
    ]
    print(summary.to_string(index=False))
    print(top_with_chart[[column for column in display_cols if column in top_with_chart.columns]].to_string(index=False))
    for path in chart_paths:
        print(f"chart={path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage752_theoretical_winner_kline_atlas as s752


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_2019_data_extension"

SOURCE_PREFIX = "qmt_roll_stage779_stage777_2022_loss_streak_review"
SOURCE_TAG = "stage779_stage777_2022_loss_streak_review_v1"
SOURCE_SEQUENCE = OUTPUT_DIR / f"{SOURCE_PREFIX}_worst_sequence_{SOURCE_TAG}.csv"

OUTPUT_PREFIX = "qmt_roll_stage780_stage777_failed_kline_atlas"
MODEL_TAG = "stage780_stage777_failed_kline_atlas_v1"
MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"

PRE_BARS = 50
POST_BARS = 50
PER_PAGE = 4


def _safe_float(row: pd.Series, column: str) -> float:
    try:
        return float(row.get(column, np.nan))
    except (TypeError, ValueError):
        return math.nan


def _format_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "nan"
    return f"{number:,.0f}"


def _load_failed_lots() -> pd.DataFrame:
    lots = pd.read_csv(SOURCE_SEQUENCE, encoding="utf-8-sig")
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    for column in [
        "seq",
        "lot_id",
        "entry_price",
        "exit_price",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "theory_return_pct",
        "risk_multiplier",
        "loss_streak",
        "loss_streak_after_close",
        "oi_price_confirm_risk_restore_applied",
        "oi_price_confirm_entry_close",
        "oi_price_confirm_prev_close",
        "oi_price_confirm_entry_oi",
        "oi_price_confirm_prev_oi",
    ]:
        if column in lots.columns:
            lots[column] = pd.to_numeric(lots[column], errors="coerce")

    lots = lots[lots["realized_pnl"].lt(0.0)].copy()
    lots = lots.dropna(subset=["entry_date", "exit_date", "entry_price", "exit_price"])
    lots.sort_values(["seq", "exit_date", "entry_date", "vt_symbol", "lot_id"], inplace=True)
    lots.reset_index(drop=True, inplace=True)
    lots["failed_rank"] = np.arange(1, len(lots) + 1)

    holding_counts: list[int] = []
    for row in lots.itertuples(index=False):
        bars = s752._read_contract_bars(row.vt_symbol)
        if bars.empty:
            holding_counts.append(0)
            continue
        entry_idx = s752._event_index(bars, row.entry_date)
        exit_idx = s752._event_index(bars, row.exit_date)
        holding_counts.append(max(0, exit_idx - entry_idx + 1))
    lots["holding_bar_count"] = holding_counts
    return lots


def _plot_one(price_ax: plt.Axes, volume_ax: plt.Axes, row: pd.Series, bars: pd.DataFrame) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    entry_idx = s752._event_index(bars, entry_date)
    exit_idx = s752._event_index(bars, exit_date)
    start = max(0, entry_idx - PRE_BARS)
    end = min(len(bars), exit_idx + POST_BARS + 1)
    window = bars.iloc[start:end].copy().reset_index(drop=True)
    local_entry_idx = entry_idx - start
    local_exit_idx = exit_idx - start

    s752._plot_candles(price_ax, window)
    for ma, color in [(5, "#f59e0b"), (10, "#2563eb"), (20, "#7c3aed")]:
        price_ax.plot(window["close"].rolling(ma).mean().to_numpy(), color=color, linewidth=0.9, alpha=0.82)

    price_ax.axvspan(local_entry_idx, local_exit_idx, color="#fee2e2", alpha=0.30)
    price_ax.axvline(local_entry_idx, color="#1d4ed8", linewidth=1.25, alpha=0.95)
    price_ax.axvline(local_exit_idx, color="#9333ea", linewidth=1.25, alpha=0.95)
    price_ax.scatter([local_entry_idx], [float(row["entry_price"])], marker="^", s=38, color="#1d4ed8", zorder=5)
    price_ax.scatter([local_exit_idx], [float(row["exit_price"])], marker="v", s=38, color="#9333ea", zorder=5)

    tick_positions = np.linspace(0, max(0, len(window) - 1), num=min(7, len(window)), dtype=int)
    tick_labels = [pd.Timestamp(window.loc[pos, "date"]).strftime("%Y-%m-%d") for pos in tick_positions]
    price_ax.set_xticks(tick_positions)
    price_ax.set_xticklabels([])
    price_ax.grid(True, alpha=0.18, linewidth=0.6)
    price_ax.tick_params(axis="y", labelsize=8)
    price_ax.tick_params(axis="x", length=0)

    s752._plot_volume_oi(volume_ax, window)
    volume_ax.set_xticks(tick_positions)
    volume_ax.set_xticklabels(tick_labels, rotation=35, ha="right", fontsize=7)
    volume_ax.tick_params(axis="x", labelsize=7)

    pnl = _safe_float(row, "realized_pnl")
    r_multiple = _safe_float(row, "r_multiple")
    ret = _safe_float(row, "theory_return_pct")
    risk_multiplier = _safe_float(row, "risk_multiplier")
    loss_streak = _safe_float(row, "loss_streak")
    after_close_streak = _safe_float(row, "loss_streak_after_close")
    oi_applied = int(_safe_float(row, "oi_price_confirm_risk_restore_applied") == 1.0)
    oi0 = _safe_float(row, "oi_price_confirm_entry_oi")
    oi1 = _safe_float(row, "oi_price_confirm_prev_oi")
    close0 = _safe_float(row, "oi_price_confirm_entry_close")
    close1 = _safe_float(row, "oi_price_confirm_prev_close")

    title = (
        f"seq{int(row['seq'])} #{int(row['failed_rank'])} lot{int(row['lot_id'])} {row['vt_symbol']} "
        f"{row['direction']} ret={ret:.2f}% R={r_multiple:.2f} pnl={_format_money(pnl)} "
        f"bars={int(row['holding_bar_count'])}"
    )
    subtitle = (
        f"{entry_date:%Y-%m-%d}->{exit_date:%Y-%m-%d} "
        f"{row.get('signal', '')} exit={row.get('exit_reason', '')} "
        f"risk={risk_multiplier:.2f} entry_loss={loss_streak:.0f} close_loss={after_close_streak:.0f} "
        f"OIhit={oi_applied} OI {oi1:.0f}->{oi0:.0f} close {close1:.2f}->{close0:.2f}"
    )
    price_ax.set_title(title + "\n" + subtitle, fontsize=8.5, loc="left")
    price_ax.text(
        0.01,
        0.02,
        "blue=entry purple=exit red=holding loss | lower: volume bars + OI line | pre50/post50",
        transform=price_ax.transAxes,
        fontsize=7,
        color="#475569",
    )
    return {
        "lot_id": int(row["lot_id"]),
        "window_bars": int(len(window)),
        "pre_bars_available": int(local_entry_idx),
        "post_bars_available": int(len(window) - local_exit_idx - 1),
        "chart_start": pd.Timestamp(window["date"].iloc[0]).strftime("%Y-%m-%d"),
        "chart_end": pd.Timestamp(window["date"].iloc[-1]).strftime("%Y-%m-%d"),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = _load_failed_lots()
    chart_records: list[dict[str, Any]] = []
    page_count = int(math.ceil(len(lots) / PER_PAGE))
    chart_paths: list[Path] = []

    for page_idx in range(page_count):
        part = lots.iloc[page_idx * PER_PAGE : (page_idx + 1) * PER_PAGE]
        fig = plt.figure(figsize=(19, 15.5), constrained_layout=True)
        outer = fig.add_gridspec(2, 2)
        for ax_idx in range(PER_PAGE):
            cell = outer[ax_idx // 2, ax_idx % 2]
            inner = cell.subgridspec(2, 1, height_ratios=[3.2, 1.0], hspace=0.02)
            price_ax = fig.add_subplot(inner[0])
            volume_ax = fig.add_subplot(inner[1], sharex=price_ax)
            if ax_idx >= len(part):
                price_ax.axis("off")
                volume_ax.axis("off")
                continue
            row = part.iloc[ax_idx]
            bars = s752._read_contract_bars(row["vt_symbol"])
            if bars.empty:
                price_ax.axis("off")
                volume_ax.axis("off")
                price_ax.text(
                    0.5,
                    0.5,
                    (
                        f"missing bars\nseq{int(row['seq'])} lot{int(row['lot_id'])}\n"
                        f"{row['vt_symbol']} {row['direction']}\n"
                        f"{pd.Timestamp(row['entry_date']):%Y-%m-%d}->{pd.Timestamp(row['exit_date']):%Y-%m-%d}\n"
                        f"pnl={_format_money(row.get('realized_pnl'))}"
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
                        "page": page_idx + 1,
                        "missing_bars": 1,
                    }
                )
                continue
            chart_record = _plot_one(price_ax, volume_ax, row, bars)
            chart_record["page"] = page_idx + 1
            chart_record["missing_bars"] = 0
            chart_records.append(chart_record)
        fig.suptitle(
            (
                "Stage780 Stage777 2022 failed trades K-line atlas "
                f"(Stage779 focus losses, sorted by close sequence, pre{PRE_BARS}/post{POST_BARS}) "
                f"page {page_idx + 1}/{page_count}"
            ),
            fontsize=15,
        )
        path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_page{page_idx + 1:02d}_{MODEL_TAG}.png"
        fig.savefig(path, dpi=170)
        plt.close(fig)
        chart_paths.append(path)

    chart_frame = pd.DataFrame(chart_records)
    manifest = lots.merge(chart_frame, on="lot_id", how="left")
    manifest["chart_page"] = manifest["page"].astype("Int64")
    manifest.to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "source_sequence": str(SOURCE_SEQUENCE),
                "selected_failed_lot_count": int(len(lots)),
                "total_realized_pnl": float(lots["realized_pnl"].sum()),
                "oi_applied_count": int(lots["oi_price_confirm_risk_restore_applied"].fillna(0.0).eq(1.0).sum()),
                "page_count": int(page_count),
                "pre_bars": PRE_BARS,
                "post_bars": POST_BARS,
                "missing_bar_lots": int(chart_frame["missing_bars"].sum()) if not chart_frame.empty else 0,
                "manifest_path": str(MANIFEST_PATH),
                "chart_paths": "|".join(str(path) for path in chart_paths),
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False))
    print(
        manifest[
            [
                "seq",
                "failed_rank",
                "lot_id",
                "vt_symbol",
                "direction",
                "entry_date",
                "exit_date",
                "theory_return_pct",
                "realized_pnl",
                "r_multiple",
                "oi_price_confirm_risk_restore_applied",
                "loss_streak_after_close",
                "chart_page",
                "missing_bars",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()

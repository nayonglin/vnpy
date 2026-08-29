from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
CONTRACT_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_PREFIX = "qmt_roll_stage719_official_winner_trade_forensics"
SOURCE_TAG = "stage719_official_winner_trade_forensics_v1"
SOURCE_CLOSED_LOTS = OUTPUT_DIR / f"{SOURCE_PREFIX}_closed_lots_{SOURCE_TAG}.csv"

OUTPUT_PREFIX = "qmt_roll_stage752_theoretical_winner_kline_atlas"
MODEL_TAG = "stage752_theoretical_winner_kline_atlas_v1"
MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"

PRE_BARS = 40
POST_BARS = 40
BIG_WINNER_POSITIVE_QUANTILE = 0.80
PER_PAGE = 4


def _infer_product(vt_symbol: Any) -> str:
    text = str(vt_symbol or "").split(".", 1)[0]
    product = ""
    for char in text:
        if char.isalpha():
            product += char
        else:
            break
    return product


def _read_contract_bars(vt_symbol: Any) -> pd.DataFrame:
    text = str(vt_symbol or "")
    if "." not in text:
        return pd.DataFrame()
    contract_symbol, exchange = text.split(".", 1)
    exchange_dir = CONTRACT_ROOT / exchange
    path = exchange_dir / f"{contract_symbol}.csv"
    if not path.exists():
        lower_path = exchange_dir / f"{contract_symbol.lower()}.csv"
        upper_path = exchange_dir / f"{contract_symbol.upper()}.csv"
        if lower_path.exists():
            path = lower_path
        elif upper_path.exists():
            path = upper_path
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return pd.DataFrame()
    if "trade_date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    else:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame.rename(
        columns={
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "volume": "volume",
            "open_interest": "close_oi",
            "oi": "close_oi",
        },
        inplace=True,
    )
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame.dropna(subset=["date", "open", "high", "low", "close"])
        .drop_duplicates("date")
        .sort_values("date")
        .reset_index(drop=True)
    )


def _event_index(bars: pd.DataFrame, event_date: pd.Timestamp) -> int:
    dates = pd.to_datetime(bars["date"]).to_numpy(dtype="datetime64[ns]")
    target = np.datetime64(pd.Timestamp(event_date).normalize())
    exact = np.where(dates == target)[0]
    if len(exact):
        return int(exact[0])
    pos = int(np.searchsorted(dates, target))
    if pos >= len(bars):
        return len(bars) - 1
    if pos <= 0:
        return 0
    prev_delta = abs(dates[pos - 1] - target)
    next_delta = abs(dates[pos] - target)
    return pos - 1 if prev_delta <= next_delta else pos


def _plot_candles(ax: plt.Axes, bars: pd.DataFrame) -> None:
    width = 0.62
    up_color = "#dc2626"
    down_color = "#059669"
    for idx, row in enumerate(bars.itertuples(index=False)):
        open_price = float(row.open)
        high_price = float(row.high)
        low_price = float(row.low)
        close_price = float(row.close)
        color = up_color if close_price >= open_price else down_color
        ax.vlines(idx, low_price, high_price, color=color, linewidth=0.75, alpha=0.95)
        lower = min(open_price, close_price)
        height = abs(close_price - open_price)
        if height <= 0:
            height = max(high_price - low_price, 1.0) * 0.006
            lower -= height / 2.0
        ax.add_patch(
            Rectangle(
                (idx - width / 2.0, lower),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.45,
                alpha=0.82,
            )
        )


def _plot_volume_oi(ax: plt.Axes, window: pd.DataFrame) -> None:
    x_values = np.arange(len(window))
    has_volume = "volume" in window.columns and window["volume"].notna().any()
    has_oi = "close_oi" in window.columns and window["close_oi"].notna().any()
    if has_volume:
        ax.bar(
            x_values,
            pd.to_numeric(window["volume"], errors="coerce").fillna(0.0).to_numpy(),
            width=0.62,
            color="#94a3b8",
            alpha=0.62,
            label="Volume",
        )
    else:
        ax.text(0.01, 0.5, "volume missing", transform=ax.transAxes, fontsize=7, color="#64748b")
    ax.set_ylabel("Vol", fontsize=7, color="#64748b")
    ax.tick_params(axis="y", labelsize=7, colors="#64748b")
    ax.grid(True, axis="y", alpha=0.16, linewidth=0.5)

    if has_oi:
        oi_ax = ax.twinx()
        oi_ax.plot(
            x_values,
            pd.to_numeric(window["close_oi"], errors="coerce").to_numpy(),
            color="#0f766e",
            linewidth=0.95,
            alpha=0.92,
            label="Close OI",
        )
        oi_ax.set_ylabel("OI", fontsize=7, color="#0f766e")
        oi_ax.tick_params(axis="y", labelsize=7, colors="#0f766e")
    else:
        ax.text(0.99, 0.5, "OI missing", transform=ax.transAxes, fontsize=7, color="#64748b", ha="right")


def _plot_one(price_ax: plt.Axes, volume_ax: plt.Axes, row: pd.Series, bars: pd.DataFrame) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    entry_idx = _event_index(bars, entry_date)
    exit_idx = _event_index(bars, exit_date)
    start = max(0, entry_idx - PRE_BARS)
    end = min(len(bars), exit_idx + POST_BARS + 1)
    window = bars.iloc[start:end].copy().reset_index(drop=True)
    local_entry_idx = entry_idx - start
    local_exit_idx = exit_idx - start

    _plot_candles(price_ax, window)
    for ma, color in [(5, "#f59e0b"), (10, "#2563eb"), (20, "#7c3aed")]:
        price_ax.plot(window["close"].rolling(ma).mean().to_numpy(), color=color, linewidth=0.9, alpha=0.82)

    price_ax.axvspan(local_entry_idx, local_exit_idx, color="#fef3c7", alpha=0.22)
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

    _plot_volume_oi(volume_ax, window)
    volume_ax.set_xticks(tick_positions)
    volume_ax.set_xticklabels(tick_labels, rotation=35, ha="right", fontsize=7)
    volume_ax.tick_params(axis="x", labelsize=7)

    title = (
        f"#{int(row['theory_rank'])} lot{int(row['lot_id'])} {row['vt_symbol']} "
        f"{row['direction']} ret={float(row['theory_return_pct']):.2f}% "
        f"R={float(row['r_multiple']):.2f} bars={int(row['holding_bar_count'])}"
    )
    subtitle = (
        f"{entry_date:%Y-%m-%d}->{exit_date:%Y-%m-%d} "
        f"{row.get('signal', '')} risk={float(row.get('risk_multiplier', np.nan)):.2f} "
        f"loss={float(row.get('loss_streak', np.nan)):.0f}"
    )
    price_ax.set_title(title + "\n" + subtitle, fontsize=9, loc="left")
    price_ax.text(
        0.01,
        0.02,
        "blue=entry purple=exit yellow=holding | lower: volume bars + OI line",
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


def _load_winners() -> pd.DataFrame:
    lots = pd.read_csv(SOURCE_CLOSED_LOTS)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots["entry_price"] = pd.to_numeric(lots["entry_price"], errors="coerce")
    lots["exit_price"] = pd.to_numeric(lots["exit_price"], errors="coerce")
    direction_sign = np.where(lots["direction"].astype(str).eq("long"), 1.0, -1.0)
    lots["theory_return_pct"] = (
        direction_sign * (lots["exit_price"] - lots["entry_price"]) / lots["entry_price"] * 100.0
    )
    lots = lots.dropna(subset=["entry_date", "exit_date", "entry_price", "exit_price", "theory_return_pct"])
    positive = lots[lots["theory_return_pct"].gt(0.0)].copy()
    threshold = float(positive["theory_return_pct"].quantile(BIG_WINNER_POSITIVE_QUANTILE))
    winners = positive[positive["theory_return_pct"].ge(threshold)].copy()
    winners.sort_values("theory_return_pct", ascending=False, inplace=True)
    winners["theory_rank"] = range(1, len(winners) + 1)
    winners["theory_big_winner_threshold_pct"] = threshold
    winners["holding_bar_count"] = 0
    winners["product_raw"] = winners["vt_symbol"].map(_infer_product)

    holding_counts: list[int] = []
    for row in winners.itertuples(index=False):
        bars = _read_contract_bars(row.vt_symbol)
        if bars.empty:
            holding_counts.append(0)
            continue
        entry_idx = _event_index(bars, row.entry_date)
        exit_idx = _event_index(bars, row.exit_date)
        holding_counts.append(max(0, exit_idx - entry_idx + 1))
    winners["holding_bar_count"] = holding_counts
    return winners


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    winners = _load_winners()
    chart_records: list[dict[str, Any]] = []
    page_count = int(math.ceil(len(winners) / PER_PAGE))
    chart_paths: list[Path] = []

    for page_idx in range(page_count):
        part = winners.iloc[page_idx * PER_PAGE : (page_idx + 1) * PER_PAGE]
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
            bars = _read_contract_bars(row["vt_symbol"])
            if bars.empty:
                price_ax.axis("off")
                volume_ax.axis("off")
                price_ax.text(
                    0.5,
                    0.5,
                    (
                        f"missing bars\n#{int(row['theory_rank'])} lot{int(row['lot_id'])}\n"
                        f"{row['vt_symbol']} {row['direction']}\n"
                        f"{pd.Timestamp(row['entry_date']):%Y-%m-%d}->{pd.Timestamp(row['exit_date']):%Y-%m-%d}\n"
                        f"ret={float(row['theory_return_pct']):.2f}%"
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
                "Stage752 theoretical-return big winners K-line atlas "
                f"(top {100 * (1 - BIG_WINNER_POSITIVE_QUANTILE):.0f}% positive lots, "
                f"pre{PRE_BARS}/post{POST_BARS}) page {page_idx + 1}/{page_count}"
            ),
            fontsize=15,
        )
        path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_page{page_idx + 1:02d}_{MODEL_TAG}.png"
        fig.savefig(path, dpi=170)
        plt.close(fig)
        chart_paths.append(path)

    chart_frame = pd.DataFrame(chart_records)
    manifest = winners.merge(chart_frame, on="lot_id", how="left")
    manifest["chart_page"] = manifest["page"].astype("Int64")
    manifest.to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "source_closed_lots": str(SOURCE_CLOSED_LOTS),
                "positive_quantile": BIG_WINNER_POSITIVE_QUANTILE,
                "theory_return_threshold_pct": float(winners["theory_big_winner_threshold_pct"].iloc[0]),
                "selected_winner_count": int(len(winners)),
                "page_count": int(page_count),
                "pre_bars": PRE_BARS,
                "post_bars": POST_BARS,
                "manifest_path": str(MANIFEST_PATH),
                "chart_paths": "|".join(str(path) for path in chart_paths),
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False))
    print(manifest[["theory_rank", "lot_id", "vt_symbol", "direction", "entry_date", "exit_date", "theory_return_pct", "r_multiple", "signal", "chart_page"]].to_string(index=False))


if __name__ == "__main__":
    main()

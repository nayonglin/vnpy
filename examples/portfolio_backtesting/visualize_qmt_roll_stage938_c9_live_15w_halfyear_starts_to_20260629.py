from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import font_manager
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage938_c9_live_15w_halfyear_starts_to_20260629_v1"
OUTPUT_PREFIX = "qmt_roll_stage938_c9_live_15w_halfyear_starts_to_20260629"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
DASHBOARD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dashboard_{MODEL_TAG}.png"


def _configure_font() -> None:
    candidates = [
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for item in candidates:
        path = Path(item)
        if path.exists():
            font_manager.fontManager.addfont(str(path))
            prop = font_manager.FontProperties(fname=str(path))
            plt.rcParams["font.family"] = prop.get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False


def _pct(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.1f}%"


def _money(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:,.0f}"


def _start_color(index: int, total: int) -> tuple[float, float, float, float]:
    cmap = plt.get_cmap("turbo")
    if total <= 1:
        return cmap(0.5)
    return cmap(index / (total - 1))


def _annotate_bars(ax: plt.Axes, bars, values: pd.Series, *, threshold_abs: float = 0.0) -> None:
    for bar, value in zip(bars, values):
        if pd.isna(value):
            continue
        if abs(float(value)) < threshold_abs:
            continue
        height = float(bar.get_height())
        va = "bottom" if height >= 0 else "top"
        offset = 3 if height >= 0 else -3
        ax.annotate(
            _pct(float(value)),
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center",
            va=va,
            fontsize=7.8,
            color="#20242a",
            rotation=90,
        )


def main() -> None:
    _configure_font()
    summary = pd.read_csv(SUMMARY_PATH, encoding="utf-8-sig")
    stats = pd.read_csv(STATS_PATH, encoding="utf-8-sig")
    curves = pd.read_csv(CURVES_PATH, encoding="utf-8-sig")
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce")
    starts = summary["requested_start_month"].astype(str).tolist()
    stat = stats.iloc[0]

    fig = plt.figure(figsize=(14, 18), dpi=180)
    gs = fig.add_gridspec(4, 1, height_ratios=[3.2, 3.0, 2.45, 1.35], hspace=0.42)
    fig.suptitle(
        "C9当前实盘15万：2018起逐半年冷启动到2026-06-29",
        fontsize=23,
        fontweight="bold",
        x=0.5,
        y=0.985,
    )
    fig.text(
        0.5,
        0.962,
        "当前重建线上版本 official_live_stage847_c9_15w；每个起点独立重跑；Stage182月更AI池；订单API=0",
        ha="center",
        va="top",
        fontsize=11,
        color="#4a5568",
    )

    ax1 = fig.add_subplot(gs[0, 0])
    for idx, start in enumerate(starts):
        part = curves[curves["requested_start_month"].astype(str).eq(start)].copy()
        color = _start_color(idx, len(starts))
        linewidth = 2.4 if start in {"2018-01", "2022-01", "2026-01"} else 1.25
        alpha = 0.95 if linewidth > 2 else 0.68
        ax1.plot(part["date"], part["nav"], label=start, color=color, linewidth=linewidth, alpha=alpha)
    ax1.set_yscale("log")
    ax1.set_title("绝对日历净值曲线（log，统一结束日）", fontsize=15, loc="left", pad=12)
    ax1.set_ylabel("归一净值")
    ax1.grid(color="#d9dee7", linewidth=0.7, alpha=0.75)
    ax1.legend(loc="upper left", ncols=6, fontsize=8.5, frameon=False)
    ax1.spines[["top", "right"]].set_visible(False)

    ax2 = fig.add_subplot(gs[1, 0])
    for idx, start in enumerate(starts):
        part = curves[curves["requested_start_month"].astype(str).eq(start)].copy()
        color = _start_color(idx, len(starts))
        linewidth = 2.4 if start in {"2018-01", "2022-01", "2026-01"} else 1.2
        alpha = 0.95 if linewidth > 2 else 0.68
        ax2.plot(part["days_since_start"], part["nav"], label=start, color=color, linewidth=linewidth, alpha=alpha)
    ax2.set_yscale("log")
    ax2.set_title("按启动后交易日对齐的冷启动净值曲线（log）", fontsize=15, loc="left", pad=12)
    ax2.set_xlabel("启动后交易日")
    ax2.set_ylabel("归一净值")
    ax2.grid(color="#d9dee7", linewidth=0.7, alpha=0.75)
    ax2.spines[["top", "right"]].set_visible(False)

    ax3 = fig.add_subplot(gs[2, 0])
    x = np.arange(len(summary))
    returns = pd.to_numeric(summary["total_return_pct"], errors="coerce")
    dds = pd.to_numeric(summary["max_dd_pct"], errors="coerce")
    width = 0.38
    return_colors = np.where(returns.to_numpy() >= 0, "#2B6CB0", "#D64545")
    bars_ret = ax3.bar(x - width / 2, returns, width, color=return_colors, alpha=0.9, label="到2026-06-29收益")
    bars_dd = ax3.bar(x + width / 2, dds, width, color="#805AD5", alpha=0.78, label="区间最大回撤")
    ax3.axhline(0, color="#1f2933", linewidth=1.1)
    ax3.axhline(float(stat["median_return_pct"]), color="#2B6CB0", linestyle="--", linewidth=1.1, alpha=0.8)
    ax3.set_title("每个启动点的期末收益与区间最大回撤", fontsize=15, loc="left", pad=12)
    ax3.set_ylabel("百分比")
    ax3.set_xticks(x)
    ax3.set_xticklabels(starts, rotation=45, ha="right")
    ax3.grid(axis="y", color="#d9dee7", linewidth=0.7, alpha=0.75)
    ax3.legend(loc="upper right", frameon=False)
    ax3.spines[["top", "right"]].set_visible(False)
    _annotate_bars(ax3, bars_ret, returns, threshold_abs=80.0)
    _annotate_bars(ax3, bars_dd, dds, threshold_abs=35.0)

    ax4 = fig.add_subplot(gs[3, 0])
    ax4.axis("off")
    notes = [
        f"样本 {int(stat['sample_count'])} 个；正收益 {int(stat['positive_count'])}/{int(stat['sample_count'])}；收益最低/中位/最高 "
        f"{_pct(float(stat['min_return_pct']))}/{_pct(float(stat['median_return_pct']))}/{_pct(float(stat['max_return_pct']))}。",
        f"期末权益最低/中位/最高 {_money(float(stat['min_end_equity']))}/{_money(float(stat['median_end_equity']))}/{_money(float(stat['max_end_equity']))}。",
        f"最差回撤 {_pct(float(stat['worst_max_dd_pct']))}，来自 {stat['worst_max_dd_start']}；收益最差起点 {stat['min_return_start']}，收益最好起点 {stat['max_return_start']}。",
        f"Sharpe 中位 {float(stat['median_sharpe']):.3f}；peak broker10 margin/equity {_pct(float(stat['peak_broker10_margin_to_equity_pct']))}。",
    ]
    ax4.text(0.02, 0.96, "摘要", transform=ax4.transAxes, fontsize=15, fontweight="bold", va="top")
    for i, note in enumerate(notes):
        ax4.text(0.03, 0.75 - i * 0.19, note, transform=ax4.transAxes, fontsize=12, va="top", color="#2d3748")
    ax4.text(
        0.02,
        0.02,
        f"输出：{DASHBOARD_PATH.name}",
        transform=ax4.transAxes,
        fontsize=9,
        color="#718096",
    )

    fig.subplots_adjust(left=0.075, right=0.985, top=0.93, bottom=0.035)
    fig.savefig(DASHBOARD_PATH, facecolor="white", bbox_inches="tight")
    print(DASHBOARD_PATH)


if __name__ == "__main__":
    main()

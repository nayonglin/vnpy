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

MODEL_TAG = "stage936_c9_live_15w_halfyear_start_horizon_returns_v1"
OUTPUT_PREFIX = "qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns"

DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
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


def _annotate_bars(ax: plt.Axes, bars, values: pd.Series, *, fontsize: int = 9) -> None:
    for bar, value in zip(bars, values):
        if pd.isna(value):
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
            fontsize=fontsize,
            color="#20242a",
        )


def main() -> None:
    _configure_font()
    detail = pd.read_csv(DETAIL_PATH, encoding="utf-8-sig")
    stats = pd.read_csv(STATS_PATH, encoding="utf-8-sig")

    starts = sorted(detail["requested_start_month"].astype(str).unique())
    returns = detail.pivot(index="requested_start_month", columns="horizon_label", values="return_pct").reindex(starts)
    drawdowns = (
        detail.pivot(index="requested_start_month", columns="horizon_label", values="max_dd_pct_to_horizon")
        .reindex(starts)
    )
    half = returns.get("半年", pd.Series(index=starts, dtype=float))
    one = returns.get("一年", pd.Series(index=starts, dtype=float))
    half_dd = drawdowns.get("半年", pd.Series(index=starts, dtype=float))
    one_dd = drawdowns.get("一年", pd.Series(index=starts, dtype=float))

    half_stats = stats[stats["horizon_label"].eq("半年")].iloc[0]
    one_stats = stats[stats["horizon_label"].eq("一年")].iloc[0]

    fig = plt.figure(figsize=(11, 16), dpi=190)
    gs = fig.add_gridspec(4, 1, height_ratios=[3.05, 1.55, 2.55, 1.65], hspace=0.55)

    fig.suptitle(
        "C9当前实盘15万：不同启动月份的半年/一年收益分布",
        fontsize=22,
        fontweight="bold",
        x=0.5,
        y=0.985,
    )
    fig.text(
        0.5,
        0.958,
        "版本 official_live_stage847_c9_15w；Stage182月更AI池；数据到2026-06-15；2026-01未满半年已排除",
        ha="center",
        va="top",
        fontsize=10.5,
        color="#4a5568",
    )

    x = np.arange(len(starts))
    width = 0.38

    ax1 = fig.add_subplot(gs[0, 0])
    half_colors = np.where(half.fillna(0).to_numpy() >= 0, "#2B6CB0", "#D64545")
    one_colors = np.where(one.fillna(0).to_numpy() >= 0, "#2F855A", "#D64545")
    bars_half = ax1.bar(x - width / 2, half.to_numpy(), width, label="启动到半年", color=half_colors, alpha=0.92)
    one_values = one.to_numpy(dtype=float)
    one_mask = ~np.isnan(one_values)
    bars_one = ax1.bar(x[one_mask] + width / 2, one_values[one_mask], width, label="启动到一年", color=one_colors[one_mask], alpha=0.92)
    ax1.axhline(0, color="#1f2933", linewidth=1.1)
    ax1.axhline(
        float(half_stats["median_return_pct"]),
        color="#2B6CB0",
        linestyle="--",
        linewidth=1.2,
        alpha=0.75,
        label=f"半年中位 {_pct(float(half_stats['median_return_pct']))}",
    )
    ax1.axhline(
        float(one_stats["median_return_pct"]),
        color="#2F855A",
        linestyle="--",
        linewidth=1.2,
        alpha=0.75,
        label=f"一年中位 {_pct(float(one_stats['median_return_pct']))}",
    )
    _annotate_bars(ax1, bars_half, half, fontsize=8.5)
    _annotate_bars(ax1, bars_one, one.dropna(), fontsize=8.5)
    ax1.set_title("每个启动月份的收益率", fontsize=15, loc="left", pad=14)
    ax1.set_ylabel("收益率")
    ax1.set_xticks(x)
    ax1.set_xticklabels(starts, rotation=45, ha="right")
    ax1.set_ylim(min(-45, np.nanmin([half.min(), one.min()]) - 12), np.nanmax([half.max(), one.max()]) + 55)
    ax1.grid(axis="y", color="#d9dee7", linewidth=0.7, alpha=0.75)
    ax1.legend(loc="upper right", frameon=False, ncols=2, fontsize=10)
    ax1.spines[["top", "right"]].set_visible(False)

    ax2 = fig.add_subplot(gs[1, 0])
    summary_rows = [half_stats, one_stats]
    y_positions = np.array([1, 0])
    colors = ["#2B6CB0", "#2F855A"]
    labels = ["半年", "一年"]
    for row, y, color, label in zip(summary_rows, y_positions, colors, labels):
        min_v = float(row["min_return_pct"])
        med_v = float(row["median_return_pct"])
        max_v = float(row["max_return_pct"])
        ax2.hlines(y, min_v, max_v, color=color, linewidth=5, alpha=0.28)
        ax2.scatter([min_v, med_v, max_v], [y, y, y], s=[55, 120, 55], color=color, zorder=3)
        ax2.text(min_v, y + 0.23, f"低 {_pct(min_v)}", ha="center", fontsize=9, color="#333840")
        ax2.text(med_v, y - 0.32, f"中 {_pct(med_v)}", ha="center", fontsize=10, color="#111827", fontweight="bold")
        ax2.text(max_v, y + 0.23, f"高 {_pct(max_v)}", ha="center", fontsize=9, color="#333840")
        ax2.text(-58, y, label, va="center", ha="left", fontsize=13, fontweight="bold", color=color)
    ax2.axvline(0, color="#1f2933", linewidth=1)
    ax2.set_title("收益率区间摘要：最低 / 中位 / 最高", fontsize=15, loc="left", pad=12)
    ax2.set_xlim(-65, 460)
    ax2.set_ylim(-0.55, 1.55)
    ax2.set_yticks([])
    ax2.set_xlabel("收益率")
    ax2.grid(axis="x", color="#d9dee7", linewidth=0.7, alpha=0.75)
    ax2.spines[["top", "right", "left"]].set_visible(False)

    ax3 = fig.add_subplot(gs[2, 0])
    dd_width = 0.38
    bars_half_dd = ax3.bar(x - dd_width / 2, half_dd.to_numpy(), dd_width, label="半年内最大回撤", color="#C05621", alpha=0.85)
    one_dd_values = one_dd.to_numpy(dtype=float)
    one_dd_mask = ~np.isnan(one_dd_values)
    bars_one_dd = ax3.bar(
        x[one_dd_mask] + dd_width / 2,
        one_dd_values[one_dd_mask],
        dd_width,
        label="一年内最大回撤",
        color="#805AD5",
        alpha=0.82,
    )
    ax3.axhline(0, color="#1f2933", linewidth=1)
    ax3.set_title("启动后 horizon 内最大回撤", fontsize=15, loc="left", pad=14)
    ax3.set_ylabel("最大回撤")
    ax3.set_xticks(x)
    ax3.set_xticklabels(starts, rotation=45, ha="right")
    ax3.set_ylim(min(np.nanmin([half_dd.min(), one_dd.min()]) - 6, -48), 5)
    ax3.grid(axis="y", color="#d9dee7", linewidth=0.7, alpha=0.75)
    ax3.legend(loc="lower right", frameon=False)
    ax3.spines[["top", "right"]].set_visible(False)
    for bars, values in [(bars_half_dd, half_dd), (bars_one_dd, one_dd.dropna())]:
        for bar, value in zip(bars, values):
            if pd.isna(value):
                continue
            if float(value) <= -30:
                ax3.annotate(
                    _pct(float(value)),
                    xy=(bar.get_x() + bar.get_width() / 2, float(value)),
                    xytext=(0, -3),
                    textcoords="offset points",
                    ha="center",
                    va="top",
                    fontsize=8.5,
                    color="#20242a",
                )

    ax4 = fig.add_subplot(gs[3, 0])
    ax4.axis("off")
    notes = [
        f"结论1：半年收益中位 {_pct(float(half_stats['median_return_pct']))}，一年收益中位 {_pct(float(one_stats['median_return_pct']))}，中位路径仍为正。",
        "结论2：左尾集中在 2022-01 启动；半年 -26.42%，一年 -32.18%，这是实盘心理预期里必须接受的区间。",
        "结论3：右尾集中在 2021-01 启动；半年 157.86%，一年 428.51%，不能按这种年份外推未来。",
        f"口径：半年样本 {int(half_stats['sample_count'])} 个，一年样本 {int(one_stats['sample_count'])} 个；订单API=0。",
    ]
    ax4.text(
        0.02,
        0.96,
        "怎么读这张图",
        transform=ax4.transAxes,
        fontsize=15,
        fontweight="bold",
        va="top",
        color="#111827",
    )
    for i, note in enumerate(notes):
        ax4.text(
            0.03,
            0.76 - i * 0.18,
            note,
            transform=ax4.transAxes,
            fontsize=12,
            va="top",
            color="#2d3748",
        )
    ax4.text(
        0.02,
        0.02,
        "输出：Stage936 current-live 15w horizon return dashboard",
        transform=ax4.transAxes,
        fontsize=9,
        color="#718096",
    )

    fig.subplots_adjust(left=0.085, right=0.975, top=0.925, bottom=0.04)
    fig.savefig(DASHBOARD_PATH, facecolor="white", bbox_inches="tight")
    print(DASHBOARD_PATH)


if __name__ == "__main__":
    main()

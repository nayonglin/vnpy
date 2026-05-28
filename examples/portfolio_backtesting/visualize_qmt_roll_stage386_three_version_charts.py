from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "backtest_outputs"
CHART_DIR = OUTPUT_DIR / "qmt_roll_stage386_three_version_visual_charts"

DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage383_three_version_deep_audit_daily_stage383_three_version_deep_audit_v1.csv"
FIXED_PATH = OUTPUT_DIR / "qmt_roll_stage385_any_start_holding_experience_fixed_horizon_stage385_any_start_holding_experience_v1.csv"
BUCKET_PATH = OUTPUT_DIR / "qmt_roll_stage385_any_start_holding_experience_all_interval_buckets_stage385_any_start_holding_experience_v1.csv"
WORST_PATH = OUTPUT_DIR / "qmt_roll_stage385_any_start_holding_experience_worst_starts_stage385_any_start_holding_experience_v1.csv"

VARIANT_ORDER = ["stage079", "c3", "stage78_1"]
LABELS = {
    "stage079": "Stage079：C3+11.5万现金",
    "c3": "纯C3",
    "stage78_1": "78-1正式版",
}
SHORT_LABELS = {
    "stage079": "Stage079",
    "c3": "C3",
    "stage78_1": "78-1",
}
COLORS = {
    "stage079": "#0F9F8F",
    "c3": "#2E6FBB",
    "stage78_1": "#D45B43",
}

FOCUS_HORIZONS = ["1个月", "3个月", "6个月", "1年", "2年", "3年", "5年"]
BUCKET_ORDER = ["7-30天", "31-90天", "91-180天", "181-365天", "1-2年", "2-3年", "3-4年", "4-5年", "5年以上"]


def setup_style() -> None:
    font_path = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
    if font_path.exists():
        fm.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = "Arial Unicode MS"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 140
    plt.rcParams["savefig.dpi"] = 180
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.18
    plt.rcParams["grid.linewidth"] = 0.8


def pct(v: float) -> str:
    return f"{v:.1f}%"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = pd.read_csv(DAILY_PATH, parse_dates=["date"])
    fixed = pd.read_csv(FIXED_PATH)
    bucket = pd.read_csv(BUCKET_PATH)
    worst = pd.read_csv(WORST_PATH)
    return daily, fixed, bucket, worst


def plot_equity_drawdown(daily: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(2, 1, figsize=(13.5, 8.2), sharex=True, gridspec_kw={"height_ratios": [2.1, 1]})
    ax_nav, ax_dd = axes

    for variant in VARIANT_ORDER:
        sub = daily[daily["variant"] == variant].sort_values("date")
        ax_nav.plot(sub["date"], sub["nav"], label=SHORT_LABELS[variant], color=COLORS[variant], linewidth=2.2 if variant == "stage079" else 1.7)
        ax_dd.plot(sub["date"], sub["drawdown_pct"], label=SHORT_LABELS[variant], color=COLORS[variant], linewidth=2.0 if variant == "stage079" else 1.5)

    ax_nav.set_title("三版本累计净值：收益不是问题，持有过程的回撤差异才是核心", loc="left", fontsize=15, fontweight="bold")
    ax_nav.set_yscale("log")
    ax_nav.set_ylabel("净值（对数轴）")
    ax_nav.legend(ncol=3, frameon=False, loc="upper left")
    ax_nav.text(0.01, 0.03, "对数轴用于同时看清三条高收益曲线的相对斜率", transform=ax_nav.transAxes, fontsize=10, color="#555")

    ax_dd.axhline(-30, color="#7A1F1F", linestyle="--", linewidth=1.2, alpha=0.8)
    ax_dd.text(daily["date"].min(), -29.2, "30%回撤线", color="#7A1F1F", fontsize=10, va="bottom")
    ax_dd.set_title("水下回撤：Stage079 全程压在 -30% 内，C3/78-1 会穿线", loc="left", fontsize=13, fontweight="bold")
    ax_dd.set_ylabel("回撤")
    ax_dd.set_xlabel("日期")
    ax_dd.set_ylim(min(-45, daily["drawdown_pct"].min() - 2), 2)

    fig.tight_layout()
    out = CHART_DIR / "stage386_equity_drawdown.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_fixed_horizons(fixed: pd.DataFrame) -> Path:
    focus = fixed[fixed["horizon_label"].isin(FOCUS_HORIZONS)].copy()
    focus["horizon_label"] = pd.Categorical(focus["horizon_label"], FOCUS_HORIZONS, ordered=True)
    focus = focus.sort_values(["horizon_label", "variant"])

    fig, axes = plt.subplots(2, 2, figsize=(14, 9.2))
    axes = axes.ravel()

    metrics = [
        ("return_median_pct", "中位收益", "收益 %", "line"),
        ("return_p05_pct", "5%分位收益：差启动日下的底线", "收益 %", "line"),
        ("positive_return_rate", "正收益概率", "概率", "rate"),
        ("dd30_breach_rate", "持有期内破30%回撤概率", "概率", "rate"),
    ]

    for ax, (col, title, ylabel, kind) in zip(axes, metrics):
        for variant in VARIANT_ORDER:
            sub = focus[focus["variant"] == variant].sort_values("horizon_label")
            y = sub[col].to_numpy(dtype=float)
            if kind == "rate":
                y = y * 100.0
            ax.plot(
                sub["horizon_label"].astype(str),
                y,
                marker="o",
                linewidth=2.7 if variant == "stage079" else 1.9,
                markersize=5.5,
                label=SHORT_LABELS[variant],
                color=COLORS[variant],
            )
            for x, yy in zip(sub["horizon_label"].astype(str), y):
                if x in {"6个月", "1年", "3年"} and variant == "stage079":
                    ax.annotate(pct(yy), (x, yy), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8.5, color=COLORS[variant])
        if col == "dd30_breach_rate":
            ax.axhline(0, color="#333", linewidth=0.8)
        if col in {"positive_return_rate", "dd30_breach_rate"}:
            ax.set_ylim(-3, 103)
        ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold")
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", rotation=20)
        ax.legend(frameon=False, fontsize=9)

    fig.suptitle("不同启动日 + 固定持有期：真正舒服要从 6个月 到 1年 开始看", x=0.01, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = CHART_DIR / "stage386_fixed_horizon_experience.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_bucket_heatmaps(bucket: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8))

    heat_specs = [
        ("return_p05_pct", "全量起止区间：5%分位收益", "%", "RdYlGn", None, None),
        ("dd30_breach_rate", "全量起止区间：破30%回撤概率", "%", "YlOrRd", 0, 100),
    ]
    for ax, (col, title, suffix, cmap, vmin, vmax) in zip(axes, heat_specs):
        mat = []
        for variant in VARIANT_ORDER:
            row = []
            for bucket_name in BUCKET_ORDER:
                val = bucket[(bucket["variant"] == variant) & (bucket["bucket_name"] == bucket_name)][col].iloc[0]
                if col.endswith("_rate"):
                    val *= 100
                row.append(val)
            mat.append(row)
        arr = np.array(mat, dtype=float)
        if vmin is None:
            vmin = float(np.nanpercentile(arr, 5))
        if vmax is None:
            vmax = float(np.nanpercentile(arr, 95))
        im = ax.imshow(arr, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_yticks(np.arange(len(VARIANT_ORDER)), [SHORT_LABELS[v] for v in VARIANT_ORDER])
        ax.set_xticks(np.arange(len(BUCKET_ORDER)), BUCKET_ORDER, rotation=35, ha="right")
        ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold")
        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                val = arr[i, j]
                text_color = "white" if (col == "dd30_breach_rate" and val > 55) or (col == "return_p05_pct" and val < 0) else "#222"
                ax.text(j, i, f"{val:.1f}{suffix}", ha="center", va="center", fontsize=8.5, color=text_color)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cbar.ax.set_ylabel(suffix, rotation=0, labelpad=10)

    fig.suptitle("任意启动、任意结束：Stage079 的优势是把深回撤概率压下来", x=0.01, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = CHART_DIR / "stage386_interval_bucket_heatmaps.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_worst_windows(fixed: pd.DataFrame) -> Path:
    focus = fixed[fixed["horizon_label"].isin(["6个月", "1年", "2年", "3年", "5年"])].copy()
    focus["horizon_label"] = pd.Categorical(focus["horizon_label"], ["6个月", "1年", "2年", "3年", "5年"], ordered=True)
    focus = focus.sort_values(["horizon_label", "variant"])

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.8))
    width = 0.24
    x = np.arange(5)
    for offset, variant in zip([-width, 0, width], VARIANT_ORDER):
        sub = focus[focus["variant"] == variant].sort_values("horizon_label")
        axes[0].bar(x + offset, sub["return_min_pct"], width=width, color=COLORS[variant], label=SHORT_LABELS[variant])
        axes[1].bar(x + offset, sub["max_dd_worst_pct"], width=width, color=COLORS[variant], label=SHORT_LABELS[variant])

    axes[0].axhline(0, color="#333", linewidth=0.9)
    axes[0].set_title("最差启动日最终收益", loc="left", fontsize=12.5, fontweight="bold")
    axes[0].set_ylabel("收益 %")
    axes[0].set_xticks(x, ["6个月", "1年", "2年", "3年", "5年"])
    axes[0].legend(frameon=False)

    axes[1].axhline(-30, color="#7A1F1F", linestyle="--", linewidth=1.2)
    axes[1].set_title("最差启动日期间最大回撤", loc="left", fontsize=12.5, fontweight="bold")
    axes[1].set_ylabel("回撤 %")
    axes[1].set_xticks(x, ["6个月", "1年", "2年", "3年", "5年"])
    axes[1].legend(frameon=False)

    fig.suptitle("坏运气启动窗口：Stage079 不是最高收益，但最少穿越心理/风控红线", x=0.01, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = CHART_DIR / "stage386_worst_start_windows.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def image_to_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def write_html(image_paths: list[Path]) -> Path:
    cards = []
    for path in image_paths:
        cards.append(
            f"""
            <section class="chart">
              <img src="{image_to_data_uri(path)}" alt="{path.stem}" />
            </section>
            """
        )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Stage386 三版本表现图表</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; color: #17202a; background: #f6f7f9; }}
    header {{ padding: 28px 32px 18px; background: #ffffff; border-bottom: 1px solid #e6e9ee; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    p {{ margin: 0; color: #5d6976; line-height: 1.6; }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 24px; }}
    .chart {{ background: #fff; border: 1px solid #e6e9ee; border-radius: 8px; padding: 14px; margin-bottom: 22px; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04); }}
    img {{ width: 100%; display: block; border-radius: 4px; }}
    .note {{ margin-top: 14px; font-size: 13px; color: #6b7280; }}
  </style>
</head>
<body>
  <header>
    <h1>Stage386 三版本表现图表</h1>
    <p>基于 Stage083 日度权益与 Stage085 任意启动/持有期审计输出。只读可视化，不修改策略。</p>
    <p class="note">生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
  </header>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    out = CHART_DIR / "stage386_three_version_visual_dashboard.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    setup_style()
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    daily, fixed, bucket, worst = load_data()
    _ = worst

    paths = [
        plot_equity_drawdown(daily),
        plot_fixed_horizons(fixed),
        plot_bucket_heatmaps(bucket),
        plot_worst_windows(fixed),
    ]
    html = write_html(paths)
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "chart_dir": str(CHART_DIR),
        "charts": [str(p) for p in paths],
        "html": str(html),
    }
    pd.Series(summary).to_json(CHART_DIR / "stage386_three_version_visual_charts_manifest.json", force_ascii=False, indent=2)
    print(summary)


if __name__ == "__main__":
    main()

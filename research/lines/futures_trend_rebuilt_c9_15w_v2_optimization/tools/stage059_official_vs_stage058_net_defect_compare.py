from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage059"
MODEL_TAG = "stage059_official_vs_stage058_net_defect_compare_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage059_official_vs_stage058_net_defect_compare"
LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage059_official_vs_stage058_net_defect_compare"
STAGES_DIR = LINE_DIR / "stages"
END_DATE = pd.Timestamp("2026-06-30")

STAGE053_CURVES_PATH = (
    LINE_DIR
    / "outputs"
    / "stage053_valuable_versions_halfyear_curves"
    / "rebuilt_c9_v2_stage053_halfyear_curves_stage053_valuable_versions_halfyear_curves_v1.csv.gz"
)
STAGE058_CURVES_PATH = (
    LINE_DIR
    / "outputs"
    / "stage058_quality_oi_cap50_add_risk_engine"
    / "rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_curves_stage058_quality_oi_cap50_add_risk_engine_v1.csv"
)
STAGE058_SUMMARY_PATH = (
    LINE_DIR
    / "outputs"
    / "stage058_quality_oi_cap50_add_risk_engine"
    / "rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_summary_stage058_quality_oi_cap50_add_risk_engine_v1.csv"
)

PAIR_CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_pair_curves_{MODEL_TAG}.csv"
START_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_start_defect_summary_{MODEL_TAG}.csv"
MONTHLY_HEATMAP_PATH = OUT / f"{OUTPUT_PREFIX}_monthly_gap_heatmap_{MODEL_TAG}.csv"
RELATIVE_GAP_GRID_PATH = OUT / f"{OUTPUT_PREFIX}_relative_gap_grid_{MODEL_TAG}.png"
DEFICIT_ONLY_GRID_PATH = OUT / f"{OUTPUT_PREFIX}_deficit_only_grid_{MODEL_TAG}.png"
NAV_DD_FOCUS_PATH = OUT / f"{OUTPUT_PREFIX}_nav_drawdown_focus_{MODEL_TAG}.png"
DEFECT_BAR_PATH = OUT / f"{OUTPUT_PREFIX}_defect_bar_summary_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_VERSION = "Official C9/15w Stage847"
RESEARCH_VERSION = "Stage058 quality+OI cap50 true engine"


def _drawdown_pct(nav: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(nav, errors="coerce")
    running_max = numeric.cummax()
    return (numeric / running_max - 1.0) * 100.0


def load_official_curves(path: Path = STAGE053_CURVES_PATH) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame[frame["version"].eq(OFFICIAL_VERSION)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["official_equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame.dropna(subset=["date", "requested_start_month", "official_equity"])
    frame = frame[frame["date"].le(END_DATE)].copy()
    frame = frame.sort_values(["requested_start_month", "date"]).reset_index(drop=True)
    first = frame.groupby("requested_start_month")["official_equity"].transform("first")
    frame["official_nav"] = frame["official_equity"] / first
    frame["official_drawdown_pct"] = frame.groupby("requested_start_month")["official_nav"].transform(_drawdown_pct)
    return frame[
        [
            "requested_start_month",
            "date",
            "official_equity",
            "official_nav",
            "official_drawdown_pct",
        ]
    ]


def load_stage058_curves(path: Path = STAGE058_CURVES_PATH) -> pd.DataFrame:
    frame = pd.read_csv(
        path,
        usecols=["requested_start_month", "date", "account_equity", "nav", "drawdown_pct"],
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["stage058_equity"] = pd.to_numeric(frame["account_equity"], errors="coerce")
    frame["stage058_nav"] = pd.to_numeric(frame["nav"], errors="coerce")
    frame["stage058_drawdown_pct"] = pd.to_numeric(frame["drawdown_pct"], errors="coerce")
    frame = frame.dropna(subset=["requested_start_month", "date", "stage058_equity", "stage058_nav"])
    frame = frame[frame["date"].le(END_DATE)].copy()
    return frame[
        [
            "requested_start_month",
            "date",
            "stage058_equity",
            "stage058_nav",
            "stage058_drawdown_pct",
        ]
    ]


def build_pair_curves(official: pd.DataFrame, research: pd.DataFrame) -> pd.DataFrame:
    pair = official.merge(research, on=["requested_start_month", "date"], how="inner")
    pair = pair.sort_values(["requested_start_month", "date"]).reset_index(drop=True)
    pair["stage058_minus_official_nav"] = pair["stage058_nav"] - pair["official_nav"]
    pair["stage058_vs_official_nav_gap_pct"] = (pair["stage058_nav"] / pair["official_nav"] - 1.0) * 100.0
    pair["stage058_minus_official_equity"] = pair["stage058_equity"] - pair["official_equity"]
    pair["drawdown_gap_pp"] = pair["stage058_drawdown_pct"] - pair["official_drawdown_pct"]
    pair["stage058_lags_official"] = pair["stage058_vs_official_nav_gap_pct"].lt(0.0)
    pair["month"] = pair["date"].dt.to_period("M").astype(str)
    return pair


def summarize_start_defects(pair: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for start, group in pair.groupby("requested_start_month", sort=True):
        group = group.sort_values("date")
        final = group.iloc[-1]
        worst_gap_idx = group["stage058_vs_official_nav_gap_pct"].idxmin()
        worst_gap = group.loc[worst_gap_idx]
        worst_dd_gap_idx = group["drawdown_gap_pp"].idxmin()
        worst_dd_gap = group.loc[worst_dd_gap_idx]
        rows.append(
            {
                "requested_start_month": start,
                "date_start": group["date"].iloc[0].date().isoformat(),
                "date_end": group["date"].iloc[-1].date().isoformat(),
                "final_official_nav": float(final["official_nav"]),
                "final_stage058_nav": float(final["stage058_nav"]),
                "final_stage058_vs_official_gap_pct": float(final["stage058_vs_official_nav_gap_pct"]),
                "final_stage058_minus_official_nav": float(final["stage058_minus_official_nav"]),
                "final_stage058_minus_official_equity": float(final["stage058_minus_official_equity"]),
                "worst_stage058_vs_official_gap_pct": float(worst_gap["stage058_vs_official_nav_gap_pct"]),
                "worst_gap_date": pd.Timestamp(worst_gap["date"]).date().isoformat(),
                "stage058_lag_days": int(group["stage058_lags_official"].sum()),
                "stage058_lag_day_ratio_pct": float(group["stage058_lags_official"].mean() * 100.0),
                "official_max_drawdown_pct": float(group["official_drawdown_pct"].min()),
                "stage058_max_drawdown_pct": float(group["stage058_drawdown_pct"].min()),
                "drawdown_gap_pp": float(group["stage058_drawdown_pct"].min() - group["official_drawdown_pct"].min()),
                "worst_drawdown_gap_pp": float(worst_dd_gap["drawdown_gap_pp"]),
                "worst_drawdown_gap_date": pd.Timestamp(worst_dd_gap["date"]).date().isoformat(),
            }
        )
    return pd.DataFrame(rows)


def build_monthly_heatmap(pair: pd.DataFrame) -> pd.DataFrame:
    month_end = pair.sort_values("date").groupby(["requested_start_month", "month"], as_index=False).tail(1)
    heatmap = month_end.pivot(
        index="requested_start_month",
        columns="month",
        values="stage058_vs_official_nav_gap_pct",
    )
    return heatmap.sort_index(axis=0).sort_index(axis=1)


def plot_relative_gap_grid(pair: pd.DataFrame, summary: pd.DataFrame) -> None:
    starts = sorted(pair["requested_start_month"].unique())
    cols = 3
    rows = int(np.ceil(len(starts) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(18, 3.4 * rows), sharex=False, sharey=True, constrained_layout=True)
    flat_axes = np.array(axes).reshape(-1)
    for ax, start in zip(flat_axes, starts):
        group = pair[pair["requested_start_month"].eq(start)].sort_values("date")
        y = group["stage058_vs_official_nav_gap_pct"]
        ax.plot(group["date"], y, color="#1f77b4", linewidth=1.1)
        ax.fill_between(group["date"], y, 0, where=y.ge(0), color="#2ca02c", alpha=0.18, interpolate=True)
        ax.fill_between(group["date"], y, 0, where=y.lt(0), color="#d62728", alpha=0.22, interpolate=True)
        ax.axhline(0, color="#111827", linewidth=0.8)
        row = summary[summary["requested_start_month"].eq(start)].iloc[0]
        title = (
            f"{start}  final {row['final_stage058_vs_official_gap_pct']:+.1f}%  "
            f"worst {row['worst_stage058_vs_official_gap_pct']:+.1f}%"
        )
        ax.set_title(title, fontsize=9)
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
    for ax in flat_axes[len(starts) :]:
        ax.axis("off")
    fig.suptitle(
        "Stage058 vs Official: NAV Gap by Start Cycle (Stage058 / Official - 1)",
        fontsize=15,
    )
    fig.supxlabel("Date")
    fig.supylabel("Research version relative NAV gap (%)")
    fig.savefig(RELATIVE_GAP_GRID_PATH, dpi=170)
    plt.close(fig)


def plot_deficit_only_grid(pair: pd.DataFrame, summary: pd.DataFrame) -> None:
    starts = sorted(pair["requested_start_month"].unique())
    cols = 3
    rows = int(np.ceil(len(starts) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(18, 3.1 * rows), sharex=False, sharey=True, constrained_layout=True)
    flat_axes = np.array(axes).reshape(-1)
    for ax, start in zip(flat_axes, starts):
        group = pair[pair["requested_start_month"].eq(start)].sort_values("date")
        deficit = np.minimum(group["stage058_vs_official_nav_gap_pct"].to_numpy(dtype=float), 0.0)
        ax.plot(group["date"], deficit, color="#b91c1c", linewidth=1.1)
        ax.fill_between(group["date"], deficit, 0, color="#dc2626", alpha=0.24)
        ax.axhline(0, color="#111827", linewidth=0.8)
        row = summary[summary["requested_start_month"].eq(start)].iloc[0]
        title = (
            f"{start}  worst {row['worst_stage058_vs_official_gap_pct']:+.1f}%  "
            f"lagdays {row['stage058_lag_day_ratio_pct']:.0f}%"
        )
        ax.set_title(title, fontsize=9)
        ax.set_ylim(-36, 2)
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
    for ax in flat_axes[len(starts) :]:
        ax.axis("off")
    fig.suptitle("Stage058 Deficit Only: Negative NAV Gap vs Official", fontsize=15)
    fig.supxlabel("Date")
    fig.supylabel("Only negative relative NAV gap (%)")
    fig.savefig(DEFICIT_ONLY_GRID_PATH, dpi=170)
    plt.close(fig)


def plot_nav_drawdown_focus(pair: pd.DataFrame, summary: pd.DataFrame) -> list[str]:
    ranked = summary.sort_values(
        ["final_stage058_vs_official_gap_pct", "worst_stage058_vs_official_gap_pct"],
        ascending=[True, True],
    )
    focus_starts = ranked["requested_start_month"].head(6).tolist()
    fig, axes = plt.subplots(len(focus_starts), 3, figsize=(18, 3.1 * len(focus_starts)), constrained_layout=True)
    for row_idx, start in enumerate(focus_starts):
        group = pair[pair["requested_start_month"].eq(start)].sort_values("date")
        ax = axes[row_idx, 0]
        ax.plot(group["date"], group["official_nav"], color="#111827", linewidth=1.0, label="Official")
        ax.plot(group["date"], group["stage058_nav"], color="#2563eb", linewidth=1.0, label="Stage058")
        ax.set_title(f"{start}: normalized NAV")
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=7)
        if row_idx == 0:
            ax.legend(fontsize=8, loc="best")

        ax = axes[row_idx, 1]
        ax.plot(group["date"], group["official_drawdown_pct"], color="#111827", linewidth=1.0, label="Official DD")
        ax.plot(group["date"], group["stage058_drawdown_pct"], color="#2563eb", linewidth=1.0, label="Stage058 DD")
        ax.axhline(0, color="#111827", linewidth=0.7)
        ax.set_title("underwater / drawdown")
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=7)

        ax = axes[row_idx, 2]
        y = group["stage058_vs_official_nav_gap_pct"]
        ax.plot(group["date"], y, color="#7c3aed", linewidth=1.0)
        ax.fill_between(group["date"], y, 0, where=y.ge(0), color="#2ca02c", alpha=0.18, interpolate=True)
        ax.fill_between(group["date"], y, 0, where=y.lt(0), color="#d62728", alpha=0.22, interpolate=True)
        ax.axhline(0, color="#111827", linewidth=0.7)
        ax.set_title("Stage058 relative gap")
        ax.grid(True, alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=7)
    fig.suptitle("Worst Stage058 Cycles: NAV, Drawdown, and Relative Defect")
    fig.savefig(NAV_DD_FOCUS_PATH, dpi=170)
    plt.close(fig)
    return focus_starts


def plot_defect_bars(summary: pd.DataFrame) -> None:
    frame = summary.sort_values("requested_start_month").copy()
    x = np.arange(len(frame))
    width = 0.28
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    axes[0].bar(
        x - width,
        frame["final_stage058_vs_official_gap_pct"],
        width=width,
        label="final relative NAV gap",
        color="#2563eb",
    )
    axes[0].bar(
        x,
        frame["worst_stage058_vs_official_gap_pct"],
        width=width,
        label="worst relative NAV lag",
        color="#dc2626",
    )
    axes[0].bar(
        x + width,
        frame["drawdown_gap_pp"],
        width=width,
        label="max drawdown gap (pp)",
        color="#f59e0b",
    )
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_ylabel("percent / percentage points")
    axes[0].set_title("Per-start defect summary")
    axes[0].legend(loc="best")
    axes[0].grid(True, axis="y", alpha=0.22)

    colors = np.where(frame["stage058_lag_day_ratio_pct"].gt(50), "#dc2626", "#6b7280")
    axes[1].bar(x, frame["stage058_lag_day_ratio_pct"], color=colors)
    axes[1].axhline(50, color="#111827", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("days lagging official (%)")
    axes[1].set_title("How often Stage058 stays below Official")
    axes[1].grid(True, axis="y", alpha=0.22)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(frame["requested_start_month"].tolist(), rotation=35, ha="right")
    fig.savefig(DEFECT_BAR_PATH, dpi=170)
    plt.close(fig)


def write_report(summary: pd.DataFrame, focus_starts: list[str]) -> Path:
    worst_final = summary.sort_values("final_stage058_vs_official_gap_pct").head(6)
    worst_lag = summary.sort_values("worst_stage058_vs_official_gap_pct").head(6)
    md = [
        "# Stage059 正式版 vs Stage058 净值缺陷对比",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：只读可视化；不重跑策略、不改参数、不连接 CTP、不调用订单 API",
        "- 对照：`Official C9/15w Stage847` vs `Stage058 quality+OI cap50 true engine`",
        "",
        "## 图怎么读",
        "",
        "- `relative_gap_grid`：每个起点一个小面板，曲线为 `Stage058 NAV / Official NAV - 1`；红色表示研究版低于正式版，绿色表示研究版高于正式版。",
        "- `nav_drawdown_focus`：挑选 Stage058 终点缺口最差的 6 个起点，左列是两版净值，中列是 underwater/drawdown，右列是相对净值缺口。",
        "- `defect_bar_summary`：每个起点的终点缺口、历史最深相对落后、最大回撤缺口，以及研究版低于正式版的交易日比例。",
        "",
        "## 终点缺口最差起点",
        "",
        worst_final.to_markdown(index=False),
        "",
        "## 历史最深相对落后起点",
        "",
        worst_lag.to_markdown(index=False),
        "",
        "## 结论",
        "",
        "- Stage058 的问题不是所有周期都弱，而是周期缺陷不均匀：有些起点最终明显跑赢，但部分起点会长期或深度落后正式版。",
        "- 这解释了为什么它看起来中位收益有提升，却不能晋级：正式版对短窗口和右尾保留更稳，Stage058 在缺陷周期里出现负终点或更深 underwater。",
        "",
        "## 输出",
        "",
        f"- pair_curves: `{PAIR_CURVES_PATH}`",
        f"- start_summary: `{START_SUMMARY_PATH}`",
        f"- monthly_heatmap: `{MONTHLY_HEATMAP_PATH}`",
        f"- relative_gap_grid: `{RELATIVE_GAP_GRID_PATH}`",
        f"- deficit_only_grid: `{DEFICIT_ONLY_GRID_PATH}`",
        f"- nav_drawdown_focus: `{NAV_DD_FOCUS_PATH}`",
        f"- defect_bar_summary: `{DEFECT_BAR_PATH}`",
        f"- focus_starts: `{', '.join(focus_starts)}`",
    ]
    REPORT_PATH.write_text("\n".join(md) + "\n", encoding="utf-8")
    return REPORT_PATH


def write_stage_record(summary: pd.DataFrame) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage059_official_vs_stage058_net_defect_compare.md"
    worst_final = summary.sort_values("final_stage058_vs_official_gap_pct").iloc[0]
    worst_lag = summary.sort_values("worst_stage058_vs_official_gap_pct").iloc[0]
    lines = [
        "# Stage059 正式版 vs Stage058 净值缺陷对比",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区/分支：`{ROOT}`",
        "- 阶段性质：只读可视化；不重跑策略、不改参数、不连接 CTP、不调用订单 API",
        "- 是否重要突破：否",
        "- 是否触发A/B：否；复用既有正式版与 Stage058 曲线",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：pysystemtrade/backtesting、underwater graph/drawdown analysis、drawdown definition。",
        "- 我的判断：用户需要看的不是绝对收益曲线堆叠，而是同日起点、同日期下研究版相对正式版的净值缺口和 underwater 缺陷。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无",
        "- 删除脚本：无",
        "- 新增参数：无交易参数；新增可视化口径 `Stage058 NAV / Official NAV - 1`、`drawdown_gap_pp`、`lag_day_ratio`",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：复用 Stage053 与 Stage058 既有曲线，终点 `2026-06-30`",
        "- 账户规模：两者均按各自曲线首日净值归一化，初始 NAV=1",
        "- 成本口径：不重算，沿用原曲线成本",
        "- 样本过滤：逐半年起点 `2018-01` 到 `2026-01`",
        "- 策略/归因口径：只读比较正式版与 Stage058 的净值相对缺口、回撤缺口和落后天数比例",
        "",
        "## 结果",
        "",
        f"- 终点缺口最差起点：`{worst_final['requested_start_month']}`，终点相对缺口 `{worst_final['final_stage058_vs_official_gap_pct']:.4f}%`",
        f"- 历史最深相对落后起点：`{worst_lag['requested_start_month']}`，最深相对缺口 `{worst_lag['worst_stage058_vs_official_gap_pct']:.4f}%`，发生日 `{worst_lag['worst_gap_date']}`",
        f"- 研究版低于正式版天数比例最高：`{summary.sort_values('stage058_lag_day_ratio_pct', ascending=False).iloc[0]['requested_start_month']}`",
        "- 期末权益/总收益/Sharpe/交易次数：本阶段不重跑回测，详见 Stage058 和 Stage053 原始 summary。",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{START_SUMMARY_PATH}`",
        f"- daily：`{PAIR_CURVES_PATH}`",
        f"- chart_relative_gap：`{RELATIVE_GAP_GRID_PATH}`",
        f"- chart_deficit_only：`{DEFICIT_ONLY_GRID_PATH}`",
        f"- chart_focus：`{NAV_DD_FOCUS_PATH}`",
        f"- chart_bars：`{DEFECT_BAR_PATH}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：Stage058 的缺陷主要体现在部分起点的相对净值落后、回撤缺口和落后天数，而不是简单的整体收益低。",
        "- 是否进入下一步：否；这是解释图，不改变 Stage058 不晋级判断。",
        "- 下一步：若继续研究，应换新 PIT 源或账户外层，不围绕 Stage058 的 OI 阈值/AI topN/权重救参。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否；只读比较既有曲线，不写交易规则。",
        "- 运行后判断：否；没有新增策略参数。",
        "- 原因：这是诊断可视化，不改变历史结果。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有；用户明确看不懂原图，需要解释 Stage058 为什么不晋级。",
        "- 运行后判断：有但仅限展示；图已解释缺陷，不支持继续救参。",
        "- 原因：可视化能帮助决策，但不能替代新证据。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    official = load_official_curves()
    research = load_stage058_curves()
    pair = build_pair_curves(official, research)
    summary = summarize_start_defects(pair)
    heatmap = build_monthly_heatmap(pair)
    plot_relative_gap_grid(pair, summary)
    plot_deficit_only_grid(pair, summary)
    focus_starts = plot_nav_drawdown_focus(pair, summary)
    plot_defect_bars(summary)

    pair.to_csv(PAIR_CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(START_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    heatmap.to_csv(MONTHLY_HEATMAP_PATH, encoding="utf-8-sig")
    report = write_report(summary, focus_starts)
    stage_record = write_stage_record(summary)
    print(
        {
            "pair_rows": int(len(pair)),
            "start_rows": int(len(summary)),
            "worst_final_start": str(summary.sort_values("final_stage058_vs_official_gap_pct").iloc[0]["requested_start_month"]),
            "worst_final_gap_pct": float(summary["final_stage058_vs_official_gap_pct"].min()),
            "worst_relative_gap_pct": float(summary["worst_stage058_vs_official_gap_pct"].min()),
            "report": str(report),
            "stage_record": str(stage_record),
            "relative_gap_grid": str(RELATIVE_GAP_GRID_PATH),
            "deficit_only_grid": str(DEFICIT_ONLY_GRID_PATH),
            "nav_drawdown_focus": str(NAV_DD_FOCUS_PATH),
            "defect_bar_summary": str(DEFECT_BAR_PATH),
        }
    )


if __name__ == "__main__":
    main()

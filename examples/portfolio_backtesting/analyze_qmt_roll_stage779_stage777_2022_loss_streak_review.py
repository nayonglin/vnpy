from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage779_stage777_2022_loss_streak_review_v1"
OUTPUT_PREFIX = "qmt_roll_stage779_stage777_2022_loss_streak_review"
LINE_ID = "futures_trend_2019_data_extension"

SOURCE_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage778_stage777_2022_drawdown_forensics_closed_lots_around_dd_"
    "stage778_stage777_2022_drawdown_forensics_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
OI_GROUP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_oi_group_{MODEL_TAG}.csv"
WORST_SEQUENCE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_sequence_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

FOCUS_PROFILE = "oi_restore_am40"
FOCUS_START = "2021-09"


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_window_lots() -> pd.DataFrame:
    frame = pd.read_csv(SOURCE_PATH, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date", "reference_peak_date", "reference_trough_date"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
    frame = frame[
        frame["exit_date"].between(frame["reference_peak_date"], frame["reference_trough_date"], inclusive="both")
    ].copy()
    for column in [
        "realized_pnl",
        "r_multiple",
        "volume",
        "oi_price_confirm_risk_restore_applied",
        "loss_streak",
        "risk_multiplier",
    ]:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    return frame


def _longest_loss_segment(group: pd.DataFrame) -> pd.DataFrame:
    current: list[pd.Series] = []
    segments: list[pd.DataFrame] = []
    for _, row in group.iterrows():
        if float(row["realized_pnl"]) < 0:
            current.append(row)
        else:
            if current:
                segments.append(pd.DataFrame(current))
                current = []
    if current:
        segments.append(pd.DataFrame(current))
    if not segments:
        return pd.DataFrame(columns=group.columns)
    return max(segments, key=len).copy()


def _summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (profile, start_month), group in frame.groupby(["profile", "start_month"], sort=True):
        ordered = group.sort_values(["exit_date", "entry_date", "vt_symbol", "lot_id"]).copy()
        longest = _longest_loss_segment(ordered)
        rows.append(
            {
                "profile": profile,
                "start_month": start_month,
                "closed_lots": int(len(ordered)),
                "loss_lots": int(pd.to_numeric(ordered["realized_pnl"], errors="coerce").lt(0).sum()),
                "win_lots": int(pd.to_numeric(ordered["realized_pnl"], errors="coerce").gt(0).sum()),
                "realized_pnl_sum": float(pd.to_numeric(ordered["realized_pnl"], errors="coerce").sum()),
                "max_consecutive_loss_lots": int(len(longest)),
                "max_loss_streak_pnl": float(pd.to_numeric(longest.get("realized_pnl", []), errors="coerce").sum())
                if len(longest)
                else 0.0,
                "max_loss_streak_oi_lots": int(
                    pd.to_numeric(longest.get("oi_price_confirm_risk_restore_applied", []), errors="coerce")
                    .fillna(0)
                    .eq(1)
                    .sum()
                )
                if len(longest)
                else 0,
                "max_loss_streak_oi_pnl": float(
                    pd.to_numeric(
                        longest.loc[
                            pd.to_numeric(longest.get("oi_price_confirm_risk_restore_applied", 0), errors="coerce")
                            .fillna(0)
                            .eq(1),
                            "realized_pnl",
                        ],
                        errors="coerce",
                    ).sum()
                )
                if len(longest)
                else 0.0,
                "entry_loss_streak_max": float(pd.to_numeric(ordered.get("loss_streak"), errors="coerce").max()),
                "entry_loss_streak_ge3_count": int(
                    pd.to_numeric(ordered.get("loss_streak"), errors="coerce").fillna(0).ge(3).sum()
                ),
                "risk_multiplier_unique": ",".join(
                    f"{value:g}"
                    for value in sorted(pd.to_numeric(ordered.get("risk_multiplier"), errors="coerce").dropna().unique())
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["profile", "start_month"]).reset_index(drop=True)


def _oi_group(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame[frame["profile"].eq(FOCUS_PROFILE)].copy()
    return (
        data.groupby(["start_month", "oi_price_confirm_risk_restore_applied"], as_index=False)
        .agg(
            lots=("lot_id", "count"),
            loss_lots=("realized_pnl", lambda values: int(pd.to_numeric(values, errors="coerce").lt(0).sum())),
            pnl=("realized_pnl", "sum"),
            avg_r=("r_multiple", "mean"),
            volume=("volume", "sum"),
        )
        .sort_values(["start_month", "oi_price_confirm_risk_restore_applied"])
        .reset_index(drop=True)
    )


def _focus_sequence(frame: pd.DataFrame) -> pd.DataFrame:
    focus = frame[(frame["profile"].eq(FOCUS_PROFILE)) & (frame["start_month"].eq(FOCUS_START))].copy()
    focus = focus.sort_values(["exit_date", "entry_date", "vt_symbol", "lot_id"]).copy()
    focus["is_loss"] = focus["realized_pnl"].lt(0)
    loss_streak: list[int] = []
    streak = 0
    for is_loss in focus["is_loss"]:
        streak = streak + 1 if is_loss else 0
        loss_streak.append(streak)
    focus["loss_streak_after_close"] = loss_streak
    focus["seq"] = range(1, len(focus) + 1)
    return focus


def _plot(focus: pd.DataFrame) -> None:
    data = focus.copy()
    colors = ["#dc2626" if value < 0 else "#059669" for value in data["realized_pnl"]]
    labels = [
        f"{row.seq}\n{row.product}\n{row.direction[0].upper()}"
        for row in data.itertuples(index=False)
    ]
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), gridspec_kw={"height_ratios": [2, 1]}, constrained_layout=True)
    axes[0].bar(data["seq"], data["realized_pnl"] / 1_000, color=colors)
    axes[0].axhline(0.0, color="#111827", linewidth=1)
    axes[0].set_title(f"Stage779 {FOCUS_PROFILE} {FOCUS_START}: closed lots during 2022 peak-to-trough")
    axes[0].set_ylabel("Realized PnL (k)")
    axes[0].set_xticks(data["seq"])
    axes[0].set_xticklabels(labels, fontsize=8)
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].step(data["seq"], data["loss_streak_after_close"], where="mid", color="#7c2d12", linewidth=2)
    axes[1].scatter(data["seq"], data["loss_streak_after_close"], c=colors, s=40)
    axes[1].set_ylabel("Consecutive losses")
    axes[1].set_xlabel("Closed lot sequence")
    axes[1].set_xticks(data["seq"])
    axes[1].grid(alpha=0.25)
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, oi_group: pd.DataFrame, focus: pd.DataFrame) -> None:
    detail_columns = [
        "seq",
        "exit_date",
        "entry_date",
        "product",
        "vt_symbol",
        "direction",
        "volume",
        "realized_pnl",
        "r_multiple",
        "oi_price_confirm_risk_restore_applied",
        "loss_streak",
        "risk_multiplier",
        "exit_reason",
        "loss_streak_after_close",
    ]
    focus_view = focus[[column for column in detail_columns if column in focus.columns]].copy()
    lines = [
        "# Stage779 Stage777 2022 连续亏损逐笔复盘",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 性质：只读归因；不改策略、不连接 CTP、不调用下单。",
        "- 口径：读取 Stage778 峰谷窗口闭合 lot，按出场时间重排，统计连续亏损段。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## OI Applied Group",
        "",
        _md_table(oi_group),
        "",
        f"## Focus Sequence: {FOCUS_PROFILE} {FOCUS_START}",
        "",
        _md_table(focus_view),
        "",
        "## Conclusion",
        "",
        "- 若指策略参数里的连败缩仓机制：不是。Stage777 使用关闭连败缩放的口径，风险倍率只有基础 `1` 和 OI 命中后的 `2`，没有 `0.1` 连败风控。",
        "- 若指真实交易结果是否连续失败：是。代表起点在 `2022-04-08` 后出现 `13` 笔连续亏损，且这段连续亏损在 OI 版本中有 `8` 笔命中 OI 放大。",
        "- 不开 OI 版本也有同样长度的连续亏损段，说明连亏来自趋势本体在 2022 的反转/震荡窗口；OI 的作用是把其中多笔亏损放大。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    frame = _load_window_lots()
    summary = _summary(frame)
    oi_group = _oi_group(frame)
    focus = _focus_sequence(frame)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    oi_group.to_csv(OI_GROUP_PATH, index=False, encoding="utf-8-sig")
    focus.to_csv(WORST_SEQUENCE_PATH, index=False, encoding="utf-8-sig")
    _plot(focus)
    _write_report(summary, oi_group, focus)
    print(_md_table(summary))
    print(_md_table(focus[[c for c in [
        "seq",
        "exit_date",
        "entry_date",
        "product",
        "direction",
        "volume",
        "realized_pnl",
        "r_multiple",
        "oi_price_confirm_risk_restore_applied",
        "loss_streak",
        "risk_multiplier",
        "exit_reason",
        "loss_streak_after_close",
    ] if c in focus.columns]]))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()

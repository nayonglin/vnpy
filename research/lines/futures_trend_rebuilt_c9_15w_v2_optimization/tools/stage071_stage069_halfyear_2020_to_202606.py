from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import stage069_stage013_fullcycle_intraday_stop as s069


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage071"
MODEL_TAG = "stage071_stage069_halfyear_2020_to_202606_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage071_stage069_halfyear_2020_to_202606"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage071_stage069_halfyear_2020_to_202606"
STAGES_DIR = LINE_DIR / "stages"

REQUESTED_START = pd.Timestamp("2020-01-01")
LATEST_START = pd.Timestamp("2026-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
BASE_CAPITAL = float(s069.BASE_CAPITAL)

BASELINE = s069.BASELINE
C1_NO_REENTRY = s069.C1_NO_REENTRY
C2_DAILY_REENTRY = s069.C2_DAILY_REENTRY
VARIANTS = s069.VARIANTS
VARIANT_LABELS = s069.VARIANT_LABELS
VARIANT_COLORS = s069.VARIANT_COLORS

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
DELTA_PATH = OUT / f"{OUTPUT_PREFIX}_delta_vs_baseline_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_events_{MODEL_TAG}.csv.gz"
EVENT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_event_summary_{MODEL_TAG}.csv"
CHART_EQUITY_PATH = OUT / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"
CHART_RETURN_DD_PATH = OUT / f"{OUTPUT_PREFIX}_return_dd_{MODEL_TAG}.png"
CHART_DELTA_PATH = OUT / f"{OUTPUT_PREFIX}_delta_vs_baseline_{MODEL_TAG}.png"
CHART_UNDERWATER_PATH = OUT / f"{OUTPUT_PREFIX}_underwater_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s069._json_safe(value)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _halfyear_starts() -> list[pd.Timestamp]:
    return [pd.Timestamp(item).normalize() for item in pd.date_range(REQUESTED_START, LATEST_START, freq="6MS")]


def _variant_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version in VARIANTS:
        group = summary[summary["version"].eq(version)].copy()
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["max_dd_pct"], errors="coerce")
        underwater = pd.to_numeric(group["days_below_initial"], errors="coerce").fillna(0)
        rows.append(
            {
                "version": version,
                "variant_label": VARIANT_LABELS[version],
                "start_count": int(len(group)),
                "positive_count": int(returns.gt(0).sum()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "worst_dd_pct": float(dds.min()),
                "median_dd_pct": float(dds.median()),
                "max_days_below_initial": int(underwater.max()),
                "median_days_below_initial": float(underwater.median()),
                "total_trade_count_sum": float(pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0).sum()),
                "total_slippage_sum": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0).sum()),
                "stage069_event_count_sum": int(
                    pd.to_numeric(group["stage069_event_count"], errors="coerce").fillna(0).sum()
                ),
                "stage069_reentry_count_sum": int(
                    pd.to_numeric(group["stage069_reentry_count"], errors="coerce").fillna(0).sum()
                ),
                "stage069_retry_failed_count_sum": int(
                    pd.to_numeric(group["stage069_retry_failed_count"], errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _delta_vs_baseline(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["version"].eq(BASELINE)].set_index("requested_start_month")
    rows: list[dict[str, Any]] = []
    for version in (C1_NO_REENTRY, C2_DAILY_REENTRY):
        group = summary[summary["version"].eq(version)].copy()
        for _, row in group.iterrows():
            start = str(row["requested_start_month"])
            baseline = base.loc[start]
            rows.append(
                {
                    "version": version,
                    "variant_label": VARIANT_LABELS[version],
                    "requested_start_month": start,
                    "return_delta_pct": float(row["total_return_pct"] - baseline["total_return_pct"]),
                    "dd_delta_pct": float(row["max_dd_pct"] - baseline["max_dd_pct"]),
                    "underwater_delta_days": int(row["days_below_initial"] - baseline["days_below_initial"]),
                    "trade_count_delta": float(row["total_trade_count"] - baseline["total_trade_count"]),
                    "slippage_delta": float(row["total_slippage"] - baseline["total_slippage"]),
                    "base_return_pct": float(baseline["total_return_pct"]),
                    "variant_return_pct": float(row["total_return_pct"]),
                    "base_max_dd_pct": float(baseline["max_dd_pct"]),
                    "variant_max_dd_pct": float(row["max_dd_pct"]),
                }
            )
    return pd.DataFrame(rows)


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    return s069._event_summary(events)


def run_backtests() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    starts = _halfyear_starts()
    metadata = s069.s064.s901.s513._metadata()
    original_requested_end = s069.REQUESTED_END
    s069.REQUESTED_END = REQUESTED_END
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    event_frames: list[pd.DataFrame] = []
    total_runs = len(starts) * len(VARIANTS)
    run_index = 0
    try:
        if not s069.s064.CANDIDATE_AI_PATH.exists():
            print("[stage071] Stage062 candidate AI file missing; rebuilding AI file only", flush=True)
            s069.s064.s062.build_full_monthly_ai_file()
        with s069.s064.s062._patched_live_ai_path(s069.s064.CANDIDATE_AI_PATH):
            for start in starts:
                for variant in VARIANTS:
                    run_index += 1
                    print(
                        f"[stage071] run {run_index}/{total_runs} variant={variant} start={_date_text(start)} end={_date_text(REQUESTED_END)}",
                        flush=True,
                    )
                    curve, frames = s069._run_variant(metadata, variant, start)
                    curve = curve.copy()
                    curve["stage"] = STAGE
                    curve["model_tag"] = MODEL_TAG
                    curve["line_id"] = LINE_ID
                    curve["requested_end"] = _date_text(REQUESTED_END)
                    events = frames.get("stage069_events", pd.DataFrame()).copy()
                    if not events.empty:
                        events["stage"] = STAGE
                        events["model_tag"] = MODEL_TAG
                        events["line_id"] = LINE_ID
                        events["requested_end"] = _date_text(REQUESTED_END)
                        event_frames.append(events)
                    summary_row = s069._summary_from_curve(curve, events, variant, start)
                    summary_row["stage"] = STAGE
                    summary_row["model_tag"] = MODEL_TAG
                    summary_row["line_id"] = LINE_ID
                    summary_row["requested_end"] = _date_text(REQUESTED_END)
                    summary_row["trade_date_alignment_count"] = int(len(frames.get("trade_date_alignment", pd.DataFrame())))
                    summary_rows.append(summary_row)
                    curve_frames.append(curve)
    finally:
        s069.REQUESTED_END = original_requested_end

    summary = pd.DataFrame(summary_rows).sort_values(["requested_start", "version"]).reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    events = pd.concat(event_frames, ignore_index=True, sort=False) if event_frames else pd.DataFrame()
    return {
        "summary": summary,
        "variant_summary": _variant_summary(summary),
        "delta_vs_baseline": _delta_vs_baseline(summary),
        "curves": curves,
        "events": events,
        "event_summary": _event_summary(events),
    }


def plot_outputs(results: dict[str, pd.DataFrame]) -> None:
    summary = results["summary"].copy()
    curves = results["curves"].copy()
    delta = results["delta_vs_baseline"].copy()
    months = sorted(summary["requested_start_month"].astype(str).unique())

    fig, axes = plt.subplots(3, 1, figsize=(18, 14), sharex=False, constrained_layout=True)
    for ax, version in zip(axes, VARIANTS, strict=True):
        for start in months:
            data = curves[
                curves["version"].astype(str).eq(version) & curves["requested_start_month"].astype(str).eq(start)
            ].copy()
            data["date"] = pd.to_datetime(data["date"], errors="coerce")
            data = data.sort_values("date")
            if data.empty:
                continue
            ax.plot(data["date"], data["account_equity"], linewidth=1.0, label=start)
        ax.axhline(BASE_CAPITAL, color="#111827", linewidth=0.8, linestyle="--")
        ax.set_title(VARIANT_LABELS[version])
        ax.set_ylabel("account equity")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=5, loc="best")
    fig.savefig(CHART_EQUITY_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    for version in VARIANTS:
        data = summary[summary["version"].astype(str).eq(version)].sort_values("requested_start_month")
        axes[0].plot(
            data["requested_start_month"].astype(str),
            data["total_return_pct"],
            marker="o",
            linewidth=1.4,
            color=VARIANT_COLORS[version],
            label=VARIANT_LABELS[version],
        )
        axes[1].plot(
            data["requested_start_month"].astype(str),
            data["max_dd_pct"],
            marker="o",
            linewidth=1.4,
            color=VARIANT_COLORS[version],
            label=VARIANT_LABELS[version],
        )
    axes[0].axhline(0, color="#111827", linewidth=0.9, linestyle="--")
    axes[0].set_title("Half-year starts 2020-01 to 2026-01, end 2026-06-30: total return")
    axes[0].set_ylabel("return %")
    axes[1].set_title("Half-year starts 2020-01 to 2026-01, end 2026-06-30: max drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].tick_params(axis="x", rotation=45)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_RETURN_DD_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(18, 9), sharex=True, constrained_layout=True)
    for version in (C1_NO_REENTRY, C2_DAILY_REENTRY):
        data = delta[delta["version"].eq(version)].sort_values("requested_start_month")
        axes[0].plot(
            data["requested_start_month"],
            data["return_delta_pct"],
            marker="o",
            linewidth=1.4,
            color=VARIANT_COLORS[version],
            label=VARIANT_LABELS[version],
        )
        axes[1].plot(
            data["requested_start_month"],
            data["dd_delta_pct"],
            marker="o",
            linewidth=1.4,
            color=VARIANT_COLORS[version],
            label=VARIANT_LABELS[version],
        )
    axes[0].axhline(0, color="#111827", linewidth=0.9, linestyle="--")
    axes[1].axhline(0, color="#111827", linewidth=0.9, linestyle="--")
    axes[0].set_title("Return delta vs Stage013 baseline")
    axes[0].set_ylabel("delta pp")
    axes[1].set_title("Max DD delta vs Stage013 baseline; positive means less severe DD")
    axes[1].set_ylabel("delta pp")
    axes[1].tick_params(axis="x", rotation=45)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_DELTA_PATH, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(18, 6), constrained_layout=True)
    for version in VARIANTS:
        data = summary[summary["version"].astype(str).eq(version)].sort_values("requested_start_month")
        ax.plot(
            data["requested_start_month"].astype(str),
            data["days_below_initial"],
            marker="o",
            linewidth=1.4,
            color=VARIANT_COLORS[version],
            label=VARIANT_LABELS[version],
        )
    ax.set_title("Half-year starts: days below initial capital")
    ax.set_ylabel("days")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_UNDERWATER_PATH, dpi=160)
    plt.close(fig)


def write_outputs(results: dict[str, pd.DataFrame]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["delta_vs_baseline"].to_csv(DELTA_PATH, index=False, encoding="utf-8-sig")
    results["curves"].to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    results["events"].to_csv(EVENTS_PATH, index=False, encoding="utf-8-sig")
    results["event_summary"].to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    plot_outputs(results)

    summary = results["summary"]
    variant_summary = results["variant_summary"]
    delta = results["delta_vs_baseline"]
    event_summary = results["event_summary"]
    months = sorted(summary["requested_start_month"].astype(str).unique())
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_mode": "day",
        "requested_start": REQUESTED_START.date().isoformat(),
        "latest_start": LATEST_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "halfyear_start_months": months,
        "start_count_per_arm": int(len(months)),
        "decision": "stage071_halfyear_2020_to_202606_confirms_stage069_not_promoted",
        "official_live_config_changed": False,
        "order_api_called": False,
        "ctp_connected": False,
        "pit_risk_note": (
            "Stage069 independent review found dynamic base/layer stop boundaries may use full daily bar before same-day "
            "minute scan; Stage071 keeps the same strategy logic for requested diagnostic curves."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "delta_vs_baseline": str(DELTA_PATH),
            "curves": str(CURVES_PATH),
            "events": str(EVENTS_PATH),
            "event_summary": str(EVENT_SUMMARY_PATH),
            "chart_equity": str(CHART_EQUITY_PATH),
            "chart_return_dd": str(CHART_RETURN_DD_PATH),
            "chart_delta": str(CHART_DELTA_PATH),
            "chart_underwater": str(CHART_UNDERWATER_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage071 Stage069 half-year starts 2020 to 2026-06",
                "",
                f"- generated_at: `{decision['generated_at']}`",
                f"- line_id: `{LINE_ID}`",
                "- current_mode: `day`",
                f"- starts: `{', '.join(months)}`",
                f"- end: `{REQUESTED_END.date()}`",
                "- live config changed: `false`; CTP connected: `false`; order API calls: `0`",
                "- external research judgment: stop trigger and execution price must be separated; this report does not add new execution assumptions.",
                "- PIT risk: Stage069 dynamic base/layer stop boundaries may use full daily bar before same-day minute scan; diagnostic only.",
                "",
                "## Variant Summary",
                "",
                _md_table(variant_summary),
                "",
                "## Half-Year Starts",
                "",
                _md_table(
                    summary[
                        [
                            "version",
                            "requested_start_month",
                            "actual_start",
                            "actual_end",
                            "total_return_pct",
                            "max_dd_pct",
                            "days_below_initial",
                            "last_below_initial",
                            "total_trade_count",
                            "total_slippage",
                            "stage069_event_count",
                            "stage069_reentry_count",
                            "stage069_retry_failed_count",
                        ]
                    ],
                    max_rows=60,
                ),
                "",
                "## Delta Vs Baseline",
                "",
                _md_table(delta, max_rows=60),
                "",
                "## Event Summary",
                "",
                _md_table(event_summary, max_rows=80),
                "",
                "## Decision",
                "",
                f"- decision: `{decision['decision']}`",
                "- conclusion: 2020-2026 half-year view keeps Stage069 research-only; C1 is selective and C2 remains weak.",
                "",
                "## Outputs",
                "",
                *[f"- {key}: `{path}`" for key, path in decision["outputs"].items()],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage071_stage069_halfyear_2020_to_202606.md"
    base = variant_summary[variant_summary["version"].eq(BASELINE)].iloc[0]
    c1 = variant_summary[variant_summary["version"].eq(C1_NO_REENTRY)].iloc[0]
    c2 = variant_summary[variant_summary["version"].eq(C2_DAILY_REENTRY)].iloc[0]
    stage_path.write_text(
        "\n".join(
            [
                "# Stage071 Stage069 half-year starts 2020 to 2026-06",
                "",
                f"- line_id：`{LINE_ID}`",
                "- 当前模式：day",
                f"- 记录时间：{decision['generated_at']}",
                f"- 工作区：`{ROOT}`",
                "- 是否重要突破：否；这是 Stage069 三臂 2020 起逐半年诊断视图，不是新 alpha 或新执行候选",
                "- 是否触发A/B：否；结论仍是不晋级",
                "",
                "## 外部调研与判断",
                "",
                "- Backtrader/CME stop-order 资料支持触发价与成交价分离；本阶段不新增成交假设，只按用户指定起点和终点补跑。",
                "- 独立审计已指出 Stage069 base/layer 动态保护线存在当日日K后验口径风险；本阶段资金曲线仅作诊断。",
                "",
                "## 本次变更",
                "",
                f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
                "- 修改正式入口：无",
                "- 删除文件：无",
                "- 新增参数：无；只固定起点序列和终点日期",
                "- 修改正式参数：无",
                "- 删除参数：无",
                "",
                "## 回测参数",
                "",
                f"- 起点：`{', '.join(months)}`",
                "- 终点：`2026-06-30`",
                "- 资金：`150,000`",
                "- 对照臂：A Stage013 baseline；C1 全周期动态保护线分钟止损不重进；C2 全周期动态保护线分钟止损、每天最多一次重进",
                "",
                "## 结果摘要",
                "",
                f"- A baseline：正收益 `{int(base['positive_count'])}/{int(base['start_count'])}`，最小/中位收益 `{float(base['min_return_pct']):.4f}%/{float(base['median_return_pct']):.4f}%`，最差回撤 `{float(base['worst_dd_pct']):.4f}%`，最长水下 `{int(base['max_days_below_initial'])}` 天。",
                f"- C1 no reentry：正收益 `{int(c1['positive_count'])}/{int(c1['start_count'])}`，最小/中位收益 `{float(c1['min_return_pct']):.4f}%/{float(c1['median_return_pct']):.4f}%`，最差回撤 `{float(c1['worst_dd_pct']):.4f}%`，最长水下 `{int(c1['max_days_below_initial'])}` 天。",
                f"- C2 daily reentry：正收益 `{int(c2['positive_count'])}/{int(c2['start_count'])}`，最小/中位收益 `{float(c2['min_return_pct']):.4f}%/{float(c2['median_return_pct']):.4f}%`，最差回撤 `{float(c2['worst_dd_pct']):.4f}%`，最长水下 `{int(c2['max_days_below_initial'])}` 天。",
                "",
                "## 统计口径 Review",
                "",
                "- 本阶段补跑三臂 `13` 个半年起点，共 `39` 条 true-engine 曲线。",
                "- 曲线完整性按 `version/requested_start_month` 审计，要求每臂 `13` 个起点且实际终点一致为 `2026-06-30`。",
                "- Stage069 的动态 stop PIT 风险仍然存在，因此图表只用于比较，不用于晋级。",
                "",
                "## 结论",
                "",
                "- 决策：`stage071_halfyear_2020_to_202606_confirms_stage069_not_promoted`",
                "- 原因：2020 起点扩展后仍不能支持 Stage069 晋级；C1 是局部收益增强但左尾/回撤不稳，C2 仍弱。",
                "",
                "## 后续规划和 TODO",
                "",
                "- 不继续同日重进形状。",
                "- 若继续研究日内止损，应新开 PIT-correct 版本：分钟级顺序更新，或只使用开盘前已知保护线。",
                "",
                "## 过拟合反思",
                "",
                "- 运行前：否。起点是用户指定的逐半年序列，终点固定为 2026-06-30，不新增筛选阈值或救参。",
                "- 运行后：否。结果来自完整三臂半年起点补跑，没有按收益挑月份。",
                "",
                "## 继续价值反思",
                "",
                "- 运行前：有。2020 起点能补齐你想看的长周期资金曲线。",
                "- 运行后：有，但价值是确认不晋级和指导下一步做 PIT-correct 慢确认/资金层，而不是继续当前 Stage069。",
                "",
                "## 输出",
                "",
                *[f"- {key}: `{path}`" for key, path in decision["outputs"].items()],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return stage_path


def main() -> None:
    print("[stage071] run Stage069 half-year starts 2020 to 2026-06", flush=True)
    results = run_backtests()
    stage_path = write_outputs(results)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)
    print(json.dumps(_json_safe({"variant_summary": results["variant_summary"].to_dict(orient="records")}), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

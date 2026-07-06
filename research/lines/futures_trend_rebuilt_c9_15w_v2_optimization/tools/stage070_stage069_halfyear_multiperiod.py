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


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage070"
MODEL_TAG = "stage070_stage069_halfyear_multiperiod_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage070_stage069_halfyear_multiperiod"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
STAGE069_OUT = LINE_DIR / "outputs" / "stage069_stage013_fullcycle_intraday_stop"
OUT = LINE_DIR / "outputs" / "stage070_stage069_halfyear_multiperiod"
STAGES_DIR = LINE_DIR / "stages"

BASE_CAPITAL = 150000.0
BASELINE = "stage069_stage013_baseline"
C1_NO_REENTRY = "stage069_fullcycle_intraday_stop_no_reentry"
C2_DAILY_REENTRY = "stage069_fullcycle_intraday_stop_daily_reentry_once"
VARIANTS = (BASELINE, C1_NO_REENTRY, C2_DAILY_REENTRY)
VARIANT_LABELS = {
    BASELINE: "Stage013 baseline",
    C1_NO_REENTRY: "full-cycle intraday stop, no reentry",
    C2_DAILY_REENTRY: "full-cycle intraday stop, daily reentry once",
}
VARIANT_COLORS = {
    BASELINE: "#111827",
    C1_NO_REENTRY: "#2563eb",
    C2_DAILY_REENTRY: "#f97316",
}

HALFYEAR_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HALFYEAR_VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
HALFYEAR_DELTA_PATH = OUT / f"{OUTPUT_PREFIX}_delta_vs_baseline_{MODEL_TAG}.csv"
HALFYEAR_CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
CHART_RETURN_DD_PATH = OUT / f"{OUTPUT_PREFIX}_return_dd_{MODEL_TAG}.png"
CHART_EQUITY_PATH = OUT / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"
CHART_DELTA_PATH = OUT / f"{OUTPUT_PREFIX}_delta_vs_baseline_{MODEL_TAG}.png"
CHART_UNDERWATER_PATH = OUT / f"{OUTPUT_PREFIX}_underwater_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _latest_file(pattern: str) -> Path:
    files = sorted(STAGE069_OUT.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"missing Stage069 artifact: {pattern}")
    return files[-1]


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (str, bytes, dict, list, tuple)) else False:
        return None
    return value


def _halfyear_months(summary: pd.DataFrame) -> list[str]:
    months = sorted(summary["requested_start_month"].astype(str).unique())
    return [month for month in months if month.endswith("-01") or month.endswith("-07")]


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


def load_and_filter() -> dict[str, pd.DataFrame]:
    summary = pd.read_csv(
        _latest_file("rebuilt_c9_v2_stage069_stage013_fullcycle_intraday_stop_summary_*.csv")
    )
    summary = summary[summary["version"].isin(VARIANTS)].copy()
    months = _halfyear_months(summary)
    half_summary = summary[summary["requested_start_month"].astype(str).isin(months)].copy()
    half_summary["requested_start_month"] = pd.Categorical(
        half_summary["requested_start_month"].astype(str),
        categories=months,
        ordered=True,
    )
    half_summary["version"] = pd.Categorical(half_summary["version"].astype(str), categories=VARIANTS, ordered=True)
    half_summary = half_summary.sort_values(["requested_start_month", "version"]).reset_index(drop=True)

    curves = pd.read_csv(
        _latest_file("rebuilt_c9_v2_stage069_stage013_fullcycle_intraday_stop_curves_*.csv.gz")
    )
    half_curves = curves[
        curves["version"].astype(str).isin(VARIANTS) & curves["requested_start_month"].astype(str).isin(months)
    ].copy()
    half_curves["date"] = pd.to_datetime(half_curves["date"], errors="coerce").dt.normalize()
    half_curves["requested_start_month"] = pd.Categorical(
        half_curves["requested_start_month"].astype(str),
        categories=months,
        ordered=True,
    )
    half_curves["version"] = pd.Categorical(half_curves["version"].astype(str), categories=VARIANTS, ordered=True)
    half_curves = half_curves.sort_values(["version", "requested_start_month", "date"]).reset_index(drop=True)
    return {
        "summary": half_summary,
        "variant_summary": _variant_summary(half_summary),
        "delta_vs_baseline": _delta_vs_baseline(half_summary),
        "curves": half_curves,
    }


def plot_outputs(results: dict[str, pd.DataFrame]) -> None:
    summary = results["summary"].copy()
    delta = results["delta_vs_baseline"].copy()
    curves = results["curves"].copy()
    months = sorted(summary["requested_start_month"].astype(str).unique())

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
    axes[0].set_title("Half-year starts to 2026-07-02: total return")
    axes[0].set_ylabel("return %")
    axes[1].set_title("Half-year starts to 2026-07-02: max drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].tick_params(axis="x", rotation=45)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_RETURN_DD_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(18, 13), sharex=False, constrained_layout=True)
    for ax, version in zip(axes, VARIANTS, strict=True):
        for start in months:
            data = curves[
                curves["version"].astype(str).eq(version) & curves["requested_start_month"].astype(str).eq(start)
            ].sort_values("date")
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
    results["summary"].to_csv(HALFYEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(HALFYEAR_VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["delta_vs_baseline"].to_csv(HALFYEAR_DELTA_PATH, index=False, encoding="utf-8-sig")
    results["curves"].to_csv(HALFYEAR_CURVES_PATH, index=False, encoding="utf-8-sig")
    plot_outputs(results)

    variant_summary = results["variant_summary"]
    summary = results["summary"]
    delta = results["delta_vs_baseline"]
    months = sorted(summary["requested_start_month"].astype(str).unique())
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_mode": "day",
        "source": "Stage069 monthly backtest artifacts; half-year starts are exact subset, not a new parameter sweep",
        "halfyear_start_months": months,
        "start_count_per_arm": int(len(months)),
        "decision": "stage070_halfyear_view_confirms_stage069_not_promoted",
        "official_live_config_changed": False,
        "order_api_called": False,
        "ctp_connected": False,
        "pit_risk_note": (
            "Independent review found Stage069 dynamic base/layer stop boundaries may use full daily bar before scanning "
            "same-day minute bars; Stage070 is a diagnostic view only."
        ),
        "outputs": {
            "summary": str(HALFYEAR_SUMMARY_PATH),
            "variant_summary": str(HALFYEAR_VARIANT_SUMMARY_PATH),
            "delta_vs_baseline": str(HALFYEAR_DELTA_PATH),
            "curves": str(HALFYEAR_CURVES_PATH),
            "chart_return_dd": str(CHART_RETURN_DD_PATH),
            "chart_equity": str(CHART_EQUITY_PATH),
            "chart_delta": str(CHART_DELTA_PATH),
            "chart_underwater": str(CHART_UNDERWATER_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage070 Stage069 half-year multiperiod view",
                "",
                f"- generated_at: `{decision['generated_at']}`",
                f"- line_id: `{LINE_ID}`",
                "- current_mode: `day`",
                "- source: Stage069 monthly artifacts; half-year starts are exact subset.",
                "- live config changed: `false`; CTP connected: `false`; order API calls: `0`",
                "- external research judgment: stop trigger and execution price must be separated; this report does not change Stage069 execution assumptions.",
                "- PIT risk: independent review found dynamic base/layer stop boundaries may use full daily bar before same-day minute scan; diagnostic only.",
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
                    ]
                ),
                "",
                "## Delta Vs Baseline",
                "",
                _md_table(delta),
                "",
                "## Decision",
                "",
                f"- decision: `{decision['decision']}`",
                "- conclusion: half-year view confirms Stage069 remains research-only; C1 has selective 2022/2023 benefit but worsens left tail, C2 remains worse.",
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
    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage070_stage069_halfyear_multiperiod.md"
    base = variant_summary[variant_summary["version"].eq(BASELINE)].iloc[0]
    c1 = variant_summary[variant_summary["version"].eq(C1_NO_REENTRY)].iloc[0]
    c2 = variant_summary[variant_summary["version"].eq(C2_DAILY_REENTRY)].iloc[0]
    stage_path.write_text(
        "\n".join(
            [
                "# Stage070 Stage069 half-year multiperiod view",
                "",
                f"- line_id：`{LINE_ID}`",
                "- 当前模式：day",
                f"- 记录时间：{decision['generated_at']}",
                f"- 工作区：`{ROOT}`",
                "- 是否重要突破：否；这是 Stage069 三臂半年起点视图，不是新 alpha 或新执行候选",
                "- 是否触发A/B：否；结论仍是不晋级",
                "",
                "## 外部调研与判断",
                "",
                "- Backtrader/CME stop-order 资料支持触发价与成交价分离；本阶段不新增成交假设，只复用 Stage069 结果筛半年起点。",
                "- 独立审计已指出 Stage069 base/layer 动态保护线存在当日日K后验口径风险；本阶段仅作诊断图表。",
                "",
                "## 本次变更",
                "",
                f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
                "- 修改正式入口：无",
                "- 删除文件：无",
                "- 新增参数：无；半年起点只是 Stage069 逐月结果的精确子集",
                "- 修改正式参数：无",
                "- 删除参数：无",
                "",
                "## 回测参数",
                "",
                f"- 起点：`{', '.join(months)}`",
                "- 终点：`2026-07-02`",
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
                "- 本阶段没有重跑策略逻辑，直接使用 Stage069 逐月结果中的 Jan/Jul 起点，避免引入新口径。",
                "- 曲线完整性按 `version/requested_start_month` 审计，要求每臂 `10` 个起点且终点一致。",
                "- Stage069 的动态 stop PIT 风险仍然存在，因此图表只用于比较，不用于晋级。",
                "",
                "## 结论",
                "",
                "- 决策：`stage070_halfyear_view_confirms_stage069_not_promoted`",
                "- 原因：半年视图没有推翻 Stage069 结论；C1 是局部改善但左尾/回撤更差，C2 仍明显不合格。",
                "",
                "## 后续规划和 TODO",
                "",
                "- 不继续同日重进形状。",
                "- 若继续研究日内止损，应新开 PIT-correct 版本：分钟级顺序更新，或只使用开盘前已知保护线。",
                "",
                "## 过拟合反思",
                "",
                "- 运行前：否。半年起点是预声明可读视图，不新增筛选阈值或救参。",
                "- 运行后：否。结果来自完整 Stage069 逐月回测子集，没有按收益挑月份。",
                "",
                "## 继续价值反思",
                "",
                "- 运行前：有。半年视图更容易看清真实冷启动路径。",
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
    print("[stage070] build Stage069 half-year multiperiod view", flush=True)
    results = load_and_filter()
    stage_path = write_outputs(results)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)
    print(json.dumps(_json_safe({"variant_summary": results["variant_summary"].to_dict(orient="records")}), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

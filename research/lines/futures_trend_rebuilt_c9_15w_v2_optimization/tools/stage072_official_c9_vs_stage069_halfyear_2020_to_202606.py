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
STAGE = "Stage072"
MODEL_TAG = "stage072_official_c9_vs_stage069_halfyear_2020_to_202606_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage072_official_c9_vs_stage069_halfyear_2020_to_202606"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
STAGE053_OUT = LINE_DIR / "outputs" / "stage053_valuable_versions_halfyear_curves"
STAGE071_OUT = LINE_DIR / "outputs" / "stage071_stage069_halfyear_2020_to_202606"
OUT = LINE_DIR / "outputs" / "stage072_official_c9_vs_stage069_halfyear_2020_to_202606"
STAGES_DIR = LINE_DIR / "stages"

OFFICIAL = "Official C9/15w Stage847"
STAGE013 = "stage069_stage013_baseline"
C1_NO_REENTRY = "stage069_fullcycle_intraday_stop_no_reentry"
C2_DAILY_REENTRY = "stage069_fullcycle_intraday_stop_daily_reentry_once"
VARIANTS = (OFFICIAL, STAGE013, C1_NO_REENTRY, C2_DAILY_REENTRY)
VARIANT_LABELS = {
    OFFICIAL: "Official C9/15w Stage847",
    STAGE013: "Stage013 baseline (research)",
    C1_NO_REENTRY: "Stage069 no reentry",
    C2_DAILY_REENTRY: "Stage069 daily reentry once",
}
VARIANT_COLORS = {
    OFFICIAL: "#111827",
    STAGE013: "#6b7280",
    C1_NO_REENTRY: "#2563eb",
    C2_DAILY_REENTRY: "#f97316",
}
BASE_CAPITAL = 150000.0
REQUESTED_END = "2026-06-30"

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
DELTA_PATH = OUT / f"{OUTPUT_PREFIX}_delta_vs_official_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
CHART_EQUITY_PATH = OUT / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"
CHART_RETURN_DD_PATH = OUT / f"{OUTPUT_PREFIX}_return_dd_{MODEL_TAG}.png"
CHART_DELTA_PATH = OUT / f"{OUTPUT_PREFIX}_delta_vs_official_{MODEL_TAG}.png"
CHART_FOCUS_RECENT_PATH = OUT / f"{OUTPUT_PREFIX}_equity_curves_2021_07_plus_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _target_months() -> list[str]:
    return [pd.Timestamp(item).strftime("%Y-%m") for item in pd.date_range("2020-01-01", "2026-01-01", freq="6MS")]


def _read_official() -> tuple[pd.DataFrame, pd.DataFrame]:
    months = _target_months()
    curves = pd.read_csv(
        STAGE053_OUT / "rebuilt_c9_v2_stage053_halfyear_curves_stage053_valuable_versions_halfyear_curves_v1.csv.gz"
    )
    curves = curves[
        curves["version"].eq(OFFICIAL)
        & curves["requested_start_month"].astype(str).isin(months)
        & pd.to_datetime(curves["date"], errors="coerce").le(pd.Timestamp(REQUESTED_END))
    ].copy()
    curves.rename(columns={"equity": "account_equity"}, inplace=True)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["version_label"] = VARIANT_LABELS[OFFICIAL]
    curves["source_type"] = "official_true_engine"
    curves["stage"] = STAGE
    curves["model_tag"] = MODEL_TAG
    curves["line_id"] = LINE_ID

    rows: list[dict[str, Any]] = []
    for start, group in curves.groupby("requested_start_month", sort=True):
        frame = group.sort_values("date")
        equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
        peak = equity.cummax()
        drawdown = (equity / peak - 1.0) * 100.0
        below = equity < BASE_CAPITAL - 1e-9
        below_dates = frame.loc[below, "date"]
        rows.append(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "version": OFFICIAL,
                "variant_label": VARIANT_LABELS[OFFICIAL],
                "requested_start_month": str(start),
                "actual_start": frame["date"].iloc[0].date().isoformat(),
                "actual_end": frame["date"].iloc[-1].date().isoformat(),
                "account_capital": BASE_CAPITAL,
                "end_equity": float(equity.iloc[-1]),
                "total_return_pct": float((equity.iloc[-1] / BASE_CAPITAL - 1.0) * 100.0),
                "max_dd_pct": float(drawdown.min()),
                "days_below_initial": int(below.sum()),
                "last_below_initial": below_dates.iloc[-1].date().isoformat() if not below_dates.empty else "",
                "total_trade_count": np.nan,
                "total_slippage": np.nan,
            }
        )
    return curves, pd.DataFrame(rows)


def _read_stage071() -> tuple[pd.DataFrame, pd.DataFrame]:
    months = _target_months()
    curves = pd.read_csv(
        STAGE071_OUT
        / "rebuilt_c9_v2_stage071_stage069_halfyear_2020_to_202606_curves_stage071_stage069_halfyear_2020_to_202606_v1.csv.gz"
    )
    curves = curves[
        curves["version"].astype(str).isin((STAGE013, C1_NO_REENTRY, C2_DAILY_REENTRY))
        & curves["requested_start_month"].astype(str).isin(months)
    ].copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["version_label"] = curves["version"].map(VARIANT_LABELS)
    curves["source_type"] = "stage071_true_engine"
    curves["stage"] = STAGE
    curves["model_tag"] = MODEL_TAG
    curves["line_id"] = LINE_ID

    summary = pd.read_csv(
        STAGE071_OUT
        / "rebuilt_c9_v2_stage071_stage069_halfyear_2020_to_202606_summary_stage071_stage069_halfyear_2020_to_202606_v1.csv"
    )
    summary = summary[
        summary["version"].astype(str).isin((STAGE013, C1_NO_REENTRY, C2_DAILY_REENTRY))
        & summary["requested_start_month"].astype(str).isin(months)
    ].copy()
    summary["stage"] = STAGE
    summary["model_tag"] = MODEL_TAG
    summary["line_id"] = LINE_ID
    summary["variant_label"] = summary["version"].map(VARIANT_LABELS)
    return curves, summary


def _variant_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version in VARIANTS:
        group = summary[summary["version"].astype(str).eq(version)].copy()
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
            }
        )
    return pd.DataFrame(rows)


def _delta_vs_official(summary: pd.DataFrame) -> pd.DataFrame:
    official = summary[summary["version"].eq(OFFICIAL)].set_index("requested_start_month")
    rows: list[dict[str, Any]] = []
    for version in (STAGE013, C1_NO_REENTRY, C2_DAILY_REENTRY):
        group = summary[summary["version"].eq(version)].copy()
        for _, row in group.iterrows():
            start = str(row["requested_start_month"])
            base = official.loc[start]
            rows.append(
                {
                    "version": version,
                    "variant_label": VARIANT_LABELS[version],
                    "requested_start_month": start,
                    "return_delta_pct": float(row["total_return_pct"] - base["total_return_pct"]),
                    "dd_delta_pct": float(row["max_dd_pct"] - base["max_dd_pct"]),
                    "end_equity_delta": float(row["end_equity"] - base["end_equity"]),
                    "end_equity_ratio": float(row["end_equity"] / base["end_equity"]) if float(base["end_equity"]) else np.nan,
                    "underwater_delta_days": int(row["days_below_initial"] - base["days_below_initial"]),
                    "official_return_pct": float(base["total_return_pct"]),
                    "variant_return_pct": float(row["total_return_pct"]),
                    "official_max_dd_pct": float(base["max_dd_pct"]),
                    "variant_max_dd_pct": float(row["max_dd_pct"]),
                }
            )
    return pd.DataFrame(rows)


def build() -> dict[str, pd.DataFrame]:
    official_curves, official_summary = _read_official()
    stage071_curves, stage071_summary = _read_stage071()
    curves = pd.concat([official_curves, stage071_curves], ignore_index=True, sort=False)
    summary = pd.concat([official_summary, stage071_summary], ignore_index=True, sort=False)
    months = _target_months()
    summary["requested_start_month"] = pd.Categorical(
        summary["requested_start_month"].astype(str), categories=months, ordered=True
    )
    summary["version"] = pd.Categorical(summary["version"].astype(str), categories=VARIANTS, ordered=True)
    summary = summary.sort_values(["requested_start_month", "version"]).reset_index(drop=True)
    curves["requested_start_month"] = pd.Categorical(
        curves["requested_start_month"].astype(str), categories=months, ordered=True
    )
    curves["version"] = pd.Categorical(curves["version"].astype(str), categories=VARIANTS, ordered=True)
    curves = curves.sort_values(["version", "requested_start_month", "date"]).reset_index(drop=True)
    return {
        "summary": summary,
        "variant_summary": _variant_summary(summary),
        "delta_vs_official": _delta_vs_official(summary),
        "curves": curves,
    }


def plot_outputs(results: dict[str, pd.DataFrame]) -> None:
    summary = results["summary"].copy()
    curves = results["curves"].copy()
    delta = results["delta_vs_official"].copy()
    months = _target_months()

    fig, axes = plt.subplots(4, 1, figsize=(18, 18), sharex=False, constrained_layout=True)
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

    focus_months = [month for month in months if month >= "2021-07"]
    fig, axes = plt.subplots(4, 1, figsize=(18, 18), sharex=False, constrained_layout=True)
    for ax, version in zip(axes, VARIANTS, strict=True):
        for start in focus_months:
            data = curves[
                curves["version"].astype(str).eq(version) & curves["requested_start_month"].astype(str).eq(start)
            ].copy()
            data["date"] = pd.to_datetime(data["date"], errors="coerce")
            data = data.sort_values("date")
            if data.empty:
                continue
            ax.plot(data["date"], data["account_equity"], linewidth=1.0, label=start)
        ax.axhline(BASE_CAPITAL, color="#111827", linewidth=0.8, linestyle="--")
        ax.set_title(f"{VARIANT_LABELS[version]} - starts 2021-07+")
        ax.set_ylabel("account equity")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=5, loc="best")
    fig.savefig(CHART_FOCUS_RECENT_PATH, dpi=160)
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
    for version in (STAGE013, C1_NO_REENTRY, C2_DAILY_REENTRY):
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
            data["end_equity_ratio"],
            marker="o",
            linewidth=1.4,
            color=VARIANT_COLORS[version],
            label=VARIANT_LABELS[version],
        )
    axes[0].axhline(0, color="#111827", linewidth=0.9, linestyle="--")
    axes[1].axhline(1, color="#111827", linewidth=0.9, linestyle="--")
    axes[0].set_title("Return delta vs Official C9")
    axes[0].set_ylabel("delta pp")
    axes[1].set_title("End equity ratio vs Official C9")
    axes[1].set_ylabel("ratio")
    axes[1].tick_params(axis="x", rotation=45)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_DELTA_PATH, dpi=160)
    plt.close(fig)


def write_outputs(results: dict[str, pd.DataFrame]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["delta_vs_official"].to_csv(DELTA_PATH, index=False, encoding="utf-8-sig")
    results["curves"].to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    plot_outputs(results)
    summary = results["summary"]
    variant_summary = results["variant_summary"]
    delta = results["delta_vs_official"]
    months = _target_months()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_mode": "day",
        "start_months": months,
        "requested_end": REQUESTED_END,
        "decision": "stage072_official_c9_added_as_comparison_not_strategy_change",
        "official_live_config_changed": False,
        "order_api_called": False,
        "ctp_connected": False,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "delta_vs_official": str(DELTA_PATH),
            "curves": str(CURVES_PATH),
            "chart_equity": str(CHART_EQUITY_PATH),
            "chart_focus_recent": str(CHART_FOCUS_RECENT_PATH),
            "chart_return_dd": str(CHART_RETURN_DD_PATH),
            "chart_delta": str(CHART_DELTA_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage072 Official C9 vs Stage069 half-year comparison",
                "",
                f"- generated_at: `{decision['generated_at']}`",
                f"- line_id: `{LINE_ID}`",
                "- current_mode: `day`",
                f"- starts: `{', '.join(months)}`",
                f"- end: `{REQUESTED_END}`",
                "- live config changed: `false`; CTP connected: `false`; order API calls: `0`",
                "- source: Official C9 curves from Stage053; Stage013/Stage069 curves from Stage071.",
                "- PIT risk: Stage069 dynamic base/layer stop boundaries may use full daily bar before same-day minute scan; these branches remain diagnostic only.",
                "",
                "## Variant Summary",
                "",
                _md_table(variant_summary),
                "",
                "## Per Start Summary",
                "",
                _md_table(
                    summary[
                        [
                            "version",
                            "requested_start_month",
                            "actual_start",
                            "actual_end",
                            "end_equity",
                            "total_return_pct",
                            "max_dd_pct",
                            "days_below_initial",
                            "last_below_initial",
                        ]
                    ],
                    max_rows=80,
                ),
                "",
                "## Delta Vs Official",
                "",
                _md_table(delta, max_rows=60),
                "",
                "## Decision",
                "",
                f"- decision: `{decision['decision']}`",
                "- conclusion: adding official C9 clarifies that Stage013/Stage069 research branches are not the formal high-right-tail C9 baseline.",
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
    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage072_official_c9_vs_stage069_halfyear_2020_to_202606.md"
    official = variant_summary[variant_summary["version"].eq(OFFICIAL)].iloc[0]
    stage013 = variant_summary[variant_summary["version"].eq(STAGE013)].iloc[0]
    c1 = variant_summary[variant_summary["version"].eq(C1_NO_REENTRY)].iloc[0]
    c2 = variant_summary[variant_summary["version"].eq(C2_DAILY_REENTRY)].iloc[0]
    stage_path.write_text(
        "\n".join(
            [
                "# Stage072 Official C9 vs Stage069 half-year comparison",
                "",
                f"- line_id：`{LINE_ID}`",
                "- 当前模式：day",
                f"- 记录时间：{decision['generated_at']}",
                f"- 工作区：`{ROOT}`",
                "- 是否重要突破：否；这是把正式 C9 放入同一张半年对比图，不是新策略或新执行候选",
                "- 是否触发A/B：否；只做只读对齐与绘图",
                "",
                "## 调研与判断",
                "",
                "- 本次本地调研确认：Stage053 已有 Official C9/15w Stage847 逐半年曲线，终点 `2026-06-30`；Stage071 已有三条 Stage069 研究分支同终点曲线。",
                "- 我的判断：不应再重跑正式 C9；直接合并既有正式曲线和研究曲线，能避免重复口径误差。",
                "- Stage069 的动态 stop PIT 风险仍然存在，研究分支仅作诊断；正式 C9 才是当前线上高右尾基准。",
                "",
                "## 本次变更",
                "",
                f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
                "- 修改正式入口：无",
                "- 删除文件：无",
                "- 新增参数：无",
                "- 修改正式参数：无",
                "- 删除参数：无",
                "",
                "## 对比口径",
                "",
                f"- 起点：`{', '.join(months)}`",
                f"- 终点：`{REQUESTED_END}`",
                "- 资金：`150,000`",
                "- 对比版本：Official C9/15w Stage847、Stage013 baseline、Stage069 no reentry、Stage069 daily reentry once",
                "",
                "## 结果摘要",
                "",
                f"- Official C9：正收益 `{int(official['positive_count'])}/{int(official['start_count'])}`，最小/中位/最高收益 `{float(official['min_return_pct']):.4f}%/{float(official['median_return_pct']):.4f}%/{float(official['max_return_pct']):.4f}%`，最差回撤 `{float(official['worst_dd_pct']):.4f}%`。",
                f"- Stage013 research：正收益 `{int(stage013['positive_count'])}/{int(stage013['start_count'])}`，最小/中位/最高收益 `{float(stage013['min_return_pct']):.4f}%/{float(stage013['median_return_pct']):.4f}%/{float(stage013['max_return_pct']):.4f}%`，最差回撤 `{float(stage013['worst_dd_pct']):.4f}%`。",
                f"- Stage069 no reentry：正收益 `{int(c1['positive_count'])}/{int(c1['start_count'])}`，最小/中位/最高收益 `{float(c1['min_return_pct']):.4f}%/{float(c1['median_return_pct']):.4f}%/{float(c1['max_return_pct']):.4f}%`，最差回撤 `{float(c1['worst_dd_pct']):.4f}%`。",
                f"- Stage069 daily reentry：正收益 `{int(c2['positive_count'])}/{int(c2['start_count'])}`，最小/中位/最高收益 `{float(c2['min_return_pct']):.4f}%/{float(c2['median_return_pct']):.4f}%/{float(c2['max_return_pct']):.4f}%`，最差回撤 `{float(c2['worst_dd_pct']):.4f}%`。",
                "",
                "## 结论",
                "",
                "- 决策：`stage072_official_c9_added_as_comparison_not_strategy_change`",
                "- 原因：加入正式 C9 后可以看清：Stage013/Stage069 研究分支不是正式 C9 高收益基准，不能用它们代表线上 C9。",
                "",
                "## 过拟合反思",
                "",
                "- 运行前：否。只合并既有曲线，不调参数。",
                "- 运行后：否。结果只是口径对齐，没有产生新的交易规则。",
                "",
                "## 继续价值反思",
                "",
                "- 运行前：有。能修正之前把 Stage013 baseline 误当正式 C9 的误解。",
                "- 运行后：有。后续研究应以 Official C9 为对照，而不是 Stage013 research baseline。",
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
    print("[stage072] combine Official C9 and Stage069 half-year curves", flush=True)
    results = build()
    stage_path = write_outputs(results)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)
    print(json.dumps(_json_safe({"variant_summary": results["variant_summary"].to_dict(orient="records")}), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

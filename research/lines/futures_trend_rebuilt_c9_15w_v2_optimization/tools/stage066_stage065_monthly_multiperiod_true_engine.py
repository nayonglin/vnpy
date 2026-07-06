from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
THIS_TOOLS_DIR = Path(__file__).resolve().parent
UPSTREAM_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
for candidate in (str(THIS_TOOLS_DIR), str(UPSTREAM_TOOLS_DIR), str(PORTFOLIO_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import stage064_stage013_reserve_topup_true_engine as s064
import stage065_stage013_30w_internal_reserve_release as s065


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage066"
MODEL_TAG = "stage066_stage065_monthly_multiperiod_true_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage066_stage065_monthly_multiperiod_true_engine"

REQUESTED_START = pd.Timestamp("2021-07-01")
REQUESTED_END = pd.Timestamp("2026-07-02")
LATEST_START = pd.Timestamp("2026-01-01")
BASE_TRADING_CAPITAL = float(s064.BASE_TRADING_CAPITAL)
RESERVE_CAPITAL = 150_000.0
TOTAL_INITIAL_CAPITAL = BASE_TRADING_CAPITAL + RESERVE_CAPITAL

VARIANTS = (
    "stage066_30w_idle_reserve_no_release",
    "stage066_30w_daily_floor_release",
    "stage066_30w_month_end_floor_release",
)
VARIANT_LABELS = {
    "stage066_30w_idle_reserve_no_release": "30w idle reserve, no release",
    "stage066_30w_daily_floor_release": "30w daily floor release",
    "stage066_30w_month_end_floor_release": "30w month-end floor release",
}
VARIANT_COLORS = {
    "stage066_30w_idle_reserve_no_release": "#6b7280",
    "stage066_30w_daily_floor_release": "#2563eb",
    "stage066_30w_month_end_floor_release": "#f97316",
}

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage066_stage065_monthly_multiperiod_true_engine"
STAGES_DIR = LINE_DIR / "stages"
BACK_LOG_PATH = ROOT / "back_log.md"

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
KEY_2022_2023_PATH = OUT / f"{OUTPUT_PREFIX}_key_2022_2023_months_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
CASHFLOW_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_cashflow_events_{MODEL_TAG}.csv.gz"
ACCOUNTING_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_accounting_audit_{MODEL_TAG}.csv"
CHART_VARIANT_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.png"
CHART_MONTHLY_PATH = OUT / f"{OUTPUT_PREFIX}_monthly_start_returns_{MODEL_TAG}.png"
CHART_UNDERWATER_PATH = OUT / f"{OUTPUT_PREFIX}_monthly_underwater_days_{MODEL_TAG}.png"
CHART_KEY_EQUITY_PATH = OUT / f"{OUTPUT_PREFIX}_key_month_equity_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s064._json_safe(value)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s064._drawdown_pct(equity)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _build_monthly_starts() -> list[pd.Timestamp]:
    starts = pd.date_range(REQUESTED_START, LATEST_START, freq="MS")
    return [pd.Timestamp(item).normalize() for item in starts]


def _run_live_stage013_idle(metadata: dict[str, Any], analysis_start: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s064.s013.s847.START
    original_end = s064.s013.s847.END
    original_minute_by_symbol = s064.s013.s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s064.s901._ensure_c9_minute_bars(metadata)
    try:
        s064.s013.s847.START = analysis_start.normalize()
        s064.s013.s847.END = REQUESTED_END.normalize()
        profile = s064.s013._stage013_profile(metadata)
        combined, frames = s064._run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        s064.s013.s847.START = original_start
        s064.s013.s847.END = original_end
        s064.s013.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol

    combined["account_capital"] = spec.capital.account_capital
    combined["c3_capital"] = spec.capital.c3_capital
    combined["profile"] = spec.profile
    for frame in frames.values():
        if frame.empty:
            continue
        frame["account_capital"] = spec.capital.account_capital
        frame["c3_capital"] = spec.capital.c3_capital
        frame["profile"] = spec.profile
    return combined, frames, spec


def _run_variant(metadata: dict[str, Any], variant: str, start: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    if variant == "stage066_30w_idle_reserve_no_release":
        combined, frames, _spec = _run_live_stage013_idle(metadata, start)
        curve = s064._apply_cashflow_to_curve(
            combined=combined,
            cashflow_events=pd.DataFrame(),
            daily_accounting=pd.DataFrame(),
            reserve_capital=RESERVE_CAPITAL,
        )
    elif variant == "stage066_30w_daily_floor_release":
        combined, frames, _spec = s064._run_live_stage064(metadata, start, REQUESTED_END, RESERVE_CAPITAL)
        curve = s064._apply_cashflow_to_curve(
            combined=combined,
            cashflow_events=frames.get("cashflow_events", pd.DataFrame()),
            daily_accounting=frames.get("daily_accounting", pd.DataFrame()),
            reserve_capital=RESERVE_CAPITAL,
        )
    elif variant == "stage066_30w_month_end_floor_release":
        combined, frames, _spec = s065._run_live_stage065_month_end(metadata, start, REQUESTED_END)
        curve = s064._apply_cashflow_to_curve(
            combined=combined,
            cashflow_events=frames.get("cashflow_events", pd.DataFrame()),
            daily_accounting=frames.get("daily_accounting", pd.DataFrame()),
            reserve_capital=RESERVE_CAPITAL,
        )
    else:
        raise ValueError(f"unknown variant: {variant}")

    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    curve["version"] = variant
    curve["variant_label"] = VARIANT_LABELS[variant]
    curve["reserve_capital"] = RESERVE_CAPITAL
    curve["requested_start"] = _date_text(start)
    curve["requested_start_month"] = _start_month_text(start)
    curve["requested_end"] = _date_text(REQUESTED_END)
    curve["days_since_start"] = np.arange(len(curve), dtype=int)
    for frame in frames.values():
        if frame.empty:
            continue
        frame["stage"] = STAGE
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
        frame["version"] = variant
        frame["requested_start"] = _date_text(start)
        frame["requested_start_month"] = _start_month_text(start)
        frame["requested_end"] = _date_text(REQUESTED_END)
    return curve, frames


def _summary_from_curve(curve: pd.DataFrame, variant: str, start: pd.Timestamp) -> dict[str, Any]:
    row = s065._summary_from_curve(curve, variant, start)
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "version": variant,
            "variant_label": VARIANT_LABELS[variant],
            "release_rule": variant,
            "requested_end": _date_text(REQUESTED_END),
        }
    )
    return row


def _variant_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version, group in summary.groupby("version", sort=False):
        total_ret = pd.to_numeric(group["total_account_return_pct"], errors="coerce")
        strategy_ret = pd.to_numeric(group["strategy_total_return_ex_cashflow_pct"], errors="coerce")
        total_dd = pd.to_numeric(group["total_account_max_dd_pct"], errors="coerce")
        underwater = pd.to_numeric(group["total_account_days_below_initial"], errors="coerce").fillna(0)
        rows.append(
            {
                "version": version,
                "variant_label": VARIANT_LABELS.get(version, version),
                "start_count": int(len(group)),
                "positive_total_account_count": int(total_ret.gt(0.0).sum()),
                "positive_strategy_count": int(strategy_ret.gt(0.0).sum()),
                "min_total_account_return_pct": float(total_ret.min()),
                "p10_total_account_return_pct": float(total_ret.quantile(0.10)),
                "median_total_account_return_pct": float(total_ret.median()),
                "max_total_account_return_pct": float(total_ret.max()),
                "worst_total_account_dd_pct": float(total_dd.min()),
                "median_total_account_dd_pct": float(total_dd.median()),
                "sum_total_account_days_below_initial": int(underwater.sum()),
                "max_total_account_days_below_initial": int(underwater.max()),
                "median_total_account_days_below_initial": float(underwater.median()),
                "max_external_cashflow_used": float(
                    pd.to_numeric(group["max_external_cashflow_used"], errors="coerce").fillna(0.0).max()
                ),
                "cashflow_event_count_sum": int(
                    pd.to_numeric(group["cashflow_event_count"], errors="coerce").fillna(0).sum()
                ),
                "total_trade_count_sum": float(pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0.0).sum()),
                "total_slippage_sum": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0.0).sum()),
                "audit_pass_count": int(pd.to_numeric(group["audit_pass"], errors="coerce").fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _year_summary(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    frame["start_year"] = frame["requested_start_month"].astype(str).str.slice(0, 4)
    rows: list[dict[str, Any]] = []
    for (version, year), group in frame.groupby(["version", "start_year"], sort=True):
        total_ret = pd.to_numeric(group["total_account_return_pct"], errors="coerce")
        total_dd = pd.to_numeric(group["total_account_max_dd_pct"], errors="coerce")
        underwater = pd.to_numeric(group["total_account_days_below_initial"], errors="coerce").fillna(0)
        rows.append(
            {
                "version": version,
                "start_year": year,
                "start_count": int(len(group)),
                "positive_total_account_count": int(total_ret.gt(0.0).sum()),
                "min_total_account_return_pct": float(total_ret.min()),
                "median_total_account_return_pct": float(total_ret.median()),
                "worst_total_account_dd_pct": float(total_dd.min()),
                "max_total_account_days_below_initial": int(underwater.max()),
                "median_total_account_days_below_initial": float(underwater.median()),
            }
        )
    return pd.DataFrame(rows)


def _key_2022_2023(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary[summary["requested_start_month"].astype(str).str.startswith(("2022-", "2023-"))].copy()
    columns = [
        "version",
        "requested_start_month",
        "total_account_return_pct",
        "total_account_max_dd_pct",
        "total_account_days_below_initial",
        "total_account_last_below_initial",
        "max_external_cashflow_used",
        "cashflow_event_count",
        "total_trade_count",
        "audit_pass",
    ]
    return frame[columns].sort_values(["requested_start_month", "version"]).reset_index(drop=True)


def run_backtests() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    if not s064.CANDIDATE_AI_PATH.exists():
        print("[stage066] Stage062 candidate AI file missing; rebuilding AI file only", flush=True)
        s064.s062.build_full_monthly_ai_file()

    starts = _build_monthly_starts()
    metadata = s064.s901.s513._metadata()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    cashflow_frames: list[pd.DataFrame] = []
    audit_rows: list[dict[str, Any]] = []
    total_runs = len(starts) * len(VARIANTS)

    run_index = 0
    with s064.s062._patched_live_ai_path(s064.CANDIDATE_AI_PATH):
        for start in starts:
            for variant in VARIANTS:
                run_index += 1
                print(
                    f"[stage066] run {run_index}/{total_runs} variant={variant} start={_date_text(start)}",
                    flush=True,
                )
                curve, frames = _run_variant(metadata, variant, start)
                summary = _summary_from_curve(curve, variant, start)
                summary_rows.append(summary)
                curve_frames.append(curve)
                audit_rows.append(
                    {
                        "version": variant,
                        "requested_start_month": _start_month_text(start),
                        **{key: value for key, value in summary.items() if key.endswith("_max_abs") or key == "audit_pass"},
                    }
                )
                cashflow = frames.get("cashflow_events", pd.DataFrame())
                if not cashflow.empty:
                    cashflow_frames.append(cashflow.copy())

    summary = pd.DataFrame(summary_rows).sort_values(["version", "requested_start"]).reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    cashflow_events = pd.concat(cashflow_frames, ignore_index=True, sort=False) if cashflow_frames else pd.DataFrame()
    audit = pd.DataFrame(audit_rows).sort_values(["version", "requested_start_month"]).reset_index(drop=True)
    return {
        "summary": summary,
        "variant_summary": _variant_summary(summary),
        "year_summary": _year_summary(summary),
        "key_2022_2023": _key_2022_2023(summary),
        "curves": curves,
        "cashflow_events": cashflow_events,
        "accounting_audit": audit,
    }


def _plot_outputs(summary: pd.DataFrame, variant_summary: pd.DataFrame, curves: pd.DataFrame) -> None:
    plot = variant_summary.copy()
    x = np.arange(len(plot))
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), constrained_layout=True)
    axes[0].bar(x - 0.2, plot["min_total_account_return_pct"], width=0.4, label="min return %", color="#ef4444")
    axes[0].bar(x + 0.2, plot["median_total_account_return_pct"], width=0.4, label="median return %", color="#22c55e")
    axes[0].axhline(0.0, color="#111827", linewidth=0.9)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(plot["variant_label"], rotation=15, ha="right")
    axes[0].set_title("Monthly starts: total-account return")
    axes[0].set_ylabel("return %")
    axes[0].legend(loc="best")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(x - 0.2, plot["worst_total_account_dd_pct"], width=0.4, label="worst DD %", color="#2563eb")
    axes[1].bar(x + 0.2, plot["max_total_account_days_below_initial"], width=0.4, label="max days below 300k", color="#f97316")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(plot["variant_label"], rotation=15, ha="right")
    axes[1].legend(loc="best")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_VARIANT_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    order = sorted(summary["requested_start_month"].astype(str).unique())
    for version in VARIANTS:
        data = summary[summary["version"].eq(version)].copy()
        data["requested_start_month"] = pd.Categorical(data["requested_start_month"].astype(str), categories=order, ordered=True)
        data = data.sort_values("requested_start_month")
        color = VARIANT_COLORS[version]
        axes[0].plot(
            data["requested_start_month"].astype(str),
            data["total_account_return_pct"],
            marker="o",
            linewidth=1.0,
            markersize=3,
            label=VARIANT_LABELS[version],
            color=color,
        )
        axes[1].plot(
            data["requested_start_month"].astype(str),
            data["total_account_max_dd_pct"],
            marker="o",
            linewidth=1.0,
            markersize=3,
            label=VARIANT_LABELS[version],
            color=color,
        )
    axes[0].axhline(0.0, color="#111827", linewidth=0.9, linestyle="--")
    axes[0].set_title("Monthly starts to 2026-07-02: total-account return")
    axes[0].set_ylabel("return %")
    axes[1].set_title("Monthly starts to 2026-07-02: total-account max drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].tick_params(axis="x", rotation=60)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_MONTHLY_PATH, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(18, 6), constrained_layout=True)
    for version in VARIANTS:
        data = summary[summary["version"].eq(version)].copy()
        data["requested_start_month"] = pd.Categorical(data["requested_start_month"].astype(str), categories=order, ordered=True)
        data = data.sort_values("requested_start_month")
        ax.plot(
            data["requested_start_month"].astype(str),
            data["total_account_days_below_initial"],
            marker="o",
            linewidth=1.0,
            markersize=3,
            label=VARIANT_LABELS[version],
            color=VARIANT_COLORS[version],
        )
    ax.set_title("Monthly starts: days below total initial capital 300k")
    ax.set_ylabel("days below 300k")
    ax.tick_params(axis="x", rotation=60)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_UNDERWATER_PATH, dpi=160)
    plt.close(fig)

    key_starts = ["2022-01", "2022-05", "2022-09", "2023-01", "2023-05", "2023-09"]
    fig, axes = plt.subplots(3, 2, figsize=(18, 14), sharex=False, constrained_layout=True)
    for ax, start in zip(axes.ravel(), key_starts, strict=False):
        for version in VARIANTS:
            frame = curves[
                curves["requested_start_month"].astype(str).eq(start) & curves["version"].astype(str).eq(version)
            ].sort_values("date")
            if frame.empty:
                continue
            ax.plot(frame["date"], frame["total_account_equity"], linewidth=1.0, color=VARIANT_COLORS[version], label=VARIANT_LABELS[version])
        ax.axhline(TOTAL_INITIAL_CAPITAL, color="#111827", linewidth=0.8, linestyle="--")
        ax.set_title(f"Total account equity start {start}")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, loc="best")
    fig.savefig(CHART_KEY_EQUITY_PATH, dpi=160)
    plt.close(fig)


def _decision(results: dict[str, pd.DataFrame]) -> dict[str, Any]:
    variant = results["variant_summary"].set_index("version")
    audit = results["accounting_audit"]
    residual_cols = [col for col in audit.columns if col.endswith("_max_abs") and not col.startswith("engine_")]
    max_residual = float(audit[residual_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).max().max())
    audit_pass_count = int(pd.to_numeric(audit["audit_pass"], errors="coerce").fillna(0).sum())

    month = variant.loc["stage066_30w_month_end_floor_release"]
    daily = variant.loc["stage066_30w_daily_floor_release"]
    idle = variant.loc["stage066_30w_idle_reserve_no_release"]
    decision_name = "stage066_monthly_multiperiod_keep_research_only"
    reason = (
        "逐月独立起点显示月末释放能改善不释放的正收益数量、中位收益和最长水下天数，"
        "但最小收益比不释放更差，且正收益数量和收益中位数仍弱于日级释放；"
        "日级释放收益更强但最差回撤更深，二者都没有解决最差回撤，因此先不晋级。"
    )
    if (
        audit_pass_count == len(audit)
        and float(month["positive_total_account_count"]) >= float(idle["positive_total_account_count"])
        and float(month["max_total_account_days_below_initial"]) < float(idle["max_total_account_days_below_initial"])
        and float(month["min_total_account_return_pct"]) > float(idle["min_total_account_return_pct"])
    ):
        decision_name = "stage066_month_end_release_capital_governance_candidate_needs_attribution"
        reason = (
            "月末释放在逐月起点上改善不释放基线的最小收益和最长水下天数，且会计校验全部通过；"
            "但相对日级释放收益效率不足、最差回撤未改善，晋级前必须做新增手数归因。"
        )

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_mode": "day",
        "start_frequency": "monthly",
        "requested_start": REQUESTED_START.date().isoformat(),
        "latest_start": LATEST_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "base_trading_capital": BASE_TRADING_CAPITAL,
        "reserve_capital": RESERVE_CAPITAL,
        "total_initial_capital": TOTAL_INITIAL_CAPITAL,
        "arms": list(VARIANTS),
        "start_count_per_arm": int(results["summary"]["requested_start_month"].nunique()),
        "accounting_audit_pass_count": audit_pass_count,
        "accounting_audit_row_count": int(len(audit)),
        "max_accounting_residual": max_residual,
        "decision": decision_name,
        "decision_reason": reason,
        "strategy_changed": True,
        "official_live_config_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "GIPS/TWR requires cashflow separation; pysystemtrade capital correction supports treating this as capital governance, not alpha."
        ),
        "overfit_reflection_before": (
            "否。只扩展逐月起点样本，固定 30w=15w交易袖+15w储备袖、固定日级/月末释放规则，不调金额、阈值或日期。"
        ),
        "overfit_reflection_after": (
            "否。逐月结果没有触发任何参数救援；如果后续按 2022/2023 个别月份改释放日或金额，才会转为过拟合。"
        ),
        "continue_value_before": (
            "有。逐半年样本不足以判断 2022/2023 启动月份的水下问题，必须扩成逐月独立起点。"
        ),
        "continue_value_after": (
            "有，但只作为资金治理继续；下一步应做新增手数/品种/月度归因，而不是继续 sweep 储备比例。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "year_summary": str(YEAR_SUMMARY_PATH),
            "key_2022_2023": str(KEY_2022_2023_PATH),
            "curves": str(CURVES_PATH),
            "cashflow_events": str(CASHFLOW_EVENTS_PATH),
            "accounting_audit": str(ACCOUNTING_AUDIT_PATH),
            "chart_variant": str(CHART_VARIANT_PATH),
            "chart_monthly": str(CHART_MONTHLY_PATH),
            "chart_underwater": str(CHART_UNDERWATER_PATH),
            "chart_key_equity": str(CHART_KEY_EQUITY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def write_records(decision: dict[str, Any], results: dict[str, pd.DataFrame]) -> Path:
    now = datetime.now()
    variant_summary = results["variant_summary"]
    year_summary = results["year_summary"]
    key = results["key_2022_2023"]
    audit = results["accounting_audit"]
    report_lines = [
        "# Stage066 Stage065 monthly multiperiod true-engine",
        "",
        f"- generated_at: `{decision['generated_at']}`",
        f"- line_id: `{LINE_ID}`",
        f"- start frequency: monthly `{REQUESTED_START.date()}` to `{LATEST_START.date()}`",
        f"- end: `{REQUESTED_END.date()}`",
        f"- AI file: `{s064.CANDIDATE_AI_PATH}`",
        "- live config changed: `false`; CTP connected: `false`; order API calls: `0`",
        "",
        "## Variant Summary",
        "",
        _md_table(variant_summary),
        "",
        "## Year Summary",
        "",
        _md_table(year_summary, max_rows=40),
        "",
        "## 2022-2023 Starts",
        "",
        _md_table(key, max_rows=80),
        "",
        "## Accounting Audit",
        "",
        f"- pass: `{decision['accounting_audit_pass_count']}/{decision['accounting_audit_row_count']}`",
        f"- max residual: `{decision['max_accounting_residual']:.8f}`",
        "",
        _md_table(audit.head(40), max_rows=40),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- reason: {decision['decision_reason']}",
        f"- overfit before: {decision['overfit_reflection_before']}",
        f"- overfit after: {decision['overfit_reflection_after']}",
        f"- continue before: {decision['continue_value_before']}",
        f"- continue after: {decision['continue_value_after']}",
        "",
        "## Outputs",
        "",
    ]
    for key_name, path in decision["outputs"].items():
        report_lines.append(f"- {key_name}: `{path}`")
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage066_stage065_monthly_multiperiod_true_engine.md"
    month = variant_summary[variant_summary["version"].eq("stage066_30w_month_end_floor_release")].iloc[0]
    daily = variant_summary[variant_summary["version"].eq("stage066_30w_daily_floor_release")].iloc[0]
    idle = variant_summary[variant_summary["version"].eq("stage066_30w_idle_reserve_no_release")].iloc[0]
    stage_lines = [
        "# Stage066 Stage065 monthly multiperiod true-engine",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 是否重要突破：否，资金治理扩样本审计；不是 alpha 突破",
        "- 是否触发A/B：是；资金/保证金治理层与候选部署相关，按 A vs C 口径记录",
        "",
        "## 外部调研与判断",
        "",
        "- GIPS/TWR 口径要求现金流与策略收益分离；本阶段总账户分母固定 300,000。",
        "- pysystemtrade capital correction 支持把资本变化作为资金治理，不把储备释放算作 alpha。",
        "- 本次判断：只扩逐月独立起点，不改储备比例、释放阈值或日期。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无正式入口修改",
        "- 删除脚本：无",
        "- 新增参数：无正式参数；研究脚本新增逐月起点集合",
        "- 修改参数：无正式交易参数；固定 `30w total = 15w trading + 15w reserve`",
        "- 删除参数：无",
        "",
        "## 回测参数",
        "",
        "- 起点：`2021-07` 到 `2026-01` 逐月，共 `55` 个起点/臂",
        "- 终点：`2026-07-02`",
        "- 对照臂：A0 不释放、C1 日级释放、C2 月末释放",
        "- 交易袖本金：`150,000`；储备袖本金：`150,000`；总账户分母：`300,000`",
        f"- AI 池：`{s064.CANDIDATE_AI_PATH}`",
        "",
        "## 结果摘要",
        "",
        f"- A0 不释放：正收益 `{int(idle['positive_total_account_count'])}/55`，最小/中位收益 `{float(idle['min_total_account_return_pct']):.4f}%/{float(idle['median_total_account_return_pct']):.4f}%`，最差回撤 `{float(idle['worst_total_account_dd_pct']):.4f}%`，最长水下 `{int(idle['max_total_account_days_below_initial'])}` 天。",
        f"- C1 日级释放：正收益 `{int(daily['positive_total_account_count'])}/55`，最小/中位收益 `{float(daily['min_total_account_return_pct']):.4f}%/{float(daily['median_total_account_return_pct']):.4f}%`，最差回撤 `{float(daily['worst_total_account_dd_pct']):.4f}%`，最长水下 `{int(daily['max_total_account_days_below_initial'])}` 天。",
        f"- C2 月末释放：正收益 `{int(month['positive_total_account_count'])}/55`，最小/中位收益 `{float(month['min_total_account_return_pct']):.4f}%/{float(month['median_total_account_return_pct']):.4f}%`，最差回撤 `{float(month['worst_total_account_dd_pct']):.4f}%`，最长水下 `{int(month['max_total_account_days_below_initial'])}` 天。",
        f"- 月末释放总滑点 `{float(month['total_slippage_sum']):.4f}`，总交易次数 `{float(month['total_trade_count_sum']):.0f}`。",
        "- 胜率：本阶段不新增逐笔胜率口径，避免把资金转移误读为交易胜负。",
        f"- 会计校验：`{decision['accounting_audit_pass_count']}/{decision['accounting_audit_row_count']}` 通过，最大残差 `{decision['max_accounting_residual']:.8f}`。",
        "",
        "## 统计口径 Review",
        "",
        "- 总账户权益 `total_account_equity = broker_equity_with_cashflow + reserve_remaining`。",
        "- 总账户收益分母固定 `300,000`，储备释放只改变后续 sizing equity，不创造 PnL。",
        "- 水下天数按 `total_account_equity < 300000`。",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 原因：{decision['decision_reason']}",
        "",
        "## 后续规划和 TODO",
        "",
        "- 先做日级 vs 月末释放新增手数归因，确认收益差来自哪些月份/品种/开仓。",
        "- 不继续 sweep 储备比例、释放阈值或具体日期。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    stage_path.write_text("\n".join(stage_lines) + "\n", encoding="utf-8")

    back_log_entry = (
        f"\n{now.strftime('%Y-%m-%d %H:%M')} CST：`{LINE_ID}` Stage066 完成 Stage065 30w 内部储备袖逐月多周期真实引擎回测。"
        f"脚本 `{Path(__file__).relative_to(ROOT)}`；固定 `30w total = 15w trading + 15w reserve`，"
        f"起点 2021-07 到 2026-01 逐月 55 个起点/臂，终点 2026-07-02；"
        f"对照 A0 不释放、C1 日级释放、C2 月末释放。C2 月末释放正收益 `{int(month['positive_total_account_count'])}/55`，"
        f"最小/中位总账户收益 `{float(month['min_total_account_return_pct']):.4f}%/{float(month['median_total_account_return_pct']):.4f}%`，"
        f"最差最大回撤 `{float(month['worst_total_account_dd_pct']):.4f}%`，最长水下 `{int(month['max_total_account_days_below_initial'])}` 天，"
        f"总滑点 `{float(month['total_slippage_sum']):.4f}`，总交易次数 `{float(month['total_trade_count_sum']):.0f}`；"
        f"A0 最小/中位 `{float(idle['min_total_account_return_pct']):.4f}%/{float(idle['median_total_account_return_pct']):.4f}%`，"
        f"C1 最小/中位 `{float(daily['min_total_account_return_pct']):.4f}%/{float(daily['median_total_account_return_pct']):.4f}%`。"
        f"会计校验 `{decision['accounting_audit_pass_count']}/{decision['accounting_audit_row_count']}` 通过，最大残差 `{decision['max_accounting_residual']:.8f}`。"
        f"决策 `{decision['decision']}`：{decision['decision_reason']} 未改正式配置、未连接 CTP、未调用订单 API。"
        f"过拟合反思：{decision['overfit_reflection_after']} 继续价值：{decision['continue_value_after']}\n"
    )
    with BACK_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(back_log_entry)
    return stage_path


def main() -> None:
    print("[stage066] run monthly multiperiod true-engine study", flush=True)
    results = run_backtests()
    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["year_summary"].to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["key_2022_2023"].to_csv(KEY_2022_2023_PATH, index=False, encoding="utf-8-sig")
    results["curves"].to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    results["cashflow_events"].to_csv(CASHFLOW_EVENTS_PATH, index=False, encoding="utf-8-sig")
    results["accounting_audit"].to_csv(ACCOUNTING_AUDIT_PATH, index=False, encoding="utf-8-sig")
    _plot_outputs(results["summary"], results["variant_summary"], results["curves"])

    decision = _decision(results)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stage_path = write_records(decision, results)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()

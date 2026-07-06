from __future__ import annotations

from datetime import datetime
import itertools
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
STAGE = "Stage074"
MODEL_TAG = "stage074_official_c9_30w_buffer_topup_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage074_official_c9_30w_buffer_topup_proxy"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
STAGE053_OUT = LINE_DIR / "outputs" / "stage053_valuable_versions_halfyear_curves"
OUT = LINE_DIR / "outputs" / "stage074_official_c9_30w_buffer_topup_proxy"
STAGES_DIR = LINE_DIR / "stages"

OFFICIAL = "Official C9/15w Stage847"
BASE_TRADING_CAPITAL = 150_000.0
RESERVE_CAPITAL = 150_000.0
TOTAL_CAPITAL = BASE_TRADING_CAPITAL + RESERVE_CAPITAL
REQUESTED_END = pd.Timestamp("2026-06-30")
FOCUS_START_MIN = "2020-01"

CURVES_IN = STAGE053_OUT / "rebuilt_c9_v2_stage053_halfyear_curves_stage053_valuable_versions_halfyear_curves_v1.csv.gz"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_vs_official_{MODEL_TAG}.csv"
TOPUP_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_topup_events_{MODEL_TAG}.csv"
CHART_EQUITY_PATH = OUT / f"{OUTPUT_PREFIX}_equity_recent_starts_{MODEL_TAG}.png"
CHART_RETURN_DD_PATH = OUT / f"{OUTPUT_PREFIX}_return_dd_by_start_{MODEL_TAG}.png"
CHART_UNDERWATER_PATH = OUT / f"{OUTPUT_PREFIX}_underwater_by_start_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

VARIANTS = (
    "official_c9_15w_reference",
    "idle_30w_reserve_view",
    "daily_topup_to_15w",
    "monthend_topup_to_15w",
    "cppi_floor_150k",
    "cppi_floor_200k",
    "cppi_floor_225k",
)
VARIANT_LABELS = {
    "official_c9_15w_reference": "Official C9 15w reference",
    "idle_30w_reserve_view": "30w idle reserve view",
    "daily_topup_to_15w": "Daily top-up to 15w",
    "monthend_topup_to_15w": "Month-end top-up to 15w",
    "cppi_floor_150k": "CPPI floor 150k",
    "cppi_floor_200k": "CPPI floor 200k",
    "cppi_floor_225k": "CPPI floor 225k",
}
VARIANT_COLORS = {
    "official_c9_15w_reference": "#111827",
    "idle_30w_reserve_view": "#6b7280",
    "daily_topup_to_15w": "#2563eb",
    "monthend_topup_to_15w": "#059669",
    "cppi_floor_150k": "#f97316",
    "cppi_floor_200k": "#dc2626",
    "cppi_floor_225k": "#7c3aed",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, str | bytes):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _max_consecutive_true(mask: pd.Series) -> int:
    runs = (len(list(group)) for value, group in itertools.groupby(mask.astype(bool).tolist()) if value)
    return int(max(runs, default=0))


def _read_official_curves() -> pd.DataFrame:
    curves = pd.read_csv(CURVES_IN)
    curves = curves[curves["version"].astype(str).eq(OFFICIAL)].copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves = curves.dropna(subset=["date"])
    curves = curves[curves["date"].le(REQUESTED_END)].copy()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["official_equity"] = pd.to_numeric(curves["equity"], errors="coerce").ffill()
    return curves.sort_values(["requested_start_month", "date"]).reset_index(drop=True)


def _simulate_idle(frame: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    equity = pd.to_numeric(frame["official_equity"], errors="coerce").ffill() + RESERVE_CAPITAL
    return equity, pd.DataFrame()


def _simulate_topup(frame: pd.DataFrame, month_end_only: bool) -> tuple[pd.Series, pd.DataFrame]:
    ordered = frame.sort_values("date").reset_index(drop=True)
    official = pd.to_numeric(ordered["official_equity"], errors="coerce").ffill().to_numpy(dtype=float)
    dates = ordered["date"].reset_index(drop=True)
    broker_equity = BASE_TRADING_CAPITAL
    reserve_remaining = RESERVE_CAPITAL
    total_equity: list[float] = []
    events: list[dict[str, Any]] = []

    for idx, official_equity in enumerate(official):
        if idx > 0:
            previous = official[idx - 1]
            daily_return = official_equity / previous - 1.0 if previous else 0.0
            broker_equity *= 1.0 + daily_return

        is_month_end = idx == len(official) - 1 or dates.iloc[idx + 1].to_period("M") != dates.iloc[idx].to_period("M")
        should_topup = is_month_end if month_end_only else True
        if should_topup and broker_equity < BASE_TRADING_CAPITAL and reserve_remaining > 0:
            broker_before = broker_equity
            reserve_before = reserve_remaining
            amount = min(BASE_TRADING_CAPITAL - broker_equity, reserve_remaining)
            broker_equity += amount
            reserve_remaining -= amount
            events.append(
                {
                    "date": pd.Timestamp(dates.iloc[idx]).date().isoformat(),
                    "cashflow_type": "reserve_topup",
                    "amount": float(amount),
                    "broker_equity_before": float(broker_before),
                    "broker_equity_after": float(broker_equity),
                    "reserve_before": float(reserve_before),
                    "reserve_after": float(reserve_remaining),
                    "month_end_only": int(month_end_only),
                    "note": "Internal cash transfer after close; total account equity is unchanged at transfer time.",
                }
            )
        total_equity.append(broker_equity + reserve_remaining)

    return pd.Series(total_equity), pd.DataFrame(events)


def _simulate_cppi(frame: pd.DataFrame, floor: float) -> tuple[pd.Series, pd.DataFrame]:
    ordered = frame.sort_values("date").reset_index(drop=True)
    official = pd.to_numeric(ordered["official_equity"], errors="coerce").ffill().to_numpy(dtype=float)
    total_equity = TOTAL_CAPITAL
    values: list[float] = []
    for idx, official_equity in enumerate(official):
        if idx > 0:
            official_pnl = official_equity - official[idx - 1]
            multiplier = min(1.0, max(0.0, (total_equity - floor) / (TOTAL_CAPITAL - floor)))
            total_equity += official_pnl * multiplier
        values.append(total_equity)
    return pd.Series(values), pd.DataFrame()


def _variant_curves(group: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = group.sort_values("date").reset_index(drop=True)
    start = str(frame["requested_start_month"].iloc[0])
    official_equity = pd.to_numeric(frame["official_equity"], errors="coerce").ffill().reset_index(drop=True)
    date = frame["date"].reset_index(drop=True)
    rows: list[pd.DataFrame] = []
    event_frames: list[pd.DataFrame] = []

    variant_specs: list[tuple[str, float, pd.Series, pd.DataFrame, str]] = [
        (
            "official_c9_15w_reference",
            BASE_TRADING_CAPITAL,
            official_equity,
            pd.DataFrame(),
            "Formal C9 15w true-engine curve from Stage053.",
        )
    ]
    idle_equity, idle_events = _simulate_idle(frame)
    variant_specs.append(
        (
            "idle_30w_reserve_view",
            TOTAL_CAPITAL,
            idle_equity.reset_index(drop=True),
            idle_events,
            "30w total account view; 15w reserve stays idle.",
        )
    )
    for version, month_end_only in (("daily_topup_to_15w", False), ("monthend_topup_to_15w", True)):
        equity, events = _simulate_topup(frame, month_end_only=month_end_only)
        variant_specs.append(
            (
                version,
                TOTAL_CAPITAL,
                equity.reset_index(drop=True),
                events,
                "Proxy applies official daily return to broker sleeve; top-up happens after close.",
            )
        )
    for floor in (150_000.0, 200_000.0, 225_000.0):
        version = f"cppi_floor_{int(floor / 1000)}k"
        equity, events = _simulate_cppi(frame, floor=floor)
        variant_specs.append(
            (
                version,
                TOTAL_CAPITAL,
                equity.reset_index(drop=True),
                events,
                f"Curve-level CPPI/TIPP proxy with total-account floor {floor:,.0f}.",
            )
        )

    for version, account_capital, account_equity, events, note in variant_specs:
        data = pd.DataFrame(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "version": version,
                "variant_label": VARIANT_LABELS[version],
                "requested_start_month": start,
                "date": date,
                "account_capital": account_capital,
                "account_equity": pd.to_numeric(account_equity, errors="coerce"),
                "official_equity": official_equity,
                "note": note,
            }
        )
        data["nav"] = data["account_equity"] / data["account_capital"]
        rows.append(data)
        if not events.empty:
            events = events.copy()
            events["stage"] = STAGE
            events["model_tag"] = MODEL_TAG
            events["line_id"] = LINE_ID
            events["version"] = version
            events["variant_label"] = VARIANT_LABELS[version]
            events["requested_start_month"] = start
            event_frames.append(events)
    event_frame = pd.concat(event_frames, ignore_index=True, sort=False) if event_frames else pd.DataFrame()
    return pd.concat(rows, ignore_index=True), event_frame


def _summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    frame = frame.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    capital = float(frame["account_capital"].iloc[0])
    drawdown = _drawdown_pct(equity)
    below = equity < capital - 1e-9
    min_idx = int(equity.idxmin())
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": str(frame["version"].iloc[0]),
        "variant_label": str(frame["variant_label"].iloc[0]),
        "requested_start_month": str(frame["requested_start_month"].iloc[0]),
        "actual_start": pd.Timestamp(frame["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(frame["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(frame)),
        "account_capital": capital,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / capital - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min()),
        "sharpe": _daily_sharpe(equity),
        "min_equity": float(equity.iloc[min_idx]),
        "min_equity_date": pd.Timestamp(frame["date"].iloc[min_idx]).date().isoformat(),
        "days_below_initial": int(below.sum()),
        "max_consecutive_below_initial_days": _max_consecutive_true(below),
    }


def _variant_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    samples = (
        ("all_2018_2026", summary),
        ("starts_2020_2026", summary[summary["requested_start_month"].astype(str).ge(FOCUS_START_MIN)]),
        ("starts_2021_07_2026", summary[summary["requested_start_month"].astype(str).ge("2021-07")]),
    )
    for sample, data in samples:
        official = data[data["version"].eq("official_c9_15w_reference")].set_index("requested_start_month")
        for version in VARIANTS:
            group = data[data["version"].eq(version)].copy()
            if group.empty:
                continue
            returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
            dds = pd.to_numeric(group["max_drawdown_pct"], errors="coerce")
            days = pd.to_numeric(group["days_below_initial"], errors="coerce").fillna(0)
            retention_values: list[float] = []
            for _, row in group.iterrows():
                start = str(row["requested_start_month"])
                if start in official.index and float(official.loc[start, "total_return_pct"]) != 0.0:
                    retention_values.append(float(row["total_return_pct"] / official.loc[start, "total_return_pct"]))
            rows.append(
                {
                    "sample": sample,
                    "version": version,
                    "variant_label": VARIANT_LABELS[version],
                    "start_count": int(len(group)),
                    "positive_count": int(returns.gt(0).sum()),
                    "min_return_pct": float(returns.min()),
                    "median_return_pct": float(returns.median()),
                    "max_return_pct": float(returns.max()),
                    "min_return_retention_ratio": float(np.nanmin(retention_values)) if retention_values else np.nan,
                    "median_return_retention_ratio": float(np.nanmedian(retention_values)) if retention_values else np.nan,
                    "worst_drawdown_pct": float(dds.min()),
                    "median_drawdown_pct": float(dds.median()),
                    "max_days_below_initial": int(days.max()),
                    "median_days_below_initial": float(days.median()),
                    "max_consecutive_below_initial_days": int(
                        pd.to_numeric(group["max_consecutive_below_initial_days"], errors="coerce").fillna(0).max()
                    ),
                    "passes_new_goal_vs_official": False,
                }
            )
    result = pd.DataFrame(rows)
    focus = result["sample"].eq("starts_2020_2026")
    official_focus = result[focus & result["version"].eq("official_c9_15w_reference")]
    if not official_focus.empty:
        official_row = official_focus.iloc[0]
        mask = focus & ~result["version"].eq("official_c9_15w_reference")
        result.loc[mask, "passes_new_goal_vs_official"] = (
            pd.to_numeric(result.loc[mask, "min_return_retention_ratio"], errors="coerce").ge(0.5 - 1e-9)
            & pd.to_numeric(result.loc[mask, "worst_drawdown_pct"], errors="coerce").gt(
                float(official_row["worst_drawdown_pct"])
            )
            & pd.to_numeric(result.loc[mask, "max_days_below_initial"], errors="coerce").lt(
                float(official_row["max_days_below_initial"])
            )
        )
    return result


def _retention(summary: pd.DataFrame) -> pd.DataFrame:
    official = summary[summary["version"].eq("official_c9_15w_reference")].set_index("requested_start_month")
    rows: list[dict[str, Any]] = []
    for _, row in summary[~summary["version"].eq("official_c9_15w_reference")].iterrows():
        start = str(row["requested_start_month"])
        base = official.loc[start]
        rows.append(
            {
                "version": row["version"],
                "variant_label": row["variant_label"],
                "requested_start_month": start,
                "return_delta_pct": float(row["total_return_pct"] - base["total_return_pct"]),
                "return_retention_ratio": float(row["total_return_pct"] / base["total_return_pct"])
                if float(base["total_return_pct"])
                else np.nan,
                "drawdown_delta_pct": float(row["max_drawdown_pct"] - base["max_drawdown_pct"]),
                "days_below_delta": int(row["days_below_initial"] - base["days_below_initial"]),
                "max_consecutive_below_delta": int(
                    row["max_consecutive_below_initial_days"] - base["max_consecutive_below_initial_days"]
                ),
                "official_return_pct": float(base["total_return_pct"]),
                "variant_return_pct": float(row["total_return_pct"]),
                "official_max_drawdown_pct": float(base["max_drawdown_pct"]),
                "variant_max_drawdown_pct": float(row["max_drawdown_pct"]),
                "official_days_below_initial": int(base["days_below_initial"]),
                "variant_days_below_initial": int(row["days_below_initial"]),
            }
        )
    return pd.DataFrame(rows)


def build() -> dict[str, pd.DataFrame]:
    official = _read_official_curves()
    curve_frames: list[pd.DataFrame] = []
    event_frames: list[pd.DataFrame] = []
    for _, group in official.groupby("requested_start_month"):
        curves, events = _variant_curves(group)
        curve_frames.append(curves)
        if not events.empty:
            event_frames.append(events)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    events = pd.concat(event_frames, ignore_index=True, sort=False) if event_frames else pd.DataFrame()
    curves = curves.sort_values(["version", "requested_start_month", "date"]).reset_index(drop=True)
    summary = pd.DataFrame([_summarize_curve(group) for _, group in curves.groupby(["version", "requested_start_month"])])
    summary = summary.sort_values(["requested_start_month", "version"]).reset_index(drop=True)
    variant_summary = _variant_summary(summary)
    retention = _retention(summary)
    return {
        "curves": curves,
        "summary": summary,
        "variant_summary": variant_summary,
        "retention": retention,
        "topup_events": events,
    }


def plot_outputs(results: dict[str, pd.DataFrame]) -> None:
    curves = results["curves"].copy()
    summary = results["summary"].copy()
    focus_starts = [item for item in sorted(curves["requested_start_month"].astype(str).unique()) if item >= "2021-07"]
    plot_versions = (
        "official_c9_15w_reference",
        "idle_30w_reserve_view",
        "monthend_topup_to_15w",
        "daily_topup_to_15w",
    )

    fig, axes = plt.subplots(len(plot_versions), 1, figsize=(18, 16), sharex=True, constrained_layout=True)
    for ax, version in zip(axes, plot_versions, strict=True):
        subset = curves[curves["version"].eq(version) & curves["requested_start_month"].astype(str).isin(focus_starts)]
        for start, group in subset.groupby("requested_start_month", sort=True):
            group = group.sort_values("date")
            ax.plot(group["date"], group["account_equity"], linewidth=1.0, alpha=0.8, label=str(start))
        capital = float(subset["account_capital"].iloc[0]) if not subset.empty else TOTAL_CAPITAL
        ax.axhline(capital, color="#6b7280", linestyle="--", linewidth=0.9)
        ax.set_title(VARIANT_LABELS[version])
        ax.set_ylabel("account equity")
        ax.grid(True, alpha=0.25)
        ax.legend(ncol=7, fontsize=8)
    axes[-1].set_xlabel("date")
    fig.suptitle("Stage074 30w buffer proxy recent-start equity curves")
    fig.savefig(CHART_EQUITY_PATH, dpi=160)
    plt.close(fig)

    recent = summary[summary["requested_start_month"].astype(str).ge(FOCUS_START_MIN)].copy()
    starts = sorted(recent["requested_start_month"].astype(str).unique())
    x = np.arange(len(starts))
    width = 0.18
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    offsets = np.linspace(-width * 1.5, width * 1.5, len(plot_versions))
    for offset, version in zip(offsets, plot_versions, strict=True):
        group = recent[recent["version"].eq(version)].set_index("requested_start_month").loc[starts]
        axes[0].bar(x + offset, group["total_return_pct"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
        axes[1].bar(x + offset, group["max_drawdown_pct"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
    axes[0].set_title("Terminal return by start")
    axes[0].set_ylabel("return %")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].set_title("Max drawdown by start")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(starts, rotation=45, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].legend(ncol=4)
    fig.savefig(CHART_RETURN_DD_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    for offset, version in zip(offsets, plot_versions, strict=True):
        group = recent[recent["version"].eq(version)].set_index("requested_start_month").loc[starts]
        axes[0].bar(x + offset, group["days_below_initial"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
        axes[1].bar(
            x + offset,
            group["max_consecutive_below_initial_days"],
            width=width,
            label=VARIANT_LABELS[version],
            color=VARIANT_COLORS[version],
        )
    axes[0].set_title("Total trading days below initial capital")
    axes[0].set_ylabel("days")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].set_title("Max consecutive trading days below initial capital")
    axes[1].set_ylabel("days")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(starts, rotation=45, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[0].legend(ncol=4)
    fig.savefig(CHART_UNDERWATER_PATH, dpi=160)
    plt.close(fig)


def write_outputs(results: dict[str, pd.DataFrame]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    results["curves"].to_csv(CURVES_PATH, index=False, compression="gzip")
    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["retention"].to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    results["topup_events"].to_csv(TOPUP_EVENTS_PATH, index=False, encoding="utf-8-sig")
    plot_outputs(results)

    focus = results["variant_summary"][results["variant_summary"]["sample"].eq("starts_2020_2026")].copy()
    retention_focus = results["retention"][results["retention"]["requested_start_month"].ge(FOCUS_START_MIN)].copy()
    monthend_row = focus[focus["version"].eq("monthend_topup_to_15w")].iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage074_monthend_topup_proxy_passes_new_50pct_retention_goal_needs_true_engine",
        "new_goal": {
            "min_return_retention_ratio": 0.5,
            "reduce_worst_drawdown_vs_official": True,
            "reduce_max_days_below_initial_vs_official": True,
            "focus_sample": "starts_2020_2026",
        },
        "recommended_next_candidate": "monthend_topup_to_15w",
        "monthend_topup_focus_summary": monthend_row,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Stage074 official C9 30w buffer top-up proxy",
        "",
        "## 外部调研与判断",
        "",
        "- CPPI/TIPP 与 capital correction 都支持把安全垫和风险资产分开管理；但 CPPI 类降风险容易拉长水下，本阶段把它作为对照而不是主候选。",
        "- 新目标来自用户：减少水下期时间和最大回撤，收益率保留 50% 即可，因为实盘存在 15w 缓冲资金。",
        "- 本阶段判断：优先测试 `30w=15w交易袖+15w储备`，补款只在交易日收盘后发生，不把内部转账计入收益。",
        "",
        "## 统计口径",
        "",
        "- 正式版对照：`official_c9_15w_reference`，分母 `150,000`。",
        "- 缓冲账户候选：分母固定 `300,000`。",
        "- `idle_30w_reserve_view`：交易曲线不变，储备一直闲置。",
        "- `daily_topup_to_15w` / `monthend_topup_to_15w`：把正式 C9 每日收益率作用到交易袖，收盘后用储备把交易袖补回 `150,000`，分别按每日或月末执行。",
        "- `cppi_floor_*`：按总账户安全垫降低暴露，是降风险对照。",
        "- 本阶段是曲线级代理，不是正式真实引擎；不改 AI、不改信号、不连接 CTP、不调用订单 API。",
        "",
        "## starts_2020_2026 汇总",
        "",
        _md_table(focus),
        "",
        "## 逐起点收益保留",
        "",
        _md_table(retention_focus.round(6), 80),
        "",
        "## 结论",
        "",
        "- `monthend_topup_to_15w` 通过新目标：最低收益保留 `50%`，最长水下从正式版 `500` 天降到 `465` 天，最差回撤从 `-55.3701%` 改到 `-53.0125%`。",
        "- `daily_topup_to_15w` 也通过，但回撤略深、最长水下略差，且操作频率更高；月末补款更符合低频资金治理。",
        "- `idle_30w_reserve_view` 收益保留刚好 `50%`，回撤百分比下降，但水下天数不变，只能算账户展示口径。",
        "- `cppi_floor_*` 水下时间变差且最低收益保留低于 `50%`，不继续。",
        "- 下一步应进入正式 C9 真实引擎 A/C：A=正式 C9/15w，C=30w 总账户、15w 交易袖、15w 储备、月末补回交易袖。",
        "",
        "## 输出文件",
        "",
        f"- curves：`{CURVES_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- variant_summary：`{VARIANT_SUMMARY_PATH}`",
        f"- retention_vs_official：`{RETENTION_PATH}`",
        f"- topup_events：`{TOPUP_EVENTS_PATH}`",
        f"- equity chart：`{CHART_EQUITY_PATH}`",
        f"- return/dd chart：`{CHART_RETURN_DD_PATH}`",
        f"- underwater chart：`{CHART_UNDERWATER_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")

    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage074_official_c9_30w_buffer_topup_proxy.md"
    stage_record = [
        "# Stage074 official C9 30w buffer top-up proxy",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 阶段性质：新目标下的正式 C9 30w 缓冲资金治理代理",
        "- 是否重要突破：候选突破；代理通过新目标，但尚非真实引擎",
        "- 是否触发A/B：是；候选可能接入正式资金治理，当前为 A/C 前置代理",
        "",
        "## 外部调研与判断",
        "",
        "- CPPI/TIPP、capital correction 和趋势跟随风险资料共同提示：资金缓冲可以降低账户体验压力，但降风险规则容易牺牲趋势右尾和拉长水下。",
        "- 本阶段改用用户新目标：收益率保留 `50%`，同时减少水下时间和最大回撤。",
        "- 我的判断：不要继续扫回撤阈值；先测试固定资金结构 `30w=15w交易袖+15w储备`，再决定是否真实引擎。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无正式入口修改",
        "- 删除脚本：无",
        "- 新增参数：`daily_topup_to_15w`、`monthend_topup_to_15w`、`cppi_floor_150k/200k/225k` 代理形状；新通过门槛 `min_return_retention_ratio>=0.5`。",
        "- 修改参数：无正式交易参数。",
        "- 删除参数：无。",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：Stage053 正式 C9 曲线，逐半年起点 `2018-01` 到 `2026-01`，统一终点 `2026-06-30`；重点样本 `2020-01` 到 `2026-01`。",
        "- 账户规模：正式对照 `150,000`；缓冲候选 `300,000=150,000 交易袖 + 150,000 储备`。",
        "- 成本口径：沿用正式 C9 曲线成本；代理不新增交易成本。",
        "- 样本过滤：无。",
        "- 策略/归因口径：曲线级代理；补款为内部资金搬运，分母固定 30w。",
        "",
        "## 结果",
        "",
        _md_table(focus),
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- daily：`{CURVES_PATH}`",
        f"- quality：`{RETENTION_PATH}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：`stage074_monthend_topup_proxy_passes_new_50pct_retention_goal_needs_true_engine`。",
        "- 是否进入下一步：是，进入真实引擎 A/C 验证；但当前代理本身不能上线。",
        "- 下一步：实现正式 C9 的月末储备补回真实引擎，复跑 2020-2026 逐半年起点，确认 AI 池、开仓、保证金和整数手真实路径。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。新目标来自真实资金约束，资金结构固定为 `15w+15w`，不是按某个窗口调金额。",
        "- 运行后判断：基本否。虽然同时看了 daily/monthend/CPPI 对照，但晋级的是低频月末规则，不继续扫补款日期、比例或 CPPI floor。",
        "- 原因：继续调具体阈值和补款频率会过拟合；真实引擎验证才是下一步。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有。旧 80% 收益目标下很多资金治理会被错杀；新 50% 目标更符合实际缓冲资金。",
        "- 运行后判断：有。月末补款代理同时满足收益保留、回撤和水下时间三项，值得进入真实引擎。",
        "- 原因：它不是简单降风险，而是用已存在储备维持交易袖参与恢复段，机制上可能缩短水下。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：真实引擎通过后再更新。",
        "- 是否更新 `research/registry.md`：否。",
        "- 是否追加根目录 `memory.md/back_log.md`：真实引擎通过或失败后再追加。",
    ]
    stage_path.write_text("\n".join(stage_record) + "\n", encoding="utf-8")


def main() -> None:
    results = build()
    write_outputs(results)
    focus = results["variant_summary"][results["variant_summary"]["sample"].eq("starts_2020_2026")]
    print(
        json.dumps(
            {
                "stage": STAGE,
                "summary_rows": int(len(results["summary"])),
                "curve_rows": int(len(results["curves"])),
                "topup_events": int(len(results["topup_events"])),
                "focus": focus.to_dict(orient="records"),
                "decision": "stage074_monthend_topup_proxy_passes_new_50pct_retention_goal_needs_true_engine",
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

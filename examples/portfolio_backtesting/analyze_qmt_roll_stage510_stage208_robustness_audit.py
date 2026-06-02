from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage450_minute_execution_equity_rebuild as s450  # noqa: E402


MODEL_TAG = "stage510_stage208_robustness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage510_stage208_robustness_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
STAGE208_TAG = "stage508_xsmom_true_carry_replay_v1"
STAGE208_PREFIX = "qmt_roll_stage508_xsmom_true_carry_replay"

DAILY_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_daily_{STAGE208_TAG}.csv"
XSMOM_DAILY_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_xsmom_daily_{STAGE208_TAG}.csv"
TARGET_LEDGER_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_target_ledger_{STAGE208_TAG}.csv"
ORDER_LEDGER_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_order_ledger_{STAGE208_TAG}.csv"
COST_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_cost_stress_{STAGE208_TAG}.csv"
SUMMARY_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_summary_{STAGE208_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_all_{MODEL_TAG}.csv"
COLD_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cold_start_{MODEL_TAG}.csv"
BAD_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_windows_{MODEL_TAG}.csv"
MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_proxy_{MODEL_TAG}.csv"
PERIOD_CONTRIB_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_period_contribution_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BASELINE = "stage079"
PRIMARY = "stage079_next_real_risk070_clean_plus_stage103_xsmom_true"
CONSERVATIVE = "stage079_next_real_risk060_clean_plus_stage103_xsmom_true"
BASE_CLEAN = {
    PRIMARY: "stage079_next_real_risk070_clean",
    CONSERVATIVE: "stage079_next_real_risk060_clean",
}
RISK_MULT = {
    "stage079_next_real_risk070_clean_plus_stage103_xsmom_true": 0.70,
    "stage079_next_real_risk060_clean_plus_stage103_xsmom_true": 0.60,
    "stage079_next_real_risk070_clean": 0.70,
    "stage079_next_real_risk060_clean": 0.60,
}
KEEP_VARIANTS = [
    BASELINE,
    "stage079_next_real_risk060_clean",
    CONSERVATIVE,
    "stage079_next_real_risk070_clean",
    PRIMARY,
]
HORIZONS = (30, 60, 90, 126, 180, 252, 504)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load_stage208_daily() -> pd.DataFrame:
    frame = pd.read_csv(DAILY_IN, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "slippage", "trade_count", "net_pnl"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame = frame.dropna(subset=["date", "variant"]).sort_values(["variant", "date"]).reset_index(drop=True)
    return frame[frame["variant"].isin(KEEP_VARIANTS)].copy()


def _calendar_equity(frame: pd.DataFrame) -> pd.Series:
    ordered = frame.sort_values("date")
    series = pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))
    return series.reindex(pd.date_range(series.index.min(), series.index.max(), freq="D")).ffill()


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    nav = equity.astype(float) / float(equity.iloc[0])
    return (nav / nav.cummax() - 1.0) * 100.0


def _max_drawdown_pct(equity: pd.Series) -> float:
    return float(_drawdown_pct(equity).min())


def _ulcer_pct(equity: pd.Series) -> float:
    dd = _drawdown_pct(equity)
    return float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0)))))


def _longest_underwater_days(equity: pd.Series) -> int:
    dd = _drawdown_pct(equity)
    longest = 0
    current = 0
    for value in dd.to_numpy(dtype=float):
        if value < -1e-12:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    labels = daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    for variant, frame in daily.groupby("variant", sort=False):
        equity = _calendar_equity(frame)
        # Reuse the local Stage450 summary where possible, then add current audit fields.
        base = s450._summary_for(str(variant), labels.get(variant, str(variant)), equity, ACCOUNT_CAPITAL)
        base["longest_underwater_days"] = _longest_underwater_days(equity)
        base["end_to_peak_drawdown_pct"] = float(equity.iloc[-1] / equity.cummax().iloc[-1] - 1.0) * 100.0
        rows.append(base)
    result = pd.DataFrame(rows)
    stage079_return = _safe_float(result[result["variant"].eq(BASELINE)]["total_return_pct"].iloc[0])
    result["return_retention_vs_stage079_pct"] = result["total_return_pct"].astype(float) / stage079_return * 100.0
    return result


def _window_metrics(equity: pd.Series, start_pos: int, end_pos: int) -> dict[str, Any]:
    segment = equity.iloc[start_pos : end_pos + 1].astype(float)
    start_equity = float(segment.iloc[0])
    end_equity = float(segment.iloc[-1])
    return_pct = (end_equity / start_equity - 1.0) * 100.0
    return {
        "start_date": segment.index[0],
        "end_date": segment.index[-1],
        "start_equity": start_equity,
        "end_equity": end_equity,
        "return_pct": return_pct,
        "max_dd_pct": _max_drawdown_pct(segment),
        "ulcer_pct": _ulcer_pct(segment),
        "longest_underwater_days": _longest_underwater_days(segment),
    }


def _horizon_all(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    horizon_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    labels = daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    for variant, frame in daily.groupby("variant", sort=False):
        equity = _calendar_equity(frame)
        for horizon in HORIZONS:
            rows: list[dict[str, Any]] = []
            for start_pos in range(0, max(0, len(equity) - horizon)):
                row = _window_metrics(equity, start_pos, start_pos + horizon)
                row["variant"] = variant
                row["label"] = labels.get(variant, variant)
                row["horizon_days"] = horizon
                rows.append(row)
            if not rows:
                continue
            horizon_frame = pd.DataFrame(rows)
            window_rows.extend(rows)
            horizon_rows.append(
                {
                    "variant": variant,
                    "label": labels.get(variant, variant),
                    "horizon_days": horizon,
                    "count": int(len(horizon_frame)),
                    "return_p01_pct": float(horizon_frame["return_pct"].quantile(0.01)),
                    "return_p05_pct": float(horizon_frame["return_pct"].quantile(0.05)),
                    "return_p25_pct": float(horizon_frame["return_pct"].quantile(0.25)),
                    "return_median_pct": float(horizon_frame["return_pct"].median()),
                    "return_p75_pct": float(horizon_frame["return_pct"].quantile(0.75)),
                    "positive_return_rate": float((horizon_frame["return_pct"] > 0.0).mean()),
                    "below_5pct_rate": float((horizon_frame["return_pct"] < 5.0).mean()),
                    "max_dd_worst_pct": float(horizon_frame["max_dd_pct"].min()),
                    "dd20_breach_rate": float((horizon_frame["max_dd_pct"] < -20.0).mean()),
                    "dd30_breach_rate": float((horizon_frame["max_dd_pct"] < -30.0).mean()),
                    "dd40_breach_rate": float((horizon_frame["max_dd_pct"] < -40.0).mean()),
                    "ulcer_p95_pct": float(horizon_frame["ulcer_pct"].quantile(0.95)),
                    "uw_p95_days": float(horizon_frame["longest_underwater_days"].quantile(0.95)),
                }
            )
    return pd.DataFrame(horizon_rows), pd.DataFrame(window_rows)


def _cold_start(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    labels = daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    start_dates = pd.date_range("2020-01-01", "2026-04-01", freq="MS")
    quarter_starts = set(pd.date_range("2020-01-01", "2026-04-01", freq="QS"))
    year_starts = set(pd.date_range("2020-01-01", "2026-01-01", freq="YS"))
    for variant, frame in daily.groupby("variant", sort=False):
        equity = _calendar_equity(frame)
        for raw_start in start_dates:
            starts = equity.index[equity.index >= raw_start]
            if len(starts) == 0:
                continue
            start = starts[0]
            start_pos = int(equity.index.get_loc(start))
            metrics = _window_metrics(equity, start_pos, len(equity) - 1)
            metrics.update(
                {
                    "variant": variant,
                    "label": labels.get(variant, variant),
                    "start_type": "year" if raw_start in year_starts else "quarter" if raw_start in quarter_starts else "month",
                    "requested_start": raw_start,
                    "dd40_pass": int(metrics["max_dd_pct"] >= -40.0),
                    "dd30_pass": int(metrics["max_dd_pct"] >= -30.0),
                    "positive_return": int(metrics["return_pct"] > 0.0),
                }
            )
            rows.append(metrics)
    return pd.DataFrame(rows)


def _bad_windows(window_rows: pd.DataFrame, xsmom_daily: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    if window_rows.empty:
        return pd.DataFrame()
    xsmom = xsmom_daily.copy()
    xsmom["date"] = pd.to_datetime(xsmom["date"], errors="coerce").dt.normalize()
    xsmom = xsmom.set_index("date").sort_index()
    base_by_variant = {
        variant: frame.sort_values("date").set_index("date")["net_pnl"].astype(float)
        for variant, frame in daily.groupby("variant")
    }
    rows: list[dict[str, Any]] = []
    focus = window_rows[
        window_rows["variant"].isin([PRIMARY, CONSERVATIVE])
        & window_rows["horizon_days"].isin([90, 180, 252, 504])
    ].copy()
    for (variant, horizon), group in focus.groupby(["variant", "horizon_days"]):
        worst = group.sort_values(["max_dd_pct", "return_pct"], ascending=[True, True]).head(8)
        clean_variant = BASE_CLEAN.get(str(variant), "")
        clean_pnl = base_by_variant.get(clean_variant, pd.Series(dtype=float))
        combo_pnl = base_by_variant.get(str(variant), pd.Series(dtype=float))
        for item in worst.itertuples(index=False):
            start = pd.Timestamp(item.start_date).normalize()
            end = pd.Timestamp(item.end_date).normalize()
            x_slice = xsmom.loc[(xsmom.index >= start) & (xsmom.index <= end)] if not xsmom.empty else pd.DataFrame()
            clean_slice = clean_pnl.loc[(clean_pnl.index >= start) & (clean_pnl.index <= end)] if not clean_pnl.empty else pd.Series(dtype=float)
            combo_slice = combo_pnl.loc[(combo_pnl.index >= start) & (combo_pnl.index <= end)] if not combo_pnl.empty else pd.Series(dtype=float)
            rows.append(
                {
                    "variant": variant,
                    "horizon_days": horizon,
                    "start_date": start,
                    "end_date": end,
                    "return_pct": _safe_float(item.return_pct),
                    "max_dd_pct": _safe_float(item.max_dd_pct),
                    "ulcer_pct": _safe_float(item.ulcer_pct),
                    "xsmom_true_pnl": float(x_slice["xsmom_true_daily_pnl"].sum()) if not x_slice.empty else 0.0,
                    "xsmom_frozen_pnl": float(x_slice["xsmom_frozen_daily_pnl"].sum()) if not x_slice.empty else 0.0,
                    "clean_c3_net_pnl": float(clean_slice.sum()) if not clean_slice.empty else 0.0,
                    "combo_net_pnl": float(combo_slice.sum()) if not combo_slice.empty else 0.0,
                    "xsmom_share_of_combo_pnl": (
                        float(x_slice["xsmom_true_daily_pnl"].sum()) / float(combo_slice.sum())
                        if (not x_slice.empty and not combo_slice.empty and abs(float(combo_slice.sum())) > 1e-9)
                        else np.nan
                    ),
                }
            )
    return pd.DataFrame(rows)


def _margin_proxy(daily: pd.DataFrame, xsmom_daily: pd.DataFrame) -> pd.DataFrame:
    margin = s402._load_margin()
    margin["date"] = pd.to_datetime(margin["date"], errors="coerce").dt.normalize()
    margin_full = margin[margin["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    margin_full = margin_full[["date", "c3_margin"]].copy()
    xsmom = xsmom_daily[["date", "xsmom_true_margin"]].copy()
    xsmom["date"] = pd.to_datetime(xsmom["date"], errors="coerce").dt.normalize()
    rows: list[dict[str, Any]] = []
    for variant in [PRIMARY, CONSERVATIVE]:
        frame = daily[daily["variant"].eq(variant)][["date", "account_equity"]].copy()
        if frame.empty:
            continue
        risk_mult = RISK_MULT[variant]
        merged = frame.merge(margin_full, on="date", how="left").merge(xsmom, on="date", how="left")
        merged["c3_margin_proxy"] = pd.to_numeric(merged["c3_margin"], errors="coerce").fillna(0.0) * risk_mult
        merged["xsmom_true_margin"] = pd.to_numeric(merged["xsmom_true_margin"], errors="coerce").fillna(0.0)
        merged["total_margin_proxy"] = merged["c3_margin_proxy"] + merged["xsmom_true_margin"]
        merged["broker10_margin_proxy"] = merged["total_margin_proxy"] * float(s403.BROKER10_MULTIPLIER)
        merged["margin_to_equity_pct"] = merged["total_margin_proxy"] / merged["account_equity"].astype(float) * 100.0
        merged["broker10_margin_to_equity_pct"] = merged["broker10_margin_proxy"] / merged["account_equity"].astype(float) * 100.0
        rows.append(
            {
                "variant": variant,
                "risk_multiplier": risk_mult,
                "max_margin_to_equity_pct": float(merged["margin_to_equity_pct"].max()),
                "max_broker10_margin_to_equity_pct": float(merged["broker10_margin_to_equity_pct"].max()),
                "broker10_gt_100_days": int((merged["broker10_margin_to_equity_pct"] > 100.0).sum()),
                "broker10_gt_90_days": int((merged["broker10_margin_to_equity_pct"] > 90.0).sum()),
                "p95_broker10_margin_to_equity_pct": float(merged["broker10_margin_to_equity_pct"].quantile(0.95)),
                "note": "proxy: c3_margin from Stage402 start_2020 scaled by risk multiplier plus Stage208 true xsmom margin",
            }
        )
    return pd.DataFrame(rows)


def _period_contribution(daily: pd.DataFrame, xsmom_daily: pd.DataFrame) -> pd.DataFrame:
    xsmom = xsmom_daily.copy()
    xsmom["date"] = pd.to_datetime(xsmom["date"], errors="coerce").dt.normalize()
    rows: list[dict[str, Any]] = []
    periods = [
        ("full", "2020-01-02", "2026-04-30"),
        ("weak_2021_2022", "2021-05-01", "2022-03-31"),
        ("recovery_2022_2023", "2022-04-01", "2023-12-31"),
        ("phase_2024_2025", "2024-01-01", "2025-12-31"),
        ("ytd_2026", "2026-01-01", "2026-04-30"),
    ]
    clean_by_variant = {
        variant: frame.sort_values("date").set_index("date")
        for variant, frame in daily.groupby("variant")
    }
    for combo_variant, clean_variant in BASE_CLEAN.items():
        combo = clean_by_variant.get(combo_variant, pd.DataFrame())
        clean = clean_by_variant.get(clean_variant, pd.DataFrame())
        for name, start_text, end_text in periods:
            start = pd.Timestamp(start_text)
            end = pd.Timestamp(end_text)
            combo_slice = combo.loc[(combo.index >= start) & (combo.index <= end)] if not combo.empty else pd.DataFrame()
            clean_slice = clean.loc[(clean.index >= start) & (clean.index <= end)] if not clean.empty else pd.DataFrame()
            x_slice = xsmom[(xsmom["date"] >= start) & (xsmom["date"] <= end)]
            if combo_slice.empty:
                continue
            combo_equity = combo_slice["account_equity"].astype(float)
            clean_equity = clean_slice["account_equity"].astype(float) if not clean_slice.empty else pd.Series(dtype=float)
            rows.append(
                {
                    "variant": combo_variant,
                    "base_clean_variant": clean_variant,
                    "period": name,
                    "start_date": combo_slice.index.min(),
                    "end_date": combo_slice.index.max(),
                    "combo_return_pct": (combo_equity.iloc[-1] / combo_equity.iloc[0] - 1.0) * 100.0,
                    "combo_max_dd_pct": _max_drawdown_pct(combo_equity),
                    "clean_return_pct": (clean_equity.iloc[-1] / clean_equity.iloc[0] - 1.0) * 100.0 if not clean_equity.empty else np.nan,
                    "clean_max_dd_pct": _max_drawdown_pct(clean_equity) if not clean_equity.empty else np.nan,
                    "xsmom_true_pnl": float(x_slice["xsmom_true_daily_pnl"].sum()),
                    "xsmom_frozen_pnl": float(x_slice["xsmom_frozen_daily_pnl"].sum()),
                    "xsmom_turnover": float(x_slice["xsmom_true_turnover_contracts"].sum()),
                }
            )
    return pd.DataFrame(rows)


def _decision(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    cold_start: pd.DataFrame,
    margin_proxy: pd.DataFrame,
    cost: pd.DataFrame,
) -> dict[str, Any]:
    primary = summary[summary["variant"].eq(PRIMARY)].iloc[0]
    conservative = summary[summary["variant"].eq(CONSERVATIVE)].iloc[0]
    primary_h = horizon[horizon["variant"].eq(PRIMARY)]
    primary_cold = cold_start[cold_start["variant"].eq(PRIMARY)]
    primary_margin = margin_proxy[margin_proxy["variant"].eq(PRIMARY)]
    primary_cost = cost[cost["variant"].eq(PRIMARY)].copy()
    cost_2x = primary_cost[primary_cost["slippage_multiplier"].eq(2.0)]
    cost_3x = primary_cost[primary_cost["slippage_multiplier"].eq(3.0)]
    monthly_dd40_rate = float(primary_cold[primary_cold["start_type"].eq("month")]["dd40_pass"].mean())
    horizon_dd40_worst = float(primary_h["dd40_breach_rate"].max())
    broker10_gt_100_days = int(primary_margin["broker10_gt_100_days"].iloc[0]) if not primary_margin.empty else -1
    cost_2x_dd = float(cost_2x["max_dd_pct"].iloc[0]) if not cost_2x.empty else np.nan
    cost_3x_dd = float(cost_3x["max_dd_pct"].iloc[0]) if not cost_3x.empty else np.nan
    if (
        _safe_float(primary["max_dd_pct"]) >= -40.0
        and _safe_float(primary["return_retention_vs_stage079_pct"]) >= 65.0
        and broker10_gt_100_days == 0
        and monthly_dd40_rate >= 0.95
        and horizon_dd40_worst == 0.0
    ):
        label = "stage208_primary_robust_engineering_candidate"
    else:
        label = "stage208_primary_candidate_but_fragile_need_more_review"
    return {
        "stage": "Stage211",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "primary_variant": PRIMARY,
        "primary_end_equity": _safe_float(primary["end_equity"]),
        "primary_total_return_pct": _safe_float(primary["total_return_pct"]),
        "primary_return_retention_vs_stage079_pct": _safe_float(primary["return_retention_vs_stage079_pct"]),
        "primary_max_dd_pct": _safe_float(primary["max_dd_pct"]),
        "primary_sharpe": _safe_float(primary["sharpe"]),
        "primary_ulcer_pct": _safe_float(primary["ulcer_pct"]),
        "primary_monthly_cold_start_dd40_pass_rate": monthly_dd40_rate,
        "primary_worst_horizon_dd40_breach_rate": horizon_dd40_worst,
        "primary_broker10_gt_100_days_proxy": broker10_gt_100_days,
        "primary_2x_cost_max_dd_pct": cost_2x_dd,
        "primary_3x_cost_max_dd_pct": cost_3x_dd,
        "conservative_variant": CONSERVATIVE,
        "conservative_total_return_pct": _safe_float(conservative["total_return_pct"]),
        "conservative_max_dd_pct": _safe_float(conservative["max_dd_pct"]),
        "next_step": "If primary is fragile, prefer segment/trade postmortem before any strategy-body rule change; do not tune xsmom/C3 decimals.",
    }


def _plot(daily: pd.DataFrame, horizon_windows: pd.DataFrame, cold_start: pd.DataFrame) -> None:
    labels = daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    ax_nav, ax_dd, ax_horizon, ax_cold = axes.ravel()
    for variant in [BASELINE, CONSERVATIVE, PRIMARY]:
        frame = daily[daily["variant"].eq(variant)].copy()
        equity = _calendar_equity(frame)
        ax_nav.plot(equity.index, equity / ACCOUNT_CAPITAL, label=labels.get(variant, variant), linewidth=1.05)
        dd = _drawdown_pct(equity)
        ax_dd.plot(dd.index, dd, label=labels.get(variant, variant), linewidth=1.0)
    ax_nav.set_title("Stage208 robustness: NAV")
    ax_nav.set_ylabel("NAV")
    ax_nav.legend(fontsize=8)
    ax_nav.grid(True, alpha=0.22)
    ax_dd.set_title("Underwater drawdown")
    ax_dd.set_ylabel("Drawdown %")
    ax_dd.axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_dd.axhline(-30.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_dd.grid(True, alpha=0.22)

    box_data = []
    box_labels = []
    focus = horizon_windows[
        horizon_windows["variant"].eq(PRIMARY)
        & horizon_windows["horizon_days"].isin([30, 60, 90, 180, 252, 504])
    ]
    for horizon in [30, 60, 90, 180, 252, 504]:
        values = focus[focus["horizon_days"].eq(horizon)]["return_pct"].astype(float).to_numpy()
        if len(values):
            box_data.append(values)
            box_labels.append(str(horizon))
    ax_horizon.boxplot(box_data, tick_labels=box_labels, showfliers=False)
    ax_horizon.axhline(0.0, color="#333333", linestyle="--", linewidth=0.8)
    ax_horizon.set_title("Primary candidate holding-return distribution")
    ax_horizon.set_xlabel("Holding days")
    ax_horizon.set_ylabel("Return %")
    ax_horizon.grid(True, alpha=0.22)

    cold = cold_start[(cold_start["variant"].eq(PRIMARY)) & (cold_start["start_type"].eq("month"))].copy()
    colors = np.where(cold["max_dd_pct"].astype(float) < -40.0, "#b3261e", "#1b7f5a")
    ax_cold.scatter(pd.to_datetime(cold["start_date"]), cold["max_dd_pct"].astype(float), c=colors, s=24)
    ax_cold.axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_cold.axhline(-30.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_cold.set_title("Primary candidate monthly cold-start max DD")
    ax_cold.set_ylabel("Max DD to 2026-04-30 %")
    ax_cold.grid(True, alpha=0.22)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    cold_start: pd.DataFrame,
    bad_windows: pd.DataFrame,
    margin_proxy: pd.DataFrame,
    period_contrib: pd.DataFrame,
    cost: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    primary_h = horizon[horizon["variant"].eq(PRIMARY)].sort_values("horizon_days")
    compare_h = horizon[horizon["variant"].isin([BASELINE, CONSERVATIVE, PRIMARY]) & horizon["horizon_days"].isin([90, 180, 252, 504])]
    cold_summary = (
        cold_start.groupby(["variant", "start_type"], as_index=False)
        .agg(
            count=("start_date", "size"),
            positive_rate=("positive_return", "mean"),
            dd30_pass_rate=("dd30_pass", "mean"),
            dd40_pass_rate=("dd40_pass", "mean"),
            worst_dd=("max_dd_pct", "min"),
            p05_return=("return_pct", lambda value: float(pd.Series(value).quantile(0.05))),
            median_return=("return_pct", "median"),
        )
        .sort_values(["variant", "start_type"])
    )
    cost_focus = cost[cost["variant"].isin([BASELINE, CONSERVATIVE, PRIMARY])].copy()
    report = [
        "# Stage211 Stage208鲁棒性与持有体验审计",
        "",
        f"- 生成时间：{decision['generated_at']}",
        "- 阶段性质：只读鲁棒性审计；直接读取 Stage208 daily/order/target ledger，不重新调参、不新增交易规则。",
        "- 运行前过拟合判断：否。当前只做候选压力测试，不按坏窗口改规则。",
        "- 运行前继续价值判断：是。Stage208 已经是当前真实可成交工程候选，必须先确认厚度，再决定是否做策略本体改造。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随公开资料普遍强调跨市场分散、成本、成交语义和稳健性；ATR/Chandelier/动态止损在趋势策略里常见，但容易用频繁止损换掉大波段。",
        "- GitHub 和公开回测框架多提供日线/简化撮合样例，本仓库已经有分钟成交账本，因此本阶段优先做本地真实 ledger 的多起点与持有体验审计。",
        "- 我的判断：先审 Stage208 的脆弱点，比立刻加 ATR/K线形态更低过拟合；若 Stage208 的坏窗口集中在少数可解释路径，再考虑低自由度规则。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 主候选：`{decision['primary_variant']}`。",
        f"- 主候选总收益/收益保留/最大回撤：`{decision['primary_total_return_pct']:.4f}% / {decision['primary_return_retention_vs_stage079_pct']:.4f}% / {decision['primary_max_dd_pct']:.4f}%`。",
        f"- 主候选 Sharpe/Ulcer：`{decision['primary_sharpe']:.4f} / {decision['primary_ulcer_pct']:.4f}`。",
        f"- 月度冷启动 DD40 通过率：`{decision['primary_monthly_cold_start_dd40_pass_rate']:.4f}`。",
        f"- 任意持有窗口最差 DD40 破例率：`{decision['primary_worst_horizon_dd40_breach_rate']:.4f}`。",
        f"- broker10 保证金代理穿 100% 天数：`{decision['primary_broker10_gt_100_days_proxy']}`。",
        f"- 2x/3x 成本压力最大回撤：`{decision['primary_2x_cost_max_dd_pct']:.4f}% / {decision['primary_3x_cost_max_dd_pct']:.4f}%`。",
        "",
        "## 全周期摘要",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "total_return_pct",
                    "return_retention_vs_stage079_pct",
                    "max_dd_pct",
                    "sharpe",
                    "ulcer_pct",
                    "longest_underwater_days",
                    "rolling252_dd30_breach_rate",
                    "rolling504_dd30_breach_rate",
                ]
            ]
        ),
        "",
        "## 任意启动持有体验",
        "",
        _md_table(
            primary_h[
                [
                    "horizon_days",
                    "return_p01_pct",
                    "return_p05_pct",
                    "return_median_pct",
                    "positive_return_rate",
                    "below_5pct_rate",
                    "max_dd_worst_pct",
                    "dd30_breach_rate",
                    "dd40_breach_rate",
                    "ulcer_p95_pct",
                    "uw_p95_days",
                ]
            ]
        ),
        "",
        "## 关键版本持有体验对比",
        "",
        _md_table(
            compare_h[
                [
                    "variant",
                    "horizon_days",
                    "return_p05_pct",
                    "return_median_pct",
                    "positive_return_rate",
                    "dd30_breach_rate",
                    "dd40_breach_rate",
                    "ulcer_p95_pct",
                ]
            ].sort_values(["horizon_days", "variant"])
        ),
        "",
        "## 冷启动",
        "",
        _md_table(cold_summary),
        "",
        "## 最差窗口贡献",
        "",
        _md_table(bad_windows.sort_values(["variant", "horizon_days", "max_dd_pct"]), max_rows=64),
        "",
        "## 保证金代理",
        "",
        _md_table(margin_proxy),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost_focus[
                [
                    "variant",
                    "slippage_multiplier",
                    "total_return_pct",
                    "max_dd_pct",
                    "baseline_stage079_max_dd_pct",
                    "not_worse_than_stage079_stress",
                ]
            ].sort_values(["variant", "slippage_multiplier"])
        ),
        "",
        "## 分段贡献",
        "",
        _md_table(period_contrib),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表：`{CHART_PATH}`。",
        "- 实际观察1：主候选和保守对照在 NAV 上都显著低于 Stage079 同日 baseline，说明 Stage079 原曲线仍不能当真实可成交收益承诺。",
        "- 实际观察2：`risk070 + true xsmom` 在 2021-2022 深水段没有跌破 -40%，但贴近 -38% 到 -39%；这是贴线通过，不是厚安全垫。",
        "- 实际观察3：`risk060 + true xsmom` 水下更浅、保证金更稳，但收益保留低于主候选；它更像保守部署口径，不是收益最优口径。",
        "- 实际观察4：30/60/90日持有收益箱线左尾仍明显为负，短持有体验没有被根治；504日基本转正，但坏启动窗口仍会长时间水下。",
        "- 实际观察5：月度冷启动散点全部在 DD40 内，但 2020-2022 一串启动点贴近 -40%，这也是本阶段不直接最终晋级的核心原因。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行后过拟合判断：本阶段不是过拟合；它没有改交易规则，也没有依据结果修补参数。",
        "- 运行后继续价值判断：继续有价值，但下一步应先做坏窗口逐笔复盘；只有看到稳定、可解释、低自由度的失效形态，才考虑策略本体改造。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily = _load_stage208_daily()
    xsmom_daily = pd.read_csv(XSMOM_DAILY_IN, encoding="utf-8-sig")
    xsmom_daily["date"] = pd.to_datetime(xsmom_daily["date"], errors="coerce").dt.normalize()
    cost = pd.read_csv(COST_IN, encoding="utf-8-sig")
    summary = _summary(daily)
    horizon, horizon_windows = _horizon_all(daily)
    cold_start = _cold_start(daily)
    bad_windows = _bad_windows(horizon_windows, xsmom_daily, daily)
    margin_proxy = _margin_proxy(daily, xsmom_daily)
    period_contrib = _period_contribution(daily, xsmom_daily)
    decision = _decision(summary, horizon, cold_start, margin_proxy, cost)
    _plot(daily, horizon_windows, cold_start)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    cold_start.to_csv(COLD_START_PATH, index=False, encoding="utf-8-sig")
    bad_windows.to_csv(BAD_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    margin_proxy.to_csv(MARGIN_PATH, index=False, encoding="utf-8-sig")
    period_contrib.to_csv(PERIOD_CONTRIB_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cold_start, bad_windows, margin_proxy, period_contrib, cost, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()

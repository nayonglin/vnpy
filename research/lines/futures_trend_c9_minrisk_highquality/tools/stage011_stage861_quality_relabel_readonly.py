from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage011"
MODEL_TAG = "stage011_stage861_quality_relabel_readonly_v1"
OUTPUT_PREFIX = "qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage010_authoritative_minute_coverage_audit as s010
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage011_stage861_quality_relabel_readonly"
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
WINDOW_MINUTES = 30
HEAT_R = 0.50
PER_PAGE = 4
MAX_ATLAS_ROWS = 24

STAGE010_FEATURES = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_coverage_features_stage010_authoritative_minute_coverage_audit_v1.csv"
)
STAGE010_CURVE = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_stage010_authoritative_minute_coverage_audit_v1.csv"
)
STAGE010_SUMMARY = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_stage010_authoritative_minute_coverage_audit_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
QUALITY_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_bucket_stats_{MODEL_TAG}.csv"
FIRST_BAR_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_first_bar_bucket_stats_{MODEL_TAG}.csv"
YEAR_QUALITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_quality_stats_{MODEL_TAG}.csv"
SOURCE_QUALITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_quality_crosstab_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
CONTRIB_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_chart_{MODEL_TAG}.png"
YEAR_QUALITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_quality_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s010._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    return data.to_markdown(index=False)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s010._safe_float(value, default=default)


def _normalize_day(value: Any) -> pd.Timestamp:
    return s010._normalize_day(value)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s010._drawdown_pct(equity)


def _load_curve() -> pd.DataFrame:
    if not STAGE010_CURVE.exists():
        raise RuntimeError(f"missing Stage010 curve: {STAGE010_CURVE}")
    curve = pd.read_csv(STAGE010_CURVE, encoding="utf-8-sig")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce", format="mixed").dt.normalize()
    curve = curve[curve["date"].between(START, END)].copy().sort_values("date")
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    return curve


def _load_summary() -> pd.DataFrame:
    if not STAGE010_SUMMARY.exists():
        return pd.DataFrame()
    return pd.read_csv(STAGE010_SUMMARY, encoding="utf-8-sig")


def _label_quality(row: pd.Series) -> str:
    covered = int(_safe_float(row.get("stage861_covered"), 0.0)) == 1
    minute_bars = int(_safe_float(row.get("stage861_entry_day_minute_bars"), 0.0))
    risk_valid = int(_safe_float(row.get("risk_valid"), 0.0)) == 1
    directional = _safe_float(row.get("first_30m_directional_r"))
    mae = _safe_float(row.get("first_30m_mae_r"))
    if not covered or minute_bars <= 0:
        return "missing_stage861_30m"
    if not risk_valid or not np.isfinite(directional) or not np.isfinite(mae):
        return "risk_or_feature_invalid"
    if directional <= 0:
        return "no_follow_30m"
    if mae > HEAT_R:
        return "adverse_heat_30m"
    return "clean_continuation_30m"


def _day_for_row(full_groups: dict[str, pd.DataFrame], row: pd.Series) -> pd.DataFrame:
    vt_symbol = str(row.get("vt_symbol"))
    entry_day = _normalize_day(row.get("entry_date"))
    if pd.isna(entry_day):
        entry_day = _normalize_day(row.get("entry_day"))
    return s010._day_for_symbol(full_groups, vt_symbol, entry_day)


def _first_bar_features(row: pd.Series, full_groups: dict[str, pd.DataFrame]) -> dict[str, Any]:
    day = _day_for_row(full_groups, row)
    entry = _safe_float(row.get("entry_price"))
    risk = _safe_float(row.get("risk_price"))
    direction = str(row.get("direction"))
    if day.empty:
        return {
            "first_bar_label": "missing_stage861_first_bar",
            "first_bar_directional_r": np.nan,
            "first_bar_mfe_r": np.nan,
            "first_bar_mae_r": np.nan,
            "first_bar_body_directional_r": np.nan,
        }
    if not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return {
            "first_bar_label": "risk_or_feature_invalid",
            "first_bar_directional_r": np.nan,
            "first_bar_mfe_r": np.nan,
            "first_bar_mae_r": np.nan,
            "first_bar_body_directional_r": np.nan,
        }
    first = day.iloc[0]
    close = _safe_float(first.get("close"))
    open_ = _safe_float(first.get("open"))
    high = _safe_float(first.get("high"))
    low = _safe_float(first.get("low"))
    if direction == "short":
        directional = (entry - close) / risk if np.isfinite(close) else np.nan
        body = (open_ - close) / risk if np.isfinite(open_) and np.isfinite(close) else np.nan
        mfe = (entry - low) / risk if np.isfinite(low) else np.nan
        mae = (high - entry) / risk if np.isfinite(high) else np.nan
    else:
        directional = (close - entry) / risk if np.isfinite(close) else np.nan
        body = (close - open_) / risk if np.isfinite(open_) and np.isfinite(close) else np.nan
        mfe = (high - entry) / risk if np.isfinite(high) else np.nan
        mae = (entry - low) / risk if np.isfinite(low) else np.nan
    mfe = max(0.0, mfe) if np.isfinite(mfe) else np.nan
    mae = max(0.0, mae) if np.isfinite(mae) else np.nan
    if not np.isfinite(directional):
        label = "risk_or_feature_invalid"
    elif directional > 0:
        label = "first_bar_follow_close"
    elif directional < 0:
        label = "first_bar_adverse_close"
    else:
        label = "first_bar_flat_close"
    return {
        "first_bar_label": label,
        "first_bar_directional_r": directional,
        "first_bar_mfe_r": mfe,
        "first_bar_mae_r": mae,
        "first_bar_body_directional_r": body,
    }


def _load_features(full_groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if not STAGE010_FEATURES.exists():
        raise RuntimeError(f"missing Stage010 features: {STAGE010_FEATURES}")
    data = pd.read_csv(STAGE010_FEATURES, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date", "entry_day", "exit_date_ts"]:
        if column in data.columns:
            data[column] = pd.to_datetime(data[column], errors="coerce", format="mixed").dt.normalize()
    numeric_cols = [
        "realized_pnl",
        "r_multiple",
        "volume",
        "size",
        "risk_amount",
        "entry_price",
        "exit_price",
        "risk_price",
        "risk_valid",
        "stage861_covered",
        "legacy_covered",
        "stage861_entry_day_minute_bars",
        "legacy_entry_day_minute_bars",
        "first_30m_directional_r",
        "first_30m_mfe_r",
        "first_30m_mae_r",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "clean_continuation_30m",
        "no_follow_30m",
    ]
    for column in numeric_cols:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["quality_label_stage861"] = data.apply(_label_quality, axis=1)
    first_bar = pd.DataFrame([_first_bar_features(row, full_groups) for _, row in data.iterrows()])
    data = pd.concat([data.reset_index(drop=True), first_bar], axis=1)
    data["entry_year"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.year
    data["exit_year"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.year
    data["positive_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").clip(lower=0.0)
    data["negative_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").clip(upper=0.0)
    data["source_quality_bucket"] = data["coverage_bucket"].astype(str) + "__" + data["quality_label_stage861"].astype(str)
    return data


def _bucket_stats(data: pd.DataFrame, label_col: str, label_name: str) -> pd.DataFrame:
    total_pnl = float(data["realized_pnl"].fillna(0.0).sum())
    total_positive = float(data["positive_pnl"].fillna(0.0).sum())
    total_negative_abs = abs(float(data["negative_pnl"].fillna(0.0).sum()))
    rows: list[dict[str, Any]] = []
    for label, group in data.groupby(label_col, dropna=False):
        pnl = float(group["realized_pnl"].fillna(0.0).sum())
        positive = float(group["positive_pnl"].fillna(0.0).sum())
        negative = float(group["negative_pnl"].fillna(0.0).sum())
        rows.append(
            {
                label_name: str(label),
                "lots": int(len(group)),
                "products": int(group["product"].astype(str).nunique()) if "product" in group.columns else 0,
                "years": int(group["entry_year"].nunique()),
                "net_pnl": pnl,
                "net_pnl_share_pct": pnl / total_pnl * 100.0 if total_pnl else np.nan,
                "positive_pnl": positive,
                "positive_pnl_share_pct": positive / total_positive * 100.0 if total_positive else np.nan,
                "negative_pnl": negative,
                "negative_pnl_abs_share_pct": abs(negative) / total_negative_abs * 100.0 if total_negative_abs else np.nan,
                "median_r_multiple": float(group["r_multiple"].median()),
                "win_rate_pct": float((group["realized_pnl"] > 0).mean() * 100.0),
                "median_first_30m_directional_r": float(group["first_30m_directional_r"].median()),
                "median_first_30m_mae_r": float(group["first_30m_mae_r"].median()),
                "median_first_bar_directional_r": float(group["first_bar_directional_r"].median()),
                "max_single_win": float(group["realized_pnl"].max()),
                "max_single_loss": float(group["realized_pnl"].min()),
            }
        )
    rows.append(
        {
            label_name: "ALL",
            "lots": int(len(data)),
            "products": int(data["product"].astype(str).nunique()) if "product" in data.columns else 0,
            "years": int(data["entry_year"].nunique()),
            "net_pnl": total_pnl,
            "net_pnl_share_pct": 100.0,
            "positive_pnl": total_positive,
            "positive_pnl_share_pct": 100.0,
            "negative_pnl": float(data["negative_pnl"].fillna(0.0).sum()),
            "negative_pnl_abs_share_pct": 100.0,
            "median_r_multiple": float(data["r_multiple"].median()),
            "win_rate_pct": float((data["realized_pnl"] > 0).mean() * 100.0),
            "median_first_30m_directional_r": float(data["first_30m_directional_r"].median()),
            "median_first_30m_mae_r": float(data["first_30m_mae_r"].median()),
            "median_first_bar_directional_r": float(data["first_bar_directional_r"].median()),
            "max_single_win": float(data["realized_pnl"].max()),
            "max_single_loss": float(data["realized_pnl"].min()),
        }
    )
    frame = pd.DataFrame(rows)
    order = {
        "clean_continuation_30m": 0,
        "adverse_heat_30m": 1,
        "no_follow_30m": 2,
        "risk_or_feature_invalid": 3,
        "missing_stage861_30m": 4,
        "first_bar_follow_close": 0,
        "first_bar_flat_close": 1,
        "first_bar_adverse_close": 2,
        "missing_stage861_first_bar": 3,
        "ALL": 99,
    }
    frame["_order"] = frame[label_name].map(order).fillna(50)
    return frame.sort_values(["_order", label_name]).drop(columns=["_order"]).reset_index(drop=True)


def _year_quality_stats(data: pd.DataFrame) -> pd.DataFrame:
    return (
        data.groupby(["entry_year", "quality_label_stage861"], dropna=False)
        .agg(
            lots=("lot_id", "size"),
            products=("product", "nunique"),
            net_pnl=("realized_pnl", "sum"),
            positive_pnl=("positive_pnl", "sum"),
            negative_pnl=("negative_pnl", "sum"),
            win_rate_pct=("realized_pnl", lambda x: float((pd.to_numeric(x, errors="coerce") > 0).mean() * 100.0)),
            median_first_30m_directional_r=("first_30m_directional_r", "median"),
            median_first_30m_mae_r=("first_30m_mae_r", "median"),
        )
        .reset_index()
        .sort_values(["entry_year", "quality_label_stage861"])
    )


def _source_quality_crosstab(data: pd.DataFrame) -> pd.DataFrame:
    return (
        data.groupby(["coverage_bucket", "quality_label_stage861"], dropna=False)
        .agg(
            lots=("lot_id", "size"),
            net_pnl=("realized_pnl", "sum"),
            positive_pnl=("positive_pnl", "sum"),
            negative_pnl=("negative_pnl", "sum"),
            median_first_30m_directional_r=("first_30m_directional_r", "median"),
        )
        .reset_index()
        .sort_values(["coverage_bucket", "quality_label_stage861"])
    )


def _contribution_curve(data: pd.DataFrame) -> pd.DataFrame:
    calendar = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
    selectors: dict[str, pd.Series] = {
        "all_closed_lots_reference": data.index == data.index,
        "clean_continuation_30m": data["quality_label_stage861"].eq("clean_continuation_30m"),
        "adverse_heat_30m": data["quality_label_stage861"].eq("adverse_heat_30m"),
        "no_follow_30m": data["quality_label_stage861"].eq("no_follow_30m"),
        "risk_or_feature_invalid": data["quality_label_stage861"].eq("risk_or_feature_invalid"),
        "missing_stage861_30m": data["quality_label_stage861"].eq("missing_stage861_30m"),
        "all_except_no_follow": ~data["quality_label_stage861"].eq("no_follow_30m"),
        "first_bar_follow_close": data["first_bar_label"].eq("first_bar_follow_close"),
        "first_bar_adverse_close": data["first_bar_label"].eq("first_bar_adverse_close"),
    }
    rows: list[pd.DataFrame] = []
    for label, mask in selectors.items():
        part = data[mask].copy()
        daily = (
            part.groupby("exit_date", dropna=True)["realized_pnl"].sum().reset_index().rename(columns={"exit_date": "date"})
            if not part.empty
            else pd.DataFrame(columns=["date", "realized_pnl"])
        )
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        curve = calendar.merge(daily, on="date", how="left")
        curve["realized_pnl"] = pd.to_numeric(curve["realized_pnl"], errors="coerce").fillna(0.0)
        curve["cumulative_realized_pnl"] = curve["realized_pnl"].cumsum()
        curve["contribution_drawdown_cash"] = curve["cumulative_realized_pnl"] - curve["cumulative_realized_pnl"].cummax()
        curve["diagnostic_equity"] = CAPITAL + curve["cumulative_realized_pnl"]
        curve["diagnostic_drawdown_pct"] = _drawdown_pct(curve["diagnostic_equity"])
        curve["bucket"] = label
        curve["stage"] = STAGE
        curve["model_tag"] = MODEL_TAG
        curve["note"] = "closed-lot contribution curve only; not executable mark-to-market backtest"
        rows.append(curve)
    return pd.concat(rows, ignore_index=True, sort=False)


def _summary(curve: pd.DataFrame, data: pd.DataFrame, quality_stats: pd.DataFrame, first_bar_stats: pd.DataFrame) -> pd.DataFrame:
    official_end = float(pd.to_numeric(curve["account_equity"], errors="coerce").iloc[-1])
    def _stat(label: str, column: str, stats: pd.DataFrame = quality_stats) -> float:
        hit = stats[stats.iloc[:, 0].eq(label)]
        if hit.empty:
            return np.nan
        return _safe_float(hit[column].iloc[0])

    no_follow = data[data["quality_label_stage861"].eq("no_follow_30m")]
    no_follow_year = (
        no_follow.groupby("entry_year", dropna=False)["realized_pnl"].sum().reset_index()
        if not no_follow.empty
        else pd.DataFrame(columns=["entry_year", "realized_pnl"])
    )
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "window_start": START.date().isoformat(),
        "window_end": END.date().isoformat(),
        "official_end_equity": official_end,
        "official_total_return_pct": (official_end / CAPITAL - 1.0) * 100.0,
        "official_max_dd_pct": float(pd.to_numeric(curve["drawdown_pct"], errors="coerce").min()),
        "official_sharpe": _safe_float(_load_summary().get("sharpe", pd.Series([np.nan])).iloc[0]) if not _load_summary().empty else np.nan,
        "official_total_slippage": _safe_float(_load_summary().get("total_slippage", pd.Series([np.nan])).iloc[0]) if not _load_summary().empty else np.nan,
        "official_total_trade_count": _safe_float(_load_summary().get("total_trade_count", pd.Series([np.nan])).iloc[0]) if not _load_summary().empty else np.nan,
        "official_win_rate_pct": _safe_float(_load_summary().get("nonzero_daily_win_rate_pct", pd.Series([np.nan])).iloc[0]) if not _load_summary().empty else np.nan,
        "official_broker10_peak_pct": float(pd.to_numeric(curve["broker10_margin_to_equity_pct"], errors="coerce").max()),
        "closed_lots": int(len(data)),
        "stage861_covered_lots": int(pd.to_numeric(data["stage861_covered"], errors="coerce").fillna(0).sum()),
        "hard_missing_lots": int(data["quality_label_stage861"].eq("missing_stage861_30m").sum()),
        "risk_or_feature_invalid_lots": int(data["quality_label_stage861"].eq("risk_or_feature_invalid").sum()),
        "clean_lots": int(data["quality_label_stage861"].eq("clean_continuation_30m").sum()),
        "clean_net_pnl": _stat("clean_continuation_30m", "net_pnl"),
        "clean_positive_pnl_share_pct": _stat("clean_continuation_30m", "positive_pnl_share_pct"),
        "clean_negative_pnl_abs_share_pct": _stat("clean_continuation_30m", "negative_pnl_abs_share_pct"),
        "no_follow_lots": int(len(no_follow)),
        "no_follow_net_pnl": _stat("no_follow_30m", "net_pnl"),
        "no_follow_positive_pnl_share_pct": _stat("no_follow_30m", "positive_pnl_share_pct"),
        "no_follow_negative_pnl_abs_share_pct": _stat("no_follow_30m", "negative_pnl_abs_share_pct"),
        "no_follow_positive_years": int((pd.to_numeric(no_follow_year["realized_pnl"], errors="coerce") > 0).sum()) if not no_follow_year.empty else 0,
        "first_bar_follow_lots": int(data["first_bar_label"].eq("first_bar_follow_close").sum()),
        "first_bar_follow_net_pnl": _stat("first_bar_follow_close", "net_pnl", first_bar_stats),
        "first_bar_adverse_lots": int(data["first_bar_label"].eq("first_bar_adverse_close").sum()),
        "first_bar_adverse_net_pnl": _stat("first_bar_adverse_close", "net_pnl", first_bar_stats),
        "decision": "stage011_stage861_relabel_readonly_no_trade_rule_yet",
    }
    return pd.DataFrame([row])


def _plot_path(curve: pd.DataFrame, data: pd.DataFrame) -> None:
    plot = curve.copy().sort_values("date")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    axes[0].plot(plot["date"], plot["account_equity"], color="#2563eb", label="official C9/15w")
    axes[1].plot(plot["date"], plot["drawdown_pct"], color="#dc2626", label="drawdown")
    axes[2].plot(plot["date"], plot["broker10_margin_to_equity_pct"], color="#0f766e", label="broker10")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9, alpha=0.8)
    marks = pd.concat(
        [
            data[data["quality_label_stage861"].eq("clean_continuation_30m")].nlargest(5, "realized_pnl"),
            data[data["quality_label_stage861"].eq("no_follow_30m")].nsmallest(6, "realized_pnl"),
            data[data["quality_label_stage861"].eq("no_follow_30m")].nlargest(4, "realized_pnl"),
            data[data["quality_label_stage861"].eq("adverse_heat_30m")].nlargest(4, "realized_pnl"),
            data[data["quality_label_stage861"].eq("missing_stage861_30m")],
        ],
        ignore_index=True,
        sort=False,
    ).drop_duplicates(["lot_id", "vt_symbol", "entry_date"])
    colors = {
        "clean_continuation_30m": "#16a34a",
        "adverse_heat_30m": "#f59e0b",
        "no_follow_30m": "#dc2626",
        "risk_or_feature_invalid": "#a855f7",
        "missing_stage861_30m": "#111827",
    }
    seen: set[str] = set()
    for _, row in marks.iterrows():
        date = _normalize_day(row.get("entry_date"))
        label = str(row.get("quality_label_stage861"))
        legend = label if label not in seen else None
        seen.add(label)
        for ax in axes:
            ax.axvline(date, color=colors.get(label, "#64748b"), alpha=0.23, linewidth=1.05, label=legend)
            legend = None
    axes[0].set_title("Stage011 official C9/15w path with Stage861 quality labels")
    axes[1].set_title("Official drawdown")
    axes[2].set_title("Official broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.24)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_contribution(contrib: pd.DataFrame) -> None:
    colors = {
        "all_closed_lots_reference": "#111827",
        "clean_continuation_30m": "#16a34a",
        "adverse_heat_30m": "#f59e0b",
        "no_follow_30m": "#dc2626",
        "risk_or_feature_invalid": "#a855f7",
        "missing_stage861_30m": "#64748b",
        "all_except_no_follow": "#2563eb",
        "first_bar_follow_close": "#0f766e",
        "first_bar_adverse_close": "#ea580c",
    }
    data = contrib.copy()
    fig, axes = plt.subplots(2, 1, figsize=(18, 9), sharex=True, constrained_layout=True)
    for label, group in data.groupby("bucket"):
        group = group.sort_values("date")
        linewidth = 1.7 if label in {"all_closed_lots_reference", "all_except_no_follow"} else 1.15
        alpha = 0.95 if label in {"all_closed_lots_reference", "all_except_no_follow"} else 0.65
        axes[0].plot(group["date"], group["cumulative_realized_pnl"], label=label, color=colors.get(label), linewidth=linewidth, alpha=alpha)
        axes[1].plot(group["date"], group["contribution_drawdown_cash"], label=label, color=colors.get(label), linewidth=linewidth, alpha=alpha)
    axes[0].set_title("Stage011 closed-lot cumulative PnL by Stage861 quality label")
    axes[1].set_title("Contribution drawdown in cash")
    for ax in axes:
        ax.grid(True, alpha=0.24)
        ax.legend(loc="best", ncols=2)
    fig.savefig(CONTRIB_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_year_quality(year_quality: pd.DataFrame) -> None:
    if year_quality.empty:
        return
    labels = [
        "clean_continuation_30m",
        "adverse_heat_30m",
        "no_follow_30m",
        "risk_or_feature_invalid",
        "missing_stage861_30m",
    ]
    colors = {
        "clean_continuation_30m": "#16a34a",
        "adverse_heat_30m": "#f59e0b",
        "no_follow_30m": "#dc2626",
        "risk_or_feature_invalid": "#a855f7",
        "missing_stage861_30m": "#64748b",
    }
    years = sorted(int(year) for year in year_quality["entry_year"].dropna().unique())
    x = np.arange(len(years))
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    bottom_lots = np.zeros(len(years))
    bottom_pos = np.zeros(len(years))
    bottom_neg = np.zeros(len(years))
    for label in labels:
        part = year_quality[year_quality["quality_label_stage861"].eq(label)].set_index("entry_year")
        lots = np.array([_safe_float(part.loc[year, "lots"], 0.0) if year in part.index else 0.0 for year in years])
        axes[0].bar(x, lots, bottom=bottom_lots, color=colors.get(label), label=label)
        bottom_lots += lots
        pnl = np.array([_safe_float(part.loc[year, "net_pnl"], 0.0) if year in part.index else 0.0 for year in years])
        pos = np.clip(pnl, 0.0, None)
        neg = np.clip(pnl, None, 0.0)
        axes[1].bar(x, pos, bottom=bottom_pos, color=colors.get(label), alpha=0.82, label=label if label not in axes[1].get_legend_handles_labels()[1] else None)
        axes[1].bar(x, neg, bottom=bottom_neg, color=colors.get(label), alpha=0.82)
        bottom_pos += pos
        bottom_neg += neg
    axes[0].set_title("Stage861 quality lots by entry year")
    axes[1].set_title("Stage861 quality net PnL by entry year")
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([str(year) for year in years])
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.24)
        ax.legend(loc="best", ncols=2)
    fig.savefig(YEAR_QUALITY_CHART_OUT, dpi=170)
    plt.close(fig)


def _select_atlas(data: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for label in ["clean_continuation_30m", "no_follow_30m", "adverse_heat_30m"]:
        part = data[data["quality_label_stage861"].eq(label)].copy()
        if not part.empty:
            parts.append(part.nlargest(4, "realized_pnl"))
            parts.append(part.nsmallest(4, "realized_pnl"))
    repaired = data[data["coverage_bucket"].eq("repaired_by_stage861_full")].copy()
    if not repaired.empty:
        parts.append(repaired.nlargest(5, "realized_pnl"))
    hard = data[data["quality_label_stage861"].isin(["missing_stage861_30m", "risk_or_feature_invalid"])].copy()
    if not hard.empty:
        parts.append(hard.nlargest(4, "realized_pnl"))
        parts.append(hard.nsmallest(4, "realized_pnl"))
    if not parts:
        return pd.DataFrame()
    return (
        pd.concat(parts, ignore_index=True, sort=False)
        .drop_duplicates(["lot_id", "vt_symbol", "entry_date", "direction"])
        .head(MAX_ATLAS_ROWS)
    )


def _line_prices(row: pd.Series) -> dict[str, float]:
    entry = _safe_float(row.get("entry_price"))
    risk = _safe_float(row.get("risk_price"))
    direction = str(row.get("direction"))
    if not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return {"entry": entry, "progress_05r": np.nan, "adverse_05r": np.nan}
    if direction == "short":
        return {"entry": entry, "progress_05r": entry - 0.5 * risk, "adverse_05r": entry + 0.5 * risk}
    return {"entry": entry, "progress_05r": entry + 0.5 * risk, "adverse_05r": entry - 0.5 * risk}


def _plot_atlas(data: pd.DataFrame, full_groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas(data)
    if selected.empty:
        return [], pd.DataFrame()
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.5 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row.get("vt_symbol"))
            entry_day = _normalize_day(row.get("entry_date"))
            day = _day_for_row(full_groups, row)
            if day.empty:
                ax.axis("off")
                ax.text(
                    0.5,
                    0.52,
                    (
                        f"missing Stage861 entry-day minutes\n{vt_symbol} {entry_day.date() if not pd.isna(entry_day) else ''}\n"
                        f"nearest before {row.get('stage861_nearest_before_date', '')} ({row.get('stage861_nearest_before_days', '')}d)\n"
                        f"nearest after {row.get('stage861_nearest_after_date', '')} ({row.get('stage861_nearest_after_days', '')}d)"
                    ),
                    ha="center",
                    va="center",
                    fontsize=10,
                )
            else:
                plot_day = day.head(520).reset_index(drop=True)
                s010.s008.s825._plot_candles(ax, plot_day)
                prices = _line_prices(row)
                for key, color, linestyle in [
                    ("entry", "#2563eb", "-"),
                    ("progress_05r", "#16a34a", "--"),
                    ("adverse_05r", "#dc2626", ":"),
                ]:
                    price = _safe_float(prices.get(key))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=key)
                if len(plot_day) >= 1:
                    ax.axvline(0, color="#0f172a", linestyle="-", linewidth=0.8, alpha=0.65, label="first bar")
                if len(plot_day) >= WINDOW_MINUTES:
                    ax.axvline(WINDOW_MINUTES - 1, color="#64748b", linestyle="-.", linewidth=0.9, alpha=0.78, label="30m")
                ticks = np.linspace(0, len(plot_day) - 1, num=min(8, len(plot_day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(plot_day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), fontsize=7, loc="best")
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"{row.get('quality_label_stage861')} | {row.get('first_bar_label')} | "
                    f"{vt_symbol} {row.get('direction')} {entry_day.date().isoformat() if not pd.isna(entry_day) else 'NA'} "
                    f"pnl={_safe_float(row.get('realized_pnl'), 0):,.0f} r={_safe_float(row.get('r_multiple'), 0):.2f} "
                    f"dir30={_safe_float(row.get('first_30m_directional_r'), 0):.2f} "
                    f"mae30={_safe_float(row.get('first_30m_mae_r'), 0):.2f}"
                ),
                fontsize=8.0,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "lot_id": row.get("lot_id"),
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_day.date().isoformat() if not pd.isna(entry_day) else "",
                    "direction": row.get("direction"),
                    "coverage_bucket": row.get("coverage_bucket"),
                    "quality_label_stage861": row.get("quality_label_stage861"),
                    "first_bar_label": row.get("first_bar_label"),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                    "first_30m_directional_r": _safe_float(row.get("first_30m_directional_r")),
                    "first_30m_mae_r": _safe_float(row.get("first_30m_mae_r")),
                    "png": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))),
                }
            )
        path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
        fig.suptitle("Stage011 Stage861 relabeled minute quality atlas", fontsize=12)
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(summary: pd.DataFrame, quality_stats: pd.DataFrame, first_bar_stats: pd.DataFrame, atlas_paths: list[Path]) -> dict[str, Any]:
    row = summary.iloc[0].to_dict()
    no_follow_net = _safe_float(row.get("no_follow_net_pnl"), 0.0)
    no_follow_pos_years = int(_safe_float(row.get("no_follow_positive_years"), 0.0))
    clean_positive_share = _safe_float(row.get("clean_positive_pnl_share_pct"))
    first_bar_follow_net = _safe_float(row.get("first_bar_follow_net_pnl"), 0.0)
    first_bar_adverse_net = _safe_float(row.get("first_bar_adverse_net_pnl"), 0.0)
    if no_follow_net < 0 and no_follow_pos_years <= 2:
        decision = "stage011_stage861_no_follow_still_promising_but_readonly"
    else:
        decision = "stage011_stage861_relabel_readonly_no_trade_rule_yet"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "why": (
            "Stage861 full minute relabel removes the old-source missing bias, but this stage is still a closed-lot "
            "attribution and visual audit. It does not prove an executable rule, because first-30m labels are after-entry "
            "information and Stage008 already showed mechanical no-follow reduction can damage the equity path."
        ),
        "summary": {key: _json_safe(value) for key, value in row.items()},
        "quality_stats": quality_stats.to_dict(orient="records"),
        "first_bar_stats": first_bar_stats.to_dict(orient="records"),
        "diagnostics": {
            "clean_positive_pnl_share_pct": clean_positive_share,
            "no_follow_net_pnl": no_follow_net,
            "no_follow_positive_years": no_follow_pos_years,
            "first_bar_follow_net_pnl": first_bar_follow_net,
            "first_bar_adverse_net_pnl": first_bar_adverse_net,
        },
        "outputs": {
            "features": str(FEATURES_OUT),
            "quality_bucket_stats": str(QUALITY_BUCKET_OUT),
            "first_bar_bucket_stats": str(FIRST_BAR_BUCKET_OUT),
            "year_quality_stats": str(YEAR_QUALITY_OUT),
            "source_quality_crosstab": str(SOURCE_QUALITY_OUT),
            "contribution_curve": str(CONTRIB_CURVE_OUT),
            "summary": str(SUMMARY_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "contribution_chart": str(CONTRIB_CHART_OUT),
            "year_quality_chart": str(YEAR_QUALITY_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_OUT),
        },
        "overfit_reflection_before": (
            "No: Stage011 freezes the existing 30m label shape from Stage006 and only changes the data source to Stage861. "
            "It adds a zero-threshold first-bar descriptive label, not a trade parameter."
        ),
        "overfit_reflection_after": (
            "No: no product, year, direction, month, R multiple, or window is selected to change trades. The output is a "
            "quality ledger, official path chart, contribution curves, and atlas."
        ),
        "continue_value_after": (
            "Yes: Stage861 relabeling can tell whether no-follow/clean intuition survives repaired coverage. A future true "
            "engine is only justified if it uses time-available information and avoids direct deletion or mechanical right-tail cuts."
        ),
        "order_api_called": False,
        "ctp_connected": False,
    }


def _write_report(
    summary: pd.DataFrame,
    quality_stats: pd.DataFrame,
    first_bar_stats: pd.DataFrame,
    year_quality: pd.DataFrame,
    source_quality: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage011 Stage861 full minute 质量标签重算",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段性质：只读标签重算和视觉归因；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API。",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 外部调研与判断",
        "",
        "- Market Intraday Momentum 文献指出开盘后约半小时具有信息消化和高波动特征，但这只能支持观察早段路径，不能支持扫窗口参数。",
        "- Intraday Time Series Momentum 国际证据说明日内早段动量有跨市场现象，但全球共性有限，规则必须接受跨阶段视觉反证。",
        "- pysystemtrade 数据文档强调期货系统需要把数据加工、仿真和执行状态分层；Stage011 因此先把 Stage861 full minute 作为数据前提重算标签。",
        "- NautilusTrader/Freqtrade 的回测资料都提醒分钟 bar 回测必须避免 bar 内未来信息和 lookahead；本阶段只读，不把 30m 后验标签直接接成交易。",
        "- 我的判断：Stage006/007 的旧源结论必须重算；若 no-follow 在 Stage861 下仍负，只能作为下一阶段“是否保持最小风险”的候选线索，不能直接删除或半仓救参。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Stage861 Quality Buckets",
        "",
        _md_table(quality_stats, max_rows=20),
        "",
        "## First-Bar Descriptive Buckets",
        "",
        _md_table(first_bar_stats, max_rows=20),
        "",
        "## Year Quality Stats",
        "",
        _md_table(year_quality, max_rows=50),
        "",
        "## Source x Quality",
        "",
        _md_table(source_quality, max_rows=30),
        "",
        "## Visual Outputs",
        "",
        f"- official path chart：`{PATH_CHART_OUT}`",
        f"- contribution chart：`{CONTRIB_CHART_OUT}`",
        f"- year quality chart：`{YEAR_QUALITY_CHART_OUT}`",
        *[f"- minute atlas：`{path}`" for path in atlas_paths],
        "",
        "## 视觉分析",
        "",
        "- official path chart 显示本阶段没有改变官方 C9/15w 资金路径；标记点只用于定位样本，不是 C 候选曲线。",
        "- contribution chart 显示 `no_follow_30m` 红线自 2021 后长期为负，且 `all_except_no_follow` 高于全样本参考，说明 Stage861 修复覆盖后 no-follow 仍是负质量集合。",
        "- 同一张 contribution chart 也显示 `first_bar_adverse_close` 仍有明显正贡献，因此第一根分钟K逆向不是坏信号充分条件，不能做入场当刻硬过滤。",
        "- year quality chart 显示 clean 贡献主要来自 2021/2023/2025 右尾，但 `no_follow_30m` 在 2024 为正；规则若只为回避 2022/2026 no-follow 左尾，很容易过拟合弱窗口。",
        "- atlas page001 显示 `ru2501` 等 clean 大赢家并不都要求第一根分钟K顺向，部分先轻微逆向后才进入趋势；page003 显示 `SH405/au2412/CF205/SM505` 等 no-follow 反例最终贡献正收益；page004 显示 `SH607/AP210/cu2307/lh2411` 等 no-follow 亏损样本确实有早段不跟随或假突破形态。",
        "- 视觉结论：no-follow 值得作为下一阶段“是否继续保持最小风险”的候选前提，但不能作为删除、半仓或固定 30m 硬退出规则；下一阶段若做真实引擎，必须让官方 C9 自身 stop/retry 优先，并且避免系统性砍右尾。",
        "",
        "## Judgment",
        "",
        f"- 过拟合反思：`{decision['overfit_reflection_after']}`",
        f"- 继续价值：`{decision['continue_value_after']}`",
        "- 结论：Stage011 仍不是交易候选；它只回答 Stage861 覆盖修复后，旧的 clean/no-follow 直觉是否还值得继续做真实引擎前的第一性设计。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage011] loading Stage861 full minute groups", flush=True)
    metadata = s010.s008.s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    full_minute_bars = s010.s008.s928._load_stage861_full_minute_bars(vt_symbols)
    full_groups = s010.s008.s825._minute_groups(full_minute_bars)

    print("[stage011] loading Stage010 official curve/features", flush=True)
    curve = _load_curve()
    features = _load_features(full_groups)
    quality_stats = _bucket_stats(features, "quality_label_stage861", "quality_label_stage861")
    first_bar_stats = _bucket_stats(features, "first_bar_label", "first_bar_label")
    year_quality = _year_quality_stats(features)
    source_quality = _source_quality_crosstab(features)
    contrib = _contribution_curve(features)
    summary = _summary(curve, features, quality_stats, first_bar_stats)

    print("[stage011] plotting visuals", flush=True)
    _plot_path(curve, features)
    _plot_contribution(contrib)
    _plot_year_quality(year_quality)
    atlas_paths, atlas_manifest = _plot_atlas(features, full_groups)

    decision = _decision(summary, quality_stats, first_bar_stats, atlas_paths)
    summary.loc[:, "decision"] = decision["decision"]
    _write_report(summary, quality_stats, first_bar_stats, year_quality, source_quality, atlas_paths, decision)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    quality_stats.to_csv(QUALITY_BUCKET_OUT, index=False, encoding="utf-8-sig")
    first_bar_stats.to_csv(FIRST_BAR_BUCKET_OUT, index=False, encoding="utf-8-sig")
    year_quality.to_csv(YEAR_QUALITY_OUT, index=False, encoding="utf-8-sig")
    source_quality.to_csv(SOURCE_QUALITY_OUT, index=False, encoding="utf-8-sig")
    contrib.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[stage011] decision={decision['decision']}", flush=True)
    print(f"[stage011] summary={summary.iloc[0].to_dict()}", flush=True)
    print(f"[stage011] report={REPORT_OUT}", flush=True)


if __name__ == "__main__":
    main()

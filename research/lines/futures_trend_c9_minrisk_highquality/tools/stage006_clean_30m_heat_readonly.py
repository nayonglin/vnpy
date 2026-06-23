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
STAGE = "Stage006"
MODEL_TAG = "stage006_clean_30m_heat_readonly_v1"
OUTPUT_PREFIX = "qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_clean_30m_heat_readonly"
STAGE005_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
CAPITAL = 150_000.0
HEAT_R = 0.50
WINDOW_MINUTES = 30
PER_PAGE = 4
MAX_ATLAS_ROWS = 24

STAGE005_CURVE = (
    STAGE005_DIR
    / "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_official_curve_stage005_signal_quality_visual_forensics_v1.csv"
)
STAGE005_CLOSED_LOTS = (
    STAGE005_DIR
    / "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_official_closed_lots_stage005_signal_quality_visual_forensics_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_features_{MODEL_TAG}.csv"
BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_stats_{MODEL_TAG}.csv"
YEAR_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_bucket_stats_{MODEL_TAG}.csv"
CONTRIB_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
CONTRIB_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    return data.to_markdown(index=False)


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    try:
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)
    except AttributeError:
        pass
    return pd.Timestamp(ts).normalize()


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _load_official_curve() -> pd.DataFrame:
    if not STAGE005_CURVE.exists():
        raise RuntimeError(f"missing official curve: {STAGE005_CURVE}")
    curve = pd.read_csv(STAGE005_CURVE, encoding="utf-8-sig")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce", format="mixed").dt.normalize()
    curve = curve[curve["date"].between(START, END)].copy().sort_values("date")
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    return curve


def _load_closed_lots() -> pd.DataFrame:
    if not STAGE005_CLOSED_LOTS.exists():
        raise RuntimeError(f"missing closed lots: {STAGE005_CLOSED_LOTS}")
    closed = pd.read_csv(STAGE005_CLOSED_LOTS, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date"]:
        closed[column] = pd.to_datetime(closed[column], errors="coerce").dt.normalize()
    closed = closed[
        closed["entry_date"].between(START, END)
        & closed["exit_date"].between(START, END)
    ].copy()
    return closed.reset_index(drop=True)


def _line_prices(row: pd.Series) -> dict[str, float]:
    entry = _safe_float(row.get("entry_price"))
    risk = _safe_float(row.get("stop_distance"))
    if not np.isfinite(risk) or risk <= 0:
        risk = _safe_float(row.get("entry_risk_distance_pct")) * entry if np.isfinite(entry) else np.nan
    direction = str(row.get("direction"))
    if not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return {"entry": entry, "risk": risk, "adverse_05r": np.nan, "progress_05r": np.nan}
    if direction == "short":
        return {
            "entry": entry,
            "risk": risk,
            "adverse_05r": entry + HEAT_R * risk,
            "progress_05r": entry - HEAT_R * risk,
        }
    return {
        "entry": entry,
        "risk": risk,
        "adverse_05r": entry - HEAT_R * risk,
        "progress_05r": entry + HEAT_R * risk,
    }


def _minute_features_for_lot(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row.get("vt_symbol"))
    entry_day = _normalize_day(row.get("entry_date"))
    day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    if not day.empty and not pd.isna(entry_day):
        day = day[day["bar_date"].eq(entry_day)].copy().sort_values("bar_datetime").reset_index(drop=True)
    else:
        day = pd.DataFrame()
    prices = _line_prices(row)
    entry = prices["entry"]
    risk = prices["risk"]
    direction = str(row.get("direction"))
    if day.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return {
            "minute_coverage": int(len(day)),
            "quality_label": "missing_30m",
            "quality_reason": "missing_minute_or_risk",
            "first_30m_directional_r": np.nan,
            "first_30m_mfe_r": np.nan,
            "first_30m_mae_r": np.nan,
            "entry_day_mfe_r": np.nan,
            "entry_day_mae_r": np.nan,
        }

    window = day.head(WINDOW_MINUTES).copy()
    close_30 = _safe_float(window.iloc[-1]["close"])
    if direction == "short":
        first_directional = (entry - close_30) / risk if np.isfinite(close_30) else np.nan
        first_mfe = (entry - pd.to_numeric(window["low"], errors="coerce").min()) / risk
        first_mae = (pd.to_numeric(window["high"], errors="coerce").max() - entry) / risk
        day_mfe = (entry - pd.to_numeric(day["low"], errors="coerce").min()) / risk
        day_mae = (pd.to_numeric(day["high"], errors="coerce").max() - entry) / risk
    else:
        first_directional = (close_30 - entry) / risk if np.isfinite(close_30) else np.nan
        first_mfe = (pd.to_numeric(window["high"], errors="coerce").max() - entry) / risk
        first_mae = (entry - pd.to_numeric(window["low"], errors="coerce").min()) / risk
        day_mfe = (pd.to_numeric(day["high"], errors="coerce").max() - entry) / risk
        day_mae = (entry - pd.to_numeric(day["low"], errors="coerce").min()) / risk

    first_mfe = max(0.0, first_mfe) if np.isfinite(first_mfe) else np.nan
    first_mae = max(0.0, first_mae) if np.isfinite(first_mae) else np.nan
    day_mfe = max(0.0, day_mfe) if np.isfinite(day_mfe) else np.nan
    day_mae = max(0.0, day_mae) if np.isfinite(day_mae) else np.nan

    if not np.isfinite(first_directional) or not np.isfinite(first_mae):
        label = "missing_30m"
        reason = "invalid_first_window"
    elif first_directional <= 0:
        label = "no_follow_30m"
        reason = "first_30m_directional_r_le_0"
    elif first_mae > HEAT_R:
        label = "adverse_heat_30m"
        reason = "first_30m_mae_gt_0_5r"
    else:
        label = "clean_continuation_30m"
        reason = "directional_positive_and_mae_le_0_5r"

    return {
        "minute_coverage": int(len(day)),
        "quality_label": label,
        "quality_reason": reason,
        "first_30m_directional_r": first_directional,
        "first_30m_mfe_r": first_mfe,
        "first_30m_mae_r": first_mae,
        "entry_day_mfe_r": day_mfe,
        "entry_day_mae_r": day_mae,
    }


def _feature_frame(closed: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in closed.iterrows():
        item = row.to_dict()
        item.update(_line_prices(row))
        item.update(_minute_features_for_lot(row, minute_by_symbol))
        rows.append(item)
    data = pd.DataFrame(rows)
    for column in ["realized_pnl", "r_multiple", "volume", "risk_amount"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data["entry_year"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.year
    data["exit_year"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.year
    data["positive_pnl"] = data["realized_pnl"].clip(lower=0)
    data["negative_pnl"] = data["realized_pnl"].clip(upper=0)
    return data


def _bucket_stats(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_pnl = float(features["realized_pnl"].fillna(0).sum())
    total_positive = float(features["positive_pnl"].fillna(0).sum())
    total_negative = float(features["negative_pnl"].fillna(0).sum())
    for label, group in features.groupby("quality_label", dropna=False):
        pnl = float(group["realized_pnl"].fillna(0).sum())
        positive = float(group["positive_pnl"].fillna(0).sum())
        negative = float(group["negative_pnl"].fillna(0).sum())
        rows.append(
            {
                "quality_label": label,
                "lots": int(len(group)),
                "products": int(group["product"].astype(str).nunique()),
                "years": int(group["entry_year"].nunique()),
                "total_realized_pnl": pnl,
                "pnl_share_pct": pnl / total_pnl * 100.0 if total_pnl else np.nan,
                "positive_pnl": positive,
                "positive_pnl_share_pct": positive / total_positive * 100.0 if total_positive else np.nan,
                "negative_pnl": negative,
                "negative_pnl_share_pct": negative / total_negative * 100.0 if total_negative else np.nan,
                "median_r_multiple": float(group["r_multiple"].median()),
                "mean_r_multiple": float(group["r_multiple"].mean()),
                "win_rate_pct": float((group["realized_pnl"] > 0).mean() * 100.0),
                "median_first_30m_directional_r": float(group["first_30m_directional_r"].median()),
                "median_first_30m_mfe_r": float(group["first_30m_mfe_r"].median()),
                "median_first_30m_mae_r": float(group["first_30m_mae_r"].median()),
                "median_entry_day_mfe_r": float(group["entry_day_mfe_r"].median()),
                "median_entry_day_mae_r": float(group["entry_day_mae_r"].median()),
                "max_single_loss": float(group["realized_pnl"].min()),
                "max_single_win": float(group["realized_pnl"].max()),
            }
        )
    order = {
        "clean_continuation_30m": 0,
        "adverse_heat_30m": 1,
        "no_follow_30m": 2,
        "missing_30m": 3,
    }
    result = pd.DataFrame(rows)
    result["_order"] = result["quality_label"].map(order).fillna(9)
    return result.sort_values(["_order", "quality_label"]).drop(columns=["_order"]).reset_index(drop=True)


def _year_bucket_stats(features: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        features.groupby(["entry_year", "quality_label"], dropna=False)
        .agg(
            lots=("lot_id", "size"),
            products=("product", "nunique"),
            realized_pnl=("realized_pnl", "sum"),
            positive_pnl=("positive_pnl", "sum"),
            negative_pnl=("negative_pnl", "sum"),
            median_r_multiple=("r_multiple", "median"),
            win_rate_pct=("realized_pnl", lambda x: float((pd.to_numeric(x, errors="coerce") > 0).mean() * 100.0)),
        )
        .reset_index()
        .sort_values(["entry_year", "quality_label"])
    )
    return grouped


def _contribution_curve(features: pd.DataFrame) -> pd.DataFrame:
    calendar = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
    labels = [
        "all_closed_lots_reference",
        "clean_continuation_30m",
        "adverse_heat_30m",
        "no_follow_30m",
        "missing_30m",
        "non_clean_reference",
    ]
    rows: list[pd.DataFrame] = []
    for label in labels:
        if label == "all_closed_lots_reference":
            part = features.copy()
        elif label == "non_clean_reference":
            part = features[~features["quality_label"].eq("clean_continuation_30m")].copy()
        else:
            part = features[features["quality_label"].eq(label)].copy()
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
        curve["quality_label"] = label
        curve["stage"] = STAGE
        curve["model_tag"] = MODEL_TAG
        curve["note"] = "closed-lot contribution curve only; not executable mark-to-market backtest"
        rows.append(curve)
    return pd.concat(rows, ignore_index=True, sort=False)


def _summary(curve: pd.DataFrame, features: pd.DataFrame, buckets: pd.DataFrame) -> pd.DataFrame:
    official_end = float(pd.to_numeric(curve["account_equity"], errors="coerce").iloc[-1])
    clean = buckets[buckets["quality_label"].eq("clean_continuation_30m")]
    non_clean = buckets[buckets["quality_label"].eq("non_clean_reference")]
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "window_id": FULL_WINDOW_ID,
        "start": START.date().isoformat(),
        "end": END.date().isoformat(),
        "official_end_equity": official_end,
        "official_total_return_pct": (official_end / CAPITAL - 1.0) * 100.0,
        "official_max_dd_pct": float(pd.to_numeric(curve["drawdown_pct"], errors="coerce").min()),
        "official_max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(curve["broker10_margin_to_equity_pct"], errors="coerce").max()
        ),
        "closed_lots_reference_rows": int(len(features)),
        "minute_missing_rows": int(features["quality_label"].eq("missing_30m").sum()),
        "clean_lots": int(clean["lots"].iloc[0]) if not clean.empty else 0,
        "clean_total_realized_pnl": float(clean["total_realized_pnl"].iloc[0]) if not clean.empty else 0.0,
        "clean_positive_pnl_share_pct": float(clean["positive_pnl_share_pct"].iloc[0]) if not clean.empty else np.nan,
        "clean_negative_pnl_share_pct": float(clean["negative_pnl_share_pct"].iloc[0]) if not clean.empty else np.nan,
        "decision": "stage006_readonly_quality_label_not_trade_rule",
    }
    return pd.DataFrame([row])


def _plot_path(curve: pd.DataFrame, features: pd.DataFrame) -> None:
    data = curve.copy().sort_values("date")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    axes[0].plot(data["date"], data["account_equity"], color="#2563eb", label="official C9/15w")
    axes[1].plot(data["date"], data["drawdown_pct"], color="#2563eb", label="drawdown")
    axes[2].plot(data["date"], data["broker10_margin_to_equity_pct"], color="#2563eb", label="broker10")
    colors = {
        "clean_continuation_30m": "#16a34a",
        "adverse_heat_30m": "#dc2626",
        "no_follow_30m": "#7c2d12",
        "missing_30m": "#64748b",
    }
    marked = pd.concat(
        [
            features[features["quality_label"].eq("clean_continuation_30m")].nlargest(6, "realized_pnl"),
            features[features["quality_label"].ne("clean_continuation_30m")].nsmallest(8, "realized_pnl"),
        ],
        ignore_index=True,
        sort=False,
    )
    seen: set[str] = set()
    for _, row in marked.iterrows():
        date = _normalize_day(row.get("entry_date"))
        label = str(row.get("quality_label"))
        line_label = label if label not in seen else None
        seen.add(label)
        for ax in axes:
            ax.axvline(date, color=colors.get(label, "#64748b"), alpha=0.22, linewidth=1.0, label=line_label)
            line_label = None
    axes[0].set_title("Stage006 official C9/15w path with early-quality markers")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9, alpha=0.75)
    for ax in axes:
        ax.grid(True, alpha=0.24)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_contribution(curve: pd.DataFrame) -> None:
    data = curve.copy()
    colors = {
        "all_closed_lots_reference": "#2563eb",
        "clean_continuation_30m": "#16a34a",
        "non_clean_reference": "#7c2d12",
        "adverse_heat_30m": "#dc2626",
        "no_follow_30m": "#ea580c",
        "missing_30m": "#64748b",
    }
    fig, axes = plt.subplots(2, 1, figsize=(18, 9), sharex=True, constrained_layout=True)
    for label, group in data.groupby("quality_label"):
        group = group.sort_values("date")
        if label in ["adverse_heat_30m", "no_follow_30m", "missing_30m"]:
            alpha = 0.42
            linewidth = 1.0
        else:
            alpha = 0.95
            linewidth = 1.6
        axes[0].plot(group["date"], group["cumulative_realized_pnl"], label=label, color=colors.get(label), alpha=alpha, linewidth=linewidth)
        axes[1].plot(group["date"], group["contribution_drawdown_cash"], label=label, color=colors.get(label), alpha=alpha, linewidth=linewidth)
    axes[0].set_title("Stage006 closed-lot cumulative realized PnL by first-30m quality label")
    axes[1].set_title("Contribution drawdown in cash")
    for ax in axes:
        ax.grid(True, alpha=0.24)
        ax.legend(loc="best")
    fig.savefig(CONTRIB_CHART_OUT, dpi=170)
    plt.close(fig)


def _select_atlas(features: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    clean = features[features["quality_label"].eq("clean_continuation_30m")].copy()
    non_clean = features[~features["quality_label"].eq("clean_continuation_30m")].copy()
    if not clean.empty:
        parts.append(clean.nlargest(6, "realized_pnl"))
        parts.append(clean.nsmallest(4, "realized_pnl"))
    if not non_clean.empty:
        parts.append(non_clean.nlargest(6, "realized_pnl"))
        parts.append(non_clean.nsmallest(8, "realized_pnl"))
    if not parts:
        return pd.DataFrame()
    return (
        pd.concat(parts, ignore_index=True, sort=False)
        .drop_duplicates(["lot_id", "vt_symbol", "entry_date", "direction"])
        .head(MAX_ATLAS_ROWS)
    )


def _plot_atlas(features: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas(features)
    if selected.empty:
        return [], pd.DataFrame()
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.4 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row.get("vt_symbol"))
            entry_day = _normalize_day(row.get("entry_date"))
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            if not day.empty and not pd.isna(entry_day):
                day = day[day["bar_date"].eq(entry_day)].copy().sort_values("bar_datetime").head(520).reset_index(drop=True)
            else:
                day = pd.DataFrame()
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_day}", ha="center", va="center")
            else:
                s825._plot_candles(ax, day)
                prices = _line_prices(row)
                for key, color, linestyle in [
                    ("entry", "#2563eb", "-"),
                    ("progress_05r", "#16a34a", "--"),
                    ("adverse_05r", "#dc2626", ":"),
                ]:
                    price = _safe_float(prices.get(key))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=key)
                if len(day) >= WINDOW_MINUTES:
                    ax.axvline(WINDOW_MINUTES - 1, color="#0f172a", linestyle="-.", linewidth=0.9, alpha=0.75, label="30m")
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), fontsize=7, loc="best")
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"{row.get('quality_label')} {vt_symbol} {row.get('direction')} "
                    f"{pd.Timestamp(entry_day).date().isoformat() if not pd.isna(entry_day) else 'NA'} "
                    f"r={_safe_float(row.get('r_multiple'), 0):.2f} pnl={_safe_float(row.get('realized_pnl'), 0):.0f} "
                    f"dir30={_safe_float(row.get('first_30m_directional_r'), 0):.2f} "
                    f"mae30={_safe_float(row.get('first_30m_mae_r'), 0):.2f}"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "quality_label": row.get("quality_label"),
                    "lot_id": row.get("lot_id"),
                    "vt_symbol": vt_symbol,
                    "entry_date": pd.Timestamp(entry_day).date().isoformat() if not pd.isna(entry_day) else "",
                    "direction": row.get("direction"),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "first_30m_directional_r": _safe_float(row.get("first_30m_directional_r")),
                    "first_30m_mae_r": _safe_float(row.get("first_30m_mae_r")),
                    "png": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))),
                }
            )
        path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(summary: pd.DataFrame, buckets: pd.DataFrame, atlas_paths: list[Path]) -> dict[str, Any]:
    row = summary.iloc[0].to_dict()
    clean = buckets[buckets["quality_label"].eq("clean_continuation_30m")]
    clean_positive_share = _safe_float(clean["positive_pnl_share_pct"].iloc[0]) if not clean.empty else np.nan
    clean_negative_share = _safe_float(clean["negative_pnl_share_pct"].iloc[0]) if not clean.empty else np.nan
    promote = bool(
        np.isfinite(clean_positive_share)
        and np.isfinite(clean_negative_share)
        and clean_positive_share >= 80.0
        and abs(clean_negative_share) <= 80.0
    )
    decision = "stage006_readonly_quality_label_promising_needs_true_engine" if promote else "stage006_readonly_quality_label_not_trade_rule"
    why = (
        "The first-30m clean label keeps enough positive closed-lot contribution to justify a true engine probe, "
        "but this remains read-only and non-executable."
        if promote
        else "The first-30m clean label does not prove a universal rule with enough right-tail retention and loss isolation."
    )
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "decision": decision,
        "why": why,
        "summary": {key: _json_safe(value) for key, value in row.items()},
        "bucket_stats": buckets.to_dict(orient="records") if not buckets.empty else [],
        "paths": {
            "features": str(FEATURES_OUT),
            "bucket_stats": str(BUCKET_OUT),
            "year_bucket_stats": str(YEAR_BUCKET_OUT),
            "contribution_curve": str(CONTRIB_CURVE_OUT),
            "summary": str(SUMMARY_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "contribution_chart": str(CONTRIB_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_OUT),
        },
        "next_step": (
            "If promoted, write a separate true engine that restores risk only after the frozen clean label is known. "
            "If not promoted, keep the label as visual intuition and avoid threshold rescue."
        ),
    }


def _write_report(
    summary: pd.DataFrame,
    buckets: pd.DataFrame,
    year_buckets: pd.DataFrame,
    features: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    selected = _select_atlas(features)
    lines = [
        f"# {STAGE} C9/15w clean 30m heat readonly audit",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- official live: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- stage nature: read-only quality labeling; no executable candidate; no A/B.",
        "- frozen label: `clean_continuation_30m = first_30m_directional_r > 0 and first_30m_mae_r <= 0.5R`.",
        f"- decision: `{decision['decision']}`",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=10),
        "",
        "## Bucket Stats",
        "",
        _md_table(buckets, max_rows=20),
        "",
        "## Year Bucket Stats",
        "",
        _md_table(year_buckets, max_rows=40),
        "",
        "## Selected Atlas Lots",
        "",
        _md_table(
            selected[
                [
                    "quality_label",
                    "entry_date",
                    "vt_symbol",
                    "direction",
                    "first_30m_directional_r",
                    "first_30m_mae_r",
                    "r_multiple",
                    "realized_pnl",
                    "volume",
                ]
            ],
            max_rows=30,
        )
        if not selected.empty
        else "No selected lots.",
        "",
        "## Visual Outputs",
        "",
        f"- official path chart: `{PATH_CHART_OUT}`",
        f"- contribution chart: `{CONTRIB_CHART_OUT}`",
        f"- atlas pages: `{len(atlas_paths)}`",
        "",
        "## Judgment",
        "",
        "- This stage uses a closed-lot contribution curve, not an executable mark-to-market backtest.",
        "- The label is allowed to inform whether a true engine is worth writing; it is not a trading rule yet.",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)

    official_curve = _load_official_curve()
    closed = _load_closed_lots()
    features = _feature_frame(closed, minute_by_symbol)
    buckets = _bucket_stats(features)
    year_buckets = _year_bucket_stats(features)
    contribution = _contribution_curve(features)
    summary = _summary(official_curve, features, buckets)

    _plot_path(official_curve, features)
    _plot_contribution(contribution)
    atlas_paths, atlas_manifest = _plot_atlas(features, minute_by_symbol)
    decision = _decision(summary, buckets, atlas_paths)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    buckets.to_csv(BUCKET_OUT, index=False, encoding="utf-8-sig")
    year_buckets.to_csv(YEAR_BUCKET_OUT, index=False, encoding="utf-8-sig")
    contribution.to_csv(CONTRIB_CURVE_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), encoding="utf-8")
    _write_report(summary, buckets, year_buckets, features, atlas_paths, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))


if __name__ == "__main__":
    main()

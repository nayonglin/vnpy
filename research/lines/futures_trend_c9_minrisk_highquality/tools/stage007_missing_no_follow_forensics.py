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
STAGE = "Stage007"
MODEL_TAG = "stage007_missing_no_follow_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage007_c9_minrisk_missing_no_follow_forensics"

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
import stage006_clean_30m_heat_readonly as s006
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage007_missing_no_follow_forensics"
STAGE006_DIR = LINE_DIR / "outputs" / "stage006_clean_30m_heat_readonly"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
PER_PAGE = 4
MAX_ATLAS_ROWS = 24

STAGE006_FEATURES = (
    STAGE006_DIR
    / "qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_lot_features_stage006_clean_30m_heat_readonly_v1.csv"
)
STAGE006_CURVE = (
    STAGE006_DIR
    / "qmt_roll_stage006_c9_minrisk_clean_30m_heat_readonly_contribution_curve_stage006_clean_30m_heat_readonly_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
MISSING_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_bucket_stats_{MODEL_TAG}.csv"
NO_FOLLOW_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_no_follow_year_stats_{MODEL_TAG}.csv"
NO_FOLLOW_PRODUCT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_no_follow_product_stats_{MODEL_TAG}.csv"
CONTRIBUTION_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
CONTRIB_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    return data.to_markdown(index=False)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s006._safe_float(value, default=default)


def _normalize_day(value: Any) -> pd.Timestamp:
    return s006._normalize_day(value)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s006._drawdown_pct(equity)


def _load_features() -> pd.DataFrame:
    if not STAGE006_FEATURES.exists():
        raise RuntimeError(f"missing Stage006 features: {STAGE006_FEATURES}")
    data = pd.read_csv(STAGE006_FEATURES, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    for column in [
        "realized_pnl",
        "r_multiple",
        "volume",
        "size",
        "risk_amount",
        "entry_price",
        "stop_distance",
        "entry_risk_distance_pct",
        "minute_coverage",
        "first_30m_directional_r",
        "first_30m_mae_r",
    ]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["positive_pnl"] = data["realized_pnl"].clip(lower=0)
    data["negative_pnl"] = data["realized_pnl"].clip(upper=0)
    return data


def _load_official_curve() -> pd.DataFrame:
    curve = s006._load_official_curve()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce", format="mixed").dt.normalize()
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    return curve


def _minute_availability(features: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in features.iterrows():
        vt_symbol = str(row.get("vt_symbol"))
        day = _normalize_day(row.get("entry_date"))
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        if bars.empty:
            symbol_total = 0
            date_min = ""
            date_max = ""
            entry_day_bars = 0
            nearest_before_days = np.nan
            nearest_after_days = np.nan
            source = ""
        else:
            dates = pd.to_datetime(bars["bar_date"], errors="coerce").dt.normalize()
            symbol_total = int(len(bars))
            date_min = pd.Timestamp(dates.min()).date().isoformat()
            date_max = pd.Timestamp(dates.max()).date().isoformat()
            entry_day_bars = int(dates.eq(day).sum()) if not pd.isna(day) else 0
            before = dates[dates.lt(day)] if not pd.isna(day) else pd.Series(dtype="datetime64[ns]")
            after = dates[dates.gt(day)] if not pd.isna(day) else pd.Series(dtype="datetime64[ns]")
            nearest_before_days = int((day - before.max()).days) if len(before) else np.nan
            nearest_after_days = int((after.min() - day).days) if len(after) else np.nan
            source = ",".join(sorted(bars.get("minute_source", pd.Series(dtype=str)).astype(str).unique())[:3])
        rows.append(
            {
                "lot_id": row.get("lot_id"),
                "vt_symbol": vt_symbol,
                "entry_date": day,
                "minute_symbol_total_bars": symbol_total,
                "minute_symbol_date_min": date_min,
                "minute_symbol_date_max": date_max,
                "entry_day_minute_bars": entry_day_bars,
                "nearest_before_days": nearest_before_days,
                "nearest_after_days": nearest_after_days,
                "minute_sources": source,
            }
        )
    return pd.DataFrame(rows)


def _missing_cause(row: pd.Series) -> str:
    if str(row.get("quality_label")) != "missing_30m":
        return "not_missing"
    minute_coverage = _safe_float(row.get("minute_coverage"), 0.0)
    risk = _safe_float(row.get("risk"))
    if minute_coverage <= 0:
        return "missing_entry_day_minutes"
    if not np.isfinite(risk) or risk <= 0:
        return "missing_risk_fields"
    return "other_missing"


def _enrich(features: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    availability = _minute_availability(features, minute_by_symbol)
    data = features.merge(availability, on=["lot_id", "vt_symbol", "entry_date"], how="left")
    data["missing_cause"] = data.apply(_missing_cause, axis=1)
    data["no_follow_flag"] = data["quality_label"].eq("no_follow_30m").astype(int)
    data["no_follow_signed_pnl"] = np.where(data["no_follow_flag"].eq(1), data["realized_pnl"], 0.0)
    data["recoverable_risk_from_amount"] = (
        (pd.to_numeric(data.get("risk_amount"), errors="coerce") > 0)
        & (pd.to_numeric(data.get("volume"), errors="coerce") > 0)
        & (pd.to_numeric(data.get("size"), errors="coerce") > 0)
    ).astype(int)
    data["risk_from_amount"] = np.where(
        data["recoverable_risk_from_amount"].eq(1),
        pd.to_numeric(data["risk_amount"], errors="coerce")
        / (pd.to_numeric(data["volume"], errors="coerce") * pd.to_numeric(data["size"], errors="coerce")),
        np.nan,
    )
    data["risk_repair_would_help"] = (
        data["quality_label"].eq("missing_30m")
        & (pd.to_numeric(data["minute_coverage"], errors="coerce") > 0)
        & (pd.to_numeric(data["risk_from_amount"], errors="coerce") > 0)
    ).astype(int)
    return data


def _missing_bucket_stats(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cause, group in data.groupby("missing_cause", dropna=False):
        rows.append(
            {
                "missing_cause": cause,
                "lots": int(len(group)),
                "products": int(group["product"].astype(str).nunique()),
                "years": int(group["entry_year"].nunique()),
                "realized_pnl": float(group["realized_pnl"].fillna(0).sum()),
                "positive_pnl": float(group["positive_pnl"].fillna(0).sum()),
                "negative_pnl": float(group["negative_pnl"].fillna(0).sum()),
                "median_r_multiple": float(group["r_multiple"].median()),
                "win_rate_pct": float((group["realized_pnl"] > 0).mean() * 100.0),
                "max_single_win": float(group["realized_pnl"].max()),
                "max_single_loss": float(group["realized_pnl"].min()),
                "risk_repair_would_help_lots": int(group["risk_repair_would_help"].sum()),
            }
        )
    order = {
        "not_missing": 0,
        "missing_entry_day_minutes": 1,
        "missing_risk_fields": 2,
        "other_missing": 3,
    }
    frame = pd.DataFrame(rows)
    frame["_order"] = frame["missing_cause"].map(order).fillna(9)
    return frame.sort_values(["_order", "missing_cause"]).drop(columns=["_order"]).reset_index(drop=True)


def _no_follow_year_stats(data: pd.DataFrame) -> pd.DataFrame:
    nf = data[data["quality_label"].eq("no_follow_30m")].copy()
    if nf.empty:
        return pd.DataFrame()
    return (
        nf.groupby("entry_year", dropna=False)
        .agg(
            lots=("lot_id", "size"),
            products=("product", "nunique"),
            realized_pnl=("realized_pnl", "sum"),
            positive_pnl=("positive_pnl", "sum"),
            negative_pnl=("negative_pnl", "sum"),
            median_r_multiple=("r_multiple", "median"),
            win_rate_pct=("realized_pnl", lambda x: float((pd.to_numeric(x, errors="coerce") > 0).mean() * 100.0)),
            max_single_win=("realized_pnl", "max"),
            max_single_loss=("realized_pnl", "min"),
        )
        .reset_index()
        .sort_values("entry_year")
    )


def _no_follow_product_stats(data: pd.DataFrame) -> pd.DataFrame:
    nf = data[data["quality_label"].eq("no_follow_30m")].copy()
    if nf.empty:
        return pd.DataFrame()
    return (
        nf.groupby("product", dropna=False)
        .agg(
            lots=("lot_id", "size"),
            years=("entry_year", "nunique"),
            realized_pnl=("realized_pnl", "sum"),
            positive_pnl=("positive_pnl", "sum"),
            negative_pnl=("negative_pnl", "sum"),
            median_r_multiple=("r_multiple", "median"),
            max_single_win=("realized_pnl", "max"),
            max_single_loss=("realized_pnl", "min"),
        )
        .reset_index()
        .sort_values("realized_pnl")
    )


def _contribution_curve(data: pd.DataFrame) -> pd.DataFrame:
    calendar = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
    selectors = {
        "all_closed_lots_reference": data.index == data.index,
        "no_follow_30m": data["quality_label"].eq("no_follow_30m"),
        "all_except_no_follow": ~data["quality_label"].eq("no_follow_30m"),
        "missing_entry_day_minutes": data["missing_cause"].eq("missing_entry_day_minutes"),
        "missing_risk_fields": data["missing_cause"].eq("missing_risk_fields"),
        "covered_clean_or_adverse": data["quality_label"].isin(["clean_continuation_30m", "adverse_heat_30m"]),
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


def _summary(official_curve: pd.DataFrame, data: pd.DataFrame, missing_stats: pd.DataFrame, no_follow_year: pd.DataFrame) -> pd.DataFrame:
    official_end = float(pd.to_numeric(official_curve["account_equity"], errors="coerce").iloc[-1])
    total_positive = float(data["positive_pnl"].fillna(0).sum())
    total_negative = float(data["negative_pnl"].fillna(0).sum())
    total_pnl = float(data["realized_pnl"].fillna(0).sum())
    nf = data[data["quality_label"].eq("no_follow_30m")]
    missing_minutes = data[data["missing_cause"].eq("missing_entry_day_minutes")]
    missing_risk = data[data["missing_cause"].eq("missing_risk_fields")]
    positive_no_follow_years = (
        int((pd.to_numeric(no_follow_year.get("realized_pnl", pd.Series(dtype=float)), errors="coerce") > 0).sum())
        if not no_follow_year.empty
        else 0
    )
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
        "official_max_dd_pct": float(pd.to_numeric(official_curve["drawdown_pct"], errors="coerce").min()),
        "official_max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(official_curve["broker10_margin_to_equity_pct"], errors="coerce").max()
        ),
        "closed_lots_reference_rows": int(len(data)),
        "closed_lots_reference_net_pnl": total_pnl,
        "missing_entry_day_minutes_lots": int(len(missing_minutes)),
        "missing_entry_day_minutes_net_pnl": float(missing_minutes["realized_pnl"].fillna(0).sum()),
        "missing_entry_day_minutes_positive_share_pct": float(missing_minutes["positive_pnl"].sum() / total_positive * 100.0)
        if total_positive
        else np.nan,
        "missing_risk_fields_lots": int(len(missing_risk)),
        "missing_risk_fields_net_pnl": float(missing_risk["realized_pnl"].fillna(0).sum()),
        "risk_repair_would_help_lots": int(data["risk_repair_would_help"].sum()),
        "no_follow_lots": int(len(nf)),
        "no_follow_net_pnl": float(nf["realized_pnl"].fillna(0).sum()),
        "no_follow_positive_pnl_share_pct": float(nf["positive_pnl"].sum() / total_positive * 100.0) if total_positive else np.nan,
        "no_follow_negative_pnl_share_pct": float(nf["negative_pnl"].sum() / total_negative * 100.0) if total_negative else np.nan,
        "no_follow_positive_years": positive_no_follow_years,
        "decision": "stage007_readonly_no_follow_promising_but_not_trade_rule",
    }
    return pd.DataFrame([row])


def _plot_path(official_curve: pd.DataFrame, data: pd.DataFrame) -> None:
    curve = official_curve.copy().sort_values("date")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#2563eb", label="official C9/15w")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#2563eb", label="drawdown")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#2563eb", label="broker10")
    marks = pd.concat(
        [
            data[data["quality_label"].eq("no_follow_30m")].nsmallest(8, "realized_pnl"),
            data[data["missing_cause"].eq("missing_entry_day_minutes")].nlargest(8, "realized_pnl"),
            data[data["missing_cause"].eq("missing_risk_fields")].nlargest(4, "realized_pnl"),
        ],
        ignore_index=True,
        sort=False,
    ).drop_duplicates(["lot_id", "vt_symbol", "entry_date"])
    colors = {
        "no_follow_30m": "#dc2626",
        "missing_entry_day_minutes": "#64748b",
        "missing_risk_fields": "#a855f7",
    }
    seen: set[str] = set()
    for _, row in marks.iterrows():
        date = _normalize_day(row.get("entry_date"))
        if str(row.get("quality_label")) == "no_follow_30m":
            label = "no_follow_30m"
        else:
            label = str(row.get("missing_cause"))
        legend = label if label not in seen else None
        seen.add(label)
        for ax in axes:
            ax.axvline(date, color=colors.get(label, "#64748b"), alpha=0.22, linewidth=1.0, label=legend)
            legend = None
    axes[0].set_title("Stage007 official C9/15w path with no-follow and missing-data markers")
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
        "no_follow_30m": "#dc2626",
        "all_except_no_follow": "#16a34a",
        "missing_entry_day_minutes": "#64748b",
        "missing_risk_fields": "#a855f7",
        "covered_clean_or_adverse": "#0f766e",
    }
    fig, axes = plt.subplots(2, 1, figsize=(18, 9), sharex=True, constrained_layout=True)
    for label, group in data.groupby("bucket"):
        group = group.sort_values("date")
        linewidth = 1.6 if label in {"all_closed_lots_reference", "all_except_no_follow"} else 1.15
        alpha = 0.92 if label in {"all_closed_lots_reference", "all_except_no_follow"} else 0.6
        axes[0].plot(group["date"], group["cumulative_realized_pnl"], label=label, color=colors.get(label), linewidth=linewidth, alpha=alpha)
        axes[1].plot(group["date"], group["contribution_drawdown_cash"], label=label, color=colors.get(label), linewidth=linewidth, alpha=alpha)
    axes[0].set_title("Stage007 closed-lot cumulative realized PnL: missing/no-follow audit")
    axes[1].set_title("Contribution drawdown in cash")
    for ax in axes:
        ax.grid(True, alpha=0.24)
        ax.legend(loc="best")
    fig.savefig(CONTRIB_CHART_OUT, dpi=170)
    plt.close(fig)


def _select_atlas(data: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    no_follow = data[data["quality_label"].eq("no_follow_30m")].copy()
    missing_minutes = data[data["missing_cause"].eq("missing_entry_day_minutes")].copy()
    missing_risk = data[data["missing_cause"].eq("missing_risk_fields")].copy()
    if not no_follow.empty:
        parts.append(no_follow.nsmallest(8, "realized_pnl"))
        parts.append(no_follow.nlargest(4, "realized_pnl"))
    if not missing_minutes.empty:
        parts.append(missing_minutes.nlargest(8, "realized_pnl"))
    if not missing_risk.empty:
        parts.append(missing_risk.nlargest(4, "realized_pnl"))
    if not parts:
        return pd.DataFrame()
    return (
        pd.concat(parts, ignore_index=True, sort=False)
        .drop_duplicates(["lot_id", "vt_symbol", "entry_date", "direction"])
        .head(MAX_ATLAS_ROWS)
    )


def _line_prices(row: pd.Series) -> dict[str, float]:
    entry = _safe_float(row.get("entry_price"))
    risk = _safe_float(row.get("risk"))
    direction = str(row.get("direction"))
    if not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return {"entry": entry, "progress_05r": np.nan, "adverse_05r": np.nan}
    if direction == "short":
        return {"entry": entry, "progress_05r": entry - 0.5 * risk, "adverse_05r": entry + 0.5 * risk}
    return {"entry": entry, "progress_05r": entry + 0.5 * risk, "adverse_05r": entry - 0.5 * risk}


def _plot_atlas(data: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas(data)
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
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            if not bars.empty and not pd.isna(entry_day):
                day = bars[bars["bar_date"].eq(entry_day)].copy().sort_values("bar_datetime").head(520).reset_index(drop=True)
            else:
                day = pd.DataFrame()
            if day.empty:
                ax.axis("off")
                ax.text(
                    0.5,
                    0.52,
                    (
                        f"missing entry-day minute bars\n{vt_symbol} {entry_day.date() if not pd.isna(entry_day) else ''}\n"
                        f"nearest_before_days={row.get('nearest_before_days')} nearest_after_days={row.get('nearest_after_days')}"
                    ),
                    ha="center",
                    va="center",
                )
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
                if len(day) >= 30:
                    ax.axvline(29, color="#0f172a", linestyle="-.", linewidth=0.9, alpha=0.75, label="30m")
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), fontsize=7, loc="best")
                ax.grid(True, alpha=0.18)
            cause = row.get("missing_cause") if row.get("missing_cause") != "not_missing" else row.get("quality_label")
            ax.set_title(
                (
                    f"{cause} {vt_symbol} {row.get('direction')} "
                    f"{entry_day.date().isoformat() if not pd.isna(entry_day) else 'NA'} "
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
                    "lot_id": row.get("lot_id"),
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_day.date().isoformat() if not pd.isna(entry_day) else "",
                    "direction": row.get("direction"),
                    "quality_label": row.get("quality_label"),
                    "missing_cause": row.get("missing_cause"),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "r_multiple": _safe_float(row.get("r_multiple")),
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


def _decision(summary: pd.DataFrame, missing_stats: pd.DataFrame, no_follow_year: pd.DataFrame, atlas_paths: list[Path]) -> dict[str, Any]:
    row = summary.iloc[0].to_dict()
    decision = "stage007_readonly_no_follow_promising_but_not_trade_rule"
    why = (
        "No-follow remains a useful negative-quality clue, but missing entry-day minute bars contain important right-tail winners "
        "and no-follow itself has positive years, so no executable rule is promoted."
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
        "missing_bucket_stats": missing_stats.to_dict(orient="records") if not missing_stats.empty else [],
        "no_follow_year_stats": no_follow_year.to_dict(orient="records") if not no_follow_year.empty else [],
        "paths": {
            "features": str(FEATURES_OUT),
            "missing_bucket_stats": str(MISSING_BUCKET_OUT),
            "no_follow_year_stats": str(NO_FOLLOW_YEAR_OUT),
            "no_follow_product_stats": str(NO_FOLLOW_PRODUCT_OUT),
            "contribution_curve": str(CONTRIBUTION_CURVE_OUT),
            "summary": str(SUMMARY_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "contribution_chart": str(CONTRIB_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_OUT),
        },
        "next_step": (
            "Repair or extend minute data only from authoritative historical minute sources. "
            "If that is not available, treat missing entry-day bars as a hard coverage limitation and avoid a minute-based official rule."
        ),
    }


def _write_report(
    summary: pd.DataFrame,
    missing_stats: pd.DataFrame,
    no_follow_year: pd.DataFrame,
    no_follow_product: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    lines = [
        f"# {STAGE} C9/15w missing/no-follow forensics",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- official live: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- stage nature: read-only coverage and negative-quality attribution; no executable candidate; no A/B.",
        f"- decision: `{decision['decision']}`",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=10),
        "",
        "## Missing Bucket Stats",
        "",
        _md_table(missing_stats, max_rows=20),
        "",
        "## No-Follow Year Stats",
        "",
        _md_table(no_follow_year, max_rows=30) if not no_follow_year.empty else "No no-follow rows.",
        "",
        "## Worst No-Follow Products",
        "",
        _md_table(no_follow_product, max_rows=20) if not no_follow_product.empty else "No no-follow product rows.",
        "",
        "## Visual Outputs",
        "",
        f"- official path chart: `{PATH_CHART_OUT}`",
        f"- contribution chart: `{CONTRIB_CHART_OUT}`",
        f"- atlas pages: `{len(atlas_paths)}`",
        "",
        "## Judgment",
        "",
        "- Missing entry-day minutes are a hard data coverage problem; this stage does not interpolate or fabricate minute bars.",
        "- No-follow is a promising negative-quality clue, but not a standalone trading rule because it has positive years and positive outlier winners.",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)

    official_curve = _load_official_curve()
    features = _load_features()
    enriched = _enrich(features, minute_by_symbol)
    missing_stats = _missing_bucket_stats(enriched)
    no_follow_year = _no_follow_year_stats(enriched)
    no_follow_product = _no_follow_product_stats(enriched)
    contribution = _contribution_curve(enriched)
    summary = _summary(official_curve, enriched, missing_stats, no_follow_year)

    _plot_path(official_curve, enriched)
    _plot_contribution(contribution)
    atlas_paths, atlas_manifest = _plot_atlas(enriched, minute_by_symbol)
    decision = _decision(summary, missing_stats, no_follow_year, atlas_paths)

    enriched.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    missing_stats.to_csv(MISSING_BUCKET_OUT, index=False, encoding="utf-8-sig")
    no_follow_year.to_csv(NO_FOLLOW_YEAR_OUT, index=False, encoding="utf-8-sig")
    no_follow_product.to_csv(NO_FOLLOW_PRODUCT_OUT, index=False, encoding="utf-8-sig")
    contribution.to_csv(CONTRIBUTION_CURVE_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), encoding="utf-8")
    _write_report(summary, missing_stats, no_follow_year, no_follow_product, atlas_paths, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))


if __name__ == "__main__":
    main()

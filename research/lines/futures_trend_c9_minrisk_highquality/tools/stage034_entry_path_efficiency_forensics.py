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


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage034"
MODEL_TAG = "stage034_entry_path_efficiency_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage034_c9_minrisk_entry_path_efficiency_forensics"

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
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage034_entry_path_efficiency_forensics"

FEATURES_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_coverage_features_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
SUMMARY_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_stats_{MODEL_TAG}.csv"
YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
PRODUCT_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_matrix_{MODEL_TAG}.csv"
CONTRIBUTION_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_efficiency_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_efficiency_scatter_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
FIRST_N_BARS = 30
ATLAS_WINDOW_BARS = 120
PER_PAGE = 4
MAX_ATLAS_ROWS = 20
EFFICIENCY_THRESHOLD = 0.50
HEAT_R = 0.50
TRADING_DAYS_PER_YEAR = 252


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    equity = pd.to_numeric(equity, errors="coerce").ffill()
    hwm = equity.cummax()
    return (equity / hwm - 1.0) * 100.0


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "slippage", "trade_count"]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    prev_equity = curve["account_equity"].shift(1)
    prev_equity.iloc[0] = CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev_equity - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _load_stage010_summary() -> dict[str, Any]:
    if not SUMMARY_IN.exists():
        return {}
    frame = _read_csv(SUMMARY_IN)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _official_metrics(curve: pd.DataFrame, features: pd.DataFrame) -> dict[str, float]:
    stage010 = _load_stage010_summary()
    returns = pd.to_numeric(curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    end = float(curve["account_equity"].iloc[-1]) if not curve.empty else CAPITAL
    pnl = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    return {
        "end_equity": _safe_float(stage010.get("end_equity"), end),
        "total_return_pct": _safe_float(stage010.get("total_return_pct"), (end / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": _safe_float(stage010.get("max_drawdown_pct"), float(curve["drawdown_pct"].min())),
        "sharpe": _safe_float(stage010.get("sharpe"), float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0),
        "total_slippage": _safe_float(stage010.get("total_slippage"), float(curve["slippage"].sum())),
        "total_trade_count": _safe_float(stage010.get("total_trade_count"), float(curve["trade_count"].sum())),
        "closed_lot_win_rate_pct": float((pnl > 0.0).mean() * 100.0) if len(pnl) else 0.0,
    }


def _normalize_day(value: Any) -> pd.Timestamp:
    return s010._normalize_day(value)


def _load_base_features() -> pd.DataFrame:
    data = _read_csv(FEATURES_IN)
    for column in ["entry_date", "exit_date", "entry_day", "exit_date_ts"]:
        if column in data.columns:
            data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    numeric_cols = [
        "realized_pnl",
        "r_multiple",
        "volume",
        "size",
        "entry_price",
        "exit_price",
        "risk_price",
        "risk_valid",
        "stage861_covered",
        "stage861_entry_day_minute_bars",
        "first_30m_directional_r",
        "first_30m_mfe_r",
        "first_30m_mae_r",
        "entry_day_mfe_r",
        "entry_day_mae_r",
    ]
    for column in numeric_cols:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in ["vt_symbol", "product", "direction", "coverage_bucket"]:
        data[column] = data[column].astype(str)
    if "entry_year" not in data.columns:
        data["entry_year"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.year
    else:
        data["entry_year"] = pd.to_numeric(data["entry_year"], errors="coerce")
    return data


def _directional_close_path(row: pd.Series, day: pd.DataFrame, n_bars: int) -> pd.Series:
    entry = _safe_float(row.get("entry_price"))
    risk = _safe_float(row.get("risk_price"))
    direction = str(row.get("direction"))
    first = day.head(n_bars).copy()
    closes = pd.to_numeric(first["close"], errors="coerce")
    if first.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return pd.Series(dtype=float)
    if direction == "short":
        return (entry - closes) / risk
    return (closes - entry) / risk


def _path_metrics(row: pd.Series, minute_groups: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row.get("vt_symbol"))
    entry_day = _normalize_day(row.get("entry_day"))
    if pd.isna(entry_day):
        entry_day = _normalize_day(row.get("entry_date"))
    day = s010._day_for_symbol(minute_groups, vt_symbol, entry_day)
    base = {
        "path_bars_used": 0,
        "path_net_r_30m": np.nan,
        "path_gross_r_30m": np.nan,
        "path_efficiency_30m": np.nan,
        "path_churn_ratio_30m": np.nan,
        "path_sign_flip_count_30m": np.nan,
        "path_positive_close_share_30m": np.nan,
        "path_max_adverse_close_r_30m": np.nan,
        "path_max_favorable_close_r_30m": np.nan,
        "path_quality_bucket": "missing_or_invalid_path",
    }
    if day.empty or int(_safe_float(row.get("stage861_covered"), 0.0)) != 1 or int(_safe_float(row.get("risk_valid"), 0.0)) != 1:
        return base
    path = _directional_close_path(row, day, FIRST_N_BARS).dropna()
    if path.empty:
        return base
    series = pd.concat([pd.Series([0.0]), path.reset_index(drop=True)], ignore_index=True)
    diffs = series.diff().dropna()
    gross = float(diffs.abs().sum())
    net = float(series.iloc[-1])
    efficiency = net / gross if gross > 0 else np.nan
    abs_net = abs(net)
    churn = gross / abs_net if abs_net > 1e-9 else np.inf if gross > 0 else np.nan
    signs = np.sign(series.replace(0.0, np.nan).ffill().fillna(0.0))
    sign_flips = int(((signs * signs.shift(1)) < 0).sum())
    positive_share = float((path > 0).mean()) if len(path) else np.nan
    max_adv = float(max(0.0, -path.min())) if len(path) else np.nan
    max_fav = float(max(0.0, path.max())) if len(path) else np.nan
    mae = _safe_float(row.get("first_30m_mae_r"))
    if not np.isfinite(net) or not np.isfinite(efficiency):
        bucket = "missing_or_invalid_path"
    elif net <= 0:
        bucket = "adverse_or_no_follow_path"
    elif np.isfinite(mae) and mae > HEAT_R:
        bucket = "follow_but_adverse_heat_path"
    elif efficiency >= EFFICIENCY_THRESHOLD and sign_flips <= 1:
        bucket = "efficient_follow_path"
    else:
        bucket = "noisy_follow_path"
    base.update(
        {
            "path_bars_used": int(len(path)),
            "path_net_r_30m": net,
            "path_gross_r_30m": gross,
            "path_efficiency_30m": efficiency,
            "path_churn_ratio_30m": churn if np.isfinite(churn) else np.nan,
            "path_sign_flip_count_30m": sign_flips,
            "path_positive_close_share_30m": positive_share,
            "path_max_adverse_close_r_30m": max_adv,
            "path_max_favorable_close_r_30m": max_fav,
            "path_quality_bucket": bucket,
        }
    )
    return base


def _augment_features(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    vt_symbols = sorted(data["vt_symbol"].dropna().astype(str).unique())
    minute_bars = s010.s008.s928._load_stage861_full_minute_bars(vt_symbols)
    minute_groups = s010.s008.s825._minute_groups(minute_bars)
    metrics = pd.DataFrame([_path_metrics(row, minute_groups) for _, row in data.iterrows()])
    out = pd.concat([data.reset_index(drop=True), metrics], axis=1)
    out["entry_year"] = pd.to_numeric(out["entry_year"], errors="coerce")
    out["positive_pnl"] = pd.to_numeric(out["realized_pnl"], errors="coerce").clip(lower=0.0)
    out["negative_pnl"] = pd.to_numeric(out["realized_pnl"], errors="coerce").clip(upper=0.0)
    return out, minute_groups


def _bucket_stats(features: pd.DataFrame) -> pd.DataFrame:
    total_pnl = float(features["realized_pnl"].fillna(0.0).sum())
    total_positive = float(features["positive_pnl"].fillna(0.0).sum())
    total_negative_abs = abs(float(features["negative_pnl"].fillna(0.0).sum()))
    rows: list[dict[str, Any]] = []
    for bucket, group in features.groupby("path_quality_bucket", dropna=False):
        pnl = float(group["realized_pnl"].fillna(0.0).sum())
        positive = float(group["positive_pnl"].fillna(0.0).sum())
        negative = float(group["negative_pnl"].fillna(0.0).sum())
        year_pnl = group.groupby("entry_year")["realized_pnl"].sum()
        rows.append(
            {
                "path_quality_bucket": str(bucket),
                "lots": int(len(group)),
                "products": int(group["product"].astype(str).nunique()) if "product" in group.columns else 0,
                "years": int(group["entry_year"].dropna().nunique()),
                "positive_years": int((year_pnl > 0).sum()),
                "negative_years": int((year_pnl < 0).sum()),
                "net_pnl": pnl,
                "net_pnl_share_pct": pnl / total_pnl * 100.0 if total_pnl else np.nan,
                "positive_pnl": positive,
                "positive_pnl_share_pct": positive / total_positive * 100.0 if total_positive else np.nan,
                "negative_pnl": negative,
                "negative_pnl_abs_share_pct": abs(negative) / total_negative_abs * 100.0 if total_negative_abs else np.nan,
                "median_path_net_r_30m": float(group["path_net_r_30m"].median()),
                "median_path_efficiency_30m": float(group["path_efficiency_30m"].median()),
                "median_path_gross_r_30m": float(group["path_gross_r_30m"].median()),
                "median_sign_flips": float(group["path_sign_flip_count_30m"].median()),
                "median_first_30m_mae_r": float(pd.to_numeric(group["first_30m_mae_r"], errors="coerce").median()),
                "avg_pnl_per_lot": pnl / len(group) if len(group) else np.nan,
            }
        )
    order = {
        "efficient_follow_path": 0,
        "noisy_follow_path": 1,
        "follow_but_adverse_heat_path": 2,
        "adverse_or_no_follow_path": 3,
        "missing_or_invalid_path": 4,
    }
    result = pd.DataFrame(rows)
    result["_order"] = result["path_quality_bucket"].map(order).fillna(99)
    return result.sort_values(["_order", "path_quality_bucket"]).drop(columns=["_order"]).reset_index(drop=True)


def _year_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = (
        features.pivot_table(
            index="path_quality_bucket",
            columns="entry_year",
            values="realized_pnl",
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
        .reset_index()
    )
    return matrix


def _product_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = (
        features.pivot_table(
            index="product",
            columns="path_quality_bucket",
            values="realized_pnl",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )
    value_cols = [col for col in matrix.columns if col != "product"]
    matrix["abs_total"] = matrix[value_cols].abs().sum(axis=1)
    return matrix.sort_values("abs_total", ascending=False).drop(columns=["abs_total"]).reset_index(drop=True)


def _contribution_curve(curve: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    lots = features.copy()
    lots["exit_date_ts"] = pd.to_datetime(lots.get("exit_date_ts", lots.get("exit_date")), errors="coerce").dt.normalize()
    lots["realized_pnl"] = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    daily_all = lots.groupby("exit_date_ts")["realized_pnl"].sum()
    out["cum_pnl_all_closed_lots"] = out["date"].map(daily_all).fillna(0.0).cumsum()
    for bucket in sorted(lots["path_quality_bucket"].dropna().astype(str).unique()):
        daily = lots[lots["path_quality_bucket"].astype(str).eq(bucket)].groupby("exit_date_ts")["realized_pnl"].sum()
        out[f"cum_pnl_path_bucket_{bucket}"] = out["date"].map(daily).fillna(0.0).cumsum()
    return out


def _plot_path(contrib: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(contrib["date"], contrib["account_equity"], color="#111827", linewidth=1.1, label="official equity")
    axes[0].set_title("Official C9/15w equity")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(contrib["date"], contrib["drawdown_pct"], color="#dc2626", linewidth=1.0, label="drawdown %")
    axes[1].set_title("Official drawdown and broker10")
    axes[1].grid(True, alpha=0.25)
    ax2 = axes[1].twinx()
    ax2.plot(contrib["date"], contrib["broker10_margin_to_equity_pct"], color="#2563eb", linewidth=0.8, alpha=0.75)

    colors = {
        "cum_pnl_path_bucket_efficient_follow_path": "#16a34a",
        "cum_pnl_path_bucket_noisy_follow_path": "#2563eb",
        "cum_pnl_path_bucket_follow_but_adverse_heat_path": "#f97316",
        "cum_pnl_path_bucket_adverse_or_no_follow_path": "#dc2626",
        "cum_pnl_path_bucket_missing_or_invalid_path": "#6b7280",
    }
    axes[2].plot(contrib["date"], contrib["cum_pnl_all_closed_lots"], color="#111827", linewidth=1.2, label="all closed lots")
    for column, color in colors.items():
        if column in contrib.columns:
            axes[2].plot(contrib["date"], contrib[column], color=color, linewidth=1.0, label=column.replace("cum_pnl_path_bucket_", ""))
    axes[2].axhline(0, color="#6b7280", linewidth=0.8)
    axes[2].set_title("Cumulative realized PnL by first-30m close-path efficiency bucket")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best", fontsize=8)
    fig.suptitle("Stage034 entry close-path efficiency forensics", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_year_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    data = matrix.set_index("path_quality_bucket")
    columns = [col for col in data.columns]
    values = data.to_numpy(dtype=float)
    max_abs = float(np.nanmax(np.abs(values))) if values.size else 1.0
    max_abs = max_abs if max_abs > 0 else 1.0
    fig, ax = plt.subplots(figsize=(13, max(4, 0.6 * len(data.index) + 2)), constrained_layout=True)
    im = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-max_abs, vmax=max_abs)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index, fontsize=8)
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels([str(int(col)) if pd.notna(col) else "" for col in columns], fontsize=8, rotation=45)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    ax.set_title("Net PnL by entry year and path-efficiency bucket")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="net PnL")
    fig.savefig(BUCKET_YEAR_HEATMAP_OUT, dpi=150)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    data = features.copy()
    data = data[data["path_quality_bucket"].ne("missing_or_invalid_path")].copy()
    if data.empty:
        return
    data["realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").fillna(0.0)
    colors = data["realized_pnl"].clip(lower=-500_000, upper=500_000)
    fig, ax = plt.subplots(figsize=(11, 7), constrained_layout=True)
    scatter = ax.scatter(
        data["path_efficiency_30m"],
        data["path_net_r_30m"],
        c=colors,
        cmap="RdYlGn",
        s=np.sqrt(pd.to_numeric(data["volume"], errors="coerce").fillna(1.0).clip(lower=1.0)) * 10,
        alpha=0.72,
        edgecolors="#374151",
        linewidths=0.25,
    )
    ax.axhline(0, color="#6b7280", linewidth=0.8)
    ax.axvline(EFFICIENCY_THRESHOLD, color="#16a34a", linewidth=0.8, linestyle="--")
    ax.set_xlabel("first-30m path efficiency = net directional R / gross close-path R")
    ax.set_ylabel("first-30m net directional R")
    ax.set_title("Close-path efficiency vs realized PnL")
    ax.grid(True, alpha=0.25)
    fig.colorbar(scatter, ax=ax, fraction=0.025, pad=0.02, label="realized PnL clipped")
    fig.savefig(SCATTER_OUT, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    parts = [
        features[features["path_quality_bucket"].eq("efficient_follow_path")].nsmallest(4, "realized_pnl"),
        features[features["path_quality_bucket"].eq("efficient_follow_path")].nlargest(4, "realized_pnl"),
        features[features["path_quality_bucket"].eq("noisy_follow_path")].nsmallest(4, "realized_pnl"),
        features[features["path_quality_bucket"].eq("noisy_follow_path")].nlargest(4, "realized_pnl"),
        features[features["path_quality_bucket"].eq("adverse_or_no_follow_path")].nlargest(4, "realized_pnl"),
        features[features["path_quality_bucket"].eq("follow_but_adverse_heat_path")].nlargest(4, "realized_pnl"),
    ]
    out = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    if out.empty:
        return out
    return out.drop_duplicates(subset=["lot_id", "vt_symbol", "entry_date"]).head(MAX_ATLAS_ROWS).reset_index(drop=True)


def _plot_atlas(features: pd.DataFrame, minute_groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    rows = _select_atlas_rows(features)
    if rows.empty:
        return [], pd.DataFrame()
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page_idx, start in enumerate(range(0, len(rows), PER_PAGE), start=1):
        subset = rows.iloc[start : start + PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(subset), 1, figsize=(13, 3.3 * len(subset)), constrained_layout=True)
        if len(subset) == 1:
            axes = np.array([axes])
        for ax, (_, row) in zip(axes, subset.iterrows()):
            vt_symbol = str(row.get("vt_symbol"))
            entry_day = _normalize_day(row.get("entry_day"))
            day = s010._day_for_symbol(minute_groups, vt_symbol, entry_day)
            path = _directional_close_path(row, day, ATLAS_WINDOW_BARS)
            if path.empty:
                ax.text(0.5, 0.5, "missing minute close path", transform=ax.transAxes, ha="center", va="center")
            else:
                x = np.arange(1, len(path) + 1)
                ax.plot(x, path.to_numpy(dtype=float), color="#111827", linewidth=1.1)
                ax.axvline(FIRST_N_BARS, color="#2563eb", linestyle="--", linewidth=0.8, alpha=0.8)
                ax.axhline(0, color="#6b7280", linewidth=0.8)
                ax.axhline(HEAT_R, color="#16a34a", linewidth=0.6, alpha=0.45)
                ax.axhline(-HEAT_R, color="#dc2626", linewidth=0.6, alpha=0.45)
                ax.fill_between(x, 0, path.to_numpy(dtype=float), where=path.to_numpy(dtype=float) >= 0, color="#16a34a", alpha=0.12)
                ax.fill_between(x, 0, path.to_numpy(dtype=float), where=path.to_numpy(dtype=float) < 0, color="#dc2626", alpha=0.12)
            title = (
                f"{row.get('path_quality_bucket')} | {vt_symbol} {row.get('direction')} {pd.Timestamp(row.get('entry_day')).date()} "
                f"| pnl={_safe_float(row.get('realized_pnl'), 0):,.0f} | net30={_safe_float(row.get('path_net_r_30m'), 0):.2f}R "
                f"| eff={_safe_float(row.get('path_efficiency_30m'), 0):.2f} | flips={_safe_float(row.get('path_sign_flip_count_30m'), 0):.0f}"
            )
            ax.set_title(title, loc="left", fontsize=9)
            ax.set_ylabel("directional R")
            ax.grid(True, alpha=0.25)
            manifest.append(
                {
                    "page": page_idx,
                    "lot_id": row.get("lot_id"),
                    "vt_symbol": vt_symbol,
                    "entry_day": pd.Timestamp(row.get("entry_day")).date().isoformat() if pd.notna(row.get("entry_day")) else "",
                    "path_quality_bucket": row.get("path_quality_bucket"),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "path_net_r_30m": _safe_float(row.get("path_net_r_30m")),
                    "path_efficiency_30m": _safe_float(row.get("path_efficiency_30m")),
                    "path_sign_flip_count_30m": _safe_float(row.get("path_sign_flip_count_30m")),
                }
            )
        axes[-1].set_xlabel("entry-day minute close index")
        fig.suptitle("Stage034 first-30m close-path efficiency atlas", fontsize=12)
        path = Path(str(ATLAS_TEMPLATE).format(page=page_idx))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    manifest_frame = pd.DataFrame(manifest)
    manifest_frame.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    return paths, manifest_frame


def _summary_frame(metrics: dict[str, float], features: pd.DataFrame, bucket_stats: pd.DataFrame, atlas_paths: list[Path]) -> pd.DataFrame:
    ready = features[features["path_quality_bucket"].ne("missing_or_invalid_path")].copy()
    efficient = bucket_stats[bucket_stats["path_quality_bucket"].eq("efficient_follow_path")]
    noisy = bucket_stats[bucket_stats["path_quality_bucket"].eq("noisy_follow_path")]
    adverse = bucket_stats[bucket_stats["path_quality_bucket"].eq("adverse_or_no_follow_path")]
    heat = bucket_stats[bucket_stats["path_quality_bucket"].eq("follow_but_adverse_heat_path")]

    def stat(frame: pd.DataFrame, column: str) -> float:
        return _safe_float(frame.iloc[0].get(column)) if not frame.empty else np.nan

    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "end_equity": metrics["end_equity"],
        "total_return_pct": metrics["total_return_pct"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "sharpe": metrics["sharpe"],
        "total_slippage": metrics["total_slippage"],
        "total_trade_count": metrics["total_trade_count"],
        "closed_lot_win_rate_pct": metrics["closed_lot_win_rate_pct"],
        "closed_lot_count": int(len(features)),
        "path_ready_lot_count": int(len(ready)),
        "path_ready_pct": len(ready) / len(features) * 100.0 if len(features) else 0.0,
        "efficient_follow_lots": int(stat(efficient, "lots")) if not efficient.empty else 0,
        "efficient_follow_net_pnl": stat(efficient, "net_pnl"),
        "efficient_follow_negative_pnl_abs_share_pct": stat(efficient, "negative_pnl_abs_share_pct"),
        "noisy_follow_lots": int(stat(noisy, "lots")) if not noisy.empty else 0,
        "noisy_follow_net_pnl": stat(noisy, "net_pnl"),
        "adverse_or_no_follow_lots": int(stat(adverse, "lots")) if not adverse.empty else 0,
        "adverse_or_no_follow_net_pnl": stat(adverse, "net_pnl"),
        "follow_but_adverse_heat_lots": int(stat(heat, "lots")) if not heat.empty else 0,
        "follow_but_adverse_heat_net_pnl": stat(heat, "net_pnl"),
        "atlas_pages": int(len(atlas_paths)),
        "decision": "stage034_path_efficiency_readonly_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
    }
    return pd.DataFrame([row])


def _write_report(
    summary: pd.DataFrame,
    bucket_stats: pd.DataFrame,
    year_matrix: pd.DataFrame,
    product_matrix: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    row = summary.iloc[0].to_dict()
    text = f"""# Stage034 入场前 30 分钟 close-path efficiency 只读法证

## 定位

- 时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}
- 工作模式：day。
- 研究线：`{LINE_ID}`。
- 官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。
- 阶段性质：只读分钟 close path 法证；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API。

## 外部调研结论

- AQR 的长期趋势跟随证据强调：趋势跟随的普世性来自跨市场、跨年代的价格趋势与风险归一化，而不是单一市场/年份补丁。
- Intraday time-series momentum 研究说明：日内早段走势可能对后续走势有预测力，但跨市场共性有限；不能把单一 opening range 形状直接写成规则。
- Opening range breakout 文献证明首段区间可作为日内动量框架，但本线 Stage009 已反证“反向突破硬退出”会砍 C9 右尾。因此本阶段只审计 close path 的方向持久性和噪声，不做退出或降仓。
- 我的判断：如果高质量信号真的适合“最小风险搏最大收益”，入场后短窗口应体现方向净推进相对总波动更高；但只有跨年、跨品种且不砍右尾，才可能进入下一阶段真引擎。

## 官方基准

- 期末权益：`{row["end_equity"]:,.2f}`
- 总收益：`{row["total_return_pct"]:.4f}%`
- 最大回撤：`{row["max_drawdown_pct"]:.4f}%`
- Sharpe：`{row["sharpe"]:.4f}`
- 总滑点：`{row["total_slippage"]:,.0f}`
- 总交易次数：`{row["total_trade_count"]:,.0f}`
- closed-lot 胜率：`{row["closed_lot_win_rate_pct"]:.4f}%`

## 核心结果

- official closed lots：`{int(row["closed_lot_count"])}`。
- path ready lots：`{int(row["path_ready_lot_count"])}`，ready ratio：`{row["path_ready_pct"]:.4f}%`。
- efficient follow：`{int(row["efficient_follow_lots"])}` 笔，净 PnL `{row["efficient_follow_net_pnl"]:,.2f}`，负收益绝对覆盖 `{row["efficient_follow_negative_pnl_abs_share_pct"]:.4f}%`。
- noisy follow：`{int(row["noisy_follow_lots"])}` 笔，净 PnL `{row["noisy_follow_net_pnl"]:,.2f}`。
- adverse/no-follow：`{int(row["adverse_or_no_follow_lots"])}` 笔，净 PnL `{row["adverse_or_no_follow_net_pnl"]:,.2f}`。
- follow but adverse heat：`{int(row["follow_but_adverse_heat_lots"])}` 笔，净 PnL `{row["follow_but_adverse_heat_net_pnl"]:,.2f}`。
- 决策：`{row["decision"]}`，`candidate_ready=0`，`ab_triggered=0`。

## bucket stats

{_md_table(bucket_stats, max_rows=20)}

## 年度矩阵

{_md_table(year_matrix, max_rows=20)}

## 产品矩阵前列

{_md_table(product_matrix, max_rows=20)}

## 输出文件

- features：`{FEATURES_OUT}`
- bucket stats：`{BUCKET_STATS_OUT}`
- contribution curve：`{CONTRIBUTION_CURVE_OUT}`
- path chart：`{PATH_CHART_OUT}`
- bucket-year heatmap：`{BUCKET_YEAR_HEATMAP_OUT}`
- scatter：`{SCATTER_OUT}`
- atlas manifest：`{ATLAS_MANIFEST_OUT}`
{chr(10).join(f"- atlas：`{path}`" for path in atlas_paths)}

## 视觉观察

- path chart 用官方权益、回撤、broker10 与 path bucket 贡献曲线同屏检查，避免只看 bucket 统计。
- bucket-year heatmap 检查 path bucket 是否只是某一年或某个弱窗口的产物。
- scatter 检查 `path_efficiency_30m` 与 `path_net_r_30m` 是否能把正负盈亏分开。
- atlas 逐笔看 close path：重点看 efficient follow 的失败样本、noisy follow 的赢家、adverse/no-follow 的赢家，判断是否存在明显 false positive/false negative。

## 过拟合与继续价值

- 运行前判断：不做交易规则时不过拟合；如果用 `0.50` efficiency 或 `0.5R` heat 直接降仓会过拟合。
- 运行后判断：以结果表和视觉为准；本阶段只读，不进入候选。
- 是否值得继续：只有当 bucket 贡献跨年稳定、负收益捕获明显且右尾漏损可接受时，才允许下一阶段冻结一个真引擎；否则停止 close-path efficiency 分支。

## TODO

- 若 path efficiency 只是把已知 no-follow/clean 重新命名，停止该分支。
- 若出现跨年、跨品种、低负收益覆盖且不砍右尾的稳健结构，再设计唯一冻结真引擎；不得扫窗口、效率阈值、R 阈值、品种、方向、年份或月份。
"""
    REPORT_OUT.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = _load_base_features()
    features, minute_groups = _augment_features(base)
    curve = _load_curve()
    metrics = _official_metrics(curve, features)
    bucket_stats = _bucket_stats(features)
    year_matrix = _year_matrix(features)
    product_matrix = _product_matrix(features)
    contrib = _contribution_curve(curve, features)

    _plot_path(contrib)
    _plot_year_heatmap(year_matrix)
    _plot_scatter(features)
    atlas_paths, atlas_manifest = _plot_atlas(features, minute_groups)
    summary = _summary_frame(metrics, features, bucket_stats, atlas_paths)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    bucket_stats.to_csv(BUCKET_STATS_OUT, index=False, encoding="utf-8-sig")
    year_matrix.to_csv(YEAR_MATRIX_OUT, index=False, encoding="utf-8-sig")
    product_matrix.to_csv(PRODUCT_MATRIX_OUT, index=False, encoding="utf-8-sig")
    contrib.to_csv(CONTRIBUTION_CURVE_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    if atlas_manifest.empty:
        pd.DataFrame().to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")

    decision = summary.iloc[0].to_dict()
    decision.update(
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "external_research": {
                "trend_following_century": "AQR/JPM evidence supports trend following as broad, long-horizon, risk-normalized behavior; avoid local patches.",
                "intraday_time_series_momentum": "ITSM evidence supports auditing early intraday continuation, but cross-market commonality is limited.",
                "opening_range": "ORB literature motivates first-window path diagnostics; Stage009 already rejected hard opening-range exit for C9.",
                "judgement": "Use first-30m close-path efficiency as readonly diagnostic only; no threshold promotion.",
            },
            "visual_outputs": {
                "path_chart": PATH_CHART_OUT,
                "bucket_year_heatmap": BUCKET_YEAR_HEATMAP_OUT,
                "scatter": SCATTER_OUT,
                "atlas_pages": atlas_paths,
            },
        }
    )
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, bucket_stats, year_matrix, product_matrix, atlas_paths)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

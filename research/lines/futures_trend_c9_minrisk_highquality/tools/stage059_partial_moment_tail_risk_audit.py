from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage059"
MODEL_TAG = "stage059_partial_moment_tail_risk_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage059_c9_minrisk_partial_moment_tail_risk_audit"

WINDOW = 126
MIN_PERIODS = 63
MAX_SIGNAL_AGE_DAYS = 7
INITIAL_CAPITAL = 150_000.0
TARGET_BUCKET = "adverse_tail_dominant"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE052_DIR = LINE_DIR / "outputs" / "stage052_product_trend_tstat_stage496_reaudit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage059_partial_moment_tail_risk_audit"

FEATURES_IN = (
    STAGE052_DIR
    / "qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_features_"
    "stage052_product_trend_tstat_stage496_reaudit_v1.csv"
)
PRODUCT_DAILY_IN = (
    STAGE052_DIR
    / "qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_product_trend_daily_"
    "stage052_product_trend_tstat_stage496_reaudit_v1.csv"
)
CURVE_IN = (
    STAGE052_DIR
    / "qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_upper_bound_curve_"
    "stage052_product_trend_tstat_stage496_reaudit_v1.csv"
)
STAGE052_DECISION_IN = (
    STAGE052_DIR
    / "qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_decision_"
    "stage052_product_trend_tstat_stage496_reaudit_v1.json"
)

PARTIAL_MOMENT_DAILY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_partial_moment_daily_{MODEL_TAG}.csv"
FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
BUCKET_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
PRODUCT_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_matrix_{MODEL_TAG}.csv"
QUARTILE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_score_quartile_summary_{MODEL_TAG}.csv"
TARGET_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_lots_{MODEL_TAG}.csv"
UPPER_BOUND_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_path_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_contribution_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
PRODUCT_BUCKET_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_score_scatter_{MODEL_TAG}.png"

BUCKET_COLORS = {
    "adverse_tail_dominant": "#d62728",
    "favorable_tail_not_worse": "#2ca02c",
    "tail_moment_missing": "#7f7f7f",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    features = _read_csv(FEATURES_IN)
    daily = _read_csv(PRODUCT_DAILY_IN)
    curve = _read_csv(CURVE_IN)
    decision = _read_json(STAGE052_DECISION_IN)

    for column in ["entry_date", "exit_date", "exit_day", "prev_state_date"]:
        if column in features.columns:
            features[column] = pd.to_datetime(features[column], errors="coerce")
    for column in [
        "realized_pnl",
        "negative_pnl_abs",
        "entry_year",
        "exit_year",
        "first_30m_directional_r",
        "first_30m_mfe_r",
        "first_30m_mae_r",
        "mae_r",
        "mfe_r",
        "direction_aligned_trend_tstat_252_stage052",
    ]:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily["synthetic_close"] = pd.to_numeric(daily["synthetic_close"], errors="coerce")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        if column in curve.columns:
            curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return features, daily, curve, decision


def _build_partial_moment_daily(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    source = daily[
        daily["date"].notna()
        & daily["product_key"].notna()
        & daily["synthetic_close"].notna()
        & daily["synthetic_close"].gt(0)
    ].copy()
    for product, group in source.sort_values(["product_key", "date"]).groupby("product_key", sort=True):
        item = group.sort_values("date").copy()
        ret_1d = np.log(item["synthetic_close"].astype(float)).diff()
        upm2_long = ret_1d.clip(lower=0).pow(2).rolling(WINDOW, min_periods=MIN_PERIODS).mean()
        lpm2_long = (-ret_1d).clip(lower=0).pow(2).rolling(WINDOW, min_periods=MIN_PERIODS).mean()
        item["ret_1d"] = ret_1d
        item["upm2_long"] = upm2_long
        item["lpm2_long"] = lpm2_long
        item["upm2_short"] = lpm2_long
        item["lpm2_short"] = upm2_long
        item["tail_moment_ready"] = upm2_long.notna() & lpm2_long.notna()
        item["long_tail_score"] = np.log((item["lpm2_long"] + 1e-12) / (item["upm2_long"] + 1e-12))
        item["short_tail_score"] = np.log((item["lpm2_short"] + 1e-12) / (item["upm2_short"] + 1e-12))
        rows.append(
            item[
                [
                    "date",
                    "product_key",
                    "vt_symbol",
                    "exchange",
                    "synthetic_close",
                    "ret_1d",
                    "upm2_long",
                    "lpm2_long",
                    "upm2_short",
                    "lpm2_short",
                    "long_tail_score",
                    "short_tail_score",
                    "tail_moment_ready",
                ]
            ].copy()
        )
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).sort_values(["product_key", "date"]).reset_index(drop=True)


def _feature_product_key(features: pd.DataFrame) -> pd.Series:
    normalized = features.get("normalized_product", pd.Series(index=features.index, dtype=object)).fillna("").astype(str)
    product_key = features.get("product_key", pd.Series(index=features.index, dtype=object)).fillna("").astype(str)
    out = normalized.where(normalized.str.contains(".", regex=False), product_key)
    return out.where(out.str.contains(".", regex=False), normalized)


def _bind_features(features: pd.DataFrame, pm_daily: pd.DataFrame) -> pd.DataFrame:
    features = features.copy()
    features["stage059_product_key"] = _feature_product_key(features)
    bound: list[pd.DataFrame] = []
    for product, group in features.groupby("stage059_product_key", dropna=False):
        left = group.sort_values("prev_state_date").copy()
        right = pm_daily[pm_daily["product_key"].eq(product)].sort_values("date").copy()
        if right.empty:
            item = left.copy()
            item["stage059_source_date"] = pd.NaT
            item["stage059_signal_age_days"] = np.nan
            item["stage059_tail_ready"] = False
            item["directional_upm2_126"] = np.nan
            item["directional_lpm2_126"] = np.nan
            item["stage059_tail_score"] = np.nan
            item["stage059_tail_bucket"] = "tail_moment_missing"
            bound.append(item)
            continue
        merged = pd.merge_asof(
            left,
            right,
            left_on="prev_state_date",
            right_on="date",
            direction="backward",
            tolerance=pd.Timedelta(days=MAX_SIGNAL_AGE_DAYS),
            suffixes=("", "_pm"),
        )
        direction_sign = np.where(merged["direction"].fillna("").astype(str).str.lower().eq("short"), -1, 1)
        directional_upm2 = np.where(direction_sign == 1, merged["upm2_long"], merged["upm2_short"])
        directional_lpm2 = np.where(direction_sign == 1, merged["lpm2_long"], merged["lpm2_short"])
        merged["direction_sign"] = direction_sign
        merged["stage059_source_date"] = merged["date"]
        merged["stage059_signal_age_days"] = (merged["prev_state_date"] - merged["stage059_source_date"]).dt.days
        merged["directional_upm2_126"] = directional_upm2
        merged["directional_lpm2_126"] = directional_lpm2
        ready = merged["tail_moment_ready"].apply(lambda value: bool(value) if pd.notna(value) else False)
        merged["stage059_tail_ready"] = ready
        merged["stage059_tail_score"] = np.log((directional_lpm2 + 1e-12) / (directional_upm2 + 1e-12))
        merged["stage059_tail_bucket"] = "tail_moment_missing"
        merged.loc[
            ready & (merged["directional_lpm2_126"] > merged["directional_upm2_126"]),
            "stage059_tail_bucket",
        ] = "adverse_tail_dominant"
        merged.loc[
            ready & (merged["directional_lpm2_126"] <= merged["directional_upm2_126"]),
            "stage059_tail_bucket",
        ] = "favorable_tail_not_worse"
        bound.append(merged)
    out = pd.concat(bound, ignore_index=True)
    out = out.sort_values(["entry_date", "lot_id"]).reset_index(drop=True)
    return out


def _group_summary(data: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (
        data.groupby(keys, dropna=False)
        .agg(
            lot_count=("lot_id", "count"),
            product_count=("stage059_product_key", "nunique"),
            year_count=("entry_year", "nunique"),
            net_pnl=("realized_pnl", "sum"),
            positive_pnl=("realized_pnl", lambda item: item[item > 0].sum()),
            negative_pnl_abs=("realized_pnl", lambda item: -item[item < 0].sum()),
            positive_lot_count=("realized_pnl", lambda item: int((item > 0).sum())),
            negative_lot_count=("realized_pnl", lambda item: int((item < 0).sum())),
            median_tail_score=("stage059_tail_score", "median"),
            median_first_30m_directional_r=("first_30m_directional_r", "median"),
            median_direction_aligned_tstat=("direction_aligned_trend_tstat_252_stage052", "median"),
        )
        .reset_index()
        .sort_values(["net_pnl", "lot_count"], ascending=[False, False])
    )


def _quartile_summary(data: pd.DataFrame) -> pd.DataFrame:
    valid = data[data["stage059_tail_ready"].astype(bool) & data["stage059_tail_score"].notna()].copy()
    if valid.empty:
        return pd.DataFrame()
    ranks = valid["stage059_tail_score"].rank(method="first")
    valid["tail_score_quartile"] = pd.qcut(
        ranks,
        q=min(4, valid["stage059_tail_score"].nunique(), len(valid)),
        labels=False,
        duplicates="drop",
    )
    valid["tail_score_quartile"] = valid["tail_score_quartile"].map(lambda value: f"q{int(value) + 1}_low_to_high")
    return _group_summary(valid, ["tail_score_quartile"])


def _upper_bound_curve(curve: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    events = features.copy()
    events["exit_day_norm"] = pd.to_datetime(events["exit_day"], errors="coerce").dt.normalize()
    events["target_realized_pnl"] = np.where(events["stage059_tail_bucket"].eq(TARGET_BUCKET), events["realized_pnl"], 0.0)
    events["target_lot_count"] = np.where(events["stage059_tail_bucket"].eq(TARGET_BUCKET), 1, 0)
    daily = (
        events.groupby("exit_day_norm", dropna=False)[["target_realized_pnl", "target_lot_count"]]
        .sum()
        .reset_index()
        .rename(columns={"exit_day_norm": "date"})
    )
    out = out.merge(daily, on="date", how="left")
    out["target_realized_pnl"] = out["target_realized_pnl"].fillna(0.0)
    out["target_lot_count"] = out["target_lot_count"].fillna(0).astype(int)
    out["skipped_target_pnl_cumsum"] = out["target_realized_pnl"].cumsum()
    out["upper_bound_skip_target_equity"] = out["account_equity"] - out["skipped_target_pnl_cumsum"]
    out["official_drawdown_pct_recalc"] = _drawdown_pct(out["account_equity"])
    out["upper_bound_drawdown_pct"] = _drawdown_pct(out["upper_bound_skip_target_equity"])
    out["official_nav"] = out["account_equity"] / INITIAL_CAPITAL
    out["upper_bound_nav"] = out["upper_bound_skip_target_equity"] / INITIAL_CAPITAL
    return out


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    equity = pd.to_numeric(equity, errors="coerce")
    hwm = equity.cummax()
    return (equity / hwm - 1.0) * 100.0


def _performance_from_curve(curve: pd.DataFrame, equity_col: str, dd_col: str) -> dict[str, float]:
    equity = pd.to_numeric(curve[equity_col], errors="coerce").dropna()
    if equity.empty:
        return {"end_equity": np.nan, "total_return_pct": np.nan, "max_dd_pct": np.nan, "daily_sharpe_proxy": np.nan}
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = np.nan
    if len(returns) > 2 and returns.std(ddof=0) > 0:
        sharpe = float(returns.mean() / returns.std(ddof=0) * np.sqrt(252.0))
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(pd.to_numeric(curve[dd_col], errors="coerce").min()),
        "daily_sharpe_proxy": sharpe,
    }


def _contribution_curve(features: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    data = features.copy()
    data["exit_day_norm"] = pd.to_datetime(data["exit_day"], errors="coerce").dt.normalize()
    for bucket in BUCKET_COLORS:
        data[f"pnl_{bucket}"] = np.where(data["stage059_tail_bucket"].eq(bucket), data["realized_pnl"], 0.0)
    daily_columns = [f"pnl_{bucket}" for bucket in BUCKET_COLORS]
    daily = data.groupby("exit_day_norm", dropna=False)[daily_columns].sum().reset_index().rename(columns={"exit_day_norm": "date"})
    out = out.merge(daily, on="date", how="left")
    for column in daily_columns:
        out[column] = out[column].fillna(0.0)
        out[f"cum_{column}"] = out[column].cumsum()
    return out


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2, 1.2, 1]})
    axes[0].plot(curve["date"], curve["account_equity"], lw=1.3, color="#1f77b4", label="official equity")
    axes[0].plot(
        curve["date"],
        curve["upper_bound_skip_target_equity"],
        lw=1.3,
        color="#d62728",
        label="diagnostic skip adverse-tail-dominant equity",
    )
    axes[0].set_yscale("log")
    axes[0].set_title("Stage059 partial-moment tail risk upper-bound diagnostic")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")

    axes[1].plot(
        curve["date"],
        curve["skipped_target_pnl_cumsum"],
        lw=1.3,
        color="#d62728",
        label="cum skipped target PnL",
    )
    axes[1].axhline(0, color="#555555", lw=0.8)
    axes[1].set_ylabel("PnL")
    axes[1].legend(loc="upper left")

    axes[2].plot(curve["date"], curve["official_drawdown_pct_recalc"], color="#8c564b", lw=1.1, label="official DD %")
    axes[2].plot(curve["date"], curve["upper_bound_drawdown_pct"], color="#d62728", lw=1.1, label="skip-target DD %")
    axes[2].plot(
        curve["date"],
        curve["broker10_margin_to_equity_pct"],
        color="#9467bd",
        lw=0.9,
        alpha=0.75,
        label="broker10 %",
    )
    axes[2].axhline(-40, color="#8c564b", ls="--", lw=0.8)
    axes[2].axhline(100, color="#9467bd", ls="--", lw=0.8)
    axes[2].set_ylabel("pct")
    axes[2].legend(loc="upper left", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_contribution(contrib: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    for bucket, color in BUCKET_COLORS.items():
        column = f"cum_pnl_{bucket}"
        axes[0].plot(contrib["date"], contrib[column], lw=1.3, color=color, label=bucket)
    axes[0].axhline(0, color="#555555", lw=0.8)
    axes[0].set_title("Stage059 cumulative PnL by directional partial-moment bucket")
    axes[0].set_ylabel("cum PnL")
    axes[0].legend(loc="upper left", fontsize=8)
    axes[1].plot(contrib["date"], contrib["account_equity"], color="#1f77b4", lw=1.1, label="official equity")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("equity log")
    axes[1].legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_bucket_year(bucket_year: pd.DataFrame) -> None:
    if bucket_year.empty:
        return
    pivot = bucket_year.pivot_table(index="stage059_tail_bucket", columns="exit_year", values="realized_pnl", aggfunc="sum", fill_value=0.0)
    order = [bucket for bucket in BUCKET_COLORS if bucket in pivot.index]
    pivot = pivot.loc[order]
    values = pivot.values
    vmax = max(float(np.nanmax(np.abs(values))), 1.0)
    fig, ax = plt.subplots(figsize=(12, 5))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Stage059 bucket-year realized PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values[i, j]
            if abs(value) >= vmax * 0.08:
                ax.text(j, i, f"{value/1000:.0f}k", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, label="PnL")
    fig.tight_layout()
    fig.savefig(BUCKET_YEAR_HEATMAP_OUT, dpi=150)
    plt.close(fig)


def _plot_product_bucket(product_bucket: pd.DataFrame) -> None:
    if product_bucket.empty:
        return
    product_totals = product_bucket.groupby("stage059_product_key")["realized_pnl"].sum().abs().sort_values(ascending=False)
    top_products = product_totals.head(18).index.tolist()
    temp = product_bucket[product_bucket["stage059_product_key"].isin(top_products)].copy()
    pivot = temp.pivot_table(
        index="stage059_product_key",
        columns="stage059_tail_bucket",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    pivot = pivot.reindex(top_products)
    pivot = pivot[[bucket for bucket in BUCKET_COLORS if bucket in pivot.columns]]
    values = pivot.values
    vmax = max(float(np.nanmax(np.abs(values))), 1.0)
    fig, ax = plt.subplots(figsize=(11, max(6, 0.35 * len(pivot) + 2)))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Stage059 product-bucket realized PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values[i, j]
            if abs(value) >= vmax * 0.08:
                ax.text(j, i, f"{value/1000:.0f}k", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, label="PnL")
    fig.tight_layout()
    fig.savefig(PRODUCT_BUCKET_HEATMAP_OUT, dpi=150)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    specs = [
        ("stage059_tail_score", "realized_pnl", "tail score vs realized PnL"),
        ("stage059_tail_score", "first_30m_directional_r", "tail score vs first 30m directional R"),
        ("stage059_tail_score", "direction_aligned_trend_tstat_252_stage052", "tail score vs aligned trend t-stat"),
        ("stage059_tail_score", "mae_r", "tail score vs whole-trade MAE R"),
    ]
    max_abs_pnl = max(float(features["realized_pnl"].abs().max()), 1.0)
    for ax, (x_col, y_col, title) in zip(axes.ravel(), specs):
        for bucket, group in features.groupby("stage059_tail_bucket"):
            valid = group.dropna(subset=[x_col, y_col])
            if valid.empty:
                continue
            sizes = 18 + 240 * valid["realized_pnl"].abs() / max_abs_pnl
            ax.scatter(
                valid[x_col],
                valid[y_col],
                s=sizes,
                alpha=0.68,
                color=BUCKET_COLORS.get(bucket, "#7f7f7f"),
                edgecolors="#222222",
                linewidths=0.25,
                label=bucket,
            )
        ax.axhline(0, color="#555555", lw=0.7)
        ax.axvline(0, color="#555555", lw=0.7)
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(title)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=8)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(SCATTER_OUT, dpi=150)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    bucket_summary: pd.DataFrame,
    quartile_summary: pd.DataFrame,
    bucket_year: pd.DataFrame,
    product_bucket: pd.DataFrame,
) -> None:
    lines = [
        "# Stage059 partial-moment tail risk audit",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- candidate_like: `{decision['candidate_like']}`",
        f"- tail ready lots: `{decision['tail_ready_lot_count']}/{decision['input_lot_count']}`",
        f"- target bucket: `{TARGET_BUCKET}`",
        f"- target lots: `{decision['target_lot_count']}`",
        f"- target realized PnL: `{decision['target_realized_pnl']:.2f}`",
        f"- upper-bound return retention: `{decision['upper_bound_return_retention_pct']:.4f}%`",
        f"- upper-bound max DD: `{decision['upper_bound_metrics']['max_dd_pct']:.4f}%`",
        "",
        "## Bucket Summary",
        "",
        _md_table(
            bucket_summary[
                [
                    "stage059_tail_bucket",
                    "lot_count",
                    "product_count",
                    "year_count",
                    "net_pnl",
                    "positive_lot_count",
                    "negative_lot_count",
                    "median_tail_score",
                ]
            ]
        ),
        "",
        "## Tail Score Quartiles",
        "",
        _md_table(
            quartile_summary[
                [
                    "tail_score_quartile",
                    "lot_count",
                    "product_count",
                    "year_count",
                    "net_pnl",
                    "positive_lot_count",
                    "negative_lot_count",
                    "median_tail_score",
                ]
            ],
            20,
        ),
        "",
        "## Bucket-Year PnL",
        "",
        _md_table(bucket_year[["stage059_tail_bucket", "exit_year", "lot_count", "realized_pnl"]], 30),
        "",
        "## Product-Bucket PnL",
        "",
        _md_table(
            product_bucket.reindex(product_bucket["realized_pnl"].abs().sort_values(ascending=False).index)[
                ["stage059_product_key", "stage059_tail_bucket", "lot_count", "realized_pnl"]
            ],
            30,
        ),
        "",
        "## Visual Outputs",
        "",
        f"- path chart: `{PATH_CHART_OUT}`",
        f"- contribution chart: `{CONTRIBUTION_CHART_OUT}`",
        f"- bucket-year heatmap: `{BUCKET_YEAR_HEATMAP_OUT}`",
        f"- product-bucket heatmap: `{PRODUCT_BUCKET_HEATMAP_OUT}`",
        f"- tail score scatter: `{SCATTER_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features, product_daily, curve, stage052_decision = _load_inputs()
    pm_daily = _build_partial_moment_daily(product_daily)
    bound = _bind_features(features, pm_daily)

    bucket_summary = _group_summary(bound, ["stage059_tail_bucket"])
    quartile_summary = _quartile_summary(bound)
    bucket_year = (
        bound.groupby(["stage059_tail_bucket", "exit_year"], dropna=False)
        .agg(lot_count=("lot_id", "count"), realized_pnl=("realized_pnl", "sum"))
        .reset_index()
        .sort_values(["stage059_tail_bucket", "exit_year"])
    )
    product_bucket = (
        bound.groupby(["stage059_product_key", "stage059_tail_bucket"], dropna=False)
        .agg(lot_count=("lot_id", "count"), realized_pnl=("realized_pnl", "sum"))
        .reset_index()
    )
    upper_curve = _upper_bound_curve(curve, bound)
    contrib = _contribution_curve(bound, curve)

    _plot_path(upper_curve)
    _plot_contribution(contrib)
    _plot_bucket_year(bucket_year)
    _plot_product_bucket(product_bucket)
    _plot_scatter(bound)

    pm_daily.to_csv(PARTIAL_MOMENT_DAILY_OUT, index=False, encoding="utf-8-sig")
    bound.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_year.to_csv(BUCKET_YEAR_OUT, index=False, encoding="utf-8-sig")
    product_bucket.to_csv(PRODUCT_BUCKET_OUT, index=False, encoding="utf-8-sig")
    quartile_summary.to_csv(QUARTILE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bound[bound["stage059_tail_bucket"].eq(TARGET_BUCKET)].to_csv(TARGET_LOTS_OUT, index=False, encoding="utf-8-sig")
    upper_curve.to_csv(UPPER_BOUND_CURVE_OUT, index=False, encoding="utf-8-sig")

    official_metrics = _performance_from_curve(upper_curve, "account_equity", "official_drawdown_pct_recalc")
    upper_metrics = _performance_from_curve(upper_curve, "upper_bound_skip_target_equity", "upper_bound_drawdown_pct")
    target = bound[bound["stage059_tail_bucket"].eq(TARGET_BUCKET)].copy()
    target_pnl = float(target["realized_pnl"].sum())
    return_retention = (
        upper_metrics["total_return_pct"] / official_metrics["total_return_pct"] * 100.0
        if official_metrics["total_return_pct"] and np.isfinite(official_metrics["total_return_pct"])
        else np.nan
    )
    summary = pd.DataFrame(
        [
            {
                "metric": "official",
                **official_metrics,
            },
            {
                "metric": "skip_adverse_tail_dominant_diagnostic",
                **upper_metrics,
            },
        ]
    )
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "stage059_partial_moment_tail_risk_no_candidate_right_tail_dominant",
        "candidate_like": False,
        "window": WINDOW,
        "min_periods": MIN_PERIODS,
        "input_lot_count": int(len(bound)),
        "tail_ready_lot_count": int(bound["stage059_tail_ready"].astype(bool).sum()),
        "target_bucket": TARGET_BUCKET,
        "target_lot_count": int(len(target)),
        "target_realized_pnl": target_pnl,
        "target_product_count": int(target["stage059_product_key"].nunique()),
        "target_year_count": int(target["entry_year"].nunique()),
        "official_metrics": official_metrics,
        "upper_bound_metrics": upper_metrics,
        "upper_bound_return_retention_pct": return_retention,
        "bucket_pnl": {
            str(row["stage059_tail_bucket"]): float(row["net_pnl"])
            for _, row in bucket_summary[["stage059_tail_bucket", "net_pnl"]].iterrows()
        },
        "stage052_upstream_decision": stage052_decision.get("decision"),
        "judgment": (
            "The natural partial-moment adverse-tail bucket is not a bad-quality cohort in current C9/15w. "
            "It carries a large positive right-tail contribution, so partial-moment tail asymmetry should not "
            "be promoted as a risk-cut rule without a new independent information source or forward evidence."
        ),
        "outputs": {
            "partial_moment_daily": PARTIAL_MOMENT_DAILY_OUT,
            "features": FEATURES_OUT,
            "bucket_summary": BUCKET_SUMMARY_OUT,
            "bucket_year": BUCKET_YEAR_OUT,
            "product_bucket": PRODUCT_BUCKET_OUT,
            "quartile_summary": QUARTILE_SUMMARY_OUT,
            "target_lots": TARGET_LOTS_OUT,
            "upper_bound_curve": UPPER_BOUND_CURVE_OUT,
            "summary": SUMMARY_OUT,
            "path_chart": PATH_CHART_OUT,
            "contribution_chart": CONTRIBUTION_CHART_OUT,
            "bucket_year_heatmap": BUCKET_YEAR_HEATMAP_OUT,
            "product_bucket_heatmap": PRODUCT_BUCKET_HEATMAP_OUT,
            "scatter": SCATTER_OUT,
            "report": REPORT_OUT,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, bucket_summary, quartile_summary, bucket_year, product_bucket)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

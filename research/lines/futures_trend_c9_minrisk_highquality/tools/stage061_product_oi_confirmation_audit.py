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


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage061"
MODEL_TAG = "stage061_product_oi_confirmation_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage061_c9_minrisk_product_oi_confirmation_audit"

INITIAL_CAPITAL = 150_000.0
WINDOW = 63
MAX_SIGNAL_AGE_DAYS = 7
TARGET_BUCKET = "price_aligned_oi_contracting"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
BACKTEST_OUTPUT_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"
STAGE060_DIR = LINE_DIR / "outputs" / "stage060_relative_basis_shock_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage061_product_oi_confirmation_audit"

FEATURES_IN = (
    STAGE060_DIR
    / "qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_features_"
    "stage060_relative_basis_shock_audit_v1.csv"
)
CURVE_IN = (
    STAGE060_DIR
    / "qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit_upper_bound_curve_"
    "stage060_relative_basis_shock_audit_v1.csv"
)
STAGE496_SYNTHETIC_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage496_all_required_preclose_full_bar_after_all_backfill_synthetic_"
    "stage496_all_required_preclose_full_bar_after_all_backfill_v1.csv"
)

PRODUCT_OI_DAILY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_oi_daily_{MODEL_TAG}.csv"
FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
BUCKET_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
PRODUCT_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_matrix_{MODEL_TAG}.csv"
COVERAGE_BY_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_year_{MODEL_TAG}.csv"
UPPER_BOUND_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_path_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_contribution_chart_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
PRODUCT_BUCKET_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_oi_confirmation_scatter_{MODEL_TAG}.png"

BUCKET_COLORS = {
    "price_aligned_oi_expanding": "#2ca02c",
    "price_aligned_oi_contracting": "#d62728",
    "price_not_aligned": "#ff7f0e",
    "oi_confirm_missing": "#7f7f7f",
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
        out = float(value)
        return None if np.isnan(out) or np.isinf(out) else out
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


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


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    features = _read_csv(FEATURES_IN)
    curve = _read_csv(CURVE_IN)

    for column in ["entry_date", "exit_date", "exit_day", "prev_state_date"]:
        if column in features.columns:
            features[column] = pd.to_datetime(features[column], errors="coerce")
    for column in [
        "realized_pnl",
        "entry_year",
        "exit_year",
        "first_30m_directional_r",
        "mae_r",
        "mfe_r",
        "direction_aligned_trend_tstat_252_stage052",
    ]:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")

    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        if column in curve.columns:
            curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return features, curve


def _normal_product_key(features: pd.DataFrame) -> pd.Series:
    normalized = features.get("normalized_product", pd.Series(index=features.index, dtype=object)).fillna("").astype(str)
    product_key = features.get("product_key", pd.Series(index=features.index, dtype=object)).fillna("").astype(str)
    product = features.get("product", pd.Series(index=features.index, dtype=object)).fillna("").astype(str)
    vt_symbol = features.get("vt_symbol", pd.Series(index=features.index, dtype=object)).fillna("").astype(str)
    exchange = features.get("exchange", pd.Series(index=features.index, dtype=object)).fillna("").astype(str)

    raw = normalized.where(normalized.str.contains(".", regex=False), "")
    raw = raw.where(raw.ne(""), product_key.where(product_key.str.contains(".", regex=False), ""))
    raw = raw.where(raw.ne(""), product.where(product.str.contains(".", regex=False), ""))
    derived_code = vt_symbol.str.extract(r"^([A-Za-z]+)", expand=False).fillna("")
    raw = raw.where(raw.ne(""), derived_code + "." + exchange)
    raw = raw.str.strip()
    code = raw.str.split(".", n=1).str[0]
    exch = raw.str.split(".", n=1).str[1].where(raw.str.contains(".", regex=False), exchange).fillna("")
    code = np.where(exch.eq("CZCE"), code.str.upper(), code.str.lower())
    return pd.Series(code, index=features.index).astype(str) + "." + exch.astype(str)


def _build_product_oi_daily() -> pd.DataFrame:
    columns = [
        "date",
        "product_vt_symbol",
        "vt_symbol",
        "exchange",
        "strict_full_preclose_ready",
        "synthetic_close",
        "synthetic_volume",
        "synthetic_open_interest",
        "preclose_bar_count",
        "fill_bar_count",
    ]
    bars = _read_csv(STAGE496_SYNTHETIC_IN, usecols=lambda column: column in columns)
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce")
    for column in [
        "strict_full_preclose_ready",
        "synthetic_close",
        "synthetic_volume",
        "synthetic_open_interest",
        "preclose_bar_count",
        "fill_bar_count",
    ]:
        bars[column] = pd.to_numeric(bars.get(column, np.nan), errors="coerce")
    bars["product_key"] = bars["product_vt_symbol"].fillna("").astype(str).str.strip()
    bars = bars[
        bars["date"].notna()
        & bars["product_key"].ne("")
        & bars["strict_full_preclose_ready"].fillna(0.0).gt(0.0)
        & bars["synthetic_close"].notna()
        & bars["synthetic_close"].gt(0.0)
        & bars["synthetic_open_interest"].notna()
        & bars["synthetic_open_interest"].gt(0.0)
    ].copy()
    bars = bars.sort_values(
        ["product_key", "date", "synthetic_volume", "synthetic_open_interest"],
        ascending=[True, True, False, False],
    )
    bars = bars.drop_duplicates(["product_key", "date"], keep="first")

    rows: list[pd.DataFrame] = []
    for _, group in bars.groupby("product_key", sort=True):
        item = group.sort_values("date").copy()
        item["price_log_change_63"] = np.log(item["synthetic_close"].astype(float)).diff(WINDOW)
        item["oi_log_change_63"] = np.log(item["synthetic_open_interest"].astype(float)).diff(WINDOW)
        item["volume_log_change_63"] = np.log(item["synthetic_volume"].replace(0.0, np.nan).astype(float)).diff(WINDOW)
        item["stage061_oi_ready_daily"] = item["price_log_change_63"].notna() & item["oi_log_change_63"].notna()
        rows.append(
            item[
                [
                    "date",
                    "product_key",
                    "vt_symbol",
                    "exchange",
                    "synthetic_close",
                    "synthetic_volume",
                    "synthetic_open_interest",
                    "preclose_bar_count",
                    "fill_bar_count",
                    "price_log_change_63",
                    "oi_log_change_63",
                    "volume_log_change_63",
                    "stage061_oi_ready_daily",
                ]
            ].copy()
        )
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    out.to_csv(PRODUCT_OI_DAILY_OUT, index=False, encoding="utf-8-sig")
    return out


def _bind_features(features: pd.DataFrame, oi_daily: pd.DataFrame) -> pd.DataFrame:
    features = features.copy()
    features["stage061_product_key"] = _normal_product_key(features)
    features["stage061_direction_sign"] = np.where(
        features["direction"].fillna("").astype(str).str.lower().eq("short"),
        -1.0,
        1.0,
    )
    features["_stage061_order"] = np.arange(len(features), dtype=int)
    bound: list[pd.DataFrame] = []
    right_columns = [
        "date",
        "synthetic_close",
        "synthetic_volume",
        "synthetic_open_interest",
        "price_log_change_63",
        "oi_log_change_63",
        "volume_log_change_63",
        "stage061_oi_ready_daily",
    ]
    for product, group in features.groupby("stage061_product_key", dropna=False):
        left = group.sort_values("prev_state_date").copy()
        right = oi_daily[oi_daily["product_key"].eq(product)].sort_values("date").copy()
        if right.empty:
            item = left.copy()
            for column in [
                "stage061_source_date",
                "stage061_signal_age_days",
                "stage061_synthetic_close",
                "stage061_synthetic_volume",
                "stage061_synthetic_open_interest",
                "stage061_price_log_change_63",
                "stage061_oi_log_change_63",
                "stage061_volume_log_change_63",
                "stage061_directional_price_change_63",
            ]:
                item[column] = np.nan
            item["stage061_oi_ready"] = False
            item["stage061_oi_bucket"] = "oi_confirm_missing"
            bound.append(item)
            continue
        merged = pd.merge_asof(
            left,
            right[right_columns],
            left_on="prev_state_date",
            right_on="date",
            direction="backward",
            tolerance=pd.Timedelta(days=MAX_SIGNAL_AGE_DAYS),
        )
        source_date_col = "date_y" if "date_y" in merged.columns else "date"
        merged["stage061_source_date"] = merged[source_date_col]
        merged["stage061_signal_age_days"] = (merged["prev_state_date"] - merged["stage061_source_date"]).dt.days
        merged["stage061_synthetic_close"] = merged["synthetic_close"]
        merged["stage061_synthetic_volume"] = merged["synthetic_volume"]
        merged["stage061_synthetic_open_interest"] = merged["synthetic_open_interest"]
        merged["stage061_price_log_change_63"] = merged["price_log_change_63"]
        merged["stage061_oi_log_change_63"] = merged["oi_log_change_63"]
        merged["stage061_volume_log_change_63"] = merged["volume_log_change_63"]
        merged["stage061_oi_ready"] = merged["stage061_oi_ready_daily"].map(
            lambda value: bool(value) if pd.notna(value) else False
        )
        merged["stage061_directional_price_change_63"] = (
            merged["stage061_direction_sign"] * merged["stage061_price_log_change_63"]
        )
        merged["stage061_oi_bucket"] = "oi_confirm_missing"
        ready = (
            merged["stage061_oi_ready"]
            & merged["stage061_directional_price_change_63"].notna()
            & merged["stage061_oi_log_change_63"].notna()
        )
        aligned = ready & merged["stage061_directional_price_change_63"].gt(0.0)
        merged.loc[aligned & merged["stage061_oi_log_change_63"].gt(0.0), "stage061_oi_bucket"] = (
            "price_aligned_oi_expanding"
        )
        merged.loc[aligned & merged["stage061_oi_log_change_63"].le(0.0), "stage061_oi_bucket"] = (
            "price_aligned_oi_contracting"
        )
        merged.loc[ready & ~aligned, "stage061_oi_bucket"] = "price_not_aligned"
        bound.append(merged)

    concat_frames = [frame.dropna(axis=1, how="all") for frame in bound if not frame.empty]
    out = pd.concat(concat_frames, ignore_index=True, sort=False).sort_values("_stage061_order")
    return out.drop(columns=["_stage061_order"])


def _group_summary(data: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (
        data.groupby(keys, dropna=False)
        .agg(
            lot_count=("lot_id", "count"),
            raw_product_count=("product_key", "nunique"),
            product_count=("stage061_product_key", "nunique"),
            year_count=("entry_year", "nunique"),
            net_pnl=("realized_pnl", "sum"),
            positive_pnl=("realized_pnl", lambda item: item[item > 0].sum()),
            negative_pnl_abs=("realized_pnl", lambda item: -item[item < 0].sum()),
            positive_lot_count=("realized_pnl", lambda item: int((item > 0).sum())),
            negative_lot_count=("realized_pnl", lambda item: int((item < 0).sum())),
            median_directional_price_change_63=("stage061_directional_price_change_63", "median"),
            median_oi_log_change_63=("stage061_oi_log_change_63", "median"),
            median_first_30m_directional_r=("first_30m_directional_r", "median"),
        )
        .reset_index()
        .sort_values(["net_pnl", "lot_count"], ascending=[False, False])
    )


def _bucket_year(features: pd.DataFrame) -> pd.DataFrame:
    return (
        features.groupby(["stage061_oi_bucket", "exit_year"], dropna=False)
        .agg(lot_count=("lot_id", "count"), realized_pnl=("realized_pnl", "sum"))
        .reset_index()
        .sort_values(["stage061_oi_bucket", "exit_year"])
    )


def _product_bucket(features: pd.DataFrame) -> pd.DataFrame:
    return (
        features.groupby(["stage061_product_key", "stage061_oi_bucket"], dropna=False)
        .agg(lot_count=("lot_id", "count"), realized_pnl=("realized_pnl", "sum"))
        .reset_index()
        .sort_values("realized_pnl", ascending=False)
    )


def _coverage_by_year(features: pd.DataFrame) -> pd.DataFrame:
    out = (
        features.assign(ready=features["stage061_oi_ready"].astype(bool))
        .groupby("entry_year", dropna=False)
        .agg(
            lot_count=("lot_id", "count"),
            ready_count=("ready", "sum"),
            net_pnl=("realized_pnl", "sum"),
            ready_pnl=(
                "realized_pnl",
                lambda item: item[features.loc[item.index, "stage061_oi_ready"].astype(bool)].sum(),
            ),
        )
        .reset_index()
    )
    out["ready_rate_pct"] = out["ready_count"] / out["lot_count"] * 100.0
    return out.sort_values("entry_year")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    equity = pd.to_numeric(equity, errors="coerce")
    return (equity / equity.cummax() - 1.0) * 100.0


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


def _upper_bound_curve(curve: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    events = features.copy()
    events["exit_day_norm"] = pd.to_datetime(events["exit_day"], errors="coerce").dt.normalize()
    events["target_realized_pnl"] = np.where(
        events["stage061_oi_bucket"].eq(TARGET_BUCKET),
        events["realized_pnl"],
        0.0,
    )
    events["target_lot_count"] = np.where(events["stage061_oi_bucket"].eq(TARGET_BUCKET), 1, 0)
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
    return out


def _contribution_curve(features: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    data = features.copy()
    data["exit_day_norm"] = pd.to_datetime(data["exit_day"], errors="coerce").dt.normalize()
    for bucket in BUCKET_COLORS:
        data[f"pnl_{bucket}"] = np.where(data["stage061_oi_bucket"].eq(bucket), data["realized_pnl"], 0.0)
    daily_columns = [f"pnl_{bucket}" for bucket in BUCKET_COLORS]
    daily = data.groupby("exit_day_norm", dropna=False)[daily_columns].sum().reset_index().rename(
        columns={"exit_day_norm": "date"}
    )
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
        label="diagnostic skip price-aligned / OI-contracting equity",
    )
    axes[0].set_yscale("log")
    axes[0].set_title("Stage061 product OI confirmation upper-bound diagnostic")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")

    axes[1].plot(curve["date"], curve["skipped_target_pnl_cumsum"], lw=1.3, color="#d62728", label="cum skipped target PnL")
    axes[1].axhline(0, color="#555555", lw=0.8)
    axes[1].set_ylabel("PnL")
    axes[1].legend(loc="upper left")

    axes[2].plot(curve["date"], curve["official_drawdown_pct_recalc"], color="#8c564b", lw=1.1, label="official DD %")
    axes[2].plot(curve["date"], curve["upper_bound_drawdown_pct"], color="#d62728", lw=1.1, label="skip-target DD %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#9467bd", lw=0.9, alpha=0.75, label="broker10 %")
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
        axes[0].plot(contrib["date"], contrib[f"cum_pnl_{bucket}"], lw=1.3, color=color, label=bucket)
    axes[0].axhline(0, color="#555555", lw=0.8)
    axes[0].set_title("Stage061 cumulative PnL by price/OI bucket")
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


def _plot_coverage(coverage: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    x = coverage["entry_year"].astype(int).astype(str)
    axes[0].bar(x, coverage["lot_count"], color="#dddddd", label="lots")
    axes[0].bar(x, coverage["ready_count"], color="#1f77b4", label="OI-ready")
    axes[0].set_ylabel("lot count")
    axes[0].set_title("Stage061 OI confirmation coverage by entry year")
    axes[0].legend(loc="upper left")
    axes[1].plot(x, coverage["ready_rate_pct"], marker="o", color="#1f77b4", label="ready rate %")
    axes[1].axhline(80, color="#777777", ls="--", lw=0.8)
    axes[1].set_ylabel("ready rate %")
    axes[1].legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(COVERAGE_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_bucket_year(bucket_year: pd.DataFrame) -> None:
    pivot = bucket_year.pivot_table(
        index="stage061_oi_bucket",
        columns="exit_year",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
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
    ax.set_title("Stage061 bucket-year realized PnL")
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
    product_totals = product_bucket.groupby("stage061_product_key")["realized_pnl"].sum().abs().sort_values(ascending=False)
    top_products = product_totals.head(18).index.tolist()
    temp = product_bucket[product_bucket["stage061_product_key"].isin(top_products)].copy()
    pivot = temp.pivot_table(
        index="stage061_product_key",
        columns="stage061_oi_bucket",
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
    ax.set_title("Stage061 product-bucket realized PnL")
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
        ("stage061_directional_price_change_63", "stage061_oi_log_change_63", "directional price change vs OI change"),
        ("stage061_oi_log_change_63", "realized_pnl", "OI change vs PnL"),
        ("stage061_oi_log_change_63", "first_30m_directional_r", "OI change vs first 30m R"),
        ("stage061_oi_log_change_63", "direction_aligned_trend_tstat_252_stage052", "OI change vs trend t-stat"),
    ]
    max_abs_pnl = max(float(features["realized_pnl"].abs().max()), 1.0)
    for ax, (x_col, y_col, title) in zip(axes.ravel(), specs):
        for bucket, group in features.groupby("stage061_oi_bucket"):
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
        fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(SCATTER_OUT, dpi=150)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    bucket_summary: pd.DataFrame,
    bucket_year: pd.DataFrame,
    product_bucket: pd.DataFrame,
    coverage: pd.DataFrame,
) -> None:
    lines = [
        "# Stage061 product OI confirmation audit",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- candidate_like: `{decision['candidate_like']}`",
        f"- OI-ready lots: `{decision['oi_ready_lot_count']}/{decision['input_lot_count']}`",
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
                    "stage061_oi_bucket",
                    "lot_count",
                    "product_count",
                    "raw_product_count",
                    "year_count",
                    "net_pnl",
                    "positive_lot_count",
                    "negative_lot_count",
                    "median_directional_price_change_63",
                    "median_oi_log_change_63",
                ]
            ]
        ),
        "",
        "## Coverage By Entry Year",
        "",
        _md_table(coverage, 20),
        "",
        "## Bucket-Year PnL",
        "",
        _md_table(bucket_year[["stage061_oi_bucket", "exit_year", "lot_count", "realized_pnl"]], 40),
        "",
        "## Product-Bucket PnL",
        "",
        _md_table(
            product_bucket.reindex(product_bucket["realized_pnl"].abs().sort_values(ascending=False).index)[
                ["stage061_product_key", "stage061_oi_bucket", "lot_count", "realized_pnl"]
            ],
            40,
        ),
        "",
        "## Visual Outputs",
        "",
        f"- path chart: `{PATH_CHART_OUT}`",
        f"- contribution chart: `{CONTRIBUTION_CHART_OUT}`",
        f"- coverage chart: `{COVERAGE_CHART_OUT}`",
        f"- bucket-year heatmap: `{BUCKET_YEAR_HEATMAP_OUT}`",
        f"- product-bucket heatmap: `{PRODUCT_BUCKET_HEATMAP_OUT}`",
        f"- OI confirmation scatter: `{SCATTER_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features, curve = _load_inputs()
    oi_daily = _build_product_oi_daily()
    bound = _bind_features(features, oi_daily)

    bucket_summary = _group_summary(bound, ["stage061_oi_bucket"])
    bucket_year = _bucket_year(bound)
    product_bucket = _product_bucket(bound)
    coverage = _coverage_by_year(bound)
    upper_curve = _upper_bound_curve(curve, bound)
    contribution = _contribution_curve(bound, curve)

    official_metrics = _performance_from_curve(upper_curve, "account_equity", "official_drawdown_pct_recalc")
    upper_metrics = _performance_from_curve(upper_curve, "upper_bound_skip_target_equity", "upper_bound_drawdown_pct")
    official_return = official_metrics["total_return_pct"]
    upper_return = upper_metrics["total_return_pct"]
    retention = upper_return / official_return * 100.0 if official_return else np.nan

    ready = bound["stage061_oi_ready"].astype(bool)
    target = bound[bound["stage061_oi_bucket"].eq(TARGET_BUCKET)].copy()
    missing = bound[bound["stage061_oi_bucket"].eq("oi_confirm_missing")].copy()

    decision_name = "stage061_product_oi_contracting_no_candidate_right_tail_dominant"
    candidate_like = False
    if (
        len(target) >= 30
        and float(target["realized_pnl"].sum()) < 0.0
        and retention >= 80.0
        and upper_metrics["max_dd_pct"] > official_metrics["max_dd_pct"]
    ):
        decision_name = "stage061_product_oi_contracting_watch_requires_true_engine"
        candidate_like = True

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_name,
        "candidate_like": candidate_like,
        "oi_confirmation_spec": {
            "window_rows": WINDOW,
            "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
            "directional_price_change_63": "direction_sign * log(close_t / close_t-63)",
            "oi_log_change_63": "log(open_interest_t / open_interest_t-63)",
            "target_bucket": TARGET_BUCKET,
            "bucket_rule": "directional price > 0 and OI change <= 0",
            "source": STAGE496_SYNTHETIC_IN,
        },
        "input_lot_count": int(len(bound)),
        "oi_daily_row_count": int(len(oi_daily)),
        "oi_product_count": int(oi_daily["product_key"].nunique()) if not oi_daily.empty else 0,
        "oi_first_date": oi_daily["date"].min() if not oi_daily.empty else None,
        "oi_last_date": oi_daily["date"].max() if not oi_daily.empty else None,
        "oi_ready_lot_count": int(ready.sum()),
        "oi_ready_rate_pct": float(ready.mean() * 100.0),
        "target_bucket": TARGET_BUCKET,
        "target_lot_count": int(len(target)),
        "target_realized_pnl": float(target["realized_pnl"].sum()),
        "target_product_count": int(target["stage061_product_key"].nunique()),
        "target_year_count": int(target["entry_year"].nunique()),
        "missing_lot_count": int(len(missing)),
        "missing_realized_pnl": float(missing["realized_pnl"].sum()),
        "official_metrics": official_metrics,
        "upper_bound_metrics": upper_metrics,
        "upper_bound_return_retention_pct": float(retention),
        "bucket_pnl": {str(row["stage061_oi_bucket"]): float(row["net_pnl"]) for _, row in bucket_summary.iterrows()},
        "judgment": (
            "The fixed OI-confirmation bucket is only a diagnostic upper bound. If price is already aligned but "
            "open interest contracts, the intuitive concern is a liquidation or short-covering move rather than "
            "fresh participation. The test must still reject the bucket if it carries official C9 right-tail PnL."
        ),
        "outputs": {
            "product_oi_daily": PRODUCT_OI_DAILY_OUT,
            "features": FEATURES_OUT,
            "bucket_summary": BUCKET_SUMMARY_OUT,
            "bucket_year": BUCKET_YEAR_OUT,
            "product_bucket": PRODUCT_BUCKET_OUT,
            "coverage_by_year": COVERAGE_BY_YEAR_OUT,
            "upper_bound_curve": UPPER_BOUND_CURVE_OUT,
            "summary": SUMMARY_OUT,
            "decision": DECISION_OUT,
            "path_chart": PATH_CHART_OUT,
            "contribution_chart": CONTRIBUTION_CHART_OUT,
            "coverage_chart": COVERAGE_CHART_OUT,
            "bucket_year_heatmap": BUCKET_YEAR_HEATMAP_OUT,
            "product_bucket_heatmap": PRODUCT_BUCKET_HEATMAP_OUT,
            "scatter": SCATTER_OUT,
            "report": REPORT_OUT,
        },
    }

    bound.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_year.to_csv(BUCKET_YEAR_OUT, index=False, encoding="utf-8-sig")
    product_bucket.to_csv(PRODUCT_BUCKET_OUT, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_BY_YEAR_OUT, index=False, encoding="utf-8-sig")
    upper_curve.to_csv(UPPER_BOUND_CURVE_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {"metric": "official", **official_metrics},
            {"metric": f"skip_{TARGET_BUCKET}_diagnostic", **upper_metrics},
        ]
    ).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    with DECISION_OUT.open("w", encoding="utf-8") as handle:
        json.dump(_json_safe(decision), handle, ensure_ascii=False, indent=2)

    _plot_path(upper_curve)
    _plot_contribution(contribution)
    _plot_coverage(coverage)
    _plot_bucket_year(bucket_year)
    _plot_product_bucket(product_bucket)
    _plot_scatter(bound)
    _write_report(decision, bucket_summary, bucket_year, product_bucket, coverage)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

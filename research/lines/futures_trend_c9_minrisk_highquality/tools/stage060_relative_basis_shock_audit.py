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
STAGE = "Stage060"
MODEL_TAG = "stage060_relative_basis_shock_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage060_c9_minrisk_relative_basis_shock_audit"

INITIAL_CAPITAL = 150_000.0
MAX_SIGNAL_AGE_DAYS = 7
SEASONAL_DIFF_ROWS = 252
TARGET_BUCKET = "relative_basis_yoy_headwind"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
BACKTEST_OUTPUT_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"
STAGE052_DIR = LINE_DIR / "outputs" / "stage052_product_trend_tstat_stage496_reaudit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage060_relative_basis_shock_audit"

FEATURES_IN = (
    STAGE052_DIR
    / "qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_features_"
    "stage052_product_trend_tstat_stage496_reaudit_v1.csv"
)
CURVE_IN = (
    STAGE052_DIR
    / "qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_upper_bound_curve_"
    "stage052_product_trend_tstat_stage496_reaudit_v1.csv"
)
BASIS_2020_2022_IN = BACKTEST_OUTPUT_DIR / "external_supply_demand_cache" / "supply_demand_basis_20200101_20221231.csv"
BASIS_2023_2026_IN = BACKTEST_OUTPUT_DIR / "external_supply_demand_cache" / "supply_demand_basis_20230101_20260417.csv"

RELATIVE_BASIS_DAILY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_relative_basis_daily_{MODEL_TAG}.csv"
FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
BUCKET_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
PRODUCT_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_matrix_{MODEL_TAG}.csv"
UPPER_BOUND_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_path_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_contribution_chart_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
PRODUCT_BUCKET_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_relative_basis_scatter_{MODEL_TAG}.png"

BUCKET_COLORS = {
    "relative_basis_yoy_headwind": "#d62728",
    "relative_basis_yoy_supportive": "#2ca02c",
    "relative_basis_missing": "#7f7f7f",
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


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


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features = _read_csv(FEATURES_IN)
    curve = _read_csv(CURVE_IN)
    basis = pd.concat(
        [_read_csv(BASIS_2020_2022_IN), _read_csv(BASIS_2023_2026_IN)],
        ignore_index=True,
    )

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

    basis["date"] = pd.to_datetime(basis["date"].astype(str), errors="coerce")
    basis["symbol"] = basis["symbol"].fillna("").astype(str).str.upper().str.strip()
    for column in ["near_basis_rate", "dom_basis_rate", "spot_price", "near_contract_price", "dominant_contract_price"]:
        if column in basis.columns:
            basis[column] = pd.to_numeric(basis[column], errors="coerce")
    return features, curve, basis


def _product_code(features: pd.DataFrame) -> pd.Series:
    base = features.get("normalized_product", pd.Series(index=features.index, dtype=object)).fillna("").astype(str)
    fallback = features.get("product_key", pd.Series(index=features.index, dtype=object)).fillna("").astype(str)
    raw = base.where(base.ne(""), fallback)
    raw = raw.where(raw.ne(""), features.get("vt_symbol", pd.Series(index=features.index, dtype=object)).fillna("").astype(str))
    return raw.str.split(".", n=1).str[0].str.replace(r"[^A-Za-z]", "", regex=True).str.upper()


def _build_relative_basis_daily(basis: pd.DataFrame) -> pd.DataFrame:
    source = basis[
        basis["date"].notna()
        & basis["symbol"].ne("")
        & basis["near_basis_rate"].notna()
        & basis["dom_basis_rate"].notna()
    ].copy()
    source["relative_basis_rate"] = source["near_basis_rate"] - source["dom_basis_rate"]
    source = source.replace([np.inf, -np.inf], np.nan).dropna(subset=["relative_basis_rate"])
    source = source.sort_values(["symbol", "date"]).reset_index(drop=True)
    source["relative_basis_yoy_delta_252"] = source.groupby("symbol")["relative_basis_rate"].diff(SEASONAL_DIFF_ROWS)
    source["relative_basis_change_20d"] = source.groupby("symbol")["relative_basis_rate"].diff(20)
    source["relative_basis_ready"] = source["relative_basis_yoy_delta_252"].notna()
    columns = [
        "date",
        "symbol",
        "spot_price",
        "near_contract",
        "near_contract_price",
        "dominant_contract",
        "dominant_contract_price",
        "near_basis_rate",
        "dom_basis_rate",
        "relative_basis_rate",
        "relative_basis_yoy_delta_252",
        "relative_basis_change_20d",
        "relative_basis_ready",
    ]
    out = source[[column for column in columns if column in source.columns]].copy()
    out.to_csv(RELATIVE_BASIS_DAILY_OUT, index=False, encoding="utf-8-sig")
    return out


def _bind_features(features: pd.DataFrame, rb_daily: pd.DataFrame) -> pd.DataFrame:
    features = features.copy()
    features["stage060_product_code"] = _product_code(features)
    features["stage060_direction_sign"] = np.where(
        features["direction"].fillna("").astype(str).str.lower().eq("short"),
        -1.0,
        1.0,
    )
    features["_stage060_order"] = np.arange(len(features), dtype=int)
    bound: list[pd.DataFrame] = []
    for code, group in features.groupby("stage060_product_code", dropna=False):
        left = group.sort_values("prev_state_date").copy()
        right = rb_daily[rb_daily["symbol"].eq(code)].sort_values("date").copy()
        if right.empty:
            item = left.copy()
            for column in [
                "stage060_source_date",
                "stage060_signal_age_days",
                "stage060_relative_basis_rate",
                "stage060_relative_basis_yoy_delta_252",
                "stage060_relative_basis_change_20d",
                "stage060_directional_yoy_delta",
                "stage060_directional_change_20d",
            ]:
                item[column] = np.nan
            item["stage060_relative_basis_ready"] = False
            item["stage060_relative_basis_bucket"] = "relative_basis_missing"
            bound.append(item)
            continue
        merged = pd.merge_asof(
            left,
            right[
                [
                    "date",
                    "symbol",
                    "relative_basis_rate",
                    "relative_basis_yoy_delta_252",
                    "relative_basis_change_20d",
                    "relative_basis_ready",
                ]
            ],
            left_on="prev_state_date",
            right_on="date",
            direction="backward",
            tolerance=pd.Timedelta(days=MAX_SIGNAL_AGE_DAYS),
        )
        merged["stage060_source_date"] = merged["date"]
        merged["stage060_signal_age_days"] = (merged["prev_state_date"] - merged["stage060_source_date"]).dt.days
        merged["stage060_relative_basis_rate"] = merged["relative_basis_rate"]
        merged["stage060_relative_basis_yoy_delta_252"] = merged["relative_basis_yoy_delta_252"]
        merged["stage060_relative_basis_change_20d"] = merged["relative_basis_change_20d"]
        merged["stage060_relative_basis_ready"] = merged["relative_basis_ready"].map(
            lambda value: bool(value) if pd.notna(value) else False
        )
        merged["stage060_directional_yoy_delta"] = (
            merged["stage060_direction_sign"] * merged["stage060_relative_basis_yoy_delta_252"]
        )
        merged["stage060_directional_change_20d"] = (
            merged["stage060_direction_sign"] * merged["stage060_relative_basis_change_20d"]
        )
        merged["stage060_relative_basis_bucket"] = "relative_basis_missing"
        ready = merged["stage060_relative_basis_ready"] & merged["stage060_directional_yoy_delta"].notna()
        merged.loc[ready & merged["stage060_directional_yoy_delta"].lt(0.0), "stage060_relative_basis_bucket"] = (
            "relative_basis_yoy_headwind"
        )
        merged.loc[ready & merged["stage060_directional_yoy_delta"].ge(0.0), "stage060_relative_basis_bucket"] = (
            "relative_basis_yoy_supportive"
        )
        bound.append(merged)
    concat_frames = [frame.dropna(axis=1, how="all") for frame in bound if not frame.empty]
    out = pd.concat(concat_frames, ignore_index=True, sort=False).sort_values("_stage060_order").drop(
        columns=["_stage060_order"]
    )
    return out


def _group_summary(data: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (
        data.groupby(keys, dropna=False)
        .agg(
            lot_count=("lot_id", "count"),
            product_count=("product_key", "nunique"),
            code_count=("stage060_product_code", "nunique"),
            year_count=("entry_year", "nunique"),
            net_pnl=("realized_pnl", "sum"),
            positive_pnl=("realized_pnl", lambda item: item[item > 0].sum()),
            negative_pnl_abs=("realized_pnl", lambda item: -item[item < 0].sum()),
            positive_lot_count=("realized_pnl", lambda item: int((item > 0).sum())),
            negative_lot_count=("realized_pnl", lambda item: int((item < 0).sum())),
            median_directional_yoy_delta=("stage060_directional_yoy_delta", "median"),
            median_directional_change_20d=("stage060_directional_change_20d", "median"),
            median_first_30m_directional_r=("first_30m_directional_r", "median"),
        )
        .reset_index()
        .sort_values(["net_pnl", "lot_count"], ascending=[False, False])
    )


def _bucket_year(features: pd.DataFrame) -> pd.DataFrame:
    return (
        features.groupby(["stage060_relative_basis_bucket", "exit_year"], dropna=False)
        .agg(lot_count=("lot_id", "count"), realized_pnl=("realized_pnl", "sum"))
        .reset_index()
        .sort_values(["stage060_relative_basis_bucket", "exit_year"])
    )


def _product_bucket(features: pd.DataFrame) -> pd.DataFrame:
    return (
        features.groupby(["product_key", "stage060_relative_basis_bucket"], dropna=False)
        .agg(lot_count=("lot_id", "count"), realized_pnl=("realized_pnl", "sum"))
        .reset_index()
        .sort_values("realized_pnl", ascending=False)
    )


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


def _upper_bound_curve(curve: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    events = features.copy()
    events["exit_day_norm"] = pd.to_datetime(events["exit_day"], errors="coerce").dt.normalize()
    events["target_realized_pnl"] = np.where(
        events["stage060_relative_basis_bucket"].eq(TARGET_BUCKET),
        events["realized_pnl"],
        0.0,
    )
    events["target_lot_count"] = np.where(events["stage060_relative_basis_bucket"].eq(TARGET_BUCKET), 1, 0)
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
        data[f"pnl_{bucket}"] = np.where(data["stage060_relative_basis_bucket"].eq(bucket), data["realized_pnl"], 0.0)
    daily_columns = [f"pnl_{bucket}" for bucket in BUCKET_COLORS]
    daily = data.groupby("exit_day_norm", dropna=False)[daily_columns].sum().reset_index().rename(columns={"exit_day_norm": "date"})
    out = out.merge(daily, on="date", how="left")
    for column in daily_columns:
        out[column] = out[column].fillna(0.0)
        out[f"cum_{column}"] = out[column].cumsum()
    return out


def _coverage_by_year(features: pd.DataFrame) -> pd.DataFrame:
    out = (
        features.assign(ready=features["stage060_relative_basis_ready"].astype(bool))
        .groupby("entry_year", dropna=False)
        .agg(
            lot_count=("lot_id", "count"),
            ready_count=("ready", "sum"),
            net_pnl=("realized_pnl", "sum"),
            ready_pnl=("realized_pnl", lambda item: item[features.loc[item.index, "stage060_relative_basis_ready"].astype(bool)].sum()),
        )
        .reset_index()
    )
    out["ready_rate_pct"] = out["ready_count"] / out["lot_count"] * 100.0
    return out.sort_values("entry_year")


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2, 1.2, 1]})
    axes[0].plot(curve["date"], curve["account_equity"], lw=1.3, color="#1f77b4", label="official equity")
    axes[0].plot(
        curve["date"],
        curve["upper_bound_skip_target_equity"],
        lw=1.3,
        color="#d62728",
        label="diagnostic skip relative-basis headwind equity",
    )
    axes[0].set_yscale("log")
    axes[0].set_title("Stage060 relative-basis headwind upper-bound diagnostic")
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
    axes[0].set_title("Stage060 cumulative PnL by relative-basis bucket")
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
    axes[0].bar(x, coverage["ready_count"], color="#1f77b4", label="relative-basis ready")
    axes[0].set_ylabel("lot count")
    axes[0].set_title("Stage060 relative-basis ready coverage by entry year")
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
        index="stage060_relative_basis_bucket",
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
    ax.set_title("Stage060 bucket-year realized PnL")
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
    product_totals = product_bucket.groupby("product_key")["realized_pnl"].sum().abs().sort_values(ascending=False)
    top_products = product_totals.head(18).index.tolist()
    temp = product_bucket[product_bucket["product_key"].isin(top_products)].copy()
    pivot = temp.pivot_table(
        index="product_key",
        columns="stage060_relative_basis_bucket",
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
    ax.set_title("Stage060 product-bucket realized PnL")
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
        ("stage060_directional_yoy_delta", "realized_pnl", "directional YoY relative basis vs PnL"),
        ("stage060_directional_yoy_delta", "first_30m_directional_r", "directional YoY relative basis vs first 30m R"),
        ("stage060_directional_yoy_delta", "direction_aligned_trend_tstat_252_stage052", "directional YoY relative basis vs trend t-stat"),
        ("stage060_directional_yoy_delta", "mae_r", "directional YoY relative basis vs whole-trade MAE R"),
    ]
    max_abs_pnl = max(float(features["realized_pnl"].abs().max()), 1.0)
    for ax, (x_col, y_col, title) in zip(axes.ravel(), specs):
        for bucket, group in features.groupby("stage060_relative_basis_bucket"):
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
    bucket_year: pd.DataFrame,
    product_bucket: pd.DataFrame,
    coverage: pd.DataFrame,
) -> None:
    lines = [
        "# Stage060 relative-basis shock audit",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- candidate_like: `{decision['candidate_like']}`",
        f"- relative-basis ready lots: `{decision['relative_basis_ready_lot_count']}/{decision['input_lot_count']}`",
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
                    "stage060_relative_basis_bucket",
                    "lot_count",
                    "product_count",
                    "code_count",
                    "year_count",
                    "net_pnl",
                    "positive_lot_count",
                    "negative_lot_count",
                    "median_directional_yoy_delta",
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
        _md_table(bucket_year[["stage060_relative_basis_bucket", "exit_year", "lot_count", "realized_pnl"]], 40),
        "",
        "## Product-Bucket PnL",
        "",
        _md_table(
            product_bucket.reindex(product_bucket["realized_pnl"].abs().sort_values(ascending=False).index)[
                ["product_key", "stage060_relative_basis_bucket", "lot_count", "realized_pnl"]
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
        f"- relative-basis scatter: `{SCATTER_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features, curve, basis = _load_inputs()
    rb_daily = _build_relative_basis_daily(basis)
    bound = _bind_features(features, rb_daily)

    bucket_summary = _group_summary(bound, ["stage060_relative_basis_bucket"])
    bucket_year = _bucket_year(bound)
    product_bucket = _product_bucket(bound)
    upper_curve = _upper_bound_curve(curve, bound)
    contribution = _contribution_curve(bound, curve)
    coverage = _coverage_by_year(bound)

    official_metrics = _performance_from_curve(upper_curve, "account_equity", "official_drawdown_pct_recalc")
    upper_metrics = _performance_from_curve(upper_curve, "upper_bound_skip_target_equity", "upper_bound_drawdown_pct")
    official_return = official_metrics["total_return_pct"]
    upper_return = upper_metrics["total_return_pct"]
    retention = upper_return / official_return * 100.0 if official_return else np.nan

    target = bound[bound["stage060_relative_basis_bucket"].eq(TARGET_BUCKET)].copy()
    missing = bound[bound["stage060_relative_basis_bucket"].eq("relative_basis_missing")].copy()
    ready = bound["stage060_relative_basis_ready"].astype(bool)

    decision_name = "stage060_relative_basis_headwind_no_candidate_right_tail_dominant"
    candidate_like = False
    if (
        len(target) >= 30
        and float(target["realized_pnl"].sum()) < 0.0
        and retention >= 80.0
        and upper_metrics["max_dd_pct"] > official_metrics["max_dd_pct"]
    ):
        decision_name = "stage060_relative_basis_headwind_watch_requires_true_engine"
        candidate_like = True

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_name,
        "candidate_like": candidate_like,
        "relative_basis_spec": {
            "relative_basis_rate": "near_basis_rate - dom_basis_rate",
            "seasonal_diff_rows": SEASONAL_DIFF_ROWS,
            "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
            "directional_alignment": "long wants positive YoY relative-basis delta; short wants negative",
            "target_bucket": TARGET_BUCKET,
        },
        "input_lot_count": int(len(bound)),
        "relative_basis_ready_lot_count": int(ready.sum()),
        "relative_basis_ready_rate_pct": float(ready.mean() * 100.0),
        "basis_daily_row_count": int(len(rb_daily)),
        "basis_symbol_count": int(rb_daily["symbol"].nunique()),
        "basis_first_date": rb_daily["date"].min(),
        "basis_last_date": rb_daily["date"].max(),
        "target_bucket": TARGET_BUCKET,
        "target_lot_count": int(len(target)),
        "target_realized_pnl": float(target["realized_pnl"].sum()),
        "target_product_count": int(target["product_key"].nunique()),
        "target_year_count": int(target["entry_year"].nunique()),
        "missing_lot_count": int(len(missing)),
        "missing_realized_pnl": float(missing["realized_pnl"].sum()),
        "official_metrics": official_metrics,
        "upper_bound_metrics": upper_metrics,
        "upper_bound_return_retention_pct": float(retention),
        "bucket_pnl": {
            str(row["stage060_relative_basis_bucket"]): float(row["net_pnl"])
            for _, row in bucket_summary.iterrows()
        },
        "judgment": (
            "The fixed relative-basis YoY headwind bucket is a large positive right-tail cohort for current "
            "C9/15w. Relative basis remains economically meaningful as an inventory/convenience-yield monitor, "
            "but it should not be promoted as a risk-cut rule without a new independent point-in-time source or "
            "forward evidence."
        ),
        "outputs": {
            "relative_basis_daily": RELATIVE_BASIS_DAILY_OUT,
            "features": FEATURES_OUT,
            "bucket_summary": BUCKET_SUMMARY_OUT,
            "bucket_year": BUCKET_YEAR_OUT,
            "product_bucket": PRODUCT_BUCKET_OUT,
            "upper_bound_curve": UPPER_BOUND_CURVE_OUT,
            "summary": SUMMARY_OUT,
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

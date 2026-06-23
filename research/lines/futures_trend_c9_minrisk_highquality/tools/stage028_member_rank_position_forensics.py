from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage028"
MODEL_TAG = "stage028_member_rank_position_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage028_c9_minrisk_member_rank_position_forensics"
TRADING_DAYS_PER_YEAR = 252
ACCOUNT_CAPITAL = 150_000.0
MAX_SIGNAL_AGE_DAYS = 7
ROLLING_DAYS = 120
MIN_ROLLING_DAYS = 40

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE027_DIR = LINE_DIR / "outputs" / "stage027_supply_demand_inventory_forensics"
STAGE005_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage028_member_rank_position_forensics"
BACKTEST_OUTPUT_DIR = EXAMPLE_DIR / "backtest_outputs"

FEATURES_IN = (
    STAGE027_DIR
    / "qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_features_"
    "stage027_supply_demand_inventory_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE005_DIR
    / "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_official_curve_"
    "stage005_signal_quality_visual_forensics_v1.csv"
)
RAW_MEMBER_RANK_IN = (
    BACKTEST_OUTPUT_DIR / "external_domestic_member_rank_cache" / "member_rank_sum_daily_20230101_20260417.csv"
)

MEMBER_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_member_features_{MODEL_TAG}.csv"
FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
BUCKET_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
PRODUCT_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_matrix_{MODEL_TAG}.csv"
ACTIVE_SHARE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_active_share_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_member_rank_state_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_contribution_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_member_score_scatter_{MODEL_TAG}.png"
PRODUCT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_member_rank_heatmap_{MODEL_TAG}.png"
SOURCE_COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_coverage_chart_{MODEL_TAG}.png"

PRODUCTS_BY_CODE: dict[str, str] = {
    "AP": "AP.CZCE",
    "CF": "CF.CZCE",
    "FG": "FG.CZCE",
    "MA": "MA.CZCE",
    "OI": "OI.CZCE",
    "SA": "SA.CZCE",
    "SH": "SH.CZCE",
    "SM": "SM.CZCE",
    "AU": "au.SHFE",
    "CU": "cu.SHFE",
    "FU": "fu.SHFE",
    "HC": "hc.SHFE",
    "RB": "rb.SHFE",
    "RU": "ru.SHFE",
    "SP": "sp.SHFE",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


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


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _rolling_zscore(series: pd.Series) -> pd.Series:
    mean = series.rolling(ROLLING_DAYS, min_periods=MIN_ROLLING_DAYS).mean()
    std = series.rolling(ROLLING_DAYS, min_periods=MIN_ROLLING_DAYS).std().replace(0.0, np.nan)
    return (series - mean) / std


def _select_product_rows(group: pd.DataFrame) -> pd.DataFrame:
    variety = str(group["variety"].iloc[0]).upper()
    symbol = group["symbol"].astype(str).str.upper()
    product_rows = group[symbol.eq(variety)].copy()
    if not product_rows.empty:
        return product_rows
    return group.copy()


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "drawdown_pct",
        "net_pnl",
        "slippage",
        "trade_count",
        "broker10_margin_to_equity_pct",
        "broker10_total_margin_exact",
    ]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    prev_equity = curve["account_equity"].shift(1)
    prev_equity.iloc[0] = ACCOUNT_CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev_equity - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _normalize_lot_product(product: Any, vt_symbol: Any) -> str:
    product_text = "" if pd.isna(product) else str(product).strip()
    if "." in product_text:
        return product_text
    vt_text = "" if pd.isna(vt_symbol) else str(vt_symbol).strip()
    if "." not in vt_text:
        return product_text
    contract, exchange = vt_text.rsplit(".", 1)
    match = re.match(r"([A-Za-z]+)", contract)
    if not match:
        return product_text
    return f"{match.group(1)}.{exchange}"


def _build_member_rank_features(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    frame["date"] = frame["date"].astype(str).str.replace("-", "", regex=False)
    frame["variety"] = frame["variety"].astype(str).str.upper()
    frame = frame[frame["variety"].isin(PRODUCTS_BY_CODE)].copy()
    if frame.empty:
        return pd.DataFrame()

    needed = [
        "long_open_interest_top20",
        "long_open_interest_chg_top20",
        "short_open_interest_top20",
        "short_open_interest_chg_top20",
        "vol_top20",
        "vol_chg_top20",
    ]
    for column in needed:
        frame[column] = _numeric(frame, column)

    rows: list[dict[str, Any]] = []
    for (date, variety), group in frame.groupby(["date", "variety"], sort=True):
        selected = _select_product_rows(group)
        long_oi = float(selected["long_open_interest_top20"].sum())
        short_oi = float(selected["short_open_interest_top20"].sum())
        long_chg = float(selected["long_open_interest_chg_top20"].sum())
        short_chg = float(selected["short_open_interest_chg_top20"].sum())
        vol = float(selected["vol_top20"].sum())
        vol_chg = float(selected["vol_chg_top20"].sum())
        denominator = max(long_oi + short_oi, 1.0)
        rows.append(
            {
                "member_date": date,
                "product_code": variety,
                "product": PRODUCTS_BY_CODE[variety],
                "contract_rows_used": int(len(selected)),
                "long_open_interest_top20": long_oi,
                "short_open_interest_top20": short_oi,
                "long_open_interest_chg_top20": long_chg,
                "short_open_interest_chg_top20": short_chg,
                "vol_top20": vol,
                "vol_chg_top20": vol_chg,
                "net_position_ratio_top20": (long_oi - short_oi) / denominator,
                "net_position_chg_ratio_top20": (long_chg - short_chg) / denominator,
                "turnover_pressure_ratio_top20": vol / denominator,
            }
        )

    features = pd.DataFrame(rows)
    features["member_date_dt"] = pd.to_datetime(features["member_date"], format="%Y%m%d", errors="coerce")
    features = features.dropna(subset=["member_date_dt"]).copy()
    chunks: list[pd.DataFrame] = []
    for _, group in features.groupby("product", sort=False):
        group = group.sort_values("member_date_dt").copy()
        group["member_rank_history_count"] = (
            group["net_position_chg_ratio_top20"].rolling(ROLLING_DAYS, min_periods=1).count()
        )
        group["net_position_ratio_z"] = _rolling_zscore(group["net_position_ratio_top20"])
        group["net_position_chg_ratio_z"] = _rolling_zscore(group["net_position_chg_ratio_top20"])
        group["member_feature_ready"] = (
            group["member_rank_history_count"].ge(MIN_ROLLING_DAYS)
            & group["net_position_ratio_z"].notna()
            & group["net_position_chg_ratio_z"].notna()
        )
        group["member_rank_level_component"] = np.where(
            group["member_feature_ready"],
            group["net_position_ratio_z"].clip(-2.0, 2.0) / 2.0,
            np.nan,
        )
        group["member_rank_flow_component"] = np.where(
            group["member_feature_ready"],
            group["net_position_chg_ratio_z"].clip(-2.0, 2.0) / 2.0,
            np.nan,
        )
        group["member_rank_directional_component"] = (
            0.25 * group["member_rank_level_component"] + 0.75 * group["member_rank_flow_component"]
        ).clip(-1.0, 1.0)
        chunks.append(group)

    out = pd.concat(chunks, ignore_index=True)
    out["member_available_datetime"] = out["member_date_dt"] + pd.Timedelta(hours=20)
    return out.sort_values(["product", "member_available_datetime"]).reset_index(drop=True)


def _source_summary(member_features: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    if member_features.empty:
        return pd.DataFrame()
    summary = (
        member_features.groupby("product")
        .agg(
            data_days=("member_date", "nunique"),
            ready_days=("member_feature_ready", "sum"),
            start_date=("member_date", "min"),
            end_date=("member_date", "max"),
            avg_contract_rows=("contract_rows_used", "mean"),
            avg_net_position_ratio=("net_position_ratio_top20", "mean"),
            avg_net_position_chg_ratio=("net_position_chg_ratio_top20", "mean"),
            avg_directional_component=("member_rank_directional_component", "mean"),
        )
        .reset_index()
    )
    summary.insert(0, "source_mode", "cache")
    summary["raw_rows"] = len(raw)
    summary["raw_variety_count"] = raw["variety"].astype(str).str.upper().nunique()
    return summary


def _bind_member_rank_to_lots(lots: pd.DataFrame, member_features: pd.DataFrame) -> pd.DataFrame:
    lots = lots.copy()
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots["prev_state_date"] = pd.to_datetime(lots["prev_state_date"], errors="coerce").dt.normalize()
    lots["member_lookup_datetime"] = lots["prev_state_date"].fillna(lots["entry_date"] - pd.Timedelta(days=1))
    lots["member_lookup_datetime"] = lots["member_lookup_datetime"] + pd.Timedelta(hours=23, minutes=59)
    lots["product_raw_stage028"] = lots["product"].fillna("").astype(str)
    lots["product"] = [
        _normalize_lot_product(product, vt_symbol)
        for product, vt_symbol in zip(lots["product_raw_stage028"], lots["vt_symbol"], strict=False)
    ]
    lots["direction"] = lots["direction"].fillna("").astype(str).str.lower()
    lots["_lot_order"] = np.arange(len(lots), dtype=int)

    signal_cols = [
        "member_date",
        "member_date_dt",
        "member_available_datetime",
        "product_code",
        "contract_rows_used",
        "member_rank_history_count",
        "member_feature_ready",
        "long_open_interest_top20",
        "short_open_interest_top20",
        "long_open_interest_chg_top20",
        "short_open_interest_chg_top20",
        "net_position_ratio_top20",
        "net_position_chg_ratio_top20",
        "turnover_pressure_ratio_top20",
        "net_position_ratio_z",
        "net_position_chg_ratio_z",
        "member_rank_level_component",
        "member_rank_flow_component",
        "member_rank_directional_component",
    ]
    bound_frames: list[pd.DataFrame] = []
    for product, product_lots in lots.groupby("product", sort=False):
        product_features = member_features[member_features["product"].eq(product)].copy()
        left = product_lots.sort_values("member_lookup_datetime").copy()
        if product_features.empty:
            for column in signal_cols:
                left[f"member_{column}"] = np.nan
            bound_frames.append(left)
            continue
        right = product_features[["product", *signal_cols]].sort_values("member_available_datetime").copy()
        merged = pd.merge_asof(
            left,
            right,
            left_on="member_lookup_datetime",
            right_on="member_available_datetime",
            by="product",
            direction="backward",
            tolerance=pd.Timedelta(days=MAX_SIGNAL_AGE_DAYS),
        )
        rename = {column: f"member_{column}" for column in signal_cols}
        merged = merged.rename(columns=rename)
        bound_frames.append(merged)

    out = pd.concat(bound_frames, ignore_index=True).sort_values("_lot_order").drop(columns=["_lot_order"])
    out["member_signal_missing_stage028"] = out["member_member_available_datetime"].isna()
    out["member_feature_ready_stage028"] = out["member_member_feature_ready"].fillna(False).astype(bool)
    out["member_signal_age_days"] = (
        out["member_lookup_datetime"] - pd.to_datetime(out["member_member_available_datetime"], errors="coerce")
    ).dt.total_seconds() / 86400.0

    direction_sign = np.where(out["direction"].eq("long"), 1.0, np.where(out["direction"].eq("short"), -1.0, np.nan))
    raw_component = pd.to_numeric(out["member_member_rank_directional_component"], errors="coerce")
    flow_component = pd.to_numeric(out["member_member_rank_flow_component"], errors="coerce")
    level_component = pd.to_numeric(out["member_member_rank_level_component"], errors="coerce")
    out["member_score"] = direction_sign * raw_component
    out["member_flow_score"] = direction_sign * flow_component
    out["member_level_score"] = direction_sign * level_component
    out.loc[~out["member_feature_ready_stage028"], ["member_score", "member_flow_score", "member_level_score"]] = np.nan

    score = pd.to_numeric(out["member_score"], errors="coerce")
    out["member_bucket_stage028"] = "member_missing"
    ready = out["member_feature_ready_stage028"] & score.notna()
    out.loc[ready & score.ge(0.35), "member_bucket_stage028"] = "member_supportive"
    out.loc[ready & score.le(-0.35), "member_bucket_stage028"] = "member_headwind"
    out.loc[ready & score.gt(-0.35) & score.lt(0.35), "member_bucket_stage028"] = "member_neutral"

    flow = pd.to_numeric(out["member_flow_score"], errors="coerce")
    out["member_flow_bucket_stage028"] = "member_missing"
    out.loc[ready & flow.ge(0.35), "member_flow_bucket_stage028"] = "flow_supportive"
    out.loc[ready & flow.le(-0.35), "member_flow_bucket_stage028"] = "flow_headwind"
    out.loc[ready & flow.gt(-0.35) & flow.lt(0.35), "member_flow_bucket_stage028"] = "flow_neutral"

    out["member_strong_headwind_stage028"] = "not_strong_headwind"
    out.loc[ready & score.le(-0.50), "member_strong_headwind_stage028"] = "strong_headwind"
    out.loc[~ready, "member_strong_headwind_stage028"] = "member_missing"
    return out


def _summarize_bucket(features: pd.DataFrame, bucket_column: str) -> pd.DataFrame:
    pnl_all = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    total_net = float(pnl_all.sum())
    total_pos = float(pnl_all.clip(lower=0.0).sum())
    total_neg_abs = abs(float(pnl_all.clip(upper=0.0).sum()))
    rows: list[dict[str, Any]] = []
    for bucket, group in features.groupby(bucket_column, dropna=False):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        pos = float(pnl.clip(lower=0.0).sum())
        neg = float(pnl.clip(upper=0.0).sum())
        rows.append(
            {
                "bucket_family": bucket_column,
                "bucket": str(bucket),
                "lot_count": int(len(group)),
                "product_count": int(group["product"].nunique()),
                "year_count": int(group["entry_year"].nunique()),
                "net_pnl": float(pnl.sum()),
                "positive_pnl": pos,
                "negative_pnl": neg,
                "net_pnl_share_pct": float(pnl.sum() / total_net * 100.0) if total_net else np.nan,
                "positive_coverage_pct": float(pos / total_pos * 100.0) if total_pos else np.nan,
                "negative_abs_coverage_pct": float(abs(neg) / total_neg_abs * 100.0) if total_neg_abs else np.nan,
                "win_rate_pct": float((pnl > 0.0).mean() * 100.0) if len(pnl) else np.nan,
                "median_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                "avg_member_score": float(pd.to_numeric(group["member_score"], errors="coerce").mean()),
                "avg_member_flow_score": float(pd.to_numeric(group["member_flow_score"], errors="coerce").mean()),
                "missing_rate_pct": float((~group["member_feature_ready_stage028"]).mean() * 100.0),
            }
        )
    return pd.DataFrame(rows).sort_values(["bucket_family", "net_pnl"], ascending=[True, False])


def _bucket_year_matrix(features: pd.DataFrame, bucket_column: str) -> pd.DataFrame:
    matrix = features.pivot_table(
        index=bucket_column,
        columns="entry_year",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()
    matrix.columns = [str(int(column)) for column in matrix.columns]
    return matrix.reset_index().rename(columns={bucket_column: "bucket"})


def _product_bucket_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = features.pivot_table(
        index="product",
        columns="member_bucket_stage028",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()
    return matrix.reset_index()


def _build_daily_active_share(features: pd.DataFrame, official_curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for date in official_curve["date"]:
        active = features[(features["entry_date"] <= date) & (features["exit_date"] >= date)].copy()
        total = int(len(active))
        if total == 0:
            rows.append(
                {
                    "date": date,
                    "active_lot_count": 0,
                    "member_ready_share_pct": 0.0,
                    "member_supportive_share_pct": 0.0,
                    "member_neutral_share_pct": 0.0,
                    "member_headwind_share_pct": 0.0,
                    "member_missing_share_pct": 0.0,
                    "active_avg_member_score": np.nan,
                }
            )
            continue
        ready = active["member_feature_ready_stage028"]
        rows.append(
            {
                "date": date,
                "active_lot_count": total,
                "member_ready_share_pct": float(ready.mean() * 100.0),
                "member_supportive_share_pct": float(active["member_bucket_stage028"].eq("member_supportive").mean() * 100.0),
                "member_neutral_share_pct": float(active["member_bucket_stage028"].eq("member_neutral").mean() * 100.0),
                "member_headwind_share_pct": float(active["member_bucket_stage028"].eq("member_headwind").mean() * 100.0),
                "member_missing_share_pct": float(active["member_bucket_stage028"].eq("member_missing").mean() * 100.0),
                "active_avg_member_score": float(pd.to_numeric(active["member_score"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows)


def _official_metrics(official_curve: pd.DataFrame, features: pd.DataFrame) -> dict[str, float]:
    returns = pd.to_numeric(official_curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0.0 else 0.0
    start = float(official_curve["account_equity"].iloc[0]) if not official_curve.empty else ACCOUNT_CAPITAL
    end = float(official_curve["account_equity"].iloc[-1]) if not official_curve.empty else ACCOUNT_CAPITAL
    return {
        "end_equity": end,
        "total_return_pct": (end / start - 1.0) * 100.0 if start else np.nan,
        "max_drawdown_pct": float(pd.to_numeric(official_curve["drawdown_pct"], errors="coerce").min()),
        "sharpe": sharpe,
        "total_slippage": float(pd.to_numeric(official_curve["slippage"], errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(official_curve["trade_count"], errors="coerce").fillna(0.0).sum()),
        "closed_lot_win_rate_pct": float(
            (pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0) > 0.0).mean() * 100.0
        ),
        "closed_lot_count": float(len(features)),
    }


def _plot_path(official_curve: pd.DataFrame, daily_active: pd.DataFrame) -> None:
    merged = official_curve.merge(daily_active, on="date", how="left")
    fig, axes = plt.subplots(5, 1, figsize=(15, 14), sharex=True)
    axes[0].plot(merged["date"], merged["account_equity"], color="#1f77b4", linewidth=1.6)
    axes[0].set_title("Official C9/15w equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(merged["date"], merged["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].set_title("Official drawdown pct")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(merged["date"], merged["broker10_margin_to_equity_pct"], color="#9467bd", linewidth=1.1)
    axes[2].axhline(100.0, color="#555555", linestyle="--", linewidth=0.8)
    axes[2].set_title("Broker10 margin pressure")
    axes[2].grid(True, alpha=0.25)
    axes[3].plot(merged["date"], merged["member_ready_share_pct"], color="#4c78a8", linewidth=1.0, label="ready")
    axes[3].plot(merged["date"], merged["member_missing_share_pct"], color="#7f7f7f", linewidth=0.9, label="missing")
    axes[3].set_ylim(-2, 102)
    axes[3].set_title("Active lot member-rank coverage")
    axes[3].legend(loc="upper left", ncol=2, fontsize=8)
    axes[3].grid(True, alpha=0.25)
    axes[4].plot(merged["date"], merged["member_supportive_share_pct"], color="#2ca02c", linewidth=1.0, label="supportive")
    axes[4].plot(merged["date"], merged["member_headwind_share_pct"], color="#ff7f0e", linewidth=1.0, label="headwind")
    axes[4].plot(merged["date"], merged["active_avg_member_score"], color="#111111", linewidth=0.9, label="avg_score")
    axes[4].set_title("Active lot member-rank state share")
    axes[4].legend(loc="upper left", ncol=3, fontsize=8)
    axes[4].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contribution(features: pd.DataFrame) -> None:
    calendar = pd.date_range(features["exit_date"].min(), features["exit_date"].max(), freq="D")
    fig, ax = plt.subplots(figsize=(15, 7))
    all_daily = features.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
    ax.plot(calendar, all_daily, color="#1f77b4", linewidth=1.8, label="all closed lots")
    colors = {
        "member_supportive": "#2ca02c",
        "member_neutral": "#17becf",
        "member_headwind": "#ff7f0e",
        "member_missing": "#7f7f7f",
    }
    for bucket, color in colors.items():
        sub = features[features["member_bucket_stage028"].eq(bucket)]
        if sub.empty:
            continue
        daily = sub.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
        ax.plot(calendar, daily, linewidth=1.25, label=bucket, color=color)
    ax.axhline(0.0, color="#555555", linewidth=0.8)
    ax.set_title("Closed-lot realized PnL contribution by member-rank bucket")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_bucket_year_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    data = matrix.set_index("bucket")
    values = data.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(13, max(4, 0.55 * len(data))))
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(data.columns, rotation=45, ha="right")
    ax.set_title("Member-rank bucket by entry year net PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(BUCKET_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    valid = features[features["member_feature_ready_stage028"]].copy()
    if valid.empty:
        return
    pnl = pd.to_numeric(valid["realized_pnl"], errors="coerce").fillna(0.0)
    size = np.asarray(np.clip(np.abs(pnl) / max(np.nanpercentile(np.abs(pnl), 80), 1.0) * 25.0, 10.0, 90.0))
    color = np.asarray(np.where(pnl >= 0.0, "#2ca02c", "#d62728"))
    marker_map = {"long": "o", "short": "^"}
    fig, ax = plt.subplots(figsize=(11, 7))
    for direction, marker in marker_map.items():
        sub = valid[valid["direction"].eq(direction)]
        if sub.empty:
            continue
        positions = valid.index.get_indexer(sub.index)
        ax.scatter(
            sub["member_flow_score"],
            sub["member_level_score"],
            s=size[positions],
            c=color[positions],
            alpha=0.62,
            marker=marker,
            label=direction,
            edgecolors="none",
        )
    ax.axvline(-0.35, color="#ff7f0e", linestyle="--", linewidth=0.9)
    ax.axvline(0.35, color="#2ca02c", linestyle="--", linewidth=0.9)
    ax.axhline(0.0, color="#555555", linestyle=":", linewidth=0.8)
    ax.set_title("Entry pre-state member-rank flow vs level score")
    ax.set_xlabel("top20 net long flow score aligned to C9 direction")
    ax.set_ylabel("top20 net position level score aligned to C9 direction")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_product_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    data = matrix.set_index("product")
    values = data.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(8, max(6, 0.35 * len(data))))
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(data.columns, rotation=35, ha="right")
    ax.set_title("Product x member-rank bucket net PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(PRODUCT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_source_coverage(source_summary: pd.DataFrame) -> None:
    if source_summary.empty:
        return
    data = source_summary.sort_values("ready_days", ascending=True)
    fig, ax = plt.subplots(figsize=(10, max(5, 0.35 * len(data))))
    ax.barh(data["product"], data["data_days"], color="#9ecae1", label="data_days")
    ax.barh(data["product"], data["ready_days"], color="#3182bd", label="ready_days")
    ax.set_title("Cached member-rank source coverage by product")
    ax.set_xlabel("days")
    ax.grid(True, axis="x", alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(SOURCE_COVERAGE_CHART_OUT, dpi=160)
    plt.close(fig)


def _build_decision(
    features: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    official_metrics: dict[str, float],
    member_feature_rows: int,
    source_summary: pd.DataFrame,
) -> dict[str, Any]:
    lot_count = int(len(features))
    ready_count = int(features["member_feature_ready_stage028"].sum())
    bucket_rows = bucket_summary[bucket_summary["bucket_family"].eq("member_bucket_stage028")]

    def row(bucket: str) -> dict[str, Any]:
        hit = bucket_rows[bucket_rows["bucket"].eq(bucket)]
        return hit.iloc[0].to_dict() if not hit.empty else {}

    supportive = row("member_supportive")
    headwind = row("member_headwind")
    neutral = row("member_neutral")
    missing = row("member_missing")

    candidate_like = []
    if headwind:
        if (
            float(headwind.get("net_pnl", 0.0)) < 0.0
            and float(headwind.get("negative_abs_coverage_pct", 0.0)) >= 25.0
            and float(headwind.get("positive_coverage_pct", 100.0)) <= 15.0
            and int(headwind.get("product_count", 0)) >= 8
            and int(headwind.get("year_count", 0)) >= 3
        ):
            candidate_like.append("member_headwind")

    ready_rate = ready_count / lot_count * 100.0 if lot_count else 0.0
    if ready_rate < 45.0:
        decision = "stage028_member_rank_no_candidate_coverage_too_low_for_c9"
        reason = (
            "The cached member-rank source starts in 2023 and covers only selected products, so it cannot "
            "explain the full C9 path or the 2020-2022 drawdown base."
        )
    elif candidate_like:
        decision = "stage028_member_rank_watch_only_requires_true_engine"
        reason = (
            "A broad negative member-rank bucket exists in read-only attribution, but any action would need "
            "a frozen true engine and multi-start validation."
        )
    else:
        decision = "stage028_member_rank_no_candidate_nonmonotonic_or_right_tail_dominant"
        reason = (
            "Member-rank positioning does not isolate a broad stable C9 loss bucket without also carrying "
            "meaningful positive/right-tail contribution."
        )

    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "candidate_ready": 0,
        "ab_triggered": 0,
        "reason": reason,
        "lot_count": lot_count,
        "member_feature_rows": int(member_feature_rows),
        "member_source_product_count": int(source_summary["product"].nunique()) if not source_summary.empty else 0,
        "member_ready_count": ready_count,
        "member_ready_rate_pct": ready_rate,
        "candidate_like_readonly_buckets": candidate_like,
        "member_supportive": supportive,
        "member_neutral": neutral,
        "member_headwind": headwind,
        "member_missing": missing,
        "official_metrics": official_metrics,
        "guardrails": {
            "source": str(RAW_MEMBER_RANK_IN),
            "source_mode": "local_cache_no_online_refetch",
            "point_in_time_binding": (
                "rank data available at exchange date 20:00, merge_asof backward by product on "
                f"prev_state_date end-of-day with max {MAX_SIGNAL_AGE_DAYS} calendar days lag"
            ),
            "formula": (
                "0.25 * rolling_z(top20_net_position_level) + 0.75 * rolling_z(top20_net_position_flow), "
                "aligned by C9 trade direction"
            ),
            "rolling_days": ROLLING_DAYS,
            "min_rolling_days": MIN_ROLLING_DAYS,
            "no_parameter_sweep": True,
            "no_trade_rule": True,
            "no_ctp_or_order_api": True,
            "missing_member_state_keeps_official_path": True,
        },
        "outputs": {
            "member_features": str(MEMBER_FEATURES_OUT),
            "features": str(FEATURES_OUT),
            "source_summary": str(SOURCE_SUMMARY_OUT),
            "bucket_summary": str(BUCKET_SUMMARY_OUT),
            "bucket_year_matrix": str(BUCKET_YEAR_OUT),
            "product_bucket_matrix": str(PRODUCT_BUCKET_OUT),
            "daily_active_share": str(ACTIVE_SHARE_OUT),
            "report": str(REPORT_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "contribution_chart": str(CONTRIBUTION_CHART_OUT),
            "bucket_year_heatmap": str(BUCKET_YEAR_HEATMAP_OUT),
            "scatter": str(SCATTER_OUT),
            "product_heatmap": str(PRODUCT_HEATMAP_OUT),
            "source_coverage_chart": str(SOURCE_COVERAGE_CHART_OUT),
        },
    }


def _write_report(
    features: pd.DataFrame,
    source_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    bucket_year: pd.DataFrame,
    product_bucket: pd.DataFrame,
    official_metrics: dict[str, float],
    decision: dict[str, Any],
) -> None:
    member_summary = bucket_summary[bucket_summary["bucket_family"].eq("member_bucket_stage028")]
    flow_summary = bucket_summary[bucket_summary["bucket_family"].eq("member_flow_bucket_stage028")]
    strong_headwind_summary = bucket_summary[bucket_summary["bucket_family"].eq("member_strong_headwind_stage028")]
    valid = features[features["member_feature_ready_stage028"]].copy()
    report = f"""# {STAGE} 会员持仓排名结构只读法证

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} CST
- 阶段性质：点时化会员持仓排名外生状态只读归因；不修改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否
- 当前官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`

## 外部调研与判断

- AKShare 文档确认商品期货会员持仓排名可用：`get_rank_sum_daily(start_day, end_day, vars_list)` 可取前5/10/15/20会员汇总，另有 DCE/CFFEX/CZCE/SHFE rank table 明细接口。
- 文档同时提示交易所口径不统一：大连偏品种总排名；上海、中金按合约排名、没有品种总排名，AKShare 会做合约加总；郑州同时有合约和品种排名，较接近交易所原始品种数据。
- AKShare GitHub README 说明其定位是开源财经数据接口并提示数据仅供研究参考；因此本阶段只使用本地缓存做审计，不在线重爬、不把接口噪声当 alpha。
- 我的判断：会员净多变化比 Stage027 粗仓单/基差分更接近“谁在承接风险”的微观结构，但口径差异和缓存起点决定它必须先做覆盖/语义/视觉法证，不能直接写成削仓规则。

## 回测/归因参数

- 官方 C9/15w closed-lot 区间：`{features['entry_date'].min().date()}` 至 `{features['exit_date'].max().date()}`。
- 会员持仓缓存：`{RAW_MEMBER_RANK_IN}`。
- 缓存数据区间：`{source_summary['start_date'].min() if not source_summary.empty else 'NA'}` 至 `{source_summary['end_date'].max() if not source_summary.empty else 'NA'}`。
- 点时化：交易所会员排名按收市结算后才可见，保守设为交易日 `20:00`；每笔 C9 入场只用 `prev_state_date` 日终前可见数据，最大滞后 `{MAX_SIGNAL_AGE_DAYS}` 个自然日。
- 固定公式：前20会员净持仓水平和净多变化各自做 `{ROLLING_DAYS}` 日滚动 zscore，最低 `{MIN_ROLLING_DAYS}` 日启用；方向分量为 `0.25 * level + 0.75 * flow`，再按 C9 多/空方向取同向分数。
- 固定分桶：`score >= 0.35` 为 `member_supportive`，`score <= -0.35` 为 `member_headwind`，其余 neutral；缺缓存或滚动历史不足为 missing。
- 策略口径：只读 closed-lot 归因和官方资金曲线视觉审计，不是交易引擎。

## 官方基准指标

- 期末权益：`{official_metrics['end_equity']:,.2f}`
- 总收益：`{official_metrics['total_return_pct']:.4f}%`
- 最大回撤：`{official_metrics['max_drawdown_pct']:.4f}%`
- Sharpe：`{official_metrics['sharpe']:.4f}`
- 总滑点：`{official_metrics['total_slippage']:,.0f}`
- 总交易次数：`{official_metrics['total_trade_count']:,.0f}`
- closed-lot 胜率：`{official_metrics['closed_lot_win_rate_pct']:.4f}%`

## 覆盖

- official closed lots：`{len(features)}`
- member ready：`{decision['member_ready_count']}`，覆盖率 `{decision['member_ready_rate_pct']:.4f}%`
- 有效会员持仓产品数：`{valid['product'].nunique() if not valid.empty else 0}`
- 有效会员持仓年份数：`{valid['entry_year'].nunique() if not valid.empty else 0}`
- 会员持仓特征行数：`{decision['member_feature_rows']}`
- source products：`{decision['member_source_product_count']}`

## 来源覆盖

{_md_table(source_summary, max_rows=40)}

## 会员持仓分组

{_md_table(member_summary)}

## 会员持仓流量分组

{_md_table(flow_summary)}

## 强逆风分组

{_md_table(strong_headwind_summary)}

## 年度矩阵

{_md_table(bucket_year)}

## 产品-会员持仓矩阵

{_md_table(product_bucket, max_rows=40)}

## 视觉观察

- path chart：`{PATH_CHART_OUT}`
  - 观察官方权益、回撤、broker10 与 active member-rank coverage/state；若覆盖只从 2023 后出现，不能解释 2020-2022 深回撤底座。
- contribution chart：`{CONTRIBUTION_CHART_OUT}`
  - 观察 supportive/neutral/headwind/missing 的 realized PnL 台阶；如果 headwind 也参与右尾，不能削仓。
- bucket-year heatmap：`{BUCKET_YEAR_HEATMAP_OUT}`
  - 观察 bucket 是否跨年单调；单一年份或近端窗口负贡献不构成普世规则。
- scatter：`{SCATTER_OUT}`
  - 观察会员净多流量与净持仓水平中盈亏点是否可分。
- product heatmap：`{PRODUCT_HEATMAP_OUT}`
  - 观察是否由少数产品块主导；若是，不能做产品/交易所补丁。
- source coverage chart：`{SOURCE_COVERAGE_CHART_OUT}`
  - 观察本地缓存产品覆盖和滚动历史启用情况。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 过拟合反思

- 运行前判断：否。信息源来自公开交易所会员持仓排名，本阶段使用本地已存在缓存，固定低自由度公式，不按 C9 亏损年份、品种、方向或具体交易调参。
- 运行后判断：以决策为准；若覆盖低或 bucket 非单调，继续扫 TopN、zscore 窗口、权重、阈值、产品、年份或方向就是过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage027 粗供需分已无候选，会员持仓结构是更接近风险承接主体的外生源。
- 运行后判断：以决策为准；若本阶段无候选，会员排名只保留为 forward watch/风险解释标签，不进入 true engine。
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = _read_csv(FEATURES_IN)
    official_curve = _load_official_curve()
    raw_member = _read_csv(RAW_MEMBER_RANK_IN)
    member_features = _build_member_rank_features(raw_member)
    source_summary = _source_summary(member_features, raw_member)

    features = _bind_member_rank_to_lots(lots, member_features)
    bucket_summary = pd.concat(
        [
            _summarize_bucket(features, "member_bucket_stage028"),
            _summarize_bucket(features, "member_flow_bucket_stage028"),
            _summarize_bucket(features, "member_strong_headwind_stage028"),
        ],
        ignore_index=True,
    )
    bucket_year = _bucket_year_matrix(features, "member_bucket_stage028")
    product_bucket = _product_bucket_matrix(features)
    daily_active = _build_daily_active_share(features, official_curve)
    official_metrics = _official_metrics(official_curve, features)
    decision = _build_decision(features, bucket_summary, official_metrics, len(member_features), source_summary)

    member_features.to_csv(MEMBER_FEATURES_OUT, index=False, encoding="utf-8-sig")
    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_year.to_csv(BUCKET_YEAR_OUT, index=False, encoding="utf-8-sig")
    product_bucket.to_csv(PRODUCT_BUCKET_OUT, index=False, encoding="utf-8-sig")
    daily_active.to_csv(ACTIVE_SHARE_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path(official_curve, daily_active)
    _plot_contribution(features)
    _plot_bucket_year_heatmap(bucket_year)
    _plot_scatter(features)
    _plot_product_heatmap(product_bucket)
    _plot_source_coverage(source_summary)
    _write_report(features, source_summary, bucket_summary, bucket_year, product_bucket, official_metrics, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage021"
MODEL_TAG = "stage021_same_direction_correlation_crowding_proxy_v1"
OUTPUT_PREFIX = "qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage021_same_direction_correlation_crowding_proxy"
STAGE016_DIR = LINE_DIR / "outputs" / "stage016_intersection_stability_audit"
STAGE019_DIR = LINE_DIR / "outputs" / "stage019_no_follow_light_shave_true_engine"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252

# Frozen diagnostic gate. This is a proxy audit, not a promoted trading rule.
CORR_GATE_START = 0.60
CORR_GATE_FULL = 0.80
CORR_GATE_FLOOR_WEIGHT = 0.50

FEATURES_IN = (
    STAGE016_DIR
    / "qmt_roll_stage016_c9_minrisk_intersection_stability_audit_features_"
    "stage016_intersection_stability_audit_v1.csv"
)
CURVE_IN = (
    STAGE019_DIR
    / "qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_curve_"
    "stage019_no_follow_light_shave_true_engine_v1.csv"
)
SUMMARY_IN = (
    STAGE019_DIR
    / "qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_summary_"
    "stage019_no_follow_light_shave_true_engine_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
ATTRIBUTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lot_attribution_{MODEL_TAG}.csv"
DAILY_WEIGHTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_weights_{MODEL_TAG}.csv"
CURVES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
METRICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_metrics_{MODEL_TAG}.csv"
YEAR_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_drawdown_chart_{MODEL_TAG}.png"
WEIGHT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_weight_share_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lot_contribution_chart_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_corr_pnl_scatter_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_return_heatmap_{MODEL_TAG}.png"


VARIANT_OFFICIAL = "A_official_c9_15w"
VARIANT_PROXY = "C_corr060_080_floor50_daily_active_proxy"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce", format="mixed")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _drawdown_pct(equity: pd.Series | np.ndarray) -> pd.Series:
    values = pd.Series(equity, dtype="float64")
    hwm = values.cummax()
    return (values / hwm - 1.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or returns.std(ddof=0) <= 1e-12:
        return np.nan
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _ulcer_pct(drawdown_pct: pd.Series) -> float:
    dd = pd.to_numeric(drawdown_pct, errors="coerce").fillna(0.0).clip(upper=0.0)
    return float(np.sqrt(np.mean(np.square(dd))))


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
    headers = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in headers) + " |")
    return "\n".join(lines)


def _prepare_official_curve() -> pd.DataFrame:
    data = _read_csv(CURVE_IN)
    if "arm" in data.columns:
        data = data[data["arm"].eq("A_official_stage847_c9_15w")].copy()
    if data.empty:
        raise RuntimeError("Stage019 curve does not contain A_official_stage847_c9_15w")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "net_pnl",
        "account_equity",
        "broker10_total_margin_exact",
        "broker10_margin_to_equity_pct",
        "slippage",
        "trade_count",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    data["official_drawdown_pct"] = _drawdown_pct(data["account_equity"]).to_numpy()
    return data[
        [
            "date",
            "net_pnl",
            "account_equity",
            "official_drawdown_pct",
            "broker10_total_margin_exact",
            "broker10_margin_to_equity_pct",
            "slippage",
            "trade_count",
        ]
    ].copy()


def _prepare_official_summary() -> dict[str, float]:
    if not SUMMARY_IN.exists():
        return {}
    data = _read_csv(SUMMARY_IN)
    if "arm" in data.columns:
        data = data[data["arm"].eq("A_official_stage847_c9_15w")].copy()
    if data.empty:
        return {}
    row = data.iloc[0]
    keys = [
        "nonzero_daily_win_rate_pct",
        "total_trade_count",
        "stop_retry_event_count",
        "broker10_cap_event_count",
        "closed_trade_rows",
    ]
    return {key: float(pd.to_numeric(row.get(key), errors="coerce")) for key in keys if key in row.index}


def _prepare_features() -> pd.DataFrame:
    data = _read_csv(FEATURES_IN)
    required = [
        "lot_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        "risk_amount",
        "volume",
        "size",
        "stop_distance",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
    ]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise RuntimeError(f"Stage016 features missing columns: {missing}")

    data["entry_day"] = data["entry_date"].map(_normalize_day)
    data["exit_day"] = data["exit_date"].map(_normalize_day)
    for column in [
        "realized_pnl",
        "risk_amount",
        "volume",
        "size",
        "stop_distance",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
        "active_positions_before",
        "portfolio_drawdown_pct",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        else:
            data[column] = np.nan

    data["risk_base"] = pd.to_numeric(data["risk_amount"], errors="coerce").abs()
    fallback = (
        pd.to_numeric(data["volume"], errors="coerce").abs()
        * pd.to_numeric(data["size"], errors="coerce").abs()
        * pd.to_numeric(data["stop_distance"], errors="coerce").abs()
    )
    data.loc[~np.isfinite(data["risk_base"]) | (data["risk_base"] <= 0), "risk_base"] = fallback
    data.loc[~np.isfinite(data["risk_base"]) | (data["risk_base"] <= 0), "risk_base"] = 1.0

    corr = data["same_direction_correlation_max_corr"].fillna(0.0)
    active_count = data["same_direction_correlation_active_count"].fillna(0.0)
    gate_weight = pd.Series(1.0, index=data.index, dtype="float64")
    mask = (active_count >= 1.0) & (corr > CORR_GATE_START)
    scaled = 1.0 - (corr - CORR_GATE_START) / (CORR_GATE_FULL - CORR_GATE_START) * (1.0 - CORR_GATE_FLOOR_WEIGHT)
    gate_weight.loc[mask] = scaled.loc[mask].clip(lower=CORR_GATE_FLOOR_WEIGHT, upper=1.0)
    data["corr_gate_weight"] = gate_weight
    data["corr_gate_applied"] = mask
    data["corr_ge_075_active_ge1"] = (active_count >= 1.0) & (corr >= 0.75)
    data["corr_ge_060_active_ge1"] = (active_count >= 1.0) & (corr >= 0.60)
    data["active_ge2"] = active_count >= 2.0
    data["positive_pnl"] = data["realized_pnl"].clip(lower=0.0).fillna(0.0)
    data["negative_pnl"] = data["realized_pnl"].clip(upper=0.0).fillna(0.0)
    data["entry_year"] = pd.to_datetime(data["entry_day"], errors="coerce").dt.year
    data["exit_year"] = pd.to_datetime(data["exit_day"], errors="coerce").dt.year
    return data


def _mask_stats(data: pd.DataFrame, name: str, mask: pd.Series) -> dict[str, Any]:
    subset = data[mask.fillna(False)].copy()
    total_pos = float(data["positive_pnl"].sum())
    total_neg_abs = float(-data["negative_pnl"].sum())
    pnl = float(subset["realized_pnl"].sum()) if not subset.empty else 0.0
    pos = float(subset["positive_pnl"].sum()) if not subset.empty else 0.0
    neg = float(subset["negative_pnl"].sum()) if not subset.empty else 0.0
    return {
        "bucket": name,
        "lot_count": int(len(subset)),
        "product_count": int(subset["product"].nunique()) if not subset.empty else 0,
        "year_count": int(subset["entry_year"].nunique()) if not subset.empty else 0,
        "net_pnl": pnl,
        "positive_pnl": pos,
        "negative_pnl": neg,
        "positive_coverage_pct": pos / total_pos * 100.0 if total_pos > 0 else np.nan,
        "negative_abs_coverage_pct": -neg / total_neg_abs * 100.0 if total_neg_abs > 0 else np.nan,
        "positive_years": int((subset.groupby("entry_year")["realized_pnl"].sum() > 0).sum())
        if not subset.empty
        else 0,
        "negative_years": int((subset.groupby("entry_year")["realized_pnl"].sum() < 0).sum())
        if not subset.empty
        else 0,
        "mean_max_corr": float(subset["same_direction_correlation_max_corr"].mean()) if not subset.empty else np.nan,
        "median_max_corr": float(subset["same_direction_correlation_max_corr"].median()) if not subset.empty else np.nan,
        "mean_active_count": float(subset["same_direction_correlation_active_count"].mean()) if not subset.empty else np.nan,
        "mean_gate_weight": float(subset["corr_gate_weight"].mean()) if not subset.empty else np.nan,
    }


def _closed_lot_attribution(features: pd.DataFrame) -> pd.DataFrame:
    masks = [
        ("all_closed_lots", pd.Series(True, index=features.index)),
        ("corr_gate_applied_060_080_floor50", features["corr_gate_applied"]),
        ("corr_ge_075_active_ge1", features["corr_ge_075_active_ge1"]),
        ("corr_ge_060_active_ge1", features["corr_ge_060_active_ge1"]),
        ("active_ge2", features["active_ge2"]),
        ("not_corr_gate_applied", ~features["corr_gate_applied"]),
    ]
    return pd.DataFrame([_mask_stats(features, name, mask) for name, mask in masks])


def _daily_weights(official: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    valid = features.dropna(subset=["entry_day", "exit_day"]).copy()
    rows: list[dict[str, Any]] = []
    for date in official["date"]:
        day = pd.Timestamp(date).normalize()
        active = valid[(valid["entry_day"] <= day) & (valid["exit_day"] >= day)].copy()
        if active.empty:
            rows.append(
                {
                    "date": day,
                    "active_lot_count": 0,
                    "active_risk_base": 0.0,
                    "corr_gate_active_risk_share": 0.0,
                    "corr075_active_risk_share": 0.0,
                    "daily_corr_gate_weight": 1.0,
                    "mean_active_max_corr": 0.0,
                    "max_active_max_corr": 0.0,
                }
            )
            continue
        risk = pd.to_numeric(active["risk_base"], errors="coerce").fillna(0.0).clip(lower=0.0)
        total_risk = float(risk.sum())
        if total_risk <= 1e-12:
            total_risk = 1.0
            risk = pd.Series(1.0, index=active.index)
        gate_share = float(risk[active["corr_gate_applied"].fillna(False)].sum() / total_risk)
        corr075_share = float(risk[active["corr_ge_075_active_ge1"].fillna(False)].sum() / total_risk)
        weighted_gate = float((risk * active["corr_gate_weight"].fillna(1.0)).sum() / total_risk)
        rows.append(
            {
                "date": day,
                "active_lot_count": int(len(active)),
                "active_risk_base": float(total_risk),
                "corr_gate_active_risk_share": gate_share,
                "corr075_active_risk_share": corr075_share,
                "daily_corr_gate_weight": float(np.clip(weighted_gate, CORR_GATE_FLOOR_WEIGHT, 1.0)),
                "mean_active_max_corr": float(
                    pd.to_numeric(active["same_direction_correlation_max_corr"], errors="coerce")
                    .fillna(0.0)
                    .mean()
                ),
                "max_active_max_corr": float(
                    pd.to_numeric(active["same_direction_correlation_max_corr"], errors="coerce")
                    .fillna(0.0)
                    .max()
                ),
            }
        )
    return pd.DataFrame(rows)


def _build_curves(official: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    base = official.merge(weights, on="date", how="left")
    base["daily_corr_gate_weight"] = base["daily_corr_gate_weight"].fillna(1.0)
    base["corr_gate_active_risk_share"] = base["corr_gate_active_risk_share"].fillna(0.0)
    curves: list[pd.DataFrame] = []

    official_curve = base.copy()
    official_curve["variant"] = VARIANT_OFFICIAL
    official_curve["label"] = "Official C9/15w"
    official_curve["risk_weight"] = 1.0
    official_curve["scaled_net_pnl"] = official_curve["net_pnl"]
    official_curve["account_equity_proxy"] = official_curve["account_equity"]
    official_curve["drawdown_pct"] = official_curve["official_drawdown_pct"]
    official_curve["broker10_margin_scaled"] = official_curve["broker10_total_margin_exact"]
    official_curve["broker10_margin_to_equity_pct_proxy"] = official_curve["broker10_margin_to_equity_pct"]
    official_curve["slippage_scaled"] = official_curve["slippage"]
    curves.append(official_curve)

    proxy = base.copy()
    proxy["variant"] = VARIANT_PROXY
    proxy["label"] = "Same-direction corr crowding proxy"
    proxy["risk_weight"] = proxy["daily_corr_gate_weight"].clip(CORR_GATE_FLOOR_WEIGHT, 1.0)
    proxy["scaled_net_pnl"] = proxy["net_pnl"] * proxy["risk_weight"]
    proxy["account_equity_proxy"] = CAPITAL + proxy["scaled_net_pnl"].cumsum()
    proxy["drawdown_pct"] = _drawdown_pct(proxy["account_equity_proxy"]).to_numpy()
    proxy["broker10_margin_scaled"] = proxy["broker10_total_margin_exact"] * proxy["risk_weight"]
    proxy["broker10_margin_to_equity_pct_proxy"] = (
        proxy["broker10_margin_scaled"] / proxy["account_equity_proxy"].replace(0.0, np.nan) * 100.0
    ).replace([np.inf, -np.inf], np.nan)
    proxy["slippage_scaled"] = proxy["slippage"] * proxy["risk_weight"]
    curves.append(proxy)

    columns = [
        "date",
        "variant",
        "label",
        "risk_weight",
        "scaled_net_pnl",
        "account_equity_proxy",
        "drawdown_pct",
        "broker10_margin_scaled",
        "broker10_margin_to_equity_pct_proxy",
        "slippage_scaled",
        "trade_count",
        "corr_gate_active_risk_share",
        "corr075_active_risk_share",
        "daily_corr_gate_weight",
        "active_lot_count",
        "active_risk_base",
        "mean_active_max_corr",
        "max_active_max_corr",
    ]
    return pd.concat([item[columns] for item in curves], ignore_index=True)


def _metrics(curves: pd.DataFrame, official_summary: dict[str, float]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    official_return = np.nan
    official_dd = np.nan
    official_broker = np.nan
    official_slippage = np.nan
    for variant, group in curves.groupby("variant", sort=False):
        group = group.sort_values("date")
        equity = group["account_equity_proxy"].astype(float)
        drawdown = group["drawdown_pct"].astype(float)
        end_equity = float(equity.iloc[-1])
        total_return = (end_equity / CAPITAL - 1.0) * 100.0
        max_dd = float(drawdown.min())
        total_slippage = float(group["slippage_scaled"].sum())
        max_broker = float(group["broker10_margin_to_equity_pct_proxy"].max())
        row = {
            "variant": variant,
            "end_equity": end_equity,
            "total_return_pct": total_return,
            "return_retention_pct": np.nan,
            "max_dd_pct": max_dd,
            "dd_improvement_pp": np.nan,
            "ulcer_pct": _ulcer_pct(drawdown),
            "sharpe": _sharpe_from_equity(equity),
            "total_slippage_proxy": total_slippage,
            "total_trade_count_reference": official_summary.get("total_trade_count", float(group["trade_count"].sum())),
            "win_rate_reference_pct": official_summary.get("nonzero_daily_win_rate_pct", np.nan),
            "max_broker10_margin_to_equity_pct": max_broker,
            "days_over_100pct": int((group["broker10_margin_to_equity_pct_proxy"] > 100.0).sum()),
            "days_over_90pct": int((group["broker10_margin_to_equity_pct_proxy"] > 90.0).sum()),
            "avg_risk_weight": float(group["risk_weight"].mean()),
            "min_risk_weight": float(group["risk_weight"].min()),
            "days_weight_lt_1": int((group["risk_weight"] < 0.999999).sum()),
            "avg_corr_gate_active_risk_share": float(group["corr_gate_active_risk_share"].mean()),
            "max_corr_gate_active_risk_share": float(group["corr_gate_active_risk_share"].max()),
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_live_alias": OFFICIAL_LIVE_ALIAS,
        }
        if variant == VARIANT_OFFICIAL:
            official_return = total_return
            official_dd = max_dd
            official_broker = max_broker
            official_slippage = total_slippage
        rows.append(row)

    metrics = pd.DataFrame(rows)
    if np.isfinite(official_return) and abs(official_return) > 1e-12:
        metrics["return_retention_pct"] = metrics["total_return_pct"] / official_return * 100.0
    if np.isfinite(official_dd):
        metrics["dd_improvement_pp"] = metrics["max_dd_pct"] - official_dd
        metrics["dd_improvement_positive_pp"] = metrics["dd_improvement_pp"]
    if np.isfinite(official_broker):
        metrics["broker10_improvement_pp"] = official_broker - metrics["max_broker10_margin_to_equity_pct"]
    if np.isfinite(official_slippage):
        metrics["slippage_delta_vs_official"] = metrics["total_slippage_proxy"] - official_slippage
    return metrics


def _year_stats(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["year"] = pd.to_datetime(data["date"]).dt.year
    rows: list[dict[str, Any]] = []
    for (variant, year), group in data.groupby(["variant", "year"]):
        group = group.sort_values("date")
        start = float(group["account_equity_proxy"].iloc[0] - group["scaled_net_pnl"].iloc[0])
        if not np.isfinite(start) or start <= 0:
            start = float(group["account_equity_proxy"].iloc[0])
        end = float(group["account_equity_proxy"].iloc[-1])
        rows.append(
            {
                "variant": variant,
                "year": int(year),
                "start_equity_reference": start,
                "end_equity": end,
                "year_return_pct": (end / start - 1.0) * 100.0 if start > 0 else np.nan,
                "year_max_dd_pct": float(group["drawdown_pct"].min()),
                "year_avg_risk_weight": float(group["risk_weight"].mean()),
                "year_min_risk_weight": float(group["risk_weight"].min()),
                "year_days_weight_lt_1": int((group["risk_weight"] < 0.999999).sum()),
                "year_avg_corr_gate_active_risk_share": float(group["corr_gate_active_risk_share"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _contribution_curve(features: pd.DataFrame) -> pd.DataFrame:
    data = features.dropna(subset=["exit_day"]).sort_values(["exit_day", "lot_id"]).copy()
    data["all_pnl"] = data["realized_pnl"].fillna(0.0)
    data["corr_gate_pnl"] = np.where(data["corr_gate_applied"], data["realized_pnl"].fillna(0.0), 0.0)
    data["not_corr_gate_pnl"] = np.where(~data["corr_gate_applied"], data["realized_pnl"].fillna(0.0), 0.0)
    return pd.DataFrame(
        {
            "exit_day": data["exit_day"],
            "lot_id": data["lot_id"],
            "cum_all_pnl": data["all_pnl"].cumsum(),
            "cum_corr_gate_pnl": data["corr_gate_pnl"].cumsum(),
            "cum_not_corr_gate_pnl": data["not_corr_gate_pnl"].cumsum(),
        }
    )


def _plot_path_chart(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    colors = {VARIANT_OFFICIAL: "#1f77b4", VARIANT_PROXY: "#d62728"}
    labels = {VARIANT_OFFICIAL: "Official", VARIANT_PROXY: "Corr crowding proxy"}
    for variant, group in curves.groupby("variant", sort=False):
        group = group.sort_values("date")
        color = colors.get(variant, None)
        axes[0].plot(group["date"], group["account_equity_proxy"], label=labels.get(variant, variant), color=color)
        axes[1].plot(group["date"], group["drawdown_pct"], label=labels.get(variant, variant), color=color)
        axes[2].plot(
            group["date"],
            group["broker10_margin_to_equity_pct_proxy"],
            label=labels.get(variant, variant),
            color=color,
        )
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity log")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    axes[2].axhline(100.0, color="black", linewidth=0.8, linestyle="--")
    axes[0].legend(loc="best")
    axes[0].set_title("Stage021 same-direction correlation crowding proxy")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_weight_chart(weights: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    axes[0].plot(weights["date"], weights["daily_corr_gate_weight"], color="#d62728", label="daily corr gate weight")
    axes[0].set_ylabel("risk weight")
    axes[0].set_ylim(0.45, 1.05)
    axes[0].legend(loc="best")

    axes[1].plot(
        weights["date"],
        weights["corr_gate_active_risk_share"] * 100.0,
        color="#9467bd",
        label="corr gate active risk share",
    )
    axes[1].plot(
        weights["date"],
        weights["corr075_active_risk_share"] * 100.0,
        color="#8c564b",
        alpha=0.8,
        label="corr>=0.75 active risk share",
    )
    axes[1].set_ylabel("active share %")
    axes[1].legend(loc="best")

    axes[2].plot(weights["date"], weights["active_lot_count"], color="#2ca02c", label="active lots")
    axes[2].set_ylabel("active lots")
    axes[2].legend(loc="best")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(WEIGHT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contribution_chart(features: pd.DataFrame) -> None:
    curve = _contribution_curve(features)
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(curve["exit_day"], curve["cum_all_pnl"], label="all closed lots", color="#1f77b4")
    ax.plot(curve["exit_day"], curve["cum_corr_gate_pnl"], label="corr gate applied", color="#d62728")
    ax.plot(curve["exit_day"], curve["cum_not_corr_gate_pnl"], label="not corr gate", color="#2ca02c")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_title("Closed-lot contribution by entry-time same-direction correlation state")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    data = features.copy()
    x = data["same_direction_correlation_max_corr"].fillna(0.0)
    y = data["realized_pnl"].fillna(0.0)
    colors = np.where(data["corr_gate_applied"], "#d62728", "#1f77b4")
    sizes = np.clip(data["risk_base"].fillna(1.0) / data["risk_base"].median(), 0.5, 8.0) * 18.0
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.scatter(x, y, c=colors, s=sizes, alpha=0.62, edgecolors="none")
    ax.axvline(CORR_GATE_START, color="black", linestyle="--", linewidth=0.8)
    ax.axvline(CORR_GATE_FULL, color="black", linestyle=":", linewidth=0.8)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("entry-time same-direction max corr")
    ax.set_ylabel("closed-lot realized PnL")
    ax.set_title("PnL vs same-direction correlation state")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(SCATTER_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_year_heatmap(year_stats: pd.DataFrame) -> None:
    pivot = year_stats.pivot_table(index="variant", columns="year", values="year_return_pct", aggfunc="first")
    if pivot.empty:
        return
    fig, ax = plt.subplots(figsize=(13, 3.8))
    values = pivot.to_numpy(dtype=float)
    max_abs = np.nanmax(np.abs(values)) if np.isfinite(values).any() else 1.0
    image = ax.imshow(values, cmap="RdYlGn", aspect="auto", vmin=-max_abs, vmax=max_abs)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(year)) for year in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values[i, j]
            if np.isfinite(value):
                ax.text(j, i, f"{value:.0f}%", ha="center", va="center", fontsize=8)
    ax.set_title("Year return heatmap")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    features: pd.DataFrame,
    attribution: pd.DataFrame,
    weights: pd.DataFrame,
    metrics: pd.DataFrame,
    year_stats: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    proxy_row = metrics[metrics["variant"].eq(VARIANT_PROXY)].iloc[0].to_dict()
    top_corr = (
        features[features["corr_gate_applied"]]
        .sort_values("realized_pnl")
        [
            [
                "lot_id",
                "vt_symbol",
                "direction",
                "entry_date",
                "exit_date",
                "realized_pnl",
                "same_direction_correlation_max_corr",
                "same_direction_correlation_active_count",
                "corr_gate_weight",
            ]
        ]
        .head(12)
    )
    weight_summary = pd.DataFrame(
        [
            {
                "days": int(len(weights)),
                "days_weight_lt_1": int((weights["daily_corr_gate_weight"] < 0.999999).sum()),
                "avg_daily_weight": float(weights["daily_corr_gate_weight"].mean()),
                "min_daily_weight": float(weights["daily_corr_gate_weight"].min()),
                "avg_corr_gate_active_share_pct": float(weights["corr_gate_active_risk_share"].mean() * 100.0),
                "max_corr_gate_active_share_pct": float(weights["corr_gate_active_risk_share"].max() * 100.0),
            }
        ]
    )
    lines = [
        f"# {STAGE} same-direction correlation crowding proxy",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- official_live_version: `{OFFICIAL_LIVE_VERSION}`",
        f"- official_live_alias: `{OFFICIAL_LIVE_ALIAS}`",
        f"- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        "- boundary: read-only daily active-risk proxy; candidate_ready=0; no CTP/order API.",
        "",
        "## Frozen Hypothesis",
        "",
        (
            f"When an entry occurs while same-direction active positions already exist and "
            f"`same_direction_correlation_max_corr` is above `{CORR_GATE_START:.2f}`, "
            f"the active risk is progressively discounted until `{CORR_GATE_FULL:.2f}`, "
            f"with a floor weight of `{CORR_GATE_FLOOR_WEIGHT:.2f}`. This is a proxy only."
        ),
        "",
        "## Metrics",
        "",
        _md_table(
            metrics[
                [
                    "variant",
                    "end_equity",
                    "total_return_pct",
                    "return_retention_pct",
                    "max_dd_pct",
                    "dd_improvement_positive_pp",
                    "sharpe",
                    "total_slippage_proxy",
                    "total_trade_count_reference",
                    "win_rate_reference_pct",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_weight_lt_1",
                    "avg_risk_weight",
                ]
            ]
        ),
        "",
        "## Closed-Lot Attribution",
        "",
        _md_table(
            attribution[
                [
                    "bucket",
                    "lot_count",
                    "product_count",
                    "year_count",
                    "net_pnl",
                    "positive_coverage_pct",
                    "negative_abs_coverage_pct",
                    "positive_years",
                    "negative_years",
                    "mean_max_corr",
                    "mean_gate_weight",
                ]
            ]
        ),
        "",
        "## Daily Weight Summary",
        "",
        _md_table(weight_summary),
        "",
        "## Worst Corr-Gate Closed Lots",
        "",
        _md_table(top_corr, max_rows=12),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- candidate_ready: `{int(decision['candidate_ready'])}`",
        f"- return_retention_pct: `{proxy_row['return_retention_pct']:.4f}`",
        f"- dd_improvement_positive_pp: `{proxy_row['dd_improvement_positive_pp']:.4f}`",
        f"- days_weight_lt_1: `{int(proxy_row['days_weight_lt_1'])}`",
        "",
        "## Visual Outputs",
        "",
        f"- path/drawdown/broker10: `{PATH_CHART_OUT}`",
        f"- daily risk weight/share: `{WEIGHT_CHART_OUT}`",
        f"- closed-lot contribution: `{CONTRIBUTION_CHART_OUT}`",
        f"- corr/PnL scatter: `{SCATTER_CHART_OUT}`",
        f"- year heatmap: `{YEAR_HEATMAP_OUT}`",
        "",
        "## Files",
        "",
        f"- features: `{FEATURES_OUT}`",
        f"- closed-lot attribution: `{ATTRIBUTION_OUT}`",
        f"- daily weights: `{DAILY_WEIGHTS_OUT}`",
        f"- curves: `{CURVES_OUT}`",
        f"- metrics: `{METRICS_OUT}`",
        f"- year_stats: `{YEAR_STATS_OUT}`",
        f"- decision: `{DECISION_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    official = _prepare_official_curve()
    official_summary = _prepare_official_summary()
    features = _prepare_features()
    attribution = _closed_lot_attribution(features)
    weights = _daily_weights(official, features)
    curves = _build_curves(official, weights)
    metrics = _metrics(curves, official_summary)
    year_stats = _year_stats(curves)

    proxy = metrics[metrics["variant"].eq(VARIANT_PROXY)].iloc[0]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "candidate_ready": False,
        "ab_experiment_triggered": False,
        "boundary": "read_only_daily_active_risk_proxy_not_true_engine",
        "decision": "stage021_corr_crowding_proxy_no_candidate_insufficient_explanatory_power",
        "reason": (
            "The same-direction correlation crowding state is pre-observable and low-freedom, "
            "but the affected sample is too small to deliver the target drawdown reduction while "
            "retaining 80%+ return in a true-engine-ready way."
        ),
        "corr_gate_start": CORR_GATE_START,
        "corr_gate_full": CORR_GATE_FULL,
        "corr_gate_floor_weight": CORR_GATE_FLOOR_WEIGHT,
        "proxy_metrics": proxy.to_dict(),
        "corr_gate_lot_count": int(features["corr_gate_applied"].sum()),
        "corr_gate_net_pnl": float(features.loc[features["corr_gate_applied"], "realized_pnl"].sum()),
        "days_weight_lt_1": int((weights["daily_corr_gate_weight"] < 0.999999).sum()),
        "max_corr_gate_active_risk_share": float(weights["corr_gate_active_risk_share"].max()),
        "inputs": {
            "features": FEATURES_IN,
            "official_curve": CURVE_IN,
            "official_summary": SUMMARY_IN,
        },
        "outputs": {
            "report": REPORT_OUT,
            "metrics": METRICS_OUT,
            "curves": CURVES_OUT,
            "daily_weights": DAILY_WEIGHTS_OUT,
            "path_chart": PATH_CHART_OUT,
            "weight_chart": WEIGHT_CHART_OUT,
            "contribution_chart": CONTRIBUTION_CHART_OUT,
            "scatter_chart": SCATTER_CHART_OUT,
            "year_heatmap": YEAR_HEATMAP_OUT,
        },
    }

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    attribution.to_csv(ATTRIBUTION_OUT, index=False, encoding="utf-8-sig")
    weights.to_csv(DAILY_WEIGHTS_OUT, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_OUT, index=False, encoding="utf-8-sig")
    metrics.to_csv(METRICS_OUT, index=False, encoding="utf-8-sig")
    year_stats.to_csv(YEAR_STATS_OUT, index=False, encoding="utf-8-sig")
    summary = pd.DataFrame([_json_safe(decision)])
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_path_chart(curves)
    _plot_weight_chart(weights)
    _plot_contribution_chart(features)
    _plot_scatter(features)
    _plot_year_heatmap(year_stats)
    _write_report(features, attribution, weights, metrics, year_stats, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

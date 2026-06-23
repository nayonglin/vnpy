from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage053"
MODEL_TAG = "stage053_external_source_priority_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage053_c9_minrisk_external_source_priority_audit"

OFFICIAL_ARM = "A_official_stage847_c9_15w"
INITIAL_CAPITAL = 150_000.0

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage053_external_source_priority_audit"

STAGE046_DIR = LINE_DIR / "outputs" / "stage046_entry_day_confirmed_breakeven_true_engine"
OFFICIAL_CURVE_IN = (
    STAGE046_DIR
    / "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_curve_"
    "stage046_entry_day_confirmed_breakeven_true_engine_v1.csv"
)

ROUTE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_summary_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
YEAR_COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_coverage_{MODEL_TAG}.csv"
UPPER_BOUND_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_posthoc_upper_bound_curves_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_posthoc_upper_bound_path_chart_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_coverage_gap_chart_{MODEL_TAG}.png"
FRONTIER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_priority_frontier_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ready_year_heatmap_{MODEL_TAG}.png"
BUCKET_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_best_negative_bucket_fragility_{MODEL_TAG}.png"


@dataclass(frozen=True)
class SourceSpec:
    key: str
    stage: str
    label: str
    feature_path: Path
    ready_col: str
    bucket_col: str
    missing_bucket: str
    economic_prior: str
    next_data_action: str


SOURCE_SPECS = [
    SourceSpec(
        key="market_breadth",
        stage="Stage025",
        label="market divergence / breadth",
        feature_path=LINE_DIR
        / "outputs"
        / "stage025_market_divergence_breadth_forensics"
        / "qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_features_"
        "stage025_market_divergence_breadth_forensics_v1.csv",
        ready_col="market_state_missing_stage025",
        bucket_col="broad_market_state_stage025",
        missing_bucket="market_state_missing",
        economic_prior="medium: cross-market trend breadth can describe regime, but Stage025 was nonmonotonic",
        next_data_action="do not trade; only keep as regime context unless paired with a new independent source",
    ),
    SourceSpec(
        key="term_structure",
        stage="Stage026",
        label="term structure carry alignment",
        feature_path=LINE_DIR
        / "outputs"
        / "stage026_term_structure_carry_alignment_forensics"
        / "qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics_features_"
        "stage026_term_structure_carry_alignment_forensics_v1.csv",
        ready_col="curve_state_missing_stage026",
        bucket_col="carry_combo_bucket_stage026",
        missing_bucket="curve_missing",
        economic_prior="medium-high: carry has commodity risk-premium basis, but Stage026 adverse buckets were right-tail",
        next_data_action="do not trade; only revisit with more direct inventory/positioning evidence",
    ),
    SourceSpec(
        key="supply_inventory",
        stage="Stage027",
        label="basis / warehouse supply demand",
        feature_path=LINE_DIR
        / "outputs"
        / "stage027_supply_demand_inventory_forensics"
        / "qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics_features_"
        "stage027_supply_demand_inventory_forensics_v1.csv",
        ready_col="supply_signal_missing_stage027",
        bucket_col="supply_bucket_stage027",
        missing_bucket="supply_missing",
        economic_prior="high: warehouse receipts and basis are direct physical-market state, but current coarse score failed",
        next_data_action="repair official warehouse / receipt source granularity before any rule",
    ),
    SourceSpec(
        key="member_rank",
        stage="Stage028/029",
        label="member position rank structure",
        feature_path=LINE_DIR
        / "outputs"
        / "stage028_member_rank_position_forensics"
        / "qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_features_"
        "stage028_member_rank_position_forensics_v1.csv",
        ready_col="member_feature_ready_stage028",
        bucket_col="member_bucket_stage028",
        missing_bucket="member_missing",
        economic_prior="high: position ranks are closest to risk absorption, but current history coverage is too low",
        next_data_action="fix DCE/CZCE/SHFE/GFEX historical selectors and PIT backfill before alpha use",
    ),
    SourceSpec(
        key="product_trend_stage496",
        stage="Stage052",
        label="Stage496 product trend t-stat",
        feature_path=LINE_DIR
        / "outputs"
        / "stage052_product_trend_tstat_stage496_reaudit"
        / "qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit_features_"
        "stage052_product_trend_tstat_stage496_reaudit_v1.csv",
        ready_col="trend_ready_stage052",
        bucket_col="stage052_trend_bucket",
        missing_bucket="trend_missing",
        economic_prior="medium: trend significance is robust literature, but Stage052 target was right-tail",
        next_data_action="close trading route; only fill 2018-2019/forward coverage for monitoring",
    ),
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
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


def _bool_series(series: pd.Series, *, missing_col_semantics: bool = False) -> pd.Series:
    if series.dtype == bool:
        out = series.copy()
    else:
        text = series.astype(str).str.lower().str.strip()
        out = text.isin(["true", "1", "1.0", "yes"])
        out = out.mask(text.isin(["false", "0", "0.0", "no"]), False)
    return ~out if missing_col_semantics else out


def _normalize_product(vt_symbol: Any, fallback: Any = "") -> str:
    symbol = "" if pd.isna(vt_symbol) else str(vt_symbol)
    if "." in symbol:
        code, exchange = symbol.split(".", 1)
        match = re.match(r"^([A-Za-z]+)", code)
        if match:
            return f"{match.group(1)}.{exchange}"
    raw = "" if pd.isna(fallback) else str(fallback)
    if "." in raw:
        return raw
    match = re.match(r"^([A-Za-z]+)", raw)
    if match:
        return match.group(1)
    return raw or "UNKNOWN"


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


def _fmt(value: Any, digits: int = 4) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NA"
    if not np.isfinite(number):
        return "NA"
    return f"{number:.{digits}f}"


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve = curve[curve["arm"].eq(OFFICIAL_ARM)].copy()
    if curve.empty:
        raise RuntimeError(f"official curve arm is empty: {OFFICIAL_ARM}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    return curve.sort_values("date").reset_index(drop=True)


def _equity_metrics(equity: pd.Series, date: pd.Series | None = None) -> dict[str, float | str]:
    equity = equity.astype(float).reset_index(drop=True)
    running_max = equity.cummax()
    drawdown_pct = (equity / running_max - 1.0) * 100.0
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    ret_std = returns.std(ddof=0)
    sharpe = float(returns.mean() / ret_std * np.sqrt(252.0)) if ret_std and ret_std > 0 else np.nan
    trough_idx = int(drawdown_pct.idxmin())
    metrics: dict[str, float | str] = {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(drawdown_pct.min()),
        "sharpe": sharpe,
    }
    if date is not None:
        dates = pd.to_datetime(date).reset_index(drop=True)
        metrics["max_dd_date"] = dates.iloc[trough_idx].strftime("%Y-%m-%d")
    return metrics


def _prepare_features(spec: SourceSpec) -> pd.DataFrame:
    frame = _read_csv(spec.feature_path)
    required = {"lot_id", "vt_symbol", "entry_date", "exit_date", "realized_pnl", spec.ready_col, spec.bucket_col}
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"{spec.key} missing columns: {sorted(missing)}")
    frame = frame.copy()
    frame["source_key"] = spec.key
    frame["source_label"] = spec.label
    frame["source_stage"] = spec.stage
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce")
    frame["exit_date"] = pd.to_datetime(frame["exit_date"], errors="coerce")
    frame["exit_day"] = frame["exit_date"].dt.normalize()
    frame["entry_year"] = frame["entry_date"].dt.year.astype("Int64")
    frame["exit_year"] = frame["exit_date"].dt.year.astype("Int64")
    frame["realized_pnl"] = pd.to_numeric(frame["realized_pnl"], errors="coerce").fillna(0.0)
    if "normalized_product" not in frame.columns:
        fallback = frame["product_key"] if "product_key" in frame.columns else ""
        frame["normalized_product"] = [
            _normalize_product(vt_symbol, raw) for vt_symbol, raw in zip(frame["vt_symbol"], fallback)
        ]
    if spec.ready_col.endswith("missing_stage025") or spec.ready_col.endswith("missing_stage026") or spec.ready_col.endswith(
        "missing_stage027"
    ):
        frame["source_ready"] = _bool_series(frame[spec.ready_col], missing_col_semantics=True)
    else:
        frame["source_ready"] = _bool_series(frame[spec.ready_col])
    frame["source_bucket"] = frame[spec.bucket_col].fillna(spec.missing_bucket).astype(str)
    frame.loc[~frame["source_ready"], "source_bucket"] = spec.missing_bucket
    return frame


def _source_bucket_summary(features: pd.DataFrame) -> pd.DataFrame:
    total_positive = float(features["realized_pnl"].clip(lower=0).sum())
    total_negative_abs = float((-features["realized_pnl"].clip(upper=0)).sum())
    rows: list[dict[str, Any]] = []
    for (source_key, bucket), group in features.groupby(["source_key", "source_bucket"], dropna=False):
        yearly = group.groupby("exit_year")["realized_pnl"].sum()
        rows.append(
            {
                "source_key": source_key,
                "source_label": str(group["source_label"].iloc[0]),
                "source_stage": str(group["source_stage"].iloc[0]),
                "bucket": bucket,
                "lot_count": int(len(group)),
                "ready_lot_count": int(group["source_ready"].sum()),
                "product_count": int(group["normalized_product"].nunique()),
                "year_count": int(group["exit_year"].nunique()),
                "net_pnl": float(group["realized_pnl"].sum()),
                "positive_pnl": float(group["realized_pnl"].clip(lower=0).sum()),
                "negative_pnl_abs": float((-group["realized_pnl"].clip(upper=0)).sum()),
                "positive_coverage_pct": float(group["realized_pnl"].clip(lower=0).sum() / total_positive * 100.0)
                if total_positive
                else np.nan,
                "negative_coverage_pct": float((-group["realized_pnl"].clip(upper=0)).sum() / total_negative_abs * 100.0)
                if total_negative_abs
                else np.nan,
                "positive_year_count": int((yearly > 0).sum()),
                "negative_year_count": int((yearly < 0).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["source_key", "net_pnl"]).reset_index(drop=True)


def _build_upper_curve(curve: pd.DataFrame, target: pd.DataFrame, label: str) -> pd.DataFrame:
    cashflow = (
        target.dropna(subset=["exit_day"])
        .groupby("exit_day", as_index=False)
        .agg(target_realized_pnl=("realized_pnl", "sum"), target_lot_count=("realized_pnl", "size"))
        .rename(columns={"exit_day": "date"})
    )
    upper = curve[["date", "account_equity", "drawdown_pct", "nav"]].copy()
    upper = upper.merge(cashflow, on="date", how="left")
    upper["target_realized_pnl"] = upper["target_realized_pnl"].fillna(0.0)
    upper["target_lot_count"] = upper["target_lot_count"].fillna(0).astype(int)
    upper["skipped_target_pnl_cumsum"] = upper["target_realized_pnl"].cumsum()
    upper["upper_bound_equity"] = upper["account_equity"] - upper["skipped_target_pnl_cumsum"]
    upper["upper_bound_drawdown_pct"] = (
        upper["upper_bound_equity"] / upper["upper_bound_equity"].cummax() - 1.0
    ) * 100.0
    upper["curve_label"] = label
    return upper


def _fragility(group: pd.DataFrame) -> dict[str, Any]:
    if group.empty:
        return {
            "leave_worst_year_remaining_pnl": np.nan,
            "leave_worst_product_remaining_pnl": np.nan,
            "worst_year": "",
            "worst_product": "",
        }
    total = float(group["realized_pnl"].sum())
    by_year = group.groupby("exit_year")["realized_pnl"].sum().sort_values()
    by_product = group.groupby("normalized_product")["realized_pnl"].sum().sort_values()
    worst_year = by_year.index[0] if len(by_year) else ""
    worst_product = by_product.index[0] if len(by_product) else ""
    return {
        "leave_worst_year_remaining_pnl": float(total - by_year.iloc[0]) if len(by_year) else np.nan,
        "leave_worst_product_remaining_pnl": float(total - by_product.iloc[0]) if len(by_product) else np.nan,
        "worst_year": "" if pd.isna(worst_year) else str(worst_year),
        "worst_product": "" if pd.isna(worst_product) else str(worst_product),
    }


def _official_metrics(curve: pd.DataFrame) -> dict[str, Any]:
    metrics = _equity_metrics(curve["account_equity"], curve["date"])
    nonzero = curve[curve["net_pnl"].ne(0)]
    metrics.update(
        {
            "total_slippage": float(curve["slippage"].sum()),
            "total_trade_count": float(curve["trade_count"].sum()),
            "win_rate_pct": float((nonzero["net_pnl"] > 0).mean() * 100.0) if len(nonzero) else np.nan,
            "broker10_peak_pct": float(curve["broker10_margin_to_equity_pct"].max()),
        }
    )
    return metrics


def _route_summary(
    specs: list[SourceSpec],
    all_features: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    curve: pd.DataFrame,
    official: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    curve_rows: list[pd.DataFrame] = []
    for spec in specs:
        features = all_features[all_features["source_key"].eq(spec.key)].copy()
        ready = features[features["source_ready"]].copy()
        missing = features[~features["source_ready"]].copy()
        ready_buckets = bucket_summary[
            bucket_summary["source_key"].eq(spec.key) & ~bucket_summary["bucket"].eq(spec.missing_bucket)
        ].copy()
        if ready_buckets.empty:
            best_bucket = ""
            best_bucket_pnl = np.nan
            target = ready.iloc[0:0].copy()
        else:
            best = ready_buckets.sort_values("net_pnl").iloc[0]
            best_bucket = str(best["bucket"])
            best_bucket_pnl = float(best["net_pnl"])
            target = features[features["source_bucket"].eq(best_bucket)].copy()
        upper_curve = _build_upper_curve(curve, target, f"{spec.key}:{best_bucket}")
        upper_metrics = _equity_metrics(upper_curve["upper_bound_equity"], upper_curve["date"])
        curve_rows.append(upper_curve)
        fragility = _fragility(target)
        ready_pct = float(len(ready) / len(features) * 100.0) if len(features) else np.nan
        missing_net_pnl = float(missing["realized_pnl"].sum())
        target_years = int(target["exit_year"].nunique()) if len(target) else 0
        target_products = int(target["normalized_product"].nunique()) if len(target) else 0
        dd_improvement_pp = float(upper_metrics["max_dd_pct"] - official["max_dd_pct"])
        return_retention_pct = float(upper_metrics["total_return_pct"] / official["total_return_pct"] * 100.0)
        posthoc_candidate_like = bool(
            best_bucket_pnl < 0
            and len(target) >= 20
            and target_years >= 4
            and target_products >= 8
            and dd_improvement_pp >= 3.0
            and return_retention_pct >= 80.0
            and fragility["leave_worst_year_remaining_pnl"] < 0
            and fragility["leave_worst_product_remaining_pnl"] < 0
        )
        if spec.key == "member_rank":
            data_priority = "highest_data_engineering_priority"
        elif spec.key == "supply_inventory":
            data_priority = "medium_official_source_granularity_priority"
        elif spec.key == "product_trend_stage496":
            data_priority = "monitor_only_after_2018_2019_fill"
        else:
            data_priority = "low_research_priority_without_new_information"
        rows.append(
            {
                "source_key": spec.key,
                "source_stage": spec.stage,
                "source_label": spec.label,
                "economic_prior": spec.economic_prior,
                "next_data_action": spec.next_data_action,
                "data_priority": data_priority,
                "lot_count": int(len(features)),
                "ready_lot_count": int(len(ready)),
                "ready_pct": ready_pct,
                "missing_lot_count": int(len(missing)),
                "missing_net_pnl": missing_net_pnl,
                "ready_net_pnl": float(ready["realized_pnl"].sum()),
                "ready_product_count": int(ready["normalized_product"].nunique()),
                "ready_year_count": int(ready["exit_year"].nunique()),
                "posthoc_best_negative_bucket": best_bucket,
                "posthoc_best_negative_bucket_net_pnl": best_bucket_pnl,
                "posthoc_best_negative_bucket_lot_count": int(len(target)),
                "posthoc_best_negative_bucket_product_count": target_products,
                "posthoc_best_negative_bucket_year_count": target_years,
                "leave_worst_year_remaining_pnl": fragility["leave_worst_year_remaining_pnl"],
                "leave_worst_product_remaining_pnl": fragility["leave_worst_product_remaining_pnl"],
                "worst_year": fragility["worst_year"],
                "worst_product": fragility["worst_product"],
                "upper_bound_end_equity": upper_metrics["end_equity"],
                "upper_bound_total_return_pct": upper_metrics["total_return_pct"],
                "upper_bound_max_dd_pct": upper_metrics["max_dd_pct"],
                "upper_bound_max_dd_date": upper_metrics.get("max_dd_date"),
                "upper_bound_sharpe": upper_metrics["sharpe"],
                "upper_bound_dd_improvement_pp": dd_improvement_pp,
                "upper_bound_return_retention_pct": return_retention_pct,
                "posthoc_candidate_like": posthoc_candidate_like,
            }
        )
    return pd.DataFrame(rows), pd.concat(curve_rows, ignore_index=True)


def _year_coverage(all_features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (source_key, year), group in all_features.groupby(["source_key", "entry_year"], dropna=False):
        rows.append(
            {
                "source_key": source_key,
                "entry_year": int(year) if not pd.isna(year) else -1,
                "lot_count": int(len(group)),
                "ready_lot_count": int(group["source_ready"].sum()),
                "ready_pct": float(group["source_ready"].mean() * 100.0),
                "missing_net_pnl": float(group.loc[~group["source_ready"], "realized_pnl"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["source_key", "entry_year"]).reset_index(drop=True)


def _write_charts(
    route_summary: pd.DataFrame,
    year_coverage: pd.DataFrame,
    upper_curves: pd.DataFrame,
    curve: pd.DataFrame,
    official: dict[str, Any],
) -> None:
    plt.rcParams.update({"figure.dpi": 130, "font.size": 9})

    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="black", linewidth=1.4, label="official equity")
    for label, group in upper_curves.groupby("curve_label"):
        key = label.split(":", 1)[0]
        if key in {"supply_inventory", "member_rank", "product_trend_stage496"}:
            axes[0].plot(group["date"], group["upper_bound_equity"], linewidth=1.1, alpha=0.85, label=label)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(
        curve["date"],
        (curve["account_equity"] / curve["account_equity"].cummax() - 1.0) * 100.0,
        color="black",
        linewidth=1.4,
        label="official DD",
    )
    for label, group in upper_curves.groupby("curve_label"):
        key = label.split(":", 1)[0]
        if key in {"supply_inventory", "member_rank", "product_trend_stage496"}:
            axes[1].plot(group["date"], group["upper_bound_drawdown_pct"], linewidth=1.1, alpha=0.85, label=label)
    axes[1].set_ylabel("drawdown %")
    axes[1].legend(loc="lower left", fontsize=8)
    axes[1].grid(True, alpha=0.25)
    fig.suptitle("Stage053 post-hoc best-negative bucket upper bounds (not deployable)")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT)
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ordered = route_summary.sort_values("ready_pct")
    x = np.arange(len(ordered))
    ax1.bar(x, ordered["ready_pct"], color="#3182bd", alpha=0.85, label="ready %")
    ax1.set_xticks(x)
    ax1.set_xticklabels(ordered["source_key"], rotation=30, ha="right")
    ax1.set_ylabel("ready %")
    ax1.set_ylim(0, 105)
    ax1.grid(True, axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.plot(x, ordered["missing_net_pnl"], color="#d94801", marker="o", label="missing net pnl")
    ax2.axhline(0.0, color="black", linewidth=0.8)
    ax2.set_ylabel("missing net pnl")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    fig.suptitle("Stage053 external source coverage and missing PnL")
    fig.tight_layout()
    fig.savefig(COVERAGE_CHART_OUT)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    sizes = np.clip(route_summary["posthoc_best_negative_bucket_lot_count"].astype(float) * 22.0, 80, 900)
    colors = route_summary["upper_bound_return_retention_pct"]
    scatter = ax.scatter(
        route_summary["ready_pct"],
        route_summary["upper_bound_dd_improvement_pp"],
        s=sizes,
        c=colors,
        cmap="viridis",
        alpha=0.75,
        edgecolor="white",
        linewidth=0.7,
    )
    for _, row in route_summary.iterrows():
        ax.annotate(str(row["source_key"]), (row["ready_pct"], row["upper_bound_dd_improvement_pp"]), fontsize=8)
    ax.axhline(5.0, color="black", linestyle="--", linewidth=0.9, label="target +5pp DD")
    ax.axvline(80.0, color="black", linestyle=":", linewidth=0.9, label="80% ready ref")
    ax.set_xlabel("source ready %")
    ax.set_ylabel("post-hoc DD improvement pp")
    ax.set_title("Coverage vs post-hoc drawdown upper bound")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right")
    fig.colorbar(scatter, ax=ax, label="return retention %")
    fig.tight_layout()
    fig.savefig(FRONTIER_CHART_OUT)
    plt.close(fig)

    matrix = year_coverage.pivot_table(index="source_key", columns="entry_year", values="ready_pct", fill_value=0.0)
    matrix = matrix.reindex(route_summary["source_key"])
    fig, ax = plt.subplots(figsize=(12, 4.5))
    image = ax.imshow(matrix.to_numpy(dtype=float), aspect="auto", cmap="Blues", vmin=0.0, vmax=100.0)
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels([str(c) for c in matrix.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_title("Source ready % by entry year")
    fig.colorbar(image, ax=ax, shrink=0.8, label="ready %")
    fig.tight_layout()
    fig.savefig(YEAR_HEATMAP_OUT)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6))
    ordered = route_summary.sort_values("posthoc_best_negative_bucket_net_pnl")
    x = np.arange(len(ordered))
    ax.bar(x, ordered["posthoc_best_negative_bucket_net_pnl"], color="#cb181d", alpha=0.75)
    ax.scatter(x, ordered["leave_worst_year_remaining_pnl"], color="#08519c", label="leave worst year")
    ax.scatter(x, ordered["leave_worst_product_remaining_pnl"], color="#238b45", label="leave worst product")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    labels = [
        f"{row.source_key}\n{row.posthoc_best_negative_bucket}"
        for row in ordered.itertuples(index=False)
    ]
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("PnL")
    ax.set_title("Post-hoc best-negative bucket fragility")
    ax.legend(loc="lower right")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(BUCKET_CHART_OUT)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    official = _official_metrics(curve)
    features = pd.concat([_prepare_features(spec) for spec in SOURCE_SPECS], ignore_index=True)
    bucket_summary = _source_bucket_summary(features)
    route_summary, upper_curves = _route_summary(SOURCE_SPECS, features, bucket_summary, curve, official)
    year_coverage = _year_coverage(features)

    posthoc_pass_count = int(route_summary["posthoc_candidate_like"].sum())
    if posthoc_pass_count:
        decision = "stage053_posthoc_bucket_exists_but_requires_ab_skill_before_engine"
    else:
        decision = "stage053_no_posthoc_external_bucket_pass_prioritize_member_rank_data_engineering"

    route_summary.to_csv(ROUTE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    year_coverage.to_csv(YEAR_COVERAGE_OUT, index=False, encoding="utf-8-sig")
    upper_curves.to_csv(UPPER_BOUND_CURVE_OUT, index=False, encoding="utf-8-sig")
    _write_charts(route_summary, year_coverage, upper_curves, curve, official)

    priority_view = route_summary[
        [
            "source_key",
            "ready_pct",
            "missing_net_pnl",
            "posthoc_best_negative_bucket",
            "posthoc_best_negative_bucket_net_pnl",
            "posthoc_best_negative_bucket_lot_count",
            "upper_bound_dd_improvement_pp",
            "upper_bound_return_retention_pct",
            "data_priority",
        ]
    ].copy()
    bucket_view = bucket_summary.sort_values(["source_key", "net_pnl"])[
        [
            "source_key",
            "bucket",
            "lot_count",
            "product_count",
            "year_count",
            "net_pnl",
            "positive_year_count",
            "negative_year_count",
        ]
    ].copy()
    official_line = {
        "official_end_equity": official["end_equity"],
        "official_total_return_pct": official["total_return_pct"],
        "official_max_dd_pct": official["max_dd_pct"],
        "official_max_dd_date": official["max_dd_date"],
        "official_sharpe": official["sharpe"],
        "official_total_slippage": official["total_slippage"],
        "official_total_trade_count": official["total_trade_count"],
        "official_win_rate_pct": official["win_rate_pct"],
        "official_broker10_peak_pct": official["broker10_peak_pct"],
    }
    decision_payload = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "posthoc_pass_count": posthoc_pass_count,
        "official_version": OFFICIAL_LIVE_VERSION,
        "official": official_line,
        "route_summary": route_summary.to_dict(orient="records"),
        "outputs": {
            "route_summary": ROUTE_SUMMARY_OUT,
            "bucket_summary": BUCKET_SUMMARY_OUT,
            "year_coverage": YEAR_COVERAGE_OUT,
            "upper_bound_curves": UPPER_BOUND_CURVE_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "coverage_chart": COVERAGE_CHART_OUT,
            "frontier_chart": FRONTIER_CHART_OUT,
            "year_heatmap": YEAR_HEATMAP_OUT,
            "bucket_chart": BUCKET_CHART_OUT,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# {STAGE} external source priority audit

## Positioning

- Official version: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`.
- This is a read-only source-priority audit after Stage052.
- It compares frozen external source audits: market breadth, term structure, supply/inventory, member rank, and Stage496 product trend t-stat.
- The "best negative bucket" is selected post hoc only to measure diagnostic upper bounds. It is not a trading rule and cannot be promoted.

## Official Baseline

| item | value |
| --- | ---: |
| end equity | {_fmt(official['end_equity'], 2)} |
| total return | {_fmt(official['total_return_pct'])}% |
| max DD | {_fmt(official['max_dd_pct'])}% |
| Sharpe | {_fmt(official['sharpe'])} |
| total slippage | {_fmt(official['total_slippage'], 2)} |
| total trades | {_fmt(official['total_trade_count'], 0)} |
| win rate | {_fmt(official['win_rate_pct'])}% |

## Route Summary

{_md_table(priority_view)}

## Bucket Summary

{_md_table(bucket_view, max_rows=40)}

## Decision

- Decision: `{decision}`.
- No external source has a deployable post-hoc upper-bound shape under the line objective.
- Member rank remains the highest data-engineering priority because the economic prior is strongest and current coverage is only low-history / near-date.
- Supply/inventory official-source granularity is second priority; the current coarse AKShare score is nonmonotonic and should not be traded.
- Stage496 product t-stat is closed as a trading route and can remain a monitoring/data asset only.

## Visuals

- Path chart: `{PATH_CHART_OUT.name}`.
- Coverage gap chart: `{COVERAGE_CHART_OUT.name}`.
- Source priority frontier: `{FRONTIER_CHART_OUT.name}`.
- Ready-year heatmap: `{YEAR_HEATMAP_OUT.name}`.
- Best-negative bucket fragility: `{BUCKET_CHART_OUT.name}`.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe({"decision": decision, **official_line}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

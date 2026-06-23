from __future__ import annotations

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
STAGE = "Stage048"
MODEL_TAG = "stage048_lowvol_lowparticipation_robustness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit"

TARGET_STATE = "joint_low_vol_low_participation"
OFFICIAL_ARM = "A_official_stage847_c9_15w"
INITIAL_CAPITAL = 150_000.0

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage048_lowvol_lowparticipation_robustness_audit"

STAGE047_DIR = LINE_DIR / "outputs" / "stage047_vol_participation_joint_state_audit"
STAGE046_DIR = LINE_DIR / "outputs" / "stage046_entry_day_confirmed_breakeven_true_engine"

FEATURES_IN = (
    STAGE047_DIR
    / "qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit_features_"
    "stage047_vol_participation_joint_state_audit_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE046_DIR
    / "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_curve_"
    "stage046_entry_day_confirmed_breakeven_true_engine_v1.csv"
)

TARGET_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_lots_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
LEAVE_ONE_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_year_{MODEL_TAG}.csv"
LEAVE_ONE_PRODUCT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_product_{MODEL_TAG}.csv"
PRODUCT_YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_matrix_{MODEL_TAG}.csv"
UPPER_BOUND_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_curve_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

UPPER_BOUND_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_path_chart_{MODEL_TAG}.png"
TARGET_CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_contribution_chart_{MODEL_TAG}.png"
ROBUSTNESS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_robustness_chart_{MODEL_TAG}.png"
PRODUCT_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_heatmap_{MODEL_TAG}.png"
STATE_SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_scatter_highlight_{MODEL_TAG}.png"


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


def _normalize_product(vt_symbol: Any, fallback: Any) -> str:
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


def _load_features() -> pd.DataFrame:
    features = _read_csv(FEATURES_IN)
    required = {
        "stage047_vol_part_joint",
        "realized_pnl",
        "entry_date",
        "exit_date",
        "vt_symbol",
        "product_key",
        "prev_rolling20_ann_vol_pct",
        "trend_participation_pct",
    }
    missing = required - set(features.columns)
    if missing:
        raise RuntimeError(f"Stage047 features missing columns: {sorted(missing)}")
    features["entry_date"] = pd.to_datetime(features["entry_date"], errors="coerce")
    features["exit_date"] = pd.to_datetime(features["exit_date"], errors="coerce")
    features["exit_year"] = features["exit_date"].dt.year.astype("Int64")
    features["realized_pnl"] = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    features["normalized_product"] = [
        _normalize_product(vt_symbol, fallback)
        for vt_symbol, fallback in zip(features["vt_symbol"], features["product_key"])
    ]
    features["is_stage048_target"] = features["stage047_vol_part_joint"].eq(TARGET_STATE)
    return features


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    if "arm" not in curve.columns:
        raise RuntimeError("official curve missing arm column")
    curve = curve[curve["arm"].eq(OFFICIAL_ARM)].copy()
    if curve.empty:
        raise RuntimeError(f"official curve arm is empty: {OFFICIAL_ARM}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    curve = curve.sort_values("date").reset_index(drop=True)
    return curve


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


def _official_metrics(curve: pd.DataFrame) -> dict[str, float | str]:
    metrics = _equity_metrics(curve["account_equity"], curve["date"])
    nonzero = curve[curve["net_pnl"].ne(0)]
    metrics.update(
        {
            "total_slippage": float(curve["slippage"].sum()),
            "total_trade_count": float(curve["trade_count"].sum()),
            "win_rate_pct": float((nonzero["net_pnl"] > 0).mean() * 100.0) if len(nonzero) else np.nan,
            "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
            "days_over_100pct": float((curve["broker10_margin_to_equity_pct"] > 100.0).sum()),
        }
    )
    return metrics


def _build_upper_bound_curve(curve: pd.DataFrame, target: pd.DataFrame) -> pd.DataFrame:
    cashflow = (
        target.dropna(subset=["exit_date"])
        .groupby("exit_date", as_index=False)
        .agg(target_realized_pnl=("realized_pnl", "sum"), target_lot_count=("realized_pnl", "size"))
    )
    cashflow = cashflow.rename(columns={"exit_date": "date"})
    upper = curve[["date", "account_equity", "drawdown_pct", "nav", "broker10_margin_to_equity_pct"]].copy()
    upper = upper.merge(cashflow, on="date", how="left")
    upper["target_realized_pnl"] = upper["target_realized_pnl"].fillna(0.0)
    upper["target_lot_count"] = upper["target_lot_count"].fillna(0).astype(int)
    upper["skipped_target_pnl_cumsum"] = upper["target_realized_pnl"].cumsum()
    upper["upper_bound_skip_target_equity"] = upper["account_equity"] - upper["skipped_target_pnl_cumsum"]
    upper["upper_bound_nav"] = upper["upper_bound_skip_target_equity"] / INITIAL_CAPITAL
    upper["upper_bound_drawdown_pct"] = (
        upper["upper_bound_skip_target_equity"]
        / upper["upper_bound_skip_target_equity"].cummax()
        - 1.0
    ) * 100.0
    upper["official_drawdown_pct_recalc"] = (upper["account_equity"] / upper["account_equity"].cummax() - 1.0) * 100.0
    return upper


def _leave_one(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    total_pnl = float(frame["realized_pnl"].sum())
    total_count = int(len(frame))
    grouped = (
        frame.groupby(column, dropna=False)
        .agg(removed_count=("realized_pnl", "size"), removed_pnl=("realized_pnl", "sum"))
        .reset_index()
        .rename(columns={column: "removed_key"})
    )
    grouped["remaining_count"] = total_count - grouped["removed_count"]
    grouped["remaining_pnl"] = total_pnl - grouped["removed_pnl"]
    grouped["remaining_negative"] = grouped["remaining_pnl"] < 0
    grouped = grouped.sort_values("remaining_pnl").reset_index(drop=True)
    return grouped


def _target_summary(target: pd.DataFrame, all_features: pd.DataFrame) -> dict[str, Any]:
    total_positive = float(all_features["realized_pnl"].clip(lower=0).sum())
    total_negative_abs = float((-all_features["realized_pnl"].clip(upper=0)).sum())
    return {
        "target_state": TARGET_STATE,
        "target_lot_count": int(len(target)),
        "target_product_count": int(target["normalized_product"].nunique()),
        "target_year_count": int(target["exit_year"].nunique()),
        "target_net_pnl": float(target["realized_pnl"].sum()),
        "target_positive_pnl": float(target["realized_pnl"].clip(lower=0).sum()),
        "target_negative_pnl_abs": float((-target["realized_pnl"].clip(upper=0)).sum()),
        "target_positive_coverage_pct": float(
            target["realized_pnl"].clip(lower=0).sum() / total_positive * 100.0
        )
        if total_positive
        else np.nan,
        "target_negative_coverage_pct": float(
            (-target["realized_pnl"].clip(upper=0)).sum() / total_negative_abs * 100.0
        )
        if total_negative_abs
        else np.nan,
        "target_min_exit_date": target["exit_date"].min().strftime("%Y-%m-%d") if len(target) else "",
        "target_max_exit_date": target["exit_date"].max().strftime("%Y-%m-%d") if len(target) else "",
    }


def _write_charts(
    features: pd.DataFrame,
    target: pd.DataFrame,
    upper_curve: pd.DataFrame,
    leave_year: pd.DataFrame,
    leave_product: pd.DataFrame,
    product_year: pd.DataFrame,
) -> None:
    plt.rcParams.update({"figure.dpi": 130, "font.size": 9})

    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True)
    axes[0].plot(upper_curve["date"], upper_curve["account_equity"], label="official equity", linewidth=1.5)
    axes[0].plot(
        upper_curve["date"],
        upper_curve["upper_bound_skip_target_equity"],
        label="upper bound: skip target closed-lot cashflows",
        linewidth=1.5,
    )
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (log)")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(upper_curve["date"], upper_curve["official_drawdown_pct_recalc"], label="official DD", linewidth=1.2)
    axes[1].plot(upper_curve["date"], upper_curve["upper_bound_drawdown_pct"], label="upper-bound DD", linewidth=1.2)
    axes[1].set_ylabel("drawdown %")
    axes[1].legend(loc="lower left")
    axes[1].grid(True, alpha=0.25)

    axes[2].plot(
        upper_curve["date"],
        -upper_curve["skipped_target_pnl_cumsum"],
        color="#7f3b08",
        label="equity add-back from skipped target",
        linewidth=1.2,
    )
    axes[2].bar(
        upper_curve["date"],
        -upper_curve["target_realized_pnl"],
        color="#d95f0e",
        alpha=0.25,
        label="daily add-back",
    )
    axes[2].set_ylabel("cashflow impact")
    axes[2].legend(loc="upper left")
    axes[2].grid(True, alpha=0.25)
    fig.suptitle("Stage048 upper-bound path audit: target skip is not a true engine")
    fig.tight_layout()
    fig.savefig(UPPER_BOUND_PATH_CHART_OUT)
    plt.close(fig)

    target_curve = target.dropna(subset=["exit_date"]).sort_values(["exit_date", "normalized_product"]).copy()
    target_curve["cumulative_pnl"] = target_curve["realized_pnl"].cumsum()
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = np.where(target_curve["realized_pnl"] >= 0, "#238b45", "#cb181d")
    ax.bar(target_curve["exit_date"], target_curve["realized_pnl"], color=colors, alpha=0.35, width=8)
    ax.plot(target_curve["exit_date"], target_curve["cumulative_pnl"], color="#08519c", linewidth=1.8)
    for year in sorted(target_curve["exit_year"].dropna().unique()):
        year_dt = pd.Timestamp(f"{int(year)}-01-01")
        ax.axvline(year_dt, color="black", alpha=0.06, linewidth=0.8)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Target cohort realized contribution by exit date")
    ax.set_ylabel("PnL")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(TARGET_CONTRIBUTION_CHART_OUT)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    year_plot = leave_year.copy()
    axes[0].bar(year_plot["removed_key"].astype(str), year_plot["remaining_pnl"], color="#6baed6")
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set_title("Leave-one-year remaining target PnL")
    axes[0].set_ylabel("remaining PnL")
    axes[0].grid(True, axis="y", alpha=0.25)

    product_plot = leave_product.sort_values("remaining_pnl").head(15).copy()
    axes[1].bar(product_plot["removed_key"].astype(str), product_plot["remaining_pnl"], color="#9ecae1")
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Leave-one-product remaining target PnL (worst 15 by remaining PnL)")
    axes[1].set_ylabel("remaining PnL")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ROBUSTNESS_CHART_OUT)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, max(4, 0.35 * len(product_year))))
    matrix = product_year.set_index("normalized_product")
    values = matrix.to_numpy(dtype=float)
    vmax = np.nanmax(np.abs(values)) if values.size else 1.0
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels([str(col) for col in matrix.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_title("Target cohort product-year realized PnL")
    fig.colorbar(image, ax=ax, shrink=0.82, label="PnL")
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_HEATMAP_OUT)
    plt.close(fig)

    scatter = features[
        features["prev_rolling20_ann_vol_pct"].notna() & features["trend_participation_pct"].notna()
    ].copy()
    fig, ax = plt.subplots(figsize=(9, 6))
    non_target = scatter[~scatter["is_stage048_target"]]
    target_scatter = scatter[scatter["is_stage048_target"]]
    ax.scatter(
        non_target["prev_rolling20_ann_vol_pct"],
        non_target["trend_participation_pct"],
        s=18,
        c=np.where(non_target["realized_pnl"] >= 0, "#74c476", "#fb6a4a"),
        alpha=0.35,
        label="other lots",
    )
    ax.scatter(
        target_scatter["prev_rolling20_ann_vol_pct"],
        target_scatter["trend_participation_pct"],
        s=46,
        facecolors="none",
        edgecolors="#08519c",
        linewidths=1.2,
        label="target state",
    )
    ax.axvline(50.0, color="black", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.axhline(25.0, color="black", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("prev rolling20 annualized vol pct")
    ax.set_ylabel("trend participation pct")
    ax.set_title("Stage047 state space highlight")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(STATE_SCATTER_OUT)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    target = features[features["is_stage048_target"]].copy()
    if target.empty:
        raise RuntimeError(f"target state is empty: {TARGET_STATE}")
    curve = _load_official_curve()

    official = _official_metrics(curve)
    upper_curve = _build_upper_bound_curve(curve, target)
    upper_metrics = _equity_metrics(upper_curve["upper_bound_skip_target_equity"], upper_curve["date"])

    leave_year = _leave_one(target, "exit_year")
    leave_product = _leave_one(target, "normalized_product")
    product_year = (
        target.pivot_table(
            index="normalized_product",
            columns="exit_year",
            values="realized_pnl",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )
    product_year = product_year.loc[
        product_year.drop(columns=["normalized_product"]).abs().sum(axis=1).sort_values(ascending=False).index
    ]

    summary = _target_summary(target, features)
    exclude_2026 = leave_year[leave_year["removed_key"].astype(str).eq("2026")]
    excluding_2026_pnl = float(exclude_2026["remaining_pnl"].iloc[0]) if len(exclude_2026) else np.nan
    worst_product_removed = leave_product.sort_values("removed_pnl").head(1)
    excluding_top_loss_product_pnl = (
        float(worst_product_removed["remaining_pnl"].iloc[0]) if len(worst_product_removed) else np.nan
    )
    dd_improvement_pp = float(upper_metrics["max_dd_pct"] - official["max_dd_pct"])
    return_retention_pct = float(upper_metrics["total_return_pct"] / official["total_return_pct"] * 100.0)
    end_equity_delta = float(upper_metrics["end_equity"] - official["end_equity"])

    strict_pass = bool(
        summary["target_net_pnl"] < 0
        and excluding_2026_pnl < 0
        and excluding_top_loss_product_pnl < 0
        and dd_improvement_pp >= 3.0
        and return_retention_pct >= 80.0
    )
    decision = (
        "stage048_lowvol_lowparticipation_passes_frozen_precheck_needs_ab_skill_before_engine"
        if strict_pass
        else "stage048_lowvol_lowparticipation_fails_robustness_no_engine"
    )

    summary_row = {
        **summary,
        "official_version": OFFICIAL_LIVE_VERSION,
        "official_alias": OFFICIAL_LIVE_ALIAS,
        "official_end_equity": official["end_equity"],
        "official_total_return_pct": official["total_return_pct"],
        "official_max_dd_pct": official["max_dd_pct"],
        "official_max_dd_date": official["max_dd_date"],
        "official_sharpe": official["sharpe"],
        "official_total_slippage": official["total_slippage"],
        "official_total_trade_count": official["total_trade_count"],
        "official_win_rate_pct": official["win_rate_pct"],
        "official_broker10_peak_pct": official["max_broker10_margin_to_equity_pct"],
        "upper_bound_end_equity": upper_metrics["end_equity"],
        "upper_bound_total_return_pct": upper_metrics["total_return_pct"],
        "upper_bound_max_dd_pct": upper_metrics["max_dd_pct"],
        "upper_bound_max_dd_date": upper_metrics["max_dd_date"],
        "upper_bound_sharpe": upper_metrics["sharpe"],
        "upper_bound_end_equity_delta": end_equity_delta,
        "upper_bound_max_dd_improvement_pp": dd_improvement_pp,
        "upper_bound_return_retention_pct": return_retention_pct,
        "excluding_2026_remaining_pnl": excluding_2026_pnl,
        "excluding_top_loss_product_remaining_pnl": excluding_top_loss_product_pnl,
        "strict_precheck_pass": strict_pass,
        "decision": decision,
    }

    target.to_csv(TARGET_LOTS_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary_row]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    leave_year.to_csv(LEAVE_ONE_YEAR_OUT, index=False, encoding="utf-8-sig")
    leave_product.to_csv(LEAVE_ONE_PRODUCT_OUT, index=False, encoding="utf-8-sig")
    product_year.to_csv(PRODUCT_YEAR_MATRIX_OUT, index=False, encoding="utf-8-sig")
    upper_curve.to_csv(UPPER_BOUND_CURVE_OUT, index=False, encoding="utf-8-sig")

    _write_charts(features, target, upper_curve, leave_year, leave_product, product_year)

    decision_payload = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "strict_precheck_pass": strict_pass,
        "official_version": OFFICIAL_LIVE_VERSION,
        "target_state": TARGET_STATE,
        "target_summary": summary,
        "official_metrics": official,
        "upper_bound_metrics": upper_metrics,
        "upper_bound_end_equity_delta": end_equity_delta,
        "upper_bound_max_dd_improvement_pp": dd_improvement_pp,
        "upper_bound_return_retention_pct": return_retention_pct,
        "excluding_2026_remaining_pnl": excluding_2026_pnl,
        "excluding_top_loss_product_remaining_pnl": excluding_top_loss_product_pnl,
        "interpretation": (
            "Read-only closed-lot cashflow upper bound. It is not a true engine, does not alter "
            "official config, and does not prove live tradability."
        ),
        "outputs": {
            "target_lots": TARGET_LOTS_OUT,
            "summary": SUMMARY_OUT,
            "leave_one_year": LEAVE_ONE_YEAR_OUT,
            "leave_one_product": LEAVE_ONE_PRODUCT_OUT,
            "product_year_matrix": PRODUCT_YEAR_MATRIX_OUT,
            "upper_bound_curve": UPPER_BOUND_CURVE_OUT,
            "upper_bound_path_chart": UPPER_BOUND_PATH_CHART_OUT,
            "target_contribution_chart": TARGET_CONTRIBUTION_CHART_OUT,
            "robustness_chart": ROBUSTNESS_CHART_OUT,
            "product_year_heatmap": PRODUCT_YEAR_HEATMAP_OUT,
            "state_scatter": STATE_SCATTER_OUT,
        },
    }
    DECISION_OUT.write_text(
        json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    year_view = (
        target.groupby("exit_year")
        .agg(lots=("realized_pnl", "size"), net_pnl=("realized_pnl", "sum"))
        .reset_index()
        .sort_values("exit_year")
    )
    product_view = (
        target.groupby("normalized_product")
        .agg(lots=("realized_pnl", "size"), net_pnl=("realized_pnl", "sum"))
        .reset_index()
        .sort_values("net_pnl")
    )
    report = f"""# {STAGE} low-vol low-participation robustness audit

## Positioning

- Official version: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`.
- Target state: `{TARGET_STATE}` from Stage047 frozen buckets.
- This is a read-only closed-lot robustness and upper-bound audit. It is not a true engine and not a live candidate.
- No official config, CTP path, order API, product whitelist, year filter, or threshold is changed.

## Summary

| item | value |
| --- | ---: |
| target lots | {summary['target_lot_count']} |
| normalized products | {summary['target_product_count']} |
| years | {summary['target_year_count']} |
| target net PnL | {summary['target_net_pnl']:.2f} |
| target positive coverage % | {summary['target_positive_coverage_pct']:.4f} |
| target negative coverage % | {summary['target_negative_coverage_pct']:.4f} |
| official end equity | {official['end_equity']:.2f} |
| official total return % | {official['total_return_pct']:.4f} |
| official max DD % | {official['max_dd_pct']:.4f} |
| upper-bound end equity | {upper_metrics['end_equity']:.2f} |
| upper-bound total return % | {upper_metrics['total_return_pct']:.4f} |
| upper-bound max DD % | {upper_metrics['max_dd_pct']:.4f} |
| upper-bound max DD improvement pp | {dd_improvement_pp:.4f} |
| upper-bound return retention % | {return_retention_pct:.4f} |
| excluding 2026 remaining PnL | {excluding_2026_pnl:.2f} |
| excluding top-loss product remaining PnL | {excluding_top_loss_product_pnl:.2f} |
| decision | `{decision}` |

## Year Contribution

{_md_table(year_view)}

## Product Contribution

{_md_table(product_view)}

## Leave-One Year

{_md_table(leave_year)}

## Leave-One Product

{_md_table(leave_product, max_rows=20)}

## Visual Outputs

- Upper-bound equity/drawdown/cashflow path: `{UPPER_BOUND_PATH_CHART_OUT}`
- Target contribution curve: `{TARGET_CONTRIBUTION_CHART_OUT}`
- Leave-one robustness bars: `{ROBUSTNESS_CHART_OUT}`
- Product-year heatmap: `{PRODUCT_YEAR_HEATMAP_OUT}`
- State scatter highlight: `{STATE_SCATTER_OUT}`

## Judgment

The target state is a weak closed-lot cohort, but it fails the frozen pre-engine robustness gate unless it remains material after removing near-end 2026 and the largest product block, and unless its optimistic upper-bound path materially improves drawdown while retaining more than 80% of official return. This audit deliberately refuses threshold sweeps.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

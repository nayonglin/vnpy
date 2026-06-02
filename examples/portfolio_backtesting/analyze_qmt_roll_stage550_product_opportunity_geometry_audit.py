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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage550_product_opportunity_geometry_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage550_product_opportunity_geometry_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE541_TAG = "stage541_single_product_opportunity_map_v1"
STAGE541_PREFIX = "qmt_roll_stage541_single_product_opportunity_map"
STAGE541_SUMMARY_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_summary_{STAGE541_TAG}.csv"
STAGE541_ANNUAL_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_annual_{STAGE541_TAG}.csv"
STAGE541_DAILY_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_daily_{STAGE541_TAG}.csv"

STAGE543_TAG = "stage543_ex_ante_product_selector_diagnostic_v1"
STAGE543_PREFIX = "qmt_roll_stage543_ex_ante_product_selector_diagnostic"
STAGE543_SCORED_IN = OUTPUT_DIR / f"{STAGE543_PREFIX}_scored_samples_{STAGE543_TAG}.csv"

STAGE544_TAG = "stage544_family_constrained_selector_diagnostic_v1"
STAGE544_PREFIX = "qmt_roll_stage544_family_constrained_selector_diagnostic"
STAGE544_FAMILY_MAP_IN = OUTPUT_DIR / f"{STAGE544_PREFIX}_family_map_{STAGE544_TAG}.csv"

ANNUAL_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_matrix_{MODEL_TAG}.csv"
ANNUAL_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_summary_{MODEL_TAG}.csv"
ANNUAL_SELECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_selection_{MODEL_TAG}.csv"
FEATURE_IC_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_ic_{MODEL_TAG}.csv"
CORRELATION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_correlation_summary_{MODEL_TAG}.csv"
PRODUCT_DIAGNOSTIC_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_diagnostic_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

ORACLE6 = {"al.SHFE", "ao.SHFE", "c.DCE", "lu.INE", "v.DCE", "y.DCE"}
FINANCIAL_EXCHANGES = {"CFFEX"}
YEARS = list(range(2020, 2027))

FEATURES = [
    "ai_probability",
    "simple_trend",
    "market_terrain_equal",
    "strategy_memory_equal",
    "hybrid_equal",
    "hist_pnl_60d",
    "hist_pnl_120d",
    "hist_pnl_252d",
    "hist_sharpe_like_120d",
    "hist_sharpe_like_252d",
    "hist_active_days_120d",
    "hist_trade_count_120d",
    "hist_drawdown_120d",
    "low_core_corr_rank_pct",
    "core_corr_252d",
    "market_trend_efficiency_60d",
    "market_trend_efficiency_120d",
    "market_volume_ratio_60d",
    "market_open_interest_change_60d",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for path in [STAGE541_SUMMARY_IN, STAGE541_ANNUAL_IN, STAGE541_DAILY_IN, STAGE543_SCORED_IN, STAGE544_FAMILY_MAP_IN]:
        if not path.exists():
            raise FileNotFoundError(path)

    summary = pd.read_csv(STAGE541_SUMMARY_IN, encoding="utf-8-sig")
    annual = pd.read_csv(STAGE541_ANNUAL_IN, encoding="utf-8-sig")
    daily = pd.read_csv(STAGE541_DAILY_IN, encoding="utf-8-sig")
    scored = pd.read_csv(STAGE543_SCORED_IN, encoding="utf-8-sig")
    family_map = pd.read_csv(STAGE544_FAMILY_MAP_IN, encoding="utf-8-sig")

    for frame in [summary, annual, daily, scored, family_map]:
        if "product_vt_symbol" in frame.columns:
            frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    summary["is_core_product"] = pd.to_numeric(summary["is_core_product"], errors="coerce").fillna(0).astype(int)
    annual["is_core_product"] = pd.to_numeric(annual["is_core_product"], errors="coerce").fillna(0).astype(int)
    annual["year"] = pd.to_numeric(annual["year"], errors="coerce").fillna(0).astype(int)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    scored["eval_date"] = pd.to_datetime(scored["eval_date"], errors="coerce").dt.normalize()

    for frame, columns in [
        (summary, ["total_pnl", "core_daily_pnl_corr", "max_broker10_margin_to_sleeve_equity_pct"]),
        (annual, ["net_pnl", "trade_count", "slippage", "active_days"]),
        (daily, ["net_pnl", "trade_count", "slippage"]),
    ]:
        for column in columns:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    for column in FEATURES + ["future_stage541_pnl_60d", "future_stage541_pnl_120d"]:
        if column in scored.columns:
            scored[column] = pd.to_numeric(scored[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)

    return summary, annual, daily, scored, family_map


def _commodity_noncore(summary: pd.DataFrame) -> set[str]:
    frame = summary[summary["is_core_product"].eq(0)].copy()
    frame = frame[~frame["exchange"].astype(str).str.upper().isin(FINANCIAL_EXCHANGES)].copy()
    return set(frame["product_vt_symbol"].astype(str))


def _annual_matrix(summary: pd.DataFrame, annual: pd.DataFrame, family_map: pd.DataFrame) -> pd.DataFrame:
    noncore = _commodity_noncore(summary)
    annual = annual[annual["product_vt_symbol"].isin(noncore)].copy()
    base = (
        annual.pivot_table(index="product_vt_symbol", columns="year", values="net_pnl", aggfunc="sum", fill_value=0.0)
        .reindex(columns=YEARS, fill_value=0.0)
        .reset_index()
    )
    static = summary[["product_vt_symbol", "exchange", "product", "total_pnl", "core_daily_pnl_corr", "max_broker10_margin_to_sleeve_equity_pct"]].copy()
    matrix = base.merge(static, on="product_vt_symbol", how="left").merge(family_map, on="product_vt_symbol", how="left")
    matrix["is_oracle6"] = matrix["product_vt_symbol"].isin(ORACLE6).astype(int)
    matrix["positive_years"] = matrix[YEARS].gt(0.0).sum(axis=1)
    matrix["active_years"] = matrix[YEARS].ne(0.0).sum(axis=1)
    matrix["worst_year_pnl"] = matrix[YEARS].min(axis=1)
    matrix["best_year_pnl"] = matrix[YEARS].max(axis=1)
    matrix["annual_pnl_std"] = matrix[YEARS].std(axis=1)
    matrix.sort_values(["total_pnl", "positive_years"], ascending=[False, False], inplace=True)
    return matrix


def _annual_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year in YEARS:
        values = matrix[["product_vt_symbol", "product_family", "is_oracle6", year]].copy()
        values.rename(columns={year: "net_pnl"}, inplace=True)
        sorted_values = values.sort_values("net_pnl", ascending=False)
        positive = values[values["net_pnl"] > 0.0]
        top3 = sorted_values.head(3)
        top6 = sorted_values.head(6)
        oracle = values[values["is_oracle6"].eq(1)]
        rows.append(
            {
                "year": year,
                "product_count": int(len(values)),
                "positive_products": int(len(positive)),
                "positive_product_rate_pct": float(len(positive) / len(values) * 100.0) if len(values) else 0.0,
                "all_noncore_pnl": float(values["net_pnl"].sum()),
                "positive_only_pnl": float(positive["net_pnl"].sum()),
                "top3_pnl": float(top3["net_pnl"].sum()),
                "top6_pnl": float(top6["net_pnl"].sum()),
                "oracle6_pnl": float(oracle["net_pnl"].sum()),
                "top3_products": ",".join(top3["product_vt_symbol"].astype(str).tolist()),
                "top6_products": ",".join(top6["product_vt_symbol"].astype(str).tolist()),
                "oracle6_top6_overlap": int(top6["product_vt_symbol"].isin(ORACLE6).sum()),
                "best_product": str(sorted_values.iloc[0]["product_vt_symbol"]) if not sorted_values.empty else "",
                "best_product_pnl": float(sorted_values.iloc[0]["net_pnl"]) if not sorted_values.empty else 0.0,
                "worst_product": str(sorted_values.iloc[-1]["product_vt_symbol"]) if not sorted_values.empty else "",
                "worst_product_pnl": float(sorted_values.iloc[-1]["net_pnl"]) if not sorted_values.empty else 0.0,
                "top3_family_count": int(top3["product_family"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def _annual_selection_tests(matrix: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year in YEARS:
        current = matrix[["product_vt_symbol", "product_family", "is_oracle6", year]].copy()
        current.rename(columns={year: "future_year_pnl"}, inplace=True)
        if year > min(YEARS):
            previous = matrix[["product_vt_symbol", year - 1]].copy().rename(columns={year - 1: "prev_year_pnl"})
            current = current.merge(previous, on="product_vt_symbol", how="left")
            current["prev_year_pnl"] = current["prev_year_pnl"].fillna(0.0)
        else:
            current["prev_year_pnl"] = 0.0

        choices = {
            "all_noncore_equal": current,
            "hindsight_top3": current.sort_values("future_year_pnl", ascending=False).head(3),
            "hindsight_top6": current.sort_values("future_year_pnl", ascending=False).head(6),
            "oracle6_hindsight_basket": current[current["product_vt_symbol"].isin(ORACLE6)],
        }
        if year > min(YEARS):
            choices.update(
                {
                    "prev_year_top3": current.sort_values(["prev_year_pnl", "product_vt_symbol"], ascending=[False, True]).head(3),
                    "prev_year_top6": current.sort_values(["prev_year_pnl", "product_vt_symbol"], ascending=[False, True]).head(6),
                    "prev_year_positive": current[current["prev_year_pnl"] > 0.0],
                }
            )
            family_rows: list[pd.Series] = []
            for _, fam in current.sort_values(["prev_year_pnl", "product_vt_symbol"], ascending=[False, True]).groupby("product_family", sort=False):
                if not fam.empty:
                    family_rows.append(fam.iloc[0])
            choices["prev_year_family_cap1"] = pd.DataFrame(family_rows) if family_rows else current.iloc[:0]

        for mode, selected in choices.items():
            selected = selected.copy()
            rows.append(
                {
                    "year": year,
                    "mode": mode,
                    "selected_count": int(len(selected)),
                    "future_year_pnl_sum": float(selected["future_year_pnl"].sum()) if not selected.empty else 0.0,
                    "future_year_pnl_mean": float(selected["future_year_pnl"].mean()) if not selected.empty else 0.0,
                    "positive_selected_count": int((selected["future_year_pnl"] > 0.0).sum()) if not selected.empty else 0,
                    "selected_products": ",".join(selected["product_vt_symbol"].astype(str).tolist()) if not selected.empty else "",
                    "oracle6_overlap": int(selected["product_vt_symbol"].isin(ORACLE6).sum()) if not selected.empty else 0,
                    "family_count": int(selected["product_family"].nunique()) if not selected.empty else 0,
                }
            )
    selection = pd.DataFrame(rows)
    mode_summary = (
        selection.groupby("mode")
        .agg(
            years=("year", "nunique"),
            avg_selected_count=("selected_count", "mean"),
            avg_future_year_pnl_sum=("future_year_pnl_sum", "mean"),
            total_future_year_pnl_sum=("future_year_pnl_sum", "sum"),
            positive_year_rate_pct=("future_year_pnl_sum", lambda item: float((item > 0.0).mean() * 100.0)),
            avg_oracle6_overlap=("oracle6_overlap", "mean"),
            avg_family_count=("family_count", "mean"),
        )
        .reset_index()
    )
    return selection.merge(mode_summary.add_prefix("mode_summary_"), left_on="mode", right_on="mode_summary_mode", how="left")


def _feature_ic(scored: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    noncore = _commodity_noncore(summary)
    scored = scored[scored["product_vt_symbol"].isin(noncore)].copy()
    rows: list[dict[str, Any]] = []
    for horizon in (60, 120):
        target = f"future_stage541_pnl_{horizon}d"
        for feature in FEATURES:
            if feature not in scored.columns or target not in scored.columns:
                continue
            date_ics: list[float] = []
            for _, frame in scored.groupby("eval_date", sort=True):
                if frame[feature].nunique(dropna=True) <= 1 or frame[target].nunique(dropna=True) <= 1:
                    continue
                ic = frame[feature].rank().corr(frame[target].rank())
                if pd.notna(ic) and math.isfinite(float(ic)):
                    date_ics.append(float(ic))
            if not date_ics:
                continue
            arr = np.asarray(date_ics, dtype=float)
            rows.append(
                {
                    "feature": feature,
                    "horizon_days": horizon,
                    "months": int(len(arr)),
                    "mean_spearman_ic": float(np.mean(arr)),
                    "median_spearman_ic": float(np.median(arr)),
                    "positive_ic_rate_pct": float(np.mean(arr > 0.0) * 100.0),
                    "ic_std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
                    "t_like": float(np.mean(arr) / (np.std(arr, ddof=1) / math.sqrt(len(arr)))) if len(arr) > 1 and np.std(arr, ddof=1) > 0 else 0.0,
                    "p10_ic": float(np.percentile(arr, 10)),
                    "p90_ic": float(np.percentile(arr, 90)),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["horizon_days", "mean_spearman_ic"], ascending=[True, False], inplace=True)
    return result


def _correlation_summary(daily: pd.DataFrame, summary: pd.DataFrame, family_map: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    noncore = _commodity_noncore(summary)
    daily = daily[daily["product_vt_symbol"].isin(noncore)].copy()
    pivot = daily.pivot_table(index="date", columns="product_vt_symbol", values="net_pnl", aggfunc="sum", fill_value=0.0)
    active_counts = pivot.ne(0.0).sum()
    active_products = active_counts[active_counts >= 20].index.tolist()
    pivot = pivot[active_products]
    corr = pivot.corr().replace([np.inf, -np.inf], np.nan).fillna(0.0)

    product_diag = summary[summary["product_vt_symbol"].isin(noncore)].copy()
    product_diag = product_diag.merge(family_map, on="product_vt_symbol", how="left")
    product_diag["is_oracle6"] = product_diag["product_vt_symbol"].isin(ORACLE6).astype(int)
    product_diag["active_days_from_daily"] = product_diag["product_vt_symbol"].map(active_counts).fillna(0).astype(int)

    rows: list[dict[str, Any]] = []
    family_lookup = product_diag.set_index("product_vt_symbol")["product_family"].to_dict()
    for i, left in enumerate(corr.columns):
        for right in corr.columns[i + 1 :]:
            rows.append(
                {
                    "left": left,
                    "right": right,
                    "left_family": family_lookup.get(left, ""),
                    "right_family": family_lookup.get(right, ""),
                    "same_family": int(family_lookup.get(left, "") == family_lookup.get(right, "")),
                    "corr": float(corr.loc[left, right]),
                    "abs_corr": float(abs(corr.loc[left, right])),
                    "left_is_oracle6": int(left in ORACLE6),
                    "right_is_oracle6": int(right in ORACLE6),
                }
            )
    pair_frame = pd.DataFrame(rows)
    summary_rows = [
        {
            "group": "all_pairs",
            "pairs": int(len(pair_frame)),
            "avg_abs_corr": float(pair_frame["abs_corr"].mean()) if not pair_frame.empty else 0.0,
            "p90_abs_corr": float(pair_frame["abs_corr"].quantile(0.90)) if not pair_frame.empty else 0.0,
            "avg_corr": float(pair_frame["corr"].mean()) if not pair_frame.empty else 0.0,
        }
    ]
    for name, frame in [
        ("same_family_pairs", pair_frame[pair_frame["same_family"].eq(1)] if not pair_frame.empty else pair_frame),
        ("cross_family_pairs", pair_frame[pair_frame["same_family"].eq(0)] if not pair_frame.empty else pair_frame),
        ("oracle_involved_pairs", pair_frame[(pair_frame["left_is_oracle6"].eq(1)) | (pair_frame["right_is_oracle6"].eq(1))] if not pair_frame.empty else pair_frame),
    ]:
        summary_rows.append(
            {
                "group": name,
                "pairs": int(len(frame)),
                "avg_abs_corr": float(frame["abs_corr"].mean()) if not frame.empty else 0.0,
                "p90_abs_corr": float(frame["abs_corr"].quantile(0.90)) if not frame.empty else 0.0,
                "avg_corr": float(frame["corr"].mean()) if not frame.empty else 0.0,
            }
        )
    corr_summary = pd.DataFrame(summary_rows)

    product_diag["avg_abs_corr_to_active_noncore"] = product_diag["product_vt_symbol"].map(
        {
            product: float(corr[product].drop(index=product, errors="ignore").abs().mean())
            for product in corr.columns
        }
    ).fillna(0.0)
    return corr_summary, product_diag


def _decision(
    annual_summary: pd.DataFrame,
    annual_selection: pd.DataFrame,
    feature_ic: pd.DataFrame,
    corr_summary: pd.DataFrame,
    product_diag: pd.DataFrame,
) -> dict[str, Any]:
    mode_summary = (
        annual_selection[
            [
                "mode",
                "mode_summary_years",
                "mode_summary_avg_selected_count",
                "mode_summary_avg_future_year_pnl_sum",
                "mode_summary_total_future_year_pnl_sum",
                "mode_summary_positive_year_rate_pct",
                "mode_summary_avg_oracle6_overlap",
                "mode_summary_avg_family_count",
            ]
        ]
        .drop_duplicates("mode")
        .sort_values("mode_summary_avg_future_year_pnl_sum", ascending=False)
    )
    best_ex_ante = mode_summary[mode_summary["mode"].isin(["prev_year_top3", "prev_year_top6", "prev_year_positive", "prev_year_family_cap1"])]
    best_ex_ante_record = best_ex_ante.head(1).to_dict("records")[0] if not best_ex_ante.empty else {}
    best_ic60 = feature_ic[feature_ic["horizon_days"].eq(60)].head(5).to_dict("records") if not feature_ic.empty else []
    best_ic120 = feature_ic[feature_ic["horizon_days"].eq(120)].head(5).to_dict("records") if not feature_ic.empty else []
    all_noncore = mode_summary[mode_summary["mode"].eq("all_noncore_equal")]
    oracle = mode_summary[mode_summary["mode"].eq("oracle6_hindsight_basket")]
    hindsight = mode_summary[mode_summary["mode"].eq("hindsight_top6")]
    ex_ante_value = float(best_ex_ante_record.get("mode_summary_avg_future_year_pnl_sum", 0.0) or 0.0)
    all_value = float(all_noncore["mode_summary_avg_future_year_pnl_sum"].iloc[0]) if not all_noncore.empty else 0.0
    oracle_value = float(oracle["mode_summary_avg_future_year_pnl_sum"].iloc[0]) if not oracle.empty else 0.0
    hindsight_value = float(hindsight["mode_summary_avg_future_year_pnl_sum"].iloc[0]) if not hindsight.empty else 0.0

    if ex_ante_value > all_value and ex_ante_value > 0.25 * max(hindsight_value, 1.0):
        label = "annual_ex_ante_selection_has_signal_needs_true_sleeve_replay"
    else:
        label = "opportunity_exists_but_ex_ante_selection_weak_keep_forward_state_research"

    return {
        "stage": "Stage250",
        "script_stage": "Stage550",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": label,
        "annual_positive_product_rate_avg_pct": float(annual_summary["positive_product_rate_pct"].mean()),
        "annual_top3_family_count_avg": float(annual_summary["top3_family_count"].mean()),
        "all_noncore_avg_year_pnl": all_value,
        "oracle6_hindsight_avg_year_pnl": oracle_value,
        "hindsight_top6_avg_year_pnl": hindsight_value,
        "best_ex_ante_annual_mode": best_ex_ante_record,
        "best_feature_ic_60d": best_ic60,
        "best_feature_ic_120d": best_ic120,
        "correlation_summary": corr_summary.to_dict("records"),
        "oracle6_products": product_diag[product_diag["is_oracle6"].eq(1)][
            [
                "product_vt_symbol",
                "product_family",
                "total_pnl",
                "core_daily_pnl_corr",
                "avg_abs_corr_to_active_noncore",
                "max_broker10_margin_to_sleeve_equity_pct",
            ]
        ].to_dict("records"),
        "overfit_boundary": "This audit uses hindsight only for upper-bound labels; no product set is promoted without point-in-time selector evidence.",
        "next_step": "If ex-ante annual persistence is weak, do not build a dynamic selector; keep accumulating forward external state and test only low-freedom sleeve structures.",
    }


def _make_chart(
    matrix: pd.DataFrame,
    annual_summary: pd.DataFrame,
    annual_selection: pd.DataFrame,
    feature_ic: pd.DataFrame,
    corr_summary: pd.DataFrame,
    product_diag: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(18, 16))
    fig.suptitle(f"Stage550 product opportunity geometry: {decision['decision']}", fontsize=13)

    top_products = matrix.sort_values("total_pnl", ascending=False).head(18).copy()
    labels = [
        f"{row.product_vt_symbol}{'*' if int(row.is_oracle6) else ''}"
        for row in top_products.itertuples(index=False)
    ]
    heat = top_products[YEARS].to_numpy(dtype=float)
    vmax = np.nanpercentile(np.abs(heat), 95) if heat.size else 1.0
    vmax = max(vmax, 1.0)
    ax = axes[0, 0]
    im = ax.imshow(heat, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_title("Top non-core product annual PnL (*=Oracle6)")
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xticks(np.arange(len(YEARS)))
    ax.set_xticklabels([str(year) for year in YEARS], rotation=30)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 1]
    ax.bar(annual_summary["year"].astype(str), annual_summary["positive_products"], color="#2b6cb0")
    ax.set_title("Positive non-core products by year")
    ax.set_ylabel("products")
    ax.grid(axis="y", alpha=0.25)
    ax2 = ax.twinx()
    ax2.plot(annual_summary["year"].astype(str), annual_summary["positive_product_rate_pct"], color="#c05621", marker="o")
    ax2.set_ylabel("positive rate %")

    mode_summary = (
        annual_selection[
            [
                "mode",
                "mode_summary_avg_future_year_pnl_sum",
                "mode_summary_positive_year_rate_pct",
                "mode_summary_avg_family_count",
            ]
        ]
        .drop_duplicates("mode")
        .sort_values("mode_summary_avg_future_year_pnl_sum", ascending=True)
    )
    ax = axes[1, 0]
    colors = ["#2f855a" if "hindsight" in mode or "oracle" in mode else "#2b6cb0" for mode in mode_summary["mode"]]
    ax.barh(mode_summary["mode"], mode_summary["mode_summary_avg_future_year_pnl_sum"], color=colors)
    ax.set_title("Annual selector diagnostic: avg future-year PnL")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.grid(axis="x", alpha=0.25)

    ax = axes[1, 1]
    ic60 = feature_ic[feature_ic["horizon_days"].eq(60)].sort_values("mean_spearman_ic", ascending=False).head(10)
    ax.barh(ic60["feature"][::-1], ic60["mean_spearman_ic"][::-1], color="#805ad5")
    ax.set_title("Best point-in-time feature IC for future 60d")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.grid(axis="x", alpha=0.25)

    ax = axes[2, 0]
    plot_diag = product_diag[product_diag["active_days_from_daily"] >= 20].copy()
    colors = np.where(plot_diag["is_oracle6"].eq(1), "#d53f8c", "#4a5568")
    ax.scatter(
        plot_diag["core_daily_pnl_corr"],
        plot_diag["total_pnl"],
        s=np.clip(plot_diag["active_days_from_daily"], 20, 350) / 2,
        c=colors,
        alpha=0.75,
        edgecolor="white",
        linewidth=0.5,
    )
    for row in plot_diag[plot_diag["is_oracle6"].eq(1)].itertuples(index=False):
        ax.text(row.core_daily_pnl_corr, row.total_pnl, row.product_vt_symbol, fontsize=8)
    ax.set_title("Standalone PnL vs core correlation")
    ax.set_xlabel("corr to Stage526 daily PnL")
    ax.set_ylabel("total PnL")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.grid(alpha=0.25)

    ax = axes[2, 1]
    corr_plot = corr_summary.copy()
    x = np.arange(len(corr_plot))
    ax.bar(x, corr_plot["avg_abs_corr"], color="#dd6b20")
    ax.set_title("Average abs correlation by pair group")
    ax.set_ylabel("avg abs corr")
    ax.set_xticks(x)
    ax.set_xticklabels(corr_plot["group"], rotation=25, ha="right")
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    annual_summary: pd.DataFrame,
    annual_selection: pd.DataFrame,
    feature_ic: pd.DataFrame,
    corr_summary: pd.DataFrame,
    product_diag: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    mode_summary = (
        annual_selection[
            [
                "mode",
                "mode_summary_avg_selected_count",
                "mode_summary_avg_future_year_pnl_sum",
                "mode_summary_total_future_year_pnl_sum",
                "mode_summary_positive_year_rate_pct",
                "mode_summary_avg_oracle6_overlap",
                "mode_summary_avg_family_count",
            ]
        ]
        .drop_duplicates("mode")
        .sort_values("mode_summary_avg_future_year_pnl_sum", ascending=False)
    )
    oracle_diag = product_diag[product_diag["is_oracle6"].eq(1)].sort_values("total_pnl", ascending=False)
    lines = [
        "# Stage550 产品机会几何审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`。",
        "- 阶段性质：只读诊断；不做收益回测，不生成交易候选。",
        "- 核心问题：非核心品种是否每年都有趋势机会，以及这些机会能否被当时可见特征提前识别。",
        "",
        "## Annual Opportunity",
        "",
        _md_table(
            annual_summary[
                [
                    "year",
                    "positive_products",
                    "positive_product_rate_pct",
                    "top3_pnl",
                    "top6_pnl",
                    "oracle6_pnl",
                    "top3_products",
                    "oracle6_top6_overlap",
                ]
            ]
        ),
        "",
        "## Annual Selector Modes",
        "",
        _md_table(mode_summary),
        "",
        "## Feature IC",
        "",
        _md_table(feature_ic.head(15)),
        "",
        "## Correlation",
        "",
        _md_table(corr_summary),
        "",
        "## Oracle6 Diagnostics",
        "",
        _md_table(
            oracle_diag[
                [
                    "product_vt_symbol",
                    "product_family",
                    "total_pnl",
                    "core_daily_pnl_corr",
                    "avg_abs_corr_to_active_noncore",
                    "positive_years",
                    "worst_year_pnl",
                    "best_year_pnl",
                    "max_broker10_margin_to_sleeve_equity_pct",
                ]
            ]
        ),
        "",
        "## 判断",
        "",
        "- 非核心品种确实每年都有一批正收益机会，且 Oracle6 多为低核心相关、低保证金占用的可承载品种。",
        "- 但年度 hindsight top 与 Oracle6 上限显著高于上一年赢家延续、现有AI概率、simple趋势分和策略记忆特征，说明当前事前选品能力仍不足。",
        "- 相关性约束应继续作为风险预算壳，而不是 alpha 来源；真正缺的是可在当时获得、能解释趋势土壤变化的外生状态。",
        "- 不建议根据本报告直接接入任何固定新品种篮子；下一步应继续积累 forward 外生状态账本，或只测试低自由度、非挤占式、核心不替换的 sleeve 结构。",
        "",
        "## 输出文件",
        "",
        f"- annual matrix：`{ANNUAL_MATRIX_PATH}`",
        f"- annual summary：`{ANNUAL_SUMMARY_PATH}`",
        f"- annual selection：`{ANNUAL_SELECTION_PATH}`",
        f"- feature IC：`{FEATURE_IC_PATH}`",
        f"- correlation summary：`{CORRELATION_SUMMARY_PATH}`",
        f"- product diagnostic：`{PRODUCT_DIAGNOSTIC_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, annual, daily, scored, family_map = _load_inputs()
    matrix = _annual_matrix(summary, annual, family_map)
    annual_summary = _annual_summary(matrix)
    annual_selection = _annual_selection_tests(matrix)
    feature_ic = _feature_ic(scored, summary)
    corr_summary, product_diag = _correlation_summary(daily, summary, family_map)

    # Add annual geometry columns to product diagnostics for reporting.
    product_diag = product_diag.merge(
        matrix[
            [
                "product_vt_symbol",
                "positive_years",
                "active_years",
                "worst_year_pnl",
                "best_year_pnl",
                "annual_pnl_std",
            ]
        ],
        on="product_vt_symbol",
        how="left",
    )

    decision = _decision(annual_summary, annual_selection, feature_ic, corr_summary, product_diag)

    matrix.to_csv(ANNUAL_MATRIX_PATH, index=False, encoding="utf-8-sig")
    annual_summary.to_csv(ANNUAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual_selection.to_csv(ANNUAL_SELECTION_PATH, index=False, encoding="utf-8-sig")
    feature_ic.to_csv(FEATURE_IC_PATH, index=False, encoding="utf-8-sig")
    corr_summary.to_csv(CORRELATION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_diag.to_csv(PRODUCT_DIAGNOSTIC_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(annual_summary, annual_selection, feature_ic, corr_summary, product_diag, decision)
    _make_chart(matrix, annual_summary, annual_selection, feature_ic, corr_summary, product_diag, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
